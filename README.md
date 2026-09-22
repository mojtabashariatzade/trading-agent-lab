# Trading Agent Lab -- autonomous trading system in development

## Product objective

Build a system that observes markets, decides LONG or SHORT when justified, sizes and executes permitted positions, manages exits and reconciles net trading P&L for the owner's account. PASS, WAIT and DATA_INSUFFICIENT remain valid outcomes. Research, backtesting, unseen evaluation and paper operation are development stages toward that trader, not separate products to sell. Subscription sales, customer analytics and software licensing are outside this project's scope.

The final objective includes automatic market execution after validation and separate live activation. The current repository does not establish a working live broker loop or profitable model. GBPJPY/M15 is the first benchmark, not a permanent product boundary. Keep the software-development coordinator separate from the Trading Decision Core.

## Project reading entry point

Start with the [project handbook](docs/PROJECT_HANDBOOK.md), [Persian owner guide](docs/PROJECT_HANDBOOK.fa.md), [trading-profit plan](docs/REVENUE_PLAN.md), [daily work plan](docs/DAILY_DELIVERY_PLAN.md) and [dated evidence/status snapshot](docs/PROJECT_STATUS.json). The [course and Market Grammar architecture](docs/architecture/MARKET_GRAMMAR_DESIGN.md) is a research design, not implemented behavior. It preserves the fifteen-family league and macro/news layer while separating course claims, teacher reconstruction and actual trading validity.

The original starter description below is retained as historical setup context. Read it together with the current handbook's evidence and gaps; it does not prove that independent agents, deployment or real-data evaluation are active. Follow actual repository tests, permissions and deployment receipts. A documentation change activates none of them.

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
