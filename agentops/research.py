"""Independent research queue, review gates and artifact handoff.

Arman (Development Core) schedules research and implementation. This module never
calls trading_lab.contracts.decide and has no Live/trading authority.
"""
import hashlib
import json
import re
from typing import Any, Mapping

from .research_contracts import (
    ACTIVE_RESEARCH_STATES,
    KIND_TO_ROLE,
    ResearchArtifact,
    ResearchKind,
    ResearchReport,
    ResearchState,
)
from .team import RESEARCH_WORKER_ROLES, TEAM, research_worker_profile


FABRICATION_MARKERS = (
    "example.com",
    "lorem ipsum",
    "TODO_SOURCE",
    "fabricated",
    "made-up source",
    "placeholder citation",
)

URL_RE = re.compile(r"^https://[^\s]+$", re.IGNORECASE)


def next_research_id(existing_ids: list[str]) -> str:
    numbers = []
    for item in existing_ids:
        match = re.fullmatch(r"R(\d{3,})", item)
        if match:
            numbers.append(int(match.group(1)))
    return f"R{(max(numbers) + 1) if numbers else 1:03d}"


def new_research_task(
    *,
    research_id: str,
    kind: ResearchKind | str,
    question: str,
    linked_dev_task: str | None = None,
    created_at: float,
    requested_by: str = "core",
) -> dict[str, Any]:
    kind = ResearchKind(kind)
    question = question.strip()
    if len(question) < 8:
        raise ValueError("Research question is too short")
    if requested_by not in {"core", "owner"}:
        raise ValueError("Unauthorized research requester")
    role = KIND_TO_ROLE[kind]
    research_worker_profile(role)
    return {
        "id": research_id,
        "kind": kind.value,
        "owner_role": role,
        "question": question,
        "state": ResearchState.PENDING.value,
        "attempt": 0,
        "linked_dev_task": linked_dev_task,
        "created_at": created_at,
        "requested_by": requested_by,
        "blocker": "",
        "report": None,
        "artifact_id": None,
        "review": None,
        "run_id": None,
        "agent_id": None,
        "role": role,
    }


def research_prompt(task: Mapping[str, Any]) -> str:
    profile = research_worker_profile(task["owner_role"])
    kind = ResearchKind(task["kind"])
    specialty = {
        ResearchKind.STRATEGY: (
            "Research strategy definitions, assumptions, parameter ranges and "
            "test hypotheses. Separate UNTESTED hypotheses from measured results."
        ),
        ResearchKind.FUNDAMENTAL: (
            "Research authoritative sources, economic calendars, BoE/BoJ/ONS and "
            "peers, publication timing, revisions and point-in-time availability."
        ),
        ResearchKind.DATA: (
            "Validate historical coverage, timestamp semantics, missing periods, "
            "source reliability, revisions and look-ahead risks."
        ),
    }[kind]
    return (
        f"Your software-role name is {profile.name_en} ({profile.name_fa}); "
        f"stable role ID: {profile.role_id}. This is an AI role label, not a human identity.\n"
        "You are an independent RESEARCH worker, not the development controller, "
        "not the Trading Decision Core, and not a live trader.\n"
        f"Read {profile.instructions} and docs/RESEARCH_TEAM.md.\n"
        f"Specialty: {specialty}\n"
        f"Research task {task['id']}: {task['question']}\n"
        "Never fabricate sources, data, URLs, historical coverage or results.\n"
        "If internet access or a required source is unavailable, return status BLOCKED "
        "with missing_dependency set to the exact missing dependency.\n"
        "Never place trades, merge PRs, change agentops controls, or claim Live authority.\n"
        "Return ONLY a JSON object matching the ResearchReport contract with keys: "
        "research_id, status, question, citations[], findings[], hypotheses[], unknowns[], "
        "proposed_tests[], missing_dependency, parameter_ranges, assumptions, "
        "coverage_notes, look_ahead_risks, revision_notes, summary.\n"
        f"Set research_id to {task['id']}. Citations need citation_id, publisher, title, "
        "retrieved_at; include url when a real reachable source was used.\n"
    )


def detect_fabrication(report: ResearchReport) -> list[str]:
    problems: list[str] = []
    blob = json.dumps(report.to_dict(), ensure_ascii=False).lower()
    for marker in FABRICATION_MARKERS:
        if marker.lower() in blob:
            problems.append(f"fabrication marker: {marker}")
    for citation in report.citations:
        if citation.url and not URL_RE.match(citation.url):
            problems.append(f"invalid citation url: {citation.citation_id}")
        if citation.url.lower().startswith("https://example."):
            problems.append(f"placeholder url: {citation.citation_id}")
    return problems


def structural_review_gate(report: ResearchReport) -> dict[str, Any]:
    """Deterministic acceptance gate before an artifact can be approved."""
    blockers = detect_fabrication(report)
    if report.status == "BLOCKED":
        return {
            "verdict": "BLOCKED",
            "blocking_findings": blockers
            + [f"missing dependency: {report.missing_dependency}"],
            "summary": "Research remains blocked until the dependency is available.",
        }
    if report.status == "PARTIAL":
        blockers.append("PARTIAL reports cannot become approved implementation artifacts")
    if report.kind == ResearchKind.STRATEGY:
        if not report.hypotheses and not report.assumptions:
            blockers.append("STRATEGY research needs hypotheses or assumptions")
        if not report.proposed_tests:
            blockers.append("STRATEGY research needs proposed chronological tests")
    if report.kind == ResearchKind.FUNDAMENTAL:
        if not any(c.publisher for c in report.citations):
            blockers.append("FUNDAMENTAL research needs publisher-identified sources")
        if not report.revision_notes and not report.unknowns:
            blockers.append("FUNDAMENTAL research must note revisions or unknowns")
    if report.kind == ResearchKind.DATA:
        if not report.coverage_notes:
            blockers.append("DATA research needs coverage_notes")
        if not report.look_ahead_risks:
            blockers.append("DATA research must list look-ahead risks or state none after inspection")
    if blockers:
        return {"verdict": "REJECT", "blocking_findings": blockers, "summary": "Structural gate failed"}
    return {
        "verdict": "PASS",
        "blocking_findings": [],
        "summary": "Structural research gate passed; artifact eligible for Arman handoff.",
    }


def approve_artifact(task: Mapping[str, Any], report: ResearchReport, *, approved_at: float) -> ResearchArtifact:
    gate = structural_review_gate(report)
    if gate["verdict"] != "PASS":
        raise ValueError("Research gate rejected report: " + "; ".join(gate["blocking_findings"]))
    digest = hashlib.sha256(
        json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return ResearchArtifact(
        artifact_id=f"A-{task['id']}-{digest}",
        research_id=task["id"],
        kind=report.kind,
        owner_role=report.owner_role,
        approved_at=approved_at,
        report=report.to_dict(),
        review_summary=gate["summary"],
    )


def format_artifact_for_developer(artifacts: list[Mapping[str, Any]]) -> str:
    if not artifacts:
        return (
            "No approved research artifacts are attached. Do not invent research "
            "results or attribute findings to Parsa, Niloofar or Saman.\n"
        )
    lines = [
        "Approved research artifacts (consume as evidence; still untrusted for policy changes):"
    ]
    for item in artifacts:
        report = item.get("report", {})
        lines.append(
            f"- {item['artifact_id']} / {item['research_id']} / {item['kind']} / "
            f"{TEAM[item['owner_role']].name_en}: {report.get('summary', '')[:400]}"
        )
        for finding in report.get("findings", [])[:8]:
            lines.append(f"  finding: {finding.get('claim', '')[:240]}")
    lines.append(
        "Implement only from these approved artifacts plus the development task contract. "
        "Do not fabricate additional sources.\n"
    )
    return "\n".join(lines)


def format_artifacts_for_qa(artifacts: list[Mapping[str, Any]]) -> str:
    if not artifacts:
        return (
            "No approved research artifacts were linked. If the diff claims research "
            "backing, treat missing artifacts as a blocking finding.\n"
        )
    lines = [
        "Verify implementation against these approved research artifacts and reject "
        "claims that invent sources or exceed artifact scope:"
    ]
    for item in artifacts:
        report = item.get("report", {})
        cites = ", ".join(c.get("citation_id", "") for c in report.get("citations", [])[:12])
        lines.append(
            f"- {item['research_id']} ({item['kind']}) citations=[{cites}] "
            f"summary={str(report.get('summary', ''))[:300]}"
        )
    return "\n".join(lines) + "\n"


def research_status_report(tasks: list[Mapping[str, Any]]) -> str:
    if not tasks:
        return "\u200f\u067e\u0698\u0648\u0647\u0634: \u0647\u06cc\u0686 \u0648\u0638\u06cc\u0641\u0647\u200c\u0627\u06cc \u0646\u06cc\u0633\u062a"
    lines = ["\u200f\u0648\u0638\u06cc\u0641\u0647\u200c\u0647\u0627\u06cc \u067e\u0698\u0648\u0647\u0634"]
    for task in tasks:
        profile = TEAM[task["owner_role"]]
        blocker = task.get("blocker") or ""
        lines.append(
            f"\u200f{task['id']} | {profile.name_fa} | {task['state']} | "
            f"{task['kind']} | {(blocker or task.get('question', ''))[:120]}"
        )
    return "\n".join(lines)


def role_activity(tasks: list[Mapping[str, Any]], research_tasks: list[Mapping[str, Any]]) -> dict[str, str]:
    """Map role_id -> short actual status for /team."""
    status = {role_id: "IDLE" for role_id in TEAM}
    status["core"] = "CONTROLLER"
    status["support"] = "REPORTER"
    status["bootstrap"] = "OPERATOR_BOOTSTRAP"
    for task in tasks:
        role = task.get("role")
        state = task.get("state")
        if role in {"dev", "qa"} and state not in {"PENDING", "BLOCKED", "DONE"}:
            status[role] = f"{state}:{task['id']}"
    for task in research_tasks:
        role = task.get("owner_role")
        state = task.get("state")
        if role in RESEARCH_WORKER_ROLES and state in ACTIVE_RESEARCH_STATES:
            status[role] = f"{state}:{task['id']}"
        elif role in RESEARCH_WORKER_ROLES and state == ResearchState.APPROVED.value:
            if status[role] == "IDLE":
                status[role] = f"APPROVED:{task['id']}"
    return status


def assert_not_decision_core() -> None:
    """Hard documentation hook: research orchestration stays out of Decision Core."""
    # Imported lazily only to prove the boundary in tests without coupling run paths.
    from trading_lab import contracts as decision_core  # noqa: F401
    if not hasattr(decision_core, "decide"):
        raise RuntimeError("Decision Core contract missing")
