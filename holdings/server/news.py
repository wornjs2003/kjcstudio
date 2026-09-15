"""뉴스 모으기.

두 갈래를 따로 받아 따로 보여준다. 성격이 달라 섞으면 둘 다 안 읽힌다
(2026-09-15 지시).

    시장 이슈    경제지 RSS · 제목에서 주제어를 찾아 묶는다
                 반도체·유가·금리처럼 주가에 영향을 주는 것. 원문 링크가 있다
    종목 움직임  KIS news-title · 시장구분 01(코스피) 02(코스닥)
                 지금 움직이는 종목. 링크는 없지만 종목코드가 정확히 붙어 온다

왜 나눴나 — KIS 를 01·02 로 좁히면 종목코드는 붙지만 내용이 "우리넷 소폭
상승세 +4.05%" 같은 자동 생성 시세 기사다. 주가에 영향을 주는 뉴스가 아니라
주가가 움직인 결과다. 반대로 거시 뉴스는 종목코드가 안 붙는다. 한쪽 방식으로는
둘 다 못 얻는다. 제목 검색(FID_TITL_CNTT)도 넣어 봤지만 걸러지지 않았다.

── 왜 구글 뉴스가 아닌가 ──

구글 뉴스 RSS 는 검색이라 주제별로 12건씩 받기 좋았다. 그런데 배포본
(Cloudflare Worker)에서 503 이 난다. 워커에서 헤더를 네 가지로 바꿔 시험했고
전부 막혔다. 본문이 구글의 "Sorry..." 차단 페이지였다 (2026-09-15 실측).
로컬에서는 통과한다 — IP 로 막는 것으로 보인다.

로컬과 배포본이 다르게 도는 것이 가장 나쁘므로, 양쪽 다 경제지 RSS 로 간다.
KIS 뉴스도 재봤지만 주제어에 걸리는 것이 6% 였고 그나마 절반이 자동 시세
기사였다. 경제지 RSS 는 20% 가 걸린다.

**이 방식의 약점** — 검색이 아니라 최신순 목록이라, 그날 기사가 없는 주제는
0건이 된다. 구글은 그럴 일이 없었다. 부족하면 출처를 늘린다.

주제어와 받아올 곳은 data/news-topics.json 에 있다. 코드는 안 고쳐도 된다.
"""

import html
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
TOPICS_PATH = os.path.join(os.path.dirname(HERE), "data", "news-topics.json")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KJC-Holdings/1.0"

# 한 출처에서 몇 건까지 볼 것인가. 주제어에 걸리는 것만 남으므로 넉넉히 둔다.
PER_FEED = 150

# 화면에 몇 건까지 보낼 것인가. 그보다 많아도 아래는 안 읽힌다.
MAX_ROWS = 80

# 출처 수만큼만 부른다. 뉴스는 초 단위로 바뀌지 않는다.
NEWS_TTL = 180

# KIS 종목 움직임. 이쪽은 장중에 빨리 바뀌므로 짧게 둔다.
MOVES_TTL = 60

_cache = {}
_lock = threading.Lock()


def _cached(key, ttl, make):
    """ttl 초 안에 받아둔 것이 있으면 그것을 준다."""
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and (now - hit[0]) < ttl:
            return hit[1]
    value = make()
    with _lock:
        _cache[key] = (now, value)
    return value


# ---------------------------------------------------------------- 설정

def load_topics():
    """주제어와 받아올 곳을 읽는다. 없거나 깨졌으면 빈 목록으로 돌려준다.

    화면이 이 목록으로 필터 칩을 만들므로, 수집과 화면이 늘 같은 것을 본다.
    """
    try:
        with open(TOPICS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {"topics": [], "drop": [], "feeds": []}

    topics = [t for t in (raw.get("topics") or []) if t.get("on", True)]
    drop = ((raw.get("버릴제목") or {}).get("말")) or []
    feeds = raw.get("feeds") or []
    return {"topics": topics, "drop": drop, "feeds": feeds}


def _dropped(title, drop):
    """자동 생성 시세 기사인가."""
    return any(w and w in title for w in drop)


def pick_topic(title, topics):
    """제목에 주제어가 들어 있으면 그 주제를 돌려준다. 없으면 None.

    앞에 적힌 주제부터 본다. 한 제목이 여러 주제에 걸리면 먼저 적힌 것이
    이긴다 — 순서를 바꾸려면 news-topics.json 에서 묶음 순서를 옮긴다.
    """
    for t in topics:
        for kw in (t.get("keywords") or []):
            if kw and kw in title:
                return t
    return None


# ---------------------------------------------------------------- 시장 이슈

def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        enc = r.headers.get_content_charset() or "utf-8"
        return body.decode(enc, "replace")


_ITEM = re.compile(r"<item>(.*?)</item>", re.S)
_TAG = {
    "title": re.compile(r"<title>(.*?)</title>", re.S),
    "link": re.compile(r"<link>(.*?)</link>", re.S),
    "date": re.compile(r"<pubDate>(.*?)</pubDate>", re.S),
}


def _unescape(s):
    """CDATA 를 벗기고 HTML 문자표기를 푼다.

    손으로 치환하다 &#039; 를 빠뜨려 제목에 그대로 남았다 (2026-09-15).
    숫자로 쓴 것까지 다루려면 html.unescape 를 쓰는 편이 낫다.

    일부 언론사는 두 번 감싸 &amp;#039; 로 보낸다. 바뀌지 않을 때까지
    되풀이하되, 끝없이 돌지 않도록 세 번에서 멈춘다.
    """
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s or "", flags=re.S)
    for _ in range(3):
        once = html.unescape(s)
        if once == s:
            break
        s = once
    return re.sub(r"<[^>]+>", "", s).strip()


def _kst(pubdate):
    """RSS 의 시각을 한국 시각 문자열로. 못 읽으면 원문을 그대로 둔다."""
    try:
        return parsedate_to_datetime(pubdate).astimezone(KST).isoformat(timespec="seconds")
    except Exception:
        return pubdate


def fetch_feed(feed, topics, drop):
    """한 출처를 받아 주제어에 걸리는 것만 돌려준다.

    주제가 없는 기사는 버린다. 경제지라도 절반 넘게는 주가와 상관없는
    일반 기사다 (2026-09-15 실측: 100건 중 20건만 걸렸다).
    """
    out = []
    for block in _ITEM.findall(_get(feed["url"]))[:PER_FEED]:
        def pick(name):
            m = _TAG[name].search(block)
            return _unescape(m.group(1)) if m else ""

        title = pick("title")
        if not title or _dropped(title, drop):
            continue
        topic = pick_topic(title, topics)
        if not topic:
            continue

        out.append({
            "title": title,
            "link": pick("link"),
            "at": _kst(pick("date")),
            "source": feed.get("label") or feed.get("id") or "",
            "topic": topic.get("id"),
            "topicLabel": topic.get("label"),
        })
    return out


def fetch_issues():
    """켜져 있는 출처를 모두 받아 시각 역순으로 합친다.

    한 곳이 실패해도 나머지는 보여준다. 전부 실패해야 오류로 친다.
    """
    def make():
        conf = load_topics()
        rows, errors = [], {}
        seen = set()
        for f in conf["feeds"]:
            try:
                for row in fetch_feed(f, conf["topics"], conf["drop"]):
                    # 같은 기사가 여러 곳에 실린다. 제목으로 한 번만 담는다.
                    if row["title"] in seen:
                        continue
                    seen.add(row["title"])
                    rows.append(row)
            except Exception as e:
                errors[f.get("id") or "?"] = safe_message(e, 90)
        rows.sort(key=lambda r: r.get("at") or "", reverse=True)
        return {"rows": rows[:MAX_ROWS], "errors": errors or None,
                "topics": [{"id": t["id"], "label": t["label"],
                            "color": t.get("color")} for t in conf["topics"]]}

    return _cached("issues", NEWS_TTL, make)


# ---------------------------------------------------------------- 종목 움직임

# KIS 뉴스 시장구분. 01 코스피 · 02 코스닥.
# 빈 값으로 부르면 정치·사건사고가 대부분이라 쓰지 않는다 (2026-09-15 확인).
MOVE_MARKETS = ["01", "02"]

NEWS_PATH = "/uapi/domestic-stock/v1/quotations/news-title"
NEWS_TR = "FHKST01011800"


def fetch_moves(kis_get, cfg):
    """KIS 에서 종목이 붙은 뉴스를 받는다.

    kis_get 을 넘겨받는 이유 — 토큰·호출 간격을 kis_proxy 가 들고 있어서다.
    여기서 따로 부르면 초당 한도를 둘이서 각각 세게 된다.
    """
    def make():
        rows, errors = [], {}
        seen = set()
        for mk in MOVE_MARKETS:
            try:
                data = kis_get(cfg, NEWS_PATH, {
                    "FID_NEWS_OFER_ENTP_CODE": "", "FID_COND_MRKT_CLS_CODE": mk,
                    "FID_INPUT_ISCD": "", "FID_TITL_CNTT": "",
                    "FID_INPUT_DATE_1": "", "FID_INPUT_HOUR_1": "",
                    "FID_RANK_SORT_CLS_CODE": "", "FID_INPUT_SRNO": "",
                }, NEWS_TR)
            except Exception as e:
                errors[mk] = safe_message(e, 90)
                continue

            for r in (data.get("output") or []):
                srno = (r.get("cntt_usiq_srno") or "").strip()
                if not srno or srno in seen:
                    continue
                title = (r.get("hts_pbnt_titl_cntt") or "").strip()
                if not title:
                    continue

                # 관련 종목은 최대 10개까지 코드와 이름이 따로 온다
                stocks = []
                for i in range(1, 11):
                    c = (r.get("iscd%d" % i) or "").strip()
                    if not c:
                        continue
                    stocks.append({"code": c, "name": (r.get("kor_isnm%d" % i) or "").strip()})
                if not stocks:
                    continue          # 종목이 안 붙었으면 이 갈래의 몫이 아니다

                seen.add(srno)
                d = (r.get("data_dt") or "").strip()
                t = (r.get("data_tm") or "").strip()
                rows.append({
                    "id": srno,
                    "title": title,
                    "at": _stamp(d, t),
                    "source": (r.get("dorg") or "").strip(),
                    "market": "코스피" if mk == "01" else "코스닥",
                    "stocks": stocks,
                })

        rows.sort(key=lambda r: r.get("at") or "", reverse=True)
        return {"rows": rows, "errors": errors or None}

    return _cached("moves", MOVES_TTL, make)


def _stamp(d, t):
    """20260915 + 121741 → 2026-09-15T12:17:41+09:00"""
    if len(d) != 8:
        return ""
    t = (t + "000000")[:6]
    return "%s-%s-%sT%s:%s:%s+09:00" % (d[:4], d[4:6], d[6:8], t[:2], t[2:4], t[4:6])
