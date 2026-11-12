# -*- coding: utf-8 -*-
"""공포·탐욕 지수 — 코스피 · 삼성전자 · SK하이닉스 (2026-11-06 · server/fear_greed.py)

재권님 「이거 만들고 싶어 분석해」(사진 · 작업우선순위 배분) → 그림 → 「차트 위쪽에 버튼을 만들고 누르면 보여지게」 ·
「공포지수 25에 세로선 · 25 아래에서 25를 통과할 때 내가 알 수 있게 · 코스피 삼전 닉스 이렇게만」 → 「1차로 만들어」(11-06).

    셈       요소 일곱을 각자 원래 값으로 셈 → 지난 1년(WINDOW 거래일) 그 요소 값들 가운데 오늘이 몇 % 자리인가로 0~100
             (변동성 · VIX 는 클수록 공포라 뒤집음) → 셈된 요소들의 평균(같은 무게 · 못 잰 요소는 빼고 평균)
    코스피    모멘텀 코스피 125일선 대비 · 주가 강도 52주 신고가 − 신저가(코스피 시가총액 상위 200 · 우선주 포함 중 1년 일봉이 다 있는 종목 수 대비) ·
             시장 폭 20일 오른 종목의 거래대금 비중 · 변동성 20일 · 외국인 20일 누적(시장) · 투자심리선 10일 · 간밤 VIX ÷ 50일 평균
    종목      시장에만 있는 둘을 그 종목 것으로 바꾼다 — 주가 강도 52주 범위 안 자리 · 시장 폭 → 20일 중 오른 날의 거래대금 비중 ·
             외국인 20일 누적은 그 종목(쌓인 날이 짧으면 쌓인 만큼 안에서 자리 · 모자라면 뺌)
    재료      전부 이미 있는 것 — 일봉(candles D) · 시장 외국인(fetch_investor_flow · 한 번 300거래일) · 종목 외국인(investor_daily) ·
             VIX(us_outlook 의 Cboe 1년). 바깥에 새로 묻지 않는다
    25 돌파   점수가 FEAR_LINE 아래에서 그 위로 올라선 날 = 「풀림」. 앞 풀림 뒤 REGROUP 거래일 안의 것은 「다시 넘음」 으로 묶는다(사진의 규칙).
             보내는 서버(8765)가 평일 ALERT_AT 뒤 한 번 그날 마감 값으로 보고 「풀림 첫날」 이면 알린다 — **SEND 가 False 면 안 보내고 기록만**
    장중      그날 일봉(지수 · 그 종목)이 들어와 있으면 그것으로 셈 — 마감 전이면 「장중」 이라 적는다. 코스피는 그날 종목 일봉이
             앞 거래일의 COUNT_RATIO 아래면 점수를 안 내고 「셈 중」(counting) · 25 풀림 판정도 차거나 JUDGE_UNTIL 까지 미룬다(2026-11-12)
"""
import json
import urllib.request
import statistics as st
import threading
import time
from datetime import datetime, timedelta, timezone

import dart
import us_outlook
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))
TARGETS = (("KOSPI", "0001", "코스피"), ("005930", "005930", "삼성전자"), ("000660", "000660", "SK하이닉스"))
WINDOW = 250            # 0~100 을 매기는 기간(거래일 · 1년)
HIST = 120              # 화면 그래프 기간
FEAR_LINE = 25          # 이 아래가 「극도의 공포」 · 이것을 아래에서 위로 넘으면 「풀림」
REGROUP = 20            # 앞 풀림 뒤 이 거래일 안에 다시 넘으면 같은 일로 묶는다
MIN_HIST = 40           # 요소 값이 이만큼은 쌓여야 자리를 매긴다(종목 외국인처럼 짧은 것)
MIN_STOCKS = 100        # 시장 두 요소(신고가 · 폭)를 그날 셈하려면 1년 일봉이 다 있는 종목이 이만큼(코스피 상위 200 중 · 11-12 잰 148)
COUNT_RATIO = 0.9       # 그날 일봉이 든 종목이 앞 거래일의 이 비율 아래면 「셈 중」 — 점수를 안 내고 풀림 판정도 미룬다
JUDGE_UNTIL = (23, 30)  # 「셈 중」 이면 ALERT_AT 뒤 TICK 마다 다시 본다 — 이 시각까지 안 차면 그날은 판정 안 함으로 남긴다(종목 일봉은 20:10 부터 한 바퀴가 채운다 — 두 시간 남짓 · kis_proxy DWMY_AT_MIN)
CACHE_SEC = 300
ZONES = ((25, "극도의 공포"), (45, "공포"), (55, "중립"), (75, "탐욕"), (101, "극도의 탐욕"))
SEND = False            # 25 풀림 알림 — 만들었고 꺼 둠(켜기는 재권님 지시 · 몇 통 갈지는 응답 alerts 로 센다)
ALERT_AT = (15, 45)     # 마감 뒤 이 시각부터 그날 한 번 본다
TICK = 60

_cache = {}
_lock = threading.Lock()
_status = {"alertDay": None, "alertLast": None, "error": None}


def _now():
    return datetime.now(KST)


def zone(s):
    return next(n for lim, n in ZONES if s < lim) if s is not None else None


def _pctile(vals, v):
    s = [x for x in vals if x is not None]
    if len(s) < MIN_HIST or v is None:
        return None
    return round(sum(1 for x in s if x <= v) / len(s) * 100)


def _daily(proxy, code):
    with proxy._db_lock, proxy.db_conn() as conn:
        return conn.execute("SELECT ts, close, volume FROM candles WHERE code = ? AND period = 'D' AND close > 0 ORDER BY ts",
                            (code,)).fetchall()


def _stocks(proxy, since):
    """코스피 시가총액 상위(dart 감시 목록 · 매일 07시) 종목의 일봉 — 우선주 포함 (2026-11-12 qa 검수 · 재권님 「우선주도 넣어」).
    전에는 일봉이 있는 6자리 전부를 세어 코스닥 · ETF 가 섞였다."""
    codes = {r["stock_code"] for r in dart.universe_top_rows("KOSPI")}   # 상위 200 — 대상 표가 5천억 이상으로 넓어져도(11-12) 그대로
    px = {c: {} for c in codes}
    if not codes:
        return px
    with proxy._db_lock, proxy.db_conn() as conn:
        for code, ts, cl, vol in conn.execute(
                "SELECT code, ts, close, volume FROM candles WHERE period = 'D' AND close > 0 AND ts >= ? "
                "AND code IN (%s)" % ",".join("?" * len(codes)), (since, *codes)):
            px[code][ts] = (cl, vol or 0)
    return px


def _day_count(mkt, day):
    return sum(1 for m in mkt.values() if day in m)


def _vix_ratio(proxy):
    """{미국 날(YYYYMMDD): VIX ÷ 그날까지 50일 평균} — 못 받았으면 {}."""
    try:
        up = proxy.upstream_base()
        if up:                                # 세션 서버는 8765 가 받아 둔 것을 읽는다 — 바깥을 따로 안 부른다
            req = urllib.request.Request(up + "/api/market/us-outlook", headers={"X-KJC-Prio": "low"})
            with urllib.request.urlopen(req, timeout=10) as r:
                o = json.loads(r.read().decode("utf-8"))
        else:
            o = us_outlook.outlook()
        v = ((o.get("vix") or {}).get("data") or {}).get("rows") or []
    except Exception:
        return {}
    d = [r["date"].replace("-", "") for r in v]
    c = [r["close"] for r in v]
    return {d[j]: c[j] / (sum(c[j - 49:j + 1]) / 50) for j in range(49, len(c))}


def _foreign_market(proxy):
    try:
        rows = proxy.fetch_investor_flow(proxy.load_secrets(), "KOSPI", 300) or []
    except Exception:
        return {}
    d = [r["date"].replace("-", "") for r in rows]
    a = [(r.get("foreign") or {}).get("amt") for r in rows]          # 백만원
    return {d[j]: sum(a[j - 19:j + 1]) for j in range(19, len(a)) if None not in a[j - 19:j + 1]}


def _foreign_stock(proxy, code):
    with proxy._db_lock, proxy.db_conn() as conn:
        rows = conn.execute("SELECT date, row FROM investor_daily WHERE code = ? ORDER BY date", (code,)).fetchall()
    d, a = [], []
    for day, row in rows:
        try:
            v = (json.loads(row).get("foreign") or {}).get("netAmt")
        except (ValueError, AttributeError):
            v = None
        if v is not None:
            d.append(day); a.append(v)
    return {d[j]: sum(a[j - 19:j + 1]) for j in range(19, len(a))}


def _factors(days, cl, vol, i, mkt=None, fr=None, vx=None):
    """그날 i 의 요소 원래 값 — 못 셈은 None."""
    f = dict.fromkeys(("mom", "hl", "breadth", "vol", "frn", "psy", "vix"))
    if i >= 124:
        f["mom"] = cl[i] / (sum(cl[i - 124:i + 1]) / 125) - 1
    if i >= 20:
        f["vol"] = st.pstdev([cl[j] / cl[j - 1] - 1 for j in range(i - 19, i + 1)])
    if i >= 10:
        f["psy"] = sum(1 for j in range(i - 9, i + 1) if cl[j] > cl[j - 1]) / 10
    d = days[i]
    if mkt is not None:                       # 코스피 — 종목 수로
        if i >= 20:
            nh = nl = n = 0
            up = tot = 0.0
            d20, win = days[i - 20], days[max(0, i - 250):i]
            for m in mkt.values():
                if d not in m:
                    continue
                c = m[d][0]
                prev = [m[x][0] for x in win if x in m]
                if len(prev) >= 200:
                    n += 1
                    if c > max(prev):
                        nh += 1
                    elif c < min(prev):
                        nl += 1
                if d20 in m:
                    amt = sum(m[x][0] * m[x][1] for x in days[i - 19:i + 1] if x in m)
                    tot += amt
                    if c > m[d20][0]:
                        up += amt
            if n >= MIN_STOCKS:
                f["hl"] = (nh - nl) / n
                f["hlN"] = n
                if tot:
                    f["breadth"] = up / tot
    else:                                     # 종목 — 그 종목 것으로
        if i >= 249:
            lo, hi = min(cl[i - 249:i + 1]), max(cl[i - 249:i + 1])
            f["hl"] = (cl[i] - lo) / (hi - lo) if hi > lo else None
        if i >= 20:
            tot = sum(cl[j] * vol[j] for j in range(i - 19, i + 1))
            up = sum(cl[j] * vol[j] for j in range(i - 19, i + 1) if cl[j] > cl[j - 1])
            f["breadth"] = up / tot if tot else None
    if fr:
        f["frn"] = fr.get(d)
    if vx:
        prev = [x for x in vx if x < d]
        f["vix"] = vx[max(prev)] if prev else None
    return f


KEYS = (("mom", 1), ("hl", 1), ("breadth", 1), ("vol", -1), ("frn", 1), ("psy", 1), ("vix", -1))


def _score(F, days, i):
    win = range(max(0, i - WINDOW + 1), i + 1)
    parts = {}
    for k, sgn in KEYS:
        p = _pctile([F[j][k] for j in win], F[i][k])
        parts[k] = None if p is None else (p if sgn > 0 else 100 - p)
    have = [v for v in parts.values() if v is not None]
    return (round(sum(have) / len(have)) if have else None), parts


def crossings(hist):
    """[(day, 'first'|'again')] — 아래에서 FEAR_LINE 위로 올라선 날 · 앞 풀림 뒤 REGROUP 거래일 안이면 again."""
    out, last = [], None
    for j in range(1, len(hist)):
        a, b = hist[j - 1][1], hist[j][1]
        if a is not None and b is not None and a < FEAR_LINE <= b:
            kind = "again" if last is not None and j - last <= REGROUP else "first"
            if kind == "first":           # 묶음은 첫날부터 센다(사진 「앞 첫날 뒤 20거래일 안」)
                last = j
            out.append((hist[j][0], kind))
    return out


def _compute(proxy, key):
    t = next(x for x in TARGETS if x[0] == key)
    rows = _daily(proxy, t[1])
    if len(rows) < 130:
        return {"key": key, "name": t[2], "ready": False, "why": "일봉이 모자람(%d일)" % len(rows)}
    days = [r[0] for r in rows]
    cl = [r[1] for r in rows]
    vol = [r[2] or 0 for r in rows]
    vx = _vix_ratio(proxy)
    if key == "KOSPI":
        mkt = _stocks(proxy, days[max(0, len(days) - HIST - WINDOW - 260)])
        fr = _foreign_market(proxy)
    else:
        mkt, fr = None, _foreign_stock(proxy, t[1])
    start = max(0, len(days) - HIST - WINDOW)
    F = {}
    for i in range(start, len(days)):
        F[i] = _factors(days, cl, vol, i, mkt, fr, vx)
    def short(i):                             # 그날 종목 일봉이 앞 거래일의 COUNT_RATIO 아래인가 — 지난 날도 같은 선(그래프에 빈칸)
        return mkt is not None and i >= 1 and _day_count(mkt, days[i]) < int(_day_count(mkt, days[i - 1]) * COUNT_RATIO + 0.999)
    hist = []
    for i in range(len(days) - HIST, len(days)):
        s, _ = _score(F, days, i)
        hist.append([days[i], None if short(i) else s])
    i = len(days) - 1
    s, parts = _score(F, days, i)
    count = None
    if mkt is not None and i >= 1:
        # **그날 일봉이 덜 쌓였으면 「셈 중」** — 11-11 은 그날 일봉이 앞날의 몇 분의 1이라 두 요소가 빠진 채 다섯으로 셈됐다(qa 검수)
        n0, n1 = _day_count(mkt, days[i]), _day_count(mkt, days[i - 1])
        count = {"day": n0, "prev": n1, "need": int(n1 * COUNT_RATIO + 0.999)}
        if n0 < count["need"]:
            s, parts = None, {k: None for k in parts}
            hist[-1][1] = None
    raw = {k: F[i][k] for k, _ in KEYS}
    vols = [F[j]["vol"] for j in range(max(start, i - WINDOW + 1), i + 1) if F[j]["vol"] is not None]
    now = _now()
    today = now.strftime("%Y%m%d")
    run = 0
    for h in reversed(hist):
        if h[1] is None or h[1] >= FEAR_LINE:
            break
        run += 1
    def ago(n):
        return hist[-1 - n][1] if len(hist) > n and hist[-1][1] is not None and hist[-1 - n][1] is not None else None
    cr = crossings(hist)
    return {
        "key": key, "name": t[2], "ready": s is not None or (count is not None and count["day"] < count["need"]), "day": days[i],
        "live": days[i] == today and now.weekday() < 5 and (now.hour, now.minute) < (15, 30),
        "score": s, "zone": zone(s) if s is not None else None, "parts": parts,
        "counting": count is not None and s is None, "count": count, "raw": raw, "hlN": F[i].get("hlN"),
        "volRatio": (raw["vol"] / st.mean(vols)) if raw["vol"] is not None and vols else None,
        "d5": None if ago(5) is None else s - ago(5), "d20": None if ago(20) is None else s - ago(20),
        "below": run, "hist": hist,
        "crossings": [{"day": d, "kind": k} for d, k in cr],
        "lastFirst": next((d for d, k in reversed(cr) if k == "first"), None),
        "kind": "market" if key == "KOSPI" else "stock",
    }


def get(proxy, key):
    """캐시(CACHE_SEC) — 셈이 몇 초 걸려 부를 때마다 하지 않는다. 열쇠는 그날 마지막 일봉 시각까지 넣지 않고 시간만 본다."""
    key = key if any(t[0] == key for t in TARGETS) else "KOSPI"
    with _lock:
        c = _cache.get(key)
        if c and time.time() - c[0] < CACHE_SEC:
            return c[1]
    try:
        d = _compute(proxy, key)
    except Exception as e:
        d = {"key": key, "ready": False, "why": "셈 실패 — " + safe_message(e, 160)}
    with _lock:
        _cache[key] = (time.time(), d)
    return d


def all_targets(proxy, key=None):
    return {"targets": [{"key": t[0], "name": t[2]} for t in TARGETS], "line": FEAR_LINE, "regroup": REGROUP,
            "zones": [{"under": lim, "name": n} for lim, n in ZONES], "data": get(proxy, key or "KOSPI")}


def status():
    return dict(_status, send=SEND, alertAt="평일 %02d:%02d 뒤 한 번" % ALERT_AT,
                note="25 풀림 알림은 SEND 가 켜져야 보낸다 — 꺼져 있으면 alertLast 에 「보냈을 것」 만 적는다")


def _alert_once(proxy, day):
    """그날 마감 값으로 셋을 보고 「풀림 첫날」 이 그날인 것을 알린다 — 같은 날 다시 안 본다(_status.alertDay).
    판정했으면 True · 코스피가 「셈 중」 이라 미뤘으면 False(loop 가 다음 TICK 에 다시 부른다 · JUDGE_UNTIL 뒤에는 True)."""
    hits = []
    now = _now()
    with _lock:
        _cache.pop("KOSPI", None)                       # 마감 값으로 다시 셈
    k = get(proxy, "KOSPI")
    if k.get("counting"):
        # **그날 일봉이 덜 쌓였으면 판정을 미룬다** — TICK 뒤 다시(loop 가 alertDay 를 비운다) · JUDGE_UNTIL 까지
        late = (now.hour, now.minute) >= JUDGE_UNTIL
        _status["alertLast"] = {"day": day, "at": now.isoformat(timespec="seconds"), "hits": [], "text": None,
                                "sent": "판정 안 함 — 셈 중(그날 일봉 %d/%d)" % (k["count"]["day"], k["count"]["prev"])
                                        + ("" if late else " · 다시 봄")}
        return late
    for t in TARGETS:
        with _lock:
            _cache.pop(t[0], None)                      # 마감 값으로 다시 셈
        d = get(proxy, t[0])
        if d.get("day") == day and any(c["day"] == day and c["kind"] == "first" for c in d.get("crossings") or []):
            hits.append(d)
    msg = None
    if hits:
        msg = "\n".join("[공포·탐욕] %s %d — %d 아래에서 위로 올라섰습니다(풀림 첫날 %s)"
                        % (d["name"], d["score"], FEAR_LINE, day[4:6] + "-" + day[6:]) for d in hits)
    sent = None
    if msg and SEND:
        with proxy._db_lock, proxy.db_conn() as conn:          # 재시작해도 같은 날 두 번 안 보낸다
            if conn.execute("SELECT 1 FROM fear_greed_alert WHERE day = ?", (day,)).fetchone():
                return True
            conn.execute("INSERT INTO fear_greed_alert VALUES (?, ?, ?)", (day, _now().isoformat(timespec="seconds"), msg))
        ok, why = dart.telegram_send(msg)
        sent = ok if ok else why
    _status["alertLast"] = {"day": day, "at": _now().isoformat(timespec="seconds"),
                            "hits": [h["name"] for h in hits], "text": msg, "sent": sent if SEND else "꺼짐(SEND=False)"}
    return True


def start(proxy):
    """보내는 서버만 — 평일 ALERT_AT 뒤 그날 한 번 25 풀림을 본다."""
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS fear_greed_alert (day TEXT PRIMARY KEY, at TEXT, text TEXT)")

    def loop():
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                if now.weekday() < 5 and (now.hour, now.minute) >= ALERT_AT and _status["alertDay"] != day:
                    _status["alertDay"] = day
                    if not _alert_once(proxy, day):
                        _status["alertDay"] = None      # 셈 중 — 다음 TICK 에 다시
            except Exception as e:
                _status["error"] = safe_message(e, 160)
            time.sleep(TICK)
    threading.Thread(target=loop, daemon=True, name="fear-greed").start()
    return True
