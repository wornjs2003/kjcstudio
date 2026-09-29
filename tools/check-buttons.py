#!/usr/bin/env python3
"""홀딩스 화면의 **눌리는 것**을 뽑아 하나씩 눌러 보고, 의도대로 도는지 본다.

재권님 지시로 만들었다 (2026-09-29) — **「홀딩스 안에 버튼들 의도대로 잘 되는지
검수… 하나하나 직접하는 건 비효율적」.**

    python3 tools/check-buttons.py            뽑기만 한다 (누르지 않는다)
    python3 tools/check-buttons.py --click    눌러 본다 (**아직 안 만들었다**)
    python3 tools/check-buttons.py --port N   다른 서버를 본다 (기본 8767)

**⚠️ 8767(중간서버)을 기본으로 본다.** 2026-09-29 12:08 부터 **8765 가
텔레그램 발송 담당**이라, 거기 대고 누르면 **진짜로 폰이 울린다.**
8767 은 `is_sender` 가 `MAIN_PORT`(8765)만 보므로 **포트 층에서 막혀 있다.**

**막는 층을 겹친다.** 포트 하나만 믿지 않는다 —

    ① 대상이 8767            포트 층
    ② `Fetch` 로 쓰기 가로채기  PUT · POST · DELETE 를 **네트워크에서** 끊는다
    ③ 대화상자 자동 닫기       `Page.javascriptDialogOpening`

**② 를 가로챈 쪽에서 확인하면 아무것도 확인하지 않은 것**이라, 가로챈 건수를
따로 세어 **끝에 보여준다.** 0 이 아니면 그만큼이 실제로 막힌 것이다.

**소스 셈과 대보는 이유** — 화면에서 뽑은 수가 소스의 「버튼을 만드는 자리」
수보다 **적으면 놓친 것**이다. 「대상 0개를 `0` 으로 내지 않는다」 가 이 자리다.
소스 셈은 하한 대조용이고, **틀 하나가 반복문 안에 있으면 화면에서는 수십 개**가
되므로 많이 나오는 것은 정상이다.

크롬 조종은 `tools/check-layout.py` 것을 **그대로 가져다 쓴다.** 복제하지
않는다 — 「같은 값은 한 곳에만 둔다」.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

# 윈도우 콘솔은 기본이 cp949 라 '—' 같은 글자에서 죽는다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- check-layout.py 의 크롬 조종을 빌려 쓴다 ------------------------------
# 파일 이름에 `-` 가 있어 보통 import 가 안 된다. 경로로 읽는다.
_spec = importlib.util.spec_from_file_location(
    "_layout", os.path.join(ROOT, "tools", "check-layout.py"))
_layout = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_layout)

CHROME = _layout.CHROME
ws_connect = _layout.ws_connect
_send = _layout._send
_recv = _layout._recv
VIEW_W, VIEW_H = _layout.VIEW_W, _layout.VIEW_H

PORT_DEFAULT = 8767          # **중간서버.** 위 주석 참고
CDP_PORT = 9223              # check-layout 과 안 겹치게
PAGES = ["index.html", "stock.html", "daily.html", "news.html"]

# 화면에서 **눌리는 것**을 뽑는다. 대상을 박지 않는다 — 뽑는 **방법**을 적는다.
# `cursor:pointer` 까지 보는 것은, 이 저장소가 `<div>` 에 click 리스너를 거는
# 자리가 많아서다(2026-09-29 실측 — click 리스너 33곳).
PICK = r"""
(() => {
  const out = [];
  const seen = new Set();
  const push = (el, how) => {
    if (seen.has(el)) return;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;        // 안 보이는 것은 뺀다
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') return;
    seen.add(el);
    out.push({
      how, tag: el.tagName.toLowerCase(),
      id: el.id || '', cls: (el.className || '').toString().slice(0, 40),
      text: (el.innerText || el.value || el.title || '').trim().slice(0, 30),
      x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
      w: Math.round(r.width), h: Math.round(r.height)
    });
  };
  document.querySelectorAll('button').forEach(e => push(e, 'button'));
  document.querySelectorAll('[role="button"]').forEach(e => push(e, 'role'));
  document.querySelectorAll('a[href]').forEach(e => push(e, 'a'));
  document.querySelectorAll('[onclick]').forEach(e => push(e, 'onclick'));
  document.querySelectorAll('*').forEach(e => {
    if (getComputedStyle(e).cursor === 'pointer') push(e, 'pointer');
  });

  // **같은 종류는 대표 하나만 남긴다.**
  //
  // 안 묶으면 2072개가 나온다(2026-09-29 실측 — news 한 장에 1147개).
  // 순위표·목록은 **줄마다 같은 틀**이라 하나가 되면 나머지도 된다.
  // 하나씩 누르면 몇 시간이 걸려 **아무도 안 돌린다** — 안 돌리는 검사는
  // 없는 것과 같다.
  //
  // **묶는 값은 `모양 + 태그 + 클래스` 다.** 텍스트로 묶으면 종목 이름마다
  // 갈려서 안 줄고, 클래스로만 묶으면 다른 모양이 섞인다.
  //
  // **대표만 눌렀다는 것은 결과에 적는다** — 「걸렸다」 와 「위반이다」 를
  // 가르는 것과 같은 자리다. 같은 클래스인데 동작이 다른 것이 있으면
  // 이 도구는 못 본다.
  const rep = new Map();
  for (const it of out) {
    const key = it.how + '|' + it.tag + '|' + it.cls;
    if (!rep.has(key)) { it.같은것 = 1; rep.set(key, it); }
    else rep.get(key).같은것 += 1;
  }
  return [...rep.values()];
})()
"""


def source_floor():
    """소스에서 **버튼을 만드는 자리** 수. 화면 셈의 하한 대조용이다.

    **이것이 「버튼 수」 가 아니다.** 틀 하나가 반복문 안에 있으면 화면에서는
    수십 개가 된다. **화면 셈이 이 값보다 적으면 놓친 것**이라는 뜻으로만 쓴다.
    """
    n = 0
    for base, _, files in os.walk(os.path.join(ROOT, "holdings")):
        if "vendor" in base or "node_modules" in base:
            continue
        for fn in files:
            if not fn.endswith((".html", ".js")):
                continue
            try:
                with open(os.path.join(base, fn), encoding="utf-8") as f:
                    s = f.read()
            except Exception:
                continue
            n += s.count("<button")
            n += s.count("createElement('button')")
            n += s.count('createElement("button")')
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT_DEFAULT,
                    help="어느 서버를 볼지 (기본 %d · 중간서버)" % PORT_DEFAULT)
    ap.add_argument("--click", action="store_true",
                    help="눌러 본다 — **아직 안 만들었습니다**")
    args = ap.parse_args()

    base = "http://localhost:%d/holdings/" % args.port

    if args.port == 8765:
        print("⚠️ 8765 는 **텔레그램 발송 담당**입니다 (2026-09-29 12:08 부터).")
        print("   누르면 실제로 폰이 울릴 수 있습니다. 8767 을 쓰십시오.")
        return 2

    try:
        urllib.request.urlopen(base, timeout=3)
    except Exception as e:
        print("서버가 없습니다 — %d 를 먼저 띄우십시오 (%s)" % (args.port, type(e).__name__))
        return 2

    if not CHROME:
        print("크롬을 못 찾았습니다")
        return 2

    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu",
         "--user-data-dir=" + tempfile.mkdtemp(prefix="kjc-btn-"),
         "--no-first-run", "--no-default-browser-check",
         "--remote-debugging-port=%d" % CDP_PORT,
         "--window-size=%d,%d" % (VIEW_W, VIEW_H), "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        tabs = None
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen(
                    "http://127.0.0.1:%d/json" % CDP_PORT, timeout=2))
                break
            except Exception:
                time.sleep(0.5)
        if not tabs:
            print("크롬이 디버깅 포트를 안 열었습니다")
            return 2

        ws = ws_connect(tabs[0]["webSocketDebuggerUrl"])
        counter = [0]

        def call(method, params=None):
            counter[0] += 1
            _send(ws, {"id": counter[0], "method": method, "params": params or {}})
            while True:
                m = _recv(ws)
                if m.get("id") == counter[0]:
                    return m

        call("Page.enable")

        found = {}
        for page in PAGES:
            call("Page.navigate", {"url": base + page})
            time.sleep(3.0)
            r = call("Runtime.evaluate", {"expression": PICK, "returnByValue": True})
            got = r.get("result", {}).get("result", {}).get("value") or []
            found[page] = got

        floor = source_floor()
        total = sum(len(v) for v in found.values())

        print("눌리는 것 — 화면 %d장" % len(found))
        for page, items in found.items():
            by = {}
            for it in items:
                by[it["how"]] = by.get(it["how"], 0) + 1
            kinds = " · ".join("%s %d" % (k, v) for k, v in sorted(by.items()))
            raw = sum(it.get("같은것", 1) for it in items)
            print("  %-12s %3d종류 (실제 %4d개)   %s" % (page, len(items), raw, kinds))

        print("")
        raw_total = sum(it.get("같은것", 1) for v in found.values() for it in v)
        print("  화면에서 뽑은 것  %d종류 (실제 %d개)" % (total, raw_total))
        print("    **같은 모양·태그·클래스는 대표 하나만 셉니다.**")
        print("    목록은 줄마다 같은 틀이라 하나가 되면 나머지도 됩니다 —")
        print("    **다만 같은 클래스인데 동작이 다른 것은 이 도구가 못 봅니다.**")
        print("  소스의 만드는 자리 %d   (하한 대조용 — 적으면 놓친 것입니다)" % floor)

        if total == 0:
            print("")
            print("  **0개입니다. 「버튼이 없다」 가 아니라 「못 뽑았다」 일 수 있습니다.**")
            print("  화면이 다 그려지기 전에 쟀거나 선택자가 안 맞는 것입니다.")
            return 2
        if total < floor:
            print("")
            print("  ⚠️ 소스보다 적습니다 — 놓친 자리가 있습니다.")

        if args.click:
            print("")
            print("  ⚠️ **누르는 것은 아직 안 만들었습니다.** 지금은 뽑기까지입니다.")
            print("     쓰기 가로채기(`Fetch`)와 대화상자 닫기를 먼저 붙인 뒤에")
            print("     누릅니다 — **막는 층 없이 누르면 폰이 울립니다.**")
        return 0
    finally:
        proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
