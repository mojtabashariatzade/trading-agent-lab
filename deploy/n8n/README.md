# n8n server deployment kit

Version 1.0.0 | Prepared 2026-09-22 | State: PREPARED / NOT DEPLOYED

## Purpose and boundary

Prepare server-side project coordination now; install only when the owner names
an accessible server and explicitly requests deployment. This is NOT the trading
engine. The product remains the owner's autonomous LONG/SHORT trader. Its market
state, specialist competition, Trading Decision Core and deterministic risk layer
stay in the Python trading application, not in an n8n timer or language-model node.
No sales, customer-pricing or subscription work is introduced.

The kit implements n8n + PostgreSQL + a small private Python bridge. There is no
Redis/queue-mode cluster yet: one control host is enough for this initial scope.
The existing Windows supervisor, repo-root compose file and Telegram polling are
not modified. No service, server, credential, model API or live trade is activated
by downloading this kit or merging its source.

## What is included

- Four importable, inactive workflows: GitHub snapshot every five minutes; private
  Telegram polling every minute; one durable outbox send each minute; daily UTC
  plan/evidence digest at 08:00. These run only after installation and activation.
- Repo-scoped GET-only GitHub access. Main SHA pins plan/state fetches. Paginated
  issue lists flag incompleteness. A snapshot is not fresh CI/review evidence.
- Private Telegram owner/chat allowlist, stale-command rejection, persistent
  update offsets, duplicate suppression, and messages never copied to public #27.
- /status, /update, /today, /help, /pause, /resume and /stop in THIS new bridge.
  /today is explicitly the nominal plan, not an assertion of work performed.
  /pause and /stop pause request handoff only, not trading or protective orders.
- Free text is queued privately for a real external worker. The message is not
  interpreted as shell, trade or deployment authority. Credentials are rejected.
- Authenticated, leased worker claim/result API; one outstanding job; expired
  leases and submitted results require reconciliation, not blind retry or fake DONE.
- Explicit deployment approval, host-key-verified SSH, fresh-host checks, local
  secret generation, owner creation, inactive import verification, health checks,
  persistent data, bounded logs and private local backup command.

## Important limitation: n8n is not an AI worker

No coding/research model is included, purchased or silently selected. The claim API
is a tested handoff interface, not an installed GPT agent. A separate, authorized
worker must be connected, tested and reviewed before autonomous code execution is
claimed. The active ChatGPT conversation does not become that worker by installing
n8n. Until then, the UI/status says EXTERNAL_WORKER_REQUIRED. Existing priority,
CI, exact-SHA review and no-live boundaries still apply to a connected worker.

A worker authenticates with the worker_key (not the n8n control key), POSTs
/v1/jobs/claim with its real executor name and returns /v1/jobs/result with the
lease, job_id, safe summary and repository evidence URL. A returned URL is not
proof of tests or a merge: state becomes RESULT_SUBMITTED / REVIEW_REQUIRED,
never automatically DONE. Reconciliation and a production AI executor are next
integration work, not hidden features in this release. Do not enable handoff for
an unattended team until that full loop is verified. No endpoint executes code.

## Server target and access

Initial tested-by-contract target: a fresh Ubuntu 24.04 LTS server, Docker Engine
and Compose v2, Python 3, outbound HTTPS to GitHub/Telegram/image registries. An
initial sizing proposal is 2 vCPU / 4 GB RAM with at least 20 GB free disk, for the
control services only; it is NOT a benchmark or a model-training specification.
Other OS images require a reviewed bootstrap adjustment rather than blind install.

The n8n editor binds ONLY to 127.0.0.1:5678. PostgreSQL and the bridge have no host
ports. Access the editor using an authorized SSH tunnel. No domain purchase or
public webhook is required for this polling design. Secure-cookie=false is used
ONLY for loopback HTTP over SSH; do not expose that configuration publicly.
Public UI/HTTPS needs a separately reviewed reverse proxy and secure cookies.
Host firewall rules alone are not a substitute for loopback port binding.

Server facts needed at deployment: approved host/IP, SSH port/user, independently
verified host fingerprint, secure key/authorized connector access, owner email,
and permission to install Docker on that named fresh machine. Never paste keys
or bot tokens into chat or GitHub. The prepared remote installer must have network
reachability and an available secure key file in the actual deployment environment.
The owner should not have to edit daily scripts; the operator runs this process.

## Staged installation (operator commands, not owner chores)

0. Recheck current n8n security advisories and patch release; preparation pins n8n
   2.39.10, verified from the official release on 2026-09-22. A review older than
   seven days blocks apply. Review/update the kit; do not merely forge a fresh date.
1. After explicit deployment instruction, run remote_install.py with verified
   host/user/key/known_hosts, owner email, --security-reviewed-on YYYY-MM-DD and
   --deploy-approved. --fresh-ubuntu-approved permits the included Docker package
   bootstrap on a clean Ubuntu 24.04 host. It does not delete conflicting packages.
   Without --deploy-approved it does not contact the server.
2. The operator may equivalently copy this directory to the server, then run:

       python3 install.py prepare --approved --owner-email owner@example.test
       python3 install.py apply --approved --security-reviewed-on YYYY-MM-DD

   Only the named server should run these. Fresh secrets are generated privately;
   repeat prepare preserves them, and partial unmarked state is rejected. Images
   are pulled and resolved to immutable registry digests for that installation.
   The owner bootstrap uses the pinned version's local /rest/owner/setup endpoint.
   Existing owner/data is never reset automatically. Workflows are imported inactive
   and exported back for verification. The root-level legacy compose is not used.
3. Verify .private/installed.json and actual container readiness. Test n8n imports,
   owner authentication and restart persistence. Then, with activation authorization:

       python3 install.py activate --approved

   This publishes each named workflow and restarts n8n; it does not enable external
   connectors, launch models or trade. CLI publication must be verified after restart.
4. Configure .private/connections securely on the server; restart bridge. Use a
   fine-grained READ token limited to this repo for reliable GitHub polling. An empty
   token uses public unauthenticated limits, so do not assume unlimited requests.
   Turn on github_sync_enabled only after scope/rate checks. Token scopes are an
   account-setting requirement, not enforceable by a JSON field in this kit.
5. For Telegram, verify old Windows/cloud polling has STOPPED and no webhook is in
   use. Record actual bot_id, verifier and timestamp in telegram_handoff. Then set
   owner/chat IDs and enable polling/sending. The bridge will not delete an existing
   webhook, discard pending updates or steal bot ownership. Lost/ambiguous sends
   become DELIVERY_UNCERTAIN for review instead of risking repeated messages.
6. Test a new authorized /status and /today end-to-end, then restart and prove no
   replayed updates. Only after this receipt is server-side Telegram operational.
   Do not start PR #29's cloud poller alongside this consumer.

The remote helper uploads only a fixed file allowlist; .private, backups, keys and
course media are excluded. It refuses an existing destination to avoid overwriting
an old deployment. Upgrade/migration is not the fresh-install path.

## Secrets and trusted boundaries

Generated .private has mode 0700. Files mounted as Docker secrets are 0444 inside
that private directory, allowing the non-root service UID to read its own mounted
files; they are not world-readable through the host directory. Owner bootstrap
and receipt files are 0600. PostgreSQL's app user is distinct from its administrator.
n8n cannot read GitHub/Telegram/worker credentials; only the bridge mounts those.
No Docker socket, broker secrets or arbitrary execution endpoint is provided.
The bridge is single-host trusted infrastructure; do not expose its plain HTTP
worker API to the public internet. Attach a reviewed worker to the private network
or add an authenticated encrypted transport in a future integration.

Only a trusted owner may edit workflows. Execute Command, Git, SSH, file and Code
nodes and community packages are disabled. Workflow execution payload retention is
turned off; the private SQLite inbox retains project messages for reconciliation.
Backups/inbox remain sensitive. Do not claim the stack is independently security
audited; actual version/host hardening and restore testing remain required.

## Operations, backup and rollback

       python3 install.py status
       python3 install.py backup --approved --backup-dir /approved/private/path/new-snapshot

Backup stops n8n/bridge writers, dumps the n8n database and copies bridge state,
n8n data and encryption/connection secrets, then restarts the services. The new
backup directory is private but NOT encrypted by this script. Move it only to
approved encrypted/off-host storage. A local snapshot is not disaster recovery.
No automatic destructive restore is supplied. Restore to a separate fresh instance,
restore the matching encryption key/database/files, verify logins/workflows/inbox
and only then switch the single Telegram consumer. Run that drill at deployment;
no successful restore is claimed today. Do not downgrade a migrated database in
place or delete volumes to fix a startup issue. Stop the stack without -v to
preserve data. Health checks do not prove task progress or profitable trading.

## Validation and remaining deployment gates

Offline unit/contract and loopback HTTP tests are in tests/added/test_n8n_kit.py.
The preparation environment has no Docker daemon and no external DNS connectivity.
Therefore Docker image pulls, Compose runtime validation, n8n owner/import/publish,
SSH deployment, real Telegram/GitHub delivery and backup/restore are NOT_RUN here.
These are explicit installation acceptance gates, not implied by Python tests.
No server was purchased, no Windows files changed and no existing bot polled.

## Primary implementation references (checked 2026-09-22)

- n8n release: https://github.com/n8n-io/n8n/releases/tag/n8n%402.39.10
- n8n import/deactivation CLI: https://github.com/n8n-io/n8n/blob/n8n%402.39.10/packages/cli/src/commands/import/workflow.ts
- n8n publish/restart CLI: https://github.com/n8n-io/n8n/blob/n8n%402.39.10/packages/cli/src/commands/publish/workflow.ts
- n8n owner setup: https://github.com/n8n-io/n8n/blob/n8n%402.39.10/packages/cli/src/controllers/owner.controller.ts
- Security advisories: https://github.com/n8n-io/n8n/security/advisories
- Docker Ubuntu packages: https://docs.docker.com/engine/install/ubuntu/
- Repository product boundary: docs/PROJECT_CONTRACT.md and docs/architecture/MARKET_GRAMMAR_DESIGN.md
