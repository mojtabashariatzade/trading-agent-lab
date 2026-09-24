"""Canonical strategy-family registry for Epic #38 reconciliation.

This registry preserves contract S01-S15 identifiers while explicitly mapping each
entry to the Epic #38 taxonomy labels.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Literal


_CONTRACT_ID_PATTERN = re.compile(r"^S(0[1-9]|1[0-5])$")

_EXPECTED_CANONICAL_MAPPING: dict[str, tuple[int, str, str]] = {
    "S01": (1, "EMA / trend-following", "DIRECT"),
    "S02": (2, "Breakout / Donchian", "DIRECT"),
    "S03": (7, "Volatility expansion/compression", "RECONCILED"),
    "S04": (3, "Session-range breakout", "DIRECT"),
    "S05": (1, "EMA / trend-following", "RECONCILED"),
    "S06": (6, "RSI-style exhaustion/reversal", "DIRECT"),
    "S07": (4, "Mean reversion / Bollinger re-entry", "DIRECT"),
    "S08": (8, "Price-action / candle-structure", "RECONCILED"),
    "S09": (10, "Multi-timeframe trend/regime", "DIRECT"),
    "S10": (11, "Currency-strength / cross-sectional FX", "DIRECT"),
    "S11": (12, "Carry / rate-differential regime", "DIRECT"),
    "S12": (13, "Macro-surprise", "DIRECT"),
    "S13": (13, "Macro-surprise", "RECONCILED"),
    "S14": (14, "Central-bank communication/text", "DIRECT"),
    "S15": (15, "News/event-risk reaction", "DIRECT"),
}


@dataclass(frozen=True)
class StrategyFamilyDefinition:
    contract_id: str
    contract_name: str
    epic_family_id: int
    epic_family_name: str
    taxonomy_alignment: Literal["DIRECT", "RECONCILED"]
    taxonomy_note: str
    variant_count_bounds: tuple[int, int]
    parameter_bounds: dict[str, tuple[float, float]]
    filters: tuple[str, ...]
    horizon_bars: tuple[int, int]
    data_prerequisites: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _CONTRACT_ID_PATTERN.fullmatch(self.contract_id):
            raise ValueError("contract_id must be one of S01..S15")
        if not self.contract_name.strip() or not self.epic_family_name.strip():
            raise ValueError("family names are required")
        if not (1 <= self.epic_family_id <= 15):
            raise ValueError("epic_family_id must be in [1, 15]")
        if self.taxonomy_alignment not in {"DIRECT", "RECONCILED"}:
            raise ValueError("taxonomy_alignment must be DIRECT or RECONCILED")
        if self.taxonomy_alignment == "DIRECT" and self.taxonomy_note.strip():
            raise ValueError("direct mappings must keep taxonomy_note empty")
        if self.taxonomy_alignment == "RECONCILED" and not self.taxonomy_note.strip():
            raise ValueError("reconciled mappings require an explicit taxonomy_note")

        min_variants, max_variants = self.variant_count_bounds
        if min_variants < 1 or max_variants < min_variants:
            raise ValueError("variant_count_bounds must be positive and ordered")

        min_horizon, max_horizon = self.horizon_bars
        if min_horizon < 1 or max_horizon < min_horizon:
            raise ValueError("horizon_bars must be positive and ordered")

        if not self.parameter_bounds:
            raise ValueError("parameter_bounds are required")
        for key, bounds in self.parameter_bounds.items():
            if not key.strip():
                raise ValueError("parameter name cannot be empty")
            lower, upper = bounds
            if upper < lower:
                raise ValueError(f"parameter bound is not ordered for {key}")

        if not self.filters:
            raise ValueError("at least one eligibility filter is required")
        if not self.data_prerequisites:
            raise ValueError("data_prerequisites are required")


@dataclass(frozen=True)
class FamilyEligibility:
    contract_id: str
    eligible: bool
    missing_prerequisites: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _CONTRACT_ID_PATTERN.fullmatch(self.contract_id):
            raise ValueError("contract_id must be one of S01..S15")
        normalized = tuple(sorted({str(item).strip() for item in self.missing_prerequisites if str(item).strip()}))
        object.__setattr__(self, "missing_prerequisites", normalized)
        if self.eligible and normalized:
            raise ValueError("eligible entries may not include missing_prerequisites")


def _normalized_capabilities(available_prerequisites: Iterable[str]) -> set[str]:
    return {str(item).strip() for item in available_prerequisites if str(item).strip()}


def validated_strategy_family_registry() -> tuple[StrategyFamilyDefinition, ...]:
    """Return the default registry after strict identity/coverage checks.

    This helper gives callers one canonical checked source so downstream code can
    fail fast if accidental edits remove an expected contract family.
    """

    registry = default_strategy_family_registry()
    if len(registry) != 15:
        raise ValueError("registry must contain exactly 15 entries")
    ids = [entry.contract_id for entry in registry]
    expected_order = [f"S{i:02d}" for i in range(1, 16)]
    if ids != expected_order:
        raise ValueError("registry must be ordered by contract_id from S01 to S15")
    unique_ids = set(ids)
    expected_ids = {f"S{i:02d}" for i in range(1, 16)}
    if unique_ids != expected_ids or len(ids) != len(unique_ids):
        raise ValueError("registry must contain each of S01..S15 exactly once")

    for entry in registry:
        expected_epic_id, expected_epic_name, expected_alignment = _EXPECTED_CANONICAL_MAPPING[entry.contract_id]
        if entry.epic_family_id != expected_epic_id:
            raise ValueError(f"{entry.contract_id} must map to epic_family_id={expected_epic_id}")
        if entry.epic_family_name != expected_epic_name:
            raise ValueError(f"{entry.contract_id} must map to epic_family_name='{expected_epic_name}'")
        if entry.taxonomy_alignment != expected_alignment:
            raise ValueError(f"{entry.contract_id} must keep taxonomy_alignment={expected_alignment}")

    return registry


def default_strategy_family_registry() -> tuple[StrategyFamilyDefinition, ...]:
    """Return canonical S01-S15 family definitions with bounded search spaces."""

    return (
        StrategyFamilyDefinition(
            contract_id="S01",
            contract_name="EMA trend",
            epic_family_id=1,
            epic_family_name="EMA / trend-following",
            taxonomy_alignment="DIRECT",
            taxonomy_note="",
            variant_count_bounds=(6, 30),
            parameter_bounds={"fast_period": (5, 30), "slow_period": (20, 120), "atr_stop_mult": (1.0, 3.0)},
            filters=("trend_strength_adx_min", "spread_max_pips"),
            horizon_bars=(4, 64),
            data_prerequisites=("ohlcv_m15", "spread_bid_ask"),
        ),
        StrategyFamilyDefinition(
            contract_id="S02",
            contract_name="Donchian breakout",
            epic_family_id=2,
            epic_family_name="Breakout / Donchian",
            taxonomy_alignment="DIRECT",
            taxonomy_note="",
            variant_count_bounds=(6, 24),
            parameter_bounds={"channel_lookback": (10, 80), "breakout_buffer_pips": (0.0, 3.0), "atr_stop_mult": (1.0, 4.0)},
            filters=("volatility_floor_atr", "spread_max_pips"),
            horizon_bars=(4, 80),
            data_prerequisites=("ohlcv_m15", "spread_bid_ask"),
        ),
        StrategyFamilyDefinition(
            contract_id="S03",
            contract_name="Volatility compression breakout",
            epic_family_id=7,
            epic_family_name="Volatility expansion/compression",
            taxonomy_alignment="RECONCILED",
            taxonomy_note="Mapped from contract breakout-compression wording to epic volatility regime bucket.",
            variant_count_bounds=(6, 24),
            parameter_bounds={"compression_window": (12, 96), "compression_pct_rank_max": (0.05, 0.35), "expansion_trigger_mult": (1.1, 2.5)},
            filters=("min_session_liquidity", "spread_max_pips"),
            horizon_bars=(4, 64),
            data_prerequisites=("ohlcv_m15", "spread_bid_ask"),
        ),
        StrategyFamilyDefinition(
            contract_id="S04",
            contract_name="Session range breakout",
            epic_family_id=3,
            epic_family_name="Session-range breakout",
            taxonomy_alignment="DIRECT",
            taxonomy_note="",
            variant_count_bounds=(6, 20),
            parameter_bounds={"range_start_hour_london": (7, 9), "range_duration_bars": (2, 8), "breakout_buffer_pips": (0.0, 2.0)},
            filters=("session_calendar_valid", "spread_max_pips"),
            horizon_bars=(2, 40),
            data_prerequisites=("ohlcv_m15", "spread_bid_ask", "iana_timezone_rules"),
        ),
        StrategyFamilyDefinition(
            contract_id="S05",
            contract_name="Trend pullback",
            epic_family_id=1,
            epic_family_name="EMA / trend-following",
            taxonomy_alignment="RECONCILED",
            taxonomy_note="Handled as pullback-entry variants under the epic trend-following family.",
            variant_count_bounds=(6, 24),
            parameter_bounds={"trend_ma_period": (30, 200), "pullback_depth_atr": (0.3, 2.0), "resume_trigger_bars": (1, 8)},
            filters=("trend_strength_adx_min", "no_major_news_window"),
            horizon_bars=(4, 80),
            data_prerequisites=("ohlcv_m15", "spread_bid_ask", "event_calendar_pti"),
        ),
        StrategyFamilyDefinition(
            contract_id="S06",
            contract_name="RSI mean reversion",
            epic_family_id=6,
            epic_family_name="RSI-style exhaustion/reversal",
            taxonomy_alignment="DIRECT",
            taxonomy_note="",
            variant_count_bounds=(6, 24),
            parameter_bounds={"rsi_period": (5, 30), "oversold_level": (10, 35), "overbought_level": (65, 90)},
            filters=("range_regime_filter", "spread_max_pips"),
            horizon_bars=(2, 32),
            data_prerequisites=("ohlcv_m15", "spread_bid_ask"),
        ),
        StrategyFamilyDefinition(
            contract_id="S07",
            contract_name="Bollinger re-entry",
            epic_family_id=4,
            epic_family_name="Mean reversion / Bollinger re-entry",
            taxonomy_alignment="DIRECT",
            taxonomy_note="",
            variant_count_bounds=(6, 24),
            parameter_bounds={"window": (10, 60), "deviation_mult": (1.0, 3.5), "reentry_confirmation_bars": (1, 4)},
            filters=("range_regime_filter", "spread_max_pips"),
            horizon_bars=(2, 32),
            data_prerequisites=("ohlcv_m15", "spread_bid_ask"),
        ),
        StrategyFamilyDefinition(
            contract_id="S08",
            contract_name="Failed breakout",
            epic_family_id=8,
            epic_family_name="Price-action / candle-structure",
            taxonomy_alignment="RECONCILED",
            taxonomy_note="False-break structure is tracked in epic price-action/candle-structure bucket.",
            variant_count_bounds=(6, 20),
            parameter_bounds={"lookback_bars": (8, 64), "failure_reentry_bars": (1, 6), "wick_body_ratio_min": (1.2, 4.0)},
            filters=("swing_structure_valid", "spread_max_pips"),
            horizon_bars=(2, 32),
            data_prerequisites=("ohlcv_m15", "spread_bid_ask"),
        ),
        StrategyFamilyDefinition(
            contract_id="S09",
            contract_name="Multi-timeframe alignment",
            epic_family_id=10,
            epic_family_name="Multi-timeframe trend/regime",
            taxonomy_alignment="DIRECT",
            taxonomy_note="",
            variant_count_bounds=(6, 20),
            parameter_bounds={"m15_signal_period": (5, 30), "h1_trend_period": (10, 80), "h4_regime_period": (10, 80)},
            filters=("all_timeframes_available", "spread_max_pips"),
            horizon_bars=(4, 96),
            data_prerequisites=("ohlcv_m15", "ohlcv_h1", "ohlcv_h4", "spread_bid_ask"),
        ),
        StrategyFamilyDefinition(
            contract_id="S10",
            contract_name="Currency-basket strength",
            epic_family_id=11,
            epic_family_name="Currency-strength / cross-sectional FX",
            taxonomy_alignment="DIRECT",
            taxonomy_note="",
            variant_count_bounds=(4, 16),
            parameter_bounds={"basket_lookback_bars": (8, 96), "strength_zscore_threshold": (0.5, 2.5), "confirmation_bars": (1, 8)},
            filters=("cross_pair_coverage_min", "spread_max_pips"),
            horizon_bars=(4, 96),
            data_prerequisites=("ohlcv_m15", "cross_pair_ohlcv_m15", "spread_bid_ask"),
        ),
        StrategyFamilyDefinition(
            contract_id="S11",
            contract_name="Rate/yield context with short-horizon entry",
            epic_family_id=12,
            epic_family_name="Carry / rate-differential regime",
            taxonomy_alignment="DIRECT",
            taxonomy_note="",
            variant_count_bounds=(4, 16),
            parameter_bounds={"carry_lookback_days": (5, 120), "yield_spread_zscore": (0.5, 3.0), "entry_trigger_bars": (1, 8)},
            filters=("official_rate_series_available", "release_latency_resolved"),
            horizon_bars=(4, 96),
            data_prerequisites=("policy_rate_series_pti", "yield_curve_series_pti", "ohlcv_m15", "spread_bid_ask"),
        ),
        StrategyFamilyDefinition(
            contract_id="S12",
            contract_name="UK macro surprise",
            epic_family_id=13,
            epic_family_name="Macro-surprise",
            taxonomy_alignment="DIRECT",
            taxonomy_note="",
            variant_count_bounds=(4, 16),
            parameter_bounds={"surprise_zscore_abs_min": (0.5, 3.5), "cooldown_hours": (1, 72), "entry_delay_minutes": (0, 180)},
            filters=("uk_release_vintage_available", "forecast_known_pre_release"),
            horizon_bars=(1, 48),
            data_prerequisites=("official_uk_releases_pti", "consensus_forecasts_pti", "ohlcv_m15", "spread_bid_ask"),
        ),
        StrategyFamilyDefinition(
            contract_id="S13",
            contract_name="Japan macro surprise",
            epic_family_id=13,
            epic_family_name="Macro-surprise",
            taxonomy_alignment="RECONCILED",
            taxonomy_note="Shares epic macro-surprise bucket with UK events but remains a separate contract family ID.",
            variant_count_bounds=(4, 16),
            parameter_bounds={"surprise_zscore_abs_min": (0.5, 3.5), "cooldown_hours": (1, 72), "entry_delay_minutes": (0, 180)},
            filters=("jp_release_vintage_available", "forecast_known_pre_release"),
            horizon_bars=(1, 48),
            data_prerequisites=("official_jp_releases_pti", "consensus_forecasts_pti", "ohlcv_m15", "spread_bid_ask"),
        ),
        StrategyFamilyDefinition(
            contract_id="S14",
            contract_name="Central-bank statement change",
            epic_family_id=14,
            epic_family_name="Central-bank communication/text",
            taxonomy_alignment="DIRECT",
            taxonomy_note="",
            variant_count_bounds=(4, 16),
            parameter_bounds={"text_change_score_min": (0.1, 0.9), "hawkish_dovish_threshold": (0.1, 0.9), "entry_delay_minutes": (0, 240)},
            filters=("official_statement_timestamped", "language_model_confidence_min"),
            horizon_bars=(1, 64),
            data_prerequisites=("official_central_bank_text_pti", "policy_calendar_pti", "ohlcv_m15", "spread_bid_ask"),
        ),
        StrategyFamilyDefinition(
            contract_id="S15",
            contract_name="Reversal after a news shock",
            epic_family_id=15,
            epic_family_name="News/event-risk reaction",
            taxonomy_alignment="DIRECT",
            taxonomy_note="",
            variant_count_bounds=(4, 16),
            parameter_bounds={"shock_sigma_min": (1.5, 6.0), "reversal_confirmation_bars": (1, 10), "max_reversal_window_bars": (2, 32)},
            filters=("headline_archive_pti", "event_availability_time_known"),
            horizon_bars=(1, 48),
            data_prerequisites=("headline_archive_pti", "ohlcv_m15", "spread_bid_ask"),
        ),
    )


def family_definition_by_contract_id(contract_id: str) -> StrategyFamilyDefinition:
    """Return one canonical family definition for a contract ID (S01..S15)."""

    contract_id = str(contract_id).strip().upper()
    for entry in validated_strategy_family_registry():
        if entry.contract_id == contract_id:
            return entry
    raise KeyError(f"Unknown contract_id: {contract_id}")


def family_eligibility_matrix(*, available_prerequisites: Iterable[str]) -> tuple[FamilyEligibility, ...]:
    """Compute eligibility per contract family from available point-in-time prerequisites.

    Families are eligible only when all declared data_prerequisites are available.
    """

    available = _normalized_capabilities(available_prerequisites)
    matrix: list[FamilyEligibility] = []
    for entry in validated_strategy_family_registry():
        missing = tuple(sorted(prereq for prereq in entry.data_prerequisites if prereq not in available))
        matrix.append(
            FamilyEligibility(
                contract_id=entry.contract_id,
                eligible=not missing,
                missing_prerequisites=missing,
            )
        )
    return tuple(matrix)


__all__ = [
    "FamilyEligibility",
    "family_definition_by_contract_id",
    "family_eligibility_matrix",
    "StrategyFamilyDefinition",
    "default_strategy_family_registry",
    "validated_strategy_family_registry",
]
