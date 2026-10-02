# -*- coding: utf-8 -*-
"""서버리소스 before/after 측정 — 화면이 실제로 얼마나 빨리 · 얼마나 자주 움직이나를 잰다 (2026-10-02 · qa 요건).

재권님이 서버리소스를 1순위로 정하셨고(2026-10-02), qa 몫이 before/after 측정인데 재는 도구가 없었다.
「하루 점검」 의 「지켜보며 세는 검사」 와 같은 뿌리 — check-chart.py 처럼 헤드리스 크롬을 띄워 **화면이 하는 일을
기계가 본다.** 「됨」 이 아니라 **잰 값**을 낸다.

    python3 tools/measure-resource.py [--port 8765] [--code 005930] [--rounds 5] [--watch 60] [--json <파일>]

【잰 값】 화면당 · 같은 조건으로 N회
    1. 클릭 → 선택 종목 차트까지 ms   — 순위표 줄을 누른 뒤 큰 차트가 그 종목으로 다시 그려질 때까지.
                                      차트 API 요청이 **나갔으면 「안 받은(차가운)」, 안 나갔으면 「미리 받은(따뜻한)」** 으로 가른다
    2. 스크롤 → 새 줄이 채워지기까지 ms — 순위표를 한 화면 내린 뒤 보이는 줄의 가격 칸(`···`)이 전부 값이 될 때까지.
                                      창 밖(아래 LOOK_AHEAD 밖)에 아직 `···` 인 줄 수도 함께
    3. 선택 종목의 실제 갱신 간격       — 활성 줄의 가격 칸 textContent 가 바뀐 시각을 N초 지켜보고 간격(초)의 중앙값·최소·최대
    4. 다시 그린 칸 수                 — 순위표(`#kh-rows`) 아래 DOM 이 바뀐 칸을 1초 단위로 센다(MutationObserver)
    5. 서버 쪽                        — `/api/kis/stats` 의 구간차(calls1h · calls1hRelayed · overruns60s · relayCacheMisses ·
                                      cacheHits · upstreamCalls) · `logs/<포트>.log` 의 `[KIS]` 줄을 「구역/마지막 조각」 으로 센 것

【조건으로 적는 것】 포트 · 시각 · 장중 여부 · 종목 · 헤드리스 · 창 크기 · 잰 곳(기계) · 커밋 · 차가운/따뜻한
【잰 대가】 헤드리스 크롬 자체가 화면 하나만큼 서버에 부하를 더한다 — 이 창이 보낸 `/api/*` 요청 수를 결과에 함께 적는다.

종료코드 — 0 쟀다 · 2 **못 쟀다**(서버 · 크롬). 2 를 통과로 읽지 않는다. 「못 쟀다」 는 `0` 이 아니라 `null` 로 낸다 —
「못 쟀으면 0 이 아니라 못 쟀다고 낸다」.
"""
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("check_layout", os.path.join(ROOT, "tools", "check-layout.py"))
CL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CL)

VIEW_W, VIEW_H = 1600, 1000
POLL = 0.05           # 상태를 보는 간격(초) — ms 단위 측정이라 촘촘히
CLICK_MAX = 15        # 클릭 뒤 차트가 올 때까지 최대(초)
SCROLL_MAX = 15       # 스크롤 뒤 줄이 채워질 때까지 최대(초)


def market_open(now):
    return now.weekday() < 5 and (9, 0) <= (now.hour, now.minute) <= (15, 30)


def git_head(folder):
    try:
        return subprocess.check_output(["git", "-C", folder, "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return None


def stats(port):
    try:
        d = json.load(urllib.request.urlopen("http://localhost:%d/api/kis/stats" % port, timeout=5)).get("data", {})
        return {k: d.get(k) for k in ("calls1h", "calls1hRelayed", "overruns60s", "relayCacheMisses", "relayCacheHits",
                                      "cacheHits", "upstreamCalls", "priceCacheTtl", "calls60s", "upstream", "overrunsTotal")}
    except Exception:
        return None


def log_path(port):
    return os.path.join(ROOT, "logs", "%d.log" % port)


def kis_log_counts(port, offset):
    """`logs/<포트>.log` 에서 **측정 시작 때의 파일 크기(offset) 뒤에 붙은 줄**만 `[KIS] … /uapi/...` 를 「구역/마지막」 으로 센다.
    시각 문자열로 거르면 어제 같은 시각 줄까지 센다 — 첫 실측(10:22 · 1분 측정)에서 234 가 나왔다.
    마지막 조각만 세면 주식·선물의 inquire-price 가 섞인다 (2026-10-02 · 개발2)."""
    path = log_path(port)
    if not os.path.exists(path) or offset is None:
        return None
    out = {}
    pat = re.compile(r"\[KIS\] \d\d:\d\d:\d\d\.\d+ :\d+ (/uapi/\S+)")
    try:
        with open(path, "rb") as fp:
            fp.seek(offset)
            for raw in fp:
                line = raw.decode("utf-8", "replace")
                m = pat.search(line)
                if not m:
                    continue
                parts = m.group(1).split("/")
                key = parts[2] + "/" + parts[-1] if len(parts) > 3 else m.group(1)
                out[key] = out.get(key, 0) + 1
    except Exception:
        return None
    return out


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


KNOWN = {"--port", "--code", "--rounds", "--watch", "--json"}


def main(argv):
    if not argv or "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0 if ("--help" in argv or "-h" in argv) else 2
    unknown = [a for a in argv if a.startswith("--") and a not in KNOWN]
    if unknown:
        # 모르는 인자로 기본 8765 를 재면 **메인에 화면 하나만큼 부하**가 간다 (qa 2026-10-02 · api 243건) — 돌지 않는다
        print("못 쟀다 — 모르는 인자 %s. 아는 것: %s" % (" ".join(unknown), " ".join(sorted(KNOWN))))
        return 2

    def opt(name, default):
        return argv[argv.index(name) + 1] if name in argv else default
    port = int(opt("--port", 8765))
    code = opt("--code", "005930")
    rounds = int(opt("--rounds", 5))
    watch = int(opt("--watch", 60))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_json = opt("--json", os.path.join(ROOT, "logs", "measure-%d-%s.json" % (port, stamp)))
    base = "http://localhost:%d/holdings/" % port
    now = datetime.now()

    try:
        urllib.request.urlopen(base, timeout=5)
    except Exception as e:
        print("못 쟀다 — 서버가 없다(%d): %s" % (port, type(e).__name__))
        return 2
    if not CL.CHROME:
        print("못 쟀다 — 크롬을 못 찾았다 (KJC_CHROME 으로 알려 주십시오)")
        return 2

    report = {
        "conditions": {"port": port, "at": now.strftime("%Y-%m-%d %H:%M:%S"), "market_open": market_open(now),
                       "code": code, "headless": True, "window": [VIEW_W, VIEW_H], "measured_on": platform.node(),
                       "commit_main_folder": git_head(ROOT), "rounds": rounds, "watch_sec": watch,
                       "cost_note": "헤드리스 크롬 한 장이 서버에 화면 하나만큼의 부하를 더한다 — own_api_requests 참조"},
        "server_before": stats(port), "server_after": None, "server_delta": None, "server_window": None, "kis_log_by_path": None,
        "click_to_chart_ms": [], "scroll_to_fill_ms": [], "update_interval_sec": None, "redraw_cells_per_sec": None,
        "own_api_requests": 0, "problems": [],
    }
    log_offset = os.path.getsize(log_path(port)) if os.path.exists(log_path(port)) else None
    # 이 서버가 KIS 를 8765 로 넘기면(upstream) KIS 호출은 8765.log 에 남는다 — 그쪽도 같은 구간을 센다
    relayed = bool((report["server_before"] or {}).get("upstream")) if report["server_before"] else False
    up_offset = os.path.getsize(log_path(8765)) if (relayed and port != 8765 and os.path.exists(log_path(8765))) else None

    dbg = CL.free_port(9500) or 9500
    proc = subprocess.Popen(
        [CL.CHROME, "--headless=new", "--disable-gpu",
         "--user-data-dir=" + tempfile.mkdtemp(prefix="kjc-measure-"),
         "--no-first-run", "--no-default-browser-check",
         "--remote-debugging-port=%d" % dbg,
         "--window-size=%d,%d" % (VIEW_W, VIEW_H), "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    try:
        tabs = None
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % dbg, timeout=2))
                break
            except Exception:
                time.sleep(0.5)
        if not tabs:
            print("못 쟀다 — 크롬이 디버깅 포트를 안 열었다")
            return 2
        ws = CL.ws_connect([t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"])
        counter = [0]
        events = []

        def call(method, params=None):
            counter[0] += 1
            CL._send(ws, {"id": counter[0], "method": method, "params": params or {}})
            while True:
                m = CL._recv(ws)
                if m.get("id") == counter[0]:
                    return m
                if "method" in m:
                    events.append(m)

        def pump(sec):
            end = time.time() + sec
            ws.settimeout(0.05)
            try:
                while time.time() < end:
                    try:
                        m = CL._recv(ws)
                    except Exception:
                        time.sleep(0.01)
                        continue
                    if "method" in m:
                        events.append(m)
            finally:
                ws.settimeout(30)

        def ev(expr):
            r = call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": False})
            return r.get("result", {}).get("result", {}).get("value")

        def drain_requests():
            """이 창이 보낸 /api/ 요청을 세고, 차트 API 응답의 출처(meta.source)들을 돌려준다."""
            n_api, chart_rids, sources = 0, [], []
            for m in events:
                if m["method"] == "Network.requestWillBeSent":
                    url = m.get("params", {}).get("request", {}).get("url", "")
                    if "/api/" in url:
                        n_api += 1
                elif m["method"] == "Network.responseReceived":
                    if "/api/kis/chart" in m.get("params", {}).get("response", {}).get("url", ""):
                        chart_rids.append(m["params"].get("requestId"))
            events.clear()
            report["own_api_requests"] += n_api
            for rid in chart_rids:
                try:
                    body = json.loads(call("Network.getResponseBody", {"requestId": rid})["result"]["body"])
                    sources.append(str((body.get("meta") or {}).get("source") or "?"))
                except Exception:
                    sources.append("?")
            return sources

        for m in ("Page.enable", "Runtime.enable", "Network.enable"):
            call(m)
        if ev("innerWidth") != VIEW_W:
            print("못 쟀다 — 남의 크롬에 붙었다")
            return 2

        call("Page.navigate", {"url": base + "index.html"})
        # 순위표가 뜨고 가격이 채워질 때까지
        for _ in range(int(30 / 0.5)):
            pump(0.5)
            if ev("document.querySelectorAll('#kh-rows tr[data-code]').length > 5 && document.querySelectorAll('#kh-big-chart canvas').length > 0"):
                break
        pump(2.0)
        drain_requests()

        # ── 1. 클릭 → 선택 종목 차트 ──
        rows = ev("JSON.stringify([...document.querySelectorAll('#kh-rows tr[data-code]')].map(t=>t.dataset.code))") or "[]"
        rows = json.loads(rows)
        if len(rows) < 3:
            report["problems"].append("순위표 줄이 %d개뿐이라 클릭 측정을 못 했다" % len(rows))
        else:
            # 회차마다 **다른 종목**(브라우저 캔들 캐시 60초 때문 — qa: 같은 셋을 돌리니 15 중 14 가 캐시) · 앞쪽 줄과 뒤쪽 줄을 번갈아 ·
            # 마지막에 첫 종목을 한 번 **다시** 눌러 따뜻한 값도 하나 둔다
            front = [rows[1 + i] for i in range(min(rounds, max(len(rows) - 2, 0)))]
            back = [rows[-1 - i] for i in range(min(rounds, max(len(rows) - 2, 0)))]
            picks = [x for pair in zip(front, back) for x in pair] + ([front[0]] if front else [])
            for i, c in enumerate(picks):
                drain_requests()
                started = ev("""(function(){const tr=document.querySelector('#kh-rows tr[data-code="%s"]'); if(!tr) return null;
                    tr.scrollIntoView({block:'center'}); window.__m_t0=performance.now(); window.__m_canvas0=document.querySelectorAll('#kh-big-chart canvas').length;
                    tr.click(); return true;})()""" % c)
                if not started:
                    report["problems"].append("줄 %s 를 못 찾았다" % c)
                    continue
                got = None
                for _ in range(int(CLICK_MAX / POLL)):
                    pump(POLL)
                    got = ev("""(function(){const tr=document.querySelector('#kh-rows tr.is-active'); if(!tr||tr.dataset.code!=='%s') return null;
                        const cv=document.querySelectorAll('#kh-big-chart canvas').length; if(!cv) return null;
                        if(document.querySelector('#kh-big-chart .kh-soon')) return -1;
                        return Math.round(performance.now()-window.__m_t0);})()""" % c)
                    if got is not None:
                        break
                srcs = drain_requests()
                kind = "브라우저 캐시" if not srcs else ("미리 받은(DB)" if all(s == "DB" for s in srcs) else "안 받은(%s)" % ",".join(srcs))
                report["click_to_chart_ms"].append({"round": i + 1, "code": c, "ms": got if (got is not None and got >= 0) else None,
                                                    "chart_request": bool(srcs), "sources": srcs, "kind": kind, "failed": got == -1})
                pump(0.5)

        # ── 2. 스크롤 → 새로 보인 줄의 시세 응답이 오기까지 ──
        # 「가격 칸에 값이 있나」 로는 안 갈린다 — 첫 화면이 200줄 시세를 미리 받아 두어 스크롤하자마자 참이다 (qa 실측 53~104ms).
        # 그래서 **새로 보인 줄의 코드가 든 /api/kis/quotes 응답**이 오기까지를 잰다. 값이 이미 있던 줄 수도 함께 적는다.
        def visible_codes():
            v = ev("""(function(){const b=document.getElementById('kh-rank-scroll'); if(!b) return null; const br=b.getBoundingClientRect();
                const out=[]; for(const tr of document.querySelectorAll('#kh-rows tr[data-code]')){const r=tr.getBoundingClientRect();
                  if(r.bottom>=br.top && r.top<=br.bottom) out.push(tr.dataset.code);} return JSON.stringify(out);})()""")
            return json.loads(v) if v else None
        for i in range(rounds):
            before = visible_codes()
            if before is None:
                report["problems"].append("순위표 스크롤 칸(#kh-rank-scroll)이 없다")
                break
            drain_requests()
            ev("""(function(){const b=document.getElementById('kh-rank-scroll'); b.scrollTop = b.scrollTop + b.clientHeight; window.__m_t0=performance.now();})()""")
            pump(0.05)
            after = visible_codes() or []
            new_codes = [c for c in after if c not in before]
            had_value = ev("""(function(){const codes=%s; let n=0; for(const c of codes){const tr=document.querySelector('#kh-rows tr[data-code="'+c+'"]');
                const cell=tr&&tr.querySelector('td.kh-num'); const txt=cell?cell.textContent.trim():''; if(txt && txt!=='···') n++;} return n;})()""" % json.dumps(new_codes))
            got = None
            end = time.time() + SCROLL_MAX
            while time.time() < end and got is None:
                pump(POLL)
                for m in list(events):
                    if m["method"] == "Network.responseReceived":
                        url = m.get("params", {}).get("response", {}).get("url", "")
                        if "/api/kis/quotes" in url and any(c in url for c in new_codes):
                            got = ev("Math.round(performance.now()-window.__m_t0)")
                            break
            drain_requests()
            report["scroll_to_fill_ms"].append({"round": i + 1, "ms": got, "new_rows": len(new_codes), "new_rows_already_had_value": had_value,
                                                "scrolled_to_end": len(new_codes) == 0})
            pump(0.3)

        # ── 3·4. 갱신 간격 · 다시 그린 칸 수 (N초 지켜본다) ──
        # 가격 칸은 **매번 다시 찾는다** — 줄이 다시 그려지면 잡아 둔 칸이 문서에서 떨어진다 (qa: 60초에 0번으로 나왔다).
        # 큰 차트 머리의 가격(#kh-big-v)도 함께 본다. 다시 그린 것은 「새로 만든 요소 수」 — addedNodes 중 같은 바퀴의
        # removedNodes 에 없던 것 + 글자가 바뀐 칸. DOM 변경 건수로 세면 줄을 옮긴 것(추가+삭제)이 나쁜 것으로 보인다 (qa · 창구 · 작업우선순위).
        ev("""(function(){window.__m={row:[],big:[],made:{}};
            const rowTxt=()=>{const r=document.querySelector('#kh-rows tr.is-active'); const c=r&&r.querySelector('td.kh-num span, td.kh-num'); return c?c.textContent.trim():null;};
            const bigTxt=()=>{const e=document.getElementById('kh-big-v'); return e?e.textContent.trim():null;};
            window.__m.lastRow=rowTxt(); window.__m.lastBig=bigTxt();
            window.__m.obs=new MutationObserver(ms=>{const sec=Math.floor((performance.now()-window.__m.t0)/1000);
              const removed=new Set(); for(const m of ms) for(const n of m.removedNodes) removed.add(n);
              let made=0; for(const m of ms){ if(m.type==='characterData') made++; for(const n of m.addedNodes){ if(!removed.has(n)) made++; } }
              window.__m.made[sec]=(window.__m.made[sec]||0)+made;
              const r=rowTxt(); if(r!==null && r!==window.__m.lastRow){window.__m.lastRow=r; window.__m.row.push(performance.now());}
              const b=bigTxt(); if(b!==null && b!==window.__m.lastBig){window.__m.lastBig=b; window.__m.big.push(performance.now());}});
            window.__m.obs.observe(document.getElementById('kh-rows'),{subtree:true,childList:true,characterData:true});
            const bigEl=document.getElementById('kh-big-v'); if(bigEl) window.__m.obs.observe(bigEl,{subtree:true,childList:true,characterData:true});
            window.__m.t0=performance.now(); return rowTxt()!==null;})()""")
        pump(float(watch))
        res = ev("""(function(){const m=window.__m; m.obs.disconnect();
            return JSON.stringify({row:m.row.map(t=>Math.round(t-m.t0)), big:m.big.map(t=>Math.round(t-m.t0)), made:Object.values(m.made), watchedMs:Math.round(performance.now()-m.t0)});})()""")
        res = json.loads(res) if res else {"row": [], "big": [], "made": [], "watchedMs": None}
        def interval(ts):
            gaps = [(b - a) / 1000.0 for a, b in zip(ts, ts[1:])]
            return {"changes": len(ts), "median": median(gaps), "min": min(gaps) if gaps else None, "max": max(gaps) if gaps else None}
        report["update_interval_sec"] = {"active_row_price": interval(res["row"]), "big_chart_price": interval(res["big"]),
                                         "watched_sec": (res["watchedMs"] or 0) / 1000.0}
        made = res["made"]
        report["redraw_cells_per_sec"] = {"seconds_with_change": len(made), "median": median(made), "max": max(made) if made else None,
                                          "total_new_elements": sum(made), "watched_sec": (res["watchedMs"] or 0) / 1000.0}
        drain_requests()
    except (IOError, OSError) as e:
        print("못 쟀다 — CDP: %s" % e)
        return 2
    finally:
        try:
            if ws:
                CL._send(ws, {"id": 99999, "method": "Browser.close"})
                time.sleep(0.5)
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass

    # ── 5. 서버 쪽 ──
    report["server_after"] = stats(port)
    # 누적 카운터만 구간차. calls1h · calls60s · overruns60s 는 「지난 N초」 이동 창이라 구간차가 음수로도 나온다 (qa — −49)
    CUMULATIVE = ("relayCacheMisses", "relayCacheHits", "cacheHits", "upstreamCalls", "overrunsTotal")
    if report["server_before"] and report["server_after"]:
        b, a = report["server_before"], report["server_after"]
        report["server_delta"] = {k: (a[k] - b[k]) if isinstance(b.get(k), (int, float)) and isinstance(a.get(k), (int, float)) else None
                                  for k in CUMULATIVE}
        report["server_window"] = {k: [b.get(k), a.get(k)] for k in ("calls1h", "calls1hRelayed", "calls60s", "overruns60s")}
    report["kis_log_by_path"] = kis_log_counts(port, log_offset)
    report["kis_log_by_path_8765"] = kis_log_counts(8765, up_offset) if up_offset is not None else None

    try:
        os.makedirs(os.path.dirname(out_json), exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as fp:
            json.dump(report, fp, ensure_ascii=False, indent=1)
    except Exception:
        pass

    c = report["conditions"]
    print("서버리소스 측정 — %s · 서버 %d · 종목 %s · 장중 %s · 잰 곳 %s · 커밋 %s · 헤드리스 %dx%d"
          % (c["at"], port, code, "예" if c["market_open"] else "아니오", c["measured_on"], c["commit_main_folder"], VIEW_W, VIEW_H))
    kinds = {}
    for r in report["click_to_chart_ms"]:
        kinds.setdefault(r["kind"], []).append(r["ms"])
    print("  1. 클릭→차트  " + " · ".join("%s %d회 중앙값 %s ms" % (k, len(v), median(v)) for k, v in kinds.items())
          + " · 실패 %d" % sum(1 for r in report["click_to_chart_ms"] if r["failed"]))
    sc = [r["ms"] for r in report["scroll_to_fill_ms"] if not r.get("scrolled_to_end")]
    print("  2. 스크롤→새 줄 시세 응답  %d회 중앙값 %s ms · %d초 안에 안 온 회 %d · 새로 보인 줄 중 값이 이미 있던 줄 %s"
          % (len(sc), median(sc), SCROLL_MAX, sum(1 for x in sc if x is None),
             "/".join("%s:%s" % (r["new_rows_already_had_value"], r["new_rows"]) for r in report["scroll_to_fill_ms"]) or "-"))
    u = report["update_interval_sec"]
    for label, k in (("활성 줄 가격", "active_row_price"), ("큰 차트 가격", "big_chart_price")):
        x = u[k]
        print("  3. 갱신 간격(%s)  %d번 바뀜 / %.0f초 · 중앙값 %s · 최소 %s · 최대 %s (초)" % (label, x["changes"], u["watched_sec"], x["median"], x["min"], x["max"]))
    r4 = report["redraw_cells_per_sec"]
    print("  4. 새로 만든 요소  초당 중앙값 %s · 최대 %s · 합 %s (%d초 중 %d초에 변화)" % (r4["median"], r4["max"], r4["total_new_elements"], int(r4["watched_sec"]), r4["seconds_with_change"]))
    d = report["server_delta"]
    print("  5. 서버 누적 구간차  %s" % (", ".join("%s %+d" % (k, v) for k, v in d.items() if v is not None) if d else "못 쟀다(stats 없음)"))
    w = report.get("server_window")
    if w:
        print("     이동 창(시작 → 끝)  " + ", ".join("%s %s → %s" % (k, v[0], v[1]) for k, v in w.items()))
    def show_log(label, counts):
        if counts is None:
            print("     [KIS] 로그 %s  못 쟀다 — 로그 파일이 이 폴더에 없다(메인 폴더에서 돌린다)" % label)
        elif not counts:
            print("     [KIS] 로그 %s  0건 (측정 구간에 KIS 호출 줄이 안 붙었다)" % label)
        else:
            top = sorted(counts.items(), key=lambda kv: -kv[1])[:5]
            print("     [KIS] 로그 %s  합 %d · " % (label, sum(counts.values())) + " · ".join("%s %d" % kv for kv in top))
    show_log("%d.log" % port, report["kis_log_by_path"])
    if report.get("kis_log_by_path_8765") is not None:
        show_log("8765.log(넘긴 쪽 · 다른 화면 몫도 섞임)", report["kis_log_by_path_8765"])
    print("  잰 대가  이 창이 보낸 /api/ 요청 %d" % report["own_api_requests"])
    for p in report["problems"]:
        print("  !! " + p)
    print("  → %s" % out_json)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
