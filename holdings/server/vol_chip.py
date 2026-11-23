# -*- coding: utf-8 -*-
"""단타 칩 「거래량」 — 풀린 주식수 대비 거래량 · 어제 같은 시각까지 대비 거래량 (2026-11-23).

재권님 — 「거래량 검색식을 만들어야 되는데. 풀린주식수 대비 거래량을 알아야 하고 어제대비 거래량도 알아야해. 3천억이상 종목중에
상승이 많이 있는 종목들 찾아서 …」(작업우선순위 창 11:2x) → 시안 그림 → 「지수는 빼고 이정보를 실시간으로 들고 있어야 하고 단타엡에 추가해줘
풀린주식대비()%이거나 전일거래대비 ()% 일때 거래량이다. 라는 룰로」 → 「대비 2 거래량 250 으로 디폴트로 하고 내가 넣으면 넣은값으로」(11:3x · 개발1 창).

    대상     순위 목록(감시 종목) 중 시가총액 칩 룰 순위.capMinEok 이상 · ETF 뺌(open_rise._universe 와 같은 가름)
    값       vol        지금 누적 거래량(주) — 묶음 시세(fetch_quotes_multi) 캐시를 함께 탄다(풀린 시총 한 바퀴 · 장외 칩이 이미 받은 값)
             turn       「거래 비율」(%) = 누적 거래대금 ÷ 풀린 시가총액 × 100 — 단타 판 칸과 같은 셈 한 곳(turnover.calc) · 재권님 「나 로 해」(11-23 11:4x ·
                        개념정의 창 11:2x 「풀린 주식수 대비 거래량을 새로 두지 않고 거래 비율 하나로」 와 맞춤 — 처음 판은 거래량 ÷ 풀린 주식수를 따로 셌다)
             prevSamePct 전일 동시간 누적 대비(%) = 지금 누적 거래량 ÷ 어제 같은 분까지 누적 거래량 × 100 — 재권님 「대비와 거래량 기준은 전일 동시간 누적이야」
                        · 「9시1분이면 그시간대에 대한 값이여야 하고 9시 30분이면 그시간대여야해」(11-23 11:3x). 어제 값은 1분 바퀴가 쌓은
                        turnover_slot.vol(그 분의 통합 누적 · 오늘과 같은 시세 · 같은 자리) — prevSrc 「1m」
                        그 칸이 아직 없는 날(거래량 칸을 처음 쌓은 11-23 의 다음 거래일 전)만 홈 큰 차트 셈(kis_proxy.vol_same_time · 정규장 5분봉 끝난 봉까지) — prevSrc 「5m」 · upto
    장 뒤    정규장 마감(dt30._close_min) 뒤에는 오늘 쪽도 마감 칸 누적에 묶는다 — 지금 시세에는 장 뒤 거래가 더해져 분자만 커진다(qa 11-23)
    장 전    단타 판은 09:00 전(chips_now pre)에 이 칩을 안 부른다 — 그 앞에서 돌아간다
    어디서   1분 칸은 8765 만 쌓는다 — 다른 서버의 /api/kis/vol-chip 은 8765 것을 넘긴다 · 단타 목록도 8765 것(dt30.live)
    걸림     turn ≥ 칩 룰 거래량.turnPct  **또는**  prevSamePct ≥ 칩 룰 거래량.prevSamePct
    못 잼    풀린 주식수 · 어제 5분봉 · 오늘 끝난 5분봉이 없으면 그 칸은 None(0 아님) — 다른 칸으로만 가린다
    들고 있기 CACHE_TTL 초 — 단타 판 · 주소가 함께 쓴다. 감시 종목 전부를 다시 센다(「실시간으로 들고 있어야」)
"""
import threading
import time
from datetime import datetime, timedelta, timezone

import chip_rules

KST = timezone(timedelta(hours=9))
CACHE_TTL = 60                 # 다시 세는 간격(초) — 풀린 시총 한 바퀴(turnover.TURN_INTERVAL)와 같은 1분

_st = {"at": 0.0, "data": None}
_lock = threading.Lock()


def build(proxy, cfg):
    import company_profile
    import open_rise
    cap_min = chip_rules.get("순위", "capMinEok")
    t_pct = chip_rules.get("거래량", "turnPct")
    p_pct = chip_rules.get("거래량", "prevSamePct")
    uni, etf = open_rise._universe(proxy)
    cand = [u for u in uni if u["cap"] is not None and u["cap"] >= cap_min]
    quotes, _ = proxy.fetch_quotes_multi(cfg, [u["code"] for u in cand], max_age=proxy.PRICE_CACHE_TTL)
    fl = company_profile.floats()
    import turnover
    now = datetime.now(KST)
    import dt30
    hm, close = now.hour * 60 + now.minute, dt30._close_min(proxy, now)
    slot = turnover._slot(min(hm, close))
    day = now.strftime("%Y%m%d")
    prev1 = turnover.prev_slot_vol(proxy, [u["code"] for u in cand], day, slot)
    # 정규장이 끝난 뒤에는 오늘 쪽도 마감 칸 값에 묶는다 — 지금 시세는 장 뒤(넥스트레이드 애프터) 거래가 더해져 분자에만 쌓인다(qa 11-23 · 11-10 「79%→122%」 꼴)
    shut = turnover.day_slot_vol(proxy, [u["code"] for u in cand], day, slot) if hm >= close else {}
    rows, seen = [], 0
    for u in cand:
        q = quotes.get(u["code"]) or {}
        if hm >= close:                                  # 장 뒤 — 마감 칸 값(없으면 못 잼 · 지금 시세로 대신하지 않는다)
            vol, value, price = shut.get(u["code"]) or (None, None, None)
        else:
            vol, value, price = q.get("volume"), q.get("value"), q.get("price")
        if vol is None:
            continue
        seen += 1
        fcap, turn = turnover.calc(price, value, fl.get(u["code"]))
        st, src = None, None
        pv = prev1.get(u["code"])
        if pv:
            sp, src = round(vol / pv * 100), "1m"
        else:
            try:
                st = proxy.vol_same_time(u["code"])
            except Exception:
                st = None
            sp = round(st["today"] / st["prev"] * 100) if st and st.get("today") is not None and st.get("prev") else None
            src = "5m" if sp is not None else None
        by = [k for k, ok in (("turn", turn is not None and turn >= t_pct), ("prev", sp is not None and sp >= p_pct)) if ok]
        if by:
            rows.append({"code": u["code"], "name": u["name"], "market": u["market"], "cap": u["cap"],
                         "price": q.get("price"), "pct": q.get("pct"), "vol": vol, "floatCap": fcap,
                         "turn": turn, "prevSamePct": sp, "prevVol": pv, "prevSrc": src, "upto": slot if src == "1m" else (st.get("upto") if st else None), "by": by})
    rows.sort(key=lambda r: (-(r["pct"] if r["pct"] is not None else -999), -(r["cap"] or 0)))
    return {"rows": rows, "candidates": len(cand), "quoted": seen, "etfOut": etf, "floatKnown": sum(1 for u in cand if fl.get(u["code"])),
            "slot": slot, "prev1m": len(prev1), "turnPct": t_pct, "prevSamePct": p_pct, "capMinEok": cap_min,
            "at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")}


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
