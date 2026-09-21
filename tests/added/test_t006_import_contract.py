"""Acceptance tests for T006 local historical-data sampling readiness."""

import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from trading_lab.data.import_contract import (
    ArtifactManifest,
    CoverageGap,
    MacroReleaseRecord,
    SamplingReport,
    SamplingState,
    StorageKind,
    build_local_manifest,
    require_original_release,
    verify_local_artifact,
)


UTC = timezone.utc


class HistoricalImportContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "fixtures").mkdir()
        (self.root / "real-observations").mkdir()
        self.sample = self.root / "real-observations" / "gbpjpy.csv"
        self.payload = b"at,bid,ask\n2026-01-01T10:00:00Z,190.0,190.1\n"
        self.sample.write_bytes(self.payload)
        self.start = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
        self.end = datetime(2026, 1, 1, 10, 30, tzinfo=UTC)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self) -> ArtifactManifest:
        gap = CoverageGap(
            datetime(2026, 1, 1, 10, 15, tzinfo=UTC),
            self.end,
            "provider returned no observations",
        )
        return build_local_manifest(
            self.sample,
            storage_root=self.root,
            provider="Dukascopy",
            provider_version="documented-format-v1",
            storage_kind=StorageKind.REAL_OBSERVATION,
            coverage_start_utc=self.start,
            coverage_end_utc=self.end,
            gaps=(gap,),
            record_count=1,
        )

    def test_manifest_records_exact_provenance_coverage_gaps_and_checksum(self):
        manifest = self.build()
        self.assertEqual(manifest.provider, "Dukascopy")
        self.assertEqual(manifest.storage_path, "real-observations/gbpjpy.csv")
        self.assertEqual(manifest.sha256_hex, hashlib.sha256(self.payload).hexdigest())
        self.assertEqual(manifest.gaps[0].start_utc.minute, 15)
        self.assertTrue(verify_local_artifact(self.sample, storage_root=self.root, manifest=manifest))
        self.assertIn('"record_count":1', manifest.to_json())

    def test_checksum_detects_tampering(self):
        manifest = self.build()
        self.sample.write_bytes(self.payload + b"tampered")
        self.assertFalse(verify_local_artifact(self.sample, storage_root=self.root, manifest=manifest))

    def test_real_and_fixture_storage_cannot_be_mislabeled(self):
        fixture = self.root / "fixtures" / "case.csv"
        fixture.write_text("synthetic\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "storage_path does not match"):
            build_local_manifest(
                fixture,
                storage_root=self.root,
                provider="unit-test",
                provider_version="v1",
                storage_kind=StorageKind.REAL_OBSERVATION,
                coverage_start_utc=self.start,
                coverage_end_utc=self.end,
                record_count=1,
            )

    def test_downloaded_and_unverified_reports_are_distinct(self):
        unverified = SamplingReport(
            provider="Dukascopy",
            provider_version="documented-format-v1",
            state=SamplingState.UNVERIFIED,
            terms_checked_at_utc=None,
            terms_allow_automated_sample=None,
            manifest=None,
            note="No download attempted; provider permission remains unverified.",
        )
        self.assertIs(unverified.state, SamplingState.UNVERIFIED)
        with self.assertRaisesRegex(ValueError, "terms approval"):
            SamplingReport(
                provider="Dukascopy",
                provider_version="documented-format-v1",
                state=SamplingState.DOWNLOADED,
                terms_checked_at_utc=None,
                terms_allow_automated_sample=None,
                manifest=self.build(),
                note="invalid downloaded claim",
            )

    def test_string_state_cannot_bypass_download_evidence_gate(self):
        with self.assertRaisesRegex(ValueError, "state must be a SamplingState"):
            SamplingReport(
                provider="Dukascopy",
                provider_version="documented-format-v1",
                state="downloaded",  # type: ignore[arg-type]
                terms_checked_at_utc=None,
                terms_allow_automated_sample=None,
                manifest=None,
                note="must not be accepted as a downloaded claim",
            )

    def test_naive_coverage_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware UTC"):
            build_local_manifest(
                self.sample,
                storage_root=self.root,
                provider="Dukascopy",
                provider_version="documented-format-v1",
                storage_kind=StorageKind.REAL_OBSERVATION,
                coverage_start_utc=datetime(2026, 1, 1, 10, 0),
                coverage_end_utc=self.end,
                record_count=1,
            )

    def test_revision_never_substitutes_for_missing_original(self):
        missing = MacroReleaseRecord("uk-cpi", None, None, revisions=(2.1,))
        with self.assertRaisesRegex(ValueError, "revision substitution is forbidden"):
            require_original_release(missing)
        original = MacroReleaseRecord("uk-cpi", 2.0, self.start, revisions=(2.1,))
        self.assertEqual(require_original_release(original), 2.0)


if __name__ == "__main__":
    unittest.main()
