@echo off
title Aura AI
color 0B
echo.
echo  =====================================================
echo   Aura AI  ^|  Starting...
echo  =====================================================
echo.
echo  Starting backend server...
cd /d "%~dp0backend"
start "" pythonw main.py
cd /d "%~dp0"

REM Wait for backend to start
timeout /t 3 /nobreak >nul

echo  Starting overlay HUD...
cd /d "%~dp0overlay"
start "" pythonw hud.py
cd /d "%~dp0"

echo.
echo  =====================================================
echo   App is running!
echo.
echo   - Overlay: visible on screen (invisible in share)
echo   - Hotkey: Ctrl+Shift+Space to show/hide overlay
echo   - To set API key: click the gear icon in the overlay
echo.
echo   Get your free API key:
echo   https://aistudio.google.com
echo  =====================================================
echo.
timeout /t 5 /nobreak >nul
exit
