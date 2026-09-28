"""Deterministic GitHub policy validators for process issues #52 and #57.

These helpers validate issue/comment text against the repository's owner-approved
process checklists:
- #57 epic-creation policy minimum fields
- #52 blocker metadata minimum fields
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyEvaluationResult:
    compliant: bool
    found_requirements: tuple[str, ...]
    missing_requirements: tuple[str, ...]


def _normalize_text(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def evaluate_epic_creation_policy(body: str) -> PolicyEvaluationResult:
    """Validate epic proposal text against issue #57 hard-rule checklist."""
    text = _normalize_text(body)

    checks: tuple[tuple[str, bool], ...] = (
        (
            "WHY_EXISTING_EPICS_CANNOT_ABSORB_SCOPE",
            _contains_any(
                text,
                (
                    "why existing epics cannot absorb",
                    "why existing epic cannot absorb",
                    "cannot be absorbed by existing epic",
                ),
            ),
        ),
        (
            "DEPENDENCY_MAP_BLOCKED_BY_AND_BLOCKS",
            (
                _contains_any(text, ("dependency map", "dependencies"))
                and _contains_any(text, ("blocked-by", "blocked by"))
                and _contains_any(text, ("blocks",))
            ),
        ),
        (
            "OWNER",
            _contains_any(text, ("owner:", "owner ", "assignee:", "responsible:")),
        ),
        (
            "ACCEPTANCE_CRITERIA",
            _contains_any(text, ("acceptance criteria", "acceptance:")),
        ),
        (
            "DELIVERY_IMPACT",
            _contains_any(text, ("delivery impact", "time/risk tradeoff", "time risk tradeoff")),
        ),
    )

    found = tuple(code for code, ok in checks if ok)
    missing = tuple(code for code, ok in checks if not ok)
    return PolicyEvaluationResult(compliant=not missing, found_requirements=found, missing_requirements=missing)


def evaluate_blocker_metadata_policy(text_body: str) -> PolicyEvaluationResult:
    """Validate blocker text against issue #52 metadata requirements."""
    text = _normalize_text(text_body)

    checks: tuple[tuple[str, bool], ...] = (
        ("PRECISE_REASON", _contains_any(text, ("reason:", "root cause:", "because"))),
        ("OWNER", _contains_any(text, ("owner:", "assignee:", "responsible:"))),
        ("DEPENDENCY", _contains_any(text, ("dependency:", "depends on", "blocked-by", "blocked by"))),
        ("UNBLOCK_CONDITION", _contains_any(text, ("unblock condition:", "unblocked when", "to unblock"))),
    )

    found = tuple(code for code, ok in checks if ok)
    missing = tuple(code for code, ok in checks if not ok)
    return PolicyEvaluationResult(compliant=not missing, found_requirements=found, missing_requirements=missing)


def evaluate_github_trace_policy(text_body: str) -> PolicyEvaluationResult:
    """Validate process updates against issue #52 GitHub-only visibility rules.

    The check is deterministic and text-based so it can gate templates/comments:
    - Every progress update must include a GitHub-visible trace (Issue/PR/Comment).
    - Internal board/tool state may appear only as supportive context.
    """
    text = _normalize_text(text_body)

    has_issue_ref = bool(re.search(r"#\d+", text))
    has_github_url = _contains_any(
        text,
        (
            "github.com",
            "/issues/",
            "/pull/",
        ),
    )
    has_trace = has_issue_ref or has_github_url

    has_visibility_entity = _contains_any(
        text,
        (
            "issue",
            "sub-issue",
            "sub issue",
            "pr",
            "pull request",
            "comment",
        ),
    )

    mentions_internal_only_source = _contains_any(
        text,
        (
            "kanban",
            "internal board",
            "internal tracker",
            "local-only",
            "local only",
        ),
    )
    internal_is_marked_supportive = _contains_any(
        text,
        (
            "supportive only",
            "supporting only",
            "not source of truth",
            "github is source of truth",
        ),
    )

    has_status_word = _contains_any(text, ("done", "blocked", "in progress", "complete", "completed"))
    internal_only_status_violation = has_status_word and mentions_internal_only_source and not has_trace

    checks: tuple[tuple[str, bool], ...] = (
        ("GITHUB_TRACE_PRESENT", has_trace),
        ("VISIBILITY_ENTITY_PRESENT", has_visibility_entity),
        (
            "INTERNAL_TOOLS_MARKED_SUPPORTIVE",
            (not mentions_internal_only_source) or internal_is_marked_supportive,
        ),
        ("NO_INTERNAL_ONLY_STATUS", not internal_only_status_violation),
    )

    found = tuple(code for code, ok in checks if ok)
    missing = tuple(code for code, ok in checks if not ok)
    return PolicyEvaluationResult(compliant=not missing, found_requirements=found, missing_requirements=missing)
