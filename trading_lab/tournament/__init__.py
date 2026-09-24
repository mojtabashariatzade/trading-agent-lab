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
from .family_league import (
    FamilyEligibilityMatrixRow,
    IntraFamilyLeagueHarness,
    IntraFamilyLeagueResult,
    PrerequisiteGateResult,
    RankedVariant,
    VariantEligibility,
)

__all__ = [
    "DatasetClass",
    "FamilyEligibilityMatrixRow",
    "IntraFamilyLeagueHarness",
    "IntraFamilyLeagueResult",
    "Opportunity",
    "PrerequisiteGateResult",
    "REQUIRED_INTEGRITY_GATES",
    "RankedVariant",
    "RuleBasedDecisionCore",
    "TournamentConfig",
    "TournamentDecision",
    "TournamentRun",
    "TournamentRunner",
    "VariantEligibility",
    "default_experts",
]
