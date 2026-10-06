#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""지도(data/maps/*.json)의 종목마다 「회사 카드」 를 검증된 출처에서 받아 data/company-cards.json 에 둔다.

    python3 company-setup/tools/fetch-company-cards.py [--only 000660,NVDA] [--quiet]

2026-10-06 재권님 지시 — 「각 회사의 홈페이지나 분석된 증권사에서 자료를 가져오는 방식 · 임의로 쓰는 게 아니고
검증된 방법」 → 출처 셋 「우선 그렇게 해놓고 나중에 수정하자」.

    국내(6자리 코드)   사업     금감원 DART 정기보고서 「사업의 개요」 — 회사가 직접 쓴 글. 기업개황(홈페이지 · 업종 · 대표)
                      실적·추정 네이버 증권 API(FnGuide 집계) — 매출 · 영업이익 · 순이익 · EPS · PER · PBR, 마지막 열은 증권사 추정(E)
                      컨센서스 네이버 증권 API — 목표주가 평균 · 투자의견 평균 · 증권사 리포트 제목 목록
    해외(티커)        실적     미국 증권위 EDGAR companyfacts — 매출 · 영업이익 · 순이익(회계연도 셋)
                      사업     EDGAR 업종 설명(sicDescription) + 최신 10-K · 20-F 링크(본문은 영어 · 링크만)
                      컨센서스 없음(EDGAR 에 없다) — `null`

값을 지어내지 않는다. 못 받은 칸은 `null` 이고 `errors` 에 이유가 남는다. 받은 시각(`fetchedAt`)과 출처 주소(`from`)를
카드마다 적어 화면이 그대로 보여 준다(「숫자에는 뜻을 붙인다」 · 「됨 대신 넣은 값」).

DART 키는 holdings/secrets.json 의 dart.api_key, 회사 고유번호는 holdings/market.db 의 dart_corps(금감원 표 · 읽기만)에서 찾는다.
네이버 길은 공개 문서가 없는 내부 API 라 바뀔 수 있다 — 바뀌면 그 칸만 `null` 이 되고 나머지는 산다.
"""
import io, json, os, re, sqlite3, sys, time, zipfile, urllib.request, urllib.parse
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
MAPS = os.path.join(HERE, "..", "data", "maps")
OUT = os.path.join(HERE, "..", "data", "company-cards.json")
SECRETS = os.path.join(ROOT, "holdings", "secrets.json")
MARKET_DB = os.path.join(ROOT, "holdings", "market.db")

UA_WEB = "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/120 Safari/537.36 KJC-Insight/1.0"
UA_SEC = "KJC Studio contact@kjcstudio.kr"        # SEC 는 연락처가 든 UA 를 요구한다
DART = "https://opendart.fss.or.kr/api"
NAVER = "https://m.stock.naver.com/api/stock"
EDGAR = "https://data.sec.gov"
PAUSE = 0.35                                       # 요청 사이 쉬는 시간(초) — 한 번에 수십 건이라 예의상
BIZ_MAX = 1200                                     # 「사업의 개요」 발췌 글자 수
QUIET = "--quiet" in sys.argv


def log(*a):
    if not QUIET:
        print(*a, flush=True)


def get(url, ua=UA_WEB, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json,text/html,*/*"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def get_json(url, ua=UA_WEB):
    return json.loads(get(url, ua).decode("utf-8", "replace"))


def num(s):
    """'1,234' · '-77,303' · 'N/A' → 숫자 또는 None"""
    if s is None:
        return None
    t = str(s).replace(",", "").strip()
    if t in ("", "N/A", "-", "null"):
        return None
    try:
        return float(t) if "." in t else int(t)
    except ValueError:
        return None


# ── 지도에서 종목 모으기 ─────────────────────────────────────────────────
def load_stocks():
    out = {}
    for fn in sorted(os.listdir(MAPS)):
        if not fn.endswith(".json"):
            continue
        d = json.load(open(os.path.join(MAPS, fn), encoding="utf-8"))
        for s in d.get("stocks") or []:
            key = s.get("code") or s.get("ticker")
            if not key:
                continue
            c = out.setdefault(key, {"name": s["name"], "code": s.get("code"), "ticker": s.get("ticker"),
                                     "market": s.get("market") or ("KR" if s.get("code") else ""), "maps": []})
            c["maps"].append({"map": d.get("id") or fn[:-5], "node": s.get("node"), "grade": s.get("grade")})
    return out


# ── 국내 — DART ───────────────────────────────────────────────────────────
def dart_key():
    try:
        return json.load(open(SECRETS, encoding="utf-8"))["dart"]["api_key"]
    except Exception:
        return None


def corp_code(stock_code):
    try:
        db = sqlite3.connect("file:%s?mode=ro" % MARKET_DB, uri=True)
        r = db.execute("select corp_code from dart_corps where stock_code=?", (stock_code,)).fetchone()
        return r[0] if r else None
    except Exception:
        return None


def strip_tags(raw):
    t = re.sub(r"<[^>]+>", " ", raw)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", t)


def dart_business(key, cc):
    """최신 정기보고서(사업 → 반기 → 분기 순으로 아무거나 최신)의 「사업의 개요」 발췌 + 보고서 링크"""
    q = urllib.parse.urlencode({"crtfc_key": key, "corp_code": cc, "bgn_de": "20240101", "pblntf_ty": "A", "page_count": 20})
    lst = get_json(DART + "/list.json?" + q)
    reps = [x for x in lst.get("list") or [] if re.search(r"사업보고서|반기보고서|분기보고서", x.get("report_nm", ""))]
    if not reps:
        return None, "정기보고서 없음"
    rep = reps[0]
    time.sleep(PAUSE)
    z = zipfile.ZipFile(io.BytesIO(get(DART + "/document.xml?" + urllib.parse.urlencode({"crtfc_key": key, "rcept_no": rep["rcept_no"]}))))
    main = [n for n in z.namelist() if re.fullmatch(r"\d+\.xml", n)] or z.namelist()
    txt = strip_tags(z.read(main[0]).decode("utf-8", "replace"))
    hits = [m.start() for m in re.finditer("사업의 개요", txt)]
    if not hits:
        return None, "「사업의 개요」 못 찾음"
    start = hits[1] if len(hits) > 1 else hits[0]          # 첫 번째는 목차인 경우가 많다
    body = txt[start + len("사업의 개요"):]
    end = re.search(r"2\. 주요 제품|2\. 주요제품|나\. |II\. |2\. 주요 서비스", body)
    body = body[: end.start()] if end and end.start() > 200 else body
    body = body.strip()
    if len(body) > BIZ_MAX:
        body = body[:BIZ_MAX].rsplit(" ", 1)[0] + "…"
    return {"text": body, "report": rep["report_nm"], "reportDate": rep["rcept_dt"],
            "from": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + rep["rcept_no"]}, None


def fetch_dart(card, key):
    cc = corp_code(card["code"])
    if not key:
        return None, "DART 키 없음(holdings/secrets.json)"
    if not cc:
        return None, "금감원 표(dart_corps)에 코드 없음"
    q = urllib.parse.urlencode({"crtfc_key": key, "corp_code": cc})
    j = get_json(DART + "/company.json?" + q)
    if j.get("status") != "000":
        return None, "기업개황 %s %s" % (j.get("status"), j.get("message"))
    time.sleep(PAUSE)
    biz, err = dart_business(key, cc)
    return {"corpName": j.get("corp_name"), "ceo": j.get("ceo_nm"), "homepage": j.get("hm_url"),
            "industryCode": j.get("induty_code"), "established": j.get("est_dt"), "address": j.get("adres"),
            "business": biz, "from": "https://dart.fss.or.kr/dsae001/main.do?corpCode=" + cc,
            "source": "금감원 DART"}, err


# ── 국내 — 네이버 증권(FnGuide 집계) ─────────────────────────────────────
WANT_ROWS = ["매출액", "영업이익", "당기순이익", "영업이익률", "ROE", "부채비율", "EPS", "PER", "BPS", "PBR", "주당배당금"]
WANT_TOTAL = ["시가총액", "PER", "PBR", "외국인소진율", "배당수익률", "52주최고", "52주최저", "상장주식수"]


def fetch_naver(card):
    code = card["code"]
    integ = get_json("%s/%s/integration" % (NAVER, code))
    time.sleep(PAUSE)
    fin = get_json("%s/%s/finance/annual" % (NAVER, code))
    cons = integ.get("consensusInfo") or {}
    cols = [(t["key"], t["title"].rstrip("."), t.get("isConsensus") == "Y") for t in (fin.get("financeInfo") or {}).get("trTitleList") or []]
    rows = {}
    for r in (fin.get("financeInfo") or {}).get("rowList") or []:
        if r.get("title") in WANT_ROWS:
            rows[r["title"]] = {k: num((r.get("columns") or {}).get(k, {}).get("value")) for k, _, _ in cols}
    totals = {t["key"]: t.get("value") for t in integ.get("totalInfos") or [] if t.get("key") in WANT_TOTAL}
    reports = [{"broker": x.get("bnm"), "title": x.get("tit"), "date": x.get("wdt"),
                "from": "https://m.stock.naver.com/domestic/stock/%s/research/%s" % (code, x.get("id"))}
               for x in (integ.get("researches") or [])[:5]]
    return {"columns": [{"key": k, "label": t, "estimate": e} for k, t, e in cols], "unit": "억원 · EPS·BPS·배당은 원",
            "rows": rows, "totals": totals,
            "consensus": {"targetPriceMean": num(cons.get("priceTargetMean")), "recommMean": num(cons.get("recommMean")),
                          "asOf": cons.get("createDate"), "scale": "투자의견 1(매도)~5(매수)"},
            "reports": reports, "from": "https://m.stock.naver.com/domestic/stock/%s/total" % code,
            "source": "네이버 증권(FnGuide 집계)"}, None


# ── 해외 — SEC EDGAR ──────────────────────────────────────────────────────
_tickers = None


def cik_of(ticker):
    global _tickers
    if _tickers is None:
        d = get_json("https://www.sec.gov/files/company_tickers.json", UA_SEC)
        _tickers = {v["ticker"].upper(): (int(v["cik_str"]), v["title"]) for v in d.values()}
    return _tickers.get(ticker.upper())


GAAP_TAGS = {"revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
             "operatingIncome": ["OperatingIncomeLoss"],
             "netIncome": ["NetIncomeLoss", "ProfitLoss"]}
IFRS_TAGS = {"revenue": ["Revenue", "RevenueFromContractsWithCustomers"], "operatingIncome": ["ProfitLossFromOperatingActivities"], "netIncome": ["ProfitLoss"]}


def pick_fy(facts, tags, forms=("10-K", "20-F", "10-K/A", "20-F/A")):
    """회계연도 값을 **기간이 끝나는 날**로 하나씩 — 셋. `fy` 칸은 「낸 해」 라 쓰지 않는다
    (엔비디아는 1월 결산이라 fy 로 고르면 한 해 어긋난다 · 2026-10-06 실측). 분기 값은 기간이 1년이 아니라 뺀다.
    **여러 태그를 한데 모은다** — 회사가 해마다 태그를 바꾼다(마이크로소프트는 Revenues 가 2010 까지만이고 그 뒤는
    RevenueFromContractWithCustomer… · 실측). 같은 끝나는 날이 여럿이면 가장 늦게 낸 것."""
    from datetime import date
    by, unit_of = {}, {}
    for tag in tags:
        node = facts.get(tag)
        if not node:
            continue
        for unit, arr in (node.get("units") or {}).items():
            for v in arr:
                if v.get("form") not in forms or not v.get("start") or not v.get("end"):
                    continue
                try:
                    days = (date.fromisoformat(v["end"]) - date.fromisoformat(v["start"])).days
                except ValueError:
                    continue
                if not 340 <= days <= 380:
                    continue
                k = v["end"]
                if k not in by or v.get("filed", "") > by[k].get("filed", ""):
                    by[k] = v; unit_of[k] = (unit, tag)
    if not by:
        return None
    ends = sorted(by)[-3:]
    unit, tag = unit_of[ends[-1]]
    return {"unit": unit, "tag": tag, "values": {e: by[e]["val"] for e in ends}}


def fetch_edgar(card):
    hit = cik_of(card["ticker"])
    if not hit:
        return None, "SEC 티커 표에 없음"
    cik, title = hit
    sub = get_json("%s/submissions/CIK%010d.json" % (EDGAR, cik), UA_SEC)
    time.sleep(PAUSE)
    cf = get_json("%s/api/xbrl/companyfacts/CIK%010d.json" % (EDGAR, cik), UA_SEC)
    f = sub.get("filings", {}).get("recent", {})
    report = None
    for i, form in enumerate(f.get("form") or []):
        if form in ("10-K", "20-F"):
            acc = f["accessionNumber"][i].replace("-", "")
            report = {"form": form, "date": f["filingDate"][i],
                      "from": "https://www.sec.gov/Archives/edgar/data/%d/%s/%s" % (cik, acc, f["primaryDocument"][i])}
            break
    facts = cf.get("facts") or {}
    gaap, ifrs = facts.get("us-gaap") or {}, facts.get("ifrs-full") or {}
    fin = {}
    for k in GAAP_TAGS:
        fin[k] = pick_fy(gaap, GAAP_TAGS[k]) or pick_fy(ifrs, IFRS_TAGS[k])
    return {"entityName": cf.get("entityName") or title, "sic": sub.get("sicDescription"), "fiscalYearEnd": sub.get("fiscalYearEnd"),
            "homepage": sub.get("website") or None, "report": report, "financials": fin,
            "from": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=%d" % cik, "source": "미국 증권위 EDGAR"}, None


# ── 조립 ──────────────────────────────────────────────────────────────────
def main():
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    stocks = load_stocks()
    key = dart_key()
    prev = {}
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT, encoding="utf-8")).get("cards") or {}
        except Exception:
            prev = {}
    cards, n_ok, n_err = dict(prev), 0, 0
    for k, c in stocks.items():
        if only and k not in only:
            continue
        card = {"name": c["name"], "code": c["code"], "ticker": c["ticker"], "market": c["market"], "maps": c["maps"],
                "dart": None, "naver": None, "edgar": None, "errors": {}, "fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M")}
        try:
            if c["code"]:
                try:
                    card["dart"], e = fetch_dart(card, key)
                    if e:
                        card["errors"]["dart"] = e
                except Exception as ex:
                    card["errors"]["dart"] = "%s: %s" % (type(ex).__name__, str(ex)[:120])
                time.sleep(PAUSE)
                try:
                    card["naver"], e = fetch_naver(card)
                except Exception as ex:
                    card["errors"]["naver"] = "%s: %s" % (type(ex).__name__, str(ex)[:120])
            elif c["ticker"]:
                try:
                    card["edgar"], e = fetch_edgar(card)
                    if e:
                        card["errors"]["edgar"] = e
                except Exception as ex:
                    card["errors"]["edgar"] = "%s: %s" % (type(ex).__name__, str(ex)[:120])
        finally:
            time.sleep(PAUSE)
        cards[k] = card
        if card["errors"]:
            n_err += 1
        else:
            n_ok += 1
        log("%-8s %-12s %s" % (k, c["name"], ("· ".join("%s=%s" % kv for kv in card["errors"].items()) or "받음")))
    out = {"fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "sources": {"dart": "금감원 DART 전자공시 — 기업개황 · 정기보고서 「사업의 개요」",
                       "naver": "네이버 증권(FnGuide 집계) — 연간 실적 · 증권사 추정(E) · 목표주가 · 투자의견 · 리포트",
                       "edgar": "미국 증권위 EDGAR — companyfacts 재무 · 10-K/20-F"},
           "cards": cards}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    log("저장: %s — 카드 %d장 (이번에 받음 %d · 오류 있음 %d)" % (os.path.relpath(OUT, ROOT), len(cards), n_ok, n_err))


if __name__ == "__main__":
    main()
