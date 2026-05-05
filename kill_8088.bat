@echo off
set PORT=8080
echo Finding process on port %PORT%...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr LISTENING ^| findstr :%PORT%') do (
    echo Killing PID: %%a
    taskkill /F /PID %%a
)

echo Task finished.
pause
