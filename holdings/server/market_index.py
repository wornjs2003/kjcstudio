# -*- coding: utf-8 -*-
"""시장지표 — 홀딩스 홈 「시장지표」 갈래의 칩 열하나와 큰 차트 1년치 (2026-10-12 · 재권님 「응 해줘」 · 창구 경유).

값은 **네이버 증권 시장지표** 하나에서 받는다(재권님 「네이버 값을 기준으로」). 공개 API 가 아니고 그 화면에
「무단 배포 금지」 가 붙어 있다 — 우리 화면에 그리는 데만 쓴다. 브라우저는 교차 출처라 직접 못 불러 서버가 받는다.

    GET /api/market/indicators          칩 열하나 — 마지막 값 · 앞 값 · 날짜 · 봉인가 선인가
    GET /api/market/indicator?key=us10  그 지표 1년 일별 — 봉이면 시가·고가·저가·종가, 선이면 종가
    GET /api/market/materials           오른쪽 칸 「시장지표 재료」 — 환율 · 금리 · 에너지 · 금속 · 농산 · 운임의 지금 값
                                        (2026-10-12 · 재권님 「응 그래」 · 시안 3)

── 어디서 받나 (2026-10-12 실측 · 주식페이지_개발) ──

    https://stock.naver.com/api/securityService/marketindex/<갈래>/<코드>/prices?page=N&pageSize=60
    한 쪽에 60일 · 다섯 쪽이면 1년 · 코드의 `=` 는 `%3D` 로

재료(지금 값)는 갈래 목록 한 번에 받는다 — `…/marketindex/<갈래>` · 환율은 `…/marketindex/exchange/majors`.
시황분석 도구(company-setup/tools/fetch-naver-macro.py)가 같은 주소를 손으로 받아 파일로 두던 것을 여기로 옮겼다 —
그 도구는 「홀딩스에 들어오면 없앤다」 고 적혀 있다(없애는 것은 시황분석 레인).

── 봉인가 선인가 (재권님 「캔들이 없으면 그래프로만 그려도 돼」) ──

    봉   달러인덱스 · 국채 넷        시가·고가·저가·종가가 다 온다
    선   원/달러 · 원/100엔          시가·고가·저가 칸이 **아예 없다** — 은행 고시 기준율 종가뿐(영영)
         회사채 AA-                  시가·고가·저가가 0 으로 온다 — 하루 한 번 정하는 평가 금리(영영)
         신용 가산금리               AA- 종가 − 국고채 3년 종가. **같은 출처(네이버)끼리 뺀다** — ECOS 국고채와 섞으면
                                     10-08 에 3.994 · 3.983 으로 갈렸다
         BDI · 상하이 컨테이너         네 값이 날마다 같다 — 하루(주) 한 번 발표하는 지수(영영)

**깨진 봉은 여기서 고친다** — 2026-10-12 실측 1년치에서 고가·저가가 0 으로 온 날이 미국 2년 8일 · 10년 1일,
종가가 고가·저가 밖인 날이 달러인덱스 5일 · 미국 2년 1일이었다. 0 이면 시가·종가로 메우고 밖이면 넓힌다.
몇 개를 고쳤는지는 응답 `fixed` 에 낸다.

── 캐시 · 어느 서버가 받나 ──

1년치는 하루 한 번(`HIST_TTL`) · 최근 열흘은 몇 분마다(`RECENT_TTL`) 받아 날짜로 합친다 — 칩 값이 하루 내내 묵지 않게.
화면은 주기로 묻지 않고 갈래를 열 때 받는다. 응답의 `cacheTtlSec` 이 지금 값이다.
**받는 것은 상류(8765)다** — 상류가 있는 서버는 넘긴다(kis_proxy 의 `_handle_market`). KIS 예산은 안 쓴다.

**못 받은 값은 0 이 아니라 `last: null` · `error` 다** — 그 지표만 비고 나머지는 나온다.
"""
import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from secrets_guard import safe_message

HIST_TTL = 24 * 3600
RECENT_TTL = 5 * 60
RETRY_TTL = 10 * 60           # 하나라도 못 받았을 때 1년치를 다시 받는 간격
PAGES = 5
PAGE_SIZE = 60
RECENT_SIZE = 10
TIMEOUT = 15
KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
URL = "https://stock.naver.com/api/securityService/marketindex/%s/%s/prices?page=%d&pageSize=%d"

# 칩 순서 그대로. digits = 화면 소수 자리 · unit = 값 뒤에 붙는 글자 · kind = candle(봉) | line(선)
ITEMS = [
    {"key": "usdkrw", "name": "원/달러", "group": "환율", "cat": "exchange", "code": "FX_USDKRW", "unit": "원", "digits": 2, "kind": "line"},
    {"key": "jpykrw", "name": "원/100엔", "group": "환율", "cat": "exchange", "code": "FX_JPYKRW", "unit": "원", "digits": 2, "kind": "line"},
    {"key": "dxy", "name": "달러인덱스", "group": "환율", "cat": "exchange", "code": ".DXY", "unit": "", "digits": 2, "kind": "candle"},
    {"key": "us10", "name": "미국 10년", "group": "국채", "cat": "bond", "code": "US10YT=RR", "unit": "%", "digits": 3, "kind": "candle"},
    {"key": "us2", "name": "미국 2년", "group": "국채", "cat": "bond", "code": "US2YT=RR", "unit": "%", "digits": 3, "kind": "candle"},
    {"key": "kr10", "name": "한국 10년", "group": "국채", "cat": "bond", "code": "KR10YT=RR", "unit": "%", "digits": 3, "kind": "candle"},
    {"key": "kr3", "name": "한국 3년", "group": "국채", "cat": "bond", "code": "KR3YT=RR", "unit": "%", "digits": 3, "kind": "candle"},
    {"key": "aa", "name": "회사채 AA-", "group": "회사채", "cat": "domesticInterest", "code": "KFIA103009", "unit": "%", "digits": 3, "kind": "line"},
    {"key": "spread", "name": "신용 가산금리", "group": "회사채", "from": ("aa", "kr3"), "unit": "%p", "digits": 3, "kind": "line"},
    {"key": "bdi", "name": "건화물 운임 BDI", "group": "운임", "cat": "transport", "code": ".BADI", "unit": "", "digits": 0, "kind": "line"},
    {"key": "scfi", "name": "상하이 컨테이너", "group": "운임", "cat": "transport", "code": ".SCFIDXSSE", "unit": "", "digits": 2, "kind": "line", "freq": "주간"},
    # 원자재 — 홈 갈래 「원자재」 를 이 갈래로 합쳤다(2026-10-14 재권님 「응 넣어줘」 · 「응」). 같은 네이버 길이 일봉 시가·고가·저가·종가를 준다.
    # 여섯을 고른 까닭 — 에너지(원유 둘 · 가스) · 귀금속(금 · 은) · 산업 금속(구리)을 한 칩씩은 보이게. 실시간 순위 「원자재」 표도 이 목록을 쓴다.
    # 날짜는 그 거래소 날짜(미국 시카고 · 뉴욕 장 마감) — 값은 전일 정산가다
    {"key": "wti", "name": "WTI 원유", "group": "원자재", "cat": "energy", "code": "CLcv1", "unit": "", "digits": 2, "kind": "candle"},
    {"key": "brent", "name": "브렌트유", "group": "원자재", "cat": "energy", "code": "LCOcv1", "unit": "", "digits": 2, "kind": "candle"},
    {"key": "natgas", "name": "천연가스", "group": "원자재", "cat": "energy", "code": "NGcv1", "unit": "", "digits": 3, "kind": "candle"},
    {"key": "gold", "name": "국제 금", "group": "원자재", "cat": "metals", "code": "GCcv1", "unit": "", "digits": 1, "kind": "candle"},
    {"key": "silver", "name": "은", "group": "원자재", "cat": "metals", "code": "SIcv1", "unit": "", "digits": 2, "kind": "candle"},
    {"key": "copper", "name": "구리", "group": "원자재", "cat": "metals", "code": "HGcv1", "unit": "", "digits": 3, "kind": "candle"},
]
BY_KEY = {i["key"]: i for i in ITEMS}

# 오른쪽 칸 칩 순서 그대로. parts = (네이버 갈래 경로, 묶음 머리 · 없으면 칩 이름)
MATERIALS = [
    {"id": "환율", "parts": [("exchange/majors", None)]},
    {"id": "금리", "parts": [("standardInterest", "나라별 기준금리"), ("domesticInterest", "국내 금리")]},
    {"id": "에너지", "parts": [("energy", None)]},
    {"id": "금속", "parts": [("metals", None)]},
    {"id": "농산", "parts": [("agricultural", None)]},
    {"id": "운임", "parts": [("transport", None)]},
]
_mat = {"at": 0.0, "groups": None, "fetchedAt": None, "err": {}}
META_KEYS = ("key", "name", "group", "unit", "digits", "kind", "freq")

_lock = threading.Lock()
_hist = {"at": 0.0, "ttl": 0, "rows": {}, "err": {}}
_recent = {"at": 0.0, "rows": {}, "err": {}}
_fetched = {"at": None}


def _num(x):
    if x in (None, "", "-"):
        return None
    try:
        return float(str(x).replace(",", ""))
    except ValueError:
        return None


def _page(it, page, size):
    url = URL % (it["cat"], urllib.parse.quote(it["code"], safe=""), page, size)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        j = json.loads(r.read().decode("utf-8", "replace"))
    if not isinstance(j, list):
        raise RuntimeError("네이버 응답 모양이 다릅니다")
    out = []
    for r in j:
        d = str(r.get("localTradedAt") or "")[:10]
        c = _num(r.get("closePrice"))
        if len(d) == 10 and c is not None:
            out.append([d, _num(r.get("openPrice")), _num(r.get("highPrice")), _num(r.get("lowPrice")), c])
    return out


def _fetch(it, pages, size):
    rows = []
    for p in range(1, pages + 1):
        got = _page(it, p, size)
        rows += got
        if len(got) < size:
            break
    return rows


def _merge(*lists):
    by = {}
    for rows in lists:
        for r in rows or []:
            by[r[0]] = r
    return [by[d] for d in sorted(by)]


def _fix(rows):
    """봉 고치기 — 돌려주는 것: (고친 줄, 고친 날 수)."""
    out, n = [], 0
    for d, o, h, l, c in rows:
        if o is None or o <= 0:
            o = c
        if not h or not l or h <= 0 or l <= 0:
            out.append([d, o, max(o, c), min(o, c), c]); n += 1
        elif h < max(o, c) or l > min(o, c):
            out.append([d, o, max(h, o, c), min(l, o, c), c]); n += 1
        else:
            out.append([d, o, h, l, c])
    return out, n


def _refresh():
    """캐시가 죽었으면 받는다. 잠금 안에서 부른다."""
    now = time.time()
    real = [i for i in ITEMS if "code" in i]
    if now - _hist["at"] >= _hist["ttl"]:
        rows, err = {}, {}
        for it in real:
            try:
                rows[it["key"]] = _fetch(it, PAGES, PAGE_SIZE)
            except Exception as e:
                err[it["key"]] = safe_message(e, 160)
                if it["key"] in _hist["rows"]:
                    rows[it["key"]] = _hist["rows"][it["key"]]     # 못 받으면 어제 것을 그대로 둔다
        _hist.update(at=now, ttl=RETRY_TTL if err else HIST_TTL, rows=rows, err=err)
        _recent.update(at=0.0)
    if now - _recent["at"] >= RECENT_TTL:
        rows, err = {}, {}
        for it in real:
            try:
                rows[it["key"]] = _fetch(it, 1, RECENT_SIZE)
            except Exception as e:
                err[it["key"]] = safe_message(e, 160)
        _recent.update(at=now, rows=rows, err=err)
        _fetched["at"] = datetime.now(KST).isoformat(timespec="seconds")


def _series(key):
    """한 지표 1년치 — (줄, 오류). 봉이 아니면 시가·고가·저가는 None."""
    it = BY_KEY[key]
    if "from" in it:
        a, b = (_series(k)[0] for k in it["from"])
        bm = {r[0]: r[4] for r in b}
        rows = [[r[0], None, None, None, round(r[4] - bm[r[0]], 3)] for r in a if r[0] in bm]
        errs = [e for e in (_series(k)[1] for k in it["from"]) if e]
        return rows, ("; ".join(errs) or None)
    rows = _merge(_hist["rows"].get(key), _recent["rows"].get(key))
    if rows:
        start = (date.fromisoformat(rows[-1][0]) - timedelta(days=365)).isoformat()
        rows = [r for r in rows if r[0] > start]
    if it["kind"] != "candle":
        rows = [[r[0], None, None, None, r[4]] for r in rows]
    return rows, (_recent["err"].get(key) or _hist["err"].get(key))


def _left():
    now = time.time()
    return max(0, int(min(_hist["ttl"] - (now - _hist["at"]), RECENT_TTL - (now - _recent["at"]))))


def _mat_now():
    """재료 줄의 지금 값 — 코드(reutersCode) → (값, 날짜). 원자재 칩이 재료 줄과 같은 값을 내게 한다."""
    try:
        materials()
    except Exception:
        return {}
    out = {}
    for g in (_mat["groups"] or []):
        for p in g["parts"]:
            for r in p["rows"]:
                if r.get("code") and r.get("v") is not None and r.get("at"):
                    out.setdefault(r["code"], (r["v"], r["at"], r.get("pct")))
    return out


def indicators():
    # 재료 줄에 같은 코드가 있는 칩(원자재 · 달러인덱스 · 환율)은 일봉 마지막(어제 종가)이 아니라 재료 줄의 지금 값을 쓴다 (2026-10-14 재권님 「홀딩스의 값이 정확한지 확인하고」 →
    # 값 맞추기 c 「응 해줘」 · WTI 칩 94.14 ↔ 줄 94.77 이던 것). 전일 값은 줄의 등락률이 맞는 쪽을 일봉 끝 둘에서 고른다 —
    # 재료 줄 날짜는 거래소 날짜라 일봉 마지막과 같은 날로 찍혀도 그 뒤 거래일 값일 수 있다(10-15 실측 WTI 줄 10-14 93.89 −1.26% ·
    # 일봉 10-14 95.09 → 전일은 95.09)
    # materials() 가 같은 자물쇠를 잡으므로 자물쇠 밖에서 먼저 읽는다
    now_v = _mat_now()
    with _lock:
        _refresh()
        out = []
        for it in ITEMS:
            rows, err = _series(it["key"])
            last = rows[-1] if rows else None
            prev = rows[-2] if len(rows) > 1 else None
            last = {"d": last[0], "c": last[4]} if last else None
            prev = {"d": prev[0], "c": prev[4]} if prev else None
            m = now_v.get(it.get("code"))         # 재료 줄에 같은 코드가 있는 칩 전부(원자재 · 달러인덱스 · 환율 — 10-15 「응 해줘」)
            if m and last and m[1] >= last["d"]:
                v, d, pct = m
                newer = d > last["d"]
                if not newer and pct is not None and last["c"]:
                    gap = lambda c: abs((v / c - 1) * 100 - pct) if c else 1e9
                    newer = gap(last["c"]) < gap(prev["c"] if prev else None)
                if newer:
                    prev = last
                last = {"d": d, "c": v}
            out.append({**{k: it.get(k) for k in META_KEYS},
                        "last": last,
                        "prev": prev,
                        "error": None if last else (err or "받은 값이 없습니다")})
        return {"ok": any(i["last"] for i in out), "source": "네이버 증권 시장지표",
                "fetchedAt": _fetched["at"], "cacheTtlSec": _left(), "items": out}


# ── 재료 칸 줄 하나의 1년치 (2026-10-14 재권님 「시장지표에 옮겨진 환율등등 목록을 누르면 차트에 캔들이든 선차트든 나와야」 ·
# 「응 커밋하고 그다음 차트해줘」) ──
# 열쇠는 `n:<갈래>:<코드>` — 재료 응답의 path 앞 조각과 reutersCode 다. **그때 재료 목록에 있는 코드만** 받는다(아무 코드나 넘기는 길이
# 되지 않게). 누를 때만 받는다 — 처음 누른 줄은 1년치(다섯 쪽)를 받아 하루 들고, 그 줄은 최근 10건을 `RECENT_TTL` 마다 덧받는다.
# 봉인가 선인가는 받은 값이 정한다 — 고가 · 저가가 온 날이 대부분이면 봉, 아니면 종가 선(위 「봉인가 선인가」 와 같은 뜻).
# 2026-10-14 실측(재료 80줄) — 봉 46 · 종가만 16 · **날짜별 값이 안 오는 줄 18**(나라별 기준금리 17 은 이 길이 404 · 유로/달러는 빈 목록)
_mser = {}
_mlock = threading.Lock()
MAT_PREFIX = "n:"


def _mat_find(key):
    """`n:<갈래>:<코드>` → (그 줄, 갈래) · 재료 목록에 없으면 None."""
    try:
        _, cat, code = key.split(":", 2)
    except ValueError:
        return None
    if _mat["groups"] is None:
        materials()
    for g in (_mat["groups"] or []):
        for p in g["parts"]:
            if p["path"].split("/")[0] != cat:
                continue
            for r in p["rows"]:
                if r.get("code") == code:
                    return r, cat, g["id"], p["path"].endswith("Interest")
    return None


def _mat_digits(v):
    v = abs(v or 0)
    return 2 if v >= 100 else 3


def mat_indicator(key):
    """재료 줄 하나 — indicator() 와 같은 모양. 목록에 없는 열쇠면 None."""
    found = _mat_find(key)
    if not found:
        return None
    row, cat, gid, rate = found
    it = {"cat": cat, "code": row["code"]}
    with _mlock:
        now = time.time()
        got = _mser.get(key) or {"hat": 0.0, "hist": [], "rat": 0.0, "recent": [], "err": None}
        try:
            if now - got["hat"] >= HIST_TTL:
                got.update(hist=_fetch(it, PAGES, PAGE_SIZE), hat=now, rat=now, err=None)
            elif now - got["rat"] >= RECENT_TTL:
                got.update(recent=_fetch(it, 1, RECENT_SIZE), rat=now, err=None)
        except Exception as e:
            got.update(hat=got["hat"] or now - HIST_TTL + RETRY_TTL, rat=now, err=safe_message(e, 160))
        _mser[key] = got
        rows = _merge(got["hist"], got["recent"])
        # 「이 길로는 날짜별 값이 없다」(네이버가 404 · 빈 목록)와 「받다가 실패했다」 를 가른다 — 앞은 고장이 아니라 200 으로 낸다(kis_proxy)
        absent = not rows and (not got["err"] or "404" in got["err"])
        err = got["err"]
    if rows:
        start = (date.fromisoformat(rows[-1][0]) - timedelta(days=365)).isoformat()
        rows = [r for r in rows if r[0] > start]
    ohlc = sum(1 for r in rows if r[2] and r[3] and r[2] > 0 and r[3] > 0 and r[2] != r[3])
    kind = "candle" if rows and ohlc >= len(rows) * 0.8 else "line"
    fixed = 0
    if kind == "candle":
        rows, fixed = _fix(rows)
    bars = [{"d": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4]} if kind == "candle" else {"d": r[0], "c": r[4]}
            for r in rows]
    meta = {"key": key, "name": row["name"], "group": gid, "unit": "%" if rate else "",
            "digits": _mat_digits(bars[-1]["c"] if bars else row.get("v")), "kind": kind, "freq": None}
    return {"ok": bool(bars), "source": "네이버 증권 시장지표", "fetchedAt": datetime.now(KST).isoformat(timespec="seconds"),
            "cacheTtlSec": RECENT_TTL, "item": meta, "bars": bars, "fixed": fixed,
            "absent": bool(absent and not bars),
            "error": None if bars else ("이 지표는 날짜별 값을 받는 곳이 아직 없습니다" if absent else (err or "받은 값이 없습니다"))}


def indicator(key):
    if key.startswith(MAT_PREFIX):
        return mat_indicator(key)
    if key not in BY_KEY:
        return None
    with _lock:
        _refresh()
        it = BY_KEY[key]
        rows, err = _series(key)
        fixed = 0
        if it["kind"] == "candle":
            rows, fixed = _fix(rows)
        bars = [{"d": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4]} if it["kind"] == "candle"
                else {"d": r[0], "c": r[4]} for r in rows]
        return {"ok": bool(bars), "source": "네이버 증권 시장지표", "fetchedAt": _fetched["at"],
                "cacheTtlSec": _left(), "item": {k: it.get(k) for k in META_KEYS},
                "bars": bars, "fixed": fixed, "error": None if bars else (err or "받은 값이 없습니다")}


def _mat_row(x):
    return {"name": x.get("name"), "code": x.get("reutersCode"), "v": _num(x.get("closePrice")),
            "pct": _num(x.get("fluctuationsRatio")), "at": str(x.get("localTradedAt") or "")[:10] or None,
            "unit": x.get("unit") or None}


def materials():
    """오른쪽 칸 재료 — 갈래마다 한 번 · `RECENT_TTL` 마다. 못 받은 갈래는 빈 목록 · `errors` 에 그 이름."""
    with _lock:
        now = time.time()
        if _mat["groups"] is None or now - _mat["at"] >= RECENT_TTL:
            groups, err = [], {}
            for g in MATERIALS:
                parts = []
                for path, label in g["parts"]:
                    try:
                        req = urllib.request.Request(
                            "https://stock.naver.com/api/securityService/marketindex/" + path,
                            headers={"User-Agent": UA})
                        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                            j = json.loads(r.read().decode("utf-8", "replace"))
                        rows = [_mat_row(x) for x in (j if isinstance(j, list) else [])]
                    except Exception as e:
                        err[path] = safe_message(e, 120)
                        old = next((p for og in (_mat["groups"] or []) for p in og["parts"] if p["path"] == path), None)
                        rows = old["rows"] if old else []          # 못 받으면 앞에 받은 것을 그대로 둔다
                    parts.append({"path": path, "label": label or g["id"], "rows": rows})
                groups.append({"id": g["id"], "parts": parts})
            _mat.update(at=now, groups=groups, err=err,
                        fetchedAt=datetime.now(KST).isoformat(timespec="seconds"))
        left = max(0, int(RECENT_TTL - (now - _mat["at"])))
        n = sum(len(p["rows"]) for g in _mat["groups"] for p in g["parts"])
        return {"ok": n > 0, "source": "네이버 증권 시장지표", "fetchedAt": _mat["fetchedAt"],
                "cacheTtlSec": left, "groups": _mat["groups"], "count": n, "errors": _mat["err"]}
