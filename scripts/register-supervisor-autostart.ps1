# Registers Windows auto-restart for the local supervisor (current-user Task Scheduler).
# Falls back to a Startup-folder watcher if Task Scheduler registration is denied.
# Does not read secrets for monitoring. Does not enable live trading.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Data = Join-Path $env:LOCALAPPDATA "trading-agent-lab"
$Starter = Join-Path $PSScriptRoot "start-supervisor.ps1"
$TaskName = "TradingAgentLab-Supervisor"
$StatusDir = Join-Path $Data "status"
$LogDir = Join-Path $Data "logs"
New-Item -ItemType Directory -Force -Path $StatusDir, $LogDir | Out-Null

if (-not (Test-Path $Starter)) {
  throw "Missing start script: $Starter"
}

$registered = $false
try {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$Starter`""
  $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg -WorkingDirectory $Root
  $triggerLogon = New-ScheduledTaskTrigger -AtLogOn
  $triggerRepeat = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
  $settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
  $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($triggerLogon, $triggerRepeat) `
    -Settings $settings -Principal $principal -Description "Auto-restart trading-agent-lab supervisor if it is not running" | Out-Null
  $registered = $true
  Write-Host "Scheduled task registered: $TaskName"
  Write-Host "Triggers: AtLogOn + every 5 minutes; on-failure restart count=3"
} catch {
  Write-Host "Task Scheduler registration denied or failed: $($_.Exception.Message)"
  Write-Host "Installing Startup-folder fallback watcher instead."
  $startup = [Environment]::GetFolderPath("Startup")
  $watcher = Join-Path $startup "TradingAgentLab-Supervisor.cmd"
  $cmd = @"
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "$Starter"
"@
  Set-Content -Path $watcher -Value $cmd -Encoding ASCII
  Write-Host "Startup watcher installed: $watcher"
  $registered = $true
}

$flagFile = Join-Path $StatusDir "supervisor_restart.enabled"
Set-Content -Path $flagFile -Value "true" -Encoding ascii
Write-Host "supervisor restart enabled"
if (-not $registered) { exit 1 }
exit 0
