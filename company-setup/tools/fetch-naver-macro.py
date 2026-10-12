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
    r = subprocess.run(["curl", "-sfL", "-m", str(timeout), "-A", "Mozilla/5.0", BASE + path], capture_output=True)
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
    X["histSrc"] = "네이버 증권 시장지표 과거 값(…/marketindex/<갈래>/<코드>/prices) · %s 부터" % since
    X["errors"] = err
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(X, f, ensure_ascii=False, separators=(",", ":"))
    n_now = sum(len(X[c]) for c in CATS) + sum(len(v) for v in X["bond"].values()) + len(X["majors"])
    print("지금 값 %d개 · 1년 흐름 %d/%d개 · 못 받은 것 %s → %s" % (
        n_now, len(X["hist"]), len(HIST), ", ".join(err) or "없음", os.path.normpath(OUT)))
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
