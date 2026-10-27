# -*- coding: utf-8 -*-
"""미국장 예측용 값 — Insight 시황분석 탭 「오늘 밤 미국장 예상 범위」 가 더해 쓸 재료 (2026-10-27 · 재권님 「응 해줘」).

경위 — 재권님 10-26 「가능한 부분만 통계적으로 가면 될 것 같아. 못 가져오는 것들 가져올 방법 찾아봐」 → 시황분석1 이 받을 길을
찾고(temp/시황분석1-미장예측.html) 「서버에 받을 것은 주식 레인에」 에 「응 해봐」 → 안(받을 것 · 주기 · 주소)에 「응 해줘」(10-27 11:4x).
**방향을 예측하지 않는다** — 화면이 셈할 재료만 낸다. 셈(예상 범위 등)은 화면 몫이다.

    GET /api/market/us-outlook      다섯 묶음을 한 번에 — 묶음마다 at(받은 시각) · error(못 받았으면)

── 어디서 받나 (2026-10-27 11:3x 실측 · 다 값이 왔다) ──

    futures    야후 chart — ES=F · NQ=F · YM=F · RTY=F 와 ^DJI · ^RUT · ^TYX · ^VIX9D · ^VVIX   10분쯤 늦은 값
    options    Cboe 지연 시세 _SPX.json (한 번에 13MB · 15분 늦은 값) — 가장 가까운 만기의 등가격 스트래들
    econ       나스닥 경제지표 일정 — 미국 줄만 · 예상치(consensus) · 발표치 · 이전치
    fomc       야후 연방기금 선물(ZQ<달><해>.CBT) + 뉴욕 연준 실효 금리(EFFR) — 다음 FOMC 의 시장 기대 금리
    vix        Cboe VIX 일별 이력 csv — 지난 1년 종가와 지금 값의 1년 백분위

**야후 · 나스닥 · Cboe 는 공식으로 열어 둔 API 가 아니다 · 약관은 확인하지 못했다.** 주소가 바뀌거나 막히면 그 묶음만
`error` 와 함께 앞에 받은 값(있으면)을 그대로 낸다 — **0 · 빈칸으로 덮지 않는다.** 한 번도 못 받았으면 값 칸이 null 이다.
CTA(추세 추종 자금) 포지션은 유료라 못 받는다(영영 — 무료 출처가 없다).
실적 발표 일정은 여기서 받지 않는다 — 개발2 카드(미국 종목) 몫이라 겹치지 않게 뺐다.

── 주기 · 어느 서버가 받나 ──

화면은 주기로 묻지 않고 열 때 받는다. 묶음마다 수명(`TTL`)이 지나면 그 묶음만 다시 받는다 — 묶음끼리 동시에.
옵션은 무거워서 **한국 17:00 ~ 05:30(미국장 앞뒤)에만** 다시 받는다. 그 밖에는 마지막 값을 낸다(서버가 막 떠서 한 번도
없으면 그때만 한 번 받는다). 응답 `ttl` 이 묶음별 수명이다.
**받는 것은 상류(8765)다** — 상류가 있는 서버는 넘긴다(kis_proxy 의 `_handle_market`). KIS 예산은 안 쓴다.
"""
import csv
import io
import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))
ET = ZoneInfo("America/New_York")
TIMEOUT = 20
UA = "Mozilla/5.0"     # 야후는 긴 브라우저 이름이면 429 로 막는다 — 짧은 이름은 200(market_index.py · 10-15 실측)

TTL = {"futures": 5 * 60, "options": 30 * 60, "econ": 60 * 60, "fomc": 60 * 60, "vix": 24 * 3600}
OPTIONS_WINDOW = ((17, 0), (5, 30))      # 한국 시각 — 이 사이에만 옵션을 다시 받는다 (밤을 넘긴다)
WAIT = 40                                # 묶음 받기를 기다리는 한도(초) — 넘으면 있는 값으로 낸다

FUTURES = (("ES=F", "S&P 500 선물"), ("NQ=F", "나스닥 100 선물"), ("YM=F", "다우 선물"), ("RTY=F", "러셀 2000 선물"),
           ("^DJI", "다우 지수"), ("^RUT", "러셀 2000 지수"), ("^TYX", "미국 30년물 금리"),
           ("^VIX9D", "VIX 9일"), ("^VVIX", "VVIX(VIX 의 변동성)"))
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%s?range=1d&interval=5m"
CBOE_SPX = "https://cdn-api.cboe.com/api/global/delayed_quotes/options/_SPX.json"
CBOE_VIX_CSV = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
NASDAQ_ECON = "https://api.nasdaq.com/api/calendar/economicevents?date=%s"
NYFED_EFFR = "https://markets.newyorkfed.org/api/rates/unsecured/effr/last/1.json"
MONTH_CODE = "FGHJKMNQUVXZ"              # 선물 달 기호 1~12월
CAL_PATH = __import__("os").path.join(__import__("os").path.dirname(__file__), "..", "data", "market-calendar.json")
STRADDLE_FACTOR = 0.85                   # 등가격 스트래들 × 0.85 = 시장이 보는 예상 변동폭(옵션 시장의 흔한 근사 · 시황분석1 조사)

_lock = threading.Lock()
_state = {k: {"at": 0.0, "data": None, "error": None, "fetchedAt": None} for k in TTL}
_busy = {k: threading.Lock() for k in TTL}


def _get(url, as_text=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/csv, */*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read().decode("utf-8", "replace")
    return raw if as_text else json.loads(raw)


def _num(x):
    try:
        v = float(str(x).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None
    return v


# ── 묶음 다섯 ────────────────────────────────────────────────────────

def _futures():
    rows, errs = [], {}
    for sym, name in FUTURES:
        try:
            meta = _get(YAHOO_URL % urllib.parse.quote(sym))["chart"]["result"][0]["meta"]
            v, prev, t = _num(meta.get("regularMarketPrice")), _num(meta.get("chartPreviousClose")), meta.get("regularMarketTime")
            if v is None or not prev or not t:
                raise ValueError("값이 비어 왔습니다")
            rows.append({"sym": sym, "name": name, "v": v, "prev": prev, "pct": round((v / prev - 1) * 100, 2),
                         "at": datetime.fromtimestamp(t, KST).isoformat(timespec="minutes")})
        except Exception as e:
            errs[sym] = safe_message(e, 120)
            rows.append({"sym": sym, "name": name, "v": None, "prev": None, "pct": None, "at": None})
    if all(r["v"] is None for r in rows):
        raise RuntimeError("야후에서 하나도 못 받았습니다 — " + "; ".join("%s %s" % kv for kv in list(errs.items())[:2]))
    return {"rows": rows, "errors": errs, "source": "야후 파이낸스(10분쯤 늦음)"}


def _parse_opt(sym):
    """SPXW261027C07700000 → (만기 date, 'C'|'P', 행사가). 모양이 다르면 None."""
    i = next((k for k, ch in enumerate(sym) if ch.isdigit()), -1)
    if i < 0 or len(sym) < i + 15:
        return None
    try:
        exp = datetime.strptime(sym[i:i + 6], "%y%m%d").date()
        return exp, sym[i + 6], int(sym[i + 7:i + 15]) / 1000.0
    except ValueError:
        return None


def _options():
    d = _get(CBOE_SPX)["data"]
    spot = _num(d.get("current_price"))
    if not spot:
        raise ValueError("SPX 지금 값이 비어 왔습니다")
    now_et = datetime.now(ET)
    today_et = now_et.date()
    # 미국 장이 끝난 뒤(16:15 ET 뒤)면 오늘 만기는 이미 끝났다 — 매수·매도 호가가 0 이라 셈이 안 된다(10-27 12:00 실측)
    first = today_et + timedelta(days=1) if (now_et.hour, now_et.minute) >= (16, 15) else today_et
    chain = {}
    oi = {"C": 0.0, "P": 0.0}
    for o in d.get("options") or []:
        p = _parse_opt(o.get("option") or "")
        if not p:
            continue
        exp, cp, k = p
        oi[cp] = oi.get(cp, 0.0) + (_num(o.get("open_interest")) or 0)
        if exp >= first:
            chain.setdefault(exp, {}).setdefault(k, {})[cp] = o
    if not chain:
        raise ValueError("남은 만기가 없습니다")
    exp = min(chain)
    strikes = [k for k, v in chain[exp].items() if "C" in v and "P" in v]
    if not strikes:
        raise ValueError("등가격 줄을 못 찾았습니다")
    atm = min(strikes, key=lambda k: abs(k - spot))

    def mid(o):
        b, a = _num(o.get("bid")), _num(o.get("ask"))
        return (b + a) / 2 if b is not None and a and a >= b else None
    c, p = mid(chain[exp][atm]["C"]), mid(chain[exp][atm]["P"])
    straddle = (c + p) if c is not None and p is not None else None
    move = straddle * STRADDLE_FACTOR if straddle is not None else None
    return {
        "spot": spot, "spotAt": d.get("last_trade_time"), "iv30": _num(d.get("iv30")),
        "expiry": exp.isoformat(), "atmStrike": atm,
        "callMid": c, "putMid": p, "straddle": round(straddle, 2) if straddle is not None else None,
        "expectedMove": round(move, 2) if move is not None else None,
        "expectedMovePct": round(move / spot * 100, 2) if move is not None else None,
        "putCallOI": round(oi["P"] / oi["C"], 3) if oi["C"] else None,
        "factor": STRADDLE_FACTOR,
        "source": "Cboe 지연 시세(15분 늦음)",
        "note": "가장 가까운 만기 등가격 스트래들(매수·매도 가운데 값 합) × %.2f · 풋콜은 모든 만기 미결제 합" % STRADDLE_FACTOR,
    }


def _clean(v):
    v = (v or "").replace("&nbsp;", " ").strip()
    return v or None


def _econ():
    today_et = datetime.now(ET).date()
    rows, errs = [], {}
    for day in (today_et, today_et + timedelta(days=1)):
        try:
            # 나스닥은 `date=` 에 하루 뒤 날짜를 넣어야 그날(미 동부) 일정이 온다 — 10-27 실측: date=2026-10-27 이
            # 월요일(10-26) 발표인 시카고 연준 국가활동지수 · 댈러스 연준 제조업을 냈고 date=2026-10-26 은 미국 줄 0
            j = _get(NASDAQ_ECON % (day + timedelta(days=1)).isoformat())
            for r in ((j.get("data") or {}).get("rows") or []):
                if (r.get("country") or "").strip() != "United States":
                    continue
                rows.append({"date": day.isoformat(), "time": _clean(r.get("gmt")), "name": _clean(r.get("eventName")),
                             "actual": _clean(r.get("actual")), "consensus": _clean(r.get("consensus")),
                             "previous": _clean(r.get("previous"))})
        except Exception as e:
            errs[day.isoformat()] = safe_message(e, 120)
    if errs and not rows:
        raise RuntimeError("나스닥 일정을 못 받았습니다 — " + "; ".join(errs.values()))
    return {"rows": rows, "errors": errs, "source": "나스닥 경제지표 일정",
            "dateNote": "date 는 미 동부 날짜 — 나스닥에는 하루 뒤 날짜로 물어야 그날 것이 온다(10-27 실측)",
            "timeNote": "time 칸은 나스닥이 「gmt」 로 이름 붙인 값 그대로 — 값은 미 동부 시각으로 보이나 확인하지 못했다"}


def _next_fomc():
    with open(CAL_PATH, encoding="utf-8") as f:
        ev = json.load(f).get("events") or []
    today_et = datetime.now(ET).date()
    days = sorted(date.fromisoformat(e.get("endDate") or e["date"]) for e in ev
                  if (e.get("result") or {}).get("type") == "fomc")
    later = [d for d in days if d >= today_et]
    return (later[0] if later else None), days


def _zq(y, m):
    sym = "ZQ%s%02d.CBT" % (MONTH_CODE[m - 1], y % 100)
    meta = _get(YAHOO_URL % urllib.parse.quote(sym))["chart"]["result"][0]["meta"]
    v = _num(meta.get("regularMarketPrice"))
    if v is None:
        raise ValueError(sym + " 값이 비어 왔습니다")
    return sym, round(100 - v, 4)


def _fomc():
    meet, all_days = _next_fomc()
    if not meet:
        raise RuntimeError("일정표(data/market-calendar.json)에 남은 FOMC 가 없습니다 — 일정표를 갱신할 때입니다")
    effr = (_get(NYFED_EFFR).get("refRates") or [{}])[0]
    before = _num(effr.get("percentRate"))
    if before is None:
        raise ValueError("뉴욕 연준 실효 금리가 비어 왔습니다")
    y, m = meet.year, meet.month
    n = (date(y + (m == 12), m % 12 + 1, 1) - date(y, m, 1)).days
    d = meet.day                                  # 결정 날까지는 옛 금리 · 다음 날부터 새 금리
    nxt_y, nxt_m = (y + (m == 12), m % 12 + 1)
    next_has_meeting = any(x.year == nxt_y and x.month == nxt_m for x in all_days)
    if n - d < 7 and not next_has_meeting:        # 달 끝 회의 — 그 달 선물로는 새 금리 날이 짧아 다음 달 선물을 쓴다(CME 방법)
        sym, after = _zq(nxt_y, nxt_m)
        how = "다음 달 선물(%s) = 회의 뒤 금리" % sym
    else:
        sym, avg = _zq(y, m)
        after = round((avg - before * d / n) / ((n - d) / n), 4)
        how = "그 달 선물(%s) 평균에서 결정 날까지의 실효 금리를 빼서 셈" % sym
    chg = round((after - before) * 100, 1)        # bp
    return {
        "meeting": meet.isoformat(), "effr": before, "effrDate": effr.get("effectiveDate"),
        "target": [_num(effr.get("targetRateFrom")), _num(effr.get("targetRateTo"))],
        "impliedAfter": after, "changeBp": chg,
        "cut25Prob": round(max(0.0, min(1.0, -chg / 25.0)) * 100, 1),
        "hike25Prob": round(max(0.0, min(1.0, chg / 25.0)) * 100, 1),
        "how": how, "source": "야후 연방기금 선물 + 뉴욕 연준 실효 금리",
        "note": "CME FedWatch 방법을 줄인 셈 — 25bp 한 번만 본다(50bp 이상은 확률이 100% 에서 잘림)",
    }


def _vix():
    text = _get(CBOE_VIX_CSV, as_text=True)
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            rows.append({"date": datetime.strptime(r["DATE"], "%m/%d/%Y").date().isoformat(), "close": float(r["CLOSE"])})
        except (KeyError, ValueError):
            continue
    rows = rows[-252:]
    if not rows:
        raise ValueError("VIX 이력이 비어 왔습니다")
    last = rows[-1]["close"]
    closes = sorted(x["close"] for x in rows)
    pct = round(sum(1 for c in closes if c <= last) / len(closes) * 100, 1)
    return {"rows": rows, "last": last, "lastDate": rows[-1]["date"], "pctile1y": pct,
            "min1y": closes[0], "max1y": closes[-1], "source": "Cboe VIX 일별 이력"}


MAKERS = {"futures": _futures, "options": _options, "econ": _econ, "fomc": _fomc, "vix": _vix}


# ── 받기 · 내기 ─────────────────────────────────────────────────────

def _in_options_window(now=None):
    t = (now or datetime.now(KST))
    hm = (t.hour, t.minute)
    start, end = OPTIONS_WINDOW
    return hm >= start or hm < end


def _stale(k, now):
    s = _state[k]
    if s["data"] is None and s["at"] == 0:
        return True                               # 한 번도 안 받았다 — 창 밖이어도 한 번은 받는다
    if now - s["at"] < TTL[k]:
        return False
    return k != "options" or _in_options_window()


def _refresh(k):
    if not _busy[k].acquire(blocking=False):
        return                                    # 이미 받는 중
    try:
        try:
            data, err = MAKERS[k](), None
        except Exception as e:
            data, err = None, safe_message(e, 160)
        with _lock:
            s = _state[k]
            s["at"] = time.time()
            s["error"] = err
            if data is not None:
                s["data"] = data
                s["fetchedAt"] = datetime.now(KST).isoformat(timespec="seconds")
            # 못 받았으면 앞에 받은 값을 그대로 둔다 — 0 · 빈칸으로 덮지 않는다
    finally:
        _busy[k].release()


def outlook():
    now = time.time()
    todo = [k for k in TTL if _stale(k, now)]
    th = [threading.Thread(target=_refresh, args=(k,), daemon=True) for k in todo]
    for t in th:
        t.start()
    end = time.time() + WAIT
    for t in th:
        t.join(max(0.0, end - time.time()))
    with _lock:
        out = {}
        for k, s in _state.items():
            out[k] = {"data": s["data"], "fetchedAt": s["fetchedAt"], "error": s["error"],
                      "ttl": TTL[k], "age": round(time.time() - s["at"], 1) if s["at"] else None}
    got = sum(1 for v in out.values() if v["data"] is not None)
    return {"ok": got > 0, "got": got, "of": len(out), **out,
            "optionsWindow": "%02d:%02d~%02d:%02d" % (OPTIONS_WINDOW[0] + OPTIONS_WINDOW[1]),
            "note": "야후 · 나스닥 · Cboe 는 공식 API 가 아니다(약관 확인 못 함) — 못 받은 묶음은 error · 앞 값 그대로"}
