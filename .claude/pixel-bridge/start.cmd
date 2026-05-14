@echo off
:: Pixel Bridge — Auto-start script for Windows
:: Starts the standalone server if not already running

set PIXEL_DIR=%USERPROFILE%\.claude\pixel-bridge\standalone
set PID_FILE=%USERPROFILE%\.pixel-agents\server.pid
set LOG_FILE=%USERPROFILE%\.pixel-agents\server.log
set PORT=3456

if not exist "%USERPROFILE%\.pixel-agents" mkdir "%USERPROFILE%\.pixel-agents"

:: Check if port is in use
netstat -ano 2>nul | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    exit /b 0
)

:: Check if dist\server.js exists
if not exist "%PIXEL_DIR%\dist\server.js" (
    exit /b 0
)

:: Start server in background
cd /d "%PIXEL_DIR%"
start /b "" node dist\server.js >> "%LOG_FILE%" 2>&1
exit /b 0
