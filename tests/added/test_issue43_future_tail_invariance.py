"""Regression coverage for Issue #43 future-tail invariance in tournament entry gating."""

import unittest
from datetime import datetime, timedelta, timezone

from trading_lab.execution.kernel import M1Bar, Quote
from trading_lab.strategies import ExitConfig, Side, StrategyProposal
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
        bid_high=bid + 0.01,
        bid_low=bid - 0.01,
        bid_close=bid,
        ask_open=ask,
        ask_high=ask + 0.01,
        ask_low=ask - 0.01,
        ask_close=ask,
    )


class FixedBuyExpert:
    strategy_id = "FIXED_BUY"
    version = "issue43-test"

    def propose(self, rows, *, league, shared_exit):
        generated = datetime.fromisoformat(rows[-1]["end"])
        return StrategyProposal(
            strategy_id=self.strategy_id,
            version=self.version,
            side=Side.BUY,
            generated_at=generated,
            expires_at=generated + timedelta(minutes=15),
            reason="ISSUE43_FIXED_BUY",
            exit_config=shared_exit or ExitConfig(10.0, 10.0),
            league=league,
        )


class Issue43FutureTailInvarianceTests(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 1, 6, 10, 0, tzinfo=UTC)
        self.runner = TournamentRunner(
            experts=[FixedBuyExpert()],
            config=TournamentConfig(max_holding_minutes=2),
        )

    def test_removing_future_tail_keeps_entry_decision_and_censors_trade(self):
        full_tail = [m1(self.at + timedelta(minutes=i)) for i in range(2)]
        opportunity_base = dict(
            opportunity_id="O1",
            decision_at=self.at,
            m15_rows=m15_rows(self.at),
            entry_quote=Quote(self.at, 100.0, 100.2),
            risk_allowed=True,
        )

        run_full = self.runner.run(
            run_id="issue43-full-tail",
            dataset_id="fixture-issue43",
            opportunities=[Opportunity(m1_bars=full_tail, **opportunity_base)],
            created_at=self.at,
        )
        run_empty_tail = self.runner.run(
            run_id="issue43-empty-tail",
            dataset_id="fixture-issue43",
            opportunities=[Opportunity(m1_bars=[], **opportunity_base)],
            created_at=self.at,
        )

        self.assertEqual(run_full.decisions[0].side, run_empty_tail.decisions[0].side)
        self.assertEqual(run_full.decisions[0].reason, run_empty_tail.decisions[0].reason)
        self.assertEqual(
            run_full.decisions[0].strategy_ids,
            run_empty_tail.decisions[0].strategy_ids,
        )

        self.assertEqual(len(run_empty_tail.trades), 1)
        self.assertTrue(run_empty_tail.trades[0].result.censored)
        self.assertIsNone(run_empty_tail.trades[0].result.net_pnl)

    def test_censored_position_blocks_later_overlap(self):
        t1 = self.at + timedelta(minutes=1)
        run = self.runner.run(
            run_id="issue43-overlap",
            dataset_id="fixture-issue43",
            opportunities=[
                Opportunity(
                    opportunity_id="O1",
                    decision_at=self.at,
                    m15_rows=m15_rows(self.at),
                    entry_quote=Quote(self.at, 100.0, 100.2),
                    m1_bars=[],
                ),
                Opportunity(
                    opportunity_id="O2",
                    decision_at=t1,
                    m15_rows=m15_rows(t1),
                    entry_quote=Quote(t1, 100.0, 100.2),
                    m1_bars=[m1(t1)],
                ),
            ],
            created_at=self.at,
        )

        self.assertEqual(run.decisions[0].reason, "SINGLE_EXPERT")
        self.assertEqual(run.decisions[1].reason, "POSITION_OPEN")
        self.assertEqual(len(run.trades), 1)
        self.assertTrue(run.trades[0].result.censored)

    def test_missing_entry_inputs_still_return_data_required(self):
        no_quote = self.runner.run(
            run_id="issue43-no-quote",
            dataset_id="fixture-issue43",
            opportunities=[
                Opportunity(
                    opportunity_id="O1",
                    decision_at=self.at,
                    m15_rows=m15_rows(self.at),
                    entry_quote=None,
                    m1_bars=[m1(self.at)],
                )
            ],
            created_at=self.at,
        )
        self.assertEqual(no_quote.decisions[0].reason, "DATA_REQUIRED")

        no_m15 = self.runner.run(
            run_id="issue43-no-m15",
            dataset_id="fixture-issue43",
            opportunities=[
                Opportunity(
                    opportunity_id="O1",
                    decision_at=self.at,
                    m15_rows=[],
                    entry_quote=Quote(self.at, 100.0, 100.2),
                    m1_bars=[m1(self.at)],
                )
            ],
            created_at=self.at,
        )
        self.assertEqual(no_m15.decisions[0].reason, "DATA_REQUIRED")


if __name__ == "__main__":
    unittest.main()
