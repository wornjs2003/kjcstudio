# -*- coding: utf-8 -*-
"""당일 수급 — 장중에 시장 투자자 · 프로그램 매매를 1분마다 쌓아 5분 구간마다 매수 · 매도 · 순매수로 낸다 (2026-10-27).

재권님 — 「투자자 정보에서 당일에 개인 기관 외국인 수급현황을 좀더 디테일하게 … 언제 팔고 사고 하는지 랑 프로그램 매매 도」(10-26)
→ 시안 (나) · 「프로그램 순매수도 시간대별로 좀더 세분화」 · 종목은 「둘 다」(관심종목 + 고른 종목) · 「캔들처럼 시간별로 얼마나
들어오는지 · 금액이랑 양도」 · 「ㄴ(구간 막대) · 매수랑 매도 둘다」 · 「이 모습처럼 · 모달 창 밖으로 길어지지 않게」(10-27 · 개발2 창).
화면은 투자자 지표 모달의 「당일」 탭(js/components/investor-modal.js).

    왜 쌓나     KIS 는 지난 시각을 물어도 **가장 최근 것만** 준다(2026-10-27 11:56 실측 — 시각 칸을 넣어도 같은 30줄).
                시장 투자자는 그날 누계 한 줄 · 프로그램은 최근 30줄뿐이라, 하루 흐름은 서버가 받아 쌓아야 나온다
    무엇을      시장 투자자  FHPTJ04030000(999 · S001 = 코스피) · 외국인 · 기관 · 개인 매수 · 매도 · 순 금액(백만원) · 수량(천주)과 기관 안
                시장 프로그램 FHPPG04600101(K = 코스피) · 1분 줄 30개 · 차익 + 비차익 매수 · 매도 · 순(백만원) · 수량은 KIS 가 안 준다
                종목 프로그램 FHPPG04650101 · 체결 줄 30개(삼성전자는 2분쯤) · 매수 · 매도 · 순 금액(원) · 수량(주)
    언제        평일 09:00~15:30 · 1분마다 시장 투자자 · 종목 프로그램 / 25분마다 시장 프로그램(한 번에 30분치라 겹쳐 받는다)
    어느 종목    관심종목(dart.watchlist()) 전부 + 화면이 고른 종목(이 주소를 부른 뒤 WANT_SEC 동안) — 재권님 「둘 다」
    하루 몇 번   시장 약 390 + 시장 프로그램 약 16 + 종목 390 × 관심종목 수(7개면 약 2,730) + 고른 종목 1분에 1번
    저장        market.db `flow_snap`(날 · 갈래 · 코드 · 분 · 그 분의 누적값 JSON). 누적값을 두고 구간 값은 낼 때 뺄셈한다
    주소        GET /api/kis/flow-today?code=&step=5 — 모양은 today() 주석. 「없음」 은 null(0 아님)
    코스닥       시장 번호를 아직 못 맞췄다(10-26 1001 은 0 만 왔다) — 코스피만 낸다. 맞추면 MKT 에 더한다

8765 만 받는다(`kis_proxy` 가 `is_sender` 로 부른다) · 다른 서버는 이 주소를 8765 로 넘기고(고른 종목 표시가 8765 에 닿게),
넘길 곳이 없으면 자기 DB(세션 서버는 메인 DB 를 읽기 전용으로 연다)로 답한다. 알림은 없다(화면만).
"""

import json
import threading
import time
from datetime import datetime, timedelta, timezone

from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))

OPEN, CLOSE = (9, 0), (15, 31)      # 15:30 마감 값까지 한 번 더 받는다
TICK = 15                           # 바퀴 — 분이 바뀌었나만 본다
PGM_EVERY = 25                      # 시장 프로그램은 한 번에 30분치 — 25분마다면 안 빈다
WANT_SEC = 30 * 60                  # 화면이 고른 종목을 몇 초 동안 쌓나(모달을 닫은 뒤에도 그만큼)
STEPS = (1, 5, 10, 30)
CACHE_TTL = 60                      # 화면이 다시 묻는 주기 — 1분마다 쌓으니 그보다 자주 물을 까닭이 없다
Q = "/uapi/domestic-stock/v1/quotations/"
WHO = ("frgn", "orgn", "prsn")      # 외국인 · 기관 · 개인
INST = ("scrt", "ivtr", "pe_fund", "bank", "insu", "mrbn", "fund", "etc_orgt", "etc_corp")

_SCHEMA = """CREATE TABLE IF NOT EXISTS flow_snap (
    day TEXT NOT NULL, kind TEXT NOT NULL, code TEXT NOT NULL, hm TEXT NOT NULL, data TEXT, saved_at TEXT,
    PRIMARY KEY (day, kind, code, hm))"""

_want = {}                          # 고른 종목 → 마지막으로 부른 때
_status = {"running": False, "lastMinute": None, "lastPgm": None, "calls": 0, "error": None, "errorAt": None}


def _now():
    return datetime.now(KST)


def _i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def want(code):
    """화면이 이 종목을 보고 있다 — WANT_SEC 동안 1분마다 쌓는다."""
    if code and code.isdigit() and len(code) == 6:
        _want[code] = time.time()


def _codes(proxy):
    import dart
    now = time.time()
    for c, at in list(_want.items()):
        if now - at > WANT_SEC:
            _want.pop(c, None)
    try:
        watch = [c for c in dart.watchlist() if c.isdigit() and len(c) == 6]
    except Exception:
        watch = []
    return list(dict.fromkeys(watch + list(_want)))


def _save(proxy, rows):
    if not rows:
        return
    at = _now().strftime("%H:%M:%S")
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        conn.executemany("INSERT OR REPLACE INTO flow_snap (day, kind, code, hm, data, saved_at) VALUES (?,?,?,?,?,?)",
                         [(d, k, c, hm, json.dumps(v, ensure_ascii=False), at) for d, k, c, hm, v in rows])


def _get(proxy, cfg, path, params, tr):
    _status["calls"] += 1
    return proxy.kis_get(cfg, Q + path, params, tr) or {}


def snap_market(proxy, cfg, day, hm):
    o = (_get(proxy, cfg, "inquire-investor-time-by-market", {"FID_INPUT_ISCD": "999", "FID_INPUT_ISCD_2": "S001"},
              "FHPTJ04030000").get("output") or [None])[0]
    if not o:
        return 0
    v = {}
    for w in WHO:
        v[w] = {"buy": _i(o.get(w + "_shnu_tr_pbmn")), "sell": _i(o.get(w + "_seln_tr_pbmn")), "net": _i(o.get(w + "_ntby_tr_pbmn")),
                "buyQty": _i(o.get(w + "_shnu_vol")), "sellQty": _i(o.get(w + "_seln_vol")), "netQty": _i(o.get(w + "_ntby_qty"))}
    v["inst"] = {k: _i(o.get(k + "_ntby_tr_pbmn")) for k in INST}
    _save(proxy, [(day, "mkt", "KOSPI", hm, v)])
    return 1


def snap_program_market(proxy, cfg, day):
    rows = _get(proxy, cfg, "comp-program-trade-today",
                {"FID_COND_MRKT_DIV_CODE": "J", "FID_MRKT_CLS_CODE": "K", "FID_SCTN_CLS_CODE": "", "FID_INPUT_ISCD": "",
                 "FID_COND_MRKT_DIV_CODE1": "", "FID_INPUT_HOUR_1": ""}, "FHPPG04600101").get("output") or []
    out = []
    for r in rows:
        hm = (r.get("bsop_hour") or "")[:4]
        if len(hm) != 4:
            continue
        a = [_i(r.get(x)) for x in ("arbt_smtn_shnu_tr_pbmn", "nabt_smtn_shnu_tr_pbmn", "arbt_smtn_seln_tr_pbmn", "nabt_smtn_seln_tr_pbmn")]
        out.append((day, "pgm", "KOSPI", hm, {
            "buy": None if None in a[:2] else a[0] + a[1], "sell": None if None in a[2:] else a[2] + a[3],
            "net": _i(r.get("whol_smtn_ntby_tr_pbmn")),
            "arbNet": _i(r.get("arbt_smtn_ntby_tr_pbmn")), "nonArbNet": _i(r.get("nabt_smtn_ntby_tr_pbmn"))}))
    _save(proxy, out)
    return len(out)


def snap_program_stock(proxy, cfg, day, code):
    rows = _get(proxy, cfg, "program-trade-by-stock", {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
                "FHPPG04650101").get("output") or []
    last = {}
    for r in rows:                  # 체결 줄 → 분마다 그 분의 마지막(가장 늦은) 누적값
        t = r.get("bsop_hour") or ""
        if len(t) >= 4 and (t[:4] not in last or t > last[t[:4]][0]):
            last[t[:4]] = (t, r)
    out = [(day, "pgs", code, hm, {
        "buy": _i(r.get("whol_smtn_shnu_tr_pbmn")), "sell": _i(r.get("whol_smtn_seln_tr_pbmn")), "net": _i(r.get("whol_smtn_ntby_tr_pbmn")),
        "buyQty": _i(r.get("whol_smtn_shnu_vol")), "sellQty": _i(r.get("whol_smtn_seln_vol")), "netQty": _i(r.get("whol_smtn_ntby_qty")),
        "price": _i(r.get("stck_prpr"))}) for hm, (t, r) in last.items()]
    _save(proxy, out)
    return len(out)


def _in_session(now):
    return now.weekday() < 5 and OPEN <= (now.hour, now.minute) < CLOSE


def _err(e):
    _status["error"], _status["errorAt"] = safe_message(e, 160), _now().strftime("%H:%M:%S")


def start(proxy):
    """보내는 서버가 뜰 때 한 번 — 장중 1분 바퀴."""
    def loop():
        time.sleep(20)
        while True:
            try:
                now = _now()
                hm = now.strftime("%H%M")
                if _in_session(now) and _status["lastMinute"] != now.strftime("%Y%m%d") + hm:
                    _status["lastMinute"] = now.strftime("%Y%m%d") + hm
                    day = now.strftime("%Y%m%d")
                    cfg = proxy.load_secrets()
                    try:
                        snap_market(proxy, cfg, day, hm)
                    except Exception as e:
                        _err(e)
                    for c in _codes(proxy):
                        try:
                            snap_program_stock(proxy, cfg, day, c)
                        except Exception as e:
                            _err(e)
                    mins = now.hour * 60 + now.minute
                    if _status["lastPgm"] is None or _status["lastPgm"][0] != day or mins - _status["lastPgm"][1] >= PGM_EVERY or hm == "1530":
                        try:
                            snap_program_market(proxy, cfg, day)
                            _status["lastPgm"] = (day, mins)
                        except Exception as e:
                            _err(e)
            except Exception as e:
                _err(e)
                print("  [당일 수급] 예기치 못한 오류: %s" % type(e).__name__)
            time.sleep(TICK)

    _status["running"] = True
    threading.Thread(target=loop, daemon=True, name="intraday-flow").start()
    return True


def status():
    return dict(_status, want=sorted(_want), pgmEvery=PGM_EVERY, wantSec=WANT_SEC)


def _load(proxy, day, kind, code):
    try:
        with proxy.db_conn() as conn:
            rows = conn.execute("SELECT hm, data FROM flow_snap WHERE day=? AND kind=? AND code=? ORDER BY hm",
                                (day, kind, code)).fetchall()
    except Exception as e:          # 표가 아직 없다(이 DB 에 아무도 안 쌓았다) — 빈 것으로
        if "no such table" in str(e):
            return []
        raise
    return [(hm, json.loads(d)) for hm, d in rows]


def _sub(a, b):
    return None if a is None or b is None else a - b


def _buckets(snaps, step, pick):
    """누적 스냅샷 → 구간 값. 구간 값 = 그 구간의 마지막 스냅샷 − 앞 구간의 마지막 스냅샷.
    09:00 에 시작하는 첫 구간만 앞 값을 0 으로 둔다(누계가 개장에서 시작). 그 밖에 앞 값이 없는 구간은 뺀다(모른다)."""
    last = {}
    for hm, v in snaps:
        m = int(hm[:2]) * 60 + int(hm[2:])
        b = (m - 1) // step * step if m > 9 * 60 else 9 * 60      # 09:05 에 받은 값은 09:00~09:05 구간의 끝
        last[b] = v
    out, prev = [], None
    for b in sorted(last):
        cur = pick(last[b])
        if prev is None and b == 9 * 60:
            prev = {k: 0 for k in cur}
        if prev is not None:
            out.append(dict({k: _sub(cur.get(k), prev.get(k)) for k in cur}, t="%02d%02d" % divmod(b, 60)))
        prev = cur
    return out


def today(proxy, code=None, step=5):
    """GET /api/kis/flow-today 의 data —
        market   {rows: [{t, frgn: {buy, sell, net, buyQty, sellQty, netQty}, orgn, prsn}], last: 마지막 누계(같은 모양 + inst), lastAt}
        program  {rows: [{t, buy, sell, net}], lastAt}                          금액 백만원 · 수량 없음
        stock    {code, rows: [{t, buy, sell, net, buyQty, sellQty, netQty}], lastAt, watching}   금액 원 · 수량 주
      t = 구간 시작 「HHMM」 · 값은 그 구간 동안 늘어난 양 · 모르는 칸은 null."""
    day = _now().strftime("%Y%m%d")
    mk = _load(proxy, day, "mkt", "KOSPI")
    pg = _load(proxy, day, "pgm", "KOSPI")
    out = {
        "market": {"rows": _buckets(mk, step, lambda v: {f"{w}.{k}": (v.get(w) or {}).get(k) for w in WHO
                                                         for k in ("buy", "sell", "net", "buyQty", "sellQty", "netQty")}),
                   "last": mk[-1][1] if mk else None, "lastAt": mk[-1][0] if mk else None},
        "program": {"rows": _buckets(pg, step, lambda v: {k: v.get(k) for k in ("buy", "sell", "net")}),
                    "lastAt": pg[-1][0] if pg else None},
    }
    for r in out["market"]["rows"]:     # 「frgn.buy」 꼴을 {frgn: {buy}} 로 편다
        for w in WHO:
            r[w] = {k: r.pop(f"{w}.{k}") for k in ("buy", "sell", "net", "buyQty", "sellQty", "netQty")}
    if code:
        st = _load(proxy, day, "pgs", code)
        out["stock"] = {"code": code, "rows": _buckets(st, step, lambda v: {k: v.get(k) for k in ("buy", "sell", "net", "buyQty", "sellQty", "netQty")}),
                        "lastAt": st[-1][0] if st else None, "watching": code in _want}
    return out
