# Cursor-safe entry: start detached supervisor if needed, print snapshot, exit immediately.
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
& (Join-Path $here "start-supervisor.ps1")
$code = $LASTEXITCODE
if ($code -notin 0, 4, 5) { exit $code }
& (Join-Path $here "check-supervisor-status.ps1")
exit $LASTEXITCODE
