@echo off
chcp 65001 > nul
title KJC Studio - startup
cd /d "%~dp0"

REM ===================================================================
REM  KJC Studio - startup after reboot
REM
REM  1) local server 8765 (holdings preview) - kis_proxy.py, has the APIs
REM  2) browser
REM  3) every named Claude session window
REM
REM  Registered in the Windows startup folder. Safe to run by hand;
REM  anything already running is skipped.
REM
REM  KEEP THIS FILE ASCII-ONLY.
REM  cmd re-seeks this file by byte offset after every line. `chcp 65001`
REM  changes how those bytes are counted, so Korean text further down
REM  makes cmd lose its place and run fragments of lines. It happened.
REM  Korean messages are printed by tools/update-sessions.py instead.
REM ===================================================================

echo ------------------------------------------------
echo   KJC Studio - startup
echo ------------------------------------------------
echo.

REM --- 1) local server -------------------------------------------
REM  kis_proxy.py, NOT holdings-preview.bat. The latter is plain
REM  http.server: pages load but /api/kis/* all return 404.
REM  Run servers with pythonw (no console window) and log to a file.
REM  Five taskbar windows were piling up - see CLAUDE.md. pythonw has no
REM  stdout, so print() kills it unless output is redirected (2026-09-22).
set PYW=C:\Users\9800X3D\AppData\Local\Programs\Python\Python313\pythonw.exe
if not exist "%PYW%" set PYW=pythonw
if not exist "%~dp0logs" mkdir "%~dp0logs"

netstat -ano | findstr ":8765" | findstr "LISTENING" > nul 2>&1
if %errorlevel%==0 (
  echo   [skip]  server already listening on 8765
) else (
  echo   [start] local server 8765
  start "" /b cmd /c "cd /d "%~dp0holdings" && "%PYW%" server/kis_proxy.py > "%~dp0logs\8765.log" 2>&1"
  ping -n 4 127.0.0.1 > nul
)

REM --- 1b) staging server 8767 (middle server) -------------------
REM  Sessions merge here, check the screen, then it goes to main.
REM  See CLAUDE.md "three places" section. Skipped if the folder
REM  is missing, so this file still works before the split is set up.
REM  Flat, not nested. cmd expands a whole ( ) block on entry, so
REM  %errorlevel% inside it holds the value from BEFORE netstat ran.
REM  This skipped 8767 forever - found 2026-09-22. :startsession below
REM  and the 8765 block above are already flat, which is why they work.
if not exist "C:\work\kjc-staging\holdings\server\kis_proxy.py" (
  echo   [skip]  staging folder not found - split not set up yet
  goto :after8767
)
netstat -ano | findstr ":8767" | findstr "LISTENING" > nul 2>&1
if %errorlevel%==0 (
  echo   [skip]  staging server already listening on 8767
  goto :after8767
)
echo   [start] staging server 8767
start "" /b cmd /c "cd /d C:\work\kjc-staging\holdings && "%PYW%" server/kis_proxy.py --port 8767 > "%~dp0logs\8767.log" 2>&1"
ping -n 3 127.0.0.1 > nul
:after8767

REM --- 1c) session servers (split work) --------------------------
REM  One folder per session, each with its own port. All use --slow:
REM  long caches, no 5m prefill, no disclosure/news collectors.
REM  Measured 2026-09-21: 4 KIS calls vs 44 on a normal server.
REM  Skipped when the folder is missing, so this file still works
REM  before the split is set up.
call :startsession stock 8766
call :startsession daily 8768
call :startsession home  8769
call :startsession dev3  8770

REM --- 2) browser ------------------------------------------------
REM  Open the browser only when no KJC window is up yet. Running this
REM  file three times left three Chrome windows behind - it was asked
REM  about four times before anyone found it, because only the cmd
REM  windows were being counted.
REM  findstr /c: keeps "KJC Holdings" as ONE phrase. Without /c: a
REM  quoted string with a space means "KJC" OR "Holdings", which would
REM  match unrelated tabs.
tasklist /fi "imagename eq chrome.exe" /v /fo csv 2>nul | findstr /i /c:"KJC Holdings" > nul
if %errorlevel%==0 (
  echo   [skip]  browser already open
) else (
  echo   [open]  browser
  start "" "http://localhost:8765/"
)

REM --- 3) session windows ----------------------------------------
echo   [open]  Claude sessions
python tools\update-sessions.py --open

echo.
echo ------------------------------------------------
echo   main      http://localhost:8765/
echo   holdings  http://localhost:8765/holdings/
echo   projects  http://localhost:8765/projects/
echo   setup     http://localhost:8765/company-setup/
echo ------------------------------------------------
ping -n 4 127.0.0.1 > nul

goto :eof

:startsession
REM  %1 = folder suffix (C:\work\kjc-%1)   %2 = port
if not exist "C:\work\kjc-%~1\holdings\server\kis_proxy.py" (
  echo   [skip]  kjc-%~1 not found
  goto :eof
)
netstat -ano | findstr ":%~2" | findstr "LISTENING" > nul 2>&1
if %errorlevel%==0 (
  echo   [skip]  session server already listening on %~2
  goto :eof
)
echo   [start] session server %~2 ^(kjc-%~1, slow^)
start "" /b cmd /c "cd /d C:\work\kjc-%~1\holdings && "%PYW%" server/kis_proxy.py --port %~2 --slow > "%~dp0logs\%~2.log" 2>&1"
ping -n 3 127.0.0.1 > nul
goto :eof
