"""Local Kian smoke tests for M15 bar helpers."""
import unittest
from datetime import datetime, timezone

from trading_lab.data.bars import Quote, assign_bar_start, build_m15_bars, m15_floor


class LocalKianBarsTests(unittest.TestCase):
    def test_rejects_naive(self):
        with self.assertRaises(ValueError):
            Quote(datetime(2026, 1, 1, 10, 0, 0), 1.0, 1.1)

    def test_rejects_crossed(self):
        with self.assertRaises(ValueError):
            Quote(datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc), 1.2, 1.1)

    def test_boundary_floor(self):
        ts = datetime(2026, 1, 1, 10, 15, 0, tzinfo=timezone.utc)
        self.assertEqual(m15_floor(ts), ts)
        self.assertEqual(assign_bar_start(ts), ts)

    def test_build_one_bar(self):
        q = [
            Quote(datetime(2026, 1, 1, 10, 0, 1, tzinfo=timezone.utc), 100.0, 100.2),
            Quote(datetime(2026, 1, 1, 10, 5, 0, tzinfo=timezone.utc), 100.1, 100.3),
        ]
        bars = build_m15_bars(q)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0]["ticks"], 2)


if __name__ == "__main__":
    unittest.main()
