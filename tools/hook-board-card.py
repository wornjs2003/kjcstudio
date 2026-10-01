# -*- coding: utf-8 -*-
"""PreToolUse(Edit·Write) 훅 — 「일은 보드에서 시작한다」 의 ① (보조. 주는 pre-commit 의 ③).

저장소 안 파일을 고치려는데 이 세션의 doing 카드가 보드에 없으면 막는다.
`temp/` · 세션 임시 폴더 · 메모리 폴더 · 보드 데이터는 범위 밖이다 — 안 빼면 메모를
적는 것까지 막혀 룰을 지키려는 행동이 막힌다. 보드를 못 봤으면 막지 않는다.
"""
import json
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_OF_SCOPE = ("temp/", "holdings/data/docs/")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("tool_name") not in ("Edit", "Write"):
        return 0
    path = (data.get("tool_input") or {}).get("file_path") or ""
    if not path:
        return 0
    top = subprocess.run(["git", "-C", os.path.dirname(path) or ".", "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True).stdout.strip()
    if not top:
        return 0                                   # 저장소 밖 — 임시 폴더 · 메모리 폴더
    rel = os.path.relpath(path, top)
    if rel.startswith("..") or any(rel.startswith(p) for p in OUT_OF_SCOPE):
        return 0
    tool = os.path.join(top, "tools", "board-card.py")
    if not os.path.exists(tool):
        return 0
    r = subprocess.run([sys.executable, tool, "--gate", "edit"], capture_output=True, text=True, timeout=5)
    if r.returncode == 1:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "일은 보드에서 시작한다 — " + r.stdout.strip()}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
