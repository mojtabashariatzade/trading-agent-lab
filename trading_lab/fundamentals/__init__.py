"""Point-in-time fundamental research contracts."""
from .registry import (
    SourceEntry,
    SourceKind,
    SourceRegistry,
    VerificationStatus,
    default_source_registry,
)
from .schema import (
    EconomicRelease,
    IntradayPrecisionError,
    PITValidationError,
    PITValidationIssue,
    TimePoint,
    TimestampPrecision,
    collect_release_pit_issues,
    parse_release_payload,
    release_as_of,
    releases_as_of,
    validate_release_pit_constraints,
    validate_intraday_same_day_precision,
)

__all__ = [
    "EconomicRelease",
    "IntradayPrecisionError",
    "PITValidationError",
    "PITValidationIssue",
    "SourceEntry",
    "SourceKind",
    "SourceRegistry",
    "TimePoint",
    "TimestampPrecision",
    "collect_release_pit_issues",
    "VerificationStatus",
    "default_source_registry",
    "parse_release_payload",
    "release_as_of",
    "releases_as_of",
    "validate_release_pit_constraints",
    "validate_intraday_same_day_precision",
]
