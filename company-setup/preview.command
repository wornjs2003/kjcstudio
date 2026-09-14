#!/bin/bash
# KJC Studio - 회사 설립 체크리스트 (포트 8090)
# 저장소 루트에서 내보낸다. 화면이 ../assets/ · ../partials/ 를 함께 쓰기 때문이다.
# 이 폴더만 내보내면 색과 메뉴가 404 가 된다 (2026-09-14).
cd "$(dirname "$0")/.."

PORT=8090
URL="http://localhost:$PORT/company-setup/"

echo "------------------------------------------------"
echo "  KJC Studio - 회사 설립 체크리스트"
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
