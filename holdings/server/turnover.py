# -*- coding: utf-8 -*-
"""풀린 시총 · 거래 비율 — 단타 판 칸 둘의 서버 셈 (2026-11-23).

재권님 말씀 — 「전종목의 거래되는 총 시가 - 이건 표기가 안되고 있고, 거래되는 총량에 비해 몇%가 거래되는지도 표기가 안되고 있는데
이거 들어갈 자리는 단타쪽이면 좋을거 같아. 쌓아놓는건 서버에 여유가 생길때 지속적으로 받으면 좋을거같아. 단타칩에 걸려서 보여지는 종목은
실시간으로 보여지게 개선되면 돼」 → 받는 주기 「가」(장중 1분마다 전 종목 한 바퀴 · 11-23 08:3x · 개발2 카드 ①).

    풀린 시총(floatCap · 억원)   풀린 주식수 × 현재가 — 풀린 주식수는 발행주식수 × 유동비율(company_profile.floats() · 네이버 기업현황 한 곳)
    거래 비율(turn · %)          그날 누적 거래대금 ÷ 풀린 시총 × 100

받는 길
    판에 보이는 종목(칩 걸림)   단타 목록 · 판이 받는 현재가에 누적 거래대금이 함께 온다 — 그 자리에서 셈(실시간)
    그 밖 감시 목록 전부        장중 TURN_INTERVAL 마다 한 바퀴(dart 감시 목록 · 30종목 묶음 시세) — 그날 마지막 값을 turnover_day 에 쌓는다
                               묶음 시세 캐시를 함께 써서 투자자 판(INVESTOR_BOARD_REFRESH_INTERVAL)이 막 받은 종목은 다시 안 묻는다
    전날 대비(turnPrevPct · %)   오늘 지금까지 거래 비율 ÷ 전날 같은 시각까지 거래 비율 × 100 — 재권님 「거래 비율은 전날 동시간 대비로 해줘」(11-23 08:5x ·
                               색 기준은 지표 표 data/metrics.json turn_prev_pct) · 같은 시각 값은 turnover_slot(SLOT_MIN 분 칸 · SLOT_KEEP_DAYS 날만)
못 잰 칸은 None(「못 잼」 · 0 아님) — 유동비율을 아직 못 읽은 종목 · 거래대금이 안 온 종목 · 전날 그 칸이 없는 종목.
"""
import threading
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
TURN_INTERVAL = 60            # 장중 전 종목 한 바퀴 간격(초) — 재권님 「가」(11-23 · 장중 1분마다) · 785종목이면 묶음 27건(KIS 초당 0.45건쯤)
AFTER_MIN = 5                 # 정규장 끝 뒤 이 분 안에 한 바퀴 더 — 그날 마지막 거래대금을 쌓는다
_SCHEMA = ("CREATE TABLE IF NOT EXISTS turnover_day (day TEXT NOT NULL, code TEXT NOT NULL, value INTEGER, price INTEGER, "
           "float_shares INTEGER, at TEXT, PRIMARY KEY (day, code))")

SLOT_MIN = 1                  # 「같은 시각」 칸(분) — 바퀴(TURN_INTERVAL 1분)마다 한 칸 · 5분이던 것을 줄임(qa 덧 11-23 — 칸 끝 무렵 값과 견줘 장 초반 전날 대비가 낮게 나옴)
SLOT_KEEP_DAYS = 2            # 시각 칸 표는 오늘 · 전날만 — 전날과 견주는 데만 쓴다(그날 마지막 값은 turnover_day 가 1년) · 785종목 × 390칸 하루 30만 줄 남짓
_SLOT_SCHEMA = ("CREATE TABLE IF NOT EXISTS turnover_slot (day TEXT NOT NULL, slot TEXT NOT NULL, code TEXT NOT NULL, value INTEGER, price INTEGER, "
                "PRIMARY KEY (day, slot, code))")

_status = {"at": None, "codes": 0, "got": 0, "error": None, "rounds": 0}


def _now():
    return datetime.now(KST)


def calc(price, value, fl):
    """(floatCap 억원 | None, turn % | None). fl — 풀린 주식수."""
    if not price or not fl:
        return None, None
    won = fl * price
    cap = round(won / 1e8)
    turn = round(value / won * 100, 2) if value is not None else None
    return cap, turn


def _slot(hm):
    return "%02d%02d" % divmod(hm // SLOT_MIN * SLOT_MIN, 60)


def prev_slot(proxy, codes, day, slot):
    """오늘 앞 마지막 날의 그 칸(없으면 그 앞 가장 가까운 칸) 값 {code: (value, price)} — 표가 없거나 못 읽으면 {}."""
    if not codes:
        return {}
    q = ",".join("?" * len(codes))
    try:
        with proxy.db_conn() as conn:
            pd = conn.execute("SELECT MAX(day) FROM turnover_slot WHERE day < ?", (day,)).fetchone()[0]
            if not pd:
                return {}
            got = conn.execute("SELECT code, value, price, slot FROM turnover_slot WHERE day = ? AND slot <= ? AND code IN (%s) ORDER BY slot"
                               % q, [pd, slot] + list(codes)).fetchall()
    except Exception:
        return {}
    return {c: (v, p) for c, v, p, _ in got}            # 칸 순으로 덮어 가장 늦은 칸이 남음


def _prev_pct(turn, pv, fl):
    if turn is None or not pv:
        return None
    _, t0 = calc(pv[1], pv[0], fl)
    return round(turn / t0 * 100, 1) if t0 else None


def fill(rows, prices=None, proxy=None):
    """rows[] 에 floatCap · turn · turnPrevPct 를 붙인다 — prices {code: {price, value}} 가 있으면 그 값(실시간) · 없으면 줄의 price 와 쌓인 그날 값.
    proxy 를 주면 전날 같은 시각 칸과 견준다(없으면 turnPrevPct null)."""
    import company_profile
    fl = company_profile.floats()
    now = _now()
    prev = prev_slot(proxy, [r["code"] for r in rows], now.strftime("%Y%m%d"), _slot(now.hour * 60 + now.minute)) if proxy is not None else {}
    for r in rows:
        p = (prices or {}).get(r["code"]) or {}
        price = p.get("price") if p else r.get("price")
        value = p.get("value") if p else r.get("value")
        f = fl.get(r["code"])
        r["floatCap"], r["turn"] = calc(price, value, f)
        r["turnPrevPct"] = _prev_pct(r["turn"], prev.get(r["code"]), f)


def day_rows(proxy, day, codes):
    """쌓인 그날 값 {code: {price, value, floatShares, at}} — 지난 판 칸을 채울 때."""
    if not codes:
        return {}
    q = ",".join("?" * len(codes))
    try:
        with proxy.db_conn() as conn:
            got = conn.execute("SELECT code, value, price, float_shares, at FROM turnover_day WHERE day = ? AND code IN (%s)" % q,
                               [day] + list(codes)).fetchall()
    except Exception:
        return {}                                      # 표가 아직 없음 — 못 잼
    return {c: {"value": v, "price": p, "floatShares": f, "at": a} for c, v, p, f, a in got}


def fill_day(proxy, day, rows):
    """지난 판(굳힌 날) 줄에 그날 쌓인 마지막 값으로 floatCap · turn — 쌓기 전 날은 None."""
    codes = [r["code"] for r in rows]
    got = day_rows(proxy, day, codes)
    pd = None
    try:
        with proxy.db_conn() as conn:
            pd = conn.execute("SELECT MAX(day) FROM turnover_day WHERE day < ?", (day,)).fetchone()[0]
    except Exception:
        pass
    prev = day_rows(proxy, pd, codes) if pd else {}
    for r in rows:
        g = got.get(r["code"]) or {}
        r["floatCap"], r["turn"] = calc(g.get("price"), g.get("value"), g.get("floatShares"))
        pg = prev.get(r["code"]) or {}
        r["turnPrevPct"] = _prev_pct(r["turn"], (pg.get("value"), pg.get("price")) if pg else None, g.get("floatShares"))   # 굳힌 판 — 그날 끝 ÷ 전날 끝


def _store(proxy, day, quotes, fl):
    import dt30
    at = _now().strftime("%H:%M:%S")
    rows = [(day, c, q.get("value"), q.get("price"), fl.get(c), at) for c, q in quotes.items() if q.get("price")]
    if not rows:
        return 0
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        conn.executemany("INSERT OR REPLACE INTO turnover_day (day, code, value, price, float_shares, at) VALUES (?,?,?,?,?,?)", rows)
        keep = [d for (d,) in conn.execute("SELECT DISTINCT day FROM turnover_day ORDER BY day DESC LIMIT ?", (dt30.DAYS_KEEP,))]
        if keep:
            conn.execute("DELETE FROM turnover_day WHERE day < ?", (keep[-1],))   # 보관은 단타 판과 같은 거래일 수(dt30.DAYS_KEEP)
        now = _now()
        slot = _slot(min(now.hour * 60 + now.minute, dt30._close_min(proxy, now)))   # 끝난 뒤 바퀴는 끝 칸에
        conn.execute(_SLOT_SCHEMA)
        conn.executemany("INSERT OR REPLACE INTO turnover_slot (day, slot, code, value, price) VALUES (?,?,?,?,?)",
                         [(d, slot, c, v, p) for d, c, v, p, _, _ in rows])
        ks = [d for (d,) in conn.execute("SELECT DISTINCT day FROM turnover_slot ORDER BY day DESC LIMIT ?", (SLOT_KEEP_DAYS,))]
        if ks:
            conn.execute("DELETE FROM turnover_slot WHERE day < ?", (ks[-1],))
    return len(rows)


def round_once(proxy, cfg, day):
    """감시 목록 전부 한 바퀴 — 쌓은 종목 수."""
    import company_profile
    import dart
    codes = [r["stock_code"] for r in dart.universe_rows(None) if (r["stock_code"] or "").isdigit() and len(r["stock_code"]) == 6]
    quotes, _ = proxy.fetch_quotes_multi(cfg, codes, max_age=TURN_INTERVAL // 2)
    n = _store(proxy, day, quotes, company_profile.floats())
    _status.update(at=_now().strftime("%H:%M:%S"), codes=len(codes), got=n, error=None, rounds=_status["rounds"] + 1)
    return n


def status():
    return dict(_status, turnSec=TURN_INTERVAL)


def start(proxy):
    """쓰는 서버가 뜰 때 한 번 — 평일 정규장 동안 TURN_INTERVAL 마다 · 끝난 뒤 AFTER_MIN 안 한 번."""
    if not proxy.marketdb.writable():
        return False
    import dt30
    import market_hours

    def loop():
        proxy._prio.low = True                         # 여유분으로 — 화면 · 칩 종목(chip_live)이 막 불렀으면 비켜선다(kis_proxy._rate_limit · 재권님 「서버에 여유가 생길때」)
        time.sleep(60)                                 # 뜬 직후 다른 일과 겹치지 않게
        last = 0.0
        closed = None
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = now.hour * 60 + now.minute
                if now.weekday() < 5 and market_hours.today(proxy, day=day, now=now).get("open") is not False:
                    o = dt30.OPEN_AT[0] * 60 + dt30.OPEN_AT[1] + dt30.late_min(proxy, now)
                    c = dt30._close_min(proxy, now)
                    if o <= hm < c and time.time() - last >= TURN_INTERVAL:
                        last = time.time()
                        round_once(proxy, proxy.load_secrets(), day)
                    elif c <= hm < c + AFTER_MIN + 1 and closed != day and hm >= c + 1:
                        closed = day                   # 끝난 뒤 한 번 — 그날 마지막 값
                        round_once(proxy, proxy.load_secrets(), day)
                        print("  [거래 비율] %s 마감 값 %d종목 쌓음" % (day, _status["got"]), flush=True)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [거래 비율] 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            time.sleep(10)

    threading.Thread(target=loop, daemon=True, name="turnover").start()
    return True
