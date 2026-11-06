# -*- coding: utf-8 -*-
"""화면 찍기 — 재권님 창 크기 하나로만 찍는다 (2026-10-06 지시).

재권님 말씀 — 「그릴때 차트창 싸이즈가 지맘대로 또 그려서 보여주네. 이거 재발 안하게 계속 말하는데 왜 계속
재발하는거지? 이유좀 찾아 제발좀」 → 안 「응 그렇게 해줘」.

원인 — 세션마다 헤드리스 크롬의 창 크기를 제각각 골랐다(기록에 140가지). 홀딩스 화면은 창 폭에 따라 칸이 다시
배치되어, **찍는 창이 다르면 차트 창이 다른 크기로 그려진다.** 재권님 창은 2560×1359 · 배율 1.5 였다.

그래서 크기는 **한 곳**(`tools/view-size.json` — `tools/view-size.html` 로 재권님 창에서 잰 값)에만 두고,
찍기는 이 도구 하나로 한다. 창 크기를 명령에 직접 적으면 훅(`tools/hook-view-size.py`)이 막는다.

    python3 tools/shot.py <주소> <저장할 png>                       재권님 창 크기로
    python3 tools/shot.py <주소> <저장할 png> --phone               좁은 폭(390×844) · 배율은 재권님 창 높이로 센다
    python3 tools/shot.py <주소> <저장할 png> --phone --tall 2100   폰 화면을 세로로 길게
    python3 tools/shot.py <주소> <저장할 png> --full                재권님 창 폭 그대로 · 페이지 끝까지(창 높이는 안 바꾼다)
    python3 tools/shot.py <주소> <저장할 png> --tall 2400           재권님 창 폭 그대로 · 창 높이만 늘려서
    python3 tools/shot.py <주소> <저장할 png> --webgl               3D · 지구본처럼 WebGL 로 그리는 화면
    python3 tools/shot.py <주소> <저장할 png> --wait 8              다 그려지기를 더 기다린다(초 · 기본 3)
    python3 tools/shot.py --size                                    지금 기준 크기만 보기

**찍으면 그림 옆에 `<이름>-보기.html` 을 함께 만든다** — 재권님께는 그 주소를 드린다(그림 그대로는 배율만큼 크게 보인다 ·
「찍은 그림은 창에 맞춰 한눈에 보이게 드린다」 · 2026-10-14).
**좁은 폭(`--phone`) 그림은 창 높이에 맞춘 폭으로 보이고, 흐리지 않게 배율을 올려 찍는다 (2026-11-04 재권님 「폰보기 화면이 너무 작아」).**
배율은 `phone_dpr()` — 재권님 창 높이 × 배율 ÷ 좁은 폭 높이를 올림한다(2560×1359 · 1.5 창이면 3). 칸 배치를 셈하는 폭(390)은 그대로다.

**크롬을 디버깅 포트로 직접 조종한다** (`tools/check-layout.py` 와 같은 길). 첫 판은 `--screenshot` 한 줄로 찍었는데,
홀딩스가 롱폴링으로 서버 연결을 계속 열어 두어 **찍은 뒤에도 크롬이 안 끝나 30~90초씩 걸리고 가끔 실패했다**
(2026-10-06 실측). 지금은 열고 → 다 그려질 때까지(그림 칸 수 · 문서 높이가 1초 동안 그대로) 기다리고 → 찍고 → 닫는다.

**길게 찍어도 폭은 바꾸지 않는다 (2026-11-03 재권님 「이전이랑 크기를 왜 맘대로 바꿔서 보기 힘들게」 → 「응 고쳐」).**
그 전에는 `--tall` 이 `--phone` 에서만 먹어, 긴 페이지를 한 장에 담으려면 폭을 390 으로 바꿀 수밖에 없었다.
`--full` 은 창은 그대로 두고 페이지 끝까지 찍는다(창 높이를 바꾸면 `vh` 로 짠 칸이 다시 배치된다 — 그래서 이쪽을 권한다).
**같은 계열 그림(이름 끝 숫자만 다른 `tg` · `tg2` · 같은 이름 다시 찍기)의 폭이 앞 그림과 다르면 알린다** — 막지 않는다.
폭을 바꿔야 하면 재권님께 먼저 말씀드린다(「찍는 창 크기도 창 크기다」). 세로 길이는 글 길이로 늘 바뀌니 안 센다.

종료 — 0 찍음 · 2 못 찍음(기준 크기를 아직 안 쟀다 · 크롬 없음 · 서버 없음). **2 를 「찍었다」 로 읽지 않는다.**
스크롤바는 숨기지 않는다 — 재권님 화면과 조건이 가깝다(check-layout 과 같은 이유).
"""
import base64
import importlib.util
import json
import math
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


def phone_dpr():
    """좁은 폭 그림의 찍기 배율 — 보기 페이지가 창 높이에 맞춰 키워도 흐리지 않을 만큼(2026-11-04).
    재권님 창 높이(CSS) × 그 창의 배율 = 실제 픽셀 높이 · 그것을 좁은 폭 높이로 나눠 올림. 창 크기를 못 쟀으면 1."""
    size = view_size()
    if not size:
        return 1.0
    return float(max(1, math.ceil(size[1] * view_dpr() / PHONE[1])))


def viewer(out, tall, phone=False, url=""):
    """찍은 그림 옆에 「창에 맞춰 보기」 페이지를 만든다 (2026-10-14 재권님 「화면보다 크게 해서 보여주는 이유가 뭐야?」 ·
    「한눈에 안들어오잖아」 → 룰 「찍은 그림은 창에 맞춰 한눈에 보이게 드린다」).

    그림은 배율만큼 픽셀이 많아(재권님 창 1.5) 그대로 열면 화면보다 크게 보인다. 창 크기 그림은 **줄이기만 한다** — 가로 · 세로 다 들어오게,
    `--tall` · `--full` 은 가로만 맞추고 세로 스크롤. **좁은 폭 그림은 창 높이에 맞춘 폭**(창 높이 × 390/844 · 창 폭보다 넓으면 창 폭)으로
    보인다 — `--tall` 이어도 같은 폭이고 세로만 스크롤한다(2026-11-04 재권님 「폰보기 화면이 너무 작아」).
    그림은 `?t=<찍은 시각>` 으로 불러 같은 이름으로 다시 찍어도 옛 그림이 안 보인다. 이름은 그림 이름 뒤에 `-보기` 만 붙인다.
    찍은 주소를 `<meta name="kjc-shot-url">` 에 남긴다 — 종목 화면(holdings/stock.html)이면 머리에 한 줄을 적고 훅(hook-link-path)이 그것을 센다
    (2026-11-06 재권님 「스케일 맘대로 바꾸는거 계속 반복되는데」 → CLAUDE.md 「홀딩스 작업은 홈 첫 화면으로 보여 드린다」)."""
    base, name = os.path.dirname(out), os.path.basename(out)
    stem = os.path.splitext(name)[0]
    page = os.path.join(base, stem + "-보기.html")
    if phone:
        fit = "width:min(100vw,calc(100vh * %d / %d));height:auto" % PHONE
    else:
        fit = "max-width:100%;height:auto" if tall else "max-width:100vw;max-height:100vh;width:auto;height:auto"
    stock = "holdings/stock.html" in (url or "")
    note = ("<div style=\"position:fixed;top:0;left:0;right:0;padding:6px 12px;font:13px sans-serif;background:var(--kh-bg-card);color:var(--kh-text-secondary)\">"
            "종목 화면 그림 — 홈 첫 화면이 기준(칸 배치가 홈과 달라 차트가 다른 크기로 보입니다)</div>"
            "<link rel=\"stylesheet\" href=\"/assets/css/theme.css\">") if stock else ""
    html = ("<!doctype html><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>%s</title>"
            "<meta name=\"kjc-shot-url\" content=\"%s\">"
            "<style>html,body{margin:0}body{display:flex;justify-content:center}img{display:block;%s}</style>"
            "%s<img src=\"%s?t=%d\" alt=\"%s\">\n") % (stem, html_attr(url), fit, note, name, int(time.time()), stem)
    open(page, "w", encoding="utf-8").write(html)
    if stock:
        print("알림: 종목 화면(holdings/stock.html)을 찍었습니다 — 홀딩스 일은 홈 큰 차트(/holdings/) · 모달(/holdings/?code=<종목>) 그림으로 드립니다. "
              "종목 화면 자체를 고친 때만 이 그림을 드립니다(CLAUDE.md 「홀딩스 작업은 홈 첫 화면으로 보여 드린다」)")
    parts = page.replace("\\", "/").split("/")
    rel = "/".join(parts[parts.index("temp"):]) if "temp" in parts else None
    if rel:
        print("보기: http://localhost:<내 서버 포트>/%s   ← 확인란에는 이 주소(창에 맞춰 한눈에)" % rel)
    else:
        print("보기: %s   ← temp/ 밖이라 http 주소가 없다 — 재권님께 드릴 그림은 temp/ 에 찍는다" % page)


def html_attr(v):
    return str(v or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def png_size(path):
    """PNG 머리에서 (폭, 높이) 픽셀. 못 읽으면 None."""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
    except Exception:
        return None


def series_before(out):
    """같은 계열의 앞 그림 (경로, (폭, 높이)) — 같은 이름을 다시 찍으면 덮이기 전 그것, 아니면 이름 끝 숫자만 다른 것 중 가장 최근.
    없으면 None. 계열은 이름 끝 숫자를 뗀 것으로 가른다(`시황분석-tg2` → `시황분석-tg`)."""
    if os.path.exists(out):
        s = png_size(out)
        return (out, s) if s else None
    base = os.path.dirname(out)
    key = os.path.splitext(os.path.basename(out))[0].rstrip("0123456789").rstrip("-_")
    if not key:
        return None   # 이름이 숫자뿐(1.png)이면 계열을 못 가른다 — 남의 숫자 그림과 묶지 않는다 (qa 11-03)
    best = None
    try:
        names = os.listdir(base)
    except Exception:
        return None
    for n in names:
        stem, ext = os.path.splitext(n)
        if ext.lower() != ".png" or stem.rstrip("0123456789").rstrip("-_") != key:
            continue
        p = os.path.join(base, n)
        s = png_size(p)
        if s and (best is None or os.path.getmtime(p) > best[2]):
            best = (p, s, os.path.getmtime(p))
    return (best[0], best[1]) if best else None


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
        print("쓰는 법: python3 tools/shot.py <주소> <저장할 png> [--phone] [--full] [--tall 높이] [--webgl] [--wait 초]")
        return 2
    url, out = argv[0], os.path.abspath(argv[1])
    phone = "--phone" in argv
    dpr = phone_dpr() if phone else view_dpr()
    full = "--full" in argv
    if phone:
        size = (PHONE[0], int(arg(argv, "--tall", PHONE[1])))
    if not size:
        print("✗ 못 찍음 — 재권님 창 크기를 아직 안 쟀다(%s 없음). 개념정의에 알리십시오." % SIZE_FILE)
        return 2
    if not phone and "--tall" in argv:
        size = (size[0], int(arg(argv, "--tall", size[1])))   # 폭은 재권님 창 그대로 · 높이만
    before = series_before(out)
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
        shot = {"format": "png"}
        h = size[1]
        if full:
            # 창은 그대로 두고 문서 끝까지 — 창 높이를 바꾸면 vh 로 짠 칸이 다시 배치된다
            h = max(int(js("Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)") or size[1]), size[1])
            shot.update({"captureBeyondViewport": True,
                         "clip": {"x": 0, "y": 0, "width": size[0], "height": h, "scale": 1}})
        r = call("Page.captureScreenshot", shot)
        data = r.get("result", {}).get("data")
        if not data:
            print("✗ 못 찍음 — 크롬이 그림을 안 줬다")
            return 2
        open(out, "wb").write(base64.b64decode(data))
        print("찍음: %s · %d × %d%s · 배율 %s%s" % (out, size[0], h, " (페이지 끝까지)" if full else "", dpr,
                                                  " (폰)" if phone else " (재권님 창)"))
        now = png_size(out)
        # 좁은 폭은 셈하는 폭이 늘 390 이라 뺀다 — 픽셀 폭은 배율(창 높이)을 따라 바뀐다
        if not phone and before and now and before[1][0] != now[0]:
            print("⚠ 앞 그림과 폭이 다릅니다 — %s 는 %d × %d 였고 이번은 %d × %d (픽셀)."
                  % (os.path.basename(before[0]), before[1][0], before[1][1], now[0], now[1]))
            print("  폭을 바꿨으면 재권님께 먼저 말씀드립니다. 긴 페이지는 --full 이 폭을 안 바꿉니다(「찍는 창 크기도 창 크기다」).")
        viewer(out, "--tall" in argv or full, phone, url)
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
