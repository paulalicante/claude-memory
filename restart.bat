@echo off
REM Find and kill Claude Memory process by HTTP server port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765" ^| findstr LISTENING') do (
    echo Stopping Claude Memory (PID %%a)...
    TASKKILL /F /PID %%a >nul 2>&1
)

timeout /t 1 /nobreak >nul

echo Starting Claude Memory...
cd /d "%~dp0"
start /B pythonw run.pyw

echo Done! Claude Memory is restarting...
timeout /t 2 /nobreak >nul
