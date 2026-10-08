# -*- coding: utf-8 -*-
"""경제 지표 — 한국은행 ECOS · 미국 FRED (2026-10-08 · 재권님 「응 해줘」 · 창구 경유).

Insight 종목분석 ⑥-9 국면 재료 다섯 줄(경기종합지수 · 금리 · 물가 · 재고 · 고용)이 쓴다.
응답 모양은 그 화면을 그리는 `시황분석1` 과 맞췄다(2026-10-08).

    GET /api/macro/regime            다섯 줄 묶음 한 번에
    GET /api/macro/series?ids=a,b    낱개

── 어디서 받나 (2026-10-08 실측 · 주식페이지_개발3) ──

    ECOS   https://ecos.bok.or.kr/api/StatisticSearch/{키}/json/kr/1/100/{표}/M/{시작}/{끝}/{항목1}[/{항목2}]
           키는 secrets.json 의 `ecos.api_key` · sample 키는 10건까지라 못 쓴다
    FRED   https://fred.stlouisfed.org/graph/fredgraph.csv?id={계열}&cosd=YYYY-MM-DD   키 없이 받힌다
           날마다 나오는 계열(T10Y2Y · BAMLH0A0HYM2)은 `fq=Monthly&fam=avg` 로 **달 평균**을 받는다 —
           10-08 실측에서 마지막 달은 9월이었다(덜 찬 이번 달은 안 나왔다)

대조(시황분석 10-07 실측과 같았다): 선행 순환변동치 104.2 · 동행 101.7(2026-08) · 국고채 3년 3.991 ·
회사채 3년 AA- 4.663 · 소비자물가 120.43(2026-09) · 제조업 재고율 100.9 · 취업자 28,944천명 · 실업률 2.7(2026-08 · 계절조정).

── 캐시 ──

월간 자료라 **하루 한 번** 받는다(`MACRO_TTL`). 한 계열이라도 못 받았으면 30분 뒤 다시 받는다(`MACRO_RETRY_TTL`).
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

from secrets_guard import safe_message

SECRETS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "secrets.json")
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
    # 재고
    {"id": "kr_inv_ratio", "label": "제조업 재고율", "unit": "2020=100", "ecos": ("901Y026", "I33A")},
    {"id": "us_isratio", "label": "미국 재고/매출 비율", "unit": "배", "fred": ("ISRATIO", False)},
    # 고용
    {"id": "kr_emp", "label": "취업자 수(계절조정)", "unit": "천명", "ecos": ("901Y027", "I61BA", "I28B")},
    {"id": "kr_unemp", "label": "실업률(계절조정)", "unit": "%", "ecos": ("901Y027", "I61BC", "I28B")},
    {"id": "us_unrate", "label": "미국 실업률", "unit": "%", "fred": ("UNRATE", False)},
    {"id": "us_payems", "label": "미국 비농업 고용", "unit": "천명", "fred": ("PAYEMS", False)},
]

# 서버가 계산해 내는 계열 — (원 계열, 방식)
DERIVED = [
    {"id": "kr_cpi_yoy", "label": "소비자물가 전년비", "unit": "%", "from": "kr_cpi", "how": "yoy"},
    {"id": "us_cpi_yoy", "label": "미국 소비자물가 전년비", "unit": "%", "from": "us_cpi", "how": "yoy"},
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

ALL_IDS = [r["id"] for r in RAW] + [d["id"] for d in DERIVED]

_lock = threading.Lock()
_cache = {"at": 0.0, "ttl": 0, "series": None, "fetchedAt": None}


def ecos_key():
    try:
        with open(SECRETS_PATH, encoding="utf-8") as f:
            e = (json.load(f) or {}).get("ecos") or {}
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


def _fred(series_id, monthly_avg):
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
            out.append({"d": row[0][:7], "v": float(row[1])})
    return out


def _derive(how, pts):
    by = {p["d"]: p["v"] for p in pts}
    out = []
    for p in pts:
        y, m = int(p["d"][:4]), int(p["d"][5:7])
        if how == "yoy":
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
    return {"label": meta["label"], "unit": meta["unit"], "freq": "M", "source": source,
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
            series[d["id"]] = _shape(d, src, _derive(d["how"], base))
        else:
            series[d["id"]] = _shape(d, src, None, "원 계열(%s)을 못 받았습니다" % d["from"])
    return series


def bundle():
    """전 계열 — 캐시가 살아 있으면 그것을. 돌려주는 것: (series, fetchedAt, 남은 캐시 초)."""
    with _lock:
        now = time.time()
        if _cache["series"] is None or now - _cache["at"] >= _cache["ttl"]:
            s = _fetch_all()
            bad = any(v["error"] for v in s.values())
            _cache.update(at=now, ttl=MACRO_RETRY_TTL if bad else MACRO_TTL, series=s,
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
