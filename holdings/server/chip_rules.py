# -*- coding: utf-8 -*-
"""관심 아래 칩 룰 값 — 한 곳 (2026-11-20).

재권님 — 「관심 하위의 버튼별로 룰 정리해주고 그거 수정 가능하도록 해줘」(11-18 · 작업우선순위 창) 의 서버 몫 →
「개발1은 라」(11-20 15:07) → 안 「칩 룰 숫자를 서버 표 한 곳에 모으고 투자 전략 룰 문서 값이 있으면 그것을」 에 「응」(개발1 창).

    표          아래 RULES 한 곳 — 칩마다 열쇠 · 기본값 · 이름 · 단위 · 설명 · 받는 범위
    값          룰 문서 strategy-rules 의 rules.chips.<칩>.<열쇠> 가 있으면 그것 · 없거나 범위 밖이면 기본값(범위 밖은 bad 로 알림)
                — 자동 관심(rules.volsurge) · 단타 셈(rules.dt30)처럼 그 문서 한 곳을 읽는다. 화면이 그 칸을 고치면(편집 열쇠) 다음 읽기부터 든다
    읽기        get(칩, 열쇠) — 문서는 READ_TTL 초 들고 있다(부를 때마다 디스크를 안 읽게)
    주소        GET /api/kis/chip-rules — 칩마다 칸 목록 · 지금 값 · 기본값 · 출처(doc · default) · bad
    받는 쪽     서버 파일은 get() 을, 화면은 주소를 — 같은 숫자를 따로 들지 않는다(「같은 값은 한 곳에만 둔다」).
                옮기는 차례: 개발1 몫(pre_flow · open_rise · dart 시가총액 문턱 · 순위 주소 meta) 먼저 · 개발2 몫(dt30 · day_top · home.js ·
                strategy-dt30.js 의 칩 목록 · 현재상승 · 하락 뺌)은 그쪽이 받기로 바꾼다(11-20 둘이 나눔)

넣지 않은 것 — 첫 봉 길이(open_rise.BAR_MIN · 1분)는 받는 봉 기간(BAR_PERIOD)과 한 몸이라 숫자만 바꾸면 깨진다 · 칸으로 두지 않는다.
"""

import threading
import time

READ_TTL = 10                  # 룰 문서를 다시 읽는 간격(초)

# 칩 → 열쇠 → (기본값, 이름, 단위, 설명, 받는 범위(min, max) 또는 고를 것 목록)
RULES = {
    "순위": {
        "capMinEok": (3000, "시가총액 문턱", "억원",
                      "단타 판 · 홈 순위 칩(현재상승 · 초반상승 · 단타 셈)이 보는 시가총액 아래 끝 — 재권님 「3000으로 통일」(11-20)", (0, 1000000)),
    },
    "프리장": {
        "topN": (70, "고르는 줄 수", "종목",
                 "넥스트레이드 프리마켓에 전일 종가보다 오른 종목 중 거래대금 상위 몇 종목 — 재권님 「상승인 종목 70개」(11-12)", (1, 300)),
        "riseMinPct": (0.0, "상승 문턱", "%",
                       "전일 정규장 종가 대비 이 % 를 넘어야 든다 — 0 이면 보합은 안 든다(11-12 「가」)", (-30.0, 30.0)),
    },
    "초반상승": {
        "risePct": (1.5, "첫 1분봉 상승 문턱", "%",
                    "정규장 첫 1분봉(09:00~09:01)이 시가보다 이 % 이상 올라 끝난 종목 — 재권님 문턱 「나」 1.5%(11-18)", (0.1, 30.0)),
        "preRisePct": (2.0, "프리장 대비 상승 문턱", "%",
                       "또는 — 첫 1분봉 끝 값이 넥스트레이드 프리장 마지막 값보다 이 % 이상 높은 종목 · 프리장 체결이 없던 종목은 이 셈을 안 한다 — 재권님 「프리장보다 2%이상 오를때」(11-23)", (0.1, 30.0)),
        "rise2Pct": (2.0, "2분 상승 문턱", "%",
                     "또는 — 시가부터 2분(09:01 1분봉 끝 값)이 그날 시가(첫 1분봉 시가)보다 이 % 이상 높은 종목 — 재권님 「1분봉은 1.5% 이고 분별로 룰이 추가되야」 → 시황분석1 잰 값 → 「가 해줘 3분까지만 하자」(11-23)", (0.1, 30.0)),
        "rise3Pct": (3.0, "3분 상승 문턱", "%",
                     "또는 — 시가부터 3분(09:02 1분봉 끝 값)이 그날 시가보다 이 % 이상 높은 종목 · 3분까지만 센다 — 재권님 「가 해줘 3분까지만 하자」(11-23)", (0.1, 30.0)),
    },
    "프리장대비": {
        "preUpPct": (3.0, "프리장 대비 상승 문턱", "%",
                     "지금 값이 넥스트레이드 프리장 마지막 값(08:50 끝)보다 이 % 이상 높은 종목 · 장중 내내 다시 셈 · 프리장 체결이 없던 종목은 안 든다 · 초반상승과 따로(둘 다 걸릴 수 있음) · 단타 셈에는 안 듦 — 재권님 「프리장보다 3%이상 오른종목 칩 · 프리장 50분기준」 → 안에 「응」(11-23)", (0.1, 30.0)),
    },
    "거래비율": {
        "turnPct": (2.0, "거래 비율 문턱", "%",
                    "유통주식 대비 지금 거래 비율(누적 거래대금 ÷ 풀린 시가총액 × 100 · 단타 판 「거래 비율」 칸과 같은 셈)이 이 % 이상이면 든다 · 시가총액 순위.capMinEok 이상 · ETF 뺌 — "
                    "재권님 「유통거래대금 대비 현재거래대금 ()%이상」 · 「둘중 하나로 하지말고 각각 칩으로 해줘」 · 「두개야 / 전일대비 현시점거래비율 이랑 유통주식대비 현시점 거래비율」(11-23 16:3x)", (0.01, 1000.0)),
    },
    "거래비율급증": {
        "turnPrevPct": (250.0, "거래 비율 전날 대비 문턱", "%",
                        "지금 거래 비율 ÷ 전날 같은 시각까지 거래 비율 × 100(단타 판 「거래 비율 전날 대비」 칸과 같은 셈 · turnover)이 이 % 이상이면 든다 · 전날 1분 칸이 없으면 정규장 5분봉 끝난 봉까지 거래량 비로 어림(출처 5m) — "
                        "재권님 「전일대비 현시점거래비율」(11-23 16:3x) · 문턱 250 은 옛 거래량 대비 값을 옮김", (1.0, 100000.0)),
    },
    "미국강세": {
        "topN": (5, "미국 상위 묶음 수", "묶음",
                 "어제 미국장에서 가장 많이 오른 업종 · 테마 묶음 몇 개(오른 것만 · us-kr-groups 의 국내 짝 이름) — 그 국내 업종 · 테마 종목에 칩 — 재권님 「미국장 상승 섹터나 테마에 속한 종목은 단타에 칩하나」(11-25 13:5x)", (1, 30)),
    },
    "돈몰림": {
        "winMin": (15, "최근 몇 분", "분",
                   "업종 · 테마 묶음의 최근 이만큼(5분 칸 winMin/5 개 · 5 단위로 내림) 거래대금을 전날 같은 칸들과 견줌 — 재권님 「시간과 배수는 ()로 빼서 내가 조절하게」(11-25 14:1x)", (5, 60)),
        "mult": (1.3, "전날 같은 때 대비 배수", "배",
                 "그 묶음 최근 거래대금 ≥ 전날 같은 칸들 합 × 이 배수 — 재권님 「그 섹터의 전일대비 현재시각대금 비율로」(11-25 14:0x)", (1.0, 10.0)),
        "minEok": (100, "최근 대금 아래 끝", "억원",
                   "그 묶음 최근 거래대금이 이 억 이상이어야 든다(작은 묶음 헛걸림 막기)", (0, 100000)),
        "holdMin": (30, "다수결 창", "분",
                    "최근 이만큼(5분 칸 holdMin/5 개 · 5 단위로 내림) 중 위 셋이 맞은 칸이 안 맞은 칸보다 많으면 칩이 붙어 있음 — 5분마다 붙었다 떨어지는 깜빡임을 줄임(11-25 지난 기록 셈 · 종목당 7.7번 → 1.9번 · 한 시각 최대 176 → 84) — 재권님 「든 횟수가 높으면 들어있고 나간 횟수가 높으면 빼는 방향」 → 「응 해」(11-25 15:0x)", (5, 120)),
        "buyShare": (55, "매수 몫", "%",
                     "정규장 칸: 그 사이 매수 ÷ (매수 + 매도) × 100 이 이 % 이상 · 매수 값이 없는 칸(프리장)이 끼면 그 사이 묶음 등락이 오른 것으로 대신", (0, 100)),
    },
    "현재상승": {
        "nowRisePct": (3.0, "시가 대비 상승 문턱", "%",
                       "지금 값이 오늘 시가보다 이 % 이상 높은 종목", (0.1, 30.0)),
    },
    "단타": {
        "ovChips": (["관심", "프리장", "VI·급등", "장외", "매수", "초반상승", "수급", "거래비율", "거래비율급증", "돈몰림", "미국강세"], "단타가 세는 칩", "목록",
                    "단타 셈(겹친 칩 수)에 드는 칩과 그 차례 — 화면 칩 줄 차례와 같다", None),
        "dayChips": (["프리장", "미국강세", "장외"], "하루 고정 칩", "목록",
                     "장 전에 정해져 그날 내내 붙은 것으로 보는 칩 — 굳히는 때 앞 마지막 값(프리장은 프리장 끝 08:50 · 그 밖은 여는 시각)을 그날 끝까지 그대로 · 그 뒤 새로 붙거나 빠진 것은 안 셈 · "
                     "나머지 칩은 장중 붙음 · 빠짐 시각 그대로(매수는 같은 시각 함께 붙은 칩) — 재권님 「응」(11-26 13:4x · 미국강세가 낮에 미국 일봉이 더 들어와 상위 묶음이 바뀌던 것 · 프리장이 08:50 에 빠지던 것)", None),
        "dropBelowPct": (0.0, "하락 뺌 문턱", "%",
                         "전일 종가 대비 이 % 아래인 종목은 단타 판에 안 넣는다 — 0 이면 보합은 남긴다(11-12)", (-30.0, 30.0)),
    },
}

_cache = {"at": 0.0, "doc": None}
_lock = threading.Lock()


def _doc():
    now = time.time()
    with _lock:
        if _cache["doc"] is not None and now - _cache["at"] < READ_TTL:
            return _cache["doc"]
    try:
        d = (rules_doc().get("rules") or {}).get("chips") or {}
    except Exception:
        d = {}
    with _lock:
        _cache.update(at=now, doc=d)
    return d


def _ok(v, default, rng):
    """문서 값이 받을 만한가 — 기본값과 같은 꼴(수 · 목록)이고 범위 안이면."""
    if isinstance(default, list):
        return isinstance(v, list) and all(isinstance(x, str) and x for x in v)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    lo, hi = rng or (None, None)
    return (lo is None or v >= lo) and (hi is None or v <= hi)


def get(chip, key):
    """그 칩 칸의 지금 값 — 문서 값이 받을 만하면 그것 · 아니면 기본값. 표에 없는 칩 · 열쇠는 KeyError(짐작한 값을 안 낸다)."""
    default, _n, _u, _d, rng = RULES[chip][key]
    v = (_doc().get(chip) or {}).get(key)
    if v is not None and _ok(v, default, rng):
        return type(default)(v) if isinstance(default, (int, float)) and not isinstance(default, bool) else list(v)
    return list(default) if isinstance(default, list) else default


def table():
    """주소용 — [{chip, key, name, unit, note, value, default, source, bad, range}]."""
    doc = _doc()
    out = []
    for chip, keys in RULES.items():
        for key, (default, name, unit, note, rng) in keys.items():
            raw = (doc.get(chip) or {}).get(key)
            bad = raw is not None and not _ok(raw, default, rng)
            out.append({"chip": chip, "key": key, "name": name, "unit": unit, "note": note,
                        "value": get(chip, key), "default": default,
                        "source": "doc" if raw is not None and not bad else "default",
                        "bad": raw if bad else None, "range": list(rng) if rng else None,
                        "docPath": "rules.chips.%s.%s" % (chip, key)})
    return out


# ── 룰 문서 읽기 한 곳 (2026-11-23) ────────────────────────────────────────────────
# 보드를 넘기는 서버(KJC_BOARD_UPSTREAM — 메인 8764 · 중간 · 세션)는 자기 폴더에 룰 문서가 없다 — 그 파일을 읽으면 {} 라
# 칩 문턱 · 점수 · 셈 칸이 기본값으로 셈됐다(개념정의 검수 11-23 19:2x — 개발 3 · staging · service 빈 값). 그래서 상류(8765)의 문서를 받는다
# (「두 구역이 같은 값을 쓰면 — 받는 곳은 서버 하나」 · dt-list 를 상류에서 받는 것과 같은 길). 8765 는 자기 파일.
RULES_DOC = "strategy-rules"
RULES_DOC_TTL = 30            # 상류에서 받은 룰 문서를 들고 있는 초 — 셈마다 묻지 않게
_rd = {"at": 0.0, "doc": None}


def rules_doc():
    """룰 문서 strategy-rules 의 내용({"rules": …}) — 상류가 있으면 상류 · 없으면 자기 파일 · 못 읽으면 {}(그때 셈은 기본값 · 로그 한 줄)."""
    import json, os, time, urllib.request
    up = (os.environ.get("KJC_BOARD_UPSTREAM") or "").strip().rstrip("/")
    if not up:
        try:
            import docstore
            return docstore.read_doc(RULES_DOC) or {}
        except Exception:
            return {}
    now = time.time()
    if _rd["doc"] is not None and now - _rd["at"] < RULES_DOC_TTL:
        return _rd["doc"]
    try:
        req = urllib.request.Request(up + "/api/board/doc/" + RULES_DOC, headers={"X-KJC-Prio": "low"})
        with urllib.request.urlopen(req, timeout=3) as r:
            d = json.loads(r.read().decode("utf-8")).get("data") or {}
    except Exception as e:
        print("  [룰 문서] 상류에서 못 받음 — %s · 지난 값%s" % (type(e).__name__, "" if _rd["doc"] is not None else " 없음(기본값으로 셈)"), flush=True)
        return _rd["doc"] if _rd["doc"] is not None else {}
    _rd.update(at=now, doc=d if isinstance(d, dict) else {})
    return _rd["doc"]
