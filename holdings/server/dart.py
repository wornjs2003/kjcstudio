#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenDART 공시 수집.

무엇을 하는가
  1. 기업 대응표를 하루 한 번 받아 둔다 (corp_code ↔ 종목코드 ↔ 회사명)
  2. 시가총액 상위 목록(코스피 200 · 코스닥 150 · UNIVERSE_SIZES)을 하루 한 번 정해 둔다
     — 공시를 거르는 데는 안 쓴다(아래 3)
  3. 5분마다 "오늘 올라온 공시"를 통째로 받아 **종목코드가 있는 것을 전부** 저장한다
     (2026-09-15 지시 · save_disclosures 를 only_codes 없이 부른다 — 처음엔 감시 대상만 남겼다)
  4. 새로 들어온 공시가 관심종목이면 텔레그램으로 보낸다

왜 이렇게 하는가
  종목마다 따로 물으면 200종목 × 하루 288번 = 57,600건이라 하루 한도(약 20,000건)를
  넘긴다. 기간으로 한 번에 받아 우리 쪽에서 거르면 하루 1,200건 안쪽이다.

한도
  OpenDART 는 하루 약 20,000건. 넘기면 status 020 을 돌려준다.
  실시간 푸시는 없다. 주기적으로 물어보는 수밖에 없다.
"""

import html
import io
import json
import os
import re
import sqlite3

import marketdb
import tglog                # 오늘 보낸 텔레그램 글 기록(2026-10-26) — telegram_send 가 적는다
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone

# 오류 문구에서 비밀을 지운다. 왜 필요한지는 그 파일 머리말에 적혀 있다.
from secrets_guard import safe_message, scrub, secrets_path

KST = timezone(timedelta(hours=9))

HOLDINGS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 자리·journal_mode·쓰기 가능 여부는 **`marketdb` 한 곳**이 정한다 (2026-10-01).
DB_PATH = marketdb.DB_PATH

DART_API = "https://opendart.fss.or.kr/api"

# 하루 한도 — 공식은 「일반적으로 20,000건 이상이면 020 · 요청 제한이 다르게 설정된 경우는 그에 준한다」
# (OpenDART 개발 가이드 · 메시지 설명 · 2026-10-15 확인). 키마다 다를 수 있다 — 우리 키의 값은 OpenDART
# 「오픈API 이용현황」 에서만 보인다. 1분 제한(100건 등)은 남의 글에만 있고 공식 문서에서는 못 찾았다.
DART_DAILY_LIMIT = 20000
# 하루 이만큼까지만 쓴다 — 넘으면 그날은 받기를 멈추고 자정(KST)에 다시 센다.
# 재권님 2026-10-15 「절반만 안으로 만들어놔」. 무엇을 더 받을지는 나중에 정하신다.
DART_DAILY_BUDGET = DART_DAILY_LIMIT // 2

# 공시 원문 보기 주소. rcept_no 하나만 있으면 열린다.
VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=%s"

# 감시 대상 — 시장마다 시가총액 상위 몇 종목까지 볼 것인가.
# 코스닥 150 은 2026-10-06 에 더했다 (재권님 「코스피 200 종목 불러오는데 코스닥 150 도」 · 「가」 =
# 지수 구성종목이 아니라 코스피 쪽과 같은 **시가총액 상위**). 순위는 시장마다 1부터 센다.
UNIVERSE_SIZES = (("KOSPI", 200), ("KOSDAQ", 150))
UNIVERSE_SIZE = 200          # 코스피 쪽 — 옛 이름이라 남긴다

# 어느 시장의 공시를 받을 것인가 (2026-09-15 지시로 넓혔다).
#   Y 유가증권(코스피) · K 코스닥 · N 코넥스 · E 기타
# 코넥스는 하루 한 건 남짓이고, 기타는 75건 중 68건이 비상장·펀드라
# 종목코드가 없다. 종목코드가 없으면 화면에 붙일 종목이 없어 쓸 수 없다.
COLLECT_MARKETS = ["Y", "K"]

# 며칠 치를 들고 있을 것인가. 넘긴 것은 폴링할 때 지운다.
# 전 종목으로 넓히면서 하루 400~600건이 쌓인다. 30일이면 1.5만 건쯤이다.
RETENTION_DAYS = 30

# 텔레그램을 보낼 종목.
# js/data/market.js 의 WATCHLIST 와 같아야 한다. 한쪽만 고치면 어긋난다.
# 카카오를 뺀 이유는 그 파일의 WATCHLIST 위 주석에 있다 (2026-09-23 지시).
WATCH_CODES = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035420",  # NAVER
    "005380",  # 현대차
    "373220",  # LG에너지솔루션
    "207940",  # 삼성바이오로직스
    "068270",  # 셀트리온
]

# 언제 물어볼 것인가.
# DART 접수는 평일에만 있다. 07:00 이전과 20:00 이후는 물어봐야 새 것이 없다.
# ── 이 PC 에서 공시 알림을 보낼 것인가 ──
#
# **끈다 (2026-09-22 지시 — 「두 번 오는 거 같은데」).**
#
# 배포본 Worker 가 24시간 돌며 같은 공시를 보낸다. **보낸 기록이 워커와
# 로컬에 따로 있어 서로를 모르므로**, 둘 다 켜져 있으면 재권님 폰에 **두 번**
# 간다. 인터넷 서버는 PC 가 꺼져 있어도 도니 그쪽을 남기고 이쪽을 끈다.
#
# **수집은 계속 돈다.** 화면이 그 공시를 쓴다 — 끄는 것은 **보내는 자리뿐**이다.
#
# **데일리 발송은 이것과 무관하다.** 같은 `telegram_send()` 를 쓰지만
# 여기서 막는 것은 공시(`notify`)뿐이라, 열쇠를 비우는 방식과 다르다.
# `secrets.json` 을 비우면 데일리까지 죽는다.
#
# ── 2026-09-30 에 여기가 다시 보내게 됐다 ────────────────────────────
#
# 사이트가 맥미니로 넘어오면서 **워커 Route 를 지웠다.** 위 「그쪽을 남기고
# 이쪽을 끈다」 의 「그쪽」 이 없어졌으므로 **이제 여기가 보낸다.**
#
# **다만 이 줄을 `True` 로 바꾸지 않았다.** 그러면 **두 번 간다** —
# `--slow` 가 아닌 서버가 둘이고 **둘 다 공시를 수집한다.**
# 2026-09-30 15:43 실측 — 8765 와 8767 의 `lastReceivedAt` 이 **2초 차이**였다.
#
# **그래서 포트로 가린다.** 위 ⚠️ 가 요구한 것이 그것이고, 그 자리는
# `kis_proxy.py` 의 공시 폴러를 켜는 곳이다.
#
#     dart.NOTIFY_LOCAL = is_sender(args.port)
#
# **이 줄은 그 값이 안 들어왔을 때의 안전한 기본값이다.** `dart.py` 를
# 단독으로 부르거나 `kis_proxy` 가 안 정해 주면 **안 보내는 쪽**으로 남는다 —
# 「모르면 안 보낸다」 가 「모르면 보낸다」 보다 낫다.
NOTIFY_LOCAL = False
#
# **데일리·뉴스·신호와 같은 방식이 됐다.** 넷 다 `is_sender()` 하나를 본다.
#
#     데일리   `send=` 를 넘긴다      →  8765 하나만 보낸다
#     뉴스     `send=` 를 넘긴다      →  〃
#     신호     `is_sender` 로 켠다    →  〃
#     공시     `NOTIFY_LOCAL` 을 정해 준다  →  〃
#
# **켜도 쌓인 것이 쏟아지지 않는다** (2026-09-30 실측). `notified = 0` 인
# 2,188건은 **이 스위치가 생기기 전**(`d48b5e6` · 9/22 16:51) 것이고,
# 그 뒤 것은 전부 `1` 이다. **`0` 을 다시 찾아 보내는 코드도 없다.**
#
# 켜는 날에는 데일리와 같은 꼴(`kis_proxy.py` 의 `MAIN_PORT`)로 맞춘다.

POLL_INTERVAL = 300          # 5분
POLL_FROM = 7 * 60           # 07:00
POLL_TO = 20 * 60            # 20:00

_db_lock = threading.Lock()

SCHEMA = [
    # 기업 대응표 — corpCode.xml 에서 받는다. 상장사만 남긴다.
    """CREATE TABLE IF NOT EXISTS dart_corps (
         corp_code   TEXT PRIMARY KEY,
         stock_code  TEXT,
         corp_name   TEXT,
         modify_date TEXT
       )""",
    "CREATE INDEX IF NOT EXISTS idx_corps_stock ON dart_corps (stock_code)",

    # 감시 대상 — 코스피 시가총액 순위
    """CREATE TABLE IF NOT EXISTS index_members (
         stock_code  TEXT NOT NULL,
         index_code  TEXT NOT NULL,        -- KPI200 | KQI150
         name        TEXT,
         updated_at  TEXT,
         PRIMARY KEY (stock_code, index_code)
       )""",
    """CREATE TABLE IF NOT EXISTS dart_universe (
         stock_code  TEXT PRIMARY KEY,
         name        TEXT,
         rank        INTEGER,               -- 시장 안의 순위 (1부터)
         market_cap  INTEGER,
         updated_at  TEXT,
         market      TEXT DEFAULT 'KOSPI'   -- KOSPI | KOSDAQ (2026-10-06)
       )""",

    # 받아온 공시. rcept_no 가 접수번호이자 원문 주소의 열쇠다.
    """CREATE TABLE IF NOT EXISTS dart_disclosures (
         rcept_no    TEXT PRIMARY KEY,
         corp_code   TEXT,
         stock_code  TEXT,
         corp_name   TEXT,
         report_nm   TEXT,
         flr_nm      TEXT,
         rcept_dt    TEXT,
         rm          TEXT,
         received_at TEXT,
         notified    INTEGER DEFAULT 0
       )""",
    "CREATE INDEX IF NOT EXISTS idx_disc_stock ON dart_disclosures (stock_code, rcept_no DESC)",
    "CREATE INDEX IF NOT EXISTS idx_disc_recent ON dart_disclosures (rcept_no DESC)",

    """CREATE TABLE IF NOT EXISTS sync_meta (
         key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
       )""",
]


def db_conn():
    """읽기 전용 서버면 `mode=ro` 로 열린다 — `marketdb` 가 정한다."""
    return marketdb.connect(timeout=10)


def db_init():
    with _db_lock, db_conn() as conn:
        for sql in SCHEMA:
            conn.execute(sql)
        # 옛 표에는 market 칸이 없다 — 쓸 수 있는 서버만 붙인다 (2026-10-06).
        # 읽기 전용 서버는 못 붙이므로 아래 읽기 함수가 칸이 없으면 전부 코스피로 읽는다.
        if marketdb.writable() and not _universe_has_market(conn):
            try:
                conn.execute("ALTER TABLE dart_universe ADD COLUMN market TEXT DEFAULT 'KOSPI'")
            except sqlite3.Error as e:
                print("[db] dart_universe market 칸 붙이기 실패 — %s" % safe_message(e, 120))


def _universe_has_market(conn):
    return any(r[1] == "market" for r in conn.execute("PRAGMA table_info(dart_universe)"))


def _meta_get(key):
    with _db_lock, db_conn() as conn:
        r = conn.execute("SELECT value FROM sync_meta WHERE key = ?", (key,)).fetchone()
    return r["value"] if r else None


def _meta_set(key, value):
    # 읽기 전용 서버는 **안 써 본다.** 깃발이 켜져 있어도 디스크 · 권한 ·
    # 잠금으로 실패할 수 있어 예외도 함께 잡는다 (`marketdb` 의 「깃발과 실패는
    # 다르다」).
    if not marketdb.writable():
        return
    try:
        _meta_set_write(key, value)
    except sqlite3.Error as e:
        print("[db] sync_meta 쓰기 실패 %s — %s" % (key, safe_message(e, 120)))


def _meta_set_write(key, value):
    with _db_lock, db_conn() as conn:
        conn.execute(
            """INSERT INTO sync_meta (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                                             updated_at=excluded.updated_at""",
            (key, str(value), datetime.now(KST).isoformat(timespec="seconds")),
        )


def _today():
    return datetime.now(KST).strftime("%Y%m%d")


# ---------------------------------------------------------------- 하루 사용량
#
# OpenDART 를 부르는 자리는 전부 `_dart_get` 을 거친다 — 여기서 하루 건수와 020 을 센다.
# 셈은 sync_meta 의 `dart_usage` 한 줄(JSON)에 두어 서버를 다시 켜도 그날 셈이 이어진다.
# **세는 곳은 공시를 받는 서버 하나다**(start_poller 가 `_COUNTING` 을 켠다 · 지금 8765).
# 공시를 안 받는 서버(8764 · 8767 · 세션)는 셈을 들고 있지 않고, 물을 때마다 sync_meta 를
# 다시 읽어 낸다 — 오늘 기록이 없으면 calls 는 0 이 아니라 null(못 셌다) 이다
# (「못 쟀으면 0 이 아니라 「못 쟀다」 고 낸다」 · 2026-10-15 개념정의 검수).

_usage_lock = threading.Lock()
_usage = None
_COUNTING = False


def _usage_now():
    """오늘 셈. 날짜가 바뀌었으면 0 부터. 부르는 쪽이 _usage_lock 을 쥔다."""
    global _usage
    today = _today()
    if _usage is None:
        try:
            _usage = json.loads(_meta_get("dart_usage") or "null")
        except (ValueError, sqlite3.Error):
            _usage = None
    if not isinstance(_usage, dict) or _usage.get("date") != today:
        _usage = {"date": today, "calls": 0, "e020": 0, "last020": None, "blocked": 0}
    return _usage


def _usage_save(u):
    _meta_set("dart_usage", json.dumps(u, ensure_ascii=False))


def dart_usage():
    """하루 사용량 — /api/dart/status 가 그대로 낸다.

    counter  "this"   이 서버가 센다(공시를 받는 서버)
             "record" 세는 서버가 DB 에 남긴 오늘 셈을 읽었다
             None     오늘 셈이 없다 — calls · left 도 None(0 이 아니다)
    """
    if _COUNTING:
        with _usage_lock:
            u = dict(_usage_now())
        u["counter"] = "this"
    else:
        try:
            rec = json.loads(_meta_get("dart_usage") or "null")
        except (ValueError, sqlite3.Error):
            rec = None
        if isinstance(rec, dict) and rec.get("date") == _today():
            u = dict(rec)
            u["counter"] = "record"
        else:
            u = {"date": _today(), "calls": None, "e020": None, "last020": None,
                 "blocked": None, "counter": None}
    u.update({"limit": DART_DAILY_LIMIT, "budget": DART_DAILY_BUDGET,
              "left": None if u["calls"] is None else max(0, DART_DAILY_BUDGET - u["calls"])})
    return u


class DartBudgetExceeded(RuntimeError):
    pass


def _dart_get(url, timeout):
    """OpenDART 한 번 부르기 — 하루 쓸 값을 넘으면 부르지 않고 DartBudgetExceeded."""
    with _usage_lock:
        u = _usage_now()
        if u["calls"] >= DART_DAILY_BUDGET:
            u["blocked"] = u.get("blocked", 0) + 1
            _usage_save(u)
            raise DartBudgetExceeded("하루 쓸 값 %d건에 닿아 오늘은 받지 않습니다" % DART_DAILY_BUDGET)
        u["calls"] += 1
        _usage_save(u)
    req = urllib.request.Request(url, headers={"User-Agent": "KJC-Holdings/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _note_020():
    with _usage_lock:
        u = _usage_now()
        u["e020"] += 1
        u["last020"] = datetime.now(KST).isoformat(timespec="seconds")
        _usage_save(u)


def get_key():
    """secrets.json 의 dart.api_key. 없으면 None — 공시 기능만 조용히 꺼진다."""
    path = secrets_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except ValueError:
        return None
    return ((data.get("dart") or {}).get("api_key")) or None


# ---------------------------------------------------------------- 기업 대응표

def refresh_corps(key):
    """corpCode.xml 을 받아 상장사만 저장한다. 하루 한 번이면 충분하다.

    받는 것은 ZIP 이다. 안에 CORPCODE.xml 하나가 들어 있고, 전체 기업이
    십만 개가 넘는다. 그중 stock_code 가 채워진 것이 상장사다.
    """
    url = DART_API + "/corpCode.xml?" + urllib.parse.urlencode({"crtfc_key": key})
    raw = _dart_get(url, 60)

    # 키가 틀리면 ZIP 이 아니라 XML 로 오류가 온다
    if not raw.startswith(b"PK"):
        if b"<status>020</status>" in raw:
            _note_020()
        msg = scrub(raw.decode("utf-8", "replace"))[:200]
        raise RuntimeError("기업 대응표를 받지 못했습니다: %s" % msg)

    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml = z.read(z.namelist()[0])

    rows = []
    for el in ET.fromstring(xml).iter("list"):
        stock = (el.findtext("stock_code") or "").strip()
        if not stock:                       # 비상장은 버린다
            continue
        rows.append((
            (el.findtext("corp_code") or "").strip(),
            stock,
            (el.findtext("corp_name") or "").strip(),
            (el.findtext("modify_date") or "").strip(),
        ))

    db_init()
    with _db_lock, db_conn() as conn:
        conn.executemany(
            """INSERT INTO dart_corps (corp_code, stock_code, corp_name, modify_date)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(corp_code) DO UPDATE SET
                 stock_code=excluded.stock_code, corp_name=excluded.corp_name,
                 modify_date=excluded.modify_date""",
            rows,
        )
    _meta_set("dart_corps_date", _today())
    return len(rows)


# ---------------------------------------------------------------- 감시 대상 200

def _to_int(v):
    if v is None:
        return None
    s = re.sub(r"[^0-9-]", "", str(v))
    return int(s) if s not in ("", "-") else None


# 지수 구성종목. 네이버에서 받는다 — KIS 에 구성종목을 주는 API 를 찾지
# 못했다 (2026-09-15 확인). 시총 순위와 같은 곳이라 새로 뚫을 것이 없다.
#
# KQI150 은 네이버 문서에 없는 이름이다. 후보를 직접 호출해 찾았다 —
# KDQ150 · KOSDAQ150 · KQ150 · KSQ150 은 HTTP 200 이지만 종목이 0개로
# 돌아온다. KQI150 만 149종목을 준다 (KPI200 은 199종목).
# 이름을 바꿔야 할 일이 생기면 같은 방법으로 확인하고 고친다.
#
# 분기에 한 번 바뀌는 값이라 하루 한 번만 받는다.
INDEX_LISTS = [("KPI200", "코스피200"), ("KQI150", "코스닥150")]

NAVER_MEMBERS = "https://finance.naver.com/sise/entryJongmok.naver?&type=%s&page=%d"
MEMBER_ROW = re.compile(r'code=(\d{6})[^>]*>\s*([^<]+?)\s*</a>')


def fetch_index_members(index_code, max_page=25):
    """지수 구성종목을 받는다. [(코드, 이름), ...]

    페이지당 10종목이고, 같은 것이 또 나오면 끝으로 본다.
    """
    out, seen = [], set()
    for page in range(1, max_page + 1):
        url = NAVER_MEMBERS % (index_code, page)
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://finance.naver.com/",
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode("euc-kr", "replace")
        rows = MEMBER_ROW.findall(body)
        if not rows:
            break
        fresh = 0
        for code, name in rows:
            if code in seen:
                continue
            seen.add(code)
            out.append((code, html.unescape(name).strip()))
            fresh += 1
        if fresh == 0:
            break
    return out


def refresh_index_members():
    """두 지수의 구성종목을 받아 저장한다. 실패한 지수는 옛 목록을 그대로 둔다."""
    db_init()
    now = datetime.now(KST).isoformat(timespec="seconds")
    done = {}
    for index_code, label in INDEX_LISTS:
        try:
            rows = fetch_index_members(index_code)
        except Exception as e:
            _meta_set("dart_last_error", "%s: %s" % (label, safe_message(e, 90)))
            continue
        if not rows:
            continue
        with _db_lock, db_conn() as conn:
            conn.execute("DELETE FROM index_members WHERE index_code = ?", (index_code,))
            conn.executemany(
                """INSERT INTO index_members (stock_code, index_code, name, updated_at)
                   VALUES (?, ?, ?, ?)""",
                [(c, index_code, n, now) for c, n in rows])
        done[index_code] = len(rows)
    if done:
        _meta_set("dart_members_date", _today())
    return done


def index_members_map():
    """{종목코드: [지수코드, ...]} 를 돌려준다. 화면이 걸러낼 때 쓴다."""
    db_init()
    out = {}
    with _db_lock, db_conn() as conn:
        for row in conn.execute("SELECT stock_code, index_code FROM index_members"):
            out.setdefault(row["stock_code"], []).append(row["index_code"])
    return out


def index_members_count():
    db_init()
    with _db_lock, db_conn() as conn:
        rows = conn.execute(
            "SELECT index_code, COUNT(*) n FROM index_members GROUP BY index_code")
        return {r["index_code"]: r["n"] for r in rows}


def fetch_kospi_top(size=UNIVERSE_SIZE):
    return fetch_market_top("KOSPI", size)


def fetch_market_top(market, size):
    """시장(KOSPI · KOSDAQ)의 시가총액 순위를 네이버에서 받는다 (100건씩).

    공식 API 가 아니다. 한국투자증권 순위 API 는 30건까지만 주기 때문에
    200종목을 만들 수 없어서 이쪽을 쓴다. 막히면 예외가 나고, 그때는
    직전에 저장해 둔 목록을 그대로 쓴다 (refresh_universe 참고).

    시총 순위는 하루 한 번만 부르면 되고, 순위가 조금 틀려도 감시 대상이
    한두 종목 바뀔 뿐이라 판단을 그르치지 않는다.
    """
    out = []
    page = 1
    while len(out) < size and page <= 10:
        url = ("https://m.stock.naver.com/api/stocks/marketValue/%s"
               "?page=%d&pageSize=100" % (market, page))
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://m.stock.naver.com/",
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read().decode("utf-8"))
        items = body.get("stocks") or []
        if not items:
            break
        for it in items:
            code = (it.get("itemCode") or "").strip()
            if len(code) != 6 or not code.isdigit():
                continue
            out.append({
                "code": code,
                "name": (it.get("stockName") or "").strip(),
                "cap": _to_int(it.get("marketValue")),
            })
        page += 1
    return out[:size]


def refresh_universe():
    """감시 대상을 새로 정한다 — 시장마다 따로. 못 받은 시장은 기존 목록을 건드리지 않는다."""
    db_init()
    got, errs = {}, []
    for market, size in UNIVERSE_SIZES:
        try:
            items = fetch_market_top(market, size)
        except Exception as e:
            errs.append("%s 시가총액 순위를 받지 못했습니다: %s" % (market, safe_message(e, 80)))
            continue
        if len(items) < 50:
            errs.append("%s 받은 종목이 %d개뿐이라 반영하지 않았습니다." % (market, len(items)))
            continue
        got[market] = items
    if not got:
        return {"ok": False, "count": universe_size(), "error": " · ".join(errs)}

    now = datetime.now(KST).isoformat(timespec="seconds")
    with _db_lock, db_conn() as conn:
        has = _universe_has_market(conn)
        for market, items in got.items():
            if not has and market != "KOSPI":
                continue                       # 칸이 없는 옛 표에는 코스피만 담는다
            if has:
                conn.execute("DELETE FROM dart_universe WHERE COALESCE(market, 'KOSPI') = ?", (market,))
            else:
                conn.execute("DELETE FROM dart_universe")
            conn.executemany(
                """INSERT OR REPLACE INTO dart_universe
                     (stock_code, name, rank, market_cap, updated_at%s)
                   VALUES (?, ?, ?, ?, ?%s)""" % ((", market", ", ?") if has else ("", "")),
                [(it["code"], it["name"], i + 1, it["cap"], now) + ((market,) if has else ())
                 for i, it in enumerate(items)],
            )
    if "KOSPI" in got:
        _meta_set("dart_universe_date", _today())
    out = {"ok": not errs, "count": universe_size()}
    if errs:
        out["error"] = " · ".join(errs)
    return out


def universe_rows(market="KOSPI", limit=None):
    """감시 대상 목록 — 시가총액 순. 열: stock_code · name · rank · market_cap · market.

    **목록을 읽는 자리는 이것 하나다** (2026-10-06). 코스닥이 같은 표에 들어오면서 `ORDER BY rank` 만으로는
    코스피 1위와 코스닥 1위가 섞인다. 미리 받기 · 신호 감시 · 모달 순위는 `market="KOSPI"` 그대로 읽는다.
    `market=None` 이면 전부 — 코스피가 먼저다.
    """
    db_init()
    with _db_lock, db_conn() as conn:
        has = _universe_has_market(conn)
        if not has and market not in (None, "KOSPI"):
            return []
        col = "COALESCE(market, 'KOSPI')" if has else "'KOSPI'"
        sql = "SELECT stock_code, name, rank, market_cap, %s AS market FROM dart_universe" % col
        args = []
        if market and has:
            sql += " WHERE %s = ?" % col
            args.append(market)
        # 코스피가 먼저 — 글자 순(KOSPI > KOSDAQ)에 기대지 않고 뜻으로 적는다 (창구 검수)
        sql += " ORDER BY %s rank" % (
            "CASE %s WHEN 'KOSPI' THEN 0 ELSE 1 END, %s," % (col, col) if market is None and has else "")
        if limit:
            sql += " LIMIT ?"
            args.append(limit)
        return conn.execute(sql, args).fetchall()


def cap_rank(code, market="KOSPI"):
    """시가총액 순위 — 그 시장 안의 순위. 목록 밖이면 None."""
    for r in universe_rows(market):
        if r["stock_code"] == code:
            return r["rank"]
    return None


def search(q, limit=10):
    """종목 찾기 — 이름 일부나 코드로 (2026-10-06 지시 — 「내기록 이걸 검색창으로 해주고 종목 검색 가능하도록」).

    **새로 받는 것이 없다.** 이미 있는 표 둘을 읽는다.
        순위 목록(dart_universe)   코스피 200 · 코스닥 150 — ETF 도 든다 · 시장이 있다
        기업 대응표(dart_corps)    OpenDART 상장사 전체 — ETF 는 없다 · 시장이 없다
    그래서 ETF 는 순위 안의 것만 찾는다. 대응표에는 **상장폐지된 회사도 종목코드를 단 채 남아 있을 수 있다** —
    지금은 가려낼 값이 표에 없다(받는 쪽 xml 에 상장 여부가 없다). 순위 목록에 든 것을 먼저 낸다.

    순서 — 순위 목록 → 이름이 같음 → 이름이 그것으로 시작 → 이름에 들어 있음. 코드는 앞부분이 같으면.
    """
    q = (q or "").strip()
    if not q:
        return []
    limit = max(1, min(int(limit or 10), 20))
    db_init()
    low = q.lower()
    digits = q.isdigit()
    with _db_lock, db_conn() as conn:
        has = _universe_has_market(conn)
        col = "COALESCE(market, 'KOSPI')" if has else "'KOSPI'"
        uni = conn.execute("SELECT stock_code, name, rank, %s AS market FROM dart_universe" % col).fetchall()
        if digits:
            corps = conn.execute(
                "SELECT stock_code, corp_name FROM dart_corps WHERE stock_code LIKE ? LIMIT 200",
                (q + "%",)).fetchall()
        else:
            corps = conn.execute(
                "SELECT stock_code, corp_name FROM dart_corps WHERE stock_code <> '' AND corp_name LIKE ? LIMIT 400",
                ("%" + q + "%",)).fetchall()

    def score(name, code):
        n = (name or "").lower()
        if digits:
            return 0 if code == q else (1 if code.startswith(q) else None)
        if n == low:
            return 0
        if n.startswith(low):
            return 1
        if low in n:
            return 2
        return None

    out, seen = [], set()
    rows = []
    for r in uni:
        sc = score(r["name"], r["stock_code"])
        if sc is not None:
            rows.append((0, sc, 0 if r["market"] == "KOSPI" else 1, r["rank"] or 999, r["stock_code"], r["name"], r["market"]))
    for r in corps:
        code = (r["stock_code"] or "").strip()
        sc = score(r["corp_name"], code)
        if sc is not None and len(code) == 6:
            rows.append((1, sc, 2, 999, code, r["corp_name"], None))
    for row in sorted(rows, key=lambda x: (x[1], x[0], x[2], x[3], len(x[5] or ""))):
        if row[4] in seen:
            continue
        seen.add(row[4])
        out.append({"code": row[4], "name": row[5], "market": row[6]})
        if len(out) >= limit:
            break
    return out


def universe_size():
    db_init()
    with _db_lock, db_conn() as conn:
        return conn.execute("SELECT COUNT(*) n FROM dart_universe").fetchone()["n"]


# ---------------------------------------------------------------- 공시 받기

def fetch_list(key, bgn, end, corp_cls="Y", max_pages=12):
    """기간 안의 공시를 통째로 받는다.

    corp_cls  Y=유가증권(코스피) K=코스닥 N=코넥스 E=기타
    status    000 정상 · 013 데이터 없음 · 020 하루 한도 초과 · 800 시스템 점검
    """
    out = []
    page = 1
    while page <= max_pages:
        url = DART_API + "/list.json?" + urllib.parse.urlencode({
            "crtfc_key": key, "bgn_de": bgn, "end_de": end,
            "corp_cls": corp_cls, "page_no": page, "page_count": 100,
        })
        body = json.loads(_dart_get(url, 30).decode("utf-8"))

        status_code = body.get("status")
        if status_code == "020":
            _note_020()
        if status_code == "013":            # 아직 공시가 없다
            break
        if status_code != "000":
            raise RuntimeError("%s %s" % (status_code, body.get("message") or ""))

        out.extend(body.get("list") or [])
        if page >= int(body.get("total_page") or 1):
            break
        page += 1
    return out


def purge_old(days=RETENTION_DAYS):
    """보관 기간이 지난 공시를 지운다. 지운 건수를 돌려준다.

    rcept_dt 는 'YYYYMMDD' 문자열이라 문자열 비교로 자를 수 있다.
    """
    cut = (datetime.now(KST) - timedelta(days=days)).strftime("%Y%m%d")
    db_init()
    with _db_lock, db_conn() as conn:
        cur = conn.execute("DELETE FROM dart_disclosures WHERE rcept_dt < ?", (cut,))
        return cur.rowcount or 0


def save_disclosures(items, only_codes=None, notified=0):
    """공시를 저장한다. 새로 들어온 것만 돌려준다.

    only_codes 가 None 이면 **종목코드가 있는 것을 전부** 담는다
    (2026-09-15 지시). 목록을 주면 그것만 담는다.

    종목코드가 없는 공시는 버린다. 비상장·펀드라 화면에 붙일 종목이 없고,
    눌러도 갈 곳이 없다.

    notified=1 로 넣으면 '이미 알린 것으로 친다'. 처음 켤 때 오늘 치를
    한꺼번에 받아 오는데, 그걸 전부 보내면 텔레그램이 도배된다.
    """
    fresh = []
    db_init()
    with _db_lock, db_conn() as conn:
        for it in items:
            code = (it.get("stock_code") or "").strip()
            if not code:
                continue                      # 비상장·펀드
            if only_codes is not None and code not in only_codes:
                continue
            rcept = (it.get("rcept_no") or "").strip()
            if not rcept:
                continue
            # **거르기일 뿐 판정이 아니다.** 아래 INSERT 의 결과가 판정한다 —
            # 여기서 보고 아래에서 쓰는 사이에 남이 끼어들 수 있다.
            if conn.execute("SELECT 1 FROM dart_disclosures WHERE rcept_no = ?",
                            (rcept,)).fetchone():
                continue
            row = {
                "rcept_no": rcept,
                "corp_code": (it.get("corp_code") or "").strip(),
                "stock_code": code,
                "corp_name": (it.get("corp_name") or "").strip(),
                "report_nm": (it.get("report_nm") or "").strip(),
                "flr_nm": (it.get("flr_nm") or "").strip(),
                "rcept_dt": (it.get("rcept_dt") or "").strip(),
                "rm": (it.get("rm") or "").strip(),
            }
            # **새 것인지는 기록이 판정한다** (2026-09-22).
            #
            # `worker/kis-worker.js` 에서 **같은 공시가 두 번 나간 일**이 있었다.
            # 거기는 `SELECT` 로 본 것을 그대로 보내는데, 그것을 **둘이 동시에
            # 부르면** 둘 다 「없다」 를 보고 각각 보낸다. **기록은 한 벌인데
            # 보낸 것이 두 번**이었다.
            #
            # 여기는 `_db_lock` 이 있어 **한 프로세스 안에서는** 안 나는데,
            # **같은 `market.db` 를 여러 서버가 쓰면 그때부터 난다.**
            # 지금은 `NOTIFY_LOCAL = False` 라 보내지 않아 드러나지 않을 뿐이다.
            #
            # `ON CONFLICT` 로 두고 `rowcount` 를 보면 **실제로 들어간 것만**
            # 남는다 — 워커의 `meta.changes` 와 같은 자리다.
            cur = conn.execute(
                """INSERT INTO dart_disclosures
                     (rcept_no, corp_code, stock_code, corp_name, report_nm,
                      flr_nm, rcept_dt, rm, received_at, notified)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(rcept_no) DO NOTHING""",
                (row["rcept_no"], row["corp_code"], row["stock_code"],
                 row["corp_name"], row["report_nm"], row["flr_nm"],
                 row["rcept_dt"], row["rm"],
                 datetime.now(KST).isoformat(timespec="seconds"), notified),
            )
            if not cur.rowcount:
                continue
            fresh.append(row)
    return fresh


def read_disclosures(code=None, limit=30):
    db_init()
    sql = """SELECT rcept_no, stock_code, corp_name, report_nm, flr_nm, rcept_dt, rm
               FROM dart_disclosures"""
    args = []
    if code:
        sql += " WHERE stock_code = ?"
        args.append(code)
    sql += " ORDER BY rcept_no DESC LIMIT ?"
    args.append(max(1, min(int(limit), 200)))
    with _db_lock, db_conn() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [{
        "rceptNo": r["rcept_no"],
        "code": r["stock_code"],
        "name": r["corp_name"],
        "title": r["report_nm"],
        "filer": r["flr_nm"],
        "date": r["rcept_dt"],
        "note": r["rm"],
        "url": VIEWER % r["rcept_no"],
    } for r in rows]



# ── 기업설명회(IR) 일시 (2026-10-26 재권님 「응 묶어」 · 작업우선순위 경유) ──────────────
#
# 「기업설명회(IR)개최」 공시는 **일시가 본문에만 있다** — 목록(OpenDART list)은 제목 · 접수일만 준다.
# 그래서 한국 실적 발표(SK하이닉스 10-28 09:00 · 삼성 콘콜)가 일정 칸에 안 들어갔다(시황분석이 찾음).
# 공시 바퀴가 새 IR 공시를 저장한 뒤 **우리 종목(코스피 200 · 코스닥 150 · 관심)** 것만 본문을 한 번 읽어
# 일시 · 목적 · 방법을 `dart_ir` 에 한 줄로 둔다. 본문은 DART 보기 화면(dart.fss.or.kr)이라 OpenDART 하루 한도를 안 쓴다.
#
#   본문 모양(2026-10-14 SK하이닉스 20261014800385 실측) —
#     「1. 일시 및 장소 일시 2026-10-28 09:00 장소 - … 3. 개최목적 2026년 3분기 경영실적 발표 4. 개최방법 Conference Call …」
#   앞 「일시 및 장소」 의 「일시」 는 숫자가 안 따라와 건너뛴다. 시각이 「--:--」 이거나 없으면 날만 둔다(지어내지 않는다 —
#   기아처럼 시각을 「기타」 줄 글로만 적은 것도 있는데 그 글은 안 읽는다).
#   코스닥 쪽 서식은 다르다(2026-10-16 ISC 실측) — 「1. 일시 행사일 시간(현지시간) 시작일 종료일 시작시간 종료시간
#   2026-10-29 2026-10-30 09:00 18:00 … 4. 실시목적 … 5. 실시방법 …」. 「IR 자료게재 게재일시」 의 날은 행사일이 아니라 뺀다.
#
# 쓰는 곳: GET /api/dart/ir?days=14 — Insight 일정 칸 · 홈 일정 달력 · 결과 알림(events.py)이 같은 값을 읽는다(화면 쪽은 각 레인).
IR_WORD = "기업설명회"
IR_PER_PASS = 10                 # 한 바퀴(5분)에 읽는 본문 수(한 건 = 보기 화면 2번) — 처음 켤 때 밀린 것을 몇 바퀴에 나눠 읽는다
IR_GAP_SEC = 2.0                 # 본문 사이 쉼 — **DART 보기 화면은 몰아 부르면 이 기계를 막는다**(2026-10-26 12:34 시험에서
                                 # 0.3초 간격 · 1분 반에 이백 번쯤 부르자 연결을 끊기 시작했고 그 뒤로 한동안 안 열렸다).
                                 # events.py 의 잠정실적 본문도 같은 곳이라 막히면 함께 못 읽는다 — 그래서 넉넉히 쉰다
IR_TIMEOUT = 15
IR_KEEP_DAYS = RETENTION_DAYS    # 일시가 이만큼 지난 줄은 지운다(공시 보관과 같은 날수)
IR_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) KJCStudio"

IR_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS dart_ir (
         rcept_no    TEXT PRIMARY KEY,
         stock_code  TEXT,
         corp_name   TEXT,
         report_nm   TEXT,
         rcept_dt    TEXT,
         ir_date     TEXT,              -- 'YYYY-MM-DD' (한국 날짜) · 못 읽으면 NULL
         ir_time     TEXT,              -- 'HH:MM' · 본문에 시각이 없으면 NULL
         ir_end      TEXT,              -- 끝나는 날(코스닥 서식의 종료일) · 하루짜리는 NULL
         purpose     TEXT,
         method      TEXT,
         error       TEXT,              -- 본문은 받았는데 일시를 못 읽은 까닭 — 다시 읽지 않는다(다음 정정 공시가 새 줄로 온다)
         parsed_at   TEXT
       )""",
    "CREATE INDEX IF NOT EXISTS idx_ir_date ON dart_ir (ir_date)",
]


def viewer_body(rcept_no):
    """공시 본문 HTML(EUC-KR → 글). 첫 화면에서 문서 번호를 찾아 그 문서를 받는다.
    events.py 의 잠정실적 읽기도 이것을 쓴다(두 벌로 두지 않는다)."""
    def get(url):
        req = urllib.request.Request(url, headers={"User-Agent": IR_UA})
        with urllib.request.urlopen(req, timeout=IR_TIMEOUT) as r:
            return r.read()
    main = get(VIEWER % rcept_no).decode("utf-8", "replace")
    m = re.search(r'viewDoc\("%s",\s*"(\d+)"' % rcept_no, main)
    if not m:
        raise RuntimeError("공시 문서 번호를 못 찾았습니다")
    raw = get("https://dart.fss.or.kr/report/viewer.do?rcpNo=%s&dcmNo=%s&eleId=0&offset=0&length=0&dtd=HTML"
              % (rcept_no, m.group(1)))
    for enc in ("cp949", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


_IR_RANGE = re.compile(
    r"시작일\s*종료일\s*시작시간\s*종료시간\s*(20\d{2})-(\d{2})-(\d{2})\s*(?:(20\d{2})-(\d{2})-(\d{2}))?\s*(?:(\d{1,2}):(\d{2}))?")
_IR_WHEN = re.compile(
    r"(?<!게재)일\s*시\s*:?\s*(20\d{2})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})\s*일?"
    r"(?:\s*\(\s*[월화수목금토일]\s*\))?"
    r"(?:\s*(오전|오후)?\s*(\d{1,2})\s*(?::|시)\s*(\d{2})?)?")


def parse_ir(body):
    """본문 → {date, time, purpose, method}. 일시를 못 읽으면 date 가 None."""
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", body)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t)
    out = {"date": None, "endDate": None, "time": None, "purpose": None, "method": None}
    r = _IR_RANGE.search(t)
    if r:
        g = r.groups()
        out["date"] = "%s-%s-%s" % g[0:3]
        if g[3]:
            out["endDate"] = "%s-%s-%s" % g[3:6]
        if g[6] is not None:
            out["time"] = "%02d:%s" % (int(g[6]), g[7])
    m = None if r else _IR_WHEN.search(t)
    if m:
        y, mo, d, ampm, hh, mm = m.groups()
        try:
            out["date"] = datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
        except ValueError:
            out["date"] = None
        if out["date"] and hh is not None:
            h = int(hh)
            if ampm == "오후" and h < 12:
                h += 12
            if 0 <= h <= 23:
                out["time"] = "%02d:%s" % (h, mm or "00")
    for key, label in (("purpose", "(?:개최|실시)목적"), ("method", "(?:개최|실시)방법")):
        m = re.search(label + r"\s*:?\s*(.+?)\s*(?:\d{1,2}\s*\.\s*[가-힣(]|$)", t)
        if m:
            out[key] = m.group(1).strip(" -")[:120] or None
    return out


def ir_codes():
    """본문을 읽을 종목 — 코스피 200 · 코스닥 150(대상 표) · 지수 구성 · 관심. 표를 박지 않고 그날 표에서 센다."""
    codes = set(WATCH_CODES)
    try:
        codes.update(r["stock_code"] for r in universe_rows(None))
    except Exception:
        pass
    try:
        codes.update(index_members_map().keys())
    except Exception:
        pass
    return codes


def ir_init():
    with _db_lock, db_conn() as conn:
        for sql in IR_SCHEMA:
            conn.execute(sql)


def fill_ir(limit=IR_PER_PASS):
    """아직 안 읽은 우리 종목 IR 공시의 본문을 읽어 `dart_ir` 에 둔다. 읽은 수 · 남은 수를 돌려준다.
    쓰기 서버만 한다 — 읽기 전용 서버(마운트만 한 자리)는 건너뛴다."""
    if not marketdb.writable():
        return {"read": 0, "left": None, "skipped": "읽기 전용"}
    ir_init()
    codes = ir_codes()
    with _db_lock, db_conn() as conn:
        rows = conn.execute(
            """SELECT d.rcept_no, d.stock_code, d.corp_name, d.report_nm, d.rcept_dt
                 FROM dart_disclosures d LEFT JOIN dart_ir i ON i.rcept_no = d.rcept_no
                WHERE d.report_nm LIKE ? AND i.rcept_no IS NULL
                ORDER BY d.rcept_no DESC""", ("%" + IR_WORD + "%",)).fetchall()
    todo = [r for r in rows if r["stock_code"] in codes]
    done = 0
    for r in todo[:max(0, int(limit))]:
        # **받기 실패는 적지 않고 그 바퀴를 멈춘다** — 다음 바퀴에 다시 읽는다. DART 보기 화면은 몰아 부르면 연결을 끊는다
        # (2026-10-26 시험 — 0.3초 간격으로 백 번쯤 부르자 「Remote end closed connection」 이 이어졌다). 적으면 영영 못 읽은 것이 된다
        try:
            body = viewer_body(r["rcept_no"])
        except Exception as e:
            _meta_set("dart_ir_last_error", "%s: %s" % (r["rcept_no"], safe_message(e, 120)))
            break
        p, err = parse_ir(body), None
        if not p["date"]:
            err = "일시를 못 읽음"
        with _db_lock, db_conn() as conn:
            conn.execute(
                """INSERT INTO dart_ir (rcept_no, stock_code, corp_name, report_nm, rcept_dt,
                                        ir_date, ir_time, ir_end, purpose, method, error, parsed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(rcept_no) DO NOTHING""",
                (r["rcept_no"], r["stock_code"], r["corp_name"], r["report_nm"], r["rcept_dt"],
                 p["date"], p["time"], p["endDate"], p["purpose"], p["method"], err,
                 datetime.now(KST).isoformat(timespec="seconds")))
        done += 1
        time.sleep(IR_GAP_SEC)
    cut = (datetime.now(KST) - timedelta(days=IR_KEEP_DAYS)).strftime("%Y-%m-%d")
    with _db_lock, db_conn() as conn:
        conn.execute("DELETE FROM dart_ir WHERE ir_date IS NOT NULL AND ir_date < ?", (cut,))
    return {"read": done, "left": max(0, len(todo) - done)}


def _ir_is_earnings(purpose):
    p = purpose or ""
    return "실적" in p or ("분기" in p and any(w in p for w in ("설명", "발표")))


def read_ir(days=14, past=0):
    """앞으로 `days` 일(오늘 포함)의 IR — 한국 시각. `past` 일 앞까지 함께.
    같은 종목의 **정정 공시**가 뒤에 왔으면 그 종목의 앞 줄(같은 목적)을 뺀다 — 날이 바뀐 정정이 둘로 안 보이게."""
    # 읽기 전용 서버(8764 · 세션 서버 — 메인 DB 를 mode=ro 로 연다)는 표를 못 만든다. 8765 가 새 코드로 뜨기 전에는 표가 없다
    # — 그때는 빈 목록에 ready=false 를 낸다(「없다」 가 아니라 「아직 안 읽었다」 · 「못 쟀으면 0 이 아니라 못 쟀다」)
    if marketdb.writable():
        ir_init()
    else:
        with _db_lock, db_conn() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='dart_ir'").fetchone():
                return [], {"ready": False, "count": 0, "note": "IR 일시 표가 아직 없습니다 — 받는 서버(8765)가 새 코드로 뜨면 생깁니다"}
    now = datetime.now(KST)
    a = (now - timedelta(days=max(0, int(past)))).strftime("%Y-%m-%d")
    b = (now + timedelta(days=max(0, int(days)))).strftime("%Y-%m-%d")
    with _db_lock, db_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM dart_ir WHERE ir_date BETWEEN ? AND ?
                ORDER BY ir_date, COALESCE(ir_time, '99:99'), rcept_no""", (a, b)).fetchall()
        n_err = conn.execute("SELECT COUNT(*) n FROM dart_ir WHERE error IS NOT NULL").fetchone()["n"]
    rows = [dict(r) for r in rows]
    keep = []
    for r in rows:
        later = [x for x in rows if x["stock_code"] == r["stock_code"] and x["rcept_no"] > r["rcept_no"]
                 and "정정" in (x["report_nm"] or "") and (x["purpose"] or "") == (r["purpose"] or "")]
        if not later:
            keep.append(r)
    data = [{
        "code": r["stock_code"],
        "name": r["corp_name"],
        "date": r["ir_date"],
        "time": r["ir_time"],
        "endDate": r["ir_end"],
        "kst": "%s %s" % (r["ir_date"], r["ir_time"]) if r["ir_time"] else None,
        "purpose": r["purpose"],
        "method": r["method"],
        # 실적 발표로 치는 것 — 목적에 「실적」 이 들거나(「2026년 3분기 경영실적 발표」) 「분기」 와 설명 · 발표가 함께 든 것
        # (「2026년 3분기 기업설명회」 — 한화 계열 · 포스코 계열이 이렇게 적는다). 「3분기 국내 NDR」 은 안 든다
        "earnings": _ir_is_earnings(r["purpose"]),
        "title": r["report_nm"],
        "rceptNo": r["rcept_no"],
        "url": VIEWER % r["rcept_no"],
    } for r in keep]
    return data, {"ready": True, "from": a, "to": b, "count": len(data), "unreadable": n_err,
                  "lastFillAt": _meta_get("dart_ir_fill"), "lastFill": _meta_get("dart_ir_fill_result")}


def status():
    db_init()
    with _db_lock, db_conn() as conn:
        n_corps = conn.execute("SELECT COUNT(*) n FROM dart_corps").fetchone()["n"]
        n_uni = conn.execute("SELECT COUNT(*) n FROM dart_universe").fetchone()["n"]
        n_disc = conn.execute("SELECT COUNT(*) n FROM dart_disclosures").fetchone()["n"]
        last = conn.execute(
            "SELECT MAX(received_at) t FROM dart_disclosures").fetchone()["t"]
    return {
        "configured": bool(get_key()),
        "telegram": bool(telegram_config()),
        "corps": n_corps,
        "universe": n_uni,
        "disclosures": n_disc,
        "lastReceivedAt": last,
        "lastPollAt": _meta_get("dart_last_poll"),
        # 고치기 전에 저장된 값이 남아 있을 수 있어 돌려줄 때 한 번 더 거른다
        "lastPollError": scrub(_meta_get("dart_last_error")) or None,
        "watchCodes": WATCH_CODES,
        "usage": dart_usage(),
    }


# ---------------------------------------------------------------- 텔레그램

def telegram_config():
    """봇 토큰과 받을 사람. secrets.json 에 없으면 보내지 않는다.

    **보내는 서버(`NOTIFY_LOCAL` = `is_sender`)가 아니면 텔레그램 칸을 아예 안 읽는다** (2026-10-12 지시 —
    「한곳에서만 알림을 보낸다」). 열쇠 파일을 한 벌(`~/.kjc`)로 합치면 세션 서버 · 서비스방도 메인의 봇 값을
    갖게 되는데, 그때도 발송 판정(`is_sender`)에 더해 이 한 겹이 남는다. 공시 · 뉴스 · 데일리 · 신호 · 예약
    알림이 전부 `telegram_send` → 이 함수를 지나므로 자리는 여기 하나다.
    """
    if not NOTIFY_LOCAL:
        return None
    path = secrets_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            tg = (json.load(f).get("telegram") or {})
    except ValueError:
        return None
    if tg.get("bot_token") and tg.get("chat_id"):
        return {"token": tg["bot_token"], "chat": str(tg["chat_id"])}
    return None


# 조용한 시간 — 이 사이에는 텔레그램을 **하나도** 안 보낸다 (2026-10-12 재권님 「밤 10시~아침 7시까지는
# 알림을 주지 않는다」 · 「가」). 텔레그램은 전부 아래 `telegram_send` 하나로 나가므로(뉴스 즉시 · 정기 묶음 ·
# 공시 · 신호 · 예약 · 데일리) **여기 한 곳**이 막는다 — 새 발송 길이 생겨도 저절로 걸린다.
# 밤에 걸린 것은 버리지 않는다: 뉴스는 07:30 정기 묶음에 ❗ 로(`news_store.send_alerts`) · 공시 · 예약은 다음 바퀴.
# 맥미니 꺼짐 알림은 Cloudflare 워커가 보내 이 함수를 안 거친다 — 그것은 밤에도 간다(재권님 답 · 예외).
QUIET_FROM = 22 * 60          # 22:00 (분)
QUIET_TO = 7 * 60             # 07:00 (분) — 이 시각부터 보낸다
QUIET_REASON = "조용한 시간(22:00~07:00)이라 보내지 않았습니다"


def in_quiet(ts=None):
    """그 시각(초 · 없으면 지금)이 조용한 시간인가. 한국 시각으로 본다."""
    t = datetime.fromtimestamp(time.time() if ts is None else ts, KST)
    m = t.hour * 60 + t.minute
    if QUIET_FROM <= QUIET_TO:
        return QUIET_FROM <= m < QUIET_TO
    return m >= QUIET_FROM or m < QUIET_TO       # 자정을 넘는다


# 텔레그램 한 통의 한도는 4,096자다(UTF-16 단위로 센다 · 이모지는 2). 넘으면 sendMessage 가 통째로 실패한다.
# 넘는 날만 줄 경계로 나눠 차례로 보낸다 — 「넘는 날만 두 통」 재권님 「가」(2026-10-23). 여유를 두고 4,000 으로 자른다.
TELEGRAM_MAX = 4000


def _tg_len(s):
    return len(s.encode("utf-16-le")) // 2


def telegram_chunks(text, limit=TELEGRAM_MAX):
    """한도 안이면 [text] 그대로. 넘으면 줄 경계로 나눈다 — 한 줄이 한도보다 길 때만 그 줄을 글자로 자른다."""
    if _tg_len(text) <= limit:
        return [text]
    out, cur = [], ""
    for line in text.split("\n"):
        while _tg_len(line) > limit:            # 한 줄이 통째로 넘는 드문 경우
            if cur:
                out.append(cur)
                cur = ""
            cut = limit
            while _tg_len(line[:cut]) > limit:
                cut -= 1
            out.append(line[:cut])
            line = line[cut:]
        cand = line if not cur else cur + "\n" + line
        if _tg_len(cand) > limit:
            out.append(cur)
            cur = line
        else:
            cur = cand
    if cur.strip():
        out.append(cur)
    return [c for c in out if c.strip()]


def _telegram_post(cfg, text):
    url = "https://api.telegram.org/bot%s/sendMessage" % cfg["token"]
    data = urllib.parse.urlencode({
        "chat_id": cfg["chat"],
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read().decode("utf-8"))
        return bool(body.get("ok")), body.get("description") or ""
    except Exception as e:
        # 주소에 봇 토큰이 들어 있다. 예외 문구에 URL 이 섞이면 토큰이 샌다.
        return False, safe_message(e, 100)


def telegram_send(text):
    """보낸다 — 그리고 그 결과를 `tglog` 에 한 줄(보냄 · 조용한 시간 · 실패). 모든 발송이 여기를 지나므로 기록도 여기 하나다."""
    ok, why = _telegram_send(text)
    tglog.note(text, "sent" if ok else ("quiet" if why == QUIET_REASON else "fail"), None if ok else scrub(why))
    return ok, why


def _telegram_send(text):
    if in_quiet():
        return False, QUIET_REASON
    cfg = telegram_config()
    if not cfg:
        return False, "텔레그램 설정이 없습니다 (secrets.json 의 telegram)"
    parts = telegram_chunks(text)
    for i, part in enumerate(parts):
        ok, why = _telegram_post(cfg, part)
        if not ok:
            # 몇 번째에서 멈췄는지 함께 낸다 — 앞 통은 이미 갔다(못 지운다)
            return False, why if len(parts) == 1 else "%d통 중 %d번째 실패: %s" % (len(parts), i + 1, why)
    return True, "" if len(parts) == 1 else "%d통으로 나눠 보냄" % len(parts)


def format_message(row):
    dt = row.get("rcept_dt") or ""
    when = "%s-%s" % (dt[4:6], dt[6:8]) if len(dt) == 8 else dt
    lines = [
        "📢 %s (%s)" % (row["corp_name"], row["stock_code"]),
        row["report_nm"],
    ]
    if row.get("flr_nm") and row["flr_nm"] != row["corp_name"]:
        lines.append("제출: %s" % row["flr_nm"])
    lines.append("접수 %s" % when)
    lines.append(VIEWER % row["rcept_no"])
    return "\n".join(lines)


def notify(rows):
    """관심종목 공시만 보낸다. 보낸 것은 표시해 두어 두 번 보내지 않는다."""
    sent = 0
    for row in rows:
        if row["stock_code"] not in WATCH_CODES:
            continue
        ok, _err = telegram_send(format_message(row))
        with _db_lock, db_conn() as conn:
            conn.execute("UPDATE dart_disclosures SET notified = ? WHERE rcept_no = ?",
                         (1 if ok else 0, row["rcept_no"]))
        if ok:
            sent += 1
            time.sleep(0.4)      # 텔레그램 초당 제한을 건드리지 않게 천천히
    return sent


# ---------------------------------------------------------------- 한 바퀴

def poll_once(key, quiet_first_run=True):
    """오늘 공시를 시장마다 받아 저장하고, 새 것 중 관심종목을 알린다.

    저장은 종목코드 있는 것 전부, 텔레그램은 관심종목만이다 (2026-09-15).
    """
    db_init()
    today = _today()

    # 하루 한 번 해 두면 되는 것들
    if _meta_get("dart_corps_date") != today:
        try:
            refresh_corps(key)
        except Exception as e:
            _meta_set("dart_last_error", "대응표: %s" % safe_message(e, 120))
    # 코스닥이 아직 없으면(market 칸을 막 붙였을 때) 그날 한 번 더 받는다 — 쓸 수 있는 서버만.
    # 읽기 전용 서버는 칸을 못 붙여 코스닥이 늘 0 이라, 안 가르면 돌 때마다 쓰기를 시도한다
    if (_meta_get("dart_universe_date") != today or universe_size() == 0
            or (marketdb.writable() and not universe_rows("KOSDAQ", 1))):
        refresh_universe()
    if _meta_get("dart_members_date") != today or not index_members_count():
        refresh_index_members()

    # 시장마다 한 번씩 받는다. 기간 조회라 종목 수와 무관하게 호출이 일정하다.
    items = []
    for cls in COLLECT_MARKETS:
        try:
            items.extend(fetch_list(key, today, today, corp_cls=cls))
        except Exception as e:
            # 한 시장이 막혀도 나머지는 담는다. 전부 실패했을 때만 오류로 친다.
            msg = "%s: %s" % (cls, safe_message(e, 100))
            _meta_set("dart_last_error", msg)
            if cls == COLLECT_MARKETS[-1] and not items:
                return {"ok": False, "error": msg}

    # 처음 켜는 날이면 오늘 치가 한꺼번에 들어온다. 그건 알리지 않는다.
    #
    # **`NOTIFY_LOCAL` 이 꺼져 있을 때도 같은 길로 간다.** 보내지 않되
    # `notified = 1` 로 적어 둔다 — 안 적으면 나중에 다시 켤 때 그동안
    # 쌓인 것이 **한꺼번에 쏟아진다.** 「이미 알린 것으로 친다」 는 이 방식이
    # 처음 켜는 날을 위해 이미 있던 것이라 그대로 쓴다 (`save_disclosures` 참고).
    first_run = _meta_get("dart_last_poll") is None
    mark = 1 if ((first_run and quiet_first_run) or not NOTIFY_LOCAL) else 0

    # 종목코드가 있는 것은 전부 담는다 (2026-09-15 지시).
    # 텔레그램은 그대로 관심종목만 간다 — notify() 가 WATCH_CODES 로 거른다.
    fresh = save_disclosures(items, notified=mark)
    sent = 0 if mark else notify(fresh)

    purged = purge_old()

    # 우리 종목 IR 공시의 본문 일시 — 한 바퀴에 몇 건씩(fill_ir). 실패해도 공시 바퀴는 멈추지 않는다
    try:
        r = fill_ir()
        _meta_set("dart_ir_fill", datetime.now(KST).isoformat(timespec="seconds"))
        _meta_set("dart_ir_fill_result", json.dumps(r, ensure_ascii=False))
    except Exception as e:
        _meta_set("dart_ir_fill_result", json.dumps({"error": safe_message(e, 120)}, ensure_ascii=False))

    _meta_set("dart_last_poll", datetime.now(KST).isoformat(timespec="seconds"))
    _meta_set("dart_last_error", "")
    return {"ok": True, "received": len(items), "matched": len(fresh),
            "notified": sent, "purged": purged, "firstRun": first_run}


# ── 알림 예약 ────────────────────────────────────────────────
#
# 정해둔 시각이 지나면 텔레그램으로 한 번 보낸다. 5분마다 도는 루프가
# 확인하므로 정각이 아니라 그 안쪽 어딘가에 도착한다.
#
# 보낸 것은 sync_meta 에 적어 두 번 가지 않게 한다 — 공시가 "오늘 보냈나"를
# 기억하는 것과 같은 방식이다. 지나간 것은 지운다.
#
# (그때의 워커에도 같은 목록이 있었다 — 2026-10-06 에 워커를 지웠다.)
REMINDERS = [
    {"id": "20260916-0900", "at": "2026-09-16T09:00",
     "text": "오늘 할 일 — 숫자 깜빡임 제거 부분 수정"},
]


def _kst_stamp(now=None):
    """지금 한국 시각을 '2026-09-16T09:00' 꼴로.

    문자열끼리 비교하면 시간대 계산을 한 번 더 하지 않아도 된다.
    """
    return (now or datetime.now(KST)).strftime("%Y-%m-%dT%H:%M")


def send_reminders():
    """때가 된 알림을 보낸다. 보낸 건수를 돌려준다.

    **메인서버만 보낸다** — 공시 발송과 같은 `NOTIFY_LOCAL`(= `is_sender`)을 본다 (2026-10-12).
    그 전에는 이 깃발을 안 봐서 공시 폴러가 도는 서버마다 따로 보낼 수 있었다.
    보내지 않은 서버는 「보냈다」 표시도 안 남긴다 — 메인이 그대로 보낸다.
    """
    if not REMINDERS or not NOTIFY_LOCAL:
        return 0
    db_init()
    now = _kst_stamp()
    sent = 0
    for r in REMINDERS:
        if now < r["at"]:
            continue                      # 아직 때가 아니다
        key = "remind_" + r["id"]
        if _meta_get(key):
            continue                      # 이미 보냈다
        ok, _err = telegram_send(r["text"])
        if ok:
            _meta_set(key, now)
            sent += 1
    return sent


def _should_poll(now=None):
    now = now or datetime.now(KST)
    if now.weekday() >= 5:
        return False
    hm = now.hour * 60 + now.minute
    return POLL_FROM <= hm < POLL_TO


def start_poller():
    """백그라운드로 5분마다 한 바퀴 돈다. 키가 없으면 아무것도 하지 않는다."""
    global _COUNTING
    key = get_key()
    if not key:
        return False
    _COUNTING = True             # 하루 셈은 공시를 받는 이 서버가 든다 — dart_usage 참고

    def loop():
        time.sleep(5)            # 서버가 막 뜬 참이라 잠깐 기다렸다 시작한다
        while True:
            try:
                # 공시와 별개로 먼저 본다. 주말·장 시간과 무관하게 가야 한다.
                try:
                    n = send_reminders()
                    if n:
                        print("  [알림] 예약 알림 %d건 보냄" % n)
                except Exception:
                    pass

                if _should_poll():
                    r = poll_once(key)
                    if r.get("ok") and r.get("matched"):
                        print("  [DART] 새 공시 %d건 · 알림 %d건"
                              % (r["matched"], r.get("notified", 0)))
                    elif not r.get("ok"):
                        print("  [DART] %s" % r.get("error"))
            except Exception as e:
                print("  [DART] 예기치 못한 오류: %s" % type(e).__name__)
            time.sleep(POLL_INTERVAL)

    threading.Thread(target=loop, daemon=True, name="dart-poller").start()
    return True
