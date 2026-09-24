"""Auditable synthetic research tournament."""
from .core import (
    DatasetClass,
    Opportunity,
    REQUIRED_INTEGRITY_GATES,
    RuleBasedDecisionCore,
    TournamentConfig,
    TournamentDecision,
    TournamentRun,
    TournamentRunner,
    default_experts,
)
from .candidate_feed import (
    CandidateFeedValidationError,
    CoreLeagueCandidate,
    CoreLeagueCandidateFeed,
    CoreLeagueCandidateFeedAdapter,
)
from .core_league import (
    CoreLeagueEvaluationArtifact,
    CoreLeagueEvaluationError,
    CoreLeagueEvaluationHarness,
    CoreLeagueEvaluationRow,
)
from .family_league import (
    FamilyEligibilityMatrixRow,
    IntraFamilyLeagueHarness,
    IntraFamilyLeagueResult,
    PrerequisiteGateResult,
    RankedVariant,
    VariantEligibility,
)
from .inter_family import (
    FamilyChampion,
    IneligibleFamily,
    InterFamilyChampionshipHarness,
    InterFamilyChampionshipResult,
    PromotionContract,
)
from .selector_input import (
    RejectedFamilyReason,
    SelectorCandidate,
    SelectorInputContract,
    SelectorInputContractHarness,
)
from .selector_calibration import (
    SelectorCalibrationArtifact,
    SelectorCalibrationError,
    SelectorCalibrationHarness,
    SelectorCalibrationRow,
)
from .selector_ablation import (
    SelectorAblationArtifact,
    SelectorAblationError,
    SelectorAblationHarness,
    SelectorAblationRow,
)
from .phase_b_evidence import (
    PhaseBEvidenceBundle,
    PhaseBEvidenceBundleHarness,
    PhaseBEvidenceError,
    StageEvidenceRef,
)

__all__ = [
    "CandidateFeedValidationError",
    "CoreLeagueCandidate",
    "CoreLeagueCandidateFeed",
    "CoreLeagueCandidateFeedAdapter",
    "CoreLeagueEvaluationArtifact",
    "CoreLeagueEvaluationError",
    "CoreLeagueEvaluationHarness",
    "CoreLeagueEvaluationRow",
    "DatasetClass",
    "FamilyEligibilityMatrixRow",
    "FamilyChampion",
    "IneligibleFamily",
    "IntraFamilyLeagueHarness",
    "IntraFamilyLeagueResult",
    "InterFamilyChampionshipHarness",
    "InterFamilyChampionshipResult",
    "Opportunity",
    "PhaseBEvidenceBundle",
    "PhaseBEvidenceBundleHarness",
    "PhaseBEvidenceError",
    "PrerequisiteGateResult",
    "PromotionContract",
    "REQUIRED_INTEGRITY_GATES",
    "RankedVariant",
    "RejectedFamilyReason",
    "RuleBasedDecisionCore",
    "StageEvidenceRef",
    "SelectorAblationArtifact",
    "SelectorAblationError",
    "SelectorAblationHarness",
    "SelectorAblationRow",
    "SelectorCalibrationArtifact",
    "SelectorCalibrationError",
    "SelectorCalibrationHarness",
    "SelectorCalibrationRow",
    "SelectorCandidate",
    "SelectorInputContract",
    "SelectorInputContractHarness",
    "TournamentConfig",
    "TournamentDecision",
    "TournamentRun",
    "TournamentRunner",
    "VariantEligibility",
    "default_experts",
]
