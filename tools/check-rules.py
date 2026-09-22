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
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = ("/.git/", "/node_modules/", "/vendor/", "/.claude/worktrees/",
        "/uidata/", "/logs/", "/history/")

BAD, LOOK = "BAD", "LOOK"


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
    return ".bat 안에 한글", n, hits, BAD


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
    return "한글 출력 도구에 인코딩 두 줄", n, hits, BAD


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
    return "send_error 에 한글 (빈 응답이 나간다)", n, hits, BAD


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
    return "스크롤바를 common.css 밖에서 덮어씀", n, hits, BAD


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
    return "구역 첫 화면이 common.css 를 안 실음", n, hits, BAD


def c_bat_timeout():
    """`timeout /t` 는 입력이 리다이렉트되면 즉시 죽는다."""
    hits, n = [], 0
    for p in walk(".bat"):
        n += 1
        for i, line in enumerate(rd(os.path.join(ROOT, p)).split("\n"), 1):
            if re.search(r"\btimeout\s+/t\b", line, re.I):
                hits.append("%s:%d" % (p, i))
    return ".bat 에서 timeout /t 를 씀", n, hits, BAD


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
    return "모달로 안 옮긴 「자세히」·「더보기」", n, hits, LOOK


CHECKS = [c_bat_nonascii, c_py_encoding, c_send_error_korean,
          c_scrollbar, c_common_css_link, c_bat_timeout, c_modal_links]


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    print("룰 검사 — CLAUDE.md 「아직 검사가 없는 룰」 을 한 번에 센다")
    print("=" * 66)

    bad_total, look_total, unmeasured = 0, 0, []

    for fn in CHECKS:
        try:
            name, n, hits, kind = fn()
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
            print("  OK  %-42s 0   (대상 %d)" % (name, n))
            continue

        mark = "!!" if kind == BAD else "-> "
        tail = "" if kind == BAD else "   <- 위반인지는 봐야 압니다"
        print("  %s  %-42s %-3d (대상 %d)%s" % (mark, name, len(hits), n, tail))
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
