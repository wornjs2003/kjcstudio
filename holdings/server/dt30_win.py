# -*- coding: utf-8 -*-
"""단타 판 칩별 승률 — 날마다 그날 판의 손익을 쌓고, 칩마다 · 겹침마다 승률을 셈한다 (2026-11-18).

재권님 — 단타 판 칩별 승률(시황분석1 잼 · 작업우선순위 배분 「(나)로」) → 착수 안에 「응」(개발2 창 11-18).

    셈        종목마다 09:01 매수가(rows[].buy) → 14:00 값(rows[].px['1400']) 손익 % — 둘 중 하나라도 없으면 「못 잼」(ret null · 따로 셈)
    쌓기      그날 판이 끝나면(closed · 14:00 칸까지 적힘 · 보통 14:01) 하루 한 줄 — market.db dt30_win(날 · 종목 손익 JSON · 그 판의 저장 시각)
              판이 다시 저장되면(되채움 등 · saved_at 이 바뀜) 그날 줄도 다시 · 남은 판(지난 30거래일)은 서버가 뜬 뒤 처음 바퀴에 채운다 — KIS 안 씀
    이김      손익 % − 수수료 % 가 0 보다 크다. 수수료는 룰 문서 strategy-rules 의 rules.dt30.feePct 한 곳(화면 칸 · 재권님이 넣으심)
              빈칸이면 수수료 없이 셈하고 meta.fee 에 null · meta.feeNote 「빈칸 — 수수료 안 셈」(0 으로 보지 않는다)
              승률은 주소가 부를 때 그때 수수료로 셈한다 — 수수료를 바꾸면 지난 날에도 바로 든다(쌓는 것은 손익뿐)
    칸        칩마다 · 두 칩 겹침 · 세 칩 겹침(rows[].chips 이름 전부 — 셈에 안 드는 현재상승 · 볼린저도) ·
              칩 수별(rows[].n — 단타 셈에 드는 칩 수) · 칩 수별 중 현재상승이 든 것
              각 칸: n(건수 · 못 잼 뺌) · win · winRate(%) · avg · median · over3(손익 BIG_PCT % 넘음) · unmeasured(못 잼)
    위 다섯    날마다 손익 큰 종목 TOP_DAY 개(수수료 뺀 값)
    주소      GET /api/kis/dt30-win?days=30 — 지난 days 거래일(쌓인 날 중 최근)
"""
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from itertools import combinations

import dt30

KST = timezone(timedelta(hours=9))
SELL_AT = "1400"             # 파는 시각 칸(dt30 times 의 끝)
BIG_PCT = 3.0                # 「3% 넘게 오른 수」
TOP_DAY = 5                  # 날마다 이익 큰 종목 수
DAYS_DEFAULT = 30
TICK = 60                    # 끝난 판을 보는 간격(초)
RISE_CHIP = "현재상승"
_SCHEMA = "CREATE TABLE IF NOT EXISTS dt30_win (day TEXT PRIMARY KEY, src_saved TEXT, rows TEXT NOT NULL, at TEXT)"
_status = {"error": None, "filled": 0, "at": None}


def _now():
    return datetime.now(KST)


def day_rows(b):
    """판(dict) → 종목마다 {code · name · chips · n · buy · sell · ret(% · 못 잼이면 None)}."""
    out = []
    for r in b.get("rows") or []:
        buy, sell = r.get("buy"), (r.get("px") or {}).get(SELL_AT)
        ret = round((sell - buy) / buy * 100, 3) if buy and sell is not None else None
        out.append({"code": r.get("code"), "name": r.get("name"), "chips": list(r.get("chips") or []), "n": r.get("n"),
                    "buy": buy, "sell": sell, "ret": ret})
    return out


def fill(proxy):
    """끝난 판 중 아직 안 쌓았거나 다시 저장된 날을 쌓는다 → 쌓은 날 수."""
    n = 0
    with proxy.db_conn() as conn:
        boards = conn.execute("SELECT day, saved_at FROM dt30").fetchall()
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        have = {d: s for d, s in conn.execute("SELECT day, src_saved FROM dt30_win")}
    for day, saved in boards:
        if have.get(day) == saved:
            continue
        got = dt30._load(proxy, day)
        if not got or not got[0].get("closed", True):
            continue                                   # 안 끝난 그날 판 — 14:00 칸을 다 적은 뒤
        rows = day_rows(got[0])
        with proxy._db_lock, proxy.db_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO dt30_win VALUES (?,?,?,?)",
                         (day, got[1], json.dumps(rows, ensure_ascii=False), _now().strftime("%Y-%m-%d %H:%M:%S")))
        n += 1
    with proxy._db_lock, proxy.db_conn() as conn:
        keep = set(d for d, _ in boards)
        gone = [d for (d,) in conn.execute("SELECT day FROM dt30_win") if d not in keep]
        conn.executemany("DELETE FROM dt30_win WHERE day = ?", [(d,) for d in gone])   # 판이 지워진 날(DAYS_KEEP 밖)은 같이
    return n


def fee_pct():
    """수수료 % — 룰 문서 한 곳. 빈칸 · 못 읽음이면 None."""
    try:
        import docstore
        d = docstore.read_doc("strategy-rules") or {}
        d = d.get("data", d) if isinstance(d, dict) else {}
        v = ((d.get("rules") or {}).get("dt30") or {}).get("feePct")
        return None if v is None or v == "" else float(v)
    except Exception:
        return None


def _stat(rets, unmeasured):
    rets = sorted(rets)
    n = len(rets)
    if not n:
        return {"n": 0, "win": 0, "winRate": None, "avg": None, "median": None, "over3": 0, "unmeasured": unmeasured}
    mid = rets[n // 2] if n % 2 else (rets[n // 2 - 1] + rets[n // 2]) / 2
    win = sum(1 for x in rets if x > 0)
    return {"n": n, "win": win, "winRate": round(win / n * 100, 1), "avg": round(sum(rets) / n, 2), "median": round(mid, 2),
            "over3": sum(1 for x in rets if x > BIG_PCT), "unmeasured": unmeasured}


def summary(proxy, days=DAYS_DEFAULT):
    """주소 /api/kis/dt30-win 의 data · meta."""
    fee = fee_pct()
    with proxy.db_conn() as conn:
        try:
            got = conn.execute("SELECT day, rows FROM dt30_win ORDER BY day DESC LIMIT ?", (days,)).fetchall()
        except Exception:
            got = []
    groups = {"chip": {}, "pair": {}, "triple": {}, "count": {}, "countRise": {}}

    def add(kind, key, v):
        g = groups[kind].setdefault(key, [[], 0])
        if v is None:
            g[1] += 1
        else:
            g[0].append(v)

    daily, every = [], []
    for day, raw in got:
        rows = json.loads(raw)
        rets, miss, best = [], 0, []
        for r in rows:
            v = None if r["ret"] is None else round(r["ret"] - (fee or 0), 3)
            chips = sorted(set(r["chips"]))
            for c in chips:
                add("chip", c, v)
            for k, kind in ((2, "pair"), (3, "triple")):
                for combo in combinations(chips, k):
                    add(kind, " + ".join(combo), v)
            if r.get("n") is not None:
                add("count", str(r["n"]), v)
                if RISE_CHIP in chips:
                    add("countRise", str(r["n"]), v)
            if v is None:
                miss += 1
            else:
                rets.append(v)
                every.append(v)
                best.append({"code": r["code"], "name": r["name"], "ret": v, "chips": r["chips"]})
        best.sort(key=lambda x: -x["ret"])
        daily.append(dict(_stat(rets, miss), day=day, top=best[:TOP_DAY]))
    out = {"all": _stat(every, sum(d["unmeasured"] for d in daily)), "days": daily}
    for kind, g in groups.items():
        out[kind] = sorted(({"key": k, **_stat(v[0], v[1])} for k, v in g.items()), key=lambda x: (-x["n"], x["key"]))
    meta = {"days": len(got), "from": got[-1][0] if got else None, "to": got[0][0] if got else None,
            "fee": fee, "feeNote": None if fee is not None else "빈칸 — 수수료 안 셈",
            "buy": "09:01 매수가(rows[].buy)", "sell": SELL_AT, "bigPct": BIG_PCT, "topDay": TOP_DAY,
            "filledAt": _status["at"], "error": _status["error"]}
    return out, meta


def start(proxy):
    """쓰는 서버가 뜰 때 한 번 — 끝난 판을 TICK 마다 본다(처음 바퀴에 남은 판 전부)."""
    if not proxy.marketdb.writable():
        return False

    def loop():
        time.sleep(45)
        while True:
            try:
                n = fill(proxy)
                _status.update(error=None, at=_now().strftime("%H:%M:%S"))
                if n:
                    _status["filled"] += n
                    print("  [단타 승률] %d일 쌓음" % n, flush=True)
            except Exception as e:
                _status["error"] = type(e).__name__
                print("  [단타 승률] 멈춤 — %s" % proxy.safe_message(e, 120), flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="dt30-win").start()
    return True
