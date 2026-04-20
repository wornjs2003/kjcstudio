#!/bin/bash
# KJC Holdings 로컬 미리보기 (루트 편의용 단축)
# 더블클릭하면 holdings 폴더를 루트로 서빙하고 Chrome 새 창이 열립니다.
# holdings를 나중에 분리할 경우, holdings/preview.command 가 독립 실행 파일로 따라갑니다.
# 종료: 이 창에서 Control+C 또는 창 닫기

# holdings 폴더로 이동
cd "$(dirname "$0")/holdings"

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
echo "  KJC Holdings · 보유 종목 / 주식 분석"
echo "────────────────────────────────────────────"
echo ""
echo "  포트      : ${PORT}"
echo "  대시보드  : ${URL}"
echo "  주식 분석 : ${URL}analysis/"
echo "  로드맵    : ${URL}roadmap.html"
echo ""
echo "  ※ holdings는 독립 프로젝트 구조로 서빙됩니다."
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
