# -*- coding: utf-8 -*-
"""파일을 띄우고, 그 창만 앞으로 꺼낸다.

창을 띄울 일이 있으면 이것을 쓴다. **직접 열지도, P/Invoke 를 부르지도 않는다** —
아래 「하지 않는 일」 이 이미 들어 있고, 직접 쓰면 그때마다 다시 지켜야 한다.
`Start-Process <주소>` 로 열면 이 장치를 통째로 건너뛴다.

    python tools/show-window.py <파일경로> [창제목의 일부]

재권님 룰 (2026-09-16):

    "창띄울때 기존창을 줄이지마"

    ① 띄우는 것 — 로컬 이미지 · 로컬 웹페이지
    ② 문자로 된 것은 메모장으로 연다
    ③ 앞으로 꺼낼 때는 **그 프로그램의 창만** 본다. 제목으로 짐작하지 않는다

③ 이 따로 있는 이유는, 버그가 **여는 자리가 아니라 연 다음**에 있어서다.

    이미지    뷰어·Chrome          새 창 생김        → before/after 로 잡힘
    웹페이지  Chrome --new-window  새 창 생김        → 잡힘
    문자      메모장               **새 창 안 생김**  → 제목으로 짐작하러 간다

메모장이 탭으로 붙어 새 창이 없고, 그때 제목으로 찾으면 이렇게 된다.

    'kis-worker.js' 로 찾음 → 1개 일치
    → kis-worker.js - KJCStudio - Visual Studio Code

**제목은 그 파일을 연 다른 프로그램도 갖고 있다.** ② 때문에 문자는 항상
이 길로 가므로 오히려 더 자주 난다. 그래서 프로그램으로 거른다.

**이 스크립트가 「하지 않는 일」 은 `CLAUDE.md` 의
「창을 띄울 때 기존 창을 건드리지 않는다」 절에 있다. 여기 다시 적지 않는다.**

전에는 그 목록을 여기에도 적어 두었다가 **2026-09-16 에 셋 vs 넷,
2026-09-18 에 넷 vs 다섯으로 같은 자리가 두 번 갈렸다.**
대조 도구를 만들자는 이야기가 나왔지만 만들지 않기로 했다 (2026-09-18 지시) —
값이 아니라 **문장**이라, 한쪽을 더 낫게 고쳐 쓰기만 해도 불일치가 뜬다.
그것을 줄이려면 항목 수를 박아야 하는데 그건 같은 날 양쪽에서 빼낸 그 숫자다.
**검사기를 만드는 대신 복제를 없앴다.**

아래는 그 목록의 **경위**다. 무엇을 하지 않는지가 아니라 왜 그렇게 됐는지라
코드 옆에 둔다.

「제목으로 못 찾으면 아무 창도 건드리지 않는다」 가 핵심이다. 2026-09-16 에 제목 매칭이 빗나갔는데, 그때
「가장 최근에 뜬 Chrome」 을 대신 집어서 재권님이 보고 계시던
Cloudflare 대시보드를 앞으로 꺼냈다. 못 찾았으면 멈췄어야 했다.
찾지 못하는 것은 괜찮고, 엉뚱한 창을 집는 것이 사고다.

「이미 띄운 것은 다시 열지 않는다」 가 2026-09-18 에 생겼다. 그 전에는
「닫지 않는다. **항상 새 창으로 연다**」 한 줄이었고, **그 한 줄이 창을 쌓으라고 시키고 있었다.** 닫지 않는 것과
매번 새로 여는 것은 다른 이야기인데 묶여 있었다.

  2026-09-16   CLAUDE.md 창 16개
  2026-09-18   md-diff 창 4개

이제 already_open() 이 먼저 보고, 있으면 열지 않는다. **브라우저를 새로고침시킬
방법이 없어서** 그 대신 Ctrl+Shift+R 을 부탁드린다고 알린다.

「닫지 않는다」 는 한 번 반대로 넣었다가 뺐다 (2026-09-16 지시). 같은 파일을 두 번 띄우면
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
import io
import json
import os
import re
import subprocess
import sys
import time
from ctypes import wintypes

# 윈도우 콘솔은 기본이 cp949 라 '—' 같은 글자에서 죽는다.
# 출력만 UTF-8 로 바꾼다 (holdings/tools/check-theme-sync.py 와 같은 처리).
#
# 이 두 줄이 없어도 개발 중에는 멀쩡해 보였다. 환경변수 PYTHONIOENCODING 이
# 걸린 셸에서만 돌려봤기 때문이다. 그것이 없는 곳 — 특히 .bat 이 부르는
# cmd — 에서는 판단이 맞아도 출력에서 죽어, 부르는 쪽은 실패로 읽는다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32

SW_RESTORE = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
# 메모장으로 여는 확장자. 연결 프로그램에 맡기지 않는다 (아래 main 주석 참고).
TEXT_EXT = (".md", ".txt", ".log", ".json", ".csv")


def session_name():
    """이 세션의 이름. 못 알아내면 빈 문자열.

    창을 여럿 띄워 두면 **어느 세션이 띄운 것인지 알 수 없다.** 2026-09-16 에
    CLAUDE.md 창이 16개 쌓여 재권님이 "이 창 누가 띄웠냐" 고 물으셨다.

    환경변수 `CLAUDE_CODE_SESSION_ID` 로 기록 파일을 찾고, 거기서 마지막
    `/rename` 을 읽는다. `tools/update-sessions.py` 와 같은 방식이고,
    같은 이유로 `type` 이 `system` 인 줄만 인정한다 — 남의 기록을 읽는 세션은
    그 이름이 자기 대화에 남아서, 글자만 보면 남의 이름을 자기 것으로 단다.
    """
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not sid:
        return ""
    path = os.path.join(os.path.expanduser("~"), ".claude", "projects",
                        "C--work-KJCStudio", sid + ".jsonl")
    pat = re.compile(r"Session renamed to: ([가-힣A-Za-z0-9_\-. ]{1,30})")
    name = ""
    try:
        with io.open(path, encoding="utf-8", errors="ignore") as fp:
            for line in fp:
                if "Session renamed to:" not in line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("type") != "system":
                    continue
                m = pat.search(str(row.get("content", "")))
                if m:
                    name = m.group(1).strip()
    except OSError:
        pass
    return name


def doc_title(path):
    """HTML 의 `<title>` 을 읽는다. **창 제목이 파일명이 아니라 이것이다.**"""
    if not path.lower().endswith((".html", ".htm")):
        return ""
    try:
        s = io.open(path, encoding="utf-8").read()
    except OSError:
        return ""
    m = re.search(r"<title>(.*?)</title>", s, re.S | re.I)
    return m.group(1).strip() if m else ""


def url_title(url):
    """로컬 서버 주소에서 `<title>` 을 받아 온다.

    **주소의 파일명으로는 창을 못 찾는다** — 창에 뜨는 것은 `<title>` 이다.
    서버가 안 떠 있으면 빈 문자열을 돌려주고, 부르는 쪽이 멈춘다.

    **세션 이름은 못 붙인다.** `stamp_title` 은 파일을 고치는데 이것은
    서버가 내보내는 것이고 우리 것이 아닐 수도 있다. 그래서 주소로 띄운
    창은 **누가 띄웠는지 제목에 안 남는다.**
    """
    import re
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            head = r.read(8192).decode("utf-8", "replace")
    except Exception:
        return ""
    m = re.search(r"<title[^>]*>(.*?)</title>", head, re.S | re.I)
    return m.group(1).strip() if m else ""


def stamp_title(path, who):
    """HTML 제목 앞에 세션 이름을 붙인다. **임시 파일에만** 손댄다.

    브라우저 탭에 뜨는 것은 파일명이 아니라 `<title>` 이라, 파일명 규칙
    (`temp/README.md`)만으로는 화면에서 누가 띄웠는지 알 수 없다.

    저장소 파일은 고치지 않는다. 화면에 나가는 제목이고 내 것이 아니다.
    """
    if not who or not path.lower().endswith((".html", ".htm")):
        return
    try:
        s = io.open(path, encoding="utf-8").read()
    except OSError:
        return
    m = re.search(r"<title>(.*?)</title>", s, re.S | re.I)
    if not m:
        return
    cur = m.group(1).strip()
    if who in cur:
        return                       # 이미 붙어 있다

    # 임시 폴더인가. 저장소 안 파일은 건드리지 않는다.
    low = path.replace("\\", "/").lower()
    if "/temp/" not in low and "scratchpad" not in low:
        print(f"  제목에 세션 이름이 없습니다 — 저장소 파일이라 고치지 않습니다")
        return

    try:
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            s.replace(m.group(0), f"<title>{who} · {cur}</title>", 1))
        print(f"  제목에 붙임: {who}")
    except OSError:
        pass


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


def proc_name(hwnd):
    """그 창을 만든 프로그램의 파일명. 못 알아내면 '?' 를 준다.

    제목만으로는 누가 만든 창인지 알 수 없어서 필요하다.
    `kis-worker.js - KJCStudio - Visual Studio Code` 는 제목에 파일명이 들어
    있지만 우리가 연 창이 아니다.
    """
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return "?"
    buf = ctypes.create_unicode_buffer(4096)
    size = wintypes.DWORD(4096)
    ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
    k32.CloseHandle(h)
    return buf.value.rsplit("\\", 1)[-1] if ok else "?"


def already_open(hint, exe):
    """**이미 띄워 둔 창**이 있나. 있으면 (hwnd, 제목), 없으면 None.

    이것이 없어서 창이 쌓였다. 부를 때마다 새로 열고, 재권님 화면에
    같은 창이 넷·열여섯 개씩 남았다 (2026-09-16 · 2026-09-18).

    **「닫지 않는다」 와 「매번 새로 연다」 는 다른 이야기인데 한 줄에
    묶여 있었다.** 닫지 않는 것은 재권님 창을 지키려는 것이고,
    새로 여는 것은 그 결과가 아니다.

    여럿이면 None 을 준다 — 이미 쌓여 있다는 뜻이라, 거기에 하나 더
    얹지 않고 부르는 쪽이 판단하게 한다.
    """
    hits = [(h, t) for h, t in windows()
            if hint and hint in t and (not exe or proc_name(h).lower() == exe.lower())]
    return hits[0] if len(hits) == 1 else (None if not hits else hits)


def raise_only(title_part, before, filename="", exe=""):
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
    # 그때만 한 번 더 찾는데, **내가 연 그 프로그램의 창 안에서만** 찾는다.
    #
    # 파일명만으로 찾으면 샌다. 같은 날 실측한 것이다.
    #
    #     'kis-worker.js' 로 찾음 → 1개 일치
    #     → kis-worker.js - KJCStudio - Visual Studio Code
    #
    # **제목은 그 파일을 연 다른 프로그램도 갖고 있다.** 편집기에 열어 둔
    # 파일을 띄우면 재권님이 쓰시던 편집기가 앞으로 튀어나온다.
    # 1개라서 조건도 통과한다.
    #
    # 오늘 이 자리를 두 번 좁혔다 — 임의의 힌트 → 파일명 → 프로그램 + 파일명.
    # 앞의 둘은 **무엇으로 열었는지를 안 보고** 제목만 봤다는 점이 같다.
    #
    # 프로세스 **이름**으로 거른다. Popen 이 준 PID 로는 안 된다 —
    # 메모장이 탭 방식이라 그 프로세스는 기존 메모장에 넘기고 곧 끝나서,
    # 우리가 쥔 PID 는 죽어 있고 그 PID 의 창도 없다.
    if not hits and filename and exe:
        hits = [(h, t) for h, t in windows()
                if filename in t and proc_name(h).lower() == exe.lower()]

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
    arg = sys.argv[1]
    is_url = arg.lower().startswith(("http://", "https://"))

    # **로컬 서버 주소도 받는다 (2026-09-21).** 전에는 파일만 받아서
    # `http://localhost:8768/...` 이 경로로 해석돼 「없는 파일입니다」 가 났다.
    # 화면 확인은 거의 다 로컬 서버인데(`daily.html` 은 JS 가 API 를 부르니
    # `file://` 로 열면 안 된다), 「여는 것도 도구로 한다」 가 룰이라
    # **룰대로 하면 열 수단이 없는 상태**였다. 주식페이지_개발1 이 찾았다.
    if is_url:
        path = arg
    else:
        path = os.path.abspath(arg)
        if not os.path.exists(path):
            print(f"  없는 파일입니다: {path}")
            return

        # 누가 띄웠는지 제목에 남긴다. 창이 여럿일 때 구분이 안 되기 때문이다.
        stamp_title(path, session_name())

    # 제목 조각. 안 주면 파일명에서 뽑는데, **HTML 은 그러면 못 찾는다** —
    # 창에 뜨는 것은 파일명이 아니라 `<title>` 이다. 2026-09-18 에 `md-diff.html`
    # 을 힌트 없이 띄웠더니 「0개 일치」 가 나왔고, 못 찾을 때마다 다시 부르느라
    # **빈 창이 둘 쌓였다.** 띄우기는 성공하고 꺼내기만 실패해서, 화면에는
    # 창이 늘어나는데 출력은 「아무것도 안 했다」 고 말한다.
    #
    # 길면 앞부분만 쓴다. 창 제목은 뒤에 ` - Chrome` 이 붙고, 세션 이름이
    # 앞에 붙어 있어 앞 40자만으로도 특정된다.
    if len(sys.argv) > 2:
        hint = sys.argv[2]
    elif is_url:
        # **주소는 서버에서 `<title>` 을 받아 온다.** 주소의 파일명으로는
        # 창을 못 찾는다 — 창에 뜨는 것은 `<title>` 이다.
        hint = url_title(path)[:40]
        if not hint:
            print(f"  제목을 못 읽었습니다: {path}")
            print("  서버가 떠 있는지 보시고, 창제목의 일부를 두 번째 인자로 주십시오")
            return
    else:
        hint = doc_title(path)[:40] or os.path.splitext(os.path.basename(path))[0]

    # 무엇으로 열 것인가. 아래 raise_only 가 후보를 그 프로그램의 창으로
    # 좁히는 데 쓰고, 열기 전에 already_open 이 같은 기준으로 찾는 데도 쓴다.
    # os.startfile 로 여는 것은 무엇이 뜰지 모르므로 빈 채로 둔다.
    if is_url or path.lower().endswith((".html", ".htm")):
        opened_with = "chrome.exe" if any(os.path.exists(c) for c in CHROME) else ""
    elif path.lower().endswith(TEXT_EXT):
        opened_with = "notepad.exe"
    else:
        opened_with = ""

    # **주소로 열 때는 이미 뜬 창을 찾지 않는다 (2026-09-21).**
    # 창 제목에 포트가 안 나와서, 8765 창과 8768 창을 **가릴 수가 없다** —
    # 실측으로 `<title>` 이 똑같았다. 세션마다 자기 포트가 있으므로
    # **남의 포트 창을 꺼내면 「고친 그 화면을 띄운다」 가 깨진다.**
    # 실제로 한 세션이 안 고친 화면을 보여드릴 뻔했다.
    #
    # 「찾지 못하는 것은 괜찮고 **엉뚱한 창을 집는 것이 사고다**」 를 따른다.
    # 창이 쌓이는 것은 X 를 눌러 닫으면 되고, 잘못 본 화면은 되돌릴 수 없다.
    found = (None, None) if is_url else already_open(hint, opened_with)
    if isinstance(found, tuple) and found[0] is not None:
        hwnd, title = found
        u32.ShowWindow(hwnd, SW_RESTORE)
        u32.BringWindowToTop(hwnd)
        u32.SetForegroundWindow(hwnd)
        print(f"  이미 떠 있어 앞으로만 꺼냈습니다: {title}")
        print("  **파일이 바뀌었으면 그 창에서 Ctrl+Shift+R 을 눌러 주십시오.**")
        print("  (브라우저를 새로고침시킬 방법이 없습니다. 새 창을 또 열지 않습니다)")
        if is_url:
            # **포트는 창 제목에 안 나온다.** 2026-09-21 실측 —
            # 8765 와 8768 의 `daily.html` 이 `<title>` 이 똑같았다.
            # 세션마다 자기 포트가 있으므로, 남의 포트 창을 꺼낼 수 있다.
            print("  ⚠ **포트까지는 가리지 못했습니다.** 창 제목에 포트가 안 나옵니다 —")
            print(f"     보시려던 것이 {path} 가 맞는지 확인해 주십시오.")
            print("     다른 포트 창이면 그 창을 닫고 다시 부르십시오.")
        return
    if isinstance(found, list):
        print(f"  같은 창이 이미 {len(found)}개 떠 있습니다. 더 열지 않습니다")
        for _, t in found[:5]:
            print(f"      {t}")
        print("  (하나만 남기고 X 로 닫으신 뒤 다시 불러 주십시오)")
        return

    before = windows()

    if is_url or path.lower().endswith((".html", ".htm")):
        exe = next((c for c in CHROME if os.path.exists(c)), None)
        url = path if is_url else "file:///" + path.replace("\\", "/")
        if exe:
            subprocess.Popen([exe, "--new-window", url])
        else:
            os.startfile(path)
            opened_with = ""
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
    raise_only(hint, before, os.path.basename(path), opened_with)


if __name__ == "__main__":
    main()
