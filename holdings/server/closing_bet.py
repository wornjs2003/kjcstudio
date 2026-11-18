# -*- coding: utf-8 -*-
"""종가배팅 판 서버 값 — 정규장 많이 오른 종목을 날마다 쌓고, 장 뒤(넥장) 흐름 · 다음 날 프리장 첫 값 · 그 시장 형편을 붙인다 (2026-11-18).

재권님 11-18 11:2x 「응 만들어」(시황분석 창 — Insight 「투자 전략」 의 「단타 · 종가배팅」 탭) → 서버 몫 착수 안에 「응 만들어」(11:40 · 개발1 창).
화면은 시황분석이 만든다. 판정 기준은 시황분석 2년 대입(233건)에 쓴 셈 그대로다(11-18 시황분석 답).

    언제      평일 15:41~15:59 — nxt_board.save_close 가 받은 KRX(J) 멀티 시세를 그대로 넘겨받는다(따로 안 부름)
                후보 = 정규장 등락 CAND_PCT 이상(BIG 두 종목은 BIG_PCT 이상) · 코스피 · 코스닥 주권만(nxt_pre 마스터)
                후보마다 종목 현재가 한 번(시가총액) · 지수 둘 일봉(MKT_WINDOWS 구간씩)
              평일 17:00~20:00 — 후보만 AFTER_EVERY 초마다 넥장(NX) 멀티 시세
                rebreakAt = 17:00 뒤 처음 정규장 종가 이상이 된 시각(앞 번보다 NX 누적 거래량이 늘었을 때의 값만 센다 —
                            체결이 없으면 현재가에 앞 시각 값이 남아 있어서다 · nxt_board 머리 「장외 체결」 과 같은 까닭)
                afterLow  = 그 사이 본 값 중 가장 낮은 것(AFTER_EVERY 초마다 본 값이라 참 저가보다 높을 수 있다)
              평일 20:01~20:29 — afterLast = 장외 마지막가(15:2x 메인장 마감 뒤 체결이 없으면 null)
              다음 거래일 08:51~15:00 — pre = 그날 넥장 분봉(08:00~08:49) 중 처음 체결된 봉의 시가(후보마다 1~2번)
    판정      pass.rise    정규장 등락 ≥ RULE.rise 그리고 < RULE.limitUp(상한가 근처는 종가에 못 산다 — 대입에서 뺐다)
              pass.pos     종가 위치 (종가−저가)/(고가−저가) ≥ RULE.pos
              pass.top     rise · pos 를 통과한 종목들 중 거래대금 순위 ≤ RULE.top
              pass.rebreak rebreakAt 이 있음(20:00 까지)
              pass.mkt     그 종목 시장 지수가 「할 때」 — 지수 종가 > 20일 평균(그날 포함) 그리고 종가 ÷ 앞 120거래일 종가 최고(그날 빼고) − 1 > RULE.fromHigh
              buy          다섯 다 true · 하나라도 아직 모르면(null) null
    저장      market.db 의 `closing_bet`(날 · 종목) · `closing_mkt`(날 · 시장)
    주소      GET /api/nxt/closing-bet?day=YYYYMMDD(없으면 가장 최근) — 모양은 board() 주석 · 「없음」 은 null(0 아님)

8765 만 받는다(kis_proxy 가 is_sender 로 부른다) · 읽기는 어느 서버든 자기 DB 로. 알림은 없다(화면만).
"""

import threading
import time
from datetime import datetime, timedelta, timezone

import nxt_pre
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))

CAND_PCT = 8.0                  # 후보 — 정규장 등락 이 % 이상
BIG = ("005930", "000660")      # 삼성전자 · SK하이닉스 — 크기가 커서 후보 선을 낮춘다
BIG_PCT = 3.0
RULE = {"rise": 10.0, "limitUp": 29.5, "pos": 0.9, "top": 30, "big": BIG_PCT, "cand": CAND_PCT,
        "ma": 20, "highDays": 120, "fromHigh": -10.0}
AFTER_AT, AFTER_UNTIL = (17, 0), (20, 0)
AFTER_EVERY = 120               # 장 뒤 몇 초마다 — 재권님 승인 「2분마다」(11-18)
LAST_AT, LAST_UNTIL = (20, 1), (20, 30)
PRE_AT, PRE_UNTIL = (8, 51), (15, 0)
INDEX = (("kospi", "0001"), ("kosdaq", "1001"))
MKT_WINDOWS = 3                 # 지수 일봉을 100일(달력) 구간씩 몇 번 — 121거래일을 넉넉히 덮는다
DAYS_MAX = 60
TICK = 20

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS closing_bet (
        day TEXT NOT NULL, code TEXT NOT NULL, market TEXT, name TEXT,
        close INTEGER, high INTEGER, low INTEGER, value INTEGER, chg REAL, cap INTEGER,
        base_vol INTEGER, last_vol INTEGER, main_vol INTEGER,
        rebreak_at TEXT, after_low INTEGER, after_last INTEGER, pre INTEGER, pre_day TEXT, saved_at TEXT,
        PRIMARY KEY (day, code))""",
    """CREATE TABLE IF NOT EXISTS closing_mkt (
        day TEXT NOT NULL, market TEXT NOT NULL, close REAL, chg REAL, ma20 REAL, high120 REAL, saved_at TEXT,
        PRIMARY KEY (day, market))""",
)

_status = {"candDay": None, "candAt": None, "cands": None, "mktAt": None, "afterAt": None, "afterRounds": 0,
           "lastDay": None, "lastAt": None, "preDay": None, "preAt": None, "preGot": None, "error": None}


def _now():
    return datetime.now(KST)


def _init(proxy):
    with proxy._db_lock, proxy.db_conn() as conn:
        for q in _SCHEMA:
            conn.execute(q)


def is_candidate(code, chg):
    if chg is None:
        return False
    return chg >= (BIG_PCT if code in BIG else CAND_PCT)


def _cap(proxy, cfg, code):
    """시가총액(억원) — 종목 현재가 한 번. 못 받으면 null."""
    try:
        data = proxy.kis_get(cfg, "/uapi/domestic-stock/v1/quotations/inquire-price",
                             {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}, "FHKST01010100")
        return proxy._num(((data or {}).get("output") or {}).get("hts_avls"), int)
    except Exception:
        return None


def _index_bars(proxy, cfg, code, today):
    """지수 일봉 [(날, 종가)] 오래된 것부터 — 100일(달력) 구간씩 MKT_WINDOWS 번."""
    got = {}
    to = today
    for _ in range(MKT_WINDOWS):
        frm = to - timedelta(days=99)
        for b in proxy._index_bars_from_kis(cfg, code, "D", frm, to):
            got[b["ts"]] = b["close"]
        to = frm - timedelta(days=1)
        time.sleep(nxt_pre.GAP_SEC)
    return sorted(got.items())


def save_market(proxy, day):
    """그날 코스피 · 코스닥 — 종가 · 등락 · 20일 평균 · 앞 120거래일 종가 최고. 저장한 수(그날 봉이 없으면 안 씀)."""
    _init(proxy)
    cfg = proxy.load_secrets()
    today = datetime.strptime(day, "%Y%m%d")
    stamp = _now().isoformat(timespec="seconds")
    rows = []
    for market, code in INDEX:
        try:
            bars = _index_bars(proxy, cfg, code, today)
        except Exception as e:
            _status["error"] = "지수 %s: %s" % (market, safe_message(e, 100))
            continue
        if not bars or bars[-1][0] != day:
            continue
        closes = [c for _d, c in bars]
        close = closes[-1]
        prev = closes[-2] if len(closes) >= 2 else None
        n = RULE["ma"]
        ma = round(sum(closes[-n:]) / n, 2) if len(closes) >= n else None
        k = RULE["highDays"]
        hi = max(closes[-k - 1:-1]) if len(closes) >= k + 1 else None
        rows.append((day, market, close, round((close / prev - 1) * 100, 2) if prev else None, ma, hi, stamp))
    if rows:
        with proxy._db_lock, proxy.db_conn() as conn:
            conn.executemany("INSERT OR REPLACE INTO closing_mkt (day, market, close, chg, ma20, high120, saved_at) "
                             "VALUES (?,?,?,?,?,?,?)", rows)
    _status["mktAt"] = stamp
    return len(rows)


def save_candidates(proxy, day, krx):
    """nxt_board.save_close 가 15:41 에 받은 J 멀티 시세 {code: {price, high, low, value, pct, name}} 로 그날 후보를 쌓는다.
    후보 수. 이미 쌓은 날이면 값만 다시 쓴다(뒤에 붙인 장 뒤 · 프리장 칸은 안 지운다)."""
    _init(proxy)
    cfg = proxy.load_secrets()
    stamp = _now().isoformat(timespec="seconds")
    cands = [(c, r) for c, r in krx.items()
             if nxt_pre.MARKET_OF.get(c) in ("kospi", "kosdaq") and r.get("price") and is_candidate(c, r.get("pct"))]
    with proxy._db_lock, proxy.db_conn() as conn:
        try:
            mv = {r[0]: r[1] for r in conn.execute("SELECT code, main_vol FROM nxt_board WHERE day = ?", (day,))}
        except Exception:
            mv = {}
    rows = []
    for code, r in cands:
        rows.append((day, code, nxt_pre.MARKET_OF.get(code), r.get("name"), r.get("price"), r.get("high"), r.get("low"),
                     r.get("value"), r.get("pct"), _cap(proxy, cfg, code), mv.get(code), stamp))
        time.sleep(nxt_pre.GAP_SEC)
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.executemany(
            "INSERT INTO closing_bet (day, code, market, name, close, high, low, value, chg, cap, main_vol, saved_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(day, code) DO UPDATE SET close = excluded.close, high = excluded.high, "
            "low = excluded.low, value = excluded.value, chg = excluded.chg, cap = COALESCE(excluded.cap, closing_bet.cap), "
            "main_vol = COALESCE(excluded.main_vol, closing_bet.main_vol), market = excluded.market, name = excluded.name", rows)
    _status.update(candDay=day, candAt=stamp, cands=len(rows))
    try:
        save_market(proxy, day)
    except Exception as e:
        _status["error"] = "시장 칸: %s" % safe_message(e, 100)
    return len(rows)


def _nx(proxy, cfg, codes):
    """{code: {price, vol}} — 넥장(NX) 멀티 시세"""
    out = {}
    codes = list(codes)
    for i in range(0, len(codes), nxt_pre.MULTI_MAX):
        params = {}
        for n, c in enumerate(codes[i:i + nxt_pre.MULTI_MAX], 1):
            params["FID_COND_MRKT_DIV_CODE_%d" % n] = "NX"
            params["FID_INPUT_ISCD_%d" % n] = c
        data = proxy.kis_get(proxy.load_secrets() if cfg is None else cfg,
                             "/uapi/domestic-stock/v1/quotations/intstock-multprice", params, "FHKST11300006")
        for r in (data or {}).get("output") or []:
            code = (r.get("inter_shrn_iscd") or "").strip()
            if code:
                out[code] = {"price": proxy._num(r.get("inter2_prpr"), int), "vol": proxy._num(r.get("acml_vol"), int)}
        time.sleep(nxt_pre.GAP_SEC)
    return out


def after_round(proxy, day, hm):
    """장 뒤 한 번 — 후보마다 체결이 늘었으면 그 값으로 저가 · 종가 다시 넘음을 본다. 본 종목 수."""
    with proxy._db_lock, proxy.db_conn() as conn:
        rs = [dict(r) for r in conn.execute(
            "SELECT code, close, base_vol, last_vol, rebreak_at, after_low FROM closing_bet WHERE day = ?", (day,))]
    if not rs:
        return 0
    nx = _nx(proxy, proxy.load_secrets(), [r["code"] for r in rs])
    upd = []
    for r in rs:
        n = nx.get(r["code"])
        if not n or n["vol"] is None:
            continue
        if r["base_vol"] is None:                 # 17:00 뒤 첫 번 — 거래량 기준만 잡는다(그 전 체결 값은 안 센다)
            upd.append((n["vol"], n["vol"], r["rebreak_at"], r["after_low"], day, r["code"]))
            continue
        traded = n["vol"] > (r["last_vol"] or r["base_vol"])
        rb, low = r["rebreak_at"], r["after_low"]
        if traded and n["price"]:
            if rb is None and r["close"] and n["price"] >= r["close"]:
                rb = "%02d%02d" % hm
            low = n["price"] if low is None else min(low, n["price"])
        upd.append((r["base_vol"], n["vol"], rb, low, day, r["code"]))
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.executemany("UPDATE closing_bet SET base_vol = ?, last_vol = ?, rebreak_at = ?, after_low = ? "
                         "WHERE day = ? AND code = ?", upd)
    _status["afterAt"] = _now().isoformat(timespec="seconds")
    _status["afterRounds"] = (_status.get("afterRounds") or 0) + 1
    return len(upd)


def save_last(proxy, day):
    """20:01 — 장외 마지막가. 메인장 마감(15:2x) 뒤 체결이 없었으면 null · 메인장 거래량을 못 쟀으면 17시 기준과 견준다."""
    with proxy._db_lock, proxy.db_conn() as conn:
        rs = [dict(r) for r in conn.execute("SELECT code, main_vol, base_vol FROM closing_bet WHERE day = ?", (day,))]
    if not rs:
        return 0
    nx = _nx(proxy, proxy.load_secrets(), [r["code"] for r in rs])
    upd = []
    for r in rs:
        n = nx.get(r["code"])
        if not n or n["vol"] is None:
            continue
        ref = r["main_vol"] if r["main_vol"] is not None else r["base_vol"]
        traded = ref is not None and n["vol"] > ref
        upd.append((n["price"] if traded and n["price"] else None, day, r["code"]))
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.executemany("UPDATE closing_bet SET after_last = ? WHERE day = ? AND code = ?", upd)
    _status.update(lastDay=day, lastAt=_now().isoformat(timespec="seconds"))
    return len(upd)


def _first_pre(proxy, cfg, code, day):
    """그날 넥장 08:00~08:49 분봉 중 처음 체결된 봉의 시가 — 없으면 None."""
    best = None
    for hour in ("082900", "085000"):
        data = proxy.kis_get(cfg, "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice",
                             {"FID_COND_MRKT_DIV_CODE": "NX", "FID_INPUT_ISCD": code, "FID_INPUT_HOUR_1": hour,
                              "FID_INPUT_DATE_1": day, "FID_PW_DATA_INCU_YN": "N", "FID_FAKE_TICK_INCU_YN": ""},
                             "FHKST03010230")
        for r in (data or {}).get("output2") or []:
            t = str(r.get("stck_cntg_hour") or "")[:4]
            if r.get("stck_bsop_date") != day or not (nxt_pre.PRE_FROM <= t <= nxt_pre.PRE_TO):
                continue
            if (proxy._num(r.get("cntg_vol"), int) or 0) <= 0:
                continue
            if best is None or t < best[0]:
                best = (t, proxy._num(r.get("stck_oprc"), int))
        time.sleep(nxt_pre.GAP_SEC)
        if best:
            break
    return best[1] if best else None


def save_pre(proxy, today):
    """앞 거래일 후보의 프리장 첫 값을 오늘 분봉으로 — 채운 수. 하나도 체결이 없으면(휴장) 안 쓴다."""
    with proxy._db_lock, proxy.db_conn() as conn:
        r = conn.execute("SELECT MAX(day) FROM closing_bet WHERE day < ?", (today,)).fetchone()
        prev = r[0] if r else None
        if not prev:
            return 0
        codes = [x[0] for x in conn.execute("SELECT code FROM closing_bet WHERE day = ? AND pre_day IS NULL", (prev,))]
    if not codes:
        return 0
    cfg = proxy.load_secrets()
    got = {}
    for c in codes:
        try:
            p = _first_pre(proxy, cfg, c, today)
        except Exception:
            continue
        if p:
            got[c] = p
    if got:          # 휴장(체결 0)이면 pre_day 를 안 적어 다음 거래일에 다시 본다
        with proxy._db_lock, proxy.db_conn() as conn:
            conn.executemany("UPDATE closing_bet SET pre = ?, pre_day = ? WHERE day = ? AND code = ?",
                             [(got.get(c), today, prev, c) for c in codes])
    _status.update(preDay=today, preAt=_now().isoformat(timespec="seconds"), preGot=len(got))
    return len(got)


def _go(m):
    """시장 「할 때」 — 종가 > 20일 평균 그리고 앞 120거래일 종가 최고 대비 > RULE.fromHigh. 값이 모자라면 null."""
    if not m or m.get("close") is None or m.get("ma20") is None or m.get("high120") is None:
        return None, None, None
    above = m["close"] > m["ma20"]
    fh = round((m["close"] / m["high120"] - 1) * 100, 2)
    return above, fh, bool(above and fh > RULE["fromHigh"])


def _r(x, n):
    return round(x, n) if x is not None else None


def board(proxy, day=None):
    """화면 한 장 —

        {day, preDay(다음 거래일 · 아직이면 null),
         mkt: {kospi: {chg, ma20Above, fromHigh, go}, kosdaq: {…}},
         rows: [{code, name, market, cap(억원), chg, pos, value(억원), close, rebreakAt('HHMM'), afterLow, afterLast, pre,
                 pass: {rise, pos, top, rebreak, mkt}, buy}]}  — 거래대금 순

    pass.rebreak · afterLast 는 20:01 전이면 null(아직 모름) · pre 는 다음 거래일 08:51 전이면 null.
    """
    _empty = {"day": None, "preDay": None, "mkt": {"kospi": None, "kosdaq": None}, "rows": []}
    with proxy._db_lock, proxy.db_conn() as conn:
        try:
            days = [r[0] for r in conn.execute("SELECT DISTINCT day FROM closing_bet ORDER BY day DESC LIMIT ?", (DAYS_MAX,))]
        except Exception:                        # 표가 아직 없다 — 쌓기 전
            return _empty, []
        if not days:
            return _empty, []
        day = day if day in days else days[0]
        rs = [dict(r) for r in conn.execute("SELECT * FROM closing_bet WHERE day = ?", (day,))]
        mk = {r["market"]: dict(r) for r in conn.execute("SELECT * FROM closing_mkt WHERE day = ?", (day,))}
    now = _now()
    done_after = day < now.strftime("%Y%m%d") or (now.hour, now.minute) >= LAST_AT
    mkt = {}
    for m, _c in INDEX:
        row = mk.get(m)
        above, fh, go = _go(row)
        mkt[m] = None if not row else {"chg": row.get("chg"), "ma20Above": above, "fromHigh": fh, "go": go}
    out = []
    for r in rs:
        rng = (r["high"] or 0) - (r["low"] or 0)
        pos = _r((r["close"] - r["low"]) / rng, 3) if r["close"] and r["low"] is not None and rng > 0 else None
        rise = None if r["chg"] is None else (RULE["rise"] <= r["chg"] < RULE["limitUp"])
        out.append({"code": r["code"], "name": r["name"], "market": r["market"], "cap": r["cap"], "chg": r["chg"], "pos": pos,
                    "value": _r(r["value"] / 1e8, 1) if r["value"] is not None else None, "close": r["close"],
                    "rebreakAt": r["rebreak_at"], "afterLow": r["after_low"], "afterLast": r["after_last"], "pre": r["pre"],
                    "_preDay": r["pre_day"], "_v": r["value"] or 0,
                    "pass": {"rise": rise, "pos": None if pos is None else pos >= RULE["pos"], "top": None,
                             "rebreak": True if r["rebreak_at"] else (False if done_after else None),
                             "mkt": (mkt.get(r["market"]) or {}).get("go")}})
    out.sort(key=lambda x: -x["_v"])
    ok = [x for x in out if x["pass"]["rise"] and x["pass"]["pos"]]   # 거래대금 순위는 rise · pos 통과한 것들 사이(시황분석 대입 그대로)
    for i, x in enumerate(ok):
        x["pass"]["top"] = i < RULE["top"]
    pre_day = None
    for x in out:
        if x["pass"]["top"] is None:
            x["pass"]["top"] = False if (x["pass"]["rise"] is False or x["pass"]["pos"] is False) else None
        ps = list(x["pass"].values())
        x["buy"] = False if False in ps else (None if None in ps else True)
        pre_day = pre_day or x.pop("_preDay")
        x.pop("_preDay", None)
        x.pop("_v")
    return {"day": day, "preDay": pre_day, "mkt": mkt, "rows": out}, days


def meta(days):
    return {"days": days, "rule": dict(RULE), "afterEverySec": AFTER_EVERY, "status": dict(_status)}


def start(proxy):
    """보내는 서버가 뜰 때 한 번 — 17~20시 장 뒤 · 20:01 마지막가 · 08:51 프리장 첫 값 바퀴(15:41 후보는 nxt_board 가 부른다)."""
    def loop():
        time.sleep(60)
        last_after = 0.0
        while True:
            try:
                now = _now()
                hm = (now.hour, now.minute)
                day = now.strftime("%Y%m%d")
                if now.weekday() < 5:
                    if AFTER_AT <= hm < AFTER_UNTIL and time.time() - last_after >= AFTER_EVERY:
                        last_after = time.time()
                        try:
                            after_round(proxy, day, hm)
                        except Exception as e:
                            _status["error"] = "장 뒤: %s" % safe_message(e, 120)
                    if LAST_AT <= hm < LAST_UNTIL and _status["lastDay"] != day:
                        _status["lastDay"] = day
                        try:
                            save_last(proxy, day)
                        except Exception as e:
                            _status["error"] = "마지막가: %s" % safe_message(e, 120)
                    if PRE_AT <= hm < PRE_UNTIL and _status["preDay"] != day:
                        _status["preDay"] = day          # 실패해도 그날은 한 번
                        try:
                            n = save_pre(proxy, day)
                            print("  [종가배팅] %s 프리장 첫 값 %s종목" % (day, n))
                        except Exception as e:
                            _status["error"] = "프리장: %s" % safe_message(e, 120)
            except Exception as e:
                print("  [종가배팅] 예기치 못한 오류: %s" % type(e).__name__)
            time.sleep(TICK)

    _init(proxy)
    threading.Thread(target=loop, daemon=True, name="closing-bet").start()
    return True
