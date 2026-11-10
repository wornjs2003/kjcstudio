# -*- coding: utf-8 -*-
"""장 시각 한 곳 — 평소 시각 상수 + 그날 값(휴장 · 바뀐 시각) (2026-11-07 · 작업우선순위 배분 이벤트 대응 ③).

재권님 — 이벤트 대응 묶음(「해당 이벤트가 발생했을때 가져오는 정보들도 정확히 가져오도록」) ③ 휴장일 · 장 지연 · 연장 · 조기 폐장 →
안 그림 temp/dev2-hours 에 「응 해줘」(개발2 창 · 11-07). 「장 시각 상수 한 곳」 카드(개발)와 자리가 같아 개발 · 작업우선순위와 맞춤 —
**이 파일을 개발2 가 먼저 만들고, 개발이 뒤에 자기 쪽 장 시각(vwap.py SESSIONS · kis_proxy MINUTE_DAY_END · chart.js 세로선)과
market_event · watch_log 것을 여기로 옮긴다.** 다른 곳에 장 시각 숫자를 새로 박지 않는다(「같은 값은 한 곳에만 둔다」).

── 평소 시각(HHMM) ──

    PRE_OPEN ~ PRE_CLOSE    넥스트레이드 프리마켓
    REG_OPEN ~ REG_CLOSE    정규장(KRX)
    ~ AFTER_CLOSE           넥스트레이드 애프터마켓 끝

── 그날 값 — 어디서 ──

    열리나     KIS 국내휴장일조회(CTCA0903R · /chk-holiday) — 공식 예제 「원장 서비스와 연관 · 가급적 1일 1회」 라 보내는 서버(8765)가
               하루 한 번(HOLIDAY_AT 뒤) 부른다. 한 번에 기준일부터 앞날 여럿이 온다(11-07 잼 — 11-13~11-20 등 · 칸 opnd_yn 개장일 ·
               bzdy_yn 영업일 · tr_day_yn 거래일 · sttl_day_yn 결제일). 받은 날들을 market.db market_day 에 쌓는다
    바뀐 시각   KIS 에 없다(11-19 수능날도 「개장 Y」 만 · 11-07 잼). 거래소가 미리 발표하는 날(수능 · 새해 첫날)은 보드 문서
               DOC(`/api/board/doc/market-hours`)의 days 에 {"YYYYMMDD": {"open": "1000", "close": "1630", "why": "수능"}} 로 적는다 —
               적는 것은 사람(재권님 · 세션)이다. 정규장만 옮긴다 — 넥스트레이드 쪽 바뀐 시각은 그 날 칸에 pre · after 로 따로 적으면 쓴다
    알림       거래소 공시(KIND 오늘의공시 RSS)에 HOURS_WORDS 가 든 글이 오면 notices 에 모은다 — 표에 적을지는 사람이 본다
               (평일 NOTICE_FROM~NOTICE_TO 에 NOTICE_SEC 마다 · 정확한 제목은 못 쟀다)
    못 하는 것  갑자기 생긴 장 지연(전산 고장)은 미리 알 길이 없다 — 공시가 오면 알리는 데까지

── 내는 것 ──

    today()   {"day", "open"(True · False · None=못 쟀다), "reg": [여는, 닫는], "pre", "after", "why", "src"} — 서버 다른 일이 부른다
    board()   주소 /api/alerts/market-hours 의 data — today + 앞날 몇 · notices · 홈 맨 위 띠(market-event.js)가 쓴다
"""
import json
import re
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
PRE_OPEN, PRE_CLOSE = "0800", "0850"
REG_OPEN, REG_CLOSE = "0900", "1530"
AFTER_CLOSE = "2000"
PREOPEN_AUCTION_MIN = 30             # 정규장 여는 시각 앞 동시호가(KRX 08:30~09:00) 길이 — 예상 체결가가 오는 때(2026-11-10 · kis_proxy fetch_asking)
HOLIDAY_AT = (6, 30)                 # 이 시각 뒤 하루 한 번 휴장일 조회
TICK_SEC = 60
NOTICE_SEC = 600
NOTICE_FROM, NOTICE_TO = (7, 0), (18, 0)
AHEAD_DAYS = 10                      # board 에 내는 앞날 수
DOC = "market-hours"
KIND_RSS = ("https://kind.krx.co.kr/disclosure/rsstodaydistribute.do?method=searchRssTodayDistribute"
            "&repIsuSrtCd=&mktTpCd=0&searchCorpName=&currentPageSize=100")
HOURS_WORDS = ("매매거래시간", "거래시간 변경", "거래시간변경", "개장시간", "개장 시간", "개장 지연", "장 개시 지연", "휴장")

_SCHEMA = """CREATE TABLE IF NOT EXISTS market_day (
    day TEXT PRIMARY KEY, open_yn TEXT, row TEXT, saved_at TEXT)"""
_st = {"fetched": None, "error": None, "notices": [], "noticeAt": None, "noticeError": None}
_lock = threading.Lock()


def _now():
    return datetime.now(KST)


def _hhmm(t):
    return t if t is None else str(t).replace(":", "")[:4]


def _doc_days():
    try:
        import docstore
        doc = docstore.read_doc(DOC) or {}
        return doc.get("days") or {}
    except Exception:
        return {}


def _kis_day(proxy, day):
    try:
        with proxy.db_conn() as conn:
            r = conn.execute("SELECT open_yn FROM market_day WHERE day = ?", (day,)).fetchone()
        return r[0] if r else None
    except Exception:
        return None                  # 표가 아직 없음


def today(proxy, day=None, now=None):
    """그날 장 — 열리나 · 정규장 · 프리 · 애프터 시각 · 왜. 휴장일 표에 그날이 없으면 open 은 주말만 가르고 나머지 None(못 쟀다)."""
    now = now or _now()
    day = day or now.strftime("%Y%m%d")
    wd = datetime.strptime(day, "%Y%m%d").weekday()
    yn = _kis_day(proxy, day)
    ch = _doc_days().get(day) or {}
    if yn in ("Y", "N"):
        open_ = yn == "Y"
        src = "KIS 휴장일"
    elif wd >= 5:
        open_, src = False, "주말"
    else:
        open_, src = None, "못 쟀다"
    if ch.get("closed"):
        open_, src = False, "표"
    reg = [_hhmm(ch.get("open")) or REG_OPEN, _hhmm(ch.get("close")) or REG_CLOSE]
    pre = [_hhmm((ch.get("pre") or [None, None])[0]) or PRE_OPEN, _hhmm((ch.get("pre") or [None, None])[1]) or PRE_CLOSE]
    after = [reg[1], _hhmm((ch.get("after") or [None, None])[1]) or AFTER_CLOSE]
    changed = bool(ch) and (reg != [REG_OPEN, REG_CLOSE] or ch.get("closed"))
    why = ch.get("why") or (None if open_ is not False else ("주말" if wd >= 5 else "휴장일"))
    return {"day": day, "open": open_, "reg": reg, "pre": pre, "after": after, "changed": changed, "why": why, "src": src,
            "usual": {"reg": [REG_OPEN, REG_CLOSE], "pre": [PRE_OPEN, PRE_CLOSE], "afterClose": AFTER_CLOSE}}


def in_regular(proxy, now=None):
    """지금 정규장 시간인가 — 휴장이면 False · 바뀐 시각을 따른다. 그날 열리는지 못 쟀으면 평일은 연 것으로 본다."""
    now = now or _now()
    t = today(proxy, now=now)
    if t["open"] is False:
        return False
    hm = now.strftime("%H%M")
    return t["reg"][0] <= hm < t["reg"][1]


def in_preopen_auction(proxy, now=None):
    """지금 장 전 동시호가인가 — 그날 정규장 여는 시각 앞 PREOPEN_AUCTION_MIN 분. 휴장이면 False · 바뀐 시각(수능 10:00)을 따른다."""
    now = now or _now()
    t = today(proxy, now=now)
    if t["open"] is False:
        return False
    o = t["reg"][0]
    m = int(o[:2]) * 60 + int(o[2:]) - PREOPEN_AUCTION_MIN
    return "%02d%02d" % (m // 60, m % 60) <= now.strftime("%H%M") < o


def fetch_holidays(proxy, cfg, day):
    """KIS 휴장일 조회 한 번 — 기준일부터 앞날들을 market_day 에 쌓는다. 쌓은 날 수."""
    d = proxy.kis_get(cfg, "/uapi/domestic-stock/v1/quotations/chk-holiday",
                      {"BASS_DT": day, "CTX_AREA_FK": "", "CTX_AREA_NK": ""}, "CTCA0903R")
    rows = [r for r in (d.get("output") or []) if r.get("bass_dt")]
    at = _now().strftime("%Y-%m-%d %H:%M:%S")
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        conn.executemany("INSERT OR REPLACE INTO market_day (day, open_yn, row, saved_at) VALUES (?,?,?,?)",
                         [(r["bass_dt"], r.get("opnd_yn"), json.dumps(r, ensure_ascii=False), at) for r in rows])
    return len(rows)


def _notice_tick():
    req = urllib.request.Request(KIND_RSS, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        xml = r.read().decode("utf-8", "replace")
    at = _now().strftime("%m-%d %H:%M")
    for title in re.findall(r"<item>.*?<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", xml, re.S):
        title = title.strip()
        if any(w in title for w in HOURS_WORDS) and title not in [n["title"] for n in _st["notices"]]:
            _st["notices"] = (_st["notices"] + [{"title": title, "at": at}])[-20:]
            print("  [장 시각] 거래소 공시 — %s (표에 적을지 봐 주십시오)" % title, flush=True)
    _st["noticeAt"] = at


def board(proxy, now=None):
    now = now or _now()
    t = today(proxy, now=now)
    ahead, d = [], now.date()
    for _ in range(AHEAD_DAYS):
        d += timedelta(days=1)
        x = today(proxy, day=d.strftime("%Y%m%d"), now=now)
        if (x["open"] is False and d.weekday() < 5) or x["changed"]:
            ahead.append(x)                  # 앞날은 「평일인데 쉬는 날 · 시각이 바뀐 날」 만
    return {"today": t, "ahead": ahead, "notices": list(_st["notices"]), "noticeAt": _st["noticeAt"]}


def status():
    return dict(fetched=_st["fetched"], error=_st["error"], noticeError=_st["noticeError"],
                holidayAt="%02d:%02d" % HOLIDAY_AT, doc="/api/board/doc/" + DOC)


def start(proxy):
    """보내는 서버(8765)가 뜰 때 한 번 — 휴장일 하루 한 번 · 거래소 공시 거래시간 글 모으기."""
    def loop():
        time.sleep(30)
        last_notice = 0
        while True:
            now = _now()
            day = now.strftime("%Y%m%d")
            if (now.hour, now.minute) >= HOLIDAY_AT and _st["fetched"] != day:
                try:
                    n = fetch_holidays(proxy, proxy.load_secrets(), day)
                    _st.update(fetched=day, error=None)
                    print("  [장 시각] 휴장일 %d일 받음(%s 부터)" % (n, day), flush=True)
                except Exception as e:
                    _st["error"] = proxy.safe_message(e, 120)
            if now.weekday() < 5 and NOTICE_FROM <= (now.hour, now.minute) < NOTICE_TO and time.time() - last_notice >= NOTICE_SEC:
                last_notice = time.time()
                try:
                    _notice_tick()
                    _st["noticeError"] = None
                except Exception as e:
                    _st["noticeError"] = proxy.safe_message(e, 120)
            time.sleep(TICK_SEC)

    threading.Thread(target=loop, daemon=True, name="market-hours").start()
    return True
