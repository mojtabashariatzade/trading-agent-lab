from __future__ import annotations

import unittest

from trading_lab.accounting import AccountLedger, FillEvent, build_ledger_evaluation_artifact


class Issue75LedgerReportingTests(unittest.TestCase):
    def test_no_trade_summary_separates_external_cashflows(self) -> None:
        ledger = AccountLedger(starting_balance=5_000.0)
        ledger.apply_cashflow(600.0)
        ledger.apply_cashflow(-100.0)

        artifact = build_ledger_evaluation_artifact(
            snapshots=[ledger.snapshot(mark_price=150.0)]
        )

        self.assertEqual(artifact["schema_version"], "ledger-evaluation.v1")
        self.assertEqual(artifact["snapshot_count"], 1)
        latest = artifact["latest"]
        self.assertAlmostEqual(latest["trading_pnl_net"], 0.0)
        self.assertAlmostEqual(latest["external_cashflow_total"], 500.0)
        self.assertAlmostEqual(latest["equity_total"], 5_500.0)
        self.assertAlmostEqual(latest["cash_balance"], 5_500.0)

        cashflow = artifact["governance_summary"]["cashflow"]
        self.assertAlmostEqual(cashflow["trading_equity_ex_cashflows"], 5_000.0)
        self.assertTrue(artifact["governance_summary"]["invariants"]["equity_reconciliation_ok"])

    def test_losing_period_exposes_drawdown_and_recovery_fields(self) -> None:
        ledger = AccountLedger(starting_balance=10_000.0)
        ledger.apply_fill(FillEvent(side="BUY", quantity=2.0, price=100.0, commission=1.0))
        drop = ledger.snapshot(mark_price=95.0)
        ledger.apply_fill(FillEvent(side="SELL", quantity=2.0, price=94.0, commission=1.0))
        close = ledger.snapshot(mark_price=94.0)

        artifact = build_ledger_evaluation_artifact(snapshots=[drop, close])

        latest = artifact["latest"]
        self.assertAlmostEqual(latest["trading_pnl_net"], -14.0)
        self.assertGreater(latest["max_drawdown"], 0.0)
        self.assertGreaterEqual(latest["recovery"], 0.0)
        self.assertGreater(artifact["risk"]["worst_drawdown"], 0.0)

    def test_cost_stress_consistency_in_reporting_artifact(self) -> None:
        ledger = AccountLedger(starting_balance=1_000.0)
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

        artifact = build_ledger_evaluation_artifact(
            snapshots=[ledger.snapshot(mark_price=100.0)]
        )

        latest = artifact["latest"]
        self.assertAlmostEqual(latest["realized_gross_pnl"], 0.0)
        self.assertAlmostEqual(latest["realized_costs_total"], 1.6)
        self.assertAlmostEqual(latest["rollover_total"], 0.3)
        self.assertAlmostEqual(latest["trading_pnl_net"], -1.9)

        perf = artifact["governance_summary"]["trading_performance"]
        self.assertAlmostEqual(perf["realized_costs_total"], 1.6)
        self.assertAlmostEqual(perf["trading_pnl_net"], -1.9)


if __name__ == "__main__":
    unittest.main()
