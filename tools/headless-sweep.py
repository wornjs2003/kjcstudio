# -*- coding: utf-8 -*-
"""주인 없이 남은 헤드리스 크롬을 닫는다 — 매일 새벽 한 번(2026-11-12 재권님 「가」 → 「만들어」).

    python3 tools/headless-sweep.py              닫는다 · 닫은 수와 줄어든 메모리를 logs/headless-sweep.log 에 한 줄
    python3 tools/headless-sweep.py --dry-run    닫지 않고 무엇이 걸리는지만 낸다

**왜** — 세션 임시 스크립트가 화면을 찍으려 띄운 헤드리스 크롬을 끝에 안 닫아 쌓였다. 11-12 11:42 에 하루 넘은 것
113 프로세스 · 2.8GB · 스왑 12GB 중 11.2GB 가 차 재권님이 「엔터치면 반응이 느린데」 하셨다. 그날 손으로 본체 16개를 닫아
스왑이 7.7GB 로 내려갔다.

**닫는 것 — 넷이 다 맞을 때만**
    ① 실제 크롬 본체 — 실행 파일이 Google Chrome.app 의 MacOS/Google Chrome 이고 `--type=` 이 없다(도우미 프로세스는 본체가 닫히면 함께 끝난다)
    ② `--headless` 로 떴다 — 재권님이 쓰시는 크롬은 이것이 없다
    ③ 부모가 끊겼다(ppid 1) — 띄운 스크립트 · 도구가 이미 끝났다. 도는 중인 shot.py · check-layout 의 크롬은 부모가 살아 있다
    ④ SWEEP_HOURS 시간 넘게 남았다
    이름이 같아도 크롬이 아니면 안 건드린다 — VS Code 의 copilot 도 `--headless` 로 뜬다(11-12 잼).
    8765 · 8764 서버는 크롬이 아니라 걸릴 일이 없다.

**종료코드** — 0 닫음 또는 닫을 것 없음 · 2 프로세스 목록을 못 읽음(못 쟀다 — 0 이 아니다).
예약은 launchd/kr.kjcstudio.headless-sweep.plist(매일 04:30) — 설치는 「켜기」 라 재권님 지시로 한다.
"""
import datetime
import os
import re
import signal
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SWEEP_HOURS = 12              # 이 시간 넘게 주인 없이 남은 것만 닫는다 — 한 곳
CHROME_BIN = "/Google Chrome.app/Contents/MacOS/Google Chrome"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "logs", "headless-sweep.log")


def _secs(etime):
    """ps 의 etime([[dd-]hh:]mm:ss)을 초로."""
    days, _, rest = etime.rpartition("-")
    parts = [int(x) for x in rest.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts
    return (int(days) if days else 0) * 86400 + h * 3600 + m * 60 + s


def procs():
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,etime=,rss=,command="], capture_output=True, text=True, timeout=20)
    if out.returncode:
        raise RuntimeError("ps 종료 %d" % out.returncode)
    rows = []
    for ln in out.stdout.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(.*)$", ln)
        if m:
            rows.append({"pid": int(m.group(1)), "ppid": int(m.group(2)), "age": _secs(m.group(3)),
                         "rss": int(m.group(4)), "cmd": m.group(5)})
    return rows


def targets(rows):
    out = []
    for r in rows:
        exe = r["cmd"].split(" --", 1)[0]
        if (exe.endswith(CHROME_BIN) and "--type=" not in r["cmd"] and "--headless" in r["cmd"]
                and r["ppid"] == 1 and r["age"] > SWEEP_HOURS * 3600):
            out.append(r)
    return out


def tree_rss(rows, pid):
    """본체와 그 아래 프로세스의 메모리 합(KB)."""
    kids = {}
    for r in rows:
        kids.setdefault(r["ppid"], []).append(r)
    total, stack = 0, [pid]
    by = {r["pid"]: r for r in rows}
    while stack:
        p = stack.pop()
        total += by[p]["rss"] if p in by else 0
        stack += [k["pid"] for k in kids.get(p, [])]
    return total


def main(argv):
    dry = "--dry-run" in argv
    try:
        rows = procs()
    except Exception as e:
        print("프로세스 목록을 못 읽었다(%s) — 못 쟀다 · 닫은 것 없음" % type(e).__name__)
        return 2
    ts = targets(rows)
    mb = sum(tree_rss(rows, t["pid"]) for t in ts) / 1024
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for t in ts:
        print("  %s %d · %.1f시간 · %s" % ("걸림" if dry else "닫음", t["pid"], t["age"] / 3600, t["cmd"][:120]))
    if dry:
        print("시험 — 닫을 것 %d개 · 함께 끝날 메모리 약 %.0fMB · 기준 %d시간 넘게 · 부모 끊김 · 크롬 본체" % (len(ts), mb, SWEEP_HOURS))
        return 0
    for t in ts:
        try:
            os.kill(t["pid"], signal.SIGTERM)
        except ProcessLookupError:
            pass
    if ts:
        time.sleep(5)
        alive = {r["pid"] for r in procs()}
        for t in ts:
            if t["pid"] in alive:
                try:
                    os.kill(t["pid"], signal.SIGKILL)
                except ProcessLookupError:
                    pass
    line = "%s · 닫음 %d · 약 %.0fMB · 기준 %d시간" % (now, len(ts), mb, SWEEP_HOURS)
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        print("기록을 못 남겼다(%s)" % type(e).__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
