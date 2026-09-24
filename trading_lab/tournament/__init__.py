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

__all__ = [
    "CandidateFeedValidationError",
    "CoreLeagueCandidate",
    "CoreLeagueCandidateFeed",
    "CoreLeagueCandidateFeedAdapter",
    "DatasetClass",
    "FamilyEligibilityMatrixRow",
    "FamilyChampion",
    "IneligibleFamily",
    "IntraFamilyLeagueHarness",
    "IntraFamilyLeagueResult",
    "InterFamilyChampionshipHarness",
    "InterFamilyChampionshipResult",
    "Opportunity",
    "PrerequisiteGateResult",
    "PromotionContract",
    "REQUIRED_INTEGRITY_GATES",
    "RankedVariant",
    "RejectedFamilyReason",
    "RuleBasedDecisionCore",
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
