@echo off
chcp 65001 >nul
title KJC Studio - Refresh Works
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

echo ------------------------------------------------
echo   Scanning work images and refreshing the list
echo ------------------------------------------------
echo.

%PY% tools\refresh-works.py

echo.
if %ERRORLEVEL%==0 (
  echo   Done. Reload the browser ^(Ctrl+Shift+R^)
) else (
  echo   Something went wrong. See the message above.
)
echo.
pause
