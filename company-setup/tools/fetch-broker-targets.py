#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""종목 리포트를 쓴 종목마다 「증권사별 목표가」 를 KIS 종목투자의견에서 받아 data/stock-report/brokers.json 에 둔다.

    python3 company-setup/tools/fetch-broker-targets.py [--only 005930,000660] [--months 6] [--port 8765]

2026-10-07 재권님 — 「실적 증권사 추정 … 증권사별로 얼마나 다른지 확인」 → 「증권사별로 책정된 값을 넣어주면 좋을거같은데」
→ 「너무 많은데 최고와 최저 평균으로 표기되면 될거같아」 → 「응 해줘」.
네이버(FnGuide)는 목표가 평균 하나만 준다. KIS 종목투자의견(invest-opinion · FHKST663300C0)은 증권사마다 낸 날 · 의견 ·
목표가를 준다 — 이 도구는 그것을 받아 **증권사마다 가장 최근 값 하나**만 남긴다. 화면(js/stock-report.js)이 최고 · 평균 · 최저를 센다.

KIS 는 우리 서버(기본 8765)의 중계(/api/kis/relay)로 부른다 — KIS 를 한 곳에서 세는 서버의 초당 한도를 그대로 탄다.
종목은 data/stock-report/index.json 에 적힌 것(리포트를 쓴 종목)만. 실적 추정은 증권사별로 못 받는다(그 TR 은 한국투자 한 곳 값).
값을 지어내지 않는다 — 못 받은 종목은 `items` 에 없고 `errors` 에 이유가 남는다.
"""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "stock-report")
INDEX = os.path.join(DATA, "index.json")
OUT = os.path.join(DATA, "brokers.json")
PATH = "/uapi/domestic-stock/v1/quotations/invest-opinion"
TR = "FHKST663300C0"


def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default


def relay(port, params):
    url = f"http://localhost:{port}/api/kis/relay?" + urllib.parse.urlencode(
        {"path": PATH, "tr_id": TR, "params": json.dumps(params)})
    with urllib.request.urlopen(url, timeout=20) as r:
        body = json.loads(r.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError("서버가 ok 를 안 줬다")
    return (body.get("data") or {}).get("output") or []


def latest_per_broker(rows):
    """KIS 는 최근 것이 앞에 온다 — 증권사마다 처음 만난 것(가장 최근)만, 목표가가 0 · 빈 것은 뺀다."""
    out, seen = [], set()
    for r in sorted(rows, key=lambda x: x.get("stck_bsop_date", ""), reverse=True):
        b = (r.get("mbcr_name") or "").strip()
        try:
            t = int(float(r.get("hts_goal_prc") or 0))
        except ValueError:
            t = 0
        if not b or b in seen or t <= 0:
            continue
        seen.add(b)
        out.append({"broker": b, "date": r.get("stck_bsop_date"), "opinion": (r.get("invt_opnn") or "").strip(), "target": t})
    return out


def main():
    port = arg("--port", "8765")
    months = int(arg("--months", "6"))
    only = [c for c in (arg("--only", "") or "").split(",") if c]
    codes = only or [it["code"] for it in json.load(open(INDEX, encoding="utf-8")).get("items", [])]
    today = datetime.now()
    since = today - timedelta(days=round(months * 30.5))
    d1, d2 = since.strftime("%Y%m%d"), today.strftime("%Y%m%d")
    prev = {}
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT, encoding="utf-8")).get("items", {})
        except ValueError:
            prev = {}
    items, errors = dict(prev), {}
    for i, code in enumerate(codes):
        if i:
            time.sleep(0.3)
        try:
            rows = relay(port, {"FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "16633", "FID_INPUT_ISCD": code,
                                "FID_INPUT_DATE_1": d1, "FID_INPUT_DATE_2": d2})
            items[code] = {"fetchedAt": today.strftime("%Y-%m-%d %H:%M"), "from": d1, "to": d2, "brokers": latest_per_broker(rows)}
            print(f"  {code}  증권사 {len(items[code]['brokers'])}곳")
        except (urllib.error.URLError, RuntimeError, ValueError, OSError) as e:
            # 오류 글은 밖(파일 · 화면)으로 나가므로 종류만 적는다 — 「예외·오류 문구가 밖으로 나가면 scrub 를 거친다」
            errors[code] = type(e).__name__ + (f" {e.code}" if isinstance(e, urllib.error.HTTPError) else "")
            print(f"  {code}  못 받음 — {errors[code]}")
    out = {
        "note": "증권사별 목표가 — KIS 종목투자의견(invest-opinion · FHKST663300C0) · 증권사마다 가장 최근 값 하나 · "
                "tools/fetch-broker-targets.py 가 만든다(손으로 고치지 않는다) · 화면은 js/stock-report.js 「기본 지표」",
        "items": items, "errors": errors,
    }
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, OUT)
    print(f"저장: {os.path.relpath(OUT)} · 종목 {len(items)} · 못 받음 {len(errors)}")
    return 1 if errors and not any(c in items for c in codes) else 0


if __name__ == "__main__":
    sys.exit(main())
