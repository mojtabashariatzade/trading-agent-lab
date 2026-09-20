param([switch]$Restart)
# Detached supervisor launcher. MUST exit quickly — never blocks Cursor chat.
# Does NOT survive PC sleep/shutdown. Does NOT enable live trading.
# Monitoring: scripts/check-supervisor-status.ps1 (finite snapshot only). NEVER secrets.env.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Data = Join-Path $env:LOCALAPPDATA "trading-agent-lab"
$StateDir = Join-Path $Data "state"
$StatusDir = Join-Path $Data "status"
$Secrets = Join-Path $Data "secrets.env"
$LogDir = Join-Path $Data "logs"
New-Item -ItemType Directory -Force -Path $StateDir, $StatusDir, $LogDir | Out-Null

$env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User')

if (-not (Test-Path $Secrets)) {
  @"
# Local secrets — NEVER commit. NEVER paste into chat. NEVER read for status monitoring.
GITHUB_REPOSITORY=mojtabashariatzade/trading-agent-lab
GITHUB_TOKEN=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CONTROL_CHAT_ID=
TELEGRAM_OWNER_IDS=
TELEGRAM_REPORT_CHAT_ID=
"@ | Set-Content -Path $Secrets -Encoding UTF8
  Write-Host "Created secrets template (tokens only): $Secrets"
  Write-Host "Fill GITHUB_TOKEN (or rely on gh auth). Then re-run."
  exit 2
}

Get-Content $Secrets | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#")) { return }
  $i = $line.IndexOf("=")
  if ($i -lt 1) { return }
  $k = $line.Substring(0, $i).Trim()
  $v = $line.Substring($i + 1).Trim()
  Set-Item -Path "Env:$k" -Value $v
}

if (-not $env:GITHUB_TOKEN) {
  $tok = & gh auth token 2>$null
  if ($LASTEXITCODE -eq 0 -and $tok) { $env:GITHUB_TOKEN = $tok }
}
if (-not $env:GITHUB_TOKEN) {
  Write-Host "Missing GITHUB_TOKEN (set in secrets.env or gh auth login)"
  exit 3
}

$env:STATE_PATH = Join-Path $StateDir "team.sqlite3"
$env:RUNTIME_STATUS_PATH = Join-Path $StatusDir "runtime_status.json"
$env:RUNTIME_CONFIG_PATH = Join-Path $StatusDir "runtime_config.json"
$env:GITHUB_REPOSITORY = if ($env:GITHUB_REPOSITORY) { $env:GITHUB_REPOSITORY } else { "mojtabashariatzade/trading-agent-lab" }
$env:AGENT_RUNTIME = "local"
$env:TELEGRAM_OPTIONAL = "true"
$env:AUTO_MERGE_SAFE = "true"
$env:AUTONOMOUS_DEFAULT = "true"
$env:ALLOW_AGENT_RUNS = "true"
$env:SPEND_LIMIT_CONFIRMED = "true"
$env:REPOSITORY_PROTECTION_CONFIRMED = "true"
$env:ALLOW_PUBLIC_REPO = "true"
$env:CURSOR_API_KEY = "local"
$env:POLL_SECONDS = if ($env:POLL_SECONDS) { $env:POLL_SECONDS } else { "30" }
$env:HEARTBEAT_SECONDS = if ($env:HEARTBEAT_SECONDS) { $env:HEARTBEAT_SECONDS } else { "300" }
$env:STUCK_TIMEOUT_SECONDS = if ($env:STUCK_TIMEOUT_SECONDS) { $env:STUCK_TIMEOUT_SECONDS } else { "300" }
$env:MAX_STUCK_RETRIES = if ($env:MAX_STUCK_RETRIES) { $env:MAX_STUCK_RETRIES } else { "3" }
$env:STUCK_BACKOFF_SECONDS = if ($env:STUCK_BACKOFF_SECONDS) { $env:STUCK_BACKOFF_SECONDS } else { "15" }
$restartFlag = Join-Path $StatusDir "supervisor_restart.enabled"
$env:SUPERVISOR_RESTART_ENABLED = if (Test-Path $restartFlag) { "true" } else { "false" }
$env:MAX_DAILY_LAUNCHES = if ($env:MAX_DAILY_LAUNCHES) { $env:MAX_DAILY_LAUNCHES } else { "12" }
$env:MAX_ATTEMPTS = if ($env:MAX_ATTEMPTS) { $env:MAX_ATTEMPTS } else { "2" }
$env:MAX_RUN_SECONDS = if ($env:MAX_RUN_SECONDS) { $env:MAX_RUN_SECONDS } else { "5400" }
$env:DEFAULT_BRANCH = if ($env:DEFAULT_BRANCH) { $env:DEFAULT_BRANCH } else { "main" }
$env:SUPERVISOR_LOG_DIR = $LogDir

$bootstrapConfig = [ordered]@{
  schema = "trading-agent-lab.runtime_config.v1"
  repo = $env:GITHUB_REPOSITORY
  branch = $env:DEFAULT_BRANCH
  agent_runtime = $env:AGENT_RUNTIME
  auto_merge_safe = $true
  autonomous_default = $true
  allow_runs = $true
  spend_limit_confirmed = $true
  protection_confirmed = $true
  allow_public_repo = $true
  telegram_optional = $true
  poll_seconds = [int]$env:POLL_SECONDS
  heartbeat_seconds = [int]$env:HEARTBEAT_SECONDS
  stuck_timeout_seconds = [int]$env:STUCK_TIMEOUT_SECONDS
  max_stuck_retries = [int]$env:MAX_STUCK_RETRIES
  stuck_backoff_seconds = [int]$env:STUCK_BACKOFF_SECONDS
  supervisor_restart_enabled = ($env:SUPERVISOR_RESTART_ENABLED -eq "true")
  watchdog_active = $true
  selfheal_enabled = $true
  status_path = $env:RUNTIME_STATUS_PATH
  config_path = $env:RUNTIME_CONFIG_PATH
  supervisor_command = "python -m agentops.supervisor"
  process_name = "python"
  live_trading = $false
  broker_access = $false
  monitoring_policy = @{
    read_secrets_env = $false
    read_only_commands_ok = $true
    no_blocking_tail = $true
    detached_only = $true
  }
}
($bootstrapConfig | ConvertTo-Json -Depth 5) | Set-Content -Path $env:RUNTIME_CONFIG_PATH -Encoding UTF8

$PidFile = Join-Path $Data "supervisor.pid"

if (Test-Path $PidFile) {
  $old = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($old) {
    $proc = Get-Process -Id $old -ErrorAction SilentlyContinue
    if ($proc) {
      if (-not $Restart) {
        Write-Host "DETACHED_ALREADY pid=$old status=$($env:RUNTIME_STATUS_PATH)"
        exit 0
      }
      Stop-Process -Id $old -Force -ErrorAction SilentlyContinue
      Start-Sleep -Milliseconds 400
    }
  }
}

$Py = (Get-Command python -ErrorAction Stop).Source
# Detached: NO RedirectStandardOutput/Error (those locks can hang Cursor forever).
# Child inherits this process environment (including tokens) — never write tokens to disk launchers.
$proc = Start-Process -FilePath $Py `
  -ArgumentList @("-m", "agentops.supervisor") `
  -WorkingDirectory $Root `
  -WindowStyle Hidden `
  -PassThru

if (-not $proc) {
  Write-Host "DETACHED_START_FAILED"
  exit 4
}
Set-Content -Path $PidFile -Value $proc.Id -Encoding ascii

# Tiny alive check only — do not wait for supervisor exit.
Start-Sleep -Milliseconds 400
$alive = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
if (-not $alive) {
  Write-Host "DETACHED_EXITED_EARLY pid=$($proc.Id) status=$($env:RUNTIME_STATUS_PATH)"
  exit 5
}
Write-Host "DETACHED_OK pid=$($proc.Id) status=$($env:RUNTIME_STATUS_PATH)"
exit 0
