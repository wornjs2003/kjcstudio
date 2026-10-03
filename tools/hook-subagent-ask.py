# -*- coding: utf-8 -*-
"""하위 작업자 훅 — 하위를 띄우기 전에 「재권님께 여쭈었습니까」 를 본다 (2026-10-03 지시).

재권님 말씀 — 「나눌지 말지 판단은 누가 하지?」 → 「나한테 물어보고 하도록 해줘」 → 룰이 들어간 뒤 「훅도 만들어줘」.
룰은 CLAUDE.md 「일이 여럿이면 하위 작업자에게 나눈다」 의 「나눌지도 재권님께 여쭌다」 에 있다.

PreToolUse(Agent)에서 돈다. 하위를 띄우는 지시문(prompt) 안에 **「재권님 허락:」 줄**이 있어야 지나간다.

    재권님 허락: 「응 둘로 나눠」(10-03 09:3x)

**기계는 허락을 못 본다** — 그 줄이 곧 세션의 서명이다(메인 가드의 `KJC_MAIN_OK=1` 과 같은 모양). 그래서
지나간 것을 `logs/subagent-ok.log` 에 한 줄 남긴다(시각 · 폴더 · 세션 · 허락 줄 · 하위 설명). 막는 겹이 뚫려도
세는 겹은 남는다 — 받지 않고 적었으면 위반이고 그 목록에서 드러난다.

MODE(`KJC_SUBAGENT_HOOK`) — block(기본) 이면 막고, look 이면 알리기만, off 면 안 돈다.

읽기만 하는 하위(`Explore` · `claude-code-guide`)는 보지 않는다 — 일을 나누는 것이 아니라 찾아보는 것이다.

못 보는 것 — 허락 줄이 진짜 재권님 답인지 · Bash 로 `claude -p` 를 띄우는 것 · Workflow(그 도구는 사용자가
직접 부르셔야만 돈다 — 따로 막지 않는다).
"""
import json
import os
import re
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODE = os.environ.get("KJC_SUBAGENT_HOOK", "block")    # block | look | off
# 읽기만 하는 하위는 「일을 나누는 것」 이 아니라 빼다 — 파일 검색 · 공식 문서 찾기 (2026-10-03 재권님 「해줘」).
# qa 재생에서 기록의 Agent 호출 18건 중 7건이 이 둘이었다.
READ_ONLY = {"Explore", "claude-code-guide"}
# **줄 맨 앞 · 같은 줄 안에서만** 본다 (qa 시뮬레이션 2026-10-03) — 「재권님 허락:」 만 쓰고 줄을 바꾸면 다음 줄을
# 허락으로 잡았고, 지시문 한가운데의 설명(「…허락: 줄이 있어야」)도 통과했다.
# 마크다운 꼴(「- 재권님 허락:」 · 「**재권님 허락:**」 · 「> …」)은 정상 허락이다 — 줄 앞 목록·인용 표시와 굵게를 허용한다(qa 재검).
MARK = re.compile(r"^[ \t]*(?:[-*•>][ \t]*)*(?:\*\*)?재권님[ \t]*허락[ \t]*(?:\*\*)?[:：](?:\*\*)?[ \t]*(\S[^\n]{0,200})", re.M)


def log(root, line):
    try:
        os.makedirs(os.path.join(root, "logs"), exist_ok=True)
        with open(os.path.join(root, "logs", "subagent-ok.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def main():
    if MODE == "off":
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0                                   # 못 읽었으면 막지 않는다 — 훅이 일을 멈추게 하면 안 된다
    if data.get("tool_name") != "Agent":
        return 0
    ti = data.get("tool_input") or {}
    if str(ti.get("subagent_type") or "") in READ_ONLY:
        return 0
    prompt = str(ti.get("prompt") or "")
    desc = str(ti.get("description") or "")[:60]
    m = MARK.search(prompt)
    root = data.get("cwd") or os.getcwd()
    if m:
        ok = m.group(1).splitlines()[0].strip()
        log(root, "\t".join([time.strftime("%Y-%m-%d %H:%M:%S"), os.path.basename(root),
                             os.environ.get("CLAUDE_CODE_SESSION_ID", "")[:8], ok[:120], desc]))
        return 0
    msg = ("하위 작업자를 띄우기 전에 재권님께 여쭙니다 — CLAUDE.md 「나눌지도 재권님께 여쭌다」(2026-10-03 지시).\n"
           "  ① 맨 아래 확인란 하나로: 「이 일을 하위 N 으로 나눠 돌릴까요 — 각자 무엇을」 (주식 레인은 창구를 거쳐)\n"
           "  ② 답을 받은 뒤 하위 지시문 첫 줄에:  재권님 허락: 「<받은 답 그대로>」(시각)\n"
           "  「쪼갤 값이 없으면 쪼개지 않는다」 기준에 안 드는 일이면 하위 없이 직접 하십시오.\n"
           "  허락 줄은 기록(logs/subagent-ok.log)에 남습니다 — 받지 않고 적으면 위반입니다.")
    if MODE == "block":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": msg}}, ensure_ascii=False))
    else:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "additionalContext": msg}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
