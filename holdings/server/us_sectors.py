"""「지금 뜨는 산업」 의 미국 칸 — SPDR 섹터 ETF 11개 (2026-10-08 지시).

재권님 말씀 — 「지금뜨는산업 국내 미국 에서 미국클릭이 안되고 주간 월간도 안되는데」.
국내 칸은 네이버 업종(`naver.py`)이고, 미국은 업종을 주는 곳이 없어 **섹터 ETF 열하나**를 업종으로 쓴다.

── 값이 어디서 오나 ──

    섹터 등락률      그 ETF 의 일봉(KIS) — `get_chart` 를 그대로 탄다. 열하나라 봉 캐시(`fresh_sec`)가 수를 정한다
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

#: 섹터 ETF 열하나 — 이름은 화면에 나가는 한글 이름이다
SECTORS = (
    ("XLK", "기술"), ("XLF", "금융"), ("XLE", "에너지"), ("XLV", "헬스케어"),
    ("XLI", "산업재"), ("XLY", "경기소비재"), ("XLP", "필수소비재"), ("XLU", "유틸리티"),
    ("XLB", "소재"), ("XLRE", "부동산"), ("XLC", "커뮤니케이션"),
)
SECTOR_NAME = dict(SECTORS)

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

def _change(bars_d, bars_5m, back):
    """(지금 값, 견준 값, 등락률%) — 봉이 모자라면 등락률은 None."""
    if not bars_d:
        return None, None, None
    closes = [b["close"] for b in bars_d if b.get("close") is not None]
    now = closes[-1] if closes else None
    if bars_5m and bars_d and bars_5m[-1]["ts"][:8] > bars_d[-1]["ts"][:8]:
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
    """섹터 열하나 → 등락률 큰 순. 국내 `naver.groups` 와 같은 칸 이름을 쓴다(화면이 같은 코드로 그린다).

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
