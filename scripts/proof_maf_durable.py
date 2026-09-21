"""Isolated live proof for maf_durable — does NOT touch the production supervisor state.

Writes evidence under %LOCALAPPDATA%/trading-agent-lab/durable-proof/
Leaves legacy ORCHESTRATION_BACKEND=legacy supervisor alone.
"""
import json
import tempfile
import time
from pathlib import Path

from agentops.config import Settings
from agentops.controller import Controller
from agentops.orchestration.maf_durable.activities import TaskActivities
from agentops.orchestration.maf_durable.backend import MafDurableBackend
from agentops.orchestration.maf_durable.checkpoint_store import CheckpointStore
from agentops.orchestration.maf_durable.engine import LocalDurableEngine
from agentops.orchestration.maf_durable.dts_bridge import try_describe_dts
from agentops.selfheal import MaintenanceLoop
from agentops.store import Store
from tests.fakes import FakeCursor, FakeGitHub, FakeTelegram, Clock, update, BASE, HEAD, REPO


def parallel_backlog():
    return [
        {
            "id": "T101",
            "title": "Parallel probe A",
            "description": "Independent",
            "acceptance": ["A"],
            "allowed_prefixes": ["docs/research/"],
            "depends_on": [],
            "phase": 1,
        },
        {
            "id": "T102",
            "title": "Parallel probe B",
            "description": "Independent",
            "acceptance": ["B"],
            "allowed_prefixes": ["docs/research/"],
            "depends_on": [],
            "phase": 1,
        },
    ]


def main() -> int:
    proof_root = Path.home() / "AppData" / "Local" / "trading-agent-lab" / "durable-proof"
    proof_root.mkdir(parents=True, exist_ok=True)
    evidence = {"at": time.time(), "checks": {}}

    dts = try_describe_dts("http://localhost:8080", "default")
    evidence["dts"] = dts

    with tempfile.TemporaryDirectory(dir=str(proof_root)) as tmp:
        cfg = Settings(
            REPO,
            "fake-gh",
            "fake-cursor",
            "1:fake",
            42,
            frozenset({42}),
            state_path=":memory:",
            allow_runs=True,
            spend_limit_confirmed=True,
            protection_confirmed=True,
            agent_runtime="local",
            orchestration_backend="maf_durable",
            durable_checkpoint_dir=tmp,
            telegram_optional=True,
        )
        db = Store(":memory:")
        gh, cu, tg = FakeGitHub(), FakeCursor(), FakeTelegram()
        ctl = Controller(cfg, db, gh, cu, tg, parallel_backlog(), clock=Clock())
        healer = MaintenanceLoop(cfg, db, ctl, Path("."))
        engine = LocalDurableEngine(CheckpointStore(tmp), TaskActivities(ctl))
        backend = MafDurableBackend(cfg, ctl, healer, engine=engine)
        ctl.handle(update("/resume"))

        # --- Parallel proof ---
        for _ in range(8):
            backend.tick()
        t101, t102 = db.task("T101"), db.task("T102")
        parallel_ok = bool(
            t101.get("run_id")
            and t102.get("run_id")
            and t101["run_id"] != t102["run_id"]
            and t101.get("durable_instance_id")
            and t102.get("durable_instance_id")
            and t101["durable_instance_id"] != t102["durable_instance_id"]
        )
        evidence["checks"]["parallel_t101_t102"] = {
            "ok": parallel_ok,
            "T101": {
                "state": t101.get("state"),
                "run_id": t101.get("run_id"),
                "durable_instance_id": t101.get("durable_instance_id"),
            },
            "T102": {
                "state": t102.get("state"),
                "run_id": t102.get("run_id"),
                "durable_instance_id": t102.get("durable_instance_id"),
            },
        }

        # --- Crash resume proof (separate task lifecycle on T101 path already launched) ---
        resume_store = CheckpointStore(Path(tmp) / "resume")
        resume_engine = LocalDurableEngine(resume_store, TaskActivities(ctl))
        # Fresh task for clean step accounting
        db.save(
            {
                "id": "T201",
                "state": "PENDING",
                "attempt": 0,
                "phase": 1,
            }
        )
        # Expand specs via a one-off controller is hard; reuse engine activities on T101 snapshot.
        # Use dedicated instance with completed launch step then restart engine.
        rec = engine.start_task("T101", instance_id="T101:resume-proof")
        # Ensure launch completed
        for _ in range(6):
            rec = engine.advance_instance(rec["instance_id"], max_steps=1)
            if "prepare_and_launch_dev" in rec.get("completed_steps", []):
                break
        launch_key = f"{rec['instance_id']}:prepare_and_launch_dev"
        before = engine.execution_counts.get(launch_key, 0)
        created_before = len(cu.created)
        completed = list(rec["completed_steps"])
        engine2 = LocalDurableEngine(CheckpointStore(tmp), TaskActivities(ctl))
        rec2 = engine2.advance_instance(rec["instance_id"], max_steps=1)
        resume_ok = (
            "prepare_and_launch_dev" in completed
            and engine2.execution_counts.get(launch_key, 0) == 0
            and len(cu.created) == created_before
            and "prepare_and_launch_dev" in rec2.get("completed_steps", [])
        )
        evidence["checks"]["crash_resume_no_relaunch"] = {
            "ok": resume_ok,
            "completed_steps": rec2.get("completed_steps"),
            "launch_executions_before_crash": before,
            "launch_executions_after_restart": engine2.execution_counts.get(launch_key, 0),
            "cursor_creates_unchanged": len(cu.created) == created_before,
        }

        # --- PR reconcile without relaunch ---
        db.save(
            {
                "id": "T001",
                "state": "PENDING",
                "attempt": 1,
                "phase": 1,
                "pr": 7,
                "base_sha": BASE,
                "head_sha": HEAD,
                "run_id": None,
            }
        )
        # Need T001 in specs — use separate controller
        from tests.fakes import backlog

        ctl2 = Controller(cfg, Store(":memory:"), FakeGitHub(), FakeCursor(), FakeTelegram(), backlog(), clock=Clock())
        ctl2.db.set("paused", False)
        ctl2.handle(update("/resume"))
        t = ctl2.db.task("T001")
        t.update(state="PENDING", pr=7, base_sha=BASE, head_sha=HEAD, run_id=None, attempt=1)
        ctl2.db.save(t)
        eng3 = LocalDurableEngine(CheckpointStore(Path(tmp) / "recon"), TaskActivities(ctl2))
        r = eng3.start_task("T001", instance_id="T001:recon")
        r = eng3.advance_instance(r["instance_id"], max_steps=3)
        t = ctl2.db.task("T001")
        reconcile_ok = t.get("state") in {"CI_WAIT", "LAUNCHING_QA", "REVIEWING"} and t.get("pr") == 7
        evidence["checks"]["reconcile_existing_pr"] = {
            "ok": reconcile_ok,
            "state": t.get("state"),
            "pr": t.get("pr"),
        }

    evidence["all_ok"] = all(c.get("ok") for c in evidence["checks"].values())
    out = proof_root / "latest_proof.json"
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
