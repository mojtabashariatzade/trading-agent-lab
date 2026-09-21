"""Persistent local supervisor — independent of the Cursor chat UI.

Process name: python (python.exe on Windows)
Command: python -m agentops.supervisor
Status file: %LOCALAPPDATA%\\trading-agent-lab\\status\\runtime_status.json
Config file: %LOCALAPPDATA%\\trading-agent-lab\\status\\runtime_config.json
  (non-sensitive flags only — never read secrets.env for monitoring)

Does not enable live trading or broker access.
"""
import json
import logging
import os
from pathlib import Path
import sys
import time
import traceback

from .config import Settings
from .controller import Controller, STATUS, DETAIL
from .local_runtime import LocalCursor
from .orchestration.factory import create_backend
from .providers import Cursor, GitHub, NullTelegram, ProviderError, Telegram
from .runtime_status import build_runtime_config, build_status, write_runtime_config, write_status
from .selfheal import MaintenanceLoop
from .store import Store


def _select_cursor(cfg: Settings, root: Path):
    runtime = cfg.agent_runtime
    if runtime == "local" or not cfg.cursor_key or cfg.cursor_key in {"", "local", "fake-cursor"}:
        return LocalCursor(root, github_repo=cfg.repo)
    return Cursor(cfg.cursor_key)


def _select_telegram(cfg: Settings):
    if cfg.telegram_optional and (
        not cfg.telegram_token
        or cfg.telegram_token.startswith("0:")
        or cfg.telegram_token.endswith("localoptionaldisabled")
    ):
        return NullTelegram()
    return Telegram(cfg.telegram_token)


def _acquire_lock(lock_path: str):
    handle = open(lock_path, "a", encoding="utf-8")
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            handle.close()
            raise RuntimeError("Another supervisor instance already holds the state lock") from exc
    else:
        import fcntl

        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return handle


def _publish_config(cfg: Settings) -> dict:
    payload = build_runtime_config(cfg)
    write_runtime_config(cfg.resolved_config_path, payload)
    return payload


def _publish_status(cfg: Settings, db: Store, *, pid: int) -> dict:
    payload = build_status(
        db,
        pid=pid,
        process_alive=True,
        auto_merge_safe=cfg.auto_merge_safe,
        now=time.time(),
        stuck_timeout_seconds=cfg.stuck_timeout_seconds,
        max_stuck_retries=cfg.max_stuck_retries,
        supervisor_restart_enabled=cfg.supervisor_restart_enabled,
        orchestration_backend=cfg.orchestration_backend,
        durable_runtime=db.get("durable_runtime"),
    )
    # Mirror non-sensitive monitoring pointers into status (still no secrets).
    payload["config_path"] = cfg.resolved_config_path
    payload["status_path"] = cfg.resolved_status_path
    write_status(cfg.resolved_status_path, payload)
    db.set("heartbeat_at", payload["last_heartbeat_unix"])
    db.set("runtime_status", payload)
    return payload


def _status_telegram_line(payload: dict) -> str:
    return (
        f"{STATUS}: supervisor {payload['status']}\n"
        f"{DETAIL}: task={payload.get('current_task') or '-'} agent={payload.get('current_agent') or '-'} "
        f"next={payload.get('next_queued_task') or '-'} blocker={payload.get('blocker_reason') or '-'}"
    )


def main() -> int:
    log_dir = os.environ.get("SUPERVISOR_LOG_DIR", "").strip()
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(Path(log_dir) / "supervisor.err.log", encoding="utf-8")
        handlers = [fh]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )
    cfg = Settings.from_env()
    Path(cfg.state_path).parent.mkdir(parents=True, exist_ok=True)
    lock = _acquire_lock(cfg.state_path + ".lock")
    db = Store(cfg.state_path)
    root = Path(__file__).resolve().parents[1]
    gh = GitHub(cfg.repo, cfg.github_token)
    cursor = _select_cursor(cfg, root)
    tg = _select_telegram(cfg)
    tg.preflight()
    backlog = json.loads((root / "planning/tasks.json").read_text(encoding="utf-8"))
    controller = Controller(cfg, db, gh, cursor, tg, backlog)
    healer = MaintenanceLoop(cfg, db, controller, root)
    backend = create_backend(cfg, controller, healer)
    pid = os.getpid()

    # Autonomous boot: unpause when authorizations are already confirmed.
    if cfg.autonomous_default and cfg.allow_runs and cfg.spend_limit_confirmed and cfg.protection_confirmed:
        try:
            controller.ready_to_run()
            db.set("paused", False)
        except RuntimeError as exc:
            logging.warning("Autonomous start deferred: %s", exc)
            db.set("paused", True)

    db.notify(
        "boot:" + str(int(time.time())),
        STATUS + ": supervisor started (autonomous-by-default). No live trading. Status: "
        + cfg.resolved_status_path + " Config: " + cfg.resolved_config_path,
    )
    _publish_config(cfg)
    _publish_status(cfg, db, pid=pid)
    logging.info(
        "Supervisor alive pid=%s backend=%s status_file=%s config_file=%s auto_merge_safe=%s",
        pid,
        backend.name,
        cfg.resolved_status_path,
        cfg.resolved_config_path,
        cfg.auto_merge_safe,
    )

    failures = 0
    last_heartbeat = 0.0
    try:
        while True:
            try:
                for update in tg.updates(db.get("telegram_offset", 0)):
                    backend.handle(update)
                backend.tick()
                heal_reports = getattr(backend, "last_heal_reports", None) or []
                backend.flush()
                now = time.time()
                payload = _publish_status(cfg, db, pid=pid)
                if heal_reports:
                    payload["selfheal"] = {
                        "last_status": heal_reports[-1].get("status"),
                        "last_class": heal_reports[-1].get("failure_class"),
                        "last_report": heal_reports[-1].get("report_path"),
                        "ci_result": heal_reports[-1].get("ci_result"),
                        "qa_result": heal_reports[-1].get("qa_result"),
                        "resumed_task": heal_reports[-1].get("resumed_task"),
                    }
                    write_status(cfg.resolved_status_path, payload)
                if db.get("supervisor_reload_requested"):
                    logging.info("Supervisor reload requested by self-heal; exiting cleanly for OS restart")
                    db.set("supervisor_reload_requested", False)
                    _publish_status(cfg, db, pid=pid)
                    return 0
                if now - last_heartbeat >= cfg.heartbeat_seconds:
                    # Periodic status to Telegram when connected; always on disk above.
                    db.notify(
                        f"heartbeat:{int(now // cfg.heartbeat_seconds)}",
                        _status_telegram_line(payload),
                    )
                    backend.flush()
                    last_heartbeat = now
                failures = 0
                time.sleep(cfg.poll_seconds)
            except ProviderError as exc:
                failures += 1
                logging.warning("Provider unavailable: %s", exc)
                _publish_status(cfg, db, pid=pid)
                if exc.provider == "Telegram" and not cfg.telegram_optional:
                    db.set("paused", True)
                    try:
                        backend.tick()
                    except (RuntimeError, ValueError, KeyError):
                        pass
                time.sleep(min(300, 10 * 2 ** min(failures, 5)))
            except (RuntimeError, ValueError, KeyError) as exc:
                db.set("paused", True)
                logging.error("Supervisor blocked: %s", type(exc).__name__)
                _publish_status(cfg, db, pid=pid)
                db.notify(
                    "controller-block:" + str(int(time.time() // 3600)),
                    STATUS + ": SUPERVISOR BLOCKED\n" + DETAIL
                    + ": inspect deployment and configuration; no task completion assumed. "
                    + str(exc)[:500],
                )
                try:
                    backend.flush()
                except ProviderError:
                    pass
                time.sleep(30)
            except Exception as exc:  # noqa: BLE001 — recover; never silently die
                failures += 1
                logging.error("Supervisor recovered from unexpected error: %s\n%s", exc, traceback.format_exc())
                _publish_status(cfg, db, pid=pid)
                time.sleep(min(300, 10 * 2 ** min(failures, 5)))
    finally:
        # Mark stopped only if this process still holds the lock path semantics.
        try:
            payload = build_status(
                db,
                pid=pid,
                process_alive=False,
                auto_merge_safe=cfg.auto_merge_safe,
                now=time.time(),
                stuck_timeout_seconds=cfg.stuck_timeout_seconds,
                max_stuck_retries=cfg.max_stuck_retries,
                supervisor_restart_enabled=cfg.supervisor_restart_enabled,
                orchestration_backend=cfg.orchestration_backend,
                durable_runtime=db.get("durable_runtime"),
            )
            payload["status"] = "STOPPED"
            write_status(cfg.resolved_status_path, payload)
        except Exception:  # noqa: BLE001
            logging.exception("Failed to write STOPPED status")
        try:
            lock.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
