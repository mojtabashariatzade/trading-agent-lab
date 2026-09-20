"""Seed contracts and a deterministic research decision gate; not a trained strategy."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite
from typing import Iterable


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


def decide(assessments: Iterable[Assessment], now: datetime, *, data_healthy: bool,
           risk_allowed: bool, position_open: bool, min_ev: float = 0.10,
           min_direction_gap: float = 0.05) -> Decision:
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
