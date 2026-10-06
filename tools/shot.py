# -*- coding: utf-8 -*-
"""화면 찍기 — 재권님 창 크기 하나로만 찍는다 (2026-10-06 지시).

재권님 말씀 — 「그릴때 차트창 싸이즈가 지맘대로 또 그려서 보여주네. 이거 재발 안하게 계속 말하는데 왜 계속
재발하는거지? 이유좀 찾아 제발좀」 → 안 「응 그렇게 해줘」.

원인 — 세션마다 헤드리스 크롬의 창 크기를 제각각 골랐다. 기록에 열 가지가 넘었다(1600×1200 · 1600×1000 ·
1920×1100 · 1440×900 …). 홀딩스 화면은 창 폭에 따라 칸이 늘고 줄어서, **찍는 창이 다르면 차트 창이 다른 크기로
그려진다.** 코드를 안 바꿔도 재권님 눈에는 「창 크기가 또 바뀌었다」 다. 그리고 재권님 실제 창 크기는 잰 적이 없었다.

그래서 크기는 **한 곳**(`tools/view-size.json` — 재권님 창에서 잰 값)에만 두고, 찍기는 이 도구 하나로 한다.
창 크기를 명령에 직접 적으면 훅(`tools/hook-view-size.py`)이 막는다.

    python3 tools/shot.py <주소> <저장할 png>              재권님 창 크기로
    python3 tools/shot.py <주소> <저장할 png> --phone      폰(390×844) — 폰 화면을 보여 드릴 때만
    python3 tools/shot.py <주소> <저장할 png> --phone --tall 2100   폰 화면을 세로로 길게
    python3 tools/shot.py --size                           지금 기준 크기만 보기

종료 — 0 찍음 · 2 못 찍음(기준 크기를 아직 안 쟀다 · 크롬 없음 · 서버 없음). **2 를 「찍었다」 로 읽지 않는다.**
스크롤바는 숨기지 않는다 — 재권님 화면과 조건이 가깝다(check-layout 과 같은 이유).
"""
import json
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SIZE_FILE = os.path.join(ROOT, "tools", "view-size.json")
PHONE = (390, 844)
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
]


def view_size():
    """(폭, 높이) — 재권님 창에서 잰 값. 없으면 None(「못 쟀다」)."""
    try:
        d = json.load(open(SIZE_FILE, encoding="utf-8"))
        return int(d["width"]), int(d["height"])
    except Exception:
        return None


def view_dpr():
    try:
        return float(json.load(open(SIZE_FILE, encoding="utf-8")).get("dpr") or 1)
    except Exception:
        return 1.0


def chrome():
    env = os.environ.get("KJC_CHROME")
    for p in ([env] if env else []) + CHROME_CANDIDATES:
        if p and os.path.exists(p):
            return p
    return None


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    size = view_size()
    if argv[0] == "--size":
        print("기준 창 크기:", ("%d × %d (%s)" % (size[0], size[1], SIZE_FILE)) if size else "**아직 안 쟀다**")
        return 0 if size else 2
    if len(argv) < 2:
        print("쓰는 법: python3 tools/shot.py <주소> <저장할 png> [--phone]")
        return 2
    url, out = argv[0], argv[1]
    if "--phone" in argv:
        size = PHONE
        if "--tall" in argv:                       # 폰 화면을 세로로 길게(전체) — 폭은 그대로
            size = (PHONE[0], int(argv[argv.index("--tall") + 1]))
    if not size:
        print("✗ 못 찍음 — 재권님 창 크기를 아직 안 쟀다(%s 없음). 개념정의에 알리십시오." % SIZE_FILE)
        return 2
    exe = chrome()
    if not exe:
        print("✗ 못 찍음 — 크롬을 못 찾았다(KJC_CHROME 으로 줄 수 있다)")
        return 2
    cmd = [exe, "--headless=new", "--disable-gpu", "--no-first-run",
           "--window-size=%d,%d" % size, "--virtual-time-budget=8000",
           "--force-device-scale-factor=%s" % (1 if "--phone" in argv else view_dpr()),
           "--screenshot=%s" % os.path.abspath(out), url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if r.returncode != 0 or not os.path.exists(out):
        print("✗ 못 찍음 — 크롬 종료 %d · %s" % (r.returncode, (r.stderr or "").strip()[-200:]))
        return 2
    print("찍음: %s · %d × %d%s" % (out, size[0], size[1], " (폰)" if "--phone" in argv else " (재권님 창)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
