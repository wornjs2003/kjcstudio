@echo off
rem kjcEngine launcher. ASCII only - see CLAUDE.md rule on .bat files.
rem Korean messages belong in main.py, not here.

cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
  python main.py
  goto :done
)

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 main.py
  goto :done
)

echo.
echo   Python 3 not found. Install it from https://www.python.org/downloads/
echo   and tick "Add python.exe to PATH" during setup.
echo.
pause

:done
