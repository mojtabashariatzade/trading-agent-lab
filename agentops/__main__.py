"""Dedicated single-process deployment; never run from a candidate PR checkout."""
import fcntl
import json
import logging
from pathlib import Path
import time

from .config import Settings
from .controller import Controller, STATUS, DETAIL
from .providers import Cursor, GitHub, Telegram, ProviderError
from .store import Store


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = Settings.from_env()
    Path(cfg.state_path).parent.mkdir(parents=True, exist_ok=True)
    lock = open(cfg.state_path + ".lock", "a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    db = Store(cfg.state_path)
    gh, cursor, tg = GitHub(cfg.repo, cfg.github_token), Cursor(cfg.cursor_key), Telegram(cfg.telegram_token)
    tg.preflight()
    root = Path(__file__).resolve().parents[1]
    backlog = json.loads((root / "planning/tasks.json").read_text())
    controller = Controller(cfg, db, gh, cursor, tg, backlog)
    db.notify("boot:" + str(int(time.time())), STATUS + ": controller started; /status for evidence. No live trading adapter exists.")
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
            # Redacted error strings only. Do not log raw HTTP exceptions or payloads.
            failures += 1
            logging.warning("Provider unavailable: %s", exc)
            if exc.provider == "Telegram":
                db.set("paused", True)
                # Still monitor/cancel an already-running job; do not hide its state.
                try:
                    controller.tick()
                except (RuntimeError, ValueError, KeyError):
                    pass
            time.sleep(min(300, 10 * 2 ** min(failures, 5)))
        except (RuntimeError, ValueError, KeyError) as exc:
            db.set("paused", True)
            logging.error("Controller paused: %s", type(exc).__name__)
            db.notify("controller-block:" + str(int(time.time() // 3600)), STATUS + ": CONTROLLER PAUSED\n" + DETAIL + ": inspect deployment and configuration; no task completion assumed.")
            time.sleep(30)


if __name__ == "__main__":
    main()
