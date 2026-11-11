# -*- coding: utf-8 -*-
"""초반상승 — 정규장 첫 5분봉(09:00~09:05)이 시가보다 RISE_PCT % 이상 올라 끝난 종목 · 실시간 순위 「초반상승」 칩 (2026-11-11).

재권님 — 「아침 9시5분 기준으로 양봉이 2% 이상이 되고 시가총액이 5천억 이상인 종목들 소팅해서 실시간 순위에 초반상승 이라고 만들어서
넣어줘」(작업우선순위 창 11:25) → 「양봉 2%」 를 (가) 첫 5분봉 시가 대비 종가 · (나) 09:05 가격의 전일 종가 대비 로 여쭈어 「가」(개발1 창 11:41).

    대상        순위 목록(dart.universe_rows · 코스피 200 · 코스닥 150) 중 시가총액 MIN_CAP_EOK 억원 이상
    셈          그날 5분봉 BAR_HM 봉(09:00 시작 · 통합) — (종가 − 시가) ÷ 시가 ≥ RISE_PCT %
    차례        그 상승률 큰 순
    다 찬 봉만   그 봉을 **끝난 뒤에 받았는지**는 kis_proxy `_minutes_fresh_upto`(「지금 칸」 을 받은 분)로 가른다 — 09:05 전에 받은 덜 찬 봉으로
                고르지 않는다(거래량 전날 대비 % 와 같은 기록 · 11-11 qa 돌려보냄). 아직이면 그 종목은 `pending` 으로 센다
    언제        새로 받지 않는다 — DB 에 쌓인 5분봉만 읽는다(미리받기가 순위 목록 5분봉을 받는다). 그 봉이 다 차면 값이 그대로라 그날 판이 굳는다
    없음        그날 봉이 없는 종목은 `noBar` 로 센다(0 아님) · 장 전(그 거래일 09:05 전)이면 판이 비고 phase 가 before

KIS 를 부르지 않는다. 값(09:00 봉 · 2% · 5천억)은 이 파일 상수 한 곳 — 화면은 meta 로 받아 글에 쓴다.
"""

from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

BAR_HM = "0900"          # 정규장 첫 5분봉(시작 시각) — 09:00~09:05
RISE_PCT = 2.0           # 첫 봉 시가 대비 종가 상승률 문턱(%)
MIN_CAP_EOK = 5000       # 시가총액 문턱(억원 · 5천억) — dart_universe.market_cap 단위가 억원
CACHE_TTL = 60           # 같은 판을 다시 세지 않는 시간(초) — 화면이 다시 묻는 주기도 이 값(서버 값)

_BAR_END_MIN = int(BAR_HM[:2]) * 60 + int(BAR_HM[2:]) + 5     # 그 봉이 끝나는 분(09:05)
_st = {"at": 0.0, "data": None}


def _universe():
    import dart
    out = []
    for r in dart.universe_rows(None):
        code = r["stock_code"] or ""
        if code.isdigit() and len(code) == 6:
            out.append({"code": code, "name": r["name"], "market": r["market"], "cap": r["market_cap"]})
    return out


def build(proxy, now=None):
    """그날 판 — {day, phase, rows, candidates, pending, noBar, capMissing}."""
    now = now or datetime.now(KST)
    day = proxy._minutes_trade_day()
    live_today = day == now.strftime("%Y%m%d")
    if live_today and now.hour * 60 + now.minute < _BAR_END_MIN:
        return {"day": day, "phase": "before", "rows": [], "candidates": None, "pending": None, "noBar": None, "capMissing": None}
    uni = _universe()
    cap_missing = sum(1 for u in uni if u["cap"] is None)
    cand = [u for u in uni if u["cap"] is not None and u["cap"] >= MIN_CAP_EOK]
    codes = [u["code"] for u in cand]
    bars = {}
    if codes:
        with proxy._db_lock, proxy.db_conn() as conn:
            q = ",".join("?" * len(codes))
            for r in conn.execute(
                    "SELECT code, open, high, low, close, volume FROM candles WHERE period = '5m' AND ts = ? AND code IN (%s)" % q,
                    [day + BAR_HM] + codes):
                bars[r["code"]] = dict(r)
    rows, pending, no_bar = [], 0, 0
    for u in cand:
        b = bars.get(u["code"])
        if not b or not b["open"] or b["close"] is None:
            no_bar += 1
            continue
        if live_today:
            fresh = proxy._minutes_fresh_upto(u["code"])
            if fresh is None or fresh < _BAR_END_MIN:
                pending += 1                 # 그 봉을 09:05 뒤에 아직 안 받았다 — 덜 찬 값일 수 있다
                continue
        pct = (b["close"] - b["open"]) / b["open"] * 100
        if pct >= RISE_PCT:
            rows.append({"code": u["code"], "name": u["name"], "market": u["market"], "cap": u["cap"],
                         "open": b["open"], "close": b["close"], "high": b["high"], "volume": b["volume"],
                         "pct": round(pct, 2)})
    rows.sort(key=lambda x: -x["pct"])
    return {"day": day, "phase": "pending" if pending else "done", "rows": rows,
            "candidates": len(cand), "pending": pending, "noBar": no_bar, "capMissing": cap_missing}


def fetch(proxy, now=None):
    """(판, 센 시각). CACHE_TTL 안이면 들고 있던 판."""
    import time
    if _st["data"] is None or time.time() - _st["at"] >= CACHE_TTL:
        _st["data"] = build(proxy, now)
        _st["at"] = time.time()
    return _st["data"], _st["at"]
