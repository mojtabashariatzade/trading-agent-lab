"""Deterministic account ledger for P&L/risk acceptance harnesses.

Research-only accounting utility; no live broker integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


EPSILON = 1e-12


def _finite(value: float, *, name: str) -> float:
    numeric = float(value)
    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _positive(value: float, *, name: str) -> float:
    numeric = _finite(value, name=name)
    if numeric <= 0:
        raise ValueError(f"{name} must be positive")
    return numeric


@dataclass(frozen=True)
class FillEvent:
    """One executed fill with explicit one-time transaction costs."""

    side: str
    quantity: float
    price: float
    commission: float = 0.0
    spread_cost: float = 0.0
    slippage_cost: float = 0.0

    def __post_init__(self) -> None:
        side = str(self.side).upper().strip()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "quantity", _positive(self.quantity, name="quantity"))
        object.__setattr__(self, "price", _positive(self.price, name="price"))
        object.__setattr__(self, "commission", _finite(self.commission, name="commission"))
        object.__setattr__(self, "spread_cost", _finite(self.spread_cost, name="spread_cost"))
        object.__setattr__(self, "slippage_cost", _finite(self.slippage_cost, name="slippage_cost"))


@dataclass(frozen=True)
class LedgerSnapshot:
    position_qty: float
    average_entry_price: float | None
    cash_balance: float
    equity_total: float
    trading_equity_ex_cashflows: float
    realized_gross_pnl: float
    realized_costs_total: float
    rollover_total: float
    unrealized_pnl: float
    trading_pnl_net: float
    external_cashflow_total: float
    exposure_abs: float
    drawdown: float
    max_drawdown: float
    recovery: float


class AccountLedger:
    """Single-instrument ledger with deterministic reversal/reduction accounting."""

    def __init__(self, *, starting_balance: float = 0.0) -> None:
        self.starting_balance = _finite(starting_balance, name="starting_balance")
        self.position_qty = 0.0  # signed: long>0, short<0
        self.average_entry_price = 0.0
        self.realized_gross_pnl = 0.0
        self.realized_costs_total = 0.0
        self.rollover_total = 0.0
        self.external_cashflow_total = 0.0

        self._peak_trading_equity = self.starting_balance
        self._max_drawdown = 0.0
        self._trough_at_max_drawdown = self.starting_balance

    def apply_fill(self, fill: FillEvent) -> None:
        signed_qty = fill.quantity if fill.side == "BUY" else -fill.quantity
        self.realized_costs_total += fill.commission + fill.spread_cost + fill.slippage_cost

        # Opening/increasing in same direction.
        if abs(self.position_qty) <= EPSILON or (self.position_qty > 0 and signed_qty > 0) or (self.position_qty < 0 and signed_qty < 0):
            self._increase_position(signed_qty=signed_qty, price=fill.price)
            return

        # Reducing/closing/reversing against current direction.
        remaining = signed_qty
        if self.position_qty > 0 and remaining < 0:
            close_qty = min(self.position_qty, -remaining)
            self.realized_gross_pnl += (fill.price - self.average_entry_price) * close_qty
            self.position_qty -= close_qty
            remaining += close_qty
        elif self.position_qty < 0 and remaining > 0:
            close_qty = min(-self.position_qty, remaining)
            self.realized_gross_pnl += (self.average_entry_price - fill.price) * close_qty
            self.position_qty += close_qty
            remaining -= close_qty

        if abs(self.position_qty) <= EPSILON:
            self.position_qty = 0.0
            self.average_entry_price = 0.0

        # If opposite-side fill exceeded the close quantity, open residual as reversal.
        if abs(remaining) > EPSILON:
            self._increase_position(signed_qty=remaining, price=fill.price)

    def apply_rollover(self, amount: float) -> None:
        # Positive amount is a cost, negative amount is a credit.
        self.rollover_total += _finite(amount, name="amount")

    def apply_cashflow(self, amount: float) -> None:
        # Deposit (+) / withdrawal (-), not part of trading P&L.
        self.external_cashflow_total += _finite(amount, name="amount")

    def snapshot(self, *, mark_price: float) -> LedgerSnapshot:
        mark = _positive(mark_price, name="mark_price")
        unrealized = self._unrealized_pnl(mark)
        trading_pnl_net = self.realized_gross_pnl - self.realized_costs_total - self.rollover_total

        trading_equity = self.starting_balance + trading_pnl_net + unrealized
        cash_balance = self.starting_balance + self.external_cashflow_total + trading_pnl_net
        equity_total = trading_equity + self.external_cashflow_total

        if trading_equity > self._peak_trading_equity:
            self._peak_trading_equity = trading_equity
        drawdown = self._peak_trading_equity - trading_equity
        if drawdown > self._max_drawdown:
            self._max_drawdown = drawdown
            self._trough_at_max_drawdown = trading_equity
        recovery = trading_equity - self._trough_at_max_drawdown if self._max_drawdown > 0 else 0.0

        return LedgerSnapshot(
            position_qty=self.position_qty,
            average_entry_price=(self.average_entry_price if abs(self.position_qty) > EPSILON else None),
            cash_balance=cash_balance,
            equity_total=equity_total,
            trading_equity_ex_cashflows=trading_equity,
            realized_gross_pnl=self.realized_gross_pnl,
            realized_costs_total=self.realized_costs_total,
            rollover_total=self.rollover_total,
            unrealized_pnl=unrealized,
            trading_pnl_net=trading_pnl_net,
            external_cashflow_total=self.external_cashflow_total,
            exposure_abs=abs(self.position_qty * mark),
            drawdown=drawdown,
            max_drawdown=self._max_drawdown,
            recovery=recovery,
        )

    def _increase_position(self, *, signed_qty: float, price: float) -> None:
        if abs(self.position_qty) <= EPSILON:
            self.position_qty = signed_qty
            self.average_entry_price = price
            return
        current_abs = abs(self.position_qty)
        added_abs = abs(signed_qty)
        new_abs = current_abs + added_abs
        self.average_entry_price = (
            self.average_entry_price * current_abs + price * added_abs
        ) / new_abs
        self.position_qty += signed_qty

    def _unrealized_pnl(self, mark_price: float) -> float:
        if abs(self.position_qty) <= EPSILON:
            return 0.0
        if self.position_qty > 0:
            return (mark_price - self.average_entry_price) * self.position_qty
        return (self.average_entry_price - mark_price) * (-self.position_qty)
