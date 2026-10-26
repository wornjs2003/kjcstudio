# -*- coding: utf-8 -*-
"""넥스트레이드 장 전 거래량이 전날의 2배 넘은 종목 — 08:50 목록 한 통 (2026-10-26).

재권님 — 「넥스트장에서 전날과 비교해서 거래량이 100%이상 증가한 종목도 텔레그램으로 알려주도록 해줘」(13:1x) →
「장외 거래량은 8시 50분에 코스피 코스닥 종목 전부」(13:2x) · 작업우선순위 경유.

    언제     평일 08:51 한 번(장 전 시장이 08:50 에 닫힌 뒤) — 장 뒤(20:00) 통은 말씀에 없어 안 넣었다
    범위     코스피 · 코스닥 **주권 전부** — KIS 종목 마스터(kospi_code.mst · kosdaq_code.mst)의 그룹 「ST」.
             ETF · ETN · 리츠 · 외국 DR 은 뺀다(「종목」 이라 하셨다). 마스터를 그날 받고, 못 받으면 전날 저장한 목록
    값       멀티 시세(intstock-multprice) 시장구분 **NX(넥스트레이드만)** 의 누적 거래량 — 08:50 에는 곧 장 전 거래량이다.
             (2026-10-26 13:2x 실측 — 같은 때 삼성전자 J 7,249,105 · NX 4,129,183 · UN 11,378,394 = J + NX.)
             넥스트레이드에서 안 사고파는 종목은 0 이다. 30종목씩 묶어 **하루 90번쯤** 부른다
    견줌     오늘 장 전 거래량 ≥ 전날(저장해 둔 앞 거래일) 장 전 거래량 × RATIO · 전날이 MIN_PREV 주 이상인 것만
             (전날 1주 → 오늘 2주 같은 헛배율을 막는다 · 재권님 답에 문턱이 없어 추천값 1만주 — 글 머리에 적는다)
    글       배율 큰 순 · 종목(코드) · 배율 · 오늘 · 전날 · 장외가 · 전날 정규장 종가 대비 % · 길면 dart.telegram_send 가 나눠 보낸다
    저장     market.db 의 `nxt_pre` (날 · 종목 · 거래량 · 장외가 · 전날 종가) — 다음 날 견줄 재료. **처음 켠 다음 거래일부터 목록이 나온다**
    휴장     NX 거래량 합이 0 이면 휴장으로 보고 저장도 발송도 안 한다(공휴일을 따로 가리지 못한다)

**보내기는 따로 켠다** — `SEND`. 꺼져 있으면 저장 · 셈만 하고 로그와 `status()` 에 보낼 글을 남긴다(「켜기 전에 먼저 잰다」).
8765 만 돈다(`kis_proxy` 가 `is_sender` 로 부른다). KIS 는 `proxy.kis_get` 으로 — 예산 · 토큰은 그쪽이 든다.
"""

import io
import threading
import time
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone

import dart
import tglog
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))

SEND = False
RUN_AT = (8, 51)                # 장 전 시장(08:00~08:50)이 닫힌 뒤
RUN_UNTIL = (9, 0)              # 이 시각이 지나면 그날은 건너뛴다 — 정규장이 열리면 NX 거래량에 본장이 섞인다
RATIO = 2.0                     # 「100% 이상 증가」 = 2배 이상
MIN_PREV = 10000                # 전날 장 전 거래량 문턱(주)
MULTI_MAX = 30                  # 멀티 시세 한 번에 받는 종목 수(kis_proxy.MULTI_MAX 와 같은 KIS 한도)
GAP_SEC = 0.15                  # 묶음 사이 쉼 — 예산은 kis_get 이 지키지만 아침 다른 받기에 비켜선다
TICK = 20                       # 바퀴(초)

MASTER = "https://new.real.download.dws.co.kr/common/master/%s_code.mst.zip"
# 줄 끝에서 그룹 코드까지의 글자 수 — 2026-10-26 실측(삼성전자 · 에코프로비엠 줄). KIS 예제의 228 · 222 는 줄 끝 글자 하나를 센 값이다
MASTER_TAIL = {"kospi": 227, "kosdaq": 221}

_SCHEMA = """CREATE TABLE IF NOT EXISTS nxt_pre (
    day TEXT NOT NULL, code TEXT NOT NULL, name TEXT, vol INTEGER, price INTEGER, prev_close INTEGER,
    saved_at TEXT, PRIMARY KEY (day, code))"""

_status = {"lastRunDay": None, "lastRunAt": None, "codes": None, "nonzero": None, "hits": None,
           "preview": None, "error": None, "send": SEND}


def _now():
    return datetime.now(KST)


def master_codes():
    """코스피 · 코스닥 주권 {code: name}. 받기 실패면 예외."""
    out = {}
    for mk, tail in MASTER_TAIL.items():
        req = urllib.request.Request(MASTER % mk, headers={"User-Agent": "Mozilla/5.0 KJCStudio"})
        with urllib.request.urlopen(req, timeout=30) as r:
            z = zipfile.ZipFile(io.BytesIO(r.read()))
        text = z.read(z.namelist()[0]).decode("cp949", "replace")
        for row in text.split("\n"):
            row = row.rstrip("\r")
            if len(row) <= tail or row[-tail:-tail + 2] != "ST":
                continue
            code = row[0:9].strip()
            if len(code) == 6:
                out[code] = row[21:-tail].strip()
    if len(out) < 1000:                       # 모양이 바뀌었으면 수가 크게 준다 — 그날은 쓰지 않는다
        raise RuntimeError("마스터에서 주권이 %d개뿐입니다(모양이 바뀌었을 수 있음)" % len(out))
    return out


def _init(proxy):
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)


def _prev_day(proxy, day):
    with proxy._db_lock, proxy.db_conn() as conn:
        r = conn.execute("SELECT MAX(day) d FROM nxt_pre WHERE day < ?", (day,)).fetchone()
    return r["d"] if r else None


def _saved(proxy, day):
    with proxy._db_lock, proxy.db_conn() as conn:
        return {r["code"]: dict(r) for r in conn.execute("SELECT * FROM nxt_pre WHERE day = ?", (day,))}


def fetch_nx(proxy, cfg, codes):
    """{code: {vol, price, prev_close, name}} — NX 시장 누적 거래량 · 현재가 · 전일 종가."""
    out = {}
    codes = list(codes)
    for i in range(0, len(codes), MULTI_MAX):
        chunk = codes[i:i + MULTI_MAX]
        params = {}
        for n, c in enumerate(chunk, 1):
            params["FID_COND_MRKT_DIV_CODE_%d" % n] = "NX"
            params["FID_INPUT_ISCD_%d" % n] = c
        data = proxy.kis_get(cfg, "/uapi/domestic-stock/v1/quotations/intstock-multprice", params, "FHKST11300006")
        for r in (data or {}).get("output") or []:
            code = (r.get("inter_shrn_iscd") or "").strip()
            if not code:
                continue
            num = lambda k: proxy._num(r.get(k), int)
            out[code] = {"vol": num("acml_vol") or 0, "price": num("inter2_prpr"),
                         "prev_close": num("inter2_prdy_clpr"), "name": (r.get("inter_kor_isnm") or "").strip()}
        time.sleep(GAP_SEC)
    return out


def compare(today, prev):
    """오늘 · 전날 {code: row} → 2배 넘은 것 [{code, name, vol, prev, ratio, price, pct}] 배율 큰 순."""
    hits = []
    for code, t in today.items():
        p = prev.get(code)
        if not p or (p.get("vol") or 0) < MIN_PREV or not t.get("vol"):
            continue
        ratio = t["vol"] / p["vol"]
        if ratio < RATIO:
            continue
        pc = t.get("prev_close")
        pct = (t["price"] / pc - 1) * 100 if t.get("price") and pc else None
        hits.append({"code": code, "name": t.get("name") or code, "vol": t["vol"], "prev": p["vol"],
                     "ratio": ratio, "price": t.get("price"), "pct": pct})
    hits.sort(key=lambda h: -h["ratio"])
    return hits


def format_list(day, prev_day, hits):
    d = "%s-%s" % (day[4:6], day[6:8])
    head = ("📈 넥스트레이드 장 전 거래량 2배 · %s 08:50\n"
            "전날(%s-%s) 장 전 %s주 이상인 종목 중 %d개 · 배율 큰 순 · 참고용입니다"
            % (d, prev_day[4:6], prev_day[6:8], format(MIN_PREV, ","), len(hits)))
    lines = []
    for h in hits:
        pct = "—" if h["pct"] is None else "%+.1f%%" % h["pct"]
        price = "—" if not h["price"] else format(h["price"], ",") + "원"
        lines.append("%s(%s) %.1f배 · 오늘 %s주 · 전날 %s주 · 장외가 %s · 종가 대비 %s"
                     % (h["name"], h["code"], h["ratio"], format(h["vol"], ","), format(h["prev"], ","), price, pct))
    return head + ("\n\n" + "\n".join(lines) if lines else "\n\n2배 넘은 종목이 없습니다")


def run_once(proxy, day=None):
    """그날 한 번 — 받기 · 저장 · 견줌 · (켜져 있으면) 보내기. 결과 dict."""
    _init(proxy)
    day = day or _now().strftime("%Y%m%d")
    cfg = proxy.load_secrets()
    prev_day = _prev_day(proxy, day)
    try:
        names = master_codes()
    except Exception as e:
        # 마스터를 못 받으면 앞 거래일에 저장한 목록으로 — 새로 상장한 종목만 빠진다
        if not prev_day:
            raise RuntimeError("종목 마스터를 못 받았고 저장한 목록도 없습니다: %s" % safe_message(e, 120))
        names = {c: r.get("name") for c, r in _saved(proxy, prev_day).items()}
        _status["error"] = "마스터 받기 실패 — 앞 거래일 목록(%d) 사용: %s" % (len(names), safe_message(e, 120))
    rows = fetch_nx(proxy, cfg, names)
    total = sum(r["vol"] for r in rows.values())
    _status.update({"lastRunDay": day, "lastRunAt": _now().isoformat(timespec="seconds"),
                    "codes": len(names), "nonzero": sum(1 for r in rows.values() if r["vol"])})
    if not total:
        _status.update({"hits": None, "preview": None, "error": "NX 거래량 합이 0 — 휴장으로 보고 저장 · 발송 안 함"})
        return dict(_status)
    stamp = _now().isoformat(timespec="seconds")
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO nxt_pre (day, code, name, vol, price, prev_close, saved_at) VALUES (?,?,?,?,?,?,?)",
            [(day, c, r["name"] or names.get(c), r["vol"], r["price"], r["prev_close"], stamp) for c, r in rows.items()])
    if not prev_day:
        _status.update({"hits": None, "preview": None, "error": "첫날 — 저장만 했습니다. 다음 거래일부터 견줍니다"})
        return dict(_status)
    hits = compare(rows, _saved(proxy, prev_day))
    text = format_list(day, prev_day, hits)
    _status.update({"hits": len(hits), "preview": text})
    if SEND:
        ok, err = dart.telegram_send(text)
        if not ok:
            _status["error"] = "보내지 못했습니다: %s" % err
    else:
        print("  [장 전 거래량·안보냄] %d종목 — %s" % (len(hits), text.split("\n")[0]))
        tglog.note(text, "off")
    return dict(_status)


def status():
    return dict(_status, send=SEND)


def start(proxy):
    """서버가 뜰 때 한 번. 평일 08:51~09:00 사이 첫 바퀴에 그날 한 번 돈다."""
    def loop():
        time.sleep(30)
        while True:
            try:
                now = _now()
                hm = (now.hour, now.minute)
                day = now.strftime("%Y%m%d")
                if now.weekday() < 5 and RUN_AT <= hm < RUN_UNTIL and _status["lastRunDay"] != day:
                    _status["lastRunDay"] = day          # 실패해도 그날은 한 번만 — 09:00 넘어 다시 받으면 본장이 섞인다
                    try:
                        r = run_once(proxy, day)
                        print("  [장 전 거래량] %s종목 중 거래 %s · 2배 %s" % (r.get("codes"), r.get("nonzero"), r.get("hits")))
                    except Exception as e:
                        _status["error"] = safe_message(e, 160)
                        print("  [장 전 거래량] 실패: %s" % type(e).__name__)
            except Exception as e:
                print("  [장 전 거래량] 예기치 못한 오류: %s" % type(e).__name__)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="nxt-pre").start()
    return True
