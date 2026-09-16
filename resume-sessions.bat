@echo off
chcp 65001 > nul
REM ===================================================================
REM  KJC Studio - 세션 한 번에 열기
REM  이 파일은 tools/update-sessions.py 가 만든다. 직접 고치지 말 것.
REM  세션이 늘면 이 파일을 실행만 해도 목록이 새로 채워진다.
REM ===================================================================

cd /d "%~dp0"

REM 목록을 먼저 새로 만든다 (세션이 늘었을 수 있으므로)
python tools\update-sessions.py --quiet

REM 개념정의
start "개념정의" cmd /k "cd /d %~dp0 && claude --resume 04fa6a4d-eada-4ddc-9cb9-18ae177540e4"

REM 주식페이지_개발
start "주식페이지_개발" cmd /k "cd /d %~dp0 && claude --resume 36e5295a-5818-465f-ab1a-12bc8ae5f6d1"

REM 홈페이지_정리
start "홈페이지_정리" cmd /k "cd /d %~dp0 && claude --resume cf9e2f1b-004a-494b-92cc-a815366b4719"

REM 스케줄_툴개발
start "스케줄_툴개발" cmd /k "cd /d %~dp0 && claude --resume 9bf6d383-13c2-4a27-b4fd-ff388169b1f2"

echo 세션 4개를 열었습니다.
timeout /t 2 > nul
