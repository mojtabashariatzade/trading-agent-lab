# Local validation receipt -- release-truth verification

Date: 2026-09-21. Python: **3.12.10**.
Workspace: `D:\generative-search-production (1)\trading-agent-team-named-v2\trading-agent-team`

Repository (intentional **PUBLIC**): https://github.com/mojtabashariatzade/trading-agent-lab  
Default branch: `main`  
Verified main tip at receipt time: see `BOOTSTRAP_RECEIPT.md` (re-fetch before relying on SHA).

## Commands and results (re-run this session)

```text
python --version
# Python 3.12.10

python -m unittest discover -s tests -v
# Ran 179 tests — OK

python -m unittest tests.test_policy tests.test_store tests.test_controller \
  tests.test_contracts tests.test_providers tests.test_settings \
  tests.test_team tests.test_research -v
# Protected suite — Ran 119 tests — OK

python -m unittest discover -s tests/added -v
# Candidate suite — Ran 49 tests — OK (LocalCursor/maf/dup-PR/Negar QA)

python -m compileall -q agentops trading_lab
# exit 0
```

Exact counts also recorded in `BOOTSTRAP_RECEIPT.md` from the same machine run. Main tip SHA is re-fetched there (do not rely on a stale SHA in this file).

## Git / GitHub (current reality)

```text
Git repository: YES (connected)
Remote: https://github.com/mojtabashariatzade/trading-agent-lab.git
Visibility: PUBLIC (intentional — do not flip to private)
Default branch: main
Active workflow: .github/workflows/ci.yml (name: research-ci)
gh CLI: available (PATH may need Machine+User refresh on new shells)
```

## Research / Development Core capability (code vs claim)

| Capability | Status |
|---|---|
| Research queue + artifacts | Present in code + tests |
| LocalCursor Kian/Negar workers | Present (local runtime) |
| Detached supervisor | Present (`python -m agentops.supervisor`) |
| MAF durable orchestration flag | Present (`ORCHESTRATION_BACKEND=maf_durable` default) |
| Duplicate open-PR reuse | Present (controller + LocalCursor + tests) |
| Negar QA evidence artifact | Present (`agentops/qa_evidence.py`; software role, not a GitHub human) |
| Cursor Cloud paid workers | Not configured / not claimed complete |
| Telegram production bot | Optional / not claimed complete |
| Docker / DTS emulator | Docker not installed on this PC; local checkpoint used |
| Broker / Live trading / market downloads | Not enabled; out of scope |

## Remaining blockers (honest)

- PR `#8` remains **draft** until CI green on latest head, feature verified, branch up to date with `main`, and Negar QA evidence for that exact head SHA.
- Owner approval remains required for live trading, broker, secrets, paid spend, destructive ops.
- Enforce admins on branch protection is **off** (admin bypass still possible).
- Negar is **not** a separate GitHub human identity; evidence is a machine-readable artifact + PR comment.

This is a local/control-plane receipt, not a profitability or production-readiness claim.
