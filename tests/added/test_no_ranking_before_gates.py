"""Evidence-backed checks that ranking is gated by integrity outcomes."""

from datetime import datetime, timedelta, timezone
import unittest

from trading_lab.contracts import AccountingState, Assessment, Side, decide
from trading_lab.tournament import DatasetClass, REQUIRED_INTEGRITY_GATES, TournamentConfig, TournamentRun


class _ExplodingAssessments:
    """Raises if ranking tries to consume assessments while a gate is failing."""

    def __iter__(self):
        raise AssertionError("Ranking iterable should not be consumed before gate pass")


class _CountingAssessments:
    """Records whether ranking iteration actually happened."""

    def __init__(self, rows):
        self._rows = list(rows)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        return iter(self._rows)


class NoRankingBeforeGatesTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assessments = [
            Assessment(
                strategy_id="S01",
                side=Side.BUY,
                generated_at=self.now - timedelta(minutes=1),
                expires_at=self.now + timedelta(minutes=14),
                expected_net_r=0.60,
            )
        ]

    def test_gate_failure_blocks_ranking_iteration(self):
        failing_accounting = AccountingState(
            equity=101.0,
            cash_available=90.0,
            unrealized_pnl=10.0,
            min_cash_required=20.0,
            free_margin=50.0,
            required_margin=30.0,
            overlap_detected=False,
            rollover_due=1.5,
            rollover_charged=1.5,
        )

        decision = decide(
            _ExplodingAssessments(),
            self.now,
            data_healthy=True,
            risk_allowed=True,
            position_open=False,
            accounting=failing_accounting,
        )

        self.assertEqual(decision.side, Side.PASS)
        self.assertEqual(decision.reason, "ACCOUNTING_BLOCK_MTM")
        self.assertIsNone(decision.strategy_id)

    def test_missing_integrity_gate_state_blocks_ranking(self):
        run = TournamentRun(
            run_id="real-missing-gates",
            dataset_id="real-sample",
            dataset_class=DatasetClass.REAL_OBSERVATION,
            created_at=self.now,
            strategy_versions=(("S01", "test-1"),),
            config=TournamentConfig(),
            proposals=(),
            decisions=(),
            trades=(),
            final_cash=0.0,
        )

        self.assertFalse(run.leaderboard_eligible)
        self.assertEqual(run.integrity_missing_gates, REQUIRED_INTEGRITY_GATES)
        self.assertEqual(run.ranking_blockers(), ("INTEGRITY_GATES_INCOMPLETE",))

    def test_passed_integrity_gates_allow_ranking(self):
        run = TournamentRun(
            run_id="real-all-gates",
            dataset_id="real-sample",
            dataset_class=DatasetClass.REAL_OBSERVATION,
            created_at=self.now,
            strategy_versions=(("S01", "test-1"),),
            config=TournamentConfig(),
            proposals=(),
            decisions=(),
            trades=(),
            final_cash=0.0,
            integrity_gates_completed=REQUIRED_INTEGRITY_GATES,
        )

        self.assertTrue(run.leaderboard_eligible)
        self.assertEqual(run.integrity_missing_gates, ())
        self.assertEqual(run.ranking_blockers(), ())

    def test_ranking_proceeds_after_successful_gate_completion(self):
        passing_accounting = AccountingState(
            equity=100.0,
            cash_available=90.0,
            unrealized_pnl=10.0,
            min_cash_required=20.0,
            free_margin=50.0,
            required_margin=30.0,
            overlap_detected=False,
            rollover_due=1.5,
            rollover_charged=1.5,
        )
        tracked = _CountingAssessments(self.assessments)

        decision = decide(
            tracked,
            self.now,
            data_healthy=True,
            risk_allowed=True,
            position_open=False,
            accounting=passing_accounting,
        )

        self.assertEqual(tracked.iterations, 1)
        self.assertEqual(decision.side, Side.BUY)
        self.assertEqual(decision.reason, "ELIGIBLE_PROPOSAL")
        self.assertEqual(decision.strategy_id, "S01")

    def test_blocked_gate_evaluation_contains_aggregated_failure_reasons(self):
        failing_accounting = AccountingState(
            equity=101.0,
            cash_available=90.0,
            unrealized_pnl=10.0,
            min_cash_required=20.0,
            free_margin=50.0,
            required_margin=30.0,
            overlap_detected=False,
            rollover_due=1.5,
            rollover_charged=1.5,
        )

        evaluation = failing_accounting.evaluate_gates()

        self.assertTrue(evaluation.blocked)
        self.assertEqual(
            evaluation.failure_reasons,
            ((
                "MTM",
                "ACCOUNTING_BLOCK_MTM",
                "MTM mismatch: equity must equal cash_available + unrealized_pnl within tolerance",
            ),),
        )

    def test_blocked_gate_emits_trace_and_marks_ranking_not_executed(self):
        failing_accounting = AccountingState(
            equity=101.0,
            cash_available=90.0,
            unrealized_pnl=10.0,
            min_cash_required=20.0,
            free_margin=50.0,
            required_margin=30.0,
            overlap_detected=False,
            rollover_due=1.5,
            rollover_charged=1.5,
        )
        trace: list[dict[str, object]] = []

        decision = decide(
            _ExplodingAssessments(),
            self.now,
            data_healthy=True,
            risk_allowed=True,
            position_open=False,
            accounting=failing_accounting,
            trace_sink=trace,
        )

        self.assertEqual(decision.side, Side.PASS)
        self.assertEqual(decision.reason, "ACCOUNTING_BLOCK_MTM")
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]["blocked"], True)
        self.assertEqual(trace[0]["ranking_executed"], False)
        self.assertEqual(trace[0]["block_error_code"], "ACCOUNTING_BLOCK_MTM")
        self.assertEqual(
            trace[0]["failure_reasons"],
            [
                {
                    "gate_name": "MTM",
                    "error_code": "ACCOUNTING_BLOCK_MTM",
                    "error_message": "MTM mismatch: equity must equal cash_available + unrealized_pnl within tolerance",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
