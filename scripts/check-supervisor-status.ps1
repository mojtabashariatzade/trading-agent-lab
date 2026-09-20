# Finite snapshot only. Never Get-Content -Wait / tail -f. Never blocks Cursor.
$ErrorActionPreference = "Stop"
$Data = Join-Path $env:LOCALAPPDATA "trading-agent-lab"
$StatusFile = Join-Path $Data "status\runtime_status.json"
$ConfigFile = Join-Path $Data "status\runtime_config.json"
$PidFile = Join-Path $Data "supervisor.pid"
$ErrLog = Join-Path $Data "logs\supervisor.err.log"

Write-Host "=== Supervisor snapshot (detached check; no follow/tail) ==="
if (Test-Path $StatusFile) {
  Get-Content $StatusFile -TotalCount 80
} else {
  Write-Host "runtime_status.json: missing"
}
if (Test-Path $ConfigFile) {
  Write-Host "--- config keys (truncated) ---"
  Get-Content $ConfigFile -TotalCount 40
}

$alive = $false
$pidVal = $null
if (Test-Path $PidFile) {
  $pidVal = (Get-Content $PidFile -TotalCount 1)
  if ($pidVal) {
    $proc = Get-Process -Id ([int]$pidVal) -ErrorAction SilentlyContinue
    if ($proc) { $alive = $true; Write-Host "Process: $($proc.ProcessName) PID=$($proc.Id) alive=true" }
    else { Write-Host "Process: pidfile=$pidVal alive=false" }
  }
}
if (Test-Path $ErrLog) {
  Write-Host "--- err.log last 8 lines ---"
  Get-Content $ErrLog -Tail 8
}
if (-not $alive) {
  Write-Host "Verdict: NOT_RUNNING"
  exit 1
}
Write-Host "Verdict: DETACHED_ALIVE"
exit 0
