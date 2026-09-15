#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KJC Studio · QA 검사기

  의도한 값(expected.json)과 지금 저장소 상태를 대조합니다.
  결과를 qa/latest.json 과 qa/history/ 에 남기고, 직전 회차와 비교해 무엇이
  새로 생기고 무엇이 해결됐는지 적습니다.

  혼자서도 돌아갑니다.
      python qa/check.py
      python qa/check.py --auto      자동 실행으로 기록

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
        return re.sub(r"<!--.*?-->", " ", text, flags=re.S)
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


def check_raw_color(spec):
    """토큰을 쓰지 않고 색을 직접 박은 곳이 있는가.

    주석을 지우고 봅니다. 토큰을 정의하는 파일 자체는 당연히 색이 있으므로 제외합니다.
    """
    found = []
    for rel in spec["files"]:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        if rel in spec.get("exclude", []):
            continue
        kind = "css" if rel.endswith(".css") else ("html" if rel.endswith(".html") else "js")
        body = strip_comments(read(rel), kind)
        for m in re.finditer(r"#[0-9a-fA-F]{6}\b", body):
            found.append((rel, m.group(0).lower()))

    if not found:
        return "pass", "0곳", "검사한 파일 " + str(len(spec["files"])) + "개"

    colors = sorted(set(c for _, c in found))
    where = sorted(set(f for f, _ in found))
    return "changed", str(len(found)) + "곳 · " + str(len(colors)) + "종", \
        " · ".join(colors[:4]) + (" 외" if len(colors) > 4 else "") + "  (" + ", ".join(where[:3]) + ")"


def check_file_exists(spec):
    """정해둔 파일이 실제로 있는가. 없으면 아직 안 만든 것입니다."""
    missing = [f for f in spec["files"] if not exists(f)]
    if not missing:
        return "pass", str(len(spec["files"])) + "개 모두 있음", " · ".join(spec["files"][:4])
    return "todo", str(len(missing)) + "개 없음", " · ".join(missing)


CHECKERS = {
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
