# -*- coding: utf-8 -*-
"""종목 기록 — 관심 · 자동 · VI · 급등 · 매수 종목을 날마다 한 표에 쌓는다 (2026-11-06).

재권님 — 「관심종목에 등록된 종목들 데이터 누적해놓으면 좋을거같아. 관심종목에 있는종목이 전날대비 상승비 / 관심종목에 있는 종목들
프리장부터 넥장까지 5분봉 가격변 / 여기에 vi 종목이랑 매수에 있는 동목도 같은 룰로 정리해놓고 싶은데 시안잡아봐」(작업우선순위 경유) →
시안 → 「기록을 어디에다가 쌓아놔야 하는데 투자전략에다가 하위로 텝 만들어서 넣어노면 좋을거같은데」(개발2 창). 화면은 Insight 「투자 전략」
하위 탭(시황분석 레인) · 쌓기와 주소는 여기(주식 레인).

    어디서 온 종목   관심 — 관심 목록 문서(docstore watchlist)의 items 중 자동이 아닌 것 · 자동 — 그 문서 auto 칸 + 그날 auto_watch_pick ·
                    VI · 급등 — 그날 intraday_alerts 목록(실시간 순위 「VI-급등」 칩) · 매수 — 그날 「매수」 칩에 한 번이라도 잡힌 종목(flow_rank.joint_codes)
                    한 종목이 여럿에 들면 src 에 다 적는다
    값              전일 종가 — 그날 앞 가장 최근 일봉(차트 일봉 · 통합) 종가 · 마지막 — 그날 마지막 5분봉 종가
                    pct 전일비(전일 종가 → 마지막) · pre 프리장(전일 종가 → 08:55 봉) · reg 정규장(프리장 끝 → 15:30 봉) ·
                    aft 애프터(정규장 끝 → 마지막) — %. 그 구간 봉이 없으면 None(0 이 아니다)
    5분봉           이미 쌓는 candles 5m(08:00~20:00 · 통합)을 그대로 읽는다 — 따로 안 담는다. SAVE_AT 에 그날 5분봉이 없는 종목만
                    받아 채운다(_get_chart_one · 한 종목 하루치 = 30분 칸마다 KIS 한 번)
    저장            market.db 의 watch_log(날 · 종목 · 줄 JSON) — 평일 SAVE_AT 한 번 · 쓰기 되는 서버(8765)만
    주소            GET /api/watch-log?day=YYYYMMDD — 저장한 날은 저장한 줄 · 오늘(아직 안 남김)은 지금 DB 로 셈(KIS 안 부름) ·
                    line(그날 5분봉 [시각, 종가])은 부를 때 candles 에서 읽는다 · days 는 저장한 날 목록
"""
import json
import threading
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
SAVE_AT = (20, 5)                  # 넥스트레이드 애프터(20:00) 끝 · 마지막 5분봉이 닫힌 뒤
TICK = 60
DAYS_MAX = 60                      # 날 고르기 목록에 내는 날 수
PRE_END, REG_END = "0900", "1535"  # 프리장 08:00~08:55 봉 · 정규장 09:00~15:30 봉(15:30 봉까지) · 그 뒤 애프터

_SCHEMA = """CREATE TABLE IF NOT EXISTS watch_log (
    day TEXT NOT NULL, code TEXT NOT NULL, row TEXT NOT NULL, saved_at TEXT, PRIMARY KEY (day, code))"""
_status = {"saved": None, "error": None, "filled": None}
_lock = threading.Lock()


def _now():
    return datetime.now(KST)


def sources(proxy, day):
    """그날 종목 → (이름, 어디서 목록). day — YYYYMMDD."""
    out = {}

    def put(code, name, src):
        if not code or not str(code).isdigit():
            return                   # ETN(Q…) · 선물형 ETF(…X…) 같은 코드는 뺀다 — 일봉 · 5분봉을 안 쌓는다
        nm, ss = out.setdefault(code, [None, []])
        if src not in ss:
            ss.append(src)
        if name and not nm:
            out[code][0] = name

    try:
        import docstore
        doc = docstore.read_doc("watchlist") or {}
    except Exception:
        doc = {}
    auto = set((doc.get("auto") or {}).keys()) if isinstance(doc.get("auto"), dict) else set(doc.get("auto") or [])
    for it in doc.get("items") or []:
        if isinstance(it, dict):
            put(it.get("code"), it.get("name"), "자동" if it.get("code") in auto else "관심")
    try:
        with proxy.db_conn() as conn:
            for code, name in conn.execute("SELECT code, name FROM auto_watch_pick WHERE day = ?", (day,)):
                put(code, name, "자동")
    except Exception:
        pass
    try:
        import intraday_alerts
        t = intraday_alerts.today()
        if t.get("day") == day:
            for it in t.get("items") or []:
                put(it.get("code"), it.get("name"), "VI" if it.get("kind") == "vi" else "급등")
    except Exception:
        pass
    try:
        import flow_rank
        if day == _now().strftime("%Y%m%d"):
            for code in flow_rank.joint_codes():
                put(code, (flow_rank._jt["acc"].get(code) or {}).get("name"), "매수")
    except Exception:
        pass
    return out


def _bars(proxy, code, day):
    with proxy.db_conn() as conn:
        return conn.execute("SELECT ts, close FROM candles WHERE code = ? AND period = '5m' AND ts LIKE ? ORDER BY ts",
                            (code, day + "%")).fetchall()


def _prev_close(proxy, code, day):
    with proxy.db_conn() as conn:
        r = conn.execute("SELECT close FROM candles WHERE code = ? AND period = 'D' AND ts < ? ORDER BY ts DESC LIMIT 1",
                         (code, day)).fetchone()
    return r[0] if r else None


def _pct(a, b):
    return None if not a or b is None else round((b / a - 1) * 100, 2)


def row(proxy, code, name, src, day):
    """한 종목 그날 줄 — 봉이 없으면 값은 None."""
    bars = _bars(proxy, code, day)
    at = lambda t0, t1: [c for ts, c in bars if t0 <= ts[8:] < t1]
    pre, reg, aft = at("0800", PRE_END), at(PRE_END, REG_END), at(REG_END, "2400")
    prev = _prev_close(proxy, code, day)
    last = bars[-1][1] if bars else None
    return {"code": code, "name": name or code, "src": src, "prev": prev, "last": last,
            "pct": _pct(prev, last), "pre": _pct(prev, pre[-1]) if pre else None,
            "reg": _pct(pre[-1] if pre else prev, reg[-1]) if reg else None,
            "aft": _pct(reg[-1], aft[-1]) if reg and aft else None, "n": len(bars)}


def _order(rows):
    # 여럿에 든 종목 먼저 · 그 안은 전일비 큰 순(값 없음은 맨 뒤)
    return sorted(rows, key=lambda r: (-len(r["src"]), r["pct"] is None, -(r["pct"] or 0)))


def days(proxy):
    try:
        with proxy.db_conn() as conn:
            return [d for (d,) in conn.execute("SELECT DISTINCT day FROM watch_log ORDER BY day DESC LIMIT ?", (DAYS_MAX,))]
    except Exception:
        return []


def board(proxy, day=None):
    """주소 /api/watch-log 의 data — 저장한 날은 저장한 줄 · 아니면 지금 DB 로 셈. line 은 늘 candles 에서."""
    day = day or _now().strftime("%Y%m%d")
    saved = []
    try:
        with proxy.db_conn() as conn:
            saved = [json.loads(r) for (r,) in conn.execute("SELECT row FROM watch_log WHERE day = ?", (day,))]
    except Exception:
        saved = []
    rows = saved or [row(proxy, c, nm, ss, day) for c, (nm, ss) in sources(proxy, day).items()]
    for r in rows:
        r["line"] = [[ts[8:12], c] for ts, c in _bars(proxy, r["code"], day)]
    rows = _order(rows)
    cnt = {}
    for r in rows:
        for s in r["src"]:
            cnt[s] = cnt.get(s, 0) + 1
    return {"day": day, "saved": bool(saved), "days": days(proxy), "counts": cnt, "rows": rows}


def save(proxy, cfg, day):
    """그날 종목 줄을 남긴다 — 5분봉이 없는 종목은 먼저 받아 채운다(쓰기 되는 서버만)."""
    src = sources(proxy, day)
    filled = 0
    for code in src:
        if not _bars(proxy, code, day):
            try:
                proxy._get_chart_one(cfg, code, "5m", 200)
                filled += 1
            except Exception:
                pass
        if _prev_close(proxy, code, day) is None:
            try:
                proxy._get_chart_one(cfg, code, "D", 5)
            except Exception:
                pass
    rows = [row(proxy, c, nm, ss, day) for c, (nm, ss) in src.items()]
    at = _now().strftime("%H:%M:%S")
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        conn.executemany("INSERT OR REPLACE INTO watch_log (day, code, row, saved_at) VALUES (?,?,?,?)",
                         [(day, r["code"], json.dumps(r, ensure_ascii=False), at) for r in rows])
    return len(rows), filled


def status():
    return dict(_status, saveAt="%02d:%02d" % SAVE_AT)


def start(proxy):
    """보내는 서버가 뜰 때 한 번 — 평일 SAVE_AT 뒤 그날 줄을 남긴다."""
    if not proxy.marketdb.writable():
        return False

    def loop():
        time.sleep(90)
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                if now.weekday() < 5 and (now.hour, now.minute) >= SAVE_AT and _status.get("saved") != day:
                    n, filled = save(proxy, proxy.load_secrets(), day)
                    _status.update(saved=day, filled=filled, error=None)
                    print("  [종목 기록] %s %d종목 남김 · 5분봉 받아 채움 %d" % (day, n, filled), flush=True)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [종목 기록] 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="watch-log").start()
    return True
