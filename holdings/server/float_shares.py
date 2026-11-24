"""풀린 주식수(유동 주식수) — 한 곳 (2026-11-24).

재권님 「응 해」(18:3x · 시황분석1 창 · 작업우선순위 경유) → 「응 만들어 커밋하고 언제쯤 다 받아지는지도 확인해줘」(18:3x · 개발2 창).
단타 「유통 대비 거래」(= 거래대금 ÷ 풀린 시총)의 바탕. 전에는 네이버에서 이미 받아 둔 종목만(company_profile 의 naver) 있어
보통주 1,069 중 647 만 값이 있었고 지난 판 13~33% 가 「못 잼」 이었다.

    풀린 주식수 = 유통주식수(OpenDART 「주식의 총수 현황」 stockTotqySttus 보통주 distb_stock_co = 발행 − 자기주식)
                 − 최대주주 + 특수관계인 기말 보유(「최대주주 현황」 hyslrSttus 보통주 「계」 줄 · 지배구조 dart_gov 가 밤마다 받아 둔 것)

받는 때 · 양 — 지배구조(dart_gov)와 같은 밤(20:00~07:00) · 같은 밤 몫(dart_gov.GOV_NIGHT_CALLS) · 같은 쉼(GOV_GAP_SEC) · 같은 하루 남김(GOV_RESERVE).
회사마다 보통 한 건(가장 최근 정기보고서 · 없으면 그 앞 둘까지). 시가총액 큰 회사(dart_universe)부터.

다시 받기 — 받은 뒤에 그 회사에 주식 수가 바뀌는 공시(아래 STALE_RE · 공시 바퀴가 쌓는 dart_disclosures)가 들어오거나 ·
KIS 상장주식수(시세 응답 lstn_stcn · note_listed)가 받아 둔 발행주식수와 LISTED_GAP_PCT 넘게 다르면 다음 밤에.

내주기(floats_info) — 한 곳 · 차례: ① dart(위 셈) ② naver(발행 × 유동비율 · 받아 둔 종목) ③ dart-유통(최대주주 보유를 모름 — 어림)
④ kis(상장주식 전체 — 어림). src 로 어느 것인지 함께 낸다. 우선주는 안 넣는다(company_profile.floats 와 같은 까닭).
**켜기는 FETCH 다** — 쌓는 것은 공시를 받는 쓰기 서버(8765) 하나 · 읽기 전용 서버는 같은 표를 읽기만 한다.
"""

import json
import re
import sys
import threading
import time
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import dart
import dart_gov
import marketdb

FETCH = True                 # 켜기 — 재권님 「응 만들어」(11-24 18:3x) · 끄려면 False(쌓인 것은 그대로 냄)
LISTED_GAP_PCT = 1.0         # KIS 상장주식수와 받아 둔 발행주식수가 이 % 넘게 다르면 다시 받음(주식 수가 바뀐 것)
CACHE_SEC = 300              # 내주기 메모리 — 분마다 부르는 곳(turnover · 단타 판)이 표를 매번 안 읽게
STALE_RE = re.compile(r"사업보고서|반기보고서|분기보고서|유상증자|무상증자|자기주식|최대주주|전환청구|신주인수권|교환청구|주식소각|감자|합병|분할|주식등의대량보유")
COMMON_KND = ("보통주", "보통주식", "의결권있는주식")   # 최대주주 현황 stock_knd 를 띄어쓰기 빼고 견줌(2026-11-24 dart_gov 2,566곳에서 센 이름)

SCHEMA = """CREATE TABLE IF NOT EXISTS float_shares (
      stock_code   TEXT PRIMARY KEY,
      corp_code    TEXT,
      year         TEXT,            -- 받은 보고서 해
      reprt        TEXT,            -- 보고서 갈래(11011 사업 · 11012 반기 · 11013 1분기 · 11014 3분기)
      stlm_dt      TEXT,            -- 그 표의 기준일
      issued       INTEGER,         -- 발행주식 총수(보통주)
      treasury     INTEGER,         -- 자기주식수
      distb        INTEGER,         -- 유통주식수 = 발행 − 자기주식
      major        INTEGER,         -- 최대주주 + 특수관계인 기말 보유(보통주) · 모르면 NULL
      major_year   TEXT,            -- 그 최대주주 현황의 해(지배구조 dart_gov)
      float_sh     INTEGER,         -- 풀린 주식수 = distb − major(모르면 NULL)
      status       TEXT,            -- ok · none(보고서 없음) · stale(다시 받을 차례)
      why          TEXT,            -- stale 까닭
      listed       INTEGER,         -- KIS 상장주식수(본 때)
      fetched_at   TEXT
)"""

_lock = threading.Lock()
_listed = {}                 # {code: KIS 상장주식수} — 시세 응답이 볼 때마다(note_listed) · 밤에 표와 견줌
_cache = {"at": 0.0, "data": None}
_state = {"started": False, "done": 0, "left": None, "stopped": None, "at": None}


def _now():
    return datetime.now(dart.KST)


def init():
    with dart.db_conn() as conn:
        conn.execute(SCHEMA)


def _rows(sql, args=()):
    try:
        with dart.db_conn() as conn:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
    except Exception:
        return []                                       # 표가 아직 없음 — 못 잼


def _int(v):
    try:
        return int(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def major_common(major_json):
    """최대주주 현황 줄들 → 보통주 최대주주 + 특수관계인 기말 보유 합 | None. 「계」 줄이 있으면 그것 · 없으면 줄 합(「계」 를 빼고)."""
    try:
        rows = json.loads(major_json or "[]")
    except ValueError:
        return None
    knd = lambda r: re.sub(r"\s", "", str(r.get("stock_knd") or ""))
    com = [r for r in rows if knd(r) in COMMON_KND]
    if not com:
        com = [r for r in rows if knd(r) in ("-", "")]  # 주식 종류를 안 적은 보고서 — 다 보통주로 봄
    if not com:
        return None
    tot = [r for r in com if str(r.get("nm") or "").strip() == "계"]
    vals = [_int(r.get("trmend_posesn_stock_co")) for r in (tot[:1] if tot else com)]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def _reports(now=None):
    """[(해, 보고서 갈래)] — 가장 최근에 나왔을 정기보고서부터 셋(제출 기한 다음 날부터 그것을 먼저 봄 · 늦게 낸 곳은 그 앞 것으로)."""
    now = now or _now()
    y, md = now.year, now.month * 100 + now.day
    seq = [(y, "11014"), (y, "11012"), (y, "11013"), (y - 1, "11011"), (y - 1, "11014"), (y - 1, "11012")]
    start = 0 if md >= 1115 else 1 if md >= 815 else 2 if md >= 516 else 3 if md >= 401 else 4   # 제출 기한(3분기 11-14 · 반기 8-14 · 1분기 5-15 · 사업 3-31) 다음 날부터
    return [(str(a), b) for a, b in seq[start:start + 3]]


def fetch_one(key, code, corp_code):
    """한 회사 — 주식의 총수 현황을 받아 표에 적는다 → status. 멈춰야 하면 dart_gov._Stop."""
    got = None
    for year, rp in _reports():
        st, d = dart_gov._get(key, "stockTotqySttus.json", {"corp_code": corp_code, "bsns_year": year, "reprt_code": rp})
        if st == "000":
            com = [r for r in d.get("list") or [] if re.sub(r"\s", "", str(r.get("se") or "")) in ("보통주", "보통주식")]
            if com:
                got = (year, rp, com[0])
                break
    g = dart_gov._rows("SELECT year, major FROM dart_gov WHERE stock_code = ? AND status = 'ok'", (code,))
    mj = major_common(g[0]["major"]) if g else None
    row = {"stock_code": code, "corp_code": corp_code, "year": None, "reprt": None, "stlm_dt": None, "issued": None, "treasury": None,
           "distb": None, "major": mj, "major_year": g[0]["year"] if g else None, "float_sh": None, "status": "none", "why": None,
           "listed": _listed.get(code), "fetched_at": _now().isoformat(timespec="seconds")}
    if got:
        year, rp, r = got
        iss, tr, ds = _int(r.get("istc_totqy")), _int(r.get("tesstk_co")), _int(r.get("distb_stock_co"))
        if ds is None and iss is not None:
            ds = iss - (tr or 0)
        fl = ds - mj if ds is not None and mj is not None and 0 <= mj < ds else None
        row.update(year=year, reprt=rp, stlm_dt=r.get("stlm_dt"), issued=iss, treasury=tr, distb=ds, float_sh=fl, status="ok")
    with dart.db_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO float_shares (%s) VALUES (%s)" % (",".join(row), ",".join("?" * len(row))), list(row.values()))
    _cache["at"] = 0.0
    return row["status"]


def _mark_stale(now=None):
    """받은 뒤 주식 수가 바뀌는 공시가 들어왔거나 KIS 상장주식수가 달라진 회사를 stale 로 → 그 수."""
    have = {r["stock_code"]: r for r in _rows("SELECT stock_code, issued, fetched_at, status FROM float_shares")}
    if not have:
        return 0
    marks = {}
    for r in _rows("SELECT stock_code, report_nm, received_at FROM dart_disclosures WHERE received_at >= ?",
                   ((_now() - timedelta(days=40)).isoformat(timespec="seconds"),)):
        h = have.get(r["stock_code"])
        if h and h["status"] != "stale" and (r["received_at"] or "") > (h["fetched_at"] or "") and STALE_RE.search(r["report_nm"] or ""):
            marks[r["stock_code"]] = "공시 " + (r["report_nm"] or "")[:40]
    for c, ls in list(_listed.items()):
        h = have.get(c)
        if h and h["status"] == "ok" and h["issued"] and ls and abs(ls / h["issued"] - 1) * 100 > LISTED_GAP_PCT:
            marks.setdefault(c, "상장주식수 %d ↔ 발행 %d" % (ls, h["issued"]))
    if marks:
        with dart.db_conn() as conn:
            conn.executemany("UPDATE float_shares SET status = 'stale', why = ? WHERE stock_code = ?", [(w, c) for c, w in marks.items()])
    return len(marks)


def todo():
    """받을 차례 — [(code, corp_code)]. 지배구조가 코스피 · 코스닥으로 본 회사 중 안 받았거나 stale · 시가총액 큰 회사부터."""
    corps = {r["stock_code"]: r["corp_code"] for r in dart_gov._rows("SELECT stock_code, corp_code FROM dart_gov WHERE corp_cls IN ('Y', 'K')")}
    have = {r["stock_code"]: r["status"] for r in _rows("SELECT stock_code, status FROM float_shares")}
    try:
        first = [r["stock_code"] for r in dart.universe_rows(None)]
    except Exception:
        first = []
    order = [c for c in first if c in corps] + sorted(c for c in corps if c not in set(first))
    return [(c, corps[c]) for c in order if c.endswith("0") and have.get(c) in (None, "stale")]


def fill(key, limit=None):
    if not marketdb.writable():
        return {"done": 0, "stopped": "읽기 전용", "left": None}
    init()
    with _lock:
        _mark_stale()
        jobs = todo()
        done, why = 0, None
        for code, corp_code in jobs:
            if limit is not None and done >= limit:
                break
            ok, why = dart_gov._room()
            if not ok:
                break
            try:
                fetch_one(key, code, corp_code)
            except dart_gov._Stop as e:
                why = str(e)
                dart._meta_set("float_shares_last_error", "%s %s: %s" % (_now().strftime("%m-%d %H:%M"), code, why))
                break
            done += 1
        return {"done": done, "stopped": why, "left": len(jobs) - done}


def start_filler():
    """밤마다 받는 바퀴 — 지배구조와 같은 밤 · 같은 몫. 공시를 받는 쓰기 서버만 부른다."""
    key = dart.get_key()
    if not (FETCH and key and marketdb.writable()) or _state["started"]:
        return False
    _state["started"] = True
    init()

    def loop():
        time.sleep(90)                                  # 지배구조 바퀴(30초 뒤)와 첫 바퀴가 겹치지 않게
        while True:
            try:
                if dart_gov._is_night() and dart_gov._room()[0]:
                    r = fill(key)
                    _state.update(r, at=_now().isoformat(timespec="seconds"))
                    dart._meta_set("float_shares_fill", json.dumps(_state, ensure_ascii=False))
                    if r["done"]:
                        print("  [풀린 주식수] %d곳 받음 · 남음 %s · 멈춤 %s" % (r["done"], r["left"], r["stopped"]), flush=True)
            except Exception as e:
                print("  [풀린 주식수] 예기치 못한 오류: %s" % type(e).__name__, flush=True)
            time.sleep(dart_gov.GOV_TICK_SEC)

    threading.Thread(target=loop, daemon=True, name="float-shares").start()
    return True


def note_listed(code, listed):
    """시세 응답이 볼 때마다 — KIS 상장주식수를 메모리에(밤에 표와 견줌 · ④ 어림의 재료). 받지 않는다."""
    if code and isinstance(listed, int) and listed > 0:
        _listed[code] = listed


def floats_info():
    """{code: (풀린 주식수, src)} — 위 차례 ①~④ 한 곳. 우선주는 안 넣는다."""
    if _cache["data"] is not None and time.time() - _cache["at"] < CACHE_SEC:
        return _cache["data"]
    import company_profile
    out = {}
    for c, (sh, src) in company_profile.naver_floats().items():
        out[c] = (sh, src)
    dist = {}
    for r in _rows("SELECT stock_code, float_sh, distb, listed FROM float_shares WHERE status IN ('ok', 'stale')"):
        c = r["stock_code"]
        if not c.endswith("0"):
            continue
        if r["float_sh"]:
            out[c] = (r["float_sh"], "dart")             # ① 이 이김
        elif r["distb"]:
            dist[c] = r["distb"]
    for c, v in dist.items():
        out.setdefault(c, (v, "dart-유통"))             # ③ 최대주주 보유를 모름 — 어림
    for c, v in _listed.items():
        if c.endswith("0"):
            out.setdefault(c, (v, "kis"))               # ④ 상장주식 전체 — 어림
    _cache.update(at=time.time(), data=out)
    return out


def status():
    rows = _rows("SELECT status, COUNT(*) n, SUM(float_sh IS NOT NULL) f FROM float_shares GROUP BY status")
    try:
        last = json.loads(dart._meta_get("float_shares_fill") or "null")
    except ValueError:
        last = None
    return {"fetch": FETCH, "byStatus": {r["status"]: {"n": r["n"], "float": r["f"]} for r in rows}, "todo": len(todo()),
            "last": last, "listedSeen": len(_listed), "nightCalls": dart_gov.GOV_NIGHT_CALLS, "gapSec": dart_gov.GOV_GAP_SEC}
