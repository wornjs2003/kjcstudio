#!/usr/bin/env python3
"""세계 돈의 흐름 — 종목과 상관없는 시장 배경 한 벌을 받아 data/world-flow.json 에 둔다 (2026-10-08).

재권님 말씀 — 「각 나라별 주요지수들 최근 등락률을 확인하고 그안에서 많이 오른 섹터나 etf를 체크하면 지금 세계 어느나라에 돈이 몰리는지」
(00:51) · 「세계돈의 흐름은 종목이 아니고 전세계의 흐름」(15:2x) · 「전세계 채권가격 흐름도 넣어줘」(15:3x).

  나라      나라 ETF(달러로 같은 잣대) — 미국 SPY · 일본 EWJ · 중국 MCHI · 대만 EWT · 인도 INDA · 독일 EWG · 한국 EWY · 세계 ACWI
  업종      미국 섹터 SPDR 11 + 반도체 SOXX
  채권 값   채권 ETF — 미국 국채 단기 SHY · 중기 IEF · 장기 TLT · 미국 밖 선진국 BNDX · 신흥국 EMB · 우량 회사채 LQD · 하이일드 HYG
  금리      미국 2년 · 10년(FRED 매일) · 한국 국고채 3년 · 10년(ECOS 매일) · 독일 · 일본 10년(FRED 달마다 — OECD 장기금리)
  돈        코스피 외국인 순매수(시장 전체 · KIS)

ETF 일봉 · 코스피 투자자는 이 폴더 서버(--port, 기본 8771)의 KIS 경로로 받는다 — KIS 를 직접 부르지 않는다.
등락률은 거래일 기준 1주 = 5 · 1개월 = 21 · 3개월 = 63 봉 전 종가 대비. 받지 못한 것은 None 으로 두고 errors 에 이름만 적는다(주소에 키가 있어 문구를 안 남긴다).
"""
import csv, io, json, os, sys, urllib.request
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "..", "data", "world-flow.json")
SECRETS = os.path.join(ROOT, "holdings", "secrets.json")
PORT = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else "8771"
API = "http://localhost:%s/api" % PORT

COUNTRIES = [("ACWI", "세계"), ("SPY", "미국"), ("EWJ", "일본"), ("MCHI", "중국"), ("EWT", "대만"), ("INDA", "인도"), ("EWG", "독일"), ("EWY", "한국")]
SECTORS = [("XLK", "기술"), ("SOXX", "반도체"), ("XLC", "통신서비스"), ("XLY", "임의소비재"), ("XLP", "필수소비재"), ("XLE", "에너지"), ("XLF", "금융"),
           ("XLV", "헬스케어"), ("XLI", "산업재"), ("XLB", "소재"), ("XLRE", "부동산"), ("XLU", "유틸리티")]
BONDS = [("SHY", "미국 국채 단기(1~3년)"), ("IEF", "미국 국채 중기(7~10년)"), ("TLT", "미국 국채 장기(20년+)"), ("BNDX", "미국 밖 선진국 채권"),
         ("EMB", "신흥국 달러 채권"), ("LQD", "미국 우량 회사채"), ("HYG", "미국 하이일드 회사채")]
SPANS = {"w1": 5, "m1": 21, "m3": 63}


def get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def etf(code):
    j = json.loads(get("%s/kis/chart?code=%s&period=D" % (API, code)))
    c = [x for x in (j.get("data") or {}).get("candles") or [] if x.get("close")]
    if len(c) < 2:
        return None
    last = c[-1]
    out = {"code": code, "date": last["ts"], "close": last["close"]}
    for k, n in SPANS.items():
        out[k] = round((last["close"] / c[-1 - n]["close"] - 1) * 100, 2) if len(c) > n else None
    return out


def fred(series):
    rows = list(csv.reader(io.StringIO(get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + series).decode())))[1:]
    return [(r[0].replace("-", ""), float(r[1])) for r in rows if len(r) > 1 and r[1] not in ("", ".")]


def ecos(key, item):
    end = datetime.now(); start = end - timedelta(days=140)
    u = "https://ecos.bok.or.kr/api/StatisticSearch/%s/json/kr/1/200/817Y002/D/%s/%s/%s" % (key, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), item)
    rows = json.loads(get(u)).get("StatisticSearch", {}).get("row", [])
    return [(r["TIME"], float(r["DATA_VALUE"])) for r in rows]


def yld(name, series, daily, src):
    """금리 한 줄 — 최근 값과 1주 · 1개월 · 3개월 변화(bp). 달마다 오는 것은 1개월 · 3개월만"""
    if not series:
        return {"name": name, "src": src, "value": None}
    d, v = series[-1]
    o = {"name": name, "src": src, "date": d, "value": v, "daily": daily}
    steps = SPANS if daily else {"m1": 1, "m3": 3}
    for k, n in steps.items():
        o[k] = round((v - series[-1 - n][1]) * 100) if len(series) > n else None
    return o


def main():
    res = {"fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M"), "spans": "거래일 1주 = 5 · 1개월 = 21 · 3개월 = 63 봉 · 금리 변화는 bp(0.01%p)",
           "countries": [], "sectors": [], "bondEtfs": [], "yields": [], "kospiForeign": None, "errors": {}}
    for key, lst, names in (("countries", COUNTRIES, None), ("sectors", SECTORS, None), ("bondEtfs", BONDS, None)):
        for code, name in lst:
            try:
                r = etf(code)
                if r:
                    r["name"] = name; res[key].append(r)
                else:
                    res["errors"][code] = "일봉 없음"
            except Exception as ex:
                res["errors"][code] = type(ex).__name__
    try:
        key = json.load(open(SECRETS, encoding="utf-8"))["ecos"]["api_key"]
        res["yields"].append(yld("한국 국고채 3년", ecos(key, "010200000"), True, "ECOS 817Y002"))
        res["yields"].append(yld("한국 국고채 10년", ecos(key, "010210000"), True, "ECOS 817Y002"))
    except Exception as ex:
        res["errors"]["ecos"] = type(ex).__name__
    for name, sid, daily in (("미국 국채 2년", "DGS2", True), ("미국 국채 10년", "DGS10", True), ("독일 국채 10년", "IRLTLT01DEM156N", False), ("일본 국채 10년", "IRLTLT01JPM156N", False)):
        try:
            res["yields"].append(yld(name, fred(sid), daily, "FRED " + sid))
        except Exception as ex:
            res["errors"][sid] = type(ex).__name__
    try:
        j = json.loads(get("%s/kis/investor-flow?market=KOSPI" % API))
        rows = j.get("data") or []          # 과거 → 최근 · 금액 백만원
        amt = [r["foreign"]["amt"] for r in rows if r.get("foreign") and r["foreign"].get("amt") is not None]
        res["kospiForeign"] = {"date": rows[-1]["date"] if rows else None, "d5": sum(amt[-5:]) / 100 if amt else None, "d20": sum(amt[-20:]) / 100 if len(amt) >= 20 else None, "unit": "억원"}
    except Exception as ex:
        res["errors"]["investor-flow"] = type(ex).__name__
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("✓ 받음 — 나라 %d · 업종 %d · 채권 ETF %d · 금리 %d · 못 받음 %d" % (len(res["countries"]), len(res["sectors"]), len(res["bondEtfs"]), len(res["yields"]), len(res["errors"])))
    for k, v in res["errors"].items():
        print("  ✗", k, v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
