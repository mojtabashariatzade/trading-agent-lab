"""Deterministic intra-family league harness built on the canonical family registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from trading_lab.strategies import StrategyFamilyDefinition, default_strategy_family_registry


@dataclass(frozen=True)
class PrerequisiteGateResult:
    prerequisite: str
    available: bool
    reason: str


@dataclass(frozen=True)
class VariantEligibility:
    contract_id: str
    variant_id: str
    eligible: bool
    reasons: tuple[str, ...]
    prerequisite_results: tuple[PrerequisiteGateResult, ...]


@dataclass(frozen=True)
class FamilyEligibilityMatrixRow:
    contract_id: str
    contract_name: str
    epic_family_id: int
    epic_family_name: str
    variant_count_bounds: tuple[int, int]
    variants: tuple[VariantEligibility, ...]


@dataclass(frozen=True)
class RankedVariant:
    contract_id: str
    variant_id: str
    score: float


@dataclass(frozen=True)
class IntraFamilyLeagueResult:
    matrix: tuple[FamilyEligibilityMatrixRow, ...]
    ranked_by_family: tuple[tuple[str, tuple[RankedVariant, ...]], ...]


def _variant_ids(contract_id: str, bounds: tuple[int, int]) -> tuple[str, ...]:
    min_variants, max_variants = bounds
    # Deterministic harness picks a bounded executable slice anchored by the
    # lower bound to avoid randomization and preserve reproducibility.
    return tuple(f"{contract_id}-V{i:02d}" for i in range(1, min_variants + 1))


def _prerequisite_status(
    definition: StrategyFamilyDefinition,
    available_prerequisites: Mapping[str, bool],
) -> tuple[PrerequisiteGateResult, ...]:
    statuses: list[PrerequisiteGateResult] = []
    for prerequisite in definition.data_prerequisites:
        if prerequisite not in available_prerequisites:
            statuses.append(
                PrerequisiteGateResult(
                    prerequisite=prerequisite,
                    available=False,
                    reason="PREREQUISITE_STATUS_UNKNOWN",
                )
            )
            continue
        available = bool(available_prerequisites[prerequisite])
        statuses.append(
            PrerequisiteGateResult(
                prerequisite=prerequisite,
                available=available,
                reason=(
                    "AVAILABLE"
                    if available
                    else "PREREQUISITE_UNAVAILABLE"
                ),
            )
        )
    return tuple(statuses)


class IntraFamilyLeagueHarness:
    """Deterministic family/variant eligibility + ranking harness."""

    def __init__(
        self,
        *,
        registry: Sequence[StrategyFamilyDefinition] | None = None,
    ) -> None:
        resolved_registry = tuple(registry or default_strategy_family_registry())
        if not resolved_registry:
            raise ValueError("registry is required")
        self.registry = resolved_registry

    def evaluate(
        self,
        *,
        available_prerequisites: Mapping[str, bool],
        variant_scores: Mapping[str, Mapping[str, float]] | None = None,
    ) -> IntraFamilyLeagueResult:
        variant_scores = variant_scores or {}

        matrix_rows: list[FamilyEligibilityMatrixRow] = []
        ranked_rows: list[tuple[str, tuple[RankedVariant, ...]]] = []

        for definition in self.registry:
            prerequisite_results = _prerequisite_status(definition, available_prerequisites)
            missing = tuple(
                f"{result.reason}:{result.prerequisite}"
                for result in prerequisite_results
                if not result.available
            )
            variants: list[VariantEligibility] = []
            ranked: list[RankedVariant] = []
            for variant_id in _variant_ids(definition.contract_id, definition.variant_count_bounds):
                eligible = not missing
                reasons = ("ALL_PREREQUISITES_AVAILABLE",) if eligible else missing
                variant = VariantEligibility(
                    contract_id=definition.contract_id,
                    variant_id=variant_id,
                    eligible=eligible,
                    reasons=reasons,
                    prerequisite_results=prerequisite_results,
                )
                variants.append(variant)
                if eligible:
                    score = float(
                        variant_scores.get(definition.contract_id, {}).get(variant_id, 0.0)
                    )
                    ranked.append(
                        RankedVariant(
                            contract_id=definition.contract_id,
                            variant_id=variant_id,
                            score=score,
                        )
                    )

            ranked_sorted = tuple(
                sorted(
                    ranked,
                    key=lambda item: (-item.score, item.variant_id),
                )
            )
            matrix_rows.append(
                FamilyEligibilityMatrixRow(
                    contract_id=definition.contract_id,
                    contract_name=definition.contract_name,
                    epic_family_id=definition.epic_family_id,
                    epic_family_name=definition.epic_family_name,
                    variant_count_bounds=definition.variant_count_bounds,
                    variants=tuple(variants),
                )
            )
            ranked_rows.append((definition.contract_id, ranked_sorted))

        return IntraFamilyLeagueResult(
            matrix=tuple(matrix_rows),
            ranked_by_family=tuple(ranked_rows),
        )


__all__ = [
    "FamilyEligibilityMatrixRow",
    "IntraFamilyLeagueHarness",
    "IntraFamilyLeagueResult",
    "PrerequisiteGateResult",
    "RankedVariant",
    "VariantEligibility",
]
