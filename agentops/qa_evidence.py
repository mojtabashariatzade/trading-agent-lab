"""Durable Negar QA evidence — software role, not a separate GitHub human reviewer.

A changed PR head SHA invalidates prior evidence. Arman (controller) verifies
`head_sha` match before auto-merge / owner-approval gates.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = "trading-agent-lab.negar_qa.v1"


def evidence_dir() -> Path:
    override = os.environ.get("NEGAR_QA_DIR", "").strip()
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME") or "."
    return Path(base) / "trading-agent-lab" / "status" / "negar_qa"


def record_negar_qa(
    *,
    repo: str,
    pr: int,
    head_sha: str,
    verdict: str,
    ci_url: str = "",
    qa_payload: dict | None = None,
    now: float | None = None,
    protected_tests: str = "see research-ci",
    candidate_tests: str = "see research-ci",
) -> dict:
    """Write machine-readable Negar QA record tied to exact PR head SHA."""
    ts = datetime.fromtimestamp(now or datetime.now(timezone.utc).timestamp(), timezone.utc).isoformat()
    payload = {
        "schema": SCHEMA,
        "reviewer_role": "Negar",
        "reviewer_kind": "software_role",
        "not_a_github_human": True,
        "repo": repo,
        "pr": int(pr),
        "head_sha": str(head_sha).lower(),
        "verdict": verdict,
        "ci_url": ci_url,
        "protected_tests": protected_tests,
        "candidate_tests": candidate_tests,
        "qa": qa_payload or {},
        "recorded_at": ts,
        "invalid_if_head_sha_changes": True,
    }
    root = evidence_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"pr-{int(pr)}-{str(head_sha).lower()[:12]}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload["artifact_path"] = str(path)
    latest = root / f"pr-{int(pr)}-latest.json"
    latest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def load_negar_qa(pr: int, head_sha: str) -> dict | None:
    path = evidence_dir() / f"pr-{int(pr)}-{str(head_sha).lower()[:12]}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if str(data.get("head_sha") or "").lower() != str(head_sha).lower():
        return None
    return data


def is_negar_qa_valid(evidence: dict | None, *, pr: int, head_sha: str) -> bool:
    if not evidence:
        return False
    if int(evidence.get("pr") or 0) != int(pr):
        return False
    if str(evidence.get("head_sha") or "").lower() != str(head_sha).lower():
        return False
    if evidence.get("verdict") != "PASS":
        return False
    if evidence.get("reviewer_role") != "Negar":
        return False
    return True
