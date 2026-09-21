"""Event-driven research execution kernel stubs. No live-order functions."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Fill:
    side: str
    price: float
    reason: str


def entry_price(side: str, bid: float, ask: float) -> float:
    """Buy uses ask; sell uses bid."""
    side_u = side.upper()
    if side_u == "BUY":
        return ask
    if side_u == "SELL":
        return bid
    raise ValueError("side must be BUY or SELL")


def exit_price(side: str, bid: float, ask: float) -> float:
    """Close long at bid; close short at ask."""
    side_u = side.upper()
    if side_u == "BUY":
        return bid
    if side_u == "SELL":
        return ask
    raise ValueError("side must be BUY or SELL")
