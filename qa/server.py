#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KJC Studio · QA 보드 로컬 서버

  보드 화면의 버튼이 실제로 동작하려면 파일을 읽고 쓸 수 있어야 합니다.
  브라우저만으로는 저장소를 뒤질 수 없어서, 검사와 승인을 대신 처리하는
  작은 서버를 둡니다.

  저장소 루트를 내보냅니다. 화면이 ../assets/ 와 ../partials/ 를 함께 쓰기 때문입니다.

  주소
    /qa/                     보드 화면
    POST /qa/api/run         지금 검사하기
    POST /qa/api/approve     「의도함」 — 지금 값을 새 기준으로
    POST /qa/api/ignore      「검사 제외」 — 오탐으로 판정
    POST /qa/api/unignore    제외 되돌리기
    GET  /qa/api/history     회차 목록

  이 서버는 로컬 전용입니다. 배포 사이트에서는 버튼이 동작하지 않고
  마지막 검사 결과만 읽기 전용으로 보입니다.
"""

import json
import os
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

KST = timezone(timedelta(hours=9))

QA_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(QA_DIR)
HISTORY_DIR = os.path.join(QA_DIR, "history")
EXPECTED_PATH = os.path.join(QA_DIR, "expected.json")
LATEST_PATH = os.path.join(QA_DIR, "latest.json")

PORT = 8093

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_json(path, fallback=None):
    if not os.path.isfile(path):
        return fallback
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def save_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_check(mode="manual"):
    """검사기를 따로 띄워 돌립니다.

    같은 프로세스에서 import 하지 않는 이유는, 검사기를 고친 뒤 서버를
    다시 띄우지 않아도 바로 반영되게 하기 위해서입니다.
    """
    cmd = [sys.executable, os.path.join(QA_DIR, "check.py")]
    if mode == "auto":
        cmd.append("--auto")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def history_list(limit=14):
    """최근 회차를 새 것부터 돌려줍니다."""
    if not os.path.isdir(HISTORY_DIR):
        return []
    names = sorted((n for n in os.listdir(HISTORY_DIR) if n.endswith(".json")), reverse=True)
    out = []
    for n in names[:limit]:
        d = load_json(os.path.join(HISTORY_DIR, n))
        if not d:
            continue
        out.append({
            "file": n,                       # 화면에서 이 회차를 펼칠 때 씁니다
            "at": d.get("at", ""),
            "mode": d.get("mode", ""),
            "counts": d.get("counts", {}),
            "groups": group_summary(d.get("results", [])),
            "note": (d.get("diff") or {}).get("note", ""),
        })
    return out


def group_summary(results):
    """회차마다 어느 묶음을 몇 개 훑었는지.

    회차 줄에 '문구·구조 2 · 디자인 토큰 4' 처럼 적어서,
    펼치지 않아도 무엇을 검사했는지 보이게 합니다.
    """
    order, tally = [], {}
    for r in results:
        g = r.get("group") or "기타"
        if g not in tally:
            tally[g] = {"name": g, "total": 0, "bad": 0}
            order.append(g)
        tally[g]["total"] += 1
        if r.get("status") in ("mismatch", "changed"):
            tally[g]["bad"] += 1
    return [tally[g] for g in order]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *a):
        pass                      # 요청마다 찍으면 시끄러워서 끕니다

    def end_headers(self):
        """화면을 고쳐도 브라우저가 옛 파일을 들고 있으면 안 바뀐 것처럼 보입니다.
        개발용 서버라 캐시를 아예 막습니다."""
        self.send_header("cache-control", "no-store, must-revalidate")
        self.send_header("pragma", "no-cache")
        self.send_header("expires", "0")
        super().end_headers()

    def send_head(self):
        """If-Modified-Since 로 304 를 돌려주지 않게 합니다."""
        self.headers.replace_header("If-Modified-Since", "") \
            if "If-Modified-Since" in self.headers else None
        return super().send_head()

    # ── 도우미 ───────────────────────────────
    def _json(self, body, status=200):
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(raw)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get("content-length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    # ── GET ───────────────────────────────
    def do_GET(self):
        if self.path.startswith("/qa/api/history"):
            return self._json({"ok": True, "items": history_list()})
        return super().do_GET()

    # ── POST ──────────────────────────────
    def do_POST(self):
        if not self.path.startswith("/qa/api/"):
            return self._json({"ok": False, "error": "없는 주소입니다"}, 404)

        action = self.path[len("/qa/api/"):].split("?")[0].strip("/")
        body = self._body()

        if action == "run":
            code, out = run_check(body.get("mode", "manual"))
            if code != 0:
                return self._json({"ok": False, "error": out.strip()[-400:]}, 500)
            return self._json({"ok": True, "report": load_json(LATEST_PATH), "log": out.strip()})

        expected = load_json(EXPECTED_PATH)
        if expected is None:
            return self._json({"ok": False, "error": "expected.json 을 읽지 못했습니다"}, 500)

        cid = body.get("id")
        if not cid:
            return self._json({"ok": False, "error": "어느 항목인지 알려주세요"}, 400)

        now = datetime.now(KST).isoformat(timespec="seconds")

        if action == "approve":
            # 지금 값이 새 기준이 됩니다. 이게 버그와 의도를 가르는 장치입니다.
            expected.setdefault("approved", {})[cid] = {
                "value": body.get("value", ""),
                "at": now,
                "note": body.get("note", "재권님이 「의도함」 을 누름"),
            }
            expected.get("ignored", {}).pop(cid, None)

        elif action == "ignore":
            # 오탐으로 판정. 왜 뺐는지 남겨야 같은 걸 또 올리지 않습니다.
            expected.setdefault("ignored", {})[cid] = {
                "at": now,
                "why": body.get("why", "오탐으로 판정"),
            }
            expected.get("approved", {}).pop(cid, None)

        elif action == "unignore":
            expected.get("ignored", {}).pop(cid, None)
            expected.get("approved", {}).pop(cid, None)

        else:
            return self._json({"ok": False, "error": "모르는 요청입니다"}, 400)

        save_json(EXPECTED_PATH, expected)
        code, out = run_check("manual")          # 바꾼 뒤 바로 다시 검사합니다
        return self._json({"ok": True, "report": load_json(LATEST_PATH), "log": out.strip()})


def main():
    url = "http://localhost:%d/qa/" % PORT

    print("-" * 52)
    print("  KJC Studio · QA 보드")
    print("-" * 52)
    print()
    print("  주소 : " + url)
    print()
    print("  종료 : 이 창을 닫거나 Ctrl+C")
    print("-" * 52)
    print()

    # 처음 열 때 한 번 검사해 둡니다
    code, out = run_check("manual")
    print(out.strip())
    print()

    threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  서버를 멈췄습니다.")


if __name__ == "__main__":
    main()
