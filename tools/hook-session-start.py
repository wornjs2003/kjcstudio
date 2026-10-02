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
    print("  · 메인 폴더 · 서비스방의 데이터와 8765 · 8764 는 허락 없이 안 건드린다 — 스킬 `main-guard`")
    print("  · 커밋은 재권님이 하라고 하실 때만 · 경로 지정 · 커밋 지시는 푸시까지 — 「커밋 · 푸시 · 배포 규칙」")
    print("  · 재권님이 답하실 것은 맨 아래 하나 · 한국어로만 · 숫자에는 뜻 — 「응답 규칙」")
    # 재시작마다 SendMessage 이름이 바뀌어 세션끼리 주소를 잃었다(2026-10-02 지시 「재발 안하게 룰 만들어줘」)
    print("  · 세션 간 메시지는 보낼 때마다 주소를 센다 — `python3 tools/session-addr.py`(세션 이름 → 지금 주소). 기억한 이름을 쓰지 않는다 · 첫 줄에 내 세션 이름")
    return 0


if __name__ == "__main__":
    sys.exit(main())
