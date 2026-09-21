# Named software team

Names are software-role labels, not real people, separate accounts, or evidence
that a cloud provider is already connected. Display names do not change
authorization. Stable machine role IDs and task/idempotency keys are retained.

| Role ID | Name | Responsibility | Actual runtime mode |
|---|---|---|---|
| `core` | Arman | `agents/CORE.md` | Deterministic development orchestrator; not Trading Decision Core |
| `dev` | Kian | `agents/DEVELOPER.md` | `AGENT_RUNTIME=local`: scripted `LocalCursor` in an isolated git worktree (no chat). Cloud Cursor API only when `AGENT_RUNTIME=cloud` |
| `qa` | Negar | `agents/QA.md` | Same engines as Kian; local Negar reruns unittest on the exact PR SHA in a worktree |
| `quant` | Parsa | `agents/QUANT.md` | Independent research worker via research queue |
| `fundamental` | Niloofar | `agents/FUNDAMENTAL.md` | Independent research worker via research queue |
| `data` | Saman | `agents/DATA.md` | Independent research worker via research queue |
| `support` | Raha | `agents/SUPPORT.md` | Deterministic Telegram reporter for dev and research events |
| `bootstrap` | Sohrab | `agents/BOOTSTRAP.md` | Operator-started Cursor bootstrap role |

Name source of truth: `agentops/team.py`. `/team` shows Persian names, runtime
modes and live status. `/research` shows research queue rows. Coding launches
remain fail-closed for research roles; research launches use `launch_research`.
Arman stays separate from `trading_lab.contracts.decide`. Safety gates, spend
limits, phase gates and no-live-trading restrictions remain in force.
