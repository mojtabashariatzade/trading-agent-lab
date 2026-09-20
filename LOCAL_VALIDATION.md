# Local validation receipt -- release-truth verification

Date: 2026-09-20T23:34+03:00. Python: **3.12.10**.
Workspace: `D:\generative-search-production (1)\trading-agent-team-named-v2\trading-agent-team`

**Verified this run: 127 tests passed (full discover + protected CI suite).**
No external account was connected or modified during this verification.

## Receipt conflict resolved

| Copy | Path | Status |
|---|---|---|
| Stale owner Downloads copy | `c:\Users\LENOVO\Downloads\LOCAL_VALIDATION.md` | Old named-team v2: claimed **113** tests and **advisory-only** research |
| Active workspace receipt | this file | Matches code after research-team upgrade |

The Downloads zip/receipt was the pre-upgrade package. The active workspace contains the research queue implementation. This receipt supersedes the Downloads copy.

## Commands and results (re-run)

```text
python --version
# Python 3.12.10

python -m unittest discover -s tests -v
# Ran 127 tests in ~0.29s
# OK

python -m unittest tests.test_policy tests.test_store tests.test_controller \
  tests.test_contracts tests.test_providers tests.test_settings \
  tests.test_team tests.test_research -v
# Ran 127 tests in ~0.27s
# OK
# Module counts: policy 26, store 6, controller 32, contracts 16,
# providers 9, settings 6, team 18, research 14 = 127

python -m compileall -q agentops trading_lab
# exit 0

python -m agentops.demo
# OFFLINE_FAKE_PROVIDER_DEMO; external_calls=0; paid_agents_started=0; real_trades=0
```

## Git status

```text
Not a git repository (no .git directory).
No commit history, branch, or remote.
Bootstrap has not published this tree yet.
```

## Research capability matrix (code vs claim)

| Capability | Present in code? | Primary locations | Proving tests |
|---|---|---|---|
| Research task queue (SQLite) | YES | `agentops/store.py` `research_tasks` table; `save_research` / `research` / `research_tasks` | `tests.test_research.ResearchQueueTests.test_request_assigns_parsa_for_strategy` |
| Typed Citation/Finding/Report/Artifact | YES | `agentops/research_contracts.py` | `test_complete_report_passes_gate_and_creates_artifact`; `test_structural_gate_requires_data_coverage` |
| Parsa/Niloofar/Saman research-worker paths | YES | `team.py` `research_worker_after_setup` + `RESEARCH_WORKER_ROLES`; `controller.launch_research`; `research.research_prompt` | `test_research_workers_are_first_class` (team); `test_research_launch_uses_research_worker_not_coding_profile`; `test_dev_waits_for_required_research` |
| Coding launch fail-closed for research roles | YES | `worker_profile` vs `research_worker_profile`; `launch` vs `launch_research` | `test_research_roles_cannot_use_coding_launch`; `test_only_developer_and_qa_are_coding_workers` |
| Evidence/source structural gate | YES | `research.structural_review_gate` + fabrication markers | `test_fabrication_marker_is_rejected`; `test_structural_gate_requires_data_coverage` |
| BLOCKED + exact missing dependency | YES | `submit_research_report` when `status=BLOCKED` | `test_blocked_report_keeps_exact_dependency` |
| Arman research-before-development gate | YES | `research_gate_for_dev`; backlog `requires_research`; auto `request_research` + launch | `test_dev_waits_for_required_research` |
| Kian consumes approved artifacts only | YES | `prompt(dev)` + `format_artifact_for_developer` | `test_kian_prompt_consumes_approved_artifact`; `test_developer_prompt_has_kian_and_research_artifact_rules` |
| Negar reviews research evidence | YES | `prompt(qa)` + `format_artifacts_for_qa` | `test_negar_prompt_checks_research_evidence` |
| Raha research Telegram reporting | YES | `event()` outbox signed by support; research kinds | `test_raha_reports_research_progress` |
| `/team` live role status | YES | `live_team_report` + `role_activity` | `test_team_command_shows_live_research_status` |
| `/research` queue/status/blockers | YES | `handle_research_command` + `research_status_report` | `test_research_command_lists_owner_status_blockers`; `test_research_request_command_queues_without_unpause_when_paused` |
| Arman ≠ Trading Decision Core | YES | no `decide` import in controller; `assert_not_decision_core` | `test_arman_is_separate_from_decision_core` |

## Still mocked / not done

- Real Cursor Cloud research/coding workers (FakeCursor only).
- Real GitHub PR/CI/Telegram bot hosting/Docker deploy.
- Live internet source fetches; historical market downloads; training; broker; Live trading.
- Research completion path in production uses Cursor run results; offline tests inject reports via `submit_research_report`.
- `gh` CLI: **not installed** on this machine.
- Docker: **not installed** on this machine.
- Git repository: **not initialized** yet.
- No budget/phase/merge/live-trading limit was relaxed.

## Bootstrap readiness after this receipt

Local research-team upgrade is verified in code and tests.
Control-plane bootstrap started; see `BOOTSTRAP_RECEIPT.md`.

Current external blockers (do not fabricate success):
- GitHub: `gh` installed; **owner must complete** device login at https://github.com/login/device
- Cursor Cloud API key / spend cap: unset / unconfirmed
- Telegram BotFather + numeric IDs: not configured (never paste token in chat)
- Docker host: not installed locally; one ~USD 7/mo hosting proposal pending approval

This is a local test receipt, not a security audit or production readiness claim.
