# -*- coding: utf-8 -*-
"""단타 30 판 — 평일 09:06 단타 상위 30 을 그날 판으로 굳히고 30분마다 값을 적는다 · 30거래일 (2026-11-11).

재권님(시황분석1 창 17:4x) — 「단타 목록 상위 30개를 소팅해서 9시 6분에 배수(매수)하고 9시반 10시 등 30분 단위로 2시까지 가격 추적하도록
셋팅해줘」 → 「위에 날짜도 넣어줘 30일 추적가능하도록」 → 「관심을 제외하고 지난 20일의 정보가 필요해」(18:0x) · 서버 몫은 작업우선순위가
개발2 에 배분(18:15) → 안에 「시가총액순이 아니고 칩이 많이 걸린순으로 해줘」 · 「칩이 많이 걸리고 등락이 높고 시총이 높은순」(18:1x) → 「단타칩에 걸리는 우선순위 소팅하는룰 체크해서 그룰대로 하면되」 → 「칩수가 많은순 초반상승이높은순 시총순 이렇게 해서 올려」(19:1x).
화면은 Insight 「종목 고르는 룰」(company-setup/js/strategy-dt30.js · 시황분석1)이 읽는다.

    단타       아래 OV_CHIPS 중 **하나라도** 든 종목(재권님 18:5x 「100개까지」 — 홈 「단타」 는 둘 이상 · 화면이 칩을 끄고 켜며 다시 셈).
               칩 재료는 홈과 같다(holdings/js/home.js 의 OV_CHIPS · ovList).
               재료는 화면이 받는 서버 값 그대로 — 관심 · 수급(watchlist 문서 · 자동 묶음이 수급) · 프리장(pre_flow) · VI·급등(intraday_alerts) ·
               매수(「매수」 판 rows 전부) · 초반상승(open_rise). 장외는 평일 09:00~15:40 비어 있어(화면 설명 그대로) 09:06 에는 안 든다.
               관심 · 프리장 · 매수는 시가총액 CAP_MIN_EOK 억원 아래를 뺀다(화면 capBelowMin · 시가총액을 모르면 안 뺀다)
               **화면과 이 파일 두 곳에 셈이 있다** — 값 한 곳으로 모으는 것은 개발1 카드 「관심 아래 칩 룰 값 한 곳」(화면이 서버를 받는 쪽)
    차례       칩 수 많은 순 → 초반상승(첫 5분봉 시가 대비 % · rise) 높은 순 → 시가총액 큰 순 — 상위 TOP_N
               (재권님 19:1x 「칩수가 많은순 초반상승이높은순 시총순 이렇게 해서 올려」 · 초반상승에 안 든 종목은 같은 칩 수 안에서 뒤)
               홈 「단타」 칩은 칩 수 → 시가총액이다 — 이 판만 초반상승을 둘째로 둔다
    하위 칩    rows[].subs {칩: [하위]} — VI·급등: VI · 급등 / 매수: ①~④(「매수」 판 tier) / 관심: 든 묶음 이름(자동 묶음 빼고)
    칩 이름    rows[].chips 는 그때 걸린 칩 이름 전부(셈에 안 드는 볼린저 · 현재상승도 적는다 — 시황분석1 「관심 하위의 룰들」)
    매수가     09:06 그때 현재가(buy) — 시세는 fetch_quotes_multi(캐시 먼저 · 30종목씩 묶음)
    값        px{HHMM} — TIMES 각 시각에 끝난 5분봉 종가(DB candles · 그 봉을 끝난 뒤 받았으면) · 없으면 그때 현재가(pxSrc 「now」)
    저장      market.db dt30(날 · 판 JSON) — 쓰기 되는 서버(8765)만 · 한 번 굳힌 날은 다시 안 굳힌다 · DAYS_KEEP 거래일 넘으면 지운다
    주소      GET /api/kis/dt30?day=YYYYMMDD — day 를 빼면 마지막 날 · meta.days 는 남긴 날(최근 먼저)

못 받은 칩은 meta.missing 에 이름으로 남긴다(「0 종목」 과 「못 받음」 을 가른다).
"""
import json
import threading
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
TOP_N = 100                  # 재권님 18:5x 「상위 30개면 소팅에 걸리는게 적을수 있으니 지금 100개까지 늘려놔」
BUY_AT = (9, 6)              # 굳히는 시각 — 재권님 「9시 6분에 배수」
TRACK_FROM = (9, 30)         # 값 적는 첫 시각
TRACK_TO = (14, 0)           # 값 적는 끝 시각 — 「2시까지」
TRACK_STEP = 30              # 분 — 「30분 단위로」
BAR_MIN = 5                  # 5분봉 길이(분)
BUY_LATE = (9, 30)           # 서버가 늦게 떠 이 시각이 지나면 그날은 안 굳힌다(09:06 판이 아니게 되므로)
DAYS_KEEP = 30               # 「30일 추적」
CAP_MIN_EOK = 3000           # 시가총액 문턱(억원) — 화면 RANK_MIN_CAP_EOK 와 같은 값(두 곳 · 위 「화면과 이 파일」)
NOW_RISE_PCT = 3.0           # 「현재상승」 — 시가 대비 %(화면 NOW_RISE_PCT 와 같은 값 · 칩 이름 적기에만 씀)
TICK = 20
OV_CHIPS = ("관심", "프리장", "VI·급등", "장외", "매수", "초반상승", "수급")   # 단타 셈에 드는 칩 — 화면 OV_CHIPS 차례

_SCHEMA = "CREATE TABLE IF NOT EXISTS dt30 (day TEXT PRIMARY KEY, saved_at TEXT, board TEXT NOT NULL)"
_status = {"frozen": None, "error": None}


def _now():
    return datetime.now(KST)


def times():
    """값 적는 시각들 ['0930', '1000', … '1400']."""
    out, m = [], TRACK_FROM[0] * 60 + TRACK_FROM[1]
    while m <= TRACK_TO[0] * 60 + TRACK_TO[1]:
        out.append("%02d%02d" % divmod(m, 60))
        m += TRACK_STEP
    return out


def _six(code):
    code = str(code or "")
    return code if code.isdigit() and len(code) == 6 else None


def chips_now(proxy, cfg):
    """지금 걸린 칩 — ({코드: {이름, 칩 집합}}, 못 받은 칩 이름 목록, 시가총액 {코드: 억원})."""
    import dart, docstore, intraday_alerts, open_rise, pre_flow, signal_watch
    uni = dart.universe_rows(None)
    cap = {r["stock_code"]: r["market_cap"] for r in uni}
    mkt = {r["stock_code"]: r["market"] for r in uni}
    try:                                   # 순위 목록 밖은 KIS 종목 마스터(nxt_pre 가 받아 둔 전 종목 시장 표)로 채운다
        import nxt_pre
        for c, m in list(nxt_pre.MARKET_OF.items()):
            mkt.setdefault(c, str(m).upper())
    except Exception:
        pass
    small = lambda c: cap.get(c) is not None and cap[c] < CAP_MIN_EOK
    hit, missing = {}, []

    def put(code, name, chip, sub=None):
        code = _six(code)
        if code:
            g = hit.setdefault(code, {"name": name or "", "chips": set(), "subs": {}})
            g["chips"].add(chip)
            if sub and sub not in g["subs"].setdefault(chip, []):
                g["subs"][chip].append(sub)
            if not g["name"] and name:
                g["name"] = name

    try:
        doc = docstore.read_doc("watchlist") or {}
        auto = set((doc.get("auto") or {}).keys()) if isinstance(doc.get("auto"), dict) else set()
        grp = [(g.get("name"), set(g.get("codes") or [])) for g in doc.get("groups") or []
               if isinstance(g, dict) and g.get("id") != "auto"]          # 관심 하위 = 그 종목이 든 묶음(자동 묶음은 수급이라 뺀다)
        for it in doc.get("items") or []:
            if isinstance(it, dict):
                c = it.get("code")
                if c in auto:
                    put(c, it.get("name"), "수급")
                elif not small(c):
                    put(c, it.get("name"), "관심")
                    for gn, gc in grp:
                        if c in gc:
                            put(c, it.get("name"), "관심", gn)
    except Exception:
        missing += ["관심", "수급"]
    try:
        pf, _, _ = pre_flow.fetch(proxy, cfg)
        if pf is None:
            missing.append("프리장")
        for r in (pf or {}).get("rows") or []:
            if not small(r.get("code")):
                put(r.get("code"), r.get("name"), "프리장")
    except Exception:
        missing.append("프리장")
    try:
        for it in intraday_alerts.today().get("items") or []:
            put(it.get("code"), it.get("name"), "VI·급등", "VI" if it.get("kind") == "vi" else "급등")
    except Exception:
        missing.append("VI·급등")
    try:
        jd, _ = proxy.fetch_joint_buy(cfg)
        if jd is None:
            missing.append("매수")
        for r in (jd or {}).get("rows") or []:
            if not small(r.get("code")):
                put(r.get("code"), r.get("name"), "매수", "①②③④"[r["tier"] - 1] if r.get("tier") in (1, 2, 3, 4) else None)
    except Exception:
        missing.append("매수")
    try:
        b, _ = open_rise.fetch(proxy)
        if b.get("phase") in ("pending", "nodata"):
            missing.append("초반상승")
        for r in b.get("rows") or []:
            put(r.get("code"), r.get("name"), "초반상승")
            if _six(r.get("code")) and r.get("pct") is not None:
                hit[r["code"]]["rise"] = r["pct"]          # 첫 5분봉 시가 대비 % — 줄 세우기 둘째 열쇠
    except Exception:
        missing.append("초반상승")
    try:
        day = _now().strftime("%Y%m%d")
        for it in signal_watch.today_lows(proxy).get("items") or []:
            if str(it.get("ts", ""))[:8] == day and _six(it.get("code")) in hit:
                hit[it["code"]]["chips"].add("볼린저")      # 셈에 안 듦 — 이름만 적는다
    except Exception:
        pass
    return hit, missing, cap, mkt


def build(proxy, cfg, day):
    """09:06 판 — {day, buyAt, times, rows, meta}."""
    import company_profile
    hit, missing, cap, mkt = chips_now(proxy, cfg)
    ov = {c: g for c, g in hit.items() if g["chips"] & set(OV_CHIPS)}     # 칩 하나라도(18:5x — 화면이 칩을 끄고 켜며 그 안에서 다시 셈)
    prices, _ = proxy.fetch_quotes_multi(cfg, list(ov)) if ov else ({}, {})    # 30종목씩 묶어 부른다 — 한 종목씩이면 수백 건이 몰려 KIS 가 거절했다(18:5x 시험)
    sec = company_profile.sectors()
    rows = []
    for code, g in ov.items():
        p = prices.get(code) or {}
        chips = set(g["chips"])
        if p.get("open") and p.get("price") and (p["price"] / p["open"] - 1) * 100 >= NOW_RISE_PCT:
            chips.add("현재상승")
        n = len(chips & set(OV_CHIPS))
        rows.append({"code": code, "name": g["name"], "market": mkt.get(code), "cap": cap.get(code), "sector": sec.get(code),
                     "chips": [c for c in OV_CHIPS + ("현재상승", "볼린저") if c in chips], "subs": g["subs"], "n": n,
                     "buy": p.get("price"), "pct": p.get("pct"), "rise": g.get("rise"), "px": {}, "pxSrc": {}})
    rows.sort(key=lambda r: (-r["n"], -(r["rise"] if r["rise"] is not None else -1e9), -(r["cap"] if r["cap"] is not None else -1)))   # 재권님 19:1x
    rows = rows[:TOP_N]
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return {"day": day, "buyAt": "%02d:%02d" % BUY_AT, "times": times(), "rows": rows,
            "meta": {"rebuilt": False, "missing": missing, "candidates": len(ov), "topN": TOP_N, "capMinEok": CAP_MIN_EOK,
                     "order": "칩 수 많은 순 → 초반상승 높은 순 → 시가총액 순",
                     "note": "buy 는 09:06 현재가 · pct 는 그때 전일 종가 대비 등락률 · rise 는 초반상승 % (안 들면 null) · px 는 그 시각에 끝난 5분봉 종가(pxSrc now 면 그때 현재가) · "
                             "market KOSPI · KOSDAQ(순위 목록 · 없으면 KIS 종목 마스터 · 둘 다 없으면 null) · cap 억원 · 장외는 09:06 에 비어 안 셈 · 볼린저 · 현재상승은 칩 이름만(셈에 안 듦)"}}


def _bar_close(proxy, day, code, hhmm):
    """hhmm 에 끝난 5분봉 종가 — DB 에 있고(오늘이면) 그 봉을 끝난 뒤 받았을 때만."""
    m = int(hhmm[:2]) * 60 + int(hhmm[2:])
    ts = day + "%02d%02d" % divmod(m - BAR_MIN, 60)
    if day == proxy._minutes_trade_day():
        fresh = proxy._minutes_fresh_upto(code)
        if fresh is None or fresh < m:
            return None
    with proxy._db_lock, proxy.db_conn() as conn:
        r = conn.execute("SELECT close FROM candles WHERE period = '5m' AND code = ? AND ts = ?", (code, ts)).fetchone()
    return r[0] if r else None


def _load(proxy, day):
    try:
        with proxy.db_conn() as conn:
            got = conn.execute("SELECT board, saved_at FROM dt30 WHERE day = ?", (day,)).fetchone()
    except Exception:
        return None
    return (json.loads(got[0]), got[1]) if got else None


def _store(proxy, b):
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        conn.execute("INSERT OR REPLACE INTO dt30 (day, saved_at, board) VALUES (?,?,?)",
                     (b["day"], _now().strftime("%H:%M:%S"), json.dumps(b, ensure_ascii=False)))
        keep = [d for (d,) in conn.execute("SELECT day FROM dt30 ORDER BY day DESC LIMIT ?", (DAYS_KEEP,))]
        if keep:
            conn.execute("DELETE FROM dt30 WHERE day < ?", (keep[-1],))


NOW_OK_MIN = 10              # 5분봉이 없을 때 현재가로 갈음해도 되는 늦음(분) — 넘으면 그 칸은 「없음」(null)


def track(proxy, cfg, b, hhmm, late):
    """그 시각 값을 적는다 — 5분봉 종가가 없으면 그때 현재가(늦음이 NOW_OK_MIN 분 안일 때만 · 넘으면 null)."""
    need = [r["code"] for r in b["rows"] if hhmm not in r["px"]]
    now_p = {}
    for r in b["rows"]:
        if r["code"] not in need:
            continue
        v = _bar_close(proxy, b["day"], r["code"], hhmm)
        if v is not None:
            r["px"][hhmm], r["pxSrc"][hhmm] = v, "5m"
    left = [r["code"] for r in b["rows"] if hhmm not in r["px"]]
    if left and late > NOW_OK_MIN:
        for r in b["rows"]:
            if hhmm not in r["px"]:
                r["px"][hhmm], r["pxSrc"][hhmm] = None, "none"
    elif left:
        now_p, _ = proxy.fetch_quotes_multi(cfg, left)
        for r in b["rows"]:
            p = (now_p.get(r["code"]) or {}).get("price")
            if hhmm not in r["px"] and p is not None:
                r["px"][hhmm], r["pxSrc"][hhmm] = p, "now"


def days(proxy):
    try:
        with proxy.db_conn() as conn:
            return [d for (d,) in conn.execute("SELECT day FROM dt30 ORDER BY day DESC LIMIT ?", (DAYS_KEEP,))]
    except Exception:
        return []


def board(proxy, day=None):
    """주소 /api/kis/dt30 의 data — 남긴 날만(없으면 None)."""
    ds = days(proxy)
    day = day or (ds[0] if ds else None)
    got = _load(proxy, day) if day else None
    if not got:
        return None
    b, saved = got
    b["meta"]["savedAt"] = saved
    return b


def status():
    return dict(_status, buyAt="%02d:%02d" % BUY_AT, times=times(), daysKeep=DAYS_KEEP)


def start(proxy):
    """쓰는 서버가 뜰 때 한 번 — 평일 BUY_AT 에 굳히고 TIMES 마다 값을 적는다."""
    if not proxy.marketdb.writable():
        return False
    import market_hours

    def loop():
        time.sleep(30)
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = now.hour * 60 + now.minute
                if now.weekday() < 5 and market_hours.today(proxy, day=day, now=now).get("open") is not False:
                    got = _load(proxy, day)
                    if got is None and BUY_AT[0] * 60 + BUY_AT[1] <= hm < BUY_LATE[0] * 60 + BUY_LATE[1] and _status["frozen"] != day:
                        b = build(proxy, proxy.load_secrets(), day)
                        _store(proxy, b)
                        _status.update(frozen=day, error=None)
                        print("  [단타 30] %s 09:06 판 %d종목 굳힘%s" % (day, len(b["rows"]),
                              " · 못 받은 칩 " + " · ".join(b["meta"]["missing"]) if b["meta"]["missing"] else ""), flush=True)
                    elif got is not None:
                        b = got[0]
                        due = [t for t in b["times"] if int(t[:2]) * 60 + int(t[2:]) + 1 <= hm
                               and any(t not in r["px"] for r in b["rows"])]
                        if due:
                            for t in due:
                                track(proxy, proxy.load_secrets(), b, t, hm - int(t[:2]) * 60 - int(t[2:]))
                            _store(proxy, b)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [단타 30] 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="dt30").start()
    return True
