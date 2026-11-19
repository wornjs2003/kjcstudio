# -*- coding: utf-8 -*-
"""지난 날 VI 기록 — KIS VI 현황(inquire-vi-status)으로 날마다 VI 를 쌓고, 날짜를 넣으면 그날 목록을 낸다 (2026-11-19).

재권님 — 「vi급등 지난것들 정보 받을수 있나? 발등한것과 발등조건 발등시간」(11-19 14:0x · 시황분석1 창) → 안 「지난 날 VI 기록을 날마다 쌓아
단타 판에서 날짜를 고르면 그날 VI 목록」 에 「응 해줘」 → 서버 안에 「응」(11-19 14:09) → 연속 조회가 안 돼 다시 여쭌 (가)·(나) 에 「나」(11-19 14:49 · 개발2 창).

    KIS 의 한계  전 시장으로 물으면 그날 가장 늦은 것부터 30건뿐이다. 연속 조회(tr_cont)는 이 API 에서 안 듣는다 — 다음 장을 달라 해도 같은 30건
                (11-19 14:30 8765 로 잼 · 그 전 14:0x 잼: 정렬 · 상승/하락 · 시장 갈래를 바꿔도 30건). 종목을 넣어 물으면 그 종목의 그날 VI 가 다 온다.
    그래서 셋으로 모은다(meta.src 에 무엇으로 모았는지 적음)
        장중    intraday_alerts 가 정규장 동안 10초마다 받는 VI 목록(오르는 VI · 전 시장)을 그대로 쌓는다 — 한 바퀴 사이 30건 넘게 몰리면 그만큼 빠짐
        종목    순위 목록 종목 + 그날 단타 판 종목 + 끝 30건에 나온 종목을 하나씩 물어 그 종목의 그날 VI 전부(오름 · 내림)
        끝30    전 시장 마지막 30건(넥장 저녁 것)
    언제      그날 것: 장중은 바퀴마다 · 넥장 끝 뒤 STORE_AT 에 끝30 + 종목. 지난 날: 밤(STORE_AT ~ 다음 날 NIGHT_END)과 주말에 하루씩 끝30 + 종목
              (BACKFILL_DAYS 일 앞까지 · 주말 · 휴장 뺌 · 이미 종목으로 채운 날 뺌) — 하루 KIS 600번 남짓
    칸        발동 시각(cntg_vi_hour) · 풀린 시각(vi_cncl_hour) · 종류(vi_kind_code 1 정적 · 2 동적 · 3 둘 다) · 발동가(vi_prc) ·
              정적 기준가 · 괴리율(vi_stnd_prc · vi_dprt) · 동적 기준가 · 괴리율(vi_dmc_stnd_prc · vi_dmc_dprt) · 그날 횟수(vi_count) ·
              오름/내림(발동가가 기준가보다 높으면 오름) · 정규장 안(그날 market_hours 정규장 시각 — 쌓을 때 셈)
    상태      meta.state — 「종목 채움」(순위 목록 등 물은 종목은 그날 전부 · 그 밖 종목은 장중 · 끝30 에 걸린 것만) · 「장중 쌓는 중」 ·
              「못 받음」(받다가 실패) · 「안 받음」(아직 안 쌓은 날) — 0건과 가른다
    주소      GET /api/kis/vi-day?day=YYYYMMDD — 그날 목록 · 없으면 쌓인 날 목록 · 넘기는 서버(8764 · 세션)는 상류(8765)를 넘긴다(쌓는 것은 8765 하나)
"""
import threading
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
STORE_AT = (20, 10)          # 그날 것을 끝맺는 때 — 넥스트레이드 애프터마켓(20:00) 끝 뒤 · 지난 날 되채움도 이때부터
NIGHT_END = (7, 0)           # 되채움을 멈추는 때(다음 날 아침) — 장중 KIS 예산에 안 끼게
BACKFILL_DAYS = 120          # 되채움 앞 날 수(달력) — 재권님 「몇 달」 · 2025-10-15 까지 받히는 것은 잼(11-19)
CODE_GAP_SEC = 0.15          # 종목 하나 묻고 다음까지 — 초당 한도는 kis_get 이 지키고 이것은 다른 일에 비켜서는 몫
TICK = 60                    # 바퀴(초)
VI_PATH = "/uapi/domestic-stock/v1/quotations/inquire-vi-status"
VI_TR = "FHPST01390000"
KIND = {"1": "정적", "2": "동적", "3": "정적·동적"}
_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS vi_day (day TEXT, code TEXT, at TEXT, name TEXT, kind TEXT, cncl TEXT, price REAL,
       stnd REAL, dprt REAL, dmc_stnd REAL, dmc_dprt REAL, cnt INTEGER, up INTEGER, regular INTEGER, PRIMARY KEY (day, code, at))""",
    """CREATE TABLE IF NOT EXISTS vi_day_meta (day TEXT PRIMARY KEY, got_at TEXT, n INTEGER, full INTEGER, pages INTEGER, error TEXT)""",
)
_status = {"error": None, "stored": None, "backfill": None, "at": None, "live": 0}
_reg = {}                    # {날: (정규장 여는 HHMMSS, 닫는 HHMMSS, 열림?)} — 장중 바퀴마다 장 시각 표를 다시 읽지 않게


def _now():
    return datetime.now(KST)


def _num(v):
    try:
        return float(v) if str(v).strip() not in ("", "None") else None
    except (TypeError, ValueError):
        return None


def _init(conn):
    for q in _SCHEMA:
        conn.execute(q)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(vi_day_meta)")}
    if "src" not in cols:
        conn.execute("ALTER TABLE vi_day_meta ADD COLUMN src TEXT")      # 무엇으로 모았나 — 장중 · 종목 · 끝30 (11-19 「나」)
    if "codes" not in cols:
        conn.execute("ALTER TABLE vi_day_meta ADD COLUMN codes INTEGER")  # 종목으로 물은 수


def _reg_of(proxy, day):
    if day not in _reg:
        import market_hours
        t = market_hours.today(proxy, day=day)
        _reg[day] = (t["reg"][0] + "00", t["reg"][1] + "00", t.get("open") is not False)
    return _reg[day]


def _put(conn, day, r, reg):
    at = str(r.get("cntg_vi_hour") or "").zfill(6)
    code = (r.get("mksc_shrn_iscd") or "").strip()
    if not code or (r.get("bsop_date") and r["bsop_date"] != day):
        return 0
    price, stnd, dmc = _num(r.get("vi_prc")), _num(r.get("vi_stnd_prc")), _num(r.get("vi_dmc_stnd_prc"))
    base = stnd or dmc
    cn = str(r.get("vi_cncl_hour") or "").strip()
    kc = str(r.get("vi_kind_code") or "").strip()
    cur = conn.execute("INSERT OR REPLACE INTO vi_day VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
        day, code, at, (r.get("hts_kor_isnm") or "").strip(), KIND.get(kc, kc or None),
        cn.zfill(6) if cn and cn.strip("0") else None, price, stnd, _num(r.get("vi_dprt")), dmc, _num(r.get("vi_dmc_dprt")),
        int(_num(r.get("vi_count")) or 0) or None, None if not (price and base) else int(price > base),
        int(reg[0] <= at < reg[1]) if reg[2] else None))
    return cur.rowcount or 0


def _meta_set(conn, day, src_add=None, codes=None, error=None):
    n = conn.execute("SELECT COUNT(*) FROM vi_day WHERE day = ?", (day,)).fetchone()[0]
    old = conn.execute("SELECT src, codes FROM vi_day_meta WHERE day = ?", (day,)).fetchone()
    src = set(((old[0] if old else "") or "").split(",")) - {""}
    if src_add:
        src.add(src_add)
    conn.execute("INSERT OR REPLACE INTO vi_day_meta (day, got_at, n, full, pages, error, src, codes) VALUES (?,?,?,?,?,?,?,?)",
                 (day, _now().isoformat(timespec="seconds"), n, 0, None, error, ",".join(sorted(src)),
                  codes if codes is not None else (old[1] if old else None)))


def absorb(proxy, day, rows):
    """장중 — intraday_alerts 가 받은 VI 목록을 그대로 쌓는다(바퀴마다 · 쓰는 서버만). 실패해도 그 고리를 멈추지 않게 부르는 쪽이 감싼다."""
    if not rows or not proxy.marketdb.writable():
        return 0
    reg = _reg_of(proxy, day)
    with proxy._db_lock, proxy.db_conn() as conn:
        _init(conn)
        n = sum(_put(conn, day, r, reg) for r in rows)
        _meta_set(conn, day, "장중")
    _status["live"] += n
    return n


def _ask(proxy, cfg, day, code=""):
    params = {"FID_DIV_CLS_CODE": "0", "FID_COND_SCR_DIV_CODE": "20139", "FID_MRKT_CLS_CODE": "0", "FID_INPUT_ISCD": code,
              "FID_RANK_SORT_CLS_CODE": "0", "FID_INPUT_DATE_1": day, "FID_TRGT_CLS_CODE": "", "FID_TRGT_EXLS_CLS_CODE": ""}
    return proxy.kis_get(cfg, VI_PATH, params, VI_TR).get("output") or []


def _codes(proxy, day, extra):
    """종목으로 물을 목록 — 순위 목록(dart.universe_rows) + 그날 단타 판 종목 + extra(끝 30건에 나온 종목)."""
    import dart
    import dt30
    out = [r["stock_code"] for r in dart.universe_rows(None) if (r["stock_code"] or "").isdigit()]
    got = dt30._load(proxy, day)
    if got:
        out += [r["code"] for r in got[0].get("rows") or []]
    out += list(extra)
    seen = set()
    return [c for c in out if c and len(c) == 6 and not (c in seen or seen.add(c))]


def store_day(proxy, cfg, day):
    """그날을 끝30 + 종목으로 채운다 → 그날 쌓인 건수. 장중에 쌓은 것은 두고 더한다. 실패하면 meta.error 에 적고 다시 던진다."""
    reg = _reg_of(proxy, day)
    try:
        last = _ask(proxy, cfg, day)
        with proxy._db_lock, proxy.db_conn() as conn:
            _init(conn)
            for r in last:
                _put(conn, day, r, reg)
            _meta_set(conn, day, "끝30")
        codes = _codes(proxy, day, {(r.get("mksc_shrn_iscd") or "").strip() for r in last})
        rows = []
        for c in codes:
            rows += _ask(proxy, cfg, day, c)
            time.sleep(CODE_GAP_SEC)
        with proxy._db_lock, proxy.db_conn() as conn:
            for r in rows:
                _put(conn, day, r, reg)
            _meta_set(conn, day, "종목", codes=len(codes))
            return conn.execute("SELECT COUNT(*) FROM vi_day WHERE day = ?", (day,)).fetchone()[0]
    except Exception as e:
        with proxy._db_lock, proxy.db_conn() as conn:
            _init(conn)
            _meta_set(conn, day, error=proxy.safe_message(e, 120))
        raise


def _hms(s):
    return "%s:%s:%s" % (s[0:2], s[2:4], s[4:6]) if s else None


def _state(src, error):
    src = set((src or "").split(","))
    if error:
        return "못 받음"
    if "종목" in src:
        return "종목 채움"
    if "장중" in src:
        return "장중 쌓는 중"
    return "앞쪽 못 받음"


def day_list(proxy, day):
    """주소 /api/kis/vi-day?day= 의 (data, meta)."""
    with proxy._db_lock, proxy.db_conn() as conn:
        _init(conn)
        m = conn.execute("SELECT got_at, n, error, src, codes FROM vi_day_meta WHERE day = ?", (day,)).fetchone()
        rows = conn.execute("SELECT code, at, name, kind, cncl, price, stnd, dprt, dmc_stnd, dmc_dprt, cnt, up, regular "
                            "FROM vi_day WHERE day = ? ORDER BY at", (day,)).fetchall()
    data = [{"code": r[0], "at": _hms(r[1]), "name": r[2], "kind": r[3], "cancel": _hms(r[4]), "price": r[5],
             "staticBase": r[6], "staticGap": r[7], "dynamicBase": r[8], "dynamicGap": r[9], "count": r[10],
             "up": None if r[11] is None else bool(r[11]), "regular": None if r[12] is None else bool(r[12])} for r in rows]
    meta = {"day": day, "state": _state(m[3], m[2]) if m else "안 받음", "gotAt": m[0] if m else None, "n": len(data),
            "src": [s for s in (m[3] or "").split(",") if s] if m else [], "codes": m[4] if m else None, "error": m[2] if m else None,
            "regular": sum(1 for x in data if x["regular"]), "outside": sum(1 for x in data if x["regular"] is False)}
    return data, meta


def days(proxy):
    """쌓인 날 [{day, n, state}] — 최근 순."""
    with proxy._db_lock, proxy.db_conn() as conn:
        _init(conn)
        got = conn.execute("SELECT day, n, error, src FROM vi_day_meta ORDER BY day DESC").fetchall()
    return [{"day": d, "n": n, "state": _state(s, e)} for d, n, e, s in got]


def _todo(proxy, today):
    """되채울 날 하나 — 오늘 앞 BACKFILL_DAYS 일 중 평일 · 안 쉰 날 · 아직 종목으로 안 채운 가장 최근 날(오늘 이미 해 보고 못 받은 날은 내일 다시)."""
    import market_hours
    with proxy._db_lock, proxy.db_conn() as conn:
        _init(conn)
        done = {d: (s, e, g) for d, s, e, g in conn.execute("SELECT day, src, error, got_at FROM vi_day_meta")}
    t0 = datetime.strptime(today, "%Y%m%d")
    for i in range(1, BACKFILL_DAYS + 1):
        d = t0 - timedelta(days=i)
        ds = d.strftime("%Y%m%d")
        if d.weekday() >= 5:
            continue
        s, e, g = done.get(ds, (None, None, None))
        if "종목" in (s or "") and not e:
            continue
        if e and (g or "")[:10] == _now().strftime("%Y-%m-%d"):
            continue
        if market_hours.today(proxy, day=ds).get("open") is False:
            continue
        return ds
    return None


def status():
    return dict(_status, storeAt="%02d:%02d" % STORE_AT, nightEnd="%02d:%02d" % NIGHT_END, backfillDays=BACKFILL_DAYS)


def start(proxy):
    """쓰는 서버가 뜰 때 한 번 — 평일 STORE_AT 뒤 그날 것을 끝맺고, 밤 · 주말에 지난 날 하루씩 되채운다(장중 쌓기는 intraday_alerts 가 absorb 를 부름)."""
    if not proxy.marketdb.writable():
        return False
    import market_hours

    def loop():
        time.sleep(70)
        stored = None
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = now.hour * 60 + now.minute
                night = hm >= STORE_AT[0] * 60 + STORE_AT[1] or hm < NIGHT_END[0] * 60 + NIGHT_END[1] or now.weekday() >= 5
                if night:
                    if (hm >= STORE_AT[0] * 60 + STORE_AT[1] and stored != day and now.weekday() < 5
                            and market_hours.today(proxy, day=day, now=now).get("open") is not False):
                        stored = day               # 멈춰도 그날은 다시 안 돈다
                        n = store_day(proxy, proxy.load_secrets(), day)
                        _status["stored"] = "%s %d건" % (now.strftime("%H:%M"), n)
                        print("  [VI 기록] %s 그날 VI %d건(장중 · 종목 · 끝30)" % (day, n), flush=True)
                    else:
                        back = _todo(proxy, day)
                        if back:
                            n = store_day(proxy, proxy.load_secrets(), back)
                            _status["backfill"] = "%s %d건" % (back, n)
                            print("  [VI 기록] 지난 날 %s VI %d건 채움" % (back, n), flush=True)
                _status.update(error=None, at=now.strftime("%H:%M:%S"))
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [VI 기록] 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="vi-days").start()
    return True
