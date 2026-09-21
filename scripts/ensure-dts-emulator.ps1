# Detached Durable Task Scheduler emulator (Docker). Exits quickly — never blocks Cursor.
# Requires Docker Desktop. If Docker is missing, maf_durable still runs via local checkpoint engine.
param([switch]$Restart)
$ErrorActionPreference = "Stop"

$Name = "dts-emulator"
$Image = "mcr.microsoft.com/dts/dts-emulator:latest"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "DTS_EMULATOR_SKIPPED reason=docker_not_found"
  Write-Host "Install Docker Desktop, then re-run. Until then ORCHESTRATION_BACKEND=maf_durable uses local_checkpoint."
  exit 0
}

$existing = docker ps -a --filter "name=^/${Name}$" --format "{{.ID}} {{.Status}}" 2>$null
if ($existing) {
  if ($Restart) {
    docker rm -f $Name 2>$null | Out-Null
  } else {
    $running = docker ps --filter "name=^/${Name}$" --format "{{.ID}}"
    if ($running) {
      Write-Host "DTS_EMULATOR_ALREADY id=$running dashboard=http://localhost:8082"
      exit 0
    }
    docker start $Name | Out-Null
    Write-Host "DTS_EMULATOR_STARTED name=$Name dashboard=http://localhost:8082"
    exit 0
  }
}

docker pull $Image
docker run -d --name $Name -p 8080:8080 -p 8082:8082 $Image | Out-Null
Write-Host "DTS_EMULATOR_OK name=$Name grpc=http://localhost:8080 dashboard=http://localhost:8082"
exit 0
