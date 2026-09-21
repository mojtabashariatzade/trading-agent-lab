"""Acceptance tests for T004 synthetic end-to-end research tournament."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_lab.execution.kernel import M1Bar, Quote
from trading_lab.research import run_artifact, write_run_artifact
from trading_lab.strategies import ExitConfig, ExitLeague, Side, StrategyProposal
from trading_lab.tournament import Opportunity, TournamentConfig, TournamentRunner


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
        self.assertIn("SYNTHETIC_TEST_ONLY", artifact["synthetic_warning"])
        with self.assertRaises(RuntimeError):
            run.real_performance_rows()

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


if __name__ == "__main__":
    unittest.main()
