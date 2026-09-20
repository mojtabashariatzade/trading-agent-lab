# Delegates to the Cursor-safe detached ensure script (exits immediately).
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "ensure-supervisor.ps1")
exit $LASTEXITCODE
