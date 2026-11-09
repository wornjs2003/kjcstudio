# -*- coding: utf-8 -*-
"""시간대별 거래량 · 전일비 — 실시간 순위 모달 「전일비」 칸 (2026-11-05).

재권님 — 「실시간 순위 모달에 거래량과 전일거래비 도 넣어줘」(작업우선순위 경유) → 다른 곳은 어떻게 하나 찾아봄 →
「넥장은 넥장 장중은 장중으로 장외는 장외?」 → 「프리장은 프리장끼리」 → 안 「응 그렇게 해줘」(개발2 창).

    왜 쌓나     KIS 는 하루 누적 거래량 한 덩어리만 준다 — 프리장 · 정규장 · 애프터를 가르는 칸이 없고, 어제 시간대별 값도 안 준다.
                그래서 시간대가 끝나는 때 순위 종목의 누적 거래량(통합 · 거래소 + 넥스트레이드)을 저장해 두고 그 차이로 가른다
    언제        평일 BOUNDS 의 세 시각(프리장 끝 · 정규장 끝 · 애프터 끝) — 그 시각부터 SNAP_WINDOW 분 안에 한 번
    무엇을      순위 목록(dart.universe_rows) 국내 종목 · 멀티 시세(FHKST11300006 · 시장 구분 UN)의 acml_vol · 30종목씩 묶어 7건쯤
    저장        market.db `vol_snap`(날 · 종목 · 경계 · 누적 거래량)
    셈          시간대 거래량 = 그 시간대 끝 누적 − 앞 시간대 끝 누적(프리장은 0 부터)
                지금 전일비 = 오늘 지금 시간대 거래량(지금 누적 − 오늘 앞 경계) ÷ 어제(저장이 있는 가장 최근 날) 같은 시간대 전체 × 100
    없음        어제 저장이 없거나 오늘 앞 경계를 못 저장했으면 그 종목은 None(0 아님) — 화면은 「—」
    주소        GET /api/kis/vol-ratio?codes=a,b,… — 지금 누적은 CACHE_TTL 동안 들고 있다

8765 만 저장한다(`kis_proxy` 가 `is_sender` 로 부른다) · 다른 서버는 같은 DB 를 읽어(세션 서버는 메인 DB 를 읽기 전용) 같은 값을 낸다.
"""

import threading
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

# 시간대 — (이름, 화면 이름, 시작, 끝 경계). 끝 경계 시각에 그날 누적을 저장한다
BOUNDS = (("pre", "프리장", "0800", "0859"), ("reg", "정규장", "0900", "1530"), ("after", "애프터", "1530", "2000"))
SNAP_WINDOW = 3                    # 경계 시각부터 몇 분 안에 저장하나 — 서버가 그 사이 바빠도 놓치지 않게
TICK = 20                          # 바퀴 (초)
CACHE_TTL = 60                     # 지금 누적을 들고 있는 시간 — 화면이 다시 묻는 주기도 이 값(서버 값)
CHUNK = 30                         # 멀티 시세 한 번에 묻는 종목 수(KIS 상한)
MULTI = "/uapi/domestic-stock/v1/quotations/intstock-multprice"

_SCHEMA = """CREATE TABLE IF NOT EXISTS vol_snap (
    day TEXT NOT NULL, code TEXT NOT NULL, bound TEXT NOT NULL, vol INTEGER, saved_at TEXT,
    PRIMARY KEY (day, code, bound))"""

_now_cache = {}                    # code → (받은 때, 누적 거래량)
_status = {"running": False, "last": {}, "error": None}


def _now():
    return datetime.now(KST)


def _i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def session_of(now=None):
    """지금 시간대 (이름, 화면 이름) — 평일 08:00~20:00 밖이면 (None, None)."""
    now = now or _now()
    hm = now.strftime("%H%M")
    if now.weekday() >= 5:
        return None, None
    for name, label, start, end in BOUNDS:
        if start <= hm < end:
            return name, label
    return None, None


def fetch_un_volumes(proxy, cfg, codes):
    """종목들의 통합 누적 거래량 {code: vol}. 못 받은 종목은 빠진다."""
    out = {}
    for i in range(0, len(codes), CHUNK):
        part = codes[i:i + CHUNK]
        params = {}
        for n, c in enumerate(part, 1):
            params["FID_COND_MRKT_DIV_CODE_%d" % n] = "UN"
            params["FID_INPUT_ISCD_%d" % n] = c
        try:
            data = proxy.kis_get(cfg, MULTI, params, "FHKST11300006") or {}
        except RuntimeError:
            continue
        for r in data.get("output") or []:
            c = (r.get("inter_shrn_iscd") or "").strip()
            v = _i(r.get("acml_vol"))
            if c and v is not None:
                out[c] = v
    return out


def _universe():
    import dart
    return [r["stock_code"] for r in dart.universe_rows(None)
            if (r["stock_code"] or "").isdigit() and len(r["stock_code"]) == 6]   # sqlite3.Row — .get 없음(11-09 qa · 11-05 부터 여기서 멈췄다)


def snap(proxy, cfg, day, bound):
    vols = fetch_un_volumes(proxy, cfg, _universe())
    if not vols:
        return 0
    at = _now().strftime("%H:%M:%S")
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        conn.executemany("INSERT OR REPLACE INTO vol_snap (day, code, bound, vol, saved_at) VALUES (?,?,?,?,?)",
                         [(day, c, bound, v, at) for c, v in vols.items()])
    return len(vols)


def start(proxy):
    """보내는 서버가 뜰 때 한 번 — 경계 시각마다 저장하는 바퀴."""
    def loop():
        time.sleep(30)
        while True:
            try:
                now = _now()
                day, hm = now.strftime("%Y%m%d"), now.strftime("%H%M")
                if now.weekday() < 5:
                    for name, _label, _start, end in BOUNDS:
                        e = datetime.strptime(day + end, "%Y%m%d%H%M").replace(tzinfo=KST)
                        if e <= now < e + timedelta(minutes=SNAP_WINDOW) and _status["last"].get(name) != day:
                            n = snap(proxy, proxy.load_secrets(), day, name)
                            if n:
                                _status["last"][name] = day
                                print("  [시간대 거래량] %s %s · %d종목 저장" % (day, name, n), flush=True)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [시간대 거래량] 멈춤 (%s)" % type(e).__name__, flush=True)
            time.sleep(TICK)

    _status["running"] = True
    threading.Thread(target=loop, daemon=True, name="session-volume").start()
    return True


def _load(proxy, codes, today):
    """{(day, code, bound): vol} — 오늘과, 오늘 앞에 저장이 있는 가장 최근 날 하나. (그 날, 표)."""
    marks = ",".join("?" * len(codes))
    try:
        with proxy.db_conn() as conn:
            prev = conn.execute("SELECT MAX(day) FROM vol_snap WHERE day < ?", (today,)).fetchone()
            prev = prev[0] if prev else None
            days = [d for d in (today, prev) if d]
            rows = conn.execute("SELECT day, code, bound, vol FROM vol_snap WHERE day IN (%s) AND code IN (%s)"
                                % (",".join("?" * len(days)), marks), days + list(codes)).fetchall()
    except Exception:              # 표가 아직 없다(저장 전) · 읽기 전용 — 「없음」 으로 낸다
        return None, {}
    return prev, {(d, c, b): v for d, c, b, v in rows}


def ratio(proxy, cfg, codes):
    """(지금 시간대 이름, 화면 이름, 어제 날, {code: 전일비 % 또는 None})."""
    now = _now()
    name, label = session_of(now)
    if not name or not codes:
        return name, label, None, {}
    today = now.strftime("%Y%m%d")
    names = [b[0] for b in BOUNDS]
    before = names[names.index(name) - 1] if names.index(name) else None
    prev_day, tab = _load(proxy, codes, today)
    need = [c for c in codes if not (_now_cache.get(c) and time.time() - _now_cache[c][0] < CACHE_TTL)]
    if need:
        got = fetch_un_volumes(proxy, cfg, need)
        t = time.time()
        for c, v in got.items():
            _now_cache[c] = (t, v)
    out = {}
    for c in codes:
        cur = (_now_cache.get(c) or (0, None))[1]
        base = 0 if before is None else tab.get((today, c, before))
        y_end = tab.get((prev_day, c, name)) if prev_day else None
        y_base = 0 if before is None else (tab.get((prev_day, c, before)) if prev_day else None)
        if cur is None or base is None or y_end is None or y_base is None or y_end - y_base <= 0:
            out[c] = None
            continue
        out[c] = round((cur - base) / (y_end - y_base) * 100, 1)
    return name, label, prev_day, out
