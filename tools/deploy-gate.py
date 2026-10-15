# -*- coding: utf-8 -*-
"""옮기기 문턱 — 검수를 안 지난 커밋이 서비스방(8764) · 메인서버(8765)로 딸려 가지 않게 (2026-10-15 재권님 「응 해줘」).

계기 — 2026-10-15 하루에 두 번(17:54 sign.js · 18:55 개발2 투자자 모달) 창구가 `main` 을 통째로 옮기면서 **검수 전 커밋이
서비스방까지 갔다.** 「업무 흐름」 5번 「검수 대기 중이면 옮기기를 기다린다」 가 기억에만 있었다 — 한 번은 사고, 두 번은 구조다.
두 세션(`홈페이지_정리` · `작업우선순위`)이 안을 봤다.

    python3 tools/deploy-gate.py                     옮길 범위(service..main)를 본다 — service-deploy.command 가 옮기기 전에 부른다
    python3 tools/deploy-gate.py <A>..<B>            범위를 준다 — 8765 재시작 전에 창구가 「지난 재시작 커밋..main」 으로 손으로 돌린다

종료 — 0 통과 · 1 검수 통과 줄이 없는 커밋이 있다(안 옮긴다) · 2 못 봤다(보드 · git). **2 를 통과로 읽지 않는다** —
옮기기는 되돌릴 수 없는 쪽이라 못 보면 멈춘다(편집 게이트와 거꾸로).

셈 — 범위의 머지 아닌 커밋 중 **서비스에 닿는 파일**을 고친 것마다 보드에 검수 통과 줄이 있나 본다.
  · 닿는 파일 — 아래 `NOT_SERVED`(검수 대상이 아닌 것 · 「업무 흐름」 5번)를 **뺀 나머지 전부**. 닿는 폴더를 적지 않는다 —
    새 구역이 생기면 저절로 든다(「검사 도구에 대상 값을 박지 않는다」)
  · 검수 통과 줄 — 카드 메모의 「검수 통과(qa)」 · 「검수 통과(개념정의)」 줄. 그 줄의 해시는 **다 뽑는다**(`9f61f3d+5b3afa7` · 공백 ·
    가운뎃점). 해시가 머지 커밋(staging 머지)이면 그 머지로 들어온 묶음(첫 부모..그 머지) 전부를 통과로 친다
  · 누구 검수가 필요한가 — qa 는 늘. 개념정의는 **그 커밋의 카드 담당이 개념정의가 아닐 때** — 개념정의 자기 커밋은 qa 하나다
    (「업무 흐름」 5번). 담당은 post-commit 이 「커밋 <해시>」 를 적은 카드의 `who` 로 가른다 — 레인 표를 여기 또 적지 않는다.
    카드를 못 찾으면 둘 다 요구한다(안전한 쪽)
  · `Revert` 커밋과 그것이 되돌린 원본(같은 범위 안)은 뺀다 — 나가지 않은 것을 무른 것이다
  · **못 보는 것** — 그 통과 줄을 정말 그 검수 세션이 적었나(메모 줄에 쓴 세션이 안 남는다 · 「아직 검사가 없는 룰」 표)

넘기기 — 재권님이 그래도 옮기라 하시면 `KJC_DEPLOY_FORCE=1`. 쓴 것은 `logs/deploy-force.log` 에 한 줄 남는다(`KJC_MAIN_OK` 와 같은 모양).
보드를 못 읽어 멈췄으면 넘기기보다 **8765 를 먼저 띄운다** — 보드가 8765 에 있다.
"""
import datetime
import importlib.util
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# 검수 대상이 아닌 것 — 「업무 흐름」 5번(룰 문서 · tools/ · .claude/ · .githooks/ · kjcEngine/) + 서비스가 안 내는 자리
NOT_SERVED_DIRS = ("tools/", ".claude/", ".githooks/", "launchd/", "kjcEngine/", "temp/",
                   "debugging/")   # debugging 은 서비스방에서 8093 으로 넘겨 외부접속에 안 닿는다(「상단 메뉴 구성」)
QA, DEF = "검수 통과(qa)", "검수 통과(개념정의)"
HEX = re.compile(r"(?<![0-9A-Za-z])[0-9a-f]{7,40}(?![0-9A-Za-z])")


def served(path):
    if path.endswith(".md") or path.startswith(NOT_SERVED_DIRS):
        return False
    if "/" not in path and path.startswith("."):       # 루트 점 파일(.gitignore · .worktreeinclude …)
        return False
    return True


def git(*a):
    return subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True, check=True).stdout


def full(h):
    r = subprocess.run(["git", "-C", ROOT, "rev-parse", "--verify", "--quiet", h + "^{commit}"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def board_cards():
    spec = importlib.util.spec_from_file_location("board_card", os.path.join(ROOT, "tools", "board-card.py"))
    bc = importlib.util.module_from_spec(spec)
    src = open(spec.origin, encoding="utf-8").read().replace('\nif __name__ == "__main__":', "\nif False:")
    exec(compile(src, spec.origin, "exec"), bc.__dict__)
    doc, _ = bc.read()
    return bc.tasks(doc)


def main(argv):
    rng = argv[0] if argv else "service..main"
    if ".." not in rng:
        print("쓰는 법: python3 tools/deploy-gate.py [<A>..<B>]")
        return 2
    try:
        commits = git("rev-list", "--no-merges", rng).split()
    except subprocess.CalledProcessError as e:
        print("✗ 못 봤다 — git 범위를 못 읽었다(%s): %s" % (rng, (e.stderr or "").strip()[:120]))
        return 2
    if not commits:
        print("옮길 커밋이 없다(%s)" % rng)
        return 0

    # Revert 와 그 원본을 뺀다
    drop = set()
    for c in commits:
        body = git("log", "-1", "--format=%B", c)
        m = re.search(r"This reverts commit ([0-9a-f]{7,40})", body)
        if m:
            orig = full(m.group(1))
            drop.add(c)
            if orig in commits:
                drop.add(orig)
            # staging 은 걸린 것을 **머지째** 되돌린다(「Revert "staging 에 … 합침"」) — 그 머지로 들어온 묶음도 뺀다.
            # 고친 판이 다시 올라오면 그 판(되살림 커밋)이 제 통과 줄을 받는다
            if orig:
                ps = git("rev-list", "--parents", "-n", "1", orig).split()[1:]
                if len(ps) > 1:
                    drop.update(x for x in git("rev-list", "%s..%s" % (ps[0], orig)).split() if x in commits)

    need = []
    for c in commits:
        if c in drop:
            continue
        files = [f for f in git("diff-tree", "--no-commit-id", "--name-only", "-r", c).split("\n") if f]
        hit = [f for f in files if served(f)]
        if hit:
            need.append((c, hit))
    if not need:
        print("통과 — 서비스에 닿는 커밋이 없다(%s · 커밋 %d)" % (rng, len(commits)))
        return 0

    try:
        cards = board_cards()
    except Exception as e:                      # 보드를 못 읽었다 — 「없다」 가 아니라 「못 봤다」
        print("✗ 못 봤다 — 보드를 못 읽었다(%s). 옮기지 않는다." % type(e).__name__)
        print("  보드는 8765 에 있다 — 8765 를 먼저 띄운다(KJC_DEPLOY_FORCE 가 아니라)")
        return 2

    # 통과 줄 → 통과로 칠 커밋 묶음
    passed = {QA: set(), DEF: set()}
    for t in cards:
        for ln in (t.get("memo") or "").splitlines():
            for kind in (QA, DEF):
                if kind not in ln:
                    continue
                for h in HEX.findall(ln):
                    f = full(h)
                    if not f:
                        continue
                    parents = git("rev-list", "--parents", "-n", "1", f).split()[1:]
                    if len(parents) > 1:              # 머지 — 그 머지로 들어온 묶음 전부
                        passed[kind].update(git("rev-list", "%s..%s" % (parents[0], f)).split())
                    else:
                        passed[kind].add(f)

    def owner(c):
        """post-commit 이 「커밋 <해시>」 를 적은 카드의 담당 — 없으면 None."""
        short = c[:7]
        for t in cards:
            memo = t.get("memo") or ""
            if re.search(r"커밋 %s" % short, memo) and "(추정)커밋 %s" % short not in memo:
                return t.get("who")
        return None

    bad = []
    for c, hit in need:
        who = owner(c)
        want = [QA] if who == "개념정의" else [QA, DEF]
        miss = [k for k in want if c not in passed[k]]
        if miss:
            bad.append((c, hit, who, miss))

    if not bad:
        print("통과 — 서비스에 닿는 커밋 %d 개 모두 검수 통과 줄이 있다(%s)" % (len(need), rng))
        return 0

    print("✗ 검수 통과 줄이 없는 커밋이 있다 — 옮기지 않는다(%s)" % rng)
    for c, hit, who, miss in bad:
        subj = git("log", "-1", "--format=%s", c).strip()[:60]
        print("  %s  %s" % (c[:7], subj))
        print("      담당 %s · 없는 줄: %s · 닿는 파일: %s%s" % (who or "카드 못 찾음", " · ".join(miss),
              " · ".join(hit[:4]), " 외 %d" % (len(hit) - 4) if len(hit) > 4 else ""))
    if os.environ.get("KJC_DEPLOY_FORCE") == "1":
        os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
        with open(os.path.join(ROOT, "logs", "deploy-force.log"), "a", encoding="utf-8") as f:
            f.write("%s · %s · %s\n" % (datetime.datetime.now().isoformat(timespec="seconds"), rng,
                                        " ".join(c[:7] for c, *_ in bad)))
        print("  KJC_DEPLOY_FORCE=1 — 재권님 지시로 넘긴다(logs/deploy-force.log 에 남김)")
        return 0
    print("  검수가 끝나면 다시. 재권님이 그래도 옮기라 하시면 KJC_DEPLOY_FORCE=1")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
