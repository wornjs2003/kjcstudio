# -*- coding: utf-8 -*-
"""코스피 1분 · 5분봉을 날마다 쌓아 지난 날도 읽게 (2026-11-25).

카드 「코스피 5분봉을 날마다 쌓아 단타 판이 지난 날도 읽게」 — 개발2 → 개발1 로 옮김(11-25 작업우선순위 배분) ·
재권님 「그렇게 해」(장 끝 뒤 한 번 · 날 주소) → 「1분봉은?」 → 「응 그렇게 해」(1분봉도 장중 네 번 · 같은 날 주소에서 1분 · 5분).

    왜       지수 5분봉은 화면(홈 지수 차트 · 단타 판)이 부를 때만 쌓였다(kis_proxy.fetch_index_minutes) —
             아무도 안 연 날은 통째로 빈다(개발 DB 11-13 ~ 11-22 없음 · 11-25 잼). 1분봉은 아예 안 쌓였다
    받는 것   kis_proxy._index_minutes_from_kis(FHKUP03500200 · 한 번에 최근 약 100봉 · 날을 고르는 칸이 없다 —
             지난 날 빈칸은 다시 못 받는다)
               5분   한 번에 99봉 — 장 끝 뒤 한 번이면 그날 09:00~15:30(79봉)을 다 덮는다
               1분   한 번에 최근 101분(11-25 15:59 잼 13:52~15:32) — 하루치(390봉)는 SLOTS_1M_USUAL 네 번(100분 안쪽 간격)으로 잇는다
    때       보통 날 시각 + dt30.late_min(늦게 여는 날 그만큼 뒤 · 「장 시각으로 셈하는 코드는 늦게 여는 날 그만큼 옮긴다」) ·
             서버가 늦게 떴으면 지난 때는 한 번으로 몰아 받는다(1분은 그 사이가 빈다 — 날 주소 meta 에 봉 수로 보인다)
    저장      market.db candles(code 0001 · period 1m · 5m) — 종목 봉과 같은 표 · 남길 길이는 「봉은 기간마다 정한 길이만 남긴다」 그대로
    주소      GET /api/kis/index-day?code=KOSPI&period=1m|5m&day=YYYYMMDD — 모양은 bars() 주석
    도는 곳    보내는 서버(8765) 하나 · 그 밖은 읽기만
"""

import threading
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
CODES = (("0001", "KOSPI"),)
SLOTS_1M_USUAL = ((10, 40), (12, 20), (14, 0), (15, 40))   # 보통 날 시각 — 한 번에 최근 101분이라 100분 안쪽 간격 · 마지막은 장 끝(15:30) 뒤 · late_min 만큼 민다
AT_5M_USUAL = (15, 40)             # 보통 날 시각 — 장 끝 뒤 한 번(99봉이 하루치를 덮는다) · late_min 만큼 민다
UNTIL_USUAL = (23, 0)              # 보통 날 시각 — 이 뒤로는 그날 몫을 새로 안 받는다(다음 날 첫 봉이 섞이지 않게 넉넉히)
STEP = {"1m": "60", "5m": "300"}
TICK = 30

_status = {"running": False, "day": None, "done1m": -1, "done5m": False, "last": [], "error": None}
_lock = threading.Lock()


def _now():
    return datetime.now(KST)


def _shift(hm, off):
    m = hm[0] * 60 + hm[1] + off
    return (m // 60, m % 60)


def _late(proxy, now):
    """그날 늦은 분 · 장이 열리나 — 못 읽으면 (None, None)."""
    try:
        import dt30
        import market_hours
        t = market_hours.today(proxy, now=now)
        if t.get("open") is False:
            return 0, False
        return dt30.late_min(proxy, now=now), True
    except Exception:
        return None, None


def plan(proxy, now=None):
    """그날 받는 때 — {1m: [(시, 분)], 5m: (시, 분), until, lateMin, open}. 늦은 분을 못 읽으면 보통 날 시각 · lateMin None."""
    now = now or _now()
    late, open_ = _late(proxy, now)
    off = late or 0
    return {"1m": [_shift(s, off) for s in SLOTS_1M_USUAL], "5m": _shift(AT_5M_USUAL, off),
            "until": _shift(UNTIL_USUAL, off), "lateMin": late, "open": open_}


def _get(proxy, cfg, period):
    """코드마다 한 번 받아 쌓는다 — [(이름, 받은 봉 수 · 못 받으면 None)]."""
    out = []
    for code, name in CODES:
        try:
            bars = proxy._index_minutes_from_kis(cfg, code, STEP[period])
        except RuntimeError:
            out.append((name, None))
            continue
        if bars:
            proxy.save_candles(code, period, bars)
        out.append((name, len(bars)))
    return out


def tick(proxy, now=None):
    """지난 때가 있고 아직 안 받았으면 받는다 — 1분은 지난 때가 여럿이어도 한 번(그 사이는 못 채운다)."""
    now = now or _now()
    day = now.strftime("%Y%m%d")
    if now.weekday() >= 5:
        return False
    p = plan(proxy, now)
    if p["open"] is False:
        return False
    hm = (now.hour, now.minute)
    if hm >= p["until"]:
        return False
    if _status["day"] != day:
        _status.update(day=day, done1m=-1, done5m=False, last=[])
    passed = [i for i, s in enumerate(p["1m"]) if hm >= s]
    want1 = bool(passed) and passed[-1] > _status["done1m"]
    want5 = hm >= p["5m"] and not _status["done5m"]
    if not (want1 or want5) or not _lock.acquire(blocking=False):
        return False
    try:
        cfg = proxy.load_secrets()
        for period, want in (("1m", want1), ("5m", want5)):
            if not want:
                continue
            got = _get(proxy, cfg, period)
            if period == "1m":
                skipped = [i for i in passed[:-1] if i > _status["done1m"]]
                _status["done1m"] = passed[-1]
            else:
                skipped = []
                _status["done5m"] = all(n is not None for _, n in got)    # 못 받았으면 다음 바퀴에 다시
            _status["last"].append({"at": _now().strftime("%H:%M:%S"), "period": period, "got": dict(got),
                                    "skippedSlots": ["%02d:%02d" % p["1m"][i] for i in skipped], "lateMin": p["lateMin"]})
            print("  [지수 날 봉] %s %s 받음 — %s%s%s" % (
                day, period, " · ".join("%s %s" % (nm, "못 받음" if n is None else "%d봉" % n) for nm, n in got),
                " · 지난 때 %s 못 받음(서버가 늦게 뜸)" % ", ".join("%02d:%02d" % p["1m"][i] for i in skipped) if skipped else "",
                " · 늦은 분 못 읽음(보통 날 시각)" if p["lateMin"] is None else ""), flush=True)
        return True
    finally:
        _lock.release()


def bars(proxy, name, period, day):
    """그날 봉 — {code, period, day, bars: [{ts, open, high, low, close}]} · 과거 → 최신 · 없으면 bars [] · 이름이 없으면 None."""
    code = next((c for c, n in CODES if n == name), None)
    if code is None:
        return None
    with proxy._db_lock, proxy.db_conn() as conn:
        rows = conn.execute(
            "SELECT ts, open, high, low, close FROM candles WHERE code = ? AND period = ? AND ts >= ? AND ts < ? ORDER BY ts",
            (code, period, day, day + "z")).fetchall()
    return {"code": name, "period": period, "day": day, "bars": [dict(r) for r in rows]}


def days(proxy, name, period, limit=60):
    """그 봉이 쌓인 날 [(날, 봉 수)] — 최근 먼저."""
    code = next((c for c, n in CODES if n == name), None)
    if code is None:
        return []
    try:
        with proxy._db_lock, proxy.db_conn() as conn:
            return [{"day": d, "count": n} for d, n in conn.execute(
                "SELECT substr(ts, 1, 8) d, COUNT(*) FROM candles WHERE code = ? AND period = ? GROUP BY d ORDER BY d DESC LIMIT ?",
                (code, period, limit))]
    except Exception:
        return []


def status(proxy=None):
    s = dict(_status)
    if proxy is not None:
        p = plan(proxy)
        s.update(slots1m=["%02d:%02d" % x for x in p["1m"]], at5m="%02d:%02d" % p["5m"], lateMin=p["lateMin"], open=p["open"])
    return s


def start(proxy):
    """보내는 서버가 뜰 때 한 번."""
    def loop():
        time.sleep(60)
        while True:
            try:
                tick(proxy)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [지수 날 봉] 멈춤 (%s)" % type(e).__name__, flush=True)
            time.sleep(TICK)

    _status["running"] = True
    threading.Thread(target=loop, daemon=True, name="idx-day").start()
    return True
