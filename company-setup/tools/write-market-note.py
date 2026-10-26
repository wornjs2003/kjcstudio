#!/usr/bin/env python3
"""자동 시황 글 — 받아 둔 값에 정해진 문장틀로 숫자만 넣는다 (2026-10-26 재권님 「시황 글이랑 일정도 자동으로 갱신되게 해줘」 →
안 (가) 규칙 문장 「응」 · 작업우선순위 경유). 세션이 기사를 읽고 쓰는 글(data/market-note.json · 스킬 market-brief)과 같은 틀이고,
검사도 같은 것(check-market-note.py)을 거친다. 판단 · 원인은 넣지 않는다 — 「읽기」 줄은 숫자 방향으로 고르는 정해진 문장이다.

    python3 company-setup/tools/write-market-note.py [--port 8765] [--data <값 파일 폴더>] [--out <경로>] [--also <경로> …]

재료 — 홀딩스 서버(「두 구역이 같은 값을 쓰면」 · 서버에 있는 값은 서버에서): /api/market/indicator(금리 · 환율 · 원자재 · 운임 1년치) ·
/api/kis/index-candles(코스피 · 코스닥 일봉) · /api/kis/indices(오른 · 내린 종목 수 · 미국 지수) · /api/macro/releases(다음 발표).
서버에 없는 것은 받는 도구들이 쓴 파일: world-macro(나라별 정책금리 · 물가 · 경기선행 · 주가 한 달) · external-risk(대외변수).
돌리는 자리 — launchd market-data(평일 06:30 · 16:10) 받기 끝. 결과는 --out(market-note-live.json · .gitignore) — 화면이 손 글과 견주어 새 것을 보인다.

못 만들면(서버 · 파일을 못 읽음 · 검사에 걸림) 옛 -live 글을 그대로 두고 그 안에 failedAt · failedWhy 만 적는다 — 화면이 「못 만듦(시각)」 을 붙인다.
종료 0 씀 · 1 못 만듦
"""
import datetime, json, os, subprocess, sys, urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _save import targets  # noqa: E402  --out · --also 읽기는 받는 도구들과 같은 것

A = sys.argv
PORT = A[A.index("--port") + 1] if "--port" in A else "8765"
DATA = A[A.index("--data") + 1] if "--data" in A else os.path.join(HERE, "..", "data")
NOW = datetime.datetime.now()


class Miss(Exception):
    pass


def get(path):
    try:
        with urllib.request.urlopen("http://localhost:%s%s" % (PORT, path), timeout=20) as r:
            j = json.load(r)
    except Exception as ex:
        raise Miss("서버 %s 못 읽음(%s)" % (path.split("?")[0], type(ex).__name__))
    if not j or j.get("ok") is False:
        raise Miss("서버 %s 오류" % path.split("?")[0])
    return j


def live(name):
    for n in (name + "-live.json", name + ".json"):
        p = os.path.join(DATA, n)
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    raise Miss("%s 파일 없음" % name)


# ── 셈
def d(s):
    s = str(s).replace("-", "")[:8]
    return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def ago(rows, days):
    """rows = [(날짜, 값)] 날짜 순 — 마지막 날에서 days 일 전 이하의 가장 늦은 값"""
    if not rows:
        return None
    cut = d(rows[-1][0]) - datetime.timedelta(days=days)
    back = [v for t, v in rows if d(t) <= cut]
    return back[-1] if back else None


def ind(key):
    j = get("/api/market/indicator?key=" + key)
    rows = [(b["d"], b["c"]) for b in j.get("bars") or [] if b.get("c") is not None]
    if not rows:
        raise Miss("서버 지표 %s 비었음" % key)
    return rows


def pct(a, b):
    return None if a is None or b in (None, 0) else (a / b - 1) * 100


def sg(x, n=1, unit="%"):
    return "—" if x is None else ("%+.*f%s" % (n, x, unit)).replace("+-", "-")


def bp(a, b):
    return None if a is None or b is None else round((a - b) * 100)


def md(s):
    t = d(s)
    return "%d월 %d일" % (t.month, t.day)


def comma(x, n=2):
    return "—" if x is None else "{:,.{n}f}".format(x, n=n)


def main():
    lacks = []   # 빠진 칸 — 한계에 적는다
    W = live("world-macro")
    C = W.get("countries") or {}
    R = live("external-risk")

    us10, us2, kr3 = ind("us10"), ind("us2"), ind("kr3")
    try:
        spread = ind("spread")
    except Miss:
        spread = None
        lacks.append("신용 가산금리")
    kospi = [(b["ts"], b["close"]) for b in get("/api/kis/index-candles?code=KOSPI")["data"]["bars"] if b.get("close")]
    kosdaq = [(b["ts"], b["close"]) for b in get("/api/kis/index-candles?code=KOSDAQ")["data"]["bars"] if b.get("close")]
    # 장중(평일 09:00~15:40)에 돌리면 일봉 마지막 칸이 그날 장중 값이다 — 「마감」 으로 쓰지 않게 그 칸을 뺀다(손으로 돌릴 때 · launchd 는 06:30 · 16:10)
    today = NOW.strftime("%Y%m%d")
    if NOW.weekday() < 5 and (9, 0) <= (NOW.hour, NOW.minute) < (15, 40):
        kospi = [x for x in kospi if x[0] != today]
        kosdaq = [x for x in kosdaq if x[0] != today]
    if len(kospi) < 30 or len(kosdaq) < 30:
        raise Miss("지수 일봉이 모자람")
    IX = {x["code"]: x for x in get("/api/kis/indices")["data"]}

    # 1. 금리 · 물가
    up = [c["name"] for c in C.values() if (c.get("rate") or {}).get("dir") == "up"]
    dn = [c["name"] for c in C.values() if (c.get("rate") or {}).get("dir") == "down"]
    hot = [(c["name"], c["cpi"]["v"]) for c in C.values() if (c.get("cpi") or {}).get("v") is not None and not c["cpi"].get("annual") and c["cpi"]["v"] > 2]
    u10, u10m = us10[-1][1], bp(us10[-1][1], ago(us10, 30))
    u2m = bp(us2[-1][1], ago(us2, 30))
    k3m = bp(kr3[-1][1], ago(kr3, 30))
    s1 = [{"t": "정책금리 직전 결정이 인상인 곳 %d곳(%s) · 인하 %d곳%s 입니다." % (
              len(up), " · ".join(up) or "없음", len(dn), "(%s)" % " · ".join(dn) if dn else "")},
          {"t": "물가가 목표 2%% 보다 높은 곳: %s." % (" · ".join("%s %.1f%%" % h for h in hot) or "없음")},
          {"t": "미국 10년 금리 **%.2f%%(한 달 %s)** · 2년 %.2f%%(%s)." % (u10, sg(u10m, 0, "bp"), us2[-1][1], sg(u2m, 0, "bp"))},
          {"t": "한국 국채 3년 %.2f%%(한 달 %s)%s." % (kr3[-1][1], sg(k3m, 0, "bp"),
              " · 회사채 가산금리 %.2f%%p(한 달 %s)" % (spread[-1][1], sg(bp(spread[-1][1], ago(spread, 30)), 0, "bp")) if spread else "")}]
    if u10m is None:
        r1 = "미국 금리의 한 달 변화를 잴 값이 없어 방향은 말하기 어려울 수 있습니다."
    elif u10m >= 10:
        r1 = "미국 장기 금리가 한 달 사이 올라, 높은 금리가 오래 간다는 쪽에 값이 매겨지는 것으로 읽힙니다."
    elif u10m <= -10:
        r1 = "미국 장기 금리가 한 달 사이 내려, 금리 부담이 조금 덜어지는 쪽으로 읽힙니다."
    else:
        r1 = "미국 장기 금리가 한 달 사이 크게 움직이지 않아, 금리 쪽 압력은 그대로인 것으로 보입니다."
    h1 = "1. 금리 · 물가 — " + ("오르는 쪽" if (u10m or 0) >= 10 else "내리는 쪽" if (u10m or 0) <= -10 else "제자리")

    # 2. 경기
    cu = [(c["name"], c["cli"]["v"]) for c in C.values() if (c.get("cli") or {}).get("v") is not None and c["cli"].get("prev") is not None and c["cli"]["v"] > c["cli"]["prev"]]
    cd = [(c["name"], c["cli"]["v"]) for c in C.values() if (c.get("cli") or {}).get("v") is not None and c["cli"].get("prev") is not None and c["cli"]["v"] < c["cli"]["prev"]]
    clid = next((c["cli"]["date"] for c in C.values() if c.get("cli")), "")
    y3m = ((W.get("series") or {}).get("yld") or {}).get("US3M") or []
    s2 = [{"t": "경기선행지수(%s · 100 = 장기 평균) 오름: %s / 내림: %s." % (clid, " · ".join("%s %.1f" % x for x in cu) or "없음", " · ".join("%s %.1f" % x for x in cd) or "없음")}]
    if y3m:
        s2.append({"t": "미국 10년 − 3개월 금리차 %.2f%%p(3개월 금리 %s 값)." % (u10 - y3m[-1][1], md(y3m[-1][0]))})
    else:
        lacks.append("미국 3개월 금리")
    gd = [(c["name"], c["gdp"]["v"]) for c in C.values() if (c.get("gdp") or {}).get("v") is not None]
    if gd:
        s2.append({"t": "올해 성장률 전망(IMF): " + " · ".join("%s %.1f%%" % x for x in sorted(gd, key=lambda x: -x[1])[:4]) + " 순입니다."})
    if len(s2) < 2:
        raise Miss("경기 줄이 모자람")
    usup = any(n == "미국" for n, _ in cu)
    r2 = ("미국 경기선행이 오르는 쪽이라, 미국 경기가 버티는 흐름으로 읽힙니다." if usup else
          "경기선행이 오르는 곳이 많지 않아, 경기 쪽 받침은 약한 것으로 보입니다." if len(cu) < len(cd) else
          "경기선행이 오르는 곳과 내리는 곳이 섞여 있어, 방향은 아직 갈리지 않은 것으로 보입니다.")
    h2 = "2. 경기 — " + ("미국 오름" if usup else "오름보다 내림이 많음" if len(cu) < len(cd) else "섞임")

    # 3. 시장 반응
    eq = sorted([(c["name"], c["eq"]["m1"]) for c in C.values() if (c.get("eq") or {}).get("m1") is not None], key=lambda x: -x[1])
    eqd = next((c["eq"]["date"] for c in C.values() if c.get("eq")), "")
    s3 = []
    if len(eq) >= 4:
        s3.append({"t": "나라 주가 한 달(ETF · %s 까지):" % md(eqd), "sub": ["%s 가 강합니다." % " · ".join("%s %s" % (n, sg(v)) for n, v in eq[:2]),
                                                                   "%s 가 약합니다." % " · ".join("%s %s" % (n, sg(v)) for n, v in eq[-2:])]})
    try:
        dx = ind("dxy")
        gold = ind("gold")
        s3.append({"t": "달러인덱스 %.2f(한 달 %s) · 금 %s달러(한 달 %s)." % (dx[-1][1], sg(pct(dx[-1][1], ago(dx, 30))), comma(gold[-1][1], 1), sg(pct(gold[-1][1], ago(gold, 30))))})
    except Miss:
        lacks.append("달러인덱스 · 금")
    spx, nq, vx = IX.get("SPX"), IX.get("NASDAQ"), IX.get("VIX")
    if spx and nq:
        s3.append({"t": "미국 증시 %s: S&P 500 %s · 나스닥 %s%s." % (md(spx.get("asOf") or ""), sg(spx.get("changePct"), 2), sg(nq.get("changePct"), 2),
                                                              " · 공포 지수 VIX %.2f" % vx["value"] if vx else "")})
    if len(s3) < 2:
        raise Miss("시장 반응 줄이 모자람")
    kr_eq = dict(eq).get("한국")
    us_eq = dict(eq).get("미국")
    if kr_eq is not None and us_eq is not None and us_eq - kr_eq >= 5:
        r3 = "미국보다 한국 주가가 크게 약해, 한국에서 먼저 돈이 빠지는 것으로 읽힙니다."
    elif kr_eq is not None and us_eq is not None and kr_eq - us_eq >= 5:
        r3 = "한국 주가가 미국보다 강해, 돈이 한국 쪽으로 들어오는 것으로 읽힙니다."
    else:
        r3 = "나라 사이 주가 차이가 크지 않아, 돈이 한쪽으로 쏠리지는 않은 것으로 보입니다."
    h3 = "3. 시장 반응 — " + ("한국이 약함" if r3.startswith("미국보다") else "한국이 강함" if r3.startswith("한국 주가") else "고름")

    # 4. 한국
    kp, kq = kospi[-1], kosdaq[-1]
    k20 = pct(kp[1], kospi[-21][1])
    q20 = pct(kq[1], kosdaq[-21][1])
    k1 = pct(kp[1], kospi[-2][1])
    hi = max(kospi[-250:], key=lambda x: x[1])
    s4 = [{"t": "코스피 %s 마감 %s(%s) · 20거래일 **%s** — 1년 안 종가 고점 %s(%s)에서 %s." % (
              md(kp[0]), comma(kp[1]), sg(k1, 2), sg(k20), comma(hi[1]), md(hi[0]), sg(pct(kp[1], hi[1])))},
          {"t": "코스닥 %s 마감 %s(%s) · 20거래일 %s." % (md(kq[0]), comma(kq[1]), sg(pct(kq[1], kosdaq[-2][1]), 2), sg(q20))}]
    ki = IX.get("KOSPI")
    if ki and ki.get("up") is not None and NOW.weekday() < 5 and (NOW.hour, NOW.minute) >= (15, 40):   # 오른 · 내린 종목 수는 그날 장 값이라 마감 뒤 판에서만
        s4.append({"t": "코스피 오른 종목 %s 대 내린 종목 %s." % (ki["up"], ki["down"])})
    try:
        fx = ind("usdkrw")
        fm = pct(fx[-1][1], ago(fx, 30))
        s4.append({"t": "원/달러 %s원(한 달 %s%s)." % (comma(fx[-1][1], 1), sg(fm), "" if fm is None or abs(fm) < 0.5 else " · 원화 강세" if fm < 0 else " · 원화 약세")})
    except Miss:
        lacks.append("원/달러")
    if k20 is None:
        r4 = "코스피 20거래일 변화를 잴 값이 모자라 방향은 말하기 어려울 수 있습니다."
    elif k20 <= -5:
        r4 = "코스피가 한 달 사이 크게 빠져, 한국 주식에서 비중을 줄이는 흐름으로 읽힙니다."
    elif k20 >= 5:
        r4 = "코스피가 한 달 사이 크게 올라, 한국 주식으로 돈이 들어오는 흐름으로 읽힙니다."
    else:
        r4 = "코스피가 한 달 사이 큰 방향 없이 움직여, 뚜렷한 쏠림은 없는 것으로 보입니다."
    h4 = "4. 한국 — 코스피 20거래일 " + sg(k20)

    # 5. 원자재 · 운임
    s5 = []
    for key, nm, unit, n in (("wti", "유가(WTI)", "달러", 2), ("copper", "구리", "달러", 3)):
        try:
            r = ind(key)
            s5.append({"t": "**%s:** %s%s · 한 달 %s · 1년 %s." % (nm, comma(r[-1][1], n), unit, sg(pct(r[-1][1], ago(r, 30))), sg(pct(r[-1][1], r[0][1]), 0))})
            if key == "wti":
                wm = pct(r[-1][1], ago(r, 30))
            else:
                cm = pct(r[-1][1], ago(r, 30))
        except Miss:
            lacks.append(nm)
    sub = []
    for key, nm, days in (("bdi", "건화물 운임(BDI)", 30), ("scfi", "상하이 컨테이너 운임(한 주에 한 번)", 28)):
        try:
            r = ind(key)
            sub.append("%s %s · 한 달 %s" % (nm, comma(r[-1][1], 0), sg(pct(r[-1][1], ago(r, days)))))
        except Miss:
            lacks.append(nm)
    if sub:
        s5.append({"t": "**운임:**", "sub": sub})
    if len(s5) < 2:
        raise Miss("원자재 줄이 모자람")
    wm = locals().get("wm")
    cm = locals().get("cm")
    oil = "유가가 올라 물가 부담이 커지는 쪽" if (wm or 0) >= 5 else "유가가 내려 물가 부담은 조금 덜어지는 쪽" if (wm or 0) <= -5 else "유가는 제자리 걸음"
    cop = "구리가 올라 산업 수요는 버티는 것" if (cm or 0) >= 3 else "구리가 내려 산업 수요가 약해지는 것" if (cm or 0) <= -3 else "구리도 큰 변화가 없는 것"
    r5 = "%s이고, %s으로 읽힙니다." % (oil, cop)
    h5 = "5. 원자재 · 운임 — 유가 한 달 %s" % sg(wm)

    secs = [{"h": h1, "items": s1, "read": r1}, {"h": h2, "items": s2, "read": r2}, {"h": h3, "items": s3, "read": r3},
            {"h": h4, "items": s4, "read": r4}, {"h": h5, "items": s5, "read": r5}]

    # 6. 대외변수(있으면)
    g, ep, tp = R.get("gpr") or [], R.get("epu") or [], R.get("tpu") or []
    if g and ep and tp:
        gm = ago([(x[0], x[2]) for x in g if x[2] is not None], 30)
        s6 = [{"t": "지정학 위험(세계) 30일 평균 %.0f(100 = 1985~2019 평균 · 한 달 전 %s)." % (g[-1][2], "%.0f" % gm if gm is not None else "—")},
              {"t": "정책 불확실성(미국) 30일 평균 %.0f · 무역정책 불확실성 %.0f(100 = 평소)." % (ep[-1][2], tp[-1][2])}]
        vxr, ovr = R.get("vix") or [], R.get("ovx") or []
        if vxr and ovr:
            s6.append({"t": "공포 지수 VIX %.2f · 원유 OVX %.1f(%s 값)." % (vxr[-1][1], ovr[-1][1], md(vxr[-1][0]))})
        hi6 = g[-1][2] >= 150 or ep[-1][2] >= 200
        r6 = ("기사로 잰 대외 불안이 평소보다 꽤 높은 편이라, 위험을 피하는 매도가 나올 수 있는 자리로 보입니다." if hi6 else
              "기사로 잰 대외 불안이 아주 높지는 않아, 대외 요인보다 금리 · 실적 쪽이 더 크게 작용하는 것으로 보입니다.")
        secs.append({"h": "6. 대외변수 — " + ("불안 높음" if hi6 else "보통"), "items": s6, "read": r6})
    else:
        lacks.append("대외변수")

    # 앞으로 볼 것 — 서버 발표 일정 · 미국 연준 회의
    nxt = []
    try:
        rel = sorted([x for x in get("/api/macro/releases").get("releases") or [] if x.get("nextReleaseKst")], key=lambda x: x["nextReleaseKst"])
        for x in rel[:3]:
            nxt.append({"t": "%s %s 발표(한국 시각 %s)" % (md(x["nextReleaseKst"][:10]), x.get("name"), x["nextReleaseKst"][11:16])})
    except Miss:
        lacks.append("발표 일정")
    meet = (C.get("US") or {}).get("meet")
    if meet and meet.get("v"):
        nxt.append({"t": "미국 연준 회의(%s) %s" % (meet.get("name", "FOMC"), meet["v"])})
    if not nxt:
        raise Miss("앞으로 볼 것이 없음")

    one = "코스피는 20거래일 %s, 미국 S&P 500 은 %s 하루 %s — 미국 10년 금리는 한 달 %s 입니다(규칙 문장 · 숫자만)." % (
        sg(k20), md(spx.get("asOf")) if spx and spx.get("asOf") else "", sg(spx.get("changePct"), 2) if spx else "—", sg(u10m, 0, "bp"))
    limits = ["세션이 기사를 읽고 쓴 글이 아닙니다 — 받아 둔 값에 정해진 문장틀로 숫자만 넣었습니다. 「읽기」 줄은 숫자의 방향으로 고른 정해진 문장입니다.",
              "왜 움직였는지(원인)는 들어 있지 않습니다 — 크게 움직인 날의 원인은 아래 「크게 움직인 날」 칸에 세션이 적습니다.",
              "물가 · 경기선행은 달마다 나오는 값이라 %s 이 마지막입니다." % (clid or "—")]
    if lacks:
        limits.append("못 받아 뺀 칸: " + " · ".join(lacks) + ".")

    stamp = NOW.strftime("%Y-%m-%d %H:%M")
    return {
        "_읽는법": "자동 시황(규칙 문장) — company-setup/tools/write-market-note.py 가 평일 06:30 · 16:10 받기 끝에 쓴다(2026-10-26 재권님 (가) 「응」). "
                   "틀은 세션 글(data/market-note.json)과 같고 화면이 둘 중 새 것을 보인다. failedAt 이 있으면 그 시각에 못 만들어 옛 글이 남은 것이다.",
        "auto": True, "at": stamp, "writtenAt": stamp, "by": "자동(규칙 문장)",
        "basis": "코스피 %s 마감 · 미국 지수 %s · 미국 10년 %s · 값 파일 %s 받음 · 서버 %s" % (
            md(kp[0]), md(spx.get("asOf")) if spx and spx.get("asOf") else "—", md(us10[-1][0]), W.get("fetchedAt", "—"), PORT),
        "one": one, "sections": secs, "next": nxt, "limits": limits}


def fail(why, paths):
    print("못 만듦 —", why)
    for p in paths:
        try:
            N = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue   # 옛 글이 없으면 손 글(씨앗)이 그대로 보인다
        N["failedAt"], N["failedWhy"] = NOW.strftime("%Y-%m-%d %H:%M"), why
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(N, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
    return 1


if __name__ == "__main__":
    out, paths = targets(os.path.join(DATA, "market-note-live.json"))
    try:
        N = main()
    except Miss as ex:
        sys.exit(fail(str(ex), paths))
    except Exception as ex:   # 셈이 터져도 옛 글은 지킨다
        sys.exit(fail("셈 오류(%s)" % type(ex).__name__, paths))
    probe = paths[0] + ".check.json"
    with open(probe, "w", encoding="utf-8", newline="\n") as f:
        json.dump(N, f, ensure_ascii=False, indent=1)
    rc = subprocess.run([sys.executable, os.path.join(HERE, "check-market-note.py"), probe], capture_output=True, text=True)
    print(rc.stdout.strip())
    if rc.returncode != 0:
        os.remove(probe)
        sys.exit(fail("검사 걸림", paths))
    for p in paths:
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(N, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
    os.remove(probe)
    print("씀 —", ", ".join(map(os.path.normpath, paths)))
