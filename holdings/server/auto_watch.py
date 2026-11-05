# -*- coding: utf-8 -*-
"""자동 관심종목 — 「전일 거래량 급등」 룰에 걸린 종목을 날마다 센다 (2026-11-05).

재권님 — 「평일 08:00 전일 거래량 급등 종목 자동 추가」 → 착수 안에 「해」 → 「이거 룰을 투자전략에 넣어주고 거기를 고치면
소팅하는게 바뀌게끔」 → 「코스피 200까지」 · 「코스닥도 150개 종목중에서」 · 「코스닥 코스피 둘다 해줘」 → 「만들어봐」(개발 창).

    대상      코스피 시가총액 상위 200 · 코스닥 150 — dart.py 가 날마다 받아 둔 감시 대상 `dart_universe` 를 그대로 읽는다(따로 안 받는다).
              2026-10-06 재권님 「코스피 200 종목 … 코스닥 150 도」 가 「가」 = 지수 구성종목이 아니라 **시가총액 상위** 로 정해진 그 목록이다.
              지수 구성종목 표(`index_members`)는 쓰지 않는다 — 네이버 구성종목 주소가 410(없어진 주소)이라 2026-09-17 뒤로 안 바뀌었다(11-05 12:4x 잼).
              그 목록에는 ETF 도 들어 있어 **주권만 남긴다** — nxt_pre.master_codes()(KIS 종목 마스터 파일 · KIS 호출 아님)에 있는 코드만
    값        평일 15:41~15:59 한 번 — 멀티 시세(intstock-multprice) 시장구분 J 30종목씩(약 12번) · 그날 KRX 종가 · 등락률 · 거래량
              (16:00 시간외 단일가 전 — 그 뒤 J 현재가는 시간외 값으로 움직인다 · nxt_board.py 머리 주석의 실측)
    20일 평균  쌓은 날 값의 앞 20거래일 거래량 평균 — 모자란 종목은 J 일봉(inquire-daily-itemchartprice) 한 번으로 채운다
              (처음 한 번 약 350번 · 그 뒤는 지수에 새로 든 종목만). 등락률도 그 일봉의 앞 종가로 센다
    기준      투자전략 「종목 고르는 룰」 문서 strategy-rules 의 volsurge 칸 — prevPct(앞 거래일 등락률 % 이상) · volMult(20일 평균 몇 배 이상) ·
              sortBy(줄 세우기 'mult' 배수 순 · 'pct' 등락률 순 · 빈칸이면 배수 순) · autoMax(몇 종목까지 · 빈칸이면 다)
              **부를 때마다 문서를 다시 읽어 거르고 줄을 세운다** — 화면에서 칸을 고치면 KIS 를 다시 안 부르고 바로 바뀐다.
              거르는 셈은 여기 한 곳이다(화면은 받은 대로 그린다 · 「같은 값은 한 곳에만 둔다」)
    안 세는 것  sectorPct(미국장 같은 섹터) — 종목 ↔ 미국 섹터 표가 없다(「아직」 이지 「영영」 이 아니다) · exclude(빼는 것) — 글 칸이라 못 셈.
              응답 meta.notCounted 에 적는다
    저장      market.db 의 `auto_watch_day`(날 · 종목 · 지수 · 이름 · 종가 · 등락률 · 거래량 · 어디서)
    주소      GET /api/auto-watch — 모양은 compute() 주석 · 「없음」 은 null(0 아님)
    결과      그날 걸린 종목(compute 의 picked)을 auto_watch_pick 에 남기고(넣기가 꺼져 있어도 · record_picks), 다음 거래일 값을 쌓으면
              그 종목의 다음 날 종가 등락률을 붙여 낸다 — GET /api/auto-watch/history(history()). 셈은 부를 때 auto_watch_day 에서 한다(따로 안 쌓는다).
              (2026-11-05 재권님 「관심종목에 등록된 종목들 다음날 상승인지 하락인지 이거 쌓아놔야 하는데 투자전략에다가 데이터 넣어줘야해」 → 「응 만들어.」)
              다음 날 시가 · 장중 고가는 쌓지 않아 못 센다 — 종가 대비 종가만
    넣기      **그날 값을 쌓은 바로 뒤**(정규장이 끝난 15:41 판) 걸린 종목을 관심 목록(문서 watchlist)과 묶음 「자동」 에 넣는다 — apply_watch()
              (2026-11-05 재권님 「넣는건 정규장이 끝나면 바로 넣는 방향으로 수정해」 · 처음 안은 다음날 08:00 이었다). 쌓아 둔 값을 쓰므로 KIS 0번.
              문서에 `auto: {code: {day, added}}` 를 둔다 — day 넣은 날 · added 이 셈이 하트 목록에 새로 넣었나(원래 하트가 있던 종목은 false).
              KEEP_DAYS 거래일 뒤 「자동」 묶음에서 빼고, added 인 종목은 하트 목록에서도 뺀다 — 단 재권님이 다른 묶음에 담았으면 그때부터 재권님 것(added 를 내림).
              하트를 끈 종목은 auto 에서도 지운다. **added 종목은 알림(dart.watchlist)에서 뺀다** — 날마다 십여 개씩 들어와 알림이 쏟아지지 않게.
              **켜기는 ADD 하나다 — 지금 False**(관심 목록 · 알림이 바뀌는 일이라 켜기는 따로 여쭌다)

8765 만 받는다(`kis_proxy` 가 `is_sender` 로 부른다) · 읽기는 어느 서버든 자기 DB 로. 알림은 없다.
"""

import json
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import dart
import docstore
import nxt_pre
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))

RUN_AT, RUN_UNTIL = (15, 41), (16, 0)
AVG_DAYS = 20                   # 룰 칸 이름이 「20일 평균」 이라 칸으로 안 둔다(바꾸면 투자전략 글도 함께)
BACK_CAL_DAYS = 45              # 일봉 채우기에 묻는 달력 날 — 20거래일 + 앞 종가 하나가 넉넉히 든다
MULTI_MAX = 30
GAP_SEC = 0.15                  # 묶음 사이 쉼 — 예산은 kis_get 이 지키지만 다른 받기에 비켜선다
RULE_DOC, RULE_KEY = "strategy-rules", "volsurge"
SORTS = ("mult", "pct")
ADD = False                     # 정규장 뒤 관심 목록 넣기 — 만들었고 꺼 둠(머리 주석 「넣기」 · 켜기는 재권님 지시로)
WATCH_DOC = "watchlist"
AUTO_GROUP = {"id": dart.AUTO_GROUP_ID, "name": "자동"}
KEEP_DAYS = 5                   # 넣은 날 뒤 이 거래일이 지나면 뺀다(재권님 「5거래일 뒤 자동 것만 빼기」)
TICK = 30
HOLIDAY_SAME = 0.9              # 앞 날과 종가 · 거래량이 똑같은 종목이 이만큼이면 휴장(거래가 있는 날에 우연히 같을 수는 없다)
RETRY_SEC = 300                 # 그날 값을 못 받았을 때 다시 도는 간격 — 창(15:41~16:00) 안에서만
BUSY_RETRY_SEC = 60             # 뜰 때 채우기가 자물쇠를 쥐고 있을 때 바퀴가 다시 보는 간격

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS auto_watch_day (
        day TEXT NOT NULL, code TEXT NOT NULL, idx TEXT, name TEXT,
        close INTEGER, pct REAL, vol INTEGER, src TEXT, saved_at TEXT, PRIMARY KEY (day, code))""",
    "CREATE INDEX IF NOT EXISTS idx_auto_watch_code ON auto_watch_day (code, day DESC)",
    # 그날 룰에 걸린 종목 — 룰 칸을 나중에 고쳐도 「그날 무엇이 걸렸나」 가 안 바뀌게 그때 것을 남긴다(record_picks)
    """CREATE TABLE IF NOT EXISTS auto_watch_pick (
        day TEXT NOT NULL, code TEXT NOT NULL, rank INTEGER, name TEXT, idx TEXT,
        close INTEGER, pct REAL, mult REAL, rule TEXT, saved_at TEXT, PRIMARY KEY (day, code))""",
)

_status = {"runDay": None, "runAt": None, "saved": None, "backfillAt": None, "backfillCodes": None,
           "kisCalls": 0, "error": None}
_run_lock = threading.Lock()


def _now():
    return datetime.now(KST)


def _init(proxy):
    with proxy._db_lock, proxy.db_conn() as conn:
        for q in _SCHEMA:
            conn.execute(q)


_master = {"day": None, "codes": None}


def _stock_codes():
    """주권 코드 집합 — 하루 한 번 마스터 파일. 못 받으면 None(거르지 않고 그대로 — 응답 meta 에 적힌다)."""
    day = _now().strftime("%Y%m%d")
    if _master["day"] != day:
        try:
            _master.update(day=day, codes=set(nxt_pre.master_codes()))
            _status["masterError"] = None
        except Exception as e:
            _master.update(day=day, codes=None)
            _status["masterError"] = safe_message(e, 120)
    return _master["codes"]


def members(proxy):
    """[(code, 시장, name)] — dart 가 쌓은 시가총액 상위(시장 · 순위 안) 중 주권. 표가 없으면 []."""
    try:
        with proxy._db_lock, proxy.db_conn() as conn:
            rows = conn.execute("SELECT stock_code, COALESCE(market, 'KOSPI'), name FROM dart_universe "
                                "ORDER BY COALESCE(market, 'KOSPI'), rank").fetchall()
    except Exception:
        return []
    keep = _stock_codes()
    out = [(r[0], r[1], r[2]) for r in rows if keep is None or r[0] in keep]
    _status["universe"] = {"rows": len(rows), "stocks": len(out), "filtered": keep is not None}
    return out


def _multi_j(proxy, cfg, codes):
    """{code: {close, pct, vol, name}} — 멀티 시세 시장구분 J"""
    out = {}
    for i in range(0, len(codes), MULTI_MAX):
        params = {}
        for n, c in enumerate(codes[i:i + MULTI_MAX], 1):
            params["FID_COND_MRKT_DIV_CODE_%d" % n] = "J"
            params["FID_INPUT_ISCD_%d" % n] = c
        data = proxy.kis_get(cfg, "/uapi/domestic-stock/v1/quotations/intstock-multprice", params, "FHKST11300006")
        _status["kisCalls"] += 1
        for r in (data or {}).get("output") or []:
            code = (r.get("inter_shrn_iscd") or "").strip()
            if code:
                out[code] = {"close": proxy._num(r.get("inter2_prpr"), int), "pct": proxy._num(r.get("prdy_ctrt")),
                             "vol": proxy._num(r.get("acml_vol"), int), "name": (r.get("inter_kor_isnm") or "").strip()}
        time.sleep(GAP_SEC)
    return out


def save_today(proxy, day, codes=None):
    """그날 종가 · 등락률 · 거래량 — 15:41~15:59. 저장한 종목 수. 거래량 합이 0 이면(휴장) 안 쓴다."""
    _init(proxy)
    cfg = proxy.load_secrets()
    mem = members(proxy)
    if codes is not None:
        mem = [m for m in mem if m[0] in codes]
    if not mem:
        _status.update(error="감시 대상 표(dart_universe)가 비었습니다 — dart 가 받은 뒤 다시")
        return None
    got = _multi_j(proxy, cfg, [m[0] for m in mem])
    if not got or all(r["vol"] is None for r in got.values()):   # 「못 받음」(줄은 왔는데 거래량 칸이 다 없음도) — 휴장과 가른다. None 이면 바퀴가 RETRY_SEC 뒤 다시 돈다
        _status.update(error="멀티 시세를 하나도 못 받음 — 다시 돈다")
        return None
    if not sum((r["vol"] or 0) for r in got.values()):
        _status.update(error="받은 거래량 합이 0 — 휴장으로 보고 저장 안 함")
        return 0
    # 평일 휴장(공휴일) — J 멀티가 앞 거래일 값을 그대로 주면 거래량 합이 0 이 아니다(qa 검수 11-05 · 안 잼).
    # 받은 종목 거의 전부의 종가 · 거래량이 앞에 쌓인 날과 같으면 휴장으로 본다
    with proxy._db_lock, proxy.db_conn() as conn:
        last = conn.execute("SELECT MAX(day) FROM auto_watch_day WHERE day < ?", (day,)).fetchone()[0]
        prev = {r[0]: (r[1], r[2]) for r in conn.execute(
            "SELECT code, close, vol FROM auto_watch_day WHERE day = ?", (last,))} if last else {}
    both = [c for c in got if c in prev]
    if both and sum(1 for c in both if (got[c]["close"], got[c]["vol"]) == prev[c]) >= HOLIDAY_SAME * len(both):
        _status.update(error="종가 · 거래량이 %s 와 같음 — 휴장으로 보고 저장 안 함" % last)
        return 0
    stamp = _now().isoformat(timespec="seconds")
    rows = [(day, c, idx, name or got[c]["name"], got[c]["close"], got[c]["pct"], got[c]["vol"], "multi", stamp)
            for c, idx, name in mem if c in got and got[c]["close"]]
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.executemany("INSERT OR REPLACE INTO auto_watch_day (day, code, idx, name, close, pct, vol, src, saved_at) "
                         "VALUES (?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def _history_count(proxy, before):
    """{code: 그 날 앞 쌓인 날 수}"""
    with proxy._db_lock, proxy.db_conn() as conn:
        return {r[0]: r[1] for r in conn.execute(
            "SELECT code, COUNT(*) FROM auto_watch_day WHERE day < ? GROUP BY code", (before,))}


def backfill(proxy, until, codes=None):
    """앞 20거래일이 모자란 종목을 J 일봉 한 번씩으로 채운다. until 날(그날 것은 안 넣음 — 장중 봉은 덜 끝났다). 채운 종목 수."""
    _init(proxy)
    cfg = proxy.load_secrets()
    mem = members(proxy)
    if codes is not None:
        mem = [m for m in mem if m[0] in codes]
    have = _history_count(proxy, until)
    need = [m for m in mem if have.get(m[0], 0) < AVG_DAYS + 1]
    d_to = (datetime.strptime(until, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
    d_from = (datetime.strptime(until, "%Y%m%d") - timedelta(days=BACK_CAL_DAYS)).strftime("%Y%m%d")
    done = 0
    for code, idx, name in need:
        try:
            bars = proxy._bars_once(cfg, code, "D", d_from, d_to, "J")
            _status["kisCalls"] += 1
        except Exception as e:
            _status["error"] = "%s 일봉: %s" % (code, safe_message(e, 120))
            continue
        bars = sorted((b for b in bars if b.get("ts") and b["ts"] < until and b.get("close")), key=lambda b: b["ts"])
        stamp = _now().isoformat(timespec="seconds")
        rows = []
        for i, b in enumerate(bars):
            prev = bars[i - 1]["close"] if i else None
            pct = round((b["close"] - prev) / prev * 100, 2) if prev else None
            rows.append((b["ts"], code, idx, name, b["close"], pct, b.get("volume"), "daily", stamp))
        if rows:
            with proxy._db_lock, proxy.db_conn() as conn:
                # 멀티로 저장한 날은 덮지 않는다 — 그날 KRX 값이 원천이다
                conn.executemany("INSERT OR IGNORE INTO auto_watch_day (day, code, idx, name, close, pct, vol, src, saved_at) "
                                 "VALUES (?,?,?,?,?,?,?,?,?)", rows)
            done += 1
        time.sleep(GAP_SEC)
    _status.update(backfillAt=_now().isoformat(timespec="seconds"), backfillCodes=done)
    return done


def _fill_locked(proxy, day):
    """뜰 때 채우기 — run 과 같은 자물쇠. 이미 돌고 있으면 안 한다."""
    if not _run_lock.acquire(blocking=False):
        return None
    try:
        return backfill(proxy, day)
    except Exception as e:
        _status["error"] = safe_message(e, 160)
    finally:
        _run_lock.release()


def run(proxy, day, codes=None):
    """그날 한 바퀴 — 앞 날 채우기 · 그날 값 저장. 겹쳐 돌지 않는다."""
    if not _run_lock.acquire(blocking=False):
        return None
    try:
        b = backfill(proxy, day, codes)
        n = save_today(proxy, day, codes)
        _status.update(runDay=day, runAt=_now().isoformat(timespec="seconds"), saved=n)
        if n:                        # 저장했으면 앞서 남은 「못 받음」 을 지운다 — meta 를 읽는 쪽이 헷갈리지 않게(qa 덧 11-05)
            _status.update(error=None)
            try:
                record_picks(proxy, day)
            except Exception as e:
                _status["pickError"] = safe_message(e, 160)
            if ADD:
                try:
                    apply_watch(proxy, day)
                except Exception as e:
                    _status["addLast"] = {"day": day, "error": safe_message(e, 160)}
        return {"backfill": b, "saved": n}
    finally:
        _run_lock.release()


def record_picks(proxy, day):
    """그날 걸린 종목을 auto_watch_pick 에 남긴다 — 같은 날 다시 돌면(재시작) 그날 것을 바꿔 쓴다 → 남긴 수 · 룰이 비었으면 None."""
    d = compute(proxy)
    if not d["ready"] or d["day"] != day:
        _status["pickLast"] = {"day": day, "skip": "룰 칸이 비었거나 그날 값이 아님(%s)" % d["day"]}
        return None
    rule = json.dumps(d["rule"], ensure_ascii=False)
    at = _now().isoformat(timespec="seconds")
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute("DELETE FROM auto_watch_pick WHERE day = ?", (day,))
        conn.executemany("INSERT INTO auto_watch_pick VALUES (?,?,?,?,?,?,?,?,?,?)",
                         [(day, p["code"], i + 1, p["name"], p["idx"], p["close"], p["pct"], p["mult"], rule, at)
                          for i, p in enumerate(d["picked"])])
    _status["pickLast"] = {"day": day, "at": at, "picked": len(d["picked"])}
    return len(d["picked"])


def _side(pct):
    return None if pct is None else "up" if pct > 0 else "down" if pct < 0 else "flat"


def history(proxy, days=30):
    """GET /api/auto-watch/history 의 data — 걸린 날마다 종목 · 다음 거래일 결과.

        days     최근 몇 날(걸린 기록이 있는 날 · 1~120)
        list     [{ day, nextDay(다음 거래일 · 아직이면 null), rule, picks: [{ code, name, rank, idx, close, pct, mult,
                    next: { pct, close, side('up' · 'down' · 'flat') } | null, missing }], summary }] — 새 날부터
                 missing  다음 거래일은 왔는데 그 종목 값이 없다(거래정지 · 못 받음) — 「아직」 과 가른다(qa 덧 11-05)
        summary  { picks, done(결과 붙은 수), pending(다음 거래일이 아직 안 옴), missing(왔는데 값 없음), up, down, flat,
                   upRate(%), avgNext(%) } — 비율 · 평균은 done 만으로 · 결과가 없으면 null
        total    모든 날을 합친 summary
    """
    days = int(days)
    if not 1 <= days <= 120:
        raise ValueError("days 는 1~120 정수입니다.")
    with proxy._db_lock, proxy.db_conn() as conn:
        try:
            pick_days = [r[0] for r in conn.execute(
                "SELECT DISTINCT day FROM auto_watch_pick ORDER BY day DESC LIMIT ?", (days,))]
        except Exception:            # 표가 아직 없다
            return {"list": [], "total": _summary([]), "note": "아직 남긴 날 없음 — 8765 가 평일 15:41 판 뒤에 처음 남긴다"}
        trade_days = [r[0] for r in conn.execute("SELECT DISTINCT day FROM auto_watch_day WHERE src = 'multi' ORDER BY day")]
        out, allp = [], []
        for day in pick_days:
            nxt = next((d for d in trade_days if d > day), None)
            rows = conn.execute("SELECT code, name, rank, idx, close, pct, mult, rule FROM auto_watch_pick WHERE day = ? ORDER BY rank",
                                (day,)).fetchall()
            res = {}
            if nxt:
                res = {r[0]: (r[1], r[2]) for r in conn.execute(
                    "SELECT code, pct, close FROM auto_watch_day WHERE day = ? AND src = 'multi'", (nxt,))}
            picks = []
            for code, name, rank, idx, close, pct, mult, rule in rows:
                r = res.get(code)
                nx = {"pct": r[0], "close": r[1], "side": _side(r[0])} if r and r[0] is not None else None
                picks.append({"code": code, "name": name, "rank": rank, "idx": idx, "close": close, "pct": pct, "mult": mult, "next": nx,
                              "missing": bool(nxt) and nx is None})
            allp += picks
            try:
                rl = json.loads(rows[0][7]) if rows else None
            except ValueError:
                rl = None
            out.append({"day": day, "nextDay": nxt, "rule": rl, "picks": picks, "summary": _summary(picks)})
    return {"list": out, "total": _summary(allp)}


def _summary(picks):
    done = [p["next"] for p in picks if p["next"]]
    up = sum(1 for x in done if x["side"] == "up")
    missing = sum(1 for p in picks if p.get("missing"))
    return {"picks": len(picks), "done": len(done), "pending": len(picks) - len(done) - missing, "missing": missing, "up": up,
            "down": sum(1 for x in done if x["side"] == "down"), "flat": sum(1 for x in done if x["side"] == "flat"),
            "upRate": round(up * 100 / len(done), 1) if done else None,
            "avgNext": round(sum(x["pct"] for x in done) / len(done), 2) if done else None}


def _trading_days(proxy):
    """값을 쌓은 날들(오름차순) — 「몇 거래일 지났나」 를 센다."""
    with proxy._db_lock, proxy.db_conn() as conn:
        return [r[0] for r in conn.execute("SELECT DISTINCT day FROM auto_watch_day WHERE src = 'multi' ORDER BY day")]


def merge_watch(doc, picks, day, days):
    """관심 목록 문서 → 새 문서 · 넣은 코드 · 뺀 코드. 문서를 읽고 쓰는 일과 떼어 둬 시험할 수 있게 했다."""
    items = [dict(x) for x in doc.get("items") or [] if isinstance(x, dict) and x.get("code")]
    groups = [dict(g, codes=list(g.get("codes") or [])) for g in doc.get("groups") or [] if isinstance(g, dict) and g.get("id")]
    auto = {c: dict(v) for c, v in (doc.get("auto") or {}).items() if isinstance(v, dict)}
    grp = next((g for g in groups if g["id"] == AUTO_GROUP["id"]), None)
    if grp is None:
        grp = dict(AUTO_GROUP, codes=[])
        groups.append(grp)
    have = {x["code"] for x in items}
    other = {c for g in groups if g["id"] != AUTO_GROUP["id"] for c in g["codes"]}
    added, removed = [], []
    for code in list(auto):
        info = auto[code]
        if code not in have:         # 재권님이 하트를 껐다 — 자동 표시도 지운다
            del auto[code]
            if code in grp["codes"]:
                grp["codes"].remove(code)
            continue
        if info.get("added") and code in other:
            info["added"] = False    # 다른 묶음에 담았다 — 그때부터 재권님 것
        if sum(1 for d in days if info.get("day", "") < d <= day) >= KEEP_DAYS:
            if code in grp["codes"]:
                grp["codes"].remove(code)
            if info.get("added"):
                items = [x for x in items if x["code"] != code]
            del auto[code]
            removed.append(code)
    have = {x["code"] for x in items}
    for p in picks:
        code = p["code"]
        if code in auto:             # 다시 걸렸다 — 넣은 날을 오늘로(5거래일이 다시 시작)
            auto[code]["day"] = day
        else:
            auto[code] = {"day": day, "added": code not in have}
            if code not in have:
                items.append({"code": code, "name": p.get("name") or code})
            added.append(code)
        if code not in grp["codes"]:
            grp["codes"].append(code)
    out = dict(doc, items=items, groups=groups, auto=auto)
    return out, added, removed


def apply_watch(proxy, day):
    """그날 걸린 종목을 관심 목록에 넣고 오래된 자동 것을 뺀다 — 보내는 서버(8765)만 · 그날 값을 쌓은 바로 뒤."""
    d = compute(proxy)
    if not d["ready"] or not d["day"] or d["day"] != day:
        _status["addLast"] = {"day": day, "skip": "룰 칸이 비었거나 그날 값이 아님(%s)" % d["day"]}
        return None
    days = _trading_days(proxy)
    for _ in range(3):               # 그 사이 화면이 썼으면(충돌) 다시 읽어 얹는다
        at = docstore.doc_updated_at(WATCH_DOC)
        doc = docstore.read_doc(WATCH_DOC)
        if not isinstance(doc, dict) or not isinstance(doc.get("items"), list):
            _status["addLast"] = {"day": day, "skip": "관심 목록 문서가 없음 — 화면에서 하트를 한 번 누르면 생긴다"}
            return None
        new, added, removed = merge_watch(doc, d["picked"], day, days)
        try:
            docstore.write_doc(WATCH_DOC, new, if_updated_at=at)
        except docstore.DocConflict:
            continue
        _status["addLast"] = {"day": day, "at": _now().isoformat(timespec="seconds"), "added": added, "removed": removed}
        return _status["addLast"]
    _status["addLast"] = {"day": day, "error": "관심 목록 문서를 세 번 다 남이 먼저 썼음"}
    return None


def rules(proxy):
    """volsurge 칸 — (값 dict, 어디서). 못 읽으면 ({}, '못 읽음: …'). 세션 서버는 보드 상류(8765)에서 읽는다."""
    up = getattr(proxy, "BOARD_UPSTREAM_RAW", "")
    try:
        if up:
            req = urllib.request.Request(up + "/api/board/doc/" + RULE_DOC, headers={"X-KJC-Prio": "low"})
            with urllib.request.urlopen(req, timeout=4) as r:
                data = (json.loads(r.read().decode("utf-8")) or {}).get("data")
            src = "보드 상류"
        else:
            data = docstore.read_doc(RULE_DOC)
            src = "보드 문서"
    except Exception as e:
        return {}, "못 읽음: " + safe_message(e, 100)
    r = ((data or {}).get("rules") or {}).get(RULE_KEY) if isinstance(data, dict) else None
    return (r if isinstance(r, dict) else {}), src


def _num_or_none(v):
    try:
        return None if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return None


def compute(proxy):
    """GET /api/auto-watch 의 data — 쌓인 값을 지금 룰로 거르고 줄 세운다. KIS 를 안 부른다.

        day         셈한 날(가장 최근에 그날 값이 저장된 날) · 없으면 null
        rule        { prevPct, volMult, sortBy, autoMax } — 문서 값 그대로(빈칸 null) · sortBy 는 쓴 값
        ready       기준 둘(prevPct · volMult)이 다 있나
        picked      [{ code, name, idx, close, pct, vol, avg20, mult }] — 걸린 종목 · 줄 세운 차례 · autoMax 로 자름
        pool        대상 종목 수(시가총액 상위 중 주권) · measured: 그날 값과 앞 20거래일이 다 있는 수 · noToday: 그날 값이 없는 수 · short: 그날 값은 있는데 앞 20거래일이 모자란 수
        hitAll      자르기 전 걸린 수
    """
    if proxy.marketdb.writable():
        _init(proxy)                 # 읽기 전용 서버(세션 · 8764)는 8765 가 만든 표를 읽기만 한다
    rule, src = rules(proxy)
    prev_pct, vol_mult = _num_or_none(rule.get("prevPct")), _num_or_none(rule.get("volMult"))
    sort_by = rule.get("sortBy") if rule.get("sortBy") in SORTS else "mult"
    auto_max = _num_or_none(rule.get("autoMax"))
    mem = members(proxy)
    out = {"day": None, "rule": {"prevPct": prev_pct, "volMult": vol_mult, "sortBy": sort_by,
                                 "autoMax": int(auto_max) if auto_max else None, "from": src},
           "ready": prev_pct is not None and vol_mult is not None,
           "picked": [], "pool": len(mem), "measured": None, "noToday": None, "short": None, "hitAll": None}
    with proxy._db_lock, proxy.db_conn() as conn:
        try:
            row = conn.execute("SELECT day FROM auto_watch_day WHERE src = 'multi' GROUP BY day ORDER BY day DESC LIMIT 1").fetchone()
        except Exception:            # 표가 아직 없다(8765 가 한 번도 안 돌았다) — 「없음」 으로 낸다
            row = None
        if not row:
            out["note"] = "아직 쌓인 값 없음 — 8765 가 평일 15:41 에 처음 쌓는다"
            return out
        day = out["day"] = row[0]
        today = {r[0]: r for r in conn.execute(
            "SELECT code, idx, name, close, pct, vol FROM auto_watch_day WHERE day = ?", (day,))}
        hist = {}
        for code, vol in conn.execute(
                "SELECT code, vol FROM auto_watch_day WHERE day < ? AND day >= ? ORDER BY code, day DESC",
                (day, (datetime.strptime(day, "%Y%m%d") - timedelta(days=BACK_CAL_DAYS)).strftime("%Y%m%d"))):
            lst = hist.setdefault(code, [])
            if len(lst) < AVG_DAYS:
                lst.append(vol)
    rows, short, no_today = [], 0, 0
    for code, idx, name in mem:
        t = today.get(code)
        h = [v for v in hist.get(code, []) if v is not None]
        if not t:
            no_today += 1
            continue
        if len(h) < AVG_DAYS:
            short += 1
            continue
        avg = sum(h) / len(h)
        mult = round(t[5] / avg, 2) if avg and t[5] is not None else None
        rows.append({"code": code, "name": name or t[2], "idx": idx, "close": t[3], "pct": t[4], "vol": t[5],
                     "avg20": round(avg), "mult": mult})
    out["measured"], out["noToday"], out["short"] = len(rows), no_today, short
    if not out["ready"]:
        return out
    hit = [r for r in rows if r["pct"] is not None and r["mult"] is not None
           and r["pct"] >= prev_pct and r["mult"] >= vol_mult]
    hit.sort(key=lambda r: (r[sort_by], r["mult" if sort_by == "pct" else "pct"]), reverse=True)
    out["hitAll"] = len(hit)
    out["picked"] = hit[:int(auto_max)] if auto_max and auto_max > 0 else hit
    return out


def status(proxy=None):
    s = dict(_status)
    if proxy is not None and not s.get("runAt"):   # 재시작으로 메모리가 비었으면 DB 의 쌓은 시각(qa 덧 11-05 — 8764 · 재시작 뒤 「셈 시각」 이 빔)
        try:
            with proxy._db_lock, proxy.db_conn() as conn:
                r = conn.execute("SELECT day, MAX(saved_at), COUNT(*) FROM auto_watch_day WHERE src = 'multi' "
                                 "GROUP BY day ORDER BY day DESC LIMIT 1").fetchone()
            if r:
                s.update(runDay=r[0], runAt=r[1], saved=r[2], runFrom="DB")
        except Exception:
            pass
    s["notCounted"] = ["sectorPct — 종목 ↔ 미국 섹터 표가 아직 없음", "exclude — 글 칸이라 못 셈(ETF 는 주권 거르기로 빠짐)"]
    s["add"] = "꺼짐 — 정규장 뒤 관심 목록 넣기는 만들어 두고 꺼 둠" if not ADD else "켜짐 — 그날 값을 쌓은 바로 뒤 관심 목록 · 「자동」 묶음에 넣음"
    s["runWindow"] = "평일 %02d:%02d~%02d:%02d" % (RUN_AT + RUN_UNTIL)
    return s


def start(proxy):
    """보내는 서버가 뜰 때 한 번 — 평일 15:41 바퀴. 뜰 때마다 앞 날이 모자란 종목만 먼저 채운다(다 찼으면 KIS 0번).
    뜰 때 채우기도 _run_lock 안에서 돈다 — 15:41 바퀴와 겹치면 바퀴가 1분 뒤 다시 본다(일봉을 두 번 묻지 않게 · qa 검수 11-05)."""
    def loop():
        time.sleep(60)
        try:
            _init(proxy)
            now = _now()
            with proxy._db_lock, proxy.db_conn() as conn:
                last = conn.execute("SELECT MAX(day) FROM auto_watch_day WHERE src = 'multi'").fetchone()[0]
                have = last and conn.execute("SELECT 1 FROM auto_watch_pick WHERE day = ? LIMIT 1", (last,)).fetchone()
            if last and not have and not (RUN_AT <= (now.hour, now.minute) < RUN_UNTIL and last == now.strftime("%Y%m%d")):
                record_picks(proxy, last)            # 이 코드 전에 쌓은 날 — 그날 룰이 아니라 **지금 룰 칸**으로 셈(그 사이 고쳤으면 다를 수 있다 · qa 덧 11-05) · 바퀴 창 안이면 바퀴가 남긴다
            if members(proxy):
                th = threading.Thread(target=_fill_locked, args=(proxy, now.strftime("%Y%m%d")), daemon=True, name="auto-watch-fill")
                th.start()
        except Exception as e:
            _status["error"] = safe_message(e, 160)
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                if now.weekday() < 5 and RUN_AT <= (now.hour, now.minute) < RUN_UNTIL and _status["runDay"] != day \
                        and time.time() >= (_status.get("retryAt") or 0):
                    _status["runDay"] = day                  # 저장했거나 휴장이면 그날은 한 번
                    try:
                        r = run(proxy, day)
                        if r is None:                        # 뜰 때 채우기가 돌고 있다 — 1분 뒤 다시
                            _status.update(runDay=None, retryAt=time.time() + BUSY_RETRY_SEC)
                        elif r.get("saved") is None:         # 못 받음 — 창 안에서 RETRY_SEC 뒤 다시
                            _status.update(runDay=None, retryAt=time.time() + RETRY_SEC)
                        print("  [자동 관심종목] %s 앞 날 채움 %s종목 · 그날 값 %s종목" % (day, (r or {}).get("backfill"), (r or {}).get("saved")))
                    except Exception as e:
                        _status["error"] = safe_message(e, 160)
                        print("  [자동 관심종목] 실패: %s" % type(e).__name__)
            except Exception:
                pass
            time.sleep(TICK)
    threading.Thread(target=loop, daemon=True, name="auto-watch").start()
    return True
