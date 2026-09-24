from __future__ import annotations

import unittest

from trading_lab.accounting.ledger import AccountLedger, FillEvent


class Issue70AccountLedgerTests(unittest.TestCase):
    def test_reversal_sequence_open_increase_reduce_close_reverse(self) -> None:
        ledger = AccountLedger(starting_balance=10_000.0)

        ledger.apply_fill(FillEvent(side="BUY", quantity=1.0, price=100.0))
        ledger.apply_fill(FillEvent(side="BUY", quantity=1.0, price=102.0))
        ledger.apply_fill(FillEvent(side="SELL", quantity=0.5, price=103.0))
        ledger.apply_fill(FillEvent(side="SELL", quantity=2.0, price=99.0))
        ledger.apply_fill(FillEvent(side="BUY", quantity=0.5, price=97.0))

        snap = ledger.snapshot(mark_price=97.0)

        self.assertAlmostEqual(snap.position_qty, 0.0)
        self.assertIsNone(snap.average_entry_price)
        self.assertAlmostEqual(snap.realized_gross_pnl, -1.0)
        self.assertAlmostEqual(snap.realized_costs_total, 0.0)
        self.assertAlmostEqual(snap.trading_pnl_net, -1.0)
        self.assertAlmostEqual(snap.cash_balance, 9_999.0)

    def test_no_trade_period_and_external_cashflows_are_separate(self) -> None:
        ledger = AccountLedger(starting_balance=5_000.0)

        ledger.apply_cashflow(750.0)
        ledger.apply_cashflow(-250.0)

        snap = ledger.snapshot(mark_price=150.0)

        self.assertAlmostEqual(snap.trading_pnl_net, 0.0)
        self.assertAlmostEqual(snap.external_cashflow_total, 500.0)
        self.assertAlmostEqual(snap.cash_balance, 5_500.0)
        self.assertAlmostEqual(snap.equity_total, 5_500.0)
        self.assertAlmostEqual(snap.trading_equity_ex_cashflows, 5_000.0)
        self.assertAlmostEqual(snap.max_drawdown, 0.0)

    def test_cost_stress_counts_spread_commission_slippage_and_rollover_once(self) -> None:
        ledger = AccountLedger(starting_balance=1_000.0)

        per_fill_cost = 0.5 + 0.2 + 0.1
        ledger.apply_fill(
            FillEvent(
                side="BUY",
                quantity=1.0,
                price=100.0,
                commission=0.5,
                spread_cost=0.2,
                slippage_cost=0.1,
            )
        )
        ledger.apply_fill(
            FillEvent(
                side="SELL",
                quantity=1.0,
                price=100.0,
                commission=0.5,
                spread_cost=0.2,
                slippage_cost=0.1,
            )
        )
        ledger.apply_rollover(0.3)

        snap = ledger.snapshot(mark_price=100.0)

        self.assertAlmostEqual(snap.realized_gross_pnl, 0.0)
        self.assertAlmostEqual(snap.realized_costs_total, 2.0 * per_fill_cost)
        self.assertAlmostEqual(snap.rollover_total, 0.3)
        self.assertAlmostEqual(snap.trading_pnl_net, -(2.0 * per_fill_cost + 0.3))
        self.assertAlmostEqual(snap.cash_balance, 1_000.0 - (2.0 * per_fill_cost + 0.3))

    def test_losing_period_reports_exposure_drawdown_and_recovery(self) -> None:
        ledger = AccountLedger(starting_balance=10_000.0)

        ledger.apply_fill(FillEvent(side="BUY", quantity=2.0, price=100.0, commission=1.0))
        mid_drop = ledger.snapshot(mark_price=95.0)
        self.assertAlmostEqual(mid_drop.exposure_abs, 190.0)
        self.assertGreater(mid_drop.drawdown, 0.0)
        self.assertGreater(mid_drop.max_drawdown, 0.0)

        ledger.apply_fill(FillEvent(side="SELL", quantity=2.0, price=94.0, commission=1.0))
        after_close = ledger.snapshot(mark_price=94.0)

        self.assertAlmostEqual(after_close.position_qty, 0.0)
        self.assertAlmostEqual(after_close.realized_gross_pnl, -12.0)
        self.assertAlmostEqual(after_close.realized_costs_total, 2.0)
        self.assertAlmostEqual(after_close.trading_pnl_net, -14.0)
        self.assertGreaterEqual(after_close.recovery, 0.0)


if __name__ == "__main__":
    unittest.main()
