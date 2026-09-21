# ChatGPT/GitHub brain mode

Purpose: remove Cursor Cloud and weak local LLMs from the critical coding path.

## Control model

- ChatGPT is the external reasoning/review layer.
- GitHub is the source of truth for code, tasks, diffs, CI and review evidence.
- The Windows supervisor remains a deterministic executor/monitor only.
- Deterministic LocalCursor Kian/Negar are fail-closed by default and may be enabled only for explicit smoke tests.
- No local Ollama model is required.
- No broker or Live trading capability is added.

## Delivery contract

1. A task must have explicit scope and acceptance criteria.
2. ChatGPT creates or updates a dedicated feature branch through GitHub.
3. GitHub Actions runs the protected and candidate test suites.
4. ChatGPT reviews the actual diff and CI result against the task contract.
5. Low-risk merges may only occur when the repository policy allows them.
6. Policy, workflow, planning, secrets, broker/live, destructive, and other high-risk changes remain human-gated.
7. A deterministic scaffold is never counted as a completed implementation.

## Local runtime

The PC may keep the supervisor online for Telegram, status, GitHub polling and deterministic execution. It is not an AI coding source in this mode.

Set `ALLOW_DETERMINISTIC_LOCAL_WORKERS=true` only for explicit local smoke tests. Production development should leave it unset/false.

## Quality rule

A task is DONE only when the implementation exists in code, its acceptance criteria are covered by tests/evidence, CI is green, and the resulting GitHub state is verified. Documentation-only scaffolds do not satisfy implementation tasks.
