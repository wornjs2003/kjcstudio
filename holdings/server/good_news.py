# -*- coding: utf-8 -*-
"""「좋은 뉴스」 판정 — 투자전략 재료 줄의 「좋은 뉴스」 를 공시마다 셈한다 (2026-11-05).

재권님 — 작업우선순위 배분(13:5x 「응」) → 착수 안 「응 올려줘」 → 만드는 안 「응 해줘」(개발 창).
근거는 시황분석 카드 「어떤 종목을 사서 할지 룰 시안」 — 공시 한 건마다 여섯 칸을 보고, 「이미 오름」 을 함께 낸다.

    여섯 칸    그 종목 이야기 · 오르는 쪽 갈래 · 처음 소식 · 방향 위 · 크기 · 공시로 확정
               공시는 그 회사가 낸 것이라 「그 종목 이야기」 · 「공시로 확정」 은 늘 맞음이다(뉴스 기사를 붙일 때 갈린다).
               「처음 소식」 은 정정 공시가 아닌가로만 본다 — 정정은 판정하지 않는다
    갈래 · 방향  holdings/data/disclosure-tags.json 의 「방향」 줄 한 곳(공시 제목의 낱말로 가른다 · 위에서 먼저 걸린 것 하나)
    크기       공급계약 — 공시 본문(OpenDART document.xml)의 「매출액 대비(%)」 칸을 그대로 읽는다(11-05 15:18 잼 · 동성화인텍 25.9)
    목적       자사주 취득 — OpenDART 자기주식 취득 결정 상세(tsstkAqDecsn)의 취득목적(aq_pp) 글을 낱말로 가른다
               가르는 낱말은 갈래 파일 「자사주 취득」 항목의 목적위 · 목적밖 한 곳 — 위만 → 위 / 밖만 → 판정 밖 / 둘 다 · 아무것도 → 못 가름
    이미 오름   공시 날 앞 마지막 거래일 종가 ÷ 그보다 newsPreDays 거래일 앞 종가 − 1 (%) — 자동 관심종목이 쌓는 J 종가(auto_watch_day),
               없으면 차트 일봉(candles D · 통합). 판정에는 안 쓰고 값만 낸다(기준 칸이 아직 없다)
    기준       투자전략 문서 strategy-rules 의 volsurge 칸 — newsPreDays(정수) · newsMinSizePct(0 이상). 빈칸이면 「기준 없음」(0 으로 안 메운다)
    판정       맞음 · 아님 · 못 가름 · 판정 밖 + 까닭 한 줄 — 크기 기준(newsMinSizePct)이 빈칸이면 크기를 견주지 않았으니 「못 가름」(맞음 아님 · 개념정의 검수 11-05)

    받기       8765(보내는 서버)만 OpenDART 를 부른다 — 5분마다 최근 FETCH_DAYS 날의 공급계약 · 자사주 공시 중 아직 안 받은 것을
               한 바퀴 FETCH_MAX 건까지. 한 건에 한 번 받아 market.db 의 good_news_detail 에 둔다(하루 쓸 값은 dart._dart_get 이 센다).
               잠깐 실패(transient)는 RETRY_BASE_SEC 부터 두 배씩 늘려 RETRY_MAX 번까지 다시 받고, 404 · 400 같은 답과 그 밖 오류는 바로 굳는다
               다른 서버는 쌓인 것을 읽기만 한다 — 아직 안 받은 것은 「못 가름 · 상세 아직 안 받음」
    주소       GET /api/good-news?days=7&code=005930 — 모양은 compute() 주석 · 「없음」 은 null(0 아님) · 알림은 없다
"""
import io
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import zipfile
from datetime import datetime, timedelta, timezone

import auto_watch
import dart
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))
TAGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "disclosure-tags.json")
DAYS_DEFAULT = 7
DAYS_MAX = 31
FETCH_DAYS = 31                 # 받기가 거슬러 보는 날 — 응답의 days 최대와 같게
FETCH_MAX = 30                  # 한 바퀴에 받는 건수 — 하루 공급계약 · 자사주가 스무 건 안팎(10-06~11-05 셈)
TICK = 300
GAP_SEC = 0.3
PRE_LOOK_CAL_DAYS = 120         # 「이미 오름」 종가를 찾는 달력 날
RETRY_MAX = 5                   # 잠깐 실패(연결 끊김 · 시간 넘김 · 429 · 5xx)를 몇 번까지 다시 받나 — 넘으면 「못 가름」 으로 굳는다
RETRY_BASE_SEC = 600            # 첫 다시 받기까지 — 그 뒤 실패마다 두 배(10 · 20 · 40 · 80분)


_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS good_news_detail (
        rcept_no TEXT PRIMARY KEY, kind TEXT, size_pct REAL, purpose TEXT, error TEXT, fetched_at TEXT)""",
)
_ADD_COLS = ("tries INTEGER DEFAULT 0", "retry_at TEXT")   # 11-05 덧 — 처음 판 표에 붙인다(retry_at 이 있으면 그 시각 뒤 다시 받는다 · null 이면 굳음)
_status = {"fetchAt": None, "fetched": None, "pending": None, "error": None, "dartCalls": 0}
_lock = threading.Lock()


def _now():
    return datetime.now(KST)


def _flat(s):
    return re.sub(r"[\sㆍ·・()\[\]]", "", s or "")


def _init(proxy):
    with proxy._db_lock, proxy.db_conn() as conn:
        for q in _SCHEMA:
            conn.execute(q)
        have = {r[1] for r in conn.execute("PRAGMA table_info(good_news_detail)")}
        for col in _ADD_COLS:
            if col.split()[0] not in have:
                conn.execute("ALTER TABLE good_news_detail ADD COLUMN " + col)


_tags = {"mtime": None, "rows": []}


def lanes():
    """disclosure-tags.json 의 「방향」 줄 — 파일이 바뀌면 다시 읽는다."""
    m = os.path.getmtime(TAGS)
    if _tags["mtime"] != m:
        with open(TAGS, encoding="utf-8") as f:
            rows = json.load(f).get("방향") or []
        _tags.update(mtime=m, rows=[dict(r, _말=[_flat(w) for w in r.get("말") or []]) for r in rows])
    return _tags["rows"]


def lane_of(report_nm):
    t = _flat(report_nm)
    for r in lanes():
        if any(w and w in t for w in r["_말"]):
            return r
    return None


def is_corrected(report_nm):
    return "정정" in (report_nm or "")


# ---------------------------------------------------------------- 상세 받기 (보내는 서버만)

def _doc_text(key, rno):
    raw = dart._dart_get(dart.DART_API + "/document.xml?" + urllib.parse.urlencode({"crtfc_key": key, "rcept_no": rno}), 40)
    _status["dartCalls"] += 1
    if raw[:2] != b"PK":
        raise ValueError("본문이 zip 이 아님: " + raw[:80].decode("utf-8", "replace"))
    z = zipfile.ZipFile(io.BytesIO(raw))
    x = z.read(z.namelist()[0]).decode("utf-8", "replace")
    x = re.sub(r"<style.*?</style>", " ", x, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x))


def size_from_text(t):
    """「매출액 대비(%) 25.9」 → 25.9 · 칸이 없거나 「-」 면 None."""
    m = re.search(r"매출액\s*대비\s*\(\s*%\s*\)\s*([\-0-9.,]+)", t)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _purpose(key, rno, corp_code, rcept_dt):
    raw = dart._dart_get(dart.DART_API + "/tsstkAqDecsn.json?" + urllib.parse.urlencode(
        {"crtfc_key": key, "corp_code": corp_code, "bgn_de": rcept_dt, "end_de": rcept_dt}), 20)
    _status["dartCalls"] += 1
    j = json.loads(raw.decode("utf-8", "replace"))
    if j.get("status") != "000":
        raise ValueError("자기주식 취득 결정 상세 %s %s" % (j.get("status"), j.get("message")))
    lst = j.get("list") or []
    for it in lst:
        if it.get("rcept_no") == rno:
            return it.get("aq_pp") or ""
    if len(lst) == 1:                # 정정본이 나오면 상세는 정정본 접수번호만 준다(11-05 매커스 000118 → 000183 잼) — 그날 그 회사 것이 하나면 그것
        return lst[0].get("aq_pp") or ""
    raise ValueError("상세에 그 접수번호 없음(그날 그 회사 상세 %d건)" % len(lst))


def purpose_side(p, ln):
    """취득목적 글 → '위' · '밖' · None(못 가름). 낱말은 갈래 파일의 목적위 · 목적밖(없으면 못 가름)."""
    t = _flat(p)
    up = any(_flat(w) in t for w in ln.get("목적위") or [])
    out = any(_flat(w) in t for w in ln.get("목적밖") or [])
    return "위" if up and not out else "밖" if out and not up else None


def transient(e):
    """다시 물으면 될 수 있는 실패인가 — 연결 끊김 · 시간 넘김 · 429(너무 잦음) · 5xx. 404 · 400 같은 답은 다시 물어도 같아 아니다."""
    if isinstance(e, urllib.error.HTTPError):
        return e.code == 429 or e.code >= 500
    return isinstance(e, OSError)


def _todo(proxy, since):
    with proxy._db_lock, proxy.db_conn() as conn:
        rows = conn.execute(
            "SELECT d.rcept_no, d.corp_code, d.report_nm, d.rcept_dt, COALESCE(g.tries, 0) FROM dart_disclosures d "
            "LEFT JOIN good_news_detail g ON g.rcept_no = d.rcept_no "
            "WHERE d.rcept_dt >= ? AND (g.rcept_no IS NULL OR (g.retry_at IS NOT NULL AND g.retry_at <= ?)) "
            "ORDER BY d.rcept_no DESC", (since, _now().isoformat(timespec="seconds"))).fetchall()
    out = []
    for rno, cc, nm, dt, tries in rows:
        if is_corrected(nm):
            continue
        ln = lane_of(nm)
        if ln and (ln.get("크기") or ln.get("목적")):
            out.append((rno, cc, dt, ln, tries))
    return out


def fetch_round(proxy):
    """아직 안 받은 상세를 FETCH_MAX 건까지 받는다 → 받은 수 · 바쁘면 None."""
    if not _lock.acquire(blocking=False):
        return None
    try:
        key = dart.get_key()
        if not key:
            _status["error"] = "OpenDART 키 없음"
            return 0
        _init(proxy)
        _status["error"] = None      # 지난 바퀴 오류는 이 바퀴가 다시 적는다
        todo = _todo(proxy, (_now() - timedelta(days=FETCH_DAYS)).strftime("%Y%m%d"))
        got = 0
        for rno, cc, dt, ln, tries in todo[:FETCH_MAX]:
            size = purpose = err = retry_at = None
            try:
                if ln.get("크기") == "매출액대비":
                    size = size_from_text(_doc_text(key, rno))
                    if size is None:
                        err = "본문에 「매출액 대비(%)」 칸 없음"
                if ln.get("목적") == "자사주목적":
                    purpose = _purpose(key, rno, cc, dt)
            except dart.DartBudgetExceeded as e:
                _status["error"] = safe_message(e, 120)
                break
            except Exception as e:
                err = safe_message(e, 160)
                if transient(e):     # 잠깐 실패 — 간격을 두 배씩 늘려 RETRY_MAX 번까지 다시 · 그 뒤 굳음
                    tries += 1
                    if tries < RETRY_MAX:
                        retry_at = _now() + timedelta(seconds=RETRY_BASE_SEC * 2 ** (tries - 1))
                        err = "잠깐 실패 %d번째 · %s 에 다시: %s" % (tries, retry_at.strftime("%H:%M"), err)
                        retry_at = retry_at.isoformat(timespec="seconds")
                    else:
                        err = "잠깐 실패 %d번 — 더 안 받음: %s" % (tries, err)
                    _status["error"] = err
            with proxy._db_lock, proxy.db_conn() as conn:
                conn.execute("INSERT OR REPLACE INTO good_news_detail (rcept_no, kind, size_pct, purpose, error, fetched_at, tries, retry_at) "
                             "VALUES (?,?,?,?,?,?,?,?)",
                             (rno, ln["갈래"], size, purpose, err, _now().isoformat(timespec="seconds"), tries, retry_at))
            got += 1
            time.sleep(GAP_SEC)
        _status.update(fetchAt=_now().isoformat(timespec="seconds"), fetched=got, pending=max(0, len(todo) - got))
        return got
    finally:
        _lock.release()


def start(proxy):
    def loop():
        time.sleep(90)
        while True:
            try:
                fetch_round(proxy)
            except Exception as e:
                _status["error"] = safe_message(e, 160)
            time.sleep(TICK)
    threading.Thread(target=loop, name="good-news", daemon=True).start()
    return True


# ---------------------------------------------------------------- 셈

def _int_or_none(v):
    f = auto_watch._num_or_none(v)
    return int(f) if f is not None and f >= 1 and f == int(f) else None


def _closes(conn, code, before):
    """before(YYYYMMDD) 앞 거래일 종가들(새 것부터) · 어디서."""
    lo = (datetime.strptime(before, "%Y%m%d") - timedelta(days=PRE_LOOK_CAL_DAYS)).strftime("%Y%m%d")
    try:
        rows = conn.execute("SELECT day, close FROM auto_watch_day WHERE code = ? AND day < ? AND day >= ? "
                            "AND close IS NOT NULL ORDER BY day DESC", (code, before, lo)).fetchall()
    except Exception:
        rows = []
    if rows:
        return rows, "J 종가(자동 관심종목)"
    rows = conn.execute("SELECT ts, close FROM candles WHERE code = ? AND period = 'D' AND ts < ? AND ts >= ? "
                        "AND close IS NOT NULL ORDER BY ts DESC", (code, before, lo)).fetchall()
    return rows, ("일봉(통합)" if rows else None)


def pre_up(conn, code, rcept_dt, n):
    if not n or not code:
        return None
    rows, src = _closes(conn, code, rcept_dt)
    if len(rows) <= n:
        return {"pct": None, "from": src, "why": "앞 %d거래일 종가가 모자람(%d)" % (n, len(rows))}
    (d1, c1), (d0, c0) = rows[0], rows[n]
    return {"pct": round((c1 / c0 - 1) * 100, 2) if c0 else None, "from": src, "base": d0, "last": d1}


def judge(row, ln, det, min_size):
    """→ (판정, 까닭, 여섯 칸). 칸 값: True · False · None(못 셈) · '해당 없음'."""
    nm = row["title"]
    first = not is_corrected(nm)
    up = ln["방향"] == "위"
    chk = {"about": True, "upLane": up, "first": first, "dirUp": up, "size": "해당 없음", "confirmed": True}
    if not first:
        return "판정 밖", "정정 공시 — 판정 안 함", chk
    if ln["방향"] == "밖":
        return "판정 밖", "%s — %s" % (ln["갈래"], ln.get("뜻") or "판정하지 않는 갈래"), chk
    if ln["방향"] == "아래":
        return "아님", "%s — 내리는 쪽 갈래" % ln["갈래"], chk
    if ln["방향"] == "갈림":
        chk["dirUp"] = None
        return "못 가름", "%s — 숫자를 봐야 위아래가 갈림(셈 아직 없음)" % ln["갈래"], chk
    need = ln.get("크기") or ln.get("목적")
    if need and det is None:
        chk["dirUp" if ln.get("목적") else "size"] = None
        return "못 가름", "상세 아직 안 받음(8765 가 5분마다 받는다)", chk
    if ln.get("목적"):
        side = purpose_side(det["purpose"], ln) if det["purpose"] is not None else None
        if side == "밖":
            chk["upLane"] = chk["dirUp"] = False
            return "판정 밖", "취득 목적이 임직원 보상 쪽 — 「%s」" % det["purpose"], chk
        if side is None:
            chk["dirUp"] = None
            return "못 가름", "취득 목적 못 가름 — %s" % ("「%s」" % det["purpose"] if det["purpose"] else (det["error"] or "글 없음")), chk
    if ln.get("크기"):
        size = det["size_pct"]
        if size is None:
            chk["size"] = None
            return "못 가름", "크기 못 읽음 — %s" % (det["error"] or "칸 없음"), chk
        if min_size is None:
            chk["size"] = None
            return "못 가름", "크기 기준 없음(newsMinSizePct 빈칸) · 매출액 대비 %.1f%%" % size, chk
        chk["size"] = size >= min_size
        if not chk["size"]:
            return "아님", "매출액 대비 %.1f%% < 기준 %g%%" % (size, min_size), chk
        return "맞음", "%s · 매출액 대비 %.1f%% ≥ %g%%" % (ln["갈래"], size, min_size), chk
    return "맞음", ln["갈래"] + (" · 목적 「%s」" % det["purpose"] if det and det.get("purpose") else ""), chk


def compute(proxy, days=DAYS_DEFAULT, code=None):
    """GET /api/good-news 의 data.

        days        본 날 수(1~31) · code: 한 종목만(없으면 전부)
        rule        { newsPreDays, newsMinSizePct, from } — 빈칸 null
        items       [{ rcept, code, name, title, date, link, lane, dir, sizePct, purpose, preUp{pct, from, base, last | why},
                       checks{about, upLane, first, dirUp, size, confirmed}, verdict, why }] — 새 공시부터
                    갈래에 안 걸린 공시는 빠진다(noLane 에 수만)
        counts      { 맞음, 아님, 못 가름, 판정 밖 } · noLane · detailMissing: 상세가 필요한데 아직 없는 수
    """
    if proxy.marketdb.writable():
        _init(proxy)
    days = max(1, min(DAYS_MAX, int(days or DAYS_DEFAULT)))
    rule, src = auto_watch.rules(proxy)
    n = _int_or_none(rule.get("newsPreDays"))
    min_size = auto_watch._num_or_none(rule.get("newsMinSizePct"))
    if min_size is not None and min_size < 0:
        min_size = None
    since = (_now() - timedelta(days=days - 1)).strftime("%Y%m%d")
    out = {"days": days, "since": since, "rule": {"newsPreDays": n, "newsMinSizePct": min_size, "from": src},
           "items": [], "counts": {"맞음": 0, "아님": 0, "못 가름": 0, "판정 밖": 0}, "noLane": 0, "detailMissing": 0}
    q = "SELECT rcept_no, stock_code, corp_name, report_nm, rcept_dt FROM dart_disclosures WHERE rcept_dt >= ?"
    args = [since]
    if code:
        q += " AND stock_code = ?"
        args.append(code)
    with proxy._db_lock, proxy.db_conn() as conn:
        rows = conn.execute(q + " ORDER BY rcept_no DESC", args).fetchall()
        try:
            dets = {r[0]: {"size_pct": r[1], "purpose": r[2], "error": r[3]} for r in conn.execute(
                "SELECT rcept_no, size_pct, purpose, error FROM good_news_detail WHERE rcept_no IN (%s)"
                % ",".join("?" * len(rows)), [r[0] for r in rows])} if rows else {}
        except Exception:            # 표가 아직 없다(8765 가 한 번도 안 받았다)
            dets = {}
        for rno, sc, name, nm, dt in rows:
            ln = lane_of(nm)
            if not ln:
                out["noLane"] += 1
                continue
            det = dets.get(rno)
            item = {"rcept": rno, "code": sc, "name": name, "title": (nm or "").strip(), "date": dt,
                    "link": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + rno,
                    "lane": ln["갈래"], "dir": ln["방향"],
                    "sizePct": det["size_pct"] if det else None, "purpose": det["purpose"] if det else None,
                    "preUp": pre_up(conn, sc, dt, n) if n else {"pct": None, "why": "기준 없음(newsPreDays 빈칸)"}}
            if (ln.get("크기") or ln.get("목적")) and det is None and not is_corrected(nm):
                out["detailMissing"] += 1
            item["verdict"], item["why"], item["checks"] = judge(item, ln, det, min_size)
            out["counts"][item["verdict"]] += 1
            out["items"].append(item)
    return out


def status():
    s = dict(_status)
    s["lanes"] = TAGS.split("holdings/")[-1] + " 의 「방향」"
    s["notCounted"] = ["갈림 갈래(잠정실적 · 손익구조 · 감사보고서) — 숫자 셈 아직", "이미 오름 — 값만 냄(기준 칸 없음)", "뉴스 기사 — 공시만 셈"]
    return s
