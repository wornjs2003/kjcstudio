@echo off
rem Launch kjcEngine. Builds first if the exe is missing.
cd /d "%~dp0"
if not exist kjcEngine.exe call build.bat
if not exist kjcEngine.exe exit /b 1
start "" kjcEngine.exe
