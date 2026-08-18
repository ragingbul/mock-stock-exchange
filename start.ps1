# Start both backend + frontend for local PC play (localhost only).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Mock Stock Exchange"
Write-Host "  Terminal: http://localhost:3000/terminal"
Write-Host "  Admin:    http://localhost:3000/admin"
Write-Host "  API:      http://localhost:8000/docs"
Write-Host ""

$backend = Start-Process -PassThru -WindowStyle Normal -FilePath "$root\backend\.venv\Scripts\uvicorn.exe" -ArgumentList @("app.main:app","--host","127.0.0.1","--port","8000","--reload") -WorkingDirectory "$root\backend"
Start-Sleep -Seconds 2
$frontend = Start-Process -PassThru -WindowStyle Normal -FilePath "npm" -ArgumentList @("run","dev") -WorkingDirectory "$root\frontend"

Write-Host "Backend PID $($backend.Id) · Frontend PID $($frontend.Id)"
Write-Host "Press Enter to stop both..."
[void][System.Console]::ReadLine()

Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*mock*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "Stopped."
