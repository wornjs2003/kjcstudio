#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""theme.css 와 theme.js 의 색이 어긋났는지 본다.

왜 필요한가
-----------
차트는 canvas 라 CSS 를 상속받지 못한다. 그래서 `holdings/js/theme.js` 가
`assets/css/theme.css` 를 읽어서 색 문자열을 넘겨준다.

그런데 CSS 가 아직 안 붙었을 때를 대비해 `FALLBACK` 에 같은 값을 복제해 두었다.
주석에 "theme.css 값을 바꾸면 아래 FALLBACK 도 같이 맞춰 주세요" 라고만 적혀 있어서,
**사람이 기억해야 맞는 구조**다. 잊으면 조용히 어긋난다. 화면은 멀쩡해 보이고
차트 색만 옛날 값으로 남는다.

루트 CLAUDE.md 의 「구역 구조 규칙」이 "복제를 발견하면 루트로 합친다" 고 하는데,
이건 합칠 수 없는 복제다(캔버스가 CSS 를 못 읽는다). 대신 어긋나면 잡는다.

쓰는 법
-------
    python tools/check-theme-sync.py

    맞으면  종료코드 0
    틀리면  종료코드 1 + 어긋난 항목 출력

표기 차이는 걸러낸다
--------------------
theme.css 는 `rgb(var(--kh-ink-rgb) / 6%)` 처럼 쓰고 theme.js 는
`rgba(16,16,19,0.06)` 로 쓴다. 같은 색이므로 실제 숫자로 풀어서 비교한다.
2026-09-15 에 이 두 가지가 "어긋남" 으로 잡혀 헛걸음할 뻔했다.
"""

import io
import os
import re
import sys

# 윈도우 콘솔은 기본이 cp949 라 '—' 같은 글자에서 죽는다.
# 출력만 UTF-8 로 바꾼다 (2026-09-15 확인).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# holdings/tools/ 로 옮겨서 한 단계가 깊어졌다 (2026-09-17).
# 이 도구들이 보는 경로는 **저장소 루트 기준**이라 루트를 정확히 잡아야 한다.
HERE = os.path.dirname(os.path.abspath(__file__))        # holdings/tools
ROOT = os.path.dirname(os.path.dirname(HERE))            # 저장소 루트
CSS = os.path.join(ROOT, "assets", "css", "theme.css")
JS = os.path.join(ROOT, "holdings", "js", "theme.js")


def read(path):
    return io.open(path, encoding="utf-8").read()


def css_vars(text, prefix):
    """--<prefix>-<이름>: <값>; 를 모은다."""
    pat = r"--%s-([a-z0-9-]+)\s*:\s*([^;]+);" % prefix
    return {k: v.strip() for k, v in re.findall(pat, text)}


def js_map(text, name):
    """const <name> = { 'a': 'b', ... }; 를 모은다."""
    m = re.search(r"const %s = \{(.*?)\};" % name, text, re.S)
    if not m:
        return {}
    return dict(re.findall(r"'([a-z0-9-]+)'\s*:\s*'([^']+)'", m.group(1)))


def normalize(value, rgb_table):
    """색을 비교 가능한 형태로 편다.

    #rrggbb            → (r, g, b)
    rgba(r,g,b,a)      → (r, g, b, a)
    rgb(r g b / p%)    → (r, g, b, a)
    rgb(var(--kh-x-rgb) / p%) → rgb_table 에서 x 를 찾아 푼다
    """
    v = value.strip().lower()

    # var(--kh-<이름>-rgb) 를 실제 숫자로 바꾼다
    def sub_var(m):
        return rgb_table.get(m.group(1), m.group(0))

    v = re.sub(r"var\(\s*--kh-([a-z0-9-]+?)-rgb\s*\)", sub_var, v)

    m = re.fullmatch(r"#([0-9a-f]{6})", v)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)

    m = re.fullmatch(r"#([0-9a-f]{3})", v)
    if m:
        h = m.group(1)
        return tuple([int(c * 2, 16) for c in h] + [1.0])

    # rgb(16 16 19 / 6%) · rgba(16,16,19,0.06) · rgb(16,16,19)
    m = re.fullmatch(r"rgba?\(([^)]+)\)", v)
    if m:
        body = m.group(1)
        alpha = 1.0
        if "/" in body:
            body, a = body.split("/", 1)
            a = a.strip()
            alpha = float(a[:-1]) / 100 if a.endswith("%") else float(a)
        parts = [p for p in re.split(r"[,\s]+", body.strip()) if p]
        if len(parts) == 4:            # rgba(r,g,b,a)
            alpha = float(parts[3])
            parts = parts[:3]
        if len(parts) == 3:
            return tuple(int(float(p)) for p in parts) + (round(alpha, 4),)

    return v   # 풀지 못하면 문자열 그대로 비교


def main():
    for p in (CSS, JS):
        if not os.path.exists(p):
            print("파일을 찾지 못했습니다: %s" % p)
            return 2

    css, js = read(CSS), read(JS)
    cssv = css_vars(css, "kh")
    rgb_table = {k[:-4]: v for k, v in cssv.items() if k.endswith("-rgb")}

    problems = []

    # 1) 색 대체값
    for name, jsval in js_map(js, "FALLBACK").items():
        cssval = cssv.get(name)
        if cssval is None:
            problems.append((name, jsval, "theme.css 에 --kh-%s 가 없음" % name))
        elif normalize(jsval, rgb_table) != normalize(cssval, rgb_table):
            problems.append((name, jsval, cssval))

    # 2) 삼원색 대체값 (--kh-<이름>-rgb)
    for name, jsval in js_map(js, "FALLBACK_RGB").items():
        cssval = cssv.get(name + "-rgb")
        if cssval is None:
            problems.append((name + "-rgb", jsval,
                             "theme.css 에 --kh-%s-rgb 가 없음" % name))
        elif jsval.split() != cssval.split():
            problems.append((name + "-rgb", jsval, cssval))

    total = len(js_map(js, "FALLBACK")) + len(js_map(js, "FALLBACK_RGB"))

    if not problems:
        print("일치 — 대체값 %d개 전부 theme.css 와 같습니다." % total)
        return 0

    print("어긋난 값 %d개 (전체 %d개)" % (len(problems), total))
    print()
    print("  %-18s %-26s %s" % ("이름", "theme.js", "theme.css"))
    print("  " + "-" * 70)
    for name, jsval, cssval in problems:
        print("  %-18s %-26s %s" % (name, jsval, cssval))
    print()
    print("holdings/js/theme.js 의 FALLBACK 을 theme.css 값으로 맞추세요.")
    print("차트만 옛 색으로 남고 화면은 멀쩡해 보이므로 눈으로는 찾기 어렵습니다.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
