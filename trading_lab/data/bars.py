"""Causal UTC M15 bars and Wilder ATR for research.

Pure helpers only: supplied bid/ask observations in, deterministic bars/features out.
No downloader, no network I/O, no invented volume.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Iterable, Mapping, Sequence


M15 = timedelta(minutes=15)


def _aware(ts: datetime) -> datetime:
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return ts.astimezone(timezone.utc)


def _finite_positive(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


@dataclass(frozen=True)
class Quote:
    at: datetime
    bid: float
    ask: float

    def __post_init__(self) -> None:
        at = _aware(self.at)
        bid = _finite_positive(self.bid, "bid")
        ask = _finite_positive(self.ask, "ask")
        if bid > ask:
            raise ValueError("Crossed bid/ask")
        object.__setattr__(self, "at", at)
        object.__setattr__(self, "bid", bid)
        object.__setattr__(self, "ask", ask)


def m15_floor(ts: datetime) -> datetime:
    """Return the UTC start of the half-open M15 interval containing ts."""
    ts = _aware(ts)
    return ts.replace(minute=(ts.minute // 15) * 15, second=0, microsecond=0)


def assign_bar_start(ts: datetime) -> datetime:
    """Assign a quote to [start, start+15m); exact boundaries start the next bar."""
    return m15_floor(ts)


def build_m15_bars(
    quotes: Iterable[Quote],
    *,
    closed_at: datetime | None = None,
) -> list[dict]:
    """Build explicit half-open UTC M15 bars.

    Missing intervals are omitted, never filled. gap_before and
    missing_intervals_before preserve the gap explicitly. Tick count is the
    only activity count; no synthetic volume is produced.

    When closed_at is supplied, only bars whose end is <= closed_at are
    returned, preventing an in-progress bar from leaking into closed-bar features.
    Without closed_at the caller is declaring the supplied batch historical
    and complete through its final interval.
    """
    cutoff = _aware(closed_at) if closed_at is not None else None
    ordered = sorted(quotes, key=lambda q: q.at)
    if not ordered:
        return []

    buckets: dict[datetime, list[Quote]] = {}
    for quote in ordered:
        if not isinstance(quote, Quote):
            raise TypeError("quotes must contain Quote values")
        start = assign_bar_start(quote.at)
        buckets.setdefault(start, []).append(quote)

    bars: list[dict] = []
    previous_start: datetime | None = None
    for start in sorted(buckets):
        end = start + M15
        if cutoff is not None and end > cutoff:
            continue

        rows = buckets[start]
        mids = [(q.bid + q.ask) / 2.0 for q in rows]
        missing = 0
        if previous_start is not None:
            step_count = int((start - previous_start) / M15)
            missing = max(0, step_count - 1)

        bars.append(
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "open": mids[0],
                "high": max(mids),
                "low": min(mids),
                "close": mids[-1],
                "ticks": len(rows),
                "gap_before": missing > 0,
                "missing_intervals_before": missing,
                "closed": True,
            }
        )
        previous_start = start
    return bars


def _bar_prices(bar: Mapping[str, object]) -> tuple[float, float, float]:
    if bar.get("closed", True) is not True:
        raise ValueError("ATR requires closed bars only")
    try:
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("bar must contain numeric high, low and close") from exc
    if not all(isfinite(x) and x > 0 for x in (high, low, close)):
        raise ValueError("bar prices must be finite and positive")
    if high < low or close > high or close < low:
        raise ValueError("invalid OHLC range")
    return high, low, close


def true_ranges(bars: Sequence[Mapping[str, object]]) -> list[float]:
    """Return causal true ranges for closed bars."""
    result: list[float] = []
    previous_close: float | None = None
    for bar in bars:
        high, low, close = _bar_prices(bar)
        if previous_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - previous_close), abs(low - previous_close))
        result.append(tr)
        previous_close = close
    return result


def wilder_atr(
    bars: Sequence[Mapping[str, object]],
    *,
    period: int = 14,
) -> list[float | None]:
    """Return Wilder ATR aligned to bars using only current/past closed bars.

    The first period - 1 outputs are None. The seed ATR is the simple mean of
    the first period true ranges; subsequent values use Wilder smoothing.
    Future bars cannot alter any already-produced value.
    """
    if isinstance(period, bool) or not isinstance(period, int) or period <= 0:
        raise ValueError("ATR period must be a positive integer")

    trs = true_ranges(bars)
    output: list[float | None] = [None] * len(trs)
    if len(trs) < period:
        return output

    atr = sum(trs[:period]) / period
    if not isfinite(atr) or atr < 0:
        raise ValueError("invalid ATR")
    output[period - 1] = atr

    for i in range(period, len(trs)):
        atr = ((atr * (period - 1)) + trs[i]) / period
        if not isfinite(atr) or atr < 0:
            raise ValueError("invalid ATR")
        output[i] = atr
    return output


def atr14(bars: Sequence[Mapping[str, object]]) -> list[float | None]:
    """Convenience wrapper for the project-standard Wilder ATR14."""
    return wilder_atr(bars, period=14)
