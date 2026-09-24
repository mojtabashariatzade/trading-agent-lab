"""Acceptance tests for T004 synthetic end-to-end research tournament."""
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from trading_lab.contracts import AccountingState
from trading_lab.execution.kernel import M1Bar, Quote
from trading_lab.research import run_artifact, write_run_artifact
from trading_lab.strategies import ExitConfig, ExitLeague, Side, StrategyProposal
from trading_lab.tournament import (
    DatasetClass,
    Opportunity,
    REQUIRED_INTEGRITY_GATES,
    TournamentConfig,
    TournamentRun,
    TournamentRunner,
)


UTC = timezone.utc


def m15_rows(end_at: datetime, count: int = 21, close: float = 100.0):
    start = end_at - timedelta(minutes=15 * count)
    rows = []
    for i in range(count):
        at = start + timedelta(minutes=15 * i)
        rows.append(
            {
                "start": at.isoformat(),
                "end": (at + timedelta(minutes=15)).isoformat(),
                "open": close,
                "high": close + 0.1,
                "low": close - 0.1,
                "close": close,
                "ticks": 10,
                "gap_before": False,
                "closed": True,
            }
        )
    return rows


def m1(at: datetime, *, bid=100.0, ask=100.2):
    return M1Bar(
        start=at,
        bid_open=bid,
        bid_high=bid + 0.05,
        bid_low=bid - 0.05,
        bid_close=bid,
        ask_open=ask,
        ask_high=ask + 0.05,
        ask_low=ask - 0.05,
        ask_close=ask,
    )


class FixedExpert:
    version = "test-1"

    def __init__(self, strategy_id, side, native_exit=None):
        self.strategy_id = strategy_id
        self.side = side
        self.native_exit = native_exit or ExitConfig(10.0, 10.0)

    def propose(self, rows, *, league=ExitLeague.NATIVE, shared_exit=None):
        generated = datetime.fromisoformat(rows[-1]["end"])
        if league == ExitLeague.SHARED:
            if shared_exit is None:
                raise ValueError("shared exit required")
            exit_config = shared_exit if self.side != Side.PASS else None
        else:
            exit_config = self.native_exit if self.side != Side.PASS else None
        return StrategyProposal(
            strategy_id=self.strategy_id,
            version=self.version,
            side=self.side,
            generated_at=generated,
            expires_at=generated + timedelta(minutes=15),
            reason="FIXED_TEST_PROPOSAL",
            exit_config=exit_config,
            league=league,
        )


class T004TournamentTests(unittest.TestCase):
    @staticmethod
    def _decision_signature(decision):
        return (
            decision.opportunity_id,
            decision.side,
            decision.reason,
            decision.strategy_ids,
            decision.exit_config,
        )

    def test_no_data_is_data_required_not_winner(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        runner = TournamentRunner(experts=[FixedExpert("A", Side.BUY)])
        run = runner.run(
            run_id="no-data",
            dataset_id="fixture-empty",
            opportunities=[
                Opportunity(
                    "O1",
                    at,
                    m15_rows=[],
                    entry_quote=None,
                    m1_bars=[],
                )
            ],
            created_at=at,
        )
        self.assertEqual(run.decisions[0].side, Side.PASS)
        self.assertEqual(run.decisions[0].reason, "DATA_REQUIRED")
        self.assertEqual(run.decisions[0].strategy_ids, ())
        self.assertEqual(run.trades, ())

    def test_risk_veto_is_first_class_and_prevents_trade(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        runner = TournamentRunner(experts=[FixedExpert("A", Side.BUY)])
        run = runner.run(
            run_id="risk-veto",
            dataset_id="fixture-risk",
            opportunities=[
                Opportunity(
                    "O1",
                    at,
                    m15_rows=m15_rows(at),
                    entry_quote=Quote(at, 100.0, 100.2),
                    m1_bars=[m1(at)],
                    risk_allowed=False,
                )
            ],
            created_at=at,
        )
        self.assertEqual(run.decisions[0].side, Side.PASS)
        self.assertEqual(run.decisions[0].reason, "RISK_VETO")
        self.assertEqual(len(run.proposals), 1)
        self.assertEqual(run.trades, ())

    def test_pass_and_direction_conflict_are_first_class(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        base = dict(
            opportunity_id="O1",
            decision_at=at,
            m15_rows=m15_rows(at),
            entry_quote=Quote(at, 100.0, 100.2),
            m1_bars=[m1(at)],
        )

        all_pass = TournamentRunner(experts=[FixedExpert("A", Side.PASS)]).run(
            run_id="all-pass",
            dataset_id="fixture-pass",
            opportunities=[Opportunity(**base)],
            created_at=at,
        )
        self.assertEqual(all_pass.decisions[0].reason, "ALL_PASS")
        self.assertEqual(all_pass.trades, ())

        conflict = TournamentRunner(
            experts=[FixedExpert("A", Side.BUY), FixedExpert("B", Side.SELL)]
        ).run(
            run_id="conflict",
            dataset_id="fixture-conflict",
            opportunities=[Opportunity(**base)],
            created_at=at,
        )
        self.assertEqual(conflict.decisions[0].side, Side.PASS)
        self.assertEqual(conflict.decisions[0].reason, "DIRECTION_CONFLICT")
        self.assertEqual(conflict.trades, ())

    def test_shared_exit_consensus_executes_through_one_kernel(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        runner = TournamentRunner(
            experts=[FixedExpert("A", Side.BUY), FixedExpert("B", Side.BUY)],
            config=TournamentConfig(
                max_holding_minutes=1,
                league=ExitLeague.SHARED,
                shared_exit=ExitConfig(10.0, 10.0),
            ),
        )
        run = runner.run(
            run_id="consensus",
            dataset_id="fixture-consensus",
            opportunities=[
                Opportunity(
                    "O1",
                    at,
                    m15_rows=m15_rows(at),
                    entry_quote=Quote(at, 100.0, 100.2),
                    m1_bars=[m1(at, bid=100.4, ask=100.6)],
                )
            ],
            created_at=at,
        )
        self.assertEqual(run.decisions[0].reason, "SHARED_EXIT_CONSENSUS")
        self.assertEqual(run.decisions[0].strategy_ids, ("A", "B"))
        self.assertEqual(len(run.trades), 1)
        self.assertEqual(run.trades[0].strategy_ids, ("A", "B"))

    def test_single_account_skips_overlapping_opportunity(self):
        t0 = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        expert = FixedExpert("A", Side.BUY)
        runner = TournamentRunner(
            experts=[expert],
            config=TournamentConfig(
                max_holding_minutes=3,
                league=ExitLeague.SHARED,
                shared_exit=ExitConfig(10.0, 10.0),
            ),
        )
        first_m1 = [m1(t0 + timedelta(minutes=i)) for i in range(3)]
        run = runner.run(
            run_id="single-account",
            dataset_id="fixture-overlap",
            opportunities=[
                Opportunity(
                    "O1",
                    t0,
                    m15_rows=m15_rows(t0),
                    entry_quote=Quote(t0, 100.0, 100.2),
                    m1_bars=first_m1,
                ),
                Opportunity(
                    "O2",
                    t0 + timedelta(minutes=1),
                    m15_rows=m15_rows(t0),
                    entry_quote=Quote(t0 + timedelta(minutes=1), 100.0, 100.2),
                    m1_bars=[m1(t0 + timedelta(minutes=1))],
                ),
            ],
            created_at=t0,
        )
        self.assertEqual(len(run.trades), 1)
        self.assertEqual(run.decisions[0].reason, "SINGLE_EXPERT")
        self.assertEqual(run.decisions[1].reason, "POSITION_OPEN")

    def test_default_three_experts_connect_end_to_end_and_can_all_pass(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        runner = TournamentRunner()
        run = runner.run(
            run_id="default-experts",
            dataset_id="fixture-flat",
            opportunities=[
                Opportunity(
                    "O1",
                    at,
                    m15_rows=m15_rows(at, count=25, close=100.0),
                    entry_quote=Quote(at, 100.0, 100.2),
                    m1_bars=[m1(at)],
                )
            ],
            created_at=at,
        )
        self.assertEqual(
            tuple(x[0] for x in run.strategy_versions),
            ("BOLLINGER_REENTRY", "EMA_TREND", "SESSION_RANGE_BREAKOUT"),
        )
        self.assertEqual(run.decisions[0].side, Side.PASS)
        self.assertEqual(run.decisions[0].reason, "ALL_PASS")
        self.assertEqual(len(run.proposals), 3)

    def test_synthetic_run_cannot_be_real_performance(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        run = TournamentRunner(experts=[FixedExpert("A", Side.PASS)]).run(
            run_id="synthetic-only",
            dataset_id="fixture-only",
            opportunities=[
                Opportunity(
                    "O1",
                    at,
                    m15_rows=m15_rows(at),
                    entry_quote=Quote(at, 100.0, 100.2),
                    m1_bars=[m1(at)],
                )
            ],
            created_at=at,
        )
        artifact = run_artifact(run)
        self.assertEqual(artifact["dataset_class"], "SYNTHETIC_TEST_ONLY")
        self.assertFalse(artifact["leaderboard_eligible"])
        self.assertEqual(artifact["integrity_required_gates"], list(REQUIRED_INTEGRITY_GATES))
        self.assertEqual(artifact["integrity_completed_gates"], [])
        self.assertEqual(artifact["integrity_missing_gates"], list(REQUIRED_INTEGRITY_GATES))
        self.assertIn("DATASET_SYNTHETIC_TEST_ONLY", artifact["ranking_blockers"])
        self.assertIn("INTEGRITY_GATES_INCOMPLETE", artifact["ranking_blockers"])
        self.assertIn("SYNTHETIC_TEST_ONLY", artifact["synthetic_warning"])
        with self.assertRaises(RuntimeError):
            run.real_performance_rows()

    def test_real_dataset_is_blocked_until_required_integrity_gates_complete(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        blocked = TournamentRun(
            run_id="real-blocked",
            dataset_id="real-sample",
            dataset_class=DatasetClass.REAL_OBSERVATION,
            created_at=at,
            strategy_versions=(("A", "test-1"),),
            config=TournamentConfig(),
            proposals=(),
            decisions=(),
            trades=(),
            final_cash=0.0,
            integrity_gates_completed=("G06",),
        )
        self.assertFalse(blocked.leaderboard_eligible)
        self.assertEqual(
            blocked.integrity_missing_gates,
            ("G07", "G08", "G16"),
        )
        self.assertEqual(
            blocked.ranking_blockers(),
            ("INTEGRITY_GATES_INCOMPLETE",),
        )

        eligible = TournamentRun(
            run_id="real-eligible",
            dataset_id="real-sample",
            dataset_class=DatasetClass.REAL_OBSERVATION,
            created_at=at,
            strategy_versions=(("A", "test-1"),),
            config=TournamentConfig(),
            proposals=(),
            decisions=(),
            trades=(),
            final_cash=0.0,
            integrity_gates_completed=REQUIRED_INTEGRITY_GATES,
        )
        self.assertTrue(eligible.leaderboard_eligible)
        self.assertEqual(eligible.integrity_missing_gates, ())
        self.assertEqual(eligible.ranking_blockers(), ())

    def test_real_run_execution_path_is_blocked_before_integrity_gates(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        runner = TournamentRunner(experts=[FixedExpert("A", Side.BUY)])
        with self.assertRaisesRegex(
            RuntimeError,
            r"EXECUTION_PATH blocked; missing_integrity_gates=\[G06, G07, G08, G16\]",
        ):
            runner.run(
                run_id="real-precondition-blocked",
                dataset_id="real-sample",
                dataset_class=DatasetClass.REAL_OBSERVATION,
                opportunities=[
                    Opportunity(
                        "O1",
                        at,
                        m15_rows=m15_rows(at),
                        entry_quote=Quote(at, 100.0, 100.2),
                        m1_bars=[m1(at)],
                    )
                ],
                created_at=at,
            )

    def test_real_run_execution_path_allows_when_integrity_gates_complete(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        runner = TournamentRunner(experts=[FixedExpert("A", Side.BUY)])
        run = runner.run(
            run_id="real-precondition-passed",
            dataset_id="real-sample",
            dataset_class=DatasetClass.REAL_OBSERVATION,
            integrity_gates_completed=REQUIRED_INTEGRITY_GATES,
            opportunities=[
                Opportunity(
                    "O1",
                    at,
                    m15_rows=m15_rows(at),
                    entry_quote=Quote(at, 100.0, 100.2),
                    m1_bars=[m1(at)],
                    accounting_state=AccountingState(
                        decision_time_utc=at,
                        account_snapshot_time_utc=at,
                        max_snapshot_age_seconds=60,
                        instrument="GBPJPY",
                        account_currency="JPY",
                        equity=100.0,
                        cash_available=90.0,
                        unrealized_pnl=10.0,
                        min_cash_required=20.0,
                        free_margin=50.0,
                        required_margin=30.0,
                        overlap_detected=False,
                        net_exposure_after_candidate=0.2,
                        max_abs_exposure_limit=1.0,
                        open_positions_same_instrument=0,
                        max_positions_same_instrument=1,
                        rollover_due=1.5,
                        rollover_charged=1.5,
                        mtm_tolerance_abs=1e-9,
                        rollover_tolerance_abs=1e-9,
                        rollover_due_date_utc=date(2026, 1, 5),
                        rollover_charge_date_utc=date(2026, 1, 5),
                    ),
                )
            ],
            created_at=at,
        )
        self.assertEqual(run.dataset_class, DatasetClass.REAL_OBSERVATION)
        self.assertEqual(run.integrity_missing_gates, ())
        self.assertTrue(run.leaderboard_eligible)
        self.assertEqual(run.ranking_blockers(), ())
        self.assertEqual(len(run.trades), 1)

    def test_real_performance_rows_reports_integrity_gate_blockers_clearly(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        blocked = TournamentRun(
            run_id="real-blocked-rows",
            dataset_id="real-sample",
            dataset_class=DatasetClass.REAL_OBSERVATION,
            created_at=at,
            strategy_versions=(("A", "test-1"),),
            config=TournamentConfig(),
            proposals=(),
            decisions=(),
            trades=(),
            final_cash=0.0,
            integrity_gates_completed=("G06",),
        )
        with self.assertRaisesRegex(
            RuntimeError,
            r"REAL_PERFORMANCE_ROWS blocked; missing_integrity_gates=\[G07, G08, G16\]",
        ):
            blocked.real_performance_rows()

    def test_artifact_saves_proposals_decisions_trades_and_manifest(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        run = TournamentRunner(
            experts=[FixedExpert("A", Side.BUY)],
            config=TournamentConfig(
                max_holding_minutes=1,
                shared_exit=ExitConfig(10.0, 10.0),
            ),
        ).run(
            run_id="artifact",
            dataset_id="fixture-artifact",
            opportunities=[
                Opportunity(
                    "O1",
                    at,
                    m15_rows=m15_rows(at),
                    entry_quote=Quote(at, 100.0, 100.2),
                    m1_bars=[m1(at)],
                )
            ],
            created_at=at,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_run_artifact(run, Path(directory) / "run.json")
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["schema"], "trading-agent-lab.tournament-run.v1")
        self.assertEqual(saved["run_id"], "artifact")
        self.assertEqual(len(saved["proposals"]), 1)
        self.assertEqual(len(saved["decisions"]), 1)
        self.assertEqual(len(saved["trades"]), 1)
        self.assertEqual(saved["strategy_versions"], [["A", "test-1"]])

    def test_future_m15_bar_is_rejected(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        future_rows = m15_rows(at + timedelta(minutes=15), count=1)
        runner = TournamentRunner(experts=[FixedExpert("A", Side.PASS)])
        with self.assertRaises(ValueError):
            runner.run(
                run_id="future",
                dataset_id="fixture-future",
                opportunities=[
                    Opportunity(
                        "O1",
                        at,
                        m15_rows=future_rows,
                        entry_quote=Quote(at, 100.0, 100.2),
                        m1_bars=[m1(at)],
                    )
                ],
                created_at=at,
            )

    def test_metamorphic_dropping_future_m1_tail_keeps_entry_decision(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        runner = TournamentRunner(
            experts=[FixedExpert("A", Side.BUY)],
            config=TournamentConfig(
                max_holding_minutes=3,
                league=ExitLeague.SHARED,
                shared_exit=ExitConfig(10.0, 10.0),
            ),
        )

        baseline = runner.run(
            run_id="metamorphic-tail-baseline",
            dataset_id="fixture-tail",
            opportunities=[
                Opportunity(
                    "O1",
                    at,
                    m15_rows=m15_rows(at),
                    entry_quote=Quote(at, 100.0, 100.2),
                    m1_bars=[m1(at + timedelta(minutes=i)) for i in range(3)],
                )
            ],
            created_at=at,
        )

        dropped_tail = runner.run(
            run_id="metamorphic-tail-dropped",
            dataset_id="fixture-tail",
            opportunities=[
                Opportunity(
                    "O1",
                    at,
                    m15_rows=m15_rows(at),
                    entry_quote=Quote(at, 100.0, 100.2),
                    m1_bars=[],
                )
            ],
            created_at=at,
        )

        self.assertEqual(baseline.decisions[0].side, dropped_tail.decisions[0].side)
        self.assertEqual(baseline.decisions[0].reason, dropped_tail.decisions[0].reason)
        self.assertEqual(
            baseline.decisions[0].strategy_ids,
            dropped_tail.decisions[0].strategy_ids,
        )
        self.assertFalse(baseline.trades[0].result.censored)
        self.assertTrue(dropped_tail.trades[0].result.censored)

    def test_metamorphic_truncating_future_tail_keeps_pre_cutoff_decisions(self):
        t0 = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        t1 = t0 + timedelta(minutes=4)
        runner = TournamentRunner(
            experts=[FixedExpert("A", Side.BUY)],
            config=TournamentConfig(
                max_holding_minutes=2,
                league=ExitLeague.SHARED,
                shared_exit=ExitConfig(10.0, 10.0),
            ),
        )

        baseline = runner.run(
            run_id="metamorphic-pre-cutoff-baseline",
            dataset_id="fixture-pre-cutoff",
            opportunities=[
                Opportunity(
                    "O1",
                    t0,
                    m15_rows=m15_rows(t0),
                    entry_quote=Quote(t0, 100.0, 100.2),
                    m1_bars=[m1(t0), m1(t0 + timedelta(minutes=1)), m1(t0 + timedelta(minutes=2))],
                ),
                Opportunity(
                    "O2",
                    t1,
                    m15_rows=m15_rows(t1),
                    entry_quote=Quote(t1, 100.0, 100.2),
                    m1_bars=[m1(t1), m1(t1 + timedelta(minutes=1)), m1(t1 + timedelta(minutes=2))],
                ),
            ],
            created_at=t0,
        )

        truncated = runner.run(
            run_id="metamorphic-pre-cutoff-truncated",
            dataset_id="fixture-pre-cutoff",
            opportunities=[
                Opportunity(
                    "O1",
                    t0,
                    m15_rows=m15_rows(t0),
                    entry_quote=Quote(t0, 100.0, 100.2),
                    m1_bars=[m1(t0), m1(t0 + timedelta(minutes=1))],
                ),
                Opportunity(
                    "O2",
                    t1,
                    m15_rows=m15_rows(t1),
                    entry_quote=Quote(t1, 100.0, 100.2),
                    m1_bars=[m1(t1)],
                ),
            ],
            created_at=t0,
        )

        self.assertEqual(
            [self._decision_signature(x) for x in baseline.decisions],
            [self._decision_signature(x) for x in truncated.decisions],
        )

    def test_metamorphic_open_trade_can_become_censored_after_cutoff(self):
        t0 = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        t_cutoff = t0 + timedelta(minutes=1)
        t_after = t0 + timedelta(minutes=4)
        runner = TournamentRunner(
            experts=[FixedExpert("A", Side.BUY)],
            config=TournamentConfig(
                max_holding_minutes=3,
                league=ExitLeague.SHARED,
                shared_exit=ExitConfig(10.0, 10.0),
            ),
        )

        baseline = runner.run(
            run_id="metamorphic-censor-baseline",
            dataset_id="fixture-censor",
            opportunities=[
                Opportunity(
                    "O1",
                    t0,
                    m15_rows=m15_rows(t0),
                    entry_quote=Quote(t0, 100.0, 100.2),
                    m1_bars=[
                        m1(t0),
                        m1(t0 + timedelta(minutes=1)),
                        m1(t0 + timedelta(minutes=2)),
                        m1(t0 + timedelta(minutes=3)),
                    ],
                ),
                Opportunity(
                    "O2",
                    t_cutoff,
                    m15_rows=m15_rows(t_cutoff),
                    entry_quote=Quote(t_cutoff, 100.0, 100.2),
                    m1_bars=[m1(t_cutoff), m1(t_cutoff + timedelta(minutes=1))],
                ),
                Opportunity(
                    "O3",
                    t_after,
                    m15_rows=m15_rows(t_after),
                    entry_quote=Quote(t_after, 100.0, 100.2),
                    m1_bars=[m1(t_after), m1(t_after + timedelta(minutes=1))],
                ),
            ],
            created_at=t0,
        )

        truncated = runner.run(
            run_id="metamorphic-censor-truncated",
            dataset_id="fixture-censor",
            opportunities=[
                Opportunity(
                    "O1",
                    t0,
                    m15_rows=m15_rows(t0),
                    entry_quote=Quote(t0, 100.0, 100.2),
                    m1_bars=[m1(t0), m1(t0 + timedelta(minutes=1))],
                ),
                Opportunity(
                    "O2",
                    t_cutoff,
                    m15_rows=m15_rows(t_cutoff),
                    entry_quote=Quote(t_cutoff, 100.0, 100.2),
                    m1_bars=[m1(t_cutoff)],
                ),
                Opportunity(
                    "O3",
                    t_after,
                    m15_rows=m15_rows(t_after),
                    entry_quote=Quote(t_after, 100.0, 100.2),
                    m1_bars=[m1(t_after)],
                ),
            ],
            created_at=t0,
        )

        # Entry decisions up to cutoff time remain identical.
        self.assertEqual(
            [self._decision_signature(x) for x in baseline.decisions[:2]],
            [self._decision_signature(x) for x in truncated.decisions[:2]],
        )
        self.assertEqual(baseline.decisions[1].reason, "POSITION_OPEN")

        # Already-open trade may become censored when future bars are removed.
        self.assertFalse(baseline.trades[0].result.censored)
        self.assertTrue(truncated.trades[0].result.censored)

        # Post-cutoff behavior can differ because the censored trade stays open.
        self.assertEqual(baseline.decisions[2].reason, "SINGLE_EXPERT")
        self.assertEqual(truncated.decisions[2].reason, "POSITION_OPEN")


if __name__ == "__main__":
    unittest.main()
