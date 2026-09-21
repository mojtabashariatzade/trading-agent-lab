"""Manifest/checksum local import contract for T006 sampling readiness."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
from pathlib import Path
from typing import Iterable


class DataClass(str, Enum):
    TEST_FIXTURE = "TEST_FIXTURE"
    REAL_OBSERVATION = "REAL_OBSERVATION"


class AcquisitionStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    DOWNLOADED = "DOWNLOADED"
    BLOCKED = "BLOCKED"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _required_text(value: str, name: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


@dataclass(frozen=True)
class Gap:
    after: datetime
    before: datetime
    missing_intervals: int

    def __post_init__(self) -> None:
        after = _aware_utc(self.after)
        before = _aware_utc(self.before)
        if before <= after:
            raise ValueError("gap before must be after gap after")
        if isinstance(self.missing_intervals, bool) or self.missing_intervals <= 0:
            raise ValueError("missing_intervals must be positive")
        object.__setattr__(self, "after", after)
        object.__setattr__(self, "before", before)


@dataclass(frozen=True)
class DataManifest:
    dataset_id: str
    provider_id: str
    provider_version: str
    data_class: DataClass
    acquisition_status: AcquisitionStatus
    checksum_algorithm: str
    checksum_sha256: str
    payload_bytes: int
    actual_start: datetime
    actual_end: datetime
    record_count: int
    expected_interval_seconds: int
    gaps: tuple[Gap, ...]

    def __post_init__(self) -> None:
        for name in ("dataset_id", "provider_id", "provider_version"):
            object.__setattr__(self, name, _required_text(getattr(self, name), name))
        if not isinstance(self.data_class, DataClass):
            raise ValueError("Typed DataClass required")
        if not isinstance(self.acquisition_status, AcquisitionStatus):
            raise ValueError("Typed AcquisitionStatus required")
        if self.acquisition_status != AcquisitionStatus.DOWNLOADED:
            raise ValueError("A manifest describes bytes actually present and must be DOWNLOADED")
        if self.checksum_algorithm.lower() != "sha256":
            raise ValueError("Only sha256 manifests are supported")
        if len(self.checksum_sha256) != 64:
            raise ValueError("Invalid sha256 checksum")
        int(self.checksum_sha256, 16)
        if self.payload_bytes < 0:
            raise ValueError("payload_bytes cannot be negative")
        start = _aware_utc(self.actual_start)
        end = _aware_utc(self.actual_end)
        if end < start:
            raise ValueError("actual_end cannot precede actual_start")
        if isinstance(self.record_count, bool) or self.record_count <= 0:
            raise ValueError("record_count must be positive")
        if (
            isinstance(self.expected_interval_seconds, bool)
            or self.expected_interval_seconds <= 0
        ):
            raise ValueError("expected_interval_seconds must be positive")
        object.__setattr__(self, "actual_start", start)
        object.__setattr__(self, "actual_end", end)
        object.__setattr__(self, "checksum_algorithm", "sha256")
        object.__setattr__(self, "gaps", tuple(self.gaps))


def sha256_file(path: str | Path) -> str:
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _detect_gaps(
    timestamps: list[datetime],
    expected_interval: timedelta,
) -> tuple[Gap, ...]:
    expected_seconds = int(expected_interval.total_seconds())
    if expected_seconds <= 0 or expected_interval != timedelta(seconds=expected_seconds):
        raise ValueError("expected_interval must be a positive whole number of seconds")

    gaps: list[Gap] = []
    for previous, current in zip(timestamps, timestamps[1:]):
        delta = current - previous
        if delta <= timedelta(0):
            raise ValueError("timestamps must be strictly increasing")
        if delta <= expected_interval:
            continue
        missing = int(delta.total_seconds() // expected_seconds) - 1
        if missing < 1:
            missing = 1
        gaps.append(Gap(previous, current, missing))
    return tuple(gaps)


def build_manifest(
    *,
    payload_path: str | Path,
    timestamps: Iterable[datetime],
    expected_interval: timedelta,
    dataset_id: str,
    provider_id: str,
    provider_version: str,
    data_class: DataClass,
) -> DataManifest:
    """Build evidence from bytes that already exist locally; never downloads data."""
    path = Path(payload_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    rows = [_aware_utc(value) for value in timestamps]
    if not rows:
        raise ValueError("Cannot manifest empty observations")
    for previous, current in zip(rows, rows[1:]):
        if current <= previous:
            raise ValueError("timestamps must be strictly increasing")

    seconds = int(expected_interval.total_seconds())
    gaps = _detect_gaps(rows, expected_interval)
    return DataManifest(
        dataset_id=dataset_id,
        provider_id=provider_id,
        provider_version=provider_version,
        data_class=data_class,
        acquisition_status=AcquisitionStatus.DOWNLOADED,
        checksum_algorithm="sha256",
        checksum_sha256=sha256_file(path),
        payload_bytes=path.stat().st_size,
        actual_start=rows[0],
        actual_end=rows[-1],
        record_count=len(rows),
        expected_interval_seconds=seconds,
        gaps=gaps,
    )


def verify_manifest(payload_path: str | Path, manifest: DataManifest) -> bool:
    path = Path(payload_path)
    return (
        path.is_file()
        and path.stat().st_size == manifest.payload_bytes
        and sha256_file(path) == manifest.checksum_sha256
    )


@dataclass(frozen=True)
class StorageLayout:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    @property
    def fixtures(self) -> Path:
        return self.root / "fixtures"

    @property
    def real_observations(self) -> Path:
        return self.root / "real_observations"

    def destination(self, data_class: DataClass, relative_name: str) -> Path:
        if not isinstance(data_class, DataClass):
            raise ValueError("Typed DataClass required")
        relative = Path(relative_name)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("Unsafe relative storage path")
        base = self.fixtures if data_class == DataClass.TEST_FIXTURE else self.real_observations
        return base / relative
