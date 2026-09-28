@echo off
setlocal
cd /d "%~dp0"
title QA Status Dashboard

echo ==========================================
echo   QA Status Dashboard - V24 + V32
echo ==========================================
echo.

if not exist ".env" (
    echo ERROR: .env was not found.
    echo Create .env and add:
    echo AZURE_PAT=YOUR_REAL_PAT
    echo.
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found in PATH.
    pause
    exit /b 1
)

python -c "import requests, dotenv" >nul 2>nul
if errorlevel 1 (
    echo Installing required Python packages...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Could not install Python requirements.
        pause
        exit /b 1
    )
)

echo Checking configuration and updating dashboard...
echo.
python QA_Status_Dashboard.py
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo ==========================================
    echo Dashboard was NOT updated.
    echo Fix the error shown above, then run again.
    echo Exit code: %RC%
    echo ==========================================
    pause
    exit /b %RC%
)

if not exist "QA_Status_Dashboard.html" (
    echo ERROR: Dashboard HTML was not generated.
    pause
    exit /b 10
)

echo.
echo Opening the updated dashboard...
start "" "%~dp0QA_Status_Dashboard.html"
exit /b 0
