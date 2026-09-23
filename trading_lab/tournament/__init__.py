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

__all__ = [
    "DatasetClass",
    "Opportunity",
    "REQUIRED_INTEGRITY_GATES",
    "RuleBasedDecisionCore",
    "TournamentConfig",
    "TournamentDecision",
    "TournamentRun",
    "TournamentRunner",
    "default_experts",
]
