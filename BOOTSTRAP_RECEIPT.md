# Bootstrap receipt -- honest blockers after release-truth verification

Date: 2026-09-20. Role: Sohrab (bootstrap). No live trading. No broker.

## Release-truth (completed)

- Active workspace research upgrade verified: **127/127 tests OK**, compileall OK, offline demo OK.
- Stale Downloads receipt (113 / advisory-only) corrected to point at workspace truth.
- Capability proof matrix is in `LOCAL_VALIDATION.md`.

## A. GitHub -- BLOCKED on owner auth

| Step | Result |
|---|---|
| Local `git init -b main` | DONE (no commits yet; identity unset in git config) |
| Install `gh` 2.101.0 | DONE via winget |
| `gh auth status` | **NOT LOGGED IN** |
| Create private `trading-agent-lab` | **BLOCKED** |
| Push / protect main / CI+owner merge rules | **BLOCKED** |

Owner action required (one-time, in a local terminal — not in chat):

```text
gh auth login --hostname github.com --git-protocol https --web
```

After login succeeds, reply here with “GitHub auth done” (do not paste tokens). Bootstrap will then create/use private `trading-agent-lab`, push, and configure protections.

## B. Cursor Cloud -- BLOCKED

- `CURSOR_API_KEY` env: UNSET
- No spend-cap confirmation
- Do **not** start paid agents until owner approves an explicit spending cap

Owner: connect the private repo in Cursor Cloud UI and set a real provider spend limit, then confirm the cap amount in chat (number only, no API key).

## C. Telegram -- BLOCKED (owner BotFather steps)

Do **not** paste the bot token into this chat.

1. In Telegram, open @BotFather → `/newbot` → choose name/username.
2. Store the token only in the host secret UI as `TELEGRAM_BOT_TOKEN`.
3. Message the bot from your private account; record **numeric** owner user id and control chat id (`TELEGRAM_OWNER_IDS`, `TELEGRAM_CONTROL_CHAT_ID`).
4. Optional read-only report channel id → `TELEGRAM_REPORT_CHAT_ID` (not a command source).
5. After secrets exist on the host, verify `/team`, `/research`, `/status`, `/pause`, `/resume`, `/stop`.

## D. Persistent hosting -- BLOCKED (Docker missing locally)

- Docker CLI: **not installed** on this machine.
- No existing authorized Docker host was detectable from this environment.

**Single hosting proposal (do not purchase without approval):**
- Small always-on Linux Docker / background worker (e.g. Render Background Worker class).
- Purpose: Arman/Raha control plane + persistent SQLite volume + Telegram long-poll.
- Documented cost class: roughly **~USD 7/month** on common starter PaaS plans — confirm current public pricing before any purchase.
- `purchase_authorized`: **false**

## E. Smoke test -- NOT STARTED

Requires A–D. When unblocked: one harmless coding cloud task + one harmless research worker smoke (Parsa/Niloofar/Saman path), artifact → review → CI → Negar → owner approval. **No merge without owner approval.**

## F. Telegram owner report -- NOT SENT

No bot connected; fabricating a Telegram report would violate honesty rules.

## Explicit non-actions

- No broker connectivity
- No live trading
- No large paid dataset download
- No fabricated GitHub/Cursor/Telegram/Docker success
