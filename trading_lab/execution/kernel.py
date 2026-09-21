"""Event-driven research execution kernel. Simulator only; no live-order functions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from math import isfinite
from typing import Iterable, Sequence


M1 = timedelta(minutes=1)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _positive(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def _non_negative(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


def _side(side: str) -> str:
    value = str(side).upper()
    if value not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    return value


@dataclass(frozen=True)
class Quote:
    at: datetime
    bid: float
    ask: float

    def __post_init__(self) -> None:
        at = _aware_utc(self.at)
        bid = _positive(self.bid, "bid")
        ask = _positive(self.ask, "ask")
        if bid > ask:
            raise ValueError("Crossed bid/ask")
        object.__setattr__(self, "at", at)
        object.__setattr__(self, "bid", bid)
        object.__setattr__(self, "ask", ask)


@dataclass(frozen=True)
class M1Bar:
    """One UTC minute of executable bid/ask OHLC observations."""

    start: datetime
    bid_open: float
    bid_high: float
    bid_low: float
    bid_close: float
    ask_open: float
    ask_high: float
    ask_low: float
    ask_close: float

    def __post_init__(self) -> None:
        start = _aware_utc(self.start)
        if start.second or start.microsecond:
            raise ValueError("M1 bar start must be minute-aligned")
        values = {
            "bid_open": self.bid_open,
            "bid_high": self.bid_high,
            "bid_low": self.bid_low,
            "bid_close": self.bid_close,
            "ask_open": self.ask_open,
            "ask_high": self.ask_high,
            "ask_low": self.ask_low,
            "ask_close": self.ask_close,
        }
        clean = {name: _positive(value, name) for name, value in values.items()}
        if clean["bid_high"] < max(clean["bid_open"], clean["bid_close"]):
            raise ValueError("Invalid bid high")
        if clean["bid_low"] > min(clean["bid_open"], clean["bid_close"]):
            raise ValueError("Invalid bid low")
        if clean["ask_high"] < max(clean["ask_open"], clean["ask_close"]):
            raise ValueError("Invalid ask high")
        if clean["ask_low"] > min(clean["ask_open"], clean["ask_close"]):
            raise ValueError("Invalid ask low")
        if clean["bid_low"] > clean["bid_high"] or clean["ask_low"] > clean["ask_high"]:
            raise ValueError("Invalid OHLC range")
        if clean["bid_open"] > clean["ask_open"] or clean["bid_close"] > clean["ask_close"]:
            raise ValueError("Crossed bid/ask bar")
        object.__setattr__(self, "start", start)
        for name, value in clean.items():
            object.__setattr__(self, name, value)

    @property
    def end(self) -> datetime:
        return self.start + M1


class ExitReason(str, Enum):
    TP = "TP"
    SL = "SL"
    TIMEOUT = "TIMEOUT"
    CENSORED = "CENSORED"


@dataclass(frozen=True)
class TradeRequest:
    side: str
    stop_distance: float
    target_distance: float
    timeout_at: datetime
    quantity: float = 1.0
    slippage: float = 0.0
    commission_per_side: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "side", _side(self.side))
        object.__setattr__(self, "stop_distance", _positive(self.stop_distance, "stop_distance"))
        object.__setattr__(self, "target_distance", _positive(self.target_distance, "target_distance"))
        timeout_at = _aware_utc(self.timeout_at)
        if timeout_at.second or timeout_at.microsecond:
            raise ValueError("timeout_at must be minute-aligned for M1 execution")
        object.__setattr__(self, "timeout_at", timeout_at)
        object.__setattr__(self, "quantity", _positive(self.quantity, "quantity"))
        object.__setattr__(self, "slippage", _non_negative(self.slippage, "slippage"))
        object.__setattr__(
            self,
            "commission_per_side",
            _non_negative(self.commission_per_side, "commission_per_side"),
        )


@dataclass(frozen=True)
class Fill:
    side: str
    price: float
    reason: str


@dataclass(frozen=True)
class TradeResult:
    side: str
    entry_at: datetime
    entry_price: float
    stop_price: float
    target_price: float
    exit_at: datetime | None
    exit_price: float | None
    reason: ExitReason
    gross_pnl: float | None
    commission_paid: float
    net_pnl: float | None
    risk_amount: float
    r_multiple: float | None
    ambiguous_m1: bool
    censored: bool


def entry_price(side: str, bid: float, ask: float, *, slippage: float = 0.0) -> float:
    """Executable entry with explicit adverse slippage; spread is already in bid/ask."""
    side_u = _side(side)
    bid = _positive(bid, "bid")
    ask = _positive(ask, "ask")
    slip = _non_negative(slippage, "slippage")
    if bid > ask:
        raise ValueError("Crossed bid/ask")
    adjusted = ask + slip if side_u == "BUY" else bid - slip
    if adjusted <= 0 or not isfinite(adjusted):
        raise ValueError("slippage makes entry price invalid")
    return adjusted


def exit_price(side: str, bid: float, ask: float, *, slippage: float = 0.0) -> float:
    """Executable close with explicit adverse slippage; no separate spread deduction."""
    side_u = _side(side)
    bid = _positive(bid, "bid")
    ask = _positive(ask, "ask")
    slip = _non_negative(slippage, "slippage")
    if bid > ask:
        raise ValueError("Crossed bid/ask")
    adjusted = bid - slip if side_u == "BUY" else ask + slip
    if adjusted <= 0 or not isfinite(adjusted):
        raise ValueError("slippage makes exit price invalid")
    return adjusted


class ExecutionKernel:
    """Single deterministic kernel used by labels and account replay."""

    def execute(
        self,
        request: TradeRequest,
        entry: Quote,
        bars: Sequence[M1Bar] | Iterable[M1Bar],
    ) -> TradeResult:
        if request.timeout_at <= entry.at:
            raise ValueError("timeout_at must be after entry")
        rows = list(bars)
        for i, bar in enumerate(rows):
            if not isinstance(bar, M1Bar):
                raise TypeError("bars must contain M1Bar values")
            if i and bar.start <= rows[i - 1].start:
                raise ValueError("M1 bars must be strictly increasing")
            if bar.start < entry.at:
                raise ValueError("M1 bars cannot contain pre-entry observations")

        px_in = entry_price(
            request.side,
            entry.bid,
            entry.ask,
            slippage=request.slippage,
        )
        if px_in <= 0:
            raise ValueError("slippage makes entry price non-positive")

        if request.side == "BUY":
            stop = px_in - request.stop_distance
            target = px_in + request.target_distance
        else:
            stop = px_in + request.stop_distance
            target = px_in - request.target_distance
        if stop <= 0 or target <= 0:
            raise ValueError("invalid stop/target price")

        entry_commission = request.commission_per_side * request.quantity
        risk_amount = request.stop_distance * request.quantity

        for bar in rows:
            # If timeout is before this bar starts, the dataset does not contain
            # an executable observation at the timeout instant.
            if request.timeout_at < bar.start:
                return self._censored(
                    request=request,
                    entry=entry,
                    px_in=px_in,
                    stop=stop,
                    target=target,
                    risk_amount=risk_amount,
                    entry_commission=entry_commission,
                )

            if request.side == "BUY":
                stop_hit = bar.bid_low <= stop
                target_hit = bar.bid_high >= target
                stop_gap = bar.bid_open <= stop
                target_gap = bar.bid_open >= target
            else:
                stop_hit = bar.ask_high >= stop
                target_hit = bar.ask_low <= target
                stop_gap = bar.ask_open >= stop
                target_gap = bar.ask_open <= target

            if stop_hit and target_hit:
                # M1 path is unknowable. Choose the conservative loss outcome.
                raw_exit = self._stop_exit_raw(request.side, bar, stop, stop_gap)
                return self._resolved(
                    request=request,
                    entry=entry,
                    px_in=px_in,
                    stop=stop,
                    target=target,
                    exit_at=bar.start,
                    raw_exit=raw_exit,
                    reason=ExitReason.SL,
                    risk_amount=risk_amount,
                    ambiguous=True,
                )

            if stop_hit:
                raw_exit = self._stop_exit_raw(request.side, bar, stop, stop_gap)
                return self._resolved(
                    request=request,
                    entry=entry,
                    px_in=px_in,
                    stop=stop,
                    target=target,
                    exit_at=bar.start,
                    raw_exit=raw_exit,
                    reason=ExitReason.SL,
                    risk_amount=risk_amount,
                    ambiguous=False,
                )

            if target_hit:
                # A target is capped at the requested level; favorable gaps are
                # not credited because intrabar fill quality is unknown.
                raw_exit = target
                return self._resolved(
                    request=request,
                    entry=entry,
                    px_in=px_in,
                    stop=stop,
                    target=target,
                    exit_at=bar.start,
                    raw_exit=raw_exit,
                    reason=ExitReason.TP,
                    risk_amount=risk_amount,
                    ambiguous=False,
                )

            if request.timeout_at <= bar.end:
                raw_exit = bar.bid_close if request.side == "BUY" else bar.ask_close
                return self._resolved(
                    request=request,
                    entry=entry,
                    px_in=px_in,
                    stop=stop,
                    target=target,
                    exit_at=request.timeout_at,
                    raw_exit=raw_exit,
                    reason=ExitReason.TIMEOUT,
                    risk_amount=risk_amount,
                    ambiguous=False,
                )

        return self._censored(
            request=request,
            entry=entry,
            px_in=px_in,
            stop=stop,
            target=target,
            risk_amount=risk_amount,
            entry_commission=entry_commission,
        )

    @staticmethod
    def _stop_exit_raw(side: str, bar: M1Bar, stop: float, gap: bool) -> float:
        if not gap:
            return stop
        if side == "BUY":
            return bar.bid_open
        return bar.ask_open

    @staticmethod
    def _resolved(
        *,
        request: TradeRequest,
        entry: Quote,
        px_in: float,
        stop: float,
        target: float,
        exit_at: datetime,
        raw_exit: float,
        reason: ExitReason,
        risk_amount: float,
        ambiguous: bool,
    ) -> TradeResult:
        if request.side == "BUY":
            px_out = raw_exit - request.slippage
            gross = (px_out - px_in) * request.quantity
        else:
            px_out = raw_exit + request.slippage
            gross = (px_in - px_out) * request.quantity
        if px_out <= 0 or not isfinite(px_out):
            raise ValueError("slippage makes exit price invalid")
        commission = 2.0 * request.commission_per_side * request.quantity
        net = gross - commission
        return TradeResult(
            side=request.side,
            entry_at=entry.at,
            entry_price=px_in,
            stop_price=stop,
            target_price=target,
            exit_at=_aware_utc(exit_at),
            exit_price=px_out,
            reason=reason,
            gross_pnl=gross,
            commission_paid=commission,
            net_pnl=net,
            risk_amount=risk_amount,
            r_multiple=net / risk_amount,
            ambiguous_m1=ambiguous,
            censored=False,
        )

    @staticmethod
    def _censored(
        *,
        request: TradeRequest,
        entry: Quote,
        px_in: float,
        stop: float,
        target: float,
        risk_amount: float,
        entry_commission: float,
    ) -> TradeResult:
        return TradeResult(
            side=request.side,
            entry_at=entry.at,
            entry_price=px_in,
            stop_price=stop,
            target_price=target,
            exit_at=None,
            exit_price=None,
            reason=ExitReason.CENSORED,
            gross_pnl=None,
            commission_paid=entry_commission,
            net_pnl=None,
            risk_amount=risk_amount,
            r_multiple=None,
            ambiguous_m1=False,
            censored=True,
        )


class SinglePositionAccount:
    """Research account replay with exactly one position at a time."""

    def __init__(self, *, kernel: ExecutionKernel | None = None, cash: float = 0.0):
        cash = float(cash)
        if not isfinite(cash):
            raise ValueError("cash must be finite")
        self.kernel = kernel or ExecutionKernel()
        self.cash = cash
        self.position_open = False
        self.history: list[TradeResult] = []

    def execute(
        self,
        request: TradeRequest,
        entry: Quote,
        bars: Sequence[M1Bar] | Iterable[M1Bar],
    ) -> TradeResult:
        if self.position_open:
            raise RuntimeError("single-position account already has an open position")
        self.position_open = True
        try:
            result = self.kernel.execute(request, entry, bars)
        except Exception:
            self.position_open = False
            raise
        self.history.append(result)
        if result.censored:
            # Missing tail means the position outcome is unresolved; it remains
            # open and blocks subsequent trades rather than inventing a close.
            return result
        self.cash += float(result.net_pnl)
        self.position_open = False
        return result
