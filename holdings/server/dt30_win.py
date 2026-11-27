# -*- coding: utf-8 -*-
"""단타 판 칩별 승률 — 날마다 그날 판의 손익을 쌓고, 칩마다 · 겹침마다 승률을 셈한다 (2026-11-18).

재권님 — 단타 판 칩별 승률(시황분석1 잼 · 작업우선순위 배분 「(나)로」) → 착수 안에 「응」(개발2 창 11-18).

    셈        종목마다 판 매수가(rows[].buy · 판에 든 때 값 — meta 「buy」 설명) → 14:00 값(rows[].px['1400']) 손익 % — 둘 중 하나라도 없으면 「못 잼」(ret null · 따로 셈)
    쌓기      그날 판이 끝나면(closed · 14:00 칸까지 적힘 · 보통 14:01) 하루 한 줄 — market.db dt30_win(날 · 종목 손익 JSON · 그 판의 저장 시각)
              판이 다시 저장되면(되채움 등 · saved_at 이 바뀜) 그날 줄도 다시 · 남은 판(지난 30거래일)은 서버가 뜬 뒤 처음 바퀴에 채운다 — KIS 안 씀
    이김      세후 손익이 0 보다 크다 — 화면(strategy-dt30.js calc)과 같은 셈(개념정의 검수 11-18):
              세후 % = (판 값 − 산 값 − 판 값 × (거래세 + 농특세 + 수수료)) ÷ 산 값 × 100 · 세금 · 수수료 둘 다 팔 때만(재권님 「증권수수료는 팔때만」 11-18)
              세율은 아래 TAX(시장마다) 한 곳 — 단타 판 응답 meta.tax 로 화면이 받는다(11-20 재권님 「증권사 세율만 조절되도록 남기면되, 단타에 표기는 해놓고」) · 시장을 모르면 세금을 못 셈 → 「못 잼」
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
TAX = {"KOSPI": {"tx": 0.05, "rural": 0.15}, "KOSDAQ": {"tx": 0.20, "rural": 0.0}}   # % · 2026 세율(KB증권 「2026년 증권거래세율 변경 안내」) · 한 곳 — 단타 판 화면은 dt30 판 meta.tax 로 받음 · 단타 판에서 못 바꿈(재권님 11-20 14:09)
VER = "v11"                  # 쌓는 줄 모양이 바뀌면 올린다 — 옛 줄을 다시 쌓는다(v2 · 시장 칸 · v3 · 11-18 전 판 칩 이름 옮김 · v4 · 칩 둘 이상만 · v5 · 칩 붙은 시각 chipAt · subAt · buyAt · lockAt 11-20 · v6 · buyTs · lockTs 실제 시각 11-20 · v7 · 시각 칸 값 px — 매도 시각을 부를 때 셈 11-20 · v8 · 굳힘 차례 lock — 「사지 않음」 묶음 가름 11-23 · v9 · 굳힌 뒤 붙은 칩 거래비율 · 거래비율급증을 다시 쌓음(개념정의 덧 ② 11-23) · v10 · 굳힘 → 시간 창(lock 이 창 번호 1~6 · 11-23 17:2x) · v11 · 사는 셈 한 곳(dt30.buy_point) 재료 — chipTime · pxMin · 여는 시각 · 칩 하나 이상 줄 다(11-23 19:0x))
_SCHEMA = "CREATE TABLE IF NOT EXISTS dt30_win (day TEXT PRIMARY KEY, src_saved TEXT, rows TEXT NOT NULL, at TEXT)"
_status = {"error": None, "filled": 0, "at": None}
_bars_memo = {}               # (날, 종목 튜플, 끝) → 그날 봉 — 지난 날만(봉이 안 바뀜) · 부를 때마다 30날 1분봉을 다시 읽어 5~19초 걸리던 것(11-27 09:2x 잼)
_sum_memo = {"key": None, "val": None, "at": 0.0}   # 들어간 것(쌓인 줄 · 셈 칸 · 수수료 · 문턱)이 같고 오늘 줄이 없으면 지난 셈 그대로
_memo_lock = threading.Lock()
BARS_MEMO_DAYS = 60
SUM_LIVE_SEC = 60             # 오늘 줄이 든 셈은 이 초만 그대로(오늘 봉이 늘어서)


def _now():
    return datetime.now(KST)


def _chips_now_rule(b, r):
    """11-18 전 판(meta.watchRule 이 「자동」 이 아님)의 칩을 지금 이름으로 — 「수급」(자동 관심 종목)은 「관심」 으로 이어 세고
    하트 「관심」 은 뺀다 — 재권님 「전 하트 관심은 삭제」(11-18 17:1x · 「수급」 을 새 「관심」 과 한 줄로 이어 셀까요 물음에).
    → (칩 목록, 단타 셈 칩 수). 뺀 뒤 단타 셈 칩이 하나도 없으면(하트로만 든 종목) 칩 수 0 — day_rows 가 그 종목을 뺀다."""
    chips = list(r.get("chips") or [])
    if (b.get("meta") or {}).get("watchRule") != "자동":
        chips = [("관심" if c == "수급" else c) for c in chips if c != "관심"]
    return chips, len(set(chips) & set(dt30.ov_chips()))


def day_rows(b, proxy=None):
    """판(dict) → 종목마다 {code · name · chips · n · buy · sell · ret(% · 못 잼이면 None) · chipAt · subAt · buyAt · lockAt(붙은 · 든 · 굳힌 시각)} · 11-18 전 판은 칩 이름을 지금 룰로(_chips_now_rule)."""
    out = []
    cf, om = {}, None
    dt30.live_merge(b)                                 # 다시 지은 라이브 판 — 장중 값으로(판과 같게) · 못 하면 터뜨려 저장 안 함(fill 이 다음에 다시 · 단타 리뷰 ② 11-26)
    if proxy is not None:                              # 칩 시각 · 여는 시각 · N분 값을 못 읽으면 터뜨림 — 보통 날 · 장 전으로 셈한 줄을 저장해 영영 다시 안 세던 것(단타 리뷰 ② 11-26)
        dt30._pxmin_fill(proxy, b)                     # 여는 시각 + N분 값 — 사는 값 재료(쌓인 1분봉 · DB 만)
        cf = dt30.chip_first_get(proxy, b["day"], [r["code"] for r in (b.get("rows") or []) + ((b.get("meta") or {}).get("outRows") or [])])
        om = dt30._open_min(proxy, b["day"], b)
    outs = [dict(o) for o in (b.get("meta") or {}).get("outRows") or []]   # 판에서 빠진 종목 — 빠진 뒤 값 칸은 5분봉으로 채움(dt30._out_px)
    if outs and proxy is not None:
        try:
            dt30._out_px(proxy, b, outs)
        except Exception as e:
            print("  [단타 승률] %s 빠진 종목 값 못 채움 — %s" % (b.get("day"), proxy.safe_message(e, 120)), flush=True)
    b = dict(b, rows=(b.get("rows") or []) + outs)
    ct = dt30.chip_times(b, cf)
    for r in b.get("rows") or []:
        chips, n = _chips_now_rule(b, r)
        if n < 1:
            continue                                   # 지금 룰로는 판에 없는 종목 — 하트 관심으로만 든 종목(재권님 「삭제」) · 칩 수 문턱은 부를 때 셈 칸 minChip 으로(dt30.buy_need · 11-23)
        buy, sell = r.get("buy"), (r.get("px") or {}).get(SELL_AT)
        ret = round((sell - buy) / buy * 100, 3) if buy and sell is not None else None
        out.append({"code": r.get("code"), "name": r.get("name"), "market": r.get("market"), "chips": chips, "n": n,
                    "buy": buy, "sell": sell, "ret": ret, "px": r.get("px") or {},   # 시각 칸 값 — 매도 시각(end_at)으로 부를 때 판 값을 고른다
                    # 칩 · 하위가 판에 붙은 시각과 든 시각 — 굳힌 뒤(10:30 뒤) 늦게 붙은 칩도 승률에 넣되 시간대로 가를 수 있게
                    # (재권님 「시간대가 추가되면 넣어놓는게 좋을거같아」 11-20 · 옛 판은 없음 → null)
                    "chipAt": r.get("chipAt"), "subAt": r.get("subAt"), "buyAt": r.get("buyAt"), "buyTs": r.get("buyTs"), "lockAt": r.get("lockAt"), "lockTs": r.get("lockTs"),
                    "pxMin": r.get("pxMin"), "px1": r.get("px1"), "viAt": r.get("viAt"), "surgeAt": r.get("surgeAt"),
                    "chipTime": ct.get(r["code"]) or {}, "_pxMinAt": (b.get("meta") or {}).get("pxMinAt") or {}, "_open": om, "_times": b.get("times") or [],
                    "lock": r.get("lock")})                       # 시간 창 번호(1~5 · 장중 dt30.INTRA_LOCK · 문턱 밑 None · 11-23 17:2x 전에는 굳힘 차례) — 「사지 않음」 묶음 가름(no_buy_locks)
    return out


def _in_ts(r):
    """판에 든 때 HHMMSS — buyTs(초까지) · 없으면 buyAt + 「00」 · 둘 다 없으면 ''(옛 판 · 못 가름 → 안 뺌)."""
    t = str(r.get("buyTs") or "").replace(":", "")
    if len(t) >= 6 and t[:6].isdigit():
        return t[:6]
    a = str(r.get("buyAt") or "").replace(":", "")[:4]
    return a + "00" if len(a) == 4 and a.isdigit() else ""


def late_chip(r, chip):
    """그 칩이 산 뒤(판에 든 때 · _in_ts)에 붙었나 — chipAt 「HH:MM」 이 든 때 HHMMSS 보다 늦으면 True · 시각을 모르면 False(못 가름 → 안 가름).
    재권님 「나로 하고 나중에 검색할때 칩갯수옆에 시간외제외 버튼 만들면 될거같아」(11-23 16:5x) — 승률은 다 세고 이 칸으로 따로 보인다."""
    at = str((r.get("chipAt") or {}).get(chip) or "").replace(":", "")[:4]
    t = _in_ts(r)
    return len(at) == 4 and at.isdigit() and bool(t) and at + "00" > t


def _in_until(proxy, day, rule):
    """그날 든 때 가격으로 사는 끝 HHMMSS — 셈 칸 inUntil(없으면 SET_DEF) 분 59초 · 늦게 여는 날은 늦은 분만큼 뒤(여는 시각 + 1분 기준 · 개념정의 덧 11-23).
    못 읽으면 여는 시각 분 59초 — 9시 1분 뒤 든 종목은 안 삼(화면 단타 판 셈 caf0a62 과 같게 · 개념정의 8315a24 덧)."""
    v = str(rule.get("inUntil") or "").replace(":", "").strip()
    if len(v) == 3 and v.isdigit():
        v = "0" + v                                    # 「9:05」 · 「905」 처럼 앞 0 없이 넣은 값(qa 덧 11-23)
    if len(v) != 4 or not v.isdigit():
        v = "%02d%02d" % dt30.OPEN_AT                  # 끝을 모르면 든 때 가격으로는 안 삼 — 여는 시각 분 안(09:00:59)까지만
    m = int(v[:2]) * 60 + int(v[2:]) + dt30.late_min(proxy, day=day)
    return "%02d%02d59" % divmod(m, 60)


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
        try:
            rows = day_rows(got[0], proxy)
        except Exception as e:                         # 재료를 못 읽은 날 — 저장 안 하고 다음 바퀴에 다시(단타 리뷰 ② 11-26)
            print("  [단타 승률] %s 못 셈 — 저장 안 하고 다음에 다시 · %s" % (day, proxy.safe_message(e, 120)), flush=True)
            continue
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
        d = dt30.chip_rules.rules_doc() or {}           # 상류(8765) 문서 한 곳 — 넘기는 서버도 같은 셈 칸(개념정의 덧 ① 11-23)
        d = d.get("data", d) if isinstance(d, dict) else {}
        v = ((d.get("rules") or {}).get("dt30") or {}).get("feePct")
        return None if v is None or v == "" else float(v)
    except Exception:
        return None


def _set(live=False):
    """단타 판 셈 칸 — 룰 문서 strategy-rules rules.dt30.set(화면과 같은 칸 한 곳) · 비거나 못 읽으면 {}.
    live=True 면 그날 굳힌 셈 칸을 건너뛰고 지금 저장값 — 조합 문턱(comboUp · comboN · dt30.combo_pick)이 쓴다(재권님 「아니 내가 문턱을 조정하면 다 되도록 해야해」 → 「응」 11-27 12:1x)."""
    fz = None if live else getattr(dt30._SET_TL, "v", None)   # 그날 판에 굳힌 셈 칸(dt30._frozen_set · 매수 알림 창 · 재권님 「가」 11-26)
    if isinstance(fz, dict):
        return fz
    try:
        d = dt30.chip_rules.rules_doc() or {}           # 상류(8765) 문서 한 곳 — 넘기는 서버도 같은 셈 칸(개념정의 덧 ① 11-23)
        d = d.get("data", d) if isinstance(d, dict) else {}
        v = ((d.get("rules") or {}).get("dt30") or {}).get("set")
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


# 셈 칸이 비었을 때 값 — 한 곳(손절 −1 · 꺾임 켬 · 둘 다 · 0 · 고점 빈칸 · 시각 미달 끔 90분 2% · 횡보 끔) ·
#   /api/kis/chip-rules meta.sellDef 로 내주고 화면 단타 판은 받기만(11-20 재권님 「가」 · 두 벌 합치기 — 화면 DEF_SET 의 같은 칸은 시황분석이 지움)
SET_DEF = {"stop": -1, "turn": True, "turnBy": "both", "turnPct": 0, "trail": None,
           "cut": False, "cutMin": 90, "cutPct": 2, "flat": False, "flatMin": None, "flatPct": None,
           "inUntil": "0905", "comboUp": 70, "comboN": 2}
# comboUp · comboN — 칩 조합 고르는 문턱(오른 비율 % · 건수) 칸이 아예 없을 때 · 비워 저장하면 안 고름(dt30.combo_pick · 재권님 「70%이상만」 11-26)
# inUntil — 매수 「9시 1분 값」 일 때 여는 시각 + 1분 뒤 판에 든 줄을 든 때 가격으로 사는 끝 시각(그 분 59초까지 · HHMM) · 그 뒤 든 줄은 안 삼 —
#   재권님 「매수 시각을 9시 5분까지로 수정해」(11-23 09:11) → 「나」 → 「9시 1분부터 5분까지는 들어올때 산다 라는룰로」(09:1x) · 셈은 화면(단타 판 buyOf)


def no_buy_locks():
    """「사지 않음」 굳힘 차례 집합 — 룰 문서 셈 칸 rules.dt30.set.lockNoBuy([첫째, 둘째, 셋째, 장중] 참/거짓 · null 은 산다).
    재권님 「굳힘에 사지않는다 라는 버튼도 하나 만들어줘」(11-23 11:43) → 안에 「응」 · 열쇠는 시황분석1 화면과 같게.
    참인 차례에 굳은 줄은 승률 · 손익 셈에서 안 산 것으로 뺀다 · 판(rows)에는 그대로 남는다. 못 읽으면 빈 집합(전처럼 다 산 것)."""
    v = _set().get("lockNoBuy")
    return {i for i, x in enumerate(v, 1) if x is True} if isinstance(v, list) else set()


def sell_rule():
    """매도 셈 칸 — 셈 칸 값이 없으면 SET_DEF · endAt 은 「HHMM」 또는 None."""
    S = dict(SET_DEF)
    S.update({k: v for k, v in _set().items() if k in SET_DEF or k == "endAt"})
    v = str(S.get("endAt") or "").replace(":", "").strip()
    S["endAt"] = v if len(v) == 4 and v.isdigit() and int(v[:2]) < 24 and int(v[2:]) < 60 else None
    return S


def end_at():
    """매도 시각 「HHMM」 — 셈 칸 endAt · 빈칸 · 못 읽음 · 틀린 꼴이면 None(판 끝 SELL_AT).
    재권님 「응 해」(11-20 15:3x · 시황분석 창) — 승률 표도 단타 판 매도 시각을 따르게(14:00 고정 대신)."""
    return sell_rule()["endAt"]


def _hm(t):
    return str(t or "").replace(":", "")[:4]


def _cut_time(at, mins):
    """산 시각 → 판정 시각(HHMM) — 30분 단위 반올림(분 15 이상이면 다음 30분) 뒤 mins 분 · 화면 cutTime 과 같은 셈."""
    t = _hm(at)
    if len(t) != 4 or not t.isdigit():
        return ""
    r = (int(t[:2]) * 60 + int(t[2:]) + 15) // 30 * 30 + int(mins or 0)
    return "%02d%02d" % (r // 60, r % 60)


def sell_bar():
    """매도 셈 봉 길이 — 셈 칸 rules.dt30.set.sellBar 「1m」 · 「5m」 · 「30m」(없거나 틀리면 「5m」) · 화면과 같은 칸 한 곳.
    재권님 「꺽임 시가미달 횡보 매도시각도 1분봉으로」 → 「매도타이밍은 5분봉으로 하자」 → 「1분봉과 5분봉을 선택할수 있게 해줘 30분봉도」(11-23 20:1x · 시황분석1 창 a66a940)."""
    v = _set().get("sellBar")
    return v if v in ("1m", "5m", "30m") else "5m"


def _bars_step(per, bs, step):
    """봉을 step 분 봉으로 — 1분봉을 5분씩 묶음(시가 첫 · 고가 최대 · 저가 최소 · 종가 끝 · 봉 시작 = 분을 step 으로 내림) · 이미 그 길이 이상이면 그대로."""
    have = 1 if per == "1m" else dt30.BAR_MIN
    if step <= have:
        return bs
    out = {}
    for t, o, h, l, c in bs:
        m = int(t[:2]) * 60 + int(t[3:])
        k = "%02d:%02d" % divmod(m // step * step, 60)
        g = out.get(k)
        out[k] = [k, o, h, l, c] if g is None else [k, g[1], max(g[2], h), min(g[3], l), c]
    return [out[k] for k in sorted(out)]


def _sell_bars(r, end, S, per, step):
    """봉으로 파는 값과 까닭 — 화면 sellBars 와 같은 셈(시황분석1 a66a940 · 11-23 20:1x):
        ① 산 시각(HHMM)이 든 봉과 그 앞 봉은 뺀다 — 매수가가 그 봉 종가라 그 봉 저가는 사기 전 값
        ② 봉마다 차례로 — 봉 시작 ≥ 매도 시각 → 그 봉 시가 「매도 시각」 · 손절(저가 ≤ 매수가 × (1 + 손절%) → 시가가 밑이면 시가 아니면 손절가) ·
           고점(앞 봉 고가 최고 > 매수가 · 저가 ≤ 최고 × (1 − 고점%) → 같은 꼴) · 꺾임(turnBy ≠ peak · 앞 봉 종가 > 매수가 · 종가 ÷ 앞 종가 − 1 < −꺾임% → 종가) ·
           미달(산 시각 + cutMin 반올림 시각 ≤ 봉 끝 인 첫 봉 · 종가 % ≤ cutPct → 종가) · 횡보(같은 꼴 flatMin · |%| ≤ flatPct)
        ③ 끝까지 안 걸리면 마지막 봉 종가 「매도 시각」"""
    buy, b_at = r.get("buy"), _hm(r.get("buyAt"))
    stop, turnby, trail = S.get("stop"), S.get("turnBy") or "both", S.get("trail")
    stop_px = buy * (1 + float(stop) / 100) if stop is not None else None
    tr = float(trail) if S.get("turn") and turnby != "prev" and trail is not None else None
    tp = -float(S.get("turnPct") or 0) if S.get("turn") and turnby != "peak" else None
    cut_hm = _cut_time(b_at, S.get("cutMin")) if S.get("cut") and S.get("cutPct") is not None else ""
    flat_hm = _cut_time(b_at, S.get("flatMin")) if S.get("flat") and S.get("flatMin") is not None and S.get("flatPct") is not None else ""
    cut_done = flat_done = False
    peak = prev_c = last = None
    for t, o, h, l, c in _bars_step(per, r.get("bars") or [], step):
        hm = t.replace(":", "")
        m = int(hm[:2]) * 60 + int(hm[2:])
        if b_at and hm <= b_at < "%02d%02d" % divmod(m + step, 60) or (b_at and hm < b_at):
            continue                                   # ① 산 시각이 든 봉 · 그 앞 봉
        if hm >= end:
            return o, "매도 시각"
        if stop_px is not None and l <= stop_px:
            return (o if o < stop_px else round(stop_px, 2)), "손절"
        if tr is not None and peak is not None and peak > buy:
            line = peak * (1 - tr / 100)
            if l <= line:
                return (o if o < line else round(line, 2)), "고점"
        if tp is not None and prev_c is not None and prev_c > buy and (c / prev_c - 1) * 100 < tp:
            return c, "꺾임"
        e = "%02d%02d" % divmod(m + step, 60)          # 봉 끝
        p = (c / buy - 1) * 100
        if cut_hm and not cut_done and cut_hm <= e:
            cut_done = True
            if p <= float(S.get("cutPct")):
                return c, "미달"
        if flat_hm and not flat_done and flat_hm <= e:
            flat_done = True
            if abs(p) <= float(S.get("flatPct")):
                return c, "횡보"
        peak = h if peak is None else max(peak, h)
        prev_c, last = c, c
    return last, "매도 시각"


def sell_of(r, end, S=None):
    """그 줄을 파는 값과 까닭 → (값, 까닭) — 화면 sellAt 과 같은 셈(손절 · 꺾임 · 고점 · 시각 미달 · 횡보 · 매도 시각).
    재권님 「각각의 룰에 걸리면 매도야」(11-20 15:5x) — 그 전에는 매도 시각만 따랐다.
    시각 칸(30분)마다 매수가 대비 % 로 보고 처음 걸린 칸 값에 판다 · 하나도 안 걸리면 end 이하 마지막 값 있는 칸 · 칸이 없는 옛 줄은 쌓은 sell."""
    px = r.get("px")
    if not px:
        return r.get("sell"), "옛 줄"
    S = S or sell_rule()
    sb = S.get("sellBar") if S.get("sellBar") in ("1m", "5m", "30m") else sell_bar()
    per = r.get("_barPer") or r.get("barSrc")
    if sb != "30m" and r.get("bars") and r.get("buy") and per:
        out = _sell_bars(r, end, S, per, 1 if sb == "1m" and per == "1m" else dt30.BAR_MIN)   # 봉으로 — 1분봉이 없는 날(5m)은 「1m」 이어도 5분봉 폭으로(개념정의 덧 · 화면도 5분봉으로 맞춤)
        if out[0] is not None:
            return out
    buy, b_at = r.get("buy"), _hm(r.get("buyAt"))
    ks = [k for k in sorted(px, key=_hm) if _hm(k) <= end]
    if not buy:
        vs = [k for k in ks if px[k] is not None]
        return (px[vs[-1]] if vs else None), "매도 시각"
    stop, turnby, trail = S.get("stop"), S.get("turnBy") or "both", S.get("trail")
    cut_hm = _cut_time(b_at, S.get("cutMin")) if S.get("cut") and S.get("cutPct") is not None else ""   # % 가 비면 안 셈(qa 덧 11-20 — 그 전 float(None) 으로 죽음)
    flat_hm = _cut_time(b_at, S.get("flatMin")) if S.get("flat") and S.get("flatMin") is not None and S.get("flatPct") is not None else ""
    cut_done = flat_done = False
    pk, prev, last = 0.0, None, None
    for k in ks:
        v = px[k]
        if v is None or (b_at and _hm(k) <= b_at):
            continue                                   # 산 시각 앞 칸은 안 봄(화면과 같게)
        p = (v / buy - 1) * 100
        last = k
        if stop is not None and p <= stop:
            return v, "손절"
        if S.get("turn") and turnby != "peak" and prev is not None and prev > 0 and ((100 + p) / (100 + prev) - 1) * 100 < -float(S.get("turnPct") or 0):
            return v, "꺾임"
        if S.get("turn") and turnby != "prev" and trail is not None and pk > 0 and ((100 + p) / (100 + pk) - 1) * 100 <= -float(trail):
            return v, "고점"
        if cut_hm and not cut_done and _hm(k) >= cut_hm:
            cut_done = True
            if p <= float(S.get("cutPct")):
                return v, "미달"
        if flat_hm and not flat_done and _hm(k) >= flat_hm:
            flat_done = True
            if abs(p) <= float(S.get("flatPct")):
                return v, "횡보"
        pk, prev = max(pk, p), p
    return (px[last] if last else None), "매도 시각"


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
    rule = sell_rule()
    end = rule["endAt"] or SELL_AT
    with proxy.db_conn() as conn:
        try:
            got = conn.execute("SELECT day, rows FROM dt30_win ORDER BY day DESC LIMIT ?", (days,)).fetchall()
        except Exception:
            got = []
    import zlib
    import dart
    caps = {r["stock_code"]: r["market_cap"] for r in dart.universe_rows(None)}
    today = _now().strftime("%Y%m%d")
    key = (tuple((d, zlib.crc32(raw.encode("utf-8"))) for d, raw in got), fee, json.dumps(rule, sort_keys=True, default=str), end,
           dt30.buy_need(), dt30.buy_until(), dt30.buy_mode(), dt30.cap_min_eok(), tuple(dt30.ov_chips()),
           zlib.crc32(json.dumps(sorted(caps.items()), default=str).encode()), _status["at"], _status["error"])
    with _memo_lock:
        if _sum_memo["key"] == key and (not any(d >= today for d, _ in got) or time.time() - _sum_memo["at"] < SUM_LIVE_SEC):
            return _sum_memo["val"]
    val = _summary(proxy, got, fee, rule, end, caps, today)
    with _memo_lock:
        _sum_memo.update(key=key, val=val, at=time.time())
    return val


def _day_bars(proxy, day, codes, end, today):
    k = (day, tuple(codes), end)
    with _memo_lock:
        hit = _bars_memo.get(k)
    if hit is not None:
        return hit
    bars = dt30.bars_get(proxy, day, codes, "0900", end)
    if day < today:
        with _memo_lock:
            _bars_memo[k] = bars
            while len(_bars_memo) > BARS_MEMO_DAYS:
                _bars_memo.pop(next(iter(_bars_memo)))
    return bars


def _summary(proxy, got, fee, rule, end, caps, today):
    groups = {"chip": {}, "pair": {}, "triple": {}, "count": {}, "countRise": {}, "chipLate": {}, "buySrc": {}}

    def add(kind, key, v):
        g = groups[kind].setdefault(key, [[], 0])
        if v is None:
            g[1] += 1
        else:
            g[0].append(v)

    small = lambda c: bool(caps) and (caps.get(c) is None or caps[c] < dt30.cap_min_eok())   # 감시 목록을 못 읽으면 안 거름
    need, until, mode = dt30.buy_need(), dt30.buy_until(), dt30.buy_mode()
    skipped = 0
    daily, every, whys = [], [], {}
    for day, raw in got:
        rows = json.loads(raw)
        try:                                           # 그날 봉(1m · 없으면 5m) — 산 줄의 매도 셈 재료(봉 줄 · 화면과 같은 셈)
            bars = _day_bars(proxy, day, [r["code"] for r in rows], end, today)
        except Exception as e:
            bars = {}
            print("  [단타 승률] %s 봉 못 읽음 — 30분 칸으로 셈 · %s" % (day, proxy.safe_message(e, 120)), flush=True)
        rets, miss, best = [], 0, []
        for r in rows:
            if small(r.get("code")):
                continue                               # 시가총액 문턱 밖(감시 목록에 없거나 문턱 아래 · 지금 목록으로) — 재권님 「응 빼 지금룰에 맞춰서 다 적용해」(11-23) · 판 셈(dt30.drop_small)과 같게
            if "chipTime" not in r:
                continue                               # v11 전 줄(쌓기 전) — 다음 바퀴에 다시 쌓임
            bp = dt30.buy_point({"meta": {"pxMinAt": r.get("_pxMinAt") or {}}, "times": r.get("_times") or []}, r, r["chipTime"], need, r.get("_open"), until, mode)
            if not bp:
                skipped += 1
                continue                               # 칩이 09:30 까지 N개 안 참 · 사는 값 못 잼 — 안 산 것(사는 셈 한 곳 dt30.buy_point · 화면과 같게 · 11-23 19:0x)
            if bp["at"].replace(":", "") >= end:
                continue                               # 매도 시각보다 늦게(같은 때 포함) 산 것은 안 산 것 — 화면 셈과 같게(재권님 「가」 11-20)
            r["buy"], r["buyAt"], r["chips"] = bp["px"], bp["at"], dt30.chips930(r, r["chipTime"], until)
            r["_barPer"], r["bars"] = bars.get(r["code"], (None, []))   # 그날 봉 그대로 — 산 봉 · 앞 봉 빼기는 _sell_bars 가(화면과 같게)
            r["n"] = len(set(r["chips"]) & set(dt30.ov_chips()))
            r["sell"], why = sell_of(r, end, rule)     # 매도 룰 — 부를 때 셈(셈 칸을 바꾸면 지난 날에도 바로 든다 · 수수료와 같은 길)
            whys[why] = whys.get(why, 0) + 1
            v = net_pct(r, fee)
            chips = sorted(set(r["chips"]))
            add("buySrc", bp["src"], v)                # 산 값 출처마다(9시 1분 값 · N분 값 · 든 때 값 · 칸 값) — 시간 창은 걷음(11-23 19:0x)
            for c in chips:
                add("chip", c, v)
                if late_chip(r, c):
                    add("chipLate", c, v)              # 산 뒤에 붙은 칩 — 다 세되 따로 보인다(재권님 「나」 11-23 16:5x · 산 때 몰랐던 칩 · 개념정의 덧)
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
            "buy": "사는 셈 한 곳(dt30.buy_point) — 칩은 %02d:%02d 까지 · 칩 %d개 찬 순간 · 9시 1분 이하면 9시 1분 값 · 1~5분 안이면 그 분 값 · 그 뒤 든 때 값 · 아니면 다음 30분 칸 값" % (dt30.CHIP_UNTIL + (need,)),
            "minChips": need, "chipUntil": "%02d:%02d" % dt30.CHIP_UNTIL, "buyLate930": until != dt30.CHIP_UNTIL, "sellBar": sell_bar(), "buyMode": mode, "notBought": skipped, "sell": end, "sellDef": SELL_AT, "sellNote": "매도 룰 — 단타 판 셈 칸 rules.dt30.set(화면과 같은 칸 · 빈 칸은 sellRule 의 기본) · 30분 칸마다 손절 · 꺾임 · 고점 · 시각 미달 · 횡보 중 처음 걸린 칸 값에 팖 · 안 걸리면 매도 시각(endAt · 빈칸이면 판 끝 sellDef) 이하 마지막 값 있는 칸 · 매도 시각보다 늦게(같은 때 포함) 든 종목은 안 산 것(셈에서 뺌) · 불타기는 안 듦", "sellRule": rule, "sellWhy": whys, "chipLateNote": "chipLate — 칩마다 산 뒤(판에 든 때 뒤)에 붙은 줄만 따로 셈 · chip 칸은 다 셈(재권님 「나」 11-23) · 칩 시각 chipAt 을 모르는 옛 판은 안 듦", "bigPct": BIG_PCT, "topDay": TOP_DAY,
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
