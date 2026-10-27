# -*- coding: utf-8 -*-
"""시황 글 알림 — 자동 시황 글이 새로 써지면 텔레그램 한 통 (2026-10-27).

재권님(시황분석 창) — 모양 「텔레그램으로 올렸다 라고하고 링크만 주면 돼」 · 보내는 길 「가」(8765 서버가 보낸다) →
작업우선순위 배분 → 개발1 창 안 「응」.

    무엇을 보나   company-setup/data/market-note-live.json 의 `at`(작성 시각) — 시황분석 도구 write-market-note.py 가
                 launchd market-data(평일 06:30 · 16:10) 끝에 쓴다
    언제 보내나   `at` 이 지난번 본 것과 다르면 한 통 — 「시황 글 올렸습니다」 + 링크
    안 보내는 것  · 못 만든 날 — 그 도구는 옛 글에 `failedAt` 만 적고 `at` 을 안 바꾼다(그래서 저절로 빠진다)
                 · 서버가 **처음** 떴을 때 이미 있던 글 — 본 것으로만 적는다
                 · 같은 `at` 두 번 — 보낸 `at` 을 market.db sync_meta 에 남겨 재시작해도 안 간다
    조용한 시간   22:00~07:00(dart.QUIET_FROM · QUIET_TO) 에 써진 글(06:3x)은 **버리지 않고** 조용한 시간이 끝나면 보낸다 — 07:00 한 통
    발송         dart.telegram_send — 텔레그램 기록(tglog)도 거기서 남는다

8765 만 돈다(`kis_proxy` 가 `is_sender` 로 부른다 · 「알림은 메인서버에서만 나간다」). 화면 · API 는 없다.
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import dart
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
NOTE = os.path.join(HERE, "..", "..", "company-setup", "data", "market-note-live.json")
LINK = "https://thekjcstudio.com/company-setup/market.html"
TEXT = "시황 글 올렸습니다\n" + LINK
STATE_KEY = "note_alert_state"      # market.db sync_meta — {"seen": 마지막으로 본(보낸) at, "sentAt": 보낸 시각}
TICK = 60

_status = {"startedAt": None, "lastTick": None, "seen": None, "pending": None, "lastSent": None, "lastError": None}


def _read_at():
    """지금 파일의 `at` — 파일이 없거나 못 읽으면 None(아직 등록 전 · 쓰는 중)."""
    try:
        with open(NOTE, encoding="utf-8") as f:
            return (json.load(f) or {}).get("at") or None
    except (OSError, ValueError):
        return None


def _load():
    try:
        return json.loads(dart._meta_get(STATE_KEY) or "{}")
    except ValueError:
        return {}


def _save(state):
    dart._meta_set(STATE_KEY, json.dumps(state, ensure_ascii=False))


def tick(now=None):
    now = now or datetime.now(KST)
    _status["lastTick"] = now.isoformat(timespec="seconds")
    at = _read_at()
    if not at:
        return
    state = _load()
    if not state.get("seen"):                      # 처음 — 있던 글은 본 것으로만 적는다
        _save({"seen": at, "sentAt": None})
        _status.update(seen=at, pending=None)
        return
    if at == state["seen"]:
        _status.update(seen=at, pending=None)
        return
    if dart.in_quiet():                            # 06:3x 글 — 조용한 시간이 끝나면 보낸다(seen 을 안 바꿔 두면 된다)
        _status["pending"] = at
        return
    ok, why = dart.telegram_send(TEXT)
    # 실패해도 본 것으로 적는다 — 바퀴마다 다시 보내 실패 기록이 쌓이지 않게. 기록은 tglog 에 남는다
    _save({"seen": at, "sentAt": now.isoformat(timespec="seconds") if ok else None})
    _status.update(seen=at, pending=None, lastSent=now.isoformat(timespec="seconds") if ok else None,
                   lastError=None if ok else safe_message(Exception(why), 100))
    print("  [시황 글] %s — 글 %s" % ("알림 보냄" if ok else "알림 못 보냄(%s)" % safe_message(Exception(why), 80), at), flush=True)


def start():
    """메인(보내는 서버)에서 `kis_proxy` 가 부른다."""
    _status["startedAt"] = datetime.now(KST).isoformat(timespec="seconds")

    def loop():
        time.sleep(30)
        last = None
        while True:
            try:
                tick()
                last = None
            except Exception as e:
                key = "%s: %s" % (type(e).__name__, safe_message(e, 100))
                _status["lastError"] = key
                if key != last:
                    last = key
                    print("  [시황 글] 바퀴 오류 — %s (같은 오류는 다시 안 적습니다)" % key, flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="note-alert").start()
    return True


def status():
    return dict(_status, tickSec=TICK, note=os.path.normpath(NOTE))
