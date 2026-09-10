@echo off
chcp 65001 >nul
title KJC Holdings - KIS 연결 확인
cd /d "%~dp0"

rem 파이썬 탐지 (python -> py -3 순서)
set PY=
python --version >nul 2>&1 && set PY=python
if not defined PY py -3 --version >nul 2>&1 && set PY=py -3
if not defined PY (
  echo   [오류] 파이썬을 찾을 수 없습니다.
  echo   https://www.python.org/downloads/ 에서 설치하세요.
  pause
  exit /b 1
)

%PY% "server\setup_kis.py" --check

echo.
pause
