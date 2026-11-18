"""레버리지 지표 — 빚을 내 산 돈이 얼마나 쌓였나 · /api/market/leverage (2026-11-17)

재권님 11-17 「홀딩스 화면에서 보고싶은데. 실시간이면 더 좋고」 · 「세마녀의날 옆에 있으면 좋을거같아」(시황분석 창) →
시안에 「가로 해줘」 · 「가에 신용융자 누르면 모달 띄워지게 버튼처럼」 · 「모달로 띄워지면 변동이 그래프로 보여지게」 · 11-18 자리는 위 지수 띠 끝(「나」 — 장 상태 줄이 꺾여서).

넷을 받는다 — 실시간 자료는 없다(한국 매일 · 하루 늦게 / 미국 달 · 분기). 그래서 값마다 기준 날짜를 함께 낸다.
    kr      한국 신용융자 · 예탁증권담보융자 — 금융투자협회 통계(freesis) · 날마다 · 백만 원 · 비공식 길(공개 화면이 부르는 주소)
            칸 — TMPV2 신용융자 전체 · 3 코스피 · 4 코스닥 · 9 예탁증권담보융자(칸 뜻은 기사 값과 맞춰 본 것 · 시황분석 11-17)
    finra   미국 개인 빚투 — FINRA 「Margin Statistics」 엑셀 · 달마다 · 고객 증거금 계좌 빚(Debit Balances) · 백만 달러
    hfLev   미국 헤지펀드 레버리지 — 미 재무부 금융조사국(OFR) Form PF · 분기 · 주식 전략 총자산 가중 평균(배)
    hfGross · hfNet  헤지펀드 주식 총 · 넷 노출 — OFR (매수 + 공매도) ÷ 순자산 · (매수 − 공매도) ÷ 순자산(근사 · %)

셈은 이 파일 한 곳 · 화면은 받은 대로 그린다. 바깥은 CACHE_SEC 에 한 번만 부르고, 못 받으면 앞 값을 그대로 두고 「못 받음」 을 함께 낸다
(「못 쟀으면 0 이 아니라 「못 쟀다」 고 낸다」). 서버마다(8765 · 8764 · 세션 · 8767) 바깥을 따로 받는다 — 8765 로 넘기는 길(KJC_KIS_UPSTREAM)은 KIS 만이고,
여섯 시간에 한 번이라 부담이 작아 넘기지 않았다(qa 11-18 실측 — 8767 이 바로 받음).
"""
import json
import re
import threading
import time
import urllib.request
import zipfile
import io
from datetime import datetime, timedelta, timezone

from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))
CACHE_SEC = 6 * 3600          # 자료가 하루 · 달 · 분기라 여섯 시간에 한 번이면 넉넉하다
KR_YEARS = 3                  # 한국 신용융자를 거슬러 받는 햇수(그래프 길이)
TIMEOUT = 20
UA = "Mozilla/5.0 (KJC Holdings)"

KOFIA_URL = "https://freesis.kofia.or.kr/meta/getMetaDataList.do"
KOFIA_OBJ = "STATSCU0100000070BO"
FINRA_URL = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"
OFR_URL = "https://data.financialresearch.gov/hf/v1/series/timeseries?mnemonic="
OFR_LEV = "FPF-STRATEGY_EQUITY_LEVERAGERATIO_GAVWMEAN"
OFR_LONG = "FPF-ASSETCLASS_EQUITIES_LGNE_SUM"
OFR_SHORT = "FPF-ASSETCLASS_EQUITIES_SGNE_SUM"
OFR_NAV = "FPF-ALLQHF_NAV_SUM"

SOURCES = {
    "kr": "금융투자협회 통계(freesis) · 날마다 · 하루 늦게 나옴",
    "finra": "FINRA Margin Statistics · 달마다",
    "hf": "미 재무부 금융조사국(OFR) Form PF · 분기",
}

_lock = threading.Lock()
_cache = {}                   # 이름 → {"at": 받은 시각(초), "data": …, "err": 못 받은 까닭}


def _get(url, body=None):
    hdr = {"User-Agent": UA}
    if body is not None:
        hdr["Content-Type"] = "application/json"
        body = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=hdr)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def _kr():
    """[{d: YYYY-MM-DD, total, kospi, kosdaq, deposit}] 옛것부터 · 백만 원."""
    end = datetime.now(KST)
    start = end - timedelta(days=365 * KR_YEARS)
    body = {"dmSearch": {"tmpV40": "1000000", "tmpV41": "1", "tmpV1": "D",
                         "tmpV45": start.strftime("%Y%m%d"), "tmpV46": end.strftime("%Y%m%d"), "OBJ_NM": KOFIA_OBJ}}
    for n in range(3):                # 응답이 중간에 끊겨 오는 때가 있다(11-17 8766 실측 · JSON 32KB 에서 끊김) — 세 번까지 다시
        try:
            rows = json.loads(_get(KOFIA_URL, body).decode("utf-8")).get("ds1") or []
            break
        except ValueError:
            if n == 2:
                raise
            time.sleep(1)
    out = []
    for r in rows:
        d = str(r.get("TMPV1") or "")
        if len(d) != 8 or not r.get("TMPV2"):
            continue
        out.append({"d": f"{d[:4]}-{d[4:6]}-{d[6:]}", "total": r.get("TMPV2"), "kospi": r.get("TMPV3"),
                    "kosdaq": r.get("TMPV4"), "deposit": r.get("TMPV9")})
    out.sort(key=lambda x: x["d"])
    if not out:
        raise ValueError("빈 응답")
    return out


def _finra():
    """[{d: YYYY-MM, v: 고객 증거금 계좌 빚(백만 달러)}] 옛것부터 — 엑셀을 zip 으로 열어 첫 시트 A · B 칸만 읽는다."""
    z = zipfile.ZipFile(io.BytesIO(_get(FINRA_URL)))
    ss = [re.sub(r"<[^>]+>", "", x) for x in re.findall(r"<si>.*?</si>", z.read("xl/sharedStrings.xml").decode("utf-8"), re.S)]
    sheet = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    out = []
    for row in re.findall(r"<row[^>]*>(.*?)</row>", sheet, re.S):
        cells = {}
        for col, attrs, val in re.findall(r'<c r="([A-Z]+)\d+"([^>]*)>(?:<v>([^<]*)</v>)?', row):
            if val == "":
                continue
            cells[col] = ss[int(val)] if 't="s"' in attrs else val
        ym, v = cells.get("A", ""), cells.get("B")
        if re.fullmatch(r"\d{4}-\d{2}", ym or "") and v:
            try:
                out.append({"d": ym, "v": float(v)})
            except ValueError:
                pass
    out.sort(key=lambda x: x["d"])
    if not out:
        raise ValueError("엑셀에서 줄을 못 찾음")
    return out


def _ofr(mn):
    return {d: v for d, v in json.loads(_get(OFR_URL + mn).decode("utf-8")) if v is not None}


def _hf():
    lev = _ofr(OFR_LEV)
    lo, sh, nav = _ofr(OFR_LONG), _ofr(OFR_SHORT), _ofr(OFR_NAV)
    gross, net = [], []
    for d in sorted(set(lo) & set(sh) & set(nav)):
        if nav[d]:
            gross.append({"d": d, "v": round((lo[d] + sh[d]) / nav[d] * 100, 1)})
            net.append({"d": d, "v": round((lo[d] - sh[d]) / nav[d] * 100, 1)})
    if not lev:
        raise ValueError("레버리지 줄이 비었음")
    return {"lev": [{"d": d, "v": v} for d, v in sorted(lev.items())], "gross": gross, "net": net}


_FETCH = {"kr": _kr, "finra": _finra, "hf": _hf}


def _one(name):
    c = _cache.get(name)
    if c and time.time() - c["at"] < CACHE_SEC:
        return c
    try:
        c = {"at": time.time(), "data": _FETCH[name](), "err": None}
    except Exception as e:                      # 못 받으면 앞 값을 두고 까닭만 붙인다 · 다음 차례는 짧게(10분 뒤)
        prev = c or {}
        c = {"at": time.time() - CACHE_SEC + 600, "data": prev.get("data"), "err": safe_message(e, 120)}
        print(f"[레버리지] {name} 못 받음 — {c['err']}", flush=True)
    _cache[name] = c
    return c


def payload():
    with _lock:
        got = {n: _one(n) for n in _FETCH}
    kr, fi, hf = (got[n]["data"] for n in ("kr", "finra", "hf"))
    hf = hf or {}
    data = {
        "kr": kr, "finra": fi, "hfLev": hf.get("lev"), "hfGross": hf.get("gross"), "hfNet": hf.get("net"),
        "sources": SOURCES,
        "fail": {n: got[n]["err"] for n in got if got[n]["err"]},
        "fetchedAt": {n: datetime.fromtimestamp(got[n]["at"], KST).strftime("%Y-%m-%d %H:%M") for n in got if got[n]["data"]},
    }
    return {"ok": bool(kr or fi or hf), "data": data, "meta": {"cacheSec": CACHE_SEC}}
