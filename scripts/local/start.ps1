# Start TRADEVERSE local LAN stack (HTTP port 80 via nginx).
$ErrorActionPreference = "Stop"

$RootDir = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $RootDir

$Compose = "docker compose -f docker-compose.local.yml"

if (-not (Test-Path ".env")) {
    Write-Error "Missing .env - copy .env.local.example to .env and configure."
}

Write-Host "==> Build images"
Invoke-Expression "$Compose build"

Write-Host "==> Start postgres"
Invoke-Expression "$Compose up -d postgres"

Write-Host "==> Wait for postgres"
do {
    Start-Sleep -Seconds 2
    $ready = Invoke-Expression "$Compose exec -T postgres pg_isready -U mse -d mock_stock_exchange" 2>$null
} while ($LASTEXITCODE -ne 0)

Write-Host "==> Run migrations"
Invoke-Expression "$Compose run --rm backend alembic upgrade head"

Write-Host "==> Start all services"
Invoke-Expression "$Compose up -d"

Write-Host ""
Write-Host "TRADEVERSE is running."
Write-Host "  Localhost:  http://localhost/terminal"
Write-Host "  LAN:        http://YOUR_LAN_IP/terminal  (find IP: ipconfig)"
$frontendUrl = (Get-Content .env | Where-Object { $_ -match '^FRONTEND_URL=' } | ForEach-Object { $_ -replace '^FRONTEND_URL=', '' }).Trim()
if ($frontendUrl -like "https://*") {
    Write-Host "  ngrok:      $frontendUrl/terminal"
}
Write-Host "  Admin:      http://localhost/admin"
Write-Host "  Health:     http://localhost/api/v1/health"
Write-Host ""
Write-Host "For ngrok: run 'ngrok http 80' in another terminal (tunnel must point to port 80)."
Write-Host "Run scripts/local/health-check.ps1 to verify."
