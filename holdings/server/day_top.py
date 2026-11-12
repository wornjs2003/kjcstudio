# -*- coding: utf-8 -*-
"""등락 상위와 걸린 필터 — 날마다 장 끝난 뒤 한 번 쌓는다 (2026-11-11).

재권님 — 「시가통액 5천억이상 등락률 상위 종목 표가 필요하고 거기 상위에 어떤 테마인지(섹터) 를 넣어서 색으로 표를 분류해줘」 →
「이 종목중에 관심안에 걸린종목과 안걸린 종목을 구분해서 이유까지」 → 「이거 매일 정리해서 데이터 쌓아놔야 할거같은데.. 이걸 바탕으로
좋은종목 찾기를 만들려고해」 · 「가장 많이 걸린 필터들 분석해서 정리해줘. 매일매일 장 끝나면 정리되서 쌓아놔야 할거같아. 어떤필터가
중요한지 데이터가 필요해」(작업우선순위 경유) → 안 「응」(개발1 창 16:2x). 화면은 Insight 종목 기록(시황분석1)이 읽는다.

    대상      auto_watch_day 의 그날 판(15:41 · KRX 종가 · 코스피 시총 상위 200 · 코스닥 150 중 주권만 — ETF 는 이미 빠짐) 중
              시가총액 MIN_CAP_EOK 억원 이상 — 시가총액은 감시 목록(dart.universe_rows)의 market_cap(억원)
              **전부 남긴다**(상위만이 아니다) — 「좋은 종목 찾기」 는 걸린 것 · 안 걸린 것을 함께 봐야 해서다. 등락률 차례는 rank
    값        pct(KRX 종가 등락률) · close · vol · value(종가 × 거래량 · 어림) · cap · sector(WICS · company_profile)
    필터      종목마다 걸린 것과 그 시각(filters: {이름: "HH:MM" 또는 ""})
                VI · 급등      intraday_alerts 그날 목록 — 처음 본 시각
                초반상승       open_rise.build 의 rows — 09:05(첫 봉이 끝난 때)
                프리장         pre_flow 그날 판 중 프로그램 순매수 > 0 — 08:50(굳힌 때)
                볼린저         signal_watch.today_lows — 그 봉 시각
                매수①~④       kis_proxy 「매수」 판의 tier — 그날 처음 잡힌 시각(first)
                수급           auto_watch_pick 중 그날 룰(rule 칸)을 넘은 것 — 신고가 부근만 붙은 것은 빼고 · 15:41
                거래량전날2배  auto_watch_day 그날 ÷ 앞 날 거래량 VOL_PREV_X 배 이상 — 시험 기준(재권님 11-11 「전날대비 2배로 했을때」) · 15:41
                관심           관심 목록 문서 items 중 자동 묶음이 아닌 것(하트) — 시각 없음
                단타           관심 · 프리장 · VI·급등 · 매수 · 초반상승 · 수급 중 둘 이상(화면 ov 와 같은 셈 · 장외는 장 뒤라 안 셈)
    다음날    board() 가 부를 때 다음 거래일 auto_watch_day 의 그 종목 pct 를 next 로 붙인다(따로 안 쌓는다)
    저장      market.db `day_top`(날 · 판 JSON) — 평일 SAVE_AT 뒤 「매수」 판이 굳으면(외 · 기 확정 · 연기금 들어옴) 한 번 · 늦어도 SAVE_LATE
              쓰기 되는 서버(8765)만 · 한 번 남긴 날은 다시 안 쓴다(watch_log 와 같다)
    주소      GET /api/kis/day-top?day=YYYYMMDD[&all=1] — day 를 빼면 마지막 날 · 기본은 상위 TOP_N 줄 · all=1 이면 전부 ·
              meta.days 는 남긴 날 목록(최근 먼저) · **주소는 KIS 를 안 부른다** — 판을 지을 때(하루 한 번)는 볼린저 칸의
              signal_watch.today_lows 가 시가총액을 채우느라 몇 종목 시세를 부를 수 있다(qa 11-11)
"""
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import dart            # 시가총액 문턱(UNIVERSE_MIN_CAP_EOK) 한 곳 — 모듈을 읽을 때 쓴다

KST = timezone(timedelta(hours=9))
MIN_CAP_EOK = dart.UNIVERSE_MIN_CAP_EOK   # 시가총액 문턱(억원) — 대상 목록 문턱 그대로(한 곳 · 개념정의 검수 11-12) · 재권님 「시가통액 5천억이상」 → 「3천억으로 통일해」 → 「오전에 3천억이라고 한거 5천억으로 바꿔」(11-12)
TOP_N = 40                    # 주소가 기본으로 내는 줄 수
VOL_PREV_X = 2.0              # 「거래량 전날 2배」 시험 기준
SAVE_AT = (16, 10)            # flow_rank 확정치 쌓기(15:45) · 「매수」 판 굳기를 기다린 뒤
SAVE_LATE = (17, 30)          # 「매수」 판이 안 굳어도 이 시각엔 남긴다(그때 meta.jointFrozen false)
TICK = 60
DAYS_MAX = 120
OV_FROM = ("관심", "프리장", "VI·급등", "매수", "초반상승", "수급")   # 단타 셈 — 화면 home.js OV_CHIPS 와 같은 뜻(장외 빼고)

PICK_AT = "15:41"               # 수급 · 거래량전날2배 시각 — auto_watch_day 그날 판이 굳는 때(SAVE_AT 과 다르다)
_SCHEMA = "CREATE TABLE IF NOT EXISTS day_top (day TEXT PRIMARY KEY, saved_at TEXT, board TEXT NOT NULL)"
_status = {"saved": None, "error": None}


def _now():
    return datetime.now(KST)


def _hm(s):
    s = str(s or "")
    return s[:5] if len(s) >= 5 and s[2] == ":" else s


def build(proxy, day):
    """그날 판 — {day, rows, filterStats, meta}. auto_watch_day 그날 판이 없으면 None."""
    import dart, company_profile, intraday_alerts, open_rise, pre_flow, signal_watch, docstore
    with proxy.db_conn() as conn:
        today = {r[0]: r for r in conn.execute("SELECT code, name, idx, close, pct, vol FROM auto_watch_day WHERE day = ?", (day,))}
        if not today:
            return None
        pd = conn.execute("SELECT MAX(day) FROM auto_watch_day WHERE day < ?", (day,)).fetchone()[0]
        prev = dict(conn.execute("SELECT code, vol FROM auto_watch_day WHERE day = ?", (pd,))) if pd else {}
        picks = conn.execute("SELECT code, pct, mult, rule FROM auto_watch_pick WHERE day = ?", (day,)).fetchall()
    cap = {r["stock_code"]: r["market_cap"] for r in dart.universe_rows(None)}
    sec = company_profile.sectors()
    hit = {}

    def put(code, name, t=""):
        f = hit.setdefault(code, {})
        if name not in f or (t and (not f[name] or t < f[name])):
            f[name] = t

    try:
        al = intraday_alerts.today()
        if al.get("day") == day:
            for it in al.get("items") or []:
                put(it.get("code"), "VI" if it.get("kind") == "vi" else "급등", _hm(it.get("t")))
    except Exception:
        pass
    try:
        b = open_rise.build(proxy)
        if b.get("day") == day:
            for r in b.get("rows") or []:
                put(r["code"], "초반상승", b.get("barTo") or "")
        rise_meta = {k: b.get(k) for k in ("phase", "pending", "noBar")}
    except Exception:
        rise_meta = {"phase": "error"}
    try:
        pf, _, _ = pre_flow.fetch(proxy, proxy.load_secrets())
        if pf and pf.get("day") == day:
            for r in pf.get("rows") or []:
                if (r.get("program") or 0) > 0:
                    put(r["code"], "프리장", pf.get("hm") or "")
    except Exception:
        pass
    try:
        for it in signal_watch.today_lows(proxy).get("items") or []:
            if str(it.get("ts", ""))[:8] == day:
                put(it["code"], "볼린저", it.get("t") or "")
    except Exception:
        pass
    jd = (proxy._joint_buy.get("data") or {}) if proxy._joint_buy.get("day") == "%s-%s-%s" % (day[:4], day[4:6], day[6:]) else {}
    for r in jd.get("rows") or []:
        if r.get("tier"):
            put(r["code"], "매수%s" % "①②③④"[r["tier"] - 1], r.get("first") or "")
    for code, pct, mult, rule in picks:
        try:
            ru = json.loads(rule or "{}")
        except ValueError:
            ru = {}
        if pct is not None and ru.get("prevPct") is not None and pct >= ru["prevPct"] \
                and (ru.get("volMult") is None or (mult is not None and mult >= ru["volMult"])):
            put(code, "수급", PICK_AT)
    for code, r in today.items():
        if r[5] and prev.get(code) and r[5] / prev[code] >= VOL_PREV_X:
            put(code, "거래량전날2배", PICK_AT)
    try:
        doc = docstore.read_doc("watchlist") or {}
        auto = set((doc.get("auto") or {}).keys()) if isinstance(doc.get("auto"), dict) else set()
        for it in doc.get("items") or []:
            if isinstance(it, dict) and it.get("code") not in auto:
                put(it.get("code"), "관심")
    except Exception:
        pass
    rows = []
    for code, (c, name, idx, close, pct, vol) in today.items():
        cp = cap.get(code)
        if pct is None or cp is None or cp < MIN_CAP_EOK:
            continue
        f = dict(hit.get(code) or {})
        ov = [k for k in OV_FROM if k in f or (k == "VI·급등" and ("VI" in f or "급등" in f))
              or (k == "매수" and any(x.startswith("매수") for x in f))]
        if len(ov) >= 2:
            f["단타"] = ""
        rows.append({"code": code, "name": name, "market": idx, "pct": pct, "close": close, "vol": vol,
                     "value": close * vol if close and vol else None, "cap": cp, "sector": sec.get(code), "filters": f})
    rows.sort(key=lambda r: -r["pct"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    names = sorted({k for r in rows for k in r["filters"]})
    top = rows[:TOP_N]
    stats = [{"name": n, "top": sum(1 for r in top if n in r["filters"]), "all": sum(1 for r in rows if n in r["filters"])} for n in names]
    stats.sort(key=lambda s: (-s["top"], -s["all"]))
    return {"day": day, "rows": rows, "filterStats": stats,
            "meta": {"universe": len(rows), "topN": TOP_N, "minCapEok": MIN_CAP_EOK, "prevDay": pd, "volPrevX": VOL_PREV_X,
                     "jointFrozen": bool(proxy._joint_buy.get("frozen")), "rise": rise_meta,
                     "note": "pct KRX 종가 등락률 · cap 억원 · value 종가 × 거래량(어림 · 원) · filters 값은 처음 걸린 시각(없으면 빈칸) · "
                             "장외는 안 셈 · next 는 다음 거래일 종가 등락률(부를 때 붙임)"}}


def days(proxy):
    try:
        with proxy.db_conn() as conn:
            return [d for (d,) in conn.execute("SELECT day FROM day_top ORDER BY day DESC LIMIT ?", (DAYS_MAX,))]
    except Exception:
        return []


def board(proxy, day=None, all_rows=False):
    """주소 /api/kis/day-top 의 data — 남긴 날만(없으면 None). 다음 거래일 등락률(next)을 붙인다."""
    ds = days(proxy)
    day = day or (ds[0] if ds else None)
    if not day:
        return None
    try:
        with proxy.db_conn() as conn:
            got = conn.execute("SELECT board, saved_at FROM day_top WHERE day = ?", (day,)).fetchone()
            nd = conn.execute("SELECT MIN(day) FROM auto_watch_day WHERE day > ?", (day,)).fetchone()[0]
            nxt = dict(conn.execute("SELECT code, pct FROM auto_watch_day WHERE day = ?", (nd,))) if nd else {}
    except Exception:
        return None
    if not got:
        return None
    b = json.loads(got[0])
    rows = b["rows"] if all_rows else b["rows"][:TOP_N]
    for r in rows:
        r["next"] = nxt.get(r["code"])
    b["rows"] = rows
    b["meta"].update(savedAt=got[1], nextDay=nd)
    return b


def filters(proxy):
    """주소 /api/kis/day-top/filters 의 data — 쌓인 날 전부를 모아 필터별 셈 · 날별 셈 (2026-11-11 재권님 「이데이터를 쌓아두고 평균도 내야하는데
    투자전략에 … 종목기록 옆에 필터 라고 이름만들어서 여기에 날짜별로 쌓으면」). 셈은 여기 한 곳 — 화면은 받은 대로 그린다.

        days[]   최근 먼저 — {day, topN, universe, nextDay, filters: {이름: {top, all, next: 걸린 종목 다음 날 등락률 평균 | null, nextN}}}
        filters  모든 날 합 — {name, top, all, topRate(상위 중 몫 %), allRate(전체 중 몫 %), lift(배 · topRate ÷ allRate), hit(적중 % · 걸린 것 중 상위),
                 nextAvg(다음 날 등락률 평균 % · 다음 날이 온 종목만), nextUp(그중 오른 몫 %), nextN, days(걸린 날 수)} — 상위 중 많은 순
    「없음」 은 null(0 아님) — 다음 날이 아직 안 온 날 · 대상이 0 인 칸."""
    out, tot = [], {}
    sum_top = sum_all = 0
    for day in days(proxy):
        b = board(proxy, day, True)
        if not b:
            continue
        rows, n = b["rows"], b["meta"]["topN"]
        top = {r["code"] for r in rows[:n]}
        per = {}
        for r in rows:
            for f in r["filters"]:
                a = per.setdefault(f, {"top": 0, "all": 0, "_nx": []})
                a["all"] += 1
                a["top"] += r["code"] in top
                if r.get("next") is not None:
                    a["_nx"].append(r["next"])
        for f, a in per.items():
            t = tot.setdefault(f, {"top": 0, "all": 0, "_nx": [], "days": 0})
            t["top"] += a["top"]
            t["all"] += a["all"]
            t["_nx"] += a["_nx"]
            t["days"] += 1
            nx = a.pop("_nx")
            a.update(next=round(sum(nx) / len(nx), 2) if nx else None, nextN=len(nx))
        sum_top += min(n, len(rows))
        sum_all += len(rows)
        out.append({"day": day, "topN": n, "universe": len(rows), "nextDay": b["meta"].get("nextDay"), "filters": per})

    def rate(a, b):
        return round(a * 100 / b, 1) if b else None

    fs = []
    for f, t in tot.items():
        nx = t["_nx"]
        tr, ar = rate(t["top"], sum_top), rate(t["all"], sum_all)
        fs.append({"name": f, "top": t["top"], "all": t["all"], "topRate": tr, "allRate": ar,
                   "lift": round(tr / ar, 2) if tr is not None and ar else None, "hit": rate(t["top"], t["all"]),
                   "nextAvg": round(sum(nx) / len(nx), 2) if nx else None, "nextUp": rate(sum(1 for v in nx if v > 0), len(nx)),
                   "nextN": len(nx), "days": t["days"]})
    fs.sort(key=lambda x: (-x["top"], -x["all"]))
    return {"days": out, "filters": fs, "sumTop": sum_top, "sumAll": sum_all}


def _saved_day(proxy, day):
    try:
        with proxy.db_conn() as conn:
            return conn.execute("SELECT 1 FROM day_top WHERE day = ?", (day,)).fetchone() is not None
    except Exception:
        return False


def save(proxy, day):
    b = build(proxy, day)
    if b is None:
        return None
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        conn.execute("INSERT OR REPLACE INTO day_top (day, saved_at, board) VALUES (?,?,?)",
                     (day, _now().strftime("%H:%M:%S"), json.dumps(b, ensure_ascii=False)))
    return len(b["rows"])


def status():
    return dict(_status, saveAt="%02d:%02d" % SAVE_AT, saveLate="%02d:%02d" % SAVE_LATE)


def start(proxy):
    """쓰는 서버가 뜰 때 한 번 — 평일 SAVE_AT 뒤 「매수」 판이 굳으면(늦어도 SAVE_LATE) 그날 판을 남긴다."""
    if not proxy.marketdb.writable():
        return False

    def loop():
        time.sleep(120)
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = (now.hour, now.minute)
                if now.weekday() < 5 and hm >= SAVE_AT and _status.get("saved") != day:
                    if _saved_day(proxy, day):
                        _status.update(saved=day)
                    elif proxy._joint_buy.get("frozen") or hm >= SAVE_LATE:
                        n = save(proxy, day)
                        _status.update(saved=day, error=None)
                        print("  [등락 상위] %s %s" % (day, "그날 판 없음(휴장 · 15:41 판 전) — 안 남김" if n is None else "%d종목 남김" % n), flush=True)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [등락 상위] 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="day-top").start()
    return True
