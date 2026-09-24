"""Issue #40 accounting-integrity gates before strategy ranking."""

from datetime import date, datetime, timedelta, timezone
import unittest

from trading_lab.contracts import AccountingState, Assessment, Side, decide


class _ExplodingAssessments:
    """Raises if ranking tries to consume assessments."""

    def __iter__(self):
        raise AssertionError("Ranking iterable should not be consumed when blocked")


class _CountingAssessments:
    """Tracks whether ranking iteration happened."""

    def __init__(self, rows):
        self._rows = list(rows)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        return iter(self._rows)


class Issue40AccountingGateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assessments = [
            Assessment(
                strategy_id="S01",
                side=Side.BUY,
                generated_at=self.now - timedelta(minutes=1),
                expires_at=self.now + timedelta(minutes=14),
                expected_net_r=0.60,
            ),
            Assessment(
                strategy_id="S02",
                side=Side.SELL,
                generated_at=self.now - timedelta(minutes=1),
                expires_at=self.now + timedelta(minutes=14),
                expected_net_r=0.20,
            ),
        ]

    def _choose(self, accounting: AccountingState, assessments=None):
        return decide(
            assessments if assessments is not None else self.assessments,
            self.now,
            data_healthy=True,
            risk_allowed=True,
            position_open=False,
            accounting=accounting,
        )

    def _base_accounting(self, **overrides) -> AccountingState:
        values = {
            "decision_time_utc": self.now,
            "account_snapshot_time_utc": self.now,
            "max_snapshot_age_seconds": 300,
            "instrument": "GBPJPY",
            "account_currency": "JPY",
            "equity": 100.0,
            "cash_available": 90.0,
            "unrealized_pnl": 10.0,
            "min_cash_required": 20.0,
            "free_margin": 50.0,
            "required_margin": 30.0,
            "overlap_detected": False,
            "net_exposure_after_candidate": 0.0,
            "max_abs_exposure_limit": 1_000_000.0,
            "open_positions_same_instrument": 0,
            "max_positions_same_instrument": 2,
            "rollover_due": 1.5,
            "rollover_charged": 1.5,
            "rollover_due_date_utc": date(2026, 1, 1),
            "rollover_charge_date_utc": date(2026, 1, 1),
        }
        values.update(overrides)
        return AccountingState(**values)

    def test_each_gate_failure_returns_expected_block_code_and_message(self):
        scenarios = [
            (
                "mtm",
                self._base_accounting(equity=101.0),
                "ACCOUNTING_BLOCK_MTM",
                "MTM mismatch: equity must equal cash_available + unrealized_pnl within tolerance",
            ),
            (
                "cash",
                self._base_accounting(cash_available=10.0, unrealized_pnl=90.0),
                "ACCOUNTING_BLOCK_CASH",
                "Insufficient cash: cash_available is below min_cash_required",
            ),
            (
                "margin",
                self._base_accounting(free_margin=10.0),
                "ACCOUNTING_BLOCK_MARGIN",
                "Insufficient free margin: free_margin is below required_margin",
            ),
            (
                "overlap",
                self._base_accounting(overlap_detected=True),
                "ACCOUNTING_BLOCK_OVERLAP",
                "Exposure overlap/limit violation for candidate instrument",
            ),
            (
                "rollover",
                self._base_accounting(rollover_charged=0.5),
                "ACCOUNTING_BLOCK_ROLLOVER",
                "Rollover mismatch: amount/date inconsistent with due rollover",
            ),
        ]

        for name, accounting, expected_code, expected_message in scenarios:
            with self.subTest(gate=name):
                decision = self._choose(accounting)
                evaluation = accounting.evaluate_gates()
                self.assertEqual(decision.side, Side.PASS)
                self.assertEqual(decision.reason, expected_code)
                self.assertIsNone(decision.strategy_id)
                self.assertTrue(evaluation.blocked)
                self.assertEqual(evaluation.block_error_code, expected_code)
                self.assertEqual(evaluation.block_error_message, expected_message)

    def test_blocked_cases_do_not_invoke_ranking_iteration(self):
        blocked_states = [
            self._base_accounting(equity=101.0),
            self._base_accounting(cash_available=10.0, unrealized_pnl=90.0),
            self._base_accounting(free_margin=10.0),
            self._base_accounting(overlap_detected=True),
            self._base_accounting(rollover_charged=0.5),
        ]

        for accounting in blocked_states:
            with self.subTest(reason=accounting.block_reason()):
                result = self._choose(accounting, assessments=_ExplodingAssessments())
                self.assertEqual(result.side, Side.PASS)
                self.assertIsNotNone(result.reason)
                self.assertIsNone(result.strategy_id)

    def test_first_failure_short_circuits_in_fixed_order_and_marks_skips(self):
        accounting = self._base_accounting(
            cash_available=10.0,
            unrealized_pnl=90.0,
            free_margin=10.0,
            overlap_detected=True,
            rollover_charged=0.5,
        )
        decision = self._choose(accounting)
        evaluation = accounting.evaluate_gates()

        self.assertEqual(decision.side, Side.PASS)
        self.assertEqual(decision.reason, "ACCOUNTING_BLOCK_CASH")
        statuses = {row.gate_name: row.status for row in evaluation.gate_results}
        self.assertEqual(statuses["INPUT_PRECHECK"], "PASS")
        self.assertEqual(statuses["MTM"], "PASS")
        self.assertEqual(statuses["CASH"], "FAIL")
        self.assertEqual(statuses["MARGIN"], "SKIP")
        self.assertEqual(statuses["OVERLAP"], "SKIP")
        self.assertEqual(statuses["ROLLOVER"], "SKIP")

    def test_positive_path_proceeds_to_ranking(self):
        tracked = _CountingAssessments(self.assessments)
        result = self._choose(self._base_accounting(), assessments=tracked)
        self.assertEqual(tracked.iterations, 1)
        self.assertEqual(result.side, Side.BUY)
        self.assertEqual(result.reason, "ELIGIBLE_PROPOSAL")
        self.assertEqual(result.strategy_id, "S01")

    def test_nonfinite_numeric_values_are_rejected_deterministically(self):
        for field, value in (("equity", float("nan")), ("cash_available", float("inf"))):
            with self.subTest(field=field, value=value):
                accounting = self._base_accounting(**{field: value})
                decision = self._choose(accounting)
                evaluation = accounting.evaluate_gates()
                self.assertEqual(decision.side, Side.PASS)
                self.assertEqual(decision.reason, "ACCOUNTING_BLOCK_INPUT_NONFINITE")
                self.assertEqual(evaluation.block_error_code, "ACCOUNTING_BLOCK_INPUT_NONFINITE")

    def test_missing_required_snapshot_field_blocks_before_gate_one(self):
        accounting = self._base_accounting(instrument="")
        decision = self._choose(accounting)
        evaluation = accounting.evaluate_gates()
        self.assertEqual(decision.reason, "ACCOUNTING_BLOCK_INPUT_MISSING")
        self.assertTrue(evaluation.blocked)
        self.assertEqual(evaluation.block_error_code, "ACCOUNTING_BLOCK_INPUT_MISSING")
        statuses = {row.gate_name: row.status for row in evaluation.gate_results}
        self.assertEqual(statuses["INPUT_PRECHECK"], "FAIL")
        self.assertEqual(statuses["MTM"], "SKIP")

    def test_stale_snapshot_blocks_with_stale_code(self):
        accounting = self._base_accounting(
            account_snapshot_time_utc=self.now - timedelta(minutes=10),
            max_snapshot_age_seconds=60,
        )
        decision = self._choose(accounting)
        self.assertEqual(decision.side, Side.PASS)
        self.assertEqual(decision.reason, "ACCOUNTING_BLOCK_SNAPSHOT_STALE")

    def test_future_snapshot_blocks_with_future_code(self):
        accounting = self._base_accounting(
            account_snapshot_time_utc=self.now + timedelta(seconds=1),
            max_snapshot_age_seconds=60,
        )
        decision = self._choose(accounting, assessments=_ExplodingAssessments())
        evaluation = accounting.evaluate_gates()
        self.assertEqual(decision.side, Side.PASS)
        self.assertEqual(decision.reason, "ACCOUNTING_BLOCK_SNAPSHOT_FUTURE")
        self.assertIsNone(decision.strategy_id)
        self.assertTrue(evaluation.blocked)
        self.assertEqual(evaluation.block_error_code, "ACCOUNTING_BLOCK_SNAPSHOT_FUTURE")
        statuses = {row.gate_name: row.status for row in evaluation.gate_results}
        self.assertEqual(statuses["INPUT_PRECHECK"], "FAIL")
        self.assertEqual(statuses["MTM"], "SKIP")

    def test_negative_min_cash_required_is_invalid_and_blocks_cash_gate(self):
        accounting = self._base_accounting(min_cash_required=-1.0)
        decision = self._choose(accounting, assessments=_ExplodingAssessments())
        evaluation = accounting.evaluate_gates()
        self.assertEqual(decision.side, Side.PASS)
        self.assertEqual(decision.reason, "ACCOUNTING_BLOCK_CASH")
        self.assertIsNone(decision.strategy_id)
        self.assertTrue(evaluation.blocked)
        self.assertEqual(evaluation.block_error_code, "ACCOUNTING_BLOCK_CASH")

    def test_negative_required_margin_is_invalid_and_blocks_margin_gate(self):
        accounting = self._base_accounting(required_margin=-1.0)
        decision = self._choose(accounting, assessments=_ExplodingAssessments())
        evaluation = accounting.evaluate_gates()
        self.assertEqual(decision.side, Side.PASS)
        self.assertEqual(decision.reason, "ACCOUNTING_BLOCK_MARGIN")
        self.assertIsNone(decision.strategy_id)
        self.assertTrue(evaluation.blocked)
        self.assertEqual(evaluation.block_error_code, "ACCOUNTING_BLOCK_MARGIN")

    def test_negative_zero_cash_is_allowed_when_at_or_above_min_cash_required(self):
        accounting = self._base_accounting(
            equity=10.0,
            cash_available=-0.0,
            unrealized_pnl=10.0,
            min_cash_required=0.0,
        )
        decision = self._choose(accounting)
        evaluation = accounting.evaluate_gates()
        self.assertEqual(decision.side, Side.BUY)
        self.assertEqual(decision.reason, "ELIGIBLE_PROPOSAL")
        self.assertEqual(decision.strategy_id, "S01")
        statuses = {row.gate_name: row.status for row in evaluation.gate_results}
        self.assertEqual(statuses["CASH"], "PASS")

    def test_impossible_exposure_or_position_count_blocks_overlap_gate(self):
        by_exposure = self._choose(
            self._base_accounting(net_exposure_after_candidate=2_000_000.0, max_abs_exposure_limit=1_000.0)
        )
        by_position_count = self._choose(
            self._base_accounting(open_positions_same_instrument=3, max_positions_same_instrument=2)
        )
        self.assertEqual(by_exposure.reason, "ACCOUNTING_BLOCK_OVERLAP")
        self.assertEqual(by_position_count.reason, "ACCOUNTING_BLOCK_OVERLAP")

    def test_rollover_date_mismatch_blocks_even_when_amount_matches(self):
        result = self._choose(
            self._base_accounting(
                rollover_due=1.5,
                rollover_charged=1.5,
                rollover_due_date_utc=date(2026, 1, 1),
                rollover_charge_date_utc=date(2026, 1, 2),
            )
        )
        self.assertEqual(result.side, Side.PASS)
        self.assertEqual(result.reason, "ACCOUNTING_BLOCK_ROLLOVER")

    def test_same_inputs_produce_identical_decision_and_gate_evaluation(self):
        scenarios = [
            ("mtm_fail", self._base_accounting(equity=101.0)),
            ("cash_fail", self._base_accounting(cash_available=10.0, unrealized_pnl=90.0)),
            ("margin_fail", self._base_accounting(free_margin=10.0)),
            ("overlap_fail", self._base_accounting(overlap_detected=True)),
            ("rollover_fail", self._base_accounting(rollover_charged=0.5)),
            ("all_pass", self._base_accounting()),
        ]

        for name, accounting in scenarios:
            with self.subTest(scenario=name):
                snapshots = []
                for _ in range(3):
                    decision = self._choose(accounting)
                    evaluation = accounting.evaluate_gates()
                    snapshots.append(
                        (
                            decision.side,
                            decision.reason,
                            decision.strategy_id,
                            evaluation.blocked,
                            evaluation.block_error_code,
                            evaluation.block_error_message,
                            tuple((row.gate_name, row.status, row.error_code) for row in evaluation.gate_results),
                        )
                    )
                self.assertEqual(snapshots[0], snapshots[1])
                self.assertEqual(snapshots[1], snapshots[2])


if __name__ == "__main__":
    unittest.main()
