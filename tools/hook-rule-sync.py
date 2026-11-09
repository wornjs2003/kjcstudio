#!/usr/bin/env python3
"""룰 문서는 폴더가 뒤처져도 최신을 읽게 — 바뀐 절만 넣어 준다 (2026-11-09 지시).

재권님 말씀 그대로다 — 「룰 만들어 놓지 않았나?」 → 「룰을 공통으로 다 세션별로 잘 읽을 수 있도록 개념정의한테 말해」
(개발1 창 · 10:4x) → 문안에 「응」. 계기는 7785602 직후 개발1 이 그 룰을 어긴 것 — kjc-daily 가 미커밋을 들고 받기를
미뤄 폴더 CLAUDE.md 에 그 절이 없었다. CLAUDE.md 「룰 문서는 폴더가 뒤처져도 최신을 읽는다」 가 이 도구의 룰이다.

세 자리에서 돈다(같은 파일 · 훅 이름은 stdin 의 hook_event_name 으로 가른다).
    SessionStart       첫 줄에 「이 폴더가 로컬 main 보다 룰 커밋 N 건 뒤」 · 그 아래 바뀐 절의 바뀐 줄(앞뒤 두 줄) · 새 절은 통째로
    UserPromptSubmit   main 의 룰 문서가 이 세션이 마지막 본 것보다 새것이면 한 번만
    PreToolUse         〃 — 세션 간 메시지 턴은 UserPromptSubmit 이 안 돌아서(창구 검토)

- **비교는 로컬 `main` 과 갈림점(`git merge-base HEAD main`)** — 같은 .git 이라 fetch 없이 읽힌다. main 쪽에서 바뀐 것만 넣는다 —
  가지가 룰 문서를 먼저 고쳤어도 그것을 「지운 줄」 로 거꾸로 넣지 않는다(qa 시험 11-09). 작업 트리가 아니라 커밋과 견준다 —
  개발 폴더에서 룰 문서를 고치는 중인 세션에게 「main 쪽 옛 본문」 을 넣지 않게. 개발 폴더는 HEAD 가 main 이라 늘 0 이다 —
  그 0 은 「뒤처짐 없음」 이지 「못 잼」 이 아니다
- **룰 문서는 이름으로 센다** — main 의 파일 중 이름이 CLAUDE.md · SKILL.md 인 것. 목록을 박지 않는다
- **값싼 길 먼저** — 파일마다 blob 해시(`git rev-parse`)만 견주고, 다를 때만 본문을 읽는다
- **이미 보여 준 것** 은 세션마다 한 파일(main 쪽 blob 해시)로 남긴다 — 같은 것을 두 번 넣지 않는다
- **훅 자체가 낡지 않게** — 이 파일이 main 의 것과 다르면 main 판을 읽어 그것으로 돈다(뒤처진 폴더도 새 셈을 쓴다).
  다만 settings.json 의 등록은 폴더 것이라, 이 훅이 아예 없는 폴더는 한 번은 받아야 한다
- **폴더 파일은 안 건드린다** — 받기(merge)는 그대로 각 세션 · 창구 몫이다. 읽기만 맞춘다
- **못 읽으면 막지 않고** 「룰 최신 여부 못 잼」 한 줄 + logs/rule-sync.log 한 줄
"""

import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAX_CHARS = 12000          # 넣는 본문의 한도 — 넘으면 절 제목 목록 + 읽는 명령만
NAMES = ("CLAUDE.md", "SKILL.md")
SELF = "tools/hook-rule-sync.py"
STATE_DIR = os.path.join(tempfile.gettempdir(), "claude-rule-sync")
HEAD_RE = re.compile(r"^(#{1,4}) +(.+?) *$")


def git(cwd, *args):
    r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=5)
    if r.returncode != 0:
        raise RuntimeError("git %s 실패" % args[0])
    return r.stdout


def blob(cwd, ref, path):
    r = subprocess.run(["git", "-C", cwd, "rev-parse", "-q", "--verify", "%s:%s" % (ref, path)],
                       capture_output=True, text=True, timeout=5)
    return r.stdout.strip() if r.returncode == 0 else None


def sections(text):
    """절 제목 → 본문. 코드블록 안의 # 는 제목이 아니다. 제목이 같으면 뒤에 차례를 붙여 가른다."""
    out, cur, buf, fence, seen = {}, "(머리)", [], False, {}
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else HEAD_RE.match(line)
        if m:
            out[cur] = "\n".join(buf)
            t = m.group(2)
            seen[t] = seen.get(t, 0) + 1
            cur = t if seen[t] == 1 else "%s (%d)" % (t, seen[t])
            buf = [line]
        else:
            buf.append(line)
    out[cur] = "\n".join(buf)
    return out


def changed(cwd, base, path):
    """main 쪽에서 바뀐 · 새 절(본문), 지워진 절 제목. 빈 줄만 달라진 절 · 빈 머리는 뺀다(qa 시험 11-09)."""
    new = sections(git(cwd, "show", "main:" + path))
    old = sections(git(cwd, "show", "%s:%s" % (base, path))) if blob(cwd, base, path) else {}
    diff = [(t, b) for t, b in new.items() if b.strip() and (old.get(t) or "").strip() != b.strip()]
    gone = [t for t in old if t not in new]
    return diff, gone


def state_file(sid):
    os.makedirs(STATE_DIR, exist_ok=True)
    return os.path.join(STATE_DIR, re.sub(r"[^A-Za-z0-9_-]", "_", sid or "nosession") + ".json")


def log(cwd, msg):
    try:
        top = git(cwd, "rev-parse", "--show-toplevel").strip()
        os.makedirs(os.path.join(top, "logs"), exist_ok=True)
        with open(os.path.join(top, "logs", "rule-sync.log"), "a", encoding="utf-8") as f:
            import time
            f.write("%s %s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), cwd, msg))
    except Exception:
        pass


def build(cwd, sid, event):
    # git 한 번으로 HEAD ↔ main 에서 다른 룰 문서만 — 도구 호출마다 돌아서 값싼 길이 먼저다(개발 폴더는 늘 빈 값)
    base = git(cwd, "merge-base", "HEAD", "main").strip()
    out = git(cwd, "diff", "--name-only", base, "main", "--", *[":(glob)**/" + n for n in NAMES])
    pend = [(p, blob(cwd, "main", p)) for p in out.splitlines() if p]
    pend = [(p, mb) for p, mb in pend if mb]   # main 에서 지워진 문서는 넣지 않는다
    sf = state_file(sid)
    try:
        shown = json.load(open(sf, encoding="utf-8"))
    except Exception:
        shown = {}
    todo = [(p, mb) for p, mb in pend if shown.get(p) != mb]
    if not todo:
        return None
    behind = git(cwd, "rev-list", "--count", "HEAD..main", "--", *[p for p, _ in pend]).strip()
    head = ("[룰 최신] 이 폴더가 로컬 main 보다 룰 문서 커밋 %s 건 뒤입니다 — 아래는 main 쪽 최신 본문입니다. "
            "이것을 따르고(+ 줄이 지금 룰), 룰 문구를 옮겨 적을 때는 `git show main:<파일>` 에서 뽑으십시오. 받기(merge staging)는 그대로 하십시오." % behind)
    parts, titles = [], []
    for p, mb in todo:
        diff, gone = changed(cwd, base, p)
        old_secs = sections(git(cwd, "show", "%s:%s" % (base, p))) if blob(cwd, base, p) else {}
        for t, b in diff:
            if t in old_secs:              # 바뀐 절 — 바뀐 줄과 앞뒤 두 줄만(+ 새 줄 · - 지운 줄)
                hunk = [l for l in difflib.unified_diff(old_secs[t].splitlines(), b.splitlines(), lineterm="", n=2)
                        if not l.startswith(("---", "+++"))]
                if not any(l[:1] in "+-" and l[1:].strip() for l in hunk if not l.startswith("@@")):
                    continue               # 빈 줄만 달라졌다
                parts.append("── %s · 「%s」 · 바뀐 줄(+ 새 줄 · - 지운 줄) ──\n%s" % (p, t, "\n".join(hunk)))
            else:                          # 새 절 — 통째로
                parts.append("── %s · 「%s」 · 새 절 ──\n%s" % (p, t, b.strip()))
            titles.append("%s 「%s」" % (p, t))
        for t in gone:
            parts.append("── %s · 「%s」 ── main 에서 지워진 절입니다" % (p, t))
            titles.append("%s 「%s」(지워짐)" % (p, t))
    body = "\n\n".join(parts)
    if len(body) > MAX_CHARS:
        body = ("바뀐 절이 많아 제목만 적습니다 — `git show main:<파일>` 로 그 절을 읽으십시오.\n  · "
                + "\n  · ".join(titles))
    for p, mb in todo:
        shown[p] = mb
    with open(sf, "w", encoding="utf-8") as f:
        json.dump(shown, f)
    return head + "\n\n" + body if parts else None


def emit(event, text):
    if event in ("SessionStart", "UserPromptSubmit"):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}, ensure_ascii=False))
    else:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}, ensure_ascii=False))


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw or "{}")
    except Exception:
        data = {}
    cwd = data.get("cwd") or os.getcwd()
    event = data.get("hook_event_name") or "SessionStart"
    # 훅 자체가 낡았으면 main 판으로 돈다 — 한 번만(환경 표시)
    if not os.environ.get("KJC_RULE_SYNC_MAIN"):
        try:
            latest = blob(cwd, "main", SELF)
            here = os.path.abspath(__file__)
            with open(here, "rb") as f:
                body = f.read()
            local = hashlib.sha1(b"blob %d\0" % len(body) + body).hexdigest()
            if latest and latest != local:
                tmp = os.path.join(STATE_DIR, "hook-rule-sync-%s.py" % latest[:12])   # 판마다 이름이 달라 세션끼리 안 부딪힌다
                if not os.path.exists(tmp):
                    os.makedirs(STATE_DIR, exist_ok=True)
                    part = tmp + ".%d" % os.getpid()
                    with open(part, "w", encoding="utf-8") as f:
                        f.write(git(cwd, "show", "main:" + SELF))
                    os.replace(part, tmp)
                env = dict(os.environ, KJC_RULE_SYNC_MAIN="1")
                r = subprocess.run([sys.executable, tmp], input=raw, capture_output=True, text=True, env=env, timeout=10)
                sys.stdout.write(r.stdout)
                return 0
        except Exception:
            pass                                # main 판을 못 읽으면 이 판으로 돈다
    try:
        text = build(cwd, data.get("session_id"), event)
    except Exception as e:
        log(cwd, "못 잼 (%s)" % type(e).__name__)
        if event == "SessionStart":
            emit(event, "[룰 최신] 룰 최신 여부 못 잼 — 폴더가 뒤처졌는지 `git log --oneline HEAD..main -- CLAUDE.md` 로 직접 세십시오")
        return 0
    if text:
        emit(event, text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
