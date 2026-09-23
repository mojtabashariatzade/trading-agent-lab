"""Manifest/checksum local import contract for T006 sampling readiness."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Callable, Iterable


DIGEST_ALGORITHM_SHA256 = "sha256"


class DataClass(str, Enum):
    TEST_FIXTURE = "TEST_FIXTURE"
    REAL_OBSERVATION = "REAL_OBSERVATION"


class AcquisitionStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    DOWNLOADED = "DOWNLOADED"
    BLOCKED = "BLOCKED"


class IntegrityCheckError(ValueError):
    """Raised when immutable payload, record, metadata, or provenance checks fail."""


@dataclass(frozen=True)
class PayloadSnapshot:
    """Immutable parse-boundary payload identity.

    Invariants:
    - raw_bytes is captured once at the parse boundary and never mutated.
    - payload_sha256 is derived only from raw_bytes.
    - payload_size_bytes reflects len(raw_bytes) at capture time.
    """

    raw_bytes: bytes
    payload_sha256: str
    payload_size_bytes: int
    payload_digest_algorithm: str = DIGEST_ALGORITHM_SHA256

    def __post_init__(self) -> None:
        frozen_bytes = bytes(self.raw_bytes)
        digest_algorithm = _normalize_digest_algorithm(
            self.payload_digest_algorithm,
            "payload_digest_algorithm",
        )
        digest = _digest_bytes(frozen_bytes, digest_algorithm)
        if self.payload_sha256:
            normalized = _normalize_sha256(self.payload_sha256, "payload_sha256")
            if normalized != digest:
                raise ValueError("payload_sha256 does not match raw_bytes")
            digest = normalized
        object.__setattr__(self, "raw_bytes", frozen_bytes)
        object.__setattr__(self, "payload_sha256", digest)
        object.__setattr__(self, "payload_size_bytes", len(frozen_bytes))
        object.__setattr__(self, "payload_digest_algorithm", digest_algorithm)


def _capture_payload_snapshot(
    payload: bytes | bytearray | memoryview,
    *,
    digest_algorithm: str = DIGEST_ALGORITHM_SHA256,
) -> PayloadSnapshot:
    """Capture immutable parse-boundary bytes and stable digest identity.

    This must run immediately after payload ingest and before any parsing/transforms.
    """

    return PayloadSnapshot(
        raw_bytes=bytes(payload),
        payload_sha256="",
        payload_size_bytes=0,
        payload_digest_algorithm=digest_algorithm,
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _required_text(value: str, name: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _normalize_sha256(value: str, name: str) -> str:
    digest = str(value).strip().lower()
    if len(digest) != 64:
        raise ValueError(f"Invalid {name}")
    int(digest, 16)
    return digest


def _normalize_digest_algorithm(value: str, name: str) -> str:
    algorithm = str(value).strip().lower()
    if not algorithm:
        raise ValueError(f"{name} is required")
    if algorithm != DIGEST_ALGORITHM_SHA256:
        raise ValueError(f"Unsupported {name}: {algorithm}")
    return algorithm


def _digest_bytes(payload: bytes, algorithm: str) -> str:
    normalized = _normalize_digest_algorithm(algorithm, "digest algorithm")
    if normalized == DIGEST_ALGORITHM_SHA256:
        return hashlib.sha256(payload).hexdigest()
    raise ValueError(f"Unsupported digest algorithm: {normalized}")


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
class RecordBinding:
    record_index: int
    record_payload_sha256: str
    source_byte_start: int
    source_byte_end: int
    parsed_timestamp_utc: datetime

    def __post_init__(self) -> None:
        if isinstance(self.record_index, bool) or self.record_index < 0:
            raise ValueError("record_index must be non-negative")
        digest = _normalize_sha256(self.record_payload_sha256, "record_payload_sha256")
        start = int(self.source_byte_start)
        end = int(self.source_byte_end)
        if start < 0 or end <= start:
            raise ValueError("Invalid record byte range")
        object.__setattr__(self, "record_payload_sha256", digest)
        object.__setattr__(self, "source_byte_start", start)
        object.__setattr__(self, "source_byte_end", end)
        object.__setattr__(self, "parsed_timestamp_utc", _aware_utc(self.parsed_timestamp_utc))


@dataclass(frozen=True)
class MetadataBinding:
    payload_sha256: str
    record_index: int
    record_payload_sha256: str
    timestamp_utc: datetime
    is_gap_boundary: bool = False
    gap_id: str = ""
    availability_class: str = ""

    def __post_init__(self) -> None:
        payload_sha = _normalize_sha256(self.payload_sha256, "payload_sha256")
        record_sha = _normalize_sha256(self.record_payload_sha256, "record_payload_sha256")
        if isinstance(self.record_index, bool) or self.record_index < 0:
            raise ValueError("record_index must be non-negative")
        object.__setattr__(self, "payload_sha256", payload_sha)
        object.__setattr__(self, "record_payload_sha256", record_sha)
        object.__setattr__(self, "timestamp_utc", _aware_utc(self.timestamp_utc))
        object.__setattr__(self, "gap_id", str(self.gap_id).strip())
        object.__setattr__(self, "availability_class", str(self.availability_class).strip())


def _clone_record_binding(binding: RecordBinding) -> RecordBinding:
    return RecordBinding(
        record_index=binding.record_index,
        record_payload_sha256=binding.record_payload_sha256,
        source_byte_start=binding.source_byte_start,
        source_byte_end=binding.source_byte_end,
        parsed_timestamp_utc=binding.parsed_timestamp_utc,
    )


def _clone_metadata_binding(binding: MetadataBinding) -> MetadataBinding:
    return MetadataBinding(
        payload_sha256=binding.payload_sha256,
        record_index=binding.record_index,
        record_payload_sha256=binding.record_payload_sha256,
        timestamp_utc=binding.timestamp_utc,
        is_gap_boundary=binding.is_gap_boundary,
        gap_id=binding.gap_id,
        availability_class=binding.availability_class,
    )


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
    source_provenance: str = ""
    legal_source: str = ""
    payload_snapshot_sha256: str = ""
    payload_digest_algorithm: str = DIGEST_ALGORITHM_SHA256
    payload_snapshot_path: str = ""
    payload_records_path: str = ""
    record_digest_algorithm: str = DIGEST_ALGORITHM_SHA256
    records_root_sha256: str = ""
    records_root_digest_algorithm: str = DIGEST_ALGORITHM_SHA256
    record_bindings: tuple[RecordBinding, ...] = ()
    metadata_bindings: tuple[MetadataBinding, ...] = ()

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
        payload_digest_algorithm = _normalize_digest_algorithm(
            self.payload_digest_algorithm,
            "payload_digest_algorithm",
        )
        if payload_digest_algorithm != self.checksum_algorithm.lower():
            raise ValueError("payload_digest_algorithm must match checksum_algorithm")
        checksum_sha256 = _normalize_sha256(self.checksum_sha256, "sha256 checksum")
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
        source_provenance = str(self.source_provenance).strip()
        legal_source = str(self.legal_source).strip()
        payload_snapshot_sha256 = str(self.payload_snapshot_sha256).strip().lower()
        if payload_snapshot_sha256:
            payload_snapshot_sha256 = _normalize_sha256(
                payload_snapshot_sha256,
                "payload_snapshot_sha256",
            )
        if source_provenance and not legal_source:
            raise ValueError("legal_source is required when source_provenance is set")
        if legal_source and not source_provenance:
            raise ValueError("source_provenance is required when legal_source is set")

        payload_snapshot_path = str(self.payload_snapshot_path).strip()
        payload_records_path = str(self.payload_records_path).strip()
        records_root_sha256 = str(self.records_root_sha256).strip().lower()
        record_digest_algorithm = _normalize_digest_algorithm(
            self.record_digest_algorithm,
            "record_digest_algorithm",
        )
        records_root_digest_algorithm = _normalize_digest_algorithm(
            self.records_root_digest_algorithm,
            "records_root_digest_algorithm",
        )
        if records_root_sha256:
            records_root_sha256 = _normalize_sha256(records_root_sha256, "records_root_sha256")

        record_bindings = tuple(_clone_record_binding(row) for row in self.record_bindings)
        metadata_bindings = tuple(_clone_metadata_binding(row) for row in self.metadata_bindings)
        if record_bindings and len(record_bindings) != self.record_count:
            raise ValueError("record_count must match record_bindings length")

        object.__setattr__(self, "actual_start", start)
        object.__setattr__(self, "actual_end", end)
        object.__setattr__(self, "checksum_algorithm", "sha256")
        object.__setattr__(self, "checksum_sha256", checksum_sha256)
        object.__setattr__(self, "gaps", tuple(self.gaps))
        object.__setattr__(self, "source_provenance", source_provenance)
        object.__setattr__(self, "legal_source", legal_source)
        object.__setattr__(self, "payload_snapshot_sha256", payload_snapshot_sha256)
        object.__setattr__(self, "payload_digest_algorithm", payload_digest_algorithm)
        object.__setattr__(self, "payload_snapshot_path", payload_snapshot_path)
        object.__setattr__(self, "payload_records_path", payload_records_path)
        object.__setattr__(self, "record_digest_algorithm", record_digest_algorithm)
        object.__setattr__(self, "records_root_sha256", records_root_sha256)
        object.__setattr__(self, "records_root_digest_algorithm", records_root_digest_algorithm)
        object.__setattr__(self, "record_bindings", record_bindings)
        object.__setattr__(self, "metadata_bindings", metadata_bindings)


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


def _records_root(
    record_bindings: Iterable[RecordBinding],
    *,
    digest_algorithm: str = DIGEST_ALGORITHM_SHA256,
) -> str:
    payload = "\n".join(row.record_payload_sha256 for row in record_bindings).encode("ascii")
    return _digest_bytes(payload, digest_algorithm)


def _immutable_snapshot_root(payload_path: Path) -> Path:
    return payload_path.parent / "immutable_payloads" / "sha256"


def _write_snapshot_artifacts(
    *,
    snapshot: PayloadSnapshot,
    payload_path: Path,
    dataset_id: str,
    provider_id: str,
    provider_version: str,
    record_bindings: tuple[RecordBinding, ...],
) -> tuple[str, str]:
    root = _immutable_snapshot_root(payload_path)
    root.mkdir(parents=True, exist_ok=True)
    snapshot_path = root / f"{snapshot.payload_sha256}.bin"
    records_path = root / f"{snapshot.payload_sha256}.records.jsonl"
    envelope_path = root / f"{snapshot.payload_sha256}.json"

    snapshot_path.write_bytes(snapshot.raw_bytes)
    with records_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in record_bindings:
            handle.write(
                json.dumps(
                    {
                        "record_index": row.record_index,
                        "record_payload_sha256": row.record_payload_sha256,
                        "source_byte_start": row.source_byte_start,
                        "source_byte_end": row.source_byte_end,
                        "parsed_timestamp_utc": row.parsed_timestamp_utc.isoformat(),
                    },
                    sort_keys=True,
                )
            )
            handle.write("\n")

    envelope_path.write_text(
        json.dumps(
            {
                "dataset_id": dataset_id,
                "provider_id": provider_id,
                "provider_version": provider_version,
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "payload_size_bytes": snapshot.payload_size_bytes,
                "payload_sha256": snapshot.payload_sha256,
                "payload_digest_algorithm": snapshot.payload_digest_algorithm,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return str(snapshot_path), str(records_path)


PayloadRecordParser = Callable[[bytes], Iterable[tuple[datetime, int, int]]]


def _build_record_bindings(
    *,
    snapshot: PayloadSnapshot,
    payload_record_parser: PayloadRecordParser | None,
    digest_algorithm: str,
) -> tuple[RecordBinding, ...]:
    if payload_record_parser is None:
        return ()
    rows = list(payload_record_parser(snapshot.raw_bytes))
    bindings: list[RecordBinding] = []
    for idx, row in enumerate(rows):
        if len(row) != 3:
            raise ValueError("payload_record_parser rows must be (timestamp_utc, source_byte_start, source_byte_end)")
        ts_value, start_value, end_value = row
        start = int(start_value)
        end = int(end_value)
        if start < 0 or end <= start or end > snapshot.payload_size_bytes:
            raise ValueError("payload_record_parser returned invalid byte offsets")
        digest = _digest_bytes(snapshot.raw_bytes[start:end], digest_algorithm)
        bindings.append(
            RecordBinding(
                record_index=idx,
                record_payload_sha256=digest,
                source_byte_start=start,
                source_byte_end=end,
                parsed_timestamp_utc=_aware_utc(ts_value),
            )
        )
    return tuple(bindings)


def _bind_metadata_to_snapshot_identity(
    *,
    snapshot: PayloadSnapshot,
    record_bindings: tuple[RecordBinding, ...],
    metadata_bindings: Iterable[MetadataBinding] | None,
) -> tuple[MetadataBinding, ...]:
    metadata_rows = tuple(metadata_bindings or ())
    if not metadata_rows:
        return ()
    if not record_bindings:
        raise ValueError("metadata bindings require record bindings")

    by_index = {row.record_index: row for row in record_bindings}
    if len(by_index) != len(record_bindings):
        raise IntegrityCheckError("record_hash_mismatch: duplicate record bindings by index")

    bound_rows: list[MetadataBinding] = []
    for row in metadata_rows:
        canonical_record = by_index.get(row.record_index)
        if canonical_record is None:
            raise IntegrityCheckError("metadata_orphan_record: metadata row is not bound to parsed payload record")
        if row.timestamp_utc != canonical_record.parsed_timestamp_utc:
            raise IntegrityCheckError("metadata_timestamp_mismatch: metadata timestamp differs from bound record")
        if row.payload_sha256 != snapshot.payload_sha256:
            raise IntegrityCheckError("metadata_payload_mismatch: metadata references different payload snapshot")
        if row.record_payload_sha256 != canonical_record.record_payload_sha256:
            raise IntegrityCheckError("metadata_orphan_record: metadata row is not bound to parsed payload record")

        # Downstream identity always comes from immutable snapshot-derived record bindings,
        # never from transformed payload metadata fields.
        bound_rows.append(
            MetadataBinding(
                payload_sha256=snapshot.payload_sha256,
                record_index=canonical_record.record_index,
                record_payload_sha256=canonical_record.record_payload_sha256,
                timestamp_utc=canonical_record.parsed_timestamp_utc,
                is_gap_boundary=row.is_gap_boundary,
                gap_id=row.gap_id,
                availability_class=row.availability_class,
            )
        )

    return tuple(bound_rows)


def build_manifest(
    *,
    payload_path: str | Path,
    timestamps: Iterable[datetime],
    expected_interval: timedelta,
    dataset_id: str,
    provider_id: str,
    provider_version: str,
    data_class: DataClass,
    payload_timestamp_parser: Callable[[bytes], Iterable[datetime]] | None = None,
    payload_record_parser: PayloadRecordParser | None = None,
    metadata_bindings: Iterable[MetadataBinding] | None = None,
    source_provenance: str = "",
    legal_source: str = "",
    payload_digest_algorithm: str = DIGEST_ALGORITHM_SHA256,
    record_digest_algorithm: str = DIGEST_ALGORITHM_SHA256,
) -> DataManifest:
    """Build evidence from bytes that already exist locally; never downloads data."""
    path = Path(payload_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    # Parse-boundary invariant: capture immutable payload bytes once, then only use
    # snapshot identity (snapshot.raw_bytes + snapshot.payload_sha256) downstream.
    payload_digest_algorithm = _normalize_digest_algorithm(
        payload_digest_algorithm,
        "payload_digest_algorithm",
    )
    record_digest_algorithm = _normalize_digest_algorithm(
        record_digest_algorithm,
        "record_digest_algorithm",
    )
    snapshot = _capture_payload_snapshot(
        path.read_bytes(),
        digest_algorithm=payload_digest_algorithm,
    )
    rows = [_aware_utc(value) for value in timestamps]
    if not rows:
        raise ValueError("Cannot manifest empty observations")
    for previous, current in zip(rows, rows[1:]):
        if current <= previous:
            raise ValueError("timestamps must be strictly increasing")

    if payload_timestamp_parser is not None:
        parsed_rows = [_aware_utc(value) for value in payload_timestamp_parser(snapshot.raw_bytes)]
        if parsed_rows != rows:
            raise ValueError(
                "metadata timestamps must match timestamps parsed from payload bytes"
            )

    record_bindings = _build_record_bindings(
        snapshot=snapshot,
        payload_record_parser=payload_record_parser,
        digest_algorithm=record_digest_algorithm,
    )
    if record_bindings and [row.parsed_timestamp_utc for row in record_bindings] != rows:
        raise ValueError("record bindings must preserve the parsed timestamp sequence")

    metadata_rows = _bind_metadata_to_snapshot_identity(
        snapshot=snapshot,
        record_bindings=record_bindings,
        metadata_bindings=metadata_bindings,
    )

    snapshot_path, records_path = _write_snapshot_artifacts(
        snapshot=snapshot,
        payload_path=path,
        dataset_id=dataset_id,
        provider_id=provider_id,
        provider_version=provider_version,
        record_bindings=record_bindings,
    )

    seconds = int(expected_interval.total_seconds())
    gaps = _detect_gaps(rows, expected_interval)
    manifest = DataManifest(
        dataset_id=dataset_id,
        provider_id=provider_id,
        provider_version=provider_version,
        data_class=data_class,
        acquisition_status=AcquisitionStatus.DOWNLOADED,
        checksum_algorithm="sha256",
        checksum_sha256=snapshot.payload_sha256,
        payload_bytes=snapshot.payload_size_bytes,
        actual_start=rows[0],
        actual_end=rows[-1],
        record_count=len(rows),
        expected_interval_seconds=seconds,
        gaps=gaps,
        source_provenance=source_provenance,
        legal_source=legal_source,
        payload_snapshot_sha256=snapshot.payload_sha256,
        payload_digest_algorithm=payload_digest_algorithm,
        payload_snapshot_path=snapshot_path,
        payload_records_path=records_path,
        record_digest_algorithm=record_digest_algorithm,
        records_root_sha256=(
            _records_root(record_bindings, digest_algorithm=record_digest_algorithm)
            if record_bindings
            else ""
        ),
        records_root_digest_algorithm=record_digest_algorithm,
        record_bindings=record_bindings,
        metadata_bindings=metadata_rows,
    )

    # Fail closed at parse-time when metadata is provided: imported metadata is accepted
    # only if bound to the exact parsed byte snapshot.
    if metadata_rows:
        verify_manifest_bindings(manifest, metadata_bindings=metadata_rows)

    return manifest


def verify_manifest(payload_path: str | Path, manifest: DataManifest) -> bool:
    path = Path(payload_path)
    if not path.is_file():
        return False
    checksum = sha256_file(path)
    return (
        path.stat().st_size == manifest.payload_bytes
        and checksum == manifest.checksum_sha256
        and (
            not manifest.payload_snapshot_sha256
            or checksum == manifest.payload_snapshot_sha256
        )
    )


def _load_record_bindings_from_file(records_path: Path) -> tuple[RecordBinding, ...]:
    rows: list[RecordBinding] = []
    for raw_line in records_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            rows.append(
                RecordBinding(
                    record_index=int(payload["record_index"]),
                    record_payload_sha256=str(payload["record_payload_sha256"]),
                    source_byte_start=int(payload["source_byte_start"]),
                    source_byte_end=int(payload["source_byte_end"]),
                    parsed_timestamp_utc=datetime.fromisoformat(
                        str(payload["parsed_timestamp_utc"]).replace("Z", "+00:00")
                    ),
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise IntegrityCheckError(
                "record_hash_mismatch: malformed record binding file"
            ) from exc
    return tuple(rows)


def _gaps_signature(gaps: tuple[Gap, ...]) -> tuple[tuple[str, str, int], ...]:
    return tuple((gap.after.isoformat(), gap.before.isoformat(), gap.missing_intervals) for gap in gaps)


def verify_manifest_bindings(
    manifest: DataManifest,
    *,
    metadata_bindings: Iterable[MetadataBinding] | None = None,
) -> bool:
    """Verify immutable snapshot/record/metadata/provenance binding.

    Raises IntegrityCheckError with explicit failure tags when integrity checks fail.
    """
    if not manifest.payload_snapshot_path or not manifest.payload_records_path:
        raise IntegrityCheckError("missing_snapshot: immutable snapshot paths are required")
    if not manifest.payload_snapshot_sha256:
        raise IntegrityCheckError("missing_snapshot: payload_snapshot_sha256 is required")
    if not manifest.source_provenance or not manifest.legal_source:
        raise IntegrityCheckError("provenance_inconsistency: source_provenance/legal_source must both be present")

    snapshot_path = Path(manifest.payload_snapshot_path)
    records_path = Path(manifest.payload_records_path)
    if not snapshot_path.is_file() or not records_path.is_file():
        raise IntegrityCheckError("missing_snapshot: immutable payload artifacts are missing")

    payload_sha = _digest_bytes(
        snapshot_path.read_bytes(),
        manifest.payload_digest_algorithm,
    )
    if payload_sha != manifest.payload_snapshot_sha256:
        raise IntegrityCheckError("payload_hash_mismatch: snapshot bytes do not match payload_snapshot_sha256")
    if payload_sha != manifest.checksum_sha256:
        raise IntegrityCheckError("manifest_consistency_mismatch: checksum_sha256 differs from snapshot digest")

    record_rows = _load_record_bindings_from_file(records_path)
    if manifest.record_bindings and record_rows != manifest.record_bindings:
        raise IntegrityCheckError("record_hash_mismatch: manifest record bindings differ from snapshot binding file")

    snapshot_bytes = snapshot_path.read_bytes()
    for row in record_rows:
        if row.source_byte_end > len(snapshot_bytes):
            raise IntegrityCheckError("record_hash_mismatch: record byte range exceeds payload size")
        digest = _digest_bytes(
            snapshot_bytes[row.source_byte_start:row.source_byte_end],
            manifest.record_digest_algorithm,
        )
        if digest != row.record_payload_sha256:
            raise IntegrityCheckError("record_hash_mismatch: record digest does not match byte slice")

    calculated_root = (
        _records_root(record_rows, digest_algorithm=manifest.records_root_digest_algorithm)
        if record_rows
        else ""
    )
    if manifest.records_root_sha256 != calculated_root:
        raise IntegrityCheckError("records_root_mismatch: ordered record root digest mismatch")

    metadata_rows = tuple(metadata_bindings or manifest.metadata_bindings)
    if manifest.data_class == DataClass.REAL_OBSERVATION and not metadata_rows:
        raise IntegrityCheckError("metadata_missing_bindings: real observations require bound metadata")

    if metadata_rows:
        by_key = {
            (row.record_index, row.record_payload_sha256): row
            for row in record_rows
        }
        if len(by_key) != len(record_rows):
            raise IntegrityCheckError("record_hash_mismatch: duplicate record bindings by index/hash")

        for row in metadata_rows:
            if row.payload_sha256 != payload_sha:
                raise IntegrityCheckError("metadata_payload_mismatch: metadata references different payload snapshot")
            key = (row.record_index, row.record_payload_sha256)
            bound = by_key.get(key)
            if bound is None:
                raise IntegrityCheckError("metadata_orphan_record: metadata row is not bound to parsed payload record")
            if row.timestamp_utc != bound.parsed_timestamp_utc:
                raise IntegrityCheckError("metadata_timestamp_mismatch: metadata timestamp differs from bound record")

        ordered_metadata = sorted(metadata_rows, key=lambda item: item.record_index)
        timestamps = [row.timestamp_utc for row in ordered_metadata]
        for previous, current in zip(timestamps, timestamps[1:]):
            if current <= previous:
                raise IntegrityCheckError("metadata_timestamp_mismatch: metadata timestamps are not strictly increasing")
        recomputed_gaps = _detect_gaps(
            timestamps,
            timedelta(seconds=manifest.expected_interval_seconds),
        )
        if _gaps_signature(recomputed_gaps) != _gaps_signature(manifest.gaps):
            raise IntegrityCheckError("gap_mismatch: coverage gaps do not match bound metadata timestamps")

    return True


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
