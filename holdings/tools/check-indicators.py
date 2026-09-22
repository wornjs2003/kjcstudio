#!/usr/bin/env python3
"""화면과 서버의 지표 계산이 같은 값을 내는지 대조한다.

    holdings/js/chart.js        화면이 그리는 볼린저 · RSI · MACD (자바스크립트)
    holdings/server/signal_watch.py   서버가 신호를 판정하는 같은 계산 (파이썬)

둘은 같은 식을 쓴다. 언어가 달라 합칠 수 없다. 한쪽만 고치면
**「화면엔 신호가 보이는데 알림은 안 온다」** 가 되고, 둘 다 오류를 안 내므로
눈으로는 못 찾는다.

    python holdings/tools/check-indicators.py     맞으면 0, 어긋나면 1

`market.db` 에 쌓인 5분봉을 그대로 넣어 **봉마다** 값을 댄다.
어긋나면 그 봉과 두 값을 찍는다.

CLAUDE.md 「같은 값은 한 곳에만 둔다 → 못 합치면 대조 도구를 만든다」.
tools/check-kis-consts.py 와 같은 자리다 — 그쪽은 **상수**를 대고
이쪽은 **계산 결과**를 댄다.
"""
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
HOLDINGS = os.path.dirname(HERE)
ROOT = os.path.dirname(HOLDINGS)
DB = os.path.join(HOLDINGS, "market.db")

sys.path.insert(0, os.path.join(HOLDINGS, "server"))

# 부동소수라 완전히 같기를 기대하면 안 된다. 상대오차로 본다.
# **이 값은 여기 한 곳에만 둔다.**
TOL = 1e-9

# 몇 종목 · 몇 봉을 댈지. 많이 댈수록 느리지만 더 넓게 본다.
CODES = 6
BARS = 200


def fail(msg):
    print("  " + msg)
    return False


def load_bars():
    """market.db 에서 5분봉을 꺼낸다. 종목마다 과거→최신 순."""
    if not os.path.exists(DB):
        return None, "market.db 가 없습니다 — 서버를 한 번 띄워 주십시오: %s" % DB
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    codes = [r[0] for r in con.execute(
        "SELECT code, COUNT(*) n FROM candles WHERE period='5m' "
        "GROUP BY code HAVING n >= ? ORDER BY n DESC LIMIT ?", (BARS, CODES))]
    out = {}
    for c in codes:
        rows = con.execute(
            "SELECT ts, open, high, low, close, volume FROM candles "
            "WHERE period='5m' AND code=? ORDER BY ts DESC LIMIT ?", (c, BARS)).fetchall()
        out[c] = [dict(r) for r in reversed(rows)]
    con.close()
    if not out:
        return None, ("5분봉이 %d개 이상인 종목이 없습니다. "
                      "서버를 띄워 두면 미리받기가 쌓습니다." % BARS)
    return out, None


# 봉 데이터를 **파일로** 넘긴다. 인자로 주면 윈도우 명령줄 길이 제한
# (약 32,000자)에 걸린다 — 6종목 × 200봉이면 10만 자가 넘는다.
JS = r"""
import { readFileSync } from 'node:fs';
import { bollinger, rsi, macd } from '../js/chart.js';
const bars = JSON.parse(readFileSync(process.argv[2], 'utf-8'));
const out = {};
for (const [code, candles] of Object.entries(bars)) {
  const bb = bollinger(candles, '5m');
  const r  = rsi(candles, '5m');
  const m  = macd(candles, '5m');
  out[code] = { up: bb.vUp, lo: bb.vLo, rsi: r.values,
                line: m.vLine, signal: m.vSignal, hist: m.vHist };
}
process.stdout.write(JSON.stringify(out));
"""


def run_js(bars):
    """chart.js 를 node 로 돌려 같은 값을 받는다."""
    script = os.path.join(HERE, "_check-indicators.mjs")
    data = os.path.join(HERE, "_check-indicators.json")
    io.open(script, "w", encoding="utf-8", newline="\n").write(JS)
    io.open(data, "w", encoding="utf-8", newline="\n").write(
        json.dumps(bars, ensure_ascii=False))
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        _clean(script, data)
        return None, "node 를 찾지 못했습니다 (PATH 에 없습니다)"
    try:
        p = subprocess.run(
            [node, script, data],
            cwd=HERE, capture_output=True, timeout=120)
        if p.returncode != 0:
            return None, (p.stderr.decode("utf-8", "replace").strip().splitlines() or ["(없음)"])[-1]
        return json.loads(p.stdout.decode("utf-8")), None
    except FileNotFoundError:
        return None, "node 를 실행하지 못했습니다"
    except subprocess.TimeoutExpired:
        return None, "node 가 제때 안 끝났습니다"
    finally:
        _clean(script, data)


def _clean(*paths):
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


def close_enough(a, b):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= TOL * scale


def main():
    print("지표 대조 — chart.js(화면) ↔ signal_watch.py(서버)")
    print()

    bars, err = load_bars()
    if err:
        print("  " + err)
        return 1

    try:
        import signal_watch as sig_mod     # holdings/server/signal_watch.py
    except Exception as e:
        print("  signal_watch.py 를 불러오지 못했습니다: %s" % e)
        return 1

    js, err = run_js(bars)
    if err:
        print("  chart.js 를 node 로 돌리지 못했습니다: %s" % err)
        return 1

    bad = 0
    checked = 0
    for code, candles in bars.items():
        closes = [c["close"] for c in candles]
        py = {
            "up": bollinger_up(sig_mod, closes),
            "lo": bollinger_lo(sig_mod, closes),
            "rsi": sig_mod.rsi(closes),
        }
        line, signal, hist = sig_mod.macd(closes)
        py["line"], py["signal"], py["hist"] = line, signal, hist

        for key in ("up", "lo", "rsi", "line", "signal", "hist"):
            a, b = py[key], js[code][key]
            if len(a) != len(b):
                bad += 1
                print("  %s %-6s 길이가 다릅니다 — 파이썬 %d · JS %d"
                      % (code, key, len(a), len(b)))
                continue
            for i in range(len(a)):
                checked += 1
                if not close_enough(a[i], b[i]):
                    bad += 1
                    print("  %s %-6s 봉 %d (ts %s) — 파이썬 %r · JS %r"
                          % (code, key, i, candles[i]["ts"], a[i], b[i]))
                    if bad >= 10:
                        print("  … 열 개까지만 찍습니다")
                        break
            if bad >= 10:
                break
        if bad >= 10:
            break

    print("  종목 %d · 값 %d개 대 봤습니다 (허용 오차 %g)"
          % (len(bars), checked, TOL))
    if bad:
        print()
        print("  어긋납니다. 한쪽만 고친 것이 있는지 보십시오 —")
        print("    holdings/js/chart.js        bollinger · rsi · macd")
        print("    holdings/server/signal_watch.py   같은 이름의 함수")
        return 1
    print("  같습니다.")
    return 0


def bollinger_up(m, closes):
    return m.bollinger(closes)[0]


def bollinger_lo(m, closes):
    return m.bollinger(closes)[1]


if __name__ == "__main__":
    sys.exit(main())
