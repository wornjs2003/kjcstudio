"""「지금 뜨는 산업」 의 미국 칸 — SPDR 섹터 ETF 11개 + 반도체(XSD · 2026-10-27) (2026-10-08 지시).

재권님 말씀 — 「지금뜨는산업 국내 미국 에서 미국클릭이 안되고 주간 월간도 안되는데」.
국내 칸은 네이버 업종(`naver.py`)이고, 미국은 업종을 주는 곳이 없어 **섹터 ETF 열하나**(+ 반도체 XSD · 2026-10-27)를 업종으로 쓴다.

── 값이 어디서 오나 ──

    섹터 등락률      그 ETF 의 일봉(KIS) — `get_chart` 를 그대로 탄다. 열둘이라 봉 캐시(`fresh_sec`)가 수를 정한다
    구성 종목        State Street 가 날마다 내는 보유 종목 파일(xlsx) — 하루 한 번 받는다
    종목 등락률      **봉 표(candles)에 이미 있는 일봉**만 읽는다 — KIS 를 더 안 부른다.
                    메인 서버(8765)가 장 전에 S&P500 · 나스닥100 전 종목의 일봉을 받아 둔다(`start_us_prefill`).
                    봉이 없는 종목은 등락률을 `None` 으로 낸다 — `0` 으로 내지 않는다(「못 쟀으면 「못 쟀다」 고 낸다」)

── 기간 ──

    d  마지막 봉 ÷ 그 앞 봉        w  마지막 봉 ÷ 5봉 앞        m  마지막 봉 ÷ 20봉 앞

5분봉이 마지막 일봉보다 새것이면 그 종가를 「지금 값」 으로 쓴다 — 장중에 일봉이 아직 없을 때다.

**kis_proxy 함수는 인자로 받는다** — `us_universe` 와 같은 까닭(kis_proxy 가 이 파일을 import 한다).
"""

import io
import re
import threading
import time
import urllib.request
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

_KST, _NY = ZoneInfo("Asia/Seoul"), ZoneInfo("America/New_York")

#: 섹터 ETF 열둘 — 이름은 화면에 나가는 한글 이름이다
SECTORS = (
    ("XLK", "기술"), ("XLF", "금융"), ("XLE", "에너지"), ("XLV", "헬스케어"),
    ("XLI", "산업재"), ("XLY", "경기소비재"), ("XLP", "필수소비재"), ("XLU", "유틸리티"),
    ("XLB", "소재"), ("XLRE", "부동산"), ("XLC", "커뮤니케이션"),
    # 반도체 — SPDR 11 섹터에는 칸이 없고 기술(XLK) 안에 섞여 있다. 같은 State Street 파일을 내는 SPDR S&P 반도체 ETF.
    # 종목 비중이 같은(동일가중) ETF 라 엔비디아도 다른 종목과 같은 무게다 (2026-10-27 재권님 「전날 반도체가 떴는데 반도체가 없는게」 → 「응」)
    ("XSD", "반도체"),
)
SECTOR_NAME = dict(SECTORS)

#: 한국 업종(네이버 WICS 이름 · company_profile.sectors) → 미국 섹터 ETF — 국제 표준 분류(GICS) 큰 갈래 그대로 · 반도체 업종만 XSD.
#: 자동 관심 룰 「미국장 같은 섹터 % 이상」(auto_watch · strategy-rules volsurge.sectorPct)이 이 표 하나를 읽는다(2026-11-12 재권님
#: 「안 세는 것 — 이건 미국장이 끝나면 토스나 네이버에서 받아올수 있지않나?」 → 덧 조건(또는)). 표에 없는 업종은 「못 셈」(빼지 않는다)
KR_SECTOR_ETF = {
    "반도체와반도체장비": "XSD",
    "디스플레이장비및부품": "XLK", "디스플레이패널": "XLK", "전자장비와기기": "XLK", "통신장비": "XLK", "IT서비스": "XLK",
    "소프트웨어": "XLK", "핸드셋": "XLK",
    "제약": "XLV", "생물공학": "XLV", "건강관리장비와용품": "XLV", "생명과학도구및서비스": "XLV", "건강관리업체및서비스": "XLV",
    "건강관리기술": "XLV",
    "기계": "XLI", "전기제품": "XLI", "전기장비": "XLI", "우주항공과국방": "XLI", "복합기업": "XLI", "조선": "XLI", "건설": "XLI",
    "상업서비스와공급품": "XLI", "건축자재": "XLI", "항공사": "XLI", "항공화물운송과물류": "XLI", "무역회사와판매업체": "XLI",
    "운송인프라": "XLI", "도로와철도운송": "XLI", "해운사": "XLI",
    "화학": "XLB", "철강": "XLB", "비철금속": "XLB", "포장재": "XLB",
    "은행": "XLF", "증권": "XLF", "손해보험": "XLF", "생명보험": "XLF", "카드": "XLF", "창업투자": "XLF",
    "화장품": "XLP", "식품": "XLP", "담배": "XLP", "가정용기기와용품": "XLP",
    "자동차부품": "XLY", "자동차": "XLY", "백화점과일반상점": "XLY", "섬유,의류,신발,호화품": "XLY", "호텔,레스토랑,레저": "XLY",
    "인터넷과카탈로그소매": "XLY", "전자제품": "XLY",
    "게임엔터테인먼트": "XLC", "방송과엔터테인먼트": "XLC", "양방향미디어와서비스": "XLC", "무선통신서비스": "XLC",
    "다각화된통신서비스": "XLC", "광고": "XLC",
    "석유와가스": "XLE", "에너지장비및서비스": "XLE", "전기유틸리티": "XLU", "가스유틸리티": "XLU",
}


def last_changes(conn):
    """섹터 ETF 마다 가장 최근에 끝난 미국장 하루 등락률 {etf: (미국 날짜, %)} — 봉 표(candles)의 일봉 마지막 둘. 없으면 빠진다."""
    out = {}
    for etf, _ in SECTORS:
        r = conn.execute("SELECT ts, close FROM candles WHERE period = 'D' AND code = ? ORDER BY ts DESC LIMIT 2", (etf,)).fetchall()
        if len(r) == 2 and r[0][1] and r[1][1]:
            out[etf] = (str(r[0][0])[:8], round((r[0][1] / r[1][1] - 1) * 100, 2))
    return out

#: 기간 → 몇 봉 앞과 견주나
SPAN_BACK = {"d": 1, "w": 5, "m": 20}

HOLDINGS_URL = ("https://www.ssga.com/library-content/products/fund-data/etfs/us/"
                "holdings-daily-us-en-%s.xlsx")
HOLDINGS_TTL = 6 * 3600          # 파일은 하루 한 번 바뀐다
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

_hold = {}                        # 티커 → {"at", "rows", "asof"}
_hold_lock = threading.Lock()


# ── 보유 종목 파일 ──────────────────────────────────────────────────────────

def _col(ref):
    """'B12' → 1"""
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def _read_xlsx(raw):
    """첫 시트를 줄 목록으로. 표 칸(sharedStrings) · 글자 칸(inlineStr) · 숫자 칸을 다 읽는다."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        s = z.read("xl/sharedStrings.xml").decode("utf-8")
        for si in re.findall(r"<si>(.*?)</si>", s, re.S):
            shared.append("".join(re.findall(r"<t[^>]*>([^<]*)</t>", si)))
    sheet = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    out = []
    for row in re.findall(r"<row[^>]*>(.*?)</row>", sheet, re.S):
        cells = {}
        for attrs, body in re.findall(r"<c ([^>]*?)(?:/>|>(.*?)</c>)", row, re.S):
            ref = re.search(r'r="([A-Z]+)\d+"', attrs)
            if not ref:
                continue
            t = re.search(r't="(\w+)"', attrs)
            t = t.group(1) if t else ""
            if t == "inlineStr":
                v = "".join(re.findall(r"<t[^>]*>([^<]*)</t>", body or ""))
            else:
                m = re.search(r"<v>([^<]*)</v>", body or "")
                v = m.group(1) if m else ""
                if t == "s" and v.isdigit():
                    v = shared[int(v)] if int(v) < len(shared) else ""
            cells[_col(ref.group(1))] = v.strip()
        if cells:
            out.append([cells.get(i, "") for i in range(max(cells) + 1)])
    return out


def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def holdings(etf):
    """그 ETF 의 보유 종목 → (목록, 기준일). 목록은 {"ticker", "name", "weight"} · 비중 큰 순.

    못 받으면 들고 있던 것을 그대로 쓴다. 처음부터 못 받았으면 빈 목록.
    """
    with _hold_lock:
        hit = _hold.get(etf)
        if hit and time.time() - hit["at"] < HOLDINGS_TTL:
            return hit["rows"], hit["asof"]
    try:
        req = urllib.request.Request(HOLDINGS_URL % etf.lower(), headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            table = _read_xlsx(r.read())
    except Exception:
        return (hit["rows"], hit["asof"]) if hit else ([], None)

    asof = None
    rows, head = [], None
    for line in table:
        if not head:
            if line and line[0].startswith("As of"):
                asof = line[0][len("As of"):].strip()
            for c in line[1:]:
                if c.startswith("As of"):
                    asof = c[len("As of"):].strip()
            if line and line[0] == "Name" and "Ticker" in line:
                head = {name: i for i, name in enumerate(line)}
            continue
        get = lambda k: line[head[k]] if k in head and head[k] < len(line) else ""
        tic = get("Ticker").upper()
        w = _num(get("Weight"))
        if not tic or w is None or tic in ("-", "CASH_USD"):
            continue
        rows.append({"ticker": tic, "name": get("Name"), "weight": w})
    rows.sort(key=lambda x: -x["weight"])
    with _hold_lock:
        _hold[etf] = {"at": time.time(), "rows": rows, "asof": asof}
    return rows, asof


def _symbol(tic, known):
    """보유 파일 표기(BRK.B) → 마스터 표기. 둘 다 없으면 None — 시세를 못 부르는 종목이다."""
    for t in (tic, tic.replace(".", "/"), tic.replace(".", ""), tic.replace(".", "-")):
        if t in known:
            return t
    return None


# ── 등락률 ──────────────────────────────────────────────────────────────────

def _us_day(ts_kst):
    """5분봉 시각(한국 시각 'YYYYMMDDHHMM') → 그 봉의 미국 날짜 'YYYYMMDD'.

    일봉 ts 는 미국 날짜, 5분봉 ts 는 한국 시각이다. 앞 8자를 그대로 견주면 미국장이 끝난 뒤(한국 새벽 05:00 마감봉)
    5분봉이 늘 「다음 날」 로 보여 장중으로 읽혔다 — 구성 종목 하루 등락률이 마감값끼리 견준 ≈0% 가 됐다
    (2026-10-27 실측 · NVDA 실제 +2.39% → +0.03%). 서머타임은 ZoneInfo 가 가린다."""
    try:
        return datetime.strptime(ts_kst[:12], "%Y%m%d%H%M").replace(tzinfo=_KST).astimezone(_NY).strftime("%Y%m%d")
    except (TypeError, ValueError):
        return ts_kst[:8]


def _change(bars_d, bars_5m, back):
    """(지금 값, 견준 값, 등락률%) — 봉이 모자라면 등락률은 None."""
    if not bars_d:
        return None, None, None
    closes = [b["close"] for b in bars_d if b.get("close") is not None]
    now = closes[-1] if closes else None
    if bars_5m and bars_d and _us_day(bars_5m[-1]["ts"]) > bars_d[-1]["ts"][:8]:
        now = bars_5m[-1]["close"]           # 장중 — 오늘 일봉이 아직 없다
        closes.append(now)
    if now is None or len(closes) <= back:
        return now, None, None
    base = closes[-1 - back]
    if not base:
        return now, None, None
    return now, base, (now / base - 1.0) * 100.0


def _member_rows(etf, span, read_candles, known):
    back = SPAN_BACK[span]
    hold, asof = holdings(etf)
    out = []
    for h in hold:
        sym = _symbol(h["ticker"], known)
        if not sym:
            continue
        now, base, pct = _change(read_candles(sym, "D", back + 2), read_candles(sym, "5m", 1), back)
        info = known.get(sym) or {}
        out.append({
            "code": sym, "name": info.get("name_ko") or h["name"],
            "price": now, "amt": (now - base) if (now is not None and base) else None,
            "pct": pct, "weight": h["weight"],
        })
    return out, asof


def groups(span, get_chart, read_candles, known):
    """섹터 열둘 → 등락률 큰 순. 국내 `naver.groups` 와 같은 칸 이름을 쓴다(화면이 같은 코드로 그린다).

    rise · steady · fall 은 **봉이 있는 구성 종목만** 센다 — `count` 는 보유 종목 전체, `measured` 는 센 수.
    """
    back = SPAN_BACK[span]
    rows = []
    for etf, name in SECTORS:
        pct = None
        try:
            bars, _, _ = get_chart(etf, "D", back + 30)
            _, _, pct = _change(bars, read_candles(etf, "5m", 1), back)
        except Exception:
            pass
        members, _ = _member_rows(etf, span, read_candles, known)
        got = [m["pct"] for m in members if m["pct"] is not None]
        rows.append({
            "no": etf, "name": name, "pct": pct,
            "rise": sum(1 for p in got if p > 0), "steady": sum(1 for p in got if p == 0),
            "fall": sum(1 for p in got if p < 0),
            "count": len(members), "measured": len(got),
        })
    rows.sort(key=lambda r: (r["pct"] is None, -(r["pct"] or 0)))
    return rows


def stocks(etf, span, read_candles, known):
    """그 섹터의 구성 종목 → 등락률 큰 순(상승률 TOP). 봉이 없는 종목은 뒤로 — 등락률 None."""
    if etf not in SECTOR_NAME:
        raise ValueError("섹터는 %s 중 하나여야 합니다." % ", ".join(SECTOR_NAME))
    rows, asof = _member_rows(etf, span, read_candles, known)
    rows.sort(key=lambda r: (r["pct"] is None, -(r["pct"] or 0)))
    return {"rows": rows, "name": SECTOR_NAME[etf], "asof": asof}
