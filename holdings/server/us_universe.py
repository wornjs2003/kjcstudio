"""미국 종목 목록 — 나스닥100 구성종목과 종목마다의 거래소 코드 (2026-10-07 재권님 「응 해줘」).

국내의 코스피200 · 코스닥150(`dart.INDEX_LISTS`) 옆에 **나스닥100** 을 둔다. 받는 곳이 둘이다.

    구성종목     nasdaq.com 공개 목록         지수 구성 표(`index_members`)에 `NDX100` 으로
    거래소 코드   KIS 종목 마스터 파일 셋       새 표 `us_symbols` 에 (티커 · 거래소 · 한글 · 영문 · 주식/ETF)

**마스터 파일만으로는 구성종목을 못 고른다.** 마스터에 「지수 구성 여부」 칸(sjong)이 있지만
2026-10-07 실측으로 세 파일 12,817줄이 **전부 0** 이었다. 그래서 목록은 nasdaq.com 에서 받는다.

**KIS 해외 시세를 부르려면 거래소 코드(NAS · NYS · AMS)가 꼭 있어야 한다** — 국내처럼 종목코드만으로는
안 된다. 나스닥100 은 나스닥 종목뿐이지만, 묶음을 넓힐 때(S&P500 은 거래소를 섞는다) 그대로 쓰도록
세 거래소를 다 받아 둔다. KIS 호출은 하나도 없다 — 둘 다 공개 파일이다.

하루 한 번(`US_REFRESH_SEC` 마다 날짜를 보고) 받는다. 받는 것이 실패하면 옛 목록을 그대로 둔다.
DB 에 쓸 수 있는 서버만 받는다(`marketdb.writable()`).
"""
import io
import json
import threading
import time
import urllib.request
import zipfile
from datetime import datetime

import dart
import marketdb
from dart import KST
from secrets_guard import safe_message

#: 지수 구성 표에 쓰는 묶음 이름 — 국내 `KPI200` · `KQI150` 과 같은 자리
NDX100 = "NDX100"

#: 나스닥100 구성종목 목록 (nasdaq.com 공개 API — 브라우저 이름표가 없으면 응답이 안 온다)
NDX100_URL = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"

#: KIS 해외 종목 마스터 — 거래소마다 파일 하나 (open-trading-api 의 stocks_info 가 쓰는 주소)
MASTER_URL = "https://new.real.download.dws.co.kr/common/master/%smst.cod.zip"
MASTER_EXCD = ("NAS", "NYS", "AMS")

#: 마스터의 상품 구분(stis) → 우리 이름. 지수(1) · 워런트(4)는 받지 않는다
MASTER_KIND = {"2": "stock", "3": "etf"}

#: 하루가 바뀌었는지 보는 간격(초). 받는 것은 하루 한 번이다
US_REFRESH_SEC = 3600

# ── 화면에 보이는 모양 — **한 곳에서만 정한다** (2026-10-07 재권님 기본값) ──────────────
# 재권님이 따로 말씀이 없으셔서 기본으로 정했다. 바꾸시면 이 두 줄만 고친다.
#: 미국 봉의 시각을 한국 시각으로 보인다 (False 면 미국 현지 시각)
US_SHOW_KST = True
#: 정규장(미국 09:30~16:00)만 넣는다 (False 면 프리 · 애프터마켓 04:00~20:00 까지)
US_REGULAR_ONLY = True

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS us_symbols (
         symbol      TEXT PRIMARY KEY,      -- KIS 마스터의 티커 (AAPL · BRK/B)
         excd        TEXT NOT NULL,         -- NAS | NYS | AMS — KIS 해외 시세의 거래소 코드
         name_ko     TEXT,
         name_en     TEXT,
         kind        TEXT,                  -- stock | etf
         updated_at  TEXT
       )""",
]

_lock = threading.Lock()


def db_init():
    dart.db_init()                       # index_members · sync_meta 는 dart 가 만든다
    with dart._db_lock, dart.db_conn() as conn:
        for sql in SCHEMA:
            conn.execute(sql)


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_ndx100():
    """나스닥100 구성종목 → [(티커, 영문 이름)]. 2026-10-07 실측 101종목(GOOGL · GOOG 처럼 한 회사 두 줄이 있다)."""
    data = json.loads(_get(NDX100_URL).decode("utf-8"))
    rows = ((data.get("data") or {}).get("data") or {}).get("rows") or []
    out = []
    for r in rows:
        sym = (r.get("symbol") or "").strip().upper()
        if sym:
            out.append((sym, (r.get("companyName") or "").strip()))
    return out


def fetch_master(excd):
    """KIS 마스터 한 거래소 → [(티커, 거래소, 한글, 영문, 종류)]. 탭으로 나뉜 cp949 글이다.

    칸 순서는 open-trading-api 의 해외종목코드정보 헤더를 따른다 — 4 symb · 6 knam · 7 enam · 8 stis.
    """
    raw = _get(MASTER_URL % excd.lower(), timeout=60)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name = z.namelist()[0]
        text = z.read(name).decode("cp949", errors="replace")
    out = []
    for line in text.splitlines():
        f = line.split("\t")
        if len(f) < 9 or f[2].strip() != excd:
            continue
        kind = MASTER_KIND.get(f[8].strip())
        if not kind:
            continue
        out.append((f[4].strip(), excd, f[6].strip(), f[7].strip(), kind))
    return out


def refresh():
    """목록 둘을 받아 저장한다 → {"symbols": 몇, "NDX100": 몇, "missing": [마스터에 없는 티커]}.

    **실패한 쪽은 옛 목록을 그대로 둔다** — 지우고 나서 받지 않는다(`dart.refresh_index_members` 와 같은 모양).
    """
    db_init()
    now = datetime.now(KST).isoformat(timespec="seconds")
    out = {}
    syms = []
    for excd in MASTER_EXCD:
        try:
            syms.extend(fetch_master(excd))
        except Exception as e:
            dart._meta_set("us_last_error", "마스터 %s: %s" % (excd, safe_message(e, 90)))
            syms = []                     # 한 거래소라도 빠지면 이번에는 표를 안 바꾼다
            break
    if syms:
        with dart._db_lock, dart.db_conn() as conn:
            conn.execute("DELETE FROM us_symbols")
            conn.executemany(
                "INSERT OR REPLACE INTO us_symbols (symbol, excd, name_ko, name_en, kind, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)", [s + (now,) for s in syms])
        out["symbols"] = len(syms)
    try:
        members = fetch_ndx100()
    except Exception as e:
        dart._meta_set("us_last_error", "나스닥100: %s" % safe_message(e, 90))
        members = []
    if members:
        known = symbol_map()
        # 한글 이름이 있으면 그것을 쓴다 — 국내 구성종목도 한글 이름으로 들어 있다
        rows = [(s, NDX100, (known.get(s) or {}).get("name_ko") or n, now) for s, n in members]
        with dart._db_lock, dart.db_conn() as conn:
            conn.execute("DELETE FROM index_members WHERE index_code = ?", (NDX100,))
            conn.executemany(
                "INSERT INTO index_members (stock_code, index_code, name, updated_at) VALUES (?, ?, ?, ?)",
                rows)
        out[NDX100] = len(members)
        out["missing"] = [s for s, _ in members if s not in known]
    if out.get("symbols") and out.get(NDX100):
        dart._meta_set("us_members_date", datetime.now(KST).strftime("%Y%m%d"))
    return out


def symbol_map():
    """{티커: {"excd", "name_ko", "name_en", "kind"}} — 시세를 부를 때 거래소 코드를 여기서 찾는다."""
    with dart._db_lock, dart.db_conn() as conn:
        try:
            rows = conn.execute("SELECT symbol, excd, name_ko, name_en, kind FROM us_symbols").fetchall()
        except Exception:
            return {}                    # 아직 표가 없다(읽기 전용 서버가 먼저 떴을 때)
    return {r["symbol"]: {"excd": r["excd"], "name_ko": r["name_ko"],
                          "name_en": r["name_en"], "kind": r["kind"]} for r in rows}


def members(index_code=NDX100):
    """그 묶음의 티커 목록 (지수 구성 표 순서 그대로)."""
    with dart._db_lock, dart.db_conn() as conn:
        rows = conn.execute("SELECT stock_code FROM index_members WHERE index_code = ?",
                            (index_code,)).fetchall()
    return [r["stock_code"] for r in rows]


def start():
    """하루 한 번 목록을 받는 뒤 작업을 켠다. 쓸 수 없는 서버면 켜지 않는다."""
    if not marketdb.writable():
        return False

    def loop():
        while True:
            try:
                if dart._meta_get("us_members_date") != datetime.now(KST).strftime("%Y%m%d"):
                    with _lock:
                        got = refresh()
                    print("  미국 목록  : 종목 %s · 나스닥100 %s · 마스터에 없는 티커 %s"
                          % (got.get("symbols", "—"), got.get(NDX100, "—"),
                             ", ".join(got.get("missing") or []) or "없음"))
            except Exception as e:
                print("  미국 목록  : 못 받았습니다 (%s)" % type(e).__name__)
            time.sleep(US_REFRESH_SEC)

    threading.Thread(target=loop, daemon=True, name="us-universe").start()
    return True
