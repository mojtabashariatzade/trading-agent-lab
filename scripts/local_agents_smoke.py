"""Local PC smoke: run research workers + control path without Telegram cloud.

Uses real GitHub token from `gh auth token` when available.
Cursor launches stay mocked unless CURSOR_API_KEY is set in the environment.
Never enables live trading.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentops.config import Settings
from agentops.controller import Controller
from agentops.store import Store
from tests.fakes import Clock, FakeCursor, FakeGitHub, FakeTelegram, backlog


def _gh_token() -> str:
    env = os.environ.get("GITHUB_TOKEN", "").strip()
    if env:
        return env
    try:
        out = subprocess.check_output(["gh", "auth", "token"], text=True, timeout=20).strip()
        return out
    except (OSError, subprocess.CalledProcessError):
        return "local-placeholder-token"


def main() -> int:
    state_dir = Path(os.environ.get("LOCALAPPDATA", str(ROOT / ".local-state"))) / "trading-agent-lab" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "smoke.sqlite3"

    token = _gh_token()
    cursor_key = os.environ.get("CURSOR_API_KEY", "").strip()
    using_real_cursor = bool(cursor_key)

    cfg = Settings(
        repo=os.environ.get("GITHUB_REPOSITORY", "mojtabashariatzade/trading-agent-lab"),
        github_token=token,
        cursor_key=cursor_key or "fake-cursor",
        telegram_token="1:fake",
        control_chat=42,
        owner_ids=frozenset({42}),
        state_path=str(state_path),
        allow_runs=False,
        spend_limit_confirmed=False,
        protection_confirmed=False,
    )

    db = Store(str(state_path))
    clock = Clock()
    # Prefer fake providers for guaranteed local smoke; real Cursor only when key present.
    if using_real_cursor:
        from agentops.providers import Cursor, GitHub, Telegram

        gh, cu, tg = GitHub(cfg.repo, cfg.github_token), Cursor(cfg.cursor_key), FakeTelegram()
        print(json.dumps({"mode": "LOCAL_SMOKE_REAL_CURSOR_FAKE_TELEGRAM", "repo": cfg.repo}))
    else:
        gh, cu, tg = FakeGitHub(), FakeCursor(), FakeTelegram()
        # Align fake repo identity with public repo name for readiness checks.
        gh.private = False  # public repo now
        print(json.dumps({"mode": "LOCAL_SMOKE_FAKE_PROVIDERS", "repo": cfg.repo, "note": "Set CURSOR_API_KEY for real cloud agents"}))

    # Controller ready_to_run requires private+protected; for local smoke use FakeGitHub private=True
    # when using fakes so research path can execute offline.
    if not using_real_cursor:
        gh.private = True
        gh.protected = True

    c = Controller(cfg, db, gh, cu, tg, backlog(), clock=clock)

    # Research smoke: Parsa STRATEGY task -> approved artifact (offline injection)
    r = c.request_research("STRATEGY", "Smoke: document GBPJPY M15 mean-reversion assumptions (UNTESTED)")
    report = {
        "research_id": r["id"],
        "status": "COMPLETE",
        "question": r["question"],
        "citations": [{
            "citation_id": "c1",
            "publisher": "Bank of England",
            "title": "Monetary Policy Report (smoke citation template)",
            "url": "https://www.bankofengland.co.uk/monetary-policy-report",
            "retrieved_at": "2026-09-21T00:00:00Z",
        }],
        "findings": [{
            "claim": "Strategy notes must separate hypotheses from measured results.",
            "evidence_citation_ids": ["c1"],
            "confidence": "MEDIUM",
            "limitations": "Smoke test; no market download performed",
        }],
        "hypotheses": ["Costs reduce net expectancy"],
        "assumptions": ["Causal M15 bars"],
        "parameter_ranges": {"lookback": "10-40"},
        "proposed_tests": ["Chronological walk-forward on development split only"],
        "summary": "Local smoke research artifact; UNTESTED.",
    }
    c.submit_research_report(r["id"], report)

    # Niloofar + Saman blocked examples prove fail-closed
    n = c.request_research("FUNDAMENTAL", "Smoke: BoE calendar access check")
    c.submit_research_report(n["id"], {
        "research_id": n["id"],
        "status": "BLOCKED",
        "question": n["question"],
        "citations": [],
        "findings": [],
        "missing_dependency": "Live ONS/BoE vintage API credentials not configured on this host",
        "summary": "Blocked honestly",
    })
    d = c.request_research("DATA", "Smoke: historical coverage check")
    c.submit_research_report(d["id"], {
        "research_id": d["id"],
        "status": "BLOCKED",
        "question": d["question"],
        "citations": [],
        "findings": [],
        "missing_dependency": "No licensed GBPJPY M15 archive downloaded (owner approval required)",
        "summary": "Blocked honestly",
    })

    c.flush()
    team = c.live_team_report()
    research = c.handle_research_command(["/research"])
    out = {
        "research_tasks": [
            {"id": t["id"], "role": t["owner_role"], "state": t["state"], "blocker": t.get("blocker", "")}
            for t in db.research_tasks()
        ],
        "approved_artifacts": len(c.approved_artifacts_for()),
        "telegram_notifications_buffered": len(tg.sent) if hasattr(tg, "sent") else "n/a",
        "team_report_preview": team.splitlines()[:6],
        "research_report_preview": research.splitlines()[:8],
        "real_cursor": using_real_cursor,
        "live_trading": False,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    receipt = state_dir / "last_smoke.json"
    receipt.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("SMOKE_RECEIPT=" + str(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
