param(
    [string]$Repo = "mojtabashariatzade/trading-agent-lab"
)

$ErrorActionPreference = "Stop"
$SecretsPath = Join-Path $env:LOCALAPPDATA "trading-agent-lab\secrets.env"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is required."
}
& gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI is not authenticated."
}
if (-not (Test-Path $SecretsPath)) {
    throw "Local Telegram secrets file not found: $SecretsPath"
}

$values = @{}
Get-Content $SecretsPath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $i = $line.IndexOf("=")
    if ($i -lt 1) { return }
    $k = $line.Substring(0, $i).Trim()
    $v = $line.Substring($i + 1).Trim()
    $values[$k] = $v
}

$token = [string]$values["TELEGRAM_BOT_TOKEN"]
$owners = [string]$values["TELEGRAM_OWNER_IDS"]
$chat = [string]$values["TELEGRAM_CONTROL_CHAT_ID"]
$owner = ($owners -split ",")[0].Trim()

if (-not $token -or -not $owner -or -not $chat) {
    throw "TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_IDS and TELEGRAM_CONTROL_CHAT_ID must already exist locally."
}

Write-Host "Uploading Telegram relay secrets to GitHub Actions without printing their values..."
$token | & gh secret set TELEGRAM_BOT_TOKEN --repo $Repo
if ($LASTEXITCODE -ne 0) { throw "Failed to set TELEGRAM_BOT_TOKEN" }
$owner | & gh secret set TELEGRAM_OWNER_ID --repo $Repo
if ($LASTEXITCODE -ne 0) { throw "Failed to set TELEGRAM_OWNER_ID" }
$chat | & gh secret set TELEGRAM_CHAT_ID --repo $Repo
if ($LASTEXITCODE -ne 0) { throw "Failed to set TELEGRAM_CHAT_ID" }

Write-Host "Secrets uploaded."
Write-Host "After the telegram-cloud-relay workflow is merged to main, run:"
Write-Host "  gh workflow run telegram-cloud-relay.yml --repo $Repo"
Write-Host ""
Write-Host "Important: once cloud relay is active, the same Telegram bot should have only one getUpdates consumer."
Write-Host "The local Telegram poller should be disabled to avoid competing offsets."
