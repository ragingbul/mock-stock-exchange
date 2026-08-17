# Stop TRADEVERSE local LAN stack (preserves database volume).
$ErrorActionPreference = "Stop"

$RootDir = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $RootDir

docker compose -f docker-compose.local.yml down
Write-Host "Stopped. Database volume postgres_data_local preserved."
