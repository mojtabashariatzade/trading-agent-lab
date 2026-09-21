"""Local durable engine — checkpointed activities, crash-safe resume, parallel instances.

Mirrors Durable Task Extension semantics for Development Core on a self-hosted PC
when the DTS emulator is not running. Completed steps are never re-executed.
"""
import time

from agentops.orchestration.maf_durable.activities import TaskActivities, next_incomplete_step
from agentops.orchestration.maf_durable.checkpoint_store import CheckpointStore
from agentops.orchestration.maf_durable.lifecycle import LIFECYCLE_STEPS


class LocalDurableEngine:
    """Runs one poll of activity progress for durable instances."""

    def __init__(self, store: CheckpointStore, activities: TaskActivities):
        self.store = store
        self.activities = activities
        # Counts how many times each step body executed (for resume proofs).
        self.execution_counts: dict[str, int] = {}

    def start_task(self, task_id: str, *, instance_id: str | None = None, force_new: bool = False) -> dict:
        if not force_new:
            existing = [
                r
                for r in self.store.list_all()
                if r.get("task_id") == task_id and r.get("status") in {"Running", "Completed"}
            ]
            running = [r for r in existing if r.get("status") == "Running"]
            if running:
                return running[0]
            completed = [r for r in existing if r.get("status") == "Completed"]
            if completed and not instance_id:
                # Reuse completed only if caller wants a fresh attempt via new instance_id.
                return completed[-1]
        return self.store.create(task_id=task_id, instance_id=instance_id)

    def get(self, instance_id: str) -> dict | None:
        return self.store.get(instance_id)

    def advance_instance(self, instance_id: str, *, max_steps: int = 1) -> dict:
        """Execute up to max_steps incomplete activities. Skips completed_steps forever."""
        record = self.store.get(instance_id)
        if not record:
            raise KeyError(instance_id)
        if record.get("status") in {"Completed", "Failed"}:
            return record

        steps_run = 0
        while steps_run < max_steps:
            step = next_incomplete_step(list(record.get("completed_steps") or []))
            if step is None:
                record["status"] = "Completed"
                record["current_step"] = None
                return self.store.save(record)

            record["current_step"] = step
            key = f"{instance_id}:{step}"
            self.execution_counts[key] = self.execution_counts.get(key, 0) + 1
            result = self.activities.run(step, record["task_id"])
            record.setdefault("execution_log", []).append(
                {
                    "step": step,
                    "outcome": result.outcome,
                    "detail": result.detail[:500],
                    "at": time.time(),
                }
            )
            record.setdefault("step_results", {})[step] = {
                "outcome": result.outcome,
                "detail": result.detail[:500],
            }

            if result.outcome == "completed" or result.outcome == "skipped":
                completed = list(record.get("completed_steps") or [])
                if step not in completed:
                    completed.append(step)
                record["completed_steps"] = completed
                steps_run += 1
                # Continue loop only if max_steps allows more completions this tick.
                continue

            if result.outcome == "failed":
                record["status"] = "Failed"
                record["error"] = result.detail[:1000]
                return self.store.save(record)

            # waiting — persist and stop this tick without marking step complete
            record["status"] = "Running"
            return self.store.save(record)

        return self.store.save(record)

    def advance_all_running(self, *, max_steps_each: int = 1) -> list[dict]:
        out = []
        for rec in self.store.list_running():
            out.append(self.advance_instance(rec["instance_id"], max_steps=max_steps_each))
        return out

    def running_for_task(self, task_id: str) -> dict | None:
        for rec in self.store.list_running():
            if rec.get("task_id") == task_id:
                return rec
        return None

    def step_execution_count(self, instance_id: str, step: str) -> int:
        return int(self.execution_counts.get(f"{instance_id}:{step}", 0))

    @staticmethod
    def all_steps() -> tuple[str, ...]:
        return LIFECYCLE_STEPS
