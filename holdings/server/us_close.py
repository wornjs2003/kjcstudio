# -*- coding: utf-8 -*-
"""미국 데일리 저장본에 더하는 미국 마감 값 넷 — 다우 · 러셀 2000 · 미국 10년 국채 금리 · 달러인덱스 (2026-11-18).

경위 — 재권님 「이정보도 그날 새벽 미국장 정보 다 넣어서 저장되게 해줘. 미국장이 안좋을때는 금액조절하는걸 만들려고 해」 →
「없는 다우 · 러셀2000 · 미국 10년 국채 · 달러인덱스는 개발1 서버에 날마다 저장」 에 「응」(20:2x · 시황분석1 창 · 작업우선순위가 나름).
`usdaily-<날>` 의 `indices` 에 지금 줄과 같은 {code, name, value, change, changePct, unit, source} 로 붙는다(daily.start_us_daily).

── 어디서 받나 ──

    넷 다 야후 일봉       ^DJI · ^RUT · ^TNX(CBOE 10년 금리 · % 그대로) · DX-Y.NYB(ICE 달러인덱스 1973=100 — data/metrics.json 의 dxy 와 같은 지수).
                          us_outlook 과 같은 주소 · 같은 짧은 이름(UA)으로 부른다. 공식으로 열어 둔 API 가 아니다(약관 확인 못 함)
    야후가 안 되면         달러인덱스 · 10년은 서버가 이미 받는 market_index.indicator("dxy" · "us10")(네이버 1년 일봉)로 — source 칸에 그렇게 적힌다

**왜 달러 · 금리도 야후가 먼저인가 (11-19 qa 검수)** — 네이버 1년 일봉은 한국 아침에 **어젯밤 봉이 아직 없다**(11-19 08:10 새로 받아도
마지막이 11-17). 그대로 쓰면 07:00 저장본에 다우 · 러셀은 어젯밤 마감 · 달러 · 금리는 그 전날 마감이 들어가 날이 갈린다. 야후는 08:10 에 11-18 봉이 있었다.
지난 날을 채울 때는 네이버도 맞다 — 늦는 것은 마지막 하루뿐이다.

**어느 날 값인가** — 저장본 날짜(한국 아침)보다 **앞 날짜의 마지막 일봉**이 그 밤 미국 마감이다. 한국 07:00 에 달러인덱스는 이미
그날 아시아 거래 중이라 같은 날짜 봉을 쓰면 마감 값이 아니다.
**금리 줄의 `changePct` 는 금리의 % 변화다**(4.10 → 4.14 면 +0.98) — 같은 모양을 맞추려고 둔다. 금리는 보통 %p 로 보므로
`change`(%p)를 함께 싣는다.
**못 받으면 값 칸이 null 이고 `error` 에 까닭** — 0 으로 채우지 않는다.
"""
import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from secrets_guard import safe_message

import market_index

ET = timezone(timedelta(hours=-5))      # 날짜만 가른다 — 미국 마감(16:00 ET)은 서머타임이어도 같은 날짜다
UA = "Mozilla/5.0"                       # 야후는 긴 이름이면 429 — us_outlook · market_index 와 같은 짧은 이름
TIMEOUT = 15
YAHOO_DAILY = "https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=1d"

# (code, 이름, 단위, 야후 열쇠, 야후가 안 될 때 네이버 열쇠 또는 None)
ROWS = (
    ("DJI", "다우", "pt", "^DJI", None),
    ("RUT", "러셀 2000", "pt", "^RUT", None),
    ("US10Y", "미국 10년 국채 금리", "%", "^TNX", "us10"),
    ("DXY", "달러인덱스", "", "DX-Y.NYB", "dxy"),
)
CODES = tuple(r[0] for r in ROWS)
SOURCE = {"yahoo": "야후 파이낸스 일봉", "naver": "네이버 증권 시장지표 일봉(야후를 못 받아 대신)"}


def _yahoo_bars(sym, rng):
    """야후 일봉 → [(미국 날짜 'YYYY-MM-DD', 종가)] (종가 없는 날은 뺀다)."""
    req = urllib.request.Request(YAHOO_DAILY % (urllib.parse.quote(sym), rng), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        res = json.loads(r.read().decode("utf-8", "replace"))["chart"]["result"][0]
    ts = res.get("timestamp") or []
    closes = ((res.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    out = {}
    for t, c in zip(ts, closes):
        if c is not None:
            out[datetime.fromtimestamp(t, ET).date().isoformat()] = float(c)    # 같은 날짜가 두 번 오면 뒤(장중 갱신)가 이긴다
    return sorted(out.items())


def _naver_bars(key):
    got = market_index.indicator(key) or {}
    bars = [(b["d"], b["c"]) for b in (got.get("bars") or []) if b.get("c") is not None]
    if not bars:
        raise RuntimeError(got.get("error") or "받은 값이 없습니다")
    return bars


def _err(e):
    return "%s: %s" % (type(e).__name__, safe_message(e, 120))


def series(rng="1mo"):
    """넷의 일봉 — {code: ([(날짜, 종가)], 오류 또는 None, 받은 곳 'yahoo' · 'naver')}. rng 는 야후 기간(1mo · 1y)."""
    out = {}
    for code, _name, _unit, ysym, nkey in ROWS:
        try:
            out[code] = (_yahoo_bars(ysym, rng), None, "yahoo")
            continue
        except Exception as e:
            yerr = "야후 " + _err(e)
        if not nkey:
            out[code] = ([], yerr, "yahoo")
            continue
        try:
            out[code] = (_naver_bars(nkey), None, "naver")
        except Exception as e:
            out[code] = ([], yerr + " · 네이버 " + _err(e), "naver")
    return out


def rows_for(day, ser):
    """저장본 날짜(`date` · 한국) → 넷의 줄. 그 날짜보다 앞의 마지막 봉과 그 앞 봉으로 셈한다."""
    d0 = day.isoformat() if isinstance(day, date) else str(day)
    out = []
    for code, name, unit, _ysym, _nkey in ROWS:
        bars, err, src = ser.get(code, ([], "못 셈", "yahoo"))
        before = [b for b in bars if b[0] < d0]
        row = {"code": code, "name": name, "unit": unit, "source": SOURCE[src],
               "value": None, "change": None, "changePct": None, "date": None, "error": None}
        if len(before) >= 2 and before[-2][1]:
            (d, c), (_pd, pc) = before[-1], before[-2]
            row.update(value=round(c, 3), change=round(c - pc, 3), changePct=round((c / pc - 1) * 100, 2), date=d)
        else:
            row["error"] = err or "그 날 앞 봉이 모자랍니다"
        out.append(row)
    return out


def merge_into(indices, extra):
    """저장본 지수 목록에 넷을 붙인다 — 같은 code 는 갈아 끼운다(다시 채울 때).
    새 줄이 못 받은 줄(value null)이고 있던 줄에 값이 있으면 있던 줄을 남긴다 — 다시 셀 때 한 출처가 실패해 값을 null 로 덮지 않게(11-19 qa)."""
    old = {i.get("code"): i for i in (indices or []) if i.get("code") in CODES}
    keep = [i for i in (indices or []) if i.get("code") not in CODES]
    rows = []
    for r in extra:
        o = old.get(r.get("code"))
        rows.append(o if r.get("value") is None and o and o.get("value") is not None else r)
    return keep + rows
