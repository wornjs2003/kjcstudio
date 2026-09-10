#!/bin/bash
# KJC Holdings - 한국투자증권 API 키 설정 (macOS)
cd "$(dirname "$0")" || exit 1

PY=""
if command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
else
  echo "  [오류] 파이썬을 찾을 수 없습니다."
  echo "  https://www.python.org/downloads/ 에서 설치하세요."
  read -r -p "  엔터를 누르면 닫힙니다..."
  exit 1
fi

"$PY" "server/setup_kis.py"

echo
read -r -p "  엔터를 누르면 닫힙니다..."
