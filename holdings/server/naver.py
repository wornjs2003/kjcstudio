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

import html
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

# 종목별 뉴스에서 받아 둘 묶음 수. 화면은 위에서 몇 개만 쓴다
NEWS_SIZE = 12

# 종목토론에서 받아 둘 글 수
DISCUSS_SIZE = 12

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


def news(code, size=NEWS_SIZE):
    """종목별 뉴스. **바깥이 배열**이고 각 묶음 안에 items 가 있다.

    같은 사건을 여러 언론사가 쓰면 한 묶음으로 온다 — 우리는 묶음마다
    첫 기사만 쓴다. 그래야 같은 제목이 줄줄이 늘어서지 않는다.

    날짜는 `202609181902` 형태다 (YYYYMMDDHHMM).

    **제목이 HTML 로 이스케이프되어 온다** — `&quot;직접 대화하자&quot;` 처럼.
    화면은 받은 글자를 다시 이스케이프해 넣으므로 여기서 풀지 않으면
    `&quot;` 가 그대로 보인다 (2026-09-18 실측).
    """
    def make():
        j = _get("https://m.stock.naver.com/api/news/stock/%s?pageSize=%d&page=1"
                 % (code, size))
        rows = []
        for g in (j if isinstance(j, list) else []):
            items = g.get("items") or []
            if not items:
                continue
            it = items[0]
            oid = (it.get("officeId") or "").strip()
            aid = (it.get("articleId") or "").strip()
            rows.append({
                "title": html.unescape((it.get("title") or "").strip()),
                "office": (it.get("officeName") or "").strip(),
                "at": (it.get("datetime") or "").strip(),
                # 같은 사건을 쓴 기사 수. 1 이면 안 적는다
                "more": max(0, len(items) - 1),
                "url": ("https://n.news.naver.com/mnews/article/%s/%s" % (oid, aid)
                        if oid and aid else None),
            })
        return rows

    return _cached("n:" + code, make)


def discuss(code, size=DISCUSS_SIZE):
    """종목토론실 글 목록.

    ── 어디서 받나 (2026-09-18 실측) ──

    옛 주소(`finance.naver.com/item/board.naver`)는 302 로
    `stock.naver.com/domestic/stock/<코드>/discussion` 에 넘어갑니다. 그 화면이
    부르는 것이 아래 주소이고, **호스트가 `stock.naver.com` 입니다** —
    이 파일의 다른 호출과 달리 `m.stock` 도 `api.stock` 도 404 였습니다.

        discussionType=DOMESTIC_STOCK   STOCK 은 400(잘못된 값)
        excludesItemNews=true           토론 목록에 섞여 오는 뉴스는 뺍니다

    `contentSwReplacedButImg` 가 본문인데 **화면에는 제목만 씁니다.** 칸이
    좁아 본문까지 넣으면 몇 줄 못 보여줍니다.
    """
    def make():
        j = _get("https://stock.naver.com/api/community/discussion/posts"
                 "?itemCode=%s&discussionType=DOMESTIC_STOCK&isHolderOnly=false"
                 "&excludesItemNews=true&isItemNewsOnly=false&pageSize=%d"
                 % (code, size))
        rows = []
        for p in (j.get("posts") or []):
            pid = str(p.get("id") or "").strip()
            rows.append({
                "title": html.unescape((p.get("title") or "").strip()),
                "writer": ((p.get("writer") or {}).get("nickname") or "").strip(),
                # 2026-09-18T19:16:37 — 화면에서 오늘 것이면 시각으로 적습니다
                "at": (p.get("writtenAt") or "").strip(),
                "comments": _num(p.get("commentCount")) or 0,
                "likes": _num(p.get("recommendCount")) or 0,
                "url": ("https://stock.naver.com/domestic/stock/%s/discussion/%s"
                        % (code, pid) if pid else None),
            })
        return rows

    return _cached("d:" + code, make)


def integration(code):
    """종목 한 장 요약 — **일별 매매동향 5일**과 **지표 18개**가 한 번에 온다.

    종목 화면 머리의 「외국인 순매수 · 기관 순매수」 와 아래 「개인·외국인·기관」
    칸이 이것으로 채워진다 (2026-09-21 지시 — A 종목 화면).

    ── 왜 KIS 가 아니라 네이버인가 ──

    KIS 에도 종목별 투자자(`/api/kis/investor`, 30일)가 있고 이미 붙어 있다.
    네이버를 쓰는 것은 **외인 보유율과 지표 18개가 함께 오기 때문**이다 —
    PER·PBR·EPS·BPS·52주·배당까지 한 번에 받는다. KIS 로는 여러 번 불러야 한다.
    **KIS 예산도 안 쓴다.**

    ── 시가총액 순위는 여기 없다 ──

    응답 어디에도 순위가 없다(2026-09-21 실측 — 「순위」·「rank」 둘 다 0곳).
    그래서 **공시 수집이 아침마다 받아 두는 표(dart_universe)에서 붙인다.**
    그 표는 코스피 상위 200종목이라 **그 밖은 순위를 모른다** — None 으로 둔다.

    ── 숫자가 문자열로 온다 ──

    `"-1,673,323"` · `"46.46%"` 처럼 온다. 이 파일의 다른 함수들과 같이
    `_num()` 으로 풀어서 보낸다.
    """
    def make():
        j = _get("https://m.stock.naver.com/api/stock/%s/integration" % code)

        flow = []
        for d in (j.get("dealTrendInfos") or [])[:5]:
            flow.append({
                "date": d.get("bizdate"),
                "foreign": _num(d.get("foreignerPureBuyQuant")),
                "inst": _num(d.get("organPureBuyQuant")),
                "person": _num(d.get("individualPureBuyQuant")),
                "foreignRate": _num(d.get("foreignerHoldRatio")),
                "close": _num(d.get("closePrice")),
                "volume": _num(d.get("accumulatedTradingVolume")),
            })

        # 지표는 key/value 목록으로 온다. 화면이 찾기 쉽게 code 를 키로 돌려준다.
        info = {}
        for t in (j.get("totalInfos") or []):
            info[t.get("code")] = {"name": t.get("key"), "value": t.get("value")}

        return {
            "name": j.get("stockName"),
            "flow": flow,
            "info": info,
            "rank": _cap_rank(code),
        }

    return _cached("i:" + code, make)


def _cap_rank(code):
    """시가총액 순위. 공시 수집이 아침마다 받아 두는 표에서 읽는다.

    **코스피 상위 200종목뿐이다.** 그 밖이면 None 이고, 화면은 「—」로 적는다.
    받아오는 것은 `server/dart.py` 이고 여기서는 읽기만 한다.
    """
    import os
    import sqlite3
    db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "market.db")
    try:
        with sqlite3.connect(db, timeout=5) as c:
            r = c.execute("SELECT rank FROM dart_universe WHERE stock_code = ?",
                          (code,)).fetchone()
        return r[0] if r else None
    except Exception:
        return None          # 표가 아직 없을 수 있다. 순위만 빠진다


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
