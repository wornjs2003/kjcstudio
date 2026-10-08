#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""미국 SPDR ETF 의 자금 유출입을 운용사(State Street) 공식 자료로 셈해 data/us-etf-flow.json 에 둔다.

    python3 company-setup/tools/fetch-us-etf-flow.py [--quiet]

2026-10-08 재권님 「해외 ETF · 세계 펀드 자금 흐름 … 받을 수 있는 곳 있는지 확인해봐」 → 「응 해줘 · 해외에서 더 받을수 있는곳은
기입해놔 나중에 연결하게」. 「세계 돈의 흐름」 ② 돈의 「해외 ETF」 칸을 채운다.

    받는 곳   State Street Investment Management(SPDR 운용사) 의 ETF 별 「NAV History」 엑셀 — 날짜 · 기준가(NAV) ·
              발행 주식 수(Shares Outstanding) · 순자산. 키 없이 받힌다(2026-10-08 실측 200)
    셈        그날 유출입 = (오늘 주식 수 − 어제 주식 수) × 오늘 기준가. 주식 수는 설정 · 환매(돈이 실제로 들어오고 나감)
              로만 바뀌어서 값이 오른 것과 가른다 — 국내 ETF 의 fetch-etf-nav.py 와 같은 방법
    묶음      1일 · 5거래일(주간) · 20거래일(월간) 합

ETF 목록은 아래 ETFS 한 곳. 값을 지어내지 않는다 — 못 받은 ETF 는 error 에 이유가 남는다.
"""
import io, json, os, re, sys, time, urllib.request, zipfile
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "..", "data", "us-etf-flow.json")
URL = "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-%s.xlsx"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/126 Safari/537.36 KJC-Insight/1.0"
QUIET = "--quiet" in sys.argv
ETFS = [("SPY", "S&P 500"), ("XLK", "기술"), ("XLF", "금융"), ("XLV", "헬스케어"), ("XLY", "임의소비재"), ("XLP", "필수소비재"),
        ("XLE", "에너지"), ("XLI", "산업재"), ("XLB", "소재"), ("XLU", "유틸리티"), ("XLRE", "부동산"), ("XLC", "커뮤니케이션")]


def log(*a):
    if not QUIET:
        print(*a, flush=True)


def col(ref):
    return re.match(r"[A-Z]+", ref).group(0)


def read_xlsx(raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    ss = [re.sub(r"<[^>]+>", "", m) for m in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode("utf-8"), re.S)]
    rows = []
    for r in re.findall(r"<row[^>]*>(.*?)</row>", z.read("xl/worksheets/sheet1.xml").decode("utf-8"), re.S):
        cells = {}
        for ref, attrs, body in re.findall(r'<c r="([A-Z]+\d+)"([^>]*)>(.*?)</c>', r, re.S):
            v = re.search(r"<v>(.*?)</v>", body)
            if not v:
                continue
            cells[col(ref)] = ss[int(v.group(1))] if 't="s"' in attrs else v.group(1)
        rows.append(cells)
    return rows


def series(rows):
    """「Date | NAV | Shares Outstanding | Total Net Assets」 머리 아래 줄들 → [(YYYY-MM-DD, nav, shares)] 오래된 것부터"""
    out, on = [], False
    for c in rows:
        if c.get("A", "").strip() == "Date":
            on = True; continue
        if not on:
            continue
        try:
            d = datetime.strptime(c.get("A", "").strip(), "%d-%b-%Y").strftime("%Y-%m-%d")
            out.append((d, float(c["B"]), float(c["C"])))
        except (ValueError, KeyError):
            continue
    return sorted(out)


def main():
    res = []
    for t, name in ETFS:
        row = {"ticker": t, "name": name, "error": None}
        try:
            req = urllib.request.Request(URL % t.lower(), headers={"User-Agent": UA})
            s = series(read_xlsx(urllib.request.urlopen(req, timeout=40).read()))
            if len(s) < 21:
                row["error"] = "줄이 %d 개뿐" % len(s)
            else:
                flows = [(s[i][0], (s[i][2] - s[i - 1][2]) * s[i][1]) for i in range(1, len(s))]
                f = lambda n: round(sum(v for _, v in flows[-n:]))
                row.update({"asOf": s[-1][0], "nav": s[-1][1], "shares": s[-1][2], "aum": round(s[-1][1] * s[-1][2]),
                            "flow1d": f(1), "flow5d": f(5), "flow20d": f(20),
                            "recent": [{"date": d, "flow": round(v)} for d, v in flows[-20:]]})
        except Exception as ex:
            row["error"] = "%s: %s" % (type(ex).__name__, str(ex)[:80])
        res.append(row)
        log("%-5s %-8s %s" % (t, name, row["error"] or "%s · 5일 %+.2f억달러 · 20일 %+.2f억달러" % (row["asOf"], row["flow5d"] / 1e8, row["flow20d"] / 1e8)))
        time.sleep(0.4)
    doc = {"fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M"), "unit": "USD",
           "source": "State Street Investment Management — SPDR ETF NAV History(기준가 · 발행 주식 수)",
           "method": "유출입 = 주식 수 변화 × 그날 기준가 · 5일 = 주간 · 20일 = 월간", "etfs": res}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(doc, fp, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    log("저장: %s" % os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
