# Create .env from .env.local.example with generated secrets (idempotent if .env exists).

$ErrorActionPreference = "Stop"

$RootDir = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $RootDir

if (Test-Path ".env") {
    Write-Host ".env already exists - leaving it unchanged."
    Write-Host "Edit CORS_ORIGINS / FRONTEND_URL / BACKEND_URL as needed."
    exit 0
}

if (-not (Test-Path ".env.local.example")) {
    Write-Error "Missing .env.local.example"
}

Copy-Item ".env.local.example" ".env"

function New-Secret([int]$bytes = 24) {
    $buf = New-Object byte[] $bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buf)
    return [Convert]::ToBase64String($buf).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Set-EnvKeyInFile([string]$key, [string]$value) {
    $lines = Get-Content ".env"
    $found = $false
    $out = foreach ($line in $lines) {
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
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines((Join-Path (Get-Location) ".env"), $out, $utf8NoBom)
}

$pg = New-Secret 24
$jwt = New-Secret 32
$admin = New-Secret 18

Set-EnvKeyInFile "POSTGRES_PASSWORD" $pg
Set-EnvKeyInFile "JWT_SECRET" $jwt
Set-EnvKeyInFile "ADMIN_SECRET" $admin
Set-EnvKeyInFile "CORS_ORIGINS" "http://localhost,http://127.0.0.1"
Set-EnvKeyInFile "FRONTEND_URL" "http://localhost"
Set-EnvKeyInFile "BACKEND_URL" "http://localhost"

Write-Host "Created .env with generated POSTGRES_PASSWORD, JWT_SECRET, ADMIN_SECRET."
Write-Host "ADMIN_SECRET=$admin"
Write-Host "Save the admin secret - you need it for /admin."
