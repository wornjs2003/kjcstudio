# -*- coding: utf-8 -*-
"""시장 전체 사건 — 서킷브레이커(주식 매매거래 중단) · 사이드카(프로그램 호가 정지)를 알아차린다 (2026-11-07 · 작업우선순위 배분 ①).

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

    그날 정규장(market_hours.in_regular — 휴장일 · 수능날 같은 바뀐 시각을 따른다)에 TICK_SEC 마다 두 지수의 등락률을 본다 — 화면이 받아 둔 지수 캐시가 살아 있으면 그것을,
    아니면 지수 하나 조회(fetch_index · 한 바퀴 KIS 최대 2건). 다음 단계 조건이 처음 맞은 시각부터 HOLD_SEC 이 지나면 발동으로 적는다
    (그 시각 = 조건이 맞기 시작한 때 + 1분). 매매 중단 · 단일가 중에는 다음 단계를 안 본다(지수가 멈춰 있다).
    KIND 는 정규장에 KIND_SEC 마다 오늘의공시 RSS 를 읽어 제목에 서킷 낱말(KIND_WORDS)이 든 글을 모은다 — 정확한 제목 · 올라오는 늦음은
    못 쟀다. 시장 낱말(코스닥 · 유가증권 · 코스피)로 그 시장 사건에 「확인됨」 을 붙이고, 못 가르면 kind 목록에만 둔다.
    우리 셈이 놓쳤는데 KIND 가 먼저 오면 그 시장에 단계 모름(stage None) · 확인됨 사건을 만든다.

── 사이드카(2026-11-07 · 재권님 「응」 — 서킷과 같은 모양) ──

    코스피  코스피200 선물(최근월 연결 10100000 · 서버가 이미 받음 fetch_futures)이 전일 종가보다 ±5% 넘게 1분
    코스닥  코스닥150 선물(최근월 연결 10600000 · 11-07 KIS 로 받힘 확인 — 코스닥150F 202612)이 ±6% 넘게,
            그리고 코스닥150 지수(3003)가 같은 쪽으로 ±3% 넘게 1분
    → 내리면 프로그램 매도 · 오르면 매수 호가 효력 SIDECAR_MIN 분 정지 · 시장마다 하루 한 번 · SIDECAR_LAST(14:50) 뒤에는 안 걸림(다올 안내 · 원문 못 열어 봄)
    거래소 공시 낱말 KIND_WORDS_SC 로 「확인됨」. 2026 에 자주 걸려(기사 「일상된 사이드카」) 알림은 켤 때 건수를 따로 잰다

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

import market_hours
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
MARKETS = (("0001", "코스피"), ("1001", "코스닥"))
STAGES = ((1, -8.0), (2, -15.0), (3, -20.0))   # 단계 · 전일 종가 대비 %
MORE_DROP = 1.0                                 # 2 · 3단계 — 앞 단계 발동 지수보다 이만큼(%) 더
HOLD_SEC = 60                                   # 조건이 이만큼 이어져야 발동
HALT_MIN, SINGLE_MIN = 20, 10                   # 매매 중단 · 그 뒤 단일가
TICK_SEC = 10
KIND_SEC = 60
KIND_RSS = ("https://kind.krx.co.kr/disclosure/rsstodaydistribute.do?method=searchRssTodayDistribute"
            "&repIsuSrtCd=&mktTpCd=0&searchCorpName=&currentPageSize=100")
KIND_WORDS = ("서킷", "Circuit", "매매거래중단", "매매거래 중단")
SIDECAR = (("코스피", "10100000", 5.0, None, None),          # 시장 · 선물 코드 · 선물 % · 함께 볼 지수 · 지수 %
           ("코스닥", "10600000", 6.0, "3003", 3.0))
SIDECAR_MIN = 5
SIDECAR_LAST = 14 * 60 + 50                     # 이 시각부터는 안 걸림
KIND_WORDS_SC = ("사이드카", "Sidecar", "프로그램매매", "효력정지", "효력 정지")
# 사건을 **새로 만드는** 길은 시장 전체를 뜻하는 낱말만 — 넓은 낱말(효력정지 · 프로그램매매 · 매매거래중단)은 회사 공시
# (「주주총회결의 효력정지 가처분」 · 종목 하나의 매매거래 중단)에도 붙어, 우리 셈이 이미 만든 사건에 「확인됨」 을 붙일 때만 쓴다(qa 검수 11-07)
KIND_NEW_WORDS = ("서킷", "Circuit", "사이드카", "Sidecar")
SEND = False                                    # 켜기는 재권님 지시로

_SCHEMA = """CREATE TABLE IF NOT EXISTS market_event (
    day TEXT NOT NULL, market TEXT NOT NULL, kind TEXT NOT NULL, stage INTEGER, at TEXT NOT NULL,
    value REAL, pct REAL, row TEXT, PRIMARY KEY (day, market, kind, at))"""
_fut = {}
_proxy = [None]                                 # tick 이 받은 proxy — 사이드카 마감 셈이 그날 장 시각을 읽는다                                      # 코스닥150 선물 — 화면이 안 받는 값이라 여기서만 짧게 둔다
_lock = threading.Lock()
_st = {"day": None, "m": {}, "kind": [], "kindAt": None, "kindError": None, "error": None, "preview": [], "sent": 0}


def _now():
    return datetime.now(KST)


def _fresh(day):
    _st.update(day=day, kind=[], kindAt=None, preview=[], sent=0,
               m={name: {"stage": 0, "events": [], "since": None, "value": None, "pct": None, "at": None,
                         "sc": {"since": None, "side": None, "done": False, "fpct": None, "ipct": None}} for _, name in MARKETS})


def _hm(dt):
    return dt.strftime("%H:%M:%S")


def phase(ev, now):
    """사건 하나가 지금 어느 때인가 — halt 매매 중단 · single 단일가 · closed 그날 끝 · sidecar 프로그램 호가 정지 · done 지남."""
    if ev.get("type") == "sc":
        return "sidecar" if ev.get("until") and now.strftime("%H:%M:%S") < ev["until"] else "done"
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
    ev = {"type": "cb", "stage": stage, "at": at, "value": value, "pct": pct, "est": True, "confirmed": False, "kind": None}
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
    cbs = [e for e in m["events"] if e.get("type", "cb") == "cb"]
    if cbs and phase(cbs[-1], now) in ("halt", "single"):
        m["since"] = None
        return None
    nxt, thr = STAGES[m["stage"]]
    ok = pct <= thr
    if ok and nxt > 1:
        base = next((e["value"] for e in reversed(cbs) if e.get("stage") == nxt - 1 and e.get("value")), None)
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


def check_sc(name, fpct, ipct, need_i, now):
    """사이드카 — 선물 등락률(fpct) · 함께 볼 지수 등락률(ipct · 코스닥만)로. 발동이면 새 사건(시험이 그대로 부른다)."""
    m = _st["m"][name]
    sc = m["sc"]
    sc.update(fpct=fpct, ipct=ipct)
    defn = next(d for d in SIDECAR if d[0] == name)
    if sc["done"] or fpct is None or (need_i and ipct is None):
        sc["since"] = None
        return None
    side = "sell" if fpct <= -defn[2] else ("buy" if fpct >= defn[2] else None)
    if side and need_i:
        if not ((side == "sell" and ipct <= -defn[4]) or (side == "buy" and ipct >= defn[4])):
            side = None
    if not side or side != sc["side"]:
        sc["side"], sc["since"] = side, (now if side else None)
        return None
    if (now - sc["since"]).total_seconds() < HOLD_SEC:
        return None
    t0 = sc["since"] + timedelta(seconds=HOLD_SEC)
    last = SIDECAR_LAST
    if _proxy[0] is not None:                       # 그날 정규장 끝이 바뀌었으면(수능날 16:30) 40분 전도 따라 옮긴다
        c = market_hours.today(_proxy[0], now=now)["reg"][1]
        last = int(c[:2]) * 60 + int(c[2:]) - (15 * 60 + 30 - SIDECAR_LAST)
    if t0.hour * 60 + t0.minute >= last:
        sc["side"], sc["since"] = None, None     # 14:50 뒤 — 걸지 않고 다음 바퀴에 다시 센다(그래도 안 걸린다)
        return None
    ev = {"type": "sc", "side": side, "at": _hm(t0), "until": _hm(t0 + timedelta(minutes=SIDECAR_MIN)),
          "value": None, "pct": fpct, "ipct": ipct, "est": True, "confirmed": False, "kind": None}
    sc.update(done=True, since=None)
    m["events"].append(ev)
    return ev


def _kq_fut(proxy, cfg, code):
    hit = _fut.get(code)
    if hit and time.time() - hit[0] < TICK_SEC / 2:
        return hit[1]
    d = proxy.kis_get(cfg, "/uapi/domestic-futureoption/v1/quotations/inquire-price",
                      {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": code}, "FHMIF10000000")
    v = proxy._num((d.get("output1") or {}).get("futs_prdy_ctrt"))
    _fut[code] = (time.time(), v)
    return v


def _fut_pct(proxy, cfg, code):
    if code == proxy.FUTURES_CODE:          # 코스피200 — 서버가 이미 받는 값(캐시)을 그대로
        row = proxy.fetch_futures(cfg)
        return row.get("changePct") if row else None
    return _kq_fut(proxy, cfg, code)


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
        if ev.get("type") == "sc":
            m["sc"]["done"] = True
        if ev.get("stage"):
            m["stage"] = max(m["stage"], ev["stage"])


def _text(name, ev):
    if ev.get("type") == "sc":
        side = {"sell": "매도", "buy": "매수"}.get(ev.get("side"), "")
        tag = "확인됨" if ev.get("confirmed") else "추정"
        pct = "" if ev.get("pct") is None else " · 선물 %+.2f%%" % ev["pct"]
        until = (" — %s 까지 프로그램 %s 호가 정지" % (ev["until"][:5], side)) if ev.get("until") else " — 거래소 공시"
        return "[%s 사이드카 · %s] %s %s 발동%s%s" % (side, tag, name, ev["at"][:5], pct, until)
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
        typ = "sc" if any(w in title for w in KIND_WORDS_SC) else ("cb" if any(w in title for w in KIND_WORDS) else None)
        if typ is None or title in _st["kind"]:
            continue
        _st["kind"].append(title)
        name = "코스닥" if "코스닥" in title else ("코스피" if ("유가" in title or "코스피" in title or "KOSPI" in title) else None)
        if name is None:
            continue                 # 시장을 못 가름 — kind 목록에만
        m = _st["m"][name]
        ev = next((e for e in reversed(m["events"]) if not e.get("confirmed") and e.get("type", "cb") == typ), None)
        if ev is None and not any(w in title for w in KIND_NEW_WORDS):
            continue                 # 넓은 낱말뿐 — 우리 셈 사건이 없으면 새로 안 만든다
        if ev is None:               # 우리 셈이 놓침 — 시장 전체 낱말 공시로 사건을 만든다
            ev = {"type": typ, "stage": None, "at": _st["kindAt"], "value": m["value"], "pct": m["pct"], "est": False}
            if typ == "sc":
                t0 = datetime.strptime(_st["kindAt"], "%H:%M:%S")
                ev.update(stage=None, side=("sell" if "매도" in title else ("buy" if "매수" in title else None)),
                          until=(t0 + timedelta(minutes=SIDECAR_MIN)).strftime("%H:%M:%S"), pct=m["sc"]["fpct"])
                m["sc"]["done"] = True
            m["events"].append(ev)
            _alert(proxy, port, name, dict(ev, confirmed=True))
        ev.update(confirmed=True, kind=title, kindAt=_st["kindAt"])
        _save(proxy, day, name, typ, ev)


def tick(proxy, cfg, port, now=None):
    now = now or _now()
    _proxy[0] = proxy
    day = now.strftime("%Y%m%d")
    with _lock:
        if _st["day"] != day:
            _fresh(day)
            _restore(proxy, day)
        if not market_hours.in_regular(proxy, now):     # 휴장일 · 바뀐 시각(수능날 등)을 따른다 — 장 시각 한 곳
            return
        for code, name in MARKETS:
            value, pct = _index(proxy, cfg, code)
            ev = check(name, value, pct, now)
            if ev:
                print("  [시장 사건] %s 서킷 %d단계(추정) %s · 지수 %s (%.2f%%)" % (name, ev["stage"], ev["at"], value, pct), flush=True)
                _save(proxy, day, name, "cb", ev)
                _alert(proxy, port, name, ev)
        for name, fcode, _fp, icode, _ip in SIDECAR:
            fpct = _fut_pct(proxy, cfg, fcode)
            ipct = _index(proxy, cfg, icode)[1] if icode else None
            ev = check_sc(name, fpct, ipct, bool(icode), now)
            if ev:
                print("  [시장 사건] %s %s 사이드카(추정) %s · 선물 %.2f%%" % (name, ev["side"], ev["at"], fpct), flush=True)
                _save(proxy, day, name, "sc", ev)
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
            live = [e for e in evs if e["phase"] in ("halt", "single", "closed", "sidecar")]
            cur = next((e for e in reversed(live) if e.get("type", "cb") == "cb"), None) or (live[-1] if live else None)
            out[name] = {"stage": max([e.get("stage") or 0 for e in evs] + [0]), "value": m.get("value"), "pct": m.get("pct"), "at": m.get("at"),
                         "now": cur, "live": live, "events": evs}
        return {"day": day, "markets": out, "kind": list(_st["kind"]), "kindAt": _st["kindAt"]}


def status():
    return {"send": SEND, "sent": _st["sent"], "preview": list(_st["preview"]), "error": _st["error"],
            "kindError": _st["kindError"], "tickSec": TICK_SEC, "kindSec": KIND_SEC,
            "rule": "서킷 1단계 −8%% · 2단계 −15%%(+1단계보다 1%%) · 3단계 −20%%(+2단계보다 1%%) · 1분 이어짐 · 중단 %d분 · 단일가 %d분 / "
                    "사이드카 코스피200 선물 ±5%% · 코스닥150 선물 ±6%% + 코스닥150 지수 ±3%% · 1분 · %d분 · 하루 한 번 · 14:50 뒤 안 걸림" % (HALT_MIN, SINGLE_MIN, SIDECAR_MIN)}


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
            if market_hours.in_regular(proxy, now) and time.time() - last_kind >= KIND_SEC:
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
