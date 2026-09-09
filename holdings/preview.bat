@echo off
chcp 65001 >nul
title KJC Holdings - 독립 실행 (포트 8765)
cd /d "%~dp0"

rem 파이썬 탐지 (python -> py -3 순서)
set PY=
python --version >nul 2>&1 && set PY=python
if not defined PY py -3 --version >nul 2>&1 && set PY=py -3
if not defined PY (
  echo   [오류] 파이썬을 찾을 수 없습니다.
  echo.
  echo   https://www.python.org/downloads/ 에서 설치하세요.
  echo   설치 화면에서 "Add python.exe to PATH" 를 반드시 체크해야 합니다.
  echo.
  pause
  exit /b 1
)

set PORT=8765
set URL=http://localhost:%PORT%/

echo ------------------------------------------------
echo   KJC Holdings - 독립 실행
echo ------------------------------------------------
echo.
echo   대시보드  : %URL%
echo   주식 분석 : %URL%analysis/
echo.
echo   종료 : 이 창을 닫거나 Ctrl+C
echo ------------------------------------------------
echo.

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

start "" "%URL%"
%PY% -m http.server %PORT%

echo.
echo   서버가 종료되었습니다.
pause
