# Expose the local TRADEVERSE stack (nginx :80) via ngrok and wire CORS/.env.
# Prerequisites: Docker stack running (scripts/local/start.ps1), ngrok installed + authed.
# Usage: .\scripts\local\share.ps1

$ErrorActionPreference = "Stop"

$RootDir = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $RootDir

if ($env:NGROK_API) {
    $NgrokApi = $env:NGROK_API
} else {
    $NgrokApi = "http://127.0.0.1:4040/api/tunnels"
}

if ($env:HEALTH_URL) {
    $HealthUrl = $env:HEALTH_URL
} else {
    $HealthUrl = "http://127.0.0.1/api/v1/health"
}

if (-not (Test-Path ".env")) {
    Write-Error "Missing .env - run .\scripts\local\setup-env.ps1 first."
}

$ngrokCmd = Get-Command ngrok -ErrorAction SilentlyContinue
if (-not $ngrokCmd) {
    Write-Error "ngrok not found on PATH. Install from https://ngrok.com/download and run: ngrok config add-authtoken <token>"
}

Write-Host "==> Check local stack health"
try {
    Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 5 | Out-Null
} catch {
    Write-Error "Local stack is not healthy at $HealthUrl. Start it first: .\scripts\local\start.ps1"
}

function Get-NgrokPublicUrl {
    try {
        $data = Invoke-RestMethod -Uri $NgrokApi -TimeoutSec 2
        $https = $data.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1
        if ($https) { return $https.public_url }
        $http = $data.tunnels | Where-Object { $_.public_url -like "http://*" } | Select-Object -First 1
        if ($http) { return $http.public_url }
    } catch {
        return $null
    }
    return $null
}

$publicUrl = Get-NgrokPublicUrl
if (-not $publicUrl) {
    Write-Host "==> Starting ngrok http 80"
    $logPath = Join-Path $env:TEMP "tradeverse-ngrok.log"
    Start-Process -FilePath "ngrok" -ArgumentList @("http", "80", "--log=stdout") -RedirectStandardOutput $logPath -WindowStyle Hidden
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        $publicUrl = Get-NgrokPublicUrl
        if ($publicUrl) { break }
    }
}

if (-not $publicUrl) {
    Write-Error "Could not get ngrok public URL. Run 'ngrok http 80' manually, then: .\scripts\local\apply-public-url.ps1 https://YOUR-ID.ngrok-free.dev"
}

Write-Host "==> ngrok public URL: $publicUrl"
& "$PSScriptRoot\apply-public-url.ps1" $publicUrl

Write-Host ""
Write-Host "Share these links:"
Write-Host "  Terminal:  $publicUrl/terminal"
Write-Host "  Admin:     $publicUrl/admin"
Write-Host "  Screen:    $publicUrl/market-screen"
Write-Host "  Health:    $publicUrl/api/v1/health"
Write-Host ""
Write-Host "Keep this laptop awake. Stop stack: .\scripts\local\stop.ps1"
