"""Dedicated single-process deployment; never run from a candidate PR checkout."""
import json
import logging
from pathlib import Path
import sys
import time

from .config import Settings
from .controller import Controller, STATUS, DETAIL
from .local_runtime import LocalCursor
from .providers import Cursor, GitHub, Telegram, ProviderError
from .store import Store


def _select_cursor(cfg: Settings, root: Path):
    """Cloud-ready selector: local runtime when requested or Cursor key missing."""
    runtime = cfg.agent_runtime
    if runtime == "local" or not cfg.cursor_key or cfg.cursor_key in {"", "local", "fake-cursor"}:
        return LocalCursor(root, github_repo=cfg.repo)
    return Cursor(cfg.cursor_key)


def _acquire_lock(lock_path: str):
    """Exclusive lock that works on Windows and Unix."""
    handle = open(lock_path, "a", encoding="utf-8")
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            handle.close()
            raise RuntimeError("Another controller instance already holds the state lock") from exc
    else:
        import fcntl

        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return handle


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = Settings.from_env()
    Path(cfg.state_path).parent.mkdir(parents=True, exist_ok=True)
    lock = _acquire_lock(cfg.state_path + ".lock")
    db = Store(cfg.state_path)
    root = Path(__file__).resolve().parents[1]
    gh = GitHub(cfg.repo, cfg.github_token)
    cursor = _select_cursor(cfg, root)
    tg = Telegram(cfg.telegram_token)
    tg.preflight()
    backlog = json.loads((root / "planning/tasks.json").read_text(encoding="utf-8"))
    controller = Controller(cfg, db, gh, cursor, tg, backlog)
    db.notify(
        "boot:" + str(int(time.time())),
        STATUS + ": controller started; /status for evidence. No live trading adapter exists.",
    )
    failures = 0
    while True:
        try:
            for update in tg.updates(db.get("telegram_offset", 0)):
                controller.handle(update)
            controller.tick()
            controller.flush()
            db.set("heartbeat_at", time.time())
            failures = 0
            time.sleep(cfg.poll_seconds)
        except ProviderError as exc:
            failures += 1
            logging.warning("Provider unavailable: %s", exc)
            if exc.provider == "Telegram":
                db.set("paused", True)
                try:
                    controller.tick()
                except (RuntimeError, ValueError, KeyError):
                    pass
            time.sleep(min(300, 10 * 2 ** min(failures, 5)))
        except (RuntimeError, ValueError, KeyError) as exc:
            db.set("paused", True)
            logging.error("Controller paused: %s", type(exc).__name__)
            db.notify(
                "controller-block:" + str(int(time.time() // 3600)),
                STATUS + ": CONTROLLER PAUSED\n" + DETAIL
                + ": inspect deployment and configuration; no task completion assumed.",
            )
            time.sleep(30)


if __name__ == "__main__":
    main()
