@echo off
chcp 65001 >nul
title KJC Studio - Projects (port 8091)
rem Serve from the repository ROOT: the page pulls ../assets/ and ../partials/.
rem Serving this folder alone makes the colours and the menu 404 (2026-09-14).
rem
rem ASCII ONLY below chcp. cmd re-opens this file and seeks by BYTE offset on
rem every line; chcp 65001 changes that accounting, so non-ASCII text below it
rem can make cmd resume mid-line. 2026-09-16 it printed
rem   '/*' is not recognized as an internal or external command
rem Korean belongs in the Python program, not here (CLAUDE.md).
cd /d "%~dp0.."

set PY=
python --version >nul 2>&1 && set PY=python
if not defined PY py -3 --version >nul 2>&1 && set PY=py -3
if not defined PY (
  echo   [ERROR] Python not found.
  echo   Install from https://www.python.org/downloads/
  pause
  exit /b 1
)

set PORT=8091
set URL=http://localhost:%PORT%/projects/

echo ------------------------------------------------
echo   KJC Studio - Projects
echo ------------------------------------------------
echo.
echo   URL   : %URL%
echo.
echo   Stop  : close this window, or press Ctrl+C
echo ------------------------------------------------
echo.

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

start "" "%URL%"
%PY% -m http.server %PORT%

echo.
echo   Server stopped.
pause
