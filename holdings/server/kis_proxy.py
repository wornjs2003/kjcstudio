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
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# 같은 폴더(server/)의 모듈들. 스크립트로 실행하므로 바로 잡힌다.
import dart
import news
# 오류 문구에서 비밀을 지운다. 외부 호출 오류를 사람에게 보여줄 때는
# 반드시 이것을 거친다 (2026-09-14 에 인증키가 실제로 샜다).
from secrets_guard import safe_message, scrub

# Windows 기본 콘솔(cp949)에서 한글·기호 출력에 실패해 서버가 죽지 않도록 고정한다.
for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass

HOLDINGS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 정적 파일은 저장소 루트에서 내보낸다. holdings 만 내보내면 화면이
# 함께 쓰는 ../assets/ · ../partials/ 가 404 가 된다 (2026-09-14).
# 배포본도 /holdings/index.html 기준이라, 이렇게 두면 로컬과 배포의
# 경로가 같아진다. 키·DB 경로는 그대로 holdings 안을 가리킨다.
SITE_ROOT = os.path.dirname(HOLDINGS_DIR)

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
#
# 차트는 통합으로 고정한다. 과거 봉이라 "지금 몇 시인가"를 따질 일이 없다.
MARKET_DIV_CHART = "UN"

# 정규장 시간대 (KRX)
KRX_OPEN  = (9, 0)
KRX_CLOSE = (15, 30)
KST = timezone(timedelta(hours=9))


def quote_market_div(now=None):
    """시세를 어느 시장 기준으로 볼지 정한다 (CLAUDE.md 의 시세 표기 규칙).

    정규장 중에는 KRX 값을 그대로 쓴다. 남들이 보는 숫자와 같아야 하기 때문이다.
    장이 끝나면 통합으로 넘겨서, 넥스트레이드에서 더 움직인 값이 있으면 그것을 쓴다.

    통합(UN)을 그냥 써도 되는 이유 — 넥스트레이드에 거래가 없으면 KRX 종가를
    그대로 돌려준다. 2026-09-12 에 실제로 호출해 확인했다.
        삼성전자우 193300 / 흥아해운 1878 / 동양3우B 5750  (NX 는 셋 다 0)
    그래서 종목마다 두 번 부를 필요가 없다.

    공휴일은 가리지 못한다. 휴장일 낮에는 KRX 기준(전일 종가)이 나오는데,
    장이 열리지 않은 날이라 어느 쪽을 봐도 전일 값이므로 문제되지 않는다.
    """
    now = now or datetime.now(KST)
    if now.weekday() >= 5:            # 토·일
        return "UN"
    hm = (now.hour, now.minute)
    if KRX_OPEN <= hm < KRX_CLOSE:
        return "J"
    return "UN"

# 토큰 발급은 1분에 1회 이상 시도하면 차단된다. 최소 간격을 강제한다.
TOKEN_MIN_INTERVAL = 70
_last_token_attempt = 0.0

# 발급은 한 번에 하나만 들어간다. 이 서버는 요청을 동시에 처리하므로
# (ThreadingHTTPServer) 토큰이 없는 상태로 화면을 열면 prices·quotes·
# indices·index-minutes 가 한꺼번에 발급을 시도한다. 자물쇠가 없으면
# 하나만 성공하고 나머지는 위 간격에 걸려 500(서버가 터짐)이 된다.
_token_lock = threading.Lock()

# 시세 캐시: KIS 호출량을 줄이는 핵심 장치.
# 같은 종목을 이 시간 안에 다시 요청하면 KIS 를 부르지 않고 캐시로 답한다.
# 값을 키우면 호출이 줄고, 줄이면 더 자주 갱신된다.
#
# TTL 은 화면 갱신 주기보다 1~5초 짧게 잡는다. 그래야 자기 탭은 늘 새 값을 받고,
# 같은 종목을 거의 동시에 묻는 다른 탭만 캐시가 받아낸다. 창을 여러 개 띄워도
# KIS 호출이 곱해지지 않는다.
#   전에는 TTL 10초 < 갱신 15초라 부르러 올 때마다 이미 만료돼 있어서
#   캐시가 사실상 놀고 있었다 (적중률 18%).
#
# 갈래는 js/components/frame.js 와 짝을 이룬다. FAST_CODES 는 그쪽
# PRIORITY_CODES 와 같아야 한다.
FAST_CODES = {"005930", "000660"}   # 5초마다 갱신 — 삼성전자 · SK하이닉스
PRICE_CACHE_TTL_FAST = 4            # 빠른 갈래 (갱신 5초)
PRICE_CACHE_TTL = 25                # 느린 갈래 · 지수 (갱신 30초)
_price_cache = {}          # code -> (저장시각, 데이터)
_cache_lock = threading.Lock()
_stats = {"kis_calls": 0, "cache_hits": 0}


def _cache_ttl(code):
    """종목이 어느 갈래인지에 따라 캐시 수명을 정한다."""
    return PRICE_CACHE_TTL_FAST if code in FAST_CODES else PRICE_CACHE_TTL


def _cache_get(code):
    with _cache_lock:
        hit = _price_cache.get(code)
        if hit and (time.time() - hit[0]) < _cache_ttl(code):
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
#   BUDGET_RATIO      : 그중 실제로 쓸 비율. 0.5 = 한도의 50%
#
# 2026-09-14 에 0.1(초당 1건) 에서 0.5(초당 5건) 로 올렸다.
# 순위표를 15종목으로 늘리려니 첫 조회에 28.8초가 걸렸다(실측). 한국투자증권
# 제한이 아니라 이 값 때문이었다. 초당 5건이면 같은 조회가 3초 안에 끝난다.
# 기준값 10 도 실제 한도(20)보다 낮게 잡아 둔 것이라, 실제로는 한도의 1/4 이다.
# 배포본(worker/kis-worker.js 의 kisPace)도 200ms = 초당 5건으로 같다.
#
# 이 두 값만 바꾸면 호출량 전체가 조절된다.
KIS_LIMIT_PER_SEC = 10.0
BUDGET_RATIO = 0.5                                  # 한도의 1/2 만 사용
KIS_CALLS_PER_SEC = KIS_LIMIT_PER_SEC * BUDGET_RATIO   # = 초당 1건
KIS_MIN_INTERVAL = 1.0 / KIS_CALLS_PER_SEC             # = 1.0초 간격

# 동시에 진행할 호출 수. 초당 건수와는 별개다 — 간격은 _rate_limit() 이 지키고,
# 이 값은 응답을 기다리는 시간을 몇 개까지 겹칠지를 정한다.
KIS_MAX_PARALLEL = 8

_rate_lock = threading.Lock()
_last_call_at = 0.0
_call_times = []                 # 최근 호출 시각 (사용량 측정용)


def _rate_limit():
    """KIS 호출 사이 간격을 지킨다. 기다리는 동안 남을 막지 않는다.

    전에는 자물쇠를 쥔 채로 기다렸다. 그래서 아래 ThreadPoolExecutor 로 동시에
    부르려 해도 결국 한 줄로 섰고, 허용량의 1/4 도 못 쓰면서 17종목에 10.5초가
    걸렸다 (2026-09-14 실측).

    이제는 자물쇠 안에서 "내 차례 시각" 만 받아 오고, 기다리는 것은 자물쇠를
    놓은 뒤에 한다. 여러 호출이 각자 다른 시각을 배정받아 겹쳐 진행되므로,
    초당 건수는 그대로 지키면서 KIS 응답을 기다리는 시간이 서로 가려진다.
    """
    global _last_call_at
    with _rate_lock:
        now_m = time.monotonic()
        # 내 차례는 '직전 차례 + 간격' 과 '지금' 중 늦은 쪽
        start_at = max(now_m, _last_call_at + KIS_MIN_INTERVAL)
        _last_call_at = start_at
        now = time.time()
        _call_times.append(now)
        # 1시간보다 오래된 기록은 버린다
        cutoff = now - 3600
        while _call_times and _call_times[0] < cutoff:
            _call_times.pop(0)

    wait = start_at - time.monotonic()
    if wait > 0:
        time.sleep(wait)


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
        "priceCacheTtlFast": PRICE_CACHE_TTL_FAST,
        "fastCodes": sorted(FAST_CODES),
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
        raise RuntimeError("secrets.json 형식이 잘못되었습니다: %s" % safe_message(e))

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
    """접근토큰을 얻는다. 캐시가 유효하면 재사용한다.

    캐시를 두 번 본다. 자물쇠 **밖**에서 한 번 — 토큰이 있는 평소에는
    줄을 서지 않아야 느려지지 않는다. 자물쇠 **안**에서 다시 한 번 —
    기다리는 동안 먼저 들어간 쪽이 받아 두었으면 그것을 쓴다.

    2026-09-16 에 자물쇠가 없어 났던 일: 서버를 새로 띄운 직후 첫 화면에서
    요청 넷이 동시에 발급을 시도해 하나만 성공하고 셋이 500(서버가 터짐)이
    되었다. 동시 5건으로 재현했다 — 성공 1 · 실패 4.
    """
    global _last_token_attempt

    cached = _read_token_cache(cfg["mode"])
    if cached:
        return cached

    with _token_lock:
        return _issue_token(cfg)


def _issue_token(cfg):
    """실제 발급. _token_lock 을 쥔 상태에서만 부른다."""
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
        detail = scrub(e.read().decode("utf-8", "replace"))[:300]
        raise RuntimeError("토큰 발급 실패 (HTTP %s): %s" % (e.code, detail))
    except urllib.error.URLError as e:
        raise RuntimeError("토큰 발급 실패 (네트워크): %s" % safe_message(e.reason))

    token = data.get("access_token")
    if not token:
        raise RuntimeError("토큰 발급 응답에 access_token 이 없습니다: %s" % str(data)[:200])

    _write_token_cache(cfg["mode"], token, data.get("expires_in", 86400))
    return token


# ---------------------------------------------------------------- KIS 호출

# ── Debugging(검사) 보드로 넘기기 ─────────────────────────────
#
# 로컬 서버가 다섯인데 상단 메뉴는 포트를 바꾸지 않는다. 그래서 8765
# (holdings 미리보기)에서 Debugging 보드를 열면 화면은 뜨지만 검사 API 가
# 없어 404(그런 주소 없음)가 쏟아졌다 (2026-09-15 재권님 지적).
#
# 「로컬은 8765 하나로 본다」로 정했으므로, /debugging/ 로 오는 것은
# 8093(Debugging 보드 전용)으로 넘긴다. 8093 은 반대로 /holdings/ 를
# 8765 로 넘긴다 — 대칭이다.
DEBUGGING_PORT = 8093
DEBUGGING_BASE = "http://localhost:%d" % DEBUGGING_PORT

# 8093 이 살아 있는지. 매 요청마다 확인하면 느리므로 잠깐 기억해 둔다.
_dbg_alive = {"at": 0.0, "ok": False}
DEBUGGING_PROBE_TTL = 3.0


# 8093 이 꺼져 있을 때 보여줄 안내. 연결 실패 화면 대신 무엇을 켜야 하는지
# 적어 준다. 숫자에는 뜻을 괄호로 붙인다 (CLAUDE.md 「응답 규칙」).
DEBUGGING_OFF_HTML = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>Debugging 보드가 꺼져 있습니다</title>
<style>
  :root { color-scheme: light; }
  body { margin: 0; min-height: 100vh; display: flex; align-items: center;
         justify-content: center; background: #f6f7f9; color: #101013;
         font-family: "Noto Sans KR", -apple-system, sans-serif; }
  .box { background: #fff; border-radius: 16px; padding: 40px 44px;
         max-width: 520px; }
  h1 { font-size: 1.15rem; margin: 0 0 14px; }
  p { font-size: 0.88rem; line-height: 1.65; color: #4e5968; margin: 0 0 10px; }
  code { background: #f2f4f6; border-radius: 6px; padding: 2px 7px;
         font-family: "JetBrains Mono", monospace; font-size: 0.85rem; }
  .why { margin-top: 20px; padding-top: 16px; border-top: 1px solid #f2f4f6;
         font-size: 0.8rem; color: #8b95a1; }
</style></head><body>
<div class="box">
  <h1>Debugging 보드가 꺼져 있습니다</h1>
  <p>이 화면은 <code>8093</code>(Debugging 보드 전용) 서버가 켜져 있어야 보입니다.
     아래 파일을 더블클릭해 주세요.</p>
  <p><code>debugging\debugging.bat</code></p>
  <p>켠 뒤 이 페이지를 새로고침하면 넘어갑니다.</p>
  <div class="why">
    지금 보고 계신 것은 <code>8765</code>(holdings 미리보기)입니다.
    검사 기능은 <code>8093</code>에만 있어서, 여기서 열면
    「지금 검사하기」가 <code>404</code>(그런 주소 없음)로 끝납니다.
    그래서 넘기도록 해 두었습니다.
  </div>
</div></body></html>"""


def debugging_alive():
    """8093 이 떠 있나. 포트만 두드려 본다 (요청은 보내지 않는다).

    꺼져 있는데 넘기면 브라우저가 '연결 실패' 화면을 낸다. 그러느니
    무엇을 켜야 하는지 적어 주는 편이 낫다.
    """
    now = time.time()
    if now - _dbg_alive["at"] < DEBUGGING_PROBE_TTL:
        return _dbg_alive["ok"]
    ok = False
    try:
        with socket.create_connection(("127.0.0.1", DEBUGGING_PORT), timeout=0.25):
            ok = True
    except OSError:
        ok = False
    _dbg_alive.update(at=now, ok=ok)
    return ok


def out_rows(data, key):
    """KIS 응답에서 배열을 꺼낸다.

    `data.get("output") or []` 로 쓰면 output 이 객체로 왔을 때 키를 순회해
    문자열이 나오고, 그 뒤 r.get(...) 에서 터진다. 워커 쪽에서는 같은 자리가
    "object is not iterable" 로 500 이 됐다 (2026-09-15).
    배열이 아니면 빈 배열로 친다. worker/kis-worker.js 의 outRows 와 같다.
    """
    v = (data or {}).get(key)
    return v if isinstance(v, list) else []


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
        detail = scrub(e.read().decode("utf-8", "replace"))[:300]
        # 초당 건수 초과(EGW00201)는 잠깐 쉬었다 한 번만 다시 시도한다.
        if "EGW00201" in detail and _retry > 0:
            time.sleep(1.0)
            return kis_get(cfg, path, params, tr_id, _retry - 1)
        raise RuntimeError("KIS 호출 실패 (HTTP %s): %s" % (e.code, detail))
    except urllib.error.URLError as e:
        raise RuntimeError("KIS 호출 실패 (네트워크): %s" % safe_message(e.reason))

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
            return code, None, safe_message(e)

    # 동시에 몇 개까지 진행할지. 초당 건수는 _rate_limit() 이 따로 지키므로
    # 이 값은 "KIS 응답을 기다리는 시간을 몇 개까지 겹칠 것인가" 를 뜻한다.
    # 2 였을 때는 _rate_limit 이 자물쇠를 쥐고 기다려서 사실상 1 이었다.
    with ThreadPoolExecutor(max_workers=KIS_MAX_PARALLEL) as pool:
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

        # 아래 둘은 이미 이 응답에 들어 있었는데 쓰지 않고 버리던 것이다.
        # 따로 부르지 않아도 되므로 호출이 늘지 않는다 (2026-09-15).

        # 상승·보합·하락 종목 수. 화면 맨 위 장 상태 줄에 쓴다.
        "up": _num(o.get("ascn_issu_cnt"), int),
        "flat": _num(o.get("stnr_issu_cnt"), int),
        "down": _num(o.get("down_issu_cnt"), int),
        "upperLimit": _num(o.get("uplm_issu_cnt"), int),
        "lowerLimit": _num(o.get("lslm_issu_cnt"), int),

        # 연중 최고·최저. 52주가 아니라 '올해 들어' 기준이다(dryy = during year).
        # 화면에도 그렇게 적어야 한다.
        "yearHigh": _num(o.get("dryy_bstp_nmix_hgpr")),
        "yearHighDate": (o.get("dryy_bstp_nmix_hgpr_date") or "").strip() or None,
        "yearLow": _num(o.get("dryy_bstp_nmix_lwpr")),
        "yearLowDate": (o.get("dryy_bstp_nmix_lwpr_date") or "").strip() or None,
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
    rows = out_rows(data, "output2")
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


# 지수 당일 흐름 (5분 간격).
#
#   FID_INPUT_HOUR_1 은 시각이 아니라 **초 단위 간격**이다. 여기서 한참 헤맸다.
#   "150000"(15시) 처럼 시각을 넣으면 날짜별 요약이 돌아오고,
#   "300"(300초=5분)을 넣으면 09:00~15:30 하루치가 99건으로 온다.
#   (2026-09-14 직접 호출해 확인. 공식 문서에는 값이 적혀 있지 않았다)
#
#   한 번에 101건까지 온다. 5분 간격이면 505분이라 정규장(390분)을 다 덮는다.
INDEX_MINUTE_STEP = "300"        # 5분
INDEX_MINUTE_TTL = 30            # 장중에는 계속 바뀌므로 짧게


def fetch_index_minutes(cfg, code):
    """지수 5분봉. **받아둔 것을 DB 에 쌓아 며칠치를 들고 있는다** (2026-09-16 지시).

    KIS 는 한 번에 100건쯤 준다. 그것만 쓰면 하루 조금 넘는 분량이라
    200일선이 안 그려지고, 서버를 껐다 켜면 그만큼으로 되돌아간다.
    받은 것을 버리지 않고 합치면 날이 갈수록 쌓인다. **호출은 안 늘어난다** —
    지금도 부르고 있고, 그 결과를 저장만 하는 것이다.

    종목 5분봉이 쓰는 candles 표를 그대로 쓴다.
    """
    db_init()
    keep = INDEX_KEEP["5m"]
    rows = read_candles(code, "5m", keep)

    mkey = "idx:%s:5m" % code
    stale = (time.time() - float(_meta_get(mkey) or 0)) > INDEX_MINUTE_TTL
    if rows and not stale:
        return rows

    bars = _index_minutes_from_kis(cfg, code)
    if bars:
        save_candles(code, "5m", bars)
        rows = read_candles(code, "5m", keep)
    _meta_set(mkey, time.time())
    return rows


def _index_minutes_from_kis(cfg, code):
    """한 번 받아 온다. 100건쯤 온다."""
    data = kis_get(cfg, "/uapi/domestic-stock/v1/quotations/inquire-time-indexchartprice", {
        "FID_COND_MRKT_DIV_CODE": "U",
        "FID_INPUT_ISCD": code,
        "FID_INPUT_HOUR_1": INDEX_MINUTE_STEP,
        "FID_PW_DATA_INCU_YN": "Y",
        "FID_ETC_CLS_CODE": "0",
    }, "FHKUP03500200")

    bars = []
    for r in out_rows(data, "output2"):
        hhmmss = (r.get("stck_cntg_hour") or "").strip()
        # 888888 · 999999 는 시각이 아니라 요약 표시다. 버린다.
        if not hhmmss.isdigit() or hhmmss in ("888888", "999999"):
            continue
        close = _num(r.get("bstp_nmix_prpr"))
        if close is None:
            continue
        bars.append({
            "ts": (r.get("stck_bsop_date") or "") + hhmmss[:4],
            "open": _num(r.get("bstp_nmix_oprc")),
            "high": _num(r.get("bstp_nmix_hgpr")),
            "low": _num(r.get("bstp_nmix_lwpr")),
            "close": close,
            "volume": 0,           # 지수 분봉에는 거래량이 없다. 표가 요구해서 채운다
        })
    bars.sort(key=lambda b: b["ts"])
    return bars


# ── 해외 지수·환율 ──────────────────────────────────────────────────
# 국내 계약으로도 받아진다. 2026-09-15 에 직접 호출해 확인했다.
# 야후를 붙일 필요가 없다.
# (docs/data-sources.md 가 "국내 계약으로는 못 받는다" 고 적고 있었는데
#  2026-09-17 에 고쳤다. 코드가 문서를 반박한 채로 이틀 있었다)
#
#   시장구분 N = 해외지수 · X = 환율
#
# 다우존스는 코드를 찾지 못했다. DJI · .DJI · DJIA 를 네 가지 시장구분으로
# 시도했지만 모두 0 이 온다 (DOW 는 다우社 주식이라 28원이 나온다).
# WTI·금도 이 API 로는 안 나온다 — 해외선물 쪽을 따로 봐야 한다.
OVERSEAS_DEFS = [
    ("USDKRW", "X", "FX@KRW",  "미국 USD", "원"),
    ("SPX",    "N", "SPX",     "S&P 500",  "pt"),
    ("NASDAQ", "N", "COMP",    "나스닥 종합", "pt"),
    ("VIX",    "N", "VIX",     "VIX",      "pt"),
]
OVERSEAS_TTL = 60          # 해외장은 국내 장중에 거의 멈춰 있다
_ovs_cache = {}


# ── 지수 캔들 ───────────────────────────────────────────────────────
# 첫 화면 큰 차트가 쓴다. 5분봉은 위의 fetch_index_minutes 가 맡고,
# 일·주·월·년봉은 여기서 받는다. 네 기간 모두 시·고·저·종이 온다
# (2026-09-15 확인). 종목 캔들과 같은 모양으로 돌려줘 화면이 같은 코드로 읽는다.
INDEX_PERIODS = {"D": "일", "W": "주", "M": "월", "Y": "년"}


# 봉마다 얼마나 받아 두는가 (2026-09-16 지시).
#
# 200일 이동평균을 그리려면 봉이 200개 넘게 있어야 한다. 그런데 KIS 는
# **한 번에 50개까지만** 준다 — 400일을 달라고 해도 50개다 (실측).
# 그래서 구간을 뒤로 밀어가며 여러 번 받아 채운다.
#
#     일  300개  약 1년 3개월
#     주  260개  약 5년
#     월  250개  약 21년
#     년   40개  1993년부터가 34개뿐이다. **MA200 을 못 그린다** —
#                자료가 없는 것이지 덜 받는 것이 아니다. 화면이 그렇게 적는다
INDEX_KEEP = {"5m": 400, "D": 300, "W": 260, "M": 250, "Y": 40}
#              ↑ 5분봉은 하루 78봉이라 400개면 약 닷새다 (2026-09-16 지시)

# 한 번에 오는 개수 (KIS 제한, 2026-09-16 실측)
INDEX_PAGE = 50

# 나눠 받을 때 최대 몇 번까지. 끝없이 도는 것을 막는다
INDEX_PAGES = 8

# 얼마나 지나면 다시 받나. 과거 봉은 변하지 않으므로 오늘 것만 새로 온다
INDEX_FRESH = {"D": 60, "W": 300, "M": 600, "Y": 3600}

# 한 번 부를 때 훑는 기간. 어차피 50개만 오지만, 좁으면 그보다 적게 온다
INDEX_SPAN = {"D": 400, "W": 1500, "M": 4000, "Y": 12000}


def _index_bars_from_kis(cfg, code, period, date_from, date_to):
    """한 구간을 받아 온다. 최대 INDEX_PAGE 개."""
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice",
        {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": code,
         "FID_INPUT_DATE_1": date_from.strftime("%Y%m%d"),
         "FID_INPUT_DATE_2": date_to.strftime("%Y%m%d"),
         "FID_PERIOD_DIV_CODE": period},
        "FHKUP03500100",
    )
    out = []
    for r in out_rows(data, "output2"):
        day = (r.get("stck_bsop_date") or "").strip()
        close = _num(r.get("bstp_nmix_prpr"))
        if not day or close is None:
            continue
        out.append({
            "ts": day,
            "open": _num(r.get("bstp_nmix_oprc")),
            "high": _num(r.get("bstp_nmix_hgpr")),
            "low": _num(r.get("bstp_nmix_lwpr")),
            "close": close,
            "volume": _num(r.get("acml_vol"), int) or 0,
        })
    out.sort(key=lambda b: b["ts"])
    return out


def _index_backfill(cfg, code, period, want):
    """구간을 뒤로 밀어가며 want 개가 모일 때까지 받는다."""
    span = timedelta(days=INDEX_SPAN[period])
    got = {}
    to = datetime.now(KST)
    for _ in range(INDEX_PAGES):
        bars = _index_bars_from_kis(cfg, code, period, to - span, to)
        if not bars:
            break                       # 더 옛날 자료가 없다
        for b in bars:
            got[b["ts"]] = b
        if len(got) >= want:
            break
        oldest = min(b["ts"] for b in bars)
        to = datetime.strptime(oldest, "%Y%m%d").replace(tzinfo=KST) - timedelta(days=1)
    return sorted(got.values(), key=lambda b: b["ts"])


def fetch_index_candles(cfg, code, period):
    """지수 봉. **받아둔 것을 DB 에서 읽고, 모자라거나 묵었을 때만 부른다.**

    전에는 메모리 캐시 5분짜리만 있어서 서버를 껐다 켜면 사라졌고, 매번
    새로 받은 50개로 그렸다. 그래서 MA60 부터 조용히 빠졌다 (2026-09-16).

    종목 봉이 쓰는 candles 표를 그대로 쓴다. 지수 코드(0001)는 네 자리라
    종목코드 여섯 자리와 겹치지 않는다.
    """
    db_init()
    want = INDEX_KEEP[period]
    rows = read_candles(code, period, want)

    mkey = "idx:%s:%s" % (code, period)
    stale = (time.time() - float(_meta_get(mkey) or 0)) > INDEX_FRESH[period]
    if len(rows) >= want and not stale:
        return rows

    if len(rows) < want:
        bars = _index_backfill(cfg, code, period, want)      # 처음이거나 모자라다
    else:
        span = timedelta(days=INDEX_SPAN[period])
        now = datetime.now(KST)
        bars = _index_bars_from_kis(cfg, code, period, now - span, now)   # 새 봉만

    if bars:
        save_candles(code, period, bars)
        rows = read_candles(code, period, want)
    _meta_set(mkey, time.time())
    return rows


# ── 코스피200 선물 ──────────────────────────────────────────────────
# 종목코드 "10100000" 이 최근월물을 가리킨다. 응답의 hts_kor_isnm 에
# "F 202612" 처럼 어느 월물인지 적혀 온다.
#
# 코드를 찾는 데 한참 걸렸다. 101W09 · 101U6000 같은 월물 표기를 여러 개
# 넣어 봤지만 전부 output1(선물 자리)이 비어 오고 output2(기초자산 = 코스피
# 지수)만 돌아왔다. 8자리 "10100000" 이 맞다 (2026-09-15 확인).
FUTURES_CODE = "10100000"
# 화면이 1초마다 물어보므로 그보다 짧게 잡는다. 그래야 자기 탭은 늘 새 값을 받고,
# 같은 것을 거의 동시에 묻는 다른 탭만 캐시가 받아낸다.
FUTURES_TTL = 0.7
_fut_cache = {}


def fetch_futures(cfg):
    """코스피200 선물 최근월물. 못 받으면 None — 화면은 그 칸만 비운다."""
    hit = _fut_cache.get("k200")
    if hit and (time.time() - hit[0]) < FUTURES_TTL:
        return hit[1]
    try:
        _stats["kis_calls"] += 1
        data = kis_get(
            cfg,
            "/uapi/domestic-futureoption/v1/quotations/inquire-price",
            {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": FUTURES_CODE},
            "FHMIF10000000",
        )
    except RuntimeError:
        return None

    o = data.get("output1") or {}
    price = _num(o.get("futs_prpr"))
    if price is None:
        return None
    row = {
        "name": (o.get("hts_kor_isnm") or "").strip(),   # 예: "F 202612"
        "price": price,
        "change": _num(o.get("futs_prdy_vrss")),
        "changePct": _num(o.get("futs_prdy_ctrt")),
        "volume": _num(o.get("acml_vol"), int),
        "source": "KIS",
    }
    _fut_cache["k200"] = (time.time(), row)
    return row


def fetch_overseas(cfg):
    """해외 지수와 환율. 하나가 실패해도 나머지는 돌려준다."""
    out, errors = [], {}
    for key, div, code, name, unit in OVERSEAS_DEFS:
        hit = _ovs_cache.get(key)
        if hit and (time.time() - hit[0]) < OVERSEAS_TTL:
            out.append(hit[1])
            continue
        try:
            _stats["kis_calls"] += 1
            # 기간을 넓게 잡아 현재값과 추이를 한 번에 받는다.
            # output1 에 현재값, output2 에 일봉이 함께 온다 — 두 번 부를 필요가 없다.
            now = datetime.now(KST)
            data = kis_get(
                cfg,
                "/uapi/overseas-price/v1/quotations/inquire-daily-chartprice",
                {"FID_COND_MRKT_DIV_CODE": div, "FID_INPUT_ISCD": code,
                 "FID_INPUT_DATE_1": (now - timedelta(days=100)).strftime("%Y%m%d"),
                 "FID_INPUT_DATE_2": now.strftime("%Y%m%d"),
                 "FID_PERIOD_DIV_CODE": "D"},
                "FHKST03030100",
            )
            o = data.get("output1") or {}
            value = _num(o.get("ovrs_nmix_prpr"))
            if value in (None, 0):
                errors[key] = "값이 오지 않았습니다"
                continue
            # 언제 기준 값인지. 해외장은 국내 낮 시간에 닫혀 있어서, 이것을 안 적으면
            # 어제 종가를 실시간인 줄 알게 된다 (2026-09-15 지적).
            rows_sorted = sorted(out_rows(data, "output2"),
                                 key=lambda r: r.get("stck_bsop_date") or "")
            as_of = (rows_sorted[-1].get("stck_bsop_date") if rows_sorted else None)

            row = {
                "code": key, "name": name, "unit": unit,
                "value": value, "asOf": as_of, "market": "overseas",
                "change": _num(o.get("ovrs_nmix_prdy_vrss")),
                "changePct": _num(o.get("prdy_ctrt")),
                # 카드의 작은 그래프가 쓴다. 옛것부터 차례로 담는다.
                "series": [
                    v for v in (
                        _num(r.get("ovrs_nmix_prpr"))
                        for r in sorted(out_rows(data, "output2"),
                                        key=lambda r: r.get("stck_bsop_date") or "")
                    ) if v
                ][-60:],
                "source": "KIS",
            }
            out.append(row)
            _ovs_cache[key] = (time.time(), row)
        except RuntimeError as e:
            errors[key] = safe_message(e)
    return out, errors


# 지수 캐시. 종목 시세 캐시(25초)를 함께 쓰고 있었는데, 그건 화면이 30초마다
# 물어보던 시절 값이다. 지수·선물은 1초마다 받으므로 그보다 짧아야 한다.
INDEX_TTL = 0.7
_index_cache = {}


def _index_cache_get(key):
    hit = _index_cache.get(key)
    if hit and (time.time() - hit[0]) < INDEX_TTL:
        _stats["cache_hits"] += 1
        return hit[1]
    return None


def fetch_indices(cfg, with_chart=True):
    out, errors = [], {}
    for code, name in INDEX_DEFS:
        cache_key = "IDX:" + code
        cached = _index_cache_get(cache_key)
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
            # fetch_index 가 준 것을 그대로 싣는다. 전에는 값·등락만 골라 담고
            # 나머지를 버려서, 시장현황·연중최고저를 추가해도 화면까지 오지 않았다.
            row = {
                **info,
                "code": name, "name": name, "unit": "pt",
                "series": series, "source": "KIS",
            }
            out.append(row)
            _index_cache[cache_key] = (time.time(), row)
        except RuntimeError as e:
            errors[name] = safe_message(e)
    return out, errors


def _num(v, cast=float):
    try:
        return cast(str(v).strip())
    except (TypeError, ValueError):
        return None


def fetch_price(cfg, code):
    """국내 주식 현재가 조회. 시장 기준은 지금 시각에 따라 정해진다."""
    div = quote_market_div()
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-price",
        {"FID_COND_MRKT_DIV_CODE": div, "FID_INPUT_ISCD": code},
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


# ── 여러 종목을 한 번에 ────────────────────────────────────────────────
# 현재가 API(inquire-price)는 한 번에 한 종목만 준다. 순위표처럼 수십 종목을
# 보여주는 화면에서는 그만큼 호출이 곱해져 한참 걸린다.
#
#   30종목을 받을 때   단건 조회 30번  vs  멀티 조회 1번
#
# 관심종목(멀티종목) 시세조회는 **한 번에 30종목까지** 준다.
# 2026-09-14 에 직접 호출해 확인했다 (40개를 보내면 앞 30개만 돌아온다).
#
# 다만 단건 조회보다 주는 항목이 적다. 시가총액·PER·PBR·52주 최고저가 없다.
# 그래서 종목 화면(stock.html)은 여전히 단건 조회를 쓰고, 이것은 목록용이다.
MULTI_MAX = 30

# 목록 시세를 몇 초 동안 들고 있을 것인가.
#
# 순위표가 0.2초마다 다섯 묶음 중 하나씩 도므로 같은 묶음은 1초마다 다시
# 온다. 캐시를 1초로 두면 매번 아슬아슬하게 만료되어 효과가 없다. 2초면
# 한 번 걸러 내보내므로 KIS 호출이 절반이 된다 (2026-09-16 지시).
#
# 값이 최대 2초 묵는다. 그 대신 초당 호출이 여유를 갖는다 — 배포본에서
# 요청이 겹쳐 워커가 1101(예외로 죽음)로 떨어지는 일을 막는다.
#
# 이 상수는 여태 선언만 되고 쓰이지 않았다. 로컬은 요청이 적어 드러나지
# 않았을 뿐, 배포본과 같은 구멍이었다.
MULTI_CACHE_TTL = 2

_multi_cache = {}
_multi_lock = threading.Lock()


def _multi_key(codes, div):
    """묶음이 같으면 같은 키. 순서가 달라도 같은 것으로 본다."""
    return div + ":" + ",".join(sorted(codes))


def fetch_quotes_multi(cfg, codes):
    """목록용 시세. 30종목씩 묶어 부른다. {code: {...}} 로 돌려준다.

    같은 묶음을 MULTI_CACHE_TTL 초 안에 다시 물으면 받아둔 값을 준다.
    화면이 부르는 횟수는 그대로이고 KIS 호출만 줄어든다.
    """
    div = quote_market_div()
    key = _multi_key(codes, div)
    now = time.time()
    with _multi_lock:
        hit = _multi_cache.get(key)
        if hit and (now - hit[0]) < MULTI_CACHE_TTL:
            _stats["cache_hits"] += 1
            return hit[1]

    out, errors = {}, {}

    for i in range(0, len(codes), MULTI_MAX):
        chunk = codes[i:i + MULTI_MAX]
        params = {}
        for n, code in enumerate(chunk, start=1):
            params["FID_COND_MRKT_DIV_CODE_%d" % n] = div
            params["FID_INPUT_ISCD_%d" % n] = code
        try:
            _stats["kis_calls"] += 1
            data = kis_get(
                cfg,
                "/uapi/domestic-stock/v1/quotations/intstock-multprice",
                params, "FHKST11300006",
            )
        except RuntimeError as e:
            for code in chunk:
                errors[code] = safe_message(e)
            continue

        for r in out_rows(data, "output"):
            code = (r.get("inter_shrn_iscd") or "").strip()
            if not code:
                continue
            price = _num(r.get("inter2_prpr"), int)
            amt = _num(r.get("inter2_prdy_vrss"), int)
            prev = _num(r.get("inter2_prdy_clpr"), int)
            out[code] = {
                "price": price,
                "prev": prev,
                "amt": amt,
                "pct": _num(r.get("prdy_ctrt")),
                "name": (r.get("inter_kor_isnm") or "").strip(),
                "open": _num(r.get("inter2_oprc"), int),
                "high": _num(r.get("inter2_hgpr"), int),
                "low": _num(r.get("inter2_lwpr"), int),
                "volume": _num(r.get("acml_vol"), int),
                # 거래대금은 실제 값이 온다. 현재가×거래량으로 어림하지 않아도 된다.
                "value": _num(r.get("acml_tr_pbmn"), int),
                "source": "KIS",
            }

    # 받아둔다. 오류만 있고 값이 하나도 없으면 담지 않는다 — 다음 요청이
    # 다시 시도해야 한다.
    if out:
        with _multi_lock:
            _multi_cache[key] = (time.time(), (out, errors))
            # 순위표를 오르내리면 묶음이 계속 바뀐다. 위쪽을 막아 둔다.
            if len(_multi_cache) > 200:
                for k in list(_multi_cache)[:50]:
                    _multi_cache.pop(k, None)
    return out, errors


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
            "FID_COND_MRKT_DIV_CODE": MARKET_DIV_CHART, "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": date_from, "FID_INPUT_DATE_2": date_to,
            "FID_PERIOD_DIV_CODE": PERIODS[period]["kis"], "FID_ORG_ADJ_PRC": "0",
        },
        "FHKST03010100",
    )
    out = []
    for r in out_rows(data, "output2"):
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


def fetch_minutes_from_kis(cfg, code, hour=None):
    """1분봉. 별도 API 이며 기준 시각부터 과거 30개만 돌려준다.

    hour 를 주지 않으면 '지금까지' 를 기준으로 삼는다. 예전에는 기본값이
    "153000" 이어서, 장중에 최근 구간을 갱신할 때마다 15:00~15:30 자리에
    현재가로 채워진 가짜 봉이 생겼다 (2026-09-14 확인).
    """
    if hour is None:
        m = minute_scan_start()
        hour = "%02d%02d00" % (m // 60, m % 60)
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
        {
            "FID_ETC_CLS_CODE": "", "FID_COND_MRKT_DIV_CODE": MARKET_DIV_CHART,
            "FID_INPUT_ISCD": code, "FID_INPUT_HOUR_1": hour,
            "FID_PW_DATA_INCU_YN": "Y",
        },
        "FHKST03010200",
    )
    out = []
    for r in out_rows(data, "output2"):
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


def minute_scan_start(now=None):
    """분봉을 어느 시각부터 거슬러 내려갈지 정한다.

    **아직 오지 않은 시각은 묻지 않는다.** 장중에 20:00 같은 미래 시각을
    요청하면 KIS 가 마지막 체결값을 그 시각의 봉인 것처럼 돌려준다.
    그대로 저장하면 아직 체결되지도 않은 시간대에 가짜 봉이 생긴다.

    2026-09-14 11:52 에 실제로 그랬다. 11:55~20:00 구간에 현재가로 채워진
    봉이 종목당 98개씩(합계 693개) 들어가 있었고, 종목을 열 때마다 늘어났다.

    장이 다 끝난 뒤나 주말에는 하루치를 통째로 받아도 된다. 그때는 20:00 이
    이미 지난 시각이라 미래가 아니다.
    """
    now = now or datetime.now(KST)
    if now.weekday() >= 5:
        return MINUTE_DAY_END                 # 주말 — 지난 거래일 하루치
    cur = now.hour * 60 + now.minute
    if cur >= MINUTE_DAY_END:
        return MINUTE_DAY_END                 # 20:00 이후 — 하루치
    return cur                                # 그 밖에는 지금 시각까지만


def fetch_minutes_day(cfg, code):
    """하루치 1분봉을 모은다.

    KIS 분봉 API 는 기준 시각부터 과거 30개만 돌려주므로, 시각을 30분씩
    거슬러 내려가며 여러 번 부른다. 통합 시장이라 넥스트레이드 시간대
    (~20:00)까지 포함한다. 한 번 받아 저장하면 이후에는 최근 구간만 갱신한다.

    시작 시각은 minute_scan_start() 가 정한다. 미래를 묻지 않기 위해서다.
    """
    bars = {}
    t = minute_scan_start()
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
            # 처음이면 하루치를 모으고(호출 여러 번), 이후에는 최근 구간만 갱신한다.
            # 기준 시각을 넘기지 않으면 '지금까지' 로 잡힌다 (미래 봉 방지)
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
        super().__init__(*args, directory=SITE_ROOT, **kwargs)

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

    def end_headers(self):
        """화면 파일은 받아두되 쓰기 전에 매번 물어보게 한다.

        Cache-Control 을 아예 안 붙이던 때가 있었다. 브라우저가 Last-Modified
        만 보고 옛 JS·CSS 를 계속 써서, 고친 것이 화면에 안 나타났다
        (2026-09-14). 그래서 no-store 를 붙였다.

        그런데 no-store 는 **받아둔 것을 버리라**는 뜻이라 매번 전부 다시
        내려받는다. 다른 화면에 갔다 오면 처음부터 다시 불러오게 된다
        (2026-09-15 지적).

        no-cache 는 다르다. 받아두되 쓰기 전에 서버에 묻는다. 안 바뀌었으면
        304 로 끝나고 본문은 다시 안 내려온다. 고친 것은 그대로 반영되고,
        안 고친 것은 다시 받지 않는다. 둘 다 얻는다.

        API 응답에는 _send_json 이 이미 붙이고 있다. 여기는 정적 파일 몫이다.
        worker/kis-worker.js 도 같은 값이어야 한다.
        """
        if not (self.path or "").startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        if (self.path or "").startswith("/api/kis/"):
            self._handle_kis()
            return
        if (self.path or "").startswith("/api/dart/"):
            self._handle_dart()
            return
        if (self.path or "").startswith("/api/news/"):
            self._handle_news()
            return
        if (self.path or "").startswith("/debugging/"):
            self._handle_debugging()
            return
        super().do_GET()

    # ── Debugging(검사) 보드 ──
    # 8093 으로 넘긴다. 꺼져 있으면 무엇을 켜야 하는지 적어 준다.
    def _handle_debugging(self):
        if debugging_alive():
            self.send_response(302)
            self.send_header("Location", DEBUGGING_BASE + self.path)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return

        body = DEBUGGING_OFF_HTML.encode("utf-8")
        self.send_response(503)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ── 뉴스 ──
    # 두 갈래를 따로 받는다. 자세한 이유는 server/news.py 머리말에 있다.
    #   issues  구글 뉴스 RSS · 주제어별 · 원문 링크 있음
    #   moves   KIS news-title · 종목코드 붙음 · 링크 없음
    def _handle_news(self):
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path[len("/api/news/"):].strip("/")

        try:
            if route == "topics":
                self._send_json({"ok": True, "data": news.load_topics()["topics"]})
                return

            if route == "issues":
                r = news.fetch_issues()
                self._send_json({"ok": True, "data": r["rows"],
                                 "meta": {"topics": r["topics"], "errors": r["errors"]}})
                return

            if route == "moves":
                cfg = load_secrets()
                r = news.fetch_moves(kis_get, cfg)
                self._send_json({"ok": True, "data": r["rows"],
                                 "meta": {"errors": r["errors"]}})
                return

            if route == "feed":          # 화면이 한 번에 받아가는 자리
                cfg = load_secrets()
                iss = news.fetch_issues()
                mov = news.fetch_moves(kis_get, cfg)
                self._send_json({"ok": True, "data": {
                    "issues": iss["rows"], "moves": mov["rows"],
                    "topics": iss["topics"],
                }, "meta": {"errors": {"issues": iss["errors"], "moves": mov["errors"]}}})
                return

            self._send_json({"ok": False, "error": "알 수 없는 경로입니다: " + route}, 404)
        except Exception as e:
            self._send_json({"ok": False, "error": safe_message(e)}, 500)

    # ── 공시 (OpenDART) ──
    # KIS 와 키도 한도도 다르므로 경로를 나눠 둔다. 키가 없으면 503 으로 답하고,
    # 화면은 "연결 예정" 을 그대로 보여준다.
    def _handle_dart(self):
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path[len("/api/dart/"):].strip("/")
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            if route == "status":
                self._send_json({"ok": True, "data": dart.status()})
                return

            key = dart.get_key()
            if not key:
                self._send_json({
                    "ok": False,
                    "error": "OpenDART 인증키가 없습니다. setup-dart.bat 을 실행해 주세요.",
                }, 503)
                return

            if route == "disclosures":
                code = (qs.get("code") or [""])[0].strip()
                if code and (not code.isdigit() or len(code) != 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                try:
                    limit = int((qs.get("limit") or ["30"])[0])
                except ValueError:
                    limit = 30
                rows = dart.read_disclosures(code or None, limit)
                self._send_json({
                    "ok": True,
                    "data": rows,
                    "meta": {"count": len(rows), "code": code or None,
                             "lastPollAt": dart._meta_get("dart_last_poll")},
                })
                return

            if route == "poll":          # 5분을 기다리지 않고 지금 한 번 받아온다
                self._send_json({"ok": True, "data": dart.poll_once(key)})
                return

            if route == "members":
                # 지수 구성종목. 화면이 IR 을 걸러낼 때 쓴다 (2026-09-15).
                self._send_json({
                    "ok": True,
                    "data": dart.index_members_map(),
                    "meta": {"counts": dart.index_members_count(),
                             "updatedAt": dart._meta_get("dart_members_date")},
                })
                return

            if route == "universe":
                with dart._db_lock, dart.db_conn() as conn:
                    rows = conn.execute(
                        """SELECT rank, stock_code, name, market_cap
                             FROM dart_universe ORDER BY rank"""
                    ).fetchall()
                self._send_json({"ok": True, "data": [
                    {"rank": r["rank"], "code": r["stock_code"],
                     "name": r["name"], "cap": r["market_cap"]} for r in rows
                ]})
                return

            self._send_json({"ok": False, "error": "알 수 없는 경로입니다: %s" % route}, 404)
        except Exception as e:
            self._send_json({"ok": False, "error": "서버 오류: %s" % type(e).__name__}, 500)

    def _handle_kis(self):
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path[len("/api/kis/"):].strip("/")
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            cfg = load_secrets()
        except RuntimeError as e:
            self._send_json({"ok": False, "error": safe_message(e)}, 500)
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
                token_ok, token_err = False, safe_message(e)
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

            if route == "index-candles":
                name = (qs.get("code") or ["KOSPI"])[0].strip().upper()
                found = next((c for c, n in INDEX_DEFS if n == name), None)
                if not found:
                    self._send_json({"ok": False, "error": "code 가 올바르지 않습니다."}, 400)
                    return
                period = (qs.get("period") or ["D"])[0].strip().upper()
                if period not in INDEX_PERIODS:
                    self._send_json({
                        "ok": False,
                        "error": "period 는 %s 중 하나여야 합니다." % ", ".join(INDEX_PERIODS),
                    }, 400)
                    return
                bars = fetch_index_candles(cfg, found, period)
                self._send_json({
                    "ok": True,
                    "data": {"code": name, "period": period, "bars": bars},
                    "meta": {"count": len(bars), "label": INDEX_PERIODS[period]},
                })
                return

            if route == "index-minutes":
                name = (qs.get("code") or ["KOSPI"])[0].strip().upper()
                found = next((c for c, n in INDEX_DEFS if n == name), None)
                if not found:
                    self._send_json({
                        "ok": False,
                        "error": "code 는 %s 중 하나여야 합니다." % ", ".join(n for _, n in INDEX_DEFS),
                    }, 400)
                    return
                bars = fetch_index_minutes(cfg, found)
                self._send_json({
                    "ok": True,
                    "data": {"code": name, "bars": bars},
                    "meta": {"count": len(bars), "stepSec": int(INDEX_MINUTE_STEP)},
                })
                return

            if route == "indices":
                with_chart = (qs.get("chart") or ["1"])[0] != "0"
                data, errors = fetch_indices(cfg, with_chart)
                # 해외 지수·환율도 같은 응답에 실어 보낸다. 화면이 한 번만 부르면 된다.
                if (qs.get("overseas") or ["1"])[0] != "0":
                    ovs, ovs_err = fetch_overseas(cfg)
                    data = data + ovs
                    errors.update(ovs_err)
                futures = fetch_futures(cfg)
                self._send_json({"ok": bool(data), "data": data,
                                 "futures": futures, "errors": errors or None})
                return

            if route == "quotes":
                raw = (qs.get("codes") or [""])[0]
                codes = [c.strip() for c in raw.split(",") if c.strip()]
                codes = [c for c in codes if c.isdigit() and len(c) == 6]
                codes = list(dict.fromkeys(codes))[:120]   # 멀티 4묶음까지
                if not codes:
                    self._send_json({"ok": False, "error": "codes 에 6자리 종목코드가 없습니다."}, 400)
                    return
                before = _stats["kis_calls"]
                data, errors = fetch_quotes_multi(cfg, codes)
                self._send_json({
                    "ok": True,
                    "data": data,
                    "errors": errors or None,
                    "meta": {
                        "requested": len(codes),
                        "kisCalls": _stats["kis_calls"] - before,
                        "perCall": MULTI_MAX,
                    },
                })
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
                        "cacheTtlFast": PRICE_CACHE_TTL_FAST,
                        "totalKisCalls": _stats["kis_calls"],
                    },
                })
                return
            self._send_json({"ok": False, "error": "알 수 없는 경로입니다: %s" % route}, 404)
        except RuntimeError as e:
            self._send_json({"ok": False, "error": safe_message(e)}, 502)
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
        print("  [경고] %s" % safe_message(e))

    print("-" * 52)
    print("  KJC Holdings - 로컬 서버")
    print("-" * 52)
    print("  대시보드  : http://localhost:%d/holdings/" % args.port)
    print("  주식 분석 : http://localhost:%d/holdings/analysis/" % args.port)
    print("  메인 사이트: http://localhost:%d/" % args.port)
    if cfg:
        print("  KIS 연동  : 사용 (%s)" % MODE_LABEL[cfg["mode"]])
        print("  상태 확인 : http://localhost:%d/api/kis/health" % args.port)
    else:
        print("  KIS 연동  : 꺼짐 (secrets.json 없음, 정적 서버로만 동작)")

    if dart.start_poller():
        print("  공시 수집 : 사용 (코스피 상위 %d종목 · %d분마다)"
              % (dart.UNIVERSE_SIZE, dart.POLL_INTERVAL // 60))
        print("  알림      : %s"
              % ("텔레그램 켜짐 (관심종목 %d개)" % len(dart.WATCH_CODES)
                 if dart.telegram_config() else "꺼짐 (secrets.json 의 telegram 없음)"))
    else:
        print("  공시 수집 : 꺼짐 (setup-dart.bat 으로 인증키를 넣어주세요)")
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
