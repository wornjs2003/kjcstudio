# -*- coding: utf-8 -*-
"""파일을 **안전하게** 쓴다.

2026-09-22 지시 — 키 파일을 바로 덮어쓰는 세 곳을 고치라고 하셨다.

지금은 `write_json_atomic` 하나뿐이다. 공용 저장 층(`read_doc`·`write_doc`·
`list_docs`)은 설계를 올려 두었고 자리가 정해지면 이 파일 위에 얹는다 —
「가장 낮은 것 하나부터」 라 그 순서로 간다.


■ 왜 필요한가

저장소를 훑어 보니 **`os.replace` 와 `os.rename` 을 쓰는 곳이 하나도
없었다**(2026-09-22 실측). `open(path, "w")` 는 **여는 순간 파일을 비운다.**
거기서 프로그램이 죽거나 디스크가 차면 **원본도 새것도 없다.**

    holdings/server/setup_dart.py   secrets.json 을 바로 덮어씀
    holdings/server/setup_kis.py    〃
    holdings/server/kis_proxy.py    토큰 캐시를 바로 덮어씀

토큰 캐시는 깨져도 다시 받으면 된다. **`secrets.json` 은 깨지면 KIS·DART
키가 날아간다** — gitignore 라 저장소에도 없고 되살릴 곳이 없다.


■ 어떻게 막나

    ①  같은 폴더의 임시 파일에 다 쓴다
    ②  os.replace 로 제자리에 옮긴다     ← **원자적이다. 중간 상태가 없다**

**같은 폴더**여야 한다. 다른 드라이브로 `os.replace` 하면 원자성이 깨진다.

①에서 죽으면 원본은 손도 안 댄 상태다. ②는 쪼개지지 않으므로 읽는 쪽은
**옛 내용이나 새 내용 중 하나**를 본다 — 반쪽짜리를 보는 일이 없다.


■ 키를 다루므로

**값을 예외 메시지에 싣지 않는다.** 실패하면 경로만 말한다.
9월 14일에 OpenDART 키가 오류 메시지로 샌 적이 있다.
"""

import io
import json
import os
import tempfile
import time


def _replace_with_retry(tmp, path, tries=12):
    """`os.replace` 를 다시 해 본다. **윈도우라서 필요하다.**

    2026-09-22 실측 — 읽는 쪽 넷이 계속 열었다 닫는 동안 쓰기를 20번 했더니
    **`PermissionError: [WinError 5]` 로 죽었다.**

    윈도우는 **그 파일을 열어 둔 프로세스가 있으면 rename 을 막는다.**
    POSIX 는 막지 않아서, 리눅스에서만 재 봤으면 못 봤을 자리다.

    읽기는 아주 짧으므로 잠깐 기다렸다 다시 하면 된다. 12번(총 0.78초)
    안에 안 되면 올려보낸다 — 조용히 넘기면 **안 써졌는데 썼다고 믿는다.**

    이것은 원자성을 깨지 않는다. `os.replace` 자체는 여전히 쪼개지지 않고,
    **되냐 안 되냐만** 다시 묻는 것이다.
    """
    for i in range(tries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(0.01 * (i + 1))


def write_json_atomic(path, data, indent=2):
    """`data` 를 `path` 에 JSON 으로 **안전하게** 쓴다.

    쓰다가 죽어도 `path` 는 **옛 내용 그대로** 남는다.

    비어 있는 것(None · {} · [])은 **쓰지 않고** False 를 돌려준다.
    빈 값으로 덮는 것이 가장 흔한 사고인데, 그때는 파일이 멀쩡해 보여서
    눈치채기 어렵다 — 「없다」 와 「빈 값이 들어왔다」 를 여기서 가른다.

    Returns:
        True  썼다
        False 비어 있어서 안 썼다
    """
    if data is None or (isinstance(data, (dict, list, str)) and len(data) == 0):
        return False

    path = os.path.abspath(path)
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)

    body = json.dumps(data, ensure_ascii=False, indent=indent) + "\n"

    # 같은 폴더에 만든다 — 다른 드라이브로 옮기면 원자성이 깨진다
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".tmp-", suffix=".json")
    try:
        with io.open(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
            f.flush()
            # 디스크까지 내려보낸다. 여기까지 와야 ② 가 의미가 있다 —
            # 캐시에만 있으면 전원이 끊길 때 빈 파일이 남을 수 있다
            os.fsync(f.fileno())
        _replace_with_retry(tmp, path)
        return True
    except Exception:
        # 임시 파일을 남기지 않는다. 지우기에 실패해도 원본은 멀쩡하다
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        # **값을 싣지 않는다.** 경로만 올려보낸다
        raise IOError("파일을 쓰지 못했습니다: %s" % path)


def read_json(path, default=None):
    """읽는다. 없거나 깨졌으면 `default` 를 돌려준다.

    깨진 파일을 예외로 올리면 부르는 쪽마다 try 를 쓰게 된다.
    여기서 한 번만 가른다.
    """
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default
