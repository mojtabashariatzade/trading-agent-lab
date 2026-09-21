"""Pure contracts for research strategy experts.

These contracts create research proposals only. They contain no order-submission,
network, broker, or Live trading behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite
from typing import Mapping, Protocol, Sequence


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    PASS = "PASS"


class ExitLeague(str, Enum):
    SHARED = "SHARED"
    NATIVE = "NATIVE"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value


def _dt(value: object) -> datetime:
    if isinstance(value, datetime):
        return _aware(value)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _aware(parsed)
    raise ValueError("Expected ISO timestamp or datetime")


def _positive(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


@dataclass(frozen=True)
class ExitConfig:
    stop_distance: float
    target_distance: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "stop_distance", _positive(self.stop_distance, "stop_distance"))
        object.__setattr__(self, "target_distance", _positive(self.target_distance, "target_distance"))


@dataclass(frozen=True)
class ClosedBar:
    start: datetime
    end: datetime
    open: float
    high: float
    low: float
    close: float
    ticks: int
    gap_before: bool

    def __post_init__(self) -> None:
        start = _aware(self.start)
        end = _aware(self.end)
        if end <= start:
            raise ValueError("Bar end must be after start")
        values = [float(self.open), float(self.high), float(self.low), float(self.close)]
        if not all(isfinite(x) and x > 0 for x in values):
            raise ValueError("Bar OHLC must be finite and positive")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("Invalid bar OHLC")
        if self.high < self.low:
            raise ValueError("Invalid bar range")
        if isinstance(self.ticks, bool) or int(self.ticks) < 1:
            raise ValueError("Closed bar requires positive tick count")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        object.__setattr__(self, "open", values[0])
        object.__setattr__(self, "high", values[1])
        object.__setattr__(self, "low", values[2])
        object.__setattr__(self, "close", values[3])
        object.__setattr__(self, "ticks", int(self.ticks))
        object.__setattr__(self, "gap_before", bool(self.gap_before))


def parse_closed_bar(row: Mapping[str, object]) -> ClosedBar:
    if row.get("closed", True) is not True:
        raise ValueError("Strategies may consume closed bars only")
    try:
        return ClosedBar(
            start=_dt(row["start"]),
            end=_dt(row["end"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            ticks=int(row.get("ticks", 1)),
            gap_before=bool(row.get("gap_before", False)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("Invalid closed-bar record") from exc


def closed_bars(rows: Sequence[Mapping[str, object]]) -> list[ClosedBar]:
    bars = [parse_closed_bar(row) for row in rows]
    for previous, current in zip(bars, bars[1:]):
        if current.start <= previous.start:
            raise ValueError("Bars must be strictly increasing")
        if current.start < previous.end:
            raise ValueError("Bars may not overlap")
    return bars


@dataclass(frozen=True)
class StrategyProposal:
    strategy_id: str
    version: str
    side: Side
    generated_at: datetime
    expires_at: datetime
    reason: str
    exit_config: ExitConfig | None
    league: ExitLeague

    def __post_init__(self) -> None:
        if not self.strategy_id.strip() or not self.version.strip():
            raise ValueError("Strategy id and version are required")
        generated = _aware(self.generated_at)
        expires = _aware(self.expires_at)
        if expires <= generated:
            raise ValueError("Proposal expiry must be after generation")
        if not isinstance(self.side, Side):
            raise ValueError("Typed side required")
        if not isinstance(self.league, ExitLeague):
            raise ValueError("Typed exit league required")
        if self.side != Side.PASS and self.exit_config is None:
            raise ValueError("Trade proposal requires exit configuration")
        object.__setattr__(self, "generated_at", generated)
        object.__setattr__(self, "expires_at", expires)


class StrategyExpert(Protocol):
    strategy_id: str
    version: str

    def propose(
        self,
        rows: Sequence[Mapping[str, object]],
        *,
        league: ExitLeague = ExitLeague.NATIVE,
        shared_exit: ExitConfig | None = None,
    ) -> StrategyProposal:
        ...


def choose_exit(
    native: ExitConfig,
    *,
    league: ExitLeague,
    shared_exit: ExitConfig | None,
) -> ExitConfig:
    if league == ExitLeague.NATIVE:
        return native
    if league == ExitLeague.SHARED:
        if shared_exit is None:
            raise ValueError("Shared-exit league requires shared_exit")
        return shared_exit
    raise ValueError("Unknown exit league")
