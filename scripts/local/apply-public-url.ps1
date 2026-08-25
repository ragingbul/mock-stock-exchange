# Write a public base URL (ngrok / LAN) into .env and restart backend + nginx.
# Usage: .\scripts\local\apply-public-url.ps1 https://abc123.ngrok-free.dev

$ErrorActionPreference = "Stop"

$RootDir = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $RootDir

if ($args.Count -lt 1 -or [string]::IsNullOrWhiteSpace($args[0])) {
    Write-Error "Usage: .\scripts\local\apply-public-url.ps1 https://YOUR-ID.ngrok-free.dev"
}

$publicUrl = $args[0].TrimEnd("/")

if (-not (Test-Path ".env")) {
    Write-Error "Missing .env"
}

$lines = Get-Content ".env"
$corsLine = $lines | Where-Object { $_ -match "^CORS_ORIGINS=" } | Select-Object -First 1
$existing = @()
if ($corsLine) {
    $existing = ($corsLine -replace "^CORS_ORIGINS=", "").Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}

$origins = New-Object "System.Collections.Generic.List[string]"
foreach ($o in (@("http://localhost", "http://127.0.0.1") + $existing + @($publicUrl))) {
    if (-not $origins.Contains($o)) {
        $origins.Add($o) | Out-Null
    }
}

if ($publicUrl -match "ngrok") {
    $filtered = New-Object "System.Collections.Generic.List[string]"
    foreach ($o in $origins) {
        if ($o -eq $publicUrl -or $o -notmatch "ngrok") {
            $filtered.Add($o) | Out-Null
        }
    }
    if (-not $filtered.Contains($publicUrl)) {
        $filtered.Add($publicUrl) | Out-Null
    }
    $origins = $filtered
}

function Set-EnvKey([string[]]$content, [string]$key, [string]$value) {
    $found = $false
    $out = foreach ($line in $content) {
        if ($line -match ("^" + [regex]::Escape($key) + "=")) {
            $found = $true
            "$key=$value"
        } else {
            $line
        }
    }
    if (-not $found) {
        $out = @($out) + "$key=$value"
    }
    return $out
}

$corsValue = ($origins -join ",")
$lines = Set-EnvKey $lines "CORS_ORIGINS" $corsValue
$lines = Set-EnvKey $lines "FRONTEND_URL" $publicUrl
$lines = Set-EnvKey $lines "BACKEND_URL" $publicUrl

$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllLines((Join-Path (Get-Location) ".env"), $lines, $utf8NoBom)

Write-Host "Updated .env CORS / FRONTEND_URL / BACKEND_URL -> $publicUrl"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Updated .env, but docker was not found - start Docker Desktop, then run:"
    Write-Host "  docker compose -f docker-compose.local.yml restart backend nginx"
    exit 0
}

$Compose = "docker compose -f docker-compose.local.yml"
Write-Host "==> Restart backend + nginx (pick up new CORS / URLs)"
Invoke-Expression "$Compose up -d nginx" | Out-Null
Invoke-Expression "$Compose restart backend nginx"

Write-Host "Done. Leave NEXT_PUBLIC_API_URL and NEXT_PUBLIC_WS_URL empty (same-origin)."
