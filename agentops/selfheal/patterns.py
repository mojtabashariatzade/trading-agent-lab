"""Durable failure-pattern registry (non-secret). Caps repair attempts per class."""
import json
import os
import time
from pathlib import Path


MAX_REPAIR_ATTEMPTS = 3
# Transient worker/launch classes cool down and retry; they must not kill the queue overnight.
CLASS_COOLDOWN_SECONDS = 600
TRANSIENT_STRATEGIES = frozenset({"recover_worker", "defer_upstream"})

# Built-in recoverable patterns → strategy id
BUILTIN_PATTERNS = {
    "worker_terminal_error": {
        "match": ["Cursor terminal/unknown status: ERROR", "status: ERROR", "status: EXPIRED"],
        "strategy": "recover_worker",
        "description": "Coding worker ended in ERROR/EXPIRED without delivery",
    },
    "worker_terminal_unknown": {
        "match": ["Cursor terminal/unknown status:"],
        "strategy": "recover_worker",
        "description": "Coding worker ended in unexpected terminal status",
    },
    "retryable_attempt_cap_stall": {
        "match": ["Attempt cap with retryable failure", "retryable_attempt_cap"],
        "strategy": "recover_worker",
        "description": "BLOCKED+retryable but attempt counter exhausted; dependency chain stalled",
    },
    "stuck_no_progress": {
        "match": ["STUCK: no worker progress", "STUCK research:"],
        "strategy": "recover_worker",
        "description": "Watchdog detected no progress within timeout",
    },
    "queue_dependency_hard_block": {
        "match": ["dependency_hard_block"],
        "strategy": "defer_upstream",
        "description": "Dependent is waiting; recover the upstream blocked task only, never a second cap",
    },
}


def default_registry_path() -> str:
    override = os.environ.get("FAILURE_PATTERN_REGISTRY_PATH", "").strip()
    if override:
        return override
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME") or "."
    return str(Path(base) / "trading-agent-lab" / "status" / "failure_patterns.json")


class PatternRegistry:
    def __init__(self, path: str | None = None):
        self.path = path or default_registry_path()
        self.data = self._load()

    def _load(self) -> dict:
        target = Path(self.path)
        if not target.is_file():
            return {"schema": "trading-agent-lab.failure_patterns.v1", "classes": {}, "events": []}
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"schema": "trading-agent-lab.failure_patterns.v1", "classes": {}, "events": []}

    def save(self) -> None:
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(self.data, indent=2, sort_keys=True) + "\n"
        tmp = target.with_suffix(".tmp")
        tmp.write_text(raw, encoding="utf-8")
        os.replace(tmp, target)

    def classify(self, text: str) -> str:
        blob = (text or "").strip()
        if not blob:
            return "unknown_empty"
        for class_id, meta in BUILTIN_PATTERNS.items():
            for needle in meta["match"]:
                if needle.lower() in blob.lower():
                    return class_id
        # Stable unknown fingerprint from first 80 chars
        key = "unknown_" + "".join(ch if ch.isalnum() else "_" for ch in blob[:80]).strip("_").lower()
        return key[:80] or "unknown"

    def strategy_for(self, class_id: str) -> str:
        if class_id in BUILTIN_PATTERNS:
            return BUILTIN_PATTERNS[class_id]["strategy"]
        learned = self.data.get("classes", {}).get(class_id, {})
        return learned.get("strategy", "capture_and_block")

    def repair_count(self, class_id: str) -> int:
        return int(self.data.get("classes", {}).get(class_id, {}).get("repair_attempts", 0))

    def record_attempt(self, class_id: str, *, success: bool, detail: str) -> dict:
        classes = self.data.setdefault("classes", {})
        row = classes.setdefault(
            class_id,
            {
                "repair_attempts": 0,
                "successes": 0,
                "failures": 0,
                "strategy": self.strategy_for(class_id),
                "first_seen_at": time.time(),
                "last_seen_at": time.time(),
                "last_detail": "",
                "self_heal_blocked": False,
            },
        )
        row["repair_attempts"] = int(row.get("repair_attempts", 0)) + 1
        row["last_seen_at"] = time.time()
        row["last_detail"] = detail[:1000]
        if success:
            row["successes"] = int(row.get("successes", 0)) + 1
        else:
            row["failures"] = int(row.get("failures", 0)) + 1
        if row["repair_attempts"] >= MAX_REPAIR_ATTEMPTS and not success:
            row["self_heal_blocked"] = True
        events = self.data.setdefault("events", [])
        events.append(
            {
                "at": time.time(),
                "class_id": class_id,
                "success": success,
                "attempt": row["repair_attempts"],
                "detail": detail[:500],
            }
        )
        self.data["events"] = events[-200:]
        self.save()
        return row

    def is_blocked(self, class_id: str) -> bool:
        row = self.data.get("classes", {}).get(class_id, {})
        return bool(row.get("self_heal_blocked"))

    def release_cooled(self, now: float | None = None) -> list[str]:
        """After cooldown, clear transient class blocks so overnight work can resume."""
        now = time.time() if now is None else float(now)
        released: list[str] = []
        for class_id, row in self.data.get("classes", {}).items():
            strategy = row.get("strategy") or self.strategy_for(class_id)
            if strategy not in TRANSIENT_STRATEGIES and class_id not in BUILTIN_PATTERNS:
                continue
            if not row.get("self_heal_blocked") and int(row.get("repair_attempts", 0)) < MAX_REPAIR_ATTEMPTS:
                continue
            last = float(row.get("last_seen_at") or 0)
            if now - last < CLASS_COOLDOWN_SECONDS:
                continue
            row["self_heal_blocked"] = False
            row["repair_attempts"] = 0
            row["last_released_at"] = now
            released.append(class_id)
        if released:
            self.save()
        return released
