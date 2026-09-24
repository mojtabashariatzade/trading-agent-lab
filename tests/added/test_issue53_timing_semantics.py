"""Regression tests for Issue #53 canonical timing semantics across replay paths."""

import unittest
from datetime import datetime, timedelta, timezone

from trading_lab.execution.kernel import ExecutionKernel, M1Bar, Quote, SinglePositionAccount, TradeRequest
from trading_lab.strategies import ExitConfig, ExitLeague, Side, StrategyProposal
from trading_lab.tournament import Opportunity, TournamentConfig, TournamentRunner


UTC = timezone.utc


def m15_rows(end_at: datetime, count: int = 21):
    start = end_at - timedelta(minutes=15 * count)
    rows = []
    for i in range(count):
        at = start + timedelta(minutes=15 * i)
        rows.append(
            {
                "start": at.isoformat(),
                "end": (at + timedelta(minutes=15)).isoformat(),
                "open": 100.0,
                "high": 100.1,
                "low": 99.9,
                "close": 100.0,
                "ticks": 10,
                "gap_before": False,
                "closed": True,
            }
        )
    return rows


def m1(at: datetime, *, bid=100.0, ask=100.2, spread=0.2):
    ask = bid + spread if ask is None else ask
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


class FixedBuyExpert:
    strategy_id = "FIXED_BUY"
    version = "issue53"

    def propose(self, rows, *, league=ExitLeague.NATIVE, shared_exit=None):
        generated = datetime.fromisoformat(rows[-1]["end"])
        exit_config = shared_exit if league == ExitLeague.SHARED else ExitConfig(10.0, 10.0)
        return StrategyProposal(
            strategy_id=self.strategy_id,
            version=self.version,
            side=Side.BUY,
            generated_at=generated,
            expires_at=generated + timedelta(minutes=15),
            reason="FIXED",
            exit_config=exit_config,
            league=league,
        )


class Issue53TimingSemanticsTests(unittest.TestCase):
    def test_quote_not_available_at_decision_is_data_required(self):
        t0 = datetime(2026, 1, 7, 10, 0, tzinfo=UTC)
        runner = TournamentRunner(experts=[FixedBuyExpert()])
        run = runner.run(
            run_id="issue53-unavailable-quote",
            dataset_id="fixture-issue53",
            opportunities=[
                Opportunity(
                    opportunity_id="O1",
                    decision_at=t0,
                    m15_rows=m15_rows(t0),
                    entry_quote=Quote(t0, 100.0, 100.2, available_at=t0 + timedelta(minutes=1)),
                    m1_bars=[m1(t0), m1(t0 + timedelta(minutes=1))],
                )
            ],
            created_at=t0,
        )
        self.assertEqual(run.decisions[0].reason, "DATA_REQUIRED")
        self.assertEqual(run.trades, ())

    def test_fill_ready_latency_skips_pre_fill_bar(self):
        t0 = datetime(2026, 1, 7, 10, 0, tzinfo=UTC)
        kernel = ExecutionKernel()
        request = TradeRequest(
            side="BUY",
            stop_distance=2.0,
            target_distance=0.1,
            timeout_at=t0 + timedelta(minutes=3),
            entry_latency_minutes=1,
        )
        result = kernel.execute(
            request,
            Quote(t0, 100.0, 100.2),
            [
                M1Bar(
                    start=t0,
                    bid_open=100.0,
                    bid_high=100.4,
                    bid_low=99.9,
                    bid_close=100.1,
                    ask_open=100.2,
                    ask_high=100.6,
                    ask_low=100.1,
                    ask_close=100.3,
                ),
                m1(t0 + timedelta(minutes=1), bid=100.0),
                m1(t0 + timedelta(minutes=2), bid=100.0),
            ],
        )
        self.assertEqual(result.entry_at, t0 + timedelta(minutes=1))
        self.assertNotEqual(result.reason.value, "TP")

    def test_timeout_must_be_after_fill_ready(self):
        t0 = datetime(2026, 1, 7, 10, 0, tzinfo=UTC)
        with self.assertRaises(ValueError):
            ExecutionKernel().execute(
                TradeRequest(
                    side="BUY",
                    stop_distance=1.0,
                    target_distance=1.0,
                    timeout_at=t0 + timedelta(minutes=1),
                    entry_latency_minutes=1,
                ),
                Quote(t0, 100.0, 100.2),
                [m1(t0 + timedelta(minutes=1))],
            )

    def test_runner_and_account_paths_share_fill_ready_behavior(self):
        t0 = datetime(2026, 1, 7, 10, 0, tzinfo=UTC)
        config = TournamentConfig(
            max_holding_minutes=1,
            entry_latency_minutes=1,
            league=ExitLeague.SHARED,
            shared_exit=ExitConfig(10.0, 10.0),
        )
        runner = TournamentRunner(experts=[FixedBuyExpert()], config=config)
        bars = [m1(t0), m1(t0 + timedelta(minutes=1))]
        run = runner.run(
            run_id="issue53-path-parity",
            dataset_id="fixture-issue53",
            opportunities=[
                Opportunity(
                    opportunity_id="O1",
                    decision_at=t0,
                    m15_rows=m15_rows(t0),
                    entry_quote=Quote(t0, 100.0, 100.2),
                    m1_bars=bars,
                )
            ],
            created_at=t0,
        )
        self.assertEqual(len(run.trades), 1)
        tournament_result = run.trades[0].result

        account = SinglePositionAccount()
        request = TradeRequest(
            side="BUY",
            stop_distance=10.0,
            target_distance=10.0,
            timeout_at=t0 + timedelta(minutes=2),
            entry_latency_minutes=1,
        )
        account_result = account.execute(request, Quote(t0, 100.0, 100.2), bars)

        self.assertEqual(tournament_result.entry_at, t0 + timedelta(minutes=1))
        self.assertEqual(tournament_result.entry_at, account_result.entry_at)
        self.assertEqual(tournament_result.reason, account_result.reason)


if __name__ == "__main__":
    unittest.main()
