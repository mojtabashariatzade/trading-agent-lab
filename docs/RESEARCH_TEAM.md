# Research team -- independent workers with queue and gates

## Implemented in this release
Parsa (quant), Niloofar (fundamental/news) and Saman (data) are independent
research workers scheduled through Arman's research queue. They are not the
Trading Decision Core and cannot place trades, merge PRs or raise Live limits.

Runtime pieces:
- Research task queue persisted in the controller store (`research_tasks`)
- Typed ResearchReport / Citation / Finding / Artifact contracts
- Source and citation requirements enforced by a structural review gate
- Arman can assign research before development (`requires_research` on backlog
  tasks, or `/research request KIND question`)
- Approved artifacts are attached to Kian developer prompts
- Negar QA prompts include research evidence checks when artifacts exist
- Raha reports research progress, blockers and approvals over Telegram outbox
- `/team` shows each named agent with live queue/controller status
- `/research` lists tasks, owners, states and blockers

## Workflow
Research request → assigned to Parsa / Niloofar / Saman → evidence + structured
report → structural review gate → approved research artifact → Arman schedules
implementation → Kian implements → CI → Negar QA (code + research evidence) →
owner approval → merge.

## Specialty contracts
- Parsa / STRATEGY: definitions, assumptions, parameter ranges, test hypotheses.
- Niloofar / FUNDAMENTAL: authoritative sources, calendars, BoE/BoJ/ONS and peers,
  publication timing, revisions, point-in-time availability.
- Saman / DATA: coverage, timestamp semantics, missing periods, reliability,
  revisions, look-ahead risks.

## Honesty rules
Researchers must not fabricate sources, URLs, coverage or results. Missing
internet/source access marks the task BLOCKED with the exact missing dependency.
Provider adapters and cloud launches remain mocked until authorized bootstrap.
No research path activates Live trading.
