#!/bin/sh
# 화면 아래에 늘 떠 있는 줄. **재권님이 하셔야 할 것만** 띄운다.
#
# 만든 이유 (2026-09-17 지시) — 「커밋·푸시·배포 같은 내가 봐야 하는 단어를
# 눈에 잘 띄도록」. 세션이 답변 끝에 물으면 긴 글에 묻힌다. 실제로 커밋 하나가
# 세 시간 넘게 푸시를 기다렸고, 그 사이 재권님은 배포본 500 을 그것 때문으로
# 아셨다. 여기 떠 있으면 답변을 안 읽어도 보인다.
#
# 설정은 .claude/settings.json 의 statusLine 이다.
# Windows 에서는 Claude Code 가 Git Bash 로 돌리므로 두 PC 가 같은 파일을 쓴다.
# 경로는 반드시 슬래시로 적는다 — Git Bash 가 백슬래시를 이스케이프로 먹는다.
#
# 세션 JSON 이 stdin 으로 들어오지만 쓰지 않는다. 여기 필요한 것은 git 뿐이다.

cd "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || exit 0

R='\033[31m'; Y='\033[33m'; G='\033[32m'; D='\033[90m'; B='\033[1m'; X='\033[0m'

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
[ -z "$branch" ] && exit 0

ahead=$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)
dirty=$(git status --porcelain 2>/dev/null | grep -c .)

# 워커가 바뀌었으면 푸시로 끝나지 않는다 — Cloudflare 대시보드에 손으로
# 붙여넣어야 반영된다 (「커밋 · 푸시 · 배포 규칙」). 재권님만 하실 수 있는 일이라
# 가장 눈에 띄게 둔다.
worker=$(git diff --name-only '@{u}..HEAD' 2>/dev/null | grep -c 'worker/.*\.js')

out="${D}${branch}${X}"

if [ "$ahead" -gt 0 ]; then
  out="$out  ${B}${Y}푸시 대기 ${ahead}${X}"
else
  out="$out  ${G}푸시 끝${X}"
fi

[ "$worker" -gt 0 ] && out="$out  ${B}${R}배포 필요${X}"
[ "$dirty" -gt 0 ] && out="$out  ${D}미커밋 ${dirty}${X}"

printf '%b\n' "$out"
