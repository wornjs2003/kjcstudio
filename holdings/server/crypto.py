# -*- coding: utf-8 -*-
"""가상자산 — 홀딩스 실시간 순위 「가상자산」 칩의 대표 열 종목과 큰 차트 일봉 (2026-10-14 · 재권님 「(실시간 순위에) 더하는 쪽으로 ·
가상자산은 주로 많이 참고하거나 대표되는 거 10개만 추려서 넣어주면 될 거 같아」 · 「응」 · 창구 경유).

값은 **업비트 공개 시세**(키 없음)에서 받는다. KIS 에는 가상자산이 없다(개발1 조사 · 10-14). 브라우저가 직접 안 부르고 서버가 받아 든다.

    GET /api/market/crypto              열 종목 — 원화 가격 · 등락률(한국 09:00 기준) · 24시간 거래대금 · 시장지표 칩과 같은 모양(last · prev)
    GET /api/market/indicator?key=btc   그 종목 일봉 200개 — 시장지표와 같은 응답 모양이라 큰 차트가 같은 길로 그린다(kis_proxy 가 key 로 가른다)

── 어떤 열인가 (고른 기준 — 2026-10-14 12:2x 실측 · 주식페이지_개발) ──

**세계 시가총액 순위 위에서부터, 업비트 원화 시장에 있는 것만, 달러에 묶인 코인(스테이블코인)은 뺀다.**
출처 — CoinGecko `api.coingecko.com/api/v3/coins/markets`(시가총액 순) · 업비트 `api.upbit.com/v1/market/all`.
그날 빠진 것 — BNB · 지캐시 · 하이퍼리퀴드 · 모네로(업비트 원화에 없음). 다음 후보 — 비트코인캐시 · 아발란체 · 수이.
거래대금 순으로 고르지 않은 까닭 — 그날 급등한 코인이 섞여 날마다 목록이 바뀐다. **목록은 아래 ITEMS 한 곳이다.**

── 한도 (응답 머리 `remaining-req` · 10-14 실측) ──

    현재가  group=ticker  · 일봉 group=candles — **IP 하나에 초당 10 · 분당 600** (limit-by-ip: Yes)

현재가는 열 종목을 **한 번에 한 건**으로 받아 `TICKER_TTL` 동안 든다. 일봉은 종목마다 누를 때 두 건(한 번에 200개라 1년을 채우려고) ·
`CANDLE_TTL` 동안 든다.
화면은 주기로 묻지 않는다 — 칩을 누를 때 받는다. **받는 것은 상류(8765)다** — 상류가 있는 서버는 넘긴다(kis_proxy 의 `_handle_market`).

**못 받은 값은 0 이 아니라 `last: null` · `error` 다.**
"""
import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from secrets_guard import safe_message

TICKER_URL = "https://api.upbit.com/v1/ticker?markets=%s"
CANDLE_URL = "https://api.upbit.com/v1/candles/days?market=%s&count=%d"
CANDLE_DAYS = 365             # 큰 차트 머리가 「1년」 이라 1년을 채운다 — 한 번에 200개까지라 두 번 받는다
TICKER_TTL = 10                # 현재가를 들고 있는 초 — 칩을 누를 때만 묻는다
CANDLE_TTL = 10 * 60           # 일봉을 들고 있는 초
CANDLE_COUNT = 200             # 업비트 한 번에 주는 최대
TIMEOUT = 10
KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

# 세계 시가총액 순 — 위 「어떤 열인가」. digits 는 원화 가격 소수 자리(업비트 원화 호가가 100원 아래만 소수)
ITEMS = [
    {"key": "btc", "name": "비트코인", "code": "KRW-BTC", "sym": "BTC"},
    {"key": "eth", "name": "이더리움", "code": "KRW-ETH", "sym": "ETH"},
    {"key": "xrp", "name": "엑스알피(리플)", "code": "KRW-XRP", "sym": "XRP"},
    {"key": "sol", "name": "솔라나", "code": "KRW-SOL", "sym": "SOL"},
    {"key": "trx", "name": "트론", "code": "KRW-TRX", "sym": "TRX"},
    {"key": "doge", "name": "도지코인", "code": "KRW-DOGE", "sym": "DOGE"},
    {"key": "link", "name": "체인링크", "code": "KRW-LINK", "sym": "LINK"},
    {"key": "ada", "name": "에이다", "code": "KRW-ADA", "sym": "ADA"},
    {"key": "near", "name": "니어프로토콜", "code": "KRW-NEAR", "sym": "NEAR"},
    {"key": "xlm", "name": "스텔라루멘", "code": "KRW-XLM", "sym": "XLM"},
]
BY_KEY = {i["key"]: i for i in ITEMS}
SOURCE = "업비트 원화 시장"

_lock = threading.Lock()
_tick = {"at": 0.0, "rows": {}, "err": None, "fetchedAt": None}
_bars = {}                     # key → {"at", "bars", "err"}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _digits(price):
    return 0 if price is None or price >= 100 else (2 if price >= 1 else 4)


def _meta(it, price=None):
    return {"key": it["key"], "name": it["name"], "sym": it["sym"], "group": "가상자산", "unit": "원",
            "digits": _digits(price), "kind": "candle", "freq": None}


def _refresh_tick():
    now = time.time()
    if now - _tick["at"] < TICKER_TTL:
        return
    try:
        j = _get(TICKER_URL % urllib.parse.quote(",".join(i["code"] for i in ITEMS), safe=","))
        rows = {x.get("market"): x for x in (j if isinstance(j, list) else [])}
        _tick.update(at=now, rows=rows, err=None, fetchedAt=datetime.now(KST).isoformat(timespec="seconds"))
    except Exception as e:
        _tick.update(at=now, err=safe_message(e, 160))   # 못 받으면 든 값을 그대로 둔다


def items():
    with _lock:
        _refresh_tick()
        out = []
        for it in ITEMS:
            x = _tick["rows"].get(it["code"])
            price = x.get("trade_price") if x else None
            prev = x.get("prev_closing_price") if x else None
            d = str(x.get("trade_date_kst") or "") if x else ""
            day = "%s-%s-%s" % (d[:4], d[4:6], d[6:8]) if len(d) == 8 else None
            out.append({**_meta(it, price),
                        "last": {"d": day, "c": price} if price is not None else None,
                        "prev": {"d": None, "c": prev} if prev is not None else None,
                        "pct": round(x["signed_change_rate"] * 100, 2) if x and x.get("signed_change_rate") is not None else None,
                        "value24": x.get("acc_trade_price_24h") if x else None,
                        "error": None if price is not None else (_tick["err"] or "받은 값이 없습니다")})
        return {"ok": any(i["last"] for i in out), "source": SOURCE, "basis": "등락률은 한국 09:00 기준 · 24시간 거래대금",
                "fetchedAt": _tick["fetchedAt"], "cacheTtlSec": max(0, int(TICKER_TTL - (time.time() - _tick["at"]))),
                "items": out}


def indicator(key):
    """그 종목 일봉 — 시장지표 indicator() 와 같은 모양. 모르는 key 면 None."""
    it = BY_KEY.get(key)
    if not it:
        return None
    with _lock:
        now = time.time()
        got = _bars.get(key)
        if not got or now - got["at"] >= CANDLE_TTL:
            try:
                j = _get(CANDLE_URL % (urllib.parse.quote(it["code"]), CANDLE_COUNT))
                j = j if isinstance(j, list) else []
                if len(j) >= CANDLE_COUNT:      # 앞 해를 마저 — 가장 오래된 봉의 시각(UTC) 앞에서 끊어 한 번 더
                    old = min(str(r.get("candle_date_time_utc") or "") for r in j)
                    more = _get(CANDLE_URL % (urllib.parse.quote(it["code"]), CANDLE_DAYS - CANDLE_COUNT)
                                + "&to=" + urllib.parse.quote(old + "Z"))
                    j += more if isinstance(more, list) else []
                bars = [{"d": str(r.get("candle_date_time_kst") or "")[:10], "o": r.get("opening_price"),
                         "h": r.get("high_price"), "l": r.get("low_price"), "c": r.get("trade_price")}
                        for r in (j if isinstance(j, list) else []) if r.get("trade_price") is not None]
                bars = sorted({b["d"]: b for b in bars}.values(), key=lambda b: b["d"])[-CANDLE_DAYS:]
                got = {"at": now, "bars": bars, "err": None}
            except Exception as e:
                got = {"at": now, "bars": (got or {}).get("bars", []), "err": safe_message(e, 160)}
            _bars[key] = got
        bars = got["bars"]
        return {"ok": bool(bars), "source": SOURCE, "fetchedAt": datetime.now(KST).isoformat(timespec="seconds"),
                "cacheTtlSec": max(0, int(CANDLE_TTL - (now - got["at"]))),
                "item": _meta(it, bars[-1]["c"] if bars else None), "bars": bars, "fixed": 0,
                "error": None if bars else (got["err"] or "받은 값이 없습니다")}
