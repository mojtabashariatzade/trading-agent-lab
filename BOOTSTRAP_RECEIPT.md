# Bootstrap / control-plane receipt

Date: 2026-09-21. No Live trading. No broker access. No Cursor Cloud required for this receipt.

## Repository

| Item | Value |
|---|---|
| URL | https://github.com/mojtabashariatzade/trading-agent-lab |
| Visibility | **PUBLIC** (intentional; do not change to private) |
| Default branch | `main` |
| main tip at docs publish (parent) | `0b774ac562f1d0768fe38fce9c83a64fe6af3b58` |
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

## Test counts (final verified)

Verified after syncing the control-plane candidate tree with `main@93d6c7828b15508c0618dcff370966cdca7fbee5` (no re-count for later docs-only publish):

| Suite | Result |
|---|---|
| Full `unittest discover -s tests` | OK (**179**) |
| Protected suite | OK (**119**) |
| Candidate `tests/added` | OK (**49**) |
| `compileall agentops trading_lab` | exit 0 |

Note: those **179 / 49 / 119** counts include candidate control-plane tests delivered on draft PR `#8`. They are the final verified hygiene numbers. Bare `main` without `#8` has a smaller candidate set until `#8` merges.

## Open / closed PRs (control-plane cleanup)

Closed as superseded (with comments):

- `#5` → superseded by merged `#7` (M15 bars)
- `#6` → superseded by merged `#7`
- `#12` → superseded by merged `#13` / `eb8ce07…`

Kept open:

- `#8` draft — autonomous supervisor / agentops
- `#14` — T101 parallel autonomy probe (still useful; CI green)
- `#17` — T102 parallel autonomy probe (still useful; CI green)

Merged during/after cleanup window: `#16` (T003), `#19` (T004), `#21` (T005).

## PR `#8` gates (not merge-ready until all true)

- Draft until owner promotes
- CI + Negar QA must match the **exact current** head SHA (a new push invalidates prior Negar evidence)
- Owner approval remains a separate gate

## Negar QA mechanism

- Module: `agentops/qa_evidence.py` (on PR `#8` until merged)
- Artifact dir: `%LOCALAPPDATA%\trading-agent-lab\status\negar_qa\`
- Also posted as a fenced JSON PR comment when CI+QA PASS
- Invalid if PR head SHA changes
- Not a separate GitHub human reviewer

## Duplicate PR prevention

- `GitHub.find_open_pr_number` / `find_open_prs`
- `Controller.bind_existing_open_pr` before relaunch
- `LocalCursor._find_existing_pr` before `gh pr create`
- Tests: `tests/added/test_duplicate_pr_prevention.py` (on PR `#8` until merged)

## Operating notes

- Supervisor: `python -m agentops.supervisor` (detached via `scripts/start-supervisor.ps1`)
- Status: `%LOCALAPPDATA%\trading-agent-lab\status\runtime_status.json`
- Telegram / Docker / Cursor Cloud / broker / Live: **not** claimed complete

## Docs updated

- `LOCAL_VALIDATION.md`: YES
- `BOOTSTRAP_RECEIPT.md`: YES (this file)
