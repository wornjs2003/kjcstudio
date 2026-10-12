# -*- coding: utf-8 -*-
"""시장지표 — 홀딩스 홈 「시장지표」 갈래의 칩 열하나와 큰 차트 1년치 (2026-10-12 · 재권님 「응 해줘」 · 창구 경유).

값은 **네이버 증권 시장지표** 하나에서 받는다(재권님 「네이버 값을 기준으로」). 공개 API 가 아니고 그 화면에
「무단 배포 금지」 가 붙어 있다 — 우리 화면에 그리는 데만 쓴다. 브라우저는 교차 출처라 직접 못 불러 서버가 받는다.

    GET /api/market/indicators          칩 열하나 — 마지막 값 · 앞 값 · 날짜 · 봉인가 선인가
    GET /api/market/indicator?key=us10  그 지표 1년 일별 — 봉이면 시가·고가·저가·종가, 선이면 종가

── 어디서 받나 (2026-10-12 실측 · 주식페이지_개발) ──

    https://stock.naver.com/api/securityService/marketindex/<갈래>/<코드>/prices?page=N&pageSize=60
    한 쪽에 60일 · 다섯 쪽이면 1년 · 코드의 `=` 는 `%3D` 로

── 봉인가 선인가 (재권님 「캔들이 없으면 그래프로만 그려도 돼」) ──

    봉   달러인덱스 · 국채 넷        시가·고가·저가·종가가 다 온다
    선   원/달러 · 원/100엔          시가·고가·저가 칸이 **아예 없다** — 은행 고시 기준율 종가뿐(영영)
         회사채 AA-                  시가·고가·저가가 0 으로 온다 — 하루 한 번 정하는 평가 금리(영영)
         신용 가산금리               AA- 종가 − 국고채 3년 종가. **같은 출처(네이버)끼리 뺀다** — ECOS 국고채와 섞으면
                                     10-08 에 3.994 · 3.983 으로 갈렸다
         BDI · 상하이 컨테이너         네 값이 날마다 같다 — 하루(주) 한 번 발표하는 지수(영영)

**깨진 봉은 여기서 고친다** — 2026-10-12 실측 1년치에서 고가·저가가 0 으로 온 날이 미국 2년 8일 · 10년 1일,
종가가 고가·저가 밖인 날이 달러인덱스 5일 · 미국 2년 1일이었다. 0 이면 시가·종가로 메우고 밖이면 넓힌다.
몇 개를 고쳤는지는 응답 `fixed` 에 낸다.

── 캐시 · 어느 서버가 받나 ──

1년치는 하루 한 번(`HIST_TTL`) · 최근 열흘은 몇 분마다(`RECENT_TTL`) 받아 날짜로 합친다 — 칩 값이 하루 내내 묵지 않게.
화면은 주기로 묻지 않고 갈래를 열 때 받는다. 응답의 `cacheTtlSec` 이 지금 값이다.
**받는 것은 상류(8765)다** — 상류가 있는 서버는 넘긴다(kis_proxy 의 `_handle_market`). KIS 예산은 안 쓴다.

**못 받은 값은 0 이 아니라 `last: null` · `error` 다** — 그 지표만 비고 나머지는 나온다.
"""
import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from secrets_guard import safe_message

HIST_TTL = 24 * 3600
RECENT_TTL = 5 * 60
RETRY_TTL = 10 * 60           # 하나라도 못 받았을 때 1년치를 다시 받는 간격
PAGES = 5
PAGE_SIZE = 60
RECENT_SIZE = 10
TIMEOUT = 15
KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
URL = "https://stock.naver.com/api/securityService/marketindex/%s/%s/prices?page=%d&pageSize=%d"

# 칩 순서 그대로. digits = 화면 소수 자리 · unit = 값 뒤에 붙는 글자 · kind = candle(봉) | line(선)
ITEMS = [
    {"key": "usdkrw", "name": "원/달러", "group": "환율", "cat": "exchange", "code": "FX_USDKRW", "unit": "원", "digits": 2, "kind": "line"},
    {"key": "jpykrw", "name": "원/100엔", "group": "환율", "cat": "exchange", "code": "FX_JPYKRW", "unit": "원", "digits": 2, "kind": "line"},
    {"key": "dxy", "name": "달러인덱스", "group": "환율", "cat": "exchange", "code": ".DXY", "unit": "", "digits": 2, "kind": "candle"},
    {"key": "us10", "name": "미국 10년", "group": "국채", "cat": "bond", "code": "US10YT=RR", "unit": "%", "digits": 3, "kind": "candle"},
    {"key": "us2", "name": "미국 2년", "group": "국채", "cat": "bond", "code": "US2YT=RR", "unit": "%", "digits": 3, "kind": "candle"},
    {"key": "kr10", "name": "한국 10년", "group": "국채", "cat": "bond", "code": "KR10YT=RR", "unit": "%", "digits": 3, "kind": "candle"},
    {"key": "kr3", "name": "한국 3년", "group": "국채", "cat": "bond", "code": "KR3YT=RR", "unit": "%", "digits": 3, "kind": "candle"},
    {"key": "aa", "name": "회사채 AA-", "group": "회사채", "cat": "domesticInterest", "code": "KFIA103009", "unit": "%", "digits": 3, "kind": "line"},
    {"key": "spread", "name": "신용 가산금리", "group": "회사채", "from": ("aa", "kr3"), "unit": "%p", "digits": 3, "kind": "line"},
    {"key": "bdi", "name": "건화물 운임 BDI", "group": "운임", "cat": "transport", "code": ".BADI", "unit": "", "digits": 0, "kind": "line"},
    {"key": "scfi", "name": "상하이 컨테이너", "group": "운임", "cat": "transport", "code": ".SCFIDXSSE", "unit": "", "digits": 2, "kind": "line", "freq": "주간"},
]
BY_KEY = {i["key"]: i for i in ITEMS}
META_KEYS = ("key", "name", "group", "unit", "digits", "kind", "freq")

_lock = threading.Lock()
_hist = {"at": 0.0, "ttl": 0, "rows": {}, "err": {}}
_recent = {"at": 0.0, "rows": {}, "err": {}}
_fetched = {"at": None}


def _num(x):
    if x in (None, "", "-"):
        return None
    try:
        return float(str(x).replace(",", ""))
    except ValueError:
        return None


def _page(it, page, size):
    url = URL % (it["cat"], urllib.parse.quote(it["code"], safe=""), page, size)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        j = json.loads(r.read().decode("utf-8", "replace"))
    if not isinstance(j, list):
        raise RuntimeError("네이버 응답 모양이 다릅니다")
    out = []
    for r in j:
        d = str(r.get("localTradedAt") or "")[:10]
        c = _num(r.get("closePrice"))
        if len(d) == 10 and c is not None:
            out.append([d, _num(r.get("openPrice")), _num(r.get("highPrice")), _num(r.get("lowPrice")), c])
    return out


def _fetch(it, pages, size):
    rows = []
    for p in range(1, pages + 1):
        got = _page(it, p, size)
        rows += got
        if len(got) < size:
            break
    return rows


def _merge(*lists):
    by = {}
    for rows in lists:
        for r in rows or []:
            by[r[0]] = r
    return [by[d] for d in sorted(by)]


def _fix(rows):
    """봉 고치기 — 돌려주는 것: (고친 줄, 고친 날 수)."""
    out, n = [], 0
    for d, o, h, l, c in rows:
        if o is None or o <= 0:
            o = c
        if not h or not l or h <= 0 or l <= 0:
            out.append([d, o, max(o, c), min(o, c), c]); n += 1
        elif h < max(o, c) or l > min(o, c):
            out.append([d, o, max(h, o, c), min(l, o, c), c]); n += 1
        else:
            out.append([d, o, h, l, c])
    return out, n


def _refresh():
    """캐시가 죽었으면 받는다. 잠금 안에서 부른다."""
    now = time.time()
    real = [i for i in ITEMS if "code" in i]
    if now - _hist["at"] >= _hist["ttl"]:
        rows, err = {}, {}
        for it in real:
            try:
                rows[it["key"]] = _fetch(it, PAGES, PAGE_SIZE)
            except Exception as e:
                err[it["key"]] = safe_message(e, 160)
                if it["key"] in _hist["rows"]:
                    rows[it["key"]] = _hist["rows"][it["key"]]     # 못 받으면 어제 것을 그대로 둔다
        _hist.update(at=now, ttl=RETRY_TTL if err else HIST_TTL, rows=rows, err=err)
        _recent.update(at=0.0)
    if now - _recent["at"] >= RECENT_TTL:
        rows, err = {}, {}
        for it in real:
            try:
                rows[it["key"]] = _fetch(it, 1, RECENT_SIZE)
            except Exception as e:
                err[it["key"]] = safe_message(e, 160)
        _recent.update(at=now, rows=rows, err=err)
        _fetched["at"] = datetime.now(KST).isoformat(timespec="seconds")


def _series(key):
    """한 지표 1년치 — (줄, 오류). 봉이 아니면 시가·고가·저가는 None."""
    it = BY_KEY[key]
    if "from" in it:
        a, b = (_series(k)[0] for k in it["from"])
        bm = {r[0]: r[4] for r in b}
        rows = [[r[0], None, None, None, round(r[4] - bm[r[0]], 3)] for r in a if r[0] in bm]
        errs = [e for e in (_series(k)[1] for k in it["from"]) if e]
        return rows, ("; ".join(errs) or None)
    rows = _merge(_hist["rows"].get(key), _recent["rows"].get(key))
    if rows:
        start = (date.fromisoformat(rows[-1][0]) - timedelta(days=365)).isoformat()
        rows = [r for r in rows if r[0] > start]
    if it["kind"] != "candle":
        rows = [[r[0], None, None, None, r[4]] for r in rows]
    return rows, (_recent["err"].get(key) or _hist["err"].get(key))


def _left():
    now = time.time()
    return max(0, int(min(_hist["ttl"] - (now - _hist["at"]), RECENT_TTL - (now - _recent["at"]))))


def indicators():
    with _lock:
        _refresh()
        out = []
        for it in ITEMS:
            rows, err = _series(it["key"])
            last = rows[-1] if rows else None
            prev = rows[-2] if len(rows) > 1 else None
            out.append({**{k: it.get(k) for k in META_KEYS},
                        "last": {"d": last[0], "c": last[4]} if last else None,
                        "prev": {"d": prev[0], "c": prev[4]} if prev else None,
                        "error": None if last else (err or "받은 값이 없습니다")})
        return {"ok": any(i["last"] for i in out), "source": "네이버 증권 시장지표",
                "fetchedAt": _fetched["at"], "cacheTtlSec": _left(), "items": out}


def indicator(key):
    if key not in BY_KEY:
        return None
    with _lock:
        _refresh()
        it = BY_KEY[key]
        rows, err = _series(key)
        fixed = 0
        if it["kind"] == "candle":
            rows, fixed = _fix(rows)
        bars = [{"d": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4]} if it["kind"] == "candle"
                else {"d": r[0], "c": r[4]} for r in rows]
        return {"ok": bool(bars), "source": "네이버 증권 시장지표", "fetchedAt": _fetched["at"],
                "cacheTtlSec": _left(), "item": {k: it.get(k) for k in META_KEYS},
                "bars": bars, "fixed": fixed, "error": None if bars else (err or "받은 값이 없습니다")}
