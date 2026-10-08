#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""업종 성장성 재료를 한국은행 ECOS 에서 받아 data/industry.json 에 둔다 — 종목 리포트 「산업 성장성」 칸이 쓴다.

    python3 company-setup/tools/fetch-industry.py [--quiet]

2026-10-08 재권님 「시황 · 사업 성장성 … 필요한 값들 서치해줘 · 증권사 투자회사 공인된 기관들에서」 → 안 「응 해줘」.
「산업이 크고 있나」 를 공인 통계 셋으로 본다(규칙은 종목 분석 문서 ⑥-11).

    매출액 증가율   한국은행 기업경영분석(분기)        502Y001 · 업종 · 종합 · 매출액증가율
    생산지수        통계청 광업제조업동향(ECOS 수록)   901Y032 · 업종 · 생산지수(원지수) — 1년 전 같은 달과 견준다
    업황 전망 BSI   한국은행 기업경기조사              512Y008 · 업황전망BSI · 업종 — 100 위면 좋아질 거라는 회사가 더 많다

종목 → 업종은 회사 카드(data/company-cards.json)의 DART 업종코드(한국표준산업분류) 앞 두 자리로 잇는다.
업종 코드 대응은 ECOS StatisticItemList 로 2026-10-08 확인한 것이다. ECOS 키는 holdings/secrets.json 의 ecos.api_key.
값을 지어내지 않는다 — 없는 업종(금융 등)은 그 칸이 null 이고 이유가 남는다.
"""
import json, os, sys, urllib.request
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CARDS = os.path.join(HERE, "..", "data", "company-cards.json")
OUT = os.path.join(HERE, "..", "data", "industry.json")
SECRETS = os.path.join(ROOT, "holdings", "secrets.json")
ECOS = "https://ecos.bok.or.kr/api"
QUIET = "--quiet" in sys.argv

# 한국표준산업분류 앞 두 자리 → ECOS 항목 코드
SALES = {}      # 502Y001 업종코드 (기업경영분석은 묶음으로 낸다)
for lo, hi, code, name in [(10, 12, "2010", "식음료담배"), (13, 15, "2020", "섬유의복가죽"), (16, 18, "2030", "목재종이인쇄"), (19, 22, "2040", "석유화학"),
                           (23, 23, "2050", "비금속광물"), (24, 25, "2060", "금속제품"), (26, 27, "2071", "전자영상통신장비"), (28, 29, "2072", "전기기타기계장비"),
                           (30, 31, "2080", "운송장비"), (32, 34, "2090", "가구및기타"), (35, 36, "4000", "전기가스업"), (41, 42, "5000", "건설업"),
                           (45, 47, "7000", "도매 및 소매업"), (49, 52, "8000", "운수업"), (55, 56, "9000", "숙박 및 음식점업"), (58, 63, "10000", "출판 · 방송통신 · 정보서비스"),
                           (70, 76, "11000", "전문 · 과학기술 · 사업지원"), (90, 91, "12000", "예술 · 스포츠 · 여가")]:
    for k in range(lo, hi + 1):
        SALES[k] = (code, name)
PROD = {10: "I11ACA", 11: "I11ACB", 12: "I11ACC", 13: "I11ACD", 14: "I11ACE", 15: "I11ACF", 16: "I11ACG", 17: "I11ACH", 18: "I11ACI", 19: "I11ACJ",
        20: "I11ACK", 21: "I11ACL", 22: "I11ACM", 23: "I11ACN", 24: "I11ACO", 25: "I11ACP", 26: "I11ACQ", 27: "I11ACR", 28: "I11ACS", 29: "I11ACT",
        30: "I11ACU", 31: "I11ACV", 32: "I11ACW", 33: "I11ACX", 35: "I11ADA"}
BSI = {k: "C%02d00" % k for k in range(10, 34) if k not in (12,)}
BSI.update({12: "C3300", 35: "D3500", 41: "F4100", 42: "F4100", 45: "G4500", 46: "G4500", 47: "G4500"})


def log(*a):
    if not QUIET:
        print(*a, flush=True)


def back(n, cycle):
    d = datetime.now()
    if cycle == "M":
        y, m = d.year, d.month - n
        while m <= 0:
            m += 12; y -= 1
        return "%04d%02d" % (y, m)
    q = (d.month - 1) // 3 + 1 - n
    y = d.year
    while q <= 0:
        q += 4; y -= 1
    return "%04dQ%d" % (y, q)


def search(key, table, cycle, n, *items):
    url = "%s/StatisticSearch/%s/json/kr/1/100/%s/%s/%s/%s/%s" % (ECOS, key, table, cycle, back(n, cycle), back(0, cycle), "/".join(items))
    j = json.loads(urllib.request.urlopen(url, timeout=30).read())
    rows = (j.get("StatisticSearch") or {}).get("row") or []
    return [(r["TIME"], float(r["DATA_VALUE"])) for r in rows if r.get("DATA_VALUE") not in (None, "")]


def main():
    try:
        key = json.load(open(SECRETS, encoding="utf-8"))["ecos"]["api_key"]
    except Exception:
        print("ECOS 키 없음(holdings/secrets.json 의 ecos.api_key)"); sys.exit(2)
    cards = json.load(open(CARDS, encoding="utf-8"))["cards"]
    ks = sorted({int(str(c["dart"]["industryCode"])[:2]) for c in cards.values() if c.get("code") and c.get("dart") and c["dart"].get("industryCode")})
    out = {}
    for k in ks:
        row = {"ksic2": k, "sales": None, "prod": None, "bsi": None, "errors": {}}
        try:
            if k in SALES:
                code, name = SALES[k]
                vs = search(key, "502Y001", "Q", 9, code, "A", "2000")
                row["sales"] = {"name": name, "series": vs[-8:], "from": "ECOS 502Y001 · %s · 종합 · 매출액증가율(%%)" % code} if vs else None
            else:
                row["errors"]["sales"] = "기업경영분석에 이 업종 묶음 없음(금융 · 보험 등)"
            if k in PROD:
                vs = search(key, "901Y032", "M", 25, PROD[k], "1")
                if vs:
                    last = vs[-1]; ago = next((v for t, v in vs if t == "%04d%s" % (int(last[0][:4]) - 1, last[0][4:])), None)
                    row["prod"] = {"at": last[0], "value": last[1], "yearAgo": ago, "yoy": (last[1] / ago - 1) * 100 if ago else None,
                                   "series": vs[-13:], "from": "ECOS 901Y032 · %s · 생산지수(원지수 · 2020=100)" % PROD[k]}
            else:
                row["errors"]["prod"] = "생산지수는 광업 · 제조업 · 전기가스만"
            if k in BSI:
                vs = search(key, "512Y008", "M", 6, "BA", BSI[k])
                row["bsi"] = {"series": vs, "from": "ECOS 512Y008 · 업황전망BSI · %s" % BSI[k]} if vs else None
            else:
                row["errors"]["bsi"] = "기업경기조사에 이 업종 없음"
        except Exception as ex:
            row["errors"]["ecos"] = type(ex).__name__        # 주소에 키가 들어 있어 문구를 안 남긴다
        out[str(k)] = row
        log("%02d  매출 %s · 생산 %s · BSI %s %s" % (k, "있음" if row["sales"] else "—", "있음" if row["prod"] else "—", "있음" if row["bsi"] else "—", row["errors"] or ""))
    doc = {"fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M"), "source": "한국은행 ECOS — 기업경영분석 · 광업제조업동향 · 기업경기조사", "byKsic2": out}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(doc, fp, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    log("저장: %s" % os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
