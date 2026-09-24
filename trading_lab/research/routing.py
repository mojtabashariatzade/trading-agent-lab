"""Allowlisted research-routing guard and read-only handoff contract.

This module provides a protected-path-safe implementation surface for issue #63.
It does not dispatch workers itself; it computes deterministic, auditable routing
outcomes that callers can enforce.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable


class ResearchKind(str, Enum):
    STRATEGY = "STRATEGY"
    FUNDAMENTAL = "FUNDAMENTAL"
    DATA = "DATA"


class RouteState(str, Enum):
    DISPATCH = "DISPATCH"
    BLOCKED = "BLOCKED"
    INTERRUPTED = "INTERRUPTED"


@dataclass(frozen=True)
class ResearchRequest:
    task_id: str
    kind: ResearchKind
    question: str
    requested_by: str


@dataclass(frozen=True)
class ResearchExecutorCapability:
    executor_name: str
    available: bool
    supported_kinds: tuple[ResearchKind, ...]


@dataclass(frozen=True)
class RouteDecision:
    state: RouteState
    route: str
    owner_visible_reason: str
    coding_lane_allowed: bool
    blocked: bool
    reported_executor: str


@dataclass(frozen=True)
class ReadOnlyHandoffRecord:
    schema: str
    task_id: str
    kind: str
    requested_by: str
    route_state: str
    route: str
    blocked: bool
    owner_visible_reason: str
    reported_executor: str
    captured_at_utc: str


def _normalize_supported_kinds(values: Iterable[ResearchKind]) -> tuple[ResearchKind, ...]:
    return tuple(dict.fromkeys(values))


def decide_research_route(
    request: ResearchRequest,
    capability: ResearchExecutorCapability,
    launch_interrupted: bool = False,
) -> RouteDecision:
    """Compute deterministic research routing with coding-lane guardrails.

    Key contract for #63/#41:
    - If capability is unavailable or unsupported, route is BLOCKED with explicit reason.
    - If launch is interrupted, route is INTERRUPTED with explicit reason.
    - In all non-dispatch paths, coding lane is explicitly denied.
    """
    supported = _normalize_supported_kinds(capability.supported_kinds)

    if launch_interrupted:
        return RouteDecision(
            state=RouteState.INTERRUPTED,
            route="read_only_handoff",
            owner_visible_reason=(
                f"Research launch interrupted for {request.kind.value}; "
                "request captured in read-only handoff."
            ),
            coding_lane_allowed=False,
            blocked=True,
            reported_executor="INTERRUPTED",
        )

    if not capability.available:
        return RouteDecision(
            state=RouteState.BLOCKED,
            route="read_only_handoff",
            owner_visible_reason=(
                f"Research executor unavailable for {request.kind.value}; "
                "request captured for read-only handoff."
            ),
            coding_lane_allowed=False,
            blocked=True,
            reported_executor="UNAVAILABLE",
        )

    if request.kind not in supported:
        return RouteDecision(
            state=RouteState.BLOCKED,
            route="read_only_handoff",
            owner_visible_reason=(
                f"Research executor does not support {request.kind.value}; "
                "request captured for read-only handoff."
            ),
            coding_lane_allowed=False,
            blocked=True,
            reported_executor="UNSUPPORTED_KIND",
        )

    return RouteDecision(
        state=RouteState.DISPATCH,
        route="research_executor",
        owner_visible_reason=f"Research request accepted by {capability.executor_name}.",
        coding_lane_allowed=False,
        blocked=False,
        reported_executor=capability.executor_name,
    )


def build_read_only_handoff_record(
    request: ResearchRequest,
    decision: RouteDecision,
    captured_at: datetime | None = None,
) -> ReadOnlyHandoffRecord:
    """Create an auditable handoff record for blocked/interrupted routing outcomes."""
    instant = (captured_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return ReadOnlyHandoffRecord(
        schema="trading-agent-lab.research-handoff.v1",
        task_id=request.task_id,
        kind=request.kind.value,
        requested_by=request.requested_by,
        route_state=decision.state.value,
        route=decision.route,
        blocked=decision.blocked,
        owner_visible_reason=decision.owner_visible_reason,
        reported_executor=decision.reported_executor,
        captured_at_utc=instant.isoformat(),
    )
