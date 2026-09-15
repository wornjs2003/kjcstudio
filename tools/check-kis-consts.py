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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = "holdings/server/kis_proxy.py"
JS = "holdings/worker/kis-worker.js"

# (무엇인지, 파이썬 이름, 워커 이름, 비교 방식)
#
#   None     값이 똑같아야 한다
#   "list"   ["Y", "K"] 같은 목록. 따옴표 안의 값만 순서대로 비교한다
#   "ceil"   파이썬 값을 올림한 것과 워커 값이 같으면 통과.
#            워커는 Cloudflare 엣지 캐시(cf.cacheTtl)를 쓰는데 공식 문서가
#            소수를 받는지 밝히지 않아, 소수 초는 워커에서 올림해 넣는다
#            (2026-09-15 확인). 그래서 0.7 ↔ 1 은 어긋난 것이 아니다.
PAIRS = [
    ("차트 시장구분",        "MARKET_DIV_CHART",    "MARKET_DIV_CHART",     None),
    ("분봉 시작 시각",       "MINUTE_DAY_START",    "MINUTE_DAY_START",     None),
    ("분봉 끝 시각",         "MINUTE_DAY_END",      "MINUTE_DAY_END",       None),
    ("시세 캐시 (빠름)",     "PRICE_CACHE_TTL_FAST", "QUOTE_CACHE_TTL_FAST", None),
    ("시세 캐시 (느림)",     "PRICE_CACHE_TTL",     "QUOTE_CACHE_TTL",      None),
    ("종목 차트 캐시",       "INDEX_CHART_TTL",     "CHART_CACHE_TTL",      None),
    ("지수 추이 캐시",       "INDEX_CHART_TTL",     "SERIES_TTL",           None),
    ("지수 분봉 간격",       "INDEX_MINUTE_STEP",   "INDEX_MINUTE_STEP",    None),
    ("지수 분봉 캐시",       "INDEX_MINUTE_TTL",    "INDEX_MINUTE_TTL",     None),
    ("해외지수 캐시",        "OVERSEAS_TTL",        "OVERSEAS_TTL",         None),
    ("지수 캔들 캐시",       "INDEX_CANDLE_TTL",    "INDEX_CANDLE_TTL",     None),
    ("선물 종목코드",        "FUTURES_CODE",        "FUTURES_CODE",         None),
    ("선물 캐시",            "FUTURES_TTL",         "FUTURES_TTL",          "ceil"),
    ("지수 캐시",            "INDEX_TTL",           "INDEX_TTL",            "ceil"),
    ("멀티 조회 최대",       "MULTI_MAX",           "MULTI_MAX",            None),
    ("공시 감시 종목 수",    "UNIVERSE_SIZE",       "UNIVERSE_SIZE",        None),
    ("공시 수집 시장",       "COLLECT_MARKETS",     "COLLECT_MARKETS",      "list"),
    ("공시 보관 일수",       "RETENTION_DAYS",      "RETENTION_DAYS",       None),
]

# 어긋남을 알릴 때 "올림이라 괜찮은 것" 인지 곁들이려고 미리 모아 둔다
CEIL_NOTE = {w for w, _, _, c in PAIRS if c == "ceil"}

# 공시 상수는 dart.py 에 있다. 파일이 다른 것만 따로 적는다.
PY_ALT = {
    "UNIVERSE_SIZE":   "holdings/server/dart.py",
    "COLLECT_MARKETS": "holdings/server/dart.py",
    "RETENTION_DAYS":  "holdings/server/dart.py",
}


def read_consts(rel):
    """파일에서 최상위 상수를 이름→값 으로 읽는다.

    파이썬은 `NAME = 값`, 자바스크립트는 `const NAME = 값;` 형태만 본다.
    줄 끝 주석은 버린다. 8 * 60 처럼 간단한 곱셈은 계산한다."""
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return None
    out = {}
    for line in io.open(path, encoding="utf-8"):
        m = re.match(r"^(?:const\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.+)$", line)
        if not m:
            continue
        name, raw = m.group(1), m.group(2)
        raw = re.sub(r"\s*(#|//).*$", "", raw).strip().rstrip(";").strip()
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


def as_list(v):
    """["Y", "K"] 든 ["Y","K"] 든 같게 보도록 따옴표 안만 뽑는다."""
    return re.findall(r"""["']([^"']*)["']""", str(v))


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
