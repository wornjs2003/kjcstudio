# -*- coding: utf-8 -*-
"""지금검색 — 관심 아래 칩 줄의 「지금검색」 단추를 누르면 칩 룰대로 그 자리에서 다시 센다 (2026-11-11).

재권님 — 「관심종목 하위에 지금검색 버튼 만들고 그거 누르면 관심종목 하위에 룰에 맞게 다시 검색해서 종목 보여지게 해줘」(창구 창 16:1x) →
안 (가) 서버가 든 판을 다시 받기 · (나) 누를 때 서버가 다시 셈 에 「나」(17:2x).

    다시 세는 것   매수(외 · 기 · 프 함께 사는 종목 · kis_proxy._joint_buy_rebuild) — 그날 판을 굳히기 전까지
                  수급(관심 「자동」 묶음 · auto_watch.live_once) — 장중 창(auto_watch.in_live)에서 · 쓰는 서버만(관심 목록에 넣는 자리라서)
                  프리장(pre_flow._rebuild) — 프리장 시간대에서 · 쓰는 서버만
    다시 셀 것 없음 VI · 초반상승 · 장외 · 볼린저 · 현재상승 — 쌓인 기록 · 화면이 가진 시세로 셈. 화면이 다시 받기만 한다
    문턱          MIN_SEC 안에 다시 누르면 KIS 를 안 부르고 앞 결과를 그대로 준다(여러 창 · 여러 번 눌러 예산을 먹지 않게)
    기다림        다시 세기는 셋을 함께 돌리고 WAIT_SEC 까지 기다린다 — 그 안에 안 끝나면 「세는 중」 으로 내고 뒤에서 끝난다

칩마다 결과는 아래 글 넷 중 하나다(「없음」 을 0 으로 안 낸다).
"""

import threading
import time
from datetime import datetime, timedelta, timezone

import auto_watch
import pre_flow

KST = timezone(timedelta(hours=9))

MIN_SEC = 60        # 다시 셀 수 있는 가장 짧은 간격(초) — 수급 한 바퀴가 KIS 멀티 시세 11번쯤
WAIT_SEC = 15       # 다시 세기를 기다리는 가장 긴 시간(초)

DONE, BUSY, SKIP, READER = "다시 셈", "세는 중", "다시 셀 때 아님", "개발 서버 판을 받음"

_lock = threading.Lock()
_running = threading.Lock()     # 한 번에 하나 — 세는 동안 또 누르면 기다리지 않고 「세는 중」
_last = {"at": 0.0, "result": None}


def _now():
    return datetime.now(KST)


def run(proxy, cfg, writer):
    """칩마다 무엇을 했는지 · 언제 · 다음에 다시 셀 수 있는 때. writer — 이 서버가 쓰는 서버(8765)인가."""
    if not _running.acquire(blocking=False):
        return {"at": None, "chips": {}, "cool": 0, "minSec": MIN_SEC, "running": True}
    try:
        with _lock:
            left = MIN_SEC - (time.time() - _last["at"])
            if _last["result"] is not None and left > 0:
                return dict(_last["result"], cool=int(left) + 1)
            _last["at"] = time.time()
        return _run(proxy, cfg, writer)
    finally:
        _running.release()


def _run(proxy, cfg, writer):
    now = _now()
    chips, jobs = {}, []

    # 매수 — 그날 판을 굳혔으면(정규장 끝 · 다 확정) 다시 셀 것이 없다
    with proxy._joint_buy_lock:
        frozen = proxy._joint_buy["frozen"]
    # fetch_joint_buy 와 같은 셈 — 굳힌 판은 다음 평일 프리장 열 때까지
    if frozen and not (now.date().isoformat() > frozen and now.weekday() < 5 and (now.hour, now.minute) >= proxy.NXT_PRE_OPEN):
        chips["buy"] = SKIP + " — 그날 판 굳음"
    else:
        jobs.append(("buy", threading.Thread(target=proxy._joint_buy_rebuild, args=(cfg,), daemon=True, name="rescan-buy")))

    # 수급 — 장중에만 · 쓰는 서버만
    if not writer:
        chips["auto"] = READER
    elif not auto_watch.in_live(now):
        chips["auto"] = SKIP + " — 장중 %02d:%02d~%02d:%02d 밖" % (auto_watch.LIVE_FROM + auto_watch.SESSION[1])
    else:
        jobs.append(("auto", threading.Thread(target=auto_watch.live_once, args=(proxy,), daemon=True, name="rescan-auto")))

    # 프리장 — 프리장 시간대에만 · 쓰는 서버만
    if not writer:
        chips["pre"] = READER
    elif pre_flow.phase(now) != "live":
        chips["pre"] = SKIP + " — 프리장 %02d:%02d~%02d:%02d 밖" % (pre_flow.PRE_OPEN + pre_flow.PRE_CLOSE)
    else:
        jobs.append(("pre", threading.Thread(target=pre_flow._rebuild, args=(proxy, cfg), daemon=True, name="rescan-pre")))

    for _, t in jobs:
        t.start()
    end = time.time() + WAIT_SEC
    for k, t in jobs:
        t.join(max(0.0, end - time.time()))
        chips[k] = BUSY if t.is_alive() else DONE

    result = {"at": _now().strftime("%Y-%m-%d %H:%M:%S"), "chips": chips, "cool": 0, "minSec": MIN_SEC, "running": False,
              "note": "VI · 초반상승 · 장외 · 볼린저 · 현재상승은 쌓인 기록 · 화면 시세로 세어 다시 받기만 함"}
    with _lock:
        _last["result"] = result
    return result
