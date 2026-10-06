# -*- coding: utf-8 -*-
"""본문에서 묻고 맨 아래 확인란이 없는 답을 턴 끝에서 잡는다 — Stop 훅 (2026-10-06 지시).

재권님 말씀 — 「물어볼 때는 줄(────)로 감싸는 게 아니었나? 개념정의한테 훅으로 만들어 달라고 해」
(16:3x · 주식페이지_개발2 창). 그 세션 답 둘이 본문 「… 은 검수 뒤에 따로 여쭙겠습니다」 로 끝나고 확인란이 없었다.
룰은 CLAUDE.md 「재권님이 확인하실 것은 맨 아래에 둔다」 — 그 절의 「무엇이 검사하나」 가 이것이다.

판정 — 마지막 답 하나만 본다.
  확인란이 있다 — 답 끝쪽에 「────」 / ▶ 줄 / 「────」 (코드블록 밖) → 통과
  「지금 답하실 것은 없습니다」 가 있다 → 통과 (물을 것이 없다는 것을 끝줄로 보인다 · 작업우선순위 의견)
  그 밖에 본문에 묻는 말(ASK)이 있다 → 막는다. 확인란이 없는 답에서는 「여쭙겠습니다」 도 묻는 말로 센다
    — 확인란이 있는 답의 「그 다음에 여쭙겠습니다」 는 「하나만 둔다」 를 지키는 알림이라 그대로 둔다(창구 의견)
  세지 않는 자리 — 코드블록 · 백틱 · 「 」 · 표 칸(| 로 시작하는 줄) · ▶ 줄. 남의 물음을 옮겨 적은 경우가 많다

함께 잡는 것 — 확인란 ▶ 줄의 백틱 없는 http · 코드블록 안에 든 ▶ 줄(그 안은 주소가 안 눌린다).

잰 값(16:5x · qa 재생 · 최종 답 8,205) — 걸림 520 · 오탐 ≈140 중 125 가 「여쭙겠습니다」 —
그것은 설계대로다(확인란 없는 답의 「여쭙겠습니다」 는 묻는 것 · 재권님 승인). 놓침 167(「갈까요?」 꼴)은 물음표 꼴로 더했다. 「원하시면 말씀해 주십시오」 처럼 애매한 것도 섞이는데
확인란을 두거나 「지금 답하실 것은 없습니다」 를 적으면 통과한다.

같은 턴에 두 번 막지 않는다(`stop_hook_active`). `KJC_CONFIRM_HOOK=block|look|off` — 기본은 알리기만.
"""
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODE = os.environ.get("KJC_CONFIRM_HOOK", "look")
NONE = "지금 답하실 것은 없습니다"
NONE_RE = re.compile(r"답하실\s*(것|일)\s*[은이]?\s*없")   # 「지금 재권님이 답하실 것은 없습니다」 처럼 낱말이 끼어도(qa 재생 10건)
ASK = re.compile(r"할까요|하시겠습니까|될까요|맞습니까|괜찮을까요|좋을까요|드릴까요|볼까요|넘길까요"
                 r"|말씀해 주십시오|정해 주십시오|골라 주십시오|주시겠습니까"
                 r"|[가-힣]+까요\s*[?？]")    # 「갈까요?」 · 「합칠까요?」 — 동사를 하나씩 적으면 구멍이 난다(qa 재생 놓침 167)
LATER = re.compile(r"여쭙겠습니다|여쭈겠습니다")
RULE = re.compile(r"[─━]{4,}")
FENCE = re.compile(r"```.*?```", re.S)
ARROW = "▶"


def body(t):
    """세지 않는 자리를 뺀 본문."""
    t = FENCE.sub("", t)
    t = re.sub(r"`[^`\n]*`", "", t)
    t = re.sub(r"「[^」]*」", "", t)
    t = re.sub(r"[\"“][^\"”\n]*[\"”]", "", t)     # 큰따옴표 인용도 남의 말(qa 재생 9건)
    return "\n".join(l for l in t.splitlines() if not l.lstrip().startswith("|") and ARROW not in l)


def box_lines(t):
    """코드블록 밖의 확인란 ▶ 줄들 — 위 줄이 「────」 이고 아래 몇 줄 안에 「────」 가 있는 것."""
    L = [l.strip() for l in FENCE.sub("", t).splitlines() if l.strip()]
    out = []
    for i, l in enumerate(L):
        if ARROW in l and i and RULE.fullmatch(L[i - 1]) and any(RULE.fullmatch(x) for x in L[i + 1:i + 4]):
            out.append(l)
    return out


def judge(t):
    """걸리면 이유 목록."""
    why = []
    boxes = box_lines(t)
    for f in FENCE.findall(t):
        if ARROW in f:
            why.append("확인란이 코드블록 안에 있습니다 — 그 안은 주소가 안 눌립니다. 「────」 를 글자로 직접 적습니다")
            break
    for l in boxes:
        if re.search(r"https?://", re.sub(r"`[^`\n]*`", "", l)):
            why.append("확인란의 주소가 백틱으로 안 감싸였습니다 — `http://…` 꼴로")
            break
    if not boxes and not NONE_RE.search(t):
        b = body(t)
        m = ASK.search(b) or LATER.search(b)
        if m:
            why.append("본문에서 묻는데(「%s」) 맨 아래 확인란이 없습니다" % m.group(0))
    return why


def last_text(path):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - (1 << 20)))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("type") != "assistant" or r.get("isSidechain") or r.get("isApiErrorMessage"):
            continue
        m = r.get("message") or {}
        if m.get("model") == "<synthetic>":
            continue
        t = [b.get("text", "") for b in m.get("content") or [] if isinstance(b, dict) and b.get("type") == "text"]
        if any(x.strip() for x in t):
            return "\n".join(t)
    return ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if MODE == "off" or data.get("stop_hook_active"):
        return 0
    text = data.get("last_assistant_message") or last_text(data.get("transcript_path") or "")
    why = judge(text or "")
    if not why:
        return 0
    reason = ("CLAUDE.md 「재권님이 확인하실 것은 맨 아래에 둔다」. 재권님이 답하실 것은 답 맨 아래 한 자리에\n"
              "────────────────────────────\n▶ 묻는 말 한 줄\n────────────────────────────\n"
              "으로 둡니다. 물을 것이 없으면 끝에 「%s」 한 줄을 적습니다.\n" % NONE
              + "\n".join("  · " + w for w in why))
    if MODE == "block":
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    else:
        print(json.dumps({"systemMessage": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
