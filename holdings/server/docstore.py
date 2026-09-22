# -*- coding: utf-8 -*-
"""파일을 **안전하게** 쓴다.

2026-09-22 지시 — 키 파일을 바로 덮어쓰는 세 곳을 고치라고 하셨다.

두 켜다.

    write_json_atomic   파일 하나를 안전하게 쓴다. 키 파일·토큰 캐시도 이것을 쓴다
    read_doc/write_doc  그 위에 얹은 **문서 층**. 이름으로 읽고 쓴다


■ 이 층이 아는 것과 모르는 것

    층이 안다        문서 하나를 안전하게 읽고 쓰기 · 이름 규칙 · 경로 · 직전 것 보관
    쓰는 쪽이 안다    **무엇을 목록으로 둘지 · 커서를 어디 둘지 · 며칠을 남길지**

`index.json` 도 **그냥 문서 하나**다. 부르는 쪽이 `write_doc("ai-analysis-index", …)`
로 쓰면 되고 이 층은 그것이 목록인지 모른다. 그래야 **안 쓰는 쪽이 안 쓰는 것을
지고 가지 않는다** — 데일리분석은 열 개뿐이라 목록도 커서도 안 쓴다.


■ 왜 다섯이 같은 것을 쓰는가

프로젝트 · AI 작업 · 검수 보드 셋에 AI 분석과 데일리분석이 더해져 **다섯**이다.
`CLAUDE.md` 「저장은 이 PC 안에만 둔다」 가 **이미 「세 번째라 걸린다」** 고 적어
두었고, 여기서 각자 만들면 복제가 다섯이 된다.

    한 곳에 모을 것   persistLocal · loadFromServer · syncToServer · serverAlive · 경로

**그중 아래 켜(서버 쪽)가 이 파일이다.** 위 켜(화면의 localStorage 동기화)는
보드 셋만 쓰므로 그쪽에 둔다 — 화면은 파일을 못 쓰고 서버는 localStorage 가 없다.


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


# ── 문서 층 ───────────────────────────────────────────────────
#
# 이름 규칙과 응답 모양은 **배포본 워커(`projects/worker/board-api.js`)를
# 그대로 흉내** 낸다. `CLAUDE.md` 가 그렇게 정해 뒀다 —
#
#     맥미니 서버가 나중에 같은 모양으로 응답하면 **화면은 한 줄도 안 고치고**
#     주소만 바꾸면 된다. 모양이 같아야 아래 공용 모듈에 분기가 안 생긴다.
#
# 그래서 새로 설계하지 않는다.

import re

# `board-api.js:264` 의 정규식과 **같은 규칙**이다. 한글은 못 쓴다.
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

# 경로는 **여기 한 곳**에서 정한다. 맥미니 서버가 생기면 이 줄만 고친다.
DOC_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "docs")
HISTORY_DIRNAME = "history"


class DocNameError(ValueError):
    """이름이 규칙에 안 맞는다. 부르는 쪽이 400 으로 돌려주면 된다."""


def _path(name):
    if not isinstance(name, str) or not NAME_RE.match(name):
        # **이름을 그대로 싣지 않는다.** `../` 같은 것이 로그에 남으면
        # 그 자체가 무엇을 시도했는지 알려준다. 길이만 적는다.
        raise DocNameError("문서 이름이 규칙에 안 맞습니다 (%d자). "
                           "영문·숫자·밑줄·붙임표 1~40자만 됩니다" % len(str(name)))
    return os.path.join(DOC_ROOT, name + ".json")


def read_doc(name):
    """문서를 읽는다. 없거나 깨졌으면 None.

    「없다」 와 「빈 것이 들어 있다」 는 다르다 — 빈 문서는 `write_doc` 이
    애초에 안 쓰므로, None 이면 **정말 없는 것**이다.
    """
    return read_json(_path(name), None)


def write_doc(name, data, history=True):
    """문서를 **안전하게** 쓴다.

    하는 일이 넷이고 **순서가 뜻을 가진다.**

        ①  이름을 검사한다
        ②  **빈 것이면 안 쓴다** — None · {} · [] · ""
        ③  history=True 면 원본을 history/ 로 **복사**
        ④  write_json_atomic 으로 제자리에

    **②가 ③보다 앞이다.** 빈 값이 들어오면 직전 것도 안 밀린다. 뒤집으면
    빈 값이 열 번 들어올 때 history 까지 빈 값으로 채워져 **되살릴 것이
    없어진다** (2026-09-22 에 `주식페이지_개발2` 와 정리한 자리).

    **history 는 「안전하게 쓴다」 의 일부지 정책이 아니다.** 며칠을 남길지는
    쓰는 쪽이 정한다 — 이 층은 오래된 것을 지우지 않는다.

    Returns:
        True  썼다
        False **비어 있어서 안 썼다** — 원본은 그대로다
    """
    path = _path(name)

    # ② 빈 것이면 여기서 멈춘다. write_json_atomic 도 같은 검사를 하지만,
    #    그쪽까지 가면 ③ 이 이미 돌아 history 가 밀린 뒤다.
    if data is None or (isinstance(data, (dict, list, str)) and len(data) == 0):
        return False

    # ③ 원본이 있으면 남긴다. **이동이 아니라 복사**다 —
    #    옮기면 그 순간 제자리가 비고, 거기서 죽으면 읽는 쪽은 빈 자리를 본다.
    if history and os.path.exists(path):
        try:
            hdir = os.path.join(DOC_ROOT, HISTORY_DIRNAME)
            os.makedirs(hdir, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            with io.open(path, "r", encoding="utf-8") as src:
                body = src.read()
            with io.open(os.path.join(hdir, "%s-%s.json" % (name, stamp)),
                         "w", encoding="utf-8", newline="\n") as dst:
                dst.write(body)
        except OSError:
            # 직전 것을 못 남겨도 **새 것은 쓴다.** 여기서 멈추면
            # 백업 실패가 저장 실패가 된다.
            pass

    return write_json_atomic(path, data)


def list_docs(prefix=""):
    """문서 이름 목록. `history/` 는 안 센다.

    파일이 곧 목록이다 — 따로 목록 파일을 두면 「파일은 있는데 목록에 없는」
    어긋남이 생긴다. 목록 파일이 필요한 쪽은 그것도 문서로 쓰면 된다.
    """
    try:
        names = os.listdir(DOC_ROOT)
    except OSError:
        return []
    out = []
    for f in names:
        if not f.endswith(".json"):
            continue
        n = f[:-5]
        if NAME_RE.match(n) and n.startswith(prefix):
            out.append(n)
    return sorted(out)


def list_history(name):
    """그 문서의 직전 것들. 오래된 것부터."""
    hdir = os.path.join(DOC_ROOT, HISTORY_DIRNAME)
    try:
        names = os.listdir(hdir)
    except OSError:
        return []
    head = name + "-"
    return sorted(f[:-5] for f in names if f.startswith(head) and f.endswith(".json"))
