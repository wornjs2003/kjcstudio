"""우리가 안 받던 바깥 값 셋 — /api/market/world-extra (2026-11-19)

재권님 「https://apt2.me/global_index.jsp 여기 정보들 가져올수있나?」 → 조사 → 「다」 · 「전부다 해줘」 → 바로 받히는 셋을
서버가 받아 내주는 안에 「응」(11-19). apt2.me 를 긁지 않고 원 출처에서 받는다. 화면 자리는 아직 없다(따로 여쭘).

    binance   바이낸스 한국 종목 무기한선물(USDT) — 바이낸스 선물 공개 주소 · 키 없음 · 실시간(24시간)
              표시가(markPrice) · 지수가(indexPrice) · 마지막 체결 · 24시간 등락 · 펀딩비
    skhy      SK하이닉스 미국 상장분(나스닥 SKHY · 2026-07 상장) — KIS 해외 현재가(HHDFS00000300 · 8765 경유)
    eurkrw    원/유로 — 네이버 시장지표(market_index 와 같은 길 · FX_EURKRW) · 최근 두 날로 등락

못 받은 것(조사 11-19 · 이 파일 밖): 삼성전자 런던 GDR(KIS 가 런던을 안 받음 · 공식 길 없음 — 「영영」 이 아니라 「아직」) ·
외국인 코스피200 선물 순매수(KIS 시장 투자자 조회에 선물 코드를 못 찾음 — 「아직」) · 대차잔고(금융투자협회 · 공공데이터 키 신청 — 「아직」).

셈은 이 파일 한 곳 · 화면은 받은 대로 그린다. 셋을 따로 TTL 마다 받고, 못 받으면 앞 값을 두고 「못 받음」 을 함께 낸다
(「못 쟀으면 0 이 아니라 「못 쟀다」 고 낸다」). 누가 부를 때만 받는다 — 화면이 없는 동안은 바깥을 안 부른다.
"""
import json
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import market_index
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))
TIMEOUT = 4                   # 바깥 한 번 부를 때 기다리는 한도(초) — 바이낸스는 여덟 번을 함께 부른다
WAIT_SEC = 5                  # 부름 하나가 받는 일을 기다리는 한도(초) — 넘으면 앞 값을 낸다
UA = "Mozilla/5.0 (KJC Holdings)"

#: 받는 간격(초) — 바이낸스는 24시간 실시간이라 짧게 · SKHY 는 해외 지수와 같게(kis_proxy OVERSEAS_TTL) · 유로는 시장지표와 같게
TTL = {"binance": 10, "skhy": 60, "eurkrw": market_index.RECENT_TTL}

BINANCE_URL = "https://fapi.binance.com/fapi/v1/"
#: 바이낸스 선물에 있는 한국 쪽 무기한선물(11-19 exchangeInfo 로 잼 — 「CSOP…2L」 레버리지 ETF · SAMSUNGEM 은 뺌) · 기호 · 이름
BINANCE_SYMBOLS = [
    ("SKHYNIXUSDT", "SK하이닉스"),
    ("SAMSUNGUSDT", "삼성전자"),
    ("HYUNDAIUSDT", "현대차"),
    ("EWYUSDT", "한국 ETF(EWY)"),
]
SKHY = {"excd": "NAS", "symb": "SKHY", "name": "SK하이닉스 미국 상장분(나스닥 SKHY)"}
EURKRW = {"cat": "exchange", "code": "FX_EURKRW", "name": "원/유로"}

SOURCES = {
    "binance": "바이낸스 선물(USDT 무기한) · 실시간",
    "skhy": "한국투자증권 해외 현재가 · 나스닥",
    "eurkrw": "네이버 시장지표(하나은행 고시) · 날마다",
}

_lock = threading.Lock()      # _cache · _busy 를 고칠 때만 쥔다 — 받는 동안은 안 쥔다
_busy = set()                 # 지금 받는 중인 이름
_cache = {}                   # 이름 → {"at": 받은 시각(초), "data": …, "err": 못 받은 까닭}


def _num(x):
    try:
        v = float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return v


def _bget(path):
    req = urllib.request.Request(BINANCE_URL + path, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _binance():
    paths = [q + sym for sym, _ in BINANCE_SYMBOLS for q in ("premiumIndex?symbol=", "ticker/24hr?symbol=")]
    with ThreadPoolExecutor(len(paths)) as ex:            # 여덟을 함께 — 하나가 막혀도 TIMEOUT 한 번이면 끝난다
        got = list(ex.map(_bget, paths))
    out = []
    for k, (sym, name) in enumerate(BINANCE_SYMBOLS):
        p, t = got[2 * k], got[2 * k + 1]
        out.append({"symbol": sym, "name": name, "mark": _num(p.get("markPrice")), "index": _num(p.get("indexPrice")),
                    "last": _num(t.get("lastPrice")), "open24h": _num(t.get("openPrice")),
                    "chgPct24h": _num(t.get("priceChangePercent")), "funding": _num(p.get("lastFundingRate")),
                    "at": datetime.fromtimestamp((p.get("time") or 0) / 1000, KST).strftime("%Y-%m-%d %H:%M:%S")})
    return out


def _skhy(kp):
    d = kp.kis_get(kp.load_secrets(), "/uapi/overseas-price/v1/quotations/price",
                   {"AUTH": "", "EXCD": SKHY["excd"], "SYMB": SKHY["symb"]}, "HHDFS00000300") or {}
    o = d.get("output") or {}
    last, base = _num(o.get("last")), _num(o.get("base"))
    if not last:
        raise ValueError("현재가가 비었음(%s)" % (d.get("msg1") or "응답 없음"))
    return {"symbol": SKHY["symb"], "name": SKHY["name"], "last": last, "base": base,
            "chgPct": round((last - base) / base * 100, 2) if base else None, "unit": "달러"}


def _eurkrw():
    rows = market_index._page(EURKRW, 1, 2)       # 최근 것부터 두 날
    if not rows:
        raise ValueError("빈 응답")
    d, c = rows[0][0], rows[0][4]
    prev = rows[1][4] if len(rows) > 1 else None
    return {"name": EURKRW["name"], "date": d, "value": c, "prev": prev,
            "chgPct": round((c - prev) / prev * 100, 2) if prev else None, "unit": "원"}


_FETCH = {"binance": lambda kp: _binance(), "skhy": _skhy, "eurkrw": lambda kp: _eurkrw()}


def _fetch(name, kp):
    """잠금 밖에서 받는다 — 받는 동안 다른 부름은 앞 값을 바로 가져간다(11-19 개념정의 검수 덧 · 잠금 안에서 받으면 바이낸스가 막힐 때 80초 넘게 줄이 섰다)."""
    prev = _cache.get(name) or {}
    try:
        c = {"at": time.time(), "data": _FETCH[name](kp), "err": None}
    except Exception as e:                      # 못 받으면 앞 값을 두고 까닭만 붙인다
        c = {"at": time.time(), "data": prev.get("data"), "err": safe_message(e, 120)}
        print(f"[바깥 값] {name} 못 받음 — {c['err']}", flush=True)
    with _lock:
        _cache[name] = c
        _busy.discard(name)


def payload(kp):
    """kp — 서버 본체 모듈(kis_proxy) · KIS 를 그 길(kis_get · 8765 경유)로 부른다.

    낡은 것만 받는데, 받는 일은 따로 돌리고 WAIT_SEC 까지만 기다린다 — 그 안에 못 끝나면 앞 값(없으면 빈 값)을 내고
    받는 일은 뒤에서 마저 끝나 다음 부름에 나온다. 같은 이름을 둘이 함께 받지 않는다(_busy)."""
    now = time.time()
    run = []
    with _lock:
        for n in _FETCH:
            c = _cache.get(n)
            if (not c or now - c["at"] >= TTL[n]) and n not in _busy:
                _busy.add(n)
                t = threading.Thread(target=_fetch, args=(n, kp), daemon=True)
                run.append(t)
    for t in run:
        t.start()
    end = time.time() + WAIT_SEC
    for t in run:
        t.join(max(0, end - time.time()))
    with _lock:
        got = {n: _cache.get(n) or {"at": now, "data": None, "err": "받는 중"} for n in _FETCH}
    data = {n: got[n]["data"] for n in got}
    data.update(sources=SOURCES,
                fail={n: got[n]["err"] for n in got if got[n]["err"]},
                fetchedAt={n: datetime.fromtimestamp(got[n]["at"], KST).strftime("%Y-%m-%d %H:%M:%S") for n in got if got[n]["data"]})
    return {"ok": any(got[n]["data"] for n in got), "data": data, "meta": {"ttlSec": TTL}}
