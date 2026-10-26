# -*- coding: utf-8 -*-
"""실적 · 금리 결정 · 미국 지표 — 결과가 나오면 텔레그램으로 (2026-10-25 재권님 · 작업우선순위 경유).

재권님 말씀 — 「수요일 오전 9시에 SK 하이닉스 실적 발표 있고, 새벽 3시에 FOMC 금리 결정하는 거 있고 …
요것들 다 일정 체크해가지고 일정 나올 때마다 정리해가지고 텔레그램을 받으면 좋을 것 같은데」.
안에 「가」 — **밤사이(22:00~07:00 · 조용한 시간) 결과는 07:00 에 한 통으로 묶는다** · 미국 실적 일정은 손 목록.

── 무엇을 보나 · 결과를 어디서 받나 ──

    한국 실적   관심종목(`dart.WATCH_CODES`)의 「영업(잠정)실적」 공시 — 공시 바퀴가 이미 받아 둔 것(market.db)을 읽고,
                본문 표(DART 화면)에서 매출 · 영업이익 · 순이익과 전분기 · 전년 대비를 읽는다
    FOMC        고정 일정 파일(`data/market-calendar.json`)의 FOMC 줄 `result.type = "fomc"` —
                연준 보도 목록(RSS)의 「Federal Reserve issues FOMC statement」 를 읽어 금리 범위와 올림 · 내림 · 동결
    미국 실적   같은 파일의 실적 줄 `result.type = "sec"` · `cik` — 미국 증권위원회(SEC) 공시의 실적 8-K(항목 2.02) ·
                보도자료(EX-99.1) 첫머리에서 매출 · 주당순이익(희석)
    미국 지표   `macro.RELEASES` 의 발표일(FRED) — 발표 시각이 지나면 그 계열 하나만 FRED 에서 바로 받는다
                (`macro.bundle` 은 발표 한 시간 뒤에야 다시 받는다 · 그 캐시는 건드리지 않는다). 같은 시각 발표는 한 통

**예상치와 견주지 않는다** — 예상치를 받는 곳이 없다(재권님 안 그대로). 숫자는 회사 · 기관 원문에서 읽은 것만 낸다.
못 읽으면 지어내지 않고 「숫자 못 읽음 — 원문 주소」 로 낸다.

── 언제 보내나 ──

    낮(07:00~22:00)   결과를 읽은 그 바퀴에 바로 한 통
    밤(22:00~07:00)   쌓아 두었다가 07:00 이 지난 첫 바퀴에 「🌙 밤사이 결과」 한 통 — 07:30 데일리 글 앞
    끝내 못 받음      기다림이 지나면(`GIVE_UP_H`) 「결과를 못 받았습니다 — 주소」 한 줄을 같은 길로 — 조용히 빠지지 않게

발송은 `dart.telegram_send` 하나다(조용한 시간 · 4,096자 나누기 그대로). **보내는 서버는 메인(`is_sender`) 하나** —
`kis_proxy` 가 그 서버에서만 이 바퀴를 띄운다.

**`SEND = False` 가 기본이다 — 켜기는 재권님 지시로**(「커밋 · 푸시 · 배포 규칙」 의 켜기). 꺼져 있으면 바퀴는 돌되
보내지 않고, 보냈을 글을 `/api/events/status` 의 `preview` 에 남긴다(보낸 표시도 안 남긴다 — 켜면 그때 처음 보낸다).

손으로 보기:  python3 holdings/server/events.py --check 2026-07-29   그날(한국 날짜) 무엇이 어떤 글로 나갔을지 — 보내지 않는다
"""

import html as _html
import json
import os
import re
import sys
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import dart
import macro
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))
ET = ZoneInfo("America/New_York")

SEND = True                  # 2026-10-25 재권님 「응 해줘」 로 켬(작업우선순위 경유) — 끄려면 False · 위 머리 주석
TICK = 300                   # 5분마다 한 바퀴 (공시 바퀴와 같은 간격)
GIVE_UP_H = 12               # 결과 시각부터 이만큼 지나도 못 받으면 「못 받음」 한 줄
TIMEOUT = 20

CAL_PATH = os.path.join(HERE, "..", "data", "market-calendar.json")
SEC_UA = "KJCStudio contact@kjcstudio.kr"     # SEC 는 연락처가 든 이름표를 요구한다(공정 접근 규칙)
FED_RSS = "https://www.federalreserve.gov/feeds/press_monetary.xml"
EARN_WORD = "영업(잠정)실적"                     # 잠정실적 공정공시 제목에 늘 든다
STATE_KEY = "events_state"                      # market.db sync_meta — {보낸 것 · 못 받음 표시 · 밤사이 쌓인 글}

_lock = threading.Lock()
_status = {"startedAt": None, "lastTick": None, "lastError": None, "tracked": [], "preview": []}


# ── 받기 ────────────────────────────────────────────────────────────

def _get(url, ua=None):
    req = urllib.request.Request(url, headers={"User-Agent": ua} if ua else {})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def _text(raw):
    """HTML → 한 줄 글. 줄표 · 나눔 없는 빈칸을 보통 글자로 바꾼다(숫자 읽기가 그것에 걸린다 — FOMC 4월 결정문)."""
    t = raw if isinstance(raw, str) else raw.decode("utf-8", "replace")
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)
    for a, b in (("‑", "-"), ("‐", "-"), ("‒", "-"), ("\xa0", " "), (" ", " "), (" ", " ")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def _rows(raw_html):
    """HTML 표 → 칸 글자 목록의 목록."""
    out = []
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", raw_html):
        cells = [_text(c) for c in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row)]
        if cells:
            out.append(cells)
    return out


# ── 숫자 꼴 ─────────────────────────────────────────────────────────

def _pct(v):
    """'+13.7%' · '-4.0%' · 숫자가 아니면 None."""
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return "%+.1f%%" % f


def _usd(amount, scale):
    """'119.8', 'billion' → '$119.8B(1,198억 달러)'."""
    a = float(amount.replace(",", ""))
    eok = a * 10 if scale.lower() == "billion" else a / 100        # 1 billion = 10억 달러 · 100 million = 1억 달러
    eok_s = ("{:,.0f}".format(eok) if eok >= 10 else "{:,.1f}".format(eok))
    return "$%s%s(%s억 달러)" % (amount, "B" if scale.lower() == "billion" else "M", eok_s)


def _frac(s):
    """'3-3/4' → 3.75 · '4' → 4.0."""
    s = s.strip()
    m = re.match(r"^(\d+)(?:-(\d+)/(\d+))?$", s)
    if m:
        v = float(m.group(1))
        if m.group(2):
            v += float(m.group(2)) / float(m.group(3))
        return v
    m = re.match(r"^(\d+)/(\d+)$", s)
    return float(m.group(1)) / float(m.group(2)) if m else None


# ── 한국 실적 — DART 잠정실적 공시 본문 ─────────────────────────────

def dart_body(rcept_no):
    """공시 본문 HTML(EUC-KR → 글). 첫 화면에서 문서 번호를 찾아 그 문서를 받는다."""
    main = _get(dart.VIEWER % rcept_no).decode("utf-8", "replace")
    m = re.search(r'viewDoc\("%s",\s*"(\d+)"' % rcept_no, main)
    if not m:
        raise RuntimeError("공시 문서 번호를 못 찾았습니다")
    raw = _get("https://dart.fss.or.kr/report/viewer.do?rcpNo=%s&dcmNo=%s&eleId=0&offset=0&length=0&dtd=HTML"
               % (rcept_no, m.group(1)))
    for enc in ("cp949", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def parse_earnings_kr(body):
    """잠정실적 표 → {unit, period, items: [{name, cur, prev, qoq, yoy_prev, yoy}]}.
    표 모양(2026-10-08 삼성전자 실측): 「매출액 · 당해실적 · 당기 · 전기 · 전기대비% · 흑적 · 전년동기 · 전년동기대비% · 흑적」."""
    rows = _rows(body)
    unit = None
    m = re.search(r"단위\s*:\s*([^,%<\s]+)", _text(body))
    if m:
        unit = m.group(1)
    period = None
    for r in rows:
        if r and r[0] == "당기실적" and len(r) >= 4:
            period = "%s~%s" % (r[1], r[3])
            break
    want = [("매출액", "매출"), ("영업이익", "영업이익"), ("당기순이익", "순이익")]
    items = []
    for key, label in want:
        for r in rows:
            if len(r) >= 9 and r[0] == key and r[1] == "당해실적":
                cur, prev, qoq, yprev, yoy = r[2], r[3], r[4], r[6], r[7]
                if cur in ("-", ""):
                    break
                items.append({"name": label, "cur": cur, "prev": prev, "qoq": qoq, "yprev": yprev, "yoy": yoy,
                              "turn_q": r[5] if r[5] not in ("-", "") else None,
                              "turn_y": r[8] if r[8] not in ("-", "") else None})
                break
    return {"unit": unit, "period": period, "items": items}


def _won(v, unit):
    """표 값 → 읽기 쉬운 원 단위. 백만원 · 억원은 1조가 넘으면 조원으로(2026-07-29 하이닉스 「79,318,746백만원」 → 79.32조원)."""
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return "%s%s" % (v, unit or "")
    per_jo = {"백만원": 1e6, "억원": 1e4, "천원": 1e9, "원": 1e12}.get(unit or "")
    if per_jo and abs(f) >= per_jo:
        return "%.2f조원" % (f / per_jo)
    if unit == "백만원" and abs(f) >= 100:
        return "{:,.0f}억원".format(f / 100)
    return "%s%s" % (v, unit or "")


def format_earnings_kr(name, code, title, url, parsed):
    lines = ["📊 %s(%s) 잠정실적" % (name, code)]
    if parsed and parsed.get("items"):
        u = parsed.get("unit") or ""
        for it in parsed["items"]:
            bits = ["%s %s" % (it["name"], _won(it["cur"], u))]
            q = it["turn_q"] or (_pct(it["qoq"]) and "전분기비 " + _pct(it["qoq"]))
            y = it["turn_y"] or (_pct(it["yoy"]) and "전년비 " + _pct(it["yoy"]))
            bits += [b for b in (q, y) if b]
            lines.append(" · ".join(bits))
        if parsed.get("period"):
            lines.append("기간 %s · 연결" % parsed["period"])
    else:
        lines.append("숫자 못 읽음 — 공시 원문을 보십시오")
    lines.append((title or "").strip())
    lines.append(url)
    return "\n".join(lines)


def kr_earnings_today(day):
    """그날(한국 날짜 'YYYYMMDD') 관심종목 잠정실적 공시 — 공시 바퀴가 market.db 에 받아 둔 것."""
    out = []
    for code in dart.WATCH_CODES:
        for r in dart.read_disclosures(code, 20):
            if r["date"] == day and EARN_WORD in (r["title"] or ""):
                out.append(r)
    return out


# ── FOMC — 연준 보도문 ──────────────────────────────────────────────

def fomc_statement(et_day):
    """그 미국 날짜의 FOMC 결정문 주소. 보도 목록(RSS)에서 찾는다 — 없으면 None."""
    xml = _get(FED_RSS, SEC_UA).decode("utf-8", "replace")
    stamp = et_day.replace("-", "")
    for item in re.findall(r"(?s)<item>(.*?)</item>", xml):
        title = re.search(r"(?s)<title>(.*?)</title>", item)
        link = re.search(r"(?s)<link>(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?</link>", item)
        if title and link and "FOMC statement" in title.group(1) and stamp in link.group(1):
            return link.group(1).strip()
    return None


def parse_fomc(text):
    """결정문 → {action, by, lo, hi, vote}. 문장(2026-06 · 07 · 09 실측): 「decided to maintain|lower|raise the target range
    for the federal funds rate [by 1/4 percentage point] (at|to) 3-1/2 to 3-3/4 percent」."""
    m = re.search(r"(?i)decided to (maintain|lower|raise) the target range for the federal funds rate([^.]*?)percent\b(?!age)", text)
    if not m:
        return None
    tail = m.group(2)
    rng = re.search(r"(?:at|to)\s+([\d/-]+)\s+to\s+([\d/-]+)\s*$", tail.strip())
    by = re.search(r"by\s+([\d/-]+)\s+percentage point", tail)
    vote = re.search(r"by a (\d+)\s*[-–]\s*(\d+) vote", text)
    if not rng:
        return None
    return {"action": m.group(1).lower(), "by": _frac(by.group(1)) if by else None,
            "lo": _frac(rng.group(1)), "hi": _frac(rng.group(2)),
            "vote": (int(vote.group(1)), int(vote.group(2))) if vote else None}


def format_fomc(p, url):
    word = {"maintain": "동결", "lower": "인하", "raise": "인상"}[p["action"]]
    head = word if p["action"] == "maintain" else "%.2f%%p %s" % (p["by"], word) if p["by"] else word
    lines = ["🏦 미국 FOMC 금리 결정 — %s" % head,
             "기준금리 범위 %.2f~%.2f%%" % (p["lo"], p["hi"])]
    if p.get("vote"):
        lines.append("표결 찬성 %d · 반대 %d" % p["vote"])
    lines.append("연준 결정문 %s" % url)
    return "\n".join(lines)


# ── 미국 실적 — SEC 8-K 항목 2.02 · 보도자료 EX-99.1 ────────────────

def sec_earnings_filing(cik, et_day):
    """그 미국 날짜에 낸 실적 8-K(항목 2.02)의 (접수번호, 접수 시각). 없으면 None."""
    j = json.loads(_get("https://data.sec.gov/submissions/CIK%010d.json" % int(cik), SEC_UA))
    r = (j.get("filings") or {}).get("recent") or {}
    for i, form in enumerate(r.get("form") or []):
        if form == "8-K" and "2.02" in (r["items"][i] or "") and r["filingDate"][i] == et_day:
            return r["accessionNumber"][i], r["acceptanceDateTime"][i]
    return None


def sec_exhibit(cik, acc):
    """접수 목록 화면에서 EX-99.1 주소. 첨부 이름이 회사마다 달라(인텔 q226earningsrelease.htm) 종류 칸으로 찾는다."""
    a = acc.replace("-", "")
    h = _get("https://www.sec.gov/Archives/edgar/data/%d/%s/%s-index.html" % (int(cik), a, acc), SEC_UA)
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", h.decode("utf-8", "replace")):
        if re.search(r">\s*EX-99\.1\s*<", row):
            m = re.search(r'href="([^"]+\.htm)"', row)
            if m:
                return "https://www.sec.gov" + m.group(1)
    return None


_AMT = r"\$\s?([\d,]+(?:\.\d+)?)\s?(billion|million)"


def parse_earnings_us(text):
    """보도자료 첫머리 → {rev, scale, pct, pct_dir, basis, eps}. 지난 세 분기 네 회사(구글 · 인텔 · 아마존 · 샌디스크)
    열두 건으로 맞췄다(2026-10-25). 사업부 매출(AWS · Cloud 등) · 연 환산(run rate) 값은 건너뛴다."""
    head = text[:6000]
    out = {}
    for c in re.finditer(r"(?i)\b(revenues?|net sales)\b(?:(?!income|margin)[^$.]){0,140}?" + _AMT, head):
        before = head[max(0, c.start() - 30):c.start()]
        after = head[c.end():c.end() + 40]
        if re.search(r"(?i)\b(AWS|segment|Cloud|Services|Datacenter|Edge|Consumer)\s*$", before) \
                or re.search(r"(?i)run rate", after):
            continue
        out["rev"], out["scale"] = c.group(2), c.group(3)
        s = head[max(0, c.start() - 10):c.end() + 160]
        p = re.search(r"(?i)\b(increased|up|grew|growth of|decreased|down|declined)\b[^%]{0,30}?(\d+(?:\.\d+)?)%\s*"
                      r"(sequentially|year[- ]over[- ]year)?", s)
        if p:
            out["pct"] = float(p.group(2)) * (-1 if p.group(1).lower() in ("decreased", "down", "declined") else 1)
            out["basis"] = "전분기비" if (p.group(3) or "").lower() == "sequentially" else "전년비"
        break
    m = (re.search(r"(?i)\$\s?(-?[\d.]+)\s+per\s+diluted\s+share", head)
         or re.search(r"(?i)\$\s?(-?[\d.]+)\)?\s*(?:GAAP\s+)?diluted\s+(?:net income|earnings|EPS)", head)
         or re.search(r"(?i)\b(?:diluted\s+)?(?:EPS|earnings per (?:diluted )?share|net income per (?:diluted )?share)\b"
                      r"[^$]{0,80}?\$\s?(-?[\d.]+)", head))
    if m:
        out["eps"] = m.group(1).rstrip(".")
    return out


def format_earnings_us(title, p, url):
    lines = ["📊 %s" % title]
    if p.get("rev"):
        s = "매출 %s" % _usd(p["rev"], p["scale"])
        if p.get("pct") is not None:
            s += " · %s %+.0f%%" % (p["basis"], p["pct"])
        lines.append(s)
    if p.get("eps"):
        lines.append("주당순이익(희석) $%s" % p["eps"])
    if not p.get("rev") and not p.get("eps"):
        lines.append("숫자 못 읽음 — 보도자료를 보십시오")
    lines.append("보도자료(미국 증권위원회 공시) %s" % url)
    return "\n".join(lines)


# ── 미국 지표 — FRED 그 계열 하나 ────────────────────────────────────

def fred_series(sid):
    """macro 의 계열 id → 점 목록. 원 계열이면 FRED 하나, 계산 계열이면 원 계열을 받아 같은 셈(`macro._derive`)."""
    if sid in macro.RAW_BY:
        return macro._fred(*macro.RAW_BY[sid]["fred"])
    d = next((x for x in macro.DERIVED if x["id"] == sid), None)
    if not d:
        raise RuntimeError("모르는 계열 %s" % sid)
    return macro._derive(d["how"], macro._fred(*macro.RAW_BY[d["from"]]["fred"]))


def _label(sid):
    m = macro.RAW_BY.get(sid) or next((x for x in macro.DERIVED if x["id"] == sid), {})
    return m.get("label", sid), m.get("unit", "")


def _is_count(unit):
    return unit in ("천명", "건", "천건", "백만 달러")


def _num(v, unit):
    if _is_count(unit):
        return "{:,.0f}{}".format(v, unit)
    return ("{:,.2f}".format(v) + (unit if unit in ("%", "%p") else (" " + unit if unit else ""))).rstrip()


def _period(d, freq):
    """'2026-04' (분기) → '2026년 2분기' · 주간 '2026-10-17' → '10-17 주' · 달 그대로."""
    if freq == "Q":
        return "%s년 %d분기" % (d[:4], (int(d[5:7]) - 1) // 3 + 1)
    if freq == "W":
        return "%s 주" % d[5:10]
    return d


def _line(sid, pts):
    label, unit = _label(sid)
    meta = macro.RAW_BY.get(sid) or {}
    fred = meta.get("fred") or (macro.RAW_BY.get(next((x["from"] for x in macro.DERIVED if x["id"] == sid), ""), {}).get("fred") or ())
    freq = fred[2] if len(fred) > 2 else "M"
    last, prev = pts[-1], (pts[-2] if len(pts) > 1 else None)
    s = "%s %s(%s)" % (label, _num(last["v"], unit), _period(last["d"], freq))
    if prev:
        dv = last["v"] - prev["v"]
        s += " · 직전 %s · %s" % (_num(prev["v"], unit), ("{:+,.0f}".format(dv) if _is_count(unit) else "%+.2f" % dv))
    return s


def format_release(rel, pts):
    """한 발표 → 줄 몇(이름 · 머리 값 · 딸린 값). pts 는 그 발표의 머리 계열."""
    out = ["• %s" % rel["name"], "  " + _line(rel["main"], pts)]
    for sid in rel.get("also") or []:
        try:
            out.append("  " + _line(sid, fred_series(sid)))
        except Exception:
            pass                       # 딸린 값은 못 받아도 머리 값은 낸다
    return out


# ── 할 일 모으기 ────────────────────────────────────────────────────

def _cal():
    with open(CAL_PATH, encoding="utf-8") as f:
        return json.load(f)


def _at_et(day, hm):
    hh, mm = (int(x) for x in hm.split(":"))
    y, m, d = (int(x) for x in day.split("-"))
    return datetime(y, m, d, hh, mm, tzinfo=ET).astimezone(KST)


def tasks(now):
    """지금 결과를 기다리는 것 — 결과 시각이 지났고 `GIVE_UP_H` 안인 것. [{id, kind, at, …}]"""
    out = []
    lo = now - timedelta(hours=GIVE_UP_H + 1)
    try:
        events = _cal().get("events") or []
    except (OSError, ValueError) as e:
        events = []
        _status["lastError"] = "일정 파일 못 읽음 — %s" % safe_message(e, 80)
    for e in events:
        res = e.get("result") or {}
        if res.get("type") not in ("fomc", "sec"):
            continue
        day = e.get("endDate") or e.get("date")
        at = _at_et(day, res.get("et") or "16:00")
        if lo <= at <= now:
            out.append({"id": "%s:%s:%s" % (res["type"], day, res.get("cik") or ""), "kind": res["type"],
                        "at": at, "etDay": day, "title": e.get("title") or "", "cik": res.get("cik")})
    dates, _err = macro._release_dates()
    slots = {}
    for r in macro.RELEASES:
        for d in (dates or {}).get(r["key"]) or []:
            at = macro._release_at(r, d)
            if lo <= at <= now:
                slots.setdefault((d, r["et"]), []).append(r)
    for (d, et), rels in sorted(slots.items()):
        out.append({"id": "rel:%s:%s" % (d, et), "kind": "rel", "at": _at_et(d, et), "etDay": d, "rels": rels})
    kday = now.strftime("%Y%m%d")
    for r in kr_earnings_today(kday):
        out.append({"id": "kr:%s" % r["rceptNo"], "kind": "kr", "at": now, "row": r})
    return out


def resolve(t, state):
    """할 일 하나 → (글 또는 None, 다 끝났나). 못 받았으면 (None, False) — 다음 바퀴에 다시."""
    if t["kind"] == "kr":
        r = t["row"]
        try:
            parsed = parse_earnings_kr(dart_body(r["rceptNo"]))
        except Exception as e:
            print("  [결과] %s 공시 본문 못 읽음 — %s" % (r["name"], safe_message(e, 80)), flush=True)
            parsed = None
        return format_earnings_kr(r["name"], r["code"], r["title"], r["url"], parsed), True
    if t["kind"] == "fomc":
        url = fomc_statement(t["etDay"])
        if not url:
            return None, False
        p = parse_fomc(_text(_get(url, SEC_UA)))
        if not p:
            return "🏦 미국 FOMC 금리 결정 — 결정문은 나왔는데 숫자 못 읽음\n%s" % url, True
        return format_fomc(p, url), True
    if t["kind"] == "sec":
        f = sec_earnings_filing(t["cik"], t["etDay"])
        if not f:
            return None, False
        url = sec_exhibit(t["cik"], f[0])
        if not url:
            return "📊 %s\n보도자료 첨부를 못 찾음 — 공시 접수 %s" % (t["title"], f[0]), True
        return format_earnings_us(t["title"], parse_earnings_us(_text(_get(url, SEC_UA))), url), True
    if t["kind"] == "rel":
        done = state.setdefault("relDone", {}).setdefault(t["id"], [])
        ready = []
        for r in t["rels"]:
            if r["key"] in done:
                continue
            try:
                pts = fred_series(r["main"])
            except Exception as e:
                print("  [결과] %s FRED 못 받음 — %s" % (r["short"], safe_message(e, 80)), flush=True)
                continue
            if pts and macro._fresh(r, t["etDay"], pts[-1]):
                ready.append((r, pts))
        everything = len(done) + len(ready) == len(t["rels"])
        # 같은 시각 발표는 다 들어오면 한 통 · 한 시간이 지나면 들어온 것부터 보낸다(늦는 것은 다음 통)
        late = t["now"] - t["at"] > timedelta(hours=1)
        if ready and (everything or late):
            done.extend(r["key"] for r, _ in ready)
            lines = []
            for r, pts in ready:
                lines += format_release(r, pts)
            kst = t["at"].strftime("%m-%d %H:%M")
            return "📈 미국 지표 발표 (한국 %s · 미국 날짜 %s)\n%s\n출처 FRED" % (kst, t["etDay"], "\n".join(lines)), everything
        return None, False
    return None, True


def _give_up_text(t):
    name = {"fomc": "미국 FOMC 금리 결정", "sec": t.get("title"), "rel": "미국 지표(%s)" % t.get("etDay")}.get(t["kind"], t["id"])
    return "⚠ %s — 결과를 %d시간 안에 못 받았습니다(원문을 직접 보십시오)" % (name, GIVE_UP_H)


# ── 한 바퀴 ─────────────────────────────────────────────────────────

def _load_state():
    try:
        return json.loads(dart._meta_get(STATE_KEY) or "{}")
    except ValueError:
        return {}


def _save_state(state, now):
    # 오래된 표시는 버린다 — 열나흘이 지난 것
    cut = (now - timedelta(days=14)).isoformat()
    state["done"] = {k: v for k, v in (state.get("done") or {}).items() if v >= cut}
    dart._meta_set(STATE_KEY, json.dumps(state, ensure_ascii=False))


def _emit(text, state, now):
    """보낸다 — 밤이면 쌓는다. 꺼져 있으면 미리보기에만. 돌려주는 것: 이 글을 처리했나(다음 바퀴에 또 보낼 필요 없음)."""
    if not SEND:
        _status["preview"] = (_status["preview"] + [{"at": now.isoformat(timespec="seconds"),
                                                     "night": dart.in_quiet(now.timestamp()), "text": text}])[-20:]
        return True
    if dart.in_quiet(now.timestamp()):
        state.setdefault("queue", []).append(text)
        return True
    ok, why = dart.telegram_send(text)
    if not ok:
        print("  [결과] 보내지 못함 — %s" % safe_message(Exception(why), 100), flush=True)
    return ok


def tick(now=None):
    now = now or datetime.now(KST)
    with _lock:
        state = _load_state()
        done = state.setdefault("done", {})
        if not SEND:
            done.update(_status.setdefault("_mem", {}))   # 꺼져 있으면 디스크에 안 쓴다 — 기억은 이 프로세스 안에만
        # 밤사이 쌓인 것 — 조용한 시간이 끝난 첫 바퀴에 한 통
        if SEND and state.get("queue") and not dart.in_quiet(now.timestamp()):
            body = "🌙 밤사이 결과 (%d건)\n\n%s" % (len(state["queue"]), "\n\n".join(state["queue"]))
            ok, why = dart.telegram_send(body)
            if ok:
                state["queue"] = []
            else:
                print("  [결과] 밤사이 묶음 보내지 못함 — %s" % safe_message(Exception(why), 100), flush=True)
        tracked = []
        for t in tasks(now):
            if t["id"] in done:
                continue
            tracked.append({"id": t["id"], "kind": t["kind"], "at": t["at"].isoformat(timespec="minutes")})
            t["now"] = now
            try:
                text, finished = resolve(t, state)
            except Exception as e:
                print("  [결과] %s 못 받음 — %s: %s" % (t["id"], type(e).__name__, safe_message(e, 80)), flush=True)
                text, finished = None, False
            if text and _emit(text, state, now) and finished and SEND:
                done[t["id"]] = now.isoformat(timespec="seconds")
            elif not text and not finished and now - t["at"] > timedelta(hours=GIVE_UP_H):
                if _emit(_give_up_text(t), state, now) and SEND:
                    done[t["id"]] = now.isoformat(timespec="seconds")
            elif finished and not text and SEND:
                done[t["id"]] = now.isoformat(timespec="seconds")
            if not SEND and (text or finished):
                done[t["id"]] = "미리보기"             # 꺼져 있어도 같은 글을 바퀴마다 또 만들지 않는다 — 저장은 안 한다
        if SEND:
            _save_state(state, now)
        else:
            _status.setdefault("_mem", {}).update(done)
        _status["tracked"] = tracked
        _status["lastTick"] = now.isoformat(timespec="seconds")


def start():
    """메인(보내는 서버)에서 `kis_proxy` 가 부른다."""
    _status["startedAt"] = datetime.now(KST).isoformat(timespec="seconds")

    def loop():
        time.sleep(20)
        last = None
        while True:
            try:
                tick()
                last = None
            except Exception as e:
                key = "%s: %s" % (type(e).__name__, safe_message(e, 100))
                _status["lastError"] = key
                if key != last:
                    last = key
                    print("  [결과] 바퀴 오류 — %s (같은 오류는 다시 안 적습니다)" % key, flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="events-results").start()
    return True


def status():
    s = {k: v for k, v in _status.items() if not k.startswith("_")}
    s.update(send=SEND, tickSec=TICK, giveUpHours=GIVE_UP_H,
             queued=len((_load_state().get("queue") or [])) if SEND else None)
    return s


# ── 손으로 보기 ─────────────────────────────────────────────────────

def check(kday):
    """그 한국 날짜에 결과를 냈을 글을 찍는다. 보내지 않고 상태도 안 쓴다 — 지난 날로 셈을 대보는 자리."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    y, m, d = (int(x) for x in kday.split("-"))
    now = datetime(y, m, d, 23, 59, tzinfo=KST)
    found = 0
    # 한국 실적 — 그날 접수된 관심종목 잠정실적
    for r in kr_earnings_today(now.strftime("%Y%m%d")):
        found += 1
        print(resolve({"kind": "kr", "row": r}, {})[0], "\n")
    # FOMC · 미국 실적 — 미국 날짜는 하루 전(한국 새벽에 나온다)
    et_day = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    url = fomc_statement(et_day)
    if url:
        found += 1
        p = parse_fomc(_text(_get(url, SEC_UA)))
        print(format_fomc(p, url) if p else "FOMC 숫자 못 읽음 %s" % url, "\n")
    # 회사 목록은 일정 파일의 result.type == "sec" 줄에서 뽑는다 — 여기 따로 적으면 회사가 늘 때 이쪽만 낡는다
    seen = {}
    for e in _cal().get("events", []):
        r = e.get("result") or {}
        if r.get("type") == "sec" and r.get("cik") not in seen:
            seen[r["cik"]] = e.get("title", "")
    for cik, title in seen.items():
        f = sec_earnings_filing(cik, et_day)
        if f:
            found += 1
            url = sec_exhibit(cik, f[0])
            print(format_earnings_us(title, parse_earnings_us(_text(_get(url, SEC_UA))), url), "\n")
            time.sleep(0.3)
    print("(%s · 찾은 결과 %d건 · 미국 지표는 FRED 발표일 범위가 지난 40일이라 여기서 안 봄)" % (kday, found))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--check":
        check(sys.argv[2])
    else:
        print(__doc__)
