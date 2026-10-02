# -*- coding: utf-8 -*-
"""한국어 아닌 답을 턴 끝에서 잡는다 — Stop 훅 (2026-10-02 지시).

재권님 말씀 — 「이거 개념정의한테 얘기해 훅 만들라고」(개발 창 · 작업우선순위 경유).
그날 오전 한 세션이 재권님께 드리는 보고를 내리 영어로 썼고 재권님이 「넌 왜 영어로만 하나?」 하셨다.
CLAUDE.md 「응답 규칙」 의 「한국어 외 혼용 금지」 는 있었는데 **검사가 없었다** — 2026-09-30 일본어에 이어 두 번째다.

무엇을 세나 — 이번 턴(마지막 사람 말 뒤)에 세션이 쓴 글 덩어리 하나하나. **세션 간 메시지도 「사람 말」 로 본다** —
그래서 재권님께 드리는 답만이 아니라 **세션 간 메시지에 답하는 턴도** 걸린다(「한국어 외 혼용 금지」 는 세션 간 메시지에도 걸린다).
  코드블록 · 백틱 · 주소 · 경로 · 해시를 지운 뒤 한글 글자와 라틴 글자를 센다.
  **라틴 비율이 LIMIT 를 넘는 덩어리가 하나라도 있으면** 걸린다. 글자가 MIN 보다 적은 덩어리는 안 센다.
  가나 · 한자가 KANA_MIN 이상 섞인 덩어리도 걸린다(2026-09-30 「コミットを確認」 · 한자는 창구 검토로 더함 —
  작업우선순위는 「한국어 답에도 드물게 쓰인다」 로 빼자는 의견. qa 재생으로 한국어 답의 한자 수를 재서 정한다).
  빼는 것 — 코드블록 · 백틱 안 · URL · 경로 · 파일 이름 · 해시(7~40 hex) · 대문자_스네이크(상수 · tr_id) · 세션 주소 이름(kjcstudio-b4).

가르는 값은 재서 정했다 (2026-10-02 · 전 세션 기록의 최종 답 6,939건).
  라틴 비율 50% 초과 57건 — 거의 전부 문장이 통째로 영어(그날 오전 보고 · 중간 안내)
  50~80% 사이는 2건뿐 — 갈림이 뚜렷하다
  25~50% 는 Cloudflare 메뉴 이름처럼 영어 낱말이 많은 **정상 한국어 답**이다 → 걸리면 안 된다
  그래서 LIMIT 0.5 → qa 재시험(턴 7,123)에서 남은 오탐 셋이 50~52% 라 **0.55** 로 올렸다. 막힐 턴 ≈98 · 오탐 0.

걸리면 턴을 끝내지 않고(decision: block) 「한국어로 다시 써 주십시오」 를 돌려준다. 같은 턴에 두 번 막지 않는다 —
`stop_hook_active` 면 지나간다(무한 반복 방지). 막을지 알리기만 할지는 qa 시뮬레이션으로 정한다
(`KJC_KOREAN_HOOK=block|look|off`).
"""
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODE = os.environ.get("KJC_KOREAN_HOOK", "look")    # 기본은 알리기만 — 막을지는 qa 뒤 재권님 (작업우선순위 감사)
LIMIT = 0.55    # 라틴 / (한글 + 라틴) — 0.5 바로 위 오탐 셋이 빠지고 진짜 영어(거의 80% 이상)는 그대로 걸린다(qa 재시험)
MIN = 20        # 한글 + 라틴 글자 수가 이보다 적으면 안 센다 — 「OK」 · 「done」 한 줄 같은 것
KANA_MIN = 5

STRIP = [re.compile(p, f) for p, f in (
    (r"<system-reminder>.*?(</system-reminder>|$)", re.S),   # 시스템 알림이 글 끝에 붙어 나온 것(qa 재생 28턴)
    (r"\[SYSTEM NOTIFICATION[^\]]*\].*", re.S),
    (r"```.*?```", re.S), (r"`[^`\n]*`", 0), (r"https?://\S+", 0),
    (r"^(    |\t).*$", re.M),                                # 4칸 들여쓴 블록 — 이 저장소 문서 버릇(qa 재생 오탐 일곱의 공통)
    (r"\b[A-Za-z]:\\[^\s]*", 0),                            # 윈도우 경로 C:\…
    (r"(~|\.{0,2})/[\w.\-/가-힣]+", 0),
    (r"\b[\w\-]+\.(py|js|html|css|md|json|sh|command|plist|jsonl|db)\b", 0),
    (r"\b[0-9a-f]{7,40}\b", 0),
    (r"\b[A-Z][A-Z0-9]*(_[A-Z0-9]+)+\b", 0),            # 대문자_스네이크 — 상수 이름 · KIS tr_id (창구 검토)
    (r"\b[A-Z]{2,}[0-9]{4,}[A-Z0-9]*\b", 0),           # FHKST01010100 꼴 tr_id
    (r"\b[a-z][\w]*-[0-9a-f]{2}\b", 0))]              # 세션 주소 이름 kjcstudio-b4 · kjc-staging-10
HAN = re.compile(r"[가-힣]")
LAT = re.compile(r"[A-Za-z]")
KANA = re.compile("[\u3040-\u30ff\u4e00-\u9fff]")   # 가나 + 한자 — 일본어 · 중국어 혼용(창구 검토)


def clean(t):
    for r in STRIP:
        t = r.sub(" ", t)
    return t


def judge(text):
    """걸리면 이유 한 줄, 아니면 None."""
    c = clean(text)
    h, l, k = len(HAN.findall(c)), len(LAT.findall(c)), len(KANA.findall(c))
    if k >= KANA_MIN:
        return "가나 · 한자 %d자" % k
    if h + l < MIN:
        return None
    r = l / (h + l)
    if r > LIMIT:
        return "라틴 글자 %d%% (한글 %d · 라틴 %d)" % (round(r * 100), h, l)
    return None


def tail_lines(path):
    """끝에서 거꾸로 읽어 마지막 사람 말까지의 줄 — 기록 크기와 무관하게 짧다(qa: 163MB 를 다 읽으면 1.1초)."""
    try:
        f = open(path, "rb")
    except OSError:
        return []
    with f:
        f.seek(0, 2)
        size, chunk = f.tell(), 1 << 20
        while True:
            start = max(0, size - chunk)
            f.seek(start)
            lines = f.read().decode("utf-8", "ignore").splitlines()
            if start:
                lines = lines[1:]                     # 잘린 첫 줄
            if start == 0 or any(_human(l) for l in lines):
                return lines
            chunk *= 4


def _row(line):
    try:
        return json.loads(line)
    except ValueError:
        return None


def _human(line):
    if '"user"' not in line:
        return False
    r = _row(line)
    if not r or r.get("type") != "user" or r.get("isSidechain"):
        return False
    c = (r.get("message") or {}).get("content")
    return isinstance(c, str) or (isinstance(c, list) and any(
        isinstance(b, dict) and b.get("type") == "text" for b in c))


def turn_texts(path):
    """마지막 사람 말 뒤에 세션이 쓴 글 덩어리들. 도구 결과는 사람 말이 아니다.
    **시스템이 넣은 글은 뺀다** — 한도 · API 오류 문구가 assistant 줄(model "<synthetic>" · isApiErrorMessage)로 남아
    세션 글로 잡혔다(qa 재생 48턴). 안 빼면 한도에 걸린 턴마다 막고 → 다시 부르고 → 또 한도가 된다."""
    texts = []
    for line in tail_lines(path):
        if _human(line):
            texts = []
            continue
        r = _row(line)
        if not r or r.get("type") != "assistant" or r.get("isSidechain") or r.get("isApiErrorMessage"):
            continue
        m = r.get("message") or {}
        if m.get("model") == "<synthetic>":
            continue
        for b in m.get("content") or []:
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip():
                texts.append(b["text"])
    return texts


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if MODE == "off" or data.get("stop_hook_active"):
        return 0
    hits = []
    # 마지막 답은 입력의 last_assistant_message 로 본다 — 훅이 돌 때 기록 파일에 아직 안 써진 경우가 있어
    # 일곱 번 중 다섯 번 빗나갔다(qa 실측). 기록 파일은 같은 턴의 중간 글에만 쓴다
    texts = turn_texts(data.get("transcript_path") or "")
    last = (data.get("last_assistant_message") or "").strip()
    if last and last not in [t.strip() for t in texts]:
        texts.append(last)
    for t in texts:
        why = judge(t)
        if why:
            hits.append("  · %s — 「%s…」" % (why, t.strip().replace("\n", " ")[:50]))
    if not hits:
        return 0
    reason = ("한국어가 아닌 글이 있습니다 — CLAUDE.md 「응답 규칙」 의 「한국어 외 혼용 금지」. "
              "중간 안내도 같습니다. 같은 내용을 한국어로 다시 써서 답을 마쳐 주십시오 "
              "(코드 · 경로 · 명령은 백틱 안이면 그대로 둡니다).\n" + "\n".join(hits[:5]))
    if MODE == "block":
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    else:
        print(json.dumps({"systemMessage": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
