#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KJC Holdings 로컬 개발 서버 + 한국투자증권(KIS) API 중계.

브라우저는 앱키를 절대 보지 못한다. 앱키는 이 서버 프로세스 안에만 있고,
브라우저는 `/api/kis/...` 로만 요청한다.

실행:
    python server/kis_proxy.py           (holdings 폴더 기준)
    python server/kis_proxy.py --port 8765

키 설정:
    holdings/secrets.json 파일을 만들고 아래 형태로 채운다.
    (secrets.json 은 .gitignore 에 등록되어 있어 커밋되지 않는다)

    {
      "kis": {
        "mode": "vts",
        "app_key": "발급받은 App Key",
        "app_secret": "발급받은 App Secret",
        "account": "12345678-01"
      }
    }

    mode: "vts" = 모의투자, "prod" = 실전투자
"""

import argparse
import json
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# Windows 기본 콘솔(cp949)에서 한글·기호 출력에 실패해 서버가 죽지 않도록 고정한다.
for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass

HOLDINGS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS_PATH = os.path.join(HOLDINGS_DIR, "secrets.json")
TOKEN_CACHE_PATH = os.path.join(HOLDINGS_DIR, ".kis-token-cache.json")

HOSTS = {
    "vts": "https://openapivts.koreainvestment.com:29443",   # 모의투자
    "prod": "https://openapi.koreainvestment.com:9443",      # 실전투자
}
MODE_LABEL = {"vts": "모의투자", "prod": "실전투자"}

# 시장 구분
#   J  = KRX 정규장만 (09:00~15:30)
#   NX = 넥스트레이드(대체거래소)만
#   UN = 통합 — 정규장 + 넥스트레이드. 08:00~20:00 내내 값이 움직인다.
# 통합을 쓰면 거래량도 양쪽이 합산된다.
MARKET_DIV = "UN"

# 토큰 발급은 1분에 1회 이상 시도하면 차단된다. 최소 간격을 강제한다.
TOKEN_MIN_INTERVAL = 70
_last_token_attempt = 0.0

# 시세 캐시: KIS 호출량을 줄이는 핵심 장치.
# 같은 종목을 이 시간 안에 다시 요청하면 KIS 를 부르지 않고 캐시로 답한다.
# 값을 키우면 호출이 줄고, 줄이면 더 자주 갱신된다.
PRICE_CACHE_TTL = 10
_price_cache = {}          # code -> (저장시각, 데이터)
_cache_lock = threading.Lock()
_stats = {"kis_calls": 0, "cache_hits": 0}


def _cache_get(code):
    with _cache_lock:
        hit = _price_cache.get(code)
        if hit and (time.time() - hit[0]) < PRICE_CACHE_TTL:
            _stats["cache_hits"] += 1
            return hit[1]
    return None


def _cache_put(code, data):
    with _cache_lock:
        _price_cache[code] = (time.time(), data)


# ── 호출 예산 ────────────────────────────────────────────────────────────
# KIS 는 초당 호출 건수를 제한한다(초과 시 EGW00201).
#
# 실전 계좌 기본 한도는 초당 20건이다. 조건을 채우면 40~100건까지 늘려 준다
# (2026-08-31 한국투자증권 오픈API 활성화 캠페인 보도자료 기준, 2026-12-31 까지).
# 공식 개발자 포털과 GitHub 저장소에는 숫자가 적혀 있지 않아 보도자료를 근거로 삼았다.
# 모의 계좌 한도는 자료마다 달라 확인하지 못했다.
#
# 아래 기준값은 실제 한도(20)보다 낮게 잡아 두었다. 여유를 더 두려는 것이고,
# 지금 쓰는 양은 실제 한도의 5% 수준이다. 자세한 내용은 docs/data-sources.md 참고.
#
#   KIS_LIMIT_PER_SEC : 계정에 허용된다고 보는 한도 (기준값)
#   BUDGET_RATIO      : 그중 실제로 쓸 비율. 0.1 = 한도의 10%
#
# 이 두 값만 바꾸면 호출량 전체가 조절된다.
KIS_LIMIT_PER_SEC = 10.0
BUDGET_RATIO = 0.1                                  # 한도의 1/10 만 사용
KIS_CALLS_PER_SEC = KIS_LIMIT_PER_SEC * BUDGET_RATIO   # = 초당 1건
KIS_MIN_INTERVAL = 1.0 / KIS_CALLS_PER_SEC             # = 1.0초 간격

_rate_lock = threading.Lock()
_last_call_at = 0.0
_call_times = []                 # 최근 호출 시각 (사용량 측정용)


def _rate_limit():
    """KIS 호출 사이에 최소 간격을 강제한다. 모든 스레드가 공유한다."""
    global _last_call_at
    with _rate_lock:
        wait = _last_call_at + KIS_MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call_at = time.monotonic()
        now = time.time()
        _call_times.append(now)
        # 1시간보다 오래된 기록은 버린다
        cutoff = now - 3600
        while _call_times and _call_times[0] < cutoff:
            _call_times.pop(0)


def usage_stats():
    """실제 호출량을 돌려준다 (재권님이 눈으로 확인하기 위한 용도)."""
    now = time.time()
    last_10s = sum(1 for t in _call_times if t > now - 10)
    last_60s = sum(1 for t in _call_times if t > now - 60)
    last_1h = len(_call_times)
    return {
        "limitPerSec": KIS_LIMIT_PER_SEC,
        "budgetRatio": BUDGET_RATIO,
        "budgetPerSec": KIS_CALLS_PER_SEC,
        "minIntervalSec": KIS_MIN_INTERVAL,
        "calls10s": last_10s,
        "calls60s": last_60s,
        "calls1h": last_1h,
        "perSec60s": round(last_60s / 60.0, 3),
        "budgetUsedPct": round((last_60s / 60.0) / KIS_CALLS_PER_SEC * 100, 1) if KIS_CALLS_PER_SEC else 0,
        "limitUsedPct": round((last_60s / 60.0) / KIS_LIMIT_PER_SEC * 100, 1) if KIS_LIMIT_PER_SEC else 0,
        "cacheHits": _stats["cache_hits"],
        "totalCalls": _stats["kis_calls"],
        "priceCacheTtl": PRICE_CACHE_TTL,
    }


# ---------------------------------------------------------------- 설정 읽기

def load_secrets():
    """secrets.json 을 읽는다. 없으면 None (정적 서버로만 동작)."""
    if not os.path.exists(SECRETS_PATH):
        return None
    try:
        with open(SECRETS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except ValueError as e:
        raise RuntimeError("secrets.json 형식이 잘못되었습니다: %s" % e)

    kis = data.get("kis") or {}
    missing = [k for k in ("app_key", "app_secret") if not kis.get(k)]
    if missing:
        raise RuntimeError("secrets.json 의 kis 항목에 %s 가 없습니다." % ", ".join(missing))

    mode = (kis.get("mode") or "vts").lower()
    if mode not in HOSTS:
        raise RuntimeError('mode 는 "vts"(모의) 또는 "prod"(실전) 여야 합니다.')
    kis["mode"] = mode
    return kis


# ---------------------------------------------------------------- 토큰 관리

def _read_token_cache(mode):
    try:
        with open(TOKEN_CACHE_PATH, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        return None
    if cache.get("mode") != mode:
        return None
    # 만료 5분 전이면 새로 받는다
    if float(cache.get("expires_at", 0)) <= time.time() + 300:
        return None
    return cache.get("access_token")


def _write_token_cache(mode, token, expires_in):
    tmp = {
        "mode": mode,
        "access_token": token,
        "expires_at": time.time() + float(expires_in),
    }
    try:
        with open(TOKEN_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(tmp, f)
    except OSError:
        pass


def get_token(cfg):
    """접근토큰을 얻는다. 캐시가 유효하면 재사용한다."""
    global _last_token_attempt

    cached = _read_token_cache(cfg["mode"])
    if cached:
        return cached

    elapsed = time.time() - _last_token_attempt
    if elapsed < TOKEN_MIN_INTERVAL:
        raise RuntimeError(
            "토큰 재발급 대기 중입니다. %d초 후 다시 시도해 주세요. "
            "(KIS 는 1분에 1회만 발급을 허용합니다)" % int(TOKEN_MIN_INTERVAL - elapsed)
        )
    _last_token_attempt = time.time()

    url = HOSTS[cfg["mode"]] + "/oauth2/tokenP"
    body = json.dumps({
        "grant_type": "client_credentials",
        "appkey": cfg["app_key"],
        "appsecret": cfg["app_secret"],
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"content-type": "application/json; charset=utf-8"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError("토큰 발급 실패 (HTTP %s): %s" % (e.code, detail))
    except urllib.error.URLError as e:
        raise RuntimeError("토큰 발급 실패 (네트워크): %s" % e.reason)

    token = data.get("access_token")
    if not token:
        raise RuntimeError("토큰 발급 응답에 access_token 이 없습니다: %s" % str(data)[:200])

    _write_token_cache(cfg["mode"], token, data.get("expires_in", 86400))
    return token


# ---------------------------------------------------------------- KIS 호출

def kis_get(cfg, path, params, tr_id, _retry=1):
    token = get_token(cfg)
    _rate_limit()
    url = HOSTS[cfg["mode"]] + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "authorization": "Bearer " + token,
        "appkey": cfg["app_key"],
        "appsecret": cfg["app_secret"],
        "tr_id": tr_id,
        "custtype": "P",
        "content-type": "application/json; charset=utf-8",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        # 초당 건수 초과(EGW00201)는 잠깐 쉬었다 한 번만 다시 시도한다.
        if "EGW00201" in detail and _retry > 0:
            time.sleep(1.0)
            return kis_get(cfg, path, params, tr_id, _retry - 1)
        raise RuntimeError("KIS 호출 실패 (HTTP %s): %s" % (e.code, detail))
    except urllib.error.URLError as e:
        raise RuntimeError("KIS 호출 실패 (네트워크): %s" % e.reason)

    if str(data.get("rt_cd", "0")) != "0":
        if data.get("msg_cd") == "EGW00201" and _retry > 0:
            time.sleep(1.0)
            return kis_get(cfg, path, params, tr_id, _retry - 1)
        raise RuntimeError("KIS 오류: %s (%s)" % (data.get("msg1", "알 수 없음"), data.get("msg_cd", "")))
    return data


def fetch_prices(cfg, codes):
    """여러 종목을 한 번에 조회한다.

    KIS 현재가 API 는 한 번에 한 종목만 받으므로 서버가 나눠 호출한다.
    호출 제한(실전 20건/초)에 걸리지 않도록 동시 실행 수를 제한한다.
    """
    from concurrent.futures import ThreadPoolExecutor

    out, errors = {}, {}

    # 1) 캐시에 있는 종목은 KIS 를 부르지 않는다.
    missing = []
    for code in codes:
        cached = _cache_get(code)
        if cached is not None:
            out[code] = cached
        else:
            missing.append(code)

    if not missing:
        return out, errors

    # 토큰을 먼저 한 번 확보해 두면 개별 호출이 동시에 발급을 시도하지 않는다.
    get_token(cfg)

    def one(code):
        try:
            _stats["kis_calls"] += 1
            return code, fetch_price(cfg, code), None
        except RuntimeError as e:
            return code, None, str(e)

    # 동시 실행을 2 로 제한해 KIS 초당 호출 제한에 여유를 둔다.
    with ThreadPoolExecutor(max_workers=2) as pool:
        for code, info, err in pool.map(one, missing):
            if info:
                # 프론트가 쓰는 형태로 맞춘다 (price / prev / amt / pct)
                price = info.get("price")
                amt = info.get("change")
                pct = info.get("changePct")
                prev = (price - amt) if (price is not None and amt is not None) else None
                row = {
                    "price": price, "prev": prev, "amt": amt, "pct": pct,
                    "per": info.get("per"), "pbr": info.get("pbr"),
                    "high52": info.get("high52"), "low52": info.get("low52"),
                    "volume": info.get("volume"), "marketCap": info.get("marketCap"),
                    "open": info.get("open"), "high": info.get("high"),
                    "low": info.get("low"), "name": info.get("name"),
                }
                out[code] = row
                _cache_put(code, row)
            else:
                errors[code] = err
    return out, errors


# ---------------------------------------------------------------- 지수 조회
# 지수는 주식과 다른 창구를 쓴다.
#   주식: inquire-price       / tr_id FHKST01010100 / 시장구분 J / 값 stck_prpr
#   지수: inquire-index-price / tr_id FHPUP02100000 / 시장구분 U / 값 bstp_nmix_prpr
INDEX_DEFS = [
    ("0001", "KOSPI"),
    ("1001", "KOSDAQ"),
    ("2001", "KOSPI200"),
]
INDEX_CHART_TTL = 600      # 일봉은 자주 바뀌지 않으므로 길게 캐시한다
_chart_cache = {}          # code -> (저장시각, series)


def fetch_index(cfg, code):
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-index-price",
        {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": code},
        "FHPUP02100000",
    )
    o = data.get("output") or {}
    return {
        "value": _num(o.get("bstp_nmix_prpr")),
        "change": _num(o.get("bstp_nmix_prdy_vrss")),
        "changePct": _num(o.get("bstp_nmix_prdy_ctrt")),
        "open": _num(o.get("bstp_nmix_oprc")),
        "high": _num(o.get("bstp_nmix_hgpr")),
        "low": _num(o.get("bstp_nmix_lwpr")),
    }


def fetch_index_series(cfg, code, days=60):
    """지수 일봉 종가 시계열 (차트용). 오래된 것부터 정렬해 돌려준다."""
    with _cache_lock:
        hit = _chart_cache.get(code)
        if hit and (time.time() - hit[0]) < INDEX_CHART_TTL:
            return hit[1]

    import datetime
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days * 2 + 30)  # 휴장일 감안해 넉넉히
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice",
        {
            "FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": end.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": "D",
        },
        "FHKUP03500100",
    )
    rows = data.get("output2") or []
    pairs = []
    for r in rows:
        v = _num(r.get("bstp_nmix_prpr"))
        d = r.get("stck_bsop_date")
        if v is not None and d:
            pairs.append((d, v))
    pairs.sort(key=lambda x: x[0])          # 과거 -> 최신
    series = [v for _, v in pairs][-days:]

    with _cache_lock:
        _chart_cache[code] = (time.time(), series)
    return series


def fetch_indices(cfg, with_chart=True):
    out, errors = [], {}
    for code, name in INDEX_DEFS:
        cache_key = "IDX:" + code
        cached = _cache_get(cache_key)
        if cached is not None:
            out.append(cached)
            continue
        try:
            _stats["kis_calls"] += 1
            info = fetch_index(cfg, code)
            series = []
            if with_chart:
                try:
                    _stats["kis_calls"] += 1
                    series = fetch_index_series(cfg, code)
                except RuntimeError:
                    series = []          # 차트만 실패해도 현재값은 보여준다
            row = {
                "code": name, "name": name, "unit": "pt",
                "value": info["value"], "change": info["change"],
                "changePct": info["changePct"], "series": series,
                "source": "KIS",
            }
            out.append(row)
            _cache_put(cache_key, row)
        except RuntimeError as e:
            errors[name] = str(e)
    return out, errors


def _num(v, cast=float):
    try:
        return cast(str(v).strip())
    except (TypeError, ValueError):
        return None


def fetch_price(cfg, code):
    """국내 주식 현재가 조회."""
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-price",
        {"FID_COND_MRKT_DIV_CODE": MARKET_DIV, "FID_INPUT_ISCD": code},
        "FHKST01010100",
    )
    o = data.get("output") or {}
    sign = o.get("prdy_vrss_sign")  # 1상한 2상승 3보합 4하한 5하락
    return {
        "code": code,
        "name": o.get("bstp_kor_isnm"),
        "price": _num(o.get("stck_prpr"), int),
        "change": _num(o.get("prdy_vrss"), int),
        "changePct": _num(o.get("prdy_ctrt")),
        "sign": sign,
        "open": _num(o.get("stck_oprc"), int),
        "high": _num(o.get("stck_hgpr"), int),
        "low": _num(o.get("stck_lwpr"), int),
        "volume": _num(o.get("acml_vol"), int),
        "marketCap": _num(o.get("hts_avls"), int),
        "per": _num(o.get("per")),
        "pbr": _num(o.get("pbr")),
        "eps": _num(o.get("eps")),
        "bps": _num(o.get("bps")),
        "high52": _num(o.get("w52_hgpr"), int),
        "low52": _num(o.get("w52_lwpr"), int),
        "source": "KIS",
        "mode": cfg["mode"],
    }


# ---------------------------------------------------------------- 저장 계층 (SQLite)
# 배포본은 Cloudflare D1 을 쓰고, 로컬은 같은 구조를 SQLite 파일로 둔다.
# 차트는 과거 데이터가 필요한데 볼 때마다 KIS 를 부르면 호출량을 감당할 수 없다.

DB_PATH = os.path.join(HOLDINGS_DIR, "market.db")
_db_lock = threading.Lock()

# ts 형식: 일/주/월/년봉은 YYYYMMDD, 분봉은 YYYYMMDDHHMM
# period: D(일) W(주) M(월) Y(년) 1m(1분) 5m(5분)
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS candles (
         code   TEXT    NOT NULL,
         period TEXT    NOT NULL,
         ts     TEXT    NOT NULL,
         open   INTEGER,
         high   INTEGER,
         low    INTEGER,
         close  INTEGER,
         volume INTEGER,
         PRIMARY KEY (code, period, ts)
       )""",
    "CREATE INDEX IF NOT EXISTS idx_candles ON candles (code, period, ts DESC)",
    """CREATE TABLE IF NOT EXISTS sync_meta (
         key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
       )""",
]

# 기간별 설정
#   fresh_sec : 이 시간이 지나면 최근 구간을 다시 받는다 (장중 당일 캔들 갱신용)
PERIODS = {
    "D":  {"kis": "D", "label": "일",  "fresh_sec": 60,  "span_days": 400},
    "W":  {"kis": "W", "label": "주",  "fresh_sec": 300, "span_days": 2000},
    "M":  {"kis": "M", "label": "월",  "fresh_sec": 600, "span_days": 4000},
    "Y":  {"kis": "Y", "label": "년",  "fresh_sec": 3600, "span_days": 8000},
    "1m": {"kis": None, "label": "1분", "fresh_sec": 30, "span_days": 1},
    "5m": {"kis": None, "label": "5분", "fresh_sec": 30, "span_days": 1},
}

# 분봉 수집 범위 (분 단위). 통합 시장 기준 08:00~20:00
MINUTE_DAY_START = 8 * 60
MINUTE_DAY_END = 20 * 60


def db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def db_init():
    with _db_lock, db_conn() as conn:
        for sql in SCHEMA:
            conn.execute(sql)
    return {"created": len(SCHEMA)}


def db_status():
    with _db_lock, db_conn() as conn:
        r = conn.execute(
            """SELECT COUNT(*) AS rows, COUNT(DISTINCT code) AS codes,
                      MIN(ts) AS firstTs, MAX(ts) AS lastTs
                 FROM candles"""
        ).fetchone()
        per = conn.execute(
            "SELECT period, COUNT(*) AS n FROM candles GROUP BY period"
        ).fetchall()
    return {
        "rows": r["rows"], "codes": r["codes"],
        "firstTs": r["firstTs"], "lastTs": r["lastTs"],
        "byPeriod": {p["period"]: p["n"] for p in per},
    }


def _meta_get(key):
    with _db_lock, db_conn() as conn:
        r = conn.execute("SELECT value FROM sync_meta WHERE key = ?", (key,)).fetchone()
    return r["value"] if r else None


def _meta_set(key, value):
    import datetime
    with _db_lock, db_conn() as conn:
        conn.execute(
            """INSERT INTO sync_meta (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                                             updated_at=excluded.updated_at""",
            (key, str(value), datetime.datetime.now().isoformat(timespec="seconds")),
        )


def fetch_bars_from_kis(cfg, code, period, date_from, date_to):
    """일/주/월/년봉. 같은 API 에서 기간 구분 코드만 바뀐다 (한 번에 최대 100개)."""
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        {
            "FID_COND_MRKT_DIV_CODE": MARKET_DIV, "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": date_from, "FID_INPUT_DATE_2": date_to,
            "FID_PERIOD_DIV_CODE": PERIODS[period]["kis"], "FID_ORG_ADJ_PRC": "0",
        },
        "FHKST03010100",
    )
    out = []
    for r in data.get("output2") or []:
        d = r.get("stck_bsop_date")
        close = _num(r.get("stck_clpr"), int)
        if not d or close is None:
            continue
        out.append({
            "ts": str(d),
            "open": _num(r.get("stck_oprc"), int),
            "high": _num(r.get("stck_hgpr"), int),
            "low": _num(r.get("stck_lwpr"), int),
            "close": close,
            "volume": _num(r.get("acml_vol"), int),
        })
    return out


def fetch_minutes_from_kis(cfg, code, hour="153000"):
    """1분봉. 별도 API 이며 기준 시각부터 과거 30개만 돌려준다."""
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
        {
            "FID_ETC_CLS_CODE": "", "FID_COND_MRKT_DIV_CODE": MARKET_DIV,
            "FID_INPUT_ISCD": code, "FID_INPUT_HOUR_1": hour,
            "FID_PW_DATA_INCU_YN": "Y",
        },
        "FHKST03010200",
    )
    out = []
    for r in data.get("output2") or []:
        d, t = r.get("stck_bsop_date"), r.get("stck_cntg_hour")
        close = _num(r.get("stck_prpr"), int)
        if not d or not t or close is None:
            continue
        out.append({
            "ts": "%s%s" % (d, str(t)[:4]),          # YYYYMMDDHHMM
            "open": _num(r.get("stck_oprc"), int),
            "high": _num(r.get("stck_hgpr"), int),
            "low": _num(r.get("stck_lwpr"), int),
            "close": close,
            "volume": _num(r.get("cntg_vol"), int),
        })
    return out


def fetch_minutes_day(cfg, code):
    """하루치 1분봉을 모은다.

    KIS 분봉 API 는 기준 시각부터 과거 30개만 돌려주므로, 시각을 30분씩
    거슬러 올라가며 여러 번 부른다. 통합 시장이라 넥스트레이드 시간대
    (~20:00)까지 포함한다. 한 번 받아 저장하면 이후에는 최근 구간만 갱신한다.
    """
    bars = {}
    t = MINUTE_DAY_END
    while t >= MINUTE_DAY_START:
        hour = "%02d%02d00" % (t // 60, t % 60)
        try:
            for b in fetch_minutes_from_kis(cfg, code, hour):
                bars[b["ts"]] = b
        except RuntimeError:
            pass          # 해당 구간에 데이터가 없을 수 있다. 계속 진행.
        t -= 30
    return sorted(bars.values(), key=lambda x: x["ts"])


def aggregate_minutes(bars, minutes):
    """1분봉을 N분봉으로 묶는다 (KIS 는 5분봉을 직접 주지 않는다)."""
    buckets = {}
    for b in sorted(bars, key=lambda x: x["ts"]):
        hhmm = b["ts"][8:12]
        slot = (int(hhmm[:2]) * 60 + int(hhmm[2:])) // minutes * minutes
        key = b["ts"][:8] + "%02d%02d" % (slot // 60, slot % 60)
        g = buckets.get(key)
        if not g:
            buckets[key] = {"ts": key, "open": b["open"], "high": b["high"],
                            "low": b["low"], "close": b["close"],
                            "volume": b["volume"] or 0}
        else:
            g["high"] = max(g["high"], b["high"])
            g["low"] = min(g["low"], b["low"])
            g["close"] = b["close"]
            g["volume"] += (b["volume"] or 0)
    return [buckets[k] for k in sorted(buckets)]


def save_candles(code, period, candles):
    if not candles:
        return 0
    with _db_lock, db_conn() as conn:
        conn.executemany(
            """INSERT INTO candles (code, period, ts, open, high, low, close, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(code, period, ts) DO UPDATE SET
                 open=excluded.open, high=excluded.high, low=excluded.low,
                 close=excluded.close, volume=excluded.volume""",
            [(code, period, c["ts"], c["open"], c["high"], c["low"], c["close"], c["volume"])
             for c in candles],
        )
    return len(candles)


def read_candles(code, period, limit):
    with _db_lock, db_conn() as conn:
        rows = conn.execute(
            """SELECT ts, open, high, low, close, volume
                 FROM candles WHERE code = ? AND period = ?
                 ORDER BY ts DESC LIMIT ?""",
            (code, period, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]   # 차트는 과거 -> 최신 순


def get_chart(cfg, code, period, limit):
    """DB 를 먼저 보고, 최근 구간이 오래됐으면 KIS 에서 받아 덮어쓴다.

    당일(또는 최근) 캔들은 장중에 계속 바뀌므로, 마지막 갱신으로부터
    fresh_sec 이 지나면 다시 받아온다. 과거 캔들은 변하지 않으므로 그대로 둔다.
    """
    import datetime
    db_init()
    conf = PERIODS[period]
    rows = read_candles(code, period, limit)

    mkey = "sync:%s:%s" % (code, period)
    last_sync = float(_meta_get(mkey) or 0)
    stale = (time.time() - last_sync) > conf["fresh_sec"]

    fetched = 0
    if not rows or stale:
        if conf["kis"]:                      # 일/주/월/년
            today = datetime.date.today()
            start = today - datetime.timedelta(days=conf["span_days"])
            bars = fetch_bars_from_kis(cfg, code, period,
                                       start.strftime("%Y%m%d"), today.strftime("%Y%m%d"))
        else:                                # 분봉
            # 처음이면 하루치를 모으고(호출 여러 번), 이후에는 최근 구간만 갱신한다
            if rows:
                raw = fetch_minutes_from_kis(cfg, code)
            else:
                raw = fetch_minutes_day(cfg, code)
            bars = aggregate_minutes(raw, 5) if period == "5m" else raw
        fetched = save_candles(code, period, bars)
        _meta_set(mkey, time.time())
        if fetched:
            rows = read_candles(code, period, limit)

    return rows, fetched, ("KIS+DB" if fetched else "DB")


# ---------------------------------------------------------------- HTTP 핸들러

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HOLDINGS_DIR, **kwargs)

    def log_message(self, fmt, *args):
        # 정적 파일 요청 로그는 조용히, API 만 표시
        if "/api/" in (self.path or ""):
            sys.stderr.write("  [API] %s\n" % (self.path,))

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if (self.path or "").startswith("/api/kis/"):
            self._handle_kis()
            return
        super().do_GET()

    def _handle_kis(self):
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path[len("/api/kis/"):].strip("/")
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            cfg = load_secrets()
        except RuntimeError as e:
            self._send_json({"ok": False, "error": str(e)}, 500)
            return

        if route == "health":
            if not cfg:
                self._send_json({
                    "ok": False,
                    "configured": False,
                    "error": "secrets.json 이 없습니다. holdings/secrets.example.json 을 복사해 키를 넣어주세요.",
                })
                return
            try:
                get_token(cfg)
                token_ok, token_err = True, None
            except RuntimeError as e:
                token_ok, token_err = False, str(e)
            self._send_json({
                "ok": token_ok,
                "configured": True,
                "mode": cfg["mode"],
                "modeLabel": MODE_LABEL[cfg["mode"]],
                "tokenOk": token_ok,
                "error": token_err,
            })
            return

        if not cfg:
            self._send_json({
                "ok": False,
                "error": "secrets.json 이 없어 KIS 를 쓸 수 없습니다.",
            }, 503)
            return

        try:
            if route == "price":
                code = (qs.get("code") or [""])[0].strip()
                if not code.isdigit() or len(code) != 6:
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                self._send_json({"ok": True, "data": fetch_price(cfg, code)})
                return

            if route == "stats":
                self._send_json({"ok": True, "data": usage_stats()})
                return

            if route == "db/init":
                self._send_json({"ok": True, "data": db_init()})
                return

            if route == "db/status":
                db_init()
                self._send_json({"ok": True, "data": db_status()})
                return

            if route == "chart":
                code = (qs.get("code") or [""])[0].strip()
                if not code.isdigit() or len(code) != 6:
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                period = (qs.get("period") or ["D"])[0].strip()
                if period not in PERIODS:
                    self._send_json({
                        "ok": False,
                        "error": "period 는 %s 중 하나여야 합니다." % ", ".join(PERIODS),
                    }, 400)
                    return
                try:
                    limit = int((qs.get("limit") or qs.get("days") or ["240"])[0])
                except ValueError:
                    limit = 240
                limit = max(1, min(limit, 1000))
                rows, fetched, source = get_chart(cfg, code, period, limit)
                self._send_json({
                    "ok": True,
                    "data": {"code": code, "period": period, "candles": rows},
                    "meta": {
                        "count": len(rows), "fetched": fetched, "source": source,
                        "label": PERIODS[period]["label"],
                    },
                })
                return

            if route == "indices":
                with_chart = (qs.get("chart") or ["1"])[0] != "0"
                data, errors = fetch_indices(cfg, with_chart)
                self._send_json({"ok": bool(data), "data": data, "errors": errors or None})
                return

            if route == "prices":
                raw = (qs.get("codes") or [""])[0]
                codes = [c.strip() for c in raw.split(",") if c.strip()]
                codes = [c for c in codes if c.isdigit() and len(c) == 6]
                codes = list(dict.fromkeys(codes))[:40]  # 중복 제거, 과다 요청 방지
                if not codes:
                    self._send_json({"ok": False, "error": "codes 에 6자리 종목코드가 없습니다."}, 400)
                    return
                before = _stats["kis_calls"]
                data, errors = fetch_prices(cfg, codes)
                called = _stats["kis_calls"] - before
                self._send_json({
                    "ok": True,
                    "data": data,
                    "errors": errors or None,
                    "meta": {
                        "requested": len(codes),
                        "fromCache": len(codes) - called,
                        "kisCalls": called,
                        "cacheTtl": PRICE_CACHE_TTL,
                        "totalKisCalls": _stats["kis_calls"],
                    },
                })
                return
            self._send_json({"ok": False, "error": "알 수 없는 경로입니다: %s" % route}, 404)
        except RuntimeError as e:
            self._send_json({"ok": False, "error": str(e)}, 502)
        except Exception as e:  # 예기치 못한 오류도 앱키가 새지 않게 요약만
            self._send_json({"ok": False, "error": "서버 오류: %s" % type(e).__name__}, 500)


# ---------------------------------------------------------------- 진입점

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    try:
        cfg = load_secrets()
    except RuntimeError as e:
        cfg = None
        print("  [경고] %s" % e)

    print("-" * 52)
    print("  KJC Holdings - 로컬 서버")
    print("-" * 52)
    print("  대시보드  : http://localhost:%d/" % args.port)
    print("  주식 분석 : http://localhost:%d/analysis/" % args.port)
    if cfg:
        print("  KIS 연동  : 사용 (%s)" % MODE_LABEL[cfg["mode"]])
        print("  상태 확인 : http://localhost:%d/api/kis/health" % args.port)
    else:
        print("  KIS 연동  : 꺼짐 (secrets.json 없음, 정적 서버로만 동작)")
    print("  종료      : Ctrl+C")
    print("-" * 52)
    sys.stdout.flush()

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  서버를 종료했습니다.")
        srv.server_close()


if __name__ == "__main__":
    main()
