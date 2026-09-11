#!/bin/bash
# KJC Studio - 프로젝트 관리 (포트 8091)
cd "$(dirname "$0")"

PORT=8091
URL="http://localhost:$PORT/"

echo "------------------------------------------------"
echo "  KJC Studio - 프로젝트 관리"
echo "------------------------------------------------"
echo
echo "  주소 : $URL"
echo
echo "  종료 : 이 창을 닫거나 Ctrl+C"
echo "------------------------------------------------"
echo

# 같은 포트를 쓰던 이전 서버 정리
lsof -ti tcp:$PORT | xargs kill -9 2>/dev/null

if open -a "Google Chrome" "$URL" 2>/dev/null; then :; else open "$URL"; fi

python3 -m http.server $PORT
