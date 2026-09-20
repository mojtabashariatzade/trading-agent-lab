# Local PC control-plane launcher (Windows). Does not enable live trading.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Data = Join-Path $env:LOCALAPPDATA "trading-agent-lab"
$StateDir = Join-Path $Data "state"
$Secrets = Join-Path $Data "secrets.env"
$LogDir = Join-Path $Data "logs"
New-Item -ItemType Directory -Force -Path $StateDir, $LogDir | Out-Null

$env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User')

if (-not (Test-Path $Secrets)) {
  @"
# Local secrets — NEVER commit this file. NEVER paste tokens into chat.
GITHUB_REPOSITORY=mojtabashariatzade/trading-agent-lab
GITHUB_TOKEN=
CURSOR_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CONTROL_CHAT_ID=
TELEGRAM_OWNER_IDS=
TELEGRAM_REPORT_CHAT_ID=
ALLOW_AGENT_RUNS=false
SPEND_LIMIT_CONFIRMED=false
REPOSITORY_PROTECTION_CONFIRMED=false
MAX_DAILY_LAUNCHES=4
MAX_ATTEMPTS=2
MAX_RUN_SECONDS=5400
POLL_SECONDS=30
DEFAULT_BRANCH=main
"@ | Set-Content -Path $Secrets -Encoding UTF8
  Write-Host "Created secrets template: $Secrets"
  Write-Host "Fill TELEGRAM_* and CURSOR_API_KEY, then re-run this script."
  notepad $Secrets
  exit 2
}

# Load KEY=VALUE lines (no export of values to console)
Get-Content $Secrets | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#")) { return }
  $i = $line.IndexOf("=")
  if ($i -lt 1) { return }
  $k = $line.Substring(0, $i).Trim()
  $v = $line.Substring($i + 1).Trim()
  Set-Item -Path "Env:$k" -Value $v
}

# Prefer live gh token when secret blank (never print token)
if (-not $env:GITHUB_TOKEN) {
  $tok = & gh auth token 2>$null
  if ($LASTEXITCODE -eq 0 -and $tok) { $env:GITHUB_TOKEN = $tok }
}
$env:STATE_PATH = Join-Path $StateDir "team.sqlite3"
$env:GITHUB_REPOSITORY = if ($env:GITHUB_REPOSITORY) { $env:GITHUB_REPOSITORY } else { "mojtabashariatzade/trading-agent-lab" }

$missing = @()
foreach ($name in @("GITHUB_TOKEN","CURSOR_API_KEY","TELEGRAM_BOT_TOKEN","TELEGRAM_CONTROL_CHAT_ID","TELEGRAM_OWNER_IDS")) {
  $val = [Environment]::GetEnvironmentVariable($name)
  if ([string]::IsNullOrWhiteSpace($val)) { $missing += $name }
}
if ($missing.Count -gt 0) {
  Write-Host "Missing required secrets: $($missing -join ', ')"
  Write-Host "Edit: $Secrets"
  notepad $Secrets
  exit 3
}

# Refuse to start paid cloud launches unless owner flipped flags in secrets.env
Write-Host "Starting local control plane (paused until /resume). ALLOW_AGENT_RUNS=$($env:ALLOW_AGENT_RUNS)"
Write-Host "State: $($env:STATE_PATH)"
Write-Host "Repo: $($env:GITHUB_REPOSITORY)"
Set-Location $Root
python -m agentops
