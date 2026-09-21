@echo off
chcp 65001 >nul
title KJC Holdings - Dashboard (port 8765)
cd /d "%~dp0holdings"

rem detect python (python -> py -3)
set PY=
python --version >nul 2>&1 && set PY=python
if not defined PY py -3 --version >nul 2>&1 && set PY=py -3
if not defined PY (
  echo   [error] Python not found.
  echo.
  echo   Install it from https://www.python.org/downloads/
  echo   Be sure to check "Add python.exe to PATH" during install.
  echo.
  pause
  exit /b 1
)

set PORT=8765
set URL=http://localhost:%PORT%/holdings/

echo ------------------------------------------------
echo   KJC Holdings - Stock Dashboard
echo ------------------------------------------------
echo.
echo   Dashboard : %URL%
echo   Analysis  : %URL%analysis/
echo   Roadmap   : %URL%roadmap.html
echo.
echo   Stop : close this window or Ctrl+C
echo ------------------------------------------------
echo.

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

start "" "%URL%"
%PY% -m http.server %PORT%

echo.
echo   Server stopped.
pause
