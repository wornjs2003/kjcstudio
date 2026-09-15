#!/usr/bin/env python3
"""관심종목 목록이 세 곳에서 같은지 대조한다.

같은 8종목이 세 파일에 따로 적혀 있다. 언어도 실행 환경도 달라 합칠 수 없다.

    holdings/js/data/market.js    WATCHLIST          브라우저가 화면에 그린다
    holdings/server/dart.py       WATCH_CODES        로컬 서버가 텔레그램을 보낸다
    holdings/worker/kis-worker.js DART_WATCH_CODES   배포본이 텔레그램을 보낸다

한쪽만 고치면 화면에는 있는데 알림이 안 오거나, 로컬과 배포본이 다른 종목을
감시한다. 어느 쪽도 오류를 내지 않아 눈으로는 못 찾는다.

    python tools/check-watchlist-sync.py     맞으면 0, 어긋나면 1

CLAUDE.md 「같은 값은 한 곳에만 둔다」 참조.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (표시 이름, 파일, 배열이 시작되는 문구)
SOURCES = [
    ("market.js  WATCHLIST",         "holdings/js/data/market.js",    "export const WATCHLIST = ["),
    ("dart.py    WATCH_CODES",       "holdings/server/dart.py",       "WATCH_CODES = ["),
    ("worker.js  DART_WATCH_CODES",  "holdings/worker/kis-worker.js", "const DART_WATCH_CODES = ["),
]

CODE = re.compile(r"""["'](\d{6})["']""")


def read_array(rel, start):
    """start 로 시작하는 배열 하나를 통째로 잘라 6자리 코드를 뽑는다.

    대괄호 깊이를 세어 자른다. 뒤에 다른 배열이 이어져도 섞이지 않는다
    (그냥 일정 길이만 읽었더니 다음 배열까지 딸려 들어왔다)."""
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return None, "파일이 없습니다: " + rel
    s = io.open(path, encoding="utf-8").read()
    at = s.find(start)
    if at < 0:
        return None, "'%s' 를 찾지 못했습니다: %s" % (start, rel)

    i = at + len(start) - 1        # '[' 자리
    depth = 0
    end = -1
    for j in range(i, len(s)):
        if s[j] == "[":
            depth += 1
        elif s[j] == "]":
            depth -= 1
            if depth == 0:
                end = j
                break
    if end < 0:
        return None, "배열이 닫히지 않았습니다: " + rel
    return CODE.findall(s[i:end]), None


def main():
    lists = []
    for name, rel, start in SOURCES:
        codes, err = read_array(rel, start)
        if err:
            print("[읽기 실패] " + err)
            return 1
        lists.append((name, codes))

    base_name, base = lists[0]
    bad = False

    for name, codes in lists:
        print("  %-28s %2d개" % (name, len(codes)))

    for name, codes in lists[1:]:
        only_base = [c for c in base if c not in codes]
        only_this = [c for c in codes if c not in base]
        if only_base or only_this:
            bad = True
            print()
            print("어긋납니다 — %s 와 %s" % (base_name, name))
            if only_base:
                print("  %s 에만 있음: %s" % (base_name, ", ".join(only_base)))
            if only_this:
                print("  %s 에만 있음: %s" % (name, ", ".join(only_this)))

    print()
    if bad:
        print("관심종목: 어긋났습니다. 세 곳을 같게 맞춰 주세요.")
        return 1
    print("관심종목: %d개, 세 곳 모두 같습니다." % len(base))
    return 0


if __name__ == "__main__":
    sys.exit(main())
