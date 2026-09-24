"""Acceptance tests for Donchian breakout expert (Issue #38 S02 seed)."""

import unittest
from datetime import datetime, timedelta, timezone

from trading_lab.strategies import (
    DonchianBreakoutConfig,
    DonchianBreakoutExpert,
    ExitConfig,
    ExitLeague,
    Side,
)


UTC = timezone.utc


def make_rows(closes, *, highs=None, lows=None, start=None, gap_index=None):
    start = start or datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    rows = []
    highs = highs or [float(c) + 0.20 for c in closes]
    lows = lows or [float(c) - 0.20 for c in closes]
    for i, close in enumerate(closes):
        rows.append(
            {
                "start": (start + timedelta(minutes=15 * i)).isoformat(),
                "end": (start + timedelta(minutes=15 * (i + 1))).isoformat(),
                "open": float(close),
                "high": float(highs[i]),
                "low": float(lows[i]),
                "close": float(close),
                "ticks": 10,
                "gap_before": i == gap_index,
                "closed": True,
            }
        )
    return rows


class DonchianBreakoutExpertTests(unittest.TestCase):
    def test_buy_breakout_and_expiry(self):
        expert = DonchianBreakoutExpert(DonchianBreakoutConfig(lookback=3, expiry_bars=3))
        rows = make_rows(
            closes=[100.0, 100.2, 100.1, 101.0],
            highs=[100.2, 100.4, 100.3, 101.2],
            lows=[99.8, 100.0, 99.9, 100.8],
        )
        result = expert.propose(rows)
        self.assertEqual(result.strategy_id, "DONCHIAN_BREAKOUT")
        self.assertEqual(result.version, "1.0.0")
        self.assertEqual(result.side, Side.BUY)
        self.assertEqual(result.reason, "CLOSED_ABOVE_DONCHIAN_HIGH")
        self.assertEqual(result.expires_at - result.generated_at, timedelta(minutes=45))

    def test_sell_breakout_and_no_breakout(self):
        expert = DonchianBreakoutExpert(DonchianBreakoutConfig(lookback=3))
        sell = expert.propose(
            make_rows(
                closes=[100.2, 100.0, 100.1, 99.0],
                highs=[100.4, 100.2, 100.3, 99.2],
                lows=[100.0, 99.8, 99.9, 98.8],
            )
        )
        flat = expert.propose(
            make_rows(
                closes=[100.0, 100.2, 100.1, 100.15],
                highs=[100.2, 100.4, 100.3, 100.25],
                lows=[99.8, 100.0, 99.9, 99.95],
            )
        )
        self.assertEqual(sell.side, Side.SELL)
        self.assertEqual(sell.reason, "CLOSED_BELOW_DONCHIAN_LOW")
        self.assertEqual(flat.side, Side.PASS)
        self.assertEqual(flat.reason, "NO_BREAKOUT")

    def test_data_gap_and_insufficient_history_return_pass(self):
        expert = DonchianBreakoutExpert(DonchianBreakoutConfig(lookback=3))
        gap = expert.propose(
            make_rows(
                closes=[100.0, 100.2, 100.1, 101.0],
                highs=[100.2, 100.4, 100.3, 101.2],
                lows=[99.8, 100.0, 99.9, 100.8],
                gap_index=2,
            )
        )
        short = expert.propose(make_rows(closes=[100.0, 100.1, 100.2]))
        self.assertEqual(gap.side, Side.PASS)
        self.assertEqual(gap.reason, "DATA_GAP")
        self.assertEqual(short.side, Side.PASS)
        self.assertEqual(short.reason, "INSUFFICIENT_HISTORY")

    def test_shared_exit_uses_shared_config(self):
        expert = DonchianBreakoutExpert(
            DonchianBreakoutConfig(
                lookback=3,
                native_exit=ExitConfig(0.30, 0.70),
            )
        )
        rows = make_rows(
            closes=[100.0, 100.2, 100.1, 101.0],
            highs=[100.2, 100.4, 100.3, 101.2],
            lows=[99.8, 100.0, 99.9, 100.8],
        )
        native = expert.propose(rows, league=ExitLeague.NATIVE)
        shared = expert.propose(rows, league=ExitLeague.SHARED, shared_exit=ExitConfig(0.50, 0.50))
        self.assertEqual(native.exit_config, ExitConfig(0.30, 0.70))
        self.assertEqual(shared.exit_config, ExitConfig(0.50, 0.50))


if __name__ == "__main__":
    unittest.main()
