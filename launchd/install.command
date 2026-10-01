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
#     8766·8768·8770  세션 폴더들   (`--slow`)
#     ~~8769~~  **2026-10-01 에 영구히 뺐다**(지시 「영구히 지워 launchd 에서도 빼」).
#               plist 를 저장소·설치본 양쪽에서 지웠다. `kjc-home` 폴더 자체는 그대로다.
#     8093  Debugging   /Users/kjc/work/KJCStudio/debugging
#
# 경로가 이 기계와 다르면 **plist 를 먼저 고쳐야 한다.**
#
# ■ 포트를 주면 그것만 올린다 (2026-10-01)
#
#     ./install.command                  전부 (지금까지와 같다)
#     ./install.command 8766 8767        그 둘만 내렸다 올린다
#
# **8765(알림 서버)를 안 끄고 세션 서버만 다시 올리려고** 만들었다 —
# 「KIS 를 8765 하나로」 를 한 서버씩 켜 보는 자리다. 8765 는 이름에 포트가
# 없어서(`kis-proxy.plist`) 8765 라고 적으면 그것으로 친다.

#
# ■ 올리기 전에 둘을 본다 — 재시작은 커밋 안 된 코드도 로드한다 (2026-10-01)
#
#     그 포트 폴더의 holdings/server/ 에 미커밋이 있나   → 있으면 **멈춘다** (누구 것인지 보여 준다)
#     kis_proxy.py 가 문법에 맞나 (py_compile)        → 깨졌으면 올리지 않는다
#
# 2026-10-01 14:02 에 8765 를 재시작했는데 메인 폴더의 미커밋 보드 코드가 함께 로드돼
# 검수 전 코드가 알림 서버에서 13분 돌았다. 무해했던 것은 운이 아니라 한 번에 write 한
# 덕이었다. 편집 중간에 재시작하면 8765 가 안 떠서 신호·공시가 멈춘다.
#
#     ./install.command --force 8766      미커밋이 있어도 올린다 — **알림이 멈춰 급히 올려야 할 때**만
#     ./install.command --check 8766      검사만 하고 올리지 않는다
#     ./install.command --wait 20 …       올린 뒤 health 를 20초까지 기다린다 (기본 10)
#
# 올린 뒤에는 /api/kis/health 가 N초 안에 200 인지 본다 — py_compile 은 문법만 보고
# import 때 터지는 것(이름 오류 · 없는 모듈)은 못 잡는다.

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
DEST=~/Library/LaunchAgents

echo ""
echo "  ── launchd 등록 ──────────────────────────────────────"
echo ""

mkdir -p "$DEST"
n=0
# 인자 — 포트 목록(비어 있으면 전부) · --force · --check · --wait N
ONLY=""; FORCE=0; CHECK=0; WAIT=10
while [ $# -gt 0 ]; do
  case "$1" in
    --force) FORCE=1 ;;
    --check) CHECK=1 ;;
    --wait)  shift; WAIT="${1:-10}" ;;
    *) ONLY="$ONLY $1" ;;
  esac
  shift
done
ONLY=$(printf '%s' "$ONLY" | /usr/bin/sed 's/^ *//')
PY_RUN="$HERE/../.claude/run-py.sh"

# 그 포트의 폴더에서 미커밋·문법을 본다. 0 이면 올려도 된다.
precheck() {  # $1 = holdings 폴더
  root=$(dirname "$1")
  [ -d "$root/.git" ] || [ -f "$root/.git" ] || return 0        # 저장소가 아니면(debugging 폴더 등) 안 본다
  dirty=$(git -C "$root" status --porcelain -- holdings/server/ 2>/dev/null)
  if [ -n "$dirty" ]; then
    echo "  ⚠️ 미커밋이 있습니다 — $root/holdings/server/"
    printf '%s\n' "$dirty" | /usr/bin/sed 's/^/        /'
    if [ "$FORCE" = "1" ]; then
      echo "        --force 라 그대로 올립니다 (검수 전 코드가 돌게 됩니다)"
    else
      echo "        커밋하거나 그 세션에 「재시작 미뤄 달라」 — 급하면 --force"
      return 1
    fi
  fi
  if [ -f "$root/holdings/server/kis_proxy.py" ]; then
    if ! sh "$PY_RUN" -m py_compile "$root/holdings/server/kis_proxy.py" 2>/dev/null; then
      echo "  ✗ 문법이 깨져 있습니다 — $root/holdings/server/kis_proxy.py  (올리면 안 뜹니다)"
      return 1
    fi
  fi
  return 0
}
port_of() {  # plist 이름 → 포트. 포트가 이름에 없는 것은 kis-proxy.plist(8765) 하나뿐이다
  # **서버 등록 파일만 올린다.** 포트도 없고 kis-proxy 도 아닌 것(check-chart · herdr)은
  # 빈 값을 내고 아래 루프가 건너뛴다 — 2026-10-02 08:31 에 `install.command 8765` 가
  # check-chart.plist(30분 주기)까지 같이 올려 지시 없는 켜기가 났다. 그런 것은 손으로 켠다.
  case "$1" in kr.kjcstudio.kis-proxy.plist) printf '8765'; return ;; esac
  printf '%s' "$1" | /usr/bin/sed -n 's/.*-\([0-9][0-9]*\)\.plist$/\1/p'
}
wanted() {   # $1 포트가 ONLY 에 있나 (ONLY 가 비면 전부)
  [ -z "$ONLY" ] && return 0
  for w in $ONLY; do [ "$w" = "$1" ] && return 0; done
  return 1
}

for f in "$HERE"/kr.kjcstudio.*.plist; do
  [ -e "$f" ] || continue
  name=$(basename "$f")
  label=${name%.plist}
  port=$(port_of "$name")
  if [ -z "$port" ]; then
    echo "  건너뜀 — 서버 등록 파일이 아닙니다(손으로 켠다): $name"
    continue
  fi
  wanted "$port" || continue

  # **경로가 실재하는지 먼저 본다.** 없는 폴더를 가리키면 `KeepAlive` 가
  # 무한히 재시도하며 로그만 쌓인다.
  wd=$(/usr/bin/sed -n 's:.*<string>\(/Users/[^<]*\)</string>.*:\1:p' "$f" \
       | grep -E '^/Users/.*/(holdings|debugging)$' | head -1)
  if [ -n "$wd" ] && [ ! -d "$wd" ]; then
    echo "  건너뜀 — 폴더가 없습니다: $name"
    echo "           $wd"
    continue
  fi

  if ! precheck "$wd"; then
    echo "  건너뜀: $name"
    continue
  fi
  if [ "$CHECK" = "1" ]; then
    echo "  검사 통과 (올리지 않음): $name"
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

[ "$CHECK" = "1" ] && { echo ""; echo "  --check 라 올리지 않았습니다."; echo ""; exit 0; }

echo ""
echo "  $n개 올렸습니다. 뜨는 데 몇 초 걸립니다."
echo ""

sleep 3

echo "  ── 확인 (health 를 ${WAIT}초까지 기다립니다) ───────────────"
for p in ${ONLY:-8093 8764 8765 8766 8767 8768 8770}; do
  pid=$(lsof -nP -iTCP:$p -sTCP:LISTEN 2>/dev/null | awk 'NR>1{print $2}' | sort -u | tr '\n' ' ')
  if [ "$p" = "8093" ]; then
    printf '    %s  %s\n' "$p" "${pid:-**안 뜸**}"
    continue
  fi
  ok=""; i=0
  while [ "$i" -lt "$WAIT" ]; do
    code=$(curl -s -o /dev/null -m 2 -w '%{http_code}' "http://127.0.0.1:$p/api/kis/health" 2>/dev/null)
    [ "$code" = "200" ] && { ok=1; break; }
    i=$((i + 1)); sleep 1
  done
  if [ -n "$ok" ]; then
    printf '    %s  %s  health 200 (%s초)\n' "$p" "$pid" "$i"
  else
    printf '    %s  %s  ⚠️ **health 가 %s초 안에 200 이 아닙니다** — 로그를 보십시오: logs/%s.log\n' "$p" "${pid:-안 뜸}" "$WAIT" "$p"
  fi
done
echo ""
echo '  ⚠️ cloudflared(터널)는 여기 없습니다 — Cloudflare 가 만든 것이고'
echo "     /Library/LaunchDaemons 에 따로 있습니다."
echo ""
