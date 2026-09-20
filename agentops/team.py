"""Stable software-role names. Names confer no permissions or real-person identity."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class AgentProfile:
    role_id: str
    name_en: str
    name_fa: str
    title_fa: str
    runtime_mode: str
    instructions: str


TEAM: Mapping[str, AgentProfile] = MappingProxyType({
    'core': AgentProfile('core', 'Arman', '\u0622\u0631\u0645\u0627\u0646', '\u0645\u062f\u06cc\u0631 \u062a\u0648\u0633\u0639\u0647', 'deterministic_controller', 'agents/CORE.md'),
    'dev': AgentProfile('dev', 'Kian', '\u06a9\u06cc\u0627\u0646', '\u0628\u0631\u0646\u0627\u0645\u0647\u200c\u0646\u0648\u06cc\u0633', 'cloud_worker_after_setup', 'agents/DEVELOPER.md'),
    'qa': AgentProfile('qa', 'Negar', '\u0646\u06af\u0627\u0631', '\u0628\u0627\u0632\u0628\u06cc\u0646 \u0648 \u0645\u0633\u0626\u0648\u0644 \u062a\u0633\u062a', 'cloud_worker_after_setup', 'agents/QA.md'),
    'quant': AgentProfile('quant', 'Parsa', '\u067e\u0627\u0631\u0633\u0627', '\u067e\u0698\u0648\u0647\u0634\u06af\u0631 \u0627\u0633\u062a\u0631\u0627\u062a\u0698\u06cc \u0648 \u0645\u062f\u0644', 'research_worker_after_setup', 'agents/QUANT.md'),
    'fundamental': AgentProfile('fundamental', 'Niloofar', '\u0646\u06cc\u0644\u0648\u0641\u0631', '\u067e\u0698\u0648\u0647\u0634\u06af\u0631 \u0641\u0627\u0646\u062f\u0627\u0645\u0646\u062a\u0627\u0644 \u0648 \u062e\u0628\u0631', 'research_worker_after_setup', 'agents/FUNDAMENTAL.md'),
    'data': AgentProfile('data', 'Saman', '\u0633\u0627\u0645\u0627\u0646', '\u0645\u0633\u0626\u0648\u0644 \u062f\u0627\u062f\u0647 \u0648 \u0627\u0639\u062a\u0628\u0627\u0631 \u0645\u0646\u0627\u0628\u0639', 'research_worker_after_setup', 'agents/DATA.md'),
    'support': AgentProfile('support', 'Raha', '\u0631\u0647\u0627', '\u067e\u0634\u062a\u06cc\u0628\u0627\u0646 \u0648 \u06af\u0632\u0627\u0631\u0634\u200c\u062f\u0647\u0646\u062f\u0647', 'deterministic_reporter', 'agents/SUPPORT.md'),
    'bootstrap': AgentProfile('bootstrap', 'Sohrab', '\u0633\u0647\u0631\u0627\u0628', '\u0645\u0633\u0626\u0648\u0644 \u0631\u0627\u0647\u200c\u0627\u0646\u062f\u0627\u0632\u06cc', 'operator_bootstrap', 'agents/BOOTSTRAP.md'),
})
MODE_LABELS = MappingProxyType({
    'deterministic_controller': '\u06a9\u0646\u062a\u0631\u0644\u0631 \u0642\u0627\u0639\u062f\u0647\u200c\u0645\u062d\u0648\u0631\u061b \u0627\u062c\u0631\u0627 \u067e\u0633 \u0627\u0632 \u0631\u0627\u0647\u200c\u0627\u0646\u062f\u0627\u0632\u06cc',
    'cloud_worker_after_setup': '\u0627\u062c\u0631\u0627\u06cc \u0627\u0628\u0631\u06cc \u0645\u0633\u062a\u0642\u0644\u061b \u067e\u0633 \u0627\u0632 \u0627\u062a\u0635\u0627\u0644 \u0648 \u0645\u062c\u0648\u0632',
    'research_worker_after_setup': '\u06a9\u0627\u0631\u06af\u0631 \u0645\u0633\u062a\u0642\u0644 \u067e\u0698\u0648\u0647\u0634\u061b \u0635\u0641 \u0648 \u062f\u0631\u0648\u0627\u0632\u0647 \u062c\u062f\u0627\u061b \u067e\u0633 \u0627\u0632 \u0627\u062a\u0635\u0627\u0644',
    'deterministic_reporter': '\u06af\u0632\u0627\u0631\u0634\u200c\u06af\u0631 \u0642\u0627\u0639\u062f\u0647\u200c\u0645\u062d\u0648\u0631\u061b \u0628\u062f\u0648\u0646 \u0645\u062f\u0644 \u0632\u0628\u0627\u0646\u06cc \u062c\u062f\u0627',
    'operator_bootstrap': '\u0646\u0642\u0634 \u0631\u0627\u0647\u200c\u0627\u0646\u062f\u0627\u0632\u06cc \u062f\u0631 Cursor\u061b \u0627\u062c\u0631\u0627\u06cc \u062f\u0633\u062a\u06cc \u0627\u0648\u0644\u06cc\u0647',
})
# Coding workers only. Research workers use research_worker_profile / launch_research.
CLOUD_WORKER_ROLES = frozenset({"dev", "qa"})
RESEARCH_WORKER_ROLES = frozenset({"quant", "fundamental", "data"})
RESEARCH_ROLES = ("quant", "fundamental", "data")
RLM = "\u200f"


def worker_profile(role: str) -> AgentProfile:
    """Fail closed: research roles cannot silently become coding worker runs."""
    if role not in CLOUD_WORKER_ROLES:
        raise ValueError("This role has no independent coding worker runtime: " + str(role))
    return TEAM[role]


def research_worker_profile(role: str) -> AgentProfile:
    """Fail closed: only Parsa/Niloofar/Saman may run research workers."""
    if role not in RESEARCH_WORKER_ROLES:
        raise ValueError("This role has no independent research worker runtime: " + str(role))
    return TEAM[role]


def worker_identity(role: str) -> str:
    profile = worker_profile(role)
    return (
        f"Your software-role name is {profile.name_en} ({profile.name_fa}); "
        f"stable role ID: {profile.role_id}. This is an AI role label, not a human identity.\n"
        "The role name changes no privileges, approvals, or execution limits.\n"
    )


def research_instructions() -> str:
    references = "; ".join(
        f"{TEAM[role].name_en}: {TEAM[role].instructions}" for role in RESEARCH_ROLES
    )
    return (
        "Independent research workers exist for: " + references + ".\n"
        "Consume ONLY approved research artifacts attached by Arman. Do not invent "
        "reports, claim a researcher reviewed your work without an artifact id, or "
        "treat advisory text as Live/trading authority.\n"
    )


def team_report(statuses: Mapping[str, str] | None = None) -> str:
    """Roster with optional live per-role status from the controller store."""
    lines = [
        RLM + '\u0641\u0647\u0631\u0633\u062a \u0646\u0642\u0634\u200c\u0647\u0627\u06cc \u062a\u06cc\u0645',
        RLM + '\u0646\u0627\u0645\u200c\u0647\u0627 \u0628\u0631\u0686\u0633\u0628 \u0646\u0642\u0634 \u0646\u0631\u0645\u200c\u0627\u0641\u0632\u0627\u0631\u06cc\u200c\u0627\u0646\u062f\u061b '
              '\u0648\u0636\u0639\u06cc\u062a \u0646\u0634\u0627\u0646\u200c\u062f\u0647\u0646\u062f\u0647 \u0648\u0636\u0639\u06cc\u062a \u0648\u0627\u0642\u0639\u06cc \u0635\u0641/\u0627\u062c\u0631\u0627 \u0627\u0633\u062a.',
    ]
    for profile in TEAM.values():
        live = (statuses or {}).get(profile.role_id, "UNKNOWN")
        lines.append(
            f"{RLM}{profile.name_fa} | {profile.title_fa} | "
            f"{MODE_LABELS[profile.runtime_mode]} | {live}"
        )
    return "\n".join(lines)
