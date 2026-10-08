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
    raw = z.read(main[0]).decode("utf-8", "replace")
    tables, terr = biz_tables(raw)
    txt = strip_tags(raw)
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
    return {"text": body, "report": rep["report_nm"], "reportDate": rep["rcept_dt"], "tables": tables, "tablesError": terr,
            "from": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + rep["rcept_no"]}, None


# 제품별 · 지역별 매출 — 같은 정기보고서 원문의 「2. 주요 제품 및 서비스」 · 「4. 매출 및 수주상황」 표를 그대로 옮긴다
# (2026-10-08 재권님 「일부 항목들 할수있는것들은 채워줘」). 표 모양이 회사마다 달라 **해석하지 않고 줄 · 칸 그대로** 둔다 —
# 화면이 「사업보고서 표 그대로」 로 보여 준다. 못 찾으면 null + 이유(지어내지 않는다)
TBL_ROWS, TBL_CELL, SNIP = 14, 60, 420
REGION = re.compile(r"^(국\s*내|내\s*수|수\s*출|해\s*외|미\s*주|미국|북미|중국|아시아|유럽|일본|대만|한국)")


def _clean(s):
    return re.sub(r"\s+", " ", strip_tags(s)).strip()


def _section(x, pat):
    ts = [(m.start(), _clean(m.group(1))) for m in re.finditer(r"<TITLE[^>]*>(.*?)</TITLE>", x, re.S)]
    for i, (p, t) in enumerate(ts):
        if i and re.search(pat, t) and not t.startswith("목"):
            return x[p: ts[i + 1][0] if i + 1 < len(ts) else len(x)]
    return None


def _tables(sec):
    out = []
    for m in re.finditer(r"<TABLE(.*?)</TABLE>", sec or "", re.S):
        rows = [[_clean(c)[:TBL_CELL] for c in re.findall(r"<T[DHEU][^>]*>(.*?)</T[DHEU]>", tr, re.S)]
                for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", m.group(1), re.S)]
        out.append([r for r in rows if any(r)])
    return out


def _unit_before(ts, i):
    """표 바로 앞의 한 줄짜리 표가 「(단위 : …)」 이면 그 글"""
    if i and len(ts[i - 1]) == 1:
        u = " ".join(ts[i - 1][0])
        if "단위" in u:
            return u
    return None


def biz_tables(x):
    out, err = {"product": None, "region": None, "share": None, "customers": None, "materials": None, "materialPrice": None}, []
    ts = _tables(_section(x, r"주요\s*제품"))
    for i, t in enumerate(ts):
        if len(t) >= 2 and re.search(r"매출|비율|비중", " ".join(t[0])):
            out["product"] = {"rows": t[:TBL_ROWS], "unit": _unit_before(ts, i), "cut": len(t) > TBL_ROWS}
            break
    if not out["product"]:
        err.append("「주요 제품」 절에 매출 표 없음")
    ts = _tables(_section(x, r"매출\s*및\s*수주"))
    for i, t in enumerate(ts):
        hit = sum(1 for r in t for c in r[:2] if REGION.match(c))
        if hit >= 2 and not any("⇒" in " ".join(r) for r in t) and any(re.search(r"\d{2,}", c) for r in t for c in r):
            out["region"] = {"rows": t[:TBL_ROWS], "unit": _unit_before(ts, i), "cut": len(t) > TBL_ROWS}
            break
    if not out["region"]:
        err.append("「매출 및 수주상황」 절에 지역 · 내수/수출 표 없음")
    # 성장성 재료(2026-10-08 재권님 「응 해줘」) — 시장점유율 · 주요 매출처 · 원재료. 회사가 적은 글 · 표를 그대로 옮긴다
    ts_all = [(m.start(), _clean(m.group(1))) for m in re.finditer(r"<TITLE[^>]*>(.*?)</TITLE>", x, re.S)]
    a = [p for p, t in ts_all if re.match(r"II\.\s*사업의\s*내용", t)]
    seg = ""
    if a:
        b = [p for p, t in ts_all if re.match(r"III\.", t) and p > a[-1]]
        seg = x[a[-1]: b[0] if b else len(x)]
    tseg = _tables(seg)
    shares = [t for t in tseg if len(t) >= 2 and any("점유율" in c for r in t[:2] for c in r)]
    if not shares:      # 표 바로 아래 「※ 시장점유율은 …」 한 줄짜리 주석만 점유율을 말하는 회사(삼성전자 실측) — 그 앞 표가 점유율 표다
        for i, t in enumerate(tseg):
            if len(t) == 1 and "점유율" in " ".join(t[0]) and i and len(tseg[i - 1]) >= 2:
                shares = [tseg[i - 1]]; break
    txt = _clean(seg)
    m = re.search(r"시장\s*점유율\s*(\(|은|현황)", txt) or re.search(r"시장\s*점유율", txt)
    out["share"] = {"table": {"rows": shares[0][:TBL_ROWS], "unit": None, "cut": len(shares[0]) > TBL_ROWS} if shares else None,
                    "text": txt[m.start(): m.start() + SNIP].rsplit(" ", 1)[0] + "…" if m else None} if (shares or m) else None
    if not out["share"]:
        err.append("「사업의 내용」 에 시장점유율 없음")
    m = re.search(r"주요\s*매출처", txt)
    if m:
        t = txt[m.start(): m.start() + SNIP]
        e = re.search(r"\s[2-9]\.\s|\s[나-하]\.\s", t[10:])
        out["customers"] = (t[: e.start() + 10] if e else t.rsplit(" ", 1)[0] + "…").strip()
    else:
        err.append("「주요 매출처」 글 없음")
    sec = _section(x, r"원재료") or ""
    ts = _tables(sec)
    for i, t in enumerate(ts):
        if len(t) >= 2 and re.search(r"매입|투입", " ".join(t[0])):
            out["materials"] = {"rows": t[:TBL_ROWS], "unit": _unit_before(ts, i), "cut": len(t) > TBL_ROWS}
            break
    # 원재료 가격 — 「가격 변동」 · 「가격변동추이」 글 바로 뒤의 첫 표만(생산능력 · 생산실적 표를 집지 않게 · 2026-10-08 실측)
    pm = re.search(r"가격\s*변동", re.sub(r"<TABLE.*?</TABLE>", "", sec, flags=re.S))
    if pm:
        k = re.search(r"가격\s*변동", sec).start()
        e = re.search(r"생산\s*능력|생산\s*실적|가동률|생산설비", sec[k:])     # 가격 글 뒤 생산 쪽 소절이 오면 거기서 끊는다 — 그 표는 가격이 아니다
        after = _tables(sec[k: k + e.start()] if e else sec[k:])
        pt = next((t for t in after if len(t) >= 2), None)
        if pt:
            out["materialPrice"] = {"rows": pt[:TBL_ROWS], "unit": next((" ".join(t[0]) for t in after[:2] if len(t) == 1 and "단위" in " ".join(t[0])), None), "cut": len(pt) > TBL_ROWS}
    if not out.get("materials"):
        err.append("「원재료」 절에 매입 표 없음")
    return out, "; ".join(err) or None


# 다가오는 일정 — DART 거래소 공시에서 기업설명회(실적 발표) · 배당 기준일 · 주주총회 날짜를 본문에서 읽는다
# (2026-10-08 같은 지시). 제목만으로는 날짜가 안 나와 공시 본문을 연다. 최근 400일 안에서 종류마다 가장 최근 것 하나
EVENT_KINDS = [
    ("ir", r"기업설명회", [(r"일시\s*(\d{4}-\d{2}-\d{2}(?:\s*\d{1,2}:\d{2})?)", "date"), (r"개최목적\s*(.{2,40}?)\s*\d\.", "what")]),
    ("dividend", r"현금ㆍ현물배당결정|현금ㆍ현물배당을위한주주명부폐쇄", [(r"(?:배당기준일|기준일)\s*(\d{4}-\d{2}-\d{2})", "date"),
                                                              (r"배당금지급\s*예정일자\s*(\d{4}-\d{2}-\d{2})", "pay"), (r"1주당 배당금\(원\)\s*보통주식\s*([\d,]+)", "dps")]),
    ("agm", r"주주총회소집결의", [(r"일\s*시\s*(\d{4}-\d{2}-\d{2}(?:\s*\d{1,2}:\d{2})?)", "date")]),
]


def dart_events(key, cc):
    from datetime import timedelta
    bgn = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")
    lst = []
    for page in (1, 2, 3):
        q = urllib.parse.urlencode({"crtfc_key": key, "corp_code": cc, "bgn_de": bgn, "pblntf_ty": "I", "page_no": page, "page_count": 100})
        j = get_json(DART + "/list.json?" + q)
        time.sleep(PAUSE)
        lst += j.get("list") or []
        if page >= int(j.get("total_page") or 1):
            break
    out, today = [], datetime.now().strftime("%Y-%m-%d")
    for kind, pat, fields in EVENT_KINDS:
        hit = next((x for x in lst if re.search(pat, re.sub(r"\s+", "", x.get("report_nm", ""))) and "정정" not in x.get("report_nm", "")), None) \
              or next((x for x in lst if re.search(pat, re.sub(r"\s+", "", x.get("report_nm", "")))), None)
        if not hit:
            continue
        ev = {"kind": kind, "title": re.sub(r"\s+", " ", hit["report_nm"]).strip(), "filed": hit["rcept_dt"],
              "from": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + hit["rcept_no"]}
        try:
            z = zipfile.ZipFile(io.BytesIO(get(DART + "/document.xml?" + urllib.parse.urlencode({"crtfc_key": key, "rcept_no": hit["rcept_no"]}))))
            raw = re.sub(r"<style.*?</style>", "", z.read(z.namelist()[0]).decode("utf-8", "replace"), flags=re.S | re.I)
            txt = strip_tags(raw)
            for rx, k in fields:
                m = re.search(rx, txt)
                ev[k] = m.group(1).strip() if m else None
        except Exception as ex:
            ev["error"] = type(ex).__name__
        time.sleep(PAUSE)
        ev["upcoming"] = bool(ev.get("date") and ev["date"][:10] >= today)
        out.append(ev)
    return {"events": out, "source": "금감원 DART 거래소 공시 본문"}, (None if out else "최근 400일 안 일정 공시 없음")


# 재무 건전성 — DART 단일회사 전체 재무제표(fnlttSinglAcntAll) · 가장 최근 사업보고서 · 연결(없으면 별도)
# (2026-10-07 재권님 「재무건전성은 dart 에서 재무재표를 받아 볼 수 있지 않나」 → 「있음으로 표기되야 하고 채워 넣어줘」)
# 계정은 account_id(IFRS 표준 이름)로 먼저 찾고, 없으면 account_nm(한글)으로 — 회사마다 이름이 조금씩 달라서다. 못 찾은 칸은 null(지어내지 않는다)
FS_WANT = {
    "assets":      (["ifrs-full_Assets"], ["자산총계"]),
    "liab":        (["ifrs-full_Liabilities"], ["부채총계"]),
    "equity":      (["ifrs-full_Equity"], ["자본총계"]),
    "curAssets":   (["ifrs-full_CurrentAssets"], ["유동자산"]),
    "curLiab":     (["ifrs-full_CurrentLiabilities"], ["유동부채"]),
    "cash":        (["ifrs-full_CashAndCashEquivalents"], ["현금및현금성자산", "현금및예치금"]),   # 「현금및예치금」 은 금융지주 · 은행 표기(2026-10-08 KB · 신한 · 하나 실측)
    "revenue":     (["ifrs-full_Revenue"], ["매출액", "수익(매출액)", "영업수익"]),
    "opIncome":    (["dart_OperatingIncomeLoss"], ["영업이익", "영업이익(손실)"]),
    "netIncome":   (["ifrs-full_ProfitLoss"], ["당기순이익", "당기순이익(손실)", "연결당기순이익"]),
    "opCF":        (["ifrs-full_CashFlowsFromUsedInOperatingActivities"], ["영업활동현금흐름", "영업활동으로 인한 현금흐름"]),
    "capex":       (["ifrs-full_PurchaseOfPropertyPlantAndEquipment"], ["유형자산의 취득", "유형자산의취득", "유형자산 취득", "유형자산의 증가"]),
    "dividendPaid":(["ifrs-full_DividendsPaidClassifiedAsFinancingActivities"], ["배당금의 지급", "배당금지급"]),
    "buyback":     (["ifrs-full_PaymentsToAcquireOrRedeemEntitysShares"], ["자기주식의 취득", "자기주식의취득", "자기주식 취득"]),
    # ROIC(투하자본이익률)용 — 2026-10-08 재권님 「일부 항목들 할수있는것들은 채워줘」. 세율 = 법인세비용 ÷ 법인세차감전이익, 투하자본 = 자본 + 차입금 − 현금
    "preTax":      (["ifrs-full_ProfitLossBeforeTax"], ["법인세비용차감전순이익", "법인세비용차감전순이익(손실)", "법인세차감전순이익"]),
    "tax":         (["ifrs-full_IncomeTaxExpenseContinuingOperations"], ["법인세비용", "법인세비용(수익)"]),
    "stBorrow":    (["ifrs-full_ShorttermBorrowings"], ["단기차입금"]),
    "curLTD":      (["ifrs-full_CurrentPortionOfLongtermBorrowings"], ["유동성장기부채", "유동성장기차입금"]),
    "ltBorrow":    (["ifrs-full_LongtermBorrowings"], ["장기차입금"]),
    "bonds":       (["dart_BondsIssued", "ifrs-full_NoncurrentPortionOfNoncurrentBondsIssued"], ["사채"]),
}
FS_SJ = {"assets": "BS", "liab": "BS", "equity": "BS", "curAssets": "BS", "curLiab": "BS", "cash": "BS",
         "revenue": "IS", "opIncome": "IS", "netIncome": "IS", "opCF": "CF", "capex": "CF", "dividendPaid": "CF", "buyback": "CF",
         "preTax": "IS", "tax": "IS", "stBorrow": "BS", "curLTD": "BS", "ltBorrow": "BS", "bonds": "BS"}


def _amt(v):
    try:
        return int(str(v).replace(",", "").strip())
    except Exception:
        return None


def dart_fs(key, cc):
    year = datetime.now().year
    for y in (year - 1, year - 2):
        for div in ("CFS", "OFS"):
            q = urllib.parse.urlencode({"crtfc_key": key, "corp_code": cc, "bsns_year": str(y), "reprt_code": "11011", "fs_div": div})
            j = get_json(DART + "/fnlttSinglAcntAll.json?" + q)
            time.sleep(PAUSE)
            rows = j.get("list") or []
            if j.get("status") != "000" or not rows:
                continue
            out = {"year": y, "fsDiv": "연결" if div == "CFS" else "별도", "unit": "원", "now": {}, "prev": {},
                   "from": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + rows[0].get("rcept_no", ""), "source": "금감원 DART 사업보고서 재무제표"}
            for k, (ids, names) in FS_WANT.items():
                sj = FS_SJ[k]
                cand = [r for r in rows if (r.get("sj_div") == sj or (sj == "IS" and r.get("sj_div") == "CIS"))]
                hit = next((r for r in cand if r.get("account_id") in ids), None) or \
                      next((r for r in cand if r.get("account_nm", "").replace(" ", "") in [n.replace(" ", "") for n in names]), None)
                out["now"][k] = _amt(hit.get("thstrm_amount")) if hit else None
                out["prev"][k] = _amt(hit.get("frmtrm_amount")) if hit else None
            return out, None
    return None, "사업보고서 재무제표 없음(%d · %d)" % (year - 1, year - 2)


# 회계 신뢰도 — DART 회계감사인의 명칭 및 감사의견(accnutAdtorNmNdAdtOpinion) · 가장 최근 사업보고서 · 당기 · 전기
# (2026-10-07 재권님 「회계신뢰도 dart 에서 볼 수 있는 거 같은데 이것도 확인해줘」). 「계속기업」 글자가 강조사항 · 특기사항에 있으면 goingConcern=True
def dart_audit(key, cc):
    year = datetime.now().year
    for y in (year - 1, year - 2):
        q = urllib.parse.urlencode({"crtfc_key": key, "corp_code": cc, "bsns_year": str(y), "reprt_code": "11011"})
        j = get_json(DART + "/accnutAdtorNmNdAdtOpinion.json?" + q)
        time.sleep(PAUSE)
        rows = j.get("list") or []
        if j.get("status") != "000" or not rows:
            continue
        out = []
        for r in rows:
            term = re.sub(r"\s+", "", r.get("bsns_year", ""))
            item = {"term": term, "auditor": r.get("adtor"), "opinion": r.get("adt_opinion"),
                    "emphasis": r.get("emphs_matter"), "special": r.get("adt_reprt_spcmnt_matter"), "keyMatters": r.get("core_adt_matter")}
            item["goingConcern"] = "계속기업" in "%s %s" % (item["emphasis"] or "", item["special"] or "")
            if not (item["opinion"] or "").strip("- "):          # DART 가 빈 줄(의견 없음)을 섞어 보낸다 — 리노공업 · 현대차 실측
                continue
            if not any(x["term"] == item["term"] and x["opinion"] == item["opinion"] and x["keyMatters"] == item["keyMatters"] for x in out):
                out.append(item)
        if not out:
            continue
        return {"year": y, "rows": out, "from": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + rows[0].get("rcept_no", ""),
                "source": "금감원 DART 사업보고서 감사의견"}, None
    return None, "사업보고서 감사의견 없음(%d · %d)" % (year - 1, year - 2)


# 경영진 · 지배구조 · 주주환원 — DART 사업보고서 주요사항(최대주주 · 임원 · 이사 보수 · 5억 이상 개인 보수 · 자기주식 · 배당 · 소액주주)
# (2026-10-07 재권님 「이것도 dart 에서 받을 수 있지 않나? 가능하면 이것도 표기해줘」). 못 받은 칸은 null
def _n(v):
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except Exception:
        return None


def _dart_list(key, cc, api, y):
    q = urllib.parse.urlencode({"crtfc_key": key, "corp_code": cc, "bsns_year": str(y), "reprt_code": "11011"})
    j = get_json(DART + "/%s.json?" % api + q)
    time.sleep(PAUSE)
    return j.get("list") or [] if j.get("status") == "000" else []


def dart_gov(key, cc):
    year = datetime.now().year
    for y in (year - 1, year - 2):
        hs = _dart_list(key, cc, "hyslrSttus", y)
        if not hs:
            continue
        common = [r for r in hs if any(t in (r.get("stock_knd") or "") for t in ("보통", "의결권 있는"))] or hs   # 회사마다 「보통주」 · 「의결권 있는 주식」 으로 갈린다(하이닉스 실측)
        tot = next((r for r in common if (r.get("nm") or "").strip() in ("계", "합계")), None)
        holders = [{"name": r.get("nm"), "relate": r.get("relate"), "pct": _n(r.get("trmend_posesn_stock_qota_rt"))}
                   for r in common if (r.get("nm") or "").strip() not in ("계", "합계")]
        holders.sort(key=lambda x: -(x["pct"] or 0))
        ex = _dart_list(key, cc, "exctvSttus", y)
        reg = [r for r in ex if "이사" in (r.get("rgist_exctv_at") or "") or "감사" in (r.get("rgist_exctv_at") or "")]
        ceo = [r.get("nm") for r in ex if "대표" in (r.get("chrg_job") or "") + (r.get("ofcps") or "")]
        pay = (_dart_list(key, cc, "hmvAuditAllSttus", y) or [{}])[0]
        top = [{"name": r.get("nm"), "title": re.sub(r"\s+", " ", r.get("ofcps") or ""), "pay": _n(r.get("mendng_totamt"))} for r in _dart_list(key, cc, "indvdlByPay", y)]
        ts = [r for r in _dart_list(key, cc, "tesstkAcqsDspsSttus", y) if any(t in (r.get("stock_knd") or "") for t in ("보통", "의결권 있는"))]
        tsum = next((r for r in ts if "계" in (r.get("acqs_mth1") or "") and "소계" not in (r.get("acqs_mth1") or "")), None) or (ts[-1] if ts else None)
        al = _dart_list(key, cc, "alotMatter", y)
        def alv(name, knd=None):
            r = next((r for r in al if name in (r.get("se") or "") and (knd is None or knd in (r.get("stock_knd") or ""))), None)
            return (_n(r.get("thstrm")), _n(r.get("frmtrm"))) if r else (None, None)
        mh = (_dart_list(key, cc, "mrhlSttus", y) or [{}])[0]
        return {"year": y,
                "major": {"totalPct": _n(tot.get("trmend_posesn_stock_qota_rt")) if tot else (round(sum(h["pct"] or 0 for h in holders), 2) if holders else None),
                          "top": holders[:3], "count": len(holders)},
                "board": {"registered": len(reg), "inside": sum(1 for r in reg if "사내" in (r.get("rgist_exctv_at") or "")),
                          "outside": sum(1 for r in reg if "사외" in (r.get("rgist_exctv_at") or "")), "ceo": ceo[:3], "executives": len(ex)},
                "pay": {"people": _n(pay.get("nmpr")), "total": _n(pay.get("mendng_totamt")), "avg": _n(pay.get("jan_avrg_mendng_am")), "top": top[:5]},
                "treasury": {"begin": _n(tsum.get("bsis_qy")), "acquired": _n(tsum.get("change_qy_acqs")), "disposed": _n(tsum.get("change_qy_dsps")),
                             "retired": _n(tsum.get("change_qy_incnr")), "end": _n(tsum.get("trmend_qy"))} if tsum else None,
                "dividend": {"payout": alv("현금배당성향"), "dps": alv("주당 현금배당금", "보통"), "yield": alv("현금배당수익률", "보통")},
                "minority": {"pct": _n(mh.get("hold_stock_rate")), "holders": _n(mh.get("shrholdr_co"))},
                "source": "금감원 DART 사업보고서 — 최대주주 · 임원 · 이사 보수 · 개인별 보수(5억 이상) · 자기주식 · 배당 · 소액주주"}, None
    return None, "사업보고서 최대주주 현황 없음(%d · %d)" % (year - 1, year - 2)


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
    time.sleep(PAUSE)
    fs, err2 = dart_fs(key, cc)
    time.sleep(PAUSE)
    audit, err3 = dart_audit(key, cc)
    time.sleep(PAUSE)
    gov, err4 = dart_gov(key, cc)
    time.sleep(PAUSE)
    events, err5 = dart_events(key, cc)
    err = "; ".join(e for e in (err, err2, err3, err4, err5) if e) or None
    return {"fs": fs, "audit": audit, "gov": gov, "events": events, "corpName": j.get("corp_name"), "ceo": j.get("ceo_nm"), "homepage": j.get("hm_url"),
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
           "sources": {"dart": "금감원 DART 전자공시 — 기업개황 · 정기보고서 「사업의 개요」 · 사업보고서 재무제표(재무 건전성) · 감사의견(회계 신뢰도) · 최대주주 · 임원 · 보수 · 자기주식 · 배당(경영진 · 지배구조 · 주주환원)",
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
