"""자동 관심종목의 다음 날 프리장 5분봉 — 전날 「전일 거래량 급등」 목록(auto_watch_pick)에 걸린 종목의 그다음 거래일 넥스트레이드 장 전(08:00~08:50) 값을 쌓는다 (2026-11-20).

재권님 — 「어제오른 종목인데 종가대비 프리장 5분 가격…」 → 「여기에 올라오는 종목은 항상 그걸 해달라고 해줘 쌓아놔야해」(11-20 · 작업우선순위 경유).

    누구      그날 앞 거래일의 auto_watch_pick 전부(15:41 판에 걸린 종목 · 신고가 부근만 붙은 것도 든다 · rank 그대로) — 11-19 판 161종목
    무엇      넥스트레이드(NX) 1분봉 08:00~08:49 를 5분씩 묶어 시가 · 고가 · 저가 · 종가 · 거래량 — 종가 대비 등락은 부를 때 셈
    기준      전날 종가 둘 — prevClose 그 목록에 적힌 정규장(KRX) 종가(auto_watch_pick.close) · nxPrev 넥스트 멀티 시세의 전일 종가(넥스트 애프터까지 · 홀딩스 시세 등락과 같은 기준)
              둘이 다를 수 있다(11-20 제주항공 8,420 ↔ 8,210) — pct 는 정규장 종가 대비 · pctNx 는 넥스트 전일 종가 대비
    언제      평일 RUN_AT 뒤 그날 한 번 · 못 받으면 RETRY_SEC 뒤 다시 · RUN_UNTIL 까지(KIS 1분봉 NX 는 오늘 것만 준다 — 지난 날 되채움은 못 한다)
    부름      종목마다 1분봉 두 번(30줄씩 · 08:49 · 08:19 끝) + 넥스트 멀티 시세 30종목에 한 번(못 받은 종목 가르기) — 161종목이면 330번쯤 · 하루 한 번
    상태      state — ok 체결 있음 · none 넥스트 시세는 받았는데 장 전 체결 없음 · nonx 넥스트 시세를 못 받음(넥스트 비상장 · 응답 없음) · fail 1분봉을 못 받음
    휴장      목록 종목이 하나도 ok 가 아니면 쓰지 않는다(휴장 · 넥스트 쉬는 날)
    주소      GET /api/auto-watch/pre?days=N — 쌓인 날 최근 N 날 · KIS 를 안 부른다

8765 만 받는다(`kis_proxy` 가 `is_sender` 로 부른다) · 읽기는 어느 서버든 자기 DB 로. 알림은 없다.
"""

import json
import threading
import time
from datetime import datetime, timedelta, timezone

import nxt_pre
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))
RUN_AT = (8, 51)                # 장 전 시장(08:00~08:50)이 닫힌 뒤
RUN_UNTIL = (20, 0)             # 넥스트레이드가 닫히는 때 — 그 뒤엔 1분봉 응답이 어떻게 오는지 안 잼
RETRY_SEC = 300
TICK = 30
GAP_SEC = 0.15
BAR_MIN = 5                     # 묶는 봉 길이(분)
HOURS = ("084900", "081900")    # 1분봉 끝 시각 — 30줄씩 받아 08:00~08:49 를 덮는다
PRE_FROM, PRE_TO = "0800", "0849"

_SCHEMA = """CREATE TABLE IF NOT EXISTS auto_watch_pre (
    day TEXT NOT NULL, code TEXT NOT NULL, pick_day TEXT, rank INTEGER, name TEXT, prev_close INTEGER, nx_prev INTEGER,
    state TEXT, vol INTEGER, last INTEGER, bars TEXT, saved_at TEXT, PRIMARY KEY (day, code))"""

_status = {"runDay": None, "retryAt": 0, "last": None, "error": None}


def _now():
    return datetime.now(KST)


def _init(proxy):
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)


def _picks(proxy, day):
    """그날(day) 앞 거래일의 자동 목록 → (그 날, [(code, name, close, rank)]) · 없으면 (None, [])."""
    with proxy.db_conn() as conn:
        pd = conn.execute("SELECT MAX(day) FROM auto_watch_pick WHERE day < ?", (day,)).fetchone()[0]
        if not pd:
            return None, []
        rows = conn.execute("SELECT code, name, close, rank FROM auto_watch_pick WHERE day = ? ORDER BY rank", (pd,)).fetchall()
    return pd, [tuple(r) for r in rows]


def _minutes(proxy, cfg, code, day):
    """그날 넥스트레이드 1분봉 08:00~08:49 → {HHMM: (o, h, l, c, v)} · 한 번이라도 못 받으면 None."""
    got = {}
    for hour in HOURS:
        data = proxy.kis_get(cfg, "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
                             {"FID_ETC_CLS_CODE": "", "FID_COND_MRKT_DIV_CODE": "NX", "FID_INPUT_ISCD": code,
                              "FID_INPUT_HOUR_1": hour, "FID_PW_DATA_INCU_YN": "Y"},
                             "FHKST03010200")
        if data is None or str(data.get("rt_cd", "0")) != "0":
            return None                                # 오류 응답을 「체결 없음」 으로 읽지 않는다
        for r in data.get("output2") or []:
            t = str(r.get("stck_cntg_hour") or "")[:4]
            if r.get("stck_bsop_date") != day or not (PRE_FROM <= t <= PRE_TO):
                continue
            num = lambda k: proxy._num(r.get(k), int)
            v = num("cntg_vol") or 0
            if v:
                got[t] = (num("stck_oprc"), num("stck_hgpr"), num("stck_lwpr"), num("stck_prpr"), v)
        time.sleep(GAP_SEC)
    return got


def _bars(mins):
    """1분봉 → 5분봉 [[HHMM 시작, o, h, l, c, v]] · 체결 없는 칸은 안 넣는다(0 으로 채우지 않는다)."""
    out = {}
    for t in sorted(mins):
        o, h, l, c, v = mins[t]
        m = int(t[:2]) * 60 + int(t[2:])
        k = "%02d%02d" % divmod(m - m % BAR_MIN, 60)
        b = out.get(k)
        if b is None:
            out[k] = [k, o, h, l, c, v]
        else:
            hs, ls = [x for x in (b[2], h) if x is not None], [x for x in (b[3], l) if x is not None]
            b[2], b[3] = (max(hs) if hs else None), (min(ls) if ls else None)
            b[4], b[5] = c, b[5] + v
    return [out[k] for k in sorted(out)]


def run_once(proxy, day):
    """그날 한 번 — 쌓은 종목 수 · 0 쌓을 것 없음(목록 없음 · 다 쌓음 · 휴장) · None 지금 못 함 · 못 받은(fail) 종목이 남음(RETRY_SEC 뒤 다시).
    이미 쌓은 날이면 fail 종목만 다시 받는다(창구 덧 11-20 — 한 종목이라도 쌓이면 그날 끝이라 실패 종목이 영영 비던 것)."""
    _init(proxy)
    with proxy.db_conn() as conn:
        have = {c: st for c, st in conn.execute("SELECT code, state FROM auto_watch_pre WHERE day = ?", (day,))}
    pick_day, picks = _picks(proxy, day)
    if have:
        picks = [p for p in picks if have.get(p[0]) == "fail"]
        if not picks:
            return 0
    if not picks:
        _status["last"] = {"day": day, "note": "앞 거래일 자동 목록 없음"}
        return 0
    cfg = proxy.load_secrets()
    nx = nxt_pre.fetch_nx(proxy, cfg, [p[0] for p in picks])     # 넥스트 시세를 받았나 가르기(못 받은 종목 = nonx)
    nxp = lambda c: (nx.get(c) or {}).get("prev_close") or None    # 넥스트 거래가 없던 종목은 0 이 온다 — 0 으로 두지 않는다
    rows, fail = [], 0
    for code, name, close, rank in picks:
        try:
            mins = _minutes(proxy, cfg, code, day)
        except Exception:
            mins = None
        if mins is None:
            fail += 1
            rows.append((code, rank, name, close, nxp(code), "fail", None, None, []))
            continue
        bars = _bars(mins)
        if bars:
            rows.append((code, rank, name, close, nxp(code), "ok", sum(b[5] for b in bars), bars[-1][4], bars))
        else:
            rows.append((code, rank, name, close, nxp(code), "none" if code in nx else "nonx", 0 if code in nx else None, None, []))
    ok = sum(1 for r in rows if r[5] == "ok")
    if not ok and not have:
        _status["last"] = {"day": day, "pickDay": pick_day, "codes": len(rows), "fail": fail,
                           "note": "체결 있는 종목 0 — 휴장이거나 못 받음 · 안 씀"}
        return None if fail == len(rows) else 0
    at = _now().isoformat(timespec="seconds")
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.executemany("INSERT OR REPLACE INTO auto_watch_pre VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                         [(day, c, pick_day, rk, n, cl, np, st, v, last, json.dumps(b), at) for c, rk, n, cl, np, st, v, last, b in rows])
    _status["last"] = {"day": day, "pickDay": pick_day, "codes": len(rows), "ok": ok, "fail": fail, "at": at, "retry": bool(have)}
    return None if fail else len(rows)


def _pct(px, base):
    return None if px is None or not base else round((px - base) / base * 100, 2)


def board(proxy, days=5):
    """쌓인 날 최근 days 날 → [{day, pickDay, rows:[{code, name, prevClose, state, vol, last, lastPct, bars:[{t, o, h, l, c, v, pct}]}]}]."""
    _init(proxy)
    with proxy.db_conn() as conn:
        ds = [d for (d,) in conn.execute("SELECT DISTINCT day FROM auto_watch_pre ORDER BY day DESC LIMIT ?", (days,))]
        out = []
        for d in ds:
            rows = conn.execute("SELECT code, pick_day, rank, name, prev_close, nx_prev, state, vol, last, bars, saved_at FROM auto_watch_pre "
                                "WHERE day = ? ORDER BY rank, code", (d,)).fetchall()
            out.append({"day": d, "pickDay": rows[0][1] if rows else None, "savedAt": rows[0][10] if rows else None,
                        "rows": [{"code": c, "rank": rk, "name": n, "prevClose": pc, "nxPrev": np, "state": st, "vol": v, "last": last,
                                  "lastPct": _pct(last, pc), "lastPctNx": _pct(last, np),
                                  "bars": [{"t": "%s:%s" % (b[0][:2], b[0][2:]), "o": b[1], "h": b[2], "l": b[3], "c": b[4], "v": b[5],
                                            "pct": _pct(b[4], pc), "pctNx": _pct(b[4], np)} for b in json.loads(bars or "[]")]}
                                 for c, _, rk, n, pc, np, st, v, last, bars, _ in rows]})
    return out


def status():
    return dict(_status, runAt="%02d:%02d" % RUN_AT, runUntil="%02d:%02d" % RUN_UNTIL)


def start(proxy):
    """보내는 서버가 뜰 때 한 번 — 평일 RUN_AT~RUN_UNTIL 사이 그날 한 번(못 받으면 RETRY_SEC 뒤 다시)."""
    def loop():
        time.sleep(45)
        while True:
            try:
                now = _now()
                hm = (now.hour, now.minute)
                day = now.strftime("%Y%m%d")
                if now.weekday() < 5 and RUN_AT <= hm < RUN_UNTIL and _status["runDay"] != day \
                        and time.time() >= _status["retryAt"]:
                    _status["runDay"] = day
                    try:
                        n = run_once(proxy, day)
                        if n is None:
                            _status.update(runDay=None, retryAt=time.time() + RETRY_SEC)
                        elif n:
                            print("  [자동 프리장] %s %d종목 쌓음(체결 있음 %s)" % (day, n, (_status["last"] or {}).get("ok")))
                    except Exception as e:
                        _status.update(runDay=None, retryAt=time.time() + RETRY_SEC, error=safe_message(e, 160))
                        print("  [자동 프리장] 실패: %s" % type(e).__name__)
            except Exception:
                pass
            time.sleep(TICK)
    threading.Thread(target=loop, daemon=True, name="auto-pre").start()
    return True
