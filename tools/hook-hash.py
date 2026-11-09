#!/usr/bin/env python3
"""재권님께 드리는 글에 커밋 번호가 있으면 알린다 — Stop 훅 (2026-11-09 지시).

재권님 말씀 그대로다 — 「72f5ba1 이렇게 말하지 말라고 개념정의한테 룰 보완하라해」(창구 창 · 12:1x) → 문안에 「응」(15:3x).
룰은 CLAUDE.md 「재권님께 드리는 글에는 커밋 번호를 쓰지 않는다 — 일의 이름으로」.

마지막 답에서 7~12자리 16진 낱말을 모아 **이 저장소에 실제로 있는 커밋만** 센다(`git cat-file --batch-check`) —
숫자만 된 번호도 잡고, 색 · 카드 id · 우연한 16진 글자는 커밋이 아니라 안 걸린다(작업우선순위 검토).
백틱 안도 센다 — 가장 흔한 꼴이다. 코드블록 · 재권님 말씀 인용(「재권님 … 「…」」) · 주소는 뺀다(창구 검토 · qa 재생 11-09).

`KJC_HASH_HOOK=block|look|off` — 도구 기본은 알리기만(look) · settings.json 이 block 으로 부른다(2026-11-10 재권님 「응」 ·
qa 재생 11-09 — 잘못 걸린 것 0).
같은 턴에 두 번 막지 않는다(`stop_hook_active`). 못 읽으면 조용히 지나간다 — 막는 훅이 아니라서다.
"""
import json
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODE = os.environ.get("KJC_HASH_HOOK", "look")
FENCE = re.compile(r"```.*?(?:```|\Z)", re.S)
# 재권님 말씀 인용만 뺀다 — 「 」 바로 앞(열두 글자 안)에 「재권님」 이 있을 때. 세션이 카드 줄 · 제 안내를 「 」 로 옮긴 것은
# 재권님 눈에 번호가 보이는 꼴이라 센다(qa 재생 11-09 — 「 」 를 다 빼면 18턴이 샜고 재권님 인용은 표본에 없었다)
QUOTE = re.compile(r"재권님[^\n「」]{0,12}「[^「」]*」")
URL = re.compile(r"https?://\S+")
WORD = re.compile(r"(?<![0-9A-Za-z#])[0-9a-f]{7,12}(?![0-9A-Za-z])")


def last_text(path):
    """입력에 마지막 답이 없을 때만 기록 파일 끝에서 찾는다."""
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
            continue                    # API 오류 · 시스템이 넣은 글은 세션이 쓴 답이 아니다(qa 11-09)
        t = [b.get("text", "") for b in (r.get("message") or {}).get("content") or []
             if isinstance(b, dict) and b.get("type") == "text"]
        if any(x.strip() for x in t):
            return "\n".join(t)
    return ""


def candidates(text):
    t = FENCE.sub(" ", text or "")
    t = QUOTE.sub(" ", t)
    t = URL.sub(" ", t)
    seen = []
    for w in WORD.findall(t):
        if w not in seen:
            seen.append(w)
    return seen


def commits(cwd, words):
    """그중 이 저장소의 커밋인 것만."""
    if not words:
        return []
    r = subprocess.run(["git", "-C", cwd, "cat-file", "--batch-check"], input="".join(w + "^{commit}\n" for w in words),
                       capture_output=True, text=True, timeout=5)
    out = r.stdout.splitlines()
    return [w for w, line in zip(words, out) if not line.endswith("missing") and " commit " in line]


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if MODE == "off" or data.get("stop_hook_active"):
        return 0
    text = data.get("last_assistant_message") or last_text(data.get("transcript_path") or "")
    try:
        hits = commits(data.get("cwd") or os.getcwd(), candidates(text))
    except Exception:
        return 0
    if not hits:
        return 0
    reason = ("재권님께 드리는 글에 커밋 번호가 있습니다 — " + " · ".join(hits[:5]) + ". 일의 이름으로 써 주십시오"
              "(「글자 크기 단계」 · 「관심종목 목록 고침」 처럼 · 어디까지 갔는지는 가지 · 자리로). 번호는 카드 · 세션 간 메시지 · "
              "커밋 메시지에만 둡니다(CLAUDE.md 「재권님께 드리는 글에는 커밋 번호를 쓰지 않는다」).")
    if MODE == "block":
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    else:
        print(json.dumps({"systemMessage": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
