@echo off
chcp 65001 >nul
title KJC Studio - 회사 설립 체크리스트 (포트 8090)
cd /d "%~dp0"

set PY=
python --version >nul 2>&1 && set PY=python
if not defined PY py -3 --version >nul 2>&1 && set PY=py -3
if not defined PY (
  echo   [오류] 파이썬을 찾을 수 없습니다.
  echo   https://www.python.org/downloads/ 에서 설치하세요.
  pause
  exit /b 1
)

set PORT=8090
set URL=http://localhost:%PORT%/

echo ------------------------------------------------
echo   KJC Studio - 회사 설립 체크리스트
echo ------------------------------------------------
echo.
echo   주소 : %URL%
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
