#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""네이버 업종 · 테마 (2026-09-18 지시 — 「지금 뜨는 산업」)

왜 네이버인가
-------------
KIS 로는 업종 등락률까지만 됩니다. 화면이 보여주려는 것 둘이 KIS 에 없습니다.

    그 업종에서 몇이 오르고 내렸나      riseCount · fallCount · steadyCount
    그 업종 안의 종목 목록              업종을 눌렀을 때 펼쳐지는 것

테마는 KIS 에 아예 없습니다(`docs/kis-sector-investor.md` 5절).

    KIS      업종 41개 · 테마 없음 · 2.31초
    네이버   업종 79개 · 테마 264개 · 4번 호출 0.10초

**비공식 API 입니다.** 예고 없이 바뀔 수 있고 호출 한도도 공개된 것이 없습니다.
다만 `dart.py` 가 시가총액 순위를, 워커가 지수 구성종목을 받을 때 이미 같은
계통을 쓰고 있어 이 저장소가 처음 쓰는 곳이 아닙니다.

숫자가 문자열로 옵니다
----------------------
`closePrice` 가 `"60,700"` 처럼 **콤마가 든 문자열**입니다. 화면에서 그대로
`Number()` 에 넣으면 `NaN` 이 됩니다. **여기서 풀어서 보냅니다** — 화면과 워커가
각자 풀면 세 곳에 같은 처리가 생깁니다.

조사 기록은 `docs/sector-sources.md` 에 있습니다.
"""

import json
import re
import sys
import threading
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://m.stock.naver.com/api/stocks"

# dart.py 가 쓰는 것과 같은 헤더. Referer 가 없으면 막힙니다.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://m.stock.naver.com/",
}

# 장중에는 계속 움직이므로 짧게 둡니다. 화면이 여러 개 떠 있어도
# 이 안에서는 한 번만 부릅니다.
TTL = 30

# 한 번에 받아 둘 개수. 화면은 위에서 몇 개만 쓰지만, 칩을 눌러 옮길 때
# 다시 부르지 않도록 넉넉히 받아 둡니다.
LIST_SIZE = 20
STOCK_SIZE = 10

# ── 「기타」 는 업종이 아니다 (2026-09-18) ──────────────────────────
#
# 네이버 업종 목록에 `기타`(no=25)가 끼어 있는데 **1,538종목**입니다.
# 분류가 안 된 나머지를 다 모아둔 칸이라 시장 거의 전부이고, 그래서
# 등락률이 시장 평균과 같습니다. 「지금 뜨는 산업」에 올라오면 아무 뜻이
# 없습니다 — 보는 쪽은 「이게 무슨 산업이지」 하게 됩니다.
#
# **이름이나 번호로 거르지 않습니다.** 이름은 네이버가 바꿀 수 있고 번호도
# 바뀔 수 있습니다. **크기로 거릅니다** — 실제 업종 중 가장 큰 것이
# 반도체 171종목인데 「기타」 는 1,538종목이라 아홉 배 넘게 벌어져 있어
# 경계가 안전합니다 (2026-09-18 실측).
#
# 테마에는 이런 칸이 없습니다. 가장 큰 것이 시스템반도체 58종목입니다.
MAX_GROUP_COUNT = 1000

_cache = {}
_lock = threading.Lock()


def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _cached(key, make):
    with _lock:
        hit = _cache.get(key)
        if hit and (time.time() - hit[0]) < TTL:
            return hit[1]
    value = make()
    with _lock:
        _cache[key] = (time.time(), value)
    return value


def _num(v):
    """"60,700" · "+1,140" · "" 를 숫자로. 못 읽으면 None."""
    if v is None:
        return None
    s = re.sub(r"[,\s%]", "", str(v))
    if s in ("", "-", "+"):
        return None
    try:
        return float(s) if ("." in s) else int(s)
    except ValueError:
        return None


def groups(kind="industry"):
    """업종 또는 테마 목록. **등락률 내림차순이 기본**이라 그대로 씁니다.

    「지금 뜨는」 순서가 그대로 옵니다 (docs/sector-sources.md 실측).
    """
    if kind not in ("industry", "theme"):
        raise ValueError("kind 는 industry 또는 theme 여야 합니다.")

    def make():
        j = _get("%s/%s?page=1&pageSize=%d" % (BASE, kind, LIST_SIZE))
        rows = []
        dropped = 0
        for g in (j.get("groups") or []):
            if (_num(g.get("totalCount")) or 0) > MAX_GROUP_COUNT:
                dropped += 1          # 「기타」 처럼 분류가 아닌 칸. 위 주석 참고
                continue
            rows.append({
                "no": g.get("no"),
                "name": g.get("name"),
                "pct": _num(g.get("changeRate")),
                "rise": _num(g.get("riseCount")) or 0,
                "steady": _num(g.get("steadyCount")) or 0,
                "fall": _num(g.get("fallCount")) or 0,
                "count": _num(g.get("totalCount")) or 0,
            })
        total = _num(j.get("totalCount"))
        return {
            "rows": rows,
            # 거른 만큼 빼서 돌려줍니다. 화면이 「79개 중」 이라고 적는데
            # 실제로는 하나를 빼고 보여주므로 숫자가 어긋나면 안 됩니다.
            "total": (total - dropped) if total is not None else None,
            "dropped": dropped,
            "marketStatus": j.get("marketStatus"),
        }

    return _cached("g:" + kind, make)


def stocks(kind, no):
    """그 업종·테마의 종목. **등락률 내림차순**이라 앞에서부터 상승률 TOP 입니다."""
    if kind not in ("industry", "theme"):
        raise ValueError("kind 는 industry 또는 theme 여야 합니다.")
    no = int(no)

    def make():
        j = _get("%s/%s/%d?page=1&pageSize=%d" % (BASE, kind, no, STOCK_SIZE))
        rows = []
        for s in (j.get("stocks") or []):
            code = (s.get("itemCode") or "").strip()
            if len(code) != 6:
                continue
            rows.append({
                "code": code,
                "name": s.get("stockName"),
                "price": _num(s.get("closePrice")),
                "amt": _num(s.get("compareToPreviousClosePrice")),
                "pct": _num(s.get("fluctuationsRatio")),
                "volume": _num(s.get("accumulatedTradingVolume")),
                "value": _num(s.get("accumulatedTradingValue")),
            })
        return {"rows": rows, "name": j.get("groupName") or j.get("name")}

    return _cached("s:%s:%d" % (kind, no), make)
