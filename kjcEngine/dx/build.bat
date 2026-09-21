@echo off
rem kjcEngine DirectX 11 build. ASCII only - see CLAUDE.md rule on .bat files.
rem Korean messages belong in the C++ source, not here.

set VS=C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat
if not exist "%VS%" (
  echo.
  echo   Visual Studio C++ tools not found at:
  echo   %VS%
  echo.
  exit /b 1
)

call "%VS%" >nul
cd /d "%~dp0"

cl /nologo /EHsc /std:c++17 /utf-8 /O2 /I. main.cpp model.cpp texture.cpp ibl.cpp panel.cpp font.cpp gputime.cpp third_party\ufbx.c /Fe:kjcEngine.exe ^
   /link /SUBSYSTEM:WINDOWS user32.lib gdi32.lib comctl32.lib
if errorlevel 1 (
  echo.
  echo   BUILD FAILED
  echo.
  exit /b 1
)

del /q *.obj 2>nul
echo   BUILD OK - kjcEngine.exe
