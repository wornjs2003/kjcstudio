# -*- coding: utf-8 -*-
"""세션 이름 ↔ 지금 보낼 주소 — 재부팅 · 재시작 뒤 세션끼리 대화가 끊기는 것을 막는다 (2026-10-02 지시).

재권님 말씀 — 「다른 세션에서 여기랑 대화가 안되는 곳이 있는데 … 재부팅이나 재시작시 발생하는데 재발 안하게 룰 만들어줘」.

왜 끊기나 (2026-10-02 실측)
  SendMessage 의 이름(`kjcstudio-b4` 같은 것)은 **세션이 다시 뜰 때마다 바뀐다** — 개념정의가 아침 `kjcstudio-8c`
  에서 재시작 뒤 `kjcstudio-b4` 가 됐다. 그 이름에는 세션 이름(개념정의 · qa …)이 없고, 메인 폴더 창 넷은 겉으로
  가를 수 없다. 옛 이름을 기억해 두고 보내면 **없는 이름**이라 안 가거나, 같은 폴더의 엉뚱한 세션에 간다.

그래서 기억하지 않고 **그 자리에서 센다.**
  세션 이름   herdr 창 이름(label) — 재권님이 붙인 이름. 세션 기록 id(agent_session)로 맞춘다
  보낼 주소   `uds:/tmp/cc-socks/<pid>.sock` — 그 프로세스가 사는 동안 그대로다. pid 는 `--resume <기록 id>` 로 맞춘다
              (SendMessage 의 to 에 이 꼴을 그대로 넣으면 간다 — 2026-10-02 qa 에 보내 확인)
  이름        ListAgents 의 이름 — 참고로만. 재시작하면 바뀐다

    python3 tools/session-addr.py            표 — 세션 이름 · 보낼 주소 · 폴더
    python3 tools/session-addr.py qa         그 세션의 보낼 주소 한 줄 (없으면 종료 1) — 「개발2」 처럼 끝만 써도 된다
    받은 메시지의 from(uds:…sock)이 누구인지도 이 표로 거꾸로 가른다 — from-name 은 폴더 이름이라 못 가른다

종료코드  0 다 맞춤 · 1 찾는 이름 없음 · 2 **못 쟀다**(herdr 를 못 읽음 · 소켓 0개 — 「없다」 가 아니라 「안 봤다」)
"""
import glob
import json
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SOCKS = "/tmp/cc-socks"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return ""


def labels():
    """{세션 기록 id: (창 이름, 폴더)} — herdr 를 못 읽으면 None."""
    try:
        panes = json.loads(run(["herdr", "pane", "list"]))["result"]["panes"]
    except Exception:
        return None
    out = {}
    for p in panes:
        sid = (p.get("agent_session") or {}).get("value")
        if sid:
            out[sid] = ((p.get("label") or "").strip() or "?", os.path.basename(p.get("cwd") or ""))
    return out


def sid_of(pid):
    """(세션 기록 id, 어디서 얻었나) — `--resume <id>` 가 먼저, 없으면 열어 둔 기록 **파일 이름**의 id.

    경로의 첫 id 를 집으면 안 된다 — 헤드리스 시험 세션은 기록 폴더 이름에 **부모 세션 id** 가 들어 있어
    부모로 읽혔고, 그 동안 같은 이름이 둘이 되어 훅이 손을 뗐다(2026-10-02 qa 실측 · 「한 번 빗나감」 의 원인)."""
    m = re.search(r"--resume\s+(" + UUID.pattern + ")", run(["ps", "-o", "args=", "-p", pid]))
    if m:
        return m.group(1), "resume"
    m = re.search(r"(" + UUID.pattern + r")\.jsonl", " ".join(
        l for l in run(["lsof", "-p", pid]).splitlines() if ".jsonl" in l))
    return (m.group(1), "lsof") if m else ("", "")


def table():
    lb = labels()
    socks = sorted(glob.glob(os.path.join(SOCKS, "*.sock")))
    if lb is None or not socks:
        return None
    best = {}                                 # 세션 기록 id → (얻은 길, 줄) — 같은 id 가 둘이면 --resume 쪽
    rest = []
    for s in socks:
        pid = os.path.basename(s)[:-5]
        if not run(["ps", "-o", "pid=", "-p", pid]).strip():
            continue                          # 죽은 프로세스가 남긴 소켓
        sid, via = sid_of(pid)
        name, cwd = lb.get(sid, ("?(창 이름 없음)", "?"))
        row = (name, "uds:" + s, cwd, sid[:8])
        if not sid:
            rest.append(row)
        elif sid not in best or (via == "resume" and best[sid][0] != "resume"):
            best[sid] = (via, row)
    return sorted([r for _, r in best.values()] + rest)


def resolve(rows, want):
    """이름 → 그 줄. 완전 일치가 먼저, 없으면 끝 일치(「개발2」 → 주식페이지_개발2) — **하나일 때만.**
    훅(hook-sendmessage-addr.py)도 이 함수를 쓴다 — 맞추는 셈이 두 곳이면 갈린다(작업우선순위 감사)."""
    exact = [r for r in rows if r[0] == want]
    if exact:
        return exact if len(exact) == 1 else exact
    return [r for r in rows if r[0].endswith(want)]


def main():
    rows = table()
    if rows is None:
        print("못 쟀습니다 — herdr 창 목록을 못 읽었거나 소켓이 0개입니다. 「없다」 가 아니라 「안 봤다」 입니다.")
        return 2
    want = sys.argv[1] if len(sys.argv) > 1 else ""
    if want:
        hit = resolve(rows, want)
        if len(hit) != 1:
            print("「%s」 에 맞는 세션이 %d개입니다 — 표를 보십시오: python3 tools/session-addr.py" % (want, len(hit)))
            return 1
        print(hit[0][1])
        return 0
    print("세션 이름 → 보낼 주소 (SendMessage 의 to 에 그대로 · 재시작하면 다시 돌린다)")
    for name, addr, cwd, sid in rows:
        print("  %-18s %-30s %-12s %s" % (name, addr, cwd, sid))
    return 0


if __name__ == "__main__":
    sys.exit(main())
