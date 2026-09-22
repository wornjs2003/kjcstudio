#!/bin/sh
# 화면 아래에 늘 떠 있는 두 줄. **재권님이 하셔야 할 것만** 띄운다.
#
# 만든 이유 (2026-09-17 지시) — 「커밋·푸시·배포 같은 내가 봐야 하는 단어를
# 눈에 잘 띄도록」. 세션이 답변 끝에 물으면 긴 글에 묻힌다. 실제로 커밋 하나가
# 세 시간 넘게 푸시를 기다렸고, 그 사이 재권님은 배포본 500 을 그것 때문으로
# 아셨다.
#
# 개수만 띄웠더니 「무엇이 대기 중이지」 를 다시 물어야 했다. 그래서 **내용**을
# 적는다. 클릭해서 보러 가는 방법도 알아봤지만, 푸시 대기 중인 커밋은 아직
# 원격에 없어서 열 주소가 없다. 적혀 있으면 클릭할 일 자체가 없다.
#
#     main  푸시 대기 1  Keep push and deploy state on screen…
#           미커밋 2  modal.css · latest.json
#
# 설정은 .claude/settings.json 의 statusLine 이다.
# Windows 에서는 Claude Code 가 Git Bash 로 돌리므로 두 PC 가 같은 파일을 쓴다.
# 경로는 반드시 슬래시로 적는다 — Git Bash 가 백슬래시를 이스케이프로 먹는다.

# 상태줄 입력을 통째로 받아 둔다. 주간 사용량이 여기 온다 (2026-09-22 지시).
# **한 번만 읽을 수 있으므로** 변수에 담는다.
STDIN_JSON=$(cat)

cd "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || exit 0

R='\033[31m'; Y='\033[33m'; G='\033[32m'; D='\033[90m'; B='\033[1m'; X='\033[0m'

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
[ -z "$branch" ] && exit 0

ahead=$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)

# ── 첫 줄 — 푸시 ──────────────────────────────────
line1="${D}${branch}${X}"

if [ "$ahead" -gt 0 ]; then
  line1="$line1  ${B}${Y}푸시 대기 ${ahead}${X}"

  # 가장 오래 기다린 것부터 보여준다. 여럿이면 그것 하나와 「외 N건」.
  subject=$(git log --format='%s' '@{u}..HEAD' 2>/dev/null | tail -1 | cut -c1-44)
  if [ -n "$subject" ]; then
    line1="$line1  ${D}${subject}"
    [ "$ahead" -gt 1 ] && line1="$line1 외 $((ahead - 1))건"
    line1="$line1${X}"
  fi

else
  line1="$line1  ${G}푸시 끝${X}"
fi

# ── 배포 ──────────────────────────────────────────
# 워커는 푸시해도 반영되지 않는다. Cloudflare 대시보드에 손으로 붙여넣어야 하고,
# 그건 재권님만 하실 수 있다 (「커밋 · 푸시 · 배포 규칙」).
#
# 처음에는 이 표시를 「푸시 대기」 안에 넣었다가 뺐다. **순서가 커밋 → 푸시 →
# 배포라서, 푸시하는 순간 ahead 가 0이 되어 초록 「푸시 끝」 으로 바뀌고
# 배포 안내가 사라졌다.** 정작 배포할 때가 그때인데 아무 말이 없었다.
# 2026-09-17 아침 배포본 500 이 바로 그 상태였다 — 푸시는 됐고 대시보드에만
# 안 올라가 있었다. 지금 코드는 **푸시 여부와 무관하게** 판단한다.
#
# 배포됐는지는 알아낼 수 없다. 대시보드에 못 들어가고 배포본은 Access 뒤라
# 302 만 온다. 그래서 재권님이 「배포했다」 고 하시면 세션이 여기에 적는다.
#
#     git rev-parse @{u} > .claude/deployed
#
# 원격 쪽(@{u})을 보는 이유는, **아직 푸시 안 된 워커 변경은 배포할 수 없기**
# 때문이다. 올라가 있는 것만 배포 대상이다.
# 브랜치 이름을 박지 않는다 — 위 ahead 계산과 같은 기준을 쓴다.
last_worker=$(git log -1 --format=%H '@{u}' -- '*/worker/*.js' 2>/dev/null)

if [ -n "$last_worker" ]; then
  deployed=$(cat .claude/deployed 2>/dev/null)
  need=1
  if [ -n "$deployed" ] && git merge-base --is-ancestor "$last_worker" "$deployed" 2>/dev/null; then
    need=0                      # 그 커밋까지는 이미 배포했다
  fi
  if [ "$need" -eq 1 ]; then
    who=$(git show --name-only --format='' "$last_worker" 2>/dev/null |
          grep 'worker/.*\.js' | head -1 | sed 's|.*/||')
    line1="$line1  ${B}${R}배포 필요${X}"
    [ -n "$who" ] && line1="$line1 ${R}— ${who}${X}"
  fi
fi

printf '%b\n' "$line1"

# ── 둘째 줄 — 미커밋 ──────────────────────────────
# 하나도 없으면 줄을 만들지 않는다. 빈 줄이 남으면 화면만 차지한다.
# **자동 생성 파일은 세지 않는다 (2026-09-22 지시).** 이 줄은 「재권님이
# 하셔야 할 것만 띄운다」 로 만든 것인데, 도구가 만드는 파일은 하실 일이 없다.
# `check.py` 와 `update-sessions.py` 가 돌 때마다 바뀌어 **늘 떠 있었다.**
# 재권님이 「푸시 대기하는 거 뭐지?」 하고 물으셨는데 **푸시 대기는 0건**이었고
# 그 줄이었다.
#
# **이름을 박지 않는다.** 자동 생성 파일이 하나 더 생기면 그 순간 낡는다
# (「검사 도구에 대상 값을 박지 않는다」). 대신 **파일 쪽에 표시를 두고**
# 그것을 본다 — 만드는 도구가 `generated-by-tool` 을 적는다.
dirty_names=$(git status --porcelain 2>/dev/null | sed 's/^...//; s/^"//; s/"$//' |
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    head -c 300 "$f" 2>/dev/null | grep -q 'generated-by-tool' || printf '%s
' "$f"
  done)
dirty=$(printf '%s' "$dirty_names" | grep -c . )


# 미커밋이 없으면 둘째 줄은 건너뛴다. **셋째 줄은 그것과 무관하게 늘 나온다.**
if [ "$dirty" -gt 0 ]; then
names=$(printf '%s
' "$dirty_names" |
        sed 's/.*\///' |                    # 경로를 떼고 파일명만
        head -3 |
        awk '{ printf "%s%s", sep, $0; sep=" · " }')

line2="      ${D}미커밋 ${dirty}  ${names}"
[ "$dirty" -gt 3 ] && line2="$line2 외 $((dirty - 3))개"
line2="$line2${X}"

printf '%b\n' "$line2"
fi

# ── 셋째 줄: 주간 한도 사용률 ────────────────────────────────
#
# 재권님 지시 (2026-09-22) — 「주간 사용량을 보고싶은데 **이것만** 추가할수있나?」
# 위 두 줄은 그대로 두고 아래에 붙인다.
#
# **받아 온 맥용 스크립트를 그대로 쓰지 않았다.** 이 PC 에 `jq` 가 없고
# `stat -f` · `date -j` 도 GNU 에서 안 된다. 그리고 **값의 모양이 달랐다** —
# 상태줄 입력을 찍어 확인했다.
#
#     .rate_limits.seven_day.used_percentage   32        ← 정수다
#     .rate_limits.seven_day.resets_at         1790528400 ← ISO 가 아니라 유닉스 초다
#
# **값이 없어도 줄을 없애지 않는다.** 줄 수가 오락가락하면 화면이 들썩인다.
week=$(printf '%s' "$STDIN_JSON" | python -c "
import sys, json, datetime
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
try:
    d = json.load(sys.stdin)['rate_limits']['seven_day']
    pct = int(round(float(d['used_percentage'])))
    at = datetime.datetime.fromtimestamp(float(d['resets_at']))
    n = max(0, min(10, pct // 10))
    print('%d|%s|%d/%d %02d:%02d' % (pct, '#' * n + '-' * (10 - n),
                                     at.month, at.day, at.hour, at.minute))
except Exception:
    print('||')
" 2>/dev/null)

pct=${week%%|*}
rest=${week#*|}
bar=${rest%%|*}
at=${rest#*|}

if [ -n "$pct" ]; then
  # 색은 맨 위에 모아 둔 것을 쓴다 (「같은 값은 한 곳에만 둔다」).
  C=$G
  [ "$pct" -ge 70 ] && C=$Y
  [ "$pct" -ge 90 ] && C=$R
  printf '%b\n' "      ${D}주간 한도${X} ${C}${pct}%${X} ${D}[${bar}]  ${at} 초기화${X}"
else
  printf '%b\n' "      ${D}주간 한도 --${X}"
fi
