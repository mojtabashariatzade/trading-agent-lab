"""Point-in-time fundamental release contracts for intraday research."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Iterable


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
            "previous_as_known",
            _optional_finite(self.previous_as_known, "previous_as_known"),
        )
        object.__setattr__(
            self,
            "revision",
            _optional_finite(self.revision, "revision"),
        )

        if self.published_at is not None and self.observed_at.value < self.published_at.value:
            raise ValueError("observed_at cannot precede published_at")
        if self.available_at.value < self.observed_at.value:
            raise ValueError("available_at cannot precede observed_at")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.jurisdiction, self.indicator, self.event_period)

    def surprise(self) -> float | None:
        """First-release surprise; missing forecast stays unknown, never zero."""
        if self.first_actual is None or self.pre_release_forecast is None:
            return None
        return self.first_actual - self.pre_release_forecast


class IntradayPrecisionError(ValueError):
    pass


def validate_intraday_same_day_precision(
    release: EconomicRelease,
    decision_time: datetime,
) -> None:
    """Reject causal ordering that same-day day/unknown timestamps cannot establish."""
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
        if point.value.date() != decision.date():
            continue
        if point.precision in IMPRECISE_INTRADAY:
            raise IntradayPrecisionError(
                f"{name} precision {point.precision.value} is not valid for same-day intraday use"
            )


def releases_as_of(
    releases: Iterable[EconomicRelease],
    decision_time: datetime,
    *,
    intraday_same_day: bool = True,
) -> dict[tuple[str, str, str], EconomicRelease]:
    """Return the latest version of each release key that was actually available."""
    decision = _aware_utc(decision_time)
    selected: dict[tuple[str, str, str], EconomicRelease] = {}

    for release in releases:
        if release.available_at.value > decision:
            continue
        if intraday_same_day:
            validate_intraday_same_day_precision(release, decision)

        previous = selected.get(release.key)
        if previous is None:
            selected[release.key] = release
            continue

        candidate_order = (release.available_at.value, release.revision_seq)
        previous_order = (previous.available_at.value, previous.revision_seq)
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
) -> EconomicRelease | None:
    key = (jurisdiction, indicator, event_period)
    return releases_as_of(
        releases,
        decision_time,
        intraday_same_day=intraday_same_day,
    ).get(key)
