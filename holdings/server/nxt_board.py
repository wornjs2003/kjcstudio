# -*- coding: utf-8 -*-
"""넥스트레이드 장외 보드 — 날마다 종가 · 장외(장 후) · 다음날 프리장 · 야간선물을 쌓아 Insight 「투자 전략」 에 낸다 (2026-10-26).

재권님 — 「종가 후 넥장에서 오른 · 내린 종목 목록과 다음날 시초가 차이를 Insight 에서 매일 모니터링」(16:4x) →
시황분석 시안 「응 세로로 2배 늘려서 진행해줘」(17:2x) → 서버 안 「응 해」(17:4x · 개발1 창). 화면은 시황분석이 만든다.

    언제      평일 15:41~15:59 한 번 — KRX 종가(시간외 단일가 16:00 전 · 그 뒤 J 현재가는 시간외 값으로 움직인다 — 2026-10-26 17:47 실측
              삼성전자 J 213,000 ↔ 정규장 종가 213,500)
              평일 15:21~15:29 한 번 — 넥스트레이드 메인장(~15:20) 이 닫히고 애프터(15:30~) 가 열리기 전 NX 누적 거래량(main_vol)
              평일 20:01~20:30 한 번 — 장외(애프터마켓)가 20:00 에 닫힌 뒤
              매일 06:01~06:30 한 번 — 야간선물(KRX 야간장)이 06:00 에 닫힌 뒤. 그 값은 **앞 평일** 의 것으로 적는다
    범위      코스피 · 코스닥 **주권 전부** — nxt_pre 의 종목 마스터(그룹 ST) 그대로. 시장은 nxt_pre.MARKET_OF
    값        멀티 시세(intstock-multprice) 30종목씩 — 15:41 시장구분 J 의 현재가 = 그날 **KRX 종가**,
              20:01 시장구분 NX 의 현재가 · 누적 거래량 = **장외 마지막가** · 그날 NX 거래량. 하루 91번 × 2
              15:41 을 놓친 날(서버가 그때 내려가 있었음)은 종가가 null — 장외 등락률도 null 이다(시간외 값을 종가로 쓰지 않는다)
              ⚠️ 「20:00 뒤 NX 현재가 = 장외 마지막가」 는 **아직 실측 전**(2026-10-26 20:01 에 잰다)
    프리장    다음 거래일 08:51 에 nxt_pre 가 저장하는 장외가(nxt_pre.price) 를 그대로 읽는다 — 따로 안 부른다
    다음 날 시가  다음 거래일의 정규장 시가(open) — 15:41 종가와 같은 J 멀티 시세 응답의 시가(inter2_oprc)를 그날 줄에 함께 쓴다(KIS 더 안 부름 ·
              2026-11-20 재권님 「응 그래」 · 넥장 표에 다음날 시초가 칸). 그 전에 쌓인 날 · 15:41 을 놓친 날은 fill_open 이 보드에 오른
              종목만 J 일봉으로 채운다(서버 뜰 때 · 종가 저장 뒤)
    「다음 날」  그 날보다 뒤에 종가가 쌓인 첫 거래일 — 없으면(아직 그날 15:41 전) 프리장(nxt_pre)이 쌓인 첫 날. 전에는 프리장 날로만 잡아
              2026-11-19(수능 · 프리장 기록 없음)을 건너뛰고 11-18 줄의 다음 날이 11-20 으로 나왔다
    야간선물  코스피200 · 코스닥150 최근월물(FHMIF10000000 · 시장 CM · 10100000 · 10600000) — 2번
              (2026-10-26 17:2x 둘 다 응답 정상 · 그때는 야간장 전이라 값이 주간과 같았다 — 06:00 값이 야간 종가인지는 아직 못 잼)
    장외 체결  NX 누적 거래량은 **하루 전체** 라 20:01 값만으로는 장외 체결이 있었는지 못 가른다 — 체결이 없어도 현재가에
              메인장 마지막 가격이 남아 「장외가 = 종가 · 0.00%」 로 보였다(2026-11-05 시황분석 · qa 82칸). 그래서
              장외 거래량 = 20:01 누적 − 15:2x 누적(main_vol). **0 이면 장외가를 null** 로 낸다.
              main_vol 이 없는 날(그날 15:2x 를 놓침 · 2026-11-05 전에 쌓인 날)은 가를 수 없어 전처럼 내고 afterVol 은 null
    저장      market.db 의 `nxt_board`(날 · 종목 · 시장 · 이름 · 종가 · 장외가 · 그날 NX 거래량 · 메인장 마감 NX 거래량) · `nxt_fut`(날 · 무엇 · 이름 · 값 · 등락률)
    주소      GET /api/nxt/board?market=kospi|kosdaq&days=N — 모양은 board() 주석 · 「없음」 은 null(0 아님)

8765 만 받는다(`kis_proxy` 가 `is_sender` 로 부른다) · 읽기는 어느 서버든 자기 DB 로. 알림은 없다(화면만).
"""

import threading
import time
from datetime import datetime, timedelta, timezone

import closing_bet
import nxt_pre
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))

MAINVOL_AT, MAINVOL_UNTIL = (15, 21), (15, 30)
CLOSE_AT, CLOSE_UNTIL = (15, 41), (16, 0)
AFTER_AT, AFTER_UNTIL = (20, 1), (20, 30)
FUT_AT, FUT_UNTIL = (6, 1), (6, 30)
TOP_N = 20                      # 날마다 오름 · 내림 각 몇 종목 — 시황분석 시안 「장외 오름 · 내림 각 20」
DAYS_MAX = 20
FUTS = (("kospi200", "10100000"), ("kosdaq150", "10600000"))
AFTER_RETRY_SEC = 180          # 20:01~20:29 장외 저장이 실패하면 이만큼 뒤 다시 — 전에는 하루 한 번이라 2026-11-18 20:01 한 번 실패로 그날 장외가 통째로 비었다
FUT_RETRY_SEC = 120             # 06:01~06:29 야간선물 받기가 하나라도 실패하면 이만큼 뒤 다시 — 창 안에서 많아야 열네 번 · 한 번에 KIS 2건
TICK = 30

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS nxt_board (
        day TEXT NOT NULL, code TEXT NOT NULL, market TEXT, name TEXT,
        close INTEGER, after INTEGER, after_vol INTEGER, main_vol INTEGER, saved_at TEXT, PRIMARY KEY (day, code))""",
    """CREATE TABLE IF NOT EXISTS nxt_fut (
        day TEXT NOT NULL, which TEXT NOT NULL, name TEXT, last REAL, pct REAL, saved_at TEXT,
        PRIMARY KEY (day, which))""",
)

_status = {"mainVolDay": None, "mainVolAt": None, "mainVolCodes": None, "closeDay": None, "closeAt": None, "closeCodes": None, "afterDay": None, "afterAt": None, "afterCodes": None, "afterTraded": None,
           "futDay": None, "futAt": None, "error": None}


def _now():
    return datetime.now(KST)


def _init(proxy):
    with proxy._db_lock, proxy.db_conn() as conn:
        for q in _SCHEMA:
            conn.execute(q)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(nxt_board)")}
        if "main_vol" not in cols:              # 2026-11-05 전에 만든 표 — 칸만 더한다(옛 날은 null)
            conn.execute("ALTER TABLE nxt_board ADD COLUMN main_vol INTEGER")
        if "open" not in cols:                  # 그날 정규장 시가(2026-11-20) — 옛 날은 null · fill_open 이 보드 종목만 채움
            conn.execute("ALTER TABLE nxt_board ADD COLUMN open INTEGER")


def _prev_weekday(d):
    d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d


def _multi(proxy, cfg, codes, div):
    """{code: {price, vol, name}} — 멀티 시세 한 시장구분"""
    out = {}
    codes = list(codes)
    for i in range(0, len(codes), nxt_pre.MULTI_MAX):
        params = {}
        for n, c in enumerate(codes[i:i + nxt_pre.MULTI_MAX], 1):
            params["FID_COND_MRKT_DIV_CODE_%d" % n] = div
            params["FID_INPUT_ISCD_%d" % n] = c
        data = proxy.kis_get(cfg, "/uapi/domestic-stock/v1/quotations/intstock-multprice", params, "FHKST11300006")
        for r in (data or {}).get("output") or []:
            code = (r.get("inter_shrn_iscd") or "").strip()
            if code:
                out[code] = {"price": proxy._num(r.get("inter2_prpr"), int), "vol": proxy._num(r.get("acml_vol"), int) or 0,
                             "open": proxy._num(r.get("inter2_oprc"), int),   # 그날 시가 — 15:41 J 값이면 정규장 시가(넥장 보드 「다음 날 시가」)
                             "name": (r.get("inter_kor_isnm") or "").strip(),
                             # 종가배팅 후보(closing_bet)가 15:41 J 값을 그대로 쓴다 — 따로 안 부르게
                             "high": proxy._num(r.get("inter2_hgpr"), int), "low": proxy._num(r.get("inter2_lwpr"), int),
                             "value": proxy._num(r.get("acml_tr_pbmn"), int), "pct": proxy._num(r.get("prdy_ctrt"))}
        time.sleep(nxt_pre.GAP_SEC)
    return out


def save_main_vol(proxy, day):
    """넥스트레이드 메인장 마감 뒤 NX 누적 거래량 — 15:21~15:29. 저장한 종목 수. 합이 0 이면(휴장) 안 쓴다."""
    _init(proxy)
    cfg = proxy.load_secrets()
    names = nxt_pre.master_codes()
    nx = _multi(proxy, cfg, names, "NX")
    stamp = _now().isoformat(timespec="seconds")
    if not sum(r["vol"] for r in nx.values()):
        _status.update(mainVolDay=day, mainVolAt=stamp, mainVolCodes=0, error="NX 거래량 합이 0 — 휴장으로 보고 저장 안 함")
        return 0
    # 응답에 없는 종목(그 묶음 실패)은 null — 0 으로 두면 20:01 에 하루 전체가 장외 거래로 셈된다(개념정의 검수 11-05)
    rows = [(day, code, nxt_pre.MARKET_OF.get(code), name or (nx.get(code) or {}).get("name"),
             nx[code]["vol"] if code in nx else None, stamp) for code, name in names.items()]
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.executemany("INSERT INTO nxt_board (day, code, market, name, main_vol, saved_at) VALUES (?,?,?,?,?,?) "
                         "ON CONFLICT(day, code) DO UPDATE SET main_vol = COALESCE(excluded.main_vol, nxt_board.main_vol)", rows)  # 다시 돌 때 빠진 종목이 첫 값을 안 지움
    _status.update(mainVolDay=day, mainVolAt=stamp, mainVolCodes=len(rows), error=None)
    return len(rows)


def save_close(proxy, day):
    """그날 KRX 종가 — 15:41~15:59. 저장한 종목 수. 값이 없으면(휴장) 안 쓴다."""
    _init(proxy)
    cfg = proxy.load_secrets()
    names = nxt_pre.master_codes()
    krx = _multi(proxy, cfg, names, "J")
    if not sum(r["vol"] for r in krx.values()):
        _status.update(closeDay=day, closeAt=_now().isoformat(timespec="seconds"), closeCodes=0, error="KRX 거래량 합이 0 — 휴장으로 보고 저장 안 함")
        return 0
    stamp = _now().isoformat(timespec="seconds")
    rows = [(day, code, nxt_pre.MARKET_OF.get(code), name or (krx.get(code) or {}).get("name"),
             (krx.get(code) or {}).get("price") or None, (krx.get(code) or {}).get("open") or None, stamp) for code, name in names.items()]
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.executemany("INSERT INTO nxt_board (day, code, market, name, close, open, saved_at) VALUES (?,?,?,?,?,?,?) "
                         "ON CONFLICT(day, code) DO UPDATE SET close = excluded.close, open = COALESCE(excluded.open, nxt_board.open), "
                         "market = excluded.market, name = excluded.name", rows)
    _status.update(closeDay=day, closeAt=stamp, closeCodes=len(rows), error=None)
    try:                                         # 종가배팅 판 후보 — 같은 J 값으로(2026-11-18 · server/closing_bet.py)
        closing_bet.save_candidates(proxy, day, krx)
    except Exception as e:
        _status["error"] = "종가배팅 후보: %s" % safe_message(e, 120)
    return len(rows)


def save_after(proxy, day):
    """그날 장외 마지막가 · 장외 거래량 — 20:01~20:29. 저장한 종목 수. NX 거래량 합이 0 이면 휴장으로 보고 안 쓴다."""
    _init(proxy)
    cfg = proxy.load_secrets()
    names = nxt_pre.master_codes()
    nx = _multi(proxy, cfg, names, "NX")
    if not sum(r["vol"] for r in nx.values()):
        _status.update(afterDay=day, afterAt=_now().isoformat(timespec="seconds"), afterCodes=len(names), afterTraded=0,
                       error="NX 거래량 합이 0 — 휴장으로 보고 저장 안 함")
        return 0
    stamp = _now().isoformat(timespec="seconds")
    with proxy._db_lock, proxy.db_conn() as conn:
        main_vol = {r[0]: r[1] for r in conn.execute("SELECT code, main_vol FROM nxt_board WHERE day = ?", (day,))}
    rows = []
    for code, name in names.items():
        n = nx.get(code)
        if n is None:                                             # 응답에 없음(그 묶음 실패) — 못 받음은 null
            rows.append((day, code, nxt_pre.MARKET_OF.get(code), name, None, None, stamp))
            continue
        vol, mv = n.get("vol") or 0, main_vol.get(code)
        traded = (vol - mv) > 0 if mv is not None else vol > 0    # main_vol 이 없으면 가를 수 없다 — 전처럼
        rows.append((day, code, nxt_pre.MARKET_OF.get(code), name or n.get("name"),
                     (n.get("price") or None) if traded else None, vol, stamp))
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.executemany("INSERT INTO nxt_board (day, code, market, name, after, after_vol, saved_at) VALUES (?,?,?,?,?,?,?) "
                         "ON CONFLICT(day, code) DO UPDATE SET after = excluded.after, after_vol = excluded.after_vol, "
                         "saved_at = excluded.saved_at", rows)
    _status.update(afterDay=day, afterAt=stamp, afterCodes=len(rows), afterTraded=sum(1 for r in rows if r[4]), error=None)
    return len(rows)


def save_futures(proxy, day):
    """야간선물 둘 — 그 앞 평일(day) 의 값으로 적는다. 저장한 수."""
    _init(proxy)
    cfg = proxy.load_secrets()
    stamp = _now().isoformat(timespec="seconds")
    rows = []
    for which, code in FUTS:
        try:
            data = proxy.kis_get(cfg, "/uapi/domestic-futureoption/v1/quotations/inquire-price",
                                 {"FID_COND_MRKT_DIV_CODE": "CM", "FID_INPUT_ISCD": code}, "FHMIF10000000")
            o = (data or {}).get("output1") or {}
            rows.append((day, which, (o.get("hts_kor_isnm") or "").strip() or None,
                         proxy._num(o.get("futs_prpr")), proxy._num(o.get("futs_prdy_ctrt")), stamp))
        except Exception as e:
            _status["error"] = "야간선물 %s: %s" % (which, safe_message(e, 100))
            print("  [넥장 보드] %s" % _status["error"], flush=True)      # 상태값만 두면 재시작에 사라진다(2026-11-19)
    if rows:
        with proxy._db_lock, proxy.db_conn() as conn:
            conn.executemany("INSERT OR REPLACE INTO nxt_fut (day, which, name, last, pct, saved_at) VALUES (?,?,?,?,?,?)", rows)
    _status.update(futAt=stamp)         # futDay 는 바퀴가 둘 다 받았을 때만 적는다 — 여기서 적으면 실패해도 그날이 끝난다
    return len(rows)


def latest_futures_or_fetch(proxy):
    """07:00 미국 데일리용 — 오늘 06:01 저장분이 없으면 한 번 더 받아 저장하고 읽는다 (2026-11-19 — 06:01 이 KIS 오류로 둘 다
    실패해 저장본에 야간선물이 빠졌다). 정규장 전이라 KIS 야간선물 시세는 아직 지난밤 마감값이다."""
    got = latest_futures(proxy)
    if got and len(got.get("rows") or {}) >= len(FUTS):
        return got
    try:
        save_futures(proxy, _prev_weekday(_now()).strftime("%Y%m%d"))
    except Exception as e:
        print("  [넥장 보드] 야간선물 07:00 다시 받기 실패: %s" % type(e).__name__, flush=True)
    return latest_futures(proxy) or got


def latest_futures(proxy):
    """오늘 06:01 에 저장한 야간선물 — {day, rows: {which: {name, last, pct}}} · 오늘 저장분이 없으면 None.

    데일리분석 07:30 글이 읽는다(daily.night_lines). **저장 시각(saved_at)이 오늘인 것만** 낸다 —
    06:01 을 놓친 날 지난 값을 오늘 것처럼 보내지 않는다. 표가 없으면(한 번도 안 돈 서버) None.
    """
    today = _now().strftime("%Y-%m-%d")
    with proxy._db_lock, proxy.db_conn() as conn:
        try:
            rs = [dict(r) for r in conn.execute(
                "SELECT day, which, name, last, pct, saved_at FROM nxt_fut WHERE day = (SELECT MAX(day) FROM nxt_fut)")]
        except Exception:
            return None
    rs = [r for r in rs if (r.get("saved_at") or "")[:10] == today]
    if not rs:
        return None
    return {"day": rs[0]["day"], "rows": {r["which"]: {"name": r["name"], "last": r["last"], "pct": r["pct"]} for r in rs}}


def _pct(a, b):
    return round((a / b - 1) * 100, 2) if a and b else None


def _after_vol(whole, main):
    """장외 거래량 = 그날 NX 거래량 − 메인장 마감 NX 거래량. 어느 쪽이 없거나 빼서 음수면(못 잰 것) null."""
    if whole is None or main is None or whole < main:
        return None
    return whole - main


def board(proxy, market, days=5):
    """화면 한 장 —

        {market, days: [{day, preDay, fut: {kospi200: {name, last, pct} | null, kosdaq150: …}}] (최신이 앞),
         rows: [{code, name, side: "up" | "down", rank, cells: {<day>: {close, after, afterPct, afterVol, pre, prePct, open, openPct, openVsAfter}}}]}

    after 가 null 이면 장외 체결이 없었다(또는 못 받음). afterVol 은 장외(15:30~20:00) 거래량 — 그날 15:2x 를 못 잰 날은 null.

    rows 는 날마다 장외 등락률(afterPct · 종가 대비) 오름 · 내림 상위 TOP_N 의 합집합. side · rank 는 그 종목이 든 가장 최근 날 것.
    pre 는 다음 거래일 08:51 장 전 가격(nxt_pre) · prePct 는 그날 종가 대비. 값이 없으면 null.
    open 은 다음 거래일 정규장 시가 · openPct 는 그날 종가 대비 · openVsAfter 는 그날 장외가 대비(장외가 없으면 null).
    preDay 는 「다음 거래일」 — 그 날 뒤 종가가 쌓인 첫 날, 없으면 프리장이 쌓인 첫 날(머리말 「다음 날」).
    """
    days = max(1, min(DAYS_MAX, int(days or 5)))
    with proxy._db_lock, proxy.db_conn() as conn:
        try:
            conn.execute("SELECT 1 FROM nxt_board LIMIT 1")
        except Exception:                       # 표가 아직 없다 — 쌓기 전
            return {"market": market, "days": [], "rows": []}
        ds = [r[0] for r in conn.execute(
            "SELECT DISTINCT day FROM nxt_board WHERE market = ? ORDER BY day DESC LIMIT ?", (market, days))]
        if not ds:
            return {"market": market, "days": [], "rows": []}
        q = ",".join("?" * len(ds))
        # 저장 바퀴가 안 도는 서버(8764 · 세션)는 칸을 안 더한 옛 표일 수 있다 — 읽기 길에서는 표를 안 바꾸고 null 로 읽는다(qa 검수 11-05)
        has_mv = "main_vol" in {r[1] for r in conn.execute("PRAGMA table_info(nxt_board)")}
        cols = {r[1] for r in conn.execute("PRAGMA table_info(nxt_board)")}
        board_rows = [dict(r) for r in conn.execute(
            "SELECT day, code, name, close, after, after_vol, " + ("main_vol" if has_mv else "NULL AS main_vol") + " FROM nxt_board WHERE market = ? AND day IN (%s)" % q, [market] + ds)]
        pre_days, pre, opens = {d: None for d in ds}, {}, {}
        for d in ds:                            # 다음 거래일 — 종가가 쌓인 첫 날(수능처럼 프리장이 없던 날도 거래일이다)
            r = conn.execute("SELECT MIN(day) FROM nxt_board WHERE market = ? AND day > ? AND close IS NOT NULL", (market, d)).fetchone()
            pre_days[d] = r[0] if r else None
        nds = [x for x in set(pre_days.values()) if x]
        if nds and "open" in cols:
            q3 = ",".join("?" * len(nds))
            for r in conn.execute("SELECT day, code, open FROM nxt_board WHERE market = ? AND day IN (%s) AND open IS NOT NULL" % q3, [market] + nds):
                opens[(r["day"], r["code"])] = r["open"]
        try:                                    # nxt_pre 표가 없는 서버(한 번도 안 돈 자리)면 프리장은 전부 null
            for d in ds:
                if pre_days[d]:
                    continue
                r = conn.execute("SELECT MIN(day) FROM nxt_pre WHERE day > ?", (d,)).fetchone()   # 다음 날 종가가 아직 없음(그날 15:41 전) — 프리장 날
                pre_days[d] = r[0] if r else None
            pd_list = [x for x in set(pre_days.values()) if x]
            if pd_list:
                q2 = ",".join("?" * len(pd_list))
                for r in conn.execute("SELECT day, code, price, vol FROM nxt_pre WHERE day IN (%s)" % q2, pd_list):
                    if r["price"] and (r["vol"] or 0) > 0:
                        pre[(r["day"], r["code"])] = r["price"]
        except Exception:
            pass
        futs = {}
        for r in conn.execute("SELECT day, which, name, last, pct FROM nxt_fut WHERE day IN (%s)" % q, ds):
            futs.setdefault(r["day"], {})[r["which"]] = {"name": r["name"], "last": r["last"], "pct": r["pct"]}
    by_day = {}
    for r in board_rows:
        by_day.setdefault(r["day"], []).append(r)
    picked = {}            # code -> (side, rank, 그 날)
    for d in sorted(ds):                          # 오래된 날부터 — 최근 날이 덮어 side · rank 가 최근 것이 된다
        ranked = [r for r in by_day.get(d, []) if r["after"] and r["close"]]
        ranked.sort(key=lambda r: r["after"] / r["close"])
        for i, r in enumerate(reversed(ranked[-TOP_N:])):
            if r["after"] > r["close"]:
                picked[r["code"]] = ("up", i + 1, d)
        for i, r in enumerate(ranked[:TOP_N]):
            if r["after"] < r["close"]:
                picked[r["code"]] = ("down", i + 1, d)
    cells_of = {}
    names = {}
    for r in board_rows:
        if r["code"] not in picked:
            continue
        names[r["code"]] = r["name"]
        p = pre.get((pre_days.get(r["day"]), r["code"]))
        o = opens.get((pre_days.get(r["day"]), r["code"]))
        cells_of.setdefault(r["code"], {})[r["day"]] = {
            "close": r["close"], "after": r["after"], "afterPct": _pct(r["after"], r["close"]),
            "afterVol": _after_vol(r["after_vol"], r["main_vol"]),
            "pre": p, "prePct": _pct(p, r["close"]),
            "open": o, "openPct": _pct(o, r["close"]), "openVsAfter": _pct(o, r["after"])}
    rows = [{"code": c, "name": names.get(c), "side": s, "rank": k, "cells": cells_of.get(c, {})}
            for c, (s, k, _d) in picked.items()]
    rows.sort(key=lambda x: (x["side"] != "up", x["rank"]))
    return {"market": market,
            "days": [{"day": d, "preDay": pre_days.get(d), "fut": {w: futs.get(d, {}).get(w) for w, _c in FUTS}} for d in ds],
            "rows": rows}


def fill_open(proxy):
    """보드에 오른 종목의 「다음 거래일 시가」 가 빈 칸만 J 일봉으로 채운다 — 시가를 함께 쓰기 전(2026-11-20 전)에 쌓인 날 · 15:41 을 놓친 날.
    오늘 시가는 그날 15:41 종가 저장이 쓰므로 오늘보다 앞 날만 본다. 종목마다 일봉 한 번(KIS 1건). 채운 칸 수."""
    _init(proxy)
    today = _now().strftime("%Y%m%d")
    need = {}                                     # code -> {다음 날, …}
    for m in ("kospi", "kosdaq"):
        b = board(proxy, m, DAYS_MAX)
        nd_of = {x["day"]: x.get("preDay") for x in b.get("days") or []}
        for r in b.get("rows") or []:
            for d, c in (r.get("cells") or {}).items():
                nd = nd_of.get(d)
                if nd and nd < today and c.get("open") is None and c.get("close"):
                    need.setdefault(r["code"], set()).add(nd)
    if not need:
        return 0
    cfg = proxy.load_secrets()
    n = 0
    for code, nds in need.items():
        try:
            bars = {b["date"]: b.get("open") for b in proxy._stock_daily_j(cfg, code, min(nds))}
        except Exception as e:
            _status["error"] = "다음 날 시가 채우기 %s: %s" % (code, safe_message(e, 120))
            continue
        ups = [(bars[d], d, code) for d in nds if bars.get(d)]
        if ups:
            with proxy._db_lock, proxy.db_conn() as conn:
                conn.executemany("UPDATE nxt_board SET open = ? WHERE day = ? AND code = ? AND open IS NULL", ups)
            n += len(ups)
    return n


def _fill_open_log(proxy):
    try:
        n = fill_open(proxy)
        if n:
            print("  [넥장 보드] 다음 날 시가 %s칸 일봉으로 채움" % n)
    except Exception as e:
        _status["error"] = "다음 날 시가 채우기: %s" % safe_message(e, 120)
        print("  [넥장 보드] 다음 날 시가 채우기 실패: %s" % safe_message(e, 120))


# ── 프리장 시작가 날마다 (2026-11-20 · 시황분석 「미국 3지수 표」 서버 몫 ← 재권님 「나」 → 안에 「응」 · 개발1 창) ──
# 넥스트레이드(NX) 일봉의 시가 = 그날 08:00 프리장 첫 체결 — 11-17 · 11-18 · 11-20 삼성전자 · SK하이닉스 넷이 08:00 첫 5분봉 시가와 같았다(15:0x 잼 ·
# 통합 UN 일봉 시가도 같음). 프리장이 안 열린 날(2026-11-19 수능)은 NX 시가가 정규장 시가와 같아 그대로 쓰면 틀린다 — 그래서 날마다 「열렸나」 를 가른다:
#     프리장 기록이 있는 날부터(nxt_pre 첫 날 · 2026-10-26)  nxt_pre 그날 줄 또는 그 종목 08:00 분봉이 있으면 값 · 없으면 null(why)
#     그보다 앞 날                                       값을 내되 approx true — 열렸는지 가를 기록이 영영 없다
PRE_OPEN_TTL = 600              # 일봉 다시 받는 간격(초) — 지난 날은 안 바뀌고 오늘 칸만 바뀐다 · 종목 하나에 KIS 2건
PRE_OPEN_MAX_CODES = 10
_pre_open_cache = {}            # code -> (받은 때, {날: 시가})


def _nx_daily_open(proxy, cfg, code, start):
    """{날: 시가} — NX 일봉 start(YYYYMMDD)부터 오늘까지. 한 번에 100줄이라 앞으로 물어 간다(6개월이면 두 번)."""
    got_all, end = {}, _now().strftime("%Y%m%d")
    for _ in range(4):
        d = proxy.kis_get(cfg, "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
                          {"FID_COND_MRKT_DIV_CODE": "NX", "FID_INPUT_ISCD": code, "FID_INPUT_DATE_1": start,
                           "FID_INPUT_DATE_2": end, "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"}, "FHKST03010100")
        got = [r for r in proxy.out_rows(d, "output2") if r.get("stck_bsop_date")]
        for r in got:
            o = proxy._num(r.get("stck_oprc"), int)
            if o:
                got_all[r["stck_bsop_date"]] = o
        first = min((r["stck_bsop_date"] for r in got), default=None)
        if len(got) < 100 or not first or first <= start:
            break
        end = (datetime.strptime(first, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
    return {k: v for k, v in got_all.items() if k >= start}


def pre_open(proxy, cfg, codes, months=6):
    """{data: {code: [{date, open, approx, why}] 최신이 앞}, meta: {from, preKnownFrom, errors, preError}} — 「없음」 은 null(0 아님).
    프리장 기록 표(nxt_pre)를 못 읽으면 approx null(모름) · why · meta.preError — 「어림」(옛 날)과 가른다."""
    now = _now()
    start = (now - timedelta(days=int(31 * months))).strftime("%Y%m%d")
    with proxy.db_conn() as conn:
        pre_err = None
        try:
            pre_days = {r[0] for r in conn.execute("SELECT DISTINCT day FROM nxt_pre WHERE vol > 0")}
        except Exception as e:                    # 못 읽음 — 「어림」 으로 보내지 않고 따로(창구 검수 덧 11-20)
            pre_days, pre_err = set(), "프리장 기록 표 못 읽음: %s" % type(e).__name__
        bar_days = {}
        for c in codes:
            bar_days[c] = {r[0][:8] for r in conn.execute(
                "SELECT ts FROM candles WHERE code = ? AND period IN ('1m', '5m') AND ts >= ? AND substr(ts, 9, 4) BETWEEN '0800' AND '0849'",
                (c, start + "0000"))}
    known_from = min(pre_days) if pre_days else None
    data, errors = {}, {}
    for c in codes:
        hit = _pre_open_cache.get(c)
        if hit and time.time() - hit[0] < PRE_OPEN_TTL and min(hit[1] or {"0": 0}) <= start:
            opens = hit[1]
        else:
            try:
                opens = _nx_daily_open(proxy, cfg, c, start)
                _pre_open_cache[c] = (time.time(), opens)
            except Exception as e:
                errors[c] = safe_message(e, 120)
                opens = (hit or (0, {}))[1]
        rows = []
        for day in sorted(opens, reverse=True):
            if day < start:
                continue
            if pre_err:
                rows.append({"date": day, "open": opens[day], "approx": None, "why": "프리장 기록 표를 못 읽어 그날 프리장이 열렸는지 못 가름"})
            elif known_from and day >= known_from:
                ok = day in pre_days or day in bar_days.get(c, set())
                rows.append({"date": day, "open": opens[day] if ok else None, "approx": False,
                             "why": None if ok else "프리장 기록 없음 — 그날 프리장이 안 열렸거나(수능 등) 08:51 기록을 못 쌓음"})
            else:
                rows.append({"date": day, "open": opens[day], "approx": True, "why": None})
        data[c] = rows
    return {"data": data, "meta": {"from": start, "preKnownFrom": known_from, "errors": errors or None, "preError": pre_err}}


def status():
    return dict(_status)


def start(proxy):
    """보내는 서버가 뜰 때 한 번 — 15:21 메인장 NX 거래량 · 15:41 종가 · 20:01 장외 · 06:01 야간선물 바퀴."""
    def loop():
        time.sleep(45)
        _fill_open_log(proxy)                    # 뜰 때 한 번 — 빈 칸만이라 다 채운 뒤에는 KIS 를 안 부른다
        while True:
            try:
                now = _now()
                hm = (now.hour, now.minute)
                day = now.strftime("%Y%m%d")
                if now.weekday() < 5 and MAINVOL_AT <= hm < MAINVOL_UNTIL and _status["mainVolDay"] != day:
                    _status["mainVolDay"] = day
                    try:
                        n = save_main_vol(proxy, day)
                        print("  [넥장 보드] %s 메인장 마감 NX 거래량 %s종목 저장" % (day, n))
                    except Exception as e:
                        _status["error"] = safe_message(e, 160)
                        print("  [넥장 보드] 메인장 거래량 저장 실패: %s" % type(e).__name__)
                if now.weekday() < 5 and CLOSE_AT <= hm < CLOSE_UNTIL and _status["closeDay"] != day:
                    _status["closeDay"] = day
                    try:
                        n = save_close(proxy, day)
                        print("  [넥장 보드] %s 종가 %s종목 저장" % (day, n))
                        if n:
                            _fill_open_log(proxy)
                    except Exception as e:
                        _status["error"] = safe_message(e, 160)
                        print("  [넥장 보드] 종가 저장 실패: %s" % type(e).__name__)
                if (now.weekday() < 5 and AFTER_AT <= hm < AFTER_UNTIL and _status["afterDay"] != day
                        and time.time() >= _status.get("afterRetryAt", 0)):
                    try:                                 # 받으면 save_after 가 afterDay 를 그날로 · 실패하면 AFTER_RETRY_SEC 뒤 창 안에서 다시(2026-11-20)
                        n = save_after(proxy, day)
                        print("  [넥장 보드] %s 장외 %s종목 저장(거래 %s)" % (day, n, _status.get("afterTraded")))
                    except Exception as e:
                        _status["afterRetryAt"] = time.time() + AFTER_RETRY_SEC
                        _status["error"] = safe_message(e, 160)
                        print("  [넥장 보드] 장외 저장 실패(%s초 뒤 다시): %s" % (AFTER_RETRY_SEC, safe_message(e, 160)))
                fday = _prev_weekday(now).strftime("%Y%m%d")
                if (1 <= now.weekday() <= 5 and FUT_AT <= hm < FUT_UNTIL and _status["futDay"] != fday
                        and time.time() >= _status.get("futRetryAt", 0)):
                    try:
                        if save_futures(proxy, fday) >= len(FUTS):
                            _status["futDay"] = fday     # 화~토 아침 = 월~금 밤 야간장 · 둘 다 받았을 때만 그날 끝(2026-11-19 — 실패하면 FUT_RETRY_SEC 뒤 다시)
                        else:
                            _status["futRetryAt"] = time.time() + FUT_RETRY_SEC
                    except Exception as e:
                        _status["futRetryAt"] = time.time() + FUT_RETRY_SEC
                        _status["error"] = safe_message(e, 160)
                        print("  [넥장 보드] 야간선물 저장 실패: %s" % type(e).__name__)
            except Exception as e:
                print("  [넥장 보드] 예기치 못한 오류: %s" % type(e).__name__)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="nxt-board").start()
    return True
