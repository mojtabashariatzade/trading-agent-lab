"""Acceptance tests for T001 causal M15 bars and Wilder ATR."""
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from trading_lab.data.bars import Quote, atr14, build_m15_bars, wilder_atr


UTC = timezone.utc


def q(minute: int, second: int, bid: float, ask: float) -> Quote:
    return Quote(datetime(2026, 1, 1, 10, minute, second, tzinfo=UTC), bid, ask)


def synthetic_bars(count: int) -> list[dict]:
    bars = []
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    close = 100.0
    for i in range(count):
        high = close + 1.0 + (i % 3) * 0.1
        low = close - 0.8 - (i % 2) * 0.1
        close = close + 0.2
        bars.append(
            {
                "start": (start + timedelta(minutes=15 * i)).isoformat(),
                "end": (start + timedelta(minutes=15 * (i + 1))).isoformat(),
                "open": close - 0.1,
                "high": high,
                "low": low,
                "close": close,
                "ticks": 10,
                "gap_before": False,
                "missing_intervals_before": 0,
                "closed": True,
            }
        )
    return bars


class T001BarsAndAtrTests(unittest.TestCase):
    def test_exact_boundary_belongs_only_to_next_interval(self):
        bars = build_m15_bars(
            [
                q(14, 59, 100.0, 100.2),
                q(15, 0, 101.0, 101.2),
            ]
        )
        self.assertEqual(len(bars), 2)
        self.assertTrue(bars[0]["start"].endswith("10:00:00+00:00"))
        self.assertTrue(bars[1]["start"].endswith("10:15:00+00:00"))
        self.assertEqual(bars[0]["ticks"], 1)
        self.assertEqual(bars[1]["ticks"], 1)

    def test_gap_is_explicit_and_no_volume_is_invented(self):
        bars = build_m15_bars(
            [
                q(0, 1, 100.0, 100.2),
                Quote(datetime(2026, 1, 1, 10, 30, 1, tzinfo=UTC), 100.5, 100.7),
            ]
        )
        self.assertEqual(len(bars), 2)
        self.assertFalse(bars[0]["gap_before"])
        self.assertTrue(bars[1]["gap_before"])
        self.assertEqual(bars[1]["missing_intervals_before"], 1)
        self.assertNotIn("volume", bars[0])
        self.assertNotIn("volume", bars[1])

    def test_closed_at_excludes_in_progress_interval(self):
        bars = build_m15_bars(
            [
                q(0, 1, 100.0, 100.2),
                q(15, 1, 101.0, 101.2),
            ],
            closed_at=datetime(2026, 1, 1, 10, 20, tzinfo=UTC),
        )
        self.assertEqual(len(bars), 1)
        self.assertTrue(bars[0]["start"].endswith("10:00:00+00:00"))

    def test_naive_and_crossed_quotes_are_rejected(self):
        with self.assertRaises(ValueError):
            Quote(datetime(2026, 1, 1, 10, 0), 100.0, 100.1)
        with self.assertRaises(ValueError):
            Quote(datetime(2026, 1, 1, 10, 0, tzinfo=UTC), 100.2, 100.1)

    def test_invalid_atr_period_and_open_bar_are_rejected(self):
        bars = synthetic_bars(14)
        with self.assertRaises(ValueError):
            wilder_atr(bars, period=0)
        with self.assertRaises(ValueError):
            wilder_atr(bars, period=True)
        bars[-1]["closed"] = False
        with self.assertRaises(ValueError):
            atr14(bars)

    def test_wilder_atr14_seed_and_alignment(self):
        bars = synthetic_bars(16)
        values = atr14(bars)
        self.assertEqual(len(values), 16)
        self.assertTrue(all(v is None for v in values[:13]))
        self.assertIsNotNone(values[13])
        self.assertIsNotNone(values[14])
        self.assertGreaterEqual(values[13], 0.0)

    def test_future_mutation_cannot_change_past_atr(self):
        bars = synthetic_bars(20)
        before = atr14(bars)
        mutated = deepcopy(bars)
        mutated[19]["high"] += 50.0
        mutated[19]["close"] += 20.0
        after = atr14(mutated)
        self.assertEqual(before[:19], after[:19])
        self.assertNotEqual(before[19], after[19])


if __name__ == "__main__":
    unittest.main()
