# -*- coding: utf-8 -*-
"""종목 풍선 — 섹터 · 주요 매출원 (2026-10-26 재권님 「실시간 순위나 차트 종목 이름위에 마우스 올리면 해당 종목의 섹터나
주요매출원을 보고싶은데」 → 출처 「(다) 둘 다」 · 작업우선순위 경유).

    네이버(FnGuide) 기업분석   섹터 둘(거래소 업종 · WICS) + 기업개요 세 줄 — 순위 350종목 거의 다 · 비중 % 없음 · 비공식(바뀔 수 있다)
    DART 정기보고서           「주요 제품 및 서비스」 절의 매출 표 — 공식 · 비중 % 있음 · 표 모양이 회사마다 달라 읽히는 종목만

화면은 `/api/dart/profile?code=` 하나로 받는다(kis_proxy.py). **값은 이 파일 한 곳이 받는다** — Insight 의 회사 카드 도구
(company-setup/tools/fetch-company-cards.py)도 같은 DART 표를 읽는데, 두 구역이 같은 값을 쓰면 홀딩스 서버가 기준이다
(CLAUDE.md 「두 구역이 같은 값을 쓰면」). 표를 읽는 셈(`_section` · `_tables` · 매출 표 고르기)은 그 도구에서 옮겨 왔다 —
**지금은 두 벌이다.** 그 도구가 이 주소를 부르게 바뀌면 한 벌이 된다(시황분석에 알림).

받은 값은 서버 폴더의 `holdings/.company-profile.json`(git 밖)에 쥔다 — 개요는 PROFILE_TTL, DART 표는 DART_TTL 동안 다시 안 받는다.
못 받은 칸은 지어내지 않고 `null` + 까닭(`error`)을 남긴다. 처음 보는 종목은 그 자리에서 받는다(네이버 한 번 · DART 두 번).
"""
import io
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone

import dart
from docstore import write_json_atomic
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))
HOLDINGS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_PATH = os.path.join(HOLDINGS_DIR, ".company-profile.json")

PROFILE_TTL = 7 * 86400        # 기업개요 · 섹터 — 거의 안 바뀐다
DART_TTL = 7 * 86400           # 새 정기보고서가 나왔나 일주일에 한 번 본다(분기마다 나온다)
FAIL_TTL = 86400               # 못 받았으면 하루 뒤 다시
NAVER_URL = "https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd=%s"
UA = "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/120 Safari/537.36"
TBL_ROWS, TBL_CELL = 12, 60    # 표는 줄 · 칸 그대로 옮기되 길이만 자른다(해석하지 않는다)
SUMMARY_MAX = 3
DART_VER = 2                   # 쥔 DART 값의 모양 — 바뀌면 다시 받는다(2: 합친 칸 spans · qa 검수 10-26)

_store = None
_lock = threading.Lock()
_busy = {}                     # code -> threading.Lock — 같은 종목을 둘이 동시에 받지 않게


def _load():
    global _store
    if _store is None:
        try:
            with open(STORE_PATH, encoding="utf-8") as f:
                _store = json.load(f)
        except (OSError, ValueError):
            _store = {}
    return _store


def _save():
    try:
        write_json_atomic(STORE_PATH, _store, indent=None)
    except Exception as e:
        print("[종목 풍선] 저장 못 함 (%s)" % type(e).__name__, flush=True)


def _now():
    return datetime.now(KST).isoformat(timespec="seconds")


def _age(part):
    try:
        return time.time() - datetime.fromisoformat(part["at"]).timestamp()
    except (KeyError, TypeError, ValueError):
        return float("inf")


def _clean(s):
    t = re.sub(r"<[^>]+>", " ", s or "")
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'")
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------- 네이버(FnGuide)

def fetch_naver(code):
    """섹터 둘 + 기업개요 줄. ETF 처럼 개요가 없는 종목은 빈 값 · error."""
    req = urllib.request.Request(NAVER_URL % code, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode("utf-8", "replace")
    lines = [_clean(x) for x in re.findall(r'class="line-left">([^<]*)<', html)]
    krx = next((x.split(":", 1)[1].strip() for x in lines if re.match(r"(KOSPI|KOSDAQ|KONEX)\s*:", x)), None)
    wics = next((x.split(":", 1)[1].strip() for x in lines if x.startswith("WICS")), None)
    summary = [_clean(x) for x in re.findall(r'class="dot_cmp"[^>]*>(.*?)</li>', html, re.S)][:SUMMARY_MAX]
    out = {"at": _now(), "krx": krx or None, "wics": wics or None, "summary": [s for s in summary if s],
           "from": "https://finance.naver.com/item/coinfo.naver?code=%s" % code}
    if not (out["krx"] or out["wics"] or out["summary"]):
        out["error"] = "개요 없음(ETF · 리츠 등)"
    return out


# ---------------------------------------------------------------- DART 정기보고서 매출 표
# 셈은 company-setup/tools/fetch-company-cards.py 의 `_section` · `_tables` · `biz_tables`(매출 표 갈래)에서 옮겼다.

def _section(x, pat):
    ts = [(m.start(), _clean(m.group(1))) for m in re.finditer(r"<TITLE[^>]*>(.*?)</TITLE>", x, re.S)]
    for i, (p, t) in enumerate(ts):
        if i and re.search(pat, t) and not t.startswith("목"):
            return x[p: ts[i + 1][0] if i + 1 < len(ts) else len(x)]
    return None


def _span(attrs, name):
    m = re.search(name + r'\s*=\s*"?(\d+)', attrs or "", re.I)
    return int(m.group(1)) if m and int(m.group(1)) > 1 else 1


def _tables(sec, spans=False):
    """표마다 줄 목록. spans=True 면 (줄 목록, 칸마다 [줄 합침, 칸 합침]) — 원본의 ROWSPAN · COLSPAN 을 남겨야
    화면이 칸을 제자리에 놓는다(안 남기면 「매출액 · 비중」 줄이 한 칸씩 왼쪽으로 밀린다 · qa 검수 10-26)."""
    out = []
    for m in re.finditer(r"<TABLE(.*?)</TABLE>", sec or "", re.S):
        rows, sp = [], []
        for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", m.group(1), re.S):
            cells = re.findall(r"<T[DHEU]([^>]*)>(.*?)</T[DHEU]>", tr, re.S)
            row = [_clean(c)[:TBL_CELL] for _a, c in cells]
            if any(row):
                rows.append(row)
                sp.append([[_span(a, "ROWSPAN"), _span(a, "COLSPAN")] for a, _c in cells])
        out.append((rows, sp) if spans else rows)
    return out


def _unit_before(ts, i):
    if i and len(ts[i - 1]) == 1:
        u = " ".join(ts[i - 1][0])
        if "단위" in u:
            return u
    return None


def _corp_code(code):
    with dart._db_lock, dart.db_conn() as conn:
        r = conn.execute("SELECT corp_code FROM dart_corps WHERE stock_code = ?", (code,)).fetchone()
    return r["corp_code"] if r else None


def fetch_dart(code, key, prev=None):
    """최신 정기보고서의 「주요 제품」 매출 표. 쥔 보고서와 같으면 문서를 다시 안 받는다."""
    cc = _corp_code(code)
    if not cc:
        return {"at": _now(), "product": None, "error": "DART 고유번호 없음"}
    bgn = (datetime.now(KST) - timedelta(days=400)).strftime("%Y%m%d")
    q = urllib.parse.urlencode({"crtfc_key": key, "corp_code": cc, "bgn_de": bgn, "pblntf_ty": "A", "page_count": 20})
    lst = json.loads(dart._dart_get(dart.DART_API + "/list.json?" + q, 15).decode("utf-8", "replace"))
    reps = [x for x in lst.get("list") or [] if re.search(r"사업보고서|반기보고서|분기보고서", x.get("report_nm", ""))]
    if not reps:
        return {"at": _now(), "product": None, "error": "정기보고서 없음"}
    rep = reps[0]
    if prev and prev.get("rcept") == rep["rcept_no"] and "product" in prev and prev.get("v") == DART_VER:
        return dict(prev, at=_now())
    raw = dart._dart_get(dart.DART_API + "/document.xml?" + urllib.parse.urlencode(
        {"crtfc_key": key, "rcept_no": rep["rcept_no"]}), 40)
    z = zipfile.ZipFile(io.BytesIO(raw))
    main = [n for n in z.namelist() if re.fullmatch(r"\d+\.xml", n)] or z.namelist()
    x = z.read(main[0]).decode("utf-8", "replace")
    out = {"at": _now(), "v": DART_VER, "rcept": rep["rcept_no"], "report": rep["report_nm"].strip(), "reportDate": rep["rcept_dt"],
           "from": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + rep["rcept_no"], "product": None}
    pairs = _tables(_section(x, r"주요\s*제품"), spans=True)
    ts = [t for t, _sp in pairs]
    for i, (t, sp) in enumerate(pairs):
        if len(t) >= 2 and re.search(r"매출|비율|비중", " ".join(t[0])):
            out["product"] = {"rows": t[:TBL_ROWS], "unit": _unit_before(ts, i), "cut": len(t) > TBL_ROWS}
            if any(c != [1, 1] for r in sp[:TBL_ROWS] for c in r):
                out["product"]["spans"] = sp[:TBL_ROWS]
            break
    if not out["product"]:
        out["error"] = "「주요 제품」 절에 매출 표 없음"
    return out


# ---------------------------------------------------------------- 묶기

def profile(code, refresh=True):
    """{naver, dart} — 쥔 것이 낡았으면 그 자리에서 다시 받는다(refresh=False 면 쥔 것만)."""
    with _lock:
        rec = dict(_load().get(code) or {})
        lk = _busy.setdefault(code, threading.Lock())
    if not refresh:
        return rec
    with lk:
        with _lock:
            rec = dict(_load().get(code) or {})
        changed = False
        nv = rec.get("naver")
        if _age(nv) > (FAIL_TTL if (not nv or nv.get("error") and not nv.get("summary")) else PROFILE_TTL):
            try:
                rec["naver"] = fetch_naver(code)
            except Exception as e:
                rec["naver"] = {"at": _now(), "error": "네이버 못 받음: %s" % safe_message(e, 80)}
            changed = True
        dt = rec.get("dart")
        key = dart.get_key()
        stale = _age(dt) > (FAIL_TTL if (not dt or not dt.get("product")) else DART_TTL) or (dt or {}).get("v") != DART_VER
        if key and stale:
            try:
                rec["dart"] = fetch_dart(code, key, dt)
            except Exception as e:
                rec["dart"] = dict(dt or {}, at=_now(), error="DART 못 받음: %s" % safe_message(e, 80))
            changed = True
        if changed:
            with _lock:
                _load()[code] = rec
                _save()
    return rec


def public(code, rec):
    """화면에 내는 모양 — 받는 칸 이름(rcept 등)은 빼지 않고, 없으면 null."""
    nv = rec.get("naver") or {}
    dt = rec.get("dart") or {}
    return {
        "code": code,
        "sector": {"krx": nv.get("krx"), "wics": nv.get("wics")},
        "summary": nv.get("summary") or [],
        "summaryFrom": nv.get("from"), "summaryAt": nv.get("at"), "summaryError": nv.get("error"),
        "products": dt.get("product"),
        "productsReport": dt.get("report"), "productsDate": dt.get("reportDate"),
        "productsFrom": dt.get("from"), "productsError": dt.get("error") if not dt.get("product") else None,
    }
