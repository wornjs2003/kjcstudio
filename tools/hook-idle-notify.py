#!/usr/bin/env python3
"""세션이 일 없이 멈추면 작업우선순위에 알린다 — 훅 (2026-11-20 지시).

재권님 말씀 그대로다 — 「세션이 멈추면 자동으로 작업우선순위에 메세지 안보내나? 이거 하네스로 만들어야 하지않나?」
→ 작업우선순위 안 (가) 보낼 때 idle 알림 구독 · (나) Stop 훅 → 「나 로해」(14:54).

**한 파일 · 두 자리**
    Stop                         쓰는 쪽 — 모든 세션(작업우선순위 · 홈페이지_정리 · qa 빼고). 답 끝이 「지금 답하실 것은 없습니다」 이고
                                 확인란(▶)이 없으며 보드에 그 담당의 doing 카드가 0 이면 logs/idle.log 에 「HH:MM <세션> 들고 있는 것 없음」 한 줄.
                                 같은 세션은 일을 다시 잡기 전까지 한 번만 적는다(logs/idle-state.json).
    UserPromptSubmit · PreToolUse 읽는 쪽 — 작업우선순위만. 아직 안 넣은 줄을 그 세션 문맥에 넣는다(logs/idle-read.json 에 어디까지 읽었나).

**다음 일을 주기 전에 재권님께 먼저 여쭙는 것은 따로 훅이다** — tools/hook-assign-ask.py(작업우선순위 카드 「훅 — 작업우선순위가 세션에 일을 주기 전에」).

**왜 기록 파일인가** — 훅에서 다른 세션에 메시지를 넣는 길을 재 보았다(14:55). Claude Code 세션 소켓의 넣는 꼴은 문서가 없어 짐작해
쓰지 않았고(「추측 금지 규칙」), `herdr agent prompt` 는 그 창에 재권님이 친 것처럼 들어가 쓰지 않는다. 그래서 작업우선순위가 다음에
도구를 부르거나 말씀을 받을 때 넣는다 — 작업우선순위는 메시지로 자주 깨므로 늦어도 그 다음 턴이다.
끝 가름(「지금 답하실 것은 없습니다」 · 확인란)은 tools/hook-confirm-box.py 한 곳 · 담당 · doing 셈은 tools/board-card.py 한 곳 ·
세션 이름은 tools/session-addr.py 한 곳.

`KJC_IDLE_HOOK=look|off` — 알리기만(막는 일이 없다). 못 읽으면(herdr · 보드) 조용히 지나가고 logs/idle-notify.log 에 한 줄.
"""
import importlib.util
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODE = os.environ.get("KJC_IDLE_HOOK", "look")
SKIP = ("작업우선순위", "홈페이지_정리", "qa")     # 받는 쪽 · 창구 · qa 는 안 적는다(작업우선순위 안)
READER = "작업우선순위"
DOING_FRESH_H = 3        # 이만큼 안 고친 doing 카드는 「들고 있는 것」 으로 안 센다(시간) — 카드 updatedAt 셈
HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.environ.get("KJC_IDLE_LOGDIR") or os.path.join(os.path.dirname(HERE), "logs")   # 시험은 다른 폴더로 — 진짜 기록에 가짜 줄이 안 들어가게
IDLE_LOG = os.path.join(LOGS, "idle.log")
STATE = os.path.join(LOGS, "idle-state.json")
READ = os.path.join(LOGS, "idle-read.json")


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def note(msg):
    try:
        os.makedirs(LOGS, exist_ok=True)
        with open(os.path.join(LOGS, "idle-notify.log"), "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def jload(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def jsave(path, v):
    os.makedirs(LOGS, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False)
    os.replace(tmp, path)


def short(name):
    return name[len("주식페이지_"):] if name.startswith("주식페이지_") else name


def writer(data, me):
    if me in SKIP:
        return
    cb = load("confirm_box", "hook-confirm-box.py")
    text = data.get("last_assistant_message") or cb.last_text(data.get("transcript_path") or "") or ""
    idle_end = bool(cb.NONE_RE.search(text[-300:])) and not cb.box_lines(text)
    state = jload(STATE, {})
    if not idle_end:
        return                                  # 물음 · 진행 중 답 — 상태는 그대로(물을 때마다 다시 알리지 않게 · qa 재생 11-20)
    try:
        bc = load("board_card", "board-card.py")
        doc, _ = bc.read()
        # 묵은 doing 은 안 센다 — 카드를 안 닫고 멈춘 세션이 많아 그대로 세면 이 훅이 영영 안 돈다(qa 재생 11-20 — 44 번 자리 · 0 번 적힘)
        fresh = time.time() * 1000 - DOING_FRESH_H * 3600 * 1000
        doing = sum(1 for t in bc.mine(doc, short(me)) if (t.get("updatedAt") or 0) >= fresh)
        todo = []                               # 후보 — 그 담당 todo 중 미뤄 둔 것(「뒤에 진행」 · 「홀딩」) 빼고 · 차례 번호 먼저(작업우선순위 검토 11-20)
        for t in bc.tasks(doc):
            if t.get("column") != "todo" or bc.who_of(t) != short(me):
                continue
            last = ((t.get("memo") or "").strip().splitlines() or [""])[-1]
            if "뒤에 진행" in last or "홀딩" in last:
                continue
            todo.append((t.get("rank") if isinstance(t.get("rank"), (int, float)) else 1e9, t.get("text", "")[:40]))
        todo = [x[1] for x in sorted(todo)[:3]]
    except Exception as e:
        note("보드 못 읽음 %s %s" % (me, type(e).__name__))
        return
    if doing:
        if state.get(me) == "idle":
            state[me] = "busy"
            jsave(STATE, state)
        return
    today = time.strftime("%Y-%m-%d")
    if state.get(me) == "idle" and state.get(me + "@day") == today:
        return                                  # 이미 알렸다 — 일을 다시 잡거나(doing 생김) 날이 바뀌기 전까지 한 번
    with open(IDLE_LOG, "a", encoding="utf-8") as f:
        f.write("%s %s 들고 있는 것 없음(진행 중 카드 0 · 답 끝 「지금 답하실 것은 없습니다」) · 후보 %s\n"
                % (time.strftime("%Y-%m-%d %H:%M"), me, " / ".join("「%s」" % x for x in todo) if todo else "없음(todo 카드 0)"))
    state[me] = "idle"
    state[me + "@day"] = today
    jsave(STATE, state)


def reader(event):
    try:
        size = os.path.getsize(IDLE_LOG)
    except OSError:
        return
    pos = jload(READ, {}).get("pos", 0)
    if pos > size:
        pos = 0                                 # 파일이 새로 생겼다
    if pos == size:
        return
    with open(IDLE_LOG, "rb") as f:
        f.seek(pos)
        new = f.read().decode("utf-8", "ignore")
    jsave(READ, {"pos": size})
    today = time.strftime("%Y-%m-%d")
    lines = [l[11:] for l in new.splitlines() if l.startswith(today)]   # 오늘 것만 · 날짜는 떼고
    if not lines:
        return
    text = ("[멈춘 세션 — 자동 · tools/hook-idle-notify.py] 아래 세션이 일 없이 멈췄습니다. 줄 일은 바로 주지 않고 후보를 ▶ 로 재권님께 먼저 여쭙니다(tools/hook-assign-ask.py)"
            "(올리기 전에 현황판 · 그 창 기록 끝을 다시 읽습니다 — CLAUDE.md 「다른 창의 물음 · 상태는 그 자리에서 읽고 올린다」).\n  · "
            + "\n  · ".join(lines))
    ev = event if event in ("UserPromptSubmit", "PreToolUse") else "PreToolUse"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": ev, "additionalContext": text}}, ensure_ascii=False))


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if MODE == "off":
        return 0
    event = data.get("hook_event_name") or ""
    try:
        sa = load("session_addr", "session-addr.py")
        lb = sa.labels()
    except Exception:
        lb = None
    if not lb:
        note("herdr 못 읽음")
        return 0
    me = (lb.get(data.get("session_id") or "") or ("", ""))[0]
    if not me or me.startswith("?"):
        return 0
    try:
        if event == "Stop":
            if not data.get("stop_hook_active"):
                writer(data, me)
        elif me == READER:
            reader(event)
    except Exception as e:
        note("%s %s %s" % (event, me, type(e).__name__))
    return 0


if __name__ == "__main__":
    sys.exit(main())
