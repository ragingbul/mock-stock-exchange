# Health check via nginx on port 80.
$ErrorActionPreference = "Stop"

$Url = if ($env:HEALTH_URL) { $env:HEALTH_URL } else { "http://127.0.0.1/api/v1/health" }
Write-Host "==> GET $Url"
Invoke-RestMethod -Uri $Url | ConvertTo-Json
