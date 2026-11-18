# -*- coding: utf-8 -*-
"""「실적」 칩 — 실적이 예상보다 좋고, 앞으로의 전망도 좋게 낸 종목 (2026-11-18).

재권님 — 「실적 잘 나오는 종목만 추려 가지고 보는 것도 만들어야 될 거 같애」(11-17 창구 창) · 기준 「예상보다 좋게 나온 것과 앞으로 성장성도
좋게 발표 된 것 두가지」(창구 경유) · 자리 「가」 홈 실시간 순위 칩 · 「이거 insight에 단타에도 칩 추가되어야해」 · 셈 안에 「응 해줘」(11-18 개발3 창).
셈은 이 파일 한 곳이고 홈 칩과 Insight 단타 판 칩이 같은 주소를 받는다.

    ① 예상보다 좋음   회사가 낸 「영업(잠정)실적」 공시의 영업이익(당기) > 네이버 그 분기 예상치(isConsensus=Y 칸)
                     그 분기 칸이 이미 실적(N)이면 예상치가 남아 있지 않다 — 「예상치 없음」(null · 0 으로 안 메운다)
                     당기가 분기(대략 석 달)가 아니면 「분기 실적 아님」 으로 못 가름
    ② 전망 좋음       「영업실적등에대한전망」 공시 표의 가장 뒤 해(값이 든 해) 매출 · 영업이익 — 값이 든 칸만 — 이 모두 기준보다 큼
                     기준: 네이버 연간 그 앞 해 실적(N) · 그 해가 아직 예상치(Y)면 최근 실적 네 분기 합
                     전망 기간이 1년이 아니면(분기 · 반기 전망) 못 가름
    칩              days(기본 · 최대 31) 안에 ① ② 가 둘 다 맞은 종목. 같은 종목 공시가 여럿이면 가장 새 것(정정이면 정정본) · 연결 먼저

    받기   8765(보내는 서버)만 공시 본문(dart.viewer_body — 공시 뷰어 · OpenDART 하루 한도 밖)과 네이버 재무를 받아 market.db 에 둔다 —
           5분마다 FETCH_MAX 건까지 · 네이버는 종목마다 NAVER_TTL 지나면 다시. 다른 서버는 쌓인 것을 읽기만 한다
    네이버  m.stock.naver.com/api/stock/<코드>/finance/quarter · annual — 비공식 · 이용 약관 안 봄(재권님께 알리고 「응 해줘」)
    주소   GET /api/earnings-beat?days=31 — 모양은 compute() 주석 · 「없음」 은 null
"""
import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone

import dart
import events
import naver
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))
DAYS_DEFAULT = 31
DAYS_MAX = 31
FETCH_DAYS = 31
FETCH_MAX = 20                  # 한 바퀴 본문 건수 — 31일에 잠정실적 · 전망 합 600건 안팎(11-17 8765 잼 578 + 22) · 첫날만 밀린다
TICK = 300
GAP_SEC = 0.5
NAVER_TTL = 6 * 3600            # 예상치는 하루에 몇 번 안 바뀐다
RETRY_SEC = 3600                # 본문 · 네이버 받기 실패 뒤 다시 받기까지
RETRY_MAX = 3
EARN_WORD = events.EARN_WORD    # 「영업(잠정)실적」 — 한 곳
OUTLOOK_WORD = "영업실적등에대한전망"
TO_EOK = {"원": 1e-8, "천원": 1e-5, "백만원": 1e-2, "억원": 1.0, "조원": 1e4}

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS earnings_beat_doc (
        rcept_no TEXT PRIMARY KEY, kind TEXT, parsed TEXT, error TEXT, fetched_at TEXT, tries INTEGER DEFAULT 0, retry_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS earnings_beat_naver (
        code TEXT PRIMARY KEY, quarter TEXT, annual TEXT, error TEXT, fetched_at TEXT)""",
)
_status = {"fetchAt": None, "docs": None, "naver": None, "pending": None, "error": None}
_lock = threading.Lock()


def _now():
    return datetime.now(KST)


def _init(proxy):
    with proxy._db_lock, proxy.db_conn() as conn:
        for q in _SCHEMA:
            conn.execute(q)


def kind_of(title):
    t = re.sub(r"\s", "", title or "")
    if EARN_WORD in t:
        return "earn"
    if OUTLOOK_WORD in t:
        return "outlook"
    return None


def _num(v):
    s = re.sub(r"[,\s]", "", str(v or ""))
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return None


def _eok(v, unit):
    f, k = _num(v), TO_EOK.get(unit or "")
    return None if f is None or k is None else f * k


def _day(s):
    m = re.match(r"(20\d{2})[-.]?(\d{2})[-.]?(\d{2})", s or "")
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


# ---------------------------------------------------------------- 공시 본문 읽기

def parse_earn(body):
    """잠정실적 → {unit, start, end, op(영업이익 당기 · 억원), sales(억원)} — 표 읽기는 events.parse_earnings_kr 한 곳."""
    p = events.parse_earnings_kr(body)
    unit = p.get("unit")
    start = end = None
    if p.get("period"):
        a, _, b = p["period"].partition("~")
        start, end = a.strip(), b.strip()
    got = {it["name"]: _eok(it["cur"], unit) for it in p.get("items") or []}
    return {"unit": unit, "start": start, "end": end, "op": got.get("영업이익"), "sales": got.get("매출")}


def parse_outlook(body):
    """실적 전망 표 → {unit, years: [{year, start, end, sales, op}]} — 값은 억원 · 빈칸은 None.
    표 모양(2026-11-18 엔씨 잼): 「구분(단위 : 억원) · 2026 · 사업연도 · 2027 · 사업연도 …」 / 「대상기간 · 시작일 · …」 / 「종료일 · …」 / 「매출액 · v · v · v」."""
    rows = events._rows(body)
    unit, years = None, []
    for r in rows:
        if r and "단위" in r[0]:
            m = re.search(r"단위\s*:\s*([^)\s]+)", r[0])
            unit = m.group(1) if m else None
            years = [c for c in r[1:] if re.fullmatch(r"20\d{2}", c or "")]
            break
    if not years:
        return {"unit": unit, "years": [], "error": "전망 표 머리(해) 못 찾음"}
    n = len(years)

    def vals(r):
        return r[-n:] if len(r) > n else None

    out = [{"year": int(y), "start": None, "end": None, "sales": None, "op": None} for y in years]
    head = next(i for i, r in enumerate(rows) if r and "단위" in r[0])
    for r in rows[head + 1:]:
        if not r:
            continue
        if re.match(r"\d+\.", r[0]):     # 다음 절(「2. 전망 또는 예측의 근거」) — 표 하나만 읽는다(뒤에 다른 표가 붙는 공시가 있다 · 11-18 서울반도체)
            break
        v = vals(r)
        if v is None:
            continue
        key = r[0]
        if key == "대상기간" or "시작일" in r[:2]:
            field = "start"
        elif key == "종료일":
            field = "end"
        elif key == "매출액":
            field = "sales"
        elif key == "영업이익":
            field = "op"
        else:
            continue
        for o, x in zip(out, v):
            if field in ("start", "end"):
                o[field] = x if _day(x) else None
            elif o[field] is None:
                o[field] = _eok(x, unit)
    return {"unit": unit, "years": out}


# ---------------------------------------------------------------- 받기 (보내는 서버만)

def _naver_fin(code):
    q = naver._get("https://m.stock.naver.com/api/stock/%s/finance/quarter" % code)
    a = naver._get("https://m.stock.naver.com/api/stock/%s/finance/annual" % code)

    def slim(j):
        fi = (j or {}).get("financeInfo") or {}
        cons = {t.get("key"): t.get("isConsensus") == "Y" for t in fi.get("trTitleList") or []}
        rows = {}
        for r in fi.get("rowList") or []:
            if r.get("title") in ("매출액", "영업이익"):
                rows[r["title"]] = {k: _num((v or {}).get("value")) for k, v in (r.get("columns") or {}).items()}
        return {"cons": cons, "rows": rows}
    return slim(q), slim(a)


def keep_consensus(old, new):
    """네이버는 분기보고서가 나오면 그 분기 예상치 칸을 실적으로 바꿔 예상치가 사라진다(2026-11-18 잼 — 11월 중순 3분기 잠정실적 대부분 「예상치 없음」).
    그래서 받을 때마다 예상치(Y) 칸을 kept 에 남겨 두고, 새로 받은 것이 실적(N)으로 바뀌어도 kept 는 지우지 않는다."""
    kept = dict((old or {}).get("kept") or {})
    for k, y in (new.get("cons") or {}).items():
        if y:
            kept[k] = (new["rows"].get("영업이익") or {}).get(k)
    new["kept"] = {k: v for k, v in kept.items() if v is not None}
    return new


def fetch_round(proxy):
    if not _lock.acquire(blocking=False):
        return None
    try:
        _init(proxy)
        _status["error"] = None
        now = _now()
        since = (now - timedelta(days=FETCH_DAYS)).strftime("%Y%m%d")
        with proxy._db_lock, proxy.db_conn() as conn:
            rows = conn.execute(
                "SELECT d.rcept_no, d.stock_code, d.report_nm, COALESCE(e.tries, 0) FROM dart_disclosures d "
                "LEFT JOIN earnings_beat_doc e ON e.rcept_no = d.rcept_no "
                "WHERE d.rcept_dt >= ? AND (d.report_nm LIKE ? OR d.report_nm LIKE ?) "
                "AND (e.rcept_no IS NULL OR (e.retry_at IS NOT NULL AND e.retry_at <= ?)) ORDER BY d.rcept_no DESC",
                (since, "%" + EARN_WORD + "%", "%" + OUTLOOK_WORD + "%", now.isoformat(timespec="seconds"))).fetchall()
            codes = [r[0] for r in conn.execute(
                "SELECT DISTINCT stock_code FROM dart_disclosures WHERE rcept_dt >= ? AND stock_code != '' "
                "AND (report_nm LIKE ? OR report_nm LIKE ?)", (since, "%" + EARN_WORD + "%", "%" + OUTLOOK_WORD + "%"))]
            fresh = {r[0] for r in conn.execute(
                "SELECT code FROM earnings_beat_naver WHERE fetched_at >= ?",
                ((now - timedelta(seconds=NAVER_TTL)).isoformat(timespec="seconds"),))}
        docs = 0
        for rno, code, nm, tries in rows[:FETCH_MAX]:
            kind = kind_of(nm)
            parsed = err = retry_at = None
            try:
                body = dart.viewer_body(rno)
                parsed = parse_earn(body) if kind == "earn" else parse_outlook(body)
            except Exception as e:
                err = safe_message(e, 160)
                tries += 1
                if tries < RETRY_MAX:
                    retry_at = (now + timedelta(seconds=RETRY_SEC)).isoformat(timespec="seconds")
            with proxy._db_lock, proxy.db_conn() as conn:
                conn.execute("INSERT OR REPLACE INTO earnings_beat_doc VALUES (?,?,?,?,?,?,?)",
                             (rno, kind, json.dumps(parsed, ensure_ascii=False) if parsed else None, err,
                              _now().isoformat(timespec="seconds"), tries, retry_at))
            docs += 1
            time.sleep(GAP_SEC)
        nv = 0
        for code in codes:
            if not code or code in fresh:
                continue
            q = a = err = None
            try:
                q, a = _naver_fin(code)
            except Exception as e:
                err = safe_message(e, 160)
            with proxy._db_lock, proxy.db_conn() as conn:
                if err:     # 못 받으면 들고 있던 값은 두고 받은 시각만 — RETRY_SEC 뒤 다시(fetched_at 을 TTL 앞으로 당겨 둔다)
                    at = (_now() - timedelta(seconds=NAVER_TTL - RETRY_SEC)).isoformat(timespec="seconds")
                    if conn.execute("UPDATE earnings_beat_naver SET error = ?, fetched_at = ? WHERE code = ?", (err, at, code)).rowcount == 0:
                        conn.execute("INSERT INTO earnings_beat_naver VALUES (?,?,?,?,?)", (code, None, None, err, at))
                else:
                    old = conn.execute("SELECT quarter FROM earnings_beat_naver WHERE code = ?", (code,)).fetchone()
                    q = keep_consensus(json.loads(old[0]) if old and old[0] else None, q)
                    conn.execute("INSERT OR REPLACE INTO earnings_beat_naver VALUES (?,?,?,?,?)",
                                 (code, json.dumps(q), json.dumps(a), None, _now().isoformat(timespec="seconds")))
            nv += 1
            time.sleep(GAP_SEC)
        _status.update(fetchAt=_now().isoformat(timespec="seconds"), docs=docs, naver=nv, pending=max(0, len(rows) - docs))
        return docs
    except Exception as e:
        _status["error"] = safe_message(e, 160)
        return 0
    finally:
        _lock.release()


def start(proxy):
    def loop():
        time.sleep(120)
        while True:
            fetch_round(proxy)
            time.sleep(TICK)
    threading.Thread(target=loop, name="earnings-beat", daemon=True).start()
    return True


# ---------------------------------------------------------------- 셈

def judge_beat(p, fin):
    """→ {ok, op, consensus, pct, quarter, why}. ok: True · False · None(못 가름)."""
    out = {"ok": None, "op": None, "consensus": None, "pct": None, "quarter": None, "why": None}
    if not p:
        out["why"] = "본문 아직 안 읽음"
        return out
    out["op"] = p.get("op")
    s, e = _day(p.get("start")), _day(p.get("end"))
    if not (s and e):
        out["why"] = "실적 기간 못 읽음"
        return out
    if not 80 <= (e - s).days <= 100:
        out["why"] = "분기 실적 아님(%s~%s)" % (p.get("start"), p.get("end"))
        return out
    key = e.strftime("%Y%m")
    out["quarter"] = key
    if p.get("op") is None:
        out["why"] = "영업이익 못 읽음"
        return out
    q = (fin or {}).get("quarter")
    if not q:
        out["why"] = "네이버 재무 아직 안 받음"
        return out
    c = (q["rows"].get("영업이익") or {}).get(key) if q["cons"].get(key) else (q.get("kept") or {}).get(key)
    if c is None and not q["cons"].get(key):
        out["why"] = "예상치 없음(네이버에 그 분기 예상치가 없음 · 실적 확정 전에 못 받아 둠)"
        return out
    if c is None:
        out["why"] = "예상치 없음(영업이익 칸 빔)"
        return out
    out["consensus"] = c
    out["pct"] = round((p["op"] / c - 1) * 100, 1) if c > 0 else None
    out["ok"] = p["op"] > c
    out["why"] = "영업이익 %s억 %s 예상 %s억" % (_fmt(p["op"]), ">" if out["ok"] else "≤", _fmt(c))
    return out


def _base(fin, year, name):
    """year 전망의 기준 — (값, 어디서). 앞 해 연간 실적 · 없으면 최근 실적 네 분기 합."""
    a, q = (fin or {}).get("annual"), (fin or {}).get("quarter")
    k = "%d12" % (year - 1)
    if a and a["cons"].get(k) is False and (a["rows"].get(name) or {}).get(k) is not None:
        return a["rows"][name][k], "%d년 실적" % (year - 1)
    if q:
        keys = sorted(k for k, y in q["cons"].items() if y is False)[-4:]
        vals = [(q["rows"].get(name) or {}).get(k) for k in keys]
        if len(keys) == 4 and all(v is not None for v in vals):
            return sum(vals), "최근 네 분기 실적 합(%s~%s)" % (keys[0], keys[-1])
    return None, None


def _base_part(fin, s, e, name):
    """1년이 아닌 전망(분기 · 반기)의 기준 — 한 해 앞 같은 기간의 실적 분기 합. 분기가 다 없으면 None."""
    q = (fin or {}).get("quarter")
    if not q:
        return None, None
    n = max(1, round(((e - s).days + 1) / 91))
    lo, hi = "%d%02d" % (s.year - 1, s.month), "%d%02d" % (e.year - 1, e.month)
    keys = sorted(k for k, y in q["cons"].items() if y is False and lo <= k <= hi)
    vals = [(q["rows"].get(name) or {}).get(k) for k in keys]
    if len(keys) != n or any(v is None for v in vals):
        return None, None
    return sum(vals), "한 해 앞 같은 기간 실적(%s~%s)" % (keys[0], keys[-1])


def judge_outlook(p, fin):
    """→ {ok, year, sales, op, base: {sales, op}, from, why}."""
    out = {"ok": None, "year": None, "sales": None, "op": None, "base": {}, "from": None, "why": None}
    if not p:
        out["why"] = "본문 아직 안 읽음"
        return out
    ys = [y for y in p.get("years") or [] if y.get("sales") is not None or y.get("op") is not None]
    if not ys:
        out["why"] = p.get("error") or "전망 값이 빈칸"
        return out
    y = ys[-1]
    out.update(year=y["year"], sales=y["sales"], op=y["op"])
    s, e = _day(y.get("start")), _day(y.get("end"))
    part = bool(s and e and not 330 <= (e - s).days <= 370)     # 분기 · 반기 전망 — 한 해 앞 같은 기간 실적과 견준다
    if not fin or not (fin.get("annual") or fin.get("quarter")):
        out["why"] = "네이버 재무 아직 안 받음"
        return out
    oks, bits = [], []
    for name, key in (("매출액", "sales"), ("영업이익", "op")):
        v = y[key]
        if v is None:
            continue
        b, src = _base_part(fin, s, e, name) if part else _base(fin, y["year"], name)
        out["base"][key] = b
        out["from"] = out["from"] or src
        if b is None:
            out["why"] = "기준 실적 못 찾음(%s)" % name
            return out
        oks.append(v > b)
        bits.append("%s %s억 %s %s억" % ("매출" if key == "sales" else "영업이익", _fmt(v), ">" if v > b else "≤", _fmt(b)))
    out["ok"] = all(oks)
    out["why"] = ("%s~%s 전망 " % (y["start"], y["end"]) if part else "%d년 전망 " % y["year"]) + " · ".join(bits) + " (기준 %s)" % out["from"]
    return out


def _fmt(v):
    return "{:,.0f}".format(v) if v is not None else "—"


def _pick(docs):
    """같은 종목 · 같은 갈래 공시 여럿 → 가장 새 것 · 같은 날이면 연결 먼저."""
    docs = sorted(docs, key=lambda d: (d["date"], "연결" in d["title"], d["rcept"]), reverse=True)
    return docs[0] if docs else None


def compute(proxy, days=DAYS_DEFAULT):
    """GET /api/earnings-beat 의 data.

        days     본 날 수(1~31)
        items    [{ code, name, both(True · False · None), earn{rcept, date, title, link} | null, beat{ok, op, consensus, pct, quarter, why},
                    outlook{rcept, date, title, link} | null, guide{ok, year, sales, op, base{sales, op}, from, why} }]
                 ① ② 둘 다 맞은 종목이 위 · 그 안은 가장 새 공시 순 — 값은 억원 · 없음은 null
        counts   { both, beat, guide, noConsensus } · pending: 본문을 아직 안 읽은 공시 수
    """
    if proxy.marketdb.writable():
        _init(proxy)
    days = max(1, min(DAYS_MAX, int(days or DAYS_DEFAULT)))
    since = (_now() - timedelta(days=days - 1)).strftime("%Y%m%d")
    out = {"days": days, "since": since, "items": [], "counts": {"both": 0, "beat": 0, "guide": 0, "noConsensus": 0}, "pending": 0}
    with proxy._db_lock, proxy.db_conn() as conn:
        rows = conn.execute(
            "SELECT rcept_no, stock_code, corp_name, report_nm, rcept_dt FROM dart_disclosures WHERE rcept_dt >= ? "
            "AND stock_code != '' AND (report_nm LIKE ? OR report_nm LIKE ?)",
            (since, "%" + EARN_WORD + "%", "%" + OUTLOOK_WORD + "%")).fetchall()
        try:
            docs = {r[0]: json.loads(r[1]) if r[1] else None for r in conn.execute("SELECT rcept_no, parsed FROM earnings_beat_doc")}
            fins = {r[0]: {"quarter": json.loads(r[1]) if r[1] else None, "annual": json.loads(r[2]) if r[2] else None}
                    for r in conn.execute("SELECT code, quarter, annual FROM earnings_beat_naver")}
        except Exception:            # 표가 아직 없다(8765 가 한 번도 안 받았다)
            docs, fins = {}, {}
    by = {}
    for rno, code, name, nm, dt in rows:
        k = kind_of(nm)
        if not k:
            continue
        if rno not in docs:
            out["pending"] += 1
        g = by.setdefault(code, {"name": name, "earn": [], "outlook": []})
        g[k].append({"rcept": rno, "date": dt, "title": (nm or "").strip(),
                     "link": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + rno})
    for code, g in by.items():
        fin = fins.get(code)
        e, o = _pick(g["earn"]), _pick(g["outlook"])
        beat = judge_beat(docs.get(e["rcept"]), fin) if e else None
        guide = judge_outlook(docs.get(o["rcept"]), fin) if o else None
        b, gd = beat and beat["ok"], guide and guide["ok"]
        both = True if (b and gd) else False if (b is False or gd is False or not e or not o) else None
        it = {"code": code, "name": g["name"], "both": both, "earn": e, "beat": beat, "outlook": o, "guide": guide,
              "_last": max(x["rcept"] for x in g["earn"] + g["outlook"])}
        out["counts"]["both"] += both is True
        out["counts"]["beat"] += bool(b)
        out["counts"]["guide"] += bool(gd)
        out["counts"]["noConsensus"] += bool(beat and beat["ok"] is None and (beat["why"] or "").startswith("예상치 없음"))
        out["items"].append(it)
    out["items"].sort(key=lambda x: (x["both"] is True, x["_last"]), reverse=True)
    for it in out["items"]:
        del it["_last"]
    return out


def status():
    s = dict(_status)
    s["source"] = "공시 뷰어(dart.fss.or.kr) · 네이버 재무(m.stock.naver.com · 비공식)"
    return s
