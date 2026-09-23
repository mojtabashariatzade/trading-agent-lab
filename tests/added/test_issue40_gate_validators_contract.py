"""Contract tests for deterministic standalone accounting gate validators."""

from datetime import date
import unittest

from trading_lab.contracts import (
    validate_cash_integrity_gate,
    validate_margin_sufficiency_gate,
    validate_mark_to_market_gate,
    validate_overlap_constraints_gate,
    validate_rollover_validity_gate,
)


class Issue40GateValidatorsContractTests(unittest.TestCase):
    def test_all_gate_validators_return_consistent_result_schema(self):
        checks = [
            validate_mark_to_market_gate(
                equity=100.0,
                cash_available=90.0,
                unrealized_pnl=10.0,
                mtm_tolerance_abs=1e-9,
            ),
            validate_cash_integrity_gate(
                cash_available=90.0,
                min_cash_required=20.0,
            ),
            validate_margin_sufficiency_gate(
                free_margin=50.0,
                required_margin=30.0,
            ),
            validate_overlap_constraints_gate(
                overlap_detected=False,
                net_exposure_after_candidate=100.0,
                max_abs_exposure_limit=200.0,
                open_positions_same_instrument=0,
                max_positions_same_instrument=2,
            ),
            validate_rollover_validity_gate(
                rollover_due=1.5,
                rollover_charged=1.5,
                rollover_due_date_utc=date(2026, 1, 1),
                rollover_charge_date_utc=date(2026, 1, 1),
                rollover_tolerance_abs=1e-9,
            ),
        ]

        for row in checks:
            with self.subTest(gate=row.gate_name):
                self.assertEqual(row.status, "PASS")
                self.assertIsNone(row.error_code)
                self.assertIsNone(row.error_message)
                self.assertIsInstance(row.measured_values, dict)
                self.assertIsInstance(row.thresholds_used, dict)

    def test_gate_validator_failures_return_machine_and_human_reason(self):
        checks = [
            validate_mark_to_market_gate(
                equity=101.0,
                cash_available=90.0,
                unrealized_pnl=10.0,
                mtm_tolerance_abs=1e-9,
            ),
            validate_cash_integrity_gate(
                cash_available=10.0,
                min_cash_required=20.0,
            ),
            validate_margin_sufficiency_gate(
                free_margin=10.0,
                required_margin=30.0,
            ),
            validate_overlap_constraints_gate(
                overlap_detected=True,
                net_exposure_after_candidate=100.0,
                max_abs_exposure_limit=200.0,
                open_positions_same_instrument=0,
                max_positions_same_instrument=2,
            ),
            validate_rollover_validity_gate(
                rollover_due=1.5,
                rollover_charged=0.5,
                rollover_due_date_utc=date(2026, 1, 1),
                rollover_charge_date_utc=date(2026, 1, 1),
                rollover_tolerance_abs=1e-9,
            ),
        ]

        for row in checks:
            with self.subTest(gate=row.gate_name):
                self.assertEqual(row.status, "FAIL")
                self.assertIsInstance(row.error_code, str)
                self.assertTrue(row.error_code)
                self.assertIsInstance(row.error_message, str)
                self.assertTrue(row.error_message)


if __name__ == "__main__":
    unittest.main()
