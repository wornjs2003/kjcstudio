#!/usr/bin/env python3
"""미국장 섹터 정리를 아침 7시에 텔레그램으로 보낸다 (2026-11-03 지시).
재권님 — 「미국장 정리한거 아침 7시에 텔레그램으로 정리해서 매일 보내주도록 해줘」 · 「섹터별로 정리한거」 ·
안 (가) 규칙 글 / (나) 무인 클로드가 뉴스로 까닭을 붙임 / (다) 07:30 글에 덧붙임 중 「나로 해줘」.

하는 일 (화~토 아침 — 미국 월~금 장 다음 날. launchd 등록은 「켜기」 라 재권님 지시로 한다)
    1 8765 에서 숫자를 받는다 — 지수(/api/kis/indices) · 섹터 열둘(/api/kis/us-sectors) · 섹터별 종목(/api/kis/us-sector-stocks) ·
      원자재 · 금리(/api/market/indicators). **글 속 숫자는 전부 여기서 온다** — 클로드는 숫자를 만들지 않는다
    2 S&P500 의 날짜가 직전 평일(미국 장날)이 아니면 끝 — 미국 휴장이거나 값이 아직 안 왔다. 보내지 않고 카드에 한 줄
    3 무인 claude -p 한 번 — 도구는 웹 검색 · 웹 읽기 둘만 · 설정 · 훅 안 읽음(--safe-mode) · 글(JSON)만 돌려받는다.
      강한 섹터 셋 · 약한 섹터 셋의 「까닭」 과 출처 주소 · 한국장 볼 것(해석이라고 표시)을 쓴다
    4 글을 엮어 07:00 이 될 때까지 기다렸다 보낸다 — 조용한 시간(22:00~07:00)은 dart.telegram_send 가 막는다
    5 보드 카드 「미국 섹터 정리 아침 7시」 에 한 줄 — 보냄/안 보냄 · 비용(달러) · 걸린 초

보내는 자리 — 텔레그램은 dart.telegram_send 하나로만 나간다(조용한 시간 · 나눠 보내기 · 토큰 가리기가 거기 있다).
**--send 와 KJC_ROLE=server 가 함께 있을 때만** 텔레그램 칸을 읽는다(「알림은 메인서버에서만 나간다」 의 이 도구 쪽 겹).
DB 는 읽기 전용으로 연다(KJC_DB_READONLY=1) — 보낸 글 기록(tglog)은 서버 DB 라 이 도구는 안 적는다(카드에 적는다).

    python3 company-setup/tools/us-sector-morning.py                         글만 화면에(보내지 않음 · 카드 없음)
    python3 company-setup/tools/us-sector-morning.py --result-file r.json    클로드를 안 부르고 글 엮기만 시험
    KJC_ROLE=server python3 company-setup/tools/us-sector-morning.py --send  보낸다 — launchd 가 이 모양으로 부른다
"""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("KJC_DB_READONLY", "1")          # dart 를 부르기 전에 — 메인 DB 에 안 쓴다
sys.path.insert(0, os.path.join(ROOT, "holdings", "server"))
from secrets_guard import safe_message  # noqa: E402 — 오류 문구는 카드(밖)로 나가므로 가려 적는다

SERVER = os.environ.get("KJC_DATA_URL", "http://localhost:8765").rstrip("/")
CARD = "미국 섹터 정리 아침 7시"
BUDGET_USD = "2"                     # 한 번에 이 이상 쓰면 claude 가 스스로 멈춘다
SEND_AT = (7, 0)                     # 이 시각 전이면 기다렸다 보낸다
PICK = 3                             # 강한 · 약한 섹터 몇 개에 까닭을 붙이나
PATH_ADD = ["/opt/homebrew/bin", os.path.expanduser("~/.local/bin"), "/usr/local/bin"]
KST = dt.timezone(dt.timedelta(hours=9))
DAYS = "월화수목금토일"


def log(msg):
    print("%s %s" % (dt.datetime.now(KST).strftime("%m-%d %H:%M:%S"), msg), flush=True)


def tool(name):
    p = shutil.which(name, path=os.pathsep.join(PATH_ADD + [os.environ.get("PATH", "")]))
    if not p:
        # SystemExit 가 아니라 RuntimeError — main 의 except Exception 이 잡아 「숫자만」 으로 간다(qa 검수 11-03)
        raise RuntimeError("%s 를 못 찾았습니다(PATH)" % name)
    return p


def get(path):
    with urllib.request.urlopen(SERVER + path, timeout=20) as r:
        return json.load(r)


def card(line):
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "board-card.py"), CARD, line],
                   capture_output=True, text=True, timeout=30)


# ---------------------------------------------------------------- 숫자 받기

def last_weekday(today):
    d = today - dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def gather():
    raw = get("/api/kis/indices")
    idx = {i["code"]: i for i in raw["data"]}
    sp = idx.get("SPX") or {}
    day = sp.get("asOf") or ""
    allsec = get("/api/kis/us-sectors")["data"]
    # 등락률이 없는 섹터는 0 으로 두지 않는다 — 정렬 · 강약 뽑기에서 빼고 「그 밖」 에 「—」 로 낸다(개념정의 검수 11-03)
    sectors = sorted((x for x in allsec if isinstance(x.get("pct"), (int, float))), key=lambda x: x["pct"], reverse=True)
    nopct = [x for x in allsec if not isinstance(x.get("pct"), (int, float))]
    for s in sectors:
        try:
            rows = get("/api/kis/us-sector-stocks?" + urllib.parse.urlencode({"no": s["no"]}))["data"]
        except Exception as e:
            log("섹터 종목 못 받음 %s — %s" % (s["no"], safe_message(e, 80)))
            rows = []
        rows = [r for r in rows if isinstance(r.get("pct"), (int, float))]
        rows.sort(key=lambda r: r["pct"], reverse=True)
        # ⬆ 는 오른 종목만 · ⬇ 는 내린 종목만 — 오른 종목이 하나뿐인 날 내린 종목이 ⬆ 에 섞이지 않게(qa 검수 11-03)
        s["top"] = [r for r in rows if r["pct"] > 0][:2]
        s["bottom"] = [r for r in rows if r["pct"] < 0][-2:][::-1]
    ind = {i["key"]: i for i in get("/api/market/indicators")["items"]}
    return {"day": day, "idx": idx, "sectors": sectors, "ind": ind, "nopct": nopct, "night": raw.get("futuresNight") or {}}


# ---------------------------------------------------------------- 클로드

def ask_claude(data):
    s = data["sectors"]
    picks = s[:PICK] + s[-PICK:]
    brief = {
        "미국장 날짜": data["day"],
        "지수": {k: data["idx"][k].get("changePct") for k in ("SPX", "NASDAQ", "NDX", "SOX", "VIX") if k in data["idx"]},
        "섹터": [{"no": x["no"], "이름": x["name"], "등락률": round(x["pct"], 2) if isinstance(x.get("pct"), (int, float)) else None,
                 "강한 종목": [(r["name"], r["code"], round(r["pct"], 1)) for r in x["top"]],
                 "약한 종목": [(r["name"], r["code"], round(r["pct"], 1)) for r in x["bottom"]]} for x in picks],
        "코스피200 야간선물 등락률": (data.get("night") or {}).get("changePct"),
    }
    prompt = (
        "너는 한국 투자자에게 아침마다 미국장 섹터 정리를 보내는 사람이다. 아래 숫자는 서버가 받은 값이라 그대로 믿는다. "
        "웹 검색으로 그날(미국 시각) 마감 기사를 찾아, 각 섹터가 왜 그렇게 움직였는지 까닭을 적어라.\n"
        "규칙: 한국어로만 · 기사에서 확인한 것만(지어내지 않음 · 못 찾으면 why 에 「까닭 못 찾음」) · 숫자는 새로 만들지 않음 · "
        "섹터 하나에 한두 문장(80자 안쪽) · src 는 그 까닭을 확인한 기사 주소 하나 · "
        "korea 는 한국장에서 볼 것 두세 줄인데 기사가 아니라 너의 해석이므로 줄 앞에 「(해석)」 · "
        "headline 은 그날 미국장을 한 줄(60자 안쪽).\n"
        "출력은 JSON 하나만(설명 · 코드블록 없이): "
        '{"headline": "...", "why": {"<섹터 no>": {"text": "...", "src": "https://..."}}, "korea": ["(해석) ..."]}\n\n'
        "숫자:\n" + json.dumps(brief, ensure_ascii=False))
    t0 = time.time()
    r = subprocess.run([tool("claude"), "-p", "--safe-mode", "--tools", "WebSearch,WebFetch",
                        "--allowedTools", "WebSearch", "WebFetch", "--no-session-persistence",
                        "--output-format", "json", "--max-budget-usd", BUDGET_USD],
                       input=prompt, capture_output=True, text=True, timeout=900, cwd=tempfile.gettempdir())
    if r.returncode != 0:
        raise RuntimeError("claude 종료 %d" % r.returncode)
    out = json.loads(r.stdout)
    out["_secs"] = round(time.time() - t0)
    return out


def parse(result):
    s = result.get("result") or ""
    s = s[s.find("{"): s.rfind("}") + 1]
    d = json.loads(s)
    if not isinstance(d.get("why"), dict):
        raise ValueError("결과에 why 가 없습니다")
    return d


# ---------------------------------------------------------------- 글 엮기

def pct(v):
    if not isinstance(v, (int, float)):
        return "—"
    return "%+.2f%%" % v


def dot(v):
    """한국식 색 — 오름 빨강 · 내림 파랑 · 0 · 없음은 흰 점(텔레그램 글에는 색을 못 넣어 점으로 낸다)"""
    if not isinstance(v, (int, float)) or v == 0:
        return "⚪"
    return "🔴" if v > 0 else "🔵"


def stocks(rows):
    return " · ".join("%s %+.1f" % (r["name"], r["pct"]) for r in rows) or "—"


def compose(data, ai):
    day = data["day"]
    try:
        d = dt.datetime.strptime(day, "%Y%m%d").date()
        title_day = "%d/%d(%s)" % (d.month, d.day, DAYS[d.weekday()])
    except ValueError:
        title_day = day or "날짜 모름"
    idx, ind, s = data["idx"], data["ind"], data["sectors"]
    L = ["🇺🇸 미국장 섹터 정리 · %s 마감" % title_day, "━━━━━━━━━━━━━━"]
    if ai.get("headline"):
        L.append("📌 " + ai["headline"])
    # 한국장 볼 것은 맨 위 — 야간선물 · 해석 세 줄(재권님 「야간 선물은 맨위쪽으로」 · 「한국장에서 볼것 이걸 다 맨 위로」 11-03)
    L += ["", "🇰🇷 한국장 볼 것"]
    nf = data.get("night") or {}
    v = nf.get("changePct")
    if isinstance(nf.get("price"), (int, float)):
        L.append("🌙 %s 코스피200 야간선물 %.2f %s%s" % (dot(v), nf["price"], pct(v), "" if nf.get("open") else "  (마감)"))
    else:
        L.append("🌙 ⚪ 코스피200 야간선물 — 못 받음")
    L.extend("%s %s" % ("①②③④⑤"[i] if i < 5 else "·", k) for i, k in enumerate(ai.get("korea") or []))
    L += ["", "📊 지수"]
    for k, n in (("SPX", "S&P500"), ("NASDAQ", "나스닥"), ("SOX", "반도체지수"), ("VIX", "VIX")):
        v = (idx.get(k) or {}).get("changePct")
        val = (idx.get(k) or {}).get("value")
        L.append("%s %s %s%s" % (dot(v), n, pct(v), "  (%.2f)" % val if k == "VIX" and val else ""))
    extra = []
    for k, n in (("wti", "WTI"), ("dxy", "달러인덱스"), ("us10", "미국10년")):
        last = (ind.get(k) or {}).get("last") or {}
        if last.get("c") is not None:
            extra.append("%s %s%s" % (n, last["c"], "" if last.get("d", "").replace("-", "") == day else "(%s)" % last.get("d", "")[5:].replace("-", "/")))
    if extra:
        L.append("▫️ " + " · ".join(extra))
    why = ai.get("why") or {}

    def block(title, rows):
        L.extend(["", title])
        for i, x in enumerate(rows, 1):
            L.append("")
            L.append("%s %d. %s %s  (오름 %s · 내림 %s)" % (dot(x.get("pct")), i, x["name"], pct(x.get("pct")), x.get("rise", "—"), x.get("fall", "—")))
            w = why.get(x["no"]) or {}
            if w.get("text"):
                L.append("💬 " + w["text"])
            L.append("⬆ " + stocks(x["top"]))
            L.append("⬇ " + stocks(x["bottom"]))
    block("🔥 강한 섹터", s[:PICK])
    block("🧊 약한 섹터", s[-PICK:][::-1])
    mid = (s[PICK:-PICK] if len(s) > PICK * 2 else []) + list(data.get("nopct") or [])
    if mid:
        L += ["", "📋 그 밖"]
        L.extend("%s %s %s" % (dot(x.get("pct")), x["name"], pct(x.get("pct"))) for x in mid)
    srcs = []
    for x in s[:PICK] + s[-PICK:]:
        u = (why.get(x["no"]) or {}).get("src")
        if u and u not in srcs:
            srcs.append(u)
    L += ["", "━━━━━━━━━━━━━━"]
    if srcs:
        L.append("🔗 출처")
        L.extend(srcs)
    L.append("숫자: 서버(KIS · State Street 구성) · 까닭: 무인 클로드가 기사 검색")
    return "\n".join(L)


# ---------------------------------------------------------------- 보내기

def send(text):
    import dart                       # 여기서 부른다 — 글만 볼 때는 텔레그램 쪽을 아예 안 읽는다
    dart.NOTIFY_LOCAL = True          # 이 함수는 --send + KJC_ROLE=server 일 때만 온다(main 에서 가른다)
    now = dt.datetime.now(KST)
    at = now.replace(hour=SEND_AT[0], minute=SEND_AT[1], second=5, microsecond=0)
    if now < at:
        log("%s 까지 기다림" % at.strftime("%H:%M:%S"))
        time.sleep((at - now).total_seconds())
    return dart.telegram_send(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="텔레그램으로 보낸다(KJC_ROLE=server 일 때만)")
    ap.add_argument("--result-file", help="claude 를 부르지 않고 이 결과(JSON)를 쓴다 — 시험용")
    ap.add_argument("--any-day", action="store_true", help="미국장 날짜 검사를 건너뛴다 — 시험용")
    a = ap.parse_args()
    sending = a.send and os.environ.get("KJC_ROLE") == "server"
    if a.send and not sending:
        log("--send 인데 KJC_ROLE=server 가 아니라 보내지 않습니다")

    try:
        data = gather()
    except Exception as e:
        log("서버 값 못 받음 — " + safe_message(e, 120))
        if sending:
            card("못 보냄 — 서버(8765) 값 못 받음 %s" % safe_message(e, 80))
        return 2
    want = last_weekday(dt.datetime.now(KST).date()).strftime("%Y%m%d")
    if data["day"] != want and not a.any_day:
        log("미국장 날짜 %s ≠ 직전 평일 %s — 휴장이거나 값이 아직 안 왔다. 안 보냄" % (data["day"] or "없음", want))
        if sending:
            card("안 보냄 — S&P500 날짜 %s · 직전 평일 %s (휴장 또는 값 없음)" % (data["day"] or "없음", want))
        return 0

    cost = secs = None
    try:
        if a.result_file:
            with open(a.result_file, encoding="utf-8") as f:
                raw = json.load(f)
        else:
            raw = ask_claude(data)
            cost, secs = raw.get("total_cost_usd"), raw.get("_secs")
        ai = parse(raw)
    except Exception as e:
        log("까닭 못 받음 — %s · 숫자만 보냄" % safe_message(e, 120))
        ai = {"headline": "(까닭을 못 받아 숫자만 보냅니다)", "why": {}, "korea": []}

    text = compose(data, ai)
    print(text)
    print("\n— 글자 %d · 비용 %s달러 · %s초" % (len(text), cost if cost is not None else "—", secs if secs is not None else "—"))
    if not sending:
        return 0
    ok, why = send(text)
    log("보냄" if ok else "못 보냄 — " + why)
    card("%s %s · 비용 %s달러 · %s초 · 글자 %d" % ("보냄" if ok else "못 보냄(%s)" % why[:60], data["day"],
                                              ("%.2f" % cost) if isinstance(cost, (int, float)) else "—",
                                              secs if secs is not None else "—", len(text)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
