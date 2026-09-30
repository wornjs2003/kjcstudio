#!/bin/sh
# 맥에서 서버들을 **재부팅해도 뜨게** 등록한다 (2026-09-30).
#
# ■ 왜 저장소에 두나
#
# 등록 파일은 `~/Library/LaunchAgents/` 에 있는데 **거기는 저장소가 아니다.**
# 그래서 다른 기계로 옮기면 **서버가 하나도 안 뜬다.**
#
# 2026-09-28 에 윈도우에서 맥으로 옮겼을 때 정확히 그 일이 났다 —
# `startup.bat` 이 윈도우 전용이라 **세션 서버 넷(8766·8768·8769·8770)과
# Debugging(8093)이 통째로 비어 있었다.** 며칠 뒤 재권님이
# **「다 떠야할거같은데」** 하셔서 드러났다.
#
# `.bat` 은 저장소에 있는데 **맥 쪽 짝이 없었다.** 이 폴더가 그 짝이다.
#
# ■ 키가 들어 있지 않다
#
# 경로와 포트만 있다. `KJC_ROLE` 도 여기서 주지 않는다 —
# **그것은 「켜기」 라 따로 승인받는다.**
#
# ■ 무엇이 어디를 보나
#
#     8765  메인서버     /Users/kjc/work/KJCStudio    **알림을 보내는 자리**
#     8764  서비스방     /Users/kjc/service           **외부접속이 보는 자리**
#     8767  중간서버     /Users/kjc/work/kjc-staging
#     8766·8768·8769·8770  세션 폴더들   (`--slow`)
#     8093  Debugging   /Users/kjc/work/KJCStudio/debugging
#
# 경로가 이 기계와 다르면 **plist 를 먼저 고쳐야 한다.**

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
DEST=~/Library/LaunchAgents

echo ""
echo "  ── launchd 등록 ──────────────────────────────────────"
echo ""

mkdir -p "$DEST"
n=0
for f in "$HERE"/kr.kjcstudio.*.plist; do
  [ -e "$f" ] || continue
  name=$(basename "$f")
  label=${name%.plist}

  # **경로가 실재하는지 먼저 본다.** 없는 폴더를 가리키면 `KeepAlive` 가
  # 무한히 재시도하며 로그만 쌓인다.
  wd=$(/usr/bin/sed -n 's:.*<string>\(/Users/[^<]*\)</string>.*:\1:p' "$f" \
       | grep -E '^/Users/.*/(holdings|debugging)$' | head -1)
  if [ -n "$wd" ] && [ ! -d "$wd" ]; then
    echo "  건너뜀 — 폴더가 없습니다: $name"
    echo "           $wd"
    continue
  fi

  cp "$f" "$DEST/$name"

  # 이미 올라가 있으면 내렸다 다시 올린다. 안 그러면 옛 설정으로 계속 돈다.
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  if launchctl bootstrap "gui/$(id -u)" "$DEST/$name" 2>/dev/null; then
    echo "  올렸습니다: $name"
    n=$((n + 1))
  else
    echo "  ⚠️ 못 올렸습니다: $name  (포트를 다른 것이 잡고 있을 수 있습니다)"
  fi
done

echo ""
echo "  $n개 올렸습니다. 뜨는 데 몇 초 걸립니다."
echo ""

sleep 8

echo "  ── 확인 ──────────────────────────────────────────────"
for p in 8093 8764 8765 8766 8767 8768 8769 8770; do
  pid=$(lsof -nP -iTCP:$p -sTCP:LISTEN 2>/dev/null | awk 'NR>1{print $2}' | sort -u | tr '\n' ' ')
  printf '    %s  %s\n' "$p" "${pid:-**안 뜸**}"
done
echo ""
echo '  ⚠️ cloudflared(터널)는 여기 없습니다 — Cloudflare 가 만든 것이고'
echo "     /Library/LaunchDaemons 에 따로 있습니다."
echo ""
