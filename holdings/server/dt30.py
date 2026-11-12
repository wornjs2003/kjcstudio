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
    지금 값    그날 판(closed false)은 주소가 부를 때 rows[].now(현재가) · nowAt · meta.refreshMs(다시 받을 주기 · 서버 값) — 14:00 칸을 다 적으면 closed true 로 굳힘
    값        px{HHMM} — TIMES 각 시각에 끝난 5분봉 종가(DB candles · 그 봉을 끝난 뒤 받았으면) · 없으면 그때 현재가(pxSrc 「now」)
    저장      market.db dt30(날 · 판 JSON) — 쓰기 되는 서버(8765)만 · 한 번 굳힌 날은 다시 안 굳힌다 · DAYS_KEEP 거래일 넘으면 지운다
    주소      GET /api/kis/dt30?day=YYYYMMDD — day 를 빼면 마지막 날 · meta.days 는 남긴 날(최근 먼저)

하락 뺌    전일 종가 대비 등락률(pct)이 DROP_BELOW_PCT 아래인 종목은 판에 안 넣는다 — 재권님 「단타에 하락인 종목은 필요없어」 →
               「거래량 많은 종목중에 하락인건 제외한다는 룰 넣어봐」(11-12) · 09:35 굳히기 전까지 1분마다 다시 셀 때 그때 값으로 넣고 뺀다 ·
               굳힌 뒤 내려간 종목은 그대로 둔다(이미 산 값) · 등락률을 모르면 안 뺀다(못 잼은 하락이 아니다) · 뺀 수는 meta.dropDown
               판에 들었다가 하락으로 빠진 종목은 그날 다시 안 넣는다(meta.out) · 없다가 조건이 맞게 된 종목은 넣는다 —
               재권님 「처음 들었다가 빠지면 제외하고 없다가 값이 적용되는 목록은 넣는다」(11-12 11:3x)

못 받은 칩은 meta.missing 에 이름으로 남긴다(「0 종목」 과 「못 받음」 을 가른다).
"""
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import dart            # 시가총액 문턱(UNIVERSE_MIN_CAP_EOK) 한 곳 — 모듈을 읽을 때 쓴다(dart 는 이 파일을 안 부른다)

KST = timezone(timedelta(hours=9))
TOP_N = 100                  # 재권님 18:5x 「상위 30개면 소팅에 걸리는게 적을수 있으니 지금 100개까지 늘려놔」
BUY_AT = (9, 1)              # 굳히는 시각 — 재권님 「9시 6분에 배수」 → 「9시 5분에 무조건 갱신」(11-12 09:1x) → 「9시 1분에 바로 단타 리스트 뜨도록 … 못가져온 값은 못가져온대로 … 무슨값인지만 인지되도록」(09:2x · 작업우선순위 경유) · 빠진 칩은 meta.missing · 들어오면 patch_late 가 채움
TRACK_FROM = (9, 30)         # 값 적는 첫 시각
TRACK_TO = (14, 0)           # 값 적는 끝 시각 — 「2시까지」
TRACK_STEP = 30              # 분 — 「30분 단위로」
BAR_MIN = 5                  # 5분봉 길이(분)
BUY_LATE = (9, 35)           # 굳히는 시각 — 재권님 「9시 35분에 굳히는걸로」(11-12 09:2x) · BUY_AT 부터 이때까지 판을 다시 세고 이 뒤로는 줄을 안 바꾼다 · 서버가 이 뒤에 뜨면 그날 판은 안 짓는다
DAYS_KEEP = 30               # 「30일 추적」
CAP_MIN_EOK = dart.UNIVERSE_MIN_CAP_EOK   # 시가총액 문턱(억원) — 대상 목록 문턱 그대로(한 곳 · 개념정의 검수 11-12) · 화면 RANK_MIN_CAP_EOK 와 같은 값(두 곳 · 위 「화면과 이 파일」) · 3천억 → 5천억 재권님 「응」(11-12)
NOW_RISE_PCT = 3.0           # 「현재상승」 — 시가 대비 %(화면 NOW_RISE_PCT 와 같은 값 · 칩 이름 적기에만 씀)
DROP_BELOW_PCT = 0.0         # 하락 뺌 — 전일 종가 대비 이 % 아래는 판에 안 넣는다(0 이면 보합은 남긴다 · 재권님 11-12)
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


def chips_now(proxy, cfg, early=True):
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
        doc = docstore.read_doc("watchlist")
        if not isinstance(doc, dict):
            raise ValueError("관심 문서 없음")              # 못 읽음을 0 종목으로 두지 않는다(qa 11-11)
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
        if jd is None or not jd.get("rows"):
            missing.append("매수")
        for r in (jd or {}).get("rows") or []:
            if not small(r.get("code")):
                put(r.get("code"), r.get("name"), "매수", "①②③④"[r["tier"] - 1] if r.get("tier") in (1, 2, 3, 4) else None)
    except Exception:
        missing.append("매수")
    if "매수" in missing and early and early_buy(proxy, cfg, [c for c in hit if not small(c)], put) is not None:
        missing.remove("매수")
        missing.append("매수어림")                     # build 가 meta.early 로 옮긴다 — 못 받은 칩이 아니다
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


EARLY_WORKERS = 6


def early_buy(proxy, cfg, codes, put):
    """「매수」 판이 아직 없을 때(외 · 기 장중 가집계가 09:30 · 10:00 에 처음 나온다) 후보 종목의 외국계 창구 순매수 · 종목 프로그램 순매수가
    둘 다 양수면 「매수」 어림(하위 「어림」)으로 넣는다 — 재권님 「프로그램은 받을수 있지않나? 외국계창구랑」 · 「차트에서 읽고 있잖아」(11-12 09:1x).
    값은 큰 차트 바닥 줄이 읽는 것과 같은 함수(fetch_investor_member 의 foreignFirms.net · _program_net_today) — 새 받는 길을 만들지 않는다.
    매수 판이 서면 patch_late 가 이 어림을 걷고 그 판으로 바꾼다. 넣은 종목 수(못 받으면 None)."""
    from concurrent.futures import ThreadPoolExecutor

    def one(c):
        try:
            m = proxy.fetch_investor_member(cfg, c) or {}
            fn = (m.get("foreignFirms") or {}).get("net")
            pg = proxy._program_net_today(cfg, c)
        except Exception:
            return c, None, None
        return c, fn, pg
    try:
        with ThreadPoolExecutor(EARLY_WORKERS) as ex:
            got = list(ex.map(one, codes))
    except Exception:
        return None
    if codes and all(fn is None and pg is None for _, fn, pg in got):
        return None                                    # 하나도 못 받았다 — 「어림」 으로 두지 않고 못 받은 칩으로 남긴다(qa 11-12 · KIS 몰림 때)
    n = 0
    for c, fn, pg in got:
        if fn is not None and fn > 0 and pg is not None and pg > 0:
            put(c, None, "매수", "어림")
            n += 1
    return n


def build(proxy, cfg, day, skip=()):
    """09:06 판 — {day, buyAt, times, rows, meta}. skip — 그날 판에서 하락으로 빠진 종목(다시 안 넣음)."""
    import company_profile
    hit, missing, cap, mkt = chips_now(proxy, cfg)
    ov = {c: g for c, g in hit.items() if g["chips"] & set(OV_CHIPS)}     # 칩 하나라도(18:5x — 화면이 칩을 끄고 켜며 그 안에서 다시 셈)
    prices, _ = proxy.fetch_quotes_multi(cfg, list(ov)) if ov else ({}, {})    # 30종목씩 묶어 부른다 — 한 종목씩이면 수백 건이 몰려 KIS 가 거절했다(18:5x 시험)
    sec = company_profile.sectors()
    rows, down = [], []
    for code, g in ov.items():
        if code in skip:
            continue                                   # 들었다가 하락으로 빠진 종목 — 그날 다시 안 넣음(재권님 11-12 11:3x)
        p = prices.get(code) or {}
        if p.get("pct") is not None and p["pct"] < DROP_BELOW_PCT:
            down.append(code)                          # 하락 뺌(재권님 11-12) — 모르면 안 뺀다
            continue
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
    return {"day": day, "buyAt": "%02d:%02d" % BUY_AT, "times": times(), "rows": rows, "closed": False,
            "meta": {"rebuilt": False, "missing": [c for c in missing if c != "매수어림"], "candidates": len(ov), "dropDown": len(down), "downCodes": sorted(down), "dropBelowPct": DROP_BELOW_PCT,
                     "early": ["매수"] if "매수어림" in missing else [], "approx": ["매수"] if "매수어림" in missing else [], "topN": TOP_N, "capMinEok": CAP_MIN_EOK,
                     "order": "칩 수 많은 순 → 초반상승 높은 순 → 시가총액 순",
                     "note": "buy 는 굳힌 때(buyAt) 현재가 · pct 는 그때 전일 종가 대비 등락률 · rise 는 초반상승 % (안 들면 null) · px 는 그 시각에 끝난 5분봉 종가(pxSrc now 면 그때 현재가) · "
                             "market KOSPI · KOSDAQ(순위 목록 · 없으면 KIS 종목 마스터 · 둘 다 없으면 null) · cap 억원 · 장외는 09:06 에 비어 안 셈 · 볼린저 · 현재상승은 칩 이름만(셈에 안 듦)"}}


LATE_CHIPS = ("초반상승", "매수")   # 09:06 에 값이 아직 없을 수 있는 칩 — 초반상승은 첫 5분봉이 덜 들어옴 · 매수는 외 · 기 장중 가집계가 09:30 에 처음 나옴
# 재권님 「지금하라고해」(11-12 09:1x · 오늘 판에 두 칩이 빠져 굳음) — 그날 판이 그 칩 없이 굳었으면 값이 나오는 대로 채워 넣고 다시 줄 세운다.
# 초반상승은 09:00 봉이라 09:06 과 같은 값이다. 매수는 채운 시각의 판이라 meta.approx 에 넣고 meta.late 에 시각을 적는다.
# 새로 들어온 종목의 buy 는 09:05 봉 시가(되채우기와 같음 · 없으면 null) · 다른 칩은 채울 때 다시 센 값이다.


def patch_late(proxy, cfg, b):
    """그날 판의 meta.missing 중 LATE_CHIPS 를 값이 나왔으면 채운다. 채운 칩 이름 목록(없으면 빈 목록)."""
    import open_rise
    want = [c for c in LATE_CHIPS if c in (b["meta"].get("missing") or []) + (b["meta"].get("early") or [])]
    if not want:
        return []
    got = {}                                           # 칩 → {코드: (이름, 하위, 초반상승 %)}
    if "초반상승" in want:
        try:
            o, _ = open_rise.fetch(proxy)
            late = _now().hour * 60 + _now().minute >= BUY_LATE[0] * 60 + BUY_LATE[1]
            if o.get("phase") == "done" or (late and o.get("phase") == "pending"):   # 09:30 이 지나도 덜 받았으면 받은 데까지로
                got["초반상승"] = {r["code"]: (r.get("name"), None, r.get("pct")) for r in o.get("rows") or [] if _six(r.get("code"))}
        except Exception:
            pass
    if "매수" in want:
        try:
            jd, _ = proxy.fetch_joint_buy(cfg)
            if jd is not None and jd.get("rows"):
                got["매수"] = {r["code"]: (r.get("name"), "①②③④"[r["tier"] - 1] if r.get("tier") in (1, 2, 3, 4) else None, None)
                              for r in jd["rows"] if _six(r.get("code"))}
        except Exception:
            pass
    if "매수" in want and "매수" not in got and "매수" in (b["meta"].get("missing") or []):
        # 굳힐 때 어림도 못 했던 판(11-12 오늘 판 · 서버가 어림 전 코드였다) — 판 안 종목에 어림을 지금 넣는다
        rows0 = {r["code"]: r for r in b["rows"]}

        def put0(code, name, chip, sub=None):
            r = rows0.get(code)
            if r is not None and chip not in r["chips"]:
                r["chips"].append(chip)
                r["subs"][chip] = [sub] if sub else []
        if early_buy(proxy, cfg, [r["code"] for r in b["rows"] if not (r.get("cap") is not None and r["cap"] < CAP_MIN_EOK)], put0) is not None:
            b["meta"]["missing"] = [c for c in b["meta"]["missing"] if c != "매수"]
            b["meta"]["early"] = sorted(set(b["meta"].get("early") or []) | {"매수"})
            ap = b["meta"].setdefault("approx", [])
            if "매수" not in ap:
                ap.append("매수")
            b["meta"].setdefault("late", {})["매수어림"] = _now().strftime("%H:%M")
            got["매수어림"] = {}
    if not got:
        return []
    # 굳힌 판에 있는 종목에만 칩을 붙인다 — 다시 셀 재료(chips_now)가 필요 없다
    if "매수" in got:                                  # 09:05 어림(하위 「어림」)을 걷고 판 값으로 바꾼다
        for r in b["rows"]:
            if r["subs"].get("매수") == ["어림"]:
                r["subs"].pop("매수", None)
                r["chips"] = [c for c in r["chips"] if c != "매수"]
        b["meta"]["early"] = [c for c in b["meta"].get("early") or [] if c != "매수"]
    rows = {r["code"]: r for r in b["rows"]}
    small = lambda c: rows[c].get("cap") is not None and rows[c]["cap"] < CAP_MIN_EOK
    for chip, m in got.items():
        for code, (name, sub, rise) in m.items():
            r = rows.get(code)
            if r is None or (chip == "매수" and small(code)):                              # 굳힌 판에는 새 종목을 안 넣는다 — 뒤늦게 안 신호로 앞 가격에 산 셈이 되므로(개념정의 덧 11-12)
                continue
            if chip not in r["chips"]:
                r["chips"].append(chip)
            if sub:
                r["subs"].setdefault(chip, [])
                if sub not in r["subs"][chip]:
                    r["subs"][chip].append(sub)
            if rise is not None:
                r["rise"] = rise
    order = OV_CHIPS + ("현재상승", "볼린저")
    for r in rows.values():
        r["chips"] = [c for c in order if c in r["chips"]]
        r["n"] = len(set(r["chips"]) & set(OV_CHIPS))
    out = sorted(rows.values(), key=lambda r: (-r["n"], -(r["rise"] if r["rise"] is not None else -1e9), -(r["cap"] if r["cap"] is not None else -1)))
    b["rows"] = out[:TOP_N]
    for i, r in enumerate(b["rows"]):
        r["rank"] = i + 1
    b["meta"]["missing"] = [c for c in b["meta"]["missing"] if c not in got]
    late = b["meta"].setdefault("late", {})
    for chip in got:
        if chip == "매수어림":
            continue
        late[chip] = _now().strftime("%H:%M")
        if chip == "매수":
            ap = b["meta"].setdefault("approx", [])
            if chip not in ap:
                ap.append(chip)
    b["meta"]["candidates"] = max(b["meta"].get("candidates") or 0, len(rows))
    return list(got)


RESCAN_SEC = 60               # BUY_AT ~ BUY_LATE 동안 판을 다시 세는 간격(초) — 칩 재료(프리장 · 수급 · VI · 매수 어림 …) 캐시 둘레
# 재권님 「궅히지말고 정보가 들어오는대로 개선되게 해줘」 → 「9시 35분에 굳히는걸로」(11-12 09:2x) — 굳히는 시각(BUY_LATE) 전까지는 판을 굳히지 않고
# RESCAN_SEC 마다 칩을 다시 세어 줄을 다시 세운다. 이미 든 종목의 buy 는 처음 든 때 값 그대로 · 새로 든 종목은 든 때 현재가(rows[].buyAt).
# BUY_LATE 뒤로는 줄을 바꾸지 않고 늦게 나온 칩(patch_late)만 채운다 — 30분 값을 적는 동안 종목이 바뀌면 그 칸을 견줄 수 없다.
# 09:30 칸은 굳히기 전에 오므로 그 뒤에 든 종목은 그 칸을 09:30 에 끝난 5분봉 종가로 채운다(track).


def refresh(proxy, cfg, b):
    """그날 판을 지금 들어온 값으로 다시 세운다(종목 · 칩 · 순위). 바뀐 줄 수."""
    out = set(b["meta"].get("out") or [])
    nb = build(proxy, cfg, b["day"], skip=out)
    old = {r["code"]: r for r in b["rows"]}
    out |= set(old) & set(nb["meta"].get("downCodes") or [])     # 판에 있다가 이번에 하락으로 빠진 종목 — 그날 다시 안 넣음
    hm = _now().strftime("%H:%M")
    changed = 0
    for r in nb["rows"]:
        o = old.get(r["code"])
        if o is not None:
            r["buy"], r["pct"], r["px"], r["pxSrc"] = o["buy"], o["pct"], o["px"], o["pxSrc"]
            r["buyAt"] = o.get("buyAt") or b.get("buyAt")
            if o.get("rank") != r["rank"] or o.get("chips") != r["chips"]:
                changed += 1
        else:
            r["buyAt"] = hm
            changed += 1
    changed += len(set(old) - {r["code"] for r in nb["rows"]})
    b["rows"] = nb["rows"]
    late = b["meta"].get("late") or {}
    b["meta"] = dict(nb["meta"], late=late, rescanAt=hm, out=sorted(out))
    return changed


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


# ---------------------------------------------------------------- 지난 날 되채우기
# 재권님 「관심을 제외하고 지난 20일의 정보가 필요해 가져올수 있는곳 찾아서 가져와줘」(18:0x) → 「지난 30일 데이터도 적용해서 넣어놔」(19:3x).
# 개발 DB 에 쌓인 것으로 그날 09:06 판을 다시 센다 — VI 만 KIS 에 묻는다. 다시 센 날은 meta.rebuilt true · missing(못 센 칩) · approx(어림한 칩).
#   관심       뺀다(재권님)
#   수급       앞 거래일 auto_watch_day 값에 **지금** 수급 룰(auto_watch.compute · 문서 rules.volsurge)을 댄다 — 그날 룰이 달랐을 수 있어 어림
#   프리장     그날 08:00~08:50 5분봉 거래대금(종가 × 거래량) 상위 pre_flow.TOP_N — 프로그램 순매수 기록이 없어 어림
#   VI·급등    급등 — 09:00 · 09:05 봉 고가가 앞 거래일 종가보다 intraday_alerts.SURGE_PCT % 이상 · VI — KIS 「VI 현황」(날짜 · 종목) 에서 09:00~09:06 발동
#              (VI_PROBE_PCT % 넘게 오른 종목만 묻는다 · QUIET 밖에서만 돈다)
#   매수       앞 거래일 확정치(investor_daily) 외국인 · 기관 둘 다 순매수인 종목 중 합 상위 JOINT_TOP — 장중 가집계가 없어 어림 · 하위 칸 없음
#   초반상승   09:00 봉 (종가 − 시가) ÷ 시가 ≥ open_rise.RISE_PCT · 시가총액 open_rise.MIN_CAP_EOK 이상(라이브와 같은 셈)
#   장외       09:06 에는 비어 있다(라이브와 같다)
#   볼린저     그날 09:06 전에 보낸 바닥 신호(signal_sent) — 칩 이름만
#   매수가     09:05 봉 시가(09:06 값에 가장 가까운 쌓인 값) · pct 는 앞 거래일 종가 대비 · 현재상승은 그 값이 09:00 시가보다 NOW_RISE_PCT 이상
#   시가총액 · 섹터 · 시장은 지금 값이다(그날 값 기록이 없다)
# 5분봉이 쌓인 종목은 순위 목록(코스피 200 · 코스닥 150) 둘레뿐이다 — 그 밖 종목은 칩에 못 든다
BACKFILL_DAYS = DAYS_KEEP     # 되채울 거래일 수 — 「지난 30일」
JOINT_TOP = 30                # 「매수」 어림 — 외 · 기 순매수 합 상위 몇
VI_PROBE_PCT = 3.0            # 지난 날 VI 를 KIS 에 물을 종목 — 09:00 · 09:05 봉 고가가 앞 거래일 종가보다 이 % 이상(동적 VI 가장 낮은 문턱 · 코스피200 3%)
QUIET = ((7, 30), (20, 10))   # 되채우기(VI 를 KIS 에 묻는다)를 안 하는 때 — 장 전 · 장중 · 넥장(20:00)까지 KIS 몫을 안 쓴다
VI_WORKERS = 6                # VI 를 겹쳐 묻는 수
# 서버가 뜨면 QUIET 와 상관없이 이번 주(월요일부터 어제까지) 거래일을 먼저 채운다 — 재권님 「어제랑 어그제라도 먼저 넣어노라고해」 → 「이번주꺼만 넣어줘」(11-12 08:4x) · 하루 VI 묻기 150번 남짓 · 사본 DB 로 두 날 65초
RECENT_SKIP = ((8, 59), (9, 3))  # 그래도 이때는 미룬다 — BUY_AT 굳힘이 밀리지 않게


def _trade_days(proxy, before, n):
    with proxy.db_conn() as conn:
        return [d for (d,) in conn.execute(
            "SELECT DISTINCT day FROM auto_watch_day WHERE day < ? ORDER BY day DESC LIMIT ?", (before, n + 1))]


def rebuild(proxy, day, prev, cfg=None):
    """day 의 09:06 판을 쌓인 값으로 다시 센다(prev = 앞 거래일). 5분봉이 없으면 None. cfg 를 주면 VI 를 KIS 에서 받는다."""
    import auto_watch, company_profile, dart, intraday_alerts, open_rise, pre_flow
    uni = dart.universe_rows(None)
    cap = {r["stock_code"]: r["market_cap"] for r in uni}
    mkt = {r["stock_code"]: r["market"] for r in uni}
    small = lambda c: cap.get(c) is not None and cap[c] < CAP_MIN_EOK
    with proxy.db_conn() as conn:
        bars = {}
        for code, ts, o, h, c, v in conn.execute(
                "SELECT code, ts, open, high, close, volume FROM candles WHERE period = '5m' AND ts >= ? AND ts <= ?",
                (day + "0800", day + "1400")):
            bars.setdefault(code, {})[ts[8:12]] = (o, h, c, v)
        if not any("0900" in b for b in bars.values()):
            return None
        pv = {r[0]: r for r in conn.execute("SELECT code, name, close, pct, vol FROM auto_watch_day WHERE day = ?", (prev,))}
        inv = conn.execute("SELECT code, row FROM investor_daily WHERE date = ?", (prev,)).fetchall()
        bb = [r[0] for r in conn.execute("SELECT DISTINCT code FROM signal_sent WHERE day = ? AND ts <= ?",
                                         (day, int(day + "0906")))]
    names = {c: (r[1] or "") for c, r in pv.items()}
    names.update({r["stock_code"]: r["name"] for r in uni})
    hit, missing, approx = {}, ["관심"] + ([] if cfg else ["VI"]), ["수급", "프리장", "매수"]

    def put(code, chip, sub=None, **kw):
        g = hit.setdefault(code, {"name": names.get(code, ""), "chips": set(), "subs": {}})
        g["chips"].add(chip)
        g.update(kw)
        if sub and sub not in g["subs"].setdefault(chip, []):
            g["subs"][chip].append(sub)

    try:                                                   # 수급 — 앞 거래일 값에 지금 룰
        live = {"day": prev, "frac": 1, "at": "", "got": {c: {"name": r[1], "close": r[2], "pct": r[3], "vol": r[4]} for c, r in pv.items()}}
        res = auto_watch.compute(proxy, live=live)
        if not res.get("ready"):
            raise ValueError("수급 룰 못 읽음")             # 룰을 못 읽으면 「없음」 이 아니라 「못 셈」
        for r in res.get("picked") or []:
            put(r["code"], "수급")
    except Exception:
        missing.append("수급")
    amt = {c: sum((b[2] or 0) * (b[3] or 0) for hm, b in d.items() if "0800" <= hm <= "0850") for c, d in bars.items()}
    for c in sorted([c for c, a in amt.items() if a > 0 and not small(c)], key=lambda c: -amt[c])[:pre_flow.TOP_N]:
        put(c, "프리장")
    for c, d in bars.items():                              # 급등
        base = (pv.get(c) or (None, None, None))[2]
        hi = max([d[hm][1] for hm in ("0900", "0905") if hm in d and d[hm][1]] or [0])
        if base and hi and (hi / base - 1) * 100 >= intraday_alerts.SURGE_PCT:
            put(c, "VI·급등", "급등")
    if cfg:                                                # VI — KIS 「VI 현황」 에 날짜 · 종목을 넣으면 그 종목의 그날 VI(최근 것부터 30건)가 온다(19:4x 잼)
        vt = "%02d%02d00" % BUY_AT
        probe = []
        for c, d in bars.items():
            base = (pv.get(c) or (None, None, None))[2]
            hi = max([d[hm][1] for hm in ("0900", "0905") if hm in d and d[hm][1]] or [0])
            if base and hi and (hi / base - 1) * 100 >= VI_PROBE_PCT:
                probe.append(c)                        # 09:06 까지 VI_PROBE_PCT % 도 안 오른 종목은 묻지 않는다(상승 VI 문턱 아래)

        def ask(c):
            return c, proxy.kis_get(cfg, intraday_alerts.VI_PATH,
                                    {"FID_DIV_CLS_CODE": "1", "FID_COND_SCR_DIV_CODE": "20139", "FID_MRKT_CLS_CODE": "0",
                                     "FID_INPUT_ISCD": c, "FID_RANK_SORT_CLS_CODE": "0", "FID_INPUT_DATE_1": day,
                                     "FID_TRGT_CLS_CODE": "", "FID_TRGT_EXLS_CLS_CODE": ""}, intraday_alerts.VI_TR).get("output") or []

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=VI_WORKERS) as ex:      # 한 건 왕복이 1초 남짓이라 겹쳐 묻는다 — 초당 한도는 kis_get 이 지킨다
            for fut in [ex.submit(ask, c) for c in probe]:
                try:
                    c, out = fut.result()
                except Exception:
                    if "VI" not in missing:
                        missing.append("VI")
                    continue
                if any(r.get("bsop_date") == day and "090000" <= str(r.get("cntg_vi_hour") or "") <= vt for r in out):
                    put(c, "VI·급등", "VI")
    jb = []
    for c, row in inv:                                     # 매수 어림
        try:
            j = json.loads(row)
            f, i = j["foreign"]["netAmt"], j["inst"]["netAmt"]
        except (ValueError, KeyError, TypeError):
            continue
        if f and i and f > 0 and i > 0 and not small(c):
            jb.append((f + i, c))
    for _, c in sorted(jb, reverse=True)[:JOINT_TOP]:
        put(c, "매수")
    for c, d in bars.items():                              # 초반상승
        b = d.get("0900")
        cp = cap.get(c)
        if b and b[0] and b[2] is not None and cp is not None and cp >= open_rise.MIN_CAP_EOK:
            pct = (b[2] - b[0]) / b[0] * 100
            if pct >= open_rise.RISE_PCT:
                put(c, "초반상승", rise=round(pct, 2))
    for c in bb:
        if c in hit:
            hit[c]["chips"].add("볼린저")
    sec = company_profile.sectors()
    rows, down = [], 0
    for code, g in hit.items():
        if not g["chips"] & set(OV_CHIPS):
            continue
        d = bars.get(code) or {}
        buy = (d.get("0905") or (None,))[0]
        base = (pv.get(code) or (None, None, None))[2]
        if buy and base and (buy / base - 1) * 100 < DROP_BELOW_PCT:
            down += 1                                  # 하락 뺌 — 09:05 봉 시가가 앞 거래일 종가 아래
            continue
        o9 = (d.get("0900") or (None,))[0]
        chips = set(g["chips"])
        if buy and o9 and (buy / o9 - 1) * 100 >= NOW_RISE_PCT:
            chips.add("현재상승")
        px, src = {}, {}
        for t in times():
            m = int(t[:2]) * 60 + int(t[2:]) - BAR_MIN
            b = d.get("%02d%02d" % divmod(m, 60))
            px[t], src[t] = (b[2], "5m") if b and b[2] is not None else (None, "none")
        rows.append({"code": code, "name": g["name"], "market": mkt.get(code), "cap": cap.get(code), "sector": sec.get(code),
                     "chips": [c for c in OV_CHIPS + ("현재상승", "볼린저") if c in chips], "subs": g["subs"],
                     "n": len(chips & set(OV_CHIPS)), "buy": buy,
                     "pct": round((buy / base - 1) * 100, 2) if buy and base else None, "rise": g.get("rise"),
                     "px": px, "pxSrc": src})
    rows.sort(key=lambda r: (-r["n"], -(r["rise"] if r["rise"] is not None else -1e9), -(r["cap"] if r["cap"] is not None else -1)))
    rows = rows[:TOP_N]
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return {"day": day, "buyAt": "%02d:%02d" % BUY_AT, "times": times(), "rows": rows, "closed": True,
            "meta": {"rebuilt": True, "missing": missing, "approx": approx, "prevDay": prev, "candidates": len(hit), "topN": TOP_N, "dropDown": down, "dropBelowPct": DROP_BELOW_PCT,
                     "capMinEok": CAP_MIN_EOK, "order": "칩 수 많은 순 → 초반상승 높은 순 → 시가총액 순",
                     "note": "쌓인 값으로 다시 셈(VI 만 KIS) · 관심 뺌 · 수급 · 프리장 · 매수는 어림(dt30.py 「지난 날 되채우기」) · "
                             "buy 는 09:05 봉 시가 · 시가총액 · 섹터 · 시장은 지금 값"}}


def backfill(proxy, today, limit=BACKFILL_DAYS, since=None):
    """today 앞 limit 거래일 중 판이 없는 날을 다시 세어 남긴다(라이브로 굳힌 날은 안 건드린다). 남긴 날 수."""
    ds = _trade_days(proxy, today, limit)
    have = set(days(proxy))
    n = 0
    cfg = proxy.load_secrets()
    for i, d in enumerate(ds[:limit]):
        if d in have or i + 1 >= len(ds) or (since and d < since):
            continue
        b = rebuild(proxy, d, ds[i + 1], cfg)
        if b and b["rows"]:
            _store(proxy, b)
            n += 1
    return n


def days(proxy):
    try:
        with proxy.db_conn() as conn:
            return [d for (d,) in conn.execute("SELECT day FROM dt30 ORDER BY day DESC LIMIT ?", (DAYS_KEEP,))]
    except Exception:
        return []


def board(proxy, day=None, cfg=None):
    """주소 /api/kis/dt30 의 data — 남긴 날만(없으면 None). 안 끝난 그날 판이면 rows[].now · nowAt 을 붙인다(cfg 를 줄 때)."""
    ds = days(proxy)
    day = day or (ds[0] if ds else None)
    got = _load(proxy, day) if day else None
    if not got:
        return None
    b, saved = got
    b["meta"]["savedAt"] = saved
    b.setdefault("closed", True)                       # 옛 판(closed 칸 전) · 되채운 날은 끝난 판
    b["meta"]["refreshMs"] = None if b["closed"] else proxy.PRICE_CACHE_TTL * 1000
    if not b["closed"] and cfg is not None:
        # 그날 판은 14:00 마지막 칸 전까지 지금 값을 붙인다 — 재권님 「그날은 변동에 맞춰서 실시간으로 적용되야 하고 그날 2시가 지나면 값이 저장되도록」(19:3x)
        # 다시 받을 주기는 서버 값(refreshMs · 시세 캐시와 같은 PRICE_CACHE_TTL) — 화면은 그 값으로 돈다 · 시세는 그 나이 안이면 캐시
        q, _ = proxy.fetch_quotes_multi(cfg, [r["code"] for r in b["rows"]], max_age=proxy.PRICE_CACHE_TTL)
        for r in b["rows"]:
            r["now"] = (q.get(r["code"]) or {}).get("price")
        b["nowAt"] = _now().strftime("%H:%M:%S")
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
        filled = recent = None
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = now.hour * 60 + now.minute
                if recent != day and not (RECENT_SKIP[0][0] * 60 + RECENT_SKIP[0][1] <= hm < RECENT_SKIP[1][0] * 60 + RECENT_SKIP[1][1]):
                    recent = day
                    n = backfill(proxy, day, BACKFILL_DAYS, since=(now - timedelta(days=now.weekday())).strftime("%Y%m%d"))
                    if n:
                        print("  [단타 30] 이번 주 %d일 먼저 다시 세어 남김" % n, flush=True)
                if filled != day and not (QUIET[0][0] * 60 + QUIET[0][1] <= hm < QUIET[1][0] * 60 + QUIET[1][1]):
                    filled = day                 # 멈춰도 그날은 다시 안 돈다(20초마다 무거운 셈을 되풀이하지 않게)
                    n = backfill(proxy, day)
                    if n:
                        print("  [단타 30] 지난 날 %d일 다시 세어 남김" % n, flush=True)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [단타 30] 되채우기 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
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
                        print("  [단타 30] %s %02d:%02d 판 %d종목 굳힘%s" % (day, BUY_AT[0], BUY_AT[1], len(b["rows"]),
                              " · 못 받은 칩 " + " · ".join(b["meta"]["missing"]) if b["meta"]["missing"] else ""), flush=True)
                    elif got is not None:
                        b = got[0]
                        was = bool(b.get("closed"))
                        due = [t for t in b["times"] if int(t[:2]) * 60 + int(t[2:]) + 1 <= hm
                               and any(t not in r["px"] for r in b["rows"])]
                        filled_late = []
                        if not b.get("closed") and hm < BUY_LATE[0] * 60 + BUY_LATE[1]:
                            if time.time() - _status.get("rescan", 0) >= RESCAN_SEC:
                                _status["rescan"] = time.time()
                                if refresh(proxy, proxy.load_secrets(), b):
                                    filled_late = ["다시 셈"]
                        elif not b.get("closed"):
                            filled_late = patch_late(proxy, proxy.load_secrets(), b)
                        if filled_late and filled_late != ["다시 셈"]:
                            print("  [단타 30] %s 판에 늦게 나온 칩 채움 — %s" % (day, " · ".join(filled_late)), flush=True)
                        if due:
                            for t in due:
                                track(proxy, proxy.load_secrets(), b, t, hm - int(t[:2]) * 60 - int(t[2:]))
                        if not b.get("closed") and all(t in r["px"] for t in b["times"] for r in b["rows"]):
                            b["closed"] = True             # 14:00 마지막 칸까지 적었다 — 그날 판을 굳힌다(그 뒤 now 안 붙음)
                            for r in b["rows"]:
                                r.pop("now", None)
                        if due or filled_late or b.get("closed") and not was:
                            _store(proxy, b)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [단타 30] 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="dt30").start()
    return True
