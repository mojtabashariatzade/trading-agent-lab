"""Deterministic Core-league candidate feed adapter.

Consumes selector-input artifacts and emits a deterministic candidate feed payload
for Core-league evaluation.

Input contract requirements:
- schema_version must be "selector-input.v1"
- candidates must include required selector candidate fields
- rejected_families must be present and machine-readable

Adapter invariants:
- output candidate ordering is deterministic
- contract_id values are unique
- ineligible-family payloads are rejected with machine-readable reason codes
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .selector_input import SelectorInputContract


class CandidateFeedValidationError(ValueError):
    """Machine-readable validation error for candidate-feed adaptation."""

    def __init__(self, message: str, *, reason_codes: tuple[str, ...]):
        super().__init__(message)
        self.reason_codes = reason_codes


@dataclass(frozen=True)
class CoreLeagueCandidate:
    contract_id: str
    epic_family_id: int
    variant_id: str
    score: float
    promotion_bucket: str
    promotion_rank: int


@dataclass(frozen=True)
class CoreLeagueCandidateFeed:
    schema_version: str
    source_selector_schema: str
    candidates: tuple[CoreLeagueCandidate, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "source_selector_schema": self.source_selector_schema,
            "candidates": [
                {
                    "contract_id": item.contract_id,
                    "epic_family_id": item.epic_family_id,
                    "variant_id": item.variant_id,
                    "score": item.score,
                    "promotion_bucket": item.promotion_bucket,
                    "promotion_rank": item.promotion_rank,
                }
                for item in self.candidates
            ],
        }


class CoreLeagueCandidateFeedAdapter:
    """Validate selector-input payloads and emit deterministic candidate feed."""

    FEED_SCHEMA_VERSION = "core-league-candidate-feed.v1"
    REQUIRED_SELECTOR_SCHEMA = "selector-input.v1"
    _BUCKET_ORDER = {"champion": 0, "runner_up": 1}

    def build(
        self,
        *,
        selector_input: SelectorInputContract | Mapping[str, object],
    ) -> CoreLeagueCandidateFeed:
        payload = self._coerce_payload(selector_input)
        reason_codes: set[str] = set()

        schema_version = payload.get("schema_version")
        if schema_version != self.REQUIRED_SELECTOR_SCHEMA:
            reason_codes.add("UNSUPPORTED_SELECTOR_SCHEMA")

        rejected_rows = payload.get("rejected_families")
        if not isinstance(rejected_rows, list):
            reason_codes.add("MISSING_REJECTED_FAMILIES")
            rejected_rows = []
        else:
            for row in rejected_rows:
                if not isinstance(row, Mapping):
                    reason_codes.add("MALFORMED_REJECTED_FAMILY_ROW")
                    continue
                contract_id = row.get("contract_id")
                reasons = row.get("reasons")
                if not isinstance(contract_id, str) or not contract_id.strip():
                    reason_codes.add("INVALID_REJECTED_CONTRACT_ID")
                if not isinstance(reasons, list) or not reasons or not all(
                    isinstance(item, str) and item.strip() for item in reasons
                ):
                    reason_codes.add("INVALID_REJECTED_REASONS")
            if rejected_rows:
                reason_codes.add("INELIGIBLE_FAMILIES_PRESENT")

        candidate_rows = payload.get("candidates")
        if not isinstance(candidate_rows, list):
            reason_codes.add("MISSING_CANDIDATES")
            candidate_rows = []

        if reason_codes:
            raise CandidateFeedValidationError(
                "selector input payload is not eligible for Core-league candidate feed",
                reason_codes=tuple(sorted(reason_codes)),
            )

        seen_contracts: set[str] = set()
        candidates: list[CoreLeagueCandidate] = []

        for row in candidate_rows:
            if not isinstance(row, Mapping):
                reason_codes.add("MALFORMED_CANDIDATE_ROW")
                continue

            contract_id = row.get("contract_id")
            epic_family_id = row.get("epic_family_id")
            variant_id = row.get("variant_id")
            score = row.get("score")
            promotion_bucket = row.get("promotion_bucket")
            promotion_rank = row.get("promotion_rank")

            if not isinstance(contract_id, str) or not contract_id.strip():
                reason_codes.add("INVALID_CANDIDATE_CONTRACT_ID")
                continue
            if contract_id in seen_contracts:
                reason_codes.add("DUPLICATE_CANDIDATE_CONTRACT_ID")
                continue
            if isinstance(epic_family_id, bool) or not isinstance(epic_family_id, int):
                reason_codes.add("INVALID_EPIC_FAMILY_ID")
                continue
            if not isinstance(variant_id, str) or not variant_id.strip():
                reason_codes.add("INVALID_VARIANT_ID")
                continue
            try:
                score_value = float(score)
            except (TypeError, ValueError):
                reason_codes.add("INVALID_SCORE")
                continue
            if not isfinite(score_value):
                reason_codes.add("INVALID_SCORE")
                continue
            if promotion_bucket not in self._BUCKET_ORDER:
                reason_codes.add("INVALID_PROMOTION_BUCKET")
                continue
            if isinstance(promotion_rank, bool) or not isinstance(promotion_rank, int) or promotion_rank < 1:
                reason_codes.add("INVALID_PROMOTION_RANK")
                continue

            seen_contracts.add(contract_id)
            candidates.append(
                CoreLeagueCandidate(
                    contract_id=contract_id,
                    epic_family_id=epic_family_id,
                    variant_id=variant_id,
                    score=score_value,
                    promotion_bucket=promotion_bucket,
                    promotion_rank=promotion_rank,
                )
            )

        if reason_codes:
            raise CandidateFeedValidationError(
                "selector input payload is malformed",
                reason_codes=tuple(sorted(reason_codes)),
            )

        ordered = tuple(
            sorted(
                candidates,
                key=lambda item: (
                    self._BUCKET_ORDER[item.promotion_bucket],
                    item.promotion_rank,
                    item.contract_id,
                    item.variant_id,
                ),
            )
        )

        return CoreLeagueCandidateFeed(
            schema_version=self.FEED_SCHEMA_VERSION,
            source_selector_schema=self.REQUIRED_SELECTOR_SCHEMA,
            candidates=ordered,
        )

    @staticmethod
    def _coerce_payload(
        selector_input: SelectorInputContract | Mapping[str, object],
    ) -> Mapping[str, object]:
        if isinstance(selector_input, SelectorInputContract):
            return selector_input.to_dict()
        if isinstance(selector_input, Mapping):
            return selector_input
        raise CandidateFeedValidationError(
            "selector_input must be a SelectorInputContract or mapping payload",
            reason_codes=("INVALID_SELECTOR_INPUT_TYPE",),
        )


__all__ = [
    "CandidateFeedValidationError",
    "CoreLeagueCandidate",
    "CoreLeagueCandidateFeed",
    "CoreLeagueCandidateFeedAdapter",
]
