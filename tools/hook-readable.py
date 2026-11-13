#!/usr/bin/env python3
"""재권님께 드리는 글이 읽기 어려운 꼴이면 알린다 — Stop 훅 (2026-11-13 지시).

재권님 말씀 그대로다(개념정의 창 · 11-12 17:4x) — 「나한테 물어보고나 확인받을때 룰을 잡아. 말이 읽기 힘들고 어려워. …
이걸 항상 잘되게 할 룰이 있나? 하네스나 뭐 이런걸로 하면되나?」 → 룰 + 장치 안에 「응」(11-13 08:2x) → 문안에 「응 넣어」(11-13 12:1x).
룰은 CLAUDE.md 「재권님께 여쭙는 글은 읽기 쉽게 — 첫 줄에 정하실 것 · 짧은 줄 · 우리말」.

마지막 답만 센다 — 기계가 셀 수 있는 꼴 다섯:
    ① 확인란 ▶ 줄이 READ_BOX_MAX 자 넘음
    ② ▶ 줄에 코드 이름(백틱 안 · 주소 아님) · 파일 이름(확장자) · 영어 낱말(READ_EN_OK 밖)
    ③ 본문 한 줄에 가운뎃점(·)이 READ_DOTS_MAX 개 넘음 — 셋 넘게 늘어놓으면 줄로 나눈다
    ④ 본문에 코드 이름(백틱 안 · 주소 아님)이 READ_CODE_MAX 개 넘음
    ⑤ 빈 줄 없이 이어진 문단이 READ_PARA_MAX 자 넘음
세지 않는 자리 — 코드블록 · 「 」 인용 · 표 줄(| 로 시작) · 주소. 도구에 넘긴 글(세션 간 메시지 · 카드 메모 · 커밋 메시지)은 마지막 답이 아니라 안 센다.
못 본다 — 「쉬운 말인가」 의 뜻 · 첫 줄이 정말 요점인가.

`KJC_READABLE_HOOK=block|look|off` — 처음은 알리기만(look · 재권님 「응 넣어」 의 「처음엔 알리기만」). 값(상수)은 qa 재생으로 지난 답에서
몇이 걸리는지 · 잘못 걸리는 것을 잰 뒤 다듬고, 막기는 그 뒤 재권님께 여쭌다(hook-hash 와 같은 길).
같은 턴에 두 번 막지 않는다(`stop_hook_active`). 못 읽으면 조용히 지나간다. 걸린 것은 logs/readable.log 에 한 줄 남긴다(qa 가 센다).
"""
import json
import os
import re
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODE = os.environ.get("KJC_READABLE_HOOK", "look")
READ_BOX_MAX = 140        # ▶ 줄 글자 수 — 짧은 꼴(「앞서 HH:MM 에 여쭌 것 그대로입니다 — <물음 한 줄>」)이 들어가는 폭 · qa 재생으로 다듬는다
READ_DOTS_MAX = 3         # 한 줄 가운뎃점 — 현황 표 「하는 일」 칸 꼴(둘)이 안 걸리게(창구 검토)
READ_CODE_MAX = 3         # 본문 코드 이름 수
READ_PARA_MAX = 400       # 한 문단 글자 수
# 재권님이 쓰시는 영어 약어 · 이름 — 이 밖의 영어 낱말이 ▶ 줄에 있으면 센다(대소문자 그대로 견줌)
READ_EN_OK = {"PER", "PBR", "ROE", "EPS", "RSI", "MACD", "MA", "VWAP", "ETF", "KIS", "DART", "KRX", "WICS", "VI", "IR", "CPI", "PCE",
              "FOMC", "AI", "API", "CSS", "PNG", "VS", "Code", "Claude", "Insight", "Holdings", "Projects", "Debugging", "NXT", "qa",
              "OK", "UN", "J", "US", "KR", "EU", "JP", "SK", "LG", "Haiku", "Chrome", "Herdr",
              # qa 재생 11-13 에 잘못 걸린 낱말 — 지수 · 거래소 · 약어
              "STOXX", "CME", "HBM", "DB", "CNBC", "OpenDART", "SENSEX", "DAX", "KODEX", "KIND", "Opus", "Esc", "clear", "D", "S", "P", "HTML"}

FENCE = re.compile(r"```.*?(?:```|\Z)", re.S)
QUOTE = re.compile(r"「[^「」\n]*」")
URL = re.compile(r"https?://\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:com|co\.kr|kr|net|org|io)\b")   # 맨 도메인(thekjc.co.kr)도 주소
TICK = re.compile(r"`([^`\n]+)`")
FILE = re.compile(r"\b[\w./-]+\.(?:py|js|css|html|json|md|sh|plist|command|db|txt)\b")
EN = re.compile(r"(?<![A-Za-z0-9_&/])[A-Za-z][A-Za-z0-9_-]+")   # & · / 뒤는 앞 낱말의 일부(S&P500 · /clear)
LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "readable.log")


def last_text(path):
    """입력에 마지막 답이 없을 때만 기록 파일 끝에서 찾는다 — hook-hash.py 와 같은 셈."""
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
        if r.get("type") != "assistant" or r.get("isSidechain") or r.get("isApiErrorMessage") \
                or (r.get("message") or {}).get("model") == "<synthetic>":
            continue
        t = [b.get("text", "") for b in (r.get("message") or {}).get("content") or []
             if isinstance(b, dict) and b.get("type") == "text"]
        if any(x.strip() for x in t):
            return "\n".join(t)
    return ""


def codes(s):
    """백틱 안 이름 중 주소가 아닌 것."""
    return [x for x in TICK.findall(s) if not URL.match(x.strip())]


def check(text):
    t = FENCE.sub("\n", text or "")
    t = QUOTE.sub("「」", t)
    hits = []
    body = []
    for line in t.splitlines():
        s = line.strip()
        if s.startswith("▶"):
            plain = URL.sub("", TICK.sub(lambda m: "" if URL.match(m.group(1).strip()) else m.group(1), s))
            if len(plain) > READ_BOX_MAX:
                hits.append("① ▶ 줄 %d자(%d 넘음)" % (len(plain), READ_BOX_MAX))
            names = list(dict.fromkeys(codes(s) + FILE.findall(URL.sub("", TICK.sub("", s)))))   # 백틱 안 파일은 codes 가 셈
            rest = FILE.sub("", URL.sub("", TICK.sub("", s)))                      # 파일 이름은 위에서 셌다 — 두 번 안 셈
            en = [w for w in EN.findall(rest) if w not in READ_EN_OK and re.sub(r"[-_]?(\d+|n)$", "", w) not in READ_EN_OK]   # MA20 · STOXX50 · D-1
            if names or en:
                hits.append("② ▶ 줄에 코드 · 파일 · 영어 — " + " · ".join((names + en)[:4]))
            continue
        if s.startswith("|") or set(s) <= set("─-—= "):
            body.append("")
            continue
        if re.match(r"(?:[-*•]|\d+[.)])\s", s) or (line[:1] in " \t" and s):
            body.append("")             # 목록 한 항목은 따로 센다 — 짧은 목록이 한 문단으로 잡히던 것(qa 재생 11-13)
        body.append(s)
        dots = s.count(" · ")       # 띄어 쓴 것만 — 붙여 쓴 이름(「VI·급등」)은 한 낱말(qa 재생 11-13)
        if dots > READ_DOTS_MAX:
            hits.append("③ 한 줄 가운뎃점 %d개 — 「%s…」" % (dots, s[:24]))
    n = len({c.strip().rstrip("/").split("/")[-1] for x in body for c in codes(x)})   # 같은 이름은 한 번(경로 · 끝 이름 같게 · qa 재생 11-13)
    if n > READ_CODE_MAX:
        hits.append("④ 본문 코드 이름 %d개(%d 넘음)" % (n, READ_CODE_MAX))
    para = 0
    for x in body + [""]:
        if x:
            para += len(URL.sub("", x))
        else:
            if para > READ_PARA_MAX:
                hits.append("⑤ 문단 %d자(%d 넘음)" % (para, READ_PARA_MAX))
            para = 0
    out = []
    for h in hits:
        if h not in out:
            out.append(h)
    return out


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if MODE == "off" or data.get("stop_hook_active"):
        return 0
    text = data.get("last_assistant_message") or last_text(data.get("transcript_path") or "")
    try:
        hits = check(text)
    except Exception:
        return 0
    if not hits:
        return 0
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s\t%s\t%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), data.get("session_id", ""), " / ".join(hits)))
    except OSError:
        pass
    reason = ("재권님께 드리는 글이 읽기 어려운 꼴입니다 — " + " / ".join(hits[:4]) + ". 첫 줄에 무엇이 됐나 · 무엇을 정하시나를 한 문장으로, "
              "셋 넘게 늘어놓을 것은 줄로 나누고, 파일 · 코드 이름 · 영어 대신 우리말로(CLAUDE.md 「재권님께 여쭙는 글은 읽기 쉽게」).")
    if MODE == "block":
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    else:
        print(json.dumps({"systemMessage": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
