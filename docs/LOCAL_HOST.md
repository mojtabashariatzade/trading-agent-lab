# Local PC host (no cloud server)

Host machine runs Arman/Raha control plane with persistent SQLite under
`%LOCALAPPDATA%\trading-agent-lab\`.

## Start

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-local-host.ps1
```

Secrets file (outside git):

`%LOCALAPPDATA%\trading-agent-lab\secrets.env`

`GITHUB_TOKEN` is filled automatically from `gh auth token` when possible.
You must fill Telegram + Cursor keys yourself (never paste them into chat).

## Safety defaults

- `ALLOW_AGENT_RUNS=false`
- `SPEND_LIMIT_CONFIRMED=false`
- `REPOSITORY_PROTECTION_CONFIRMED=false`
- No broker / live trading
