#!/usr/bin/env python3
"""차트 검수의 두 값을 잰다 — 종목을 눌러 큰 차트가 그려지기까지 · 모달 가격이 실제로 바뀐 간격 (2026-11-23 · 재권님 「응 만들어」).

스킬 chart-review 의 ③ · ④ 다. 10-02 에 qa 가 같은 것을 세션 임시 폴더의 CDP 글로 두 번 손으로 쟀고
그 글이 지워졌다 — 두 번 쓰였으니 도구로 옮겼다.

    python3 tools/measure-chart.py                          8765 를 잰다 (둘 다)
    python3 tools/measure-chart.py --port 8767 --against 8765   두 서버를 같은 종목으로 나란히
    python3 tools/measure-chart.py --only click             클릭만 (장 밖에도 뜻이 있다)
    python3 tools/measure-chart.py --only modal --watch 180     모달만 · 지켜보는 초
    python3 tools/measure-chart.py --codes 005930,000660    누를 종목 (기본: 첫 서버 순위표 위에서 N 개)
    python3 tools/measure-chart.py --n 5 --json <경로>

**무엇을 재나**

    클릭 → 그려짐   순위표 줄을 누른 순간부터 큰 차트 칸 그림(canvas 픽셀)이 바뀐 때 ms — 두 값:
                    첫 그림(처음 바뀜) · 다 그려짐(그 뒤 QUIET_MS 동안 더 안 바뀐 마지막 바뀜 — 덧붙이기 · 보조 칸까지).
                    「차트 불러오는 중」 덮개 동안 · 그 종목 봉을 받는 동안의 바뀜(옛 차트에 시세가 붙음)은 안 셈.
                    줄마다 덮개가 떴나(= 서버에 받아 둔 봉이 없어 통째로 받음)로 갈라 중앙값
    모달 갱신 간격   `/holdings/?code=<종목>` 로 모달을 띄워 `#kh-price` 글자가 실제로 바뀐 때를 지켜봄 — 요청 간격이 아니다

**통과 문턱은 없다** — 값만 낸다. 통과인지는 검수하는 쪽이 지시 낱말과 견준다(chart-review 「잴 것」 ② ③ ④).

**종료코드** — 0 다 잼 · 1 걸림(누른 차트가 끝내 안 그려짐 · 장중인데 모달 가격이 한 번도 안 바뀜) · 2 못 쟀다(서버 · 크롬 ·
장 밖이라 모달 간격을 못 잼 · 순위표에 그 종목이 없음). **2 를 통과로 읽지 않는다.**

**못 보는 것** — 순위표 밖 종목(누를 줄이 없다 — 그래서 서버에 받아 둔 봉이 없는 「처음 여는 종목」 은 그런 종목이 순위표에 있을 때만 나온다) ·
터널 구간(맥미니 안에서 재서 외부접속 기기의 시간은 빠진다) · 재권님 크롬의 저장값 · 확대 비율.
"""
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# check-layout.py 의 크롬 찾기 · CDP 소켓을 그대로 쓴다 (복제하지 않는다)
_spec = importlib.util.spec_from_file_location("check_layout", os.path.join(ROOT, "tools", "check-layout.py"))
CL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CL)

# 창 크기는 재권님 창 한 곳(tools/view-size.json)에서 — 「찍는 창 크기도 창 크기다」
with open(os.path.join(ROOT, "tools", "view-size.json"), encoding="utf-8") as _f:
    _VS = json.load(_f)
VIEW_W, VIEW_H = _VS["width"], _VS["height"]

# ── 기다리는 값은 여기 한 곳 ──
PAGE_READY_MAX = 40     # 첫 화면이 순위표 · 큰 차트를 그릴 때까지 최대 초
CLICK_MAX = 20          # 누른 뒤 그려질 때까지 최대 초 — 넘으면 걸림
QUIET_MS = 800          # 첫 그림 뒤 이만큼 더 안 바뀌면 「다 그려짐」 — 덧붙이기 · 보조 칸은 0.4~0.6초 안에 끝나고(qa 11-23)
                        # 옛 차트 · 새 차트에 시세가 붙는 바뀜은 1.4초 넘게 띄어 오므로 그보다 짧게 둔다
AFTER_CLICK_REST = 1.5  # 한 번 잰 뒤 쉬는 초 — 뒤따라 오는 덧붙이기 받기가 다음 잼에 섞이지 않게
DEFAULT_N = 5           # 누를 종목 수
DEFAULT_WATCH = 120     # 모달 가격을 지켜보는 초
MARKET_KST = ((9, 0), (15, 30))   # 정규장 — 이 밖이면 모달 가격이 안 바뀌는 것이 정상이라 「못 쟀다」

# 큰 차트 칸의 canvas 전부를 성기게 읽어 서명을 만든다 — 그림이 바뀌었나만 본다.
# 가장 큰 canvas 하나만 보면 그것이 십자선 겹(빈 그림)이라 영영 안 바뀐다(2026-11-23 첫 돌림 · 셋 중 셋 「안 그려짐」)
_SIG_JS = r"""
function __kjcSig(){
  const host=document.getElementById('kh-big-chart'); if(!host) return null;
  let h=0, n=0;
  host.querySelectorAll('canvas').forEach(c=>{
    if(!c.width||!c.height) return;
    let ctx; try{ctx=c.getContext('2d');}catch(e){return;} if(!ctx) return;
    const d=ctx.getImageData(0,0,c.width,c.height).data; n++;
    for(let i=0;i<d.length;i+=4*97){h=(h*31+d[i]+d[i+1]*3+d[i+2]*7+d[i+3])|0;}
  });
  return n ? n+':'+h : null;
}
"""

# 차트 봉 요청을 종목별로 센다 — 받는 중에 옛 차트에 시세가 붙어 바뀐 것을 「그려짐」 으로 세지 않게(qa 11-23 ①)
_FETCH_HOOK = r"""
(() => { if (window.__kjcF) return; window.__kjcF = {s:{}, e:{}};
  const of = window.fetch;
  window.fetch = function(u, o){ const url = String((u && u.url) || u);
    const m = /\/api\/kis\/chart\b.*[?&]code=([^&]+)/.exec(url); const c = m && decodeURIComponent(m[1]);
    if (c) __kjcF.s[c] = (__kjcF.s[c]||0)+1;
    const p = of.apply(this, arguments);
    if (c) p.then(r => r.clone().text()).catch(()=>{}).finally(() => { __kjcF.e[c] = (__kjcF.e[c]||0)+1; });
    return p; };
})();
"""

_CLICK_JS = _SIG_JS + r"""
(async (code, maxMs, quietMs) => {
  const tr=document.querySelector('#kh-rows tr[data-code="'+code+'"]');
  if(!tr) return {err:'순위표에 없음'};
  const host=document.getElementById('kh-big-chart'), F=window.__kjcF||{s:{},e:{}};
  const s0=F.s[code]||0, e0=F.e[code]||0;
  let base=__kjcSig(), overlay=false, first=null, last=null, changes=0;
  const t0=performance.now(); tr.click();
  return await new Promise(res=>{
    const tick=()=>{
      const now=performance.now();
      if(now-t0>maxMs) return res(first==null?{err:'안 그려짐', overlay}:{ms:first, settled:last, changes, overlay, cut:true});
      const pending=(F.s[code]||0)-s0 > 0 && (F.e[code]||0)-e0 === 0;   // 그 종목 첫 봉 요청이 아직 안 끝남 — 뒤이은 덧붙이기 받기는 안 막는다
      if(host.querySelector('.kh-big-loading')) overlay=true;
      else if(pending && first==null) base=__kjcSig();         // 받는 중 옛 차트 바뀜은 기준으로 삼켜 버린다
      else { const s=__kjcSig();
        if(s && s!==base){ base=s; changes++; last=Math.round(now-t0); if(first==null) first=last; }
        else if(first!=null && now-t0-last>=quietMs) return res({ms:first, settled:last, changes, overlay}); }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
})(%s, %d, %d)
"""

_WATCH_JS = r"""
(async (sec) => {
  const el=document.getElementById('kh-price'); if(!el) return {err:'모달 가격 칸 없음'};
  let last=el.textContent; const t0=performance.now(); const at=[];
  const ob=new MutationObserver(()=>{const t=el.textContent; if(t!==last){last=t; at.push(Math.round(performance.now()-t0));}});
  ob.observe(el,{childList:true,characterData:true,subtree:true});
  await new Promise(r=>setTimeout(r,sec*1000)); ob.disconnect();
  return {at, first:el.textContent};
})(%d)
"""


class Unmeasured(Exception):
    pass


def arg(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def in_market():
    t = time.localtime()     # 맥미니 시계는 KST 다
    if t.tm_wday >= 5:
        return False
    hm = (t.tm_hour, t.tm_min)
    return MARKET_KST[0] <= hm < MARKET_KST[1]


class Tab:
    def __init__(self, ws):
        self.ws, self.n = ws, 0

    def call(self, method, params=None):
        self.n += 1
        CL._send(self.ws, {"id": self.n, "method": method, "params": params or {}})
        while True:
            m = CL._recv(self.ws)
            if m.get("id") == self.n:
                return m

    def ev(self, expr, await_promise=False, timeout=None):
        if timeout:
            self.ws.settimeout(timeout)
        try:
            r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": await_promise})
        finally:
            self.ws.settimeout(30)
        return r.get("result", {}).get("result", {}).get("value")

    def go(self, url):
        self.call("Page.navigate", {"url": url})
        end = time.time() + PAGE_READY_MAX
        while time.time() < end:
            time.sleep(0.5)
            ok = self.ev("!!(document.querySelector('#kh-rows tr[data-code]') && document.querySelector('#kh-big-chart canvas'))")
            if ok:
                time.sleep(1.0)     # 첫 그리기 뒤 덧붙이기가 가라앉게
                return
        raise Unmeasured("첫 화면이 %d초 안에 순위표 · 큰 차트를 안 그렸다 (%s)" % (PAGE_READY_MAX, url))


def measure_click(tab, base, codes):
    tab.go(base)
    sel = tab.ev("(document.querySelector('#kh-rows tr.is-active')||{}).dataset?.code || null")
    out = []
    for c in codes:
        if c == sel:
            out.append({"code": c, "skip": "이미 골라져 있음"})
            continue
        r = tab.ev(_CLICK_JS % (json.dumps(c), CLICK_MAX * 1000, QUIET_MS), await_promise=True, timeout=CLICK_MAX + 10) or {"err": "값 없음"}
        r["code"] = c
        out.append(r)
        sel = c
        time.sleep(AFTER_CLICK_REST)
    return out


def summarize_click(rows):
    s = {}
    for key, label in ((True, "받아 둔 봉 없음(덮개 뜸)"), (False, "받아 둔 봉으로 그림")):
        got = [r for r in rows if "ms" in r and r.get("overlay") == key]
        ms, st = [r["ms"] for r in got], [r["settled"] for r in got]
        s[label] = {"n": len(ms), "median_ms": round(statistics.median(ms)) if ms else None, "ms": ms,
                    "settled_median_ms": round(statistics.median(st)) if st else None, "settled_ms": st}
    return s


def measure_modal(tab, base, code, watch):
    tab.call("Page.navigate", {"url": base + "?code=" + code})
    end = time.time() + PAGE_READY_MAX
    while time.time() < end:
        time.sleep(0.5)
        if tab.ev("!!document.getElementById('kh-price')"):
            break
    else:
        raise Unmeasured("모달이 %d초 안에 안 떴다" % PAGE_READY_MAX)
    time.sleep(2.0)
    r = tab.ev(_WATCH_JS % watch, await_promise=True, timeout=watch + 20) or {"err": "값 없음"}
    at = r.get("at") or []
    gaps = [round((b - a) / 1000, 1) for a, b in zip(at, at[1:])]
    r.update({"code": code, "watch_sec": watch, "changes": len(at), "gaps_sec": gaps,
              "median_gap_sec": statistics.median(gaps) if gaps else None})
    return r


def run_port(port, codes, n, watch, only):
    base = "http://localhost:%d/holdings/" % port
    try:
        urllib.request.urlopen(base, timeout=5)
    except Exception as e:
        raise Unmeasured("서버가 없다(%d): %s" % (port, type(e).__name__))
    dbg = CL.free_port(9460) or 9460
    proc = subprocess.Popen(
        [CL.CHROME, "--headless=new", "--disable-gpu",
         "--user-data-dir=" + tempfile.mkdtemp(prefix="kjc-mchart-"),
         "--no-first-run", "--no-default-browser-check",
         "--remote-debugging-port=%d" % dbg,
         "--window-size=%d,%d" % (VIEW_W, VIEW_H), "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        tabs = None
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % dbg, timeout=2))
                break
            except Exception:
                time.sleep(0.5)
        if not tabs:
            raise Unmeasured("크롬이 디버깅 포트를 안 열었다")
        tab = Tab(CL.ws_connect([t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]))
        tab.call("Page.enable")
        tab.call("Runtime.enable")
        tab.call("Page.addScriptToEvaluateOnNewDocument", {"source": _FETCH_HOOK})
        if tab.ev("innerWidth") != VIEW_W:
            raise Unmeasured("남의 크롬에 붙었다 (창 폭이 다르다)")
        res = {"port": port, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
        if not codes:
            tab.go(base)
            codes = tab.ev("[...document.querySelectorAll('#kh-rows tr[data-code]')].slice(0,%d).map(t=>t.dataset.code)" % (n + 1)) or []
        res["codes"] = codes
        if only in (None, "click"):
            rows = measure_click(tab, base, codes)
            res["click"] = {"rows": rows, "summary": summarize_click(rows)}
        if only in (None, "modal"):
            res["modal"] = measure_modal(tab, base, codes[0], watch) if codes else {"err": "종목 없음"}
        return res, codes
    finally:
        proc.terminate()


def main(argv):
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    port = int(arg(argv, "--port", 8765))
    against = arg(argv, "--against")
    n = int(arg(argv, "--n", DEFAULT_N))
    watch = int(arg(argv, "--watch", DEFAULT_WATCH))
    only = arg(argv, "--only")
    codes = [c for c in (arg(argv, "--codes", "") or "").split(",") if c]
    out_json = arg(argv, "--json")
    if not CL.CHROME:
        print("못 쟀다 — 크롬을 못 찾았다 (KJC_CHROME 으로 알려 주십시오)")
        return 2

    market = in_market()
    ports = [int(against), port] if against else [port]   # 기준(고치기 전)을 먼저 — 같은 종목으로
    results, code = [], 0
    for p in ports:
        try:
            r, codes = run_port(p, codes, n, watch, only)
        except Unmeasured as e:
            print("못 쟀다 — %s" % e)
            return 2
        results.append(r)

    for r in results:
        print("── %d · %s" % (r["port"], r["at"]))
        if "click" in r:
            for row in r["click"]["rows"]:
                if "err" in row:
                    print("  %s  %s" % (row["code"], row["err"]))
                    code = max(code, 1 if row["err"] == "안 그려짐" else 2)
            for label, s in r["click"]["summary"].items():
                print("  클릭→그려짐 · %s : %s번 · 첫 그림 중앙값 %s ms %s · 다 그려짐(%dms 조용) 중앙값 %s ms %s" % (
                      label, s["n"], "—" if s["median_ms"] is None else s["median_ms"], s["ms"], QUIET_MS,
                      "—" if s["settled_median_ms"] is None else s["settled_median_ms"], s["settled_ms"]))
        if "modal" in r:
            m = r["modal"]
            if "err" in m:
                print("  모달  %s" % m["err"])
                code = max(code, 2)
            elif m["changes"] == 0:
                if market:
                    print("  모달 %s · %d초 동안 가격이 한 번도 안 바뀜 — 장중이라 걸림" % (m["code"], m["watch_sec"]))
                    code = max(code, 1)
                else:
                    print("  모달 %s · 가격 안 바뀜 — 장 밖이라 못 잼" % m["code"])
                    code = max(code, 2)
            else:
                print("  모달 %s · %d초 동안 %d번 바뀜 · 간격 중앙값 %s초 · %s" % (m["code"], m["watch_sec"], m["changes"],
                      "—(한 번뿐)" if m["median_gap_sec"] is None else m["median_gap_sec"], m["gaps_sec"]))
    print("  못 보는 것 — 터널 구간(외부접속 기기의 시간) · 재권님 크롬 저장값 · 확대 비율")

    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump({"market": market, "results": results, "exit": code}, f, ensure_ascii=False, indent=1)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
