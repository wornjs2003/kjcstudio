#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""국내 ETF 시가총액을 하루 한 번 쌓고, 설정 · 환매(돈이 들어오고 나간 양)를 어림한다.

2026-10-08 재권님 — 「ETF별 자금 유출입 … 매일 쌓아 두면 어림할 수 있습니다 — 이건 그렇게 해주」.
KIS · 토스 · 네이버 어디에도 ETF 설정 · 환매 항목이 없다(2026-10-08 실측). 그래서 지금 값을 매일 받아 둔다.

받는 곳 — 네이버 ETF 목록(비공식 · 예고 없이 바뀔 수 있다)

    GET https://finance.naver.com/api/sise/etfItemList.nhn?etfType=0     cp949 · 국내 ETF 전부(1,172개 · 2026-10-08)
    itemcode · itemname · nowVal(현재가) · nav(좌당 순자산) · marketSum(시가총액 · 억원)

어림하는 법 — 시가총액 = 상장 좌수 × 가격 이라, 가격이 움직인 몫을 빼면 좌수가 늘고 준 몫만 남는다.

    유입(억원) ≈ 시가총액(오늘) − 시가총액(앞 거래일) × 가격(오늘) / 가격(앞 거래일)

    = 늘어난 좌수 × 오늘 가격. 플러스면 설정(돈이 들어옴) · 마이너스면 환매(돈이 나감).
    **어림이다** — 분배금 · 액면 분할이 있던 날은 틀린다. 억원 단위로 반올림된 값이라 작은 ETF 는 흔들린다.

**장 마감 뒤에 돌린다.** 장중 값은 그날의 값이 아니라서 저장하지 않는다(15:40 전이면 멈춘다 · --force 로만).
**지난 값은 받을 곳이 없다** — 쌓기 시작한 날부터 어림이 나온다. 첫날은 쌓기만 한다.

    python3 company-setup/tools/fetch-etf-nav.py            오늘 마감 값을 쌓고 어림을 다시 낸다
    python3 company-setup/tools/fetch-etf-nav.py --force    장중이어도 쌓는다(시험용 · 그날 값이 아님)

저장 — company-setup/data/etf-nav.json   {"names": {코드: 이름}, "days": {YYYYMMDD: {코드: [시가총액, 가격]}}}
       company-setup/data/etf-flow.json  마지막 두 거래일로 어림한 유입 · 유출 (화면이 읽는 쪽)
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = "https://finance.naver.com/api/sise/etfItemList.nhn?etfType=0"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
NAV_PATH = os.path.join(DATA, "etf-nav.json")
FLOW_PATH = os.path.join(DATA, "etf-flow.json")
KST = timezone(timedelta(hours=9))
CLOSE_AFTER = (15, 40)        # 이 시각 전이면 장중 값이라 쌓지 않는다
TOP = 30                      # 유입 · 유출 상위 몇 개를 내나


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"})
    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read()
    rows = json.loads(raw.decode("cp949", errors="replace"))["result"]["etfItemList"]
    out, names = {}, {}
    for x in rows:
        code, cap, price = x.get("itemcode"), x.get("marketSum"), x.get("nowVal")
        if not code or not cap or not price:
            continue
        out[code] = [cap, price]
        names[code] = x.get("itemname") or code
    return out, names


def load(path, empty):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return empty


def save(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def estimate(store):
    days = sorted(store["days"])
    if len(days) < 2:
        return {"ok": False, "why": "쌓인 날이 %d일이라 아직 어림할 수 없습니다(두 거래일부터)" % len(days),
                "days": days}
    prev, cur = days[-2], days[-1]
    a, b = store["days"][prev], store["days"][cur]
    flows = []
    for code, (cap, price) in b.items():
        if code not in a:
            continue                      # 새로 상장한 것은 앞날 값이 없다
        cap0, price0 = a[code]
        if not price0:
            continue
        flows.append((round(cap - cap0 * price / price0), code))
    flows.sort()
    names = store["names"]
    pick = lambda rows: [{"code": c, "name": names.get(c, c), "flow": v} for v, c in rows]
    return {
        "ok": True, "from": prev, "to": cur, "unit": "억원", "count": len(flows),
        "inflowTotal": sum(v for v, _ in flows if v > 0),
        "outflowTotal": sum(v for v, _ in flows if v < 0),
        "topIn": pick(reversed(flows[-TOP:])), "topOut": pick(flows[:TOP]),
        "note": "어림 — 시가총액 변화에서 가격 변화 몫을 뺀 값(늘어난 좌수 × 가격) · 분배금 · 분할이 있던 날은 틀린다",
    }


def main():
    force = "--force" in sys.argv
    now = datetime.now(KST)
    if not force and (now.weekday() >= 5 or (now.hour, now.minute) < CLOSE_AFTER):
        print("장 마감(15:40) 뒤 평일에만 쌓습니다 — 지금 %s. 시험이면 --force." % now.strftime("%m-%d %H:%M"))
        return 2
    try:
        today, names = fetch()
    except Exception as e:                 # 받지 못했으면 「0개」 가 아니라 「못 받았다」 로 낸다
        print("네이버 ETF 목록을 못 받았습니다: %s" % type(e).__name__)
        return 2
    if not today:
        print("네이버 ETF 목록이 비어 왔습니다 — 저장하지 않습니다")
        return 2
    store = load(NAV_PATH, {"names": {}, "days": {}})
    ymd = now.strftime("%Y%m%d")
    store["names"].update(names)
    store["days"][ymd] = today
    save(NAV_PATH, store)
    est = estimate(store)
    est["fetchedAt"] = now.isoformat(timespec="seconds")
    est["source"] = "네이버 ETF 목록(비공식) · finance.naver.com/api/sise/etfItemList.nhn"
    save(FLOW_PATH, est)
    print("%s ETF %d개 쌓음 · 쌓인 날 %d일" % (ymd, len(today), len(store["days"])))
    if est["ok"]:
        print("어림 %s → %s · 유입 %+d억 · 유출 %+d억" % (est["from"], est["to"], est["inflowTotal"], est["outflowTotal"]))
    else:
        print(est["why"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
