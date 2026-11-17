# -*- coding: utf-8 -*-
"""프리장 거래량 급증 — 넥스트레이드 프리마켓에서 전날 같은 시각보다 거래량이 터진 종목 (2026-11-17).

재권님 — 「장시작하자마자 전날대비 거래량이터지는 종목 최대한 빠르게 알수있는 방법은?」 → 「프리장에서 필요해」 →
(가) 「가 인데 종목울 늘릴길은 없나??」 → 「8시~8시5분동안 이 리스트 만드는곳에 서버리소스를 집중한다 라는 룰로 하면 어디까지 가능한지 .
가능목표는 국내상장사 5천억이상 종목」 → 안 「응 만들어」(개발1 창 · 작업우선순위 경유).

    대상        순위 목록(dart.universe_rows · 시가총액 dart.UNIVERSE_MIN_CAP_EOK 이상 · ETF 포함) — 프리장 판(pre_flow)과 같은 목록
    훑기        멀티 시세 NX(넥스트레이드만) 누적 거래량 · 30종목씩(nxt_pre.fetch_nx) — 묶음 사이 쉼 없이
    주기        평일 BURST_FROM~BURST_UNTIL 은 BURST_SEC 마다(재권님 「8시~8시5분 … 서버리소스를 집중」) · 그 뒤 PRE_CLOSE 까지 SLOW_SEC 마다
                (11-13 8765 로그 — 08:00~08:05 KIS 787건 · 초당 평균 2.6 · 가장 많은 1초 23 / 예산 40 · 583 한 바퀴 20건 →
                 2초마다면 초당 10 · 예산의 25%)
    견줌        오늘 지금까지 누적 ÷ **앞 거래일 같은 분까지** 누적(그 분 봉 포함) — 앞 거래일 값은 NX 1분봉(FHKST03010230 · nxt_pre 되채우기와 같은 조회)을
                하루 한 번 받아 market.db `pre_minute` 에 분마다 누적으로 둔다(장 전 08:00 앞 · 또는 뜬 뒤 빠졌으면)
                앞 거래일 같은 분 누적이 MIN_PREV_SAME 주 미만이면 배율은 None(헛배율을 막는다 · 처음 값은 짐작 — qa 재생으로 다듬는다)
    판          배율 RATIO 이상을 배율 큰 순 · 칸 — 종목 · 현재가 · 등락률(전일 정규장 종가 대비) · 오늘 누적 · 전날 같은 분 누적 · 배율 · 거래대금(어림)
    없음        못 받은 값은 None(0 아님) · 넥스트레이드 거래량 합이 0 이면 휴장 · 장 전으로 보고 판을 비운다(nxt_pre 와 같은 셈)
    넥스트레이드 밖 종목은 프리장 거래가 없어 「영영」 안 나온다(11-14 잼 — 5천억 이상 주권 435 중 15거래일 한 번도 장 전 거래 없음 92)

8765(보내는 서버)만 훑고 판을 market.db `pre_surge_board` 에 남긴다 · 다른 서버(8764 · 세션)는 그 표를 읽는다(프리장 판과 같은 모양).
KIS 는 proxy.kis_get(예산 · 토큰은 그쪽). 알림은 없다.
"""
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import nxt_pre

KST = timezone(timedelta(hours=9))

PRE_OPEN = (8, 0)
BURST_FROM = (8, 0)        # 서버 여유를 몰아 쓰는 구간 — 재권님 「8시~8시5분」
BURST_UNTIL = (8, 5)
PRE_CLOSE = (8, 50)        # 넥스트레이드 프리마켓 끝 — 이 뒤로는 안 훑는다(09:00 부터는 메인장이 섞인다)
BURST_SEC = 2              # 몰아 쓰는 구간 주기(초) — 583 한 바퀴 20건이라 초당 10건(예산 40 의 25%)
SLOW_SEC = 20              # 그 뒤 주기(초)
RATIO = 2.0                # 「터짐」 — 전날 같은 분 누적의 이 배 이상
MIN_PREV_SAME = 1000       # 전날 같은 분 누적 문턱(주) — 짐작값
TOP = 100                  # 판에 싣는 줄 상한
READ_TTL = 2               # 읽는 서버가 DB 판을 다시 읽는 간격(초)
MIN_FROM, MIN_TO = "0800", "0849"
PREP_QUIET_UNTIL = (9, 30)  # 앞 날 분 누적 받기를 정규장 첫 30분에는 안 한다
PREP_GAP = 0.05            # 앞 날 받기 종목 사이 쉼(초) — 340종목쯤이면 20초 남짓

_SCHEMA_MIN = """CREATE TABLE IF NOT EXISTS pre_minute (
    day TEXT NOT NULL, code TEXT NOT NULL, hm TEXT NOT NULL, cum INTEGER, PRIMARY KEY (day, code, hm))"""
_SCHEMA_BOARD = """CREATE TABLE IF NOT EXISTS pre_surge_board (
    day TEXT PRIMARY KEY, data TEXT NOT NULL, saved_at TEXT)"""

_st = {"data": None, "at": 0.0, "read": 0.0}
_prev = {"day": None, "base": None, "cum": {}}     # 견줄 앞 거래일 · 그 날 분마다 누적 {code: {hm: cum}}
_status = {"prepared": None, "lastBuild": None, "buildMs": None, "error": None}
_writer = {"on": False}
_lock = threading.Lock()


def _now():
    return datetime.now(KST)


def phase(now=None):
    """before(평일 08:00 전) · burst(08:00~08:05) · live(08:05~08:50) · closed(그 밖)."""
    now = now or _now()
    hm = (now.hour, now.minute)
    if now.weekday() >= 5:
        return "closed"
    if hm < PRE_OPEN:
        return "before"
    if hm < BURST_UNTIL:
        return "burst"
    if hm < PRE_CLOSE:
        return "live"
    return "closed"


def _universe():
    import dart
    return [r["stock_code"] for r in dart.universe_rows(None)
            if (r["stock_code"] or "").isdigit() and len(r["stock_code"]) == 6]


def _base_day(now):
    """다음(또는 지금) 프리장이 견줄 앞 거래일 — 평일 09:00 뒤면 오늘 · 아니면 앞 평일. 휴장은 nxt_pre 표로 거른다."""
    d = now.date()
    if not (now.weekday() < 5 and (now.hour, now.minute) >= (9, 0)):
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def _minutes(proxy, cfg, code, day):
    """그 날 08:00~08:49 NX 1분봉 → 분마다 누적 {hm: cum} — 봉이 없는 분은 앞 분 누적을 잇는다."""
    data = proxy.kis_get(cfg, "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice",
                         {"FID_COND_MRKT_DIV_CODE": "NX", "FID_INPUT_ISCD": code, "FID_INPUT_HOUR_1": "085000",
                          "FID_INPUT_DATE_1": day, "FID_PW_DATA_INCU_YN": "Y", "FID_FAKE_TICK_INCU_YN": ""},
                         "FHKST03010230")
    per = {}
    for r in (data or {}).get("output2") or []:
        t = str(r.get("stck_cntg_hour") or "")[:4]
        if r.get("stck_bsop_date") != day or not (MIN_FROM <= t <= MIN_TO):
            continue
        per[t] = per.get(t, 0) + (proxy._num(r.get("cntg_vol"), int) or 0)
    out, cum = {}, 0
    for m in range(50):
        hm = "08%02d" % m
        cum += per.get(hm, 0)
        out[hm] = cum
    return out


def _load_prev(proxy, day):
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA_MIN)
        rows = conn.execute("SELECT code, hm, cum FROM pre_minute WHERE day = ?", (day,)).fetchall()
    cum = {}
    for r in rows:
        cum.setdefault(r["code"], {})[r["hm"]] = r["cum"]
    return cum


def prepare(proxy, day=None):
    """앞 거래일 분마다 누적을 받아 둔다 — 이미 있으면 읽기만. 받은 종목 수."""
    cfg = proxy.load_secrets()
    day = day or _base_day(_now())
    cum = _load_prev(proxy, day)
    if not cum:
        # 받을 종목 — 그 날 장 전에 거래가 있던 것(nxt_pre 08:51 저장)만. 표가 없으면 대상 전부
        try:
            saved = nxt_pre._saved(proxy, day)
        except Exception:
            saved = {}
        univ = _universe()
        if saved:
            codes = [c for c in univ if (saved.get(c) or {}).get("vol")]
        else:
            codes = univ
        rows, fail = [], 0
        for c in codes:
            try:
                m = _minutes(proxy, cfg, c, day)
            except Exception:
                fail += 1
                continue
            time.sleep(PREP_GAP)
            if m.get(MIN_TO):
                cum[c] = m
                rows.extend((day, c, hm, v) for hm, v in m.items())
        if rows:
            with proxy._db_lock, proxy.db_conn() as conn:
                conn.execute(_SCHEMA_MIN)
                conn.executemany("INSERT OR REPLACE INTO pre_minute (day, code, hm, cum) VALUES (?,?,?,?)", rows)
                conn.execute("DELETE FROM pre_minute WHERE day < ?", ((datetime.strptime(day, "%Y%m%d") - timedelta(days=14)).strftime("%Y%m%d"),))
        _status["prepared"] = {"day": day, "codes": len(cum), "asked": len(codes), "fail": fail,
                               "at": _now().strftime("%H:%M:%S")}
    with _lock:
        _prev.update(day=day, cum=cum)
    return len(cum)


def build(today, prev_cum, hm):
    """오늘 NX {code: {vol, price, prev_close, name}} · 앞 날 {code: {hm: cum}} · 지금 분 → (줄들, 셈).
    지금 분이 08:49 를 넘으면 08:49 로 견준다. 셈과 고르기는 이 한 곳."""
    key = min(max(hm, MIN_FROM), MIN_TO)
    rows, traded, compared = [], 0, 0
    for code, t in today.items():
        vol = t.get("vol") or 0
        if vol <= 0:
            continue
        traded += 1
        p = (prev_cum.get(code) or {}).get(key)
        ratio = round(vol / p, 2) if p and p >= MIN_PREV_SAME else None
        if ratio is None:
            continue
        compared += 1
        if ratio < RATIO:
            continue
        px, pc = t.get("price"), t.get("prev_close")
        rows.append({"code": code, "name": t.get("name") or code, "price": px,
                     "pct": round((px / pc - 1) * 100, 2) if px and pc else None,
                     "vol": vol, "prevSame": p, "ratio": ratio, "amt": (px or 0) * vol or None})
    rows.sort(key=lambda r: -r["ratio"])
    return rows[:TOP], {"traded": traded, "compared": compared, "hits": len(rows), "at": key}


def _make(proxy, cfg):
    now = _now()
    day = now.strftime("%Y%m%d")
    t0 = time.time()
    today = nxt_pre.fetch_nx(proxy, cfg, _universe(), gap=0)
    if not today or not sum((r.get("vol") or 0) for r in today.values()):
        return {"rows": [], "noTrade": True, "day": day, "hm": now.strftime("%H:%M:%S")}
    with _lock:
        prev_day, prev_cum = _prev["day"], _prev["cum"]
    rows, n = build(today, prev_cum, now.strftime("%H%M"))
    _status["buildMs"] = int((time.time() - t0) * 1000)
    return {"rows": rows, "noTrade": False, "day": day, "hm": now.strftime("%H:%M:%S"), "prevDay": prev_day,
            "scanned": len(today), "prevCodes": len(prev_cum), **n}


def _save(proxy, m):
    try:
        with proxy._db_lock, proxy.db_conn() as conn:
            conn.execute(_SCHEMA_BOARD)
            conn.execute("INSERT OR REPLACE INTO pre_surge_board (day, data, saved_at) VALUES (?,?,?)",
                         (m["day"], json.dumps(m, ensure_ascii=False), _now().strftime("%H:%M:%S")))
    except Exception as e:
        print("  [프리장 급증] 저장 못 함 (%s)" % type(e).__name__, flush=True)


def _load_saved(proxy):
    try:
        with proxy.db_conn() as conn:
            r = conn.execute("SELECT data, day, saved_at FROM pre_surge_board ORDER BY day DESC LIMIT 1").fetchone()
        if not r:
            return None, 0.0
        try:
            at = datetime.strptime(r[1] + r[2], "%Y%m%d%H:%M:%S").replace(tzinfo=KST).timestamp()
        except (TypeError, ValueError):
            at = 0.0
        return json.loads(r[0]), at
    except Exception:
        return None, 0.0


def fetch(proxy):
    """(판, 지은 시각, phase). 그날 판은 market_hours.AFTER_CLOSE(20:00)까지만 내고 그 뒤는 빈 판(reset) — 프리장 판과 같게."""
    import market_hours
    now = _now()
    ph = phase(now)
    if _writer["on"]:
        with _lock:
            data, at = _st["data"], _st["at"]
        if data is None:
            data, at = _load_saved(proxy)
    else:
        if _st["data"] is None or time.time() - _st["read"] >= READ_TTL:
            data, at = _load_saved(proxy)
            with _lock:
                _st.update(data=data, at=at, read=time.time())
        with _lock:
            data, at = _st["data"], _st["at"]
    day = now.strftime("%Y%m%d")
    if data and (data.get("day") != day or now.strftime("%H%M") >= market_hours.AFTER_CLOSE) and ph in ("before", "closed"):
        return {"rows": [], "reset": True, "day": data.get("day")}, at, ph
    if data and data.get("day") != day:
        return None, at, ph
    return data, at, ph


def status():
    return dict(_status)


def start(proxy):
    """보내는 서버(8765)가 뜰 때 한 번 — 장 전에 앞 날 분 누적을 받고, 프리장 동안 훑어 판을 남긴다."""
    _writer["on"] = True

    def loop():
        time.sleep(20)
        while True:
            nap = 10
            try:
                now = _now()
                ph = phase(now)
                base = _base_day(now)
                busy = (9, 0) <= (now.hour, now.minute) < PREP_QUIET_UNTIL     # 정규장 첫 30분은 비켜선다
                if _prev["day"] != base and ph in ("before", "closed") and not busy:
                    n = prepare(proxy, base)
                    print("  [프리장 급증] 앞 거래일 %s 분 누적 %d종목 준비" % (base, n), flush=True)
                if ph in ("burst", "live"):
                    if _prev["day"] != base:          # 프리장 중 재시작 — 앞 날 값이 표에 있으면 읽기만(없으면 받는다)
                        prepare(proxy, base)
                    t0 = time.time()
                    m = _make(proxy, proxy.load_secrets())
                    with _lock:
                        _st["data"], _st["at"] = m, time.time()
                    if not m.get("noTrade"):
                        _save(proxy, m)
                    _status["lastBuild"] = m.get("hm")
                    nap = max(0.2, (BURST_SEC if ph == "burst" else SLOW_SEC) - (time.time() - t0))
            except Exception as e:
                _status["error"] = "%s · %s" % (_now().strftime("%H:%M:%S"), type(e).__name__)
                print("  [프리장 급증] 멈춤 (%s)" % type(e).__name__, flush=True)
            time.sleep(nap)

    threading.Thread(target=loop, daemon=True, name="pre-surge").start()
    return True
