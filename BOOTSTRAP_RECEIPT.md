# Status receipt — autonomous-by-default + persistent supervisor

Date: 2026-09-21. No Cursor Cloud. No live trading. No broker access.

## Operating model
- Normal development/research/tests/PRs: auto-merge when CI green + Negar PASS + no high-risk files.
- Human approval only for: live trading, broker, secrets, paid spend, destructive ops, production deploy, security/branch-protection, irreversible data.
- Supervisor runs as a real OS process independent of the Cursor chat window.

## How to start / monitor (Windows)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-supervisor.ps1
powershell -ExecutionPolicy Bypass -File scripts\check-supervisor-status.ps1
```

## Three facts to verify it is alive

| Item | Value |
|---|---|
| Main process name | `python` (`python.exe`) |
| Supervisor command | `python -m agentops.supervisor` |
| Status file | `%LOCALAPPDATA%\trading-agent-lab\status\runtime_status.json` |

Also: Config file (non-sensitive flags only)
`%LOCALAPPDATA%\trading-agent-lab\status\runtime_config.json`

## Monitoring policy (no approval needed)
- Read-only checks (`Get-Content`, `Get-Process`) on status/config/logs/pid are always allowed.
- Never open `secrets.env` for heartbeat or status.
- Trust `runtime_status.json` + alive PID over the Cursor chat UI.

## Watchdog
- Stuck timeout: 5 minutes (`STUCK_TIMEOUT_SECONDS=300`)
- Max automatic stuck/crash retries: 3 (then BLOCKED, continue queue)
- Supervisor OS restart: `scripts\register-supervisor-autostart.ps1` (Task Scheduler)

## Cursor chat must not block
- Use `scripts\ensure-supervisor.ps1` only (exits in ~1s after DETACHED_OK).
- Never `tail -f` / `Get-Content -Wait` on supervisor logs from Cursor.
- Monitor via finite `runtime_status.json` snapshots only.

## Self-heal
- Failure-pattern registry: `%LOCALAPPDATA%\trading-agent-lab\status\failure_patterns.json`
- Maintenance reports: `%LOCALAPPDATA%\trading-agent-lab\status\maintenance\`
- Max autonomous repairs per failure class: **3** then `SELF_HEAL_BLOCKED` (counters persist across restart; reset only after a recorded fix, not on a timer)
- Launching without a `run_id` is not a heal and is not reported as `RUNNING / Kian`
- `MAX_DAILY_LAUNCHES` is a cloud/paid budget. Local `LocalCursor` workers are not a daily team wall
- Ready PRs resume at CI/QA; Kian is not relaunched for the same delivery
- Independent ready tasks continue while another task waits on CI, approval, or a hard block
- After CI+QA PASS, allowlisted self-heal files are auto-committed and pushed
- Never auto-modifies live trading / broker / secrets / spend / security without approval

## Notes
- PC sleep/shutdown stops local execution until the machine wakes (Task Scheduler/Startup resumes when logged on).
- Heartbeat writes at least every 5 minutes (`HEARTBEAT_SECONDS=300`).
- Telegram status mirror is optional.
