# -*- coding: utf-8 -*-
"""수정 비밀번호 — 정해 둔 보드 문서는 재권님만 고친다 (2026-11-11).

재권님(시황분석1 창 16:4x) 「나 수정비밀번호를 넣는 방향으로 해」 · 개발3 창 「수정비밀번호 숫자 6자를 눌러주세요 라고 뜨게해줘」 →
안에 「응 해」(17:0x). 첫 문서는 투자 전략 룰(strategy-rules).

    지키는 문서   PROTECTED — PUT /api/board/doc/<이름> 은 머리글 `X-Edit-Key` 가 맞을 때만 받는다 · GET 은 그대로
    맞는지 묻기   POST /api/board/edit-check  {"doc": "<이름>"} + 같은 머리글 → {"ok": true} · 아니면 403
    값            숫자 6자. 열쇠 파일(secrets_guard.secrets_path)에는 섞은 값만 — strategyEditSalt · strategyEditHash
                 (PBKDF2-SHA256). 숫자 그대로는 어디에도 두지 않는다
    잠금          MAX_FAIL 번 틀리면 LOCK_SEC 초 동안 맞아도 403 + locked(남은 초) — 숫자 6자는 백만 가지라 다 넣어 볼 수 있다
                 셈은 이 프로세스 안에서만 한다(세션 서버는 보드를 8765 로 넘기므로 8765 한 곳에 모인다)

비밀번호를 정하거나 바꾸는 것은 재권님이 맥 터미널에서 직접 한다 — 세션은 숫자를 보지도 주고받지도 않는다.

    python3 holdings/server/edit_key.py set       숫자 6자를 두 번 묻고(화면에 안 보임) 섞은 값을 열쇠 파일에 넣는다
    python3 holdings/server/edit_key.py status    정해져 있나만 낸다

바꾼 값은 서버를 다시 띄우지 않아도 다음 확인부터 듣는다(열쇠 파일을 그때그때 읽는다).
"""

import getpass
import hashlib
import hmac
import json
import os
import re
import sys
import threading
import time

from secrets_guard import secrets_path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROTECTED = frozenset({"strategy-rules"})
HEADER = "X-Edit-Key"
MAX_FAIL = 5
LOCK_SEC = 600
ITER = 200000
KEY_SALT, KEY_HASH = "strategyEditSalt", "strategyEditHash"
CODE_RE = re.compile(r"^[0-9]{6}$")

_lock = threading.Lock()
_fails = 0
_locked_until = 0.0


def _stored():
    """(salt, hash) — 아직 안 정했거나 못 읽으면 (None, None)."""
    try:
        with open(secrets_path(), encoding="utf-8") as f:
            s = json.load(f)
    except Exception:
        return None, None
    return s.get(KEY_SALT) or None, s.get(KEY_HASH) or None


def _digest(code, salt_hex):
    return hashlib.pbkdf2_hmac("sha256", code.encode("ascii"), bytes.fromhex(salt_hex), ITER).hex()


def is_set():
    salt, h = _stored()
    return bool(salt and h)


def check(code):
    """(ok, 까닭, 잠김 남은 초). 까닭은 화면에 보일 한국어."""
    global _fails, _locked_until
    with _lock:
        now = time.time()
        if now < _locked_until:
            return False, "여러 번 틀려 잠겼습니다", int(_locked_until - now) + 1
        salt, h = _stored()
        if not (salt and h):
            return False, "수정 비밀번호가 아직 정해지지 않았습니다", 0
        good = bool(isinstance(code, str) and CODE_RE.match(code)) and hmac.compare_digest(_digest(code, salt), h)
        if good:
            _fails = 0
            return True, "", 0
        _fails += 1
        if _fails >= MAX_FAIL:
            _fails = 0
            _locked_until = now + LOCK_SEC
            return False, "여러 번 틀려 잠겼습니다", LOCK_SEC
        return False, "수정 비밀번호가 맞지 않습니다", 0


def _set():
    a = getpass.getpass("수정 비밀번호 숫자 6자: ")
    if not CODE_RE.match(a):
        print("숫자 6자가 아닙니다 — 바꾸지 않았습니다")
        return 1
    if getpass.getpass("한 번 더: ") != a:
        print("두 번이 다릅니다 — 바꾸지 않았습니다")
        return 1
    path = secrets_path()
    with open(path, encoding="utf-8") as f:
        s = json.load(f)
    salt = os.urandom(16).hex()
    s[KEY_SALT], s[KEY_HASH] = salt, _digest(a, salt)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.chmod(tmp, os.stat(path).st_mode & 0o777)
    os.replace(tmp, path)
    print("정했습니다 — %s 에 섞은 값만 넣었습니다. 서버 재시작 없이 바로 듣습니다." % path)
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "set":
        sys.exit(_set())
    print("수정 비밀번호: " + ("정해져 있음" if is_set() else "아직 없음") + " · 열쇠 파일 " + secrets_path())
    sys.exit(0)
