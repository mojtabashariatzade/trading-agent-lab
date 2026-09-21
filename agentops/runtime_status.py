"""Local runtime status file — truth about whether a supervisor process is alive."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from .research_contracts import ResearchState

LIVE_WORKER = {"DEVELOPING", "REVIEWING"}
WAITING_DEV = {"CI_WAIT", "LAUNCHING_DEV", "LAUNCHING_QA", "WAITING_APPROVAL", "MERGING"}
ACTIVE_DEV = LIVE_WORKER | WAITING_DEV | {"CANCELLING"}
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
        "paid_launch_cap_applies": settings.agent_runtime != "local",
        "worker_engine": "local_cursor" if settings.agent_runtime == "local" else "cursor_cloud",
        "worker_human_required": settings.agent_runtime != "local",
        "max_attempts": settings.max_attempts,
        "max_run_seconds": settings.max_run_seconds,
        "max_phase": settings.max_phase,
        "status_path": settings.resolved_status_path,
        "config_path": settings.resolved_config_path,
        "state_path": settings.state_path,
        "supervisor_command": "python -m agentops.supervisor",
        "process_name": "python",
        "orchestration_backend": getattr(settings, "orchestration_backend", "legacy"),
        "dts_endpoint": getattr(settings, "dts_endpoint", "http://localhost:8080"),
        "dts_task_hub": getattr(settings, "dts_task_hub", "default"),
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
    orchestration_backend: str = "legacy",
    durable_runtime: str | None = None,
) -> dict:
    """Derive RUNNING / IDLE / BLOCKED / STOPPED from durable task state + process liveness."""
    paused = bool(store.get("paused", True))
    tasks = store.tasks()
    research = store.research_tasks()
    backend = (orchestration_backend or store.get("orchestration_backend") or "legacy").strip().lower()
    durable_runtime = durable_runtime or store.get("durable_runtime")

    active = [t for t in tasks if t.get("state") in ACTIVE_DEV]
    active_r = [t for t in research if t.get("state") in ACTIVE_RESEARCH]
    waiting = [t for t in tasks if t.get("state") == "WAITING_APPROVAL"]
    blocked = [t for t in tasks if t.get("state") == "BLOCKED"]
    blocked_r = [t for t in research if t.get("state") == ResearchState.BLOCKED.value]
    pending = [t for t in tasks if t.get("state") == "PENDING"]
    pending_r = [t for t in research if t.get("state") == ResearchState.PENDING.value]
    done = [t for t in tasks if t.get("state") == "DONE"]

    live = [t for t in tasks if t.get("state") in LIVE_WORKER and t.get("run_id")]
    # maf_durable: RUNNING requires a real durable instance id as well as run_id.
    if backend == "maf_durable":
        live = [
            t
            for t in live
            if t.get("durable_instance_id")
            and str(t.get("durable_status") or "Running") == "Running"
        ]
    waiting_dev = [t for t in tasks if t.get("state") in WAITING_DEV]
    waiting_dev.extend(t for t in tasks if t.get("state") in LIVE_WORKER and not t.get("run_id"))
    current = live[0] if live else (active_r[0] if active_r else (waiting_dev[0] if waiting_dev else None))
    current_task = current["id"] if current else None
    live_run = bool(current and current.get("run_id") and current.get("state") in LIVE_WORKER)
    if backend == "maf_durable":
        live_run = bool(
            live_run
            and current
            and current.get("durable_instance_id")
            and str(current.get("durable_status") or "") == "Running"
        )
    current_agent = _agent_label(current) if current and live_run else None
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

    waiting_reason = None
    next_action = None
    next_check_at = None
    if current:
        fp = str(current.get("progress_fingerprint") or "")
        if current.get("state") == "CI_WAIT":
            waiting_reason = f"{current['id']} waiting on CI for PR {current.get('pr')}"
            next_action = "launch Negar QA when CI is PASS"
            next_check_at = _iso(now + 30)
        elif fp.startswith("daily_limit:"):
            waiting_reason = f"Paid/cloud launch budget exhausted ({fp})"
            next_action = "retry after next UTC day or when budget remains"
            next_check_at = _iso(now + 60)
        elif current.get("state") in {"LAUNCHING_DEV", "LAUNCHING_QA"} and not current.get("run_id"):
            waiting_reason = f"{current['id']} launching; no worker run_id yet"
            next_action = "complete create() or recover after launch stall"
            next_check_at = _iso(now + 30)
        elif current.get("state") == "WAITING_APPROVAL":
            waiting_reason = blocker_reason
            next_action = "owner approval or auto-merge if reasons clear"
    if not process_alive:
        status = "STOPPED"
    elif paused and not live and not active_r:
        status = "STOPPED"
    elif live or active_r:
        status = "RUNNING"
    elif waiting_dev and not waiting:
        status = "WAITING"
    elif waiting or blocked or blocked_r:
        status = "BLOCKED"
    else:
        status = "IDLE"
        next_action = next_action or ("start next ready queued task" if pending else "no authorized executable work")

    durable_instance_id = (current or {}).get("durable_instance_id") if current else None
    return {
        "status": status,
        "paused": paused,
        "current_task": current_task,
        "current_agent": current_agent,
        "run_id": (current or {}).get("run_id"),
        "durable_instance_id": durable_instance_id,
        "orchestration_backend": backend,
        "durable_runtime": durable_runtime,
        "last_progress_at": _iso((current or {}).get("last_progress_at")),
        "waiting_reason": waiting_reason,
        "next_action": next_action,
        "next_check_at": next_check_at,
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
            "active": len(live) + len(active_r),
            "waiting": len(waiting_dev),
        },
        "live_trading": False,
        "broker_access": False,
    }


def write_status(path: str, payload: dict) -> None:
    write_json_atomic(path, payload)


def write_runtime_config(path: str, payload: dict) -> None:
    write_json_atomic(path, payload)
