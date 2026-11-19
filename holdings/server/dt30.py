# -*- coding: utf-8 -*-
"""단타 30 판 — 평일 09:06 단타 상위 30 을 그날 판으로 굳히고 30분마다 값을 적는다 · 30거래일 (2026-11-11).

재권님(시황분석1 창 17:4x) — 「단타 목록 상위 30개를 소팅해서 9시 6분에 배수(매수)하고 9시반 10시 등 30분 단위로 2시까지 가격 추적하도록
셋팅해줘」 → 「위에 날짜도 넣어줘 30일 추적가능하도록」 → 「관심을 제외하고 지난 20일의 정보가 필요해」(18:0x) · 서버 몫은 작업우선순위가
개발2 에 배분(18:15) → 안에 「시가총액순이 아니고 칩이 많이 걸린순으로 해줘」 · 「칩이 많이 걸리고 등락이 높고 시총이 높은순」(18:1x) → 「단타칩에 걸리는 우선순위 소팅하는룰 체크해서 그룰대로 하면되」 → 「칩수가 많은순 초반상승이높은순 시총순 이렇게 해서 올려」(19:1x).
화면은 Insight 「종목 고르는 룰」(company-setup/js/strategy-dt30.js · 시황분석1)이 읽는다.

    단타       아래 OV_CHIPS 중 **하나라도** 든 종목(재권님 18:5x 「100개까지」 — 홈 「단타」 는 둘 이상 · 화면이 칩을 끄고 켜며 다시 셈).
               칩 재료는 홈과 같다(holdings/js/home.js 의 OV_CHIPS · ovList).
               재료는 화면이 받는 서버 값 그대로 — 관심 · 수급(watchlist 문서 · 자동 묶음이 수급) · 프리장(pre_flow) · VI·급등(intraday_alerts) ·
               매수(「매수」 판 rows 전부) · 초반상승(open_rise) · 장외(순위 목록 시세의 regPct > 0 · 11-18 더함 — 서버가 평일 07:30~15:30 비워 아침 판에는 보통 안 든다).
               관심 · 프리장 · 매수는 시가총액 CAP_MIN_EOK 억원 아래를 뺀다(화면 capBelowMin · 시가총액을 모르면 안 뺀다)
               **화면과 이 파일 두 곳에 셈이 있다** — 값 한 곳으로 모으는 것은 개발1 카드 「관심 아래 칩 룰 값 한 곳」(화면이 서버를 받는 쪽)
    차례       칩 수 많은 순 → 초반상승(첫 5분봉 시가 대비 % · rise) 높은 순 → 시가총액 큰 순 — 상위 TOP_N
               (재권님 19:1x 「칩수가 많은순 초반상승이높은순 시총순 이렇게 해서 올려」 · 초반상승에 안 든 종목은 같은 칩 수 안에서 뒤)
               홈 「단타」 칩은 칩 수 → 시가총액이다 — 이 판만 초반상승을 둘째로 둔다
    VI 값     rows[].viPx {at, px, src 「vi」(VI 발동가) | 「1m」(그 분 1분봉 시가)} | null — VI 없음 · 못 잼 · 매수 시점 「VI 발동」 고르기용
               (재권님 「매수 타이밍을 9시1분 과 vi발동 두개를 고를수 있게 해줘. 그것에 맞춰서 차익도 달라지게」 11-18 19:2x · 차익 셈은 화면)
    09:01 값   rows[].px1 {at, px, src 「1m」 | 「now」} | null — 첫 1분봉(여는 시각 ~ +1분) 종가 · 1분봉이 없으면 그때 현재가 · 그것도 없으면 null ·
               지난 판은 1분봉이 남은 날(11-12 부터)만 읽을 때 채움 — 재권님 「9시 1분 등락도 넣어줘 이쯤 살거니깐」(11-18 19:1x) · meta.px1At
    N분 뒤 값  rows[].pxMin {"1"~"5": {at, px, src} | null} · meta.pxMinAt {"1": "HH:MM" …} — 정규장 여는 시각 + N분의 값(그 분 1분봉 종가 ·
               없으면 그때 현재가 src 「now」 · 못 재면 null) · px1 은 pxMin "1" 과 같은 값 — 재권님 「사는 시간도 쓸수있게 해줘 9시 1분~ 5분 사이에 살거야」(11-19 12:2x)
               늦게 여는 날(수능 10:00)은 여는 시각 + N분(10:01~10:05) — 11-19 「응 해줘」
    수급       rows[].flow {HHMM: {ff, pg, fr, inst, at} | null} — 30분 칸마다 그때 외국계 창구(주) · 프로그램(원) · 외국인 · 기관 추정가집계(주) 순매수를 적어 굳힘 ·
               rows[].flowNow · meta.flowNowAt — 그날 판(안 끝남)은 09:00 뒤 FLOW_NOW_SEC 마다 지금 값 · 못 받은 칸 · 지난 시각은 null(못 잼) — 묶음 ③
    칩 시각    rows[].chipAt {칩: "HH:MM"} — 그 칩이 그날 판의 그 줄에서 처음 보인 시각 — 칩이 생긴 때가 아니라 판이 처음 본 때다(판을 짓는 08:00 ·
               다시 세는 1분마다 · 늦게 나온 칩은 채운 때 — 08:00 전에 이미 있던 칩은 「08:00」 · 서버가 늦게 뜨면 그 시각) · 다시 세어 빠진 칩은 지운다 ·
               지난 날 다시 센 판은 칸이 없다(그때 언제 붙었는지 기록이 없다) — 묶음 ② 재권님 「응 만들어」(11-18 18:0x)
    처음 시각  rows[].viAt · surgeAt — VI · 급등이 그날 처음 난 시각(HH:MM:SS · 없으면 null) · 오늘 판은 VI · 급등 알림이 본 시각(급등은 이 서버가 처음 본 때) ·
               지난 날 다시 센 판은 VI 는 KIS VI 현황의 발동 시각 · 급등은 5분봉이라 그 봉 시작 「HH:MM~」(surgeApprox true) — 묶음 ① 재권님 「응 만들어」(11-18 18:0x)
    하위 칩    rows[].subs {칩: [하위]} — VI·급등: VI · 급등 / 매수: ①~④(「매수」 판 tier) / 관심: 든 묶음 이름(자동 묶음 빼고)
    칩 이름    rows[].chips 는 그때 걸린 칩 이름 전부(셈에 안 드는 볼린저 · 현재상승도 적는다 — 시황분석1 「관심 하위의 룰들」)
    매수가     09:06 그때 현재가(buy) — 시세는 fetch_quotes_multi(캐시 먼저 · 30종목씩 묶음)
    지금 값    그날 판(closed false)은 주소가 부를 때 rows[].now(현재가) · nowAt · meta.refreshMs(다시 받을 주기 · 서버 값) — 14:00 칸을 다 적으면 closed true 로 굳힘
    값        px{HHMM} — TIMES 각 시각에 끝난 5분봉 종가(DB candles · 그 봉을 끝난 뒤 받았으면) · 없으면 그때 현재가(pxSrc 「now」)
    저장      market.db dt30(날 · 판 JSON) — 쓰기 되는 서버(8765)만 · 한 번 굳힌 날은 다시 안 굳힌다 · DAYS_KEEP 거래일 넘으면 지운다
    주소      GET /api/kis/dt30?day=YYYYMMDD — day 를 빼면 마지막 날 · meta.days 는 남긴 날(최근 먼저)

하락 뺌    전일 종가 대비 등락률(pct)이 DROP_BELOW_PCT 아래인 종목은 판에 안 넣는다 — 재권님 「단타에 하락인 종목은 필요없어」 →
               「거래량 많은 종목중에 하락인건 제외한다는 룰 넣어봐」(11-12) · 09:35 굳히기 전까지 1분마다 다시 셀 때 그때 값으로 넣고 뺀다 ·
               굳힌 뒤 내려간 종목은 그대로 둔다(이미 산 값) · 등락률을 모르면 안 뺀다(못 잼은 하락이 아니다) · 뺀 수는 meta.dropDown
               판에 들었다가 빠진 종목은 까닭(하락 · 100위 밖으로 밀림 · 칩이 빠짐)과 무관하게 그날 다시 안 넣는다(meta.out) ·
               없다가 조건이 맞게 된 종목은 넣는다 — 재권님 「처음 들었다가 빠지면 제외하고 없다가 값이 적용되는 목록은 넣는다」(11-12 11:3x) →
               「밀린건 넣지 않는다로 룰 만들자」(11-13 · qa 가 09:07↔09:32 판에서 다시 든 18 종목 매수가가 바뀐 것을 찾음)

못 받은 칩은 meta.missing 에 이름으로 남긴다(「0 종목」 과 「못 받음」 을 가른다).
"""
import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone

import dart            # 시가총액 문턱(UNIVERSE_MIN_CAP_EOK) 한 곳 — 모듈을 읽을 때 쓴다(dart 는 이 파일을 안 부른다)

KST = timezone(timedelta(hours=9))
TOP_N = 100                  # 재권님 18:5x 「상위 30개면 소팅에 걸리는게 적을수 있으니 지금 100개까지 늘려놔」
BUY_AT = (8, 0)              # 판 짓기 시작 — 재권님 「단타 목록은 8시부터 계속 리스트 나오게 해줘」(11-18 · 시황분석 창 · 작업우선순위 경유 · 안에 「응」 17:0x) · 그 전 09:01 — 재권님 「9시 6분에 배수」 → 「9시 5분에 무조건 갱신」(11-12 09:1x) → 「9시 1분에 바로 단타 리스트 뜨도록 … 못가져온 값은 못가져온대로 … 무슨값인지만 인지되도록」(09:2x · 작업우선순위 경유) · 빠진 칩은 meta.missing · 들어오면 patch_late 가 채움
TRACK_FROM = (9, 30)         # 값 적는 첫 시각
TRACK_TO = (14, 0)           # 값 적는 끝 시각 — 「2시까지」
TRACK_STEP = 30              # 분 — 「30분 단위로」
BAR_MIN = 5                  # 5분봉 길이(분)
BUY_LATE = (10, 30)          # 굳히는 시각 — 재권님 「굳히기는 10시반으로」(11-18 · 안에 「응」 17:0x) · 그 전 「9시 35분에 굳히는걸로」(11-12 09:2x) · BUY_AT 부터 이때까지 판을 다시 세고 이 뒤로는 줄을 안 바꾼다 · 서버가 이 뒤에 뜨면 그날 판은 안 짓는다
OPEN_AT = (9, 0)             # 정규장 첫 값 — 그 전(BUY_AT ~ 09:00)에 든 종목의 매수가는 이 시각 정규장 시가(rows[].buyWait 가 그 표시 · 09:00 뒤 첫 다시 세기에 채움)
OUT_FROM = (9, 1)            # 「한 번 빠지면 그날 다시 안 넣음」 을 세기 시작하는 때 — 장 전에는 프리장 값이 오가며 줄이 자주 바뀐다(11-18 안 「응」)
PRE_WAIT = ("초반상승",)   # 09:00 전에는 값이 날 수 없는 칩 — 못 받음(missing)이 아니라 기다림(meta.wait)
# 「매수」 는 어림을 08:00 부터 — 재권님 「매수 목록중에 초반에 받을수 있는게 있지않나? 프리장에서」 → 「아니 매수는 그전에 받을수 있는 값 받으라고 했는데」
# (11-18 17:2x · 시황분석1 경유). 장 전은 프로그램만(early_buy pre) — 외국계 창구는 거래소(J) 창구라 장 전 체결이 없어 오늘 값이 없고 어제 값이 올 수 있다.
# 어림을 하나도 못 받으면 그때만 wait 에 「매수」(못 받음 아님) · 가집계(①~④)는 09:30 첫 입력이라 그대로 기다림(patch_late 가 채움)
# VI·급등 은 08:00 부터 — 재권님 「8시부터 받을수 있는 정보는 다 받으면 좋을거같은데. 단타 칩들은 정보가 빠르게 들어올수록 좋아」 →
# 장 전 VI(KIS VI 현황 08시대 — 넥스트 프리장으로 보임 · 11-19 08시대에 잴 것) · 장 전 급등(통합 등락률 순위 · 전일 종가 대비 SURGE_PCT 이상)에 「응 해줘」
# (11-18 17:2x · 시황분석1 경유). 텔레그램 알림(intraday_alerts)은 정규장만 그대로 — 단타 판만 pre_vi_surge 로 따로 읽는다 · 매수 어림(외국계 창구 · 프로그램)도 안 부른다
PAST_BUY_AT = (9, 1)         # 지난 날 다시 세기(rebuild)의 기준 시각 — 11-18 전 판 셈 그대로 둔다(지난 날을 10:30 기준으로 다시 세지 않는다 · 지시 밖)
PAST_LATE = (9, 35)          # 〃 VI·급등 창 끝
DAYS_KEEP = 30               # 「30일 추적」
CAP_MIN_EOK = dart.UNIVERSE_MIN_CAP_EOK   # 시가총액 문턱(억원) — 대상 목록 문턱 그대로(한 곳 · 개념정의 검수 11-12) · 화면 RANK_MIN_CAP_EOK 와 같은 값(두 곳 · 위 「화면과 이 파일」) · 3천억 → 5천억 재권님 「응」(11-12)
NOW_RISE_PCT = 3.0           # 「현재상승」 — 시가 대비 %(화면 NOW_RISE_PCT 와 같은 값 · 칩 이름 적기에만 씀)
DROP_BELOW_PCT = 0.0         # 하락 뺌 — 전일 종가 대비 이 % 아래는 판에 안 넣는다(0 이면 보합은 남긴다 · 재권님 11-12)
TICK = 20
NX_AT = (8, 5)               # 다음 날 프리장 값 시각 — 재권님 「이종목들 내일 프리장에 8시 5분에 얼마인지 체크해서 넣어줘 … 어제에 프리장 8시5분 이라고 칸이 있어야 되고」(11-18 16:3x · 시황분석1 창 · 작업우선순위 경유)
NX_NOW_UNTIL = (8, 20)       # 이때까지는 넥스트레이드 현재가(src 「now」) · 넘으면 그날 08:05 1분봉 종가(src 「1m」)
NX_SKIP = ((8, 55), (9, 40)) # 1분봉 되찾기를 미루는 때 — 판 굳히기 · 다시 세기(BUY_AT ~ BUY_LATE)에 KIS 몫을 비켜선다
OV_CHIPS = ("관심", "프리장", "VI·급등", "장외", "매수", "초반상승", "수급")   # 단타 셈에 드는 칩 — 화면 OV_CHIPS 차례 · 11-18 뒤 판은 「수급」 이 「관심」 으로 합쳐져 안 나온다(지난 날 판에는 남는다)

_SCHEMA = "CREATE TABLE IF NOT EXISTS dt30 (day TEXT PRIMARY KEY, saved_at TEXT, board TEXT NOT NULL)"
_status = {"frozen": None, "error": None}


def _now():
    return datetime.now(KST)


_late = {"day": None, "at": 0.0, "min": 0}


def late_min(proxy, now=None, day=None):
    """그날 정규장이 보통 날보다 몇 분 늦게 여나 — 0 보통 · 수능(10:00)이면 60. market_hours 표 한 곳 · 못 읽으면 0(보통 날로 본다) · 5분 둘레로 다시 읽음.
    늦게 여는 날은 판의 정규장 시각들(OPEN_AT · OUT_FROM · BUY_LATE · 값 적는 시각)을 그만큼 뒤로 민다 —
    재권님 「가로 해줘」(11-19 08:3x · (가) 1시간 미룸 — 매수가 10:00 시가). BUY_AT(판 짓기 08:00) · 지난 날 다시 세기(PAST_*)는 그대로."""
    now = now or _now()
    other = day is not None and day != now.strftime("%Y%m%d")     # 지난 날(다시 세기) — 그날 표를 읽고 캐시는 안 씀
    day = day or now.strftime("%Y%m%d")
    if not other and _late["day"] == day and time.time() - _late["at"] < 300:
        return _late["min"]
    m = 0
    try:
        import market_hours
        t = market_hours.today(proxy, day=day, now=now)
        if t.get("open") is not False:
            a, u = t["reg"][0], t["usual"]["reg"][0]
            m = max(0, (int(a[:2]) * 60 + int(a[2:])) - (int(u[:2]) * 60 + int(u[2:])))
    except Exception:
        m = 0
    if not other:
        _late.update(day=day, at=time.time(), min=m)
    return m


def _sh(hm, off):
    """(시, 분) 을 off 분 뒤로 — (시, 분)."""
    return divmod(hm[0] * 60 + hm[1] + off, 60)


def times(off=0):
    """값 적는 시각들 ['0930', '1000', … '1400'] · off 분 늦게 여는 날은 그만큼 뒤로."""
    out, m = [], TRACK_FROM[0] * 60 + TRACK_FROM[1] + off
    while m <= TRACK_TO[0] * 60 + TRACK_TO[1] + off:
        out.append("%02d%02d" % divmod(m, 60))
        m += TRACK_STEP
    return out


def _six(code):
    code = str(code or "")
    return code if code.isdigit() and len(code) == 6 else None


def chips_now(proxy, cfg, early=True, pre=False):
    """지금 걸린 칩 — ({코드: {이름, 칩 집합}}, 못 받은 칩 이름 목록, 시가총액 {코드: 억원}).
    pre — 09:00 전: PRE_WAIT 칩(매수 · 초반상승)과 볼린저는 안 부르고 못 받음에도 안 넣는다(build 가 meta.wait 로) · VI·급등 은 장 전 것(pre_vi_surge)."""
    import dart, docstore, intraday_alerts, open_rise, pre_flow, signal_watch
    uni = dart.universe_rows(None)
    cap = {r["stock_code"]: r["market_cap"] for r in uni}
    mkt = {r["stock_code"]: r["market"] for r in uni}
    try:                                   # 순위 목록 밖은 KIS 종목 마스터(nxt_pre 가 받아 둔 전 종목 시장 표)로 채운다
        import nxt_pre
        for c, m in list(nxt_pre.MARKET_OF.items()):
            mkt.setdefault(c, str(m).upper())
    except Exception:
        pass
    small = lambda c: cap.get(c) is not None and cap[c] < CAP_MIN_EOK
    hit, missing = {}, []

    def put(code, name, chip, sub=None, at=None, px=None):
        code = _six(code)
        if code:
            g = hit.setdefault(code, {"name": name or "", "chips": set(), "subs": {}})
            g["chips"].add(chip)
            if sub and sub not in g["subs"].setdefault(chip, []):
                g["subs"][chip].append(sub)
            if not g["name"] and name:
                g["name"] = name
            if at and chip == "VI·급등" and sub in ("VI", "급등"):
                _first_at(g, sub, at, px)

    try:
        watch_chips(docstore.read_doc("watchlist"), put, small)
    except Exception:
        missing.append("관심")
    try:
        pf, _, _ = pre_flow.fetch(proxy, cfg)
        if pf is None:
            missing.append("프리장")
        for r in (pf or {}).get("rows") or []:
            if not small(r.get("code")):
                put(r.get("code"), r.get("name"), "프리장")
    except Exception:
        missing.append("프리장")
    try:                                   # 장외 — 홈 「장외」 칩과 같은 값(순위 목록 시세의 regPct · 정규장 종가 대비) · 오른 것만 · 시가총액 문턱 아래 뺌
        # 재권님 「한곳에서 받는건데 이미 받은값은 그걸 가져와야 하고」(11-18 17:3x · 시황분석1 경유) — 시세 캐시를 함께 탄다(PRICE_CACHE_TTL)
        # 서버가 평일 07:30~15:30 장외 값을 비우므로(kis_proxy after_cleared) 08:00 ~ 10:30 판에는 보통 안 든다
        if not proxy.after_cleared():
            names = {r["stock_code"]: r["name"] for r in uni if not small(r["stock_code"])}   # 문턱 아래는 처음부터 안 물음(KIS 몫)
            q, _ = proxy.fetch_quotes_multi(cfg, list(names), max_age=proxy.PRICE_CACHE_TTL)
            for c, v in q.items():
                if v.get("regPct") is not None and v["regPct"] > 0 and not small(c):
                    put(c, names.get(c) or v.get("name"), "장외")
    except Exception:
        missing.append("장외")
    try:
        pre_vi_surge(proxy, cfg, _now().strftime("%Y%m%d"), put, pre)
    except Exception:
        missing.append("VI·급등")
    if pre:
        if early and early_buy(proxy, cfg, [c for c in hit if not small(c)], put, pre=True) is not None:
            missing.append("매수어림")                 # build 가 meta.early · approx 로
        else:
            missing.append("매수대기")                 # 장 전에 어림을 하나도 못 받음 — build 가 wait 로
        return hit, missing, cap, mkt
    try:
        for it in intraday_alerts.today().get("items") or []:
            put(it.get("code"), it.get("name"), "VI·급등", "VI" if it.get("kind") == "vi" else "급등", at=it.get("t"), px=it.get("price"))
    except Exception:
        missing.append("VI·급등")
    try:
        jd, _ = proxy.fetch_joint_buy(cfg)
        if jd is None or not jd.get("rows"):
            missing.append("매수")
        for r in (jd or {}).get("rows") or []:
            if not small(r.get("code")):
                put(r.get("code"), r.get("name"), "매수", "①②③④"[r["tier"] - 1] if r.get("tier") in (1, 2, 3, 4) else None)
    except Exception:
        missing.append("매수")
    if "매수" in missing and early and early_buy(proxy, cfg, [c for c in hit if not small(c)], put) is not None:
        missing.remove("매수")
        missing.append("매수어림")                     # build 가 meta.early 로 옮긴다 — 못 받은 칩이 아니다
    try:
        b, _ = open_rise.fetch(proxy)
        if b.get("phase") in ("pending", "nodata"):
            missing.append("초반상승")
        for r in b.get("rows") or []:
            put(r.get("code"), r.get("name"), "초반상승")
            if _six(r.get("code")) and r.get("pct") is not None:
                hit[r["code"]]["rise"] = r["pct"]          # 첫 5분봉 시가 대비 % — 줄 세우기 둘째 열쇠
    except Exception:
        missing.append("초반상승")
    try:
        day = _now().strftime("%Y%m%d")
        for it in signal_watch.today_lows(proxy).get("items") or []:
            if str(it.get("ts", ""))[:8] == day and _six(it.get("code")) in hit:
                hit[it["code"]]["chips"].add("볼린저")      # 셈에 안 듦 — 이름만 적는다
    except Exception:
        pass
    return hit, missing, cap, mkt


def _first_at(g, sub, at, px=None):
    """VI · 급등 처음 시각을 줄에 — viAt · surgeAt(HH:MM:SS · 가장 이른 것). 단타 판 묶음 ① — 재권님 「응 만들어」(11-18 18:0x).
    VI 는 그때 발동가도(viPrice) — 매수 시점 「VI 발동」 고르기(재권님 「매수 타이밍을 9시1분 과 vi발동 두개를 고를수 있게」 11-18 19:2x)."""
    k = "viAt" if sub == "VI" else "surgeAt"
    if not g.get(k) or at < g[k]:
        g[k] = at
        if sub == "VI":
            g["viPrice"] = px


_pre_hits = {}        # 날 → {코드: (이름, {하위})} — 장 전(08:00~09:00)에 본 VI · 급등 · 09:00 뒤에도 그날 판 칩으로 남긴다(서버 재시작이면 VI 는 다시 읽고 급등은 잃음)


def pre_vi_surge(proxy, cfg, day, put, pre):
    """장 전 VI · 급등을 「VI·급등」 칩으로 — 정규장 것은 intraday_alerts 몫(chips_now). 그날 처음 부를 때와 장 전 동안은 VI 현황을 다시 읽는다.
    VI — KIS VI 현황(상승 · 그날 · 최근 30건)에서 발동 시각이 09:00 전인 것 · 급등 — 장 전에만 통합 등락률 순위(전일 종가 대비) SURGE_PCT 이상."""
    import intraday_alerts as ia
    seen = _pre_hits.setdefault(day, {})
    for k in [d for d in _pre_hits if d != day]:
        _pre_hits.pop(k, None)
    if pre or "_vi" not in seen:
        for r in ia._vi_rows(proxy, day):
            h = (r.get("cntg_vi_hour") or "").strip().zfill(6)
            code = _six((r.get("mksc_shrn_iscd") or "").strip())
            if code and h < "%02d%02d00" % _sh(OPEN_AT, late_min(proxy)):
                v = seen.setdefault(code, [(r.get("hts_kor_isnm") or "").strip(), set(), {}, None])
                v[1].add("VI")
                t = "%s:%s:%s" % (h[0:2], h[2:4], h[4:6])
                if not v[2].get("VI") or t < v[2]["VI"]:
                    v[2]["VI"] = t
                    try:
                        v[3] = float(r.get("vi_prc") or 0) or None    # VI 발동가
                    except (TypeError, ValueError):
                        v[3] = None
        seen["_vi"] = True
    if pre:
        for r in proxy.fetch_movers(cfg, "up", "all") or []:
            code = _six(r.get("code"))
            if code and r.get("pct") is not None and r["pct"] >= ia.SURGE_PCT:
                v = seen.setdefault(code, [r.get("name") or "", set(), {}, None])
                v[1].add("급등")
                v[2].setdefault("급등", _now().strftime("%H:%M:%S"))      # 이 서버가 처음 본 때(넘은 때가 아니다 · 순위 캐시만큼 늦을 수 있다)
    for code, v in seen.items():
        if code != "_vi":
            for sub in sorted(v[1]):
                put(code, v[0], "VI·급등", sub, at=(v[2] if len(v) > 2 else {}).get(sub), px=v[3] if len(v) > 3 and sub == "VI" else None)


def watch_chips(doc, put, small, merged=True):
    """관심 목록 문서 → 칩.
    merged(오늘 판 · 11-18 뒤) — 자동 관심 룰에 든 종목만 「관심」(하트 종목은 안 씀 · 하위 없음 · 시가총액 문턱은 자동 룰 그대로) —
        재권님 「관심 하트 없애고 자동으로 관심」 · 「응 맞아」(11-18 16:4x · 작업우선순위 경유 · 안에 「응」 17:0x)
    merged=False(지난 날 다시 세기 · 11-18 전 셈) — 하트 종목은 「관심」(하위 = 든 묶음 이름 · 시가총액 CAP_MIN_EOK 아래 뺌) · 자동 묶음은 「수급」."""
    if not isinstance(doc, dict):
        raise ValueError("관심 문서 없음")              # 못 읽음을 0 종목으로 두지 않는다(qa 11-11)
    auto = set((doc.get("auto") or {}).keys()) if isinstance(doc.get("auto"), dict) else set()
    if merged:
        names = {it.get("code"): it.get("name") for it in doc.get("items") or [] if isinstance(it, dict)}
        for c in sorted(auto):
            a = doc["auto"].get(c)
            put(c, names.get(c) or (a.get("name") if isinstance(a, dict) else None), "관심")
        return
    grp = [(g.get("name"), set(g.get("codes") or [])) for g in doc.get("groups") or []
           if isinstance(g, dict) and g.get("id") != "auto"]          # 관심 하위 = 그 종목이 든 묶음(자동 묶음은 수급이라 뺀다)
    for it in doc.get("items") or []:
        if isinstance(it, dict):
            c = it.get("code")
            if c in auto:
                put(c, it.get("name"), "수급")
            elif not small(c):
                put(c, it.get("name"), "관심")
                for gn, gc in grp:
                    if c in gc:
                        put(c, it.get("name"), "관심", gn)


def watch_at(day):
    """day 09:01 직전의 관심 목록 문서 — 보드 문서 저장 기록(docstore 의 git · 2026-10-26 부터)에서 꺼낸다. 기록이 없으면 None."""
    import subprocess, docstore
    at = "%s-%s-%s %02d:%02d:00 +0900" % (day[:4], day[4:6], day[6:], PAST_BUY_AT[0], PAST_BUY_AT[1])
    r = subprocess.run(["git", "log", "-1", "--before=" + at, "--format=%H", "--", "watchlist.json"],
                       cwd=docstore.DOC_ROOT, capture_output=True, timeout=10)
    h = r.stdout.decode().strip() if r.returncode == 0 else ""
    if not h:
        return None
    r = subprocess.run(["git", "show", h + ":watchlist.json"], cwd=docstore.DOC_ROOT, capture_output=True, timeout=10)
    if r.returncode != 0:
        return None
    d = json.loads(r.stdout.decode("utf-8"))
    return d.get("data") if isinstance(d, dict) and isinstance(d.get("data"), dict) and "items" not in d else d


def chip_rules(proxy, merged=True):
    """화면 룰 표에 내줄 칩 룰 값 — 자동 관심 룰은 auto_watch 룰 문서 한 곳에서 읽는다.
    merged(11-18 뒤 판) — 「관심」 = 자동 관심 룰 · merged=False(지난 날) — 관심은 이 파일 문턱 · 수급 = 자동 관심 룰."""
    out = {"하락뺌": {"dropBelowPct": DROP_BELOW_PCT}}
    if not merged:
        out["관심"] = {"capMinEok": CAP_MIN_EOK, "what": "하트 누른 종목 · 하위는 든 묶음 이름 · 자동 묶음은 수급"}
    key = "관심" if merged else "수급"
    try:
        import auto_watch
        r, src = auto_watch.rules(proxy)
        out[key] = dict(r, src=src, what="자동 관심 룰에 든 종목(하트 안 씀)") if merged else dict(r, src=src)
    except Exception:
        out[key] = None                                 # 못 읽음 — 빈 룰로 두지 않는다
    return out


EARLY_WORKERS = 6


def early_buy(proxy, cfg, codes, put, pre=False):
    """「매수」 판이 아직 없을 때(외 · 기 장중 가집계가 09:30 · 10:00 에 처음 나온다) 후보 종목의 외국계 창구 순매수 · 종목 프로그램 순매수가
    둘 다 양수면 「매수」 어림(하위 「어림」)으로 넣는다 — 재권님 「프로그램은 받을수 있지않나? 외국계창구랑」 · 「차트에서 읽고 있잖아」(11-12 09:1x).
    값은 큰 차트 바닥 줄이 읽는 것과 같은 함수(fetch_investor_member 의 foreignFirms.net · _program_net_today) — 새 받는 길을 만들지 않는다.
    매수 판이 서면 patch_late 가 이 어림을 걷고 그 판으로 바꾼다. 넣은 종목 수(못 받으면 None)."""
    from concurrent.futures import ThreadPoolExecutor

    now_hms = _now().strftime("%H:%M:%S")

    def one(c):
        try:
            if pre:
                # 장 전(09:00 전) — 프로그램만 · 외국계 창구는 거래소 창구라 장 전 오늘 값이 없다(어제 값이 올 수 있어 안 부름) — 재권님 11-18 17:2x
                pg = proxy._program_net_today(cfg, c)
                at = (getattr(proxy, "_program_at", {}) or {}).get(c)
                if pg is not None and (not at or at > now_hms):
                    pg = None                          # 마지막 체결 줄이 지금보다 늦다 = 어제 줄(체결 줄에 날짜 칸이 없다) — 못 잼
                return c, None, pg
            m = proxy.fetch_investor_member(cfg, c) or {}
            fn = (m.get("foreignFirms") or {}).get("net")
            pg = proxy._program_net_today(cfg, c)
        except Exception:
            return c, None, None
        return c, fn, pg
    try:
        with ThreadPoolExecutor(EARLY_WORKERS) as ex:
            got = list(ex.map(one, codes))
    except Exception:
        return None
    if codes and all(fn is None and pg is None for _, fn, pg in got):
        return None                                    # 하나도 못 받았다 — 「어림」 으로 두지 않고 못 받은 칩으로 남긴다(qa 11-12 · KIS 몰림 때)
    n = 0
    for c, fn, pg in got:
        if pre and pg is not None and pg > 0:
            put(c, None, "매수", "어림")               # 장 전 어림 — 프로그램 순매수만(meta.earlyNote)
            n += 1
        elif fn is not None and fn > 0 and pg is not None and pg > 0:
            put(c, None, "매수", "어림")
            n += 1
    return n


MIN_CHIPS = 2                 # 단타 목록 문턱 — 단타 셈 칩 이 수 이상 · 홈 「단타」 · 투자 전략 단타 칩 · 단타 판(build) 셋 다 이 값(meta.minChips) —
                              # 재권님 안 「단타 목록을 서버 한 곳에서 셈해 … 문턱은 홈처럼 칩 둘 이상으로」 에 「응 이거 바로 해야할거같아」(11-18 17:4x · 시황분석1 창 · 작업우선순위 경유)
MIN_CHIPS_LATE = 1            # 장이 늦게 여는 날(수능 · 정규장 10:00 · 넥스트레이드 프리마켓 없음) 문턱 — 08시대 칩이 관심 하나뿐이라 둘 문턱이면 목록 · 판이 다 빔
                              # 재권님 「암것도 안보이네 나로 해줘」(11-19 08:22 · 작업우선순위 창 · (나) 칩 하나도 보이게)


def min_chips(proxy, now=None):
    """그날 단타 문턱 한 곳 — 보통 MIN_CHIPS · 정규장이 보통 날보다 늦게 여는 날(late_min > 0)은 MIN_CHIPS_LATE.
    「늦게 여는 날인가」 는 late_min 한 곳(개념정의 덧 11-19) · 못 읽으면 0 이라 MIN_CHIPS."""
    return MIN_CHIPS_LATE if late_min(proxy, now) > 0 else MIN_CHIPS


LIVE_TTL = 60                 # 단타 목록(live) 캐시(초) — 홈 「단타」 · 단타 판이 같은 셈을 이 나이 안이면 함께 쓴다 · 화면은 롱폴 열쇠 dt30.LIVE_TTL

# 줄 세우기 — 재권님 「응」(11-18 19:3x · 시황분석1 창 · 작업우선순위 경유): 룰 문서 strategy-rules 의 rules.dt30.score
# {칩 이름: 점수, "칩|HH:MM 전": 점수, "칩|HH:MM 이후": 점수} 를 읽어 「점수 합 큰 순 → 초반상승 높은 순 → 시가총액 순」.
# 표가 비었거나 못 읽으면 지금 셈(칩 수 많은 순). 칩 이름은 화면 chipName 과 같게 — 서버 「수급」 은 화면 「자동」 이라 둘 다 받는다.
# 시각 조건은 그 칩이 처음 붙은 때로 가른다 — VI·급등 은 viAt · surgeAt 중 이른 것, 그 밖은 rows[].chipAt. 시각을 모르면 그 조건은 안 셈.
SCORE_ALIAS = {"수급": "자동"}


def score_table(proxy=None):
    """룰 문서의 점수표 — 숫자 값만 남긴 dict · 비었거나 못 읽으면 None."""
    try:
        import docstore
        d = docstore.read_doc("strategy-rules") or {}
        t = ((d.get("rules") or {}).get("dt30") or {}).get("score") or {}
    except Exception:
        return None
    t = {str(k).strip(): float(v) for k, v in t.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    return t or None


def _chip_time(r, chip):
    if chip == "VI·급등":
        ts = [t for t in (r.get("viAt"), r.get("surgeAt")) if t]
        return min(ts) if ts else None
    return (r.get("chipAt") or {}).get(chip)


def score_conflicts(tab):
    """한 칩에 「칩」 점수와 「칩|HH:MM 전/이후」 점수가 함께 적힌 칩 이름 — 재권님 「함께 있을수 없는 값이야 둘중 하나만 기입하도록 해줘」(11-18 20:2x).
    입력은 화면이 하나만 받게 막는다 · 서버는 둘 다 있으면 시각 점수만 쓰고(화면 셈과 같게) 이 목록을 meta.scoreConflict 로 낸다."""
    if not tab:
        return []
    plain = {k.strip() for k in tab if "|" not in k}
    split = {k.partition("|")[0].strip() for k in tab if "|" in k}
    return sorted(plain & split)


VI_SPLIT_AT = (9, 25)        # VI·급등 「09:25 전 · 이후」 나누는 보통 날 시각 — 늦게 여는 날은 late_min 만큼 뒤(meta.viSplit) · 점수표 열쇠 이름은 그대로
                             # 재권님 「응 만들어」(11-19 · 시황분석1 창 · 늦게 여는 날 VI 나누기 옮기기 — 화면만 밀면 서버 점수와 갈림)


def vi_split(off=0):
    """나누는 시각 「HH:MM」 — 보통 09:25 · off 분 늦게 여는 날은 그만큼 뒤."""
    return "%02d:%02d" % _sh(VI_SPLIT_AT, off)


def row_score_by(r, tab, off=0):
    """칩마다의 몫 {칩: 점수} — 칩마다 「칩」 열쇠 또는 맞는 「칩|HH:MM 전/이후」 열쇠(둘 다 적혔으면 시각 열쇠만 · score_conflicts).
    점수가 안 걸린 칩은 안 넣는다. 화면은 끈 칩 몫만 빼서 차례를 세운다 — 셈은 이 한 곳(시황분석1 과 맞춤 11-18 20:3x)."""
    by = {}
    bad = set(score_conflicts(tab))
    for c in r.get("chips") or []:
        total = 0.0
        hit = False
        names = {c, SCORE_ALIAS.get(c, c)}
        for k, v in tab.items():
            name, _, cond = k.partition("|")
            if name.strip() not in names:
                continue
            if not cond:
                if name.strip() in bad:
                    continue
                total += v
                hit = True
                continue
            m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*(전|이후)\s*", cond)
            t = _chip_time(r, c)
            if not m or not t:
                continue
            hm = "%02d:%02d" % _sh((int(m.group(1)), int(m.group(2))), off)   # 열쇠 시각을 늦게 연 분만큼 뒤로(열쇠 이름은 그대로)
            if (t[:5] < hm) == (m.group(3) == "전"):
                total += v
                hit = True
        if hit:
            by[c] = round(total, 4)
    return by


def row_score(r, tab, off=0):
    """그 줄의 점수 합 — row_score_by 의 합."""
    return round(sum(row_score_by(r, tab, off).values()), 4)


def sort_rows(rows, tab, off=0):
    """줄 세우기 한 곳 — tab(점수표)이 있으면 점수 합 · 없으면 칩 수. 앞의 것이 같으면 초반상승 → 시가총액. rows 를 제자리에서 세우고 order 글을 낸다."""
    rise = lambda r: -(r["rise"] if r.get("rise") is not None else -1e9)
    cap = lambda r: -(r["cap"] if r.get("cap") is not None else -1)
    if tab:
        for r in rows:
            r["scoreBy"] = row_score_by(r, tab, off)
            r["score"] = round(sum(r["scoreBy"].values()), 4)
        rows.sort(key=lambda r: (-r["score"], rise(r), cap(r)))
        return "점수 합 큰 순 → 초반상승 높은 순 → 시가총액 순"
    for r in rows:
        r.pop("score", None)
        r.pop("scoreBy", None)
    rows.sort(key=lambda r: (-r["n"], rise(r), cap(r)))   # 재권님 19:1x
    return "칩 수 많은 순 → 초반상승 높은 순 → 시가총액 순"

_live = {"at": 0.0, "pre": None, "data": None, "busy": False}
LIVE_STALE_SEC = 300         # 가진 목록이 이만큼 넘게 묵었으면 바로 내주지 않고 새로 셀 때까지 기다렸다 답한다(초) — 물음이 한동안 없다가 오면
                             # 몇십 분 전 목록이 나갔다(11-19 11:29~12:09 물음 0 → 12:10 에 40분 묵은 목록 · 재권님 「응 해줘」 11-19)
                             # 셈이 수십 초라(11-18 49초) 넘기는 서버의 시간 한도(60초) 안이다

_ext = {"cap": {}, "q": [], "busy": False}   # 순위 목록 밖 종목 시가총액(억원) — {코드: (날, 값 | None)} · 그날 한 번 단건 시세(hts_avls)
EXT_CAP_GAP_SEC = 0.5        # 한 종목 받고 다음까지 — KIS 예산을 몰아 쓰지 않게


def _ext_cap_want(proxy, cfg, codes):
    """순위 목록 밖 종목의 시가총액 {코드: 억원 | None} — 쥔 것만 바로 내고, 그날 아직 안 받은 것은 뒤에서 받는다(다음 셈부터 보임).
    못 받으면 그날은 None(「못 잼」 · 0 아님)."""
    day = _now().strftime("%Y%m%d")
    got = {c: _ext["cap"][c][1] for c in codes if (_ext["cap"].get(c) or (None,))[0] == day}
    need = [c for c in codes if c not in got and c not in _ext["q"]]
    if need:
        _ext["q"].extend(need)
        if not _ext["busy"]:
            _ext["busy"] = True

            def run():
                try:
                    while _ext["q"]:
                        c = _ext["q"].pop(0)
                        try:
                            v = (proxy.fetch_price(cfg, c) or {}).get("marketCap")
                        except Exception:
                            v = None
                        _ext["cap"][c] = (_now().strftime("%Y%m%d"), v)
                        time.sleep(EXT_CAP_GAP_SEC)
                finally:
                    _ext["busy"] = False

            threading.Thread(target=run, daemon=True, name="dt-ext-cap").start()
    return got

_live_lock = threading.Lock()
_calc_lock = threading.Lock()   # 셈은 한 번에 하나 — 셈이 수십 초 걸려(11-18 19:5x 8765 49초) 동시에 온 물음마다 따로 세면 서로 늦춰 넘기는 서버(8764)가 시간 한도에 걸렸다(창구 잼)


def _live_bg(proxy, cfg):
    try:
        with _calc_lock:
            _live_calc(proxy, cfg)
    except Exception:
        pass                                           # 못 셈 — 가진 목록을 그대로 두고 다음 물음 때 다시
    finally:
        with _live_lock:
            _live["busy"] = False


def live(proxy, cfg, force=False):
    """단타 목록 — 캐시가 LIVE_TTL 을 넘었어도 가진 목록을 바로 내주고 뒤에서 한 번만 다시 센다(meta.at 이 그 목록을 센 때).
    가진 목록이 없거나(뜬 직후 · 장 전 ↔ 장중이 바뀜) LIVE_STALE_SEC 넘게 묵었거나 force 면 셈을 기다린다 — 그 사이 다른 셈이 끝났으면 그것을 쓴다."""
    ub = getattr(proxy, "upstream_base", None)
    if (ub() if callable(ub) else getattr(proxy, "KIS_UPSTREAM_RAW", "")):
        return _live_calc(proxy, cfg)                  # 넘기는 서버(8764 · 중간 · 세션)는 자기 캐시 없이 상류를 바로 넘긴다 — 낡은 목록을 두 겹으로 쌓지 않게(qa 덧 11-18 · 상류가 이미 바로 답한다)
    now = _now()
    pre = now.hour * 60 + now.minute < OPEN_AT[0] * 60 + OPEN_AT[1] + late_min(proxy, now)
    with _live_lock:
        if not force and _live["data"] is not None and _live["pre"] == pre and time.time() - _live["at"] < LIVE_STALE_SEC:
            if time.time() - _live["at"] >= LIVE_TTL and not _live["busy"]:
                _live["busy"] = True
                threading.Thread(target=_live_bg, args=(proxy, cfg), daemon=True).start()
            return _live["data"]
    t0 = time.time()
    with _calc_lock:
        with _live_lock:
            if _live["data"] is not None and _live["pre"] == pre and _live["at"] >= t0:
                return _live["data"]                   # 기다리는 사이 다른 셈이 끝남
        return _live_calc(proxy, cfg)


def _live_calc(proxy, cfg):
    """단타 목록 한 곳 — 지금 걸린 칩(chips_now) · 시세 · 하락 표시 · 차례. 홈 「단타」 와 단타 판(build)이 같이 쓴다
    — 재권님 「홈에 있는 칩을 단타에도 추가해서 동기화하고 한곳에서 받도록 해」(11-18 17:4x) · 「둘이 동기화해서 홈이든 단테든 한곳에 있어야 하는 정본」.
    {"rows": [{code, name, market, cap, sector, chips, subs, n, price, open, pct, rise, down}], "meta": {at, pre, missing, wait, early, approx, earlyNote, candidates, dropBelowPct, capMinEok, order}}
    rows 는 단타 셈 칩(OV_CHIPS)이 하나 이상 든 종목 전부(하락도 down true 로 남김) · 문턱(둘 이상 · 상위 몇)은 읽는 쪽이 정한다(지금 홈 둘 이상 · 단타 판 하나 이상 · TOP_N)."""
    import company_profile
    now = _now()
    off = late_min(proxy, now)
    pre = now.hour * 60 + now.minute < OPEN_AT[0] * 60 + OPEN_AT[1] + off
    ub = getattr(proxy, "upstream_base", None)
    up = ub() if callable(ub) else getattr(proxy, "KIS_UPSTREAM_RAW", "")   # 자기 자신을 가리키는 상류는 거른다(kis_proxy._resolve_upstream · 창구 덧 11-18)
    if up:
        # 넘기는 서버(메인 8764 · 중간 · 세션)는 셈하지 않고 상류(8765)의 목록을 그대로 받는다 — 셈은 한 곳 ·
        # 관심 문서는 8765 에만 있다(qa 검수 11-18 — 8767 이 자기 폴더 관심 문서를 못 읽어 「관심」 이 빠짐 · 첫 셈 33초)
        import urllib.request
        req = urllib.request.Request(up + "/api/kis/dt-list", headers={"X-KJC-Prio": "low"})
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.loads(r.read().decode("utf-8"))
        data = {"rows": j.get("data") or [], "meta": dict(j.get("meta") or {}, via="상류")}
        with _live_lock:
            _live.update(at=time.time(), pre=pre, data=data)
        return data
    hit, missing, cap, mkt = chips_now(proxy, cfg, pre=pre)
    ov = {c: g for c, g in hit.items() if g["chips"] & set(OV_CHIPS)}
    prices, _ = proxy.fetch_quotes_multi(cfg, list(ov), max_age=proxy.PRICE_CACHE_TTL) if ov else ({}, {})   # 30종목씩 묶음 · 시세 캐시 함께
    sec = company_profile.sectors()
    out = [c for c in ov if cap.get(c) is None]            # 순위 목록 밖 — 시가총액은 단건 시세(그날 한 번) · 업종은 회사 정보 채우기에 맡긴다(11-19 「응 해줘」)
    if out:
        ext = _ext_cap_want(proxy, cfg, out)
        cap = dict(cap, **{c: v for c, v in ext.items() if v is not None})
        company_profile.want_sectors([c for c in out if not sec.get(c)])
    rows = []
    for code, g in ov.items():
        p = prices.get(code) or {}
        chips = set(g["chips"])
        if p.get("open") and p.get("price") and (p["price"] / p["open"] - 1) * 100 >= NOW_RISE_PCT:
            chips.add("현재상승")
        rows.append({"code": code, "name": g["name"] or p.get("name") or "", "market": mkt.get(code), "cap": cap.get(code), "sector": sec.get(code),
                     "chips": [c for c in OV_CHIPS + ("현재상승", "볼린저") if c in chips], "subs": g["subs"], "n": len(chips & set(OV_CHIPS)),
                     "price": p.get("price"), "open": p.get("open"), "pct": p.get("pct"), "rise": g.get("rise"),
                     "viAt": g.get("viAt"), "surgeAt": g.get("surgeAt"),
                     "viPx": {"at": g["viAt"], "px": g.get("viPrice"), "src": "vi"} if g.get("viAt") and g.get("viPrice") else None,
                     "down": p.get("pct") is not None and p["pct"] < DROP_BELOW_PCT})      # 하락 — 모르면 안 뺀다(재권님 11-12)
    tab = score_table(proxy)
    order = sort_rows(rows, tab, off)
    early = ["매수"] if "매수어림" in missing else []
    data = {"rows": rows, "meta": {
        "at": now.strftime("%H:%M:%S"), "pre": pre, "openAt": "%02d:%02d" % _sh(OPEN_AT, off), "lateMin": off, "viSplit": vi_split(off),
        "missing": [c for c in missing if c not in ("매수어림", "매수대기")],
        "wait": (list(PRE_WAIT) + (["매수"] if "매수대기" in missing else [])) if pre else [],
        "early": early, "approx": list(early),
        "earlyNote": "매수 어림 — 09:00 전은 프로그램 순매수 > 0 만(외국계 창구 장 전 값 없음) · 09:00 뒤는 외국계 창구 · 프로그램 둘 다 > 0" if pre and early else None,
        "candidates": len(ov), "chips": [c for c in OV_CHIPS if c != "수급"], "minChips": min_chips(proxy),   # 수급은 11-18 관심으로 합쳐짐(지난 판에만)
        "dropBelowPct": DROP_BELOW_PCT, "capMinEok": CAP_MIN_EOK, "watchRule": "자동",
        "order": order, "score": tab, "scoreConflict": score_conflicts(tab), "ttl": LIVE_TTL}}
    with _live_lock:
        _live.update(at=time.time(), pre=pre, data=data)
    return data


def build(proxy, cfg, day, skip=()):
    """09:06 판 — {day, buyAt, times, rows, meta}. skip — 그날 판에 들었다가 빠진 종목(다시 안 넣음 · 까닭 무관)."""
    lv = live(proxy, cfg, force=True)                  # 단타 목록 한 곳(홈 「단타」 와 같은 셈) — 판은 그 목록에 매수가 · 30분 값 · 손익만 더한다
    lm = lv["meta"]
    pre = bool(lm["pre"]) and _now().strftime("%Y%m%d") == day
    rows, down = [], []
    mc = min_chips(proxy)
    for x in lv["rows"]:
        if x["code"] in skip:
            continue                                   # 들었다가 빠진 종목 — 그날 다시 안 넣음(재권님 11-12 11:3x · 11-13 「밀린건 넣지 않는다」)
        if x["n"] < mc:
            continue                                   # 문턱 — 칩 둘 이상(11-18 · 홈과 같게) · 늦게 여는 날은 하나(min_chips)
        if x["down"]:
            down.append(x["code"])                     # 하락 뺌(재권님 11-12) — 모르면 안 뺀다
            continue
        r = {k: x.get(k) for k in ("code", "name", "market", "cap", "sector", "chips", "subs", "n", "pct", "rise", "open", "viAt", "surgeAt", "viPx")}
        r.update(buy=None if pre else x["price"], px={}, pxSrc={},
                 chipAt={c: _now().strftime("%H:%M") for c in x["chips"]})      # 칩마다 판에 처음 붙은 시각(묶음 ② · 다시 세면 앞 시각 그대로)
        if pre:
            r["buyWait"] = True                        # 09:00 전에 든 종목 — 매수가는 09:00 정규장 시가(refresh 가 09:00 뒤 첫 바퀴에 채움 · 그때까지 buy null)
        rows.append(r)
    missing = lm["missing"] + (["매수어림"] if lm["early"] else [])
    ov = lv["rows"]
    tab = score_table(proxy)
    off = late_min(proxy)
    order = sort_rows(rows, tab, off)
    rows = rows[:TOP_N]
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return {"day": day, "buyAt": "%02d:%02d" % BUY_AT, "times": times(off), "rows": rows, "closed": False,
            "meta": {"rebuilt": False, "missing": list(lm["missing"]), "wait": list(lm["wait"]) if pre else [], "liveAt": lm["at"], "openAt": "%02d:%02d" % _sh(OPEN_AT, off), "lateMin": off, "viSplit": vi_split(off), "watchRule": "자동", "candidates": len(ov), "dropDown": len(down), "downCodes": sorted(down), "dropBelowPct": DROP_BELOW_PCT, "rules": chip_rules(proxy), "minChips": mc,
                     "early": ["매수"] if "매수어림" in missing else [], "earlyNote": "매수 어림 — 09:00 전은 프로그램 순매수 > 0 만(외국계 창구 장 전 값 없음) · 09:00 뒤는 외국계 창구 · 프로그램 둘 다 > 0" if pre else None, "approx": ["매수"] if "매수어림" in missing else [], "topN": TOP_N, "capMinEok": CAP_MIN_EOK,
                     "order": order, "score": tab, "scoreConflict": score_conflicts(tab),
                     "note": "buy 는 굳힌 때(buyAt) 현재가 · pct 는 그때 전일 종가 대비 등락률 · rise 는 초반상승 % (안 들면 null) · px 는 그 시각에 끝난 5분봉 종가(pxSrc now 면 그때 현재가) · "
                             "market KOSPI · KOSDAQ(순위 목록 · 없으면 KIS 종목 마스터 · 둘 다 없으면 null) · cap 억원 · 장외는 09:06 에 비어 안 셈 · 볼린저 · 현재상승은 칩 이름만(셈에 안 듦)"}}


LATE_CHIPS = ("초반상승", "매수")   # 09:06 에 값이 아직 없을 수 있는 칩 — 초반상승은 첫 5분봉이 덜 들어옴 · 매수는 외 · 기 장중 가집계가 09:30 에 처음 나옴
# 재권님 「지금하라고해」(11-12 09:1x · 오늘 판에 두 칩이 빠져 굳음) — 그날 판이 그 칩 없이 굳었으면 값이 나오는 대로 채워 넣고 다시 줄 세운다.
# 초반상승은 09:00 봉이라 09:06 과 같은 값이다. 매수는 채운 시각의 판이라 meta.approx 에 넣고 meta.late 에 시각을 적는다.
# 새로 들어온 종목의 buy 는 09:05 봉 시가(되채우기와 같음 · 없으면 null) · 다른 칩은 채울 때 다시 센 값이다.


def patch_late(proxy, cfg, b):
    """그날 판의 meta.missing 중 LATE_CHIPS 를 값이 나왔으면 채운다. 채운 칩 이름 목록(없으면 빈 목록)."""
    import open_rise
    want = [c for c in LATE_CHIPS if c in (b["meta"].get("missing") or []) + (b["meta"].get("early") or [])]
    if not want:
        return []
    got = {}                                           # 칩 → {코드: (이름, 하위, 초반상승 %)}
    if "초반상승" in want:
        try:
            o, _ = open_rise.fetch(proxy)
            late = _now().hour * 60 + _now().minute >= BUY_LATE[0] * 60 + BUY_LATE[1] + late_min(proxy)
            if o.get("phase") == "done" or (late and o.get("phase") == "pending"):   # 09:30 이 지나도 덜 받았으면 받은 데까지로
                got["초반상승"] = {r["code"]: (r.get("name"), None, r.get("pct")) for r in o.get("rows") or [] if _six(r.get("code"))}
        except Exception:
            pass
    if "매수" in want:
        try:
            jd, _ = proxy.fetch_joint_buy(cfg)
            if jd is not None and jd.get("rows"):
                got["매수"] = {r["code"]: (r.get("name"), "①②③④"[r["tier"] - 1] if r.get("tier") in (1, 2, 3, 4) else None, None)
                              for r in jd["rows"] if _six(r.get("code"))}
        except Exception:
            pass
    if "매수" in want and "매수" not in got and "매수" in (b["meta"].get("missing") or []):
        # 굳힐 때 어림도 못 했던 판(11-12 오늘 판 · 서버가 어림 전 코드였다) — 판 안 종목에 어림을 지금 넣는다
        rows0 = {r["code"]: r for r in b["rows"]}

        def put0(code, name, chip, sub=None):
            r = rows0.get(code)
            if r is not None and chip not in r["chips"]:
                r["chips"].append(chip)
                r["subs"][chip] = [sub] if sub else []
        if early_buy(proxy, cfg, [r["code"] for r in b["rows"] if not (r.get("cap") is not None and r["cap"] < CAP_MIN_EOK)], put0) is not None:
            b["meta"]["missing"] = [c for c in b["meta"]["missing"] if c != "매수"]
            b["meta"]["early"] = sorted(set(b["meta"].get("early") or []) | {"매수"})
            ap = b["meta"].setdefault("approx", [])
            if "매수" not in ap:
                ap.append("매수")
            b["meta"].setdefault("late", {})["매수어림"] = _now().strftime("%H:%M")
            got["매수어림"] = {}
    if not got:
        return []
    # 굳힌 판에 있는 종목에만 칩을 붙인다 — 다시 셀 재료(chips_now)가 필요 없다
    if "매수" in got:                                  # 09:05 어림(하위 「어림」)을 걷고 판 값으로 바꾼다
        for r in b["rows"]:
            if r["subs"].get("매수") == ["어림"]:
                r["subs"].pop("매수", None)
                r["chips"] = [c for c in r["chips"] if c != "매수"]
        b["meta"]["early"] = [c for c in b["meta"].get("early") or [] if c != "매수"]
    rows = {r["code"]: r for r in b["rows"]}
    small = lambda c: rows[c].get("cap") is not None and rows[c]["cap"] < CAP_MIN_EOK
    for chip, m in got.items():
        for code, (name, sub, rise) in m.items():
            r = rows.get(code)
            if r is None or (chip == "매수" and small(code)):                              # 굳힌 판에는 새 종목을 안 넣는다 — 뒤늦게 안 신호로 앞 가격에 산 셈이 되므로(개념정의 덧 11-12)
                continue
            if chip not in r["chips"]:
                r["chips"].append(chip)
                r.setdefault("chipAt", {}).setdefault(chip, _now().strftime("%H:%M"))     # 늦게 나온 칩이 붙은 시각(묶음 ②)
            if sub:
                r["subs"].setdefault(chip, [])
                if sub not in r["subs"][chip]:
                    r["subs"][chip].append(sub)
            if rise is not None:
                r["rise"] = rise
    order = OV_CHIPS + ("현재상승", "볼린저")
    for r in rows.values():
        r["chips"] = [c for c in order if c in r["chips"]]
        r["n"] = len(set(r["chips"]) & set(OV_CHIPS))
    out = list(rows.values())
    tab = score_table(proxy)
    off = late_min(proxy)
    b["meta"]["order"] = sort_rows(out, tab, off)
    b["meta"]["viSplit"] = vi_split(off)
    b["meta"]["score"] = tab
    b["meta"]["scoreConflict"] = score_conflicts(tab)
    b["rows"] = out[:TOP_N]
    for i, r in enumerate(b["rows"]):
        r["rank"] = i + 1
    b["meta"]["missing"] = [c for c in b["meta"]["missing"] if c not in got]
    late = b["meta"].setdefault("late", {})
    for chip in got:
        if chip == "매수어림":
            continue
        late[chip] = _now().strftime("%H:%M")
        if chip == "매수":
            ap = b["meta"].setdefault("approx", [])
            if chip not in ap:
                ap.append(chip)
    b["meta"]["candidates"] = max(b["meta"].get("candidates") or 0, len(rows))
    return list(got)


RESCAN_SEC = 60               # BUY_AT ~ BUY_LATE 동안 판을 다시 세는 간격(초) — 칩 재료(프리장 · 수급 · VI · 매수 어림 …) 캐시 둘레
# 재권님 「궅히지말고 정보가 들어오는대로 개선되게 해줘」 → 「9시 35분에 굳히는걸로」(11-12 09:2x) — 굳히는 시각(BUY_LATE) 전까지는 판을 굳히지 않고
# RESCAN_SEC 마다 칩을 다시 세어 줄을 다시 세운다. 이미 든 종목의 buy 는 처음 든 때 값 그대로 · 새로 든 종목은 든 때 현재가(rows[].buyAt).
# BUY_LATE 뒤로는 줄을 바꾸지 않고 늦게 나온 칩(patch_late)만 채운다 — 30분 값을 적는 동안 종목이 바뀌면 그 칸을 견줄 수 없다.
# 09:30 칸은 굳히기 전에 오므로 그 뒤에 든 종목은 그 칸을 09:30 에 끝난 5분봉 종가로 채운다(track).


def refresh(proxy, cfg, b):
    """그날 판을 지금 들어온 값으로 다시 세운다(종목 · 칩 · 순위). 바뀐 줄 수."""
    out = set(b["meta"].get("out") or [])
    nb = build(proxy, cfg, b["day"], skip=out)
    old = {r["code"]: r for r in b["rows"]}
    now = _now()
    nm = now.hour * 60 + now.minute
    off = late_min(proxy, now)
    if nm >= OUT_FROM[0] * 60 + OUT_FROM[1] + off:
        out |= set(old) - {r["code"] for r in nb["rows"]}        # 판에 있다가 이번에 빠진 종목(하락 · 순위 밖 · 칩 빠짐) — 그날 다시 안 넣음(재권님 11-13) · 09:01 부터 셈(11-18)
    opened = nm >= OPEN_AT[0] * 60 + OPEN_AT[1] + off
    hm = now.strftime("%H:%M")
    changed = 0
    for r in nb["rows"]:
        o = old.get(r["code"])
        if o is not None:
            r["chipAt"] = dict(r.get("chipAt") or {}, **{c: t for c, t in (o.get("chipAt") or {}).items() if c in r["chips"]})   # 앞에 붙어 있던 칩은 그 시각 그대로 · 빠진 칩은 지움
            for k in ("px1", "flow", "flowNow"):
                if k in o:
                    r[k] = o[k]                        # 다시 세도 적어 둔 09:01 값 · 수급은 그대로
        if o is not None and o.get("buyWait") and opened:
            # 09:00 전에 든 종목 — 매수가를 09:00 정규장 시가로(시가를 아직 못 받았으면 지금 값 · 그것도 없으면 다음 바퀴에)
            r["px"], r["pxSrc"] = o["px"], o["pxSrc"]
            if r.get("open") or r.get("buy"):
                r["buy"], r["buyAt"] = r.get("open") or r["buy"], "%02d:%02d" % _sh(OPEN_AT, off)
                r["buySrc"] = "시가" if r.get("open") else "지금 값"
                r.pop("buyWait", None)
            else:
                r["buy"], r["buyWait"] = None, True
            changed += o.get("rank") != r["rank"] or o.get("chips") != r["chips"]
        elif o is not None:
            r["buy"], r["pct"], r["px"], r["pxSrc"] = o["buy"], o["pct"], o["px"], o["pxSrc"]
            r["buyAt"] = o.get("buyAt") or b.get("buyAt")
            for k in ("buyWait", "buySrc"):
                if k in o:
                    r[k] = o[k]
            if o.get("rank") != r["rank"] or o.get("chips") != r["chips"]:
                changed += 1
        else:
            r["buyAt"] = hm
            changed += 1
    changed += len(set(old) - {r["code"] for r in nb["rows"]})
    b["rows"] = nb["rows"]
    if b.get("times") != nb["times"] and not any(o.get("px") for o in old.values()):
        b["times"] = nb["times"]                       # 값 적는 시각 — 아직 한 칸도 안 적었으면 지금 셈(늦게 여는 날 뒤로 민 시각)으로 · 적기 시작했으면 그대로
    late = b["meta"].get("late") or {}
    b["meta"] = dict(nb["meta"], late=late, rescanAt=hm, out=sorted(out))
    return changed


def _bar_close(proxy, day, code, hhmm):
    """hhmm 에 끝난 5분봉 종가 — DB 에 있고(오늘이면) 그 봉을 끝난 뒤 받았을 때만."""
    m = int(hhmm[:2]) * 60 + int(hhmm[2:])
    ts = day + "%02d%02d" % divmod(m - BAR_MIN, 60)
    if day == proxy._minutes_trade_day():
        fresh = proxy._minutes_fresh_upto(code)
        if fresh is None or fresh < m:
            return None
    with proxy._db_lock, proxy.db_conn() as conn:
        r = conn.execute("SELECT close FROM candles WHERE period = '5m' AND code = ? AND ts = ?", (code, ts)).fetchone()
    return r[0] if r else None


def _load(proxy, day):
    try:
        with proxy.db_conn() as conn:
            got = conn.execute("SELECT board, saved_at FROM dt30 WHERE day = ?", (day,)).fetchone()
    except Exception:
        return None
    return (json.loads(got[0]), got[1]) if got else None


def _store(proxy, b):
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        conn.execute("INSERT OR REPLACE INTO dt30 (day, saved_at, board) VALUES (?,?,?)",
                     (b["day"], _now().strftime("%H:%M:%S"), json.dumps(b, ensure_ascii=False)))
        keep = [d for (d,) in conn.execute("SELECT day FROM dt30 ORDER BY day DESC LIMIT ?", (DAYS_KEEP,))]
        if keep:
            conn.execute("DELETE FROM dt30 WHERE day < ?", (keep[-1],))


NOW_OK_MIN = 10              # 5분봉이 없을 때 현재가로 갈음해도 되는 늦음(분) — 넘으면 그 칸은 「없음」(null)


FLOW_NOW_SEC = 300            # 그날 판 줄의 수급 「지금 값」 다시 받는 간격(초) — 재권님 안 「지금 값은 5분마다」(묶음 ③ · 11-18 18:0x 「응 만들어」)
FLOW_WORKERS = 4              # 수급 받기를 겹쳐 묻는 수 — 초당 한도는 kis_get 이 지킨다


def flows(proxy, cfg, codes):
    """종목마다 수급 넷 — {code: {ff, pg, fr, inst, at}} · 못 받은 칸은 null(0 아님).
    ff 외국계 창구 순매수(주 · 거래소 창구) · pg 프로그램 순매수(원 · 통합) · fr · inst 외국인 · 기관 장중 추정가집계 순매수(주 · 최신 입력).
    받는 함수는 큰 차트 바닥 줄 · 「매수」 칩이 쓰는 것 그대로(fetch_investor_member · _program_net_today · fetch_investor_estimate) — 새 받는 길 없음."""
    from concurrent.futures import ThreadPoolExecutor
    at = _now().strftime("%H:%M")

    def one(c):
        out = {"ff": None, "pg": None, "fr": None, "inst": None, "at": at}
        try:
            out["ff"] = ((proxy.fetch_investor_member(cfg, c) or {}).get("foreignFirms") or {}).get("net")
        except Exception:
            pass
        try:
            out["pg"] = proxy._program_net_today(cfg, c)
        except Exception:
            pass
        try:
            lt = (proxy.fetch_investor_estimate(cfg, c) or {}).get("latest") or {}
            out["fr"], out["inst"] = lt.get("foreign"), lt.get("inst")
        except Exception:
            pass
        return c, out
    with ThreadPoolExecutor(FLOW_WORKERS) as ex:
        return dict(ex.map(one, codes))


def track(proxy, cfg, b, hhmm, late):
    """그 시각 값을 적는다 — 5분봉 종가가 없으면 그때 현재가(늦음이 NOW_OK_MIN 분 안일 때만 · 넘으면 null)."""
    need = [r["code"] for r in b["rows"] if hhmm not in r["px"]]
    now_p = {}
    for r in b["rows"]:
        if r["code"] not in need:
            continue
        v = _bar_close(proxy, b["day"], r["code"], hhmm)
        if v is not None:
            r["px"][hhmm], r["pxSrc"][hhmm] = v, "5m"
    left = [r["code"] for r in b["rows"] if hhmm not in r["px"]]
    if left and late > NOW_OK_MIN:
        for r in b["rows"]:
            if hhmm not in r["px"]:
                r["px"][hhmm], r["pxSrc"][hhmm] = None, "none"
    elif left:
        now_p, _ = proxy.fetch_quotes_multi(cfg, left)
        for r in b["rows"]:
            p = (now_p.get(r["code"]) or {}).get("price")
            if hhmm not in r["px"] and p is not None:
                r["px"][hhmm], r["pxSrc"][hhmm] = p, "now"
    # 수급 — 30분 칸마다 그때 값을 적어 굳힌다(묶음 ③). 지난 시각 값은 다시 못 받으므로 늦음이 NOW_OK_MIN 분을 넘으면 null(못 잼)
    fneed = [r["code"] for r in b["rows"] if hhmm not in (r.get("flow") or {})]
    if fneed:
        got = flows(proxy, cfg, fneed) if late <= NOW_OK_MIN else {}
        for r in b["rows"]:
            if r["code"] in fneed:
                r.setdefault("flow", {})[hhmm] = got.get(r["code"])


# ---------------------------------------------------------------- 지난 날 되채우기
# 재권님 「관심을 제외하고 지난 20일의 정보가 필요해 가져올수 있는곳 찾아서 가져와줘」(18:0x) → 「지난 30일 데이터도 적용해서 넣어놔」(19:3x).
# 개발 DB 에 쌓인 것으로 그날 09:06 판을 다시 센다 — VI 만 KIS 에 묻는다. 다시 센 날은 meta.rebuilt true · missing(못 센 칩) · approx(어림한 칩).
#   관심 · 수급  그날 09:01 직전 관심 목록 문서(보드 문서 저장 기록 · watch_at)로 오늘 판과 같게 센다 — meta.watchSrc 「기록」
#              (재권님 「투자 전략 단타안에 관심도 넣어주고 룰도 넣어줘」 11-12 → 안 「응」) · 시가총액은 지금 값
#              기록이 없는 날(2026-10-26 전)은 관심 「못 받음」 · 수급은 앞 거래일 auto_watch_day 값에 **지금** 수급 룰을 댄 어림 — meta.watchSrc 「없음」
#   프리장     그날 pre_flow.PRE_OPEN~PRE_CLOSE 5분봉(끝 봉 빼고) 거래대금(종가 × 거래량)과 마지막 봉 종가 ÷ 앞 거래일 종가 등락률로 pre_flow.pick(오른 것 중 거래대금 큰 순) — 어림
#   VI·급등    급등 — 09:00 ~ BUY_LATE(09:35) 봉 고가가 앞 거래일 종가보다 intraday_alerts.SURGE_PCT % 이상 · VI — KIS 「VI 현황」(날짜 · 종목) 에서 09:00~BUY_LATE 발동
#              (VI_PROBE_PCT % 넘게 오른 종목만 묻는다 · QUIET 밖에서만 돈다)
#   매수       앞 거래일 확정치(investor_daily) 외국인 · 기관 둘 다 순매수인 종목 중 합 상위 JOINT_TOP — 장중 가집계가 없어 어림 · 하위 칸 없음
#   초반상승   09:00 봉 (종가 − 시가) ÷ 시가 ≥ open_rise.RISE_PCT · 시가총액 open_rise.MIN_CAP_EOK 이상(라이브와 같은 셈)
#   장외       09:06 에는 비어 있다(라이브와 같다)
#   볼린저     그날 09:06 전에 보낸 바닥 신호(signal_sent) — 칩 이름만
#   매수가     09:05 봉 시가(09:06 값에 가장 가까운 쌓인 값) · pct 는 앞 거래일 종가 대비 · 현재상승은 그 값이 09:00 시가보다 NOW_RISE_PCT 이상
#   시가총액 · 섹터 · 시장은 지금 값이다(그날 값 기록이 없다)
# 5분봉이 쌓인 종목은 순위 목록(코스피 200 · 코스닥 150) 둘레뿐이다 — 그 밖 종목은 칩에 못 든다
BACKFILL_DAYS = DAYS_KEEP     # 되채울 거래일 수 — 「지난 30일」
JOINT_TOP = 30                # 「매수」 어림 — 외 · 기 순매수 합 상위 몇
VI_PROBE_PCT = 3.0            # 지난 날 VI 를 KIS 에 물을 종목 — 09:00 · 09:05 봉 고가가 앞 거래일 종가보다 이 % 이상(동적 VI 가장 낮은 문턱 · 코스피200 3%)
QUIET = ((7, 30), (20, 10))   # 되채우기(VI 를 KIS 에 묻는다)를 안 하는 때 — 장 전 · 장중 · 넥장(20:00)까지 KIS 몫을 안 쓴다
VI_WORKERS = 6                # VI 를 겹쳐 묻는 수
# 서버가 뜨면 QUIET 와 상관없이 이번 주(월요일부터 어제까지) 거래일을 먼저 채운다 — 재권님 「어제랑 어그제라도 먼저 넣어노라고해」 → 「이번주꺼만 넣어줘」(11-12 08:4x) · 하루 VI 묻기 150번 남짓 · 사본 DB 로 두 날 65초
RECENT_SKIP = ((7, 59), (8, 3))  # 그래도 이때는 미룬다 — BUY_AT 굳힘이 밀리지 않게


def _trade_days(proxy, before, n):
    with proxy.db_conn() as conn:
        return [d for (d,) in conn.execute(
            "SELECT DISTINCT day FROM auto_watch_day WHERE day < ? ORDER BY day DESC LIMIT ?", (before, n + 1))]


def rebuild(proxy, day, prev, cfg=None):
    """day 의 09:06 판을 쌓인 값으로 다시 센다(prev = 앞 거래일). 5분봉이 없으면 None. cfg 를 주면 VI 를 KIS 에서 받는다."""
    import auto_watch, company_profile, dart, intraday_alerts, market_hours, open_rise, pre_flow
    uni = dart.universe_rows(None)
    cap = {r["stock_code"]: r["market_cap"] for r in uni}
    mkt = {r["stock_code"]: r["market"] for r in uni}
    small = lambda c: cap.get(c) is not None and cap[c] < CAP_MIN_EOK
    with proxy.db_conn() as conn:
        bars = {}
        for code, ts, o, h, c, v in conn.execute(
                "SELECT code, ts, open, high, close, volume FROM candles WHERE period = '5m' AND ts >= ? AND ts <= ?",
                (day + "0800", day + "1400")):
            bars.setdefault(code, {})[ts[8:12]] = (o, h, c, v)
        if not any("0900" in b for b in bars.values()):
            return None
        pv = {r[0]: r for r in conn.execute("SELECT code, name, close, pct, vol FROM auto_watch_day WHERE day = ?", (prev,))}
        pbar = {}                                          # 앞 거래일 종가를 auto_watch_day 에 없는 종목(대상 밖 작은 종목 · VI 가 잦다)은 앞 날 정규장 끝(market_hours.REG_CLOSE)까지 끝난 마지막 5분봉 종가로
        rc = int(market_hours.REG_CLOSE[:2]) * 60 + int(market_hours.REG_CLOSE[2:])
        for code, ts, c in conn.execute("SELECT code, ts, close FROM candles WHERE period = '5m' AND ts >= ? AND ts < ? ORDER BY ts",
                                        (prev + "%02d%02d" % divmod(rc - 30, 60), prev + market_hours.REG_CLOSE)):
            if c:
                pbar[code] = c
        inv = conn.execute("SELECT code, row FROM investor_daily WHERE date = ?", (prev,)).fetchall()
        bb = [r[0] for r in conn.execute("SELECT DISTINCT code FROM signal_sent WHERE day = ? AND ts <= ?",
                                         (day, int(day + "0906")))]
    base_of = lambda c: (pv.get(c) or (None, None, None))[2] or pbar.get(c)
    approx_base = {"급등": 0, "VI": 0}    # 앞 거래일 종가 — 없으면 앞 날 마지막 정규장 5분봉 종가(어림)
    names = {c: (r[1] or "") for c, r in pv.items()}
    names.update({r["stock_code"]: r["name"] for r in uni})
    hit, missing, approx = {}, [] if cfg else ["VI"], ["프리장", "매수"]

    def put(code, chip, sub=None, **kw):
        g = hit.setdefault(code, {"name": names.get(code, ""), "chips": set(), "subs": {}})
        g["chips"].add(chip)
        g.update(kw)
        if sub and sub not in g["subs"].setdefault(chip, []):
            g["subs"][chip].append(sub)

    try:
        wdoc = watch_at(day)
    except Exception:
        wdoc = None
    watch_src = "기록" if isinstance(wdoc, dict) else "없음"
    if watch_src == "기록":
        watch_chips(wdoc, lambda c, n, chip, sub=None: put(_six(c), chip, sub) if _six(c) else None, small, merged=False)
    else:
        missing.append("관심")
    try:                                                   # 수급 — 기록이 없는 날만 앞 거래일 값에 지금 룰(어림)
        if watch_src == "기록":
            raise StopIteration
        approx.append("수급")
        live = {"day": prev, "frac": 1, "at": "", "got": {c: {"name": r[1], "close": r[2], "pct": r[3], "vol": r[4]} for c, r in pv.items()}}
        res = auto_watch.compute(proxy, live=live)
        if not res.get("ready"):
            raise ValueError("수급 룰 못 읽음")             # 룰을 못 읽으면 「없음」 이 아니라 「못 셈」
        for r in res.get("picked") or []:
            put(r["code"], "수급")
    except StopIteration:
        pass
    except Exception:
        missing.append("수급")
    p0, p1 = "%02d%02d" % pre_flow.PRE_OPEN, "%02d%02d" % pre_flow.PRE_CLOSE     # 프리장 창 — 서버 값 한 곳 · 끝 봉(08:50~)은 프리장 밖(day_top_fill 과 같게)
    amt = {c: sum((b[2] or 0) * (b[3] or 0) for hm, b in d.items() if p0 <= hm < p1) for c, d in bars.items()}
    items = []
    for c, a in amt.items():                               # 프리장 — 서버 셈 한 곳(pre_flow.pick · 오른 것 중 거래대금 큰 순 TOP_N · 재권님 11-12)
        if a > 0 and not small(c):
            last = [bars[c][hm][2] for hm in sorted(bars[c]) if p0 <= hm < p1 and bars[c][hm][2]]
            base = base_of(c)
            items.append({"code": c, "amt": a, "pct": (last[-1] / base - 1) * 100 if last and base else None})
    for c in pre_flow.pick(items):
        put(c, "프리장")
    late = PAST_LATE[0] * 60 + PAST_LATE[1] - BAR_MIN       # VI · 급등은 굳히는 때(BUY_LATE)까지 본다 — 그날 판이 09:35 까지 다시 세며 넣는 것과 같게
    vi_bars = ["%02d%02d" % divmod(m, 60) for m in range(9 * 60, late + 1, BAR_MIN)]   # (재권님 「vi가 왜 안나오지?」 11-12 → 「응」 11-13 · 전에는 09:00 · 09:05 봉 · 09:01 까지라 28 → 1)
    for c, d in bars.items():                              # 급등
        base = base_of(c)
        hi = max([d[hm][1] for hm in vi_bars if hm in d and d[hm][1]] or [0])
        if base and hi and (hi / base - 1) * 100 >= intraday_alerts.SURGE_PCT:
            first = next(hm for hm in vi_bars if hm in d and d[hm][1] and (d[hm][1] / base - 1) * 100 >= intraday_alerts.SURGE_PCT)
            put(c, "VI·급등", "급등", surgeAt=first[:2] + ":" + first[2:] + "~", surgeApprox=True)   # 5분봉이라 그 봉 시작 시각(5분 단위 어림 · 「~」)
            if c not in pv:
                approx_base["급등"] += 1                   # 어림 종가(앞 날 5분봉)로 센 급등
    if cfg:                                                # VI — KIS 「VI 현황」 에 날짜 · 종목을 넣으면 그 종목의 그날 VI(최근 것부터 30건)가 온다(19:4x 잼)
        vt = "%02d%02d00" % PAST_LATE
        probe = []
        for c, d in bars.items():
            base = base_of(c)
            hi = max([d[hm][1] for hm in vi_bars if hm in d and d[hm][1]] or [0])
            if base and hi and (hi / base - 1) * 100 >= VI_PROBE_PCT:
                probe.append(c)                        # BUY_LATE 까지 VI_PROBE_PCT % 도 안 오른 종목은 묻지 않는다(상승 VI 문턱 아래)

        def ask(c):
            return c, proxy.kis_get(cfg, intraday_alerts.VI_PATH,
                                    {"FID_DIV_CLS_CODE": "1", "FID_COND_SCR_DIV_CODE": "20139", "FID_MRKT_CLS_CODE": "0",
                                     "FID_INPUT_ISCD": c, "FID_RANK_SORT_CLS_CODE": "0", "FID_INPUT_DATE_1": day,
                                     "FID_TRGT_CLS_CODE": "", "FID_TRGT_EXLS_CLS_CODE": ""}, intraday_alerts.VI_TR).get("output") or []

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=VI_WORKERS) as ex:      # 한 건 왕복이 1초 남짓이라 겹쳐 묻는다 — 초당 한도는 kis_get 이 지킨다
            for fut in [ex.submit(ask, c) for c in probe]:
                try:
                    c, out = fut.result()
                except Exception:
                    if "VI" not in missing:
                        missing.append("VI")
                    continue
                hs = sorted(((h, r) for h, r in ((str(r.get("cntg_vi_hour") or "").strip().zfill(6), r) for r in out if r.get("bsop_date") == day)
                             if "090000" <= h <= vt), key=lambda x: x[0])   # 앞 0 이 빠진 시각(「93012」)도 맞게 견준다(qa 덧 11-18)
                if hs:
                    h0, r0 = hs[0]
                    at0 = "%s:%s:%s" % (h0[0:2], h0[2:4], h0[4:6])
                    try:
                        p0 = float(r0.get("vi_prc") or 0) or None
                    except (TypeError, ValueError):
                        p0 = None
                    put(c, "VI·급등", "VI", viAt=at0,                     # 그날 그 종목 VI 중 가장 이른 것(KIS VI 현황) · 그때 발동가
                        viPx={"at": at0, "px": p0, "src": "vi"} if p0 else None)
                    if c not in pv:
                        approx_base["VI"] += 1             # 어림 종가로 골라 물은 종목에서 나온 VI
    jb = []
    for c, row in inv:                                     # 매수 어림
        try:
            j = json.loads(row)
            f, i = j["foreign"]["netAmt"], j["inst"]["netAmt"]
        except (ValueError, KeyError, TypeError):
            continue
        if f and i and f > 0 and i > 0 and not small(c):
            jb.append((f + i, c))
    for _, c in sorted(jb, reverse=True)[:JOINT_TOP]:
        put(c, "매수")
    for c, d in bars.items():                              # 초반상승
        b = d.get("0900")
        cp = cap.get(c)
        if b and b[0] and b[2] is not None and cp is not None and cp >= open_rise.MIN_CAP_EOK:
            pct = (b[2] - b[0]) / b[0] * 100
            if pct >= open_rise.PAST_RISE_PCT:             # 지난 날은 첫 5분봉 2% 셈 그대로(1분봉은 11-12 부터만)
                put(c, "초반상승", rise=round(pct, 2))
    for c in bb:
        if c in hit:
            hit[c]["chips"].add("볼린저")
    sec = company_profile.sectors()
    rows, down = [], 0
    for code, g in hit.items():
        if not g["chips"] & set(OV_CHIPS):
            continue
        d = bars.get(code) or {}
        buy = (d.get("0905") or (None,))[0]
        base = base_of(code)
        if buy and base and (buy / base - 1) * 100 < DROP_BELOW_PCT:
            down += 1                                  # 하락 뺌 — 09:05 봉 시가가 앞 거래일 종가 아래
            continue
        o9 = (d.get("0900") or (None,))[0]
        chips = set(g["chips"])
        if buy and o9 and (buy / o9 - 1) * 100 >= NOW_RISE_PCT:
            chips.add("현재상승")
        px, src = {}, {}
        for t in times():
            m = int(t[:2]) * 60 + int(t[2:]) - BAR_MIN
            b = d.get("%02d%02d" % divmod(m, 60))
            px[t], src[t] = (b[2], "5m") if b and b[2] is not None else (None, "none")
        rows.append({"code": code, "name": g["name"], "market": mkt.get(code), "cap": cap.get(code), "sector": sec.get(code),
                     "chips": [c for c in OV_CHIPS + ("현재상승", "볼린저") if c in chips], "subs": g["subs"],
                     "n": len(chips & set(OV_CHIPS)), "buy": buy,
                     "pct": round((buy / base - 1) * 100, 2) if buy and base else None, "rise": g.get("rise"),
                     "viAt": g.get("viAt"), "surgeAt": g.get("surgeAt"), "surgeApprox": g.get("surgeApprox"), "viPx": g.get("viPx"),
                     "px": px, "pxSrc": src})
    tab = score_table(proxy)
    off = late_min(proxy, day=day)                     # 그날 늦게 열었으면 VI·급등 나누는 시각도 그만큼 뒤(개념정의 덧 11-19 — 그날 판과 같게)
    order = sort_rows(rows, tab, off)
    rows = rows[:TOP_N]
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return {"day": day, "buyAt": "%02d:%02d" % PAST_BUY_AT, "times": times(), "rows": rows, "closed": True,
            "meta": {"rebuilt": True, "viSplit": vi_split(off), "missing": missing, "approx": approx, "prevDay": prev, "candidates": len(hit), "topN": TOP_N, "dropDown": down, "dropBelowPct": DROP_BELOW_PCT,
                     "watchSrc": watch_src, "rules": chip_rules(proxy, merged=False), "viUntil": "%02d:%02d" % PAST_LATE, "approxBase": approx_base,
                     "capMinEok": CAP_MIN_EOK, "order": order, "score": tab, "scoreConflict": score_conflicts(tab),
                     "note": "쌓인 값으로 다시 셈(VI 만 KIS) · 관심 · 수급은 그날 09:01 직전 관심 목록(watchSrc 기록 · 없으면 관심 못 받음 · 수급 어림) · 프리장 · 매수는 어림(dt30.py 「지난 날 되채우기」) · "
                             "buy 는 09:05 봉 시가 · 시가총액 · 섹터 · 시장은 지금 값"}}


def backfill(proxy, today, limit=BACKFILL_DAYS, since=None, today_too=False):
    """today 앞 limit 거래일 중 판이 없는 날을 다시 세어 남긴다(라이브로 굳힌 날은 안 건드린다). 남긴 날 수."""
    ds = _trade_days(proxy, today, limit)
    have, keep_live = set(), {}
    for d in days(proxy):                              # 관심 없이 세어 둔 되채운 날(watchSrc 칸 전)은 한 번 다시 센다(11-12 「응」)
        got = _load(proxy, d)
        m = (got[0].get("meta") or {}) if got else {}
        if not (m.get("rebuilt") and ("watchSrc" not in m or m.get("viUntil") != "%02d:%02d" % PAST_LATE)):
            have.add(d)                                # VI 창이 다른 되채운 날(11-13 전)도 한 번 다시 센다
        elif m.get("liveBefore"):
            keep_live[d] = m["liveBefore"]
    n = 0
    cfg = proxy.load_secrets()
    for i, d in enumerate(ds[:limit]):
        if d in have or i + 1 >= len(ds) or (since and d < since):
            continue
        b = rebuild(proxy, d, ds[i + 1], cfg)
        if b and b["rows"]:
            if d in keep_live:                         # 장중에 고른 기록은 다시 세도 이어 남긴다
                b["meta"]["liveBefore"], b["meta"]["redoneFromLive"] = keep_live[d], True
            _store(proxy, b)
            n += 1
    if today_too and ds:                               # 오늘 판 — 14:00 칸까지 닫혔는데 오늘 바뀐 룰(meta.rules 칸) 전에 센 판이면 쌓인 값으로 한 번 다시 센다
        got = _load(proxy, today)                      # (재권님 「오늘 마뀐걸로 새로 해서 해줘」 11-12 15:2x · 그때 고른 기록은 덮인다)
        if got and got[0].get("closed") and "rules" not in (got[0].get("meta") or {}):
            b = rebuild(proxy, today, ds[0], cfg)
            if b and b["rows"]:
                b["meta"]["redoneFromLive"] = True
                old = got[0]                           # 덮이는 장중 기록을 한 벌 남긴다 — 되살릴 수 있게(개념정의 덧 11-12)
                b["meta"]["liveBefore"] = {"savedAt": got[1], "buyAt": old.get("buyAt"), "meta": old.get("meta"),
                                           "rows": [{k: r.get(k) for k in ("code", "name", "rank", "chips", "subs", "n", "buy", "buyAt", "pct", "rise", "px", "pxSrc")}
                                                    for r in old.get("rows") or []]}
                _store(proxy, b)
                n += 1
    return n


def _nx_1m(proxy, cfg, code, day, hhmm):
    """그날 넥스트레이드 1분봉 중 hhmm 에 끝난 봉(없으면 그 앞 마지막 프리장 봉)의 종가 · 거래량 합 — 못 받으면 (None, None)."""
    import nxt_pre
    data = proxy.kis_get(cfg, "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice",
                         {"FID_COND_MRKT_DIV_CODE": "NX", "FID_INPUT_ISCD": code, "FID_INPUT_HOUR_1": hhmm + "00",
                          "FID_INPUT_DATE_1": day, "FID_PW_DATA_INCU_YN": "Y", "FID_FAKE_TICK_INCU_YN": ""},
                         "FHKST03010230")
    if data is None:
        return None, None
    vol, last = 0, None
    for r in data.get("output2") or []:
        t = str(r.get("stck_cntg_hour") or "")[:4]
        if r.get("stck_bsop_date") != day or not (nxt_pre.PRE_FROM <= t <= hhmm):
            continue
        vol += proxy._num(r.get("cntg_vol"), int) or 0
        if last is None or t > last[0]:
            last = (t, proxy._num(r.get("stck_prpr"), int))
    return (last[1] if last else None), vol


def nx_quotes(proxy, cfg, codes, day, hm):
    """그날(day · 거래일) 넥스트레이드 NX_AT 값 — {code: {day, px, src, vol}} · 08:05 전이면 {} · 지금 못 하면 None(다음 바퀴에 다시).
    NX_AT ~ NX_NOW_UNTIL 은 멀티 시세 현재가(src 「now」 · 30종목 묶음) · 그 뒤는 그 시각까지 1분봉 마지막 종가(src 「1m」 · 종목마다 · NX_SKIP 동안은 None).
    거래가 없던 종목 · 못 받은 종목은 px null(0 아님). 단타 판(nx_fill)과 종가배팅 판(closing_bet)이 함께 쓴다 — 셈은 여기 한 곳."""
    if hm < NX_AT[0] * 60 + NX_AT[1]:
        return {}
    hhmm = "%02d%02d" % NX_AT
    out = {}
    if hm < NX_NOW_UNTIL[0] * 60 + NX_NOW_UNTIL[1]:
        import nxt_pre
        q = nxt_pre.fetch_nx(proxy, cfg, codes, gap=0)
        if not q:
            return None                                # 하나도 못 받음 — 다음 바퀴에 다시(NX_NOW_UNTIL 넘으면 1분봉으로)
        for c in codes:
            v = q.get(c)
            out[c] = ({"day": day, "px": None, "src": None, "vol": None} if v is None          # 못 받음(NX 미상장 · 응답 없음)
                      else {"day": day, "px": v["price"] if v.get("vol") else None, "src": "now", "vol": v.get("vol")})   # 거래 없으면 null
        return out
    lo, hi = NX_SKIP
    if lo[0] * 60 + lo[1] <= hm < hi[0] * 60 + hi[1]:
        return None
    for c in codes:
        px, vol = _nx_1m(proxy, cfg, c, day, hhmm)
        out[c] = {"day": day, "px": px if vol else None, "src": "1m" if vol is not None else None, "vol": vol}
    return out


def nx_fill(proxy, cfg, day, hm):
    """그날(day · 거래일) NX_AT 에 앞 판 종목의 넥스트레이드 값을 그 판에 적는다 — rows[].nx {day, px, src, vol} · meta.nxAt · nxDay.
    값 셈은 nx_quotes 한 곳. 앞 판만 — 지난 날 되채움은 안 함(지시 밖).
    1 적음 · 0 적을 것 없음(앞 판 없음 · 이미 적음 · 08:05 전) · None 지금 못 함(다음 바퀴에 다시)."""
    if hm < NX_AT[0] * 60 + NX_AT[1]:
        return 0
    prev = [d for d in days(proxy) if d < day]
    got = _load(proxy, prev[0]) if prev else None
    if not got:
        return 0
    b = got[0]
    if b.get("meta", {}).get("nxDay") == day:
        return 0                                       # 이미 적었다(현재가든 1분봉이든 한 번)
    q = nx_quotes(proxy, cfg, [r["code"] for r in b["rows"]], day, hm)
    if q is None:
        return None
    for r in b["rows"]:
        r["nx"] = q.get(r["code"]) or {"day": day, "px": None, "src": None, "vol": None}
    b["meta"].update(nxAt="%02d:%02d" % NX_AT, nxDay=day,
                     nxNote="nx — 다음 거래일 넥스트레이드 %02d:%02d 값(src now = 그때 현재가 · 1m = 그날 그 시각까지의 1분봉 마지막 종가) · 거래가 없거나 못 받으면 px null" % NX_AT)
    _store(proxy, b)
    return 1


def days(proxy):
    try:
        with proxy.db_conn() as conn:
            return [d for (d,) in conn.execute("SELECT day FROM dt30 ORDER BY day DESC LIMIT ?", (DAYS_KEEP,))]
    except Exception:
        return []


PX_MIN = (1, 2, 3, 4, 5)     # 「개장 N분 뒤 값」(rows[].pxMin) — 재권님 「사는 시간도 쓸수있게 해줘 9시 1분~ 5분 사이에 살거야」(11-19 12:2x) ·
                             # N=1 이 「09:01 값」(px1 · 재권님 「9시 1분 등락도 넣어줘 이쯤 살거니깐」 11-18 19:1x)


def _open_min(proxy, day, b=None):
    """그날 정규장 여는 시각(분) — 보통 날 OPEN_AT · 늦게 여는 날(수능 10:00)은 늦은 분만큼 뒤(11-19 「응 해줘」).
    판(b)에 저장된 meta.lateMin 을 먼저 쓴다 — 장 시각 표(market-hours 문서)는 개발 폴더에만 있어 메인 · 중간서버가 읽으면 0 이 된다(qa 걸림 11-19 13:58)."""
    lm = ((b or {}).get("meta") or {}).get("lateMin")
    if not isinstance(lm, int):
        lm = late_min(proxy, day=day)
    return OPEN_AT[0] * 60 + OPEN_AT[1] + lm


def _hhmm(m):
    return "%02d:%02d" % divmod(m, 60)


def _vipx_fill(proxy, b):
    """VI 발동 때 값이 없는 줄(viAt 만 있음) — 그 분 1분봉 시가(src 「1m」 · DB candles) · 없으면 viPx null(못 잼).
    VI 가 없는 줄은 viPx null. 저장 안 함(읽을 때) — 재권님 「매수 타이밍을 9시1분 과 vi발동 두개를 고를수 있게」(11-18 19:2x)."""
    rows = b.get("rows") or []
    for r in rows:
        r.setdefault("viPx", None)
    old = [r for r in rows if not r.get("viAt") and "VI" in ((r.get("subs") or {}).get("VI·급등") or [])]
    if old:                                            # 시각 칸 전 판(11-18 전 · 그날 판 처음 셈) — 그날 쌓인 VI 사건(vi_stats.vi_events)의 첫 발동
        try:
            with proxy.db_conn() as conn:
                ev = {}
                for c, at, px in conn.execute("SELECT code, at, price FROM vi_events WHERE day = ? AND kind = 'VI' ORDER BY at", (b["day"],)):
                    ev.setdefault(c, (at, px))         # 그 종목 그날 첫 발동(이른 시각 먼저 · 개념정의 덧 11-19)
        except Exception:
            ev = {}
        for r in old:
            if r["code"] in ev:
                r["viAt"] = ev[r["code"]][0]
                if ev[r["code"]][1]:
                    r["viPx"] = {"at": ev[r["code"]][0], "px": ev[r["code"]][1], "src": "vi"}
    olds = [r for r in rows if not r.get("surgeAt") and not r.get("surgeApprox") and "급등" in ((r.get("subs") or {}).get("VI·급등") or [])]
    if olds:                                           # 〃 급등 — 그날 쌓인 급등 사건의 첫 시각(이 서버가 처음 본 때 · 판 viAt 과 같은 출처) · 저장 안 함
        try:
            with proxy.db_conn() as conn:
                sv = {}
                for c, at in conn.execute("SELECT code, at FROM vi_events WHERE day = ? AND kind = '급등' ORDER BY at", (b["day"],)):
                    sv.setdefault(c, at)
        except Exception:
            sv = {}
        for r in olds:
            if r["code"] in sv:
                r["surgeAt"] = sv[r["code"]]
    need = [r for r in rows if r.get("viAt") and not r.get("viPx")]
    if not need:
        return 0
    got = {}
    with proxy.db_conn() as conn:
        for r in need:
            ts = b["day"] + r["viAt"][0:2] + r["viAt"][3:5]
            row = conn.execute("SELECT open FROM candles WHERE period = '1m' AND code = ? AND ts = ?", (r["code"], ts)).fetchone()
            if row and row[0]:
                got[r["code"]] = row[0]
    for r in need:
        v = got.get(r["code"])
        r["viPx"] = {"at": r["viAt"], "px": v, "src": "1m"} if v else None
    return len(got)


def _pxmin_fill(proxy, b):
    """줄마다 rows[].pxMin {"N": {at, px, src 「1m」}} — 여는 시각 + N분의 값 = 그 앞 1분봉(여는 시각 + N − 1 분 봉) 종가(DB candles 1m).
    이미 있는 칸은 그대로 · 1분봉이 없는 칸은 비워 둔다(null 은 _pxmin_live · board 가 채움). px1 = pxMin "1"(옛 판에 px1 이 있으면 그대로).
    meta.pxMinAt · px1At 를 적는다. 그날 판은 고리가 분마다 적고(_pxmin_live) · 지난 판은 1분봉이 남은 날만(11-12 부터) 읽을 때 채운다(저장 안 함)."""
    _vipx_fill(proxy, b)
    rows = b.get("rows") or []
    o = _open_min(proxy, b["day"], b)
    at = {str(n): _hhmm(o + n) for n in PX_MIN}
    b["meta"]["pxMinAt"] = at
    b["meta"]["px1At"] = at["1"]
    n_got = 0
    with proxy.db_conn() as conn:
        for n in PX_MIN:
            k = str(n)
            need = [r for r in rows if not (r.get("pxMin") or {}).get(k)]
            if not need:
                continue
            ts = b["day"] + _hhmm(o + n - 1).replace(":", "")
            q = "SELECT code, close FROM candles WHERE period = '1m' AND ts = ? AND code IN (%s)" % ",".join("?" * len(need))
            got = dict(conn.execute(q, [ts] + [r["code"] for r in need]).fetchall())
            for r in need:
                v = got.get(r["code"])
                if v:
                    r.setdefault("pxMin", {})[k] = {"at": at[k], "px": v, "src": "1m"}
                    n_got += 1
    for r in rows:
        if not r.get("px1") and (r.get("pxMin") or {}).get("1"):
            r["px1"] = r["pxMin"]["1"]
    return n_got


def _pxmin_live(proxy, cfg, b, n):
    """그날 판 — 여는 시각 + N분이 지난 뒤 한 번: 1분봉 종가를 적고 · 1분봉이 없는 종목은 그때 현재가(src 「now」 · 늦음이 NOW_OK_MIN 분 안일 때만) ·
    그것도 없으면 null(못 잼). 그 칸이 적힌 줄(null 포함)은 다시 안 본다 — 새로 든 종목은 다음 바퀴에."""
    _pxmin_fill(proxy, b)
    k = str(n)
    left = [r for r in b["rows"] if not (r.get("pxMin") or {}).get(k)]
    m = _open_min(proxy, b["day"], b) + n
    late = _now().hour * 60 + _now().minute - m
    if left and late <= NOW_OK_MIN:
        q, _ = proxy.fetch_quotes_multi(cfg, [r["code"] for r in left])
        for r in left:
            p = (q.get(r["code"]) or {}).get("price")
            if p:
                r.setdefault("pxMin", {})[k] = {"at": _hhmm(m), "px": p, "src": "now"}
    for r in b["rows"]:
        r.setdefault("pxMin", {}).setdefault(k, None)
        if n == 1 and not r.get("px1"):
            r["px1"] = r["pxMin"]["1"]


TG_TOP = 10                  # 텔레그램으로 보내는 상위 종목 수 — 재권님 「단타 목록 상위 10개가 최초로 볼수있는 시간이 어떻게 되지? 그걸 바로 텔레그램으로 보내고 싶은데」 → 「나」(개장 1분 뒤 · 11-19 13:5x)
TG_SEND = False              # 켜기 — 그날 판 상위 TG_TOP 을 개장 1분 값이 적힌 뒤 하루 한 통 · 켜는 것은 재권님 지시로(11-19 시험 한 통만 보냄)
TG_LATE_MIN = 10             # 개장 1분 값 뒤 이 분 안에서만 보낸다 — 서버가 늦게 뜬 날 묵은 차례를 보내지 않게
TG_PAGE = "/company-setup/strategy.html"   # 단타 판 화면 — 링크는 dart.MAIN_URL + 이 경로(「알림 글의 링크는 메인 주소 한 곳에서」)


def top_text(proxy, b, n=TG_TOP, head=""):
    """그날 판 상위 n 줄을 텔레그램 글로 — 머리(날짜 · 개장 1분 시각 · 못 받은 칩) · 종목마다 한 줄(차례 · 이름 · 점수 · 칩 · 시가 대비) · 끝에 단타 판 링크.
    차례는 판의 rank(점수 합 큰 순) 그대로 · 점수는 지금 점수표로 셈(없으면 칩 수) · 시가 대비는 개장 1분 값(pxMin "1") ÷ 여는 시각 1분봉 시가 − 1(없으면 「—」 · 0 아님)."""
    _pxmin_fill(proxy, b)
    rows = sorted(b.get("rows") or [], key=lambda r: r.get("rank") or 1e9)[:n]
    tab = score_table(proxy)
    off = (b.get("meta") or {}).get("lateMin")
    off = off if isinstance(off, int) else late_min(proxy, day=b["day"])
    at = (b.get("meta") or {}).get("px1At") or ""
    lines = ["%s📈 단타 상위 %d · %s-%s %s" % (head, len(rows), b["day"][4:6], b["day"][6:8], at)]
    miss = [c for c in (b.get("meta") or {}).get("missing") or [] if c != "매수어림"]
    if miss:
        lines.append("아직 못 받은 칩: " + " · ".join(miss))
    ts = b["day"] + _hhmm(_open_min(proxy, b["day"], b)).replace(":", "")
    with proxy.db_conn() as conn:                      # 정규장 시가 = 여는 시각 1분봉 시가(시세의 시가는 장 전 값이 섞일 수 있다 · 11-19 CJ ENM 47,000 ↔ 10:00 봉 42,150)
        q = "SELECT code, open FROM candles WHERE period = '1m' AND ts = ? AND code IN (%s)" % ",".join("?" * len(rows))
        o1 = dict(conn.execute(q, [ts] + [r["code"] for r in rows]).fetchall()) if rows else {}
    for i, r in enumerate(rows):
        p1 = ((r.get("pxMin") or {}).get("1") or {}).get("px")
        o = o1.get(r["code"])
        pct = "%+.1f%%" % ((p1 / o - 1) * 100) if p1 and o else "—"
        sc = row_score(r, tab, off) if tab else None
        lines.append("%d. %s(%s) %s · %s · 시가 대비 %s" % (
            i + 1, r.get("name") or "", r.get("code"), ("%g점" % sc) if sc is not None else "%d칩" % (r.get("n") or 0),
            " ".join(r.get("chips") or []) or "칩 없음", pct))
    if not rows:
        lines.append("든 종목 없음")
    lines.append("단타 판 › %s%s" % (dart.MAIN_URL, TG_PAGE))
    return "\n".join(lines)


def send_top(proxy, b, head=""):
    """top_text 를 보낸다 → (보냄?, 까닭). 보내는 자리는 dart.telegram_send 하나(보내는 서버만 · 조용한 시간 · 기록)."""
    return dart.telegram_send(top_text(proxy, b, head=head))


def board(proxy, day=None, cfg=None):
    """주소 /api/kis/dt30 의 data — 남긴 날만(없으면 None). 안 끝난 그날 판이면 rows[].now · nowAt 을 붙인다(cfg 를 줄 때)."""
    ds = days(proxy)
    day = day or (ds[0] if ds else None)
    got = _load(proxy, day) if day else None
    if not got:
        return None
    b, saved = got
    b["meta"]["savedAt"] = saved
    try:
        _pxmin_fill(proxy, b)                          # 여는 시각 + N분 값 · 09:01 값 — 적힌 것이 없으면 쌓인 1분봉에서(지난 판 · 그날 판 둘 다 · 저장 안 함)
        for r in b.get("rows") or []:
            r.setdefault("px1", None)
            pm = r.setdefault("pxMin", {})
            for n in PX_MIN:
                pm.setdefault(str(n), None)                # 못 잼 — 0 아님
    except Exception:
        pass
    b.setdefault("closed", True)                       # 옛 판(closed 칸 전) · 되채운 날은 끝난 판
    b["meta"]["refreshMs"] = None if b["closed"] else proxy.PRICE_CACHE_TTL * 1000
    if not b["closed"] and cfg is not None:
        # 그날 판은 14:00 마지막 칸 전까지 지금 값을 붙인다 — 재권님 「그날은 변동에 맞춰서 실시간으로 적용되야 하고 그날 2시가 지나면 값이 저장되도록」(19:3x)
        # 다시 받을 주기는 서버 값(refreshMs · 시세 캐시와 같은 PRICE_CACHE_TTL) — 화면은 그 값으로 돈다 · 시세는 그 나이 안이면 캐시
        q, _ = proxy.fetch_quotes_multi(cfg, [r["code"] for r in b["rows"]], max_age=proxy.PRICE_CACHE_TTL)
        for r in b["rows"]:
            r["now"] = (q.get(r["code"]) or {}).get("price")
        b["nowAt"] = _now().strftime("%H:%M:%S")
    return b


def status():
    return dict(_status, buyAt="%02d:%02d" % BUY_AT, times=times(), daysKeep=DAYS_KEEP)


def start(proxy):
    """쓰는 서버가 뜰 때 한 번 — 평일 BUY_AT 에 굳히고 TIMES 마다 값을 적는다."""
    if not proxy.marketdb.writable():
        return False
    import market_hours

    def loop():
        time.sleep(30)
        filled = recent = None
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = now.hour * 60 + now.minute
                if recent != day and not (RECENT_SKIP[0][0] * 60 + RECENT_SKIP[0][1] <= hm < RECENT_SKIP[1][0] * 60 + RECENT_SKIP[1][1]):
                    recent = day
                    n = backfill(proxy, day, BACKFILL_DAYS, since=(now - timedelta(days=now.weekday())).strftime("%Y%m%d"), today_too=True)
                    if n:
                        print("  [단타 30] 이번 주 %d일 먼저 다시 세어 남김" % n, flush=True)
                if filled != day and not (QUIET[0][0] * 60 + QUIET[0][1] <= hm < QUIET[1][0] * 60 + QUIET[1][1]):
                    filled = day                 # 멈춰도 그날은 다시 안 돈다(20초마다 무거운 셈을 되풀이하지 않게)
                    n = backfill(proxy, day)
                    if n:
                        print("  [단타 30] 지난 날 %d일 다시 세어 남김" % n, flush=True)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [단타 30] 되채우기 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = now.hour * 60 + now.minute
                if _status.get("nx") != day and now.weekday() < 5 and market_hours.today(proxy, day=day, now=now).get("open") is not False:
                    n = nx_fill(proxy, proxy.load_secrets(), day, hm)
                    if n:
                        _status["nx"] = day
                        print("  [단타 30] 앞 판에 %s %02d:%02d 프리장 값 적음" % (day, NX_AT[0], NX_AT[1]), flush=True)
                    elif n == 0 and hm >= NX_AT[0] * 60 + NX_AT[1]:
                        _status["nx"] = day          # 적을 앞 판이 없거나 이미 적음 — 그날은 다시 안 봄(None 은 다음 바퀴에 다시)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [단타 30] 프리장 값 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = now.hour * 60 + now.minute
                off = late_min(proxy, now)                 # 늦게 여는 날(수능) — 정규장 시각들을 그만큼 뒤로(재권님 「가로 해줘」 11-19)
                if now.weekday() < 5 and market_hours.today(proxy, day=day, now=now).get("open") is not False:
                    got = _load(proxy, day)
                    if got is None and BUY_AT[0] * 60 + BUY_AT[1] <= hm < BUY_LATE[0] * 60 + BUY_LATE[1] + off and _status["frozen"] != day:
                        b = build(proxy, proxy.load_secrets(), day)
                        _store(proxy, b)
                        _status.update(frozen=day, error=None)
                        print("  [단타 30] %s %02d:%02d 판 %d종목 굳힘%s" % (day, BUY_AT[0], BUY_AT[1], len(b["rows"]),
                              " · 못 받은 칩 " + " · ".join(b["meta"]["missing"]) if b["meta"]["missing"] else ""), flush=True)
                    elif got is not None:
                        b = got[0]
                        if b.get("closed") and not b.get("rows") and hm < BUY_LATE[0] * 60 + BUY_LATE[1] + off:
                            b["closed"] = False            # 줄 0 으로 굳어 버린 판 — 굳히는 때 전이면 다시 연다(11-19 수능 아침 08:00 에 빈 판이 굳어 다시 세기가 멈춤)
                        was = bool(b.get("closed"))
                        due = [t for t in b["times"] if int(t[:2]) * 60 + int(t[2:]) + 1 <= hm
                               and any(t not in r["px"] for r in b["rows"])]
                        filled_late = []
                        if not b.get("closed") and hm < BUY_LATE[0] * 60 + BUY_LATE[1] + off:
                            if time.time() - _status.get("rescan", 0) >= RESCAN_SEC:
                                _status["rescan"] = time.time()
                                if refresh(proxy, proxy.load_secrets(), b):
                                    filled_late = ["다시 셈"]
                        elif not b.get("closed"):
                            filled_late = patch_late(proxy, proxy.load_secrets(), b)
                        if filled_late and filled_late != ["다시 셈"]:
                            print("  [단타 30] %s 판에 늦게 나온 칩 채움 — %s" % (day, " · ".join(filled_late)), flush=True)
                        if due:
                            for t in due:
                                track(proxy, proxy.load_secrets(), b, t, hm - int(t[:2]) * 60 - int(t[2:]))
                        flow_now = False
                        o_min = _open_min(proxy, day, b)
                        for n in PX_MIN:                   # 여는 시각 + N분 값 — 그 분이 끝난 뒤(+1분) 한 번(새로 든 종목은 다음 바퀴에) · N=1 이 09:01 값
                            if hm >= o_min + n + 1 and any(str(n) not in (r.get("pxMin") or {}) for r in b["rows"]):
                                _pxmin_live(proxy, proxy.load_secrets(), b, n)
                                flow_now = True
                        if TG_SEND and _status.get("tg") != day and o_min + 2 <= hm < o_min + 2 + TG_LATE_MIN and b["rows"]:
                            _status["tg"] = day            # 하루 한 통 — 실패해도 다시 안 보낸다(앞 통이 갔을 수 있다)
                            ok, why = send_top(proxy, b)
                            print("  [단타 30] 상위 %d 텔레그램 %s" % (TG_TOP, "보냄" if ok else "못 보냄 — " + str(why)), flush=True)
                        if not b.get("closed") and hm >= OPEN_AT[0] * 60 + OPEN_AT[1] + off and time.time() - _status.get("flowNow", 0) >= FLOW_NOW_SEC:
                            _status["flowNow"] = time.time()      # 그날 판 줄의 수급 지금 값 — FLOW_NOW_SEC 마다(묶음 ③ · 09:00 뒤)
                            got = flows(proxy, proxy.load_secrets(), [r["code"] for r in b["rows"]])
                            for r in b["rows"]:
                                r["flowNow"] = got.get(r["code"])
                            b["meta"]["flowNowAt"] = _now().strftime("%H:%M")
                            flow_now = True
                        if not b.get("closed") and b["rows"] and all(t in r["px"] for t in b["times"] for r in b["rows"]):   # 빈 판은 안 굳힌다(all([]) 은 참)
                            b["closed"] = True             # 14:00 마지막 칸까지 적었다 — 그날 판을 굳힌다(그 뒤 now 안 붙음)
                            for r in b["rows"]:
                                r.pop("now", None)
                        if due or filled_late or flow_now or b.get("closed") and not was:
                            _store(proxy, b)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [단타 30] 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="dt30").start()
    return True
