# -*- coding: utf-8 -*-
"""
세션 목록을 훑어서 두 파일을 다시 만든다.

  resume-sessions.bat  이름이 붙은 세션을 각각 새 창으로 여는 실행 파일
  SESSIONS.md          세션 목록과 복구 방법을 적은 문서

세션이 늘거나 이름이 바뀌면 이 스크립트를 다시 돌리면 된다.
resume-sessions.bat 은 실행될 때 스스로 이 스크립트를 먼저 부르므로,
평소에는 따로 돌릴 일이 없다.

세션 기록은 Claude Code 가 아래에 남긴다.
  %USERPROFILE%\\.claude\\projects\\C--work-KJCStudio\\<세션ID>.jsonl
이름은 `/rename` 을 쓴 기록에서 찾는다. 이름이 없는 세션은 목록에서 뺀다.
"""
import io
import os
import re
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(os.path.expanduser("~"), ".claude", "projects", "C--work-KJCStudio")
BAT = os.path.join(REPO, "resume-sessions.bat")
DOC = os.path.join(REPO, "SESSIONS.md")

# 이름에 쓸 수 있는 글자만 받는다. 넓게 잡으면 대화에 섞인 코드 조각까지
# 이름으로 잡히는 일이 생긴다 (실제로 그랬다).
RENAME = re.compile(r"Session renamed to: ([가-힣A-Za-z0-9_\-. ]{1,30})")


def find_name(path):
    """파일 전체에서 마지막 rename 기록을 찾는다. 큰 파일이라 조각내서 읽는다."""
    name = ""
    try:
        with io.open(path, encoding="utf-8", errors="ignore") as fp:
            for chunk in iter(lambda: fp.read(1 << 20), ""):
                for m in RENAME.finditer(chunk):
                    name = m.group(1).strip()
    except OSError:
        pass
    return name


def collect():
    rows = []
    if not os.path.isdir(LOGS):
        return rows
    for fn in os.listdir(LOGS):
        if not fn.endswith(".jsonl"):
            continue
        path = os.path.join(LOGS, fn)
        name = find_name(path)
        if not name:                      # 이름 없는 세션은 싣지 않는다
            continue
        rows.append({
            "id": fn[:-6],
            "name": name,
            "mtime": datetime.fromtimestamp(os.path.getmtime(path)),
            "mb": os.path.getsize(path) / 1024 / 1024,
        })
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return rows


def write_bat(rows):
    lines = [
        "@echo off",
        "chcp 65001 > nul",
        "REM ===================================================================",
        "REM  KJC Studio - 세션 한 번에 열기",
        "REM  이 파일은 tools/update-sessions.py 가 만든다. 직접 고치지 말 것.",
        "REM  세션이 늘면 이 파일을 실행만 해도 목록이 새로 채워진다.",
        "REM ===================================================================",
        "",
        "cd /d \"%~dp0\"",
        "",
        "REM 목록을 먼저 새로 만든다 (세션이 늘었을 수 있으므로)",
        "python tools\\update-sessions.py --quiet",
        "",
    ]
    if not rows:
        lines += [
            "echo 이름이 붙은 세션이 없습니다.",
            "echo 각 창에서 /rename 으로 이름을 붙인 뒤 다시 실행하세요.",
            "pause",
        ]
    else:
        for r in rows:
            lines.append(f"REM {r['name']}")
            lines.append(
                f'start "{r["name"]}" cmd /k "cd /d %~dp0 && claude --resume {r["id"]}"'
            )
            lines.append("")
        lines.append(f"echo 세션 {len(rows)}개를 열었습니다.")
        lines.append("timeout /t 2 > nul")

    # .bat 은 CRLF 로 저장한다 (.gitattributes 규칙)
    with io.open(BAT, "w", encoding="utf-8", newline="\r\n") as fp:
        fp.write("\n".join(lines) + "\n")


def write_doc(rows):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    L = []
    A = L.append
    A("# 세션 복구 방법")
    A("")
    A("재부팅하거나 창을 닫아도 대화는 남는다. 아래 방법으로 이어서 쓴다.")
    A("")
    A(f"> 이 문서는 `tools/update-sessions.py` 가 만든다. 직접 고치지 말 것.")
    A(f"> 마지막 갱신 {now}")
    A("")
    A("## 한 번에 열기")
    A("")
    A("`resume-sessions.bat` 을 더블클릭하면 아래 세션이 각각 새 창으로 열린다.")
    A("실행할 때 목록을 다시 훑으므로, 세션이 늘어도 그대로 두면 된다.")
    A("")
    A("## 지금 있는 세션")
    A("")
    if not rows:
        A("이름이 붙은 세션이 없다. 각 창에서 `/rename 이름` 을 먼저 쓴다.")
    else:
        A("| 이름 | 세션 ID | 마지막 대화 | 크기 |")
        A("|---|---|---|---|")
        for r in rows:
            A(f"| **{r['name']}** | `{r['id']}` | {r['mtime']:%m-%d %H:%M} | {r['mb']:.0f}MB |")
    A("")
    A("## 하나만 열기")
    A("")
    A("```")
    A("claude --resume <세션 ID>")
    A("```")
    A("")
    A("예를 들어 이렇게 친다.")
    A("")
    A("```")
    if rows:
        A(f"claude --resume {rows[0]['id']}    REM {rows[0]['name']}")
    else:
        A("claude --resume 04fa6a4d-eada-4ddc-9cb9-18ae177540e4")
    A("```")
    A("")
    A("ID 를 모르면 아래처럼 쳐서 목록에서 고른다.")
    A("")
    A("```")
    A("claude --resume")
    A("```")
    A("")
    A("가장 최근 대화 하나만 이어갈 때는 이것으로 충분하다.")
    A("")
    A("```")
    A("claude --continue")
    A("```")
    A("")
    A("## 알아둘 것")
    A("")
    A("- **작업 폴더를 맞춰서 연다.** 네 세션 모두 `C:\\work\\KJCStudio` 에서 돈다.")
    A("  다른 곳에서 열면 상대 경로가 어긋난다. `resume-sessions.bat` 은 알아서 맞춘다")
    A("- **이름이 없는 세션은 목록에 싣지 않는다.** `/rename` 을 쓴 적이 있어야 잡힌다")
    A("- 그냥 `claude` 만 치면 **새 세션**이 생긴다. 기존 대화와 별개다")
    A("- 세션 기록은 `%USERPROFILE%\\.claude\\projects\\C--work-KJCStudio\\` 에 쌓인다")
    A("- 네 세션은 같은 작업 트리를 공유한다. 레인은 `CLAUDE.md` 「세션 역할 분담」 표를 따른다")
    A("")
    A("## 목록이 안 맞을 때")
    A("")
    A("세션을 새로 만들고 이름을 붙였는데 목록에 없으면 아래를 실행한다.")
    A("")
    A("```")
    A("python tools\\update-sessions.py")
    A("```")
    A("")
    with io.open(DOC, "w", encoding="utf-8", newline="\n") as fp:
        fp.write("\n".join(L))


def main():
    quiet = "--quiet" in sys.argv
    rows = collect()
    write_bat(rows)
    write_doc(rows)
    if not quiet:
        print(f"세션 {len(rows)}개를 찾았습니다.")
        for r in rows:
            print(f"  {r['name']:<16} {r['id']}  ({r['mtime']:%m-%d %H:%M})")
        print()
        print(f"  {BAT}")
        print(f"  {DOC}")


if __name__ == "__main__":
    main()
