from __future__ import annotations

import unittest

from trading_lab.accounting import AccountLedger, FillEvent, build_ledger_evaluation_artifact


class Issue45ReportingRiskControlsTests(unittest.TestCase):
    def test_unsupported_risk_controls_and_channels_remain_unset(self) -> None:
        ledger = AccountLedger(starting_balance=10_000.0)
        ledger.apply_fill(FillEvent(side="BUY", quantity=1.0, price=100.0))

        artifact = build_ledger_evaluation_artifact(
            snapshots=[ledger.snapshot(mark_price=101.0)]
        )

        risk_controls = artifact["governance_summary"]["risk_controls"]
        self.assertEqual(risk_controls["position_sizing"], "UNSET")
        self.assertEqual(risk_controls["daily_loss_limit"], "UNSET")
        self.assertEqual(risk_controls["account_loss_limit"], "UNSET")
        self.assertEqual(risk_controls["max_concurrent_positions"], "UNSET")
        self.assertEqual(risk_controls["emergency_stop"], "UNSET")

        result_channels = artifact["governance_summary"]["result_channels"]
        for channel in ("hypothetical", "out_of_sample", "paper", "live"):
            self.assertEqual(result_channels[channel]["status"], "UNSET")
            self.assertEqual(result_channels[channel]["period"], "UNSET")
            self.assertEqual(result_channels[channel]["source"], "UNSET")
            self.assertEqual(result_channels[channel]["revision"], "UNSET")

    def test_explicit_risk_controls_and_channels_are_preserved(self) -> None:
        ledger = AccountLedger(starting_balance=10_000.0)
        ledger.apply_fill(FillEvent(side="SELL", quantity=2.0, price=150.0))

        artifact = build_ledger_evaluation_artifact(
            snapshots=[ledger.snapshot(mark_price=149.0)],
            risk_controls={
                "position_sizing": "fixed_fractional_1pct",
                "daily_loss_limit": 250.0,
                "account_loss_limit": 1_500.0,
                "max_concurrent_positions": 3,
                "emergency_stop": "manual_and_auto_kill_switch",
            },
            result_channels={
                "paper": {
                    "status": "AVAILABLE",
                    "period": "2026-Q3",
                    "source": "paper-execution-sim",
                    "revision": "r1",
                }
            },
        )

        risk_controls = artifact["governance_summary"]["risk_controls"]
        self.assertEqual(risk_controls["position_sizing"], "fixed_fractional_1pct")
        self.assertEqual(risk_controls["daily_loss_limit"], 250.0)
        self.assertEqual(risk_controls["account_loss_limit"], 1_500.0)
        self.assertEqual(risk_controls["max_concurrent_positions"], 3)
        self.assertEqual(risk_controls["emergency_stop"], "manual_and_auto_kill_switch")

        channels = artifact["governance_summary"]["result_channels"]
        self.assertEqual(channels["paper"]["status"], "AVAILABLE")
        self.assertEqual(channels["paper"]["period"], "2026-Q3")
        self.assertEqual(channels["paper"]["source"], "paper-execution-sim")
        self.assertEqual(channels["paper"]["revision"], "r1")

        # Unspecified channels/fields must stay UNSET.
        self.assertEqual(channels["live"]["status"], "UNSET")
        self.assertEqual(channels["hypothetical"]["source"], "UNSET")


if __name__ == "__main__":
    unittest.main()
