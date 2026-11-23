# -*- coding: utf-8 -*-
"""초반상승 — 아침 첫 봉(11-18 부터 09:00~09:01 1분봉 · 그 전 09:00~09:05 5분봉)이 시가보다 RISE_PCT % 이상 올라 끝난 종목 · 실시간 순위 「초반상승」 칩 (2026-11-11).

재권님 — 「아침 9시5분 기준으로 양봉이 2% 이상이 되고 시가총액이 5천억 이상인 종목들 소팅해서 실시간 순위에 초반상승 이라고 만들어서
넣어줘」(작업우선순위 창 11:25) → 「양봉 2%」 를 (가) 첫 5분봉 시가 대비 종가 · (나) 09:05 가격의 전일 종가 대비 로 여쭈어 「가」(개발1 창 11:41).

    대상        순위 목록(dart.universe_rows · 시가총액 dart.UNIVERSE_MIN_CAP_EOK 이상) 중 시가총액 MIN_CAP_EOK 억원 이상 · **ETF 는 뺀다**(재권님 「가」 11-11)
                ETF = 순위 목록에 있는데 OpenDART 기업 대응표(dart_corps)에 없고 코드 끝자리가 0 — 대응표에 없는 것은 ETF 와 우선주뿐이고
                우선주는 끝자리가 0 이 아니다(11-11 개발 DB: 대응표 밖 42 = ETF 39 + 우선주 3 · 대응표 안에 끝자리 0 아닌 코드 0)
    셈          그날 첫 봉 — BAR_PERIOD 의 여는 시각 봉(11-18 부터 09:00~09:01 1분봉 · 보통 날 여는 시각 — market_hours.today 의 usual reg[0] · 재권님 「아침 9시부터 9시 5분」) — (종가 − 시가) ÷ 시가 ≥ RISE_PCT %
                늦게 여는 날(수능 등)은 그날 여는 시각의 첫 봉(market_hours.today 의 reg[0] · 11-19 수능 10:00~10:01) — 재권님 「응 해줘」(11-19 · 개발2 창)
                그 전에는 늘 보통 날 09:00 봉을 읽어 늦게 연 날 하나도 안 잡혔다(11-19 오전 · 초반상승 값 든 줄 0)
                장 시각 숫자를 이 파일에 두지 않는다(market_hours 머리 · 개념정의 검수 11-11)
                **또는** 첫 봉 종가가 프리장 마지막 값(nxt_pre 08:51 저장 표 · 체결 있던 종목만)보다 PRE_RISE_PCT % 이상 높음 — 둘 중 하나면 든다 ·
                줄의 by 에 걸린 셈(open · pre) · 프리장 체결 없던 종목은 시가 대비만 · 표를 못 읽으면 preMissing — 재권님 「초반상승은 경우의 수를 둬야 할거같은데
                지금룰에 걸리거나/ 프리장보다 2%이상 오를때 로 해줘」(11-23 · 작업우선순위 창) → 안(견주는 값은 첫 1분봉 끝 값)에 「응 커밋해」(개발1 창)
                지난 날 다시 셈(day_top_fill · dt30 rebuild — 첫 5분봉 PAST_RISE_PCT)에는 안 넣었다
    차례        그 상승률 큰 순
    다 찬 봉만   그 봉을 **끝난 뒤에 받았는지**는 kis_proxy `_minutes_fresh_upto`(「지금 칸」 을 받은 분)로 가른다 — 그 봉이 끝나기 전에 받은 덜 찬 봉으로
                고르지 않는다(거래량 전날 대비 % 와 같은 기록 · 11-11 qa 돌려보냄). 아직이면 그 종목은 `pending` 으로 센다
    언제        새로 받지 않는다 — DB 에 쌓인 봉만 읽는다(미리받기가 순위 목록 5분봉을 받을 때 1분봉도 함께 저장된다). 그 봉이 다 차면 값이 그대로라 그날 판이 굳는다
    phase       closed(그날 휴장) · before(첫 봉이 아직 안 끝남) · pending(다 받기 기다림) · done(그날 판 고정) ·
                nodata(대상이 있는데 첫 봉이 하나도 없음 — 「오른 종목 없음」 이 아니라 「못 쟀다」)
    없음        그날 봉이 없는 종목은 `noBar` 로 센다(0 아님)

판은 KIS 를 부르지 않는다. 값(2% · 시가총액 문턱)은 이 파일 상수 한 곳 · 장 시각은 market_hours 한 곳 — 화면은 meta 로 받아 글에 쓴다.

    첫 봉 먼저   미리받기만 기다리면 화면이 열려 있는 동안 종목 사이를 쉬어 09:10 에 70~80종목뿐이었다(11-12 · 09:06 단타 판에 거의 빠짐).
                그래서 쓰는 서버는 첫 봉이 끝나는 순간(+FIRST_GRACE_SEC) 대상 중 아직 끝난 뒤 안 받은 종목의 분봉을 차례로 받는다(5분봉 길 · 1분봉 함께 저장) —
                미리받기와 같은 get_chart(「지금 칸」 · 받은 분 표시) · 대상 수만큼 KIS(약 300종목) · FIRST_UNTIL_MIN 지나면 그만
                (재권님 「9시부터 9시5분까지 미리 받게 하면 되지않아?」 → 덜 찬 봉이라 09:05 뒤에 받아야 함 → 「응 그렇게 해」 11-12)
"""

from datetime import datetime, timedelta, timezone

import chip_rules      # 칩 룰 값 한 곳(2026-11-20) — 상승 문턱
import dart            # 시가총액 문턱(UNIVERSE_MIN_CAP_EOK) 한 곳 — 모듈을 읽을 때 쓴다

import market_hours

KST = timezone(timedelta(hours=9))

BAR_MIN = 1              # 첫 봉의 길이(분) — 첫 1분봉(09:00~09:01) · 재권님 「초반상승을 첫 1분봉으로」 → 문턱 「나」 1.5%(11-18 20:0x · 그날 1분봉으로 센 하루 평균 40종목 — 5분봉 2% 셈과 비슷)
BAR_PERIOD = "1m"        # 그 봉을 읽는 기간 — 5분봉을 받을 때 1분봉도 함께 저장된다(kis_proxy get_chart · 2026-11-11)
PRE_RISE_PCT = chip_rules.RULES["초반상승"]["preRisePct"][0]   # 기본값(2%) — 「또는」 셈: 첫 봉 종가가 프리장 마지막 값(nxt_pre 08:51 저장 표 price)보다 이만큼 높음 · 지금 값은 chip_rules.get · 재권님 「지금룰에 걸리거나/ 프리장보다 2%이상 오를때」(11-23) → 안에 「응 커밋해」
RISE_PCT = chip_rules.RULES["초반상승"]["risePct"][0]   # 기본값(1.5%) — 첫 봉 시가 대비 종가 상승률 문턱 · 지금 값은 chip_rules.get(「초반상승」, risePct) · 룰 문서로 고침(2026-11-20)
PAST_BAR_MIN = 5         # 지난 날 다시 셈(day_top_fill · dt30 rebuild)은 첫 5분봉 그대로 — 1분봉은 11-12 부터만 쌓여 있어 그 전 날은 셀 수 없다
PAST_RISE_PCT = 2.0      # 〃 문턱(11-18 전 셈 그대로)
MIN_CAP_EOK = dart.RANK_MIN_CAP_EOK   # 시가총액 문턱(억원) — 단타 · 순위 문턱 한 곳(dart.RANK_MIN_CAP_EOK · 3천억 · 재권님 「3000으로 통일」 → 「나」 11-20 · 그 전 5천억 11-12) · 단위 억원
CACHE_TTL = 60           # 같은 판을 다시 세지 않는 시간(초) — 화면이 다시 묻는 주기도 이 값(서버 값)
FIRST_GRACE_SEC = 3      # 첫 봉이 끝난 뒤 이만큼 기다렸다 받는다 — KIS 가 그 분을 닫을 틈
FIRST_UNTIL_MIN = 10     # 첫 봉 끝에서 이 분이 지나면 먼저 받기를 그만둔다(남은 것은 미리받기 몫)
T_RECHECK_SEC = 60       # 먼저 받기 고리가 그날 장 시각(market_hours.today)을 다시 읽는 간격(초) — 늦게 여는 날을 알아보려고

_st = {"at": 0.0, "data": None}


def _universe(proxy):
    """순위 목록 → (ETF 뺀 줄, 뺀 ETF 수)."""
    import dart
    with proxy._db_lock, proxy.db_conn() as conn:
        corps = {r[0] for r in conn.execute("SELECT stock_code FROM dart_corps WHERE stock_code <> ''")}
    out, etf = [], 0
    for r in dart.universe_rows(None):
        code = r["stock_code"] or ""
        if not (code.isdigit() and len(code) == 6):
            continue
        if corps and code not in corps and code.endswith("0"):
            etf += 1                       # 대응표가 비었으면(못 읽음) 거르지 않는다 — 다 ETF 로 빼지 않게
            continue
        out.append({"code": code, "name": r["name"], "market": r["market"], "cap": r["market_cap"]})
    return out, etf


def build(proxy, now=None):
    """그날 판 — {day, barFrom, barTo, phase, rows, candidates, pending, noBar, capMissing}."""
    now = now or datetime.now(KST)
    day = proxy._minutes_trade_day()
    live_today = day == now.strftime("%Y%m%d")
    t = market_hours.today(proxy, day=day, now=now)
    # 그날 여는 시각의 첫 봉 — 보통 날 09:00(재권님 「그건 아침 9시부터 9시 5분인데」 11-11) · 늦게 여는 날(수능)은 그 시각(11-19 「응 해줘」).
    # 숫자는 market_hours 한 곳. 그 봉이 없으면 nodata(「못 셈」) — 「오른 종목 없음」 으로 내지 않는다(개념정의 검수 11-11)
    bar_hm = t["reg"][0]
    bar_end = int(bar_hm[:2]) * 60 + int(bar_hm[2:]) + BAR_MIN
    head = {"day": day, "barFrom": "%s:%s" % (bar_hm[:2], bar_hm[2:]), "barTo": "%02d:%02d" % divmod(bar_end, 60)}
    empty = dict(head, rows=[], candidates=None, pending=None, noBar=None, capMissing=None, etfOut=None)
    if t["open"] is False:
        return dict(empty, phase="closed")
    if live_today and now.hour * 60 + now.minute < bar_end:
        return dict(empty, phase="before")
    # 리셋 — 그날 판은 넥장이 끝나는 market_hours.AFTER_CLOSE(20:00)까지만 · 그 뒤부터 다음 날 첫 봉까지 「시작 전」
    # (2026-11-13 재권님 「관심안에 초반상승은 아직 시작전이니 전날 장이 마감되면 리셋되게 해줘」 · 「저녁 8시에 리셋」)
    if not live_today or now.strftime("%H%M") >= market_hours.AFTER_CLOSE:
        return dict(empty, phase="before", reset=True)
    uni, etf = _universe(proxy)
    cap_missing = sum(1 for u in uni if u["cap"] is None)
    cap_min = dart.rank_min_cap_eok()
    cand = [u for u in uni if u["cap"] is not None and u["cap"] >= cap_min]
    codes = [u["code"] for u in cand]
    bars = {}
    if codes:
        with proxy._db_lock, proxy.db_conn() as conn:
            q = ",".join("?" * len(codes))
            for r in conn.execute(
                    "SELECT code, open, high, low, close, volume FROM candles WHERE period = ? AND ts = ? AND code IN (%s)" % q,
                    [BAR_PERIOD, day + bar_hm] + codes):
                bars[r["code"]] = dict(r)
    rows, pending, no_bar = [], 0, 0
    rise_pct = chip_rules.get("초반상승", "risePct")
    pre_rise_pct = chip_rules.get("초반상승", "preRisePct")
    import nxt_pre
    try:                                   # 그날 프리장 마지막 값 — 08:51 저장 표 · 거래량 0 은 체결 없음이라 「프리장 대비」 를 안 센다
        pre, _d, _src = nxt_pre.last_prices(proxy, day)   # 자기 표가 비면 8765 것(메인 · 세션 서버는 이 표를 안 채운다)
    except Exception:
        pre = None                         # 못 읽음 — 「시가 대비」 만 센다 · 응답 preMissing 으로 알린다
    for u in cand:
        b = bars.get(u["code"])
        if not b or not b["open"] or b["close"] is None:
            no_bar += 1
            continue
        if live_today:
            fresh = proxy._minutes_fresh_upto(u["code"])
            if fresh is None or fresh < bar_end:
                pending += 1                 # 그 봉을 끝난 뒤에 아직 안 받았다 — 덜 찬 값일 수 있다
                continue
        pct = (b["close"] - b["open"]) / b["open"] * 100
        pp = (pre or {}).get(u["code"])
        pre_pct = (b["close"] - pp) / pp * 100 if pp else None
        by = [k for k, ok in (("open", pct >= rise_pct), ("pre", pre_pct is not None and pre_pct >= pre_rise_pct)) if ok]
        if by:                             # 둘 중 하나면 든다 · by = 걸린 셈(open 시가 대비 · pre 프리장 대비 · 둘 다)
            rows.append({"code": u["code"], "name": u["name"], "market": u["market"], "cap": u["cap"],
                         "open": b["open"], "close": b["close"], "high": b["high"], "volume": b["volume"],
                         "pct": round(pct, 2), "pre": pp, "prePct": round(pre_pct, 2) if pre_pct is not None else None, "by": by})
    rows.sort(key=lambda x: -x["pct"])
    phase = "pending" if pending else "nodata" if cand and no_bar == len(cand) else "done"
    return dict(head, phase=phase, rows=rows, candidates=len(cand), pending=pending, noBar=no_bar, capMissing=cap_missing, etfOut=etf,
                risePct=rise_pct, preRisePct=pre_rise_pct, preMissing=pre is None, preCount=len(pre) if pre is not None else None)


def fetch(proxy, now=None):
    """(판, 센 시각). CACHE_TTL 안이면 들고 있던 판."""
    import time
    if _st["data"] is None or time.time() - _st["at"] >= CACHE_TTL:
        _st["data"] = build(proxy, now)
        _st["at"] = time.time()
    return _st["data"], _st["at"]


_first = {"day": None, "got": 0, "left": None, "at": None, "error": None, "tday": None, "tat": None, "t": None}


def first_status():
    return {k: v for k, v in _first.items() if k not in ("tday", "tat", "t")}


def _first_once(proxy, now):
    """그날 첫 봉을 끝난 뒤 아직 안 받은 대상 종목을 받는다 → 남은 수. 그날 할 일이 아니면 None."""
    day = proxy._minutes_trade_day()
    if day != now.strftime("%Y%m%d"):
        return None
    import time
    sec = now.hour * 3600 + now.minute * 60 + now.second
    if sec < (int(market_hours.REG_OPEN[:2]) * 60 + int(market_hours.REG_OPEN[2:]) + BAR_MIN) * 60 + FIRST_GRACE_SEC:
        return None                                # 보통 날 첫 봉 끝 전 — 늦게 여는 날은 그보다 늦으니 장 시각도 안 묻는다(고리가 1초마다 돈다 · qa 덧 11-12)
    if _first.get("tday") != day or time.time() - (_first.get("tat") or 0) >= T_RECHECK_SEC:
        # 그날 장 시각 — 자정에 한 번만 붙잡으면 그 뒤 고친 장 시각(수능 공지)을 못 본다(qa 덧 11-12) · T_RECHECK_SEC 마다 다시 읽음
        _first.update(tday=day, tat=time.time(), t=market_hours.today(proxy, day=day, now=now))
    t = _first["t"]
    if t["open"] is False:
        return None                                # 휴장 — 헛호출 안 함
    bar_hm = t["reg"][0]                           # 그날 여는 시각 — 늦게 여는 날(수능 10:00)은 그 시각의 첫 봉(11-19 「응 해줘」)
    bar_end = int(bar_hm[:2]) * 60 + int(bar_hm[2:]) + BAR_MIN
    if sec < bar_end * 60 + FIRST_GRACE_SEC or now.hour * 60 + now.minute >= bar_end + FIRST_UNTIL_MIN:
        return None
    uni, _ = _universe(proxy)
    cap_min = dart.rank_min_cap_eok()
    codes = [u["code"] for u in uni if u["cap"] is not None and u["cap"] >= cap_min]
    todo = [c for c in codes if (proxy._minutes_fresh_upto(c) or 0) < bar_end]
    _first.update(day=day, got=0, error=None, left=len(todo), at=now.strftime("%H:%M:%S"))   # 그날 셈 — 날이 바뀌면 0 부터(개념정의 덧 11-12)
    cfg = proxy.load_secrets()
    for c in todo:
        if datetime.now(KST).hour * 60 + datetime.now(KST).minute >= bar_end + FIRST_UNTIL_MIN:
            break
        try:
            proxy.get_chart(cfg, c, "5m", 1, gap_check=False)
            _first["got"] += 1
        except Exception as e:
            _first["error"] = type(e).__name__
        _first["left"] -= 1
    _st["at"] = 0.0                              # 판을 바로 다시 센다
    return _first["left"]


def start(proxy):
    """쓰는 서버가 뜰 때 한 번 — 날마다 첫 봉이 끝나는 순간 대상 종목 첫 봉을 먼저 받는다."""
    import threading
    import time
    if not proxy.marketdb.writable():
        return False

    def loop():
        done = None
        while True:
            now = datetime.now(KST)
            try:
                if done != now.strftime("%Y%m%d"):
                    left = _first_once(proxy, now)
                    if left is not None:
                        done = now.strftime("%Y%m%d")
                        print("  [초반상승] %s 첫 봉 먼저 받기 — %d종목 받음 · 남음 %d" % (now.strftime("%H:%M:%S"), _first["got"], left), flush=True)
            except Exception as e:
                _first["error"] = type(e).__name__
            time.sleep(1)

    threading.Thread(target=loop, daemon=True, name="open-rise-first").start()
    return True
