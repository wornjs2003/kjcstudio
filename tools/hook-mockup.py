# -*- coding: utf-8 -*-
"""시안 저장 훅 — 시안이 창 크기를 바꾸거나 값을 지어내는 것을 저장 순간에 잡는다 (2026-10-02 지시).

재권님 말씀 그대로다 — 「이거 재부팅하거나 새로 세션추가할때마다 발생하는데 재발방지책 개념정의세션에 만들라해」.
「이거」 는 시안을 그릴 때 기존 UI 의 칸 · 창 크기를 바꾸고 수치를 지어내는 것이다. 2026-10-02 하루에 한 시안이
v1 → v2 → v3 세 번 연달아 걸렸다(검은 띠 · 점선 · 배지 색 → 칸 크기 · 지어낸 값 → 1600px 고정 틀).
룰은 CLAUDE.md 「시안은 실제 화면 위에 얹는다」 · 「창 크기·배치는 지시 없이 바꾸지 않는다」 에 있었는데
**그 절 스스로 「아직 검사가 없다」** 였다. 절차는 스킬 `mockup`(.claude/skills/mockup/SKILL.md).

PreToolUse(Write · Edit)에서 돈다. **저장소 안 `temp/` 와 세션 임시 폴더(scratchpad)의 시안 파일만** 본다 —
저장소의 진짜 화면 파일은 레인 룰과 check-layout 의 자리다.

시안 파일이란 (이름을 박지 않고 모양으로 가른다)
  .html · .js 이면서  이름에 시안 · mockup · mock · 목업 이 있거나
                     내용에 같은 서버 화면을 거는 iframe(src="/…" · localhost)이 있다

세는 것
  ① 고정 폭 · 배율   iframe · body · html 이나 틀(.frame 등)에 width: NNNpx(세 자리 이상) · zoom · transform: scale
                    → 창 크기를 시안이 정한다. 재권님 화면 폭과 다르게 보인다 (v3 의 1600px 이 이것)
  ② 기록 없음        「잰 칸」 과 「값 출처」 두 낱말이 파일 안에 없다
                    → 얹기 전후 칸 px 를 재지 않았거나, 값을 어디서 받았는지 안 적었다
  ③ 나란히 둔 틀     iframe 이 둘 이상 — 각 틀이 창보다 좁아져 화면이 다시 배치된다. **「봐야 할 자리」**
                    (전후를 나란히 보여 드리는 것 자체는 쓸모가 있다 — 막지 않는다)

① 은 MODE 가 "block" 이면 막고 "look"(기본) 이면 알리기만 한다. ② 는 늘 알리기만 — 낱말 맞추기를 막으면 주문이 된다(qa 재생 2026-10-02 · 46건 100% 막힘). **어느 쪽이 맞는지는 qa 시뮬레이션이 정한다** —
오탐이 쌓이면 우회가 습관이 된다(메인 가드 때 배운 것). ③ 은 늘 알리기만 한다.

못 보는 것 — Bash 로 쓴 시안(heredoc · cp) · 시안 파일 밖에서 진짜 화면 코드를 고친 것 · 지어낸 값 그 자체
(숫자가 API 에서 왔는지는 기계가 모른다 — 「값 출처」 낱말이 있는지까지만 본다).
"""
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODE = os.environ.get("KJC_MOCKUP_HOOK", "look")    # block | look | off — 기본은 알리기만(재권님 확인 전 · 작업우선순위 감사)

NAME = re.compile(r"(시안|sian|mockup|mock|목업)", re.I)
FRAME = re.compile(r"<iframe\b[^>]*\bsrc\s*=\s*[\"'](/|https?://(localhost|127\.0\.0\.1))", re.I)
# CSS 규칙 하나 — 선택자 { 본문 }. 틀에 해당하는 선택자만 본다
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
FRAME_SEL = re.compile(r"(^|[\s,>])(iframe|body|html|[.#][\w-]*(frame|wrap|stage|shot)[\w-]*|#f\b)", re.I)
STYLE = re.compile(r"<style[^>]*>(.*?)</style>", re.I | re.S)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
# width 만 — max-width(페이지 안쪽 최대 폭)는 오탐이었다. 1000px 미만(휴대폰 390 등 목적이 있는 폭)도 뺀다 (qa 재생 2026-10-02)
FIXED_W = re.compile(r"(?<![-\w])()width\s*:\s*(\d{4,})px", re.I)
SCALE = re.compile(r"\bzoom\s*:|transform\s*:[^;]*scale\(", re.I)
IFRAME_W_ATTR = re.compile(r"<iframe\b[^>]*\bwidth\s*=\s*[\"']?(\d{4,})(?!%)", re.I)
RECORD = ("잰 칸", "값 출처")


def in_scope(path):
    p = os.path.realpath(path).replace("\\", "/")
    if not p.endswith((".html", ".htm", ".js")):
        return False
    return "/temp/" in p or "/scratchpad/" in p


def after_edit(path, ti):
    """편집 뒤 파일 내용을 만든다 — Edit 은 바뀔 조각만 오므로 지금 파일에 대입해 본다."""
    if "content" in ti:
        return ti.get("content") or ""
    try:
        cur = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        cur = ""
    old, new = ti.get("old_string", ""), ti.get("new_string", "")
    if not old:
        return cur
    return cur.replace(old, new) if ti.get("replace_all") else cur.replace(old, new, 1)


def is_mockup(path, text):
    return bool(NAME.search(os.path.basename(path))) or bool(FRAME.search(text))


def check(path, text):
    """(막을 것, 봐야 할 것) — 둘 다 문장 목록."""
    bad, look = [], []
    # CSS 는 <style> 안에서만 읽는다 — 밖의 글(<!doctype html> 등)이 선택자로 섞인다(2026-10-02 시험에서 걸림).
    # .js 시안은 파일 전체가 코드라 그대로 본다
    css = text if path.endswith(".js") else "\n".join(STYLE.findall(text))
    css = CSS_COMMENT.sub("", css)
    for m in RULE.finditer(css):
        sel, body = m.group(1).strip(), m.group(2)
        if not FRAME_SEL.search(sel):
            continue
        w = FIXED_W.search(body)
        if w:
            bad.append("고정 폭 — `%s { %swidth: %spx }`. 틀의 폭은 창이 정한다(100%% · 100vw)" % (sel[-40:], w.group(1) or "", w.group(2)))
        if SCALE.search(body):
            bad.append("배율 — `%s` 에 zoom · scale. 실제 화면을 줄이거나 키우지 않는다" % sel[-40:])
    a = IFRAME_W_ATTR.search(text)
    if a:
        bad.append("고정 폭 — iframe 의 width=\"%s\" 속성" % a.group(1))
    missing = [w for w in RECORD if w not in text]
    if missing:
        # 낱말 맞추기는 막지 않는다 — 막으면 붙이기만 하면 통과하는 주문이 되고, 위반을 지우는 편집까지 막혔다 (qa 재생)
        look.append("기록 없음 — 파일 안에 「%s」 가 없다. 예: <!-- 잰 칸: 투자지표 카드 6칸 얹기 전후 같음(DOM 실측) / 값 출처: /api/kis/price · 없으면 — -->" % "」 · 「".join(missing))
    if len(re.findall(r"<iframe\b", text, re.I)) >= 2:
        look.append("iframe 이 둘 이상 — 나란히 두면 각 틀이 창보다 좁아져 화면이 다시 배치된다. 전후 비교면 「같은 폭에서 위아래로」 또는 쿼리 하나로 덧그리기")
    return bad, look


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if MODE == "off" or data.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return 0
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ""
    if not path or not in_scope(path):
        return 0
    if data.get("tool_name") == "MultiEdit":
        text = open(path, encoding="utf-8", errors="replace").read() if os.path.exists(path) else ""
        for e in ti.get("edits") or []:
            old, new = e.get("old_string", ""), e.get("new_string", "")
            text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    else:
        text = after_edit(path, ti)
    if not is_mockup(path, text):
        return 0
    bad, look = check(path, text)
    if bad and os.path.exists(path):
        before, _ = check(path, open(path, encoding="utf-8", errors="replace").read())
        if len(bad) < len(before):
            look = ["위반이 줄어드는 편집이라 막지 않았습니다 — 남은 것: " + " / ".join(bad)] + look
            bad = []
    if not bad and not look:
        return 0

    lines = ["시안 파일입니다 — 스킬 `mockup`(.claude/skills/mockup/SKILL.md) 의 절차를 따릅니다."]
    lines += ["  ✗ " + b for b in bad] + ["  · " + l for l in look]
    lines.append("룰: CLAUDE.md 「시안은 실제 화면 위에 얹는다」 · 「창 크기·배치는 지시 없이 바꾸지 않는다」.")
    msg = "\n".join(lines)

    if bad and MODE == "block":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": msg}}, ensure_ascii=False))
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "additionalContext": msg}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
