# -*- coding: utf-8 -*-
"""파일을 띄우고, 그 창만 앞으로 꺼낸다.

창을 띄울 일이 있으면 이것을 쓴다. P/Invoke 를 직접 부르지 않는다 —
아래 네 가지가 이미 들어 있고, 직접 쓰면 그때마다 다시 지켜야 한다.

    python tools/show-window.py <파일경로> [창제목의 일부]

재권님 룰 (2026-09-16):

    "창띄울때 기존창을 줄이지마"

그래서 이 스크립트가 **하지 않는** 일이 넷이다.

  1. 기존 창을 최소화하지 않는다
  2. 기존 창을 옮기거나 크기를 바꾸지 않는다
  3. 제목으로 못 찾으면 **아무 창도 건드리지 않는다**
  4. **기존 창을 닫지 않는다. 항상 새 창으로 연다**

3번이 핵심이다. 2026-09-16 에 제목 매칭이 빗나갔는데, 그때
「가장 최근에 뜬 Chrome」 을 대신 집어서 재권님이 보고 계시던
Cloudflare 대시보드를 앞으로 꺼냈다. 못 찾았으면 멈췄어야 했다.
찾지 못하는 것은 괜찮고, 엉뚱한 창을 집는 것이 사고다.

4번은 한 번 넣었다가 뺐다 (2026-09-16 지시). 같은 파일을 두 번 띄우면
창이 쌓여서, 제목이 맞는 창을 닫고 새로 여는 방식을 넣었었다.
**그 안전장치가 샜다.** 열려 있던 창 24개로 재보니 이랬다.

    힌트 '주식페이지_개발'   1개 일치 → 통과 → 재권님 세션 창
    힌트 'KJC'              3개 일치 → 통과 → VS Code · Holdings 창
    힌트 '설정'              2글자     → 막힘

**1개만 걸릴 때가 가장 안전해 보이는데 실제로는 가장 위험하다.**
그 하나가 재권님이 쓰시던 창이어도 장치를 전부 통과한다.
글자 수도 척도가 못 된다 — 한글 2글자가 영어 3글자보다 훨씬 특이하다.

    창이 쌓이는 것은 X 를 눌러 닫으면 된다.
    닫혀버린 창은 되돌릴 수 없다.

그래서 닫기를 통째로 뺐다. `hint` 는 **앞으로 꺼낼 창을 고를 때만** 쓴다.

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
# 메모장으로 여는 확장자. 연결 프로그램에 맡기지 않는다 (아래 main 주석 참고).
TEXT_EXT = (".md", ".txt", ".log", ".json", ".csv")


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


def raise_only(title_part, before, filename=""):
    """제목이 맞는 창 하나만 앞으로. 못 찾으면 아무것도 하지 않는다.

    before 는 파일을 열기 **전**의 창 목록이다. 그 안에 이미 있던 창은
    내가 연 것이 아니므로 건드리지 않는다 — 제목이 우연히 겹쳐도 마찬가지다.

    전에는 「새 창 중에 없으면 기존 창까지 뒤진다」 는 폴백이 있었는데 뺐다.
    2026-09-16 에 Cloudflare 대시보드를 앞으로 꺼낸 것이 정확히 그 경로였다.
    **새 창 중에 없으면 아무것도 하지 않는 것이 맞다.**
    """
    old = {h for h, _ in before}
    hits = [(h, t) for h, t in windows()
            if title_part in t and h not in old]

    # 새 창이 안 생겼을 수 있다. 윈도우 11 메모장은 **탭으로 붙어서**,
    # 같은 파일을 세 번 열어도 창은 하나다 (2026-09-16 실측).
    # 그때만 파일명 전체로 한 번 더 찾는다.
    #
    # 위에서 뺀 폴백과 헷갈리기 쉬운데 다르다. 그것은 **사용자가 준 임의의
    # 힌트**로 기존 창을 뒤져서 '룰이 안 지켜' 같은 조각이 엉뚱한 창을 물었다.
    # 이것은 `opentest.md` 처럼 **확장자까지 붙은 파일명**으로만 찾는다.
    # 그 정도면 충분히 특이하고, 걸리는 창은 그 파일을 띄운 창뿐이다.
    if not hits and filename:
        hits = [(h, t) for h, t in windows() if filename in t]

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
    elif path.lower().endswith(TEXT_EXT):
        # 메모장을 직접 부른다. os.startfile 로는 안 열린다 —
        # 이 PC 에 .md 연결 프로그램이 없다 (2026-09-16 확인).
        #
        #     cmd /c assoc .md
        #     File association not found for extension .md
        #
        # 그동안 문서가 열렸던 것은 부르는 쪽에서 notepad 를 직접 지정했기
        # 때문이고, 이 도구를 거치면 아무 일도 일어나지 않았다.
        subprocess.Popen(["notepad.exe", path])
    else:
        os.startfile(path)

    time.sleep(2.0)
    raise_only(hint, before, os.path.basename(path))


if __name__ == "__main__":
    main()
