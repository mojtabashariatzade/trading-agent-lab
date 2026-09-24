"""Regression tests for Issue #56: account-state gates must block replay/ranking paths."""

import unittest
from datetime import date, datetime, timedelta, timezone

from trading_lab.contracts import AccountingState
from trading_lab.execution.kernel import M1Bar, Quote
from trading_lab.strategies import ExitConfig, ExitLeague, Side, StrategyProposal
from trading_lab.tournament import DatasetClass, Opportunity, TournamentConfig, TournamentRunner

UTC = timezone.utc


class FixedExpert:
    version = "test-issue56"

    def __init__(self, strategy_id: str, side: Side):
        self.strategy_id = strategy_id
        self.side = side

    def propose(self, rows, *, league=ExitLeague.NATIVE, shared_exit=None):
        generated = datetime.fromisoformat(rows[-1]["end"])
        if league == ExitLeague.SHARED:
            if shared_exit is None:
                raise ValueError("shared exit required")
            exit_config = shared_exit if self.side != Side.PASS else None
        else:
            exit_config = ExitConfig(10.0, 10.0) if self.side != Side.PASS else None
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


def accounting_state_for(decision_at: datetime, **overrides) -> AccountingState:
    base = dict(
        decision_time_utc=decision_at,
        account_snapshot_time_utc=decision_at,
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
    )
    base.update(overrides)
    return AccountingState(**base)


class Issue56AccountStateReplayGateTests(unittest.TestCase):
    def test_real_observation_requires_accounting_snapshot(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        runner = TournamentRunner(experts=[FixedExpert("A", Side.BUY)])

        with self.assertRaisesRegex(RuntimeError, "missing_accounting_state_snapshot"):
            runner.run(
                run_id="issue56-missing-accounting",
                dataset_id="fixture-issue56",
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
                dataset_class=DatasetClass.REAL_OBSERVATION,
                integrity_gates_completed=("G06", "G07", "G08", "G16"),
            )

    def test_failed_accounting_gate_blocks_replay_before_ranking(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        runner = TournamentRunner(experts=[FixedExpert("A", Side.BUY)])

        run = runner.run(
            run_id="issue56-cash-block",
            dataset_id="fixture-issue56",
            opportunities=[
                Opportunity(
                    "O1",
                    at,
                    m15_rows=m15_rows(at),
                    entry_quote=Quote(at, 100.0, 100.2),
                    m1_bars=[m1(at)],
                    accounting_state=accounting_state_for(
                        at,
                        equity=20.0,
                        cash_available=10.0,
                    ),
                )
            ],
            created_at=at,
            dataset_class=DatasetClass.REAL_OBSERVATION,
            integrity_gates_completed=("G06", "G07", "G08", "G16"),
        )

        self.assertEqual(run.decisions[0].side, Side.PASS)
        self.assertEqual(run.decisions[0].reason, "ACCOUNTING_BLOCK_CASH")
        self.assertEqual(run.proposals, ())
        self.assertEqual(run.trades, ())

    def test_passing_accounting_state_allows_normal_replay_flow(self):
        at = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
        runner = TournamentRunner(
            experts=[FixedExpert("A", Side.BUY)],
            config=TournamentConfig(
                max_holding_minutes=1,
                league=ExitLeague.SHARED,
                shared_exit=ExitConfig(10.0, 10.0),
            ),
        )

        run = runner.run(
            run_id="issue56-pass",
            dataset_id="fixture-issue56",
            opportunities=[
                Opportunity(
                    "O1",
                    at,
                    m15_rows=m15_rows(at),
                    entry_quote=Quote(at, 100.0, 100.2),
                    m1_bars=[m1(at)],
                    accounting_state=accounting_state_for(at),
                )
            ],
            created_at=at,
            dataset_class=DatasetClass.REAL_OBSERVATION,
            integrity_gates_completed=("G06", "G07", "G08", "G16"),
        )

        self.assertEqual(run.decisions[0].reason, "SINGLE_EXPERT")
        self.assertEqual(len(run.proposals), 1)
        self.assertEqual(len(run.trades), 1)


if __name__ == "__main__":
    unittest.main()
