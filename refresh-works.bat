@echo off
chcp 65001 >nul
title KJC Studio - 작업물 목록 갱신
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

echo ------------------------------------------------
echo   작업물 이미지를 스캔해서 목록을 갱신합니다
echo ------------------------------------------------
echo.

%PY% tools\refresh-works.py

echo.
if %ERRORLEVEL%==0 (
  echo   갱신 완료. 브라우저를 새로고침하세요 ^(Ctrl+Shift+R^)
) else (
  echo   문제가 생겼습니다. 위 메시지를 확인하세요.
)
echo.
pause
