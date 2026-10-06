# -*- coding: utf-8 -*-
"""찍는 창 크기 훅 — 세션이 화면을 찍을 때 창 크기를 직접 정하면 막는다 (2026-10-06 지시).

재권님 말씀 — 「그릴때 차트창 싸이즈가 지맘대로 또 그려서 보여주네 … 왜 계속 재발하는거지?」 → 「응 그렇게 해줘」.
세션마다 헤드리스 크롬 창 크기를 제각각 골라(기록에 열 가지 넘게) 차트 창이 매번 다른 크기로 그려졌다.
크기는 `tools/view-size.json`(재권님 창에서 잰 값) 한 곳이고, 찍기는 `tools/shot.py` 로 한다.

PreToolUse(Bash · Write · Edit)에서 돈다. 세는 것 —
  Bash   명령에 창 크기를 정하는 말이 있다: `--window-size=W,H` · `setDeviceMetricsOverride` · `set_viewport_size` ·
         `viewport` 에 width/height · `resize_window`
  Write · Edit   세션 임시 폴더 · `temp/` 의 .py · .sh · .js · .html 에 위 말이 들어간다(스크립트로 돌려 피하는 길)
**지나가는 것** — 재권님 창 크기와 같은 값 · 폰(폭 500 이하 · 높이는 무엇이든) · 읽기·기록 명령(grep · sed · git …에 크롬이 안 붙은 것) · 우리 도구를 부르는 명령(`tools/shot.py` · `check-layout.py` ·
`check-chart.py` · `measure-resource.py` — 그 안의 크기는 도구가 정한다) · 저장소 안 다른 파일 편집(도구 코드는 레인 룰의 자리).

MODE(`KJC_VIEW_HOOK`) — block(기본) · look · off. 막는 말이 `tools/shot.py` 쓰는 법을 알려 준다.
못 보는 것 — 변수에 담은 크기 · 브라우저 확장(claude-in-chrome)으로 실제 창을 키우는 것.
"""
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODE = os.environ.get("KJC_VIEW_HOOK", "block")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OK_TOOLS = re.compile(r"tools/(shot|check-layout|check-chart|measure-resource)\.py")
SIZE = re.compile(r"--window-size[= ](\d+)\s*[,x]\s*(\d+)|setDeviceMetricsOverride|set_viewport_size|resize_window|"
                  r"viewport\W{0,6}\{?\s*['\"]?width['\"]?\s*[:=]\s*(\d+)")
PHONE = (390, 844)
PHONE_MAX_W = 500         # 폭이 이 이하면 폰 화면이다 — 높이는 길게 찍어도 된다(세로로 긴 폰 화면 · qa 기록 28건)
# 읽기·기록 명령은 크기 낱말이 들어 있어도 찍는 것이 아니다 — grep · sed · git 커밋 메시지 등(qa 재생에서 막혔다)
READ_FIRST = re.compile(r"^\s*(?:cd\s+\S+\s*&&\s*)?(grep|rg|sed|cat|head|tail|less|wc|git|echo|printf)\b")


def allowed_size():
    try:
        d = json.load(open(os.path.join(ROOT, "tools", "view-size.json"), encoding="utf-8"))
        return int(d["width"]), int(d["height"])
    except Exception:
        return None


def hits(text):
    out = []
    ok = {allowed_size(), PHONE}
    for m in SIZE.finditer(text or ""):
        if m.group(1) and ((int(m.group(1)), int(m.group(2))) in ok or int(m.group(1)) <= PHONE_MAX_W):
            continue                                   # 재권님 창 크기 · 폰(폭 500 이하)이면 지나간다
        out.append(m.group(0)[:60])
    return out


def main():
    if MODE == "off":
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    tool, ti = data.get("tool_name"), data.get("tool_input") or {}
    found = []
    if tool == "Bash":
        cmd = str(ti.get("command") or "")
        if OK_TOOLS.search(cmd) and not re.search(r"--window-size|setDeviceMetricsOverride", cmd):
            return 0
        if READ_FIRST.match(cmd) and not re.search(r"(?i)chrome|chromium|headless|playwright|puppeteer", cmd):
            return 0                                   # 읽기 · 커밋 메시지 — 찍지 않는다
        found = hits(cmd)
    elif tool in ("Write", "Edit", "MultiEdit"):
        path = str(ti.get("file_path") or "")
        tmp = "/scratchpad/" in path or "/temp/" in path or path.startswith("/private/tmp/") or path.startswith("/tmp/")
        if not tmp or not path.endswith((".py", ".sh", ".js", ".html", ".mjs")):
            return 0
        found = hits(str(ti.get("content") or ti.get("new_string") or ""))
    if not found:
        return 0
    size = allowed_size()
    msg = ("화면을 찍는 창 크기를 직접 정하지 않습니다 — 「찍는 창 크기도 창 크기다」(2026-10-06 지시).\n"
           "  걸린 것: %s\n"
           "  찍기는:  python3 tools/shot.py <주소> <저장할 png>   (재권님 창 %s · 폰은 --phone)\n"
           "  세션마다 크기가 달라 차트 창이 매번 다른 크기로 그려졌습니다. 크기는 tools/view-size.json 한 곳입니다."
           % (" · ".join(found[:3]), ("%d×%d" % size) if size else "— 아직 안 쟀음 · 개념정의에 알리십시오"))
    if MODE == "block":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                  "permissionDecisionReason": msg}}, ensure_ascii=False))
    else:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": msg}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
