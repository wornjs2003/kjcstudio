#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""git 에 안 담기는 것을 맥미니 안의 백업 폴더로 옮겨 둔다.

**왜 이것이 있나** — `.gitignore` 에 넣는 순간 그 파일은 **어디에도 사본이
없다.** GitHub 에도 없고 git 이력에도 없다. 지우면 되돌릴 방법이 없다.

**한 번 손으로 복사하는 것과 다르다.** 손으로 하면 그 사본이 그날부터
낡는다 — 그리고 **낡은 것은 조용하다.** 있는 줄 알고 있다가 필요한 날
옛것을 꺼내게 된다. 그래서 돌릴 수 있는 형태로 둔다.

⚠️ **같은 디스크다. 「백업」 이 막아 주는 것과 못 막는 것이 다르다.**

    막아 준다   **실수로 지운 것 · 덮어쓴 것**
    못 막는다   **그 디스크가 죽는 것** — 원본과 같이 죽는다

외장 디스크는 나중이다 (2026-09-30 지시 — 「폴더 하나 만들어서 거기에
먼저 넣어둬 외장디스크는 나중에」). **그때까지 이 한계가 그대로**이므로
여기 적어 둔다 — 안 적으면 다음 사람이 「백업이 있으니 됐다」 로 읽는다.

⚠️ **`secrets.json` 은 담지 않는다.** 「세션이 `secrets.json` 을 안 만진다 —
읽지도 고치지도 않는다」 가 룰이다. **읽어서 복사하는 것도 읽는 것이다.**
그 파일을 어떻게 백업할지는 재권님이 정하실 자리이고, 정해지면 여기 더한다.

**무엇을 담을지 목록을 박지 않는다.** `git status --ignored` 가 내주는 것을
쓴다 — `.gitignore` 에 줄이 하나 늘면 **저절로 들어온다.**
「검사 도구에 대상 값을 박지 않는다」 그대로다.
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.expanduser("~/kjc-backup")

# **담지 않는 것.** 이유가 서로 다르므로 함께 적어 둔다.
SKIP = {
    "holdings/secrets.json": "키 파일 — 세션이 만지지 않는다 (룰)",
    ".claude/deployed": "배포 기록 — PC 마다 따로 세는 것이 맞다",
}
SKIP_DIRS = ("__pycache__", ".claude/worktrees", "node_modules", ".DS_Store")

# **다시 만들 수 있는 것은 담지 않는다.** 「잃었을 때 다시 만들 수 있나」 가
# 정본과 사본을 가르는 기준이다 (「데이터와 백업은 맥미니가 정본이다」).
REBUILDABLE = {
    "uidata/icons": "tools/fetch-stock-icons.py 로 다시 받는다",
    "logs": "돌면서 다시 쌓인다",
    "holdings/server/__pycache__": "파이썬이 다시 만든다",
}


def ignored_paths():
    """git 이 무시하는 것을 git 에게 물어본다. 목록을 박지 않는다."""
    out = subprocess.run(
        ["git", "-C", ROOT, "status", "--porcelain", "--ignored=matching"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        print("git status 가 실패했습니다 (%d)" % out.returncode)
        return None
    paths = []
    for line in out.stdout.splitlines():
        if not line.startswith("!! "):
            continue
        p = line[3:].strip().strip('"').rstrip("/")
        if any(d in p for d in SKIP_DIRS):
            continue
        paths.append(p)
    return paths


def classify(paths):
    """담을 것 · 건너뛸 것 · 다시 만들 수 있는 것으로 가른다."""
    take, skip, rebuild = [], [], []
    for p in paths:
        if p in SKIP:
            skip.append((p, SKIP[p]))
        elif any(p == k or p.startswith(k + "/") for k in REBUILDABLE):
            key = next(k for k in REBUILDABLE if p == k or p.startswith(k + "/"))
            rebuild.append((p, REBUILDABLE[key]))
        else:
            take.append(p)
    return take, skip, rebuild


def copy_db(src, dst):
    """**돌고 있는 SQLite 는 통째로 복사하지 않는다.**

    `market.db` 는 `journal_mode = delete` 다. 그 모드에서 **쓰는 중에
    `shutil.copy2` 로 복사하면 찢어진 파일**이 나올 수 있다 — 쓰기 사이에
    걸리면 멀쩡해서, **통과했다고 방법이 맞은 것이 아니다.**

    2026-09-30 에 실제로 그 자리를 밟았다. 통째로 복사한 사본이
    `integrity_check` 를 통과했는데, **서버가 계속 쓰는 중**이었고 그저
    쓰기 사이에 걸린 것이었다. **한 번 통과한 것으로는 안 갈린다.**

    `.backup` 은 잠금을 잡고 **한 시점의 일관된 사본**을 만든다. 서버는
    그 동안 기다리기만 하고 죽지 않는다.
    """
    src_db = sqlite3.connect("file:%s?mode=ro" % src, uri=True)
    try:
        dst_db = sqlite3.connect(dst)
        try:
            src_db.backup(dst_db)
        finally:
            dst_db.close()
    finally:
        src_db.close()


def verify_db(path):
    """**내가 넣은 것을 내가 다시 읽지 않는다** — 열어서 물어본다."""
    try:
        db = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
        try:
            ok = db.execute("PRAGMA integrity_check").fetchone()[0]
            return ok == "ok"
        finally:
            db.close()
    except sqlite3.Error:
        return False


def size_of(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    n = 0
    for dirpath, _, files in os.walk(path):
        for f in files:
            try:
                n += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return n


def human(n):
    for unit in ("B", "K", "M", "G"):
        if n < 1024 or unit == "G":
            return "%.0f%s" % (n, unit) if unit != "B" else "%dB" % n
        n /= 1024.0


def main():
    dry = "--dry-run" in sys.argv

    paths = ignored_paths()
    if paths is None:
        return 2
    if not paths:
        # **「대상 0개」 를 `0` 으로 내지 않는다.** 셀 것이 없어서 나온 0 은
        # 「안 봤다」 다 — `.gitignore` 가 비었거나 범위가 틀린 것이다.
        print("담을 것이 **하나도 안 나왔습니다** — 범위를 의심하십시오.")
        print("  git -C %s status --ignored=matching 을 직접 돌려 보십시오." % ROOT)
        return 2

    take, skip, rebuild = classify(paths)

    stamp = time.strftime("%Y%m%d-%H%M")
    out_dir = os.path.join(DEST, stamp)

    print("백업 — %s" % ("재보기만 합니다 (--dry-run)" if dry else out_dir))
    print("  가져온 목록: git status --ignored (%d줄)" % len(paths))
    print()

    total = 0
    bad = []
    print("  담습니다:")
    for p in sorted(take):
        src = os.path.join(ROOT, p)
        if not os.path.exists(src):
            continue
        n = size_of(src)
        total += n
        print("    %-46s %6s" % (p, human(n)))
        if dry:
            continue
        dst = os.path.join(out_dir, p)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        elif p.endswith(".db"):
            copy_db(src, dst)
            if not verify_db(dst):
                bad.append(p)
        else:
            shutil.copy2(src, dst)

    if skip:
        print("\n  담지 않습니다 — 이유가 있습니다:")
        for p, why in sorted(skip):
            print("    %-46s %s" % (p, why))

    if rebuild:
        print("\n  담지 않습니다 — 다시 만들 수 있습니다:")
        seen = set()
        for p, why in sorted(rebuild):
            key = why
            if key in seen:
                continue
            seen.add(key)
            print("    %-46s %s" % (p.split("/")[0] + "/…", why))

    print("\n  합계 %s" % human(total))

    if dry:
        print("\n  실제로 담으려면 --dry-run 을 빼고 돌리십시오.")
        return 0

    if bad:
        # **담은 것이 깨졌으면 `0` 으로 끝내지 않는다.** 「담았다」 와
        # 「꺼낼 수 있다」 는 다른 이야기다.
        print("\n  ⚠️ **담았는데 안 읽힙니다** — 다시 돌리십시오:")
        for p in bad:
            print("      %s" % p)
        return 1

    # **회차 폴더까지 좁힌다.** 위(`DEST`)가 700 이라 들어갈 수는 없지만,
    # 나중에 백업을 외장으로 옮기면 그 권한이 따라간다.
    os.chmod(DEST, 0o700)
    os.chmod(out_dir, 0o700)
    print("  폴더 권한 700 (소유자만) — 회차 폴더까지")

    # **직전 것을 남긴다.** 회차를 쌓아 두면 실수로 지운 것을 되돌릴 수 있다.
    # `debugging/history/` 가 같은 방식이다.
    rounds = sorted(d for d in os.listdir(DEST)
                    if os.path.isdir(os.path.join(DEST, d)))
    print("  회차 %d개 — 가장 오래된 것 %s" % (len(rounds), rounds[0]))
    if len(rounds) > 7:
        print("  ⚠️ 회차가 일곱을 넘었습니다. 오래된 것을 지울지 정하십시오")
        print("     (자동으로 지우지 않습니다 — 되살릴 수 없는 쪽이라서입니다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
