#!/usr/bin/env python3
"""로컬 서버와 배포 워커의 설정값이 같은지 대조한다.

    holdings/server/kis_proxy.py     로컬 개발 서버 (파이썬)
    holdings/worker/kis-worker.js    배포본 Cloudflare Worker (자바스크립트)

둘은 같은 일을 한다. 언어가 달라 합칠 수 없다. 한쪽만 고치면 로컬에서 본
숫자와 사이트에서 본 숫자가 갈린다. 둘 다 오류를 내지 않아 눈으로는 못 찾는다.

    python tools/check-kis-consts.py     맞으면 0, 어긋나면 1

이름이 다른 짝은 아래 PAIRS 에 적어 둔다. 비교 방식도 거기서 고른다.
새 설정값을 넣을 때는 여기에도 한 줄 넣는다.

CLAUDE.md 「같은 값은 한 곳에만 둔다」 참조.
"""
import io
import math
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
PY = "holdings/server/kis_proxy.py"
JS = "holdings/worker/kis-worker.js"

# (무엇인지, 파이썬 이름, 워커 이름, 비교 방식)
#
#   None     값이 똑같아야 한다
#   "list"   ["Y", "K"] 같은 목록. 따옴표 안의 값만 순서대로 비교한다
#   "dict"   {"D": 300} 같은 사전. 키와 값을 짝지어 비교한다.
#            파이썬은 키를 따옴표로 쓰고 자바스크립트는 안 쓰는데, 그 차이는
#            무시한다. 값까지 봐야 하므로 "list" 로는 대조가 안 된다
#            (list 는 따옴표 안만 보는데, 사전은 값이 숫자라 하나도 안 잡힌다)
#   "ceil"   파이썬 값을 올림한 것과 워커 값이 같으면 통과.
#            워커는 Cloudflare 엣지 캐시(cf.cacheTtl)를 쓰는데 공식 문서가
#            소수를 받는지 밝히지 않아, 소수 초는 워커에서 올림해 넣는다
#            (2026-09-15 확인). 그래서 0.7 ↔ 1 은 어긋난 것이 아니다.
PAIRS = [
    ("차트 시장구분",        "MARKET_DIV_CHART",    "MARKET_DIV_CHART",     None),
    ("분봉 시작 시각",       "MINUTE_DAY_START",    "MINUTE_DAY_START",     None),
    ("분봉 끝 시각",         "MINUTE_DAY_END",      "MINUTE_DAY_END",       None),
    # 「빠른 갈래」 는 2026-09-18 에 없앴다 — 모든 종목이 같은 수명을 쓴다
    ("시세 캐시 (느림)",     "PRICE_CACHE_TTL",     "QUOTE_CACHE_TTL",      None),
    ("종목 차트 캐시",       "INDEX_CHART_TTL",     "CHART_CACHE_TTL",      None),
    ("지수 추이 캐시",       "INDEX_CHART_TTL",     "SERIES_TTL",           None),
    ("지수 분봉 간격",       "INDEX_MINUTE_STEP",   "INDEX_MINUTE_STEP",    None),
    ("지수 분봉 캐시",       "INDEX_MINUTE_TTL",    "INDEX_MINUTE_TTL",     None),
    ("해외지수 캐시",        "OVERSEAS_TTL",        "OVERSEAS_TTL",         None),
    ("지수 봉 보관량",       "INDEX_KEEP",          "INDEX_KEEP",           "dict"),
    ("지수 봉 갱신 주기",    "INDEX_FRESH",         "INDEX_FRESH",          "dict"),
    ("지수 봉 훑는 기간",    "INDEX_SPAN",          "INDEX_SPAN_DAYS",      "dict"),
    ("지수 봉 한 번에",      "INDEX_PAGE",          "INDEX_PAGE",           None),
    ("지수 봉 나눠받기 횟수", "INDEX_PAGES",         "INDEX_PAGES",          None),
    ("분봉 다시받기 간격",   "MINUTE_REFILL_GAP",   "MINUTE_REFILL_GAP",    None),
    ("5분봉 미리받기 종목수", "PREFILL_TOP",         "PREFILL_TOP",          None),
    # 5분봉은 5분에 한 번만 새 봉이 생긴다. 그 사이에 또 받으면 같은 값을
    # 두 번 받는 것이다. **로컬과 배포본이 앱키를 같이 쓰므로** 한쪽만
    # 고치면 절반만 고치는 셈이다 (2026-09-18 지시).
    ("5분봉 미리받기 간격",  "PREFILL_FRESH_SEC",   "PREFILL_FRESH_SEC",    None),
    # 네이버 업종·테마 — server/naver.py 와 워커가 같은 값을 봐야 한다
    ("네이버 캐시",          "TTL",                 "NAVER_TTL",            None),
    ("네이버 목록 개수",     "LIST_SIZE",           "NAVER_LIST_SIZE",      None),
    ("네이버 종목 개수",     "STOCK_SIZE",          "NAVER_STOCK_SIZE",     None),
    ("네이버 큰 칸 제외",    "MAX_GROUP_COUNT",     "NAVER_MAX_GROUP_COUNT", None),
    ("네이버 뉴스 개수",     "NEWS_SIZE",           "NAVER_NEWS_SIZE",      None),
    ("네이버 토론 개수",     "DISCUSS_SIZE",        "NAVER_DISCUSS_SIZE",   None),
    ("체결 캐시",           "TICKS_TTL",           "TICKS_TTL",            None),
    ("선물 종목코드",        "FUTURES_CODE",        "FUTURES_CODE",         None),
    ("선물 캐시",            "FUTURES_TTL",         "FUTURES_TTL",          "ceil"),
    ("지수 캐시",            "INDEX_TTL",           "INDEX_TTL",            "ceil"),
    ("멀티 조회 최대",       "MULTI_MAX",           "MULTI_MAX",            None),
    ("목록 시세 캐시",       "MULTI_CACHE_TTL",     "MULTI_CACHE_TTL",      None),
    ("업종 시장 목록",      "SECTOR_MARKETS",      "SECTOR_MARKETS",       "list"),
    ("업종 분류 코드",      "SECTOR_BLNG",         "SECTOR_BLNG",          None),
    ("업종에서 빼는 것",    "SECTOR_SKIP",         "SECTOR_SKIP",          "list"),
    ("업종 캐시",           "SECTOR_TTL",          "SECTOR_TTL",           None),
    ("등락률 순위 캐시",    "MOVERS_TTL",          "MOVERS_TTL",           None),
    ("등락률 순위 최대",    "MOVERS_MAX",          "MOVERS_MAX",           None),
    # 종목별 투자자 · 호가 (2026-09-18)
    ("종목별 투자자 일수",  "INVESTOR_DAYS",       "INVESTOR_DAYS",        None),
    ("종목별 투자자 캐시",  "INVESTOR_TTL",        "INVESTOR_TTL",         None),
    ("호가 단계",           "ASKING_LEVELS",       "ASKING_LEVELS",        None),
    ("호가 캐시",           "ASKING_TTL",          "ASKING_TTL",           None),
    ("투자자 상위 캐시",    "INVESTOR_TOP_TTL",    "INVESTOR_TOP_TTL",     None),
    ("투자자 추이 캐시",    "INVESTOR_FLOW_TTL",   "INVESTOR_FLOW_TTL",    None),
    ("투자자 추이 기간",    "INVESTOR_FLOW_DAYS",  "INVESTOR_FLOW_DAYS",   None),
    ("공시 감시 종목 수",    "UNIVERSE_SIZE",       "UNIVERSE_SIZE",        None),
    ("공시 수집 시장",       "COLLECT_MARKETS",     "COLLECT_MARKETS",      "list"),
    ("공시 보관 일수",       "RETENTION_DAYS",      "RETENTION_DAYS",       None),
    ("지수 구성종목 목록",   "INDEX_LISTS",         "INDEX_LISTS",          "list"),
    ("알림 예약",            "REMINDERS",           "REMINDERS",            "list"),
    # 살아있음 신호 — server/heartbeat.py ↔ worker/kis-worker.js (2026-09-23)
    ("살아있음 키",          "ALIVE_KEY",           "ALIVE_KEY",            None),
    ("꺼짐 판정 시간",       "ALIVE_STALE_SEC",     "ALIVE_STALE_SEC",      None),
]

# 어긋남을 알릴 때 "올림이라 괜찮은 것" 인지 곁들이려고 미리 모아 둔다
CEIL_NOTE = {w for w, _, _, c in PAIRS if c == "ceil"}

# 공시 상수는 dart.py 에, 네이버 상수는 naver.py 에 있다.
# 파일이 다른 것만 따로 적는다.
PY_ALT = {
    "UNIVERSE_SIZE":   "holdings/server/dart.py",
    "INDEX_LISTS":     "holdings/server/dart.py",
    "REMINDERS":       "holdings/server/dart.py",
    "COLLECT_MARKETS": "holdings/server/dart.py",
    "RETENTION_DAYS":  "holdings/server/dart.py",
    "TTL":             "holdings/server/naver.py",
    "LIST_SIZE":       "holdings/server/naver.py",
    "STOCK_SIZE":      "holdings/server/naver.py",
    "MAX_GROUP_COUNT": "holdings/server/naver.py",
    "NEWS_SIZE":       "holdings/server/naver.py",
    "DISCUSS_SIZE":    "holdings/server/naver.py",
    "TICKS_TTL":       "holdings/server/kis_proxy.py",
    "ALIVE_KEY":       "holdings/server/heartbeat.py",
    "ALIVE_STALE_SEC": "holdings/server/heartbeat.py",
}


def read_consts(rel):
    """파일에서 최상위 상수를 이름→값 으로 읽는다.

    파이썬은 `NAME = 값`, 자바스크립트는 `const NAME = 값;` 형태를 본다.
    줄 끝 주석은 버린다. 8 * 60 처럼 간단한 곱셈은 계산한다.

    **여러 줄에 걸친 배열도 읽는다.** 전에는 첫 줄만 읽어서 `REMINDERS = [`
    의 `[` 만 잡혔고, 양쪽이 똑같이 빈 값이 되어 무엇을 고쳐도 늘 통과했다.
    도구가 통과한다고 믿을 수 없게 되는 종류의 구멍이라, 일부러 어긋나게
    해서 잡히는지 확인하고 고쳤다 (2026-09-15).
    """
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return None
    lines = io.open(path, encoding="utf-8").read().splitlines()
    out = {}

    for i, line in enumerate(lines):
        m = re.match(r"^(?:const\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.+)$", line)
        if not m:
            continue
        name, raw = m.group(1), m.group(2)
        raw = re.sub(r"\s*(#|//).*$", "", raw).strip()

        # 대괄호가 열린 채 줄이 끝나면 닫힐 때까지 이어 붙인다
        if raw.count("[") > raw.count("]"):
            buf = [raw]
            depth = raw.count("[") - raw.count("]")
            for nxt in lines[i + 1:]:
                cut = re.sub(r"\s*(#|//).*$", "", nxt)
                buf.append(cut.strip())
                depth += cut.count("[") - cut.count("]")
                if depth <= 0:
                    break
            raw = " ".join(buf)

        raw = raw.rstrip(";").strip()
        out[name] = parse_value(raw)
    return out


def parse_value(raw):
    """문자열 리터럴 · 숫자 · 간단한 곱셈만 다룬다. 나머지는 원문 그대로."""
    m = re.match(r'^["\'](.*)["\']$', raw)
    if m:
        return m.group(1)
    if re.match(r"^[\d\s.*+/-]+$", raw):
        try:
            return float(eval(raw, {"__builtins__": {}}, {}))    # 숫자만 들어온다
        except Exception:
            pass
    return raw


# 사전 키로 쓰인 따옴표. 파이썬은 {"id": ...} 처럼 키를 따옴표로 쓰지만
# 자바스크립트는 { id: ... } 로 쓴다. 그대로 비교하면 늘 어긋난다.
DICT_KEY = re.compile(r"""["'](\w+)["']\s*:""")


def as_list(v):
    """["Y", "K"] 든 ["Y","K"] 든 같게 보도록 따옴표 안의 값만 뽑는다.

    사전 키는 뺀다 — 파이썬 {"at": "..."} 와 자바스크립트 { at: "..." } 가
    같은 것으로 읽혀야 한다.
    """
    text = DICT_KEY.sub(":", str(v))
    return re.findall(r"""["']([^"']*)["']""", text)


# 사전의 키:값 한 쌍. 키는 따옴표가 있어도 없어도 같게 본다.
DICT_PAIR = re.compile(r"""["']?([A-Za-z0-9_]+)["']?\s*:\s*([\d.]+)""")


def as_dict(v):
    """{"D": 300, "W": 260} 과 { D: 300, W: 260 } 을 같게 본다.

    값이 숫자인 사전만 다룬다. 문자열 값이 섞이면 as_list 를 쓴다.
    """
    return {k: float(n) for k, n in DICT_PAIR.findall(str(v))}


def same(a, b):
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) < 1e-9
    return a == b


def show(v):
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else str(v)
    return str(v)


def main():
    py = read_consts(PY)
    js = read_consts(JS)
    if py is None or js is None:
        print("[읽기 실패] 파일을 찾지 못했습니다")
        return 1

    alt = {}
    for name, rel in PY_ALT.items():
        got = read_consts(rel)
        if got:
            alt[name] = got

    bad = []
    missing = []
    ok = 0

    for what, pname, jname, conv in PAIRS:
        src = alt.get(pname, py)
        if pname not in src:
            where = os.path.basename(PY_ALT.get(pname, PY))
            missing.append((what, "%s 에 %s 가 없습니다" % (where, pname)))
            continue
        if jname not in js:
            missing.append((what, "kis-worker.js 에 %s 가 없습니다" % jname))
            continue
        a = src[pname]
        b = js[jname]
        if conv == "list":
            hit = as_list(a) == as_list(b)
        elif conv == "dict":
            hit = as_dict(a) == as_dict(b) and bool(as_dict(a))
        elif conv == "ceil":
            hit = isinstance(a, float) and isinstance(b, float) and math.ceil(a) == b
        else:
            hit = same(a, b)
        if hit:
            ok += 1
        else:
            bad.append((what, pname, show(a), jname, show(b)))

    for what, pname, a, jname, b in bad:
        print("어긋남  %-16s 파이썬 %s = %s   ·   워커 %s = %s"
              % (what, pname, a, jname, b))
        if what in CEIL_NOTE:
            print("        (워커는 올림한 값이어야 합니다 — 위 머리말 참조)")
    for what, msg in missing:
        print("없음    %-16s %s" % (what, msg))

    if bad or missing:
        print()
        print("설정값: %d개 일치, %d개 어긋남, %d개 없음."
              % (ok, len(bad), len(missing)))
        print("양쪽을 같게 맞춰 주세요. 워커를 고쳤으면 Cloudflare 에 다시 올려야 합니다.")
        return 1

    print("설정값: %d개, 서버와 워커가 모두 같습니다." % ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
