#!/bin/bash
# KJC Studio 메인 사이트 로컬 미리보기
# 더블클릭하면 로컬 서버가 실행되고 Chrome 새 창이 열립니다.
# 종료: 이 창에서 Control+C 또는 창 닫기

cd "$(dirname "$0")"

PORT=8080
URL="http://localhost:${PORT}/"

# 기존 포트 정리
lsof -ti tcp:${PORT} | xargs kill -9 2>/dev/null

# 종료 시 서버 정리 + 메시지
cleanup() {
  echo ""
  echo "────────────────────────────────────────────"
  echo "  KJC Studio 서버가 종료되었습니다."
  echo "────────────────────────────────────────────"
  kill $SERVER_PID 2>/dev/null
  exit 0
}
trap cleanup INT TERM

echo "────────────────────────────────────────────"
echo "  KJC Studio · 메인 사이트"
echo "────────────────────────────────────────────"
echo ""
echo "  포트      : ${PORT}"
echo "  메인      : ${URL}"
echo "  About     : ${URL}about.html"
echo "  Services  : ${URL}services.html"
echo "  Contact   : ${URL}contact.html"
echo ""
echo "  카테고리  : ${URL}category/3d-modeling.html"
echo "              ${URL}category/ai-work.html"
echo "              ${URL}category/web-interactive.html"
echo "              ${URL}category/branding.html"
echo ""
echo "  Holdings는 별도 실행 파일 사용:"
echo "    · 루트 단축 : holdings-preview.command"
echo "    · 독립 실행 : holdings/preview.command"
echo ""
echo "  종료: Control+C 또는 이 창 닫기"
echo "────────────────────────────────────────────"
echo ""

# Python 내장 서버 백그라운드 시작
python3 -m http.server ${PORT} >/dev/null 2>&1 &
SERVER_PID=$!

# 브라우저 오픈 (Chrome 우선, 없으면 기본 브라우저)
sleep 1
if [ -d "/Applications/Google Chrome.app" ]; then
  open -na "Google Chrome" --args --new-window "${URL}"
else
  open "${URL}"
fi

wait $SERVER_PID
