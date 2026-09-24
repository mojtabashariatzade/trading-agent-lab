"""Deterministic selector ablation/comparison harness over calibration artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .selector_calibration import SelectorCalibrationArtifact


class SelectorAblationError(ValueError):
    """Machine-readable validation error for selector ablation/comparison."""

    def __init__(self, message: str, *, reason_codes: tuple[str, ...]):
        super().__init__(message)
        self.reason_codes = reason_codes


@dataclass(frozen=True)
class SelectorAblationRow:
    mode_id: str
    rank: int
    outcome: str
    pass_count: int
    wait_count: int
    eligible_count: int
    total_weight: float
    score: float
    top_contract_id: str | None


@dataclass(frozen=True)
class SelectorAblationArtifact:
    schema_version: str
    source_calibration_schema: str
    tie_break_fields: tuple[str, ...]
    rows: tuple[SelectorAblationRow, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "source_calibration_schema": self.source_calibration_schema,
            "tie_break_fields": list(self.tie_break_fields),
            "rows": [
                {
                    "mode_id": row.mode_id,
                    "rank": row.rank,
                    "outcome": row.outcome,
                    "pass_count": row.pass_count,
                    "wait_count": row.wait_count,
                    "eligible_count": row.eligible_count,
                    "total_weight": row.total_weight,
                    "score": row.score,
                    "top_contract_id": row.top_contract_id,
                }
                for row in self.rows
            ],
        }


class SelectorAblationHarness:
    """Compare deterministic selector modes from one calibration artifact."""

    ABLATION_SCHEMA_VERSION = "selector-ablation.v1"
    REQUIRED_CALIBRATION_SCHEMA = "selector-calibration.v1"
    _TIE_BREAK_FIELDS = ("score_desc", "eligible_count_desc", "mode_id")

    def compare(
        self,
        *,
        calibration_artifact: SelectorCalibrationArtifact | Mapping[str, object],
    ) -> SelectorAblationArtifact:
        payload = self._coerce_payload(calibration_artifact)
        eligible_rows = self._parse_calibration_payload(payload)

        rows = [
            self._single_specialist_baseline(eligible_rows),
            self._calibrated_selector(eligible_rows),
            self._blended_fallback(eligible_rows),
        ]
        rows.sort(key=lambda row: (-row.score, -row.eligible_count, row.mode_id))

        ranked = tuple(
            SelectorAblationRow(
                mode_id=row.mode_id,
                rank=index,
                outcome=row.outcome,
                pass_count=row.pass_count,
                wait_count=row.wait_count,
                eligible_count=row.eligible_count,
                total_weight=row.total_weight,
                score=row.score,
                top_contract_id=row.top_contract_id,
            )
            for index, row in enumerate(rows, start=1)
        )

        return SelectorAblationArtifact(
            schema_version=self.ABLATION_SCHEMA_VERSION,
            source_calibration_schema=self.REQUIRED_CALIBRATION_SCHEMA,
            tie_break_fields=self._TIE_BREAK_FIELDS,
            rows=ranked,
        )

    def _parse_calibration_payload(
        self,
        payload: Mapping[str, object],
    ) -> tuple[tuple[str, int, bool, float], ...]:
        reason_codes: set[str] = set()

        schema_version = payload.get("schema_version")
        if schema_version != self.REQUIRED_CALIBRATION_SCHEMA:
            reason_codes.add("UNSUPPORTED_CALIBRATION_SCHEMA")

        rows = payload.get("rows")
        if not isinstance(rows, list):
            reason_codes.add("MISSING_CALIBRATION_ROWS")
            rows = []

        if reason_codes:
            raise SelectorAblationError(
                "calibration artifact is not eligible for ablation",
                reason_codes=tuple(sorted(reason_codes)),
            )

        seen_contracts: set[str] = set()
        eligible_rows: list[tuple[str, int, bool, float]] = []
        pass_count = 0
        wait_count = 0
        eligible_count = 0
        total_pass_weight = 0.0

        for row in rows:
            if not isinstance(row, Mapping):
                reason_codes.add("MALFORMED_CALIBRATION_ROW")
                continue

            contract_id = row.get("contract_id")
            core_rank = row.get("core_rank")
            outcome = row.get("outcome")
            eligible = row.get("eligible")
            calibrated_weight = row.get("calibrated_weight")

            if not isinstance(contract_id, str) or not contract_id.strip():
                reason_codes.add("INVALID_CONTRACT_ID")
                continue
            if contract_id in seen_contracts:
                reason_codes.add("DUPLICATE_CONTRACT_ID")
                continue

            if isinstance(core_rank, bool) or not isinstance(core_rank, int) or core_rank < 1:
                reason_codes.add("INVALID_CORE_RANK")
                continue
            if outcome not in {"PASS", "WAIT"}:
                reason_codes.add("INVALID_OUTCOME")
                continue
            if not isinstance(eligible, bool):
                reason_codes.add("INVALID_ELIGIBLE_FLAG")
                continue

            try:
                weight_value = float(calibrated_weight)
            except (TypeError, ValueError):
                reason_codes.add("INVALID_CALIBRATED_WEIGHT")
                continue
            if not isfinite(weight_value) or weight_value < 0.0:
                reason_codes.add("INVALID_CALIBRATED_WEIGHT")
                continue

            seen_contracts.add(contract_id)
            if outcome == "PASS":
                pass_count += 1
            else:
                wait_count += 1
            if eligible:
                eligible_count += 1
            if outcome == "PASS":
                total_pass_weight += weight_value
            eligible_rows.append((contract_id, core_rank, eligible, weight_value))

        payload_pass_count = payload.get("pass_count")
        payload_wait_count = payload.get("wait_count")
        payload_eligible_count = payload.get("eligible_count")

        if payload_pass_count != pass_count:
            reason_codes.add("PASS_COUNT_MISMATCH")
        if payload_wait_count != wait_count:
            reason_codes.add("WAIT_COUNT_MISMATCH")
        if payload_eligible_count != eligible_count:
            reason_codes.add("ELIGIBLE_COUNT_MISMATCH")
        if pass_count > 0 and abs(total_pass_weight - 1.0) > 1e-9:
            reason_codes.add("PASS_WEIGHT_SUM_MISMATCH")

        if reason_codes:
            raise SelectorAblationError(
                "calibration artifact payload is malformed",
                reason_codes=tuple(sorted(reason_codes)),
            )

        return tuple(sorted(eligible_rows, key=lambda item: (item[1], item[0])))

    @staticmethod
    def _single_specialist_baseline(
        rows: tuple[tuple[str, int, bool, float], ...],
    ) -> SelectorAblationRow:
        eligibles = [row for row in rows if row[2]]
        if not eligibles:
            return SelectorAblationRow(
                mode_id="fixed_single_specialist",
                rank=0,
                outcome="WAIT",
                pass_count=0,
                wait_count=1,
                eligible_count=0,
                total_weight=0.0,
                score=0.0,
                top_contract_id=None,
            )
        top = eligibles[0]
        return SelectorAblationRow(
            mode_id="fixed_single_specialist",
            rank=0,
            outcome="PASS",
            pass_count=1,
            wait_count=0,
            eligible_count=1,
            total_weight=1.0,
            score=1.0 / top[1],
            top_contract_id=top[0],
        )

    @staticmethod
    def _calibrated_selector(
        rows: tuple[tuple[str, int, bool, float], ...],
    ) -> SelectorAblationRow:
        eligibles = [row for row in rows if row[2]]
        if not eligibles:
            return SelectorAblationRow(
                mode_id="calibrated_selector",
                rank=0,
                outcome="WAIT",
                pass_count=0,
                wait_count=1,
                eligible_count=0,
                total_weight=0.0,
                score=0.0,
                top_contract_id=None,
            )
        score = sum((weight / rank) for _, rank, _, weight in eligibles)
        top = max(eligibles, key=lambda item: (item[3], -item[1], item[0]))
        return SelectorAblationRow(
            mode_id="calibrated_selector",
            rank=0,
            outcome="PASS",
            pass_count=len(eligibles),
            wait_count=0,
            eligible_count=len(eligibles),
            total_weight=sum(item[3] for item in eligibles),
            score=score,
            top_contract_id=top[0],
        )

    @staticmethod
    def _blended_fallback(
        rows: tuple[tuple[str, int, bool, float], ...],
    ) -> SelectorAblationRow:
        eligibles = [row for row in rows if row[2]]
        if not eligibles:
            return SelectorAblationRow(
                mode_id="blended_fallback",
                rank=0,
                outcome="WAIT",
                pass_count=0,
                wait_count=1,
                eligible_count=0,
                total_weight=0.0,
                score=0.0,
                top_contract_id=None,
            )
        selected = eligibles[:2]
        blend_weight = 1.0 / len(selected)
        score = sum((blend_weight / rank) for _, rank, _, _ in selected)
        return SelectorAblationRow(
            mode_id="blended_fallback",
            rank=0,
            outcome="PASS",
            pass_count=len(selected),
            wait_count=0,
            eligible_count=len(selected),
            total_weight=1.0,
            score=score,
            top_contract_id=selected[0][0],
        )

    @staticmethod
    def _coerce_payload(
        calibration_artifact: SelectorCalibrationArtifact | Mapping[str, object],
    ) -> Mapping[str, object]:
        if isinstance(calibration_artifact, SelectorCalibrationArtifact):
            return calibration_artifact.to_dict()
        if isinstance(calibration_artifact, Mapping):
            return calibration_artifact
        raise SelectorAblationError(
            "calibration_artifact must be SelectorCalibrationArtifact or mapping payload",
            reason_codes=("INVALID_CALIBRATION_ARTIFACT_TYPE",),
        )


__all__ = [
    "SelectorAblationArtifact",
    "SelectorAblationError",
    "SelectorAblationHarness",
    "SelectorAblationRow",
]
