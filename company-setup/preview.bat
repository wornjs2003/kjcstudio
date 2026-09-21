@echo off
chcp 65001 >nul
title KJC Studio - Company Setup (port 8090)
rem Serve from the repo root: the page also uses ../assets/ and ../partials/.
rem Serving only this folder makes colors and the menu 404 (2026-09-14).
cd /d "%~dp0.."

set PY=
python --version >nul 2>&1 && set PY=python
if not defined PY py -3 --version >nul 2>&1 && set PY=py -3
if not defined PY (
  echo   [error] Python not found.
  echo   Install it from https://www.python.org/downloads/
  pause
  exit /b 1
)

set PORT=8090
set URL=http://localhost:%PORT%/company-setup/

echo ------------------------------------------------
echo   KJC Studio - Company Setup
echo ------------------------------------------------
echo.
echo   URL  : %URL%
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
