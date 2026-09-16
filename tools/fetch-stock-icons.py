#!/usr/bin/env python3
"""종목 아이콘을 받아 uidata/icons/ 에 저장한다.

    python tools/fetch-stock-icons.py

**이미지는 저장소에 담지 않는다.** `.gitignore` 로 빠져 있고, 이 도구만 담는다.
기계를 옮기면 거기서 한 번 돌리면 된다 (2026-09-16 지시).

왜 담지 않나 — 세 가지다.

    저장소가 공개다        회사 로고가 공개 저장소에 올라간다
    기록에 영원히 쌓인다    git 은 PNG 를 델타 압축하지 못한다. 96px 로 담았다가
                           나중에 128px 로 바꾸면 96px 판본이 기록에 그대로 남는다
    서버가 곧 그 기계다     맥미니를 서버로 두기로 했으므로, 파일은 그 기계에만
                           있으면 된다. GitHub 을 거칠 이유가 없다

── 규격 ──

원본은 480×480 이고, 화면에서 쓰는 크기는 28~36px 이다
(frame.css · home.css · stock.css). 고해상도 화면의 2배(72px)를 덮도록
96px 로 줄인다. 전체 약 10.5MB 다.

**줄인 것이 원본보다 크면 원본을 쓴다.** ETF·우선주는 원본이 이미 1.8KB 라
다시 그리면 되레 커진다 (2026-09-16 실측).

── 적중률 (2026-09-16 무작위 표본 실측) ──

    보통주      98%     못 받는 것은 최근 상장 종목
    ETF        100%
    우선주      62%     남양유업우 · LG우 · 하이트진로2우B 등

못 받은 것은 index.json 에 이유와 함께 남긴다. 조용히 빠지면 왜 없는지
알 수 없다 (holdings/CLAUDE.md 「데이터 규칙」).
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

try:
    from PIL import Image
except ImportError:
    print("Pillow 가 필요합니다.  pip install Pillow")
    sys.exit(1)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "uidata", "icons")
INDEX_PATH = os.path.join(OUT_DIR, "index.json")

# 전종목 목록. dart.py 가 이미 쓰는 곳이라 출처를 새로 늘리지 않는다.
NAVER_LIST = "https://m.stock.naver.com/api/stocks/marketValue/%s?page=%d&pageSize=100"
MARKETS = ["KOSPI", "KOSDAQ"]

# 아이콘. 원본 480×480 PNG.
TOSS_ICON = "https://static.toss.im/png-icons/securities/icn-sec-fill-%s.png"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# 화면에서 쓰는 가장 큰 자리가 36px 이다. 고해상도 2배를 덮는다.
ICON_SIZE = 96

# 토스에 한꺼번에 몰리지 않게. 3,900건을 8줄로 나눠 받으면 3~4분쯤 걸린다.
WORKERS = 8

# 목록 페이지를 넘길 때 쉬는 시간
LIST_PAUSE = 0.1

# ETF 는 이름으로 가린다. 종목코드만으로는 구분할 수 없다.
ETF_WORDS = ("KODEX", "TIGER", "ACE", "PLUS", "RISE", "SOL ", "HANARO", "KOSEF",
             "ARIRANG", "TIMEFOLIO", "KIWOOM", "히어로즈", "마이티", "파워",
             "레버리지", "인버스", "선물(H)")


def kind(code, name):
    """보통주 · 우선주·기타 · ETF 중 무엇인가.

    우선주는 종목코드 끝자리가 0 이 아니다 (005935 삼성전자우).
    """
    if any(w in name for w in ETF_WORDS):
        return "ETF"
    return "우선주·기타" if code[-1] != "0" else "보통주"


def fetch_all_stocks():
    """코스피·코스닥 전종목을 받는다. 중복은 뺀다."""
    rows, seen = [], set()
    for market in MARKETS:
        page = 1
        while page <= 60:
            req = urllib.request.Request(NAVER_LIST % (market, page), headers={
                "User-Agent": UA, "Referer": "https://m.stock.naver.com/"})
            with urllib.request.urlopen(req, timeout=20) as r:
                body = json.loads(r.read().decode("utf-8"))
            items = body.get("stocks") or []
            if not items:
                break
            for it in items:
                code = (it.get("itemCode") or "").strip()
                if len(code) != 6 or not code.isdigit() or code in seen:
                    continue
                seen.add(code)
                rows.append({"code": code,
                             "name": (it.get("stockName") or "").strip(),
                             "market": market})
            page += 1
            time.sleep(LIST_PAUSE)
    return rows


def shrink(raw, size):
    """96px 로 줄인다. 줄인 것이 더 크면 원본을 그대로 돌려준다.

    ETF·우선주 아이콘은 원본이 이미 작아서, 다시 그리면 PNG 헤더가 붙는
    만큼 커진다. 그럴 때는 손대지 않는 편이 낫다.
    """
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    if im.size[0] <= size and im.size[1] <= size:
        return raw, im.size
    buf = io.BytesIO()
    im.resize((size, size), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return (buf.getvalue(), (size, size)) if buf.tell() < len(raw) else (raw, im.size)


def grab_one(row, size, force):
    """한 종목. 이미 있으면 건너뛴다."""
    code = row["code"]
    path = os.path.join(OUT_DIR, code + ".png")
    if not force and os.path.exists(path):
        return dict(row, state="있음", bytes=os.path.getsize(path))

    try:
        req = urllib.request.Request(TOSS_ICON % code, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        why = "아이콘이 없습니다 (%s)" % e.code
        return dict(row, state="없음", why=why)
    except Exception as e:
        return dict(row, state="실패", why=str(e)[:80])

    try:
        data, dim = shrink(raw, size)
    except Exception as e:
        return dict(row, state="실패", why="그림을 못 읽었습니다: %s" % str(e)[:60])

    with open(path, "wb") as f:
        f.write(data)
    return dict(row, state="받음", bytes=len(data), dim="%dx%d" % dim)


def main():
    ap = argparse.ArgumentParser(description="종목 아이콘 받기")
    ap.add_argument("--force", action="store_true", help="이미 있어도 다시 받는다")
    ap.add_argument("--no-etf", action="store_true", help="ETF 는 건너뛴다")
    ap.add_argument("--size", type=int, default=ICON_SIZE, help="한 변 픽셀 (기본 %d)" % ICON_SIZE)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    print("전종목 목록을 받는 중입니다…")
    stocks = fetch_all_stocks()
    for s in stocks:
        s["kind"] = kind(s["code"], s["name"])
    counts = {}
    for s in stocks:
        counts[s["kind"]] = counts.get(s["kind"], 0) + 1
    print("  전종목 %d개  (%s)"
          % (len(stocks), " · ".join("%s %d" % (k, v) for k, v in counts.items())))

    todo = [s for s in stocks if not (args.no_etf and s["kind"] == "ETF")]
    if args.no_etf:
        print("  ETF 를 뺐습니다 → %d개를 받습니다" % len(todo))

    print("아이콘을 받는 중입니다… (%d줄로 나눠 받습니다)" % WORKERS)
    done = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, got in enumerate(ex.map(lambda s: grab_one(s, args.size, args.force), todo), 1):
            done.append(got)
            if i % 200 == 0 or i == len(todo):
                print("  %d / %d" % (i, len(todo)))

    got = [d for d in done if d["state"] in ("받음", "있음")]
    miss = [d for d in done if d["state"] not in ("받음", "있음")]
    total = sum(d.get("bytes", 0) for d in got)

    # 화면이 이 파일을 읽어 「어느 종목에 그림이 있나」를 안다. 그래서 가볍게 둔다.
    # 종목명은 js/data/market.js 에 이미 있으므로 여기 또 적지 않는다
    # (CLAUDE.md 「같은 값은 한 곳에만 둔다」). 이름까지 담았더니 343KB 였고,
    # 코드만 담으니 34KB 다.
    index = {
        "설명": "어느 종목에 아이콘이 있는지. 화면이 이것을 읽어 그림을 넣을지 정한다.",
        "만든것": "tools/fetch-stock-icons.py",
        "갱신일": datetime.now(KST).isoformat(timespec="seconds"),
        "규격": args.size,
        "출처": {"목록": "네이버 시가총액", "아이콘": "토스 종목 아이콘"},
        "종목수": len(stocks),
        "받은수": len(got),
        "용량바이트": total,
        "icons": sorted(d["code"] for d in got),
        "없음": [{"code": d["code"], "name": d["name"], "why": d.get("why", "")} for d in miss],
    }
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print()
    print("  받음   %d개   %.1f MB" % (len(got), total / 1024 / 1024))
    print("  없음   %d개" % len(miss))
    by_kind = {}
    for d in miss:
        by_kind[d["kind"]] = by_kind.get(d["kind"], 0) + 1
    for k, v in sorted(by_kind.items()):
        print("           %-10s %d개" % (k, v))
    print()
    print("  저장한 곳  %s" % OUT_DIR)
    print("  목록       %s" % INDEX_PATH)
    print()
    print("  이 폴더의 PNG 는 저장소에 담기지 않습니다. 기계를 옮기면 다시 돌리세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
