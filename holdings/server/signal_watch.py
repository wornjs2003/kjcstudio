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
RSI_LOW = 30                    # **바닥** — 이 선을 **위로** 뚫을 때
RSI_HIGH = 70                   # **고점** — 이 선을 **아래로** 뚫을 때
MACD_FAST, MACD_SLOW, MACD_SIG = 12, 26, 9

# 셋이 **같은 봉**에서 맞아야 하는가.
# False 면 WINDOW 봉 안에 흩어져 있어도 친다 (조사: 같은 봉 101번 · 5봉 143번).
SAME_BAR = True
WINDOW = 5

# **하루 횟수를 안 막는다** (2026-09-23 지시 — 「횟수는 제한을 두지 않는다」).
# 전에는 한 종목에 하루 3번까지였다.
#
# **같은 봉이 여러 번 가는 것은 따로 막는다** — 그것은 횟수 제한이 아니라
# 기록(`signal_sent`)이 막는 자리다. 60초마다 도는데 5분봉이라 **같은 봉을
# 다섯 번 본다.** 기록이 없으면 한 신호가 다섯 번 간다.
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
SEND = True


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

    Returns: **신호 목록** (0~2개). 각각 {"kind", "ts", "close", "why"}

    **둘은 대칭이다** (2026-09-23 지시 — 「이 두가지 경우에 다 메세지가 와야해」).

        바닥(low)   ① 볼린저 **하단**을 **저가**가 건드리고 그 봉이 **양봉**
                    ② MACD 히스토그램이 **음수인데 직전보다 큼** (매도세가 약해진다)
                    ③ RSI 가 직전 < 30, 이번 ≥ 30 (**아래에서 위로** 뚫는다)

        고점(high)  ① 볼린저 **상단**을 **고가**가 건드리고 그 봉이 **음봉**
                    ② MACD 히스토그램이 **양수인데 작아짐** (매수세가 약해진다)
                    ③ RSI 가 직전 > 70, 이번 ≤ 70 (**위에서 아래로** 뚫는다)

    **「매수세가 약해지는 신호」 는 고점 쪽 자리였다 — 되돌리지 않는다.**
    바닥 신호를 먼저 만들 때(2026-09-22) 그 말을 글자대로 읽으면 나머지 둘과
    방향이 반대라 12일에 1번뿐이어서 **「매도세 약화」 로 바꿨다.** 다음 날
    재권님이 고점 신호를 말씀하시며 갈렸다 — **처음부터 두 신호를 함께 보고
    계셨고**, 「매수세 약화」 는 이쪽이었다. 바닥 쪽 판단도 그대로 맞다.

    **셋을 한 함수로 쓰지 않고 `kind` 로 가른다.** 나란히 두면 대칭이 눈에
    보이고, 한쪽만 고치는 일이 줄어든다.
    """
    if len(rows) < NEED_BARS:
        return []

    closes = [r["close"] for r in rows]
    bb_up, bb_lo = bollinger(closes)
    rsi_v = rsi(closes)
    _, _, hist = macd(closes)
    last = len(rows) - 1

    def band(i, kind):
        """① 띠를 건드리고 봉 방향이 맞는가."""
        r = rows[i]
        if kind == "low":
            return bb_lo[i] is not None and r["low"] <= bb_lo[i] and r["close"] > r["open"]
        return bb_up[i] is not None and r["high"] >= bb_up[i] and r["close"] < r["open"]

    def hist_turn(i, kind):
        """② 히스토그램이 돌아서는가."""
        if not (i > 0 and hist[i] is not None and hist[i - 1] is not None):
            return False
        if kind == "low":
            return hist[i] < 0 and hist[i] > hist[i - 1]
        return hist[i] > 0 and hist[i] < hist[i - 1]

    def rsi_cross(i, kind):
        """③ RSI 가 선을 뚫는가."""
        if not (i > 0 and rsi_v[i] is not None and rsi_v[i - 1] is not None):
            return False
        if kind == "low":
            return rsi_v[i - 1] < RSI_LOW <= rsi_v[i]
        return rsi_v[i - 1] > RSI_HIGH >= rsi_v[i]

    out = []
    for kind in ("low", "high"):
        if not band(last, kind):
            continue
        if SAME_BAR:
            ok2, ok3 = hist_turn(last, kind), rsi_cross(last, kind)
        else:
            lo_i = max(0, last - WINDOW + 1)
            ok2 = any(hist_turn(i, kind) for i in range(lo_i, last + 1))
            ok3 = any(rsi_cross(i, kind) for i in range(lo_i, last + 1))
        if not (ok2 and ok3):
            continue
        r = rows[last]
        out.append({
            "kind": kind,
            "ts": r["ts"],
            "close": r["close"],
            "why": {
                # 라벨(「하단/상단」 · 「저가/고가」)은 `format_message` 가 붙인다.
                "band": round(bb_lo[last] if kind == "low" else bb_up[last], 2),
                "touch": r["low"] if kind == "low" else r["high"],
                "rsi": round(rsi_v[last], 1),
                "hist": round(hist[last], 4),
            },
        })
    return out


# ── 보낸 기록 — 서버를 다시 띄워도 남아야 한다 ──────────────────

# **`kind` 가 열쇠에 들어간다.** 없으면 한 봉에 한 신호만 기록되어,
# 한쪽이 찍힌 봉에서 다른 쪽이 「이미 보냈다」 로 걸린다.
_SCHEMA = """CREATE TABLE IF NOT EXISTS signal_sent (
    code TEXT NOT NULL, ts INTEGER NOT NULL, kind TEXT NOT NULL,
    day TEXT NOT NULL, sent_at REAL NOT NULL,
    PRIMARY KEY (code, ts, kind))"""


def _init(proxy):
    with proxy._db_lock, proxy.db_conn() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(signal_sent)")]
        old = conn.execute("SELECT 1 FROM sqlite_master "
                           "WHERE type='table' AND name='signal_sent_old'").fetchone()
        if cols and "kind" not in cols:
            # **옛 표를 옮긴다.** `CREATE TABLE IF NOT EXISTS` 는 이미 있는 표의
            # 칸을 안 바꾸므로, 여기서 직접 옮기지 않으면 **새 칸이 영영 안 생긴다.**
            # `kind` 가 생기기 전 것은 전부 바닥 신호였다 (고점은 2026-09-23 에 생겼다).
            conn.execute("ALTER TABLE signal_sent RENAME TO signal_sent_old")
            conn.execute(_SCHEMA)
            conn.execute("INSERT OR IGNORE INTO signal_sent "
                         "SELECT code, ts, 'low', day, sent_at FROM signal_sent_old")
            conn.execute("DROP TABLE signal_sent_old")
        else:
            conn.execute(_SCHEMA)
            if old:
                # **앞선 옮기기가 중간에 끊겼다.** 이어서 마저 옮긴다.
                #
                # `ALTER TABLE` · `CREATE TABLE` 은 **되돌아가지 않는다** —
                # 파이썬 `sqlite3` 가 그 앞에서 트랜잭션을 안 여는 구간이 있어,
                # `INSERT` 가 터지면 **두 표가 다 남는다.** 그러면 다음에 돌 때
                # `kind` 가 보여 위 갈래를 건너뛰고, **옛 데이터가 `_old` 에
                # 영영 갇힌다.** 그 자리를 여기서 받는다.
                #
                # 2026-09-23 에 `홈페이지_정리` 가 임시 DB 로 `INSERT` 를 일부러
                # 터뜨려 찾았다. **지금은 세 폴더 다 행 0 이라 걸릴 것이 없지만,**
                # 쌓인 뒤에 칸을 또 늘리는 날이 오면 그때 든다.
                conn.execute("INSERT OR IGNORE INTO signal_sent "
                             "SELECT code, ts, 'low', day, sent_at FROM signal_sent_old")
                conn.execute("DROP TABLE signal_sent_old")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_signal_day ON signal_sent(code, day)")


def _already(proxy, code, ts, kind):
    with proxy._db_lock, proxy.db_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM signal_sent WHERE code=? AND ts=? AND kind=?",
            (code, ts, kind)).fetchone() is not None


def _mark(proxy, code, ts, kind, day):
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO signal_sent VALUES (?,?,?,?,?)",
                     (code, ts, kind, day, time.time()))


# ── 한 바퀴 ───────────────────────────────────────────────────

def check_once(proxy, names=None):
    """관심종목을 한 번 훑는다. 보낸(또는 보낼 뻔한) 건수를 돌려준다."""
    _init(proxy)
    day = time.strftime("%Y%m%d")
    hit = 0

    for code in WATCH:
        try:
            rows = proxy.read_candles(code, PERIOD, NEED_BARS)
            for sig in judge(rows):
                # **같은 봉 중복만 막는다.** 하루 횟수는 안 센다 (위 LOOP_SEC 주석).
                if _already(proxy, code, sig["ts"], sig["kind"]):
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
                _mark(proxy, code, sig["ts"], sig["kind"], day)
                hit += 1
        except Exception as e:
            # 한 종목이 실패해도 나머지는 본다 (prefillMinutes 와 같은 자리)
            print("  [신호] %s 판정 실패: %s" % (code, type(e).__name__))
    return hit


def format_message(code, name, sig):
    """**📉 는 「내려온 자리」 · 📈 는 「올라간 자리」** — 지금 어디 있는지를 가리킨다.
    사고팔라는 말은 안 쓴다. 끝의 「참고용입니다」 도 그래서 둔다."""
    w = sig["why"]
    low = sig["kind"] == "low"
    return ("%s %s (%s) %s\n"
            "현재가 %s원\n"
            "볼린저 %s %s · %s %s\n"
            "RSI %s · MACD 히스토그램 %s\n"
            "5분봉 기준 · 참고용입니다"
            % ("📉" if low else "📈", name, code,
               "바닥 신호" if low else "고점 신호",
               format(sig["close"], ","),
               "하단" if low else "상단", format(w["band"], ","),
               "저가" if low else "고가", format(w["touch"], ","),
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
