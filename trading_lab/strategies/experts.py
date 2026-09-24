"""Three deterministic research strategy experts for T003."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time, timedelta
from math import isfinite
from statistics import fmean, pstdev
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .contracts import (
    ExitConfig,
    ExitLeague,
    Side,
    StrategyProposal,
    choose_exit,
    closed_bars,
)


def _positive_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _positive_float(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def _ema(values: Sequence[float], period: int) -> float:
    if not values:
        raise ValueError("EMA requires values")
    alpha = 2.0 / (period + 1.0)
    value = float(values[0])
    for item in values[1:]:
        value = alpha * float(item) + (1.0 - alpha) * value
    return value


def _proposal(
    *,
    strategy_id: str,
    version: str,
    bars,
    side: Side,
    reason: str,
    expiry_bars: int,
    league: ExitLeague,
    native_exit: ExitConfig,
    shared_exit: ExitConfig | None,
) -> StrategyProposal:
    latest = bars[-1]
    width = latest.end - latest.start
    if width <= timedelta(0):
        raise ValueError("Invalid bar width")
    exit_config = None
    if side != Side.PASS:
        exit_config = choose_exit(native_exit, league=league, shared_exit=shared_exit)
    return StrategyProposal(
        strategy_id=strategy_id,
        version=version,
        side=side,
        generated_at=latest.end,
        expires_at=latest.end + width * expiry_bars,
        reason=reason,
        exit_config=exit_config,
        league=league,
    )


@dataclass(frozen=True)
class EmaTrendConfig:
    fast_period: int = 5
    slow_period: int = 12
    expiry_bars: int = 2
    native_exit: ExitConfig = field(default_factory=lambda: ExitConfig(0.30, 0.60))

    def __post_init__(self) -> None:
        fast = _positive_int(self.fast_period, "fast_period")
        slow = _positive_int(self.slow_period, "slow_period")
        expiry = _positive_int(self.expiry_bars, "expiry_bars")
        if fast >= slow:
            raise ValueError("fast_period must be less than slow_period")
        object.__setattr__(self, "fast_period", fast)
        object.__setattr__(self, "slow_period", slow)
        object.__setattr__(self, "expiry_bars", expiry)


class EmaTrendExpert:
    """EMA crossover trend proposal from closed bars only."""

    strategy_id = "EMA_TREND"
    version = "1.0.0"

    def __init__(self, config: EmaTrendConfig | None = None):
        self.config = config or EmaTrendConfig()

    def propose(
        self,
        rows: Sequence[Mapping[str, object]],
        *,
        league: ExitLeague = ExitLeague.NATIVE,
        shared_exit: ExitConfig | None = None,
    ) -> StrategyProposal:
        bars = closed_bars(rows)
        need = self.config.slow_period + 1
        if len(bars) < need:
            return self._pass(bars, league, shared_exit, "INSUFFICIENT_HISTORY")
        window = bars[-need:]
        if any(bar.gap_before for bar in window[1:]):
            return self._pass(bars, league, shared_exit, "DATA_GAP")

        closes = [bar.close for bar in bars]
        fast_prev = _ema(closes[:-1], self.config.fast_period)
        slow_prev = _ema(closes[:-1], self.config.slow_period)
        fast_now = _ema(closes, self.config.fast_period)
        slow_now = _ema(closes, self.config.slow_period)

        if fast_prev <= slow_prev and fast_now > slow_now:
            side, reason = Side.BUY, "FAST_EMA_CROSSED_ABOVE_SLOW"
        elif fast_prev >= slow_prev and fast_now < slow_now:
            side, reason = Side.SELL, "FAST_EMA_CROSSED_BELOW_SLOW"
        else:
            side, reason = Side.PASS, "NO_CROSSOVER"

        return _proposal(
            strategy_id=self.strategy_id,
            version=self.version,
            bars=bars,
            side=side,
            reason=reason,
            expiry_bars=self.config.expiry_bars,
            league=league,
            native_exit=self.config.native_exit,
            shared_exit=shared_exit,
        )

    def _pass(self, bars, league, shared_exit, reason):
        if not bars:
            raise ValueError("At least one closed bar is required")
        return _proposal(
            strategy_id=self.strategy_id,
            version=self.version,
            bars=bars,
            side=Side.PASS,
            reason=reason,
            expiry_bars=self.config.expiry_bars,
            league=league,
            native_exit=self.config.native_exit,
            shared_exit=shared_exit,
        )


@dataclass(frozen=True)
class BollingerReentryConfig:
    window: int = 20
    deviations: float = 2.0
    expiry_bars: int = 2
    native_exit: ExitConfig = field(default_factory=lambda: ExitConfig(0.25, 0.40))

    def __post_init__(self) -> None:
        object.__setattr__(self, "window", _positive_int(self.window, "window"))
        object.__setattr__(self, "deviations", _positive_float(self.deviations, "deviations"))
        object.__setattr__(self, "expiry_bars", _positive_int(self.expiry_bars, "expiry_bars"))


class BollingerReentryExpert:
    """Mean-reversion proposal when price re-enters a causal Bollinger envelope."""

    strategy_id = "BOLLINGER_REENTRY"
    version = "1.0.0"

    def __init__(self, config: BollingerReentryConfig | None = None):
        self.config = config or BollingerReentryConfig()

    @staticmethod
    def _band(values: Sequence[float], deviations: float) -> tuple[float, float]:
        mean = fmean(values)
        sigma = pstdev(values)
        return mean - deviations * sigma, mean + deviations * sigma

    def propose(
        self,
        rows: Sequence[Mapping[str, object]],
        *,
        league: ExitLeague = ExitLeague.NATIVE,
        shared_exit: ExitConfig | None = None,
    ) -> StrategyProposal:
        bars = closed_bars(rows)
        need = self.config.window + 1
        if len(bars) < need:
            return self._pass(bars, league, shared_exit, "INSUFFICIENT_HISTORY")
        window = bars[-need:]
        if any(bar.gap_before for bar in window[1:]):
            return self._pass(bars, league, shared_exit, "DATA_GAP")

        closes = [bar.close for bar in bars]
        previous_sample = closes[-self.config.window - 1 : -1]
        current_sample = closes[-self.config.window :]
        prev_lower, prev_upper = self._band(previous_sample, self.config.deviations)
        curr_lower, curr_upper = self._band(current_sample, self.config.deviations)
        previous_close = closes[-2]
        current_close = closes[-1]

        if previous_close < prev_lower and current_close >= curr_lower:
            side, reason = Side.BUY, "REENTERED_FROM_BELOW"
        elif previous_close > prev_upper and current_close <= curr_upper:
            side, reason = Side.SELL, "REENTERED_FROM_ABOVE"
        else:
            side, reason = Side.PASS, "NO_REENTRY"

        return _proposal(
            strategy_id=self.strategy_id,
            version=self.version,
            bars=bars,
            side=side,
            reason=reason,
            expiry_bars=self.config.expiry_bars,
            league=league,
            native_exit=self.config.native_exit,
            shared_exit=shared_exit,
        )

    def _pass(self, bars, league, shared_exit, reason):
        if not bars:
            raise ValueError("At least one closed bar is required")
        return _proposal(
            strategy_id=self.strategy_id,
            version=self.version,
            bars=bars,
            side=Side.PASS,
            reason=reason,
            expiry_bars=self.config.expiry_bars,
            league=league,
            native_exit=self.config.native_exit,
            shared_exit=shared_exit,
        )


@dataclass(frozen=True)
class SessionBreakoutConfig:
    timezone_name: str = "Europe/London"
    range_start: time = time(8, 0)
    range_end: time = time(9, 0)
    expiry_bars: int = 4
    native_exit: ExitConfig = field(default_factory=lambda: ExitConfig(0.35, 0.70))

    def __post_init__(self) -> None:
        if not self.timezone_name.strip():
            raise ValueError("timezone_name is required")
        try:
            ZoneInfo(self.timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc
        if self.range_start >= self.range_end:
            raise ValueError("Session range must be same-day and increasing")
        object.__setattr__(self, "expiry_bars", _positive_int(self.expiry_bars, "expiry_bars"))


class SessionRangeBreakoutExpert:
    """Breakout from a defined local-session range using IANA timezone/DST rules."""

    strategy_id = "SESSION_RANGE_BREAKOUT"
    version = "1.0.0"

    def __init__(self, config: SessionBreakoutConfig | None = None):
        self.config = config or SessionBreakoutConfig()
        self._tz = ZoneInfo(self.config.timezone_name)

    def propose(
        self,
        rows: Sequence[Mapping[str, object]],
        *,
        league: ExitLeague = ExitLeague.NATIVE,
        shared_exit: ExitConfig | None = None,
    ) -> StrategyProposal:
        bars = closed_bars(rows)
        if not bars:
            raise ValueError("At least one closed bar is required")
        latest = bars[-1]
        latest_local = latest.start.astimezone(self._tz)
        if latest_local.timetz().replace(tzinfo=None) < self.config.range_end:
            return self._pass(bars, league, shared_exit, "SESSION_RANGE_NOT_CLOSED")

        session_date = latest_local.date()
        session_start = latest_local.replace(
            hour=self.config.range_start.hour,
            minute=self.config.range_start.minute,
            second=self.config.range_start.second,
            microsecond=0,
        )
        session_end = latest_local.replace(
            hour=self.config.range_end.hour,
            minute=self.config.range_end.minute,
            second=self.config.range_end.second,
            microsecond=0,
        )

        range_bars = []
        range_starts_local = []
        for candidate in bars[:-1]:
            local = candidate.start.astimezone(self._tz)
            local_time = local.timetz().replace(tzinfo=None)
            if (
                local.date() == session_date
                and self.config.range_start <= local_time < self.config.range_end
            ):
                range_bars.append(candidate)
                range_starts_local.append(local)

        if not range_bars:
            return self._pass(bars, league, shared_exit, "SESSION_RANGE_MISSING")
        if any(bar.gap_before for bar in range_bars[1:]) or latest.gap_before:
            return self._pass(bars, league, shared_exit, "DATA_GAP")

        bar_width = latest.end - latest.start
        expected_starts_local = []
        cursor = session_start
        while cursor < session_end:
            if cursor + bar_width > session_end:
                return self._pass(bars, league, shared_exit, "RANGE_INCOMPLETE")
            expected_starts_local.append(cursor)
            cursor += bar_width

        if any((bar.end - bar.start) != bar_width for bar in range_bars):
            return self._pass(bars, league, shared_exit, "RANGE_INCOMPLETE")
        if (
            len(range_starts_local) != len(expected_starts_local)
            or set(range_starts_local) != set(expected_starts_local)
        ):
            return self._pass(bars, league, shared_exit, "RANGE_INCOMPLETE")

        range_high = max(bar.high for bar in range_bars)
        range_low = min(bar.low for bar in range_bars)
        if latest.close > range_high:
            side, reason = Side.BUY, "CLOSED_ABOVE_SESSION_RANGE"
        elif latest.close < range_low:
            side, reason = Side.SELL, "CLOSED_BELOW_SESSION_RANGE"
        else:
            side, reason = Side.PASS, "NO_BREAKOUT"

        return _proposal(
            strategy_id=self.strategy_id,
            version=self.version,
            bars=bars,
            side=side,
            reason=reason,
            expiry_bars=self.config.expiry_bars,
            league=league,
            native_exit=self.config.native_exit,
            shared_exit=shared_exit,
        )

    def _pass(self, bars, league, shared_exit, reason):
        return _proposal(
            strategy_id=self.strategy_id,
            version=self.version,
            bars=bars,
            side=Side.PASS,
            reason=reason,
            expiry_bars=self.config.expiry_bars,
            league=league,
            native_exit=self.config.native_exit,
            shared_exit=shared_exit,
        )
