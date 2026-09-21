# Detached durable worker companion for ORCHESTRATION_BACKEND=maf_durable.
# Does NOT replace the legacy supervisor. Does NOT enable live trading.
param([switch]$Restart)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Data = Join-Path $env:LOCALAPPDATA "trading-agent-lab"
$LogDir = Join-Path $Data "logs"
$StatusDir = Join-Path $Data "status"
New-Item -ItemType Directory -Force -Path $LogDir, $StatusDir | Out-Null

$PidFile = Join-Path $Data "durable_worker.pid"
if (Test-Path $PidFile) {
  $old = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($old) {
    $proc = Get-Process -Id $old -ErrorAction SilentlyContinue
    if ($proc) {
      if (-not $Restart) {
        Write-Host "DURABLE_WORKER_ALREADY pid=$old"
        exit 0
      }
      Stop-Process -Id $old -Force -ErrorAction SilentlyContinue
      Start-Sleep -Milliseconds 300
    }
  }
}

# Best-effort emulator (no-op without Docker).
& "$PSScriptRoot\ensure-dts-emulator.ps1" | Out-Host

$env:ORCHESTRATION_BACKEND = if ($env:ORCHESTRATION_BACKEND) { $env:ORCHESTRATION_BACKEND } else { "maf_durable" }
$env:DTS_ENDPOINT = if ($env:DTS_ENDPOINT) { $env:DTS_ENDPOINT } else { "http://localhost:8080" }
$env:DTS_TASK_HUB = if ($env:DTS_TASK_HUB) { $env:DTS_TASK_HUB } else { "default" }
$env:AGENT_RUNTIME = if ($env:AGENT_RUNTIME) { $env:AGENT_RUNTIME } else { "local" }
$env:TELEGRAM_OPTIONAL = "true"
$env:DURABLE_WORKER_HEARTBEAT = Join-Path $StatusDir "durable_worker.heartbeat"

# Inherit secrets if present (same pattern as supervisor) — never print tokens.
$Secrets = Join-Path $Data "secrets.env"
if (Test-Path $Secrets) {
  Get-Content $Secrets | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $i = $line.IndexOf("=")
    if ($i -lt 1) { return }
    $k = $line.Substring(0, $i).Trim()
    $v = $line.Substring($i + 1).Trim()
    if (-not [Environment]::GetEnvironmentVariable($k)) {
      Set-Item -Path "Env:$k" -Value $v
    }
  }
}
if (-not $env:GITHUB_TOKEN) {
  $tok = & gh auth token 2>$null
  if ($LASTEXITCODE -eq 0 -and $tok) { $env:GITHUB_TOKEN = $tok }
}
$env:GITHUB_REPOSITORY = if ($env:GITHUB_REPOSITORY) { $env:GITHUB_REPOSITORY } else { "mojtabashariatzade/trading-agent-lab" }
$env:STATE_PATH = if ($env:STATE_PATH) { $env:STATE_PATH } else { (Join-Path $Data "state\team.sqlite3") }

$Py = (Get-Command python -ErrorAction Stop).Source
$proc = Start-Process -FilePath $Py `
  -ArgumentList @("-m", "agentops.durable_worker") `
  -WorkingDirectory $Root `
  -WindowStyle Hidden `
  -PassThru

if (-not $proc) {
  Write-Host "DURABLE_WORKER_START_FAILED"
  exit 4
}
Set-Content -Path $PidFile -Value $proc.Id -Encoding ascii
Start-Sleep -Milliseconds 400
if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) {
  Write-Host "DURABLE_WORKER_EXITED_EARLY pid=$($proc.Id)"
  exit 5
}
Write-Host "DURABLE_WORKER_OK pid=$($proc.Id) backend=$($env:ORCHESTRATION_BACKEND)"
exit 0
