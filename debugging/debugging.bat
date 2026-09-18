@echo off
chcp 65001 >nul
title KJC Studio - Debugging (port 8093)

rem Run from this folder. server.py works out the repository root itself,
rem which it needs because the page pulls ../assets/ and ../partials/.
rem
rem ASCII ONLY below chcp. cmd re-opens this file and seeks by BYTE offset on
rem every line; chcp 65001 changes that accounting, so non-ASCII text below it
rem can make cmd resume mid-line. 2026-09-16 it printed
rem   '/*' is not recognized as an internal or external command
rem Korean belongs in the Python program, not here (CLAUDE.md).
cd /d "%~dp0"

set PY=
python --version >nul 2>&1 && set PY=python
if not defined PY py -3 --version >nul 2>&1 && set PY=py -3
if not defined PY (
  echo   [ERROR] Python not found.
  echo   Install from https://www.python.org/downloads/
  pause
  exit /b 1
)

rem Clear out a server still holding the port from a previous run
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8093" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

%PY% server.py

echo.
echo   Server stopped.
pause
