"""Activities wrapping existing Controller / LocalCursor / policy — no role rewrite."""
from agentops.orchestration.maf_durable.lifecycle import LIFECYCLE_STEPS


class ActivityResult:
    __slots__ = ("outcome", "detail")

    def __init__(self, outcome: str, detail: str = ""):
        # outcome: completed | waiting | failed | skipped
        self.outcome = outcome
        self.detail = detail


class TaskActivities:
    """Bind durable step names to Controller methods (Kian/Negar unchanged)."""

    def __init__(self, controller):
        self.controller = controller

    def run(self, step: str, task_id: str) -> ActivityResult:
        task = self.controller.db.task(task_id)
        if not task:
            return ActivityResult("failed", f"unknown task {task_id}")
        if task.get("state") == "DONE":
            return ActivityResult("completed", "already DONE")
        if task.get("state") == "BLOCKED" and not task.get("retryable"):
            return ActivityResult("failed", str(task.get("feedback") or "BLOCKED"))

        handlers = {
            "reconcile_existing_delivery": self._reconcile,
            "prepare_and_launch_dev": self._prepare_launch_dev,
            "await_dev_worker": self._await_dev,
            "ci_wait": self._ci_wait,
            "launch_qa": self._launch_qa,
            "await_qa_worker": self._await_qa,
            "approval_or_merge": self._approval_or_merge,
        }
        handler = handlers.get(step)
        if not handler:
            return ActivityResult("failed", f"unknown step {step}")
        return handler(task)

    def _reconcile(self, task: dict) -> ActivityResult:
        if task.get("state") in {"CI_WAIT", "LAUNCHING_QA", "REVIEWING", "WAITING_APPROVAL", "MERGING"}:
            return ActivityResult("completed", f"already past reconcile ({task['state']})")
        if task.get("pr") and self.controller.reconcile_existing_delivery(task):
            task = self.controller.db.task(task["id"]) or task
            if task.get("state") == "DONE":
                return ActivityResult("completed", "reconciled merged PR")
            return ActivityResult("completed", f"reconciled to {task.get('state')}")
        return ActivityResult("completed", "no existing delivery")

    def _prepare_launch_dev(self, task: dict) -> ActivityResult:
        state = task.get("state")
        if state in {"DEVELOPING", "CI_WAIT", "LAUNCHING_QA", "REVIEWING", "WAITING_APPROVAL", "MERGING", "DONE"}:
            return ActivityResult("completed", f"skip launch; state={state}")
        if state == "LAUNCHING_DEV" and task.get("run_id"):
            return ActivityResult("completed", "already launched")
        if self.controller.db.get("paused", True):
            return ActivityResult("waiting", "paused")
        if self.controller.clock() < float(task.get("backoff_until") or 0):
            return ActivityResult("waiting", "backoff")

        # Match Controller.tick PENDING → LAUNCHING_DEV path without rewriting roles.
        if state == "PENDING":
            spec = self.controller.specs[task["id"]]
            done = {t["id"] for t in self.controller.db.tasks() if t["state"] == "DONE"}
            if spec["phase"] > self.controller.cfg.max_phase or not set(spec["depends_on"]) <= done:
                return ActivityResult("waiting", "dependencies or phase gate")
            gate = self.controller.research_gate_for_dev(spec)
            if gate:
                return ActivityResult("waiting", gate)
            base = self.controller.ready_to_run()
            if "issue" not in task:
                task["issue"] = self.controller.gh.ensure_issue(spec)
            task.update(
                attempt=int(task.get("attempt") or 0) + 1,
                base_sha=base,
                launch_at=None,
                role="dev",
                state="LAUNCHING_DEV",
                last_error=None,
            )
            self.controller.db.save(task)

        if task.get("state") in {"LAUNCHING_DEV", "PENDING"} or (
            task.get("state") == "BLOCKED" and task.get("retryable")
        ):
            if task.get("state") == "BLOCKED" and task.get("retryable"):
                if int(task.get("attempt") or 0) < self.controller.cfg.max_attempts:
                    self.controller.retry(task)
                    task = self.controller.db.task(task["id"]) or task
            self.controller.launch(task, "dev")
            task = self.controller.db.task(task["id"]) or task
            if task.get("run_id"):
                return ActivityResult("completed", f"launched run_id={task['run_id']}")
            return ActivityResult("waiting", "launch pending run_id")
        return ActivityResult("waiting", f"state={task.get('state')}")

    def _await_dev(self, task: dict) -> ActivityResult:
        if task.get("state") in {"CI_WAIT", "LAUNCHING_QA", "REVIEWING", "WAITING_APPROVAL", "MERGING", "DONE"}:
            return ActivityResult("completed", f"dev finished; state={task['state']}")
        if task.get("state") == "BLOCKED":
            return ActivityResult("failed", str(task.get("feedback") or "BLOCKED"))
        if not task.get("run_id"):
            return ActivityResult("waiting", "no run_id yet")
        # Drive existing advance() for DEVELOPING / LAUNCHING_DEV.
        try:
            self.controller.advance(task)
        except Exception as exc:  # noqa: BLE001 — surface as durable failure detail
            return ActivityResult("waiting", f"advance: {exc}")
        task = self.controller.db.task(task["id"]) or task
        if task.get("state") in {"CI_WAIT", "DONE", "LAUNCHING_QA", "REVIEWING"}:
            return ActivityResult("completed", f"advanced to {task['state']}")
        if task.get("state") == "BLOCKED":
            return ActivityResult("failed", str(task.get("feedback") or "BLOCKED"))
        return ActivityResult("waiting", f"state={task.get('state')}")

    def _ci_wait(self, task: dict) -> ActivityResult:
        if task.get("state") in {"LAUNCHING_QA", "REVIEWING", "WAITING_APPROVAL", "MERGING", "DONE"}:
            return ActivityResult("completed", f"past CI; state={task['state']}")
        if task.get("state") != "CI_WAIT":
            # Dev may still be running — wait.
            if task.get("state") in {"DEVELOPING", "LAUNCHING_DEV"}:
                return ActivityResult("waiting", "dev not finished")
            return ActivityResult("waiting", f"state={task.get('state')}")
        try:
            self.controller.advance(task)
        except Exception as exc:  # noqa: BLE001
            return ActivityResult("waiting", f"ci advance: {exc}")
        task = self.controller.db.task(task["id"]) or task
        if task.get("state") in {"LAUNCHING_QA", "REVIEWING"}:
            return ActivityResult("completed", "CI PASS → QA")
        if task.get("state") == "BLOCKED":
            return ActivityResult("failed", str(task.get("feedback") or "CI blocked"))
        return ActivityResult("waiting", "CI not PASS yet")

    def _launch_qa(self, task: dict) -> ActivityResult:
        if task.get("state") in {"REVIEWING", "WAITING_APPROVAL", "MERGING", "DONE"}:
            return ActivityResult("completed", f"qa already active/done ({task['state']})")
        if task.get("state") == "LAUNCHING_QA" and task.get("run_id"):
            return ActivityResult("completed", "qa launched")
        if task.get("state") == "CI_WAIT":
            return ActivityResult("waiting", "still CI_WAIT")
        if task.get("state") == "LAUNCHING_QA":
            self.controller.launch(task, "qa")
            task = self.controller.db.task(task["id"]) or task
            if task.get("run_id"):
                return ActivityResult("completed", f"qa run_id={task['run_id']}")
            return ActivityResult("waiting", "qa launch pending")
        return ActivityResult("waiting", f"state={task.get('state')}")

    def _await_qa(self, task: dict) -> ActivityResult:
        if task.get("state") in {"WAITING_APPROVAL", "MERGING", "DONE"}:
            return ActivityResult("completed", f"qa finished; state={task['state']}")
        if task.get("state") == "BLOCKED":
            return ActivityResult("failed", str(task.get("feedback") or "QA blocked"))
        if task.get("state") not in {"REVIEWING", "LAUNCHING_QA"}:
            return ActivityResult("waiting", f"state={task.get('state')}")
        try:
            self.controller.advance(task)
        except Exception as exc:  # noqa: BLE001
            return ActivityResult("waiting", f"qa advance: {exc}")
        task = self.controller.db.task(task["id"]) or task
        if task.get("state") in {"WAITING_APPROVAL", "MERGING", "DONE"}:
            return ActivityResult("completed", f"advanced to {task['state']}")
        if task.get("state") == "BLOCKED":
            return ActivityResult("failed", str(task.get("feedback") or "QA blocked"))
        return ActivityResult("waiting", f"state={task.get('state')}")

    def _approval_or_merge(self, task: dict) -> ActivityResult:
        if task.get("state") == "DONE":
            return ActivityResult("completed", "DONE")
        if task.get("state") == "WAITING_APPROVAL":
            if task.get("approval_reasons") or not self.controller.cfg.auto_merge_safe:
                return ActivityResult("waiting", "human approval required")
            try:
                self.controller.advance(task)
            except Exception as exc:  # noqa: BLE001
                return ActivityResult("waiting", f"approval: {exc}")
            task = self.controller.db.task(task["id"]) or task
            if task.get("state") == "DONE":
                return ActivityResult("completed", "auto-merged")
            return ActivityResult("waiting", "still waiting approval")
        if task.get("state") == "MERGING":
            try:
                self.controller.advance(task)
            except Exception as exc:  # noqa: BLE001
                return ActivityResult("waiting", f"merge: {exc}")
            task = self.controller.db.task(task["id"]) or task
            if task.get("state") == "DONE":
                return ActivityResult("completed", "merged")
            return ActivityResult("waiting", "merging")
        return ActivityResult("waiting", f"state={task.get('state')}")


def next_incomplete_step(completed: list[str]) -> str | None:
    done = set(completed)
    for step in LIFECYCLE_STEPS:
        if step not in done:
            return step
    return None
