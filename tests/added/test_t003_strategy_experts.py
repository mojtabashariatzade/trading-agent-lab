"""Acceptance tests for T003 strategy experts."""
import unittest
from datetime import datetime, timedelta, timezone

from trading_lab.strategies import (
    BollingerReentryConfig,
    BollingerReentryExpert,
    EmaTrendConfig,
    EmaTrendExpert,
    ExitConfig,
    ExitLeague,
    SessionBreakoutConfig,
    SessionRangeBreakoutExpert,
    Side,
    VolatilityCompressionBreakoutExpert,
    VolatilityCompressionConfig,
)


UTC = timezone.utc


def make_rows(closes, *, start=None, gap_index=None):
    start = start or datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    rows = []
    for i, close in enumerate(closes):
        close = float(close)
        rows.append(
            {
                "start": (start + timedelta(minutes=15 * i)).isoformat(),
                "end": (start + timedelta(minutes=15 * (i + 1))).isoformat(),
                "open": close,
                "high": close + 0.05,
                "low": max(0.001, close - 0.05),
                "close": close,
                "ticks": 10,
                "gap_before": i == gap_index,
                "closed": True,
            }
        )
    return rows


def session_row(start, *, close, high, low):
    return {
        "start": start.isoformat(),
        "end": (start + timedelta(minutes=15)).isoformat(),
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "ticks": 10,
        "gap_before": False,
        "closed": True,
    }


def compression_row(start, *, high, low, close):
    return {
        "start": start.isoformat(),
        "end": (start + timedelta(minutes=15)).isoformat(),
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "ticks": 10,
        "gap_before": False,
        "closed": True,
    }


class T003StrategyExpertTests(unittest.TestCase):
    def test_ema_trend_buy_crossover_is_pure_versioned_and_expires(self):
        expert = EmaTrendExpert(EmaTrendConfig(fast_period=2, slow_period=3, expiry_bars=2))
        rows = make_rows([3.0, 2.0, 1.0, 4.0])
        first = expert.propose(rows)
        second = expert.propose(rows)
        self.assertEqual(first, second)
        self.assertEqual(first.strategy_id, "EMA_TREND")
        self.assertEqual(first.version, "1.0.0")
        self.assertEqual(first.side, Side.BUY)
        self.assertEqual(first.reason, "FAST_EMA_CROSSED_ABOVE_SLOW")
        self.assertEqual(first.expires_at - first.generated_at, timedelta(minutes=30))

    def test_ema_trend_sell_and_no_signal(self):
        expert = EmaTrendExpert(EmaTrendConfig(fast_period=2, slow_period=3))
        sell = expert.propose(make_rows([1.0, 2.0, 3.0, 0.5]))
        flat = expert.propose(make_rows([1.0, 1.0, 1.0, 1.0]))
        self.assertEqual(sell.side, Side.SELL)
        self.assertEqual(flat.side, Side.PASS)
        self.assertEqual(flat.reason, "NO_CROSSOVER")

    def test_ema_data_gap_returns_pass(self):
        expert = EmaTrendExpert(EmaTrendConfig(fast_period=2, slow_period=3))
        result = expert.propose(make_rows([3.0, 2.0, 1.0, 4.0], gap_index=3))
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "DATA_GAP")

    def test_bollinger_reentry_buy_sell_and_no_signal(self):
        expert = BollingerReentryExpert(BollingerReentryConfig(window=3, deviations=1.0))
        buy = expert.propose(make_rows([10.0, 10.0, 0.5, 5.0]))
        sell = expert.propose(make_rows([1.0, 1.0, 10.0, 5.0]))
        flat = expert.propose(make_rows([5.0, 5.0, 5.0, 5.0]))
        self.assertEqual(buy.side, Side.BUY)
        self.assertEqual(buy.reason, "REENTERED_FROM_BELOW")
        self.assertEqual(sell.side, Side.SELL)
        self.assertEqual(sell.reason, "REENTERED_FROM_ABOVE")
        self.assertEqual(flat.side, Side.PASS)

    def test_volatility_compression_breakout_buy_and_sell(self):
        expert = VolatilityCompressionBreakoutExpert(
            VolatilityCompressionConfig(
                lookback=3,
                compression_threshold=0.7,
                expansion_multiplier=2.0,
            )
        )
        start = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)

        buy_rows = [
            compression_row(start + timedelta(minutes=15 * 0), high=100.8, low=100.0, close=100.4),
            compression_row(start + timedelta(minutes=15 * 1), high=100.9, low=100.1, close=100.5),
            compression_row(start + timedelta(minutes=15 * 2), high=101.0, low=100.2, close=100.6),
            compression_row(start + timedelta(minutes=15 * 3), high=100.62, low=100.38, close=100.50),
            compression_row(start + timedelta(minutes=15 * 4), high=101.2, low=100.4, close=101.05),
        ]
        sell_rows = [
            compression_row(start + timedelta(minutes=15 * 0), high=100.8, low=100.0, close=100.4),
            compression_row(start + timedelta(minutes=15 * 1), high=100.9, low=100.1, close=100.5),
            compression_row(start + timedelta(minutes=15 * 2), high=101.0, low=100.2, close=100.6),
            compression_row(start + timedelta(minutes=15 * 3), high=100.62, low=100.38, close=100.50),
            compression_row(start + timedelta(minutes=15 * 4), high=100.55, low=99.70, close=100.10),
        ]

        buy = expert.propose(buy_rows)
        sell = expert.propose(sell_rows)
        self.assertEqual(buy.side, Side.BUY)
        self.assertEqual(buy.reason, "UPSIDE_COMPRESSION_BREAKOUT")
        self.assertEqual(sell.side, Side.SELL)
        self.assertEqual(sell.reason, "DOWNSIDE_COMPRESSION_BREAKOUT")

    def test_volatility_compression_no_compression_and_no_expansion(self):
        expert = VolatilityCompressionBreakoutExpert(
            VolatilityCompressionConfig(
                lookback=3,
                compression_threshold=0.7,
                expansion_multiplier=2.0,
            )
        )
        start = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)

        no_compression = [
            compression_row(start + timedelta(minutes=15 * 0), high=100.8, low=100.0, close=100.4),
            compression_row(start + timedelta(minutes=15 * 1), high=100.9, low=100.1, close=100.5),
            compression_row(start + timedelta(minutes=15 * 2), high=101.0, low=100.2, close=100.6),
            compression_row(start + timedelta(minutes=15 * 3), high=100.95, low=100.25, close=100.60),
            compression_row(start + timedelta(minutes=15 * 4), high=101.3, low=100.4, close=101.10),
        ]
        no_expansion = [
            compression_row(start + timedelta(minutes=15 * 0), high=100.8, low=100.0, close=100.4),
            compression_row(start + timedelta(minutes=15 * 1), high=100.9, low=100.1, close=100.5),
            compression_row(start + timedelta(minutes=15 * 2), high=101.0, low=100.2, close=100.6),
            compression_row(start + timedelta(minutes=15 * 3), high=100.62, low=100.38, close=100.50),
            compression_row(start + timedelta(minutes=15 * 4), high=100.66, low=100.34, close=100.63),
        ]

        self.assertEqual(expert.propose(no_compression).reason, "NO_COMPRESSION")
        self.assertEqual(expert.propose(no_expansion).reason, "NO_EXPANSION")

    def test_shared_and_native_exit_leagues_are_distinct(self):
        expert = EmaTrendExpert(
            EmaTrendConfig(
                fast_period=2,
                slow_period=3,
                native_exit=ExitConfig(0.30, 0.60),
            )
        )
        rows = make_rows([3.0, 2.0, 1.0, 4.0])
        native = expert.propose(rows, league=ExitLeague.NATIVE)
        shared = expert.propose(
            rows,
            league=ExitLeague.SHARED,
            shared_exit=ExitConfig(0.50, 0.50),
        )
        self.assertEqual(native.league, ExitLeague.NATIVE)
        self.assertEqual(shared.league, ExitLeague.SHARED)
        self.assertEqual(native.exit_config, ExitConfig(0.30, 0.60))
        self.assertEqual(shared.exit_config, ExitConfig(0.50, 0.50))
        with self.assertRaises(ValueError):
            expert.propose(rows, league=ExitLeague.SHARED)

    def test_session_breakout_uses_explicit_london_timezone_in_winter(self):
        expert = SessionRangeBreakoutExpert(
            SessionBreakoutConfig(timezone_name="Europe/London")
        )
        base = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        rows = [
            session_row(base + timedelta(minutes=0), close=100.0, high=100.4, low=99.8),
            session_row(base + timedelta(minutes=15), close=100.1, high=100.5, low=99.9),
            session_row(base + timedelta(minutes=30), close=100.2, high=100.6, low=100.0),
            session_row(base + timedelta(minutes=45), close=100.3, high=100.7, low=100.1),
            session_row(base + timedelta(minutes=60), close=100.9, high=101.0, low=100.6),
        ]
        result = expert.propose(rows)
        self.assertEqual(result.side, Side.BUY)
        self.assertEqual(result.reason, "CLOSED_ABOVE_SESSION_RANGE")

    def test_session_breakout_respects_dst_without_fixed_utc_offset(self):
        expert = SessionRangeBreakoutExpert(
            SessionBreakoutConfig(timezone_name="Europe/London")
        )
        # In July London is UTC+1, so local 08:00 starts at 07:00 UTC.
        base = datetime(2026, 7, 6, 7, 0, tzinfo=UTC)
        rows = [
            session_row(base + timedelta(minutes=0), close=100.0, high=100.4, low=99.8),
            session_row(base + timedelta(minutes=15), close=100.1, high=100.5, low=99.9),
            session_row(base + timedelta(minutes=30), close=100.2, high=100.6, low=100.0),
            session_row(base + timedelta(minutes=45), close=100.3, high=100.7, low=100.1),
            session_row(base + timedelta(minutes=60), close=99.5, high=100.2, low=99.4),
        ]
        result = expert.propose(rows)
        self.assertEqual(result.side, Side.SELL)
        self.assertEqual(result.reason, "CLOSED_BELOW_SESSION_RANGE")

    def test_session_before_range_close_is_pass(self):
        expert = SessionRangeBreakoutExpert()
        base = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        rows = [
            session_row(base, close=100.0, high=100.2, low=99.8),
            session_row(base + timedelta(minutes=15), close=100.1, high=100.3, low=99.9),
        ]
        result = expert.propose(rows)
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "SESSION_RANGE_NOT_CLOSED")

    def test_session_breakout_missing_first_opening_interval_is_incomplete(self):
        expert = SessionRangeBreakoutExpert(
            SessionBreakoutConfig(timezone_name="Europe/London")
        )
        base = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        rows = [
            session_row(base + timedelta(minutes=15), close=100.1, high=100.5, low=99.9),
            session_row(base + timedelta(minutes=30), close=100.2, high=100.6, low=100.0),
            session_row(base + timedelta(minutes=45), close=100.3, high=100.7, low=100.1),
            session_row(base + timedelta(minutes=60), close=100.9, high=101.0, low=100.6),
        ]
        result = expert.propose(rows)
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "RANGE_INCOMPLETE")

    def test_session_breakout_missing_middle_opening_interval_is_incomplete(self):
        expert = SessionRangeBreakoutExpert(
            SessionBreakoutConfig(timezone_name="Europe/London")
        )
        base = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        rows = [
            session_row(base + timedelta(minutes=0), close=100.0, high=100.4, low=99.8),
            session_row(base + timedelta(minutes=30), close=100.2, high=100.6, low=100.0),
            session_row(base + timedelta(minutes=45), close=100.3, high=100.7, low=100.1),
            session_row(base + timedelta(minutes=60), close=100.9, high=101.0, low=100.6),
        ]
        result = expert.propose(rows)
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "RANGE_INCOMPLETE")

    def test_session_breakout_missing_last_opening_interval_is_incomplete(self):
        expert = SessionRangeBreakoutExpert(
            SessionBreakoutConfig(timezone_name="Europe/London")
        )
        base = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        rows = [
            session_row(base + timedelta(minutes=0), close=100.0, high=100.4, low=99.8),
            session_row(base + timedelta(minutes=15), close=100.1, high=100.5, low=99.9),
            session_row(base + timedelta(minutes=30), close=100.2, high=100.6, low=100.0),
            session_row(base + timedelta(minutes=60), close=100.9, high=101.0, low=100.6),
        ]
        result = expert.propose(rows)
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "RANGE_INCOMPLETE")

    def test_session_breakout_overlapping_opening_intervals_are_incomplete(self):
        expert = SessionRangeBreakoutExpert(
            SessionBreakoutConfig(timezone_name="Europe/London")
        )
        base = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        rows = [
            session_row(base + timedelta(minutes=0), close=100.0, high=100.4, low=99.8),
            {
                "start": (base + timedelta(minutes=15)).isoformat(),
                "end": (base + timedelta(minutes=45)).isoformat(),
                "open": 100.1,
                "high": 100.6,
                "low": 99.9,
                "close": 100.2,
                "ticks": 10,
                "gap_before": False,
                "closed": True,
            },
            session_row(base + timedelta(minutes=45), close=100.3, high=100.7, low=100.1),
            session_row(base + timedelta(minutes=60), close=100.9, high=101.0, low=100.6),
        ]
        result = expert.propose(rows)
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "RANGE_INCOMPLETE")

    def test_session_breakout_partial_bar_crossing_range_start_is_incomplete(self):
        expert = SessionRangeBreakoutExpert(
            SessionBreakoutConfig(timezone_name="Europe/London")
        )
        base = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        rows = [
            {
                "start": (base - timedelta(minutes=15)).isoformat(),
                "end": (base + timedelta(minutes=15)).isoformat(),
                "open": 100.0,
                "high": 100.5,
                "low": 99.7,
                "close": 100.1,
                "ticks": 10,
                "gap_before": False,
                "closed": True,
            },
            session_row(base + timedelta(minutes=15), close=100.1, high=100.5, low=99.9),
            session_row(base + timedelta(minutes=30), close=100.2, high=100.6, low=100.0),
            session_row(base + timedelta(minutes=45), close=100.3, high=100.7, low=100.1),
            session_row(base + timedelta(minutes=60), close=100.9, high=101.0, low=100.6),
        ]
        result = expert.propose(rows)
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "RANGE_INCOMPLETE")

    def test_session_breakout_partial_bar_crossing_range_end_is_incomplete(self):
        expert = SessionRangeBreakoutExpert(
            SessionBreakoutConfig(timezone_name="Europe/London")
        )
        base = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        rows = [
            session_row(base + timedelta(minutes=0), close=100.0, high=100.4, low=99.8),
            session_row(base + timedelta(minutes=15), close=100.1, high=100.5, low=99.9),
            session_row(base + timedelta(minutes=30), close=100.2, high=100.6, low=100.0),
            {
                "start": (base + timedelta(minutes=45)).isoformat(),
                "end": (base + timedelta(minutes=75)).isoformat(),
                "open": 100.3,
                "high": 100.9,
                "low": 100.1,
                "close": 100.8,
                "ticks": 10,
                "gap_before": False,
                "closed": True,
            },
            session_row(base + timedelta(minutes=75), close=100.9, high=101.0, low=100.6),
        ]
        result = expert.propose(rows)
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "RANGE_INCOMPLETE")

    def test_session_breakout_complete_range_without_breakout_is_no_breakout(self):
        expert = SessionRangeBreakoutExpert(
            SessionBreakoutConfig(timezone_name="Europe/London")
        )
        base = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        rows = [
            session_row(base + timedelta(minutes=0), close=100.0, high=100.4, low=99.8),
            session_row(base + timedelta(minutes=15), close=100.1, high=100.5, low=99.9),
            session_row(base + timedelta(minutes=30), close=100.2, high=100.6, low=100.0),
            session_row(base + timedelta(minutes=45), close=100.3, high=100.7, low=100.1),
            session_row(base + timedelta(minutes=60), close=100.4, high=100.5, low=100.2),
        ]
        result = expert.propose(rows)
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "NO_BREAKOUT")

    def test_session_breakout_gap_within_complete_range_is_data_gap(self):
        expert = SessionRangeBreakoutExpert(
            SessionBreakoutConfig(timezone_name="Europe/London")
        )
        base = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        rows = [
            session_row(base + timedelta(minutes=0), close=100.0, high=100.4, low=99.8),
            session_row(base + timedelta(minutes=15), close=100.1, high=100.5, low=99.9),
            session_row(base + timedelta(minutes=30), close=100.2, high=100.6, low=100.0),
            session_row(base + timedelta(minutes=45), close=100.3, high=100.7, low=100.1),
            session_row(base + timedelta(minutes=60), close=100.9, high=101.0, low=100.6),
        ]
        rows[2]["gap_before"] = True
        result = expert.propose(rows)
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "DATA_GAP")

    def test_session_breakout_gap_before_breakout_bar_is_data_gap(self):
        expert = SessionRangeBreakoutExpert(
            SessionBreakoutConfig(timezone_name="Europe/London")
        )
        base = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        rows = [
            session_row(base + timedelta(minutes=0), close=100.0, high=100.4, low=99.8),
            session_row(base + timedelta(minutes=15), close=100.1, high=100.5, low=99.9),
            session_row(base + timedelta(minutes=30), close=100.2, high=100.6, low=100.0),
            session_row(base + timedelta(minutes=45), close=100.3, high=100.7, low=100.1),
            session_row(base + timedelta(minutes=60), close=100.9, high=101.0, low=100.6),
        ]
        rows[-1]["gap_before"] = True
        result = expert.propose(rows)
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "DATA_GAP")

    def test_open_bar_is_rejected(self):
        expert = EmaTrendExpert(EmaTrendConfig(fast_period=2, slow_period=3))
        rows = make_rows([3.0, 2.0, 1.0, 4.0])
        rows[-1]["closed"] = False
        with self.assertRaises(ValueError):
            expert.propose(rows)


if __name__ == "__main__":
    unittest.main()
