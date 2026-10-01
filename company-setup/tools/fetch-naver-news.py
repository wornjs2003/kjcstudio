"""네이버 증권 뉴스(stock.naver.com/news)에 있는 것을 받아 Insight 화면용 파일로 둔다.

    python3 company-setup/tools/fetch-naver-news.py

2026-10-01 지시 — 「네이버에 있는거 가져와서 그냥 채워만 놓으면 됨」.
네이버 API 는 다른 사이트에서의 직접 호출을 막는다(Access-Control-Allow-Origin 없음).
그래서 화면이 바로 못 부르고, 이 도구가 받아 data/naver-news.json 에 둔다.
**돌린 그 시각의 값이다** — 화면에 받은 시각을 함께 적는다.
"""
import json, os, sys, urllib.request
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://stock.naver.com"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "naver-news.json")
N = 15

# 네이버 화면의 칸 → 그 칸이 부르는 주소 (2026-10-01 stock.naver.com/news 스크립트에서 찾음)
FEEDS = {
    "flash":  "/api/domestic/news/list?category=flashnews&page=1&pageSize=%d",   # 실시간 속보
    "rank":   "/api/domestic/news/list?category=ranknews&page=1&pageSize=%d",    # 많이 본 뉴스
    "main":   "/api/domestic/news/list?category=mainnews&page=1&pageSize=%d",    # 주요 뉴스
    "world":  "/api/foreign/news/worldNews?page=1&pageSize=%d",                  # 해외 뉴스
    "notice": "/api/domestic/news/noticeList?page=1&pageSize=%d",                # 공시
}


def get(path):
    req = urllib.request.Request(BASE + path % N, headers={
        "User-Agent": "Mozilla/5.0", "Referer": BASE + "/news"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def domestic(d):
    return [{
        "title": a.get("title"), "source": a.get("officeHname"), "at": a.get("datetime"),
        "rank": a.get("ranking"), "thumb": a.get("thumbUrl"),
        "link": "https://n.news.naver.com/mnews/article/%s/%s" % (a.get("officeId"), a.get("articleId")),
    } for a in d.get("articles", [])]


def world(d):
    # 해외 기사의 네이버 주소 모양은 확인하지 못해 링크를 두지 않는다
    return [{"title": a.get("tit"), "source": a.get("ohnm"),
             "at": "%s-%s-%s %s:%s" % (a["dt"][:4], a["dt"][4:6], a["dt"][6:8], a["dt"][8:10], a["dt"][10:12])}
            for a in (d if isinstance(d, list) else [])]


def notice(d):
    return [{"title": a.get("title"), "source": a.get("itemName") or a.get("noticeTypeName"),
             "kind": a.get("comment"), "at": (a.get("datetime") or "").replace("T", " ")[:16]}
            for a in d.get("content", [])]


def main():
    out = {"fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M"), "from": BASE + "/news"}
    fails = []
    for key, path in FEEDS.items():
        try:
            d = get(path)
            out[key] = world(d) if key == "world" else notice(d) if key == "notice" else domestic(d)
        except Exception as e:
            out[key] = None
            fails.append("%s(%s)" % (key, type(e).__name__))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("받음 %s — %s" % (out["fetchedAt"], ", ".join("%s %d건" % (k, len(out[k])) for k in FEEDS if out[k] is not None)))
    if fails:
        print("못 받음:", ", ".join(fails))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
