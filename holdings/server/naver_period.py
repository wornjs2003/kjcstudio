"""「지금 뜨는 산업」 국내 주간 · 월간 — 네이버 묶음 안 종목들의 기간 등락률 평균 (2026-10-08 재권님 「네이버로」).

네이버 업종 · 테마 목록은 **일간 등락률만** 준다(기간 인자를 넣어도 같은 값 · 2026-10-08 실측).
그래서 묶음은 네이버 것을 그대로 두고, 묶음 안 종목마다 5거래일 · 20거래일 등락률을 내어
**단순 평균**한다. 일간 화면과 같은 묶음 · 같은 이름이고, 테마도 된다.

── 언제 받나 ──

**장 마감 뒤 하루 한 번** 받는다(`BATCH_AFTER` 이후 · 평일). 값은 그날 종가 기준이고 장중에는 안 바뀐다.
받는 양 — 묶음 목록 4번 · 묶음 종목 목록 약 350번 · 종목 일별 종가 약 2천6백 번(한 종목 1번에 21거래일치).
네이버만 부르고 **KIS 는 안 부른다.** `CALL_GAP` 간격으로 차례로 불러 십 분 남짓 걸린다.

**받는 것은 DB 에 쓰는 서버(8765) 하나다** — `marketdb.writable()`. 나머지 서버는 같은 표를 읽기만 한다.
받은 것이 하나도 없으면 「못 쟀다」 로 낸다 — 빈 목록을 `0` 으로 채우지 않는다.

── 표 ──

    naver_period_stock   code · name · c0(마지막 종가) · pw · pm(주간 · 월간 등락률 %) · ts(마지막 종가 날짜)

**액면병합 · 분할 날만 그날 등락률로 바꾼다.** 네이버 일별 종가는 그것을 고치지 않은 값이다 —
2026-10-08 실측으로 씨아이테크가 907 → 7,670원(그날 등락률 −15.44%)이라 종가로 견주면 +700% 가 되고,
그런 종목이 46개였다. 그렇다고 등락률만 이어 곱하면 안 된다 — 같은 날 삼성전자의 10-02 등락률이 0.00 인데
종가는 274,500 → 276,000 이었다. 그래서 날마다 **종가 변화**를 쓰고, 그것이 그날 등락률과
`SPLIT_GAP` 넘게 어긋나는 날만 등락률로 바꾼다.
    naver_period_member  kind · no · code — 묶음 안 종목
    naver_period_group   kind · no · name · rank_d(네이버 순서)
"""

import json
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import dart
import marketdb

KST = timezone(timedelta(hours=9))
BASE = "https://m.stock.naver.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://m.stock.naver.com/",
}
PAGE = 100                    # 네이버가 한 번에 주는 최대(300 은 빈 응답 · 2026-10-08 실측)
SPAN_BACK = {"w": 5, "m": 20}
BATCH_AFTER = (16, 10)        # 장 마감(15:30) · 종가 확정(16:00 무렵) 뒤
SPLIT_GAP = 15.0              # 종가 변화와 그날 등락률이 이만큼(%p) 어긋나면 액면 변동으로 본다
CALL_GAP = 0.15               # 네이버 호출 사이 — 한도가 공개돼 있지 않아 넉넉히 띄운다
CHECK_SEC = 600               # 받을 때가 됐나 보는 간격
MAX_GROUP_COUNT = 1000        # 「기타」 처럼 분류가 아닌 묶음은 뺀다(naver.py 와 같은 기준)

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS naver_period_stock (
         code TEXT PRIMARY KEY, name TEXT, c0 REAL, pw REAL, pm REAL, ts TEXT, updated_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS naver_period_member (
         kind TEXT NOT NULL, no INTEGER NOT NULL, code TEXT NOT NULL, PRIMARY KEY (kind, no, code))""",
    """CREATE TABLE IF NOT EXISTS naver_period_group (
         kind TEXT NOT NULL, no INTEGER NOT NULL, name TEXT, pos INTEGER, PRIMARY KEY (kind, no))""",
]

_run_lock = threading.Lock()
state = {"running": False, "last": None, "error": None, "calls": 0}


def _get(url, tries=3):
    """한 번 끊겨도 한 바퀴가 통째로 멈추지 않게 다시 부른다(2026-10-08 실측 — 3천 번 중 한 번 시간 초과로 멈췄다)"""
    for i in range(tries):
        state["calls"] += 1
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r:
                body = r.read().decode("utf-8")
            time.sleep(CALL_GAP)
            return json.loads(body) if body.strip() else None
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2.0 * (i + 1))


def _num(v):
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def db_init():
    if not marketdb.writable():
        return
    with dart._db_lock, dart.db_conn() as conn:
        for q in SCHEMA:
            conn.execute(q)


# ── 받기 ────────────────────────────────────────────────────────────────

def _all_groups(kind):
    out, page = [], 1
    while True:
        j = _get("%s/stocks/%s?page=%d&pageSize=%d" % (BASE, kind, page, PAGE)) or {}
        rows = j.get("groups") or []
        out += [g for g in rows if (_num(g.get("totalCount")) or 0) <= MAX_GROUP_COUNT]
        if len(rows) < PAGE:
            return out
        page += 1


def _members(kind, no):
    out, page = [], 1
    while True:
        j = _get("%s/stocks/%s/%d?page=%d&pageSize=%d" % (BASE, kind, no, page, PAGE)) or {}
        rows = j.get("stocks") or []
        for s in rows:
            code = (s.get("itemCode") or "").strip()
            if len(code) == 6:
                out.append((code, s.get("stockName")))
        if len(rows) < PAGE:
            return out
        page += 1


def _closes(code):
    """최근 → 과거 순 (날짜, 종가, 그날 등락률%) 21개까지 — 20일 변화에 앞 하루가 더 든다"""
    j = _get("%s/stock/%s/price?pageSize=%d&page=1" % (BASE, code, SPAN_BACK["m"] + 1)) or []
    out = []
    for r in j if isinstance(j, list) else []:
        c = _num(r.get("closePrice"))
        d = (r.get("localTradedAt") or "")[:10].replace("-", "")
        if c and len(d) == 8:
            out.append((d, c, _num(r.get("fluctuationsRatio"))))
    return out


def _chain(cl, n):
    """최근 n 거래일 등락률(%). 날마다 종가 변화를 이어 곱하되, 액면 변동 날은 그날 등락률로. 모자라면 None"""
    if len(cl) <= n:
        return None
    f = 1.0
    for i in range(n):
        day = (cl[i][1] / cl[i + 1][1] - 1.0) * 100.0
        r = cl[i][2]
        if r is not None and abs(day - r) > SPLIT_GAP:
            day = r
        f *= 1.0 + day / 100.0
    return (f - 1.0) * 100.0


def run():
    """한 바퀴 받는다 → {"groups", "stocks", "calls", "sec"}. 겹쳐 부르면 뒤쪽은 바로 돌아간다."""
    if not marketdb.writable():
        return {"skipped": "읽기 전용 서버"}
    if not _run_lock.acquire(blocking=False):
        return {"skipped": "이미 받는 중"}
    state.update(running=True, error=None)
    t0, c0 = time.time(), state["calls"]
    try:
        db_init()
        now = datetime.now(KST).isoformat(timespec="seconds")
        groups, members, names = [], [], {}
        for kind in ("industry", "theme"):
            for pos, g in enumerate(_all_groups(kind)):
                no = int(g["no"])
                groups.append((kind, no, g.get("name"), pos))
                for code, name in _members(kind, no):
                    members.append((kind, no, code))
                    names[code] = name
        stocks = []
        for code in names:
            try:
                cl = _closes(code)
            except Exception:
                cl = []
            if not cl:
                continue
            stocks.append((code, names[code], cl[0][1], _chain(cl, SPAN_BACK["w"]),
                           _chain(cl, SPAN_BACK["m"]), cl[0][0], now))
        if not groups or not stocks:
            raise RuntimeError("네이버에서 받은 것이 없습니다")
        # **다 받은 뒤에 갈아끼운다** — 반쯤 받다 끊기면 옛 값을 그대로 둔다
        with dart._db_lock, dart.db_conn() as conn:
            conn.execute("DELETE FROM naver_period_group")
            conn.execute("DELETE FROM naver_period_member")
            conn.execute("DELETE FROM naver_period_stock")    # 상장폐지 종목이 남지 않게
            conn.executemany("INSERT OR REPLACE INTO naver_period_group VALUES (?, ?, ?, ?)", groups)
            conn.executemany("INSERT OR REPLACE INTO naver_period_member VALUES (?, ?, ?)", members)
            conn.executemany("INSERT OR REPLACE INTO naver_period_stock VALUES (?, ?, ?, ?, ?, ?, ?)", stocks)
        dart._meta_set("naver_period_date", datetime.now(KST).strftime("%Y%m%d"))
        out = {"groups": len(groups), "stocks": len(stocks), "calls": state["calls"] - c0,
               "sec": round(time.time() - t0)}
        state["last"] = out
        return out
    except Exception as e:
        state["error"] = type(e).__name__
        raise
    finally:
        state["running"] = False
        _run_lock.release()


def _due():
    try:
        with dart._db_lock, dart.db_conn() as conn:
            have = conn.execute("SELECT COUNT(*) FROM naver_period_stock").fetchone()[0]
    except Exception:
        have = 0
    if not have:
        return True                                  # 처음 — 시각을 안 기다린다
    now = datetime.now(KST)
    if now.weekday() >= 5 or (now.hour, now.minute) < BATCH_AFTER:
        return False
    return dart._meta_get("naver_period_date") != now.strftime("%Y%m%d")


def start(port, main_port):
    """하루 한 번 받는 뒤 작업을 켠다. **메인서버(8765)에서만** 켠다 — 쓸 수 있는 서버가 둘이면(서비스방이
    자기 DB 에 쓰게 떠 있을 때) 네이버를 두 배로 부른다(창구 검수 · 2026-10-08). 다른 서버는 표를 읽기만 한다."""
    if not marketdb.writable() or port != main_port:
        return False

    def loop():
        while True:
            try:
                if _due():
                    got = run()
                    print("  업종 기간  : 묶음 %s · 종목 %s · 네이버 %s번 · %s초"
                          % (got.get("groups"), got.get("stocks"), got.get("calls"), got.get("sec")))
            except Exception as e:
                print("  업종 기간  : 못 받았습니다 (%s)" % type(e).__name__)
            time.sleep(CHECK_SEC)

    threading.Thread(target=loop, daemon=True, name="naver-period").start()
    return True


# ── 읽기 ────────────────────────────────────────────────────────────────

def _pct(row, span):
    return row["pw"] if span == "w" else row["pm"]


def _read(sql, args=()):
    try:
        with dart._db_lock, dart.db_conn() as conn:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
    except Exception:
        return None                                  # 표가 아직 없다 — 「못 쟀다」


def groups(kind, span):
    """묶음 전부 → 기간 등락률(구성 종목 단순 평균) 큰 순. 받은 것이 없으면 None.

    칸 이름은 `naver.groups` 와 같다(화면이 같은 코드로 그린다). `measured` 는 평균에 든 종목 수.
    """
    if kind not in ("industry", "theme") or span not in SPAN_BACK:
        raise ValueError("kind · span 이 올바르지 않습니다.")
    gs = _read("SELECT no, name, pos FROM naver_period_group WHERE kind = ?", (kind,))
    rows = _read("""SELECT m.no, s.pw, s.pm, s.ts FROM naver_period_member m
                      JOIN naver_period_stock s ON s.code = m.code WHERE m.kind = ?""", (kind,))
    cnt = _read("SELECT no, COUNT(*) AS n FROM naver_period_member WHERE kind = ? GROUP BY no", (kind,))
    if not gs or rows is None:
        return None
    by = {}
    asof = None
    for r in rows:
        p = _pct(r, span)
        if p is not None:
            by.setdefault(r["no"], []).append(p)
            asof = max(asof or r["ts"], r["ts"])
    n = {c["no"]: c["n"] for c in (cnt or [])}
    out = []
    for g in gs:
        ps = by.get(g["no"]) or []
        out.append({
            "no": g["no"], "name": g["name"],
            "pct": (sum(ps) / len(ps)) if ps else None,
            "rise": sum(1 for p in ps if p > 0), "steady": sum(1 for p in ps if p == 0),
            "fall": sum(1 for p in ps if p < 0),
            "count": n.get(g["no"], 0), "measured": len(ps),
        })
    out.sort(key=lambda r: (r["pct"] is None, -(r["pct"] or 0)))
    return {"rows": out, "total": len(out), "asof": asof}


def stocks(kind, no, span):
    """그 묶음의 종목 → 기간 등락률 큰 순. 가격은 마지막 종가. 받은 것이 없으면 None."""
    if kind not in ("industry", "theme") or span not in SPAN_BACK:
        raise ValueError("kind · span 이 올바르지 않습니다.")
    rows = _read("""SELECT s.code, s.name, s.c0, s.pw, s.pm, s.ts FROM naver_period_member m
                      JOIN naver_period_stock s ON s.code = m.code WHERE m.kind = ? AND m.no = ?""",
                 (kind, int(no)))
    if rows is None:
        return None
    out = []
    for r in rows:
        p = _pct(r, span)
        out.append({"code": r["code"], "name": r["name"], "price": r["c0"],
                    "amt": (r["c0"] - r["c0"] / (1.0 + p / 100.0)) if (r["c0"] and p is not None and p > -100) else None,
                    "pct": p, "volume": None, "value": None})
    out.sort(key=lambda r: (r["pct"] is None, -(r["pct"] or 0)))
    return out
