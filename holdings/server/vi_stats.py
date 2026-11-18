# -*- coding: utf-8 -*-
"""VI · 급등 뒤 얼마나 오르나 — 그날 VI · 급등을 하루 한 번 쌓고, 발동 값 대비 30분 · 60분 · 14:00 · 그날 최고를 셈한다 (2026-11-18).

재권님 — 단타 판 묶음 넷 ④ 「VI 발동 뒤 30분 · 60분 · 14시 · 그날 최고 상승 통계 주소」 → 「응 만들어」(11-18 18:0x · 개발2 창).

    쌓기      그날 VI · 급등(intraday_alerts.today() — 홈 「오늘 VI · 급등」 칸과 같은 목록 · 정규장)을 장 뒤 STORE_AT 부터 바퀴마다
              market.db vi_events(날 · 종목 · VI|급등 · 시각 · 발동 값) — 같은 종목 · 같은 갈래는 그날 첫 것만(VI 가 여러 번 나도 첫 발동)
    값        발동 값 = VI 는 VI 발동가(vi_prc) · 급등은 알림이 본 때 현재가 · 없으면 그 시각이 든 5분봉 시가
              +30 · +60 = 그 시각에서 30 · 60분 뒤 시각이 든 5분봉 종가 · 14:00 = 13:55 봉 종가(발동이 14:00 뒤면 null) ·
              최고 = 그 시각 봉부터 15:25 봉까지 고가 중 최고(15:25 봉이 있어야 셈)
              전부 발동 값 대비 % · 봉이 없으면(장 중 · 못 받음) null(못 잼 · 0 아님)
    봉        5분봉은 DB candles(미리받기가 쌓은 순위 목록 둘레) — 없는 종목은 FILL_FROM 뒤 그날 1분봉을 받아 5분봉으로 채운다
              (kis_proxy._kr_past_day · 종목마다 KIS 몇 건 · 하루 FILL_MAX 종목까지 · 초당 한도는 kis_get 이 지킨다)
    지난 날   이 모듈이 뜨기 전 날은 쌓인 VI 목록이 없다 — 되채움은 따로(보드 카드 「VI 발동 뒤 얼마나 오르나 통계 … 지난 날 되채움」)
    주소      GET /api/kis/vi-stats?days=30 — 갈래(VI · 급등)마다 r30 · r60 · r1400 · rmax 각각 n · 오름 수 · 오름 % · 평균 · 가운데 · 3% 넘음 · 못 잼
              + 날마다 사건 목록(그 값들 포함)
"""
import threading
import time
from datetime import datetime, timedelta, timezone

import dt30
import dt30_win

KST = timezone(timedelta(hours=9))
STORE_AT = (15, 40)          # 그날 VI · 급등을 쌓기 시작하는 때(정규장 끝 뒤) — 그 뒤 바퀴마다 빠진 것만 더한다
FILL_FROM = dt30.QUIET[1]    # 봉이 없는 종목의 그날 1분봉을 받는 때 — 단타 판 되채우기가 KIS 를 쓰기 시작하는 때(넥장 뒤 · 값은 dt30 한 곳)
FILL_MAX = 300               # 하루 봉 받는 종목 수 한도
TICK = 60                    # 바퀴(초)
DAYS_DEFAULT = 30
DAYS_MAX = 120               # 주소 days 상한 — kis_proxy 가 읽는다
BIG_PCT = dt30_win.BIG_PCT   # 「3% 넘음」 문턱 — 칩별 승률과 같은 값(사본 안 둠 · 개념정의 검수)
BAR_MIN = 5
SPANS = (("r30", 30), ("r60", 60))
AT_1400 = "1355"             # 14:00 값 = 13:55~14:00 봉 종가
CLOSE_BAR = "1525"           # 최고를 보는 끝 봉(15:25~15:30)
FILLED_KEY = "vi_stats_filled"   # sync_meta — 봉 채움을 마친 날
_SCHEMA = """CREATE TABLE IF NOT EXISTS vi_events (day TEXT, code TEXT, kind TEXT, at TEXT, name TEXT, price REAL,
              PRIMARY KEY (day, code, kind))"""
_status = {"error": None, "stored": None, "filled": 0, "at": None}


def _now():
    return datetime.now(KST)


def store(proxy, day=None):
    """그날 VI · 급등을 쌓는다(이미 있는 것은 그대로) → 새로 쌓은 수."""
    import intraday_alerts
    got = intraday_alerts.today()
    day = got.get("day") or day
    n = 0
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        for it in sorted(got.get("items") or [], key=lambda x: x.get("t") or ""):
            if not it.get("code") or not it.get("t"):
                continue
            cur = conn.execute("INSERT OR IGNORE INTO vi_events (day, code, kind, at, name, price) VALUES (?,?,?,?,?,?)",
                               (day, it["code"], "VI" if it.get("kind") == "vi" else "급등", it["t"], it.get("name") or "", it.get("price")))
            n += cur.rowcount or 0
    return n


def _bars(proxy, day, codes):
    """{code: {HHMM: (open, high, close)}} — 그날 5분봉."""
    out = {}
    if not codes:
        return out
    with proxy.db_conn() as conn:
        q = "SELECT code, ts, open, high, close FROM candles WHERE period = '5m' AND ts >= ? AND ts <= ? AND code IN (%s)" % ",".join("?" * len(codes))
        for code, ts, o, h, c in conn.execute(q, [day + "0800", day + "2000"] + list(codes)):
            out.setdefault(code, {})[ts[8:12]] = (o, h, c)
    return out


def _floor5(m):
    return m - m % BAR_MIN


def _hm(m):
    return "%02d%02d" % divmod(m, 60)


def measure(ev, bars):
    """사건 하나 → {base, r30, r60, r1400, rmax} · 못 재면 그 칸 null."""
    d = bars or {}
    t = int(ev["at"][0:2]) * 60 + int(ev["at"][3:5])
    m0 = _floor5(t)
    b0 = d.get(_hm(m0))
    base = ev.get("price") or (b0[0] if b0 else None)
    out = {"base": base, "r30": None, "r60": None, "r1400": None, "rmax": None}
    if not base:
        return out
    pct = lambda v: round((v / base - 1) * 100, 2) if v else None
    for key, mins in SPANS:
        b = d.get(_hm(_floor5(t + mins)))
        out[key] = pct(b[2]) if b else None
    a14 = int(AT_1400[:2]) * 60 + int(AT_1400[2:])
    if m0 <= a14:
        b = d.get(AT_1400)
        out["r1400"] = pct(b[2]) if b else None
    if d.get(CLOSE_BAR):                               # 끝 봉까지 있을 때만 그날 최고(장 중 · 봉 못 받음이면 못 잼)
        end = int(CLOSE_BAR[:2]) * 60 + int(CLOSE_BAR[2:])
        his = [d[_hm(m)][1] for m in range(m0, end + 1, BAR_MIN) if _hm(m) in d and d[_hm(m)][1]]
        out["rmax"] = pct(max(his)) if his else None
    return out


def _stat(vals):
    v = sorted(x for x in vals if x is not None)
    miss = sum(1 for x in vals if x is None)
    n = len(v)
    if not n:
        return {"n": 0, "up": 0, "upRate": None, "avg": None, "median": None, "over3": 0, "unmeasured": miss}
    mid = v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2
    up = sum(1 for x in v if x > 0)
    return {"n": n, "up": up, "upRate": round(up / n * 100, 1), "avg": round(sum(v) / n, 2), "median": round(mid, 2),
            "over3": sum(1 for x in v if x > BIG_PCT), "unmeasured": miss}


def summary(proxy, days=DAYS_DEFAULT):
    """주소 /api/kis/vi-stats 의 (data, meta)."""
    with proxy.db_conn() as conn:
        try:
            ds = [d for (d,) in conn.execute("SELECT DISTINCT day FROM vi_events ORDER BY day DESC LIMIT ?", (days,))]
            evs = [dict(zip(("day", "code", "kind", "at", "name", "price"), r)) for r in conn.execute(
                "SELECT day, code, kind, at, name, price FROM vi_events WHERE day >= ? ORDER BY day DESC, at", (ds[-1] if ds else "99999999",))]
        except Exception:
            ds, evs = [], []
    by_day = {}
    for e in evs:
        by_day.setdefault(e["day"], []).append(e)
    keys = ("r30", "r60", "r1400", "rmax")
    groups = {"VI": {k: [] for k in keys}, "급등": {k: [] for k in keys}}
    daily = []
    for day in ds:
        es = by_day.get(day) or []
        bars = _bars(proxy, day, sorted({e["code"] for e in es}))
        rows = []
        for e in es:
            m = measure(e, bars.get(e["code"]))
            for k in keys:
                groups[e["kind"]][k].append(m[k])
            rows.append(dict(e, **m))
        daily.append({"day": day, "events": rows})
    data = {kind: {k: _stat(v) for k, v in g.items()} for kind, g in groups.items()}
    data["days"] = daily
    meta = {"days": len(ds), "from": ds[-1] if ds else None, "to": ds[0] if ds else None, "bigPct": BIG_PCT,
            "spans": {"r30": "발동 뒤 30분", "r60": "발동 뒤 60분", "r1400": "14:00", "rmax": "그날 최고(15:30 까지)"},
            "base": "VI 는 VI 발동가 · 급등은 알림이 본 때 현재가 · 없으면 그 시각 5분봉 시가 — 전부 발동 값 대비 %",
            "note": "정규장 VI · 급등만(홈 「오늘 VI · 급등」 목록) · 종목 · 갈래마다 그날 첫 발동 · 봉이 없으면 못 잼(null) · 이 모듈이 뜬 날부터 쌓임",
            "storedAt": _status["stored"], "filled": _status["filled"], "error": _status["error"]}
    return data, meta


def fill_bars(proxy, day):
    """그날 사건 중 끝 봉(CLOSE_BAR)까지 5분봉이 없는 종목의 그날 봉을 받는다 → 받은 종목 수."""
    with proxy.db_conn() as conn:
        codes = sorted({c for (c,) in conn.execute("SELECT code FROM vi_events WHERE day = ?", (day,))})
    have = _bars(proxy, day, codes)
    need = [c for c in codes if CLOSE_BAR not in (have.get(c) or {})][:FILL_MAX]
    cfg = proxy.load_secrets()
    n = 0
    for c in need:
        try:
            proxy._kr_past_day(cfg, c, day)
            n += 1
        except Exception:
            pass
    return n


def status():
    return dict(_status, storeAt="%02d:%02d" % STORE_AT, fillFrom="%02d:%02d" % FILL_FROM)


def start(proxy):
    """쓰는 서버가 뜰 때 한 번 — 평일 STORE_AT 뒤 그날 VI · 급등을 쌓고, FILL_FROM 뒤 봉 없는 종목을 한 번 채운다."""
    if not proxy.marketdb.writable():
        return False

    def loop():
        time.sleep(50)
        import dart
        filled = dart._meta_get(FILLED_KEY)           # 그날 채움을 한 날 — DB 에 둔다(재시작마다 다시 받지 않게 · qa 덧)
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = now.hour * 60 + now.minute
                if now.weekday() < 5 and hm >= STORE_AT[0] * 60 + STORE_AT[1]:
                    if store(proxy, day):
                        _status["stored"] = now.strftime("%H:%M")
                    if filled != day and hm >= FILL_FROM[0] * 60 + FILL_FROM[1]:
                        filled = day                     # 멈춰도 그날은 다시 안 돈다
                        dart._meta_set(FILLED_KEY, day)
                        n = fill_bars(proxy, day)
                        _status["filled"] += n
                        if n:
                            print("  [VI 통계] %s 봉 없던 %d종목 채움" % (day, n), flush=True)
                _status.update(error=None, at=now.strftime("%H:%M:%S"))
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [VI 통계] 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="vi-stats").start()
    return True
