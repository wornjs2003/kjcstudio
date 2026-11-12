# -*- coding: utf-8 -*-
"""프리장 — 넥스트레이드 프리마켓(08:00~08:50)에 프로그램이 몰리는 종목 · 실시간 순위 「프리장」 칩 (2026-11-05).

재권님 — 「프리장 열리면 매수 쪽 몰리는것들 바로 체크되나?」 → 「프리장에 프로그램 몰리는것 만들어줘. 이걸 참고해서 매매를 할수있게
다른것들도 같이 챙겨서 해줘봐」 → 안 「응 만들어」(개발2 창 18:1x).

    왜 따로     「매수」 칩의 외국인 · 기관은 증권사 가집계라 첫 입력이 09:30 — 프리장에는 값이 없다. 프로그램은 통합(UN)
                체결 줄이라 넥스트레이드 체결이 든다(11-05 17:35 애프터 줄로 확인 · 프리장은 아직 안 잼)
    대상        순위 목록(dart.universe_rows · 시가총액 dart.UNIVERSE_MIN_CAP_EOK 이상) — 멀티 시세 NX(넥스트레이드만) 로 한 번에 훑고(30종목씩),
                프리장 거래대금(현재가 × 누적 거래량 · 어림)이 큰 TOP_N 종목만 프로그램을 따로 받는다(종목마다 1건)
    칸          프로그램 순매수(원 · 그날 누적 = 프리장 몫) · 등락률(전일 정규장 종가 대비) · 거래대금(어림) ·
                거래량 배율(오늘 ÷ 앞 거래일 장 전 거래량 · nxt_pre 가 08:51 에 쌓는 표 · 앞 날이 MIN_PREV 주 미만이면 None) ·
                공시(앞 평일 15:30 뒤 받은 것 — dart_disclosures)
    업종        같은 업종(네이버 WICS · company_profile.sectors)끼리 프리장 등락률을 묶는다 — 거래가 있는 종목이 SECTOR_MIN 이상인 업종만 ·
                평균 등락률 크기(절댓값) 큰 순 SECTOR_TOP 개 · 오른 수 · 내린 수 · 가장 많이 움직인 종목 둘
                (11-05 재권님 「프리장에 동일업종들이 등락이 많은것도 표기가 되면 좋을거같은데」)
    고르기      전일 정규장 종가보다 오른(RISE_MIN_PCT 초과) 종목 중 프리장 거래대금 상위 TOP_N · 거래대금 큰 순 — pick() 한 곳
                (2026-11-12 재권님 「프리장 룰 이건데 개선하자. 거래대금이 많은데 상승인 종목 70개」 → (가) 「응 맞아」 ·
                 「실시간으로 거래대금 재면서 최종으로 8시 50분에 궅힌다」. 그 전에는 거래대금 상위 40 · 프로그램 순매수 큰 순이었다 —
                 프로그램은 거르기에서 빠지고 칸으로만 남는다)
    언제        평일 08:00~08:50 은 TTL 마다 뒤에서 다시 짓는다 · 08:50~09:00 에 한 번 더 지어 그날 판으로 굳힌다(phase closed) —
                09:00 이 지나면 넥스트레이드 메인장이 섞여 다시 안 짓는다 · 다음 평일 08:00 까지 그 판이 남는다
    없음        못 받은 값은 None(0 아님) · 넥스트레이드 거래량 합이 0 이면 휴장 · 장 전으로 보고 판을 비운다(nxt_pre 와 같은 셈)

KIS 는 proxy.kis_get(예산 · 토큰은 그쪽) · 한 번 짓는 데 멀티 12건 + TOP_N 건.

**보내는 서버(8765)가 묻는 이 없이도 짓고 그날 판을 DB 에 남긴다** (11-05 qa 덧 — 메모리에만 두면 아무도 안 열었거나 재시작하면
그날 판이 사라졌다). start() 바퀴가 프리장 동안 FLOW_TTL 마다 · 08:50~09:00 에 한 번 지어 market.db `pre_flow_board`(날 · 판 JSON)에
쓴다. 다른 서버(세션 · 8764)는 메모리에 판이 없으면 그 표를 읽는다(세션 서버는 메인 DB 를 읽기 전용) — 하루 KIS 900건쯤(17번 × 52).
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import nxt_pre

KST = timezone(timedelta(hours=9))

PRE_OPEN = (8, 0)        # 넥스트레이드 프리마켓
PRE_CLOSE = (8, 50)
MAIN_OPEN = (9, 0)       # 이 뒤에는 NX 값에 메인장이 섞인다 — 안 짓는다
TOP_N = 70               # 프리장 판 줄 수 — 오른 종목 중 거래대금 상위(재권님 「상승인 종목 70개」 11-12 · 전에는 40)
RISE_MIN_PCT = 0.0       # 「상승」 — 전일 정규장 종가 대비 이 % 를 넘어야 든다(보합은 안 든다 · 재권님 (가) 11-12)
FLOW_TTL = 180           # 프리장 동안 다시 짓는 간격(초) — 화면이 다시 묻는 주기도 이 값(서버 값)
FIRST_WAIT = 15          # 첫 판을 기다리는 최대 시간(초)
MIN_PREV = nxt_pre.MIN_PREV   # 거래량 배율 — 앞 날 장 전 거래량 문턱(주)
SECTOR_MIN = 3           # 업종 묶음 — 거래가 있는 종목이 이 수 이상인 업종만
SECTOR_TOP = 6           # 업종 묶음 — 평균 등락률 크기 큰 순 몇 개

_st = {"at": 0.0, "data": None, "day": None, "final": False, "read": 0.0}     # read — 읽는 서버가 DB 를 마지막으로 읽은 때
_SCHEMA = """CREATE TABLE IF NOT EXISTS pre_flow_board (
    day TEXT PRIMARY KEY, data TEXT NOT NULL, final INTEGER, saved_at TEXT)"""
_writer = {"on": False}      # start() 를 부른 서버(8765)만 DB 에 쓴다
_lock = threading.Lock()
_build = threading.Lock()


def _now():
    return datetime.now(KST)


def phase(now=None):
    """before(평일 08:00 전) · live(08:00~08:50) · closed(그 밖)."""
    now = now or _now()
    hm = (now.hour, now.minute)
    if now.weekday() >= 5:
        return "closed"
    if hm < PRE_OPEN:
        return "before"
    if hm < PRE_CLOSE:
        return "live"
    return "closed"


def _universe():
    import dart
    # 줄은 sqlite3.Row 라 `.get` 이 없다 — 11-09 까지 여기서 AttributeError 로 판이 한 번도 안 지어졌다(8765 로그 「짓다 멈춤」 · 개발2 잼)
    return [r["stock_code"] for r in dart.universe_rows(None)
            if (r["stock_code"] or "").isdigit() and len(r["stock_code"]) == 6]


def _prev_weekday(now):
    d = now.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _prev_pre_vol(proxy, day):
    """앞 거래일 장 전 거래량 {code: vol} — nxt_pre 표(08:51 저장). 없으면 {}."""
    try:
        prev = nxt_pre._prev_day(proxy, day)
        return {c: r.get("vol") for c, r in nxt_pre._saved(proxy, prev).items()} if prev else {}
    except Exception:
        return {}


def _disclosures(proxy, codes, now):
    """앞 평일 15:30 뒤 받은 공시 {code: [제목 …]} — dart_disclosures(받은 시각 received_at)."""
    since = "%sT15:30" % _prev_weekday(now).isoformat()
    if not codes:
        return {}
    try:
        with proxy.db_conn() as conn:
            rows = conn.execute("SELECT stock_code, report_nm FROM dart_disclosures WHERE received_at >= ? AND stock_code IN (%s) "
                                "ORDER BY rcept_no DESC" % ",".join("?" * len(codes)), [since] + list(codes)).fetchall()
    except Exception:
        return {}
    out = {}
    for c, nm in rows:
        out.setdefault(c, []).append(" ".join((nm or "").split()))
    return out


def _sectors(nx):
    """업종별 프리장 등락 — [{name, n, up, down, avg, top: [{code, name, pct}…]}] · 업종 이름이 없는 종목은 뺀다."""
    try:
        import company_profile
        sec = company_profile.sectors()
    except Exception:
        return []
    groups = {}
    for c, r in nx.items():
        pc, px = r.get("prev_close"), r.get("price")
        if not (r.get("vol") and pc and px and sec.get(c)):
            continue
        groups.setdefault(sec[c], []).append({"code": c, "name": r.get("name"), "pct": round((px / pc - 1) * 100, 2)})
    out = []
    for name, xs in groups.items():
        if len(xs) < SECTOR_MIN:
            continue
        avg = sum(x["pct"] for x in xs) / len(xs)
        out.append({"name": name, "n": len(xs), "up": sum(1 for x in xs if x["pct"] > 0),
                    "down": sum(1 for x in xs if x["pct"] < 0), "avg": round(avg, 2),
                    "top": sorted(xs, key=lambda x: -abs(x["pct"]))[:2]})
    out.sort(key=lambda g: -abs(g["avg"]))
    return out[:SECTOR_TOP]


def pick(items):
    """프리장 판 고르기 한 곳 — items 는 {code, amt, pct} · 오른(pct > RISE_MIN_PCT) 것 중 거래대금 큰 순 TOP_N 의 code.
    등락률을 모르면 안 든다(오른 것을 고르는 판이라). 되채우기(day_top_fill · dt30)도 이것을 부른다."""
    up = [x for x in items if (x.get("amt") or 0) > 0 and x.get("pct") is not None and x["pct"] > RISE_MIN_PCT]
    return [x["code"] for x in sorted(up, key=lambda x: -x["amt"])[:TOP_N]]


def _make(proxy, cfg):
    now = _now()
    day = now.strftime("%Y%m%d")
    nx = nxt_pre.fetch_nx(proxy, cfg, _universe())
    if not nx or not sum((r.get("vol") or 0) for r in nx.values()):
        return {"rows": [], "noTrade": True, "day": day, "hm": now.strftime("%H:%M")}
    prev = _prev_pre_vol(proxy, day)
    amt = lambda r: (r.get("price") or 0) * (r.get("vol") or 0)
    pct = lambda r: (r["price"] / r["prev_close"] - 1) * 100 if r.get("price") and r.get("prev_close") else None
    cand = pick([{"code": c, "amt": amt(r), "pct": pct(r)} for c, r in nx.items() if (r.get("vol") or 0) > 0])
    disc = _disclosures(proxy, cand, now)
    rows, missing = [], 0
    for c in cand:
        r = nx[c]
        pg = proxy._program_net_today(cfg, c)
        if pg is None:
            missing += 1
        pc, px = r.get("prev_close"), r.get("price")
        pv = prev.get(c)
        rows.append({"code": c, "name": r.get("name"), "price": px,
                     "pct": round((px / pc - 1) * 100, 2) if px and pc else None,
                     "amt": amt(r) or None, "vol": r.get("vol"),
                     "ratio": round(r["vol"] / pv, 1) if pv and pv >= MIN_PREV else None,
                     "program": pg, "disc": disc.get(c) or []})
    return {"rows": rows, "sectors": _sectors(nx), "noTrade": False, "programMissing": missing, "candidates": len(cand),
            "day": day, "hm": now.strftime("%H:%M")}


def _save(proxy, m, final):
    try:
        with proxy._db_lock, proxy.db_conn() as conn:
            conn.execute(_SCHEMA)
            conn.execute("INSERT OR REPLACE INTO pre_flow_board (day, data, final, saved_at) VALUES (?,?,?,?)",
                         (m["day"], json.dumps(m, ensure_ascii=False), 1 if final else 0, _now().strftime("%H:%M:%S")))
    except Exception as e:
        print("  [프리장] 저장 못 함 (%s)" % type(e).__name__, flush=True)


def _load_saved(proxy):
    """DB 에 남은 가장 최근 판 (판, 굳혔나, 남긴 때 epoch) — 없거나 못 읽으면 (None, False, 0).
    남긴 때는 그날 · saved_at 으로 센다 — 읽은 지금으로 두면 아침 판이 방금 받은 값처럼 보였다(qa 덧 11-05)."""
    try:
        with proxy.db_conn() as conn:
            r = conn.execute("SELECT data, final, day, saved_at FROM pre_flow_board ORDER BY day DESC LIMIT 1").fetchone()
        if not r:
            return None, False, 0.0
        try:
            built = datetime.strptime(r[2] + r[3], "%Y%m%d%H:%M:%S").replace(tzinfo=KST).timestamp()
        except (TypeError, ValueError):
            built = 0.0
        return json.loads(r[0]), bool(r[1]), built
    except Exception:
        return None, False, 0.0


def _rebuild(proxy, cfg):
    if not _build.acquire(blocking=False):
        return
    try:
        ph = phase()
        m = _make(proxy, cfg)
        with _lock:
            _st["data"], _st["at"], _st["day"] = m, time.time(), m["day"]
            _st["final"] = ph == "closed"          # 08:50~09:00 에 지은 판 — 그날 판으로 굳힌다
        if _writer["on"] and not m.get("noTrade"):
            _save(proxy, m, ph == "closed")
    except Exception as e:
        # 어디서 멈췄는지 함께 찍는다 — 이름만 찍어 11-09 에 까닭을 로그로 못 갈랐다
        import traceback
        tb = traceback.extract_tb(e.__traceback__)[-1]
        print("  [프리장] 짓다 멈춤 (%s · %s:%s)" % (type(e).__name__, os.path.basename(tb.filename), tb.lineno), flush=True)
    finally:
        _build.release()


def fetch(proxy, cfg):
    """(판, 지은 시각, phase). 쓰는 서버(start 를 부른 8765)는 프리장 동안 낡으면 뒤에서 다시 짓고 08:50~09:00 에 한 번 굳힌다 ·
    읽는 서버는 DB 에 남은 판만 읽는다."""
    now = _now()
    ph = phase(now)
    day = now.strftime("%Y%m%d")
    with _lock:
        data, at, sday, final = _st["data"], _st["at"], _st["day"], _st["final"]
    hm = (now.hour, now.minute)
    if not _writer["on"]:
        # 읽는 서버(8764 · 세션) — 짓지 않는다(받는 곳은 서버 하나 · 개념정의 검수 11-05). 판이 없거나 FLOW_TTL 보다 낡았으면
        # 쓰는 서버가 남긴 판을 다시 읽는다. 프리장 중인데 DB 에 오늘 판이 아직 없으면 None — 화면은 「아직」
        if data is None or time.time() - _st["read"] >= FLOW_TTL:
            saved, sfinal, built = _load_saved(proxy)
            with _lock:
                _st["data"], _st["day"], _st["final"], _st["at"], _st["read"] = saved, (saved or {}).get("day"), sfinal, built, time.time()
            data, at = saved, built
        if ph == "live" and data and data.get("day") != day:
            return None, at, ph
        return data, at, ph
    if data is None or (sday != day and ph != "live"):
        saved, sfinal, built = _load_saved(proxy)   # 재시작 뒤 — 이 서버가 남긴 그날(또는 앞 날) 판 · at 은 남긴 때
        if saved:
            with _lock:
                _st["data"], _st["day"], _st["final"] = saved, saved.get("day"), sfinal
                _st["at"] = built or _st["at"]
            data, sday, final, at = saved, saved.get("day"), sfinal, _st["at"]
    want = (ph == "live" and (data is None or sday != day or time.time() - at >= FLOW_TTL)) or \
           (ph == "closed" and now.weekday() < 5 and PRE_CLOSE <= hm < MAIN_OPEN and not (sday == day and final))
    if want:
        t = threading.Thread(target=_rebuild, args=(proxy, cfg), daemon=True, name="pre-flow")
        t.start()
        if data is None or sday != day:
            t.join(FIRST_WAIT)
            with _lock:
                data, at = _st["data"], _st["at"]
    return data, at, ph


def start(proxy):
    """보내는 서버가 뜰 때 한 번 — 묻는 이 없이 프리장 판을 짓고 DB 에 남기는 바퀴."""
    _writer["on"] = True

    def loop():
        time.sleep(30)
        while True:
            try:
                fetch(proxy, proxy.load_secrets())
            except Exception as e:
                print("  [프리장] 바퀴 멈춤 (%s)" % type(e).__name__, flush=True)
            time.sleep(30)

    threading.Thread(target=loop, daemon=True, name="pre-flow-loop").start()
    return True
