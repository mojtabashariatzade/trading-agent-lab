"""Deterministic Core-league evaluation harness for selector candidate feeds."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .candidate_feed import CoreLeagueCandidateFeed


class CoreLeagueEvaluationError(ValueError):
    """Machine-readable validation error for Core-league evaluation."""

    def __init__(self, message: str, *, reason_codes: tuple[str, ...]):
        super().__init__(message)
        self.reason_codes = reason_codes


@dataclass(frozen=True)
class CoreLeagueEvaluationRow:
    contract_id: str
    epic_family_id: int
    variant_id: str
    score: float
    promotion_bucket: str
    promotion_rank: int
    core_rank: int
    outcome: str


@dataclass(frozen=True)
class CoreLeagueEvaluationArtifact:
    schema_version: str
    source_candidate_schema: str
    tie_break_fields: tuple[str, ...]
    pass_count: int
    wait_count: int
    rows: tuple[CoreLeagueEvaluationRow, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "source_candidate_schema": self.source_candidate_schema,
            "tie_break_fields": list(self.tie_break_fields),
            "pass_count": self.pass_count,
            "wait_count": self.wait_count,
            "rows": [
                {
                    "contract_id": row.contract_id,
                    "epic_family_id": row.epic_family_id,
                    "variant_id": row.variant_id,
                    "score": row.score,
                    "promotion_bucket": row.promotion_bucket,
                    "promotion_rank": row.promotion_rank,
                    "core_rank": row.core_rank,
                    "outcome": row.outcome,
                }
                for row in self.rows
            ],
        }


class CoreLeagueEvaluationHarness:
    """Validate candidate-feed payloads and emit deterministic Core-league artifacts."""

    EVALUATION_SCHEMA_VERSION = "core-league-evaluation.v1"
    REQUIRED_CANDIDATE_SCHEMA = "core-league-candidate-feed.v1"
    _BUCKET_ORDER = {"champion": 0, "runner_up": 1}
    _TIE_BREAK_FIELDS = (
        "promotion_bucket_priority",
        "promotion_rank",
        "score_desc",
        "contract_id",
        "variant_id",
    )

    def evaluate(
        self,
        *,
        candidate_feed: CoreLeagueCandidateFeed | Mapping[str, object],
    ) -> CoreLeagueEvaluationArtifact:
        payload = self._coerce_payload(candidate_feed)
        reason_codes: set[str] = set()

        schema_version = payload.get("schema_version")
        if schema_version != self.REQUIRED_CANDIDATE_SCHEMA:
            reason_codes.add("UNSUPPORTED_CANDIDATE_FEED_SCHEMA")

        candidate_rows = payload.get("candidates")
        if not isinstance(candidate_rows, list):
            reason_codes.add("MISSING_CANDIDATES")
            candidate_rows = []

        if reason_codes:
            raise CoreLeagueEvaluationError(
                "candidate feed is not eligible for Core-league evaluation",
                reason_codes=tuple(sorted(reason_codes)),
            )

        seen_contracts: set[str] = set()
        seen_families: set[int] = set()
        parsed_rows: list[CoreLeagueEvaluationRow] = []

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
                reason_codes.add("INVALID_CONTRACT_ID")
                continue
            if contract_id in seen_contracts:
                reason_codes.add("DUPLICATE_CONTRACT_ID")
                continue

            if isinstance(epic_family_id, bool) or not isinstance(epic_family_id, int):
                reason_codes.add("INVALID_EPIC_FAMILY_ID")
                continue
            if epic_family_id in seen_families:
                reason_codes.add("DUPLICATE_EPIC_FAMILY_ID")
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
            seen_families.add(epic_family_id)
            parsed_rows.append(
                CoreLeagueEvaluationRow(
                    contract_id=contract_id,
                    epic_family_id=epic_family_id,
                    variant_id=variant_id,
                    score=score_value,
                    promotion_bucket=promotion_bucket,
                    promotion_rank=promotion_rank,
                    core_rank=0,
                    outcome="UNSET",
                )
            )

        if reason_codes:
            raise CoreLeagueEvaluationError(
                "candidate feed payload is malformed",
                reason_codes=tuple(sorted(reason_codes)),
            )

        ordered = sorted(
            parsed_rows,
            key=lambda item: (
                self._BUCKET_ORDER[item.promotion_bucket],
                item.promotion_rank,
                -item.score,
                item.contract_id,
                item.variant_id,
            ),
        )

        ranked_rows: list[CoreLeagueEvaluationRow] = []
        pass_count = 0
        wait_count = 0
        for index, item in enumerate(ordered, start=1):
            outcome = "PASS" if item.promotion_bucket == "champion" else "WAIT"
            if outcome == "PASS":
                pass_count += 1
            else:
                wait_count += 1
            ranked_rows.append(
                CoreLeagueEvaluationRow(
                    contract_id=item.contract_id,
                    epic_family_id=item.epic_family_id,
                    variant_id=item.variant_id,
                    score=item.score,
                    promotion_bucket=item.promotion_bucket,
                    promotion_rank=item.promotion_rank,
                    core_rank=index,
                    outcome=outcome,
                )
            )

        return CoreLeagueEvaluationArtifact(
            schema_version=self.EVALUATION_SCHEMA_VERSION,
            source_candidate_schema=self.REQUIRED_CANDIDATE_SCHEMA,
            tie_break_fields=self._TIE_BREAK_FIELDS,
            pass_count=pass_count,
            wait_count=wait_count,
            rows=tuple(ranked_rows),
        )

    @staticmethod
    def _coerce_payload(
        candidate_feed: CoreLeagueCandidateFeed | Mapping[str, object],
    ) -> Mapping[str, object]:
        if isinstance(candidate_feed, CoreLeagueCandidateFeed):
            return candidate_feed.to_dict()
        if isinstance(candidate_feed, Mapping):
            return candidate_feed
        raise CoreLeagueEvaluationError(
            "candidate_feed must be a CoreLeagueCandidateFeed or mapping payload",
            reason_codes=("INVALID_CANDIDATE_FEED_TYPE",),
        )


__all__ = [
    "CoreLeagueEvaluationArtifact",
    "CoreLeagueEvaluationError",
    "CoreLeagueEvaluationHarness",
    "CoreLeagueEvaluationRow",
]
