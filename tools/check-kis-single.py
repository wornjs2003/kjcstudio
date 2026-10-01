# -*- coding: utf-8 -*-
"""KIS 를 부르는 자리가 **8765 하나인지** 센다 (2026-10-01 지시 · 길 (가) 넘기기).

    python3 tools/check-kis-single.py          맞으면 0 · 어긋나면 1 · 못 쟀으면 2

**셋을 본다.** 대상 개수를 함께 낸다 — 「대상 0개」 를 `0` 으로 내지 않는다.

    a. 토큰 캐시   `git worktree list` 의 폴더마다 `holdings/.kis-token-cache.json` 을 보고,
                  **메인 폴더 밖의 것이 8765 기동 뒤에 갱신됐으면** 위반.
                  옛 파일이 남은 것은 위반이 아니다 — 지울 필요가 없다.
                  ⚠️ 8765 가 죽어 폴백이 돌면 그때도 생긴다. 살아 있는 서버의
                  `stats.upstreamFallbacks` 와 함께 읽는다 (아래 d).
    b. 등록 파일   변수가 **둘**이다 (2026-10-01 · 개발2 코드). 8765 가 아닌 plist 전부에
                  **보내는 쪽**(`*UPSTREAM`) 이 있나 · **8765 plist 에 받는 쪽**(`*UPSTREAM_SERVE`)
                  이 있나 — 받는 쪽이 없으면 보내는 쪽이 전부 404 → 폴백이라 「됐다」 로
                  보이는데 아무것도 안 모인다. 설치본(`~/Library/LaunchAgents`)이 저장소와 같나.
    c. 변수 이름   plist 가 주는 이름 집합과 `kis_proxy.py` 가 `os.environ.get(...)` 으로
                  읽는 이름 집합이 같나 — 「같은 값은 한 곳에」 의 대조 도구.
    d. 살아 있는 서버  `/api/kis/stats` 에 `upstream` 이 있으면 센다. 없으면 「아직」.

**값을 박지 않는다.** 폴더는 `git worktree list` 로, plist 는 `launchd/` 글롭으로,
변수 이름은 plist 에서 읽어 온다. 메인 폴더는 이 파일의 위치다.
"""
import glob
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PORT = 8765
CACHE_REL = os.path.join("holdings", ".kis-token-cache.json")
PROXY = os.path.join(ROOT, "holdings", "server", "kis_proxy.py")
LAUNCHD = os.path.join(ROOT, "launchd")
INSTALLED = os.path.expanduser("~/Library/LaunchAgents")

bad = []      # 위반
unsure = []   # 못 쟀다 · 아직
notes = []


def sh(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return ""


# ── 8765 기동 시각 ───────────────────────────────────────────
def main_started():
    out = sh(["lsof", "-nP", "-iTCP:%d" % MAIN_PORT, "-sTCP:LISTEN"])
    pids = sorted({ln.split()[1] for ln in out.splitlines()[1:] if ln.split()})
    if not pids:
        return None
    # ps 의 lstart 는 로캘 글자라 epoch 로 바꾸기 어렵다 — etime(경과)으로 거꾸로 센다
    et = sh(["ps", "-o", "etime=", "-p", pids[0]]).strip()
    if not et:
        return None
    d, rest = (et.split("-") + [""])[:2] if "-" in et else ("0", et)
    parts = [int(x) for x in rest.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    secs = int(d) * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]
    return time.time() - secs


# ── a. 토큰 캐시 ─────────────────────────────────────────────
def worktrees():
    out = sh(["git", "-C", ROOT, "worktree", "list", "--porcelain"])
    return [ln.split(" ", 1)[1] for ln in out.splitlines() if ln.startswith("worktree ")]


def check_caches():
    started = main_started()
    dirs = worktrees()
    if not dirs:
        unsure.append("a. 폴더 목록을 못 얻었다 (git worktree list 가 비었다)")
        return
    if started is None:
        unsure.append("a. 8765 가 안 떠 있어 기동 시각을 못 쟀다 — 캐시 %d곳만 나열한다" % len(dirs))
    fresh = []
    for d in dirs:
        f = os.path.join(d, CACHE_REL)
        if not os.path.exists(f):
            continue
        mt = os.path.getmtime(f)
        is_main = os.path.realpath(d) == os.path.realpath(ROOT)
        stamp = time.strftime("%m-%d %H:%M", time.localtime(mt))
        if started is not None and mt >= started and not is_main:
            fresh.append("%s  %s" % (stamp, f))
        notes.append("  캐시  %s  %s%s" % (stamp, f, "  ← 메인" if is_main else ""))
    print("a. 토큰 캐시 — 폴더 %d곳 · 캐시 %d개%s"
          % (len(dirs), len([n for n in notes if n.startswith("  캐시")]),
             "" if started is None else " · 8765 기동 %s" % time.strftime("%m-%d %H:%M", time.localtime(started))))
    for n in notes:
        print(n)
    if fresh:
        bad.append("a. 8765 기동 뒤에 메인 밖에서 갱신된 토큰 캐시 %d개 — 직접 부르고 있거나 폴백이 돌았다 (d 와 함께 본다)\n     "
                   % len(fresh) + "\n     ".join(fresh))


# ── b·c. 등록 파일과 변수 이름 ───────────────────────────────
def plist_env(path):
    s = open(path, encoding="utf-8").read()
    m = re.search(r"<key>EnvironmentVariables</key>\s*<dict>(.*?)</dict>", s, re.S)
    if not m:
        return {}
    return dict(re.findall(r"<key>([A-Z_]+)</key>\s*<string>([^<]*)</string>", m.group(1)))


def port_of(name):
    m = re.search(r"-(\d+)\.plist$", name)
    return int(m.group(1)) if m else MAIN_PORT


def check_plists():
    files = sorted(glob.glob(os.path.join(LAUNCHD, "kr.kjcstudio.*.plist")))
    allk = [f for f in files if "kis-proxy" in os.path.basename(f) or "service" in os.path.basename(f)]
    targets = [f for f in allk if port_of(os.path.basename(f)) != MAIN_PORT]
    mains = [f for f in allk if port_of(os.path.basename(f)) == MAIN_PORT]
    if not targets or not mains:
        unsure.append("b. launchd/ 에 kis-proxy·service plist 가 모자란다(8765 %d · 그 밖 %d) — 본 것이 없다"
                      % (len(mains), len(targets)))
        return None
    names = set()
    missing, differ, notinst, serve_missing, serve_wrong = [], [], [], [], []
    for f in allk:
        env = plist_env(f)
        send = [k for k in env if k.endswith("UPSTREAM")]          # 보내는 쪽
        serve = [k for k in env if k.endswith("UPSTREAM_SERVE")]   # 받는 쪽
        names.update(send + serve)
        base = os.path.basename(f)
        if f in mains:
            if not serve:
                serve_missing.append(base)
            if send:
                serve_wrong.append(base + "(받는 쪽인데 보내는 변수가 있다 — 자기에게 넘긴다)")
        else:
            if not send:
                missing.append(base)
            if serve:
                serve_wrong.append(base + "(보내는 쪽인데 받는 변수가 있다)")
        inst = os.path.join(INSTALLED, base)
        if not os.path.exists(inst):
            notinst.append(base)
        elif open(inst, encoding="utf-8").read() != open(f, encoding="utf-8").read():
            differ.append(base)
    print("b. 등록 파일 — 보내는 쪽 %d개 중 변수 있음 %d · 받는 쪽(8765) %d개 중 SERVE 있음 %d · 설치본 다름 %d · 미설치 %d"
          % (len(targets), len(targets) - len(missing), len(mains), len(mains) - len(serve_missing),
             len(differ), len(notinst)))
    if missing:
        bad.append("b. 보내는 변수가 없는 plist: " + ", ".join(missing))
    if serve_missing:
        bad.append("b. 8765 plist 에 받는 변수(*UPSTREAM_SERVE)가 없다 — 보내는 쪽이 전부 404 → 폴백 → 아무것도 안 모인다: "
                   + ", ".join(serve_missing))
    if serve_wrong:
        bad.append("b. 역할이 뒤집힌 plist: " + ", ".join(serve_wrong))
    if differ or notinst:
        unsure.append("b. 설치본이 저장소와 다르다(아직 안 올렸거나 손으로 고쳤다): "
                      + ", ".join(differ + [n + "(미설치)" for n in notinst])
                      + "\n     → 재권님이 launchd/install.command <포트> 로 올리신다")
    sends = {n for n in names if n.endswith("UPSTREAM")}
    if len(sends) > 1:
        bad.append("c. plist 끼리 보내는 변수 이름이 갈린다: " + ", ".join(sorted(sends)))
    return names


def check_name(names):
    if not names:
        unsure.append("c. plist 에 상류 변수가 하나도 없어 이름을 대조할 수 없다")
        return
    src = open(PROXY, encoding="utf-8").read()
    read = set(re.findall(r"os\.(?:environ\.get|getenv)\(\s*[\"']([A-Z_]*UPSTREAM[A-Z_]*)[\"']", src))
    print("c. 변수 이름 — plist %s · kis_proxy.py %s"
          % (", ".join(sorted(names)), ", ".join(sorted(read)) or "(아직 안 읽는다)"))
    if not read:
        unsure.append("c. kis_proxy.py 가 아직 상류 변수를 안 읽는다 — 코드가 들어오기 전이다 (「아직」)")
    elif names != read:
        bad.append("c. 이름이 갈린다 — plist %s ↔ kis_proxy.py %s" % (sorted(names), sorted(read)))


# ── d. 살아 있는 서버 ────────────────────────────────────────
def check_live():
    ports = sorted({port_of(os.path.basename(f))
                    for f in glob.glob(os.path.join(LAUNCHD, "kr.kjcstudio.*.plist"))
                    if "kis-proxy" in f or "service" in f})
    seen, using, fallback = 0, [], []
    for p in ports:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/api/kis/stats" % p, timeout=2) as r:
                data = json.load(r).get("data", {})
        except Exception:
            continue
        seen += 1
        if "upstream" not in data:
            continue
        if p != MAIN_PORT and not data.get("upstream"):
            using.append(p)
        if data.get("upstreamFallbacks"):
            fallback.append("%d(%s건)" % (p, data["upstreamFallbacks"]))
    print("d. 살아 있는 서버 — 응답 %d/%d" % (seen, len(ports)))
    if seen == 0:
        unsure.append("d. 응답하는 서버가 없다")
    if using:
        bad.append("d. 상류를 안 쓰는 서버: " + ", ".join(str(p) for p in using))
    if fallback:
        unsure.append("d. 폴백이 돈 서버 — 8765 가 죽어 있었던 때가 있다: " + ", ".join(fallback))


def main():
    print("── KIS 를 8765 하나로 — 검사 ──────────────────────────")
    check_caches()
    names = check_plists()
    check_name(names or set())
    check_live()
    print()
    for u in unsure:
        print("  ？ " + u)
    for b in bad:
        print("  ✗ " + b)
    if bad:
        print("\n  어긋남 %d" % len(bad))
        return 1
    if unsure:
        print("\n  어긋남 0 · 못 잰 것 %d — 「통과」 가 아니다" % len(unsure))
        return 2
    print("\n  통과 — KIS 를 부르는 자리가 8765 하나다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
