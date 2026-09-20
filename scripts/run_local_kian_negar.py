"""Run Kian then Negar locally (no Cursor Cloud). Uses real GitHub via gh auth token."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from agentops.config import Settings
from agentops.controller import Controller
from agentops.local_runtime import LocalCursor
from agentops.providers import GitHub
from agentops.store import Store
from tests.fakes import FakeTelegram, update


def gh_token() -> str:
    return subprocess.check_output(["gh", "auth", "token"], text=True, timeout=30).strip()


def main() -> int:
    os.environ["PYTHONIOENCODING"] = "utf-8"
    # Do not hard-reset: preserve local runtime sources. Sync refs only.
    subprocess.check_call(["git", "fetch", "origin", "main"], cwd=ROOT)

    state_dir = Path(os.environ.get("LOCALAPPDATA", str(ROOT / ".state"))) / "trading-agent-lab" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    token = gh_token()
    cfg = Settings(
        repo="mojtabashariatzade/trading-agent-lab",
        github_token=token,
        cursor_key="local",
        telegram_token="1:fake",
        control_chat=42,
        owner_ids=frozenset({42}),
        state_path=str(state_dir / "local_kian_negar.sqlite3"),
        allow_runs=True,
        spend_limit_confirmed=True,
        protection_confirmed=True,
        allow_public_repo=True,
        agent_runtime="local",
        max_daily_launches=8,
    )
    backlog = json.loads((ROOT / "planning" / "tasks.json").read_text(encoding="utf-8"))
    # Smoke only the first phase-1 task for a bounded local run.
    backlog = [backlog[0]]
    db = Store(cfg.state_path)
    gh = GitHub(cfg.repo, cfg.github_token)
    cursor = LocalCursor(ROOT, github_repo=cfg.repo)
    tg = FakeTelegram()
    c = Controller(cfg, db, gh, cursor, tg, backlog)

    print(json.dumps({"event": "resume", "runtime": "local", "task": "T001"}))
    now = int(time.time())
    c.handle(update("/resume", uid=int(now), date=now))
    print(json.dumps({"paused_after_resume": c.db.get("paused")}))
    # Drive until WAITING_APPROVAL or BLOCKED or timeout
    deadline = time.time() + 900
    last = ""
    while time.time() < deadline:
        c.tick()
        c.flush()
        task = db.task("T001")
        state_name = task["state"]
        if state_name != last:
            print(json.dumps({"task": "T001", "state": state_name, "role": task.get("role"), "pr": task.get("pr")}))
            last = state_name
        if state_name in {"WAITING_APPROVAL", "BLOCKED", "DONE"}:
            break
        time.sleep(2)

    task = db.task("T001")
    out = {
        "final_state": task["state"],
        "pr": task.get("pr"),
        "head_sha": task.get("head_sha"),
        "qa": task.get("qa"),
        "runtime": "local",
        "cursor_cloud": False,
        "live_trading": False,
        "notifications": len(tg.sent),
    }
    receipt = state_dir / "kian_negar_local_run.json"
    receipt.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print("RECEIPT=" + str(receipt))
    return 0 if task["state"] in {"WAITING_APPROVAL", "DONE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
