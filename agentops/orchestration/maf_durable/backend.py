"""MAF durable orchestration backend — feature-flagged parallel to legacy.

Schedules one durable instance per backlog task, advances via checkpointed
activities that wrap Controller (Kian/Negar/Git/CI/QA unchanged). Self-heal
still uses MaintenanceLoop. Default supervisor stays on LegacyBackend.
"""
import logging
from pathlib import Path

from agentops.orchestration.maf_durable.activities import TaskActivities
from agentops.orchestration.maf_durable.dts_bridge import try_describe_dts
from agentops.orchestration.maf_durable.engine import LocalDurableEngine
from agentops.orchestration.maf_durable.checkpoint_store import CheckpointStore
from agentops.orchestration.maf_durable.lifecycle import WAITING_STEPS

log = logging.getLogger(__name__)


def default_checkpoint_root(cfg) -> Path:
    override = getattr(cfg, "durable_checkpoint_dir", "") or ""
    if override:
        return Path(override)
    state = Path(cfg.state_path)
    if str(state) == ":memory:" or not state.parent.exists():
        base = Path.home() / "AppData" / "Local" / "trading-agent-lab" / "durable"
        return base / "checkpoints"
    return state.parent.parent / "durable" / "checkpoints"


class MafDurableBackend:
    """Durable Development Core host. Does not rewrite trading or role logic."""

    name = "maf_durable"

    def __init__(self, cfg, controller, healer, *, engine: LocalDurableEngine | None = None):
        self.cfg = cfg
        self.controller = controller
        self.healer = healer
        self.last_heal_reports: list[dict] = []
        self.dts_info = try_describe_dts(cfg.dts_endpoint, cfg.dts_task_hub)
        if engine is not None:
            self.engine = engine
        else:
            store = CheckpointStore(default_checkpoint_root(cfg))
            self.engine = LocalDurableEngine(store, TaskActivities(controller))
        # Persist durable ids onto tasks for status honesty.
        controller.db.set("orchestration_backend", self.name)
        controller.db.set("durable_runtime", self.dts_info.get("runtime"))

    def tick(self) -> None:
        self.last_heal_reports = self.healer.tick() or []
        ctl = self.controller
        # Stuck watch + PR reconcile still owned by Controller (parity).
        ctl.watch_stuck_workers()
        for task in ctl.db.tasks():
            if (
                task.get("state") in {"BLOCKED", "PENDING", "LAUNCHING_DEV"}
                and task.get("pr")
                and not task.get("run_id")
            ):
                try:
                    ctl.reconcile_existing_delivery(task)
                except Exception:  # noqa: BLE001
                    pass

        # Advance research via existing controller path (unchanged).
        from agentops.research_contracts import ResearchState
        from agentops.providers import ProviderError

        for task in ctl.db.research_tasks():
            if task["state"] in {
                ResearchState.PENDING.value,
                ResearchState.LAUNCHING.value,
                ResearchState.RUNNING.value,
            }:
                try:
                    if ctl.clock() < float(task.get("backoff_until") or 0):
                        continue
                    ctl.advance_research(task)
                except ProviderError as exc:
                    ctl.event(task, "PROVIDER_UNAVAILABLE", str(exc))
                except (ValueError, KeyError, RuntimeError) as exc:
                    task = ctl.db.research(task["id"]) or task
                    task.update(state=ResearchState.BLOCKED.value, blocker=str(exc)[:1000])
                    ctl.db.save_research(task)
                    ctl.event(task, "RESEARCH_BLOCKED", str(exc))

        if ctl.db.get("paused", True):
            self.engine.advance_all_running(max_steps_each=1)
            self._sync_durable_ids()
            return

        # Schedule durable instances for ready PENDING tasks up to coding slots.
        busy = [t for t in ctl.db.tasks() if ctl.occupies_coding_worker(t)]
        # Waiting durable steps must not consume coding slots.
        slots = ctl.max_coding_workers() - len(busy)
        done = {t["id"] for t in ctl.db.tasks() if t["state"] == "DONE"}
        if slots > 0:
            launched = 0
            for task in ctl.db.tasks():
                if launched >= slots:
                    break
                if task["state"] != "PENDING":
                    continue
                spec = ctl.specs[task["id"]]
                if spec["phase"] > ctl.cfg.max_phase or not set(spec["depends_on"]) <= done:
                    continue
                if ctl.research_gate_for_dev(spec):
                    continue
                if self.engine.running_for_task(task["id"]):
                    continue
                rec = self.engine.start_task(task["id"])
                task["durable_instance_id"] = rec["instance_id"]
                ctl.db.save(task)
                launched += 1

        # Attach or replace durable instances for mid-flight coding tasks.
        for task in ctl.db.tasks():
            if task.get("state") in {"DONE", "BLOCKED", "PENDING"}:
                continue
            existing_id = task.get("durable_instance_id")
            existing = self.engine.get(existing_id) if existing_id else None
            if existing and existing.get("status") == "Running":
                continue
            # Failed/missing instances must not permanently freeze LAUNCHING_* shells.
            force_new = bool(existing and existing.get("status") in {"Failed", "Completed"})
            if existing and existing.get("status") == "Completed" and task.get("state") == "DONE":
                continue
            rec = self.engine.start_task(task["id"], force_new=force_new or not existing)
            task["durable_instance_id"] = rec["instance_id"]
            task["durable_status"] = rec.get("status")
            ctl.db.save(task)

        # Relaunch LAUNCHING_* shells that lost run_id (e.g. after ERROR / supervisor restart).
        for task in ctl.db.tasks():
            if task.get("state") not in {"LAUNCHING_DEV", "LAUNCHING_QA"}:
                continue
            if task.get("run_id"):
                continue
            if ctl.clock() < float(task.get("backoff_until") or 0):
                continue
            if len([t for t in ctl.db.tasks() if ctl.occupies_coding_worker(t)]) >= ctl.max_coding_workers():
                break
            role = "qa" if task.get("state") == "LAUNCHING_QA" else "dev"
            try:
                ctl.launch(task, role)
            except Exception as exc:  # noqa: BLE001
                log.warning("Relaunch failed for %s: %s", task.get("id"), exc)

        self.engine.advance_all_running(max_steps_each=2)
        self._sync_durable_ids()

        # Close DONE issues (parity with Controller.tick tail).
        for task in ctl.db.tasks():
            if task["state"] == "DONE" and task.get("issue") and not task.get("issue_closed"):
                try:
                    ctl.gh.close_issue(task["issue"])
                    task["issue_closed"] = True
                    ctl.db.save(task)
                except Exception:  # noqa: BLE001
                    pass

    def _sync_durable_ids(self) -> None:
        for rec in self.engine.store.list_all():
            task = self.controller.db.task(rec["task_id"])
            if not task:
                continue
            task["durable_instance_id"] = rec["instance_id"]
            task["durable_status"] = rec.get("status")
            task["durable_current_step"] = rec.get("current_step")
            if rec.get("status") == "Failed" and task.get("state") not in {"BLOCKED", "DONE"}:
                task.setdefault("last_error", rec.get("error"))
            self.controller.db.save(task)

    def flush(self) -> None:
        self.controller.flush()

    def handle(self, update: dict) -> None:
        self.controller.handle(update)

    def occupies_coding_via_durable(self, task: dict) -> bool:
        """Waiting durable steps free the coding slot for unrelated work."""
        step = task.get("durable_current_step")
        if step in WAITING_STEPS and task.get("state") in {
            "CI_WAIT",
            "WAITING_APPROVAL",
            "MERGING",
        }:
            return False
        return self.controller.occupies_coding_worker(task)
