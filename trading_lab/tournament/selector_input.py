"""Deterministic selector-input contract built from championship promotion output.

Required candidate fields for downstream Core-league consumers:
- contract_id
- epic_family_id
- variant_id
- score
- promotion_bucket ("champion" or "runner_up")
- promotion_rank (1-indexed rank within its promotion bucket)

Contract invariants:
- candidate ordering is deterministic and stable
- candidate contract_ids are unique
- rejected families provide explicit non-empty machine-readable reasons
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .inter_family import InterFamilyChampionshipResult


@dataclass(frozen=True)
class SelectorCandidate:
    contract_id: str
    epic_family_id: int
    variant_id: str
    score: float
    promotion_bucket: str
    promotion_rank: int


@dataclass(frozen=True)
class RejectedFamilyReason:
    contract_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SelectorInputContract:
    schema_version: str
    candidates: tuple[SelectorCandidate, ...]
    rejected_families: tuple[RejectedFamilyReason, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a machine-readable artifact for downstream deterministic consumption."""
        return {
            "schema_version": self.schema_version,
            "candidates": [
                {
                    "contract_id": candidate.contract_id,
                    "epic_family_id": candidate.epic_family_id,
                    "variant_id": candidate.variant_id,
                    "score": candidate.score,
                    "promotion_bucket": candidate.promotion_bucket,
                    "promotion_rank": candidate.promotion_rank,
                }
                for candidate in self.candidates
            ],
            "rejected_families": [
                {
                    "contract_id": family.contract_id,
                    "reasons": list(family.reasons),
                }
                for family in self.rejected_families
            ],
        }


class SelectorInputContractHarness:
    """Build and validate deterministic selector-input artifacts."""

    SCHEMA_VERSION = "selector-input.v1"

    def build(
        self,
        *,
        championship_result: InterFamilyChampionshipResult,
    ) -> SelectorInputContract:
        if not isinstance(championship_result, InterFamilyChampionshipResult):
            raise TypeError("championship_result must be an InterFamilyChampionshipResult")

        promotion = championship_result.promotion
        seen_contracts: set[str] = set()
        candidates: list[SelectorCandidate] = []

        for bucket_name, promoted in (
            ("champion", promotion.selected_champions),
            ("runner_up", promotion.runner_ups),
        ):
            for index, item in enumerate(promoted, start=1):
                if item.contract_id in seen_contracts:
                    raise ValueError(
                        f"duplicate promoted contract_id in selector input: {item.contract_id}"
                    )
                if not isfinite(item.score):
                    raise ValueError(
                        f"non-finite score in selector input for {item.contract_id}: {item.score}"
                    )
                seen_contracts.add(item.contract_id)
                candidates.append(
                    SelectorCandidate(
                        contract_id=item.contract_id,
                        epic_family_id=item.epic_family_id,
                        variant_id=item.variant_id,
                        score=float(item.score),
                        promotion_bucket=bucket_name,
                        promotion_rank=index,
                    )
                )

        rejected_families: list[RejectedFamilyReason] = []
        for ineligible in sorted(
            promotion.ineligible_families,
            key=lambda item: item.contract_id,
        ):
            cleaned_reasons = tuple(
                sorted(
                    {
                        reason
                        for reason in ineligible.reasons
                        if reason and reason != "ALL_PREREQUISITES_AVAILABLE"
                    }
                )
            )
            if not cleaned_reasons:
                raise ValueError(
                    f"ineligible family requires explicit reasons: {ineligible.contract_id}"
                )
            rejected_families.append(
                RejectedFamilyReason(
                    contract_id=ineligible.contract_id,
                    reasons=cleaned_reasons,
                )
            )

        return SelectorInputContract(
            schema_version=self.SCHEMA_VERSION,
            candidates=tuple(candidates),
            rejected_families=tuple(rejected_families),
        )


__all__ = [
    "RejectedFamilyReason",
    "SelectorCandidate",
    "SelectorInputContract",
    "SelectorInputContractHarness",
]
