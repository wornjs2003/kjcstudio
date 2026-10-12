#!/usr/bin/env python3
"""네이버 증권 시장지표 — 유가 · 금속 · 운임 · 농산물 · 국내 금리 · 나라별 기준금리 · 나라별 국채 곡선 · 원화 환율과
그중 몇 가지의 1년 흐름을 받아 data/naver-macro.json 에 둔다 (2026-10-12 · 재권님 「응 붙여줘」 · 받는 방식 (가)).
시황분석 탭(market.html)이 읽는다. 화면(브라우저)은 네이버를 직접 못 불러 이 도구가 받아 둔다 — 손으로 돌린다.

  지금 값   stock.naver.com/api/securityService/marketindex/<갈래>          갈래 = CATS
            …/marketindex/bond/nation/<나라>                               국채 곡선 = BOND_NATIONS
            …/marketindex/exchange/majors                                  원화 환율 · 달러지수
  1년 흐름  …/marketindex/<갈래>/<코드>/prices?page=N&pageSize=60           한 번에 60개가 상한이라 쪽을 넘긴다

**나중에 바뀔 자리** — 홀딩스에 시장지표 차트가 들어와 서버가 이 값을 내주게 되면 시황분석 탭은 거기서 받는다
(재권님 10-12 「홀딩스에 차트 넣으면 거기서 값을 가져오는 방향」). 그때 이 도구와 이 파일은 없앤다 — 둘을 함께 두지 않는다.

  국내 시장(2026-10-12 재권님 「응 해봐」 — 「그 밖의 재료」 룰 · 시황분석1 안 · 한국거래소 마감 시황의 공통 칸)
            m.stock.naver.com/api/index/<KOSPI|KOSDAQ>/integration   투자자별 순매수(억원) · 프로그램(억원) · 오른/내린 종목 수 · 시가총액 상위
            m.stock.naver.com/api/stocks/industry                     업종 등락(네이버 업종 분류)
  지수 1년  m.stock.naver.com/api/index/<KOSPI|KOSDAQ>/price · api.stock.naver.com/index/<.INX|.IXIC>/price — 크게 움직인 날을 화면이 고른다

받지 못한 갈래는 빈 목록으로 두고 errors 에 이름만 적는다. 키가 없는 곳이다.
"""
import json, os, subprocess, sys
from datetime import date, datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "naver-macro.json")
BASE = "https://stock.naver.com/api/securityService/marketindex/"

CATS = ["energy", "metals", "transport", "agricultural", "domesticInterest", "standardInterest"]
BOND_NATIONS = ["USA", "KOR", "JPN", "DEU", "GBR", "CHN", "BRA", "AUS"]
# 1년 흐름 — (이름, 갈래, 코드). 시안(temp/시황분석-네이버값-시안.html)이 그래프로 그린 것
HIST = [
    ("WTI", "energy", "CLcv1"), ("브렌트유", "energy", "LCOcv1"), ("두바이유", "energy", "DCBc1"),
    ("국제 금", "metals", "GCcv1"), ("은", "metals", "SIcv1"), ("구리(선물)", "metals", "HGcv1"),
    ("BDI 건화물선지수", "transport", ".BADI"), ("상하이컨테이너 운임지수", "transport", ".SCFIDXSSE"),
    ("중국컨테이너 운임지수", "transport", ".CCFIDXSSE"),
    ("콜금리 (1일)", "domesticInterest", "KRCALLBOKK"), ("CD금리 (91일)", "domesticInterest", "KFIA114000"),
    ("회사채 (3년, AA-)", "domesticInterest", "KFIA103009"), ("회사채 (3년, BBB-)", "domesticInterest", "KFIA103010"),
    ("한국 국채 3년", "bond", "KR3YT=RR"),
]


def get(path, timeout=20):
    url = path if path.startswith("http") else BASE + path
    r = subprocess.run(["curl", "-sfL", "-m", str(timeout), "-A", "Mozilla/5.0", url], capture_output=True)
    if r.returncode:
        raise RuntimeError("curl %d" % r.returncode)
    return json.loads(r.stdout.decode("utf-8", "replace"))


def num(s):
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return None


def item(x):
    """화면이 쓰는 칸만 — 값은 숫자로, 바뀐 비율이 없으면 None."""
    return {"name": x.get("name"), "code": x.get("reutersCode"), "v": num(x.get("closePrice")),
            "pct": num(x.get("fluctuationsRatio")), "at": x.get("localTradedAt"),
            "dir": (x.get("fluctuationsType") or {}).get("name")}


def history(cat, code, since):
    out = []
    for page in range(1, 10):
        rows = get("%s/%s/prices?page=%d&pageSize=60" % (cat, code.replace("=", "%3D"), page))
        if not rows:
            break
        for r in rows:
            d = (r.get("localTradedAt") or "")[:10]
            v = num(r.get("closePrice"))
            if d >= since and v is not None:
                out.append([d, v])
        if (rows[-1].get("localTradedAt") or "")[:10] < since:
            break
    return sorted(set(map(tuple, out)))


M_API = "https://m.stock.naver.com/api/"
IDX = [("KOSPI", "코스피", M_API + "index/KOSPI/price"), ("KOSDAQ", "코스닥", M_API + "index/KOSDAQ/price"),
       ("SPX", "S&P 500", "https://api.stock.naver.com/index/.INX/price"), ("IXIC", "나스닥", "https://api.stock.naver.com/index/.IXIC/price")]


def kr_market(code):
    d = get(M_API + "index/%s/integration" % code)
    t, p, u = d.get("dealTrendInfo") or {}, d.get("programTrendInfo") or {}, d.get("upDownStockInfo") or {}
    return {"date": t.get("bizdate"),
            "investor": {"개인": num(t.get("personalValue")), "외국인": num(t.get("foreignValue")), "기관": num(t.get("institutionalValue"))},
            "program": {"차익": num(p.get("indexDifferenceReal")), "비차익": num(p.get("indexBiDifferenceReal")), "합계": num(p.get("indexTotalReal"))},
            "updown": {"상한": num(u.get("upperCount")), "오름": num(u.get("riseCount")), "보합": num(u.get("steadyCount")),
                       "내림": num(u.get("fallCount")), "하한": num(u.get("lowerCount"))},
            "top": [{"name": x.get("stockName"), "code": x.get("itemCode"), "v": num(x.get("closePrice")), "pct": num(x.get("fluctuationsRatio"))}
                    for x in (d.get("enrollStocks") or [])[:10]]}


def index_year(url, since):
    out = []
    for page in range(1, 10):
        rows = get("%s?page=%d&pageSize=60" % (url, page))
        if not rows:
            break
        for r in rows:
            d = (r.get("localTradedAt") or "")[:10]
            v, c = num(r.get("closePrice")), num(r.get("fluctuationsRatio"))
            if d >= since and v is not None:
                out.append([d, v, c])
        if (rows[-1].get("localTradedAt") or "")[:10] < since:
            break
    return sorted({p[0]: p for p in out}.values())


def main():
    err = {}
    X = {"fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
         "src": "네이버 증권 시장지표(stock.naver.com/market/marketindex)"}
    for c in CATS:
        try:
            X[c] = [item(x) for x in get(c)]
        except Exception as ex:
            X[c], err[c] = [], type(ex).__name__
    X["bond"] = {}
    for n in BOND_NATIONS:
        try:
            X["bond"][n] = [item(x) for x in get("bond/nation/" + n)]
        except Exception as ex:
            X["bond"][n], err["bond/" + n] = [], type(ex).__name__
    try:
        X["majors"] = [item(x) for x in get("exchange/majors")]
    except Exception as ex:
        X["majors"], err["majors"] = [], type(ex).__name__
    since = (date.today() - timedelta(days=366)).isoformat()
    X["hist"] = {}
    for name, cat, code in HIST:
        try:
            X["hist"][name] = {"cat": cat, "code": code, "s": [list(p) for p in history(cat, code, since)]}
        except Exception as ex:
            err["hist/" + name] = type(ex).__name__
    X["kr"] = {}
    for code in ("KOSPI", "KOSDAQ"):
        try:
            X["kr"][code] = kr_market(code)
        except Exception as ex:
            err["kr/" + code] = type(ex).__name__
    try:
        X["industry"] = [{"name": g.get("name"), "pct": num(g.get("changeRate")), "n": g.get("totalCount"),
                          "up": g.get("riseCount"), "down": g.get("fallCount")} for g in get(M_API + "stocks/industry?page=1&pageSize=100").get("groups", [])]
    except Exception as ex:
        X["industry"], err["industry"] = [], type(ex).__name__
    X["idx"] = {}
    for key, name, url in IDX:
        try:
            X["idx"][key] = {"name": name, "s": index_year(url, since)}   # [날짜, 종가, 전날 대비 %]
        except Exception as ex:
            err["idx/" + key] = type(ex).__name__
    X["histSrc"] = "네이버 증권 시장지표 과거 값(…/marketindex/<갈래>/<코드>/prices) · %s 부터" % since
    X["errors"] = err
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(X, f, ensure_ascii=False, separators=(",", ":"))
    n_now = sum(len(X[c]) for c in CATS) + sum(len(v) for v in X["bond"].values()) + len(X["majors"])
    print("지금 값 %d개 · 1년 흐름 %d/%d개 · 국내 시장 %d · 업종 %d · 지수 1년 %d/%d · 못 받은 것 %s → %s" % (
        n_now, len(X["hist"]), len(HIST), len(X["kr"]), len(X["industry"]), len(X["idx"]), len(IDX), ", ".join(err) or "없음", os.path.normpath(OUT)))
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
