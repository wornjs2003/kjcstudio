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


# ── 시세 · 봉 받기 (묶음 2 · 2026-10-07) ──────────────────────────────────────────
#
# **KIS 를 부르는 함수(`kis_get`)는 인자로 받는다** — kis_proxy 가 이 파일을 import 하므로 거꾸로 부르면
# 서로 물린다. 돌려주는 모양은 국내와 같게 맞춘다(봉은 ts · open · high · low · close · volume).
# 국내와 다른 점: 가격이 **달러 소수**다 — 봉 표 칸이 INTEGER 여도 SQLite 는 소수를 REAL 로 그대로 둔다
# (2026-10-07 사본 실측 331.28 → real).

import re
from datetime import timedelta

#: 미국 티커 모양 — 대문자로 시작 · 대문자 · 숫자 · 점 · 슬래시 · 하이픈(BRK/B). 6자리 숫자인 국내 코드와 안 겹친다
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9./-]{0,9}$")

PRICE_PATH = "/uapi/overseas-price/v1/quotations/price-detail"
PRICE_TR = "HHDFS76200200"
DAILY_PATH = "/uapi/overseas-price/v1/quotations/dailyprice"
DAILY_TR = "HHDFS76240000"
MIN_PATH = "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice"
MIN_TR = "HHDFS76950200"

#: 일·주·월봉의 GUBN — 년봉은 KIS 에 없어 월봉을 묶어 만든다
DAILY_GUBN = {"D": "0", "W": "1", "M": "2"}
#: 한 번에 오는 봉 수(일·주·월 100 · 5분 120) — 이어 받기 상한을 정할 때 쓴다
DAILY_PER_CALL = 100
MIN_PER_CALL = 120
#: 5분봉을 한 번에 몇 쪽까지 이어 받나. 하루(04:00~20:00)가 192봉이라 두 쪽이 하루치다
US_5M_PAGES = 2
#: 정규장 — 미국 현지 시각(HHMMSS). 16:00 봉에 종가 동시호가가 든다(2026-10-07 AAPL 실측 거래량 943만) — 국내 15:30 봉과 같은 자리라 넣는다
REGULAR_FROM, REGULAR_TO = "093000", "160000"

_sym_cache = {"at": 0.0, "map": {}}


def _symbols():
    """`symbol_map()` 을 1분 들고 있는다 — 시세를 부를 때마다 표 전체를 읽지 않게."""
    if time.time() - _sym_cache["at"] > 60:
        _sym_cache["map"] = symbol_map()
        _sym_cache["at"] = time.time()
    return _sym_cache["map"]


def is_us(code):
    """미국 티커인가 — 모양이 맞고 **us_symbols 에 있어야** 한다(거래소 코드를 알아야 부를 수 있다)."""
    return bool(code) and bool(TICKER_RE.match(code)) and code in _symbols()


def excd_of(code):
    return (_symbols().get(code) or {}).get("excd")


def _f(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _i(v):
    x = _f(v)
    return int(x) if x is not None else None


def us_price(kis_get, cfg, code):
    """미국 현재가 — 상세 API 한 번으로 국내 세 모양(price · prices · quotes)이 쓰는 칸을 다 채운다."""
    data = kis_get(cfg, PRICE_PATH, {"AUTH": "", "EXCD": excd_of(code), "SYMB": code}, PRICE_TR)
    o = (data or {}).get("output") or {}
    last, base = _f(o.get("last")), _f(o.get("base"))
    chg = round(last - base, 4) if last is not None and base is not None else None
    pct = round(chg / base * 100, 2) if chg is not None and base else None
    info = _symbols().get(code) or {}
    return {
        "code": code, "name": info.get("name_ko") or info.get("name_en"), "currency": "USD",
        "price": last, "prev": base, "change": chg, "amt": chg, "changePct": pct, "pct": pct,
        "sign": "2" if (chg or 0) > 0 else ("5" if (chg or 0) < 0 else "3"),
        "open": _f(o.get("open")), "high": _f(o.get("high")), "low": _f(o.get("low")),
        "volume": _i(o.get("tvol")), "value": _f(o.get("tamt")),
        "marketCap": _f(o.get("tomv")), "per": _f(o.get("perx")), "pbr": _f(o.get("pbrx")),
        "eps": _f(o.get("epsx")), "bps": _f(o.get("bpsx")),
        "high52": _f(o.get("h52p")), "low52": _f(o.get("l52p")), "source": "KIS",
    }


def us_bars(kis_get, cfg, code, period, limit):
    """일·주·월·년봉 → 봉 목록(과거 → 최신). 년봉은 월봉을 해마다 묶는다(ts = 그해 마지막 봉 날짜 · 국내와 같은 모양)."""
    gubn = DAILY_GUBN.get("M" if period == "Y" else period)
    want = limit * 12 if period == "Y" else limit
    pages = max(1, min(10, -(-want // DAILY_PER_CALL)))
    out, bymd = {}, ""
    for _ in range(pages):
        data = kis_get(cfg, DAILY_PATH, {"AUTH": "", "EXCD": excd_of(code), "SYMB": code,
                                         "GUBN": gubn, "BYMD": bymd, "MODP": "1"}, DAILY_TR)
        rows = (data or {}).get("output2") or []
        if not isinstance(rows, list) or not rows:
            break
        for r in rows:
            d = (r.get("xymd") or "").strip()
            c = _f(r.get("clos"))
            if len(d) == 8 and c is not None:
                out[d] = {"ts": d, "open": _f(r.get("open")), "high": _f(r.get("high")),
                          "low": _f(r.get("low")), "close": c, "volume": _i(r.get("tvol"))}
        oldest = min(out)
        if len(rows) < DAILY_PER_CALL or len(out) >= want:
            break
        bymd = (datetime.strptime(oldest, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
    bars = [out[k] for k in sorted(out)]
    if period != "Y":
        return bars
    years = {}
    for b in bars:                                   # 과거 → 최신 순이라 첫 봉이 시가 · 마지막이 종가
        y = years.get(b["ts"][:4])
        if y is None:
            years[b["ts"][:4]] = dict(b)
        else:
            y.update(ts=b["ts"], close=b["close"], high=max(y["high"], b["high"]),
                     low=min(y["low"], b["low"]), volume=(y["volume"] or 0) + (b["volume"] or 0))
    return [years[k] for k in sorted(years)]


def us_5m(kis_get, cfg, code, pages=US_5M_PAGES):
    """5분봉 → 봉 목록(과거 → 최신). ts 는 `US_SHOW_KST` 면 한국 시각(kymd+khms), 아니면 현지(xymd+xhms).

    `US_REGULAR_ONLY` 면 현지 09:30~16:00 봉만 둔다. 한 쪽 120봉 · `pages` 쪽까지 이어 받는다
    (처음 채울 때 `US_5M_PAGES` · 그 뒤 갱신은 한 쪽 — 120봉이 10시간이라 장중 갱신에는 한 쪽이면 된다).
    """
    out, keyb, nxt = {}, "", ""
    for _ in range(max(1, pages)):
        data = kis_get(cfg, MIN_PATH, {"AUTH": "", "EXCD": excd_of(code), "SYMB": code, "NMIN": "5",
                                       "PINC": "1", "NEXT": nxt, "NREC": str(MIN_PER_CALL),
                                       "FILL": "", "KEYB": keyb}, MIN_TR)
        rows = (data or {}).get("output2") or []
        if not isinstance(rows, list) or not rows:
            break
        last_local = None
        for r in rows:
            xd, xt = (r.get("xymd") or "").strip(), (r.get("xhms") or "").strip()
            kd, kt = (r.get("kymd") or "").strip(), (r.get("khms") or "").strip()
            c = _f(r.get("last"))
            if len(xd) != 8 or len(xt) != 6 or c is None:
                continue
            last_local = xd + xt
            if US_REGULAR_ONLY and not (REGULAR_FROM <= xt <= REGULAR_TO):
                continue
            ts = (kd + kt[:4]) if US_SHOW_KST else (xd + xt[:4])
            out[ts] = {"ts": ts, "open": _f(r.get("open")), "high": _f(r.get("high")),
                       "low": _f(r.get("low")), "close": c, "volume": _i(r.get("evol"))}
        if len(rows) < MIN_PER_CALL or not last_local:
            break
        # 다음 쪽 — 이번 쪽 가장 이른 봉의 한 칸 앞 (open-trading-api 예제의 KEYB 모양)
        prev = datetime.strptime(min(r["xymd"] + r["xhms"] for r in rows if r.get("xymd") and r.get("xhms")),
                                 "%Y%m%d%H%M%S") - timedelta(minutes=5)
        keyb, nxt = prev.strftime("%Y%m%d%H%M%S"), "1"
    return [out[k] for k in sorted(out)]


# ── 미국 장 시간 (묶음 3 · 2026-10-07) ─────────────────────────────────────────────
#
# **미국 동부 시각으로 센다** — 서머타임을 zoneinfo 가 따라간다(2026-10-07 지금 서머타임 · 11월 1일에 끝남).
# 한국 시각으로 박으면 서머타임이 바뀌는 날 한 시간이 어긋난다.

from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
#: 정규장 — 동부 시각 분(09:30 · 16:00). 미리받기는 마감 봉(16:00)이 닫히는 16:05 까지 돈다
SESSION_OPEN_MIN, SESSION_CLOSE_MIN = 9 * 60 + 30, 16 * 60
#: 장 마감 뒤 일·주·월·년봉 마지막 봉을 받는 시각 — 동부 16:10
AFTER_CLOSE_MIN = 16 * 60 + 10
#: 휴장으로 판정하는 시각 — 동부 10:00. 이때까지 오늘 봉이 하나도 없으면 휴장으로 본다
#: (시세가 지연이어도 30분이면 첫 봉이 든다 — 개장 직후에 판정하면 지연 탓에 장날을 휴장으로 읽는다)
HOLIDAY_JUDGE_MIN = 10 * 60


def et_now():
    return datetime.now(ET)


def session_state(now=None):
    """지금 미국 장이 어디쯤인가 → ("pre" | "open" | "after" | "closed", 동부 날짜 YYYYMMDD, 지금 분).

    open 은 09:30~16:05(마감 봉이 닫힐 때까지), after 는 16:05 뒤 그날, 주말은 closed.
    휴장일은 여기서 모른다 — 미리받기가 그날 첫 봉으로 판정한다.
    """
    now = now or et_now()
    d, m = now.strftime("%Y%m%d"), now.hour * 60 + now.minute
    if now.weekday() >= 5:
        return "closed", d, m
    if m < SESSION_OPEN_MIN:
        return "pre", d, m
    if m <= SESSION_CLOSE_MIN + 5:
        return "open", d, m
    return "after", d, m


def session_open_kst(et_date):
    """그날 동부 09:30 이 한국 시각으로 몇 시인가 → 봉 ts 와 견줄 YYYYMMDDHHMM.

    `US_SHOW_KST` 가 꺼져 있으면 봉 ts 가 현지 시각이므로 현지 그대로 돌려준다.
    """
    t = datetime.strptime(et_date, "%Y%m%d").replace(
        hour=SESSION_OPEN_MIN // 60, minute=SESSION_OPEN_MIN % 60, tzinfo=ET)
    if US_SHOW_KST:
        t = t.astimezone(KST)
    return t.strftime("%Y%m%d%H%M")
