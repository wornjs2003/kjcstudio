"""
첫 화면 시장 지도(히트맵) — 칸 넓이 = 시가총액 · 색 = 오늘 등락률 (2026-10-27 재권님 「홈이나 국내 미국 을 누르면 첫화면이
이런식으로 코스피 코스닥 등등이 보여지면 좋을거 같은데」 → 시안 「응 맞아」 → 「응 시작해」).

    GET /api/kis/heatmap?market=kr     코스피 시가총액 상위 KR_TOP["kospi"] · 코스닥 KR_TOP["kosdaq"]
    GET /api/kis/heatmap?market=us     섹터 ETF 열하나(SPDR) 구성 종목 중 시가총액 상위 US_TOP

    → {"market", "groups": [{"name", "sectors": [{"name", "stocks": [{"code", "name", "cap", "pct", "price"}]}]}],
       "asof", "capNote", "missing": [code]}

국내
  - **종목 · 업종 · 시가총액** — KIS 종목 목록 파일(nxt_pre.MASTER · 하루 한 번). 업종은 그 파일의 지수업종 중분류 → 소분류 → 대분류
    순으로 이름이 있는 첫 칸(「제조」 처럼 너무 넓은 대분류는 건너뛴다). 이름은 업종 지수 응답(fetch_sectors)의 이름 그대로
  - 그 파일의 시가총액(억원)은 **전날 종가 기준**이다 — 2026-10-27 실측 삼성전자 12,452,573억 ↔ 순위표 1,248.2조. 그래서
    지금 값 = 파일 값 × 지금가 / 전날 종가
  - **등락률 · 지금가 · 전날 종가** — 순위표와 같은 멀티 시세(kis_proxy.fetch_quotes_multi · 30종목씩 한 바퀴 = KIS 4번).
    정규장 중은 KRX · 장 밖은 통합(넥스트레이드)이다 — holdings/CLAUDE.md 「시세 표기 규칙」. 응답은 HEATMAP_TTL 동안 그대로 낸다
    (재권님 「주가가 바뀌면 바뀌도록 적용해줘」 2026-10-28 — 60초에서 줄임 · 화면은 롱폴로 바뀐 것을 받는다)
  - 업종 분류는 증권사 것 그대로다 — 지주사가 「금융」 · 알테오젠이 「일반서비스」 에 들어간다(재권님이 그대로 쓰기로 함)

미국
  - 「지금 뜨는 산업」 미국 칸과 같은 값(us_sectors.stocks — 봉 표만 읽는다 · KIS 를 더 안 부른다). 반도체(XSD)는 기술(XLK)과
    종목이 겹쳐 뺀다
  - 시가총액은 나스닥100 순위표가 하루 한 번 적어 두는 `uscap:<티커>`(달러). 없는 종목은 같은 섹터 안에서 「시가총액 ÷ ETF 비중」 의
    가운데 값으로 어림한다(ETF 비중은 시가총액 비례라 한 섹터 안에서는 그 비가 거의 같다) — 어림한 수는 `estimated` 로 낸다

「없음」 은 None 으로 낸다 — 0 으로 꾸미지 않는다(화면은 회색 · —).
"""
import io
import threading
import time
import urllib.request
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

import nxt_pre
import us_sectors

KR_TOP = {"kospi": 70, "kosdaq": 40}       # 시안 그대로 — 재권님 「응 맞아」(2026-10-27)
US_TOP = 110
HEATMAP_TTL = 5                             # 응답을 그대로 내는 초 — 보는 동안 KIS 초당 0.8건(2026-10-28 8765 실측 초당 1.6건 · 예산 40)
WIDE = ("제조",)                            # 대분류 중 너무 넓어 업종으로 안 쓰는 이름
US_SKIP = ("XSD",)                          # 기술(XLK)과 겹치는 반도체 ETF

_KST = ZoneInfo("Asia/Seoul")
_master = {"day": None, "rows": None}
_master_lock = threading.Lock()
_cache = {}                                  # market → (시각, 값)


def _today():
    return datetime.now(_KST).strftime("%Y%m%d")


def master():
    """{"kospi": [{code, name, cap(억원), secs:[대, 중, 소]}] (시가총액 큰 순), "kosdaq": …} — 하루 한 번 받는다."""
    with _master_lock:
        if _master["day"] == _today() and _master["rows"]:
            return _master["rows"]
        out = {}
        for mk, tail in nxt_pre.MASTER_TAIL.items():
            req = urllib.request.Request(nxt_pre.MASTER % mk, headers={"User-Agent": "Mozilla/5.0 KJCStudio"})
            with urllib.request.urlopen(req, timeout=30) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            text = z.read(z.namelist()[0]).decode("cp949", "replace")
            rows = []
            for row in text.split("\n"):
                row = row.rstrip("\r")
                if len(row) <= tail:
                    continue
                p = row[-tail:]
                code = row[0:9].strip()
                if p[0:2] != "ST" or len(code) != 6:
                    continue
                try:
                    cap = int(p[-15:-6])             # 끝에서 시가총액(9) · 그룹사(3) · 신용 · 담보 · 대주(1씩)
                except ValueError:
                    continue
                rows.append({"code": code, "name": row[21:-tail].strip(), "cap": cap or None,
                             "secs": [p[3:7], p[7:11], p[11:15]]})
            rows.sort(key=lambda x: -(x["cap"] or 0))
            if len(rows) < 500:                      # 모양이 바뀌었으면 수가 크게 준다 — 그날은 쓰지 않는다
                raise RuntimeError("%s 종목 목록에서 주권이 %d개뿐입니다(모양이 바뀌었을 수 있음)" % (mk, len(rows)))
            out[mk] = rows
        _master["day"], _master["rows"] = _today(), out
        return out


def kr(proxy, cfg):
    hit = _cache.get("kr")
    if hit and time.time() - hit[0] < HEATMAP_TTL:
        return hit[1]
    names = {}
    try:
        data, _err = proxy.fetch_sectors(cfg)
        names = {r["code"]: r["name"] for r in data}
    except Exception:
        pass                                         # 이름표를 못 받으면 업종은 「기타」 — 지도는 그린다
    m = master()
    picks = {mk: m[mk][:n] for mk, n in KR_TOP.items()}
    q, _errs = proxy.fetch_quotes_multi(cfg, [r["code"] for rows in picks.values() for r in rows], max_age=HEATMAP_TTL)
    groups, missing = [], []
    for mk, label in (("kospi", "코스피"), ("kosdaq", "코스닥")):
        secs = {}
        for r in picks[mk]:
            p = q.get(r["code"]) or {}
            price, prev = p.get("price"), p.get("prev")
            cap = r["cap"] * price / prev if (r["cap"] and price and prev) else r["cap"]
            if p.get("pct") is None:
                missing.append(r["code"])
            c1, c2, c3 = r["secs"]
            sec = next((names[c] for c in (c2, c3, c1) if c in names and names[c] not in WIDE), "기타")
            secs.setdefault(sec, []).append({"code": r["code"], "name": r["name"], "cap": round(cap) if cap else None,
                                             "pct": p.get("pct"), "price": price})
        groups.append({"name": label, "sectors": _sorted(secs)})
    out = {"market": "kr", "groups": groups, "asof": datetime.now(_KST).isoformat(timespec="seconds"),
           "capUnit": "억원", "capNote": "종목 목록 파일(전날 종가) × 지금가 ÷ 전날 종가", "missing": missing,
           "div": proxy.quote_market_div(), "source": "KIS 종목 목록 · KIS 멀티 시세"}
    _cache["kr"] = (time.time(), out)
    return out


def us(proxy, read_candles, known, sector_stocks):
    """sector_stocks(etf) → us_sectors.stocks 결과(kis_proxy 의 섹터 캐시를 함께 쓴다)"""
    hit = _cache.get("us")
    if hit and time.time() - hit[0] < HEATMAP_TTL:
        return hit[1]
    caps = {}
    with proxy._db_lock, proxy.db_conn() as conn:
        for r in conn.execute("SELECT key, value FROM sync_meta WHERE key LIKE 'uscap:%'"):
            try:
                caps[r["key"][6:]] = float(r["value"])
            except (TypeError, ValueError):
                pass
    every = []
    for etf, sname in us_sectors.SECTORS:
        if etf in US_SKIP:
            continue
        rows = (sector_stocks(etf) or {}).get("rows") or []
        ratios = sorted(caps[r["code"]] / r["weight"] for r in rows if caps.get(r["code"]) and r.get("weight"))
        mid = ratios[len(ratios) // 2] if ratios else None
        for r in rows:
            cap, est = caps.get(r["code"]), False
            if not cap and mid and r.get("weight"):
                cap, est = mid * r["weight"], True
            if cap:
                every.append({"sector": sname, "code": r["code"], "name": r["name"], "cap": round(cap),
                              "pct": r.get("pct"), "price": r.get("price"), "estimated": est})
    seen, top = set(), []
    for r in sorted(every, key=lambda x: -x["cap"]):
        if r["code"] in seen:                        # 두 섹터에 든 종목은 큰 쪽 하나만
            continue
        seen.add(r["code"])
        top.append(r)
        if len(top) >= US_TOP:
            break
    secs = {}
    for r in top:
        secs.setdefault(r.pop("sector"), []).append(r)
    out = {"market": "us", "groups": [{"name": "미국", "sectors": _sorted(secs)}],
           "asof": datetime.now(_KST).isoformat(timespec="seconds"), "capUnit": "달러",
           "capNote": "나스닥100 순위표가 적어 둔 값 · 없으면 섹터 ETF 비중으로 어림(estimated)",
           "missing": [r["code"] for r in top if r["pct"] is None], "source": "State Street · KIS"}
    _cache["us"] = (time.time(), out)
    return out


def _sorted(secs):
    """업종 안은 시가총액 큰 순 · 업종은 합이 큰 순"""
    out = [{"name": n, "stocks": sorted(rs, key=lambda x: -(x["cap"] or 0))} for n, rs in secs.items()]
    out.sort(key=lambda s: -sum(x["cap"] or 0 for x in s["stocks"]))
    return out
