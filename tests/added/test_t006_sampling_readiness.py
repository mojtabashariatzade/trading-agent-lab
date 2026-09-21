"""Acceptance tests for T006 historical-data sampling readiness."""
import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_lab.data import (
    AcquisitionStatus,
    DataClass,
    DukascopySamplingAdapter,
    StorageLayout,
    TermsStatus,
    build_manifest,
    original_macro_value,
    verify_manifest,
)
from trading_lab.fundamentals import EconomicRelease, TimePoint, TimestampPrecision


UTC = timezone.utc
T0 = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)


class T006SamplingReadinessTests(unittest.TestCase):
    def test_manifest_records_provider_version_coverage_gaps_and_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            payload = b"ts,bid,ask\n1,100.0,100.2\n"
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
            )

            self.assertEqual(manifest.provider_id, "dukascopy")
            self.assertEqual(manifest.provider_version, "readiness-1")
            self.assertEqual(manifest.actual_start, timestamps[0])
            self.assertEqual(manifest.actual_end, timestamps[-1])
            self.assertEqual(manifest.record_count, 3)
            self.assertEqual(len(manifest.gaps), 1)
            self.assertEqual(manifest.gaps[0].missing_intervals, 1)
            self.assertEqual(
                manifest.checksum_sha256,
                hashlib.sha256(payload).hexdigest(),
            )
            self.assertTrue(verify_manifest(path, manifest))

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
            )
            self.assertTrue(verify_manifest(path, manifest))
            path.write_bytes(b"changed")
            self.assertFalse(verify_manifest(path, manifest))

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
            path.write_bytes(b"sample")
            real_manifest = build_manifest(
                payload_path=path,
                timestamps=[T0, T0 + timedelta(minutes=1)],
                expected_interval=timedelta(minutes=1),
                dataset_id="real-sample",
                provider_id="dukascopy",
                provider_version="readiness-1",
                data_class=DataClass.REAL_OBSERVATION,
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
            )
            with self.assertRaises(ValueError):
                adapter.downloaded_report(allowed, fixture_manifest)

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
            previous_as_known=1.0,
            revision=1.8,
            source_id="ons",
            source_version="v1",
            revision_seq=1,
        )
        self.assertIsNone(original_macro_value(release))

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
                )


if __name__ == "__main__":
    unittest.main()
