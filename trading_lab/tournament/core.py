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

from trading_lab.contracts import AccountingState

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
    DonchianBreakoutExpert,
    EmaTrendExpert,
    ExitConfig,
    ExitLeague,
    SessionRangeBreakoutExpert,
    Side,
    StrategyProposal,
    VolatilityCompressionBreakoutExpert,
)
from trading_lab.strategies.contracts import parse_closed_bar


class DatasetClass(str, Enum):
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"
    REAL_OBSERVATION = "REAL_OBSERVATION"


REQUIRED_INTEGRITY_GATES: tuple[str, ...] = ("G06", "G07", "G08", "G16")


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
    entry_latency_minutes: int = 0
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
        if (
            isinstance(self.entry_latency_minutes, bool)
            or not isinstance(self.entry_latency_minutes, int)
            or self.entry_latency_minutes < 0
        ):
            raise ValueError("entry_latency_minutes must be a non-negative integer")
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
    accounting_state: AccountingState | None = None

    def __post_init__(self) -> None:
        if not self.opportunity_id.strip():
            raise ValueError("opportunity_id is required")
        decision_at = _aware_utc(self.decision_at)
        if decision_at.second or decision_at.microsecond:
            raise ValueError("decision_at must be minute-aligned")
        object.__setattr__(self, "decision_at", decision_at)
        object.__setattr__(self, "m15_rows", tuple(self.m15_rows))
        object.__setattr__(self, "m1_bars", tuple(self.m1_bars))
        object.__setattr__(self, "risk_allowed", bool(self.risk_allowed))
        if self.accounting_state is not None and not isinstance(self.accounting_state, AccountingState):
            raise ValueError("accounting_state must be an AccountingState or None")


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
    integrity_gates_completed: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(sorted({str(gate).strip().upper() for gate in self.integrity_gates_completed if str(gate).strip()}))
        object.__setattr__(self, "integrity_gates_completed", normalized)

    @property
    def integrity_missing_gates(self) -> tuple[str, ...]:
        return tuple(gate for gate in REQUIRED_INTEGRITY_GATES if gate not in self.integrity_gates_completed)

    def ranking_blockers(self) -> tuple[str, ...]:
        blockers: list[str] = []
        if self.dataset_class == DatasetClass.SYNTHETIC_TEST_ONLY:
            blockers.append("DATASET_SYNTHETIC_TEST_ONLY")
        if self.integrity_missing_gates:
            blockers.append("INTEGRITY_GATES_INCOMPLETE")
        return tuple(blockers)

    def _blocked_message(self, *, path_name: str) -> str:
        blockers = self.ranking_blockers()
        parts: list[str] = [f"{path_name} blocked"]
        if "INTEGRITY_GATES_INCOMPLETE" in blockers:
            missing = ", ".join(self.integrity_missing_gates)
            parts.append(f"missing_integrity_gates=[{missing}]")
        if "DATASET_SYNTHETIC_TEST_ONLY" in blockers:
            parts.append("dataset_class=SYNTHETIC_TEST_ONLY")
        if not blockers:
            parts.append("no blockers")
        return "; ".join(parts)

    def require_integrity_before_ranking(self) -> None:
        if self.integrity_missing_gates:
            raise RuntimeError(self._blocked_message(path_name="RANKING_PATH"))

    @property
    def leaderboard_eligible(self) -> bool:
        return not self.ranking_blockers()

    def real_performance_rows(self) -> tuple[dict[str, object], ...]:
        blockers = self.ranking_blockers()
        if blockers:
            raise RuntimeError(self._blocked_message(path_name="REAL_PERFORMANCE_ROWS"))

        rows: list[dict[str, object]] = []
        for trade in self.trades:
            result = trade.result
            rows.append(
                {
                    "run_id": self.run_id,
                    "dataset_id": self.dataset_id,
                    "opportunity_id": trade.opportunity_id,
                    "strategy_ids": trade.strategy_ids,
                    "side": result.side,
                    "entry_at": result.entry_at,
                    "entry_price": result.entry_price,
                    "exit_at": result.exit_at,
                    "exit_price": result.exit_price,
                    "exit_reason": result.reason.value,
                    "gross_pnl": result.gross_pnl,
                    "commission_paid": result.commission_paid,
                    "net_pnl": result.net_pnl,
                    "risk_amount": result.risk_amount,
                    "r_multiple": result.r_multiple,
                    "ambiguous_m1": result.ambiguous_m1,
                    "censored": result.censored,
                }
            )
        return tuple(rows)


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
        DonchianBreakoutExpert(),
        VolatilityCompressionBreakoutExpert(),
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
        dataset_class: DatasetClass = DatasetClass.SYNTHETIC_TEST_ONLY,
        integrity_gates_completed: Sequence[str] = (),
    ) -> TournamentRun:
        if not run_id.strip() or not dataset_id.strip():
            raise ValueError("run_id and dataset_id are required")
        if not isinstance(dataset_class, DatasetClass):
            raise ValueError("Typed DatasetClass required")
        normalized_gates = tuple(
            sorted(
                {
                    str(gate).strip().upper()
                    for gate in integrity_gates_completed
                    if str(gate).strip()
                }
            )
        )
        missing_required = tuple(
            gate for gate in REQUIRED_INTEGRITY_GATES if gate not in normalized_gates
        )
        if dataset_class == DatasetClass.REAL_OBSERVATION and missing_required:
            missing = ", ".join(missing_required)
            raise RuntimeError(
                "EXECUTION_PATH blocked; missing_integrity_gates="
                f"[{missing}]"
            )
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
            if dataset_class == DatasetClass.REAL_OBSERVATION and opportunity.accounting_state is None:
                raise RuntimeError("EXECUTION_PATH blocked; missing_accounting_state_snapshot")

            if opportunity.accounting_state is not None:
                accounting_eval = opportunity.accounting_state.evaluate_gates()
                if accounting_eval.blocked:
                    decisions.append(
                        TournamentDecision(
                            opportunity.opportunity_id,
                            Side.PASS,
                            accounting_eval.block_error_code or "ACCOUNTING_BLOCK",
                            (),
                            None,
                        )
                    )
                    continue

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
                timeout_at=max(
                    opportunity.entry_quote.at,
                    opportunity.entry_quote.available_at,
                )
                + timedelta(
                    minutes=(
                        self.config.entry_latency_minutes
                        + self.config.max_holding_minutes
                    )
                ),
                slippage=self.config.slippage,
                commission_per_side=self.config.commission_per_side,
                entry_latency_minutes=self.config.entry_latency_minutes,
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
            dataset_class=dataset_class,
            created_at=created_at,
            strategy_versions=versions,
            config=self.config,
            proposals=tuple(proposal_records),
            decisions=tuple(decisions),
            trades=tuple(trades),
            final_cash=account.cash,
            integrity_gates_completed=normalized_gates,
        )

    @staticmethod
    def _data_ready(opportunity: Opportunity) -> bool:
        # Entry eligibility must depend only on data available at decision time.
        # M1 bars are post-entry evolution; missing future tail can censor an
        # already-open trade but must not veto opening the trade itself.
        return bool(
            opportunity.m15_rows
            and opportunity.entry_quote is not None
            and opportunity.entry_quote.at <= opportunity.decision_at
            and opportunity.entry_quote.available_at <= opportunity.decision_at
        )

    @staticmethod
    def _validate_causal_m15(opportunity: Opportunity) -> None:
        for row in opportunity.m15_rows:
            bar = parse_closed_bar(row)
            if bar.end > opportunity.decision_at:
                raise ValueError("M15 strategy input contains future/unclosed data")
