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

open_one() {
  name=$1; sid=$2
  echo "  여는 중 — $name"
  cmux new-workspace --name "$name" --cwd "$REPO" \
       --command "claude --resume $sid" --focus false || \
    echo "    ** 실패: $name **"
}

open_one "개념정의"          04fa6a4d-eada-4ddc-9cb9-18ae177540e4
open_one "작업우선순위"      b5e2504d-dc3b-43cb-b44e-ee923448b090
open_one "홈페이지_정리"     cf9e2f1b-004a-494b-92cc-a815366b4719
open_one "주식페이지_개발"   36e5295a-5818-465f-ab1a-12bc8ae5f6d1
open_one "주식페이지_개발1"  79392509-8e6d-4d89-83e6-924be9e42ef4
open_one "주식페이지_개발2"  dbe9b967-1b4e-4624-824f-27c827bbf82c
open_one "주식페이지_개발3"  9bf6d383-13c2-4a27-b4fd-ff388169b1f2
open_one "엔진_개발"         71470664-9e0d-44f3-9a92-ddd0fe66dd6d
open_one "qa"               12b7e713-afb0-4450-aabb-18b6544b14b4

echo ""
echo "  여덟을 열었습니다. 왼쪽 목록에서 고르십시오."
echo ""
