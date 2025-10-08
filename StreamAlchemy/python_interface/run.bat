@echo off
REM StreamAlchemy Windows Launcher
REM This script sets up and runs StreamAlchemy on Windows

echo StreamAlchemy Windows Launcher
echo =============================

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Check if FFmpeg is available
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo Error: FFmpeg is not installed or not in PATH
    echo Please install FFmpeg from https://ffmpeg.org
    pause
    exit /b 1
)

REM Free up port 5000 (Windows)
echo Freeing up port 5000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Set up virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create virtual environment
        pause
        exit /b 1
    )
) else (
    echo Virtual environment already exists
)

REM Install dependencies
echo Installing dependencies...
venv\Scripts\pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies
    pause
    exit /b 1
)

REM Run the application
echo Starting StreamAlchemy...
echo Platform: Windows
echo Working directory: %SCRIPT_DIR%
echo.
echo Press Ctrl+C to stop the application
echo.

venv\Scripts\python app.py

echo.
echo StreamAlchemy has stopped
pause
