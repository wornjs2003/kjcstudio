#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""홈페이지 Claude 창의 「업무지시」 — 서버가 작업우선순위 창에 글을 넣고 그 창의 답을 돌려준다 (2026-11-23).

재권님 「홈페이지에 연결된 클로드와 너랑 동기화해서 홈페이지 보면서 업무지시 가능하게 만들수있나?」 → (나) 바로 전함 「나 로 해서 확인해봐」 ·
「외부접속도 같이 받게」(11-18 · 개념정의 창) → 「홈페이지랑 연결된 클로드랑 너랑 연결하는거 진행안됬나?」(11-23 13:06) → 안에 「응 해줘봐」(13:1x).

어떻게 도나
  화면(assets/js/claude-rail.js · 「업무지시」 단추를 켠 글) → POST /api/claude/order → submit() → 뒤에서 _work()
    ① herdr 창 목록에서 이름이 TARGET_LABEL 인 창을 찾는다(창 id 는 그때 센다 — 재시작마다 바뀐다)
    ② 그 창이 물음에 막혀(blocked) 있으면 「지금 못 받음」 · 일하는 중이면 쉴 때까지 WAIT_IDLE_SEC 만큼 기다린다
    ③ `herdr agent prompt <창> "[홈페이지 지시] (#번호 · 내부/외부접속 · 시각) 글"` → 끝날 때까지 기다린다
    ④ 답은 그 세션의 대화 기록(~/.claude/projects/*/<세션 id>.jsonl)에서 #번호가 든 글 뒤의 마지막 답 글을 읽는다
       — 창 화면 글은 상태 줄 · 입력 칸이 섞여 기록을 먼저 쓴다. 못 찾으면 창 화면 끝 몇 줄을 「(창 화면에서 읽음)」 으로
  화면은 GET /api/claude/order?id=… 로 상태를 받는다 — 다시 묻는 간격은 서버가 낸 pollMs(「화면은 서버에 주기로 묻지 않는다」).
  한 번에 기다리는 요청으로 하지 않는 까닭 — 답이 몇 분 걸릴 수 있는데 외부접속(Cloudflare)은 100초에 끊는다.

지키는 것
  - **보내는 자리는 ORDER_PORTS 둘뿐**(개발 서버 · 메인) — 세션 서버에서 시험하다 작업우선순위 창에 글이 들어가지 않게
  - **한 번에 하나** — 두 서버(8765 · 8764)가 함께 받아도 LOCK_FILE 로 하나만 간다
  - 기록 — logs/claude-order.log 한 줄(시각 · 내부/외부접속 · 포트 · 결과 · 글). 오류 문구는 safe_message
  - 글은 한 줄로 넣는다(줄바꿈은 「 / 」) — 창 입력 칸에서 줄바꿈이 보내기로 읽힐 수 있다
"""

import fcntl
import glob
import json
import os
import shutil
import subprocess
import threading
import time
import uuid

from secrets_guard import safe_message

TARGET_LABEL = "작업우선순위"                # 지시를 받는 창 — herdr 창 이름(label)
MARK = "[홈페이지 지시]"                     # 글머리 — 작업우선순위가 이것을 재권님 말씀으로 받는다(11-18 재권님 답)
ORDER_PORTS = (8765, 8764)                  # 보내는 자리 — 개발 서버 · 메인(외부접속이 보는 자리)
PATH_ADD = ["/opt/homebrew/bin", os.path.expanduser("~/.local/bin"), "/usr/local/bin"]   # launchd PATH 에 herdr 가 없다
MAX_TEXT = 2000                             # 글자 — 지시 한 번
WAIT_IDLE_SEC = 180                         # 그 창이 일하는 중이면 쉴 때까지 기다리는 한도
WAIT_DONE_SEC = 900                         # 넣은 뒤 답이 끝날 때까지 기다리는 한도
POLL_MS = 3000                              # 화면이 상태를 다시 묻는 간격 — 화면은 이 값을 받아 쓴다
KEEP_JOBS = 20                              # 지난 지시 몇 개를 기억하나(화면이 늦게 물어도 답을 받게)
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(REPO, "logs", "claude-order.log")
LOCK_FILE = "/tmp/kjc-claude-order.lock"     # 두 서버 사이 「한 번에 하나」

_lock = threading.Lock()
_jobs = {}            # id → 상태 묶음
_order = []           # 들어온 차례(오래된 것을 지우려고)


class Busy(Exception):
    """앞 지시가 아직 돌고 있다."""


class NotHere(Exception):
    """이 서버는 지시를 보내지 않는 자리다."""


def _herdr():
    p = shutil.which("herdr", path=os.pathsep.join(PATH_ADD + [os.environ.get("PATH", "")]))
    if not p:
        raise RuntimeError("herdr 를 못 찾았습니다(PATH)")
    return p


def _run(args, timeout):
    r = subprocess.run([_herdr(), *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def _pane():
    """(창 id, 상태, 세션 기록 id) — 이름이 TARGET_LABEL 인 창이 하나가 아니면 RuntimeError."""
    code, out, err = _run(["pane", "list"], 10)
    if code != 0:
        raise RuntimeError("herdr 창 목록을 못 읽었습니다 — %s" % (err or out)[:120])
    panes = [p for p in json.loads(out)["result"]["panes"] if (p.get("label") or "").strip() == TARGET_LABEL]
    if len(panes) != 1:
        raise RuntimeError("%s 창이 %d개입니다 — 하나여야 보냅니다" % (TARGET_LABEL, len(panes)))
    p = panes[0]
    return p["pane_id"], p.get("agent_status") or "unknown", (p.get("agent_session") or {}).get("value") or ""


def _log(job):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s\t%s\t%s\t%s\t%s\t%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), job["id"], job["origin"], job["port"],
                                                job["state"] + ("(" + job["error"] + ")" if job.get("error") else ""),
                                                job["text"].replace("\n", " / ")))
    except Exception as e:
        print("[업무지시] 기록 못 씀 — %s" % safe_message(e, 80), flush=True)


def _text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text") or "" for c in content if isinstance(c, dict) and c.get("type") == "text")
    return ""


def _answer_from_log(sid, tag):
    """그 세션 기록에서 tag(#번호)가 든 사람 글 뒤의 마지막 답 글. 못 찾으면 None."""
    files = glob.glob(os.path.expanduser("~/.claude/projects/*/%s.jsonl" % sid)) if sid else []
    if not files:
        return None
    seen, last = False, None
    with open(max(files, key=os.path.getmtime), encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            msg = e.get("message") or {}
            ut = _text_of(msg.get("content")) if e.get("type") == "user" else ""   # 도구 결과 줄은 글이 비어 사람 글로 안 친다
            if ut:
                if tag in ut:
                    seen, last = True, None
                elif seen and last:
                    break                     # 그 뒤 다른 사람 글이 왔다 — 거기까지가 이 지시의 답
            elif seen and e.get("type") == "assistant":
                t = _text_of(msg.get("content")).strip()
                if t:
                    last = t
    return last


def _answer_from_screen(pane):
    code, out, _ = _run(["agent", "read", pane, "--source", "recent-unwrapped", "--lines", "60"], 10)
    if code != 0:
        return None
    keep = []
    for ln in out.splitlines():
        s = ln.strip()
        if s.startswith(("─", "❯", "⏵", "Opus", "id:", "✔", "※")) or "ctx:[" in s:
            continue                          # 입력 칸 · 상태 줄
        keep.append(ln)
    return "(창 화면에서 읽음)\n" + "\n".join(keep[-30:]).strip()


def _work(job):
    lockf = open(LOCK_FILE, "w")
    try:
        try:
            fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError("다른 서버가 지시를 보내는 중입니다 — 끝나면 다시 보내 주십시오")
        pane, status, sid = _pane()
        if status == "blocked":
            raise RuntimeError("지금 못 받음 — %s 창이 다른 물음에 막혀 있습니다" % TARGET_LABEL)
        if status == "working":
            job["state"] = "waiting-idle"
            code, _, err = _run(["agent", "wait", pane, "--until", "idle", "--until", "done", "--until", "blocked",
                                 "--timeout", str(WAIT_IDLE_SEC * 1000)], WAIT_IDLE_SEC + 10)
            if code != 0:
                raise RuntimeError("지금 못 받음 — %s 창이 %d초 넘게 일하는 중입니다" % (TARGET_LABEL, WAIT_IDLE_SEC))
            pane, status, sid = _pane()
            if status == "blocked":
                raise RuntimeError("지금 못 받음 — %s 창이 다른 물음에 막혀 있습니다" % TARGET_LABEL)
        line = "%s (#%s · %s · %s) %s" % (MARK, job["id"], job["origin"], time.strftime("%H:%M"), job["text"].replace("\n", " / "))
        job["state"] = "sent"
        code, out, err = _run(["agent", "prompt", pane, line, "--wait", "--until", "idle", "--until", "done", "--until", "blocked",
                               "--timeout", str(WAIT_DONE_SEC * 1000)], WAIT_DONE_SEC + 10)
        if code != 0:
            raise RuntimeError("넣었으나 끝을 못 봤습니다 — %s" % (err or out)[:120])
        _, status, sid2 = _pane()
        ans = _answer_from_log(sid2 or sid, "#" + job["id"]) or _answer_from_screen(pane)
        if not ans:
            raise RuntimeError("넣었으나 답 글을 못 읽었습니다")
        job.update(state="done", answer=ans, blocked=status == "blocked")
    finally:
        try:
            fcntl.flock(lockf, fcntl.LOCK_UN)
        finally:
            lockf.close()


def _thread(job):
    try:
        _work(job)
    except subprocess.TimeoutExpired:
        job.update(state="fail", error="기다리다 끊었습니다")
    except Exception as e:
        job.update(state="fail", error=safe_message(e, 160))
    job["secs"] = round(time.time() - job["t0"], 1)
    _log(job)


def submit(text, origin, port):
    """지시 하나를 받아 뒤에서 보낸다 → 상태 묶음. 빈 글 · 긴 글 ValueError · 돌고 있으면 Busy · 이 자리가 아니면 NotHere."""
    if port not in ORDER_PORTS:
        raise NotHere("이 서버(%s)는 업무지시를 보내지 않습니다 — 개발 서버 · 메인 화면에서 보내 주십시오" % port)
    if text is not None and not isinstance(text, str):
        raise ValueError("지시는 글자여야 합니다")
    text = (text or "").strip()
    if not text:
        raise ValueError("지시가 비었습니다")
    if len(text) > MAX_TEXT:
        raise ValueError("지시는 %d 자까지입니다" % MAX_TEXT)
    with _lock:
        if any(j["state"] not in ("done", "fail") for j in _jobs.values()):
            raise Busy("앞 지시를 작업우선순위 창이 받는 중입니다 — 끝나면 다시 보내 주십시오")
        job = {"id": uuid.uuid4().hex[:6], "text": text, "origin": origin, "port": port, "state": "queued",
               "t0": time.time(), "at": time.strftime("%H:%M:%S"), "answer": None, "error": None, "secs": None}
        _jobs[job["id"]] = job
        _order.append(job["id"])
        while len(_order) > KEEP_JOBS:
            _jobs.pop(_order.pop(0), None)
    threading.Thread(target=_thread, args=(job,), daemon=True).start()
    return view(job)


def get(job_id):
    j = _jobs.get(str(job_id or ""))
    return view(j) if j else None


def view(j):
    return {k: j[k] for k in ("id", "state", "at", "origin", "answer", "error", "secs")} | {"blocked": j.get("blocked", False),
                                                                                          "pollMs": POLL_MS, "target": TARGET_LABEL}
