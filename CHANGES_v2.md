# Changes -- research-team upgrade

Requested change: upgrade Parsa, Niloofar and Saman from advisory prompts into
independent research workers with queue, contracts, citation gates and artifact
handoff before Kian development, while keeping Arman separate from the Trading
Decision Core and preserving all safety / no-live-trading gates.

## Added
- `agentops/research_contracts.py`, `agentops/research.py`
- Store table `research_tasks`
- Controller: `request_research`, `launch_research`, `submit_research_report`,
  `approve_research`, `/research`, live `/team` status, research-before-dev gate
- `tests/test_research.py` and CI inclusion of that module

## Updated
- Role docs, `docs/RESEARCH_TEAM.md`, `docs/TEAM.md`, `AGENTS.md`, README, TEAM.fa.md
- Named-team tests for first-class research workers and artifact consumption

Cloud bootstrap and live providers remain out of scope for this receipt.
