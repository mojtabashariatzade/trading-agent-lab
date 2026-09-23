"""Seed contracts and a deterministic research decision gate; not a trained strategy."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
import logging
from math import isfinite
from typing import Callable, Iterable


LOGGER = logging.getLogger(__name__)


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value


@dataclass(frozen=True)
class Observation:
    name: str
    value: float
    event_time: datetime
    available_at: datetime
    source: str
    version: str

    def __post_init__(self):
        if aware(self.available_at) < aware(self.event_time):
            raise ValueError("Information cannot precede its event")
        if not isfinite(self.value):
            raise ValueError("Observation must be finite")
        if not self.source or not self.version:
            raise ValueError("Source and version are mandatory")


def known_at(rows: Iterable[Observation], decision_time: datetime) -> list[Observation]:
    aware(decision_time)
    return [row for row in rows if row.available_at <= decision_time]


@dataclass(frozen=True)
class Quote:
    at: datetime
    available_at: datetime
    bid: float
    ask: float

    def __post_init__(self):
        if aware(self.available_at) < aware(self.at):
            raise ValueError("Quote availability precedes event")
        if not all(isfinite(x) and x > 0 for x in (self.bid, self.ask)) or self.bid > self.ask:
            raise ValueError("Invalid bid/ask")


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    PASS = "PASS"


@dataclass(frozen=True)
class Assessment:
    strategy_id: str
    side: Side
    generated_at: datetime
    expires_at: datetime
    expected_net_r: float | None

    def __post_init__(self):
        if not isinstance(self.side, Side):
            raise ValueError("Typed side is required")
        if aware(self.expires_at) <= aware(self.generated_at):
            raise ValueError("Invalid validity interval")
        if self.expected_net_r is not None and not isfinite(self.expected_net_r):
            raise ValueError("EV must be finite or unknown")


@dataclass(frozen=True)
class Decision:
    side: Side
    reason: str
    strategy_id: str | None = None


@dataclass(frozen=True)
class AccountingGateResult:
    gate_name: str
    status: str
    error_code: str | None
    error_message: str | None
    measured_values: dict[str, object]
    thresholds_used: dict[str, object]


@dataclass(frozen=True)
class AccountingGateEvaluation:
    gate_order: tuple[str, ...]
    gate_results: tuple[AccountingGateResult, ...]
    blocked: bool
    block_error_code: str | None
    block_error_message: str | None
    failure_reasons: tuple[tuple[str, str, str], ...] = ()


def validate_mark_to_market_gate(
    *,
    equity: float,
    cash_available: float,
    unrealized_pnl: float,
    mtm_tolerance_abs: float,
) -> AccountingGateResult:
    """Validate MTM parity: equity ~= cash_available + unrealized_pnl within tolerance."""
    expected_equity = cash_available + unrealized_pnl
    delta = abs(equity - expected_equity)
    if mtm_tolerance_abs < 0 or delta > mtm_tolerance_abs:
        return AccountingGateResult(
            gate_name="MTM",
            status="FAIL",
            error_code="ACCOUNTING_BLOCK_MTM",
            error_message="MTM mismatch: equity must equal cash_available + unrealized_pnl within tolerance",
            measured_values={
                "equity": equity,
                "cash_available": cash_available,
                "unrealized_pnl": unrealized_pnl,
                "expected_equity": expected_equity,
                "delta": delta,
            },
            thresholds_used={"mtm_tolerance_abs": mtm_tolerance_abs},
        )
    return AccountingGateResult(
        gate_name="MTM",
        status="PASS",
        error_code=None,
        error_message=None,
        measured_values={"delta": delta},
        thresholds_used={"mtm_tolerance_abs": mtm_tolerance_abs},
    )


def validate_cash_integrity_gate(*, cash_available: float, min_cash_required: float) -> AccountingGateResult:
    """Validate that available cash is not below configured minimum requirement."""
    if min_cash_required < 0 or cash_available < min_cash_required:
        return AccountingGateResult(
            gate_name="CASH",
            status="FAIL",
            error_code="ACCOUNTING_BLOCK_CASH",
            error_message="Insufficient cash: cash_available is below min_cash_required",
            measured_values={
                "cash_available": cash_available,
                "min_cash_required": min_cash_required,
            },
            thresholds_used={"min_cash_required": min_cash_required},
        )
    return AccountingGateResult(
        gate_name="CASH",
        status="PASS",
        error_code=None,
        error_message=None,
        measured_values={"cash_available": cash_available},
        thresholds_used={"min_cash_required": min_cash_required},
    )


def validate_margin_sufficiency_gate(*, free_margin: float, required_margin: float) -> AccountingGateResult:
    """Validate that free margin is sufficient for required margin."""
    if required_margin < 0 or free_margin < required_margin:
        return AccountingGateResult(
            gate_name="MARGIN",
            status="FAIL",
            error_code="ACCOUNTING_BLOCK_MARGIN",
            error_message="Insufficient free margin: free_margin is below required_margin",
            measured_values={
                "free_margin": free_margin,
                "required_margin": required_margin,
            },
            thresholds_used={"required_margin": required_margin},
        )
    return AccountingGateResult(
        gate_name="MARGIN",
        status="PASS",
        error_code=None,
        error_message=None,
        measured_values={"free_margin": free_margin},
        thresholds_used={"required_margin": required_margin},
    )


def validate_overlap_constraints_gate(
    *,
    overlap_detected: bool,
    net_exposure_after_candidate: float,
    max_abs_exposure_limit: float,
    open_positions_same_instrument: int,
    max_positions_same_instrument: int,
) -> AccountingGateResult:
    """Validate overlap/exposure/position-count constraints for candidate execution."""
    if (
        not isinstance(open_positions_same_instrument, int)
        or not isinstance(max_positions_same_instrument, int)
        or open_positions_same_instrument < 0
        or max_positions_same_instrument < 0
        or max_abs_exposure_limit < 0
    ):
        return AccountingGateResult(
            gate_name="OVERLAP",
            status="FAIL",
            error_code="ACCOUNTING_BLOCK_OVERLAP",
            error_message="Exposure overlap/limit violation for candidate instrument",
            measured_values={
                "open_positions_same_instrument": open_positions_same_instrument,
                "max_positions_same_instrument": max_positions_same_instrument,
                "max_abs_exposure_limit": max_abs_exposure_limit,
            },
            thresholds_used={
                "max_abs_exposure_limit": max_abs_exposure_limit,
                "max_positions_same_instrument": max_positions_same_instrument,
            },
        )

    over_exposure = abs(net_exposure_after_candidate) > max_abs_exposure_limit
    too_many_positions = open_positions_same_instrument > max_positions_same_instrument
    if overlap_detected or over_exposure or too_many_positions:
        return AccountingGateResult(
            gate_name="OVERLAP",
            status="FAIL",
            error_code="ACCOUNTING_BLOCK_OVERLAP",
            error_message="Exposure overlap/limit violation for candidate instrument",
            measured_values={
                "overlap_detected": overlap_detected,
                "net_exposure_after_candidate": net_exposure_after_candidate,
                "open_positions_same_instrument": open_positions_same_instrument,
            },
            thresholds_used={
                "max_abs_exposure_limit": max_abs_exposure_limit,
                "max_positions_same_instrument": max_positions_same_instrument,
            },
        )
    return AccountingGateResult(
        gate_name="OVERLAP",
        status="PASS",
        error_code=None,
        error_message=None,
        measured_values={
            "overlap_detected": overlap_detected,
            "net_exposure_after_candidate": net_exposure_after_candidate,
            "open_positions_same_instrument": open_positions_same_instrument,
        },
        thresholds_used={
            "max_abs_exposure_limit": max_abs_exposure_limit,
            "max_positions_same_instrument": max_positions_same_instrument,
        },
    )


def validate_rollover_validity_gate(
    *,
    rollover_due: float,
    rollover_charged: float,
    rollover_due_date_utc: date,
    rollover_charge_date_utc: date,
    rollover_tolerance_abs: float,
) -> AccountingGateResult:
    """Validate rollover amount/date consistency against configured tolerance."""
    if not isinstance(rollover_due_date_utc, date) or not isinstance(rollover_charge_date_utc, date):
        return AccountingGateResult(
            gate_name="ROLLOVER",
            status="FAIL",
            error_code="ACCOUNTING_BLOCK_ROLLOVER",
            error_message="Rollover mismatch: amount/date inconsistent with due rollover",
            measured_values={
                "rollover_due_date_utc": rollover_due_date_utc,
                "rollover_charge_date_utc": rollover_charge_date_utc,
            },
            thresholds_used={"rollover_tolerance_abs": rollover_tolerance_abs},
        )

    amount_delta = abs(rollover_due - rollover_charged)
    date_mismatch = rollover_due_date_utc != rollover_charge_date_utc
    if rollover_tolerance_abs < 0 or amount_delta > rollover_tolerance_abs or date_mismatch:
        return AccountingGateResult(
            gate_name="ROLLOVER",
            status="FAIL",
            error_code="ACCOUNTING_BLOCK_ROLLOVER",
            error_message="Rollover mismatch: amount/date inconsistent with due rollover",
            measured_values={
                "rollover_due": rollover_due,
                "rollover_charged": rollover_charged,
                "rollover_due_date_utc": rollover_due_date_utc.isoformat(),
                "rollover_charge_date_utc": rollover_charge_date_utc.isoformat(),
                "amount_delta": amount_delta,
            },
            thresholds_used={"rollover_tolerance_abs": rollover_tolerance_abs},
        )
    return AccountingGateResult(
        gate_name="ROLLOVER",
        status="PASS",
        error_code=None,
        error_message=None,
        measured_values={
            "amount_delta": amount_delta,
            "rollover_due_date_utc": rollover_due_date_utc.isoformat(),
            "rollover_charge_date_utc": rollover_charge_date_utc.isoformat(),
        },
        thresholds_used={"rollover_tolerance_abs": rollover_tolerance_abs},
    )


@dataclass(frozen=True)
class AccountingState:
    """Deterministic accounting integrity checks that gate ranking decisions."""

    # Shared pre-check snapshot contract.
    decision_time_utc: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
    account_snapshot_time_utc: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
    max_snapshot_age_seconds: int = 2_147_483_647
    instrument: str = "GBPJPY"
    account_currency: str = "JPY"

    # Accounting gate inputs.
    equity: float = 0.0
    cash_available: float = 0.0
    unrealized_pnl: float = 0.0
    min_cash_required: float = 0.0
    free_margin: float = 0.0
    required_margin: float = 0.0
    overlap_detected: bool = False
    net_exposure_after_candidate: float = 0.0
    max_abs_exposure_limit: float = 1e18
    open_positions_same_instrument: int = 0
    max_positions_same_instrument: int = 1_000_000
    rollover_due: float = 0.0
    rollover_charged: float = 0.0
    mtm_tolerance_abs: float = 1e-9
    rollover_tolerance_abs: float = 1e-9
    rollover_due_date_utc: date = date(1970, 1, 1)
    rollover_charge_date_utc: date = date(1970, 1, 1)
    # Legacy compatibility field used to set both MTM/rollover tolerances.
    tolerance: float | None = None

    GATE_ORDER: tuple[str, ...] = (
        "MTM",
        "CASH",
        "MARGIN",
        "OVERLAP",
        "ROLLOVER",
    )

    def __post_init__(self):
        if self.tolerance is not None:
            if not isfinite(self.tolerance) or self.tolerance < 0:
                raise ValueError("tolerance must be finite and non-negative")
            object.__setattr__(self, "mtm_tolerance_abs", float(self.tolerance))
            object.__setattr__(self, "rollover_tolerance_abs", float(self.tolerance))

    @staticmethod
    def _missing(value: object) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    def _shared_precheck_failure(self) -> AccountingGateResult | None:
        required_fields = {
            "decision_time_utc": self.decision_time_utc,
            "account_snapshot_time_utc": self.account_snapshot_time_utc,
            "max_snapshot_age_seconds": self.max_snapshot_age_seconds,
            "instrument": self.instrument,
            "account_currency": self.account_currency,
        }
        missing = sorted(name for name, value in required_fields.items() if self._missing(value))
        if missing:
            return AccountingGateResult(
                gate_name="INPUT_PRECHECK",
                status="FAIL",
                error_code="ACCOUNTING_BLOCK_INPUT_MISSING",
                error_message="Required accounting snapshot field is missing",
                measured_values={"missing_fields": tuple(missing)},
                thresholds_used={},
            )

        nonfinite_checks = {
            "equity": self.equity,
            "cash_available": self.cash_available,
            "unrealized_pnl": self.unrealized_pnl,
            "min_cash_required": self.min_cash_required,
            "free_margin": self.free_margin,
            "required_margin": self.required_margin,
            "net_exposure_after_candidate": self.net_exposure_after_candidate,
            "max_abs_exposure_limit": self.max_abs_exposure_limit,
            "rollover_due": self.rollover_due,
            "rollover_charged": self.rollover_charged,
            "mtm_tolerance_abs": self.mtm_tolerance_abs,
            "rollover_tolerance_abs": self.rollover_tolerance_abs,
        }
        for name, value in nonfinite_checks.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = float("nan")
            if not isfinite(numeric):
                return AccountingGateResult(
                    gate_name="INPUT_PRECHECK",
                    status="FAIL",
                    error_code="ACCOUNTING_BLOCK_INPUT_NONFINITE",
                    error_message="Accounting snapshot contains NaN/inf numeric field",
                    measured_values={"field": name, "value": value},
                    thresholds_used={},
                )

        if self.mtm_tolerance_abs < 0 or self.rollover_tolerance_abs < 0:
            return AccountingGateResult(
                gate_name="INPUT_PRECHECK",
                status="FAIL",
                error_code="ACCOUNTING_BLOCK_INPUT_MISSING",
                error_message="Tolerance fields must be non-negative",
                measured_values={
                    "mtm_tolerance_abs": self.mtm_tolerance_abs,
                    "rollover_tolerance_abs": self.rollover_tolerance_abs,
                },
                thresholds_used={},
            )

        if (
            not isinstance(self.decision_time_utc, datetime)
            or self.decision_time_utc.tzinfo is None
            or self.decision_time_utc.utcoffset() is None
            or not isinstance(self.account_snapshot_time_utc, datetime)
            or self.account_snapshot_time_utc.tzinfo is None
            or self.account_snapshot_time_utc.utcoffset() is None
        ):
            return AccountingGateResult(
                gate_name="INPUT_PRECHECK",
                status="FAIL",
                error_code="ACCOUNTING_BLOCK_INPUT_MISSING",
                error_message="decision/account snapshot timestamps must be timezone-aware",
                measured_values={
                    "decision_time_utc": self.decision_time_utc,
                    "account_snapshot_time_utc": self.account_snapshot_time_utc,
                },
                thresholds_used={},
            )

        if not isinstance(self.max_snapshot_age_seconds, int) or self.max_snapshot_age_seconds < 0:
            return AccountingGateResult(
                gate_name="INPUT_PRECHECK",
                status="FAIL",
                error_code="ACCOUNTING_BLOCK_INPUT_MISSING",
                error_message="max_snapshot_age_seconds must be a non-negative integer",
                measured_values={"max_snapshot_age_seconds": self.max_snapshot_age_seconds},
                thresholds_used={},
            )

        if self.account_snapshot_time_utc > self.decision_time_utc:
            return AccountingGateResult(
                gate_name="INPUT_PRECHECK",
                status="FAIL",
                error_code="ACCOUNTING_BLOCK_SNAPSHOT_FUTURE",
                error_message="Account snapshot time is in the future vs decision time",
                measured_values={
                    "decision_time_utc": self.decision_time_utc.isoformat(),
                    "account_snapshot_time_utc": self.account_snapshot_time_utc.isoformat(),
                },
                thresholds_used={},
            )

        snapshot_age_seconds = int((self.decision_time_utc - self.account_snapshot_time_utc).total_seconds())
        if snapshot_age_seconds > self.max_snapshot_age_seconds:
            return AccountingGateResult(
                gate_name="INPUT_PRECHECK",
                status="FAIL",
                error_code="ACCOUNTING_BLOCK_SNAPSHOT_STALE",
                error_message="Account snapshot is older than max_snapshot_age_seconds",
                measured_values={"snapshot_age_seconds": snapshot_age_seconds},
                thresholds_used={"max_snapshot_age_seconds": self.max_snapshot_age_seconds},
            )

        return None

    def _gate_mtm(self) -> AccountingGateResult:
        return validate_mark_to_market_gate(
            equity=self.equity,
            cash_available=self.cash_available,
            unrealized_pnl=self.unrealized_pnl,
            mtm_tolerance_abs=self.mtm_tolerance_abs,
        )

    def _gate_cash(self) -> AccountingGateResult:
        return validate_cash_integrity_gate(
            cash_available=self.cash_available,
            min_cash_required=self.min_cash_required,
        )

    def _gate_margin(self) -> AccountingGateResult:
        return validate_margin_sufficiency_gate(
            free_margin=self.free_margin,
            required_margin=self.required_margin,
        )

    def _gate_overlap(self) -> AccountingGateResult:
        return validate_overlap_constraints_gate(
            overlap_detected=self.overlap_detected,
            net_exposure_after_candidate=self.net_exposure_after_candidate,
            max_abs_exposure_limit=self.max_abs_exposure_limit,
            open_positions_same_instrument=self.open_positions_same_instrument,
            max_positions_same_instrument=self.max_positions_same_instrument,
        )

    def _gate_rollover(self) -> AccountingGateResult:
        return validate_rollover_validity_gate(
            rollover_due=self.rollover_due,
            rollover_charged=self.rollover_charged,
            rollover_due_date_utc=self.rollover_due_date_utc,
            rollover_charge_date_utc=self.rollover_charge_date_utc,
            rollover_tolerance_abs=self.rollover_tolerance_abs,
        )

    def gate_evaluators(self) -> tuple[Callable[[], AccountingGateResult], ...]:
        """Extension point for future deterministic accounting gates."""
        return (
            self._gate_mtm,
            self._gate_cash,
            self._gate_margin,
            self._gate_overlap,
            self._gate_rollover,
        )

    def evaluate_gates(self) -> AccountingGateEvaluation:
        """Evaluate gates in fixed order with first-failure short-circuit."""
        results: list[AccountingGateResult] = []

        def _failure_reasons(rows: Iterable[AccountingGateResult]) -> tuple[tuple[str, str, str], ...]:
            reasons: list[tuple[str, str, str]] = []
            for row in rows:
                if row.status == "FAIL" and row.error_code and row.error_message:
                    reasons.append((row.gate_name, row.error_code, row.error_message))
            return tuple(reasons)

        precheck_fail = self._shared_precheck_failure()
        if precheck_fail is not None:
            results.append(precheck_fail)
            for gate_name in self.GATE_ORDER:
                results.append(
                    AccountingGateResult(
                        gate_name=gate_name,
                        status="SKIP",
                        error_code=None,
                        error_message=None,
                        measured_values={},
                        thresholds_used={},
                    )
                )
            return AccountingGateEvaluation(
                gate_order=("INPUT_PRECHECK",) + self.GATE_ORDER,
                gate_results=tuple(results),
                blocked=True,
                block_error_code=precheck_fail.error_code,
                block_error_message=precheck_fail.error_message,
                failure_reasons=_failure_reasons(results),
            )

        results.append(
            AccountingGateResult(
                gate_name="INPUT_PRECHECK",
                status="PASS",
                error_code=None,
                error_message=None,
                measured_values={
                    "decision_time_utc": self.decision_time_utc.isoformat(),
                    "account_snapshot_time_utc": self.account_snapshot_time_utc.isoformat(),
                    "snapshot_age_seconds": int(
                        (self.decision_time_utc - self.account_snapshot_time_utc).total_seconds()
                    ),
                },
                thresholds_used={"max_snapshot_age_seconds": self.max_snapshot_age_seconds},
            )
        )

        blocked_code: str | None = None
        blocked_message: str | None = None
        evaluators = self.gate_evaluators()
        for index, evaluate in enumerate(evaluators):
            result = evaluate()
            results.append(result)
            if result.status == "FAIL":
                blocked_code = result.error_code
                blocked_message = result.error_message
                for skipped in self.GATE_ORDER[index + 1:]:
                    results.append(
                        AccountingGateResult(
                            gate_name=skipped,
                            status="SKIP",
                            error_code=None,
                            error_message=None,
                            measured_values={},
                            thresholds_used={},
                        )
                    )
                break

        evaluation = AccountingGateEvaluation(
            gate_order=("INPUT_PRECHECK",) + self.GATE_ORDER,
            gate_results=tuple(results),
            blocked=blocked_code is not None,
            block_error_code=blocked_code,
            block_error_message=blocked_message,
            failure_reasons=_failure_reasons(results),
        )
        if evaluation.blocked:
            LOGGER.info(
                "RANKING_GATES_BLOCKED code=%s reasons=%s",
                evaluation.block_error_code,
                evaluation.failure_reasons,
            )
        else:
            LOGGER.debug("RANKING_GATES_PASSED gate_order=%s", evaluation.gate_order)
        return evaluation

    def block_reason(self) -> str | None:
        evaluation = self.evaluate_gates()
        return evaluation.block_error_code


def decide(assessments: Iterable[Assessment], now: datetime, *, data_healthy: bool,
           risk_allowed: bool, position_open: bool, min_ev: float = 0.10,
           min_direction_gap: float = 0.05,
           accounting: AccountingState | None = None,
           trace_sink: list[dict[str, object]] | None = None) -> Decision:
    """Pure rule-based seed. EVs supplied here are untrained inputs, not performance claims."""
    aware(now)
    if not all(isfinite(x) and x >= 0 for x in (min_ev, min_direction_gap)):
        raise ValueError("Invalid thresholds")
    if not data_healthy:
        return Decision(Side.PASS, "DATA_UNAVAILABLE")
    if not risk_allowed:
        return Decision(Side.PASS, "RISK_BLOCK")
    if position_open:
        return Decision(Side.PASS, "POSITION_OPEN")
    accounting_state = accounting or AccountingState()
    accounting_evaluation = accounting_state.evaluate_gates()
    if accounting_evaluation.blocked:
        if trace_sink is not None:
            trace_sink.append(
                {
                    "blocked": True,
                    "block_error_code": accounting_evaluation.block_error_code,
                    "block_error_message": accounting_evaluation.block_error_message,
                    "failure_reasons": [
                        {
                            "gate_name": gate_name,
                            "error_code": error_code,
                            "error_message": error_message,
                        }
                        for gate_name, error_code, error_message in accounting_evaluation.failure_reasons
                    ],
                    "ranking_executed": False,
                }
            )
        return Decision(Side.PASS, accounting_evaluation.block_error_code or "ACCOUNTING_BLOCK")

    if trace_sink is not None:
        trace_sink.append(
            {
                "blocked": False,
                "block_error_code": None,
                "block_error_message": None,
                "failure_reasons": [],
                "ranking_executed": True,
            }
        )

    eligible = [a for a in assessments if a.side != Side.PASS and a.generated_at <= now < a.expires_at
                and a.expected_net_r is not None and a.expected_net_r >= min_ev]
    if not eligible:
        return Decision(Side.PASS, "NO_EDGE")
    eligible.sort(key=lambda a: (-a.expected_net_r, a.strategy_id))
    best = eligible[0]
    opposite = next((a for a in eligible if a.side != best.side), None)
    if opposite is not None and best.expected_net_r - opposite.expected_net_r < min_direction_gap:
        return Decision(Side.PASS, "DIRECTION_CONFLICT")
    return Decision(best.side, "ELIGIBLE_PROPOSAL", best.strategy_id)
