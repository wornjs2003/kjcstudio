# -*- coding: utf-8 -*-
"""등락 상위와 걸린 필터 — 지난 거래일 판을 다시 세어 채운다 (2026-11-11).

재권님 — 「개발1한테 데이터 다 받았어?」(시황분석1 경유) → 「빈칸되는거 받아올수있는지 증권사로 체크해」 →
「관심을 제외하고 전부 받아서 시황분석이 데이터 만들수 있게 준비해놔」(개발1 창 19:4x).

day_top 은 11-11 부터 날마다 그날 판을 남긴다. 그 앞 FILL_DAYS 거래일을 쌓인 재료 + KIS 지난 날 조회로 **다시 세어**
같은 모양(rows · filterStats · meta)으로 day_top 표에 넣는다. 이미 남긴 날(그날 판)은 덮지 않는다.

    대상 · 값   day_top.build 와 같다 — auto_watch_day 그날 판 중 시가총액 MIN_CAP_EOK 억 이상. 시가총액은 **지금** 감시 목록 값이다
               (지난 날 시가총액은 안 쌓았다 — meta.capNow)
    필터(다시 셈 · 시각은 셀 수 있을 때만)
      VI           KIS VI 현황(inquire-vi-status)에 종목 · 날짜를 넣어 그날 정규장(intraday_alerts.SESSION) 발동 — 처음 시각.
                   시장 전체로 물으면 그날 마지막 30건만 와서(11-11 19:40 잼) 종목마다 묻는다
      급등         그날 정규장 5분봉 고가 ÷ 앞 날 KRX 종가 − 1 ≥ intraday_alerts.SURGE_PCT — 처음 넘은 봉 시각.
                   정규장 5분봉이 없으면 일봉(D) 고가로 보고 시각은 빈칸
      초반상승     그날 정규장 첫 5분봉(market_hours 보통 날 여는 시각) 종가 ÷ 시가 − 1 ≥ open_rise.RISE_PCT
      프리장       프리마켓(pre_flow.PRE_OPEN~PRE_CLOSE) 5분봉 거래대금(종가 × 거래량 합) 상위 pre_flow.TOP_N 중 넥스트레이드 프로그램 순매수 > 0 —
                   지난 날 프로그램은 넥장 하루 합(프리 + 애프터)으로만 온다(KIS 프로그램 일별 NX · 11-11 잼) → 프리장 몫이 아님 · meta.approx
      볼린저       signal_sent(kind low) 그날 줄 중 그날 판을 남기는 때(day_top.SAVE_AT) 앞 — 그 봉 시각
      매수①~④     kis_proxy.joint_tier — 후보는 외국인 · 기관 순매수 금액 상위 JOINT_LIST 중 한쪽에라도 든 종목(목록 밖 쪽은 모름 — 그날 판과 같다).
                   외국인 · 기관 · 연기금은 investor_daily 확정치(연기금 = instDetail.fund), 프로그램은 KIS 프로그램 일별(J · 한 번에 30거래일 · 둘 다 살 때만).
                   그날 판은 시장 전체 순위 목록(가집계)이고 여기는 대상(5천억 이상) 안 확정치라 다를 수 있고 처음 잡힌 시각이 없다 · meta.approx
      수급         지금 룰(auto_watch.rules · volsurge 의 prevPct · volMult) — 그날 등락률 · 거래량 ÷ 앞 20거래일 평균(auto_watch_day)
      거래량전날2배 auto_watch_day 그날 ÷ 앞 날 ≥ day_top.VOL_PREV_X
      단타         day_top.OV_FROM 중 둘 이상(관심 없이)
    못 셈        관심 — 그날 하트 목록이 남아 있지 않다(증권사에도 없다) → meta.missing
    빠진 5분봉   프리마켓 · 첫 봉 자리에 5분봉이 없는 종목은 KIS 지난 날 분봉(FHKST03010230)을 09:05 에서 한 번(120분 · 07:06~09:05)
                받아 5분봉으로 저장한다(kis_proxy.save_candles · 그 범위 안 다섯 분이 다 든 칸만)
    언제         쓰는 서버(8765)만 · 장이 쉬는 때(평일 FILL_FROM 뒤 · FILL_UNTIL 전 · 주말) · 하루씩 최근 날부터 · 남긴 날은 건너뜀
    표시         meta.rebuilt true · missing ["관심"] · approx {칩: 까닭} · capNow true · calls(이 날 KIS 부른 수)
"""
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import day_top

KST = timezone(timedelta(hours=9))

FILL_DAYS = 20                  # 되채울 거래일 — 재권님 「지난 20일」(시황분석1 18:0x)
FILL_FROM = (20, 30)            # 평일 이 뒤 — 넥장(20:00) · 저녁 받기가 끝난 뒤
FILL_UNTIL = (7, 0)             # 평일 이 전
VOL_AVG_DAYS = 20               # 수급 「20일 평균」(auto_watch.AVG_DAYS 와 같은 뜻)
CALL_GAP = 0.12                 # KIS 부르기 사이 쉼(초) — 예산은 kis_get 이 지키고, 다른 받기에 비켜선다
PRE_HOUR = "090500"
JOINT_LIST = 30                 # 「매수」 후보 — 외국인 · 기관 순매수 금액 상위 몇씩(그날 판의 순위 목록 30줄과 같은 뜻 · 여기서는 대상 안에서 셈)             # 빠진 5분봉 — 이 시각에서 120분 거슬러 한 번

_status = {"state": "안 돎", "done": [], "error": None, "at": None}
_prog_cache = {}                # code -> {날: 프로그램 순매수 금액} — 한 바퀴 동안
_failed = set()                 # 짓다 멈춘 날 — 서버가 다시 뜰 때까지 다시 안 묻는다(KIS 를 되풀이해 부르지 않게)


def status():
    return dict(_status, failed=sorted(_failed), fillDays=FILL_DAYS, window="평일 %02d:%02d~다음 날 %02d:%02d · 주말" % (FILL_FROM + FILL_UNTIL))


def _idle(now):
    hm = (now.hour, now.minute)
    return now.weekday() >= 5 or hm >= FILL_FROM or hm < FILL_UNTIL


def _hm(s):
    s = str(s or "").zfill(6)
    return "%s:%s" % (s[0:2], s[2:4])


def targets(proxy):
    """되채울 날 — auto_watch_day 에 있는 거래일 중 day_top 이 처음 남긴 날 앞 FILL_DAYS 개(최근 먼저) · 이미 남긴 날 뺌."""
    with proxy.db_conn() as conn:
        saved = {d for (d,) in conn.execute("SELECT day FROM day_top")} if _has_table(conn) else set()
        first = min(saved) if saved else datetime.now(KST).strftime("%Y%m%d")
        cand = [d for (d,) in conn.execute("SELECT DISTINCT day FROM auto_watch_day WHERE day < ? ORDER BY day DESC LIMIT ?",
                                           (first, FILL_DAYS))]
    return [d for d in cand if d not in saved]


def _has_table(conn):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='day_top'").fetchone() is not None


def _kis(proxy, path, params, tr, calls):
    calls[0] += 1
    time.sleep(CALL_GAP)
    return proxy.kis_get(proxy.load_secrets(), path, params, tr)


def _vi(proxy, code, day, calls):
    """그날 정규장 VI 처음 시각("HH:MM") · 없으면 None · 못 받으면 False."""
    import intraday_alerts as ia
    try:
        d = _kis(proxy, ia.VI_PATH, {"FID_DIV_CLS_CODE": "0", "FID_COND_SCR_DIV_CODE": "20139", "FID_MRKT_CLS_CODE": "0",
                                     "FID_INPUT_ISCD": code, "FID_RANK_SORT_CLS_CODE": "0", "FID_INPUT_DATE_1": day,
                                     "FID_TRGT_CLS_CODE": "", "FID_TRGT_EXLS_CLS_CODE": ""}, ia.VI_TR, calls)
    except Exception:
        return False
    hits = []
    for r in d.get("output") or []:
        if r.get("bsop_date") != day or r.get("mksc_shrn_iscd") != code:
            continue
        t = str(r.get("cntg_vi_hour") or "").zfill(6)
        m = int(t[:2]) * 60 + int(t[2:4])
        if ia.SESSION_FROM <= m < ia.SESSION_TO:
            hits.append(t)
    return _hm(min(hits)) if hits else None


def _program(proxy, code, day, calls, div="J"):
    """그날 프로그램 순매수 금액(원) · 모르면 None — div J 거래소 · NX 넥스트레이드(그날 넥장 전체 합). 한 번에 30거래일이 와서 종목마다 들고 있는다."""
    key = (code, div)
    got = _prog_cache.get(key)
    if got is None or (day not in got and got and min(got) > day):
        try:
            d = _kis(proxy, "/uapi/domestic-stock/v1/quotations/program-trade-by-stock-daily",
                     {"FID_COND_MRKT_DIV_CODE": div, "FID_INPUT_ISCD": code, "FID_INPUT_DATE_1": day}, "FHPPG04650201", calls)
        except Exception:
            return None
        got = dict(got or {})
        for r in d.get("output") or []:
            try:
                got[r["stck_bsop_date"]] = int(r.get("whol_smtn_ntby_tr_pbmn"))
            except (KeyError, TypeError, ValueError):
                pass
        _prog_cache[key] = got
    return got.get(day)


def _fill_5m(proxy, code, day, calls):
    """프리마켓 · 첫 봉 자리 5분봉이 없으면 09:05 에서 120분 한 번 받아 저장 → 저장한 봉 수 · 못 받으면 0."""
    try:
        calls[0] += 1
        time.sleep(CALL_GAP)
        rows = [b for b in proxy._kr_past_chunk(proxy.load_secrets(), code, day, PRE_HOUR) if b["ts"][:8] == day]
    except Exception:
        return 0
    if not rows:
        return 0
    first = min(int(b["ts"][8:10]) * 60 + int(b["ts"][10:12]) for b in rows)
    bars = [b for b in proxy.aggregate_minutes(rows, 5) if int(b["ts"][8:10]) * 60 + int(b["ts"][10:12]) >= first
            and int(b["ts"][8:10]) * 60 + int(b["ts"][10:12]) + 4 <= int(PRE_HOUR[:2]) * 60 + int(PRE_HOUR[2:4])]
    return proxy.save_candles(code, "5m", bars) if bars and proxy.marketdb.writable() else 0


def build(proxy, day, kis=True):
    """지난 날 판 — day_top.build 와 같은 모양 + meta.rebuilt. kis=False 면 KIS 를 안 부른다(시험 · VI · 프로그램 · 빠진 봉은 「못 셈」)."""
    import dart, company_profile, intraday_alerts as ia, open_rise, pre_flow, market_hours, auto_watch
    calls = [0]
    with proxy.db_conn() as conn:
        today = {r[0]: r for r in conn.execute("SELECT code, name, idx, close, pct, vol FROM auto_watch_day WHERE day = ?", (day,))}
        if not today:
            return None
        back = [d for (d,) in conn.execute("SELECT DISTINCT day FROM auto_watch_day WHERE day < ? ORDER BY day DESC LIMIT ?",
                                           (day, VOL_AVG_DAYS))]
        pd = back[0] if back else None
        hist = {}
        if back:
            q = ",".join("?" * len(back))
            for code, d, close, vol in conn.execute("SELECT code, day, close, vol FROM auto_watch_day WHERE day IN (%s)" % q, back):
                hist.setdefault(code, {})[d] = (close, vol)
        lows = conn.execute("SELECT code, MIN(ts) FROM signal_sent WHERE kind = 'low' AND ts >= ? AND ts < ? GROUP BY code",
                            (int(day + "0000"), int(day + "%02d%02d" % day_top.SAVE_AT))).fetchall()
        # 그날 봉만(day 칸은 보낸 날이라 앞 날 저녁 봉이 섞인다 · 그날 판도 봉 날짜로 거른다) · 그날 판을 남기는 때 앞까지
        inv = {}
        for code, row in conn.execute("SELECT code, row FROM investor_daily WHERE date = ?", (day,)):
            try:
                inv[code] = json.loads(row)
            except ValueError:
                pass
    cap = {r["stock_code"]: r["market_cap"] for r in dart.universe_rows(None)}
    sec = company_profile.sectors()
    uni = [c for c, r in today.items() if r[4] is not None and cap.get(c) is not None and cap[c] >= day_top.MIN_CAP_EOK]

    t = market_hours.today(proxy, day=day)
    open_hm = t["usual"]["reg"][0]
    pre_from = "%02d%02d" % pre_flow.PRE_OPEN
    pre_to = "%02d%02d" % pre_flow.PRE_CLOSE

    def bars_of(codes):
        out = {}
        if not codes:
            return out
        with proxy.db_conn() as conn:
            q = ",".join("?" * len(codes))
            for code, ts, o, h, c, v in conn.execute(
                    "SELECT code, ts, open, high, close, volume FROM candles WHERE period = '5m' AND ts >= ? AND ts < ? AND code IN (%s)" % q,
                    [day + "0000", day + "9999"] + codes):
                out.setdefault(code, []).append((ts[8:12], o, h, c, v))
        return out

    bars = bars_of(uni)
    filled = 0
    if kis:
        miss = [c for c in uni if not any(b[0] == open_hm for b in bars.get(c, []))]
        for c in miss:
            filled += _fill_5m(proxy, c, day, calls)
        if miss:
            bars.update(bars_of(miss))
    with proxy.db_conn() as conn:
        dhigh = dict(conn.execute("SELECT code, high FROM candles WHERE period = 'D' AND ts = ?", (day,)))

    hit = {}

    def put(code, name, tm=""):
        f = hit.setdefault(code, {})
        if name not in f or (tm and (not f[name] or tm < f[name])):
            f[name] = tm

    no_bar = 0
    pre_amt = {}
    for c in uni:
        bs = sorted(bars.get(c, []))
        first = next((b for b in bs if b[0] == open_hm), None)
        if first is None:
            no_bar += 1
        elif first[1] and first[3] is not None and (first[3] - first[1]) / first[1] * 100 >= open_rise.RISE_PCT:
            put(c, "초반상승", "%s:%02d" % (open_hm[:2], int(open_hm[2:]) + open_rise.BAR_MIN))
        prev_close = (hist.get(c, {}).get(pd) or (None,))[0] if pd else None
        if prev_close:
            lim = prev_close * (1 + ia.SURGE_PCT / 100)
            reg = [b for b in bs if ia.SESSION_FROM <= int(b[0][:2]) * 60 + int(b[0][2:]) < ia.SESSION_TO]
            up = next((b for b in reg if b[2] is not None and b[2] >= lim), None)
            if up:
                put(c, "급등", "%s:%s" % (up[0][:2], up[0][2:]))
            elif not reg and dhigh.get(c) and dhigh[c] >= lim:
                put(c, "급등", "")
        amt = sum((b[3] or 0) * (b[4] or 0) for b in bs if pre_from <= b[0] < pre_to)
        if amt > 0:
            pre_amt[c] = amt
    for c in sorted(pre_amt, key=lambda x: -pre_amt[x])[:pre_flow.TOP_N]:
        pg = _program(proxy, c, day, calls, "NX") if kis else None
        if pg is not None and pg > 0:
            put(c, "프리장", "%02d:%02d" % pre_flow.PRE_CLOSE)      # 그날 판은 굳힌 때(08:50) — 같게

    for code, ts in lows:
        if code in today:
            put(code, "볼린저", "%s:%s" % (str(ts)[8:10], str(ts)[10:12]) if len(str(ts)) >= 12 else "")

    vi_fail = prog_fail = 0
    for c in uni:
        if kis:
            v = _vi(proxy, c, day, calls)
            if v is False:
                vi_fail += 1
            elif v:
                put(c, "VI", v)
    net = lambda c, k: ((inv.get(c) or {}).get(k) or {}).get("netAmt")
    flist = set(sorted([c for c in uni if (net(c, "foreign") or 0) > 0], key=lambda c: -net(c, "foreign"))[:JOINT_LIST])
    ilist = set(sorted([c for c in uni if (net(c, "inst") or 0) > 0], key=lambda c: -net(c, "inst"))[:JOINT_LIST])
    for c in flist | ilist:
        fa = net(c, "foreign") if c in flist else None
        ia_ = net(c, "inst") if c in ilist else None
        fund = (((inv.get(c) or {}).get("instDetail") or {}).get("fund") or {}).get("netAmt")
        pg = None
        if kis and fa and ia_:
            pg = _program(proxy, c, day, calls)
            if pg is None:
                prog_fail += 1
        tier = proxy.joint_tier(fa, ia_, pg, fund)
        if tier:
            put(c, "매수%s" % "①②③④"[tier - 1], "")

    rule, _src = auto_watch.rules(proxy)
    pp, vm = rule.get("prevPct"), rule.get("volMult")
    for c in uni:
        r = today[c]
        vols = [v for (_, v) in (hist.get(c) or {}).values() if v]
        mult = r[5] / (sum(vols) / len(vols)) if r[5] and len(vols) >= VOL_AVG_DAYS else None
        if pp is not None and r[4] >= pp and (vm is None or (mult is not None and mult >= vm)):
            put(c, "수급", "15:41")
        pv = (hist.get(c, {}).get(pd) or (None, None))[1] if pd else None
        if r[5] and pv and r[5] / pv >= day_top.VOL_PREV_X:
            put(c, "거래량전날2배", "15:41")

    rows = []
    for c in uni:
        code, name, idx, close, pct, vol = today[c]
        f = dict(hit.get(c) or {})
        ov = [k for k in day_top.OV_FROM if k in f or (k == "VI·급등" and ("VI" in f or "급등" in f))
              or (k == "매수" and any(x.startswith("매수") for x in f))]
        if len(ov) >= 2:
            f["단타"] = ""
        rows.append({"code": c, "name": name, "market": idx, "pct": pct, "close": close, "vol": vol,
                     "value": close * vol if close and vol else None, "cap": cap[c], "sector": sec.get(c), "filters": f})
    rows.sort(key=lambda r: -r["pct"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    names = sorted({k for r in rows for k in r["filters"]})
    top = rows[:day_top.TOP_N]
    stats = [{"name": n, "top": sum(1 for r in top if n in r["filters"]), "all": sum(1 for r in rows if n in r["filters"])} for n in names]
    stats.sort(key=lambda s: (-s["top"], -s["all"]))
    return {"day": day, "rows": rows, "filterStats": stats,
            "meta": {"universe": len(rows), "topN": day_top.TOP_N, "minCapEok": day_top.MIN_CAP_EOK, "prevDay": pd, "volPrevX": day_top.VOL_PREV_X,
                     "rebuilt": True, "missing": ["관심"], "capNow": True, "calls": calls[0], "filled5m": filled, "noBar": no_bar,
                     "viFail": vi_fail if kis else None, "programFail": prog_fail if kis else None, "kis": kis,
                     "approx": {"프리장": "프리마켓 거래대금 상위 중 넥스트레이드 프로그램 순매수 > 0 — 프로그램은 넥장 하루 합(프리 + 애프터)",
                                "매수": "대상 안 외 · 기 순매수 상위 30 · 장 끝 확정치(investor_daily · 프로그램 일별) · 처음 잡힌 시각 없음",
                                "수급": "지금 룰로 셈",
                                "급등": "정규장 5분봉 고가 기준 · 봉이 없으면 일봉 고가(시각 빈칸)"},
                     "note": "지난 날 다시 셈(day_top_fill) · cap 은 지금 시가총액 · filters 값은 처음 걸린 시각(모르면 빈칸) · next 는 부를 때 붙임"}}


def save(proxy, day):
    if not proxy.marketdb.writable():
        return None
    b = build(proxy, day)
    if b is None:
        return None
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(day_top._SCHEMA)
        conn.execute("INSERT OR IGNORE INTO day_top (day, saved_at, board) VALUES (?,?,?)",      # 그날 판(이미 남긴 날)은 안 덮는다
                     (day, "되채움 " + datetime.now(KST).strftime("%m-%d %H:%M:%S"), json.dumps(b, ensure_ascii=False)))
    return b


def start(proxy):
    """쓰는 서버가 뜰 때 한 번 — 장이 쉬는 때 하루씩 되채운다. 다 채우면 쉰다(새 판이 남으면 앞 날이 밀리지 않는다 — 처음 남긴 날 앞만 본다)."""
    if not proxy.marketdb.writable():
        return False

    def loop():
        time.sleep(180)
        while True:
            try:
                if _idle(datetime.now(KST)):
                    todo = [d for d in targets(proxy) if d not in _failed]
                    if todo:
                        d = todo[0]
                        _status.update(state="채우는 중 %s" % d, at=datetime.now(KST).strftime("%H:%M:%S"))
                        try:
                            b = save(proxy, d)
                        except Exception as e:
                            _failed.add(d)
                            _status["error"] = "%s %s" % (d, type(e).__name__)
                            print("  [등락 상위 되채움] %s 멈춤 (%s) — 이 서버가 다시 뜰 때까지 건너뜀" % (d, type(e).__name__), flush=True)
                            continue
                        _status["done"].append({"day": d, "rows": len(b["rows"]) if b else None,
                                                "calls": b["meta"]["calls"] if b else None})
                        print("  [등락 상위 되채움] %s %s" % (d, "판 없음" if not b else "%d종목 · KIS %d번" % (len(b["rows"]), b["meta"]["calls"])), flush=True)
                        continue
                    _status["state"] = "다 채움"
                else:
                    _status["state"] = "장중이라 쉼"
            except Exception as e:
                _status["error"] = "%s" % type(e).__name__
            time.sleep(60)

    threading.Thread(target=loop, daemon=True, name="day-top-fill").start()
    return True
