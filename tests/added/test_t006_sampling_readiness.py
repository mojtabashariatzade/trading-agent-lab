"""Acceptance tests for T006 historical-data sampling readiness."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_lab.data import (
    AcquisitionStatus,
    DataClass,
    DukascopySamplingAdapter,
    IntegrityCheckError,
    MetadataBinding,
    StorageLayout,
    TermsStatus,
    build_manifest,
    original_macro_value,
    verify_manifest,
    verify_manifest_bindings,
)
from trading_lab.data.imports import _capture_payload_snapshot
from trading_lab.fundamentals import EconomicRelease, TimePoint, TimestampPrecision


UTC = timezone.utc
T0 = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)


class T006SamplingReadinessTests(unittest.TestCase):
    @staticmethod
    def _parse_iso_csv_timestamps(payload: bytes) -> list[datetime]:
        lines = payload.decode("utf-8").strip().splitlines()
        if not lines:
            return []
        rows: list[datetime] = []
        for line in lines[1:]:
            if not line.strip():
                continue
            ts = line.split(",", 1)[0].strip()
            rows.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
        return rows

    @staticmethod
    def _parse_iso_csv_record_bindings(payload: bytes) -> list[tuple[datetime, int, int]]:
        lines = payload.splitlines(keepends=True)
        if not lines:
            return []
        rows: list[tuple[datetime, int, int]] = []
        offset = 0
        for index, line in enumerate(lines):
            start = offset
            end = offset + len(line)
            offset = end
            if index == 0 or not line.strip():
                continue
            timestamp_text = line.decode("utf-8").split(",", 1)[0].strip()
            rows.append((datetime.fromisoformat(timestamp_text.replace("Z", "+00:00")), start, end))
        return rows

    @staticmethod
    def _build_metadata_bindings(payload: bytes) -> list[MetadataBinding]:
        payload_sha = hashlib.sha256(payload).hexdigest()
        parsed_rows = T006SamplingReadinessTests._parse_iso_csv_record_bindings(payload)
        bindings: list[MetadataBinding] = []
        for idx, (timestamp_utc, start, end) in enumerate(parsed_rows):
            bindings.append(
                MetadataBinding(
                    payload_sha256=payload_sha,
                    record_index=idx,
                    record_payload_sha256=hashlib.sha256(payload[start:end]).hexdigest(),
                    timestamp_utc=timestamp_utc,
                    is_gap_boundary=False,
                    gap_id="",
                    availability_class="REAL_OBSERVATION",
                )
            )
        return bindings

    def test_manifest_records_provider_version_coverage_gaps_and_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            payload = (
                b"ts,bid,ask\n"
                b"2026-01-05T10:00:00Z,100.0,100.2\n"
                b"2026-01-05T10:01:00Z,100.1,100.3\n"
                b"2026-01-05T10:03:00Z,100.4,100.6\n"
            )
            path.write_bytes(payload)
            timestamps = [
                T0,
                T0 + timedelta(minutes=1),
                T0 + timedelta(minutes=3),
            ]
            manifest = build_manifest(
                payload_path=path,
                timestamps=timestamps,
                expected_interval=timedelta(minutes=1),
                dataset_id="gbpjpy-sample-001",
                provider_id="dukascopy",
                provider_version="readiness-1",
                data_class=DataClass.REAL_OBSERVATION,
                payload_timestamp_parser=self._parse_iso_csv_timestamps,
                payload_record_parser=self._parse_iso_csv_record_bindings,
                metadata_bindings=self._build_metadata_bindings(payload),
                source_provenance="dukascopy:sample:gbpjpy:m1",
                legal_source="terms-reviewed:ticket-123",
            )

            self.assertEqual(manifest.provider_id, "dukascopy")
            self.assertEqual(manifest.provider_version, "readiness-1")
            self.assertEqual(manifest.actual_start, timestamps[0])
            self.assertEqual(manifest.actual_end, timestamps[-1])
            self.assertEqual(manifest.record_count, 3)
            self.assertEqual(len(manifest.gaps), 1)
            self.assertEqual(manifest.gaps[0].missing_intervals, 1)
            self.assertEqual(manifest.source_provenance, "dukascopy:sample:gbpjpy:m1")
            self.assertEqual(manifest.legal_source, "terms-reviewed:ticket-123")
            self.assertEqual(manifest.payload_snapshot_sha256, manifest.checksum_sha256)
            self.assertEqual(manifest.payload_digest_algorithm, "sha256")
            self.assertEqual(manifest.record_digest_algorithm, "sha256")
            self.assertEqual(manifest.records_root_digest_algorithm, "sha256")
            self.assertTrue(manifest.payload_snapshot_path.endswith(".bin"))
            self.assertTrue(manifest.payload_records_path.endswith(".records.jsonl"))
            self.assertEqual(len(manifest.metadata_bindings), 3)
            self.assertEqual(len(manifest.record_bindings), 3)
            self.assertEqual(manifest.record_bindings[0].record_index, 0)
            self.assertEqual(manifest.record_bindings[2].record_index, 2)
            self.assertEqual(
                manifest.checksum_sha256,
                hashlib.sha256(payload).hexdigest(),
            )
            self.assertTrue(verify_manifest(path, manifest))
            self.assertTrue(verify_manifest_bindings(manifest, metadata_bindings=manifest.metadata_bindings))

    def test_manifest_rejects_metadata_timestamps_if_payload_parser_disagrees(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            path.write_bytes(
                b"ts,bid,ask\n"
                b"2026-01-05T10:00:00Z,100.0,100.2\n"
                b"2026-01-05T10:01:00Z,100.1,100.3\n"
            )
            with self.assertRaises(ValueError):
                build_manifest(
                    payload_path=path,
                    timestamps=[T0, T0 + timedelta(minutes=2)],
                    expected_interval=timedelta(minutes=1),
                    dataset_id="bad-binding",
                    provider_id="dukascopy",
                    provider_version="readiness-1",
                    data_class=DataClass.REAL_OBSERVATION,
                    payload_timestamp_parser=self._parse_iso_csv_timestamps,
                    source_provenance="dukascopy:sample:gbpjpy:m1",
                    legal_source="terms-reviewed:ticket-123",
                )

    def test_parse_boundary_snapshot_digest_stays_stable_for_identical_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stable.csv"
            payload = (
                b"ts,bid,ask\n"
                b"2026-01-05T10:00:00Z,100.0,100.2\n"
                b"2026-01-05T10:01:00Z,100.1,100.3\n"
            )
            expected_sha = hashlib.sha256(payload).hexdigest()
            path.write_bytes(payload)

            manifest_one = build_manifest(
                payload_path=path,
                timestamps=[T0, T0 + timedelta(minutes=1)],
                expected_interval=timedelta(minutes=1),
                dataset_id="stable-1",
                provider_id="dukascopy",
                provider_version="readiness-1",
                data_class=DataClass.REAL_OBSERVATION,
                payload_timestamp_parser=self._parse_iso_csv_timestamps,
                payload_record_parser=self._parse_iso_csv_record_bindings,
                metadata_bindings=self._build_metadata_bindings(payload),
                source_provenance="dukascopy:sample:gbpjpy:m1",
                legal_source="terms-reviewed:ticket-123",
            )

            # Mutating the source file later must not change already-bound snapshot identity.
            path.write_bytes(payload + b"#mutated")
            self.assertEqual(manifest_one.payload_snapshot_sha256, expected_sha)
            self.assertEqual(Path(manifest_one.payload_snapshot_path).read_bytes(), payload)

            # Re-importing exact same bytes must reproduce the same stable identity digest.
            path.write_bytes(payload)
            manifest_two = build_manifest(
                payload_path=path,
                timestamps=[T0, T0 + timedelta(minutes=1)],
                expected_interval=timedelta(minutes=1),
                dataset_id="stable-2",
                provider_id="dukascopy",
                provider_version="readiness-1",
                data_class=DataClass.REAL_OBSERVATION,
                payload_timestamp_parser=self._parse_iso_csv_timestamps,
                payload_record_parser=self._parse_iso_csv_record_bindings,
                metadata_bindings=self._build_metadata_bindings(payload),
                source_provenance="dukascopy:sample:gbpjpy:m1",
                legal_source="terms-reviewed:ticket-123",
            )

            self.assertEqual(manifest_two.payload_snapshot_sha256, expected_sha)
            self.assertEqual(manifest_two.payload_snapshot_sha256, manifest_one.payload_snapshot_sha256)

    def test_capture_snapshot_detaches_from_mutable_source_bytes(self):
        mutable_payload = bytearray(b"row-1\nrow-2\n")
        snapshot = _capture_payload_snapshot(mutable_payload)
        mutable_payload[:] = b"tampered"

        self.assertEqual(snapshot.raw_bytes, b"row-1\nrow-2\n")
        self.assertEqual(snapshot.payload_sha256, hashlib.sha256(b"row-1\nrow-2\n").hexdigest())
        self.assertEqual(snapshot.payload_digest_algorithm, "sha256")

    def test_manifest_metadata_identity_detaches_from_mutable_input_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            payload = (
                b"ts,bid,ask\n"
                b"2026-01-05T10:00:00Z,100.0,100.2\n"
                b"2026-01-05T10:01:00Z,100.1,100.3\n"
            )
            path.write_bytes(payload)
            metadata_rows = self._build_metadata_bindings(payload)
            manifest = build_manifest(
                payload_path=path,
                timestamps=[T0, T0 + timedelta(minutes=1)],
                expected_interval=timedelta(minutes=1),
                dataset_id="immutable-metadata-binding",
                provider_id="dukascopy",
                provider_version="readiness-1",
                data_class=DataClass.REAL_OBSERVATION,
                payload_timestamp_parser=self._parse_iso_csv_timestamps,
                payload_record_parser=self._parse_iso_csv_record_bindings,
                metadata_bindings=metadata_rows,
                source_provenance="dukascopy:sample:gbpjpy:m1",
                legal_source="terms-reviewed:ticket-123",
            )

            original_manifest_identity = (
                manifest.metadata_bindings[0].payload_sha256,
                manifest.metadata_bindings[0].record_payload_sha256,
                manifest.metadata_bindings[0].timestamp_utc,
            )

            object.__setattr__(metadata_rows[0], "payload_sha256", hashlib.sha256(b"tampered-payload").hexdigest())
            object.__setattr__(metadata_rows[0], "record_payload_sha256", hashlib.sha256(b"tampered-row").hexdigest())
            object.__setattr__(metadata_rows[0], "timestamp_utc", T0 + timedelta(minutes=99))

            self.assertEqual(
                (
                    manifest.metadata_bindings[0].payload_sha256,
                    manifest.metadata_bindings[0].record_payload_sha256,
                    manifest.metadata_bindings[0].timestamp_utc,
                ),
                original_manifest_identity,
            )
            self.assertEqual(manifest.metadata_bindings[0].payload_sha256, manifest.payload_snapshot_sha256)
            self.assertEqual(
                manifest.metadata_bindings[0].record_payload_sha256,
                manifest.record_bindings[0].record_payload_sha256,
            )

    def test_manifest_rejects_unsupported_digest_algorithm(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            path.write_bytes(b"ts,bid,ask\n2026-01-05T10:00:00Z,100.0,100.2\n")
            with self.assertRaisesRegex(ValueError, "Unsupported payload_digest_algorithm"):
                build_manifest(
                    payload_path=path,
                    timestamps=[T0],
                    expected_interval=timedelta(minutes=1),
                    dataset_id="unsupported-digest",
                    provider_id="dukascopy",
                    provider_version="readiness-1",
                    data_class=DataClass.REAL_OBSERVATION,
                    source_provenance="dukascopy:sample:gbpjpy:m1",
                    legal_source="terms-reviewed:ticket-123",
                    payload_digest_algorithm="sha1",
                )

    def test_checksum_detects_payload_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.bin"
            path.write_bytes(b"original")
            manifest = build_manifest(
                payload_path=path,
                timestamps=[T0, T0 + timedelta(minutes=1)],
                expected_interval=timedelta(minutes=1),
                dataset_id="checksum",
                provider_id="test-provider",
                provider_version="v1",
                data_class=DataClass.TEST_FIXTURE,
                source_provenance="fixture:unit",
                legal_source="internal:test-fixture",
            )
            self.assertTrue(verify_manifest(path, manifest))
            path.write_bytes(b"changed")
            self.assertFalse(verify_manifest(path, manifest))

    def test_binding_verification_rejects_payload_and_record_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            payload = (
                b"ts,bid,ask\n"
                b"2026-01-05T10:00:00Z,100.0,100.2\n"
                b"2026-01-05T10:01:00Z,100.1,100.3\n"
            )
            path.write_bytes(payload)
            manifest = build_manifest(
                payload_path=path,
                timestamps=[T0, T0 + timedelta(minutes=1)],
                expected_interval=timedelta(minutes=1),
                dataset_id="tamper-check",
                provider_id="dukascopy",
                provider_version="readiness-1",
                data_class=DataClass.REAL_OBSERVATION,
                payload_timestamp_parser=self._parse_iso_csv_timestamps,
                payload_record_parser=self._parse_iso_csv_record_bindings,
                metadata_bindings=self._build_metadata_bindings(payload),
                source_provenance="dukascopy:sample:gbpjpy:m1",
                legal_source="terms-reviewed:ticket-123",
            )

            snapshot_path = Path(manifest.payload_snapshot_path)
            snapshot_path.write_bytes(snapshot_path.read_bytes() + b"x")
            with self.assertRaisesRegex(IntegrityCheckError, "payload_hash_mismatch"):
                verify_manifest_bindings(manifest, metadata_bindings=manifest.metadata_bindings)

            path.write_bytes(payload)
            manifest = build_manifest(
                payload_path=path,
                timestamps=[T0, T0 + timedelta(minutes=1)],
                expected_interval=timedelta(minutes=1),
                dataset_id="tamper-check-2",
                provider_id="dukascopy",
                provider_version="readiness-1",
                data_class=DataClass.REAL_OBSERVATION,
                payload_timestamp_parser=self._parse_iso_csv_timestamps,
                payload_record_parser=self._parse_iso_csv_record_bindings,
                metadata_bindings=self._build_metadata_bindings(payload),
                source_provenance="dukascopy:sample:gbpjpy:m1",
                legal_source="terms-reviewed:ticket-123",
            )
            records_path = Path(manifest.payload_records_path)
            lines = records_path.read_text(encoding="utf-8").splitlines()
            self.assertTrue(lines)
            first_row = json.loads(lines[0])
            first_row["record_payload_sha256"] = hashlib.sha256(b"tampered-row").hexdigest()
            lines[0] = json.dumps(first_row, sort_keys=True)
            records_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(IntegrityCheckError, "record_hash_mismatch"):
                verify_manifest_bindings(manifest, metadata_bindings=manifest.metadata_bindings)

    def test_binding_verification_rejects_orphan_metadata_and_gap_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            payload = (
                b"ts,bid,ask\n"
                b"2026-01-05T10:00:00Z,100.0,100.2\n"
                b"2026-01-05T10:01:00Z,100.1,100.3\n"
                b"2026-01-05T10:03:00Z,100.4,100.6\n"
            )
            path.write_bytes(payload)
            bindings = self._build_metadata_bindings(payload)
            manifest = build_manifest(
                payload_path=path,
                timestamps=[T0, T0 + timedelta(minutes=1), T0 + timedelta(minutes=3)],
                expected_interval=timedelta(minutes=1),
                dataset_id="metadata-check",
                provider_id="dukascopy",
                provider_version="readiness-1",
                data_class=DataClass.REAL_OBSERVATION,
                payload_timestamp_parser=self._parse_iso_csv_timestamps,
                payload_record_parser=self._parse_iso_csv_record_bindings,
                metadata_bindings=bindings,
                source_provenance="dukascopy:sample:gbpjpy:m1",
                legal_source="terms-reviewed:ticket-123",
            )

            orphan = MetadataBinding(
                payload_sha256=manifest.payload_snapshot_sha256,
                record_index=99,
                record_payload_sha256=hashlib.sha256(b"orphan").hexdigest(),
                timestamp_utc=T0 + timedelta(minutes=99),
                is_gap_boundary=False,
                gap_id="",
                availability_class="REAL_OBSERVATION",
            )
            with self.assertRaisesRegex(IntegrityCheckError, "metadata_orphan_record"):
                verify_manifest_bindings(manifest, metadata_bindings=[*bindings, orphan])

            tampered_gap_rows = [row for row in bindings if row.record_index != 1]
            with self.assertRaisesRegex(IntegrityCheckError, "gap_mismatch"):
                verify_manifest_bindings(manifest, metadata_bindings=tampered_gap_rows)

    def test_fixture_and_real_storage_are_separate(self):
        layout = StorageLayout(Path("research-data"))
        fixture = layout.destination(DataClass.TEST_FIXTURE, "gbpjpy/sample.csv")
        real = layout.destination(DataClass.REAL_OBSERVATION, "gbpjpy/sample.csv")
        self.assertEqual(fixture, Path("research-data/fixtures/gbpjpy/sample.csv"))
        self.assertEqual(real, Path("research-data/real_observations/gbpjpy/sample.csv"))
        self.assertNotEqual(fixture.parent.parent, real.parent.parent)
        with self.assertRaises(ValueError):
            layout.destination(DataClass.REAL_OBSERVATION, "../escape.csv")

    def test_dukascopy_readiness_is_explicitly_unverified_and_not_downloaded(self):
        adapter = DukascopySamplingAdapter()
        plan = adapter.plan(
            instrument="GBPJPY",
            requested_start=T0,
            requested_end=T0 + timedelta(hours=1),
        )
        report = adapter.readiness_report(plan)
        self.assertEqual(plan.terms_status, TermsStatus.UNVERIFIED)
        self.assertFalse(plan.network_enabled)
        self.assertEqual(report.status, AcquisitionStatus.UNVERIFIED)
        self.assertFalse(report.downloaded)
        self.assertIsNone(report.manifest)
        self.assertIn("No sample downloaded", report.note)

    def test_downloaded_claim_requires_verified_terms_and_real_manifest(self):
        adapter = DukascopySamplingAdapter()
        unverified = adapter.plan(
            instrument="GBPJPY",
            requested_start=T0,
            requested_end=T0 + timedelta(hours=1),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            real_payload = (
                b"ts,bid,ask\n"
                b"2026-01-05T10:00:00Z,100.0,100.2\n"
                b"2026-01-05T10:01:00Z,100.1,100.3\n"
            )
            path.write_bytes(real_payload)
            real_manifest = build_manifest(
                payload_path=path,
                timestamps=[T0, T0 + timedelta(minutes=1)],
                expected_interval=timedelta(minutes=1),
                dataset_id="real-sample",
                provider_id="dukascopy",
                provider_version="readiness-1",
                data_class=DataClass.REAL_OBSERVATION,
                payload_timestamp_parser=self._parse_iso_csv_timestamps,
                payload_record_parser=self._parse_iso_csv_record_bindings,
                metadata_bindings=self._build_metadata_bindings(real_payload),
                source_provenance="dukascopy:sample:gbpjpy:m1",
                legal_source="terms-reviewed:ticket-123",
            )
            with self.assertRaises(PermissionError):
                adapter.downloaded_report(unverified, real_manifest)

            allowed = adapter.plan(
                instrument="GBPJPY",
                requested_start=T0,
                requested_end=T0 + timedelta(hours=1),
                terms_status=TermsStatus.VERIFIED_ALLOWED,
            )
            report = adapter.downloaded_report(allowed, real_manifest)
            self.assertTrue(report.downloaded)
            self.assertEqual(report.status, AcquisitionStatus.DOWNLOADED)
            self.assertIs(report.manifest, real_manifest)

            fixture_manifest = build_manifest(
                payload_path=path,
                timestamps=[T0, T0 + timedelta(minutes=1)],
                expected_interval=timedelta(minutes=1),
                dataset_id="fixture-sample",
                provider_id="dukascopy",
                provider_version="readiness-1",
                data_class=DataClass.TEST_FIXTURE,
                source_provenance="fixture:unit",
                legal_source="internal:test-fixture",
            )
            with self.assertRaises(ValueError):
                adapter.downloaded_report(allowed, fixture_manifest)

    def test_downloaded_report_requires_legal_and_source_provenance(self):
        adapter = DukascopySamplingAdapter()
        allowed = adapter.plan(
            instrument="GBPJPY",
            requested_start=T0,
            requested_end=T0 + timedelta(hours=1),
            terms_status=TermsStatus.VERIFIED_ALLOWED,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            path.write_bytes(b"sample")
            manifest_missing_provenance = build_manifest(
                payload_path=path,
                timestamps=[T0, T0 + timedelta(minutes=1)],
                expected_interval=timedelta(minutes=1),
                dataset_id="real-sample",
                provider_id="dukascopy",
                provider_version="readiness-1",
                data_class=DataClass.REAL_OBSERVATION,
            )
            with self.assertRaises(ValueError):
                adapter.downloaded_report(allowed, manifest_missing_provenance)

    def test_original_macro_value_never_substitutes_revision(self):
        release = EconomicRelease(
            release_id="macro-1",
            indicator="GDP",
            jurisdiction="UK",
            event_period="2026-Q2",
            scheduled_at=TimePoint(T0, TimestampPrecision.MINUTE),
            published_at=TimePoint(T0 + timedelta(minutes=1), TimestampPrecision.MINUTE),
            observed_at=TimePoint(T0 + timedelta(minutes=2), TimestampPrecision.MINUTE),
            available_at=TimePoint(T0 + timedelta(minutes=3), TimestampPrecision.MINUTE),
            first_actual=1.2,
            pre_release_forecast=1.1,
            pre_release_forecast_observed_at=TimePoint(T0 - timedelta(minutes=30), TimestampPrecision.MINUTE),
            pre_release_forecast_source_id="licensed_forecast_provider",
            pre_release_forecast_source_version="forecast-v1",
            previous_as_known=1.0,
            revision=1.8,
            source_id="ons",
            source_version="v1",
            revision_seq=1,
        )
        self.assertEqual(original_macro_value(release), 1.2)
        self.assertNotEqual(original_macro_value(release), release.revision)

    def test_missing_first_actual_stays_missing_even_if_revision_exists(self):
        release = EconomicRelease(
            release_id="macro-2",
            indicator="GDP",
            jurisdiction="UK",
            event_period="2026-Q2",
            scheduled_at=TimePoint(T0, TimestampPrecision.MINUTE),
            published_at=TimePoint(T0 + timedelta(minutes=1), TimestampPrecision.MINUTE),
            observed_at=TimePoint(T0 + timedelta(minutes=2), TimestampPrecision.MINUTE),
            available_at=TimePoint(T0 + timedelta(minutes=3), TimestampPrecision.MINUTE),
            first_actual=None,
            pre_release_forecast=1.1,
            pre_release_forecast_observed_at=TimePoint(T0 - timedelta(minutes=30), TimestampPrecision.MINUTE),
            pre_release_forecast_source_id="licensed_forecast_provider",
            pre_release_forecast_source_version="forecast-v1",
            previous_as_known=1.0,
            revision=1.8,
            source_id="ons",
            source_version="v1",
            revision_seq=1,
        )
        self.assertIsNone(original_macro_value(release))

    def test_original_macro_value_rejects_legacy_invalid_forecast_provenance(self):
        release = EconomicRelease(
            release_id="macro-legacy-invalid",
            indicator="GDP",
            jurisdiction="UK",
            event_period="2026-Q2",
            scheduled_at=TimePoint(T0, TimestampPrecision.MINUTE),
            published_at=TimePoint(T0 + timedelta(minutes=1), TimestampPrecision.MINUTE),
            observed_at=TimePoint(T0 + timedelta(minutes=2), TimestampPrecision.MINUTE),
            available_at=TimePoint(T0 + timedelta(minutes=3), TimestampPrecision.MINUTE),
            first_actual=1.2,
            pre_release_forecast=1.1,
            pre_release_forecast_observed_at=TimePoint(T0 - timedelta(minutes=30), TimestampPrecision.MINUTE),
            pre_release_forecast_source_id="licensed_forecast_provider",
            pre_release_forecast_source_version="forecast-v1",
            previous_as_known=1.0,
            revision=1.8,
            source_id="ons",
            source_version="v1",
            revision_seq=1,
        )
        object.__setattr__(release, "pre_release_forecast_source_id", "unknown_forecast_source")
        with self.assertRaisesRegex(
            ValueError,
            "pre_release_forecast_source_id unknown_forecast_source is not in source registry",
        ):
            original_macro_value(release)

    def test_manifest_rejects_unsorted_or_naive_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample"
            path.write_bytes(b"x")
            with self.assertRaises(ValueError):
                build_manifest(
                    payload_path=path,
                    timestamps=[T0 + timedelta(minutes=1), T0],
                    expected_interval=timedelta(minutes=1),
                    dataset_id="bad-order",
                    provider_id="provider",
                    provider_version="v1",
                    data_class=DataClass.TEST_FIXTURE,
                    source_provenance="fixture:unit",
                    legal_source="internal:test-fixture",
                )
            with self.assertRaises(ValueError):
                build_manifest(
                    payload_path=path,
                    timestamps=[datetime(2026, 1, 5, 10, 0)],
                    expected_interval=timedelta(minutes=1),
                    dataset_id="naive",
                    provider_id="provider",
                    provider_version="v1",
                    data_class=DataClass.TEST_FIXTURE,
                    source_provenance="fixture:unit",
                    legal_source="internal:test-fixture",
                )


if __name__ == "__main__":
    unittest.main()
