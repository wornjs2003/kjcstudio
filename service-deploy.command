#!/bin/sh
# 작업방에서 만든 것을 **서비스방으로 옮긴다** (2026-09-30 지시).
#
# 재권님 말씀 — 「맥미니 내부에서 작업할곳과 실제 대이터를 나눌 필요는 있어뵈는데」.
#
# ■ 이것이 「푸시」 를 대신한다
#
# 전에는 `푸시` 가 관문이었다 — 재권님이 「푸시해」 하실 때 GitHub 이
# 반영했다. 사이트가 맥미니로 넘어오면서 그 관문이 없어졌고,
# **작업방에서 파일을 저장하는 순간 폰에 나가는** 상태가 됐다.
#
#     전에    커밋 → **푸시**   → 사이트 바뀜
#     지금    커밋 → **옮기기** → 사이트 바뀜     ← 이 스크립트
#
# **하는 일은 같고 이름만 바뀐다.** 정하시는 것도 그대로 재권님이다.
#
# ■ 데이터는 안 건드린다
#
# 서비스방은 **자기 `market.db`** 를 갖고 자기 서버가 거기에 쓴다
# (「전부 두 벌」 — 2026-09-30 지시). 코드만 옮긴다.
#
# ■ 되돌리기
#
#     git -C /Users/kjc/service reset --hard <옮기기 전 해시>
#
# 그 해시를 아래에서 찍어 둔다.

set -e

WORK=/Users/kjc/work/KJCStudio
SERVICE=/Users/kjc/service
PORT=8764

echo ""
echo "  ── 작업방 → 서비스방 ────────────────────────────────"
echo ""

if [ ! -d "$SERVICE/.git" ] && [ ! -f "$SERVICE/.git" ]; then
  echo "  서비스방이 없습니다: $SERVICE"
  echo "  먼저 만들어야 합니다."
  exit 1
fi

before=$(git -C "$SERVICE" rev-parse --short HEAD)
main=$(git -C "$WORK" rev-parse --short main)

if [ "$(git -C "$SERVICE" rev-parse HEAD)" = "$(git -C "$WORK" rev-parse main)" ]; then
  echo "  이미 같습니다 — 옮길 것이 없습니다 ($before)"
  echo ""
  exit 0
fi

echo "  옮길 커밋:"
git -C "$WORK" log --oneline "$before..main" | sed 's/^/      /'
echo ""

# **미커밋이 있으면 멈춘다.** 커밋 안 된 것은 옮기지 않는다 —
# 그것이 이 관문의 목적이다.
if [ -n "$(git -C "$WORK" status --porcelain --untracked-files=no)" ]; then
  echo "  ⚠️ 작업방에 **커밋 안 된 것**이 있습니다:"
  git -C "$WORK" status --porcelain --untracked-files=no | sed 's/^/      /'
  echo ""
  echo "  **커밋된 것까지만 옮깁니다.** 위 파일은 안 갑니다."
  echo ""
fi

# **검수 문턱 (2026-10-15 재권님 「응 해줘」)** — 서비스에 닿는 커밋마다 보드에 「검수 통과」 줄이 있어야 옮긴다.
# 그날 두 번 검수 전 커밋이 main 통째 옮기기에 딸려 갔다. 못 보면(보드 · git) 멈춘다 — 옮기기는 되돌릴 수 없는 쪽이다.
# 재권님이 그래도 옮기라 하시면 KJC_DEPLOY_FORCE=1 (logs/deploy-force.log 에 남는다). 셈은 tools/deploy-gate.py 머리 주석
if ! sh "$WORK/.claude/run-py.sh" "$WORK/tools/deploy-gate.py" "$before..main"; then
  echo ""
  echo "  옮기지 않았습니다 — 위 커밋의 검수가 끝나면 다시 돌립니다"
  echo ""
  exit 1
fi
echo ""
git -C "$SERVICE" merge --ff-only main
after=$(git -C "$SERVICE" rev-parse --short HEAD)

echo ""
echo "  옮겼습니다:  $before  →  $after"
echo "  되돌리려면:  git -C $SERVICE reset --hard $before"
echo ""

# 서버를 다시 읽게 한다. 파이썬은 파일을 매번 읽지 않으므로 재시작이 필요하다.
# **화면 파일(HTML·CSS·JS)은 재시작 없이도 바뀐다** — 서버가 그때그때 읽는다.
# 서버 코드(`holdings/server/` 의 `.py`)가 바뀐 경우에만 재시작한다 — 도구(`tools/` 등)의 `.py` 로는 안 한다 (2026-10-14 창구 · 안 해도 될 재시작).
if git -C "$SERVICE" diff --name-only "$before" "$after" | grep -q '^holdings/server/.*\.py$'; then
  echo "  서버 코드가 바뀌었습니다 — 재시작합니다"
  launchctl kickstart -k "gui/$(id -u)/kr.kjcstudio.service-$PORT" 2>/dev/null \
    && echo "  재시작했습니다" \
    || echo "  ⚠️ 재시작 실패 — 손으로 확인해 주십시오"
  sleep 3
fi

code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost:$PORT/api/kis/health" || echo 000)
echo "  서비스방 상태: $code  (200 이면 정상)"
echo ""
echo "  ──────────────────────────────────────────────────────"
echo ""
