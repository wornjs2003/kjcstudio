# -*- coding: utf-8 -*-
"""경로 조건 룰을 명령줄로 바로 고칠 때도 넣어 준다 (2026-11-24).

루트 CLAUDE.md 가 너무 커져 화면 · 서버 전용 절을 `.claude/rules/*.md`(frontmatter `paths:`)로 옮겼다
(재권님 「응 그렇게 해」 11-24 19:1x · CLAUDE.md 「이 문서 밖에 있는 룰」). Claude Code 는 그 파일을 **맞는 파일을 읽거나
고칠 때** 넣는데, qa 시뮬(11-24)에서 — Read · Edit 도구 · Bash cat · head · grep 은 들어오고 **Bash sed -i · 파이썬 쓰기는
안 들어왔다.** 자동 모드 세션은 그 길로 자주 고쳐 그 룰을 못 본 채 고칠 수 있다. 이 훅이 그 틈을 메운다.

    PreToolUse  Read · Edit · Write · MultiEdit · NotebookEdit · Bash 의 읽기(cat · head · tail · grep · rg · sed -n · wc)
                → 그 룰 파일은 「저절로 들어옴」 으로 적기만
                Bash 의 쓰기(sed -i · 리다이렉트 · tee · 파이썬 · node · mv · cp · perl -i · git apply)
                → 그 세션이 그 룰 파일을 아직 못 받았으면 본문을 한 번 넣는다
    SessionStart(시작 · /clear · 압축)  → 적어 둔 것을 지운다(압축 뒤에는 경로 룰이 바로 안 돌아온다 — 공식 문서)

- 룰 파일 · 범위는 이름을 박지 않고 `.claude/rules/*.md` 의 `paths:` 를 그때 읽는다
- 막지 않는다 · 못 읽으면 조용히 지나가고 `logs/path-rules.log` 에 한 줄
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STATE_DIR = os.path.join(tempfile.gettempdir(), "claude-path-rules")
READ_RE = re.compile(r"^\s*(?:cat|head|tail|grep|rg|wc|less|sed\s+-n)\b")
WRITE_RE = re.compile(r"\bsed\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*i|\bperl\s+-[a-zA-Z]*i|\btee\b|(?<![0-9&<>])>>?\s*[^\s&>|]|"
                      r"\bmv\b|\bcp\b|\bgit\s+apply\b|\bpatch\b|"
                      # 파이썬 · node 는 「돌리기」 가 대부분이라 쓰는 말이 함께 있을 때만 쓰기로 본다
                      r"\b(?:python3?|node)\b[\s\S]*(?:open\([^)]*['\"][wa]|\.write\(|write_text|writeFileSync|os\.replace|shutil\.)")
WHOLE_RE = re.compile(r"\bsed\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*i|\bperl\s+-[a-zA-Z]*i|\bgit\s+apply\b|\bpatch\b|"
                      r"\b(?:python3?|node)\b[\s\S]*(?:open\(|\.write\(|write_text|writeFileSync|os\.replace|shutil\.)")   # 명령 안 경로 전부가 고칠 대상일 수 있는 꼴
RUN_RE = re.compile(r"\b(?:python3?|node|sh|bash)\s+(?:-[a-zA-Z]+\s+)*([\w./~-]+)")   # 돌리는 스크립트 자체는 고치는 대상이 아니다
PATH_RE = re.compile(r"[\w./~-]*[\w-]\.(?:js|mjs|css|html|json|py|bat|plist|md|sh|command)\b")


def top_of(cwd):
    r = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=3)
    return r.stdout.strip() if r.returncode == 0 else None


def glob_re(g):
    out, i = "", 0
    while i < len(g):
        if g.startswith("**/", i):
            out += r"(?:.*/)?"; i += 3
        elif g.startswith("**", i):
            out += r".*"; i += 2
        elif g[i] == "*":
            out += r"[^/]*"; i += 1
        elif g[i] == "?":
            out += r"[^/]"; i += 1
        else:
            out += re.escape(g[i]); i += 1
    return re.compile(out + r"\Z")


def rules(top):
    """[(룰 파일 상대 경로, [정규식], 본문)] — frontmatter paths: 가 있는 것만."""
    d = os.path.join(top, ".claude", "rules")
    out = []
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not name.endswith(".md"):
            continue
        text = open(os.path.join(d, name), encoding="utf-8").read()
        m = re.match(r"---\n(.*?)\n---\n", text, re.S)
        if not m:
            continue
        pats = re.findall(r'^\s*-\s*"?([^"\n]+?)"?\s*$', m.group(1), re.M)
        if pats:
            out.append((".claude/rules/" + name, [glob_re(p) for p in pats], text[m.end():]))
    return out


def rel(top, cwd, p):
    p = os.path.expanduser(p)
    a = os.path.normpath(p if os.path.isabs(p) else os.path.join(cwd, p))
    r = os.path.relpath(a, top)
    return None if r.startswith("..") else r.replace(os.sep, "/")


def state_path(sid):
    os.makedirs(STATE_DIR, exist_ok=True)
    return os.path.join(STATE_DIR, re.sub(r"[^A-Za-z0-9_-]", "_", sid or "nosession") + ".json")


def log(top, msg):
    try:
        os.makedirs(os.path.join(top, "logs"), exist_ok=True)
        with open(os.path.join(top, "logs", "path-rules.log"), "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    cwd = data.get("cwd") or os.getcwd()
    sid = data.get("session_id")
    event = data.get("hook_event_name") or ""
    sp = state_path(sid)
    if event == "SessionStart":
        try:
            os.remove(sp)
        except OSError:
            pass
        return 0
    top = top_of(cwd)
    if not top:
        return 0
    try:
        rs = rules(top)
        if not rs:
            return 0
        tool = data.get("tool_name") or ""
        ti = data.get("tool_input") or {}
        if tool == "Bash":
            cmd = ti.get("command") or ""
            run = set(RUN_RE.findall(cmd))
            paths = [p for p in PATH_RE.findall(cmd) if p not in run]
            kind = "read" if READ_RE.search(cmd) and not WRITE_RE.search(cmd) else "write" if WRITE_RE.search(cmd) else None
            if kind == "write" and not WHOLE_RE.search(cmd):
                # 리다이렉트 · tee · mv · cp 는 쓰는 자리만 — `git show x:a.js > /tmp/b` 의 a.js 는 읽는 쪽이다
                tg = re.findall(r"(?:>>?|\btee\s+(?:-a\s+)?)\s*([^\s&|;]+)", cmd)
                tg += [m.split()[-1] for m in re.findall(r"\b(?:mv|cp)\s+[^;&|\n]+", cmd)]
                paths = [p for p in paths if p in tg or any(t.endswith(p) for t in tg)]
        else:
            paths = [ti.get("file_path") or ti.get("notebook_path") or ""]
            kind = "read"                     # 도구로 읽기 · 고치기는 Claude Code 가 저절로 넣는다
        if not kind:
            return 0
        hit = []
        for p in paths:
            r = rel(top, cwd, p) if p else None
            if not r:
                continue
            for name, pats, body in rs:
                if name not in [h[0] for h in hit] and any(x.match(r) for x in pats):
                    hit.append((name, body, r))
        if not hit:
            return 0
        try:
            st = json.load(open(sp, encoding="utf-8"))
        except Exception:
            st = {}
        give = []
        for name, body, r in hit:
            if st.get(name):
                continue
            st[name] = "seen" if kind == "read" else "given"
            if kind == "write":
                give.append("── %s (이 명령이 고치는 %s 가 그 범위) ──\n%s" % (name, r, body.strip()))
        tmp = sp + ".%d" % os.getpid()
        json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, sp)
        if give:
            log(top, "넣음 %s %s" % (sid, ", ".join(h[0] for h in hit)))
            text = ("[경로 룰] 명령줄로 바로 고치면 경로 조건 룰이 저절로 안 들어와 이 훅이 이 세션에 한 번 넣습니다 — "
                    "고치기 전에 아래 룰을 따르십시오(CLAUDE.md 「이 문서 밖에 있는 룰」).\n\n" + "\n\n".join(give))
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}, ensure_ascii=False))
    except Exception as e:
        log(top, "못 잼 (%s)" % type(e).__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
