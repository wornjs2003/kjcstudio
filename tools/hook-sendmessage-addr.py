# -*- coding: utf-8 -*-
"""세션 이름으로 보내면 지금 주소로 바꿔 준다 — PreToolUse(SendMessage) 훅 (2026-10-02 지시).

재권님 말씀 — 「다른 세션에서 여기랑 대화가 안되는 곳이 있는데 … 재부팅이나 재시작시 발생하는데 재발 안하게 룰 만들어줘」.

**왜 끊기나** — SendMessage 의 이름(`kjcstudio-b4` 등)은 세션이 다시 뜰 때마다 바뀌고, 그 이름에 세션 이름이 없다.
그날 개발이 개념정의 주소를 몰라 작업우선순위를 거쳐 보냈고 재권님이 「왜 모르지..?」 하셨다. 같은 날 창구는 메인 폴더 창
넷을 못 갈라 개발2 몫을 개념정의에 보냈다. 연결 자체는 살아 있었다(2026-10-02 12:0x 여덟 곳 다 답함) — **주소를 몰랐다.**

**어떻게** — `to` 가 세션 이름(「세션 역할 분담」 표의 이름 · 창 이름)이면 `tools/session-addr.py` 의 셈으로
`uds:/tmp/cc-socks/<pid>.sock` 으로 바꿔 넘긴다(updatedInput). 기억하지 않고 **보낼 때마다 센다** — 재시작해도 안 낡는다.
이미 주소 꼴(uds: · ListAgents 이름)이면 손대지 않는다. 이름 맞추기는 session-addr.py 의 resolve() — 완전 일치, 없으면
끝 일치(「개발2」), 하나일 때만.

**권한은 안 건드린다** — 처음 판은 `permissionDecision: allow` 를 함께 내서 묻기가 걸린 세션에서 그 물음을 건너뛰게 했다
(작업우선순위 감사). qa 시험 H(2026-10-02)에서 결정 없이도 updatedInput 이 들어 바뀐 주소로 도착해서 뺐다. 단, 그 시험은
SendMessage 를 미리 허락해 둔 세션이었다 — **묻기가 걸린 세션에서 묻기가 그대로 뜨는지는 못 쟀다.**
이름이 둘 이상에 맞거나 하나도 안 맞으면 손대지 않고 지나간다 —
그때는 SendMessage 가 「그런 이름 없음」 으로 알린다(조용히 엉뚱한 곳에 가는 것보다 낫다).
"""
import importlib.util
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def session_addr():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session-addr.py")
    spec = importlib.util.spec_from_file_location("session_addr", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("tool_name") != "SendMessage" or os.environ.get("KJC_ADDR_HOOK") == "off":
        return 0
    ti = dict(data.get("tool_input") or {})
    to = (ti.get("to") or "").strip()
    if not to or to.startswith("uds:") or to == "main":
        return 0
    try:
        sa = session_addr()
        hit = sa.resolve(sa.table() or [], to)      # 맞추는 셈은 session-addr.py 한 곳
    except Exception:
        return 0                                    # 못 쟀으면 손대지 않는다
    if len(hit) != 1:
        return 0
    ti["to"] = hit[0][1]
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "updatedInput": ti}}, ensure_ascii=False))     # 결정(allow)을 안 낸다 — 권한은 그대로 두고 주소만 바꾼다
    return 0


if __name__ == "__main__":
    sys.exit(main())
