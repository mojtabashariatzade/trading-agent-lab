"""Source register for T005 fundamental research.

Presence in this registry is not verification. History, licensing and coverage stay
UNVERIFIED until sampled/reviewed by the data-validation workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VerificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"


class SourceKind(str, Enum):
    OFFICIAL = "OFFICIAL"
    SECONDARY_CALENDAR = "SECONDARY_CALENDAR"
    REVISION_ARCHIVE = "REVISION_ARCHIVE"
    LICENSED_FORECAST = "LICENSED_FORECAST"


@dataclass(frozen=True)
class SourceEntry:
    source_id: str
    name: str
    kind: SourceKind
    official: bool
    history_status: VerificationStatus = VerificationStatus.UNVERIFIED
    license_status: VerificationStatus = VerificationStatus.UNVERIFIED
    coverage_status: VerificationStatus = VerificationStatus.UNVERIFIED
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.name.strip():
            raise ValueError("source_id and name are required")
        if not isinstance(self.kind, SourceKind):
            raise ValueError("Typed SourceKind required")
        for field_name in ("history_status", "license_status", "coverage_status"):
            if not isinstance(getattr(self, field_name), VerificationStatus):
                raise ValueError("Typed VerificationStatus required")


@dataclass(frozen=True)
class SourceRegistry:
    entries: tuple[SourceEntry, ...]

    def __post_init__(self) -> None:
        ids = [entry.source_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate source_id")

    def get(self, source_id: str) -> SourceEntry:
        for entry in self.entries:
            if entry.source_id == source_id:
                return entry
        raise KeyError(source_id)

    def ids(self) -> tuple[str, ...]:
        return tuple(entry.source_id for entry in self.entries)


def default_source_registry() -> SourceRegistry:
    """Required T005 source names, intentionally unverified until sampled."""
    return SourceRegistry(
        (
            SourceEntry(
                "forex_factory",
                "Forex Factory",
                SourceKind.SECONDARY_CALENDAR,
                False,
                notes="Secondary calendar reference; point-in-time history must be sampled before use.",
            ),
            SourceEntry("ons", "UK Office for National Statistics", SourceKind.OFFICIAL, True),
            SourceEntry("boe", "Bank of England", SourceKind.OFFICIAL, True),
            SourceEntry("boj", "Bank of Japan", SourceKind.OFFICIAL, True),
            SourceEntry(
                "statistics_bureau_japan",
                "Statistics Bureau of Japan",
                SourceKind.OFFICIAL,
                True,
            ),
            SourceEntry(
                "esri_japan",
                "Economic and Social Research Institute, Japan",
                SourceKind.OFFICIAL,
                True,
            ),
            SourceEntry("mof_japan", "Ministry of Finance Japan", SourceKind.OFFICIAL, True),
            SourceEntry("federal_reserve", "Federal Reserve", SourceKind.OFFICIAL, True),
            SourceEntry("bls", "U.S. Bureau of Labor Statistics", SourceKind.OFFICIAL, True),
            SourceEntry("bea", "U.S. Bureau of Economic Analysis", SourceKind.OFFICIAL, True),
            SourceEntry(
                "alfred",
                "ALFRED",
                SourceKind.REVISION_ARCHIVE,
                True,
                notes="Revision/archive source; point-in-time field coverage must be sampled.",
            ),
            SourceEntry(
                "licensed_forecast_provider",
                "Licensed forecast provider",
                SourceKind.LICENSED_FORECAST,
                False,
                notes="Placeholder class only; no vendor, purchase, credential or entitlement is assumed.",
            ),
        )
    )
