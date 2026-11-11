# -*- coding: utf-8 -*-
"""SessionStart 훅 — 세션이 열리면(처음 · 이어서 · /clear 뒤 · 압축 뒤) 「new-session 스킬을 읽으십시오」 를 띄운다
(2026-10-02 지시 — 「응 해줘」).

**왜** — new-session 스킬은 세션이 「내 자리가 어디지」 하고 **물을 때만** 읽힌다(qa 실측). 묻지 않고 바로 일을
시작하는 세션은 안 읽는다. 열릴 때 한 줄 띄우면 그 틈이 메워진다.

**어떻게** — SessionStart 훅의 표준 출력은 세션의 문맥에 더해진다. 그래서 막는 것이 아니라 **읽을 것을 가리키는
한 줄**만 낸다. 룰 본문은 여기 없다 — 스킬이 CLAUDE.md 절을 가리키고, 여기는 스킬을 가리킨다.

**못 보는 것** — 세션이 실제로 읽었는지. 그것은 기계가 못 본다.
"""
import json
import re
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    src = data.get("source") or ""          # startup · resume · clear · compact
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skill = os.path.join(root, ".claude", "skills", "new-session", "SKILL.md")
    if not os.path.exists(skill):
        return 0                            # 스킬이 없는 폴더(옛 가지)면 조용히
    why = {"startup": "세션이 새로 열렸습니다", "resume": "세션을 이어서 엽니다",
           "clear": "/clear 뒤입니다", "compact": "문맥이 압축됐습니다"}.get(src, "세션이 열렸습니다")
    # **가리키기만 하면 안 읽는다** (qa 2026-10-02 실측 — 한 줄은 6/6 들어가는데 묻지 않는 세션은 0/5 스킬을 안 읽었다.
    # 그런데 문맥에 **든** 룰은 따랐다). 그래서 핵심 몇 줄을 여기 직접 담고, 자세한 것은 스킬로 보낸다.
    # 룰 본문은 베끼지 않는다 — 한 줄씩 **어느 절인지**만 가리킨다 (「같은 값은 한 곳에만 둔다」).
    print("[new-session] %s. 일을 시작하기 전에 — 자세한 것은 스킬 `new-session`(.claude/skills/new-session/SKILL.md)." % why)
    print("  · 내 이름 · 레인 · 자리(폴더 · 가지 · 포트)를 먼저 찾는다 — CLAUDE.md 「세션 역할 분담」 · 「무엇이 어디에 있나」. 표에 없는 창이면 손대기 전에 여쭙는다")
    print("  · 레인 표가 이보다 좁으면 레인 표가 이긴다 (qa · 작업우선순위 · 홈페이지_정리)")
    print("  · 파일을 고치거나 만드는 일은 먼저 안을 드리고 「그렇게 해」 뒤에. 읽기만 하는 일은 바로 — 「작업 착수 규칙」")
    print("  · 지시를 받으면 첫 행동은 보드 카드 — 「일은 보드에서 시작한다」. 진행 상태도 카드에 적는다")
    print("  · 개발 폴더 · 메인의 데이터와 8765 · 8764 는 허락 없이 안 건드린다 — 스킬 `main-guard`")
    print("  · 커밋은 재권님이 하라고 하실 때만 · 경로 지정 · 커밋 지시는 푸시까지 — 「커밋 · 푸시 · 배포 규칙」")
    print("  · 재권님이 답하실 것은 맨 아래 하나 · 한국어로만 · 숫자에는 뜻 — 「응답 규칙」")
    # 재시작마다 SendMessage 이름이 바뀌어 세션끼리 주소를 잃었다(2026-10-02 지시 「재발 안하게 룰 만들어줘」)
    print("  · 세션 간 메시지는 보낼 때마다 주소를 센다 — `python3 tools/session-addr.py`(세션 이름 → 지금 주소). 기억한 이름을 쓰지 않는다 · 첫 줄에 내 세션 이름")
    if src in ("compact", "clear"):
        open_work(root)
    return 0


def open_work(root):
    """압축 · /clear 뒤 그 세션의 열린 일을 보드에서 넣는다 — 「받은 지시는 끝나거나 재권님이 거두실 때까지 보드에 살아 있다」
    (2026-11-11 지시 「응 만들어」). 압축 요약을 세션이 잘 쓰는 것에 기대지 않는다 — 카드가 원천이다.
    11-10 1분봉 — 답 없는 물음이 압축 뒤 짧은 꼴로도 안 떠 다음날 재권님이 찾으셨다."""
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location("board_card", os.path.join(root, "tools", "board-card.py"))
        bc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bc)
        label = bc.label_of(bc.session_name())
        if not label:
            print("[열린 일] 못 읽음 — 세션 이름을 못 얻었다. `python3 tools/board-card.py --mine --label <담당>` 으로 보십시오")
            return
        doc, _ = bc.read()                      # 못 보면 Unseen — 「못 볼 때는 막지 않는다」 와 같은 셈(1.5초 · 503 · 5xx)
    except Exception as e:
        print("[열린 일] 못 읽음(%s) — 보드(8765)가 돌아오면 `python3 tools/board-card.py --mine` 으로 보십시오" % type(e).__name__)
        return
    rows, asks, after = [], [], []
    for t in bc.tasks(doc):
        if bc.who_of(t) != label:
            continue
        col = t.get("column") or "todo"
        memo = t.get("memo") or ""
        title = (t.get("text") or "")[:70]
        if col in ("doing", "review"):
            rows.append("%s · %s" % (col, title))
        if col != "done":
            q = bc.open_question(memo)
            if q:
                at = ""
                for ln in memo.split("\n"):
                    m = re.match(r"^\s*(\d{1,2}:\d{2})\s+묻는 중:", ln)
                    if m:
                        at = m.group(1)
                asks.append("%s「%s」 — 카드 「%s」" % ((at + " ") if at else "", q, title[:40]))
            ls = [x for x in memo.split("\n") if x.strip()]
            if col == "todo" and ls and "뒤에 진행:" in ls[-1]:
                after.append("%s — %s" % (title[:50], ls[-1].split("뒤에 진행:", 1)[1].strip()))
    print("[열린 일 · %s] 보드에서 읽음 — 하던 일과 걸린 물음을 이것으로 잇는다" % label)
    if not (rows or asks or after):
        print("  · 열린 카드 · 걸린 물음 없음")
        return
    for r in rows[:8]:
        print("  · " + r)
    if len(rows) > 8:
        print("  · … 외 %d장 — `python3 tools/board-card.py --mine`" % (len(rows) - 8))
    for a in after[:5]:
        print("  · 뒤에 진행: " + a)
    if asks:
        print("  답 없는 물음 — **자기 기록에서 답이 있었는지 먼저 본다.** 있었으면 `--answer` 로 닫고 안 올린다 ·"
              " 없으면 다음 답 맨 아래에 「▶ 앞서 HH:MM 에 여쭌 것 그대로입니다 — <물음 한 줄>」 로 다시 올린다")
        for a in asks[:5]:
            print("  · " + a)
        if len(asks) > 5:
            print("  · … 외 %d개" % (len(asks) - 5))


if __name__ == "__main__":
    sys.exit(main())
