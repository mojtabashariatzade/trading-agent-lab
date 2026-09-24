"""Deterministic repository-level merge-readiness gate.

This module enforces a strict rule: merge readiness is false when required checks
fail or required review is missing, unless an explicit approved override rationale
is provided and recorded.
"""
from __future__ import annotations

from dataclasses import dataclass

PASSING_REQUIRED_CHECK_CONCLUSIONS = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED"})
REVIEW_APPROVED = "APPROVED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class RequiredCheckStatus:
    name: str
    conclusion: str

    def normalized_name(self) -> str:
        return str(self.name).strip()

    def normalized_conclusion(self) -> str:
        return str(self.conclusion).strip().upper()


@dataclass(frozen=True)
class MergeGateEvaluationInput:
    repository: str
    pr_number: int
    required_checks: tuple[RequiredCheckStatus, ...]
    review_decision: str | None
    override_approved: bool = False
    override_rationale: str | None = None


@dataclass(frozen=True)
class MergeGateResult:
    merge_ready: bool
    block_codes: tuple[str, ...]
    failed_required_checks: tuple[str, ...]
    review_decision: str | None
    override_applied: bool
    override_rationale: str | None


def _normalize_review_decision(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _normalized_override_rationale(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def evaluate_merge_readiness(payload: MergeGateEvaluationInput) -> MergeGateResult:
    """Evaluate merge readiness deterministically from required checks + review state."""
    failed_required_checks = tuple(
        check.normalized_name()
        for check in payload.required_checks
        if check.normalized_conclusion() not in PASSING_REQUIRED_CHECK_CONCLUSIONS
    )

    review_decision = _normalize_review_decision(payload.review_decision)
    block_codes: list[str] = []
    if failed_required_checks:
        block_codes.append("REQUIRED_CHECKS_FAILED")
    if review_decision != REVIEW_APPROVED:
        block_codes.append("REQUIRED_REVIEW_MISSING")

    override_rationale = _normalized_override_rationale(payload.override_rationale)
    if payload.override_approved and not override_rationale:
        block_codes.append("OVERRIDE_RATIONALE_REQUIRED")

    base_blocked = bool(failed_required_checks) or (review_decision != REVIEW_APPROVED)
    override_applied = payload.override_approved and override_rationale is not None and base_blocked
    merge_ready = not base_blocked

    if override_applied:
        merge_ready = True

    return MergeGateResult(
        merge_ready=merge_ready,
        block_codes=tuple(dict.fromkeys(block_codes)),
        failed_required_checks=failed_required_checks,
        review_decision=review_decision,
        override_applied=override_applied,
        override_rationale=override_rationale if override_applied else None,
    )
