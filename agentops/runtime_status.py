"""Local runtime status file — truth about whether a supervisor process is alive."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from .research_contracts import ResearchState

ACTIVE_DEV = {
    "DEVELOPING",
    "REVIEWING",
    "LAUNCHING_DEV",
    "LAUNCHING_QA",
    "CI_WAIT",
    "MERGING",
    "CANCELLING",
}
ACTIVE_RESEARCH = {
    ResearchState.LAUNCHING.value,
    ResearchState.RUNNING.value,
    ResearchState.UNDER_REVIEW.value,
}
ROLE_LABEL = {"dev": "Kian", "qa": "Negar", "core": "Arman", "support": "Raha"}


def _status_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME") or "."
    return Path(base) / "trading-agent-lab" / "status"


def default_status_path() -> str:
    override = os.environ.get("RUNTIME_STATUS_PATH", "").strip()
    if override:
        return override
    return str(_status_dir() / "runtime_status.json")


def default_config_path() -> str:
    """Non-sensitive runtime flags only — never tokens or secrets.env contents."""
    override = os.environ.get("RUNTIME_CONFIG_PATH", "").strip()
    if override:
        return override
    return str(_status_dir() / "runtime_config.json")


def build_runtime_config(settings) -> dict:
    """Public, non-sensitive flags safe to read for monitoring (no secrets)."""
    return {
        "schema": "trading-agent-lab.runtime_config.v1",
        "repo": settings.repo,
        "branch": settings.branch,
        "agent_runtime": settings.agent_runtime,
        "auto_merge_safe": settings.auto_merge_safe,
        "autonomous_default": settings.autonomous_default,
        "allow_runs": settings.allow_runs,
        "spend_limit_confirmed": settings.spend_limit_confirmed,
        "protection_confirmed": settings.protection_confirmed,
        "allow_public_repo": settings.allow_public_repo,
        "telegram_optional": settings.telegram_optional,
        "telegram_connected": not (
            settings.telegram_optional
            and (
                not settings.telegram_token
                or settings.telegram_token.startswith("0:")
                or settings.telegram_token.endswith("localoptionaldisabled")
            )
        ),
        "poll_seconds": settings.poll_seconds,
        "heartbeat_seconds": settings.heartbeat_seconds,
        "stuck_timeout_seconds": settings.stuck_timeout_seconds,
        "max_stuck_retries": settings.max_stuck_retries,
        "stuck_backoff_seconds": settings.stuck_backoff_seconds,
        "supervisor_restart_enabled": settings.supervisor_restart_enabled,
        "watchdog_active": True,
        "selfheal_enabled": True,
        "max_selfheal_repairs": 3,
        "max_daily_launches": settings.max_daily_launches,
        "max_attempts": settings.max_attempts,
        "max_run_seconds": settings.max_run_seconds,
        "max_phase": settings.max_phase,
        "status_path": settings.resolved_status_path,
        "config_path": settings.resolved_config_path,
        "state_path": settings.state_path,
        "supervisor_command": "python -m agentops.supervisor",
        "process_name": "python",
        "live_trading": False,
        "broker_access": False,
        "monitoring_policy": {
            "read_secrets_env": False,
            "allowed_paths": [
                "status/runtime_status.json",
                "status/runtime_config.json",
                "logs/supervisor.out.log",
                "logs/supervisor.err.log",
                "supervisor.pid",
            ],
            "read_only_commands_ok": True,
        },
    }


def write_json_atomic(path: str, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix="runtime_", suffix=".json", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _iso(ts: float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _agent_label(task: dict) -> str | None:
    role = task.get("role") or task.get("owner_role")
    if not role:
        return None
    return ROLE_LABEL.get(role, str(role))


def build_status(
    store,
    *,
    pid: int,
    process_alive: bool,
    auto_merge_safe: bool,
    now: float,
    stuck_timeout_seconds: int = 300,
    max_stuck_retries: int = 3,
    supervisor_restart_enabled: bool = False,
) -> dict:
    """Derive RUNNING / IDLE / BLOCKED / STOPPED from durable task state + process liveness."""
    paused = bool(store.get("paused", True))
    tasks = store.tasks()
    research = store.research_tasks()

    active = [t for t in tasks if t.get("state") in ACTIVE_DEV]
    active_r = [t for t in research if t.get("state") in ACTIVE_RESEARCH]
    waiting = [t for t in tasks if t.get("state") == "WAITING_APPROVAL"]
    blocked = [t for t in tasks if t.get("state") == "BLOCKED"]
    blocked_r = [t for t in research if t.get("state") == ResearchState.BLOCKED.value]
    pending = [t for t in tasks if t.get("state") == "PENDING"]
    pending_r = [t for t in research if t.get("state") == ResearchState.PENDING.value]
    done = [t for t in tasks if t.get("state") == "DONE"]

    current = active[0] if active else (active_r[0] if active_r else None)
    current_task = current["id"] if current else None
    current_agent = _agent_label(current) if current else None
    if not process_alive:
        current_agent = None

    retry_count = int(current.get("stuck_retries", 0)) if current else 0
    last_error = None
    if current and current.get("last_error"):
        last_error = str(current["last_error"])[:500]
    elif blocked:
        last_error = str(blocked[0].get("feedback") or blocked[0].get("last_error") or "")[:500] or None

    blocker_reason = None
    if waiting:
        reasons = waiting[0].get("approval_reasons") or []
        blocker_reason = (
            "Human approval required: " + "; ".join(reasons[:5])
            if reasons
            else f"Waiting owner approval for {waiting[0]['id']}"
        )
    elif blocked:
        blocker_reason = str(blocked[0].get("feedback") or blocked[0].get("blocker") or "blocked")[:500]
    elif blocked_r:
        blocker_reason = str(blocked_r[0].get("blocker") or "research blocked")[:500]

    next_queued = None
    if pending_r:
        next_queued = pending_r[0]["id"]
    elif pending:
        next_queued = pending[0]["id"]

    last_completed = done[-1]["id"] if done else None

    if not process_alive:
        status = "STOPPED"
    elif paused and not active and not active_r:
        status = "STOPPED"
    elif active or active_r:
        status = "RUNNING"
    elif waiting or blocked or blocked_r:
        status = "BLOCKED"
    else:
        status = "IDLE"

    return {
        "status": status,
        "paused": paused,
        "current_task": current_task,
        "current_agent": current_agent,
        "last_heartbeat_at": _iso(now),
        "last_heartbeat_unix": now,
        "last_completed_task": last_completed,
        "blocker_reason": blocker_reason,
        "next_queued_task": next_queued,
        "pid": pid,
        "process_alive": process_alive,
        "auto_merge_safe": auto_merge_safe,
        "retry_count": retry_count,
        "last_error": last_error,
        "watchdog": {
            "active": True,
            "timeout_seconds": stuck_timeout_seconds,
            "max_retries": max_stuck_retries,
        },
        "supervisor_restart_enabled": supervisor_restart_enabled,
        "counts": {
            "done": len(done),
            "pending": len(pending),
            "blocked": len(blocked) + len(blocked_r),
            "waiting_approval": len(waiting),
            "active": len(active) + len(active_r),
        },
        "live_trading": False,
        "broker_access": False,
    }


def write_status(path: str, payload: dict) -> None:
    write_json_atomic(path, payload)


def write_runtime_config(path: str, payload: dict) -> None:
    write_json_atomic(path, payload)
