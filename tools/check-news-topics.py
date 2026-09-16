#!/usr/bin/env python3
"""뉴스 설정이 두 곳에서 같은지 대조한다.

    holdings/data/news-topics.json    로컬 서버가 읽는다 (server/news.py)
    holdings/worker/kis-worker.js     배포본이 쓴다 (NEWS_TOPICS · NEWS_FEEDS)

워커는 대시보드에 코드만 붙여넣는 방식이라 JSON 파일을 같이 올릴 수 없다.
합칠 수 없는 복제다. 한쪽만 고치면 로컬에서는 새 주제가 보이는데 사이트에는
안 보인다. 둘 다 오류를 내지 않아 눈으로는 못 찾는다.

    python tools/check-news-topics.py     맞으면 0, 어긋나면 1

CLAUDE.md 「같은 값은 한 곳에만 둔다」 참조.
"""
import io
import json
import os
import re
import sys

# 윈도우 콘솔은 기본이 cp949 라 '—' 같은 글자에서 죽는다.
# 출력만 UTF-8 로 바꾼다 (tools/check-theme-sync.py 와 같은 처리).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = "holdings/data/news-topics.json"
JS_PATH = "holdings/worker/kis-worker.js"

RE_TOPICS = re.compile(r"const NEWS_TOPICS = \[(.*?)\n\];", re.S)
RE_FEEDS = re.compile(r"const NEWS_FEEDS = \[(.*?)\n\];", re.S)
RE_DROP = re.compile(r"const NEWS_DROP = \[(.*?)\];", re.S)
RE_BLOCK = re.compile(r"\{(.*?)\}", re.S)
RE_STR = re.compile(r'"([^"]*)"')


def _field(block, key):
    hit = re.search(key + r'\s*:\s*"([^"]*)"', block)
    return hit.group(1) if hit else None


def read_json():
    path = os.path.join(ROOT, JSON_PATH)
    if not os.path.exists(path):
        return None, "파일이 없습니다: " + JSON_PATH
    raw = json.load(io.open(path, encoding="utf-8"))
    return {
        "topics": [t for t in (raw.get("topics") or []) if t.get("on", True)],
        "drop": ((raw.get("버릴제목") or {}).get("말")) or [],
        "feeds": [(f.get("id"), f.get("url")) for f in (raw.get("feeds") or [])],
    }, None


def read_js():
    """워커에서 같은 값을 읽는다.

    자바스크립트를 실행하지 않고 글자만 본다. 배열 리터럴이라 따옴표 안만
    뽑으면 된다.
    """
    path = os.path.join(ROOT, JS_PATH)
    if not os.path.exists(path):
        return None, "파일이 없습니다: " + JS_PATH
    s = io.open(path, encoding="utf-8").read()

    m = RE_TOPICS.search(s)
    if not m:
        return None, "NEWS_TOPICS 를 찾지 못했습니다"

    topics = []
    for block in RE_BLOCK.findall(m.group(1)):
        on = re.search(r"on\s*:\s*(true|false)", block)
        if on and on.group(1) == "false":
            continue                      # 꺼둔 것은 JSON 쪽에서도 빠진다
        kw = re.search(r"keywords\s*:\s*\[(.*?)\]", block, re.S)
        topics.append({
            "id": _field(block, "id"),
            "color": _field(block, "color"),
            "label": _field(block, "label"),
            "keywords": RE_STR.findall(kw.group(1)) if kw else [],
        })

    d = RE_DROP.search(s)
    drop = RE_STR.findall(d.group(1)) if d else []

    feeds = []
    f = RE_FEEDS.search(s)
    if f:
        for block in RE_BLOCK.findall(f.group(1)):
            feeds.append((_field(block, "id"), _field(block, "url")))

    return {"topics": topics, "drop": drop, "feeds": feeds}, None


def main():
    a, err = read_json()
    if err:
        print("[읽기 실패] " + err)
        return 1
    b, err = read_js()
    if err:
        print("[읽기 실패] " + err)
        return 1

    print("  news-topics.json   주제 %d · 버릴말 %d · 출처 %d"
          % (len(a["topics"]), len(a["drop"]), len(a["feeds"])))
    print("  kis-worker.js      주제 %d · 버릴말 %d · 출처 %d"
          % (len(b["topics"]), len(b["drop"]), len(b["feeds"])))

    bad = []

    def differ(what, x, y):
        bad.append("어긋남  %s 이(가) 다릅니다" % what)
        bad.append("        json  : %s" % (x,))
        bad.append("        worker: %s" % (y,))

    ida = [t.get("id") for t in a["topics"]]
    idb = [t.get("id") for t in b["topics"]]
    if ida != idb:
        differ("주제 목록", ", ".join(map(str, ida)), ", ".join(map(str, idb)))
    else:
        for x, y in zip(a["topics"], b["topics"]):
            for key in ("label", "color"):
                if x.get(key) != y.get(key):
                    bad.append("어긋남  %s 의 %s — json %r · worker %r"
                               % (x.get("id"), key, x.get(key), y.get(key)))
            if x.get("keywords") != y.get("keywords"):
                differ("%s 의 주제어" % x.get("id"), x.get("keywords"), y.get("keywords"))

    if a["feeds"] != b["feeds"]:
        differ("받아올 곳", a["feeds"], b["feeds"])
    if a["drop"] != b["drop"]:
        differ("버릴 제목 목록", a["drop"], b["drop"])

    print()
    if bad:
        for line in bad:
            print(line)
        print()
        print("뉴스 설정: 어긋났습니다. 두 곳을 같게 맞춰 주세요.")
        print("워커를 고쳤으면 Cloudflare 에 다시 올려야 합니다.")
        return 1

    print("뉴스 설정: 주제 %d개 · 출처 %d곳, 두 곳이 같습니다."
          % (len(a["topics"]), len(a["feeds"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
