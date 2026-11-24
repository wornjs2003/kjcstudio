# -*- coding: utf-8 -*-
"""경로 조건 룰을 명령줄로 바로 고칠 때도 넣어 준다 (2026-11-24).

루트 CLAUDE.md 가 너무 커져 화면 · 서버 전용 절을 `.claude/rules/*.md`(frontmatter `paths:`)로 옮겼다
(재권님 「응 그렇게 해」 11-24 19:1x · CLAUDE.md 「이 문서 밖에 있는 룰」). Claude Code 는 그 파일을 **맞는 파일을 읽거나
고칠 때** 넣는데, qa 시뮬(11-24)에서 — Read · Edit 도구 · Bash cat · head · grep 은 들어오고 **Bash sed -i · 파이썬 쓰기는
안 들어왔다.** 자동 모드 세션은 그 길로 자주 고쳐 그 룰을 못 본 채 고칠 수 있다. 이 훅이 그 틈을 메운다.

    PreToolUse  Read · Edit · Write · MultiEdit · NotebookEdit · Bash 의 읽기(cat · head · tail · grep · rg · sed -n · wc)
                → 그 룰 파일은 「저절로 들어옴」 으로 적기만
                Bash 의 쓰기(sed -i · 리다이렉트 · tee · 파이썬 · node · mv · cp · perl -i · git apply)
                → 그 세션이 그 룰 파일을 아직 못 받았으면 **한 번 멈추고** 「그 파일을 읽기 도구로 먼저 여십시오」 + 절 제목
                  (다시 돌리면 지나간다 · 재권님 「응 해」 11-24 19:2x — 알림만으로는 명령이 돈 뒤에 읽혔다 · 본문은 1만 자 한도로 못 넣고
                  룰 파일 cat 은 출력이 잘려 그 범위 파일을 열게 한다 · qa 11-24)
                  경로는 cd 뒤 자리 · 같은 저장소 다른 워크트리 절대경로 · 파이썬 코드 안 따옴표 경로(변수 포함)로 풀고,
                  heredoc 본문 · 따옴표 안 글(커밋 메시지 · 카드 메모) · git 명령은 뺀다
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
# 파이썬 · node 의 「쓰는 말」 — open( 은 쉼표 뒤 모드가 w · a · x 일 때만(경로 첫 글자 a · w 를 모드로 읽던 헛걸림 · qa 11-24)
PYW = (r"\b(?:python3?|node)\b[\s\S]*(?:open\([^)]*,\s*(?:mode\s*=\s*)?[rb]?['\"][wax]|\.write\(|write_text|write_bytes|"
       r"writeFileSync|appendFileSync|os\.replace|shutil\.(?:copy|move))")
NOTE_MAX = 9000              # 넣는 글 한도 — Claude Code 는 훅 글이 1만 자 남짓을 넘으면 문맥에 안 넣고 미리보기 2KB 만 준다(qa 11-24 잼)
READ_RE = re.compile(r"^\s*(?:cat|head|tail|grep|rg|wc|less|sed\s+-n)\b")
WRITE_RE = re.compile(r"\bsed\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*i|\bperl\s+-[a-zA-Z]*i|\btee\b|(?<![0-9&<>])>>?\s*[^\s&>|]|"
                      r"\bmv\b|\bcp\b|\bgit\s+apply\b|\bpatch\b|"
                      # 파이썬 · node 는 「돌리기」 가 대부분이라 쓰는 말이 함께 있을 때만 쓰기로 본다
                      + PYW)
WHOLE_RE = re.compile(r"\bsed\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*i|\bperl\s+-[a-zA-Z]*i|\bgit\s+apply\b|\bpatch\b|"
                      + PYW)   # 명령 안 경로 전부가 고칠 대상일 수 있는 꼴
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


def worktrees(top):
    r = subprocess.run(["git", "-C", top, "worktree", "list", "--porcelain"], capture_output=True, text=True, timeout=3)
    return [l[9:] for l in r.stdout.splitlines() if l.startswith("worktree ")] or [top]


def rel(tops, cwd, p):
    """저장소 자리 기준 상대 경로 — 같은 저장소의 다른 워크트리(kjc-dev2 · kjc-home …) 절대경로도 그 자리 기준으로(qa 11-24 놓침)."""
    p = os.path.expanduser(p)
    a = os.path.normpath(p if os.path.isabs(p) else os.path.join(cwd, p))
    for t in sorted(tops, key=len, reverse=True):
        r = os.path.relpath(a, t)
        if not r.startswith(".."):
            return r.replace(os.sep, "/")
    return None


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
            # heredoc 본문은 글이다 — 메모 · 메시지에 적은 경로는 고칠 대상이 아니다(작업우선순위 11-24 헛걸림)
            head = re.split(r"<<-?\s*['\"]?\w+['\"]?", cmd, maxsplit=1)[0]
            bare = re.sub(r"'[^']*'|\"[^\"]*\"", "''", head)       # 따옴표 안 글(커밋 메시지 · 카드 메모)을 뺀 명령
            pyw = re.search(PYW, cmd)
            if pyw:   # 파이썬 · node 쓰기 — 코드 안 따옴표 경로(변수에 담은 것도)를 고칠 대상으로
                paths = [p for p in re.findall(r"['\"]([^'\"\n]*\.(?:js|mjs|css|html|json|py|bat|plist|md|sh|command))['\"]", cmd) if p not in run]
            else:
                paths = [p for p in PATH_RE.findall(bare) if p not in run]
            kind = ("write" if pyw or WRITE_RE.search(bare) else "read" if READ_RE.search(bare) else None)
            if re.match(r"\s*git\b(?!\s+apply)", bare):
                kind = None if kind == "write" else kind               # git 명령은 저장소 파일을 손으로 고치는 것이 아니다
            if kind == "write" and not pyw and not WHOLE_RE.search(bare):
                # 리다이렉트 · tee · mv · cp 는 쓰는 자리만 — `git show x:a.js > /tmp/b` 의 a.js 는 읽는 쪽이다
                tg = re.findall(r"(?:>>?|\btee\s+(?:-a\s+)?)\s*([^\s&|;]+)", bare)
                tg += [m.split()[-1] for m in re.findall(r"\b(?:mv|cp)\s+[^;&|\n]+", bare)]
                paths = [p for p in paths if p in tg or any(t.endswith(p) for t in tg)]
            cds = re.findall(r"(?:^|[;&|]\s*)cd\s+([^\s;&|]+)", bare)
            if cds:   # `cd …/holdings && sed -i … js/home.js` — 상대 경로는 마지막 cd 자리에서 푼다(qa 11-24 놓침)
                d = os.path.expanduser(cds[-1].strip("'\""))
                cwd = os.path.normpath(d if os.path.isabs(d) else os.path.join(cwd, d))
        else:
            paths = [ti.get("file_path") or ti.get("notebook_path") or ""]
            kind = "read"                     # 도구로 읽기 · 고치기는 Claude Code 가 저절로 넣는다
        if not kind:
            return 0
        hit = []
        tops = worktrees(top) if paths else [top]
        for p in paths:
            r = rel(tops, cwd, p) if p else None
            if not r:
                continue
            for name, pats, body in rs:
                if name not in [h[0] for h in hit] and any(x.match(r) for x in pats):
                    hit.append((name, body, r, os.path.normpath(os.path.join(cwd, os.path.expanduser(p)))))
        if not hit:
            return 0
        try:
            st = json.load(open(sp, encoding="utf-8"))
        except Exception:
            st = {}
        give = []
        for name, body, r, ab in hit:
            if st.get(name) in ("seen", "given"):
                continue
            if kind == "read":
                st[name] = "seen"
            elif st.get(name) == "asked":
                st[name] = "given"            # 한 번 멈춘 뒤 다시 돌린 것 — 지나간다(계속 막지 않는다)
            else:
                st[name] = "asked"
                heads = [re.sub(r"^#+ ", "", l) for l in body.splitlines() if re.match(r"#{2,4} ", l)]
                tgt = ab if os.path.isfile(ab) else "그 폴더의 다른 파일(%s 는 아직 없음)" % r
                give.append("── `%s` — 이 명령이 고치는 %s 가 그 범위 ──\n먼저 읽기 도구(Read)로 `%s` 를 여십시오 — 한 줄(limit 1)만 열어도 그 룰이 저절로 들어옵니다.\n절: %s"
                            % (name, r, tgt, " / ".join(heads)))
        tmp = sp + ".%d" % os.getpid()
        json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, sp)
        if give:
            log(top, "멈춤 %s %s" % (sid, ", ".join(h[0] for h in hit)))
            # 한 번 멈춘다(재권님 「응 해」 11-24 19:2x) — 알림만 주면 그 명령이 돈 뒤에 읽혀 첫 고침 전에 룰을 못 봤다(qa 실제 세션 두 판).
            # 룰 파일을 cat 하라고 하면 출력이 잘려(4.5만 자) 그 범위 파일을 읽기 도구로 열게 한다 — 그러면 Claude Code 가 룰을 통째로 넣는다
            text = ("[경로 룰 · 한 번 멈춤] 명령줄로 바로 고치면 경로 조건 룰이 저절로 안 들어옵니다. 고치기 전에 아래대로 연 뒤 같은 명령을 다시 돌리면 지나갑니다"
                    "(이 세션에 룰 파일마다 한 번 · CLAUDE.md 「이 문서 밖에 있는 룰」).\n\n" + "\n\n".join(give))[:NOTE_MAX]
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": text}}, ensure_ascii=False))
    except Exception as e:
        log(top, "못 잼 (%s)" % type(e).__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
