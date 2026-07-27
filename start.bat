@echo off
title Aura AI — Starting...
color 0B
echo.
echo  =====================================================
echo   Aura AI  ^|  Starting...
echo  =====================================================
echo.

REM Kill any old backend instances first
taskkill /F /IM pythonw.exe /FI "WINDOWTITLE eq Aura*" >nul 2>&1
timeout /t 1 /nobreak >nul

echo  [1/2] Starting backend server...
cd /d "%~dp0backend"
start "AuraBackend" pythonw main.py
cd /d "%~dp0"

echo  [   ] Waiting for backend to be ready (up to 15s)...
REM Wait for backend HTTP to respond
set /a tries=0
:WAIT_LOOP
timeout /t 1 /nobreak >nul
curl -s --max-time 1 http://localhost:8000/ >nul 2>&1
if %errorlevel%==0 goto BACKEND_READY
set /a tries+=1
if %tries% lss 18 goto WAIT_LOOP

:BACKEND_READY
echo  [2/2] Starting overlay HUD...
cd /d "%~dp0overlay"
start "AuraHUD" pythonw hud.py
cd /d "%~dp0"

echo.
echo  =====================================================
echo   Aura AI is running!
echo.
echo   - Hotkey: Ctrl+Shift+Space to show/hide
echo   - Voice:  Alt+Space  OR  click the mic button
echo   - Wake:   Say "Hey Aura" (enable in Settings)
echo   - API:    Click gear icon to set Gemini key
echo.
echo   Get free key: aistudio.google.com
echo  =====================================================
echo.
timeout /t 4 /nobreak >nul
exit
