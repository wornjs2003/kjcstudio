# -*- coding: utf-8 -*-
"""저장소 룰 중 **기계가 볼 수 있는 것**을 한 번에 센다.

`CLAUDE.md` 의 「아직 검사가 없는 룰」 표에 적혀 있던 것들이다. 검사 방법은
적혀 있었는데 **돌리는 사람이 없어서 안 돌았다.** 2026-09-22 에 재권님이
「룰 안지키는거 감시안함?」 하고 물으셔서 만들었다.

**이 도구가 지키는 세 가지**

  ① **대상 값을 박지 않는다.** 폴더와 **세는 방법**만 적는다. 파일이
     늘어도 저절로 들어온다 (2026-09-16 에 `daily.css` 가 목록에 없어
     그냥 지나간 일이 있다).

  ② **셀 것이 없어서 나온 `0` 과 진짜 `0` 을 가른다.** 앞의 것은
     「없다」 가 아니라 **「안 봤다」** 다. 대상 개수를 함께 낸다.

  ③ **「걸렸다」 와 「위반이다」 를 가른다.** 2026-09-22 에 「자세히 ›」
     둘이 걸렸는데 **둘 다 이미 모달을 열고 있었다** — `grep` 이 JS
     가로채기를 못 봤다. 그런 검사는 `LOOK` 으로 내고 **종료코드를
     올리지 않는다.**

종료코드   0 걸린 것 없음 · 1 위반 있음 · 2 **못 쟀다**
"""
import io
import json
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = ("/.git/", "/node_modules/", "/vendor/", "/.claude/worktrees/",
        "/uidata/", "/logs/", "/history/")

BAD, LOOK = "BAD", "LOOK"

# ── 검사의 **근거**를 함께 낸다 (2026-09-22) ──────────────────
#
# `홈페이지_정리` 가 자기 도구에서 찾은 자리다. 그 도구가 「누르는 자리
# 44px 미만 13개」 를 냈는데, **44px 은 WCAG 2.5.5 의 AAA 기준**이고
# 표준이 보통 요구하는 **AA 는 24px(2.5.8)** 이었다. AA 로 다시 세니
# **0개**였다. **「표준을 어겼다」 가 아니라 「최고 등급에 못 미친다」** 였다.
#
# **읽는 쪽은 「켜졌다」 를 「어겼다」 로 읽는다.** 그래서 각 검사가
# **누가 정한 기준인지**를 함께 낸다. 셋은 무게가 다르다.
#
#     지시   재권님이 정하셨다        — 어기면 지시를 어긴 것이다
#     표준   밖에서 정해진 값이다     — **등급까지 적는다**
#     실측   이 저장소에서 깨져 봤다  — 그때 그 일이 또 난다
지시, 표준, 실측 = "지시", "표준", "실측"


def rd(path):
    try:
        return io.open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def walk(*exts):
    """저장소 안의 파일을 훑는다. 경로는 루트 기준으로 낸다."""
    for base, dirs, files in os.walk(ROOT):
        rel = "/" + os.path.relpath(base, ROOT).replace("\\", "/") + "/"
        if any(s in rel for s in SKIP):
            dirs[:] = []
            continue
        for f in files:
            if f.endswith(exts):
                yield os.path.relpath(os.path.join(base, f), ROOT).replace("\\", "/")


def strip_py_comments(src):
    """파이썬 줄 주석을 지운다. 주석 안의 예시를 위반으로 세지 않기 위해서다.

    문자열 안의 `#` 까지 가리지는 못하므로 **완벽하지 않다** — 그래서
    이 함수를 쓰는 검사는 걸린 줄을 함께 낸다."""
    out = []
    for line in src.split("\n"):
        out.append("" if line.lstrip().startswith("#") else line)
    return "\n".join(out)


# ─────────────────────────────────────────────────────────────
# 검사들. 각각 (이름, 대상 개수, 걸린 것 목록, 판정) 을 돌려준다.
# ─────────────────────────────────────────────────────────────

def c_bat_nonascii():
    """`cmd` 는 줄마다 파일을 되짚어서, `chcp` 뒤에 한글이 있으면 밀린다."""
    hits, n = [], 0
    for p in walk(".bat"):
        n += 1
        try:
            b = io.open(os.path.join(ROOT, p), "rb").read()
        except Exception:
            continue
        bad = len([x for x in b if x > 127])
        if bad:
            hits.append("%s — 비ASCII %d자" % (p, bad))
    return ".bat 안에 한글", n, hits, BAD, (실측, "chcp 뒤에 한글이 있으면 cmd 가 줄을 밀어 읽는다 (2026-09-16)")


def c_py_encoding():
    """한글을 찍고 `__main__` 이 있는 도구에 인코딩 두 줄이 있나."""
    hits, n = [], 0
    for p in walk(".py"):
        s = rd(os.path.join(ROOT, p))
        if "__main__" not in s or not re.search(r"[가-힣]", s):
            continue
        n += 1
        if "reconfigure" in s or "TextIOWrapper(sys.stdout" in s:
            continue
        hits.append(p)
    return "한글 출력 도구에 인코딩 두 줄", n, hits, BAD, (실측, "윈도우 콘솔이 cp949 라 `—` 같은 글자에서 죽는다. **독립 실행되는 것만** 본다 — 프로세스의 주인이 켜면 import 된 것도 따라온다")


def c_send_error_korean():
    """HTTP 상태 줄은 latin-1 이라 한글을 넣으면 **빈 응답**이 나간다."""
    hits, n = [], 0
    pat = re.compile(r'send_error\(\s*\d+\s*,\s*["\']([^"\']*)["\']')
    for p in walk(".py"):
        src = rd(os.path.join(ROOT, p))
        if "send_error(" not in src:
            continue
        n += 1
        for m in pat.finditer(strip_py_comments(src)):
            if re.search(r"[가-힣]", m.group(1)):
                hits.append("%s — %s" % (p, m.group(1)[:24]))
    return "send_error 에 한글 (빈 응답이 나간다)", n, hits, BAD, (표준, "HTTP 상태 줄은 latin-1 이다 (RFC 9110). 한글을 넣으면 빈 응답이 나간다")


def c_scrollbar():
    """모양은 `common.css` 한 곳에서만 정한다. 감추는 것은 덮어쓰기가 아니다."""
    hits, n = [], 0
    block = re.compile(r"::-webkit-scrollbar[^{]*\{([^}]*)\}")
    for p in walk(".css"):
        if p.endswith("common.css"):
            continue
        s = rd(os.path.join(ROOT, p))
        if "::-webkit-scrollbar" not in s:
            continue
        n += 1
        for m in block.finditer(s):
            body = m.group(1)
            hides = re.search(r"display\s*:\s*none|height\s*:\s*0|width\s*:\s*0", body)
            sets = re.search(r"\b(width|background)\s*:", body)
            if sets and not hides:
                hits.append(p)
                break
    return "스크롤바를 common.css 밖에서 덮어씀", n, hits, BAD, (지시, "「UI 에 사용되는 스크롤바는 하나로만 적용되도록」 (2026-09-18)")


def c_common_css_link():
    """구역 첫 화면이 공용 CSS 를 싣나. 새 구역이 빠뜨리는 것을 잡는다."""
    hits, n = [], 0
    for name in sorted(os.listdir(ROOT)):
        d = os.path.join(ROOT, name)
        idx = os.path.join(d, "index.html")
        if not os.path.isdir(d) or name.startswith(".") or not os.path.exists(idx):
            continue
        if "assets/css/theme.css" not in rd(idx):
            continue                      # 구역이 아니다 (공용 테마를 안 쓴다)
        n += 1
        if "common.css" not in rd(idx):
            hits.append(name + "/index.html")
    return "구역 첫 화면이 common.css 를 안 실음", n, hits, BAD, (지시, "스크롤바 한 벌을 그 파일이 들고 있다 (2026-09-18). 안 실으면 브라우저 기본이 나온다")


def c_bat_timeout():
    """`timeout /t` 는 입력이 리다이렉트되면 즉시 죽는다."""
    hits, n = [], 0
    for p in walk(".bat"):
        n += 1
        for i, line in enumerate(rd(os.path.join(ROOT, p)).split("\n"), 1):
            if re.search(r"\btimeout\s+/t\b", line, re.I):
                hits.append("%s:%d" % (p, i))
    return ".bat 에서 timeout /t 를 씀", n, hits, BAD, (실측, "입력이 리다이렉트되면 `Input redirection is not supported` 로 즉시 죽는다")


def c_modal_links():
    """「자세히」·「더보기」가 화면을 벗어나나.

    **걸린 것이 곧 위반은 아니다.** 막는 길이 둘인데 이 검사는 한쪽만
    본다 — `data-modal` 은 보고 **JS 가로채기는 못 본다.** 그래서
    걸린 것을 `LOOK`(봐야 할 자리)으로 낸다. 2026-09-22 에 이것으로
    멀쩡한 코드 둘을 위반으로 넘겨 두 세션이 시간을 썼다.
    """
    hits, n = [], 0
    tag = re.compile(r"<a\s[^>]*href[^>]*>")
    for p in walk(".html"):
        if not p.startswith("holdings/"):
            continue
        s = rd(os.path.join(ROOT, p))
        n += 1
        for m in tag.finditer(s):
            seg = s[m.start():m.start() + 160]
            if re.search(r"더보기|자세히", seg) and "data-modal" not in m.group(0):
                hits.append("%s:%d" % (p, s[:m.start()].count("\n") + 1))
    return "모달로 안 옮긴 「자세히」·「더보기」", n, hits, LOOK, (지시, "「자세히 버튼은 차트에서 모달 띄우는 버튼으로 다 통일해줘」. **JS 가 가로채는 길을 이 검사가 못 본다**")


def c_hook_exec():
    """훅은 실행 비트가 없으면 git 이 **조용히 건너뛴다** — 오류도 안 낸다.

    2026-10-01 에 새로 만든 `post-merge` 가 100644 로 올라갔다. `core.fileMode=false` 라
    chmod 가 저장소에 안 실렸고, 창구가 main 에 합쳐도 카드가 안 움직였다. 「실패가 통과로
    보인다」 꼴 — 저장소에 **기록된** 모드(`git ls-files -s`)를 센다. 작업 트리 비트가 아니다.
    """
    hits, n = [], 0
    try:
        out = subprocess.run(["git", "ls-files", "-s", ".githooks/"], capture_output=True,
                             text=True, cwd=ROOT).stdout
    except Exception:
        return "훅에 실행 비트가 없다", 0, [], BAD, (실측, "git ls-files 를 못 돌렸다")
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        mode, path = parts[0], parts[3]
        if os.path.basename(path).startswith(".") or path.endswith((".md", ".txt")):
            continue
        n += 1
        if mode != "100755":
            hits.append("%s — %s (git update-index --chmod=+x %s)" % (path, mode, path))
    return "훅에 실행 비트가 없다 (git 이 조용히 건너뛴다)", n, hits, BAD, (실측, "2026-10-01 post-merge 가 100644 로 올라가 main 머지 때 카드가 안 움직였다")


def c_nav_gutter():
    """메뉴 줄의 기준선은 하나다 — 홀딩스 격자 (2026-10-01 지시 「홀딩스가 기준이야」).

    둘을 본다. ① `nav.css` 에서 `data-nav=` 선택자가 `.site-nav` 의 padding 을 바꾸는 곳 — 0 이어야
    한다(주석은 뺀다). ② 바탕값 둘(`theme.css` 의 `--grid-max` · `--grid-inset`)이 `frame.css` 의 `.kh-app`
    max-width · `.kh-main` 좌우 padding 과 같은가. frame.css 가 그 변수를 쓰면 복제가 없는 것이라 통과다 —
    「합칠 수 있으면 대조 도구보다 먼저 합친다」. 값을 박지 않고 서로를 읽는다.
    """
    nav = rd(os.path.join(ROOT, "assets/css/nav.css"))
    theme = rd(os.path.join(ROOT, "assets/css/theme.css"))
    frame = rd(os.path.join(ROOT, "holdings/css/frame.css"))
    if not nav or not frame or not theme:
        return "메뉴 기준선이 구역별로 갈림", 0, [], BAD, (지시, "nav.css · theme.css · frame.css 를 못 읽었다")
    strip = lambda x: re.sub(r"/\*.*?\*/", "", x, flags=re.S)
    nav_code, theme_code, frame_code = strip(nav), strip(theme), strip(frame)
    hits, n = [], 2
    for m in re.finditer(r"([^{}]*data-nav=[^{}]*\.site-nav[^{}]*)\{([^}]*)\}", nav_code):
        if re.search(r"\bpadding(-left|-right)?\s*:", m.group(2)):
            hits.append("nav.css — 구역별 예외: " + " ".join(m.group(1).split()))
    if not re.search(r"--nav-gutter\s*:\s*max\(\s*var\(--grid-inset\)", nav_code):
        hits.append("nav.css 의 --nav-gutter 가 theme.css 의 --grid-inset · --grid-max 로 계산되지 않는다")
    gmax = re.search(r"--grid-max\s*:\s*(\d+)px", theme_code)
    gins = re.search(r"--grid-inset\s*:\s*(\d+)px", theme_code)
    app = re.search(r"\.kh-app\s*\{[^}]*max-width\s*:\s*([^;]+);", frame_code)
    main = re.search(r"\.kh-main\s*\{[^}]*padding\s*:\s*\S+\s+([^;\s]+)", frame_code)
    if not gmax or not gins:
        hits.append("theme.css 에 --grid-max · --grid-inset 이 없다")
    elif not app or not main:
        hits.append("frame.css 에서 .kh-app max-width · .kh-main 좌우 padding 을 못 찾았다")
    else:
        a, m_ = app.group(1).strip(), main.group(1).strip()
        if a != "var(--grid-max)" and a != gmax.group(1) + "px":
            hits.append("격자 폭이 갈렸다 — theme.css --grid-max %spx ↔ frame.css .kh-app %s" % (gmax.group(1), a))
        if m_ != "var(--grid-inset)" and m_ != gins.group(1) + "px":
            hits.append("안쪽 여백이 갈렸다 — theme.css --grid-inset %spx ↔ frame.css .kh-main %s" % (gins.group(1), m_))
    return "메뉴 기준선이 구역별로 갈림 · 홀딩스 격자와 어긋남", n, hits, BAD, (지시, "「홀딩스가 기준이야」 (2026-10-01) — 구역을 오갈 때 메뉴가 44px 움직였다")

def c_shared_css():
    """구역 밖에서 거는 파일은 「거는 쪽이 둘 이상인 파일」 이다 (2026-10-01 지시 「같이쓴다」).

    다른 구역 화면이 `../<구역>/css/…` 로 거는 파일을 **「봐야 할 자리」** 로 낸다 — 거는 것 자체는
    위반이 아니고, 그 파일을 고치는 쪽이 거는 화면 전부를 보고 다른 쪽에 먼저 알려야 한다는 표시다.
    파일 이름도 구역 이름도 박지 않는다. `assets/css/` 는 룰이 정한 공용 자리라 뺀다.
    """
    link = re.compile(r'href="\.\./([a-z][a-z-]*/css/[^"]+)"')
    by, n = {}, 0
    for p in walk(".html"):
        if p.startswith("temp/"):
            continue
        n += 1
        for m in link.finditer(rd(os.path.join(ROOT, p))):
            target = m.group(1)
            if target.startswith("assets/css/"):
                continue
            by.setdefault(target, []).append(p)
    hits = ["%s  ← %s" % (t, ", ".join(sorted(set(v)))) for t, v in sorted(by.items())]
    return "거는 쪽이 둘 이상인 구역 CSS", n, hits, LOOK, (지시, "「같이쓴다」 (2026-10-01) — 고치면 거는 화면 전부를 보고 다른 쪽 세션에 먼저 알린다")

def c_main_guard():
    """메인 자리는 재권님 허락 없이 건드리지 않는다 (2026-10-01 지시) — 장치가 조용히 꺼지는 것을 잡는다.

    훅 등록(settings.json) · 훅 파일 · 스킬 · deny 셋이 **다 있어야** 한다. 하나라도 빠지면 위반.
    2026-10-01 17:4x 에 한 세션이 메인 8765 의 market.db 를 쓰기 모드로 열어 journal_mode 가 바뀌었다.
    """
    hits, n = [], 4
    try:
        st = json.loads(rd(os.path.join(ROOT, ".claude/settings.json")) or "{}")
    except Exception:
        st = {}
    hooks = st.get("hooks", {}).get("PreToolUse", [])
    if not any("hook-main-guard" in h.get("command", "") for g in hooks for h in g.get("hooks", [])):
        hits.append(".claude/settings.json 에 hook-main-guard 훅 등록이 없다")
    if not os.path.exists(os.path.join(ROOT, "tools/hook-main-guard.py")):
        hits.append("tools/hook-main-guard.py 가 없다")
    if not os.path.exists(os.path.join(ROOT, ".claude/skills/main-guard/SKILL.md")):
        hits.append(".claude/skills/main-guard/SKILL.md 가 없다")
    deny = st.get("permissions", {}).get("deny", [])
    if not any("install.command 8765" in x for x in deny) or not any(x.endswith("kr.kjcstudio.kis-proxy)") for x in deny):
        hits.append(".claude/settings.json deny 에 메인 자리 항목(install.command 8765 · launchctl 메인)이 없다")
    return "메인 자리 안전장치가 빠짐", n, hits, BAD, (지시, "「메인쪽은 내 허락없이 절대 건들면 안되는곳이야 안정장치를 여러개 만들어줘」 (2026-10-01)")

def c_main_ok_log():
    """KJC_MAIN_OK=1 을 쓴 기록 — 허락은 기계가 못 보니 **몇 번 썼는지**를 「봐야 할 자리」 로 낸다 (작업우선순위 · 홈페이지_정리 검토)."""
    p = os.path.join(ROOT, "logs", "main-ok.log")
    if not os.path.exists(p):
        return "KJC_MAIN_OK=1 사용 기록", 1, [], LOOK, (지시, "아직 한 번도 안 썼다")
    lines = [l for l in rd(p).splitlines() if l.strip()]
    return "KJC_MAIN_OK=1 사용 기록 (허락받고 쓴 것인지 재권님이 보신다)", 1, [l[:150] for l in lines[-10:]], LOOK, (지시, "「메인쪽은 내 허락없이 절대 건들면 안되는곳」 — 쓴 자국을 남긴다")


CHECKS = [c_bat_nonascii, c_py_encoding, c_send_error_korean,
          c_scrollbar, c_common_css_link, c_bat_timeout, c_modal_links, c_hook_exec, c_nav_gutter, c_shared_css, c_main_guard, c_main_ok_log]


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    print("룰 검사 — CLAUDE.md 「아직 검사가 없는 룰」 을 한 번에 센다")
    print("=" * 66)

    bad_total, look_total, unmeasured = 0, 0, []

    for fn in CHECKS:
        try:
            name, n, hits, kind, (근거종류, 근거글) = fn()
        except Exception as e:
            print("  ??  %-42s **못 쟀습니다** (%s)" % (fn.__name__, e))
            unmeasured.append(fn.__name__)
            continue

        if n == 0:
            # 셀 것이 없었다. 「없다」 가 아니라 「안 봤다」 다.
            print("  ??  %-42s **대상 0개 — 못 쟀습니다**" % name)
            unmeasured.append(name)
            continue

        if not hits:
            print("  OK  %-42s 0   (대상 %d)  [%s]" % (name, n, 근거종류))
            continue

        mark = "!!" if kind == BAD else "-> "
        tail = "" if kind == BAD else "   <- 위반인지는 봐야 압니다"
        print("  %s  %-42s %-3d (대상 %d)  [%s]%s"
              % (mark, name, len(hits), n, 근거종류, tail))
        print("        근거: " + 근거글)
        for h in (hits if verbose else hits[:4]):
            print("        " + h)
        if not verbose and len(hits) > 4:
            print("        … 그 밖 %d개 (--verbose 로 전부)" % (len(hits) - 4))

        if kind == BAD:
            bad_total += len(hits)
        else:
            look_total += len(hits)

    print("=" * 66)
    print("  위반 %d · 봐야 할 자리 %d · 못 잰 검사 %d"
          % (bad_total, look_total, len(unmeasured)))

    if look_total:
        print()
        print("  「봐야 할 자리」 는 위반이 아닐 수 있습니다. 고치기 전에 재십시오 —")
        print("  「자세히」·「더보기」 는 JS 가 가로채는 길이 따로 있습니다.")
        print("      grep -rn preventDefault holdings/js/ --include=*.js | grep -v vendor")

    if unmeasured:
        print()
        print("  **못 잰 검사가 있습니다.** 「0」 이 아니라 「안 봤다」 입니다:")
        for u in unmeasured:
            print("      " + u)
        return 2

    return 1 if bad_total else 0


if __name__ == "__main__":
    sys.exit(main())
