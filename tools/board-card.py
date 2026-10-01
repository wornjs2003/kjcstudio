# -*- coding: utf-8 -*-
"""보드 카드 — 「일은 보드에서 시작한다」(2026-10-01 지시) 의 손발.

    python3 tools/board-card.py "<카드 제목 일부>" "<붙일 줄>" [--sub "<하위>"] [--done "<하위 일부>"]
    python3 tools/board-card.py --new "[갈래] 무엇" "<첫 줄>" [--todo]     담당 라벨은 자동
    python3 tools/board-card.py --mine                                     내 doing 카드 (0 있음 · 1 없음 · 2 못 봄)
    python3 tools/board-card.py --gate edit|commit                         훅용 — 없으면 1, 못 봤으면 0
    python3 tools/board-card.py --commit [--dry]                           post-commit 용 — HEAD 를 카드에 적는다
    어느 명령이든 --label <담당>                                            세션 이름을 못 얻을 때 손으로 (= KJC_BOARD_LABEL)

**쓰는 곳은 하나다** — `KJC_BOARD_URL`(기본 8765). 세션 폴더 서버에 쓰면 넘기기가 안 켜진
서버는 자기 폴더로 가므로 기본값을 그대로 둔다.

**담당 라벨 = 세션 이름에서 『주식페이지_』 를 뗀 것.** 표를 두지 않는다 —
`projects/data/config.js` 가 담당 목록을 일부러 안 두는 것과 같은 이유다(복제).
세션 이름은 Herdr 가 아는 창 제목(`HERDR_PANE_ID`)에서 얻고, 없으면 기록의 `/rename` 을 본다.

**못 봤다 와 카드 0개 를 가른다.** 연결 거부 · 타임아웃 · 503 · 5xx · JSON 아님은 전부
「못 봤다」(종료 2)이고 훅은 그때 막지 않는다 — 보드가 단일 장애점이 됐기 때문이다.
"""
import glob
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BOARD = (os.environ.get("KJC_BOARD_URL") or "http://127.0.0.1:8765").rstrip("/")
DOC = BOARD + "/api/board/doc/projects"
TIMEOUT = 1.5           # 훅이 편집마다 돈다 — 보드 읽기 실측 8.6ms 라 넉넉하다


class Unseen(Exception):
    """보드를 못 봤다 — 카드 0개와 다르다."""


# ── 세션 이름 → 담당 라벨 ───────────────────────────────────
def session_name():
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    pane = os.environ.get("HERDR_PANE_ID", "")
    if sid or pane:
        # **세션 UUID 로 먼저 맞춘다.** `HERDR_PANE_ID` 는 세션이 시작될 때 박힌 값이라
        # 창·탭을 재배치하면 낡는다 — 2026-10-01 에 주식페이지_개발3 이 `w5:p1` 을 들고 있었는데
        # 목록에는 `w2:p5` 였다. `agent_session.value` 는 `CLAUDE_CODE_SESSION_ID` 와 1:1 이라 안 낡는다.
        try:
            out = subprocess.run(["herdr", "agent", "list"], capture_output=True,
                                 text=True, timeout=TIMEOUT).stdout
            agents = json.loads(out)["result"]["agents"]
            title = lambda a: (a.get("terminal_title_stripped") or a.get("name") or "").strip()
            for a in agents:
                if sid and (a.get("agent_session") or {}).get("value") == sid:
                    return title(a)
            for a in agents:
                if pane and a.get("pane_id") == pane:
                    return title(a)
            # 3순위 cwd — 같은 폴더에 둘이 앉으면(메인 폴더) 못 가르므로 하나일 때만
            here = os.path.realpath(os.getcwd())
            same = [a for a in agents if os.path.realpath(a.get("cwd") or "") == here]
            if len(same) == 1:
                return title(same[0])
        except Exception:
            pass
    if not sid:
        return ""
    pat = re.compile(r"Session renamed to: ([가-힣A-Za-z0-9_\-. ]{1,30})")
    name = ""
    for path in glob.glob(os.path.expanduser("~/.claude/projects/*/%s.jsonl" % sid)):
        try:
            with io.open(path, encoding="utf-8", errors="ignore") as fp:
                for line in fp:
                    if "Session renamed to:" not in line:
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if row.get("type") != "system":
                        continue
                    m = pat.search(str(row.get("content", "")))
                    if m:
                        name = m.group(1).strip()
        except OSError:
            pass
    return name


FORCED_LABEL = ""   # --label 로 준 것. 환경변수 KJC_BOARD_LABEL 과 같다 — 위가 다 막혔을 때 손으로


def label_of(name):
    forced = FORCED_LABEL or os.environ.get("KJC_BOARD_LABEL", "").strip()
    return forced or name.replace("주식페이지_", "").strip()


# ── 보드 읽기 · 쓰기 ─────────────────────────────────────────
def read():
    try:
        with urllib.request.urlopen(DOC, timeout=TIMEOUT) as r:
            if r.status != 200:
                raise Unseen("HTTP %d" % r.status)
            body = json.load(r)
    except urllib.error.HTTPError as e:
        raise Unseen("HTTP %d" % e.code)
    except Unseen:
        raise
    except Exception as e:                  # 연결 거부 · 타임아웃 · JSON 아님
        raise Unseen(type(e).__name__)
    if not isinstance(body, dict) or "data" not in body:
        raise Unseen("응답 모양이 다르다")
    return body["data"], body.get("updatedAt")


def tasks(doc):
    pj = doc.get("projects") or []
    active = doc.get("activeId")
    for p in pj:
        if p.get("id") == active:
            return p.setdefault("tasks", [])
    return pj[0].setdefault("tasks", []) if pj else []


def write(doc, at):
    req = urllib.request.Request(DOC, data=json.dumps({"data": doc, "updatedAt": at}).encode(),
                                 headers={"Content-Type": "application/json"}, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status
    except urllib.error.HTTPError as e:
        if e.code == 409:
            return 409
        raise Unseen("HTTP %d" % e.code)
    except Exception as e:
        raise Unseen(type(e).__name__)


def apply(change):
    """읽고 → 고치고 → 쓰기. 409 면 한 번 다시 읽어 다시 고친다."""
    for _ in range(2):
        doc, at = read()
        change(doc)
        if write(doc, at) != 409:
            return
    raise Unseen("409 두 번 — 남이 계속 쓰고 있다")


LABELS = re.compile(r"^\s*\[([^\]]+)\]\s*\[([^\]]+)\]")


def mine(doc, label):
    out = []
    for t in tasks(doc):
        if t.get("column") != "doing":
            continue
        m = LABELS.match(t.get("text", ""))
        if m and m.group(2).strip() == label:
            out.append(t)
    return out


def now():
    return time.strftime("%H:%M")


# ── 명령들 ───────────────────────────────────────────────────
def cmd_note(key, line, sub, done):
    def change(doc):
        hits = [t for t in tasks(doc) if key in t.get("text", "")]
        if len(hits) != 1:
            sys.exit("카드 %d개 걸림 — 더 좁혀서: %s" % (len(hits), key))
        t = hits[0]
        if line:
            t["memo"] = (t.get("memo") or "").rstrip() + "\n  %s %s" % (now(), line)
        if sub:
            t.setdefault("subs", []).append({"id": "s%d" % int(time.time() * 1000), "done": False, "text": sub})
        if done:
            for s in t.get("subs", []):
                if done in s["text"]:
                    s["done"] = True
                    if not s["text"].startswith("[됨]"):
                        s["text"] = "[됨] " + s["text"]
    apply(change)
    print("보드 저장됨", now())


def cmd_new(text, line, todo):
    label = label_of(session_name())
    if not label:
        sys.exit("세션 이름을 못 얻어 담당 라벨을 못 붙인다 — 보드 문제가 아니다. `--label <담당>` 으로 주십시오")
    m = re.match(r"^\s*(\[[^\]]+\])\s*(.*)$", text)
    if not m:
        sys.exit("카드 제목은 「[갈래] 무엇」 모양이어야 한다")
    full = "%s [%s] %s" % (m.group(1), label, m.group(2).strip())

    def change(doc):
        ms = int(time.time() * 1000)
        tasks(doc).append({"id": "t%dr" % ms, "text": full, "column": "todo" if todo else "doing",
                           "subs": [], "links": [], "due": "", "priority": "normal", "createdAt": ms,
                           "memo": "  %s %s" % (now(), line) if line else ""})
    apply(change)
    print("카드 만듦:", full)


def cmd_mine(gate=None):
    label = label_of(session_name())
    if not label:
        # 「보드가 안 답한다」(밖의 사정 → 통과) 와 「이름을 못 얻었다」(우리 도구의 결함) 를 가른다
        # (2026-10-01 · 홈페이지_정리 지적). 뒤쪽까지 통과시키면 고장이 영영 안 드러난다.
        # 세션 밖(사람이 터미널에서)은 세션 id 자체가 없으므로 통과한다.
        if not os.environ.get("CLAUDE_CODE_SESSION_ID") and not os.environ.get("HERDR_PANE_ID"):
            print("세션 밖(사람 손)이라 카드 검사를 건너뛴다")
            return 0 if gate else 2
        print("✗ 세션 이름을 못 얻었다 — **보드 문제가 아니라 도구 쪽 결함이다.** 카드가 안 생기는 세션이 되므로 막는다.")
        print("   `herdr agent list` 의 agent_session.value 와 `echo $CLAUDE_CODE_SESSION_ID` 를 대보십시오.")
        print("   넘기려면 `--label <담당>` 또는 KJC_BOARD_LABEL=<담당> — 그리고 개념정의에 알린다")
        return 1 if gate else 2
    try:
        doc, _ = read()
    except Unseen as e:
        print("보드를 못 봤다(%s) — 막지 않는다. 카드는 보드가 돌아오면 적는다" % e)
        return 0 if gate else 2
    cards = mine(doc, label)
    if not cards:
        print("[%s] 의 doing 카드가 보드에 없다 — 카드 먼저:" % label)
        print("    python3 tools/board-card.py --new \"[갈래] 무엇\" \"무엇을 왜\"")
        return 1
    for t in cards:
        print("  ·", t["text"])
    return 0


def cmd_commit(dry):
    label = label_of(session_name())
    g = lambda *a: subprocess.run(["git"] + list(a), capture_output=True, text=True).stdout.strip()
    h, subject, branch = g("rev-parse", "--short", "HEAD"), g("log", "-1", "--format=%s"), g("rev-parse", "--abbrev-ref", "HEAD")
    if not label:
        print("  보드: 세션 이름을 못 얻어 카드에 못 적었다 (%s)" % h)
        return 0
    words = lambda s: {w for w in re.split(r"[\s·—\-:,.()「」『』\[\]/]+", s) if len(w) >= 2}
    sw = words(subject)

    picked = {}

    def change(doc):
        cards = mine(doc, label)
        if not cards:
            raise Unseen("[%s] 의 doing 카드가 없다" % label)
        best, score = None, 0
        for t in cards:
            body = LABELS.sub("", t["text"])
            n = len(words(body) & sw)
            if n > score:
                best, score = t, n
        guess = ""
        if score < 2:
            best = max(cards, key=lambda t: t.get("createdAt", 0))
            guess = "(추정) "
        picked["text"] = best["text"]
        picked["guess"] = guess
        best["memo"] = (best.get("memo") or "").rstrip() + "\n  %s %s커밋 %s %s · %s" % (now(), guess, h, subject, branch)

    if dry:
        try:
            doc, _ = read()
            change(doc)
            print("  (시험) 적을 카드:", picked["guess"] + picked["text"])
        except Unseen as e:
            print("  (시험) 보드에 못 적는다:", e)
        return 0
    try:
        apply(change)
        print("  보드: %s%s ← %s" % (picked["guess"], picked["text"], h))
    except Unseen as e:
        print("  보드에 못 적었다(%s) — 돌아오면 손으로: python3 tools/board-card.py \"<카드>\" \"커밋 %s %s · %s\"" % (e, h, subject, branch))
    return 0


def main(argv):
    global FORCED_LABEL
    if "--label" in argv:
        i = argv.index("--label")
        FORCED_LABEL = argv[i + 1].strip() if i + 1 < len(argv) else ""
        argv = argv[:i] + argv[i + 2:]
    if not argv or argv[0] in ("--help", "-h"):
        print(__doc__)
        return 0
    if argv[0] == "--mine":
        return cmd_mine()
    if argv[0] == "--gate":
        return cmd_mine(gate=argv[1] if len(argv) > 1 else "edit")
    if argv[0] == "--commit":
        return cmd_commit("--dry" in argv)
    if argv[0] == "--new":
        text = argv[1] if len(argv) > 1 else ""
        rest = [a for a in argv[2:] if not a.startswith("--")]
        return cmd_new(text, rest[0] if rest else "", "--todo" in argv) or 0
    key = argv[0]
    line = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else ""
    sub = done = None
    for i, x in enumerate(argv):
        if x == "--sub":
            sub = argv[i + 1]
        if x == "--done":
            done = argv[i + 1]
    try:
        cmd_note(key, line, sub, done)
    except Unseen as e:
        sys.exit("보드를 못 봤다: %s" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
