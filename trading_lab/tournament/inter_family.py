"""Deterministic inter-family championship and promotion contract harness."""

from __future__ import annotations

from dataclasses import dataclass

from .family_league import IntraFamilyLeagueResult, RankedVariant


@dataclass(frozen=True)
class FamilyChampion:
    contract_id: str
    epic_family_id: int
    variant_id: str
    score: float


@dataclass(frozen=True)
class IneligibleFamily:
    contract_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PromotionContract:
    selected_champions: tuple[FamilyChampion, ...]
    runner_ups: tuple[FamilyChampion, ...]
    ineligible_families: tuple[IneligibleFamily, ...]


@dataclass(frozen=True)
class InterFamilyChampionshipResult:
    championship_ranking: tuple[FamilyChampion, ...]
    promotion: PromotionContract


def _collect_ineligible_reasons(row) -> tuple[str, ...]:
    reasons = {
        reason
        for variant in row.variants
        for reason in variant.reasons
        if reason != "ALL_PREREQUISITES_AVAILABLE"
    }
    return tuple(sorted(reasons))


class InterFamilyChampionshipHarness:
    """Build deterministic cross-family ranking and promotion contract."""

    def evaluate(
        self,
        *,
        intra_family_result: IntraFamilyLeagueResult,
        champion_slots: int = 1,
        runner_up_slots: int = 2,
    ) -> InterFamilyChampionshipResult:
        if champion_slots < 1:
            raise ValueError("champion_slots must be >= 1")
        if runner_up_slots < 0:
            raise ValueError("runner_up_slots must be >= 0")

        metadata_by_contract = {row.contract_id: row for row in intra_family_result.matrix}
        ranked_by_contract = dict(intra_family_result.ranked_by_family)

        champions: list[FamilyChampion] = []
        ineligible: list[IneligibleFamily] = []

        for contract_id in sorted(metadata_by_contract.keys()):
            row = metadata_by_contract[contract_id]
            ranked_variants: tuple[RankedVariant, ...] = ranked_by_contract.get(contract_id, ())
            if not ranked_variants:
                ineligible.append(
                    IneligibleFamily(
                        contract_id=contract_id,
                        reasons=_collect_ineligible_reasons(row),
                    )
                )
                continue

            best = ranked_variants[0]
            champions.append(
                FamilyChampion(
                    contract_id=contract_id,
                    epic_family_id=row.epic_family_id,
                    variant_id=best.variant_id,
                    score=best.score,
                )
            )

        championship_ranking = tuple(
            sorted(
                champions,
                key=lambda item: (-item.score, item.contract_id, item.variant_id),
            )
        )

        selected_champions = championship_ranking[:champion_slots]

        selected_epic_families = {item.epic_family_id for item in selected_champions}
        runner_ups: list[FamilyChampion] = []
        for contender in championship_ranking[champion_slots:]:
            if contender.epic_family_id in selected_epic_families:
                continue
            runner_ups.append(contender)
            selected_epic_families.add(contender.epic_family_id)
            if len(runner_ups) >= runner_up_slots:
                break

        promotion = PromotionContract(
            selected_champions=tuple(selected_champions),
            runner_ups=tuple(runner_ups),
            ineligible_families=tuple(sorted(ineligible, key=lambda item: item.contract_id)),
        )

        return InterFamilyChampionshipResult(
            championship_ranking=championship_ranking,
            promotion=promotion,
        )


__all__ = [
    "FamilyChampion",
    "IneligibleFamily",
    "InterFamilyChampionshipHarness",
    "InterFamilyChampionshipResult",
    "PromotionContract",
]
