# -*- coding: utf-8 -*-
"""파일을 띄우고, 그 창만 앞으로 꺼낸다.

창을 띄울 일이 있으면 이것을 쓴다. P/Invoke 를 직접 부르지 않는다 —
아래 세 가지가 이미 들어 있고, 직접 쓰면 그때마다 다시 지켜야 한다.

    python tools/show-window.py <파일경로> [창제목의 일부]

재권님 룰 (2026-09-16):

    "창띄울때 기존창을 줄이지마"

그래서 이 스크립트가 **하지 않는** 일이 셋이다.

  1. 기존 창을 최소화하지 않는다
  2. 기존 창을 옮기거나 크기를 바꾸지 않는다
  3. 제목으로 못 찾으면 **아무 창도 건드리지 않는다**

3번이 핵심이다. 2026-09-16 에 제목 매칭이 빗나갔는데, 그때
「가장 최근에 뜬 Chrome」 을 대신 집어서 재권님이 보고 계시던
Cloudflare 대시보드를 앞으로 꺼냈다. 못 찾았으면 멈췄어야 했다.
찾지 못하는 것은 괜찮고, 엉뚱한 창을 집는 것이 사고다.

SW_RESTORE 는 **내가 방금 연 창에만** 쓴다. 그 창이 최소화된 채로
열렸을 때 펴 주는 용도이고, 다른 창에는 쓰지 않는다.
"""
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

# 윈도우 콘솔은 기본이 cp949 라 '—' 같은 글자에서 죽는다.
# 출력만 UTF-8 로 바꾼다 (tools/check-theme-sync.py 와 같은 처리).
#
# 이 두 줄이 없어도 개발 중에는 멀쩡해 보였다. 환경변수 PYTHONIOENCODING 이
# 걸린 셸에서만 돌려봤기 때문이다. 그것이 없는 곳 — 특히 .bat 이 부르는
# cmd — 에서는 판단이 맞아도 출력에서 죽어, 부르는 쪽은 실패로 읽는다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

u32 = ctypes.windll.user32

SW_RESTORE = 9
CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def windows():
    """보이는 최상위 창을 (핸들, 제목) 으로 모은다."""
    found = []
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd):
            n = u32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(hwnd, buf, n + 1)
                found.append((hwnd, buf.value))
        return True

    u32.EnumWindows(proto(cb), 0)
    return found


def raise_only(title_part, before):
    """제목이 맞는 창 하나만 앞으로. 못 찾으면 아무것도 하지 않는다.

    before 는 파일을 열기 **전**의 창 목록이다. 그 안에 이미 있던 창은
    내가 연 것이 아니므로 건드리지 않는다 — 제목이 우연히 겹쳐도 마찬가지다.
    """
    old = {h for h, _ in before}
    hits = [(h, t) for h, t in windows()
            if title_part in t and h not in old]

    if not hits:                       # 새 창 중에 없으면 이미 열려 있던 것일 수 있다
        hits = [(h, t) for h, t in windows() if title_part in t]

    if len(hits) != 1:
        print(f"  건드리지 않음 — 창을 특정하지 못했습니다 ({len(hits)}개 일치)")
        print("  (엉뚱한 창을 앞으로 꺼내느니 아무것도 안 하는 편이 낫습니다)")
        return False

    hwnd, title = hits[0]
    u32.ShowWindow(hwnd, SW_RESTORE)   # 내가 연 창에만 쓴다
    u32.BringWindowToTop(hwnd)
    u32.SetForegroundWindow(hwnd)
    print(f"  앞으로: {title}")
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    path = os.path.abspath(sys.argv[1])
    if not os.path.exists(path):
        print(f"  없는 파일입니다: {path}")
        return

    # 제목 조각을 안 주면 파일명에서 뽑는다
    hint = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(os.path.basename(path))[0]

    before = windows()

    if path.lower().endswith((".html", ".htm")):
        exe = next((c for c in CHROME if os.path.exists(c)), None)
        url = "file:///" + path.replace("\\", "/")
        if exe:
            subprocess.Popen([exe, "--new-window", url])
        else:
            os.startfile(path)
    else:
        os.startfile(path)

    time.sleep(2.0)
    raise_only(hint, before)


if __name__ == "__main__":
    main()
