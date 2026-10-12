#!/usr/bin/env python3
"""미국 지표 발표 날 다음 날 코스피가 오른 확률 — 경기 국면으로 갈라 센다 (2026-10-12 재권님 「확률로 알고싶은데」 →
시황분석1 조사 → 「응」 · FRED 열쇠 등록). data/release-odds.json 에 두고 시황분석 탭(market.html)이 읽는다. 손으로 돌린다.

  발표 날   FRED API release/dates — 물가(CPI) · 고용 · 생산자물가(PPI) · 소매판매 · GDP · 개인소득·소비(PCE). 열쇠 holdings/secrets.json fred
            FOMC(연준 회의)는 FRED 의 그 갈래가 회의 날만이 아니라 날마다 찍혀 있어 뺐다(2026-10-12 실측 3,809날)
  코스피    한국은행 ECOS 802Y001(코스피 일별 · 1995~) — 미국 발표는 한국 밤이라 **그 날짜 다음 한국 거래일** 이 반응하는 날
  국면      OECD 경기선행지수 미국(FRED USALOLITOAASTSAM · 달마다). 발표 달의 **두 달 전** 값이 그 전달보다 높으면 「오르는 중」 —
            발표가 늦게 나와 그 달에 실제로 알 수 있던 값만 쓴다(미리 본 값 안 쓰기)
  견줄 값   발표가 없던 날까지 모든 날의 「오른 확률」 — 발표 날이 그보다 높아야 뜻이 있다

받는 쪽이 셋이라 하나라도 못 받으면 파일을 안 바꾸고 종료 1. 예상치(서프라이즈)는 과거를 받을 곳이 없어 안 쓴다 — Andersen 외(2007)는
「예상과 다른 몫」 에 반응한다고 했으므로 이 셈은 그보다 흐린 셈이다(화면에 적는다).
"""
import json, os, subprocess, sys, urllib.parse
from datetime import date, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "..", "data", "release-odds.json")
SECRETS = os.path.join(ROOT, "holdings", "secrets.json")
SINCE = "1995-01-01"
RELEASES = [(10, "CPI", "소비자물가(CPI)"), (50, "JOBS", "고용"), (46, "PPI", "생산자물가(PPI)"),
            (9, "RETAIL", "소매판매"), (53, "GDP", "GDP"), (54, "PCE", "개인소득 · 소비(PCE)")]


def curl(url, timeout=60):
    r = subprocess.run(["curl", "-sfL", "-m", str(timeout), url], capture_output=True)
    if r.returncode:
        raise RuntimeError("curl %d" % r.returncode)
    return json.loads(r.stdout.decode("utf-8", "replace"))


def main():
    sec = json.load(open(SECRETS, encoding="utf-8"))
    fk, ek = sec["fred"]["api_key"], sec["ecos"]["api_key"]
    fred = lambda path, **q: curl("https://api.stlouisfed.org/fred/%s?%s" % (path, urllib.parse.urlencode(dict(q, api_key=fk, file_type="json"))))
    try:
        dates = {}
        for rid, key, _ in RELEASES:
            d = fred("release/dates", release_id=rid, realtime_start=SINCE, include_release_dates_with_no_data="true", limit=10000, sort_order="asc")
            dates[key] = sorted({x["date"] for x in d["release_dates"]})
        cli = [(o["date"][:7], float(o["value"])) for o in fred("series/observations", series_id="USALOLITOAASTSAM", observation_start="1993-01-01")["observations"] if o["value"] != "."]
        today = date.today().strftime("%Y%m%d")
        rows = curl("https://ecos.bok.or.kr/api/StatisticSearch/%s/json/kr/1/100000/802Y001/D/19950101/%s/0001000" % (ek, today))["StatisticSearch"]["row"]
    except Exception as ex:   # 주소에 열쇠가 있어 문구를 안 남긴다
        print("못 받음:", type(ex).__name__)
        return 1
    k = sorted(("%s-%s-%s" % (r["TIME"][:4], r["TIME"][4:6], r["TIME"][6:]), float(r["DATA_VALUE"])) for r in rows)
    ret = {k[i][0]: k[i][1] / k[i - 1][1] - 1 for i in range(1, len(k))}   # 그날 코스피 등락
    kd = [d for d, _ in k[1:]]
    cm = dict(cli)

    def phase(d):   # 발표 달의 두 달 전 값 vs 세 달 전 값
        y, m = int(d[:4]), int(d[5:7])
        a = "%04d-%02d" % ((y * 12 + m - 3) // 12, (y * 12 + m - 3) % 12 + 1)
        b = "%04d-%02d" % ((y * 12 + m - 4) // 12, (y * 12 + m - 4) % 12 + 1)
        return None if a not in cm or b not in cm else ("up" if cm[a] > cm[b] else "down")

    def nxt(d):   # 그 날짜 다음 한국 거래일
        import bisect
        i = bisect.bisect_right(kd, d)
        return kd[i] if i < len(kd) else None

    def stat(rs):
        n = len(rs)
        return None if not n else {"n": n, "up": round(sum(r > 0 for r in rs) / n * 100, 1), "avg": round(sum(rs) / n * 100, 3)}

    base = {"all": stat(list(ret.values()))}
    for ph in ("up", "down"):
        base[ph] = stat([r for d, r in ret.items() if phase(d) == ph])
    out = []
    last = kd[-1]
    for rid, key, name in RELEASES:
        hit = [(d, nxt(d)) for d in dates[key] if d <= last]
        hit = [(d, n) for d, n in hit if n]
        row = {"key": key, "name": name, "all": stat([ret[n] for _, n in hit])}
        for ph in ("up", "down"):
            row[ph] = stat([ret[n] for d, n in hit if phase(d) == ph])
        row["next"] = next((d for d in dates[key] if d > last), None)
        out.append(row)
    X = {"fetchedAt": date.today().isoformat(), "kospiFrom": kd[0], "kospiTo": last,
         "cliLast": cli[-1][0], "phaseNow": phase(date.today().isoformat()),
         "base": base, "releases": out,
         "src": "발표 날 FRED release/dates · 코스피 한국은행 ECOS 802Y001 · 국면 OECD 경기선행지수 미국(FRED USALOLITOAASTSAM · 두 달 전 값의 방향)"}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(X, f, ensure_ascii=False, indent=1)
    print("코스피 %s~%s %d날 · 모든 날 오른 확률 %.1f%%" % (kd[0], last, len(kd), base["all"]["up"]))
    for r in out:
        a, u, d = r["all"], r["up"], r["down"]
        print("  %-14s %4d번 오름 %5.1f%% · 경기선행↑ %s · ↓ %s · 다음 %s" % (r["name"], a["n"], a["up"],
              "%.1f%%(%d)" % (u["up"], u["n"]) if u else "—", "%.1f%%(%d)" % (d["up"], d["n"]) if d else "—", r["next"]))
    print("  지금 국면", X["phaseNow"], "→", os.path.normpath(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
