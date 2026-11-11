# -*- coding: utf-8 -*-
"""멈춘 카드 셈 — 「받은 지시는 끝나거나 재권님이 거두실 때까지 보드에 살아 있다」(2026-11-11 지시 — 「응 만들어」).

    python3 tools/board-stale.py                     담당별로 멈춘 카드를 낸다 (0 없음 · 1 있음 · 2 못 봄)
    python3 tools/board-stale.py --who <담당>         그 담당만
    python3 tools/board-stale.py --standing "<카드 제목 일부>" [-]
                                                     영구 카드(절차서 · 상시 업무) 표시 — (ㄷ) 에서 뺀다 · - 면 표시를 지운다

**무엇을 세나 — 셋**
    (ㄱ) 답 없는 「묻는 중:」 이 STALE_DAYS 일 넘게 남은 카드
    (ㄴ) doing 인데 메모 줄 수가 STALE_DAYS 일 넘게 안 늘어난 카드
    (ㄷ) doing · review 카드인데 그 카드의 커밋(「커밋 <해시>」 줄 — post-commit 이 적는 꼴)이 이미 origin/main 에 든 카드 — 끝났는데 안 닫힘. 마지막 커밋 줄 뒤에 검수 줄 말고 다른 메모가 붙었으면 뺀다(일이 이어짐)
         창구가 옮겨 심은 것은 `cherry picked from commit <해시>` 줄로 거슬러 찾는다(세션 해시만 보면 영영 안 걸린다 · 창구 11-11 잼)
    마지막 메모 줄에 「홀딩」 이나 「뒤에 진행:」 이 있으면 뺀다 — 재권님이 미루신 것이다

**며칠인가는 이 도구가 쌓은 기록으로 센다.** 메모 줄에는 시각만 있고 날짜가 없다. updatedAt 은 열 옮김 · 훅 해시 적기로도
바뀌어 쓰지 않는다(작업우선순위 검토). 그래서 돌 때마다 카드별 메모 줄 수 · 열린 물음을 `logs/board-stale.json` 에 남기고,
값이 바뀐 날을 센다. **기록이 아직 없는 카드는 「첫 셈 · 어림」 이다** — 그때만 updatedAt 을 어림으로 쓰고 그렇게 적는다.

**「지시하신 일」 가름** — 메모에 재권님 말씀 인용(「재권님 … 「…」」 꼴)이 있으면 지시로 센다. 없는 doing · review 는 「지시인지 못 가름」
으로 따로 낸다 — 0 으로 내지 않는다. [미배분] todo 는 세션이 스스로 찾은 것이라 (ㄷ) 만 본다.

**돌리는 쪽** — 작업우선순위가 아침 한 번 돌려 담당 세션에 돌린다. 닫을지 · 이어 갈지는 그 세션 · 재권님이 정한다.
이 도구는 카드를 고치지 않는다(--standing 표시만 예외).
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STALE_DAYS = 2                      # 이 날 수를 넘게 안 움직이면 멈춘 것으로 센다 — 한 곳
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "logs", "board-stale.json")
HASH = re.compile(r"커밋\s+([0-9a-f]{7,12})\b")   # 커밋 뒤 훅이 적는 「커밋 <해시>」 줄만 — 덧말 · 검수 통과 줄에 인용한 남의 해시는 안 센다(개발2 11-11 · 손 안 댄 todo 가 걸렸다)
ORDER = re.compile(r"재권님[^「\n]{0,40}「")          # 재권님 말씀 인용 — 「재권님 「…」」 · 「재권님(창) 「…」」


def _board():
    spec = importlib.util.spec_from_file_location("board_card", os.path.join(ROOT, "tools", "board-card.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _lines(memo):
    return [x for x in (memo or "").split("\n") if x.strip()]


def _paused(memo):
    ls = _lines(memo)
    return bool(ls) and ("홀딩" in ls[-1] or "뒤에 진행:" in ls[-1])


def _main_sets():
    """origin/main 의 커밋 해시(전부) · 옮겨 심은 원본 해시. 못 읽으면 None."""
    try:
        out = subprocess.run(["git", "-C", ROOT, "log", "origin/main", "--format=%H%x00%b%x01"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode:
            return None
    except Exception:
        return None
    full, picked = [], set()
    for rec in out.stdout.split("\x01"):
        if "\x00" not in rec:
            continue
        h, body = rec.strip().split("\x00", 1)
        full.append(h)
        for src in re.findall(r"cherry picked from commit ([0-9a-f]{7,40})", body):
            picked.add(src)
    return full, picked


def _in_main(h, sets):
    full, picked = sets
    return any(x.startswith(h) for x in full) or any(x.startswith(h) for x in picked)


def _is_commit(h):
    r = subprocess.run(["git", "-C", ROOT, "cat-file", "-t", h], capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == "commit"


def cmd_standing(key, off):
    bc = _board()

    def change(doc):
        hits = [t for t in bc.tasks(doc) if key in t.get("text", "")]
        if len(hits) != 1:
            sys.exit("카드 %d개 걸림 — 더 좁혀서: %s" % (len(hits), key))
        if off:
            hits[0].pop("standing", None)
        else:
            hits[0]["standing"] = True
        bc.touch(hits[0])
    try:
        bc.apply(change)
    except bc.Unseen as e:
        print("보드를 못 봤다(%s)" % e)
        return 2
    print("영구 카드 표시 %s: %s" % ("지움" if off else "함", key))
    return 0


def main(argv):
    if "--standing" in argv:
        i = argv.index("--standing")
        key = argv[i + 1] if i + 1 < len(argv) else ""
        if not key:
            sys.exit("--standing 에 카드 제목 일부를 주십시오")
        return cmd_standing(key, "-" in argv[i + 2:])
    only = None
    if "--who" in argv:
        i = argv.index("--who")
        only = argv[i + 1] if i + 1 < len(argv) else ""
    bc = _board()
    try:
        doc, _ = bc.read()
    except bc.Unseen as e:
        print("보드를 못 봤다(%s) — 멈춘 카드를 못 셌다. 0 이 아니다" % e)
        return 2
    sets = _main_sets()
    today = time.strftime("%Y-%m-%d")
    try:
        state = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        state = {}
    new_state, found = {}, {}
    commit_ok = {}

    for t in bc.tasks(doc):
        col = t.get("column") or "todo"
        if col == "done":
            continue
        cid = t.get("id") or t.get("text", "")
        memo = t.get("memo") or ""
        n = len(_lines(memo))
        ask = bc.open_question(memo)
        old = state.get(cid)
        rough = old is None
        if rough:                                     # 첫 셈 — updatedAt 로 어림
            u = t.get("updatedAt") or t.get("createdAt") or 0
            since = time.strftime("%Y-%m-%d", time.localtime(u / 1000)) if u else today
            ent = {"n": n, "since": since, "ask": ask, "ask_since": since if ask else None}
        else:
            ent = dict(old)
            if n != old.get("n"):
                ent["n"], ent["since"] = n, today
            if ask != old.get("ask"):
                ent["ask"], ent["ask_since"] = ask, (today if ask else None)
        new_state[cid] = ent
        who = bc.who_of(t) or "(담당 없음)"
        if only is not None and who != only:
            continue
        if _paused(memo):
            continue
        days = lambda d: (time.mktime(time.strptime(today, "%Y-%m-%d")) - time.mktime(time.strptime(d, "%Y-%m-%d"))) / 86400
        why = []
        if ask and ent.get("ask_since") and days(ent["ask_since"]) > STALE_DAYS:
            why.append("(ㄱ) 답 없는 물음 %d일 — %s" % (days(ent["ask_since"]), ask[:60]))
        if col == "doing" and days(ent["since"]) > STALE_DAYS:
            why.append("(ㄴ) 메모 %d일 안 늘어남" % days(ent["since"]))
        # (ㄷ) 은 doing · review 만 · 마지막 「커밋 …」 줄 뒤에 「검수 통과」 가 아닌 메모가 붙었으면 뺀다 — 「남은 것: …」 처럼 일이 이어지는 카드 ·
        # 본 일은 main 에 가고 남은 하위로 todo 에 내린 카드가 날마다 다시 떴다(qa 11-11 시뮬 · 33 중 약 10)
        ls = _lines(memo)
        last = max((i for i, x in enumerate(ls) if HASH.search(x)), default=None)
        tail_ok = last is not None and all("검수 통과" in x or "검수 걸림" in x or re.search(r"열 \w+ → \w+", x) for x in ls[last + 1:])
        if sets and not t.get("standing") and col in ("doing", "review") and tail_ok:
            hs = []
            for h in dict.fromkeys(HASH.findall(memo)):
                if h not in commit_ok:
                    commit_ok[h] = _is_commit(h)
                if commit_ok[h]:
                    hs.append(h)
            if hs and all(_in_main(h, sets) for h in hs):
                why.append("(ㄷ) 적힌 커밋 %d개가 다 main 에 듦 — 끝났는데 열이 %s" % (len(hs), col))
        if not why:
            continue
        kind = "지시" if ORDER.search(memo) else ("스스로 찾음" if col == "todo" else "지시인지 못 가름")
        found.setdefault(who, []).append((kind, col, t.get("text", "")[:70], why, rough))

    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        tmp = STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(new_state, f, ensure_ascii=False)
        os.replace(tmp, STATE)
    except Exception as e:
        print("기록을 못 남겼다(%s) — 다음 셈도 어림이 된다" % type(e).__name__)

    print("멈춘 카드 — %s · 기준 %d일 넘게 · 보드 8765%s" % (time.strftime("%m-%d %H:%M"), STALE_DAYS,
          "" if sets else " · ⚠ origin/main 을 못 읽어 (ㄷ) 은 못 셌다"))
    if not found:
        print("  없음")
        return 0
    for who in sorted(found, key=lambda w: -len(found[w])):
        rows = found[who]
        print("\n[%s] %d장" % (who, len(rows)))
        for kind, col, title, why, rough in sorted(rows, key=lambda r: r[0] != "지시"):
            print("  · %s · %s · %s%s" % (kind, col, title, " · 첫 셈(어림)" if rough else ""))
            for w in why:
                print("      %s" % w)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
