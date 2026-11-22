# -*- coding: utf-8 -*-
"""단타 칩 종목 1분봉 실시간 — 장중 CHIP_M1_INTERVAL 마다 칩 걸린 종목의 1분봉을 받아 쌓는다 (2026-11-23).

재권님 말씀 — 11-20 「장중에는 칩에 걸리는 종목만 실시간으로 받는다. 그외 종목은 서버의 여유분으로 차곡차곡 쌓는다.
단타에 칩이라고 정의된 부분은 빠르게 적용도게 되야한다」 · 11-23 08:4x 「칩에 걸린 종목은 실시간으로 정보 받아와야해」.

    받는 종목   단타 목록(dt30._live · 홈 「단타」 와 같은 셈 · 셈하지 않고 쥔 것만 읽음) + 그날 단타 판 줄
               — 새로 칩에 든 종목은 다음 바퀴부터 든다
    받는 길     kis_proxy.get_chart(…, "1m") — 화면 차트와 같은 길(1분 · 5분 함께 저장 · 그 종목 그날 처음이면 하루치)
    차례       높음 그대로(칩 종목은 실시간) · 그 밖 감시 목록 거래대금 쌓기(turnover.py)는 낮음으로 비켜선다
현재가 · 거래대금은 단타 목록이 묶음 시세로 따로 받는다(LIVE_TTL · PRICE_CACHE_TTL) — 이 파일은 1분봉만.
"""
import threading
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
CHIP_M1_INTERVAL = 60         # 칩 종목 1분봉 한 바퀴 간격(초) — 1분봉이라 1분
CHIP_M1_LIMIT = 30            # 한 번에 읽어 오는 봉 수(DB 에서 · 받는 양은 get_chart 가 정함)

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


def status():
    return dict(_status, interval=CHIP_M1_INTERVAL)


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

    threading.Thread(target=loop, daemon=True, name="chip-live").start()
    return True
