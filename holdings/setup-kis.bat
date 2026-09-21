@echo off
chcp 65001 >nul
title KJC Holdings - KIS API key setup
cd /d "%~dp0"

rem ASCII only. Korean text breaks cmd after chcp - see CLAUDE.md
rem Find python (python -> py -3)
set PY=
python --version >nul 2>&1 && set PY=python
if not defined PY py -3 --version >nul 2>&1 && set PY=py -3
if not defined PY (
  echo   [error] Python not found.
  echo.
  echo   Install from https://www.python.org/downloads/
  echo   Check "Add python.exe to PATH" during setup.
  echo.
  pause
  exit /b 1
)

%PY% "server\setup_kis.py"

echo.
pause
