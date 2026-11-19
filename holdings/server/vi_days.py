# -*- coding: utf-8 -*-
"""지난 날 VI 기록 — KIS VI 현황(inquire-vi-status)을 날짜로 그날 전부 받아 날마다 쌓고, 날짜를 넣으면 그날 목록을 낸다 (2026-11-19).

재권님 — 「vi급등 지난것들 정보 받을수 있나? 발등한것과 발등조건 발등시간」(11-19 14:0x · 시황분석1 창) → 안 「지난 날 VI 기록을 날마다 쌓아
단타 판에서 날짜를 고르면 그날 VI 목록」 에 「응 해줘」 → 서버 안(연속 조회 · 날마다 쌓기 · 되채움 · 날짜 주소)에 「응」(11-19 14:09 · 개발2 창).

    받기      KIS VI 현황 FHPST01390000 · FID_INPUT_DATE_1 = 그날 · 전 시장 · 상승 · 하락 둘 다. 한 번에 그날 늦은 것부터 30건이라
              연속 조회(kis_get tr_cont · 응답 머리 M · F 면 뒤가 더 있음)로 끝까지 — PAGES_MAX 장까지
              (11-19 14:0x 잼: 날짜로 2025-10-15 까지 받힘 · 정렬 · 상승/하락 · 시장 갈래를 바꿔도 30건 — 그래서 연속 조회)
    끝        응답 머리가 D · E(끝)이면 full 1 · 장 수 한도에 걸렸거나 머리를 못 읽었으면(옛 상류) full 0 — 「그날 전부」 가 아니다
    쌓기      market.db vi_day(날 · 종목 · 발동 시각 한 줄 — 같은 종목이 그날 여러 번이면 여러 줄) · vi_day_meta(날마다 받은 때 · 건수 · full · 못 받음)
              그날 것은 넥장이 끝난 뒤 STORE_AT 에 한 번 · 지난 날은 BACKFILL_DAYS 일 앞까지 한 바퀴에 하루씩(주말 · 휴장 뺌 · 이미 full 인 날 뺌)
    칸        발동 시각(cntg_vi_hour) · 풀린 시각(vi_cncl_hour) · 종류(vi_kind_code 1 정적 · 2 동적 · 3 둘 다) · 발동가(vi_prc) ·
              정적 기준가 · 괴리율(vi_stnd_prc · vi_dprt) · 동적 기준가 · 괴리율(vi_dmc_stnd_prc · vi_dmc_dprt) · 그날 횟수(vi_count) ·
              오름/내림(발동가가 기준가보다 높으면 오름) · 정규장 안(그날 market_hours 정규장 시각 — 쌓을 때 셈)
    못 받음   받다가 실패한 날은 vi_day_meta.error — 주소가 「못 받음」 으로 낸다(0건과 가름) · 안 받은 날은 「안 받음」
    주소      GET /api/kis/vi-day?day=YYYYMMDD — 그날 목록 · 없으면 쌓인 날 목록 · 넘기는 서버(8764 · 세션)는 상류(8765)를 넘긴다(쌓는 것은 8765 하나)
"""
import threading
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
STORE_AT = (20, 10)          # 그날 것을 쌓는 때 — 넥스트레이드 애프터마켓(20:00) 끝 뒤
BACKFILL_DAYS = 120          # 되채움 앞 날 수(달력) — 재권님 「몇 달」 · 2025-10-15 까지 받히는 것은 잼(11-19)
PAGES_MAX = 80               # 하루 연속 조회 장 수 한도(장마다 30건 — 2,400건)
PAGE_GAP_SEC = 0.3           # 장 사이 쉼 — 초당 한도는 kis_get 이 지키고 이것은 다른 일에 비켜서는 몫
TICK = 60                    # 바퀴(초)
VI_PATH = "/uapi/domestic-stock/v1/quotations/inquire-vi-status"
VI_TR = "FHPST01390000"
KIND = {"1": "정적", "2": "동적", "3": "정적·동적"}
_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS vi_day (day TEXT, code TEXT, at TEXT, name TEXT, kind TEXT, cncl TEXT, price REAL,
       stnd REAL, dprt REAL, dmc_stnd REAL, dmc_dprt REAL, cnt INTEGER, up INTEGER, regular INTEGER, PRIMARY KEY (day, code, at))""",
    """CREATE TABLE IF NOT EXISTS vi_day_meta (day TEXT PRIMARY KEY, got_at TEXT, n INTEGER, full INTEGER, pages INTEGER, error TEXT)""",
)
_status = {"error": None, "stored": None, "backfill": None, "at": None}


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


def fetch_day(proxy, cfg, day):
    """그날 VI 전부 → (줄 목록, full, 장 수). 연속 조회로 끝까지(PAGES_MAX 까지)."""
    params = {"FID_DIV_CLS_CODE": "0", "FID_COND_SCR_DIV_CODE": "20139", "FID_MRKT_CLS_CODE": "0", "FID_INPUT_ISCD": "",
              "FID_RANK_SORT_CLS_CODE": "0", "FID_INPUT_DATE_1": day, "FID_TRGT_CLS_CODE": "", "FID_TRGT_EXLS_CLS_CODE": ""}
    rows, seen, cont, full, pages = [], set(), "", False, 0
    while pages < PAGES_MAX:
        d = proxy.kis_get(cfg, VI_PATH, params, VI_TR, tr_cont=cont)
        pages += 1
        new = 0
        for r in d.get("output") or []:
            if r.get("bsop_date") and r["bsop_date"] != day:
                continue
            k = (r.get("mksc_shrn_iscd"), str(r.get("cntg_vi_hour") or "").zfill(6))
            if not k[0] or k in seen:
                continue
            seen.add(k)
            rows.append(r)
            new += 1
        tc = d.get("_tr_cont")
        if tc in ("D", "E") or (tc == "" and pages == 1 and len(d.get("output") or []) < 30):
            full = True                    # KIS 가 끝이라 함 · 첫 장이 30건이 안 되면 그것이 전부
            break
        if tc not in ("M", "F") or new == 0:
            break                          # 머리를 못 읽음(옛 상류) · 같은 장이 되풀이됨 — 끝을 모름(full 0)
        cont = "N"
        time.sleep(PAGE_GAP_SEC)
    return rows, full, pages


def store_day(proxy, cfg, day):
    """그날을 받아 쌓는다 → 건수. 실패하면 vi_day_meta.error 에 적고 다시 던진다."""
    import market_hours
    try:
        rows, full, pages = fetch_day(proxy, cfg, day)
    except Exception as e:
        with proxy._db_lock, proxy.db_conn() as conn:
            _init(conn)
            conn.execute("INSERT OR REPLACE INTO vi_day_meta (day, got_at, n, full, pages, error) VALUES (?,?,?,?,?,?)",
                         (day, _now().isoformat(timespec="seconds"), None, 0, None, proxy.safe_message(e, 120)))
        raise
    t = market_hours.today(proxy, day=day)
    r0, r1 = t["reg"][0] + "00", t["reg"][1] + "00"
    with proxy._db_lock, proxy.db_conn() as conn:
        _init(conn)
        conn.execute("DELETE FROM vi_day WHERE day = ?", (day,))
        for r in rows:
            at = str(r.get("cntg_vi_hour") or "").zfill(6)
            price, stnd, dmc = _num(r.get("vi_prc")), _num(r.get("vi_stnd_prc")), _num(r.get("vi_dmc_stnd_prc"))
            base = stnd or dmc
            cn = str(r.get("vi_cncl_hour") or "").strip()
            conn.execute("INSERT OR REPLACE INTO vi_day VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                day, r["mksc_shrn_iscd"], at, (r.get("hts_kor_isnm") or "").strip(),
                KIND.get(str(r.get("vi_kind_code") or "").strip(), str(r.get("vi_kind_code") or "").strip() or None),
                cn.zfill(6) if cn and cn.strip("0") else None, price, stnd, _num(r.get("vi_dprt")), dmc, _num(r.get("vi_dmc_dprt")),
                int(_num(r.get("vi_count")) or 0) or None, None if not (price and base) else int(price > base),
                int(r0 <= at < r1) if t.get("open") is not False else None))
        conn.execute("INSERT OR REPLACE INTO vi_day_meta (day, got_at, n, full, pages, error) VALUES (?,?,?,?,?,?)",
                     (day, _now().isoformat(timespec="seconds"), len(rows), int(full), pages, None))
    return len(rows)


def _hms(s):
    return "%s:%s:%s" % (s[0:2], s[2:4], s[4:6]) if s else None


def day_list(proxy, day):
    """주소 /api/kis/vi-day?day= 의 (data, meta)."""
    with proxy._db_lock, proxy.db_conn() as conn:
        _init(conn)
        m = conn.execute("SELECT got_at, n, full, pages, error FROM vi_day_meta WHERE day = ?", (day,)).fetchone()
        rows = conn.execute("SELECT code, at, name, kind, cncl, price, stnd, dprt, dmc_stnd, dmc_dprt, cnt, up, regular "
                            "FROM vi_day WHERE day = ? ORDER BY at", (day,)).fetchall()
    data = [{"code": r[0], "at": _hms(r[1]), "name": r[2], "kind": r[3], "cancel": _hms(r[4]), "price": r[5],
             "staticBase": r[6], "staticGap": r[7], "dynamicBase": r[8], "dynamicGap": r[9], "count": r[10],
             "up": None if r[11] is None else bool(r[11]), "regular": None if r[12] is None else bool(r[12])} for r in rows]
    if m is None:
        state = "안 받음"
    elif m[4]:
        state = "못 받음"
    else:
        state = "전부" if m[2] else "앞쪽 못 받음"   # 끝을 모름 — 늦은 것부터 받았으니 이른 시각이 빠졌을 수 있다
    meta = {"day": day, "state": state, "gotAt": m[0] if m else None, "n": m[1] if m else None, "pages": m[3] if m else None,
            "error": m[4] if m else None, "regular": sum(1 for x in data if x["regular"]), "outside": sum(1 for x in data if x["regular"] is False)}
    return data, meta


def days(proxy):
    """쌓인 날 [{day, n, state}] — 최근 순."""
    with proxy._db_lock, proxy.db_conn() as conn:
        _init(conn)
        got = conn.execute("SELECT day, n, full, error FROM vi_day_meta ORDER BY day DESC").fetchall()
    return [{"day": d, "n": n, "state": "못 받음" if e else ("전부" if f else "앞쪽 못 받음")} for d, n, f, e in got]


def _todo(proxy, today):
    """되채울 날 하나 — 오늘 앞 BACKFILL_DAYS 일 중 평일 · 안 쉰 날 · 아직 full 이 아닌 가장 최근 날(못 받은 날은 하루 한 번만)."""
    import market_hours
    with proxy._db_lock, proxy.db_conn() as conn:
        _init(conn)
        done = {d: (f, e, g) for d, f, e, g in conn.execute("SELECT day, full, error, got_at FROM vi_day_meta")}
    t0 = datetime.strptime(today, "%Y%m%d")
    for i in range(1, BACKFILL_DAYS + 1):
        d = (t0 - timedelta(days=i))
        ds = d.strftime("%Y%m%d")
        if d.weekday() >= 5:
            continue
        f, e, g = done.get(ds, (None, None, None))
        if f:
            continue
        if ds in done and (g or "")[:10] == _now().strftime("%Y-%m-%d"):
            continue                       # 오늘 이미 해 본 날(끝을 모름 · 못 받음) — 내일 다시
        if market_hours.today(proxy, day=ds).get("open") is False:
            continue
        return ds
    return None


def status():
    return dict(_status, storeAt="%02d:%02d" % STORE_AT, backfillDays=BACKFILL_DAYS)


def start(proxy):
    """쓰는 서버가 뜰 때 한 번 — 평일 STORE_AT 뒤 그날 것을 쌓고, 그 뒤 바퀴마다 지난 날 하루씩 되채운다."""
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
                if hm >= STORE_AT[0] * 60 + STORE_AT[1]:
                    if stored != day and now.weekday() < 5 and market_hours.today(proxy, day=day, now=now).get("open") is not False:
                        stored = day               # 멈춰도 그날은 다시 안 돈다
                        n = store_day(proxy, proxy.load_secrets(), day)
                        _status["stored"] = "%s %d건" % (now.strftime("%H:%M"), n)
                        print("  [VI 기록] %s 그날 VI %d건 쌓음" % (day, n), flush=True)
                    else:
                        back = _todo(proxy, day)
                        if back:
                            n = store_day(proxy, proxy.load_secrets(), back)
                            _status["backfill"] = "%s %d건" % (back, n)
                _status.update(error=None, at=now.strftime("%H:%M:%S"))
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [VI 기록] 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="vi-days").start()
    return True
