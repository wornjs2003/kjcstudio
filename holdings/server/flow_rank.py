# -*- coding: utf-8 -*-
"""투자자 매매 동향 — 외국인 · 기관 순매수 순위와 「특이 매수」(전일 순매도 → 오늘 순매수) (2026-11-06).

재권님 — 「이거 만들고 싶어 분석해」(사진 · 작업우선순위 경유) → 분석 (가) 외국인 · 기관 가집계 먼저 / (나) 개인까지 → 「순차로 해줘」(개발2 창).
이 파일은 (가)다. 개인은 KIS 순위 API 에 갈래가 없어 (나)에서 따로 한다.

    순위      fetch_investor_top(FHPTJ04400000 · **가집계**) 를 코스피 · 코스닥 × 수량 · 금액 정렬 넷으로 불러 합친다 —
              한 번에 30줄만 오고(MOVERS_MAX) 「전체(0000)」 는 정렬에 따라 한 시장만 온다(2026-11-06 11:3x 8772 실측)
              합친 뒤 순매수 금액 순으로 LIMIT 개 · 순번은 이 합친 목록 안의 차례다
    전일      종목마다 fetch_investor(FHKST01010900 · 확정치)의 오늘 앞 가장 최근 날 순매수 금액 — 그 값은 하루 동안 안 바뀌어
              날마다 한 번만 부른다(_prev) · 뒤에서 채우고(_fill) 그동안 판은 prevMissing 을 낸다
    특이 매수  전일 순매도(< 0) → 오늘 순매수(> 0) 「전환」. 줄 세우기는 강도 순
    강도      오늘 순매수 금액 ÷ 오늘 거래대금(거래량 × 현재가) × 100 — 거래대금 중 그 투자자 순매수 몫(%) ·
              외국인 · 기관이 함께 순매수면 다른 쪽 몫도 더한다(both)
    저장      market.db `flow_rank`(날 · 투자자 · 판 JSON) — 보내는 서버가 SAVE_AT 뒤 한 번 · 지난 날은 그 표를 읽는다
    주체별    종목마다 매매 주체(개인 · 외국인 · 기관계 · 기관 안 여덟 · 기타법인) 순매수 금액 — 순매수(매수 우위)인 주체가 많은 종목이 위
              (2026-11-06 재권님 「매매 주체별 더 다양하게 … 각 매매 주체별로 매수가 우위인게 많은 종목을 위로」).
              값은 종목별 확정치 일별(FHPTJ04160001)이 쌓은 market.db `investor_daily` — 그 주소는 00:00~15:40 에 거절돼 장중에는 지난 거래일 값이다.
              보내는 서버가 평일 COLLECT_AT 뒤 한 번 — 그날 외국인 · 기관 순위 종목 + 감시 목록(dart.universe_rows) 전부를
              kis_proxy `_inv_long_fetch`(「투자자 3달」 · 종목마다 KIS 두 번 · 하루 한 번)로 쌓는다. 그 밖 종목은 화면에서 열어 본 것만
              프로그램 — 그 날 종목 프로그램 순매수(FHPPG04650201 · 거래소 J · 원 → 백만원). 주체가 아니라 「어떻게」 라 매수 우위 수에는 안 센다
              줄 세우기(재권님 「기관 외국인 프로그램 이 세개가 사면 가장 좋은거 … 이게 가장 우선이야. 그다음이 연기금」):
                ① 기관계 · 외국인 · 프로그램 셋 다 순매수(top) ② 연기금 순매수 ③ 셋 중 몇이 샀나 ④ 매수 우위 주체 수 ⑤ 순매수 금액 합
    주소      GET /api/kis/flow-rank?who=foreign|inst[&day=YYYYMMDD] · ?view=actor[&day=YYYYMMDD]

금액은 백만원 · 「없음」 은 null(0 아님). ⚠️ 오늘 값은 가집계라 장 마감 뒤 확정치와 다를 수 있다.
"""

import json
import threading
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
WHO = ("foreign", "inst")
TOP3 = ("inst", "foreign", "program")   # 셋 다 사면 맨 위 — 재권님 11-06 「이게 가장 우선이야」
MARKETS = ("KOSPI", "KOSDAQ")
LIMIT = 100
SAVE_AT = (14, 50)                 # 하루 마지막 가집계(14:30 ±10분) 뒤 — 그날 판을 남기는 시각
COLLECT_AT = (15, 45)              # 종목별 확정치(FHPTJ04160001)가 15:41 부터 받힌다(kis_proxy INVESTOR_LONG_OPEN) — 그 뒤
WARM_AT = (9, 40)                  # 첫 가집계(외국인 09:30 ±10분) 뒤 — 전일 확정치를 미리 채워 모달이 처음 열릴 때 기다리지 않게
TICK = 60
DAYS_MAX = 30                      # 지난 날 고르기 목록에 내는 날 수

_SCHEMA = """CREATE TABLE IF NOT EXISTS flow_rank (
    day TEXT NOT NULL, who TEXT NOT NULL, saved_at TEXT, board TEXT NOT NULL,
    PRIMARY KEY (day, who))"""

_cache = {}                        # who → (받은 때, 판)
_prev = {}                         # (오늘, code) → 오늘 앞 가장 최근 날 확정 행
_lock = threading.Lock()          # _want · _filling
_build_lock = threading.Lock()    # 판 셈 하나씩
_status = {"running": False, "saved": None, "error": None}


def _now():
    return datetime.now(KST)


def _amt(side):
    return (side or {}).get("amt")


def _prev_row(proxy, cfg, code, today):
    """오늘 앞 가장 최근 날 확정 행 {date, foreign, inst} — 못 받으면 None."""
    key = (today, code)
    if key in _prev:
        return _prev[key]
    try:
        rows = proxy.fetch_investor(cfg, code) or []
    except RuntimeError:
        return None                # 다음에 다시 — 못 받은 것을 남겨 두지 않는다
    row = next((r for r in rows if (r.get("date") or "") < today), None)
    out = None
    if row:
        out = {"date": row["date"],
               "foreign": (row.get("foreign") or {}).get("netAmt"),
               "inst": (row.get("inst") or {}).get("netAmt")}
    _prev[key] = out
    return out


_filling = {"on": False}
_want = set()                      # 전일 확정치를 받아야 할 (오늘, code) — 외국인 · 기관 판이 함께 넣는다


def _fill(proxy, cfg, codes, today):
    """전일 확정치를 뒤에서 채운다 — 종목마다 KIS 한 번이라 100종목이면 1분 남짓 걸린다(2026-11-06 8772 실측 60초).
    화면은 기다리지 않고 prevMissing 수를 보고 다시 묻는다. 다 채우면 판을 다시 센다."""
    with _lock:
        _want.update((today, c) for c in codes)
        if _filling["on"]:
            return
        _filling["on"] = True

    def run():
        try:
            while True:
                with _lock:
                    if not _want:
                        _filling["on"] = False
                        break
                    day, code = _want.pop()
                if _prev_row(proxy, cfg, code, day) is None and (day, code) not in _prev:
                    _prev[(day, code)] = None    # 못 받음 — 오늘은 다시 안 부른다(전일 「—」)
        finally:
            _filling["on"] = False
            _cache.clear()

    threading.Thread(target=run, daemon=True, name="flow-rank-prev").start()


def _merged(proxy, cfg):
    """{who: [행 …]} — 코스피 · 코스닥 × 수량 · 금액 넷을 합친 순매수 상위 · 못 받은 갈래 {who: 오류}."""
    rows, errors = {w: {} for w in WHO}, {}
    for market in MARKETS:
        for by in ("qty", "amt"):
            got, errs = proxy.fetch_investor_top(cfg, "buy", market, by, proxy.MOVERS_MAX)
            for w in WHO:
                if w in errs:
                    errors[w] = errs[w]
                for r in got.get(w) or []:
                    r = dict(r, market=market)
                    rows[w].setdefault(r["code"], r)
    return rows, errors


def build(proxy, cfg, who):
    now = _now()
    today = now.strftime("%Y%m%d")
    rows, errors = _merged(proxy, cfg)
    other = "inst" if who == "foreign" else "foreign"
    mine = [r for r in rows[who].values() if (_amt(r.get(who)) or 0) > 0]
    mine.sort(key=lambda r: _amt(r.get(who)), reverse=True)
    out = []
    for i, r in enumerate(mine[:LIMIT], 1):
        net, net2 = _amt(r.get(who)), _amt(r.get(other))
        value = (r.get("volume") or 0) * (r.get("price") or 0) / 1e6     # 거래대금(백만원) 어림
        both = net2 is not None and net2 > 0
        power = None
        if value > 0:
            power = round((net + (net2 if both else 0)) / value * 100, 2)
        p = _prev.get((today, r["code"]))
        prev_net = p.get(who) if p else None
        out.append({
            "rank": i, "code": r["code"], "name": r.get("name"), "market": r.get("market"),
            "price": r.get("price"), "pct": r.get("pct"),
            "net": net, "otherNet": net2, "both": both, "value": round(value) if value else None,
            "power": power, "prevNet": prev_net, "prevDate": p.get("date") if p else None,
            "flip": prev_net is not None and prev_net < 0,
        })
    missing = [x["code"] for x in out if (today, x["code"]) not in _prev]
    if missing:
        _fill(proxy, cfg, missing, today)
    special = sorted((x for x in out if x["flip"]), key=lambda x: (x["power"] is None, -(x["power"] or 0)))
    return {"day": today, "who": who, "at": now.strftime("%H:%M"), "basis": "가집계",
            "rows": out, "special": [x["code"] for x in special],
            "prevMissing": len(missing),     # 전일 확정치를 아직 못 받은 종목 수 — 0 이 되면 특이 매수가 다 센 것
            "errors": errors.get(who)}


def board(proxy, cfg, who, day=None):
    """판 하나 — day 가 오늘이 아니면 저장한 것을 읽는다(없으면 None)."""
    today = _now().strftime("%Y%m%d")
    if day and day != today:
        return _load(proxy, day, who)
    with _build_lock:
        hit = _cache.get(who)
        if hit and time.time() - hit[0] < proxy.INVESTOR_TOP_TTL:
            return hit[1]
        b = build(proxy, cfg, who)
        _cache[who] = (time.time(), b)
        return b


def _actors(proxy):
    """(열쇠 · 이름 · 줄에서 꺼내는 길) — 이름은 kis_proxy 의 INV_INST_DETAIL 한 곳에서 가져온다."""
    out = [("person", "개인", lambda r: (r.get("person") or {}).get("netAmt")),
           ("foreign", "외국인", lambda r: (r.get("foreign") or {}).get("netAmt")),
           ("inst", "기관계", lambda r: (r.get("inst") or {}).get("netAmt"))]
    for k, n in proxy.INV_INST_DETAIL:
        out.append((k, n, lambda r, k=k: ((r.get("instDetail") or {}).get(k) or {}).get("netAmt")))
    out.append(("etcCorp", "기타법인", lambda r: (r.get("etcCorp") or {}).get("netAmt")))
    return out


_pg = {}                           # (날, code) → 그 날 프로그램 순매수(백만원) 또는 None(못 받음)
_pg_want = set()
_pg_filling = {"on": False}


def _pg_get(proxy, cfg, day, code):
    try:
        data = proxy.kis_get(cfg, "/uapi/domestic-stock/v1/quotations/program-trade-by-stock-daily",
                             {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code, "FID_INPUT_DATE_1": day}, "FHPPG04650201")
    except RuntimeError:
        return None
    r = next((x for x in (data.get("output") or []) if (x.get("stck_bsop_date") or "").strip() == day), None)
    v = proxy._num(r.get("whol_smtn_ntby_tr_pbmn"), int) if r else None
    return None if v is None else round(v / 1e6)


def _pg_fill(proxy, cfg, day, codes):
    """그 날 프로그램 순매수를 뒤에서 채운다 — 종목마다 KIS 한 번. 다 채우면 화면이 다시 물을 때 들어간다."""
    with _lock:
        _pg_want.update((day, c) for c in codes)
        if _pg_filling["on"]:
            return
        _pg_filling["on"] = True

    def run():
        try:
            while True:
                with _lock:
                    if not _pg_want:
                        break
                    d, c = _pg_want.pop()
                _pg[(d, c)] = _pg_get(proxy, cfg, d, c)
        finally:
            _pg_filling["on"] = False

    threading.Thread(target=run, daemon=True, name="flow-rank-pg").start()


def actor_board(proxy, day=None, cfg=None):
    """주체별 판 — 그 날(없으면 세부가 쌓인 가장 최근 날) 종목마다 주체 순매수 금액 · 매수 우위 주체 수 순."""
    acts = _actors(proxy)
    try:
        with proxy.db_conn() as conn:
            if not day:
                r = conn.execute("SELECT MAX(date) FROM investor_daily WHERE row LIKE '%\"instDetail\": {%'").fetchone()
                day = r[0] if r else None
            rows = conn.execute("SELECT code, row FROM investor_daily WHERE date = ?", (day,)).fetchall() if day else []
            names = dict(conn.execute("SELECT stock_code, name FROM dart_universe").fetchall())
    except Exception as e:
        return {"day": day, "actors": [[k, n] for k, n, _f in acts], "rows": [], "error": type(e).__name__}
    out, pg_missing = [], []
    for code, raw in rows:
        r = json.loads(raw)
        amts = {k: f(r) for k, _n, f in acts}
        if (day, code) in _pg:
            amts["program"] = _pg[(day, code)]
        else:
            amts["program"] = None
            pg_missing.append(code)
        # 기관계는 기관 안 여덟의 합이라 세면 겹친다 — 칸으로만 보이고 주체 수에는 안 든다
        known = [v for k, v in amts.items() if v is not None and k not in ("inst", "program")]
        if not known:
            continue
        buy = sum(1 for v in known if v > 0)
        core = sum(1 for k in TOP3 if (amts.get(k) or 0) > 0)
        out.append({"code": code, "name": names.get(code) or code, "close": r.get("close"),
                    "net": amts, "buyers": buy, "counted": len(known),
                    "core": core, "top": core == len(TOP3), "fund": (amts.get("fund") or 0) > 0,
                    "buySum": sum(v for v in known if v > 0)})
    out.sort(key=lambda x: (not x["top"], not x["fund"], -x["core"], -x["buyers"], -x["buySum"]))
    if pg_missing and cfg is not None:
        _pg_fill(proxy, cfg, day, pg_missing)
    # 칸 차례 — 줄 세우기에서 먼저 보는 넷(기관계 · 외국인 · 프로그램 · 연기금)을 앞에. 「기금」 은 KIS 칸(fund)이 연기금이라 여기서는 그 이름으로
    names = dict([(k, n) for k, n, _f in acts] + [("program", "프로그램"), ("fund", "연기금")])
    first = list(TOP3) + ["fund"]
    order = first + [k for k, _n, _f in acts if k not in first]
    return {"day": day, "basis": "확정치", "actors": [[k, names[k]] for k in order], "lead": first,
            "top3": list(TOP3), "pgMissing": len(pg_missing), "sumOf": {"inst": [k for k, _n in proxy.INV_INST_DETAIL]},
            "rows": out}


# ── 「매수」 칩 쌓기 (2026-11-06 재권님 「이거 실시간으로 쌓으면서 이걸 실시간 순위에 매수에 넣어줘 계속 갱신되게」 → 그림 → 「응 넣어」) ──
# 칩 판(kis_proxy `_joint_buy_rebuild`)을 지을 때마다 그날 종목별로 — 처음 셋 다 산 시각 · 그 뒤 판에 잡힌 횟수 · 가장 큰 셋 합(원).
# 메모리에 들고 · 쓰기 되는 서버(8765)는 같은 표(flow_rank · who=joint)에 남겨 다시 떠도 그날 것을 잇는다. 다른 서버는 메모리만.
JOINT = "joint"
_jt = {"day": None, "acc": {}}
_jt_lock = threading.Lock()


def joint_track(proxy, day, rows, hm):
    """day — YYYY-MM-DD · rows — 이번 판의 줄 · hm — 지은 시각. 그날 쌓인 것 {code: {first, hits, max, name}} 을 낸다."""
    with _jt_lock:
        if _jt["day"] != day:
            old = _load(proxy, day.replace("-", ""), JOINT) or {}
            _jt["day"], _jt["acc"] = day, dict(old.get("acc") or {})
        acc = _jt["acc"]
        for r in rows:
            a = acc.setdefault(r["code"], {"first": hm, "hits": 0, "max": None, "name": r.get("name")})
            a["hits"] += 1
            if r.get("sum") is not None and (a["max"] is None or r["sum"] > a["max"]):
                a["max"] = r["sum"]
        snap = {c: dict(v) for c, v in acc.items()}
    if rows and proxy.marketdb.writable():
        try:
            _save(proxy, {"day": day.replace("-", ""), "who": JOINT, "acc": snap})
        except Exception as e:
            print("  [매수 칩 쌓기] 쓰기 실패 — %s" % type(e).__name__, flush=True)
    return snap


def joint_codes():
    """그날 한 번이라도 잡힌 종목 — 15:45 쌓기 대상에 넣는다(연기금 · 개인을 받게)."""
    with _jt_lock:
        return list(_jt["acc"]) if _jt["day"] == _now().date().isoformat() else []


def joint_more(proxy, day, codes):
    """그날 쌓인 확정치에서 연기금 · 개인 순매수(원) — 아직 없으면 {} (15:45 쌓기 전)."""
    if not codes:
        return {}
    try:
        with proxy.db_conn() as conn:
            q = "SELECT code, row FROM investor_daily WHERE date = ? AND code IN (%s)" % ",".join("?" * len(codes))
            got = conn.execute(q, [day.replace("-", "")] + list(codes)).fetchall()
    except Exception:
        return {}
    out = {}
    for code, raw in got:
        r = json.loads(raw)
        fund = ((r.get("instDetail") or {}).get("fund") or {}).get("netAmt")
        person = (r.get("person") or {}).get("netAmt")
        if fund is None and person is None:
            continue
        out[code] = {"fund": None if fund is None else fund * 1_000_000,          # 백만원 → 원
                     "person": None if person is None else person * 1_000_000}
    return out


def days(proxy):
    """저장한 날 목록(최근 먼저 · DAYS_MAX 개) — 표가 없으면 []."""
    try:
        with proxy.db_conn() as conn:
            return [d for (d,) in conn.execute("SELECT DISTINCT day FROM flow_rank ORDER BY day DESC LIMIT ?", (DAYS_MAX,))]
    except Exception:
        return []


def _load(proxy, day, who):
    try:
        with proxy.db_conn() as conn:
            r = conn.execute("SELECT board FROM flow_rank WHERE day = ? AND who = ?", (day, who)).fetchone()
    except Exception:
        return None
    return json.loads(r[0]) if r else None


def _save(proxy, b):
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        conn.execute("INSERT OR REPLACE INTO flow_rank (day, who, saved_at, board) VALUES (?,?,?,?)",
                     (b["day"], b["who"], _now().strftime("%H:%M:%S"), json.dumps(b, ensure_ascii=False)))


def _targets(proxy, cfg):
    """그날 쌓을 종목 — 외국인 · 기관 순위 판의 종목 + 감시 목록. 순서는 순위 먼저."""
    codes = joint_codes()            # 「매수」 칩에 그날 잡힌 종목 먼저(연기금 · 개인 칸)
    for w in WHO:
        codes += [r["code"] for r in (board(proxy, cfg, w) or {}).get("rows") or []]
    try:
        import dart
        codes += [r["stock_code"] for r in dart.universe_rows(None)
                  if (r["stock_code"] or "").isdigit() and len(r["stock_code"]) == 6]   # sqlite3.Row — .get 없음(11-09 · 전에는 여기서 조용히 빠졌다)
    except Exception:
        pass                       # 감시 목록을 못 읽으면 순위 종목만
    return list(dict.fromkeys(codes))


def collect(proxy, cfg):
    """종목별 주체 확정치를 쌓는다 — (쌓음 · 이미 있음/못 받음 · 대상) 수."""
    day = _now().strftime("%Y%m%d")
    codes = _targets(proxy, cfg)
    done = sum(1 for c in codes if proxy._inv_long_fetch(cfg, c))
    _pg_fill(proxy, cfg, day, codes)      # 프로그램도 그날 것으로 미리 채운다(메모리 · 이 서버만)
    return done, len(codes) - done, len(codes)


def start(proxy):
    """보내는 서버가 뜰 때 한 번 — 평일 SAVE_AT 뒤 그날 판을 남긴다."""
    def loop():
        time.sleep(60)
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                if now.weekday() < 5 and (now.hour, now.minute) >= COLLECT_AT and _status.get("collected") != day:
                    done, skip, n = collect(proxy, proxy.load_secrets())
                    _status["collected"] = day
                    print("  [투자자 매매 동향] %s 종목별 주체 확정치 %d종목 쌓음 · 건너뜀 %d · 대상 %d" % (day, done, skip, n), flush=True)
                if now.weekday() < 5 and (now.hour, now.minute) >= WARM_AT and _status.get("warmed") != day:
                    cfg = proxy.load_secrets()
                    for w in WHO:
                        board(proxy, cfg, w)
                    _status["warmed"] = day
                if now.weekday() < 5 and (now.hour, now.minute) >= SAVE_AT and _status["saved"] != day:
                    cfg = proxy.load_secrets()
                    for w in WHO:
                        _cache.pop(w, None)
                        b = board(proxy, cfg, w)
                        if b["rows"]:
                            _save(proxy, b)
                    _status["saved"] = day
                    print("  [투자자 매매 동향] %s 판 남김" % day, flush=True)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [투자자 매매 동향] 멈춤 (%s)" % type(e).__name__, flush=True)
            time.sleep(TICK)

    _status["running"] = True
    threading.Thread(target=loop, daemon=True, name="flow-rank").start()
    return True
