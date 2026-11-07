# -*- coding: utf-8 -*-
"""시장 전체 사건 — 서킷브레이커(주식 매매거래 중단)를 알아차린다 (2026-11-07 · 작업우선순위 배분 ①).

재권님 — 「서킷브레이크 같은 일/ 비슷한 다른 이벤트가 발생했을때 우리쪽 대응이 되어있는지 확인해봐」 → 「응 만들어줘. 해당 이벤트가
발생했을때 가져오는 정보들도 정확히 가져오도록 다 체크해야돼」(작업우선순위 창) → 「서킷 브레이커 같은게 발도하면 알려주는곳 찾아봐」 →
안 「우리 지수 셈으로 먼저 「서킷(추정)」 · KIND 거래소 공시가 오면 「확인됨」」 에 「응 그래 다른이벤트들도 대응해야해」(개발2 창).

── 왜 우리가 셈하나 ──

    KIS 에는 「서킷 발동」 을 알려 주는 값이 없다 — 공식 저장소(open-trading-api)의 장운영정보 실시간(H0STMKO0)은 종목마다
    VI · 거래정지 칸이고 「VI 발동 · 해제 때 온다」 고만 적혀 있다(서킷 때 오는지는 못 쟀다). 선물 현재가의 crbr_aply_mxpr · llam 은
    가격 한도일 뿐 발동 알림이 아니다. 그래서 지수 등락률로 **추정**하고, 거래소 공시(KIND 오늘의공시 RSS)에 서킷 글이 오면 **확인됨**.

── 기준(다올투자증권 안내 · 2026-06 · 10 발동 기사로 확인 · 거래소 업무규정 원문은 못 열어 봄) ──

    1단계  코스피 · 코스닥 지수가 전일 종가보다 8% 넘게 내린 채 1분 → 그 시장 20분 매매 중단 · 그 뒤 10분 단일가
    2단계  15% 넘게 내리고 1단계 발동 지수보다 1% 더 내린 채 1분 → 같은 조치
    3단계  20% 넘게 내리고 2단계 발동 지수보다 1% 더 내린 채 1분 → 그날 장 끝
    단계마다 하루 한 번. 「장 끝나기 40분 전 뒤에는 발동 안 함」 은 안내문이 사이드카에만 적어 서킷에는 안 건다(못 쟀다)

    10-15 실제 발동으로 대 봄 — 코스피 전일 6008.81 → 12:35 5527.12(−8.0%) · 12:40~13:00 5분봉이 같은 값으로 멈춤 · 13:05 재개

── 어떻게 ──

    평일 정규장(SESSION_FROM~SESSION_TO) 에 TICK_SEC 마다 두 지수의 등락률을 본다 — 화면이 받아 둔 지수 캐시가 살아 있으면 그것을,
    아니면 지수 하나 조회(fetch_index · 한 바퀴 KIS 최대 2건). 다음 단계 조건이 처음 맞은 시각부터 HOLD_SEC 이 지나면 발동으로 적는다
    (그 시각 = 조건이 맞기 시작한 때 + 1분). 매매 중단 · 단일가 중에는 다음 단계를 안 본다(지수가 멈춰 있다).
    KIND 는 정규장에 KIND_SEC 마다 오늘의공시 RSS 를 읽어 제목에 서킷 낱말(KIND_WORDS)이 든 글을 모은다 — 정확한 제목 · 올라오는 늦음은
    못 쟀다. 시장 낱말(코스닥 · 유가증권 · 코스피)로 그 시장 사건에 「확인됨」 을 붙이고, 못 가르면 kind 목록에만 둔다.
    우리 셈이 놓쳤는데 KIND 가 먼저 오면 그 시장에 단계 모름(stage None) · 확인됨 사건을 만든다.

── 남기기 · 알림 ──

    사건은 쓰기 되는 서버의 market.db market_event 표에 한 줄씩 — 그 순간 지수 · 등락률 · 시각(발동 날 「가져오는 정보가 맞나」 를 재는 바탕 · 카드 ⑧).
    알림은 보내는 서버(8765)만 · SEND 가 False 면 안 보내고 status 의 preview 에 남긴다 — **켜기는 재권님 지시로**.
    기억은 메모리 — 서버를 다시 켜면 그날 표에서 되살린다.
"""
import json
import re
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
MARKETS = (("0001", "코스피"), ("1001", "코스닥"))
STAGES = ((1, -8.0), (2, -15.0), (3, -20.0))   # 단계 · 전일 종가 대비 %
MORE_DROP = 1.0                                 # 2 · 3단계 — 앞 단계 발동 지수보다 이만큼(%) 더
HOLD_SEC = 60                                   # 조건이 이만큼 이어져야 발동
HALT_MIN, SINGLE_MIN = 20, 10                   # 매매 중단 · 그 뒤 단일가
TICK_SEC = 10
KIND_SEC = 60
SESSION_FROM, SESSION_TO = 9 * 60, 15 * 60 + 30
KIND_RSS = ("https://kind.krx.co.kr/disclosure/rsstodaydistribute.do?method=searchRssTodayDistribute"
            "&repIsuSrtCd=&mktTpCd=0&searchCorpName=&currentPageSize=100")
KIND_WORDS = ("서킷", "Circuit", "매매거래중단", "매매거래 중단")
SEND = False                                    # 켜기는 재권님 지시로

_SCHEMA = """CREATE TABLE IF NOT EXISTS market_event (
    day TEXT NOT NULL, market TEXT NOT NULL, kind TEXT NOT NULL, stage INTEGER, at TEXT NOT NULL,
    value REAL, pct REAL, row TEXT, PRIMARY KEY (day, market, kind, at))"""
_lock = threading.Lock()
_st = {"day": None, "m": {}, "kind": [], "kindAt": None, "kindError": None, "error": None, "preview": [], "sent": 0}


def _now():
    return datetime.now(KST)


def _fresh(day):
    _st.update(day=day, kind=[], kindAt=None, preview=[], sent=0,
               m={name: {"stage": 0, "events": [], "since": None, "value": None, "pct": None, "at": None} for _, name in MARKETS})


def _hm(dt):
    return dt.strftime("%H:%M:%S")


def phase(ev, now):
    """사건 하나가 지금 어느 때인가 — halt 매매 중단 · single 단일가 · closed 그날 끝 · done 지남."""
    if ev.get("stage") == 3:
        return "closed"
    if not ev.get("haltUntil"):
        return "done"
    t = now.strftime("%H:%M:%S")
    if t < ev["haltUntil"]:
        return "halt"
    if t < ev["singleUntil"]:
        return "single"
    return "done"


def _event(stage, at, value, pct):
    t0 = datetime.strptime(at, "%H:%M:%S")
    ev = {"stage": stage, "at": at, "value": value, "pct": pct, "est": True, "confirmed": False, "kind": None}
    if stage in (1, 2):
        ev["haltUntil"] = (t0 + timedelta(minutes=HALT_MIN)).strftime("%H:%M:%S")
        ev["singleUntil"] = (t0 + timedelta(minutes=HALT_MIN + SINGLE_MIN)).strftime("%H:%M:%S")
    return ev


def check(name, value, pct, now):
    """한 시장의 지금 값으로 다음 단계를 본다 — 발동이면 새 사건을 돌려준다(시험이 이 셈을 그대로 부른다)."""
    m = _st["m"][name]
    m.update(value=value, pct=pct, at=_hm(now))
    if value is None or pct is None or m["stage"] >= 3:
        return None
    if m["events"] and phase(m["events"][-1], now) in ("halt", "single"):
        m["since"] = None
        return None
    nxt, thr = STAGES[m["stage"]]
    ok = pct <= thr
    if ok and nxt > 1:
        base = next((e["value"] for e in reversed(m["events"]) if e.get("stage") == nxt - 1 and e.get("value")), None)
        ok = base is None or value <= base * (1 - MORE_DROP / 100)
    if not ok:
        m["since"] = None
        return None
    if m["since"] is None:
        m["since"] = now
        return None
    if (now - m["since"]).total_seconds() < HOLD_SEC:
        return None
    ev = _event(nxt, _hm(m["since"] + timedelta(seconds=HOLD_SEC)), value, pct)
    m["stage"], m["since"] = nxt, None
    m["events"].append(ev)
    return ev


def _index(proxy, cfg, code):
    hit = proxy._index_cache_get("IDX:" + code)
    if hit is None:
        hit = proxy.fetch_index(cfg, code)
    return hit.get("value"), hit.get("changePct")


def _save(proxy, day, name, kind, ev):
    if not proxy.marketdb.writable():
        return
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        conn.execute("INSERT OR REPLACE INTO market_event (day, market, kind, stage, at, value, pct, row) VALUES (?,?,?,?,?,?,?,?)",
                     (day, name, kind, ev.get("stage"), ev["at"], ev.get("value"), ev.get("pct"), json.dumps(ev, ensure_ascii=False)))


def _restore(proxy, day):
    try:
        with proxy.db_conn() as conn:
            rows = conn.execute("SELECT market, row FROM market_event WHERE day = ? ORDER BY at", (day,)).fetchall()
    except Exception:
        return                       # 표가 아직 없음
    for name, row in rows:
        ev = json.loads(row)
        m = _st["m"].get(name)
        if m is None:
            continue
        m["events"].append(ev)
        if ev.get("stage"):
            m["stage"] = max(m["stage"], ev["stage"])


def _text(name, ev):
    if ev.get("stage") == 3:
        act = "그날 장 끝"
    elif ev.get("haltUntil"):
        act = "%s 까지 매매 중단 · %s 까지 단일가" % (ev["haltUntil"][:5], ev["singleUntil"][:5])
    else:
        act = "거래소 공시"
    st = "%d단계" % ev["stage"] if ev.get("stage") else "단계 모름"
    tag = "확인됨" if ev.get("confirmed") else "추정"
    pct = "" if ev.get("pct") is None else " · 지수 %.2f%%" % ev["pct"]
    return "[서킷 %s · %s] %s %s 발동%s — %s" % (st, tag, name, ev["at"][:5], pct, act)


def _alert(proxy, port, name, ev):
    msg = _text(name, ev)
    if not (SEND and proxy.is_sender(port)):
        _st["preview"] = (_st["preview"] + [msg])[-10:]
        return
    import dart
    dart.telegram_send(msg)
    _st["sent"] += 1


def _kind_tick(proxy, port, day):
    req = urllib.request.Request(KIND_RSS, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        xml = r.read().decode("utf-8", "replace")
    _st["kindAt"] = _hm(_now())
    for title in re.findall(r"<item>.*?<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", xml, re.S):
        title = title.strip()
        if not any(w in title for w in KIND_WORDS) or title in _st["kind"]:
            continue
        _st["kind"].append(title)
        name = "코스닥" if "코스닥" in title else ("코스피" if ("유가" in title or "코스피" in title or "KOSPI" in title) else None)
        if name is None:
            continue                 # 시장을 못 가름 — kind 목록에만
        m = _st["m"][name]
        ev = next((e for e in reversed(m["events"]) if not e.get("confirmed")), None)
        if ev is None:               # 우리 셈이 놓침 — 공시로 사건을 만든다
            ev = {"stage": None, "at": _st["kindAt"], "value": m["value"], "pct": m["pct"], "est": False}
            m["events"].append(ev)
            _alert(proxy, port, name, dict(ev, confirmed=True))
        ev.update(confirmed=True, kind=title, kindAt=_st["kindAt"])
        _save(proxy, day, name, "cb", ev)


def tick(proxy, cfg, port, now=None):
    now = now or _now()
    day = now.strftime("%Y%m%d")
    with _lock:
        if _st["day"] != day:
            _fresh(day)
            _restore(proxy, day)
        mins = now.hour * 60 + now.minute
        if now.weekday() >= 5 or not (SESSION_FROM <= mins < SESSION_TO):
            return
        for code, name in MARKETS:
            value, pct = _index(proxy, cfg, code)
            ev = check(name, value, pct, now)
            if ev:
                print("  [시장 사건] %s 서킷 %d단계(추정) %s · 지수 %s (%.2f%%)" % (name, ev["stage"], ev["at"], value, pct), flush=True)
                _save(proxy, day, name, "cb", ev)
                _alert(proxy, port, name, ev)


def _db_events(proxy, day):
    try:
        with proxy.db_conn() as conn:
            rows = conn.execute("SELECT market, row FROM market_event WHERE day = ? ORDER BY at", (day,)).fetchall()
    except Exception:
        return None                  # 표가 아직 없음
    out = {}
    for name, row in rows:
        out.setdefault(name, []).append(json.loads(row))
    return out


def board(proxy, now=None):
    """주소 /api/alerts/market-event 의 data — 사건은 개발 DB 표에서 읽어 **어느 서버든 같은 것**(바퀴는 보내는 서버에서만 돈다).
    지수 · 등락률은 바퀴가 도는 서버의 메모리 값이라 다른 서버에서는 None."""
    now = now or _now()
    day = now.strftime("%Y%m%d")
    db = _db_events(proxy, day) or {}
    with _lock:
        out = {}
        for _, name in MARKETS:
            m = (_st["m"].get(name) if _st["day"] == day else None) or {"stage": 0, "events": []}
            evs = [dict(e, phase=phase(e, now)) for e in (db.get(name) or m["events"])]
            cur = next((e for e in reversed(evs) if e["phase"] in ("halt", "single", "closed")), None)
            out[name] = {"stage": max([e.get("stage") or 0 for e in evs] + [0]), "value": m.get("value"), "pct": m.get("pct"), "at": m.get("at"),
                         "now": cur, "events": evs}
        return {"day": day, "markets": out, "kind": list(_st["kind"]), "kindAt": _st["kindAt"]}


def status():
    return {"send": SEND, "sent": _st["sent"], "preview": list(_st["preview"]), "error": _st["error"],
            "kindError": _st["kindError"], "tickSec": TICK_SEC, "kindSec": KIND_SEC,
            "rule": "1단계 −8%% · 2단계 −15%%(+1단계보다 1%%) · 3단계 −20%%(+2단계보다 1%%) · 1분 이어짐 · 중단 %d분 · 단일가 %d분" % (HALT_MIN, SINGLE_MIN)}


def start(proxy, port):
    """보내는 서버(8765)가 뜰 때 한 번 — 셈 · 남기기 · 알림. 다른 서버는 board 가 DB 표를 읽어 같은 띠를 낸다."""
    def loop():
        time.sleep(20)
        last_kind = 0
        while True:
            t0 = time.time()
            try:
                tick(proxy, proxy.load_secrets(), port)
                _st["error"] = None
            except Exception as e:
                _st["error"] = proxy.safe_message(e, 120)
            now = _now()
            mins = now.hour * 60 + now.minute
            if now.weekday() < 5 and SESSION_FROM <= mins < SESSION_TO and time.time() - last_kind >= KIND_SEC:
                last_kind = time.time()
                try:
                    with _lock:
                        _kind_tick(proxy, port, now.strftime("%Y%m%d"))
                    _st["kindError"] = None
                except Exception as e:
                    _st["kindError"] = proxy.safe_message(e, 120)
            time.sleep(max(1, TICK_SEC - (time.time() - t0)))

    threading.Thread(target=loop, daemon=True, name="market-event").start()
    return True
