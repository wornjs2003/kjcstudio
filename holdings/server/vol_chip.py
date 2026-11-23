# -*- coding: utf-8 -*-
"""단타 칩 「거래비율」 · 「거래비율급증」 — 거래 비율 · 그 전날 같은 시각 대비 (2026-11-23).

처음(11:3x)은 칩 하나 「거래량급증」 = 거래 비율 ≥ ( )% **또는** 전날 같은 시각 대비 거래량 ≥ ( )% 였다. 재권님 「둘중 하나로 하지말고 각각 칩으로 해줘」 →
「두개야 / 전일대비 현시점거래비율 이랑 유통주식대비 현시점 거래비율」(11-23 16:3x · 개발2 창) → 「응 만들어」(16:4x) 로 칩 둘이 됐다. 거래량만 보는 셈은 칩에서 뺐다.

    대상     순위 목록(감시 종목) 중 시가총액 칩 룰 순위.capMinEok 이상 · ETF 뺌(open_rise._universe 와 같은 가름)
    값       turn        「거래 비율」(%) = 누적 거래대금 ÷ 풀린 시가총액 × 100 — 단타 판 칸과 같은 셈 한 곳(turnover.calc)
             turnPrevPct 「거래 비율 전날 대비」(%) = turn ÷ 전날 같은 1분 칸까지 거래 비율 × 100 — 단타 판 칸과 같은 셈 한 곳(turnover.turn_prev)
                        · 전날 1분 칸이 없으면 정규장 5분봉 끝난 봉까지 거래량 비로 어림(turnPrevSrc 「5m」) — 재권님 「데이터 받는대로 단타에 적용」(16:4x)
    장 뒤    정규장 마감(dt30._close_min) 뒤에는 오늘 쪽도 마감 칸 누적에 묶는다(turnover.same_time) — 지금 시세에는 장 뒤 거래가 더해져 분자만 커진다(qa 11-23)
    장 전    단타 판은 09:00 전(chips_now pre)에 이 칩을 안 부른다
    어디서   1분 칸은 8765 만 쌓는다 — 다른 서버의 /api/kis/vol-chip 은 8765 것을 넘긴다 · 단타 목록도 8765 것(dt30.live)
    걸림     칩 「거래비율」      turn ≥ 칩 룰 거래비율.turnPct
             칩 「거래비율급증」  turnPrevPct ≥ 칩 룰 거래비율급증.turnPrevPct          — 따로 붙는다(둘 다면 둘)
    못 잼    풀린 주식수 · 전날 값 · 오늘 끝난 5분봉이 없으면 그 칸은 None(0 아님) — 그 칩만 안 붙는다
    들고 있기 CACHE_TTL 초 — 단타 판 · 주소가 함께 쓴다
"""
import threading
import time
from datetime import datetime, timedelta, timezone

import chip_rules

KST = timezone(timedelta(hours=9))
CACHE_TTL = 60                 # 다시 세는 간격(초) — 풀린 시총 한 바퀴(turnover.TURN_INTERVAL)와 같은 1분

_st = {"at": 0.0, "data": None}
_lock = threading.Lock()


CHIPS = ("거래비율", "거래비율급증")


def build(proxy, cfg):
    import company_profile
    import open_rise
    import turnover
    cap_min = chip_rules.get("순위", "capMinEok")
    t_pct = chip_rules.get("거래비율", "turnPct")
    tp_pct = chip_rules.get("거래비율급증", "turnPrevPct")
    uni, etf = open_rise._universe(proxy)
    cand = [u for u in uni if u["cap"] is not None and u["cap"] >= cap_min]
    codes = [u["code"] for u in cand]
    quotes, _ = proxy.fetch_quotes_multi(cfg, codes, max_age=proxy.PRICE_CACHE_TTL)
    fl = company_profile.floats()
    same, info = turnover.same_time(proxy, codes, quotes)
    slot, prev1n = info["slot"], info["prev1m"]
    now = datetime.now(KST)
    prev = turnover.prev_slot(proxy, codes, now.strftime("%Y%m%d"), slot)
    rows, seen = [], 0
    for u in cand:
        q = quotes.get(u["code"]) or {}
        s = same.get(u["code"])
        if s is None:
            continue
        seen += 1
        f = fl.get(u["code"])
        fcap, turn = turnover.calc(s["price"], s["value"], f)
        tp, tsrc = turnover.turn_prev(turn, prev.get(u["code"]), f, s)
        chips = [c for c, ok in (("거래비율", turn is not None and turn >= t_pct), ("거래비율급증", tp is not None and tp >= tp_pct)) if ok]
        if chips:
            rows.append({"code": u["code"], "name": u["name"], "market": u["market"], "cap": u["cap"],
                         "price": q.get("price"), "pct": q.get("pct"), "vol": s["vol"], "floatCap": fcap,
                         "turn": turn, "turnPrevPct": tp, "turnPrevSrc": tsrc, "upto": s["upto"], "chips": chips})
    rows.sort(key=lambda r: (-(r["pct"] if r["pct"] is not None else -999), -(r["cap"] or 0)))
    return {"rows": rows, "candidates": len(cand), "quoted": seen, "etfOut": etf, "floatKnown": sum(1 for u in cand if fl.get(u["code"])),
            "slot": slot, "prev1m": prev1n, "turnPct": t_pct, "turnPrevPct": tp_pct, "capMinEok": cap_min,
            "at": now.strftime("%Y-%m-%d %H:%M:%S")}


def hits(proxy, cfg):
    """(판 dict, 받은 때 초) — CACHE_TTL 안이면 들고 있던 것."""
    now = time.time()
    with _lock:
        if _st["data"] is not None and now - _st["at"] < CACHE_TTL:
            return _st["data"], _st["at"]
    d = build(proxy, cfg)
    with _lock:
        _st.update(at=time.time(), data=d)
    return d, _st["at"]
