"""Deterministic Phase B tournament exit evidence bundle (Issue #89)."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping, Sequence

from trading_lab.strategies import StrategyFamilyDefinition, default_strategy_family_registry

from .core_league import CoreLeagueEvaluationArtifact
from .family_league import IntraFamilyLeagueResult
from .inter_family import InterFamilyChampionshipResult
from .candidate_feed import CoreLeagueCandidateFeed
from .selector_ablation import SelectorAblationArtifact
from .selector_calibration import SelectorCalibrationArtifact
from .selector_input import SelectorInputContract


class PhaseBEvidenceError(ValueError):
    """Machine-readable validation error for Phase B evidence assembly."""

    def __init__(self, message: str, *, reason_codes: tuple[str, ...]):
        super().__init__(message)
        self.reason_codes = reason_codes


@dataclass(frozen=True)
class StageEvidenceRef:
    issue_ref: str
    stage_name: str
    schema_or_contract: str
    record_count: int
    digest: str


@dataclass(frozen=True)
class PhaseBEvidenceBundle:
    schema_version: str
    parent_epic: str
    stage_refs: tuple[StageEvidenceRef, ...]
    acceptance_metrics: Mapping[str, object]
    known_limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "parent_epic": self.parent_epic,
            "stage_refs": [
                {
                    "issue_ref": row.issue_ref,
                    "stage_name": row.stage_name,
                    "schema_or_contract": row.schema_or_contract,
                    "record_count": row.record_count,
                    "digest": row.digest,
                }
                for row in self.stage_refs
            ],
            "acceptance_metrics": dict(self.acceptance_metrics),
            "known_limitations": list(self.known_limitations),
        }


class PhaseBEvidenceBundleHarness:
    """Aggregate #76/#78/#80/#82/#83/#84/#86/#87 artifacts into one report."""

    BUNDLE_SCHEMA_VERSION = "phase-b-evidence-bundle.v1"
    PARENT_EPIC = "#38"

    def build(
        self,
        *,
        strategy_registry: Sequence[StrategyFamilyDefinition] | None,
        intra_family_result: IntraFamilyLeagueResult,
        championship_result: InterFamilyChampionshipResult,
        selector_input: SelectorInputContract | Mapping[str, object],
        candidate_feed: CoreLeagueCandidateFeed | Mapping[str, object],
        core_league_artifact: CoreLeagueEvaluationArtifact | Mapping[str, object],
        selector_calibration_artifact: SelectorCalibrationArtifact | Mapping[str, object],
        selector_ablation_artifact: SelectorAblationArtifact | Mapping[str, object],
    ) -> PhaseBEvidenceBundle:
        registry = tuple(strategy_registry or default_strategy_family_registry())
        if len(registry) != 15:
            raise PhaseBEvidenceError(
                "strategy registry contract does not match canonical Issue #76 requirements",
                reason_codes=("INVALID_REGISTRY_CARDINALITY",),
            )

        selector_payload = self._coerce_payload(selector_input)
        candidate_payload = self._coerce_payload(candidate_feed)
        core_payload = self._coerce_payload(core_league_artifact)
        calibration_payload = self._coerce_payload(selector_calibration_artifact)
        ablation_payload = self._coerce_payload(selector_ablation_artifact)

        reason_codes: set[str] = set()

        if selector_payload.get("schema_version") != "selector-input.v1":
            reason_codes.add("UNSUPPORTED_SELECTOR_INPUT_SCHEMA")
        if candidate_payload.get("schema_version") != "core-league-candidate-feed.v1":
            reason_codes.add("UNSUPPORTED_CANDIDATE_FEED_SCHEMA")
        if core_payload.get("schema_version") != "core-league-evaluation.v1":
            reason_codes.add("UNSUPPORTED_CORE_LEAGUE_SCHEMA")
        if calibration_payload.get("schema_version") != "selector-calibration.v1":
            reason_codes.add("UNSUPPORTED_CALIBRATION_SCHEMA")
        if ablation_payload.get("schema_version") != "selector-ablation.v1":
            reason_codes.add("UNSUPPORTED_ABLATION_SCHEMA")

        core_rows = core_payload.get("rows")
        calibration_rows = calibration_payload.get("rows")
        ablation_rows = ablation_payload.get("rows")
        if not isinstance(core_rows, list):
            reason_codes.add("MISSING_CORE_ROWS")
            core_rows = []
        if not isinstance(calibration_rows, list):
            reason_codes.add("MISSING_CALIBRATION_ROWS")
            calibration_rows = []
        if not isinstance(ablation_rows, list):
            reason_codes.add("MISSING_ABLATION_ROWS")
            ablation_rows = []

        if reason_codes:
            raise PhaseBEvidenceError(
                "phase-b evidence bundle inputs are malformed",
                reason_codes=tuple(sorted(reason_codes)),
            )

        metrics = self._build_acceptance_metrics(
            core_rows=core_rows,
            core_payload=core_payload,
            calibration_rows=calibration_rows,
            calibration_payload=calibration_payload,
            ablation_rows=ablation_rows,
        )

        stage_refs = (
            StageEvidenceRef(
                issue_ref="#76",
                stage_name="canonical_family_registry",
                schema_or_contract="strategy-family-registry.v1",
                record_count=len(registry),
                digest=self._digest(
                    [
                        {
                            "contract_id": item.contract_id,
                            "epic_family_id": item.epic_family_id,
                            "variant_count_bounds": list(item.variant_count_bounds),
                            "horizon_bars": list(item.horizon_bars),
                            "data_prerequisites": list(item.data_prerequisites),
                        }
                        for item in registry
                    ]
                ),
            ),
            StageEvidenceRef(
                issue_ref="#78",
                stage_name="intra_family_league",
                schema_or_contract="intra-family-league.v1",
                record_count=sum(len(row.variants) for row in intra_family_result.matrix),
                digest=self._digest(
                    {
                        "matrix_rows": [
                            {
                                "contract_id": row.contract_id,
                                "eligible_variants": sum(1 for variant in row.variants if variant.eligible),
                            }
                            for row in intra_family_result.matrix
                        ],
                        "ranked_counts": {
                            contract_id: len(ranked)
                            for contract_id, ranked in intra_family_result.ranked_by_family
                        },
                    }
                ),
            ),
            StageEvidenceRef(
                issue_ref="#80",
                stage_name="inter_family_championship",
                schema_or_contract="inter-family-championship.v1",
                record_count=len(championship_result.championship_ranking),
                digest=self._digest(
                    {
                        "ranking": [
                            {
                                "contract_id": row.contract_id,
                                "epic_family_id": row.epic_family_id,
                                "variant_id": row.variant_id,
                                "score": row.score,
                            }
                            for row in championship_result.championship_ranking
                        ],
                        "ineligible": [
                            {
                                "contract_id": row.contract_id,
                                "reasons": list(row.reasons),
                            }
                            for row in championship_result.promotion.ineligible_families
                        ],
                    }
                ),
            ),
            StageEvidenceRef(
                issue_ref="#82",
                stage_name="selector_input_contract",
                schema_or_contract="selector-input.v1",
                record_count=len(selector_payload.get("candidates", [])),
                digest=self._digest(selector_payload),
            ),
            StageEvidenceRef(
                issue_ref="#83",
                stage_name="core_league_candidate_feed",
                schema_or_contract="core-league-candidate-feed.v1",
                record_count=len(candidate_payload.get("candidates", [])),
                digest=self._digest(candidate_payload),
            ),
            StageEvidenceRef(
                issue_ref="#84",
                stage_name="core_league_evaluation",
                schema_or_contract="core-league-evaluation.v1",
                record_count=len(core_rows),
                digest=self._digest(core_payload),
            ),
            StageEvidenceRef(
                issue_ref="#86",
                stage_name="selector_calibration",
                schema_or_contract="selector-calibration.v1",
                record_count=len(calibration_rows),
                digest=self._digest(calibration_payload),
            ),
            StageEvidenceRef(
                issue_ref="#87",
                stage_name="selector_ablation",
                schema_or_contract="selector-ablation.v1",
                record_count=len(ablation_rows),
                digest=self._digest(ablation_payload),
            ),
        )

        limitations = (
            "Artifacts are deterministic software-evidence outputs; no profitability claim is implied.",
            "Inputs can originate from synthetic fixtures in unit tests and are not live-trading evidence.",
            "Bundle validates schema/invariants only and does not replace independent QA review.",
        )

        return PhaseBEvidenceBundle(
            schema_version=self.BUNDLE_SCHEMA_VERSION,
            parent_epic=self.PARENT_EPIC,
            stage_refs=stage_refs,
            acceptance_metrics=metrics,
            known_limitations=limitations,
        )

    @staticmethod
    def _coerce_payload(value: object) -> Mapping[str, object]:
        if hasattr(value, "to_dict"):
            payload = value.to_dict()  # type: ignore[assignment]
            if isinstance(payload, Mapping):
                return payload
        if isinstance(value, Mapping):
            return value
        raise PhaseBEvidenceError(
            "artifact payload must be mapping-compatible",
            reason_codes=("INVALID_ARTIFACT_INPUT_TYPE",),
        )

    def _build_acceptance_metrics(
        self,
        *,
        core_rows: list[object],
        core_payload: Mapping[str, object],
        calibration_rows: list[object],
        calibration_payload: Mapping[str, object],
        ablation_rows: list[object],
    ) -> dict[str, object]:
        core_pass = sum(1 for row in core_rows if isinstance(row, Mapping) and row.get("outcome") == "PASS")
        core_wait = sum(1 for row in core_rows if isinstance(row, Mapping) and row.get("outcome") == "WAIT")

        cal_pass = sum(1 for row in calibration_rows if isinstance(row, Mapping) and row.get("outcome") == "PASS")
        cal_wait = sum(1 for row in calibration_rows if isinstance(row, Mapping) and row.get("outcome") == "WAIT")
        cal_eligible = sum(1 for row in calibration_rows if isinstance(row, Mapping) and row.get("eligible") is True)

        ablation_pass = sum(1 for row in ablation_rows if isinstance(row, Mapping) and row.get("outcome") == "PASS")
        ablation_wait = sum(1 for row in ablation_rows if isinstance(row, Mapping) and row.get("outcome") == "WAIT")

        counters_match = (
            core_payload.get("pass_count") == core_pass
            and core_payload.get("wait_count") == core_wait
            and calibration_payload.get("pass_count") == cal_pass
            and calibration_payload.get("wait_count") == cal_wait
            and calibration_payload.get("eligible_count") == cal_eligible
        )

        metric_payload = {
            "pass_wait_accounting": {
                "core_league": {"PASS": core_pass, "WAIT": core_wait},
                "selector_calibration": {
                    "PASS": cal_pass,
                    "WAIT": cal_wait,
                    "ELIGIBLE": cal_eligible,
                },
                "selector_ablation_modes": {"PASS": ablation_pass, "WAIT": ablation_wait},
            },
            "invariant_checks": {
                "counter_alignment": counters_match,
                "row_shape": {
                    "core_rows": len(core_rows),
                    "calibration_rows": len(calibration_rows),
                    "ablation_rows": len(ablation_rows),
                },
            },
        }
        metric_payload["reproducibility_fingerprint"] = self._digest(metric_payload)
        return metric_payload

    @staticmethod
    def _digest(value: object) -> str:
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "PhaseBEvidenceBundle",
    "PhaseBEvidenceBundleHarness",
    "PhaseBEvidenceError",
    "StageEvidenceRef",
]
