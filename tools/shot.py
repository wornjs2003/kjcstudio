# -*- coding: utf-8 -*-
"""화면 찍기 — 재권님 창 크기 하나로만 찍는다 (2026-10-06 지시).

재권님 말씀 — 「그릴때 차트창 싸이즈가 지맘대로 또 그려서 보여주네. 이거 재발 안하게 계속 말하는데 왜 계속
재발하는거지? 이유좀 찾아 제발좀」 → 안 「응 그렇게 해줘」.

원인 — 세션마다 헤드리스 크롬의 창 크기를 제각각 골랐다(기록에 140가지). 홀딩스 화면은 창 폭에 따라 칸이 다시
배치되어, **찍는 창이 다르면 차트 창이 다른 크기로 그려진다.** 재권님 창은 2560×1359 · 배율 1.5 였다.

그래서 크기는 **한 곳**(`tools/view-size.json` — `tools/view-size.html` 로 재권님 창에서 잰 값)에만 두고,
찍기는 이 도구 하나로 한다. 창 크기를 명령에 직접 적으면 훅(`tools/hook-view-size.py`)이 막는다.

    python3 tools/shot.py <주소> <저장할 png>                       재권님 창 크기로
    python3 tools/shot.py <주소> <저장할 png> --phone               폰(390×844)
    python3 tools/shot.py <주소> <저장할 png> --phone --tall 2100   폰 화면을 세로로 길게
    python3 tools/shot.py <주소> <저장할 png> --webgl               3D · 지구본처럼 WebGL 로 그리는 화면
    python3 tools/shot.py <주소> <저장할 png> --wait 8              다 그려지기를 더 기다린다(초 · 기본 3)
    python3 tools/shot.py --size                                    지금 기준 크기만 보기

**크롬을 디버깅 포트로 직접 조종한다** (`tools/check-layout.py` 와 같은 길). 첫 판은 `--screenshot` 한 줄로 찍었는데,
홀딩스가 롱폴링으로 서버 연결을 계속 열어 두어 **찍은 뒤에도 크롬이 안 끝나 30~90초씩 걸리고 가끔 실패했다**
(2026-10-06 실측). 지금은 열고 → 다 그려질 때까지(그림 칸 수 · 문서 높이가 1초 동안 그대로) 기다리고 → 찍고 → 닫는다.

종료 — 0 찍음 · 2 못 찍음(기준 크기를 아직 안 쟀다 · 크롬 없음 · 서버 없음). **2 를 「찍었다」 로 읽지 않는다.**
스크롤바는 숨기지 않는다 — 재권님 화면과 조건이 가깝다(check-layout 과 같은 이유).
"""
import base64
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SIZE_FILE = os.path.join(ROOT, "tools", "view-size.json")
PHONE = (390, 844)

# 크롬 찾기 · 빈 포트 · 웹소켓은 check-layout 의 것을 그대로 쓴다 — 두 벌로 두지 않는다
_spec = importlib.util.spec_from_file_location("check_layout", os.path.join(ROOT, "tools", "check-layout.py"))
CL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CL)


def _load():
    try:
        return json.load(open(SIZE_FILE, encoding="utf-8"))
    except Exception:
        return None


def view_size():
    """(폭, 높이) — 재권님 창에서 잰 값. 없으면 None(「못 쟀다」)."""
    d = _load()
    try:
        return int(d["width"]), int(d["height"])
    except Exception:
        return None


def view_dpr():
    d = _load() or {}
    try:
        return float(d.get("dpr") or 1)
    except Exception:
        return 1.0


def arg(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    size = view_size()
    if argv[0] == "--size":
        print("기준 창 크기:", ("%d × %d · 배율 %s (%s)" % (size[0], size[1], view_dpr(), SIZE_FILE)) if size else "**아직 안 쟀다**")
        return 0 if size else 2
    if len(argv) < 2:
        print("쓰는 법: python3 tools/shot.py <주소> <저장할 png> [--phone] [--webgl] [--wait 초]")
        return 2
    url, out = argv[0], os.path.abspath(argv[1])
    phone = "--phone" in argv
    dpr = 1.0 if phone else view_dpr()
    if phone:
        size = (PHONE[0], int(arg(argv, "--tall", PHONE[1])))
    if not size:
        print("✗ 못 찍음 — 재권님 창 크기를 아직 안 쟀다(%s 없음). 개념정의에 알리십시오." % SIZE_FILE)
        return 2
    if not CL.CHROME:
        print("✗ 못 찍음 — 크롬을 못 찾았다(KJC_CHROME 으로 줄 수 있다)")
        return 2
    wait = float(arg(argv, "--wait", 3))
    port = CL.free_port(9400) or 9400
    # --webgl — swiftshader 둘이 없으면 WebGL 화면(3D 분해도 · 지구본 지도)이 빈 채로 찍힌다(2026-10-06 시황분석 실측)
    gl = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] if "--webgl" in argv else []
    proc = subprocess.Popen(
        [CL.CHROME, "--headless=new", "--disable-gpu"] + gl +
        ["--user-data-dir=" + tempfile.mkdtemp(prefix="kjc-shot-"), "--no-first-run", "--no-default-browser-check",
         "--remote-debugging-port=%d" % port, "--window-size=%d,%d" % size, "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        tabs = None
        for _ in range(80):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % port, timeout=2))
                break
            except Exception:
                time.sleep(0.25)
        if not tabs:
            print("✗ 못 찍음 — 크롬이 디버깅 포트를 안 열었다")
            return 2
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
            r = call("Runtime.evaluate", {"expression": expr, "returnByValue": True})
            return r.get("result", {}).get("result", {}).get("value")

        call("Page.enable")
        call("Emulation.setDeviceMetricsOverride", {"width": size[0], "height": size[1],
                                                     "deviceScaleFactor": dpr, "mobile": phone})
        # 내가 띄운 크롬인지 — 창 폭으로 본다. 폰은 뺀다: 폰 흉내에서는 viewport 설정이 없는 화면이 980 폭으로 잡히는 것이 정상이다
        if not phone and js("innerWidth") != size[0]:
            print("✗ 못 찍음 — 남의 크롬에 붙었다(창 폭이 %s) · 잠시 뒤 다시" % js("innerWidth"))
            return 2
        call("Page.navigate", {"url": url})
        # 다 그려질 때까지 — 문서가 열리고, 그림 칸 · 이미지 수와 문서 높이가 1초 동안 그대로이면 멈춘다(최대 20초)
        t0, last, still = time.time(), None, 0
        while time.time() - t0 < 20:
            time.sleep(0.25)
            st = js("document.readyState + '|' + document.querySelectorAll('canvas,img,svg').length + '|' + document.body.scrollHeight")
            if st and st.startswith("complete") and st == last:
                still += 1
                if still >= 4:
                    break
            else:
                still = 0
            last = st
        time.sleep(wait)
        r = call("Page.captureScreenshot", {"format": "png"})
        data = r.get("result", {}).get("data")
        if not data:
            print("✗ 못 찍음 — 크롬이 그림을 안 줬다")
            return 2
        open(out, "wb").write(base64.b64decode(data))
        print("찍음: %s · %d × %d · 배율 %s%s" % (out, size[0], size[1], dpr, " (폰)" if phone else " (재권님 창)"))
        return 0
    except urllib.error.URLError:
        print("✗ 못 찍음 — 서버가 없다")
        return 2
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
