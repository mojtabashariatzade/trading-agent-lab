"""Commit + push self-heal artifacts after CI/QA evidence. No secrets in commits."""
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Only these paths may be auto-pushed by self-heal (never secrets, never broker/live).
ALLOW_PUSH_PREFIXES = (
    "agentops/selfheal/",
    "tests/added/",
    "BOOTSTRAP_RECEIPT.md",
    "scripts/start-supervisor.ps1",
    "scripts/check-supervisor-status.ps1",
    "scripts/ensure-supervisor.ps1",
    "scripts/register-supervisor-autostart.ps1",
)


def _run(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def publish_selfheal_changes(root: Path, *, class_id: str, regression_rel: str) -> str:
    """Stage allowlisted files, commit, push. Returns commit sha or empty on skip/fail."""
    root = Path(root)
    status = _run(root, ["git", "status", "--porcelain"])
    if status.returncode != 0:
        logger.warning("git status failed: %s", status.stderr)
        return ""
    lines = [ln for ln in (status.stdout or "").splitlines() if ln.strip()]
    to_add: list[str] = []
    for ln in lines:
        path = ln[3:].strip().replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if any(path.startswith(p) or path == p.rstrip("/") for p in ALLOW_PUSH_PREFIXES):
            to_add.append(path)
    if regression_rel and regression_rel not in to_add:
        cand = root / regression_rel
        if cand.is_file():
            to_add.append(regression_rel.replace("\\", "/"))
    # Unique preserve order
    seen: set[str] = set()
    files = []
    for p in to_add:
        if p not in seen:
            seen.add(p)
            files.append(p)
    if not files:
        return "n/a-no-git-changes"
    add = _run(root, ["git", "add", "--"] + files)
    if add.returncode != 0:
        logger.warning("git add failed: %s", add.stderr)
        return ""
    msg = f"fix(selfheal): auto-heal {class_id} after CI/QA pass"
    commit = _run(root, ["git", "commit", "-m", msg])
    if commit.returncode != 0:
        # Nothing staged / hook / empty
        if "nothing to commit" in (commit.stdout or "" + commit.stderr or "").lower():
            return "n/a-no-git-changes"
        logger.warning("git commit failed: %s", commit.stderr)
        return ""
    sha = _run(root, ["git", "rev-parse", "HEAD"])
    commit_sha = (sha.stdout or "").strip()
    push = _run(root, ["git", "push", "-u", "origin", "HEAD"])
    if push.returncode != 0:
        logger.warning("git push failed: %s", push.stderr)
        return commit_sha + " (push-failed)"
    return commit_sha
