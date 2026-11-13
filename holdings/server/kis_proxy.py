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
import collections
import json
import os
import shutil
import sqlite3
import struct
import sys
import threading
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import http.client
import hashlib
import gzip
from datetime import datetime, timedelta, timezone

# 파일을 안전하게 쓴다 — 쓰다 죽어도 옛 내용이 남는다 (2026-09-22)
from docstore import write_json_atomic
import docstore
import edit_key         # 수정 비밀번호 — 정해 둔 보드 문서는 재권님만 고친다(2026-11-11)
import marketdb
import re
import signal_watch
import heartbeat
import daily
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# 같은 폴더(server/)의 모듈들. 스크립트로 실행하므로 바로 잡힌다.
import dart
import dart_gov      # 지배구조 — 상장사마다 최대주주 · 타법인 출자(2026-11-05 · server/dart_gov.py 머리 주석)
import company_profile
import us_universe
import kis_ws
import us_sectors
import naver
import naver_period
import toss
import macro
import note_alert      # 시황 글 알림 — 자동 시황 글이 새로 써지면 텔레그램 한 통(2026-10-27 · server/note_alert.py)
import events          # 실적 · FOMC · 미국 지표 결과 알림(2026-10-25 · server/events.py 머리 주석)
import tglog           # 오늘 보낸 텔레그램 글(2026-10-26 · server/tglog.py) — /api/telegram/today
import claude_chat     # 홀딩스 오른쪽 Claude 창 — 맥미니 claude 를 한 번씩 부른다 · POST /api/claude/ask(2026-11-03 · server/claude_chat.py)
import theme_flow      # 실시간 순위 「테마」 — 큰 테마 · 작은 테마 · 수급(넥스트 5분 거래량 2배) (2026-10-27 · server/theme_flow.py)
import good_news       # 「좋은 뉴스」 판정 — 공시마다 갈래 · 방향 · 크기 · 자사주 목적 · 이미 오름 · /api/good-news(2026-11-05 · server/good_news.py)
import vwap            # VWAP(거래량 가중 평균가) — 국내 분봉에 장마다(장 전 · 정규장 · 장 후) 누적 값 `vwap` 을 붙인다(2026-11-06 · 11-07 구간 바꿈 · server/vwap.py)
import fear_greed      # 공포·탐욕 지수 — 코스피 · 삼성전자 · SK하이닉스 · /api/market/fear-greed(2026-11-06 · server/fear_greed.py)
import auto_watch      # 자동 관심종목 — 코스피 시총 200 · 코스닥 150 중 전일 거래량 급등 · 투자전략 룰로 거르고 줄 세움 · /api/auto-watch(2026-11-05 · server/auto_watch.py)
import nxt_board       # 넥스트레이드 장외 보드 — 15:41 종가 · 20:01 장외 · 06:01 야간선물 저장 · /api/nxt/board(2026-10-26 · server/nxt_board.py)
import heatmap         # 첫 화면 시장 지도 — 칸 넓이 = 시가총액 · 색 = 등락률 · /api/kis/heatmap(2026-10-27 · server/heatmap.py)
import flow_board       # 수급 정리판 — 투자자 갈래별 순매수(오늘 · 날마다 · 상위 종목)를 한 주소로 · /api/kis/flow-board(2026-11-04 · server/flow_board.py)
import open_rise        # 초반상승 — 정규장 첫 5분봉이 시가보다 오른 종목 · 실시간 순위 「초반상승」 칩 · /api/kis/open-rise(2026-11-11 · server/open_rise.py)
import rescan           # 지금검색 — 관심 아래 칩 룰을 누를 때 다시 셈 · /api/kis/rescan(2026-11-11 · server/rescan.py)
import pre_flow         # 프리장 프로그램 몰리는 종목 — 실시간 순위 「프리장」 칩 · /api/kis/pre-flow(2026-11-05 · server/pre_flow.py)
import flow_rank        # 투자자 매매 동향 — 외국인 · 기관 순매수 순위(가집계) · 「특이 매수」 전일 순매도 → 오늘 순매수 · /api/kis/flow-rank(2026-11-06 · server/flow_rank.py)
import day_top_fill     # 등락 상위 — 지난 거래일 판을 다시 세어 채움(장 쉬는 때 · 쓰는 서버만 · 2026-11-11 · server/day_top_fill.py)
import day_top          # 등락 상위와 걸린 필터 — 날마다 장 뒤 한 번 쌓음 · /api/kis/day-top(2026-11-11 · server/day_top.py)
import dt30             # 단타 30 판 — 평일 09:06 단타 상위 30 굳힘 · 30분마다 값 · 30거래일 · /api/kis/dt30(2026-11-11 · server/dt30.py)
import watch_log        # 종목 기록 — 관심 · 자동 · VI · 급등 · 매수 종목을 날마다 쌓음 · /api/watch-log(2026-11-06 · server/watch_log.py)
import session_volume   # 시간대별 거래량 · 전일비 — 프리장 · 정규장 · 애프터 끝에 순위 종목 누적 거래량 저장 · /api/kis/vol-ratio(2026-11-05 · server/session_volume.py)
import intraday_flow    # 당일 수급 — 장중 1분마다 시장 투자자 · 프로그램 매매를 쌓아 5분 구간으로 · /api/kis/flow-today(2026-10-27 · server/intraday_flow.py)
import nxt_pre         # 넥스트레이드 장 전 거래량 2배 목록 — 08:51 한 통(2026-10-26 · server/nxt_pre.py 머리 주석)
import short_sale  # 공매도 — 감시 대상 종목마다 일별 공매도를 쌓아 「공매도」 칩에 냄(2026-11-06 · server/short_sale.py 머리 주석)
import intraday_alerts  # 장중 알림 — 상승 VI · +20% 급등(2026-10-26 · server/intraday_alerts.py 머리 주석)
import market_hours     # 장 시각 한 곳 — 평소 시각 + 그날 값(KIS 휴장일 · 바뀐 시각 표 · 거래소 공시)(2026-11-07 · server/market_hours.py 머리 주석) · /api/alerts/market-hours
import market_event     # 시장 전체 사건 — 서킷브레이커 추정 · 거래소 공시 확인(2026-11-07 · server/market_event.py 머리 주석) · /api/alerts/market-event
import market_index
import us_outlook  # 미국장 예측용 값 — 지수 선물 · SPX 옵션 · 지표 예상치 · FOMC 기대 · VIX 이력(2026-10-27 · server/us_outlook.py 머리 주석)
import crypto            # 가상자산 — 업비트 공개 시세(2026-10-14 · server/crypto.py 머리 주석)
import news
import news_store
# 오류 문구에서 비밀을 지운다. 외부 호출 오류를 사람에게 보여줄 때는
# 반드시 이것을 거친다 (2026-09-14 에 인증키가 실제로 샜다).
from secrets_guard import safe_message, scrub, secrets_path

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

# ── 정적 파일로 내줄 것 · 내주지 않을 것 (2026-09-29 지시) ──────
#
# 재권님 말씀 — 「**로컬 서버 저장소 전체를 내주는것 막아**」.
#
# **그 전에는 `SITE_ROOT`(저장소 루트) 전체가 열려 있었다.** `/api/*` 와
# `/debugging/` 만 가로채고 나머지는 `SimpleHTTPRequestHandler` 로 넘겼다.
# 키 파일 · 토큰 캐시 · `market.db` · 데일리 저장본이 **전부 200** 이었다.
#
# **지금은 `127.0.0.1` 에만 떠 있어 밖에서 못 붙는다.** 그래서 「깨진 것」 이
# 아니었지만, **터널을 열면 그 순간 나간다.** 터널보다 먼저 막는다.
#
# ⚠️ **순서가 핵심이다 — 먼저 막고, 그 뒤 낸다.**
# 키 파일이 `secrets.json`·`.kis-token-cache.json` 으로 **둘 다 `.json`** 이라,
# 확장자 검사를 먼저 하면 **그것을 통과한다.**
#
# **막을 목록은 새로 정하지 않았다 — `.gitignore` 가 근거다.**
#
#     secrets.json*              holdings/.gitignore:39
#     .kis-token-cache.json      :44      ← `.json` 이라 이름으로만 막힌다
#     market.db · -journal       :51
#     data/docs/*                :56      ← 데일리 저장본. 텔레그램 문안이 들어 있다
#     .env · *.key · __pycache__
#     .claude/*                  루트 .gitignore
#     **`.git` 자체**             **gitignore 에 없다** — git 이 자기를 안 가린다
_DENY_DIRS = {".git", "__pycache__", ".claude", "logs", "node_modules",
              ".pytest_cache", ".venv", "venv"}
_DENY_NAMES = {".env", ".kis-token-cache.json", ".kis-token-cache-2.json", ".DS_Store"}
_DENY_PREFIX = ("secrets.json",)          # secrets.json · secrets.jsonbak · …
_DENY_SUFFIX = (".key", ".pem", ".db", ".db-journal", ".db-wal", ".db-shm",
                ".log", ".err", ".pyc", ".pyo", ".bak")
_DENY_REL = ("holdings/data/docs/",)      # 저장본. README.md 는 .md 라 어차피 안 나간다

# **낼 확장자 — 네 방법으로 세어 정했다** (2026-09-29).
#
#     로그(실제 요청)     못 쟀다 — 재시작 뒤 5분치라 표본이 API 폴링뿐
#     HTML·JS·CSS 링크   .js · .css · .html · .json
#     실제 파일           같은 넷. **이미지가 0건** — 세 폴더가 비어 있다
#     **코드의 동적 조립**  **`.png` 이 여기서 나왔다** —
#                       `stock-icon.js` 가 `/uidata/icons/<종목코드>.png` 를 만든다
#
# **앞의 세 방법이 다 `.png` 를 놓쳤다.** 아이콘이 gitignore 라 파일이 아직
# 없어서 안 보였다. **그대로 넣었으면 내려받는 날 아이콘이 전부 깨졌다.**
# `.jpg`·`.webp` 는 `CLAUDE.md` 의 권장 포맷이라 작업물이 들어오면 필요하다.
#
# ⚠️ **승인된 값은 열하나다. 여기서 조용히 늘리지 않는다** (2026-09-29).
#
# **내가 열하나로 올려 재권님 승인을 받고, 코드를 쓸 때 여섯을 말없이 더했다** —
# `.gif` `.htm` `.map` `.mjs` `.ttf` `.woff`. **여섯 다 저장소에 0개**였다.
# 「비슷하니 함께」 로 **재보지 않고** 넣었다. 그날 전수검사에서 **내가 직접 센
# 확장자 목록에 그 여섯이 하나도 없었는데도** 그랬다.
#
# **`.map` 만 성격이 달랐다** — 소스맵이라 빌드 도구를 쓰기 시작하면 **원본
# 코드가 나간다.** 지금 0개라 무해하고 **미래에 새는 자리**였다.
#
# **더 큰 문제는 기록이 거짓이 되는 것이었다** (`개념정의` 지적) —
# 다음에 누가 보면 **「열일곱이 승인된 값」 으로 읽는다.**
#
# **막는 것이 늘어난 것은 밝혔고 내는 것이 늘어난 것은 안 밝혔다.**
# 앞의 둘(`do_HEAD` · 목록 차단)은 「목록에 없던 것」 이라 발견으로 여겼고,
# 확장자는 「비슷해서 함께」 로 여겨 발견이 아니라고 봤다. **그 판단이 틀렸다** —
# 승인된 목록을 바꾼 것은 **어느 방향이든** 밝힌다. **내는 쪽이 더 위험하다.**
#
# **늘릴 일이 생기면 그때 승인을 받는다.**
_ALLOW_EXT = {".html", ".css", ".js", ".json",
              ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".woff2",
              ".pbf"}   # 2026-10-06 — 지구본 글꼴(company-setup/vendor/basemaps-assets/fonts). 바깥 CDN 대신 우리 서버가 낸다(로딩 개선)

SECRETS_PATH = secrets_path()        # 자리 셈은 secrets_guard 하나 — 한 벌(~/.kjc) · 옛 자리 폴백

# `/maps/` 로 내주는 **저장소 밖** 자리 (2026-10-02 지시).
#
# Insight 의 「AI 생태계 지도」 가 Protomaps PMTiles 를 쓰는데 다섯 조각 1.5GB 라
# 저장소에 담을 수 없다. 브라우저는 그 파일을 **Range 로 조각만** 읽으므로
# 정적 파일 내주기가 206 을 돌려줘야 한다(`_send_file_ranged`).
#
# ⚠️ **절대 경로다.** 8764(서비스방)는 자기 폴더(`/Users/kjc/service`)를 내주지만
# 지도는 그 폴더가 아니라 **이 한 곳**을 가리킨다 — 외부접속에서도 같은 파일을
# 봐야 하고, 1.5GB 를 폴더마다 복제할 수 없다.
#
# 경로를 박지 않는다 — `KJC_MAPS_DIR` 로 덮을 수 있다 (`marketdb` 의
# `KJC_DB_PATH` 와 같은 모양). 기본값은 지금 파일이 있는 자리다.
MAPS_URL = "/maps/"
MAPS_DIR = (os.environ.get("KJC_MAPS_DIR") or "").strip() \
    or "/Users/kjc/data/maps"

# **그 폴더의 모든 것을 내주지 않는다** (2026-10-02 · 홈페이지_정리 지적).
# 같은 자리에 변환 로그(`log-*.txt`)와 **`pmtiles` 실행 파일**이 함께 있는데,
# 확장자를 안 가리면 그것까지 나간다 — 고치기 전 실측으로 둘 다 206 이었다.
#
# **「무엇이 아닌지」 가 아니라 「무엇인지」 로 적는다.** 막을 것을 세면 파일이
# 하나 늘 때마다 「이건 예외인가」 를 따지게 되고, 안 따지면 저절로 나간다.
# 지도 조각이 늘어도 확장자는 그대로이므로 이 목록은 안 낡는다.
MAPS_EXTS = (".pmtiles",)
TOKEN_CACHE_PATH = os.path.join(HOLDINGS_DIR, ".kis-token-cache.json")
# **둘째 앱키의 토큰** (2026-10-06 · 아래 「앱키 둘」). 키마다 토큰이 따로다.
TOKEN_CACHE_PATH2 = os.path.join(HOLDINGS_DIR, ".kis-token-cache-2.json")

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
# 차트는 통합으로 **먼저** 묻는다. 과거 봉이라 "지금 몇 시인가"를 따질 일이 없다.
#
# ⚠️ **통합이 과거를 더 준다는 뜻이 아니다** (2026-10-02 실측으로 뒤집혔다).
# 넥스트레이드에 늦게 편입된 종목은 **통합으로 물으면 편입 뒤만 온다.**
#
#     005935 삼성전자우   주 UN=3   J=100  ·  월 UN=2  J=100  ·  년 UN=1  J=23
#     069500 KODEX 200   주 UN=3   J=100                        (ETF 도 같다)
#     005930 삼성전자     주 UN=100 J=100                        (편입이 오래돼 같다)
#
# 수정주가(`FID_ORG_ADJ_PRC`)는 무관했고, 잘리는 경계는 20260914 였다
# (**편입 시점으로 보이지만 그것까지는 안 쟀다 — 추정이다**).
#
# 전에 이 자리 주석이 「통합으로 고정한다」 였는데, 그 근거가 「시각을 따질
# 일이 없다」 였다. **시각 문제가 아니라 통합이 과거를 덜 주는 문제였다.**
# 그래서 고정하지 않고 **적게 오면 KRX 로 한 번 더 받는다**
# (`fetch_bars_from_kis`). 분봉이 이미 같은 모양을 쓴다 — 「전부 0」 이던
# 폴백을 「1개 이하」 로 고친 자리(2026-10-01)와 한 계열이다.
MARKET_DIV_CHART = "UN"

# 통합이 과거를 잘라 줄 때 되묻는 쪽.
MARKET_DIV_CHART_ALT = "J"

# **일 · 주 · 월 · 년봉은 통합(UN)으로 받는다 — 토스 일봉과 같은 모양** (2026-10-15 20:1x 재권님 「통합으로 해야겠다」 ·
# 「응 통합으로 해줘」 — 아침 7시 뒤 마지막 봉 종가도 통합 종가).
# 같은 날 낮에는 정규장(J)으로 바꿨었다(재권님 「오늘 시가에 맞춰야지」 — 일봉 시가 225,000 ↔ 시세 시가 216,500 이 갈림).
# 저녁에 세 곳을 견주니(삼성 10-08~10-15) 토스 일봉은 시 · 고 · 저 · 종 전부 통합(10-15 시가 225,000 · 10-14 종가 234,500),
# 네이버는 시가 정규장 · 종가 통합, 우리는 전부 정규장이라 다른 앱과 몸통이 달라 보였다 — 셋 다 등락은 정규장 종가(232,000) 기준.
# **봉은 통합 · 위쪽 시세 · 등락은 정규장** 이 토스와 같은 모양이다. 5분봉은 처음부터 통합이다.
# 과거가 잘려 오면(넥스트레이드 늦게 편입된 종목) 아래 ALT(정규장)로 한 번 더 묻는다.
MARKET_DIV_BARS = "UN"
MARKET_DIV_BARS_ALT = "J"

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
# 둘째 키 몫 — 발급 간격(1분 1회)도 자물쇠도 **키마다 따로**다 (2026-10-06).
_token_lock2 = threading.Lock()
_last_token_attempt2 = 0.0

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
# (여기 · 그때의 워커 · frame.js 의 PRIORITY_CODES)이었는데 한꺼번에 사라졌다.
PRICE_CACHE_TTL = 25                # 모든 종목 · 지수. **화면이 이 값을 받아 그 주기로 돈다** (2026-10-02 · 재권님 「나」 — 서버 값이 기준이고 화면이 따라간다)

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
    """캐시 수명. **모든 종목이 같다** (2026-09-18 지시). 위 주석 참고.
    예산이 남으면 서버가 당긴다 — `fill_factor` (2026-10-15)."""
    return max(PRICE_TTL_FLOOR, round(PRICE_CACHE_TTL * fill_factor(), 1))


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
# 지금 쓰는 양은 실제 한도의 25% 수준이다. 자세한 내용은 docs/data-sources.md 참고.
#
#   KIS_LIMIT_PER_SEC : 계정에 허용된다고 보는 한도 (기준값)
#   BUDGET_RATIO      : 그중 실제로 쓸 비율. 0.5 = 한도의 50%
#
# 두 번 올렸다.
#
#     2026-09-14   0.1 → 0.5   초당 1 → 5건
#     2026-09-23   0.5 → 1.0 → **0.5 로 되돌림**
#
# **두 번째는 같은 날 되돌렸다** (재권님 지시 — 「속도는 우선 되돌리고
# 정확히 확인한후에 정리한다」). **값이 나쁜 것이 아니라 아직 안 쟀다.**
#
#     실제 한도                **20 TPS**
#     서버 하나가 초당 10건이면
#     `--slow` 아닌 서버 **셋**이 동시에 첫 화면을 열면   **30건** → **넘는다**
#
# **8765·8767·8770 이 `--slow` 없이 돈다.** 8767 은 KIS 누적 1,009건으로
# 가장 활발하고(검수하며 화면을 연다), **8765 와 겹치면 20 — 정확히 한도**다.
# 초당 5건이던 때는 셋이어도 15 라 여유가 있었다.
#
# **안 잰 것** — **「같은 순간에 몇 건인가」.** 로그에 시각이 안 찍혀
# (`kis_proxy.py:2315`) 누적 건수만 세어진다. 위 20·30 은 **최대치 계산**이다.
#
# 첫 번째는 순위표를 15종목으로 늘리니 첫 조회에 28.8초가 걸려서였다(실측).
# **한국투자증권 제한이 아니라 이 값 때문이었다.**
#
# 두 번째도 같은 자리다. 2026-09-23 실측 — 첫 화면에서 KIS 를 **28건** 부르는데
# `_rate_limit()` 이 **0.2초씩 차례를 배정**해서 **마지막 호출이 5.6초에
# 시작**했다. 마지막 API 가 끝난 것이 **11.5초**였다. **KIS 가 느린 것이
# 아니라 우리가 줄을 세운 것**이다.
#
# 기준값 10 은 그대로다 — **실제 한도(20)의 절반**이라 아직 여유가 있다.
#
# **2026-10-15 에 20 으로 올렸다** (재권님 「키 하나당 20건으로 늘려」 · 「kis 만 늘려야해」 ·
# 안 「응 해줘」). KIS 공식 한도와 같은 값이라 여유가 0 이다 — 넘으면 아래 ㉡ 이 간격을
# 늘렸다가 60초 뒤 돌아오고, `stats` 의 `overruns60s` · `overrunsTotal` 이 센다. 넘는 일이
# 잦으면 이 값을 내린다. 그 전 장중 사용은 한도(키당 10)의 10~14% 였다(10-15 작업우선순위 실측).
#
# (2026-10-06 에 배포본 워커를 지웠다 — 그 전에는 워커가 따로 초당 5건을
# 써서 「여기 10 + 워커 5」 였다. 이제 KIS 를 부르는 것은 8765 하나다.)
#
# ⚠️ **같은 숫자 0.1 이 공유 줄 전후로 뜻이 반대다** (2026-09-23).
#
#     공유 줄 **전**   각자 0.1초  →  여섯이면 **초당 60건**   ⚠️ 한도 세 배
#     공유 줄 **후**   합쳐서 0.1초  →  **초당 10건**          ✓
#
# **그 탓에 한 번 맞췄다가 되돌렸다.** 낮에 「로컬 0.1 ↔ 워커 0.2 가
# 갈렸다」 로 올려 재권님이 **(가) 둘 다 0.2** 를 고르셨는데, 그 0.1 은
# **「안 되돌린 값」 이 아니라 공유 줄이 합계로 바꿔 놓은 값**이었다.
# 재권님이 아침에 **「10으로 해줘」** 로 정하신 그 10이다.
# **전제가 틀린 채 고르신 것**이라 **「되돌려」** 로 물리셨다.
#
#     세 길      (가) 둘 다 0.2 · (나) 둘 다 0.1 · (다) 그대로
#     고르신 것  (가) `24118ac`  →  **전제가 틀려 되돌림**  →  **(다) 그대로**
#
# **세 자리가 다 못 봤다** — 나른 쪽 · 검수한 쪽 · 실행한 쪽.
# `987d16d`(공유 줄)가 **제목에 없는 값**을 함께 바꿔서, 검수는
# 「여섯이 줄 서는 것」 만 보고 `BUDGET_RATIO` 가 1.0 이 된 것을 안 봤다.
# **제목이 안 말한 것은 아무도 안 본다.**
#
# 이 두 값만 바꾸면 호출량 전체가 조절된다.
KIS_LIMIT_PER_SEC = 20.0
BUDGET_RATIO = 1.0                                  # 기준값을 다 쓴다
# ⚠️ **이 값은 서버 하나가 아니라 여섯이 합쳐서 쓰는 몫이다** (2026-09-23).
# 아래 공유 줄이 여섯을 한 줄에 세우므로, 고정으로 나눌 때처럼
# 「각자 N건 × 여섯」 이 되지 않는다.
#
# **앱키 하나당 값이다** (2026-10-06 · 아래 「앱키 둘」). `kis2` 가 있으면
# 키마다 이만큼이라 **합은 키 수 × 이 값**(둘이면 20)이다.
KIS_CALLS_PER_SEC = KIS_LIMIT_PER_SEC * BUDGET_RATIO   # = 앱키 하나당 초당 20건
KIS_MIN_INTERVAL = 1.0 / KIS_CALLS_PER_SEC             # = 0.05초 간격

# 동시에 진행할 호출 수. 초당 건수와는 별개다 — 간격은 _rate_limit() 이 지키고,
# 이 값은 응답을 기다리는 시간을 몇 개까지 겹칠지를 정한다.
KIS_MAX_PARALLEL = 8

_rate_lock = threading.Lock()
# **벽시계 기준이다** (2026-09-23). 공유 줄과 같은 눈금을 써야
# 물러섰다 돌아올 때 이어진다.
_last_call_at = 0.0
_call_times = []                 # 최근 호출 시각 (사용량 측정용)

# ── 나가는 문 — 「어느 1초든 한도를 안 넘는다」 (2026-10-03 지시) ──────────
#
# 재권님 「1초에 10회 한도 걸어놔」. 위 줄은 **간격**(0.1초)을 배정하는데,
# 배정 뒤 `sleep` 에서 **늦게 깬 차례가 앞 차례에 붙어** 나갔다 — 실제 간격
# 35~71ms · 로그 1초 창 최대 12건(2026-10-03 가름). 간격을 지켜도 **한 초에
# 몰리는 것**은 못 막는다.
#
# 그래서 **나가기 직전**에 한 번 더 센다 — 「지난 1초 안에 실제로 문을 지난 수」
# 가 한도면 가장 오래된 것이 1초를 벗어날 때까지 기다린다. **배정 시각이 아니라
# 지나간 시각**이라 늦게 깬 것도 여기서 걸린다. `monotonic` — 이 셈은 남과
# 나누지 않는다.
#
# ⚠️ **이 프로세스 안만 센다.** KIS 를 부르는 것은 8765 하나다(넘기기). 다른
# 서버가 상류를 못 써 **폴백으로 직접 부르는 동안**은 그 서버 몫이 따로라 합이
# 넘을 수 있다 — 공유 줄(`_shared_slot`)이 간격으로만 막는다.
_send_lock = threading.Lock()
_send_times = [collections.deque(), collections.deque()]     # 키마다 하나 — 항목은 [보낸 시각, 응답 온 시각 또는 None]
# **응답이 오기 전까지 자리를 잡고 있는다** (2026-10-27 재권님 「한도를 초과해서 가져오는걸 막아야지」 · 「대기했다가 가져와야지」).
# 전에는 「보낸 시각이 지난 1초 안인 수」 를 셌는데 KIS 는 **받은 시각**으로 센다 — 닿기까지 수십 ms 가 들쭉날쭉해
# 우리 셈으로 19~20 일 때 받는 쪽에서 몰려 거절됐다(10-27 8765 거절 8번 중 7번). 이제 **응답이 안 온 것 + 응답이
# 지난 1초 안에 온 것**을 센다 — KIS 가 받은 시각은 보낸 뒤 · 응답 전 사이라 어느 1초에도 한도를 넘겨 닿지 못한다.
# 한도(`KIS_CALLS_PER_SEC`)는 그대로다. 응답을 못 적은 채 남는 자리(예외 길)는 `SEND_GATE_STALE` 뒤 풀린다
SEND_GATE_STALE = 16.0           # 초 — urlopen 시간 한도(15)보다 조금 길게
_gate_tl = threading.local()     # 이 스레드가 마지막으로 잡은 자리 — kis_get 이 응답 뒤 적는다
_send_stat = {"held": 0, "heldMs": 0.0, "maxIn1s": 0,
              "perKey": [{"maxIn1s": 0, "sent": 0}, {"maxIn1s": 0, "sent": 0}]}

# ── 앱키 둘 — 한 줄에 서서 덜 쓴 키로 나간다 (2026-10-06 지시) ──────────────
#
# 재권님 「합쳐서 20이고 이거를 잘 분배해서 쓰는 방향으로 해줘」 → 「응 그게
# 좋을거같아」. `secrets.json` 에 `kis2` 칸이 있으면 **8765 가 두 키를 함께 쓴다.**
#
# **일마다 키를 정하지 않는다.** 줄은 하나이고, 나갈 차례가 오면 **지난 1초에
# 덜 쓴 키**로 나간다. 키마다 「어느 1초든 `KIS_CALLS_PER_SEC` 건」 을 넘지
# 않으므로 **합은 키 수 × 그 값**이다. 낮에 미리받기가 쉬면 화면이 다 쓰고,
# 밤에는 밤 바퀴가 다 쓴다 — 노는 몫이 없다. 화면이 먼저인 것은 미리받기가
# 비켜서는 기존 장치(`_ui_busy`)가 그대로 맡는다.
#
# 실측(2026-10-06 11:41~11:47 · 임시 도구 264건) — 둘째 혼자 12 · 9+9 · 10+10 ·
# 13+13 전부 거절 0. 계정 합쳐 20 이 아니다(앱키별이거나 계정 한도가 26 넘음).
#
# **둘째 키가 없거나 토큰을 못 받으면 첫째 하나로 돈다** — 지금과 같다.
# 못 받으면 `KEY2_DOWN_SEC` 동안 쉬었다 다시 본다.
#
# ⚠️ **8765 만 해당이다.** 다른 서버는 KIS 를 8765 로 넘긴다(`KJC_KIS_UPSTREAM`).
# 폴백으로 직접 부를 때도 자기 `secrets.json` 을 읽으므로, 그 폴더에 `kis2` 가
# 없으면 첫째 하나다.
KEY2_DOWN_SEC = 600
# 문을 지난 시각과 실제로 보내는 시각 사이가 몇 ms 벌어진다(토큰 · 요청 만들기 ·
# 스레드 깨기). 문에서만 세면 받는 쪽에서는 1초에 한 건 더 들어올 수 있어
# (가짜 시험 10 → 11) 1초 창을 이만큼 넉넉히 비운다 (2026-10-06).
SEND_GATE_PAD = 0.06
_key2_down_until = 0.0
_keys_active = 1           # 마지막으로 줄에 선 키 수 — `stats` 가 낸다

# ── 거절됐을 때 앞뒤를 남긴다 (2026-10-03 · 재권님 「가」) ──────────────
#
# 밤 바퀴에서 `EGW00201` 이 2번 났는데 **우리 1초 창은 8 · 7** 이었다. 우리가
# 보낸 시각으로는 한도 안이라, **KIS 가 받은 시각**이 몰렸는지 봐야 한다.
# 매 호출이 새 연결(`urlopen`)이라 연결 맺는 시간만큼 도착이 밀릴 수 있다.
#
# 평소에는 아무것도 안 찍는다 — 최근 호출 몇십 개의 [보낸 시각 · 왕복 ms ·
# 결과] 를 고리에만 쥐고, **거절이 나면 그 앞 3초를 한꺼번에 찍는다.**
# 왕복이 긴 것이 거절 직전에 몰려 있으면 도착 몰림이다.
SEND_RING_MAX = 60
SEND_RING_DUMP_SEC = 3.0
_send_ring = collections.deque(maxlen=SEND_RING_MAX)

# **실제로 뜬 포트.** `MAIN_PORT`(8765)는 「어느 것이 메인인가」 를 가리는
# 상수라 다르다. 여섯이 동시에 도므로 **로그 줄마다 이것을 적는다** —
# 파일이 갈려 있어도 합쳐 볼 때 어느 서버 것인지 알 수 있다.
RUN_PORT = None

# ── 여섯 서버가 한 줄에 선다 (2026-09-23 지시) ──────────────────
#
# 재권님 말씀 — 「일꾼별로 1씩 주는게 아니고 … 유동적으로 변환이 되야
# 낭비가 없을거같은데」 · 「응 해줘, 한도를 넘기지 않게 안전장치도 필요해」.
#
# **전에는 서버마다 자기 변수만 봤다.** 여섯이 각자 「나는 초당 N건」 을
# 지켰고 **합치면 넘는데 아무도 몰랐다.** 동시에 **안 쓰는 서버가 제 몫을
# 잡고 있어** 쓰는 쪽은 모자랐다 (실측 — 8770 은 0건, 8767 은 1,009건).
#
# 파일 하나를 함께 보면 **안 쓰는 쪽은 저절로 0 을 쓰고 쓰는 쪽이 다
# 가져간다.** 몫을 정할 필요가 없다 — **먼저 온 쪽이 먼저 간다.**
#
#     혼자 바쁠 때    3.80초 → **0.95초**   **4.0배**
#     셋이 바쁠 때    3.80초 → 2.95초       1.3배
#     여섯이 바쁠 때  3.80초 → **5.95초**   **느려진다** — 대신 **안 넘는다**
#
# **「빨라진다」 가 아니라 「안전하게 빨라진다」 이다.** 지금 빠른 것은
# 한도를 넘으면서 빠른 것이다 (위 값은 합계 20 으로 재본 것이다).
#
# **왜 벽시계인가** — `time.monotonic()` 은 프로세스마다 기준이 다를 수
# 있다. **공유 파일에 적어 남이 읽는 값**이므로 벽시계여야 뜻이 통한다.
# 시계가 뒤로 가도 `max(지금, ...)` 이라 그냥 지금부터 간다.
#
# **파일은 저장소 밖에 둔다.** 여섯 폴더가 함께 봐야 하는데 저장소 안에
# 두면 **폴더마다 따로가 되어 뜻이 없다.**
#
# **죽은 서버가 줄을 잡고 안 놓으면?** — 안 그런다. 강제 종료시켜 재보니
# **0ms 만에 풀렸다** (2026-09-23 실측). OS 가 프로세스를 정리하며 핸들을
# 닫아 락도 함께 풀린다.
#
# **홈 디렉터리에 둔다** (2026-09-30).
#
# ⚠️ **전에는 「파일 자리에서 네 칸 위」 였고 그 전제가 깨졌다.**
# 「네 번 올라가면 `work` — 폴더들의 공통 부모」 로 짰는데(2026-09-23),
# **서비스방이 `~/service` 에 생기면서 `work` 밖**이 됐다. 그러자 줄이
# **둘로 갈렸다** — `~/work/.kjc-kis-rate`(work 아래 다섯)와
# `~/.kjc-kis-rate`(서비스방 혼자). **각자 초당 10건까지 쓰면 합쳐서 20** 으로
# 실제 한도와 같아지고, 2026-09-30 16~19시에 **KIS 가 41건을 거절했다**
# (`EGW00201` — 8765 22 · 8764 16 · 8767 3). 8764 는 **뜬 26초 뒤**부터 났다.
#
# **폴더 위치로 공유 자리를 정하면 폴더가 늘 때 갈린다.** 같은 뿌리가 하나
# 더 있다 — `docstore.DOC_ROOT` 도 `__file__` 기준이라 **보드가 폴더마다
# 따로**다. **세 번째를 만들지 않는다.**
#
# ⚠️ **`overruns60s` 로는 이것을 못 본다.** 그 값은 「내 줄에서 미뤘나」 를
# 세므로 **줄이 둘이면 두 줄이 각각 「안 넘었다」 로 답한다.** KIS 가 실제로
# 거절한 것(`EGW00201`)과 **다른 것을 센다.**
#
# **대가** — 윈도우에서 자리가 바뀐다 (`C:\work\` → `C:\Users\<사용자>\`).
# 동작은 같다(홈이 하나라 폴더들이 그대로 공유한다). 다만 **옛 파일이 남는다.**
# 그리고 **여러 사용자가 쓰는 기계에서는 홈이 갈린다** — 지금은 사용자가
# 하나라 안 걸리지만, 그때는 `KJC_RATE_FILE` 로 한 자리를 지정한다.
#
# ⚠️ **이 계산은 임시다.** 재권님이 **KIS 부르는 자리를 8765 하나로 모으기**
# 를 정하셨고, 그것이 되면 **공유 줄 자체가 필요 없어진다.**
_HERE = os.path.abspath(__file__)          # 아래 `here` 도 쓴다 (지우지 말 것)
RATE_FILE = os.environ.get("KJC_RATE_FILE") or os.path.join(
    os.path.expanduser("~"), ".kjc-kis-rate")

try:
    import msvcrt as _msvcrt          # 윈도우
    _fcntl = None
except ImportError:                    # 맥 · 리눅스
    _msvcrt = None
    import fcntl as _fcntl

_shared_fail = 0


def _shared_slot(gap):
    """공유 줄에서 내 차례를 받는다. 못 받으면 `None`.

    **㉠ 락을 못 잡으면 자기 줄로 물러선다.** 공유 파일이 없거나 잠겨서
    못 읽으면 **지금까지의 방식(자기 변수)** 으로 돌아간다. 공유가 깨져도
    **최소한 자기 간격은 지킨다** — 「못 잡으면 그냥 보낸다」 가 가장 나쁘다.
    """
    global _shared_fail
    fh = None
    try:
        fh = os.open(RATE_FILE, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0))
        if _msvcrt:
            _msvcrt.locking(fh, _msvcrt.LK_LOCK, 8)
        else:
            _fcntl.flock(fh, _fcntl.LOCK_EX)
        raw = os.read(fh, 8)
        last = struct.unpack("d", raw)[0] if len(raw) == 8 else 0.0
        now = time.time()
        start_at = max(now, last + gap)
        os.lseek(fh, 0, 0)
        os.write(fh, struct.pack("d", start_at))
        os.lseek(fh, 0, 0)
        if _msvcrt:
            _msvcrt.locking(fh, _msvcrt.LK_UNLCK, 8)
        else:
            _fcntl.flock(fh, _fcntl.LOCK_UN)
        _shared_fail = 0
        return start_at
    except Exception as e:
        # **한 번만 알린다.** 매 호출마다 찍으면 로그가 그것으로 찬다.
        if not _shared_fail:
            sys.stderr.write("  [KIS] **공유 줄을 못 썼습니다 — 자기 줄로 갑니다**: %s\n"
                             % type(e).__name__)
        _shared_fail += 1
        return None
    finally:
        if fh is not None:
            try:
                os.close(fh)
            except Exception:
                pass


# ── ㉡ 넘는 것을 세어 스스로 늦춘다 ────────────────────────────
#
# 지금까지는 `EGW00201` 이 나면 **1초 쉬고 한 번만** 다시 부르고 끝이었다.
# **몇 번 났는지 아무도 몰랐다** — 「넘고 있다는 것을 아무도 모른다」 가
# 2026-09-23 조사에서 가장 큰 문제로 나왔다.
#
# 최근 60초에 넘은 횟수만큼 **간격을 늘린다.** 한 번에 10%씩, 최대 **세 배**.
# 잠잠해지면 60초 뒤 저절로 돌아온다. **사람이 손대지 않아도 된다.**
_over_times = []
OVER_WINDOW = 60.0
OVER_STEP = 0.10
OVER_MAX = 3.0

# ── 누적으로도 센다 (2026-09-30) ────────────────────────────────────
#
# 위 `_over_times` 는 **60초 창으로 잘린다.** 그래서 `overruns60s` 는
# **「최근 60초에 넘었나」 까지만** 답한다 — **「오늘 한 번이라도 넘었나」 를
# 답할 값이 없었다.**
#
# 간격을 늘리는 계산에는 창이 맞다(잠잠해지면 돌아와야 한다). **보는 값으로는
# 창이 틀렸다** — 넘은 지 61초가 지나면 **없던 일이 된다.**
#
# 예산을 계산으로 정하는 구조에서는 **이 값이 계산이 맞았는지 볼 유일한
# 자리**다. 창 안에서만 보면 「지금 안 넘고 있다」 와 「한 번도 안 넘었다」 가
# 갈리지 않는다.
#
# **재시작하면 0 이다** — `totalCalls` 와 같은 뜻의 누적이다.
_over_total = 0
_over_last_at = None


def note_overrun():
    """`EGW00201` 이 났다고 적는다. `kis_get` 이 부른다."""
    global _over_total, _over_last_at
    now = time.time()
    _over_times.append(now)
    _over_total += 1
    _over_last_at = now
    while _over_times and _over_times[0] < now - OVER_WINDOW:
        _over_times.pop(0)
    sys.stderr.write("  [KIS] **한도 초과(EGW00201)** — 최근 %d초에 %d번 · 누적 %d번\n"
                     % (int(OVER_WINDOW), len(_over_times), _over_total))


def _gap_now(n_keys=1):
    """지금 쓸 간격. 넘은 적이 잦으면 늘어난다. 키가 둘이면 반이다."""
    now = time.time()
    while _over_times and _over_times[0] < now - OVER_WINDOW:
        _over_times.pop(0)
    return (KIS_MIN_INTERVAL * min(OVER_MAX, 1.0 + OVER_STEP * len(_over_times))
            / max(1, n_keys))


# ── ㉢ 남는 예산을 채운다 — 서버가 스스로 당기고 늦춘다 (2026-10-15 재권님 「응 해줘」) ──
#
# 재권님 — 「한도를 정하고 한도안에서 계속 정보 받아와야 하는데 예산이 남는 이유는 뭐지?」.
# 장중 사용이 예산의 10~14% 였다. 시세 보관(`PRICE_CACHE_TTL`)과 미리 받기의 쉬는 시간이
# 고정이라 예산이 남아도 그대로 쉬었다.
#
# 그래서 **지난 60초 사용률**을 보고 배수(`fill_factor`)를 움직인다 — 목표보다 많이 적으면
# 조금씩 줄이고(더 자주 받음), 목표를 넘거나 한도 초과(㉡)가 났으면 빨리 늘린다(되돌림).
# 이 배수를 시세 보관 시간과 미리 받기 쉬는 시간에 곱한다. 화면은 지금처럼 서버가 주는 값을
# 받는다 — 롱폴이 1초마다 안쪽을 다시 보므로 보관이 짧아지면 새 값이 그만큼 빨리 간다.
#
# **8765 처럼 KIS 를 직접 부르는 빠른 서버만** 움직인다. `--slow` 서버 · 상류로 넘기는
# 서버는 1 그대로다 — 넘기는 서버는 자기 호출이 0 으로 세어져 끝없이 당기게 된다.
FILL_TARGET = 0.6         # 지난 60초 사용이 예산(키 수 × 키당 한도)의 이만큼을 넘으면 늦춘다
FILL_FLOOR = 0.25         # 가장 당겨도 원래 값의 이만큼까지 (시세 25초 → 8초 바닥 · 쉬기 20초 → 5초)
FILL_STEP_DOWN = 0.85     # 한가하면 한 번에 이만큼 곱한다
FILL_STEP_UP = 1.5        # 차면 한 번에 이만큼 곱한다 — 늦추는 쪽이 빠르다
FILL_EVERY = 10.0         # 배수를 다시 보는 간격(초)
PRICE_TTL_FLOOR = 8       # 시세 보관 바닥(초)
_fill = {"factor": 1.0, "at": 0.0, "usage": None, "changes": 0}
_fill_lock = threading.Lock()
# **넘기는 빠른 서버(8764)는 상류(8765)의 배수를 따른다** (2026-10-15 재권님 「응」 — 외부접속도 받아
# 다시 그리게). 자기 호출은 0 으로 세어지므로 스스로 셈하지 않고, 넘기기 응답에 실려 온 값을 쓴다.
# 이 시간 안에 받은 값만 믿는다 — 상류가 죽어 폴백하면 1 로 돌아간다
FILL_REMOTE_MAX_AGE = 120.0
_fill_remote = {"factor": None, "at": 0.0}


def fill_factor():
    """시세 보관 · 미리 받기 쉬는 시간에 곱할 배수(`FILL_FLOOR` ~ 1)."""
    if SLOW:
        return 1.0
    now = time.time()
    if KIS_UPSTREAM_RAW:
        f = _fill_remote["factor"]
        if f is None or now - _fill_remote["at"] > FILL_REMOTE_MAX_AGE:
            return 1.0
        return max(FILL_FLOOR, min(1.0, f))
    with _fill_lock:
        if now - _fill["at"] < FILL_EVERY:
            return _fill["factor"]
        _fill["at"] = now
        budget = KIS_CALLS_PER_SEC * max(1, _keys_active) * 60.0
        used = sum(1 for t in list(_call_times) if t > now - 60)
        u = used / budget if budget else 1.0
        over = sum(1 for t in list(_over_times) if t > now - OVER_WINDOW)
        f = old = _fill["factor"]
        if over or u > FILL_TARGET:
            f = min(1.0, f * FILL_STEP_UP)
        elif u < FILL_TARGET * 0.8:
            f = max(FILL_FLOOR, f * FILL_STEP_DOWN)
        _fill["factor"], _fill["usage"] = f, u
        if round(f, 3) != round(old, 3):
            _fill["changes"] += 1
        return f


def fill_stats():
    return {"factor": round(fill_factor(), 3),
            "usage60s": None if _fill["usage"] is None else round(_fill["usage"], 3),
            "target": FILL_TARGET, "floor": FILL_FLOOR, "changes": _fill["changes"],
            "priceTtlNow": _cache_ttl(None),
            "fromUpstream": bool(KIS_UPSTREAM_RAW) and not SLOW}


def _stamp():
    """`11:23:45.678` — **밀리초까지 찍는다.**

    「같은 순간에 몇 건인가」 를 재려는 것이 목적이라 **초 단위로는 모자란다.**
    초로만 찍으면 「그 초에 몇 건」 까지만 나오고 **간격이 지켜졌는지**는
    안 보인다. 밀리초가 있으면 둘 다 나온다.

    날짜는 안 찍는다 — 로그가 서버 시작마다 새로 쓰이므로(`startup.bat` 이
    `>` 로 연다) **한 파일이 하루를 넘기는 일이 드물고**, 줄마다 열 글자가 는다.
    """
    t = time.time()
    return "%s.%03d" % (time.strftime("%H:%M:%S", time.localtime(t)),
                        int(t % 1 * 1000))


# ── 외부접속 우선 (2026-10-02 · 서버리소스 2단계 ⓒ) ─────────────────
#
# 8765 는 넘겨받은 요청을 **한 줄**에 세운다. 확인용 서버(`--slow`)가 넘긴 것과
# 외부접속(8764)이 넘긴 것이 같은 줄이라, 예산이 모자라면 외부접속 화면이 확인용
# 뒤에서 기다렸다. **확인용이 넘긴 것은 「낮음」 으로 표시하고**, 최근에 높은 쪽
# (외부접속 · 8765 화면)이 불렀으면 줄에 서기 전에 잠깐 비켜선다 — 미리받기가
# 화면에 비켜서는 것(`_ui_busy`)과 같은 모양이다.
#
# **표시는 보내는 쪽이 붙인다** — 헤더 `X-KJC-Prio: low`. 자기가 `--slow` 인지는
# 보내는 쪽만 안다. 헤더라서 넘기기 캐시 키(`path`·`params`·`tr_id`)가 안 바뀐다.
#
# ⚠️ **표시는 그 요청의 스레드에만 붙는다**(`threading.local`). 처리 중에
# `ThreadPoolExecutor` 로 넘어간 호출은 표시를 잃고 **높음으로 친다** — 모르면
# 높은 쪽으로 두는 편이 외부접속을 안 막는다.
PRIO_HEADER = "X-KJC-Prio"
LOW_PRIO_BUSY_WINDOW = 15.0    # 이 시간 안에 높은 쪽이 불렀으면 '붐빈다'
LOW_PRIO_YIELD_SEC = 0.5       # 낮음이 줄에 서기 전에 비켜서는 시간
_prio = threading.local()
_last_high_at = 0.0            # 높은 쪽이 마지막으로 /api/kis/* 를 부른 시각(monotonic)
_prio_stat = {"lowCalls": 0, "lowYields": 0}


# `_rate_limit` 이 그 호출에서 **일부러 잔 시간**(ms). `kis_get` 이 대기에서 뺀다.
_rl_yield = threading.local()
# 미리받기가 지금 「보이는 종목」 을 받는 중인가 — 그때는 비켜서지 않는다 ((다))
_prefill_hot = threading.local()


def _prio_low():
    return getattr(_prio, "low", False)


def _rate_limit(path=None, n_keys=1):
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
    _rl_yield.ms = 0.0
    # (다) 보이는 종목을 받는 중이면 비켜서지 않는다 — `_prefill_one` 이 켠다
    if (threading.current_thread().name == PREFILL_THREAD_NAME
            and not getattr(_prefill_hot, "on", False)):
        _t0 = time.monotonic()
        time.sleep(PREFILL_BUSY_CALL_GAP * fill_factor() if _ui_busy() else PREFILL_IDLE_CALL_GAP)
        # **실제로 잔 시간을 잰다** — 이 기계는 잠에서 늦게 깨서(10ms → 49ms 실측)
        # 정한 값으로 빼면 그 넘침이 줄 서기로 세어진다
        _rl_yield.ms += (time.monotonic() - _t0) * 1000.0

    # **확인용 서버가 넘긴 것은 외부접속에 비켜선다** (ⓒ · 위 주석).
    if _prio_low():
        _prio_stat["lowCalls"] += 1
        if (time.monotonic() - _last_high_at) < LOW_PRIO_BUSY_WINDOW:
            _prio_stat["lowYields"] += 1
            _t0 = time.monotonic()
            time.sleep(LOW_PRIO_YIELD_SEC)
            _rl_yield.ms += (time.monotonic() - _t0) * 1000.0

    # **간격은 넘은 횟수에 따라 늘어난다** (㉡). 잠잠하면 원래 값이다.
    gap = _gap_now(n_keys)

    # **먼저 공유 줄에 선다.** 여섯이 한 줄이므로 안 쓰는 서버는 자리를
    # 차지하지 않고, 쓰는 서버가 남는 몫을 다 가져간다.
    start_at = _shared_slot(gap)

    global _last_call_at
    if start_at is None:
        # **㉠ 공유 줄을 못 썼다 — 자기 줄로 물러선다.**
        # 공유가 깨져도 **최소한 자기 간격은 지킨다.**
        with _rate_lock:
            start_at = max(time.time(), _last_call_at + gap)
            _last_call_at = start_at
    else:
        # 공유로 받았어도 자기 기록은 맞춰 둔다 — 물러설 때 이어지게.
        with _rate_lock:
            _last_call_at = max(_last_call_at, start_at)

    with _rate_lock:
        now = time.time()
        _call_times.append(now)
        # 1시간보다 오래된 기록은 버린다
        cutoff = now - 3600
        while _call_times and _call_times[0] < cutoff:
            _call_times.pop(0)

    # **차례까지 기다린다.** 공유·자기 줄 둘 다 **벽시계** 기준이다 —
    # 공유 파일에 적어 남이 읽는 값이라 `monotonic` 으로는 뜻이 안 통한다.
    wait = start_at - time.time()
    if wait > 0:
        time.sleep(wait)

    # **나가는 문** — 지난 1초 안 실제로 지난 수가 한도면 더 기다린다 (위 주석).
    # 키가 둘이면 **덜 쓴 키**를 고른다 — 고른 키 번호(0 · 1)를 돌려준다.
    slot = _send_gate(n_keys)

    # **기다린 뒤에 찍는다 — 여기가 실제로 나가는 순간이다**
    # (2026-09-23 지시 — 「실시간으로 어디서뭐 쓰는지 로그 알수있는게
    #  있어야 할거같은데」).
    #
    # 처음에 자물쇠 안에서 찍었더니 **다섯 건이 같은 밀리초로 찍혔다**
    # (2026-09-23 실측). 거기는 **차례를 배정받는 자리**이고 실제로
    # 나가는 것은 `sleep` 뒤다. **「같은 순간에 몇 건인가」 를 재려는
    # 것이므로 배정 시각으로는 뜻이 없다.**
    #
    # ⚠️ **`_call_times` 는 여전히 배정 시각이다.** `usage_stats()` 가
    # 그것을 쓰므로 **로그와 값이 최대 간격만큼 어긋난다.** 고치면
    # 자물쇠 밖에서 목록을 건드리게 되어 범위가 커진다 — 로그로 먼저
    # 보고 정한다.
    #
    # 아래 `[API]` 줄은 **화면 → 서버** 요청이라 캐시로 막힌 것까지
    # 세어진다 — **한도 대상은 이쪽**이다.
    sys.stderr.write("  [KIS] %s :%s %s%s\n"
                     % (_stamp(), RUN_PORT, path or "?", " ·키2" if slot else ""))
    return slot


def _ring_dump(me):
    """거절난 호출(`me`) 앞 `SEND_RING_DUMP_SEC` 초를 한꺼번에 찍는다."""
    t_me = me[0]
    rows = [r for r in list(_send_ring) if t_me - SEND_RING_DUMP_SEC <= r[0] <= t_me + 1.0]
    sys.stderr.write("  [KIS-거절] %s :%s 거절난 것 보냄 %s · 앞 %.0f초 %d건(보낸 시각 · 왕복 ms · 결과)\n"
                     % (_stamp(), RUN_PORT, _fmt_wall(t_me), SEND_RING_DUMP_SEC, len(rows)))
    for r in rows:
        ms = "—" if r[2] is None else "%.0f" % r[2]      # 아직 안 돌아온 것은 「—」
        sys.stderr.write("    %s %6s %s%s%s\n" % (_fmt_wall(r[0]), ms, r[3] or "…",
                                                " ·키2" if r[4] else "",
                                                "  ← 이것" if r is me else ""))


def _fmt_wall(t):
    return "%s.%03d" % (time.strftime("%H:%M:%S", time.localtime(t)), int(t % 1 * 1000))


def _send_gate(n_keys=1):
    """키마다 「지난 1초 안에 이 문을 지난 수 < 한도」 인 키가 생길 때까지 기다린다.

    여럿이 비면 **덜 쓴 키**를 고른다. 고른 키 번호(0 · 1)를 돌려준다.
    """
    limit = max(1, int(KIS_CALLS_PER_SEC))
    n = max(1, min(n_keys, len(_send_times)))
    held = 0.0
    while True:
        with _send_lock:
            now = time.monotonic()
            for k in range(n):
                dq = _send_times[k]
                keep = [e for e in dq
                        if not ((e[1] is not None and e[1] <= now - 1.0)
                                or (e[1] is None and e[0] <= now - SEND_GATE_STALE))]
                if len(keep) != len(dq):
                    dq.clear()
                    dq.extend(keep)
            k = min(range(n), key=lambda i: len(_send_times[i]))
            dq = _send_times[k]
            if len(dq) < limit:
                prev = getattr(_gate_tl, "entry", None)
                if prev is not None and prev[1] is None:
                    prev[1] = now            # 앞에 잡고 안 보낸 자리(토큰 받기 · 키 바꿈)는 여기서 놓는다
                entry = [now, None]
                dq.append(entry)
                _gate_tl.entry = entry
                pk = _send_stat["perKey"][k]
                pk["sent"] += 1
                if len(dq) > pk["maxIn1s"]:
                    pk["maxIn1s"] = len(dq)
                total = sum(len(_send_times[i]) for i in range(n))
                if total > _send_stat["maxIn1s"]:
                    _send_stat["maxIn1s"] = total
                if held:
                    _send_stat["held"] += 1
                    _send_stat["heldMs"] += held * 1000.0
                return k
            # 응답이 온 것 중 가장 먼저 1초를 벗어나는 순간까지 — **`SEND_GATE_PAD` 여유**.
            # 다 아직 응답 전이면 짧게 쉬고 다시 본다
            done = [e[1] for i in range(n) for e in _send_times[i] if e[1] is not None]
            pause = (min(done) + 1.0 - now + SEND_GATE_PAD) if done else 0.02
            pause = max(0.005, pause)
        time.sleep(pause)
        held += pause


# ── 주기·캐시 값을 한 곳에서 모아 낸다 (2026-09-23 지시) ────────────────
#
# 「캐시·주기·한도 값을 화면에 박지 않는다 — 서버가 내주고 화면이 받는다」.
# 화면에 박으면 **캐시를 고쳐도 화면이 안 바뀌고**, 고쳤는지 아닌지를
# 눈으로는 못 찾는다.
#
# **목록을 적지 않는다.** 이름 규칙으로 훑으므로 상수가 늘어도 저절로 들어온다.
# 목록을 적으면 그 목록이 **또 하나의 복제**가 되고 값이 늘 때마다 낡는다.
#
# **범위는 서버 폴더 전체다.** `kis_proxy.py` 하나만 보면 `dart.py` ·
# `news.py` · `news_store.py` 의 값을 놓친다. **모듈 이름을 적는 대신
# 「파일이 이 폴더 안에 있는 모듈」** 을 훑는다 — 파일이 늘어도 따라온다.
#
# **소스를 읽어 세지 않는다. 돌고 있는 값을 낸다** — `globals()` 를 본다.
# 2026-09-23 에 `KIS_MIN_INTERVAL` 이 **소스로는 `1.0`, 실제로는 `0.2`** 였고
# 그 줄의 주석까지 낡아 있어 **읽는 쪽이 두 번 속았다.**
#
# `_PER_SEC` 는 뺀다 — 그것은 **「초당 몇 건」 이지 「몇 초마다」** 가 아니다.
# 그 값들은 아래 `usage_stats` 가 `budget…` 항목으로 따로 낸다.
_TIMING_SUFFIX = ("_TTL", "_INTERVAL", "_SEC")


def timing_values():
    """서버 폴더 안 모듈의 주기·캐시 상수를 **돌고 있는 값**으로 모은다.

    키는 `<모듈>.<이름>`, 값은 **초**다. 모듈 이름을 붙이는 것은
    `POLL_INTERVAL` 처럼 흔한 이름이 두 파일에 생겨도 **어느 것인지
    갈리게** 하기 위해서다 — 이름만 쓰면 나중에 조용히 덮인다.

    ⚠️ **모듈 이름은 `sys.modules` 의 키가 아니라 파일 이름으로 쓴다**
    (2026-10-02). 그 키는 **어떻게 띄웠느냐**에 따라 달라진다 — 이 파일을
    바로 실행하면 `__main__` 이고 import 되면 `kis_proxy` 다. 그래서
    화면이 `kis_proxy.SECTOR_TTL` 을 찾는데 서버는 `__main__.SECTOR_TTL`
    을 내주고 있었다. **찾지 못하면 `serverMs` 가 조용히 대체값으로
    내려앉아**(`js/store/timing.js`) `--slow` 서버에서도 화면만 자주 돌았다.
    **「없다」 가 아니라 「그 이름으로는 없다」 였다.**
    """
    here = os.path.dirname(_HERE)
    out = {}
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        try:
            if os.path.dirname(os.path.abspath(f)) != here:
                continue
            # 띄운 방법에 따라 달라지지 않게 **파일 이름**으로 짓는다
            mod_name = os.path.splitext(os.path.basename(os.path.abspath(f)))[0]
        except (OSError, ValueError):
            continue
        for k, v in list(vars(mod).items()):
            # 밑줄로 시작하는 것은 **그 파일 안에서만 쓰는 값**이라 뺀다.
            # `k.isupper()` 는 밑줄을 대문자로 치지 않아 `_CACHE_TTL` 이
            # 통과한다 — 2026-09-30 실측에서 `secrets_guard._CACHE_TTL` 이
            # 그렇게 섞였다. 화면이 쓸 값이 아니다.
            if k.startswith("_") or not k.isupper() or k.endswith("_PER_SEC"):
                continue
            if not k.endswith(_TIMING_SUFFIX):
                continue
            # bool 은 int 라 먼저 거른다 — `SEND = True` 같은 것이 섞인다
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            out["%s.%s" % (mod_name, k)] = v
    # **봉의 기간별 `fresh_sec`** (2026-10-03 재권님 「응 그래」). `PERIODS` 는 dict 라 위 이름 규칙에
    # 안 걸려 화면이 봉을 다시 물을 서버 값이 없었다(chart.js 가 60초를 박고 있었다).
    # 이름은 위와 같이 **파일 이름**을 앞에 붙인다 — `<모듈>.PERIODS.<기간>.fresh_sec`.
    me = os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]
    for p, conf in PERIODS.items():
        out["%s.PERIODS.%s.fresh_sec" % (me, p)] = conf["fresh_sec"]
    return out


# ── 스레드 감시 (2026-10-02 · 서버리소스 2단계 ⓔ) ──────────────────
#
# 연결 하나가 스레드 하나를 쥐는 틀이라, 롱폴링(ⓓ)을 켜거나 응답이 막히면 스레드가
# 쌓인다. **막지 않고 「봐야 할 자리」 로만 낸다** — 원인이 여럿이라 서버가 판단할 수 없다.
#
# **기준값을 박지 않는다.** 바탕(`base`)은 `stats` 를 읽을 때마다 본 **가장 작은 수**
# — 한가할 때의 스레드다. 경고선은 바탕 + 롱폴링이 쥘 수 있는 최대(`LONGPOLL_MAX_ACTIVE`)
# + 여유(`THREAD_SLACK`)다. 롱폴링 상한을 바꾸면 경고선도 따라간다.
#
# **넘은 순간에 로그 한 줄만** 남긴다 — 매번 찍으면 로그가 그 줄로 덮인다.
THREAD_SLACK = 16
_thr = {"base": None, "peak": 0, "over": False, "overCount": 0, "overLastAt": None}
_thr_lock = threading.Lock()


def thread_watch():
    now_n = threading.active_count()
    with _thr_lock:
        if _thr["base"] is None or now_n < _thr["base"]:
            _thr["base"] = now_n
        _thr["peak"] = max(_thr["peak"], now_n)
        line = _thr["base"] + LONGPOLL_MAX_ACTIVE + THREAD_SLACK
        over = now_n > line
        if over and not _thr["over"]:
            _thr["overCount"] += 1
            _thr["overLastAt"] = time.time()
            sys.stderr.write("  [스레드] **봐야 할 자리** — %d개 (바탕 %d · 경고선 %d)\n"
                             % (now_n, _thr["base"], line))
        _thr["over"] = over
        return {"now": now_n, "base": _thr["base"], "peak": _thr["peak"],
                "warnAt": line, "over": over, "overCount": _thr["overCount"],
                "overLastAt": _thr["overLastAt"]}


def usage_stats():
    """실제 호출량을 돌려준다 (재권님이 눈으로 확인하기 위한 용도)."""
    now = time.time()
    last_10s = sum(1 for t in _call_times if t > now - 10)
    last_60s = sum(1 for t in _call_times if t > now - 60)
    # **길이를 그대로 쓰지 않는다** (2026-10-01). 정리가 `_rate_limit` 안에서만
    # 돌아 **호출이 멈추면 값이 굳었다** — 「지난 1시간」 이 아니라 「기동 뒤 누적」
    # 이었다. `calls10s`·`calls60s` 는 처음부터 읽을 때 걸렀고 **이 한 줄만** 틀렸다.
    #
    # ⚠️ **여기서 정리(`pop`)하지 않는다.** `usage_stats()` 는 `_rate_lock` 을
    # 안 잡아 **자물쇠 밖에서 목록을 변경**하게 된다. 정리는 `_rate_limit` 이
    # 하고, **안 해도 못 커진다** — 초당 한도 × 1시간이 상한이다.
    last_1h = sum(1 for t in _call_times if t > now - 3600)
    last_1h_relayed = sum(1 for t in _relay_times if t > now - 3600)
    return {
        "limitPerSec": KIS_LIMIT_PER_SEC,
        "budgetRatio": BUDGET_RATIO,
        # **키 수만큼 곱한 합**이다 (2026-10-06 · 앱키 둘). 키 하나면 그대로다.
        "budgetPerSec": KIS_CALLS_PER_SEC * _keys_active,
        "minIntervalSec": KIS_MIN_INTERVAL,
        # **나가는 문** (2026-10-03) — 1초 창 최대 · 문에서 더 기다린 횟수와 합(ms).
        # 재시작 뒤 누적이다. `maxIn1s` 는 키를 합친 값 · `perKey` 는 키마다다.
        # 키마다 `maxIn1s` 가 `limitPer1s` 를 넘으면 문이 안 듣는 것이다.
        "sendGate": {"limitPer1s": max(1, int(KIS_CALLS_PER_SEC)),
                     "keys": _keys_active,
                     "maxIn1s": _send_stat["maxIn1s"],
                     "perKey": [dict(p) for p in _send_stat["perKey"][:max(1, _keys_active)]],
                     "key2DownSec": max(0, int(_key2_down_until - time.time())),
                     "held": _send_stat["held"],
                     "heldMs": round(_send_stat["heldMs"], 1)},
        "calls10s": last_10s,
        "calls60s": last_60s,
        "calls1h": last_1h,
        # **그중 넘겨받은 몫.** `calls1h - calls1hRelayed` 가 8765 자기 몫이다 —
        # 「넘기기가 얼마나 모았나」 를 재는 값이고 전에는 섞여서 못 봤다.
        "calls1hRelayed": last_1h_relayed,
        # **밀어주기 비용의 분모** (2026-10-02). 연결 하나가 스레드 하나를
        # 쥐는 틀(`ThreadingHTTPServer`)이라, 롱폴링을 켜면 이 값이 창 수만큼
        # 늘어난다. **지금은 요청이 끝나면 돌아온다** — 켜기 전후를 견주려고 둔다.
        "threads": threading.active_count(),
        # ⓔ 바탕 · 최대 · 경고선 · 넘은 횟수 — 막지 않는다
        "threadWatch": thread_watch(),
        # **응답 시간** — 하한 계산에 쓴다. 못 쟀으면 `None` 이다.
        "respMs": resp_stats(),
        "perSec60s": round(last_60s / 60.0, 3),
        "budgetUsedPct": round((last_60s / 60.0) / KIS_CALLS_PER_SEC * 100, 1) if KIS_CALLS_PER_SEC else 0,
        "limitUsedPct": round((last_60s / 60.0) / KIS_LIMIT_PER_SEC * 100, 1) if KIS_LIMIT_PER_SEC else 0,
        # ㉡ **넘은 횟수와 지금 간격** — 화면이 이것을 보면
        # 「넘고 있다」 를 알 수 있다.
        "overruns60s": len(_over_times),
        # **누적.** 창 안에서만 보면 「지금 안 넘고 있다」 와 「한 번도 안
        # 넘었다」 가 안 갈린다. 재시작하면 0 이다
        "overrunsTotal": _over_total,
        "overrunGiveUps": _over_giveup,          # 거절을 KIS_OVER_RETRY 번 다시 보내도 못 받은 수 (10-27)
        "overrunLastAt": _over_last_at,
        "gapNowSec": round(_gap_now(), 4),
        "sharedQueue": _shared_fail == 0,
        "cacheHits": _stats["cache_hits"],
        "totalCalls": _stats["kis_calls"],
        "priceCacheTtl": PRICE_CACHE_TTL,
        # 남는 예산 채우기 (2026-10-15) — 지금 배수 · 지난 60초 사용률 · 지금 시세 보관(초)
        "fill": fill_stats(),

        # ── 넘기기 (2026-10-01) ── ⚠️ **주소는 내지 않는다.** 이 응답이
        # 8764(서비스방)를 거쳐 밖으로 나가므로 내부 주소가 보이면 안 된다.
        "upstream": bool(upstream_base()),
        "upstreamServe": KIS_UPSTREAM_SERVE,
        "upstreamCalls": _up_stat["calls"],
        "upstreamFallbacks": _up_stat["fallbacks"],
        "upstreamLastError": _up_stat["lastError"],
        "boardUpstream": bool(board_upstream_base()),
        "boardUpstreamCalls": _board_stat["calls"],
        "boardUpstreamErrors": _board_stat["errors"],
        "boardUpstreamLastError": _board_stat["lastError"],
        # ── 넘겨받은 요청의 캐시 (2026-10-01) ── **줄어든 비율을 재는 자리다.**
        # `relayCacheHits` ÷ (`relayCacheHits` + `relayCacheMisses`) 가
        # **KIS 를 안 부른 비율**이다. 로그에 종목코드를 남기지 않고도
        # 「얼마나 줄었나」 가 나온다 (창구 판단 2026-10-01).
        "relayCacheHits": _relay_stat["hits"],
        "relayCacheMisses": _relay_stat["misses"],
        "relayCacheSize": len(_relay_cache),
        # 경로별 넘기기 캐시 수명(2026-10-02). `None` 이면 상수 이름이 틀렸다.
        "relayTtl": relay_ttl_table(),
        # ⓒ 낮음(확인용 서버가 넘긴 것)이 줄에 선 횟수 · 그중 비켜선 횟수
        "prioLowCalls": _prio_stat["lowCalls"],
        "prioLowYields": _prio_stat["lowYields"],
        # ⓓ 롱폴링 — 꺼져 있으면 `longpoll: false` 이고 셈은 0 이다(그 자리가 없으므로)
        "longpoll": LONGPOLL_ON,
        # 실시간 체결(웹소켓 · 2026-11-05) — 화면은 `kisWs` 가 참일 때만 `/api/kis/live` 를 묻는다.
        # 넘기는 서버는 8765 에 물어 그쪽이 꺼져 있으면 `on:false` 를 받는다(화면이 그때 쉰다)
        "kisWs": kis_ws.KIS_WS_ON or bool(upstream_base()),
        "kisWsStats": kis_ws.stats(),
        "longpollPrefixes": list(LONGPOLL_PREFIXES),
        "longpollActive": _lp_stat["active"],
        "longpollTotal": _lp_stat["total"],
        "longpollChanged": _lp_stat["changed"],
        "longpollBusy": _lp_stat["busy"],
        # 화면 API 를 통째로 넘긴 횟수 · 폴백 (차트 셋 — `HIGH_RELAY_ROUTES`)
        "upstreamRouteCalls": _up_stat["routeCalls"],
        "upstreamRouteFallbacks": _up_stat["routeFallbacks"],

        # **주기·캐시 값 전부.** 위 `priceCacheTtl` 은 `status.html` 이
        # 쓰고 있어 남겨 둔다 — 같은 값이 여기에도 들어오지만 **한 곳에서
        # 나오므로 갈리지 않는다.** 화면을 옮기면 위 줄을 지운다.
        "timing": timing_values(),
        # 「장외」 칩을 비워 두는 시각(평일) — 화면이 빈 칸 까닭 글을 이 값으로 짓는다. 시각은 아래 AFTER_CLEAR_AT · AFTER_CLEAR_UNTIL 한 곳
        "afterClear": {"from": "%02d:%02d" % AFTER_CLEAR_AT, "until": "%02d:%02d" % AFTER_CLEAR_UNTIL},
        # 정규장 칩(현재상승 · VI·급등 · 볼린저 · 매수)이 비는 때(평일) — market_hours.CHIP_RESET ~ REG_OPEN 한 곳 · 화면 「현재상승」 이 읽는다
        "chipReset": {"from": "%s:%s" % (market_hours.CHIP_RESET[:2], market_hours.CHIP_RESET[2:]),
                      "until": "%s:%s" % (market_hours.REG_OPEN[:2], market_hours.REG_OPEN[2:])},
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
    # **둘째 앱키** (2026-10-06) — 있으면 붙여 둔다. 모의/실전은 첫째를 따른다.
    # 값은 어디에도 찍지 않는다. 없거나 비었으면 첫째 하나로 돈다.
    k2 = data.get("kis2") or {}
    if k2.get("app_key") and k2.get("app_secret"):
        kis["_key2"] = {"app_key": k2["app_key"], "app_secret": k2["app_secret"],
                        "mode": mode, "_slot": 1}
    return kis


# ---------------------------------------------------------------- 토큰 관리

def _token_path(cfg_or_slot):
    """키의 토큰 캐시 경로. 둘째 키(`_slot` 1)만 따로다."""
    slot = cfg_or_slot if isinstance(cfg_or_slot, int) else (cfg_or_slot or {}).get("_slot", 0)
    return TOKEN_CACHE_PATH2 if slot else TOKEN_CACHE_PATH


def _read_token_cache(mode, path=TOKEN_CACHE_PATH):
    try:
        with open(path, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        return None
    if cache.get("mode") != mode:
        return None
    # 만료 5분 전이면 새로 받는다
    if float(cache.get("expires_at", 0)) <= time.time() + 300:
        return None
    return cache.get("access_token")


def _write_token_cache(mode, token, expires_in, path=TOKEN_CACHE_PATH):
    """토큰 캐시를 **안전하게** 쓴다 (2026-09-22).

    전에는 `open(PATH, "w")` 로 바로 덮어썼다. 거기서 죽으면 **깨진
    캐시가 남는다.** 키 파일만큼 위험하진 않지만(다시 받으면 된다)
    같은 함수를 쓰면 한 곳만 고치면 된다.

    `tmp` 라는 이름이 붙어 있어 임시 파일을 쓰는 것처럼 보였는데
    **그냥 dict 이름**이었다 — 이름이 설명 노릇을 하던 자리다.
    """
    try:
        write_json_atomic(path, {
            "mode": mode,
            "access_token": token,
            "expires_at": time.time() + float(expires_in),
        }, indent=None)
    except (OSError, IOError):
        pass


def _drop_token_cache(mode, path=TOKEN_CACHE_PATH):
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
        write_json_atomic(path,
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

    path = _token_path(cfg)
    cached = _read_token_cache(cfg["mode"], path)
    if cached:
        return cached

    with (_token_lock2 if cfg.get("_slot") else _token_lock):
        return _issue_token(cfg)


def _issue_token(cfg):
    """실제 발급. _token_lock 을 쥔 상태에서만 부른다."""
    global _last_token_attempt, _last_token_attempt2

    slot = cfg.get("_slot", 0)
    path = _token_path(slot)
    cached = _read_token_cache(cfg["mode"], path)
    if cached:
        return cached

    elapsed = time.time() - (_last_token_attempt2 if slot else _last_token_attempt)
    if elapsed < TOKEN_MIN_INTERVAL:
        raise RuntimeError(
            "토큰 재발급 대기 중입니다. %d초 후 다시 시도해 주세요. "
            "(KIS 는 1분에 1회만 발급을 허용합니다)" % int(TOKEN_MIN_INTERVAL - elapsed)
        )
    if slot:
        _last_token_attempt2 = time.time()
    else:
        _last_token_attempt = time.time()

    # **㉢ 토큰 발급도 줄에 세운다** (2026-09-23).
    # 전에는 이 길이 `_rate_limit()` 을 안 탔다 — **줄 밖이었다.**
    # 빈도가 낮아(캐시가 만료 5분 전까지 산다) 느려지는 것이 없다.
    _rate_limit("/oauth2/tokenP")
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

    _write_token_cache(cfg["mode"], token, data.get("expires_in", 86400), path)
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

# ── 이 기계가 **내보내는 자리**인가 (2026-09-28 지시) ──────────
#
# 재권님 말씀 — 「맥미니로 완전히 이전될때까지는 **같이 쓰고**, 다되면
# **맥미니가 서버**로 되고 **pc는 작업용**이 될거야」.
#
# ⚠️ **포트만으로는 기계를 못 가른다.** `MAIN_PORT` 는 **한 기계 안** 여섯
# 폴더를 가르는 장치다. 맥미니에서도 8765 로 뜨면 **양쪽 다 「내가 메인」**
# 이 되어 텔레그램이 두 번 간다.
#
#     포트         한 기계 안 여섯 폴더   ← **그대로 둔다**
#     `KJC_ROLE`   **기계 사이**          ← 이것을 더한다
#
# **바꿔 끼우지 않고 AND 로 얹는다.** 역할로만 가르면 **여섯 폴더가 다시
# 새어**, 2026-09-23 에 고친 뉴스 두 번 건이 그대로 되살아난다.
#
# **값이 없으면 `work`(안 보냄)이다.** 맥미니를 처음 띄울 때 **실수로
# 보내는 것**을 막는다 — 「켜기」 는 명시적으로 켤 때만 일어나야 한다.
#
# ⚠️ **그래서 이 PC 도 `KJC_ROLE=server` 를 받아야 계속 보낸다.**
# 안 주면 재시작하는 순간 **넷이 다 조용해진다** — 그것이 이 설계의 대가다.
# 띄우는 쪽(`startup.bat` · `preview.bat`)이 준다.
#
# `KJC_RATE_FILE` 과 같은 방식이다 — **코드에 기계 이름을 안 박는다.**
ROLE = (os.environ.get("KJC_ROLE") or "work").strip().lower()
if ROLE not in ("server", "work"):
    # **오타를 조용히 넘기지 않는다.** 모르는 값이면 안 보내는 쪽으로 가는데,
    # 말을 안 하면 「왜 알림이 안 오지」 를 한참 찾게 된다.
    sys.stderr.write("  [역할] 모르는 KJC_ROLE 입니다 — work(안 보냄)로 봅니다\n")
    ROLE = "work"
IS_SERVER = ROLE == "server"


def is_sender(port):
    """텔레그램·KV 를 **실제로 내보내는 자리인가.**

    **두 층을 함께 본다.** 하나라도 빠지면 새거나 막힌다.

        `IS_SERVER`   기계 사이 — 맥미니냐 PC 냐
        `MAIN_PORT`   한 기계 안 — 여섯 폴더 중 메인이냐
    """
    return IS_SERVER and port == MAIN_PORT


# ── KIS 를 부르는 자리를 8765 하나로 모은다 (2026-10-01 지시 · 길 (가) 넘기기) ──
#
# 재권님 지시 — 「KIS 를 부르는 자리를 8765 하나로 모은다」. 세션 서버가
# 저마다 부르면 **예산을 그만큼 나눠 쓰고** 토큰도 폴더마다 따로 발급한다
# (2026-10-01 실측 — 폴더 일곱 중 **다섯**이 그날 토큰을 받았다).
#
#     **보내는 쪽**  `KJC_KIS_UPSTREAM`        값이 있으면 상류로 넘긴다
#     **받는 쪽**    `KJC_KIS_UPSTREAM_SERVE`  **8765 만 켠다**
#
# ⚠️ **스위치를 둘로 가른 이유.** 하나로 두면 **받는 자리가 모든 서버에
# 생긴다.** 8764(서비스방)는 **외부접속이 닿는 자리**라 거기에 그 자리가
# 있으면 안 된다. 안 켠 서버는 막힌 것이 아니라 **그 자리가 아예 없다.**
#
# ⚠️ **`client_address` 로는 외부접속을 못 걸러낸다 (2026-10-01 실측).**
# 서버가 **루프백에만** 떠 있고(`127.0.0.1` · `::1`) `cloudflared` 가
# **같은 기계에서** 돈다. 그래서 **터널을 거쳐 온 요청도 `127.0.0.1` 로
# 보인다.** 「로컬에서 온 것만 받는다」 는 **외부는 못 막고 `::1` 로 온
# 정상 호출만 가끔 막는다.** 그래서 그 검사를 **넣지 않았다** — 넣으면
# 다음 사람이 그것을 방어로 읽는다 (「설명이 이미 있으면 의심할 계기조차
# 없다」). 막는 것은 위의 **받는 쪽 스위치**와 아래 `/uapi/` 제한이다.
KIS_UPSTREAM_RAW = (os.environ.get("KJC_KIS_UPSTREAM") or "").strip().rstrip("/")
KIS_UPSTREAM_SERVE = (os.environ.get("KJC_KIS_UPSTREAM_SERVE") or "").strip().lower() in (
    "1", "true", "yes", "on")
RELAY_ROUTE = "relay"
# 넘긴 횟수 · 폴백한 횟수 · 마지막 오류. `stats` 가 낸다 — **주소는 안 낸다.**
_up_stat = {"calls": 0, "fallbacks": 0, "lastError": None,
            "routeCalls": 0, "routeFallbacks": 0}

# ── 보드도 8765 하나로 (2026-10-01 지시) ──────────────────────
#
# 재권님 지시 — 「보드를 서비스서버랑 진짜서버랑 동기화」. 보드가 폴더마다
# 따로 쌓이면 **외부접속이 보는 것과 메인이 보는 것이 갈린다.**
#
# ⚠️ **KIS 와 스위치를 가른다.** 하나로 두면 **폴백 없는 쪽(보드)이
# 폴백 있는 쪽(KIS)과 한꺼번에 켜진다.** 보드는 상류가 죽으면 `503` 이라
# **더 위험한데 켜는 순간을 못 고르게 된다** — 「켜기 전에 먼저 잰다」 를
# 쓸 수 없다.
#
# **받는 자리는 새로 만들지 않았다.** 8765 가 이미 `/api/board/*` 를
# 받는다 — KIS 가 `/api/kis/relay` 를 새로 만들어야 했던 것과 다르다.
BOARD_UPSTREAM_RAW = (os.environ.get("KJC_BOARD_UPSTREAM") or "").strip().rstrip("/")
_board_stat = {"calls": 0, "errors": 0, "lastError": None}

# ── 넘겨받은 요청도 캐시를 거친다 (2026-10-01 지시) ──────────────
#
# 재권님 지시 — 「둘 다 할 거니 정해서 진행」. **(가) 먼저.**
#
# ⚠️ **`relay` 는 `kis_get` 레벨이라 위쪽 캐시 열 곳을 모두 건너뛴다**
# (`_price_cache` · `_chart_cache` · `_index_cache` · `_quote_cache` ·
# `_sector_cache` · `_movers_cache` · `_inv_flow_cache` · `_investor_cache` ·
# `_fut_cache` · `_ovs_cache`). 그 캐시들은 전부 **화면 API 함수 안**에 있고
# 그 함수가 **그 아래로** `kis_get` 을 부른다.
#
# **그래서 넘기기만으로는 KIS 총량이 줄지 않았다** (qa 실측 2026-10-01 —
# 화면 둘 10분에 `relay` 1031건 ≈ 넘긴 수, 넘긴 건마다 KIS 한 건).
# **줄어든 것은 토큰 발급과 「레이트리밋이 한 줄에 서는 것」 이었다** —
# 전에는 서버가 각자 초당 한도를 세어 **합치면 그 배수까지** 나갈 수 있었다.
#
# **여기 캐시를 두면 같은 종목을 여러 화면이 봐도 KIS 를 한 번만 부른다.**
#
# **키는 KIS 요청 단위**(`path` · `params` · `tr_id`)다. 위쪽 캐시는 키가
# `code` 라 층이 달라 **키를 맞추는 문제가 아니다.**
#
# **TTL 은 경로마다 그 경로의 화면 API 가 쓰는 상수를 그대로 쓴다**
# (2026-10-02 · 서버리소스 2단계 ⓑ). 아래 `RELAY_TTL_NAMES` 가 경로 →
# **상수 이름**(값이 아니다)을 들고 있어 새 값이 생기지 않는다.
# 전에는 전부 `PRICE_CACHE_TTL`(25초) 하나라, 지수(5초)·선물(5초)·호가(3초)를
# 넘겨받으면 **25초 묵은 값**이 나갔다 — 외부접속 지수가 26.5초 늦던 원인이다
# (내부 4.1초 · 8764→8765 루프백은 1.1ms 라 거리가 아니었다).
#
# **동시 요청 합치기(single-flight)는 일부러 안 넣었다** (창구 판단
# 2026-10-01). 넣으면 **「락 때문에 느려졌나」 와 「캐시가 듣나」 가 섞여**
# 둘 다 못 가린다. 아래 `relayCacheHits` 로 **부족한지가 값으로 나오므로**
# 그것을 보고 정한다.
_relay_cache = {}                  # (path, params, tr_id) -> (저장시각, 데이터)
_relay_stat = {"hits": 0, "misses": 0}

# **넘겨받아 KIS 로 나간 시각.** `usage_stats()` 가 `calls1hRelayed` 로 낸다 —
# 8765 의 `calls1h` 에는 **자기 호출과 넘겨받은 것이 섞여** 있어
# 2026-10-01 에 **200 = 100 + 100** 이 됐고 그것을 가를 값이 없었다.
#
# ⚠️ **`deque(maxlen=…)` 다.** `append` 가 원자적이고 **넘치면 저절로 버리므로
# 자물쇠 없이 안전하다.** `_call_times` 처럼 `pop(0)` 루프를 돌면 읽는 쪽에서
# 건드릴 때 터질 수 있다. 상한은 **초당 한도 × 1시간** 이라 1시간 창을 못 넘는다.
_relay_times = collections.deque(maxlen=int(KIS_LIMIT_PER_SEC * 3600) + 1)

# **KIS 응답 시간 표본** (2026-10-02 · 서버리소스 1단계).
# 하한 계산(`하한 = max(그리는 시간 × 2, 응답 시간)`)에 쓸 값이 `stats` 에
# **하나도 없었다.** 없으면 그 식이 전부 추측이 된다.
#
# **두 가지를 가른다** — 섞으면 하한이 부풀려진다.
#     `respMs`   순수 왕복 (KIS 가 답하는 데 걸린 시간)      ← 하한에 쓰는 값
#     `waitMs`   줄 세우기에서 기다린 시간 (`_rate_limit`)   ← 예산이 모자란 정도
#
# ⚠️ **표본 상한을 손으로 박지 않는다.** 초당 한도에서 나오므로(1분치)
# 한도를 올리면 표본도 함께 늘어난다 — 주기·TTL 값이 아니라 **재는 창**이다.
# 경로마다 따로 담는다. 경로는 코드가 가진 닫힌 집합이라 늘어나지 않는다.
RESP_SAMPLES = int(KIS_LIMIT_PER_SEC * 60) + 1
_resp_times = {}                   # 경로 끝 조각 -> deque[(시각, 왕복ms, 대기ms)]
_resp_lock = threading.Lock()      # dict 에 **키를 만들 때만** 잡는다


def _resp_key(path):
    """경로를 「구역/마지막」 으로 줄인다 — **마지막 조각만으로는 겹친다.**

    `/uapi/domestic-stock/.../inquire-price`(주식)와
    `/uapi/domestic-futureoption/.../inquire-price`(선물)가 **같은 칸에 섞였다**
    (2026-10-02 실측 — 경로 17개 중 마지막 조각이 겹치는 것 **하나**. 구역을
    붙이면 **17개가 다 갈린다**). 섞이면 **하한이 두 API 의 평균**이 된다.

    ⚠️ `CLAUDE.md` 의 예산 몫 세는 명령(`awk -F/ '{print $NF}'`)도 같은 자리에서
    둘을 합친다 — 그쪽은 문서 레인이 본다.
    """
    seg = [x for x in (path or "").split("/") if x]
    if len(seg) >= 3:
        return seg[1] + "/" + seg[-1]
    # 조각이 둘뿐이면 구역과 마지막이 같은 것을 가리켜 `over/over` 가 된다.
    return seg[-1] if seg else "?"


def _resp_note(path, resp_ms, wait_ms, yield_ms=0.0):
    """성공한 왕복 하나를 적는다. 실패는 안 적는다 — 하한은 성공 응답으로 잰다.

    `wait_ms` 는 **줄에 선 시간**, `yield_ms` 는 **일부러 비켜선 시간**(미리받기 ·
    ⓒ 낮음)이다. 섞이면 5분봉 대기 p95 가 2.15초로 나왔다 — 실제 줄은 0.15초쯤이고
    2.0초는 미리받기가 화면에 비켜선 것이었다(2026-10-02 qa 실측 · 개발2 코드 확인).
    """
    seg = _resp_key(path)
    dq = _resp_times.get(seg)
    if dq is None:
        with _resp_lock:
            dq = _resp_times.get(seg)
            if dq is None:
                dq = _resp_times[seg] = collections.deque(maxlen=RESP_SAMPLES)
    # `deque(maxlen=…)` 의 `append` 는 원자적이라 여기서는 자물쇠가 필요 없다.
    dq.append((time.time(), resp_ms, wait_ms, yield_ms))


def _pct(vals, p):
    """백분위. **표본이 없으면 `0` 이 아니라 `None` 을 낸다** —
    「없음」 을 `0` 으로 내면 「빠르다」 로 읽힌다 (CLAUDE.md).

    ⚠️ **`round()` 로 자리를 고르지 않는다.** 파이썬의 `round` 는 .5 를
    짝수로 보내서(`round(49.5) == 50`) **표본 수가 짝수냐 홀수냐에 따라 답이
    달라진다** — 1~100 의 p50 이 51 로 나왔다 (2026-10-02 시험에서 걸렸다).
    위로 올리는 nearest-rank 하나로 고정한다.
    """
    if not vals:
        return None
    v = sorted(vals)
    idx = -(-int(round(p * len(v) * 1000)) // 1000) - 1      # ceil(p*n) - 1
    return round(v[min(max(idx, 0), len(v) - 1)], 1)


def resp_stats():
    """경로별 응답 시간. **못 쟀으면 `None`** 이고 `n` 만 0 이다."""
    out = {}
    now = time.time()
    for seg, dq in list(_resp_times.items()):
        rows = list(dq)                      # 복사해서 센다 — 도는 중에 늘어난다
        if not rows:
            continue
        resp = [r[1] for r in rows]
        wait = [r[2] for r in rows]
        yld = [r[3] for r in rows]
        out[seg] = {
            "n": len(rows),
            "p50": _pct(resp, 0.50),
            "p95": _pct(resp, 0.95),
            "max": round(max(resp), 1),
            "waitP50": _pct(wait, 0.50),
            "waitP95": _pct(wait, 0.95),
            # 일부러 비켜선 시간 — 줄(`wait`)과 따로 낸다
            "yieldP50": _pct(yld, 0.50),
            "yieldP95": _pct(yld, 0.95),
            # **표본이 얼마나 오래된 것인지 함께 낸다.** 창을 숫자로 박지 않으므로
            # 읽는 쪽이 이것으로 「무엇을 본 값인지」 를 안다.
            "spanSec": round(now - rows[0][0], 1),
        }
    return out
# 넘겨받은 KIS 경로(`_resp_key` 모양) → 그 경로를 부르는 화면 API 의 **TTL 상수 이름.**
# **값을 적지 않는다** — 부를 때 `globals()` 로 읽으므로 `--slow` 가 바꾼 값도
# 그대로 따라온다. 표에 없는 경로(종목 차트 둘 등)는 `PRICE_CACHE_TTL` 이다.
# 이름이 틀리면 조용히 기본값으로 떨어지지 않게 `stats` 의 `relayTtl` 에
# **`None`** 으로 드러난다.
RELAY_TTL_NAMES = {
    "domestic-stock/inquire-price": "PRICE_CACHE_TTL",
    "domestic-stock/intstock-multprice": "MULTI_CACHE_TTL",
    "domestic-stock/inquire-index-price": "INDEX_TTL",
    "domestic-stock/inquire-daily-indexchartprice": "INDEX_CHART_TTL",
    "domestic-stock/inquire-time-indexchartprice": "INDEX_MINUTE_TTL",
    "domestic-futureoption/inquire-price": "FUTURES_TTL",
    "overseas-price/inquire-daily-chartprice": "OVERSEAS_TTL",
    "domestic-stock/inquire-index-category-price": "SECTOR_TTL",
    "domestic-stock/fluctuation": "MOVERS_TTL",
    "domestic-stock/inquire-investor-daily-by-market": "INVESTOR_FLOW_TTL",
    "domestic-stock/inquire-investor": "INVESTOR_TTL",
    "domestic-stock/investor-trend-estimate": "INVESTOR_EST_TTL",
    "domestic-stock/inquire-member": "INVESTOR_MEMBER_TTL",
    "domestic-stock/foreign-institution-total": "INVESTOR_TOP_TTL",
    "domestic-stock/inquire-ccnl": "TICKS_TTL",
    "domestic-stock/inquire-asking-price-exp-ccn": "ASKING_TTL",
    # 재무 다섯 (2026-10-02 · 모달 투자 지표 칸 재무 카드) — 분기 자료라 한 수명
    "domestic-stock/income-statement": "FINANCE_TTL",
    "domestic-stock/balance-sheet": "FINANCE_TTL",
    "domestic-stock/financial-ratio": "FINANCE_TTL",
    "domestic-stock/profit-ratio": "FINANCE_TTL",
    "domestic-stock/growth-ratio": "FINANCE_TTL",
}


def _relay_ttl(path):
    """넘겨받은 경로의 캐시 수명(초). 표에 없거나 이름이 틀리면 `PRICE_CACHE_TTL`."""
    name = RELAY_TTL_NAMES.get(_resp_key(path), "PRICE_CACHE_TTL")
    if name == "PRICE_CACHE_TTL":
        return _cache_ttl(None)          # 남는 예산이면 당겨진 값 (2026-10-15 · ㉢)
    v = globals().get(name)
    return v if isinstance(v, (int, float)) else _cache_ttl(None)


def relay_ttl_table():
    """`stats` 용 — 경로별로 지금 도는 값. **이름이 틀린 것은 `None`** 이다."""
    out = {}
    for k, name in RELAY_TTL_NAMES.items():
        v = globals().get(name)
        out[k] = v if isinstance(v, (int, float)) else None
    return out


# ── 주기 정책 (2026-10-02 · 서버리소스 2단계 ⓐ) ──────────────────
#
# **예산 하나에서 경로별 주기를 계산해 낸다** — 화면이 주기를 박지 않고 이것을 받는다
# (「캐시·주기·한도 값을 화면에 박지 않는다」).
#
#     하한     = max(그리는 시간 × 2, 응답 시간) + 잠 깨는 시간
#     실효주기 = max(TTL, 하한) + 응답 시간            응답 시간은 p95
#
# **못 쟀으면 `None`** 이다 — `0` 으로 내면 「빠르다」 로 읽힌다. 그리는 시간(`drawMs`)은
# 화면 몫이라 서버는 모른다. 화면이 `?drawMs=` 로 실어 보내면 하한에 넣고, 없으면 뺀다.
#
# **주소가 `/api/kis/policy` 인 이유** — 처음 안은 `/api/policy` 였는데 이 서버는
# `/api/kis/` 아래로만 길을 나눈다(창구 판단 2026-10-02).
_wake_ms = None
_wake_lock = threading.Lock()      # 첫 요청 둘이 겹쳐도 한 번만 잰다 (창구 검수)


def _measure_wake_ms(n=5, ask_ms=10.0):
    """`time.sleep` 이 요청보다 얼마나 늦게 깨는지(ms 중앙값). 처음 한 번만 잰다 —
    2026-10-02 실측으로 10ms 를 자면 49ms 에 깼다(이 기계)."""
    global _wake_ms
    with _wake_lock:
        if _wake_ms is not None:
            return _wake_ms
        over = []
        for _ in range(n):
            t0 = time.perf_counter()
            time.sleep(ask_ms / 1000.0)
            over.append((time.perf_counter() - t0) * 1000.0 - ask_ms)
        over.sort()
        _wake_ms = round(over[len(over) // 2], 1)
    return _wake_ms


def policy_values(draw_ms=None):
    """경로별 TTL · 응답 시간 · 하한 · 실효주기. 못 쟀으면 그 칸이 `None`."""
    wake = _measure_wake_ms()
    resp = resp_stats()
    routes = {}
    for key, ttl in relay_ttl_table().items():
        r = (resp.get(key) or {}).get("p95")
        if r is None or ttl is None:
            routes[key] = {"ttlSec": ttl, "respMs": r, "floorMs": None, "effectiveMs": None}
            continue
        base = max(draw_ms * 2.0, r) if draw_ms is not None else r
        floor = base + wake
        routes[key] = {"ttlSec": ttl, "respMs": r, "floorMs": round(floor, 1),
                       "effectiveMs": round(max(ttl * 1000.0, floor) + r, 1)}
    return {"budgetPerSec": KIS_CALLS_PER_SEC, "wakeMs": wake, "drawMs": draw_ms,
            "routes": routes}


# ── 롱폴링 입구 (2026-10-02 · 서버리소스 2단계 ⓓ) ── **기본 꺼짐**
#
# 화면이 같은 값을 몇 초마다 다시 묻는 대신, **값이 바뀔 때까지 서버가 쥐고 있다가**
# 바뀌면 바로 돌려준다.
#
#     GET /api/kis/poll?u=<안쪽 /api/kis/… 주소>&h=<지난 응답의 해시>&hold=<초>
#
# 서버는 안쪽 주소를 **자기 포트로 다시 부르고**(그래서 캐시·예산을 그대로 탄다 —
# KIS 를 더 부르지 않는다) 응답 해시가 `h` 와 다르면 바로 내고, 같으면 `LONGPOLL_STEP_SEC`
# 마다 다시 보다가 `hold` 가 지나면 `changed:false` 로 낸다.
#
# **켜는 스위치는 `KJC_LONGPOLL=1`** — 안 켠 서버에는 이 자리가 없다(404). 켜기는
# 따로 지시를 받는다(「켜기」). **연결 하나가 스레드 하나를 쥔다**(2026-10-02 실측 —
# 연결당 RSS 74KB). 그래서 `LONGPOLL_MAX_ACTIVE` 를 넘으면 쥐지 않고 바로 낸다.
#
# **쥐는 상한은 넘기기 timeout(15초)보다 짧다** — 8764 가 넘겨받아 쥐면 16초에서
# 넘기기가 먼저 끊겼다(2026-10-02 실측 · 14.5초까지 ok).
LONGPOLL_ON = (os.environ.get("KJC_LONGPOLL") or "").strip().lower() in ("1", "true", "yes", "on")
LONGPOLL_MAX_HOLD = 12.0
LONGPOLL_STEP_SEC = 1.0

# 응답 줄이기 (2026-11-03 · `Handler._send_body`) — 이보다 작은 본문은 그대로 · 수준 5 는 138KB 를 1ms 대에 12KB 대로
GZIP_MIN = 1024
GZIP_LEVEL = 5
LONGPOLL_MAX_ACTIVE = 32
_lp_lock = threading.Lock()
_lp_stat = {"active": 0, "total": 0, "changed": 0, "busy": 0}


def _lp_inner(u):
    """안쪽 주소를 자기 포트로 부른다 → (상태코드, 본문 bytes)."""
    url = "http://127.0.0.1:%d%s" % (RUN_PORT, u)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


LONGPOLL_MAX_URLS = 32     # 한 연결이 묶어 볼 수 있는 주소 수 — 2026-11-06 12 → 32(재권님 「응 늘려」 · 홈 15 · 모달 열면 24 가 400 으로 탭 통째 폴백 · 24개 한 바퀴 안쪽 읽기 약 70ms · KIS 는 안 는다)

# **지켜볼 수 있는 주소의 접두** (2026-10-02 · 재권님 「화면은 서버가 알려준다」 —
# 보드 저장본 · 정적 JSON · 뉴스도 화면이 주기로 다시 묻지 않게). 화면은 이 목록을
# `stats.longpollPrefixes` 로 받아, 서버가 안 받는 주소 하나 때문에 묶음 전체가
# 폴백으로 떨어지지 않게 가른다(개발과 계약).
#
# **KIS 밖 넷(공시 · 뉴스 · 보드 · 정적)은 예산 계산에 안 넣는다** — 안쪽 호출이 그 라우트의
# 캐시를 그대로 타므로(뉴스 `NEWS_TTL` · `MOVES_TTL`) 롱폴이 바깥 호출을 늘리지 않는다.
# "/api/nxt/" — 수급(theme_flow.flow)이 5분마다 바뀌어 화면이 지켜본다(2026-10-27). DB · 네이버 캐시만 읽어 KIS 를 더 안 부른다
# "/api/alerts/" — 그날 VI · 급등 목록(2026-11-06 · DB 한 줄만 읽어 KIS 를 안 부른다)
LONGPOLL_PREFIXES = ("/api/kis/", "/api/dart/", "/api/news/", "/api/board/doc/", "/holdings/data/", "/api/nxt/",
                     "/api/alerts/")


def _lp_url_ok(u):
    """롱폴로 지켜봐도 되는 주소인가. 아니면 그 이유(한국어), 되면 `None`."""
    path = urllib.parse.urlparse(u).path
    if ".." in u or not any(path.startswith(p) for p in LONGPOLL_PREFIXES):
        return "u 는 %s 중 하나로 시작해야 합니다." % " · ".join(LONGPOLL_PREFIXES)
    if path.startswith("/api/kis/"):
        inner = path[len("/api/kis/"):].strip("/")
        # 자기 자신(poll)은 고리가 되고 넘겨받는 자리(relay)는 넘기기 전용이다
        if not inner or inner in ("poll", RELAY_ROUTE):
            return "poll · relay 는 지켜볼 수 없습니다."
    # **`/api/dart/poll` 은 안 된다** — 부를 때마다 OpenDART 에 바로 간다(캐시 없음 · 하루 한도).
    # 롱폴이 1초마다 부르면 그날 한도(020)를 금방 쓴다.
    if path.rstrip("/") == "/api/dart/poll":
        return "/api/dart/poll 은 지켜볼 수 없습니다(OpenDART 를 바로 부릅니다)."
    if path.startswith("/holdings/data/"):
        # **`.json` 만 · 저장본 폴더(docs/)는 안 된다** — 정적 막기(`_DENY_REL`)와 같은 자리
        if not path.endswith(".json") or path.startswith("/" + _DENY_REL[0]):
            return "/holdings/data/ 는 .json 만 · docs/ 는 안 됩니다."
    return None


def _lp_hash(body):
    """**`meta` 를 뺀 본문**으로 해시를 만든다 — 값이 안 바뀌었는데 「바뀜」 이 안 나게.

    `/chart` 의 `meta` 는 새로 받은 직후 `{fetched: N, source: 'KIS'}`, 다음부터
    `{fetched: 0, source: 'DB'}` 라 봉이 같아도 해시가 두 번 바뀌었다(2026-10-02 · 개발 실측).
    `meta` 는 「언제 · 어디서 받았나」 를 싣는 자리라 값이 아니다. JSON 이 아니면 그대로 해시한다.
    """
    try:
        obj = json.loads(body.decode("utf-8"))
    except ValueError:
        return hashlib.sha1(body).hexdigest()[:16], None
    key = obj
    if isinstance(obj, dict) and "meta" in obj:
        key = {k: v for k, v in obj.items() if k != "meta"}
    raw = json.dumps(key, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16], obj


def _lp_step(u):
    """그 주소를 다시 볼 간격. **봉은 그 기간의 `fresh_sec`** — 그 전에는 서버가 새로 안 받으므로
    더 자주 봐도 같은 값을 읽을 뿐이다(KIS 수는 `fresh_sec` 이 정한다 · 이것은 안쪽 부하만 줄인다).
    나머지는 `LONGPOLL_STEP_SEC`."""
    pr = urllib.parse.urlparse(u)
    if pr.path.rstrip("/") == "/api/kis/chart":
        per = (urllib.parse.parse_qs(pr.query).get("period") or ["D"])[0]
        f = (PERIODS.get(per) or {}).get("fresh_sec")
        if isinstance(f, (int, float)):
            return max(LONGPOLL_STEP_SEC, float(f))
    return LONGPOLL_STEP_SEC


def _lp_item(u, code, body, h):
    hh, obj = _lp_hash(body)
    it = {"u": u, "hash": hh, "changed": hh != h, "status": code}
    if hh != h or code != 200:
        it["body"] = obj
    return it


def longpoll(us, hs, hold):
    """주소 여럿(`us`) 중 **하나라도** 바뀔 때까지(또는 `hold` 초) 기다린다.

    **한 화면 = 롱폴 하나**로 묶는다 — 브라우저가 HTTP/1.1 에서 한 주소당 동시 연결을
    6개까지만 열어, 화면이 주소마다 롱폴을 쥐면 나머지 요청이 막힌다(2026-10-02 · 개발과 계약).
    응답 `items` 에는 **전부** 담기고, 안 바뀐 것은 `body` 없이 `changed:false` 다.
    주소가 하나면 최상위에도 그 칸의 값을 그대로 둔다(첫 모양과 맞춘다).
    """
    if isinstance(us, str):
        us, hs = [us], [hs]
    hs = list(hs) + [""] * (len(us) - len(hs))          # 모자란 해시는 「처음 받기」
    with _lp_lock:
        _lp_stat["total"] += 1
        busy = _lp_stat["active"] >= LONGPOLL_MAX_ACTIVE
        if busy:
            _lp_stat["busy"] += 1
        else:
            _lp_stat["active"] += 1
    try:
        now = time.monotonic()
        deadline = now + (0.0 if busy else hold)
        items = [None] * len(us)
        due = [now] * len(us)               # 주소마다 다음에 볼 시각 — 처음엔 다 본다
        while True:
            now = time.monotonic()
            for i, (u, h) in enumerate(zip(us, hs)):
                if due[i] <= now:
                    items[i] = _lp_item(u, *_lp_inner(u), h)
                    due[i] = now + _lp_step(u)
            hit = any(it["changed"] or it["status"] != 200 for it in items)
            if hit or time.monotonic() >= deadline:
                break
            wake = min(min(due), deadline)
            time.sleep(max(0.0, wake - time.monotonic()))
        changed = any(it["changed"] for it in items)
        if changed:
            _lp_stat["changed"] += 1
        out = {"ok": all(it["status"] == 200 for it in items), "changed": changed,
               "busy": busy, "items": items}
        if len(items) == 1:
            out.update({k: v for k, v in items[0].items() if k != "u"})
        return out
    finally:
        if not busy:
            with _lp_lock:
                _lp_stat["active"] -= 1

RELAY_CACHE_MAX = 2000             # 키에 `params` 가 들어가 수가 늘 수 있다


def _relay_sweep(now):
    """만료된 것을 치운다. **상한을 넘을 때만** 돈다 — 매번 훑으면 비싸다.

    `ThreadingHTTPServer` 라 동시에 들어온다. **항목을 복사해서** 돌고
    `pop(k, None)` 으로 지운다 — 도는 중에 남이 지워도 터지지 않는다.
    """
    for k, v in list(_relay_cache.items()):
        if now - v[0] >= _relay_ttl(k[0]):       # k[0] 은 KIS 경로
            _relay_cache.pop(k, None)
    if len(_relay_cache) > RELAY_CACHE_MAX:
        rows = sorted(list(_relay_cache.items()), key=lambda kv: kv[1][0])
        for k, _v in rows[:len(rows) - RELAY_CACHE_MAX]:
            _relay_cache.pop(k, None)


def _resolve_upstream(raw):
    """상류 주소를 가린다 — 없거나 **자기 자신을 가리키면 `None`**.

    자기 포트를 가리키면 **자기를 부르는 고리**가 된다. `RUN_PORT` 는
    `main()` 이 정하므로 **모듈을 읽을 때가 아니라 부를 때** 본다.
    **KIS 와 보드가 함께 쓴다** — 같은 판별을 두 곳에 두지 않는다.
    """
    if not raw:
        return None
    try:
        u = urllib.parse.urlparse(raw)
    except ValueError:
        return None
    if not u.scheme or not u.hostname:
        return None
    if u.port and RUN_PORT and u.port == RUN_PORT:
        return None
    return raw


UPSTREAM_TIMEOUT = 60             # 상류(8765)로 넘긴 요청을 기다리는 초 — 경제지표 · 시장지표 · 그 밖 넘김이 함께 쓴다(개념정의 검수 11-05)

def upstream_base():
    """KIS 를 넘길 상류."""
    return _resolve_upstream(KIS_UPSTREAM_RAW)


def board_upstream_base():
    """보드를 넘길 상류."""
    return _resolve_upstream(BOARD_UPSTREAM_RAW)


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
    문자열이 나오고, 그 뒤 r.get(...) 에서 터진다. 그때의 워커에서는 같은 자리가
    "object is not iterable" 로 500 이 됐다 (2026-09-15).
    배열이 아니면 빈 배열로 친다.
    """
    v = (data or {}).get(key)
    return v if isinstance(v, list) else []


# ── 차트 셋은 화면 API 째로 넘긴다 (2026-10-02 · 서버리소스 2단계 ⓑ-2) ──
#
# 날 `/uapi/` 만 넘기면 **8765 가 KIS 를 대신 부르고 자기 DB 에는 안 쓴다**
# (`save_candles` 는 부른 쪽 함수 안에 있다). 그래서 읽기 전용 서버가 차트를
# 열 때마다 같은 봉을 다시 받았다 — 한 번 여는 데 19건(개발3 실증).
# 화면 API 째로 넘기면 **8765 가 받아 자기 DB 에 쌓고** 다음 사람은 DB 에서 읽는다.
#
# 고른 기준은 「`save_candles` 에 닿는 라우트」 다 — 이름을 고른 것이 아니라
# 그 함수를 부르는 라우트를 셌다(2026-10-02 · 라우트 33개 중 셋).
#
# **폴백은 둔다** — 읽기라 어느 쪽이 받아도 값이 같다. 보드(쓰는 곳 · 폴백 없음)와
# 다른 자리다. `4xx` 는 상류가 제대로 답한 것이라 **그대로 내려보낸다.**
HIGH_RELAY_ROUTES = ("chart", "index-candles", "index-minutes",
                     "flow-today")   # 당일 수급 — 쌓는 곳이 8765 하나라 「고른 종목」 표시가 거기 닿아야 한다(2026-10-27)


def _valid_ymd(ymd):
    """8자리여도 없는 날짜(20261399)는 거른다 — 400 으로 내려고."""
    try:
        datetime.strptime(ymd, "%Y%m%d")
        return True
    except ValueError:
        return False


class _UpstreamDown(Exception):
    """상류가 안 떠 있거나 터졌다 — **직접 부르는 쪽으로 내려간다.**"""


def _kis_via_upstream(base, path, params, tr_id):
    """KIS 를 상류 서버가 대신 부르게 한다.

    **`get_token` 도 `_rate_limit` 도 타지 않는다.** 둘 다 상류가 한다 —
    양쪽에서 기다리면 `minIntervalSec`(2026-10-01 실측 **0.1초**)만큼
    **더 느려진다.** 루프백 왕복은 **중앙 1.6ms** 라 그에 비해 무시할 수 있다.
    """
    url = base + "/api/kis/" + RELAY_ROUTE + "?" + urllib.parse.urlencode({
        "path": path,
        "tr_id": tr_id,
        "params": json.dumps(params or {}, ensure_ascii=False),
    })
    try:
        req = urllib.request.Request(url)
        if SLOW:
            req.add_header(PRIO_HEADER, "low")      # ⓒ 외부접속에 비켜선다
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = scrub(e.read().decode("utf-8", "replace"))[:300]
        # **`404` 는 「상류가 거절한 것」 이 아니라 「받을 자리가 없는 것」 이다.**
        # 보내는 쪽만 켜지고 받는 쪽(`KJC_KIS_UPSTREAM_SERVE`)이 안 켜진
        # 상태가 바로 이것이고, 그때 폴백하지 않으면 **그 서버의 KIS 가
        # 통째로 죽는다.** 설치 순서가 어긋나는 순간이 그 자리다 —
        # 그래서 `5xx` 와 같이 **직접 부르는 쪽으로 내려간다.**
        if e.code >= 500 or e.code == 404:
            raise _UpstreamDown("상류 %s: %s" % (e.code, detail))
        # **그 밖 4xx 는 폴백하지 않는다.** 상류가 제대로 답한 것이라,
        # 직접 부르면 **KIS 를 두 번 쓴다.**
        raise RuntimeError("상류가 거절했습니다 (HTTP %s): %s" % (e.code, detail))
    except (urllib.error.URLError, OSError) as e:
        raise _UpstreamDown(safe_message(e))
    if not isinstance(body, dict) or not body.get("ok"):
        raise RuntimeError("상류 응답이 이상합니다: %s" % scrub(str(body))[:200])
    if isinstance(body.get("fill"), (int, float)):      # 상류의 남는 예산 배수 (㉢)
        _fill_remote["factor"], _fill_remote["at"] = float(body["fill"]), time.time()
    return body.get("data")


KIS_OVER_RETRY = 10          # 한도 초과(EGW00201) 거절을 1초씩 쉬며 다시 보내는 최대 횟수 (2026-10-27 재권님 「대기했다가 가져와야지」)
_over_giveup = 0             # 그만큼 다시 보내도 못 받은 수 — stats 의 overrunGiveUps


def _gate_release():
    e = getattr(_gate_tl, "entry", None)
    if e is not None and e[1] is None:
        e[1] = time.monotonic()


def _over_gave_up():
    global _over_giveup
    _over_giveup += 1
    sys.stderr.write("  [KIS] %s 한도 초과 거절이 %d번 이어져 이번 것은 못 받음 — 누적 %d건\n"
                     % (_stamp(), KIS_OVER_RETRY + 1, _over_giveup))


# ── KIS 가 살아 있나 (2026-11-09 · 이벤트 대응 ⑦ · 재권님 「응」) ──
# 실제로 KIS 로 나간 호출의 성공 · 실패만 센다(상류로 넘긴 것 · 캐시는 안 센다 — 그 서버가 센다).
# **실패는 길이 끊긴 것만** — 네트워크 · 시간 초과 · HTTP 5xx · 한도 초과를 끝내 못 받은 것. 「없는 종목」 같은 KIS 업무 오류(rt_cd ≠ 0)는
# KIS 가 응답한 것이라 장애로 안 센다. market_event.py 가 이 값을 1분 바퀴로 읽어 「3분 이어짐」 이면 맨 위 띠를 띄운다
_kis_health = {"lastOk": None, "lastFail": None, "failSince": None, "lastError": None}


def _kis_ok():
    _kis_health.update(lastOk=time.time(), failSince=None)


def _kis_fail(msg):
    now = time.time()
    if _kis_health["failSince"] is None:
        _kis_health["failSince"] = now
    _kis_health.update(lastFail=now, lastError=msg)


def kis_health():
    """지금 KIS 길 — 마지막 성공 · 실패 · 실패가 이어진 처음 · 최근 60초 한도 초과 수."""
    now = time.time()
    return dict(_kis_health, overruns60s=sum(1 for t in list(_over_times) if now - t < OVER_WINDOW))


def kis_get(cfg, path, params, tr_id, _retry=1, _over=0):
    # ── 상류가 있으면 넘긴다 (2026-10-01) ──
    _base = upstream_base()
    if _base:
        try:
            data = _kis_via_upstream(_base, path, params, tr_id)
            _up_stat["calls"] += 1
            return data
        except _UpstreamDown as e:
            # **폴백** — 상류가 안 떠 있으면 직접 부른다. 화면이 멈추는
            # 것보다 낫다. 몇 번 떨어졌는지는 `stats` 가 낸다.
            _up_stat["fallbacks"] += 1
            _up_stat["lastError"] = safe_message(e)
    global _keys_active, _key2_down_until
    # **앱키 둘** (2026-10-06 · 위 주석) — 둘째가 있고 쉬는 중이 아니면 줄에 둘이 선다.
    _k2 = cfg.get("_key2")
    _keys = [cfg] + ([_k2] if _k2 and time.time() >= _key2_down_until else [])
    _keys_active = len(_keys)
    if len(_keys) == 1:
        get_token(cfg)               # 하나일 때는 지금처럼 줄 서기 전에 받아 둔다
    _t_wait0 = time.time()
    _slot = _rate_limit(path, len(_keys))
    # **`get_token` 보다 먼저 읽는다** — 발급하면 그 안의 `_rate_limit` 이 값을 지운다
    _yield_ms = getattr(_rl_yield, "ms", 0.0)
    _wait_ms = max(0.0, (time.time() - _t_wait0) * 1000.0 - _yield_ms)
    _kc = _keys[_slot] if _slot < len(_keys) else cfg
    try:
        token = get_token(_kc)
    except RuntimeError:
        if _kc is cfg:
            raise
        # 둘째 키 토큰을 못 받았다 — 쉬게 하고 이번 것은 첫째로 보낸다
        _key2_down_until = time.time() + KEY2_DOWN_SEC
        sys.stderr.write("  [KIS] %s 둘째 키 토큰 못 받음 — %d초 첫째 하나로\n"
                         % (_stamp(), KEY2_DOWN_SEC))
        _kc = cfg
        # **첫째 키 문을 다시 지난다** — 둘째 자리로 받은 것을 그대로 첫째로 보내면
        # 그 순간 첫째가 1초 한도를 넘는다(가짜 시험에서 1초 20건이 됐다).
        _send_gate(1)
        token = get_token(cfg)
    # **실제 KIS 호출을 여기 한 곳에서 센다** (2026-10-01).
    # 전에는 경로마다 손으로 올려 **13곳**이었고 **일부 경로만** 세었다.
    # **상류로 넘긴 것은 위에서 `return` 하므로 안 세어진다** — 맞다.
    # 재시도(`EGW00201`)는 재귀로 다시 와서 **한 번 더 센다** — 실제로 두 번 부른다.
    _stats["kis_calls"] += 1
    # [보낸 시각 · 왕복 ms · 결과] — 거절이 나면 앞뒤를 찍는다 (`_ring_dump`)
    _me = [time.time(), None, None, None, _kc.get("_slot", 0)]
    _send_ring.append(_me)
    url = HOSTS[cfg["mode"]] + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "authorization": "Bearer " + token,
        "appkey": _kc["app_key"],
        "appsecret": _kc["app_secret"],
        "tr_id": tr_id,
        "custtype": "P",
        "content-type": "application/json; charset=utf-8",
    })
    try:
        _t_resp0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
        finally:
            _gate_release()            # 응답이 왔다(또는 실패) — 이때부터 1초 동안 자리를 센다
        # **왕복만 잰다** — JSON 해석은 우리 쪽 일이라 뺀다.
        _me[2] = (time.time() - _t_resp0) * 1000.0
        _me[3] = "ok"
        _resp_note(path, _me[2], _wait_ms, _yield_ms)
        data = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        _me[2] = (time.time() - _t_resp0) * 1000.0
        _me[3] = "HTTP%s" % e.code
        detail = scrub(e.read().decode("utf-8", "replace"))[:300]
        # 초당 건수 초과(EGW00201)는 1초씩 쉬며 받을 때까지 다시 보낸다 — 최대 KIS_OVER_RETRY 번
        # (2026-10-27 재권님 「한도 초과하면 막는게 아니고 대기했다가 가져와야지」 · 전에는 한 번만 다시 시도)
        if "EGW00201" in detail:
            _me[3] = "EGW00201"
            _ring_dump(_me)
            note_overrun()                     # ㉡ 세어 두면 간격이 늘어난다
            if _over < KIS_OVER_RETRY:
                time.sleep(1.0)
                return kis_get(cfg, path, params, tr_id, _retry, _over + 1)
            _over_gave_up()
            _kis_fail("한도 초과를 끝내 못 받음")
        # **거부당한 토큰(EGW00123)은 버리고 한 번만 다시 받는다** (2026-09-22 지시).
        # 이것이 없으면 캐시가 스스로 만료될 때까지 몇십 분이고 계속 실패한다.
        if "EGW00123" in detail and _retry > 0:
            _drop_token_cache(cfg["mode"], _token_path(_kc))
            return kis_get(cfg, path, params, tr_id, _retry - 1, _over)
        if e.code >= 500:
            _kis_fail("HTTP %s" % e.code)
        raise RuntimeError("KIS 호출 실패 (HTTP %s): %s" % (e.code, detail))
    except urllib.error.URLError as e:
        _kis_fail("네트워크")
        raise RuntimeError("KIS 호출 실패 (네트워크): %s" % safe_message(e.reason))
    except (TimeoutError, ConnectionError) as e:
        _kis_fail("시간 초과 · 끊김")
        raise RuntimeError("KIS 호출 실패 (시간 초과 · 끊김): %s" % safe_message(e))

    if str(data.get("rt_cd", "0")) != "0":
        if data.get("msg_cd") == "EGW00201":
            _me[3] = "EGW00201"
            _ring_dump(_me)
            note_overrun()                     # ㉡
            if _over < KIS_OVER_RETRY:
                time.sleep(1.0)
                return kis_get(cfg, path, params, tr_id, _retry, _over + 1)
            _over_gave_up()
            _kis_fail("한도 초과를 끝내 못 받음")
        if data.get("msg_cd") == "EGW00123" and _retry > 0:
            _drop_token_cache(cfg["mode"], _token_path(_kc))
            return kis_get(cfg, path, params, tr_id, _retry - 1, _over)
        _kis_ok()                              # KIS 가 응답은 했다 — 업무 오류는 장애가 아니다
        raise RuntimeError("KIS 오류: %s (%s)" % (data.get("msg1", "알 수 없음"), data.get("msg_cd", "")))
    _kis_ok()
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
    ("3003", "KOSDAQ150"),   # 2026-10-06 — KIS 지수 마스터 idxcode.mst 의 KSQ150 (개발1 실측). 맨 끝에 둔다 — 화면이 순서로 읽는 자리가 있다
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

# KIS 에 없는 나라 지수 — 네이버 해외 지수 일봉에서 받는다(2026-11-10 재권님 「받아오는게 있으면 이걸 홀딩스에서 받아오게 하고
# 인사이트에서는 그 값을 가져다 쓰는방향으로 해줘」 · naver.foreign_index_daily). 홀딩스 「국외」 갈래 띠 · 큰 차트가 쓰고,
# Insight 는 이 서버 주소(/api/kis/indices · /api/kis/index-daily)를 가져다 쓴다(「두 구역이 같은 값을 쓰면」 1번).
# 열쇠 · 네이버 기호 · 이름 · 단위. 지금 값 = 마지막 일봉 종가 · 등락 = 그 앞 종가 대비(장중이면 그 나라 장중 값).
NAVER_INDEX_DEFS = [
    ("N225",   ".N225",  "일본 닛케이225", "pt"),
    ("SSEC",   ".SSEC",  "중국 상해종합",  "pt"),
    ("TWII",   ".TWII",  "대만 가권",     "pt"),
    ("SENSEX", ".BSESN", "인도 SENSEX",  "pt"),
    ("DAX",    ".GDAXI", "독일 DAX",     "pt"),
]
NAVER_INDEX_TTL = 300      # 네이버 해외 지수 일봉을 들고 있는 초 — 띠 · 큰 차트가 같은 것을 쓴다
_nvx_cache = {}


def _nvx_bars(key):
    """네이버 해외 지수 일봉(들고 있는 것). 못 받으면 RuntimeError."""
    hit = _nvx_cache.get(key)
    if hit and time.time() - hit[0] < NAVER_INDEX_TTL:
        return hit[1]
    sym = {d[0]: d[1] for d in NAVER_INDEX_DEFS}[key]
    try:
        bars = naver.foreign_index_daily(sym)
    except Exception as e:
        raise RuntimeError("네이버 해외 지수 %s: %s" % (key, safe_message(e, 100)))
    if not bars:
        raise RuntimeError("네이버 해외 지수 %s: 빈 응답" % key)
    _nvx_cache[key] = (time.time(), bars)
    return bars


def fetch_naver_indices():
    """띠에 넣을 줄 — fetch_overseas 와 같은 모양(source 만 「네이버」). 하나가 실패해도 나머지는 낸다."""
    rows, errors = [], {}
    for key, _sym, name, unit in NAVER_INDEX_DEFS:
        try:
            b = _nvx_bars(key)
            last, prev = b[-1], (b[-2] if len(b) > 1 else None)
            chg = round(last["close"] - prev["close"], 2) if prev else None
            rows.append({"code": key, "name": name, "unit": unit, "value": last["close"], "asOf": last["date"],
                         "market": "overseas", "change": chg,
                         "changePct": round(chg / prev["close"] * 100, 2) if prev and prev["close"] else None,
                         "series": [x["close"] for x in b][-60:], "source": "네이버"})
        except RuntimeError as e:
            errors[key] = safe_message(e)
    return rows, errors
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


def floor_to_span(d, period):
    """묻는 시작 날짜를 **그 구간의 첫날로 내린다.**

    ⚠️ **구간 중간부터 물으면 KIS 가 「그 날짜부터의 누적」 을 준다**
    (2026-09-29 실측). 재권님이 코스피 1993년 년봉에서 찾으셨다.

        물은 것                      돌아온 1993년 봉
        1993-11-xx ~ 오늘   시 757.08  고 880.35  저 **751.21**  종 866.18
        1990-01-01 ~ 1996   시 685.51  고 880.35  저 **602.30**  종 866.18
                                                       └ 진짜 1993년 저가

    앞엣것은 **11월부터의 누적**이라 그 해 저가가 빠진다. 그런데 **저장될
    때는 `ts` 가 같은 `19931228`** 이라 구분이 안 되고, 화면에는 「1993년
    저가가 751」 로 나온다.

    `INDEX_SPAN["Y"]` 가 12000일(약 33년)이라 `오늘 - 33년` 이 **1993년
    11월**에 떨어진 것이 그 사달이었다. **기간을 늘리는 것은 답이 아니다** —
    그 경계가 어느 해 중간으로 옮겨갈 뿐이다.

    **년·월·주봉에만 뜻이 있다.** 일봉과 분봉은 하루가 곧 구간이다.
    """
    if period == "Y":
        return d.replace(month=1, day=1)
    if period == "M":
        return d.replace(day=1)
    if period == "W":
        return d - timedelta(days=d.weekday())
    return d


def _index_bars_from_kis(cfg, code, period, date_from, date_to):
    """한 구간을 받아 온다. 최대 INDEX_PAGE 개."""
    date_from = floor_to_span(date_from, period)
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


# 데일리 「지수 대비 강한 종목」 — (지수 구성 코드 · 이름 · 기준 지수) · 2026-10-22 재권님 「응」
DAILY_STRONG_MARKETS = [("KPI200", "코스피", "0001"), ("KQI150", "코스닥", "1001")]
DAILY_STRONG_DAYS = 45       # 달력 날 — 한 달(20거래일)을 덮고 휴장을 감안


DAILY_CLOSE_MIN = 15 * 60 + 40      # 정규장(15:30) 마감 봉이 확정되는 때(분) — 데일리 강한 종목이 이 뒤면 오늘 봉을 넣는다


def _daily_strong(cfg):
    """구성 종목 일봉 · 지수 일봉을 날짜와 함께 모아 `daily.build_strong` 에 넘길 모양으로.

    **종목마다 KIS 한 번**(일봉 한 번에 100개 · 45일이면 한 번에 온다) — 구성 종목 수만큼 부른다.
    오늘 봉은 정규장이 끝난 뒤(`DAILY_CLOSE_MIN` · 16:00 데일리)에만 넣는다 — 장 전 · 장중 봉은 뺀다(2026-11-07 전에는 07:30 이라 늘 뺐다). 구성 목록은 `dart.index_members_map()` 그대로 — 그쪽이 하루 한 번 새로 받는다.
    """
    now = datetime.now(KST)
    today = now.strftime("%Y%m%d")
    if now.hour * 60 + now.minute >= DAILY_CLOSE_MIN:
        today = (now + timedelta(days=1)).strftime("%Y%m%d")     # 마감 뒤 — 오늘 봉까지 센다(아래 `< today`)
    dfrom = (now - timedelta(days=DAILY_STRONG_DAYS)).strftime("%Y%m%d")
    names = {}
    try:
        with dart._db_lock, dart.db_conn() as conn:
            for r in conn.execute("SELECT stock_code, index_code, name FROM index_members"):
                names.setdefault(r["index_code"], []).append((r["stock_code"], r["name"]))
    except Exception:
        names = {}
    out = []
    for icode, label, num in DAILY_STRONG_MARKETS:
        try:
            ib = [b for b in fetch_index_candles(cfg, num, "D") if str(b["ts"])[:8] < today]
        except Exception:
            ib = []
        index = [(str(b["ts"])[:8], float(b["close"])) for b in ib if b.get("close")]
        stocks = []
        for code, name in names.get(icode, []):
            try:
                # KRX(J) 종가 — 지수 봉이 KRX 종가라 같은 잣대로 견준다(통합 UN 종가는 넥스트레이드가 섞여 어긋남 · qa 10-22)
                bars = _bars_once(cfg, code, "D", dfrom, today, "J")
            except Exception:
                continue
            stocks.append({"code": code, "name": name,
                           "bars": [(str(b["ts"])[:8], float(b["close"])) for b in bars
                                    if b.get("close") and str(b["ts"])[:8] < today]})
        out.append({"label": label, "index": index, "stocks": stocks})
    return out


def _daily_indices(cfg):
    """데일리(07:30)가 담을 지수 — 화면과 같은 `fetch_indices_all` 에 **전일 등락**을 채운다.

    **07:30 은 장 전이라** KIS 지수 시세가 「전일 종가 · 등락 0」 을 준다 — 저장본 실측 10-01 · 10-02 ·
    10-06 국내 넷 모두 change 0 · changePct 0 이었다(2026-10-06 재권님 「응 해줘」). 그래서 국내 넷
    (`INDEX_DEFS`)만, 등락이 0 이고 **값이 지수 일봉의 마지막 마감 종가와 같을 때** 그 앞 종가로 등락을
    채우고 `basis = "전일"` 을 붙인다(`daily.py` 가 그 줄에 「(전일)」). 값이 안 맞으면 손대지 않는다 —
    다른 날 종가끼리 견주게 된다. 일봉은 DB 를 먼저 보고 낡았으면 KIS 몇 건(`fetch_index_candles`)."""
    rows = fetch_indices_all(cfg, with_chart=False)[0]
    by_name = {n: c for c, n in INDEX_DEFS}
    today = datetime.now(KST).strftime("%Y%m%d")
    for x in rows or []:
        num = by_name.get(x.get("code"))
        if not num or x.get("change") not in (0, 0.0) or x.get("value") is None:
            continue
        try:
            bars = [b for b in fetch_index_candles(cfg, num, "D") if str(b["ts"])[:8] < today]
        except Exception:
            continue
        if len(bars) < 2 or not bars[-2]["close"]:
            continue
        last, prev = float(bars[-1]["close"]), float(bars[-2]["close"])
        if abs(last - float(x["value"])) > 0.01:
            continue
        x["change"] = round(last - prev, 2)
        x["changePct"] = round((last - prev) / prev * 100, 2)
        x["basis"] = "전일"
    return rows


# ── 지수 일봉 몇 달 — 국내 · 미국 지수를 한 주소로 (2026-11-10 · 작업우선순위 배분) ──
# 재권님이 시황분석 창에서 「미국 3지수 등락률 ↔ 코스피 · 삼성전자 · 하이닉스 날마다 표」 를 Insight 새 화면으로 정하셨고
# 서버 값이 없어 넘어왔다(「두 구역이 같은 값을 쓰면」 1번 — 바깥 값은 서버가 받고 Insight 는 가져온다) → 재권님 「응」.
#   GET /api/kis/index-daily?codes=KOSPI,SPX,NASDAQ,SOX
# 국내는 fetch_index_candles 의 일봉(DB · INDEX_KEEP) 그대로 · 미국은 KIS 해외지수 일봉(FHKST03030100) — 한 번에 100일까지라
# (2026-11-10 11:50 SPX · COMP · SOX 다 100줄 · 새 날짜 먼저) 앞쪽을 한 번 더 묻는다. 받은 것은 INDEX_DAILY_TTL 동안 들고 있다.
# 이름은 INDEX_DEFS(국내) · OVERSEAS_DEFS(해외)의 열쇠 그대로다(나스닥 종합은 NASDAQ · KIS 코드 COMP).
INDEX_DAILY_MONTHS = 6          # 내주는 기간 — 화면이 정하지 않는다(「캐시·주기·한도 값을 화면에 박지 않는다」)
INDEX_DAILY_TTL = 600           # 미국 지수 일봉을 들고 있는 초 — 장이 닫힌 낮에는 안 바뀐다 · 10분에 지수마다 KIS 2건
_idx_daily = {}


def _ovs_daily(cfg, div, code, start):
    """해외지수 일봉 start(YYYYMMDD)부터 오늘까지 — 옛것부터. 100줄씩 앞으로 물어 간다(많아야 네 번)."""
    rows, end = {}, datetime.now(KST).strftime("%Y%m%d")
    for _ in range(4):
        d = kis_get(cfg, "/uapi/overseas-price/v1/quotations/inquire-daily-chartprice",
                    {"FID_COND_MRKT_DIV_CODE": div, "FID_INPUT_ISCD": code, "FID_INPUT_DATE_1": start,
                     "FID_INPUT_DATE_2": end, "FID_PERIOD_DIV_CODE": "D"}, "FHKST03030100")
        got = [r for r in out_rows(d, "output2") if r.get("stck_bsop_date")]
        for r in got:
            close = _num(r.get("ovrs_nmix_prpr"))
            if not close:
                continue                      # 0 · 빈 줄은 못 받은 날 — 넣지 않는다
            rows[r["stck_bsop_date"]] = {"date": r["stck_bsop_date"], "open": _num(r.get("ovrs_nmix_oprc")),
                                         "high": _num(r.get("ovrs_nmix_hgpr")), "low": _num(r.get("ovrs_nmix_lwpr")),
                                         "close": close}
        first = min((r["stck_bsop_date"] for r in got), default=None)
        if len(got) < 100 or not first or first <= start:
            break
        end = (datetime.strptime(first, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
    return [rows[k] for k in sorted(rows) if k >= start]


def _stock_daily_j(cfg, code, start):
    """종목 정규장(KRX · J) 일봉 start(YYYYMMDD)부터 오늘까지 — 옛것부터. 한 번에 100줄이라 앞으로 물어 간다(많아야 네 번)."""
    rows, end = {}, datetime.now(KST).strftime("%Y%m%d")
    for _ in range(4):
        d = kis_get(cfg, "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
                    {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code, "FID_INPUT_DATE_1": start,
                     "FID_INPUT_DATE_2": end, "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"}, "FHKST03010100")
        got = [r for r in out_rows(d, "output2") if r.get("stck_bsop_date")]
        for r in got:
            close = _num(r.get("stck_clpr"), int)
            if not close:
                continue                      # 0 · 빈 줄은 못 받은 날 — 넣지 않는다
            rows[r["stck_bsop_date"]] = {"date": r["stck_bsop_date"], "open": _num(r.get("stck_oprc"), int),
                                         "high": _num(r.get("stck_hgpr"), int), "low": _num(r.get("stck_lwpr"), int),
                                         "close": close, "volume": _num(r.get("acml_vol"), int)}
        first = min((r["stck_bsop_date"] for r in got), default=None)
        if len(got) < 100 or not first or first <= start:
            break
        end = (datetime.strptime(first, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
    return [rows[k] for k in sorted(rows) if k >= start]


# ── 일봉 쌓기 — 끝난 날은 market.db 에 들고 오늘 쪽만 다시 받는다 (2026-11-10 재권님 「로딩이 느린데 오늘값을 빼고 나머지는 저장해야 할거같아」 → 안에 「응」) ──
# 전에는 INDEX_DAILY_TTL 이 지나거나 재시작하면 6개월치를 KIS 에 통째로 다시 물었다(지수 · 종목 하나에 2건 · 화면 하나에 10건 남짓 ·
# 시황분석 14:07 잼). 이제 끝난 날 봉은 daily_store 에 쌓고(쓰는 서버 8765 만), 다시 받을 때는 마지막 쌓인 날 DAILY_REFETCH_DAYS 앞부터만 묻는다.
# 읽기 전용 서버는 표를 읽기만 하고 받은 것은 메모리에 들고 있다(_daily_mem). 지수 국내는 이미 candles 표라 안 거친다.
DAILY_SQL = ("CREATE TABLE IF NOT EXISTS daily_store (kind TEXT NOT NULL, code TEXT NOT NULL, date TEXT NOT NULL, "
             "open REAL, high REAL, low REAL, close REAL, volume INTEGER, PRIMARY KEY (kind, code, date))",)
DAILY_REFETCH_DAYS = 10         # 다시 받을 때 마지막 날에서 거슬러 올라가는 날 — 늦게 고쳐진 값 · 빠진 날을 덮는다
_daily_mem = {}                 # (kind, code) → {date: bar} — 쌓지 못하는 서버의 몫 · 쓰는 서버도 표를 다시 안 읽게


def _as_int(v):
    """표에서 읽은 REAL(189900.0)을 원 단위 정수로 — _num(…, int) 은 "189900.0" 을 못 읽는다."""
    return None if v is None else int(round(float(v)))


def _daily_settled_day(kind):
    """그 시장의 오늘 날짜 — 이보다 앞선 날 봉만 끝난 것으로 쌓는다. 미국은 뉴욕 날짜(장중 봉이 그 날짜)."""
    if kind == "OVS":
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d")
    return datetime.now(KST).strftime("%Y%m%d")


def _daily_stored(kind, code, start, fetch, done=False):
    """kind · code 의 일봉 start 부터 — 쌓인 것 + 모자란 쪽만 fetch(d1) 로 받아 합친다. done 이면(끝난 월물) 쌓인 것이 있으면 안 묻는다."""
    mem = _daily_mem.setdefault((kind, code), {})
    if not mem:
        try:
            with _db_lock, db_conn() as conn:
                for r in conn.execute("SELECT date, open, high, low, close, volume FROM daily_store WHERE kind=? AND code=?", (kind, code)):
                    mem[r[0]] = {"date": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5]}
        except sqlite3.Error:
            pass                                 # 표가 아직 없다(쓰는 서버가 처음 쌓을 때 만든다) — 통째로 받는다
    have = sorted(d for d in mem if d >= start)
    if not (done and have):
        d1 = start
        if have and have[0] <= (datetime.strptime(start, "%Y%m%d") + timedelta(days=7)).strftime("%Y%m%d"):
            d1 = max(start, (datetime.strptime(have[-1], "%Y%m%d") - timedelta(days=DAILY_REFETCH_DAYS)).strftime("%Y%m%d"))
        new = fetch(d1)
        for b in new:
            mem[b["date"]] = {k: b.get(k) for k in ("date", "open", "high", "low", "close", "volume")}
        settled = _daily_settled_day(kind)
        put = [(kind, code, b["date"], b.get("open"), b.get("high"), b.get("low"), b["close"], b.get("volume"))
               for b in new if b["date"] < settled]
        if put and marketdb.writable():
            try:
                with _db_lock, db_conn() as conn:
                    for sql in DAILY_SQL:
                        conn.execute(sql)
                    conn.executemany("INSERT INTO daily_store VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(kind, code, date) DO UPDATE SET "
                                     "open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, volume=excluded.volume", put)
            except sqlite3.Error as e:
                print("[일봉] 쌓기 실패 — %s" % safe_message(e, 120), flush=True)
    return [mem[d] for d in sorted(mem) if d >= start]


def fetch_stock_daily(cfg, codes):
    """종목 정규장(KRX · J) 일봉 몇 달 — {code: {name, market:"J", bars | None, error?}} (2026-11-10 · 작업우선순위 배분 ④).
    재권님(시황분석 창) 「오늘 하이닉스는 11.49% 오른 적이 없는데」 → 기준은 정규장 종가. 차트 일봉(/api/kis/chart)은 통합(UN · MARKET_DIV_CHART)이라
    종가가 20:00 애프터 끝 값 · 시가가 넥스트레이드 프리장 첫 값이다 — 11-09 SK하이닉스 J 시 1,130,000 · 종 1,136,000 ↔ UN 시 1,165,000 · 종 1,114,000
    (삼성 J 187,200 · 189,900 ↔ UN 190,900 · 187,100 · 11-10 12:1x 잼). 기간 · 받아 두는 초는 지수와 같은 INDEX_DAILY_MONTHS · INDEX_DAILY_TTL."""
    start = (datetime.now(KST) - timedelta(days=INDEX_DAILY_MONTHS * 31)).strftime("%Y%m%d")
    out = {}
    try:
        names = {c: q.get("name") for c, q in fetch_quotes_multi(cfg, codes)[0].items()}   # 이름 — 서버 시세 캐시를 함께 쓴다
    except RuntimeError:
        names = {}
    for code in codes:
        try:
            hit = _idx_daily.get("J:" + code)
            if not (hit and time.time() - hit[0] < INDEX_DAILY_TTL and hit[1] == start):
                hit = (time.time(), start, [dict(b, open=_as_int(b["open"]), high=_as_int(b["high"]), low=_as_int(b["low"]), close=_as_int(b["close"]))
                                            for b in _daily_stored("J", code, start, lambda d1, c=code: _stock_daily_j(cfg, c, d1))])
                _idx_daily["J:" + code] = hit
            out[code] = {"name": names.get(code), "market": "J", "bars": hit[2] or None}
        except RuntimeError as e:
            out[code] = {"name": names.get(code), "market": "J", "bars": None, "error": safe_message(e)}
    return out


# ── 주식선물 최근월물 일봉 몇 달 — 날마다 그날의 최근월물을 이어 붙인다 (2026-11-10 · 작업우선순위 배분 ③) ──
# 재권님 「선물대비 등락도 추가해줘」 → 「하이닉스 삼전」 → 안(그날 최근월물을 이어 붙이고 · 만기 다음 날 다음 달물로 ·
# 봉마다 같은 월물 전날 종가를 함께)에 「응」.  GET /api/kis/stock-futures-daily?codes=005930,000660
# 월물 코드는 KIS 종목 마스터(주식선물)에서 그 종목의 상품 앞자리를 읽어 만든다 — 삼성전자 A11611 = "A11" + 해 끝자리 6 + 달 11
# (2026-11-10 잼 · 하이닉스 A50611). 지난 월물도 일봉이 온다(A11605 59줄 · A11610 60줄). 한 월물 한 번 묻기(100줄 안).
# **그날의 최근월물 = 그날 봉이 있는 월물 중 가장 가까운 달** — 만기일 셈(둘째 목요일 · 휴장이면 앞당김)을 따로 안 한다.
# 만기월물은 만기일까지 봉이 있고 다음 날부터 없으니, 봉이 있나로 저절로 갈린다.
FO_STK_MASTER = "https://new.real.download.dws.co.kr/common/master/fo_stk_code_mts.mst.zip"
_fo_stk = {"day": None, "map": None}
_fo_bars = {}                         # 월물 코드 → (시각, 끝난 월물인가, 봉들) — 끝난 월물은 다시 안 묻는다


_fo_master = {}                       # 마스터 주소 → (날, 글) — 하루 한 번 받는다(주식선물 · 주식옵션 · 코스피200 옵션)


def _fo_master_text(url):
    """KIS 선물옵션 종목 마스터(zip 안 cp949 글) — 하루 한 번."""
    today = datetime.now(KST).strftime("%Y%m%d")
    hit = _fo_master.get(url)
    if hit and hit[0] == today:
        return hit[1]
    import io, zipfile
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 KJCStudio"})
    with urllib.request.urlopen(req, timeout=30) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    text = z.read(z.namelist()[0]).decode("cp949", "replace")
    _fo_master[url] = (today, text)
    return text


def _fo_stk_prefix():
    """{종목코드: (월물 앞자리, 이름)} — 마스터를 하루 한 번 받는다. 상품 앞자리는 「월물코드 = 앞자리 + 해 끝자리 + 달 두 자리」 에 맞는 줄에서만 뽑는다."""
    today = datetime.now(KST).strftime("%Y%m%d")
    if _fo_stk["day"] == today and _fo_stk["map"]:
        return _fo_stk["map"]
    text = _fo_master_text(FO_STK_MASTER)
    out = {}
    for line in text.split("\n"):
        f = line.rstrip("\r").split("|")
        if len(f) < 9 or f[0] != "1":
            continue
        m = re.search(r"\bF (\d{6})\b", f[3])
        code, under = f[1].strip(), f[7].strip()
        if not m or len(under) != 6 or under in out:
            continue
        ym = m.group(1)
        if code.endswith(ym[3] + ym[4:]):
            out[under] = (code[:-3], f[3].split(" F ")[0].strip())
    if len(out) < 50:                  # 모양이 바뀌었으면 수가 크게 준다 — 그날은 쓰지 않는다
        raise RuntimeError("주식선물 목록에서 종목이 %d개뿐입니다(모양이 바뀌었을 수 있음)" % len(out))
    _fo_stk["day"], _fo_stk["map"] = today, out
    return out


def _fo_month_bars(cfg, fcode, d1, d2, done):
    """한 월물의 일봉 d1~d2 — 옛것부터. 끝난 월물은 들고 있고, 아니면 INDEX_DAILY_TTL 동안 들고 있다."""
    hit = _fo_bars.get(fcode)
    if hit and hit[3] == (d1, d2) and (hit[1] or time.time() - hit[0] < INDEX_DAILY_TTL):
        return hit[2]

    def ask(a):
        d = kis_get(cfg, "/uapi/domestic-futureoption/v1/quotations/inquire-daily-fuopchartprice",
                    {"FID_COND_MRKT_DIV_CODE": "JF", "FID_INPUT_ISCD": fcode, "FID_INPUT_DATE_1": a,
                     "FID_INPUT_DATE_2": d2, "FID_PERIOD_DIV_CODE": "D"}, "FHKIF03020100")
        got = []
        for r in out_rows(d, "output2"):
            close = _num(r.get("futs_prpr"), int)
            if not r.get("stck_bsop_date") or not close:
                continue                       # 0 · 빈 줄은 못 받은 날 — 넣지 않는다
            got.append({"date": r["stck_bsop_date"], "open": _num(r.get("futs_oprc"), int), "high": _num(r.get("futs_hgpr"), int),
                        "low": _num(r.get("futs_lwpr"), int), "close": close, "volume": _num(r.get("acml_vol"), int)})
        return got
    bars = [{k: (_as_int(v) if k != "date" else v) for k, v in b.items()}
            for b in _daily_stored("FO", fcode, d1, ask, done=done) if b["date"] <= d2]
    _fo_bars[fcode] = (time.time(), done, bars, (d1, d2))
    return bars


def fetch_stock_futures_daily(cfg, codes):
    """{종목코드: {name, bars:[{date, contract, open, high, low, close, prevClose, volume, roll?}] | None, error?}}.
    prevClose 는 **같은 월물**의 전 거래일 종가 — 갈아탄 날(roll)도 새 월물 자기 전날 값이라 등락률이 월물 차이로 튀지 않는다.
    그 월물 전날 봉이 없으면(상장 첫날) prevClose null."""
    now = datetime.now(KST)
    today = now.strftime("%Y%m%d")
    start = (now - timedelta(days=INDEX_DAILY_MONTHS * 31)).strftime("%Y%m%d")
    try:
        pre = _fo_stk_prefix()
    except Exception as e:
        return {c: {"name": None, "bars": None, "error": "주식선물 목록을 못 받음 — " + safe_message(e)} for c in codes}
    out = {}
    for code in codes:
        if code not in pre:
            out[code] = {"name": None, "bars": None, "error": "주식선물이 없는 종목"}
            continue
        head, name = pre[code]
        try:
            y, m = int(start[:4]), int(start[4:6])
            months = []
            while (y, m) <= (now.year + (now.month == 12), now.month % 12 + 1):    # 시작 달부터 다음 달까지
                months.append((y, m))
                y, m = (y + 1, 1) if m == 12 else (y, m + 1)
            per = {}                               # 월물 코드 → 봉들
            for y, m in months:
                fcode = "%s%d%02d" % (head, y % 10, m)
                py, pm = (y - 1, 12) if m == 1 else (y, m - 1)
                d1 = max("%04d%02d01" % (py, pm), (datetime.strptime(start, "%Y%m%d") - timedelta(days=10)).strftime("%Y%m%d"))
                d2 = min("%04d%02d31" % (y, m), today)
                if d1 > d2:
                    continue
                done = "%04d%02d" % (y, m) < today[:6]                            # 지난달 월물은 끝났다
                per[fcode] = _fo_month_bars(cfg, fcode, d1, d2, done)
            front = {}                             # 날짜 → (월물 코드, 봉 차례) — 그날 봉이 있는 가장 가까운 달
            for fcode in per:                      # 넣은 차례가 곧 달 차례(가까운 달 먼저)
                for i, b in enumerate(per[fcode]):
                    if b["date"] >= start and b["date"] not in front:
                        front[b["date"]] = (fcode, i)
            bars, last = [], None
            for d in sorted(front):
                fcode, i = front[d]
                b = per[fcode][i]
                row = dict(b, contract=fcode, prevClose=per[fcode][i - 1]["close"] if i > 0 else None)
                if last and last != fcode:
                    row["roll"] = True             # 이날부터 다음 달물 — 만기 다음 날
                last = fcode
                bars.append(row)
            out[code] = {"name": name, "bars": bars or None}
        except RuntimeError as e:
            out[code] = {"name": name, "bars": None, "error": safe_message(e)}
    return out


# ── 주식선물 · 종목 풋 · 코스피200 풋/콜 지금 값 — 한 주소 (2026-11-10 · 작업우선순위 배분 · 시황분석 탭 몫) ──
# 재권님 「종목별로 실시간 선물 풋 알수있나?」 → 잼 → 안에 「응」 → 「그럼 5분으로 바꿔서 해」 →
# 「화면을 보면 그때 바로 값 가져오고 5분단위로 불러오는 방향」.  GET /api/kis/fo-snapshot?codes=005930,000660
# **누가 물을 때만 받는다** — 받은 값은 FO_SNAP_TTL(장중) · FO_SNAP_TTL_CLOSED(장 밖) 동안 다시 쓴다. 혼자 도는 받기는 없다.
# 값은 현재가 조회(inquire-price · FHMIF10000000) 하나로 받는다 — 시장 JF 주식선물 · JO 주식옵션 · O 코스피200 옵션(11-10 잼 · 모두 정상).
# 월물 · 행사가 코드는 KIS 마스터에서 — 주식은 fo_stk_code_mts(1 선물 · 5 콜 · 6 풋), 코스피200 은 fo_idx_code_mts(5 콜 · 6 풋 · 미니 · 위클리는 안 씀).
# **코스피200 풋/콜 비율은 등가격 둘레 행사가만 센다** — 콜풋 전광판(display-board-callput)은 한 번에 행사가 100줄을 위에서부터만 주고
# (11-10 잼 · 1,347.5 ~ 1,595 · 지수 814) 이어받기 머리줄을 우리 kis_get 이 아직 못 보낸다 — 그래서 그 표를 안 쓰고 둘레 행사가를 하나씩 묻는다.
# 어느 월물 · 행사가 범위로 셌는지는 응답에 그대로 낸다.
FO_IDX_MASTER = "https://new.real.download.dws.co.kr/common/master/fo_idx_code_mts.mst.zip"
FO_SNAP_TTL = 300                     # 장중(파생 주간 08:45~15:45) 받은 값을 다시 쓰는 초 — 재권님 「5분」
FO_SNAP_TTL_CLOSED = 600              # 장 밖
FO_SNAP_PUTS = 5                      # 종목마다 현재가에 가까운 행사가 몇 줄 — 콜 · 풋 각각
FO_SNAP_K200_SIDE = 5                 # 코스피200 등가격 위아래 행사가 몇 칸씩(콜 · 풋 각각 2×이것+1 줄)
FO_SNAP_WORKERS = 4                   # 옵션 시세를 몇 건씩 한꺼번에 묻나 — 하나씩이면 첫 부름이 20초를 넘었다(11-10 8767 · 창구 잼)
_fo_snap = {}                         # 열쇠 → (시각, 값)
_fo_snap_lock = threading.Lock()


def _fo_snap_ttl():
    now = datetime.now(KST)
    hm = now.hour * 100 + now.minute
    return FO_SNAP_TTL if now.weekday() < 5 and 845 <= hm < 1545 else FO_SNAP_TTL_CLOSED


def _fo_options(url, under):
    """{(콜풋, 월 YYYYMM): [(행사가, 코드)]} — 그 기초자산(주식 종목코드 · 코스피200 은 "2001")의 정규 옵션."""
    out = {}
    for line in _fo_master_text(url).split("\n"):
        f = line.rstrip("\r").split("|")
        if len(f) < 9 or f[0] not in ("5", "6") or f[7].strip() != under:
            continue
        m = re.search(r"(?:^|\s)([CP]) (\d{6})\b", f[3])     # 「미니P」 · 위클리는 앞이 붙어 안 걸린다
        if not m:
            continue
        try:
            strike = float(f[5])
        except ValueError:
            continue
        out.setdefault((m.group(1), m.group(2)), []).append((strike, f[1].strip()))
    return out


def _fo_quote(cfg, div, code):
    """현재가 조회 한 줄 — 못 받으면 None."""
    try:
        d = kis_get(cfg, "/uapi/domestic-futureoption/v1/quotations/inquire-price",
                    {"FID_COND_MRKT_DIV_CODE": div, "FID_INPUT_ISCD": code}, "FHMIF10000000")
    except RuntimeError:
        return None, None
    o1 = d.get("output1") if isinstance(d.get("output1"), dict) else {}
    o3 = d.get("output3") if isinstance(d.get("output3"), dict) else {}
    price = _num(o1.get("futs_prpr"), float)
    if not o1 or price is None:
        return None, None
    row = {"code": code, "name": (o1.get("hts_kor_isnm") or "").strip() or None, "price": price,
           "change": _num(o1.get("futs_prdy_vrss"), float), "volume": _num(o1.get("acml_vol"), int),
           "openInterest": _num(o1.get("hts_otst_stpl_qty"), int)}
    if div in ("JO", "O"):
        row["iv"] = _num(o1.get("hts_ints_vltl"), float)
    return row, _num(o3.get("bstp_nmix_prpr"), float)       # 뒤 값 = 코스피200 지수(11-10 잼 814.31)


def _fo_quotes(cfg, div, codes):
    """여러 코드를 FO_SNAP_WORKERS 건씩 한꺼번에 — [(줄, 지수)] 차례 그대로. 호출 수는 하나씩과 같다.
    ⚠️ 넘어간 스레드는 낮음 표시를 잃어 높음으로 친다(위 PRIO_HEADER 주석) — 5분에 한 번 · 수십 건이라 그대로 둔다."""
    if not codes:
        return []
    with ThreadPoolExecutor(max_workers=FO_SNAP_WORKERS) as ex:
        return list(ex.map(lambda c: _fo_quote(cfg, div, c), codes))


def _fo_front(opts, kind):
    """가장 가까운 달(지금 달 이후) 월물."""
    months = sorted(m for (k, m) in opts if k == kind and m >= datetime.now(KST).strftime("%Y%m"))
    return months[0] if months else None


def _fo_snap_stock(cfg, code):
    pre = _fo_stk_prefix()
    if code not in pre:
        return {"name": None, "futures": None, "puts": None, "error": "주식선물이 없는 종목"}
    head, name = pre[code]
    opts = _fo_options(FO_STK_MASTER, code)
    month = _fo_front(opts, "P")
    fut = None
    for ym in sorted({m for (_, m) in opts} | {datetime.now(KST).strftime("%Y%m")}):
        if ym < datetime.now(KST).strftime("%Y%m"):
            continue
        fut, _ = _fo_quote(cfg, "JF", "%s%s%s" % (head, ym[3], ym[4:]))
        if fut:
            fut["month"] = ym
            break
    side = {}                         # 콜 · 풋을 따로 — 재권님 「풋옵션 콜옵션은 구분되어야해」(11-10)
    for kind in ("C", "P"):
        if not (month and fut and (kind, month) in opts):
            side[kind] = None
            continue
        near = sorted(sorted(opts[(kind, month)], key=lambda x: abs(x[0] - fut["price"]))[:FO_SNAP_PUTS])
        got = _fo_quotes(cfg, "JO", [c for _, c in near])
        side[kind] = [dict(row or {"code": ocode, "price": None}, strike=strike)
                      for (strike, ocode), (row, _) in zip(near, got)]
    return {"name": name, "futures": fut, "calls": side["C"], "puts": side["P"], "putMonth": month, "optionMonth": month,
            "putNote": "행사가는 선물 현재가에 가까운 %d줄 — 콜 · 풋 각각" % FO_SNAP_PUTS if side["P"] else None}


def _fo_snap_k200(cfg):
    opts = _fo_options(FO_IDX_MASTER, "2001")
    month = _fo_front(opts, "P")
    if not month or ("C", month) not in opts:
        return {"error": "코스피200 옵션 목록을 못 읽음"}
    puts = sorted(opts[("P", month)])
    _, k200 = _fo_quote(cfg, "O", puts[len(puts) // 2][1])
    if not k200:
        return {"error": "코스피200 지수를 못 받음"}
    strikes = sorted(s for s, _ in puts)
    atm = min(range(len(strikes)), key=lambda i: abs(strikes[i] - k200))
    pick = strikes[max(0, atm - FO_SNAP_K200_SIDE): atm + FO_SNAP_K200_SIDE + 1]
    near = sorted(sorted(pick, key=lambda s: abs(s - k200))[:FO_SNAP_PUTS])   # 줄로 낼 행사가 — 종목 칸과 같은 수
    sums = {"C": [0, 0, 0], "P": [0, 0, 0]}                 # 거래량 · 미결제 · 못 받은 줄
    lines = {}                                              # 콜 · 풋 줄 — 재권님 「코스피200은 코스피로 나누고 여기도 적용해줘」(11-10)
    for kind in ("C", "P"):
        codes = dict(opts[(kind, month)])
        got = dict(zip([s for s in pick if s in codes], _fo_quotes(cfg, "O", [codes[s] for s in pick if s in codes])))
        lines[kind] = [dict(got.get(s, (None, None))[0] or {"code": codes.get(s), "price": None}, strike=s) for s in near]
        for s in pick:
            row, _ = got.get(s, (None, None))
            if row and row["volume"] is not None and row["openInterest"] is not None:
                sums[kind][0] += row["volume"]
                sums[kind][1] += row["openInterest"]
            else:
                sums[kind][2] += 1
    ratio = lambda p, c: round(p / c, 3) if c else None
    fut = None                                              # 지수선물 최근월물 — 석 달마다라 옵션 월물과 다를 수 있다(11-10 A01612)
    for line in _fo_master_text(FO_IDX_MASTER).split("\n"):
        f = line.rstrip("\r").split("|")
        m = re.search(r"^F (\d{6})$", f[3].strip()) if len(f) > 7 and f[0] == "1" and f[7].strip() == "2001" else None
        if m and m.group(1) >= datetime.now(KST).strftime("%Y%m") and (fut is None or m.group(1) < fut[0]):
            fut = (m.group(1), f[1].strip())
    if fut:
        row, _ = _fo_quote(cfg, "F", fut[1])
        fut = dict(row, month=fut[0]) if row else None
    return {"index": k200, "futures": fut, "calls": lines["C"], "puts": lines["P"], "optionMonth": month,
            "month": month, "strikes": [pick[0], pick[-1]], "strikeCount": len(pick),
            "callVolume": sums["C"][0], "putVolume": sums["P"][0], "callOI": sums["C"][1], "putOI": sums["P"][1],
            "putCallVolume": ratio(sums["P"][0], sums["C"][0]), "putCallOI": ratio(sums["P"][1], sums["C"][1]),
            "missing": sums["C"][2] + sums["P"][2]}


def fetch_fo_snapshot(cfg, codes):
    """{stocks: {종목코드: {name, futures, puts, putMonth}}, kospi200: {...}, at} — 받은 값은 _fo_snap_ttl() 동안 다시 쓴다."""
    out = {"stocks": {}, "kospi200": None}
    with _fo_snap_lock:                                       # 같은 때 둘이 물어도 KIS 는 한 번
        ttl = _fo_snap_ttl()
        for key in list(codes) + ["K200"]:
            hit = _fo_snap.get(key)
            if not (hit and time.time() - hit[0] < ttl):
                try:
                    val = _fo_snap_k200(cfg) if key == "K200" else _fo_snap_stock(cfg, key)
                except Exception as e:                        # 마스터를 못 받음 등
                    val = {"error": "못 받음 — " + safe_message(e)}
                hit = (time.time(), val)
                if "error" not in val or val.get("error") == "주식선물이 없는 종목":
                    _fo_snap[key] = hit
            row = dict(hit[1], at=datetime.fromtimestamp(hit[0], KST).strftime("%H:%M:%S"))
            if key == "K200":
                out["kospi200"] = row
            else:
                out["stocks"][key] = row
    return out, ttl


def fetch_index_daily(cfg, names):
    """{이름: {name, unit, market, bars:[{date, open, high, low, close}] | None, error?}} — 못 받은 지수는 bars None(0 이 아니다)."""
    start = (datetime.now(KST) - timedelta(days=INDEX_DAILY_MONTHS * 31)).strftime("%Y%m%d")
    dom = {n: c for c, n in INDEX_DEFS}
    ovs = {d[0]: d for d in OVERSEAS_DEFS}
    nvx = {d[0]: d for d in NAVER_INDEX_DEFS}
    out = {}
    for name in names:
        try:
            if name in dom:
                bars = [{"date": str(b["ts"])[:8], "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"]}
                        for b in fetch_index_candles(cfg, dom[name], "D") if str(b["ts"])[:8] >= start]
                out[name] = {"name": name, "market": "domestic", "unit": "pt", "bars": bars or None}
            elif name in ovs:
                key, div, code, label, unit = ovs[name]
                hit = _idx_daily.get(key)
                if not (hit and time.time() - hit[0] < INDEX_DAILY_TTL and hit[1] == start):
                    hit = (time.time(), start, [{k: b[k] for k in ("date", "open", "high", "low", "close")}
                                                for b in _daily_stored("OVS", key, start, lambda d1, dv=div, c=code: _ovs_daily(cfg, dv, c, d1))])
                    _idx_daily[key] = hit
                out[name] = {"name": label, "market": "overseas", "unit": unit, "kisCode": code, "bars": hit[2] or None}
            elif name in nvx:
                key, sym, label, unit = nvx[name]
                bars = [{k: b[k] for k in ("date", "open", "high", "low", "close")}
                        for b in _daily_stored("NVX", key, start, lambda d1, k=key: [x for x in _nvx_bars(k) if x["date"] >= d1])]
                out[name] = {"name": label, "market": "overseas", "unit": unit, "source": "네이버", "naverCode": sym,
                             "bars": bars or None}
            else:
                out[name] = {"name": name, "bars": None, "error": "모르는 지수 이름"}
        except RuntimeError as e:
            out[name] = {"name": name, "bars": None, "error": safe_message(e)}
    return out


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
# **5초다** (2026-09-23 지시 — 「야간선물 캐시 5초로 하고」).
#
# 0.7 초였다. 화면이 **1초마다** 묻는 자리라(`js/home.js` 의 1초 루프)
# 사실상 요청마다 KIS 로 나갔고, **캐시로 막을 수 있는 초당 건수 2.98 중
# 1.429 — 절반 가까이를 이 한 줄이 썼다** (2026-09-23 실측).
#
# 5초로 두면 초당 0.2 가 되어 **전체가 약 1.75 로 줄어든다.**
# 대신 화면은 **같은 값을 최대 다섯 번** 보게 된다.
FUTURES_TTL = 5
_fut_cache = {}

# ── KRX 야간선물 (2026-10-26 지시 — 「응 채워줘」) ─────────────────────
# 같은 조회(FHMIF10000000 · 10100000)에 시장구분 "CM" 을 주면 KRX 야간장 값이 온다
# (2026-10-25 실측 — F 863.30 · CM 861.70 −1.60). 전일비 기준(futs_sdpr)은 그 야간장
# 앞 주간장 종가다. 응답에 시각 칸이 없어 **열렸는지는 시계로 가른다.**
#
# 야간장은 18:00 ~ 다음 날 06:00(05:50~06:00 은 종가 단일가). 2025-06 부터 KRX 가
# 직접 연다. 18:00 이 정규장 휴장일이면 그날 밤은 안 열린다 — 주말은 거르지만
# **공휴일은 아직 안 가른다 — 그날은 「야간장 중」 으로 잘못 보인다**(값은 지난 밤 그대로). 이 파일의 휴장일 가르기
# (오늘 국내 5분봉이 들었나) 셈을 쓰면 닫힌다(개념정의 10-26) — 아직 안 했다.
FUTURES_NIGHT_OPEN_MIN = 18 * 60
FUTURES_NIGHT_CLOSE_MIN = 6 * 60
# 야간장 밖에는 값이 안 바뀐다 — 화면이 1초마다 물어도 KIS 로 덜 나가게 길게 둔다.
FUTURES_NIGHT_IDLE_TTL = 300


def futures_night_open(now=None):
    """지금 KRX 야간장이 열려 있나 — 주말 밤은 닫힘. 공휴일은 아직 안 가른다."""
    now = now or datetime.now(KST)
    hm = now.hour * 60 + now.minute
    if FUTURES_NIGHT_CLOSE_MIN <= hm < FUTURES_NIGHT_OPEN_MIN:
        return False
    start = now if hm >= FUTURES_NIGHT_OPEN_MIN else now - timedelta(days=1)
    return start.weekday() < 5


def fetch_futures(cfg, mrkt="F"):
    """코스피200 선물 최근월물. mrkt "F" 주간 · "CM" KRX 야간. 못 받으면 None — 화면은 그 칸만 비운다."""
    night = mrkt == "CM"
    is_open = futures_night_open() if night else None
    ttl = FUTURES_TTL if (not night or is_open) else FUTURES_NIGHT_IDLE_TTL
    key = "k200-night" if night else "k200"
    hit = _fut_cache.get(key)
    if hit and (time.time() - hit[0]) < ttl:
        if night:
            return dict(hit[1], open=is_open)
        return hit[1]
    try:
        data = kis_get(
            cfg,
            "/uapi/domestic-futureoption/v1/quotations/inquire-price",
            {"FID_COND_MRKT_DIV_CODE": mrkt, "FID_INPUT_ISCD": FUTURES_CODE},
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
    if night:
        # 열렸는지 · 장 시간은 서버가 알려 준다 — 화면이 시계를 따로 들지 않게
        row["open"] = is_open
        row["hours"] = "%02d:%02d~%02d:%02d" % (
            FUTURES_NIGHT_OPEN_MIN // 60, FUTURES_NIGHT_OPEN_MIN % 60,
            FUTURES_NIGHT_CLOSE_MIN // 60, FUTURES_NIGHT_CLOSE_MIN % 60)
    _fut_cache[key] = (time.time(), row)
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
# 초당 3.4건**을 썼다 — **그때 예산 다섯 중 셋이었다** (2026-09-18 실측. 호출한 스레드를
# 세어 보니 미리받기는 50초에 2~3회뿐이었고 나머지가 전부 이쪽이었다).
#
# 5초로 두면 2초 주기의 요청 중 대부분이 캐시로 받아진다. 값이 최대 5초 지난
# 것이 되지만 지수는 그 사이 눈에 띄게 움직이지 않는다.
#
# 선물(FUTURES_TTL)도 **2026-09-23 에 5초가 됐다.** 그전에는 0.7초여서
# 「요청마다 선물 한 건은 여전히 나간다」 고 여기 적혀 있었는데, 이제 아니다.
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
            info = fetch_index(cfg, code)
            series = []
            if with_chart:
                try:
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
    배포본 워커가 같은 파라미터를 읽어 짝으로 남겨 두었다 — 워커는
    2026-10-06 에 지웠다. 지금은 쓰는 쪽이 없다.
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_idx = pool.submit(fetch_indices, cfg, with_chart)
        f_ovs = pool.submit(fetch_overseas, cfg) if overseas else None
        data, errors = f_idx.result()
        if f_ovs is not None:
            ovs, ovs_err = f_ovs.result()
            data = data + ovs
            errors.update(ovs_err)
            nvx, nvx_err = fetch_naver_indices()      # KIS 에 없는 나라 지수(NAVER_INDEX_DEFS) — 해외와 같은 자리 · 뒤에 붙인다
            data = data + nvx
            errors.update(nvx_err)
    return data, errors


def _num(v, cast=float):
    try:
        return cast(str(v).strip())
    except (TypeError, ValueError):
        return None


class NoSuchStock(RuntimeError):
    """그런 종목 코드가 없다 — KIS 가 오류 없이 값을 전부 0 으로 준다(2026-11-05 · 999999 실측).
    「없음」 을 0원으로 내지 않으려고 따로 가른다(CLAUDE.md 「못 쟀으면 `0` 이 아니라 「못 쟀다」 고 낸다」)."""


def fetch_price(cfg, code):
    """국내 주식 현재가 조회. 시장 기준은 지금 시각에 따라 정해진다.

    **캐시를 탄다 (2026-10-01 지시 — 「캐시 붙이고」).**

    전에는 이 길만 캐시가 없어 **부를 때마다 KIS 로 나갔다.** 2026-10-01
    장중 실측 — 2초 간격으로 **10번 부르니 10번 다 나갔고 캐시가 0번
    막았다.** 같은 종목을 복수 경로(`/api/kis/prices`)로 4번 부르면
    **1번만 나간다.**

    그때의 워커는 이미 캐시를 탔고 **로컬만 갈려 있었다** —
    「룰은 하나다 — 로컬만 다르게 정하지 않는다」 의 그 자리다.

    ⚠️ **복수와 저장소를 나눈다.** 같은 `_price_cache` 를 그냥 쓰면 안 된다 —
    `fetch_prices` 는 이 함수를 부른 뒤 **「프론트가 쓰는 형태」로 바꿔서**
    담기 때문에 **담긴 모양이 이 함수의 반환 모양과 다르다.**

        이 함수가 주는 것   code · **change · changePct · sign** · eps · bps · source · mode · …
        복수가 담는 것      price · prev · amt · pct · per · pbr · high52 · … (위 여덟이 **없다**)

    그대로 쓰면 **캐시에 맞았을 때와 안 맞았을 때 응답 모양이 달라진다.**
    2026-10-01 실측으로 **지금 화면이 쓰는 키는 전부 양쪽에 다 있어** 당장은
    안 깨지지만, **내일 누가 `changePct` 를 쓰면 캐시에 맞았을 때만
    `undefined`** 가 된다 — 가장 찾기 어려운 꼴이다.

    **호출이 늘지 않는다.** 지금은 이 길에 캐시가 **아예 없어** 매번 나가므로,
    저장소를 나눠도 **나빠질 것이 없다.**
    """
    # **접두사로 복수 것과 가른다.** `_cache_ttl` 은 모든 종목이 같은 값이라
    # 접두사가 붙어도 그대로 듣는다.
    ck = "one:" + code
    cached = _cache_get(ck)
    if cached is not None:
        if cached.get("notFound"):
            raise NoSuchStock("없는 종목 코드입니다 (%s)" % code)
        return cached

    div = quote_market_div()
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-price",
        {"FID_COND_MRKT_DIV_CODE": div, "FID_INPUT_ISCD": code},
        "FHKST01010100",
    )
    o = data.get("output") or {}
    sign = o.get("prdy_vrss_sign")  # 1상한 2상승 3보합 4하한 5하락
    out = {
        "code": code,
        # **종목명을 넣지 않는다** (2026-09-18).
        #
        # 이 API 는 종목명을 안 준다. 응답 필드 80개를 다 훑었는데 이름은
        # `bstp_kor_isnm`(업종) 과 `rprs_mrkt_kor_name`(시장) 둘뿐이다.
        # 그 업종명을 `name` 으로 내보내고 있어서 삼성전자가 「전기·전자」로,
        # NAVER 가 「IT 서비스」로 나왔다.
        #
        # 그때의 워커는 이 자리에 `name` 을 아예 안 담았다. **같은 API 인데
        # 응답 모양이 갈려 있었다.** 빼서 맞췄다.
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
        # 상장주식수(주) — 투자자 누적 순매수를 %p 로 나눌 때 쓴다(holding_flow · 2026-10-26)
        "listed": _num(o.get("lstn_stcn"), int),
        # 종목 상태 칩 — 이벤트 대응 ④⑤⑥(2026-11-09 · 재권님 「응」) · 같은 응답이라 KIS 를 더 안 부른다(`stock_status`)
        "status": stock_status(o),
        "source": "KIS",
        "mode": cfg["mode"],
    }
    # **없는 종목** — 현재가도 상장주식수도 0 이면 그런 코드가 없는 것이다(거래정지 종목도 상장주식수 · 마지막 값은 있다).
    # 0원 · 0억원으로 내지 않고 따로 알린다 · 같은 코드를 캐시 동안 다시 묻지 않게 그 사실도 담아 둔다
    if not out["price"] and not out["listed"]:
        _cache_put(ck, {"notFound": True})
        raise NoSuchStock("없는 종목 코드입니다 (%s)" % code)
    if div == "UN":
        overnight_price(code, out)          # 자정 뒤 08:00 전 — 어제 20:00 넥장 마감 값으로(아래 `overnight_row`)
    _cache_put(ck, out)
    return out


# ── 종목 상태 — 거래정지 · 관리 · 시장경고 · 단기과열 · 정리매매 · 상한가 · 하한가 (2026-11-09 · 이벤트 대응 ④⑤⑥) ──
# 현재가(inquire-price) 응답 칸 그대로 — 공식 예제(open-trading-api chk_inquire_price)의 칸 이름 · 값 뜻은 11-09 공식 종목 마스터
# (kospi_code.mst 거래정지 · 관리종목 · 시장경고 · 단기과열 · 정리매매)로 고른 종목을 이 응답과 대 봐서 맞췄다:
#     거래정지 DH오토넥스 000300 → iscd_stat_cls_code 58 · 관리종목 다이나맥 000040 → mang_issu_cls_code Y(상태 51) ·
#     정리매매 CJ씨푸드1우 011155 → sltr_yn Y · 투자주의 깨끗한나라 004540 → mrkt_warn_cls_code 01 · 투자경고 에이엔피 015260 → 02 ·
#     단기과열 흥국화재우 000545 → short_over_yn Y · 보통 삼성전자 → 상태 55 · 나머지 N/00
# **못 본 것** — 시장경고 03(투자위험 · 그날 해당 종목 없음) · temp_stop_yn Y(임시정지) · 상한가 · 하한가는 prdy_vrss_sign 1 · 4(이 파일 위 주석)
STOCK_WARN = {"01": "투자주의", "02": "투자경고", "03": "투자위험"}


def stock_status(o):
    """현재가 응답 한 줄 → 칩 목록 [{"t": 글, "k": "danger" · "up" · "down"}] · 해당 없으면 빈 목록."""
    out = []
    if o.get("iscd_stat_cls_code") == "58":
        out.append({"t": "거래정지", "k": "danger"})
    elif o.get("temp_stop_yn") == "Y":
        out.append({"t": "임시정지", "k": "danger"})
    if o.get("sltr_yn") == "Y":
        out.append({"t": "정리매매", "k": "danger"})
    if o.get("mang_issu_cls_code") == "Y":
        out.append({"t": "관리종목", "k": "danger"})
    if STOCK_WARN.get(o.get("mrkt_warn_cls_code")):
        out.append({"t": STOCK_WARN[o["mrkt_warn_cls_code"]], "k": "danger"})
    if o.get("short_over_yn") == "Y":
        out.append({"t": "단기과열", "k": "danger"})
    if o.get("prdy_vrss_sign") == "1":
        out.append({"t": "상한가", "k": "up"})
    elif o.get("prdy_vrss_sign") == "4":
        out.append({"t": "하한가", "k": "down"})
    return out


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

_quote_cache = {}                  # 종목코드 → (받은 시각, 시장 구분 J · UN, 그 줄) — 묶음이 아니라 종목 단위
_multi_lock = threading.Lock()
QUOTE_CACHE_MAX = 4000             # 넘으면 오래된 것부터 치운다(한 종목 줄은 작다 · 코스피 + 코스닥 다 담아도 넘지 않는 수)


def fetch_quotes_multi(cfg, codes, max_age=None):
    """목록용 시세. 30종목씩 묶어 부른다. {code: {...}} 로 돌려준다.

    받은 값을 **종목 단위**로 들고 있다가, 누가 묻든 그 종목이 `max_age` 초 안에 받은 것이면 그 값을 쓰고
    없는 종목만 30개씩 묶어 KIS 에 묻는다 — 순위표 · 시장 지도 · 장외 순위가 같은 종목을 따로 받지 않게
    (2026-10-29 재권님 「지도에 있는값은 어디에서 가져오지? 이미 가져온 값을 그리는게 아닌가?」 → (가) 「응 해줘」).
    전에는 묶음(종목 목록 전체)을 열쇠로 들고 있어 묶음이 조금만 달라도 겹치는 종목까지 다시 받았다.

    · max_age — 부르는 쪽이 허용하는 나이(초). 기본은 MULTI_CACHE_TTL 이고 그보다 짧게는 못 준다(--slow 서버의 60초가 그대로 듣게).
      시장 지도는 자기 응답 주기(heatmap.HEATMAP_TTL)를 준다 — 원래 그만큼 묵은 값을 내던 자리라 칸끼리 받은 시각이 달라도 그 안이다
    · 정규장(J) ↔ 통합(UN)이 바뀌면 옛 쪽 값은 안 쓴다(줄마다 구분을 함께 적어 둔다)
    · 장 밖 값(attach_reg_close · overnight_quotes)은 새로 받은 종목에만 붙인다 — 들고 있던 줄은 이미 붙어 있다
    · 내줄 때는 줄을 복사한다 — 한 곳이 고쳐도 다른 곳이 안 바뀌게
    · 오류는 이번에 새로 물은 종목 것만 돌려준다 — 못 받은 종목은 담지 않아 다음 요청이 다시 묻는다
    """
    div = quote_market_div()
    age = max(MULTI_CACHE_TTL, max_age or 0)
    now = time.time()
    got, need = {}, []
    with _multi_lock:
        for code in codes:
            hit = _quote_cache.get(code)
            if hit and hit[1] == div and (now - hit[0]) < age:
                got[code] = hit[2]
            else:
                need.append(code)
    if not need:
        _stats["cache_hits"] += 1
        res = {c: dict(r) for c, r in got.items()}
        if not market_hours.auction(sys.modules[__name__]):   # 아래 끝자리와 같다 — 동시호가 뒤에는 남겨 두는 몇 분(_expect_held)만
            _expect_after(res)
        return res, {}
    codes = need
    out, errors = {}, {}
    kind = market_hours.auction(sys.modules[__name__])      # 동시호가("open" · "close")면 줄마다 예상 체결가를 싣는다

    for i in range(0, len(codes), MULTI_MAX):
        chunk = codes[i:i + MULTI_MAX]
        params = {}
        for n, code in enumerate(chunk, start=1):
            params["FID_COND_MRKT_DIV_CODE_%d" % n] = div
            params["FID_INPUT_ISCD_%d" % n] = code
        try:
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
                "expect": _multi_expect(r, kind),    # 동시호가 동안만 — 아래 _multi_expect
            }
        # 통합(UN)으로 물은 동시호가에 예상가가 하나도 안 왔으면 KRX(J)로 그 묶음을 한 번 더 묻는다 — 예상가 칸만 쓴다
        # (11-10 09:12 호가 응답에서 UN 은 예상가 "0" · J 는 값이 있었다. 멀티 시세도 그런지는 **아직 못 잼** — 오면 이 길은 안 탄다)
        if kind and div != "J" and not any(out.get(c, {}).get("expect") for c in chunk):
            try:
                jd = kis_get(cfg, "/uapi/domestic-stock/v1/quotations/intstock-multprice",
                             {k: ("J" if k.startswith("FID_COND") else v) for k, v in params.items()}, "FHKST11300006")
                for r in out_rows(jd, "output"):
                    c = (r.get("inter_shrn_iscd") or "").strip()
                    if c in out:
                        out[c]["expect"] = _multi_expect(r, kind)
            except RuntimeError:
                pass
        _expect_note({c: out[c].get("expect") for c in chunk if c in out})

    # 장 밖(통합 시세)이면 그 회차 정규장 종가와 종가 대비 등락률을 함께 싣는다 — 아래 `attach_reg_close`.
    # 평일 아침 07:00 부터 정규장이 끝날 때까지는 장외 값을 싣지 않는다 — 아래 `after_cleared`
    if div == "UN" and out:
        attach_reg_close(cfg, out)
        overnight_quotes(out)               # 자정 뒤 08:00 전 — 어제 20:00 넥장 마감 값으로(아래 `overnight_row`)
        if after_cleared():
            for q in out.values():
                for k in ("regClose", "regPct", "regDate"):
                    q.pop(k, None)

    # 받아둔다 — 받은 종목만. 못 받은 종목은 안 담아 다음 요청이 다시 묻는다
    if out:
        t = time.time()
        with _multi_lock:
            for code, row in out.items():
                _quote_cache[code] = (t, div, row)
            if len(_quote_cache) > QUOTE_CACHE_MAX:
                for k, _v in sorted(_quote_cache.items(), key=lambda kv: kv[1][0])[:len(_quote_cache) // 4]:
                    _quote_cache.pop(k, None)
    _expect_actual(out, div)
    res = {c: dict(r) for c, r in got.items()}
    res.update({c: dict(r) for c, r in out.items()})
    if not market_hours.auction(sys.modules[__name__]):       # 동시호가 뒤에는 예상가를 뗀다 — 정규장을 연 뒤 몇 분만 마지막 값(_expect_held)
        _expect_after(res)
    return res, errors


# ---------------------------------------------------------------- 장외 — 정규장 종가 대비
# 재권님 「종가 이후에 오른종목들 상위만 따로 보고싶은데 … 실시간 순위에 장외 라고 하나 만들어서 거기서 종가대비
# 등락률만 표기되도록 해줘」(2026-10-26 · 작업우선순위 경유). 홈 순위 칸 「장외」 칩이 쓰고, 개발1 의 「장 뒤 등락률을
# 정규장 종가 대비로」 도 같은 값을 가져다 쓴다 — 서버가 한 번 받는다(「같은 값은 한 곳에만 둔다」).
#
#   장 밖 시세   통합(UN) 멀티 — 넥스트레이드 애프터마켓(15:30 뒤) · 프리마켓(08:00~) 값이 들어 있다(quote_market_div)
#   정규장 종가  정규장(J) 일봉의 그날 종가 — 아래 `_reg_close_daily`
#   응답 칸      regClose(정규장 종가) · regPct(종가 대비 등락률 %) · regDate(그 종가의 날)
#
# **종가는 회차마다 한 번만 받고 다음 정규장이 열릴 때까지 쥔다.** 장이 끝나면 안 바뀌는 값이라 다시 물을 까닭이 없다
# (종목마다 일봉 1건 · 회차에 한 번). 15:30 마감부터 REG_CLOSE_READY(15:40) 전까지는 종가가 일봉에 들어오기를 기다리느라
# 받지 않는다 — **그 10분은 regPct 가 없고 「장외」 칩이 빈다**(정규장 중 쓰던 앞 회차 20:00 값도 15:30 에 내려간다).
# 빈칸으로 둔다 — 그 사이 값을 지어내지 않는다(「못 쟀으면 0 이 아니라 「못 쟀다」 고 낸다」).
# **종가는 정규장(J) 일봉의 그날 종가로 받는다** (2026-10-28 고침). 전에는 J 멀티의 「지금가」 를 처음 물을 때 쥐었는데
# 그 값이 종가가 아니었다 — 10-27 에 삼성전자 223,000 · SK하이닉스 1,363,000 · 삼성전자우 171,900 을 쥐었고, J 일봉 종가 ·
# 오늘(10-28) KIS · 네이버의 전일 종가는 222,000 · 1,341,000 · 171,100 이었다(08:4x 실측). 장외 칩이 하루 저녁 내내 틀린
# 기준으로 셈했다(재권님 「삼성 하이닉스도 많이 올랐는데 제대로 안나오는데」 → 「종가대비해서 해야해」 · 2026-10-28).
# J 멀티 지금가가 언제 어떻게 움직였는지는 못 가렸다 — 시간외 단일가(16:00~18:00)일 수 있다.
# 일봉은 한 종목에 한 번 묻는다 — 순위 목록 종목이면 하루 350번쯤. 쥔 것은 그 회차에 다시 안 묻는다.
# **일봉에 그날 줄이 없으면 쥐지 않는다**(장이 안 열린 날 · 아직 안 들어온 때) — 다음에 다시 묻는다.
# 08:00~09:00 은 넥스트레이드 프리마켓 값을 그 종가와 견준다 — 재권님 「장외는 8시되면 리셋해줘」 → (가) 「종가대비」.
REG_CLOSE_READY = (15, 40)      # 이 시각부터 그날 종가로 받는다 — 15:30 동시호가 결과가 일봉에 들 때를 넉넉히 둔다

_reg_close = {}                 # code -> (회차 날짜 "YYYY-MM-DD", 종가)
_reg_lock = threading.Lock()
_reg_inflight = set()           # 지금 일봉을 받는 중인 종목 — 다른 요청은 다시 묻지 않고 건너뛴다(다음 요청에 나온다)


def reg_session_day(now=None):
    """지금 쥐어야 할 정규장 종가가 어느 날 것인지. 받을 때가 아니면 None.

    09:00~15:40(REG_CLOSE_READY) 전은 None — 정규장 중이거나 종가가 일봉에 아직 안 든 때다. 토 · 일 · 아침 9시 전은 앞 평일."""
    now = now or datetime.now(KST)
    hm = (now.hour, now.minute)
    if now.weekday() < 5 and KRX_OPEN <= hm < REG_CLOSE_READY:
        return None
    day = now.date()
    if now.weekday() >= 5 or hm < KRX_OPEN:
        day -= timedelta(days=1)
        while day.weekday() >= 5:
            day -= timedelta(days=1)
    return day.isoformat()


def _reg_close_daily(cfg, code, day):
    """정규장(J) 일봉에서 그 날의 종가. 그 날 줄이 없으면 None — 아직 없는 것이지 0 이 아니다."""
    ymd = day.replace("-", "")
    start = (datetime.strptime(ymd, "%Y%m%d") - timedelta(days=7)).strftime("%Y%m%d")
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
         "FID_INPUT_DATE_1": start, "FID_INPUT_DATE_2": ymd,
         "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"},
        "FHKST03010100",
    )
    for r in out_rows(data, "output2"):
        if str(r.get("stck_bsop_date")) == ymd:
            close = _num(r.get("stck_clpr"), int)
            return close if close and close > 0 else None
    return None


def fetch_reg_closes(cfg, codes):
    """그 회차 정규장 종가 {code: 종가} — 정규장(J) 일봉에서. 쥔 것은 다시 안 묻는다. 못 받은 종목은 빠진다(0 으로 넣지 않는다).

    KIS 오류 · 그 날 줄이 없는 종목은 쥐지 않는다 — 다음에 다시 묻는다."""
    day = reg_session_day()
    if not day:
        return {}, None
    # 받는 중인 종목은 다른 요청(같은 순간 들어온 순위표 · 15:40 미리 받기 바퀴)이 다시 묻지 않는다 — 기다리지 않고 빼고 돌려준다.
    # 재시작 직후 · 15:40 처럼 쥔 것이 없을 때 요청마다 같은 종목 일봉을 겹쳐 물어 KIS 를 몇 배로 쓰던 자리(qa 덧말 · 2026-10-28).
    with _reg_lock:
        have = {c: v[1] for c, v in ((c, _reg_close.get(c)) for c in codes) if v and v[0] == day}
        mine = [c for c in dict.fromkeys(codes) if c not in have and c not in _reg_inflight]
        _reg_inflight.update(mine)
    try:
        for code in mine:
            try:
                close = _reg_close_daily(cfg, code, day)
            except RuntimeError as e:
                print("[장외] 정규장 종가 못 받음 %s: %s" % (code, safe_message(e)), flush=True)
                continue
            if not close:
                continue
            have[code] = close
            with _reg_lock:
                _reg_close[code] = (day, close)
                if len(_reg_close) > 3000:          # 지난 회차 것을 걷는다
                    for c in [c for c, v in _reg_close.items() if v[0] != day]:
                        _reg_close.pop(c, None)
    finally:
        with _reg_lock:
            _reg_inflight.difference_update(mine)
    return have, day


# 정규장 중(09:00~15:30) 「장외」 칩은 **전날 20:00 애프터 마감 값**을 그대로 보였다 — 2026-11-05 에 07:00~15:30 빈 칸으로 바뀜(after_cleared). 아래는 밤사이 값을 쥐는 까닭으로 남는다
# (2026-10-26 재권님 「다음 장 시작전의 종가로 해줘」 → 「전날 20 시에 멈추는걸로 해줘」 · 작업우선순위 경유 —
# 아침 프리마켓(08:00~08:50) 몫은 안 넣는다). 정규장 중에는 통합 시세가 장중 값이라 그때 물어서는 못 얻는다 —
# 그래서 **애프터가 끝난 뒤(AFTER_SNAP_AT) 한 번** 순위 목록 전부(dart.universe_rows · 시가총액 dart.UNIVERSE_MIN_CAP_EOK 이상 ·
# 통합 멀티 12건)를 받아 쥐고 파일에도 남긴다(재시작해도 남게). 그 시각에 꺼져 있었으면 프리마켓이 열리기 전
# (08:00 전)까지 · 주말 동안 늦게라도 받는다 — 그 사이 통합 시세는 20:00 마감 값 그대로라서다.
# 못 받았으면 그날은 값이 없다 — 화면이 「못 받았다」 로 적는다(0 으로 채우지 않는다).
AFTER_SNAP_AT = (20, 1)
NXT_PRE_OPEN = (8, 0)           # 넥스트레이드 프리마켓 시작 — 이때부터는 20:00 값이 아니다
AFTER_SNAP_RETRY_SEC = 600      # 못 받았으면(0종목 · 오류) 10분 뒤 다시 — 그 사이 KIS 를 두드리지 않는다
AFTER_SNAP_PATH = os.path.join(HOLDINGS_DIR, ".after-snap.json")
_after_snap = {"day": None, "at": None, "rows": {}}


def _load_after_snap():
    try:
        with open(AFTER_SNAP_PATH, encoding="utf-8") as f:
            j = json.load(f)
        if isinstance(j, dict) and isinstance(j.get("rows"), dict):
            _after_snap.update(day=j.get("day"), at=j.get("at"), rows=j["rows"])
    except (OSError, ValueError):
        pass


def take_after_snap(cfg):
    """애프터 마감(20:00) 뒤 순위 목록의 장외 값을 받아 쥔다. 받은 종목 수를 돌려준다.

    **0종목이면 쥐지도 파일에 남기지도 않는다** — 그날로 적으면 그 밤 다시 안 받아 다음 정규장 중 칸이 통째로 빈다
    (qa 검수 · 20:01 에 KIS 오류가 나는 경우). 다시 받는 간격은 고리가 정한다(AFTER_SNAP_RETRY_SEC)."""
    codes = [r["stock_code"] for r in dart.universe_rows(None)]
    if not codes:
        return 0
    quotes, _errors = fetch_quotes_multi(cfg, codes)       # 20:01 뒤는 통합(UN) — regClose · regPct 가 붙어 온다
    rows = {c: {"price": q.get("price"), "regClose": q["regClose"], "regPct": q["regPct"], "regDate": q.get("regDate")}
            for c, q in quotes.items() if q.get("regPct") is not None}
    if not rows:
        return 0
    now = datetime.now(KST)
    snap = {"day": reg_session_day(now), "at": now.strftime("%H:%M"), "rows": rows}
    _after_snap.update(snap)
    try:
        write_json_atomic(AFTER_SNAP_PATH, snap, indent=None)
    except Exception as e:
        print("[장외] 장 시작 전 값 저장 못 함 (%s)" % type(e).__name__, flush=True)
    return len(rows)


def start_after_snap(cfg):
    """애프터 마감 뒤 한 번 장외 값을 받는다(회차마다 한 번). 키가 없으면 안 돈다."""
    _load_after_snap()
    if not cfg:
        return False

    def loop():
        tried = 0.0                               # 마지막으로 받아 본 때 — 못 받았으면 AFTER_SNAP_RETRY_SEC 뒤 다시
        warmed = None                             # 정규장 종가를 미리 받아 둔 회차
        while True:
            now = datetime.now(KST)
            hm = (now.hour, now.minute)
            sday = reg_session_day(now)
            if sday and sday == now.date().isoformat() and warmed != sday:     # 그 날 15:40 뒤 한 번 — 순위 목록 종목 종가
                warmed = sday
                try:
                    codes = [r["stock_code"] for r in dart.universe_rows(None)]
                    have, _d = fetch_reg_closes(cfg, codes)
                    print("[장외] 정규장 종가 %d/%d종목 받음 (%s)" % (len(have), len(codes), now.strftime("%H:%M")), flush=True)
                except Exception as e:
                    print("[장외] 정규장 종가 미리 받기 못 함 (%s)" % type(e).__name__, flush=True)
            today = reg_session_day(now)          # 이 장외 값이 붙는 정규장 날
            # 그 회차 저녁 20:01~24:00 에만 받는다. 자정이 지나면 KIS 통합 시세가 20:00 마감 값이 아니다
            # (2026-10-28 07:5x 실측 — 아래 `overnight_row`). 전에는 08:00 전 · 주말에도 늦게 받았는데 그때 받으면 틀린 값을 쥔다
            quiet = today == now.date().isoformat() and hm >= AFTER_SNAP_AT
            if (quiet and today and _after_snap.get("day") != today
                    and time.time() - tried >= AFTER_SNAP_RETRY_SEC):
                tried = time.time()
                try:
                    n = take_after_snap(cfg)
                    print("[장외] 20:00 장외 마감 값 %d종목 받음 (%s)" % (n, now.strftime("%H:%M")), flush=True)
                except Exception as e:
                    print("[장외] 20:00 장외 마감 값 못 받음 (%s)" % type(e).__name__, flush=True)
            time.sleep(20)

    threading.Thread(target=loop, daemon=True, name="after-snap").start()
    return True


# 「장외」 칩은 평일 아침 07:00 에 비우고 정규장이 끝날 때(15:30)까지 빈 칸이다 (2026-11-05 재권님 「실시간 목록에 장외는 본장이
# 시작하면 리셋해줘야 하는데 … 아침 7시에 리셋되게 해줘」 → (가) 「15:30 애프터가 열릴 때까지 빈 칸」 · 작업우선순위 경유).
# 전에는 정규장 중에 앞 회차 20:00 장외 마감 값을 얼려 실었다(attach_after_snap · 10-26 「전날 20 시에 멈추는걸로」) — 그것을 걷어냈다.
# 밤사이(00:00~07:00) 값은 그대로 어제 20:00 마감 값이다(overnight_quotes · take_after_snap 이 쥔 것).
# 07:00~08:00(프리장 전)은 국내 종목을 어제 정규장 종가 · 등락률 0 으로 낸다 — 새 회차 기준가가 그 종가다
# (2026-11-06 재권님 「아침 7시 되면 … 국내종목은 등락률이 0이 되어야」 → (가) 「값도 어제 정규장 종가로 · 0%」)
AFTER_CLEAR_AT = (int(market_hours.CHIP_RESET[:2]), int(market_hours.CHIP_RESET[2:]))   # 07:00 → 07:30 — 다른 칩과 한 시각(11-13 재권님 「장외도 7시반」)
AFTER_CLEAR_UNTIL = (15, 30)


def after_cleared(now=None):
    """지금 「장외」 값을 비워 둘 때인가 — 평일 07:00~15:30. 공휴일은 아직 안 가른다."""
    now = now or datetime.now(KST)
    return now.weekday() < 5 and AFTER_CLEAR_AT <= (now.hour, now.minute) < AFTER_CLEAR_UNTIL


def attach_reg_close(cfg, out):
    """통합 시세 묶음에 regClose · regPct · regDate 를 붙인다. 종가를 못 받은 종목은 칸을 안 만든다."""
    closes, day = fetch_reg_closes(cfg, list(out))
    for code, q in out.items():
        close = closes.get(code)
        price = q.get("price")
        if not close or not price:
            continue
        q["regClose"] = close
        q["regPct"] = round((price / close - 1) * 100, 2)
        q["regDate"] = day


# 자정 뒤 넥스트레이드 프리마켓(08:00) 전에는 KIS 통합(UN) 시세가 **어제 20:00 넥장 마감 값이 아니다** (2026-10-28 07:5x 실측 · 8765).
#   삼성전자 222,000 · SK하이닉스 1,341,000 · 삼성전자우 171,100  ↔  어제 20:01 받아 둔 224,500 · 1,374,000 · 173,400
#   그 시간에 전일 대비 0 · 시가 · 거래량 0 이 함께 온다
# 그 값이 무엇인지는 못 가렸다. 그대로 쓰면 장외 칩 등락률이 내린 것으로 나오고, 차트 마지막 5분봉이 그 값으로 끌려 내려가
# 긴 음봉이 된다 — 재권님 「장전에 음봉 길게 나오는건 이상한거 같은데」 · 「삼성 하이닉스도 많이 올랐는데 제대로 안나오는데」 →
# 「00:00~08:00 은 어제 20:01 받아 둔 값을 시세로」 에 「응」(2026-10-28).
# 그래서 그때는 20:01 에 받아 둔 값(`_after_snap` · 순위 목록 종목)으로 지금가를 덮는다. 받아 둔 것이 없는 종목은 그대로 둔다.
#   지금가 = 20:00 넥장 마감 · 기준(prev) = 그 회차 정규장 종가 · 등락 = 종가 대비 — 08:00 프리마켓이 열리면 전일 대비의 기준이 바로 그 종가다
#   거래량 · 시가 · 고가 · 저가는 받아 둔 것이 없어 **None**(0 이 아니다 — 못 받은 값)
# 주말 · 월요일 새벽도 같다(금요일 20:01 값). 넥스트레이드가 쉬는 때라 값이 안 바뀐다.
# **확인 못 한 것** — 지수(코스피 · 코스닥)도 그 시간 전일 대비 0 이 오는데 받아 둔 것이 없어 이 셈 밖이다.
def overnight_row(code, now=None):
    """자정 뒤 08:00 전이면 그 종목의 어제 20:00 넥장 마감 값(받아 둔 것). 아니면 None."""
    now = now or datetime.now(KST)
    day = reg_session_day(now)
    if not day or now.date().isoformat() == day:          # 그 회차 저녁(자정 전)은 통합 시세가 맞다
        return None
    if now.weekday() < 5 and (now.hour, now.minute) >= NXT_PRE_OPEN:
        return None
    if _after_snap.get("day") != day:
        return None
    r = (_after_snap.get("rows") or {}).get(code)
    if not r or not r.get("price") or not r.get("regClose"):
        return None
    return r


def overnight_quotes(out, now=None):
    """멀티 시세 묶음({code: {...}})을 밤사이 받아 둔 값으로 덮는다."""
    for code, q in out.items():
        r = overnight_row(code, now)
        if not r:
            continue
        close = r["regClose"]
        price, pct = (close, 0.0) if after_cleared(now) else (r["price"], r["regPct"])
        q.update(price=price, prev=close, amt=price - close, pct=pct,
                 open=None, high=None, low=None, volume=None, value=None,
                 regClose=close, regPct=r["regPct"], regDate=r.get("regDate"), overnight=_after_snap.get("day"))


def overnight_price(code, o, now=None):
    """단건 시세(fetch_price 모양)를 밤사이 받아 둔 값으로 덮는다."""
    r = overnight_row(code, now)
    if not r:
        return
    close = r["regClose"]
    price, pct = (close, 0.0) if after_cleared(now) else (r["price"], r["regPct"])
    change = price - close
    o.update(price=price, change=change, changePct=pct,
             sign="2" if change > 0 else ("5" if change < 0 else "3"),
             open=None, high=None, low=None, volume=None, value=None, overnight=_after_snap.get("day"))


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
# 가집계가 들어오는 시각(KIS 설명 · ±10분) — 화면이 「다음 입력」 을 이 값으로 적는다(「매수」 칩 · 2026-11-05)
INVESTOR_EST_SLOTS = {"foreign": ("09:30", "11:20", "13:20", "14:30"), "inst": ("10:00", "11:20", "13:20", "14:30")}
INVESTOR_FLOW_TTL = 600    # 일별 자료라 장중에 한 번 바뀐다
INVESTOR_FLOW_DAYS = 30    # 화면이 보여주는 기간

_sector_cache = {}
_us_sector_cache = {}          # 「지금 뜨는 산업」 미국 칸 — 기간 · 섹터:기간 → (시각, 값)
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
                # 기관 세부 · 기타법인 · 외국인 등록/미등록 — 같은 응답에 있다(docs/kis-sector-investor.md 3절 · 2026-11-04 flow_board 가 씀)
                "detail": {p: _investor_side(r, p) for p in flow_board.DETAIL},
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
ASKING_TTL = 3              # 호가는 계속 움직인다. **화면이 이 값을 받아 그 주기로 돈다** (2026-10-02 · 재권님 「나」)

_investor_cache = {}
_asking_cache = {}


def fetch_investor(cfg, code, days=INVESTOR_DAYS):
    """종목별 투자자 매매. 개인 · 외국인 · 기관이 한 응답에 온다.

    30일치가 한 번에 오고 그보다 길게는 못 받는다 (2026-09-16 실측).
    """
    cached = _ttl_get(_investor_cache, code, INVESTOR_TTL)
    if cached is not None:
        return cached
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
                # 매수 · 매도 **금액**(백만원) — 투자자 지표 모달의 양쪽 막대 (2026-10-15 · KIS 가 이미 주던 칸)
                "buyAmt": _num(r.get(prefix + "_shnu_tr_pbmn"), int),
                "sellAmt": _num(r.get(prefix + "_seln_tr_pbmn"), int),
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


# ── 투자자 3달 — 마감 뒤 두 번 받아 쌓는다 (2026-10-15 재권님 「응」) ──────────
#
# 위 `fetch_investor`(FHKST01010900)는 30거래일까지만 준다. 「3달」(60거래일)은
# **종목별 투자자매매동향(일별)** FHPTJ04160001 로 받는다 — 한 번에 30거래일이
# 오고 `FID_INPUT_DATE_1` 을 앞으로 옮기면 그 날부터 거슬러 준다(2026-10-14 15:4x 실측).
#
# **00:00 ~ 15:40 에는 거절된다** — 응답 `TIME LIMIT 00:00 ~ 15:40`(2026-10-15 10:36 실측).
# 그래서 15:40 뒤 그 종목을 처음 열 때 두 번 불러 `investor_daily` 에 쌓고, 그 날은 다시
# 부르지 않는다. 그 밖 시각에는 쌓인 것만 읽는다 — 장중에 「3달」 을 눌러도 KIS 를 안 부른다.
# 모든 종목을 미리 받지 않는다 — 열어 본 종목만 하루 두 번이다.
INVESTOR_LONG_DAYS = 60          # 「3달」 이 더하는 거래일 수
INVESTOR_LONG_OPEN = (15, 41)    # 이 시각부터 받는다 — 15:40:00~05 에도 아직 거절됐다(2026-10-27 8765 · 30종목 OPSQ2001 · 10분 뒤 다시 받기로 채워짐)
INVESTOR_LONG_RETRY = 600        # 못 받았으면 이만큼 쉬었다 다시 (초)
_inv_long_fail = {}              # code -> 못 받은 시각
# 아래 `SCHEMA` 에도 들지만 `db_init` 이 서버가 뜰 때 늘 도는 것은 아니라 쌓을 때 한 번 더 부른다
INVESTOR_DAILY_SQL = """CREATE TABLE IF NOT EXISTS investor_daily (
         code TEXT NOT NULL,
         date TEXT NOT NULL,
         row  TEXT NOT NULL,
         PRIMARY KEY (code, date)
       )"""
_inv_long_lock = threading.Lock()


# 기관 세부 · 외국인 등록/미등록 (2026-10-27 재권님 「응 해줘」 · 투자자 세분화) — FHPTJ04160001 에만 온다.
# 칸 이름이 갈래마다 다르다 — 사모 · 기타기관 · 기타법인은 `_ntby_vol` 이고 나머지는 `_ntby_qty`(2026-10-26 실측).
# 그래서 둘 다 본다. 없는 칸은 None — 0 으로 바꾸지 않는다
INV_INST_DETAIL = (("scrt", "증권"), ("ivtr", "투신"), ("pe_fund", "사모"), ("bank", "은행"),
                   ("insu", "보험"), ("mrbn", "종금"), ("fund", "기금"), ("etc_orgt", "기타기관"))
INV_DETAIL_KEYS = ("instDetail", "foreignReg", "foreignNreg", "etcCorp")   # 줄에 붙는 열쇠 — 없는 날은 None


def _inv_net(r, prefix):
    qty = r.get(prefix + "_ntby_qty")
    if qty is None:
        qty = r.get(prefix + "_ntby_vol")
    return {"net": _num(qty, int), "netAmt": _num(r.get(prefix + "_ntby_tr_pbmn"), int)}


def _inv_long_row(r):
    def side(prefix):
        return {
            "net": _num(r.get(prefix + "_ntby_qty"), int),
            "netAmt": _num(r.get(prefix + "_ntby_tr_pbmn"), int),
            "buy": _num(r.get(prefix + "_shnu_vol"), int),
            "sell": _num(r.get(prefix + "_seln_vol"), int),
            "buyAmt": _num(r.get(prefix + "_shnu_tr_pbmn"), int),     # 백만원 — 위 fetch_investor 와 같은 칸
            "sellAmt": _num(r.get(prefix + "_seln_tr_pbmn"), int),
        }
    return {
        "date": r.get("stck_bsop_date"),
        "close": _num(r.get("stck_clpr"), int),
        "amt": _num(r.get("prdy_vrss"), int),
        "person": side("prsn"),
        "foreign": side("frgn"),
        "inst": side("orgn"),
        "instDetail": {k: _inv_net(r, k) for k, _n in INV_INST_DETAIL},
        "foreignReg": _inv_net(r, "frgn_reg"),
        "foreignNreg": _inv_net(r, "frgn_nreg"),
        "etcCorp": _inv_net(r, "etc_corp"),
    }


def _inv_long_page(cfg, code, ymd):
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily",
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
         "FID_INPUT_DATE_1": ymd, "FID_ORG_ADJ_PRC": "", "FID_ETC_CLS_CODE": ""},
        "FHPTJ04160001",
    )
    if not isinstance(data, dict) or str(data.get("rt_cd")) != "0":
        return None
    rows = [_inv_long_row(r) for r in out_rows(data, "output2")]
    return [r for r in rows if r["date"]]


def _inv_long_fetch(cfg, code):
    """15:40 뒤 하루 한 번 두 쪽(60거래일)을 받아 쌓는다. 쌓았으면 True."""
    import datetime
    now = datetime.datetime.now(KST)
    today = now.strftime("%Y%m%d")
    key = "inv60d:" + code      # 세부 칸이 붙은 판(10-27) — 옛 열쇠 `inv60:` 로 쌓인 날도 한 번 다시 받는다
    if (now.hour, now.minute) < INVESTOR_LONG_OPEN or not marketdb.writable():
        return False
    if _meta_get(key) == today:
        return False
    if time.time() - _inv_long_fail.get(code, 0) < INVESTOR_LONG_RETRY:
        return False
    with _inv_long_lock:
        if _meta_get(key) == today:
            return False
        got = []
        ymd = today
        broken = False
        for _ in range(2):
            page = _inv_long_page(cfg, code, ymd)
            # **두 쪽을 다 받았을 때만 쌓는다** (2026-10-15 qa · 재권님 「응 해」) — 둘째 쪽이
            # 실패한 채 30줄만 쌓이면 아래 「이어지나」 판정이 헛돈다. 빈 쪽(`[]`)은 상장이 짧아
            # 더 없는 것이라 실패가 아니다
            if page is None:
                broken = True
                break
            if not page:
                break
            got.extend(page)
            oldest = min(r["date"] for r in page)
            ymd = (datetime.datetime.strptime(oldest, "%Y%m%d")
                   - datetime.timedelta(days=1)).strftime("%Y%m%d")
        # 확정치가 빈 줄(net 이 셋 다 None)은 안 쌓는다 — 다음 날 다시 받는다
        keep = [r for r in got
                if any(r[s]["net"] is not None for s in ("person", "foreign", "inst"))]
        if broken or len(keep) < INVESTOR_DAYS:
            _inv_long_fail[code] = time.time()
            print("[투자자 3달] %s 못 받음(%d줄) — %d초 뒤 다시"
                  % (code, len(keep), INVESTOR_LONG_RETRY))
            return False
        try:
            with _db_lock, db_conn() as conn:
                conn.execute(INVESTOR_DAILY_SQL)
                conn.executemany(
                    "INSERT OR REPLACE INTO investor_daily (code, date, row) VALUES (?, ?, ?)",
                    [(code, r["date"], json.dumps(r, ensure_ascii=False)) for r in keep])
        except sqlite3.Error as e:
            _inv_long_fail[code] = time.time()
            print("[투자자 3달] %s 쓰기 실패 — %s" % (code, safe_message(e, 120)))
            return False
        _meta_set(key, today)
        _inv_long_fail.pop(code, None)
        return True


def _inv_long_read(code, upto, limit):
    """`upto` 날짜와 그보다 앞의 쌓인 줄을 새것부터 `limit` 개. 표가 없으면 빈 목록."""
    try:
        with _db_lock, db_conn() as conn:
            rs = conn.execute(
                "SELECT row FROM investor_daily WHERE code = ? AND date <= ? "
                "ORDER BY date DESC LIMIT ?", (code, upto, limit)).fetchall()
    except sqlite3.Error:
        return []
    return [json.loads(r["row"]) for r in rs]


def _inv_attach_detail(code, rows):
    """30거래일 줄(FHKST01010900 · 세부 없음)에 쌓인 같은 날 세부를 붙인다 — 받은 줄은 안 건드리고 새 줄로.

    세부는 마감 뒤 확정치라 장중 오늘 줄 · 아직 안 쌓인 날은 None 이다(0 으로 채우지 않는다)."""
    dates = [r["date"] for r in rows if r.get("date")]
    got = {}
    if dates:
        try:
            with _db_lock, db_conn() as conn:
                rs = conn.execute(
                    "SELECT date, row FROM investor_daily WHERE code = ? AND date BETWEEN ? AND ?",
                    (code, min(dates), max(dates))).fetchall()
        except sqlite3.Error:
            rs = []
        for x in rs:
            d = json.loads(x["row"])
            if d.get("instDetail") is not None:
                got[x["date"]] = d
    out = []
    for r in rows:
        d = got.get(r.get("date"))
        nr = dict(r)
        for k in INV_DETAIL_KEYS:
            nr[k] = d.get(k) if d else None
        out.append(nr)
    return out


# ── 증권사 매매 상위 5 (2026-10-27 재권님 「응 해줘」 · 투자자 세분화 ②) ──────────
# FHKST01010600(inquire-member) — 오늘 장중 누적. 매도 · 매수 상위 다섯 회원사와 외국계 합.
# 장중에도 온다(10-27 11:3x 실측 · 8765 넘기기). KRX 회원사라 시장은 `J`.
INVESTOR_MEMBER_TTL = 60
_investor_member_cache = {}
# 외국계 창구 「최근 5분」 — KIS 는 오늘 누적만 준다. 받을 때마다 누적을 쌓아 두고 지금 − 5분 전으로 센다
# (2026-11-10 재권님 「외국계 창구도 세로굵은줄 넣어줘」 → 안 「응」). 그 종목을 누가 볼 때만 받으므로 처음 5분은 recent 가 없다.
# 이 창 길이를 foreignFirms.windowSec 으로 내주고 바닥 줄(flow-foot.js)이 프로그램 칸 셈에도 그것을 읽는다 — 값은 여기 한 곳
MEMBER_RECENT_SEC = 300
_member_snaps = {}                          # code → (그날 날짜, [(시각초, 매수 누적, 매도 누적), …])


def fetch_investor_member(cfg, code):
    cached = _ttl_get(_investor_member_cache, code, INVESTOR_MEMBER_TTL)
    if cached is not None:
        return cached
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-member",
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
        "FHKST01010600",
    )
    if not isinstance(data, dict) or str(data.get("rt_cd")) != "0":
        return None
    o = data.get("output")
    o = (o[0] if o else {}) if isinstance(o, list) else (o or {})

    def side(pfx):
        out = []
        for i in range(1, 6):
            name = (o.get("%s_mbcr_name%d" % (pfx, i)) or "").strip()
            if not name:
                continue
            out.append({
                "no": o.get("%s_mbcr_no%d" % (pfx, i)),
                "name": name,
                "qty": _num(o.get("total_%s_qty%d" % (pfx, i)), int),
                "pct": _num(o.get("%s_mbcr_rlim%d" % (pfx, i))),
                "chg": _num(o.get("%s_qty_icdc%d" % (pfx, i)), int),     # 직전 조회 대비 늘어난 수량 — KIS 가 주는 그대로
                "foreign": o.get("%s_mbcr_glob_yn_%d" % (pfx, i)) == "Y",
            })
        return out

    out = {
        "sell": side("seln"),
        "buy": side("shnu"),
        "foreignFirms": {
            "sell": _num(o.get("glob_total_seln_qty"), int),
            "buy": _num(o.get("glob_total_shnu_qty"), int),
            "net": _num(o.get("glob_ntby_qty"), int),
            "sellPct": _num(o.get("glob_seln_rlim")),
            "buyPct": _num(o.get("glob_shnu_rlim")),
            "windowSec": MEMBER_RECENT_SEC,     # 「최근」 창 길이 — 바닥 줄 원이 프로그램 · 창구 둘 다 이 값으로 센다(2026-11-10 개념정의 검수)
        },
        "volume": _num(o.get("acml_vol"), int),
        "at": datetime.now(KST).strftime("%H:%M"),     # KIS 에서 받은 시각 — 큰 차트 바닥 줄이 「정보가 들어온 시각」 으로 쓴다(2026-11-03)
    }
    ff = out["foreignFirms"]
    now = time.time()
    day = datetime.now(KST).strftime("%Y-%m-%d")
    d, snaps = _member_snaps.get(code) or (day, [])
    if d != day:
        snaps = []
    if ff["buy"] is not None and ff["sell"] is not None:
        snaps.append((now, ff["buy"], ff["sell"]))
    snaps = [x for x in snaps if x[0] >= now - MEMBER_RECENT_SEC * 3]
    _member_snaps[code] = (day, snaps)
    old = [x for x in snaps if x[0] <= now - MEMBER_RECENT_SEC]
    ff["recent"] = None
    if old and ff["buy"] is not None and ff["sell"] is not None:
        b0, s0 = old[-1][1], old[-1][2]
        rb, rs = ff["buy"] - b0, ff["sell"] - s0
        if rb >= 0 and rs >= 0:             # 누적이 줄었으면(KIS 값 흔들림) 셈하지 않는다 — 없음으로 둔다
            ff["recent"] = {"buy": rb, "sell": rs, "sec": int(now - old[-1][0])}
    _investor_member_cache[code] = (now, out)
    return out


HF_SHARE_DAYS = 20                          # 누적 순매수 칸 「거래 몫」 을 세는 최근 거래일 수


def holding_flow(cfg, code):
    """투자자별 누적 순매수(%p) — 차트 보조지표 「누적 순매수」 칸 (2026-10-26 재권님 「다」 · 작업우선순위 경유).

    **보유비중이 아니다.** 거래소는 종목별로 외국인 보유만 집계하고 기관 · 개인 보유 비중은 공개 출처가 없다(10-26 조사).
    그래서 셋을 같은 잣대로 — 셈 첫날부터 사들인 주식(순매수 수량 합) ÷ 상장주식수 × 100. 첫날 앞까지는 0 에서 시작한다.
    줄은 `fetch_investor_long` 그대로(확정치 · 3달 · 쓰는 서버가 날마다 쌓는다) — 장중 오늘 빈 줄은 뺀다.
    상장주식수를 못 받으면 셈하지 않고 None(0 으로 나누지 않는다)."""
    rows = [r for r in (fetch_investor_long(cfg, code, INVESTOR_LONG_DAYS) or [])
            if r.get("date") and all((r.get(k) or {}).get("net") is not None for k in ("foreign", "inst", "person"))]
    listed = (fetch_price(cfg, code) or {}).get("listed")
    if not rows or not listed:
        return None
    rows.sort(key=lambda r: r["date"])
    # 주체별 비율 — 최근 HF_SHARE_DAYS 거래일 셋이 사고판 금액(매수 + 매도) 합에서 각자 몫(%) · 셋 합 100 · 기타법인은 안 셈
    # (2026-11-06 재권님 「차트에 누적 순매수에 주체별 비율도 있어야해」 → 「각각 그래프선 끝에 넣어」 · chart.js drawHfEnds)
    # 금액이 빈 줄은 빼고 센다 · 남는 줄이 없거나 합이 0 이면 None(0% 로 내지 않는다)
    tail = [r for r in rows if all((r.get(k) or {}).get("buyAmt") is not None and (r.get(k) or {}).get("sellAmt") is not None
                                   for k in ("foreign", "inst", "person"))][-HF_SHARE_DAYS:]
    vol = {k: sum(r[k]["buyAmt"] + r[k]["sellAmt"] for r in tail) for k in ("foreign", "inst", "person")}
    tot = sum(vol.values())
    share = {**{k: round(v / tot * 100, 1) for k, v in vol.items()}, "days": len(tail)} if tail and tot > 0 else None
    acc = {"foreign": 0, "inst": 0, "person": 0}
    out = []
    for r in rows:
        for k in acc:
            acc[k] += r[k]["net"]
        out.append({"date": r["date"], **{k: round(v / listed * 100, 4) for k, v in acc.items()}})
    return {"start": out[0]["date"], "listed": listed, "rows": out, "share": share}


def fetch_investor_long(cfg, code, days=INVESTOR_LONG_DAYS):
    """30거래일(`fetch_investor`) 뒤에 쌓인 옛 줄을 이어 확정치 `days` 거래일(+ 장중 오늘 빈 줄)까지.

    맨 앞은 그대로 `fetch_investor` 다 — 장중 오늘 줄(`net: null`)도 그대로 온다.
    화면이 오늘을 건너뛸 수 있게 한 줄 더 붙인다. 쌓인 것이 없으면 30거래일만 간다.
    """
    base = fetch_investor(cfg, code)
    try:
        _inv_long_fetch(cfg, code)
    except Exception as e:                       # 받기가 터져도 30거래일은 낸다
        _inv_long_fail[code] = time.time()
        print("[투자자 3달] %s 받다 멈춤 — %s" % (code, safe_message(e, 120)))
    # 30거래일을 못 받았으면 쌓인 줄만 내지 않는다 — 어디서 끊겼는지 가를 기준이 없다(3달 전과 같다)
    if not base or not any(r.get("date") for r in base):
        return base
    oldest = min(r["date"] for r in base if r.get("date"))
    # 붙일 줄 수는 **확정치 줄**로 센다 — 장중 오늘 빈 줄은 화면이 건너뛴다. 이렇게 세면 붙이는 줄은
    # `base` 맨 옛날을 품은 묶음(60줄) 안에서 늘 끝난다 — 묶음 밖 한 줄이 빈틈 너머에서 붙지 않는다
    confirmed = sum(1 for r in base
                    if any((r.get(s) or {}).get("net") is not None for s in ("person", "foreign", "inst")))
    need = max(0, days - confirmed)
    if not need:
        return base
    # **날짜가 이어질 때만 붙인다** (2026-10-15 qa 걸림 · 재권님 「응 해」). 쌓인 줄을 그냥
    # 붙이면 오래전에 받은 묶음이 석 달을 건너뛰어 붙었다(09-01 · 08-31 → 05-20).
    # 한 번에 받은 60줄은 이어진 거래일이라, `base` 맨 옛날과 **같은 날**이 쌓여 있으면
    # 그 묶음이 그 아래 30거래일을 빈틈없이 덮는다 — 달력 표 없이 가른다. 없으면 30거래일만
    rs = _inv_long_read(code, oldest, need + 1)
    if not rs or rs[0].get("date") != oldest:
        return base
    return base + rs[1:]


# ── 투자자 지표 모달 「그래프」 판 — 서버가 들고 있다 내준다 (2026-10-16 재권님 「정보 받아서 들고있어야」 · 「응」) ──
#
# 전에는 모달이 열릴 때마다 화면이 시세 18묶음을 차례로 묻고 그 뒤 상위 종목의 투자자 줄을 물었다 —
# 여는 데 3~3.5초, 그중 시세 묶음이 2.3~3.4초였다(10-16 12:05 · 8765 실측). 이제 서버가 거래대금 순
# 판을 하나 들고 있다가 `/api/kis/investor-board` 한 주소로 내준다.
#   판이 PRICE_CACHE_TTL 보다 낡았으면  들고 있던 판을 **먼저 내주고** 뒤에서 다시 짓는다
#   판이 없거나 INVESTOR_BOARD_STALE_TTL 보다 낡았으면  그 자리에서 짓는다(서버가 막 떴을 때 · 오래 쉰 뒤)
# 시세는 `fetch_quotes_multi` · 투자자 줄은 `fetch_investor_long` 그대로 — 서버 캐시를 함께 쓴다.
# 서버가 뜰 때 한 번 미리 짓는다(`--slow` 는 안 함).
# **장중(평일 정규장)에는 INVESTOR_BOARD_REFRESH_INTERVAL 마다 뒤에서 다시 짓는다** (2026-11-05 재권님 「응 해줘」) —
# 묻는 사람이 있을 때만 짓던 때는 판이 STALE_TTL 을 넘기면 첫 여는 사람이 그 자리에서 5초를 기다렸다
# (11-05 10:18 · 8772 실측 — 시세 350종목 30개씩 열두 묶음 1.53초 + 상위 30여 종목 투자자 줄). 한 번 짓는 데 KIS 42건쯤.
# 장 밖에는 안 돈다 — 값이 안 바뀐다.
INVESTOR_BOARD_TOP = 15            # 시장마다 줄 수 (화면 그래프 탭)
INVESTOR_BOARD_STALE_TTL = 300     # 이보다 낡은 판은 먼저 내주지 않고 다시 지어 낸다 (초)
INVESTOR_BOARD_MARKETS = ("ALL", "KOSPI", "KOSDAQ")
INVESTOR_BOARD_WORKERS = 6         # 투자자 줄을 동시에 받는 수 — 호출 간격은 kis_get 이 지킨다
INVESTOR_BOARD_REFRESH_INTERVAL = INVESTOR_BOARD_STALE_TTL - 60   # 장중 뒤에서 다시 짓는 주기 (초) — 바퀴가 30초마다 깨고 짓는 데 몇 초 걸려도 판 나이가 STALE_TTL 을 안 넘게 60초 앞당김(개념정의 검수 덧)
_inv_board = {"at": 0.0, "data": None}
_inv_board_lock = threading.Lock()         # 판을 읽고 바꾸는 자리
_inv_board_build = threading.Lock()        # 짓는 것은 한 번에 하나


def _investor_board_make(cfg):
    """거래대금 순 판을 새로 짓는다. 시장마다 상위 INVESTOR_BOARD_TOP 과 그 종목들의 투자자 줄."""
    import concurrent.futures
    uni = [r for r in dart.universe_rows(None)
           if (r["stock_code"] or "").isdigit() and len(r["stock_code"]) == 6]
    quotes, errors = fetch_quotes_multi(cfg, [r["stock_code"] for r in uni])
    items = []
    for r in uni:
        q = quotes.get(r["stock_code"]) or {}
        if not q.get("value"):
            continue
        items.append({"code": r["stock_code"], "name": q.get("name") or r["name"], "market": r["market"],
                      "value": q["value"], "price": q.get("price"), "pct": q.get("pct")})
    items.sort(key=lambda x: -x["value"])
    tops = {m: [x for x in items if m == "ALL" or x["market"] == m][:INVESTOR_BOARD_TOP]
            for m in INVESTOR_BOARD_MARKETS}
    need = list(dict.fromkeys(x["code"] for m in INVESTOR_BOARD_MARKETS for x in tops[m]))
    inv = {}
    with concurrent.futures.ThreadPoolExecutor(INVESTOR_BOARD_WORKERS) as ex:
        for code, rows in zip(need, ex.map(lambda c: fetch_investor_long(cfg, c, INVESTOR_LONG_DAYS), need)):
            inv[code] = rows or []
    return {"tops": tops, "inv": inv,
            "names": {r["stock_code"]: (quotes.get(r["stock_code"]) or {}).get("name") or r["name"] for r in uni},
            "universe": len(uni), "quoted": len(quotes), "quoteErrors": len(errors or {})}


def _investor_board_rebuild(cfg, wait):
    """판을 다시 짓는다. wait=False 면 이미 짓는 중일 때 바로 돌아간다."""
    if not _inv_board_build.acquire(blocking=wait):
        return
    try:
        if wait:                    # 기다리는 사이 다른 쪽이 지었으면 그것을 쓴다
            with _inv_board_lock:
                if _inv_board["data"] is not None and time.time() - _inv_board["at"] < PRICE_CACHE_TTL:
                    return
        data = _investor_board_make(cfg)
        if data["quoted"]:          # 시세를 하나도 못 받았으면 들고 있던 판을 덮지 않는다
            with _inv_board_lock:
                _inv_board["at"], _inv_board["data"] = time.time(), data
    except Exception as e:
        print("[투자자 판] 짓다 멈춤 — %s" % safe_message(e, 120))
    finally:
        _inv_board_build.release()


def investor_board(cfg):
    """(판, 지은 시각). 판이 없으면 (None, 0)."""
    with _inv_board_lock:
        at, data = _inv_board["at"], _inv_board["data"]
    age = time.time() - at
    if data is not None and age < PRICE_CACHE_TTL:
        return data, at
    if data is not None and age < max(INVESTOR_BOARD_STALE_TTL, PRICE_CACHE_TTL):
        threading.Thread(target=_investor_board_rebuild, args=(cfg, False), daemon=True,
                         name="investor-board").start()
        return data, at
    _investor_board_rebuild(cfg, True)
    with _inv_board_lock:
        return _inv_board["data"], _inv_board["at"]


def start_investor_board_refresh(cfg):
    """장중에 그래프 판을 INVESTOR_BOARD_REFRESH_INTERVAL 마다 다시 짓는 바퀴. 키가 없으면 안 돈다."""
    if not cfg:
        return False

    def loop():
        while True:
            now = datetime.now(KST)
            if now.weekday() < 5 and KRX_OPEN <= (now.hour, now.minute) < KRX_CLOSE:
                with _inv_board_lock:
                    age = time.time() - _inv_board["at"]
                if age >= INVESTOR_BOARD_REFRESH_INTERVAL:
                    _investor_board_rebuild(cfg, False)
            time.sleep(30)

    threading.Thread(target=loop, daemon=True, name="investor-board-refresh").start()
    return True


# ── 재무 다섯 — 모달 「투자 지표」 칸 재무 카드 (2026-10-02 지시) ──────────
#
# 재권님 — 재무 카드 시안 v3 를 보시고 「방향이 맞아 개발해」.
#
#     손익계산서   FHKST66430200   /finance/income-statement
#     대차대조표   FHKST66430100   /finance/balance-sheet
#     재무비율     FHKST66430300   /finance/financial-ratio
#     수익성비율   FHKST66430400   /finance/profit-ratio
#     성장성비율   FHKST66430800   /finance/growth-ratio
#
# **분기로 받는다** — `FID_DIV_CLS_CODE` 0 = 년 · 1 = 분기(한국투자증권 공식 예제 저장소
# `open-trading-api` 의 `finance_income_statement` 주석). 한 번에 30분기(약 7년)가 온다.
#
# **단위는 억원이다.** KIS 문서에서는 못 찾았고 **실측으로 정했다** — 대차대조표 자본금
# (`cpfn`) 8,975 가 삼성전자 자본금 8,975억 원과 같다 (2026-10-02 12:03). 화면에 「억원」
# 으로 내보내고, 바뀌면 `meta.unit` 한 곳만 고친다.
#
# **손익은 연 누적으로 온다** — 2026.03 매출 1,338,734 → 2026.06 3,053,729.
# 그래서 분기 값 = 이번 누적 − 같은 해 앞 분기 누적 (1분기는 그대로). 앞 분기가 없으면
# **`None`** 이다 — 지어서 채우지 않는다. 누적 값도 `…Ytd` 로 함께 낸다.
# **비율(수익성 · 재무 · 성장성)은 KIS 가 준 그대로다** — 누적 기준으로 보이므로 화면이
# 「누적」 이라 적는다.
#
# **99.99 는 「없음」 이다.** 판관비 · 영업외수익 같은 세부 계정에 **그 글자 그대로** 와서
# 값이 아니라 표시로 본다(문서에서는 못 찾음). ⚠️ 비율이 정말 99.99 면 함께 지워진다 —
# 그 위험은 남는다.
#
# **수명은 `FINANCE_TTL` 하나다** — 분기 자료라 하루에 몇 번 부를 일이 없다. 화면에
# 박지 않는다(「캐시·주기·한도 값을 화면에 박지 않는다」). 넘기기 표(`RELAY_TTL_NAMES`)
# 도 같은 이름을 가리킨다.
FINANCE_TTL = 6 * 3600
_finance_cache = {}
FINANCE_NONE = "99.99"

_FIN_APIS = (
    ("income", "/uapi/domestic-stock/v1/finance/income-statement", "FHKST66430200"),
    ("balance", "/uapi/domestic-stock/v1/finance/balance-sheet", "FHKST66430100"),
    ("ratio", "/uapi/domestic-stock/v1/finance/financial-ratio", "FHKST66430300"),
    ("profit", "/uapi/domestic-stock/v1/finance/profit-ratio", "FHKST66430400"),
    ("growth", "/uapi/domestic-stock/v1/finance/growth-ratio", "FHKST66430800"),
)


def _fin_num(v):
    """KIS 재무 값 하나. **`99.99` 와 빈 값은 `None`** — 「없음」 을 `0` 으로 내지 않는다."""
    s = str(v if v is not None else "").strip()
    if not s or s == FINANCE_NONE:
        return None
    return _num(s, float)


def fetch_finance(cfg, code):
    """종목 하나의 분기 재무. 다섯 API 를 `stac_yymm`(결산 년월)로 합친다.

    **하나라도 못 받으면 그 칸만 `None`** 이고 나머지는 낸다. 어느 API 가 비었는지는
    `missing` 에 적는다 — 화면이 「데이터 없음」 을 그 카드에만 쓴다.
    """
    cached = _ttl_get(_finance_cache, code, FINANCE_TTL)
    if cached is not None:
        return cached
    rows, missing = {}, []
    params = {"FID_DIV_CLS_CODE": "1", "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    for key, path, tr in _FIN_APIS:
        try:
            got = out_rows(kis_get(cfg, path, params, tr), "output")
        except Exception as e:                       # 하나가 죽어도 나머지는 낸다
            print(f"[KIS] 재무 {key} 실패: {safe_message(e, 120)}", flush=True)
            got = []
        if not got:
            missing.append(key)
        for r in got:
            ym = str(r.get("stac_yymm") or "").strip()
            if len(ym) == 6 and ym.isdigit():
                rows.setdefault(ym, {})[key] = r

    def g(ym, key, field):
        return _fin_num((rows.get(ym, {}).get(key) or {}).get(field))

    def quarter(ym, field):
        """연 누적 → 분기 — 셈은 `_q_from_ytd` 한 곳(아래 종목 여럿 주소도 같은 셈을 쓴다)."""
        return _q_from_ytd({k: g(k, "income", field) for k in rows}, ym)

    out = []
    for ym in sorted(rows):
        sale_ytd, op_ytd = g(ym, "income", "sale_account"), g(ym, "income", "bsop_prti")
        out.append({
            "ym": ym,
            # 손익 — 분기 값 · 누적 값 (억원)
            "sale": quarter(ym, "sale_account"),
            "op": quarter(ym, "bsop_prti"),
            "net": quarter(ym, "thtr_ntin"),
            "saleYtd": sale_ytd,
            "opYtd": op_ytd,
            "netYtd": g(ym, "income", "thtr_ntin"),
            # 대차 (억원)
            "assets": g(ym, "balance", "total_aset"),
            "liab": g(ym, "balance", "total_lblt"),
            "equity": g(ym, "balance", "total_cptl"),
            # 재무비율 (% · 원)
            "debtRatio": g(ym, "ratio", "lblt_rate"),
            "roe": g(ym, "ratio", "roe_val"),
            "epsYtd": g(ym, "ratio", "eps"),
            "bps": g(ym, "ratio", "bps"),
            # 수익성 (% · 누적) — 영업이익률은 KIS 가 안 주므로 누적끼리 나눈다
            "grossMargin": g(ym, "profit", "sale_totl_rate"),
            "netMargin": g(ym, "profit", "sale_ntin_rate"),
            "opMargin": (round(op_ytd / sale_ytd * 100, 2)
                         if op_ytd is not None and sale_ytd else None),
            # 성장성 (% · 전년 같은 때 대비)
            "growSale": g(ym, "growth", "grs"),
            "growOp": g(ym, "growth", "bsop_prfi_inrt"),
            "growEquity": g(ym, "growth", "equt_inrt"),
            "growAssets": g(ym, "growth", "totl_aset_inrt"),
        })
    data = {"rows": out, "missing": missing, "at": int(time.time())}
    # **다 비었으면 담지 않는다** — 빈 것을 6시간 붙들고 있으면 그동안 못 고친다.
    if out:
        _finance_cache[code] = (time.time(), data)
    return data

def _q_from_ytd(ytd, ym):
    """연 누적 → 분기 값 하나. 1분기는 그대로, 아니면 같은 해 앞 분기 누적을 뺀다. 못 세면 `None`.
    `ytd` 는 결산 년월(`YYYYMM`) → 누적 값(없음은 `None`)."""
    cur = ytd.get(ym)
    if cur is None:
        return None
    if ym[4:] == "03":
        return cur
    prev = {"06": "03", "09": "06", "12": "09"}.get(ym[4:])
    if prev is None:
        return None
    before = ytd.get(ym[:4] + prev)
    return None if before is None else cur - before


# ── 산업 분석 재무 — 종목 여럿의 분기 매출 · 영업이익 (2026-11-10 재권님 「응 그렇게 해」 · 작업우선순위 배분) ──
#
# Insight 산업 분석 화면(`company-setup/industry.html`)이 업종 · 테마 종목 190여 개의 연간 3년 + 분기 7개를
# 한 번에 본다. 위 `fetch_finance` 는 종목 하나에 API 다섯 · 6시간 캐시라 190번 부르면 KIS 를 950번 부른다.
# 그래서 **손익(income-statement) 하나만** 부르고, 받은 줄(연 누적)은 `fin_quarter` 표에 쌓는다.
# **DART 로 따로 받지 않는다** — 재권님 「이미 받아놓는곳 있지않아?」 → 이 주소 위에 더하는 안에 「응 그렇게 해」.
# 같은 값을 두 곳에서 받으면 숫자가 갈린다(「같은 값은 한 곳에만 둔다」).
#
# **언제 다시 받나** — 쌓인 마지막 분기 **다음 분기의 보고서 마감**(분기 끝 + `FIN_REPORT_DAYS` · 4분기는
# `FIN_REPORT_DAYS_Q4`)이 지났으면 받는다. 3/31 · 5/15 · 8/14 · 11/14 와 같다. 받아도 아직 안 나왔으면
# `FINANCE_TTL` 동안 그 종목을 다시 부르지 않는다. 쌓인 줄은 다시 받을 때 KIS 가 준 값으로 갈아 쓴다(정정 반영).
#
# **처음 채우기는 뒤에서 돈다** — 190종목을 한 요청 안에서 받으면 KIS 예산 따라 수십 초가 걸린다. 응답은 쌓인 것 +
# `meta.pending`(받는 중인 종목)이고, 화면은 `meta.retryAfterSec` 뒤 다시 묻는다 — 그 값도 서버가 정한다
# (「캐시·주기·한도 값을 화면에 박지 않는다」).
#
# **쓰는 것은 8765 하나다**(`marketdb.writable`). 읽기 전용 서버는 표를 읽고, 없는 종목은 받아 메모리에만 둔다.
# **기준(연결 · 별도)** — KIS 응답에 그 칸이 없다. 2026-11-10 삼성전자 2026년 2분기 매출(1,714,995억)이 DART 연결 값과
# 같았다 — 한 종목만 대 봤다.
FIN_MULTI_MAX = 300              # 한 번에 묻는 종목 수 상한
FIN_MULTI_QUARTERS = 7           # 기본 분기 수 · 연간 해 수
FIN_MULTI_YEARS = 3
FIN_REPORT_DAYS = 45             # 분기 · 반기 보고서 마감 — 분기 끝 뒤 날 수
FIN_REPORT_DAYS_Q4 = 90          # 사업보고서 마감
FIN_MULTI_RETRY_SEC = 15         # 받는 중이면 화면이 다시 물을 때까지
FIN_QUARTER_SQL = """CREATE TABLE IF NOT EXISTS fin_quarter (
         code     TEXT NOT NULL,
         ym       TEXT NOT NULL,
         sale_ytd REAL,
         op_ytd   REAL,
         at       INTEGER NOT NULL,
         PRIMARY KEY (code, ym)
       )"""
_finq_mem = {}          # code -> {ym: (매출 누적, 영업이익 누적)} — 읽기 전용 서버 · 쓰기 실패 때
_finq_tried = {}        # code -> 마지막으로 KIS 를 부른 시각
_finq_pending = set()   # 지금 뒤에서 받는 중인 종목
_finq_lock = threading.Lock()


def _finq_next_due(last_ym):
    """쌓인 마지막 분기 다음 분기의 보고서 마감일(date)."""
    y, m = int(last_ym[:4]), int(last_ym[4:]) + 3
    if m > 12:
        y, m = y + 1, m - 12
    end = datetime(y, m, 31 if m in (3, 12) else 30).date()
    return end + timedelta(days=FIN_REPORT_DAYS_Q4 if m == 12 else FIN_REPORT_DAYS)


def _finq_load(codes):
    """쌓인 줄 — code -> {ym: (매출 누적, 영업이익 누적)}. 표가 아직 없으면 빈 것."""
    out = {c: dict(_finq_mem.get(c) or {}) for c in codes}
    conn = None
    try:
        conn = marketdb.connect()
        conn.execute(FIN_QUARTER_SQL)
        for i in range(0, len(codes), 500):
            part = codes[i:i + 500]
            q = "SELECT code, ym, sale_ytd, op_ytd FROM fin_quarter WHERE code IN (%s)" % ",".join("?" * len(part))
            for r in conn.execute(q, part):
                out[r["code"]].setdefault(r["ym"], (r["sale_ytd"], r["op_ytd"]))
    except sqlite3.Error as e:
        if not _db_missing(e):
            print(f"[재무 여럿] 표 읽기 실패: {safe_message(e, 120)}", flush=True)
    finally:
        if conn is not None:
            conn.close()
    return out


def _finq_fetch(cfg, code):
    """KIS 손익 하나 → {ym: (매출 누적, 영업이익 누적)}. 못 받으면 None."""
    path, tr = {k: (p, t) for k, p, t in _FIN_APIS}["income"]
    try:
        got = out_rows(kis_get(cfg, path, {"FID_DIV_CLS_CODE": "1", "FID_COND_MRKT_DIV_CODE": "J",
                                           "FID_INPUT_ISCD": code}, tr), "output")
    except Exception as e:
        print(f"[KIS] 재무 여럿 {code} 실패: {safe_message(e, 120)}", flush=True)
        return None
    rows = {}
    for r in got:
        ym = str(r.get("stac_yymm") or "").strip()
        if len(ym) == 6 and ym.isdigit():
            rows[ym] = (_fin_num(r.get("sale_account")), _fin_num(r.get("bsop_prti")))
    return rows or None


def _finq_save(code, rows):
    """받은 줄을 쌓는다. 쓰는 서버가 아니거나 쓰기가 실패하면 메모리에만."""
    if marketdb.writable():
        conn = None
        try:
            conn = marketdb.connect()
            conn.execute(FIN_QUARTER_SQL)
            now = int(time.time())
            conn.executemany("INSERT OR REPLACE INTO fin_quarter (code, ym, sale_ytd, op_ytd, at) VALUES (?,?,?,?,?)",
                             [(code, ym, v[0], v[1], now) for ym, v in rows.items()])
            conn.commit()
            with _finq_lock:
                _finq_mem.pop(code, None)
            return
        except sqlite3.Error as e:
            print(f"[재무 여럿] 쌓기 실패 {code}: {safe_message(e, 120)}", flush=True)
        finally:
            if conn is not None:
                conn.close()
    with _finq_lock:
        _finq_mem[code] = rows


def _finq_fill(cfg, codes):
    """뒤에서 차례로 받는다 — KIS 예산은 `kis_get` 이 지킨다."""
    try:
        for c in codes:
            rows = _finq_fetch(cfg, c)
            _finq_tried[c] = time.time()
            if rows:
                _finq_save(c, rows)
            with _finq_lock:
                _finq_pending.discard(c)
    finally:
        with _finq_lock:
            _finq_pending.difference_update(codes)


def _finq_shape(rows, nq, ny):
    """쌓인 누적 줄 → 화면 모양. 분기 값은 누적에서 뺀다 · 연간은 12월 누적."""
    sale = {k: v[0] for k, v in rows.items()}
    op = {k: v[1] for k, v in rows.items()}
    yms = sorted(rows)
    return {
        "quarters": [{"ym": ym, "sale": _q_from_ytd(sale, ym), "op": _q_from_ytd(op, ym)} for ym in yms[-nq:]],
        "years": [{"year": ym[:4], "sale": sale[ym], "op": op[ym]} for ym in yms if ym.endswith("12")][-ny:],
        "last": yms[-1] if yms else None,
    }


def fetch_finance_multi(cfg, codes, nq, ny):
    """종목 여럿의 분기 · 연간 매출 · 영업이익(억원). (data, 받는 중인 종목)."""
    have = _finq_load(codes)
    now, today = time.time(), datetime.now(KST).date()
    with _finq_lock:
        todo = [c for c in codes if c not in _finq_pending
                and now - _finq_tried.get(c, 0) >= FINANCE_TTL
                and (not have[c] or today >= _finq_next_due(max(have[c])))]
        _finq_pending.update(todo)
        pending = sorted(c for c in codes if c in _finq_pending)
    if todo:
        threading.Thread(target=_finq_fill, args=(cfg, todo), daemon=True, name="fin-multi").start()
    return {c: _finq_shape(have[c], nq, ny) for c in codes}, pending

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


def investor_confirmed_today(cfg, code, now=None):
    """오늘 확정 외국인 · 기관 순매수 금액(원) — 평일 REG_CLOSE_READY(15:40) 뒤 그날 줄에 금액이 들었을 때만. 아니면 None.

    장 마감 뒤에는 가집계(14:30 입력이 마지막)가 아니라 이 값을 쓴다 — 바닥 줄 · 「매수」 칩 · 투자자 정보가 같은 값이 되게
    (2026-11-05 재권님 한국전력 — 「차트에서 매수매도와 실시간의 매수랑의 차이가 있는데 이건 왜이렇지?」 → 「가로 해고 금액으로 다 맞춰줘」).
    값은 fetch_investor(종목 투자자 · 들고 있는 동안은 KIS 를 다시 안 부른다) 그대로 · 백만원 → 원."""
    now = now or datetime.now(KST)
    if now.weekday() >= 5 or (now.hour, now.minute) < REG_CLOSE_READY:
        return None
    try:
        rows = fetch_investor(cfg, code) or []
    except RuntimeError:
        return None
    day = now.strftime("%Y%m%d")
    r = next((x for x in rows if x.get("date") == day), None)
    fa = ((r or {}).get("foreign") or {}).get("netAmt")
    ia = ((r or {}).get("inst") or {}).get("netAmt")
    if fa is None or ia is None:
        return None
    return {"date": day, "foreign": fa * 1_000_000, "inst": ia * 1_000_000}


# 체결은 한 번에 30줄이 온다. 화면이 그보다 많이 보여줄 일이 없다.
TICKS_TTL = 3              # 장중에는 계속 쌓인다. **화면이 이 값을 받아 그 주기로 돈다** (2026-10-02 · 재권님 「나」)
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

    **통합(UN) 호가다** (2026-11-09 재권님 「호가창에 매수잔량 매도잔량이 정확한건지 확인해봐」 → 「응 그래」).
    전에는 늘 KRX(J)만 받아 넥스트레이드 잔량이 빠졌다 — 삼성전자 10:46:50 매도 잔량 합 J 69,798 · NX 81,867 · UN 151,844 /
    매수 J 26,548 · NX 11,646 · UN 38,184(하이닉스도 같은 꼴). 15:30 뒤 넥스트레이드 장에서도 KRX 호가를 냈다.
    차트 봉도 통합이라(`MARKET_DIV_CHART`) 같은 값을 쓴다. 합계는 KIS 의 총잔량 그대로다.
    """
    cached = _ttl_get(_asking_cache, code, ASKING_TTL)
    if cached is not None:
        if not market_hours.auction(sys.modules[__name__]):
            return dict(cached, expect=_expect_held(code))   # 15:30 이 지나면 바로 뗀다 · 09:00 뒤는 몇 분 마지막 값(재권님 11-11 「본장 시작하면 5분후에 안보이도록」)
        return cached
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
        # 넥스트레이드에 없는 종목(우선주 · ETF)은 KRX(J) — 장 후 UN 합이 J 보다 훨씬 작게 왔다(11-09 15:43 · 005935 매도 J 47,126 · UN 12,258 ·
        # 069500 매수 J 140,960 · UN 36,063 · 1호가는 같음 · qa 검수). 가르는 것은 _nx_absent 한 곳
        {"FID_COND_MRKT_DIV_CODE": "J" if _nx_absent(cfg, code) else MARKET_DIV_CHART, "FID_INPUT_ISCD": code},
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
        "expect": _preopen_expect(cfg, code, data) or _expect_held(code),
    }
    _asking_cache[code] = (time.time(), out)
    return out


def _preopen_expect(cfg, code, data):
    """**동시호가 예상 체결가** — 장 전(08:30~09:00) · 마감(15:20~15:30) 동시호가 동안만 낸다(market_hours.auction) · 그 밖은 None
    (2026-11-10 재권님 「응 해줘」 → 자리는 「나」 — 종목 이름 옆 현재가 자리에 「예상」 과 함께 → 「종가도 해줘」).

    KIS 호가 응답 output2 에 예상 체결가(antc_cnpr) · 예상 거래량(antc_vol) · 기준가(stck_sdpr)가 온다 — 전에는 output2 를 버렸다.
    통합(UN)으로 받은 응답은 antc_cnpr 이 "0" 으로 왔다(11-10 09:12 005930 · J 는 199,400 = 그날 시가) — 그래서 받은 응답에 값이 없으면
    KRX(J)로 한 번 더 묻는다(동시호가 동안 · 호가 캐시 ASKING_TTL 마다 한 번). 전일 대비는 기준가로 셈한다(부호 칸을 읽지 않는다).
    낸 값은 맞았는지 견주려고 expect_log 에 쌓는다(_expect_note).
    **아직 못 잰 것** — 동시호가 중 UN 응답에도 값이 오는지(오면 J 를 다시 안 묻는다)."""
    try:
        kind = market_hours.auction(sys.modules[__name__])
        if not kind:
            return None
        o2 = data.get("output2") or {}
        if not (_num(o2.get("antc_cnpr"), int) or 0) > 0:
            o2 = kis_get(cfg, "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
                         {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}, "FHKST01010200").get("output2") or {}
        price = _num(o2.get("antc_cnpr"), int) or 0
        base = _num(o2.get("stck_sdpr"), int) or 0
        if price <= 0:
            return None                      # 아직 예상가가 없다(동시호가 첫 주문 전) — 0 원으로 내지 않는다
        ex = {"kind": kind, "price": price, "amt": price - base if base else None,
              "pct": round((price - base) / base * 100, 2) if base else None,
              "volume": _num(o2.get("antc_vol"), int)}
        _expect_note({code: ex})
        return ex
    except Exception:
        return None                          # 못 받았다 — 예상가 없이 호가만 낸다


def _multi_expect(r, kind):
    """멀티 시세 한 줄(FHKST11300006)에서 예상 체결가 — 기준가(inter2_sdpr) + 예상 전일 대비(intr_antc_cntg_vrss · 부호는 sign 칸).
    예상 거래량이 0 이면 아직 예상가가 없는 것으로 본다(11-10 11:09 장중 005930 은 대비 0 · 거래량 0 이 왔다) — None."""
    base = _num(r.get("inter2_sdpr"), int) or 0
    vol = _num(r.get("intr_antc_vol"), int) or 0
    if not kind or base <= 0 or vol <= 0:
        return None
    amt = abs(_num(r.get("intr_antc_cntg_vrss"), int) or 0)
    if str(r.get("intr_antc_cntg_vrss_sign") or "") in ("4", "5"):
        amt = -amt
    return {"kind": kind, "price": base + amt, "amt": amt, "pct": round(amt / base * 100, 2), "volume": vol}


# ── 예상 체결가가 맞았나 — 쌓아 두고 실제 시가 · 종가와 견준다 (2026-11-10 재권님 「예상체결가가 맞는지 데이터 쌓아놔」) ──
# expect_log    동시호가 동안 종목마다 1분에 한 줄(그 분 마지막 값) — 호가(fetch_asking) · 멀티 시세(fetch_quotes_multi)가 받은 것
# expect_actual 그 회차 실제 값 — 시가(open)는 정규장이 열린 뒤 첫 멀티 시세(J)의 시가 · 종가(close)는 15:40 뒤 정규장 종가(attach_reg_close)
# 쓰는 것은 쓰기 서버(marketdb.writable · 8765)뿐이다. 보는 주소는 /api/kis/expect-log?day=YYYYMMDD
EXPECT_SQL = ["""CREATE TABLE IF NOT EXISTS expect_log (
         day TEXT NOT NULL, kind TEXT NOT NULL, code TEXT NOT NULL, hhmm TEXT NOT NULL,
         price INTEGER, volume INTEGER, PRIMARY KEY (day, kind, code, hhmm))""",
              """CREATE TABLE IF NOT EXISTS expect_actual (
         day TEXT NOT NULL, kind TEXT NOT NULL, code TEXT NOT NULL, price INTEGER, saved_at TEXT,
         PRIMARY KEY (day, kind, code))"""]
_exp_seen = {}            # (day, kind) → {code: 마지막으로 적은 hhmm}
_exp_done = {}            # (day, kind) → 실제 값을 적은 종목 set


def _exp_codes(day, kind):
    """그날 그 동시호가에 적어 둔 종목 — 재시작해도 DB 에서 한 번 다시 읽는다."""
    key = (day, kind)
    if key not in _exp_seen:
        seen = {}
        try:
            with _db_lock, db_conn() as conn:
                for c, h in conn.execute("SELECT code, MAX(hhmm) FROM expect_log WHERE day=? AND kind=? GROUP BY code", key):
                    seen[c] = h
        except sqlite3.Error:
            pass
        _exp_seen[key] = seen
        for k in [k for k in _exp_seen if k[0] != day]:
            _exp_seen.pop(k, None)
    return _exp_seen[key]


_expect_last = {}         # code → (day, 동시호가 마지막 예상가) — 정규장을 연 뒤 몇 분 더 내는 값(_expect_held) · 서버마다 메모리


def _expect_held(code):
    """동시호가가 끝난 뒤에도 남겨 두는 예상가 — market_hours.expect_hold 가 "open" 인 동안(정규장 연 뒤 EXPECT_HOLD_MIN 분)
    장 전 동시호가에 마지막으로 받은 값 그대로 · 그 밖은 None (2026-11-11 재권님 「예상 가격은 본장 시작하면 5분후에 안보이도록」).
    메모리라 그 몇 분 사이에 서버가 다시 뜨면 남길 값이 없다 — 그때는 바로 시가로."""
    if market_hours.auction(sys.modules[__name__]):
        return None                          # 동시호가 중에는 새로 받은 값을 쓴다
    kind = market_hours.expect_hold(sys.modules[__name__])
    hit = _expect_last.get(code)
    if not kind or not hit or hit[0] != datetime.now(KST).strftime("%Y%m%d") or hit[1].get("kind") != kind:
        return None
    return dict(hit[1])


def _expect_after(rows):
    """동시호가가 아닐 때 시세 줄들의 예상가 — 남겨 두는 몇 분이면 마지막 값 · 아니면 뗀다."""
    for c, r in rows.items():
        held = _expect_held(c)
        if held:
            r["expect"] = held
        else:
            r.pop("expect", None)


def _expect_note(rows):
    """{code: expect} 를 expect_log 에 — 종목마다 그 분의 마지막 값으로 덮는다. 쓰기 서버가 아니면 아무것도 안 한다.
    마지막 값은 어느 서버든 메모리에 쥔다(_expect_last — 정규장 연 뒤 몇 분 더 낸다)."""
    now = datetime.now(KST)
    day, hhmm = now.strftime("%Y%m%d"), now.strftime("%H%M")
    for code, ex in (rows or {}).items():
        if ex and ex.get("price"):
            _expect_last[code] = (day, dict(ex))
    if not rows or not marketdb.writable():
        return
    put = []
    for code, ex in rows.items():
        if ex and ex.get("price"):
            put.append((day, ex["kind"], code, hhmm, ex["price"], ex.get("volume")))
    if not put:
        return
    try:
        with _db_lock, db_conn() as conn:
            for sql in EXPECT_SQL:
                conn.execute(sql)
            conn.executemany("INSERT INTO expect_log VALUES (?,?,?,?,?,?) ON CONFLICT(day, kind, code, hhmm) "
                             "DO UPDATE SET price=excluded.price, volume=excluded.volume", put)
    except sqlite3.Error as e:
        print("[예상] 쌓기 실패 — %s" % safe_message(e, 120), flush=True)
        return
    for d, k, c, h, _p, _v in put:
        _exp_codes(d, k)[c] = h


def _expect_actual(out, div):
    """멀티 시세 묶음에서 그 회차 실제 시가 · 종가를 expect_actual 에 — 예상가를 적어 둔 종목만 · 한 번만."""
    if not out or not marketdb.writable():
        return
    me = sys.modules[__name__]
    now = datetime.now(KST)
    day = now.strftime("%Y%m%d")
    put = []
    if div == "J" and market_hours.in_regular(me, now) and not market_hours.auction(me, now):
        for code, q in out.items():
            if code in _exp_codes(day, "open") and code not in _exp_done.setdefault((day, "open"), set()) and q.get("open"):
                put.append((day, "open", code, q["open"]))
    for code, q in out.items():
        if (q.get("regDate") or "").replace("-", "") == day and q.get("regClose") and code in _exp_codes(day, "close") \
                and code not in _exp_done.setdefault((day, "close"), set()):
            put.append((day, "close", code, q["regClose"]))
    if not put:
        return
    try:
        with _db_lock, db_conn() as conn:
            for sql in EXPECT_SQL:
                conn.execute(sql)
            conn.executemany("INSERT OR IGNORE INTO expect_actual VALUES (?,?,?,?,?)",
                             [p + (now.isoformat(timespec="seconds"),) for p in put])
    except sqlite3.Error as e:
        print("[예상] 실제 값 쌓기 실패 — %s" % safe_message(e, 120), flush=True)
        return
    for d, k, c, _p in put:
        _exp_done.setdefault((d, k), set()).add(c)
    for k in [k for k in _exp_done if k[0] != day]:
        _exp_done.pop(k, None)


def expect_report(day):
    """그날 예상 체결가가 맞았나 — 동시호가(open · close)마다 종목별로 마지막 예상가 · 실제 값 · 차이 · 몇 시 몇 분부터 실제 값과 같았나.
    실제 값을 아직 못 적은 종목은 actual None(「못 잼」 — 0 이 아니다)."""
    out = {"day": day, "open": [], "close": []}
    try:
        with _db_lock, db_conn() as conn:
            logs = conn.execute("SELECT kind, code, hhmm, price, volume FROM expect_log WHERE day=? ORDER BY kind, code, hhmm",
                                (day,)).fetchall()
            act = {(k, c): p for k, c, p in conn.execute("SELECT kind, code, price FROM expect_actual WHERE day=?", (day,))}
    except sqlite3.Error as e:
        if "no such table" in str(e):        # 쓰기 서버(8765)가 아직 한 번도 안 적었다 — 오류가 아니라 「쌓인 것 없음」
            return dict(out, empty="아직 쌓인 것 없음 — 동시호가(08:30~09:00 · 15:20~15:30)에 8765 가 적기 시작합니다")
        return dict(out, error="못 읽음 — %s" % safe_message(e, 120))
    by = {}
    for kind, code, hhmm, price, vol in logs:
        by.setdefault((kind, code), []).append((hhmm, price, vol))
    for (kind, code), rows in sorted(by.items()):
        actual = act.get((kind, code))
        last = rows[-1]
        since = None
        if actual:
            for hhmm, price, _v in reversed(rows):
                if price != actual:
                    break
                since = hhmm
        out[kind].append({"code": code, "samples": len(rows), "lastAt": last[0], "lastPrice": last[1], "lastVolume": last[2],
                          "actual": actual, "diff": (last[1] - actual) if actual else None,
                          "diffPct": round((last[1] / actual - 1) * 100, 3) if actual else None,
                          "hit": (last[1] == actual) if actual else None, "sameSince": since})
    for kind in ("open", "close"):
        graded = [r for r in out[kind] if r["actual"]]
        out[kind + "Summary"] = {"codes": len(out[kind]), "graded": len(graded),
                                 "hit": sum(1 for r in graded if r["hit"]),
                                 "avgAbsDiffPct": round(sum(abs(r["diffPct"]) for r in graded) / len(graded), 3) if graded else None}
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

# ── 셋이 함께 사는 종목 — 홈 실시간 순위 「매수」 칩 (2026-11-05 재권님 「프로그램 기관 외국인이 동시에 사고있는 종목들
# 볼수있는 방법좀 마련해봐」 → 「실시간 순위에 버튼 하나 만들고 거기에 넣어줘 · 매수 라는 버튼」) ──
#
#   외국인 · 기관   fetch_investor_top(금액 순 · 시장 전체) 두 목록(30줄씩) 중 **한쪽에라도** 든 종목 — **가집계**
#   프로그램        외국인 · 기관이 둘 다 사는 종목만 FHPPG04650101(통합 UN) 체결 줄 맨 위의 그날 누적 순매수 금액(원)
#   연기금          flow_rank.joint_more — 15:45 뒤 쌓인 그날 확정치에서(그 전 None)
#   차례(tier)      ① 외국인 · 기관 · 연기금 · 프로그램 넷 다 ② 외국인 · 기관 · 프로그램 ③ 기관 · 연기금 ④ 외국인만 — 같은 칸 안은 산 금액 합 큰 순
#                   (2026-11-11 재권님 「외국인 기관 연기금 순으로 산걸 체크하고 셋다사는게 가장좋고 그다음이 외국인 기관 그다음이 기관 연기금
#                   그다음이 외국인 순으로 줄세워서」 → 「1에 프로그램도 넣어주고 2에도 넣어줘」) · 넷에 안 드는 것(기관만 · 외국인 · 기관인데 프로그램 매도 등)은 뺀다
#                   상위 30 밖이라 값을 모르는 쪽은 산 것으로 안 센다 · 연기금은 15:45 전에 모르므로 장중에는 ② ④ 만 찬다 — joint_tier 한 곳
# 한 번 짓는 데 KIS 2건 + 겹친 종목 수(11-05 12:38 실측 12) + 오늘 빠진 종목 수 · 가집계 목록과 같은 INVESTOR_TOP_TTL 동안 들고 있다
#
# **뒤에서 짓는다** — 묻는 쪽은 들고 있던 판을 바로 받고, 낡았으면 뒤에서 다시 짓는다(처음 부를 때 KIS 14건을 쥔 채
# 기다리면 8.9초였다 · 11-05 13:00 qa 실측). 판이 아직 없으면 빈 줄과 pending 을 낸다 — 화면은 「불러오는 중」.
#
# **「없음」 과 「못 받음」 을 가른다** (11-05 개념정의 검수) — 프로그램 값을 못 받은 종목은 빼되 그 수를 programMissing 으로
# 낸다 · 외국인 · 기관 목록을 둘 다 못 받으면 listFail 로 내고 들고 있던 판을 덮지 않는다 · 못 받은 것이 있는 판은 다음 물음에
# 바로 다시 짓는다(들고 있는 시간을 안 채운다).
#
# **빠진 종목** (11-05 재권님 「동시매수하다가 어느 한곳이 매도로 바뀌는것도 파악을 할수있게」) — 그날 한 번이라도 셋 다 샀다가
# 빠진 종목을 flipped 로 낸다. 어느 쪽이 매도(0 이하)로 바뀌었나 · 상위 30 밖으로 밀려 값을 모르는 쪽 · 처음 빠진 것을 본 시각.
# 다시 셋 다 사면 flipped 에서 지운다. 프로그램을 못 받은 종목은 빠진 것으로 세지 않는다(못 받은 것이지 판 것이 아니다).
_joint_buy = {"at": 0.0, "data": None, "retry": False, "day": None, "seen": {}, "flipped": {}, "frozen": None}
JOINT_RETRY_MIN = 60                        # 못 받은 것이 있는 판을 다시 짓는 최소 간격 (초)
JOINT_FIRST_WAIT = 12                       # 첫 판을 기다리는 최대 시간 (초) — 묻는 쪽만 기다리고 판 자리는 안 막는다
_joint_buy_lock = threading.Lock()          # 판을 읽고 바꾸는 자리
_joint_buy_build = threading.Lock()         # 짓는 것은 한 번에 하나
_program_reg_cache = {}                     # code → (날, 그날 거래소 프로그램 순매수 원) — 정규장 마감 뒤 「매수」 판
_program_at = {}                            # code → 그 값의 시각(HH:MM:SS) — 장중은 체결 줄 맨 위 시각 · 마감 뒤 일별 값은 정규장 마감 시각(「매수」 칩 줄마다 · 11-06)


def _program_net_today(cfg, code, reg=False):
    """종목 프로그램 그날 누적 순매수 금액(원). 못 받으면 None.

    reg=True — 정규장이 끝난 뒤. 체결 줄(FHPPG04650101)은 최근 30줄만 줘 15:30 의 누적을 못 꺼낸다(11-05 17:36 실측 —
    17:35 ~ 17:17 만 옴). 그래서 일별 주소(FHPPG04650201)의 그날 줄을 **거래소(J)** 로 받는다 — 외 · 기 확정치(FHKST01010900 · J)와
    같은 거래소 기준이라 셋이 한 기준이 된다. 넥스트레이드(프리 · 애프터 · 메인마켓) 체결은 안 든다
    (11-05 재권님 「정규장 끝나면 정규장에서 좋았던 종목들을 남겨놓는 방향」)."""
    if reg:
        day = datetime.now(KST).strftime("%Y%m%d")
        hit = _program_reg_cache.get(code)
        if hit and hit[0] == day:
            return hit[1]
        try:
            data = kis_get(cfg, "/uapi/domestic-stock/v1/quotations/program-trade-by-stock-daily",
                           {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code, "FID_INPUT_DATE_1": day}, "FHPPG04650201")
        except RuntimeError:
            return None
        r = next((x for x in (data.get("output") or []) if (x.get("stck_bsop_date") or "").strip() == day), None)
        v = _num(r.get("whol_smtn_ntby_tr_pbmn"), int) if r else None
        now = datetime.now(KST)
        if v is not None:
            _program_at[code] = "%02d:%02d:00" % KRX_CLOSE
        if v is not None and (now.hour, now.minute) >= REG_CLOSE_READY:
            _program_reg_cache[code] = (day, v)     # 15:40 뒤 받은 값만 그날 들고 있는다 — 15:30~15:40 은 일별 줄이 덜 모였을 수 있다(개념정의 덧 11-05)
        return v
    try:
        data = kis_get(cfg, "/uapi/domestic-stock/v1/quotations/program-trade-by-stock",
                       {"FID_COND_MRKT_DIV_CODE": "UN", "FID_INPUT_ISCD": code}, "FHPPG04650101")
    except RuntimeError:
        return None
    rows = [r for r in (data.get("output") or []) if (r.get("bsop_hour") or "").strip()]
    if not rows:
        return None
    last = max(rows, key=lambda r: r.get("bsop_hour") or "")
    h = (last.get("bsop_hour") or "").strip()
    if len(h) == 6:
        _program_at[code] = "%s:%s:%s" % (h[:2], h[2:4], h[4:])
    return _num(last.get("whol_smtn_ntby_tr_pbmn"), int)


def joint_tier(fa, ia, pg, fund):
    """「매수」 칩 차례 1~4 · 안 들면 None — 위 머리 주석 (tier). 값 None(모름)은 안 산 것으로 센다."""
    b = lambda v: v is not None and v > 0
    f, i, p, n = b(fa), b(ia), b(pg), b(fund)
    if f and i and p and n: return 1
    if f and i and p: return 2
    if i and n: return 3
    if f and not i: return 4
    return None


def _joint_buy_make(cfg):
    """판을 새로 짓는다. 금액 단위는 원 · 값이 없으면 None."""
    now = datetime.now(KST)
    tops, errors = fetch_investor_top(cfg, "buy", "all", "amt", MOVERS_MAX)
    f = {r["code"]: r for r in tops.get("foreign") or []}
    i = {r["code"]: r for r in tops.get("inst") or []}
    if not f and not i:
        return {"listFail": True, "errors": len(errors or {})}
    won = lambda side: None if side is None else side * 1_000_000          # 백만원 → 원
    famt = lambda c: won(((f.get(c) or {}).get("foreign") or {}).get("amt")) if c in f else None
    iamt = lambda c: won(((i.get(c) or {}).get("inst") or {}).get("amt")) if c in i else None
    # 마감 뒤(15:40~)에는 외국인 · 기관 값을 그날 확정치로 — 후보(두 가집계 목록이 겹친 종목)는 그대로 · 확정치를 못 받은 종목만 가집계
    # (11-05 재권님 「가」 — 확정치에서 한 곳이라도 판 종목은 빠진 종목으로 넘어간다)
    # 정규장이 끝나면(15:30~) 판은 정규장 기준으로 남는다 — 프로그램은 그날 거래소 합(일별) · 외 · 기는 15:40 부터 확정치.
    # 장외(넥스트레이드 애프터) 체결은 섞지 않는다(11-05 재권님 「프리장 정규장 만 가능하면 거기에 맞게만 보여주고 정규장 끝나면
    # 정규장에서 좋았던 종목들을 남겨놓는 방향」) · 프리장(08:00~)은 외 · 기 가집계 첫 입력(09:30) 전이라 판이 비어 있다
    reg_over = now.weekday() >= 5 or (now.hour, now.minute) >= KRX_CLOSE or (now.hour, now.minute) < NXT_PRE_OPEN
    conf = {}
    closed = now.weekday() < 5 and (now.hour, now.minute) >= REG_CLOSE_READY
    if closed:
        def cf(c):
            if c not in conf:
                conf[c] = investor_confirmed_today(cfg, c, now)
            return conf[c]
        famt0, iamt0 = famt, iamt
        famt = lambda c: cf(c)["foreign"] if cf(c) else famt0(c)
        iamt = lambda c: cf(c)["inst"] if cf(c) else iamt0(c)
    # 줄마다 외 · 기 값이 무엇인가 — 마감 뒤에만 싣는다(확정치 confirmed · 확정치를 못 받아 가집계로 남은 estimate) · 장중은 싣지 않는다
    # (11-05 개념정의 검수 — 판 전체를 confirmed 로 내면 가집계로 남은 줄이 가려진다)
    basis = (lambda c: "confirmed" if conf.get(c) else "estimate") if conf is not None and closed else (lambda c: None)
    rows, missing, prog = [], 0, {}
    cands = list(dict.fromkeys(list(f) + list(i)))
    fund = {c: v.get("fund") for c, v in flow_rank.joint_more(sys.modules[__name__], now.date().isoformat(), cands).items()}
    for code in cands:
        fa, ia = famt(code), iamt(code)
        pg = None
        if fa and ia and fa > 0 and ia > 0:      # 프로그램은 ① ② 를 가를 때만 든다 — 외국인 · 기관 둘 다 사는 종목만 묻는다(KIS 건수 그대로)
            pg = _program_net_today(cfg, code, reg_over)
            prog[code] = pg
            if pg is None:
                missing += 1
        t = joint_tier(fa, ia, pg, fund.get(code))
        if t is None:
            continue
        r = f.get(code) or i.get(code)
        rows.append({"code": code, "name": r.get("name"), "price": r.get("price"), "pct": r.get("pct"),
                     "foreign": fa, "inst": ia, "program": pg, "fund": fund.get(code), "tier": t,
                     "sum": sum(v for v in (fa, ia, pg, fund.get(code)) if v and v > 0), "basis": basis(code)})
    rows.sort(key=lambda x: (x["tier"], -x["sum"]))
    return {"rows": rows, "f": f, "i": i, "famt": famt, "iamt": iamt, "prog": prog, "conf": conf, "basis": basis,
            "reg": reg_over, "phase": "closed" if reg_over else "live",
            "candidates": len(cands), "programMissing": missing, "fund": fund,
            "errors": len(errors or {}), "hm": now.strftime("%H:%M"), "day": now.date().isoformat()}


def _joint_buy_rebuild(cfg):
    if not _joint_buy_build.acquire(blocking=False):
        return
    try:
        m = _joint_buy_make(cfg)
        with _joint_buy_lock:
            if m.get("listFail"):                # 두 목록 다 못 받음 — 들고 있던 판을 덮지 않고 그렇다고만 적는다
                if _joint_buy["data"] is not None:
                    _joint_buy["data"] = dict(_joint_buy["data"], listFail=True)
                _joint_buy["retry"] = True
                return
            st = _joint_buy
            if st["day"] != m["day"]:
                st["day"], st["seen"], st["flipped"] = m["day"], {}, {}
            now_codes = {r["code"] for r in m["rows"]}
            for r in m["rows"]:
                st["seen"][r["code"]] = r["name"]
                st["flipped"].pop(r["code"], None)
            gone = [c for c in st["seen"] if c not in now_codes and c not in st["flipped"]]
        # 빠진 종목의 프로그램 값 — 판 밖에서 받는다(겹침 후보가 아니었으면 아직 안 받았다)
        extra = {c: (m["prog"][c] if c in m["prog"] else _program_net_today(cfg, c, m["reg"])) for c in gone}
        # 외국인 · 기관 상위 30 밖으로 밀린 쪽은 값을 모른다 — 그 종목의 장중 가집계(누적 수량) × 현재가로 어림해 가른다
        # (11-05 13:19 8772 — 빠짐 넷이 다 「상위 30 밖」 이었다. 아직 사는 종목을 빠진 것으로 적지 않게)
        blind = [c for c in gone if m["famt"](c) is None or m["iamt"](c) is None]
        px = fetch_quotes_multi(cfg, blind)[0] if blind else {}
        guess = {}
        for c in blind:
            try:
                e = (fetch_investor_estimate(cfg, c) or {}).get("latest") or {}
            except RuntimeError:
                e = {}
            p0 = (px.get(c) or {}).get("price")
            guess[c] = {k: (e.get(k) * p0 if e.get(k) is not None and p0 else None) for k in ("foreign", "inst")}
        back = []
        with _joint_buy_lock:
            st = _joint_buy
            for c in gone:
                pg = extra[c]
                if pg is None:                   # 못 받음 — 판 것이 아니다
                    continue
                fa, ia = m["famt"](c), m["iamt"](c)
                approx = [k for k, v in (("foreign", fa), ("inst", ia)) if v is None and (guess.get(c) or {}).get(k) is not None]
                fa = fa if fa is not None else (guess.get(c) or {}).get("foreign")
                ia = ia if ia is not None else (guess.get(c) or {}).get("inst")
                fu = m["fund"].get(c)
                t = joint_tier(fa, ia, pg, fu)
                if t is not None:                # 아직 넷 중 한 칸에 든다 — 빠진 것이 아니다(값 일부는 어림)
                    back.append({"code": c, "name": st["seen"].get(c), "price": (px.get(c) or {}).get("price"),
                                 "pct": (px.get(c) or {}).get("pct"), "foreign": fa, "inst": ia, "program": pg, "fund": fu, "tier": t,
                                 "sum": sum(v for v in (fa, ia, pg, fu) if v and v > 0), "approx": approx, "basis": m["basis"](c)})
                    continue
                sold = [k for k, v in (("foreign", fa), ("inst", ia), ("program", pg)) if v is not None and v <= 0]
                unknown = [k for k, v in (("foreign", fa), ("inst", ia)) if v is None]
                st["flipped"][c] = {"code": c, "name": st["seen"].get(c), "foreign": fa, "inst": ia, "program": pg,
                                    "sold": sold, "unknown": unknown, "at": m["hm"], "basis": m["basis"](c)}
            for c, x in list(st["flipped"].items()):     # 이미 빠진 종목도 값은 새로(바뀐 시각은 처음 본 때 그대로)
                if c in gone:
                    continue
                fa, ia = m["famt"](c), m["iamt"](c)
                x.update(foreign=fa, inst=ia, unknown=[k for k, v in (("foreign", fa), ("inst", ia)) if v is None], basis=m["basis"](c))
            rows = sorted(m["rows"] + back, key=lambda x: (x["tier"], -x["sum"]))
            st["data"] = {"rows": rows, "flipped": sorted(st["flipped"].values(), key=lambda x: x["at"], reverse=True),
                          # 외 · 기 값을 확정치로 낸 줄 · 가집계로 남은 줄의 수(rows + flipped · 마감 뒤에만 셈 · 장중은 None)
                          "confirmed": sum(1 for x in rows + list(st["flipped"].values()) if x.get("basis") == "confirmed") if m["conf"] else None,
                          "estimated": sum(1 for x in rows + list(st["flipped"].values()) if x.get("basis") == "estimate") if m["conf"] else None,
                          "phase": m["phase"],     # live 정규장 중 · closed 정규장이 끝나 그 기준으로 남겨 둔 판
                          "candidates": m["candidates"], "programMissing": m["programMissing"],
                          "listFail": False, "errors": m["errors"]}
            st["at"] = time.time()
            st["retry"] = m["programMissing"] > 0 or m["errors"] > 0
            # 정규장이 끝나고 외 · 기가 다 확정 · 프로그램 다 받은 판이면 그날 판으로 굳힌다 — 다음 평일 프리장(08:00)까지 다시 안 짓는다.
            # 밤 · 주말 · 자정이 지나도 「정규장에서 좋았던 종목」 이 남고, 날이 바뀌어 그날 줄이 없어 판이 비는 일도 없다
            done = m["phase"] == "closed" and m["conf"] and not st["data"]["estimated"] and not m["programMissing"] and not m["errors"]
            st["frozen"] = m["day"] if done else None
            data = st["data"]
        # 쌓기 — 판을 지을 때마다 그날 종목별 처음 잡힌 시각 · 잡힌 횟수 · 가장 큰 합(쓰기 되는 서버만 DB 에 남긴다) ·
        # 15:45 뒤 쌓인 확정치에서 연기금 · 개인 (2026-11-06 재권님 「이거 실시간으로 쌓으면서 이걸 실시간 순위에 매수에 넣어줘」 → 「응 넣어」)
        acc = flow_rank.joint_track(sys.modules[__name__], m["day"], data["rows"], m["hm"])
        more = flow_rank.joint_more(sys.modules[__name__], m["day"], [x["code"] for x in data["rows"] + data["flipped"]])
        with _joint_buy_lock:
            for x in data["rows"] + data["flipped"]:
                a0 = acc.get(x["code"]) or {}
                x.update(first=a0.get("first"), hits=a0.get("hits") or 0, pgAt=_program_at.get(x["code"]),
                         fund=(more.get(x["code"]) or {}).get("fund"), person=(more.get(x["code"]) or {}).get("person"))
            # 차례는 joint_tier 가 연기금까지 넣어 위에서 세웠다(11-11) — 여기서 다시 안 세운다
            data["fundIn"] = sum(1 for x in data["rows"] if x.get("fund") is not None)
    except Exception as e:
        print("[매수 칩] 짓다 멈춤 — %s" % safe_message(e, 120))
    finally:
        _joint_buy_build.release()


def fetch_joint_buy(cfg):
    """(판, 지은 시각). 판이 없으면 뒤에서 짓기 시작하고 (None, 0)."""
    with _joint_buy_lock:
        at, data, retry, frozen = _joint_buy["at"], _joint_buy["data"], _joint_buy["retry"], _joint_buy["frozen"]
    now = datetime.now(KST)
    if data is not None and frozen and not (now.date().isoformat() > frozen and now.weekday() < 5
                                            and (now.hour, now.minute) >= NXT_PRE_OPEN):
        return data, at                          # 굳힌 판 — 다음 평일 08:00 까지 그대로
    age = time.time() - at
    # 못 받은 것이 있는 판(retry)도 JOINT_RETRY_MIN 안에는 다시 안 짓는다 — 한 종목 프로그램이 늘 비면 부를 때마다 KIS 14건 남짓을
    # 되풀이한다(11-05 qa 덧 · 롱폴이 켜진 8765)
    if data is None or age >= INVESTOR_TOP_TTL or (retry and age >= JOINT_RETRY_MIN):
        t = threading.Thread(target=_joint_buy_rebuild, args=(cfg,), daemon=True, name="joint-buy")
        t.start()
        if data is None:            # 첫 판은 JOINT_FIRST_WAIT 까지 기다려 본다 — pending 만 내면 롱폴이 꺼진 서버에서 화면이 다음 주기까지 「불러오는 중」(11-05 8772)
            t.join(JOINT_FIRST_WAIT)
            with _joint_buy_lock:
                at, data = _joint_buy["at"], _joint_buy["data"]
    return data, at


# ---------------------------------------------------------------- 저장 계층 (SQLite)
# 배포본은 Cloudflare D1 을 쓰고, 로컬은 같은 구조를 SQLite 파일로 둔다.
# 차트는 과거 데이터가 필요한데 볼 때마다 KIS 를 부르면 호출량을 감당할 수 없다.

# `market.db` 의 자리·journal_mode·쓰기 가능 여부는 **`marketdb` 한 곳**이 정한다
# (2026-10-01 지시). 전에는 네 파일이 각자 조립해 **폴더마다 DB 가 따로 쌓였다.**
DB_PATH = marketdb.DB_PATH
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
    INVESTOR_DAILY_SQL,      # 「3달」 — 위 `fetch_investor_long`
]
# 예상 체결가 표(EXPECT_SQL)는 여기 두지 않는다 — db_init 은 읽기 전용 서버(8764 · 8767 · 세션)에서도 돌아, 표가 아직 없으면
# CREATE 가 「readonly database」 로 터져 지수 봉까지 못 낸다(2026-11-10 11:5x 8766 실측 · 6420cd3 에 넣었다 뺌).
# 쓰는 서버만 처음 적을 때 만든다(_expect_note · _expect_actual) · 읽는 쪽은 표가 없으면 「쌓인 것 없음」(expect_report)

# 기간별 설정
#   fresh_sec : 이 시간이 지나면 최근 구간을 다시 받는다 (장중 당일 캔들 갱신용)
PERIODS = {
    "D":  {"kis": "D", "label": "일",  "fresh_sec": 60,  "span_days": 400},
    "W":  {"kis": "W", "label": "주",  "fresh_sec": 300, "span_days": 2000, "close_once": True},
    "M":  {"kis": "M", "label": "월",  "fresh_sec": 600, "span_days": 4000, "close_once": True},
    "Y":  {"kis": "Y", "label": "년",  "fresh_sec": 3600, "span_days": 8000, "close_once": True},
    "1m": {"kis": None, "label": "1분", "fresh_sec": 30, "span_days": 1},
    "5m": {"kis": None, "label": "5분", "fresh_sec": 30, "span_days": 1, "view_days": 10},
}
# `close_once` — **마감 뒤 한 번만 다시 받는다** (2026-10-03 재권님 「응 해줘」 · 봉 결정 「주·월·년은 마지막
# 봉을 장 마감 때 한 번」). 이 기간은 `fresh_sec` 이 지나도 장중에는 KIS 를 다시 부르지 않는다 — 아래
# `_last_close_ts`. 롱폴이 이 주소를 안쪽으로 다시 부르므로, 안 그러면 화면이 주봉을 열어 둔 동안
# 5분마다 KIS 를 부르고 「바뀜」 을 알렸다. `fresh_sec` 은 롱폴이 DB 를 다시 보는 간격으로만 남는다.
# `view_days` — **보여 주는 거래일 수** (2026-10-03 재권님 「보이는 것만」 · 5분봉 10일).
# 쌓는 양이 아니다 — 옛 봉을 지우지 않는다. KIS 는 분봉을 오늘치만 주므로 지난 날짜는
# DB 에 쌓인 것만 나온다. 화면(chart.js)은 limit 를 그대로 묻고 서버가 넓힌다 —
# 날마다 봉 수가 달라(실측 6~145) 개수로는 박을 수 없어서다. 아래 `_view_limit`.

# 분봉 수집 범위 (분 단위). 통합 시장 기준 08:00~20:00
MINUTE_DAY_START = 8 * 60
MINUTE_DAY_END = 20 * 60


def db_conn():
    """읽기 전용 서버면 `mode=ro` 로 열린다 — `marketdb` 가 정한다."""
    return marketdb.connect(timeout=10)


# 통합(UN)이 과거를 잘라 줘서 잠긴 `backfill … done` 을 한 번 푸는 표.
# 값을 바꾸면 그 판으로 다시 한 번 돈다 — 지수의 `INDEX_SPAN_FIX` 와 같은 꼴이다.
BARS_MKT_FIX = "barsfix:market"
BARS_MKT_FIX_VER = "2026-10-02-un-alt"


def _unlock_bars_backfill():
    """`backfill … done` 중 주·월·년봉 것을 **한 번** 지운다.

    **이것이 없으면 고쳐도 화면이 안 바뀐다.** `fetch_bars_back` 은 끝까지
    훑고도 못 채우면 `done` 을 찍는데, 2026-10-02 까지 그 「못 채움」 의 원인이
    **통합(UN)이 과거를 덜 주는 것**이었다. 원인을 고쳐도 그 표가 남아 있으면
    `get_chart` 의 `want_more` 가 거짓이라 **다시 받지 않는다.**

    지우면 다음 조회에서 과거를 한 번 더 훑고, 그때 KRX 되묻기가 걸린다.

    **일봉은 안 지운다.** 2026-10-02 실측에서 일봉은 통합으로도 100봉이 왔다
    (`005935` · `069500` 둘 다). 통합으로 일봉까지 0 이던 `091990` 은
    **2023년 합병으로 상장폐지된 종목**이라 KRX 로 받아도 쓸 데가 없다 —
    그 종목을 관심목록에서 빼는 것은 따로 올려 두었다.

    **한 번만 돈다.** 매번 지우면 모든 종목이 열릴 때마다 과거를 다시 훑어
    KIS 호출이 계속 늘어난다.
    """
    # **읽기 전용 서버는 손대지 않는다** (2026-10-02 · `marketdb` 가 들어온 뒤).
    # 안 보면 `DELETE` 가 터지고, 호출 쪽 `try` 가 받아 「건너뜁니다」 를 찍는다 —
    # 터지지는 않지만 **재시작마다 같은 로그가 뜬다.** `_meta_set` 도 가드가 있어
    # 「했다」 표를 못 찍으므로 다음에도 또 시도하기 때문이다.
    #
    # 푸는 것은 **쓰는 서버 하나**가 하면 된다. 읽기 전용 서버는 그 결과를 읽는다.
    if not marketdb.writable():
        return 0
    if _meta_get(BARS_MKT_FIX) == BARS_MKT_FIX_VER:
        return 0
    with _db_lock, db_conn() as conn:
        cur = conn.execute(
            "DELETE FROM sync_meta WHERE key LIKE 'backfill:%' "
            "AND (key LIKE '%:W' OR key LIKE '%:M' OR key LIKE '%:Y')")
        n = cur.rowcount or 0
    _meta_set(BARS_MKT_FIX, BARS_MKT_FIX_VER)
    return n


def _prune_span_dupes():
    """한 구간에 여러 줄이 쌓인 것을 치운다 — 구간마다 **가장 큰 ts 하나**만 남긴다.

    위 SPAN_CUT 주석의 병으로 이미 쌓인 것들이다. 고쳐도 남은 줄은 안 없어져서
    화면에 그대로 나온다 — 재권님이 보신 년봉 다섯 줄이 그것이다.

    **가장 큰 ts 가 최신이다.** 진행 중인 구간은 부를수록 ts 가 뒤로 가고,
    그 줄의 종가가 가장 최근 값이다.

    서버가 뜰 때 한 번 돈다. 치울 것이 없으면 0 을 내고 아무것도 안 한다.
    """
    # **읽기 전용 서버는 손대지 않는다** (2026-10-02).
    # 2026-10-02 09:22 에 8768 을 메인 DB 읽기 전용으로 켜니 여기서
    # `OperationalError` 가 나고 「겹친 봉 정리: 건너뜁니다」 가 떴다.
    # 치우는 것은 **쓰는 서버 하나**가 하면 되고, 읽기 전용 서버는 그 결과를 읽는다.
    #
    # `_meta_set_write` · `_save_candles_write` 는 **부르는 쪽**이 가드를 보므로
    # 그 짝은 안전하다 — 여기와 `_unlock_bars_backfill` 만 자기가 봐야 했다.
    if not marketdb.writable():
        return 0
    n = 0
    with _db_lock, db_conn() as conn:
        for period, cut in SPAN_CUT.items():
            # **같은 종목 안에서** 자기보다 큰 ts 가 같은 구간에 있으면 지운다.
            #
            # 처음에 `ts NOT IN (SELECT MAX(ts) … GROUP BY code, 구간)` 으로
            # 썼다가 틀렸다 (2026-09-29). **`NOT IN` 이 종목을 안 가른다** —
            # 다른 종목의 그 구간 최대값이 목록에 있으면 이 종목의 같은
            # 날짜 줄도 살아남았다. 삼성전자 2026년이 두 줄로 남았다.
            #
            # **「9줄 치웠다」 는 숫자만 보면 됐다고 읽힌다.** 남은 줄을
            # 눈으로 보고서야 갈렸다.
            cur = conn.execute(
                "DELETE FROM candles WHERE period = ? AND ts < ("
                "  SELECT MAX(c2.ts) FROM candles c2"
                "   WHERE c2.code = candles.code AND c2.period = candles.period"
                "     AND substr(c2.ts, 1, ?) = substr(candles.ts, 1, ?))",
                (period, cut, cut))
            n += cur.rowcount or 0
    return n


# 구간 중간부터 물어 **부분 누적**이 저장된 것을 한 번 다시 받는다.
#
# `floor_to_span` 이 2026-09-29 에 들어와 **앞으로 받을 것**은 온전해졌는데,
# **이미 저장된 틀린 값은 그대로 남았다.** 재권님이 코스피 1993년 년봉에서
# 찾으셨다 — 저가가 602.30 이어야 하는데 751.21 로 있었다.
#
# ⚠️ **저절로 안 고쳐진다.** 지수 봉을 받는 `fetch_index_candles` 를 **부르는
# 화면 코드가 저장소에 하나도 없다** (`live.js` 의 `fetchIndexCandles` 를
# 쓰는 곳 0곳 — 2026-09-17 에 큰 차트가 종목 캔들로 갈아탔다). 그래서
# 「한 시간 뒤에 덮어써진다」 가 참이 아니었다.
#
# **겹침 치우기(`_prune_span_dupes`)와 다른 점** — 겹친 줄은 기계가 가려낼 수
# 있지만 **값이 틀린 줄은 못 가려낸다.** 다시 받아 덮는 수밖에 없다.
#
# **한 번만 돈다.** 표를 남겨 두 번째부터 건너뛴다 — KIS 호출이라 매번 돌면
# 재시작할 때마다 쌓인다. 값은 판 번호라, 나중에 같은 일이 또 필요하면
# 올려서 다시 돌린다.
INDEX_SPAN_FIX = "idxspan-fixed"
INDEX_SPAN_FIX_VER = "1"


def _refresh_index_spans(cfg):
    """지수 년·월봉을 한 번 다시 받아 덮는다. 받은 봉 수를 낸다.

    주봉·일봉은 하지 않는다 — **문제가 확인된 것만** 한다. 주봉은 그 주
    월요일을, 일봉은 그날을 받으므로 구간 중간부터 물어도 안 어긋난다
    (2026-09-29 실측 · 겹침 0).
    """
    if not cfg or _meta_get(INDEX_SPAN_FIX) == INDEX_SPAN_FIX_VER:
        return 0
    got = 0
    for code, _name in INDEX_DEFS:
        for period in SPAN_CUT:                     # Y · M
            try:
                now = datetime.now(KST)
                bars = _index_bars_from_kis(
                    cfg, code, period, now - timedelta(days=INDEX_SPAN[period]), now)
                if bars:
                    save_candles(code, period, bars)
                    got += len(bars)
            except Exception:
                pass                                # 하나 실패해도 나머지는 간다
    _meta_set(INDEX_SPAN_FIX, INDEX_SPAN_FIX_VER)
    return got


def _db_missing(e):
    """DB 표 · 칸이 아직 없어 난 오류인가 — 읽기 전용 서버는 표를 만들지 않는다(marketdb._ReadOnlyConn)."""
    m = str(e)
    return isinstance(e, sqlite3.OperationalError) and ("no such table" in m or "no such column" in m)


# 그때 내는 응답 — 「서버 오류」 가 아니라 「아직 없음」(「못 쟀으면 0 이 아니라 못 쟀다」 · 2026-11-10 재권님 「응」)
_DB_MISSING_BODY = {"ok": False, "data": None, "missing": True,
                    "error": "아직 없음 — 이 값을 쌓는 표를 쓰는 서버(8765)가 아직 만들지 않았습니다"}


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
    # 읽기 전용 서버는 **안 써 본다.** 깃발이 켜져 있어도 디스크 · 권한 ·
    # 잠금으로 실패할 수 있어 예외도 함께 잡는다 (`marketdb` 의 「깃발과 실패는
    # 다르다」).
    if not marketdb.writable():
        return
    try:
        _meta_set_write(key, value, datetime)
    except sqlite3.Error as e:
        print("[db] sync_meta 쓰기 실패 %s — %s" % (key, safe_message(e, 120)))


def _meta_set_write(key, value, datetime):
    with _db_lock, db_conn() as conn:
        conn.execute(
            """INSERT INTO sync_meta (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                                             updated_at=excluded.updated_at""",
            (key, str(value), datetime.datetime.now().isoformat(timespec="seconds")),
        )


def _ymd_gap(a, b):
    """YYYYMMDD 두 개 사이의 날수. 못 읽으면 0."""
    import datetime
    try:
        d1 = datetime.datetime.strptime(str(a), "%Y%m%d").date()
        d2 = datetime.datetime.strptime(str(b), "%Y%m%d").date()
    except (ValueError, TypeError):
        return 0
    return abs((d2 - d1).days)


def _looks_truncated(rows, date_from):
    """통합(UN)이 과거를 잘라 준 모양인가.

    **값을 박지 않고 스스로 비교한다.** 「몇 봉 미만이면」 같은 수를 적으면
    주기마다 다르고 종목마다 달라 그날 낡는다. 대신 **안 온 앞 구간**과
    **받은 구간**의 길이를 견준다.

        안 온 앞 구간 > 받은 구간   →  그 앞이 통째로 빠졌다고 본다

    왜 이 셈이 드는가 —

        005935 주봉   물은 범위 20210405~  ·  받은 것 20260914~20260928
                      안 온 앞 5년 ≫ 받은 14일        →  **잘렸다**
        끝까지 받은 종목   물은 범위 20150101~  ·  받은 것 20150105~20190xxx
                      안 온 앞 4일 ≪ 받은 수년        →  정상 (상장 이전이다)

    꽉 찬 응답은 보지 않는다 — 더 과거는 `fetch_bars_back` 의 다음 호출이
    가져가고, 그때 다시 이 판정을 거친다.

    **한 줄도 없으면 무조건 의심한다.** 2026-10-02 에 `091990` 이 통합으로
    일봉까지 0 이었다(그 종목은 상장폐지라 KRX 로도 결과가 같지만, 0 을
    「없다」 로 단정하지 않는 쪽이 맞다).
    """
    if len(rows) >= BARS_PER_CALL:
        return False
    if not rows:
        return True
    ts = [r["ts"] for r in rows]
    return _ymd_gap(date_from, min(ts)) > _ymd_gap(min(ts), max(ts))


def _bars_once(cfg, code, period, date_from, date_to, market):
    """한 시장에 한 번 묻는다. 돌려주는 것은 봉 목록."""
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        {
            "FID_COND_MRKT_DIV_CODE": market, "FID_INPUT_ISCD": code,
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


def fetch_bars_from_kis(cfg, code, period, date_from, date_to):
    """일/주/월/년봉. 같은 API 에서 기간 구분 코드만 바뀐다 (한 번에 최대 100개).

    **통합(UN)으로 먼저 묻고, 과거가 잘려 온 모양이면 KRX(J)로 한 번 더 묻는다**
    (2026-10-02 지시). 어느 쪽을 쓸지는 **더 많이 온 쪽**으로 정한다 —
    「통합이 늘 많다」 도 「KRX 가 늘 많다」 도 참이 아니라서다. 분봉이 이미
    같은 모양이다(`MARKET_DIV_CHART` 주석).

    **되묻는 비용은 잘린 종목에만 든다.** 꽉 찬 응답은 판정에서 빠지므로
    (`_looks_truncated`) 보통 종목은 호출이 늘지 않는다.
    """
    rows = _bars_once(cfg, code, period, date_from, date_to, MARKET_DIV_BARS)
    if MARKET_DIV_BARS_ALT != MARKET_DIV_BARS and _looks_truncated(rows, date_from):
        try:
            alt = _bars_once(cfg, code, period, date_from, date_to, MARKET_DIV_BARS_ALT)
        except Exception:
            return rows              # 되묻다 실패하면 처음 받은 것을 쓴다
        if len(alt) > len(rows):
            return alt
    return rows


# 일/주/월/년봉은 한 번에 이만큼만 온다.
#
# `fetch_bars_from_kis` 주석에 「한 번에 최대 100개」 라고 적혀 있었는데
# **적힌 것은 잰 것이 아니라** 재봤다 (2026-09-29). DB 에 일봉이 없던 종목
# 둘(000150 · 000270)을 부르니 **정확히 100봉**씩 왔다. 삼성전자가 110 으로
# 나왔던 것은 DB 에 쌓여 있던 것이 더해진 값이었다.
#
# 기간을 넓게 줘도 **date_to 기준 최근 100개**를 준다. 그래서 과거를 받으려면
# date_to 를 거슬러 다시 불러야 한다.
BARS_PER_CALL = 100


def fetch_bars_back(cfg, code, period, want):
    """일/주/월/년봉을 want 개가 될 때까지 날짜를 거슬러 여러 번 받는다.

    받은 것 중 **가장 오래된 날짜의 하루 전**을 새 date_to 로 삼아 다시 부른다.
    새 봉이 하나도 안 오면 멈춘다 — 그 종목의 상장 이전이다.

    ⚠️ **분봉은 이 길로 못 온다.** 지금 쓰는 분봉 API(`inquire-time-itemchartprice`)
    는 날짜가 아니라 **시각**만 받는다 (`fetch_minutes_day` 참조 —
    `FID_INPUT_HOUR_1` 하나뿐이다).

    **다만 「분봉은 날짜로 못 부른다」 는 뜻이 아니다.** 같은 날 그렇게 적었다가
    고쳤다 — **날짜를 받는 분봉 API 가 따로 있다.**

        주식일별분봉조회   `inquire-time-dailychartprice` · `FHKST03010230`
        받는 것           `FID_INPUT_DATE_1`(날짜) + `FID_INPUT_HOUR_1`(시각)
        한 번에           **120건** · 보관은 **1년**

    그것을 붙이면 지난 날짜의 5분봉도 채울 수 있다. **아직 안 붙였다** —
    「못 하는 것」 이 아니라 **「아직 안 한 것」** 이다.

    **몇 번 부르는지** — want 를 채우는 데 필요한 횟수에 한 번을 더한다.
    마지막 한 번은 「더 없다」 를 확인하는 몫이다. 무한히 돌지 않게 한다.
    """
    import datetime
    seen = {}
    date_to = datetime.date.today()
    span = datetime.timedelta(days=PERIODS[period]["span_days"])
    cut = SPAN_CUT.get(period)
    done = False

    # 년·월봉은 **구간으로 모은다** (2026-10-02). `ts` 로 모으면 같은 해가
    # 두 줄 남는다 — `floor_to_span` 이 `date_from` 만 구간 첫날로 내리고
    # **`date_to` 는 그대로 쓰기 때문이다.**
    #
    #     1회차  ~ 20261001 을 물었다   →  2026년 봉의 ts = 20261001
    #     2회차  ~ 20260930 을 물었다   →  **같은 2026년인데 ts = 20260930**
    #
    # 뒤엣것은 「1월~9월 30일 누적」 이라 그 해 고가·저가가 빠져 있는데,
    # `ts` 가 달라 서로 다른 봉으로 저장된다. `save_candles` 의 `SPAN_CUT`
    # 지우기는 **넣기 전에 한 번** 도므로 같은 호출 안의 둘을 못 막는다.
    # 2026-10-01 에 삼성전자우 년봉이 그렇게 두 줄이었다.
    #
    # **먼저 받은 것을 남긴다.** 1회차가 범위가 가장 넓고 `ts` 도 가장 크다 —
    # `_prune_span_dupes` 의 「가장 큰 ts 가 최신」 과 같은 판정이다.
    #
    # ⚠️ **주봉·일봉은 이 길로 안 온다.** `SPAN_CUT` 에 없고, 그쪽은 `ts` 가
    # 구간 첫날(주봉은 월요일)로 고정되어 구간 중간부터 물어도 안 어긋난다
    # (2026-09-29 실측 · 겹침 0).
    def span_key(r):
        return r["ts"][:cut] if cut else r["ts"]

    for _ in range(max(1, -(-want // BARS_PER_CALL)) + 1):
        # 구간 중간부터 물으면 **부분 누적**이 온다 — `floor_to_span` 주석 참조.
        # 지수에서 찾은 병인데 같은 API 계열이라 종목에도 건다.
        rows = fetch_bars_from_kis(
            cfg, code, period,
            floor_to_span(date_to - span, period).strftime("%Y%m%d"),
            date_to.strftime("%Y%m%d"))
        fresh = [r for r in rows if span_key(r) not in seen]
        for r in rows:
            k = span_key(r)
            if k not in seen:         # 먼저 받은 것(더 넓은 범위)을 남긴다
                seen[k] = r
        if not fresh:
            done = True               # 더 과거가 없다
            break
        if len(seen) >= want:
            break
        # **구간 키가 아니라 `ts` 에서 구한다.** 년봉은 키가 `2026`(4자리)이라
        # 키로 날짜를 만들면 깨진다.
        oldest = min(r["ts"] for r in seen.values())
        date_to = (datetime.datetime.strptime(oldest, "%Y%m%d").date()
                   - datetime.timedelta(days=1))
    if done or len(seen) < want:
        # 끝까지 훑었다. 다음부터 같은 종목을 또 파고들지 않는다 —
        # 상장이 짧은 종목은 want 를 영영 못 채워서, 이 표가 없으면
        # 화면을 열 때마다 KIS 를 몇 번씩 다시 부른다.
        _meta_set("backfill:%s:%s" % (code, period), "done")
    return sorted(seen.values(), key=lambda x: x["ts"])


_UN_THIN = {}   # minute_market_div — {종목: 날짜} 그날 UN 이 비어 J 로 바꿔 받은 종목(우선주 · ETF) · 그날은 J 먼저


def _un_thin_today(code):
    """그날 분봉에서 UN 이 비어 J 로 받은 종목인가 — minute_market_div · _nx_absent 가 함께 쓰는 셈 한 곳."""
    return bool(code) and _UN_THIN.get(code) == datetime.now(KST).strftime("%Y%m%d")


_NX_PROBE = {}   # _nx_absent — {종목: (날짜, 넥스트레이드에 없나)} 그날 한 번 물어 둔 것


def _nx_absent(cfg, code):
    """**넥스트레이드에 없는 종목인가** — 호가를 KRX(J)로 받을지 가른다 (2026-11-09 qa 검수 e4ed242 돌아옴).

    처음 판은 _UN_THIN(그날 분봉을 KIS 로 받은 프로세스에만 찬다)만 봤는데, 메인(8764) · 중간(8767)은 차트를 8765 에 통째로 넘기고
    호가는 자기 프로세스에서 받아 표가 늘 비었다 — 외부접속이 보는 8764 에서 안 들었다. 그래서 **그날 한 번 넥스트레이드(NX) 호가를 물어
    본다** — 넥스트레이드에 없는 종목은 output1 이 통째로 빈다(11-09 15:43 · 11-10 07:59 · 005935 · 069500 · 있는 종목은 닫혀도 "0" 글자로 칸이 다 온다).
    종목마다 하루 한 번 · 프로세스마다 한 번 늘 뿐이다. **08:00~20:00(넥스트레이드 장)에 물은 것만 그날 값으로 둔다** — 그 밖에는
    넥스트레이드 종목도 비어 올 수 있어 적지 않고 _UN_THIN 만 본다. 아침 첫 호가도 이 길로 풀린다(분봉을 받기 전이어도)."""
    if _un_thin_today(code):
        return True
    now = datetime.now(KST)
    day = now.strftime("%Y%m%d")
    hit = _NX_PROBE.get(code)
    if hit and hit[0] == day:
        return hit[1]
    if not ("0800" <= now.strftime("%H%M") < "2000"):
        return False
    try:
        o = kis_get(cfg, "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
                    {"FID_COND_MRKT_DIV_CODE": "NX", "FID_INPUT_ISCD": code}, "FHKST01010200").get("output1") or {}
    except Exception:
        return False                     # 못 물었다 — 적지 않고 다음에 다시 묻는다 · 그동안은 UN
    # **output1 이 통째로 비었나로 가른다** — 넥스트레이드에 없는 종목은 키가 하나도 없이 오고, 있는 종목은 장이 닫혀도 칸마다 글자 "0" 으로
    # 온다(11-10 07:59 · 005935 · 069500 키 0 · 005930 · 247540 · 000660 키 71 · 다 "0"). 칸 값으로 가르면 "0" 이 참인 것에 기대게 된다(qa 권고)
    absent = not o
    _NX_PROBE[code] = (day, absent)
    return absent


def _note_un_thin(code, first, used, used_nz):
    """UN 을 먼저 물었다가 J 로 바꿔 받았으면 그날은 그 종목을 J 먼저 묻는다 — 바퀴마다 두 번 부르지 않게.

    **J 쪽에 거래가 2개 넘게 있을 때만 적는다.** 15:30~16:00 처럼 둘 다 거래가 0~1개인 칸에서는 비겨서 J 를 고르는데,
    그것으로 보통주를 적으면 그날 정규장을 다시 J 로 받아 넥스트레이드 몫이 또 빠진다."""
    if code and first == MARKET_DIV_CHART and used == "J" and used_nz >= 2:
        _UN_THIN[code] = datetime.now(KST).strftime("%Y%m%d")


def minute_market_div(hour, code=None):
    """분봉을 **어느 시장부터 물어볼까.**

        보통        UN (통합)
        그날 UN 이 비었던 종목(우선주 · ETF)   J  (KRX)

    ── **정규장도 통합이다** (2026-11-09 재권님 「응」 · 카드 「일봉 거래량과 5분봉 합이 크게 갈림」) ──

    전에는 정규장 09:00~15:30 을 J 먼저 물었다(아래 2026-09-17 고침). 그래서 **정규장 5분봉 거래량에 넥스트레이드 몫이 빠졌다** —
    개발 DB 삼성 · 하이닉스 11-03 ~ 11-06 로 잼: 5분봉 합 + 넥스트레이드 정규장 거래량(nx_slot) = 일봉(통합)과 1~3% 안 ·
    5분봉 합만으로는 일봉의 약 75%. 차트 봉은 통합이 기준이라(holdings/CLAUDE.md 「차트 봉은 통합(`UN`)이다」) 분봉도 맞춘다.
    UN 이 못 주는 우선주 · ETF 는 아래 폴백(거래 있는 봉 1개 이하 → J)이 받고, 그날은 `_UN_THIN` 이 J 를 먼저 묻게 해 두 번 부르지 않는다.
    **새로 받는 봉부터다** — 이미 저장된 정규장 봉은 J 값 그대로다.

    아래는 그 전의 기록이다.

    ⚠️ **이것은 「먼저 물어볼 쪽」 이고 최종 선택이 아니다.**
    `fetch_minutes_from_kis` 가 받아 보고 모자라면 **다른 쪽으로 한 번 더** 받는다.

    **일봉과 달리 분봉은 한쪽만으로는 못 채운다** (2026-09-17 실측).

        08:30 프리마켓   J  0개      UN 30개
        10:30 장중       J 30개      UN 30개
        우선주 장중      J 30개      UN  0개   ← 통합은 값이 비어 온다

    삼성전자우 5분봉이 하루 종일 194,600원에 거래량 0 이었던 것이 이 때문이다.

    ── **「늘 `J`」 로 바꾸려다 시뮬레이션에서 뒤집혔다** (2026-10-01) ──

    우선주가 `UN` 에서 전일 종가로 오는 것을 보고 「`J` 를 기본으로」 를
    제안했는데, **33종목 × 4칸 × 양쪽(132칸) 실측에서 그 반대가 나왔다.**

        **`J` 가 `UN` 보다 나쁜 칸   94개**
        **`UN` 이 `J` 보다 나쁜 칸  25개**

    `UN` 은 **통합(거래소+넥스트레이드)** 이라 보통주에서는 거래량이 더 많다.
    `J` 로 통일하면 **보통주 94칸에서 거래가 깎인다.**

    **`UN` 이 못 주는 것은 종류가 정해져 있다 — 우선주와 ETF 다.**

        우선주  005935 · 005387 · 005385
        ETF     069500 · 278530 · 102110 · 229200 · 233740 · 385540
        모양    거래량>0 이 **0~1개** · 종가가 **1~2종**(전일 종가로 채움)
                **37칸 / 132칸**이 그 모양이었다. 정상 칸은 종가가 여러 종이다

    ⚠️ **위 2026-09-17 표의 「08:30 J 0개」 는 그때 값이고 지금은 아니다** —
    `J` 가 프리마켓에도 온다(005930 29/30 · 035720 27/30). 그 줄을 믿고
    「`J` 로 통일하면 프리마켓이 빈다」 고 적었다가 재서 뒤집었다.
    **두 표 다 낡는다 — 고칠 때 다시 잰다.**

    **그래서 시각 분기는 그대로 두고 폴백을 민감하게 한다** — 변경이 작고,
    정규장에 `J` 를 먼저 묻는 2026-09-17 고침도 살아 있다.
    """
    if _un_thin_today(code):
        return "J"
    return MARKET_DIV_CHART


def fetch_minutes_from_kis(cfg, code, hour=None):
    """1분봉. 별도 API 이며 기준 시각부터 과거 30개만 돌려준다.

    hour 를 주지 않으면 '지금까지' 를 기준으로 삼는다. 예전에는 기본값이
    "153000" 이어서, 장중에 최근 구간을 갱신할 때마다 15:00~15:30 자리에
    현재가로 채워진 가짜 봉이 생겼다 (2026-09-14 확인).

    ── **받아 보고 시장을 고른다** (2026-10-01 지시) ──────────────

    재권님이 005935(삼성전자우) 차트를 보시고 **「거래가 있는데 맘대로
    그리는 거」** 로 찾으셨다. 증권사 화면에는 15:30 뒤에도 201,000 봉과
    거래량이 있는데, 우리 화면은 **195,200(= 전일 종가)에 평평**했다.

    **원인은 시장 구분이었다.** `minute_market_div` 가 시각으로만 골라
    15:30 뒤를 `UN`(통합)으로 받는데, **우선주는 `UN` 에서 거래량 0 으로
    오고 KIS 가 그 칸을 전일 종가로 채운다.**

        2026-10-01 실측 (005935 · 각 30봉)
        18:30  J  거래량>0 **30개** · 종가 200,500~201,500  ← 증권사 화면과 같다
        18:30  UN 거래량>0  **0개** · 종가 **195,200** 하나 (= 전일 종가)
        16:00  J  거래량>0   1개  · 종가 203,500 / 204,500
        16:00  UN 거래량>0  **0개** · 종가 **195,200**

    **시각으로는 고를 수 없다.** 그래서 **받아 보고 고른다** — 거래량 있는 봉이
    **1개 이하**면 다른 쪽으로 한 번 더 받아 **더 많은 쪽**을 쓴다. 어느 쪽을
    먼저 물을지는 `minute_market_div` 가 정한다 — **132칸 실측표가 거기 있다**
    (`J` 가 나쁜 칸 94 · `UN` 이 나쁜 칸 25 · `UN` 이 못 주는 것은 **우선주와 ETF**).

    ⚠️ **「전부 0 이면」 만으로는 샌다.** `UN` 이 **거래량 있는 봉 하나 + 나머지
    전부 전일 종가**로 주는 모양이 있어서, 그 하나 때문에 폴백이 안 걸렸다.

        2026-10-01 20:00 칸 (005935)
        UN  봉 30 · 거래량>0 **1개**(20:00 봉 202,000) · 나머지 29개 **195,200**
        J   봉 30 · 거래량>0 **30개** · 201,000~203,000

    그래서 **19:30~19:55 가 전일 종가로 남았다.** `J` 를 먼저 물으면 그 모양이
    안 나온다 — 위 실측에서 `J` 는 늘 27~30/30 이었다. **비율로 가르지 않는
    이유**는 그 값을 박게 되기 때문이고, **먼저 물어보는 쪽을 바꾸는 것으로
    푼다.**

    **거래량 0 봉이 전부 거짓은 아니다.** 같은 날 15:35~15:55 의 204,500 ·
    거래량 0 은 **정상**이다 — 15:30 마감 동시호가가 `V106213` 이고
    넥스트레이드는 16:00 에 열려 **그 사이 거래가 없고 값은 마지막 체결가**다.
    **거짓인 것은 「전일 종가가 들어온 칸」 이다.**

    **비용은 「빈 구간에 한 번 더」** 다. 거래가 있는 구간은 그대로 한 번이다.

    **둘 다 0 이면 먼저 받은 것을 쓴다.** 진짜로 거래가 없는 구간이고,
    그때라도 **기본 시장 쪽 값이 실제 가격에 가깝다**(위 16:00 의 J 가
    203,500 인데 UN 은 전일 종가였다). 여기서 봉을 버리면
    `fetch_minutes_day` 의 「없는 칸만 받기」 가 그 칸을 **바퀴마다 다시
    받아** 느림이 되돌아온다 — 그래서 버리지 않는다.
    """
    if hour is None:
        m = minute_scan_start()
        hour = "%02d%02d00" % (m // 60, m % 60)
    first = minute_market_div(hour, code)
    out = _minutes_one_market(cfg, code, hour, first)
    nz = sum(1 for b in out if (b["volume"] or 0) > 0)
    # ⚠️ **「전부 0 이면」 으로는 샌다 — 「1개 이하」 로 본다** (2026-10-01).
    #
    # `UN` 이 **거래량 있는 봉 하나 + 나머지 전부 전일 종가**로 주는 모양이
    # 있다. 그 하나 때문에 폴백이 안 걸려 **나머지 29개가 전일 종가로
    # 남았다** — 재권님이 19:30~19:55 에서 보신 자리다.
    #
    #     2026-10-01 20:00 칸 (005935)
    #     UN  봉 30 · 거래량>0 **1개**(20:00 봉 202,000) · 나머지 **195,200**
    #     J   봉 30 · 거래량>0 **30개** · 201,000~203,000
    #
    # 37칸 / 132칸이 그 모양이었고 그중 **9칸이 정확히 1개**였다.
    # `not out`(빈 응답)도 `nz == 0` 으로 함께 걸린다.
    if nz <= 1:
        other = "UN" if first == "J" else "J"
        alt = _minutes_one_market(cfg, code, hour, other)
        # **더 나은 쪽만 쓴다.** 둘 다 1개 이하인 칸(거래가 드문 종목)에서
        # 엉뚱한 쪽으로 바꾸지 않는다
        #
        # **같으면 `J` 를 쓴다** (2026-10-06 · 개발2 분석 · 창구). 넥스트레이드 없는 종목(ETF · 우선주)은
        # 15:30 뒤 칸에서 `UN` 0~1개 · `J` 도 동시호가 한 줄(1개)이라 비기는데, 그때 `UN` 이 남으면
        # **빈 줄 종가가 전일 종가**로 깔린다(005935 15:30~15:50 = 201,000 · 069500 = 112,060).
        # `J` 의 빈 줄은 마지막 체결가다.
        alt_nz = sum(1 for b in alt if (b["volume"] or 0) > 0)
        if alt_nz > nz or (alt_nz == nz and other == "J" and alt):
            _note_un_thin(code, first, other, alt_nz)
            return alt
    return out


def _minutes_one_market(cfg, code, hour, div):
    """한 시장(`J` KRX · `UN` 통합)에서 분봉 30개를 받는다."""
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
        {
            "FID_ETC_CLS_CODE": "", "FID_COND_MRKT_DIV_CODE": div,
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


def fetch_minutes_day(cfg, code, max_past=None, refill=False):
    """그날 1분봉을 모은다 → (봉 목록, 받은 범위 목록 [(시작 분, 끝 분)]).

    KIS 분봉 API 는 기준 시각부터 과거 30개만 돌려주므로, 시각을 30분씩
    거슬러 내려가며 여러 번 부른다. 통합 시장이라 넥스트레이드 시간대
    (~20:00)까지 포함한다. 시작 시각은 minute_scan_start() 가 정한다 — 미래를 묻지 않는다.

    ── **「끝난 뒤에 받은 칸」 만 건너뛴다** (2026-10-06 재권님 「응 이거 맞아 해줘」) ──

    재권님이 LG화학 5분봉이 10시 자리에서 **갭 상승처럼** 뚝 올라간 것을 보셨다. 10:05~10:55
    열한 봉이 저장되지 않아 10:00 봉 다음에 11:00 봉이 붙어 있었다(그날 203종목 중 193종목이
    같은 시간대에 비었다). 전에는 **「30분 칸에 봉이 하나라도 있으면 다 받은 것」** 으로 보고
    건너뛰어 반쯤 빈 칸을 영영 못 메웠고, 받던 순간 자라던 봉(덜 찬 봉)도 다시 안 받았다.

    이제는 **그 칸이 끝난 뒤에 받았는지**를 적어 두고(`_minutes_done`) 그것만 건너뛴다.
    봉 개수를 세지 않으므로 거래가 드문 칸도 한 번 받으면 끝이다(전의 느림이 안 돌아온다).

    **칸 경계를 5분 칸에 맞춘다.** 첫 칸(지금까지 30분)만 지금 시각에서 끝나고, 그 뒤는
    끝 분이 5로 나눠 4가 남는 자리(…:59 · …:04)다 — 한 5분 칸이 두 묶음에 갈려 한쪽만 받으면
    덜 찬 봉이 된다(LG화학 11:00 봉 거래량 2,136 · 다시 묶으면 3,701).

    `refill` — 「끝난 뒤 받음」 표(`m5done`)를 안 보고 그날을 다 받는다. 1분봉을 그날 처음 열 때만 쓴다(2026-11-11 재권님
    「이렇게 그려야 하는데」 — 토스 1분봉처럼 빈 칸 없이). 그 표는 종목마다 하나라, 1분봉을 함께 저장하기 전에 5분봉으로 받은
    칸은 1분봉이 비어 있다. 화면이 연 그 종목 하나만 · 그날 한 번이라 미리받기 호출은 안 는다.

    `max_past` — 이미 지난 칸을 이번에 몇 개까지 받나. 미리받기와 화면 열기가 한 번에
    오래 걸리지 않게 나눠 메운다(최근 칸부터). `None` 이면 다 받는다.
    """
    bars, cover, newly = {}, [], []
    start = minute_scan_start()
    if start < MINUTE_DAY_START:
        return [], []
    now_m = _minutes_now_min()
    got_min = set() if refill else _minutes_done_cover(_minutes_done(code))
    ends = _minute_chunk_ends(start)
    past = 0
    for t in ends:
        over = t < now_m                             # 그 칸이 이미 끝났나
        if over and all(m in got_min for m in range(max(t - 29, MINUTE_DAY_START), t + 1)):
            continue
        if over and t != start:
            if max_past is not None and past >= max_past:
                break
            past += 1
        hour = "%02d%02d00" % (t // 60, t % 60)
        try:
            got = fetch_minutes_from_kis(cfg, code, hour)
        except RuntimeError:
            continue          # 해당 구간에 데이터가 없을 수 있다. 계속 진행.
        for b in got:
            bars[b["ts"]] = b
        cover.append((t - 29, t))
        if over:
            newly.append(t)
    if newly:
        _minutes_mark_done(code, newly)
    return sorted(bars.values(), key=lambda x: x["ts"]), cover


#: 미리받기 · 화면 열기가 한 번에 받을 「이미 지난 칸」 수 — 나머지는 다음에 (최근 칸부터)
MINUTE_PAST_PER_CALL = 6


def _minutes_now_min():
    """지금이 그 거래일의 몇 분째인가. 거래일이 지났으면(주말 · 다음 날 새벽) 하루 끝 뒤로 친다."""
    now = datetime.now(KST)
    if now.strftime("%Y%m%d") != _minutes_trade_day():
        return 24 * 60
    return now.hour * 60 + now.minute


def _minutes_done(code):
    """그 거래일에 **끝난 뒤에 받은** 30분 칸의 끝 분 집합 (`sync_meta` 의 `m5done:<코드>`)."""
    v = _meta_get("m5done:%s" % code) or ""
    day, _, rest = v.partition("|")
    if day != _minutes_trade_day():
        return set()
    return {int(x) for x in rest.split(",") if x.strip().isdigit()}


def _minute_chunk_ends(start):
    """`fetch_minutes_day` 가 받는 30분 칸들의 끝 분 — 첫 칸은 `start`(지금까지), 그 뒤는 **고정 눈금 …29 · …59**.

    ⚠️ **끝을 지금 시각에서 거꾸로 세지 않는다** (2026-10-06 · 8e4a5dd 결함). 그렇게 세면 칸 자리가 5분마다
    밀려, 5분마다 모든 종목에 「끝났는데 덜 받은 조각」 이 새로 생겼다 — 미리받기가 두 서버 합쳐 440종목을
    5분마다 다시 불러 16:30 에 KIS 예산 73% 까지 찼다. 눈금을 고정하면 끝난 칸은 한 번 받으면 다시 안 생긴다
    (30분에 한 칸). 첫 칸(`start-29`~`start`)은 마지막 눈금 뒤를 늘 덮는다 — 둘 사이가 30분 안이라서.
    """
    ends = [start]
    e = start - 1 - (start - 1 - 29) % 30            # start 보다 앞인 가장 늦은 눈금(…29 · …59)
    while e >= MINUTE_DAY_START:
        ends.append(e)
        e -= 30
    return ends


def _minutes_done_cover(done):
    """끝난 뒤 받은 칸들이 덮은 **분** 집합.

    칸 끝은 지금 시각에 따라 30분 안에서 5분씩 밀린다(첫 칸이 지금에서 끝나므로) — 끝 분이
    같은지로 보면 앞서 받은 칸이 거의 안 맞아 **받은 칸을 또 받는다.** 분으로 덮였는지 본다.
    """
    return {m for d in done for m in range(d - 29, d + 1)}


def _minutes_holes(code):
    """그 종목에 **이미 끝났는데 아직 끝난 뒤에 못 받은** 30분 칸이 몇 개인가 (2026-10-06).

    미리받기 관문(`prefill_due` · `_prefill_one`)이 5분 구간 표식(`pf5m`)만 보면, 마감 뒤에는
    표식이 1530 에 멈춰 종목당 한 번(지난 칸 6개)만 받고 끝난다 — 남은 구멍이 다음 날까지 갔다
    (10-06 15:4x 빈 종목 193→192 · 4분). 이것으로 「구멍이 남은 종목」 도 다시 차례에 든다.
    `fetch_minutes_day` 와 같은 칸 목록 · 같은 `m5done` 을 보므로 받은 칸은 다시 안 센다.
    """
    start = minute_scan_start()
    if start < MINUTE_DAY_START:
        return 0
    now_m = _minutes_now_min()
    got_min = _minutes_done_cover(_minutes_done(code))
    return sum(1 for t in _minute_chunk_ends(start)
               if t < now_m and not all(m in got_min for m in range(max(t - 29, MINUTE_DAY_START), t + 1)))


def _minutes_hole_due(code, want):
    """구멍 메우기로 그 종목을 받을 차례인가 — 새 봉이 생길 수 있는 동안 · 구멍이 남았고 ·
    **이 구간에 받아 봤는데 구멍이 안 줄어 그만둔 종목이 아니다**(`pf5mh`).

    KIS 가 늘 실패하는 칸이 있으면 그 칸은 영영 「끝난 뒤 받음」 이 안 적힌다 — 막지 않으면
    그 종목만 쉬는 틈마다 다시 부른다. 그만둔 표식은 구간(`want`)이 바뀌면 풀린다.
    """
    return (_minutes_live() and _meta_get("pf5mh:%s" % code) != want
            and _minutes_holes(code) > 0)


def _minutes_mark_done(code, ends):
    done = _minutes_done(code) | set(ends)
    _meta_set("m5done:%s" % code,
              _minutes_trade_day() + "|" + ",".join(str(x) for x in sorted(done)))


def _minutes_fresh_upto(code):
    """그 거래일에 「지금 칸」(지금까지 30분)을 마지막으로 받은 **분**(`sync_meta` 의 `m5upto:<코드>`) — 없으면 None.

    그 분 앞에서 끝난 5분봉은 다 끝난 뒤 받은 값이다. 「전날 같은 시각 대비 거래량 %」 가 이것으로 덜 찬 봉을 뺀다
    (2026-11-11 qa 돌려보냄 — 봉 끝 시각만 보고 세어 09:15 → 09:19 사이 하이닉스가 36% → 50% · 재권님 「가」)."""
    v = _meta_get("m5upto:%s" % code) or ""
    day, _, m = v.partition("|")
    if day != _minutes_trade_day() or not m.isdigit():
        return None
    return int(m)


def _minutes_mark_fresh(code, minute):
    """「지금 칸」 을 받아 **저장한 뒤** 부른다 — 받기 전 분을 적는다(받는 데 몇 초 걸려도 그 뒤 분을 적지 않게). 줄지 않는다."""
    old = _minutes_fresh_upto(code)
    if old is None or minute > old:
        _meta_set("m5upto:%s" % code, "%s|%d" % (_minutes_trade_day(), minute))


def _keep_covered_slots(bars5, cover, now_m):
    """받은 범위에 다섯 분이 다 든 5분봉만 남긴다 — 지금 자라는 칸은 둔다.

    한쪽만 받은 5분 칸을 저장하면 **멀쩡하던 봉을 덜 찬 봉으로 덮어쓴다**(`ON CONFLICT … UPDATE`).
    """
    out = []
    for b in bars5:
        s = int(b["ts"][8:10]) * 60 + int(b["ts"][10:12])
        if s + 4 >= now_m or all(any(lo <= m <= hi for lo, hi in cover) for m in range(s, s + 5)):
            out.append(b)
    return out


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
# ⚠️ **화면이 느려지면 안 된다.** 모든 KIS 호출이 초당 10건 줄에 서므로,
# 미리 받기가 연달아 부르면 그 뒤에 온 화면 요청이 밀린다. 종목 사이에
# 쉬어서 그 틈으로 화면 요청이 들어가게 한다.
# 받는 종목은 순위 목록 전부(2026-11-12 부터 시가총액 `dart.UNIVERSE_MIN_CAP_EOK` 이상 · 그 전 코스피 200 · 코스닥 150) — 2026-11-09 바닥 신호를 그 목록으로 넓히며(재권님 「판정 조건은 코스피 200 코스닥 150」)
# 전에는 코스피 상위 100(`PREFILL_TOP`)이었다. 새 봉만 받으므로 종목마다 5분에 한 번쯤 — 늘어난 250종목은 초당 1번 안쪽(그날 예산 초당 40 중 약 13 사용)
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
# ── 보이는 종목을 먼저 · 구간마다 · 양보 가르기 (2026-10-03 지시 (가)~(다)) ──
#
# 재권님 — 「화면에 보여질 종목들은 미리미리 호출되어 있어야」 · 「보이지 않는 종목들은
# 후차로 차근차근 받아서 저장」. 전에는 셋이 막았다.
#   ㉠ 한 바퀴를 돌고 **30분** 쉬었다 — 5분봉은 5분마다 생긴다
#   ㉡ 순서를 **바퀴 시작에 한 번만** 뽑았다 — 도중에 새로 보인 종목은 다음 바퀴
#   ㉢ 화면이 보고 있으면 **보이는 종목까지** 비켜섰다 — 화면을 위한 일인데
# 그래서 (가) 종목을 **하나 받을 때마다** 순서를 다시 뽑고(`_prefill_one`),
# (나) 다 돌면 30분이 아니라 **새 5분 구간이 닫혔나**만 짧게 보며(KIS 안 부름) 기다리고,
# (다) 화면이 최근 물은 종목(`PREFILL_HOT_SEC` 안)은 **비켜서지 않는다.** 나머지(3순위 —
# 최근 본 것 · 시총 상위)는 전처럼 비켜서며 뒤에서 받아 저장한다.
PREFILL_SLOT_POLL_SEC = 20   # 다 돈 뒤 새 구간이 닫혔나 보는 간격 — KIS 를 안 부른다
PREFILL_HOT_SEC = 60         # 이 안에 화면이 물은 종목 = 지금 보이는 것(1·2순위)

# ── 화면이 보고 있으면 더 쉰다 (2026-09-18) ────────────────────────
#
# 위 3.5 초는 **화면이 없을 때** 기준이다. 종목 하나가 하루치 5분봉을 받느라
# KIS 를 스물몇 번 부르므로, 쉬는 시간을 그만큼 잡아도 초당 3회쯤을 계속 쓴다.
# **그때 예산이 초당 5회라** 화면 몫이 2회밖에 안 남았다 (지금은 10회다).
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
# **예산 열 중 여덟이** 늘 비어 있고, 화면이 열리는 순간 그 자리로 들어간다.
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

# ── 「갱신될 때만」 을 **봉 구간**으로 가른다 (2026-10-01 지시) ─────
#
# **경과 시간으로 가르면 어긋난다.** 위 300초를 「마지막으로 받은 지 이만큼
# 지났나」 로 썼는데, **한 바퀴가 6~8분 + 쉬는 1800초**라 돌아올 때마다
# 300초가 지나 있어 **늘 참**이었다 — 2026-09-18 의 고침이 그 자리를 못 넘었다
# (2026-10-01 실측 — 300초 안쪽인 종목 **0 / 111**).
#
# **봉 구간으로 가르면 한 바퀴가 얼마든 안 어긋난다.** 같은 구간을 두 번 받지
# 않고, **구간이 안 늘어나는 동안(장 마감 뒤 · 주말)은 아예 안 받는다** —
# 하루의 17.5시간이 거기다. 재권님 말씀 「5분봉 갱신될때만 받기」 그대로다.
#
# **300 은 그대로 쓴다 — 이제 「5분봉 한 칸」 이라는 뜻이다.**
#
# ⚠️ **휴장일은 모른다.** 공휴일에는 구간이 늘어나는 것처럼 보여 받으러
# 가는데, **한 바퀴 주기가 천장이라 지금보다 나빠지지는 않는다.**
#
MINUTE_SESSION_END = "1530"    # 정규장이 끝난 뒤의 **표식**. 실제 봉 시각이 아니다


def prefill_due(code, want=None):
    """그 종목을 **지금 받아야 하나.** 미리받기 관문이다.

    **함수로 꺼내 둔 이유** — `--slow` 서버는 미리받기를 끄므로 루프를 돌려
    볼 수가 없다. 관문만 따로 부를 수 있으면 **가짜 시각으로 시험**할 수 있다
    (2026-10-01).
    """
    if want is None:
        want = _last_closed_5m_slot()
    if _meta_get("pf5m:%s" % code) != want:
        return True
    # 새 봉이 생길 수 있는 동안은 **구멍이 남은 종목도** 받는다 — 그 밖(20:10 뒤 · 주말)은
    # get_chart 가 하루치를 다시 안 받으므로 불러도 메워지지 않는다
    return _minutes_hole_due(code, want)


def _last_closed_5m_slot(now=None):
    """지금 기준 **이미 완성된** 마지막 정규장 5분봉 구간 (YYYYMMDDHHMM).

    장중이면 직전 경계, 장이 끝난 뒤면 그날 표식, 장 전·주말이면 **직전
    거래일의 표식**이다. 이 값이 안 바뀌는 동안은 새 봉이 없다는 뜻이라
    미리받기가 쉰다.
    """
    now = now or datetime.now(KST)

    def prev_session(d):
        d = d - timedelta(days=1)
        while d.weekday() >= 5:              # 토·일은 거슬러 올라간다
            d = d - timedelta(days=1)
        return d.strftime("%Y%m%d") + MINUTE_SESSION_END

    if now.weekday() >= 5:                   # 주말
        return prev_session(now)
    open_t = now.replace(hour=9, minute=0, second=0, microsecond=0)
    close_t = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if now < open_t:
        return prev_session(now)
    if now >= close_t:
        return now.strftime("%Y%m%d") + MINUTE_SESSION_END
    # 지금 속한 구간은 **아직 자라는 중**이다. 완성된 것은 그 앞
    bar_min = PREFILL_FRESH_SEC // 60
    cur = now.replace(minute=(now.minute // bar_min) * bar_min,
                      second=0, microsecond=0)
    done = cur - timedelta(minutes=bar_min)
    if done < open_t:
        return prev_session(now)
    return done.strftime("%Y%m%d%H%M")

_last_ui_at = 0.0              # 화면이 마지막으로 /api/kis/* 를 부른 시각


# ── 화면이 **어느 종목**을 보고 있나 (2026-10-01 지시) ────────────
#
# 재권님이 받는 순서를 넷으로 정하셨다.
#
#     1 모달이 열린 종목    맨 먼저 · 가장 자주
#     2 화면에 보이는 종목   그다음 (실시간 갱신은 여기까지)
#     3 오른쪽 목록 · 정렬에 쓰이는 종목
#     4 나머지             차차 · 천천히 (미리받기)
#
# **아래 `_mark_ui_call` 은 「언제」 만 적어서 1~3 을 가를 수가 없었다.**
# 그래서 미리받기가 넷을 구분 없이 시가총액 순서로 돌았다 — **1순위가 가장
# 드물고(모달은 열 때 한 번) 4순위가 가장 자주 도는** 꼴이었다 (2026-10-01 실측).
#
# **정보는 이미 매 요청에 들어온다.** 적기만 하면 된다.
#
#     모달       `asking?code=` · `ticks?code=`    **5초마다**
#     보이는 줄   `prices?codes=a,b,c`             **30초마다 목록째**
#
# **순위 표를 두지 않는다.** 「어느 종목이 몇 순위」 를 적으면 화면이 바뀔
# 때마다 낡는다 — **최근에 물어본 순서**가 곧 그 순위다.
#
# **모달 룰과 부딪히지 않는다.** 「모달은 목록 폴링에 얹혀 있다」 는 **시세**
# 이야기이고(`home.js` 의 `applyPrices`), 여기서 적는 것은 **순서**다.
UI_SEEN_MAX = 400          # 이만큼만 들고 있는다. 넘으면 오래된 것부터 버린다
_ui_seen = {}              # 종목코드 -> 화면이 마지막으로 물어본 시각(monotonic)

# ── 화면이 「어느 자리에서」 봤나 (2026-10-03 · 설계서 (라)) ──────────
#
# `_ui_seen` 은 「최근에 물었다」 만 안다. 화면이 요청에 `view=` 를 붙이면 자리를 안다.
#     modal   모달이 연 종목            ┐ 1순위 — 모달 룰 「어느 순위에 있든 1순위」
#     direct  검색 · ?code= 로 들어온 종목 ┘ (재권님 「화면에 보일 종목과는 다른 이벤트」)
#     row     보이는 줄(순위표 시세 묶음)    2순위
# **쿼리다 — 헤더가 아니다.** 롱폴의 안쪽 호출이 u 주소를 그대로 다시 부르는데 헤더는 안
# 따라간다. 표시가 없으면 지금처럼 「최근에 물었다」 로만 센다(뒤로 맞음).
UI_VIEW_RANK = {"modal": 0, "direct": 0, "row": 1}
_ui_view = {}              # 종목코드 -> (등급, 시각 monotonic)
_ui_seen_lock = threading.Lock()


def _mark_ui_call(path=""):
    """화면이 KIS 를 썼다고 적어 둔다. 미리받기가 이것을 보고 양보한다.

    **종목까지 적는다** (2026-10-01) — 위 주석 참고. `path` 를 안 주면
    전처럼 시각만 적는다.
    """
    global _last_ui_at
    _last_ui_at = time.monotonic()
    if not path:
        return
    try:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
    except Exception:
        return                     # 주소가 이상해도 시각은 이미 적었다
    raw = list(qs.get("code", []))
    for v in qs.get("codes", []):
        raw.extend(v.split(","))
    now = time.monotonic()
    rank = UI_VIEW_RANK.get((qs.get("view") or [""])[0].strip().lower())
    with _ui_seen_lock:
        for c in raw:
            c = c.strip()
            # **종목코드만 적는다.** `code=KOSPI` 처럼 지수 이름도 오는데
            # 그것을 넣으면 미리받기가 없는 종목을 받으러 간다.
            # **미국 티커도 적는다** (2026-10-12 재권님 「응 해줘」) — 미국 미리받기 · 봉 채우기가 순서에 쓴다.
            # 국내 5분봉 미리받기는 `_prefill_codes` 가 6자리만 골라 안 섞인다
            if _is_kr_code(c) or us_universe.is_us(c):
                _ui_seen[c] = now
                if rank is not None:
                    _ui_view[c] = (rank, now)
        if len(_ui_seen) > UI_SEEN_MAX:
            old = sorted(_ui_seen.items(), key=lambda kv: kv[1])
            for c, _ in old[:len(_ui_seen) - UI_SEEN_MAX]:
                _ui_seen.pop(c, None)
                _ui_view.pop(c, None)


def _ui_busy():
    return (time.monotonic() - _last_ui_at) < PREFILL_BUSY_WINDOW


def _is_kr_code(c):
    return len(c) == 6 and c.isdigit()


def _ui_key():
    """종목 → 줄 세우기 열쇠(작을수록 앞). 모달·직접 > 보이는 줄(`PREFILL_HOT_SEC` 안) > 그 밖 최근 본 것 > 안 본 것.
    안 본 종목은 모두 같은 열쇠라 **안정 정렬이면 원래 순서가 그대로 남는다** — 화면이 없는 시각(밤)에는 지금과 같다.
    네 곳(국내 5분봉 · 미국 미리받기 · 밤 받기 · 봉 채우기)이 이 하나를 쓴다 (2026-10-12 · 설계서 3번)."""
    with _ui_seen_lock:
        seen = dict(_ui_seen)
        view = dict(_ui_view)
    now = time.monotonic()
    unseen = (len(UI_VIEW_RANK) + 1, 0.0)

    def key(c):
        t = seen.get(c)
        if t is None:
            return unseen
        r = view.get(c)
        rank = r[0] if r and now - r[1] < PREFILL_HOT_SEC else len(UI_VIEW_RANK)
        return (rank, -t)
    return key, seen


def _ui_order(codes, keep=None, keep_sec=None):
    """`codes` 를 화면 순서로 다시 세운다. `keep(c)` 가 참인 종목은 **목록 밖이어도 앞에 넣는다**
    (모달 룰 「모달 열린 종목은 어느 순위에 있든 1순위」). `keep_sec` 이 있으면 목록 밖 종목은 그 초 안에 본 것만 넣는다."""
    key, seen = _ui_key()
    if not seen:
        return list(codes)
    inlist = set(codes)
    now = time.monotonic()
    extra = [c for c in seen if c not in inlist and keep and keep(c)
             and (keep_sec is None or now - seen[c] < keep_sec)]
    return sorted(list(codes) + extra, key=key)


def _prefill_codes():
    """미리 받을 종목. 코스피 시가총액 상위 순서."""
    try:
        # 순위 목록 전부 — 코스피가 먼저(2026-11-09 · 바닥 신호 signal_watch.low_codes 와 같은 목록. 그 전 10-06 에는 코스피 100 만)
        codes = [r["stock_code"] for r in dart.universe_rows(None)]
    except Exception:
        codes = []
    if not codes:                      # 순위가 아직 없으면 관심종목이라도
        codes = dart.watchlist()

    # **화면이 최근에 본 것부터 간다** (2026-10-01 지시 — 네 단계).
    # 모달이 열린 종목이 가장 최근이라 맨 앞에 서고, 보이는 줄이 그다음,
    # 나머지는 시가총액 순서 그대로 뒤에 남는다. **순위 표를 두지 않는다.**
    #
    # **목록 밖이어도 화면이 열었으면 받는다** — 모달 룰의 「모달 열린 종목은
    # 어느 순위에 있든 1순위」 그대로다.
    # (라) 화면이 자리를 알렸으면 그 등급이 먼저 — modal · direct > row > 그 밖 최근 본 것.
    # 등급은 `PREFILL_HOT_SEC` 동안만 듣는다(그 뒤엔 「최근 본 것」 으로 내려간다). 국내 6자리만 — 미국 티커는 미국 줄이 받는다
    return _ui_order(codes, keep=_is_kr_code)


def _prefill_hot_codes(now=None):
    """화면이 `PREFILL_HOT_SEC` 안에 물은 종목 — 지금 보이는 것(1·2순위).

    순위표 시세 묶음(`codes=`)이 보이는 줄을 몇 초마다 묻고, 모달 · 검색으로 연 종목은
    차트 · 가격(`code=`)이 묻는다. 그래서 「최근에 물었다」 가 「지금 보인다」 와 거의 같다.
    모달 · 직접 진입을 화면이 분명히 알리는 것은 (라)다.
    """
    now = now if now is not None else time.monotonic()
    with _ui_seen_lock:
        return {c for c, t in _ui_seen.items() if now - t < PREFILL_HOT_SEC}


def _prefill_one(cfg, want):
    """(가) 다음 받을 종목 **하나**를 그 자리에서 뽑아 받는다. 받았으면 그 코드, 없으면 `None`.

    순서를 매번 다시 뽑으므로 방금 보인 종목이 바로 앞에 선다. 그 구간을 이미 받아
    봤으면 건너뛴다(`prefill_due`) — 장이 끝난 뒤와 주말에는 구간이 안 늘어 한 종목도 안 받는다.
    """
    # **뒤쪽은 가장 오래 안 받은 종목부터** (2026-10-06). 전에는 5분 구간이 바뀔 때마다
    # 줄을 처음부터 세워, 화면이 열려 있는 동안(종목 사이 20초) 앞쪽 열댓 종목만 받고
    # 뒤쪽은 굶었다 — 10-06 에 203종목 중 193종목이 같은 시간대에 비었다(10-03 45e5892).
    # 화면에 보이는 종목(1·2순위)은 그대로 맨 앞이다.
    hot_set = _prefill_hot_codes()
    live = _minutes_live()
    due = []
    for c in _prefill_codes():
        last = _meta_get("pf5m:%s" % c) or ""
        if last != want:
            due.append((c, (0, last)))
        elif (live and _minutes_hole_due(c, want)
              and time.time() - float(_meta_get("sync:%s:5m" % c) or 0) > PERIODS["5m"]["fresh_sec"]):
            # 방금 받은 종목(`fresh_sec` 안)은 get_chart 가 안 받으므로 지금 뽑으면 헛걸음이고,
            # 구멍이 안 줄었다고 그만둔 표식까지 찍힌다 — 그 틈이 지나면 다시 든다
            # **구멍이 남은 종목은 새 구간 종목 다음** (2026-10-06 재권님 「응 해줘」) — 그중에서도
            # 가장 오래 안 받은 순. 방금 받은 종목은 `fresh_sec`(30초) 안이면 get_chart 가 안 받으므로
            # 같은 종목을 연달아 뽑지 않게 마지막 받은 시각으로 줄 세운다
            due.append((c, (1, "%020.3f" % float(_meta_get("sync:%s:5m" % c) or 0))))
    # 보이는 종목의 **구멍 메우기는 앞에 세우지 않는다** — 보이는 종목은 쉬지 않고 받으므로
    # 30초 안에 다시 뽑히면 get_chart 가 안 받은 채 같은 종목을 계속 돈다
    hot_due = [c for c, k in due if c in hot_set and k[0] == 0]
    rest = sorted((x for x in due if x[0] not in hot_due), key=lambda x: x[1])   # 안정 정렬 — 같으면 원래 순서
    code = hot_due[0] if hot_due else (rest[0][0] if rest else None)
    if code is None:
        return None
    hot = code in hot_due
    filling = _meta_get("pf5m:%s" % code) == want         # 새 구간이 아니라 구멍 메우기로 뽑혔다
    holes0 = _minutes_holes(code) if filling else 0
    _prefill_hot.on = hot
    try:
        # 하루치는 하루 한 번만. 나머지는 최근 구간만 받는다
        get_chart(cfg, code, "5m", 1, gap_check=False)
    except Exception:
        pass                       # 한 종목이 실패해도 나머지는 간다
    finally:
        _prefill_hot.on = False
    # **실패해도 적는다.** 안 적으면 그 종목만 계속 다시 부른다 — 다음 구간에 저절로 또 온다
    _meta_set("pf5m:%s" % code, want)
    if filling and _minutes_holes(code) >= holes0:
        _meta_set("pf5mh:%s" % code, want)               # 받아도 안 줄었다 — 이 구간은 그만
    if not hot:
        # 3순위는 화면이 보고 있으면 길게 쉰다. 지수·시세가 먼저다
        time.sleep((PREFILL_BUSY_REST_SEC if _ui_busy() else PREFILL_REST_SEC) * fill_factor())
    return code


# ── 일·주·월·년봉 한 바퀴 ──────────────────────────────────────
#
# **바뀌는 때를 아는 데이터는 그때만 받는다** (2026-10-01 지시 원문의 공통 룰).
# 재권님 결정(2026-10-02 14:4x) — 「5분봉 · 일봉은 바뀔 때마다 · **주·월·년봉은
# 마지막 봉을 장 마감 때 한 번**」 · 「일·주·월·년봉은 **쌓아 둔다**」.
# 그래서 이 바퀴는 **통합 거래가 끝난 뒤(20:10) 거래일마다 한 번** 네 주기의 마지막 봉을 받는다.
# 장중의 일봉은 화면이 열 때 받는 길이 따로 있다.
#
# **쌓아 둔다** — 캔들은 기간으로 지우지 않는다. 지우는 것은 같은 구간의
# 옛 줄뿐이다(`_save_candles_write` 주석).
#
# **왜 미리 받나** — 2026-10-02 실측으로 DB 에 일봉이 **12종목**뿐이었다
# (주 6 · 월 8 · 년 8). 종목 차트를 열 때마다 **매번 KIS 왕복**이었다.
# 한 번 쌓아 두면 **그 뒤로는 하루 한 번 그날 봉만** 받으면 된다.
#
# **첫 바퀴만 비싸다** — 2026-10-02 실측으로 종목당 19건 · 348종목 6,612건(48.7분).
# 그 뒤는 하루 348종목 × 네 주기 = **1,392건** 안팎이다(마지막 봉만 · 아직 안 쟀다).
#
# **기존 `prefill-5m` 틀을 그대로 쓴다.** 새로 짜지 않는다 — 종목 순서 · 양보 ·
# 「받았나」 기록이 이미 거기 있다. 다른 것은 **무엇을 구간으로 보느냐**뿐이다.
DWMY_THREAD_NAME = "prefill-dwmy"
DWMY_PERIODS = ("D", "W", "M", "Y")

#: 네 주기 모두 이 개수까지 거슬러 받는다.
#:
#: **화면의 일봉이 400 이라 그것에 맞춘다** (`chart.js` 의 `FETCH_BARS`).
#: 거기 주석대로 **`limit` 이 보관량을 정한다** — 적게 받아 두면 그 양에서
#: 멈추고, 화면이 더 요구하면 그때 또 받는다. **밤에 받은 값이 헛일이 된다.**
#:
#: **주·월·년도 같은 400 으로 둔다 — 화면보다 넉넉히다** (화면은
#: `BARS_FOR_IND` ≈ 260~320). 주기마다 다른 값을 두면 **그 값이 네 곳**이 되고
#: 화면의 상수와 갈린다. 넉넉히 받는 비용은 작다 — 네 주기 다 **데이터가
#: 짧아 일찍 멈춘다**(2026-10-02 실측 — 년봉은 삼성전자도 46봉뿐).
DWMY_WANT = 400

#: 한 바퀴를 도는 시각(분) — **통합(UN) 거래가 끝난 뒤 10분**이다(2026-10-03 지시).
#:
#: 재권님 말씀 — 「종가는 3시반이긴 하지만 **거래는 8시까지**」. 일봉을 통합으로
#: 받으므로(넥스트레이드 애프터마켓 포함) 16:00 에 받으면 **덜 된 봉**일 수 있다.
#: 거래가 끝나는 시각은 위 `MINUTE_DAY_END`(20:00)가 이미 들고 있어 그것에서 센다 —
#: 20:00 을 여기 또 적으면 두 곳이 된다.
#:
#: **10분은 여유다 — 근거를 아직 못 쟀다.** 20:00 체결이 KIS 일봉에 언제 들어가는지
#: 모른다. 2026-10-06(월) 16:05 · 20:05 에 같은 종목의 UN · J 일봉 · 주봉 마지막 봉을
#: 견주어 닫는다. 새벽에 돌면 「어제까지」 만 들어와 다음 날 그날 봉을 다시 받게 된다.
DWMY_AT_MIN = MINUTE_DAY_END + 10          # 20:10

#: 종목 사이 쉬는 시간. **한 번에 몰지 않고 길게 늘인다** (창구 판단).
#: 348종목 × 5초 = 29분에 걸쳐 돈다. 마감 뒤라 급할 일이 없다.
DWMY_REST_SEC = 5.0
DWMY_CHECK_SEC = 60            # 시각을 이만큼마다 본다

#: **기본은 꺼짐이다.** 첫 바퀴가 KIS 를 몇 분간 쓰므로 「켜기」 는 따로
#: 지시받는다 (「커밋 → 푸시 → 배포 → **켜기**」). 켤 때 `KJC_DWMY=1`.
#:
#: **코드가 들어가는 것과 도는 것은 다른 일이다** — 이 줄이 그 둘을 가른다.
DWMY_ON = (os.environ.get("KJC_DWMY") or "").strip().lower() in (
    "1", "true", "yes", "on")


def _dwmy_codes():
    """한 바퀴 돌 종목 — **국내** 지수 구성종목 전체 (2026-10-02 지시 「348」).

    ⚠️ **국내 묶음만 읽는다** (2026-10-07). 같은 표에 나스닥100(`us_universe.NDX100`)이 들어오면서,
    전체를 읽으면 미국 티커 101개가 국내 API 로 밤마다 불려 헛걸음이 된다.
    """
    codes = [c for c, _ in dart.INDEX_LISTS]
    try:
        with dart._db_lock, dart.db_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT stock_code FROM index_members WHERE index_code IN (%s) "
                "ORDER BY stock_code" % ",".join("?" * len(codes)), codes).fetchall()
        return [r["stock_code"] for r in rows]
    except Exception:
        return []


def _dwmy_slot(period, now):
    """그 주기를 **언제 다시 받나** — **마지막 거래일**에 한 번이다.

    재권님 결정(2026-10-02 14:4x) — 「주·월·년봉은 **마지막 봉을 장 마감 때
    한 번**」. 이번 주·달·해의 봉은 아직 자라는 중이라 거래일마다 바뀐다. 처음에는
    주·달·해가 **바뀔 때만** 받게 짰는데, 그러면 이번 주 봉이 월요일 값에서 멈춘다.

    **그날 날짜가 아니라 마지막 거래일이다 (2026-10-03 지시).** 날짜로 두면
    **토·일에도** 새 키가 생겨 한 바퀴(하루 약 1,392건)를 헛돈다 — 새 봉이 없다.
    토·일은 금요일 키가 되어 금요일에 받았으면 건너뛴다. **휴일은 못 가른다** —
    달력이 없다(`_last_closed_5m_slot` 도 같다). 휴일에는 한 바퀴를 더 돈다.

    `period` 를 받는 것은 기록 키(`pfW:…`)를 주기마다 따로 두려는 것이다 —
    한 주기가 실패해도 나머지를 다시 부르지 않는다.
    """
    d = now
    while d.weekday() >= 5:                  # 토·일은 금요일로 거슬러 간다
        d = d - timedelta(days=1)
    return d.strftime("%Y%m%d")


def _kr_evening_tail(cfg, code, day):
    """그날 **저녁 마지막 두 시간(18:01~20:00) 1분봉을 지난 날 길로 다시 받아** 5분봉을 덮는다 → 저장한 봉 수 (2026-11-09).

    재권님 — 「토스증권이랑 비교해서 거기랑 맞춰줘」. 토스 1분봉과 견주니 19:30~20:00 칸만 우리 거래량이 토스의
    9~34% 였다(삼성 · 하이닉스 11-03 ~ 11-06 · 19:25 칸까지는 꼭 같음). 미리받기가 그 30분 칸이 **끝나기 전에** 받은 덜 찬 봉이
    그대로 남은 것이다. KIS 지난 날 분봉(`_kr_past_chunk`)으로 다시 받으면 그 칸이 토스와 칸마다 같았다(11-06 삼성).
    그래서 통합 거래가 끝난 뒤 한 바퀴(`DWMY_AT_MIN`)에 종목마다 한 번(120개 = 두 시간) 받는다.
    받은 범위 안에 다섯 분이 다 든 5분 칸만 덮는다 — 맨 앞 조각 칸으로 멀쩡한 봉을 덮지 않게(`_keep_covered_slots` 와 같은 뜻).
    """
    end = "%02d%02d00" % (MINUTE_DAY_END // 60, MINUTE_DAY_END % 60)
    rows = [b for b in _kr_past_chunk(cfg, code, day, end) if b["ts"][:8] == day]
    if not rows:
        return 0
    first = min(int(b["ts"][8:10]) * 60 + int(b["ts"][10:12]) for b in rows)
    bars = [b for b in aggregate_minutes(rows, 5)
            if int(b["ts"][8:10]) * 60 + int(b["ts"][10:12]) >= first]
    save_candles(code, "1m", aggregate_minutes(rows, 1))   # 1분도 같은 두 시간을 덮는다 — 5분과 안 갈리게(2026-11-11)
    return save_candles(code, "5m", bars)


def start_dwmy_prefill(cfg):
    """일·주·월·년봉을 거래일마다 한 번(`DWMY_AT_MIN`) 한 바퀴 받는다.

    **쓰는 서버에서만 돈다.** 읽기 전용 서버가 받아 봐야 저장을 못 한다.
    """
    if not cfg:
        return False
    if not marketdb.writable():
        return False

    def loop():
        time.sleep(PREFILL_START_SEC)
        while True:
            try:
                now = datetime.now(KST)
                if now.hour * 60 + now.minute >= DWMY_AT_MIN:
                    tail_day = _dwmy_slot("T", now)
                    for code in _ui_order(_prefill_codes()):     # 저녁 마지막 칸 다시 받기(`_kr_evening_tail`)
                        if not _is_kr_code(code) or _meta_get("pfT:%s" % code) == tail_day:
                            continue
                        try:
                            _kr_evening_tail(cfg, code, tail_day)
                        except Exception:
                            pass   # 한 종목이 실패해도 나머지는 간다
                        _meta_set("pfT:%s" % code, tail_day)
                        time.sleep((PREFILL_BUSY_REST_SEC if _ui_busy() else DWMY_REST_SEC) * fill_factor())
                    # 화면이 본 종목부터 (2026-10-12 · 설계서 3번) — 화면이 없으면 지금처럼 종목코드 순
                    for code in _ui_order(_dwmy_codes()):
                        got = False
                        for period in DWMY_PERIODS:
                            slot = _dwmy_slot(period, now)
                            key = "pf%s:%s" % (period, code)
                            # 그 구간을 이미 받았으면 건너뛴다
                            if _meta_get(key) == slot:
                                continue
                            try:
                                get_chart(cfg, code, period, DWMY_WANT)
                            except Exception:
                                pass   # 한 종목이 실패해도 나머지는 간다
                            # **실패해도 적는다** — 안 적으면 그 종목만
                            # 바퀴마다 다시 부른다 (`prefill-5m` 과 같다)
                            _meta_set(key, slot)
                            got = True
                        if got:
                            # 받은 종목 뒤에만 쉰다. 건너뛴 종목까지 쉬면
                            # **받을 것이 없는 날에도 29분을 선다.**
                            time.sleep((PREFILL_BUSY_REST_SEC if _ui_busy()
                                        else DWMY_REST_SEC) * fill_factor())
            except Exception:
                pass
            time.sleep(DWMY_CHECK_SEC)

    threading.Thread(target=loop, daemon=True, name=DWMY_THREAD_NAME).start()
    return True


def start_prefill(cfg):
    """뒤에서 5분봉을 미리 채운다. 키가 없으면 아무것도 하지 않는다."""
    if not cfg:
        return False
    # **읽기 전용 서버는 아예 안 받는다** (2026-10-02). 받아도 저장을 못 하니
    # KIS 만 쓰고 버리는 꼴이다 — 순수 낭비다.
    #
    # 세션 서버 다섯은 `--slow` 라 여기까지 오지도 않는다. **걸리는 것은 8764**
    # 하나인데, 그 하나만으로도 348종목이 헛돈다. 그리고 `--slow` 를 떼는 날
    # 나머지도 같은 자리에 선다 — **깃발은 플래그와 무관하게 막는다.**
    if not marketdb.writable():
        return False

    def loop():
        time.sleep(PREFILL_START_SEC)
        while True:
            try:
                want = _last_closed_5m_slot()
                # (가) 하나씩 뽑아 받는다. **구간이 바뀌면 그 자리에서 새 구간으로** —
                # 남은 3순위는 새 구간의 순서 뒤에 다시 선다
                while _last_closed_5m_slot() == want and _prefill_one(cfg, want):
                    pass
            except Exception:
                pass
            # (나) 30분이 아니라 새 구간이 닫혔나만 본다 — KIS 는 안 부른다
            time.sleep(PREFILL_SLOT_POLL_SEC)

    threading.Thread(target=loop, daemon=True, name="prefill-5m").start()
    return True


def _today_kst():
    """오늘 날짜(한국) YYYYMMDD.

    get_chart 안에 `import datetime`(모듈)이 있어서 그 안에서는 전역의
    `from datetime import datetime` 이 가려진다. 날짜 만드는 곳을 하나로
    모아 그 함정을 피한다 (2026-09-17 에 걸렸다).
    """
    return datetime.now(KST).strftime("%Y%m%d")


# ── 분봉은 「오늘」 이 아니라 「마지막 거래일」 로 센다 (2026-10-03 지시 ④) ──
#
# 주말에 5분봉을 열 때마다 하루치를 통째로 다시 받아 **15~31초**가 걸렸다(개발 실측 ·
# qa 4초 · KIS 25~37건). 원인은 셋이 같은 뿌리다 — **「오늘 날짜 · 벽시계」 로 셌다.**
#   ㉠ dayfill 키가 토요일 날짜라 「오늘치 안 받음」 → 하루치 다시
#   ㉡ 그때의 `_minutes_have_today`(2026-10-06 에 `_minutes_done` 으로 바뀜)가 토요일 칸을 찾아 빈 집합 → 금요일 칸을 전부 다시
#   ㉢ 2번(마지막 봉이 1시간 넘게 오래됨)이 주말 · 장 뒤엔 늘 참
# 그리고 받아도 새 봉이 없다 — KIS 는 그날(거래일) 분봉만 준다.
#
# **휴일은 못 가린다** — 달력이 없다(`_last_closed_5m_slot` 도 같다). 휴일엔 그날
# 하루치를 한 번 헛받는다 — 전과 같은 한계다.
def _minutes_trade_day(now=None):
    """분봉이 속한 거래일 YYYYMMDD — 주말은 금요일, 평일 08:00 전은 앞 평일."""
    now = now or datetime.now(KST)
    d = now
    if d.weekday() < 5 and d.hour * 60 + d.minute < MINUTE_DAY_START:
        d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d.strftime("%Y%m%d")


def _minutes_live(now=None):
    """지금 새 분봉이 생길 수 있나 — 평일 08:00 부터 통합 거래가 끝난 뒤 10분(`DWMY_AT_MIN`)까지.

    끝을 20:00 이 아니라 20:10 으로 두는 것은 마지막 봉이 KIS 에 들어가는 여유다
    (`DWMY_AT_MIN` 주석 — 아직 못 쟀다). 같은 값을 또 적지 않고 그것을 쓴다.
    """
    now = now or datetime.now(KST)
    if now.weekday() >= 5:
        return False
    cur = now.hour * 60 + now.minute
    return MINUTE_DAY_START <= cur < DWMY_AT_MIN


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
    if _meta_get("dayfill:%s:%s" % (code, period)) != _minutes_trade_day():
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
    # **새 봉이 생길 수 없는 때(주말 · 장 앞뒤)는 2번을 안 본다** (④ · 위 주석 ㉢).
    # 그때 「마지막 봉이 오래됨」 은 늘 참인데 받아도 새 봉이 없다.
    if not _minutes_live():
        return False
    try:
        ts = rows[-1]["ts"]                      # YYYYMMDDHHMM
        last = datetime(int(ts[0:4]), int(ts[4:6]), int(ts[6:8]),
                        int(ts[8:10]), int(ts[10:12]), tzinfo=KST)
        gap = (datetime.now(KST) - last).total_seconds() / 60
    except Exception:
        return True                              # 읽을 수 없으면 다시 받는 쪽으로
    return gap > MINUTE_REFILL_GAP


CARRY_CLOSE_FROM, CARRY_CLOSE_TO = "1520", "1535"   # flatten_carried — 이 시각에 시작한 되풀이는 옮겨 실린 것
CARRY_MIN_RUN = 5                                  # flatten_carried — 이 칸 수 이상 이어진 되풀이도(토스로 맞춘 것은 11-06 다섯 칸뿐 · qa 11-09)


def flatten_carried(rows):
    """분봉에서 **바로 앞 봉과 시가 · 고가 · 저가 · 종가 · 거래량이 다 같은 봉**을 거래 없는 납작봉으로 바꾼다 — 화면에 낼 때만 (2026-11-07).

    재권님 — 「vwap 값 … 토스증권에서 보는값이랑 많이 다른거같아」 → 토스 그림 대조 → 「올리고 원인찾아서 개선해줘」 →
    「그게 데이터상 맞으면 고쳐」. KIS 는 체결이 없는 동안 마지막 체결을 「지금 분」 줄로 옮겨 싣는다(pin_carried_trade 머리) —
    그 줄이 칸마다 남아 **같은 봉이 거래량째 되풀이**됐다. 개발 DB 로 잰 것(10-20 ~ 11-07 · 5분봉):

        15:25 칸   거래량이 실린 375 칸 중 322 칸이 15:20 칸과 다섯 값이 같음 — 15:20~15:30 은 KRX 종가 단일가 · 넥스트레이드 쉼이라
                  그 칸에 체결이 날 수 없다
        11-06     09:05~09:30 코스피 거래 0 구간(카카오 · LG전자 0주 · 코스닥은 정상 · 토스 삼성도 빈칸)에 장중 1분봉을 받던 큰 종목
                  21 개만 09:10~09:25 네 칸이 09:05 봉 복사(삼성 200,642주 × 4)

    **되풀이의 첫 칸**(09:05 · 15:20)도 앞 분 체결을 옮겨 실은 것이라 앞 봉에 합치고 납작하게 한다(토스 그림 대조 · 아래 줄).
    차트 캔들 · 거래량 막대 · VWAP 이 함께 틀렸다. **저장은 그대로 두고** 응답에서만 바꾼다(drop_before_first_trade 와 같은 자리) —
    지난 봉도 내줄 때 고쳐진다. 거래량 0 봉끼리는 원래 같으니 거래량이 있는 봉만 본다. 다섯 값이 다 같은 진짜 체결은 사실상 없다고 본다.
    **일봉 거래량과 5분봉 합은 이것과 따로 크게 갈린다**(삼성 하루 900만주 안팎 · 복사 없는 날도) — 그 대조로는 이 고침을 가르지 못한다.

    **두 갈래에만 건다** (같은 날 qa 가 돌려보냄 · 개발 DB 10-20 ~ 11-07 5분봉 되풀이 묶음 1,355 를 갈라 잼).
    처음 판은 되풀이면 다 걸어, 거래 드문 종목의 장 후 둘 · 세 칸(1~10주 · 995 묶음)까지 첫 칸 거래를 앞 봉에 합쳤다
    (000080 10-21 16:00 종가 15,790 → 15,800). 그 칸이 옮겨 실린 것인지는 토스 대조가 없다 — 대조한 것은 아래 둘뿐이다.

        CARRY_CLOSE_FROM ~ TO   15:20 ~ 15:35 에서 시작한 되풀이 — 종가 단일가 · 넥스트레이드 쉼이라 체결이 날 수 없다(324 묶음)
        CARRY_MIN_RUN 칸 이상    다섯 칸 이상 이어진 되풀이 — 11-06 거래 정지 구간(09:05 ~ 09:25 · 다섯 칸 · 21 종목) 같은 것(다섯 칸 이상 26 묶음 · 11-09 개발 DB 사본 다시 셈 — 네 칸 14 묶음은 뺌)

    그 밖(둘 · 세 칸)은 받은 그대로 둔다.
    """
    out = [dict(r) for r in rows]
    sig = lambda r: (r.get("ts", "")[:8], r.get("open"), r.get("high"), r.get("low"), r.get("close"), r.get("volume"))
    i = 0
    while i < len(out):
        j = i
        while j + 1 < len(out) and (out[j + 1].get("volume") or 0) > 0 and sig(out[j + 1]) == sig(out[i]):
            j += 1
        hm = out[i].get("ts", "")[8:12]
        at_close = CARRY_CLOSE_FROM <= hm <= CARRY_CLOSE_TO
        if j > i and (out[i].get("volume") or 0) > 0 and (at_close or j - i + 1 >= CARRY_MIN_RUN):
            # 긴 되풀이(09:05 ~)의 **첫 칸도** 옮겨 실린 것이다 — 앞 분(09:04)의 체결이라 앞 봉에 합친다.
            # 토스 그림(11-06)에서 09:05 칸이 비어 있고 09:00 봉 고가가 그 칸 고가(181,500)와 맞았다.
            # **15:20 되풀이는 합치지 않고 뺀다** (2026-11-09 토스 1분봉 대조 · 재권님 「토스증권이랑 비교해서 거기랑 맞춰줘」) —
            # 합치면 15:15 칸이 토스보다 그 칸 거래량만큼 많았다(삼성 11-05 +64,173 · 11-06 +206,823). 안 합치면 15:15 칸이 토스와 같다
            p = out[i - 1] if i > 0 and not at_close else None
            if p is not None and p.get("ts", "")[:8] == out[i].get("ts", "")[:8] and (p.get("volume") or 0) > 0:
                f = out[i]
                p["high"] = max(p["high"], f["high"])
                p["low"] = min(p["low"], f["low"])
                p["close"] = f["close"]
                p["volume"] = p["volume"] + f["volume"]
            for k in range(i, j + 1):
                c = out[k].get("close")
                out[k].update(open=c, high=c, low=c, volume=0)
            i = j + 1
        else:
            i += 1
    return out


def drop_before_first_trade(rows):
    """분봉에서 **그날 첫 체결 전 · 마지막 체결 뒤의 거래량 0 봉**을 뺀다 — 화면에 낼 때만 (2026-10-03 지시).

    재권님이 069500(KODEX 200) 아침 08:00~08:55 에 납작봉이 있는 것을 물으셨다.

        ETF 는 넥스트레이드에 없어 **09:00 전 거래가 없다**
        통합(UN)은 그 빈 분을 **전일 종가로 채워** 30행을 준다 (069500 = 111,520 = 10-01 종가)
        KRX(J)는 09:00 전이 없어 전날 저녁 행을 준다 — 069500 은 그것도 거래량 0
        `fetch_minutes_from_kis` 는 **둘 다 0 이면 먼저 받은 것을 쓴다** — 그래서 저장된다

    **저장은 그대로 둔다.** 그때는 빼면 「봉이 있나」 로 받았나를 가려 그 칸을 바퀴마다 다시 받았다
    (2026-10-06 부터는 `_minutes_done` 이 「끝난 뒤에 받았나」 로 가린다). 그래서 응답에서만 뺀다.

    **마지막 체결 뒤의 거래량 0 봉도 뺀다** (같은 날 · 재권님 「빼」). 069500 은 저녁
    16:00~19:55 에도 같은 이유로 납작봉 쉰 개 남짓이 남았다 — ETF 는 그 시간 거래가 없다.

    **첫 체결과 마지막 체결 사이의 거래량 0 봉은 둔다** — 마감 동시호가 뒤 15:35 처럼 거래가
    없는 진짜 구간이고 값은 마지막 체결가다. 하루 내내 체결이 없으면 그날 봉이 다 빠진다 —
    그린 것이 없는 것이 맞다. 장중에는 체결이 아직 없는 지금 칸이 잠깐 빠졌다가 체결이 오면 생긴다.
    """
    # **하루 끝(20:00) 줄은 마감 체결을 다시 붙인 것일 수 있다** (2026-10-03 실측).
    # 넥스트레이드에 없는 종목은 KIS 가 20:00 줄에 15:30 마감 체결을 **값 · 거래량 그대로**
    # 다시 준다 — 069500 20:00 = 112,060 · 44,456 = 15:30 · 229200 20:00 = 15,180 · 108,061 = 15:30.
    # 그 줄 때문에 거래량이 두 번 세어지고 「마지막 체결」 이 20:00 이 되어 저녁 납작봉이 안 빠졌다.
    # **바로 앞 봉이 거래량 0 인데 끝 줄만 거래량이 있으면** 다시 붙은 것으로 보고 뺀다.
    # 넥스트레이드에서 저녁까지 거래가 있는 종목은 바로 앞 봉에 거래량이 있어 그대로 둔다.
    end = "%02d%02d" % (MINUTE_DAY_END // 60, MINUTE_DAY_END % 60)
    dup = set()
    for i, r in enumerate(rows):
        if (r["ts"][8:12] == end and (r.get("volume") or 0) and i > 0
                and rows[i - 1]["ts"][:8] == r["ts"][:8] and not (rows[i - 1].get("volume") or 0)):
            dup.add(i)
    rows = [r for i, r in enumerate(rows) if i not in dup]

    first, last = {}, {}
    for i, r in enumerate(rows):
        if r.get("volume") or 0:
            day = r["ts"][:8]
            first.setdefault(day, i)
            last[day] = i
    return [r for i, r in enumerate(rows)
            if r["ts"][:8] in first and first[r["ts"][:8]] <= i <= last[r["ts"][:8]]]


def aggregate_minutes(bars, minutes, stored=None):
    """1분봉을 N분봉으로 묶는다 (KIS 는 5분봉을 직접 주지 않는다).

    **거래량 0 줄은 시가 · 고가 · 저가 · 종가에 안 섞는다** (2026-11-05 재권님 「응」 · 작업우선순위 배분).
    15:30~15:39 에 KIS J 는 마감 체결을 「지금 분」 줄로 옮겨 싣고 1530 줄을 거래량 0 · 체결 아닌 값으로 준다
    (pin_carried_trade 머리 10-06 관찰) — 그 줄이 15:30 칸의 첫 줄이라 시가가 되고 고가에도 섞였다(10-07 삼성전자 269,500 ·
    종가 · 거래량은 맞았다). 「없음」 을 값으로 쓰지 않는다. **칸 안에 거래가 하나도 없을 때만** 마지막 줄 종가로 납작봉을 둔다
    — 마감 동시호가 뒤 15:35 처럼 거래가 없는 진짜 구간(drop_before_first_trade 가 처음 · 마지막 체결 밖을 뺀다).

    **거래 없는 칸의 값은 바로 앞 체결 종가다** (같은 날 qa 덧 · 재권님 「응 고쳐」). 그 칸 줄도 거래량 0 이라 그 종가는 체결이 아니다 —
    개발 DB 1분봉 거래 0 칸 83 중 53 이 마지막 체결 종가와 달랐다(069500 10-02 15:35~20:00 = 111,520 전일 종가 ↔ 마감 체결 112,060).
    같은 날 앞 칸에 체결이 있으면 그 종가를 잇는다. 이번에 받은 묶음 첫 칸이면 stored({ts: 저장된 봉})에서 그날 그 앞의 마지막 체결 칸을 찾는다.
    그날 첫 칸부터 체결이 없으면(장 전 · 하루 내내 거래 없음) 이을 값이 없어 그 줄 종가 그대로 둔다."""
    groups = {}
    for b in sorted(bars, key=lambda x: x["ts"]):
        hhmm = b["ts"][8:12]
        slot = (int(hhmm[:2]) * 60 + int(hhmm[2:])) // minutes * minutes
        groups.setdefault(b["ts"][:8] + "%02d%02d" % (slot // 60, slot % 60), []).append(b)
    out, carry = [], {}
    for key in sorted(groups):
        rows = groups[key]
        day = key[:8]
        traded = [r for r in rows if (r["volume"] or 0) > 0]
        if traded:
            out.append({"ts": key, "open": traded[0]["open"], "high": max(r["high"] for r in traded),
                        "low": min(r["low"] for r in traded), "close": traded[-1]["close"],
                        "volume": sum(r["volume"] for r in traded)})
            carry[day] = traded[-1]["close"]
        else:
            if day not in carry and stored:
                prev = [t for t, b in stored.items() if t[:8] == day and t < key and (b.get("volume") or 0) > 0]
                if prev:
                    carry[day] = stored[max(prev)]["close"]
            c = carry.get(day, rows[-1]["close"])
            out.append({"ts": key, "open": c, "high": c, "low": c, "close": c, "volume": 0})
    return out


def pin_carried_trade(raw, bars, stored, minutes):
    """「지금 줄」 로 옮겨 실린 마지막 체결을 **원래 칸에 되돌린다** (2026-10-06 지시 — 「응 고쳐줘」).

    **KIS 1분봉은 새 체결이 없는 동안 마지막 체결을 「지금 분」 줄로 옮겨 싣고, 원래 줄은 0 으로 준다.**
    2026-10-06 마감봉 관찰(005930 · 069500 · 1분마다 원본 J · UN):

        15:31 에 물으면   1530 줄 0 · 1531 줄 1,427,002   (마감 체결)
        15:36 에 물으면   1530~1535 줄 0 · 1536 줄 1,427,002
        15:40 부터        UN 은 넥스트레이드 체결이 오자 1530 줄로 되돌림 · J 와 ETF(넥스트레이드 없음)는 계속 따라감
        15:29 에 물으면   1529 줄 173,403 — 마감 동시호가 전 마지막 체결이 같은 꼴로 따라옴

    그대로 저장하면 5분봉 막대가 15:30 → 15:35 → 15:40 칸으로 옮겨 다니고 원래 칸은 납작해진다
    (10-02 「15:35 봉에 있다가 15:30 봉으로」 · ETF 마감 직전 납작봉이 이 모양).

    **판정 둘.**
      ① **이미 지난 칸의 거래량은 줄지 않는다.** 저장된 것보다 작게 오면 저장된 칸을 그대로 둔다.
         단 **그만큼이 다른 지난 칸에 늘었으면** KIS 가 제자리로 옮긴 것이라 KIS 를 따른다(두 번 세지 않게).
         옮겨 실린 체결이 다음 체결(마감 체결 등)에 밀려 「지금 줄」 에서도 사라지면, 원래 칸만 줄고
         어디에도 안 남는다 — 15:29 의 173,403 이 15:30 에 그렇게 사라졌다. ①이 그것을 막는다.
      ② **「지금 줄」 거래량이 ①에서 막은 양과 꼭 같으면** 옮겨 실린 것이다 — 지금 칸에서 뺀다.
         「지금 줄」 = 받은 1분봉의 마지막 줄 · 거래량 있음 · 시가=고가=저가=종가(한 체결).
         원래 칸이 이번 구간(30분) **밖**이면 그 칸은 안 덮였으므로, 구간 안 앞 칸이 전부 0 이고
         구간 앞 마지막 저장 칸이 **그 거래량 · 종가 그대로**일 때 뺀다(저녁에 ETF 가 15:30 체결을 끌고 다님).
    진짜 새 체결이면 앞 칸이 줄지 않아 ②에 안 걸린다. 같은 칸 안에서 옮긴 것은 합이 같아 손댈 것이 없다.

    **한계** — 원래 분에 한 번도 안 받았으면(그 시각에 아무도 안 열었다) 저장된 칸이 없어 못 되돌린다.
    그때는 처음 받은 칸에 머문다. 하루치를 다시 받으면 KIS 가 지난 시각은 제자리로 주므로 바로잡힌다.
    ①은 KIS 가 지난 칸 거래량을 **정말로 낮춰 고친** 경우에도 옛 값을 지킨다 — 관찰에서 그런 일은 없었다.

    raw     이번에 받은 1분봉(시각순)
    bars    raw 를 `minutes` 분으로 묶은 것 — 저장할 것
    stored  {ts: 저장된 봉} — 같은 날 같은 주기
    """
    if not raw or not bars or not stored:
        return bars
    last = max(raw, key=lambda b: b["ts"])
    hhmm = last["ts"][8:12]
    slot = (int(hhmm[:2]) * 60 + int(hhmm[2:])) // minutes * minutes
    cur = last["ts"][:8] + "%02d%02d" % (slot // 60, slot % 60)
    by_ts = {b["ts"]: b for b in bars}
    keys = ("ts", "open", "high", "low", "close", "volume")

    # ① 지난 칸이 준 양. **다른 지난 칸에 그만큼 늘었으면 KIS 가 제자리로 옮긴 것이다** — 그때는 KIS 를 믿는다.
    #    `UN` 은 넥스트레이드 체결이 오면 마감 체결을 1530 으로 되돌리고, 20:00 뒤 하루치는 지난 시각을
    #    제자리로 준다. 그때도 옛 칸을 지키면 두 번 세어진다.
    past = [t for t in by_ts if t < cur and t[:8] == cur[:8]]
    gained = [(by_ts[t].get("volume") or 0) - ((stored.get(t) or {}).get("volume") or 0) for t in past]
    held = set()
    for ts in past:
        old = stored.get(ts)
        if not old:
            continue
        lost = (old.get("volume") or 0) - (by_ts[ts].get("volume") or 0)
        if lost > 0 and lost not in gained:
            by_ts[ts] = {k: old[k] for k in keys}
            held.add(lost)

    v = last.get("volume") or 0                    # ② 지금 줄이 옮겨 실린 것인가
    one = last["open"] == last["high"] == last["low"] == last["close"]
    carried = False
    if v and one and cur in by_ts:
        if v in held:
            carried = True
        elif all(not (by_ts[t].get("volume") or 0) for t in by_ts if t < cur):
            first = min(by_ts)
            before = [t for t in stored
                      if t[:8] == cur[:8] and t < first and (stored[t].get("volume") or 0)]
            if before:
                o = stored[max(before)]
                carried = (o.get("volume") or 0) == v and o["close"] == last["close"]
    if carried:
        c = dict(by_ts[cur])
        c["volume"] = max(0, (c.get("volume") or 0) - v)
        if not c["volume"]:
            c["open"] = c["high"] = c["low"] = c["close"]
        by_ts[cur] = c
    return [by_ts[k] for k in sorted(by_ts)]


def _stored_day(code, period, day):
    """그날 저장된 봉 {ts: 봉}. 못 읽으면 빈 것 — 그때는 되돌리지 않는다."""
    try:
        with _db_lock, db_conn() as conn:
            rows = conn.execute(
                "SELECT ts, open, high, low, close, volume FROM candles"
                " WHERE code = ? AND period = ? AND ts LIKE ?",
                (code, period, day + "%")).fetchall()
    except Exception:
        return {}
    return {r["ts"]: dict(r) for r in rows}


# ── 한 구간에 봉이 여럿 생기던 것 (2026-09-29 · 재권님이 년봉에서 찾으셨다) ──
#
# **KIS 는 「진행 중인 구간」 의 봉에 마지막 거래일을 ts 로 준다.**
#
#     년봉 2026    20260911 · 20260914 · 20260917 · 20260918 · 20260929
#                  **시·고·저가 다섯 줄 다 같고 종가만 다르다**
#     월봉 202609   같은 모양
#
# 부를 때마다 그 날짜가 달라져서 PK(code, period, ts)가 **새 줄**이 된다.
# 그래서 한 해에 봉이 다섯 개씩 생겼다. 재권님 말씀 — 「년봉이 이상한거같은데」.
#
# **주봉·일봉은 안전하다.** 주봉은 그 주 **월요일**(구간 시작)을, 일봉은
# 그날을 준다 — 구간이 정해지면 안 바뀐다. 실측으로 겹침 0 이었다.
# 그래서 **그 둘은 건드리지 않는다.**
#
# **ts 를 구간 끝으로 바꾸지 않는다.** 지난 해 봉은 ts 가 실제 마지막
# 거래일(20251230)이라, 20251231 로 정규화하면 **기존 줄과 키가 어긋나
# 오히려 중복이 는다.** 넣기 전에 같은 구간을 지우는 쪽이 안전하다.
SPAN_CUT = {"Y": 4, "M": 6}       # ts 앞 몇 글자가 한 구간인가


def save_candles(code, period, candles):
    """받은 봉을 DB 에 넣고 **넣으려 한 개수**를 돌려준다. 못 쓰면 `0`.

    ⚠️ **`0` 은 「쓰지 못했다」 또는 「넣을 것이 없었다」 이지 「이미 다 있었다」 가
    아니다.** `ON CONFLICT … DO UPDATE` 라 들어간 줄 수를 세지 않는다.

    **여기서 막는 이유** — 이 함수를 부르는 네 자리 중 **셋에 `try` 가 없다**
    (`fetch_index_minutes` · `fetch_index_candles` · `get_chart`). 한 곳에서
    막으면 넷이 다 안전하다. **깃발(`writable`)과 실패(예외)를 둘 다 본다** —
    깃발이 켜진 서버에서도 디스크 · 권한 · 잠금으로 실패할 수 있다.
    """
    # **값이 0 인 봉은 넣지 않는다** — 없는 종목 코드에 KIS 가 0 봉(거래량 -9223372036854775808)을 준다(2026-11-05 999999 실측).
    # 가격이 0 인 봉은 어느 종목에도 없다
    candles = [c for c in (candles or []) if (c.get("close") or 0) > 0]
    if not candles:
        return 0
    if not marketdb.writable():
        return 0
    cut = SPAN_CUT.get(period)
    try:
        return _save_candles_write(code, period, candles, cut)
    except sqlite3.Error as e:
        print("[db] 캔들 저장 실패 %s %s — %s" % (code, period, safe_message(e, 120)))
        return 0


def _save_candles_write(code, period, candles, cut):
    with _db_lock, db_conn() as conn:
        if cut:
            # 넣을 봉이 그 구간의 최신이다. 옛 줄을 먼저 치운다.
            #
            # ⚠️ **이 저장소에서 캔들을 지우는 유일한 자리다.** 2026-09-29 에
            # 「지우는 코드가 없다」 를 전수로 확인하고 적어 둔 터라, 여기가
            # 생겼다는 것을 함께 적는다. 지우는 범위는 **같은 종목 · 같은 주기 ·
            # 같은 구간**뿐이고, 곧바로 그 구간의 새 줄이 들어간다.
            for span in {c["ts"][:cut] for c in candles}:
                conn.execute(
                    "DELETE FROM candles WHERE code = ? AND period = ? "
                    "AND substr(ts, 1, ?) = ?",
                    (code, period, cut, span))
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


VOL_PREV_FROM, VOL_PREV_TO = "0900", "1530"   # 정규장 5분봉(시작 시각) — 15:30 봉이 종가 단일가다. 시세의 누적 거래량(정규장)과 같은 범위


def vol_prev_day(code, today):
    """전날(오늘 앞의 마지막 거래일) 정규장 5분봉 거래량 — 「전날 같은 시각 대비 거래량 %」 의 분모 재료 (2026-11-10 재권님 「나」 · 「가」).

    **DB 에 쌓인 봉만 읽는다 — KIS 를 새로 부르지 않는다.** 그 종목의 전날 5분봉이 없으면 None(「못 받음」 — 0 이 아니다).
    화면이 지금 시각까지 더해 같은 시각 누적을 센다 — 서버는 하루 한 벌만 준다(화면이 다시 묻는 주기가 없다)."""
    with _db_lock, db_conn() as conn:
        day = conn.execute(
            "SELECT MAX(substr(ts, 1, 8)) FROM candles WHERE code = ? AND period = '5m' AND substr(ts, 1, 8) < ?",
            (code, today)).fetchone()[0]
        if not day:
            return None
        rows = conn.execute(
            """SELECT substr(ts, 9, 4) AS hm, volume FROM candles
                 WHERE code = ? AND period = '5m' AND substr(ts, 1, 8) = ? AND substr(ts, 9, 4) BETWEEN ? AND ?
                 ORDER BY ts""", (code, day, VOL_PREV_FROM, VOL_PREV_TO)).fetchall()
    bars = [[r["hm"], r["volume"]] for r in rows if r["volume"] is not None]
    if not bars:
        return None
    return {"day": day, "from": VOL_PREV_FROM, "to": VOL_PREV_TO, "bars": bars, "total": sum(v for _, v in bars)}


def vol_same_time(code, now=None):
    """오늘 · 전날 정규장 거래량을 **같은 시각까지** 같은 자리(DB 5분봉 09:00~15:30)에서 센다 — 「전날 같은 시각 대비 %」 (2026-11-10).

    분자 · 분모를 같은 봉에서 센다 — 처음 판은 분자를 머리줄 누적 거래량으로 셌는데 그 값이 15:30 에 정규장에서 통합(넥스트레이드 포함)으로 바뀌고
    장 뒤 거래가 분자에만 쌓여 마감 뒤 79% 가 122% 로 뛰었다(qa 15:45 돌려보냄). 오늘 봉은 **다 끝난 봉만** — 지금 도는 봉은 덜 찼다.
    전날 봉이 없으면 None(「못 받음」) · 오늘 끝난 봉이 아직 없으면 today · upto 가 None(장 전 · 그 종목 봉이 아직 안 쌓임)."""
    now = now or datetime.now(KST)
    today = now.strftime("%Y%m%d")
    prev = vol_prev_day(code, today)
    if prev is None:
        return None
    now_min = now.hour * 60 + now.minute
    # 봉 끝이 지났어도 그 뒤에 다시 받지 않았으면 덜 찬 값이다 — 「지금 칸」 을 마지막으로 받은 분까지만 센다(_minutes_fresh_upto).
    # 그 기록이 없으면(오늘 아직 안 받음 · 기록 전 서버) 끝난 봉도 없는 것으로 본다 — 덜 찬 값을 내느니 「아직」 이다
    fresh = _minutes_fresh_upto(code)
    if today != _minutes_trade_day() or fresh is None:
        now_min = -1
    else:
        now_min = min(now_min, fresh)
    with _db_lock, db_conn() as conn:
        rows = conn.execute(
            """SELECT substr(ts, 9, 4) AS hm, volume FROM candles
                 WHERE code = ? AND period = '5m' AND substr(ts, 1, 8) = ? AND substr(ts, 9, 4) BETWEEN ? AND ?
                 ORDER BY ts""", (code, today, VOL_PREV_FROM, VOL_PREV_TO)).fetchall()
    done = [(r["hm"], r["volume"]) for r in rows
            if r["volume"] is not None and int(r["hm"][:2]) * 60 + int(r["hm"][2:]) + 5 <= now_min]
    upto = done[-1][0] if done else None
    return {"day": today, "prevDay": prev["day"], "from": VOL_PREV_FROM, "to": VOL_PREV_TO, "upto": upto,
            "today": sum(v for _, v in done) if done else None,
            "prev": sum(v for hm, v in prev["bars"] if hm <= upto) if upto else None,
            "prevTotal": prev["total"]}


def _view_limit(code, period, limit):
    """`view_days` 가 있는 기간이면 최근 그 날짜 수만큼의 봉 수로 limit 를 넓힌다. 줄이지는 않는다.

    **5분봉에만 탄다** — 일·주·월·년봉은 밤 한 바퀴가 limit 400 으로 부르고 그 limit 이
    과거를 거슬러 받는 양을 정하므로(`fetch_bars_back`) 건드리면 안 된다 (개발3 · 2026-10-02)."""
    days = PERIODS[period].get("view_days")
    if not days:
        return limit
    with _db_lock, db_conn() as conn:
        n = conn.execute(
            """SELECT COUNT(*) FROM candles WHERE code = ? AND period = ? AND substr(ts, 1, 8) >=
                 (SELECT MIN(d) FROM (SELECT DISTINCT substr(ts, 1, 8) AS d FROM candles
                                       WHERE code = ? AND period = ? ORDER BY d DESC LIMIT ?))""",
            (code, period, code, period, days),
        ).fetchone()[0]
    return max(limit, n or 0)


def _last_close_ts(now=None):
    """가장 최근 마감 시각(초) — 거래일의 `DWMY_AT_MIN`(통합 거래가 끝난 뒤 10분).

    밤 한 바퀴(`start_dwmy_prefill`)와 **같은 시각**을 쓴다 — 값은 `DWMY_AT_MIN` 한 곳이다.
    오늘이 거래일이고 그 시각이 지났으면 오늘, 아니면 앞 거래일. 토·일은 건너뛴다.
    **휴일은 못 가른다** — 달력이 없다(`_dwmy_slot` 과 같다). 휴일에는 한 번 더 받을 뿐이다."""
    now = now or datetime.now(KST)
    d = now
    if not (d.weekday() < 5 and d.hour * 60 + d.minute >= DWMY_AT_MIN):
        d = d - timedelta(days=1)
        while d.weekday() >= 5:
            d = d - timedelta(days=1)
    mark = d.replace(hour=DWMY_AT_MIN // 60, minute=DWMY_AT_MIN % 60, second=0, microsecond=0)
    return mark.timestamp()


#: 같은 (종목, 주기) 요청이 겹칠 때 앞 요청을 기다리는 최대 초 — 넘으면 기다리지 않고 지금처럼 받는다
CHART_WAIT_SEC = 10
_chart_locks = {}          # (종목, 주기) → 자물쇠. 지우지 않는다 — 많아야 종목 수 × 주기 수다
_chart_locks_guard = threading.Lock()


def get_chart(cfg, code, period, limit, gap_check=True):
    """`_get_chart_one` 을 **같은 (종목, 주기)마다 한 번에 하나씩** 부른다 (2026-10-06 재권님 「풀리면 해줘」).

    앞 요청이 KIS 에서 하루치(30분 칸 여러 번)를 받는 2~3초 사이에 같은 요청이 또 오면, 아직 `sync`
    시각이 안 적혀 있어 모두 「오래됨」 으로 보고 **각자 하루치를 받았다.** 17:48 에 화면이 086520
    5분봉을 15초에 13번 불러 그 한 분에 분봉 호출이 499건, 예산이 112% 로 튀었다(넘침 0).
    뒤 요청은 앞 것이 끝나길 기다렸다가 들어가므로 `sync` 가 새것이라 KIS 를 안 부르고 DB 를 읽는다.

    **기다림에 상한이 있다**(`CHART_WAIT_SEC` · 창구 검수) — 앞 요청이 KIS 에서 멈추면 뒤가 전부
    매달리므로, 넘으면 기다리지 않고 지금처럼 받는다. 다른 종목 · 다른 주기는 서로 안 기다린다.
    """
    key = (code, period)
    with _chart_locks_guard:
        lk = _chart_locks.get(key)
        if lk is None:
            lk = _chart_locks[key] = threading.Lock()
    got = lk.acquire(timeout=CHART_WAIT_SEC)
    try:
        if us_universe.is_us(code):                 # 미국 티커 — 국내 몸통을 안 탄다 (2026-10-07 나스닥100)
            return _get_chart_us(cfg, code, period, limit)
        return _get_chart_one(cfg, code, period, limit, gap_check)
    finally:
        if got:
            lk.release()


def _get_chart_us(cfg, code, period, limit):
    """미국 티커의 봉 — 국내 `_get_chart_one` 과 같은 표(candles) · 같은 `sync` 시각 · 같은 `fresh_sec` 을 쓴다.

    그래서 겉 함수의 자물쇠(겹친 요청은 한 번만)가 그대로 듣는다. 받는 것은 `us_universe` 가 한다(묶음 2 ·
    2026-10-07 재권님 「응 해줘」). 1분봉은 받지 않는다. 년봉은 KIS 에 없어 월봉을 해마다 묶는다.
    처음(또는 덜 찼을 때)은 달라는 만큼 거슬러 받고, 그 뒤 「오래됨」 일 때는 최근 한 쪽만 받는다.
    """
    db_init()
    if period not in ("D", "W", "M", "Y", "5m"):
        return [], 0, "US"
    view = _view_limit(code, period, limit)
    rows = read_candles(code, period, view)
    mkey = "sync:%s:%s" % (code, period)
    bkey = "backfill:%s:%s" % (code, period)
    stale = (time.time() - float(_meta_get(mkey) or 0)) > PERIODS[period]["fresh_sec"]
    deep = period != "5m" and (not rows or (len(rows) < limit and _meta_get(bkey) != "done"))
    fetched = 0
    if deep or stale or not rows:
        try:
            if period == "5m":
                # 처음은 두 쪽(하루치) · 그 뒤 갱신은 한 쪽(120봉 = 10시간) — 장중 미리받기가 1건으로 끝난다
                bars = us_universe.us_5m(kis_get, cfg, code,
                                         us_universe.US_5M_PAGES if not rows else 1)
            else:
                n = limit if deep else (2 if period == "Y" else us_universe.DAILY_PER_CALL)
                bars = us_universe.us_bars(kis_get, cfg, code, period, n)
                got = len(bars)                 # 「다 받음」 은 거르기 전 개수로 가른다 — 거른 한 줄로 done 이 되지 않게
                # **장이 열리기 전에는 오늘 줄을 버린다** (2026-10-12 재권님 「가로」). 장 전 창(동부 07:15~)에
                # 받으면 KIS 가 아직 안 열린 오늘을 장 전 시세 한 줄로 주는데, 그것이 그날 일봉으로 굳어
                # 순위 표가 마감 종가 대신 그 값을 냈다(10-09 S&P500 503 중 502). 오늘 일봉은 장 마감 뒤
                # 바퀴(`post_round`)가 받는다. 월·년봉은 ts 가 그 봉의 마지막 날(=오늘)이라 함께 빠지고 앞서 저장한
                # 그 달 줄이 남는다. **주봉은 ts 가 그 주 시작일**이라 월요일 장 전에만 빠진다 — 화~금에는 이번 주 봉의
                # 종가가 장 전 값으로 남는다(다음 장 전 창까지). 순위 표는 일봉 · 5분봉만 읽어 주봉은 안 닿는다
                st_now, d_now, _m = us_universe.session_state()
                if st_now == "pre":
                    bars = [b for b in bars if b["ts"] < d_now]
                # 「다 받음」 은 **KIS 가 달라는 것보다 덜 줬을 때만** 적는다 (2026-10-08). 전에는 받기만 하면 적어서,
                # 장 전 창이 적게(100) 달라고 한 뒤로는 화면이 400 을 달라고 해도 더 거슬러 받지 않았다
                if deep and got < n:
                    _meta_set(bkey, "done")     # 끝까지 거슬러 받았다 — 덜 와도 KIS 가 더 안 준다
        except RuntimeError:
            bars = []
        fetched = save_candles(code, period, bars)
        _meta_set(mkey, time.time())
        if fetched:
            rows = read_candles(code, period, _view_limit(code, period, limit))
        elif not rows and bars and not marketdb.writable():
            rows = bars[-view:]                 # 읽기 전용 서버 — 저장은 못 해도 받은 것을 보여 준다
    return rows, fetched, "KIS" if fetched else "DB"


_us_members = {"at": 0.0, "set": frozenset()}


def _us_member_set():
    """미리받기 묶음(나스닥100 ∪ S&P500)을 1분 들고 있는다 — 시세를 부를 때마다 표를 읽지 않게."""
    if time.time() - _us_members["at"] > 60:
        try:
            _us_members["set"] = frozenset(us_universe.all_members())
        except Exception:
            pass                                    # 표가 아직 없다 — 옛 것을 쓴다(처음이면 빈 것 → KIS 로)
        _us_members["at"] = time.time()
    return _us_members["set"]


def _us_quotes(cfg, codes):
    """미국 티커 여럿의 시세 → (data, errors). 한 요청에 `US_QUOTES_MAX` 개까지만 받는다.

    **묶음 종목은 DB 의 5분봉으로 낸다 — KIS 를 안 부른다**(2026-10-27 재권님 「미국 정규장도 5분봉이면 될거같아 ·
    간략화」 · 「응」). 미리받기가 장외까지 5분마다 쌓으므로 값은 최대 5분 늦다. 묶음 밖 종목 · 아직 봉이 없는 종목만
    전처럼 현재가 상세를 종목마다 1건 부르고 국내와 같은 시세 캐시(`PRICE_CACHE_TTL`)를 탄다."""
    data, errors = {}, {}
    members = _us_member_set()
    for code in codes[:US_QUOTES_MAX]:
        if code in members:
            try:
                row = us_universe.us_quote(code)
            except Exception as e:
                row = None
                _us_log("%s 시세 DB 읽기 실패 (%s) — KIS 로" % (code, type(e).__name__))
            if row is not None:
                data[code] = row
                continue
        ck = "us:" + code
        hit = _cache_get(ck)
        if hit is None:
            try:
                hit = us_universe.us_price(kis_get, cfg, code)
                _cache_put(ck, hit)
            except Exception as e:
                errors[code] = safe_message(e, 120)
                continue
        data[code] = hit
    return data, errors


#: 미국 시세를 한 요청에 몇 종목까지 받나 — 종목마다 KIS 1건이라 국내 멀티(30종목에 1건)보다 비싸다
US_QUOTES_MAX = 20


# ── 미국 장중 미리받기 (묶음 3 · 2026-10-07 재권님 「응 해줘」) ────────────────────────
#
# 미국 묶음 전부(나스닥100 ∪ S&P500 · 2026-10-07 실측 519종목)의 5분봉을 미국 장중(동부 09:30~16:05 · 서머타임은
# zoneinfo 가 따라간다)에 5분 칸이 닫힐 때마다 한 바퀴 받는다. 일·주·월·년봉 · 시총 · 지난 세션 5분봉은 **장 전 창**
# (동부 07:15~09:15 · 지금 한국 20:15~22:15)에 나눠 받는다 — 재권님 「장전에 미리 받을 수 있는 거 먼저 · 분산으로」. 국내 미리받기와 줄을 따로 쓴다 — 국내 장(한국 08:00~20:10)과 시간이 안 겹친다.
# 받는 길은 겉 함수 get_chart 그대로라 자물쇠 · 저장 · `sync` 가 화면과 같다.
#
# **8765 만 돈다**(창구 검수 — 8764 는 차트 주소째 8765 로 넘기므로 8765 가 쌓은 것을 본다. 둘 다 돌면
# 같은 KIS 줄에서 두 배가 나간다). `KJC_US_PREFILL=0` 이면 8765 도 끄고, `=1` 이면 다른 서버도 켠다.
#
# **휴장일** — KIS 해외 휴장 API(countries-holiday)는 결제일 목록이라 휴장일을 직접 주지 않는다(2026-10-07 실측).
# 그래서 동부 10:00 까지 첫 종목에 오늘 봉이 없으면 그날을 휴장으로 보고 멈춘다. **KIS 오류로 못 받은 것과
# 가른다** — 오류면 「KIS 오류」 로 적고 다음 칸에 다시 본다(휴장으로 굳히지 않는다).

US_PREFILL_ENV = (os.environ.get("KJC_US_PREFILL") or "").strip().lower()
#: 장 마감 뒤 일봉 바퀴 — 마감(동부 16:00) 몇 분 뒤에 도나 · 종목 사이 몇 초 쉬나(518종목 ≈ 7분 · 초당 1.3 안팎)
US_POST_AFTER_MIN = 20
US_POST_GAP_SEC = 0.5
#: 한 바퀴를 몇 초 안에 고르게 나눠 받나 — 5분 칸 안에 끝나게
US_PREFILL_SPREAD_SEC = 270


def _us_log(msg):
    print("  [미국] %s %s" % (datetime.now(KST).strftime("%H:%M:%S"), msg))


def _us_today_seen(code, et_date):
    """그 종목 5분봉에 오늘(동부) 봉이 들었나 → True · False · None(KIS 오류로 못 봤다)."""
    try:
        bars = us_universe.us_5m(kis_get, cfg_for_us_probe(), code, 1)
    except Exception as e:
        _us_log("%s 확인 실패 — KIS 오류 (%s) · 휴장으로 보지 않고 다음 칸에 다시 봄"
                % (code, safe_message(e, 80)))
        return None
    start = us_universe.et_min_kst(et_date, us_universe.EXT_OPEN_MIN)   # 프리마켓(04:00) 봉부터 센다 (2026-10-27)
    return any(b["ts"] >= start for b in bars)


_us_cfg = {"cfg": None}


def cfg_for_us_probe():
    return _us_cfg["cfg"]


def start_us_prefill(cfg, port):
    """미국 장중 미리받기를 켠다. 8765 가 아니면(또는 끈 줄이면) 켜지 않는다."""
    if not cfg or not marketdb.writable():
        return False
    if US_PREFILL_ENV in ("0", "false", "no", "off"):
        return False
    if port != MAIN_PORT and US_PREFILL_ENV not in ("1", "true", "yes", "on"):
        return False
    _us_cfg["cfg"] = cfg

    def one_round(codes, period, limit):
        gap = US_PREFILL_SPREAD_SEC / max(1, len(codes)) if period == "5m" else 1.0
        c0, t0 = _up_stat["calls"] + _stats["kis_calls"], time.time()
        for code in codes:
            try:
                get_chart(cfg, code, period, limit)
            except Exception as e:
                _us_log("%s %s 실패 (%s)" % (code, period, safe_message(e, 80)))
            # 예산이 남으면 서버가 당긴다(㉢ · 2026-10-15) — 고정 270초 나눔은 한 종목 호출 시간까지 더해
            # 한 바퀴가 397초로 5분 칸을 넘었다(10-15 04:45~05:06 로그)
            time.sleep(gap * fill_factor())
        n = _up_stat["calls"] + _stats["kis_calls"] - c0
        _us_log("%s 한 바퀴 %d종목 · KIS %d건 · %.0f초 · 초당 %.2f건"
                % (period, len(codes), n, time.time() - t0, n / max(1.0, time.time() - t0)))

    def pre_round(codes, et_date):
        """장 전 창 — 종목마다 일·주·월·년봉 마지막 봉 · 시총 · (처음이면) 지난 세션 5분봉을 받는다.
        남은 창 시간에 고르게 나눈다. 창이 끝나면 멈추고 나머지는 다음 날 창으로 — 장중을 무겁게 하지 않는다."""
        c0, t0, done = _up_stat["calls"] + _stats["kis_calls"], time.time(), 0
        for i, code in enumerate(codes):
            ok, _, left = us_universe.in_premarket()
            if not ok:
                _us_log("장 전 창이 끝나 %d/%d종목에서 멈춤 — 나머지는 다음 날 장 전에" % (i, len(codes)))
                break
            gap = max(0.2, left / max(1, len(codes) - i))   # 남은 시간을 남은 종목에 고르게
            t1 = time.time()
            try:
                for per, lim in (("D", DWMY_WANT), ("W", DWMY_WANT), ("M", DWMY_WANT), ("Y", 20)):   # 국내와 같은 400 (2026-10-08 · 전에 240·100·100)
                    get_chart(cfg, code, per, lim)
                if not read_candles(code, "5m", 1):
                    get_chart(cfg, code, "5m", 1)            # 처음이면 지난 세션 5분봉(두 쪽)
                us_universe.save_caps(kis_get, cfg, [code])
                done += 1
            except Exception as e:
                _us_log("%s 장 전 받기 실패 (%s)" % (code, safe_message(e, 80)))
            time.sleep(max(0.0, gap - (time.time() - t1)))
        n = _up_stat["calls"] + _stats["kis_calls"] - c0
        _us_log("장 전(%s) %d/%d종목 · KIS %d건 · %.0f초 · 초당 %.2f건"
                % (et_date, done, len(codes), n, time.time() - t0, n / max(1.0, time.time() - t0)))

    def post_round(codes, et_date):
        """장 마감 뒤 바퀴 — 종목마다 일봉을 한 번 받아 그날 마감 종가를 넣는다 (2026-10-12 재권님 「가로」).
        전에는 그날 일봉을 다음 날 장 전 창에서야 받아, 그 사이 순위 표 · 차트가 장 전 값을 냈다.
        일봉 신선 기준(60초)이 장 전 창보다 짧아 `get_chart` 가 그대로 KIS 를 부른다 — 한 종목 1건."""
        c0, t0, done = _up_stat["calls"] + _stats["kis_calls"], time.time(), 0
        for code in codes:
            try:
                get_chart(cfg, code, "D", DWMY_WANT)
                done += 1
            except Exception as e:
                _us_log("%s 마감 뒤 일봉 실패 (%s)" % (code, safe_message(e, 80)))
            time.sleep(US_POST_GAP_SEC * fill_factor())
        n = _up_stat["calls"] + _stats["kis_calls"] - c0
        _us_log("마감 뒤(%s) 일봉 %d/%d종목 · KIS %d건 · %.0f초 · 초당 %.2f건"
                % (et_date, done, len(codes), n, time.time() - t0, n / max(1.0, time.time() - t0)))

    busy = {"pre": False, "post": False}

    def in_bg(key, fn, *args):
        """장 전 · 마감 뒤 바퀴는 따로 돈다 — 한 줄에서 돌면 그동안(장 전 창 두 시간) 5분봉 바퀴가 멈춘다.
        5분봉 바퀴가 프리마켓 · 애프터마켓까지 돌게 되면서 나눴다 (2026-10-27)."""
        def run():
            try:
                fn(*args)
            except Exception as e:
                _us_log("%s 바퀴 오류 (%s)" % (key, type(e).__name__))
            finally:
                busy[key] = False
        busy[key] = True
        threading.Thread(target=run, daemon=True, name="prefill-us-" + key).start()

    def loop():
        time.sleep(PREFILL_START_SEC)
        state = {"holiday": None, "seen": None, "pre": None, "slot": None, "probe": None, "post": None}
        while True:
            try:
                st, d, m = us_universe.session_state()
                codes = us_universe.all_members()
                pre, pd, _left = us_universe.in_premarket()
                if pre and codes and state["pre"] != pd and not busy["pre"]:
                    state["pre"] = pd                     # 하루 한 번 — 다 못 받아도 그날은 다시 안 돈다
                    in_bg("pre", pre_round, codes, pd)
                if (st == "after" and codes and state["post"] != d and not busy["post"]
                        and m >= us_universe.SESSION_CLOSE_MIN + US_POST_AFTER_MIN):
                    # 하루 한 번 — 휴장일이면 받은 마지막 봉이 앞 거래일이라 그대로 맞다. 재시작 뒤에도 그날 한 번 돈다
                    state["post"] = d
                    in_bg("post", post_round, codes, d)
                # 5분봉 바퀴 — 프리마켓부터 애프터마켓까지(동부 04:00~20:05 · 2026-10-27). 전에는 정규장만 돌았다
                ext, ed, em = us_universe.in_ext_hours()
                if ext and codes and state["holiday"] != ed:
                    slot = (ed, em // 5)
                    if slot != state["slot"]:
                        if state["seen"] != ed and state["probe"] != slot:   # 오늘 봉이 아직 — 칸마다 한 번만 한 종목으로 본다
                            state["probe"] = slot
                            seen = _us_today_seen(codes[0], ed)
                            if seen:
                                state["seen"] = ed
                                _us_log("오늘(%s) 봉이 들어왔다 — 미리받기 시작" % ed)
                            elif seen is False and em >= us_universe.HOLIDAY_JUDGE_MIN:
                                state["holiday"] = ed
                                _us_log("오늘(%s) 동부 10:00 까지 봉이 없다 — 휴장으로 보고 멈춤" % ed)
                        if state["seen"] == ed:
                            state["slot"] = slot
                            # 화면이 본 종목부터 · 모달로 연 묶음 밖 미국 종목도 그 바퀴에 (2026-10-12 · 설계서 3번).
                            # 목록 밖은 `PREFILL_HOT_SEC` 안에 본 것만 — 한 번 본 종목이 바퀴마다 계속 붙지 않게
                            one_round(_ui_order(codes, keep=us_universe.is_us, keep_sec=PREFILL_HOT_SEC), "5m", 1)
            except Exception as e:
                _us_log("뒤 작업 오류 (%s)" % type(e).__name__)
            time.sleep(PREFILL_SLOT_POLL_SEC)

    threading.Thread(target=loop, daemon=True, name="prefill-us").start()
    return True


# ── 봉 채우기 — 비어 있는 지난 5분봉 · 미국 일·주·월봉을 한가할 때 메운다 (2026-10-08) ─────────────────
#
# 재권님 말씀(10-08) — 「코스닥 미국주식등등 5분봉이 과거꺼 안받아진것들 있는데 이거 순차로 좀 받아놔 10일 받기로
# 한거 아니였나?」 · 「일봉 주봉 월봉까지 다 확인해 이번에 추가된 종목들 전부야」. 그날 8765 DB 실측(읽기 전용):
#
#     국내 5분봉    지난 날짜를 받는 길이 없어 그날치만 쌓였다 — 미리받기는 코스피 상위 100 + 화면이 연 종목뿐이라
#                  코스닥150 · 코스피200 나머지는 날마다 빈다(빈 「종목×날」 약 2,000)
#    미국 5분봉    10-02 부터만 있다(받기 시작한 날)
#    미국 일·주·월  일 240~300 · 주·월 100 에서 멈췄다 — 장 전 창이 적게 받고 바로 「다 받음」 을 적었다
#
# **기본은 켜짐이다 — 끄려면 `KJC_BAR_FILL=0`** (2026-10-08 재권님 「응 그렇게 해」). 처음에는 꺼짐으로 넣었다
# (처음 한 바퀴가 KIS 약 28,600건이라 재시작만으로 돌면 안 된다 · 「켜기 전에 먼저 잰다」) — 건수를 재서 올리고 켜기를
# 허락받아 기본을 바꿨다. 쓰는 서버(8765)에서만 돈다.
#
# **쉬는 때** — 국내 장중(그날 봉이 들어오는 동안) · 미국 장 전 창 · 미국 장중 · 화면을 보는 동안. 휴장일은 달력이
# 없어 「08:30 이 지났는데 그날 국내 5분봉이 하나도 없다」 로 가른다(10-09 한글날 낮을 쓰려고).
# **순서** — 미국 5분봉(KIS 가 약 한 달 전까지만 준다 — 미루면 앞날부터 영영 못 받는다) → 미국 일·주·월 → 국내 5분봉.
# **날짜** — 그 종목 일봉의 최근 `view_days`(10) 거래일. 휴장 · 거래정지 날이 저절로 빠진다.

BAR_FILL_ON = (os.environ.get("KJC_BAR_FILL") or "").strip().lower() not in ("0", "false", "no", "off")
BAR_FILL_THREAD_NAME = "bar-fill"
#: KIS 한 건 뒤 쉬는 시간 — 초당 약 1.5건. 미리받기 · 장 전 창이 쓰던 빠르기와 같은 자리다(10-07 장 전 창 실측 초당 1.49)
BAR_FILL_CALL_GAP = 0.67
#: 받을 것이 없거나 다 돈 뒤 다시 보는 간격. 다시 볼 때는 DB 만 읽는다 — KIS 를 안 부른다
BAR_FILL_REST_SEC = 1800
#: 지난 날짜 분봉(`FHKST03010230`)이 한 번에 주는 1분봉 수(2026-10-08 실측 120)
KR_PAST_PER_CALL = 120
#: 하루(08:00~20:00 = 720분)를 덮는 데 드는 건수에 한 번 여유 — 무한히 돌지 않게
KR_PAST_MAX_CALLS = (MINUTE_DAY_END - MINUTE_DAY_START) // KR_PAST_PER_CALL + 1
#: 「그날이 다 찼나」 를 볼 때 봉 사이가 이보다 벌어지면 덜 찬 것 — 미리받기가 30분 칸으로 받으므로 한 칸이 빠지면 35분이 벌어진다
BAR_FILL_MAX_GAP_MIN = 30

_bar_fill = {"state": "꺼짐", "calls": 0, "items": 0, "left": None, "at": None}


def _bar_fill_log(msg):
    print("  [채우기] %s %s" % (datetime.now(KST).strftime("%H:%M:%S"), msg))


def _kis_calls_now():
    return _up_stat["calls"] + _stats["kis_calls"]


def _day_complete(minutes, first, last):
    """그날 봉의 분(그날 몇 분째) 목록이 정규장 `first`~`last` 를 다 덮나 — 첫 봉 · 끝 봉 · 사이 벌어짐을 본다.

    봉 개수로 가르지 않는다 — 그러면 종목 · 시장마다 맞는 개수를 박아야 한다."""
    ms = sorted(m for m in minutes if first <= m <= last)
    if not ms or ms[0] > first + 5 or ms[-1] < last - 5:
        return False
    return all(b - a <= BAR_FILL_MAX_GAP_MIN for a, b in zip(ms, ms[1:]))


def _fill_marks(code):
    v = _meta_get("m5fill:%s" % code) or ""
    return {d for d in v.split(",") if d}


def _fill_mark(code, day):
    """지난 날짜로 한 번 받은 날을 적는다 — 거래가 드물어 다 안 차도 다시 안 받는다. 최근 것만 둔다."""
    days = sorted(_fill_marks(code) | {day})[-(PERIODS["5m"]["view_days"] * 2):]
    _meta_set("m5fill:%s" % code, ",".join(days))


def _recent_days(code, n, before=None):
    """그 종목 일봉의 최근 n 거래일(YYYYMMDD · 오래된 것 먼저). `before` 를 주면 그 날짜 앞만."""
    with _db_lock, db_conn() as conn:
        rows = conn.execute(
            "SELECT ts FROM candles WHERE code = ? AND period = 'D' AND (? IS NULL OR ts < ?) "
            "ORDER BY ts DESC LIMIT ?", (code, before, before, n)).fetchall()
    return sorted(r["ts"][:8] for r in rows)


def _5m_ts_since(code, since):
    with _db_lock, db_conn() as conn:
        rows = conn.execute(
            "SELECT ts FROM candles WHERE code = ? AND period = '5m' AND ts >= ?",
            (code, since)).fetchall()
    return [r["ts"] for r in rows]


def _kr_today_seen(today):
    """오늘 국내 5분봉이 하나라도 들었나 — 휴장일을 가르는 데 쓴다(달력이 없다)."""
    with _db_lock, db_conn() as conn:
        r = conn.execute(
            "SELECT 1 FROM candles WHERE period = '5m' AND ts >= ? AND ts < ? "
            "AND code GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]' LIMIT 1",
            (today + "0000", today + "9999")).fetchone()
    return r is not None


def _kr_busy(now=None):
    """국내 5분봉이 지금 들어오는 중인가. 평일 08:00~20:10 이 그 자리인데, 08:30 이 지나도 그날 봉이 하나도
    없으면 휴장일로 본다."""
    now = now or datetime.now(KST)
    if not _minutes_live(now):
        return False
    if now.hour * 60 + now.minute < MINUTE_DAY_START + 30:
        return True
    return _kr_today_seen(now.strftime("%Y%m%d"))


def _bar_fill_wait_reason():
    """지금 쉬어야 하면 그 까닭(글), 아니면 None."""
    if _ui_busy():
        return "화면을 보는 중"
    if us_universe.in_premarket()[0]:
        return "미국 장 전 창"
    if us_universe.session_state()[0] == "open":
        return "미국 장중"
    if _kr_busy():
        return "국내 장중"
    return None


def _bar_fill_gate():
    """쉬어야 하는 동안 기다린다. 까닭이 바뀔 때만 한 줄 남긴다."""
    said = None
    while True:
        why = _bar_fill_wait_reason()
        if not why:
            if said:
                _bar_fill_log("다시 받습니다")
            _bar_fill["state"] = "받는 중"
            return
        if why != said:
            _bar_fill_log("쉼 — %s" % why)
            said = why
        _bar_fill["state"] = "쉼(%s)" % why
        time.sleep(PREFILL_SLOT_POLL_SEC)


def _kr_past_one_market(cfg, code, day, hour, div):
    """지난 날짜 1분봉 한 쪽(120개) — 주식일별분봉조회(`FHKST03010230`). 모양은 `_minutes_one_market` 과 같다."""
    data = kis_get(
        cfg,
        "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice",
        {
            "FID_COND_MRKT_DIV_CODE": div, "FID_INPUT_ISCD": code,
            "FID_INPUT_HOUR_1": hour, "FID_INPUT_DATE_1": day,
            "FID_PW_DATA_INCU_YN": "Y", "FID_FAKE_TICK_INCU_YN": "",
        },
        "FHKST03010230",
    )
    out = []
    for r in out_rows(data, "output2"):
        d, t = r.get("stck_bsop_date"), r.get("stck_cntg_hour")
        close = _num(r.get("stck_prpr"), int)
        if not d or not t or close is None:
            continue
        out.append({
            "ts": "%s%s" % (d, str(t)[:4]),
            "open": _num(r.get("stck_oprc"), int),
            "high": _num(r.get("stck_hgpr"), int),
            "low": _num(r.get("stck_lwpr"), int),
            "close": close,
            "volume": _num(r.get("cntg_vol"), int),
        })
    return out


def _kr_past_chunk(cfg, code, day, hour):
    """한 쪽을 받되 시장은 `fetch_minutes_from_kis` 와 같이 고른다 — 먼저 물을 쪽은 `minute_market_div`,
    거래 있는 봉이 1개 이하면 다른 쪽으로 한 번 더 받아 더 많은 쪽(같으면 `J`). 까닭은 그 함수 주석에 있다."""
    first = minute_market_div(hour, code)
    out = _kr_past_one_market(cfg, code, day, hour, first)
    nz = sum(1 for b in out if (b["volume"] or 0) > 0)
    if nz <= 1:
        other = "UN" if first == "J" else "J"
        time.sleep(BAR_FILL_CALL_GAP)
        alt = _kr_past_one_market(cfg, code, day, hour, other)
        alt_nz = sum(1 for b in alt if (b["volume"] or 0) > 0)
        if alt_nz > nz or (alt_nz == nz and other == "J" and alt):
            _note_un_thin(code, first, other, alt_nz)
            return alt
    return out


def _kr_past_day(cfg, code, day):
    """지난 하루(08:00~20:00) 1분봉을 모아 5분봉으로 → 저장한 봉 수. 20:00 에서 120분씩 거슬러 내려간다.

    거래가 드물어 120개가 그보다 앞까지 닿으면 그 앞부터 다시 묻는다 — 같은 분을 두 번 받지 않는다."""
    raw, t = {}, MINUTE_DAY_END
    for _ in range(KR_PAST_MAX_CALLS):
        if t < MINUTE_DAY_START:
            break
        rows = _kr_past_chunk(cfg, code, day, "%02d%02d00" % (t // 60, t % 60))
        time.sleep(BAR_FILL_CALL_GAP)
        mine = [b for b in rows if b["ts"][:8] == day]
        for b in mine:
            m = int(b["ts"][8:10]) * 60 + int(b["ts"][10:12])
            if MINUTE_DAY_START <= m <= MINUTE_DAY_END:
                raw[b["ts"]] = b
        if not mine or len(mine) < len(rows):
            break                                   # 빈 날(휴장 · 정지)이거나 그날 앞까지 닿았다
        t = min(int(b["ts"][8:10]) * 60 + int(b["ts"][10:12]) for b in mine) - 1
    bars = aggregate_minutes(list(raw.values()), 5)
    return save_candles(code, "5m", bars)


def _kr_fill_work():
    """국내 — 지수 구성 종목마다 최근 거래일 중 5분봉이 덜 찬 날 → [(코드, 날짜)]."""
    n = PERIODS["5m"]["view_days"]
    first = KRX_OPEN[0] * 60 + KRX_OPEN[1]
    last = KRX_CLOSE[0] * 60 + KRX_CLOSE[1]
    today = datetime.now(KST).strftime("%Y%m%d")
    work = []
    for code in _dwmy_codes():
        work.extend((code, d) for d in _kr_days_to_fill(code, n, first, last, today))
    return work


def _kr_days_to_fill(code, n, first, last, today):
    """한 종목의 최근 n 거래일 중 5분봉이 덜 찬 날(최근 날부터). 오늘은 장중이면 뺀다 — 그날 봉은 화면이 받는다."""
    days = [d for d in _recent_days(code, n) if not (d == today and _kr_busy())]
    if not days:
        return []
    marks = _fill_marks(code)
    have = {}
    for ts in _5m_ts_since(code, days[0]):
        have.setdefault(ts[:8], []).append(int(ts[8:10]) * 60 + int(ts[10:12]))
    return [d for d in reversed(days)
            if d not in marks and not _day_complete(have.get(d, []), first, last)]


# ── 지수 밖 종목도 열면 지난 5분봉을 채운다 (2026-10-16 재권님 「응 그래」) ──────────
#
# 위 뒤 작업은 지수 구성종목(`_dwmy_codes` · 코스피200 · 코스닥150)의 지난 거래일만 채운다. 그 밖 종목은
# 화면이 여는 순간 받는 오늘 것뿐이라 5분봉이 하루치만 그려졌다(10-16 12:27 재권님 그림 · SNT다이나믹스 003570 —
# 8765 의 5분봉 54개가 전부 그날 08:00~12:25 · MA60 · MA200 「봉 부족」).
# 그래서 지수 밖 종목의 5분봉을 화면이 부르면 **그 종목만 한 번** 지난 거래일(`view_days`)을 뒤에서 채운다.
# 날마다 하는 일은 뒤 작업과 같다(`_kr_past_day` · `_fill_mark`) — 하루 7번 안팎 · 종목당 1~2분.
# 하루에 한 종목 한 번만 시작한다 — 화면은 5분봉을 30초마다 다시 부른다. 일봉이 없으면 그 일봉부터 받는다(거래일을 그것으로 센다).
# 쓰는 서버(8765)에서만 돈다 — 세션 서버 · 서비스방은 DB 를 읽기만 한다(`marketdb.READONLY`).
_kr_open_fill = {}                    # code -> 시작한 날(YYYYMMDD)
_kr_open_lock = threading.Lock()
_dwmy_set_cache = [0.0, frozenset()]  # [잰 시각, 지수 구성종목] — 한 시간 들고 있는다(5분봉 요청마다 DB 를 안 읽게)


def _in_dwmy(code):
    if time.time() - _dwmy_set_cache[0] > 3600:
        _dwmy_set_cache[1] = frozenset(_dwmy_codes())
        _dwmy_set_cache[0] = time.time()
    return code in _dwmy_set_cache[1]


def kick_kr_open_fill(cfg, code):
    """지수 밖 국내 종목의 5분봉을 열었으면 지난 거래일 채우기를 뒤에서 한 번 시작한다."""
    if not marketdb.writable() or not re.fullmatch(r"\d{6}", code or ""):
        return
    today = datetime.now(KST).strftime("%Y%m%d")
    with _kr_open_lock:
        if _kr_open_fill.get(code) == today:
            return
        _kr_open_fill[code] = today
    if _in_dwmy(code):
        return

    def run():
        try:
            n = PERIODS["5m"]["view_days"]
            if not _recent_days(code, n):
                get_chart(cfg, code, "D", BARS_PER_CALL)     # 거래일을 셀 일봉부터 — 한 쪽
            days = _kr_days_to_fill(code, n, KRX_OPEN[0] * 60 + KRX_OPEN[1],
                                    KRX_CLOSE[0] * 60 + KRX_CLOSE[1], today)
            for d in days:
                _kr_past_day(cfg, code, d)
                _fill_mark(code, d)
            if days:
                _bar_fill_log("연 종목 %s 지난 5분봉 %d일 채움" % (code, len(days)))
        except Exception as e:
            _bar_fill_log("연 종목 %s 지난 5분봉 오류 (%s)" % (code, type(e).__name__))

    threading.Thread(target=run, daemon=True, name="kr-open-fill").start()


def _us_fill_work():
    """미국 — 묶음 종목마다 최근 세션(동부 날짜) 중 5분봉이 덜 찬 날 → [(코드, 동부 날짜)].
    봉 ts 가 한국 시각이면(`US_SHOW_KST`) 동부로 바꿔 센다. 오늘 세션은 끝난 뒤(16:05)부터 든다."""
    n = PERIODS["5m"]["view_days"]
    first = us_universe.SESSION_OPEN_MIN
    last = us_universe.SESSION_CLOSE_MIN
    st, et_today, _m = us_universe.session_state()
    before = None if st in ("after", "closed") else et_today
    since_kst = (datetime.now(KST) - timedelta(days=n * 2 + 7)).strftime("%Y%m%d0000")
    work = []
    for code in us_universe.all_members():
        days = _recent_days(code, n, before)
        if not days:
            continue
        marks = _fill_marks(code)
        have = {}
        for ts in _5m_ts_since(code, since_kst):
            t = datetime.strptime(ts, "%Y%m%d%H%M")
            t = t.replace(tzinfo=KST).astimezone(us_universe.ET) if us_universe.US_SHOW_KST else t
            have.setdefault(t.strftime("%Y%m%d"), []).append(t.hour * 60 + t.minute)
        for d in reversed(days):
            if d not in marks and not _day_complete(have.get(d, []), first, last):
                work.append((code, d))
    return work


def _us_deep_work():
    """미국 일·주·월봉이 `DWMY_WANT` 에 못 미치고 아직 끝까지 거슬러 받아 보지 않은 것 → [(코드, 주기)].
    옛 「다 받음」(`backfill:`) 표시는 장 전 창이 적게 받고 적은 것이라 보지 않는다 — 이 일은 자기 표시(`usdeep:`)를 쓴다."""
    work = []
    for code in us_universe.all_members():
        for period in ("D", "W", "M"):
            if _meta_get("usdeep:%s:%s" % (code, period)) == "done":
                continue
            if len(read_candles(code, period, DWMY_WANT)) < DWMY_WANT:
                work.append((code, period))
    return work


def _kr_div_work():
    """국내 일 · 주 · 월 · 년봉 중 아직 `MARKET_DIV_BARS`(지금 통합)로 다시 안 받은 것 → [(코드, 주기)] (2026-10-15 · 기준을 바꾸면 표시가 어긋나 저절로 한 번 더 받는다).

    화면이 연 (종목, 주기)는 `_get_chart_one` 이 그 자리에서 다시 받지만, **읽기 전용 서버(8764 · 8767 · 세션)는
    저장 · 표시를 못 해** 8765 가 그 종목을 열기 전까지 통합 봉을 그대로 냈다(개념정의 검수 · 8767 삼성 일봉 시가 225,000).
    그래서 8765 의 봉 채우기가 DB 에 있는 것 전부를 한 번씩 다시 받는다. 감시 대상(시가총액 순)을 앞에 둔다."""
    try:
        with _db_lock, db_conn() as conn:
            have = conn.execute(
                "SELECT DISTINCT code, period FROM candles WHERE period IN ('D','W','M','Y') AND length(code)=6").fetchall()
            rank = {r[0]: r[1] for r in conn.execute("SELECT stock_code, rank FROM dart_universe")}
    except Exception:
        return []
    work = [(c, p) for c, p in have
            if not us_universe.is_us(c) and _meta_get("div:%s:%s" % (c, p)) != MARKET_DIV_BARS]
    work.sort(key=lambda cp: (rank.get(cp[0], 10 ** 6), cp[0], "DWMY".index(cp[1])))
    return work


def _bar_fill_run(label, work, do_one):
    """일감 목록을 하나씩 — 하나 앞마다 쉬어야 하는지 본다. 백 개마다 · 끝에 한 줄."""
    if not work:
        return 0
    c0, t0 = _kis_calls_now(), time.time()
    _bar_fill_log("%s %d건 시작" % (label, len(work)))
    left, total = list(work), len(work)
    for i in range(total):
        _bar_fill_gate()
        # **쉬었다 다시 받을 때 방금 화면이 본 종목의 일감부터** (2026-10-12 · 설계서 3번). 본 종목이 없으면
        # 맨 앞 그대로 — `min` 은 같은 열쇠면 앞의 것을 고른다
        key, seen = _ui_key()
        item = min(left, key=lambda it: key(it[0])) if seen else left[0]
        left.remove(item)
        _bar_fill["left"] = "%s %d/%d" % (label, i, total)
        try:
            do_one(*item)
        except Exception as e:
            _bar_fill_log("%s %s 실패 (%s)" % (label, " ".join(item), safe_message(e, 80)))
        _bar_fill["items"] += 1
        if (i + 1) % 100 == 0:
            n = _kis_calls_now() - c0
            _bar_fill_log("%s %d/%d · KIS %d건 · %.0f초" % (label, i + 1, total, n, time.time() - t0))
    n = _kis_calls_now() - c0
    _bar_fill["calls"] += n
    _bar_fill_log("%s 끝 %d건 · KIS %d건 · %.0f초 · 초당 %.2f건"
                  % (label, len(work), n, time.time() - t0, n / max(1.0, time.time() - t0)))
    return len(work)


def start_bar_fill(cfg, port):
    """봉 채우기를 켠다 — 쓰는 서버 · 8765 일 때만(`KJC_BAR_FILL=0` 이면 끔)."""
    if not BAR_FILL_ON or not cfg or port != MAIN_PORT or not marketdb.writable():
        return False

    def us_5m_one(code, et_date):
        bars = us_universe.us_5m_session(kis_get, cfg, code, et_date)
        time.sleep(BAR_FILL_CALL_GAP * 2)
        save_candles(code, "5m", bars)
        _fill_mark(code, et_date)

    def us_deep_one(code, period):
        bars = us_universe.us_bars(kis_get, cfg, code, period, DWMY_WANT)
        time.sleep(BAR_FILL_CALL_GAP * max(1, -(-DWMY_WANT // us_universe.DAILY_PER_CALL)))
        save_candles(code, period, bars)
        _meta_set("usdeep:%s:%s" % (code, period), "done")

    def kr_one(code, day):
        _kr_past_day(cfg, code, day)
        _fill_mark(code, day)

    def kr_div_one(code, period):
        # 화면이 여는 길과 같은 양(DWMY_WANT)을 MARKET_DIV_BARS(지금 통합)로 거슬러 받아 덮는다 · 받은 만큼 쉰다
        bars = fetch_bars_back(cfg, code, period, DWMY_WANT)
        time.sleep(BAR_FILL_CALL_GAP * max(1, -(-DWMY_WANT // BARS_PER_CALL)))
        if bars:
            save_candles(code, period, bars)
            _meta_set("div:%s:%s" % (code, period), MARKET_DIV_BARS)

    def loop():
        time.sleep(PREFILL_START_SEC)
        while True:
            try:
                _bar_fill_gate()
                done = 0
                done += _bar_fill_run("미국 5분봉", _us_fill_work(), us_5m_one)
                done += _bar_fill_run("미국 일주월", _us_deep_work(), us_deep_one)
                done += _bar_fill_run("국내 5분봉", _kr_fill_work(), kr_one)
                done += _bar_fill_run("국내 일주월년 시장구분", _kr_div_work(), kr_div_one)
                _bar_fill["at"] = datetime.now(KST).strftime("%m-%d %H:%M")
                _bar_fill["left"] = None
                _bar_fill["state"] = "다 돎 · 다음 확인 대기"
                if done:
                    _bar_fill_log("한 바퀴 끝 — 일감 %d건" % done)
            except Exception as e:
                _bar_fill_log("뒤 작업 오류 (%s)" % type(e).__name__)
            time.sleep(BAR_FILL_REST_SEC)

    _bar_fill["state"] = "켜짐"
    threading.Thread(target=loop, daemon=True, name=BAR_FILL_THREAD_NAME).start()
    return True


def _code_ok(code):
    """국내 6자리 종목코드이거나, us_symbols 에 있는 미국 티커인가."""
    return (code.isdigit() and len(code) == 6) or us_universe.is_us(code)


def _get_chart_one(cfg, code, period, limit, gap_check=True):
    """DB 를 먼저 보고, 최근 구간이 오래됐으면 KIS 에서 받아 덮어쓴다.

    당일(또는 최근) 캔들은 장중에 계속 바뀌므로, 마지막 갱신으로부터
    fresh_sec 이 지나면 다시 받아온다. 과거 캔들은 변하지 않으므로 그대로 둔다.
    """
    import datetime
    db_init()
    conf = PERIODS[period]
    rows = read_candles(code, period, _view_limit(code, period, limit))

    mkey = "sync:%s:%s" % (code, period)
    last_sync = float(_meta_get(mkey) or 0)
    if conf.get("close_once"):
        stale = last_sync < _last_close_ts()        # 마감 뒤 한 번 — 위 PERIODS 의 `close_once`
    else:
        stale = (time.time() - last_sync) > conf["fresh_sec"]

    # **`MARKET_DIV_BARS` 와 다른 기준으로 쌓인 일 · 주 · 월 · 년봉은 한 번 다시 받는다** (2026-10-15 — 낮에 정규장으로 · 저녁에 통합으로 되돌림).
    # 그 (종목, 주기)를 처음 볼 때 「오래됨」 으로 보고 달라는 만큼 거슬러 받아 덮어쓴다 — 받은 뒤 표시를 적어 다시 안 받는다.
    # 달라는 것보다 오래된 봉은 통합 그대로 남는다(화면에 안 닿는 자리).
    dkey = "div:%s:%s" % (code, period)
    if conf["kis"] and _meta_get(dkey) != MARKET_DIV_BARS:
        stale = True

    # 달라는 만큼 DB 에 없고, 아직 끝까지 훑어보지 않았으면 과거를 더 받는다.
    #
    # **「오래됐나」 만 보면 과거가 영영 안 채워진다** (2026-09-29). 한 번에
    # 100개만 오므로 일봉은 100개에서 멈춰 있었고, 그 뒤로는 `stale` 일 때만
    # 최근 것을 덮어쓰기만 했다. 그래서 200일선이 일·주·월봉에서 안 그려졌다.
    want_more = (conf["kis"] and len(rows) < limit
                 and _meta_get("backfill:%s:%s" % (code, period)) != "done")

    fetched = 0
    if not rows or stale or want_more:
        if conf["kis"]:                      # 일/주/월/년
            bars = fetch_bars_back(cfg, code, period, limit)
            if bars:
                _meta_set(dkey, MARKET_DIV_BARS)
        else:                                # 분봉
            # 많이 비었으면 하루치를 모으고(호출 여러 번), 조금이면 최근 구간만.
            #
            # **「있나 없나」로 가르면 안 된다.** 전에는 rows 가 하나라도 있으면
            # 최근 구간만 받았는데, 며칠 전 것이 남아 있는 종목은 오늘 것이
            # 통째로 비었다 — 삼성전자우가 09:00~10:15 가 없이 7개뿐이었다
            # (2026-09-17). 거래가 잦은 종목만 자주 열려 저절로 채워지고
            # 있었던 것이라, 종목마다 봉 개수가 크게 갈렸다.
            cover = None
            marks = {}                       # 이번 바퀴에 적은 「받았다」 표 — 다른 분봉 기간에도 옮긴다(아래)
            fresh_m = _minutes_now_min()             # 받기 전 분 — 이 분 앞에서 끝난 봉은 다 찬 값으로 받는다
            marks = {}                       # 이번 바퀴에 적은 「받았다」 표 — 다른 분봉 기간에도 옮긴다(아래)
            if _minutes_need_day(code, period, rows, gap_check):
                raw, cover = fetch_minutes_day(cfg, code, refill=(period == "1m"))
                marks["dayfill"] = _minutes_trade_day()
                _meta_set("dayfill:%s:%s" % (code, period), marks["dayfill"])
            elif rows and not _minutes_live():
                # ④ 그 거래일 하루치를 이미 받았고 지금은 새 봉이 안 생긴다 —
                # KIS 를 부르지 않는다(주말에 화면이 열려 있으면 30초마다 한 건씩 나갔다).
                #
                # **단 거래일마다 한 번은 마지막 30분(19:30~20:00)을 받는다** — 20:05~20:10
                # 사이에 아무도 안 열었으면 그날 꼬리가 영영 빈다(전에는 저녁·주말 2번이
                # 하루치를 다시 받아 채웠다 · 창구 검수 지적). 주말 첫 열기 때 한 건 · 그 뒤 0건.
                _day = _minutes_trade_day()
                _ck = "dayclose:%s:%s" % (code, period)
                if _meta_get(_ck) != _day:
                    try:
                        raw = fetch_minutes_from_kis(
                            cfg, code, "%02d%02d00" % (MINUTE_DAY_END // 60, MINUTE_DAY_END % 60))
                    except RuntimeError:
                        raw = []
                    _meta_set(_ck, _day)
                    marks["dayclose"] = _day
                else:
                    raw = []
            else:
                # **지금 칸 + 아직 안 끝난 지난 칸 몇 개** (2026-10-06). 전에는 지금까지 30분만
                # 받아, 한 종목을 다시 찾는 데 30분이 넘으면 그 사이가 영영 비었다.
                raw, cover = fetch_minutes_day(cfg, code, MINUTE_PAST_PER_CALL)
            # **1분 · 5분을 함께 저장한다** (2026-11-11 재권님 「바로하라고해」 · 11-10 안 「응 해봐」). KIS 가 주는 것은 늘
            # 1분 원본이라 한 번 받은 것으로 두 기간을 다 채운다 — 호출은 안 는다. 다른 기간에도 「방금 받았다」(sync ·
            # dayfill · dayclose)를 적어, 화면이 그 기간을 열어도 KIS 를 다시 부르지 않는다. 미리받기도 이 길(5m)을 지난다.
            # 1분도 aggregate_minutes(…, 1) 로 거친다 — 거래 0 줄을 앞 체결 종가로 잇는 셈이 같아야 둘이 안 갈린다.
            day = max(b["ts"] for b in raw)[:8] if raw else None
            bars = []
            for p, m in (("1m", 1), ("5m", 5)):
                st = _stored_day(code, p, day) if raw else {}
                bs = aggregate_minutes(raw, m, st) if raw else []
                if raw:   # 「지금 줄」 로 옮겨 실린 마지막 체결을 제자리로 (pin_carried_trade 주석)
                    bs = pin_carried_trade(raw, bs, st, m)
                if m == 5 and cover is not None:
                    bs = _keep_covered_slots(bs, cover, _minutes_now_min())
                if p == period:
                    bars = bs
                    continue
                if bs:
                    save_candles(code, p, bs)
                _meta_set("sync:%s:%s" % (code, p), time.time())
                for k, v in marks.items():   # 이번에 받은 것만 — 옛 표를 옮기면 덜 찬 날을 「하루치 받음」 으로 본다
                    if k == "dayfill" and p == "1m":
                        continue             # 5분 하루치는 받은 칸을 건너뛰어(m5done) 1분이 덜 찰 수 있다 — 1분은 제 하루치(refill)를 따로
                    _meta_set("%s:%s:%s" % (k, code, p), v)
        fetched = save_candles(code, period, bars)
        # 1분을 열어도 5분이 위에서 함께 저장되므로 같이 적는다(m5upto 는 종목마다 하나 · 11-12 staging 합치며)
        # 20:00 뒤 · 주말에 받으면 첫 칸이 하루 끝(MINUTE_DAY_END)에서 끝난다 — 그때도 그날 봉은 다 끝난 뒤 받은 것이라 적는다(qa 11-11 물음)
        if not conf["kis"] and period in ("1m", "5m") and cover and any(hi >= min(fresh_m, MINUTE_DAY_END) for _, hi in cover):
            _minutes_mark_fresh(code, fresh_m)       # 「지금 칸」 까지 받아 저장했다 — vol_same_time 이 이 분까지만 센다
        _meta_set(mkey, time.time())
        if fetched:
            rows = read_candles(code, period, _view_limit(code, period, limit))
        elif not rows and bars and not marketdb.writable():
            # **읽기 전용 서버인데 그 종목이 DB 에 없다.** 저장은 못 하지만
            # 방금 받은 것은 보여준다 — 안 그러면 **차트가 빈다** (2026-10-01).
            #
            # ⚠️ **`rows` 가 있으면 절대 덮지 않는다.** `bars` 는 방금 받은
            # 구간뿐이라(일봉은 한 번에 100개) 덮으면 **이력이 통째로 짧아진다** —
            # 2026-09-29 에 「200일선이 일·주·월봉에서 안 그려졌다」 던 그 사고로
            # 되돌아간다 (홈페이지_정리 지적).
            #
            # **`fetched` 로 가르지 않는 이유** — 거기에 「쓰기 실패」 라는 뜻을
            # 더 실으면 「넣을 것이 없었다」 와 섞인다. 쓰기 가능 여부는 **따로** 본다.
            rows = bars[-limit:]
            return rows, 0, "KIS"

    return rows, fetched, ("KIS+DB" if fetched else "DB")


# ---------------------------------------------------------------- HTTP 핸들러

# ── Claude 창에 붙이는 서버 자료 — 페이지별 표 하나 (2026-11-04 · 재권님 「응 그렇게 해」 두 번) ──
# 화면은 「어느 페이지 · 무엇을 보나 · 종목」 만 보내고, 무엇을 붙일지는 이 표가 정한다.
# 창을 다른 페이지에 걸면(나중 · 따로 지시) 그 페이지 이름으로 한 줄을 더한다 — 무엇을 넘길지는 그 페이지 담당이 채운다.
# 열쇠는 화면이 보내는 context.screen 그대로다(지금 홀딩스 첫 화면이 「홈」 을 보낸다).
# 자료는 서버가 이미 받아 쌓는 것만 꺼낸다 — 새로 받는 길을 만들지 않는다. 못 꺼내면 {"못 받음": 까닭}.
CLAUDE_NEWS_MARKET = 30     # 쌓인 시장 뉴스 묶음 몇 건
CLAUDE_NEWS_STOCK = 15      # 종목 뉴스 몇 건
CLAUDE_DISCLOSURES = 10     # 종목 공시 몇 건


def _claude_indices(cfg, ctx):
    out, fails = {}, 0
    for icode, iname in INDEX_DEFS[:2]:   # 코스피 · 코스닥 — 「오늘 시장」 물음의 바탕(2026-11-03 18:5x)
        try:
            v = fetch_index(cfg, icode)
            out[iname] = {k: v.get(k) for k in ("value", "change", "changePct", "high", "low", "up", "down")}
        except Exception as e:
            out[iname] = {"못 받음": safe_message(e, 80)}
            fails += 1
    if fails == len(out):   # 둘 다 못 받았으면 자료 전체가 「못 받음」 — data.sources 에 받은 것으로 세지 않게(2026-11-04 qa)
        return {"못 받음": "; ".join("%s %s" % (n, v["못 받음"]) for n, v in out.items())}
    return out


def _claude_daily(cfg, ctx):
    """오늘 데일리 분석 — 아침에 나간 요약 글(telegram 칸). 오늘 날짜 문서가 없으면 「0건(읽음)」 —
    읽기는 됐고 글이 아직 없는 것이다(2026-11-05 · 읽기 자체가 터지면 claude_sources 가 「못 받음」).
    보드 상류가 있으면 거기서 읽는다(/api/board 와 같은 자리를 보게)."""
    name = daily.doc_name(datetime.now(KST).replace(tzinfo=None))
    up = board_upstream_base()
    if up:
        req = urllib.request.Request(up + "/api/board/doc/" + name, headers={"X-KJC-Prio": "low"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = (json.loads(r.read().decode("utf-8")) or {}).get("data")
    else:
        data = docstore.read_doc(name)
    if not isinstance(data, dict) or not data.get("telegram"):
        return {"0건(읽음)": "오늘(%s) 데일리 분석 글이 아직 없습니다" % name[len(daily.DOC_PREFIX):]}
    return {"쓴 시각": data.get("at"), "글": data.get("telegram")}


def _claude_market_news(cfg, ctx):
    rows = news_store.groups(hours=24, limit=CLAUDE_NEWS_MARKET)
    return [{"제목": g.get("title"), "주소": g.get("link"), "갈래": g.get("topicLabel"), "시각": g.get("at"),
             "출처": g.get("source"), "같은 사건 기사 수": g.get("more")} for g in rows]


def _claude_quote(cfg, ctx):
    q = fetch_price(cfg, ctx["code"])
    keep = ("price", "change", "changePct", "open", "high", "low", "volume", "value",
            "marketCap", "per", "pbr", "eps", "bps", "high52", "low52")
    out = {k: q.get(k) for k in keep if q.get(k) is not None}
    if not out:   # 시세는 늘 있어야 한다 — 칸이 다 비어 왔으면 「0건(읽음)」 이 아니라 「못 받음」(2026-11-05)
        raise RuntimeError("시세 칸이 모두 비어 왔습니다")
    return out


def _claude_stock_news(cfg, ctx):
    rows, info = naver.news_related(ctx["code"])   # listed(받는 곳 목록 안 · 밖)는 press_tally 가 이미 붙였다
    if not rows:
        return []   # 빈 것은 claude_sources 가 「0건(읽음)」 으로 적는다
    return {"뉴스": [{k: r.get(k) for k in ("title", "office", "listed", "at", "url")} for r in rows[:CLAUDE_NEWS_STOCK]],
            "출처": "네이버(찾는 길)"}


def _claude_disclosures(cfg, ctx):
    rows = dart.read_disclosures(ctx["code"], CLAUDE_DISCLOSURES)
    return [{k: r.get(k) for k in ("title", "filer", "date", "url")} for r in rows]


CLAUDE_SOURCES = {
    "*":  [("지수(서버가 방금 받은 값)", _claude_indices, False),
           ("오늘 데일리 분석 요약", _claude_daily, False),
           ("지난 24시간 쌓인 시장 뉴스", _claude_market_news, False)],
    "홈": [("보는 종목 시세(서버가 방금 받은 값 · 원)", _claude_quote, True),
           ("보는 종목 뉴스", _claude_stock_news, True),
           ("보는 종목 공시", _claude_disclosures, True)],
}   # (이름, 꺼내는 함수, 국내 종목 코드가 있어야 하나)


def claude_sources(ctx):
    """페이지별 표에서 자료를 골라 {이름: 내용} 으로. 하나가 터져도 나머지는 붙인다."""
    code = str(ctx.get("code") or "").strip()
    has_code = bool(code) and _code_ok(code) and not us_universe.is_us(code)
    try:
        cfg = load_secrets()
    except Exception as e:
        cfg = None
        print("[claude] 열쇠 못 읽음 — %s" % safe_message(e, 80), flush=True)
    out = {}
    for name, fn, need_code in CLAUDE_SOURCES["*"] + CLAUDE_SOURCES.get(str(ctx.get("screen") or ""), []):
        if need_code and not has_code:
            continue
        try:
            v = fn(cfg, dict(ctx, code=code))
            # 읽었는데 0건이면 그렇다고 적는다 — 빈 [] 로는 「없다」 와 「못 읽었다」 를 Claude 가 못 가른다(2026-11-04 qa)
            out[name] = v if v not in ([], {}, None) else {"0건(읽음)": "읽었으나 해당하는 것이 없습니다"}
        except Exception as e:
            out[name] = {"못 받음": safe_message(e, 80)}
            print("[claude] %s 못 붙임 — %s" % (name, safe_message(e, 80)), flush=True)
    return out


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SITE_ROOT, **kwargs)

    def log_message(self, fmt, *args):
        # 정적 파일 요청 로그는 조용히, API 만 표시
        if "/api/" in (self.path or ""):
            sys.stderr.write("  [API] %s %s\n" % (_stamp(), self.path))

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send_body(status, body, "application/json; charset=utf-8")

    def _send_body(self, status, body, ctype, cache="no-store"):
        """본문을 내보낸다 — **받는 쪽이 gzip 을 받으면 줄여서** (2026-11-03 재권님 「종목 클릭하면 5분봉 로딩이
        느린데 이유 찾아봐」 → 「응 해봐」). 서버는 받아 둔 5분봉을 0.02~0.1초에 내는데 외부접속(8764 → Cloudflare →
        기기)에서 2.4~3.1초 걸렸다 — 한 번에 138KB 를 그대로 보냈고 gzip 이면 12.8KB 다(032830 실측).
        `GZIP_MIN` 보다 작으면 줄이지 않는다(줄이는 값보다 머리가 크다). 이미 gzip 인 본문(1f 8b)은 그대로 —
        상류를 부르는 `urllib` 는 gzip 을 청하지 않아 상류 본문은 늘 날것이지만 두 번 싸지 않게 막아 둔다."""
        if (len(body) >= GZIP_MIN and body[:2] != b"\x1f\x8b"
                and "gzip" in (self.headers.get("Accept-Encoding") or "").lower()):
            body = gzip.compress(body, compresslevel=GZIP_LEVEL)
            self.send_response(status)
            self.send_header("Content-Encoding", "gzip")
        else:
            self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Vary", "Accept-Encoding")
        if cache:
            self.send_header("Cache-Control", cache)
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
        """
        if not (self.path or "").startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
            # **Range 없는 응답에도 붙인다.** 브라우저는 이 헤더를 보고서야
            # Range 를 쓴다 — 206 을 낼 수 있어도 알리지 않으면 통째로 받아간다.
            # 한 곳에서 붙여야 `_send_file_ranged` 와 상속본 양쪽에 빠짐이 없다.
            self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    # ── 부분 받기(Range) ───────────────────────────────────────
    #
    # 상속본(`SimpleHTTPRequestHandler`)은 Range 를 **모른다** — 2026-10-02 실측으로
    # `Range: bytes=0-9` 에 200 + 전체 길이를 돌려줬다. 1.5GB 지도 파일에서는
    # 브라우저가 조각만 읽어야 하므로 206 이 필요하다.
    #
    # **단일 범위만 받는다.** 여러 범위(`bytes=0-9,20-29`)는 `multipart/byteranges`
    # 를 만들어야 하는데 PMTiles 는 쓰지 않는다 — 안 쓰는 길을 만들면 그 길만
    # 조용히 썩는다. 여러 범위가 오면 **Range 를 무시하고 통째로** 준다(규격이
    # 허용하는 폴백이다).

    def _parse_range(self, size):
        """`Range` 헤더를 (시작, 끝) 으로. 없으면 `None`, 범위 밖이면 `False`.

        **셋을 가른다** — 없는 것 · 못 읽는 것 · 범위 밖. 하나로 묶으면
        416 을 내야 할 자리에 200 이 나간다.
        """
        raw = (self.headers.get("Range") or "").strip()
        if not raw:
            return None
        if not raw.lower().startswith("bytes=") or "," in raw:
            return None                      # 모르는 형태 · 여러 범위 → 통째로
        spec = raw[6:].strip()
        try:
            if spec.startswith("-"):         # 뒤에서 N 바이트
                n = int(spec[1:])
                if n <= 0:
                    return False
                start, end = max(0, size - n), size - 1
            else:
                a, _, b = spec.partition("-")
                start = int(a)
                end = int(b) if b else size - 1
        except ValueError:
            return None                      # 숫자가 아니다 → 통째로
        if start >= size or start > end:
            return False                     # 416
        return start, min(end, size - 1)

    def _send_file_ranged(self, real, head_only=False):
        """파일 하나를 내준다. `Range` 가 오면 206, 범위 밖이면 416.

        `Accept-Ranges: bytes` 는 `end_headers` 가 붙인다 — 한 곳에서 붙여야
        Range 없는 응답에도 빠지지 않는다(브라우저는 그 헤더를 보고 Range 를 쓴다).
        """
        try:
            size = os.path.getsize(real)
        except OSError:
            self.send_error(404, "Not Found")
            return

        ctype = self.guess_type(real)
        # `.pmtiles` 는 `mimetypes` 가 모른다. 내려받기용 덩어리로 둔다.
        if real.endswith(".pmtiles"):
            ctype = "application/octet-stream"

        rng = self._parse_range(size)
        if rng is False:
            # **범위 밖**이라고 알려 준다. `Content-Range: bytes */크기` 가 규격이다.
            self.send_response(416, "Requested Range Not Satisfiable")
            self.send_header("Content-Range", "bytes */%d" % size)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        try:
            f = open(real, "rb")
        except OSError:
            self.send_error(404, "Not Found")
            return
        with f:
            if rng is None:
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(size))
                self.end_headers()
                if not head_only:
                    shutil.copyfileobj(f, self.wfile)
                return

            start, end = rng
            length = end - start + 1
            self.send_response(206, "Partial Content")
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
            self.send_header("Content-Length", str(length))
            self.end_headers()
            if head_only:
                return
            f.seek(start)
            # 한꺼번에 읽지 않는다 — 1.5GB 파일에서 큰 범위가 오면 메모리로 다 올라온다.
            left = length
            while left > 0:
                chunk = f.read(min(64 * 1024, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def _serve_maps(self, head_only=False):
        """`/maps/…` 를 `MAPS_DIR` 에서 내준다. **저장소 밖이므로 직접 막는다.**

        `_static_block` 은 「저장소 밖이면 거부」 라서 이 길에는 쓸 수 없다.
        대신 같은 방식으로 판정한다 — **합친 뒤 실제 경로로 본다.**
        `..` · `%2e%2e` 같은 우회는 `realpath` 가 정규화하므로 그 결과를 보면
        우회를 따로 막을 필요가 없다.

        디렉터리 목록은 내주지 않는다 — 파일만이다.
        """
        path = (self.path or "")[len(MAPS_URL):]
        path = path.split("?", 1)[0].split("#", 1)[0]
        rel = urllib.parse.unquote(path)
        base = os.path.realpath(MAPS_DIR)
        real = os.path.realpath(os.path.join(base, rel))
        if real != base and not real.startswith(base + os.sep):
            sys.stderr.write("  [차단] %s %s (maps 밖)\n" % (_stamp(), self.path))
            self.send_error(403, "Forbidden")
            return
        # **확장자가 아니면 「없다」 로 답한다.** 403 으로 가르면 「있지만 못 준다」
        # 가 되어 그 자리에 무엇이 있는지 알려 주는 셈이다.
        if not real.lower().endswith(MAPS_EXTS):
            self.send_error(404, "Not Found")
            return
        if not os.path.isfile(real):
            self.send_error(404, "Not Found")
            return
        self._send_file_ranged(real, head_only=head_only)

    def _static_block(self):
        """정적 파일을 막아야 하나. 막으면 이유(영문), 내줘도 되면 `None`.

        **`self.path` 가 아니라 번역된 실제 경로로 판정한다.** `..` ·
        `%2e%2e` 같은 우회는 `translate_path` 가 이미 정규화하므로,
        그 결과를 보면 **우회를 따로 막을 필요가 없다.**

        **상태 줄에 한글을 쓰지 않는다** — latin-1 이라 빈 응답이 나간다
        (`CLAUDE.md` 의 「HTTP 상태 줄에 한글」).
        """
        real = self.translate_path(self.path)
        try:
            rel = os.path.relpath(real, SITE_ROOT)
        except ValueError:
            return "outside"
        if rel == os.pardir or rel.startswith(os.pardir + os.sep):
            return "outside"                      # 저장소 밖

        # ① 먼저 막는다
        for part in rel.split(os.sep):
            low = part.lower()
            if low in _DENY_DIRS:
                return "blocked dir"
            if low in _DENY_NAMES:
                return "blocked name"
            if low.startswith(_DENY_PREFIX):
                return "secret"
            if low.endswith(_DENY_SUFFIX):
                return "blocked type"
        if rel.replace(os.sep, "/").startswith(_DENY_REL):
            return "stored doc"

        # ② 디렉터리는 `index.html` 이 있을 때만 낸다.
        #    ⚠️ **없으면 파일 목록이 나간다** — `assets` · `data` · `partials` ·
        #    `uidata` 가 그 꼴이었다 (2026-09-29 실측).
        if os.path.isdir(real):
            return None if os.path.isfile(os.path.join(real, "index.html")) \
                        else "listing"

        # ③ 그 뒤 허용 확장자만
        if os.path.splitext(rel)[1].lower() in _ALLOW_EXT:
            return None
        return "not served"

    def do_HEAD(self):
        """**GET 만 막으면 샌다.** `do_HEAD` 를 안 덮으면 상속본이 그대로 돌아
        **파일이 있는지와 크기**가 나간다 (2026-09-29 실측 — 이 메서드가 없었다).
        """
        if (self.path or "").startswith(MAPS_URL):
            self._serve_maps(head_only=True)
            return
        if not (self.path or "").startswith(("/api/", "/debugging/")):
            why = self._static_block()
            if why:
                self.send_error(403, "Forbidden")
                return
        super().do_HEAD()

    def do_GET(self):
        if (self.path or "").startswith("/api/kis/"):
            _mark_ui_call(self.path)   # 양보 + **어느 종목인지** 적는다
            # ⓒ 스레드는 요청마다 새로 서지만 표시는 매번 덮어써 둔다
            _prio.low = (self.headers.get(PRIO_HEADER) or "").strip().lower() == "low"
            if not _prio.low:
                global _last_high_at
                _last_high_at = time.monotonic()
            self._handle_kis()
            return
        if (self.path or "").startswith("/api/dart/"):
            self._handle_dart()
            return
        if (self.path or "").startswith("/api/news/"):
            self._handle_news()
            return
        if (self.path or "").startswith("/api/naver/"):
            _mark_ui_call(self.path)   # 화면이 보고 있다는 신호는 여기서도
            self._handle_naver()
            return
        if (self.path or "").startswith("/api/board/"):
            self._handle_board()
            return
        if (self.path or "").startswith("/api/toss/"):
            self._handle_toss()
            return
        if (self.path or "").startswith("/api/macro/"):
            self._handle_macro()
            return
        if urllib.parse.urlparse(self.path or "").path.rstrip("/") == "/api/telegram/today":
            # 그날 텔레그램 글 — 보냄 · 꺼짐 · 조용한 시간 · 실패를 보낸 순서로(데일리분석 모달의 「데일리분석」 칸)
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            day = (q.get("day") or [""])[0].strip()
            if day and not (day.isdigit() and len(day) == 8):
                self._send_json({"ok": False, "error": "day 는 YYYYMMDD 여덟 자리입니다."}, 400)
                return
            rows, meta = tglog.today(day or None)
            self._send_json({"ok": True, "data": rows, "meta": meta})
            return
        if urllib.parse.urlparse(self.path).path.rstrip("/") in ("/api/nxt/flow", "/api/nxt/themes"):
            # 실시간 순위 「테마」(server/theme_flow.py) — flow: 수급(넥스트 5분 거래량 2배) · themes: 큰 테마별 작은 테마(네이버 264)
            try:
                if self.path.split("?")[0].rstrip("/").endswith("/flow"):
                    self._send_json({"ok": True, "data": theme_flow.flow(sys.modules[__name__]), "meta": theme_flow.status(sys.modules[__name__])})
                else:
                    self._send_json({"ok": True, "data": theme_flow.big(), "meta": {"source": "네이버 · 큰 테마는 이름 낱말로 나눔(theme_flow.BIG)"}})
            except Exception as e:
                self._send_json({"ok": False, "error": safe_message(e, 160)}, 502)
            return
        if urllib.parse.urlparse(self.path).path.rstrip("/") == "/api/good-news":
            # 「좋은 뉴스」 판정(server/good_news.py) — 쌓인 공시를 부를 때마다 투자전략 칸(newsPreDays · newsMinSizePct)으로 판정 · OpenDART 를 안 부른다
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                days = int((q.get("days") or [good_news.DAYS_DEFAULT])[0])
            except ValueError:
                self._send_json({"ok": False, "error": "days 는 1~%d 정수입니다." % good_news.DAYS_MAX}, 400)
                return
            code = (q.get("code") or [""])[0].strip()
            if code and not re.fullmatch(r"[0-9A-Z]{6}", code):
                self._send_json({"ok": False, "error": "code 는 종목코드 여섯 자입니다."}, 400)
                return
            try:
                self._send_json({"ok": True, "data": good_news.compute(sys.modules[__name__], days, code or None), "meta": good_news.status()})
            except Exception as e:
                self._send_json({"ok": False, "error": safe_message(e, 160)}, 502)
            return
        if urllib.parse.urlparse(self.path).path.rstrip("/") == "/api/auto-watch/history":
            # 자동 관심종목 다음날 결과(server/auto_watch.py history) — 걸린 날마다 종목 · 다음 거래일 등락 · 모은 값 · KIS 를 안 부른다
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                days = int((q.get("days") or ["30"])[0])
                if not 1 <= days <= 120:
                    raise ValueError
            except ValueError:
                self._send_json({"ok": False, "error": "days 는 1~120 정수입니다."}, 400)
                return
            try:
                self._send_json({"ok": True, "data": auto_watch.history(sys.modules[__name__], days)})
            except Exception as e:
                self._send_json({"ok": False, "error": safe_message(e, 160)}, 502)
            return
        if urllib.parse.urlparse(self.path).path.rstrip("/") == "/api/watch-log":
            # 종목 기록(server/watch_log.py) — 그날 관심 · 자동 · VI · 급등 · 매수 종목의 전일비 · 프리 · 정규 · 애프터 · 5분봉 · KIS 를 안 부른다
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            day = (q.get("day") or [""])[0]
            if day and not (day.isdigit() and len(day) == 8):
                self._send_json({"ok": False, "error": "day 는 YYYYMMDD 입니다."}, 400)
                return
            try:
                self._send_json({"ok": True, "data": watch_log.board(sys.modules[__name__], day or None),
                                 "meta": dict(watch_log.status(), unit="%",
                                              note="pct 전일비(전일 일봉 종가 → 마지막 5분봉) · pre 프리장(전일 종가 → 08:55 봉) · reg 정규장(프리장 끝 → 15:30 봉) · "
                                                   "aft 애프터(정규장 끝 → 마지막) · 봉이 없으면 null · line 은 [HHMM, 종가] 5분봉 · saved false 면 지금 DB 로 셈")})
            except Exception as e:
                self._send_json({"ok": False, "error": safe_message(e, 160)}, 502)
            return
        if urllib.parse.urlparse(self.path).path.rstrip("/") == "/api/auto-watch":
            # 자동 관심종목(server/auto_watch.py) — 쌓인 값을 부를 때마다 투자전략 룰(strategy-rules)로 거르고 줄 세운다 · KIS 를 안 부른다
            try:
                self._send_json({"ok": True, "data": auto_watch.compute(sys.modules[__name__]), "meta": auto_watch.status(sys.modules[__name__])})
            except Exception as e:
                self._send_json({"ok": False, "error": safe_message(e, 160)}, 502)
            return
        if urllib.parse.urlparse(self.path).path.rstrip("/") == "/api/nxt/board":
            # 넥장 보드(Insight 「투자 전략」) — 날마다 종가 · 장외 · 프리장 · 야간선물 · 장외 오름 · 내림 상위(server/nxt_board.py)
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            market = (q.get("market") or ["kospi"])[0]
            if market not in ("kospi", "kosdaq"):
                self._send_json({"ok": False, "error": "market 은 kospi · kosdaq 둘입니다."}, 400)
                return
            try:
                days = int((q.get("days") or ["5"])[0])
            except ValueError:
                days = 5
            self._send_json({"ok": True, "data": nxt_board.board(sys.modules[__name__], market, days),
                             "meta": nxt_board.status()})
            return
        if (self.path or "").rstrip("/") == "/api/nxt-pre/status":
            # 장 전 거래량 2배 바퀴의 상태 — 마지막으로 돈 날 · 종목 수 · 2배 수 · 꺼져 있으면 보냈을 글(preview)
            st = nxt_pre.status()
            if not st.get("lastRunAt"):
                st["note"] = "아직 안 돌았습니다 — 보내는 서버(메인 %d)에서 평일 08:51 에 돕니다" % MAIN_PORT
            self._send_json({"ok": True, "data": st})
            return
        if (self.path or "").rstrip("/") == "/api/alerts/status":
            # 장중 알림 바퀴(상승 VI · +20% 급등) — 오늘 몇 건 · 몇 통 · 꺼져 있으면 보냈을 글(preview). 보내는 서버에서만 돈다
            st = intraday_alerts.status()
            if not st.get("startedAt"):
                st["note"] = "이 서버에서는 장중 알림 바퀴가 안 돕니다 — 보내는 서버(메인 %d)에서만 돕니다" % MAIN_PORT
            self._send_json({"ok": True, "data": st})
            return
        if urllib.parse.urlparse(self.path or "").path.rstrip("/") == "/api/alerts/market-hours":
            # 장 시각 한 곳 — 오늘 열리나 · 몇 시에 열고 닫나 · 앞날 쉬는 날 · 바뀐 날 · 거래소 공시 거래시간 글. 휴장일 표는 개발 DB 라 어느 서버든 같다
            try:
                self._send_json({"ok": True, "data": market_hours.board(sys.modules[__name__]), "meta": market_hours.status()})
            except Exception as e:
                self._send_json({"ok": False, "error": safe_message(e, 160)}, 502)
            return
        if urllib.parse.urlparse(self.path or "").path.rstrip("/") == "/api/alerts/market-event":
            # 서킷브레이커(추정 · 거래소 공시로 확인) — 홈 맨 위 띠. 바퀴는 보내는 서버에서만 돌고 사건은 개발 DB 표라 어느 서버든 같은 것을 읽는다
            try:
                self._send_json({"ok": True, "data": market_event.board(sys.modules[__name__]), "meta": market_event.status()})
            except Exception as e:
                self._send_json({"ok": False, "error": safe_message(e, 160)}, 502)
            return
        if urllib.parse.urlparse(self.path or "").path.rstrip("/") == "/api/alerts/today":
            # 그날 본 상승 VI · +20% 급등 목록 — 홈 「오늘 VI · 급등」 칸(2026-11-06). 바퀴는 보내는 서버에서만 돌고
            # 목록은 개발 DB(sync_meta)에 있어 **어느 서버든 같은 것을 읽는다**(intraday_alerts.today)
            self._send_json({"ok": True, "data": intraday_alerts.today()})
            return
        if urllib.parse.urlparse(self.path or "").path.rstrip("/") == "/api/signals/today":
            # 그날 걸린 바닥 신호(볼린저 하단 · MACD 매도세 줄어듦 · RSI 30 위로 — 같은 봉) — 홈 실시간 순위 「볼린저」 칸(2026-11-09).
            # 판정 · 기록은 보내는 서버의 신호 바퀴가 하고 기록은 DB 라 어느 서버든 읽는다(signal_watch.today_lows)
            self._send_json({"ok": True, "data": signal_watch.today_lows(sys.modules[__name__])})
            return
        if (self.path or "").rstrip("/") == "/api/events/status":
            # 결과 알림 바퀴의 상태 — 무엇을 기다리나 · 꺼져 있으면 보냈을 글(preview). 바퀴는 보내는 서버에서만 돈다
            st = events.status()
            if not st.get("startedAt"):
                st["note"] = "이 서버에서는 결과 알림 바퀴가 안 돕니다 — 보내는 서버(메인 %d)에서만 돕니다" % MAIN_PORT
            self._send_json({"ok": True, "data": st})
            return
        if (self.path or "").startswith("/api/market/"):
            self._handle_market()
            return
        if (self.path or "").startswith("/debugging/"):
            self._handle_debugging()
            return

        # 지도는 **저장소 밖**이라 `_static_block` 앞에서 가른다 (2026-10-02).
        if (self.path or "").startswith(MAPS_URL):
            self._serve_maps()
            return

        # ⚠️ 여기부터가 정적 파일이다. **저장소 전체를 내주지 않는다.**
        why = self._static_block()
        if why:
            sys.stderr.write("  [차단] %s %s (%s)\n"
                             % (_stamp(), self.path, why))
            self.send_error(403, "Forbidden")
            return

        # `Range` 가 오면 가로챈다. **없으면 상속본에 맡긴다** — 디렉터리 목록 ·
        # `index.html` 찾기 · 304 를 다시 쓰지 않는다. 가로채는 길이 좁을수록
        # 멀쩡히 돌던 것이 안 깨진다.
        if self.headers.get("Range"):
            real = self.translate_path(self.path)
            if os.path.isfile(real):
                self._send_file_ranged(real)
                return
        super().do_GET()

    def _kis_route_via_upstream(self, base):
        """화면 API 하나를 상류에 그대로 넘긴다. **보냈으면 `True`, 폴백이면 `False`.**

        상류가 안 떠 있거나 `5xx` · `404`(받을 자리 없음)면 `False` 를 내어
        **직접 부르는 쪽으로 내려간다** — `_kis_via_upstream` 과 같은 선이다.
        """
        try:
            _req = urllib.request.Request(base + (self.path or ""))
            if SLOW:
                _req.add_header(PRIO_HEADER, "low")     # ⓒ 외부접속에 비켜선다
            with urllib.request.urlopen(_req, timeout=15) as resp:
                code, body = resp.getcode(), resp.read()
                rct = resp.headers.get("Content-Type")
        except urllib.error.HTTPError as e:
            if e.code >= 500 or e.code == 404:
                _up_stat["routeFallbacks"] += 1
                _up_stat["lastError"] = "상류 %s" % e.code
                return False
            code, body, rct = e.code, e.read(), e.headers.get("Content-Type")
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            # `HTTPException` — 상류가 응답 중간에 끊기면(`IncompleteRead`) 이것이
            # 난다. `OSError` 가 아니라 안 잡으면 화면에 응답 없이 끊긴다 (창구 검수).
            _up_stat["routeFallbacks"] += 1
            _up_stat["lastError"] = safe_message(e)
            return False
        _up_stat["routeCalls"] += 1
        self._send_body(code, body, rct or "application/json; charset=utf-8", cache=None)
        return True

    def _board_via_upstream(self, base):
        """보드를 상류에 **그대로** 넘긴다 — 경로 · 본문 · 상태코드 그대로.

        ⚠️ **폴백을 두지 않는다. KIS 와 다른 자리다.**

            KIS    상류가 죽으면 **직접 부른다** — 같은 시세를 두 곳에서
                   받아도 **값이 같다.** 읽기다
            보드   **쓰는 곳**이다. 상류가 죽었다고 로컬에 쓰면
                   **보드가 두 곳으로 갈린다** — 한쪽에 적은 카드가
                   다른 쪽에 없고, 나중에 어느 쪽이 맞는지 못 가린다

        **GET 도 로컬 사본으로 떨어지지 않는다.** 옛 보드를 「지금」 으로
        보게 되고, **그것을 보고 쓰면 남의 것을 덮는다.**

        **「KIS 에는 폴백이 있는데 왜 여기는 없나」 로 넣지 말 것.**
        넣는 순간 위의 갈라짐이 돌아온다.

        **상태코드를 그대로 내려보낸다.** `409`(그 사이 남이 썼다)가
        화면에 닿아야 `if_updated_at` 견주기가 뜻을 갖는다 — 200 으로
        바꿔 싣거나 500 으로 뭉개면 **덮어쓰기 막기가 그 자리에서 풀린다.**
        """
        raw = b""
        if self.command in ("PUT", "POST"):
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        req = urllib.request.Request(base + (self.path or ""),
                                     data=raw if self.command in ("PUT", "POST") else None,
                                     method=self.command)
        ct = self.headers.get("Content-Type")
        if ct:
            req.add_header("content-type", ct)
        ek = self.headers.get(edit_key.HEADER)       # 수정 비밀번호 — 판정은 상류(8765) 한 곳에서(잠금 셈이 한 곳에 모인다)
        if ek:
            req.add_header(edit_key.HEADER, ek)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                code, body = resp.getcode(), resp.read()
                rct = resp.headers.get("Content-Type")
        except urllib.error.HTTPError as e:
            # **`409` · `400` 도 응답이다.** 그대로 내려보낸다.
            code, body, rct = e.code, e.read(), e.headers.get("Content-Type")
            if code >= 500:
                _board_stat["errors"] += 1
                _board_stat["lastError"] = "상류 %s" % code
        except (urllib.error.URLError, OSError) as e:
            # **폴백하지 않는다.** 무엇을 켜야 하는지 적어 준다 —
            # 「로컬 사본을 주느니 안 떠 있다고 말하는 편이 낫다」.
            _board_stat["errors"] += 1
            _board_stat["lastError"] = safe_message(e)
            self._send_json({
                "ok": False,
                "error": "보드 상류가 안 떠 있습니다. 8765(holdings 미리보기)를 켜 주십시오.",
                "upstreamDown": True,
            }, status=503)
            return
        _board_stat["calls"] += 1
        self._send_body(code, body, rct or "application/json; charset=utf-8", cache=None)

    def _handle_board(self):
        """문서 저장 — 보드 셋 · AI 분석 · 데일리분석이 함께 쓴다.

        **옛 배포본 워커(`board-api.js` · 2026-10-06 에 지움 — `git log -- projects/worker`)를 그대로 흉내 낸다.**
        `CLAUDE.md` 가 그렇게 정해 뒀다 — 맥미니 서버가 나중에 같은 모양으로
        응답하면 화면은 한 줄도 안 고치고 주소만 바꾸면 된다.

            GET  /api/board/health          살아 있나
            GET  /api/board/doc/<이름>      읽기
            PUT  /api/board/doc/<이름>      쓰기  {"data": …}

        **워커와 다른 것 하나** — 그쪽은 Access 로 사람을 가려 `owner` 별로
        나눠 담는다. 이 서버는 재권님 PC 안에서만 돌아 가릴 사람이 없다.
        그래서 `owner` 를 안 쓰고 응답에도 안 싣는다.
        """
        # ── 상류가 있으면 보드를 통째로 넘긴다 (2026-10-01) ──
        _b = board_upstream_base()
        if _b:
            self._board_via_upstream(_b)
            return

        path = (self.path or "").split("?", 1)[0].rstrip("/")

        if path == "/api/board/edit-check":
            # 수정 비밀번호가 맞는지만 묻는다(edit_key.py). json 만 받는다 — 다른 출처 페이지는 미리 묻기에서 막힌다(claude 묻기와 같은 까닭)
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if self.command != "POST" or (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
                self._send_json({"ok": False, "error": "POST · application/json 으로 보내 주십시오."}, status=405)
                return
            try:
                doc = (json.loads(raw.decode("utf-8") or "{}") or {}).get("doc")
            except Exception:
                doc = None
            if doc not in edit_key.PROTECTED:
                self._send_json({"ok": False, "error": "수정 비밀번호로 지키는 문서가 아닙니다."}, status=400)
                return
            ok, why, locked = edit_key.check(self.headers.get(edit_key.HEADER))
            self._send_json({"ok": True} if ok else {"ok": False, "error": why, "locked": locked}, status=200 if ok else 403)
            return

        if path == "/api/board/health":
            self._send_json({
                "ok": True,
                "root": docstore.DOC_ROOT,
                "docs": len(docstore.list_docs()),
                # **돌고 있나를 눈으로 보는 자리** (2026-10-01). 저장본을
                # git 으로 남기는데, 켜졌는지·쌓이는지를 여기서 본다.
                # 주소나 문서 이름은 안 낸다 — 켜짐 여부와 개수만이다.
                "git": docstore.git_status(),
                # 카드에 붙이는 파일의 한도 · 종류 — 화면이 이 값을 받아 쓴다(「캐시·주기·한도 값을 화면에 박지 않는다」)
                "fileMaxBytes": docstore.FILE_MAX_BYTES,
                "fileTypes": sorted(docstore.FILE_TYPES),
            })
            return

        # ── 카드에 붙인 파일 (2026-11-07 · docstore 「카드에 붙인 파일」) ──
        #   PUT /api/board/file            본문이 파일 그대로 · Content-Type 이 종류  → {"ok", "id", "url", "size"}
        #   GET /api/board/file/<id>        그 파일(한 번 넣으면 안 바뀌어 오래 받아 둔다)
        if path == "/api/board/file":
            n = int(self.headers.get("Content-Length") or 0)
            if self.command != "PUT":
                self._send_json({"ok": False, "error": "파일은 PUT 으로 보내 주십시오."}, status=405)
                return
            if n > docstore.FILE_MAX_BYTES:
                left = n
                while left > 0:                       # 큰 본문도 비우고 답한다(안 읽으면 보내는 쪽 연결이 깨진다)
                    chunk = self.rfile.read(min(left, 1 << 20))
                    if not chunk:
                        break
                    left -= len(chunk)
                self._send_json({"ok": False, "error": "파일이 %dMB 보다 큽니다."
                                 % (docstore.FILE_MAX_BYTES // (1024 * 1024))}, status=413)
                return
            raw = self.rfile.read(n)
            try:
                fid = docstore.save_file(raw, self.headers.get("Content-Type"))
            except docstore.FileRefused as e:
                self._send_json({"ok": False, "error": str(e)}, status=e.status)
                return
            except OSError as e:
                self._send_json({"ok": False, "error": safe_message(e)}, status=500)
                return
            self._send_json({"ok": True, "id": fid, "url": "/api/board/file/" + fid, "size": len(raw)})
            return
        m = re.match(r"^/api/board/file/([^/]+)$", path)
        if m:
            fp = docstore.file_path(urllib.parse.unquote(m.group(1)))
            if not fp:
                self._send_json({"ok": False, "error": "그런 파일이 없습니다."}, status=404)
                return
            with open(fp, "rb") as f:
                data = f.read()
            self._send_body(200, data, docstore.file_type(fp), cache="private, max-age=31536000, immutable")
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
                # **`updatedAt` 을 함께 낸다** (2026-09-30). 워커가 이미
                # 그 모양이고(옛 워커 `board-api.js`), 화면은 이것을 들고 있다가
                # PUT 에 돌려보내 **그 사이 남이 썼는지**를 가린다.
                data = docstore.read_doc(name)
                self._send_json({"ok": True, "doc": name, "data": data,
                                 "updatedAt": docstore.doc_updated_at(name)})
                return

            if self.command == "PUT":
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if name in edit_key.PROTECTED:
                    # 재권님만 고치는 문서 — 머리글 수정 비밀번호가 맞을 때만 쓴다(edit_key.py · 2026-11-11)
                    ok, why, locked = edit_key.check(self.headers.get(edit_key.HEADER))
                    if not ok:
                        self._send_json({"ok": False, "error": why, "locked": locked}, status=403)
                        return
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

                # **내가 읽은 뒤에 남이 썼나** (2026-09-30).
                #
                # 보드를 여러 세션이 동시에 쓰는데 저장이 **문서를 통째로
                # 덮는다.** 읽고 쓰는 사이에 남이 쓰면 **그 사람 것이 조용히
                # 사라진다** — `d0b0b24`(카드 끌기)로 **순서를 바꿀 때마다**
                # 전체를 PUT 하게 되면서 위험이 커졌다.
                #
                # **안 보내면 안 견준다.** 화면이 아직 안 고쳐진 동안에도
                # 보드는 돌아야 한다 — 「늘 막는 검사는 검사가 아니다」 와
                # 같은 자리다.
                try:
                    wrote = docstore.write_doc(name, body["data"], history=keep,
                                               if_updated_at=body.get("updatedAt"))
                except docstore.DocConflict as e:
                    # **`updatedAt` 만 준다. 데이터는 안 싣는다.**
                    # 화면은 그것으로 **「내가 낡았다」 를 알 뿐**이고
                    # **합치려면 다시 GET 해야 한다.**
                    #
                    # 전체를 실으면 무겁고, **그 순간 값이라 받아서 합치는
                    # 사이 또 낡는다** — 여러 세션이 초 단위로 쓴다.
                    # **다시 GET 이 그때의 최신**을 준다.
                    #
                    # ⚠️ **얼마 뒤 다시 하라는 값을 여기 넣지 않는다.**
                    # 그것을 응답에 박으면 화면이 그 숫자를 따르게 되어
                    # 「캐시·주기·한도 값을 화면에 박지 않는다」 를 반대쪽에서
                    # 어긴다. **무엇이 어긋났는지만 알린다.**
                    self._send_json({"ok": False, "doc": name,
                                     "error": "그 사이에 남이 썼습니다. 다시 읽고 쓰십시오.",
                                     "conflict": True,
                                     "updatedAt": e.current},
                                    status=409)
                    return

                # **「안 썼다」 를 조용히 넘기지 않는다.** 빈 것을 보냈는데
                # ok: true 만 오면 저장된 줄 안다.
                self._send_json({"ok": True, "doc": name, "wrote": wrote,
                                 "skipped": None if wrote else "빈 내용이라 쓰지 않았습니다",
                                 "updatedAt": docstore.doc_updated_at(name)})
                return

            self._send_json({"ok": False, "error": "GET 또는 PUT 만 됩니다."}, status=405)
        except docstore.DocNameError as e:
            self._send_json({"ok": False, "error": str(e)}, status=400)
        except Exception as e:
            # 경로에 이름이 섞여 있을 수 있어 종류만 올린다
            self._send_json({"ok": False, "error": "저장하지 못했습니다 (%s)" % type(e).__name__},
                            status=500)

    def do_POST(self):
        """POST 는 Claude 창 하나뿐이다 — 물음 · 앞 대화가 길어 주소(GET)에 못 싣는다 (2026-11-03 · server/claude_chat.py)."""
        if urllib.parse.urlparse(self.path or "").path.rstrip("/") == "/api/claude/ask":
            self._handle_claude_ask()
            return
        if urllib.parse.urlparse(self.path or "").path.rstrip("/") == "/api/board/edit-check":
            self._handle_board()          # 수정 비밀번호 맞는지 묻기 — 보드 길이라 세션 서버는 8765 로 넘긴다(edit_key.py)
            return
        try:
            self.rfile.read(int(self.headers.get("Content-Length") or 0))   # 딸려 온 본문을 먼저 비운다(아래 do_PUT 주석)
        except Exception:
            pass
        self._send_json({"ok": False, "error": "POST 는 /api/claude/ask · /api/board/edit-check 에만 됩니다."}, 405)

    def _handle_claude_ask(self):
        """화면이 보낸 물음 · 보는 것 · 앞 대화에 **서버 자료**(페이지별 표 CLAUDE_SOURCES)를 붙여 claude 에 묻는다.
        숫자는 화면 것을 옮기지 않고 서버 것을 쓴다 — 화면이 주면 두 벌이 된다. 못 받은 자료는 「못 받음」 으로 붙인다.

        **본문 종류가 application/json 이 아니면 415 로 돌려보낸다** (2026-11-03 개념정의 검수 권고) — text/plain 은 브라우저의
        「단순 요청」 이라 맥미니에서 연 아무 웹페이지가 미리 묻기(preflight) 없이 여기로 보내 claude 를 돌릴 수 있다(답은 못 읽어도
        돈은 나간다). json 만 받으면 다른 출처는 미리 묻기에 걸리고, 이 서버는 OPTIONS 에 허용을 안 주므로 거기서 막힌다."""
        if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
            try:
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
            except Exception:
                pass
            self._send_json({"ok": False, "error": "본문은 application/json 이어야 합니다."}, 415)
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 64 * 1024:
                raise ValueError("본문이 너무 큽니다")
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
            if not isinstance(body, dict):
                raise ValueError("본문은 JSON 한 덩어리여야 합니다")
        except Exception as e:
            self._send_json({"ok": False, "error": safe_message(e, 120)}, 400)
            return
        ctx = body.get("context") if isinstance(body.get("context"), dict) else {}
        try:
            claude_chat.precheck(body.get("question"))   # 거절될 물음이면 자료를 꺼내기 전에 돌려보낸다(2026-11-04 qa)
        except ValueError as e:
            self._send_json({"ok": False, "error": safe_message(e, 120)}, 400)
            return
        except claude_chat.Busy as e:
            self._send_json({"ok": False, "error": str(e)}, 429)
            return
        sources = claude_sources(ctx)   # 페이지별 표(CLAUDE_SOURCES)로 고른 서버 자료 — 2026-11-04
        try:
            data = claude_chat.ask(body.get("question"), ctx, body.get("history"), sources)
        except ValueError as e:
            self._send_json({"ok": False, "error": safe_message(e, 120)}, 400)
            return
        except claude_chat.Busy as e:
            self._send_json({"ok": False, "error": str(e)}, 429)
            return
        except Exception as e:
            self._send_json({"ok": False, "error": safe_message(e, 160)}, 502)
            return
        data["sources"] = [k for k, v in sources.items() if not (isinstance(v, dict) and "못 받음" in v)]
        self._send_json({"ok": True, "data": data})

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
    #   issues  경제지 RSS · 주제어별 · 원문 링크 있음 (구글 뉴스는 막혀 2026-09-15 에 바꿨다)
    #   moves   KIS news-title · 종목코드 붙음 · 링크 없음
    # ── 네이버 업종 · 테마 (2026-09-18) ──
    #
    # 「지금 뜨는 산업」 이 쓴다. KIS 에 없는 둘 때문에 여기서 받는다 —
    # 업종 안에서 몇이 오르내렸는지, 그리고 그 업종의 종목 목록이다.
    # 자세한 것은 server/naver.py 머리글과 docs/sector-sources.md 에 있다.
    def _handle_toss(self):
        """토스증권 — 연결 확인 · 1분봉 (2026-10-07 · 10-08). 토큰은 보내는 서버(8765)만 받는다 — toss.py 머리 주석.

        8765 가 아닌 서버는 1분봉을 KIS 와 같은 상류(`KJC_KIS_UPSTREAM`)로 넘긴다 — 토스를 직접 부르지 않는다.
        """
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path[len("/api/toss/"):].strip("/")
        main_ok = is_sender(self.server.server_address[1])
        if route == "health":
            r = toss.health(main_ok)
            self._send_json(r, 200 if r.get("ok") or r.get("connected") is None else 502)
            return
        if route != "candles":
            self._send_json({"ok": False, "error": "없는 주소입니다 — /api/toss/health · /api/toss/candles 둘입니다."}, 404)
            return
        if not toss.can_call(main_ok):
            self._toss_forward()
            return
        qs = urllib.parse.parse_qs(parsed.query)
        q = lambda k: (qs.get(k) or [""])[0].strip()
        symbol = toss.check_symbol(q("symbol"))
        interval = q("interval") or "1m"
        date = q("date")
        if not symbol:
            self._send_json({"ok": False, "error": "symbol 이 없거나 모양이 다릅니다 — 국내 005930 · 미국 AAPL · BRK.B"}, 400)
            return
        if interval != "1m":
            self._send_json({"ok": False, "error": "interval 은 1m 하나만 받습니다"}, 400)
            return
        if date and not (re.fullmatch(r"\d{8}", date) and _valid_ymd(date)):
            self._send_json({"ok": False, "error": "date 는 YYYYMMDD(한국시각 날짜)입니다"}, 400)
            return
        t0 = time.time()
        try:
            if date:
                bars, calls = toss.candles_day(symbol, date)
                nb = None
            else:
                try:
                    count = int(q("count") or 200)
                except ValueError:
                    count = 200
                bars, nb, calls = toss.minutes(symbol, q("before") or None, count)
        except Exception as e:
            self._send_json({"ok": False, "symbol": symbol, "interval": interval,
                             "error": toss._hide(e), "source": "toss"}, 502)
            return
        self._send_json({"ok": True, "symbol": symbol, "interval": interval, "date": date or None,
                         "candles": bars, "nextBefore": nb, "calls": calls,
                         "ms": int((time.time() - t0) * 1000), "source": "toss"})

    def _toss_forward(self):
        """토스 1분봉을 상류(8765)에 넘긴다. 상류가 없으면 「여기서는 안 부른다」 를 낸다 — 폴백하지 않는다
        (직접 부르면 토큰을 새로 받아 8765 토큰이 끊긴다)."""
        self._relay_upstream("토스는 8765 에서만 부릅니다", "toss")

    def _handle_macro(self):
        """경제 지표(ECOS · FRED) — server/macro.py 머리 주석. 상류가 있는 서버(메인 8764 · 세션)는 8765 로 넘기고,
        8765 에 못 닿거나 8765 가 이 주소를 모르면 그때만 자기가 받는다(2026-11-05 · 시장지표와 같은 꼴 — 그 전에는 키가 있는 서버마다 따로 받아
        메인이 12~14초 기다렸다)."""
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path[len("/api/macro/"):].strip("/")
        if route not in ("regime", "series", "releases", "calendar"):
            self._send_json({"ok": False, "error": "없는 주소입니다 — /api/macro/regime · /api/macro/series?ids= · /api/macro/releases · /api/macro/calendar 넷입니다."}, 404)
            return
        if route == "calendar":
            # 일정 파일 + 한국 시각 — 키가 필요 없어 어느 서버든 자기 파일로 낸다(macro.calendar · 2026-10-26)
            r = macro.calendar()
            self._send_json(r, 200 if r.get("ok") else 500)
            return
        base = upstream_base()
        if base:
            try:
                with urllib.request.urlopen(base + self.path, timeout=UPSTREAM_TIMEOUT) as resp:
                    status, body = resp.status, resp.read()
            except urllib.error.HTTPError as e:
                status, body = e.code, e.read()
            except (urllib.error.URLError, OSError):
                status, body = None, b""     # 8765 에 못 닿음 — 아래에서 자기가 받는다
            # 상류가 이 주소를 모른다(옛 코드 404 · JSON 아닌 403) · 못 닿았다 — 그때만 여기서 받는다
            if status is not None and not (status == 404 or (status == 403 and not body.lstrip().startswith(b"{"))):
                self._send_body(status, body, "application/json; charset=utf-8")
                return
            if not macro.ecos_key():
                self._send_json({"ok": False, "error": "상류(8765)에 못 닿았고 이 서버에는 경제 지표 키(ecos)가 없습니다", "source": "macro"}, 502)
                return
        if route == "regime":
            r = macro.regime()
        elif route == "releases":
            r = macro.releases()
        else:
            ids = (urllib.parse.parse_qs(parsed.query).get("ids") or [""])[0]
            want = [i.strip() for i in ids.split(",") if i.strip()]
            if not want:
                self._send_json({"ok": False, "error": "ids 가 비었습니다 — 예: ?ids=kr_cpi,us_unrate",
                                 "known": macro.ALL_IDS}, 400)
                return
            r = macro.pick(want)
        self._send_json(r, 200 if r.get("ok") else 502)

    def _handle_market(self):
        """시장지표(네이버) — server/market_index.py 머리 주석. 상류가 있는 서버는 넘긴다(받는 것은 8765 한 곳).

        상류가 이 주소를 아직 모르면(새 코드로 재시작 전 — 옛 8765 는 JSON 이 아닌 403 을 낸다 · 2026-10-12 실측) 그때만 여기서 받는다 — 확인용 서버가 새 코드를
        재시작 전에 볼 수 있게. 토스처럼 토큰을 끊는 일이 없어 이 폴백은 해가 없다. 응답 `servedBy` 가 어디서 받았나다."""
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path[len("/api/market/"):].strip("/")
        if route not in ("indicators", "indicator", "materials", "crypto", "us-outlook", "fear-greed"):
            self._send_json({"ok": False, "error": "없는 주소입니다 — /api/market/indicators · /api/market/indicator?key= · /api/market/materials · /api/market/crypto · /api/market/us-outlook · /api/market/fear-greed?key= 여섯입니다."}, 404)
            return
        base = upstream_base()
        if base:
            try:
                with urllib.request.urlopen(base + self.path, timeout=UPSTREAM_TIMEOUT) as resp:
                    status, body = resp.status, resp.read()
            except urllib.error.HTTPError as e:
                status, body = e.code, e.read()
            except (urllib.error.URLError, OSError) as e:
                self._send_json({"ok": False, "error": "상류(8765)에 못 닿았습니다 — %s" % safe_message(e),
                                 "source": "market"}, 502)
                return
            # 상류가 이 주소를 모른다 — 옛 코드는 JSON 아닌 403, 주소 일부만 아는 코드는 404(「없는 주소」). 아는 주소는 404 를 안 낸다
            # 지표 key 를 상류가 모르면 400(「모르는 지표」) — 새로 더한 key(가상자산 등)를 상류 재시작 전에 볼 수 있게 그때도 여기서 받는다
            if not (status == 404 or (status == 403 and not body.lstrip().startswith(b"{"))
                    or (status == 400 and route == "indicator")):
                self._send_body(status, body, "application/json; charset=utf-8")
                return
        if route == "indicators":
            r = market_index.indicators()
        elif route == "materials":
            r = market_index.materials()
        elif route == "crypto":
            r = crypto.items()
        elif route == "us-outlook":
            r = us_outlook.outlook()
        elif route == "fear-greed":           # 공포·탐욕 지수(server/fear_greed.py) — key KOSPI · 005930 · 000660 · 일봉 · 쌓인 수급으로 셈 · KIS 를 새로 안 부른다
            key = (urllib.parse.parse_qs(parsed.query).get("key") or ["KOSPI"])[0].strip().upper()
            r = dict(fear_greed.all_targets(sys.modules[__name__], key), meta=fear_greed.status())
            r["ok"] = bool(r["data"].get("ready"))
        else:
            key = (urllib.parse.parse_qs(parsed.query).get("key") or [""])[0].strip()
            # 가상자산 종목도 같은 주소로 일봉을 낸다 — 큰 차트가 한 길로 그리게(응답 모양이 같다)
            r = crypto.indicator(key) if key in crypto.BY_KEY else market_index.indicator(key)
            if r is None:
                self._send_json({"ok": False, "error": "모르는 지표입니다 — key 는 %s 중 하나입니다."
                                 % " · ".join([i["key"] for i in market_index.ITEMS] + [i["key"] for i in crypto.ITEMS])}, 400)
                return
        r["servedBy"] = "상류에 아직 없어 여기서" if base else "여기서"
        # 날짜별 값이 원래 없는 지표(`absent` · 나라별 기준금리 등)는 고장이 아니다 — 502 로 내면 F12 에 서버가 터진 것처럼 보였다(qa 10-14)
        self._send_json(r, 200 if (r.get("ok") or r.get("absent")) else 502)

    def _relay_upstream(self, why, source):
        """이 요청을 그대로 상류(`KJC_KIS_UPSTREAM`)에 넘기고 받은 것을 내려보낸다. 상류가 없으면 503."""
        base = upstream_base()
        if not base:
            self._send_json({"ok": False, "error": why + " — 이 서버에는 넘길 상류(KJC_KIS_UPSTREAM)가 없습니다",
                             "source": source}, 503)
            return
        try:
            with urllib.request.urlopen(base + self.path, timeout=UPSTREAM_TIMEOUT) as resp:
                status, body = resp.status, resp.read()
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read()
        except (urllib.error.URLError, OSError) as e:
            self._send_json({"ok": False, "error": "상류(8765)에 못 닿았습니다 — %s" % safe_message(e),
                             "source": source}, 502)
            return
        self._send_body(status, body, "application/json; charset=utf-8")

    def _handle_naver(self):
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path[len("/api/naver/"):].strip("/")
        qs = urllib.parse.parse_qs(parsed.query)
        kind = (qs.get("kind") or ["industry"])[0].strip()

        span = (qs.get("span") or ["d"])[0].strip()

        try:
            # 주간 · 월간 (2026-10-08 재권님 「네이버로」) — 묶음 안 종목 기간 등락률 평균 · `naver_period.py`
            if route in ("groups", "stocks") and span in naver_period.SPAN_BACK:
                if route == "groups":
                    g = naver_period.groups(kind, span)
                    rows = g and g["rows"]
                    meta = {"kind": kind, "span": span, "total": g and g["total"],
                            "asof": g and g["asof"], "source": "네이버"}
                else:
                    no = (qs.get("no") or [""])[0].strip()
                    if not no.isdigit():
                        self._send_json({"ok": False, "error": "no 는 숫자여야 합니다."}, 400)
                        return
                    rows = naver_period.stocks(kind, no, span)
                    meta = {"kind": kind, "no": int(no), "span": span, "source": "네이버"}
                if not rows:
                    # 못 쟀다 — 빈 목록을 「없다」 로 내지 않는다
                    self._send_json({"ok": False, "error": "기간 값을 아직 못 받았습니다(장 마감 뒤 하루 한 번 받습니다).",
                                     "meta": meta}, 503)
                    return
                meta["count"] = len(rows)
                self._send_json({"ok": True, "data": rows, "meta": meta})
                return
            if span != "d" and route in ("groups", "stocks"):
                self._send_json({"ok": False, "error": "span 은 d · w · m 중 하나여야 합니다."}, 400)
                return

            if route == "groups" and (qs.get("all") or [""])[0] == "1":
                # 업종 · 테마 **전부** — 실시간 순위 칩의 섹터 띠가 종목 섹터 이름(WICS)으로 찾는다(상위 20 만으로는 60 중 18 만 맞음 · 2026-11-11)
                g = naver.groups_all(kind)
                self._send_json({"ok": True, "data": g["rows"],
                                 "meta": {"kind": kind, "total": g["total"], "count": len(g["rows"]), "all": True,
                                          "source": "네이버", "cacheTtl": naver.TTL}})
                return
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
                # 제목에 그 종목 이름 · 별칭이 든 것만 (2026-10-06 지시). candidates 는 네이버가 준 묶음 수,
                # kept 는 남은 수, filtered=False 는 이름을 몰라 거르지 않았다는 뜻 — 화면이 셋을 가른다
                rows, info = naver.news_related(code)
                self._send_json({
                    "ok": True, "data": rows,
                    "meta": {"code": code, "count": len(rows), "source": "네이버", **info},
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
                # all=1 — 상위 10 이 아니라 그 묶음 전부(실시간 순위 「테마」 칩 · 2026-10-27)
                s = naver.stocks(kind, no, (qs.get("all") or [""])[0] == "1")
                self._send_json({
                    "ok": True, "data": s["rows"],
                    "meta": {"kind": kind, "no": int(no), "name": s["name"],
                             "count": len(s["rows"]), "total": s.get("total"), "source": "네이버"},
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

            # 이슈 판 — 같은 사건 묶음을 「이슈」 로 올려 뜨거운 정도를 숫자로 (2026-11-12 재권님 「뉴스 이슈 만들기」 → 「응 올려놔」)
            # 셈 · 기준 상수는 news_store.issues 한 곳 · `issues` 주소는 「지금 RSS 받기」 라 이름을 따로 둔다
            if route == "hot":
                r = news_store.issues()
                self._send_json({"ok": True, "data": {"issues": r["issues"], "rising": r["rising"]}, "meta": r["meta"]})
                return

            # 쌓아 둔 뉴스 — 묶음 단위 (2026-09-21 지시)
            #
            # `issues` 와 다르다. 저쪽은 **지금 RSS 를 받아** 돌려주고,
            # 이쪽은 **쌓아 둔 것을 읽는다.** 화면이 열릴 때마다 RSS 를
            # 파싱하지 않으므로 빠르고, 지나간 기사도 남아 있다.
            if route == "stored":
                qs = urllib.parse.parse_qs(parsed.query)
                # **`all=1` — 보관 기간(`news_store.NEWS_KEEP_DAYS`) 안 전부** (2026-11-05 · 「캐시 · 주기 · 한도 값을 화면에 박지 않는다」).
                # 화면이 기간 · 개수를 들지 않는다. 서버 상한(`NEWS_STORED_MAX`)을 넘으면 새것부터 그만큼만 내고 `truncated` 로 알린다
                if (qs.get("all") or [""])[0] == "1":
                    hours = news_store.NEWS_KEEP_DAYS * 24
                    rows = news_store.groups(hours=hours, limit=None)
                    found = len(rows)
                    rows = rows[:news_store.NEWS_STORED_MAX]
                    self._send_json({"ok": True, "data": rows,
                                     "meta": {"hours": hours, "count": len(rows), "found": found,
                                              "truncated": found > len(rows), "max": news_store.NEWS_STORED_MAX,
                                              "topics": news_store.counts(hours),
                                              "total": news_store.total()}})
                    return
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

            # 종목 풍선 — 섹터 · 주요 매출원 (2026-10-26 · company_profile.py). 네이버 몫은 DART 키가 없어도 낸다
            if route == "profile":
                code = (qs.get("code") or [""])[0].strip()
                if not re.fullmatch(r"\d{6}", code):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                rec = company_profile.profile(code)
                self._send_json({"ok": True, "data": company_profile.public(code, rec)})
                return

            # 지배구조 — 쌓인 것을 읽기만 한다(받기는 dart_gov 바퀴 · 8765). 키가 없어도 낸다
            if route == "gov":
                code = (qs.get("code") or [""])[0].strip()
                if not re.fullmatch(r"\d{6}", code):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                data, meta = dart_gov.gov(code)
                self._send_json({"ok": True, "data": data, "meta": meta})
                return
            if route == "gov/links":
                data, meta = dart_gov.links()
                self._send_json({"ok": True, "data": data, "meta": meta})
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

            if route == "ir":
                # 기업설명회(IR) 일시 — 본문에서 읽은 한국 날짜 · 시각(2026-10-26 · dart.read_ir).
                # 앞으로 days 일(기본 14 · 최대 90) · past 일 앞까지(기본 0 · 최대 30)
                def _n(k, d, hi):
                    try:
                        return max(0, min(hi, int((qs.get(k) or [str(d)])[0])))
                    except ValueError:
                        return d
                rows, meta = dart.read_ir(_n("days", 14, 90), _n("past", 0, 30))
                self._send_json({"ok": True, "data": rows, "meta": meta})
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

            if route == "search":
                # 종목 찾기 — 갈래 줄 검색칸 (2026-10-06 지시). 이미 있는 표 둘만 읽는다 — dart.search 주석
                q = (qs.get("q") or [""])[0]
                self._send_json({"ok": True, "data": dart.search(q, (qs.get("limit") or ["10"])[0])})
                return

            if route == "universe":
                # 코스피 200 다음 코스닥 150 (2026-10-06). rank 는 시장 안의 순위 — 화면은 market 으로 가른다
                rows = dart.universe_rows(None)
                self._send_json({"ok": True, "data": [
                    {"rank": r["rank"], "code": r["stock_code"], "name": r["name"],
                     "cap": r["market_cap"], "market": r["market"]} for r in rows
                ]})
                return

            self._send_json({"ok": False, "error": "알 수 없는 경로입니다: %s" % route}, 404)
        except Exception as e:
            if _db_missing(e):
                self._send_json(_DB_MISSING_BODY)
                return
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
            _base = upstream_base()
            if _base:
                # **넘기는 서버는 토큰을 받지 않는다** — 상류가 가진다.
                # 여기서 발급하면 폴더마다 토큰이 또 생겨 **모으려던 것이
                # 그 자리에서 어긋난다** (2026-10-01).
                token_ok, token_err = True, None
            else:
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
                # **주소는 내지 않는다.** 넘기는 중인지만 알린다
                "upstream": bool(_base),
            })
            return

        # ── 주기 정책 (2026-10-02) ── KIS 키와 무관한 값이라 secrets 검사 앞에 둔다
        # (키 없는 서버도 503 이 아니라 값을 낸다 · 창구 검수).
        # ── 롱폴링 입구 (2026-10-02 · ⓓ) ── 안 켠 서버에는 이 자리가 없다.
        if route == "poll":
            if not LONGPOLL_ON:
                self._send_json({"ok": False, "error": "그런 주소 없음"}, 404)
                return
            # **빈 값을 살려 다시 읽는다** — 위 `qs` 는 `h=` 처럼 빈 값을 버려서 묶음일 때
            # u·h 자리가 밀린다. 다른 라우트는 빈 값을 「없음」 으로 읽으므로 여기서만 바꾼다.
            _qb = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query,
                                        keep_blank_values=True)
            us = [x for x in (_qb.get("u") or []) if x]
            if not us or len(us) > LONGPOLL_MAX_URLS:
                self._send_json({"ok": False, "error": "u 는 1~%d 개여야 합니다." % LONGPOLL_MAX_URLS}, 400)
                return
            # **허용 접두 안쪽만**(`_lp_url_ok`). 묶음이면 **하나라도** 어기면 400 —
            # 화면은 `stats.longpollPrefixes` 로 미리 가른다.
            for u in us:
                why = _lp_url_ok(u)
                if why:
                    self._send_json({"ok": False, "error": why, "u": u}, 400)
                    return
            try:
                hold = float((qs.get("hold") or ["10"])[0])
            except ValueError:
                hold = 10.0
            hold = max(0.0, min(hold, LONGPOLL_MAX_HOLD))
            self._send_json(longpoll(us, _qb.get("h") or [], hold))
            return

        # ── 실시간 체결 (2026-11-05 · server/kis_ws.py) ── 새 체결이 올 때까지 쥐었다가 낸다.
        # 켠 서버(`KJC_KIS_WS=1` · 8765)만 증권사와 붙는다 — 그 밖은 상류(8765)로 넘긴다. 둘 다 아니면 `on:false`
        if route == "live":
            code = (qs.get("code") or [""])[0].strip().upper()
            if not re.fullmatch(r"[0-9A-Z]{6}", code):
                self._send_json({"ok": False, "error": "code 는 여섯 자리 종목코드여야 합니다."}, 400)
                return
            if kis_ws.KIS_WS_ON:
                try:
                    _seq = int((qs.get("seq") or ["0"])[0])
                    _hold = float((qs.get("hold") or [str(kis_ws.LIVE_HOLD_SEC)])[0])
                except ValueError:
                    self._send_json({"ok": False, "error": "seq · hold 는 숫자여야 합니다."}, 400)
                    return
                self._send_json(kis_ws.live(code, _seq, _hold))
                return
            _hb = upstream_base()
            if _hb and self._kis_route_via_upstream(_hb):
                return
            self._send_json({"ok": True, "on": False})
            return

        if route == "policy":
            # `drawMs` 는 화면이 잰 그리는 시간. 없거나 이상하면 `None` — 하한에서 뺀다.
            try:
                _dm = float((qs.get("drawMs") or [""])[0])
                _dm = _dm if 0 <= _dm < 60000 else None
            except ValueError:
                _dm = None
            self._send_json({"ok": True, "data": policy_values(_dm)})
            return

        if not cfg:
            self._send_json({
                "ok": False,
                "error": "secrets.json 이 없어 KIS 를 쓸 수 없습니다.",
            }, 503)
            return

        # ── 차트 셋은 화면 API 째로 상류에 (2026-10-02) ── 위 `HIGH_RELAY_ROUTES` 주석.
        # 받아 둔 봉만(`chart?stored=1` · 아래 chart 자리)은 KIS 를 안 부르므로 넘기지 않고 자기 DB 로 답한다 —
        # 넘기는 서버는 메인 DB 를 읽기 전용으로 열어 같은 값이다 (2026-10-07)
        if route in HIGH_RELAY_ROUTES and not (route == "chart" and (qs.get("stored") or [""])[0] == "1"):
            _hb = upstream_base()
            if _hb and self._kis_route_via_upstream(_hb):
                return

        try:
            # ── 넘겨받는 자리 (2026-10-01) ── **8765 만 켠다.**
            if route == RELAY_ROUTE:
                if not KIS_UPSTREAM_SERVE:
                    # **안 켠 서버에는 이 자리가 없다.** 막는 것이 아니라
                    # 없는 것이다 — 8764(외부접속)에 있으면 안 된다.
                    self._send_json({"ok": False, "error": "그런 주소 없음"}, 404)
                    return
                kis_path = (qs.get("path") or [""])[0]
                # **`/uapi/` 로 시작하는 것만.** 아니면 임의의 주소를
                # 부르게 하는 자리가 된다.
                if not kis_path.startswith("/uapi/"):
                    self._send_json(
                        {"ok": False, "error": "path 는 /uapi/ 로 시작해야 합니다."}, 400)
                    return
                tr = (qs.get("tr_id") or [""])[0].strip()
                if not tr:
                    self._send_json({"ok": False, "error": "tr_id 가 없습니다."}, 400)
                    return
                try:
                    relay_params = json.loads((qs.get("params") or ["{}"])[0])
                except ValueError:
                    self._send_json(
                        {"ok": False, "error": "params 가 JSON 이 아닙니다."}, 400)
                    return
                if not isinstance(relay_params, dict):
                    self._send_json(
                        {"ok": False, "error": "params 는 객체여야 합니다."}, 400)
                    return
                # **캐시를 먼저 본다.** 오류는 캐시하지 않는다 —
                # 실패를 TTL 동안 들고 있으면 더 나쁘다.
                ckey = (kis_path,
                        json.dumps(relay_params, sort_keys=True, ensure_ascii=False),
                        tr)
                now = time.time()
                hit = _relay_cache.get(ckey)
                if hit and now - hit[0] < _relay_ttl(kis_path):
                    _relay_stat["hits"] += 1
                    self._send_json({"ok": True, "data": hit[1], "cached": True,
                                     "fill": round(fill_factor(), 3)})
                    return
                _relay_stat["misses"] += 1
                _relay_times.append(now)       # `calls1hRelayed` 가 이것을 센다
                relay_data = kis_get(cfg, kis_path, relay_params, tr)
                _relay_cache[ckey] = (now, relay_data)
                if len(_relay_cache) > RELAY_CACHE_MAX:
                    _relay_sweep(now)
                self._send_json({"ok": True, "data": relay_data,
                                 "fill": round(fill_factor(), 3)})
                return

            if route == "price":
                code = (qs.get("code") or [""])[0].strip()
                if not _code_ok(code):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자이거나 미국 티커여야 합니다."}, 400)
                    return
                if us_universe.is_us(code):
                    data, errors = _us_quotes(cfg, [code])
                    if code not in data:
                        self._send_json({"ok": False, "error": errors.get(code) or "받지 못했습니다."}, 502)
                        return
                    self._send_json({"ok": True, "data": data[code]})
                    return
                try:
                    self._send_json({"ok": True, "data": fetch_price(cfg, code)})
                except NoSuchStock as e:
                    self._send_json({"ok": False, "notFound": True, "error": safe_message(e)}, 404)
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
                if not _code_ok(code):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자이거나 미국 티커여야 합니다."}, 400)
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
                # ── 받아 둔 것만 (2026-10-07 재권님 「1 해줘」 — 「다른 종목을 열 때 미리 받아 놓은 5분봉을 불러오고
                # 불러오지 못한 것만 그린다」) ── `stored=1` 이면 KIS 를 안 부르고 DB 에 있는 봉만 바로 준다. 전에는 DB 에
                # 봉이 있어도 「오래됨」 이면 빈 30분 칸을 KIS 로 다 채운 **뒤에** 답해, 종목을 바꿀 때마다 차트 칸이
                # 0.9~2.9초 「불러오는 중」 으로 덮였다(10-07 17:05 실측). 화면은 이것으로 먼저 그리고 since 로 빈 칸만 받는다.
                # 없으면 빈 목록 — 화면이 그때만 「불러오는 중」 을 띄우고 통째로 받는다.
                if (qs.get("stored") or [""])[0] == "1":
                    rows, fetched, source = read_candles(code, period, _view_limit(code, period, limit)), 0, "DB"
                else:
                    rows, fetched, source = get_chart(cfg, code, period, limit)
                if period == "5m":
                    kick_kr_open_fill(cfg, code)        # 지수 밖 종목이면 지난 거래일을 뒤에서 한 번 (2026-10-16)
                head_ts = None
                if PERIODS[period]["kis"] is None and _is_kr_code(code) and rows:
                    # **VWAP 는 그날 첫 봉부터 센다 — 받은 봉 수에서 잘린 날의 앞을 채워 셈하고 셈 뒤에 뗀다** (2026-11-11 재권님
                    # 「1분봉 그건 맞는거 같은데 vwap값은 이상한데」). 차트는 봉 수(limit)로 받아, 1분봉 320개면 오늘 10시 무렵부터라
                    # VWAP 가 그 뒤만 센 값(하이닉스 15:20 1,274,305 ↔ 하루 셈 1,249,553)이 됐다. 5분봉은 view_days 로 날째 받아 안 걸렸다
                    head_ts = rows[0]["ts"]
                    earlier = sorted((b for t, b in _stored_day(code, period, head_ts[:8]).items() if t < head_ts),
                                     key=lambda b: b["ts"])
                    rows = earlier + list(rows)
                if PERIODS[period]["kis"] is None:      # 분봉(1m · 5m)만 — 일봉 이상은 받은 그대로
                    if _is_kr_code(code):
                        rows = flatten_carried(rows)    # 앞 봉 복사 → 거래 없는 납작봉(2026-11-07)
                    rows = drop_before_first_trade(rows)
                # ── 안 받은 봉만 (2026-10-07 지시 — 「아직 안 받은 봉만 받아 덧붙이고, 받아 둔 봉은 다시 받지 않는다」) ──
                # 화면이 마지막으로 받은 봉 시각을 since 로 보내면 **그 시각 이후의 봉 전부**(그 봉 포함 — 진행 중이라
                # 값이 바뀌었을 수 있다)를 준다. 1개든 20개든. 전에는 30초마다 1,266개를 통째로 보냈다(10-07 실측).
                # 위 계산(get_chart · drop_before_first_trade)은 그대로 다 하고 **보내기만** 줄인다 — KIS 호출은 그대로다.
                rows = [r for r in rows if (r.get("close") or 0) > 0]   # 0 봉은 내지 않는다(없는 종목 · 위 `save_candles` 와 같은 선)
                if PERIODS[period]["kis"] is None and _is_kr_code(code):
                    rows = vwap.attach(rows)            # since 로 자르기 전에 — 그날 첫 봉부터 누적이라(2026-11-06)
                if head_ts:
                    rows = [r for r in rows if str(r.get("ts", "")) >= head_ts]   # 셈하려고 채운 앞 봉은 뗀다 — 받은 봉 수 그대로
                since = (qs.get("since") or [""])[0].strip()
                total = len(rows)
                if since.isdigit():
                    rows = [r for r in rows if str(r.get("ts", "")) >= since]
                self._send_json({
                    "ok": True,
                    "data": {"code": code, "period": period, "candles": rows},
                    "meta": {
                        "count": len(rows), "fetched": fetched, "source": source,
                        "label": PERIODS[period]["label"],
                        "since": since or None, "total": total,
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

            # 지수 일봉 몇 달 — 국내 · 미국을 한 번에(위 fetch_index_daily)
            if route == "index-daily":
                names = [x.strip().upper() for x in (qs.get("codes") or ["KOSPI,SPX,NASDAQ,SOX"])[0].split(",") if x.strip()][:12]
                data = fetch_index_daily(cfg, names)
                self._send_json({"ok": any(v.get("bars") for v in data.values()), "data": data,
                                 "meta": {"months": INDEX_DAILY_MONTHS, "cacheTtl": INDEX_DAILY_TTL,
                                          "names": [n for _, n in INDEX_DEFS] + [d[0] for d in OVERSEAS_DEFS]
                                                   + [d[0] for d in NAVER_INDEX_DEFS],
                                          "note": "date 는 그 시장의 거래일(미국은 현지 날짜) · 국내 오늘 봉은 장중이면 아직 안 끝난 값 · "
                                                  "bars null = 못 받음(0 이 아님)"}})
                return

            # 종목 정규장(KRX · J) 일봉 몇 달 — 지수 일봉(index-daily)과 같은 모양(위 fetch_stock_daily)
            if route == "stock-daily":
                codes = [c.strip() for c in (qs.get("codes") or [""])[0].split(",") if c.strip()]
                if not codes or len(codes) > 10 or not all(c.isdigit() and len(c) == 6 for c in codes):
                    self._send_json({"ok": False, "error": "codes 는 6자리 숫자 종목코드 1~10개(쉼표로)여야 합니다."}, 400)
                    return
                data = fetch_stock_daily(cfg, codes)
                self._send_json({"ok": any(v.get("bars") for v in data.values()), "data": data,
                                 "meta": {"months": INDEX_DAILY_MONTHS, "cacheTtl": INDEX_DAILY_TTL, "market": "J",
                                          "note": "정규장(KRX · 09:00~15:30) 시가 · 고가 · 저가 · 종가 — 넥스트레이드 프리장 · 애프터 빠짐 · "
                                                  "오늘 봉은 장중이면 아직 안 끝난 값 · bars null = 못 받음(0 이 아님)"}})
                return

            # 주식선물 최근월물 일봉 몇 달 — 날마다 그날의 최근월물(위 fetch_stock_futures_daily)
            if route == "stock-futures-daily":
                codes = [c.strip() for c in (qs.get("codes") or [""])[0].split(",") if c.strip()]
                if not codes or len(codes) > 10 or not all(c.isdigit() and len(c) == 6 for c in codes):
                    self._send_json({"ok": False, "error": "codes 는 6자리 숫자 종목코드 1~10개(쉼표로)여야 합니다."}, 400)
                    return
                data = fetch_stock_futures_daily(cfg, codes)
                self._send_json({"ok": any(v.get("bars") for v in data.values()), "data": data,
                                 "meta": {"months": INDEX_DAILY_MONTHS, "cacheTtl": INDEX_DAILY_TTL,
                                          "note": "주식선물 주간장 최근월물 — 그날 봉이 있는 가장 가까운 달 · 만기 다음 날 다음 달물(roll) · "
                                                  "prevClose 는 같은 월물 전날 종가 · contract 는 KIS 월물 코드 · "
                                                  "오늘 봉은 장중이면 아직 안 끝난 값 · bars null = 못 받음(0 이 아님)"}})
                return

            # 주식선물 · 종목 풋 · 코스피200 풋/콜 지금 값(위 fetch_fo_snapshot)
            if route == "fo-snapshot":
                codes = [c.strip() for c in (qs.get("codes") or ["005930,000660"])[0].split(",") if c.strip()]
                if not codes or len(codes) > 5 or not all(c.isdigit() and len(c) == 6 for c in codes):
                    self._send_json({"ok": False, "error": "codes 는 6자리 숫자 종목코드 1~5개(쉼표로)여야 합니다."}, 400)
                    return
                data, ttl = fetch_fo_snapshot(cfg, codes)
                self._send_json({"ok": any((v.get("futures") or v.get("puts")) for v in data["stocks"].values()) or "index" in (data["kospi200"] or {}),
                                 "data": data,
                                 "meta": {"cacheTtl": ttl, "ttlOpen": FO_SNAP_TTL, "ttlClosed": FO_SNAP_TTL_CLOSED,
                                          "note": "KIS 현재가 조회 · 누가 물을 때만 받고 cacheTtl 초 동안 같은 값 · at = 받은 시각 · "
                                                  "futures 는 주식선물 최근월물(month) · calls · puts 는 optionMonth 콜 · 풋을 따로 — 각각 선물 현재가에 가까운 행사가 · "
                                                  "kospi200 은 futures(지수선물 최근월물) · calls · puts(지수에 가까운 행사가 줄 · 종목 칸과 같은 모양) · "
                                                  "비율은 그 월물 등가격 둘레 strikes 범위(strikeCount 줄)의 콜 · 풋 합 — 시장 전체가 아님 · "
                                                  "iv 는 KIS 내재변동성 칸 그대로(단위 미확인 · 종목 옵션 0.7 꼴) · price 는 마지막 체결가라 그날 거래 0 이면 전날 값 · "
                                                  "missing = 못 받은 줄 수 · null = 못 받음(0 이 아님)"}})
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
                with ThreadPoolExecutor(max_workers=3) as pool:
                    f_all = pool.submit(fetch_indices_all, cfg, with_chart, want_ovs)
                    f_fut = pool.submit(fetch_futures, cfg)
                    f_night = pool.submit(fetch_futures, cfg, "CM")   # KRX 야간 (2026-10-26)
                    data, errors = f_all.result()
                    futures = f_fut.result()
                    futures_night = f_night.result()
                try:
                    opt_exp = market_hours.opt_expiry(sys.modules[__name__])   # 옵션 만기 칩(야간 옆 · 2026-11-12)
                except Exception:
                    opt_exp = None                                             # 못 셈 — 칩을 안 그린다(0 · 빈 날로 안 냄)
                self._send_json({"ok": bool(data), "data": data,
                                 "futures": futures, "futuresNight": futures_night, "optExpiry": opt_exp,
                                 "errors": errors or None})
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

            if route == "flow-board":
                # 수급 정리판 — Insight 「투자 전략」 (2026-11-04 · server/flow_board.py) · 새로 KIS 를 부르지 않고 이미 받는 셋을 모은다
                try:
                    days = max(1, min(int((qs.get("days") or [str(flow_board.DAYS_DEFAULT)])[0]), flow_board.DAYS_MAX))
                    step = int((qs.get("step") or [str(flow_board.STEP_DEFAULT)])[0])
                except ValueError:
                    self._send_json({"ok": False, "error": "days · step 은 숫자입니다."}, 400)
                    return
                if step not in intraday_flow.STEPS:
                    self._send_json({"ok": False, "error": "step 은 %s 중 하나입니다." % " · ".join(map(str, intraday_flow.STEPS))}, 400)
                    return
                self._send_json({"ok": True, "data": flow_board.board(sys.modules[__name__], cfg, days, step),
                                 "meta": {"days": days, "step": step, "amtUnit": "백만원", "qtyUnit": "천주",
                                          "today": "코스피만 · 장중 1분마다 쌓은 누계(intraday_flow)",
                                          "daysNote": "확정치 · 과거→최근", "top": "가집계 — 외국인 09:30 · 11:20 · 13:20 · 14:30 / 기관 10:00 · 11:20 · 13:20 · 14:30",
                                          "cacheTtl": flow_board.CACHE_TTL}})
                return

            # 홈 실시간 순위 「매수」 칩 — 외국인 · 기관 · 프로그램이 함께 사는 종목 (2026-11-05 · `fetch_joint_buy`)
            # 실시간 순위 모달 「전일비」 — 지금 시간대(프리장 · 정규장 · 애프터)끼리 오늘 ÷ 어제 (2026-11-05 · server/session_volume.py)
            if route == "vol-ratio":
                codes = [c for c in ((qs.get("codes") or [""])[0]).split(",") if c.isdigit() and len(c) == 6][:300]
                name, label, prev_day, data = session_volume.ratio(sys.modules[__name__], cfg, codes)
                self._send_json({"ok": True, "data": data,
                                 "meta": {"session": name, "label": label, "prevDay": prev_day, "unit": "%",
                                          "note": "통합(거래소 + 넥스트레이드) 누적 거래량 · 지금 시간대의 오늘 ÷ 어제 같은 시간대 전체 · 저장 없는 날은 null",
                                          "cacheTtl": session_volume.CACHE_TTL}})
                return

            # 프리장(넥스트레이드 08:00~08:50) 프로그램 몰리는 종목 — 실시간 순위 「프리장」 칩 (2026-11-05 · server/pre_flow.py)
            if route == "short-sale":
                # 실시간 순위 「공매도」 칩 — 쌓아 둔 표(short_daily)에서 셈만 한다. KIS 를 부르지 않는다(쌓는 것은 short_sale.start)
                self._send_json({"ok": True, **short_sale.ranking((qs.get("period") or ["1d"])[0], (qs.get("sort") or ["amt"])[0])})
                return
            if route == "pre-flow":
                data, at, ph = pre_flow.fetch(sys.modules[__name__], cfg)
                d = data or {}
                self._send_json({
                    "ok": data is not None, "data": d.get("rows") or [], "sectors": d.get("sectors") or [],
                    "meta": {"asof": datetime.fromtimestamp(at, KST).strftime("%Y-%m-%d %H:%M:%S") if at else None,
                             "day": d.get("day"), "builtAt": d.get("hm"), "phase": ph, "noTrade": bool(d.get("noTrade")),
                             "candidates": d.get("candidates"), "programMissing": d.get("programMissing"),
                             "amtUnit": "원", "topN": pre_flow.TOP_N,
                             "preOpen": "%02d:%02d" % pre_flow.PRE_OPEN, "preClose": "%02d:%02d" % pre_flow.PRE_CLOSE,
                             "riseMinPct": pre_flow.RISE_MIN_PCT,
                             "note": "넥스트레이드 프리마켓 · 순위 목록 중 전일 정규장 종가보다 오른 종목의 프리장 거래대금(현재가 × 거래량 · 어림) 상위 topN · 차례는 등락률 큰 순 · program 은 그날 누적(칸만) · "
                                     "등락률은 전일 정규장 종가 대비 · ratio 는 앞 거래일 장 전 거래량 대비 · disc 는 앞 평일 15:30 뒤 공시 · "
                                     "08:50~09:00 에 그날 판으로 굳힘",
                             "cacheTtl": pre_flow.FLOW_TTL},
                })
                return

            if route == "day-top/filters":
                # 쌓인 날 전부 모은 필터별 셈 · 날별 셈(server/day_top.filters) — 투자 전략 「필터」 탭 · KIS 안 부름 (2026-11-11 재권님)
                self._send_json({"ok": True, "data": day_top.filters(sys.modules[__name__]),
                                 "meta": {"minCapEok": day_top.MIN_CAP_EOK, "topN": day_top.TOP_N, "saveAt": "%02d:%02d" % day_top.SAVE_AT,
                                          "note": "상위 = 그날 등락률 상위 topN · 전체 = 시가총액 minCapEok 억 이상 주식 · lift = 상위 중 몫 ÷ 전체 중 몫 · "
                                                  "hit = 걸린 것 중 상위에 든 몫 · next = 걸린 종목 다음 거래일 종가 등락률(다음 날이 온 종목만) · % 단위"}})
                return

            if route == "day-top":
                # 등락 상위와 걸린 필터(server/day_top.py) — 남긴 날 판만 읽는다 · KIS 를 안 부른다
                day = (qs.get("day") or [""])[0].strip()
                if day and not (day.isdigit() and len(day) == 8):
                    self._send_json({"ok": False, "error": "day 는 YYYYMMDD 입니다."}, 400)
                    return
                b = day_top.board(sys.modules[__name__], day or None, (qs.get("all") or [""])[0] == "1")
                self._send_json({"ok": b is not None, "data": b,
                                 "meta": dict(day_top.status(), days=day_top.days(sys.modules[__name__]), fill=day_top_fill.status())})
                return

            if route == "dt30":
                # 단타 30 판(server/dt30.py) — 남긴 날 판을 읽는다 · 안 끝난 그날 판만 지금 값(멀티 시세 · 캐시 먼저)을 붙인다
                day = (qs.get("day") or [""])[0].strip()
                if day and not (day.isdigit() and len(day) == 8):
                    self._send_json({"ok": False, "error": "day 는 YYYYMMDD 입니다."}, 400)
                    return
                b = dt30.board(sys.modules[__name__], day or None, cfg)
                self._send_json({"ok": b is not None, "data": b,
                                 "meta": dict(dt30.status(), days=dt30.days(sys.modules[__name__]))})
                return

            if route == "open-rise":
                # 초반상승 — 정규장 첫 5분봉(여는 시각부터 5분 · market_hours)이 시가보다 RISE_PCT % 이상 올라 끝난 종목 (2026-11-11 · server/open_rise.py) · KIS 안 부름
                d, at = open_rise.fetch(sys.modules[__name__])
                self._send_json({
                    "ok": True, "data": d["rows"],
                    "meta": {"asof": datetime.fromtimestamp(at, KST).strftime("%Y-%m-%d %H:%M:%S"),
                             "day": d["day"], "phase": d["phase"], "candidates": d["candidates"], "pending": d["pending"],
                             "noBar": d["noBar"], "capMissing": d["capMissing"], "etfOut": d["etfOut"],
                             "risePct": open_rise.RISE_PCT, "minCapEok": open_rise.MIN_CAP_EOK,
                             "barFrom": d["barFrom"], "barTo": d["barTo"],
                             "note": "DB 에 쌓인 5분봉 — 정규장 첫 봉 (종가 − 시가) ÷ 시가 · 그 봉을 끝난 뒤 받은 종목만(pending 은 아직) · 시가총액 단위 억원",
                             "cacheTtl": open_rise.CACHE_TTL, "first": open_rise.first_status()},
                })
                return

            if route == "rescan":
                # 「지금검색」 — 매수 · 수급 · 프리장을 그 자리에서 다시 셈(문턱 rescan.MIN_SEC) · 나머지 칩은 화면이 다시 받기만 (2026-11-11 재권님 「나」)
                self._send_json({"ok": True, "data": rescan.run(sys.modules[__name__], cfg, pre_flow._writer["on"])})
                return

            if route == "joint-buy":
                data, at = fetch_joint_buy(cfg)
                _now = datetime.now(KST)
                if _now.weekday() < 5 and market_hours.CHIP_RESET <= _now.strftime("%H%M") < market_hours.REG_OPEN:
                    data = dict(data or {}, rows=[], flipped=[], phase="before", reset=True)   # 07:30~09:00 「시작 전」(11-13 재권님 「다른 칩은 아침 7시반에」)
                d = data or {}
                self._send_json({
                    "ok": data is not None, "data": d.get("rows") or [], "flipped": d.get("flipped") or [],
                    "meta": {"asof": datetime.fromtimestamp(at, KST).strftime("%Y-%m-%d %H:%M:%S") if at else None,
                             "pending": data is None,
                             "candidates": d.get("candidates"), "programMissing": d.get("programMissing"),
                             "listFail": bool(d.get("listFail")), "errors": d.get("errors"),
                             "amtUnit": "원", "confirmed": d.get("confirmed"), "estimated": d.get("estimated"),
                             "phase": d.get("phase"), "reset": bool(d.get("reset")), "regClose": "%02d:%02d" % KRX_CLOSE,
                             # 가집계(추정)가 한 줄이라도 섞였나 — 장중은 전부 · 마감 뒤는 estimated 가 1 이상일 때
                             "provisional": d.get("confirmed") is None or bool(d.get("estimated")),
                             "note": "외국인 · 기관은 장중 증권사 가집계(하루 네 번) · 15:40 뒤 그날 확정치(줄마다 basis · 수는 confirmed · estimated) · 프로그램은 그날 누적 · "
                                     "셋 다 순매수 양수 · flipped 는 오늘 셋 다 샀다가 빠진 종목",
                             "estSlots": INVESTOR_EST_SLOTS,
                             # 쌓기(11-06) — 줄마다 first(처음 셋 다 산 시각) · hits(그날 판에 잡힌 횟수) · pgAt(프로그램 값의 시각) ·
                             # fund · person(연기금 · 개인 그날 확정치 원 · 15:45 뒤 쌓기 전에는 null) · fundIn 은 연기금 값이 든 줄 수
                             "fundIn": d.get("fundIn"), "fundAt": "%02d:%02d" % flow_rank.COLLECT_AT,
                             "cacheTtl": INVESTOR_TOP_TTL},
                })
                return

            if route == "flow-rank":
                # 투자자 매매 동향 모달 (2026-11-06 · server/flow_rank.py) — 오늘은 가집계를 합쳐 셈 · 지난 날은 저장한 판
                if (qs.get("view") or [""])[0] == "actor":
                    day = (qs.get("day") or [""])[0].strip() or None
                    self._send_json({"ok": True, "data": flow_rank.actor_board(sys.modules[__name__], day, cfg),
                                     "meta": {"note": "종목별 확정치(FHPTJ04160001 · 15:40 뒤에만 받힘) · 화면에서 열어 본 종목만 쌓임 · 억 = 백만원 ÷ 100"}})
                    return
                who = (qs.get("who") or ["foreign"])[0].strip().lower()
                if who not in flow_rank.WHO:
                    self._send_json({"ok": False, "error": "who 는 foreign 또는 inst 여야 합니다."}, 400)
                    return
                day = (qs.get("day") or [""])[0].strip() or None
                if day and not (day.isdigit() and len(day) == 8):
                    self._send_json({"ok": False, "error": "day 는 YYYYMMDD 여야 합니다."}, 400)
                    return
                b = flow_rank.board(sys.modules[__name__], cfg, who, day)
                self._send_json({"ok": True, "data": b,
                                 "meta": {"days": flow_rank.days(sys.modules[__name__]), "limit": flow_rank.LIMIT,
                                          "note": "가집계(증권사 장중 입력 · 외국인 09:30 · 11:20 · 13:20 · 14:30 / 기관 10:00 · 11:20 · 13:20 · 14:30) · "
                                                  "전일은 확정치 · 강도 = 순매수 ÷ 거래대금(거래량 × 현재가) × 100 · 동시 순매수면 다른 쪽 몫을 더함",
                                          "cacheTtl": INVESTOR_TOP_TTL}})
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
            if route == "finance-multi":
                # 산업 분석 화면 — 종목 여럿의 분기 · 연간 매출 · 영업이익 (`fetch_finance_multi` 머리 주석)
                raw = (qs.get("codes") or [""])[0]
                codes = list(dict.fromkeys(c.strip() for c in raw.split(",") if c.strip()))
                if not codes or len(codes) > FIN_MULTI_MAX or not all(c.isdigit() and len(c) == 6 for c in codes):
                    self._send_json({"ok": False, "error": "codes 는 6자리 숫자를 쉼표로 · 최대 %d개입니다." % FIN_MULTI_MAX}, 400)
                    return

                def _n(name, dflt, hi):
                    try:
                        return max(1, min(hi, int((qs.get(name) or [dflt])[0])))
                    except (TypeError, ValueError):
                        return dflt
                nq, ny = _n("quarters", FIN_MULTI_QUARTERS, 40), _n("years", FIN_MULTI_YEARS, 10)
                data, pending = fetch_finance_multi(cfg, codes, nq, ny)
                self._send_json({
                    "ok": True, "data": data,
                    "meta": {
                        "count": len(codes), "unit": "억원", "quarters": nq, "years": ny,
                        "pending": pending, "retryAfterSec": FIN_MULTI_RETRY_SEC if pending else None,
                        "source": "한국투자증권 손익계산서(%s)" % {k: t for k, _p, t in _FIN_APIS}["income"],
                        # 분기 sale/op = 연 누적에서 같은 해 앞 분기 누적을 뺌 · 연간 = 12월 누적 · 못 세면 None
                        # 기준(연결 · 별도) 칸은 KIS 가 안 준다 — 머리 주석
                    },
                })
                return
            if route == "finance":
                code = (qs.get("code") or [""])[0].strip()
                if not (code.isdigit() and len(code) == 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                fin = fetch_finance(cfg, code)
                self._send_json({
                    "ok": bool(fin["rows"]), "data": fin["rows"],
                    "meta": {
                        "code": code, "count": len(fin["rows"]), "period": "분기",
                        "unit": "억원", "missing": fin["missing"], "fetchedAt": fin["at"],
                        "ttl": FINANCE_TTL,
                        "source": {k: tr for k, _p, tr in _FIN_APIS},
                        # 손익 sale/op/net 은 분기 값(누적에서 뺌) · …Ytd 는 연 누적 그대로
                        # 비율은 KIS 가 준 그대로(누적 기준) · 99.99 는 None
                    },
                })
                return
            if route == "investor":
                code = (qs.get("code") or [""])[0].strip()
                if not (code.isdigit() and len(code) == 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                # `span=60` 이면 쌓인 옛 줄을 이어 3달까지 (2026-10-15 · `fetch_investor_long`)
                try:
                    span = int((qs.get("span") or ["0"])[0])
                except ValueError:
                    span = 0
                if span > INVESTOR_DAYS:
                    data = fetch_investor_long(cfg, code, min(span, INVESTOR_LONG_DAYS))
                else:
                    data = fetch_investor(cfg, code)
                    try:                         # 세부는 쌓인 줄에서 온다 — 15:40 뒤 처음 열 때 한 번 쌓는다(3달과 같은 받기)
                        _inv_long_fetch(cfg, code)
                    except Exception as e:
                        _inv_long_fail[code] = time.time()
                        print("[투자자 3달] %s 받다 멈춤 — %s" % (code, safe_message(e, 120)))
                data = _inv_attach_detail(code, data or [])
                self._send_json({
                    "ok": bool(data), "data": data,
                    "meta": {
                        "code": code, "count": len(data), "days": INVESTOR_DAYS,
                        "qtyUnit": "주", "amtUnit": "백만원",
                        # 이 서버가 3달 옛 줄을 스스로 받나 — 읽기만 하는 서버(8764 등)는 8765 가
                        # 쌓은 것만 읽으므로 「15:40 뒤 채워집니다」 를 약속하지 않는다 (2026-10-15 qa)
                        "longFill": marketdb.writable(),
                        # 종목별은 확정치다 (docs/kis-sector-investor.md).
                        # 상위 목록(investor-top)만 가집계라 거기만 그렇게 적는다.
                        "provisional": False,
                        # 줄마다 instDetail(기관 세부) · foreignReg/foreignNreg(외국인 등록/미등록) · etcCorp(기타법인)
                        # — 마감(15:40) 뒤 확정치라 장중 오늘 · 아직 안 쌓인 날은 null (2026-10-27)
                        "instDetail": [[k, n] for k, n in INV_INST_DETAIL],
                        "detailOpen": "%02d:%02d" % INVESTOR_LONG_OPEN,
                    },
                })
                return

            # 당일 수급 — 투자자 지표 모달 「당일」 탭 (2026-10-27 · `intraday_flow`)
            if route == "flow-today":
                code = (qs.get("code") or [""])[0].strip()
                if code and not (code.isdigit() and len(code) == 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                try:
                    step = int((qs.get("step") or ["5"])[0])
                except ValueError:
                    step = 5
                if step not in intraday_flow.STEPS:
                    self._send_json({"ok": False, "error": "step 은 %s 중 하나입니다." % " · ".join(map(str, intraday_flow.STEPS))}, 400)
                    return
                intraday_flow.want(code)
                self._send_json({"ok": True, "data": intraday_flow.today(sys.modules[__name__], code or None, step),
                                 "meta": {"step": step, "market": "코스피", "cacheTtl": intraday_flow.CACHE_TTL,
                                          "units": {"market": "백만원 · 천주", "program": "백만원(수량 없음)", "stock": "원 · 주"},
                                          "session": "평일 09:00~15:30", "collector": intraday_flow.status()}})
                return

            # 증권사 매매 상위 5 (2026-10-27 · `fetch_investor_member`)
            # 순위표 섹터 — 종목 → WICS 이름 · 쥔 것만 · 뒤에서 채운다 (2026-11-04 · company_profile.py)
            # 「sectors」 는 업종 지수 주소라 이름을 갈랐다
            if route == "stock-sectors":
                self._send_json({"ok": True, "data": company_profile.sectors(),
                                 "meta": {"source": "네이버(FnGuide) WICS", "fill": company_profile.fill_status(),
                                          "cacheTtl": company_profile.SECTOR_LIST_TTL}})
                return

            if route == "investor-member":
                code = (qs.get("code") or [""])[0].strip()
                if not (code.isdigit() and len(code) == 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                mb = fetch_investor_member(cfg, code)
                if not mb:
                    self._send_json({"ok": False, "error": "증권사 매매 상위를 못 받았습니다."}, 503)
                    return
                self._send_json({"ok": True, "data": mb,
                                 "meta": {"code": code, "qtyUnit": "주", "pctUnit": "%",
                                          "span": "오늘 장중 누적(KRX 회원사)", "cacheTtl": INVESTOR_MEMBER_TTL}})
                return

            # 차트 보조지표 「누적 순매수」 칸 (2026-10-26 · `holding_flow`)
            if route == "holding-flow":
                code = (qs.get("code") or [""])[0].strip()
                if not (code.isdigit() and len(code) == 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                hf = holding_flow(cfg, code)
                if not hf:
                    self._send_json({"ok": False, "error": "투자자 줄이나 상장주식수를 못 받았습니다."}, 503)
                    return
                self._send_json({"ok": True, "data": hf["rows"],
                                 "meta": {"code": code, "start": hf["start"], "listed": hf["listed"], "unit": "%p",
                                          "share": hf.get("share"),
                                          "note": "보유비중 아님 · 셈 첫날부터 누적 순매수 ÷ 상장주식수 · share 는 최근 days 거래일 셋의 매수 + 매도 금액 합에서 각자 몫(%)"}})
                return

            # 투자자 지표 모달 「그래프」 판 (2026-10-16 · `investor_board`)
            if route == "investor-board":
                mkt = (qs.get("mkt") or ["ALL"])[0].upper()
                if mkt not in INVESTOR_BOARD_MARKETS:
                    self._send_json({"ok": False, "error": "mkt 는 %s 중 하나입니다." % " · ".join(INVESTOR_BOARD_MARKETS)}, 400)
                    return
                try:
                    days = int((qs.get("days") or ["1"])[0])
                except ValueError:
                    days = 1
                days = max(1, min(days, INVESTOR_LONG_DAYS))
                board, at = investor_board(cfg)
                if not board:
                    self._send_json({"ok": False, "error": "투자자 판을 아직 못 지었습니다."}, 503)
                    return
                # 줄은 확정치 days 줄 + 장중 오늘 빈 줄 하나까지 — 화면이 빈 줄을 건너뛰고 days 줄을 더한다
                data = [dict(x, rows=board["inv"].get(x["code"], [])[:days + 1]) for x in board["tops"][mkt]]
                self._send_json({
                    "ok": True, "data": data, "names": board["names"],
                    "meta": {
                        "mkt": mkt, "days": days, "top": INVESTOR_BOARD_TOP,
                        "asof": datetime.fromtimestamp(at, KST).strftime("%Y-%m-%d %H:%M:%S"),
                        "age": round(time.time() - at, 1),
                        "universe": board["universe"], "quoted": board["quoted"],
                        "quoteErrors": board["quoteErrors"],
                        "qtyUnit": "주", "amtUnit": "백만원", "valueUnit": "원",
                        "cacheTtl": PRICE_CACHE_TTL,
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
                # amount — 화면이 금액(원)으로 그리는 값 하나(11-05 재권님 「금액으로 다 맞춰줘」). 마감 뒤 확정치가 있으면 그것(basis
                # confirmed) · 없으면 최신 회차 수량 × 현재가(approx · 증권사 가집계는 수량만 준다) · 못 셈은 None
                conf = investor_confirmed_today(cfg, code)
                if conf:
                    amount = {"basis": "confirmed", "date": conf["date"], "foreign": conf["foreign"], "inst": conf["inst"], "approx": False}
                else:
                    lt = (data or {}).get("latest") or {}
                    try:
                        p0 = ((fetch_quotes_multi(cfg, [code])[0] or {}).get(code) or {}).get("price")
                    except RuntimeError:
                        p0 = None
                    amount = {"basis": "estimate", "seq": lt.get("seq"), "approx": True,
                              **{k: (lt.get(k) * p0 if lt.get(k) is not None and p0 else None) for k in ("foreign", "inst")}}
                data = dict(data or {}, amount=amount)
                self._send_json({
                    "ok": bool(data.get("latest") or conf), "data": data,
                    "meta": {
                        "code": code, "qtyUnit": "주", "amtUnit": "원",
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

            # 전날 정규장 5분봉 거래량 — 차트 위 「전날 같은 시각 대비 거래량 %」(2026-11-10 · vol_prev_day)
            if route == "vol-prev":
                code = (qs.get("code") or [""])[0].strip()
                if not (code.isdigit() and len(code) == 6):
                    self._send_json({"ok": False, "error": "code 는 6자리 숫자여야 합니다."}, 400)
                    return
                data = vol_same_time(code)
                self._send_json({"ok": data is not None, "data": data,
                                 "meta": {"code": code, "unit": "주", "source": "DB 에 쌓인 5분봉 — 오늘 · 전날 정규장 같은 시각까지(KIS 를 새로 안 부름)",
                                          "note": None if data else "전날 5분봉이 아직 안 쌓였습니다"}})
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

            # 예상 체결가가 맞았나 — 그날 쌓은 것과 실제 시가 · 종가 (2026-11-10 · expect_report)
            if route == "expect-log":
                day = (qs.get("day") or [datetime.now(KST).strftime("%Y%m%d")])[0].strip()
                if not (day.isdigit() and len(day) == 8):
                    self._send_json({"ok": False, "error": "day 는 YYYYMMDD 여야 합니다."}, 400)
                    return
                data = expect_report(day)
                self._send_json({"ok": "error" not in data, "data": data,
                                 "meta": {"note": "lastPrice = 동시호가 마지막으로 적은 예상가 · actual = 실제 시가(open) · 정규장 종가(close) · "
                                                  "actual 이 null 이면 아직 못 적음 · sameSince = 그 분부터 끝까지 실제 값과 같았음"}})
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

            if route == "heatmap":
                # 첫 화면 시장 지도 (2026-10-27 재권님 「응 시작해」 · `heatmap.py` 머리글). 국내는 멀티 시세 4번 ·
                # 미국은 「지금 뜨는 산업」 미국 칸 섹터 캐시를 함께 쓴다(봉 표만 · KIS 더 안 부름)
                mk = (qs.get("market") or ["kr"])[0].strip().lower()
                if mk not in ("kr", "us"):
                    self._send_json({"ok": False, "error": "market 은 kr · us 중 하나여야 합니다."}, 400)
                    return
                try:
                    if mk == "kr":
                        data = heatmap.kr(sys.modules[__name__], cfg)
                    else:
                        known = us_universe.symbol_map()

                        def sector_stocks(etf):
                            key = "%s:d" % etf
                            got = _ttl_get(_us_sector_cache, key, SECTOR_TTL)
                            if got is None:
                                got = us_sectors.stocks(etf, "d", read_candles, known)
                                _us_sector_cache[key] = (time.time(), got)
                            return got
                        data = heatmap.us(sys.modules[__name__], read_candles, known, sector_stocks)
                except Exception as e:
                    self._send_json({"ok": False, "error": safe_message(e)}, 502)
                    return
                self._send_json({"ok": True, "data": data, "meta": {
                    "market": mk, "cacheTtl": heatmap.HEATMAP_TTL, "source": data.get("source")}})
                return

            if route in ("us-sectors", "us-sector-stocks"):
                # 「지금 뜨는 산업」 미국 칸 — 섹터 ETF 열둘(반도체 XSD 2026-10-27) (2026-10-08 지시 · `us_sectors.py` 머리글).
                # 구성 종목 등락률은 봉 표만 읽는다. ETF 열둘의 일봉만 KIS 를 탄다(봉 캐시가 수를 정한다)
                span = (qs.get("span") or ["d"])[0].strip()
                if span not in us_sectors.SPAN_BACK:
                    self._send_json({"ok": False, "error": "span 은 d · w · m 중 하나여야 합니다."}, 400)
                    return
                known = us_universe.symbol_map()
                if route == "us-sectors":
                    rows = _ttl_get(_us_sector_cache, span, SECTOR_TTL)
                    if rows is None:
                        rows = us_sectors.groups(
                            span, lambda c, p, n: get_chart(cfg, c, p, n), read_candles, known)
                        _us_sector_cache[span] = (time.time(), rows)
                    self._send_json({"ok": True, "data": rows, "meta": {
                        "market": "us", "span": span, "total": len(rows), "count": len(rows),
                        "source": "State Street · KIS", "cacheTtl": SECTOR_TTL}})
                    return
                no = (qs.get("no") or [""])[0].strip().upper()
                if no not in us_sectors.SECTOR_NAME:
                    self._send_json({"ok": False, "error": "no 는 섹터 ETF 티커여야 합니다."}, 400)
                    return
                key = "%s:%s" % (no, span)
                got = _ttl_get(_us_sector_cache, key, SECTOR_TTL)
                if got is None:
                    got = us_sectors.stocks(no, span, read_candles, known)
                    _us_sector_cache[key] = (time.time(), got)
                self._send_json({"ok": True, "data": got["rows"], "meta": {
                    "no": no, "name": got["name"], "span": span, "asof": got["asof"],
                    "count": len(got["rows"]),
                    "priced": sum(1 for r in got["rows"] if r["pct"] is not None),
                    "source": "State Street · KIS"}})
                return

            if route == "us-board":
                # 나스닥100 순위 표 — DB 만 읽는다(KIS 0건). 미리받기가 쌓은 5분봉 · 일봉 (2026-10-07)
                idx = (qs.get("index") or [us_universe.NDX100])[0].strip().upper()
                if idx not in us_universe.US_INDEXES:
                    self._send_json({"ok": False, "error": "index 는 %s 중 하나여야 합니다."
                                     % ", ".join(us_universe.US_INDEXES)}, 400)
                    return
                rows = us_universe.us_board(idx)
                self._send_json({"ok": True, "data": rows, "meta": {"index": idx,
                    "count": len(rows), "priced": sum(1 for r in rows if r["price"] is not None),
                    "asof": max((r["asof"] for r in rows if r["asof"]), default=None),
                    "session": us_universe.session_state()[0], "kisCalls": 0,
                    "valueIsEstimate": True}})
                return

            if route == "quotes":
                raw = (qs.get("codes") or [""])[0]
                codes = [c.strip() for c in raw.split(",") if c.strip()]
                us_codes = list(dict.fromkeys(c for c in codes if us_universe.is_us(c)))
                codes = [c for c in codes if c.isdigit() and len(c) == 6]
                if us_codes and not codes:          # 미국만 — 국내 길을 안 탄다 (2026-10-07)
                    data, errors = _us_quotes(cfg, us_codes)
                    self._send_json({"ok": True, "data": data, "errors": errors or None,
                                     "meta": {"requested": len(us_codes), "us": len(data)}})
                    return
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
                us_codes = list(dict.fromkeys(c for c in codes if us_universe.is_us(c)))
                codes = [c for c in codes if c.isdigit() and len(c) == 6]
                if us_codes and not codes:          # 미국만 — 국내 길을 안 탄다 (2026-10-07)
                    data, errors = _us_quotes(cfg, us_codes)
                    self._send_json({"ok": True, "data": data, "errors": errors or None,
                                     "meta": {"requested": len(us_codes), "us": len(data)}})
                    return
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
            if _db_missing(e):
                self._send_json(_DB_MISSING_BODY)
                return
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
    global INVESTOR_EST_TTL, INVESTOR_MEMBER_TTL

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
    INVESTOR_MEMBER_TTL = SLOW_TTL      # 60 → 300
    ASKING_TTL = SLOW_SHORT_TTL         #  3 → 60. 호가는 원래 아주 짧다
    FUTURES_TTL = SLOW_SHORT_TTL        #   5 → 60. 화면이 1초마다 물어보는 자리다
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
    # 통합(UN)이 과거를 잘라 줘서 잠긴 backfill 표를 한 번 푼다 (위 주석 참조).
    # **겹친 봉 정리보다 먼저 둔다** — 푼 뒤에 다시 받아야 겹침이 생기는데,
    # 받는 것은 조회 때이고 정리는 지금이라 순서가 섞이지 않는다.
    try:
        _unlocked = _unlock_bars_backfill()
        if _unlocked:
            print("  주·월·년봉 다시 받기: 잠겨 있던 %d개를 풀었습니다" % _unlocked)
    except Exception as e:
        print("  주·월·년봉 다시 받기: 건너뜁니다 (%s)" % type(e).__name__)

    # 한 구간에 여러 줄이 쌓인 것을 치운다 (SPAN_CUT 주석 참조).
    # 고침이 들어오기 전에 쌓인 것은 저절로 안 없어진다 — 여기서 한 번 치운다.
    try:
        _dupes = _prune_span_dupes()
        if _dupes:
            print("  겹친 봉 정리: 월·년봉에서 %d줄을 치웠습니다" % _dupes)
    except Exception as e:
        print("  겹친 봉 정리: 건너뜁니다 (%s)" % type(e).__name__)

    # 부분 누적으로 저장된 지수 년·월봉을 한 번 다시 받는다 (위 주석 참조).
    # **한 번만 돈다.** 두 번째부터는 표를 보고 건너뛴다.
    try:
        _fixed = _refresh_index_spans(cfg)
        if _fixed:
            print("  지수 봉 정리: 년·월봉 %d개를 다시 받았습니다" % _fixed)
    except Exception as e:
        print("  지수 봉 정리: 건너뜁니다 (%s)" % type(e).__name__)

    if SLOW:
        print("  느린 모드  : 시세 %d초 · 미리받기/공시/뉴스수집 **끔** (--slow)"
              % SLOW_TTL)
    elif start_prefill(cfg):
        print("  5분봉 준비 : 순위 목록(시가총액 %d억 이상 · 코스피 · 코스닥)을 뒤에서 미리 받습니다"
              % dart.UNIVERSE_MIN_CAP_EOK)

    # 「장외」 칩 — 애프터 마감 뒤 한 번 순위 목록의 장외 값을 받아 쥔다 (2026-10-26 · 통합 멀티 12건쯤)
    if start_after_snap(cfg):
        print("  장외 값    : %02d:%02d 뒤 한 번 받아 다음 정규장 중에 보입니다" % AFTER_SNAP_AT)

    # 투자자 지표 모달 판을 한 번 미리 짓는다 — 뜬 직후 첫 열기가 기다리지 않게 (2026-10-16)
    if cfg and not SLOW:
        threading.Thread(target=lambda: (time.sleep(20), investor_board(cfg)), daemon=True,
                         name="investor-board-warm").start()
        start_investor_board_refresh(cfg)

    # 순위표 섹터 — 순위 목록의 WICS 를 뒤에서 한 종목씩 채운다 · 네이버만 · --slow 는 더 느리게 (2026-11-04)
    company_profile.start_sector_fill(lambda: [r["stock_code"] for r in dart.universe_rows(None)], slow=SLOW)

    # 미국 종목 목록(나스닥100 · 거래소 코드) — 하루 한 번 · KIS 호출 없음 (2026-10-07)
    # 「지금 뜨는 산업」 국내 주간 · 월간 — 장 마감 뒤 하루 한 번 · 네이버만 (2026-10-08)
    if not SLOW and naver_period.start(args.port, MAIN_PORT):
        print("  업종 기간  : 국내 업종 · 테마 주간 · 월간을 장 마감 뒤 하루 한 번 받습니다(네이버)")
    if not SLOW and us_universe.start():
        print("  미국 목록  : 나스닥100 과 거래소 코드를 하루 한 번 받습니다")
    if not SLOW and start_us_prefill(cfg, args.port):
        print("  미국 받기  : 장 전(동부 07:15~09:15) 일·주·월·년봉·시총을 나눠 받고, 장중(09:30~16:05)에는 5분봉만 5분마다")

    if start_bar_fill(cfg, args.port):
        print("  봉 채우기  : 켜짐 — 한가할 때 지난 5분봉(최근 %d거래일) · 미국 일·주·월(%d봉)을 메웁니다"
              % (PERIODS["5m"]["view_days"], DWMY_WANT))
    else:
        print("  봉 채우기  : 꺼져 있습니다 (KJC_BAR_FILL=0 이거나 8765 가 아님)")

    if not DWMY_ON:
        print("  일주월년   : **꺼져 있습니다** (켜려면 KJC_DWMY=1)")
    elif start_dwmy_prefill(cfg):
        print("  일주월년   : %d:%02d 에 %d종목을 한 바퀴 받습니다 (최대 %d봉까지)"
              % (DWMY_AT_MIN // 60, DWMY_AT_MIN % 60, len(_dwmy_codes()), DWMY_WANT))

    # 뉴스 쌓기 — **주말·밤에도 돈다.** 공시 폴러와 달리 DART 키가 없어도 돈다
    #
    # ⚠️ **발송은 메인(8765)에서만 한다** (2026-09-23 지시 — 재권님
    # 「보면 두개씩 온거 있잔아 이거 고쳐줘」).
    #
    # **쌓는 것은 `--slow` 가 아니고 DB 에 쓸 수 있는 서버만 한다** (2026-10-12).
    # 읽기 전용 서버(`KJC_DB_READONLY` · 서비스방 8764)는 메인 DB 를 `mode=ro` 로 열어
    # 쌓으려 할 때마다 `OperationalError`(읽기 전용 DB 에 쓰기)로 죽었다 — 10-10 11:38 부터
    # 8764 로그에 200번 넘게. 그 서버 화면은 8765 가 쌓은 같은 DB 를 읽으므로 잃는 것이 없다.
    # **발송만** 가린다. 데일리(아래 `send=`)와 **같은 꼴**이다.
    #
    # 그 전에는 `news_store` 가 `dart.telegram_send` 를 직접 불러서
    # **`--slow` 아닌 서버가 전부 보냈다.** 실측으로 셋이었다 —
    # 8765 · 8767 · 8770. 같은 기사가 **1분 차이로 따로** 발송됐고,
    # `market.db` 가 폴더마다 따로라 「보냈다」 표시도 안 나뉘었다.
    #
    # **정기 발송(07:30 · 13:30 · 22:00)도 같은 자리다.** 첫 칸이
    # `daily.py` 의 `SEND_AT` 와 **같은 시각**이라, 안 가리면 그 시각에
    # **데일리 1 + 뉴스 3 = 4통**이 간다.
    #
    # **보내는 자리 깃발을 여기서 먼저 넣는다** (2026-10-12) — `dart.telegram_config()` 가 이 값을 보고
    # 보내는 서버가 아니면 텔레그램 칸을 아예 안 읽는다(「한곳에서만 알림을 보낸다」). 아래 공시 쪽 긴 주석의 그 값이다.
    dart.NOTIFY_LOCAL = is_sender(args.port)
    _news_send = (dart.telegram_send
                  if (dart.telegram_config() and is_sender(args.port))
                  else None)
    if not SLOW and not marketdb.writable():
        print("  뉴스 수집 : 꺼짐 (읽기 전용 DB — 쌓는 것은 메인(%d))" % MAIN_PORT)
    elif not SLOW and news_store.start_collector(send=_news_send):
        print("  뉴스 수집 : 사용 (%d분마다 · 주말 포함 · 텔레그램 %s)"
              % (news_store.COLLECT_INTERVAL // 60,
                 (" · ".join("%02d:%02d" % t for t in news_store.DIGEST_SLOTS)
                  if _news_send else "쌓기만 — 메인(%d)에서만 보냅니다" % MAIN_PORT)))

    # **공시 발송도 포트로 가린다** (2026-09-30 지시 — 워커를 걷어냈다).
    #
    # 그 전에는 `dart.NOTIFY_LOCAL` 을 통째로 끄고 배포본 워커가 보냈다.
    # 사이트가 맥미니로 넘어오면서 **워커 Route 를 지웠으므로** 이제 여기가 보낸다.
    #
    # ⚠️ **`NOTIFY_LOCAL = True` 로 바꾸는 것만으로는 두 번 간다.**
    # `--slow` 가 아닌 서버가 **둘**이고 둘 다 공시를 수집한다 —
    # 2026-09-30 15:43 실측에서 **8765 와 8767 의 `lastReceivedAt` 이 2초 차이**였다.
    # `dart.py:95` 에 「다시 켜기 전에 포트를 가리는 형태로 바꾼다」 가 적혀 있었고,
    # 그것이 이 줄이다.
    #
    # **데일리·뉴스·신호와 같은 방식이다** — 넷 다 `is_sender()` 하나를 본다.
    # 「룰은 하나다」 의 **같은 기준, 같은 구현**이다.
    #
    # **수집은 포트로 안 가린다** — 다만 읽기 전용 DB 서버는 수집하지 않는다(아래 · 2026-10-12).
    # 그 서버 화면은 8765 가 쌓는 같은 DB 를 읽는다. 발송은 포트로 가른다.
    # `dart.NOTIFY_LOCAL = is_sender(args.port)` 는 위 뉴스 쌓기 앞으로 옮겼다(2026-10-12) — 텔레그램 칸 읽기가 그 값을 본다.

    if SLOW:
        pass                 # 확인용 서버는 공시도 안 받는다 (위 주석 참고)
    elif not marketdb.writable():
        # 뉴스와 같은 까닭 — 읽기 전용 DB 에 공시를 쌓으려다 매번 죽었다 (2026-10-12)
        print("  공시 수집 : 꺼짐 (읽기 전용 DB — 쌓는 것은 메인(%d))" % MAIN_PORT)
    elif dart.start_poller():
        print("  공시 수집 : 사용 (코스피 상위 %d종목 · %d분마다)"
              % (dart.UNIVERSE_SIZE, dart.POLL_INTERVAL // 60))
        print("  지배구조   : %s" % ("밤마다 받음(20:00~07:00)" if dart_gov.start_filler()
                                    else "꺼짐 — dart_gov.GOV_FETCH(켜기는 재권님 지시)"))
        # **`NOTIFY_LOCAL` 을 함께 본다** (2026-09-22).
        #
        # 전에는 열쇠(`secrets.json`)만 보고 「텔레그램 켜짐」 으로 찍었다.
        # `NOTIFY_LOCAL = False` 로 **공시 발송을 꺼 둔 날에도 「켜짐」** 이라,
        # 텔레그램이 두 번 오는 일을 볼 때 **로그가 로컬을 범인으로 가리켰다.**
        # 오늘 이 줄 때문에 여러 사람이 한 번씩 헛짚었다.
        if not dart.NOTIFY_LOCAL:
            _al = "쌓기만 — 메인(%d)에서만 보냅니다" % MAIN_PORT
        elif not dart.telegram_config():
            _al = "꺼짐 (secrets.json 의 telegram 없음)"
        else:
            _al = "텔레그램 켜짐 (관심종목 %d개)" % len(dart.watchlist())
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
    #
    # **보드를 넘기는 서버도 안 돈다** (2026-10-06 재권님 「응 해줘」). 데일리 화면은
    # `/api/board/doc/daily-*` 로 읽어 그 서버에서는 상류(8765) 것을 본다 — 자기 폴더에
    # 저장해도 **아무도 안 읽는 사본**이었다(서비스방 8764 가 매일 07:3x 에 썼다).
    # **포트를 먼저 정한다** — `board_upstream_base()` 가 「자기 자신을 가리키는가」 를
    # `RUN_PORT` 로 가린다. 전에는 이 아래(하트비트 앞)에서 정했다.
    global RUN_PORT
    RUN_PORT = args.port
    if not SLOW and not board_upstream_base():
        daily.start_daily(
            # **`[0]` 을 빠뜨리지 않는다.** 이 둘은 `(목록, 오류)` 를 준다.
            # 안 벗기면 튜플이 그대로 넘어가 `daily` 가 `x.get()` 에서 죽고,
            # `once()` 의 `except` 가 그것을 삼켜 **아무 일도 안 일어난다** —
            # 로그에는 「07:30 에 저장」 이 찍히는데 저장본이 안 생긴다.
            # 2026-09-22 에 그렇게 하루 종일 조용히 실패했다.
            #
            # **`fetch_indices_all`** — 화면이 보는 것과 같게 해외·환율까지 담는다.
            # `fetch_indices` 만 부르면 **국내 넷뿐**이고 해외 줄이 통째로 빈다.
            get_indices=lambda: _daily_indices(load_secrets()),
            get_sectors=lambda: fetch_sectors(load_secrets())[0],
            # **`rows` 다.** 화면이 받는 `/api/news/issues` 의 `data` 는 배열인데,
            # 그것을 만드는 `fetch_issues()` 는 `{rows, errors, topics}` 를 준다.
            # 처음에 `issues` 로 적었다가 실제로 불러 보고 잡았다 (2026-09-22).
            get_issues=lambda: (news.fetch_issues() or {}).get("rows") or [],
            get_strong=lambda: _daily_strong(load_secrets()),
            # 야간선물은 07:00 미국 데일리로 옮겼다(아래 start_us_daily · 2026-11-07)
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
                  if (dart.telegram_config() and is_sender(args.port))
                  else None),
        )
        # 보내는 서버가 아니면 텔레그램 칸을 안 읽으므로(dart.telegram_config) 까닭을 먼저 가른다
        _tg = ("텔레그램 켜짐" if (dart.telegram_config() and is_sender(args.port))
               else ("저장만 — 이 기계는 %s 입니다" % ROLE
                     if not IS_SERVER
                     else ("저장만 — 메인(%d)에서만 보냅니다" % MAIN_PORT
                           if not is_sender(args.port) else "저장만 — 열쇠 없음")))
        print("  데일리분석 : 평일 %02d:%02d 에 저장 · 최근 %d장 (%s)"
              % (daily.SEND_AT // 60, daily.SEND_AT % 60, daily.KEEP, _tg))
        # 미국 데일리 — 07:00 해외 마감 · 야간선물 · 밤사이 결과 한 통 (2026-11-07 재권님 「(가)」 · daily.start_us_daily)
        # 밤사이 결과는 보내는 서버에서만 꺼내 간다 — events 바퀴도 그 서버에서만 돈다
        _us_send = (dart.telegram_send if (dart.telegram_config() and is_sender(args.port)) else None)
        daily.start_us_daily(
            get_indices=lambda: fetch_indices_all(load_secrets(), with_chart=False)[0],
            get_night=lambda: nxt_board.latest_futures(sys.modules[__name__]),
            peek_overnight=(events.peek_overnight if (is_sender(args.port) and not SLOW) else None),
            clear_overnight=(events.clear_overnight if (is_sender(args.port) and not SLOW) else None),
            send=_us_send,
        )
        print("  미국 데일리 : 화~토 %02d:%02d 에 저장 (%s)"
              % (daily.US_SEND_AT // 60, daily.US_SEND_AT % 60, _tg))

    # 볼린저·MACD·RSI 가 동시에 맞는 자리를 본다 (2026-09-22 지시).
    # **KIS 를 새로 안 부른다** — 미리받기가 쌓아 둔 5분봉을 읽기만 한다.
    #
    # **`SLOW` 로는 못 막는다 — 포트로 가른다** (2026-09-23).
    #
    # 전에는 `not SLOW` 만 봤다. 「확인용 서버는 안 돈다」 는 뜻이었는데
    # **`--slow` 없이 뜬 세션 서버가 있으면 그대로 샌다.**
    #
    #     `--slow` 아닌 서버      8765 · 8767 · 8770      **셋**
    #     그중 열쇠가 살아 있는 것  8765 · 8770            **둘**
    #     → 신호마다 **폰에 두 번** 간다
    #
    # **데일리가 이미 이 방식이다**(위 `daily.start_daily` 의 `send=`).
    # 같은 결함이 옆 파일에 남아 있었다 — 2026-09-22 에 **8770 이 `--slow`
    # 없이 떠 있어 공시가 두 번 간** 그 자리와 같다.
    #
    # **열쇠를 비우는 것으로 막지 않는다.** 폴더마다 갈려 있고
    # (`kjc-home` 은 비었는데 `kjc-dev3` 은 살아 있다) **키 파일을 만지게 된다.**
    # 실적 · FOMC · 미국 지표 결과 알림 (2026-10-25 재권님 「가」 · server/events.py) — 신호 감시와 같은 문 하나(보내는 서버만).
    # **`events.SEND = False` 가 기본이다** — 바퀴는 돌되 안 보내고, 보냈을 글을 /api/events/status 에 남긴다. 켜기는 재권님 지시로
    if not SLOW and is_sender(args.port) and events.start():
        # 조용한 시간은 `dart.QUIET_FROM`·`QUIET_TO` 에서 만든다 — 여기 박으면 그쪽을 고쳤을 때 이 줄만 낡는다
        # 밤 결과는 07:00 미국 데일리 한 통에 실린다 · 못 실은 날만 events.OVERNIGHT_FLUSH_AT 에 따로(2026-11-07 c0d4d81) — 시각은 그 상수들에서
        print("  결과 알림 : 사용 (%d초마다 · 밤 %02d~%02d시 것은 %02d:%02d 미국 데일리에 실음 · 못 실으면 %02d:%02d 따로%s)"
              % (events.TICK, dart.QUIET_FROM // 60, dart.QUIET_TO // 60,
                 daily.US_SEND_AT // 60, daily.US_SEND_AT % 60,
                 events.OVERNIGHT_FLUSH_AT // 60, events.OVERNIGHT_FLUSH_AT % 60,
                 "" if events.SEND else " · **발송 꺼짐 — 미리보기만**"))

    # 시황 글 알림(2026-10-27 · server/note_alert.py) — 같은 문(보내는 서버만) · 켜기 스위치가 따로 없다(재권님 「가」 = 8765 가 보낸다)
    if not SLOW and is_sender(args.port) and note_alert.start():
        print("  시황 글 알림 : 사용 (%d초마다 market-note-live.json 의 at · 밤 %02d~%02d시 것은 %02d:00)"
              % (note_alert.TICK, dart.QUIET_FROM // 60, dart.QUIET_TO // 60, dart.QUIET_TO // 60))

    # 넥스트레이드 장 전 거래량 2배 목록(2026-10-26 · server/nxt_pre.py) — 같은 문(보내는 서버만) · **`nxt_pre.SEND = False` 가 기본**
    # 수급 — 넥스트 5분 거래량(2026-10-27 · server/theme_flow.py) · 같은 문(보내는 서버만) · 알림은 없다(화면만)
    if not SLOW and is_sender(args.port) and theme_flow.start(sys.modules[__name__]):
        print("  수급 : 사용 (평일 %02d:%02d~%02d:%02d %d분마다 넥스트 거래량 · 어제 같은 구간 %s배 · /api/nxt/flow)"
              % (theme_flow.OPEN + theme_flow.CLOSE + (theme_flow.SLOT_MIN, theme_flow.RATIO)))

    if not SLOW and is_sender(args.port) and nxt_board.start(sys.modules[__name__]):
        print("  넥장 보드 : 사용 (평일 %02d:%02d 종가 · %02d:%02d 장외 · %02d:%02d 야간선물 저장 · /api/nxt/board)"
              % (nxt_board.CLOSE_AT + nxt_board.AFTER_AT + nxt_board.FUT_AT))
    # 자동 관심종목(2026-11-05 · server/auto_watch.py) — 같은 문(보내는 서버만) · 값 쌓기만 · 관심 목록 넣기는 아직 없다(auto_watch.ADD)
    # 경제 지표 미리 받기(2026-11-05 · server/macro.py start) — 받는 곳은 8765 하나 · 다른 서버는 넘겨 받는다 · 요청이 바깥 35번을 기다리지 않게
    if not SLOW and is_sender(args.port) and macro.start():
        print("  경제 지표     : 미리 받기 (뜰 때 · %d초마다 기한 확인 · 기한이 지나도 들고 있던 값을 내고 뒤에서 받음)" % macro.TICK)
    # 「좋은 뉴스」 판정(2026-11-05 · server/good_news.py) — 같은 문(보내는 서버만) · 공급계약 · 자사주 상세를 5분마다 받아 쌓기만 · 알림 없음
    if not SLOW and is_sender(args.port) and good_news.start(sys.modules[__name__]):
        print("  좋은 뉴스 판정 : 사용 (5분마다 공급계약 본문 · 자사주 취득 상세 받기 · /api/good-news)")
    # 공포·탐욕 25 풀림 알림(2026-11-06 · server/fear_greed.py) — 같은 문(보내는 서버만) · 평일 15:45 뒤 한 번 · SEND 가 꺼져 있으면 기록만
    if not SLOW and is_sender(args.port) and fear_greed.start(sys.modules[__name__]):
        print("  공포·탐욕    : 25 풀림 보기 (평일 %02d:%02d 뒤 한 번 · 알림 %s · /api/market/fear-greed)"
              % (fear_greed.ALERT_AT + ("켜짐" if fear_greed.SEND else "꺼짐",)))
    if not SLOW and is_sender(args.port) and auto_watch.start(sys.modules[__name__]):
        print("  자동 관심종목 : 사용 (평일 %02d:%02d 코스피 시총 200 · 코스닥 150 값 쌓기 · /api/auto-watch%s)"
              % (auto_watch.RUN_AT + ("" if auto_watch.ADD else " · **관심 목록 넣기 없음**",)))
    # 당일 수급(2026-10-27 · server/intraday_flow.py) — 같은 문(보내는 서버만) · 알림 없음.
    # `KJC_FLOW_COLLECT=1` 은 시험 서버(자기 DB)에서 바퀴를 돌려 보는 자리다 — 세션 서버는 메인 DB 를 읽기 전용으로 열어 쓸 수 없다
    if not SLOW and is_sender(args.port) and pre_flow.start(sys.modules[__name__]):
        print("  프리장 판   : 평일 %02d:%02d~%02d:%02d 에 %d초마다 지어 market.db pre_flow_board 에 남김(「프리장」 칩)"
              % (pre_flow.PRE_OPEN + pre_flow.PRE_CLOSE + (pre_flow.FLOW_TTL,)))
    if not SLOW and is_sender(args.port) and dt30.start(sys.modules[__name__]):
        print("  단타 30 판 : 평일 %s 단타 상위 %d 굳힘 · %s~%s %d분마다 값 · %d거래일 · /api/kis/dt30"
              % (dt30.status()["buyAt"], dt30.TOP_N, dt30.times()[0], dt30.times()[-1], dt30.TRACK_STEP, dt30.DAYS_KEEP))
    if not SLOW and is_sender(args.port) and open_rise.start(sys.modules[__name__]):
        print("  초반상승   : 첫 5분봉이 끝나는 순간(+%d초) 대상 종목 첫 봉을 먼저 받음 · %d분 뒤 그만" % (open_rise.FIRST_GRACE_SEC, open_rise.FIRST_UNTIL_MIN))
    if not SLOW and is_sender(args.port) and day_top_fill.start(sys.modules[__name__]):
        print("  등락 상위 되채움: 지난 %d거래일 · %s" % (day_top_fill.FILL_DAYS, day_top_fill.status()["window"]))
    if not SLOW and is_sender(args.port) and day_top.start(sys.modules[__name__]):
        print("  등락 상위 : 평일 %02d:%02d 뒤(「매수」 판이 굳으면 · 늦어도 %02d:%02d) 시가총액 %d억 이상 등락률 판과 걸린 필터를 market.db day_top 에 남김 · /api/kis/day-top"
              % (day_top.SAVE_AT + day_top.SAVE_LATE + (day_top.MIN_CAP_EOK,)))
    if not SLOW and is_sender(args.port) and watch_log.start(sys.modules[__name__]):
        print("  종목 기록   : 평일 %02d:%02d 에 관심 · 자동 · VI · 급등 · 매수 종목 줄을 market.db watch_log 에 남김 · /api/watch-log" % watch_log.SAVE_AT)
    if (not SLOW and is_sender(args.port) or os.environ.get("KJC_FLOW_COLLECT") == "1") and flow_rank.start(sys.modules[__name__]):
        print("  투자자 매매 동향 : 평일 %02d:%02d 뒤 외국인 · 기관 순위 판을 market.db flow_rank 에 남김 · %02d:%02d 뒤 순위 · 감시 종목 주체 확정치 쌓음"
              % (flow_rank.SAVE_AT + flow_rank.COLLECT_AT))
    if (not SLOW and is_sender(args.port) or os.environ.get("KJC_FLOW_COLLECT") == "1") and session_volume.start(sys.modules[__name__]):
        print("  시간대 거래량 : 평일 %s 에 순위 종목 누적 거래량 저장(전일비)" % " · ".join(b[3][:2] + ":" + b[3][2:] for b in session_volume.BOUNDS))
    if (not SLOW and is_sender(args.port) or os.environ.get("KJC_FLOW_COLLECT") == "1") and intraday_flow.start(sys.modules[__name__]):
        print("  당일 수급 : 사용 (평일 09:00~15:30 · 1분마다 시장 투자자 · 종목 프로그램 · %d분마다 시장 프로그램 · /api/kis/flow-today)"
              % intraday_flow.PGM_EVERY)
    if not SLOW and is_sender(args.port) and nxt_pre.start(sys.modules[__name__]):
        print("  장 전 거래량 : 사용 (평일 %02d:%02d 한 번 · 전날의 %.0f배 · 전날 %s주 이상%s)"
              % (nxt_pre.RUN_AT[0], nxt_pre.RUN_AT[1], nxt_pre.RATIO, format(nxt_pre.MIN_PREV, ","),
                 "" if nxt_pre.SEND else " · **발송 꺼짐 — 미리보기만**"))

    # 장중 알림 — 상승 VI · +20% 급등 (2026-10-26 · server/intraday_alerts.py) — 같은 문 하나(보내는 서버만).
    # 발송 스위치는 `intraday_alerts.SEND`(VI 끔 10-27 · 급등 켬 10-26). 꺼 두면 바퀴는 돌되 안 보내고 /api/alerts/status 에 보냈을 글을 남긴다
    if not SLOW and is_sender(args.port) and market_hours.start(sys.modules[__name__]):
        print("  장 시각   : 휴장일 하루 한 번(%02d:%02d 뒤 · KIS) · 바뀐 시각 표 /api/board/doc/%s · 거래소 공시 거래시간 글 · /api/alerts/market-hours"
              % (market_hours.HOLIDAY_AT + (market_hours.DOC,)))
    if not SLOW and is_sender(args.port) and market_event.start(sys.modules[__name__], args.port):
        print("  시장 사건 : 서킷브레이커 추정(코스피 · 코스닥 %d초마다) · 거래소 공시 확인(%d초마다) · 발송 %s · /api/alerts/market-event"
              % (market_event.TICK_SEC, market_event.KIND_SEC, "켬" if market_event.SEND else "끔"))
    if not SLOW and is_sender(args.port) and intraday_alerts.start(sys.modules[__name__]):
        _st = intraday_alerts.status()
        print("  장중 알림 : 사용 (상승 VI · +%d%% 급등 · %d초마다 · %s · 발송 %s)"
              % (intraday_alerts.SURGE_PCT, intraday_alerts.TICK, _st["session"],
                 " · ".join("%s %s" % (k, "켜짐" if v else "**꺼짐**") for k, v in _st["send"].items())))

    # 공매도 — 감시 대상 종목마다 KIS 「공매도 일별추이」 를 쌓는다(쓰기 서버만 · 처음 1년치 약 1,050번 · 그 뒤 새 날마다 350번쯤)
    if not SLOW and is_sender(args.port) and short_sale.start(sys.modules[__name__]):
        print("  공매도 : 사용 (감시 대상 종목마다 일별 · %d초마다 기준 종목(%s)으로 새 날을 봄 · 쌓는 표 short_daily)"
              % (short_sale.TICK_SEC, short_sale.SENTINEL))

    # 실시간 체결 — 키 읽기 · 시세 기준을 넘겨 둔다. 연결은 화면이 처음 물을 때 붙는다(아무도 안 보면 안 붙는다)
    kis_ws.configure(load_secrets, quote_market_div)
    if kis_ws.KIS_WS_ON:
        print("  실시간 체결 : 사용 (보는 종목만 · 최대 %d종목 · %d초 안 보면 뺌 · 끊기면 %d→%d초 쉬고 다시)"
              % (kis_ws.LIVE_MAX_CODES, kis_ws.LIVE_IDLE_SEC, kis_ws.RECONNECT_MIN_SEC, kis_ws.RECONNECT_MAX_SEC))

    if not SLOW and is_sender(args.port) and signal_watch.start(sys.modules[__name__]):
        # **시각을 여기 박지 않는다.** `SESSION_FROM`·`SESSION_TO` 에서 만든다 —
        # 박으면 그쪽을 고쳤을 때 이 줄만 낡는다. 2026-09-23 에 대상을 50 으로
        # 넓히고 시간을 08~20 으로 바꾸면서 **이 줄이 「관심종목 … 장중만」 인
        # 채로 남았다.** 「값을 바꾸고 옆 설명을 안 고친」 자리다.
        print("  신호 감시 : 사용 (감시 대상 %d개 · 바닥 신호 %d개 · %d초마다 · %02d~%02d시%s)"
              % (len(signal_watch.watch_codes(sys.modules[__name__])),
                 len(signal_watch.low_codes(sys.modules[__name__])),
                 signal_watch.LOOP_SEC,
                 signal_watch.SESSION_FROM // 60, signal_watch.SESSION_TO // 60,
                 "" if signal_watch.SEND else " · **발송 꺼짐**"))

    # PC 가 꺼진 것을 **밖에서** 알 수 있게, 5분마다 Cloudflare KV 에
    # 「살아 있다 + 내 상태」 를 쓴다 (2026-09-23 지시 — 「pc는 항상 켜져있는걸
    # 전제로 해야하고 꺼지거나 이슈가 있으면 알림이 오면 될거같은데」).
    #
    # **메인 포트에서만 돈다.** 폴더가 여섯인데 KV 키는 하나라, 여럿이 쓰면
    # **메인이 꺼져도 세션 서버가 덮어써서 알림이 안 온다.**
    # `--slow` 로는 안 가른다 — 메인이 `--slow` 로 떠도 살아 있음은 보내야 한다.
    #
    # 판단도 조립도 `heartbeat.py` 에 있다. 이 파일은 여러 세션이 함께 쓰므로
    # 부르는 줄만 둔다 — `signal_watch` · `daily` 와 같은 꼴이다.
    # (`RUN_PORT` 는 데일리 시작 앞에서 정한다 — 아래가 아니라 위에 있다.)

    if heartbeat.start(sys.modules[__name__], args.port):
        print("  살아있음  : %d분마다 Cloudflare 에 신호 (꺼지면 알림)"
              % (heartbeat.BEAT_SEC // 60))

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
