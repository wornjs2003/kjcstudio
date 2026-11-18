# -*- coding: utf-8 -*-
"""섹터수급 — 프리장 08:00 부터 정규장 09:30 까지 업종 · 테마별 10분 거래대금 (2026-11-18).

재권님 13:03 「섹터수급 이라고 단타창에 칸 추가해줘. 이건 동일업종에 돈이 들어오는거 체크하는거야. 프리장부터 정규장 9시 30분까지
재야해」 → 시황분석1 그림 → 「응 만들어줘」 · 「그럼 테마도 만들어줘」 · 「다로 해줘」(시황분석1 창 · 13:2x) →
서버 안 「커밋해」(16:50 · 개발1 창). 화면은 시황분석1 이 만든다.

    언제      평일 SNAPS 시각마다 한 번 — 종목마다 그날 **누적 거래대금** 사진(멀티 시세 30종목씩)
                08:10 ~ 08:50   넥스트(NX) 만 — 프리장(08:00~08:50) · KRX 는 아직 안 열렸다
                09:10 ~ 09:30   KRX(J) + 넥스트(NX) 둘 다 — 09:00 동시호가 체결은 09:00 칸에 든다
              08:50 사진은 08:51 에 찍는다 — 프리장 마지막 몇 초 체결까지 담으려고
    칸        SLOTS — 칸 이름은 시작 시각 · 칸 값 = 끝 사진 누적 − 시작 사진 누적(08:00 칸은 0 에서). 08:50~09:00 칸은 없다
              (넥스트는 쉬고 KRX 는 동시호가 접수만 — 09:00 칸이 08:50 사진부터 잰다)
    범위      코스피 · 코스닥 주권(nxt_pre 마스터) 중 업종(WICS · company_profile.sectors) 이나 테마(theme_flow 의 theme_member)가 있는 종목
              2026-11-18 잼: 2,4xx 종목 · 사진 한 장에 NX 80번쯤(09:10 부터는 J 까지 두 배) — 하루 900번쯤
    묶음      by=sector — WICS 업종 · by=theme — 네이버 작은 테마(묶음 테마 theme_flow.LUMP 는 뺀다 · 수급 「테마」 와 같게)
              한 종목이 여러 테마면 각 테마에 다 센다
    pct       칸 끝 사진의 값으로 그 묶음 평균 등락률(%) — 전날 KRX 정규장 종가(nxt_board 15:41 저장) 대비
              08:50 까지는 넥스트 현재가(그날 넥스트 체결이 있는 종목만) · 09:10 부터는 KRX 현재가(체결이 있는 종목만)
    굳힘      09:31 뒤 한 번 — 그날 판(업종 · 테마)을 sector_flow_day 에 남긴다(지우지 않는다). 사진(sector_snap)은 KEEP_SNAP_DAYS 날만
    되채움    사진이 없는 날(이 서버 전 · 내려가 있던 날)은 개발 DB 5분봉으로 셈해 남긴다(src 5m · 봉 있는 종목만) — 서버가 뜰 때
              5분봉이 있는 지난 평일 전부 · 그날 사진이 없으면 09:31 굳힘 때. 재권님 「지난날들도 다 되채워야돼」(11-18 17:0x)
              메인(8764)은 개발 DB 를 읽기 전용으로 읽어(launchd 의 KJC_DB_PATH) 따로 옮기지 않아도 같은 판을 본다
    없음      사진이 빠진 칸(서버가 내려가 있었음 · 받기 실패) · 앞날이 없으면 null — 0 으로 꾸미지 않는다.
              첫날(2026-11-19)은 prev 가 다 null 이다
    주소      GET /api/kis/sector-flow?by=sector|theme[&day=YYYYMMDD] — 모양은 board() 주석

8765 만 받는다(kis_proxy 가 is_sender 로 부른다) · 읽기는 어느 서버든 자기 DB 로. 알림은 없다(화면만).
"""

import json
import threading
import time
from datetime import datetime, timedelta, timezone

import company_profile
import naver
import nxt_board
import nxt_pre
import theme_flow
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))

SLOTS = ("0800", "0810", "0820", "0830", "0840", "0900", "0910", "0920")
SNAPS = ("0810", "0820", "0830", "0840", "0850", "0910", "0920", "0930")   # 사진 이름(찍는 경계)
SNAP_FIRE = {"0850": "0851"}           # 이름과 찍는 때가 다른 사진
SLOT_FROM = {"0800": None, "0810": "0810", "0820": "0820", "0830": "0830", "0840": "0840",
             "0900": "0850", "0910": "0910", "0920": "0920"}
SLOT_TO = {"0800": "0810", "0810": "0820", "0820": "0830", "0830": "0840", "0840": "0850",
           "0900": "0910", "0910": "0920", "0920": "0930"}
J_FROM = "0910"                        # 이 사진부터 KRX 를 함께 받는다
SNAP_LATE_MIN = 5                      # 경계에서 몇 분 안이면 늦게라도 찍는다(서버가 막 떴을 때) — 그 뒤는 빈 사진
FREEZE_AT = (9, 31)
REFRESH_MS = 60000                     # 화면이 다시 받을 주기 — 사진은 10분마다라 1분이면 넉넉하다
EOK = 100000000
KEEP_SNAP_DAYS = 5
FILL_MIN_CODES = 300                   # 5분봉 되채움 — 그날 08:00~09:25 봉이 있는 종목이 이보다 적으면 안 채운다(봉을 덜 받은 날)
LIVE_TTL = 30
TICK = 15
BYS = ("sector", "theme")

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS sector_snap (
        day TEXT NOT NULL, at TEXT NOT NULL, code TEXT NOT NULL,
        nx_val INTEGER, nx_vol INTEGER, nx_price INTEGER, j_val INTEGER, j_vol INTEGER, j_price INTEGER, j_pct REAL,
        PRIMARY KEY (day, at, code))""",
    """CREATE TABLE IF NOT EXISTS sector_flow_day (
        day TEXT NOT NULL, by TEXT NOT NULL, body TEXT, saved_at TEXT, src TEXT, codes INTEGER, PRIMARY KEY (day, by))""",
)

_status = {"lastSnap": None, "lastSnapAt": None, "lastSnapSec": None, "lastCodes": None, "frozenDay": None,
           "frozenAt": None, "error": None}
_cache = {}


def _now():
    return datetime.now(KST)


def _init(proxy):
    with proxy._db_lock, proxy.db_conn() as conn:
        for q in _SCHEMA:
            conn.execute(q)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(sector_flow_day)")}
        for c, t in (("src", "TEXT"), ("codes", "INTEGER")):
            if c not in cols:
                conn.execute("ALTER TABLE sector_flow_day ADD COLUMN %s %s" % (c, t))


def _hm(s):
    return int(s[:2]) * 60 + int(s[2:])


def _members(proxy):
    """{code: [테마 no]} · {no: 이름} — 묶음 테마는 뺀다."""
    try:
        info = {int(t["no"]): t["name"] for t in naver.groups_all("theme")["rows"]
                if not any(k in t["name"] for k in theme_flow.LUMP)}
    except Exception:
        info = {}
    mem = {}
    try:
        with proxy._db_lock, proxy.db_conn() as conn:
            for no, c in conn.execute("SELECT no, code FROM theme_member"):
                if int(no) in info:
                    mem.setdefault(c, []).append(int(no))
    except Exception:
        pass
    return mem, info


def universe(proxy):
    """사진 찍을 종목 — 마스터 주권 중 업종이나 테마가 있는 것."""
    master = nxt_pre.master_codes()
    wics = company_profile.sectors()
    mem, _info = _members(proxy)
    return sorted(c for c in master if c in wics or c in mem)


def snap(proxy, day, at):
    """사진 한 장 — 누적 거래대금 · 거래량 · 현재가. 적은 종목 수(NX 거래대금 합이 0 이고 J 도 없으면 휴장으로 보고 안 적는다)."""
    _init(proxy)
    t0 = time.time()
    cfg = proxy.load_secrets()
    codes = universe(proxy)
    nx = nxt_board._multi(proxy, cfg, codes, "NX")
    jx = nxt_board._multi(proxy, cfg, codes, "J") if at >= J_FROM else {}
    if not any((r.get("value") or 0) > 0 for r in nx.values()) and not any((r.get("value") or 0) > 0 for r in jx.values()):
        _status.update(lastSnap=at, lastSnapAt=_now().isoformat(timespec="seconds"), lastCodes=0,
                       error="거래대금 합이 0 — 휴장이거나 아직 거래 전")
        return 0
    rows = []
    for c in codes:
        n, j = nx.get(c), jx.get(c)
        if not n and not j:
            continue
        rows.append((day, at, c,
                     (n or {}).get("value"), (n or {}).get("vol"), (n or {}).get("price"),
                     (j or {}).get("value"), (j or {}).get("vol"), (j or {}).get("price"), (j or {}).get("pct")))
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.executemany("INSERT OR REPLACE INTO sector_snap (day, at, code, nx_val, nx_vol, nx_price, j_val, j_vol, j_price, j_pct) "
                         "VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
        days = [r[0] for r in conn.execute("SELECT DISTINCT day FROM sector_snap ORDER BY day DESC")]
        for d in days[KEEP_SNAP_DAYS:]:
            conn.execute("DELETE FROM sector_snap WHERE day = ?", (d,))
    _status.update(lastSnap=at, lastSnapAt=_now().isoformat(timespec="seconds"), lastSnapSec=round(time.time() - t0, 1),
                   lastCodes=len(rows), error=None)
    _cache.clear()
    return len(rows)


def _snaps(conn, day):
    out = {}
    for r in conn.execute("SELECT at, code, nx_val, nx_vol, nx_price, j_val, j_vol, j_price, j_pct FROM sector_snap WHERE day = ?", (day,)):
        out.setdefault(r[0], {})[r[1]] = {"nxVal": r[2], "nxVol": r[3], "nxPrice": r[4], "jVal": r[5], "jVol": r[6],
                                          "jPrice": r[7], "jPct": r[8]}
    return out


def _total(at, r):
    """그 사진의 그 종목 누적 거래대금(원) — J 는 J_FROM 사진부터 더한다. 못 받은 칸이 있으면 None."""
    if r is None:
        return None
    nx = r.get("nxVal") or 0                      # 넥스트 거래가 없는 종목은 0 이 맞다(멀티 시세가 줄은 줬다)
    if at < J_FROM:
        return nx
    if r.get("jVal") is None:
        return None
    return nx + r["jVal"]


def _pct(at, r, close):
    if r is None:
        return None
    if at < J_FROM:
        if not (r.get("nxVol") or 0) or not r.get("nxPrice") or not close:
            return None
        return (r["nxPrice"] / close - 1) * 100
    if not (r.get("jVol") or 0) or not r.get("jPrice"):
        return None
    if close:
        return (r["jPrice"] / close - 1) * 100
    return r.get("jPct")


def _prev_close(conn, day):
    try:
        r = conn.execute("SELECT MAX(day) FROM nxt_board WHERE day < ? AND close IS NOT NULL", (day,)).fetchone()
        if not r or not r[0]:
            return {}
        return {c: v for c, v in conn.execute("SELECT code, close FROM nxt_board WHERE day = ? AND close IS NOT NULL", (r[0],))}
    except Exception:
        return {}


def _groups(proxy, by, codes):
    """{묶음 이름: [code]}"""
    out = {}
    if by == "sector":
        wics = company_profile.sectors()
        for c in codes:
            if wics.get(c):
                out.setdefault(wics[c], []).append(c)
    else:
        mem, info = _members(proxy)
        for c in codes:
            for no in mem.get(c, []):
                out.setdefault(info[no], []).append(c)
    return out


def build(proxy, day, by):
    """그날 사진으로 묶음별 칸 값을 셈 — {name: {n, amt{slot}, pct{slot}}} · 사진이 하나도 없으면 None."""
    with proxy._db_lock, proxy.db_conn() as conn:
        try:
            sn = _snaps(conn, day)
        except Exception:
            return None
        close = _prev_close(conn, day)
    if not sn:
        return None
    codes = sorted({c for s in sn.values() for c in s})
    out = {}
    for name, cs in _groups(proxy, by, codes).items():
        amt, pct, gotm = {}, {}, {}
        for slot in SLOTS:
            fa, ta = SLOT_FROM[slot], SLOT_TO[slot]
            if ta not in sn or (fa is not None and fa not in sn):
                amt[slot] = None                  # 사진이 빠졌다 — 못 잼
                gotm[slot] = None
            else:
                tot, got = 0, 0
                for c in cs:
                    b = _total(ta, sn[ta].get(c))
                    a = 0 if fa is None else _total(fa, sn[fa].get(c))
                    if b is None or a is None or b < a:
                        continue                  # 그 종목만 못 가름 — 묶음 합에서 뺀다
                    tot += b - a
                    got += 1
                amt[slot] = round(tot / EOK, 2) if got else None
                gotm[slot] = got                  # 그 칸을 셈한 종목 수 — n 보다 작으면 못 받은 종목이 있다(qa)
            if ta in sn:
                ps = [p for p in (_pct(ta, sn[ta].get(c), close.get(c)) for c in cs) if p is not None]
                pct[slot] = round(sum(ps) / len(ps), 2) if ps else None
            else:
                pct[slot] = None
        out[name] = {"n": len(cs), "amt": amt, "got": gotm, "pct": pct}
    return out


def _frozen(conn, day, by):
    try:
        r = conn.execute("SELECT body FROM sector_flow_day WHERE day = ? AND by = ?", (day, by)).fetchone()
    except Exception:
        return None
    return json.loads(r[0]) if r and r[0] else None


def _rows_of(proxy, day, by):
    """굳힌 판이 있으면 그것 · 없으면 사진으로 셈(LIVE_TTL 캐시)."""
    with proxy._db_lock, proxy.db_conn() as conn:
        f = _frozen(conn, day, by)
    if f is not None:
        return f
    key = (day, by)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < LIVE_TTL:
        return hit[1]
    v = build(proxy, day, by)
    _cache[key] = (time.time(), v)
    return v


def _store(proxy, day, by, v, src, codes):
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO sector_flow_day (day, by, body, saved_at, src, codes) VALUES (?,?,?,?,?,?)",
                     (day, by, json.dumps(v, ensure_ascii=False), _now().isoformat(timespec="seconds"), src, codes))


def freeze(proxy, day):
    """그날 판(업종 · 테마)을 남긴다 — 사진이 있으면 사진으로(src snap) · 없으면 5분봉으로(src 5m). 남긴 묶음 수 합.
    굳힌 판은 지우지 않는다(재권님 「서버 내리거나 올린다고 날라가면 안되고 저장되야하는 정보」 11-18)."""
    _init(proxy)
    n = 0
    with proxy._db_lock, proxy.db_conn() as conn:
        try:
            codes = conn.execute("SELECT COUNT(DISTINCT code) FROM sector_snap WHERE day = ?", (day,)).fetchone()[0]
        except Exception:
            codes = 0
    for by in BYS:
        v = build(proxy, day, by)
        if v is None:
            continue
        _store(proxy, day, by, v, "snap", codes)
        n += len(v)
    if not n:
        n = backfill(proxy, day)
    _cache.clear()
    return n


# ── 5분봉 되채움 — 사진이 없는 날(이 서버가 생기기 전 · 내려가 있던 날) ─────────────

def build_5m(proxy, day, by):
    """개발 DB 5분봉(candles 5m · 통합)으로 그날 판을 셈 — (판, 봉이 있는 종목 수) · 종목이 FILL_MIN_CODES 보다 적으면 (None, 수).
    칸 값 = 그 10분 안에 시작한 5분봉 종가 × 거래량 합(어림 · 시황분석1 시안 셈) · 08:50~09:00 봉은 안 씀.
    pct = 칸 끝 전 마지막 봉 종가 ÷ 전날 정규장 종가 − 1 — 08:50 전 칸은 프리장 봉이 있는 종목 · 09:00 뒤 칸은 09:00 뒤 봉이 있는 종목만."""
    lo, hi = day + "0800", day + "0925"
    with proxy._db_lock, proxy.db_conn() as conn:
        bars = {}
        for c, ts, cl, vol in conn.execute("SELECT code, ts, close, volume FROM candles WHERE period = '5m' AND ts >= ? AND ts <= ?",
                                           (lo, hi)):
            bars.setdefault(c, []).append((ts[8:12], cl, vol))
        close = _prev_close(conn, day)
        if len(bars) >= FILL_MIN_CODES:
            for c in bars:
                if c in close:
                    continue
                r = conn.execute("SELECT close FROM candles WHERE code = ? AND period = 'D' AND ts < ? ORDER BY ts DESC LIMIT 1",
                                 (c, day)).fetchone()
                if r and r[0]:
                    close[c] = r[0]
    if len(bars) < FILL_MIN_CODES:
        return None, len(bars)
    out = {}
    for name, cs in _groups(proxy, by, sorted(bars)).items():
        amt, gotm, pct = {}, {}, {}
        for slot in SLOTS:
            s0, s1 = _hm(slot), _hm(SLOT_TO[slot])
            tot = 0
            for c in cs:
                for t, cl, vol in bars[c]:
                    if s0 <= _hm(t) < s1 and cl and vol:
                        tot += cl * vol
            amt[slot] = round(tot / EOK, 2)
            gotm[slot] = None                     # 5분봉은 거래가 없으면 봉이 없어 「못 받음」 과 「거래 없음」 을 못 가른다 — 셈한 수를 안 낸다(개념정의 덧)
            start = 9 * 60 if s1 > 9 * 60 else 8 * 60
            ps = []
            for c in cs:
                last = [cl for t, cl, vol in sorted(bars[c]) if start <= _hm(t) < s1 and cl]
                if last and close.get(c):
                    ps.append((last[-1] / close[c] - 1) * 100)
            pct[slot] = round(sum(ps) / len(ps), 2) if ps else None
        out[name] = {"n": len(cs), "amt": amt, "got": gotm, "pct": pct}
    return out, len(bars)


def backfill(proxy, day):
    """사진도 굳힌 판도 없는 날을 5분봉으로 채워 남긴다(src 5m). 남긴 묶음 수 합 — 봉이 모자라면 0."""
    _init(proxy)
    n = 0
    for by in BYS:
        v, codes = build_5m(proxy, day, by)
        if v is None:
            continue
        _store(proxy, day, by, v, "5m", codes)
        n += len(v)
    _cache.clear()
    return n


def backfill_missing(proxy):
    """5분봉이 있는 지난 평일 중 굳힌 판이 없는 날을 다 채운다 — [(day, 묶음 수)]. 오늘은 사진 쪽이 굳힌다(09:31)."""
    _init(proxy)
    today = _now().strftime("%Y%m%d")
    with proxy._db_lock, proxy.db_conn() as conn:
        have = {r[0] for r in conn.execute("SELECT DISTINCT day FROM sector_flow_day")}
        ds = [r[0] for r in conn.execute("SELECT DISTINCT substr(ts, 1, 8) FROM candles WHERE period = '5m' AND substr(ts, 9, 4) = '0800'")]
    done = []
    for d in sorted(ds):
        if d in have or d >= today or datetime.strptime(d, "%Y%m%d").weekday() >= 5:
            continue
        done.append((d, backfill(proxy, d)))
    return done


def _days(conn):
    ds = set()
    for q in ("SELECT DISTINCT day FROM sector_flow_day", "SELECT DISTINCT day FROM sector_snap"):
        try:
            ds.update(r[0] for r in conn.execute(q))
        except Exception:
            pass
    return sorted(ds, reverse=True)


def _phase(now):
    hm = now.hour * 60 + now.minute
    if now.weekday() >= 5 or hm >= FREEZE_AT[0] * 60 + FREEZE_AT[1] - 1:
        return "closed"
    return "pre" if hm < 9 * 60 else "open"


def board(proxy, by="sector", day=None):
    """data {day, prev(앞 거래일 · 없으면 null), by, slots,
             rows: [{name, n, amt{slot: 억원}, got{slot: 그 칸을 셈한 종목 수 · n 보다 작으면 못 받은 종목 있음}, prev{slot: 억원 · 앞날 같은 칸}, pct{slot: % · 칸 끝 묶음 평균 · 전날 정규장 종가 대비}}]}
       meta {asof, phase(pre · open · closed), refreshMs(닫혔으면 null), by, days, status}

    줄은 그날이나 앞날에 거래대금이 있는 묶음 전부(자르지 않는다) · 차례는 그날 합 큰 순(화면이 다시 세운다) · 없는 값은 null."""
    now = _now()
    today = now.strftime("%Y%m%d")
    with proxy._db_lock, proxy.db_conn() as conn:
        days = _days(conn)
    if not day:
        day = today if (now.weekday() < 5 and now.hour >= 8) else (days[0] if days else today)
    prev = next((d for d in days if d < day), None)
    cur = _rows_of(proxy, day, by) or {}
    old = (_rows_of(proxy, prev, by) or {}) if prev else {}
    rows = []
    for name in set(cur) | set(old):
        c, o = cur.get(name) or {}, old.get(name) or {}
        amt = {s: (c.get("amt") or {}).get(s) for s in SLOTS}
        pv = {s: (o.get("amt") or {}).get(s) for s in SLOTS}
        if not any(v for v in amt.values()) and not any(v for v in pv.values()):
            continue
        rows.append({"name": name, "n": c.get("n") if c else o.get("n"), "amt": amt, "prev": pv,
                     "got": {s: (c.get("got") or {}).get(s) for s in SLOTS},
                     "pct": {s: (c.get("pct") or {}).get(s) for s in SLOTS}})
    rows.sort(key=lambda r: (-sum(v for v in r["amt"].values() if v), -sum(v for v in r["prev"].values() if v)))
    ph = _phase(now) if day == today else "closed"
    data = {"day": day, "prev": prev, "by": by, "slots": list(SLOTS), "rows": rows}
    src = {}
    with proxy._db_lock, proxy.db_conn() as conn:
        for d in (day, prev):
            try:
                r = conn.execute("SELECT src, codes FROM sector_flow_day WHERE day = ? AND by = ?", (d, by)).fetchone() if d else None
            except Exception:
                r = None
            src[d] = {"src": r[0], "codes": r[1]} if r else ({"src": "snap", "codes": None} if d == day and cur else None)
    meta = {"asof": _status.get("lastSnapAt") if day == today else None, "phase": ph,
            "refreshMs": REFRESH_MS if ph != "closed" else None, "by": by, "days": days,
            "src": src.get(day), "prevSrc": src.get(prev) if prev else None,
            "srcNote": "snap = 10분마다 누적 거래대금 사진(넥스트+KRX · 종목 2천여) · 5m = 개발 DB 5분봉 종가×거래량 되채움(봉이 있는 종목만 · codes) — 두 셈은 값이 다를 수 있다",
            "amtUnit": "억원", "status": dict(_status)}
    return data, meta


def status():
    return dict(_status)


def start(proxy):
    """보내는 서버가 뜰 때 한 번 — 평일 SNAPS 사진 · 09:31 굳힘."""
    def loop():
        time.sleep(40)
        try:
            got = backfill_missing(proxy)
            if got:
                print("  [섹터수급] 5분봉 되채움 %s" % " · ".join("%s(%s)" % g for g in got), flush=True)
        except Exception as e:
            _status["error"] = "되채움: " + safe_message(e, 120)
            print("  [섹터수급] 5분봉 되채움 실패: %s" % type(e).__name__, flush=True)
        done = set()
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = now.hour * 60 + now.minute
                if now.weekday() < 5:
                    for at in SNAPS:
                        fire = _hm(SNAP_FIRE.get(at, at))
                        if (day, at) not in done and fire <= hm < fire + SNAP_LATE_MIN:
                            done.add((day, at))           # 실패해도 그 사진은 한 번
                            try:
                                n = snap(proxy, day, at)
                                print("  [섹터수급] %s %s 사진 %s종목" % (day, at, n), flush=True)
                            except Exception as e:
                                _status["error"] = safe_message(e, 160)
                                print("  [섹터수급] %s %s 사진 실패: %s" % (day, at, type(e).__name__), flush=True)
                    if hm >= FREEZE_AT[0] * 60 + FREEZE_AT[1] and _status.get("frozenDay") != day:
                        _status["frozenDay"] = day
                        try:
                            n = freeze(proxy, day)
                            _status["frozenAt"] = _now().isoformat(timespec="seconds")
                            if n:
                                print("  [섹터수급] %s 판 굳힘 · 묶음 %s" % (day, n), flush=True)
                        except Exception as e:
                            _status["error"] = safe_message(e, 160)
                            print("  [섹터수급] %s 굳힘 실패: %s" % (day, type(e).__name__), flush=True)
                done = {k for k in done if k[0] == day}
            except Exception as e:
                print("  [섹터수급] 예기치 못한 오류: %s" % type(e).__name__, flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="sector-flow").start()
    return True
