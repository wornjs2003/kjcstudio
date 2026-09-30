#!/bin/sh
# 세션 여덟을 cmux 작업공간으로 이어받는다 (맥). `resume-sessions.bat` 의 짝이다.
#
# ⚠️ **cmux 안에서 실행해야 한다.** cmux CLI 는 「cmux 내부에서 시작된
# 프로세스만」 소켓에 붙여 준다 — Terminal.app 에서 돌리면 「액세스 거부됨」 이다.
#
# ⚠️ **먼저 Terminal.app 의 기존 세션을 닫아야 한다.** `claude --resume` 은
# 이미 돌고 있으면 **사본을 시작한다**(`claude --help`). 안 닫으면 열여섯이 된다.
#
# ⚠️ **이 파일은 `tools/update-sessions.py` 가 만들지 않는다** — 손으로 적었다.
# 세션이 늘거나 이름이 바뀌면 아래 목록도 손으로 고쳐야 한다.
# (`.bat` 쪽은 그 도구가 만든다. 둘이 갈릴 수 있다 — 2026-09-28)
set -u

REPO="/Users/kjc/work/KJCStudio"

if [ -z "${CMUX_WORKSPACE_ID:-}${CMUX_SURFACE_ID:-}" ]; then
  echo ""
  echo "  cmux 안에서 실행해 주십시오."
  echo "  지금은 cmux 밖이라 작업공간을 만들 수 없습니다."
  echo ""
  exit 2
fi

# **`claude --resume` 이 붙어 있다고 보면 안 된다** (2026-09-28 실측).
# cmux 는 그 사이에 `--settings` · `--mcp-config` 를 끼워 넣고, 어떤 세션은
# `--resume` 이 아니라 **`--session-id`** 로 뜬다. 붙은 꼴로만 세면 **0** 이
# 나와서 **이 안전장치가 통째로 안 먹는다** — 실제로 그랬다.
# 세션 번호를 뽑아 `sort -u` 로 센다. 같은 세션이 두 줄로 잡혀도 하나로 본다.
running=$(ps -ax -o command= \
  | grep -E "[c]laude .*--(resume|session-id) " \
  | grep -oE -- "--(resume|session-id) [0-9a-f-]+" \
  | sort -u | wc -l | tr -d " ")
if [ "$running" -gt 0 ]; then
  echo ""
  echo "  ⚠️ 이미 돌고 있는 세션이 ${running}개 있습니다."
  echo "     이대로 진행하면 **사본**이 생깁니다."
  echo "     Terminal.app 을 먼저 닫으십시오 (Cmd+Q)."
  echo ""
  printf "  그래도 계속하시겠습니까? [y/N] "
  read ans
  case "$ans" in y|Y) ;; *) echo "  멈췄습니다."; exit 0;; esac
fi

# **만들면서 바로 고정한다 (2026-09-30 지시).**
#
# 재권님 말씀 — 「왼쪽에 세션 목록들 **핀박고 위치 고정**하는거 안하나?
# 왜 안되어있지?」
#
# 그 전에는 이 스크립트가 `new-workspace` 만 불러서, **재부팅하면 고정이
# 통째로 풀렸다.** 실제로 그랬다 — 재부팅 전 저장본에 다섯이 고정이었고
# 다시 뜬 뒤에는 **전부 풀림**이었다.
#
# ⚠️ **핀은 「맨 위로」 가 아니라 「고정 묶음의 끝에」 붙는다.**
# 그래서 **만드는 순서대로 꽂으면 그 순서가 남는다.**
#
# 같은 날 이것을 한 개로 재다 틀렸다 — 하나만 꽂으면 **그것이 유일한
# 고정이라 맨 위로 올라간 것처럼 보인다.** 그 값으로 「아래에서 위로」 로
# 판단해 여덟을 꽂았더니 **순서가 통째로 뒤집혔다.**
# **한 개로 잰 것이 여러 개일 때와 다르다.**
#
# ⚠️ **순서가 바뀌는 원인이 하나 더 있다.** cmux 기본값
# `app.reorderOnNotification` 이 **알림이 오면 그 작업공간을 위로 올린다.**
# `~/.config/cmux/cmux.json` 에서 `false` 로 꺼 두었다 — 고정만으로는
# 안 막힌다. `qa` 가 찾았다.
# **`new-workspace` 의 출력을 짐작하지 않는다.** 무엇을 찍는지 `--help` 에
# 없고, **시험 삼아 만들면 재권님 목록에 찌꺼기가 남는다.** 그래서 만든 뒤에
# **이름으로 되찾아** 꽂는다 — 그 조회는 지금 있는 것으로 시험할 수 있다.
pin_by_name() {
  ref=$(cmux workspace list 2>/dev/null \
        | sed -e 's/^[* ]*//' \
        | awk -v n="$1" '{ ws=$1; $1=""; sub(/^ +/,""); sub(/ +\[selected\]$/,"");
                           if ($0 == n) { print ws; exit } }')
  if [ -z "$ref" ]; then
    echo "    (고정 못 함: $1 — 목록에서 못 찾았습니다. 손으로 꽂아 주십시오)"
    return 1
  fi
  cmux workspace-action --action pin --workspace "$ref" >/dev/null 2>&1 || {
    echo "    (고정 실패: $1)"; return 1; }
}

open_one() {
  name=$1; sid=$2
  echo "  여는 중 — $name"
  if cmux new-workspace --name "$name" --cwd "$REPO" \
          --command "claude --resume $sid" --focus false >/dev/null 2>&1; then
    NAMES="$NAMES$name
"
    opened=$((opened + 1))
  else
    echo "    ** 실패: $name **"
  fi
}

opened=0
NAMES=""

open_one "개념정의"          04fa6a4d-eada-4ddc-9cb9-18ae177540e4
open_one "작업우선순위"      b5e2504d-dc3b-43cb-b44e-ee923448b090
open_one "홈페이지_정리"     cf9e2f1b-004a-494b-92cc-a815366b4719
open_one "주식페이지_개발"   36e5295a-5818-465f-ab1a-12bc8ae5f6d1
open_one "주식페이지_개발1"  79392509-8e6d-4d89-83e6-924be9e42ef4
open_one "주식페이지_개발2"  dbe9b967-1b4e-4624-824f-27c827bbf82c
open_one "주식페이지_개발3"  9bf6d383-13c2-4a27-b4fd-ff388169b1f2
open_one "엔진_개발"         71470664-9e0d-44f3-9a92-ddd0fe66dd6d
open_one "qa"               12b7e713-afb0-4450-aabb-18b6544b14b4

# **여는 것이 다 끝난 뒤에 꽂는다 — 만든 순서대로.**
# 핀이 「고정 묶음의 끝에」 붙으므로 이 순서가 그대로 목록 순서가 된다.
echo ""
echo "  고정하는 중…"
pinned=0
printf '%s' "$NAMES" | while IFS= read -r n; do
  [ -n "$n" ] && pin_by_name "$n" && pinned=$((pinned + 1))
done

echo ""
# **개수를 박지 않는다** — 세션이 늘면 낡는다. 위에서 센 값을 쓴다
# (「세면 나오는 값은 본문에 적지 않는다」).
echo "  ${opened}개를 열고 **고정까지** 했습니다. 왼쪽 목록에서 고르십시오."
echo ""
echo "  ⚠️ **창을 둘로 나누는 것은 이 스크립트가 하지 않습니다.**"
echo "     왼쪽(개념정의·작업우선순위·qa)과 오른쪽 나눔은 손으로 하신 배치라"
echo "     여기서 재현하지 않습니다 — **잘못 짐작하면 배치를 흐트러뜨립니다.**"
echo ""
