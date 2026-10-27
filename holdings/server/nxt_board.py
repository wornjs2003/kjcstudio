# -*- coding: utf-8 -*-
"""넥스트레이드 장외 보드 — 날마다 종가 · 장외(장 후) · 다음날 프리장 · 야간선물을 쌓아 Insight 「투자 전략」 에 낸다 (2026-10-26).

재권님 — 「종가 후 넥장에서 오른 · 내린 종목 목록과 다음날 시초가 차이를 Insight 에서 매일 모니터링」(16:4x) →
시황분석 시안 「응 세로로 2배 늘려서 진행해줘」(17:2x) → 서버 안 「응 해」(17:4x · 개발1 창). 화면은 시황분석이 만든다.

    언제      평일 15:41~15:59 한 번 — KRX 종가(시간외 단일가 16:00 전 · 그 뒤 J 현재가는 시간외 값으로 움직인다 — 2026-10-26 17:47 실측
              삼성전자 J 213,000 ↔ 정규장 종가 213,500)
              평일 20:01~20:30 한 번 — 장외(애프터마켓)가 20:00 에 닫힌 뒤
              매일 06:01~06:30 한 번 — 야간선물(KRX 야간장)이 06:00 에 닫힌 뒤. 그 값은 **앞 평일** 의 것으로 적는다
    범위      코스피 · 코스닥 **주권 전부** — nxt_pre 의 종목 마스터(그룹 ST) 그대로. 시장은 nxt_pre.MARKET_OF
    값        멀티 시세(intstock-multprice) 30종목씩 — 15:41 시장구분 J 의 현재가 = 그날 **KRX 종가**,
              20:01 시장구분 NX 의 현재가 · 누적 거래량 = **장외 마지막가** · 그날 NX 거래량. 하루 91번 × 2
              15:41 을 놓친 날(서버가 그때 내려가 있었음)은 종가가 null — 장외 등락률도 null 이다(시간외 값을 종가로 쓰지 않는다)
              ⚠️ 「20:00 뒤 NX 현재가 = 장외 마지막가」 는 **아직 실측 전**(2026-10-26 20:01 에 잰다)
    프리장    다음 거래일 08:51 에 nxt_pre 가 저장하는 장외가(nxt_pre.price) 를 그대로 읽는다 — 따로 안 부른다
    야간선물  코스피200 · 코스닥150 최근월물(FHMIF10000000 · 시장 CM · 10100000 · 10600000) — 2번
              (2026-10-26 17:2x 둘 다 응답 정상 · 그때는 야간장 전이라 값이 주간과 같았다 — 06:00 값이 야간 종가인지는 아직 못 잼)
    저장      market.db 의 `nxt_board`(날 · 종목 · 시장 · 이름 · 종가 · 장외가 · 장외 거래량) · `nxt_fut`(날 · 무엇 · 이름 · 값 · 등락률)
    주소      GET /api/nxt/board?market=kospi|kosdaq&days=N — 모양은 board() 주석 · 「없음」 은 null(0 아님)

8765 만 받는다(`kis_proxy` 가 `is_sender` 로 부른다) · 읽기는 어느 서버든 자기 DB 로. 알림은 없다(화면만).
"""

import threading
import time
from datetime import datetime, timedelta, timezone

import nxt_pre
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))

CLOSE_AT, CLOSE_UNTIL = (15, 41), (16, 0)
AFTER_AT, AFTER_UNTIL = (20, 1), (20, 30)
FUT_AT, FUT_UNTIL = (6, 1), (6, 30)
TOP_N = 20                      # 날마다 오름 · 내림 각 몇 종목 — 시황분석 시안 「장외 오름 · 내림 각 20」
DAYS_MAX = 20
FUTS = (("kospi200", "10100000"), ("kosdaq150", "10600000"))
TICK = 30

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS nxt_board (
        day TEXT NOT NULL, code TEXT NOT NULL, market TEXT, name TEXT,
        close INTEGER, after INTEGER, after_vol INTEGER, saved_at TEXT, PRIMARY KEY (day, code))""",
    """CREATE TABLE IF NOT EXISTS nxt_fut (
        day TEXT NOT NULL, which TEXT NOT NULL, name TEXT, last REAL, pct REAL, saved_at TEXT,
        PRIMARY KEY (day, which))""",
)

_status = {"closeDay": None, "closeAt": None, "closeCodes": None, "afterDay": None, "afterAt": None, "afterCodes": None, "afterTraded": None,
           "futDay": None, "futAt": None, "error": None}


def _now():
    return datetime.now(KST)


def _init(proxy):
    with proxy._db_lock, proxy.db_conn() as conn:
        for q in _SCHEMA:
            conn.execute(q)


def _prev_weekday(d):
    d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d


def _multi(proxy, cfg, codes, div):
    """{code: {price, vol, name}} — 멀티 시세 한 시장구분"""
    out = {}
    codes = list(codes)
    for i in range(0, len(codes), nxt_pre.MULTI_MAX):
        params = {}
        for n, c in enumerate(codes[i:i + nxt_pre.MULTI_MAX], 1):
            params["FID_COND_MRKT_DIV_CODE_%d" % n] = div
            params["FID_INPUT_ISCD_%d" % n] = c
        data = proxy.kis_get(cfg, "/uapi/domestic-stock/v1/quotations/intstock-multprice", params, "FHKST11300006")
        for r in (data or {}).get("output") or []:
            code = (r.get("inter_shrn_iscd") or "").strip()
            if code:
                out[code] = {"price": proxy._num(r.get("inter2_prpr"), int), "vol": proxy._num(r.get("acml_vol"), int) or 0,
                             "name": (r.get("inter_kor_isnm") or "").strip()}
        time.sleep(nxt_pre.GAP_SEC)
    return out


def save_close(proxy, day):
    """그날 KRX 종가 — 15:41~15:59. 저장한 종목 수. 값이 없으면(휴장) 안 쓴다."""
    _init(proxy)
    cfg = proxy.load_secrets()
    names = nxt_pre.master_codes()
    krx = _multi(proxy, cfg, names, "J")
    if not sum(r["vol"] for r in krx.values()):
        _status.update(closeDay=day, closeAt=_now().isoformat(timespec="seconds"), closeCodes=0, error="KRX 거래량 합이 0 — 휴장으로 보고 저장 안 함")
        return 0
    stamp = _now().isoformat(timespec="seconds")
    rows = [(day, code, nxt_pre.MARKET_OF.get(code), name or (krx.get(code) or {}).get("name"),
             (krx.get(code) or {}).get("price") or None, stamp) for code, name in names.items()]
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.executemany("INSERT INTO nxt_board (day, code, market, name, close, saved_at) VALUES (?,?,?,?,?,?) "
                         "ON CONFLICT(day, code) DO UPDATE SET close = excluded.close, market = excluded.market, name = excluded.name", rows)
    _status.update(closeDay=day, closeAt=stamp, closeCodes=len(rows), error=None)
    return len(rows)


def save_after(proxy, day):
    """그날 장외 마지막가 · 장외 거래량 — 20:01~20:29. 저장한 종목 수. NX 거래량 합이 0 이면 휴장으로 보고 안 쓴다."""
    _init(proxy)
    cfg = proxy.load_secrets()
    names = nxt_pre.master_codes()
    nx = _multi(proxy, cfg, names, "NX")
    if not sum(r["vol"] for r in nx.values()):
        _status.update(afterDay=day, afterAt=_now().isoformat(timespec="seconds"), afterCodes=len(names), afterTraded=0,
                       error="NX 거래량 합이 0 — 휴장으로 보고 저장 안 함")
        return 0
    stamp = _now().isoformat(timespec="seconds")
    rows = []
    for code, name in names.items():
        n = nx.get(code) or {}
        traded = (n.get("vol") or 0) > 0
        rows.append((day, code, nxt_pre.MARKET_OF.get(code), name or n.get("name"),
                     (n.get("price") or None) if traded else None, n.get("vol") or 0, stamp))
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.executemany("INSERT INTO nxt_board (day, code, market, name, after, after_vol, saved_at) VALUES (?,?,?,?,?,?,?) "
                         "ON CONFLICT(day, code) DO UPDATE SET after = excluded.after, after_vol = excluded.after_vol, "
                         "saved_at = excluded.saved_at", rows)
    _status.update(afterDay=day, afterAt=stamp, afterCodes=len(rows), afterTraded=sum(1 for r in rows if r[4]), error=None)
    return len(rows)


def save_futures(proxy, day):
    """야간선물 둘 — 그 앞 평일(day) 의 값으로 적는다. 저장한 수."""
    _init(proxy)
    cfg = proxy.load_secrets()
    stamp = _now().isoformat(timespec="seconds")
    rows = []
    for which, code in FUTS:
        try:
            data = proxy.kis_get(cfg, "/uapi/domestic-futureoption/v1/quotations/inquire-price",
                                 {"FID_COND_MRKT_DIV_CODE": "CM", "FID_INPUT_ISCD": code}, "FHMIF10000000")
            o = (data or {}).get("output1") or {}
            rows.append((day, which, (o.get("hts_kor_isnm") or "").strip() or None,
                         proxy._num(o.get("futs_prpr")), proxy._num(o.get("futs_prdy_ctrt")), stamp))
        except Exception as e:
            _status["error"] = "야간선물 %s: %s" % (which, safe_message(e, 100))
    if rows:
        with proxy._db_lock, proxy.db_conn() as conn:
            conn.executemany("INSERT OR REPLACE INTO nxt_fut (day, which, name, last, pct, saved_at) VALUES (?,?,?,?,?,?)", rows)
    _status.update(futDay=day, futAt=stamp)
    return len(rows)


def _pct(a, b):
    return round((a / b - 1) * 100, 2) if a and b else None


def board(proxy, market, days=5):
    """화면 한 장 —

        {market, days: [{day, preDay, fut: {kospi200: {name, last, pct} | null, kosdaq150: …}}] (최신이 앞),
         rows: [{code, name, side: "up" | "down", rank, cells: {<day>: {close, after, afterPct, pre, prePct}}}]}

    rows 는 날마다 장외 등락률(afterPct · 종가 대비) 오름 · 내림 상위 TOP_N 의 합집합. side · rank 는 그 종목이 든 가장 최근 날 것.
    pre 는 다음 거래일 08:51 장 전 가격(nxt_pre) · prePct 는 그날 종가 대비. 값이 없으면 null.
    """
    days = max(1, min(DAYS_MAX, int(days or 5)))
    with proxy._db_lock, proxy.db_conn() as conn:
        try:
            conn.execute("SELECT 1 FROM nxt_board LIMIT 1")
        except Exception:                       # 표가 아직 없다 — 쌓기 전
            return {"market": market, "days": [], "rows": []}
        ds = [r[0] for r in conn.execute(
            "SELECT DISTINCT day FROM nxt_board WHERE market = ? ORDER BY day DESC LIMIT ?", (market, days))]
        if not ds:
            return {"market": market, "days": [], "rows": []}
        q = ",".join("?" * len(ds))
        board_rows = [dict(r) for r in conn.execute(
            "SELECT day, code, name, close, after FROM nxt_board WHERE market = ? AND day IN (%s)" % q, [market] + ds)]
        pre_days, pre = {d: None for d in ds}, {}
        try:                                    # nxt_pre 표가 없는 서버(한 번도 안 돈 자리)면 프리장은 전부 null
            for d in ds:
                r = conn.execute("SELECT MIN(day) FROM nxt_pre WHERE day > ?", (d,)).fetchone()
                pre_days[d] = r[0] if r else None
            pd_list = [x for x in set(pre_days.values()) if x]
            if pd_list:
                q2 = ",".join("?" * len(pd_list))
                for r in conn.execute("SELECT day, code, price, vol FROM nxt_pre WHERE day IN (%s)" % q2, pd_list):
                    if r["price"] and (r["vol"] or 0) > 0:
                        pre[(r["day"], r["code"])] = r["price"]
        except Exception:
            pass
        futs = {}
        for r in conn.execute("SELECT day, which, name, last, pct FROM nxt_fut WHERE day IN (%s)" % q, ds):
            futs.setdefault(r["day"], {})[r["which"]] = {"name": r["name"], "last": r["last"], "pct": r["pct"]}
    by_day = {}
    for r in board_rows:
        by_day.setdefault(r["day"], []).append(r)
    picked = {}            # code -> (side, rank, 그 날)
    for d in sorted(ds):                          # 오래된 날부터 — 최근 날이 덮어 side · rank 가 최근 것이 된다
        ranked = [r for r in by_day.get(d, []) if r["after"] and r["close"]]
        ranked.sort(key=lambda r: r["after"] / r["close"])
        for i, r in enumerate(reversed(ranked[-TOP_N:])):
            if r["after"] > r["close"]:
                picked[r["code"]] = ("up", i + 1, d)
        for i, r in enumerate(ranked[:TOP_N]):
            if r["after"] < r["close"]:
                picked[r["code"]] = ("down", i + 1, d)
    cells_of = {}
    names = {}
    for r in board_rows:
        if r["code"] not in picked:
            continue
        names[r["code"]] = r["name"]
        p = pre.get((pre_days.get(r["day"]), r["code"]))
        cells_of.setdefault(r["code"], {})[r["day"]] = {
            "close": r["close"], "after": r["after"], "afterPct": _pct(r["after"], r["close"]),
            "pre": p, "prePct": _pct(p, r["close"])}
    rows = [{"code": c, "name": names.get(c), "side": s, "rank": k, "cells": cells_of.get(c, {})}
            for c, (s, k, _d) in picked.items()]
    rows.sort(key=lambda x: (x["side"] != "up", x["rank"]))
    return {"market": market,
            "days": [{"day": d, "preDay": pre_days.get(d), "fut": {w: futs.get(d, {}).get(w) for w, _c in FUTS}} for d in ds],
            "rows": rows}


def status():
    return dict(_status)


def start(proxy):
    """보내는 서버가 뜰 때 한 번 — 15:41 종가 · 20:01 장외 · 06:01 야간선물 바퀴."""
    def loop():
        time.sleep(45)
        while True:
            try:
                now = _now()
                hm = (now.hour, now.minute)
                day = now.strftime("%Y%m%d")
                if now.weekday() < 5 and CLOSE_AT <= hm < CLOSE_UNTIL and _status["closeDay"] != day:
                    _status["closeDay"] = day
                    try:
                        n = save_close(proxy, day)
                        print("  [넥장 보드] %s 종가 %s종목 저장" % (day, n))
                    except Exception as e:
                        _status["error"] = safe_message(e, 160)
                        print("  [넥장 보드] 종가 저장 실패: %s" % type(e).__name__)
                if now.weekday() < 5 and AFTER_AT <= hm < AFTER_UNTIL and _status["afterDay"] != day:
                    _status["afterDay"] = day            # 실패해도 그날은 한 번
                    try:
                        n = save_after(proxy, day)
                        print("  [넥장 보드] %s 장외 %s종목 저장(거래 %s)" % (day, n, _status.get("afterTraded")))
                    except Exception as e:
                        _status["error"] = safe_message(e, 160)
                        print("  [넥장 보드] 장외 저장 실패: %s" % type(e).__name__)
                fday = _prev_weekday(now).strftime("%Y%m%d")
                if 1 <= now.weekday() <= 5 and FUT_AT <= hm < FUT_UNTIL and _status["futDay"] != fday:
                    _status["futDay"] = fday             # 화~토 아침 = 월~금 밤 야간장
                    try:
                        save_futures(proxy, fday)
                    except Exception as e:
                        _status["error"] = safe_message(e, 160)
                        print("  [넥장 보드] 야간선물 저장 실패: %s" % type(e).__name__)
            except Exception as e:
                print("  [넥장 보드] 예기치 못한 오류: %s" % type(e).__name__)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="nxt-board").start()
    return True
