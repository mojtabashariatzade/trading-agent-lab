"""Deterministic selector calibration harness over Core-league artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .core_league import CoreLeagueEvaluationArtifact


class SelectorCalibrationError(ValueError):
    """Machine-readable validation error for selector calibration."""

    def __init__(self, message: str, *, reason_codes: tuple[str, ...]):
        super().__init__(message)
        self.reason_codes = reason_codes


@dataclass(frozen=True)
class SelectorCalibrationRow:
    contract_id: str
    epic_family_id: int
    variant_id: str
    core_rank: int
    outcome: str
    eligible: bool
    calibrated_weight: float
    audit_flags: tuple[str, ...]


@dataclass(frozen=True)
class SelectorCalibrationArtifact:
    schema_version: str
    source_core_schema: str
    tie_break_fields: tuple[str, ...]
    pass_count: int
    wait_count: int
    eligible_count: int
    rows: tuple[SelectorCalibrationRow, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "source_core_schema": self.source_core_schema,
            "tie_break_fields": list(self.tie_break_fields),
            "pass_count": self.pass_count,
            "wait_count": self.wait_count,
            "eligible_count": self.eligible_count,
            "rows": [
                {
                    "contract_id": row.contract_id,
                    "epic_family_id": row.epic_family_id,
                    "variant_id": row.variant_id,
                    "core_rank": row.core_rank,
                    "outcome": row.outcome,
                    "eligible": row.eligible,
                    "calibrated_weight": row.calibrated_weight,
                    "audit_flags": list(row.audit_flags),
                }
                for row in self.rows
            ],
        }


class SelectorCalibrationHarness:
    """Validate Core-league artifacts and emit deterministic calibration output."""

    CALIBRATION_SCHEMA_VERSION = "selector-calibration.v1"
    REQUIRED_CORE_SCHEMA = "core-league-evaluation.v1"
    _TIE_BREAK_FIELDS = ("core_rank", "contract_id", "variant_id")

    def calibrate(
        self,
        *,
        core_league_artifact: CoreLeagueEvaluationArtifact | Mapping[str, object],
    ) -> SelectorCalibrationArtifact:
        payload = self._coerce_payload(core_league_artifact)
        reason_codes: set[str] = set()

        schema_version = payload.get("schema_version")
        if schema_version != self.REQUIRED_CORE_SCHEMA:
            reason_codes.add("UNSUPPORTED_CORE_LEAGUE_SCHEMA")

        rows = payload.get("rows")
        if not isinstance(rows, list):
            reason_codes.add("MISSING_CORE_ROWS")
            rows = []

        if reason_codes:
            raise SelectorCalibrationError(
                "core-league artifact is not eligible for selector calibration",
                reason_codes=tuple(sorted(reason_codes)),
            )

        seen_contracts: set[str] = set()
        seen_families: set[int] = set()
        seen_core_ranks: set[int] = set()
        parsed_rows: list[tuple[str, int, str, int, str]] = []

        for row in rows:
            if not isinstance(row, Mapping):
                reason_codes.add("MALFORMED_CORE_ROW")
                continue

            contract_id = row.get("contract_id")
            epic_family_id = row.get("epic_family_id")
            variant_id = row.get("variant_id")
            core_rank = row.get("core_rank")
            outcome = row.get("outcome")
            score = row.get("score")

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

            if isinstance(core_rank, bool) or not isinstance(core_rank, int) or core_rank < 1:
                reason_codes.add("INVALID_CORE_RANK")
                continue
            if core_rank in seen_core_ranks:
                reason_codes.add("DUPLICATE_CORE_RANK")
                continue

            if outcome not in {"PASS", "WAIT"}:
                reason_codes.add("INVALID_OUTCOME")
                continue

            try:
                score_value = float(score)
            except (TypeError, ValueError):
                reason_codes.add("INVALID_SCORE")
                continue
            if not isfinite(score_value):
                reason_codes.add("INVALID_SCORE")
                continue

            seen_contracts.add(contract_id)
            seen_families.add(epic_family_id)
            seen_core_ranks.add(core_rank)
            parsed_rows.append((contract_id, epic_family_id, variant_id, core_rank, outcome))

        if reason_codes:
            raise SelectorCalibrationError(
                "core-league artifact payload is malformed",
                reason_codes=tuple(sorted(reason_codes)),
            )

        parsed_rows.sort(key=lambda item: (item[3], item[0], item[2]))
        pass_count = sum(1 for item in parsed_rows if item[4] == "PASS")
        wait_count = sum(1 for item in parsed_rows if item[4] == "WAIT")

        payload_pass_count = payload.get("pass_count")
        payload_wait_count = payload.get("wait_count")
        if payload_pass_count != pass_count:
            reason_codes.add("PASS_COUNT_MISMATCH")
        if payload_wait_count != wait_count:
            reason_codes.add("WAIT_COUNT_MISMATCH")
        if reason_codes:
            raise SelectorCalibrationError(
                "core-league artifact counters are inconsistent with rows",
                reason_codes=tuple(sorted(reason_codes)),
            )

        denominator = sum((1.0 / rank) for _, _, _, rank, outcome in parsed_rows if outcome == "PASS")
        calibrated_rows: list[SelectorCalibrationRow] = []
        for contract_id, epic_family_id, variant_id, core_rank, outcome in parsed_rows:
            if outcome == "PASS" and denominator > 0.0:
                weight = (1.0 / core_rank) / denominator
                eligible = True
                audit_flags = ("ELIGIBLE_PASS",)
            else:
                weight = 0.0
                eligible = False
                audit_flags = ("INELIGIBLE_WAIT",)

            calibrated_rows.append(
                SelectorCalibrationRow(
                    contract_id=contract_id,
                    epic_family_id=epic_family_id,
                    variant_id=variant_id,
                    core_rank=core_rank,
                    outcome=outcome,
                    eligible=eligible,
                    calibrated_weight=weight,
                    audit_flags=audit_flags,
                )
            )

        return SelectorCalibrationArtifact(
            schema_version=self.CALIBRATION_SCHEMA_VERSION,
            source_core_schema=self.REQUIRED_CORE_SCHEMA,
            tie_break_fields=self._TIE_BREAK_FIELDS,
            pass_count=pass_count,
            wait_count=wait_count,
            eligible_count=pass_count,
            rows=tuple(calibrated_rows),
        )

    @staticmethod
    def _coerce_payload(
        core_league_artifact: CoreLeagueEvaluationArtifact | Mapping[str, object],
    ) -> Mapping[str, object]:
        if isinstance(core_league_artifact, CoreLeagueEvaluationArtifact):
            return core_league_artifact.to_dict()
        if isinstance(core_league_artifact, Mapping):
            return core_league_artifact
        raise SelectorCalibrationError(
            "core_league_artifact must be CoreLeagueEvaluationArtifact or mapping payload",
            reason_codes=("INVALID_CORE_LEAGUE_ARTIFACT_TYPE",),
        )


__all__ = [
    "SelectorCalibrationArtifact",
    "SelectorCalibrationError",
    "SelectorCalibrationHarness",
    "SelectorCalibrationRow",
]
