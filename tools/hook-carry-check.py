#!/usr/bin/env python3
"""나르는 자리가 남의 창 물음 · 상태를 확인 없이 올렸는지 알린다 — Stop 훅 (2026-11-20 지시).

재권님 말씀 그대로다 — 「오늘 몇번째지? 룰로 만들어」(작업우선순위 창 · 14:32) → 문안에 「해」 → 훅은 「셋이 의견이 맞는방향으로 해」.
룰은 CLAUDE.md 「다른 창의 물음 · 상태는 그 자리에서 읽고 올린다 — 옮겨 적지 않는다」.

나르는 자리(작업우선순위 · 홈페이지_정리)의 마지막 답만 본다. 두 갈래 — qa 시뮬(11-20 14:4x) 대로 좁혔다:
  ① 확인란 ▶ 줄 · 「다른 창에 걸린 …」 머리 아래 묶음에 「<세션> 창」 이 나오는데 보드에 그 담당의 열린 「묻는 중:」 이 없다
     → 「현황판에 없는 물음」. 현황 표 줄은 안 본다(매 턴 되풀이라 헛걸림 · qa).
  ② ▶ 줄에 「/clear」 와 「<세션> 창」 이 함께 있는데 그 세션 기록 끝(마지막 답)에 「/clear」 가 없다 → 「이미 /clear 됨」.
세션 이름 → 창 · 기록 id 는 tools/session-addr.py 의 labels() 한 곳 · 열린 물음 셈은 tools/board-card.py 의 open_question 한 곳.
이름은 「<이름> 창」 꼴로만 찾는다 — 「개발」 이 「개발 서버」 · 「개발1」 에 걸리지 않게(qa 헛걸림 ⓑ).

`KJC_CARRY_HOOK=look|off` — 알리기만 한다(막지 않음 · 막기로 올릴지는 qa 재생 뒤 재권님).
못 읽으면(보드 · herdr · 기록) 조용히 지나가고 logs/carry-check.log 에 한 줄 남긴다 — 매 턴 「못 잼」 을 띄우면 신호가 죽는다.
"""
import glob
import importlib.util
import json
import os
import re
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODE = os.environ.get("KJC_CARRY_HOOK", "look")
CARRIERS = ("작업우선순위", "홈페이지_정리")
HERE = os.path.dirname(os.path.abspath(__file__))
FENCE = re.compile(r"```.*?(?:```|\Z)", re.S)
LIST_HEAD = re.compile(r"다른 창에 걸린")
QUOTED = re.compile(r"「[^「」]*」")              # 인용 — 지난 일을 되짚는 글은 머리 · 이름으로 안 센다(qa 재생 11-20 · 14:32 헛걸림)
ASKW = re.compile(r"물음|여쭘|여쭙|답 대기|확인 대기|답하실")
ALIAS = {"창구": "홈페이지_정리"}
CLEAR = re.compile(r"/clear|대화를 비워|비워 주")          # 「qa 창의 대화를 비워 주시겠습니까」 도 /clear 갈래로(qa 재생 ㅁ)
NONEW = re.compile(r"없습니다|없음")           # 「그 물음은 없습니다」 — 없다는 말(qa 재생 ㅊ)
DONE = re.compile(r"이미 닫혀|이미 되어|이미 됐|틀렸습니다")   # 지난 일 되짚기 줄은 안 센다(qa 재생 ㅅ)               # 세션들이 이름 대신 부르는 말(qa 재생 — 「창구(홈페이지_정리) 창」 을 놓침)


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def log(msg):
    try:
        root = os.path.dirname(HERE)
        os.makedirs(os.path.join(root, "logs"), exist_ok=True)
        with open(os.path.join(root, "logs", "carry-check.log"), "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def last_text(path):
    """기록 파일 끝의 마지막 답 글 — 세션이 쓴 것만(API 오류 · 시스템 글 뺌 · hook-hash.py 와 같은 거름)."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - (1 << 20)))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("type") != "assistant" or r.get("isSidechain") or r.get("isApiErrorMessage") \
                or (r.get("message") or {}).get("model") == "<synthetic>":
            continue
        t = [b.get("text", "") for b in (r.get("message") or {}).get("content") or []
             if isinstance(b, dict) and b.get("type") == "text"]
        if any(x.strip() for x in t):
            return "\n".join(t)
    return ""                                   # 답이 아직 없다 — /clear 직후 새 기록


def started(path):
    """기록 파일이 시작한 시각(오늘 · HHMM · 이 맥 시간대) — 첫 timestamp. /clear 하면 새 파일이 생긴다(--resume 은 같은 파일)."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for _, line in zip(range(40), f):
                m = re.search(r'"timestamp":"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)', line)
                if m:
                    today, hms = local_hms(m.group(1))
                    return hms if today else "000000"   # 어제 이전에 시작 — 오늘 어느 물음보다 앞
    except OSError:
        return None
    return None


def local_hms(iso):
    """기록의 timestamp(UTC ISO) → (오늘인가, HHMMSS 이 맥 시간대)."""
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)", iso or "")
    if not m:
        return False, None
    lt = time.localtime(time.mktime(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")) - time.timezone)
    return time.strftime("%Y%m%d", lt) == time.strftime("%Y%m%d"), time.strftime("%H%M%S", lt)


def answers(path):
    """기록 끝 쪽의 세션 답들 [(HHMMSS 오늘만, 글)] — 오래된 것부터."""
    out = []
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - (4 << 20)))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("type") != "assistant" or r.get("isSidechain") or r.get("isApiErrorMessage") \
                or (r.get("message") or {}).get("model") == "<synthetic>":
            continue
        t = "\n".join(b.get("text", "") for b in (r.get("message") or {}).get("content") or []
                      if isinstance(b, dict) and b.get("type") == "text")
        today, hms = local_hms(r.get("timestamp"))
        if t.strip() and today:
            out.append((hms, t))
    return out


def first_asked(path, name, names):
    """이 /clear 물음을 처음 여쭌 때 — 자기 기록에서 같은 이름 + CLEAR 가 든 ▶ 이 이어진 첫 답의 시각(qa 재생 ㅇ ·
    짧은 꼴 「앞서 12시 4x분」 처럼 숫자 시각이 아닌 글이라 글에서 못 셈). 못 셈 → 지금."""
    first = time.strftime("%H%M%S")              # 이 답부터 — 이 답이 이미 기록에 있으면 그것도 같은 물음이라 이어진다
    for hms, t in reversed(answers(path)):
        box = [l for kind, l in target_lines(t) if kind == "box" and CLEAR.search(l)]
        if any(name in names_in(l, names) for l in box):
            first = min(first, hms)
        else:
            break                               # 이어짐이 끊긴 데까지만 — 오전에 같은 물음을 했다고 지금 물음의 시각으로 삼지 않는다
    return first


def target_lines(text):
    """▶ 줄 · 「다른 창에 걸린 …」 머리 아래 묶음(빈 줄까지) · 본문 한 줄에 물음 낱말이 있는 줄(이름은 names_in 이 거름).
    표 줄(| 로 시작)은 안 본다 — 현황 표가 매 턴 되풀이한다(qa 시뮬 11-20)."""
    out, inlist = [], False
    for ln in FENCE.sub(" ", text or "").split("\n"):
        s = ln.strip()
        if not s:
            inlist = False
            continue
        bare = QUOTED.sub(" ", s)
        if DONE.search(bare):
            continue
        if s.startswith("▶"):
            out.append(("box", s))
        elif LIST_HEAD.search(bare):
            inlist = True
            out.append(("list", s))
        elif inlist:
            if not NONEW.search(bare):
                out.append(("list", s))
        elif not s.startswith("|") and ASKW.search(bare) and not NONEW.search(bare):
            out.append(("body", s))
    return out


def short(name):
    return name[len("주식페이지_"):] if name.startswith("주식페이지_") else name


def names_in(line, names):
    """줄에 「<이름> 창」 꼴로 나온 세션 이름(긴 이름부터 · 겹쳐 잡지 않게)."""
    hits, rest = [], QUOTED.sub(" ", line)
    for full in sorted(names, key=lambda n: -len(short(n))):
        for alias in {full, short(full)} | {a for a, f in ALIAS.items() if f == full}:
            pat = r"(?<![0-9A-Za-z가-힣_])%s\s*(?:\([^)]*\))?\s*창(?!구)" % re.escape(alias)   # 「창구(홈페이지_정리) 창」 꼴도
            if re.search(pat, rest):
                hits.append(full)
                rest = re.sub(pat, " ", rest)
                break
    return hits


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if MODE == "off" or data.get("stop_hook_active"):
        return 0
    sa = load("session_addr", "session-addr.py")
    lb = sa.labels()
    if not lb:
        log("herdr 못 읽음")
        return 0
    me = (lb.get(data.get("session_id") or "") or ("", ""))[0]
    if me not in CARRIERS:
        return 0
    text = data.get("last_assistant_message") or last_text(data.get("transcript_path") or "") or ""
    lines = target_lines(text)
    if not lines:
        return 0
    names = {v[0]: k for k, v in lb.items() if v[0] and v[0] != me and not v[0].startswith("?")}   # 이름 → 기록 id
    try:                                        # 창(herdr)이 아는 id 는 /clear 뒤 낡을 수 있다 — 프로세스로 맞춘 표의 id 를 먼저(11-20 qa 435e… ↔ b2a7…)
        for row in sa.table() or []:
            if row[0] in names:
                names[row[0]] = row[3]
    except Exception:
        pass
    asks = clears = None
    notes = []
    for kind, ln in lines:
        hit = names_in(ln, names)
        if not hit:
            continue
        if kind == "box" and CLEAR.search(ln):
            # ② 이미 비웠나 — 그 창 지금 기록이 처음 여쭌 때보다 뒤에 시작했으면 이미 /clear 됐다(qa 재생 ㅂ · 11-20).
            #    「앞서 HH:MM 에 여쭌」 짧은 꼴이면 그 시각 · 아니면 지금. 스스로 청한 /clear 도 같은 셈으로 갈린다
            for n in hit:
                files = glob.glob(os.path.expanduser("~/.claude/projects/*/%s*.jsonl" % names[n]))
                st = started(files[0]) if files else None
                if st is None:
                    log("기록 시작 시각 못 읽음 %s" % n)
                    continue
                asked = first_asked(data.get("transcript_path") or "", n, names)
                if st > asked:
                    notes.append("「%s 창 /clear」 — 그 창은 %s:%s 에 이미 새로 시작했습니다(처음 여쭌 때 %s:%s 뒤)" % (n, st[:2], st[2:4], asked[:2], asked[2:4]))
                elif st != "000000":
                    # 처음 여쭐 때 이미 비워져 있던 것(qa 재생 ㅈ · 11-20 14:10 창구) — 오늘 시작한 기록인데 그 창이 /clear 를 청한 적이 없으면
                    tail = last_text(files[0]) or ""
                    asks_clear = [l for kind, l in target_lines(tail) if kind == "box" and CLEAR.search(l)]
                    if not asks_clear:                  # 그 창 확인란에 /clear 청함이 없다 — 본문에서 /clear 를 말한 것은 안 센다
                        notes.append("「%s 창 /clear」 — 그 창은 %s:%s 에 새로 시작했고 /clear 를 청하지 않았습니다(이미 됐을 수 있음)" % (n, st[:2], st[2:4]))
            continue
        if asks is None:
            try:
                bc = load("board_card", "board-card.py")
                doc, _ = bc.read()
                asks = {}
                for t in bc.tasks(doc):
                    if t.get("column") in ("todo", "doing", "review") and bc.open_question(t.get("memo") or ""):
                        asks.setdefault(bc.who_of(t), 0)
                        asks[bc.who_of(t)] += 1
            except Exception as e:
                log("보드 못 읽음 %s" % type(e).__name__)
                return 0
        for n in hit:
            if not asks.get(short(n)):
                notes.append("「%s 창」 물음 — 현황판(보드)에 그 담당의 열린 「묻는 중:」 이 없습니다" % n)
    if not notes:
        return 0
    seen = []
    for x in notes:
        if x not in seen:
            seen.append(x)
    msg = ("다른 창 일을 올리기 전에 그 자리에서 읽었습니까 — " + " · ".join(seen[:4]) +
           ". 현황판과 그 창 기록 끝을 다시 읽고, 풀린 것이면 정정을 따로 올립니다"
           "(CLAUDE.md 「다른 창의 물음 · 상태는 그 자리에서 읽고 올린다」 · 11-20 하루 다섯 번).")
    print(json.dumps({"systemMessage": msg}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
