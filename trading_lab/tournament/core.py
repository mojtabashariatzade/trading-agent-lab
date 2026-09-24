"""Small auditable research tournament for synthetic fixtures only.

The runner connects T003 strategy proposals to the T002 execution kernel through
a deterministic Decision Core. It never submits orders and never contacts a broker.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from math import isfinite
from typing import Mapping, Sequence

from trading_lab.execution.kernel import (
    ExecutionKernel,
    M1Bar,
    Quote,
    SinglePositionAccount,
    TradeRequest,
    TradeResult,
)
from trading_lab.strategies import (
    BollingerReentryExpert,
    EmaTrendExpert,
    ExitConfig,
    ExitLeague,
    SessionRangeBreakoutExpert,
    Side,
    StrategyProposal,
)
from trading_lab.strategies.contracts import parse_closed_bar


class DatasetClass(str, Enum):
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _positive_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _non_negative(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


@dataclass(frozen=True)
class TournamentConfig:
    max_holding_minutes: int = 60
    slippage: float = 0.0
    commission_per_side: float = 0.0
    league: ExitLeague = ExitLeague.SHARED
    shared_exit: ExitConfig = ExitConfig(0.30, 0.60)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "max_holding_minutes",
            _positive_int(self.max_holding_minutes, "max_holding_minutes"),
        )
        object.__setattr__(self, "slippage", _non_negative(self.slippage, "slippage"))
        object.__setattr__(
            self,
            "commission_per_side",
            _non_negative(self.commission_per_side, "commission_per_side"),
        )
        if not isinstance(self.league, ExitLeague):
            raise ValueError("Typed ExitLeague required")


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    decision_at: datetime
    m15_rows: Sequence[Mapping[str, object]]
    entry_quote: Quote | None
    m1_bars: Sequence[M1Bar]
    risk_allowed: bool = True

    def __post_init__(self) -> None:
        if not self.opportunity_id.strip():
            raise ValueError("opportunity_id is required")
        decision_at = _aware_utc(self.decision_at)
        if decision_at.second or decision_at.microsecond:
            raise ValueError("decision_at must be minute-aligned")
        if self.entry_quote is not None and self.entry_quote.at != decision_at:
            raise ValueError("entry_quote.at must equal decision_at")
        object.__setattr__(self, "decision_at", decision_at)
        object.__setattr__(self, "m15_rows", tuple(self.m15_rows))
        object.__setattr__(self, "m1_bars", tuple(self.m1_bars))
        object.__setattr__(self, "risk_allowed", bool(self.risk_allowed))


@dataclass(frozen=True)
class TournamentDecision:
    opportunity_id: str
    side: Side
    reason: str
    strategy_ids: tuple[str, ...]
    exit_config: ExitConfig | None

    @property
    def actionable(self) -> bool:
        return self.side != Side.PASS and self.exit_config is not None


@dataclass(frozen=True)
class ProposalRecord:
    opportunity_id: str
    proposal: StrategyProposal


@dataclass(frozen=True)
class TradeRecord:
    opportunity_id: str
    strategy_ids: tuple[str, ...]
    result: TradeResult


@dataclass(frozen=True)
class TournamentRun:
    run_id: str
    dataset_id: str
    dataset_class: DatasetClass
    created_at: datetime
    strategy_versions: tuple[tuple[str, str], ...]
    config: TournamentConfig
    proposals: tuple[ProposalRecord, ...]
    decisions: tuple[TournamentDecision, ...]
    trades: tuple[TradeRecord, ...]
    final_cash: float

    @property
    def leaderboard_eligible(self) -> bool:
        return False

    def real_performance_rows(self):
        raise RuntimeError(
            "SYNTHETIC_TEST_ONLY runs cannot populate a real-performance leaderboard"
        )


class RuleBasedDecisionCore:
    """Deterministic selection with PASS, risk veto, and data gates as first-class outcomes."""

    def decide(
        self,
        *,
        opportunity_id: str,
        decision_at: datetime,
        proposals: Sequence[StrategyProposal],
        data_ready: bool,
        risk_allowed: bool,
        position_open: bool,
    ) -> TournamentDecision:
        if not data_ready:
            return TournamentDecision(
                opportunity_id,
                Side.PASS,
                "DATA_REQUIRED",
                (),
                None,
            )
        if not risk_allowed:
            return TournamentDecision(
                opportunity_id,
                Side.PASS,
                "RISK_VETO",
                tuple(sorted(p.strategy_id for p in proposals)),
                None,
            )
        if position_open:
            return TournamentDecision(
                opportunity_id,
                Side.PASS,
                "POSITION_OPEN",
                tuple(sorted(p.strategy_id for p in proposals)),
                None,
            )

        eligible = [
            p
            for p in proposals
            if p.side != Side.PASS and p.generated_at <= decision_at < p.expires_at
        ]
        if not eligible:
            return TournamentDecision(
                opportunity_id,
                Side.PASS,
                "ALL_PASS",
                tuple(sorted(p.strategy_id for p in proposals)),
                None,
            )

        directions = {p.side for p in eligible}
        if len(directions) != 1:
            return TournamentDecision(
                opportunity_id,
                Side.PASS,
                "DIRECTION_CONFLICT",
                tuple(sorted(p.strategy_id for p in eligible)),
                None,
            )

        side = eligible[0].side
        ids = tuple(sorted(p.strategy_id for p in eligible))
        if len(eligible) == 1:
            return TournamentDecision(
                opportunity_id,
                side,
                "SINGLE_EXPERT",
                ids,
                eligible[0].exit_config,
            )

        exit_configs = {p.exit_config for p in eligible}
        shared = all(p.league == ExitLeague.SHARED for p in eligible)
        if not shared or len(exit_configs) != 1:
            return TournamentDecision(
                opportunity_id,
                Side.PASS,
                "MULTIPLE_NATIVE_PROPOSALS",
                ids,
                None,
            )

        return TournamentDecision(
            opportunity_id,
            side,
            "SHARED_EXIT_CONSENSUS",
            ids,
            eligible[0].exit_config,
        )


def default_experts():
    return (
        EmaTrendExpert(),
        BollingerReentryExpert(),
        SessionRangeBreakoutExpert(),
    )


class TournamentRunner:
    """Chronological single-account fixture replay."""

    def __init__(
        self,
        *,
        experts=None,
        kernel: ExecutionKernel | None = None,
        decision_core: RuleBasedDecisionCore | None = None,
        config: TournamentConfig | None = None,
    ):
        self.experts = tuple(experts or default_experts())
        if not self.experts:
            raise ValueError("At least one strategy expert is required")
        self.kernel = kernel or ExecutionKernel()
        self.decision_core = decision_core or RuleBasedDecisionCore()
        self.config = config or TournamentConfig()

    def run(
        self,
        *,
        run_id: str,
        dataset_id: str,
        opportunities: Sequence[Opportunity],
        created_at: datetime,
        initial_cash: float = 0.0,
    ) -> TournamentRun:
        if not run_id.strip() or not dataset_id.strip():
            raise ValueError("run_id and dataset_id are required")
        created_at = _aware_utc(created_at)
        cash = float(initial_cash)
        if not isfinite(cash):
            raise ValueError("initial_cash must be finite")

        for previous, current in zip(opportunities, opportunities[1:]):
            if current.decision_at <= previous.decision_at:
                raise ValueError("Opportunities must be strictly chronological")

        account = SinglePositionAccount(kernel=self.kernel, cash=cash)
        proposal_records: list[ProposalRecord] = []
        decisions: list[TournamentDecision] = []
        trades: list[TradeRecord] = []
        position_until: datetime | None = None
        permanently_open = False

        for opportunity in opportunities:
            data_ready = self._data_ready(opportunity)
            proposals: list[StrategyProposal] = []
            if opportunity.m15_rows:
                self._validate_causal_m15(opportunity)
                for expert in self.experts:
                    proposal = expert.propose(
                        opportunity.m15_rows,
                        league=self.config.league,
                        shared_exit=(
                            self.config.shared_exit
                            if self.config.league == ExitLeague.SHARED
                            else None
                        ),
                    )
                    proposals.append(proposal)
                    proposal_records.append(
                        ProposalRecord(opportunity.opportunity_id, proposal)
                    )

            position_open = permanently_open or (
                position_until is not None and opportunity.decision_at < position_until
            )
            decision = self.decision_core.decide(
                opportunity_id=opportunity.opportunity_id,
                decision_at=opportunity.decision_at,
                proposals=proposals,
                data_ready=data_ready,
                risk_allowed=opportunity.risk_allowed,
                position_open=position_open,
            )
            decisions.append(decision)

            if not decision.actionable:
                continue
            if opportunity.entry_quote is None:
                raise RuntimeError("Actionable decision missing entry quote")
            if decision.exit_config is None:
                raise RuntimeError("Actionable decision missing exit configuration")

            request = TradeRequest(
                side=decision.side.value,
                stop_distance=decision.exit_config.stop_distance,
                target_distance=decision.exit_config.target_distance,
                timeout_at=opportunity.entry_quote.at
                + timedelta(minutes=self.config.max_holding_minutes),
                slippage=self.config.slippage,
                commission_per_side=self.config.commission_per_side,
            )
            result = account.execute(
                request,
                opportunity.entry_quote,
                opportunity.m1_bars,
            )
            trades.append(
                TradeRecord(
                    opportunity.opportunity_id,
                    decision.strategy_ids,
                    result,
                )
            )
            if result.censored:
                permanently_open = True
                position_until = None
            else:
                permanently_open = False
                position_until = result.exit_at

        versions = tuple(
            sorted((expert.strategy_id, expert.version) for expert in self.experts)
        )
        return TournamentRun(
            run_id=run_id,
            dataset_id=dataset_id,
            dataset_class=DatasetClass.SYNTHETIC_TEST_ONLY,
            created_at=created_at,
            strategy_versions=versions,
            config=self.config,
            proposals=tuple(proposal_records),
            decisions=tuple(decisions),
            trades=tuple(trades),
            final_cash=account.cash,
        )

    @staticmethod
    def _data_ready(opportunity: Opportunity) -> bool:
        # Entry eligibility is causal: require decision-time strategy features and
        # an executable entry quote. Missing future execution bars must not change
        # the entry decision; they produce a censored trade outcome instead.
        return bool(opportunity.m15_rows and opportunity.entry_quote is not None)

    @staticmethod
    def _validate_causal_m15(opportunity: Opportunity) -> None:
        for row in opportunity.m15_rows:
            bar = parse_closed_bar(row)
            if bar.end > opportunity.decision_at:
                raise ValueError("M15 strategy input contains future/unclosed data")
