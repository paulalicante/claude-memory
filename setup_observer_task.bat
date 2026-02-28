@echo off
REM Setup Windows Scheduled Task for Otterly Memory Observer
REM Runs daily at midnight to create observations
REM Runs weekly (Sundays) at 1am to create reflections

echo Setting up Otterly Memory Observer scheduled tasks...

REM Daily observation task - runs at midnight
schtasks /create /tn "Otterly Memory - Daily Observer" /tr "C:\Python314\python.exe \"G:\My Drive\MyProjects\ClaudeMemory\claude_memory\observer.py\" observe" /sc daily /st 00:00 /f

REM Weekly reflection task - runs Sunday at 1am
schtasks /create /tn "Otterly Memory - Weekly Reflection" /tr "C:\Python314\python.exe \"G:\My Drive\MyProjects\ClaudeMemory\claude_memory\observer.py\" reflect" /sc weekly /d SUN /st 01:00 /f

echo.
echo Tasks created:
echo   - "Otterly Memory - Daily Observer" runs every day at midnight
echo   - "Otterly Memory - Weekly Reflection" runs every Sunday at 1am
echo.
echo To view tasks: schtasks /query /tn "Otterly Memory*"
echo To run now: schtasks /run /tn "Otterly Memory - Daily Observer"
echo To delete: schtasks /delete /tn "Otterly Memory - Daily Observer" /f

pause
