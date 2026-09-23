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

# 파일을 안전하게 쓴다 — 쓰다 죽어도 옛 내용이 남는다 (2026-09-22)
from docstore import write_json_atomic
import docstore
import re
import signal_watch
import daily
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# 같은 폴더(server/)의 모듈들. 스크립트로 실행하므로 바로 잡힌다.
import dart
import naver
import news
import news_store
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
# ── 모든 종목이 같은 수명을 쓴다 (2026-09-18 지시) ──
#
# 재권님 말씀 — "삼성전자 하이닉스도 같은값이여야 할거같은데
# **모든값은 통일해야해**".
#
# 전에는 삼성전자·SK하이닉스만 4초, 나머지는 25초였다. 그러면 **같은 화면에서
# 종목마다 기준 시각이 다르다** — 순위표처럼 등락률을 나란히 놓고 보는 자리에서
# 그 둘만 먼저 움직인 것처럼 보인다.
#
# 「시세 표기 규칙」이 정규장 중 KRX · 마감 후 넥스트레이드로 기준을 통일해 둔
# 것과 같은 이야기다 — **기준이 섞이면 무엇을 보고 있는지 알 수 없다.**
#
# 그래서 `FAST_CODES` 와 `PRICE_CACHE_TTL_FAST` 를 없앴다. 복제가 세 곳
# (여기 · kis-worker.js · frame.js 의 PRIORITY_CODES)이었는데 한꺼번에 사라졌다.
PRICE_CACHE_TTL = 25                # 모든 종목 · 지수 (화면 갱신 30초)

# ── 확인용 서버는 느리게 돈다 — `--slow` (2026-09-21 지시) ────────────
#
# 동시 작업을 하면 **세션마다 서버를 띄운다.** 서버가 셋이면 KIS 를 부르는
# 횟수도 세 배가 되어 한도를 넘긴다. 재권님 승인 그대로다 —
# **확인용은 시세 5분 · 미리받기 끔**, 재권님이 쓰시는 8765 는 그대로.
#
# 확인용 서버는 배치·색을 보는 자리라 값이 묵어도 지장이 없다. 차트를
# 제대로 봐야 할 때는 8765 에서 본다.
#
# **화면 코드는 하나도 안 고친다.** 서버가 「아까 그 값」을 돌려주면
# 화면이 아무리 자주 물어도 KIS 로는 안 나간다.
SLOW = False
SLOW_TTL = 300              # 시세 · 지수 · 업종 … 전부 5분
SLOW_SHORT_TTL = 60         # 호가처럼 원래 아주 짧던 것도 이만큼은 둔다
_price_cache = {}          # code -> (저장시각, 데이터)
_cache_lock = threading.Lock()
_stats = {"kis_calls": 0, "cache_hits": 0}


def _cache_ttl(code):
    """캐시 수명. **모든 종목이 같다** (2026-09-18 지시). 위 주석 참고."""
    return PRICE_CACHE_TTL


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
    # 미리받기는 화면에 자리를 내준다. 급하지 않은 일이라 늦어져도 잃는 것이
    # 없고, 화면은 기다리면 재권님이 보신다 (2026-09-18).
    if threading.current_thread().name == PREFILL_THREAD_NAME:
        time.sleep(PREFILL_BUSY_CALL_GAP if _ui_busy() else PREFILL_IDLE_CALL_GAP)

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
    """토큰 캐시를 **안전하게** 쓴다 (2026-09-22).

    전에는 `open(PATH, "w")` 로 바로 덮어썼다. 거기서 죽으면 **깨진
    캐시가 남는다.** 키 파일만큼 위험하진 않지만(다시 받으면 된다)
    같은 함수를 쓰면 한 곳만 고치면 된다.

    `tmp` 라는 이름이 붙어 있어 임시 파일을 쓰는 것처럼 보였는데
    **그냥 dict 이름**이었다 — 이름이 설명 노릇을 하던 자리다.
    """
    try:
        write_json_atomic(TOKEN_CACHE_PATH, {
            "mode": mode,
            "access_token": token,
            "expires_at": time.time() + float(expires_in),
        }, indent=None)
    except (OSError, IOError):
        pass


def _drop_token_cache(mode):
    """KIS 가 거부한 토큰을 버린다 (2026-09-22 지시 — 「응 해줘」).

    **캐시가 「아직 안 만료」 라고 믿는데 KIS 는 거부하는 구간이 있다.**
    그 상태에서는 `_read_token_cache` 가 거부당한 토큰을 계속 돌려주어
    **캐시가 스스로 만료될 때까지 몇십 분이고 계속 실패한다.**

    2026-09-22 실측 — 여섯 폴더의 토큰 발급 시각과 화면을 함께 재니,
    **가장 오래된 토큰을 든 폴더 하나만** 해외 지수 여덟이 전부
    `EGW00123` 로 거부됐다. 같은 토큰으로 국내는 통했다.

        KJCStudio  09-22 12:40 발급  12개 정상
        kjc-stock  09-21 13:12 발급  **4개 · 해외 8건 EGW00123**

    파일을 지우는 대신 **만료로 표시해 덮어쓴다.** 지우면 다른 프로세스가
    「없음」 과 「거부됨」 을 구분하지 못한다.
    """
    try:
        write_json_atomic(TOKEN_CACHE_PATH,
                          {"mode": mode, "access_token": "", "expires_at": 0},
                          indent=None)
    except (OSError, IOError):
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

# 재권님이 최종 확인하시는 서버. **텔레그램은 여기서만 보낸다** (2026-09-22).
#
# `frame.js` 의 `MAIN_PORT` 와 **같은 값**이다 — 화면은 이 포트가 아니면
# 「정식 아님」 띠를 붙인다. 언어가 달라 한 곳으로 못 합치므로, **한쪽을
# 고치면 다른 쪽도 본다.**
MAIN_PORT = 8765
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
        # **거부당한 토큰(EGW00123)은 버리고 한 번만 다시 받는다** (2026-09-22 지시).
        # 이것이 없으면 캐시가 스스로 만료될 때까지 몇십 분이고 계속 실패한다.
        if "EGW00123" in detail and _retry > 0:
            _drop_token_cache(cfg["mode"])
            return kis_get(cfg, path, params, tr_id, _retry - 1)
        raise RuntimeError("KIS 호출 실패 (HTTP %s): %s" % (e.code, detail))
    except urllib.error.URLError as e:
        raise RuntimeError("KIS 호출 실패 (네트워크): %s" % safe_message(e.reason))

    if str(data.get("rt_cd", "0")) != "0":
        if data.get("msg_cd") == "EGW00201" and _retry > 0:
            time.sleep(1.0)
            return kis_get(cfg, path, params, tr_id, _retry - 1)
        if data.get("msg_cd") == "EGW00123" and _retry > 0:
            _drop_token_cache(cfg["mode"])
            return kis_get(cfg, path, params, tr_id, _retry - 1)
        raise RuntimeError("KIS 오류: %s (%s)" % (data.get("msg1", "알 수 없음"), data.get("msg_cd", "")))
    return data


def fetch_prices(cfg, codes):
    """여러 종목을 한 번에 조회한다.

    KIS 현재가 API 는 한 번에 한 종목만 받으므로 서버가 나눠 호출한다.
    호출 제한(실전 20건/초)에 걸리지 않도록 동시 실행 수를 제한한다.
    """

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
                    "volume": info.get("volume"), "value": info.get("value"),
                    "marketCap": info.get("marketCap"),
                    "open": info.get("open"), "high": info.get("high"),
                    "low": info.get("low"),
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
    ("4001", "KRX100"),      # 2026-09-17 에 코드를 찾았다. 01xx 대역이 아니라 4xxx 다
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
# 2026-09-17 에 약 70개 심볼을 네 시장구분으로 훑어 받아지는 것만 남겼다.
# **KIS 해외지수 목록에 몇 개만 들어 있다** — 다우 · 닛케이 · 상해 · FTSE ·
# DAX · 항셍 · 대만 · 인도는 전부 0 이다. 아시아라서가 아니다(홍콩H·유로는 된다).
# 왜 그런지는 확인하지 못했다. 지수 목록을 주는 API 를 못 찾았다.
OVERSEAS_DEFS = [
    ("USDKRW", "X", "FX@KRW",  "미국 USD",   "원"),
    ("SPX",    "N", "SPX",     "S&P 500",    "pt"),
    ("NASDAQ", "N", "COMP",    "나스닥 종합",  "pt"),
    ("NDX",    "N", "NDX",     "나스닥100",   "pt"),
    ("SOX",    "N", "SOX",     "필라델피아 반도체", "pt"),
    ("SX5E",   "N", "SX5E",    "유로STOXX50", "pt"),
    ("HSCE",   "N", "HSCE",    "홍콩H",       "pt"),
    ("VIX",    "N", "VIX",     "VIX",        "pt"),
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
    """해외 지수와 환율. 하나가 실패해도 나머지는 돌려준다.

    **넷을 겹쳐 부른다** (2026-09-18). 위 fetch_indices 와 같은 이유다 —
    초당 건수는 _rate_limit() 이 지키고, 겹치는 것은 기다리는 시간뿐이다.
    자리를 미리 잡아 두는 것도 같다. OVERSEAS_DEFS 순서가 화면 순서다.
    """
    errors = {}
    slots = [None] * len(OVERSEAS_DEFS)
    todo = []
    for i, defn in enumerate(OVERSEAS_DEFS):
        hit = _ovs_cache.get(defn[0])
        if hit and (time.time() - hit[0]) < OVERSEAS_TTL:
            slots[i] = hit[1]
        else:
            todo.append((i, defn))
    if not todo:
        return [r for r in slots if r], errors

    get_token(cfg)

    def one(item):
        i, (key, div, code, name, unit) = item
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
                return i, key, None, "값이 오지 않았습니다"
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
            return i, key, row, None
        except RuntimeError as e:
            return i, key, None, safe_message(e)

    with ThreadPoolExecutor(max_workers=KIS_MAX_PARALLEL) as pool:
        for i, key, row, err in pool.map(one, todo):
            if row:
                slots[i] = row
                _ovs_cache[key] = (time.time(), row)
            else:
                errors[key] = err
    return [r for r in slots if r], errors


# 지수 캐시 (2026-09-18 지시 — 5초).
#
# 0.7초였다. 화면은 **2초마다** 부르므로 캐시가 한 번도 안 맞고 매번 실제로
# 받았다. 지수 한 번이 여덟 건(국내 3 + 해외 4 + 선물 1)이라, **화면 하나가
# 초당 3.4건**을 썼다 — 예산 다섯 중 셋이다 (2026-09-18 실측. 호출한 스레드를
# 세어 보니 미리받기는 50초에 2~3회뿐이었고 나머지가 전부 이쪽이었다).
#
# 5초로 두면 2초 주기의 요청 중 대부분이 캐시로 받아진다. 값이 최대 5초 지난
# 것이 되지만 지수는 그 사이 눈에 띄게 움직이지 않는다.
#
# ⚠️ 선물(FUTURES_TTL)은 그대로 0.7초다. 지시가 「지수 캐시」였다.
# 그래서 요청마다 선물 한 건은 여전히 나간다.
INDEX_TTL = 5
_index_cache = {}


def _index_cache_get(key):
    hit = _index_cache.get(key)
    if hit and (time.time() - hit[0]) < INDEX_TTL:
        _stats["cache_hits"] += 1
        return hit[1]
    return None


def fetch_indices(cfg, with_chart=True):
    """국내 지수. **셋을 겹쳐 부른다** (2026-09-18).

    하나씩 부르면 KIS 응답을 기다리는 시간이 그대로 더해진다. 초당 건수는
    _rate_limit() 이 따로 지키므로 겹쳐도 한도를 넘지 않는다 — 겹치는 것은
    **기다리는 시간**뿐이다. quotes 가 진작부터 쓰던 방식이다.
    """
    errors = {}
    # **자리를 미리 잡아 둔다.** 캐시에 있는 것과 새로 받는 것이 섞이면
    # 순서가 INDEX_DEFS 와 달라진다. 화면이 순서대로 읽는 자리가 있어서
    # 코스피 자리에 코스닥이 올 수 있다.
    slots = [None] * len(INDEX_DEFS)
    todo = []
    for i, (code, name) in enumerate(INDEX_DEFS):
        cached = _index_cache_get("IDX:" + code)
        if cached is not None:
            slots[i] = cached
        else:
            todo.append((i, code, name))
    if not todo:
        return [r for r in slots if r], errors

    get_token(cfg)          # 동시에 발급을 시도하지 않도록 먼저 받아 둔다

    def one(item):
        i, code, name = item
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
            return i, code, name, {
                **info,
                "code": name, "name": name, "unit": "pt",
                "series": series, "source": "KIS",
            }, None
        except RuntimeError as e:
            return i, code, name, None, safe_message(e)

    with ThreadPoolExecutor(max_workers=KIS_MAX_PARALLEL) as pool:
        for i, code, name, row, err in pool.map(one, todo):
            if row:
                slots[i] = row
                _index_cache["IDX:" + code] = (time.time(), row)
            else:
                errors[name] = err
    return [r for r in slots if r], errors


def fetch_indices_all(cfg, with_chart=True, overseas=True):
    """국내 지수 **+ 해외·환율**을 합쳐서 준다. 반환은 `(목록, 오류)` 로 같다.

    **화면과 데일리분석이 같은 것을 봐야 한다.** 합치는 방법을 두 곳에 적으면
    한쪽만 고쳤을 때 조용히 갈린다 — 2026-09-22 에 데일리분석이
    `fetch_indices` 만 불러 **국내 넷만** 담았다. 화면은 열둘이었다.

    `overseas=False` 는 `?overseas=0` 으로 부르면 국내만 주는 길이다.
    **지금 화면은 그 쿼리를 안 쓴다** (2026-09-22 실측 — `holdings/js` 에 0곳.
    `home.js:205` 의 `overseas` 는 **응답 필드**이지 쿼리가 아니다).
    **배포본 워커가 같은 파라미터를 읽으므로**(`worker/kis-worker.js:3230`)
    짝을 맞춰 남겨 둔다 — 화면이 안 쓴다고 지우면 로컬과 배포본이 갈린다.
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_idx = pool.submit(fetch_indices, cfg, with_chart)
        f_ovs = pool.submit(fetch_overseas, cfg) if overseas else None
        data, errors = f_idx.result()
        if f_ovs is not None:
            ovs, ovs_err = f_ovs.result()
            data = data + ovs
            errors.update(ovs_err)
    return data, errors


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
        # **종목명을 넣지 않는다** (2026-09-18).
        #
        # 이 API 는 종목명을 안 준다. 응답 필드 80개를 다 훑었는데 이름은
        # `bstp_kor_isnm`(업종) 과 `rprs_mrkt_kor_name`(시장) 둘뿐이다.
        # 그 업종명을 `name` 으로 내보내고 있어서 삼성전자가 「전기·전자」로,
        # NAVER 가 「IT 서비스」로 나왔다.
        #
        # 워커는 이 자리에 `name` 을 아예 안 담는다. **같은 API 인데 응답
        # 모양이 갈려 있었다.** 빼서 맞춘다.
        #
        # 종목명이 필요한 자리는 멀티 조회(intstock-multprice)가 준다 —
        # 거기는 `inter_kor_isnm` 이라 진짜 종목명이다. 화면은 그것과
        # 목록(market.js · dart_universe)에서 이름을 가져온다.
        "price": _num(o.get("stck_prpr"), int),
        "change": _num(o.get("prdy_vrss"), int),
        "changePct": _num(o.get("prdy_ctrt")),
        "sign": sign,
        "open": _num(o.get("stck_oprc"), int),
        "high": _num(o.get("stck_hgpr"), int),
        "low": _num(o.get("stck_lwpr"), int),
        "volume": _num(o.get("acml_vol"), int),
        # **거래대금** (2026-09-22). 응답에 있는데 안 내보내고 있었다 —
        # 그래서 화면이 두 곳에서 `현재가 × 거래량` 으로 어림했고,
        # **오른 날에는 장중 평균가보다 현재가가 높아 부풀려졌다.**
        # 단위는 원이다 (`acml_tr_pbmn` = 누적 거래 대금).
        "value": _num(o.get("acml_tr_pbmn"), int),
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


# ---------------------------------------------------------------- 업종 · 순위 · 투자자
# 첫 화면의 「지금 뜨는 산업」 과 「외국인 · 기관 매매」 두 칸이 쓴다.
# 값은 전부 2026-09-17 에 직접 호출해 확인했다. 응답 필드 이름과 실제 값은
# docs/kis-sector-investor.md 에 적어 두었다. **추측으로 넣은 것은 없다.**
#
#   업종 등락률   inquire-index-category-price   FHPUP02140000
#   상승/하락률   ranking/fluctuation            FHPST01700000
#   투자자 추이   inquire-investor-daily-by-market FHPTJ04040000
#   순매수 상위   foreign-institution-total      FHPTJ04400000

# (KIS 시장구분, 우리가 쓰는 이름, 업종 기준 지수코드, 순위 API 의 종목코드)
SECTOR_MARKETS = [
    ("K", "KOSPI",  "0001", "0001"),
    ("Q", "KOSDAQ", "1001", "1001"),
]

# FID_BLNG_CLS_CODE. 3 이 업종(산업별)이다. 0(전체) 으로 부르면 파생지수까지
# 100개가 섞여 온다 — 2026-09-17 에 네 값을 다 불러보고 골랐다.
SECTOR_BLNG = "3"

# blng=3 인데도 업종이 아닌 것이 코스피 쪽에 둘 섞여 온다 (2026-09-17 실측).
# 지수 상품이라 「지금 뜨는 산업」 에 올라오면 안 된다. 코스닥 쪽은 깨끗하다.
SECTOR_SKIP = ["0244", "2283"]

SECTOR_TTL = 60            # 업종 지수는 초 단위로 움직이지 않는다
MOVERS_TTL = 30            # 상승률 순위는 장중에 자주 바뀐다
MOVERS_MAX = 30            # KIS 가 한 번에 주는 행 수 (더 달라고 해도 30개다)
INVESTOR_TOP_TTL = 120     # 가집계라 하루 네 번만 갱신된다 (아래 주석 참조)
INVESTOR_FLOW_TTL = 600    # 일별 자료라 장중에 한 번 바뀐다
INVESTOR_FLOW_DAYS = 30    # 화면이 보여주는 기간

_sector_cache = {}
_movers_cache = {}
_inv_top_cache = {}
_inv_flow_cache = {}


def _ttl_get(store, key, ttl):
    hit = store.get(key)
    if hit and (time.time() - hit[0]) < ttl:
        _stats["cache_hits"] += 1
        return hit[1]
    return None


def _sign_pct(row, key_sign, value):
    """KIS 는 등락률을 늘 양수로 주고 부호를 따로 준다 — 1상한 2상승 3보합 4하한 5하락.

    ranking/fluctuation 은 이미 부호가 붙어 오지만 업종은 안 붙어 오는 날이
    있어, 두 곳 모두 부호 칸을 보고 맞춘다.
    """
    if value is None:
        return None
    sign = str(row.get(key_sign) or "").strip()
    if sign in ("4", "5") and value > 0:
        return -value
    return value


def fetch_sectors(cfg, markets=None):
    """업종별 등락률. 시장 하나에 KIS 호출 한 번이다."""
    want = [m for m in SECTOR_MARKETS if not markets or m[1] in markets]
    out, errors = [], {}
    for mrkt, name, iscd, _rank_iscd in want:
        cached = _ttl_get(_sector_cache, name, SECTOR_TTL)
        if cached is not None:
            out.extend(cached)
            continue
        try:
            _stats["kis_calls"] += 1
            data = kis_get(
                cfg,
                "/uapi/domestic-stock/v1/quotations/inquire-index-category-price",
                {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": iscd,
                 "FID_COND_SCR_DIV_CODE": "20214", "FID_MRKT_CLS_CODE": mrkt,
                 "FID_BLNG_CLS_CODE": SECTOR_BLNG},
                "FHPUP02140000",
            )
        except RuntimeError as e:
            errors[name] = safe_message(e)
            continue
        rows = []
        for r in out_rows(data, "output2"):
            code = (r.get("bstp_cls_code") or "").strip()
            if not code or code in SECTOR_SKIP:
                continue
            rows.append({
                "code": code,
                "name": (r.get("hts_kor_isnm") or "").strip(),
                "market": name,
                "price": _num(r.get("bstp_nmix_prpr")),
                "amt": _sign_pct(r, "prdy_vrss_sign", _num(r.get("bstp_nmix_prdy_vrss"))),
                "pct": _sign_pct(r, "prdy_vrss_sign", _num(r.get("bstp_nmix_prdy_ctrt"))),
                "volume": _num(r.get("acml_vol"), int),
                "value": _num(r.get("acml_tr_pbmn"), int),
                "volShare": _num(r.get("acml_vol_rlim")),
                "valueShare": _num(r.get("acml_tr_pbmn_rlim")),
                "source": "KIS",
            })
        _sector_cache[name] = (time.time(), rows)
        out.extend(rows)
    return out, errors


def fetch_movers(cfg, direction="up", market="all", limit=MOVERS_MAX):
    """등락률 순위. 한 번 부르면 30행이 온다 (더 달라고 해도 늘지 않는다)."""
    iscd = "0000"
    if market and market != "all":
        iscd = next((m[3] for m in SECTOR_MARKETS if m[1] == market), "0000")
    sort = "1" if direction == "down" else "0"
    key = "%s:%s" % (sort, iscd)
    rows = _ttl_get(_movers_cache, key, MOVERS_TTL)
    if rows is None:
        _stats["kis_calls"] += 1
        data = kis_get(
            cfg,
            "/uapi/domestic-stock/v1/ranking/fluctuation",
            # fid_prc_cls_code 는 0 이면 저가대비, 1 이면 전일종가대비다.
            # 0 으로 두면 「저가에서 얼마나 올랐나」 로 줄이 세워져 등락률이
            # 마이너스인 종목이 1위로 온다 (2026-09-17 실측). 1 이 맞다.
            {"fid_cond_mrkt_div_code": "J", "fid_cond_scr_div_code": "20170",
             "fid_input_iscd": iscd, "fid_rank_sort_cls_code": sort,
             "fid_input_cnt_1": "0", "fid_prc_cls_code": "1",
             "fid_input_price_1": "", "fid_input_price_2": "", "fid_vol_cnt": "",
             "fid_trgt_cls_code": "0", "fid_trgt_exls_cls_code": "0",
             "fid_div_cls_code": "0", "fid_rsfl_rate1": "", "fid_rsfl_rate2": ""},
            "FHPST01700000",
        )
        rows = []
        for r in out_rows(data, "output"):
            code = (r.get("stck_shrn_iscd") or "").strip()
            if not code:
                continue
            rows.append({
                "code": code,
                "name": (r.get("hts_kor_isnm") or "").strip(),
                "rank": _num(r.get("data_rank"), int),
                "price": _num(r.get("stck_prpr"), int),
                "amt": _sign_pct(r, "prdy_vrss_sign", _num(r.get("prdy_vrss"), int)),
                "pct": _sign_pct(r, "prdy_vrss_sign", _num(r.get("prdy_ctrt"))),
                "volume": _num(r.get("acml_vol"), int),
                "high": _num(r.get("stck_hgpr"), int),
                "low": _num(r.get("stck_lwpr"), int),
                "source": "KIS",
            })
        _movers_cache[key] = (time.time(), rows)
    return rows[:max(1, min(limit, MOVERS_MAX))]


def _investor_side(r, prefix):
    return {
        "qty": _num(r.get(prefix + "_ntby_qty"), int),
        "amt": _num(r.get(prefix + "_ntby_tr_pbmn"), int),
    }


def fetch_investor_flow(cfg, market="KOSPI", days=INVESTOR_FLOW_DAYS):
    """시장 전체의 개인 · 외국인 · 기관 일별 순매수.

    FID_INPUT_DATE_1 이 **가장 최근 날짜**이고, 거기서 과거로 300영업일이
    한 번에 온다 (2026-09-17 실측 — 20260917 로 부르니 20250630 까지 왔다).
    그래서 30일치를 받는 데도 호출은 한 번이다.

    **날짜 순서를 뒤집어 돌려준다.** KIS 는 최근 → 과거 순으로 주는데,
    추이선은 왼쪽이 과거여야 해서 화면마다 뒤집으면 실수가 난다.
    """
    iscd_1 = "KSQ" if market == "KOSDAQ" else "KSP"
    iscd = "1001" if market == "KOSDAQ" else "0001"
    key = market
    rows = _ttl_get(_inv_flow_cache, key, INVESTOR_FLOW_TTL)
    if rows is None:
        today = _today_kst()
        _stats["kis_calls"] += 1
        data = kis_get(
            cfg,
            "/uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market",
            {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": iscd,
             "FID_INPUT_DATE_1": today, "FID_INPUT_ISCD_1": iscd_1,
             "FID_INPUT_DATE_2": today, "FID_INPUT_ISCD_2": iscd},
            "FHPTJ04040000",
        )
        rows = []
        for r in out_rows(data, "output"):
            date = (r.get("stck_bsop_date") or "").strip()
            if len(date) != 8:
                continue
            rows.append({
                "date": "%s-%s-%s" % (date[:4], date[4:6], date[6:]),
                "index": _num(r.get("bstp_nmix_prpr")),
                "indexAmt": _sign_pct(r, "prdy_vrss_sign", _num(r.get("bstp_nmix_prdy_vrss"))),
                "indexPct": _sign_pct(r, "prdy_vrss_sign", _num(r.get("bstp_nmix_prdy_ctrt"))),
                "retail": _investor_side(r, "prsn"),
                "foreign": _investor_side(r, "frgn"),
                "inst": _investor_side(r, "orgn"),
                "source": "KIS",
            })
        rows.reverse()                       # 과거 → 최근
        _inv_flow_cache[key] = (time.time(), rows)
    want = max(1, min(days, len(rows)))
    return rows[-want:]


# ── 종목별 투자자 · 호가 (2026-09-18 지시) ────────────────────────
#
# 차트 옆 패널의 「투자자 정보」 · 「매수 · 매도 비율」 · 「외국인 · 기관 매매」가
# 쓴다. **앞의 둘은 한 API 로 된다** — inquire-investor 가 개인 · 외국인 ·
# 기관을 한 응답에 준다.
#
# 이미 붙어 있던 investor-flow · investor-top 과는 다른 것이다.
#
#     investor-flow  시장 전체가 오늘 얼마나 샀나
#     investor-top   순매수 상위 종목 목록 (**가집계**)
#     여기           **지금 보고 있는 이 종목**을 누가 샀나 (확정치)
#
# 종목별은 **확정치**다 (docs/kis-sector-investor.md). 상위 목록 쪽만
# 가집계라 화면에 그렇게 적는다.
INVESTOR_DAYS = 30          # 한 번에 오는 일수. 늘릴 수 없다
ASKING_LEVELS = 10          # 호가 단계
INVESTOR_TTL = 60           # 일별 자료라 장중에 한 번 바뀐다
ASKING_TTL = 3              # 호가는 계속 움직인다. 화면이 훑을 때만 짧게 받아낸다

_investor_cache = {}
_asking_cache = {}


def fetch_investor(cfg, code, days=INVESTOR_DAYS):
    """종목별 투자자 매매. 개인 · 외국인 · 기관이 한 응답에 온다.

    30일치가 한 번에 오고 그보다 길게는 못 받는다 (2026-09-16 실측).
    """
    cached = _ttl_get(_investor_cache, code, INVESTOR_TTL)
    if cached is not None:
        return cached
    _stats["kis_calls"] += 1
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-investor",
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
        "FHKST01010900",
    )
    out = []
    for r in out_rows(data, "output")[:days]:
        def side(prefix):
            return {
                "net": _num(r.get(prefix + "_ntby_qty"), int),
                "netAmt": _num(r.get(prefix + "_ntby_tr_pbmn"), int),
                "buy": _num(r.get(prefix + "_shnu_vol"), int),
                "sell": _num(r.get(prefix + "_seln_vol"), int),
            }
        out.append({
            "date": r.get("stck_bsop_date"),
            "close": _num(r.get("stck_clpr"), int),
            "amt": _num(r.get("prdy_vrss"), int),
            "person": side("prsn"),
            "foreign": side("frgn"),
            "inst": side("orgn"),
        })
    _investor_cache[code] = (time.time(), out)
    return out


# ── 종목별 장중 추정가집계 (2026-09-22 지시) ────────────────────
#
# 재권님 말씀 — 「응 보고싶어」 · 「우선되는거 연결해놓고 나중에 퀄업한다.
# **출처만 알수있게 해놔**」.
#
# 위 `fetch_investor` 는 장중에 오늘 줄을 `net: null` 로 준다 (11:03 · 12:00
# 실측). 네이버는 대안이 못 된다 — 경로 셋이 전부 어제까지이고 다른 이름
# 셋은 404 다 (2026-09-22 실측). **표본이 아니라 구조다.**
#
# ⚠️ **가집계다.** KIS 설명 그대로 「증권사 직원이 장중에 집계/입력한 자료를
# 단순 누계한 수치」이고 **마감 뒤 숫자가 달라진다.** 화면에 그대로 적는다.
#
# ⚠️ **개인이 없다.** 응답 필드가 외국인·기관·합계 셋뿐이다. 종목별로 개인까지
# 주는 곳은 못 찾았다 (네이버·다음·FnGuide·인베스팅·KRX·공공데이터포털).
# 재권님이 그것을 아시고 이 안을 고르셨다.
#
# ── `bsop_hour_gb` 는 회차 번호다 (2026-09-22 11:21 실측) ──
#
#     삼성전자   gb=1  외국인 -246,000 · 기관       0    ← 기관 첫 입력 전
#                gb=2  외국인  +26,000 · 기관 +42,000
#                gb=3  외국인 -116,000 · 기관 +128,000   ← 최신
#
# **큰 것이 최신이다.** 응답에 **시각이 없다** — 몇 시 것인지는 KIS 문서의
# 입력 시각(외국인 09:30·11:20·13:20·14:30 / 기관 10:00·11:20·13:20·14:30,
# ±10분)으로 미룰 뿐이다. gb=1 에 기관이 0 인 것이 그 짐작과 맞는다.
# **회차와 시각의 대응은 아직 못 박지 않았다** — 화면에 시각을 적지 않는다.
INVESTOR_EST_TTL = 60      # 하루 네 번만 바뀐다. 자주 부를 이유가 없다
_investor_est_cache = {}


def fetch_investor_estimate(cfg, code):
    """종목별 외국인·기관 추정가집계. 장중에만 뜻이 있다."""
    cached = _ttl_get(_investor_est_cache, code, INVESTOR_EST_TTL)
    if cached is not None:
        return cached
    _stats["kis_calls"] += 1
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/investor-trend-estimate",
        {"MKSC_SHRN_ISCD": code},
        "HHPTJ04160200",
    )
    rows = []
    for r in out_rows(data, "output2"):
        rows.append({
            "seq": _num(r.get("bsop_hour_gb"), int),
            "foreign": _num(r.get("frgn_fake_ntby_qty"), int),
            "inst": _num(r.get("orgn_fake_ntby_qty"), int),
            "sum": _num(r.get("sum_fake_ntby_qty"), int),
        })
    # **최신이 앞에 오게 한다.** 화면은 첫 줄만 쓴다
    rows.sort(key=lambda x: (x["seq"] is None, -(x["seq"] or 0)))
    out = {"latest": rows[0] if rows else None, "rows": rows}
    _investor_est_cache[code] = (time.time(), out)
    return out


# 체결은 한 번에 30줄이 온다. 화면이 그보다 많이 보여줄 일이 없다.
TICKS_TTL = 3              # 장중에는 계속 쌓인다. 화면이 볼 때만 짧게 받아낸다
_ticks_cache = {}


def fetch_ticks(cfg, code):
    """최근 체결 30줄 (2026-09-21 지시 — A 종목 화면).

    KIS `주식현재가 체결`(FHKST01010300). **한 번에 30줄이 오고 그게 전부다** —
    더 과거는 안 준다. 화면의 「시세」 칸이 그대로 쓴다.

    `tday_rltv` 가 **체결강도**다. 100 이 기준이고 그보다 크면 산 쪽이 세다.
    줄마다 같은 값이 와서 머리줄에 한 번만 적는다.
    """
    hit = _ticks_cache.get(code)
    if hit and (time.time() - hit[0]) < TICKS_TTL:
        return hit[1]

    r = kis_get(cfg, "/uapi/domestic-stock/v1/quotations/inquire-ccnl",
                {"FID_COND_MRKT_DIV_CODE": quote_market_div(),
                 "FID_INPUT_ISCD": code},
                "FHKST01010300")
    rows = []
    for o in (r.get("output") or []):
        hhmmss = (o.get("stck_cntg_hour") or "").strip()
        rows.append({
            # 091646 → 09:16:46. 화면에서 자르지 않게 여기서 넣는다
            "at": ("%s:%s:%s" % (hhmmss[:2], hhmmss[2:4], hhmmss[4:6])
                   if len(hhmmss) == 6 else hhmmss),
            "price": _num(o.get("stck_prpr")),
            "volume": _num(o.get("cntg_vol")),
            "diff": _num(o.get("prdy_vrss")),
            "pct": _num(o.get("prdy_ctrt")),
            # 1 상한 · 2 상승 · 3 보합 · 4 하한 · 5 하락 (KIS 공통)
            "dir": (o.get("prdy_vrss_sign") or "3").strip(),
        })
    out = {"rows": rows,
           "power": _num((r.get("output") or [{}])[0].get("tday_rltv"))}
    _ticks_cache[code] = (time.time(), out)
    return out


def fetch_asking(cfg, code):
    """호가 10단계. **매수 · 매도 비율**은 총잔량으로 낸다.

    비율은 「지금 사자가 얼마나 몰려 있나」다. 체결된 것이 아니라 **대기 중인
    주문**이므로, 장이 끝나면 의미가 옅어진다 — 화면에 그렇게 적는다.
    """
    cached = _ttl_get(_asking_cache, code, ASKING_TTL)
    if cached is not None:
        return cached
    _stats["kis_calls"] += 1
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
        "FHKST01010200",
    )
    o = data.get("output1") or {}
    ask, bid = [], []
    for i in range(1, ASKING_LEVELS + 1):
        ask.append({"price": _num(o.get("askp%d" % i), int),
                    "qty": _num(o.get("askp_rsqn%d" % i), int)})
        bid.append({"price": _num(o.get("bidp%d" % i), int),
                    "qty": _num(o.get("bidp_rsqn%d" % i), int)})
    tot_ask = _num(o.get("total_askp_rsqn"), int) or 0
    tot_bid = _num(o.get("total_bidp_rsqn"), int) or 0
    both = tot_ask + tot_bid
    out = {
        "ask": {"total": tot_ask, "levels": ask},
        "bid": {"total": tot_bid, "levels": bid},
        # 사자 비중. 50 보다 크면 사려는 주문이 더 쌓여 있다는 뜻이다
        "buyPct": round(tot_bid / both * 100, 1) if both else None,
    }
    _asking_cache[code] = (time.time(), out)
    return out


def fetch_investor_top(cfg, direction="buy", market="all", by="qty", limit=10):
    """외국인 · 기관 순매수(순매도) 상위.

    ⚠️ **가집계다.** KIS 공식 설명에 "증권사 직원이 장중에 집계/입력한 자료를
    단순 누계한 수치" 라고 적혀 있고, 입력 시각은 외국인 09:30 · 11:20 ·
    13:20 · 14:30, 기관 10:00 · 11:20 · 13:20 · 14:30 이다 (±10분).
    장 마감 뒤 확정치와 다를 수 있으므로 화면에 「가집계」 임을 적는다.
    """
    iscd = "0000"
    if market and market != "all":
        iscd = next((m[3] for m in SECTOR_MARKETS if m[1] == market), "0000")
    sort = "1" if direction == "sell" else "0"      # 0 순매수상위 · 1 순매도상위
    div = "1" if by == "amt" else "0"               # 0 수량정렬 · 1 금액정렬
    out, errors = {}, {}
    # FID_ETC_CLS_CODE — 0 전체 · 1 외국인 · 2 기관계 · 3 기타
    for who, etc in (("foreign", "1"), ("inst", "2")):
        key = "%s:%s:%s:%s" % (who, sort, div, iscd)
        rows = _ttl_get(_inv_top_cache, key, INVESTOR_TOP_TTL)
        if rows is None:
            try:
                _stats["kis_calls"] += 1
                data = kis_get(
                    cfg,
                    "/uapi/domestic-stock/v1/quotations/foreign-institution-total",
                    {"FID_COND_MRKT_DIV_CODE": "V", "FID_COND_SCR_DIV_CODE": "16449",
                     "FID_INPUT_ISCD": iscd, "FID_DIV_CLS_CODE": div,
                     "FID_RANK_SORT_CLS_CODE": sort, "FID_ETC_CLS_CODE": etc},
                    "FHPTJ04400000",
                )
            except RuntimeError as e:
                errors[who] = safe_message(e)
                continue
            rows = []
            for r in out_rows(data, "output"):
                code = (r.get("mksc_shrn_iscd") or "").strip()
                if not code:
                    continue
                rows.append({
                    "code": code,
                    "name": (r.get("hts_kor_isnm") or "").strip(),
                    "price": _num(r.get("stck_prpr"), int),
                    "amt": _sign_pct(r, "prdy_vrss_sign", _num(r.get("prdy_vrss"), int)),
                    "pct": _sign_pct(r, "prdy_vrss_sign", _num(r.get("prdy_ctrt"))),
                    "volume": _num(r.get("acml_vol"), int),
                    # net — 이 줄이 무엇으로 줄 세워졌는지에 해당하는 값
                    "net": _investor_side(r, "frgn" if who == "foreign" else "orgn"),
                    "foreign": _investor_side(r, "frgn"),
                    "inst": _investor_side(r, "orgn"),
                    "source": "KIS",
                })
            _inv_top_cache[key] = (time.time(), rows)
        out[who] = rows[:max(1, min(limit, MOVERS_MAX))]
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


def minute_market_div(hour):
    """분봉을 어느 시장에서 받을까. **구간의 시각으로 정한다.**

        정규장 09:00~15:30   J  (KRX)
        그 밖                UN (통합)

    일봉과 달리 **분봉은 한쪽만으로는 못 채운다** (2026-09-17 실측).

        08:30 프리마켓   J  0개      UN 30개   ← 넥스트레이드는 통합에만 있다
        10:30 장중       J 30개      UN 30개
        우선주 장중      J 30개      UN  0개   ← 통합은 값이 비어 온다

    삼성전자우 5분봉이 하루 종일 194,600원에 거래량 0 이었던 것이 이 때문이다.
    통합으로 받아 놓고 "거래가 없는 종목" 으로 보고 있었는데, KRX 로 부르면
    193,200원에 거래량이 정상으로 온다.

    시세 표기 규칙(CLAUDE.md)이 현재가를 가르는 방식과 같다.
    """
    try:
        m = int(hour[:2]) * 60 + int(hour[2:4])
    except Exception:
        return MARKET_DIV_CHART
    hm = (m // 60, m % 60)
    return "J" if KRX_OPEN <= hm < KRX_CLOSE else MARKET_DIV_CHART


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
            "FID_ETC_CLS_CODE": "", "FID_COND_MRKT_DIV_CODE": minute_market_div(hour),
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


# 마지막 봉이 이보다 오래됐으면 최근 구간만 받지 않고 하루치를 다시 모은다.
# 장중 한 시간이면 12개가 비는 셈이라, 그 정도면 통째로 받는 편이 낫다.
MINUTE_REFILL_GAP = 60


# ── 5분봉 미리 받아두기 ────────────────────────────────────────────
#
# 화면이 종목을 처음 열 때 하루치를 받으면 **3.1초**가 걸린다 (2026-09-17 실측).
# 30분씩 거슬러 올라가며 여러 번 부르기 때문이고, 저녁일수록 구간이 늘어
# 더 느려진다. 마우스로 순위표를 훑으면 종목마다 그만큼 걸린다.
#
# 그래서 **뒤에서 미리 받아 둔다** (2026-09-17 지시 — "5분봉은 지난거는
# 미리 다운받아서 가지고 있다가 마우스 올리면 보여지는거지?").
# 코스피 시가총액 상위 순으로 간다.
#
# ⚠️ **화면이 느려지면 안 된다.** 모든 KIS 호출이 초당 5건 줄에 서므로,
# 미리 받기가 연달아 부르면 그 뒤에 온 화면 요청이 밀린다. 종목 사이에
# 쉬어서 그 틈으로 화면 요청이 들어가게 한다.
PREFILL_TOP = 100          # 코스피 상위 몇 종목까지
# 종목 하나를 마치고 쉬는 시간 — 화면에 양보한다.
#
# 2.0 초로 뒀더니 **KIS 예산의 3분의 2를 계속 쓰고 있었다** (2026-09-17 실측
# 초당 3.1~3.4회 · 예산 5회). 화면은 0.2초를 지켰지만 남은 여유가 1.6회/초뿐이라,
# 순위표를 빠르게 훑으면 그것마저 밀린다.
#
# 3.5 초로 늘리면 미리 받기가 초당 1.4회쯤이 된다. 한 바퀴가 6분에서 8분으로
# 늘어날 뿐인데, **하루 한 번 도는 것이라 그 차이는 아무 뜻이 없다.**
PREFILL_REST_SEC = 3.5
PREFILL_START_SEC = 20     # 서버가 뜨고 이만큼 뒤에 시작 (첫 화면에 양보)
PREFILL_ROUND_SEC = 1800   # 한 바퀴 돌고 쉬는 시간. 실제 호출은 dayfill 이 막는다

# ── 화면이 보고 있으면 더 쉰다 (2026-09-18) ────────────────────────
#
# 위 3.5 초는 **화면이 없을 때** 기준이다. 종목 하나가 하루치 5분봉을 받느라
# KIS 를 스물몇 번 부르므로, 쉬는 시간을 그만큼 잡아도 초당 3회쯤을 계속 쓴다.
# 예산이 초당 5회라 화면 몫이 2회밖에 안 남는다.
#
# **실측 (2026-09-18)** — 브라우저를 하나도 안 띄운 상태에서
#
#     /api/kis/stats   초당 4.9회 · 예산 사용률 98%
#     지수 한 번        7 ~ 10초   (2초마다 부르도록 만든 요청이다)
#
# 지수는 한 번에 여덟 번을 부르는데(국내 3 + 해외 4 + 선물 1) 그 여덟이
# 미리받기 뒤에 줄을 서서 이렇게 됐다. 화면에서는 지수가 멈춰 보이고,
# 브라우저 연결(호스트당 여섯)을 다 물고 있어 **시세까지 밀린다.**
#
# 그래서 화면이 최근에 불렀으면 쉬는 시간을 크게 잡는다. 미리받기는
# 하루 한 번 돌면 되는 일이라 늦어져도 잃는 것이 없다.
PREFILL_BUSY_REST_SEC = 20.0   # 화면이 보고 있을 때 종목 사이 쉬는 시간
PREFILL_BUSY_WINDOW = 15.0     # 이 시간 안에 화면이 불렀으면 '보고 있다'로 본다

# **종목 사이만 쉬어서는 모자란다.** 한 종목의 하루치 5분봉이 KIS 를 스무 번
# 넘게 부르는데, 그 스무 번이 연달아 차례를 가져가기 때문이다. 지수 여덟 번이
# 그 사이에 한 번씩 끼어드는 꼴이 되어 **10초**가 걸렸다 (2026-09-18 실측 —
# 종목 사이 20초 양보를 넣은 뒤에도 4.5 → 8.6 → 10.0 → 10.2초).
#
# 그래서 **호출 하나하나**를 미룬다. 화면이 조용하면 이 값은 안 쓰인다.
PREFILL_BUSY_CALL_GAP = 2.0    # 화면이 보고 있을 때 미리받기 호출 사이 여유

# **화면이 없을 때도 예산을 다 쓰지는 않는다** (2026-09-18).
#
# 위 양보는 화면이 부르기 **시작한 뒤**에 걸린다. 그 전에 미리받기가 이미
# 차례를 예약해 둔 호출들이 있어서, **화면을 막 열었을 때 첫 지수 요청이
# 그 뒤에 줄을 선다.**
#
#     화면이 계속 보고 있을 때   1.05 ~ 1.96초
#     화면을 막 열었을 때        4.74 ~ 6.42초   ← 이것이 남아 있었다
#
# 그래서 평소에도 호출 사이에 이만큼 둔다. 미리받기가 초당 두 번쯤이 되어
# 예산 다섯 중 셋이 늘 비어 있고, 화면이 열리는 순간 그 자리로 들어간다.
# 한 바퀴가 느려지지만 하루 한 번 도는 일이라 잃는 것이 없다.
PREFILL_IDLE_CALL_GAP = 0.3    # 화면이 없을 때도 두는 여유
PREFILL_THREAD_NAME = "prefill-5m"

# ── 새 봉이 생겼을 때만 받는다 (2026-09-18 지시) ──────────────────
#
# 재권님 말씀 — "5분봉 미리받기 → 5분봉 갱신될때만 받기 /
# 5분봉은 선택된 화면만 실시간으로 받기".
#
# **5m 의 fresh_sec 은 30초인데 한 바퀴가 6~8분이다.** 돌아왔을 때는 이미
# 30초를 훌쩍 넘겨서 **매번 다시 받았다.** 「dayfill 이 오늘 것을 이미
# 받았으면 건너뛴다」 는 주석과 달리 건너뛰는 일이 거의 없었다.
#
#     캐시 적중률   66 / 919 = 6.7%      (2026-09-18 실측)
#     호출          초당 3.2회           화면을 안 보고 있는데도
#
# **5분봉은 5분에 한 번만 새 봉이 생긴다.** 그 사이에 다시 받는 것은 같은
# 값을 또 받는 것이다. 마지막으로 받은 지 이만큼 안 지났으면 건너뛴다.
#
# 화면이 직접 여는 종목은 이 길로 오지 않는다. get_chart 가 fresh_sec(30초)
# 으로 따로 판단하므로 **보고 있는 종목만 실시간**이 된다 — 지시 그대로다.
PREFILL_FRESH_SEC = 300

_last_ui_at = 0.0              # 화면이 마지막으로 /api/kis/* 를 부른 시각


def _mark_ui_call():
    """화면이 KIS 를 썼다고 적어 둔다. 미리받기가 이것을 보고 양보한다."""
    global _last_ui_at
    _last_ui_at = time.monotonic()


def _ui_busy():
    return (time.monotonic() - _last_ui_at) < PREFILL_BUSY_WINDOW


def _prefill_codes():
    """미리 받을 종목. 코스피 시가총액 상위 순서."""
    try:
        with dart._db_lock, dart.db_conn() as conn:
            rows = conn.execute(
                "SELECT stock_code FROM dart_universe ORDER BY rank LIMIT ?",
                (PREFILL_TOP,),
            ).fetchall()
        codes = [r["stock_code"] for r in rows]
    except Exception:
        codes = []
    if not codes:                      # 순위가 아직 없으면 관심종목이라도
        codes = list(dart.WATCH_CODES)
    return codes


def start_prefill(cfg):
    """뒤에서 5분봉을 미리 채운다. 키가 없으면 아무것도 하지 않는다."""
    if not cfg:
        return False

    def loop():
        time.sleep(PREFILL_START_SEC)
        while True:
            try:
                for code in _prefill_codes():
                    # 새 봉이 생겼을 때만 받는다. 5분봉은 5분에 하나씩 생긴다
                    last = float(_meta_get("sync:%s:5m" % code) or 0)
                    if (time.time() - last) < PREFILL_FRESH_SEC:
                        continue       # 같은 값을 또 받지 않는다
                    try:
                        # 하루치는 하루 한 번만. 나머지는 최근 구간만 받는다
                        get_chart(cfg, code, "5m", 1, gap_check=False)
                    except Exception:
                        pass           # 한 종목이 실패해도 나머지는 간다
                    # 화면이 보고 있으면 길게 쉰다. 지수·시세가 먼저다
                    time.sleep(PREFILL_BUSY_REST_SEC if _ui_busy()
                               else PREFILL_REST_SEC)
            except Exception:
                pass
            time.sleep(PREFILL_ROUND_SEC)

    threading.Thread(target=loop, daemon=True, name="prefill-5m").start()
    return True


def _today_kst():
    """오늘 날짜(한국) YYYYMMDD.

    get_chart 안에 `import datetime`(모듈)이 있어서 그 안에서는 전역의
    `from datetime import datetime` 이 가려진다. 날짜 만드는 곳을 하나로
    모아 그 함정을 피한다 (2026-09-17 에 걸렸다).
    """
    return datetime.now(KST).strftime("%Y%m%d")


def _minutes_need_day(code, period, rows, gap_check=True):
    """하루치를 통째로 받아야 하나.

    **두 가지를 본다. 하나만 보면 구멍이 남는다.**

      1. 오늘 하루치를 아직 안 받았다        → 받는다
      2. 마지막 봉이 한 시간 넘게 오래됐다   → 받는다

    처음에는 2번만 봤는데, 최근 봉이 있으면 **앞쪽 구멍을 안 메웠다.**
    삼성전자우가 10:15~10:50 만 있고 09:00~10:15 가 빈 채로 남았다
    (2026-09-17). 마지막 봉만 보면 "방금 받았으니 됐다" 가 되어 버린다.

    1번은 하루 한 번만 걸린다. 날짜를 값에 넣어 키가 늘어나지 않게 한다.
    """
    if _meta_get("dayfill:%s:%s" % (code, period)) != _today_kst():
        return True
    if not rows:
        return True
    # **미리받기는 2번을 안 본다** (2026-09-18).
    #
    # 장이 끝나면 거래가 뜸한 종목은 마지막 봉이 계속 오래된 채로 있다.
    # 그러면 2번이 **늘 참**이 되어 미리받기가 한 바퀴 돌 때마다 하루치를
    # 다시 받았다 — 한 종목에 스물몇 번이다. 오늘 실측에서 5분 간격을
    # 넣고도 초당 4.8회가 그대로였던 것이 이 때문이다.
    #
    # 화면이 여는 종목은 그대로 2번을 본다. 앞쪽 구멍을 메워야 하고,
    # 한 종목이라 부담도 작다.
    if not gap_check:
        return False
    try:
        ts = rows[-1]["ts"]                      # YYYYMMDDHHMM
        last = datetime(int(ts[0:4]), int(ts[4:6]), int(ts[6:8]),
                        int(ts[8:10]), int(ts[10:12]), tzinfo=KST)
        gap = (datetime.now(KST) - last).total_seconds() / 60
    except Exception:
        return True                              # 읽을 수 없으면 다시 받는 쪽으로
    return gap > MINUTE_REFILL_GAP


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


def get_chart(cfg, code, period, limit, gap_check=True):
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
            # 많이 비었으면 하루치를 모으고(호출 여러 번), 조금이면 최근 구간만.
            #
            # **「있나 없나」로 가르면 안 된다.** 전에는 rows 가 하나라도 있으면
            # 최근 구간만 받았는데, 며칠 전 것이 남아 있는 종목은 오늘 것이
            # 통째로 비었다 — 삼성전자우가 09:00~10:15 가 없이 7개뿐이었다
            # (2026-09-17). 거래가 잦은 종목만 자주 열려 저절로 채워지고
            # 있었던 것이라, 종목마다 봉 개수가 크게 갈렸다.
            if _minutes_need_day(code, period, rows, gap_check):
                raw = fetch_minutes_day(cfg, code)
                _meta_set("dayfill:%s:%s" % (code, period), _today_kst())
            else:
                raw = fetch_minutes_from_kis(cfg, code)
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
            _mark_ui_call()          # 미리받기가 양보하도록 알린다
            self._handle_kis()
            return
        if (self.path or "").startswith("/api/dart/"):
            self._handle_dart()
            return
        if (self.path or "").startswith("/api/news/"):
            self._handle_news()
            return
        if (self.path or "").startswith("/api/naver/"):
            _mark_ui_call()          # 화면이 보고 있다는 신호는 여기서도 준다
            self._handle_naver()
            return
        if (self.path or "").startswith("/api/board/"):
            self._handle_board()
            return
        if (self.path or "").startswith("/debugging/"):
            self._handle_debugging()
            return
        super().do_GET()

    def _handle_board(self):
        """문서 저장 — 보드 셋 · AI 분석 · 데일리분석이 함께 쓴다.

        **배포본 워커(`projects/worker/board-api.js`)를 그대로 흉내 낸다.**
        `CLAUDE.md` 가 그렇게 정해 뒀다 — 맥미니 서버가 나중에 같은 모양으로
        응답하면 화면은 한 줄도 안 고치고 주소만 바꾸면 된다.

            GET  /api/board/health          살아 있나
            GET  /api/board/doc/<이름>      읽기
            PUT  /api/board/doc/<이름>      쓰기  {"data": …}

        **워커와 다른 것 하나** — 그쪽은 Access 로 사람을 가려 `owner` 별로
        나눠 담는다. 이 서버는 재권님 PC 안에서만 돌아 가릴 사람이 없다.
        그래서 `owner` 를 안 쓰고 응답에도 안 싣는다.
        """
        path = (self.path or "").split("?", 1)[0].rstrip("/")

        if path == "/api/board/health":
            self._send_json({
                "ok": True,
                "root": docstore.DOC_ROOT,
                "docs": len(docstore.list_docs()),
            })
            return

        m = re.match(r"^/api/board/doc/([^/]+)$", path)
        if not m:
            self._send_json({"ok": False,
                             "error": "여기는 문서 저장입니다. /api/board/doc/<이름> 로 부르세요."},
                            status=404)
            return

        name = urllib.parse.unquote(m.group(1))
        try:
            if self.command == "GET":
                data = docstore.read_doc(name)
                self._send_json({"ok": True, "doc": name, "data": data})
                return

            if self.command == "PUT":
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                try:
                    body = json.loads(raw.decode("utf-8"))
                except Exception:
                    self._send_json({"ok": False, "error": "본문이 JSON 이 아닙니다."},
                                    status=400)
                    return
                if not isinstance(body, dict) or "data" not in body:
                    self._send_json({"ok": False, "error": "저장할 내용(data)이 없습니다."},
                                    status=400)
                    return

                # `history=false` 로 끌 수 있다. 기본은 켠 쪽이다 —
                # 안전한 쪽이 기본이어야 하고, 끄는 쪽이 밝히는 것이 맞다.
                keep = body.get("history", True) is not False
                wrote = docstore.write_doc(name, body["data"], history=keep)

                # **「안 썼다」 를 조용히 넘기지 않는다.** 빈 것을 보냈는데
                # ok: true 만 오면 저장된 줄 안다.
                self._send_json({"ok": True, "doc": name, "wrote": wrote,
                                 "skipped": None if wrote else "빈 내용이라 쓰지 않았습니다"})
                return

            self._send_json({"ok": False, "error": "GET 또는 PUT 만 됩니다."}, status=405)
        except docstore.DocNameError as e:
            self._send_json({"ok": False, "error": str(e)}, status=400)
        except Exception as e:
            # 경로에 이름이 섞여 있을 수 있어 종류만 올린다
            self._send_json({"ok": False, "error": "저장하지 못했습니다 (%s)" % type(e).__name__},
                            status=500)

    def do_PUT(self):
        """쓰기는 한 곳뿐이다 — 「중요」 알림 규칙 (2026-09-21 지시).

        재권님이 데일리분석 화면에서 낱말을 넣고 빼는 자리라 저장할 곳이
        필요했다. **이 서버에서만 된다** — 배포본(워커)에는 파일을 쓸 곳이 없다.
        """
        if (self.path or "").startswith("/api/news/"):
            self._handle_news()
            return
        if (self.path or "").startswith("/api/board/"):
            self._handle_board()
            return

        # **딸려 온 본문을 먼저 비운다.** 안 읽고 응답하면 보내는 쪽이
        # 아직 쓰고 있는 중에 연결이 닫혀 깨진다.
        try:
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
        except Exception:
            pass

        # **HTTP 상태 줄에는 한글을 쓸 수 없다.** 그 줄은 latin-1 로 인코딩되므로
        # `send_error(405, "PUT 은 …")` 처럼 설명을 넘기면 그 자리에서
        # UnicodeEncodeError 로 죽고 **응답이 통째로 안 나간다**(2026-09-21 실측).
        #
        #     send_response_only → (self.protocol_version, code, message).encode('latin-1')
        #     UnicodeEncodeError: 'latin-1' codec can't encode character '은'
        #
        # 겉으로는 405 가 아니라 **빈 응답**으로 보여서 원인을 알 수 없다.
        # 설명은 본문(JSON)에 담는다 — 다른 응답과 모양도 같아진다.
        self._send_json({"ok": False,
                         "error": "PUT 은 /api/news/alerts 에만 됩니다."}, 405)

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
    # ── 네이버 업종 · 테마 (2026-09-18) ──
    #
    # 「지금 뜨는 산업」 이 쓴다. KIS 에 없는 둘 때문에 여기서 받는다 —
    # 업종 안에서 몇이 오르내렸는지, 그리고 그 업종의 종목 목록이다.
    # 자세한 것은 server/naver.py 머리글과 docs/sector-sources.md 에 있다.
    def _handle_naver(self):
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path[len("/api/naver/"):].strip("/")
        qs = urllib.parse.parse_qs(parsed.query)
        kind = (qs.get("kind") or ["industry"])[0].strip()

        try:
            if route == "groups":
                g = naver.groups(kind)
                self._send_json({
                    "ok": True, "data": g["rows"],
                    "meta": {"kind": kind, "total": g["total"],
                             "marketStatus": g["marketStatus"],
                             "count": len(g["rows"]), "source": "네이버"},
                })
                return

            # 종목별 뉴스 (2026-09-18 지시 — 「이 종목 공시」를 뉴스로 바꿨다)
            if route == "news":
                code = (qs.get("code") or [""])[0].strip()
                if not (code.isdigit() and len(code) == 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                rows = naver.news(code)
                self._send_json({
                    "ok": True, "data": rows,
                    "meta": {"code": code, "count": len(rows), "source": "네이버"},
                })
                return

            # 종목 한 장 요약 — 일별 매매동향 5일 + 지표 18개 + 시총 순위
            if route == "integration":
                code = (qs.get("code") or [""])[0].strip()
                if not (code.isdigit() and len(code) == 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                d = naver.integration(code)
                self._send_json({"ok": True, "data": d,
                                 "meta": {"code": code, "days": len(d["flow"]),
                                          "source": "네이버"}})
                return

            # 종목토론 (2026-09-18 지시 — 투자자 정보와 종목 뉴스 사이)
            if route == "discuss":
                code = (qs.get("code") or [""])[0].strip()
                if not (code.isdigit() and len(code) == 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                rows = naver.discuss(code)
                self._send_json({
                    "ok": True, "data": rows,
                    "meta": {"code": code, "count": len(rows), "source": "네이버"},
                })
                return

            if route == "stocks":
                no = (qs.get("no") or [""])[0].strip()
                if not no.isdigit():
                    self._send_json({"ok": False, "error": "no 에 묶음 번호가 필요합니다."}, 400)
                    return
                s = naver.stocks(kind, no)
                self._send_json({
                    "ok": True, "data": s["rows"],
                    "meta": {"kind": kind, "no": int(no), "name": s["name"],
                             "count": len(s["rows"]), "source": "네이버"},
                })
                return

            self._send_json({"ok": False, "error": "알 수 없는 경로입니다: %s" % route}, 404)
        except ValueError as e:
            self._send_json({"ok": False, "error": safe_message(e)}, 400)
        except Exception as e:                      # 네이버가 막히거나 모양이 바뀐 경우
            self._send_json({"ok": False, "error": safe_message(e)}, 502)

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

            # 쌓아 둔 뉴스 — 묶음 단위 (2026-09-21 지시)
            #
            # `issues` 와 다르다. 저쪽은 **지금 RSS 를 받아** 돌려주고,
            # 이쪽은 **쌓아 둔 것을 읽는다.** 화면이 열릴 때마다 RSS 를
            # 파싱하지 않으므로 빠르고, 지나간 기사도 남아 있다.
            if route == "stored":
                qs = urllib.parse.parse_qs(parsed.query)
                hours = int((qs.get("hours") or ["24"])[0])
                limit = int((qs.get("limit") or ["80"])[0])
                rows = news_store.groups(hours=hours, limit=limit)
                self._send_json({"ok": True, "data": rows,
                                 "meta": {"hours": hours, "count": len(rows),
                                          "topics": news_store.counts(hours),
                                          "total": news_store.total()}})
                return

            # 무엇을 「중요」로 볼지. 화면에서 고치는 자리다
            if route == "alerts":
                if self.command == "PUT":
                    n = int(self.headers.get("Content-Length") or 0)
                    body = json.loads(self.rfile.read(n).decode("utf-8")) if n else None
                    if not isinstance(body, dict) or "즉시알림" not in body:
                        self._send_json({"ok": False,
                                         "error": "즉시알림 목록이 있어야 합니다."}, 400)
                        return
                    news_store.save_alerts(body)
                    self._send_json({"ok": True, "data": news_store.load_alerts()})
                    return
                self._send_json({"ok": True, "data": news_store.load_alerts()})
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
                want_ovs = (qs.get("overseas") or ["1"])[0] != "0"
                # 국내 · 해외 · 선물을 **함께 진행한다** (2026-09-18).
                # 하나씩 기다리면 셋의 응답 시간이 그대로 더해졌다.
                # 해외 지수·환율도 같은 응답에 실어 보낸다 — 화면이 한 번만 부르면 된다.
                with ThreadPoolExecutor(max_workers=2) as pool:
                    f_all = pool.submit(fetch_indices_all, cfg, with_chart, want_ovs)
                    f_fut = pool.submit(fetch_futures, cfg)
                    data, errors = f_all.result()
                    futures = f_fut.result()
                self._send_json({"ok": bool(data), "data": data,
                                 "futures": futures, "errors": errors or None})
                return

            if route == "sectors":
                want = (qs.get("market") or ["all"])[0].strip().upper()
                markets = None if want in ("", "ALL") else [want]
                if markets and markets[0] not in [m[1] for m in SECTOR_MARKETS]:
                    self._send_json({
                        "ok": False,
                        "error": "market 은 %s 중 하나여야 합니다." %
                                 ", ".join(m[1] for m in SECTOR_MARKETS),
                    }, 400)
                    return
                data, errors = fetch_sectors(cfg, markets)
                self._send_json({
                    "ok": bool(data), "data": data, "errors": errors or None,
                    "meta": {
                        "count": len(data),
                        "markets": markets or [m[1] for m in SECTOR_MARKETS],
                        # 단위는 화면이 되묻지 않게 응답에 적어 보낸다
                        "volumeUnit": "천주", "valueUnit": "백만원",
                        "cacheTtl": SECTOR_TTL,
                    },
                })
                return

            if route == "movers":
                direction = (qs.get("dir") or ["up"])[0].strip().lower()
                if direction not in ("up", "down"):
                    self._send_json({"ok": False, "error": "dir 은 up 또는 down 이어야 합니다."}, 400)
                    return
                market = (qs.get("market") or ["all"])[0].strip().upper()
                market = "all" if market in ("", "ALL") else market
                try:
                    limit = int((qs.get("limit") or [str(MOVERS_MAX)])[0])
                except ValueError:
                    limit = MOVERS_MAX
                rows = fetch_movers(cfg, direction, market, limit)
                self._send_json({
                    "ok": True, "data": rows,
                    "meta": {"count": len(rows), "dir": direction, "market": market,
                             "max": MOVERS_MAX, "cacheTtl": MOVERS_TTL},
                })
                return

            if route == "investor-flow":
                market = (qs.get("market") or ["KOSPI"])[0].strip().upper()
                if market not in ("KOSPI", "KOSDAQ"):
                    self._send_json({"ok": False, "error": "market 은 KOSPI 또는 KOSDAQ 이어야 합니다."}, 400)
                    return
                try:
                    days = int((qs.get("days") or [str(INVESTOR_FLOW_DAYS)])[0])
                except ValueError:
                    days = INVESTOR_FLOW_DAYS
                rows = fetch_investor_flow(cfg, market, days)
                self._send_json({
                    "ok": bool(rows), "data": rows,
                    "meta": {"count": len(rows), "market": market, "days": days,
                             "order": "과거→최근",
                             "qtyUnit": "천주", "amtUnit": "백만원",
                             "cacheTtl": INVESTOR_FLOW_TTL},
                })
                return

            if route == "investor-top":
                direction = (qs.get("dir") or ["buy"])[0].strip().lower()
                if direction not in ("buy", "sell"):
                    self._send_json({"ok": False, "error": "dir 은 buy 또는 sell 이어야 합니다."}, 400)
                    return
                by = (qs.get("by") or ["qty"])[0].strip().lower()
                if by not in ("qty", "amt"):
                    self._send_json({"ok": False, "error": "by 는 qty 또는 amt 여야 합니다."}, 400)
                    return
                market = (qs.get("market") or ["all"])[0].strip().upper()
                market = "all" if market in ("", "ALL") else market
                try:
                    limit = int((qs.get("limit") or ["10"])[0])
                except ValueError:
                    limit = 10
                data, errors = fetch_investor_top(cfg, direction, market, by, limit)
                self._send_json({
                    "ok": bool(data), "data": data, "errors": errors or None,
                    "meta": {
                        "dir": direction, "by": by, "market": market,
                        "qtyUnit": "주", "amtUnit": "백만원",
                        # 확정치가 아니다. 화면에 그대로 적어 주어야 한다
                        "provisional": True,
                        "note": "증권사 집계 가집계치 — 외국인 09:30·11:20·13:20·14:30, "
                                "기관 10:00·11:20·13:20·14:30 에 갱신 (±10분)",
                        "cacheTtl": INVESTOR_TOP_TTL,
                    },
                })
                return

            # ── 지금 보고 있는 그 종목 (2026-09-18 지시) ──
            # 위 investor-top 과 다르다. 그쪽은 「상위 목록」이고 가집계이며,
            # 이쪽은 「이 종목」이고 확정치다.
            if route == "investor":
                code = (qs.get("code") or [""])[0].strip()
                if not (code.isdigit() and len(code) == 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                data = fetch_investor(cfg, code)
                self._send_json({
                    "ok": bool(data), "data": data,
                    "meta": {
                        "code": code, "count": len(data), "days": INVESTOR_DAYS,
                        "qtyUnit": "주", "amtUnit": "백만원",
                        # 종목별은 확정치다 (docs/kis-sector-investor.md).
                        # 상위 목록(investor-top)만 가집계라 거기만 그렇게 적는다.
                        "provisional": False,
                    },
                })
                return

            # 종목별 장중 추정가집계 (2026-09-22 지시)
            if route == "investor-estimate":
                code = (qs.get("code") or [""])[0].strip()
                if not (code.isdigit() and len(code) == 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                data = fetch_investor_estimate(cfg, code)
                self._send_json({
                    "ok": bool(data and data.get("latest")), "data": data,
                    "meta": {
                        "code": code, "qtyUnit": "주",
                        # **확정치가 아니다. 화면에 그대로 적어야 한다**
                        "provisional": True,
                        "person": False,     # 개인은 이 응답에 없다
                        "note": "장중 추정가집계 — 증권사 집계치. 마감 뒤 확정치와 다르다. "
                                "입력 외국인 09:30·11:20·13:20·14:30 / "
                                "기관 10:00·11:20·13:20·14:30 (±10분)",
                        "cacheTtl": INVESTOR_EST_TTL,
                    },
                })
                return

            # 최근 체결 30줄 (2026-09-21 지시 — A 종목 화면)
            if route == "ticks":
                code = (qs.get("code") or [""])[0].strip()
                if not (code.isdigit() and len(code) == 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                data = fetch_ticks(cfg, code)
                self._send_json({
                    "ok": True, "data": data["rows"],
                    "meta": {"code": code, "count": len(data["rows"]),
                             # 체결강도. 100 이 기준이고 넘으면 산 쪽이 세다
                             "power": data["power"],
                             "market": quote_market_div()},
                })
                return

            if route == "asking":
                code = (qs.get("code") or [""])[0].strip()
                if not (code.isdigit() and len(code) == 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                data = fetch_asking(cfg, code)
                self._send_json({
                    "ok": True, "data": data,
                    "meta": {
                        "code": code, "levels": ASKING_LEVELS, "qtyUnit": "주",
                        # 체결된 것이 아니라 **대기 중인 주문**이다.
                        # 장이 끝나면 의미가 옅어진다 — 화면에 적어야 한다.
                        "resting": True,
                    },
                })
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

def apply_slow():
    """확인용 서버로 바꾼다 — 캐시 수명을 전부 길게 잡는다.

    **상수를 갈아 끼우는 방식이다.** 부르는 쪽을 고치지 않아도 되고,
    한 곳만 보면 무엇이 느려졌는지 알 수 있다.

    안 건드리는 것
      DEBUGGING_PROBE_TTL  8093 이 살아 있나 보는 것이라 KIS 와 무관하다
      INDEX_CHART_TTL      이미 600초라 300 보다 길다

    **FUTURES_TTL 을 한 번 빠뜨렸다** (2026-09-21, `홈페이지_정리` 가 찾음).
    「야간선물은 화면 한 줄뿐」 이라고 두었는데, 그 한 줄을 화면이 1초마다
    물어보고 캐시가 0.7초라 **느린 모드에서도 거의 매번 KIS 로 나갔다.**
    「값이 작다」 와 「자주 안 부른다」 는 다르다.
    """
    global SLOW
    global PRICE_CACHE_TTL, INDEX_TTL, INDEX_MINUTE_TTL, OVERSEAS_TTL
    global MULTI_CACHE_TTL, SECTOR_TTL, MOVERS_TTL, FUTURES_TTL
    global INVESTOR_TOP_TTL, INVESTOR_FLOW_TTL, INVESTOR_TTL, ASKING_TTL
    global INVESTOR_EST_TTL

    SLOW = True
    PRICE_CACHE_TTL = SLOW_TTL          # 25 → 300
    INDEX_TTL = SLOW_TTL                #  5 → 300
    INDEX_MINUTE_TTL = SLOW_TTL         # 30 → 300
    OVERSEAS_TTL = SLOW_TTL             # 60 → 300
    SECTOR_TTL = SLOW_TTL               # 60 → 300
    MOVERS_TTL = SLOW_TTL               # 30 → 300
    INVESTOR_TOP_TTL = SLOW_TTL         # 120 → 300
    INVESTOR_FLOW_TTL = max(INVESTOR_FLOW_TTL, SLOW_TTL)   # 이미 600 이라 그대로
    INVESTOR_TTL = SLOW_TTL             # 60 → 300
    INVESTOR_EST_TTL = SLOW_TTL         # 60 → 300
    ASKING_TTL = SLOW_SHORT_TTL         #  3 → 60. 호가는 원래 아주 짧다
    FUTURES_TTL = SLOW_SHORT_TTL        # 0.7 → 60. 화면이 1초마다 물어보는 자리다
    MULTI_CACHE_TTL = SLOW_SHORT_TTL    #  2 → 60. 순위표가 한 번에 훑는 자리다


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--slow", action="store_true",
                    help="확인용 서버로 띄운다 — 시세를 5분 쥐고, "
                         "미리받기·공시·뉴스수집을 돌리지 않는다")
    args = ap.parse_args()

    try:
        cfg = load_secrets()
    except RuntimeError as e:
        cfg = None
        print("  [경고] %s" % safe_message(e))

    if args.slow:
        apply_slow()

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

    # 확인용 서버에서는 셋 다 돌리지 않는다.
    #
    #   미리받기  KIS 를 가장 많이 부른다. 여기서 끄는 것이 --slow 의 핵심이다
    #   공시      OpenDART 하루 한도를 메인 서버와 나눠 쓰게 된다
    #   뉴스 수집  같은 market.db 에 서버 둘이 쓰고, **텔레그램이 두 번 간다**
    if SLOW:
        print("  느린 모드  : 시세 %d초 · 미리받기/공시/뉴스수집 **끔** (--slow)"
              % SLOW_TTL)
    elif start_prefill(cfg):
        print("  5분봉 준비 : 코스피 상위 %d종목을 뒤에서 미리 받습니다"
              % PREFILL_TOP)

    # 뉴스 쌓기 — **주말·밤에도 돈다.** 공시 폴러와 달리 DART 키가 없어도 돈다
    if not SLOW and news_store.start_collector():
        print("  뉴스 수집 : 사용 (%d분마다 · 주말 포함 · 텔레그램 %s)"
              % (news_store.COLLECT_INTERVAL // 60,
                 " · ".join("%02d:%02d" % t for t in news_store.DIGEST_SLOTS)))

    if SLOW:
        pass                 # 확인용 서버는 공시도 안 받는다 (위 주석 참고)
    elif dart.start_poller():
        print("  공시 수집 : 사용 (코스피 상위 %d종목 · %d분마다)"
              % (dart.UNIVERSE_SIZE, dart.POLL_INTERVAL // 60))
        # **`NOTIFY_LOCAL` 을 함께 본다** (2026-09-22).
        #
        # 전에는 열쇠(`secrets.json`)만 보고 「텔레그램 켜짐」 으로 찍었다.
        # `NOTIFY_LOCAL = False` 로 **공시 발송을 꺼 둔 날에도 「켜짐」** 이라,
        # 텔레그램이 두 번 오는 일을 볼 때 **로그가 로컬을 범인으로 가리켰다.**
        # 오늘 이 줄 때문에 여러 사람이 한 번씩 헛짚었다.
        if not dart.telegram_config():
            _al = "꺼짐 (secrets.json 의 telegram 없음)"
        elif not dart.NOTIFY_LOCAL:
            _al = "꺼짐 (NOTIFY_LOCAL=False — 공시 알림은 배포본 워커가 보냅니다)"
        else:
            _al = "텔레그램 켜짐 (관심종목 %d개)" % len(dart.WATCH_CODES)
        print("  알림      : %s" % _al)
    else:
        print("  공시 수집 : 꺼짐 (setup-dart.bat 으로 인증키를 넣어주세요)")

    # 데일리분석 — **아침 07:30 에 그날 것을 저장하고 문안을 보낸다**
    # (2026-09-22 지시 — 「데일리는 아침 7시반에 저장하고 그걸 요약한
    #  텔레그램용을 나한테 보내줘」 · 「항상 켜놓는 서버가 있을 거야」).
    #
    # **판단도 조립도 `daily.py` 에 있다.** 이 파일은 여러 세션이 함께 쓰므로
    # 부르는 줄만 둔다 — `signal_watch` 와 같은 꼴이다.
    #
    # `--slow` 는 안 돈다. 확인용 서버가 저장하면 **메인과 같은 파일을 두고
    # 다투고**, 폴더마다 `secrets.json` 이 따로라 발송도 안 된다.
    if not SLOW:
        daily.start_daily(
            # **`[0]` 을 빠뜨리지 않는다.** 이 둘은 `(목록, 오류)` 를 준다.
            # 안 벗기면 튜플이 그대로 넘어가 `daily` 가 `x.get()` 에서 죽고,
            # `once()` 의 `except` 가 그것을 삼켜 **아무 일도 안 일어난다** —
            # 로그에는 「07:30 에 저장」 이 찍히는데 저장본이 안 생긴다.
            # 2026-09-22 에 그렇게 하루 종일 조용히 실패했다.
            #
            # **`fetch_indices_all`** — 화면이 보는 것과 같게 해외·환율까지 담는다.
            # `fetch_indices` 만 부르면 **국내 넷뿐**이고 해외 줄이 통째로 빈다.
            get_indices=lambda: fetch_indices_all(load_secrets(), with_chart=False)[0],
            get_sectors=lambda: fetch_sectors(load_secrets())[0],
            # **`rows` 다.** 화면이 받는 `/api/news/issues` 의 `data` 는 배열인데,
            # 그것을 만드는 `fetch_issues()` 는 `{rows, errors, topics}` 를 준다.
            # 처음에 `issues` 로 적었다가 실제로 불러 보고 잡았다 (2026-09-22).
            get_issues=lambda: (news.fetch_issues() or {}).get("rows") or [],
            # 발송은 공시와 같은 통로를 쓴다. **`NOTIFY_LOCAL` 과 무관하다** —
            # 그것은 공시만 막는다 (dart.py 주석 참고).
            #
            # ── **왜 포트로 가르나** ──
            #
            # ① `--slow` 로는 못 막는다. 2026-09-22 에 **8770 이 `--slow` 없이**
            #    떠 있었고, 그런 서버가 둘이면 **07:30 에 각각 보내** 폰에 두 번 간다.
            #
            # ② **`docstore` 로도 못 막는다.** `save_today()` 가 「오늘 것이 있으면
            #    안 쓴다」 로 막고 있는데, `DOC_ROOT` 가 `__file__` 기준이라
            #    **폴더마다 다른 파일을 본다** (8765 는 `KJCStudio\…`, 8770 은
            #    `kjc-dev3\…`). 둘 다 「오늘 것이 없다」 로 읽는다.
            #    **같은 폴더 안 중복만 그것이 막는다.**
            #
            # ③ **저장은 모든 폴더에서 한다.** 그 폴더 화면이 읽어야 한다.
            #    **발송만** 가른다.
            #
            # ④ `MAIN_PORT` 는 `frame.js` 의 같은 이름과 **같은 값**이다 (위 주석).
            send=(dart.telegram_send
                  if (dart.telegram_config() and args.port == MAIN_PORT)
                  else None),
        )
        _tg = ("텔레그램 켜짐" if (dart.telegram_config() and args.port == MAIN_PORT)
               else ("저장만 — 메인(%d)에서만 보냅니다" % MAIN_PORT
                     if dart.telegram_config() else "저장만 — 열쇠 없음"))
        print("  데일리분석 : 아침 %02d:%02d 에 저장 · 최근 %d장 (%s)"
              % (daily.SEND_AT // 60, daily.SEND_AT % 60, daily.KEEP, _tg))

    # 볼린저·MACD·RSI 가 동시에 맞는 자리를 본다 (2026-09-22 지시).
    # **KIS 를 새로 안 부른다** — 미리받기가 쌓아 둔 5분봉을 읽기만 한다.
    # 확인용 서버(SLOW)는 안 돈다. 같은 알림이 폴더 수만큼 갈 이유가 없다.
    if not SLOW and signal_watch.start(sys.modules[__name__]):
        print("  신호 감시 : 사용 (관심종목 %d개 · %d초마다 · 장중만%s)"
              % (len(signal_watch.WATCH), signal_watch.LOOP_SEC,
                 "" if signal_watch.SEND else " · **발송 꺼짐**"))

    print("  종료      : Ctrl+C")
    print("-" * 52)
    sys.stdout.flush()

    # ── IPv4 와 IPv6 를 **둘 다** 연다 (2026-09-18) ──
    #
    # `127.0.0.1` 에만 열려 있었다. 그런데 브라우저와 문서는 `localhost` 를 쓰고,
    # 윈도우는 그 이름을 **IPv6(::1) 로 먼저** 푼다. 거기 아무도 없으니 실패한
    # 뒤에야 IPv4 로 넘어가는데, **그 재시도에 2초가 걸린다.**
    #
    #     127.0.0.1   0.00 ~ 0.04초
    #     localhost   2.03초          ← 요청 하나하나에 붙는다
    #
    # CSS 한 장에도 붙는다. 화면이 여는 요청이 수십 개이므로 **첫 화면이
    # 통째로 느려진다.** 오늘 잰 지수 시간에도 이 2초가 섞여 있었다.
    #
    # `::1` 하나에 V6ONLY 를 꺼서 묶는 방법은 **안 된다** — IPv6 루프백에만
    # 묶여서 `127.0.0.1` 이 거절된다(실측). 루프백 둘은 서로 다른 주소라
    # 소켓을 따로 열어야 한다. `::`(모든 인터페이스)로 열면 한 번에 되지만
    # 밖에서도 들어올 수 있게 되므로 쓰지 않는다 — 이 서버는 KIS 키를 들고 있다.
    class _V6Server(ThreadingHTTPServer):
        address_family = socket.AF_INET6

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    srv6 = None
    try:
        srv6 = _V6Server(("::1", args.port), Handler)
        threading.Thread(target=srv6.serve_forever, daemon=True,
                         name="http-v6").start()
    except OSError as e:
        # IPv6 가 꺼져 있는 PC 도 있다. 그래도 IPv4 로는 돌아야 한다.
        print("  참고      : IPv6(::1) 은 못 열었습니다 — %s" % safe_message(e))
        print("              localhost 로 열면 요청마다 2초쯤 늦습니다.")
        print("              127.0.0.1 로 여시면 그 지연이 없습니다.")
        sys.stdout.flush()

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  서버를 종료했습니다.")
        srv.server_close()
        if srv6:
            srv6.server_close()


if __name__ == "__main__":
    main()
