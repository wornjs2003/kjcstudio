#!/usr/bin/env python3
"""관심종목 목록이 여러 곳에서 같은지 대조한다.

같은 목록이 여러 파일에 따로 적혀 있다. 언어도 실행 환경도 달라 합칠 수 없다.

**개수를 여기 적지 않는다.** 자리가 없어질 수 있다 — 2026-09-30 에
배포본 워커가 경로에서 빠졌다. 아래 `SOURCES` 가 세는 자리다.

    holdings/js/data/market.js    WATCHLIST          브라우저가 화면에 그린다
    holdings/server/dart.py       WATCH_CODES        로컬 서버가 텔레그램을 보낸다
    holdings/worker/kis-worker.js DART_WATCH_CODES   배포본이 텔레그램을 보낸다

한쪽만 고치면 화면에는 있는데 알림이 안 오거나, 로컬과 배포본이 다른 종목을
감시한다. 어느 쪽도 오류를 내지 않아 눈으로는 못 찾는다.

    python tools/check-watchlist-sync.py     맞으면 0, 어긋나면 1

CLAUDE.md 「같은 값은 한 곳에만 둔다」 참조.

**`--listed [--port N]` — 목록이 실제 상장 종목인지 본다** (2026-10-03 재권님 「응 해」).
셀트리온헬스케어(091990)가 2023년 상장폐지인데 시장 전체 목록에 남아 있었다 — 목업에서
옮겨 오며 대조를 안 했다. `market.js` 의 WATCHLIST · MARKET_STOCKS 코드를 서버
`/api/kis/quotes`(기본 8765 · 서버 캐시 · 30종목에 KIS 1건)로 한 번 묻는다.

    응답에 없는 코드    「상장 목록에 없음」 — 걸림(1)
    이름이 다른 코드    「봐야 할 자리」 — 이름을 바꿨을 수 있다. 막지 않는다
    서버 · KIS 를 못 봄  「못 쟀다」(2) — **`0` 으로 내지 않는다**

**기본 실행은 네트워크를 안 쓴다** — `tools/check-all.py` 가 부르는 것은 그대로다.
언제 돌릴지는 정하지 않았다 — 손으로 돌린다.
"""
import json
import urllib.request
import io
import os
import re
import sys

# 윈도우 콘솔은 기본이 cp949 라 '—' 같은 글자에서 죽는다.
# 출력만 UTF-8 로 바꾼다 (tools/check-theme-sync.py 와 같은 처리).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# holdings/tools/ 로 옮겨서 한 단계가 깊어졌다 (2026-09-17).
# 이 도구들이 보는 경로는 **저장소 루트 기준**이라 루트를 정확히 잡아야 한다.
HERE = os.path.dirname(os.path.abspath(__file__))        # holdings/tools
ROOT = os.path.dirname(os.path.dirname(HERE))            # 저장소 루트

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


ITEM = re.compile(r"""code:\s*["'](\d{6})["']\s*,\s*name:\s*["']([^"']+)["']""")
LISTED_SOURCES = [
    ("WATCHLIST",     "export const WATCHLIST = ["),
    ("MARKET_STOCKS", "export const MARKET_STOCKS = ["),
]


def read_items(rel, start):
    """배열 하나에서 (코드, 이름) 을 뽑는다. 자르는 법은 `read_array` 와 같다."""
    codes, err = read_array(rel, start)
    if err:
        return None, err
    s = io.open(os.path.join(ROOT, rel), encoding="utf-8").read()
    at = s.find(start)
    body = s[at:]
    items = []
    for c, n in ITEM.findall(body):
        if c in codes and c not in [x[0] for x in items]:
            items.append((c, n))
    return items, None


def listed(port):
    """market.js 의 종목이 지금 시세가 오는 종목인지 — 0 통과 · 1 걸림 · 2 못 쟀다."""
    rel = "holdings/js/data/market.js"
    want = []          # (목록 이름, 코드, 이름)
    for lname, start in LISTED_SOURCES:
        items, err = read_items(rel, start)
        if err:
            print("[읽기 실패] " + err)
            return 2
        want += [(lname, c, n) for c, n in items]
    codes = list(dict.fromkeys(c for _, c, _ in want))
    if not codes:
        print("  **물을 종목이 0개입니다 — 「없다」 가 아니라 「못 읽었다」 입니다.**")
        return 2

    got, unmeasured = {}, []
    step = 120                       # 서버 `quotes` 가 한 번에 받는 상한(kis_proxy.py 의 [:120])
    for i in range(0, len(codes), step):
        chunk = codes[i:i + step]
        url = "http://127.0.0.1:%d/api/kis/quotes?codes=%s" % (port, ",".join(chunk))
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                j = json.load(r)
        except Exception as e:
            print("  못 쟀다 — 서버(%d)를 못 불렀다: %s" % (port, type(e).__name__))
            return 2
        if not j.get("ok"):
            print("  못 쟀다 — 서버가 실패를 돌려줬다: %s" % (j.get("error") or "")[:80])
            return 2
        # **KIS 오류로 빠진 것은 「상장 목록에 없음」 이 아니다** — 그 묶음은 못 쟀다로 둔다
        if j.get("errors"):
            unmeasured += chunk
            continue
        got.update(j.get("data") or {})

    missing = [(l, c, n) for l, c, n in want if c not in got and c not in unmeasured]
    renamed = [(l, c, n, (got[c] or {}).get("name")) for l, c, n in want
               if c in got and (got[c] or {}).get("name") and (got[c] or {}).get("name") != n]

    print("  market.js  WATCHLIST + MARKET_STOCKS   %d종목 (서버 %d · 응답 %d)" % (len(codes), port, len(got)))
    if renamed:
        print()
        print("  봐야 할 자리 — 이름이 다릅니다 (막지 않습니다)")
        for l, c, n, real in renamed:
            print("      %-14s %s  market.js 「%s」 ↔ 시세 「%s」" % (l, c, n, real))
    if unmeasured:
        print()
        print("  못 쟀다 — KIS 오류로 %d종목을 못 봤습니다: %s" % (len(unmeasured), ", ".join(unmeasured)))
    if missing:
        print()
        print("상장 목록에 없음 — 시세가 안 옵니다 (상장폐지 · 합병 · 코드 틀림)")
        for l, c, n in missing:
            print("      %-14s %s  %s" % (l, c, n))
        return 1
    if unmeasured:
        return 2
    print()
    print("상장: %d종목 모두 시세가 옵니다." % len(codes))
    return 0


def main():
    if "--listed" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
        return listed(port)
    # **「파일이 없다」 와 「파일은 있는데 못 읽었다」 를 가른다 (2026-09-30).**
    #
    # 자리가 **없어질 수 있다.** 배포본 워커가 그 자리다 — 2026-09-30 에
    # 터널로 넘어가면서 **워커가 경로에서 빠졌고**, 곧 지운다.
    # 그때 이 도구가 **없는 파일을 찾아 영영 실패**하면, 멀쩡한 커밋이
    # 그것 때문에 막힌다.
    #
    #     파일이 **없다**              →  **건너뛴다** (없어진 자리일 수 있다)
    #     파일은 있는데 **못 읽었다**    →  **실패다** (배열 이름이 바뀌었다)
    #
    # ⚠️ **건너뛴 것을 조용히 넘기지 않는다.** 몇 곳을 실제로 댔는지 함께
    # 낸다 — 「대상 0개를 `0` 으로 내지 않는다」 와 같은 자리다.
    lists, skipped = [], []
    for name, rel, start in SOURCES:
        codes, err = read_array(rel, start)
        if err:
            if err.startswith("파일이 없습니다"):
                skipped.append((name, rel))
                continue
            print("[읽기 실패] " + err)
            return 1
        lists.append((name, codes))

    if skipped:
        print("  건너뜁니다 — 파일이 없습니다:")
        for name, rel in skipped:
            print("      %-28s %s" % (name, rel))
        print()

    # **한 곳만 남으면 대조가 아니다.** 「같다」 고 낼 수 없다.
    if len(lists) < 2:
        print("  **댈 것이 %d곳뿐입니다 — 대조가 안 됩니다.**" % len(lists))
        print("  자리가 정말 없어졌으면 이 도구의 `SOURCES` 에서 빼십시오.")
        return 2

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
    # **개수를 박지 않는다.** 「세 곳」 이 박혀 있었는데, 자리가 하나 빠지면
    # 그 문구가 거짓이 된다. **댄 곳을 세어 쓴다.**
    if bad:
        print("관심종목: 어긋났습니다. %d곳을 같게 맞춰 주세요." % len(lists))
        return 1
    print("관심종목: %d개, %d곳 모두 같습니다." % (len(base), len(lists)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
