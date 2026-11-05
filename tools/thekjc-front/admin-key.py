#!/usr/bin/env python3
"""thekjc.co.kr 앞문 서버(가비아 thekjc-front)의 관리 열쇠 — 잠가 보관 · 1년마다 갈기 · 알림.

    python3 tools/thekjc-front/admin-key.py status      마지막으로 갈고 잠가 보낸 날 · 지난 날 수
    python3 tools/thekjc-front/admin-key.py rotate      새 열쇠를 만들어 서버에 넣고 · 새 것으로 들어가지는지 잰 뒤 · 옛 것을 뺀다
    python3 tools/thekjc-front/admin-key.py seal        열쇠를 AES-256 으로 잠근 파일을 바탕화면에 만든다(비밀번호를 묻는다 — 재권님이 친다)
    python3 tools/thekjc-front/admin-key.py sent        「메일로 보냈다」 를 적는다(재권님이 보내신 뒤)
    python3 tools/thekjc-front/admin-key.py remind      갈 때가 됐으면 텔레그램 한 통(launchd 가 부른다 · --send + KJC_ROLE=server 일 때만)
    python3 tools/thekjc-front/admin-key.py open <잠근 파일>   잠근 파일을 풀어 열쇠로 되돌린다(사고 때)

**seal · open 은 비밀번호를 화면에 안 보이게 묻는다 — 세션이 아니라 재권님이 친다.** Claude 창의 `!` 로는 안 된다(키보드 입력 창이 없어 멈춘다 · 2026-11-04 잼) — 맥 터미널 앱에서 친다. 세션은 `osascript` 로 터미널 창을 띄워 줄 수 있다.
비밀번호는 저장소 · 보드 · 메시지 · 메일 본문 어디에도 두지 않는다.
룰은 CLAUDE.md 「thekjc.co.kr 앞문 서버 — 관리 열쇠는 잠가 메일에 · 1년마다 간다 · GitHub 에는 설정만」. 다시 세우는 순서는 같은 폴더 README.md.
"""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "1.201.111.167"
USER = "ubuntu"
SSH_DIR = os.path.expanduser("~/.ssh")
KEY = os.path.join(SSH_DIR, "thekjc-front.pem")
STATE = os.path.join(SSH_DIR, "thekjc-front.state.json")   # 비밀이 아니다 — 날짜만. 저장소 밖(열쇠 곁)에 둔다
RENEW_DAYS = 365                                            # 재권님 「1년단위로 갱신」 (2026-11-04)
CIPHER = ["-aes-256-cbc", "-pbkdf2", "-iter", "600000", "-salt"]   # 맥 기본 openssl(LibreSSL)로 잠그고 풀린다 — 2026-11-04 잼
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def now():
    return dt.datetime.now().astimezone()


def load():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(st):
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def ssh(key, cmd, timeout=20):
    return subprocess.run(["ssh", "-i", key, "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
                           "-o", "ConnectTimeout=10", "%s@%s" % (USER, HOST), cmd],
                          capture_output=True, text=True, timeout=timeout)


def age_days(st):
    """갈고 잠가 보낸 날 중 늦은 쪽이 아니라 — **보낸 날**이 기준이다. 갈기만 하고 안 보냈으면 메일 사본이 옛 열쇠다."""
    at = st.get("sent_at")
    if not at:
        return None
    return (now() - dt.datetime.fromisoformat(at)).days


def cmd_status(_):
    st = load()
    for k, name in (("rotated_at", "열쇠를 간 날"), ("sealed_at", "잠근 파일을 만든 날"), ("sent_at", "메일로 보낸 날")):
        print("%-14s %s" % (name, st.get(k) or "기록 없음"))
    d = age_days(st)
    if d is None:
        print("판정          메일로 보낸 기록이 없습니다 — seal 뒤 보내고 sent 를 적으십시오")
        return 1
    print("판정          보낸 지 %d일 · %s" % (d, "갈 때입니다" if d >= RENEW_DAYS else "%d일 남음" % (RENEW_DAYS - d)))
    if st.get("rotated_at", "") > st.get("sent_at", ""):
        print("주의          보낸 뒤 열쇠를 갈았습니다 — 메일 사본은 옛 열쇠입니다. seal · 보내기 · sent 를 다시")
        return 1
    return 0


def cmd_rotate(_):
    if not os.path.exists(KEY):
        print("지금 열쇠가 없습니다: %s — 사고 대응은 README.md 「열쇠를 잃었을 때」" % KEY)
        return 2
    if ssh(KEY, "true").returncode != 0:
        print("지금 열쇠로 서버에 못 들어갑니다 — 사무실 인터넷인지 · 보안 그룹 22번 IP 부터 보십시오")
        return 2
    stamp = now().strftime("%Y%m%d")
    new = KEY + ".new"
    for p in (new, new + ".pub"):
        if os.path.exists(p):
            os.remove(p)
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "thekjc-front-admin-" + stamp, "-f", new], check=True)
    pub = open(new + ".pub", encoding="utf-8").read().strip()
    old_pub = subprocess.run(["ssh-keygen", "-y", "-f", KEY], capture_output=True, text=True, check=True).stdout.split()[1]
    # 1) 새 것을 더한다 2) 새 것으로 들어가 본다 3) 그 뒤에만 옛 것을 뺀다 — 순서가 바뀌면 문이 잠긴다
    r = ssh(KEY, "printf '%%s\\n' '%s' >> ~/.ssh/authorized_keys" % pub)
    if r.returncode != 0:
        print("새 열쇠를 서버에 못 넣었습니다: %s" % r.stderr.strip()[:200])
        return 1
    if ssh(new, "true").returncode != 0:
        print("새 열쇠로 못 들어갑니다 — 옛 열쇠를 그대로 둡니다(서버에는 새 줄이 더해진 채)")
        return 1
    r = ssh(new, "grep -v -F '%s' ~/.ssh/authorized_keys | sed '/^$/d' > ~/.ssh/ak.tmp && mv ~/.ssh/ak.tmp ~/.ssh/authorized_keys "
                 "&& chmod 600 ~/.ssh/authorized_keys && wc -l < ~/.ssh/authorized_keys" % old_pub)
    if r.returncode != 0:
        print("옛 열쇠를 못 뺐습니다 — 새 열쇠는 들어가집니다: %s" % r.stderr.strip()[:200])
        return 1
    keep = KEY + ".old-" + stamp
    shutil.move(KEY, keep)
    shutil.move(new, KEY)
    os.chmod(KEY, 0o600)
    os.replace(new + ".pub", KEY + ".pub")
    if ssh(KEY, "true").returncode != 0:
        print("⚠ 자리를 바꾼 뒤 못 들어갑니다 — 옛 열쇠 %s 는 서버에서 이미 빠졌습니다. README.md 「열쇠를 잃었을 때」" % keep)
        return 1
    os.remove(keep)
    st = load()
    st["rotated_at"] = now().isoformat(timespec="seconds")
    save(st)
    print("열쇠를 갈았습니다 — 새 것으로 들어가지고 옛 것은 서버와 맥미니에서 지웠습니다(서버 열쇠 줄 %s)" % r.stdout.strip())
    print("다음: 잠근 파일 만들기 — 맥 터미널 앱에서 `cd /Users/kjc/work/KJCStudio && python3 tools/thekjc-front/admin-key.py seal`")
    return 0


def cmd_seal(_):
    if not os.path.exists(KEY):
        print("열쇠가 없습니다: %s" % KEY)
        return 2
    if not sys.stdin.isatty():
        print("비밀번호를 화면에 안 보이게 물어야 해서 키보드 입력 창이 있어야 합니다 — Claude 창의 `!` 로는 안 됩니다. 맥 터미널 앱에서 `cd /Users/kjc/work/KJCStudio && python3 tools/thekjc-front/admin-key.py seal` 로 쳐 주십시오")
        return 2
    out = os.path.expanduser("~/Desktop/thekjc-열쇠-%s.enc" % now().strftime("%Y%m%d"))
    print("잠글 비밀번호를 두 번 묻습니다 — 화면에 안 보입니다. 이 비밀번호는 수첩에만 적고 메일에는 쓰지 마십시오.")
    r = subprocess.run(["openssl", "enc"] + CIPHER + ["-in", KEY, "-out", out])
    if r.returncode != 0 or not os.path.exists(out):
        print("잠그지 못했습니다(비밀번호 두 번이 다르면 이렇게 됩니다)")
        return 1
    print("풀리는지 한 번 봅니다 — 방금 비밀번호를 한 번 더 넣으십시오.")
    chk = subprocess.run(["openssl", "enc", "-d"] + CIPHER[:-1] + ["-in", out], capture_output=True)
    if chk.returncode != 0 or chk.stdout != open(KEY, "rb").read():
        os.remove(out)
        print("풀어 보니 맞지 않습니다 — 파일을 지웠습니다. 다시 해 주십시오")
        return 1
    st = load()
    st["sealed_at"] = now().isoformat(timespec="seconds")
    save(st)
    print("잠근 파일: %s" % out)
    print("이 파일을 재권님 메일로 첨부해 보내신 뒤 바탕화면에서 지우시고, `python3 tools/thekjc-front/admin-key.py sent` 를 적습니다")
    return 0


def cmd_sent(_):
    st = load()
    if not st.get("sealed_at"):
        print("잠근 파일을 만든 기록이 없습니다 — seal 부터")
        return 1
    st["sent_at"] = now().isoformat(timespec="seconds")
    save(st)
    print("메일로 보낸 날을 적었습니다: %s · 다음 갈 날은 %d일 뒤" % (st["sent_at"], RENEW_DAYS))
    return 0


def cmd_open(a):
    if not sys.stdin.isatty():
        print("비밀번호를 화면에 안 보이게 물어야 해서 키보드 입력 창이 있어야 합니다 — Claude 창의 `!` 로는 안 됩니다. 맥 터미널 앱에서 `cd /Users/kjc/work/KJCStudio && python3 tools/thekjc-front/admin-key.py open <파일>` 로 쳐 주십시오")
        return 2
    out = KEY if not os.path.exists(KEY) else KEY + ".from-mail"
    r = subprocess.run(["openssl", "enc", "-d"] + CIPHER[:-1] + ["-in", a.file, "-out", out])
    if r.returncode != 0:
        if os.path.exists(out):
            os.remove(out)
        print("풀지 못했습니다 — 비밀번호를 확인하십시오")
        return 1
    os.chmod(out, 0o600)
    print("풀었습니다: %s · 들어가지는지: %s" % (out, "됨" if ssh(out, "true").returncode == 0 else "안 됨(사무실 인터넷인지 · 22번 IP)"))
    return 0


def cmd_remind(a):
    st = load()
    d = age_days(st)
    due = d is None or d >= RENEW_DAYS or st.get("rotated_at", "") > st.get("sent_at", "")
    if not due:
        print("갈 때가 아닙니다 — 보낸 지 %d일" % d)
        return 0
    why = "보낸 기록 없음" if d is None else ("보낸 뒤 갈았는데 다시 안 보냄" if d < RENEW_DAYS else "보낸 지 %d일" % d)
    text = ("[thekjc 서버] 관리 열쇠를 갈 때입니다 (%s)\n"
            "개념정의 창에 「thekjc 열쇠 갈아줘」 라고 하시면 새 열쇠로 바꾸고 잠근 파일을 만들어 드립니다 — 재권님은 메일로 보내시기만 하면 됩니다." % why)
    if not (a.send and os.environ.get("KJC_ROLE") == "server"):
        print("(보내지 않음 — --send · KJC_ROLE=server 일 때만) " + text)
        return 0
    sys.path.insert(0, os.path.join(ROOT, "holdings", "server"))
    import dart
    dart.NOTIFY_LOCAL = True
    ok, err = dart.telegram_send(text)
    print("보냄" if ok else "못 보냄: %s" % err)
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="thekjc 앞문 서버 관리 열쇠")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("rotate")
    sub.add_parser("seal")
    sub.add_parser("sent")
    p = sub.add_parser("remind")
    p.add_argument("--send", action="store_true")
    p = sub.add_parser("open")
    p.add_argument("file")
    a = ap.parse_args()
    return {"status": cmd_status, "rotate": cmd_rotate, "seal": cmd_seal, "sent": cmd_sent,
            "remind": cmd_remind, "open": cmd_open}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
