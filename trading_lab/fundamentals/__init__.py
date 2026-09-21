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
    TimePoint,
    TimestampPrecision,
    release_as_of,
    releases_as_of,
    validate_intraday_same_day_precision,
)

__all__ = [
    "EconomicRelease",
    "IntradayPrecisionError",
    "SourceEntry",
    "SourceKind",
    "SourceRegistry",
    "TimePoint",
    "TimestampPrecision",
    "VerificationStatus",
    "default_source_registry",
    "release_as_of",
    "releases_as_of",
    "validate_intraday_same_day_precision",
]
