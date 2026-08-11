@echo off
title Mock Stock Exchange
cd /d "%~dp0"

echo Starting Mock Stock Exchange...
echo.
echo Terminal:  http://localhost:3000/terminal
echo Admin:     http://localhost:3000/admin
echo API docs:  http://localhost:8000/docs
echo.
echo Keep this window open. Press Ctrl+C to stop both servers.
echo.

start "MSE Backend" cmd /k "cd /d "%~dp0backend" && .\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 3 /nobreak >nul
start "MSE Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo Servers launching in separate windows.
echo Open http://localhost:3000/terminal when ready.
pause
