# -*- coding: utf-8 -*-
"""단타 판 칩별 승률 — 날마다 그날 판의 손익을 쌓고, 칩마다 · 겹침마다 승률을 셈한다 (2026-11-18).

재권님 — 단타 판 칩별 승률(시황분석1 잼 · 작업우선순위 배분 「(나)로」) → 착수 안에 「응」(개발2 창 11-18).

    셈        종목마다 판 매수가(rows[].buy · 판에 든 때 값 — meta 「buy」 설명) → 14:00 값(rows[].px['1400']) 손익 % — 둘 중 하나라도 없으면 「못 잼」(ret null · 따로 셈)
    쌓기      그날 판이 끝나면(closed · 14:00 칸까지 적힘 · 보통 14:01) 하루 한 줄 — market.db dt30_win(날 · 종목 손익 JSON · 그 판의 저장 시각)
              판이 다시 저장되면(되채움 등 · saved_at 이 바뀜) 그날 줄도 다시 · 남은 판(지난 30거래일)은 서버가 뜬 뒤 처음 바퀴에 채운다 — KIS 안 씀
    이김      세후 손익이 0 보다 크다 — 화면(strategy-dt30.js calc)과 같은 셈(개념정의 검수 11-18):
              세후 % = (판 값 − 산 값 − 판 값 × (거래세 + 농특세 + 수수료)) ÷ 산 값 × 100 · 세금 · 수수료 둘 다 팔 때만(재권님 「증권수수료는 팔때만」 11-18)
              세율은 아래 TAX(시장마다) — **화면 TAX 와 두 곳이다**(화면이 meta.tax 를 읽으면 한 곳) · 시장을 모르면 세금을 못 셈 → 「못 잼」
              수수료는 룰 문서 strategy-rules 의 rules.dt30.feePct 한 곳(화면 칸 · 재권님이 넣으심)
              빈칸이면 수수료 없이 셈하고 meta.fee 에 null · meta.feeNote 「빈칸 — 수수료 안 셈」(0 으로 보지 않는다)
              승률은 주소가 부를 때 그때 수수료로 셈한다 — 수수료를 바꾸면 지난 날에도 바로 든다(쌓는 것은 손익뿐)
    칩 이름   11-18 전 판의 「수급」(자동 관심 종목)은 「관심」 으로 이어 세고 하트 「관심」 은 뺀다(하트로만 든 종목은 줄째 뺌) — 재권님 「전 하트 관심은 삭제」(11-18)
    문턱      칩 둘 이상(dt30.MIN_CHIPS) 종목만 센다 — 지난 판(하나 이상으로 지은 판)도 같게 · 판 자체는 그대로 둔다(재권님 「응」 11-18 17:5x)
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
TAX = {"KOSPI": {"tx": 0.05, "rural": 0.15}, "KOSDAQ": {"tx": 0.20, "rural": 0.0}}   # % · 2026 세율 — 화면 strategy-dt30.js TAX 와 같은 값(두 곳)
VER = "v4"                   # 쌓는 줄 모양이 바뀌면 올린다 — 옛 줄을 다시 쌓는다(v2 · 시장 칸 · v3 · 11-18 전 판 칩 이름 옮김 · v4 · 칩 둘 이상만)
_SCHEMA = "CREATE TABLE IF NOT EXISTS dt30_win (day TEXT PRIMARY KEY, src_saved TEXT, rows TEXT NOT NULL, at TEXT)"
_status = {"error": None, "filled": 0, "at": None}


def _now():
    return datetime.now(KST)


def _chips_now_rule(b, r):
    """11-18 전 판(meta.watchRule 이 「자동」 이 아님)의 칩을 지금 이름으로 — 「수급」(자동 관심 종목)은 「관심」 으로 이어 세고
    하트 「관심」 은 뺀다 — 재권님 「전 하트 관심은 삭제」(11-18 17:1x · 「수급」 을 새 「관심」 과 한 줄로 이어 셀까요 물음에).
    → (칩 목록, 단타 셈 칩 수). 뺀 뒤 단타 셈 칩이 하나도 없으면(하트로만 든 종목) 칩 수 0 — day_rows 가 그 종목을 뺀다."""
    chips = list(r.get("chips") or [])
    if (b.get("meta") or {}).get("watchRule") != "자동":
        chips = [("관심" if c == "수급" else c) for c in chips if c != "관심"]
    return chips, len(set(chips) & set(dt30.OV_CHIPS))


def day_rows(b):
    """판(dict) → 종목마다 {code · name · chips · n · buy · sell · ret(% · 못 잼이면 None)} · 11-18 전 판은 칩 이름을 지금 룰로(_chips_now_rule)."""
    out = []
    for r in b.get("rows") or []:
        chips, n = _chips_now_rule(b, r)
        if n < dt30.MIN_CHIPS:
            continue                                   # 지금 룰로는 판에 없는 종목 — 하트 관심으로만 든 종목(재권님 「삭제」) · 칩 하나뿐인 종목(지난 판 · 재권님 「응」 11-18 17:5x — 판 문턱 둘 이상과 같게)
        buy, sell = r.get("buy"), (r.get("px") or {}).get(SELL_AT)
        ret = round((sell - buy) / buy * 100, 3) if buy and sell is not None else None
        out.append({"code": r.get("code"), "name": r.get("name"), "market": r.get("market"), "chips": chips, "n": n,
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
        if have.get(day) == "%s|%s" % (saved, VER):
            continue
        got = dt30._load(proxy, day)
        if not got or not got[0].get("closed", True):
            continue                                   # 안 끝난 그날 판 — 14:00 칸을 다 적은 뒤
        rows = day_rows(got[0])
        with proxy._db_lock, proxy.db_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO dt30_win VALUES (?,?,?,?)",
                         (day, "%s|%s" % (got[1], VER), json.dumps(rows, ensure_ascii=False), _now().strftime("%Y-%m-%d %H:%M:%S")))
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


def net_pct(r, fee):
    """세후 손익 % — 못 셈(값 없음 · 시장 모름)이면 None."""
    buy, sell, T = r.get("buy"), r.get("sell"), TAX.get(str(r.get("market") or "").upper())
    if not buy or sell is None or T is None:
        return None
    cost = sell * (T["tx"] + T["rural"]) / 100 + sell * (fee or 0) / 100     # 수수료는 팔 때만 — 재권님 「증권수수료는 팔때만」(11-18 · 단타 판 화면 셈과 같게)
    return round((sell - buy - cost) / buy * 100, 3)


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
            v = net_pct(r, fee)
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
            "fee": fee, "feeNote": None if fee is not None else "빈칸 — 수수료 안 셈", "feeSides": "팔 때만",
            "tax": TAX, "taxNote": "팔 때만 · 판 값 × (거래세 + 농특세) · 시장 모르면 못 잼", "ret": "세후 %",
            "buy": "그날 판 매수가(rows[].buy · 11-20 판부터 판에 든 때 값 — 09:01 전에 있던 종목은 9시 1분 값 · 뒤에 든 종목은 든 순간 값 · 11-18~19 09:00 시가 · 그 전 09:01)", "minChips": dt30.MIN_CHIPS, "sell": SELL_AT, "bigPct": BIG_PCT, "topDay": TOP_DAY,
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
