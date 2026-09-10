#!/bin/bash
# KJC Holdings 독립 실행 (holdings 폴더 자체를 루트로 서빙)
# 이 파일은 holdings 분리 시 함께 따라가는 독립 실행 파일입니다.
# 더블클릭하면 holdings/ 루트에서 로컬 서버가 실행되고 Chrome 새 창이 열립니다.
# 종료: 이 창에서 Control+C 또는 창 닫기

cd "$(dirname "$0")"

PORT=8765
URL="http://localhost:${PORT}/"

# 기존 포트 정리
lsof -ti tcp:${PORT} | xargs kill -9 2>/dev/null

# 종료 시 서버 정리 + 메시지
cleanup() {
  echo ""
  echo "────────────────────────────────────────────"
  echo "  KJC Holdings 서버가 종료되었습니다."
  echo "────────────────────────────────────────────"
  kill $SERVER_PID 2>/dev/null
  exit 0
}
trap cleanup INT TERM

echo "────────────────────────────────────────────"
echo "  KJC Holdings · 독립 실행"
echo "────────────────────────────────────────────"
echo ""
echo "  포트      : ${PORT}"
echo "  대시보드  : ${URL}"
echo "  주식 분석 : ${URL}analysis/"
echo "  로드맵    : ${URL}roadmap.html"
echo ""
echo "  종료: Control+C 또는 이 창 닫기"
echo "────────────────────────────────────────────"
echo ""

# 로컬 서버 백그라운드 시작 (KIS 중계 포함, secrets.json 없으면 정적 서버로 동작)
python3 "server/kis_proxy.py" --port ${PORT} &
SERVER_PID=$!

# 브라우저 오픈 (Chrome 우선, 없으면 기본 브라우저)
sleep 1
if [ -d "/Applications/Google Chrome.app" ]; then
  open -na "Google Chrome" --args --new-window "${URL}"
else
  open "${URL}"
fi

wait $SERVER_PID
