"""T007 historical-data archive contracts.

This module is intentionally network-free. It records what may be collected,
where bytes belong, how collection resumes, and what evidence is required
before real observations can be claimed. Provider-specific download code must
live behind a separately verified authorization gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable

from .imports import DataClass, DataManifest, build_manifest


class PermissionStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED_FREE = "VERIFIED_FREE"
    PAID_EXCLUDED = "PAID_EXCLUDED"
    BLOCKED = "BLOCKED"


class ArchivePartition(str, Enum):
    RAW = "raw"
    PROCESSED = "processed"
    TEST_FIXTURE = "test_fixture"
    HOLDOUT = "holdout"


def _aware_utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _required(value: str, name: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


@dataclass(frozen=True)
class SourceAuthorization:
    provider_id: str
    access_method: str
    status: PermissionStatus
    checked_at: datetime
    terms_url: str
    credentials_required: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _required(self.provider_id, "provider_id"))
        object.__setattr__(self, "access_method", _required(self.access_method, "access_method"))
        object.__setattr__(self, "terms_url", _required(self.terms_url, "terms_url"))
        object.__setattr__(self, "checked_at", _aware_utc(self.checked_at, "checked_at"))
        if not isinstance(self.status, PermissionStatus):
            raise ValueError("Typed PermissionStatus required")

    @property
    def collection_allowed(self) -> bool:
        return self.status == PermissionStatus.VERIFIED_FREE and not self.credentials_required

    def require_collection_allowed(self) -> None:
        if self.status == PermissionStatus.PAID_EXCLUDED:
            raise PermissionError("Paid data/service path is excluded")
        if self.credentials_required:
            raise PermissionError("Credential-requiring collection is disabled for coding agents")
        if self.status != PermissionStatus.VERIFIED_FREE:
            raise PermissionError("Provider access is not verified for zero-cost collection")


@dataclass(frozen=True)
class HistoricalStorageLayout:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    def destination(self, partition: ArchivePartition, relative_name: str) -> Path:
        if not isinstance(partition, ArchivePartition):
            raise ValueError("Typed ArchivePartition required")
        relative = Path(relative_name)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("Unsafe relative storage path")
        return self.root / partition.value / relative


@dataclass(frozen=True)
class IngestionCheckpoint:
    provider_id: str
    instrument: str
    requested_start: datetime
    requested_end: datetime
    next_start: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _required(self.provider_id, "provider_id"))
        object.__setattr__(self, "instrument", _required(self.instrument, "instrument").upper())
        start = _aware_utc(self.requested_start, "requested_start")
        end = _aware_utc(self.requested_end, "requested_end")
        nxt = _aware_utc(self.next_start, "next_start")
        if end <= start:
            raise ValueError("requested_end must be after requested_start")
        if nxt < start or nxt > end:
            raise ValueError("next_start must lie within requested range")
        object.__setattr__(self, "requested_start", start)
        object.__setattr__(self, "requested_end", end)
        object.__setattr__(self, "next_start", nxt)

    @property
    def complete(self) -> bool:
        return self.next_start >= self.requested_end

    def advance(self, completed_through: datetime) -> "IngestionCheckpoint":
        completed = _aware_utc(completed_through, "completed_through")
        if completed < self.next_start or completed > self.requested_end:
            raise ValueError("checkpoint advance must be monotonic and bounded")
        return IngestionCheckpoint(
            provider_id=self.provider_id,
            instrument=self.instrument,
            requested_start=self.requested_start,
            requested_end=self.requested_end,
            next_start=completed,
        )


def resumable_windows(
    checkpoint: IngestionCheckpoint,
    *,
    max_chunk: timedelta,
) -> tuple[tuple[datetime, datetime], ...]:
    """Split remaining work into deterministic half-open bounded windows."""
    if max_chunk <= timedelta(0):
        raise ValueError("max_chunk must be positive")
    windows: list[tuple[datetime, datetime]] = []
    cursor = checkpoint.next_start
    while cursor < checkpoint.requested_end:
        end = min(cursor + max_chunk, checkpoint.requested_end)
        windows.append((cursor, end))
        cursor = end
    return tuple(windows)


@dataclass(frozen=True)
class HistoricalManifest:
    instrument: str
    partition: ArchivePartition
    timezone_name: str
    available_at: datetime
    data_end_utc: datetime
    transformation_version: str
    authorization: SourceAuthorization
    payload: DataManifest

    def __post_init__(self) -> None:
        object.__setattr__(self, "instrument", _required(self.instrument, "instrument").upper())
        object.__setattr__(self, "timezone_name", _required(self.timezone_name, "timezone_name"))
        object.__setattr__(
            self,
            "transformation_version",
            _required(self.transformation_version, "transformation_version"),
        )
        object.__setattr__(self, "available_at", _aware_utc(self.available_at, "available_at"))
        object.__setattr__(self, "data_end_utc", _aware_utc(self.data_end_utc, "data_end_utc"))
        if not isinstance(self.partition, ArchivePartition):
            raise ValueError("Typed ArchivePartition required")
        if self.partition == ArchivePartition.TEST_FIXTURE:
            raise ValueError("Real historical manifests cannot use the test-fixture partition")
        self.authorization.require_collection_allowed()
        if self.payload.data_class != DataClass.REAL_OBSERVATION:
            raise ValueError("Historical manifest requires REAL_OBSERVATION bytes")
        if self.payload.provider_id != self.authorization.provider_id:
            raise ValueError("Manifest provider must match authorization provider")
        if self.data_end_utc != self.payload.actual_end:
            raise ValueError("data_end_utc must equal actual observed coverage end")
        if self.available_at < self.payload.actual_end:
            raise ValueError("available_at cannot precede the last observation")



def build_historical_manifest(
    *,
    payload_path: str | Path,
    timestamps: Iterable[datetime],
    expected_interval: timedelta,
    dataset_id: str,
    provider_version: str,
    instrument: str,
    partition: ArchivePartition,
    timezone_name: str,
    available_at: datetime,
    transformation_version: str,
    authorization: SourceAuthorization,
) -> HistoricalManifest:
    """Create evidence only from bytes already present; this never downloads data."""
    authorization.require_collection_allowed()
    rows = tuple(_aware_utc(value, "timestamp") for value in timestamps)
    if not rows:
        raise ValueError("Cannot manifest empty history")
    payload = build_manifest(
        payload_path=payload_path,
        timestamps=rows,
        expected_interval=expected_interval,
        dataset_id=dataset_id,
        provider_id=authorization.provider_id,
        provider_version=provider_version,
        data_class=DataClass.REAL_OBSERVATION,
    )
    return HistoricalManifest(
        instrument=instrument,
        partition=partition,
        timezone_name=timezone_name,
        available_at=available_at,
        data_end_utc=payload.actual_end,
        transformation_version=transformation_version,
        authorization=authorization,
        payload=payload,
    )
