# -*- coding: utf-8 -*-
"""단타 30 판 — 평일 09:06 단타 상위 30 을 그날 판으로 굳히고 30분마다 값을 적는다 · 30거래일 (2026-11-11).

재권님(시황분석1 창 17:4x) — 「단타 목록 상위 30개를 소팅해서 9시 6분에 배수(매수)하고 9시반 10시 등 30분 단위로 2시까지 가격 추적하도록
셋팅해줘」 → 「위에 날짜도 넣어줘 30일 추적가능하도록」 → 「관심을 제외하고 지난 20일의 정보가 필요해」(18:0x) · 서버 몫은 작업우선순위가
개발2 에 배분(18:15) → 안에 「시가총액순이 아니고 칩이 많이 걸린순으로 해줘」 · 「칩이 많이 걸리고 등락이 높고 시총이 높은순」(18:1x) → 「단타칩에 걸리는 우선순위 소팅하는룰 체크해서 그룰대로 하면되」 → 「칩수가 많은순 초반상승이높은순 시총순 이렇게 해서 올려」(19:1x).
화면은 Insight 「종목 고르는 룰」(company-setup/js/strategy-dt30.js · 시황분석1)이 읽는다.

    단타       아래 ov_chips() 중 **하나라도** 든 종목(재권님 18:5x 「100개까지」 — 홈 「단타」 는 둘 이상 · 화면이 칩을 끄고 켜며 다시 셈).
               칩 재료는 홈과 같다(holdings/js/home.js 의 OV_CHIPS · ovList — 칩 목록은 둘 다 칩 룰 표 한 곳).
               재료는 화면이 받는 서버 값 그대로 — 관심 · 수급(watchlist 문서 · 자동 묶음이 수급) · 프리장(pre_flow) · VI·급등(intraday_alerts) ·
               매수(「매수」 판 rows 전부) · 초반상승(open_rise) · 장외(순위 목록 시세의 regPct > 0 · 11-18 더함 — 서버가 평일 07:30~15:30 비워 아침 판에는 보통 안 든다).
               관심 · 프리장 · 매수는 시가총액 cap_min_eok() 억원 아래를 뺀다(화면 capBelowMin · 시가총액을 모르면 안 뺀다)
               **화면과 이 파일 두 곳에 셈이 있다** — 값 한 곳으로 모으는 것은 개발1 카드 「관심 아래 칩 룰 값 한 곳」(화면이 서버를 받는 쪽)
    차례       시가 대비 등락률(openRise) 높은 순 → 칩 수(점수표면 점수 합) 많은 순 → 시가총액 큰 순 — 상위 TOP_N(11-23 재권님 · sort_rows)
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

하락 뺌    전일 종가 대비 등락률(pct)이 drop_below_pct() 아래인 종목은 판에 안 넣는다 — 재권님 「단타에 하락인 종목은 필요없어」 →
               「거래량 많은 종목중에 하락인건 제외한다는 룰 넣어봐」(11-12) · 09:35 굳히기 전까지 1분마다 다시 셀 때 그때 값으로 넣고 뺀다 ·
               굳힌 뒤 내려간 종목은 그대로 둔다(이미 산 값) · 등락률을 모르면 안 뺀다(못 잼은 하락이 아니다) · 뺀 수는 meta.dropDown
               판에 들었다가 빠진 종목도 굳히기 전 다시 셀 때 다시 들 수 있다(「다시 안 넣음」 meta.out 은 11-20 없앰 · 빠짐은 meta.gone) ·
               없다가 조건이 맞게 된 종목은 넣는다 — 재권님 「처음 들었다가 빠지면 제외하고 없다가 값이 적용되는 목록은 넣는다」(11-12 11:3x) →
               「밀린건 넣지 않는다로 룰 만들자」(11-13 · qa 가 09:07↔09:32 판에서 다시 든 18 종목 매수가가 바뀐 것을 찾음)

못 받은 칩은 meta.missing 에 이름으로 남긴다(「0 종목」 과 「못 받음」 을 가른다).
"""
import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone

import chip_rules      # 칩 목록 · 문턱 한 곳(11-20)
import market_hours    # 휴장 셈 · 보관 거래일(KEEP_TRADE_DAYS) 한 곳
import dart            # 시가총액 문턱(UNIVERSE_MIN_CAP_EOK) 한 곳 — 모듈을 읽을 때 쓴다(dart 는 이 파일을 안 부른다)

KST = timezone(timedelta(hours=9))
TOP_N = 100                  # 재권님 18:5x 「상위 30개면 소팅에 걸리는게 적을수 있으니 지금 100개까지 늘려놔」
BUY_AT = (8, 0)              # 판 짓기 시작 — 재권님 「단타 목록은 8시부터 계속 리스트 나오게 해줘」(11-18 · 시황분석 창 · 작업우선순위 경유 · 안에 「응」 17:0x) · 그 전 09:01 — 재권님 「9시 6분에 배수」 → 「9시 5분에 무조건 갱신」(11-12 09:1x) → 「9시 1분에 바로 단타 리스트 뜨도록 … 못가져온 값은 못가져온대로 … 무슨값인지만 인지되도록」(09:2x · 작업우선순위 경유) · 빠진 칩은 meta.missing · 들어오면 patch_late 가 채움
TRACK_FROM = (9, 30)         # 값 적는 첫 시각
TRACK_TO = (14, 0)           # 값 적는 끝 시각 — 「2시까지」
TRACK_STEP = 30              # 분 — 「30분 단위로」
BAR_MIN = 5                  # 5분봉 길이(분)
BUY_LATE = (10, 30)          # 굳히는 시각 — 재권님 「굳히기는 10시반으로」(11-18 · 안에 「응」 17:0x) · 그 전 「9시 35분에 굳히는걸로」(11-12 09:2x) · BUY_AT 부터 이때까지 판을 다시 세고 이 뒤로는 줄을 안 바꾼다 · 서버가 이 뒤에 뜨면 그날 판은 안 짓는다 · 늦게 여는 날(수능)에도 10:30 그대로 — 재권님 「가」(11-20 09:0x · 11-19 에 11:30 까지 밀려 판이 바뀐 일)
OPEN_AT = (9, 0)             # 정규장 첫 값 — 그 전(BUY_AT ~ 09:00)에 든 종목의 매수가는 이 시각 정규장 시가(rows[].buyWait 가 그 표시 · 09:00 뒤 첫 다시 세기에 채움)
# 「한 번 빠지면 그날 다시 안 넣음」(OUT_FROM 09:01 · meta.out)은 없앴다 — 재권님 「9시 1분 뒤 한 번 빠진 종목은 다시 넣지 않는다 - 이룰없애」
# (11-20 10:2x · 한미약품이 09:23 하락뺌으로 빠진 뒤 +5% 인데 판에 못 듦). 굳히기 전 다시 셀 때 빠진 종목도 다시 들 수 있다 · 다시 들면 새로 든 줄(매수가는 다시 든 순간 값) ·
# 빠짐은 meta.gone 에 그대로 쌓인다 · 굳힌 줄(세 번 굳히기)은 그대로 안 빠진다. 옛 판의 meta.out 은 읽지 않는다.
PRE_WAIT = ("초반상승",)   # 09:00 전에는 값이 날 수 없는 칩 — 못 받음(missing)이 아니라 기다림(meta.wait)
# 「매수」 는 어림을 08:00 부터 — 재권님 「매수 목록중에 초반에 받을수 있는게 있지않나? 프리장에서」 → 「아니 매수는 그전에 받을수 있는 값 받으라고 했는데」
# (11-18 17:2x · 시황분석1 경유). 장 전은 프로그램만(early_buy pre) — 외국계 창구는 거래소(J) 창구라 장 전 체결이 없어 오늘 값이 없고 어제 값이 올 수 있다.
# 어림을 하나도 못 받으면 그때만 wait 에 「매수」(못 받음 아님) · 가집계(①~④)는 09:30 첫 입력이라 그대로 기다림(patch_late 가 채움)
# VI·급등 은 08:00 부터 — 재권님 「8시부터 받을수 있는 정보는 다 받으면 좋을거같은데. 단타 칩들은 정보가 빠르게 들어올수록 좋아」 →
# 장 전 VI(KIS VI 현황 08시대 — 넥스트 프리장으로 보임 · 11-19 08시대에 잴 것) · 장 전 급등(통합 등락률 순위 · 전일 종가 대비 SURGE_PCT 이상)에 「응 해줘」
# (11-18 17:2x · 시황분석1 경유). 텔레그램 알림(intraday_alerts)은 정규장만 그대로 — 단타 판만 pre_vi_surge 로 따로 읽는다 · 매수 어림(외국계 창구 · 프로그램)도 안 부른다
PAST_BUY_AT = (9, 1)         # 지난 날 다시 세기(rebuild)의 기준 시각 — 11-18 전 판 셈 그대로 둔다(지난 날을 10:30 기준으로 다시 세지 않는다 · 지시 밖)
PAST_LATE = (9, 35)          # 〃 VI·급등 창 끝
DAYS_KEEP = market_hours.KEEP_TRADE_DAYS   # 판을 들고 있는 거래일 — 1년(11-20 재권님 「한달로 지정됬지만 1년으로 넓히고 점점 늘려갈수 있다」 · 그 전 30) · 값은 market_hours 한 곳
# 칩 목록 · 문턱 — 서버 표 한 곳(chip_rules · 룰 문서 rules.chips 가 있으면 그것 · 11-20 개발1 표 · 개발2 받기로) · 부를 때마다 지금 값
def cap_min_eok():
    """시가총액 문턱(억원) — dart.rank_min_cap_eok() 한 곳(재권님 「3000으로 통일」 11-20)."""
    return dart.rank_min_cap_eok()


def now_rise_pct():
    """「현재상승」 — 시가 대비 %(화면도 /api/kis/chip-rules 로 같은 값)."""
    return chip_rules.get("현재상승", "nowRisePct")


def drop_below_pct():
    """하락 뺌 — 전일 종가 대비 이 % 아래는 판에 안 넣는다(0 이면 보합은 남긴다 · 재권님 11-12)."""
    return chip_rules.get("단타", "dropBelowPct")


def ov_chips():
    """단타 셈에 드는 칩과 차례(tuple) — 11-18 뒤 판은 「수급」 이 「관심」 으로 합쳐져 안 나온다(지난 날 판에는 남는다)."""
    return tuple(chip_rules.get("단타", "ovChips"))
TICK = 20
NX_AT = (8, 5)               # 다음 날 프리장 값 시각 — 재권님 「이종목들 내일 프리장에 8시 5분에 얼마인지 체크해서 넣어줘 … 어제에 프리장 8시5분 이라고 칸이 있어야 되고」(11-18 16:3x · 시황분석1 창 · 작업우선순위 경유)
NX_NOW_UNTIL = (8, 20)       # 이때까지는 넥스트레이드 현재가(src 「now」) · 넘으면 그날 08:05 1분봉 종가(src 「1m」)
NX_SKIP = ((8, 55), (9, 40)) # 1분봉 되찾기를 미루는 때 — 판 굳히기 · 다시 세기(BUY_AT ~ BUY_LATE)에 KIS 몫을 비켜선다

_SCHEMA = "CREATE TABLE IF NOT EXISTS dt30 (day TEXT PRIMARY KEY, saved_at TEXT, board TEXT NOT NULL)"
_status = {"frozen": None, "error": None}


def _now():
    return datetime.now(KST)


_late = {"day": None, "at": 0.0, "min": 0}


def late_min(proxy, now=None, day=None):
    """그날 정규장이 보통 날보다 몇 분 늦게 여나 — 0 보통 · 수능(10:00)이면 60. market_hours 표 한 곳 · 못 읽으면 0(보통 날로 본다) · 5분 둘레로 다시 읽음.
    늦게 여는 날은 판의 정규장 시각들(OPEN_AT · 값 적는 시각)을 그만큼 뒤로 민다 — 굳히는 시각(BUY_LATE)은 안 민다(재권님 「가」 11-20 09:0x · 10:30 그대로) —
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
    # 시가총액 문턱 — 감시 목록(dart · 3천억 이상 전부)에 없거나 문턱 아래면 칩 종류와 관계없이 뺀다(아래 return 둘 · _cap_keep).
    # 전에는 「감시 목록에 시총이 있고 문턱 아래」 만 걸러 목록 밖(사실상 3천억 아래) VI·급등 · 매수 어림 종목이 판에 들었다
    # (11-23 09:13 판 16줄 중 12줄 · 재권님 「단타칩에 3천억 미만인 종목들이 많이 걸려있는데 이거 필터링 안되고 있는건가?」 → 「빼고 굳힌거에도 빠져야돼」)
    # 감시 목록을 못 읽었으면(빈 표) 거르지 않는다 — 다 빼면 판이 빈다
    small = lambda c: bool(cap) and (cap.get(c) is None or cap[c] < cap_min_eok())
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
    pf = None
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
    try:                                   # 「미국강세」 — 어제 미국 상위 묶음의 국내 짝 업종 · 테마 종목(셈은 us_kr · 장 전에도 셈 — 미국 값은 밤에 이미 있음 · KIS 안 부름)
        import sector_flow, us_kr
        n_top, today = chip_rules.get("미국강세", "topN"), _now().strftime("%Y%m%d")
        codes = [c for c in cap if not small(c)]
        got_day = False
        for by, ko in (("sector", "업종"), ("theme", "테마")):
            data, _m = us_kr.board(proxy, by)
            d0 = next((d for d in data.get("days") or [] if d["kr"] == today), None)
            prev_wd = _now() - timedelta(days=3 if _now().weekday() == 0 else 1)
            if not d0 or d0["us"] < prev_wd.strftime("%Y%m%d"):
                continue                                   # 어젯밤 미국 일봉이 아직 없음 — 그저께 값으로 조용히 붙이지 않음(미국이 쉰 날도 못 받음으로 · 개념정의 덧 11-25)
            if not any((r.get("us") or {}).get(d0["us"]) is not None for r in data.get("rows") or []):
                continue                                   # 미국 값이 다 빔 — 「칩 0」 이 아니라 못 받음
            got_day = True
            ups = sorted(((r["us"].get(d0["us"]), r["name"]) for r in data.get("rows") or [] if (r["us"].get(d0["us"]) or 0) > 0), reverse=True)[:n_top]
            top = {n for _v, n in ups}
            for name, cs in sector_flow._groups(proxy, by, codes).items():
                if name in top:
                    for c in cs:
                        put(c, None, "미국강세", "%s %s" % (ko, name))
        if not got_day:
            missing.append("미국강세")                   # 오늘 한국 장날 짝이 없음(쉬는 날 · 미국 일봉 못 받음) — 0 이 아니라 못 받음
    except Exception:
        missing.append("미국강세")
    if pre:
        if early and early_buy(proxy, cfg, [c for c in hit if not small(c)], put, pre=True) is not None:
            missing.append("매수어림")                 # build 가 meta.early · approx 로
        else:
            missing.append("매수대기")                 # 장 전에 어림을 하나도 못 받음 — build 가 wait 로
        try:
            pre_log_put(proxy, hit, (pf or {}).get("rows") or [])
        except Exception as e:
            print("  [단타 프리장 기록] 못 씀 — %s" % type(e).__name__, flush=True)
        return _cap_keep(hit, small), missing, cap, mkt
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
    try:                                   # 「거래비율」 · 「거래비율급증」 — 따로 붙는다 (server/vol_chip.py · 재권님 11-23 「각각 칩으로」 · 「두개야」 16:3x)
        import vol_chip
        vb, _ = vol_chip.hits(proxy, cfg)
        for r in vb.get("rows") or []:
            for c in r.get("chips") or []:
                put(r.get("code"), r.get("name"), c)
    except Exception:
        missing.extend(["거래비율", "거래비율급증"])
    try:
        day = _now().strftime("%Y%m%d")
        for it in signal_watch.today_lows(proxy).get("items") or []:
            if str(it.get("ts", ""))[:8] == day and not small(it.get("code")):
                put(it.get("code"), it.get("name"), "볼린저")   # 셈에 안 듦 · 다른 칩 없어도 혼자 붙음(11-25 재권님 「각 칩은 독자로 적용되어야 하는데」 → 「응 해줘」)
    except Exception:
        pass
    if not pre:
        try:                               # 「돈몰림」 — 돈이 몰리는 업종 · 테마 묶음의 종목(셈은 money_chip · 값 칸은 chip_rules 「돈몰림」 · 11-25 재권님 「처음부터 셈이되도록 켜줘」)
            import money_chip
            mh, why = money_chip.hits(proxy, [c for c in cap if not small(c)])
            for c, subs in mh.items():
                for sb in subs:
                    put(c, None, money_chip.CHIP, sb)
            if why:
                missing.append(money_chip.CHIP)
        except Exception:
            missing.append("돈몰림")
        try:                               # 「현재상승」 — 감시 목록(3천억 이상) 전부의 시가 대비 % · 다른 칩 없어도 혼자 붙음(11-25 · 위와 같은 말씀)
            import turnover                # 시세는 turnover 장중 바퀴(TURN_INTERVAL)가 받아 둔 묶음 캐시를 그 나이 안에서 그대로 씀 — 새 호출은 캐시에 없는 종목만
            codes = [c for c in cap if c.isdigit() and len(c) == 6 and not small(c)]
            import market_hours
            age = turnover.TURN_INTERVAL if market_hours.in_regular(proxy) else 24 * 3600   # 정규장 가름은 market_hours 한 곳(쉬는 날 · 늦게 여는 날 · 개념정의 덧 11-25)   # 장 밖(마감 뒤 · 주말 · 쉬는 날)은 값이 안 바뀜 — 들고 있는 값을 쓰고 없는 종목만 한 번 받음(qa 덧 11-25 · 1분마다 27건 새로 부르던 것)
            qs, _ = proxy.fetch_quotes_multi(cfg, codes, max_age=age) if codes else ({}, {})
            for c, q in qs.items():
                if q.get("open") and q.get("price") and (q["price"] / q["open"] - 1) * 100 >= now_rise_pct():
                    put(c, q.get("name"), "현재상승")   # 셈에 안 듦 — 이름만(_live_calc 가 그 바퀴 시세로 다시 봄)
        except Exception:
            missing.append("현재상승")
    return _cap_keep(hit, small), missing, cap, mkt


def _cap_keep(hit, small):
    return {c: g for c, g in hit.items() if not small(c)}


def drop_small(proxy, b):
    """그날 판(굳힌 줄 포함)에서 시가총액 문턱 밖 종목을 뺀다 — 감시 목록에 없거나 문턱 아래 · 감시 목록을 못 읽으면 안 뺌.
    뺀 줄은 meta.capDrop [{code, name, at}] 에 남기고 남은 줄 rank 를 다시 1부터 → 뺀 수(재권님 「빼고 굳힌거에도 빠져야돼」 11-23)."""
    import dart
    cap = {r["stock_code"]: r["market_cap"] for r in dart.universe_rows(None)}
    if not cap:
        return 0
    lo = cap_min_eok()
    out = [r for r in b.get("rows") or [] if cap.get(r["code"]) is None or cap[r["code"]] < lo]
    if not out:
        return 0
    at = _now().strftime("%H:%M:%S")
    b["meta"].setdefault("capDrop", []).extend({"code": r["code"], "name": r.get("name"), "cap": cap.get(r["code"], r.get("cap")), "at": at} for r in out)   # 목록 밖이면 줄의 시총(qa 덧)
    gone = {r["code"] for r in out}
    b["rows"] = [r for r in b["rows"] if r["code"] not in gone]
    for i, r in enumerate(sorted(b["rows"], key=lambda r: r.get("rank") or 1e9)):
        r["rank"] = i + 1
    return len(out)


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
    merged=False(지난 날 다시 세기 · 11-18 전 셈) — 하트 종목은 「관심」(하위 = 든 묶음 이름 · 시가총액 cap_min_eok() 아래 뺌) · 자동 묶음은 「수급」."""
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


def rules_meta(proxy, merged=True):   # 이름 — 칩 룰 표 모듈 chip_rules 를 가리지 않게(11-20)
    """화면 룰 표에 내줄 칩 룰 값 — 자동 관심 룰은 auto_watch 룰 문서 한 곳에서 읽는다.
    merged(11-18 뒤 판) — 「관심」 = 자동 관심 룰 · merged=False(지난 날) — 관심은 이 파일 문턱 · 수급 = 자동 관심 룰."""
    out = {"하락뺌": {"dropBelowPct": drop_below_pct()}}
    if not merged:
        out["관심"] = {"capMinEok": cap_min_eok(), "what": "하트 누른 종목 · 하위는 든 묶음 이름 · 자동 묶음은 수급"}
    key = "관심" if merged else "수급"
    try:
        import auto_watch
        r, src = auto_watch.rules(proxy)
        out[key] = dict(r, src=src, what="자동 관심 룰에 든 종목(하트 안 씀)") if merged else dict(r, src=src)
    except Exception:
        out[key] = None                                 # 못 읽음 — 빈 룰로 두지 않는다
    return out


EARLY_WORKERS = 6
_early_seen = {}              # code → (외국계 창구 순매수, 프로그램 순매수, 프로그램 값 시각) — 가장 최근 early_buy 가 받은 값(프리장 기록 pre_log_put 이 읽음)

# ── 프리장 칩 정보 기록 (2026-11-24 재권님 「프리장에 정보는 필요해 8시부터 8시 50분까지 단타칩에 필요한 정보들은 다 저장해둬야해
#    다만 표기할지 말지만 단타판에서 정의하면 되니 너는 정보를 저장할수있게 코딩해줘」) ──
# 단타 목록 셈(chips_now)이 장 전에 돌 때마다(LIVE_TTL 둘레) 그 분의 값을 종목마다 한 줄 — 칩 · 하위 · 프리장 줄 값(가격 · 등락률 · 거래대금 ·
# 거래량 · 앞 날 대비 · 프로그램 순매수) · 매수 어림이 받은 프로그램 값과 그 시각. 한 번 적은 분은 다시 셈하지 않는다(그 분 마지막 셈이 남음).
# 어떤 칩을 판에 보일지는 단타 판(화면 · 셈 칸)이 정한다 — 여기는 값만 남긴다. 읽기 /api/kis/dt30-pre?day=YYYYMMDD
PRE_LOG_FROM, PRE_LOG_TO = (8, 0), (8, 50)
_PL_SCHEMA = ("CREATE TABLE IF NOT EXISTS dt30_pre_log (day TEXT NOT NULL, hm TEXT NOT NULL, code TEXT NOT NULL, data TEXT NOT NULL, "
              "PRIMARY KEY (day, hm, code))")
PF_KEYS = ("price", "pct", "amt", "vol", "ratio", "program")
# 남기는 날 수는 쌓는 자료 보관 거래일 한 곳(market_hours.KEEP_TRADE_DAYS · 1년) — 그 표에 남은 날 중 최근 그만큼만 두고 앞 날은 그날 처음 적을 때 지운다
# (재권님 「전부다 1년을 쌓는다」 11-23 · 개념정의 덧 11-24 — 달력 366 을 따로 두지 않음)


def _log_prune(conn, table):
    import market_hours
    conn.execute("DELETE FROM %s WHERE day < (SELECT day FROM (SELECT DISTINCT day FROM %s ORDER BY day DESC LIMIT 1 OFFSET ?))" % (table, table),
                 (market_hours.KEEP_TRADE_DAYS - 1,))
_pl_pruned = {"day": None}


def pre_log_put(proxy, hit, pf_rows, now=None):
    """그 분의 프리장 칩 정보를 dt30_pre_log 에 — 쓰는 서버만 · PRE_LOG_FROM~TO 안만 · 적은 줄 수."""
    now = now or _now()
    m = now.hour * 60 + now.minute
    if not (PRE_LOG_FROM[0] * 60 + PRE_LOG_FROM[1] <= m <= PRE_LOG_TO[0] * 60 + PRE_LOG_TO[1]) or not proxy.marketdb.writable():
        return 0
    day, hm = now.strftime("%Y%m%d"), now.strftime("%H%M")
    pf = {_six(r.get("code")): r for r in pf_rows if _six(r.get("code"))}
    out = []
    for code in sorted(set(hit) | set(pf)):
        g, r = hit.get(code) or {}, pf.get(code)
        d = {"at": now.strftime("%H:%M:%S"), "name": g.get("name") or (r or {}).get("name"),
             "chips": sorted(g.get("chips") or []), "subs": g.get("subs") or {}}
        if r:
            d["pf"] = {k: r.get(k) for k in PF_KEYS}
        e = _early_seen.get(code)
        if e:
            d["early"] = {"foreign": e[0], "program": e[1], "programAt": e[2]}
        out.append((day, hm, code, json.dumps(d, ensure_ascii=False)))
    if not out:
        _status["preLogHm"] = day + hm                 # 적을 줄이 없어도 이 분은 셈 — 고리가 20초마다 다시 세지 않게(개념정의 덧 11-25)
        return 0
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_PL_SCHEMA)
        conn.executemany("INSERT OR REPLACE INTO dt30_pre_log (day, hm, code, data) VALUES (?,?,?,?)", out)
        if _pl_pruned["day"] != day:                   # 하루 한 번 — 남기는 날 수를 넘은 앞 날 지움
            _log_prune(conn, "dt30_pre_log")
            _pl_pruned["day"] = day
    _status["preLogHm"] = day + hm                     # 이 분은 적었음 — 고리가 분마다 빈 분을 채우게(11-25)
    return len(out)


def pre_log_get(proxy, day):
    """→ ({code: [{hm, …}]}, 못 읽은 까닭 | None) — 그날 프리장 기록 · 분 순. 표가 아직 없으면(한 번도 안 적힘) ({}, None) ·
    읽다 터지면 ({}, 까닭) — 「없음」 과 「못 잼」 을 가른다(qa 덧 11-24)."""
    try:
        with proxy.db_conn() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'dt30_pre_log'").fetchone():
                return {}, None
            rows = conn.execute("SELECT hm, code, data FROM dt30_pre_log WHERE day = ? ORDER BY hm", (day,)).fetchall()
    except Exception as e:
        return {}, type(e).__name__
    out = {}
    for hm, code, data in rows:
        out.setdefault(code, []).append(dict(json.loads(data), hm="%s:%s" % (hm[:2], hm[2:])))
    return out, None


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
    pga = getattr(proxy, "_program_at", {}) or {}
    for c, fn, pg in got:
        _early_seen[c] = (fn, pg, pga.get(c) if pg is not None else None)
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
# {칩 이름: 점수, "칩|HH:MM 전": 점수, "칩|HH:MM 이후": 점수} 를 읽어 「시가 대비 등락률 높은 순 → 점수 합 큰 순 → 시가총액 순」(sort_rows).
# 표가 비었거나 못 읽으면 지금 셈(칩 수 많은 순). 칩 이름은 화면 chipName 과 같게 — 서버 「수급」 은 화면 「자동」 이라 둘 다 받는다.
# 시각 조건은 그 칩이 처음 붙은 때로 가른다 — VI·급등 은 viAt · surgeAt 중 이른 것, 그 밖은 rows[].chipAt. 시각을 모르면 그 조건은 안 셈.
SCORE_ALIAS = {"수급": "자동"}


def score_table(proxy=None):
    """룰 문서의 점수표 — 숫자 값만 남긴 dict · 비었거나 못 읽으면 None."""
    try:
        import docstore
        d = chip_rules.rules_doc() or {}
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


ORD_KEYS = {                  # 차례 점수 기준 — 룰 문서 rules.dt30.set.ordScore {열쇠: 점수} · 열쇠 이름은 화면(시황분석1 f526d19)과 같게
    "chips": "칩 수(점수표가 있으면 점수 합)", "rise": "초반상승 %", "cap": "시가총액", "floatCap": "풀린 시총",
    "turn": "거래 비율", "turnPrev": "거래 비율 전날 같은 시각 대비", "pre": "오늘 프리장 %"}


def ord_score():
    """룰 문서의 차례 점수 {열쇠: 점수} — 0 이 아닌 숫자만 · 비었거나 못 읽으면 None(지금 차례 그대로)."""
    try:
        import docstore
        d = chip_rules.rules_doc() or {}
        t = (((d.get("rules") or {}).get("dt30") or {}).get("set") or {}).get("ordScore") or {}
    except Exception:
        return None
    t = {k: float(v) for k, v in t.items() if k in ORD_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool) and v}
    return t or None


def _ord_val(r, k):
    if k == "chips":
        return r["score"] if r.get("score") is not None else r.get("n")
    if k == "turnPrev":
        return r.get("turnPrevPct")
    if k == "pre":
        return (r.get("pre") or {}).get("pct") if isinstance(r.get("pre"), dict) else None
    return r.get(k)


def _ord_total(rows, ws):
    """종목마다 Σ 점수 × 그 기준의 판 안 순위 0~1(1등 1 · 꼴찌 0 · 값 없음 0 · 값 있는 종목이 하나면 1) — 재권님 「이거를 옆에 점수로 넣을수 있게하고
    점수가 높은게 순위가 높게 해줘」 → (가)(11-23 09:20 · 시황분석1 창) · 판 안 = 지금 세우는 줄들끼리."""
    tot = {id(r): 0.0 for r in rows}
    for k, w in ws.items():
        vals = [_ord_val(r, k) for r in rows if _ord_val(r, k) is not None]
        m = len(vals)
        for r in rows:
            v = _ord_val(r, k)
            if v is None:
                continue
            i = sum(1 for x in vals if x > v)          # 자기보다 큰 값의 수 — 같은 값끼리는 같은 순위(qa 덧 11-23 · 들어온 차례로 앞이 이기던 것)
            tot[id(r)] += w * (1.0 if m == 1 else 1 - i / (m - 1))
    return tot


def sort_rows(rows, tab, off=0):
    """줄 세우기 한 곳 — 시가 대비 등락률(openRise) 높은 순 → 칩 수(tab 점수표가 있으면 점수 합) 많은 순 → 시가총액 큰 순.
    재권님 「단타 목록 나오는 순서 다시 정의」 → 등락률은 「시가대비」 · 「가로해서 높은 순으로 하고 칩에따라 소팅되면 됨」 → 목록 · 판 굳힘 둘 다 「응」(11-23 13:5x).
    openRise 가 없는 줄(못 잼)은 맨 뒤. rows 를 제자리에서 세우고 order 글을 낸다.
    룰 문서에 차례 점수(ord_score)가 있으면 그 합이 큰 순이 맨 앞 열쇠 · 같으면 위 차례(ordTotal 을 줄에 적음)."""
    orise = lambda r: -(r["openRise"] if r.get("openRise") is not None else -1e9)
    cap = lambda r: -(r["cap"] if r.get("cap") is not None else -1)
    ws = ord_score()
    if tab:
        for r in rows:
            r["scoreBy"] = row_score_by(r, tab, off)
            r["score"] = round(sum(r["scoreBy"].values()), 4)
        base, text = (lambda r: (orise(r), -r["score"], cap(r))), "시가 대비 등락률 높은 순 → 점수 합 큰 순 → 시가총액 순"
    else:
        for r in rows:
            r.pop("score", None)
            r.pop("scoreBy", None)
        base, text = (lambda r: (orise(r), -r["n"], cap(r))), "시가 대비 등락률 높은 순 → 칩 수 많은 순 → 시가총액 순"   # 재권님 11-23 13:5x
    if ws:
        tot = _ord_total(rows, ws)
        for r in rows:
            r["ordTotal"] = round(tot[id(r)], 4)
        rows.sort(key=lambda r: (-r["ordTotal"],) + base(r))
        return "차례 점수 합 큰 순(%s) → %s" % (" · ".join("%s %g" % (ORD_KEYS[k], w) for k, w in ws.items()), text)
    for r in rows:
        r.pop("ordTotal", None)
    rows.sort(key=base)
    return text

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
    rows 는 단타 셈 칩(ov_chips())이 하나 이상 든 종목 전부(하락도 down true 로 남김) · 문턱(둘 이상 · 상위 몇)은 읽는 쪽이 정한다(지금 홈 둘 이상 · 단타 판 하나 이상 · TOP_N)."""
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
    ov = {c: g for c, g in hit.items() if g["chips"] & (set(ov_chips()) | {"현재상승", "볼린저"})}   # 현재상승 · 볼린저 혼자 붙은 종목도 목록에(n 은 0 · 11-25 「각 칩은 독자로」)
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
        if p.get("open") and p.get("price"):                   # 그 바퀴 시세로 다시 가름(chips_now 의 현재상승은 묶음 캐시 값) · 시세를 못 받았으면 chips_now 것 그대로
            chips.discard("현재상승")
            if (p["price"] / p["open"] - 1) * 100 >= now_rise_pct():
                chips.add("현재상승")
        if not chips:
            continue                                           # 혼자 붙었던 현재상승이 이 바퀴 시세로 빠짐
        rows.append({"code": code, "name": g["name"] or p.get("name") or "", "market": mkt.get(code), "cap": cap.get(code), "sector": sec.get(code),
                     "chips": [c for c in ov_chips() + ("현재상승", "볼린저") if c in chips], "subs": g["subs"], "n": len(chips & set(ov_chips())),
                     "price": p.get("price"), "open": p.get("open"), "pct": p.get("pct"), "rise": g.get("rise"),
                     "openRise": round((p["price"] / p["open"] - 1) * 100, 2) if p.get("open") and p.get("price") else None,   # 시가 대비 등락률 — 차례 맨 앞 열쇠(sort_rows)
                     "viAt": g.get("viAt"), "surgeAt": g.get("surgeAt"),
                     "viPx": {"at": g["viAt"], "px": g.get("viPrice"), "src": "vi"} if g.get("viAt") and g.get("viPrice") else None,
                     "down": p.get("pct") is not None and p["pct"] < drop_below_pct()})      # 하락 — 모르면 안 뺀다(재권님 11-12)
    try:
        import turnover
        turnover.fill(rows, prices, proxy)                     # 풀린 시총 · 거래 비율 — 받은 현재가 · 누적 거래대금 그대로(실시간 · 11-23 재권님)
    except Exception as e:
        print("  [거래 비율] 단타 목록 칸 못 셈 — %s" % proxy.safe_message(e, 120), flush=True)   # 칸은 안 붙음(화면은 「못 잼」)
    _cf_live(proxy, now, rows, off)                    # 칩 처음 본 때 — 판 밖 종목까지 날마다(11-23 「응」)
    try:
        chip_log_put(proxy, now, rows, missing)        # 칩 붙음 · 빠짐 기록 — 단타 화면이 불러 셈(11-24 「서버에 적고 단타가 그값을 호출한다」)
    except Exception as e:
        print("  [단타 칩 기록] 못 남김 — %s" % proxy.safe_message(e, 120), flush=True)
    tab = score_table(proxy)
    order = sort_rows(rows, tab, off)
    early = ["매수"] if "매수어림" in missing else []
    data = {"rows": rows, "meta": {
        "at": now.strftime("%H:%M:%S"), "pre": pre, "openAt": "%02d:%02d" % _sh(OPEN_AT, off), "lateMin": off, "viSplit": vi_split(off),
        "missing": [c for c in missing if c not in ("매수어림", "매수대기")],
        "wait": (list(PRE_WAIT) + (["매수"] if "매수대기" in missing else [])) if pre else [],
        "early": early, "approx": list(early),
        "earlyNote": "매수 어림 — 09:00 전은 프로그램 순매수 > 0 만(외국계 창구 장 전 값 없음) · 09:00 뒤는 외국계 창구 · 프로그램 둘 다 > 0" if pre and early else None,
        "candidates": len(ov), "chips": [c for c in ov_chips() if c != "수급"], "minChips": min_chips(proxy),   # 수급은 11-18 관심으로 합쳐짐(지난 판에만)
        "dropBelowPct": drop_below_pct(), "capMinEok": cap_min_eok(), "watchRule": "자동",
        "order": order, "score": tab, "scoreConflict": score_conflicts(tab), "ttl": LIVE_TTL, "turnNote": TURN_NOTE}}
    with _live_lock:
        _live.update(at=time.time(), pre=pre, data=data)
    return data


# ── 칩이 처음 붙은 시각 — 날마다 · 판 밖 목록 종목까지 (2026-11-23) ─────────────────────
# 재권님 「응 전부다 해놔야해」(18:1x · 시황분석1 창) → 안에 「응」(18:4x · 개발2 창). 판 줄 chipAt 은 「판이 처음 본 때」 라 판 밖 종목 · 판에 늦게 든 종목은
# 칩 시각이 없거나 늦었다(지난 판 32일 초반상승 1012 중 19 등 · 시황분석1 잼). 그래서 단타 목록(_live_calc)이 셀 때마다 칩마다 처음 본 때를 표에 남긴다.
#     at   칩 출처의 실제 시각이 있으면 그것(VI · 급등 viAt · surgeAt · 초반상승 첫 봉 끝) · 없으면 서버가 처음 본 때 — src 로 가름
#     수급 「외국계 순매수」 · 「프로그램 순매수」 — 판 줄을 FLOW_NOW_SEC 마다 확인해 처음 순매수(> 0)로 돈 때(src 「1분 확인」)
#     외국인 · 기관 장중 가집계는 KIS 가 하루 네 번만 내 그보다 잘게는 못 셈(영영 · 그 출처로는)
# 지난 판은 셀 수 있는 것만 — VI(vi_day · 정규장 첫 발동) · 초반상승(첫 봉 끝) · 거래비율 · 거래비율급증(5분봉 · vol_past_attach) / 못 채운 칸은 비움(짐작 안 넣음).
_CF_SCHEMA = ("CREATE TABLE IF NOT EXISTS chip_first (day TEXT NOT NULL, code TEXT NOT NULL, chip TEXT NOT NULL, at TEXT NOT NULL, src TEXT, "
              "PRIMARY KEY (day, code, chip))")


def chip_first_put(proxy, day, items):
    """[(code, chip, 「HH:MM:SS」, src)] 를 처음 것만 남긴다(이미 있으면 더 이른 것으로) — 쓰는 서버만 · 남긴 수."""
    if not items or not proxy.marketdb.writable():
        return 0
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_CF_SCHEMA)
        n0 = conn.total_changes
        conn.executemany("INSERT INTO chip_first (day, code, chip, at, src) VALUES (?,?,?,?,?) "
                         "ON CONFLICT(day, code, chip) DO UPDATE SET at = excluded.at, src = excluded.src WHERE excluded.at < chip_first.at",
                         [(day, c, ch, at, src) for c, ch, at, src in items if c and ch and at])
        return conn.total_changes - n0


def chip_first_get(proxy, day, codes=None):
    """{code: {chip: 「HH:MM:SS」}} — 표가 없거나 못 읽으면 {}."""
    try:
        with proxy.db_conn() as conn:
            q, a = "SELECT code, chip, at FROM chip_first WHERE day = ?", [day]
            if codes:
                q += " AND code IN (%s)" % ",".join("?" * len(codes))
                a += list(codes)
            got = conn.execute(q, a).fetchall()
    except Exception:
        return {}
    out = {}
    for c, ch, at in got:
        out.setdefault(c, {})[ch] = at
    return out


def _hms(t):
    t = str(t or "").replace(":", "").replace("~", "")
    return "%s:%s:%s" % (t[:2], t[2:4], t[4:6] or "00") if len(t) >= 4 and t[:4].isdigit() else None


def _cf_live(proxy, now, rows, off):
    """단타 목록 한 바퀴에서 칩 처음 본 때를 남긴다."""
    import open_rise
    hms = now.strftime("%H:%M:%S")
    o_end = _hhmm(OPEN_AT[0] * 60 + OPEN_AT[1] + off + open_rise.BAR_MIN) + ":00"   # 초반상승은 첫 봉이 끝난 때 생긴다
    items = []
    for r in rows:
        for ch in r.get("chips") or []:
            if ch == "VI·급등":
                at = min([x for x in (_hms(r.get("viAt")), _hms(r.get("surgeAt"))) if x] or [hms])
                src = "VI 기록" if r.get("viAt") or r.get("surgeAt") else "서버"
            elif ch == "초반상승":
                at, src = (o_end, "첫 봉 끝") if o_end <= hms else (hms, "서버")
            else:
                at, src = hms, "서버"
            items.append((r["code"], ch, at, src))
    try:
        chip_first_put(proxy, now.strftime("%Y%m%d"), items)
    except Exception as e:
        print("  [단타 30] 칩 처음 시각 못 남김 — %s" % proxy.safe_message(e, 120), flush=True)


# ── 칩 붙음 · 빠짐 기록 (2026-11-24 재권님 「종목별로 칩이 쌓이는 시간과 칩의 셈이 달라지는 시간을 서버에 저장하도록 해서 그걸 단타창에서 호출해야
#    값이 안바뀔거같은데」 → 「서버는 정보만 있고 셈은 화면에서 한다」 → 「서버에 적고 단타가 그값을 호출한다」) ──
# 단타 목록 셈(_live_calc · 쓰는 서버)이 돌 때마다 앞 바퀴와 견주어 종목마다 칩(하위 칩 포함)이 붙거나 빠진 것을 한 건씩 남긴다 —
# 시각(그 바퀴 시각 · 초) · 칩 · 하위 · 붙음/빠짐 · 그 뒤 칩 수(단타 셈 칩) · 그 순간 값(그 바퀴 시세 · 장 전은 프리장 값). 적은 것은 다시 셈하지 않는다.
# 그 바퀴에 못 받은 칩(missing)은 「빠짐」 으로 적지 않는다(못 받음 ≠ 빠짐). 서버가 다시 뜨면 그날 기록을 되짚어 앞 상태를 잡는다(헛 「붙음」 없게).
# 바퀴 사이(LIVE_TTL 둘레) 안에 붙었다 빠진 칩은 못 본다 · 시각은 그 바퀴 시각이라 실제보다 늦을 수 있다. 읽기 /api/kis/dt30-chiplog?day=
_CL_SCHEMA = ("CREATE TABLE IF NOT EXISTS dt30_chip_log (day TEXT NOT NULL, at TEXT NOT NULL, code TEXT NOT NULL, chip TEXT NOT NULL, sub TEXT NOT NULL DEFAULT '', "
              "kind TEXT NOT NULL, n INTEGER, px REAL, PRIMARY KEY (day, at, code, chip, sub, kind))")
_cl = {"day": None, "state": {}}
PX_CHIPS = ("현재상승",)      # 단타 목록 셈이 그 바퀴 시세로 붙이는 칩 — 시세를 못 받은 바퀴엔 빠짐을 안 적음


def _cl_keys(r):
    """줄의 (칩, 하위) 묶음 — 하위가 없으면 하위 ''."""
    out = set()
    subs = r.get("subs") or {}
    for ch in r.get("chips") or []:
        ss = subs.get(ch) or []
        out.add((ch, ""))
        for sb in ss:
            out.add((ch, str(sb)))
    return out


def chip_log_put(proxy, now, rows, missing=()):
    """한 바퀴의 칩 붙음 · 빠짐을 dt30_chip_log 에 — 쓰는 서버만 · 적은 건수."""
    if not proxy.marketdb.writable():
        return 0
    day, at = now.strftime("%Y%m%d"), now.strftime("%H:%M:%S")
    if _cl["day"] != day:
        _cl.update(day=day, state=_cl_replay(proxy, day))
    prev, cur, px = _cl["state"], {}, {}
    for r in rows:
        cur[r["code"]] = _cl_keys(r)
        px[r["code"]] = r.get("price")
    miss = set(missing or ())
    ovs = set(ov_chips())
    out = []
    for code in sorted(set(prev) | set(cur)):
        a, b = prev.get(code, set()), cur.get(code, set())
        no_px = code in cur and px.get(code) is None       # 그 바퀴 시세를 못 받음 — 시세로 붙이는 칩(현재상승)의 빠짐은 못 잼(qa 덧 · 헛 off → on)
        on, off = b - a, {k for k in a - b if k[0] not in miss and not (no_px and k[0] in PX_CHIPS)}
        if not on and not off:
            continue
        keep = (a & b) | on | (a - b - off)            # 못 받은 칩은 그대로 붙은 것으로 둔다
        n = len({k[0] for k in keep if k[0] in ovs})
        for ch, sb in sorted(on):
            out.append((day, at, code, ch, sb, "on", n, px.get(code)))
        for ch, sb in sorted(off):
            out.append((day, at, code, ch, sb, "off", n, px.get(code)))
        if keep:
            prev[code] = keep
        else:
            prev.pop(code, None)
    if not out:
        return 0
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_CL_SCHEMA)
        if not _cl.get("pruned") == day:
            _log_prune(conn, "dt30_chip_log")
            _cl["pruned"] = day
        conn.executemany("INSERT OR IGNORE INTO dt30_chip_log (day, at, code, chip, sub, kind, n, px) VALUES (?,?,?,?,?,?,?,?)", out)
    return len(out)


def _cl_replay(proxy, day):
    """그날 기록을 차례로 되짚어 지금 붙은 (칩, 하위) 상태 — 서버가 다시 떴을 때 앞 상태(없으면 빈 상태)."""
    st = {}
    try:
        with proxy.db_conn() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'dt30_chip_log'").fetchone():
                return st
            for code, ch, sb, kind in conn.execute("SELECT code, chip, sub, kind FROM dt30_chip_log WHERE day = ? ORDER BY at", (day,)):
                (st.setdefault(code, set()).add if kind == "on" else st.setdefault(code, set()).discard)((ch, sb))
    except Exception as e:
        print("  [단타 칩 기록] 그날 앞 상태를 못 되짚음 — 이 바퀴 칩이 「붙음」 으로 한 번 더 적힐 수 있음 · %s" % proxy.safe_message(e, 120), flush=True)
    return {c: s for c, s in st.items() if s}


def chip_log_get(proxy, day, codes=None):
    """→ ({code: [{at, chip, sub, kind, n, px}]}, 못 읽은 까닭 | None) — 시각 순. 표가 아직 없으면 ({}, None) · 지난 날 · 기록 전 날도 그 날 기록만."""
    try:
        with proxy.db_conn() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'dt30_chip_log'").fetchone():
                return {}, None
            q, a = "SELECT at, code, chip, sub, kind, n, px FROM dt30_chip_log WHERE day = ?", [day]
            if codes:
                q += " AND code IN (%s)" % ",".join("?" * len(codes))
                a += list(codes)
            rows = conn.execute(q + " ORDER BY at, code", a).fetchall()
    except Exception as e:
        return {}, type(e).__name__
    out = {}
    for at, code, ch, sb, kind, n, px in rows:
        out.setdefault(code, []).append({"at": at, "chip": ch, "sub": sb or None, "kind": kind, "n": n, "px": px})
    return out, None


def chip_spans_get(proxy, day, codes=None, since=None):
    """→ ({code: {칩: [[「HH:MM」 붙음 | None, 「HH:MM」 빠짐 | None] …]}}, 못 잰 까닭 | None) — dt30_chip_log 의 칩 단위(하위 '') 붙음 · 빠짐을 구간으로.
    빠짐 None = 지금도 붙어 있음 · 붙음 None = 기록 전부터 붙어 있던 칩(buy930_fill 이 처음 붙은 시각으로 채움). 그날 기록이 하나도 없으면(11-24 전 판) ({}, 「그날 기록 없음」)."""
    log, why = chip_log_get(proxy, day, codes)
    if why:
        return {}, why
    if not log:
        return {}, "그날 기록 없음"
    first = min(e["at"] for v in log.values() for e in v)[:5]
    if since and first > since:
        return {}, "그날 기록이 %s 부터 — 그 앞 붙음 · 빠짐 못 잼" % first   # 칩 기록을 만든 날(11-24 14:33 부터)처럼 장 앞이 빈 날
    out = {}
    for code, evs in log.items():
        m = {}
        for e in evs:
            if e["sub"]:
                continue
            sp, t = m.setdefault(e["chip"], []), e["at"][:5]
            if e["kind"] == "on":
                if not sp or sp[-1][1] is not None:
                    sp.append([t, None])
            elif sp and sp[-1][1] is None:
                sp[-1][1] = t
            elif not sp:
                sp.append([None, t])                   # 기록 전부터 붙어 있던 칩의 빠짐 — 빠짐이 두 번 연달아 온 것은 버림(개념정의 덧 11-25)
        out[code] = {k: v for k, v in m.items() if v}
    return out, None


def _spans4(r, ct, cs):
    """줄의 칩 구간 [(「HHMM」 붙음, 「HHMM」 빠짐 | None)] — cs 칩만. 구간 기록이 없는 칩은 지금 붙어 있으면 처음 붙은 때부터 열림 · 빠졌으면 안 셈(화면 시황분석1 과 같은 셈 · 11-25)."""
    e, sp, iv = _in4(r), r.get("chipSpans") or {}, []
    for c in cs:
        s = sp.get(c)
        if s:
            iv += [(a.replace(":", ""), b.replace(":", "") if b else None) for a, b in s if a]   # 붙음 모름 구간은 안 셈(죽지 않게)
        elif c in (r.get("chips") or []):
            iv.append(((ct or {}).get(c) or e or "0000", None))
    return iv


def _nth_live(r, ct, cs, need, lim=None):
    """칩 N개가 「동시에」 붙어 있던 첫 순간 「HHMM」 | None — cs 칩만 · lim 「HHMM」 까지.
    rows[].chipSpans 가 없는 줄(칩 기록 전 판 · 승률 셈)은 예전 셈 — 처음 붙은 시각을 세워 N번째(한 번 붙었던 칩도 셈)."""
    if r.get("chipSpans") is None:
        ts = sorted((ct or {}).get(c) or _in4(r) or "0000" for c in cs)
        return ts[need - 1] if len(ts) >= need else None
    iv = _spans4(r, ct, cs)
    for t in sorted({a for a, _ in iv}):
        if lim and t > lim:
            break
        if sum(1 for a, b in iv if a <= t and (b is None or b > t)) >= need:
            return t
    return None


def _live_at(r, ct, cs, t):
    """t 「HHMM」 에 붙어 있던 칩들의 붙은 시각(오른차순) — chipSpans 가 없는 줄은 예전 셈(t 까지 한 번이라도 붙은 칩)."""
    if r.get("chipSpans") is None:
        return sorted(x for x in ((ct or {}).get(c) or _in4(r) or "0000" for c in cs) if x <= t)
    return sorted(a for a, b in _spans4(r, ct, cs) if a <= t and (b is None or b > t))


def _cf_flow(proxy, day, rows, at):
    """판 줄 수급 지금 값 — 외국계 창구(ff) · 프로그램(pg) 순매수가 처음 > 0 이 된 때."""
    items = []
    for r in rows:
        f = r.get("flowNow") or {}
        if (f.get("ff") or 0) > 0:
            items.append((r["code"], "외국계 순매수", at, "1분 확인"))
        if (f.get("pg") or 0) > 0:
            items.append((r["code"], "프로그램 순매수", at, "1분 확인"))
    try:
        chip_first_put(proxy, day, items)
    except Exception:
        pass


# ── 사는 셈 — 서버 한 곳 (2026-11-23) ─────────────────────────────────────────────
# 재권님 「9시 30분까지 칩이 적용된것들이야 9시 30분에 사는게 아니고」 · 「내가 칩 갯수 바꿀때마다 사는게 바뀌게 되야돼」(시황분석1 창 · 화면 822778f)
# → 셈을 서버 한 곳에(개발2 안 「응 그래」 19:0x). 판 · 승률 표(dt30_win) · 매수 목록(trade_signal)이 이것을 받고 화면은 rows[].buy930 을 받는다.
#     칩        단타 셈 칩(ov_chips) 중 CHIP_UNTIL 까지 붙은 것 — 칩 시각은 chip_times(모르면 판에 든 때 · 그것도 모르면 장 전으로 봄 · 짐작해 빼지 않음)
#     사는 순간  칩 시각을 세워 N번째(N = 셈 칸 rules.dt30.set.minChip · 빈칸 · 0 이면 1) — 모자라면 안 삼(None)
#     사는 값    그 순간이 9시 1분(pxMinAt["1"]) 이하면 9시 1분 값 · 여는 시각 + 1~5분 안이면 그 분 값 · 그 뒤 판에 든 때(그 순간 이후)면 든 때 값(buy) · 아니면 다음 30분 칸 값
#     화면이 끈 칩(브라우저마다)은 서버가 못 본다 — 서버 셈은 칩을 다 켠 것으로 센다
CHIP_UNTIL = (9, 30)


def _hm4(t):
    t = str(t or "").replace(":", "").replace("~", "").strip()
    return t[:4] if len(t) >= 4 and t[:4].isdigit() else ""


def chip_times(b, cf=None):
    """{code: {chip: 「HHMM」}} — 칩이 붙은 가장 이른 시각: 판 줄 chipAt · VI·급등은 viAt · surgeAt · 칩 처음 시각 표(cf = chip_first_get) 중 가장 이른 것 · 모르면 칸 없음."""
    out = {}
    for r in b.get("rows") or []:
        m, f = {}, (cf or {}).get(r["code"]) or {}
        for ch in list(dict.fromkeys(list(r.get("chips") or []) + [k for k in f if k in ov_chips()])):   # 한 번 붙었다 없어진 칩도 그 시각 그대로(재권님 「조건이 달성되면 그 종목은 순위가 고정」 19:2x)
            c = [_hm4((r.get("chipAt") or {}).get(ch)), _hm4(f.get(ch))]
            if ch == "VI·급등":
                c += [_hm4(r.get("viAt")), _hm4(r.get("surgeAt"))]
            c = [x for x in c if x]
            if c:
                m[ch] = min(c)
        out[r["code"]] = m
    return out


def buy_need():
    """사는 순간의 칩 수 N — 셈 칸 rules.dt30.set.minChip(화면과 같은 칸 한 곳) · 빈칸 · 0 · 못 읽음이면 1."""
    try:
        import dt30_win
        return max(1, int(dt30_win._set().get("minChip") or 0))
    except (TypeError, ValueError, ImportError):
        return 1


def buy_until():
    """칩을 세는 끝 — 셈 칸 rules.dt30.set.buyLate930 이 참이면 장 끝까지(09:30 뒤에 찬 종목도 삼) · 없거나 거짓 · 못 읽음이면 CHIP_UNTIL.
    재권님 「살지말지 내가 정할수 있어야해」(11-23 · 시황분석1 화면 bb01c41 과 같은 열쇠)."""
    try:
        import dt30_win
        return (23, 59) if dt30_win._set().get("buyLate930") is True else CHIP_UNTIL
    except ImportError:
        return CHIP_UNTIL


def _in4(r):
    t = str(r.get("buyTs") or "").replace(":", "")
    return t[:4] if len(t) >= 4 and t[:4].isdigit() else _hm4(r.get("buyAt"))


def chips930(r, ct, until=CHIP_UNTIL):
    """그 줄의 단타 셈 칩 중 until 까지 붙은 것 — 시각 모르는 칩은 판에 든 때로 보고(그것도 모르면 남김) 든 때가 until 뒤면 뺀다(개념정의 덧 ② 11-23)."""
    lim, e = "%02d%02d" % until, _in4(r)
    cs = list(dict.fromkeys(list(r.get("chips") or []) + list(ct or {})))    # 판 칩 + 시각이 남은 칩(붙었다 없어진 것)
    return [c for c in cs if c in ov_chips() and not (((ct or {}).get(c) or e or "") > lim)]


def buy_mode():
    """매수 단추 — 셈 칸 rules.dt30.set.buy 「open」(들어온 때 — 판에 든 때 값) · 그 밖 · 빈칸은 칩 N개 찬 때(p1 셈) · 화면 단추와 같은 칸 한 곳(시황분석1 · qa 11-23)."""
    try:
        import dt30_win
        return "open" if dt30_win._set().get("buy") == "open" else "p1"
    except ImportError:
        return "p1"


def buy_point(b, r, ct, need, open_min=None, until=CHIP_UNTIL, mode="p1"):
    """→ {px, at 「HH:MM」, chipAt 「HH:MM」(N번째 칩 시각), need, src} | None — 위 「사는 셈」 한 곳."""
    e = _in4(r)
    T = _nth_live(r, ct, chips930(r, ct, until), need, "%02d%02d" % until)   # 칩 N개가 동시에 붙어 있던 첫 순간(chipSpans 없는 줄은 예전 셈 · 11-25 재권님 「응」)
    if not T:
        return None
    at = (b.get("meta") or {}).get("pxMinAt") or {}
    o = open_min if open_min is not None else OPEN_AT[0] * 60 + OPEN_AT[1]
    p1_ = _hm4(at.get("1")) or _hhmm(o + 1).replace(":", "")
    cpx = (r.get("chipPx") or {}).get("%s:%s" % (T[:2], T[2:])) if r.get("chipPx") is not None else None
    if r.get("chipPx") is not None and not cpx and T > p1_ and (b.get("meta") or {}).get("chipPx", {}).get("ok"):
        return None                                    # 그 분 1분봉 값이 없음 — 어림으로 안 삼(화면과 같게 · 재권님 「산값은 정확해야」) · 장중이면 굳는 1분 남짓을 기다렸다 삼(재권님 「가인데 1분으로 해줘」 11-25)
    if cpx and T > p1_:                                # 칩 N개가 함께 붙은 그 분 1분봉 종가(chipPx) — 어림(30분 칸 · 든 때) 대신(11-25 재권님 「산값은 정확해야」 · 들어온 때 모드도 · 개념정의 덧)
        return {"px": cpx, "at": "%s:%s" % (T[:2], T[2:]), "chipAt": "%s:%s" % (T[:2], T[2:]), "need": need, "src": "칩 찬 분 1분봉 종가"}
    if mode == "open":                                 # 「들어온 때」 — 판에 든 때 값 · 시각(r.buy · buyAt) · 칩 N개 문턱 · 차례는 그대로
        if e and isinstance(r.get("buy"), (int, float)) and r["buy"] > 0:
            return {"px": r["buy"], "at": "%s:%s" % (e[:2], e[2:]), "chipAt": "%s:%s" % (T[:2], T[2:]), "need": need, "src": "들어온 때 값"}
        return None
    at = (b.get("meta") or {}).get("pxMinAt") or {}
    o = open_min if open_min is not None else OPEN_AT[0] * 60 + OPEN_AT[1]
    mh = lambda k: _hm4(at.get(str(k))) or _hhmm(o + k).replace(":", "")

    def mv(k):
        v = (r.get("pxMin") or {}).get(str(k)) or (r.get("px1") if k == 1 else None)
        v = v.get("px") if isinstance(v, dict) else v
        return v if isinstance(v, (int, float)) and v > 0 else None

    hm = lambda x: "%s:%s" % (x[:2], x[2:])
    out = lambda px, a, src: {"px": px, "at": hm(a), "chipAt": hm(T), "need": need, "src": src}
    p1 = mh(1)
    v1 = mv(1) if T <= p1 else None
    if v1:
        return out(v1, p1, "9시 1분 값")
    for k in PX_MIN:                                   # 9시 1분 값이 없는 날(1분봉 11-12 전)은 아래로 흘림 — 든 때 → 다음 30분 칸(화면 0a9603c 와 같게 · 재권님 「응」 20:2x)
        if k == 1 and T <= p1:
            break
        if T <= mh(k):
            v = mv(k)
            if v:
                return out(v, mh(k), "%d분 값" % k)
            break
    if e and e >= T and isinstance(r.get("buy"), (int, float)) and r["buy"] > 0:
        return out(r["buy"], e, "든 때 값")
    for t in b.get("times") or []:
        v = (r.get("px") or {}).get(t)
        if t >= T and isinstance(v, (int, float)) and v > 0:
            return out(v, t, "%s 칸 값" % hm(t))
    return None


def buy930_fill(proxy, b):
    """판 줄마다 rows[].chipTime {칩: 「HH:MM」} · chips930 · buy930(buy_point) · meta.buy930 — 읽을 때마다(저장 안 함).
    빠진 종목(meta.outRows)도 같은 셈 · 같은 차례에 든다 — 한 번 찬 차례가 당겨지지 않게."""
    rows = (b.get("rows") or []) + ((b.get("meta") or {}).get("outRows") or [])
    try:
        cf = chip_first_get(proxy, b["day"], [r["code"] for r in rows])
    except Exception:
        cf = {}
    ct, need, o, until, mode = chip_times(dict(b, rows=rows), cf), buy_need(), _open_min(proxy, b["day"], b), buy_until(), buy_mode()   # 빠진 줄(outRows)의 칩 시각도(개념정의 걸림)
    lm = o - (OPEN_AT[0] * 60 + OPEN_AT[1])
    late = until != CHIP_UNTIL
    if not late and lm > 0:
        until = _sh(CHIP_UNTIL, lm)                    # 늦게 연 날(수능 10:00)은 09:30 마감도 그만큼 뒤(10:30) — 화면 27fe7f9 와 같게 · 시황분석1 덧 11-24
    try:
        sp, why = chip_spans_get(proxy, b["day"], None, _hhmm(o))   # 그날 전부 — 기록 첫 시각을 가르려고(여는 시각 뒤에 시작한 날은 못 잼)
    except Exception as e:
        sp, why = {}, type(e).__name__
    b["meta"]["chipSpans"] = {"ok": True} if not why else {"ok": False, "why": why}   # 못 잼이면 줄에 chipSpans 를 안 싣고 매수 셈은 예전대로(한 번 붙은 칩)
    for r in rows:
        c = ct.get(r["code"]) or {}
        r["chipTime"] = {k: "%s:%s" % (v[:2], v[2:]) for k, v in c.items()}
        if not why:
            s = {k: [list(x) for x in v] for k, v in (sp.get(r["code"]) or {}).items()}
            for k, v in s.items():
                t0 = r["chipTime"].get(k)
                if v[0][0] is None or (t0 and t0 < v[0][0]):
                    v[0][0] = t0 or v[0][0] or "00:00"   # 기록 전부터 붙어 있었거나 처음 붙은 시각이 기록보다 이름 — 첫 구간을 처음 붙은 시각부터
            r["chipSpans"] = s                         # {칩: [[붙음, 빠짐 | None] …]} — 칩 빠진 시각(11-25 재권님 「칩 빠진 시각도 넣어줘」)
    if True:                                           # 구간이 없는 판(11-25 전)도 칩 처음 붙은 분(chipTime)으로 — 산 값 어림(30분 칸)을 없앰(qa 덧 · 재권님 「산값은 정확해야」)
        try:
            st = _chip_px_fill(proxy, b["day"], rows, o)
            if st is None and not any(r.get("chipPx") for r in rows):
                b["meta"]["chipPx"] = {"ok": False, "why": "그날 1분봉 없음"}   # 1분봉이 아예 없는 날 — 줄 칸을 빼고 화면 · 서버 둘 다 옛 어림 셈
                for r in rows:
                    r.pop("chipPx", None)
            else:
                b["meta"]["chipPx"] = {"ok": True, "settledTo": st}   # settledTo 「HH:MM」 — 이 분부터는 아직 굳는 중(열쇠 없음) · 지난 날은 null(다 굳음) · 시황분석1 11-25
        except Exception as e:
            b["meta"]["chipPx"] = {"ok": False, "why": type(e).__name__}
    for r in rows:
        c = ct.get(r["code"]) or {}
        r["chips930"] = chips930(r, c, until)
        r["buy930"] = buy_point(b, r, c, need, o, until, mode)
    got = sorted((r for r in rows if r["buy930"]), key=lambda r: (r["buy930"]["chipAt"], r.get("rank") or 1e9))
    for i, r in enumerate(got, 1):
        r["buy930"]["rank"] = i                        # 산 차례 — 칩 N개 먼저 찬 순(같은 분이면 판 차례) · 한 번 차면 고정 · 뒤에 찬 종목은 아래로(재권님 19:2x 「칩이 먼저찬 순서대로 순위」)
    b["meta"]["buy930"] = {"until": "%02d:%02d" % (CHIP_UNTIL if late else until), "late": late, "lateMin": lm, "need": need, "mode": mode,
                           "note": "칩은 %02d:%02d 까지 붙은 것만 · 칩 %d개가 동시에 붙어 있던 첫 순간에 삼(칩 구간 rows[].chipSpans · 그 구간 기록이 없는 판은 한 번 붙은 칩도 셈) · 산 차례(buy930.rank) = 칩 먼저 찬 순 — 차면 고정 · 뒤에 찬 종목은 아래로 · 몇 종목 살지는 화면 · 그 순간이 9시 1분 이하면 9시 1분 값 · 여는 시각 + 1~5분 안이면 그 분 값 · "
                                   "그 뒤 판에 든 때면 든 때 값 · 아니면 다음 30분 칸 값 · 칩 시각 모르면 판에 든 때(그것도 모르면 장 전) · 화면이 끈 칩은 서버 셈에 안 듦(브라우저마다)" % (tuple(CHIP_UNTIL if late else until) + (need,))}
    return b


_cpx = {}                      # (날, 종목, 「HHMM」) → 1분봉 종가 — 굳은 봉만 들고 있음(그 뒤로는 안 바뀜)
# 굳은 봉 — 그 종목 다음 분 봉이 DB 에 있으면(그 분이 끝난 뒤 받은 것) 앞 봉은 끝 값이다. 칩 1분봉 받기가 매 분 1초에 돌아(chip_live)
# 봉이 끝나고 1분 남짓이면 굳는다 — 재권님 「가인데 1분으로 해줘」(11-25 17:4x · 그 전에는 고정 3분 · 셈 탓에 실제 3~4분)


def _chip_px_fill(proxy, day, rows, o):
    """줄마다 rows[].chipPx {「HH:MM」: 원} — chipSpans 의 붙음 · 빠짐 분마다 그 분 1분봉 종가(정규장 · 여는 시각 ~ 마감 · _m1_px 셈 — 거래 없는 채움 봉은 다음 첫 체결 시가).
    1분봉이 없는 분은 열쇠를 뺀다(0 안 넣음) · 재권님 「산값은 정확해야 할거같은데. 서버에 해당종목의 분봉을 읽어서 셈해야해」(11-25 14:3x) → 개발2 창 「응」."""
    import market_hours
    now = _now()
    live = day == now.strftime("%Y%m%d")              # 오늘 — 종목마다 다음 분 봉이 들어온 봉만(진행 중 봉을 받기가 끝 값으로 다시 쓸 틈 · 개념정의 덧 11-25)
    rc = market_hours.today(proxy, day=day)["reg"][1]   # 그날 정규장 끝 — 늦게 여는 날도 그날 표(개념정의 덧 · 「장 시각으로 셈하는 코드는 늦게 여는 날 그만큼 옮긴다」)
    close = int(rc[:2]) * 60 + int(rc[2:])
    want = {}
    def times_of(r):
        if r.get("chipSpans") is not None:
            return [t for v in r["chipSpans"].values() for a, z in v for t in (a, z)]
        return list((r.get("chipTime") or {}).values())   # 구간 없는 판 — 처음 붙은 시각만
    for r in rows:
        for t in times_of(r):
                    if t:
                        m = int(t[:2]) * 60 + int(t[3:5])
                        if o <= m < close:
                            want.setdefault("%02d%02d" % divmod(m, 60), set()).add(r["code"])
    got = {}
    with proxy.db_conn() as conn:
        for hm, codes in want.items():
            need = [c for c in codes if (day, c, hm) not in _cpx]
            if need and live:                      # 그 뒤 분 봉이 아직 없는 종목은 굳는 중 — 안 읽음
                q = ",".join("?" * len(need))
                need = [c for (c,) in conn.execute("SELECT DISTINCT code FROM candles WHERE period = '1m' AND ts > ? AND ts LIKE ? AND code IN (%s)" % q,
                                                    [day + hm, day + "%"] + need)]
            if need:
                px = _m1_px(conn, day, need, day + hm, "close")
                for c, v in px.items():
                    _cpx[(day, c, hm)] = v
            for c in codes:
                v = _cpx.get((day, c, hm))
                if v:
                    got.setdefault(c, {})["%s:%s" % (hm[:2], hm[2:])] = v
    for r in rows:
        r["chipPx"] = got.get(r["code"], {})
    return (now - timedelta(minutes=1)).strftime("%H:%M") if live else None   # 장중 표시 — 이 분 언저리부터는 굳는 중일 수 있음(종목마다 다음 분 봉이 들어오면 굳음) · 지난 날은 null(다 굳음)


def _out_px(proxy, b, outs):
    """빠진 종목 줄의 비어 있는 시각 칸(px)을 그 시각에 끝난 5분봉 종가로 채운다(pxSrc 「5m」 · 없으면 비움) — 승률 표가 읽을 때만(저장 안 함)."""
    with proxy.db_conn() as conn:
        for r in outs:
            px, src = dict(r.get("px") or {}), dict(r.get("pxSrc") or {})
            for t in b.get("times") or []:
                if px.get(t) is not None:
                    continue
                m = int(t[:2]) * 60 + int(t[2:]) - BAR_MIN
                got = conn.execute("SELECT close FROM candles WHERE period = '5m' AND code = ? AND ts = ?", (r["code"], b["day"] + "%02d%02d" % divmod(m, 60))).fetchone()
                if got and got[0]:
                    px[t], src[t] = got[0], "5m"
            r["px"], r["pxSrc"] = px, src


def bars_get(proxy, day, codes, lo, end):
    """{code: (「1m」 | 「5m」, [[「HH:MM」 봉 시작, 시가, 고가, 저가, 종가], …])} — lo(HHMM) 부터 end(HHMM) 앞까지 · 1분봉이 있으면 1분봉(거래량 0 채움 봉은 뺌) ·
    없으면 5분봉 · 둘 다 없으면 칸 없음 · 값이 빈 봉은 뺀다(0 아님). 봉 줄 · 승률 표 매도 셈이 함께 쓴다."""
    got = {}
    if not codes:
        return got
    with proxy.db_conn() as conn:
        for per in ("1m", "5m"):
            need = [c for c in codes if c not in got]
            if not need:
                break
            a = lo if per == "1m" else "%02d%02d" % divmod((int(lo[:2]) * 60 + int(lo[2:])) // BAR_MIN * BAR_MIN, 60)
            for c, ts, o, h, l, cl, v in conn.execute(
                    "SELECT code, ts, open, high, low, close, volume FROM candles WHERE period = ? AND ts >= ? AND ts < ? AND code IN (%s) ORDER BY ts" % ",".join("?" * len(need)),
                    [per, day + a, day + end] + need):
                if per == "1m" and not v:
                    continue                           # 체결 없이 앞 값으로 채운 봉
                if o and h and l and cl:
                    got.setdefault(c, (per, []))[1].append([ts[8:10] + ":" + ts[10:12], o, h, l, cl])
    return got


def bars_after(per, bs, at):
    """산 시각 at(「HH:MM」)부터의 봉 — 5분봉이면 산 분이 든 봉부터 · 그 첫 봉이 산 분보다 앞에서 시작하면 종가 하나로 줄인다
    (산 앞의 고가 · 저가로 손절 · 고점이 걸리지 않게 · 개념정의 덧 ① 11-23)."""
    if per != "5m":
        return [x for x in bs if x[0] >= at]
    a5 = "%02d:%02d" % divmod((int(at[:2]) * 60 + int(at[3:])) // BAR_MIN * BAR_MIN, 60)
    out = [x for x in bs if x[0] >= a5]
    if out and out[0][0] < at:
        out[0] = [out[0][0], out[0][4], out[0][4], out[0][4], out[0][4]]
    return out


def bars_fill(proxy, b):
    """산 줄(buy930)마다 rows[].bars [[「HH:MM」, 시가, 고가, 저가, 종가], …] · barSrc 「1m」 · 「5m」 · null — 산 분부터 판 끝(times 마지막) 앞까지(bars_get).
    매도 타점을 30분 칸이 아니라 봉으로 — 재권님 「매도에서 해당룰이 적용안되는거 같은데. 3%나 4%를 맞으면 안되는데 이거 왜이래? 매도타점 정확히 계산해」(11-23 19:1x) ·
    「손절이 2%가 넘는건 이유가 뭐지?」(19:4x). 읽을 때만(저장 안 함)."""
    rows = [r for r in (b.get("rows") or []) + ((b.get("meta") or {}).get("outRows") or []) if r.get("buy930")]
    if not rows:
        return 0
    lo = min(r["buy930"]["at"].replace(":", "") for r in rows)
    got = bars_get(proxy, b["day"], [r["code"] for r in rows], lo, (b.get("times") or ["1400"])[-1])
    n = 0
    for r in rows:
        per, bs = got.get(r["code"], (None, []))
        r["bars"] = bars_after(per, bs, r["buy930"]["at"])
        r["barSrc"] = per if r["bars"] else None
        n += bool(r["bars"])
    return n


def live_merge(b):
    """라이브로 굳힌 날을 다시 지은 판(meta.liveBefore 가 있는 판)에 장중에 실제로 적은 값을 되돌린다 — 다시 지은 셈(5분봉 어림)이 덮은 것.
    줄마다(코드로) 매수가 · 든 시각 · 시각 칸 값 · 칩 붙은 시각(앞 것 · 이른 쪽)을 장중 기록으로 · 장중에만 있던 종목은 줄째 되살림 ·
    다시 지어 새로 든 종목(3천억 이상 · 칩 하나라도)은 그대로. meta.liveMerged 를 찍는다 → 되돌린 줄 수.
    재권님 「목록 왜 또 바뀐거지?」(11-24 08:0x) — 0시에 11-23 라이브 판이 다시 지어져 장중 값이 어림으로 바뀌었다."""
    m = b.get("meta") or {}
    lb = m.get("liveBefore") or {}
    if m.get("liveMerged") or not lb.get("rows"):
        return 0
    rows = {r["code"]: r for r in b.get("rows") or []}
    n = 0
    for o in lb["rows"]:
        r = rows.get(o["code"])
        if r is None:
            r = dict(o)                                # 장중에만 있던 종목 — 그 줄 그대로
            r.setdefault("px", {})
            r.setdefault("pxSrc", {})
            b["rows"].append(r)
            rows[o["code"]] = r
        else:
            for k in ("buy", "buyAt", "buyTs", "buySrc", "pct", "rise", "subAt", "viAt", "surgeAt", "viPx", "pxMin", "px1", "turnMin", "volDay"):
                if o.get(k) is not None:
                    r[k] = o[k]                        # 장중에 적은 값 — 든 시각 초(buyTs) · 산 값 출처 · 하위 붙은 시각 · VI 시각까지(개념정의 덧 11-24)
            ca = dict(r.get("chipAt") or {})
            for c, t in (o.get("chipAt") or {}).items():
                if t and (not ca.get(c) or t < ca[c]):
                    ca[c] = t
            r["chipAt"] = ca
            for t, v in (o.get("px") or {}).items():
                if v is not None:
                    r.setdefault("px", {})[t] = v
                    r.setdefault("pxSrc", {})[t] = (o.get("pxSrc") or {}).get(t) or "live"
            r["chips"] = list(dict.fromkeys(list(r.get("chips") or []) + list(o.get("chips") or [])))
        r["live"] = True                               # 장중 판에 있던 줄
        n += 1
    m["liveMerged"] = True
    return n


TRADE_VER = "t1"              # 지난 판 거래 값 셈(_past_trade)이 바뀌면 올린다 — 남은 되채운 판마다 한 번 다시 채운다(meta.tradeVer)
CF_VER = "f1"                 # 칩 시각 공식(chip_first_backfill)이 바뀌면 올린다 — 남은 판마다 한 번 다시 채운다(meta.cfVer)


def chip_first_backfill(proxy, day, b):
    """지난 판 줄 — 셀 수 있는 칩 처음 시각을 표에 · VI 는 vi_day(정규장 · 가장 이른 발동) · 초반상승은 첫 봉 끝(1분봉이 있는 날 1분 · 아니면 5분). 남긴 수."""
    import open_rise
    rows = b.get("rows") or []
    codes = [r["code"] for r in rows]
    if not codes:
        return 0
    lm = (b.get("meta") or {}).get("lateMin")
    lm = lm if isinstance(lm, int) else 0
    items = []
    try:
        with proxy.db_conn() as conn:
            vi = dict(conn.execute("SELECT code, MIN(at) FROM vi_day WHERE day = ? AND regular = 1 AND code IN (%s) GROUP BY code"
                                   % ",".join("?" * len(codes)), [day] + codes).fetchall())
            has1m = conn.execute("SELECT 1 FROM candles WHERE period = '1m' AND ts LIKE ? LIMIT 1", (day + "09%",)).fetchone() is not None
    except Exception:
        vi, has1m = {}, False
    o_end = _hhmm(OPEN_AT[0] * 60 + OPEN_AT[1] + lm + (open_rise.BAR_MIN if has1m else open_rise.PAST_BAR_MIN)) + ":00"
    for r in rows:
        ch = r.get("chips") or []
        if "VI·급등" in ch and vi.get(r["code"]):
            items.append((r["code"], "VI·급등", _hms(vi[r["code"]]), "VI 기록"))
        if "초반상승" in ch:
            items.append((r["code"], "초반상승", o_end, "첫 봉 끝"))
        for c in ("거래비율", "거래비율급증"):
            t = (r.get("chipAt") or {}).get(c)
            if c in ch and t and (r.get("volAt") or b["meta"].get(VOL_MARK)):
                items.append((r["code"], c, t + ":00", "5분봉"))
    items += _cf_formula(proxy, day, b, lm)
    return chip_first_put(proxy, day, items)


def _cf_formula(proxy, day, b, lm=0):
    """기록이 없을 때 칩 시각을 셀 공식 — 재권님 「9시 30분 이후에 붙는 칩들도 다 기록되어야해. 기록이 안되면 계산할 수 있는 공식도 있어야해」(11-23 19:0x).
        프리장    룰 시각 — 프리장 끝(pre_flow.PRE_CLOSE · 08:50) 값으로 고른다
        관심      룰 시각 — 09:01 직전 목록(여는 시각 + 1분 앞 59초)
        매수      그날 칩 판 쌓기(flow_rank joint · first) · 없으면 앞 거래일 확정치로 고른 것이라 장 전(여는 시각 앞 1초)
        볼린저    신호 보낸 때(signal_sent · sent_at 가장 이른 것)
        급등      5분봉 고가가 앞 거래일 종가 대비 SURGE_PCT 를 처음 넘은 봉의 끝(어림 · 5분 단위)
        현재상승  5분봉 종가가 그날 시가 대비 now_rise_pct 를 처음 넘은 봉의 끝(어림)
    표에 더 이른 기록이 있으면 그것이 남는다(chip_first_put 은 이른 것만) · 못 셈 칸은 안 넣는다(짐작 안 함). → [(code, chip, 「HH:MM:SS」, src)]"""
    import intraday_alerts, pre_flow
    rows = b.get("rows") or []
    codes = [r["code"] for r in rows]
    if not codes:
        return []
    o = OPEN_AT[0] * 60 + OPEN_AT[1] + (lm or 0)
    pre_at = "%02d:%02d:00" % pre_flow.PRE_CLOSE
    watch_at = _hhmm(o) + ":59"
    early_at = _hhmm(o - 1) + ":59"
    q = ",".join("?" * len(codes))
    bb, joint, bars, base = {}, {}, {}, {}
    try:
        with proxy.db_conn() as conn:
            for c, t in conn.execute("SELECT code, MIN(sent_at) FROM signal_sent WHERE day = ? AND code IN (%s) GROUP BY code" % q, [day] + codes):
                if t:
                    bb[c] = datetime.fromtimestamp(t, KST).strftime("%H:%M:%S")
            got = conn.execute("SELECT board FROM flow_rank WHERE day = ? AND who = 'joint'", (day,)).fetchone()
            if got:
                for c, v in (json.loads(got[0]).get("acc") or {}).items():
                    h = _hm4((v or {}).get("first"))
                    if h:
                        joint[c] = "%s:%s:00" % (h[:2], h[2:])
            for c, ts, h, cl in conn.execute("SELECT code, ts, high, close FROM candles WHERE period = '5m' AND ts >= ? AND ts < ? AND code IN (%s) ORDER BY ts" % q,
                                             [day + "0900", day + "1530"] + codes):
                bars.setdefault(c, []).append((ts[8:12], h, cl))
            prev = (b.get("meta") or {}).get("prevDay")
            if prev:
                base = {c: v for c, v in conn.execute("SELECT code, close FROM auto_watch_day WHERE day = ? AND code IN (%s)" % q, [prev] + codes)}
    except Exception:
        pass
    end5 = lambda t: _hhmm(int(t[:2]) * 60 + int(t[2:]) + BAR_MIN) + ":00"
    items = []
    for r in rows:
        c, ch = r["code"], r.get("chips") or []
        if "프리장" in ch:
            items.append((c, "프리장", pre_at, "룰"))
        if "관심" in ch:
            items.append((c, "관심", watch_at, "룰"))
        if "매수" in ch:
            items.append((c, "매수", joint.get(c) or early_at, "칩 판 쌓기" if c in joint else "룰"))
        if "볼린저" in ch and c in bb:
            items.append((c, "볼린저", bb[c], "신호 보낸 때"))
        bs = bars.get(c) or []
        if "VI·급등" in ch and base.get(c) and not r.get("viAt"):
            hit = next((t for t, h, _ in bs if h and (h / base[c] - 1) * 100 >= intraday_alerts.SURGE_PCT), None)
            if hit:
                items.append((c, "VI·급등", end5(hit), "5분봉 공식"))
        if "현재상승" in ch and bs:
            op = (r.get("open") or (bs[0][2] if bs else None))
            hit = next((t for t, _, cl in bs if op and cl and (cl / op - 1) * 100 >= now_rise_pct()), None) if op else None
            if hit:
                items.append((c, "현재상승", end5(hit), "5분봉 공식"))
    return items


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
        r = {k: x.get(k) for k in ("code", "name", "market", "cap", "sector", "chips", "subs", "n", "pct", "rise", "open", "openRise", "viAt", "surgeAt", "viPx",
                                   "floatCap", "turn", "turnPrevPct", "turnPrevSrc") + TRADE_KEYS}
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
            "meta": {"rebuilt": False, "missing": list(lm["missing"]), "wait": list(lm["wait"]) if pre else [], "liveAt": lm["at"], "openAt": "%02d:%02d" % _sh(OPEN_AT, off), "lateMin": off, "lockUntil": "%02d:%02d" % BUY_LATE, "lockDef": ["%02d:%02d" % t for t in LOCK_AT], "viSplit": vi_split(off), "watchRule": "자동", "candidates": len(ov), "dropDown": len(down), "downCodes": sorted(down), "dropBelowPct": drop_below_pct(), "rules": rules_meta(proxy), "minChips": mc,
                     "early": ["매수"] if "매수어림" in missing else [], "earlyNote": "매수 어림 — 09:00 전은 프로그램 순매수 > 0 만(외국계 창구 장 전 값 없음) · 09:00 뒤는 외국계 창구 · 프로그램 둘 다 > 0" if pre else None, "approx": ["매수"] if "매수어림" in missing else [], "topN": TOP_N, "capMinEok": cap_min_eok(),
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
        if early_buy(proxy, cfg, [r["code"] for r in b["rows"] if not (r.get("cap") is not None and r["cap"] < cap_min_eok())], put0) is not None:
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
    small = lambda c: rows[c].get("cap") is not None and rows[c]["cap"] < cap_min_eok()
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
                if chip in SUB_KEEP:
                    r.setdefault("subAt", {}).setdefault(chip, {}).setdefault(sub, _now().strftime("%H:%M:%S"))
            if rise is not None:
                r["rise"] = rise
    order = ov_chips() + ("현재상승", "볼린저")
    for r in rows.values():
        r["chips"] = [c for c in order if c in r["chips"]]
        r["n"] = len(set(r["chips"]) & set(ov_chips()))
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


SUB_KEEP = ("매수", "수급")      # 하위가 바뀌어도 앞 하위를 지우지 않는 칩 — 「매수」 ①~④(외국인 · 기관 갈래) · 옛 판 「수급」
# 재권님 「단타판에 수급칩이 외국인이였다나 외국인 기관으로 바뀌면 둘다 있어야해 수급칩은 각각 다 보이게 해주고 추가된 칩은 추가된 시간도 보여지게 해줘」
# (11-20 10:0x · 작업우선순위 경유) — rows[].subs[칩] 은 붙은 차례대로 쌓고 · rows[].subAt {칩: {하위: HH:MM:SS}} 에 처음 붙은 시각(칩 자체가 빠지면 하위도 함께 빠짐 · meta.gone)


def _sub_keep(r, o, ts):
    """다시 셀 때 — r(새 셈 줄)의 SUB_KEEP 하위에 o(옛 줄) 하위를 앞에 이어 붙이고 · 새로 붙은 하위에 시각을 적는다."""
    at = {c: dict(v) for c, v in ((o or {}).get("subAt") or {}).items()}
    for chip in SUB_KEEP:
        if chip not in (r.get("chips") or []):
            continue
        old = list(((o or {}).get("subs") or {}).get(chip) or []) if o and chip in (o.get("chips") or []) else []
        new = list((r.get("subs") or {}).get(chip) or [])
        merged = old + [x for x in new if x not in old]
        if any(x != "어림" for x in merged):
            merged = [x for x in merged if x != "어림"]      # 장 전 자리표 「어림」 은 진짜 하위(①~④)가 오면 걷는다(qa 걸림 11-20)
        r.setdefault("subs", {})[chip] = merged
        r.setdefault("subNow", {})[chip] = new[-1] if new else None   # 지금 셈의 하위 — subs 는 붙은 차례로 쌓여 끝이 지금 등급이 아니다(qa 덧 11-20 · 현대글로비스 ② → ④)
        m = at.setdefault(chip, {})
        if "어림" not in merged:
            m.pop("어림", None)
        first = ((o or {}).get("chipAt") or {}).get(chip) if not m else None   # 시각 기록이 아직 없는 칩(새 코드 전에 붙음) — 첫 하위는 칩이 붙은 시각(HH:MM)으로
        for x in merged:
            m.setdefault(x, first or ts)
            first = None
    r["subAt"] = {c: v for c, v in at.items() if c in (r.get("chips") or []) and v}
    r["subNow"] = {c: v for c, v in (r.get("subNow") or {}).items() if c in (r.get("chips") or [])}


LOCK_AT = ((9, 5), (9, 30), (10, 0))   # 기본 굳힘 시각(셈 칸 rules.dt30.set.lockAt 이 빈 차례 · lock_at() · 재권님 「값이 없으면 9시 5분 9시 30분 10시로 고정되게 하고 값이 있으면 그 값을 오버라이드」 11-20 14:0x) — 세 번 굳히기 — 이 시각마다 굳지 않은 줄 중 순위 위 LOCK_N 개를 굳힌다(lock 1 · 2 · 3)
LOCK_N = 10
# 재권님 「단타 목록 9시 5분에 굳히고 상위 10개만 보인다. 그이후로 추가된건 그아래로 추가되고 9시 30분에 10개 굳힌다. 그이후로 추가된건 그아래로
# 추가되고 10시 30분에 10개 굳힌다」(11-20 08:44) → 새로 다는 10개는 「(가) 그때까지 굳지 않은 종목 전체에서 순위대로」(11-20 10:1x).
# 굳힌 줄은 그날 빠지지 않고(다시 셀 때 빠져도 되살림 · 빠짐 셈 밖) 차례도 그대로 · 마지막(10:30)은 BUY_LATE 와 같아 그 뒤 판이 안 바뀐다.
# 늦게 여는 날은 여는 시각만큼 밀되 BUY_LATE(10:30)를 넘지 않는다 — 수능(10:00)이면 10:05 · 10:30 · 10:30(둘째 · 셋째가 한 바퀴에 차례로)
# (재권님 「나로 해줘」 11-20 10:2x — 「여는 시각만큼 밀어 10:05 · 10:30」 · 마지막은 「가」 굳히기 10:30 그대로). 칸: rows[].lock(1~3) · lockAt · lockRank · meta.lockDone · lockAt · lockN.


WIN_ENDS = ((9, 10), (9, 30), (10, 0), (10, 30), (11, 0))   # 시간 창 끝 — 재권님 「굳힘이 아니고 이걸 필터로 만들어야 할거같은데 9시~30분까지 목록 9시 31~10 00시 10시 31분~11 00시 장중」
                                                            # → 「09시 09시 10분도 추가해주고 그렇게 나누고 해당시간에 필터가 들어온 애들만 적용되게 나누면 돼」 → 안에 「응 해」(11-23 17:2x)
                                                            # 창은 09:00~09:10 · 09:11~09:30 · 09:31~10:00 · 10:01~10:30 · 10:31~11:00 · 그 뒤 「장중」 · 늦게 여는 날은 lateMin 만큼 뒤


def win_bounds(b):
    """그 판의 시간 창 [(번호, 이름, 시작 분, 끝 분 | None)] — 마지막은 「장중」(끝 없음)."""
    lm = (b.get("meta") or {}).get("lateMin")
    lm = lm if isinstance(lm, int) else 0
    out, start = [], OPEN_AT[0] * 60 + OPEN_AT[1] + lm
    for i, (h, m) in enumerate(WIN_ENDS, 1):
        end = h * 60 + m + lm
        out.append((i, "%s~%s" % (_hhmm(start), _hhmm(end)), start, end))
        start = end + 1
    out.append((len(WIN_ENDS) + 1, INTRA_NAME, start, None))
    return out


def _qual_at(r, n, ov):
    """그 줄이 필터(단타 셈 칩 n 개 이상)에 처음 든 시각 「HH:MM」 — 칩 시각(chipAt) 중 n 번째로 이른 것. 칩 시각이 없는 옛 줄은 든 때(_in_hms) · 그래도 없으면 None."""
    ts = sorted(t for c, t in (r.get("chipAt") or {}).items() if c in ov and isinstance(t, str) and re.fullmatch(r"\d\d:\d\d", t))
    if len(ts) >= n:
        return ts[n - 1]
    if not r.get("chipAt") and (r.get("n") or 0) >= n:
        t = _in_hms(r)
        return t[:5] if t else None
    return None


def apply_windows(proxy, b):
    """굳힘 대신 시간 창으로 나눈다 — 줄마다 필터에 처음 든 시각(_qual_at)이 든 창 하나에만(lock = 창 번호 · lockAt = 창 이름 · lockRank = 창 안 차례 · lockTs = 든 시각).
    칩이 늦게 와도 칩 시각으로 다시 나눈다(읽을 때마다 · 같은 판이면 같은 결과) · 아직 문턱 밑인 줄은 묶음 없음(진행 중).
    필터에 든 분이 판에 든 분과 다르면(늦게 온 칩 — 거래비율 등 · 칩이 빠졌다 다시 듦) 산 값을 그 분 1분봉 종가로 — 재권님 안 「산 값은 그 시각 1분봉 값」(17:2x) · 여는 시각 전이면 그대로(9시 1분 값) · 1분봉이 없으면 그대로.
    옮긴 줄 수."""
    rows = b.get("rows") or []
    if not rows:
        return 0
    m = b.setdefault("meta", {})
    n = m.get("minChips") if isinstance(m.get("minChips"), int) else MIN_CHIPS
    ov = set(ov_chips())
    wins = win_bounds(b)
    try:                                               # 칩 처음 시각 표(chip_first)가 판이 처음 본 때보다 이르면 그것으로 — 판 밖에서 먼저 붙은 칩(11-23 「응」)
        cf = chip_first_get(proxy, b["day"], [r["code"] for r in rows])
    except Exception:
        cf = {}
    for r in rows:
        for ch, at in (cf.get(r["code"]) or {}).items():
            if ch in (r.get("chips") or []) and at:
                old = (r.get("chipAt") or {}).get(ch)
                if not old or at[:5] < old:
                    r.setdefault("chipAt", {})[ch] = at[:5]
    open_m = OPEN_AT[0] * 60 + OPEN_AT[1] + ((m.get("lateMin") if isinstance(m.get("lateMin"), int) else 0))
    fix = []
    for r in rows:
        q = _qual_at(r, n, ov)
        old = (r.get("lock"), r.get("lockAt"))
        if not q:
            for k in ("lock", "lockAt", "lockRank", "lockTs"):
                r.pop(k, None)
            r.pop("winAt", None)
        else:
            qm = int(q[:2]) * 60 + int(q[3:])
            w = next((x for x in wins if x[3] is None or qm <= x[3]), wins[-1])
            r["lock"], r["lockAt"], r["winAt"] = w[0], w[1], q
            r["lockTs"] = q + ":00"
            ent = _in_hms(r)
            if ent and qm > open_m and q != ent[:5]:        # 필터에 든 분이 판에 든 분과 다르면(늦게 온 칩으로 앞 · 칩이 빠졌다 다시 들어 뒤) 그 분 값 · 같은 분이면 그대로
                fix.append((r, q))
        r["_moved"] = old != (r.get("lock"), r.get("lockAt"))
    if fix:                                            # 필터에 든 분 ≠ 판에 든 분 — 그 분 1분봉 값
        try:
            with proxy.db_conn() as conn:
                for r, q in fix:
                    px = _m1_px(conn, b["day"], [r["code"]], b["day"] + q.replace(":", ""), "close").get(r["code"])
                    if px:
                        r["buy"], r["buyAt"], r["buyTs"], r["buySrc"] = px, q, q + ":00", "창 1분봉"
        except Exception:
            pass
    for i, _name, _s, _e in wins:
        grp = sorted([r for r in rows if r.get("lock") == i], key=lambda r: r.get("rank") or 1e9)
        for k, r in enumerate(grp, 1):
            r["lockRank"] = k
    moved = sum(1 for r in rows if r.pop("_moved", False))
    m["lockAt"] = [w[1] for w in wins]
    m["windows"] = [{"lock": w[0], "name": w[1], "from": _hhmm(w[2]), "to": _hhmm(w[3]) if w[3] is not None else None} for w in wins]
    m["lockN"] = None                                  # 창에는 종목 수 한도가 없다(필터에 든 것 전부)
    m["lockMode"] = "window"                           # 굳힘(lockDone · 그 시각 스냅숏) 대신 시간 창 — 11-23 17:2x
    _lock_order(b)
    return moved


def _lock_keep(old_rows, nb_rows):
    """다시 셀 때 — 굳힌 줄이 새 셈에서 빠졌으면 옛 줄 그대로 되살린다. 되살린 수."""
    have = {r["code"] for r in nb_rows}
    back = [dict(o) for o in old_rows if o.get("lock") and o["code"] not in have]
    nb_rows.extend(back)
    return len(back)


def _lock_order(b):
    """굳힌 줄(lock · lockRank 차례)을 위에 · 나머지는 지금 순위대로 아래 · rank 를 1부터 다시 매긴다."""
    rows = b.get("rows") or []
    lk = sorted([r for r in rows if r.get("lock")], key=lambda r: (r["lock"], r.get("lockRank") or 1e9))
    rest = sorted([r for r in rows if not r.get("lock")], key=lambda r: r.get("rank") or 1e9)
    b["rows"] = lk + rest
    for i, r in enumerate(b["rows"], 1):
        r["rank"] = i


def lock_at():
    """굳히는 시각 셋 — 룰 문서 strategy-rules 의 셈 칸 rules.dt30.set.lockAt(["HH:MM" 또는 null] 셋 · 재권님이 단타 판 매수 칸 「굳힘 시각」 셋에서 정함(화면 시황분석1) ·
    11-20 「굳힘 시간은 내가 지정하면 바꿀수 있게」 → 「굳힘 시간 3개 넣어야대」). 빈 칸 · 틀린 꼴 · 못 읽음은 그 차례의 LOCK_AT 값. 이른 차례로."""
    try:
        import docstore
        v = ((((chip_rules.rules_doc() or {}).get("rules") or {}).get("dt30") or {}).get("set") or {}).get("lockAt")
    except Exception:
        v = None
    v = v if isinstance(v, list) else []
    out = []
    for i, d in enumerate(LOCK_AT):
        x = v[i] if i < len(v) else None
        ok = isinstance(x, str) and re.fullmatch(r"\d\d:\d\d", x) and int(x[:2]) < 24 and int(x[3:5]) < 60
        out.append((int(x[:2]), int(x[3:5])) if ok else d)
    return tuple(sorted(out))


def _lock_times(b):
    """그날 굳히는 시각들(분) — lock_at() + 그 판의 lateMin · BUY_LATE 를 넘지 않음."""
    lm = (b.get("meta") or {}).get("lateMin")
    lm = lm if isinstance(lm, int) else 0
    cap = BUY_LATE[0] * 60 + BUY_LATE[1]
    return [min(h * 60 + m + lm, cap) for h, m in lock_at()]


INTRA_LOCK = len(WIN_ENDS) + 1  # 「장중」 묶음(시간 창 마지막 · 11-23 17:2x 부터 창 번호) — 원래는 — 마지막 굳힘(BUY_LATE) 뒤 칩에 걸린 종목을 매도 시각까지 판에 더함 · 든 때 가격에 산 것
INTRA_NAME = "장중"            # 재권님 「10시 30분 이후에 걸리는 종목은 10시 30분 옆에 장중 이라고 칸 만들어서 거기에 걸리게 해줘」(11-23 10:3x) → 안에 「응」


def intraday_add(proxy, cfg, b, hm):
    """굳힌 뒤(BUY_LATE 뒤) — 단타 목록(live)에 새로 걸린 종목을 판에 더해 「장중」 묶음으로 → 더한 수.
    문턱은 그날 판 문턱(min_chips)과 장중 칸 칩 조건(lock_cfg 넷째) 중 큰 쪽 · 하락 뺌 · 장중 칸 수(lock_cfg 넷째)까지 · 매도 시각(dt30_win.end_at · 없으면 SELL_AT) 전까지 ·
    매수가는 든 그 순간 현재가(_buy_now) · lockTs · buyAt 은 든 때. RESCAN_SEC 마다 한 번."""
    import dt30_win
    end = dt30_win.end_at() or dt30_win.SELL_AT
    if hm >= int(end[:2]) * 60 + int(end[2:]) or time.time() - _status.get("intra", 0) < RESCAN_SEC:
        return 0
    _status["intra"] = time.time()
    cap_n, min_c = (lock_cfg() + [(LOCK_N, 0)] * (INTRA_LOCK))[INTRA_LOCK - 1]
    have = {r["code"] for r in b.get("rows") or []}
    room = cap_n - sum(1 for r in b.get("rows") or [] if r.get("lock") == INTRA_LOCK)
    if room <= 0:
        return 0
    floor = max(min_chips(proxy), min_c)
    new = []
    for x in live(proxy, cfg)["rows"]:
        if len(new) >= room:
            break
        if x["code"] in have or x["down"] or x["n"] < floor:
            continue
        r = {k: x.get(k) for k in ("code", "name", "market", "cap", "sector", "chips", "subs", "n", "pct", "rise", "open", "openRise", "viAt", "surgeAt", "viPx",
                                   "floatCap", "turn", "turnPrevPct", "turnPrevSrc") + TRADE_KEYS}
        r.update(buy=None, px={}, pxSrc={}, chipAt={c: _now().strftime("%H:%M") for c in x["chips"]})
        new.append(r)
    if not new:
        return 0
    _buy_now(proxy, cfg, new)
    k0 = max([r.get("lockRank") or 0 for r in b["rows"] if r.get("lock") == INTRA_LOCK] + [0])
    for k, r in enumerate(new, k0 + 1):
        ts = r.get("buyTs") or _now().strftime("%H:%M:%S")
        r.update(lock=INTRA_LOCK, lockAt=INTRA_NAME, lockRank=k, lockTs=ts, buyAt=ts[:5])
        _sub_keep(r, None, ts)
    b["rows"].extend(new)
    b["meta"]["intra"] = {"lock": INTRA_LOCK, "name": INTRA_NAME, "from": "%02d:%02d" % BUY_LATE, "until": "%s:%s" % (end[:2], end[2:]),
                          "n": cap_n, "minChip": floor}
    _lock_order(b)
    return len(new)


def lock_cfg():
    """굳힘마다 (굳힐 종목 수, 칩 몇 개 이상) — 룰 문서 셈 칸 rules.dt30.set.lockNs · lockMinChip(굳힘 차례마다 [첫째, 둘째, 셋째] · null 은 기본).
    재권님 「각 굳힘 칸별로 사는 금액과 종목 조건 다르게 셋팅할수 잇게 해줘」 → 종목 조건 「다」(굳힐 종목 수 · 칩 몇 개 이상 둘 다 · 11-23 10:34 · 시황분석1 창 · 열쇠는 화면 셈 칸과 같게).
    기본 — 수는 LOCK_N · 칩 조건 없음(0). 못 읽으면 기본."""
    try:
        import docstore
        S = ((((chip_rules.rules_doc() or {}).get("rules") or {}).get("dt30") or {}).get("set") or {})
    except Exception:
        S = {}
    num = lambda v, lo: int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= lo else None
    ns, mc = S.get("lockNs"), S.get("lockMinChip")
    ns, mc = (ns if isinstance(ns, list) else []), (mc if isinstance(mc, list) else [])
    out = []
    for i in range(len(LOCK_AT) + 1):                  # 굳힘 셋 + 「장중」 칸(INTRA_LOCK)
        n = num(ns[i], 1) if i < len(ns) else None
        c = num(mc[i], 0) if i < len(mc) else None
        out.append((n or LOCK_N, c or 0))
    return out


def _in_hms(r):
    """판에 든 때 「HH:MM:SS」 — buyTs · 없으면 buyAt · 없으면 칩이 처음 붙은 때 · 다 없으면 ''(가장 이름 — 굳힘에서 안 밀림)."""
    t = str(r.get("buyTs") or "")
    if re.fullmatch(r"\d\d:\d\d:\d\d", t):
        return t
    a = str(r.get("buyAt") or "")
    if re.fullmatch(r"\d\d:\d\d", a):
        return a + ":00"
    c = sorted(v for v in (r.get("chipAt") or {}).values() if isinstance(v, str) and re.fullmatch(r"\d\d:\d\d", v))
    return c[0] + ":00" if c else ""


def lock_fix(b):
    """**11-23 17:2x 부터 안 씀** — 굳힘을 시간 창(apply_windows)으로 바꿈. 0 을 낸다.
    굳힘 시각보다 뒤에 든 줄이 그 굳힘에 묶여 있으면 다음 굳힘으로 옮긴다 — 다음 굳힘이 이미 지났으면 그 묶음 끝으로 · 마지막 묶음이면 풂(진행 중).
    11-23 오늘 판 — 09:05 굳힘이 09:05:55 에 돌아 그 바퀴에 든 이수페타시스가 · 09:30 굳힘이 09:30:37 에 돌아 그 바퀴에 든 일곱이 묶였다(재권님 「그 이후에 든 종목은 9시 30분 굳힘 으로 이동되어야지」 → 「응」).
    옮긴 줄 수 · 여러 번 불러도 같다."""
    return 0                                           # 시간 창(apply_windows)이 대신 — 재권님 「굳힘이 아니고 필터로」(11-23 17:2x)
    m = b.get("meta") or {}
    ats, done = list(m.get("lockAt") or []), set(m.get("lockDone") or [])
    n = 0
    for _ in range(len(ats)):
        moved = 0
        for r in sorted(b.get("rows") or [], key=lambda x: -(x.get("lock") or 0)):   # 늦은 묶음부터 — 뒤 묶음 자리를 먼저 비워야 앞 묶음 줄이 들어감
            i = r.get("lock")
            if not i or i > len(ats) or not ats[i - 1] or _in_hms(r) < ats[i - 1] + ":00":
                continue
            j = i + 1
            grp = [x for x in b["rows"] if x.get("lock") == j and x is not r]
            cap_n, min_c = (lock_cfg() + [(LOCK_N, 0)] * 3)[j - 1] if j <= len(ats) else (LOCK_N, 0)
            if j <= len(ats) and j in done and len(grp) < cap_n and (r.get("n") or 0) >= min_c:   # 다음 묶음이 이미 굳었고 자리가 있으면 그 끝으로 — 묶음은 LOCK_N 을 안 넘김(개념정의 덧 11-23)
                r["lock"], r["lockAt"] = j, ats[j - 1]
                r["lockRank"] = max([x.get("lockRank") or 0 for x in grp] + [0]) + 1
                ts = [x.get("lockTs") for x in grp if x.get("lockTs")]
                if ts:
                    r["lockTs"] = min(ts)                  # 그 묶음이 실제로 굳힌 때 — 옛 묶음 시각이 남지 않게(개념정의 덧)
                else:
                    r.pop("lockTs", None)
                r["lockMoved"] = "%s → %s" % (ats[i - 1], ats[j - 1])
            else:
                for k in ("lock", "lockAt", "lockRank", "lockTs"):
                    r.pop(k, None)
                r["lockMoved"] = "%s → 진행 중" % ats[i - 1]   # 다음 굳힘이 아직이거나 자리가 없음 — 다음 굳힘이 든 때 순서로 다시 묶음
            moved += 1
        n += moved
        if not moved:
            break
    for r in b.get("rows") or []:                      # 옮겨진 줄의 lockTs 가 그 묶음 시각보다 앞이면(adff9e2 가 옮긴 판 · qa 11-23 09:49) 그 묶음이 실제로 굳힌 때로
        i = r.get("lock")
        if i and i <= len(ats) and ats[i - 1] and str(r.get("lockTs") or "") < ats[i - 1] + ":00":
            ts = [x.get("lockTs") for x in b["rows"] if x.get("lock") == i and str(x.get("lockTs") or "") >= ats[i - 1] + ":00"]
            if ts:
                r["lockTs"] = min(ts)
                n += 1
    if n:
        _lock_order(b)
    return n


def _lock_due(b, nm):
    """굳힐 때가 지난 차례를 굳힌다 — 굳지 않은 줄 중 순위 위 LOCK_N 개. 굳힌 차례 목록(이번에 한 것)."""
    return []                                          # 시간 창(apply_windows)이 대신 — 재권님 「굳힘이 아니고 필터로」(11-23 17:2x)
    done = list(b["meta"].get("lockDone") or [])
    old_at = list(b["meta"].get("lockAt") or [])         # 이미 굳힌 차례의 시각은 그대로 — 그날 중간에 시각을 바꿔도 지난 묶음 이름이 안 바뀜
    did = []
    at = _lock_times(b)
    for i, t in enumerate(at, 1):
        if i in done or nm < t:
            continue
        _lock_order(b)
        cut = _hhmm(t) + ":00"
        cfg_n, cfg_c = (lock_cfg() + [(LOCK_N, 0)] * 3)[i - 1]
        pick = [r for r in b["rows"] if not r.get("lock") and _in_hms(r) < cut     # 그 굳힘 시각 전에 든 줄만 — 뒤 든 줄은 다음 굳힘(재권님 「응」 11-23 09:4x)
                and (r.get("n") or 0) >= cfg_c][:cfg_n]                            # 굳힘마다 칩 몇 개 이상 · 종목 수(lock_cfg · 11-23 10:34)
        for k, r in enumerate(pick, 1):
            r["lock"], r["lockAt"], r["lockRank"] = i, _hhmm(t), k
            r["lockTs"] = _now().strftime("%H:%M:%S")      # 실제로 굳힌 때 — 서버가 늦게 떠 정한 시각(lockAt)보다 뒤에 굳힌 줄을 가르게(qa 덧 11-20)
        m = b["meta"]
        m.setdefault("lockMiss", {})[str(i)] = {                    # 굳힌 그 순간 못 받은 값 — meta.missing 은 값이 오면 지워져 굳힘 때 무엇이 빠졌는지 못 가린다
            "at": _now().strftime("%H:%M:%S"),                       # 재권님 「못가져온 값은 못가져온대로 … 무슨값인지만 인지되도록」(09:18) → 「9시 5분에 굳히는걸로」(14:19)
            "missing": [c for c in m.get("missing") or [] if c != "매수어림"],   # 못 받은 칩 — 뒤에 오면 그 줄에 채워짐(굳힌 줄은 안 빠짐)
            "approx": list(m.get("approx") or []),                   # 어림 값으로 든 칩(매수 — 장 전 값)
            "wait": list(m.get("wait") or [])}                       # 시각이 안 와 기다리는 칩(초반상승 — 여는 시각 전)
        done.append(i)
        did.append(i)
    if did:
        b["meta"]["lockDone"] = done
        b["meta"]["lockAt"] = [old_at[i - 1] if i in done and i not in did and i - 1 < len(old_at) else _hhmm(t) for i, t in enumerate(at, 1)]
        b["meta"]["lockN"] = LOCK_N
        b["meta"]["lockCfg"] = [{"n": n, "minChip": c} for n, c in lock_cfg()]   # 굳힘마다 쓴 수 · 칩 조건(그때 값)
        _lock_order(b)
    return did


def _close_min(proxy, now=None):
    """그날 정규장 끝(분) — 장 시각 표(market_hours) · 못 읽으면 REG_CLOSE."""
    import market_hours
    now = now or _now()
    try:
        c = (market_hours.today(proxy, day=now.strftime("%Y%m%d"), now=now).get("reg") or ["", ""])[1] or market_hours.REG_CLOSE
    except Exception:
        c = market_hours.REG_CLOSE
    return int(c[:2]) * 60 + int(c[2:4])


def sub_track(proxy, cfg, b):
    """굳힌 뒤에도(BUY_LATE 뒤 · 다시 셈 없음) 「매수」 하위 ①~④ 를 판 줄에 이어 쌓는다 — 매수 판(fetch_joint_buy · 캐시)만 읽음.
    판 안 종목만 · 새 하위는 subs 끝에 · subAt 에 그 시각 · 매수 칩이 없던 줄은 칩을 더하고 chipAt ·
    subNow 에 지금 하위(매수 판에서 빠졌으면 null — 칩 · subs 는 그대로). 바뀐 수.
    재권님 「이거 된거맞아? 중간에 바뀐거같은데 바뀐값이 없네?」(11-20 10:54) — 10:30 굳힌 뒤 다시 셈이 멈춰 하위가 안 쌓이던 것."""
    try:
        jd, _ = proxy.fetch_joint_buy(cfg)
    except Exception:
        return 0
    if not jd or not jd.get("rows"):
        return 0
    tier = {r["code"]: "①②③④"[r["tier"] - 1] for r in jd["rows"] if r.get("tier") in (1, 2, 3, 4)}
    now = _now()
    ts, hm = now.strftime("%H:%M:%S"), now.strftime("%H:%M")
    n = 0
    for r in b.get("rows") or []:
        t = tier.get(r["code"])
        if r.get("cap") is not None and r["cap"] < cap_min_eok():
            continue
        if not t:
            if "매수" in (r.get("chips") or []) and (r.get("subNow") or {}).get("매수") is not None:
                r["subNow"]["매수"] = None                    # 지금 매수 판에 없음 — 칩 · 쌓인 하위는 그대로 둔다
                n += 1
            continue
        if (r.get("subNow") or {}).get("매수") != t:
            r.setdefault("subNow", {})["매수"] = t
            n += 1
        if "매수" not in r["chips"]:
            r["chips"].append("매수")
            r.setdefault("chipAt", {}).setdefault("매수", hm)
            order = ov_chips() + ("현재상승", "볼린저")
            r["chips"] = [c for c in order if c in r["chips"]]
            r["n"] = len(set(r["chips"]) & set(ov_chips()))
        subs = [x for x in (r.setdefault("subs", {}).get("매수") or []) if x != "어림"]
        if t not in subs:
            subs.append(t)
            r.setdefault("subAt", {}).setdefault("매수", {})[t] = ts
            n += 1
        r["subs"]["매수"] = subs
        (r.get("subAt") or {}).get("매수", {}).pop("어림", None)
    return n


def _gone(old_rows, new_rows, at):
    """다시 셀 때 빠진 것 — 판에서 빠진 종목(what 「종목」 · 그때 칩) · 줄은 남고 빠진 칩(what 「칩」 · 빠진 칩만). 빠진 순서대로 목록.
    재권님 「응 고쳐」(11-20 08:59 · 작업우선순위 경유) — 11-19 칩 넷 종목 · 11-02 한진칼이 덮어 저장이라 언제 빠졌는지 못 가린 일."""
    new = {r["code"]: r for r in new_rows}
    out = []
    for o in old_rows:
        n = new.get(o["code"])
        if n is None:
            out.append({"at": at, "code": o["code"], "name": o.get("name"), "what": "종목", "chips": list(o.get("chips") or [])})
        else:
            lost = [c for c in o.get("chips") or [] if c not in (n.get("chips") or [])]
            if lost:
                out.append({"at": at, "code": o["code"], "name": o.get("name"), "what": "칩", "chips": lost})
    return out


FAKE_LOOK_MIN = 10           # 거래량 0 1분봉(체결 없이 앞 값으로 채운 봉)을 건너뛰고 첫 체결 봉을 찾는 폭(분) — 넘으면 못 잼(null)


def _m1_px(conn, day, codes, ts, field):
    """그 분(ts · YYYYMMDDHHMM) 1분봉 값 {code: 값} — field 「close」 · 「open」. 그 봉이 거래량 0 이면(채움 봉 · 옛 값) 건너뛰고
    FAKE_LOOK_MIN 분 안 첫 체결 봉의 시가를 쓴다(첫 체결가). 거래량을 모르는(None) 옛 봉은 그대로 믿는다.
    qa 11-20 찾음 — 11-19(10:00 개장) 여섯 종목 10:00 · 10:01 봉이 거래량 0 · 옛 값(스튜디오드래곤 23,700 ↔ 첫 체결 30,750)이라 매수가가 틀렸다."""
    if not codes:
        return {}
    hi = day + _hhmm(int(ts[8:10]) * 60 + int(ts[10:12]) + FAKE_LOOK_MIN).replace(":", "")
    q = ("SELECT code, ts, open, close, volume FROM candles WHERE period = '1m' AND ts BETWEEN ? AND ? AND code IN (%s) ORDER BY ts"
         % ",".join("?" * len(codes)))
    out, first = {}, {}
    for c, t, o, cl, v in conn.execute(q, [ts, hi] + list(codes)):
        if c in out:
            continue
        if t == ts and v != 0:
            out[c] = cl if field == "close" else o
        elif v != 0 and t > ts:
            out[c] = o                                  # 그 분이 채움 봉이었다 — 첫 체결 봉 시가
    return {c: v for c, v in out.items() if v}


def _px1_of(proxy, day, codes, om):
    """그날 「9시 1분 값」 — 여는 시각(om · 분) 1분봉 종가(= 여는 시각 + 1분의 값 · pxMin "1" 과 같은 셈) · {code: 값} · 없으면 빠짐."""
    if not codes:
        return {}
    ts = day + "%02d%02d" % divmod(om, 60)
    with proxy.db_conn() as conn:
        return _m1_px(conn, day, list(codes), ts, "close")      # 거래량 0 채움 봉은 건너뜀(_m1_px)


def _buy_now(proxy, cfg, rows):
    """판에 막 든 줄(여는 시각 + 1분 뒤) — 매수가를 든 그 순간 현재가로 다시 받는다(시세 묶음 · 가장 짧은 캐시) · buyTs 에 초까지.
    전에는 단타 목록 셈에 실린 값(시세 캐시 PRICE_CACHE_TTL 25초 + 칩 셈 수십 초 앞)이 그대로 매수가가 됐다 —
    재권님 「판에 들어갈때 그때의 가격이 정확히 들어와야해」 · 「판에 들어있으면 9시 1분가격으로 적고 판에 들어오면 들어올때 가격으로」(11-20 09:2x · 작업우선순위 경유).
    못 받은 줄은 셈에 실린 값 그대로 두고 buySrc 「목록 값」."""
    if not rows:
        return 0
    try:
        q, _ = proxy.fetch_quotes_multi(cfg, [r["code"] for r in rows])
    except Exception:
        q = {}
    ts = _now().strftime("%H:%M:%S")
    n = 0
    for r in rows:
        x = q.get(r["code"]) or {}
        v, src = x.get("price"), "현재가"
        if v and x.get("prev") and v == x["prev"] and x.get("open") and x["open"] != x["prev"]:
            # 묶음 시세 현재가가 전일 종가로 옴 · 시가는 다름 — VI 단일가 중 그렇게 왔다(11-23 큐로셀 09:01:12 21,200 · 실제 27,550 상한가 · qa 찾음)
            # 단건 시세로 한 번 더 · 그것도 같으면 쌓인 1분봉 마지막 종가 · 둘 다 없으면 목록 값
            try:
                w = (proxy.fetch_price(cfg, r["code"]) or {}).get("price")
            except Exception:
                w = None
            if w and w != x["prev"]:
                v, src = w, "현재가(단건)"
            else:
                with proxy.db_conn() as conn:
                    m = conn.execute("SELECT close FROM candles WHERE code = ? AND period = '1m' AND ts LIKE ? AND volume > 0 ORDER BY ts DESC LIMIT 1",
                                     (r["code"], _now().strftime("%Y%m%d") + "%")).fetchone()
                v, src = (m[0], "1분봉 종가(시세가 전일 종가로 옴)") if m and m[0] else (None, None)
        r["buyTs"] = ts
        if v:
            r["buy"], r["buySrc"] = v, src
            n += 1
        else:
            r["buySrc"] = "목록 값"
    return n


def _buy_wait_cut(proxy, now=None):
    """이 분(여는 시각 + 1) 전에 판에 든 줄은 「9시 1분 값」 을 기다린다(buyWait) · 그 뒤에 든 줄은 든 순간 현재가."""
    return OPEN_AT[0] * 60 + OPEN_AT[1] + late_min(proxy, now) + 1


def _buy_open_fill(proxy, b):
    """「9시 1분 값」 을 기다리는 줄(buyWait) — 여는 시각 1분봉 종가가 들어왔으면 매수가로 · 1분봉이 없는 종목은 적어 둔 개장 1분 값(px1 · 그때 현재가)으로.
    둘 다 없으면 비워 두고 기다린다 — 지금 값으로 대신 굳히지 않는다(11-20 스튜디오드래곤 · 시세의 시가 칸이 비어 09:03 값 30,800 이 굳은 일). 적은 줄 수."""
    wait = [r for r in b.get("rows") or [] if r.get("buyWait")]
    if not wait:
        return 0
    om = _open_min(proxy, b["day"], b)
    if _now().hour * 60 + _now().minute < om + 1:
        return 0
    got = _px1_of(proxy, b["day"], [r["code"] for r in wait], om)
    n = 0
    for r in wait:
        v, src = got.get(r["code"]), "1m"
        if not v:
            p1 = r.get("px1") or (r.get("pxMin") or {}).get("1") or {}
            v, src = p1.get("px"), p1.get("src")
        if v:
            r["buy"], r["buyAt"], r["buySrc"] = v, _hhmm(om + 1), "9시 1분 값" + ("" if src == "1m" else "(그때 현재가)")
            r.pop("buyWait", None)
            n += 1
    return n


def refresh(proxy, cfg, b):
    """그날 판을 지금 들어온 값으로 다시 세운다(종목 · 칩 · 순위). 바뀐 줄 수."""
    nb = build(proxy, cfg, b["day"])                   # 빠졌던 종목도 다시 셈에 든다(「한 번 빠지면 다시 안 넣음」 없앰 · 11-20)
    _lock_keep(b["rows"], nb["rows"])                  # 굳힌 줄은 새 셈에서 빠져도 그대로(세 번 굳히기)
    old = {r["code"]: r for r in b["rows"]}
    now = _now()
    nm = now.hour * 60 + now.minute
    off = late_min(proxy, now)
    opened = nm >= OPEN_AT[0] * 60 + OPEN_AT[1] + off
    hm = now.strftime("%H:%M")
    hms = now.strftime("%H:%M:%S")
    changed = 0
    for r in nb["rows"]:
        o = old.get(r["code"])
        _sub_keep(r, o, hms)                           # 하위(매수 ①~④)는 바뀌어도 앞 것을 남기고 붙은 시각을 적는다
        if o is not None:
            for k, v in o.items():                     # 다시 세어도 그 줄에 적어 둔 것(팔 때 sell · N분 값 pxMin · 프리장 nx 등)은 옮긴다 — 새 셈이 내는 칸만 새 값
                r.setdefault(k, v)                     # (qa 걸림 11-20 — sell 이 지워져 같은 종목 「팔 때」 가 여러 통 · tgTop 이 빈칸)
            r["chipAt"] = dict(r.get("chipAt") or {}, **{c: t for c, t in (o.get("chipAt") or {}).items() if c in r["chips"]})   # 앞에 붙어 있던 칩은 그 시각 그대로 · 빠진 칩은 지움
            for k in ("px1", "flow", "flowNow"):
                if k in o:
                    r[k] = o[k]                        # 다시 세도 적어 둔 09:01 값 · 수급은 그대로
        if o is not None and o.get("buyWait") and opened:
            # 9시 1분 전에 든 종목 — 매수가는 「9시 1분 값」(_buy_open_fill · 여는 시각 1분봉 종가) · 못 받았으면 비우고 기다림(다음 바퀴 · 굳힌 뒤에도)
            # 전에는 시세의 시가 → 없으면 「지금 값」 으로 굳혔다 — 11-20 스튜디오드래곤 시가 칸이 비어 09:03 값 30,800 이 매수가로 굳음 · 재권님 「판에 들어있으면 9시 1분가격으로」
            r["px"], r["pxSrc"] = o["px"], o["pxSrc"]
            r["buy"], r["buyWait"] = None, True
            r.pop("buySrc", None)
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
    if opened:
        fresh = [r for r in nb["rows"] if r["code"] not in old and not r.get("buyWait")]
        if nm < _buy_wait_cut(proxy, now):
            for r in fresh:                            # 여는 시각 그 분에 든 줄 — 9시 1분 값을 기다린다
                r["buy"], r["buyWait"] = None, True
        else:
            _buy_now(proxy, cfg, fresh)
    changed += len(set(old) - {r["code"] for r in nb["rows"]})
    if opened:
        _buy_open_fill(proxy, nb)
    gone = list(b["meta"].get("gone") or []) + _gone(b["rows"], nb["rows"], hm)   # 빠진 칩 · 종목을 그 시각과 함께 쌓는다(meta.gone)
    have = {r["code"] for r in nb["rows"]}
    outs = {o["code"]: o for o in b["meta"].get("outRows") or [] if o["code"] not in have}   # 다시 든 종목은 뺀다
    for o in b["rows"]:                                # 판에서 빠진 종목은 판 줄이 아니라 meta.outRows 에 그대로 둔다 — 칩 시각 · 산 차례 · 승률이 남게
        if o["code"] not in have:                      # (재권님 「칩이 들어오는 순서를 기억하고 칩의 개수를 조절하면 순위가 소팅되어야함」 11-23 19:3x · 개념정의 덧 ⑥ —
            outs[o["code"]] = dict(o, out=True, outAt=hm, rank=None)   #  판 줄을 도는 곳(수급 · 알림 · 매도 신호 · 차례)은 안 건드림 · 읽는 곳은 buy930_fill · 승률 표 둘)
    b["rows"] = nb["rows"]
    if b.get("times") != nb["times"] and not any(o.get("px") for o in old.values()):
        b["times"] = nb["times"]                       # 값 적는 시각 — 아직 한 칸도 안 적었으면 지금 셈(늦게 여는 날 뒤로 민 시각)으로 · 적기 시작했으면 그대로
    late = b["meta"].get("late") or {}
    keep = {k: v for k, v in (b.get("meta") or {}).items() if k not in nb["meta"]}   # 판에 적어 둔 칸(tgTop · tgTopAt · sellHi · sellChk · px1At · nx…)은 다시 세어도 그대로
    b["meta"] = dict(nb["meta"], late=late, rescanAt=hm, gone=gone)
    for k, v in keep.items():
        b["meta"].setdefault(k, v)
    b["meta"].pop("out", None)                         # 옛 「다시 안 넣음」 목록은 안 옮긴다(규칙 없앰 11-20)
    b["meta"]["outRows"] = list(outs.values())
    _lock_order(b)
    return changed + len(_lock_due(b, nm))            # 굳힌 바퀴는 바뀐 것으로 센다 — 안 세면 저장 안 돼 다음 바퀴에 다시 고름(개념정의 덧 11-20)


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
    if not got:
        return None
    b = json.loads(got[0])
    return b, got[1]                                   # 시간 창(apply_windows)은 걷음 — 읽을 때 바꾼 산 값 · 든 시각이 _store 로 굳지 않게(qa 덧 11-23 · 사는 셈은 buy930_fill 한 곳)


def _store(proxy, b):
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        conn.execute("INSERT OR REPLACE INTO dt30 (day, saved_at, board) VALUES (?,?,?)",
                     (b["day"], _now().strftime("%H:%M:%S"), json.dumps(b, ensure_ascii=False)))
        keep = [d for (d,) in conn.execute("SELECT day FROM dt30 ORDER BY day DESC LIMIT ?", (DAYS_KEEP,))]
        if keep:
            conn.execute("DELETE FROM dt30 WHERE day < ?", (keep[-1],))


NOW_OK_MIN = 10              # 5분봉이 없을 때 현재가로 갈음해도 되는 늦음(분) — 넘으면 그 칸은 「없음」(null)


FLOW_NOW_SEC = 60             # 그날 판 줄의 수급 「지금 값」 다시 받는 간격(초) — 처음 5분(묶음 ③ · 11-18) → 1분(재권님 안 「외국계 · 프로그램 처음 순매수 시각을 1분마다」 「응」 11-23 18:4x · 어림 초당 1건 남짓)
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
#   초반상승   09:00 봉 (종가 − 시가) ÷ 시가 ≥ open_rise.RISE_PCT · 시가총액 cap_min_eok() 이상(라이브와 같은 셈)
#   장외       09:06 에는 비어 있다(라이브와 같다)
#   볼린저     그날 09:06 전에 보낸 바닥 신호(signal_sent) — 칩 이름만
#   매수가     09:05 봉 시가(09:06 값에 가장 가까운 쌓인 값) · pct 는 앞 거래일 종가 대비 · 현재상승은 그 값이 09:00 시가보다 now_rise_pct() 이상
#   시가총액 · 섹터 · 시장은 지금 값이다(그날 값 기록이 없다)
# 5분봉이 쌓인 종목은 순위 목록(코스피 200 · 코스닥 150) 둘레뿐이다 — 그 밖 종목은 칩에 못 든다
BACKFILL_DAYS = 30            # 되채울 거래일 수 — 「지난 30일」 · 보관(DAYS_KEEP)과 갈랐다(11-20 — 보관을 1년으로 늘려도 지난 날 되채움이 한꺼번에 250일로 늘어 KIS 를 몰아 쓰지 않게)
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


PAST_VOL_UNTIL = (10, 30)    # 지난 날 거래비율 · 거래비율급증 칩을 보는 창 끝 — 재권님 「응 만들어 10시 반까지 만들어」(11-23 12:1x) · 지금 판이 다시 세는 끝(BUY_LATE)과 같다


def past_vol_chip(proxy, day, prev, bars, cap, small, put):
    """지난 날 「거래비율」 · 「거래비율급증」 칩 — 09:00 부터 PAST_VOL_UNTIL 까지 5분봉 끝마다 누적으로 센다 · 칩마다 따로 · 처음 넘은 봉 끝 시각을 volAt 에(둘 중 이른 것).
        거래비율급증  그날 누적 거래량 ÷ 앞 거래일 같은 시각까지 누적 × 100 ≥ 칩 룰 거래비율급증.turnPrevPct — 거래 비율 비를 거래량 비로 어림(라이브 5m 셈과 같은 어림)
                     (앞 날 5분봉이 없거나 그 시각까지 한 칸이라도 빠졌으면 그 칸 못 잼 — 0 아님)
        거래비율      그날 누적 거래대금(5분봉 종가 × 거래량 어림) ÷ (풀린 주식수 × 그 봉 종가) × 100 ≥ 칩 룰 거래비율.turnPct(turnover.calc 셈)
               풀린 주식수는 **지금** 값(company_profile.floats · 그날 값은 안 쌓였다) — 어림 · 없으면 그 칸 못 잼
        대상   감시 목록(시가총액 있음 · 문턱 이상) — 라이브(vol_chip)와 같은 가름
    재권님 「거래량 급증은 지난데이터들을 기반으로 뽑아낼수 있지않나?」 → 안에 「응 만들어 10시 반까지 만들어」(11-23 12:1x).
    → {code: 「HH:MM」} · 문턱을 못 읽으면 None(못 셈)."""
    import chip_rules, company_profile, turnover
    try:
        t_pct, p_pct = float(chip_rules.get("거래비율", "turnPct")), float(chip_rules.get("거래비율급증", "turnPrevPct"))
    except Exception:
        return None
    end = PAST_VOL_UNTIL[0] * 60 + PAST_VOL_UNTIL[1] - BAR_MIN
    o_d = OPEN_AT[0] * 60 + OPEN_AT[1] + late_min(proxy, day=day)
    o_p = OPEN_AT[0] * 60 + OPEN_AT[1] + late_min(proxy, day=prev)    # 「같은 시각」 은 연 뒤 같은 분 — 늦게 연 날(수능)과 견줄 때 어긋나지 않게(11-20 이 앞 날 11-19 10:00 개장과 견주어 528종목이 한꺼번에 걸렸다)
    hm = lambda m: "%02d%02d" % divmod(m, 60)
    slots = [(hm(m), hm(m - o_d + o_p)) for m in range(o_d, end + 1, BAR_MIN)]   # (그날 봉, 앞 날 같은 분 봉)
    if not slots:
        return {}
    pvol = {}
    with proxy.db_conn() as conn:
        for code, ts, v in conn.execute("SELECT code, ts, volume FROM candles WHERE period = '5m' AND ts >= ? AND ts <= ?",
                                        (prev + slots[0][1], prev + slots[-1][1])):
            pvol.setdefault(code, {})[ts[8:12]] = v or 0
    try:
        fl = company_profile.floats()
    except Exception:
        fl = {}
    out = {}
    for code, d in bars.items():
        if cap.get(code) is None or small(code):
            continue
        vc = val = pc = 0
        got = set()
        pd = pvol.get(code)
        pgap = False                                   # 앞 날 같은 분 봉이 하나라도 빠졌으면 그 뒤 「전일」 은 못 잼 — 빠진 칸을 0주로 더하면 분모가 작아져 헐겁게 걸린다(개념정의 검수 덧 11-23)
        for hm, phm in slots:
            b = d.get(hm)
            if b:
                vc += b[3] or 0
                val += (b[2] or 0) * (b[3] or 0)
            if pd:
                if phm in pd:
                    pc += pd[phm]
                else:
                    pgap = True
            at = "%02d:%02d" % divmod(int(hm[:2]) * 60 + int(hm[2:]) + BAR_MIN, 60)
            if "거래비율급증" not in got and pd and not pgap and pc > 0 and vc / pc * 100 >= p_pct:
                got.add("거래비율급증")
                out.setdefault(code, at)
                put(code, "거래비율급증", volAt=out[code])
            _c, turn = turnover.calc(b[2] if b else None, val, fl.get(code))
            if "거래비율" not in got and turn is not None and turn >= t_pct:
                got.add("거래비율")
                out.setdefault(code, at)
                put(code, "거래비율", volAt=out[code])
            if len(got) == 2:
                break
    return out


VOL_CHIPS = ("거래비율", "거래비율급증")
VOL_MARK = "volChips2"         # 판 meta 표시 — 두 칩을 붙여 본 판(같은 판을 두 번 안 셈)
CF_MARK = "chipFirst1"         # 판 meta 표시 — 지난 판 칩 처음 시각을 표(chip_first)에 채워 본 판


def _vol_put(b, code, chip, at):
    """굳힌 판의 그 줄에만 칩을 붙인다 — 새 종목 · 차례 · 매수가는 안 건드린다(재권님 「굳히기 개념을 다시 정의했으니 적용해도 상관없지 않아?」 11-23 16:4x ·
    굳힘은 종목 · 매수가 · 차례를 고정하고 칩 · 거래 값은 뒤에 붙는 정보). 붙였으면 True."""
    for r in b.get("rows") or []:
        if r.get("code") == code:
            if chip in r.get("chips") or []:
                return False
            r.setdefault("chips", []).append(chip)
            r.setdefault("chipAt", {}).setdefault(chip, at)
            return True
    return False


def vol_live_attach(proxy, cfg, b):
    """그날 판 줄에 「거래비율」 · 「거래비율급증」 을 값이 나오는 대로 붙인다(굳힌 뒤 · 닫힌 뒤도 그날 안이면) — 재권님 「데이터 받는대로 단타에 적용이 되어야 할거같은데」(11-23 16:4x).
    시각은 판이 처음 본 때(chipAt). 붙인 수."""
    import vol_chip
    try:
        vb, _ = vol_chip.hits(proxy, cfg)
    except Exception:
        return 0
    at = _now().strftime("%H:%M")
    n = sum(_vol_put(b, r.get("code"), c, at) for r in vb.get("rows") or [] for c in r.get("chips") or [])
    if n:
        b["meta"]["missing"] = [c for c in b["meta"].get("missing") or [] if c not in VOL_CHIPS]
    return n


def vol_past_attach(proxy, day, b):
    """지난 판(라이브로 굳혀 두 칩이 없던 날) 줄에 쌓인 5분봉으로 두 칩을 붙인다 — PAST_VOL_UNTIL 까지 · past_vol_chip 과 같은 셈 · 판 순서 그대로.
    앞 거래일이 없으면 None(못 셈 · 표시 안 남김) · 붙인 수."""
    import dart
    prev = (_trade_days(proxy, day, 1) or [None])[0]
    if not prev:
        return None
    cap = {r["stock_code"]: r["market_cap"] for r in dart.universe_rows(None)}
    for r in b.get("rows") or []:
        cap.setdefault(r.get("code"), r.get("cap"))   # 감시 목록에서 빠진 종목도 판 줄에 적힌 시가총액으로(판 줄만 보므로 문턱은 안 다시 봄)
    codes = {r.get("code") for r in b.get("rows") or []}
    with proxy.db_conn() as conn:
        bars = {}
        for code, ts, o, h, c, v in conn.execute(
                "SELECT code, ts, open, high, close, volume FROM candles WHERE period = '5m' AND ts >= ? AND ts <= ?",
                (day + "0800", day + "1400")):
            if code in codes:
                bars.setdefault(code, {})[ts[8:12]] = (o, h, c, v)
    if not bars:
        return None
    n = [0]
    for r in b.get("rows") or []:                     # 옛 이름 「거래량급증」(11-23 낮 몇 시간) — 두 칩으로 갈음하므로 걷는다(개념정의 덧 ③)
        if "거래량급증" in (r.get("chips") or []):
            r["chips"] = [c for c in r["chips"] if c != "거래량급증"]
            (r.get("subs") or {}).pop("거래량급증", None)
            (r.get("chipAt") or {}).pop("거래량급증", None)

    def put(code, chip, sub=None, volAt=None, **kw):
        n[0] += _vol_put(b, code, chip, volAt)

    if past_vol_chip(proxy, day, prev, bars, cap, lambda c: False, put) is None:
        return None
    b["meta"][VOL_MARK] = _now().strftime("%Y-%m-%d %H:%M")
    ap = b["meta"].setdefault("approx", [])
    for c in VOL_CHIPS:
        if c not in ap:
            ap.append(c)                               # 풀린 주식수는 지금 값 · 거래대금은 5분봉 종가 × 거래량 어림 · 전날 대비는 거래량 비
    return n[0]


def vol_past_sweep(proxy, today):
    """남긴 판(지난 판 · 닫힌 오늘 판) 중 두 칩을 안 붙여 본 날을 한 번씩 — 붙인 날 수."""
    k = 0
    for d in days(proxy):
        if d > today:
            continue
        got = _load(proxy, d)
        if not got or (d == today and not got[0].get("closed")):
            continue                                   # 오늘 판은 닫힌 뒤(14:00 칸) 한 번 — 10:30 까지 쌓인 봉으로 칩 시각을 채우고, 그 뒤는 vol_live_attach 가 나오는 대로
        b = got[0]
        m = b.get("meta") or {}
        did = False
        if VOL_MARK not in m and vol_past_attach(proxy, d, b) is not None:
            did = True
        if CF_MARK not in m and d < today:             # 지난 판 칩 처음 시각(셀 수 있는 것만 · 11-23 「응」) — 표에 남기고 판에 표시
            chip_first_backfill(proxy, d, b)
            b.setdefault("meta", {})[CF_MARK] = _now().strftime("%Y-%m-%d %H:%M")
            did = True
        if did:
            _store(proxy, b)
            k += 1
    return k


def rebuild(proxy, day, prev, cfg=None):
    """day 의 09:06 판을 쌓인 값으로 다시 센다(prev = 앞 거래일). 5분봉이 없으면 None. cfg 를 주면 VI 를 KIS 에서 받는다."""
    import auto_watch, company_profile, dart, intraday_alerts, market_hours, open_rise, pre_flow
    uni = dart.universe_rows(None)
    cap = {r["stock_code"]: r["market_cap"] for r in uni}
    if not cap:
        return None                                    # 감시 목록을 못 읽으면 다시 짓지 않는다 — 다 「시총 모름」 으로 빠진 빈 판이 allRows 로 굳지 않게(개념정의 덧 11-23)
    mkt = {r["stock_code"]: r["market"] for r in uni}
    small = lambda c: cap.get(c) is not None and cap[c] < cap_min_eok()
    off = late_min(proxy, day=day)                     # 그날 늦게 열었으면(수능 10:00) 봉 시각 · 시각 칸 · VI 창을 그만큼 뒤로 — 장중 판과 같게
    S = lambda hm: "%02d%02d" % _sh((int(hm[:2]), int(hm[2:])), off)   # (재권님 「이건 값을 왜 못가져오는데?」 11-19 판 → 「응 그렇게 해」 11-24 09:5x)
    with proxy.db_conn() as conn:
        bars = {}
        for code, ts, o, h, c, v in conn.execute(
                "SELECT code, ts, open, high, close, volume FROM candles WHERE period = '5m' AND ts >= ? AND ts <= ?",
                (day + "0800", day + S("1400"))):
            bars.setdefault(code, {})[ts[8:12]] = (o, h, c, v)
        if not any(S("0900") in b for b in bars.values()):
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
                                         (day, int(day + S("0906"))))]
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

    watch_src = "지금 룰"                                  # 관심 — 하트(손으로 담은 것)는 빼고 앞 거래일 장 마감 값에 지금 자동 관심 룰(11-25 재권님 「1. 관심은 지금룰로만 적용한다」 → 개발2 창 「응 그렇게 해」)
    try:                                                   # 그날 장중 실시간 넣기(상위 ADD_TOP)는 쌓지 않아 다시 못 셈 — approx 「관심」 · meta note
        approx.append("관심")
        live = {"day": prev, "frac": 1, "at": "", "got": {c: {"name": r[1], "close": r[2], "pct": r[3], "vol": r[4]} for c, r in pv.items()}}
        res = auto_watch.compute(proxy, live=live, us_before=day)    # 미국 섹터 조건은 판 날 아침에 본 미국장(판 날 앞 마지막 미국 일봉) — 섹터 룰 뜻이 「어젯밤 미국」 (qa 11-25)
        if not res.get("ready"):
            raise ValueError("관심 룰 못 읽음")             # 룰을 못 읽으면 「없음」 이 아니라 「못 셈」
        for r in res.get("picked") or []:
            if not r.get("nearHighOnly"):                  # 조건 밖인데 신고가 부근이라 더 붙은 종목은 관심 목록에 안 넣는다(auto_watch.apply_watch 와 같게)
                put(r["code"], "관심")
    except Exception:
        missing.append("관심")
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
    late = PAST_LATE[0] * 60 + PAST_LATE[1] + off - BAR_MIN       # VI · 급등은 굳히는 때(BUY_LATE)까지 본다 — 그날 판이 09:35 까지 다시 세며 넣는 것과 같게
    vi_bars = ["%02d%02d" % divmod(m, 60) for m in range(9 * 60 + off, late + 1, BAR_MIN)]   # (재권님 「vi가 왜 안나오지?」 11-12 → 「응」 11-13 · 전에는 09:00 · 09:05 봉 · 09:01 까지라 28 → 1)
    for c, d in bars.items():                              # 급등
        base = base_of(c)
        hi = max([d[hm][1] for hm in vi_bars if hm in d and d[hm][1]] or [0])
        if base and hi and (hi / base - 1) * 100 >= intraday_alerts.SURGE_PCT:
            first = next(hm for hm in vi_bars if hm in d and d[hm][1] and (d[hm][1] / base - 1) * 100 >= intraday_alerts.SURGE_PCT)
            put(c, "VI·급등", "급등", surgeAt=first[:2] + ":" + first[2:] + "~", surgeApprox=True)   # 5분봉이라 그 봉 시작 시각(5분 단위 어림 · 「~」)
            if c not in pv:
                approx_base["급등"] += 1                   # 어림 종가(앞 날 5분봉)로 센 급등
    if cfg:                                                # VI — KIS 「VI 현황」 에 날짜 · 종목을 넣으면 그 종목의 그날 VI(최근 것부터 30건)가 온다(19:4x 잼)
        vt = "%02d%02d00" % _sh(PAST_LATE, off)
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
                             if S("0900") + "00" <= h <= vt), key=lambda x: x[0])   # 앞 0 이 빠진 시각(「93012」)도 맞게 견준다(qa 덧 11-18)
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
        b = d.get(S("0900"))
        cp = cap.get(c)
        if b and b[0] and b[2] is not None and cp is not None and cp >= cap_min_eok():
            pct = (b[2] - b[0]) / b[0] * 100
            if pct >= open_rise.PAST_RISE_PCT:             # 지난 날은 첫 5분봉 2% 셈 그대로(1분봉은 11-12 부터만)
                put(c, "초반상승", rise=round(pct, 2))
    vol_at = past_vol_chip(proxy, day, prev, bars, cap, small, put)   # 거래비율 · 거래비율급증 — 09:00~PAST_VOL_UNTIL 거래 비율 · 같은 시각 대비(어림)
    if vol_at is None:
        missing.extend(["거래비율", "거래비율급증"])
    else:
        approx.extend(["거래비율", "거래비율급증"])        # 풀린 주식수는 지금 값 · 거래대금은 5분봉 종가 × 거래량 어림 · 전날 대비는 거래량 비
    for c in bb:
        if c in hit:
            hit[c]["chips"].add("볼린저")
    sec = company_profile.sectors()
    rows, down = [], 0
    for code, g in hit.items():
        if not g["chips"] & set(ov_chips()):
            continue
        if cap.get(code) is None or cap[code] < cap_min_eok():
            continue                                   # 시가총액 문턱(cap_min_eok · 3천억) 아래 · 감시 목록 밖(ETF · 작은 종목) — 칩이 붙어도 판 밖(drop_small 과 같은 가름 · qa 덧 11-23)
        d = bars.get(code) or {}
        buy = (d.get(S("0905")) or (None,))[0]
        base = base_of(code)
        if buy and base and (buy / base - 1) * 100 < drop_below_pct():
            down += 1                                  # 하락 뺌 — 09:05 봉 시가가 앞 거래일 종가 아래
            continue
        o9 = (d.get(S("0900")) or (None,))[0]
        chips = set(g["chips"])
        if buy and o9 and (buy / o9 - 1) * 100 >= now_rise_pct():
            chips.add("현재상승")
        px, src = {}, {}
        for t in times(off):
            m = int(t[:2]) * 60 + int(t[2:]) - BAR_MIN
            b = d.get("%02d%02d" % divmod(m, 60))
            px[t], src[t] = (b[2], "5m") if b and b[2] is not None else (None, "none")
        rows.append({"code": code, "name": g["name"], "market": mkt.get(code), "cap": cap.get(code), "sector": sec.get(code),
                     "chips": [c for c in ov_chips() + ("현재상승", "볼린저") if c in chips], "subs": g["subs"],
                     "n": len(chips & set(ov_chips())), "buy": buy,
                     "pct": round((buy / base - 1) * 100, 2) if buy and base else None, "rise": g.get("rise"),
                     "openRise": round((buy / o9 - 1) * 100, 2) if buy and o9 else None,   # 시가 대비 등락률 — 09:05 봉 시가 ÷ 09:00 봉 시가(되채움 · 차례 열쇠)
                     "viAt": g.get("viAt"), "surgeAt": g.get("surgeAt"), "volAt": g.get("volAt"), "surgeApprox": g.get("surgeApprox"), "viPx": g.get("viPx"),
                     "px": px, "pxSrc": src})
    tab = score_table(proxy)
    order = sort_rows(rows, tab, off)                  # off — 그날 늦게 열었으면 VI·급등 나누는 시각도 그만큼 뒤(개념정의 덧 11-19 — 그날 판과 같게)
    for i, r in enumerate(rows):                       # 지난 판은 자르지 않는다 — 문턱 이상 · 칩 하나라도 든 종목 전부(굳힘 문턱 밑은 lock 없이 · 화면이 칩 · 룰을 바꿔 다시 셀 수 있게)
        r["rank"] = i + 1                              # (재권님 「3000억 이상 모든종목 넣으라고 했는데」 11-23 18:5x · 되채움 카드 ⑨)
    trade_ok = _past_trade(proxy, day, prev, rows)
    approx.append("거래값") if trade_ok else missing.append("거래값")
    return {"day": day, "buyAt": "%02d:%02d" % _sh(PAST_BUY_AT, off), "times": times(off), "rows": rows, "closed": True,
            "meta": {"rebuilt": True, "lateMin": off if market_hours.doc_ok() is not False else None,
                     # openAt — 장 시각 못 잼이면 여는 시각도 null(보통 날 09:00 으로 둔갑시키지 않음 · qa 덧 11-24)
                     "openAt": "%02d:%02d" % _sh(OPEN_AT, off) if market_hours.doc_ok() is not False else None, "viSplit": vi_split(off), "missing": missing, "approx": approx, "prevDay": prev, "candidates": len(hit), "topN": TOP_N, "dropDown": down, "dropBelowPct": drop_below_pct(),
                     "watchSrc": watch_src, "rules": rules_meta(proxy, merged=False), "viUntil": "%02d:%02d" % _sh(PAST_LATE, off), "volUntil": "%02d:%02d" % PAST_VOL_UNTIL, "approxBase": approx_base,
                     "capMinEok": cap_min_eok(), "allRows": True, "tradeVer": TRADE_VER, "order": order, "score": tab, "scoreConflict": score_conflicts(tab),
                     "note": "쌓인 값으로 다시 셈(VI 만 KIS) · 관심 · 수급은 그날 09:01 직전 관심 목록(watchSrc 기록 · 없으면 관심 못 받음 · 수급 어림) · 프리장 · 매수는 어림(dt30.py 「지난 날 되채우기」) · "
                             "buy 는 09:05 봉 시가(늦게 연 날은 그만큼 뒤 · meta.lateMin) · 시가총액 · 섹터 · 시장은 지금 값"}}


def _past_trade(proxy, day, prev, rows):
    """지난 판 줄의 거래 값 칸(TRADE_KEYS) — 정규장(market_hours.REG_OPEN ~ REG_CLOSE) 5분봉으로 어림해 채운다 · 그날 끝 ÷ 앞 거래일 끝.
    accValue · prevDayValue 는 5분봉 종가 × 거래량 합(억원 · 어림) · prevSameSrc 「5m」 · 봉이 하나도 없는 종목 · 앞 날 봉이 없는 칸은 null(0 아님).
    풀린 시총 · 거래 비율(floatCap · turn · turnPrevPct)은 지금 풀린 주식수 × 그날 종가로 어림(turnApprox true · 재권님 「응」 11-23 20:2x) — 그날 유통주식 기록이 없어서.
    → 셈을 했나(봉을 못 읽으면 False)."""
    import market_hours
    codes = [r["code"] for r in rows]
    if not codes:
        return True
    tot = {}
    try:
        with proxy.db_conn() as conn:
            for d in (day, prev):
                for code, c, v in conn.execute(
                        "SELECT code, close, volume FROM candles WHERE period = '5m' AND ts >= ? AND ts < ? AND code IN (%s) ORDER BY ts" % ",".join("?" * len(codes)),
                        [d + market_hours.REG_OPEN, d + market_hours.REG_CLOSE] + codes):
                    t = tot.setdefault((d, code), [0, 0.0, None])
                    t[0] += v or 0
                    t[1] += (c or 0) * (v or 0)
                    if c:
                        t[2] = c                       # 그날 마지막 5분봉 종가
    except Exception:
        return False
    pct = lambda a, b: round(a / b * 100, 1) if a is not None and b else None
    try:
        import company_profile, turnover
        fl = company_profile.floats()                  # 풀린 주식수 — 지금 값(그날 값은 안 쌓였다 · 어림 · 재권님 「응」 11-23 20:2x)
    except Exception:
        fl, turnover = {}, None
    for r in rows:
        a, p = tot.get((day, r["code"])), tot.get((prev, r["code"]))
        av, aa = (a[0], round(a[1] / 1e8, 1)) if a else (None, None)
        pv, pa = (p[0], round(p[1] / 1e8, 1)) if p else (None, None)
        r.update(accVol=av, accValue=aa, prevDayVol=pv, prevDayValue=pa, prevSameVol=pv, prevSameSrc="5m" if p else None,
                 volPrevPct=pct(av, pv), valuePrevPct=pct(a[1], p[1]) if a and p else None)   # 대금 비는 반올림 전 값으로
        f = fl.get(r["code"])
        if turnover and f and a and a[2]:              # 풀린 시총 = 지금 풀린 주식수 × 그날 종가 · 거래 비율 = 그날 거래대금 ÷ 풀린 시총 · 전날 대비 = 두 날 거래 비율 비(어림)
            r["floatCap"], r["turn"] = turnover.calc(a[2], a[1], f)
            pt = turnover.calc(p[2], p[1], f)[1] if p and p[2] else None
            r["turnPrevPct"], r["turnPrevSrc"] = (round(r["turn"] / pt * 100, 1), "5m") if r["turn"] is not None and pt else (None, None)
            r["turnApprox"] = True
    return True


def _redo_gone(proxy, day, b):
    """지난 날을 다시 셀 때 덮이는 옛 판과 갈린 것 — meta.redoGone [{at 「MM-DD HH:MM」 · gone(_gone 꼴) · came(새로 든 코드)}] · 다시 셀 때마다 이어 쌓는다."""
    got = _load(proxy, day)
    if not got:
        return
    old = got[0]
    at = _now().strftime("%m-%d %H:%M")
    oc = {r["code"] for r in old.get("rows") or []}
    hist = list((old.get("meta") or {}).get("redoGone") or [])
    hist.append({"at": at, "gone": _gone(old.get("rows") or [], b["rows"], at),
                 "came": [r["code"] for r in b["rows"] if r["code"] not in oc]})
    b["meta"]["redoGone"] = hist


ALL_ROWS_SINCE = "20261124"   # 이 날 앞 판 중 줄을 자르던 것만 한 번 다시 짓는다 — 「3천억 이상 칩 든 종목 전부」 가 들어온 날(11-23 재권님 · 되채움 카드 ⑨)


M1_FILL_SPAN = 40             # 지난 판 1분봉 되받기 — 여는 시각 + 이 분까지(120줄 한 번이면 그 앞 두 시간) · 여는 값(PX_MIN) · 지난 날 VI 창(PAST_LATE)을 덮음


def m1_fill(proxy, cfg, limit=BACKFILL_DAYS):
    """지난 판(오늘 앞 limit 날) 줄 중 여는 시각 1분봉이 없는 종목 — KIS 지난 날 분봉을 한 번씩 받아 1분봉으로 저장 → 받은 (종목 · 날) 수.
    1분봉은 11-11 10:46 부터 쌓여 그 전 판은 「개장 N분 뒤 값」 · VI 값이 비었다 — 셈 칸 매수가 09:01 이면 그 날들이 「매매 없음」(11-23 재권님 「응 그렇게해」).
    받은 뒤 그 판에 여는 값(pxMin · px1) · VI 값(viPx)을 채워 **판에 저장한다** — 1분봉은 5거래일만 남아(holdings/CLAUDE.md 「봉은 기간마다 정한
    길이만 남긴다」) 지워지면 다시 비기 때문이다(개념정의 검수 11-23 · 길 (ㄱ)). 판에 여는 값이 이미 있는 줄은 안 묻는다.
    받아 봤는데 빈 종목(정지 등)은 표를 남겨 다시 안 묻는다."""
    today = _now().strftime("%Y%m%d")
    n = 0
    for day in [d for d in days(proxy) if d < today][:limit]:
        got = _load(proxy, day)
        if not got or not got[0].get("rows"):
            continue
        b = got[0]
        o = _open_min(proxy, day, b)
        codes = [r["code"] for r in b["rows"] if not all((r.get("pxMin") or {}).get(str(k)) for k in PX_MIN)]
        if not codes:
            continue
        lo, hi = day + _hhmm(o).replace(":", ""), day + _hhmm(o + max(PX_MIN)).replace(":", "")
        with proxy.db_conn() as conn:
            have = {c for (c,) in conn.execute("SELECT DISTINCT code FROM candles WHERE period = '1m' AND ts BETWEEN ? AND ? AND code IN (%s)"
                                                % ",".join("?" * len(codes)), [lo, hi] + codes)}
        for c in codes:
            mk = "m1fill:%s:%s" % (c, day)
            if c in have or proxy._meta_get(mk):
                continue
            raw = proxy._kr_past_chunk(cfg, c, day, _hhmm(o + M1_FILL_SPAN).replace(":", "") + "00")
            time.sleep(proxy.BAR_FILL_CALL_GAP)
            mine = [x for x in raw if x["ts"][:8] == day and int(x["ts"][8:10]) * 60 + int(x["ts"][10:12]) >= proxy.MINUTE_DAY_START]
            if mine:
                proxy.save_candles(c, "1m", proxy.aggregate_minutes(mine, 1))
            proxy._meta_set(mk, today)
            n += 1
        vi0 = [bool(r.get("viPx")) for r in b["rows"]]
        got_px = _pxmin_fill(proxy, b)                 # 쌓인 1분봉(방금 받은 것 · 이미 있던 것)으로 판 줄을 채워 저장 — 1분봉이 지워져도 남게
        if got_px or [bool(r.get("viPx")) for r in b["rows"]] != vi0:   # VI 값만 새로 찬 날도 남김(개념정의 덧 11-23)
            _store(proxy, b)
    return n


def backfill(proxy, today, limit=BACKFILL_DAYS, since=None, today_too=False):
    """today 앞 limit 거래일 중 판이 없는 날을 다시 세어 남긴다(라이브로 굳힌 날은 안 건드린다). 남긴 날 수."""
    ds = _trade_days(proxy, today, limit)
    have, keep_live = set(), {}
    for d in days(proxy):                              # 관심 없이 세어 둔 되채운 날(watchSrc 칸 전)은 한 번 다시 센다(11-12 「응」)
        got = _load(proxy, d)
        m = (got[0].get("meta") or {}) if got else {}
        stale = got and (m.get("capMinEok") != cap_min_eok() or (not m.get("allRows") and d < ALL_ROWS_SINCE))   # 문턱이 바뀐 판 · 줄을 자르던 옛 판(라이브로 굳힌 날 포함)은 한 번 다시 센다
                                                       # — 그 뒤 라이브 판(allRows 없음)은 날마다 다시 짓지 않는다(개념정의 덧 11-23 · 장중 기록을 어림 판으로 덮지 않게)
        lm = m.get("lateMin") if isinstance(m.get("lateMin"), int) else 0
        late_old = m.get("rebuilt") and not isinstance(m.get("lateMin"), int) and late_min(proxy, day=d) > 0   # 늦게 연 날을 09:00 기준으로 다시 지은 판(11-24 전) — 한 번 다시 센다
        old_watch = m.get("rebuilt") and m.get("watchSrc") != "지금 룰"   # 관심을 하트 · 그날 문서로 센 옛 판(11-25 전) — 한 번 다시 센다(재권님 「관심은 지금룰로만」)
        if not stale and not late_old and not old_watch and not (m.get("rebuilt") and ("watchSrc" not in m or m.get("viUntil") != "%02d:%02d" % _sh(PAST_LATE, lm))):   # (재권님 「기준 3000억 이상이라고 몇번을 말했는데」 11-23 19:0x)
            have.add(d)                                # VI 창이 다른 되채운 날(11-13 전)도 한 번 다시 센다
        elif m.get("liveBefore"):
            keep_live[d] = m["liveBefore"]
        elif stale and not m.get("rebuilt"):           # 라이브로 굳힌 날 — 덮이는 장중 기록을 한 벌 남긴다(today_too 와 같은 꼴)
            old = got[0]
            keep_live[d] = {"savedAt": got[1], "buyAt": old.get("buyAt"), "meta": old.get("meta"),
                            "rows": [{k: r.get(k) for k in ("code", "name", "rank", "chips", "subs", "n", "buy", "buyAt", "buyTs", "buySrc", "pct", "rise", "px", "pxSrc", "lock", "lockAt", "chipAt", "subAt", "viAt", "surgeAt", "viPx", "pxMin", "px1", "turnMin", "volDay")}
                                     for r in old.get("rows") or []]}
    n = 0
    cfg = proxy.load_secrets()
    for i, d in enumerate(ds[:limit]):
        if d in have or i + 1 >= len(ds) or (since and d < since):
            continue
        b = rebuild(proxy, d, ds[i + 1], cfg)
        if b and b["rows"]:
            if d in keep_live:                         # 장중에 고른 기록은 다시 세도 이어 남기고 그 값을 되돌린다(live_merge)
                b["meta"]["liveBefore"], b["meta"]["redoneFromLive"] = keep_live[d], True
                live_merge(b)
            _redo_gone(proxy, d, b)
            _store(proxy, b)
            n += 1
    for d in days(proxy)[:limit]:                      # 칩 시각 공식(CF_VER)을 남은 판마다 한 번 — 기록이 없던 칩도 시각을 갖게(11-23 19:0x 「공식도 있어야해」)
        got = _load(proxy, d)
        m = (got[0].get("meta") or {}) if got else {}
        if got and m.get("liveBefore") and not m.get("liveMerged"):
            try:                                       # 라이브로 굳힌 날을 다시 지은 판 — 장중에 적은 값을 되돌림(재권님 「목록 왜 또 바뀐거지?」 11-24)
                if live_merge(got[0]):
                    _store(proxy, got[0])
            except Exception as e:
                print("  [단타 30] %s 장중 값 못 되돌림 — %s" % (d, proxy.safe_message(e, 120)), flush=True)
        if got and d < today and m.get("prevDay") and m.get("tradeVer") != TRADE_VER:   # 거래 값 · 풀린 시총 어림을 남은 되채운 판마다 한 번(다시 짓지 않고 · 11-23 20:2x 「응」)
            try:
                if _past_trade(proxy, d, m["prevDay"], got[0].get("rows") or []):   # 봉을 못 읽은 날은 표시를 안 찍어 다음 바퀴에 다시(개념정의 덧 ②)
                    got[0]["meta"]["tradeVer"] = TRADE_VER
                    _store(proxy, got[0])
            except Exception as e:
                print("  [단타 30] %s 거래 값 못 채움 — %s" % (d, proxy.safe_message(e, 120)), flush=True)
        if got and got[0].get("closed", True) and (got[0].get("meta") or {}).get("cfVer") != CF_VER:
            try:
                chip_first_backfill(proxy, d, got[0])
                got[0]["meta"]["cfVer"] = CF_VER
                _store(proxy, got[0])
            except Exception as e:
                print("  [단타 30] %s 칩 시각 공식 못 채움 — %s" % (d, proxy.safe_message(e, 120)), flush=True)
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
                _redo_gone(proxy, today, b)
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


PRE_END = (8, 50)            # 오늘 판 rows[].pre — 넥스트레이드 프리장(08:00~08:50)이 닫힌 뒤 마지막 체결 값을 판에 굳힌다(작업우선순위 · 시황분석1 화면 11-20 · 재권님 그림에 「응 맞아」 10:53)
PRE_HOURS = ("084900", "081900")   # 1분봉 끝 시각 — 30줄씩 · 뒤 칸에 체결이 없을 때만 앞 칸을 부른다


def _pre_last(proxy, cfg, code, day):
    """그날 넥스트레이드 1분봉 08:00~08:49 중 마지막 체결 봉 → (종가, "HH:MM") · 체결 없음 ("none", None) · 못 받음 (None, None)."""
    for hour in PRE_HOURS:
        data = proxy.kis_get(cfg, "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
                             {"FID_ETC_CLS_CODE": "", "FID_COND_MRKT_DIV_CODE": "NX", "FID_INPUT_ISCD": code,
                              "FID_INPUT_HOUR_1": hour, "FID_PW_DATA_INCU_YN": "Y"}, "FHKST03010200")
        if data is None or str(data.get("rt_cd", "0")) != "0":
            return None, None
        best = None
        for r in data.get("output2") or []:
            t = str(r.get("stck_cntg_hour") or "")[:4]
            if r.get("stck_bsop_date") != day or not ("0800" <= t <= "0849") or not proxy._num(r.get("cntg_vol"), int):
                continue
            if best is None or t > best[0]:
                best = (t, proxy._num(r.get("stck_prpr"), int))
        if best:
            m = int(best[0][:2]) * 60 + int(best[0][2:]) + 1      # 1분봉 시각은 그 분의 시작 — 끝난 때로 적는다(08:49 봉 → 08:50)
            return best[1], "%02d:%02d" % divmod(m, 60)
    return "none", None


def pre_fill(proxy, cfg, b, hm):
    """오늘 판(b) 줄 중 rows[].pre 가 없는 줄에 프리장 끝 값을 적는다 — {pct, at, px, prev} · 체결이 없었으면 null(0 아님).
    pct 는 넥스트 전일 종가(멀티 시세 inter2_prdy_clpr) 대비 — 홀딩스 /api/kis/prices pct 와 같은 기준. 1분봉 NX 는 오늘 것만 주므로 지난 판은 못 채운다.
    PRE_END 전 · NX_SKIP 동안은 안 함 · 못 받은 줄은 키를 안 만들어 다음 바퀴에 다시. 적은 줄 수."""
    if hm < PRE_END[0] * 60 + PRE_END[1] or b.get("day") != _now().strftime("%Y%m%d"):
        return 0
    lo, hi = NX_SKIP
    if lo[0] * 60 + lo[1] <= hm < hi[0] * 60 + hi[1]:
        return 0
    todo = [r for r in b.get("rows") or [] if "pre" not in r]
    if not todo:
        return 0
    import nxt_pre
    q = nxt_pre.fetch_nx(proxy, cfg, [r["code"] for r in todo], gap=0)
    n = 0
    for r in todo:
        px, at = _pre_last(proxy, cfg, r["code"], b["day"])
        if px is None:
            continue
        prev = (q.get(r["code"]) or {}).get("prev_close") or None
        if px == "none":
            r["pre"] = None
        elif not prev:
            continue                                   # 전일 종가를 못 받음 — 다음 바퀴에 다시
        else:
            r["pre"] = {"pct": round((px - prev) / prev * 100, 2), "at": at, "px": px, "prev": prev}
        n += 1
    if n:
        b["meta"]["preNote"] = ("pre — 오늘 넥스트레이드 프리장 마지막 체결(%02d:%02d 전) 값 · pct 는 넥스트 전일 종가 대비 · at 그 봉이 끝난 때 · "
                                "체결이 없었으면 null · 키가 없으면 아직 못 받음" % PRE_END)
    return n


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
            got = _m1_px(conn, b["day"], [r["code"] for r in need], ts, "close")   # 거래량 0 채움 봉은 건너뜀
            for r in need:
                v = got.get(r["code"])
                if v:
                    r.setdefault("pxMin", {})[k] = {"at": at[k], "px": v, "src": "1m"}
                    n_got += 1
    for r in rows:
        if not r.get("px1") and (r.get("pxMin") or {}).get("1"):
            r["px1"] = r["pxMin"]["1"]
    _trade_min_fill(proxy, b)                          # 사는 때 거래 값 둘(turnMin · volDay) — 같은 1분봉 · 같은 때(11-24)
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


# ── 사는 때 거래 값 둘 (2026-11-24 재권님 「응 해줘」 16:5x · 시황분석1 과 논의 — 「전날 같은 시각 대비」 는 빼고 「전일대비 거래량」 은 9시 25분에)
#    rows[].turnMin {"1"~"5": {at, turn, src} | null} — 여는 시각 + N분까지의 「유통 대비 거래 %」(pxMin 과 같은 칸) ·
#        1분봉(여는 시각 봉 ~ 여는 시각 + N − 1 봉)의 Σ(종가 × 거래량) ÷ (풀린 주식수 × 그 끝 봉 종가) × 100 — 대금은 1분봉 어림(src 「1m」)
#    rows[].volDay {at, pct, vol, prevVol, src} | null — 여는 시각 + VOL_DAY_MIN 분까지 정규장 누적 거래량(한국거래소 · 프리장 뺌 · 거래 값 시각 칸 turnover_slot) ÷
#        전날 하루 거래량(한국거래소 · turnover_day · 화면 prevDayVol 과 같은 기준) × 100 — 재권님 「프리장 미포함으로 하고 전일대비 거래량」(11-24 16:5x · 시황분석1 경유) ·
#        시각 칸은 VOL_SLOT_LOOK 분 안 마지막 칸(at 에 그 칸 시각) · 칸은 오늘 · 전날만 남아(turnover.SLOT_KEEP_DAYS) 지난 판은 장중에 적어 저장한 날만
#    meta.turnMinAt · volDayAt — 그 시각(늦게 연 날은 그만큼 뒤). 그날 판은 그 분이 끝난 뒤에만 적는다(덜 찬 봉으로 안 셈) ·
#    풀린 주식수 · 1분봉 · 전날 일봉이 없으면 null(못 잼 · 0 아님). 지난 판은 1분봉이 남은 날만(11-11 부터) 읽을 때 채운다(저장 안 함).
VOL_DAY_MIN = 25             # 전일대비 거래량을 재는 때 — 여는 시각 + 이 분(보통 09:25 · 재권님 「9시 25분에 보이는걸로」 11-24)
TURN_MIN_UPTO = 30           # 유통 대비 거래를 분마다 적는 끝 — 여는 시각 + 이 분(매수 룰 기준 시각 끝 RULE_MIN_HI 와 같게 · 칩 찬 분 값으로 거르려고 · 11-24)
VOL_SLOT_LOOK = 5            # 그 시각 칸이 없으면 이 분 안 앞 칸까지(거래 값 받기가 1분마다라 칸이 1~2분 띄엄)


def _trade_min_fill(proxy, b, now=None):
    """위 「사는 때 거래 값 둘」 한 곳 — 줄에 turnMin · volDay 를 채운다(이미 있는 값은 그대로) · 새로 적은 칸 수."""
    import company_profile
    rows = b.get("rows") or []
    if not rows:
        return 0
    now = now or _now()
    day = b["day"]
    o = _open_min(proxy, day, b)
    today = day == now.strftime("%Y%m%d")
    hm = now.hour * 60 + now.minute - 1 if today else 24 * 60   # 그날 판은 1분 늦게 — 끝난 봉을 1분봉 받기(1분마다)가 가져온 뒤(pxMin 고리 +1 과 같게)
    if day > now.strftime("%Y%m%d"):
        return 0
    b["meta"]["turnMinAt"] = {str(n): _hhmm(o + n) for n in range(1, TURN_MIN_UPTO + 1)}
    b["meta"]["volDayAt"] = _hhmm(o + VOL_DAY_MIN)
    fl = company_profile.floats()
    codes = [r["code"] for r in rows]
    q = ",".join("?" * len(codes))
    lo, hi = day + _hhmm(o).replace(":", ""), day + _hhmm(o + TURN_MIN_UPTO - 1).replace(":", "")
    bars, upto, prev = {}, {}, {}
    import turnover
    try:
        with proxy.db_conn() as conn:
            for c, t, cl, v in conn.execute("SELECT code, ts, close, volume FROM candles WHERE period = '1m' AND ts BETWEEN ? AND ? AND code IN (%s) ORDER BY ts" % q,
                                            [lo, hi] + codes):
                bars.setdefault(c, []).append((t, cl, v))
            if hm >= o + VOL_DAY_MIN and any("volDay" not in r or (r["volDay"] is None and today) for r in rows) \
                    and (today or conn.execute("SELECT 1 FROM turnover_slot WHERE day = ? LIMIT 1", (day,)).fetchone()):   # 지난 판은 시각 칸이 남은 날만 묻는다(이틀만 남음 · 읽을 때마다 종목 수만큼 묻지 않게 · qa 덧 11-24)
                s_hi, s_lo = _hhmm(o + VOL_DAY_MIN).replace(":", ""), _hhmm(o + VOL_DAY_MIN - VOL_SLOT_LOOK).replace(":", "")
                for c, sl, sv in conn.execute("SELECT code, slot, vol FROM turnover_slot WHERE day = ? AND slot BETWEEN ? AND ? AND vol IS NOT NULL AND code IN (%s) ORDER BY slot" % q,
                                              [day, s_lo, s_hi] + codes):
                    upto[c] = (sv, "%s:%s" % (sl[:2], sl[2:]))   # 마지막(가장 늦은) 칸이 남는다
        if upto:
            pdy = turnover._prev_day(proxy, day)
            prev = {c: g.get("vol") for c, g in (turnover.day_rows(proxy, pdy, codes) if pdy else {}).items()}
    except Exception as e:
        print("  [단타 30] 사는 때 거래 값 못 셈 — %s" % proxy.safe_message(e, 120), flush=True)
        return 0
    n_got = 0
    for r in rows:
        c, tm = r["code"], r.setdefault("turnMin", {})
        bs = bars.get(c) or []
        for n in range(1, TURN_MIN_UPTO + 1):
            k = str(n)
            if tm.get(k) or hm < o + n:                # 그 분이 안 끝났으면(그날 판은 1분 더 기다림) 안 적음 · 적힌 값은 그대로
                continue
            end = day + _hhmm(o + n - 1).replace(":", "")
            got = [(t, cl, v) for t, cl, v in bs if t <= end and v is not None]
            f = fl.get(c)
            last = got[-1][1] if got else None
            if not got or not f or not last or any(cl is None for _, cl, _ in got):   # 종가 없는 봉이 하나라도 섞이면 대금이 작게 셈 — 못 잼(개념정의 덧 11-24)
                tm[k] = None                           # 못 잼(1분봉 · 풀린 주식수 없음) — 0 아님
                continue
            val = sum((cl or 0) * v for _, cl, v in got)
            if val <= 0:                               # 거래량 0 봉뿐 — 채움 봉(옛 값 · qa 11-20 11-19 10:00 봉)일 수 있어 0 이 아니라 못 잼
                tm[k] = None
                continue
            tm[k] = {"at": _hhmm(o + n), "turn": round(val / (f * last) * 100, 2), "src": "1m"}
            n_got += 1
        if ("volDay" not in r or (r["volDay"] is None and today)) and hm >= o + VOL_DAY_MIN:   # 못 잰(None) 칸은 다시 셈 — 그 시각 칸이 늦게 적힌 날(개념정의 덧 11-24 · 고리는 VOL_SLOT_LOOK 분까지만 다시 봄)
            a, p = upto.get(c), prev.get(c)
            r["volDay"] = {"at": a[1], "pct": round(a[0] / p * 100, 1), "vol": a[0], "prevVol": p, "src": "krx"} if a and p else None
            n_got += 1 if r["volDay"] else 0
    return n_got


TG_TOP = 10                  # 텔레그램으로 보내는 상위 종목 수 — 재권님 「단타 목록 상위 10개가 최초로 볼수있는 시간이 어떻게 되지? 그걸 바로 텔레그램으로 보내고 싶은데」 → 「나」(개장 1분 뒤 · 11-19 13:5x)
TG_SEND = True               # 켜기 — 그날 판 상위 TG_TOP 을 개장 1분 값이 적힌 뒤 하루 한 통 · 재권님 「응 해줘」(11-19 14:3x · 시험 한 통 14:01 보신 뒤) · 보내는 서버(8765)만
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
    with proxy.db_conn() as conn:                      # 정규장 시가 = 여는 시각 1분봉 시가(시세의 시가는 장 전 값이 섞일 수 있다) · 그 봉이 거래량 0 채움 봉이면 첫 체결 봉 시가(11-19 CJ ENM 10:00 봉 42,150 은 채움 봉 · 첫 체결 47,000 — qa 11-20)
        o1 = _m1_px(conn, b["day"], [r["code"] for r in rows], ts, "open")
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


# ── 매수 룰 — 서버 한 곳 (2026-11-24 재권님 · 시황분석1 「매수 룰 정의」 1f47da7 「응 이게 맞아 이대로 만들어줘」 17:5x · 개발2 안 「응」 18:1x) ──
#  1 기준 시각 R = 여는 시각 + ruleMin 분(셈 칸 rules.dt30.set.ruleMin · 5~30 · 빈칸 5) — 늦게 연 날은 여는 시각이 밀려 저절로 뒤
#  2 R 전에 칩 N개(셈 칸 minChip · buy_need)가 찬 종목 — 찬 순간(N번째 칩 시각 T) 그 분 유통 대비 거래(rows[].turnMin · T 직전에 끝난 1분 값)가
#    turnMin % 이상이면 「○○ 매수하세요」 · 못 잰 종목은 안 삼(재권님 「유통대비 거래에 안걸리면 목록에 안나와야해」 → 「가」)
#  3 R 에 — 2번 종목이 상위 ( )종목(top)에 모자라면 모자란 만큼 칩이 하나 모자란(N−1) 종목 중(채움 켬 · N > 1)
#    (재권님 「가 상위종목에 지정된 숫자에서 부족한 숫자만큼」 18:2x · 창구 경유 — fillN 칸은 걷음)
#    R 의 유통 대비 거래 조건을 넘은 것 → 상승률(시가 대비 R 1분 값) 높은 순 → 칩 많은 순 → 판 차례로 모자란 만큼
#    (재권님 「상승률이 우선이고 유통대비거래는 조건이야」)
#  4 R 뒤에 칩이 찬 종목 — 안 보냄
#  5 위 차례대로 「총 ( )만원 ÷ 상위 ( )종목」 칸(셈 칸 top · buy_top)의 종목 수까지만 — 화면이 위에서부터 그 수만 사는 것과 같게
#    (재권님 「위에서 순서대로 지정된 숫자만 인데? 총금액과 종목을 정하는 칸이 있는데」 11-24 18:2x — 처음 판은 상한 없음으로 짰음)
#  화면에서 끈 칩 · 칩 칸은 셈 칸 chipOff · subOff · chipCols 로 받아 화면과 같게 셈(chip_filter · 11-24 · 칸이 없으면 다 켠 것). 그 분 거래 값이 아직 안 적혔으면 BUY_WAIT_MIN 분까지 기다렸다 셈.
#  텔레그램(TG_SEND) · 슬랙 매수 목록(trade_signal) · 「팔 때」 대상(meta.tgTop)이 이 한 목록(buy_order)을 쓴다 — 전 「9시 3분부터 · 5종목」(sendFrom · sendN)은 걷음(재권님 「가」 18:0x)
RULE_MIN_DEF, RULE_MIN_LO, RULE_MIN_HI = 5, 5, 30   # 화면 strategy-dt30.js RULE_MIN_* 와 같은 값(두 벌 — 판 meta.buyRule.def 로 내 화면이 받게 할 자리)
TOP_DEF = 30                 # 「상위 ( )종목」 칸이 비었을 때 — 화면 DEF_SET top(PNL_TOP)과 같은 값 · 〃
TURN_ON_DEF, TURN_MIN_DEF = True, 1.0   # 저장값에 칸이 없을 때 — 화면 DEF_SET turnOn · turnMin(시황분석1 0d0e60f · 재권님 「유통거래대비 1%가 기본」)과 같은 값 · 〃
BUY_WAIT_MIN = 3             # 그 분 유통 대비 거래 값이 아직 없으면 이 분까지 기다렸다 셈(1분봉 받기가 1분마다) · 그 뒤에도 없으면 못 잼 → 안 삼
BUY_SEND_LATE = 5            # R + 이 분이 지나면 더 안 보냄(서버가 늦게 뜬 날 묵은 종목을 보내지 않게)


def _set_int(key, dflt, lo, hi):
    """셈 칸(rules.dt30.set) 정수 — 빈칸 · 틀린 꼴 · 범위 밖 · 못 읽음이면 기본값."""
    v = _set_val(key)
    try:
        v = int(v) if v is not None and v != "" and not isinstance(v, bool) else None
    except (TypeError, ValueError):
        v = None
    return v if v is not None and lo <= v <= hi else dflt


def _set_val(key):
    try:
        import dt30_win
        return dt30_win._set().get(key)
    except Exception:
        return None


def rule_min():
    """기준 시각 — 여는 시각 + 이 분(셈 칸 ruleMin · 5~30) · 없으면 RULE_MIN_DEF."""
    return _set_int("ruleMin", RULE_MIN_DEF, RULE_MIN_LO, RULE_MIN_HI)


def buy_top():
    """사는 종목 수 상한 — 「총 ( )만원 ÷ 상위 ( )종목」 칸(셈 칸 top · 1 이상) · 없으면 TOP_DEF. 매수 룰 차례대로 이 수까지만 보내고 금액도 이 수로 나눔."""
    return _set_int("top", TOP_DEF, 1, 999)


def turn_rule():
    """(거르나, 몇 %) — 셈 칸 turnOn · turnMin · 칸이 없으면 TURN_*_DEF."""
    on, mn = _set_val("turnOn"), _set_val("turnMin")
    on = TURN_ON_DEF if on is None else on is True
    try:
        mn = TURN_MIN_DEF if mn is None or mn == "" else float(mn)
    except (TypeError, ValueError):
        mn = TURN_MIN_DEF
    return bool(on and mn > 0), mn


def chip_filter():
    """화면에서 끈 칩 · 칩 칸 — 셈 칸 chipOff [칩] · subOff [「칩|하위」] · chipCols [칩] (화면 「저장」 · 여는 시각 + 4분 자동 저장이 넣음 · 11-24 재권님 「카드에 있것들 해」).
    칸이 없으면 다 켠 것 · 칸 목록이 없으면 단타 셈 칩 전부(전과 같음)."""
    lst = lambda k: [str(x) for x in _set_val(k)] if isinstance(_set_val(k), list) else None
    cols = set(lst("chipCols")) if lst("chipCols") else None
    known = lst("chipKnown")
    if cols is not None and known:                     # 저장 뒤 새로 생긴 칩(그때 화면이 몰랐던 칩)은 칸 밖이어도 켬 — 칸 메뉴 「지우기」 로 뺀 칩은 known 안이라 그대로 빠짐(시황분석1 chipKnown · 11-25 재권님 「처음부터 셈이되도록 켜줘」)
        cols |= {c for c in ov_chips() if c not in set(known)}
    return set(lst("chipOff") or []), set(lst("subOff") or []), cols


def _subs_of(r, c, split):
    """줄의 그 칩 하위 이름들 — 화면 strategy-dt30.js subsOf 와 같은 셈(VI·급등은 처음 VI · 급등 시각이 split 전 · 이후 · 모름 + 나머지)."""
    raw = (r.get("subs") or {}).get(c)
    raw = raw if isinstance(raw, list) else ([raw] if raw else [])
    if c != "VI·급등":
        return raw
    if c not in (r.get("chips") or []):
        return []
    ts = [_hm4(x) for x in (r.get("viAt"), r.get("surgeAt")) if _hm4(x)]
    t = min(ts) if ts else None
    head = "시각 모름" if t is None else ("09:25 전" if t < split else "09:25 이후")   # 화면 VI_SUBS 와 같은 이름(나누는 시각은 판 meta.viSplit)
    return [head] + [x for x in raw if x not in ("VI", "급등")]


def _chip_on(r, c, cf, split):
    """화면 everChip 과 같게 — 끈 칩 · 칸 밖 칩은 안 셈 · 지금 붙은 칩은 하위가 하나라도 켜져 있어야 · 붙었다 빠진 칩은 시각이 있으면 셈."""
    off, sub_off, cols = cf
    if c in off or (cols is not None and c not in cols):
        return False
    if c in (r.get("chips") or []):
        sb = _subs_of(r, c, split)
        return not sb or any("%s|%s" % (c, x) not in sub_off for x in sb)
    return bool((r.get("chipTime") or {}).get(c))


def _turn_at(r, n):
    """여는 시각 + n분까지의 유통 대비 거래 %(rows[].turnMin) · 없으면 None."""
    v = (r.get("turnMin") or {}).get(str(max(1, min(n, TURN_MIN_UPTO))))
    return v.get("turn") if isinstance(v, dict) else None


def buy_order(proxy, b, hm=None, inplace=False):
    """→ (줄들 · 기준 시각 분) — 위 「매수 룰」 한 곳. hm(분)을 주면 그때까지 정해진 것만(그날 판 · 고리) · 없으면 그날 끝까지(지난 판 · 읽기).
    줄마다 r["buyRule"] {order, kind 「찬」·「채움」, at 정한 시각, chipAt, turn, rise, px} · 판(b)은 안 바꿈(inplace 면 그 판 줄에 적음 — 읽기 길)."""
    import copy
    bb = b if inplace else copy.deepcopy(b)
    if not inplace:                                    # 읽기 길은 앞에서 이미 둘 다 셈(_pxmin_fill · buy930_fill)
        buy930_fill(proxy, bb)
        _trade_min_fill(proxy, bb)
    day = bb["day"]
    o = _open_min(proxy, day, bb)
    R = o + rule_min()
    now_m = hm if hm is not None else 24 * 60
    need = buy_need()
    on, tmin = turn_rule()
    fn = buy_top()                                     # 채움 목표 = 상위 ( )종목(재권님 「가」 18:2x)
    rows = (bb.get("rows") or []) + ((bb.get("meta") or {}).get("outRows") or [])
    ct_of = lambda r: {k: str(v).replace(":", "") for k, v in (r.get("chipTime") or {}).items()}

    cf, split = chip_filter(), ((bb.get("meta") or {}).get("viSplit") or vi_split(o - OPEN_AT[0] * 60 - OPEN_AT[1])).replace(":", "")

    def nth(r, lim):
        ct = ct_of(r)
        cs = [c for c in chips930(r, ct, lim) if _chip_on(r, c, cf, split)]   # 화면에서 끈 칩은 안 셈(11-24)
        l4 = "%02d%02d" % lim
        return _live_at(r, ct, cs, l4), _nth_live(r, ct, cs, need, l4)   # 칩 N개가 동시에 붙어 있던 첫 순간 · 기준 시각에 붙어 있던 칩(11-25 칩 빠진 시각)

    got = []
    for r in rows:
        _, T = nth(r, divmod(R - 1, 60))               # R 전(그 분 포함 안 함)에 N번째 칩
        if not T:
            continue
        tm_ = int(T[:2]) * 60 + int(T[2:])
        n = tm_ - o                                    # 찬 순간 직전에 끝난 1분 — 여는 시각 + n분 값
        dec = o + max(1, n) + 1                        # 그 값이 적히는 때(그날 판은 1분 늦게 · _trade_min_fill)
        if now_m < dec:
            continue
        tv = _turn_at(r, n)
        if on and tv is None and now_m < dec + BUY_WAIT_MIN:
            continue                                   # 아직 안 적힘 — 다음 바퀴
        if on and (tv is None or tv < tmin):
            continue                                   # 조건 못 넘음 · 못 잼 → 안 삼
        px = (r.get("buy930") or {}).get("px")
        got.append((tm_, r.get("rank") or 1e9, r, {"kind": "찬", "at": _hhmm(max(dec - 1, tm_)), "chipAt": _hhmm(tm_), "turn": tv, "rise": None, "px": px}))
    got.sort(key=lambda x: (x[0], x[1]))
    out = [(x[2], x[3]) for x in got]
    if need > 1 and _set_val("fill") is True and len(out) < fn and now_m >= R + 1:
        have = {r["code"] for r, _ in out}
        cand, wait = [], False
        for r in rows:
            if r["code"] in have:
                continue
            ts, _ = nth(r, divmod(R - 1, 60))
            if len(ts) != need - 1:
                continue
            tv = _turn_at(r, R - o)
            if on and tv is None and now_m < R + 1 + BUY_WAIT_MIN:
                wait = True
                continue
            if on and (tv is None or tv < tmin):
                continue
            cand.append((r, tv, len(ts), ts[-1] if ts else None))
        if not wait and cand:
            codes = [x[0]["code"] for x in cand]
            try:
                with proxy.db_conn() as conn:
                    pr = _m1_px(conn, day, codes, day + _hhmm(R - 1).replace(":", ""), "close")   # R 의 값 = 그 앞 1분봉 종가(pxMin 과 같은 셈)
                    op = _m1_px(conn, day, codes, day + _hhmm(o).replace(":", ""), "open")        # 줄에 시가가 없는 지난 판 — 여는 시각 첫 봉 시가
            except Exception as e:
                print("  [단타 30] 매수 룰 채움 — 기준 시각 1분 값 못 읽음 · %s" % proxy.safe_message(e, 120), flush=True)   # 상승률이 다 빔 → 칩 수 · 판 차례로만(개념정의 덧 11-24)
                pr, op = {}, {}
            pick = []
            for r, tv, nc, last in cand:
                p, o0 = pr.get(r["code"]), (r.get("open") if isinstance(r.get("open"), (int, float)) and r.get("open") > 0 else op.get(r["code"]))
                rise = round((p / o0 - 1) * 100, 2) if p and o0 else None
                pick.append((-(rise if rise is not None else -1e9), -nc, r.get("rank") or 1e9, r,
                             {"kind": "채움", "at": _hhmm(R), "chipAt": "%s:%s" % (last[:2], last[2:]) if last else None,   # 채운 줄은 N−1번째 칩 시각
                              "turn": tv, "rise": rise, "px": p}))
            pick.sort(key=lambda x: x[:3])
            out += [(x[3], x[4]) for x in pick[:fn - len(out)]]
    res = []
    for i, (r, info) in enumerate(out[:buy_top()], 1):   # 차례대로 상위 ( )종목까지만(5번)
        info["order"] = i
        r["buyRule"] = info
        res.append(r)
    return res, R


def buy_rule_meta(proxy, b):
    """읽기 길 — 판 meta.buyRule(룰 값 · 기본 · 서버 차례)과 줄마다 rows[].buyRule. 그날 판은 지금까지 정해진 것만."""
    now = _now()
    hm = now.hour * 60 + now.minute if b.get("day") == now.strftime("%Y%m%d") else None
    rows, R = buy_order(proxy, b, hm, inplace=True)
    on, tmin = turn_rule()
    cf = chip_filter()
    b["meta"]["buyRule"] = {"ruleAt": _hhmm(R), "ruleMin": rule_min(), "need": buy_need(), "top": buy_top(), "fill": _set_val("fill") is True,
                            "turnOn": on, "turnMin": tmin, "chipOff": sorted(cf[0]), "subOff": sorted(cf[1]), "chipCols": sorted(cf[2]) if cf[2] is not None else None, "def": {"ruleMin": RULE_MIN_DEF, "turnOn": TURN_ON_DEF, "turnMin": TURN_MIN_DEF, "top": TOP_DEF},
                            "order": [{"code": r["code"], "name": r.get("name"), **r["buyRule"]} for r in rows],
                            "sent": (b["meta"].get("tgBuy") or {}),
                            "note": "서버가 보내는 차례(order) — 기준 시각 전 칩 N개 찬 순(그 분 유통 대비 거래 조건) · 기준 시각에 모자라면 칩 N−1 종목 상승률 순 · 위에서 상위 top 종목까지만 · 끈 칩은 셈 칸 chipOff · subOff · chipCols 대로 · sent 는 실제로 보낸 것"}


def buy_text(r):
    """「매수」 텔레그램 글 — 「종목명 매수하세요」 한 줄(「팔 때」 글과 같은 꼴 · 재권님 「가로해줘」 11-24)."""
    return "%s 매수하세요" % (r.get("name") or r["code"])


def buy_send(proxy, b, hm):
    """여는 시각부터 기준 시각 + BUY_SEND_LATE 분까지 — 매수 룰(buy_order)로 새로 정해진 종목을 meta.tgTop 에 더하고(meta.tgBuy 에 차례 · 시각 · 찬/채움) 텔레그램 한 통씩 → 더한 수."""
    o = _open_min(proxy, b["day"], b)
    if hm < o + 1 or hm > o + rule_min() + BUY_SEND_LATE:
        return 0
    m = b.setdefault("meta", {})
    top = m.setdefault("tgTop", [])
    rows, _ = buy_order(proxy, b, hm)
    n = 0
    cap = buy_top()
    for r in rows:
        if r["code"] in top:
            continue
        if len(top) >= cap:                            # 이미 보낸 것으로 상위 ( )종목이 찼음 — 늦게 정해진(거래 값을 기다린) 종목이 앞 차례여도 더 안 보냄(보낸 것은 못 거둠)
            break
        top.append(r["code"])
        info = r["buyRule"]
        m.setdefault("tgBuy", {})[r["code"]] = {"px": info.get("px"), "at": info.get("at"), "chipAt": info.get("chipAt"), "sentAt": _now().strftime("%H:%M:%S"),
                                                "kind": info["kind"], "order": len(top), "turn": info.get("turn"), "rise": info.get("rise")}
        m["tgTopAt"] = _now().strftime("%H:%M")
        n += 1
        if TG_SEND:
            ok, why = dart.telegram_send(buy_text(r))
            print("  [단타 30] 매수 %s %s(%s) %s" % (r["code"], info["kind"], info.get("chipAt"), "보냄" if ok else "못 보냄 — " + str(why)), flush=True)
    return n

SELL_SEND = True             # 켜기 — 아침 상위 TG_TOP 이 꺾이면 「팔 때」 한 통씩(종목마다 한 번 · 하루 9~10통 — 11-12~19 엿새 셈) · 재권님 「응 해줘」(11-19 14:4x · 시험 한 통 보신 뒤) · 보내는 서버(8765)만
SELL_DROP_PCT = 2.0          # 고점 대비 이만큼 내려오면 — 재권님 「30분단위로 대비했을때 가격이 하락한상황이거나 고점대비 2% 하락시로 해줘」(11-19 14:3x)
SELL_STEP_MIN = 30           # 「30분 전보다 내림」 을 보는 칸 — 정시 30분마다(09:30 · 10:00 …) 그때 값을 전 칸(첫 칸은 산 값 = 개장 1분 값)과 견줌
SELL_UNTIL_MIN = 10          # 정규장 끝 이 분 전까지만 본다
_sell = {"day": None, "hi": {}, "chk": {}}   # 「팔 때」 고점 · 30분 칸 값 — 고리가 20초마다 판을 새로 읽어서 판에 두면 저장한 때 값만 남는다(개념정의 걸림 11-19) · 메모리에 두고 새로 걸린 때만 판에 적음


def sell_watch(proxy, cfg, b, now=None):
    """아침 상위(meta.tgTop) 종목이 꺾였나 — 고점(산 뒤 본 현재가 중 최고) 대비 SELL_DROP_PCT % 아래 · 또는 30분 칸 값이 전 칸보다 낮음.
    종목마다 처음 걸린 때 한 번 rows[].sell {at, px, why, hi, ref, buy} 를 적고 → 새로 걸린 줄 목록. 산 값이 없는 종목(개장 1분 값 못 잼)은 안 본다.
    값은 시세 캐시(PRICE_CACHE_TTL)를 탄다 — 고점은 그 값들 중 최고라 캐시 사이의 순간 고점은 못 본다."""
    import market_hours
    now = now or _now()
    o = _open_min(proxy, b["day"], b)
    close = int(market_hours.today(proxy, day=b["day"]).get("reg", ["", market_hours.REG_CLOSE])[1] or market_hours.REG_CLOSE)
    close = close // 100 * 60 + close % 100
    hm = now.hour * 60 + now.minute
    top = set((b.get("meta") or {}).get("tgTop") or [])
    tb = (b.get("meta") or {}).get("tgBuy") or {}
    bpx = lambda r: (tb.get(r["code"]) or {}).get("px") or ((r.get("pxMin") or {}).get("1") or {}).get("px")   # 보낸 매수 값(찬 때) · 옛 판은 개장 1분 값
    rows = [r for r in (b.get("rows") or []) + ((b.get("meta") or {}).get("outRows") or []) if r["code"] in top and not r.get("sell") and bpx(r)]
    if not rows or hm < o + 2 or hm >= close - SELL_UNTIL_MIN:
        return []
    q, _ = proxy.fetch_quotes_multi(cfg, [r["code"] for r in rows], max_age=proxy.PRICE_CACHE_TTL)
    if _sell["day"] != b["day"]:
        _sell.update(day=b["day"], hi={}, chk={})
    new = []
    for r in rows:
        p = (q.get(r["code"]) or {}).get("price")
        if not p:
            continue
        buy = bpx(r)
        hi = max(v for v in (_sell["hi"].get(r["code"]), r.get("sellHi"), buy, p) if v)   # 고점 = 산 값과 그 뒤 본 현재가 중 최고(앞으로 올 값은 안 섞음 · 서버가 다시 뜨면 판에 적힌 것부터)
        _sell["hi"][r["code"]] = hi
        why, ref = None, None
        if p <= hi * (1 - SELL_DROP_PCT / 100):
            why, ref = "고점 대비 -%g%%" % SELL_DROP_PCT, hi
        chk = _sell["chk"].setdefault(r["code"], dict(r.get("sellChk") or {}))
        m = hm // SELL_STEP_MIN * SELL_STEP_MIN             # 정시 칸(09:00 · 09:30 …) — 재권님 「30분단위라 함은 정시로 정해줘. 9시 9시반 이런것처럼」(11-19)
        if m > o + 1:                                       # 산 뒤(개장 1분 값 뒤)의 칸만
            key = "%02d%02d" % divmod(m, 60)
            if key not in chk and hm - m <= NOW_OK_MIN:
                chk[key] = p                                # 그 칸 값 = 그 칸이 지난 뒤 처음 본 현재가
                pm = m - SELL_STEP_MIN
                prev = chk.get("%02d%02d" % divmod(pm, 60)) if pm > o + 1 else buy   # 첫 칸은 산 값과 견줌
                if why is None and prev and p < prev:
                    why, ref = "30분 전보다 내림", prev
        if why:
            r["sell"] = {"at": now.strftime("%H:%M"), "px": p, "why": why, "hi": hi, "ref": ref, "buy": buy}
            r["sellHi"], r["sellChk"] = hi, dict(chk)       # 판에는 걸린 때 한 번 적는다
            new.append(r)
    return new


def sell_text(r):
    """「팔 때」 텔레그램 글 — 「종목명 매도하세요」 한 줄(재권님 「가로해줘」 11-24 14:2x). 시각 · 가격 · 까닭은 판 rows[].sell 에 그대로 남는다."""
    return "%s 매도하세요" % (r.get("name") or r["code"])


TRADE_KEYS = ("accVol", "accValue", "prevSameVol", "prevSameSrc", "volPrevPct", "valuePrevPct", "prevDayVol", "prevDayValue")   # 거래 값 칸 — 셈은 turnover._trade 한 곳
TURN_NOTE = ("floatCap 풀린 시총(억원) = 발행주식수 × 유동비율(네이버 기업현황) × 현재가 · turn 거래 비율(%) = 그날 누적 거래대금 ÷ 풀린 시총 × 100 · "
             "turnPrevPct 전날 대비(%) = 거래 비율 ÷ 전날 같은 시각(1분 칸)까지 거래 비율 × 100(굳힌 판은 그날 끝 ÷ 전날 끝) · turnPrevSrc 1m · day(전날 끝) · 5m(전날 칸이 없어 정규장 5분봉 거래량 비로 어림 · 칩 「거래비율급증」 과 같은 셈) · 색 기준 data/metrics.json turn_prev_pct · "
             "accVol 오늘 누적 거래량(주) · accValue 오늘 누적 거래대금(억원) · prevSameVol 전날 같은 시각까지 거래량(주) · "
             "volPrevPct · valuePrevPct 거래량 · 거래대금 전날 같은 시각 대비(%) · 색 기준 data/metrics.json vol_prev_pct · amt_prev_pct · "
             "prevDayVol · prevDayValue 전날 하루 거래량(주) · 거래대금(억원) · 굳힌 판은 「같은 시각」 이 전날 끝 · "
             "그날 판의 prevSameVol · volPrevPct 는 같은 셈(turnover.same_time · 거래비율급증 칩의 5분봉 어림도 이것) — prevSameSrc 1m 전날 같은 1분 칸 · 5m 정규장 5분봉 끝난 봉끼리 · "
             "5m 이면 prevSameVol 은 정규장 5분봉 합이라 accVol(시세 · 한국거래소)과 바로 견주지 않는다 · 굳힌 판은 slot 그날 끝 칸 · "
             "전날 값은 거래 값 표(시세)로만 — 봉으로 채우지 않는다(넥스트레이드 합친 값이라 기준이 다름 · 쌓기 첫날 11-23 은 전날 칸 null) · "
             "그날 판은 지금 값 · 굳힌 판은 그날 쌓인 마지막 값(turnover_day) · 못 잰 칸은 null · 우선주는 유동비율 출처가 없어 null")


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
        live_merge(b)                                  # 다시 지은 라이브 판 — 장중 값을 읽을 때도 되돌림(저장은 장 뒤 되채우기 고리 · 장중에도 화면이 바로 맞게)
    except Exception as e:
        print("  [단타 30] 장중 값 못 되돌림 — %s" % proxy.safe_message(e, 120), flush=True)
    try:                                               # 되살린 장중 줄(liveBefore 에 시총 · 시장 · 업종 칸이 없음)은 감시 목록 · 회사 정보로 채움(qa 덧 11-24)
        miss = [r for r in b.get("rows") or [] if r.get("cap") is None or not r.get("market") or not r.get("sector")]
        if miss:
            import company_profile
            uni = {u["stock_code"]: dict(u) for u in dart.universe_rows(None)}   # sqlite3.Row — get 이 없어 dict 로(qa 걸림)
            sec = company_profile.sectors()
            for r in miss:
                u = uni.get(r["code"]) or {}
                r["cap"] = r.get("cap") if r.get("cap") is not None else u.get("market_cap")
                r["market"] = r.get("market") or u.get("market")
                r["sector"] = r.get("sector") or sec.get(r["code"])
    except Exception as e:
        print("  [단타 30] 빈 시총 · 업종 칸 못 채움 — %s" % proxy.safe_message(e, 120), flush=True)
    try:
        drop_small(proxy, b)                           # 그날 판 · 지난 판 모두 읽을 때 문턱 밖은 뺌(저장 안 함 · 지금 감시 목록 시총으로) — 재권님 「3천억 아래종목은 아예 고려대상이 아니야」 → 지난 판도 「응 빼 지금룰에 맞춰서 다 적용해」(11-23 09:3x)
    except Exception as e:
        print("  [단타 30] 문턱 거르기 못 함 — %s" % proxy.safe_message(e, 120), flush=True)
    try:
        _pxmin_fill(proxy, b)                          # 여는 시각 + N분 값 · 09:01 값 — 적힌 것이 없으면 쌓인 1분봉에서(지난 판 · 그날 판 둘 다 · 저장 안 함)
        for r in b.get("rows") or []:
            r.setdefault("px1", None)
            pm = r.setdefault("pxMin", {})
            for n in PX_MIN:
                pm.setdefault(str(n), None)                # 못 잼 — 0 아님
    except Exception:
        pass
    try:
        buy930_fill(proxy, b)                          # 사는 셈 한 곳 — 칩 시각 · 09:30 까지 칩 · N번째 칩 찬 때 값(rows[].buy930 · 화면은 받기만) · 아래 봉 줄은 이 값을 씀
        try:
            buy_rule_meta(proxy, b)                    # 매수 룰 — 서버가 보내는 차례(meta.buyRule · rows[].buyRule · 11-24)
        except Exception as e:
            print("  [단타 30] 매수 룰 차례 못 셈 — %s" % proxy.safe_message(e, 120), flush=True)
    except Exception as e:
        print("  [단타 30] 사는 셈 못 함 — %s" % proxy.safe_message(e, 120), flush=True)
    else:
        if b["meta"].get("outRows"):
            try:
                _out_px(proxy, b, b["meta"]["outRows"])   # 빠진 줄의 빠진 뒤 시각 칸을 5분봉으로(승률 표와 같게 · 30분 칸 매도 셈도 걸리게 · qa 덧 · 읽을 때만)
            except Exception as e:
                print("  [단타 30] 빠진 줄 값 못 채움 — %s" % proxy.safe_message(e, 120), flush=True)   # 봉 줄은 따로 계속(qa 덧)
        try:
            bars_fill(proxy, b)                        # 산 때~판 끝 봉 줄(매도 타점 재료 · 화면 · 승률 표 같은 봉)
        except Exception as e:
            print("  [단타 30] 봉 줄 못 붙임 — %s" % proxy.safe_message(e, 120), flush=True)
    b["meta"]["subNames"] = {"매수|" + "①②③④"[k - 1]: v[0] for k, v in proxy.JOINT_TIER_NAME.items()}   # 하위 이름표 — 서버 한 곳(kis_proxy.JOINT_TIER_NAME · 11-20)
    b["meta"]["subTips"] = {"매수|" + "①②③④"[k - 1]: v[1] for k, v in proxy.JOINT_TIER_NAME.items()}
    import dt30_win
    b["meta"]["tax"] = dt30_win.TAX                    # 거래세 · 농특세(%) — 서버 한 곳(dt30_win.TAX) · 화면은 보이기만 · 바꾸는 것은 증권수수료 칸 하나(재권님 11-20 14:09)
    b.setdefault("closed", True)                       # 옛 판(closed 칸 전) · 되채운 날은 끝난 판
    open_today = False
    if b["day"] == _now().strftime("%Y%m%d"):
        try:
            import market_hours
            rc = ((market_hours.today(proxy, day=b["day"]).get("reg") or [None, None])[1] or market_hours.REG_CLOSE).replace(":", "")[:4]   # 늦게 연 날은 닫는 시각도 그날 값
            open_today = _now().strftime("%H%M") < rc        # 판이 2시에 닫혀도 정규장 끝까지는 상승률(지금 값 ÷ 시가)이 바뀐다 — 재권님 (가) 11-24 11:4x
        except Exception:
            open_today = False
    b["meta"]["refreshMs"] = None if b["closed"] and not open_today else proxy.PRICE_CACHE_TTL * 1000
    if not b["closed"] and cfg is not None:
        # 그날 판은 14:00 마지막 칸 전까지 지금 값을 붙인다 — 재권님 「그날은 변동에 맞춰서 실시간으로 적용되야 하고 그날 2시가 지나면 값이 저장되도록」(19:3x)
        # 다시 받을 주기는 서버 값(refreshMs · 시세 캐시와 같은 PRICE_CACHE_TTL) — 화면은 그 값으로 돈다 · 시세는 그 나이 안이면 캐시
        q, _ = proxy.fetch_quotes_multi(cfg, [r["code"] for r in b["rows"]], max_age=proxy.PRICE_CACHE_TTL)
        for r in b["rows"]:
            r["now"] = (q.get(r["code"]) or {}).get("price")
        b["nowAt"] = _now().strftime("%H:%M:%S")
    if b["day"] == _now().strftime("%Y%m%d") and cfg is not None:
        try:
            open_rise_now(proxy, cfg, b)
        except Exception as e:
            print("  [단타 30] 시가 대비 등락률 못 셈 — %s" % proxy.safe_message(e, 120), flush=True)
    try:
        import turnover
        if not b["closed"] and cfg is not None:
            turnover.fill(b["rows"], q, proxy)                 # 그날 판 — 지금 값(실시간)
        else:
            turnover.fill_day(proxy, b["day"], b["rows"])   # 굳힌 판 — 그날 쌓인 마지막 값 · 쌓기 전 날은 None
    except Exception as e:
        print("  [거래 비율] 판 칸 못 셈 — %s" % proxy.safe_message(e, 120), flush=True)
    b["meta"]["turnNote"] = TURN_NOTE
    return b


_or_last = {}                 # {날: {code: (상승률, 셈한 시각)}} — 정규장 중 마지막으로 센 상승률(장 뒤 · 시세가 통합으로 넘어간 뒤 읽을 때 씀 · 서버 메모리)


def open_rise_now(proxy, cfg, b):
    """그날 판 줄(rows · 빠진 줄 outRows)의 시가 대비 등락률(openRise)을 읽을 때마다 지금 값으로 — 지금 값 ÷ 오늘 시가 · 시세 캐시 나이 안이면 캐시.
    재권님 「시가대비 등락률인데 등락이 바뀔때마다 값이 여기에 적용되어야해」(11-24 11:3x) — 전에는 판 다시 세기가 멈추는 10:30 값에 굳어 있었다.
    시가는 시세의 오늘 시가 · 없거나 지금 값이 없으면 null(못 잼 · 0 아님) · 저장 안 함(읽을 때만)."""
    rows = (b.get("rows") or []) + ((b.get("meta") or {}).get("outRows") or [])
    if not rows:
        return 0
    for d in [d for d in _or_last if d != b["day"]]:
        del _or_last[d]                                # 오늘 아닌 날은 지움 — 날마다 늘지 않게(개념정의 덧)
    last = _or_last.setdefault(b["day"], {})
    if proxy.quote_market_div() != "J":            # 정규장 밖 — 시세가 통합(UN)으로 넘어가 시가가 08:00 프리장 첫 값이 됨 → 정규장 중 마지막 셈 값(없으면 저장값)
        for r in rows:
            if r["code"] in last:
                r["openRise"] = last[r["code"]][0]
        at = max((v[1] for v in last.values()), default=None)
        b["meta"]["openRiseAt"] = at
        return 0
    q, _ = proxy.fetch_quotes_multi(cfg, [r["code"] for r in rows], max_age=proxy.PRICE_CACHE_TTL)
    n, now_s = 0, _now().strftime("%H:%M:%S")
    for r in rows:
        v = q.get(r["code"]) or {}
        o, p = v.get("open"), v.get("price")             # 시가는 시세의 오늘 정규장(KRX · quote_market_div J) 시가만 — 줄 open 칸은 08:00 프리장 첫 값인 줄이 있어 대신 쓰지 않음(qa 덧 · 33줄)
        r["openRise"] = round((p / o - 1) * 100, 2) if o and p else None
        if r["openRise"] is not None:
            last[r["code"]] = (r["openRise"], now_s)
            n += 1
    b["meta"]["openRiseAt"] = now_s
    b["meta"]["openRiseNote"] = "시가 대비 등락률 = 지금 값 ÷ 오늘 정규장 시가(KRX · 남들이 보는 시세 값) — 그날 판은 정규장 중 읽을 때마다 새로(시세 캐시 나이 안) · 정규장 뒤는 마지막 셈 값 · 지난 판은 저장된 값(09:05 봉 시가 ÷ 09:00 봉 시가) · 차트 1분봉은 통합(UN) 값이라 테스처럼 갈릴 수 있음"
    return n


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
                    n = m1_fill(proxy, proxy.load_secrets())   # 장 끝난 뒤(QUIET 밖) — 지난 판 여는 시각 1분봉 빈 것 되받기
                    if n:
                        print("  [단타 30] 지난 판 1분봉 %d개(종목 · 날) 되받음" % n, flush=True)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [단타 30] 되채우기 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = now.hour * 60 + now.minute
                if _status.get("volSweep") != (day, hm >= 14 * 60 + 5) and not (RECENT_SKIP[0][0] * 60 + RECENT_SKIP[0][1] <= hm < RECENT_SKIP[1][0] * 60 + RECENT_SKIP[1][1]):
                    _status["volSweep"] = (day, hm >= 14 * 60 + 5)   # 하루 두 번(아침 · 14:05 뒤 오늘 판이 닫힌 뒤) — DB 만 읽는다(KIS 안 씀)라 장중에도 돈다
                    n = vol_past_sweep(proxy, day)   # 지난 판에 「거래비율」 · 「거래비율급증」(11-23 「데이터 받는대로」)
                    if n:
                        print("  [단타 30] 지난 판 %d일에 거래비율 칩 붙임" % n, flush=True)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [단타 30] 지난 판 거래비율 칩 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
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
                    if got is None and BUY_AT[0] * 60 + BUY_AT[1] <= hm < BUY_LATE[0] * 60 + BUY_LATE[1] and _status["frozen"] != day:
                        b = build(proxy, proxy.load_secrets(), day)
                        for r in b["rows"]:
                            _sub_keep(r, None, now.strftime("%H:%M:%S"))   # 처음 지은 판 — 하위가 붙은 시각
                        if hm < _buy_wait_cut(proxy, now):
                            for r in b["rows"]:
                                r["buy"], r["buyWait"] = None, True          # 여는 시각 + 1분 전에 지은 판 — 9시 1분 값을 기다린다
                        else:
                            _buy_now(proxy, proxy.load_secrets(), [r for r in b["rows"] if not r.get("buyWait")])   # 장중에 처음 짓는 판(서버가 늦게 뜸) — 든 순간 현재가
                        _store(proxy, b)
                        _status.update(frozen=day, error=None)
                        print("  [단타 30] %s %02d:%02d 판 %d종목 굳힘%s" % (day, BUY_AT[0], BUY_AT[1], len(b["rows"]),
                              " · 못 받은 칩 " + " · ".join(b["meta"]["missing"]) if b["meta"]["missing"] else ""), flush=True)
                    elif got is not None:
                        b = got[0]
                        if not b.get("closed") and lock_fix(b):
                            _store(proxy, b)               # 굳힘 시각 뒤 든 줄이 그 묶음에 있으면 다음 굳힘으로(11-23)
                            print("  [단타 30] %s 판 굳힘 묶음 고침 — 굳힘 시각 뒤 든 줄을 다음 굳힘으로" % day, flush=True)
                        if not b.get("closed") and drop_small(proxy, b):
                            _store(proxy, b)               # 문턱 밖 종목 — 굳힌 줄도 뺀다(그날 판만 · 끝난 판은 안 건드림)
                            print("  [단타 30] %s 판에서 시가총액 문턱 밖 종목 뺌 — %s" % (day, " · ".join(x["name"] or x["code"] for x in b["meta"]["capDrop"][-20:])), flush=True)
                        if b.get("closed") and not b.get("rows") and hm < BUY_LATE[0] * 60 + BUY_LATE[1]:
                            b["closed"] = False            # 줄 0 으로 굳어 버린 판 — 굳히는 때 전이면 다시 연다(11-19 수능 아침 08:00 에 빈 판이 굳어 다시 세기가 멈춤)
                        was = bool(b.get("closed"))
                        due = [t for t in b["times"] if int(t[:2]) * 60 + int(t[2:]) + 1 <= hm
                               and any(t not in r["px"] for r in b["rows"])]
                        filled_late = []
                        if not b.get("closed") and hm < BUY_LATE[0] * 60 + BUY_LATE[1]:
                            if time.time() - _status.get("rescan", 0) >= RESCAN_SEC:
                                _status["rescan"] = time.time()
                                if refresh(proxy, proxy.load_secrets(), b):
                                    filled_late = ["다시 셈"]
                        elif not b.get("closed"):
                            filled_late = patch_late(proxy, proxy.load_secrets(), b)
                            if _lock_due(b, hm):                   # 굳히는 때(10:30)가 지난 뒤 — 남은 차례(마지막 10개)를 굳힌다(다시 셈은 안 함)
                                filled_late = list(filled_late) + ["굳힘"]
                            if _buy_open_fill(proxy, b):           # 굳힌 뒤에도 시가를 기다리는 줄 — 1분봉이 늦게 들어오면 채움(DB 만 읽음)
                                filled_late = list(filled_late) + ["시가"]
                            n_in = intraday_add(proxy, proxy.load_secrets(), b, hm)   # 굳힌 뒤 새로 걸린 종목 — 「장중」 묶음(11-23)
                            if n_in:
                                filled_late = list(filled_late) + ["장중 %d" % n_in]
                        if hm >= BUY_LATE[0] * 60 + BUY_LATE[1] + off and b.get("rows") and time.time() - _status.get("volAt", 0) >= RESCAN_SEC:
                            _status["volAt"] = time.time()      # 굳힌 뒤 · 닫힌 뒤도 그날 안 — 두 칩을 값이 나오는 대로(11-23 16:4x)
                            nv = vol_live_attach(proxy, proxy.load_secrets(), b)
                            if nv:
                                filled_late = list(filled_late) + ["거래비율 칩 %d" % nv]
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
                        if hm >= o_min + VOL_DAY_MIN + 1 and any("volDay" not in r or (r["volDay"] is None and hm <= o_min + VOL_DAY_MIN + 1 + VOL_SLOT_LOOK) for r in b["rows"]):   # 전일대비 거래량 — 여는 시각 + 25분이 끝난 뒤 · 못 잰 줄은 VOL_SLOT_LOOK 분 더 다시(11-24)
                            _trade_min_fill(proxy, b)
                            flow_now = True
                        if b["rows"] and not b.get("closed") and buy_send(proxy, b, hm):   # 매수 — 칩 N개 찬 시각별로 · 여는 시각 + 3분부터 · 찰 때마다 한 종목씩(11-24) · 「팔 때」 대상도 이것
                            flow_now = True
                        if pre_fill(proxy, proxy.load_secrets(), b, hm):   # 오늘 프리장 끝 값 — 08:50 뒤 · 새로 든 줄은 다음 바퀴에
                            flow_now = True
                        if (b.get("closed") or hm >= BUY_LATE[0] * 60 + BUY_LATE[1]) and b.get("rows") and hm < _close_min(proxy, now) \
                                and sub_track(proxy, proxy.load_secrets(), b):   # 굳힌 뒤(10:30) · 14:00 칸을 적어 판이 닫힌 뒤에도 정규장 끝까지 매수 하위(①~④)를 이어 쌓는다
                            flow_now = True
                        if b["meta"].get("tgTop"):           # 판이 굳은 뒤(14:00)에도 정규장 끝 SELL_UNTIL_MIN 분 전까지 본다(sell_watch 가 시각을 가름 · 개념정의 걸림 11-19)
                            for r in sell_watch(proxy, proxy.load_secrets(), b):
                                flow_now = True
                                if SELL_SEND:
                                    ok, why = dart.telegram_send(sell_text(r))
                                    print("  [단타 30] 팔 때 %s %s" % (r["code"], "보냄" if ok else "못 보냄 — " + str(why)), flush=True)
                        if PRE_LOG_FROM[0] * 60 + PRE_LOG_FROM[1] <= hm <= PRE_LOG_TO[0] * 60 + PRE_LOG_TO[1] and _status.get("preLogHm") != now.strftime("%Y%m%d%H%M"):
                            try:                                  # 프리장 기록 — 분마다 한 번은 센다(화면이 부를 때만 세면 캐시 60초 + 셈 시간이 겹쳐 한 분씩 빠졌다 · 개념정의 11-25 08:02 빠짐)
                                live(proxy, proxy.load_secrets(), force=True)
                            except Exception as e:
                                print("  [단타 프리장 기록] 분마다 셈 못 함 — %s" % proxy.safe_message(e, 120), flush=True)
                        if OPEN_AT[0] * 60 + OPEN_AT[1] + off <= hm < _close_min(proxy, now) and time.time() - _status.get("cfLive", 0) >= LIVE_TTL:
                            _status["cfLive"] = time.time()       # 정규장 끝까지 단타 목록을 세어 칩 처음 시각을 남긴다 — 09:30 · 굳힘 뒤 붙는 칩도(재권님 「9시 30분 이후에 붙는 칩들도 다 기록되어야해」 11-23 19:0x)
                            try:                                  # 화면이 안 열려 있어도 돈다 · 캐시(LIVE_TTL) 안이면 셈을 다시 안 함
                                live(proxy, proxy.load_secrets())
                            except Exception as e:
                                print("  [단타 30] 칩 시각 쌓기 못 함 — %s" % proxy.safe_message(e, 120), flush=True)
                        if not b.get("closed") and hm >= OPEN_AT[0] * 60 + OPEN_AT[1] + off and time.time() - _status.get("flowNow", 0) >= FLOW_NOW_SEC:
                            _status["flowNow"] = time.time()      # 그날 판 줄의 수급 지금 값 — FLOW_NOW_SEC 마다(묶음 ③ · 09:00 뒤)
                            got = flows(proxy, proxy.load_secrets(), [r["code"] for r in b["rows"]])
                            for r in b["rows"]:
                                r["flowNow"] = got.get(r["code"])
                            b["meta"]["flowNowAt"] = _now().strftime("%H:%M")
                            _cf_flow(proxy, day, b["rows"], _now().strftime("%H:%M:%S"))   # 외국계 · 프로그램 처음 순매수 된 때(11-23 「응」)
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
