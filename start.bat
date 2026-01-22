@echo off
cd /d "%~dp0"
start /B pythonw run.pyw
echo Claude Memory is starting...
timeout /t 2 /nobreak >nul
echo Done! Check your system tray for the icon.
echo Press any key to close this window...
pause >nul
