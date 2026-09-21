"""Local historical-data import contracts with no network or broker capability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from hashlib import sha256
from math import isfinite
from pathlib import Path, PurePosixPath
import json
import re


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _require_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be UTC")


def _required_text(value: str, field: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field} is required")


class StorageKind(str, Enum):
    UNIT_FIXTURE = "unit_fixture"
    REAL_OBSERVATION = "real_observation"

    @property
    def directory(self) -> str:
        return {
            StorageKind.UNIT_FIXTURE: "fixtures",
            StorageKind.REAL_OBSERVATION: "real-observations",
        }[self]


class SamplingState(str, Enum):
    DOWNLOADED = "downloaded"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class CoverageGap:
    start_utc: datetime
    end_utc: datetime
    reason: str

    def __post_init__(self) -> None:
        _require_utc(self.start_utc, "gap.start_utc")
        _require_utc(self.end_utc, "gap.end_utc")
        if self.start_utc >= self.end_utc:
            raise ValueError("gap must be a non-empty half-open interval")
        _required_text(self.reason, "gap.reason")


@dataclass(frozen=True)
class ArtifactManifest:
    provider: str
    provider_version: str
    storage_kind: StorageKind
    storage_path: str
    coverage_start_utc: datetime
    coverage_end_utc: datetime
    gaps: tuple[CoverageGap, ...]
    record_count: int
    byte_count: int
    sha256_hex: str

    def __post_init__(self) -> None:
        _required_text(self.provider, "provider")
        _required_text(self.provider_version, "provider_version")
        _require_utc(self.coverage_start_utc, "coverage_start_utc")
        _require_utc(self.coverage_end_utc, "coverage_end_utc")
        if self.coverage_start_utc >= self.coverage_end_utc:
            raise ValueError("actual coverage must be a non-empty half-open interval")
        if self.record_count < 1 or self.byte_count < 1:
            raise ValueError("manifested artifacts must contain bytes and records")
        if not _SHA256.fullmatch(self.sha256_hex):
            raise ValueError("sha256_hex must be a lowercase SHA-256 digest")

        relative = PurePosixPath(self.storage_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("storage_path must be a safe relative path")
        if not relative.parts or relative.parts[0] != self.storage_kind.directory:
            raise ValueError("storage_path does not match storage_kind")

        previous_end: datetime | None = None
        for gap in self.gaps:
            if gap.start_utc < self.coverage_start_utc or gap.end_utc > self.coverage_end_utc:
                raise ValueError("gap lies outside actual coverage")
            if previous_end is not None and gap.start_utc < previous_end:
                raise ValueError("gaps must be sorted and non-overlapping")
            previous_end = gap.end_utc

    def to_json(self) -> str:
        payload = {
            "provider": self.provider,
            "provider_version": self.provider_version,
            "storage_kind": self.storage_kind.value,
            "storage_path": self.storage_path,
            "coverage_start_utc": self.coverage_start_utc.isoformat(),
            "coverage_end_utc": self.coverage_end_utc.isoformat(),
            "gaps": [
                {
                    "start_utc": gap.start_utc.isoformat(),
                    "end_utc": gap.end_utc.isoformat(),
                    "reason": gap.reason,
                }
                for gap in self.gaps
            ],
            "record_count": self.record_count,
            "byte_count": self.byte_count,
            "sha256": self.sha256_hex,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_local_manifest(
    artifact: Path,
    *,
    storage_root: Path,
    provider: str,
    provider_version: str,
    storage_kind: StorageKind,
    coverage_start_utc: datetime,
    coverage_end_utc: datetime,
    gaps: tuple[CoverageGap, ...] = (),
    record_count: int,
) -> ArtifactManifest:
    """Hash one supplied local artifact; this function performs no download."""

    root = storage_root.resolve(strict=True)
    resolved = artifact.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("artifact must be a local file")
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("artifact must be inside storage_root") from exc

    return ArtifactManifest(
        provider=provider,
        provider_version=provider_version,
        storage_kind=storage_kind,
        storage_path=relative.as_posix(),
        coverage_start_utc=coverage_start_utc,
        coverage_end_utc=coverage_end_utc,
        gaps=gaps,
        record_count=record_count,
        byte_count=resolved.stat().st_size,
        sha256_hex=_digest(resolved),
    )


def verify_local_artifact(
    artifact: Path, *, storage_root: Path, manifest: ArtifactManifest
) -> bool:
    """Verify location, byte count and checksum against an immutable manifest."""

    root = storage_root.resolve(strict=True)
    resolved = artifact.resolve(strict=True)
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError:
        return False
    return (
        relative == manifest.storage_path
        and resolved.is_file()
        and resolved.stat().st_size == manifest.byte_count
        and _digest(resolved) == manifest.sha256_hex
    )


@dataclass(frozen=True)
class SamplingReport:
    provider: str
    provider_version: str
    state: SamplingState
    terms_checked_at_utc: datetime | None
    terms_allow_automated_sample: bool | None
    manifest: ArtifactManifest | None
    note: str

    def __post_init__(self) -> None:
        _required_text(self.provider, "provider")
        _required_text(self.provider_version, "provider_version")
        _required_text(self.note, "note")
        if self.terms_checked_at_utc is not None:
            _require_utc(self.terms_checked_at_utc, "terms_checked_at_utc")
        if self.state is SamplingState.DOWNLOADED:
            if self.manifest is None:
                raise ValueError("downloaded samples require a manifest")
            if self.terms_checked_at_utc is None or self.terms_allow_automated_sample is not True:
                raise ValueError("downloaded samples require recorded terms approval")
            if (self.provider, self.provider_version) != (
                self.manifest.provider,
                self.manifest.provider_version,
            ):
                raise ValueError("report and manifest provenance differ")
        elif self.manifest is not None:
            raise ValueError("unverified reports cannot claim a local artifact")


@dataclass(frozen=True)
class MacroReleaseRecord:
    event_id: str
    original_value: float | None
    original_available_at_utc: datetime | None
    revisions: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        _required_text(self.event_id, "event_id")
        if (self.original_value is None) != (self.original_available_at_utc is None):
            raise ValueError("original value and availability must be recorded together")
        if self.original_available_at_utc is not None:
            _require_utc(self.original_available_at_utc, "original_available_at_utc")
        values = ((self.original_value,) if self.original_value is not None else ()) + self.revisions
        if not all(isfinite(value) for value in values):
            raise ValueError("macro values must be finite")


def require_original_release(record: MacroReleaseRecord) -> float:
    """Return only the first release; revisions are never used as a fallback."""

    if record.original_value is None:
        raise ValueError("original release is unavailable; revision substitution is forbidden")
    return record.original_value
