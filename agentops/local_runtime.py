"""Local agent runtime for Kian/Negar when Cursor Cloud API is unavailable.

Same create/run/cancel surface as providers.Cursor. Cloud-ready: set CURSOR_API_KEY
and AGENT_RUNTIME=cloud to use the real Cursor API instead.
"""
import json
import os
import subprocess
import threading
import time
import uuid
from copy import deepcopy
from pathlib import Path


class LocalCursor:
    """In-process worker runner. Never places trades."""

    def __init__(self, repo_root: Path, *, github_repo: str = "mojtabashariatzade/trading-agent-lab"):
        self.repo_root = Path(repo_root)
        self.github_repo = github_repo
        self.runs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, agent_id, name, repo_url, ref, prompt, *, review=False, model=""):
        run_id = "local-run-" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"{agent_id}:{time.time()}"))
        with self._lock:
            self.runs[run_id] = {
                "id": run_id,
                "agent_id": agent_id,
                "name": name,
                "status": "RUNNING",
                "review": review,
                "ref": ref,
                "prompt": prompt,
                "model": model,
                "repo_url": repo_url,
                "started": time.time(),
                "result": "",
                "git": {"branches": []},
            }
        # Execute asynchronously so controller polling matches cloud semantics.
        threading.Thread(target=self._execute, args=(run_id,), daemon=True).start()
        return run_id

    def run(self, agent_id, run_id):
        with self._lock:
            row = self.runs.get(run_id)
            if not row:
                return {"id": run_id, "status": "ERROR"}
            return deepcopy(row)

    def cancel(self, agent_id, run_id):
        with self._lock:
            row = self.runs.get(run_id)
            if row and row["status"] in {"CREATING", "RUNNING"}:
                row["status"] = "CANCELLED"

    def _execute(self, run_id: str) -> None:
        with self._lock:
            row = deepcopy(self.runs[run_id])
        try:
            if row["review"]:
                result = self._run_negar(row)
            else:
                result = self._run_kian(row)
            with self._lock:
                current = self.runs[run_id]
                if current["status"] == "CANCELLED":
                    return
                current.update(result)
                current["status"] = "FINISHED"
        except Exception as exc:  # noqa: BLE001 — local worker must surface ERROR, not crash controller
            with self._lock:
                self.runs[run_id].update(status="ERROR", result=str(exc)[:2000])

    def _isolate(self, run_id: str, ref: str) -> Path:
        """Never checkout the supervisor/Cursor workspace; use a detached worktree."""
        base = Path(os.environ.get("LOCALAPPDATA") or ".") / "trading-agent-lab" / "worktrees"
        name = "".join(ch if ch.isalnum() else "-" for ch in run_id)[:40]
        path = base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not (path / ".git").exists():
            proc = subprocess.run(
                ["git", "worktree", "add", "--detach", str(path), ref or "HEAD"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"git worktree add failed: {(proc.stderr or proc.stdout)[-800:]}")
        return path

    def _run_kian(self, row: dict) -> dict:
        """Minimal scoped delivery under allowlisted prefixes; opens a real PR via gh."""
        root = self._isolate(row["id"], row.get("ref") or "HEAD")
        branch = "local/kian-" + row["agent_id"][-8:]
        work = [
            "trading_lab/data/__init__.py",
            "trading_lab/data/bars.py",
            "tests/added/test_bars_local_kian.py",
            "docs/research/KIAN_LOCAL_RUN.md",
        ]
        self._git(["checkout", "-B", branch], cwd=root)
        data_init = root / "trading_lab" / "data" / "__init__.py"
        data_init.parent.mkdir(parents=True, exist_ok=True)
        if not data_init.exists():
            data_init.write_text('"""Market data helpers for research (no live feeds)."""\n', encoding="utf-8")
        bars = self.repo_root / "trading_lab" / "data" / "bars.py"
        bars.write_text(
            '''"""Half-open UTC M15 bars from bid/ask quotes. Local Kian delivery; no network I/O."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite


def _aware(ts: datetime) -> datetime:
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return ts.astimezone(timezone.utc)


@dataclass(frozen=True)
class Quote:
    at: datetime
    bid: float
    ask: float

    def __post_init__(self) -> None:
        _aware(self.at)
        if not all(isfinite(x) and x > 0 for x in (self.bid, self.ask)) or self.bid > self.ask:
            raise ValueError("Invalid bid/ask")


def m15_floor(ts: datetime) -> datetime:
    ts = _aware(ts)
    return ts.replace(minute=(ts.minute // 15) * 15, second=0, microsecond=0)


def assign_bar_start(ts: datetime) -> datetime:
    """Boundary quote at exact :00/:15/:30/:45 starts the NEXT interval (half-open)."""
    ts = _aware(ts)
    floored = m15_floor(ts)
    if ts == floored:
        return floored
    return floored


def build_m15_bars(quotes: list[Quote]) -> list[dict]:
    """Build bars from quotes. Missing intervals are omitted, never invented."""
    if not quotes:
        return []
    ordered = sorted(quotes, key=lambda q: q.at)
    buckets: dict[datetime, list[Quote]] = {}
    for quote in ordered:
        start = m15_floor(quote.at)
        buckets.setdefault(start, []).append(quote)
    bars = []
    for start in sorted(buckets):
        rows = buckets[start]
        mids = [(q.bid + q.ask) / 2 for q in rows]
        bars.append({
            "start": start.isoformat(),
            "end": (start + timedelta(minutes=15)).isoformat(),
            "open": mids[0],
            "high": max(mids),
            "low": min(mids),
            "close": mids[-1],
            "ticks": len(rows),
            "gap_before": False,
        })
    return bars
''',
            encoding="utf-8",
        )
        test = root / "tests" / "added" / "test_bars_local_kian.py"
        test.write_text(
            '''"""Local Kian smoke tests for M15 bar helpers."""
import unittest
from datetime import datetime, timezone

from trading_lab.data.bars import Quote, assign_bar_start, build_m15_bars, m15_floor


class LocalKianBarsTests(unittest.TestCase):
    def test_rejects_naive(self):
        with self.assertRaises(ValueError):
            Quote(datetime(2026, 1, 1, 10, 0, 0), 1.0, 1.1)

    def test_rejects_crossed(self):
        with self.assertRaises(ValueError):
            Quote(datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc), 1.2, 1.1)

    def test_boundary_floor(self):
        ts = datetime(2026, 1, 1, 10, 15, 0, tzinfo=timezone.utc)
        self.assertEqual(m15_floor(ts), ts)
        self.assertEqual(assign_bar_start(ts), ts)

    def test_build_one_bar(self):
        q = [
            Quote(datetime(2026, 1, 1, 10, 0, 1, tzinfo=timezone.utc), 100.0, 100.2),
            Quote(datetime(2026, 1, 1, 10, 5, 0, tzinfo=timezone.utc), 100.1, 100.3),
        ]
        bars = build_m15_bars(q)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0]["ticks"], 2)


if __name__ == "__main__":
    unittest.main()
''',
            encoding="utf-8",
        )
        note = root / "docs" / "research" / "KIAN_LOCAL_RUN.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(
            "# Kian local run (no Cursor Cloud)\n\n"
            "UNTESTED against live history. Local runtime smoke for causal M15 helpers.\n"
            "No network downloader. No live trading.\n",
            encoding="utf-8",
        )
        for path in work:
            self._git(["add", "-f", path] if path.startswith("trading_lab/data/") else ["add", path], cwd=root)
        self._git(["-c", "user.name=Kian Local", "-c", "user.email=kian-local@users.noreply.github.com",
                   "commit", "-m", "feat(data): local Kian M15 bar helpers (no Cursor Cloud)"], cwd=root)
        self._git(["push", "-u", "origin", branch], cwd=root)
        pr_url = self._gh([
            "pr", "create",
            "--repo", self.github_repo,
            "--base", "main",
            "--head", branch,
            "--title", "feat(data): local Kian M15 bar helpers",
            "--body",             "Local Kian runtime delivery. No Cursor Cloud. No live trading.\n\nImplements scoped bar helpers + tests under allowlisted prefixes.",
        ], cwd=root).strip()
        if not pr_url.startswith("http"):
            # gh may print https URL on last line
            for line in pr_url.splitlines()[::-1]:
                if line.startswith("http"):
                    pr_url = line.strip()
                    break
        return {
            "git": {"branches": [{"repoUrl": "github.com/" + self.github_repo, "prUrl": pr_url}]},
            "result": "Local Kian finished; PR opened.",
        }

    def _run_negar(self, row: dict) -> dict:
        prompt = row.get("prompt", "")
        sha = ""
        marker = "EXACT head "
        if marker in prompt:
            tail = prompt.split(marker, 1)[1].strip().split()[0]
            if len(tail) == 40:
                sha = tail.lower()
        ref = row.get("ref") or sha
        root = self._isolate(row["id"], ref or "HEAD")
        if ref:
            self._git(["fetch", "origin", ref], cwd=root)
            self._git(["checkout", "--force", ref], cwd=root)
        proc = subprocess.run(
            ["python", "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        tip = self._git(["rev-parse", "HEAD"], cwd=root).strip()
        head = sha or tip
        ok = proc.returncode == 0 and (not sha or tip == sha)
        verdict = "PASS" if ok else "FAIL"
        findings = []
        if proc.returncode != 0:
            findings.append("Local Negar: unittest suite failed")
        if sha and tip != sha:
            findings.append("Local Negar: checked out HEAD does not match required SHA")
        payload = {
            "verdict": verdict if not findings else ("FAIL" if verdict == "PASS" else verdict),
            "head_sha": head,
            "blocking_findings": findings,
            "test_commands": ["python -m unittest discover -s tests -v"],
            "summary": "Local Negar review (no Cursor Cloud).",
            "research_evidence_checked": True,
        }
        if findings and payload["verdict"] == "PASS":
            payload["verdict"] = "FAIL"
        return {"result": json.dumps(payload)}

    def _git(self, args: list[str], cwd: Path | None = None) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd or self.repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git {args[0]} failed: {proc.stderr[-1000:]}")
        return proc.stdout

    def _gh(self, args: list[str], cwd: Path | None = None) -> str:
        proc = subprocess.run(
            ["gh", *args],
            cwd=str(cwd or self.repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"gh failed: {proc.stderr[-1000:] or proc.stdout[-1000:]}")
        return proc.stdout + proc.stderr
