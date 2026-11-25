# -*- coding: utf-8 -*-
"""종목별 외국인 · 기관 장중 가집계 쌓기 — 감시 목록(시가총액 3천억 이상) 전부를 입력 시각마다 (2026-11-25).

재권님 지시 넷 중 2번(11-24 09:3x · 「단타 2」 카드) — 외국인 · 기관 장중 가집계를 3천억 이상 전 종목 · 가집계 시각마다 쌓기.
개발2 → 개발1 로 옮김(11-25 14:4x 재권님 「응 그렇게 해」 · 작업우선순위 배분) · 안에 재권님 「각 5분으로」(11-25 14:5x) — 입력 시각 각 5분 뒤.

    받는 것    kis_proxy.fetch_investor_estimate(HHPTJ04160200 · 종목 하나에 KIS 한 번 · 외국인 · 기관 · 합계 수량)
              응답에 그날 지금까지의 회차(bsop_hour_gb)가 다 들어 있다 — 한 바퀴를 놓쳐도 다음 바퀴가 앞 회차를 채운다.
              ⚠️ 수량(주)만 온다 · 금액 없음. 응답에 시각이 없어 회차 번호와 처음 받은 시각을 함께 남긴다
    대상      dart.universe_rows(None) — 감시 목록(시가총액 3천억 이상 · 코스피 먼저) 그대로
    때        SLOTS_USUAL(보통 날 입력 시각 + 5분) — 늦게 여는 날은 dt30.late_min 만큼 뒤로 민다(「장 시각으로 셈하는 코드는 늦게 여는 날 그만큼 옮긴다」)
              입력 시각 — 외국인 09:30 · 11:20 · 13:20 · 14:30 / 기관 10:00 · 11:20 · 13:20 · 14:30(KIS 문서 · ±10분)
              서버가 늦게 떴으면 지난 때는 한 바퀴로 몰아 받는다(회차가 다 들어 있어서)
    차례      낮은 차례(_prio.low) — 화면 · 칩 실시간이 막 불렀으면 비켜선다
    저장      market.db `inv_est`(날 · 종목 · 회차 → 외국인 · 기관 · 합계 · 처음 받은 때 · 마지막 받은 때) — 같은 회차를 다시 받으면 값만 고친다
    주소      GET /api/kis/inv-est?day=YYYYMMDD[&codes=a,b] — 모양은 board() 주석. 「없음」 은 null(0 아님)
    도는 곳    보내는 서버(8765) 하나 — 다른 서버는 쌓인 표를 읽기만
"""

import threading
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
SLOTS_USUAL = ((9, 35), (10, 5), (11, 25), (13, 25), (14, 35))   # 보통 날 시각 — 입력 시각 + 5분(재권님 「각 5분으로」 11-25) · 늦게 여는 날 late_min 만큼 민다
STOP_USUAL = (15, 40)              # 보통 날 시각 — 이 뒤로는 바퀴를 새로 안 돌린다(마감 뒤는 확정치 자리 · investor_confirmed_today)
TICK = 30

_SCHEMA = """CREATE TABLE IF NOT EXISTS inv_est (
    day TEXT NOT NULL, code TEXT NOT NULL, seq INTEGER NOT NULL,
    frgn INTEGER, inst INTEGER, total INTEGER,
    first_at TEXT, last_at TEXT,
    PRIMARY KEY (day, code, seq))"""

_status = {"running": False, "day": None, "slot": -1, "last": None, "error": None}
_run_lock = threading.Lock()


def _now():
    return datetime.now(KST)


def _shift(hm, off):
    m = hm[0] * 60 + hm[1] + off
    return (m // 60, m % 60)


def _late(proxy, now):
    """그날 늦은 분 · 장이 열리나 — (분, 열림). 못 읽으면 (None, None)."""
    try:
        import dt30
        import market_hours
        t = market_hours.today(proxy, now=now)
        if t.get("open") is False:
            return 0, False
        return dt30.late_min(proxy, now=now), True
    except Exception:
        return None, None


def slots(proxy, now=None):
    """그날 바퀴 시각 [(시, 분)] · 늦은 분 · 열림 — 늦은 분을 못 읽으면 보통 날 시각으로 짓고 lateMin 은 None."""
    now = now or _now()
    late, open_ = _late(proxy, now)
    off = late or 0
    return [_shift(s, off) for s in SLOTS_USUAL], _shift(STOP_USUAL, off), late, open_


def _codes():
    import dart
    return [r["stock_code"] for r in dart.universe_rows(None)
            if (r["stock_code"] or "").isdigit() and len(r["stock_code"]) == 6]


def collect(proxy, cfg, day=None):
    """한 바퀴 — 감시 목록 전부를 받아 쌓는다. (쌓은 종목 · 못 받은 종목 · 대상) 수."""
    day = day or _now().strftime("%Y%m%d")
    codes = _codes()
    got, fail = 0, 0
    proxy._prio.low = True             # 여유분으로 — 화면 · 칩 실시간이 막 불렀으면 비켜선다
    try:
        for c in codes:
            try:
                rows = (proxy.fetch_investor_estimate(cfg, c) or {}).get("rows") or []
            except RuntimeError:
                fail += 1
                continue
            at = _now().strftime("%H:%M:%S")
            vals = [(day, c, r["seq"], r.get("foreign"), r.get("inst"), r.get("sum"), at, at)
                    for r in rows if r.get("seq") is not None]
            if vals:
                with proxy._db_lock, proxy.db_conn() as conn:
                    conn.execute(_SCHEMA)
                    conn.executemany(
                        "INSERT INTO inv_est (day, code, seq, frgn, inst, total, first_at, last_at) VALUES (?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(day, code, seq) DO UPDATE SET frgn=excluded.frgn, inst=excluded.inst, "
                        "total=excluded.total, last_at=excluded.last_at", vals)
            got += 1
    finally:
        proxy._prio.low = False
    return got, fail, len(codes)


def board(proxy, day=None, codes=None):
    """그날 쌓인 가집계 — {day, rows: [{code, name, seqs: [{seq, foreign, inst, sum, firstAt, lastAt}]}]}.

    seqs 는 회차 오름차순(큰 것이 최신) · 수량(주) · 「없음」 은 null. 표가 없거나 그날 것이 없으면 rows 는 [].
    name 은 감시 목록 이름(목록 밖이면 null)."""
    day = day or _now().strftime("%Y%m%d")
    sql = "SELECT code, seq, frgn, inst, total, first_at, last_at FROM inv_est WHERE day = ?"
    args = [day]
    if codes:
        sql += " AND code IN (%s)" % ",".join("?" * len(codes))
        args += list(codes)
    sql += " ORDER BY code, seq"
    try:
        with proxy.db_conn() as conn:
            got = conn.execute(sql, args).fetchall()
    except Exception:
        got = []
    names = {}
    try:
        import dart
        names = {r["stock_code"]: r["name"] for r in dart.universe_rows(None)}
    except Exception:
        pass
    out, cur = [], None
    for code, seq, f, i, s, fa, la in got:
        if cur is None or cur["code"] != code:
            cur = {"code": code, "name": names.get(code), "seqs": []}
            out.append(cur)
        cur["seqs"].append({"seq": seq, "foreign": f, "inst": i, "sum": s, "firstAt": fa, "lastAt": la})
    return {"day": day, "rows": out}


def days(proxy, limit=30):
    try:
        with proxy.db_conn() as conn:
            return [d for (d,) in conn.execute("SELECT DISTINCT day FROM inv_est ORDER BY day DESC LIMIT ?", (limit,))]
    except Exception:
        return []


def status(proxy=None):
    s = dict(_status)
    if proxy is not None:
        sl, stop, late, open_ = slots(proxy)
        s.update(slots=["%02d:%02d" % x for x in sl], stopAt="%02d:%02d" % stop, lateMin=late, open=open_)
    return s


def tick(proxy, now=None):
    """지난 바퀴 시각이 있고 아직 안 돌았으면 한 바퀴 — 지난 것이 여럿이면 한 바퀴로 몰아 받는다."""
    now = now or _now()
    day = now.strftime("%Y%m%d")
    if now.weekday() >= 5:
        return False
    sl, stop, late, open_ = slots(proxy, now)
    if open_ is False:
        return False
    hm = (now.hour, now.minute)
    if hm >= stop:
        return False
    if _status["day"] != day:
        _status.update(day=day, slot=-1)
    passed = [i for i, s in enumerate(sl) if hm >= s]
    if not passed or passed[-1] <= _status["slot"]:
        return False
    if not _run_lock.acquire(blocking=False):
        return False
    try:
        idx = passed[-1]
        t0 = time.time()
        got, fail, n = collect(proxy, proxy.load_secrets(), day)
        _status.update(slot=idx, last={"at": _now().strftime("%H:%M:%S"), "slot": "%02d:%02d" % sl[idx],
                                       "got": got, "fail": fail, "n": n, "sec": round(time.time() - t0, 1),
                                       "lateMin": late})
        print("  [장중 가집계] %s %02d:%02d 바퀴 — %d종목 쌓음 · 못 받음 %d · 대상 %d · %.0f초%s"
              % (day, sl[idx][0], sl[idx][1], got, fail, n, time.time() - t0,
                 "" if late is not None else " · 늦은 분 못 읽음(보통 날 시각)"), flush=True)
        return True
    finally:
        _run_lock.release()


def start(proxy):
    """보내는 서버가 뜰 때 한 번."""
    def loop():
        time.sleep(60)
        while True:
            try:
                tick(proxy)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [장중 가집계] 멈춤 (%s)" % type(e).__name__, flush=True)
            time.sleep(TICK)

    _status["running"] = True
    threading.Thread(target=loop, daemon=True, name="inv-est").start()
    return True
