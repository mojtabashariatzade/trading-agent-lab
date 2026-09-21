"""Disk-backed checkpoint store for durable task-lifecycle instances.

Survives process restart. Completed activity names are never re-executed.
This is the self-hosted proof path when the DTS emulator is unavailable.
"""
import json
import os
import tempfile
import time
import uuid
from pathlib import Path


class CheckpointStore:
    """One JSON file per durable instance under a root directory."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, instance_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in instance_id)
        return self.root / f"{safe}.json"

    def _write(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        fd, tmp_name = tempfile.mkstemp(prefix="dur_", suffix=".json", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def get(self, instance_id: str) -> dict | None:
        path = self._path(instance_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, record: dict) -> dict:
        instance_id = record["instance_id"]
        record = dict(record)
        record["updated_at"] = time.time()
        self._write(self._path(instance_id), record)
        return record

    def create(
        self,
        *,
        task_id: str,
        workflow: str = "dev_core_task",
        instance_id: str | None = None,
    ) -> dict:
        iid = instance_id or f"{task_id}:{uuid.uuid4().hex[:12]}"
        record = {
            "instance_id": iid,
            "task_id": task_id,
            "workflow": workflow,
            "status": "Running",
            "completed_steps": [],
            "current_step": None,
            "step_results": {},
            "execution_log": [],
            "created_at": time.time(),
            "updated_at": time.time(),
            "error": None,
            "runtime": "local_checkpoint",
        }
        return self.save(record)

    def list_running(self) -> list[dict]:
        out = []
        for path in self.root.glob("*.json"):
            try:
                rec = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if rec.get("status") == "Running":
                out.append(rec)
        return out

    def list_all(self) -> list[dict]:
        out = []
        for path in self.root.glob("*.json"):
            try:
                out.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return out
