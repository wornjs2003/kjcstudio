#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KJC Studio · Debugging 검사기

  의도한 값(expected.json)과 지금 저장소 상태를 대조합니다.
  결과를 debugging/latest.json 과 debugging/history/ 에 남기고, 직전 회차와 비교해 무엇이
  새로 생기고 무엇이 해결됐는지 적습니다.

  혼자서도 돌아갑니다.
      python debugging/check.py
      python debugging/check.py --auto      자동 실행으로 기록

  ── 만들 때 지킨 것 ─────────────────────────────
  거짓 경보가 쌓이면 아무도 안 보게 됩니다. 그래서 이렇게 했습니다.

    1. 주석은 검사하지 않습니다.
       이 저장소는 주석에 "예전에는 이런 값이었다" 를 자주 적어둡니다.
       단순 문자열 검색이면 그게 전부 오탐이 됩니다.

    2. 해석이 들어가는 항목은 아직 넣지 않았습니다.
       참·거짓이 분명한 것만 먼저 넣고, 쓰면서 넓힙니다.

    3. 항목마다 검사 범위를 expected.json 에 적습니다.
       어느 파일의 어느 부분을 보는지 분명해야 오탐을 줄일 수 있습니다.
"""

import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

# 윈도우 콘솔은 기본이 cp949 라서 — 나 · 같은 글자에서 터집니다.
# 결과 파일은 이미 UTF-8 로 쓰므로 화면 출력만 맞춰 줍니다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

QA_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(QA_DIR)
HISTORY_DIR = os.path.join(QA_DIR, "history")
EXPECTED_PATH = os.path.join(QA_DIR, "expected.json")
LATEST_PATH = os.path.join(QA_DIR, "latest.json")


# ── 파일 읽기 ────────────────────────────────────────────

def read(rel):
    """저장소 안의 파일을 읽습니다. 없으면 None."""
    path = os.path.join(ROOT, rel)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def exists(rel):
    path = os.path.join(ROOT, rel.rstrip("/"))
    return os.path.exists(path)


# ── 주석 제거 ────────────────────────────────────────────
# 주석 안의 값은 "과거 경위" 인 경우가 많아 검사 대상이 아닙니다.

def strip_comments(text, kind):
    if not text:
        return ""
    if kind == "css":
        return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    if kind == "js":
        text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
        # 문자열 안의 // 를 지우지 않으려고 줄 앞쪽만 봅니다
        return re.sub(r"(?m)^\s*//.*$", " ", text)
    if kind == "html":
        # 우리 화면 파일은 HTML·CSS·JS 가 한 파일에 같이 있습니다.
        # <!-- --> 만 지우면 <style> 안의 /* */ 주석이 그대로 남아 오탐이 납니다.
        text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
        text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
        return re.sub(r"(?m)^\s*//.*$", " ", text)
    if kind == "py":
        return re.sub(r"(?m)^\s*#.*$", " ", text)
    if kind == "md":
        # 마크다운은 코드블록만 봅니다 (설명문에 옛 값이 자주 나옵니다)
        return text
    return text


# ══════════════════════════════════════════════════════════
#  검사 항목
#    각 함수는 (status, actual, detail) 을 돌려줍니다.
#      status : pass | mismatch | changed | todo
#      actual : 화면에 보여줄 "지금 값"
#      detail : 어디서 찾았는지
# ══════════════════════════════════════════════════════════

def check_nav_links(spec):
    """메뉴가 가리키는 곳이 실제로 있는가.

    참·거짓이 분명해서 오탐이 나지 않는 종류입니다.
    """
    src = strip_comments(read(spec["file"]), "html")
    if src is None or src == "":
        return "mismatch", "파일 없음", spec["file"] + " 를 읽지 못했습니다"

    targets = re.findall(r'href="\{\{BASE\}\}([^"]+)"', src)
    seen, missing = [], []
    for t in targets:
        t = t.split("#")[0].split("?")[0]
        if not t or t in seen:
            continue
        seen.append(t)
        if not exists(t):
            missing.append(t)

    if missing:
        return "mismatch", "깨진 링크 " + str(len(missing)) + "개", " · ".join(missing)
    return "pass", str(len(seen)) + "개 모두 정상", " · ".join(seen[:6])


def check_doc_token(spec):
    """문서에 적힌 색과 토큰에 정의된 색이 같은가.

    CLAUDE.md 는 설명문이라 주석 제거를 하지 않고, 적힌 줄에서 값만 뽑습니다.
    비교 대상은 theme.css 의 '토큰 정의' 한 줄로 한정합니다.
    """
    doc = read(spec["docFile"])
    css = strip_comments(read(spec["cssFile"]), "css")
    if doc is None or css is None:
        return "mismatch", "파일 없음", "문서 또는 CSS 를 읽지 못했습니다"

    m = re.search(spec["docPattern"], doc)
    if not m:
        return "todo", "문서에 없음", spec["docFile"] + " 에서 값을 찾지 못했습니다"
    doc_value = m.group(1).lower()

    m2 = re.search(r"--" + re.escape(spec["token"]) + r"\s*:\s*([^;]+);", css)
    if not m2:
        return "mismatch", "토큰 없음", "--" + spec["token"] + " 정의를 찾지 못했습니다"
    css_value = m2.group(1).strip().lower()

    if doc_value == css_value:
        return "pass", css_value, spec["cssFile"] + " · --" + spec["token"]
    return "mismatch", css_value, "문서는 " + doc_value + " · 코드는 " + css_value


def check_pair_sync(spec):
    """쌍으로 움직여야 하는 두 파일이 같은 엔드포인트를 들고 있는가.

    한쪽만 고치는 사고가 실제로 있었습니다.

    ── 주의 ─────────────────────────────────
    파일마다 경로를 적는 방식이 다를 수 있습니다. 같은 정규식을 양쪽에 쓰면
    "한쪽에만 있다" 는 오탐이 납니다. 실제로 첫 실행에서 그렇게 났습니다.
      kis_proxy.py    안내문에 /api/kis/health 라고 한 번 적혀 있을 뿐
      kis-worker.js   접두사를 떼어낸 뒤 route === "health" 로 비교
    그래서 패턴을 파일별로 따로 받습니다.
    """
    a = strip_comments(read(spec["fileA"]), spec.get("kindA", "py"))
    b = strip_comments(read(spec["fileB"]), spec.get("kindB", "js"))
    if a is None or b is None:
        return "todo", "파일 없음", "한쪽이 아직 없습니다"

    set_a = set(re.findall(spec["patternA"], a))
    set_b = set(re.findall(spec["patternB"], b))

    only_a = sorted(set_a - set_b)
    only_b = sorted(set_b - set_a)

    if not only_a and not only_b:
        return "pass", str(len(set_a)) + "개 일치", " · ".join(sorted(set_a)[:6])

    parts = []
    if only_a:
        parts.append(os.path.basename(spec["fileA"]) + " 에만: " + ", ".join(only_a))
    if only_b:
        parts.append(os.path.basename(spec["fileB"]) + " 에만: " + ", ".join(only_b))
    return "mismatch", "어긋남 " + str(len(only_a) + len(only_b)) + "개", " / ".join(parts)


def resolve_files(spec):
    """files 의 항목을 글로브로 펼칩니다. 새 파일이 생기면 저절로 들어옵니다.

    파일 이름을 하나씩 적어두면 **새로 만든 파일이 검사에서 조용히 빠집니다.**
    2026-09-16 에 holdings/css/daily.css 와 modal.css 가 그렇게 빠졌고,
    daily.css 에 박힌 색 두 곳을 이 검사가 아무것도 못 잡았습니다.
    그날 이 검사가 보던 것은 projects/index.html 과 api-board/index.html
    딱 둘뿐이었습니다.

    폴더로 적으면 그 일이 다시 나지 않습니다.

    ⚠️ **이것을 쓰는 검사에는 「대상 0개」 가드를 함께 넣습니다.**
    글로브가 하나도 안 맞으면 아무것도 안 보고 통과합니다 — 폴더 이름이
    바뀌거나 오타가 나면 검사가 초록으로 남은 채 눈을 감습니다.
    **0 은 「없다」 가 아니라 「못 찾았다」 일 수 있습니다.** 둘을 가르세요.
    check_raw_color 가 그 모양입니다 (2026-09-21).

    2026-09-21 기준으로 이것을 부르는 검사는 check_raw_color 하나뿐이고
    가드가 들어 있습니다. 나머지는 고정 경로만 써서 0 이 될 자리가 없습니다.
    **그중 하나가 나중에 글로브를 쓰게 되면 같은 일이 납니다.**
    """
    out = []
    for pat in spec["files"]:
        if any(ch in pat for ch in "*?["):
            hits = glob.glob(os.path.join(ROOT, pat))
            out.extend(sorted(os.path.relpath(h, ROOT).replace(os.sep, "/") for h in hits))
        else:
            out.append(pat)

    skip = set(spec.get("exclude", []))
    seen, files = set(), []
    for rel in out:
        if rel in skip or rel in seen:
            continue
        seen.add(rel)
        files.append(rel)
    return files


def token_for(color):
    """이 색을 이미 담고 있는 theme.css 토큰 이름을 찾아 줍니다.

    **걸렸을 때 고치는 법까지 같이 알려주려고** 있습니다. "색을 박지 마라" 만으로는
    무엇으로 바꿔야 하는지 알 수 없고, 이름을 짐작해 찾다가 못 찾으면 또 박게 됩니다.

    2026-09-16 에 실제로 그랬습니다 — 초록·주황이 필요해서 --kh-ok 와 --kh-warn 을
    찾았는데 -rgb 짜리만 나왔습니다. 진한 값은 --kh-tag-news · --kh-tag-notice 라는
    **다른 이름** 아래 있었습니다. 있는 줄 모르고 #02a262 · #f29300 을 직접 적었습니다.
    """
    # #fff 로 걸린 것도 이름을 찾아야 하므로 6자리로 펴서 맞춥니다.
    if len(color) == 4:
        color = "#" + "".join(ch * 2 for ch in color[1:])

    css = read("assets/css/theme.css")
    pairs = re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\b", css)
    return [name for name, value in pairs if value.lower() == color.lower()]


# 색을 적는 형태는 하나가 아닙니다. 6자리만 보면 #fff 가 통째로 안 보입니다.
# 2026-09-17 에 실제로 그랬습니다 — ai-work/ 를 검사에 넣어도 「0곳」 으로 통과했고,
# 세어 보니 #fff 가 셋 있었습니다. 구역을 안 봐서가 아니라 **형태를 안 봐서**였습니다.
RAW_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")

# rgb(var(--kh-ok-rgb) / 0.12) 는 토큰을 쓰는 것이라 위반이 아닙니다.
# **여는 괄호 뒤가 숫자일 때만** 박은 것입니다. 안 가리고 잡으면 오탐이 쏟아집니다 —
# 2026-09-17 실측으로 이 꼴 29개 중 박은 것은 2개였습니다.
RAW_FUNC = re.compile(r"\b(?:rgba?|hsla?)\(\s*[0-9.][^)]*\)")

# href="#add" 는 색이 아니라 앵커인데 3자리 hex 와 모양이 같습니다.
# 지금 저장소에는 없지만, 생기면 색으로 잘못 걸립니다.
ANCHOR_BEFORE = re.compile(r"(?:xlink:)?href\s*=\s*['\"]$")


def check_raw_color(spec):
    """토큰을 쓰지 않고 색을 직접 박은 곳이 있는가.

    주석을 지우고 봅니다. 토큰을 정의하는 파일 자체는 당연히 색이 있으므로 제외합니다.

    files 에 글로브를 쓸 수 있습니다 (resolve_files 참조).
    allow 에 적은 색은 세지 않습니다 — 국기 규정색처럼 **데이터로서의 색**입니다
    (CLAUDE.md 「하드코딩 금지의 예외」). 파일째 빼지 않고 색만 빼므로,
    그 파일에 다른 색이 새로 들어오면 그때는 걸립니다.
    """
    files = resolve_files(spec)

    # 글로브가 하나도 안 맞으면 **아무것도 안 보고 통과한다.** 폴더 이름이
    # 바뀌거나 오타가 나면 검사가 초록으로 남은 채 눈을 감는다.
    # 0 은 「없다」 가 아니라 「못 찾았다」 일 수 있다 — 둘을 가른다
    # (2026-09-21. 이 모양이 오늘만 다섯 번 났다).
    if not files:
        return "mismatch", "대상 0개",             "files 로 잡히는 파일이 없습니다 — 경로를 확인하세요: "             + " · ".join(spec.get("files") or [])

    # allow 는 목록으로도, 파일별로도 적을 수 있습니다.
    #   ["#cd2e3a", ...]                      그 검사 전체에 예외
    #   {"holdings/index.html": ["#fff"]}     그 파일에만 예외
    # 국기 SVG 처럼 **한 파일에만 있는 데이터 색**을 구역 전체에 열어주지 않으려고
    # 나눴습니다. #fff 를 css 까지 허용하면 가장 자주 박히는 색이 통째로 열립니다.
    raw_allow = spec.get("allow", [])
    if not isinstance(raw_allow, dict):
        raw_allow = {"*": raw_allow}

    found = []
    for rel in files:
        if not os.path.isfile(os.path.join(ROOT, rel)):
            continue
        allow = set(c.lower() for c in raw_allow.get(rel, raw_allow.get("*", [])))
        kind = "css" if rel.endswith(".css") else ("html" if rel.endswith(".html") else "js")
        body = strip_comments(read(rel), kind)
        for m in RAW_HEX.finditer(body):
            if ANCHOR_BEFORE.search(body[max(0, m.start() - 24):m.start()]):
                continue
            color = m.group(0).lower()
            if color in allow:
                continue
            found.append((rel, color))
        for m in RAW_FUNC.finditer(body):
            color = re.sub(r"\s+", "", m.group(0)).lower()
            if color in allow:
                continue
            found.append((rel, color))

    if not found:
        return "pass", "0곳", "검사한 파일 " + str(len(files)) + "개"

    colors = sorted(set(c for _, c in found))
    where = sorted(set(f for f, _ in found))

    # 바꿔 쓸 토큰이 이미 있으면 같이 알려줍니다. 외워 두지 않아도 됩니다.
    hints = []
    for c in colors[:4]:
        names = token_for(c)
        hints.append(c + (" → " + names[0] if names else " → 토큰 없음"))

    return "changed", str(len(found)) + "곳 · " + str(len(colors)) + "종", \
        " · ".join(hints) + (" 외" if len(colors) > 4 else "") + "  (" + ", ".join(where[:3]) + ")"


def check_file_exists(spec):
    """정해둔 파일이 실제로 있는가. 없으면 아직 안 만든 것입니다."""
    missing = [f for f in spec["files"] if not exists(f)]
    if not missing:
        return "pass", str(len(spec["files"])) + "개 모두 있음", " · ".join(spec["files"][:4])
    return "todo", str(len(missing)) + "개 없음", " · ".join(missing)


# ── 문서가 가리키는 경로 ─────────────────────────────────
# CLAUDE.md 는 파일 경로를 자주 적습니다. 파일을 옮기거나 이름을 바꾸면
# 문서만 옛 경로로 남는데, 화면은 멀쩡해 보여서 눈으로는 못 찾습니다.
#
# 경로로 볼 것을 좁게 잡습니다. 안 좁히면 오탐이 납니다 (2026-09-15 실제로 8건).
#   `theme.css`          폴더가 없다. 파일명만 적은 것이라 어느 파일인지 모른다
#   `/api/index.html`    / 로 시작. "여기에 두지 말 것" 이라는 설명 속 주소다
#   `holdings/js/vendor/*`  * 는 하나를 가리키지 않는다
# 그래서 「폴더가 하나 이상 들어간 상대경로」만 봅니다.

PATH_IN_DOC = re.compile(
    r"`((?!/)[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*/[A-Za-z0-9_.-]+"
    r"\.(?:html|css|js|json|py|md|command|bat))`"
)


def check_doc_paths(spec):
    """문서가 가리키는 파일이 저장소에 실제로 있는가."""
    text = read(spec["docFile"])
    if text is None:
        return "mismatch", "문서 없음", spec["docFile"] + " 를 찾지 못했습니다"

    paths = sorted(set(PATH_IN_DOC.findall(text)))
    if not paths:
        return "mismatch", "경로 0개", "문서에서 경로를 하나도 못 찾았습니다 — 정규식을 확인하세요"

    missing = [p for p in paths if not exists(p)]
    if not missing:
        return "pass", str(len(paths)) + "개 모두 있음",             "문서가 가리키는 경로 " + str(len(paths)) + "개 전부 저장소에 있습니다"
    return "mismatch", str(len(missing)) + "개 없음",         "문서에만 있고 저장소에 없음 — " + " · ".join(missing[:5]) +         (" 외 " + str(len(missing) - 5) + "개" if len(missing) > 5 else "")


# ── 없애기로 한 파일 ─────────────────────────────────────
# 합치거나 지우기로 정한 파일이 되살아났는지 봅니다. 되살아나도 화면은
# 멀쩡하고, 값이 두 곳으로 갈린 뒤에야 증상이 나옵니다.

def check_file_absent(spec):
    """있으면 안 되는 파일이 정말 없는가."""
    back = [f for f in spec["files"] if exists(f)]
    if not back:
        return "pass", str(len(spec["files"])) + "개 모두 없음",             "없어야 할 파일 " + str(len(spec["files"])) + "개가 전부 없습니다"
    return "mismatch", str(len(back)) + "개 되살아남",         "없애기로 했는데 있음 — " + " · ".join(back)


# ── 두 벌로 적힌 메뉴 ────────────────────────────────────
# nav.html 에는 목록이 두 벌 있습니다. 위는 PC, 아래는 폰에서 펼치는 전체화면입니다.
# 한 벌만 고치면 폰과 PC 의 메뉴가 달라지는데, 자기 기기에서는 멀쩡해 보여서
# 눈으로는 못 찾습니다. CLAUDE.md 가 「두 곳을 같이 고친다」 고 적어둔 자리입니다.
#
# 로고 링크는 data-nav 가 없어서 저절로 빠집니다. 메뉴 항목만 비교합니다.

NAV_ITEM = re.compile(r'href="([^"]+)"[^>]*data-nav="([^"]+)"')


def check_nav_pair(spec):
    """PC 목록과 모바일 목록이 같은 메뉴를 들고 있는가."""
    text = read(spec["file"])
    if text is None:
        return "mismatch", "파일 없음", spec["file"] + " 를 찾지 못했습니다"

    mark = spec["splitAt"]
    at = text.find(mark)
    if at < 0:
        return "mismatch", "구간을 못 찾음", "「" + mark + "」 가 없습니다 — 구조가 바뀌었는지 보세요"

    pc = set(NAV_ITEM.findall(text[:at]))
    mo = set(NAV_ITEM.findall(text[at:]))
    if not pc or not mo:
        return "mismatch", "항목 0개", "한쪽에서 메뉴를 하나도 못 찾았습니다 — 정규식을 확인하세요"

    if pc == mo:
        return "pass", str(len(pc)) + "개 양쪽 같음",             "PC 와 모바일이 같은 메뉴 " + str(len(pc)) + "개를 들고 있습니다"

    # 이름이 양쪽에 다 있으면 주소가 다른 것입니다. 빠진 것과 구분해서 알립니다.
    name_pc = {n for _, n in pc}
    name_mo = {n for _, n in mo}
    diff_url = sorted(n for _, n in pc - mo if n in name_mo)
    only_pc = sorted(n for _, n in pc - mo if n not in name_mo)
    only_mo = sorted(n for _, n in mo - pc if n not in name_pc)

    parts = []
    if only_pc:
        parts.append("PC 에만: " + " · ".join(only_pc))
    if only_mo:
        parts.append("모바일에만: " + " · ".join(only_mo))
    if diff_url:
        parts.append("주소가 다름: " + " · ".join(diff_url))
    n = len(only_pc) + len(only_mo) + len(diff_url)
    return "mismatch", str(n) + "개 어긋남", "  ".join(parts)


# ── 선에 쓴 상태 색 ──────────────────────────────────────
# 「흰 카드에는 선을 넣지 않는다 · 선에 상태 색을 쓰지 않는다」 (2026-09-15 지시).
#
# 한쪽 변에만 긋는 선(border-top·bottom·left·right)만 봅니다. 그것이 면을
# 나누는 선이기 때문입니다. 네 변을 다 두르는 border / border-color 는
# 체크박스 같은 컨트롤의 생김새라 대상이 아닙니다.

STATE_LINE = re.compile(
    r"border-(?:top|bottom|left|right)(?:-color)?\s*:[^;{}]*"
    r"var\(--[a-z-]*(?:done|warn|danger|accent|up|down)"
)


def check_line_color(spec):
    """면을 나누는 선에 상태 색을 썼는가."""
    found = []
    for rel in spec["files"]:
        text = read(rel)
        if text is None:
            continue
        for m in STATE_LINE.finditer(strip_comments(text, "html")):
            found.append((rel, m.group(0).split(":")[0].strip()))
    if not found:
        return "pass", "0곳", "검사한 파일 " + str(len(spec["files"])) + "개"
    where = sorted(set(f for f, _ in found))
    return "mismatch", str(len(found)) + "곳",         "선에 상태 색을 썼습니다 — " + ", ".join(where[:3])


# ── 아직 안 채운 임시값 ──────────────────────────────────
# 「나중에 채운다」 고 넣어 둔 자리는 잊힙니다. 몇 개 남았는지 세어서
# 0 이 될 때까지 화면에 띄워 둡니다. 개수가 아니라 진행률입니다.

def check_pending(spec):
    """임시로 넣어 둔 값이 몇 개 남았는가. 0 이 되면 통과."""
    text = read(spec["file"])
    if text is None:
        return "mismatch", "파일 없음", spec["file"] + " 를 찾지 못했습니다"

    n = len(re.findall(spec["pattern"], strip_comments(text, spec.get("kind", "js"))))
    if n == 0:
        return "pass", "0개 남음", spec.get("doneNote", "전부 채웠습니다")
    return "todo", str(n) + "개 남음", spec.get("todoNote", "아직 채우지 않은 자리가 있습니다")


CHECKERS = {
    "nav_pair":    check_nav_pair,
    "line_color":  check_line_color,
    "pending":     check_pending,
    "doc_paths":   check_doc_paths,
    "file_absent": check_file_absent,
    "nav_links":   check_nav_links,
    "doc_token":   check_doc_token,
    "pair_sync":   check_pair_sync,
    "raw_color":   check_raw_color,
    "file_exists": check_file_exists,
}


# ══════════════════════════════════════════════════════════
#  실행
# ══════════════════════════════════════════════════════════

def load_expected():
    with open(EXPECTED_PATH, encoding="utf-8") as f:
        return json.load(f)


def run_checks(expected):
    approved = expected.get("approved", {})
    ignored = expected.get("ignored", {})
    results = []

    for spec in expected["checks"]:
        cid = spec["id"]
        fn = CHECKERS.get(spec["type"])

        if fn is None:
            status, actual, detail = "todo", "검사기 없음", "type=" + spec["type"] + " 를 아직 만들지 않았습니다"
        else:
            try:
                status, actual, detail = fn(spec)
            except Exception as e:                       # 한 항목이 터져도 나머지는 돌아야 합니다
                status, actual, detail = "mismatch", "검사 실패", str(e)

        # 검사 제외로 표시해 둔 항목 (오탐으로 판정된 것)
        if cid in ignored:
            status = "ignored"
            detail = ignored[cid].get("why", "") + " — " + detail

        # 「의도함」 으로 승인해 둔 값과 같으면 통과로 봅니다
        elif cid in approved and approved[cid].get("value") == actual:
            status = "pass"
            detail = "승인됨 (" + approved[cid].get("at", "")[:10] + ") — " + detail

        results.append({
            "id": cid,
            "group": spec.get("group", "기타"),
            "title": spec.get("title", cid),
            "scope": spec.get("scope", ""),
            "expected": spec.get("expected", ""),
            "status": status,
            "actual": actual,
            "detail": detail,
        })

    return results


def count(results):
    c = {"pass": 0, "mismatch": 0, "changed": 0, "todo": 0, "ignored": 0}
    for r in results:
        c[r["status"]] = c.get(r["status"], 0) + 1
    return c


def load_prev():
    if not os.path.isfile(LATEST_PATH):
        return None
    try:
        with open(LATEST_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def make_diff(prev, results):
    """직전 회차와 비교합니다. 이 비교가 이 도구의 값어치입니다.

    아침엔 멀쩡했는데 저녁에 나타났다면, 그 사이 작업이 원인이고 범위가 좁혀집니다.
    """
    bad = ("mismatch", "changed")
    now_bad = {r["id"]: r for r in results if r["status"] in bad}

    if not prev:
        return {"new": [r["title"] for r in now_bad.values()], "fixed": [], "note": "첫 검사"}

    prev_bad = {r["id"]: r for r in prev.get("results", []) if r["status"] in bad}

    new = [now_bad[i]["title"] for i in now_bad if i not in prev_bad]
    fixed = [prev_bad[i]["title"] for i in prev_bad if i not in now_bad]

    if new:
        note = "새로 생김 — " + " · ".join(new)
    elif fixed:
        note = "해결됨 — " + " · ".join(fixed)
    else:
        note = "직전과 같음"

    return {"new": new, "fixed": fixed, "note": note}


def main():
    mode = "auto" if "--auto" in sys.argv else "manual"

    expected = load_expected()
    results = run_checks(expected)
    prev = load_prev()

    now = datetime.now(KST)
    report = {
        # **도구가 만든 파일이라는 표시.** 상태줄이 이것을 보고 「미커밋」
        # 에서 뺀다 — 이 파일은 검사기가 돌 때마다 바뀌는데 재권님이
        # 하실 일이 없다 (2026-09-22 지시). **이름을 박지 않으려고**
        # 파일 쪽에 표시를 둔다.
        "generated-by-tool": True,
        "at": now.isoformat(timespec="seconds"),
        "mode": mode,
        "counts": count(results),
        "diff": make_diff(prev, results),
        "results": results,
    }

    os.makedirs(HISTORY_DIR, exist_ok=True)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    with open(os.path.join(HISTORY_DIR, stamp + ".json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(LATEST_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    c = report["counts"]
    print("검사 완료 " + now.strftime("%m/%d %H:%M") + " (" + mode + ")")
    print("  통과 %d · 불일치 %d · 변경 감지 %d · 미구현 %d · 제외 %d"
          % (c["pass"], c["mismatch"], c["changed"], c["todo"], c["ignored"]))
    print("  " + report["diff"]["note"])

    # 종료코드로 결과를 알린다. 매일 자동 실행을 걸면 작업 스케줄러는
    # 이 값으로만 성패를 안다. 늘 0 이면 불일치가 나도 아무도 모른다
    # (2026-09-15 지시).
    #
    #   0  전부 통과
    #   1  손볼 것이 있다 (불일치 · 변경 감지)
    #   2  검사기 자체가 못 돌았다 — 예외로 죽으면 파이썬이 알아서 낸다
    #
    # 「미구현」은 아직 안 만든 검사라 실패로 보지 않는다.
    # 「제외」는 오탐으로 판정해 뺀 것이라 역시 아니다.
    #
    # server.py 는 0 과 1 을 모두 정상으로 받는다. 거기를 함께 고치지 않으면
    # 보드의 「검사」 버튼이 불일치를 오류로 표시한다.
    return 1 if (c["mismatch"] or c["changed"]) else 0


if __name__ == "__main__":
    sys.exit(main())
