# Trading Agent Team -- supervised autonomous development starter

## Project reading entry point

Start with the [project handbook and delivery plan](docs/PROJECT_HANDBOOK.md), the [Persian owner guide](docs/PROJECT_HANDBOOK.fa.md), and the [dated evidence/status snapshot](docs/PROJECT_STATUS.json). The handbook covers short- and long-term milestones, finance, responsibilities, research, risk, acceptance and documentation upkeep. It is a management baseline, not a runtime or spending authorization.

The original starter description below is retained as historical setup context. Read it together with the handbook's current evidence and open gaps; it does not prove that independent agents, deployment or real-data evaluation are active. Follow actual repository tests, permissions and deployment receipts rather than assuming that a documentation change activates them.

## Original starter description

**Built locally, not deployed. No remote agent is currently running. No live
trading, trained model, fetched price history, real tournament or profit claim.**

This is an executable control-plane starter for the owner's GBPJPY/M15 project,
not another long planning document. Open `CURSOR_START_TASK.md` in Cursor Agent
for the one-time account/hosting bootstrap. The owner need not run development
scripts each day; authenticated setup and spending approval remain human actions.

## What exists
- Durable SQLite-backed task state machine and explicit phase gate.
- Cursor Cloud API v1 adapter with idempotent agent creation and status polling.
- Developer task, real PR/CI checks, separate fresh QA run, SHA-bound owner merge.
- Telegram owner/chat allowlist, callbacks, status/team/pause/resume/stop/request.
- GitHub task issue creation, bounded repair attempts and verified merge evidence.
- Docker/Compose runtime with persistent state and no mounted candidate code.
- Research data-availability contracts and deterministic Trading Decision Core seed.
- Twelve roadmap tasks, of which only six phase-1 tasks can execute initially.
- Tests using isolated fake providers, plus pure policy/data-contract tests.

## Named roles -- do not misrepresent what is already wired
Arman is deterministic development orchestration, not an unrestricted LLM boss
and not the Trading Decision Core. Kian (Developer) and Negar (QA) are separate
coding cloud runs AFTER setup/authorization. Parsa, Niloofar and Saman are
independent research workers on the research queue with typed reports, citation
gates and approved artifacts before implementation. Raha reports development and
research events on Telegram. Sohrab is the operator-started Cursor bootstrap role.
Names are software labels, not people or new accounts. `/team` and `/research`
show live roster/queue status. See `docs/TEAM.md` and `docs/RESEARCH_TEAM.md`.

## Run locally without credentials (for the coding agent/operator)

    python -m unittest discover -s tests -v
    python -m agentops.demo

These commands never call remote APIs. The demo uses fake providers and clearly
labels its output as simulation. Deployment instructions are in
`docs/DEPLOYMENT.md`; all real credentials go into the hosting secret UI.

## Boundaries
One delivery at a time; maximum 4 cloud launches/day; at most 2 attempts/task;
phase 1 only; fresh state starts paused; paid run requires explicit authorization
and provider spending control. No automatic merge without owner approval.
All facts reported as DONE must have GitHub merge evidence. A terminal agent
run, successful test, or fabricated score cannot alone mean project completion.

See `LOCAL_VALIDATION.md` and `local-test-output.txt` for what was actually tested,
and `docs/SECURITY.md` for unimplemented features and operational limits.
