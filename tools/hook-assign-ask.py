#!/usr/bin/env python3
"""나르는 자리가 세션에 일을 주기 전에 재권님께 먼저 여쭈었는지 본다 — PreToolUse SendMessage 훅 (2026-11-20 지시).

재권님 말씀 그대로다 — 「일 바로 주지말고 일이 없다고 훅이 들어오면 내게 물어보고 줘야지」 → 「훅으로 만들어야지」 →
「그게 아니고 니가 일주기전에 나한테 물어보라고 한거 훅으로 만들라고」(작업우선순위 창 · 14:59).
그날 작업우선순위가 일 없는 세션 다섯에 다음 일을 바로 줬다(14:51 · 14:5x).

**무엇을 보나** — 작업우선순위 · 홈페이지_정리 가 SendMessage 로 보내는 글이 일을 주는 꼴(「다음 일」 · 「지금 시작」 · 「맡아 주십시오」 ·
「착수해 주십시오」 · 「--doing 으로」)이면, 그 세션 기록에서 **재권님이 마지막으로 치신 말씀**을 찾는다.
    그 말씀이 고르신 답 · 시키신 말(가 · 나 · 다 · 응 · 「…로 해」 · 「…하라고 해」 · 「…넘겨」 · 「…시켜」 · 「…줘」)이면 통과 — 재권님 말씀을 나르는 것이다
    아니면(그 뒤로 다른 세션 메시지 · 알림만 왔으면 그것은 재권님 말씀이 아니라 건너뛰고 더 앞의 말씀을 본다) 알린다 · 막는다
물음 · 결과 알림 메시지는 일을 주는 낱말이 없어 안 걸린다.
짧은 답(「응」 · 「가」)은 그 바로 앞 답의 확인란 ▶ 에 받는 세션 이름이 있을 때만 그 일의 답으로 본다(작업우선순위 검토 11-20).
**통과 하나 더** — 메시지가 「재권님 「…」」 를 인용했고 그 말씀이 그 창 기록에 재권님이 치신 말로 있고 그 말이 시키신 말(짧은 답 · 물음 꼴 빼고)이면 통과(지시 나르기 · /clear 뒤 다시 나름 · 11-20 15:27 사례).

**한계** — 긴 말씀(「…하라고 해」)이 다른 세션 일이어도 통과한다 · 무엇을 시키셨는지 뜻은 기계가 못 본다.

`KJC_ASSIGN_HOOK=look|block|off` — 처음은 알리기만(look) → qa 재생 → 막기(block)로 올릴지는 재권님.
못 읽으면(기록 · herdr) 조용히 지나간다 — 막는 훅이 못 읽어서 일을 멈추게 하지 않는다.
"""
import importlib.util
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODE = os.environ.get("KJC_ASSIGN_HOOK", "look")
CARRIERS = ("작업우선순위", "홈페이지_정리")
HERE = os.path.dirname(os.path.abspath(__file__))
ASSIGN = re.compile(r"다음 일|지금 시작|맡아 주십시오|착수해 주십시오|착수하십시오|시작해 주십시오|--doing 으로")
# 「가로 하고 개발1은 라」 — 후보 글자 뒤 로 · 은 · 는 · 요 · 끝(11-20 15:07 헛걸림 · 작업우선순위 찾음)
PICK = re.compile(r"^\s*(\(?[가나다라]\)?|응|네|그래|좋아|맞아|해)(\s|$|[.!,])|(?<![가-힣])\(?[가나다라]\)?\s*(로|으로|은|는|요)?(\s|$|[.!,])"
                  r"|로\s*(해|하)|하라고\s*해|해\s*줘|시켜|주라고|넘겨|맡겨|줘\s*$|라고\s*$|만들어|해야지|하자")
# 긴 지시 글(「단타 목록 9시 5분에 굳히고 상위 10개만 보인다 …」) — 15자 넘고 물음 꼴(? · …지 · …나 · …까 · …니)로 안 끝나면 시키신 말로 본다(qa 재생 11-20 08:45)
ASKEND = re.compile(r"([?？]|지|나|까|니|냐)\s*[.!]?\s*$")


def is_order(t):
    return bool(PICK.search(t)) or (len(t) >= 15 and not ASKEND.search(t))


def last_order(path):
    """기록에서 재권님이 마지막으로 치신 말씀과 그 바로 앞 답 글 — 도구 결과 · 다른 세션 메시지 · 시스템 글은 건너뛴다.
    못 읽으면 (None, None) · 말씀을 못 찾으면 ("", "")."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - (2 << 20)))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except OSError:
        return None, None
    order = None
    for line in reversed(lines):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("isMeta") or r.get("isSidechain"):
            continue
        c = (r.get("message") or {}).get("content")
        if isinstance(c, list):
            c = "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
        c = (c or "").strip()
        if order is None:
            if r.get("type") == "user" and c and not c.startswith("<"):   # 도구 결과 · 다른 세션 메시지 · 시스템 알림 · 명령은 건너뜀
                order = c
            continue
        if r.get("type") == "assistant" and c:
            return order, c                     # 그 말씀 바로 앞에 세션이 쓴 답
    return (order or ""), ""


QUOTE = re.compile(r"재권님\s*「([^」]{4,})」")


def quoted_said(path, msg):
    """메시지가 인용한 재권님 말씀(「재권님 「…」」)이 그 창 기록에 재권님이 치신 말로 있으면 True — 지시를 나르는 것이다
    (작업우선순위 11-20 15:27 · /clear 뒤 다시 나른 15:26 지시가 헛걸림). 앞 열 글자로 견준다."""
    qs = [q.strip()[:10] for q in QUOTE.findall(msg) if len(q.strip()) >= 4]
    if not qs:
        return False
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - (2 << 20)))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except OSError:
        return False
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        c = (r.get("message") or {}).get("content")
        if r.get("type") != "user" or r.get("isMeta") or not isinstance(c, str) or c.startswith("<"):
            continue
        if any(q in c for q in qs) and is_order(c) and not SHORT.search(c):
            return True     # 인용한 말이 시키신 말일 때만 — 꾸중 · 물음(「왜 또 아무말 없지?」)은 안 됨 · 짧은 답은 아래 ▶ 대조로(qa 재생 11-20 15:31)
    return False


SHORT = re.compile(r"^\s*(\(?[가나다라]\)?|응|네|그래|좋아|맞아|해)\s*[.!]?\s*$")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if MODE == "off" or data.get("tool_name") != "SendMessage":
        return 0
    msg = str((data.get("tool_input") or {}).get("message") or "")
    if not ASSIGN.search(msg):
        return 0
    try:
        spec = importlib.util.spec_from_file_location("session_addr", os.path.join(HERE, "session-addr.py"))
        sa = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sa)
        me = ((sa.labels() or {}).get(data.get("session_id") or "") or ("", ""))[0]
    except Exception:
        return 0
    if me not in CARRIERS:
        return 0
    order, prev = last_order(data.get("transcript_path") or "")
    if order is None:
        return 0
    targets = set()
    for row in (sa.table() or []):              # 받는 세션 — to 주소 · 글에 나온 이름
        if row[1] == str((data.get("tool_input") or {}).get("to") or "") or row[0] in msg or row[0].replace("주식페이지_", "") in msg:
            targets |= {row[0], row[0].replace("주식페이지_", "")}
    why = None
    if not is_order(order):
        why = "바로 앞 재권님 말씀(%s)이 그 일을 고르신 답이 아닙니다" % (("「%s」" % order[:40]) if order else "없음")
    elif SHORT.search(order) and targets:
        box = [l for l in (prev or "").splitlines() if l.strip().startswith("▶")]
        if not any(t and t in l for l in box for t in targets):
            # 짧은 「응 · 가」 는 바로 앞 답 확인란이 이 세션 일을 물었을 때만 그 일의 답이다(작업우선순위 검토 11-20)
            why = "재권님 「%s」 은 바로 앞 확인란의 다른 물음에 대한 답으로 보입니다(그 ▶ 에 이 세션이 없음)" % order[:10]
    if not why or quoted_said(data.get("transcript_path") or "", msg):
        return 0
    reason = ("세션에 일을 주는 메시지인데 %s — 후보를 ▶ 로 올려 재권님께 먼저 여쭙니다"
              "(재권님 「니가 일주기전에 나한테 물어보라고 한거 훅으로 만들라고」 11-20 · tools/hook-assign-ask.py)." % why)
    if MODE == "block":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": reason}}, ensure_ascii=False))
    else:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "[알림] " + reason}},
                         ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
