# -*- coding: utf-8 -*-
"""경제 지표 — 한국은행 ECOS · 미국 FRED (2026-10-08 · 재권님 「응 해줘」 · 창구 경유).

Insight 종목분석 ⑥-9 국면 재료 다섯 줄(경기종합지수 · 금리 · 물가 · 재고 · 고용)이 쓴다.
응답 모양은 그 화면을 그리는 `시황분석1` 과 맞췄다(2026-10-08).

    GET /api/macro/regime            다섯 줄 묶음 한 번에
    GET /api/macro/series?ids=a,b    낱개
    GET /api/macro/releases          발표 지표 — 발표일(FRED · 미국 날짜) · 머리 숫자 · 등락 · 마지막 발표가 들어왔나(2026-10-15)

── 어디서 받나 (2026-10-08 실측 · 주식페이지_개발3) ──

    ECOS   https://ecos.bok.or.kr/api/StatisticSearch/{키}/json/kr/1/100/{표}/M/{시작}/{끝}/{항목1}[/{항목2}]
           키는 secrets.json 의 `ecos.api_key` · sample 키는 10건까지라 못 쓴다
    FRED   https://fred.stlouisfed.org/graph/fredgraph.csv?id={계열}&cosd=YYYY-MM-DD   키 없이 받힌다
           날마다 나오는 계열(T10Y2Y · BAMLH0A0HYM2)은 `fq=Monthly&fam=avg` 로 **달 평균**을 받는다 —
           10-08 실측에서 마지막 달은 9월이었다(덜 찬 이번 달은 안 나왔다)

대조(시황분석 10-07 실측과 같았다): 선행 순환변동치 104.2 · 동행 101.7(2026-08) · 국고채 3년 3.991 ·
회사채 3년 AA- 4.663 · 소비자물가 120.43(2026-09) · 제조업 재고율 100.9 · 취업자 28,944천명 · 실업률 2.7(2026-08 · 계절조정).

── 캐시 ──

월간 자료라 **하루 한 번** 받는다(`MACRO_TTL`). 다만 발표일을 알면 **발표 뒤에 다시 받는다** —
하루를 기다리면 발표 값이 최대 하루 늦는다(2026-10-15). 다시 받는 때는 발표 시각 한 시간 뒤와 다음날 07:00 이다. 한 계열이라도 못 받았으면 30분 뒤 다시 받는다(`MACRO_RETRY_TTL`).
화면은 주기로 묻지 않고 열 때 한 번 받는다. 응답의 `cacheTtlSec` 이 지금 값이다.

── 어느 서버가 받나 ──

`ecos` 키가 있는 서버는 직접 받고, 없는 서버는 상류(`KJC_KIS_UPSTREAM`)로 넘긴다 — kis_proxy 의 `_handle_macro`.
KIS 예산은 안 쓴다. 토스처럼 토큰을 서로 끊는 일은 없다.

**못 받은 값은 0 이 아니라 `v: null` · `error` 다** — 그 계열만 비고 나머지는 나온다.
"""
import csv
import io
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from secrets_guard import safe_message, secrets_path

SECRETS_PATH = secrets_path()        # 자리 셈은 secrets_guard 하나
MACRO_TTL = 24 * 3600
MACRO_RETRY_TTL = 30 * 60
POINTS = 36                  # 계열마다 내는 달 수 — 옛것부터
TIMEOUT = 15
KST = timezone(timedelta(hours=9))

ECOS_URL = "https://ecos.bok.or.kr/api/StatisticSearch/%s/json/kr/1/100/%s/M/%s/%s/%s"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# 받는 계열. ecos: (표, 항목1[, 항목2]) · fred: (계열, 달 평균으로 받나)
RAW = [
    # 경기종합지수
    {"id": "kr_cli_lead", "label": "선행지수 순환변동치", "unit": "2020=100", "ecos": ("901Y067", "I16E")},
    {"id": "kr_cli_coin", "label": "동행지수 순환변동치", "unit": "2020=100", "ecos": ("901Y067", "I16D")},
    # 금리
    {"id": "kr_base_rate", "label": "한국은행 기준금리", "unit": "%", "ecos": ("722Y001", "0101000")},
    {"id": "kr_ktb3y", "label": "국고채 3년", "unit": "%", "ecos": ("721Y001", "5020000")},
    {"id": "kr_corp3y_aa", "label": "회사채 3년 AA-", "unit": "%", "ecos": ("721Y001", "7020000")},
    {"id": "us_fedfunds", "label": "미국 기준금리(실효 연방기금금리)", "unit": "%", "fred": ("FEDFUNDS", False)},
    {"id": "us_t10y2y", "label": "미국 장단기 금리차(10년-2년 · 달 평균)", "unit": "%p", "fred": ("T10Y2Y", True)},
    {"id": "us_hy_spread", "label": "미국 하이일드 신용 스프레드(달 평균)", "unit": "%p", "fred": ("BAMLH0A0HYM2", True)},
    # 물가
    {"id": "kr_cpi", "label": "소비자물가 총지수", "unit": "2020=100", "ecos": ("901Y009", "0")},
    {"id": "us_cpi", "label": "미국 소비자물가(CPIAUCSL)", "unit": "1982-84=100", "fred": ("CPIAUCSL", False)},
    # 전년비는 계절조정 안 한 지수로 낸다 — 노동부(BLS) 발표 숫자가 그 기준이다(2026-10-15)
    {"id": "us_cpi_nsa", "label": "미국 소비자물가(CPIAUCNS · 계절조정 안 함)", "unit": "1982-84=100", "fred": ("CPIAUCNS", False)},
    {"id": "us_ppi", "label": "미국 생산자물가(최종 수요)", "unit": "2009-11=100", "fred": ("PPIFIS", False)},
    {"id": "us_pce", "label": "미국 개인소비지출 물가", "unit": "2017=100", "fred": ("PCEPI", False)},
    # 재고
    {"id": "kr_inv_ratio", "label": "제조업 재고율", "unit": "2020=100", "ecos": ("901Y026", "I33A")},
    {"id": "us_isratio", "label": "미국 재고/매출 비율", "unit": "배", "fred": ("ISRATIO", False)},
    # 고용
    {"id": "kr_emp", "label": "취업자 수(계절조정)", "unit": "천명", "ecos": ("901Y027", "I61BA", "I28B")},
    {"id": "kr_unemp", "label": "실업률(계절조정)", "unit": "%", "ecos": ("901Y027", "I61BC", "I28B")},
    {"id": "us_unrate", "label": "미국 실업률", "unit": "%", "fred": ("UNRATE", False)},
    {"id": "us_payems", "label": "미국 비농업 고용", "unit": "천명", "fred": ("PAYEMS", False)},
    {"id": "us_jolts", "label": "미국 구인 건수(JOLTS)", "unit": "천건", "fred": ("JTSJOL", False)},
    {"id": "us_icsa", "label": "미국 신규 실업수당 청구(주간)", "unit": "건", "fred": ("ICSA", False, "W")},
    # 성장 · 소비
    {"id": "us_retail", "label": "미국 소매판매", "unit": "백만 달러", "fred": ("RSAFS", False)},
    {"id": "us_indpro", "label": "미국 산업생산", "unit": "2017=100", "fred": ("INDPRO", False)},
    {"id": "us_umcsent", "label": "미시간대 소비심리", "unit": "1966=100", "fred": ("UMCSENT", False)},
    {"id": "us_gdp", "label": "미국 실질 GDP 성장률(전기비 연율)", "unit": "%", "fred": ("A191RL1Q225SBEA", False, "Q")},
]

# 서버가 계산해 내는 계열 — (원 계열, 방식)
DERIVED = [
    {"id": "kr_cpi_yoy", "label": "소비자물가 전년비", "unit": "%", "from": "kr_cpi", "how": "yoy"},
    {"id": "us_cpi_yoy", "label": "미국 소비자물가 전년비", "unit": "%", "from": "us_cpi_nsa", "how": "yoy"},
    {"id": "us_ppi_mom", "label": "미국 생산자물가 전월비", "unit": "%", "from": "us_ppi", "how": "mom"},
    {"id": "us_pce_yoy", "label": "미국 개인소비지출 물가 전년비", "unit": "%", "from": "us_pce", "how": "yoy"},
    {"id": "us_retail_mom", "label": "미국 소매판매 전월비", "unit": "%", "from": "us_retail", "how": "mom"},
    {"id": "us_indpro_mom", "label": "미국 산업생산 전월비", "unit": "%", "from": "us_indpro", "how": "mom"},
    {"id": "us_payems_chg", "label": "미국 비농업 고용 전월차", "unit": "천명", "from": "us_payems", "how": "diff"},
]

GROUPS = [
    {"key": "cycle", "label": "경기종합지수", "ids": ["kr_cli_lead", "kr_cli_coin"]},
    {"key": "rate", "label": "금리", "ids": ["kr_base_rate", "kr_ktb3y", "kr_corp3y_aa",
                                          "us_fedfunds", "us_t10y2y", "us_hy_spread"]},
    {"key": "price", "label": "물가", "ids": ["kr_cpi", "kr_cpi_yoy", "us_cpi", "us_cpi_yoy"]},
    {"key": "inventory", "label": "재고", "ids": ["kr_inv_ratio", "us_isratio"]},
    {"key": "employment", "label": "고용", "ids": ["kr_emp", "kr_unemp", "us_unrate", "us_payems", "us_payems_chg"]},
]

# ── 발표 지표 (2026-10-15 재권님 「발표날짜랑 등락이 있어야」 · 「값은 Insight 매크로 칸 · 날짜는 홀딩스 주요 일정」 — 「그렇게 해」) ──
# 발표일은 FRED API 의 release/dates(열쇠 `fred.api_key`)가 미리 낸다 — 2026-10-14 실측 · 날짜는 **미국 날짜**다.
# main — 그 발표의 머리 숫자 · lag — 발표 달에서 몇 달 전 분이 나오나(그 달이 들어왔으면 「반영됨」). Q 는 분기 · W 는 주간.
# 미시간대는 그 달 안에 나오지만 FRED 계열은 한 달 늦게 올라온다(2026-10-15 실측 — 09-25 발표 뒤에도 8월이 끝) — 그래서 1
RELEASES = [
    {"key": "cpi", "short": "미국 CPI", "name": "미국 소비자물가(CPI)", "kind": "물가", "fred": 10, "et": "08:30", "main": "us_cpi_yoy", "lag": 1},
    {"key": "ppi", "short": "미국 PPI", "name": "미국 생산자물가(PPI)", "kind": "물가", "fred": 46, "et": "08:30", "main": "us_ppi_mom", "lag": 1},
    {"key": "pce", "short": "미국 PCE 물가", "name": "미국 개인소비지출 물가(PCE)", "kind": "물가", "fred": 54, "et": "08:30", "main": "us_pce_yoy", "lag": 1},
    {"key": "jobs", "short": "미국 고용", "name": "미국 고용(비농업 · 실업률)", "kind": "지표", "fred": 50, "et": "08:30", "main": "us_payems_chg",
     "also": ["us_unrate"], "lag": 1},
    {"key": "claims", "short": "미국 실업수당 청구", "name": "미국 신규 실업수당 청구", "kind": "지표", "fred": 180, "et": "08:30", "main": "us_icsa", "lag": "W"},
    {"key": "jolts", "short": "미국 JOLTS 구인", "name": "미국 구인·이직(JOLTS)", "kind": "지표", "fred": 192, "et": "10:00", "main": "us_jolts", "lag": 2},
    {"key": "retail", "short": "미국 소매판매", "name": "미국 소매판매", "kind": "지표", "fred": 9, "et": "08:30", "main": "us_retail_mom", "lag": 1},
    {"key": "indpro", "short": "미국 산업생산", "name": "미국 산업생산", "kind": "지표", "fred": 13, "et": "09:15", "main": "us_indpro_mom", "lag": 1},
    {"key": "umich", "short": "미시간대 소비심리", "name": "미시간대 소비심리", "kind": "지표", "fred": 91, "et": "10:00", "main": "us_umcsent", "lag": 1},
    {"key": "gdp", "short": "미국 GDP", "name": "미국 국내총생산(GDP)", "kind": "지표", "fred": 53, "et": "08:30", "main": "us_gdp", "lag": "Q"},
]
FRED_API = "https://api.stlouisfed.org/fred/release/dates"
RELEASE_TTL = 24 * 3600
# 발표 뒤 값을 다시 받는 때 — FRED 가 계열에 올리는 데 시간이 걸려 발표 시각 한 시간 뒤와 다음날 07:00(한국) 두 번 받는다
# et — 미국 동부 발표 시각. 서버가 서머타임을 셈해 한국 시각(`nextReleaseKst`)으로 낸다 — 화면에 21:30 · 22:30 을 박지 않는다
# (2026-10-15 재권님 「응 해줘」 · 시황분석 풍선이 21:30 을 박았다가 11-01 뒤 어긋날 자리). 확인한 곳(2026-10-15):
# bls.gov/schedule/news_release 의 cpi · ppi · empsit(08:30) · jolts(10:00) · federalreserve.gov G.17(09:15) ·
# Census 소매 · BEA 소득지출 · GDP · 노동부 실업수당(08:30 — 검색 결과로 확인) · 미시간대(10:00 — 검색 결과로 확인)
ET = ZoneInfo("America/New_York")
REFRESH_LAG = timedelta(hours=1)

ALL_IDS = [r["id"] for r in RAW] + [d["id"] for d in DERIVED]
RAW_BY = {r["id"]: r for r in RAW}

_lock = threading.Lock()
_cache = {"at": 0.0, "ttl": 0, "series": None, "fetchedAt": None}
_rel_lock = threading.Lock()
_rel = {"at": 0.0, "ttl": 0, "dates": None, "error": None}


def ecos_key():
    try:
        with open(SECRETS_PATH, encoding="utf-8") as f:
            e = (json.load(f) or {}).get("ecos") or {}
    except (OSError, ValueError):
        return None
    return (e.get("api_key") or "").strip() or None


def fred_key():
    try:
        with open(SECRETS_PATH, encoding="utf-8") as f:
            e = (json.load(f) or {}).get("fred") or {}
    except (OSError, ValueError):
        return None
    return (e.get("api_key") or "").strip() or None


def _get(url):
    # 이름표(User-Agent)를 따로 안 붙인다 — 2026-10-08 실측: 「Mozilla/5.0 …」 을 붙이면 FRED 가 맥 기본 파이썬
    # (3.9 · LibreSSL · launchd 서버가 쓰는 것)에서는 답을 안 하고 시간 초과로 끝났다. 기본 이름표는 0.5초에 받혔다
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def _months_back(n):
    now = datetime.now(KST)
    y, m = now.year, now.month - n
    while m <= 0:
        y, m = y - 1, m + 12
    return y, m


def _ecos(key, spec):
    y, m = _months_back(POINTS + 14)          # 전년비를 맨 앞 달까지 내려고 열두 달 더
    now = datetime.now(KST)
    url = ECOS_URL % (key, spec[0], "%04d%02d" % (y, m), "%04d%02d" % (now.year, now.month),
                      "/".join(urllib.parse.quote(p) for p in spec[1:]))
    j = json.loads(_get(url))
    rows = (j.get("StatisticSearch") or {}).get("row")
    if not isinstance(rows, list):
        res = j.get("RESULT") or {}
        raise RuntimeError("ECOS %s — %s" % (res.get("CODE", "모양 다름"), res.get("MESSAGE", "")[:80]))
    out = []
    for r in rows:
        t, v = r.get("TIME") or "", r.get("DATA_VALUE")
        if len(t) == 6 and v not in (None, ""):
            out.append({"d": t[:4] + "-" + t[4:], "v": float(v)})
    return out


def _fred(series_id, monthly_avg, freq="M"):
    y, m = _months_back(POINTS + 14)
    q = {"id": series_id, "cosd": "%04d-%02d-01" % (y, m)}
    if monthly_avg:
        q.update(fq="Monthly", fam="avg")
    text = _get(FRED_URL + "?" + urllib.parse.urlencode(q))
    rd = csv.reader(io.StringIO(text))
    head = next(rd, None)
    if not head or len(head) < 2:
        raise RuntimeError("FRED 응답 모양이 다릅니다")
    out = []
    for row in rd:
        if len(row) >= 2 and row[1] not in ("", "."):
            out.append({"d": row[0][:10] if freq == "W" else row[0][:7], "v": float(row[1])})
    return out


def _derive(how, pts):
    by = {p["d"]: p["v"] for p in pts}
    out = []
    for p in pts:
        y, m = int(p["d"][:4]), int(p["d"][5:7])
        if how == "mom":
            pm = (y, m - 1) if m > 1 else (y - 1, 12)
            prev = by.get("%04d-%02d" % pm)
            if prev:
                out.append({"d": p["d"], "v": round((p["v"] / prev - 1) * 100, 2)})
        elif how == "yoy":
            prev = by.get("%04d-%02d" % (y - 1, m))
            if prev:
                out.append({"d": p["d"], "v": round((p["v"] / prev - 1) * 100, 2)})
        else:
            pm = (y, m - 1) if m > 1 else (y - 1, 12)
            prev = by.get("%04d-%02d" % pm)
            if prev is not None:
                out.append({"d": p["d"], "v": round(p["v"] - prev, 1)})
    return out


def _shape(meta, source, pts, error=None):
    pts = pts[-POINTS:] if pts else []
    fred = meta.get("fred") or ()
    return {"label": meta["label"], "unit": meta["unit"], "freq": fred[2] if len(fred) > 2 else "M", "source": source,
            "points": pts,
            "last": pts[-1] if pts else None,
            "prev": pts[-2] if len(pts) > 1 else None,
            "error": error}


def _fetch_all():
    key = ecos_key()
    full, series = {}, {}
    for r in RAW:
        src = "ECOS" if "ecos" in r else "FRED"
        try:
            if src == "ECOS":
                if not key:
                    raise RuntimeError("secrets.json 의 ecos.api_key 가 없습니다")
                pts = _ecos(key, r["ecos"])
            else:
                pts = _fred(*r["fred"])
            if not pts:
                raise RuntimeError("받은 값이 없습니다")
            full[r["id"]] = pts
            series[r["id"]] = _shape(r, src, pts)
        except Exception as e:
            msg = safe_message(e, 160)
            if key:
                msg = msg.replace(key, "<가림>")
            series[r["id"]] = _shape(r, src, None, msg)
    for d in DERIVED:
        base = full.get(d["from"])
        src = series[d["from"]]["source"]
        if base:
            series[d["id"]] = _shape(dict(d, fred=RAW_BY[d["from"]].get("fred")), src, _derive(d["how"], base))
        else:
            series[d["id"]] = _shape(d, src, None, "원 계열(%s)을 못 받았습니다" % d["from"])
    return series


def bundle():
    """전 계열 — 캐시가 살아 있으면 그것을. 돌려주는 것: (series, fetchedAt, 남은 캐시 초)."""
    _release_dates()                 # 발표일을 알아야 「발표 뒤 다시 받기」 때를 잡는다 — 하루 한 번만 실제로 받는다
    with _lock:
        now = time.time()
        if _cache["series"] is None or now - _cache["at"] >= _cache["ttl"]:
            s = _fetch_all()
            bad = any(v["error"] for v in s.values())
            ttl = MACRO_RETRY_TTL if bad else MACRO_TTL
            nxt = _next_refresh(now)
            if nxt is not None:
                ttl = max(60, min(ttl, int(nxt - now)))
            _cache.update(at=now, ttl=ttl, series=s,
                          fetchedAt=datetime.now(KST).isoformat(timespec="seconds"))
        left = int(_cache["ttl"] - (now - _cache["at"]))
        return _cache["series"], _cache["fetchedAt"], max(left, 0)


def regime():
    s, at, left = bundle()
    return {"ok": any(v["points"] for v in s.values()), "fetchedAt": at, "cacheTtlSec": left,
            "groups": GROUPS, "series": s}


def pick(ids):
    """낱개 — 모르는 이름은 unknown 으로 따로 낸다."""
    want = [i for i in ids if i]
    unknown = [i for i in want if i not in ALL_IDS]
    s, at, left = bundle()
    got = {i: s[i] for i in want if i in s}
    return {"ok": bool(got) and any(v["points"] for v in got.values()), "fetchedAt": at,
            "cacheTtlSec": left, "series": got, "unknown": unknown}


# ── 발표일 ──

def _release_dates():
    """{발표 key: ['YYYY-MM-DD', …]} — 앞뒤 넉넉히(지난 40일 · 앞 90일). 하루 한 번 받는다. 못 받으면 (None, 오류)."""
    with _rel_lock:
        now = time.time()
        if _rel["dates"] is not None and now - _rel["at"] < _rel["ttl"]:
            return _rel["dates"], _rel["error"]
        key = fred_key()
        today = datetime.now(KST).date()
        out, err = {}, None
        if not key:
            err = "secrets.json 의 fred.api_key 가 없습니다"
        else:
            for r in RELEASES:
                q = {"release_id": r["fred"], "api_key": key, "file_type": "json", "sort_order": "asc",
                     "include_release_dates_with_no_data": "true",
                     "realtime_start": (today - timedelta(days=40)).isoformat(),
                     "realtime_end": (today + timedelta(days=90)).isoformat()}
                try:
                    j = json.loads(_get(FRED_API + "?" + urllib.parse.urlencode(q)))
                    out[r["key"]] = [d.get("date") for d in j.get("release_dates") or [] if d.get("date")]
                except Exception as e:
                    err = safe_message(e, 160).replace(key, "<가림>")
        _rel.update(at=now, ttl=MACRO_RETRY_TTL if err else RELEASE_TTL, dates=out if out else None, error=err)
        return _rel["dates"], err


def _next_refresh(now):
    """다음 「발표 뒤 다시 받기」 때(epoch) — 발표 시각 한 시간 뒤와 다음날 07:00(한국). 발표일을 못 받았으면 None(하루 한 번 그대로)."""
    dates = _rel["dates"]            # 잠금 없이 읽는다 — bundle 안에서 부르므로 받기를 새로 시작하지 않는다
    if not dates:
        return None
    best = None
    for r in RELEASES:
        for d in dates.get(r["key"]) or []:
            at = _release_at(r, d)
            for t in (at + REFRESH_LAG, (at + timedelta(days=1)).replace(hour=7, minute=0)):
                ts = t.timestamp()
                if ts > now and (best is None or ts < best):
                    best = ts
    return best


def _release_at(rel, day):
    """그 발표의 시각(한국 시간대 datetime) — 미국 날짜 + 미국 동부 시각."""
    hh, mm = (int(x) for x in rel["et"].split(":"))
    y, m, d = (int(x) for x in day.split("-"))
    return datetime(y, m, d, hh, mm, tzinfo=ET).astimezone(KST)


def _expected(rel, day):
    """그 발표일에 나와야 할 기간 — 그 기간이 계열 마지막 점이면 「반영됨」. 주간은 발표일 앞 2주 안."""
    y, m = int(day[:4]), int(day[5:7])
    lag = rel["lag"]
    if lag == "W":
        return None
    if lag == "Q":
        m -= 3
        while m <= 0:
            y, m = y - 1, m + 12
        return "%04d-%02d" % (y, (m - 1) // 3 * 3 + 1)
    m -= lag
    while m <= 0:
        y, m = y - 1, m + 12
    return "%04d-%02d" % (y, m)


def _fresh(rel, day, last):
    if not last or not day:
        return False
    if rel["lag"] == "W":
        d0 = datetime.strptime(day, "%Y-%m-%d").date()
        dl = datetime.strptime(last["d"], "%Y-%m-%d").date()
        return timedelta(0) <= d0 - dl <= timedelta(days=7)
    return last["d"] >= _expected(rel, day)


def releases():
    """GET /api/macro/releases — 발표 지표마다 발표일(지난 · 다음)과 머리 숫자 · 등락.
    머리 숫자는 /api/macro/series 와 같은 값이다(같은 캐시) — 화면이 둘을 따로 받아도 갈리지 않는다."""
    dates, err = _release_dates()
    s, at, left = bundle()
    now = datetime.now(KST)
    items = []
    for r in RELEASES:
        ds = (dates or {}).get(r["key"]) or []
        # 오늘 날짜라도 발표 시각 전이면 아직 「다음」 이다 — 그 발표의 미국 동부 시각으로 가른다
        past = [d for d in ds if _release_at(r, d) <= now]
        last_day = past[-1] if past else None
        nxt = next((d for d in ds if _release_at(r, d) > now), None)
        main = s.get(r["main"]) or {}
        lp, pp = main.get("last"), main.get("prev")
        chg = round(lp["v"] - pp["v"], 2) if lp and pp else None
        items.append({
            "key": r["key"], "name": r["name"], "short": r["short"], "kind": r["kind"], "country": "US",
            "dates": [d for d in ds if d >= (datetime.now(KST).date() - timedelta(days=7)).isoformat()],
            "lastRelease": last_day,
            "nextRelease": nxt,
            "releaseEt": r["et"],
            # 다음 발표의 한국 시각 — 'YYYY-MM-DD HH:MM'. 서머타임은 여기서 셈한다
            "nextReleaseKst": _release_at(r, nxt).astimezone(KST).strftime("%Y-%m-%d %H:%M") if nxt else None,
            "main": r["main"], "label": main.get("label"), "unit": main.get("unit"), "freq": main.get("freq"),
            "last": lp, "prev": pp, "chg": chg,
            # 마지막 발표가 계열에 들어왔나 — 아직이면 last 는 그 전 발표 값이다
            "fresh": _fresh(r, last_day, lp),
            "also": {i: {"label": (s.get(i) or {}).get("label"), "unit": (s.get(i) or {}).get("unit"),
                         "last": (s.get(i) or {}).get("last"), "prev": (s.get(i) or {}).get("prev")}
                     for i in r.get("also", [])},
            "error": main.get("error"),
        })
    return {"ok": bool(dates), "fetchedAt": at, "cacheTtlSec": left, "datesNote": "미국 날짜(FRED release/dates)",
            "datesError": err, "releases": items}
