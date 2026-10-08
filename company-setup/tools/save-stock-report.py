#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시황분석 리포트를 「쓴 때의 값」 문서로 저장한다 → company-setup/data/stock-report/docs/<코드>.json

    python3 company-setup/tools/save-stock-report.py <종목코드> [--port 8771]

2026-10-08 재권님 「시황분석 리포트는 작성되는게 값을 불러오는게 아니고 문서로 작성되서 저장되도록 해줘. 다만 글 읽는게 위아래로
많으니 접기는 살려주고」. 전에는 리포트를 열 때마다 서버에서 값을 받아 그려서, 같은 리포트가 여는 때마다 숫자가 달랐다.

    하는 일   헤드리스 크롬으로 stock-report.html?code=<코드>&live=1 을 열어 다 그려지기를 기다리고(window.__rp 가 생기면),
              차트 그림(canvas)을 이미지로 굳힌 뒤 본문(#rp)을 통째로 담는다. 접기(details)는 그대로 남아 화면이 다시 붙인다
    여는 쪽   stock-report.js 가 저장본이 있으면 그것을 열고(머리에 「저장본 · 쓴 시각」), 없거나 ?live=1 이면 지금 값으로 그린다
    언제      리포트 글(data/stock-report/<코드>.json)을 고쳐 쓴 뒤 — 세션이 돌린다. 주기 실행은 없다

크롬 띄우기 · 웹소켓은 tools/check-layout.py 의 것을 그대로 쓴다(tools/shot.py 와 같은 길).
"""
import importlib.util, json, os, subprocess, sys, tempfile, time, urllib.request
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUTDIR = os.path.join(HERE, "..", "data", "stock-report", "docs")
_spec = importlib.util.spec_from_file_location("check_layout", os.path.join(ROOT, "tools", "check-layout.py"))
CL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CL)


def main(argv):
    if not argv or argv[0].startswith("-"):
        print(__doc__); return 2
    code = argv[0]
    port_srv = argv[argv.index("--port") + 1] if "--port" in argv else "8771"
    url = "http://localhost:%s/company-setup/stock-report.html?code=%s&live=1&open=all" % (port_srv, code)
    if not CL.CHROME:
        print("✗ 못 저장 — 크롬을 못 찾았다"); return 2
    port = CL.free_port(9450) or 9450
    proc = subprocess.Popen([CL.CHROME, "--headless=new", "--disable-gpu", "--user-data-dir=" + tempfile.mkdtemp(prefix="kjc-save-"),
                             "--no-first-run", "--remote-debugging-port=%d" % port, "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        tabs = None
        for _ in range(80):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % port, timeout=2)); break
            except Exception:
                time.sleep(0.25)
        if not tabs:
            print("✗ 못 저장 — 크롬이 디버깅 포트를 안 열었다"); return 2
        ws = CL.ws_connect([t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"])
        n = [0]

        def call(method, params=None):
            n[0] += 1
            CL._send(ws, {"id": n[0], "method": method, "params": params or {}})
            while True:
                m = CL._recv(ws)
                if m.get("id") == n[0]:
                    return m

        def js(expr):
            return call("Runtime.evaluate", {"expression": expr, "returnByValue": True}).get("result", {}).get("result", {}).get("value")

        call("Page.enable")
        call("Page.navigate", {"url": url})
        t0 = time.time()
        while time.time() - t0 < 40 and not js("!!window.__rp"):
            time.sleep(0.5)
        if not js("!!window.__rp"):
            print("✗ 못 저장 — 리포트가 40초 안에 다 안 그려졌다(서버 · 주소 확인: %s)" % url); return 2
        time.sleep(1.5)
        got = js("""(() => {
          const rp = document.getElementById('rp');
          rp.querySelectorAll('canvas').forEach((c) => {           // 차트는 그림으로 굳힌다 — 저장본에서는 다시 그릴 값이 없다
            const im = document.createElement('img'); im.src = c.toDataURL('image/png'); im.className = c.className;
            im.alt = '차트(저장한 때의 그림)'; im.style.width = '100%'; im.style.height = 'auto'; im.id = c.id; c.replaceWith(im);
          });
          rp.querySelectorAll('.rp-live-note').forEach((x) => x.remove());   // 「저장본 없음 · 지금 값으로 그림」 표시는 저장본에 안 담는다
          const t = (document.getElementById('rp-title') || {}).textContent || '';
          return JSON.stringify({ html: rp.innerHTML, name: t.trim().split(/\\s+/)[0] || '' });
        })()""")
        d = json.loads(got)
        doc = {"code": code, "name": d["name"], "savedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
               "from": "stock-report.html?code=%s&live=1 을 그린 그대로(서버 %s)" % (code, port_srv), "html": d["html"]}
        os.makedirs(OUTDIR, exist_ok=True)
        out = os.path.join(OUTDIR, "%s.json" % code)
        tmp = out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(doc, fp, ensure_ascii=False)
        os.replace(tmp, out)
        print("저장: %s · %s · %s · %d KB" % (os.path.relpath(out, ROOT), d["name"], doc["savedAt"], os.path.getsize(out) // 1024))
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
