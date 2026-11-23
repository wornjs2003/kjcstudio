#!/bin/zsh
# KJC 주문 컴퓨터 — 맥용 실행 파일 만들기 (2026-11-23 · 재권님 「가」)
# 결과: dist/KJC주문.app — 그 옆에 config.json 을 둔다(config.example.json 을 복사해 채움 · 열쇠 · 계좌는 그 파일에만)
# 맥 기본 파이썬(창 도구 8.5)은 macOS 26 에서 「26 이상 필요」 로 꺼진다 — uv 로 받은 파이썬 3.12(창 도구 9.0)로 묶는다
#   처음 한 번:  brew install uv  ·  uv python install 3.12
cd "$(dirname "$0")" || exit 2
command -v uv > /dev/null || { echo "uv 가 없습니다 — brew install uv 뒤 uv python install 3.12"; exit 2; }
PY="$(uv python find 3.12)" || { echo "파이썬 3.12 가 없습니다 — uv python install 3.12"; exit 2; }
V="${TMPDIR:-/tmp}/kjc-trader-build"     # 가상 환경 · 중간 파일은 저장소 밖에(룰 검사가 저장소 안 파일을 센다)
"$PY" -m venv "$V/venv" || exit 1
"$V/venv/bin/pip" install -q --upgrade pip "pyinstaller==6.22.3" || exit 1
"$V/venv/bin/python" -m unittest discover -s tests -q || exit 1
"$V/venv/bin/python" -m PyInstaller --noconfirm --windowed --name KJC주문 --distpath dist --workpath "$V/work" --specpath "$V" run.py || exit 1
cp -f config.example.json dist/config.example.json
echo "다 됐습니다: $(pwd)/dist/KJC주문.app — 옆의 config.example.json 을 config.json 으로 복사해 채우십시오"
