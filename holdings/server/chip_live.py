# -*- coding: utf-8 -*-
"""단타 칩 종목 1분봉 실시간 — 장중 CHIP_M1_INTERVAL 마다 칩 걸린 종목의 1분봉을 받아 쌓는다 (2026-11-23).

재권님 말씀 — 11-20 「장중에는 칩에 걸리는 종목만 실시간으로 받는다. 그외 종목은 서버의 여유분으로 차곡차곡 쌓는다.
단타에 칩이라고 정의된 부분은 빠르게 적용도게 되야한다」 · 11-23 08:4x 「칩에 걸린 종목은 실시간으로 정보 받아와야해」.

    받는 종목   단타 목록(dt30._live · 홈 「단타」 와 같은 셈 · 셈하지 않고 쥔 것만 읽음) + 그날 단타 판 줄
               — 새로 칩에 든 종목은 다음 바퀴부터 든다
    받는 길     kis_proxy.get_chart(…, "1m") — 화면 차트와 같은 길(1분 · 5분 함께 저장 · 그 종목 그날 처음이면 하루치)
    차례       높음 그대로(칩 종목은 실시간) · 그 밖 감시 목록 거래대금 쌓기(turnover.py)는 낮음으로 비켜선다
현재가 · 거래대금은 단타 목록이 묶음 시세로 따로 받는다(LIVE_TTL · PRICE_CACHE_TTL) — 이 파일은 1분봉만.

그 밖 감시 목록(3천억 이상 전부)의 1분 · 5분봉 — 평일 DAY_FILL_AT 뒤 한 번 그날 하루치(08:00~20:00)를 낮은 차례로 받아 쌓는다(day_fill)
— 재권님 「전부다 1년을 쌓는다로 해줘. 용량이 부족해지면 욜량을 넓힐거야」 → 범위 「ㄴ」(감시 목록 모든 종목 1분 · 5분봉 · 11-23 08:5x).
이미 그날 1분봉이 DAY_FILL_HAVE 개 넘게 쌓인 종목(칩 종목 · 화면이 연 종목)은 건너뛴다.
"""
import threading
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
CHIP_M1_INTERVAL = 60         # 칩 종목 1분봉 한 바퀴 간격(초) — 1분봉이라 1분
CHIP_M1_LIMIT = 30            # 한 번에 읽어 오는 봉 수(DB 에서 · 받는 양은 get_chart 가 정함)

DAY_FILL_AT = (20, 10)        # 감시 목록 하루치 쌓기 시각 — 넥스트레이드 끝(20:00) 뒤 · 단타 되채우기 쉬는 때(dt30.QUIET) 끝과 같은 때
DAY_FILL_HAVE = 600           # 그날 1분봉이 이만큼 넘게 있으면 다 받은 종목으로 본다(08:00~20:00 은 720분 · 거래 없는 분은 빈다)

_fill = {"day": None, "done": 0, "skip": 0, "fail": 0, "at": None, "sec": None}
_status = {"at": None, "codes": 0, "ok": 0, "fail": 0, "sec": None, "error": None}


def _now():
    return datetime.now(KST)


def codes_now(proxy):
    """칩 걸린 종목 — 쥔 단타 목록 줄 + 그날 판 줄(셈은 안 부른다)."""
    import dt30
    out = []
    with dt30._live_lock:
        data = dt30._live.get("data") or {}
    out += [r["code"] for r in data.get("rows") or [] if not r.get("down")]
    got = dt30._load(proxy, _now().strftime("%Y%m%d"))
    if got:
        out += [r["code"] for r in got[0].get("rows") or []]
    return list(dict.fromkeys(c for c in out if c and c.isdigit() and len(c) == 6))


def round_once(proxy, cfg):
    t0 = time.time()
    codes = codes_now(proxy)
    ok = fail = 0
    for c in codes:
        try:
            proxy.get_chart(cfg, c, "1m", CHIP_M1_LIMIT)
            ok += 1
        except Exception:
            fail += 1
    _status.update(at=_now().strftime("%H:%M:%S"), codes=len(codes), ok=ok, fail=fail, sec=round(time.time() - t0, 1), error=None)
    return ok


def day_fill(proxy, cfg, day):
    """감시 목록 전 종목 그날 1 · 5분봉 — 받은 종목 수. 한 종목 6번 남짓(120분씩 · 08:00~20:00) · 785종목이면 50분쯤(호출 사이 BAR_FILL_CALL_GAP).
    바퀴는 하루 한 번 — 받다가 실패한 종목은 표(m1day)를 안 남기지만 그날 다시 돌지는 않는다(_fill.fail 로 셈)."""
    import dart
    t0 = time.time()
    codes = [r["stock_code"] for r in dart.universe_rows(None) if (r["stock_code"] or "").isdigit() and len(r["stock_code"]) == 6]
    with proxy.db_conn() as conn:
        have = {c for c, n in conn.execute("SELECT code, COUNT(*) FROM candles WHERE period = '1m' AND ts LIKE ? GROUP BY code", (day + "%",))
                if n > DAY_FILL_HAVE}
    _fill.update(day=day, done=0, skip=0, fail=0, at=_now().strftime("%H:%M:%S"))
    for c in codes:
        if c in have or proxy._meta_get("m1day:%s:%s" % (c, day)):
            _fill["skip"] += 1
            continue
        try:
            proxy._kr_past_day(cfg, c, day)
            proxy._meta_set("m1day:%s:%s" % (c, day), "1")
            _fill["done"] += 1
        except Exception:
            _fill["fail"] += 1
    _fill["sec"] = round(time.time() - t0)
    return _fill["done"]


def status():
    return dict(_status, interval=CHIP_M1_INTERVAL, dayFill=dict(_fill), dayFillAt="%02d:%02d" % DAY_FILL_AT)


def start(proxy):
    """보내는 서버(8765)가 뜰 때 한 번 — 평일 정규장(여는 시각 ~ 끝) 동안."""
    if not proxy.marketdb.writable():
        return False
    import dt30
    import market_hours

    def loop():
        time.sleep(45)
        last = 0.0
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = now.hour * 60 + now.minute
                if now.weekday() < 5 and market_hours.today(proxy, day=day, now=now).get("open") is not False:
                    o = dt30.OPEN_AT[0] * 60 + dt30.OPEN_AT[1] + dt30.late_min(proxy, now)
                    if o <= hm <= dt30._close_min(proxy, now) and time.time() - last >= CHIP_M1_INTERVAL:
                        last = time.time()
                        round_once(proxy, proxy.load_secrets())
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [칩 1분봉] 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            time.sleep(5)

    def fill_loop():
        proxy._prio.low = True                         # 여유분으로 — 화면이 막 불렀으면 비켜선다
        time.sleep(90)
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                if (now.weekday() < 5 and now.hour * 60 + now.minute >= DAY_FILL_AT[0] * 60 + DAY_FILL_AT[1] and _fill["day"] != day
                        and market_hours.today(proxy, day=day, now=now).get("open") is not False):
                    n = day_fill(proxy, proxy.load_secrets(), day)
                    print("  [감시 목록 분봉] %s 하루치 %d종목 쌓음 · 건너뜀 %d · 못 받음 %d · %d초"
                          % (day, n, _fill["skip"], _fill["fail"], _fill["sec"]), flush=True)
            except Exception as e:
                _fill["error"] = type(e).__name__
                print("  [감시 목록 분봉] 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            time.sleep(60)

    threading.Thread(target=loop, daemon=True, name="chip-live").start()
    threading.Thread(target=fill_loop, daemon=True, name="universe-m1").start()
    return True
