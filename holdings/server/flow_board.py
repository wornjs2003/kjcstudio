# -*- coding: utf-8 -*-
"""수급 정리판 — 투자자 갈래별 순매수를 한 주소로 모아 Insight 「투자 전략」 에 낸다 (2026-11-04).

재권님 — 「외국인 수급 실시간 및 정리해서 알려주는게 필요해 정리해놔」 · 「수급은 최대한 자세한게 좋아 기관 기타법인 금융투자
보험 투신 연기금 등등」(11-04 작업우선순위 경유) → 「insite에 투자전략에 넣어보면 좋을거 같은데」 → 서버 안 「응 해」(11-04 · 개발2 창).
화면은 시황분석이 만든다. 알림은 없다(화면만).

**새로 KIS 를 부르지 않는다** — 이미 받는 셋을 모은다.

    오늘(장중)   intraday_flow 가 1분마다 쌓는 시장 투자자 누계(market.db `flow_snap` · FHPTJ04030000) — 코스피만.
                외국인 · 기관 · 개인 + 기관 안 아홉(금융투자 · 투신 · 사모 · 은행 · 보험 · 종금 · 연기금 · 기타기관 · 기타법인).
                외국인 등록 · 미등록은 그 응답에 칸이 없어 오늘 값이 없다(null). 코스닥은 시장 번호를 아직 못 맞췄다(intraday_flow 머리)
                ⚠️ 장중 누계는 확정치와 크게 다르다 — 11-03 15:30 외국인 −4,736억 ↔ 그날 확정 −1조 5,100억(2026-11-04 08:4x 견줌).
                무엇이 빠진 값인지는 아직 못 갈랐다 — 화면은 「장중 잠정」 으로 따로 적는다
    날마다       fetch_investor_flow(FHPTJ04040000 · 확정치)의 `detail` — 코스피 · 코스닥 · 기관 세부 · 기타법인.
                외국인 등록 · 미등록은 문서(docs/kis-sector-investor.md 3절)에는 있다고 적혔는데 응답에 칸이 안 왔다(11-04 08:39 · null)
    상위 종목    fetch_investor_top(FHPTJ04400000) — **가집계**(외국인 09:30 · 11:20 · 13:20 · 14:30 / 기관 10:00 · 11:20 · 13:20 · 14:30)

    주소   GET /api/kis/flow-board?days=N&step=M — 모양은 board() 주석. 금액 백만원 · 수량 천주 · 「없음」 은 null(0 아님)
"""

import time

import intraday_flow
from secrets_guard import safe_message

# (열쇠 · KIS 앞머리 · 이름 · 묶음) — 화면이 이 순서로 그린다. 묶음 inst 는 기관계 안, etc 는 그 밖
GROUPS = (
    ("person", "prsn", "개인", None),
    ("foreign", "frgn", "외국인", None),
    ("foreignReg", "frgn_reg", "외국인 등록", "foreign"),
    ("foreignNreg", "frgn_nreg", "외국인 미등록", "foreign"),
    ("inst", "orgn", "기관계", None),
    ("scrt", "scrt", "금융투자", "inst"),
    ("ivtr", "ivtr", "투신", "inst"),
    ("peFund", "pe_fund", "사모", "inst"),
    ("bank", "bank", "은행", "inst"),
    ("insu", "insu", "보험", "inst"),
    ("mrbn", "mrbn", "종금", "inst"),
    ("fund", "fund", "연기금", "inst"),
    ("etcOrgt", "etc_orgt", "기타기관", "inst"),
    ("etcCorp", "etc_corp", "기타법인", None),
)
DETAIL = tuple(p for _k, p, _n, _g in GROUPS if p not in ("prsn", "frgn", "orgn"))   # fetch_investor_flow 가 `detail` 로 담는 앞머리
DAYS_DEFAULT, DAYS_MAX = 20, 60
STEP_DEFAULT = 30
TOP_LIMIT = 10
CACHE_TTL = 60                      # 오늘 값이 1분마다 쌓이니 그보다 자주 다시 셀 까닭이 없다

_cache = {}


def _today_net(v):
    """flow_snap 한 칸(누계) → {열쇠: 순매수 금액(백만원)}."""
    out = {}
    for k, p, _n, _g in GROUPS:
        if p in intraday_flow.WHO:
            out[k] = (v.get(p) or {}).get("net")
        else:
            out[k] = (v.get("inst") or {}).get(p)          # 기관 안 아홉 · 외국인 등록/미등록은 칸이 없어 None
    return out


def _today(proxy, step):
    day = intraday_flow._now().strftime("%Y%m%d")
    snaps = intraday_flow._load(proxy, day, "mkt", "KOSPI")
    if not snaps:
        return {"market": "KOSPI", "day": day, "lastAt": None, "net": None, "rows": [],
                "reason": "오늘 쌓인 값 없음(장 전 · 휴장 · 쌓는 서버가 안 돎)"}
    return {"market": "KOSPI", "day": day, "lastAt": snaps[-1][0], "net": _today_net(snaps[-1][1]),
            "rows": intraday_flow._buckets(snaps, step, _today_net), "reason": None}


def _day_row(r):
    det = r.get("detail") or {}
    side = {"prsn": r.get("retail"), "frgn": r.get("foreign"), "orgn": r.get("inst")}
    net, qty = {}, {}
    for k, p, _n, _g in GROUPS:
        s = side.get(p) if p in side else det.get(p)
        net[k] = (s or {}).get("amt")
        qty[k] = (s or {}).get("qty")
    return {"date": r.get("date"), "index": r.get("index"), "indexPct": r.get("indexPct"), "net": net, "qty": qty}


def board(proxy, cfg, days=DAYS_DEFAULT, step=STEP_DEFAULT):
    """GET /api/kis/flow-board 의 data —
        groups   [{key, name, of}]   of = 묶음(inst 기관계 안 · foreign 외국인 안 · null 맨 위)
        today    {market, day, lastAt: 「HHMM」, net: {열쇠: 백만원}, rows: [{t, 열쇠: 그 구간 순매수}], reason}   코스피만
        days     {KOSPI: [{date, index, indexPct, net: {열쇠}, qty: {열쇠}}], KOSDAQ: […]}   과거 → 최근 · 확정치(오늘 줄은 확정 시각 전엔 뺀다)
        top      {buy: {foreign: [...], inst: [...]}, sell: {...}}   fetch_investor_top 그대로 · 가집계
        errors   {자리: 문구}   못 받은 자리 — 그 자리 값은 빈 목록 · null"""
    key = (days, step)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    errors = {}
    try:
        today = _today(proxy, step)
    except Exception as e:
        today, errors["today"] = None, safe_message(e, 160)
    hist = {}
    for m in ("KOSPI", "KOSDAQ"):
        try:
            # 오늘 줄은 확정 전(장 전 · 장중)에 0 으로 온다(2026-11-04 08:39 실측 — 갈래 전부 0) — 0 으로 내지 않고 뺀다.
            # 확정되는 시각은 종목 확정치를 쌓는 시각과 같게 본다(kis_proxy.INVESTOR_LONG_OPEN)
            now = intraday_flow._now()
            cut = now.strftime("%Y-%m-%d") if (now.hour, now.minute) < proxy.INVESTOR_LONG_OPEN else None
            hist[m] = [_day_row(r) for r in proxy.fetch_investor_flow(cfg, m, days + 1) if r.get("date") != cut][-days:]
        except Exception as e:
            hist[m], errors["days." + m] = [], safe_message(e, 160)
    top = {}
    for d in ("buy", "sell"):
        try:
            rows, err = proxy.fetch_investor_top(cfg, d, "all", "amt", TOP_LIMIT)
            top[d] = rows
            for who, msg in (err or {}).items():
                errors["top.%s.%s" % (d, who)] = msg
        except Exception as e:
            top[d], errors["top." + d] = {}, safe_message(e, 160)
    out = {"groups": [{"key": k, "name": n, "of": g} for k, _p, n, g in GROUPS],
           "today": today, "days": hist, "top": top, "errors": errors}
    _cache[key] = (time.time(), out)
    return out
