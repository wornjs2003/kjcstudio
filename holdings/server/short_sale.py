# -*- coding: utf-8 -*-
"""공매도 — 감시 대상(코스피200 · 코스닥150) 종목마다 KIS 「공매도 일별추이」 를 쌓고, 실시간 순위 「공매도」 칩에 내준다
(2026-11-06 · 재권님 「공매도 하위에 값을 추가해야해. 소팅하는건 금액과 비율이 있어야되고 1일 5일 한달 1년 도 필요해」 → 받는 법 「나로 해줘」).

── 왜 순위 API 를 안 쓰나 ──

    KIS 「공매도 상위」(FHPST04820000)는 **공매도 수량 순 30종목만** 준다(2026-11-06 실측 · 기간 넷 다). 금액 · 비율 순으로 다시 세우면
    빠지는 종목이 생긴다 — 시장 여섯 갈래로 나눠 받아 80종목이 되자 삼성전기(그날 공매도 1,251억)가 새로 들어왔다.
    그래서 **감시 대상 전부를 종목마다** 받아 쌓고, 그 안에서 세운다. 감시 대상 밖(작은 종목)은 안 든다.

── 무엇을 쌓나 ──

    표 `short_daily` — (종목 · 날짜)마다 공매도 수량 · 공매도 거래대금 · 그날 전체 거래량 · 전체 거래대금.
    KIS 「공매도 일별추이」(FHPST04830000 · `daily-short-sale`) output2 의 `ssts_cntg_qty` · `ssts_tr_pbmn` · `acml_vol` · `acml_tr_pbmn`.
    **한 번에 100거래일까지 온다**(실측 · 범위가 더 길면 최근 100개만) — 처음 1년치는 `CHUNK_DAYS` 창으로 나눠 받는다.

── 그날 값은 언제 ──

    **장중에는 그날 줄의 공매도가 0 이다**(11-06 15:31 삼성전자 실측). 거래소가 장 뒤에 낸다. 그래서 「그 날이 나왔나」 를
    `SENTINEL`(삼성전자) 하나로 가른다 — 그 종목의 그날 공매도가 0 보다 크면 그 날까지 받는다. 0 인 날 줄은 **안 쌓는다**
    (0 으로 쌓으면 「공매도 없음」 과 「아직 안 나옴」 이 갈리지 않는다 · 「못 쟀으면 0 이 아니라 「못 쟀다」」).

── 언제 도나 ──

    쓰기 서버(개발 서버 8765)에서만. `TICK_SEC` 마다 기준 종목 한 번(KIS 1번)을 보고, 기준 날짜보다 뒤처진 종목만 받는다.
    처음에는 350종목 × 1년치라 약 1,050번(종목마다 셋) · `GAP_SEC` 간격 · 그 뒤에는 새 날이 나올 때 하루 350번쯤.
    KIS 예산은 `kis_get` 이 그대로 센다 — 따로 세지 않는다.

── 내주기 ──

    `/api/kis/short-sale?period=1d|5d|1m|1y&sort=amt|ratio` — 감시 대상 종목마다 그 기간 공매도 거래대금 합 · 비율
    (공매도 거래대금 합 ÷ 전체 거래대금 합 × 100). 「1d · 5d」 는 쌓인 거래일 끝에서 1 · 5개, 「1m · 1y」 는 마지막 날에서 한 달 · 1년 안.
    읽기 전용 서버(8764 · 세션)도 같은 DB 를 읽는다.
"""

import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

import dart
import marketdb
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))
PATH = "/uapi/domestic-stock/v1/quotations/daily-short-sale"
TR = "FHPST04830000"
SENTINEL = "005930"        # 그날 공매도가 나왔나를 가르는 종목 — 공매도가 0 인 날이 사실상 없다
KEEP_DAYS = 400            # 처음 받을 때 이만큼(달력 날) 앞부터 — 「1년」 에 여유
CHUNK_DAYS = 130           # 한 번에 물을 달력 날 — 100거래일 밑으로
GAP_SEC = 0.2              # 종목 사이 쉼 — KIS 예산(초당 40)의 한 귀퉁이만
TICK_SEC = 600             # 기준 종목을 다시 볼 간격
PERIODS = {"1d": ("n", 1), "5d": ("n", 5), "1m": ("days", 31), "1y": ("days", 366)}
SORTS = ("amt", "ratio")

_status = {"startedAt": None, "lastTick": None, "latest": None, "filled": 0, "lastError": None, "busy": False}


def _now():
    return datetime.now(KST)


def init():
    with dart._db_lock, dart.db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS short_daily (
            stock_code TEXT NOT NULL, d TEXT NOT NULL,
            qty INTEGER, amt INTEGER, vol INTEGER, tot_amt INTEGER,
            PRIMARY KEY (stock_code, d))""")


def _rows(sql, args=()):
    """읽기 — 표가 아직 없으면(쌓는 서버가 한 번도 안 돌았다) 빈 목록."""
    try:
        with dart._db_lock, dart.db_conn() as conn:
            return conn.execute(sql, args).fetchall()
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            return []
        raise


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _get(proxy, code, d1, d2):
    data = proxy.kis_get(proxy.load_secrets(), PATH,
                         {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
                          "FID_INPUT_DATE_1": d1, "FID_INPUT_DATE_2": d2}, TR)
    return data.get("output2") or []


def _latest(proxy):
    """그날 공매도가 나온 마지막 날(YYYYMMDD) — 기준 종목의 최근 열흘에서 공매도가 0 보다 큰 가장 늦은 날."""
    now = _now()
    rows = _get(proxy, SENTINEL, (now - timedelta(days=14)).strftime("%Y%m%d"), now.strftime("%Y%m%d"))
    got = [r.get("stck_bsop_date") for r in rows if (_int(r.get("ssts_cntg_qty")) or 0) > 0]
    return max(got) if got else None


def _save(code, rows, upto):
    keep = []
    for r in rows:
        d = (r.get("stck_bsop_date") or "").strip()
        if not d or d > upto:
            continue                     # 아직 안 나온 날(그날 공매도 0)은 안 쌓는다
        keep.append((code, d, _int(r.get("ssts_cntg_qty")), _int(r.get("ssts_tr_pbmn")),
                     _int(r.get("acml_vol")), _int(r.get("acml_tr_pbmn"))))
    if keep:
        with dart._db_lock, dart.db_conn() as conn:
            conn.executemany("""INSERT INTO short_daily (stock_code, d, qty, amt, vol, tot_amt) VALUES (?,?,?,?,?,?)
                                ON CONFLICT(stock_code, d) DO UPDATE SET qty=excluded.qty, amt=excluded.amt,
                                vol=excluded.vol, tot_amt=excluded.tot_amt""", keep)
    return len(keep)


def _ymd(s):
    return datetime.strptime(s, "%Y%m%d")


def fill(proxy):
    """뒤처진 종목만 받는다 → 받은 종목 수."""
    latest = _latest(proxy)
    _status["latest"] = latest
    if not latest:
        return 0
    have = {r["stock_code"]: r["m"] for r in _rows("SELECT stock_code, MAX(d) AS m FROM short_daily GROUP BY stock_code")}
    done = 0
    for u in dart.universe_rows(None):
        code = u["stock_code"]
        last = have.get(code)
        if last and last >= latest:
            continue
        start = _ymd(last) + timedelta(days=1) if last else _ymd(latest) - timedelta(days=KEEP_DAYS)
        end = _ymd(latest)
        while start <= end:
            stop = min(end, start + timedelta(days=CHUNK_DAYS))
            _save(code, _get(proxy, code, start.strftime("%Y%m%d"), stop.strftime("%Y%m%d")), latest)
            start = stop + timedelta(days=1)
            time.sleep(GAP_SEC)
        done += 1
        _status["filled"] += 1
    return done


def start(proxy):
    """쓰기 서버(개발 서버)에서 `kis_proxy` 가 부른다."""
    if not marketdb.writable():
        return False
    init()
    _status["startedAt"] = _now().isoformat(timespec="seconds")

    def loop():
        time.sleep(60)                   # 서버가 막 뜬 참이라 첫 화면에 양보한다
        last = None
        while True:
            _status["lastTick"] = _now().isoformat(timespec="seconds")
            _status["busy"] = True
            try:
                n = fill(proxy)
                if n:
                    print("  [공매도] %d종목 받음 · 기준 %s" % (n, _status["latest"]), flush=True)
                last = None
            except Exception as e:
                key = safe_message(e, 160)
                _status["lastError"] = key
                if key != last:
                    last = key
                    print("  [공매도] 바퀴 오류 — %s (같은 오류는 다시 안 적습니다)" % key, flush=True)
            finally:
                _status["busy"] = False
            time.sleep(TICK_SEC)

    threading.Thread(target=loop, daemon=True, name="short-sale").start()
    return True


def ranking(period="1d", sort="amt"):
    """`/api/kis/short-sale` — 감시 대상 종목마다 그 기간 공매도 거래대금 합 · 비율. 이름 · 시장은 감시 대상 표에서."""
    if period not in PERIODS:
        period = "1d"
    if sort not in SORTS:
        sort = "amt"
    days = [r["d"] for r in _rows("SELECT DISTINCT d FROM short_daily WHERE stock_code = ? ORDER BY d DESC LIMIT 400",
                                  (SENTINEL,))]
    meta = {"period": period, "sort": sort, "periods": list(PERIODS), "sorts": list(SORTS),
            "latest": days[0] if days else None, "status": dict(_status)}
    if not days:
        meta["saved"] = False
        return {"rows": [], "meta": meta}
    kind, n = PERIODS[period]
    if kind == "n":
        span = days[:n]
        d_from = span[-1]
    else:
        d_from = (_ymd(days[0]) - timedelta(days=n)).strftime("%Y%m%d")
        span = [d for d in days if d > d_from]
        d_from = span[-1] if span else days[0]
    meta.update(saved=True, dFrom=d_from, dTo=days[0], tradingDays=len(span))
    names = {u["stock_code"]: (u["name"], u["market"]) for u in dart.universe_rows(None)}
    got = _rows("""SELECT stock_code, SUM(amt) AS amt, SUM(qty) AS qty, SUM(tot_amt) AS tot, COUNT(*) AS n
                   FROM short_daily WHERE d >= ? AND d <= ? GROUP BY stock_code""", (d_from, days[0]))
    rows = []
    for r in got:
        if r["stock_code"] not in names:
            continue                    # 감시 대상에서 빠진 종목
        tot = r["tot"] or 0
        rows.append({"code": r["stock_code"], "name": names[r["stock_code"]][0], "market": names[r["stock_code"]][1],
                     "amt": r["amt"], "qty": r["qty"], "days": r["n"],
                     "ratio": round(r["amt"] * 100.0 / tot, 2) if tot and r["amt"] is not None else None})
    key = (lambda x: x["amt"] or 0) if sort == "amt" else (lambda x: x["ratio"] if x["ratio"] is not None else -1)
    rows.sort(key=key, reverse=True)
    meta["count"] = len(rows)
    meta["universe"] = len(names)
    return {"rows": rows, "meta": meta}
