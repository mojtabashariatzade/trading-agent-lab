"""Acceptance tests for T002 event-driven research execution kernel."""
import unittest
from datetime import datetime, timedelta, timezone

from trading_lab.execution.kernel import (
    ExecutionKernel,
    ExitReason,
    M1Bar,
    Quote,
    SinglePositionAccount,
    TradeRequest,
    entry_price,
    exit_price,
)


UTC = timezone.utc
T0 = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


def bar(
    minute: int,
    *,
    bid_open: float,
    bid_high: float,
    bid_low: float,
    bid_close: float,
    ask_open: float,
    ask_high: float,
    ask_low: float,
    ask_close: float,
) -> M1Bar:
    return M1Bar(
        start=T0 + timedelta(minutes=minute),
        bid_open=bid_open,
        bid_high=bid_high,
        bid_low=bid_low,
        bid_close=bid_close,
        ask_open=ask_open,
        ask_high=ask_high,
        ask_low=ask_low,
        ask_close=ask_close,
    )


class T002ExecutionKernelTests(unittest.TestCase):
    def setUp(self):
        self.kernel = ExecutionKernel()

    def test_bid_ask_entry_and_exit_are_symmetric(self):
        self.assertEqual(entry_price("BUY", 100.0, 100.2), 100.2)
        self.assertEqual(exit_price("BUY", 100.0, 100.2), 100.0)
        self.assertEqual(entry_price("SELL", 100.0, 100.2), 100.0)
        self.assertEqual(exit_price("SELL", 100.0, 100.2), 100.2)

    def test_observed_spread_is_not_deducted_twice(self):
        request = TradeRequest(
            "BUY",
            stop_distance=5.0,
            target_distance=5.0,
            timeout_at=T0 + timedelta(minutes=1),
        )
        result = self.kernel.execute(
            request,
            Quote(T0, 100.0, 100.2),
            [
                bar(
                    0,
                    bid_open=100.0,
                    bid_high=100.1,
                    bid_low=99.9,
                    bid_close=100.0,
                    ask_open=100.2,
                    ask_high=100.3,
                    ask_low=100.1,
                    ask_close=100.2,
                )
            ],
        )
        self.assertEqual(result.reason, ExitReason.TIMEOUT)
        self.assertAlmostEqual(result.entry_price, 100.2)
        self.assertAlmostEqual(result.exit_price, 100.0)
        self.assertAlmostEqual(result.gross_pnl, -0.2)
        self.assertAlmostEqual(result.net_pnl, -0.2)

    def test_slippage_and_commission_are_explicit(self):
        request = TradeRequest(
            "BUY",
            stop_distance=5.0,
            target_distance=5.0,
            timeout_at=T0 + timedelta(minutes=1),
            slippage=0.01,
            commission_per_side=0.02,
        )
        result = self.kernel.execute(
            request,
            Quote(T0, 100.0, 100.2),
            [
                bar(
                    0,
                    bid_open=100.0,
                    bid_high=100.1,
                    bid_low=99.9,
                    bid_close=100.0,
                    ask_open=100.2,
                    ask_high=100.3,
                    ask_low=100.1,
                    ask_close=100.2,
                )
            ],
        )
        self.assertAlmostEqual(result.entry_price, 100.21)
        self.assertAlmostEqual(result.exit_price, 99.99)
        self.assertAlmostEqual(result.gross_pnl, -0.22)
        self.assertAlmostEqual(result.commission_paid, 0.04)
        self.assertAlmostEqual(result.net_pnl, -0.26)

    def test_stop_gap_can_lose_more_than_one_r(self):
        request = TradeRequest(
            "BUY",
            stop_distance=1.0,
            target_distance=2.0,
            timeout_at=T0 + timedelta(minutes=2),
        )
        result = self.kernel.execute(
            request,
            Quote(T0, 100.0, 100.2),
            [
                bar(
                    0,
                    bid_open=98.8,
                    bid_high=99.0,
                    bid_low=98.5,
                    bid_close=98.9,
                    ask_open=99.0,
                    ask_high=99.2,
                    ask_low=98.7,
                    ask_close=99.1,
                )
            ],
        )
        self.assertEqual(result.reason, ExitReason.SL)
        self.assertLess(result.r_multiple, -1.0)
        self.assertAlmostEqual(result.exit_price, 98.8)

    def test_timeout_realizes_pnl(self):
        request = TradeRequest(
            "BUY",
            stop_distance=5.0,
            target_distance=5.0,
            timeout_at=T0 + timedelta(minutes=1),
        )
        result = self.kernel.execute(
            request,
            Quote(T0, 100.0, 100.2),
            [
                bar(
                    0,
                    bid_open=100.0,
                    bid_high=100.6,
                    bid_low=99.9,
                    bid_close=100.5,
                    ask_open=100.2,
                    ask_high=100.8,
                    ask_low=100.1,
                    ask_close=100.7,
                )
            ],
        )
        self.assertEqual(result.reason, ExitReason.TIMEOUT)
        self.assertFalse(result.censored)
        self.assertAlmostEqual(result.net_pnl, 0.3)

    def test_ambiguous_m1_tp_and_sl_is_flagged_and_conservative(self):
        request = TradeRequest(
            "BUY",
            stop_distance=1.0,
            target_distance=1.0,
            timeout_at=T0 + timedelta(minutes=2),
        )
        result = self.kernel.execute(
            request,
            Quote(T0, 100.0, 100.2),
            [
                bar(
                    0,
                    bid_open=100.0,
                    bid_high=101.3,
                    bid_low=99.1,
                    bid_close=100.4,
                    ask_open=100.2,
                    ask_high=101.5,
                    ask_low=99.3,
                    ask_close=100.6,
                )
            ],
        )
        self.assertTrue(result.ambiguous_m1)
        self.assertEqual(result.reason, ExitReason.SL)
        self.assertLess(result.net_pnl, 0.0)

    def test_missing_tail_is_censored_not_fabricated_timeout(self):
        request = TradeRequest(
            "SELL",
            stop_distance=2.0,
            target_distance=2.0,
            timeout_at=T0 + timedelta(minutes=5),
        )
        result = self.kernel.execute(
            request,
            Quote(T0, 100.0, 100.2),
            [
                bar(
                    0,
                    bid_open=100.0,
                    bid_high=100.1,
                    bid_low=99.9,
                    bid_close=100.0,
                    ask_open=100.2,
                    ask_high=100.3,
                    ask_low=100.1,
                    ask_close=100.2,
                )
            ],
        )
        self.assertEqual(result.reason, ExitReason.CENSORED)
        self.assertTrue(result.censored)
        self.assertIsNone(result.exit_price)
        self.assertIsNone(result.net_pnl)
        self.assertIsNone(result.r_multiple)

    def test_sell_stop_gap_is_symmetric(self):
        request = TradeRequest(
            "SELL",
            stop_distance=1.0,
            target_distance=2.0,
            timeout_at=T0 + timedelta(minutes=2),
        )
        result = self.kernel.execute(
            request,
            Quote(T0, 100.0, 100.2),
            [
                bar(
                    0,
                    bid_open=101.3,
                    bid_high=101.5,
                    bid_low=101.1,
                    bid_close=101.4,
                    ask_open=101.5,
                    ask_high=101.7,
                    ask_low=101.3,
                    ask_close=101.6,
                )
            ],
        )
        self.assertEqual(result.reason, ExitReason.SL)
        self.assertLess(result.r_multiple, -1.0)
        self.assertAlmostEqual(result.exit_price, 101.5)

    def test_single_position_account_uses_same_kernel(self):
        class SpyKernel(ExecutionKernel):
            def __init__(self):
                self.calls = 0

            def execute(self, request, entry, bars):
                self.calls += 1
                return super().execute(request, entry, bars)

        spy = SpyKernel()
        account = SinglePositionAccount(kernel=spy, cash=10.0)
        request = TradeRequest(
            "BUY",
            stop_distance=5.0,
            target_distance=5.0,
            timeout_at=T0 + timedelta(minutes=1),
        )
        result = account.execute(
            request,
            Quote(T0, 100.0, 100.2),
            [
                bar(
                    0,
                    bid_open=100.0,
                    bid_high=100.6,
                    bid_low=99.9,
                    bid_close=100.5,
                    ask_open=100.2,
                    ask_high=100.8,
                    ask_low=100.1,
                    ask_close=100.7,
                )
            ],
        )
        self.assertEqual(spy.calls, 1)
        self.assertFalse(account.position_open)
        self.assertEqual(account.history, [result])
        self.assertAlmostEqual(account.cash, 10.3)

    def test_censored_trade_keeps_account_position_open(self):
        account = SinglePositionAccount()
        request = TradeRequest(
            "BUY",
            stop_distance=5.0,
            target_distance=5.0,
            timeout_at=T0 + timedelta(minutes=5),
        )
        bars = [
            bar(
                0,
                bid_open=100.0,
                bid_high=100.1,
                bid_low=99.9,
                bid_close=100.0,
                ask_open=100.2,
                ask_high=100.3,
                ask_low=100.1,
                ask_close=100.2,
            )
        ]
        result = account.execute(request, Quote(T0, 100.0, 100.2), bars)
        self.assertTrue(result.censored)
        self.assertTrue(account.position_open)
        with self.assertRaises(RuntimeError):
            account.execute(request, Quote(T0, 100.0, 100.2), bars)

    def test_validation_failure_does_not_leave_account_open(self):
        account = SinglePositionAccount()
        request = TradeRequest(
            "BUY",
            stop_distance=5.0,
            target_distance=5.0,
            timeout_at=T0 + timedelta(minutes=1),
        )
        bad = [
            bar(
                1,
                bid_open=100.0,
                bid_high=100.1,
                bid_low=99.9,
                bid_close=100.0,
                ask_open=100.2,
                ask_high=100.3,
                ask_low=100.1,
                ask_close=100.2,
            ),
            bar(
                1,
                bid_open=100.0,
                bid_high=100.1,
                bid_low=99.9,
                bid_close=100.0,
                ask_open=100.2,
                ask_high=100.3,
                ask_low=100.1,
                ask_close=100.2,
            ),
        ]
        with self.assertRaises(ValueError):
            account.execute(request, Quote(T0, 100.0, 100.2), bad)
        self.assertFalse(account.position_open)

    def test_timeout_must_be_m1_aligned(self):
        with self.assertRaises(ValueError):
            TradeRequest(
                "BUY",
                stop_distance=1.0,
                target_distance=1.0,
                timeout_at=T0 + timedelta(seconds=30),
            )


if __name__ == "__main__":
    unittest.main()
