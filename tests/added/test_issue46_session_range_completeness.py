"""Issue #46 regression tests for session opening-range completeness."""

import unittest
from datetime import datetime, timedelta, timezone

from trading_lab.strategies import SessionBreakoutConfig, SessionRangeBreakoutExpert, Side


UTC = timezone.utc


def session_row(start, *, close=100.0, high=100.4, low=99.8, gap_before=False):
    return {
        "start": start.isoformat(),
        "end": (start + timedelta(minutes=15)).isoformat(),
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "ticks": 10,
        "gap_before": gap_before,
        "closed": True,
    }


class Issue46SessionRangeCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.expert = SessionRangeBreakoutExpert(
            SessionBreakoutConfig(timezone_name="Europe/London")
        )
        self.base = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)

    def _proposal(self, starts, *, breakout_close=101.1):
        rows = [session_row(start, close=100.2, high=100.5, low=99.9) for start in starts]
        rows.append(
            session_row(
                self.base + timedelta(minutes=60),
                close=breakout_close,
                high=101.2,
                low=100.8,
            )
        )
        return self.expert.propose(rows)

    def test_missing_first_opening_range_bar_is_incomplete(self):
        result = self._proposal(
            [
                self.base + timedelta(minutes=15),
                self.base + timedelta(minutes=30),
                self.base + timedelta(minutes=45),
            ]
        )
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "RANGE_INCOMPLETE")

    def test_missing_middle_opening_range_bar_is_incomplete(self):
        result = self._proposal(
            [
                self.base,
                self.base + timedelta(minutes=15),
                self.base + timedelta(minutes=45),
            ]
        )
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "RANGE_INCOMPLETE")

    def test_missing_last_opening_range_bar_is_incomplete(self):
        result = self._proposal(
            [
                self.base,
                self.base + timedelta(minutes=15),
                self.base + timedelta(minutes=30),
            ]
        )
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "RANGE_INCOMPLETE")

    def test_gap_flag_still_reports_data_gap(self):
        rows = [
            session_row(self.base, close=100.2, high=100.5, low=99.9),
            session_row(
                self.base + timedelta(minutes=15),
                close=100.1,
                high=100.4,
                low=99.8,
                gap_before=True,
            ),
            session_row(self.base + timedelta(minutes=30), close=100.3, high=100.6, low=100.0),
            session_row(self.base + timedelta(minutes=45), close=100.2, high=100.5, low=99.9),
            session_row(self.base + timedelta(minutes=60), close=101.1, high=101.2, low=100.8),
        ]
        result = self.expert.propose(rows)
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "DATA_GAP")


if __name__ == "__main__":
    unittest.main()
