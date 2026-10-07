# -*- coding: utf-8 -*-
"""차트가 고장났는지 늘 확인하는 장치 (2026-10-01 지시).

재권님 말씀 — 「차트쪽 작업된것들 중간에 고장나는지 안나는지 확인을 항상 할수있는 장치가 필요해」.

    python3 tools/check-chart.py                  8765 의 첫 화면 · 종목 화면을 연기 검사한다
    python3 tools/check-chart.py --port 8764      다른 서버(서비스방 등)
    python3 tools/check-chart.py --code 000660    종목 화면에 쓸 종목 (기본 005930)
    python3 tools/check-chart.py --json <경로>    결과를 JSON 으로도 남긴다 (기본 logs/check-chart.json)

**무엇을 보나** — 그동안 차트가 깨진 모양 넷을 그대로 센다.

    지표를 켜면 세로 범위가 움직임     `chart.js` 가 붙이는 `.kh-scale-warn` · `.kh-align-warn` 띠가 생겼나
    지표 선이 안 그려짐(5분봉 200일선)  지표를 켠 뒤 그려진 칸(canvas) 수가 늘었나
    차트 데이터를 못 받음              `/api/kis/chart` 응답이 200 · ok:true · 봉이 둘 이상인가
    라이브러리를 못 불러옴             `window.LightweightCharts` 가 있나 · 콘솔 오류 · 예외

**어떻게** — `check-layout.py` 와 같은 길로 헤드리스 크롬을 띄워 CDP 로 붙는다. 첫 화면과 종목 화면을
열고 기간을 일봉 → 5분봉으로 바꾸고 지표 여섯을 하나씩 켰다 끈다. **화면 자기 검사(경고 띠)를 기계가
읽는 것**이 핵심이다 — 전에는 그 띠를 사람이 그 화면을 보고 있을 때만 봤다.

**종료코드** — 0 통과 · 1 걸림(차트가 깨졌다) · 2 못 쟀다(서버·크롬 문제). **못 쟀다를 통과로 읽지 않는다.**

**언제 도나** — 차트 파일을 담은 커밋 뒤(`post-commit` 이 돌려 보라고 띄운다) · launchd 주기
(`launchd/kr.kjcstudio.check-chart.plist`) · 손으로. 결과는 `logs/check-chart.json` 과 로그에 남는다.
알림(텔레그램)은 **아직 안 보낸다** — 「켜기」 는 몇 건이 갈지 재서 승인받는 자리다.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# check-layout.py 의 크롬 띄우기 · CDP 소켓을 그대로 쓴다 (복제하지 않는다).
_spec = importlib.util.spec_from_file_location("check_layout", os.path.join(ROOT, "tools", "check-layout.py"))
CL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CL)

VIEW_W, VIEW_H = 1600, 1000
SETTLE_STEP = 0.5
WAIT_MAX = 30          # 화면 하나가 차트를 그릴 때까지 최대 기다리는 초
AFTER_CLICK = 10       # 기간·지표를 바꾼 뒤 다시 그려질 때까지 최대 기다리는 초 (상태로 기다린다)

# 화면마다 어디를 보나 — 선택자는 화면 코드가 정한 것(index.html · stock-view.js)
SCENES = [
    {"name": "index", "url": "index.html", "host": "#kh-big-chart",
     "period_btn": "#kh-idx-per button[data-p=%s]"},
    {"name": "stock", "url": "stock.html?code=%(code)s", "host": "#kh-chart",
     "period_btn": "#kh-per button[data-period=%s]"},
]
PERIODS = ["5m", "1d"]      # 바꿔 볼 기간 — 5분봉에서 200일선이 안 그려진 적이 있다 (dbbb055)
IND_KEYS = ["ma", "bb", "vol", "macd", "rsi", "vp"]


class Unmeasured(Exception):
    pass


# 세지 않되 **센 수는 낸다** — 세션 폴더에는 uidata/icons 가 없어서(gitignore) 종목 아이콘이 늘 404 다.
# 「고친 뒤」 를 세션 포트로 재면 그것이 「새로 생긴 오류」 로 나와 전후 비교를 흐렸다(qa 2026-10-03 · 8767).
# 조용히 빼면 8765 에서 아이콘이 진짜 깨져도 안 보이므로, 걸린 것에서만 빼고 수는 따로 적는다.
IGNORED = []


def main(argv):
    if "--help" in argv or "-h" in argv:
        # --help 가 없어서 그대로 검사를 돌리고 30분 주기 결과 파일(logs/check-chart.json)을 덮었다(qa 2026-10-03)
        print(__doc__)
        return 0
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8765
    code = argv[argv.index("--code") + 1] if "--code" in argv else "005930"
    out_json = argv[argv.index("--json") + 1] if "--json" in argv else os.path.join(ROOT, "logs", "check-chart.json")
    base = "http://localhost:%d/holdings/" % port

    try:
        urllib.request.urlopen(base, timeout=5)
    except Exception as e:
        print("못 쟀다 — 서버가 없다(%d): %s" % (port, type(e).__name__))
        return 2
    if not CL.CHROME:
        print("못 쟀다 — 크롬을 못 찾았다 (KJC_CHROME 으로 알려 주십시오)")
        return 2

    dbg = CL.free_port(9400) or 9400
    proc = subprocess.Popen(
        [CL.CHROME, "--headless=new", "--disable-gpu",
         "--user-data-dir=" + tempfile.mkdtemp(prefix="kjc-chart-"),
         "--no-first-run", "--no-default-browser-check",
         "--remote-debugging-port=%d" % dbg,
         "--window-size=%d,%d" % (VIEW_W, VIEW_H), "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    report = {"port": port, "code": code, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "scenes": [], "problems": []}
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
            """잠깐 기다리며 그동안 온 이벤트(콘솔·네트워크)를 모은다."""
            end = time.time() + sec
            ws.settimeout(0.3)
            try:
                while time.time() < end:
                    try:
                        m = CL._recv(ws)
                    except Exception:
                        time.sleep(0.05)
                        continue
                    if "method" in m:
                        events.append(m)
            finally:
                ws.settimeout(30)

        def ev(expr):
            r = call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": False})
            return r.get("result", {}).get("result", {}).get("value")

        for m in ("Page.enable", "Runtime.enable", "Log.enable", "Network.enable"):
            call(m)
        got = ev("innerWidth")
        if got != VIEW_W:
            print("못 쟀다 — 남의 크롬에 붙었다 (창 폭 %s)" % got)
            return 2

        def drain():
            """지금까지 온 이벤트에서 오류 · 차트 응답을 뽑고 비운다."""
            errs, charts = [], []
            for m in events:
                meth, p = m["method"], m.get("params", {})
                if meth == "Runtime.exceptionThrown":
                    d = p.get("exceptionDetails", {})
                    txt = (d.get("exception") or {}).get("description") or d.get("text") or "예외"
                    errs.append("예외: " + txt.splitlines()[0][:160])
                elif meth == "Runtime.consoleAPICalled" and p.get("type") == "error":
                    txt = " ".join(str(a.get("value", a.get("description", ""))) for a in p.get("args", []))
                    errs.append("console.error: " + txt[:160])
                elif meth == "Log.entryAdded":
                    e = p.get("entry", {})
                    if e.get("level") == "error" and "/uidata/" in (e.get("url") or ""):
                        IGNORED.append(e.get("url"))
                    elif e.get("level") == "error" and "favicon" not in (e.get("url") or ""):
                        errs.append("오류: " + (e.get("text") or "")[:160])
                elif meth == "Network.responseReceived":
                    res = p.get("response", {})
                    if "/api/kis/chart" in res.get("url", ""):
                        charts.append({"url": res["url"], "status": res.get("status"), "rid": p.get("requestId")})
            events.clear()
            return errs, charts

        def chart_bodies(charts):
            """차트 응답 본문을 읽어 ok · 봉 수를 센다."""
            out = []
            for c in charts:
                # since= 는 「안 받은 봉만」 받는 이어 받기라 봉 1~2 가 정상이다 — 봉 수를 안 센다(2026-10-07 · 개발 실측 헛경보)
                item = {"status": c["status"], "ok": None, "candles": None, "period": None,
                        "since": "since=" in (c.get("url") or "")}
                try:
                    r = call("Network.getResponseBody", {"requestId": c["rid"]})
                    body = json.loads(r["result"]["body"])
                    item["ok"] = bool(body.get("ok"))
                    d = body.get("data") or {}
                    if not item["since"]:
                        item["candles"] = len(d.get("candles") or [])
                    item["period"] = d.get("period")
                except Exception:
                    pass
                out.append(item)
            return out

        def state(host):
            return json.loads(ev("""JSON.stringify({
                lc: !!window.LightweightCharts,
                canvases: document.querySelectorAll('%s canvas').length,
                panes: document.querySelectorAll('%s .kh-pane, %s [class*=pane]').length,
                scaleWarn: [...document.querySelectorAll('.kh-scale-warn')].map(e => e.textContent),
                alignWarn: [...document.querySelectorAll('.kh-align-warn')].map(e => e.textContent),
                err: (document.querySelector('%s')||{}).textContent && /불러오지 못|만료|없습니다/.test(document.querySelector('%s').textContent) ? document.querySelector('%s').textContent.trim().slice(0,120) : '',
                here: location.pathname + location.search
            })""" % (host, host, host, host, host, host)))

        def wait_drawn(host, sec):
            """바꾼 뒤 차트가 다시 그려질 때까지(canvas 가 돌아오고 연달아 같을 때까지) 기다린다.

            고정 초로 기다리면 **부수고 다시 만드는 사이**를 재서 「차트가 비었다」 로 나온다 —
            첫 실측에서 두 번 중 한 번 그랬다. 시간이 아니라 상태로 기다린다 (check-layout 과 같은 자리)."""
            prev, same, st = None, 0, None
            for _ in range(int(sec / SETTLE_STEP)):
                pump(SETTLE_STEP)
                st = state(host)
                cur = (st["canvases"], len(st["scaleWarn"]), len(st["alignWarn"]))
                if st["canvases"] > 0 and cur == prev:
                    same += 1
                    if same >= 2:
                        return st
                else:
                    same = 0
                prev = cur
            return st

        def wait_chart(host, url_tail):
            """차트 칸에 canvas 가 생길 때까지 기다린다. 못 그리면 그 상태를 돌려준다."""
            st = None
            for _ in range(int(WAIT_MAX / SETTLE_STEP)):
                pump(SETTLE_STEP)
                st = state(host)
                if not st["here"].endswith(url_tail.split("?")[0]) and url_tail.split("?")[0] not in st["here"]:
                    continue
                if st["canvases"] > 0 or st["err"]:
                    pump(1.0)
                    return state(host)
            return st

        problems = report["problems"]
        for sc in SCENES:
            name, host = sc["name"], sc["host"]
            url = base + (sc["url"] % {"code": code})
            rec = {"name": name, "url": url, "steps": []}
            report["scenes"].append(rec)
            drain()
            call("Page.navigate", {"url": url})
            st = wait_chart(host, sc["url"].split("?")[0])
            errs, charts = drain()
            step = {"step": "열기", "state": st, "errors": errs, "chart_api": chart_bodies(charts)}
            rec["steps"].append(step)
            if not st or not st["lc"]:
                problems.append("%s: 차트 라이브러리(LightweightCharts)가 없다" % name)
            if st and st["canvases"] == 0:
                problems.append("%s: 차트가 안 그려졌다 (%s)" % (name, st["err"] or "canvas 0"))
            for e in errs:
                problems.append("%s(열기): %s" % (name, e))
            for c in step["chart_api"]:
                if c["status"] != 200 or c["ok"] is False or (c["candles"] is not None and c["candles"] < 2):
                    problems.append("%s: 차트 API %s ok=%s 봉=%s" % (name, c["status"], c["ok"], c["candles"]))
            if not st or st["canvases"] == 0:
                continue

            # 기간 바꾸기 — 5분봉 → 일봉
            for pid in PERIODS:
                sel = sc["period_btn"] % json.dumps(pid)
                clicked = ev("(function(){const b=document.querySelector(%s); if(!b) return false; b.click(); return true;})()" % json.dumps(sel))
                st2 = wait_drawn(host, AFTER_CLICK)
                errs, charts = drain()
                step = {"step": "기간 " + pid, "clicked": clicked, "state": st2, "errors": errs, "chart_api": chart_bodies(charts)}
                rec["steps"].append(step)
                if not clicked:
                    problems.append("%s: 기간 단추 %s 를 못 찾았다 (%s)" % (name, pid, sel))
                    continue
                if st2["canvases"] == 0:
                    problems.append("%s: 기간 %s 로 바꾸니 차트가 비었다 (%s)" % (name, pid, st2["err"]))
                for e in errs:
                    problems.append("%s(기간 %s): %s" % (name, pid, e))
                for c in step["chart_api"]:
                    if c["status"] != 200 or c["ok"] is False or (c["candles"] is not None and c["candles"] < 2):
                        problems.append("%s(기간 %s): 차트 API %s ok=%s 봉=%s" % (name, pid, c["status"], c["ok"], c["candles"]))
                if st2["scaleWarn"] or st2["alignWarn"]:
                    problems.append("%s(기간 %s): 화면 경고 띠 — %s" % (name, pid, " / ".join(st2["scaleWarn"] + st2["alignWarn"])))

            # 지표 켜고 끄기 — 하나씩
            base_canvas = state(host)["canvases"]
            for key in IND_KEYS:
                sel = "input[data-ind=%s]" % json.dumps(key)
                on = ev("(function(){const b=document.querySelector(%s); if(!b) return 'none'; if(b.checked) return 'already'; b.click(); return 'on';})()" % json.dumps(sel))
                st3 = wait_drawn(host, AFTER_CLICK)
                errs, charts = drain()
                ev("(function(){const b=document.querySelector(%s); if(b && b.checked) b.click();})()" % json.dumps(sel))
                pump(1.0)
                drain()
                step = {"step": "지표 " + key, "toggle": on, "state": st3, "errors": errs}
                rec["steps"].append(step)
                if on == "none":
                    problems.append("%s: 지표 단추 %s 가 없다" % (name, key))
                    continue
                if st3["canvases"] < base_canvas:
                    problems.append("%s(지표 %s): 그려진 칸이 줄었다 %d → %d" % (name, key, base_canvas, st3["canvases"]))
                if st3["scaleWarn"] or st3["alignWarn"]:
                    problems.append("%s(지표 %s): 화면 경고 띠 — %s" % (name, key, " / ".join(st3["scaleWarn"] + st3["alignWarn"])))
                for e in errs:
                    problems.append("%s(지표 %s): %s" % (name, key, e))
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

    # ── 결과 ──
    try:
        os.makedirs(os.path.dirname(out_json), exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as fp:
            report["ignoredUidata404"] = len(IGNORED)
            json.dump(report, fp, ensure_ascii=False, indent=1)
    except Exception:
        pass

    print("차트 연기 검사 — %s · 서버 %d · 종목 %s" % (report["at"], port, code))
    for sc in report["scenes"]:
        opened = sc["steps"][0]["state"] if sc["steps"] else None
        api = sc["steps"][0]["chart_api"] if sc["steps"] else []
        n_steps = len(sc["steps"])
        print("  %-6s 열기: canvas %s · 라이브러리 %s · 차트 API %s · 단계 %d"
              % (sc["name"], opened and opened["canvases"], opened and ("있음" if opened["lc"] else "**없음**"),
                 ",".join("%s/봉%s" % (c["status"], c["candles"]) for c in api) or "-", n_steps))
    if IGNORED:
        print("  -- 세지 않음: /uidata/ 404 %d건 (세션 폴더에는 uidata/icons 가 없다 · 8765 에서 나면 진짜다)" % len(IGNORED))
    if report["problems"]:
        print("  !! 걸린 것 %d" % len(report["problems"]))
        for p in report["problems"]:
            print("     - " + p)
        return 1
    print("  OK  걸린 것 없음 (화면 2 · 기간 %d · 지표 %d)" % (len(PERIODS), len(IND_KEYS)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
