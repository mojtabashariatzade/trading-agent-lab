"""Point-in-time fundamental release contracts for intraday research."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from math import isfinite
from typing import Iterable, Mapping

from .registry import SourceKind, default_source_registry


class TimestampPrecision(str, Enum):
    SECOND = "SECOND"
    MINUTE = "MINUTE"
    HOUR = "HOUR"
    DAY = "DAY"
    UNKNOWN = "UNKNOWN"


IMPRECISE_INTRADAY = {
    TimestampPrecision.DAY,
    TimestampPrecision.UNKNOWN,
}

CONSERVATIVE_FORECAST_INTRADAY = {
    TimestampPrecision.HOUR,
    TimestampPrecision.DAY,
    TimestampPrecision.UNKNOWN,
}


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _optional_finite(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} must be finite or None")
    return value


@dataclass(frozen=True)
class TimePoint:
    value: datetime
    precision: TimestampPrecision

    def __post_init__(self) -> None:
        if not isinstance(self.precision, TimestampPrecision):
            raise ValueError("Typed TimestampPrecision required")
        object.__setattr__(self, "value", _aware_utc(self.value))


@dataclass(frozen=True)
class EconomicRelease:
    """Immutable point-in-time record for one event-period release/version."""

    release_id: str
    indicator: str
    jurisdiction: str
    event_period: str
    scheduled_at: TimePoint
    published_at: TimePoint | None
    observed_at: TimePoint
    available_at: TimePoint
    first_actual: float | None
    pre_release_forecast: float | None
    pre_release_forecast_observed_at: TimePoint | None
    pre_release_forecast_source_id: str | None
    pre_release_forecast_source_version: str | None
    previous_as_known: float | None
    revision: float | None
    source_id: str
    source_version: str
    revision_seq: int = 0

    def __post_init__(self) -> None:
        for name in (
            "release_id",
            "indicator",
            "jurisdiction",
            "event_period",
            "source_id",
            "source_version",
        ):
            value = str(getattr(self, name))
            if not value.strip():
                raise ValueError(f"{name} is required")
            object.__setattr__(self, name, value.strip())

        if isinstance(self.revision_seq, bool) or not isinstance(self.revision_seq, int):
            raise ValueError("revision_seq must be an integer")
        if self.revision_seq < 0:
            raise ValueError("revision_seq cannot be negative")

        object.__setattr__(
            self,
            "first_actual",
            _optional_finite(self.first_actual, "first_actual"),
        )
        object.__setattr__(
            self,
            "pre_release_forecast",
            _optional_finite(self.pre_release_forecast, "pre_release_forecast"),
        )
        object.__setattr__(
            self,
            "pre_release_forecast_source_id",
            _optional_string(self.pre_release_forecast_source_id, "pre_release_forecast_source_id"),
        )
        object.__setattr__(
            self,
            "pre_release_forecast_source_version",
            _optional_string(
                self.pre_release_forecast_source_version,
                "pre_release_forecast_source_version",
            ),
        )
        object.__setattr__(
            self,
            "previous_as_known",
            _optional_finite(self.previous_as_known, "previous_as_known"),
        )
        object.__setattr__(
            self,
            "revision",
            _optional_finite(self.revision, "revision"),
        )

        validate_release_pit_constraints(self)

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.jurisdiction, self.indicator, self.event_period)

    def surprise(self, *, soft_fail_on_pit_error: bool = False) -> float | None:
        """First-release surprise; missing forecast stays unknown, never zero."""
        try:
            # Mirror ingest-time PIT enforcement at read-time so mutated/legacy
            # rows cannot bypass forecast provenance requirements downstream.
            validate_release_pit_constraints(self)
        except PITValidationError:
            if soft_fail_on_pit_error:
                return None
            raise
        if self.first_actual is None or self.pre_release_forecast is None:
            return None
        return self.first_actual - self.pre_release_forecast


class IntradayPrecisionError(ValueError):
    pass


@dataclass(frozen=True)
class PITValidationIssue:
    """Deterministic PIT validation issue with stable code/message payload."""

    code: str
    field: str
    message: str


@dataclass(frozen=True)
class PITValidationError(ValueError):
    """Structured validation error for schema/model/parser PIT checks."""

    issues: tuple[PITValidationIssue, ...]

    def __post_init__(self) -> None:
        if not self.issues:
            raise ValueError("PITValidationError requires at least one issue")

    def __str__(self) -> str:
        if len(self.issues) == 1:
            return self.issues[0].message
        return "; ".join(f"{issue.code}: {issue.message}" for issue in self.issues)


def _optional_string(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{name} cannot be blank")
    return normalized


@dataclass(frozen=True)
class _ConservativeBounds:
    """Canonical [lower, upper) interval used by all intraday/PIT timestamp checks.

    This is the single shared bounding mechanism for release chronology, same-day
    precision gating, and as-of availability cutoffs to avoid path-specific drift.
    """

    lower: datetime
    upper: datetime


def _conservative_bounds(point: TimePoint) -> _ConservativeBounds:
    """Map a timestamp to a deterministic conservative precision interval.

    Rule:
    - SECOND/MINUTE/HOUR keep their observed instant as lower bound and extend to
      the precision bucket upper bound.
    - DAY/UNKNOWN use UTC day buckets; unknown precision never expands eligibility.

    All intervals are half-open: [lower, upper). This makes boundary behavior
    deterministic across consumers (upper == decision is eligible, just-before is
    not).
    """
    lower = point.value
    if point.precision is TimestampPrecision.SECOND:
        return _ConservativeBounds(lower=lower, upper=lower + timedelta(seconds=1))
    if point.precision is TimestampPrecision.MINUTE:
        return _ConservativeBounds(lower=lower, upper=lower + timedelta(minutes=1))
    if point.precision is TimestampPrecision.HOUR:
        return _ConservativeBounds(lower=lower, upper=lower + timedelta(hours=1))
    if point.precision in (TimestampPrecision.DAY, TimestampPrecision.UNKNOWN):
        day_start = lower.replace(hour=0, minute=0, second=0, microsecond=0)
        return _ConservativeBounds(lower=day_start, upper=day_start + timedelta(days=1))
    raise ValueError(f"Unsupported timestamp precision {point.precision!r}")


def _precision_bounds(point: TimePoint) -> tuple[datetime, datetime]:
    """Return a conservative [lower, upper) interval implied by timestamp precision.

    The lower bound is the observed value. The upper bound widens by precision so
    intraday checks never infer more exact timing than the source certainty allows.
    DAY/UNKNOWN are normalized to UTC day buckets to keep next-day boundary behavior
    deterministic (a prior day ends exactly at 00:00 of the next day).
    """
    bounds = _conservative_bounds(point)
    return (bounds.lower, bounds.upper)


def _effective_available_at(point: TimePoint) -> datetime:
    """Return the conservative earliest instant when availability is guaranteed.

    For coarse precision we cannot safely assume availability at ``point.value``.
    The upper interval bound is the first instant where the value is definitely
    available under all interpretations of that precision bucket.
    """
    return _conservative_bounds(point).upper


def _is_definitely_before(left: TimePoint, right: TimePoint) -> bool:
    """Whether left is guaranteed to be earlier than right under precision bounds."""
    left_bounds = _conservative_bounds(left)
    right_bounds = _conservative_bounds(right)
    return left_bounds.upper <= right_bounds.lower


def _is_definitely_after(left: TimePoint, right: TimePoint) -> bool:
    """Whether left is guaranteed to be later than right under precision bounds."""
    left_bounds = _conservative_bounds(left)
    right_bounds = _conservative_bounds(right)
    return left_bounds.lower >= right_bounds.upper


def _overlaps_decision_day(point: TimePoint, decision_time: datetime) -> bool:
    """Whether a point's precision interval intersects the decision UTC day."""
    day_start = decision_time.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    bounds = _conservative_bounds(point)
    return bounds.lower < day_end and bounds.upper > day_start


def _validate_forecast_source(source_id: str) -> None:
    registry = default_source_registry()
    if source_id not in registry.ids():
        raise ValueError(f"pre_release_forecast_source_id {source_id} is not in source registry")
    source = registry.get(source_id)
    if source.kind != SourceKind.LICENSED_FORECAST:
        raise ValueError(f"pre_release_forecast_source_id {source_id} is not forecast-capable")


def collect_release_pit_issues(release: EconomicRelease) -> tuple[PITValidationIssue, ...]:
    """Return all PIT violations in deterministic order."""
    issues: list[PITValidationIssue] = []

    def _check_timepoint(
        *,
        field: str,
        value: object,
        required: bool,
        required_code: str,
        invalid_code: str,
    ) -> bool:
        if value is None:
            if required:
                issues.append(
                    PITValidationIssue(
                        code=required_code,
                        field=field,
                        message=f"{field} is required",
                    )
                )
                return False
            return True
        if not isinstance(value, TimePoint):
            issues.append(
                PITValidationIssue(
                    code=invalid_code,
                    field=field,
                    message=f"{field} must be provided as TimePoint",
                )
            )
            return False
        return True

    published_ok = _check_timepoint(
        field="published_at",
        value=release.published_at,
        required=False,
        required_code="PIT_PUBLISHED_AT_REQUIRED",
        invalid_code="PIT_PUBLISHED_AT_TYPE_INVALID",
    )
    observed_ok = _check_timepoint(
        field="observed_at",
        value=release.observed_at,
        required=True,
        required_code="PIT_OBSERVED_AT_REQUIRED",
        invalid_code="PIT_OBSERVED_AT_TYPE_INVALID",
    )
    available_ok = _check_timepoint(
        field="available_at",
        value=release.available_at,
        required=True,
        required_code="PIT_AVAILABLE_AT_REQUIRED",
        invalid_code="PIT_AVAILABLE_AT_TYPE_INVALID",
    )
    forecast_observed_ok = _check_timepoint(
        field="pre_release_forecast_observed_at",
        value=release.pre_release_forecast_observed_at,
        required=False,
        required_code="PIT_FORECAST_OBSERVED_AT_REQUIRED",
        invalid_code="PIT_FORECAST_OBSERVED_AT_TYPE_INVALID",
    )

    if (
        observed_ok
        and published_ok
        and release.published_at is not None
        and _is_definitely_before(release.observed_at, release.published_at)
    ):
        issues.append(
            PITValidationIssue(
                code="PIT_OBSERVED_BEFORE_PUBLISHED",
                field="observed_at",
                message="observed_at cannot precede published_at",
            )
        )
    if observed_ok and available_ok and _is_definitely_after(release.observed_at, release.available_at):
        issues.append(
            PITValidationIssue(
                code="PIT_AVAILABLE_BEFORE_OBSERVED",
                field="available_at",
                message="available_at cannot precede observed_at",
            )
        )

    if release.pre_release_forecast is None:
        if any(
            value is not None
            for value in (
                release.pre_release_forecast_observed_at,
                release.pre_release_forecast_source_id,
                release.pre_release_forecast_source_version,
            )
        ):
            issues.append(
                PITValidationIssue(
                    code="PIT_FORECAST_METADATA_WITHOUT_FORECAST",
                    field="pre_release_forecast",
                    message="pre_release_forecast metadata cannot be set when pre_release_forecast is None",
                )
            )
        return tuple(issues)

    if release.pre_release_forecast_observed_at is None:
        issues.append(
            PITValidationIssue(
                code="PIT_FORECAST_OBSERVED_AT_REQUIRED",
                field="pre_release_forecast_observed_at",
                message="pre_release_forecast_observed_at is required when pre_release_forecast is set",
            )
        )
    if release.pre_release_forecast_source_id is None:
        issues.append(
            PITValidationIssue(
                code="PIT_FORECAST_SOURCE_ID_REQUIRED",
                field="pre_release_forecast_source_id",
                message="pre_release_forecast_source_id is required when pre_release_forecast is set",
            )
        )
    if release.pre_release_forecast_source_version is None:
        issues.append(
            PITValidationIssue(
                code="PIT_FORECAST_SOURCE_VERSION_REQUIRED",
                field="pre_release_forecast_source_version",
                message="pre_release_forecast_source_version is required when pre_release_forecast is set",
            )
        )

    if release.pre_release_forecast_source_id is not None:
        try:
            _validate_forecast_source(release.pre_release_forecast_source_id)
        except ValueError as exc:
            text = str(exc)
            code = (
                "PIT_FORECAST_SOURCE_NOT_REGISTERED"
                if "not in source registry" in text
                else "PIT_FORECAST_SOURCE_NOT_FORECAST_CAPABLE"
            )
            issues.append(
                PITValidationIssue(
                    code=code,
                    field="pre_release_forecast_source_id",
                    message=text,
                )
            )

    if release.pre_release_forecast_observed_at is not None and forecast_observed_ok and available_ok:
        forecast_observed = release.pre_release_forecast_observed_at
        if (
            published_ok
            and release.published_at is not None
            and _is_definitely_after(forecast_observed, release.published_at)
        ):
            issues.append(
                PITValidationIssue(
                    code="PIT_FORECAST_OBSERVED_AFTER_PUBLISHED",
                    field="pre_release_forecast_observed_at",
                    message="pre_release_forecast_observed_at cannot be after published_at",
                )
            )
        if _is_definitely_after(forecast_observed, release.available_at):
            issues.append(
                PITValidationIssue(
                    code="PIT_FORECAST_OBSERVED_AFTER_AVAILABLE",
                    field="pre_release_forecast_observed_at",
                    message="pre_release_forecast_observed_at cannot be after available_at",
                )
            )

    return tuple(issues)


def validate_release_pit_constraints(release: EconomicRelease) -> None:
    """Enforce PIT constraints for both ingest and downstream release consumers."""
    issues = collect_release_pit_issues(release)
    if issues:
        raise PITValidationError(issues)


def parse_release_payload(payload: Mapping[str, object]) -> EconomicRelease:
    """Parse/normalize ingest payload into EconomicRelease with deterministic errors."""
    if not isinstance(payload, Mapping):
        raise PITValidationError(
            (
                PITValidationIssue(
                    code="PARSER_PAYLOAD_TYPE_INVALID",
                    field="payload",
                    message="payload must be a mapping",
                ),
            )
        )

    required_fields: tuple[str, ...] = (
        "release_id",
        "indicator",
        "jurisdiction",
        "event_period",
        "scheduled_at",
        "observed_at",
        "available_at",
        "source_id",
        "source_version",
    )
    issues: list[PITValidationIssue] = []
    for field in required_fields:
        if field not in payload or payload[field] is None:
            issues.append(
                PITValidationIssue(
                    code="PARSER_REQUIRED_FIELD_MISSING",
                    field=field,
                    message=f"{field} is required",
                )
            )
    def _raise_ordered(raised_issues: list[PITValidationIssue]) -> None:
        ordered = sorted(raised_issues, key=lambda item: (item.code, item.field, item.message))
        raise PITValidationError(tuple(ordered))

    def _timepoint(name: str) -> TimePoint | None:
        value = payload.get(name)
        if value is None:
            return None
        if isinstance(value, TimePoint):
            return value
        issues.append(
            PITValidationIssue(
                code="PARSER_TIMEPOINT_TYPE_INVALID",
                field=name,
                message=f"{name} must be provided as TimePoint",
            )
        )
        return None

    scheduled_at = _timepoint("scheduled_at")
    published_at = _timepoint("published_at")
    observed_at = _timepoint("observed_at")
    available_at = _timepoint("available_at")
    forecast_observed_at = _timepoint("pre_release_forecast_observed_at")

    if issues:
        _raise_ordered(issues)

    try:
        release = EconomicRelease(
            release_id=payload.get("release_id"),
            indicator=payload.get("indicator"),
            jurisdiction=payload.get("jurisdiction"),
            event_period=payload.get("event_period"),
            scheduled_at=scheduled_at,
            published_at=published_at,
            observed_at=observed_at,
            available_at=available_at,
            first_actual=payload.get("first_actual"),
            pre_release_forecast=payload.get("pre_release_forecast"),
            pre_release_forecast_observed_at=forecast_observed_at,
            pre_release_forecast_source_id=payload.get("pre_release_forecast_source_id"),
            pre_release_forecast_source_version=payload.get("pre_release_forecast_source_version"),
            previous_as_known=payload.get("previous_as_known"),
            revision=payload.get("revision"),
            source_id=payload.get("source_id"),
            source_version=payload.get("source_version"),
            revision_seq=payload.get("revision_seq", 0),
        )
    except PITValidationError as exc:
        issues.extend(exc.issues)
    except ValueError as exc:
        issues.append(
            PITValidationIssue(
                code="MODEL_VALIDATION_ERROR",
                field="model",
                message=str(exc),
            )
        )
    else:
        if issues:
            ordered = sorted(issues, key=lambda item: (item.code, item.field, item.message))
            raise PITValidationError(tuple(ordered))
        return release

    if issues:
        _raise_ordered(issues)
    raise PITValidationError(
        (
            PITValidationIssue(
                code="MODEL_VALIDATION_ERROR",
                field="model",
                message="Unknown validation failure",
            ),
        )
    )


def validate_intraday_same_day_precision(
    release: EconomicRelease,
    decision_time: datetime,
) -> None:
    """Reject causal ordering that same-day day/unknown timestamps cannot establish."""
    validate_release_pit_constraints(release)
    decision = _aware_utc(decision_time)
    points = (
        ("scheduled_at", release.scheduled_at),
        ("published_at", release.published_at),
        ("observed_at", release.observed_at),
        ("available_at", release.available_at),
    )
    for name, point in points:
        if point is None:
            continue
        if not _overlaps_decision_day(point, decision):
            continue
        if point.precision in IMPRECISE_INTRADAY:
            raise IntradayPrecisionError(
                f"{name} precision {point.precision.value} is not valid for same-day intraday use"
            )

    if release.pre_release_forecast is not None:
        forecast_observed = release.pre_release_forecast_observed_at
        if (
            forecast_observed is not None
            and _overlaps_decision_day(forecast_observed, decision)
            and forecast_observed.precision in CONSERVATIVE_FORECAST_INTRADAY
        ):
            raise IntradayPrecisionError(
                "pre_release_forecast_observed_at precision "
                f"{forecast_observed.precision.value} is not valid for same-day intraday use"
            )


def releases_as_of(
    releases: Iterable[EconomicRelease],
    decision_time: datetime,
    *,
    intraday_same_day: bool = True,
    intraday_override_reason: str | None = None,
    soft_fail_intraday_override: bool = False,
) -> dict[tuple[str, str, str], EconomicRelease]:
    """Return the latest version of each release key that was actually available."""
    decision = _aware_utc(decision_time)
    selected: dict[tuple[str, str, str], EconomicRelease] = {}

    if not intraday_same_day:
        override_reason = None
        if intraday_override_reason is not None:
            override_reason = str(intraday_override_reason).strip() or None
        if override_reason is None:
            if soft_fail_intraday_override:
                # Controlled fallback for backward compatibility: if a legacy
                # caller requests relaxed same-day precision without explicit
                # operator intent metadata, keep strict intraday policy.
                intraday_same_day = True
            else:
                raise PITValidationError(
                    (
                        PITValidationIssue(
                            code="PIT_INTRADAY_OVERRIDE_REASON_REQUIRED",
                            field="intraday_same_day",
                            message=(
                                "intraday_same_day=False requires non-empty "
                                "intraday_override_reason"
                            ),
                        ),
                    )
                )

    for release in releases:
        validate_release_pit_constraints(release)
        if intraday_same_day:
            validate_intraday_same_day_precision(release, decision)
        # Conservative as-of cutoff: only use rows once availability is guaranteed
        # under precision uncertainty. Exact-boundary behavior is deterministic via
        # half-open intervals because DAY/UNKNOWN/HOUR buckets end at a stable upper
        # bound and ``upper == decision`` is considered available.
        if _effective_available_at(release.available_at) > decision:
            continue

        previous = selected.get(release.key)
        if previous is None:
            selected[release.key] = release
            continue

        candidate_order = (
            _effective_available_at(release.available_at),
            release.revision_seq,
            release.available_at.value,
            release.source_version,
            release.source_id,
            release.release_id,
        )
        previous_order = (
            _effective_available_at(previous.available_at),
            previous.revision_seq,
            previous.available_at.value,
            previous.source_version,
            previous.source_id,
            previous.release_id,
        )
        if candidate_order > previous_order:
            selected[release.key] = release

    return selected


def release_as_of(
    releases: Iterable[EconomicRelease],
    decision_time: datetime,
    *,
    jurisdiction: str,
    indicator: str,
    event_period: str,
    intraday_same_day: bool = True,
    intraday_override_reason: str | None = None,
    soft_fail_intraday_override: bool = False,
) -> EconomicRelease | None:
    key = (jurisdiction, indicator, event_period)
    return releases_as_of(
        releases,
        decision_time,
        intraday_same_day=intraday_same_day,
        intraday_override_reason=intraday_override_reason,
        soft_fail_intraday_override=soft_fail_intraday_override,
    ).get(key)
