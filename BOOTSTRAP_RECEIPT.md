# Bootstrap receipt

Date: 2026-09-21. Account: **mojtabashariatzade**

## Done
- Authenticated GitHub CLI (keyring) + `gh auth setup-git` so **normal git push/pull no longer needs device codes** on this PC
- Private repo: https://github.com/mojtabashariatzade/trading-agent-lab
- Pushed `main` at commit `29cfae3` (research-team verified tree)
- Repo is **private**

## Intentionally deferred / blocked
- `.github/workflows/ci.yml` not pushed: GitHub OAuth app token still lacks `workflow` scope (device refresh never stuck). CI file is ready for a **one-time web upload**.
- Classic branch protection API returned **403** (needs GitHub Pro on private repos, or public repo). Ruleset attempt recorded separately.

## One-time CI upload (browser, no device code)
1. Open https://github.com/mojtabashariatzade/trading-agent-lab/new/main/.github/workflows  
2. Filename: `ci.yml`  
3. Paste contents from download: `C:\Users\LENOVO\Downloads\ci.yml`  
4. Commit to `main` (or open a PR if you prefer)

## No more device codes for daily work
`gh` + git credential helper are configured for this machine. Future `git push` / `gh` calls reuse the keyring token.
Only updating **workflow files via CLI** would need `workflow` scope again — use the website for that, or create a classic PAT with `repo`+`workflow` locally (never paste tokens in chat) and run:
`gh auth login --with-token < path\to\pat.txt`

## Still not done
Cursor Cloud, Telegram, Docker hosting, smoke tests, live trading (disabled).

## Downloads
- Project zip: `C:\Users\LENOVO\Downloads\trading-agent-lab-research-verified.zip`
- CI file: `C:\Users\LENOVO\Downloads\ci.yml`
- This receipt: `C:\Users\LENOVO\Downloads\BOOTSTRAP_RECEIPT.md`
