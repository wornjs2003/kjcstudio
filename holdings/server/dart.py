#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenDART 공시 수집.

무엇을 하는가
  1. 기업 대응표를 하루 한 번 받아 둔다 (corp_code ↔ 종목코드 ↔ 회사명)
  2. 코스피 시가총액 상위 200 종목을 하루 한 번 정해 둔다 — 이것이 감시 대상이다
  3. 5분마다 "오늘 올라온 공시"를 통째로 받아 감시 대상 것만 남겨 저장한다
  4. 새로 들어온 공시가 관심종목이면 텔레그램으로 보낸다

왜 이렇게 하는가
  종목마다 따로 물으면 200종목 × 하루 288번 = 57,600건이라 하루 한도(약 20,000건)를
  넘긴다. 기간으로 한 번에 받아 우리 쪽에서 거르면 하루 1,200건 안쪽이다.

한도
  OpenDART 는 하루 약 20,000건. 넘기면 status 020 을 돌려준다.
  실시간 푸시는 없다. 주기적으로 물어보는 수밖에 없다.
"""

import io
import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

HOLDINGS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(HOLDINGS_DIR, "market.db")

DART_API = "https://opendart.fss.or.kr/api"

# 공시 원문 보기 주소. rcept_no 하나만 있으면 열린다.
VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=%s"

# 감시 대상 — 코스피 시가총액 상위 몇 종목까지 볼 것인가
UNIVERSE_SIZE = 200

# 텔레그램을 보낼 종목.
# js/data/market.js 의 WATCHLIST 와 같아야 한다. 한쪽만 고치면 어긋난다.
WATCH_CODES = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035420",  # NAVER
    "035720",  # 카카오
    "005380",  # 현대차
    "373220",  # LG에너지솔루션
    "207940",  # 삼성바이오로직스
    "068270",  # 셀트리온
]

# 언제 물어볼 것인가.
# DART 접수는 평일에만 있다. 07:00 이전과 20:00 이후는 물어봐야 새 것이 없다.
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
    """CREATE TABLE IF NOT EXISTS dart_universe (
         stock_code  TEXT PRIMARY KEY,
         name        TEXT,
         rank        INTEGER,
         market_cap  INTEGER,
         updated_at  TEXT
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
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def db_init():
    with _db_lock, db_conn() as conn:
        for sql in SCHEMA:
            conn.execute(sql)


def _meta_get(key):
    with _db_lock, db_conn() as conn:
        r = conn.execute("SELECT value FROM sync_meta WHERE key = ?", (key,)).fetchone()
    return r["value"] if r else None


def _meta_set(key, value):
    with _db_lock, db_conn() as conn:
        conn.execute(
            """INSERT INTO sync_meta (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                                             updated_at=excluded.updated_at""",
            (key, str(value), datetime.now(KST).isoformat(timespec="seconds")),
        )


def _today():
    return datetime.now(KST).strftime("%Y%m%d")


# 오류 문구에서 비밀을 지운다.
#   2026-09-14 에 배포본(Cloudflare Worker)에서 인증키가 실제로 새어 나갔다.
#   외부 호출이 실패했을 때 런타임이 요청 URL 을 오류 메시지에 붙이는데,
#   그 URL 에 crtfc_key 가 들어 있었다. 그것을 그대로 저장하고 /api/dart/status
#   로 돌려줘서 누구나 볼 수 있었다.
#   여기(로컬)는 localhost 라 위험이 덜하지만, 같은 실수를 두 번 하지 않도록 막아둔다.
_SECRET_QS = re.compile(
    r"([?&](?:crtfc_key|appkey|app_key|appsecret|app_secret|api_key|access_token|token|secret)=)[^&\s\"']*",
    re.IGNORECASE,
)


def scrub(text):
    s = str(text if text is not None else "")
    s = _SECRET_QS.sub(lambda m: m.group(1) + "<가림>", s)   # 값만 지운다
    for v in _all_secrets():
        if v and len(v) >= 8:
            s = s.replace(v, "<가림>")
    return s


def _all_secrets():
    """secrets.json 에 든 값들. 오류 문구에 섞여 나가면 안 되는 것들이다."""
    path = os.path.join(HOLDINGS_DIR, "secrets.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except ValueError:
        return []
    tg = d.get("telegram") or {}
    kis = d.get("kis") or {}
    return [str(v) for v in (
        (d.get("dart") or {}).get("api_key"),
        kis.get("app_key"), kis.get("app_secret"),
        tg.get("bot_token"), tg.get("chat_id"),
    ) if v]


def safe_message(e, limit=160):
    return scrub(e)[:limit]


def get_key():
    """secrets.json 의 dart.api_key. 없으면 None — 공시 기능만 조용히 꺼진다."""
    path = os.path.join(HOLDINGS_DIR, "secrets.json")
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
    req = urllib.request.Request(url, headers={"User-Agent": "KJC-Holdings/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()

    # 키가 틀리면 ZIP 이 아니라 XML 로 오류가 온다
    if not raw.startswith(b"PK"):
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


def fetch_kospi_top(size=UNIVERSE_SIZE):
    """코스피 시가총액 순위를 네이버에서 받는다 (100건씩).

    공식 API 가 아니다. 한국투자증권 순위 API 는 30건까지만 주기 때문에
    200종목을 만들 수 없어서 이쪽을 쓴다. 막히면 예외가 나고, 그때는
    직전에 저장해 둔 목록을 그대로 쓴다 (refresh_universe 참고).

    시총 순위는 하루 한 번만 부르면 되고, 순위가 조금 틀려도 감시 대상이
    한두 종목 바뀔 뿐이라 판단을 그르치지 않는다.
    """
    out = []
    page = 1
    while len(out) < size and page <= 10:
        url = ("https://m.stock.naver.com/api/stocks/marketValue/KOSPI"
               "?page=%d&pageSize=100" % page)
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


def refresh_universe(size=UNIVERSE_SIZE):
    """감시 대상을 새로 정한다. 못 받으면 기존 목록을 건드리지 않는다."""
    db_init()
    try:
        items = fetch_kospi_top(size)
    except Exception as e:
        return {"ok": False, "count": universe_size(),
                "error": "시가총액 순위를 받지 못했습니다: %s" % safe_message(e, 80)}
    if len(items) < 50:
        return {"ok": False, "count": universe_size(),
                "error": "받은 종목이 %d개뿐이라 반영하지 않았습니다." % len(items)}

    now = datetime.now(KST).isoformat(timespec="seconds")
    with _db_lock, db_conn() as conn:
        conn.execute("DELETE FROM dart_universe")
        conn.executemany(
            """INSERT INTO dart_universe (stock_code, name, rank, market_cap, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            [(it["code"], it["name"], i + 1, it["cap"], now)
             for i, it in enumerate(items)],
        )
    _meta_set("dart_universe_date", _today())
    return {"ok": True, "count": len(items)}


def universe_codes():
    db_init()
    with _db_lock, db_conn() as conn:
        rows = conn.execute("SELECT stock_code FROM dart_universe").fetchall()
    return {r["stock_code"] for r in rows}


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
        req = urllib.request.Request(url, headers={"User-Agent": "KJC-Holdings/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode("utf-8"))

        status_code = body.get("status")
        if status_code == "013":            # 아직 공시가 없다
            break
        if status_code != "000":
            raise RuntimeError("%s %s" % (status_code, body.get("message") or ""))

        out.extend(body.get("list") or [])
        if page >= int(body.get("total_page") or 1):
            break
        page += 1
    return out


def save_disclosures(items, only_codes, notified=0):
    """감시 대상 것만 저장한다. 새로 들어온 것만 돌려준다.

    notified=1 로 넣으면 '이미 알린 것으로 친다'. 처음 켤 때 오늘 치를
    한꺼번에 받아 오는데, 그걸 전부 보내면 텔레그램이 도배된다.
    """
    fresh = []
    db_init()
    with _db_lock, db_conn() as conn:
        for it in items:
            code = (it.get("stock_code") or "").strip()
            if code not in only_codes:
                continue
            rcept = (it.get("rcept_no") or "").strip()
            if not rcept:
                continue
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
            conn.execute(
                """INSERT INTO dart_disclosures
                     (rcept_no, corp_code, stock_code, corp_name, report_nm,
                      flr_nm, rcept_dt, rm, received_at, notified)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["rcept_no"], row["corp_code"], row["stock_code"],
                 row["corp_name"], row["report_nm"], row["flr_nm"],
                 row["rcept_dt"], row["rm"],
                 datetime.now(KST).isoformat(timespec="seconds"), notified),
            )
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
    }


# ---------------------------------------------------------------- 텔레그램

def telegram_config():
    """봇 토큰과 받을 사람. secrets.json 에 없으면 보내지 않는다."""
    path = os.path.join(HOLDINGS_DIR, "secrets.json")
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


def telegram_send(text):
    cfg = telegram_config()
    if not cfg:
        return False, "텔레그램 설정이 없습니다 (secrets.json 의 telegram)"
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
    """오늘 공시를 받아 감시 대상만 저장하고, 새 것 중 관심종목을 알린다."""
    db_init()
    today = _today()

    # 하루 한 번 해 두면 되는 것들
    if _meta_get("dart_corps_date") != today:
        try:
            refresh_corps(key)
        except Exception as e:
            _meta_set("dart_last_error", "대응표: %s" % safe_message(e, 120))
    if _meta_get("dart_universe_date") != today or universe_size() == 0:
        refresh_universe()

    codes = universe_codes()
    if not codes:
        _meta_set("dart_last_error", "감시 대상 목록이 비어 있습니다")
        return {"ok": False, "error": "감시 대상 목록이 비어 있습니다"}

    try:
        items = fetch_list(key, today, today)
    except Exception as e:
        msg = safe_message(e, 120)
        _meta_set("dart_last_error", msg)
        return {"ok": False, "error": msg}

    # 처음 켜는 날이면 오늘 치가 한꺼번에 들어온다. 그건 알리지 않는다.
    first_run = _meta_get("dart_last_poll") is None
    mark = 1 if (first_run and quiet_first_run) else 0

    fresh = save_disclosures(items, codes, notified=mark)
    sent = 0 if mark else notify(fresh)

    _meta_set("dart_last_poll", datetime.now(KST).isoformat(timespec="seconds"))
    _meta_set("dart_last_error", "")
    return {"ok": True, "received": len(items), "matched": len(fresh),
            "notified": sent, "firstRun": first_run}


def _should_poll(now=None):
    now = now or datetime.now(KST)
    if now.weekday() >= 5:
        return False
    hm = now.hour * 60 + now.minute
    return POLL_FROM <= hm < POLL_TO


def start_poller():
    """백그라운드로 5분마다 한 바퀴 돈다. 키가 없으면 아무것도 하지 않는다."""
    key = get_key()
    if not key:
        return False

    def loop():
        time.sleep(5)            # 서버가 막 뜬 참이라 잠깐 기다렸다 시작한다
        while True:
            try:
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
