#!/usr/bin/env python3
"""합칠 수 없는 복제를 한 번에 대조한다.

    python tools/check-all.py      전부 맞으면 0, 하나라도 어긋나면 1

같은 값이 두 곳 이상에 적혀 있는데 언어·실행 환경이 달라 합칠 수 없는 것들이
있다. 어긋나도 오류가 안 나고 화면은 멀쩡해 보인다. 값을 고쳤으면 이것을 돌린다.

CLAUDE.md 「같은 값은 한 곳에만 둔다」 참조.
"""
import os
import subprocess
import sys

# 윈도우 콘솔은 기본이 cp949 라 '—' 같은 글자에서 죽는다.
# 출력만 UTF-8 로 바꾼다 (tools/check-theme-sync.py 와 같은 처리).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))

CHECKS = [
    ("색 (theme.css ↔ theme.js)",        "check-theme-sync.py"),
    ("관심종목 (세 곳)",                  "check-watchlist-sync.py"),
    ("설정값 (서버 ↔ 워커)",              "check-kis-consts.py"),
    ("뉴스 주제어 (JSON ↔ 워커)",         "check-news-topics.py"),
]


def main():
    failed = []
    for label, script in CHECKS:
        path = os.path.join(HERE, script)
        print("─" * 62, flush=True)
        print("■ " + label)
        # 자식 출력이 먼저 나와 머리글과 순서가 뒤집힌다. 여기서 흘려보낸다
        sys.stdout.flush()
        if not os.path.exists(path):
            print("  건너뜀 — %s 가 없습니다" % script)
            continue
        r = subprocess.run([sys.executable, path])
        if r.returncode != 0:
            failed.append(label)

    print("─" * 62)
    if failed:
        print("어긋난 곳: " + " · ".join(failed))
        return 1
    print("전부 일치합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
