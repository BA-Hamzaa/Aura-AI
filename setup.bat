@echo off
title AI Meeting Assistant — Setup
color 0B
echo.
echo  =====================================================
echo   AI Meeting Assistant — First-Time Setup
echo  =====================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is not installed!
    echo  Please download from: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH"
    pause
    exit /b 1
)
echo  [OK] Python found

REM Install pip packages
echo.
echo  Installing Python packages...
echo  (This may take a few minutes the first time)
echo.
pip install -r "%~dp0backend\requirements.txt" --quiet

echo.
echo  [OK] All packages installed
echo.
echo  =====================================================
echo   Setup complete! Run start.bat to launch the app.
echo  =====================================================
echo.
pause
