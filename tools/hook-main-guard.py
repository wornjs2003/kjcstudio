# -*- coding: utf-8 -*-
"""PreToolUse(Bash · Edit · Write) 훅 — 메인 자리를 재권님 허락 없이 건드리지 못하게 막는다 (2026-10-01 지시).

재권님 말씀 그대로 — 「메인쪽은 내 허락없이 절대 건들면 안되는곳이야 안정장치를 여러개 만들어줘」.

2026-10-01 17:4x 에 한 세션이 시험 코드에서 `KJC_DB_PATH` 로 **메인 8765 의 market.db 를 쓰기 모드로** 가리켜
journal_mode 가 WAL 로 바뀌었다(-wal · -shm 생김). 그 세션은 메인 폴더에 있지도 않았다 — **경로만 적으면 어디서든
닿는다.** 그래서 폴더가 아니라 **명령·경로**를 본다.

**메인 자리란** — 메인 폴더(`/Users/kjc/work/KJCStudio`)와 서비스방(`/Users/kjc/service` · 외부접속이 보는 자리 ·
재권님 「범위에 넣어줘」)의 **데이터와 돌고 있는 것**이다. 소스 코드가 아니다(그것은 레인 룰이 본다).

    데이터        두 폴더의 holdings/market.db(+ -wal · -shm) · holdings/data/ · holdings/secrets.json · holdings/.kis-token-cache.json
    돌고 있는 것   8765 · 8764 프로세스 — 재시작 · 죽이기 · install.command · launchd 등록(kr.kjcstudio.kis-proxy · service-8764)
    서비스방 트리   git merge · checkout · reset · pull 로 그 폴더를 바꾸는 것 — 옮기기는 service-deploy.command 로만

**두 갈래로 본다 (2026-10-01 · 네 판째).**

    ① 경로가 **낱말 하나(인자)** 로 왔다  →  **읽기 명령 목록만 통과**, 그 밖은 막는다 (mv · tee · dd · sed -i … 처음부터)
    ② 경로가 **글 안**에 있다(메모 · python -c · heredoc)  →  **닿는 동사**(open w · connect ro 없음 · KJC_DB_PATH · 리다이렉트)만

처음 두 판은 글자만 있어도 막아서 — qa 가 실제 명령 4,772건을 재생하니 **막힘 122 중 오탐 112** 였다. 셋째 판은 「위험한
동사를 세어 막기」 라 라운드마다 동사가 하나씩 더 나왔다(mv · xargs kill — 홈페이지_정리 지적). 그래서 뒤집었다 —
**읽기 목록은 열 몇 개로 고정되고 안 는다.** 글 안의 경로까지 뒤집으면 1차 오탐이 되살아나므로 ②는 그대로 둔다.

**프로세스 쪽은 닫힌 집합이다** — 8765 는 보드 메모 · `--port 8765` · curl 에 다 들어가 통과 목록으로 못 가른다.
kill · pkill · killall · xargs kill · launchctl · install.command · service-deploy.command 를 보고, **이름으로 죽이는 것**
(`pkill -f kis_proxy` · `killall python3` · `holdings/server`)은 포트가 없어도 막는다 — 여섯 서버가 함께 죽는다.

**허락을 받았으면 그 명령 앞에 `KJC_MAIN_OK=1` 을 붙인다.** 훅은 지나가게 두면서 **`logs/main-ok.log` 에 한 줄 남긴다**
(시각 · cwd · 세션 · 명령 앞 120자). 허락을 받았는지는 기계가 못 보지만 **몇 번 썼는지는 센다** — `check-rules.py` 가
그 줄 수를 「봐야 할 자리」 로 낸다. **막는 메시지가 읽는 길을 알려 준다** — 그래야 표시로 도망가지 않는다.

**다섯째 판 (2026-10-02 · 재권님 「내가 말해주면 니거 만들어」) — 글과 명령을 먼저 가른다.** 넷째 판을 qa 가 재생하니 막힘 35 → 51 로
**오탐 22 가 새로 났다** — heredoc 몸통(`<<'PY' … PY`)과 `python3 -c "…"` 의 프로그램 글을 **줄마다 셸 명령으로 읽어** `p = "…"` 의
`p` · `"main-8765": …` · `#` 주석 · `(git` 서브셸이 「메인 경로를 인자로 받는 명령」 으로 잡혔다. 그래서 `segments()` 가
**(종류, 조각)** 을 내고, heredoc 몸통 · `-c` 뒤 프로그램 · 대입문 · 따옴표로 시작하는 줄은 **글**로 보아 ②(닿는 동사)만 건다.
①은 셸 조각에만. 그리고 `install.command $p` 처럼 **포트가 변수**면 「포트 없음(=전부)」 로 읽혀 막혔다 — 변수가 있으면 판정을 못 하는
것이지 전부가 아니므로 지나간다(실제 전부는 인자가 비어 있다).

**못 막는 것** — 변수에 담은 경로(`p=…; rm $p`) · API 로 쓰기(curl PUT 8765) · 세션 밖 사람 · 8765 자신 ·
**heredoc 으로 스크립트 파일에 적어 두고 그 파일을 돌리는 것**(몸통은 글이라 kill · launchctl 을 안 센다 — 돌리는 명령 쪽에서 잡힌다) ·
`install.command $p`(변수 포트).
막히면 종료 0 에 `permissionDecision: deny` 를 낸다 — 세션이 그 이유를 보고 재권님께 여쭙는다.
"""
import json
import os
import re
import shlex
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAIN = "/Users/kjc/work/KJCStudio"
SERVICE = "/Users/kjc/service"
ROOTS = (MAIN, SERVICE)
MAIN_DATA = ("holdings/market.db", "holdings/data/", "holdings/secrets.json", "holdings/.kis-token-cache.json")
OK_LOG = os.path.join(MAIN, "logs", "main-ok.log")
HOME = os.path.expanduser("~")
GUARD_PORTS = ("8765", "8764")
GUARD_LABELS = r"kr\.kjcstudio\.(kis-proxy|service-8764)(\.plist)?(?![\w-])"

# 경로를 인자로 받아도 되는 읽기 명령 — 이 목록만 통과한다. 제어어(for · if …)는 그 자체가 아무것도 안 한다.
READ_HEADS = {"cat", "head", "tail", "less", "more", "ls", "stat", "du", "wc", "md5", "md5sum", "shasum", "sha256sum",
              "file", "grep", "rg", "ugrep", "egrep", "fgrep", "diff", "cmp", "find", "git", "sqlite3", "sed", "awk", "jq",
              "cut", "sort", "uniq", "tr", "xxd", "hexdump", "strings", "od", "nl", "column", "realpath", "basename",
              "dirname", "readlink", "test", "[", "[[", "echo", "printf", "cp", "rsync", "scp", "tar", "lsof", "which",
              "for", "while", "if", "then", "else", "elif", "do", "done", "fi", "case", "esac", "select", "in"}
OUR_TOOLS = r"^(tools|holdings/tools|debugging)/[^/]+\.py$"      # 우리 검사 도구는 경로를 인자로 받아도 통과 (홈페이지_정리)
HOWTO = " 읽기만이면: sqlite3 -readonly <db> \"SELECT …\" · 파이썬 sqlite3.connect(\"file:<db>?mode=ro\", uri=True)."
READ_SQL = r"(?i)^\s*(select|with|explain|\.tables|\.schema|\.dump|\.indexes|pragma\s+\w+\s*;?\s*)(\s|$)"
WRITE_SQL = r"(?i)\b(pragma\s+\w+\s*=|insert|update|delete|drop|alter|create|vacuum|replace|attach|reindex)\b"
KILL_NAMES = r"kis_proxy|holdings/server|kr\.kjcstudio|python3?$|^python3?$|Python"


def _deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": "메인 자리입니다 — 재권님 허락 없이 건드리지 않습니다 (CLAUDE.md 「메인 자리는 재권님 허락 없이 건드리지 않는다」). "
        + reason + " 허락을 받았으면 명령 앞에 KJC_MAIN_OK=1 을 붙이십시오 — 그 사용은 logs/main-ok.log 에 남습니다."}}, ensure_ascii=False))


# ── 조각 나누기 — 따옴표 안의 ; | && 는 안 자른다. heredoc 몸통은 「글」 조각으로 따로 낸다 ──
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][\w-]*)\1")


def segments(cmd):
    """[(종류, 조각)] — 종류는 'sh'(셸 명령) 또는 'text'(heredoc 몸통)."""
    out, cur, q, i, pending = [], "", None, 0, []

    def flush():
        nonlocal cur
        if cur.strip():
            out.append(("sh", cur.strip()))
        cur = ""

    while i < len(cmd):
        c = cmd[i]
        if q:
            cur += c
            if c == "\\" and i + 1 < len(cmd):
                cur += cmd[i + 1]; i += 1
            elif c == q:
                q = None
        elif c in ("'", '"'):
            q = c; cur += c
        elif c == "\\" and i + 1 < len(cmd):
            cur += c + cmd[i + 1]; i += 1
        elif cmd.startswith("<<", i) and not cmd.startswith("<<<", i) and HEREDOC.match(cmd, i):
            m = HEREDOC.match(cmd, i)
            pending.append(m.group(2)); cur += m.group(0); i += len(m.group(0)); continue
        elif cmd.startswith("&&", i) or cmd.startswith("||", i):
            flush(); i += 1
        elif c == "\n":
            flush()
            for word in pending:              # 다음 줄부터 종료어 줄까지가 몸통
                j, body = i + 1, []
                while True:
                    k = cmd.find("\n", j)
                    line = cmd[j:] if k < 0 else cmd[j:k]
                    if line.strip() == word:
                        i = len(cmd) if k < 0 else k
                        break
                    body.append(line)
                    if k < 0:
                        i = len(cmd); break
                    j = k + 1
                out.append(("text", "\n".join(body)))
            pending = []
        elif c in ";|":
            flush()
        else:
            cur += c
        i += 1
    flush()
    return out


def words(seg):
    try:
        return shlex.split(seg, posix=True)
    except ValueError:
        return seg.split()


def head_of(ws):
    """환경변수 접두 · sudo · 경로 접두를 뗀 첫 낱말과 나머지."""
    i = 0
    while i < len(ws) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", ws[i]):
        i += 1
    while i < len(ws) and ws[i] in ("sudo", "nohup", "time", "env", "exec", "command"):
        i += 1
    return (os.path.basename(ws[i]) if i < len(ws) else ""), (ws[i + 1:] if i < len(ws) else [])


def norm(s):
    return s.replace("~/", HOME + "/").replace("$HOME/", HOME + "/").replace("${HOME}/", HOME + "/")


def is_main_path(tok, cwd):
    """이 낱말(경로 하나)이 메인 데이터인가. 경계를 본다 — 다른 폴더 안의 같은 꼬리는 아니다."""
    t = norm(tok).strip("'\"")
    t = re.sub(r"^file:", "", t).split("?")[0]
    if not t or "$" in t:
        return ""
    t = os.path.normpath(t if t.startswith("/") else os.path.join(cwd or "/", t))
    for root in ROOTS:
        for p in MAIN_DATA:
            full = os.path.normpath(os.path.join(root, p))
            if t == full or t.startswith(full + "/") or (p.endswith("market.db") and t.startswith(full)):
                return ("서비스방 " if root == SERVICE else "") + p
    return ""


def is_service_tree(tok, cwd):
    t = norm(tok).strip("'\"")
    if not t or "$" in t:
        return False
    t = os.path.normpath(t if t.startswith("/") else os.path.join(cwd or "/", t))
    return t == SERVICE or t.startswith(SERVICE + "/")


PATH_RE = r"(?<![\w./$-])((?:~|\$HOME|\$\{HOME\}|/|\./|holdings/)[^\s\"'();|&<>]*)"


def find_main_in(seg, cwd):
    """조각 글 안에서 메인 데이터 경로를 찾는다 (경계 있음)."""
    for m in re.finditer(PATH_RE, seg):
        p = is_main_path(m.group(1), cwd)
        if p:
            return p, m
    return "", None


DBPATH_TEXT = r"(?m)^\s*(?:os\.environ\[\s*[\"']KJC_DB_PATH[\"']\s*\]|KJC_DB_PATH|export\s+KJC_DB_PATH)\s*[=:]\s*\\?[\"']?([^\s\"'\\,)]+)"


def check_text(text, cwd, argv_hit=""):
    """② 글 안의 메인 경로 — 닿는 동사가 바로 붙은 것만. 경로가 여럿이면 전부 본다.
    argv_hit 는 `python3 - <메인 경로> <<'PY'` 처럼 **인자로 받아 sys.argv 로 쓰는** 경우 — 몸통에서 sys.argv 를
    쓰기로 여는지만 본다(qa 6차 — 개발1 이 ro 로 바르게 읽는데 ①에 막혔다)."""
    # KJC_DB_PATH 를 가리키는 **대입** 만 — 줄머리 `KJC_DB_PATH=` · `os.environ["KJC_DB_PATH"] =` · yaml `KJC_DB_PATH:`.
    # 메모 글에 그 낱말이 들어간 것(보드 카드 · 패치 글)은 안 막는다 — 「일은 보드에서 시작한다」 를 막았었다 (qa 6차)
    for mm in re.finditer(DBPATH_TEXT, text):
        if is_main_path(mm.group(1), cwd):
            return "KJC_DB_PATH 가 메인 8765 의 market.db 를 가리킵니다 — 2026-10-01 에 이것으로 journal_mode 가 바뀌었습니다."
    if argv_hit:
        for line in text.split("\n"):
            if "sys.argv" in line and re.search(r"\bconnect\s*\(", line) and "mode=ro" not in line:
                return "파이썬 connect() 로 인자로 받은 메인 DB(%s)를 쓰기 가능하게 엽니다." % argv_hit + HOWTO
            if re.search(r"\bopen\s*\(\s*sys\.argv\[\d+\]\s*,\s*[\"'][rb]*[wax+]", line):
                return "파이썬 open() 으로 인자로 받은 메인 데이터(%s)를 쓰기 모드로 엽니다." % argv_hit
    for m in re.finditer(PATH_RE, text):
        hit = is_main_path(m.group(1), cwd)
        if not hit:
            continue
        before, after = text[:m.start()], text[m.end():]
        ls = before.rfind("\n") + 1
        le = text.find("\n", m.end())
        line = text[ls:] if le < 0 else text[ls:le]
        if re.search(r"\bopen\s*\(\s*[rb]?\\?[\"']?$", before) and re.match(r"[\"']?\\?[\"']?\s*,\s*\\?[\"']?[rwax+b]*[wax+]", after):
            return "파이썬 open() 으로 메인 데이터(%s)를 쓰기 모드로 엽니다." % hit
        if re.search(r"\bconnect\s*\(\s*[\"']?(file:)?\\?[\"']?$", before) and "mode=ro" not in line:
            return "파이썬 connect() 로 메인 DB(%s)를 쓰기 가능하게 엽니다." % hit + HOWTO
        if re.search(r"\b(remove|unlink|rename|replace|rmtree|write_text|write_bytes|copyfile|copy2?|move)\s*\(\s*[rb]?\\?[\"']?$", before):
            return "파이썬 호출로 메인 데이터(%s)를 바꾸는 명령입니다." % hit
    return ""


def check_segment(seg, cwd, prev_seg, prev_hit):
    ws = words(seg)
    head, args = head_of(ws)
    if head in ("python3", "python") and "-c" in args:        # `-c` 뒤는 프로그램 글이다 — ①이 아니라 ②
        k = args.index("-c")
        r = check_text(" ".join(args[k + 1:]), cwd)
        if r:
            return r
        args = args[:k]
    if head in ("python3", "python") and args and args[0] == "-" and HEREDOC.search(seg):
        # `python3 - <경로> <<'PY'` — 경로는 프로그램의 argv 다. 몸통(다음 글 조각)에서 sys.argv 쓰기만 본다
        argv_hit = next((is_main_path(a, cwd) for a in args[1:] if not a.startswith("-") and "<" not in a and is_main_path(a, cwd)), "")
        return ("", argv_hit)
    hit, m = find_main_in(seg, cwd)

    # ── ① 경로가 낱말 하나(인자)로 왔다 → 읽기 명령만 통과 ──
    # `dd of=<경로>` · `--out=<경로>` 처럼 `키=경로` 꼴도 인자다
    # `-`(표준입력) · `-x` 옵션은 경로가 아니다 — cwd 가 메인 데이터 폴더면 `-` 가 그 안의 파일로 풀려 막혔다 (qa 6차 재생)
    # `<<EOF` 같은 heredoc 표식 · 리다이렉트 조각도 경로가 아니다 (같은 재생 — cwd 가 docs 폴더라 `<<EOF` 가 그 안 파일로 풀렸다)
    arg_hits = [a for a in args if (not a.startswith("-") and "<" not in a and ">" not in a and is_main_path(a, cwd))
                or ("=" in a and is_main_path(a.split("=", 1)[1], cwd))]
    if arg_hits:
        ours = head in ("python3", "python") and args and re.match(OUR_TOOLS, args[0].lstrip("./"))
        # `code -r <경로>` 는 세션이 쓰는 것이 아니라 재권님 VS Code 에 열어 손에 넘기는 것 — 열기만이라 통과 (2026-10-07 지시
        # 「코드에서 열리게 해줘」 · 작업우선순위 검토: 안 열어 주면 KJC_MAIN_OK=1 을 습관처럼 붙여 그 표시가 빈다)
        # 좁힌 것 둘(qa 손 시험) — sudo 로 열면 저장할 때 주인이 root 로 바뀔 수 있다 · DB 같은 이진 파일은 「글 파일」 이 아니다
        ours = ours or (head == "code" and ("-r" in args or "--reuse-window" in args)
                        and not re.match(r"\s*(sudo|doas)\b", seg)
                        and not any(re.search(r"\.(db|sqlite3?)(-wal|-shm|-journal)?$", a) for a in arg_hits))
        if head not in READ_HEADS and not ours:
            return ("%s 가 메인 데이터(%s)를 인자로 받습니다 — 읽기 명령(cat · ls · grep · git · sqlite3 -readonly …)이 아니면 막습니다."
                    % (head or "(이 명령)", hit)) + HOWTO
        if head in ("cp", "rsync", "scp") and is_main_path(args[-1], cwd):
            return "%s 의 도착지가 메인 데이터(%s)입니다." % (head, hit)
        if head == "rsync" and "--remove-source-files" in args:
            return "rsync --remove-source-files 는 메인 데이터(%s)를 원래 자리에서 지웁니다." % hit
        if head == "sed" and any(a == "-i" or a.startswith("-i") for a in args):
            return "sed -i 로 메인 데이터(%s)를 고칩니다." % hit
        if head == "tar" and args and re.match(r"^-?[a-zA-Z]*x", args[0]):
            return "tar 로 메인 데이터(%s) 자리에 풀어 넣습니다." % hit
        if head == "find" and re.search(r"-delete\b|-exec\s+(rm|mv|truncate|chmod|sed)\b", seg):
            return "find 로 메인 데이터(%s)를 지우거나 바꾸는 명령입니다." % hit
        if head == "sqlite3" and "-readonly" not in args:
            # 리다이렉트(2>&1 · > x)는 질의가 아니다 — 끝의 빈 문장(;)도 (qa 2차 재생 오탐)
            sql = " ".join(a for a in args if not is_main_path(a, cwd) and not a.startswith("-")
                           and not re.match(r"^\d*[<>]", a) and a != "&")
            if not sql.strip():
                return "sqlite3 로 메인 DB(%s)를 대화형으로 엽니다." % hit + HOWTO
            stmts = [x for x in sql.split(";") if x.strip()]
            if any(not re.match(READ_SQL, x) or re.search(WRITE_SQL, x) for x in stmts):
                return "sqlite3 로 메인 DB(%s)에 읽기가 아닌 질의를 보냅니다." % hit + HOWTO

    # 리다이렉트는 머리와 무관하다
    if hit:
        for r in re.finditer(r"(?<![<\w])>{1,2}\s*[\"']?([^\s\"'|;&]+)", seg):
            if is_main_path(r.group(1), cwd):
                return "메인 데이터(%s)에 리다이렉트로 쓰는 명령입니다." % hit

    # ── ② 글 안에 든 경로 → 닿는 동사가 붙은 것만 ──
    if hit and not arg_hits:
        for a in args:
            if re.match(r"^--(db|db-path|database|out|output)=", a) and is_main_path(a.split("=", 1)[1], cwd):
                return "메인 데이터(%s)를 쓰기 인자로 넘기는 명령입니다." % hit
        r = check_text(seg, cwd)
        if r:
            return r

    # ── 프로세스 · 등록 — 닫힌 집합 ──
    if head == "install.command" and "--check" not in args:
        nums = [a for a in args if re.fullmatch(r"\d{4}", a)]
        has_var = any("$" in a for a in args)
        if (not nums and not has_var) or any(n in GUARD_PORTS for n in nums):
            return "install.command 을 포트 없이(=전부) 또는 8765 · 8764 로 돌리면 메인·서비스방 서버가 재시작됩니다."
    if head == "service-deploy.command":
        return "service-deploy.command 는 서비스방을 바꾸고 8764 를 다시 띄웁니다 — 재권님 지시로만 돌립니다."
    if head == "launchctl" and args and args[0] in ("unload", "bootout", "kickstart", "stop", "start", "kill", "remove", "disable"):
        if re.search(GUARD_LABELS, seg):
            return "launchctl 로 메인(kr.kjcstudio.kis-proxy) 또는 서비스방(kr.kjcstudio.service-8764) 서버를 내리거나 올리는 명령입니다."
    if head in ("kill", "pkill", "killall") or (head == "xargs" and re.search(r"\b(kill|pkill)\b", seg)):
        joined = " ".join(args) + " " + (prev_seg if head == "xargs" else "")
        if any(p in joined for p in GUARD_PORTS) or re.search(GUARD_LABELS, joined):
            return "8765 · 8764 프로세스를 죽이는 명령입니다."
        if head == "pkill" and "-f" in args and any(re.search(KILL_NAMES, a) for a in args if a != "-f") \
           and not re.search(r"--port\s*\d{4}|\b87(6[6-9]|7\d)\b", joined):
            return "이름으로 kis_proxy 를 죽이면 여섯 서버가 함께 죽습니다 — 포트를 적으십시오."
        if head == "killall" and any(re.search(r"^[Pp]ython3?$", a) for a in args):
            return "killall python3 은 메인 8765 · 서비스방 8764 까지 죽입니다."
    if head == "xargs" and re.search(r"\b(rm|mv|truncate|chmod)\b", seg) and prev_hit:
        return "xargs 로 메인 데이터(%s)를 지우거나 바꾸는 명령입니다." % prev_hit
    # ── 서비스방 작업 트리를 바꾸는 git ──
    if head == "git":
        tree = cwd
        if "-C" in args:
            i = args.index("-C")
            if i + 1 < len(args):
                tree = norm(args[i + 1]).strip("'\"")
        sub = next((a for a in args if not a.startswith("-") and a != tree), "")
        if sub in ("merge", "checkout", "switch", "reset", "pull", "clean", "restore", "rebase", "cherry-pick", "revert", "stash") \
           and is_service_tree(tree, cwd):
            return "서비스방(/Users/kjc/service)의 작업 트리를 바꾸는 git 명령입니다 — 옮기기는 service-deploy.command 로, 재권님 지시로."
    return ""


def check_bash(cmd, cwd):
    if "KJC_MAIN_OK=1" in cmd:
        try:
            os.makedirs(os.path.dirname(OK_LOG), exist_ok=True)
            with open(OK_LOG, "a", encoding="utf-8") as fp:
                fp.write("%s\t%s\t%s\t%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), cwd or "",
                                               os.environ.get("CLAUDE_CODE_SESSION_ID", "")[:8],
                                               " ".join(cmd.split())[:120]))
        except Exception:
            pass
        return ""
    text = norm(cmd)
    cur = cwd or os.getcwd()
    prev_hit, prev_seg, argv_hit = "", "", ""
    for kind, seg in segments(text):
        if kind == "sh":
            seg = re.sub(r"^(?:[A-Za-z_]\w*=)?\$?\(\s*", "", seg).lstrip("{ ").strip()   # NAME=$(cmd … · (cmd … · { cmd
            if not seg or seg.startswith("#"):
                continue
            if re.match(r"^[A-Za-z_][\w.]*\s+=\s", seg) or seg[0] in "\"'{}[]),":       # 대입문 · 자료 줄 — 글이다
                kind = "text"
        if kind == "text":
            r = check_text(seg, cur, argv_hit)
            argv_hit = ""
            if r:
                return r
            prev_hit, prev_seg = find_main_in(seg, cur)[0], seg
            continue
        ws = words(seg)
        head, args = head_of(ws)
        # KJC_DB_PATH=<메인> 환경변수 접두 · export — 셸에서 실제로 가리키는 꼴만 (글 안의 낱말은 check_text 가 가른다)
        for w in ws[:len(ws) - len(args)] + (args if head == "export" else []):
            if w.startswith("KJC_DB_PATH=") and is_main_path(w.split("=", 1)[1], cur):
                return "KJC_DB_PATH 가 메인 8765 의 market.db 를 가리킵니다 — 2026-10-01 에 이것으로 journal_mode 가 바뀌었습니다."
        if head == "cd":
            tgt = norm(args[0]).strip("'\"") if args else HOME
            cur = os.path.normpath(tgt if tgt.startswith("/") else os.path.join(cur, tgt))
            continue
        r = check_segment(seg, cur, prev_seg, prev_hit)
        if isinstance(r, tuple):            # `python3 - <경로> <<'PY'` — 몸통에서 본다
            argv_hit = r[1]
            r = ""
        if r:
            return r
        prev_hit = find_main_in(seg, cur)[0]
        prev_seg = seg
    return ""


def check_edit(path):
    if not path:
        return ""
    p = is_main_path(path, os.getcwd())
    return "메인 데이터 파일(%s)을 직접 고치는 것입니다." % p if p else ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    tool = data.get("tool_name")
    inp = data.get("tool_input") or {}
    cwd = data.get("cwd") or os.getcwd()
    if tool == "Bash":
        reason = check_bash(inp.get("command") or "", cwd)
    elif tool in ("Edit", "Write"):
        reason = check_edit(inp.get("file_path") or "")
    else:
        reason = ""
    if reason:
        _deny(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
