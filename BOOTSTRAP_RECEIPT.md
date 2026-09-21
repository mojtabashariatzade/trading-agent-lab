# Bootstrap / control-plane receipt

Date: 2026-09-21. No Live trading. No broker access. No Cursor Cloud required for this receipt.

## Repository

| Item | Value |
|---|---|
| URL | https://github.com/mojtabashariatzade/trading-agent-lab |
| Visibility | **PUBLIC** (intentional; do not change to private) |
| Default branch | `main` |
| main SHA (fetched this receipt) | `93d6c7828b15508c0618dcff370966cdca7fbee5` |
| Active workflow file | `.github/workflows/ci.yml` (`research-ci`) |

## Branch protection (`main`) — verified via API

| Rule | Status |
|---|---|
| Force push blocked | YES (`allow_force_pushes=false`) |
| Branch deletion blocked | YES (`allow_deletions=false`) |
| Required status check | `qa` (strict / up-to-date with base) |
| Required PR reviews | YES (`required_approving_review_count=1`, `dismiss_stale_reviews=true`) |
| Enforce admins | NO (admins can still bypass — documented limitation) |
| `require_last_push_approval` | NO (limitation: last pusher need not re-approve) |
| Rulesets | none configured (classic branch protection in use) |
| GitHub “Negar approval” check | **NOT created** — Negar is a software role, not a GitHub human |

## CI workflow hygiene (`.github/workflows/ci.yml`)

| Item | Status |
|---|---|
| `permissions.contents` | `read` |
| `pull_request_target` | absent |
| Self-hosted runner | absent (`ubuntu-24.04`) |
| `persist-credentials` | `false` |
| Protected vs candidate tests | separate interpreter steps |
| Repo secrets exposed to candidate | none declared in workflow |

## Test counts (this machine, same session)

| Suite | Result |
|---|---|
| Full `unittest discover -s tests` | OK (**179**) |
| Protected suite | OK (**119**) |
| Candidate `tests/added` | OK (**49**) |
| `compileall agentops trading_lab` | exit 0 |

## Open / closed PRs (control-plane cleanup)

Closed as superseded (with comments):

- `#5` → superseded by merged `#7` (M15 bars)
- `#6` → superseded by merged `#7`
- `#12` → superseded by merged `#13` / `eb8ce07…`

Kept open:

- `#8` draft — autonomous supervisor / agentops (must stay draft until gates below; head SHA invalidated when docs/merge commits land)
- `#14` — T101 parallel autonomy probe (still useful; CI green)
- `#17` — T102 parallel autonomy probe (still useful; CI green)

Merged during cleanup window (no longer open): `#16` (T003), `#19` (T004).

## PR `#8` gates (not merge-ready until all true)

- [ ] Latest head CI `research-ci` / `qa` GREEN (re-verify after each push)
- [x] Feature behavior verified on this PC (LocalCursor `_commit` / `_write_t002_execution` present; suites OK)
- [x] Branch contains merge of `main` @ `93d6c78…`
- [ ] Negar QA evidence artifact for **exact current** head SHA (prior SHA evidence is invalid after new commits)
- [x] Remains **draft** until owner promotes (not merged by this cleanup)

## Negar QA mechanism

- Module: `agentops/qa_evidence.py`
- Artifact dir: `%LOCALAPPDATA%\trading-agent-lab\status\negar_qa\`
- Also posted as a fenced JSON PR comment when CI+QA PASS
- Invalid if PR head SHA changes
- Not a separate GitHub human reviewer

## Duplicate PR prevention

- `GitHub.find_open_pr_number` / `find_open_prs`
- `Controller.bind_existing_open_pr` before relaunch
- `LocalCursor._find_existing_pr` before `gh pr create`
- Tests: `tests/added/test_duplicate_pr_prevention.py`

## Operating notes

- Supervisor: `python -m agentops.supervisor` (detached via `scripts/start-supervisor.ps1`)
- Status: `%LOCALAPPDATA%\trading-agent-lab\status\runtime_status.json`
- Telegram / Docker / Cursor Cloud / broker / Live: **not** claimed complete

## Docs updated

- `LOCAL_VALIDATION.md`: YES (this cleanup)
- `BOOTSTRAP_RECEIPT.md`: YES (this file)
