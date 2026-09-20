# One-time deployment -- instructions for the bootstrap agent/operator

Status: package built and unit-tested locally. Nothing is published or running in
a customer account yet. Online API integration and Docker deployment must be
smoke-tested with the owner's authorized accounts. Do not hide this gap.

## Chosen starting architecture
- Private GitHub repository: code, task issues, PRs and independent CI.
- Cursor Cloud Agents API v1: one developer and a separate fresh QA run per task.
- Small, continuously running Linux Docker worker: `agentops`, its SQLite state,
  Telegram long polling and provider status polling. No inbound port or webhook.
- A dedicated Telegram bot: private owner chat for commands; optional channel
  for read-only reports. Never accept authority from an anonymous channel post.
- No GPU or custom LLM training is needed for the development controller.

Cursor cloud runs do not require the user's PC to stay on. The CONTROL WORKER
also needs a persistent host; leaving this ChatGPT chat or closing a local Cursor
window is not a hosting service. GitHub schedules are deliberately not the control
runtime: delayed/dropped scheduled jobs and ephemeral state are a poor default for
responsive command/approval handling.

## Accounts and permissions -- human authorization cannot be fabricated
1. Private repo, default branch `main`, GitHub Actions enabled. The bootstrap
   agent can create `trading-agent-lab` with the authenticated GitHub CLI, but must
   not overwrite an existing repo. Push the starter BEFORE applying branch rules.
2. Connect Cursor source control ONLY to the research repository; use a separate
   research-only Cursor workspace where possible. Choose a paid plan / account
   with required Cloud API access and set a REAL provider spending limit. Do not
   set ALLOW_AGENT_RUNS before the owner approves spending. No keys inside agent VMs.
3. Controller GitHub credential is scoped to this single repo, with Contents:
   write (GitHub requires this for merge), Issues: write, Pull requests: write,
   Actions: read and metadata read. No organization admin, deployments, secrets,
   workflow-write or access to unrelated repositories. A narrowly scoped bot
   identity is preferred; rotate tokens and configure expiry alerts.
4. Telegram bot via the official BotFather flow. Owner sends a private message
   to the bot. Confirm the numeric owner user ID and numeric control chat ID
   from that message; NEVER mistake getMe's bot ID for the owner's ID. Tokens go
   into host secret settings. Do not ask the owner to paste them into ChatGPT.
   For a report channel, give the bot only the necessary posting permission;
   approvals stay in the allowlisted private/group control chat.
5. Choose an owner-approved persistent Docker host. No server purchase is
   authorized by this package. Generic compose is supplied; managed background
   workers such as Render are an alternative but require adapting the deployment
   and validating disk ownership. This package does not pretend to have deployed one.

## Mandatory GitHub protections
- Require pull requests and the `qa` check from the GitHub Actions app.
- Require the branch to be up to date, prohibit force pushes/deletions.
- Restrict writes/merges to `main` to the OWNER and CONTROLLER identity. Exclude
  the Cursor App and coding-agent identities. Do not give them bypass rights.
- Enforce restrictions for privileged actors where the repository plan supports it.
- Keep a human approval path for controller/policy/workflow changes. CODEOWNERS
  can be added with the actual owner handle; do not leave invented handles.
- Validate the restrictions with a negative test: a coding worker must NOT be
  able to push to or merge into main even if CI passes. Merely naming a role
  "reviewer" or instructing an agent not to merge is not an access boundary.
- A private-repository plan that cannot enforce these rules is NOT ready. Do not
  weaken requirements to make a demo run. Use an appropriate plan or remain local.

Runtime preflight checks that the repo is private and branch protected. The
additional actor restrictions require bootstrap verification; the Boolean
REPOSITORY_PROTECTION_CONFIRMED is an attestation, not a substitute for actual rules.

## Secrets and startup
Use the provider secret UI for names in `.env.example`, not a committed .env.
Never pass operator secrets through Cursor envVars or repository snapshots.
Build a controller image from the REVIEWED starter; do not auto-rebuild it from
future research PRs. The image copies only agentops and the approved backlog.
With secrets already injected by the host, the operator/agent runs:

    docker compose up -d --build

Only one controller instance; mount the named persistent volume at /state with
UID 10001 write access. No Docker socket, host home directory or candidate source
mount. No public ingress ports. Back up SQLite using SQLite's backup API (not a
live copy of only the main .sqlite file while WAL is in use). Test restore while
stopped. Secure the host and rotate access.

Set ALLOW_AGENT_RUNS, SPEND_LIMIT_CONFIRMED and REPOSITORY_PROTECTION_CONFIRMED=true
ONLY after these checks and explicit owner authorization. The service still
starts paused on a fresh DB; the owner sends /resume in Telegram.

## Exact operational behavior
- One delivery at a time. Default maximum 4 cloud launches/day (dev and QA BOTH
  count), maximum 2 developer attempts per task, 90-minute run watchdog.
- These are launch/time bounds, NOT a dollar budget. Hosting, CI and data vendors
  have separate charges. Configure vendor hard spending controls and billing alerts.
- Developer -> scoped PR -> GitHub CI -> independent QA -> owner approval -> merge.
- The approval is exact head-SHA bound and expires after 24h. A head/base change
  requires renewed CI/review, not reuse of an old green result.
- /pause prevents new launches but monitors existing jobs; /stop requests
  cancellation and waits for confirmation. Neither is an instantaneous financial
  kill switch. No real broker is connected in this product.
- /request creates a new issue for scope review; free-form messages never directly
  execute shell commands or expand the authorized backlog.
- Software failure/provider outage is BLOCKED, not fabricated completion.
- Telegram outage pauses new dispatch and continues monitoring existing jobs.
- Notifications are at-least-once, deduplicated locally; uncertain network delivery
  may duplicate reports. Task launch uses Cursor's documented idempotent agent ID.
- Backlog content is hashed. Changes need a reviewed migration; do not delete
  the state DB to skip this guard. Later phases need an explicit reviewed release.

## Deployment smoke-test checklist (NOT performed in this ChatGPT environment)
Confirm bot webhook is empty without deleting an unrelated bot's webhook.
Confirm /status, rejected wrong-user command, /pause and /resume preflight.
Confirm provider model/API access and repository access with a tiny bounded task.
Verify a real PR triggers the pinned CI workflow and its qa job.
Verify the QA result matches the exact head SHA, and invalid JSON blocks approval.
Attempt stale-SHA and protected-file changes: must block.
Approve a harmless PR and confirm the GitHub merge and issue closure.
Restart controller mid-run and verify no duplicate cloud agent or merge.
Verify provider spending cap, disk restore and operator outage alerting.
Only then authorize the six phase-1 tasks. Never activate Live.
