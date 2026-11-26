# -*- coding: utf-8 -*-
"""미국이 움직인 다음 날, 국내 섹터 · 테마도 같은 쪽으로 갔나 — 미국 묶음 등락률을 국내 업종 · 테마 이름으로 (2026-11-25).

재권님(시황분석1 창) — 「미국섹터와 테마를 국내와 동일하게 맞추고 싶은데」 → 대응표 안 → 「응 넘기고 이거 단타쪽에 있어야 할정보같은데.
매일매일 쌓여야 할거같아」(12:0x) · 「단타에 섹터 수급과 옵션 만기 사이로 · 누락된 정보는 받아서 쌓이게」(12:1x) → 개발2 창 「응 해」(14:35).
화면은 company-setup/js/strategy-uskr.js(시황분석1).

    대응표    us_kr_map.json 한 곳(시황분석1 이 만들고 재권님이 표로 보심 · 옮겨 둠)
                sector   S&P 500 GICS 하부산업 → 국내 업종(네이버 WICS) 이름 · sp500 [티커, 하부산업]
                themeEtf 국내 테마 → 미국 테마 ETF 하나 · 그 ETF 일봉이 없으면 theme3 로
                theme3   국내 테마 → 미국 종목 셋(평균) · weak = 짝 약함 · why = 고른 까닭
    미국 값   그 묶음 티커들의 그날 일봉 등락률(앞 일봉 종가 대비) 평균 — candles(period D) 를 읽기만(미국 일봉은 서버 봉 채우기가 날마다 받음)
    한국 값   그날 섹터 수급 굳힌 판(sector_flow_day · 14:01 굳힘)의 묶음 등락률 마지막 칸(13:55 끝 · 전날 정규장 종가 대비) — 오늘 칸은 null(화면이 섹터 수급 지금 값으로 덮음)
    짝        한국 장날마다 그 앞 마지막 미국 장날 · 오늘이 장 여는 날이면 오늘 칸도(한국 값 null)
    쌓기      두 값 다 날마다 서버가 받아 DB 에 남기는 것(일봉 · 섹터 수급 굳힌 판)이라 이 파일은 셈만 한다 — 빠진 날은 그 받기 쪽이 되채움
    없음      티커 일봉이 없거나 그날 판이 없으면 null — 0 으로 꾸미지 않는다
    주소      GET /api/kis/us-kr-groups?by=sector|theme[&month=YYYYMM]
              data {days [{us, kr}] 최근 먼저, rows [{name, pair{kind gics|etf|three, tickers, n, label, weak, why} | null, us{날: %}, kr{날: %}}]}
              meta {by, month, months(최근 먼저), from, asof}
"""
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
MAP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "us_kr_map.json")
FROM_DAY = "20261101"          # 이 한국 장날부터 — 카드 「11월부터 되채움」
CACHE_SEC = 300                # 같은 판을 다시 셈하지 않는 초(미국 일봉 · 굳힌 판은 하루에 한 번 바뀜)
BYS = ("sector", "theme")

_lock = threading.Lock()
_map = {"mtime": None, "val": None}
_kr_memo = {}                  # (day, by) → (저장 시각, {묶음: %}) — 뒤 칸 덧붙이기(tail_fill)가 지난 날 판을 다시 쓰면 저장 시각이 바뀌어 다시 읽음(단타 리뷰 ④ 11-26)
_memo = {}                     # (by, month) → (시각, 열쇠, 값)


def _now():
    return datetime.now(KST)


def load_map():
    m = os.path.getmtime(MAP_FILE)
    with _lock:
        if _map["mtime"] != m:
            with open(MAP_FILE, encoding="utf-8") as f:
                _map.update(mtime=m, val=json.load(f))
        return _map["val"]


def _code(t):
    return t.replace(".", "/")      # BRK.B → 봉 표 BRK/B


def _us_pct(conn, tickers, since):
    """{티커: {날: %}} — 앞 일봉 종가 대비."""
    out = {}
    for t in tickers:
        rows = conn.execute("SELECT ts, close FROM candles WHERE period = 'D' AND code = ? AND ts >= ? ORDER BY ts",
                            (_code(t), since)).fetchall()
        m = {}
        for (a, ca), (b, cb) in zip(rows, rows[1:]):
            if ca and cb:
                m[b[:8]] = (cb / ca - 1) * 100
        out[t] = m
    return out


def _kr_day(conn, day, by):
    key = (day, by)
    r = conn.execute("SELECT saved_at, body FROM sector_flow_day WHERE day = ? AND by = ?", (day, by)).fetchone()
    hit = _kr_memo.get(key)
    if hit and r and hit[0] == r[0]:
        return hit[1]
    saved = r[0] if r else None
    r = r[1:] if r else None
    v = {}
    if r and r[0]:
        for name, g in (json.loads(r[0]) or {}).items():
            p = {s: x for s, x in (g.get("pct") or {}).items() if x is not None}
            if p:
                v[name] = p[max(p)]
    if v:
        _kr_memo[key] = (saved, v)                     # 굳힌 날만 들고 있음 — 아직 안 굳힌 오늘은 다음에 다시 읽음
    return v


def _pairs(m, by, names, have):
    """{국내 이름: (짝, [티커])}"""
    out = {}
    if by == "sector":
        subs = {}
        for sym, sub in m["sp500"]:
            kr = m["sector"].get(sub)
            if kr:
                subs.setdefault(kr, {}).setdefault(sub, []).append(sym)
        loose = set(m.get("loose") or [])
        for n in names:
            g = subs.get(n)
            if not g:
                out[n] = (None, [])
                continue
            ts = [t for s in sorted(g) for t in g[s]]
            label = " · ".join((m["subKo"].get(s) or s) + (" (넓음)" if s in loose else "") for s in sorted(g))
            out[n] = ({"kind": "gics", "tickers": ts, "n": len(ts), "label": label}, ts)
        return out
    for n in names:
        etf = m["themeEtf"].get(n)
        if etf and have(etf):
            out[n] = ({"kind": "etf", "tickers": [etf], "label": None}, [etf])
            continue
        t3 = m["theme3"].get(n)
        if t3:
            out[n] = ({"kind": "three", "tickers": t3["tickers"], "weak": bool(t3.get("weak")), "why": t3.get("why")}, list(t3["tickers"]))
        else:
            out[n] = (None, [])
    return out


def board(proxy, by="sector", month=None):
    now = _now()
    today = now.strftime("%Y%m%d")
    m = load_map()
    with proxy._db_lock, proxy.db_conn() as conn:
        kr_days = [d for (d,) in conn.execute("SELECT DISTINCT day FROM sector_flow_day WHERE by = ? AND day >= ? ORDER BY day", (by, FROM_DAY))]
        last_us = (conn.execute("SELECT MAX(ts) FROM candles WHERE period = 'D' AND code = 'SPY'").fetchone() or [None])[0]
        saved = (conn.execute("SELECT MAX(saved_at) FROM sector_flow_day WHERE by = ?", (by,)).fetchone() or [None])[0]   # 지난 날 판이 다시 쓰여도(뒤 칸 덧붙이기) 다시 셈(단타 리뷰 ④ 11-26)
        key = (tuple(kr_days[-1:]), last_us, today, _map["mtime"], saved)
        hit = _memo.get((by, month))
        if hit and hit[1] == key and time.time() - hit[0] < CACHE_SEC:
            return hit[2]
        open_today = False
        try:
            import market_hours
            open_today = market_hours.today(proxy)["open"] is not False and now.weekday() < 5
        except Exception:
            open_today = now.weekday() < 5
        if open_today and today not in kr_days and today >= FROM_DAY:
            kr_days.append(today)
        since = (datetime.strptime(FROM_DAY, "%Y%m%d") - timedelta(days=14)).strftime("%Y%m%d")
        names = sorted({n for d in kr_days for n in _kr_day(conn, d, by)})
        cache = {}

        def have(t):
            if t not in cache:
                cache[t] = conn.execute("SELECT 1 FROM candles WHERE period = 'D' AND code = ? LIMIT 1", (_code(t),)).fetchone() is not None
            return cache[t]

        pairs = _pairs(m, by, names, have)
        us = _us_pct(conn, sorted({t for _, ts in pairs.values() for t in ts}), since)
        us_days = sorted({d for v in us.values() for d in v})
        kr_val = {d: _kr_day(conn, d, by) for d in kr_days}   # 오늘은 14:01 굳힌 뒤에만 값(그 전은 null · 화면이 지금 값으로 덮음)
        for pr, _ts in pairs.values():
            if pr and pr["kind"] == "etf":
                r = conn.execute("SELECT name_ko FROM us_symbols WHERE symbol = ?", (_code(pr["tickers"][0]),)).fetchone()
                pr["label"] = r[0] if r and r[0] else None
    days = []
    for k in kr_days:
        u = next((d for d in reversed(us_days) if d < k), None)
        if u:
            days.append({"us": u, "kr": k})
    months = sorted({d["kr"][:6] for d in days}, reverse=True)
    mon = month if month in months else (months[0] if months else None)
    sel = sorted((d for d in days if d["kr"][:6] == mon), key=lambda d: d["kr"], reverse=True)
    rows = []
    for n in names:
        pair, ts = pairs[n]
        uv, kv = {}, {}
        for d in sel:
            xs = [us[t][d["us"]] for t in ts if d["us"] in us.get(t, {})]
            uv[d["us"]] = round(sum(xs) / len(xs), 2) if xs else None
            kv[d["kr"]] = kr_val.get(d["kr"], {}).get(n)
        rows.append({"name": n, "pair": pair, "us": uv, "kr": kv})
    out = ({"days": sel, "rows": rows},
           {"by": by, "month": mon, "months": months, "from": FROM_DAY, "asof": now.strftime("%H:%M:%S"), "lastUs": last_us,
            "note": "미국 = 짝 티커 일봉 등락률 평균(앞 일봉 종가 대비) · 한국 = 섹터 수급 굳힌 판 마지막 칸(13:55 끝 · 전날 종가 대비) · 오늘 한국 칸은 14:01 굳히기 전엔 null(화면이 지금 값으로 덮음) · 없는 값 null"})
    _memo[(by, month)] = (time.time(), key, out)
    return out
