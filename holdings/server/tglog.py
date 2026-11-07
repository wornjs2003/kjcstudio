# -*- coding: utf-8 -*-
"""오늘 보낸 텔레그램 글 — 기록 한 곳 (2026-10-26 재권님 「응 그렇게 해」 · 작업우선순위 경유).

데일리분석 모달의 「데일리분석」 칸이 **그날 텔레그램으로 간 글**(과 꺼진 스위치 때문에 안 간 글)을 보낸 순서로 보인다.
그 목록을 여기 한 곳에 쌓고 `GET /api/telegram/today?day=YYYYMMDD` 로 낸다.

    어디서 쌓나   ① `dart.telegram_send` — **모든 발송이 이 함수 하나를 지난다**(아침 글 · 뉴스 · 공시 · 신호 · 결과 · 볼린저 ·
                  장 전 거래량 — 2026-10-26 셈). 보냄 · 조용한 시간 · 실패를 그 자리에서 적는다
                  ② 꺼진 스위치 자리(signal_watch 의 EXTRA_SEND · BB_SEND · events.SEND · nxt_pre.SEND) — 「꺼짐」 으로 적는다.
                  안 적으면 「안 보냈다」 와 「안 났다」 가 화면에서 안 갈린다
    종류          글 첫 줄의 머리(📊 데일리분석 · 📢 · [키워드] · 🔔 … 반등 신호 …)로 가른다 — 부르는 쪽을 안 고치고 한 곳에서.
                  새 알림이 생겨 머리가 안 맞으면 「알림」 으로 들어간다(빠지지 않는다)
    쓰기          **쓰기 서버(8765)만** — 읽기 전용 서버는 적지 않는다(그 서버는 보내지도 않는다). 기록이 실패해도 발송은 안 막는다
    보관          KEEP_DAYS 일 — 그 앞은 쓸 때 지운다
"""

import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import marketdb

KST = timezone(timedelta(hours=9))
KEEP_DAYS = 30
_lock = threading.Lock()

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS tg_log (
         id     INTEGER PRIMARY KEY AUTOINCREMENT,
         at     TEXT NOT NULL,            -- 적은 시각(한국 · ISO)
         day    TEXT NOT NULL,            -- 'YYYYMMDD'
         kind   TEXT,                     -- 아침 글 · 공시 · 뉴스 · 뉴스 묶음 · 신호 · 반등 · … (kind_of)
         code   TEXT,                     -- 글 첫 줄의 6자리 종목 코드 · 없으면 NULL
         head   TEXT,                     -- 첫 줄
         text   TEXT,                     -- 글 전부
         status TEXT,                     -- sent · off · quiet · fail
         why    TEXT                      -- 실패 · 조용한 시간 까닭(가린 것)
       )""",
    "CREATE INDEX IF NOT EXISTS ix_tg_day ON tg_log(day, id)",
]

# 첫 줄 머리 → 종류. **위에서부터 처음 맞는 것** — 📊 · 📈 은 둘 이상이 써서 더 긴 머리를 먼저 둔다
_KINDS = [
    (r"^📊 데일리분석", "아침 글"),
    (r"^📊 .*잠정실적", "실적"),
    (r"^📈 넥스트레이드", "장 전 거래량"),
    (r"^📈 미국 지표", "지표"),
    (r"^🌙 밤사이", "밤사이 결과"),
    (r"^📰 뉴스 정리", "뉴스 묶음"),
    (r"^📢 ", "공시"),
    (r"^⬇ 볼린저", "볼린저"),
    (r"^🔔 .* (거래대금|반등|바닥 꼬리|업종) 신호", None),        # 그 낱말이 종류
    (r"^(📉|📈) .*(바닥|고점) 신호", None),                        # 「바닥 신호」 · 「고점 신호」
    (r"^📊 ", "결과"),                                             # FOMC 등 결과 알림
    (r"^\[", "뉴스"),                                              # 「[키워드] 제목」 — 뉴스 즉시
]


def kind_of(text):
    head = (text or "").split("\n", 1)[0]
    for pat, kind in _KINDS:
        m = re.search(pat, head)
        if m:
            if kind:
                return kind
            g = m.groups()
            return (g[-1] + " 신호") if g[-1] in ("바닥", "고점") else g[-1]
    return "알림"


def _conn():
    return marketdb.connect(timeout=10)


def _init(conn):
    for sql in _SCHEMA:
        conn.execute(sql)


def note(text, status, why=None, kind=None):
    """한 줄 적는다. 실패해도 예외를 안 낸다 — 기록 때문에 발송이 멈추면 안 된다."""
    if not marketdb.writable():
        return False
    try:
        now = datetime.now(KST)
        head = (text or "").split("\n", 1)[0][:200]
        m = re.search(r"\((\d{6}|\d{5}[A-Z])\)", head)
        with _lock, _conn() as conn:
            _init(conn)
            conn.execute("INSERT INTO tg_log (at, day, kind, code, head, text, status, why) VALUES (?,?,?,?,?,?,?,?)",
                         (now.isoformat(timespec="seconds"), now.strftime("%Y%m%d"), kind or kind_of(text),
                          m.group(1) if m else None, head, text, status, (why or None) and str(why)[:200]))
            conn.execute("DELETE FROM tg_log WHERE day < ?", ((now - timedelta(days=KEEP_DAYS)).strftime("%Y%m%d"),))
        return True
    except Exception:
        return False


def today(day=None):
    """그날 목록(보낸 순서) · meta. 읽기 전용 서버에 표가 없으면 ready=false."""
    day = day or datetime.now(KST).strftime("%Y%m%d")
    try:
        with _lock, _conn() as conn:
            if marketdb.writable():
                _init(conn)
            elif not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tg_log'").fetchone():
                return [], {"ready": False, "day": day, "count": 0,
                            "note": "기록 표가 아직 없습니다 — 보내는 서버(8765)가 새 코드로 뜨면 생깁니다"}
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute(
                "SELECT id, at, kind, code, head, text, status, why FROM tg_log WHERE day = ? ORDER BY id", (day,))]
    except sqlite3.Error as e:
        return [], {"ready": False, "day": day, "count": 0, "note": "기록을 못 읽었습니다: %s" % type(e).__name__}
    return rows, {"ready": True, "day": day, "count": len(rows),
                  "sent": sum(1 for r in rows if r["status"] == "sent"),
                  "off": sum(1 for r in rows if r["status"] == "off")}
