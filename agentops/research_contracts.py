"""Typed research task contracts. Never part of the trading Decision Core."""
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping


class ResearchKind(str, Enum):
    STRATEGY = "STRATEGY"
    FUNDAMENTAL = "FUNDAMENTAL"
    DATA = "DATA"


class ResearchState(str, Enum):
    PENDING = "PENDING"
    LAUNCHING = "LAUNCHING"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


KIND_TO_ROLE: Mapping[ResearchKind, str] = {
    ResearchKind.STRATEGY: "quant",
    ResearchKind.FUNDAMENTAL: "fundamental",
    ResearchKind.DATA: "data",
}

ROLE_TO_KIND: Mapping[str, ResearchKind] = {
    role: kind for kind, role in KIND_TO_ROLE.items()
}

ACTIVE_RESEARCH_STATES = frozenset({
    ResearchState.PENDING.value,
    ResearchState.LAUNCHING.value,
    ResearchState.RUNNING.value,
    ResearchState.BLOCKED.value,
    ResearchState.SUBMITTED.value,
    ResearchState.UNDER_REVIEW.value,
})


@dataclass(frozen=True)
class Citation:
    citation_id: str
    publisher: str
    title: str
    retrieved_at: str
    url: str = ""
    published_at: str = ""
    access_notes: str = ""

    def __post_init__(self) -> None:
        if not self.citation_id.strip():
            raise ValueError("citation_id is required")
        if not self.publisher.strip() or not self.title.strip():
            raise ValueError("publisher and title are required")
        if not self.retrieved_at.strip():
            raise ValueError("retrieved_at is required")


@dataclass(frozen=True)
class ResearchFinding:
    claim: str
    evidence_citation_ids: tuple[str, ...]
    confidence: str
    limitations: str = ""

    def __post_init__(self) -> None:
        if not self.claim.strip():
            raise ValueError("finding claim is required")
        if not self.evidence_citation_ids:
            raise ValueError("each finding needs at least one citation id")
        if self.confidence not in {"HIGH", "MEDIUM", "LOW", "UNVERIFIED"}:
            raise ValueError("invalid confidence")


@dataclass(frozen=True)
class ResearchReport:
    research_id: str
    kind: ResearchKind
    owner_role: str
    question: str
    status: str
    citations: tuple[Citation, ...]
    findings: tuple[ResearchFinding, ...]
    hypotheses: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    proposed_tests: tuple[str, ...] = ()
    missing_dependency: str = ""
    parameter_ranges: Mapping[str, str] = field(default_factory=dict)
    assumptions: tuple[str, ...] = ()
    coverage_notes: str = ""
    look_ahead_risks: tuple[str, ...] = ()
    revision_notes: str = ""
    summary: str = ""

    def __post_init__(self) -> None:
        if self.owner_role != KIND_TO_ROLE[self.kind]:
            raise ValueError("owner_role does not match research kind")
        if self.status not in {"COMPLETE", "BLOCKED", "PARTIAL"}:
            raise ValueError("invalid report status")
        if self.status == "BLOCKED" and not self.missing_dependency.strip():
            raise ValueError("BLOCKED reports require missing_dependency")
        if self.status == "COMPLETE" and not self.citations:
            raise ValueError("COMPLETE reports require citations")
        if self.status == "COMPLETE" and not self.findings:
            raise ValueError("COMPLETE reports require findings")
        known = {c.citation_id for c in self.citations}
        for finding in self.findings:
            missing = [cid for cid in finding.evidence_citation_ids if cid not in known]
            if missing:
                raise ValueError("finding cites unknown ids: " + ", ".join(missing))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        return payload


@dataclass(frozen=True)
class ResearchArtifact:
    artifact_id: str
    research_id: str
    kind: ResearchKind
    owner_role: str
    approved_at: float
    report: Mapping[str, Any]
    review_summary: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        return payload


def parse_research_report(payload: Mapping[str, Any] | str, *, research_id: str, kind: ResearchKind, owner_role: str) -> ResearchReport:
    """Validate structured researcher output. Fabricated empty shells are rejected."""
    if isinstance(payload, str):
        import json
        text = payload.strip()
        if text.startswith("```json\n") and text.endswith("```"):
            text = text[8:-3].strip()
        elif text.startswith("```\n") and text.endswith("```"):
            text = text[4:-3].strip()
        data = json.loads(text)
    else:
        data = dict(payload)
    if not isinstance(data, dict):
        raise ValueError("Research report must be an object")
    if data.get("research_id") not in (None, research_id):
        raise ValueError("research_id mismatch")
    citations = tuple(
        Citation(
            citation_id=str(item["citation_id"]),
            publisher=str(item["publisher"]),
            title=str(item["title"]),
            retrieved_at=str(item["retrieved_at"]),
            url=str(item.get("url", "")),
            published_at=str(item.get("published_at", "")),
            access_notes=str(item.get("access_notes", "")),
        )
        for item in data.get("citations", [])
    )
    findings = tuple(
        ResearchFinding(
            claim=str(item["claim"]),
            evidence_citation_ids=tuple(str(x) for x in item["evidence_citation_ids"]),
            confidence=str(item["confidence"]),
            limitations=str(item.get("limitations", "")),
        )
        for item in data.get("findings", [])
    )
    return ResearchReport(
        research_id=research_id,
        kind=kind,
        owner_role=owner_role,
        question=str(data.get("question") or ""),
        status=str(data["status"]),
        citations=citations,
        findings=findings,
        hypotheses=tuple(str(x) for x in data.get("hypotheses", [])),
        unknowns=tuple(str(x) for x in data.get("unknowns", [])),
        proposed_tests=tuple(str(x) for x in data.get("proposed_tests", [])),
        missing_dependency=str(data.get("missing_dependency", "")),
        parameter_ranges={str(k): str(v) for k, v in dict(data.get("parameter_ranges", {})).items()},
        assumptions=tuple(str(x) for x in data.get("assumptions", [])),
        coverage_notes=str(data.get("coverage_notes", "")),
        look_ahead_risks=tuple(str(x) for x in data.get("look_ahead_risks", [])),
        revision_notes=str(data.get("revision_notes", "")),
        summary=str(data.get("summary", "")),
    )
