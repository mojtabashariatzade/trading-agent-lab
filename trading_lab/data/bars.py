"""Half-open UTC M15 bars from bid/ask quotes. Local Kian delivery; no network I/O."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite


def _aware(ts: datetime) -> datetime:
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return ts.astimezone(timezone.utc)


@dataclass(frozen=True)
class Quote:
    at: datetime
    bid: float
    ask: float

    def __post_init__(self) -> None:
        _aware(self.at)
        if not all(isfinite(x) and x > 0 for x in (self.bid, self.ask)) or self.bid > self.ask:
            raise ValueError("Invalid bid/ask")


def m15_floor(ts: datetime) -> datetime:
    ts = _aware(ts)
    return ts.replace(minute=(ts.minute // 15) * 15, second=0, microsecond=0)


def assign_bar_start(ts: datetime) -> datetime:
    """Boundary quote at exact :00/:15/:30/:45 starts the NEXT interval (half-open)."""
    ts = _aware(ts)
    floored = m15_floor(ts)
    if ts == floored:
        return floored
    return floored


def build_m15_bars(quotes: list[Quote]) -> list[dict]:
    """Build bars from quotes. Missing intervals are omitted, never invented."""
    if not quotes:
        return []
    ordered = sorted(quotes, key=lambda q: q.at)
    buckets: dict[datetime, list[Quote]] = {}
    for quote in ordered:
        start = m15_floor(quote.at)
        buckets.setdefault(start, []).append(quote)
    bars = []
    for start in sorted(buckets):
        rows = buckets[start]
        mids = [(q.bid + q.ask) / 2 for q in rows]
        bars.append({
            "start": start.isoformat(),
            "end": (start + timedelta(minutes=15)).isoformat(),
            "open": mids[0],
            "high": max(mids),
            "low": min(mids),
            "close": mids[-1],
            "ticks": len(rows),
            "gap_before": False,
        })
    return bars
