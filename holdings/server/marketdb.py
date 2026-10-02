# -*- coding: utf-8 -*-
"""`market.db` 의 자리와 여는 법을 한 곳에서 정한다 (2026-10-01 지시).

**왜 한 곳인가** — 전에는 경로를 **네 파일이 각자 조립**했다 (`dart.py` ·
`kis_proxy.py` · `news_store.py` · `naver.py`). 넷 다 `HOLDINGS_DIR/market.db` 라
**폴더마다 DB 가 따로 쌓였다** — 2026-10-01 실측으로 **일곱 곳 78MB** 였고,
8764 와 8765 가 같은 5분봉을 각자 받고 있었다.

「같은 값은 한 곳에만 둔다」 의 자리다. `RATE_FILE` 을 홈 기준으로 고친 것과 같은 모양.

## 여기서 정하는 셋

    경로            `KJC_DB_PATH` · 없으면 지금까지처럼 폴더 기준
    journal_mode    **WAL** — 여럿이 읽는 동안 하나가 쓴다
    쓰기 가능 여부   `KJC_DB_READONLY`

**`journal_mode` 는 소스 어디에도 없었다** (홈페이지_정리 실측). 기본값 `delete` 로
돌고 있었으므로 WAL 은 **「되돌리기」 가 아니라 처음 정하는 것**이다.

## ⚠️ 깃발과 실패는 다르다 (홈페이지_정리 지적)

`writable()` 은 **「안 해 본다」 를 정할 뿐**이다. 깃발이 켜진 서버에서도
디스크 · 권한 · 잠금으로 **쓰기가 실패할 수 있고**, 그때 호출 쪽에 `try` 가 없으면
**그대로 터진다** — 2026-10-01 실측으로 `save_candles` 를 부르는 네 자리 중
**셋이 `try` 없이** 부르고 있었다(`1397` · `1601` · `3330`).

**그래서 쓰는 쪽은 `writable()` 을 보고 그 위에 예외도 잡는다.** 둘 다 해야 한다.

## 왜 읽기 전용이 안전한가

세션 서버와 서비스방은 **확인용**이고 받아오는 자리는 8765 하나로 모였다.
2026-10-01 실측 — 주기 여섯 전부에서 **서비스방에만 있는 종목이 0개**이고
5분봉은 메인 189 > 서비스방 115 라, 읽기 전용으로 바꿔도 **잃는 것이 없다.**

**완전 공유(쓰기도 여럿)로 가지 않는 이유**는 `dart.py` 에 이미 적혀 있다 —
「같은 `market.db` 를 여러 서버가 쓰면 그때부터 난다」(공시 중복 발송).
**쓰는 것이 하나뿐이면 그 위험이 생기지 않는다.**
"""

import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
HOLDINGS_DIR = os.path.dirname(HERE)

#: `market.db` 의 자리. **이 줄이 유일한 기준이다** — 다른 파일에서 조립하지 않는다.
DB_PATH = (os.environ.get("KJC_DB_PATH") or "").strip() \
    or os.path.join(HOLDINGS_DIR, "market.db")

#: 이 서버가 DB 에 쓰지 않는가. 받아오는 자리(8765)만 쓰고 나머지는 읽기만 한다.
READONLY = (os.environ.get("KJC_DB_READONLY") or "").strip().lower() in (
    "1", "true", "yes", "on")

_journal_done = False


def writable():
    """이 서버가 DB 에 **써도 되는가**.

    ⚠️ 「쓰기가 실제로 됐는가」 가 아니다 — 위 「깃발과 실패는 다르다」 참고.
    """
    return not READONLY


def connect(timeout=10):
    """`market.db` 를 연다. 읽기 전용 서버면 `mode=ro` 로 연다.

    `mode=ro` 는 **없는 파일을 만들지 않는다.** 그냥 `sqlite3.connect` 는
    **없으면 만들어서**, 2026-10-01 에 남의 폴더를 들여다보다 0바이트 파일을
    하나 만든 일이 있었다.
    """
    if READONLY:
        conn = sqlite3.connect(
            "file:%s?mode=ro" % DB_PATH, uri=True, timeout=timeout)
    else:
        conn = sqlite3.connect(DB_PATH, timeout=timeout)
        _ensure_journal(conn)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_journal(conn):
    """`journal_mode` 를 **WAL** 로 한 번만 맞춘다.

    여럿이 읽는 동안 하나가 쓸 수 있다. 읽기 전용 연결에서는 바꿀 수 없으므로
    **쓰는 서버에서만** 부른다. 실패해도 그냥 간다 — 모드가 `delete` 로 남을 뿐
    동작은 한다.
    """
    global _journal_done
    if _journal_done:
        return
    _journal_done = True
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error:
        pass
    # ⚠️ WAL 을 켜면 최근 쓰기가 `market.db-wal` 에 먼저 들어간다. 폴더를 새로
    # 만들 때 **본체만 복사하면 그만큼 잃는다** — `.worktreeinclude` 가 `-wal` 을
    # 함께 가져가도록 해 두었다 (2026-10-01 · 홈페이지_정리가 찾음).


def describe():
    """지금 무엇을 쓰고 있는지 한 줄. 서버가 뜰 때 찍는다."""
    return "market.db %s%s" % (
        DB_PATH, "  (읽기 전용)" if READONLY else "")
