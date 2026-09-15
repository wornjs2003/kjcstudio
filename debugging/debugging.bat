@echo off
chcp 65001 >nul
title KJC Studio - Debugging (포트 8093)

rem 저장소 루트에서 내보낸다. 화면이 ../assets/ 와 ../partials/ 를 함께 쓰기 때문이다.
rem server.py 가 알아서 루트를 잡으므로 여기서는 폴더만 맞춰 준다.
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

rem 같은 포트를 쓰던 이전 서버 정리
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8093" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

%PY% server.py

echo.
echo   서버가 종료되었습니다.
pause
