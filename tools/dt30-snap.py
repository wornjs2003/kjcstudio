#!/usr/bin/env python3
"""단타 판 09:01 기록 — 장 연 1분 뒤 단타 판을 찍어 남기고, 그 뒤로 지금 판과 대조해 바뀐 것을 남긴다 (2026-11-27 지시).

재권님 말씀 — 「9시1분이 되면 단타칩에 있는 목록들 화면으로 챕쳐해서 남겨놔. 계속 바뀌는데 이상한 핑계를 대네」(12:0x · 작업우선순위 창)
→ 안에 「만들고 항상 대조해서 바뀐게 있는지 확인이 필요해」(12:1x · 개념정의 창).

    python3 tools/dt30-snap.py            때를 보고 고른다 — 오늘 기록이 없고 낮 12시 전이면 찍기, 아니면 대조
    python3 tools/dt30-snap.py snap       찍기 — 서버가 셈 칸을 굳힐 때(판 meta.buySetAt)까지 기다렸다 판 값 · 그림
    python3 tools/dt30-snap.py compare    대조 — 오늘(또는 --day) 찍은 판과 지금 판을 견줘 바뀐 것을 남김
    python3 tools/dt30-snap.py index      보기 페이지만 다시 만듦
    --day YYYYMMDD   대조 · 찍기의 날(기본 오늘) · --now 기다리지 않고 바로 찍음(시험)

남기는 곳 — `snaps/dt30/<날>/`(저장소 밖 · .gitignore · 8765 가 낸다 — 보기 `http://localhost:8765/snaps/dt30/`)
    board-<포트>.json      그 순간 서버 판 값(`/api/kis/dt30`) — 그림은 다 그려지기까지 20~60초 늦어 「그 초」 는 이것이 기준
    screen-<포트>.png      단타 판 표(`#dt-box` · 시황분석1 답) 그림 · 옆에 -보기.html(tools/shot.py 가 만듦)
    status.json            찍은 시각 · 못 찍은 까닭
    changes.json           대조할 때마다 한 줄 — 바뀐 것 목록(없으면 「바뀐 것 없음」)
두 포트 — 8764(메인 · 재권님 · 외부접속이 보는 화면) · 8765(개발 서버 · 알림을 셈하는 자리).

늦게 여는 날 — 기다리는 끝은 판 meta 의 여는 시각이 아니라 셈 칸 굳힘(buySetAt · 서버가 여는 시각 + 1분에 적음)이라 그날만큼 저절로 밀린다.
쉬는 날 — 장 시각 주소(`/api/alerts/market-hours`)가 open False 면 찍지 않고 status 에 「쉬는 날」.
못 읽으면 0 · 빈 기록으로 두지 않고 status · changes 에 「못 잼 · 까닭」 을 남긴다.
"""
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "snaps", "dt30")
PORTS = (8764, 8765)                 # 메인 · 개발 서버
WAIT_UNTIL = (11, 30)                # 굳힘을 이 시각까지 기다림 — 늦게 여는 날(수능 10:00)도 덮게
POLL_SEC = 5
SHOT_AT = "#dt-box"                  # 단타 판 표 전체(시황분석1 11-27 답)
SHOT_TALL = 3000                     # 표가 창 한 장을 넘어 세로로 길게
SHOT_WAIT = 75                       # 첫 그림까지 20~60초(지난 판 받기 · 시황분석1 잼) — 넉넉히
SNAP_BEFORE = 12                     # 때를 보고 고를 때 이 시 전이면 찍기
KST = timezone(timedelta(hours=9))


def now():
    return datetime.now(KST)


def get(port, path, timeout=60):
    with urllib.request.urlopen("http://localhost:%d%s" % (port, path), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def board(port, day=None):
    j = get(port, "/api/kis/dt30" + ("?day=%s" % day if day else ""))
    return j.get("data", j)


def day_dir(day):
    d = os.path.join(BASE, day)
    os.makedirs(d, exist_ok=True)
    return d


def rjson(path, dflt=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return dflt


def wjson(path, v, indent=1):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=indent, default=str, separators=None if indent else (",", ":"))
    os.replace(tmp, path)


def is_open_day(day):
    """True · False · None(못 잼)."""
    try:
        t = (get(8765, "/api/alerts/market-hours", 20).get("data") or {}).get("today") or {}
        return t.get("open") if t.get("day") == day else None
    except Exception:
        return None


def slim(b):
    """남길 판 — 줄마다 1분봉(rows[].bars · 판 하나에 5MB 남짓)은 뺌 · 대조에 안 쓰고 지난 1분봉은 DB 에 그대로 있다(11-27 잼)."""
    b = dict(b)
    strip = lambda rs: [{k: v for k, v in r.items() if k not in ("bars", "barSrc")} for r in rs or []]
    b["rows"] = strip(b.get("rows"))
    if (b.get("meta") or {}).get("outRows"):
        b["meta"] = dict(b["meta"], outRows=strip(b["meta"]["outRows"]))
    return b


def snap(day, no_wait=False):
    d = day_dir(day)
    st = {"day": day, "startedAt": now().strftime("%H:%M:%S"), "ports": {}}
    op = is_open_day(day)
    if op is False:
        st["why"] = "쉬는 날"
        wjson(os.path.join(d, "status.json"), st)
        return st
    if op is None:
        st["openNote"] = "장 시각 못 잼 — 굳힘을 기다려 봄"
    end = now().replace(hour=WAIT_UNTIL[0], minute=WAIT_UNTIL[1], second=0)
    got = {}
    while True:                                          # 굳힘(buySetAt)이 적힌 판이 오면 바로 판 값을 남김 — 포트마다
        for p in PORTS:
            if p in got:
                continue
            try:
                b = board(p)
            except Exception as e:
                st["ports"].setdefault(str(p), {})["lastErr"] = type(e).__name__
                continue
            m = b.get("meta") or {}
            if b.get("day") == day and (m.get("buySetAt") or no_wait):
                got[p] = b
                wjson(os.path.join(d, "board-%d.json" % p), slim(b), indent=None)   # 판 값은 빈칸 없이(하루 1MB 남짓)
                st["ports"][str(p)] = {"boardAt": now().strftime("%H:%M:%S"), "buySetAt": m.get("buySetAt"),
                                       "openAt": m.get("openAt"), "lateMin": m.get("lateMin"), "rows": len(b.get("rows") or [])}
        if len(got) == len(PORTS) or now() >= end:
            break
        time.sleep(POLL_SEC)
    for p in PORTS:
        if p not in got:
            st["ports"].setdefault(str(p), {})["why"] = "굳힘이 %02d:%02d 까지 안 옴 · 판 못 받음" % WAIT_UNTIL
            continue
        png = os.path.join(d, "screen-%d.png" % p)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "shot.py"), "http://localhost:%d/company-setup/strategy.html" % p,
                            png, "--at", SHOT_AT, "--tall", str(SHOT_TALL), "--wait", str(SHOT_WAIT)],
                           capture_output=True, text=True, timeout=SHOT_WAIT + 240)
        st["ports"][str(p)]["shotAt"] = now().strftime("%H:%M:%S")
        if r.returncode != 0 or not os.path.isfile(png):
            st["ports"][str(p)]["shotWhy"] = "그림 못 찍음 · 종료 %d · %s" % (r.returncode, (r.stderr or r.stdout).strip()[-200:])
    st["doneAt"] = now().strftime("%H:%M:%S")
    wjson(os.path.join(d, "status.json"), st)
    return st


def facts(b):
    """대조할 것 — 차례(줄 순서) · 줄마다 칩 · 조합(된 때 · 조합 · 산 값) · 매수 차례 · 보낸 매수 알림 · 고른 조합."""
    rows = b.get("rows") or []
    m = b.get("meta") or {}
    cb = lambda r: r.get("comboBuy") or {}
    return {
        "order": [r.get("code") for r in rows],
        "chips": {r.get("code"): sorted(r.get("chips") or []) for r in rows},
        "combo": {r.get("code"): [cb(r).get("key"), cb(r).get("buyAt"), cb(r).get("px")] for r in rows if r.get("comboBuy")},
        "buyOrder": [x.get("code") for x in (m.get("buyRule") or {}).get("order") or []],
        "sent": sorted((m.get("tgBuy") or {}).keys()),
        "picked": list((m.get("comboPick") or {}).get("keys") or []),
    }, {r.get("code"): r.get("name") for r in rows + ((m.get("outRows") or []))}


def diff(a, b, names):
    nm = lambda c: "%s(%s)" % (names.get(c) or "?", c)
    out = []
    if a["order"] != b["order"]:
        gone = [c for c in a["order"] if c not in b["order"]]
        new = [c for c in b["order"] if c not in a["order"]]
        moved = [(c, i + 1, b["order"].index(c) + 1) for i, c in enumerate(a["order"]) if c in b["order"] and b["order"].index(c) != i]
        if gone:
            out.append("판에서 빠짐: " + ", ".join(nm(c) for c in gone))
        if new:
            out.append("판에 새로 듦: " + ", ".join(nm(c) for c in new))
        if moved:
            out.append("차례 바뀜 %d종목: " % len(moved) + ", ".join("%s %d→%d" % (nm(c), x, y) for c, x, y in moved[:30]) + (" …" if len(moved) > 30 else ""))
    for c in a["chips"]:
        if c in b["chips"] and a["chips"][c] != b["chips"][c]:
            add = [x for x in b["chips"][c] if x not in a["chips"][c]]
            rem = [x for x in a["chips"][c] if x not in b["chips"][c]]
            out.append("칩 바뀜 %s: %s%s" % (nm(c), ("+" + "+".join(add)) if add else "", (" −" + "−".join(rem)) if rem else ""))
    for c in sorted(set(a["combo"]) | set(b["combo"])):
        if a["combo"].get(c) != b["combo"].get(c):
            out.append("조합 바뀜 %s: %s → %s" % (nm(c), a["combo"].get(c) or "없음", b["combo"].get(c) or "없음"))
    if a["buyOrder"] != b["buyOrder"]:
        out.append("매수 차례 바뀜: %s → %s" % (", ".join(nm(c) for c in a["buyOrder"]) or "없음", ", ".join(nm(c) for c in b["buyOrder"]) or "없음"))
    if a["sent"] != b["sent"]:
        out.append("보낸 매수 알림 바뀜: %s → %s" % (", ".join(nm(c) for c in a["sent"]) or "없음", ", ".join(nm(c) for c in b["sent"]) or "없음"))
    if a["picked"] != b["picked"]:
        out.append("고른 조합 바뀜: %d개 → %d개" % (len(a["picked"]), len(b["picked"])))
    return out


def compare(day):
    d = day_dir(day)
    rec = {"at": now().strftime("%m-%d %H:%M:%S"), "ports": {}}
    for p in PORTS:
        a = rjson(os.path.join(d, "board-%d.json" % p))
        if not a:
            rec["ports"][str(p)] = {"why": "그날 09:01 기록 없음 — 대조 못 함"}
            continue
        try:
            b = board(p, day)
        except Exception as e:
            rec["ports"][str(p)] = {"why": "지금 판 못 받음 · %s" % type(e).__name__}
            continue
        if not b or b.get("day") != day:
            rec["ports"][str(p)] = {"why": "지금 판이 그날 판이 아님"}
            continue
        fa, na = facts(a)
        fb, nb = facts(b)
        ch = diff(fa, fb, {**na, **nb})
        rec["ports"][str(p)] = {"changes": ch or ["바뀐 것 없음"], "n": len(ch)}
    log = rjson(os.path.join(d, "changes.json"), [])
    log.append(rec)
    wjson(os.path.join(d, "changes.json"), log)
    return rec


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def index():
    os.makedirs(BASE, exist_ok=True)
    days = sorted((x for x in os.listdir(BASE) if x.isdigit() and len(x) == 8), reverse=True)
    parts = []
    for day in days:
        d = os.path.join(BASE, day)
        st = rjson(os.path.join(d, "status.json"), {})
        log = rjson(os.path.join(d, "changes.json"), [])
        head = "%s-%s-%s" % (day[:4], day[4:6], day[6:])
        cells = []
        for p in PORTS:
            ps = (st.get("ports") or {}).get(str(p)) or {}
            nm = "메인(8764)" if p == 8764 else "개발 서버(8765)"
            links = []
            if os.path.isfile(os.path.join(d, "screen-%d-보기.html" % p)):
                links.append('<a href="%s/screen-%d-보기.html">그림</a>' % (day, p))
            if os.path.isfile(os.path.join(d, "board-%d.json" % p)):
                links.append('<a href="%s/board-%d.json">판 값</a>' % (day, p))
            why = ps.get("why") or ps.get("shotWhy")
            when = "판 값 %s · 굳힘 %s" % (ps.get("boardAt") or "—", ps.get("buySetAt") or "—")
            last = next((r["ports"].get(str(p)) for r in reversed(log) if str(p) in r.get("ports", {})), None)
            ch = ""
            if last:
                items = last.get("changes") or [last.get("why") or "—"]
                cls = "ok" if items == ["바뀐 것 없음"] else "bad"
                ch = '<div class="%s">마지막 대조 %s — %s</div><ul>%s</ul>' % (
                    cls, esc(next(r["at"] for r in reversed(log) if str(p) in r.get("ports", {}))),
                    "바뀐 것 없음" if cls == "ok" else "%d가지 바뀜" % len(items),
                    "" if cls == "ok" else "".join("<li>%s</li>" % esc(x) for x in items))
            cells.append('<div class="port"><b>%s</b> %s<div class="sub">%s</div>%s%s</div>' % (
                nm, " · ".join(links) or "—", esc(when), '<div class="bad">못 찍음 — %s</div>' % esc(why) if why else "", ch))
        note = ('<div class="bad">%s</div>' % esc(st["why"]) if st.get("why") else "") + ('<div class="sub">%s</div>' % esc(st["note"]) if st.get("note") else "")
        parts.append('<section><h2>%s</h2>%s%s</section>' % (head, note, "".join(cells)))
    html = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>단타 판 09:01 기록</title><link rel="stylesheet" href="/assets/css/theme.css"><style>
body{margin:0;padding:16px;background:var(--kh-bg);color:var(--kh-text-primary);font-family:'Noto Sans KR',sans-serif}
h1{font-size:1.3rem}section{background:var(--kh-bg-card);border-radius:12px;padding:12px 16px;margin:12px 0}
h2{font-size:1.05rem;margin:4px 0 8px}.port{margin:6px 0 10px}.sub{color:var(--kh-text-secondary);font-size:.85rem}
.ok{color:var(--kh-text-secondary);font-size:.9rem}.bad{color:var(--kh-danger);font-size:.9rem}ul{margin:4px 0 0;padding-left:20px;font-size:.88rem}
</style></head><body><h1>단타 판 09:01 기록</h1>
<p class="sub">장 연 1분 뒤(서버가 셈 칸을 굳힌 때) 판 값을 남기고 단타 판을 찍습니다 · 그 뒤 하루 여러 번 지금 판과 대조해 바뀐 것을 적습니다 · 판 값이 그 초의 기준이고 그림은 다 그려진 뒤라 몇십 초 늦습니다</p>
%s</body></html>""" % ("".join(parts) or "<p>아직 기록이 없습니다</p>")
    with open(os.path.join(BASE, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


def main(argv):
    day = now().strftime("%Y%m%d")
    if "--day" in argv:
        day = argv[argv.index("--day") + 1]
    mode = next((a for a in argv if a in ("snap", "compare", "index")), None)
    if mode is None:
        mode = "snap" if not os.path.isfile(os.path.join(BASE, day, "status.json")) and now().hour < SNAP_BEFORE else "compare"
    if mode == "snap":
        print(json.dumps(snap(day, "--now" in argv), ensure_ascii=False))
    elif mode == "compare":
        print(json.dumps(compare(day), ensure_ascii=False))
    index()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
