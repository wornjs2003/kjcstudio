# -*- coding: utf-8 -*-
"""같은 줄을 값만 바꿔가며 되풀이해 고치면 알린다.

「두 번 해서 안 되면 세 번째 대신 말한다」(CLAUDE.md)를 그 자리에서 거는 것이다.
룰은 있는데 지켜지지 않았고, 문서 스스로 「이것은 기계가 못 잡는다」 고 적어 두었다.
**전부는 못 잡아도 이 형태는 잡힌다.**

2026-09-17 에 `temp/plan.html` 의 한 줄이 짧은 시간에 네 번 바뀌었다.

    .kh-idx-chart { flex: none; height: 1000px; }
                                        500px
                                        700px
                                        600px

원인은 그 CSS 가 아니라 재권님이 다른 파일을 보고 계셨던 것이었다.
**첫 번째에 안 됐을 때 「왜 안 되는지 모르겠습니다」 라고 말했으면**
값을 네 번 굴리지 않았다.

── 어떻게 세나 ─────────────────────────────────────────
줄 번호는 편집으로 밀리니 쓰지 않는다. **바꿔 넣는 내용에서 숫자를 지워**
모양만 남긴다.

    height: 1000px   →   height: #px
    height: 500px    →   height: #px
    height: 700px    →   height: #px      ← 같은 모양이 세 번째

같은 파일에서 같은 모양이 창 안에 세 번 나오면 알린다.
값 굴리기는 이 모양이고, 보통 작업은 이 모양이 잘 안 나온다.

── 막지 않는다 ─────────────────────────────────────────
`pre-commit` 과 같다. **자물쇠가 아니라 걸림돌이다.**
`exit 2` 만 도구를 막는데 이 스크립트는 그것을 쓰지 않는다.
무슨 일이 있어도 `0` 으로 끝난다 — 감시 하나 때문에 편집이 멈추면 안 된다.
"""
import io
import json
import os
import re
import sys
import time

WINDOW_SEC = 600      # 10분 안에
THRESHOLD = 3         # 세 번째면 알린다
KEEP = 400            # 기록은 이만큼만 남긴다


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    if data.get("tool_name") != "Edit":
        return

    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ""
    new = ti.get("new_string") or ""
    if not path or not new.strip():
        return

    # 숫자를 지워 모양만 남긴다. 긴 편집은 앞부분만 본다 —
    # 값 굴리기는 짧은 줄에서 일어나고, 긴 블록까지 보면 엉뚱한 것이 걸린다.
    norm = re.sub(r"\d+", "#", new.strip())[:200]
    key = os.path.basename(path) + "|" + norm

    root = data.get("cwd") or os.getcwd()
    log = os.path.join(root, ".claude", "edit-churn.jsonl")

    now = time.time()
    rows = []
    try:
        with io.open(log, encoding="utf-8") as fp:
            for line in fp:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if now - r.get("t", 0) < WINDOW_SEC:   # 창 밖은 버린다
                    rows.append(r)
    except OSError:
        pass

    same = [r for r in rows if r.get("k") == key]
    rows.append({"t": now, "k": key})

    try:
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with io.open(log, "w", encoding="utf-8", newline="\n") as fp:
            for r in rows[-KEEP:]:
                fp.write(json.dumps(r, ensure_ascii=False) + "\n")
    except OSError:
        pass

    if len(same) + 1 < THRESHOLD:
        return

    first = min(r["t"] for r in same)
    mins = max(1, int((now - first) / 60))
    short = norm if len(norm) <= 60 else norm[:57] + "…"

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "systemMessage": (
                f"이 줄을 {mins}분 안에 {len(same) + 1}번째 고칩니다 — "
                f"{os.path.basename(path)} · {short}\n"
                "「두 번 해서 안 되면 세 번째 대신 말한다」(CLAUDE.md). "
                "값을 또 바꾸기 전에, 왜 안 되는지 모르겠다고 말하는 편이 빠릅니다."
            ),
        }
    }, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass          # 감시가 편집을 막는 일은 없어야 한다
    sys.exit(0)
