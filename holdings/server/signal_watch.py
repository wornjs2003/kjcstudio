# -*- coding: utf-8 -*-
"""볼린저 하단 + 양봉 + MACD + RSI 가 **동시에** 맞는 자리를 찾아 알린다.

**파일 이름이 `signal.py` 가 아닌 이유** — 그것은 **파이썬 표준 모듈 이름**이다.
`import signal` 이 표준 쪽을 잡아 이 파일이 안 불린다. 대조 도구를 돌리다
`AttributeError: module 'signal' has no attribute 'bollinger'` 로 잡았다.

2026-09-22 지시 — 「볼린저 밴드의 하단을 터치하고 양봉으로 될 때를 체크해
줄 수 있을까? 실시간이어야 해. 여기서 MACD 가 매수세가 약해지는 신호와
RSI 가 30에서 상승으로 전환할 때 요 3개의 시그널이 될 때 알아야 하는데」.

바닥에서 돌아서는 자리를 잡으려는 것이다.


■ 왜 `dart.py` 루프에 안 얹는가

그 루프는 주말·장 시간과 무관하게 돌며 공시를 본다. 신호는 **장중에 새 5분봉이
생길 때만** 보면 된다. 섞으면 「공시 때문에 도는 김에 신호도 본다」 가 되어
언제 보는지가 흐려진다. `dart.py` 에서 가져다 쓰는 것은 `telegram_send()`
하나이고 그 함수는 **부르기만** 한다.


■ KIS 를 새로 부르지 않는다

`kis_proxy.py` 의 미리받기가 이미 코스피 상위 100여 종목의 5분봉을
`market.db` 에 쌓고 있다. 여기서는 **읽기만** 한다. 종목을 112개까지 늘려도
호출이 안 는다.


■ 계산은 `js/chart.js` 와 **같아야 한다**

화면이 그리는 볼린저·RSI·MACD 와 여기 판정이 다르면 「화면엔 신호가 보이는데
알림은 안 온다」 가 된다. 언어가 달라 합칠 수 없으므로 **대조 도구**를 둔다.

    python holdings/tools/check-indicators.py

`chart.js` 의 함수를 node 로 돌려 같은 봉에서 같은 값이 나오는지 본다.
**이 파일의 계산식을 고치면 그쪽도 함께 고치고 그 도구를 돌려야 한다.**
CLAUDE.md 「같은 값은 한 곳에만 둔다 → 못 합치면 대조 도구를 만든다」.
"""

import threading
import time

import dart

# ── 정하는 값 — 여기 한 곳에 모은다 ────────────────────────────
#
# 2026-09-22 조사에서 나온 값이다. 과거 5분봉(112종목 · 12일)으로 세어
# **관심종목 여덟이면 하루 0.6번** 이 나왔다. 더 자주 받으시려면
# SAME_BAR 를 False 로 두면 된다 (아래 참고).

WATCH = ["005930", "000660", "035420", "035720",
         "005380", "373220", "207940", "068270"]

PERIOD = "5m"          # 일봉으로는 15개월에 1번이라 안 된다 (실측)
NEED_BARS = 120        # 판정에 쓸 봉 수. MACD 가 26+9 를 쓰므로 넉넉히

BB_PERIOD, BB_MULT = 20, 2      # 볼린저 — chart.js 와 같은 값
RSI_PERIOD = 14                 # Wilder
RSI_LINE = 30                   # 이 선을 위로 뚫을 때
MACD_FAST, MACD_SLOW, MACD_SIG = 12, 26, 9

# 셋이 **같은 봉**에서 맞아야 하는가.
# False 면 WINDOW 봉 안에 흩어져 있어도 친다 (조사: 같은 봉 101번 · 5봉 143번).
SAME_BAR = True
WINDOW = 5

SEND_MAX_PER_DAY = 3   # 한 종목에 하루 몇 번까지
LOOP_SEC = 60          # 도는 주기. 계산은 새 봉이 생겼을 때만 한다

# **보낼지 말지.**
#
# 텔레그램은 **이미 켜져 있다** — `secrets.json` 의 `telegram.bot_token` 과
# `chat_id` 에 값이 있어서 `dart.telegram_send()` 를 부르면 바로 간다.
# (`_꺼둠` 메모는 2026-09-14 것이고 코드가 안 본다. 그것을 읽고 「지금도
# 꺼져 있다」 로 잘못 적었던 일이 있다 — 「설명이 이미 있으면 의심할 계기조차
# 없다」 에 걸린 자리다.)
#
# 그래서 **기본을 「안 보냄」 으로 둔다.** 만드는 동안 재권님 폰에 시험
# 알림이 가면 안 된다. 판정은 그대로 하고 로그에만 남긴다.
SEND = False


# ── 지표 — js/chart.js 를 그대로 옮긴 것 ───────────────────────
# 식을 고치면 그쪽도 고치고 tools/check-indicators.py 를 돌린다.

def ema(values, period):
    k = 2.0 / (period + 1)
    out = [None] * len(values)
    acc = 0.0
    for i, v in enumerate(values):
        if i < period - 1:
            acc += v
            continue
        if i == period - 1:
            acc += v
            out[i] = acc / period
            continue
        out[i] = v * k + out[i - 1] * (1 - k)
    return out


def bollinger(closes, period=BB_PERIOD, mult=BB_MULT):
    """위·아래 띠. 가운데 선은 MA20 과 같아 안 만든다 (chart.js 와 같다)."""
    up = [None] * len(closes)
    lo = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        win = closes[i - period + 1:i + 1]
        mean = sum(win) / period
        # **모집단 표준편차**(n 으로 나눈다). chart.js 도 같다 —
        # n-1 로 나누면 띠가 조금 넓어져 「터치」 판정이 달라진다.
        var = sum((c - mean) ** 2 for c in win) / period
        sd = var ** 0.5
        up[i] = mean + sd * mult
        lo[i] = mean - sd * mult
    return up, lo


def rsi(closes, period=RSI_PERIOD):
    """Wilder 방식. 처음 period 개는 단순평균, 그 뒤는 지수평활."""
    vals = [None] * len(closes)
    if len(closes) <= period:
        return vals
    gain = loss = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        if d >= 0:
            gain += d
        else:
            loss -= d
    gain /= period
    loss /= period
    vals[period] = 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        gain = (gain * (period - 1) + (d if d > 0 else 0)) / period
        loss = (loss * (period - 1) + (-d if d < 0 else 0)) / period
        vals[i] = 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    return vals


def macd(closes, fast=MACD_FAST, slow=MACD_SLOW, sig=MACD_SIG):
    """(macd선, 신호선, 히스토그램). 신호선은 macd 가 생긴 뒤부터 센다."""
    e_fast = ema(closes, fast)
    e_slow = ema(closes, slow)
    diff = [None if (e_fast[i] is None or e_slow[i] is None) else e_fast[i] - e_slow[i]
            for i in range(len(closes))]
    start = next((i for i, v in enumerate(diff) if v is not None), -1)
    signal = [None] * len(closes)
    if start >= 0:
        raw = ema(diff[start:], sig)
        for i, v in enumerate(raw):
            if v is not None:
                signal[start + i] = v
    hist = [None if (diff[i] is None or signal[i] is None) else diff[i] - signal[i]
            for i in range(len(closes))]
    return diff, signal, hist


# ── 판정 ──────────────────────────────────────────────────────

def judge(rows):
    """마지막 봉이 신호인가. rows 는 과거→최신 순의 dict 목록.

    Returns: None 또는 {"ts", "close", "why": {...}}

    ① 볼린저 하단을 **저가가** 건드리고 그 봉이 **양봉**
       — 종가 기준으로 하면 12일에 6번뿐이라 너무 엄격했다 (조사)
    ② MACD 히스토그램이 **음수인데 직전보다 큼** (매도세가 약해진다)
       — 「매수세가 약해진다」 를 글자대로 읽으면 ①③과 방향이 반대이고,
         실제로 12일 동안 112종목에서 **1번**뿐이었다. 숫자가 답을 냈다
    ③ RSI 가 직전 < 30, 이번 ≥ 30 (아래에서 위로 뚫는다)
    """
    if len(rows) < NEED_BARS:
        return None

    closes = [r["close"] for r in rows]
    _, bb_lo = bollinger(closes)
    rsi_v = rsi(closes)
    _, _, hist = macd(closes)

    def c1(i):
        r = rows[i]
        return bb_lo[i] is not None and r["low"] <= bb_lo[i] and r["close"] > r["open"]

    def c2(i):
        return (i > 0 and hist[i] is not None and hist[i - 1] is not None
                and hist[i] < 0 and hist[i] > hist[i - 1])

    def c3(i):
        return (i > 0 and rsi_v[i] is not None and rsi_v[i - 1] is not None
                and rsi_v[i - 1] < RSI_LINE <= rsi_v[i])

    last = len(rows) - 1
    if not c1(last):
        return None

    if SAME_BAR:
        ok2, ok3 = c2(last), c3(last)
    else:
        lo_i = max(0, last - WINDOW + 1)
        ok2 = any(c2(i) for i in range(lo_i, last + 1))
        ok3 = any(c3(i) for i in range(lo_i, last + 1))
    if not (ok2 and ok3):
        return None

    return {
        "ts": rows[last]["ts"],
        "close": rows[last]["close"],
        "why": {
            "하단": round(bb_lo[last], 2),
            "저가": rows[last]["low"],
            "rsi": round(rsi_v[last], 1),
            "hist": round(hist[last], 4),
        },
    }


# ── 보낸 기록 — 서버를 다시 띄워도 남아야 한다 ──────────────────

def _init(proxy):
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS signal_sent (
            code TEXT NOT NULL, ts INTEGER NOT NULL, day TEXT NOT NULL,
            sent_at REAL NOT NULL, PRIMARY KEY (code, ts))""")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_signal_day ON signal_sent(code, day)")


def _already(proxy, code, ts):
    with proxy._db_lock, proxy.db_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM signal_sent WHERE code=? AND ts=?", (code, ts)).fetchone() is not None


def _today_count(proxy, code, day):
    with proxy._db_lock, proxy.db_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM signal_sent WHERE code=? AND day=?", (code, day)).fetchone()[0]


def _mark(proxy, code, ts, day):
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO signal_sent VALUES (?,?,?,?)",
                     (code, ts, day, time.time()))


# ── 한 바퀴 ───────────────────────────────────────────────────

def check_once(proxy, names=None):
    """관심종목을 한 번 훑는다. 보낸(또는 보낼 뻔한) 건수를 돌려준다."""
    _init(proxy)
    day = time.strftime("%Y%m%d")
    hit = 0

    for code in WATCH:
        try:
            rows = proxy.read_candles(code, PERIOD, NEED_BARS)
            sig = judge(rows)
            if not sig:
                continue
            if _already(proxy, code, sig["ts"]):
                continue
            if _today_count(proxy, code, day) >= SEND_MAX_PER_DAY:
                continue

            name = (names or {}).get(code, code)
            text = format_message(code, name, sig)
            if SEND:
                ok, err = dart.telegram_send(text)
                if not ok:
                    print("  [신호] 보내지 못했습니다: %s" % err)
            else:
                # 만드는 동안에는 로그에만 남긴다 (위 SEND 설명 참고)
                print("  [신호·안보냄] %s" % text.replace("\n", " / "))
            _mark(proxy, code, sig["ts"], day)
            hit += 1
        except Exception as e:
            # 한 종목이 실패해도 나머지는 본다 (prefillMinutes 와 같은 자리)
            print("  [신호] %s 판정 실패: %s" % (code, type(e).__name__))
    return hit


def format_message(code, name, sig):
    w = sig["why"]
    return ("📉 %s (%s) 바닥 신호\n"
            "현재가 %s원\n"
            "볼린저 하단 %s · 저가 %s\n"
            "RSI %s · MACD 히스토그램 %s\n"
            "5분봉 기준 · 참고용입니다"
            % (name, code, format(sig["close"], ","),
               format(w["하단"], ","), format(w["저가"], ","),
               w["rsi"], w["hist"]))


# ── 루프 ──────────────────────────────────────────────────────

_last_ts = {}          # code -> 마지막으로 본 봉. 새 봉일 때만 계산한다


def start(proxy, names=None):
    """서버가 뜰 때 한 번 부른다. 장중에만 돈다."""

    def loop():
        time.sleep(20)          # 서버가 막 뜬 참이라 첫 화면에 양보한다
        while True:
            try:
                if _in_session():
                    fresh = False
                    for code in WATCH:
                        rows = proxy.read_candles(code, PERIOD, 1)
                        ts = rows[0]["ts"] if rows else None
                        if ts and _last_ts.get(code) != ts:
                            _last_ts[code] = ts
                            fresh = True
                    # 새 봉이 하나도 없으면 계산을 건너뛴다.
                    # 60초마다 돌지만 5분봉은 5분에 하나씩만 생긴다.
                    if fresh:
                        n = check_once(proxy, names)
                        if n:
                            print("  [신호] %d건" % n)
            except Exception as e:
                print("  [신호] 예기치 못한 오류: %s" % type(e).__name__)
            time.sleep(LOOP_SEC)

    threading.Thread(target=loop, daemon=True, name="signal-watch").start()
    return True


def _in_session(now=None):
    """한국 장중인가 (평일 09:00~15:30).

    `dart.py` 의 `_should_poll` 과 다르다 — 그쪽은 공시라 장 밖에도 본다.
    """
    t = now or time.localtime()
    if t.tm_wday >= 5:
        return False
    mins = t.tm_hour * 60 + t.tm_min
    return 9 * 60 <= mins <= 15 * 60 + 30
