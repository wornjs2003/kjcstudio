# -*- coding: utf-8 -*-
"""프리장 — 넥스트레이드 프리마켓(08:00~08:50)에 프로그램이 몰리는 종목 · 실시간 순위 「프리장」 칩 (2026-11-05).

재권님 — 「프리장 열리면 매수 쪽 몰리는것들 바로 체크되나?」 → 「프리장에 프로그램 몰리는것 만들어줘. 이걸 참고해서 매매를 할수있게
다른것들도 같이 챙겨서 해줘봐」 → 안 「응 만들어」(개발2 창 18:1x).

    왜 따로     「매수」 칩의 외국인 · 기관은 증권사 가집계라 첫 입력이 09:30 — 프리장에는 값이 없다. 프로그램은 통합(UN)
                체결 줄이라 넥스트레이드 체결이 든다(11-05 17:35 애프터 줄로 확인 · 프리장은 아직 안 잼)
    대상        순위 목록(dart.universe_rows · 코스피 200 · 코스닥 150) — 멀티 시세 NX(넥스트레이드만) 로 한 번에 훑고(30종목씩),
                프리장 거래대금(현재가 × 누적 거래량 · 어림)이 큰 TOP_N 종목만 프로그램을 따로 받는다(종목마다 1건)
    칸          프로그램 순매수(원 · 그날 누적 = 프리장 몫) · 등락률(전일 정규장 종가 대비) · 거래대금(어림) ·
                거래량 배율(오늘 ÷ 앞 거래일 장 전 거래량 · nxt_pre 가 08:51 에 쌓는 표 · 앞 날이 MIN_PREV 주 미만이면 None) ·
                공시(앞 평일 15:30 뒤 받은 것 — dart_disclosures)
    업종        같은 업종(네이버 WICS · company_profile.sectors)끼리 프리장 등락률을 묶는다 — 거래가 있는 종목이 SECTOR_MIN 이상인 업종만 ·
                평균 등락률 크기(절댓값) 큰 순 SECTOR_TOP 개 · 오른 수 · 내린 수 · 가장 많이 움직인 종목 둘
                (11-05 재권님 「프리장에 동일업종들이 등락이 많은것도 표기가 되면 좋을거같은데」)
    차례        프로그램 순매수 큰 순 · 못 받은 것은 맨 뒤
    언제        평일 08:00~08:50 은 TTL 마다 뒤에서 다시 짓는다 · 08:50~09:00 에 한 번 더 지어 그날 판으로 굳힌다(phase closed) —
                09:00 이 지나면 넥스트레이드 메인장이 섞여 다시 안 짓는다 · 다음 평일 08:00 까지 그 판이 남는다
    없음        못 받은 값은 None(0 아님) · 넥스트레이드 거래량 합이 0 이면 휴장 · 장 전으로 보고 판을 비운다(nxt_pre 와 같은 셈)

KIS 는 proxy.kis_get(예산 · 토큰은 그쪽) · 한 번 짓는 데 멀티 12건 + TOP_N 건.
"""

import threading
import time
from datetime import datetime, timedelta, timezone

import nxt_pre

KST = timezone(timedelta(hours=9))

PRE_OPEN = (8, 0)        # 넥스트레이드 프리마켓
PRE_CLOSE = (8, 50)
MAIN_OPEN = (9, 0)       # 이 뒤에는 NX 값에 메인장이 섞인다 — 안 짓는다
TOP_N = 40               # 프로그램을 따로 받는 종목 수(프리장 거래대금 순)
FLOW_TTL = 180           # 프리장 동안 다시 짓는 간격(초) — 화면이 다시 묻는 주기도 이 값(서버 값)
FIRST_WAIT = 15          # 첫 판을 기다리는 최대 시간(초)
MIN_PREV = nxt_pre.MIN_PREV   # 거래량 배율 — 앞 날 장 전 거래량 문턱(주)
SECTOR_MIN = 3           # 업종 묶음 — 거래가 있는 종목이 이 수 이상인 업종만
SECTOR_TOP = 6           # 업종 묶음 — 평균 등락률 크기 큰 순 몇 개

_st = {"at": 0.0, "data": None, "day": None, "final": False}
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
    return [r["stock_code"] for r in dart.universe_rows(None)
            if (r.get("stock_code") or "").isdigit() and len(r["stock_code"]) == 6]


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


def _make(proxy, cfg):
    now = _now()
    day = now.strftime("%Y%m%d")
    nx = nxt_pre.fetch_nx(proxy, cfg, _universe())
    if not nx or not sum((r.get("vol") or 0) for r in nx.values()):
        return {"rows": [], "noTrade": True, "day": day, "hm": now.strftime("%H:%M")}
    prev = _prev_pre_vol(proxy, day)
    amt = lambda r: (r.get("price") or 0) * (r.get("vol") or 0)
    cand = sorted([c for c, r in nx.items() if (r.get("vol") or 0) > 0], key=lambda c: -amt(nx[c]))[:TOP_N]
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
    rows.sort(key=lambda x: (x["program"] is None, -(x["program"] or 0)))
    return {"rows": rows, "sectors": _sectors(nx), "noTrade": False, "programMissing": missing, "candidates": len(cand),
            "day": day, "hm": now.strftime("%H:%M")}


def _rebuild(proxy, cfg):
    if not _build.acquire(blocking=False):
        return
    try:
        ph = phase()
        m = _make(proxy, cfg)
        with _lock:
            _st["data"], _st["at"], _st["day"] = m, time.time(), m["day"]
            _st["final"] = ph == "closed"          # 08:50~09:00 에 지은 판 — 그날 판으로 굳힌다
    except Exception as e:
        print("  [프리장] 짓다 멈춤 (%s)" % type(e).__name__, flush=True)
    finally:
        _build.release()


def fetch(proxy, cfg):
    """(판, 지은 시각, phase). 프리장 동안은 낡으면 뒤에서 다시 짓고, 08:50~09:00 에 한 번 굳힌다."""
    now = _now()
    ph = phase(now)
    day = now.strftime("%Y%m%d")
    with _lock:
        data, at, sday, final = _st["data"], _st["at"], _st["day"], _st["final"]
    hm = (now.hour, now.minute)
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
