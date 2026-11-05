"""지배구조 — 코스피 · 코스닥 상장사마다 OpenDART 사업보고서의 두 표를 받아 쌓는다 (2026-11-05).

재권님(시황분석 창) 「응 이런식으로 해서 우리나라 상장사들 다 찾아서 지배구조 넣어놔」 → 「코스피 코스닥 상장사중에
계열사 최상위는 다 넣어서 이거처럼해줘」 → 받는 안에 「응 그래」(개발1 창 18:1x). 화면은 Insight 종목 분석의
「지배구조」 탭(company-setup/js/gov.js · 시황분석)이 아래 두 주소를 읽는다.

    GET /api/dart/gov?code=<6자리>   data: {code, name, year, rceptNo, major:[최대주주 현황 원문 줄], invest:[타법인 출자 현황 원문 줄]}
                                     안 받았으면 data:null · meta.pending=true — 0 · 빈칸으로 안 메운다
    GET /api/dart/gov/links          data: {edges:[[주주 code, 회사 code, 지분%]], names:{code:name},
                                            heads:{code:[최대주주 이름, 상장사 code|null, 지분%]}}
                                     — gov 의 줄마다 matchedCode(서버가 맞춘 상장사 code · 못 맞추면 null) · 화면은 이름을 맞추지 않는다
                                     meta: {done, total, skipped, fetchedAt}

회사마다 부르는 것(한 회사 = 많아야 4건)
    ① company.json            시장 구분(corp_cls) · 정식 이름 · 주식 이름 — 코스피(Y) · 코스닥(K) 가 아니면 여기서 멈춘다(코넥스 · 기타)
    ② hyslrSttus              최대주주 현황 — 사업보고서(11011) · 지난해부터, 없으면(013) 한 해 앞
    ③ otrCprInvstmntSttus     타법인 출자 현황 — ② 가 찾은 해

받는 때 · 양 — 공시 바퀴(07:00~20:00)가 안 도는 밤에만 · 한 밤(20:00~다음 07:00)에 GOV_NIGHT_CALLS 까지 ·
건마다 GOV_GAP_SEC 쉼 · 시가총액 큰 회사(dart_universe)부터 · 그 뒤 나머지. 하루 쓸 값(dart.DART_DAILY_BUDGET)의
남은 양이 GOV_RESERVE 아래면 멈춘다 — 공시 알림 몫이다. 부르는 것은 전부 dart._dart_get 을 거쳐 하루 셈에 든다.

**켜기는 GOV_FETCH 다 — 기본 꺼짐.** 켜는 것은 재권님 지시로 한다(「켜기」). 꺼져 있어도 두 주소는 쌓인 것을 낸다.
쌓는 것은 공시를 받는 쓰기 서버(8765) 하나 — 읽기 전용 DB 서버(8764 등)는 같은 표를 읽기만 한다.

다시 받기 — 사업보고서는 해에 한 번이라, 받은 해가 지난해보다 앞이면(새 보고서가 나왔을 수 있다) GOV_RETRY_DAYS 뒤 다시 본다.
코넥스 · 기타로 건너뛴 곳도 같은 날수 뒤 다시 본다(시장을 옮길 수 있다).
"""

import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dart
import marketdb
from secrets_guard import safe_message

KST = dart.KST

GOV_FETCH = False            # 켜기 — 재권님 지시로만 True (위 머리말)
GOV_NIGHT_CALLS = 4000       # 한 밤에 이만큼까지(재권님 「응 그래」 · 11-05)
GOV_GAP_SEC = 2.0            # 건마다 쉼
GOV_RESERVE = 2000           # 하루 쓸 값이 이만큼 남으면 멈춘다 — 공시 알림 몫
GOV_RETRY_DAYS = 30          # 받은 해가 지난해보다 앞 · 건너뛴 곳을 다시 볼 날수
GOV_FROM_H, GOV_TO_H = 20, 7  # 밤 — 20:00 부터 다음 날 07:00 앞까지(공시 바퀴 POLL_FROM · POLL_TO 의 밖)
GOV_TICK_SEC = 60            # 받을 때가 아닐 때 다시 보는 간격

MARKETS = ("Y", "K")         # 코스피 · 코스닥 — 코넥스(N) · 기타(E)는 뺀다(재권님 18:0x)
REPORT = "11011"             # 사업보고서
COMMON = ("보통주", "의결권있는주식")     # 띄어쓰기를 빼고 견준다 — 「의결권 있는 주식」 · 「의결권있는 주식」(SK스퀘어) 처럼 회사마다 갈린다(2026-11-05 실측)
SUM = ("계", "합계")

SCHEMA = """CREATE TABLE IF NOT EXISTS dart_gov (
      stock_code   TEXT PRIMARY KEY,
      corp_code    TEXT,
      corp_name    TEXT,            -- dart_corps 이름(짧은 이름)
      corp_cls     TEXT,            -- Y 코스피 · K 코스닥 · N 코넥스 · E 기타
      official     TEXT,            -- company.json corp_name(정식 이름 · 「삼성생명보험(주)」)
      stock_name   TEXT,            -- company.json stock_name
      status       TEXT,            -- ok 받음 · none 사업보고서 없음(두 해 다 013) · skip 코스피 · 코스닥 밖
      year         TEXT,            -- 받은 사업보고서 해 · none · skip 이면 NULL
      rcept_no     TEXT,
      major        TEXT,            -- 최대주주 현황 원문 줄(JSON)
      invest       TEXT,            -- 타법인 출자 현황 원문 줄(JSON)
      fetched_at   TEXT
    )"""

_lock = threading.Lock()         # 한 번에 한 회사만 받는다


class _Stop(Exception):
    """이 바퀴를 멈춘다 — 하루 쓸 값 · 020 · 받기 실패. 그 회사는 적지 않는다(다음에 다시)."""


def _now():
    return datetime.now(KST)


def _night_key(now=None):
    """밤의 이름 — 20:00 부터 다음 날 07:00 까지를 한 밤으로 센다(자정을 넘어도 같은 밤)."""
    now = now or _now()
    day = now - timedelta(days=1) if now.hour < GOV_TO_H else now
    return day.strftime("%Y%m%d")


def _is_night(now=None):
    h = (now or _now()).hour
    return h >= GOV_FROM_H or h < GOV_TO_H


def init():
    with dart._db_lock, dart.db_conn() as conn:
        conn.execute(SCHEMA)


def _rows(sql, args=()):
    """읽기 — 표가 아직 없으면(쌓는 서버가 한 번도 안 돌았다) 빈 목록."""
    try:
        with dart._db_lock, dart.db_conn() as conn:
            return conn.execute(sql, args).fetchall()
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            return []
        raise


# ---------------------------------------------------------------- 밤 셈

def _night_usage():
    try:
        u = json.loads(dart._meta_get("dart_gov_usage") or "null")
    except ValueError:
        u = None
    if not isinstance(u, dict) or u.get("night") != _night_key():
        u = {"night": _night_key(), "calls": 0}
    return u


def _count_call():
    u = _night_usage()
    u["calls"] += 1
    dart._meta_set("dart_gov_usage", json.dumps(u))


def _room():
    """지금 한 회사(많아야 4건)를 받아도 되나 — (된다, 안 되는 까닭)."""
    if _night_usage()["calls"] + 4 > GOV_NIGHT_CALLS:
        return False, "이 밤 몫 %d건을 다 씀" % GOV_NIGHT_CALLS
    left = dart.dart_usage().get("left")
    if left is None:
        return False, "하루 셈을 못 읽음"
    if left - 4 < GOV_RESERVE:
        return False, "하루 쓸 값이 %d건 남음(공시 알림 몫)" % left
    return True, None


# ---------------------------------------------------------------- 받기

def _get(key, path, params):
    """OpenDART 한 번 — (status, json). 020 · 받기 실패는 _Stop."""
    q = dict(params, crtfc_key=key)
    url = dart.DART_API + "/" + path + "?" + urllib.parse.urlencode(q)
    try:
        raw = dart._dart_get(url, 20)
    except dart.DartBudgetExceeded as e:
        raise _Stop(str(e))
    except Exception as e:
        raise _Stop("%s: %s" % (path, safe_message(e, 120)))
    _count_call()
    try:
        d = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        raise _Stop("%s: JSON 이 아님" % path)
    st = str(d.get("status") or "")
    if st == "020":
        dart._note_020()
        raise _Stop("020(하루 한도 초과)")
    if st not in ("000", "013"):                  # 013 = 조회된 자료 없음
        raise _Stop("%s: status %s %s" % (path, st, safe_message(d.get("message") or "", 80)))
    time.sleep(GOV_GAP_SEC)
    return st, d


def fetch_one(key, code, corp_code, name):
    """한 회사를 받아 dart_gov 에 적는다. 적은 status 를 돌려준다. 멈춰야 하면 _Stop."""
    _st, c = _get(key, "company.json", {"corp_code": corp_code})
    cls = c.get("corp_cls")
    row = {"stock_code": code, "corp_code": corp_code, "corp_name": name, "corp_cls": cls,
           "official": c.get("corp_name"), "stock_name": c.get("stock_name"),
           "status": "skip", "year": None, "rcept_no": None, "major": None, "invest": None}
    if cls in MARKETS:
        last = _now().year - 1
        major, year = [], None
        for y in (last, last - 1):
            st, d = _get(key, "hyslrSttus.json", {"corp_code": corp_code, "bsns_year": str(y), "reprt_code": REPORT})
            if st == "000" and d.get("list"):
                major, year = d["list"], str(y)
                break
        invest = []
        if year:
            st, d = _get(key, "otrCprInvstmntSttus.json",
                         {"corp_code": corp_code, "bsns_year": year, "reprt_code": REPORT})
            if st == "000":
                invest = d.get("list") or []
        rcept = next((r.get("rcept_no") for r in major + invest if r.get("rcept_no")), None)
        row.update(status="ok" if year else "none", year=year, rcept_no=rcept,
                   major=json.dumps(major, ensure_ascii=False), invest=json.dumps(invest, ensure_ascii=False))
    row["fetched_at"] = _now().isoformat(timespec="seconds")
    cols = list(row)
    with dart._db_lock, dart.db_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO dart_gov (%s) VALUES (%s)" % (",".join(cols), ",".join("?" * len(cols))),
                     [row[k] for k in cols])
    return row["status"]


def todo():
    """받을 차례 — [(code, corp_code, name)]. 시가총액 큰 회사(dart_universe)부터, 그 뒤 나머지는 코드 순."""
    corps = {r["stock_code"]: (r["corp_code"], r["corp_name"])
             for r in _rows("SELECT stock_code, corp_code, corp_name FROM dart_corps")
             if re.fullmatch(r"\d{6}", r["stock_code"] or "")}
    have = {r["stock_code"]: r for r in _rows("SELECT stock_code, status, year, fetched_at FROM dart_gov")}
    cut = (_now() - timedelta(days=GOV_RETRY_DAYS)).isoformat(timespec="seconds")
    last = str(_now().year - 1)

    def due(code):
        r = have.get(code)
        if r is None:
            return True
        if r["status"] == "ok" and r["year"] == last:
            return False
        return (r["fetched_at"] or "") < cut          # 앞 해 것 · 보고서 없음 · 건너뛴 곳은 날수가 지나면 다시

    try:
        first = [r["stock_code"] for r in dart.universe_rows(None)]
    except Exception:
        first = []
    order = [c for c in first if c in corps] + sorted(c for c in corps if c not in set(first))
    return [(c,) + corps[c] for c in order if due(c)]


def fill(key, limit=None):
    """차례대로 받는다. limit 은 회사 수(시험용). {done, stopped, left}."""
    if not marketdb.writable():
        return {"done": 0, "stopped": "읽기 전용", "left": None}
    init()
    with _lock:
        jobs = todo()
        done, why = 0, None
        for code, corp_code, name in jobs:
            if limit is not None and done >= limit:
                break
            ok, why = _room()
            if not ok:
                break
            try:
                fetch_one(key, code, corp_code, name)
            except _Stop as e:
                why = str(e)
                dart._meta_set("dart_gov_last_error", "%s %s: %s" % (_now().strftime("%m-%d %H:%M"), code, why))
                break
            done += 1
        return {"done": done, "stopped": why, "left": len(jobs) - done}


def start_filler():
    """밤마다 받는 바퀴. GOV_FETCH 가 꺼져 있으면 아무것도 안 띄운다. 공시를 받는 쓰기 서버만 부른다."""
    key = dart.get_key()
    if not (GOV_FETCH and key and marketdb.writable()):
        return False

    def loop():
        time.sleep(30)
        while True:
            try:
                if _is_night() and _room()[0]:
                    r = fill(key)
                    dart._meta_set("dart_gov_fill", json.dumps(dict(r, at=_now().isoformat(timespec="seconds")),
                                                              ensure_ascii=False))
                    if r["done"]:
                        print("  [지배구조] %d곳 받음 · 남음 %s · 멈춤 %s" % (r["done"], r["left"], r["stopped"]))
            except Exception as e:
                print("  [지배구조] 예기치 못한 오류: %s" % type(e).__name__)
            time.sleep(GOV_TICK_SEC)

    threading.Thread(target=loop, daemon=True, name="dart-gov").start()
    return True


# ---------------------------------------------------------------- 내주기

def _key(n):
    """이름 맞추기 — 화면 gov.js 의 key() 와 같은 방식(㈜ · (주) · 주식회사 · 띄어쓰기 뺌)."""
    return re.sub(r"㈜|\(주\)|주식회사|\s", "", str(n or ""))


def _show(n):
    return re.sub(r"(?<=[가-힣]) (?=[가-힣](\s|$))", "", re.sub(r"㈜|\(주\)|\n", "", str(n or ""))).strip()


def _pct(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _loads(s):
    try:
        return json.loads(s or "[]")
    except ValueError:
        return []


_ALL = "SELECT stock_code, corp_name, corp_cls, official, stock_name, status, major, invest, fetched_at FROM dart_gov"


def _matcher(rows):
    """이름 → 상장사 code 를 맞추는 셈 한 곳 — (code_of, alias). links 의 edges · heads 와 gov 의 matchedCode 가 함께 쓴다.
    **화면은 맞추지 않는다** — 받은 code 를 그대로 쓴다(개념정의 검수 · 「같은 값은 한 곳에만」 · 2026-11-05).
    이름은 한글이 들었거나 ㈜ · (주) · 주식회사가 붙은 것만 맞춘다 — 영문 약칭(현대차 해외 법인 「HMM」)이 상장사 HMM 과
    글자가 같아 잘못 이어졌다(시황분석 2026-11-05 시험)."""
    listed = [r for r in rows if r["corp_cls"] in MARKETS]
    alias, index = {}, {}
    # 같은 이름이 둘이면 나중에 고친 쪽 — 대응표에 옛 상장 코드가 남아 있다(삼성물산 000830 · 2017 ↔ 028260 · 2026-11-05 실측)
    for r in _rows("SELECT stock_code, corp_name FROM dart_corps ORDER BY modify_date"):
        if re.fullmatch(r"\d{6}", r["stock_code"] or ""):
            index[_key(r["corp_name"])] = r["stock_code"]
    for r in listed:
        index[_key(r["corp_name"])] = r["stock_code"]              # 받아 보니 코스피 · 코스닥인 쪽이 이긴다
    for r in listed:
        for n in (r["official"], r["stock_name"]):
            if n:
                index[_key(n)] = r["stock_code"]
                if n != r["corp_name"]:
                    alias[n] = r["stock_code"]

    def code_of(n):
        # 영문뿐인 이름은 ㈜ · (주) · 주식회사가 붙었을 때만 — 「SK㈜」(SK스퀘어 최대주주)는 국내 상장사고,
        # 해외 법인 「HMM」 에는 그 표시가 없다(2026-11-05 실측)
        if re.search("[가-힣]", n or "") or re.search(r"㈜|\(주\)|주식회사", n or ""):
            return index.get(_key(n))
        return None

    return code_of, alias


def gov(code):
    """GET /api/dart/gov?code= 의 (data, meta)."""
    r = _rows("SELECT * FROM dart_gov WHERE stock_code = ?", (code,))
    if not r:
        return None, {"pending": True}
    r = r[0]
    meta = {"fetchedAt": r["fetched_at"]}
    if r["status"] == "skip":
        meta["excluded"] = "코스피 · 코스닥 밖(%s)" % (r["corp_cls"] or "?")
        return None, meta
    if r["status"] == "none":
        meta["noReport"] = True              # 두 해 다 사업보고서 최대주주 표가 없다
    code_of, _alias = _matcher(_rows(_ALL))
    major, invest = _loads(r["major"]), _loads(r["invest"])
    for m in major:                          # 서버가 맞춘 상장사 code — 못 맞추면 null(합계 줄 · 사람 · 해외 법인)
        m["matchedCode"] = None if (m.get("nm") or "").strip() in SUM else code_of(m.get("nm"))
    for v in invest:
        v["matchedCode"] = None if (v.get("inv_prm") or "").strip() in SUM else code_of(v.get("inv_prm"))
    return {"code": code, "name": r["corp_name"], "year": r["year"], "rceptNo": r["rcept_no"],
            "major": major, "invest": invest}, meta


def links():
    """GET /api/dart/gov/links 의 (data, meta). 이름 맞추기는 _matcher 한 곳."""
    rows = _rows(_ALL)
    listed = [r for r in rows if r["corp_cls"] in MARKETS]
    names = {r["stock_code"]: r["corp_name"] for r in listed}
    code_of, _alias = _matcher(rows)

    best = {}

    def edge(a, b, p):
        if a and b and a != b and p is not None and best.get((a, b), -1) < p:
            best[(a, b)] = p

    heads = {}
    for r in listed:
        if r["status"] != "ok":
            continue
        me = r["stock_code"]
        major = [m for m in _loads(r["major"]) if re.sub(r"\s", "", m.get("stock_knd") or "") in COMMON and (m.get("nm") or "").strip() not in SUM]
        for m in major:
            edge(code_of(m.get("nm")), me, _pct(m.get("trmend_posesn_stock_qota_rt")))
        for v in _loads(r["invest"]):
            if (v.get("inv_prm") or "").strip() not in SUM:
                edge(me, code_of(v.get("inv_prm")), _pct(v.get("trmend_blce_qota_rt")))
        own = [m for m in major if re.search(r"본인|^최대주주$", (m.get("relate") or "").strip())] or major
        if own:
            top = max(own, key=lambda m: _pct(m.get("trmend_posesn_stock_qota_rt")) or -1)
            heads[me] = [_show(top.get("nm")), code_of(top.get("nm")), _pct(top.get("trmend_posesn_stock_qota_rt"))]

    edges = [[a, b, p] for (a, b), p in sorted(best.items())]
    groups = _groups(heads, names)
    corp = {r["stock_code"]: r["corp_name"] for r in _rows("SELECT stock_code, corp_name FROM dart_corps")}
    for a, b, _p in edges:
        for c in (a, b):
            names.setdefault(c, corp.get(c, c))
    total = sum(1 for _ in todo_all())
    meta = {"done": sum(1 for r in rows if r["corp_cls"] in MARKETS or r["status"] == "skip"),
            "total": total,
            "listed": len(listed), "skipped": sum(1 for r in rows if r["status"] == "skip"),
            "fetchedAt": max((r["fetched_at"] or "" for r in rows), default=None) or None,
            "fetching": GOV_FETCH}
    return {"edges": edges, "names": names, "heads": heads, "groups": groups}, meta


def _groups(heads, names):
    """그룹 — 회사마다 최대주주를 위로 끝까지 따라가, 맨 위가 같은 상장사끼리 묶는다 (2026-11-05 재권님
    「sk 는 지분관계가 복잡한데 모회사와 자회사만 있어서 … 하이닉스도 sk계열사중에 하난데 모회사처럼 해줘서」 → 「응」).

        top       맨 위 — 최대주주가 상장사가 아닌 곳(사람 · 비상장 법인)의 이름. 서로 물린 고리면 None
        holding   맨 위 바로 아래 상장사(지주사 자리) · 고리면 고리의 첫 회사
        cycle     서로 물린 고리의 상장사들(현대차 → 현대모비스 → 기아 → 현대차) · 없으면 []
        members   [{code, parent(최대주주 상장사 code · 맨 위 아래면 None), pct, depth(holding 이 0)}] — 깊이 · 지분 순

    **그룹 이름을 짐작해 붙이지 않는다** — 맨 위 이름 그대로다(gov.js 머리와 같은 뜻). 공정위 기업집단 명단과 다를 수 있다 —
    최대주주가 다른 친족 쪽(SK디스커버리 · 최창원)은 따로 묶인다. 최대주주를 아직 안 받은 회사에서 줄이 끊기면 거기가 맨 위가 된다.
    상장사가 둘 이상인 그룹만 낸다."""
    def up(c):
        path = [c]
        while True:
            h = heads.get(path[-1])
            nxt = h[1] if h else None
            if not nxt or nxt not in heads and nxt not in names:
                return path, (h[0] if h else None), []
            if nxt in path:
                i = path.index(nxt)
                return path, None, path[i:]
            if nxt not in heads:                  # 상장사인데 아직 안 받음 — 그 회사가 맨 위
                return path + [nxt], names.get(nxt, nxt), []
            path.append(nxt)

    by = {}
    for c in heads:
        path, top, cyc = up(c)
        key = ("cycle", tuple(sorted(cyc))) if cyc else ("top", top, path[-1])
        g = by.setdefault(key, {"top": top, "holding": (sorted(cyc)[0] if cyc else path[-1]),
                                "cycle": sorted(cyc), "members": {}})
        for i, x in enumerate(path):
            if x in g["members"]:
                continue
            h = heads.get(x)
            parent = path[i + 1] if i + 1 < len(path) else None
            if x in cyc:
                parent = h[1] if h else None
            g["members"][x] = {"code": x, "parent": parent, "pct": h[2] if h else None}
    out = []
    for g in by.values():
        m = g["members"]
        def depth(x, seen=()):
            p = m[x]["parent"]
            return 0 if not p or p not in m or p in seen or x in g["cycle"] else 1 + depth(p, seen + (x,))
        mem = sorted(({**v, "depth": depth(k)} for k, v in m.items()), key=lambda v: (v["depth"], -(v["pct"] or 0)))
        if len(mem) >= 2:
            out.append({"top": g["top"], "holding": g["holding"], "cycle": g["cycle"], "members": mem})
    out.sort(key=lambda g: -len(g["members"]))
    return out


def todo_all():
    return (r for r in _rows("SELECT stock_code FROM dart_corps") if re.fullmatch(r"\d{6}", r["stock_code"] or ""))


if __name__ == "__main__":
    # 시험 — 이 폴더 DB 에 몇 회사만 받는다(켜기 스위치와 무관 · 밤 몫 · 하루 몫은 그대로 센다)
    #   python3 holdings/server/dart_gov.py --once 5
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", type=int, default=3)
    a = ap.parse_args()
    k = dart.get_key()
    if not k:
        print("OpenDART 인증키가 없습니다")
        sys.exit(2)
    dart.db_init()
    print(json.dumps(fill(k, a.once), ensure_ascii=False))
