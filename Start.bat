@echo off
chcp 65001 >nul 2>&1
title ComfyUI XMP Tagger - Setup and Launch

echo.
echo ======================================================
echo   ComfyUI XMP Tagger - Setup ^& Launch
echo ======================================================
echo.

REM Check if Python is available on PATH
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERROR] Python was not found on this system.
    echo.
    echo   Please install Python 3.10 or newer from:
    echo   https://www.python.org/downloads/
    echo.
    echo   IMPORTANT: During installation, check the box
    echo   "Add Python to PATH" before clicking Install Now.
    echo.
    echo   This browser page will open for you:
    start https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Run setup.py which checks/installs dependencies and launches the app
python setup.py

REM If setup.py exited with an error, keep the window open
if %errorlevel% neq 0 (
    echo.
    echo   Setup did not complete successfully.
    echo   Please read the message above.
    echo.
    pause
    exit /b 1
)

exit /b 0
