"""Pure safety checks: no LLM can override these by returning a verdict."""
import json
from pathlib import PurePosixPath
import re


PROTECTED = (
    "agentops/",
    ".github/",
    ".cursor/",
    "agents/",
    "planning/",
    "tests/test_",
    "trading_lab/contracts.py",
    "AGENTS.md",
    "Dockerfile",
    "compose.yaml",
    "pyproject.toml",
    "requirements",
    ".env",
    "docs/DEPLOY",
    "docs/SECURITY",
)

# Safe autonomy paths may auto-merge after CI+Negar PASS (still never secrets/live/broker).
# Keep policy.py, planning/, .github/, AGENTS.md, and high-risk markers under human approval.
MAINTENANCE_AUTO_PREFIXES = (
    "agentops/selfheal/",
    "agentops/runtime_status.py",
    "agentops/local_runtime.py",
    "agentops/controller.py",
    "agentops/supervisor.py",
    "agentops/config.py",
    "agentops/__main__.py",
    "agentops/providers.py",
    "agentops/store.py",
    "tests/added/",
    "scripts/start-supervisor.ps1",
    "scripts/ensure-supervisor.ps1",
    "scripts/check-supervisor-status.ps1",
    "scripts/register-supervisor-autostart.ps1",
    "scripts/run-local-host.ps1",
    "docs/TEAM.md",
    "BOOTSTRAP_RECEIPT.md",
)

HIGH_RISK_MARKERS = (
    "live_trading",
    "live-trading",
    "broker",
    "credential",
    "secrets",
    "branch_protection",
    "branch-protection",
)


def validate_changes(files, allowed_prefixes):
    """Hard reject unsafe/out-of-scope diffs. High-risk in-scope diffs are allowed through QA."""
    if not files:
        return False, "empty diff"
    if len(files) > 150:
        return False, "oversized diff"
    for item in files:
        name = item["filename"]
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            return False, "unsafe path"
        if not any(name.startswith(prefix) for prefix in allowed_prefixes):
            return False, f"outside task scope: {name}"
        if any(p.lower() in {".env", ".ssh", "secrets", "credentials"} for p in path.parts):
            return False, "secret-like path"
    return True, "allowed"


def approval_required_reasons(files) -> list[str]:
    """Human approval gates for otherwise valid diffs (autonomous-by-default elsewhere)."""
    reasons: list[str] = []
    for item in files:
        name = item["filename"]
        path = PurePosixPath(name)
        status = item.get("status")
        if status not in {"added", "modified"}:
            reasons.append(f"destructive change ({status}): {name}")
        if name.startswith(PROTECTED):
            if any(name.startswith(prefix) for prefix in MAINTENANCE_AUTO_PREFIXES):
                continue
            reasons.append(f"protected/high-risk path: {name}")
        lowered = name.lower()
        for marker in HIGH_RISK_MARKERS:
            if marker in lowered:
                reasons.append(f"high-risk marker '{marker}': {name}")
                break
        if any(p.lower() in {"broker", "live"} for p in path.parts):
            reasons.append(f"broker/live path segment: {name}")
    seen: set[str] = set()
    ordered: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            ordered.append(reason)
    return ordered


def pr_number(url, repo):
    match = re.fullmatch(r"https://github\.com/" + re.escape(repo) + r"/pull/([1-9][0-9]*)/?", url)
    if not match:
        raise ValueError("Unexpected repository or pull request URL")
    return int(match[1])


def valid_pr(pr, repo, branch):
    return (pr.get("state") == "open" and not pr.get("draft", False)
            and pr.get("base", {}).get("ref") == branch
            and (pr.get("head", {}).get("repo") or {}).get("full_name") == repo
            and (pr.get("base", {}).get("repo") or {}).get("full_name") == repo
            and bool(re.fullmatch(r"[0-9a-f]{40}", pr.get("head", {}).get("sha", ""))))


def parse_review(text, sha):
    """Structured model output is advisory; CI and file policy are checked independently."""
    text = text.strip()
    if text.startswith("```json\n") and text.endswith("```"):
        text = text[8:-3].strip()
    elif text.startswith("```\n") and text.endswith("```"):
        text = text[4:-3].strip()
    if len(text) > 24000:
        raise ValueError("Review too large")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Review must be an object")
    if data.get("verdict") not in {"PASS", "FAIL", "BLOCKED"} or data.get("head_sha") != sha:
        raise ValueError("Invalid review verdict or SHA")
    findings = data.get("blocking_findings")
    commands = data.get("test_commands")
    if not isinstance(findings, list) or not all(isinstance(x, str) for x in findings):
        raise ValueError("Review findings must be strings")
    if not isinstance(commands, list) or not commands or not all(isinstance(x, str) and x.strip() for x in commands):
        raise ValueError("Review must record test commands")
    if data["verdict"] == "PASS" and findings:
        raise ValueError("PASS cannot contain blockers")
    return data


def authenticate_update(update, control_chat, owner_ids, now):
    """Channel posts, anonymous admins, bots, wrong chats and stale messages cannot command."""
    callback = update.get("callback_query")
    message = callback.get("message", {}) if callback else update.get("message", {})
    author = callback.get("from", {}) if callback else message.get("from", {})
    if message.get("chat", {}).get("id") != control_chat:
        return None
    if author.get("id") not in owner_ids or author.get("is_bot", False) or message.get("sender_chat"):
        return None
    if message.get("chat", {}).get("type") not in {"private", "group", "supergroup"}:
        return None
    if not callback and not 0 <= now - message.get("date", 0) <= 600:
        return None
    command = callback.get("data", "") if callback else message.get("text", "")
    if callback and command.startswith("a:"):
        parts = command.split(":")
        if len(parts) != 3:
            return None
        command = f"/approve {parts[1]} {parts[2]}"
    return command, callback.get("id") if callback else None
