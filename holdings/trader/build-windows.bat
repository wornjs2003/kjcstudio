@echo off
rem KJC order computer - Windows build (run once on a Windows PC with Python 3.12+)
rem Result: dist\KJC-order.exe  -- put config.json next to the exe (copy config.example.json)
rem Keys and account go only in config.json on that PC. They are never built into the exe.
chcp 65001 > nul
cd /d "%~dp0"

where python > nul 2>&1
if errorlevel 1 (
  echo Python is not installed. Install Python 3.12 from python.org with "Add to PATH" checked, then run this again.
  pause
  exit /b 2
)

set V=%TEMP%\kjc-trader-build
rem venv and work files stay outside the repo
python -m venv "%V%\venv"
if errorlevel 1 goto fail
call "%V%\venv\Scripts\activate.bat"
python -m pip install --upgrade pip "pyinstaller==6.22.3"
if errorlevel 1 goto fail
python -m unittest discover -s tests -q
if errorlevel 1 goto fail
python -m PyInstaller --noconfirm --windowed --name KJC-order --distpath dist --workpath "%V%\work" --specpath "%V%" run.py
if errorlevel 1 goto fail
copy /y config.example.json dist\config.example.json > nul
echo.
echo Done: %~dp0dist\KJC-order.exe
echo Next: copy dist\config.example.json to dist\config.json and fill it in.
pause
exit /b 0

:fail
echo Build failed. See the messages above.
pause
exit /b 1
