"""네이버 증권 뉴스(stock.naver.com/news)에 있는 것을 받아 Insight 화면용 파일로 둔다.

    python3 company-setup/tools/fetch-naver-news.py              → data/naver-news.json (손으로 한 번)
    python3 company-setup/tools/fetch-naver-news.py --to-board   → 8765 문서 저장소 naver-news (10분 주기 · launchd)

2026-10-01 지시 — 「네이버에 있는거 가져와서 그냥 채워만 놓으면 됨」.
네이버 API 는 다른 사이트에서의 직접 호출을 막는다(Access-Control-Allow-Origin 없음).
그래서 화면이 바로 못 부르고, 이 도구가 받아 data/naver-news.json 에 둔다.
**돌린 그 시각의 값이다** — 화면에 받은 시각을 함께 적는다.

2026-10-06 지시(「응 해봐」) — 10분마다 받는다. 주기로 도는 쪽은 저장소 파일 대신 **8765 의 문서 저장소**
(`PUT /api/board/doc/naver-news` · 본문 `{"data": …}` · `holdings/server/docstore.py`)에 둔다 — 파일에 쓰면
10분마다 메인 폴더가 미커밋으로 더러워진다. 화면(js/insight.js)은 그 문서를 먼저 읽고 없으면 파일로 돌아간다.
주소는 `KJC_BOARD_URL`(기본 8765) 하나 — `tools/board-card.py` 와 같은 변수다. **세션 폴더 서버(8766~8771)에
쓰지 않는다** — 보드 넘기기가 켜진 서버는 그대로 8765 로 넘긴다(메인 데이터 · 「메인 자리는 허락 없이 건드리지 않는다」).
"""
import argparse, json, os, sys, time, urllib.error, urllib.request
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://stock.naver.com"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "naver-news.json")
N = 15
BOARD_URL = (os.environ.get("KJC_BOARD_URL") or "http://localhost:8765").rstrip("/")
DOC = "naver-news"
# 요청 사이 쉼 — 재권님 「서버에 무리가지 않도록 순차로 받도록 하면 될 거 같아」(2026-10-06 16:1x · 창구 경유).
# 다섯 주소를 한 번에 하나씩(순차) 받고, 그 사이에 이만큼 쉰다. 10분 주기라 한 바퀴가 몇 초 늘어도 지장 없다
GAP_SEC = 1.0

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


def put_board(out):
    """문서 저장소에 쓴다. 성공하면 None, 실패하면 이유(예외 이름 · 상태코드) — 키가 섞일 길이 없는 값만 돌려준다."""
    body = json.dumps({"data": out}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BOARD_URL + "/api/board/doc/" + DOC, data=body, method="PUT",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode("utf-8"))
        return None if res.get("ok") else "ok 아님"
    except urllib.error.HTTPError as e:
        return "HTTP %d" % e.code
    except Exception as e:
        return type(e).__name__


def main():
    ap = argparse.ArgumentParser(description="네이버 증권 뉴스를 받아 파일 또는 8765 문서 저장소에 둔다")
    ap.add_argument("--to-board", action="store_true",
                    help="data/naver-news.json 대신 %s/api/board/doc/%s 에 PUT (10분 주기용)" % (BOARD_URL, DOC))
    args = ap.parse_args()

    out = {"fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M"), "from": BASE + "/news"}
    fails = []
    for i, (key, path) in enumerate(FEEDS.items()):
        if i:
            time.sleep(GAP_SEC)   # 순차 · 쉬어 가며 — 위 GAP_SEC
        try:
            d = get(path)
            out[key] = world(d) if key == "world" else notice(d) if key == "notice" else domestic(d)
        except Exception as e:
            out[key] = None
            fails.append("%s(%s)" % (key, type(e).__name__))
    if args.to_board:
        # 전부 못 받았으면 쓰지 않는다 — 빈 값으로 멀쩡한 저장본을 덮지 않는다(docstore 도 빈 값을 거부한다)
        if all(out[k] is None for k in FEEDS):
            print("못 받음(전부):", ", ".join(fails), "— 저장 안 함")
            return 1
        err = put_board(out)
        where = "%s 문서 %s" % (BOARD_URL, DOC)
    else:
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        err = None
        where = os.path.relpath(OUT)
    print("받음 %s — %s → %s" % (out["fetchedAt"],
          ", ".join("%s %d건" % (k, len(out[k])) for k in FEEDS if out[k] is not None), where))
    if err:
        print("저장 못 함:", err)
        return 1
    if fails:
        print("못 받음:", ", ".join(fails))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
