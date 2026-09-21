@echo off
chcp 65001 >nul
title KJC Studio - Main Site (port 8080)
cd /d "%~dp0"

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

set PORT=8080
set URL=http://localhost:%PORT%/

echo ------------------------------------------------
echo   KJC Studio - Main Site
echo ------------------------------------------------
echo.
echo   URL  : %URL%
echo.
echo   Stop : close this window or Ctrl+C
echo ------------------------------------------------
echo.

rem kill any previous server on the same port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

start "" "%URL%"
%PY% -m http.server %PORT%

echo.
echo   Server stopped.
pause
