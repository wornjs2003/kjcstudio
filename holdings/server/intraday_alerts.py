# -*- coding: utf-8 -*-
"""장중 알림 둘 — 상승 VI 발동 · +20% 급등 — 날 때마다 텔레그램으로 (2026-10-26 · 작업우선순위 경유).

    상승 VI   재권님 「VI 발동된 종목들 바로 알림 가능한지 확인해줘」(10-25) → 「상승 vi」(10-26 · 전 종목 · 상승만)
    +20% 급등 재권님 「20% 이상 급등종목이 나오면 바로 메세지 보내도록 만들어줘」(10-26 12:1x)

조사는 `holdings/docs/data-sources.md` 「2-0. VI 발동 — 받을 길」.

── 어떻게 ──

    한 바퀴(`TICK` 초)에 둘을 본다. 그 바퀴에 새로 생긴 것을 알림마다 한 통으로 묶어 보낸다.

    상승 VI   KIS REST 「VI 현황」(FHPST01390000) 상승만(`FID_DIV_CLS_CODE` 1) · 전 시장. 한 번에 최근 30건.
              (종목코드 · 발동 시각)이 처음 보이면 새 발동. VI 가 풀려도(`vi_cls_code` Y → N) 같은 열쇠라 다시 안 간다
    +20% 급등 서버의 상승률 순위(`fetch_movers` · 전 종목 30위 · 전일 종가 대비)를 읽는다 — **화면과 같은 캐시를 탄다**
              (`MOVERS_TTL` · 그래서 넘은 뒤 그만큼 늦을 수 있다). 등락률이 `SURGE_PCT` 이상인 종목을 **그날 처음 볼 때 한 번**.
              거래대금은 그 종목 현재가 조회(`fetch_price` 의 value)로 — 새로 넘은 종목만 부른다

    **기록을 파일에 두지 않는다** — 재권님 「가 로해줘」(10-26 11:4x). 본 것은 메모리에만 두고, 서버가 뜬 직후 처음 본 목록은
    **보낸 것으로 치고 안 보낸다.** 재시작 사이(1~2분)에 난 것은 놓칠 수 있다 — 재시작 뒤 한꺼번에 다시 가는 것보다 낫다.
    날짜가 바뀌면 기억을 비운다.

── 언제 ──

    평일 `SESSION_FROM` ~ `SESSION_TO` — 둘 다 정규장만(재권님 VI 「정규장만」 · 급등 「응 정규장에서만」 10-26).
    장 뒤 넥스트레이드(~20:00)는 안 본다. 바꾸려면 `SESSION_TO` 만.
    공휴일은 아직 안 가른다 — 그날은 목록이 비어 KIS 만 헛돈다.

── 보내기 ──

    `dart.telegram_send` 하나(조용한 시간 · 4,096자 나누기 그대로). 보내는 서버는 메인(`is_sender`) 하나 — `kis_proxy` 가 거기서만 띄운다.
    **`SEND` — VI 는 끄고 급등만 켰다** — 「둘다 켜」(10-26) 뒤 첫날 오전에 VI 가 103통이 되자 재권님 「VI 이건 안해도 될거같아」(10-27). 따로 끌 수 있다.
    꺼 두면 바퀴는 돌되 안 보내고, 보냈을 글을 `/api/alerts/status` 의 `preview` 에 남긴다. 몇 통 갔는지는 거기 `today`.

── 못 하는 것 ──

    VI   한 바퀴 사이에 30건 넘게 몰리면 넘친 것은 못 본다 — 연속 조회(`tr_cont`)를 안 한다. 30건이 다 새것이던 바퀴를 `overflow` 로 센다
    급등 +20% 넘는 종목이 30개를 넘으면 30위 밖은 못 본다 — 30위가 `SURGE_PCT` 이상이던 바퀴를 `overflow` 로 센다
"""

import threading
import time
from datetime import datetime, timedelta, timezone

import dart
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))

SEND = {"vi": False, "surge": True}    # VI 끔 — 재권님 「VI 이건 안해도 될거같아」(10-27 · 첫날 10:36 까지 103통). 급등은 켬 — 「둘다 켜」(10-26)
TICK = 10                    # 초. 하루 정규장 2,340바퀴쯤 · VI 는 KIS 초당 0.1 · 급등은 순위 캐시를 탄다
SESSION_FROM = 9 * 60        # 09:00
SESSION_TO = 15 * 60 + 30    # 15:30 — 정규장만(재권님 「정규장만」 10-26)
SURGE_PCT = 20.0             # 전일 종가 대비 이 % 이상을 처음 볼 때 (재권님 「20% 이상」)
PREVIEW_MAX = 40             # 꺼져 있을 때 남겨 둘 글 수

VI_PATH = "/uapi/domestic-stock/v1/quotations/inquire-vi-status"
VI_TR = "FHPST01390000"
VI_KIND = {"1": "정적", "2": "동적", "3": "정적·동적"}


def _blank_day():
    return {k: {"items": 0, "messages": 0, "overflow": 0} for k in SEND}


_status = {"startedAt": None, "lastTick": None, "lastError": None, "day": None,
           "today": _blank_day(), "preview": {k: [] for k in SEND}}
_seen = {k: set() for k in SEND}   # vi: (코드, 발동 시각) · surge: 코드 — 그날 것만
_baseline_done = False             # 뜬 뒤 첫 목록을 「보낸 것」 으로 쳤나 (「가」)


def _in_session(now):
    if now.weekday() >= 5:
        return False
    m = now.hour * 60 + now.minute
    return SESSION_FROM <= m <= SESSION_TO


def _won(v):
    try:
        return "{:,}".format(int(float(v)))
    except (TypeError, ValueError):
        return "—"


def _eok(v):
    """원 → 「1,234억」 · 1억 밑은 「—」 가 아니라 「1억 미만」."""
    try:
        v = int(v)
    except (TypeError, ValueError):
        return "—"
    return "{:,}억".format(v // 100_000_000) if v >= 100_000_000 else "1억 미만"


# ── 상승 VI ─────────────────────────────────────────────────────────

def _vi_rows(proxy, day):
    data = proxy.kis_get(
        proxy.load_secrets(), VI_PATH,
        {"FID_DIV_CLS_CODE": "1", "FID_COND_SCR_DIV_CODE": "20139", "FID_MRKT_CLS_CODE": "0",
         "FID_INPUT_ISCD": "", "FID_RANK_SORT_CLS_CODE": "0", "FID_INPUT_DATE_1": day,
         "FID_TRGT_CLS_CODE": "", "FID_TRGT_EXLS_CLS_CODE": ""},
        VI_TR,
    )
    return data.get("output") or []


def _hms(s):
    s = (s or "").zfill(6)
    return "%s:%s:%s" % (s[0:2], s[2:4], s[4:6])


def _vi_line(r):
    """「▲ 상승 VI 동적 · 종목명 · 09:12:05 · 발동가 1,234(기준가 대비 +11.3%) · 오늘 3번째」"""
    kind = VI_KIND.get((r.get("vi_kind_code") or "").strip(), "")
    # 괴리율 — 정적은 vi_dprt · 동적은 vi_dmc_dprt. 둘 다면 큰 쪽
    gaps = []
    for k in ("vi_dprt", "vi_dmc_dprt"):
        try:
            v = float(r.get(k) or 0)
        except ValueError:
            continue
        if v:
            gaps.append(v)
    gap = "(기준가 대비 +%.1f%%)" % max(gaps) if gaps else ""
    cnt = (r.get("vi_count") or "").strip()
    tail = " · 오늘 %s번째" % cnt if cnt and cnt != "0" else ""
    return "▲ 상승 VI %s · %s · %s · 발동가 %s%s%s" % (
        kind, (r.get("hts_kor_isnm") or "").strip(), _hms(r.get("cntg_vi_hour")), _won(r.get("vi_prc")), gap, tail)


def _vi_in_session(hhmmss):
    """발동 시각이 정규장 안인가 — KIS VI 현황은 넥스트레이드 시간(08:00~ · ~20:00) VI 도 준다(data-sources 2-0 · 10-23 실측)."""
    s = (hhmmss or "").strip().zfill(6)
    try:
        m = int(s[0:2]) * 60 + int(s[2:4])
    except ValueError:
        return False
    return SESSION_FROM <= m <= SESSION_TO


def _vi_new(proxy, day):
    rows = _vi_rows(proxy, day)
    new = []
    for r in rows:
        key = ((r.get("mksc_shrn_iscd") or "").strip(), (r.get("cntg_vi_hour") or "").strip())
        if key not in _seen["vi"]:
            _seen["vi"].add(key)
            # 장 전 · 장 뒤 VI 는 본 것으로만 치고 안 보낸다 — 안 그러면 09:00 첫 바퀴에 08시대 VI 가 한 통에 몰려 간다
            # (재권님 「정규장만」 · 2026-10-26 qa 검수)
            if _vi_in_session(key[1]):
                new.append(r)
    full = len(rows) >= 30 and len(new) == len(rows)       # 넘침도 정규장 VI 로만 센다
    new.sort(key=lambda r: r.get("cntg_vi_hour") or "")
    return [_vi_line(r) for r in new], full


# ── +20% 급등 ───────────────────────────────────────────────────────

def _surge_new(proxy, now, baseline):
    # 09:00 직후 순위 캐시(`MOVERS_TTL`)는 장 전(넥스트레이드 포함 · 통합) 순위일 수 있다 — 캐시 열쇠에 시장 구분이 없다.
    # 그 동안은 건너뛴다. 안 그러면 장 전에만 +20% 였던 종목이 「정규장 급등」 으로 간다(2026-10-26 개념정의 검수 덧말)
    since_open = (now.hour * 60 + now.minute - SESSION_FROM) * 60 + now.second
    if not baseline and 0 <= since_open < getattr(proxy, "MOVERS_TTL", 30) + TICK:
        return [], False
    cfg = proxy.load_secrets()
    rows = proxy.fetch_movers(cfg, "up", "all") or []
    lines = []
    for r in rows:
        pct = r.get("pct")
        code = r.get("code")
        if pct is None or pct < SURGE_PCT or not code or code in _seen["surge"]:
            continue
        _seen["surge"].add(code)
        if baseline:
            continue
        value = None
        try:
            value = (proxy.fetch_price(cfg, code) or {}).get("value")
        except Exception:
            pass                     # 거래대금만 「—」 — 알림은 낸다
        lines.append("🚀 +%d%% 급등 · %s · %s · %+.2f%% · %s원 · 거래대금 %s" % (
            SURGE_PCT, r.get("name") or code, now.strftime("%H:%M:%S"), pct, _won(r.get("price")), _eok(value)))
    last = rows[-1].get("pct") if len(rows) >= 30 else None
    full = last is not None and last >= SURGE_PCT
    return lines, full


# ── 바퀴 ────────────────────────────────────────────────────────────

def _emit(kind, lines, full, now):
    if full:
        _status["today"][kind]["overflow"] += 1
    if not lines:
        return
    text = "\n".join(lines)
    _status["today"][kind]["items"] += len(lines)
    _status["today"][kind]["messages"] += 1
    if SEND[kind]:
        ok, why = dart.telegram_send(text)
        if not ok:
            _status["lastError"] = "%s 보내기 실패: %s" % (kind, why)
    else:
        p = _status["preview"][kind] + ["%s  %s" % (now.strftime("%H:%M:%S"), text)]
        _status["preview"][kind] = p[-PREVIEW_MAX:]


def tick(proxy, now=None):
    global _baseline_done
    now = now or datetime.now(KST)
    day = now.strftime("%Y%m%d")
    if _status["day"] != day:
        _status["day"] = day
        _status["today"] = _blank_day()
        _status["preview"] = {k: [] for k in SEND}
        for s in _seen.values():
            s.clear()
    baseline = not _baseline_done
    if not baseline and not _in_session(now):
        return
    _status["lastTick"] = now.isoformat(timespec="seconds")
    errors = []
    for kind, fn in (("vi", lambda: _vi_new(proxy, day)), ("surge", lambda: _surge_new(proxy, now, baseline))):
        try:
            lines, full = fn()
        except Exception as e:
            errors.append("%s %s: %s" % (kind, type(e).__name__, safe_message(e, 80)))
            continue
        if not baseline:
            _emit(kind, lines, full and not baseline, now)
    _baseline_done = True            # 「가」 — 뜬 뒤 첫 목록은 보낸 것으로 친다
    if errors:
        raise RuntimeError(" · ".join(errors))


def start(proxy):
    """메인(보내는 서버)에서 `kis_proxy` 가 부른다."""
    _status["startedAt"] = datetime.now(KST).isoformat(timespec="seconds")

    def loop():
        time.sleep(15)              # 서버가 막 뜬 참이라 첫 화면에 양보한다
        last = None
        while True:
            t0 = time.time()
            try:
                tick(proxy)
                last = None
            except Exception as e:
                key = safe_message(e, 160)
                _status["lastError"] = key
                if key != last:
                    last = key
                    print("  [장중 알림] 바퀴 오류 — %s (같은 오류는 다시 안 적습니다)" % key, flush=True)
            time.sleep(max(1, TICK - (time.time() - t0)))

    threading.Thread(target=loop, daemon=True, name="intraday-alerts").start()
    return True


def status():
    s = dict(_status)
    s.update(send=dict(SEND), tickSec=TICK, surgePct=SURGE_PCT, session="%02d:%02d~%02d:%02d" % (
        SESSION_FROM // 60, SESSION_FROM % 60, SESSION_TO // 60, SESSION_TO % 60),
        baselineDone=_baseline_done, seen={k: len(v) for k, v in _seen.items()})
    return s
