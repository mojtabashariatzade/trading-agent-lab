"""Performance/contract tests use synthetic timestamps, not market history."""
import hashlib
import tempfile
import tracemalloc
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from trading_lab.data.imports import build_manifest, DataClass, verify_manifest

T0 = datetime(2020, 1, 1, tzinfo=timezone.utc)


class StreamingManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.bin"
        self.path.write_bytes(b"SYNTHETIC_TEST_ONLY\n")

    def build(self, rows, interval=timedelta(minutes=1)):
        return build_manifest(payload_path=self.path, timestamps=rows, expected_interval=interval,
            dataset_id="SYNTHETIC_TEST_ONLY", provider_id="unit-test", provider_version="1",
            data_class=DataClass.TEST_FIXTURE)

    def test_single_pass_generator_and_coverage(self):
        class Once:
            used = False
            def __iter__(self):
                if self.used:
                    raise AssertionError("timestamps were iterated twice")
                self.used = True
                return (T0 + timedelta(minutes=i) for i in (0, 1, 4, 5))
        result = self.build(Once())
        self.assertEqual(result.record_count, 4)
        self.assertEqual(result.actual_start, T0)
        self.assertEqual(result.actual_end, T0 + timedelta(minutes=5))
        self.assertEqual(result.gaps[0].missing_intervals, 2)
        self.assertEqual(result.checksum_sha256, hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertTrue(verify_manifest(self.path, result))

    def test_empty_duplicate_naive_and_bad_interval_rejected(self):
        cases = [([], timedelta(minutes=1)), ([T0, T0], timedelta(minutes=1)),
                 ([datetime(2020,1,1)], timedelta(minutes=1)),
                 ([T0], timedelta(0)), ([T0], timedelta(seconds=.5))]
        for rows, interval in cases:
            with self.subTest(rows=rows, interval=interval), self.assertRaises(ValueError):
                self.build(iter(rows), interval)

    def test_timezone_normalization_and_generator_list_parity(self):
        rows = [T0.astimezone(timezone(timedelta(hours=3))) + timedelta(minutes=i)
                for i in range(20)]
        self.assertEqual(self.build(rows), self.build(iter(rows)))
        self.assertEqual(self.build(iter(rows)).actual_start, T0)

    def test_generated_timestamp_storage_does_not_grow_with_record_count(self):
        # Exclude the independent, bounded 1 MiB payload-hashing buffer.
        with patch("trading_lab.data.imports.sha256_file", return_value="0"*64):
            tracemalloc.start()
            try:
                result = self.build(T0 + timedelta(minutes=i) for i in range(50000))
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
        self.assertEqual(result.record_count, 50000)
        self.assertLess(peak, 250000, f"timestamp storage grew to {peak} bytes")


if __name__ == "__main__":
    unittest.main()
