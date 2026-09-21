# Bootstrap / control-plane receipt

Date: 2026-09-21. No Live trading. No broker access. No Cursor Cloud required for this receipt.

## Repository

| Item | Value |
|---|---|
| URL | https://github.com/mojtabashariatzade/trading-agent-lab |
| Visibility | **PUBLIC** (intentional; do not change to private) |
| Default branch | `main` |
| main SHA (fetched this receipt) | `eb8ce07c7f1b2e67526998c9e3f9aff56a9390ea` |
| Active workflow file | `.github/workflows/ci.yml` (`research-ci`) |

## Branch protection (`main`) — verified via API

| Rule | Status |
|---|---|
| Force push blocked | YES (`allow_force_pushes=false`) |
| Branch deletion blocked | YES (`allow_deletions=false`) |
| Required status check | `qa` (strict / up-to-date with base) |
| Required PR reviews | YES (`required_approving_review_count=1`, `dismiss_stale_reviews=true`) |
| Enforce admins | NO (admins can still bypass — documented limitation) |
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
| Full `unittest discover -s tests` | OK (175+ after control-plane additions; re-run for exact) |
| Protected suite | OK (~119) |
| Candidate `tests/added` | OK (~45+) |
| `compileall agentops trading_lab` | exit 0 |

## Open / closed PRs (control-plane cleanup)

Closed as superseded (with comments):

- `#5` → superseded by merged `#7` (M15 bars)
- `#6` → superseded by merged `#7`
- `#12` → superseded by merged `#13` / `eb8ce07…`

Kept open:

- `#8` draft — autonomous supervisor / agentops (must stay draft until gates below)
- `#14` — T101 parallel autonomy probe (still useful; CI previously green)
- Also observed open (not in original close list): `#16` T003 scaffold, `#17` T102 probe — leave unless later superseded

## PR `#8` gates (not merge-ready until all true)

- [ ] Latest head CI `research-ci` / `qa` GREEN
- [ ] Feature behavior verified on this PC
- [ ] Branch up to date with `main`
- [ ] Negar QA evidence artifact for **exact** head SHA
- [ ] Remains draft until owner promotes

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
