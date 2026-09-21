"""Synthetic regression fixtures; never evidence of trading performance."""
import unittest
from datetime import datetime, timedelta, timezone

from trading_lab.execution.kernel import (
    ExecutionKernel, ExitReason, M1Bar, Quote, SinglePositionAccount, TradeRequest,
)

T0 = datetime(2026, 1, 1, 10, tzinfo=timezone.utc)


def candle(minute=0, *, op=100., high=100.3, low=99.9, close=100.):
    return M1Bar(T0 + timedelta(minutes=minute), op, high, low, close,
                 op + .2, high + .2, low + .2, close + .2)


def request(side="BUY", minutes=4, slip=0., commission=0.):
    return TradeRequest(side, 1., 1., T0 + timedelta(minutes=minutes),
                        slippage=slip, commission_per_side=commission)


class ExecutionAuditTests(unittest.TestCase):
    def setUp(self):
        self.kernel = ExecutionKernel()
        self.entry = Quote(T0, 100., 100.2)

    def test_missing_first_minute_is_censored(self):
        result = self.kernel.execute(request(), self.entry,
            [candle(1, op=101.5, high=102., low=101., close=101.8)])
        self.assertTrue(result.censored)
        self.assertIsNone(result.net_pnl)

    def test_missing_interior_minute_is_censored_for_both_sides(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                result = self.kernel.execute(request(side), self.entry,
                    [candle(), candle(2, op=102., high=102.2, low=98., close=101.)])
                self.assertEqual(result.reason, ExitReason.CENSORED)
                self.assertIsNone(result.r_multiple)

    def test_later_gap_cannot_erase_already_resolved_exit(self):
        result = self.kernel.execute(request(), self.entry,
            [candle(0, op=100., high=101.5, low=99.9, close=101.), candle(3)])
        self.assertEqual(result.reason, ExitReason.TP)

    def test_buy_target_at_open_precedes_later_stop(self):
        result = self.kernel.execute(request(), self.entry,
            [candle(0, op=101.5, high=101.8, low=98., close=100.)])
        self.assertEqual(result.reason, ExitReason.TP)
        self.assertEqual(result.exit_at, T0)
        self.assertFalse(result.ambiguous_m1)
        self.assertAlmostEqual(result.exit_price, result.target_price)

    def test_sell_target_at_open_precedes_later_stop(self):
        result = self.kernel.execute(request("SELL"), self.entry,
            [candle(0, op=98.5, high=102., low=98., close=100.)])
        self.assertEqual(result.reason, ExitReason.TP)
        self.assertEqual(result.exit_at, T0)
        self.assertFalse(result.ambiguous_m1)

    def test_known_stop_at_open_is_not_ambiguous(self):
        for side, op in (("BUY", 98.), ("SELL", 102.)):
            with self.subTest(side=side):
                result = self.kernel.execute(request(side), self.entry,
                    [candle(0, op=op, high=103., low=97., close=100.)])
                self.assertEqual(result.reason, ExitReason.SL)
                self.assertFalse(result.ambiguous_m1)
                self.assertEqual(result.exit_at, T0)
                self.assertLess(result.r_multiple, -1.)

    def test_unknown_intrabar_order_remains_conservative(self):
        result = self.kernel.execute(request(), self.entry,
            [candle(0, high=102., low=98., close=100.)])
        self.assertEqual(result.reason, ExitReason.SL)
        self.assertTrue(result.ambiguous_m1)

    def test_buy_limit_target_is_not_filled_below_limit(self):
        result = self.kernel.execute(request(slip=.1), self.entry,
            [candle(0, high=102., low=100., close=101.5)])
        self.assertEqual(result.reason, ExitReason.TP)
        self.assertAlmostEqual(result.exit_price, result.target_price)
        self.assertAlmostEqual(result.entry_price, 100.3)

    def test_sell_limit_target_is_not_filled_above_limit(self):
        result = self.kernel.execute(request("SELL", slip=.1), self.entry,
            [candle(0, high=100.1, low=98., close=98.5)])
        self.assertEqual(result.reason, ExitReason.TP)
        self.assertAlmostEqual(result.exit_price, result.target_price)
        self.assertAlmostEqual(result.entry_price, 99.9)

    def test_market_stop_retains_adverse_slippage_and_costs(self):
        result = self.kernel.execute(request(slip=.1, commission=.02), self.entry,
            [candle(0, op=98., high=98.5, low=97.9, close=98.2)])
        self.assertAlmostEqual(result.exit_price, 97.9)
        self.assertAlmostEqual(result.commission_paid, .04)
        self.assertAlmostEqual(result.net_pnl, 97.9 - 100.3 - .04)

    def test_m1_entry_requires_minute_alignment(self):
        with self.assertRaises(ValueError):
            self.kernel.execute(request(), Quote(T0 + timedelta(seconds=30), 100., 100.2),
                                [candle(1)])

    def test_crossed_extrema_are_invalid_even_when_open_close_uncrossed(self):
        for high, low in ((103., 99.), (102., 98.)):
            with self.subTest(high=high, low=low), self.assertRaises(ValueError):
                M1Bar(T0, 100., 102., 99., 100., 100.2, high if low==98. else 101., low, 100.2)

    def test_account_rejects_overlapping_entry_after_batch_resolution(self):
        account = SinglePositionAccount()
        account.execute(request(minutes=2), self.entry, [candle(0), candle(1)])
        before = account.cash
        with self.assertRaises(RuntimeError):
            account.execute(request(minutes=3), Quote(T0 + timedelta(minutes=1), 100., 100.2),
                            [candle(1), candle(2)])
        self.assertEqual(account.cash, before)
        self.assertEqual(len(account.history), 1)

    def test_account_accepts_entry_at_previous_exit_time(self):
        account = SinglePositionAccount()
        account.execute(request(minutes=1), self.entry, [candle()])
        second = account.execute(request(minutes=2),
                                 Quote(T0 + timedelta(minutes=1), 100., 100.2), [candle(1)])
        self.assertEqual(second.reason, ExitReason.TIMEOUT)
        self.assertEqual(len(account.history), 2)

    def test_censored_entry_commission_is_paid_without_inventing_pnl(self):
        account = SinglePositionAccount(cash=10.)
        result = account.execute(request(commission=.02), self.entry, [])
        self.assertTrue(result.censored)
        self.assertTrue(account.position_open)
        self.assertIsNone(result.net_pnl)
        self.assertAlmostEqual(account.cash, 9.98)

    def test_arithmetic_overflow_is_rejected(self):
        with self.assertRaises(ValueError):
            self.kernel.execute(TradeRequest("BUY", 1e308, 1e308,
                T0 + timedelta(minutes=1), quantity=1e308), Quote(T0, 1e308, 1e308), [])

    def test_duplicate_minutes_are_still_rejected(self):
        with self.assertRaises(ValueError):
            self.kernel.execute(request(), self.entry, [candle(), candle()])


if __name__ == "__main__":
    unittest.main()
