#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""뉴스를 받는 족족 쌓고, 같은 사건끼리 묶는다 (2026-09-21 지시)

재권님 말씀 그대로다.

    받는족족 쌓아놓고 데일리분석에 계속 쌓아지게 하고
    텔레그램으로 보내는건 아침7시반 오후1시반 저역 10시 이렇게 하루3번
    주말에도 이슈는 계속있으니 매일 받으면 좋을거같아

왜 쌓아야 하나
--------------
**지금은 아무 데도 저장하지 않는다.** `news.py` 가 RSS 를 180초 캐시로 받아
화면에 뿌리고 버린다. RSS 는 최근 것만 주므로, 화면을 안 열고 있으면 그 사이
지나간 기사는 **영영 못 본다.**

2026-09-21 09:01 의 수출 발표(714억 달러·역대최대)가 그랬다. 저장된 곳이
없어서 다음 날 「어제 이슈」로 꺼낼 수가 없다.

같은 사건은 묶는다
------------------
경제지 여럿이 같은 발표를 따로 쓴다. 그대로 쌓으면 목록이 같은 이야기로 찬다.

    [3건] 반도체 수출 '또 역대최대'…이달 20일까지 259.4%↑
            └ 아시아경제 · 머니투데이가 같은 내용을 따로 씀   (2026-09-21 실측)

**제목의 낱말이 얼마나 겹치는지**로 묶는다. 형태소 분석기 없이 되고, 같은
발표를 받아쓴 기사들은 숫자와 고유명사가 그대로 겹친다.

**묶는 일은 쌓을 때 한 번만 한다.** 화면이 열릴 때마다 하면 같은 계산을
되풀이한다 — 화면은 완성된 묶음을 읽기만 한다 (2026-09-21 지시).

무엇이 「중요」한가는 이 파일이 정하지 않는다
--------------------------------------------
`data/news-alerts.json` 이 정한다. 재권님이 데일리분석 화면에서 낱말을
넣고 빼는 자리이고, 여기는 그 파일을 읽어 판정만 한다.
"""

import io
import json
import os
import re
import sqlite3
import threading

import marketdb
import time
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

HERE = os.path.dirname(os.path.abspath(__file__))
HOLDINGS_DIR = os.path.dirname(HERE)
# 자리·journal_mode·쓰기 가능 여부는 **`marketdb` 한 곳**이 정한다 (2026-10-01).
DB_PATH = marketdb.DB_PATH
ALERTS_PATH = os.path.join(HOLDINGS_DIR, "data", "news-alerts.json")

# 얼마나 자주 받아 쌓나. news.py 의 캐시(180초)보다 길면 캐시가 소용없고,
# 짧으면 같은 것을 되풀이해 받는다. **주말·밤에도 돈다** (2026-09-21 지시).
COLLECT_INTERVAL = 300

# 같은 사건으로 묶을 때 견주는 범위. 이보다 오래된 기사와는 안 묶는다 —
# 며칠 지나 같은 낱말이 나오는 것은 대개 다른 사건이다.
GROUP_WINDOW_H = 24

# 쌓아 두는 기간 (2026-11-03 재권님 「기사는 한달 지나면 지우는 걸로」 · 그 전 2026-10-12 「1주일」). 그 전에는 지우는 코드가 없어
# 무기한 쌓였다(9-21 부터 3주 2,119건). 쌓는 바퀴(`collect_once`)에서 이보다 오래된 기사를 지운다.
# 읽는 쪽은 모두 이 안에 든다 — 데일리 화면 36시간(`daily-view.js` 의 NEWS_HOURS) · 같은 사건 묶기 창
# `GROUP_WINDOW_H`(24시간) · 즉시 알림 `ALERT_MAX_AGE_H`(3시간) · 정기 묶음은 지난 발송 뒤 것만.
# 크기(11-03 개발 DB 실측) — 7일 936건에 표 · 색인 합 0.4MB 쯤, 하루 평균 130건이라 30일이면 4천 건 · 2MB 쯤(DB 전체 514MB 에 견주면 작다).
NEWS_KEEP_DAYS = 30

# 「보관 기간 전부」(`/api/news/stored?all=1`)로 한 번에 내주는 묶음 상한 (2026-11-05 · 화면이 limit=20000 을 박아 묻던 것을 서버로).
# 넘으면 앞(새것)부터 이만큼만 내고 응답 `meta.truncated` 로 알린다 — 조용히 자르지 않는다. 11-05 8765 실측 묶음 1,077 · 압축 83KB
NEWS_STORED_MAX = 20000

# 제목 낱말이 이만큼 겹치면 같은 사건으로 본다.
#
# **2026-09-21 에 80건으로 기준을 바꿔가며 재고 골랐다.**
#
#     0.40 → 77묶음 (3건이 묶임)   같은 사건인데 안 묶이는 것이 남았다
#     0.35 → 75묶음 (5건)
#     0.30 → 74묶음 (6건)          ← 이것
#     0.25 → 71묶음 (9건)
#
# 0.30 을 고른 이유는 **놓치던 짝이 이 선에서 잡혀서**다. 아래 둘이 0.333 이다.
#
#     네오사피엔스, 코스닥 데뷔 첫 날 200%대 급등
#     '유튜브 그 목소리' 네오사피엔스 코스닥 상장일 195% 급등
#     겹친 낱말 — 네오사피엔스 · 코스닥 · 급등
#
# 더 낮추면 낱말 셋만 겹쳐도 묶여 다른 사건이 섞인다.
GROUP_MIN = 0.3

# 묶을 때 세지 않는 낱말. 어디에나 나와서 겹침을 부풀린다.
STOP = {"속보", "종합", "오늘", "내일", "우리", "관련", "기자", "단독", "분석",
        "전망", "이슈", "시장", "가운데", "대비", "기록", "가능성", "이상", "이하"}

_lock = threading.Lock()
_alerts_cache = {"at": 0, "value": None}


# ---------------------------------------------------------------- 저장소

def _conn():
    """읽기 전용 서버면 `mode=ro` 로 열린다 — `marketdb` 가 정한다."""
    return marketdb.connect(timeout=10)


def init():
    """표를 만든다. 서버가 뜰 때 한 번 부른다."""
    with _lock, _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS news_items (
          link        TEXT PRIMARY KEY,   -- 중복 판정 기준. 같은 주소는 한 번만
          title       TEXT NOT NULL,
          source      TEXT,
          topic       TEXT,
          topic_label TEXT,
          at          TEXT,               -- 기사 시각 (한국, ISO)
          at_ts       INTEGER,            -- 위를 초로. 정렬·범위 조회용
          group_id    TEXT,               -- 같은 사건 묶음
          is_lead     INTEGER DEFAULT 0,  -- 그 묶음의 대표(가장 이른 기사)
          alert       TEXT,               -- 걸린 「중요」 규칙 이름
          alerted_at  INTEGER,            -- 즉시 알림을 보낸 시각 · -1 은 안 보내고 정기 묶음으로 넘김
          digest_at   INTEGER,            -- 정기 묶음에 실어 보낸 시각
          seen_at     INTEGER             -- 우리가 처음 받은 시각
        );
        CREATE INDEX IF NOT EXISTS ix_news_at   ON news_items(at_ts DESC);
        CREATE INDEX IF NOT EXISTS ix_news_grp  ON news_items(group_id);
        CREATE INDEX IF NOT EXISTS ix_news_sent ON news_items(digest_at);
        CREATE TABLE IF NOT EXISTS news_tr (     -- 해외 1차 출처 제목 옮김(2026-11-13) — 원문 → 한국어 · 한 번 옮긴 것은 다시 안 부른다
          orig TEXT PRIMARY KEY, ko TEXT NOT NULL, at INTEGER);
        """)
        cols = {r[1] for r in c.execute("PRAGMA table_info(news_items)")}
        if "title_orig" not in cols:
            c.execute("ALTER TABLE news_items ADD COLUMN title_orig TEXT")   # 옮긴 제목의 원문(영어 등) — 없으면 제목이 원문
        if "office_id" not in cols:
            c.execute("ALTER TABLE news_items ADD COLUMN office_id TEXT")    # 찾는 길(네이버)로 온 기사의 네이버 언론사 번호 — 목록 (다) 안 · 밖은 이것으로 그때 셈(news.press_tally · 11-19 개념정의 덧)


# ---------------------------------------------------------------- 묶기

def _tokens(title):
    """제목에서 견줄 낱말만 남긴다. [속보] 같은 꼬리표와 흔한 말은 뺀다."""
    t = re.sub(r"\[[^\]]*\]", " ", title or "")
    words = re.findall(r"[가-힣A-Za-z0-9]{2,}", t)
    return {w for w in words if w not in STOP}


def _similar(a, b):
    """두 낱말 집합이 얼마나 겹치나 (0~1)."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _find_group(c, title, at_ts):
    """최근 기사 중 같은 사건이 있으면 그 묶음 번호를 돌려준다."""
    since = (at_ts or int(time.time())) - GROUP_WINDOW_H * 3600
    mine = _tokens(title)
    best, best_score = None, 0.0
    for r in c.execute(
            "SELECT title, group_id FROM news_items WHERE at_ts >= ? ORDER BY at_ts DESC LIMIT 400",
            (since,)):
        score = _similar(mine, _tokens(r["title"]))
        if score >= GROUP_MIN and score > best_score:
            best, best_score = r["group_id"], score
    return best


# ---------------------------------------------------------------- 「중요」 판정

def load_alerts():
    """중요 규칙. 파일이 없거나 깨졌으면 빈 규칙으로 돈다 — 알림만 안 갈 뿐이다."""
    now = time.time()
    if _alerts_cache["value"] is not None and (now - _alerts_cache["at"]) < 30:
        return _alerts_cache["value"]
    try:
        with io.open(ALERTS_PATH, encoding="utf-8") as f:
            value = json.load(f)
    except Exception:
        value = {"즉시알림": []}
    _alerts_cache.update(at=now, value=value)
    return value


def save_alerts(value):
    """화면에서 고친 규칙을 파일에 쓴다. 쓰고 나서 캐시를 버린다."""
    os.makedirs(os.path.dirname(ALERTS_PATH), exist_ok=True)
    with io.open(ALERTS_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
    _alerts_cache.update(at=0, value=None)
    return True


def match_alert(title, key="즉시알림"):
    """제목이 어떤 규칙에 걸리나. 안 걸리면 None.

    `key` — 「즉시알림」(바로 보낸다) · 「모아서」(정기 묶음 맨 위 칸 · 2026-10-12).
    """
    for rule in (load_alerts().get(key) or []):
        if not rule.get("켬", True):
            continue
        for pat in (rule.get("제목에") or []):
            try:
                if re.search(pat, title or ""):
                    return rule.get("이름") or pat
            except re.error:
                # 규칙은 사람이 타이핑하는 자리다. 잘못 쓴 정규식 하나가
                # 나머지 판정을 막으면 안 되므로 그것만 건너뛴다.
                if pat and pat in (title or ""):
                    return rule.get("이름") or pat
    return None


# ---------------------------------------------------------------- 쌓기

def _ts(at):
    """'2026-09-21T09:01:00+09:00' → 초. 못 읽으면 지금."""
    try:
        return int(datetime.fromisoformat(at).timestamp())
    except Exception:
        return int(time.time())


def store(rows):
    """받은 기사 중 **새 것만** 넣는다. 넣은 것들을 돌려준다.

    돌려주는 것은 즉시 알림을 보낼지 판단하는 쪽이 쓴다.
    """
    if not rows:
        return []
    now = int(time.time())
    added = []
    with _lock, _conn() as c:
        for row in rows:
            link = (row.get("link") or "").strip()
            title = (row.get("title") or "").strip()
            if not link or not title:
                continue
            if c.execute("SELECT 1 FROM news_items WHERE link = ?", (link,)).fetchone():
                continue

            at = row.get("at") or ""
            at_ts = _ts(at)
            gid = _find_group(c, title, at_ts)
            is_lead = 0
            if not gid:
                gid = "g%d_%s" % (at_ts, link[-8:])
                is_lead = 1          # 그 사건의 첫 기사가 대표가 된다
            alert = match_alert(title)

            c.execute("""INSERT INTO news_items
                (link, title, source, topic, topic_label, at, at_ts,
                 group_id, is_lead, alert, seen_at, title_orig, office_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (link, title, row.get("source"), row.get("topic"),
                       row.get("topicLabel"), at, at_ts, gid, is_lead, alert, now, row.get("titleOrig"), row.get("officeId")))
            added.append({"link": link, "title": title, "at": at,
                          "source": row.get("source"), "topic": row.get("topic"),
                          "topicLabel": row.get("topicLabel"),
                          "group": gid, "alert": alert})
    return added


def purge_old(days=None):
    """`NEWS_KEEP_DAYS` 지난 기사를 지운다. 지운 건수를 돌려준다. 기사 시각(`at_ts`)으로 자른다."""
    cut = int(time.time()) - (days or NEWS_KEEP_DAYS) * 86400
    with _lock, _conn() as c:
        return c.execute("DELETE FROM news_items WHERE at_ts < ?", (cut,)).rowcount or 0


# ---------------------------------------------------------------- 읽기

def groups(hours=24, limit=80):
    """쌓인 것을 **묶음 단위**로 돌려준다. 화면이 읽는 모양이다.

    한 묶음은 대표 기사 하나와 「외 N건」이다. 네이버 종목 뉴스가 같은 모양이라
    화면에서 두 칸이 같아 보인다.
    """
    since = int(time.time()) - hours * 3600
    fs = foreign_sources()
    out = {}
    with _conn() as c:
        for r in c.execute(
                "SELECT * FROM news_items WHERE at_ts >= ? ORDER BY at_ts DESC",
                (since,)):
            if _untranslated(r, fs):
                continue
            g = out.setdefault(r["group_id"], {
                "group": r["group_id"], "title": r["title"], "link": r["link"],
                "at": r["at"], "source": r["source"], "topic": r["topic"],
                "topicLabel": r["topic_label"], "alert": r["alert"],
                "titleOrig": _orig(r),
                "more": 0, "others": [],
            })
            if g["link"] == r["link"]:
                continue
            g["more"] += 1
            if len(g["others"]) < 4:
                g["others"].append({"title": r["title"], "link": r["link"],
                                    "source": r["source"], "at": r["at"], "titleOrig": _orig(r)})
            # 묶음 안에 중요한 것이 있으면 묶음도 중요로 친다
            if r["alert"] and not g["alert"]:
                g["alert"] = r["alert"]
    rows = sorted(out.values(), key=lambda g: g["at"] or "", reverse=True)
    return rows[:limit]


# ---------------------------------------------------------------- 이슈 (2026-11-12)
# 재권님 룰 「뉴스 분석은 모으는 자리다 — 기사를 모으고 세계 주요 이슈를 뽑는다」(CLAUDE.md) · 상세는 company-setup/README.md 「이슈 뽑기」 →
# 안 「뉴스 이슈 만들기」 에 「응 올려놔」(11-12 16:3x). 같은 사건 묶음(group_id · 위 「묶기」)을 「이슈」 하나로 올린다.
#   뜨거운 정도   기사 수 · 다룬 언론사 수 · 다룬 나라 수 · 늘어나는 속도(최근 ISSUE_RISE_H 시간 기사 수와 그 앞 같은 시간) — 숫자 그대로 · 합친 점수 없음
#   줄 세우기     언론사 수 → 나라 수 → 기사 수 → 마지막 보도 · 「막 뜨는 이슈」 는 rising 으로 따로(늘어난 수 → 최근 수)
#   나라          둘을 가른다(개념정의 덧 11-12) — where 는 사건이 난 나라 · 지역(룰 「어디」) · 아직 가를 길이 없어 None(「모름」) ·
#                 pressNations · nations 는 다룬 언론사의 나라 — 받는 곳 목록(news-topics.json feeds)의 「나라」 칸 · 목록이 한 나라뿐이면 nations 는 None(「못 잼」) · 칸이 없는 받는 곳은 nationsUnknown
#   확인 정도     받는 곳 갈래 (가) 1차 출처 기사가 묶음에 있으면 「1차 출처」 · 없으면 「기사만」
#   종목 · 업종 대입 · 좋다 나쁘다는 안 한다 — 산업 분석 몫
ISSUE_WINDOW_H = 48         # 이슈를 볼 시간 창(시간)
ISSUE_RISE_H = 3            # 늘어나는 속도 — 최근 이 시간과 그 앞 같은 시간의 기사 수
ISSUE_MIN_ARTICLES = 2      # 이슈로 올리는 묶음의 최소 기사 수(한 건짜리는 사건이 아니라 기사)
ISSUE_LIMIT = 50            # 내주는 이슈 수
ISSUE_RISING_TOP = 10       # 「막 뜨는 이슈」 칸 수
ISSUE_ARTICLES_MAX = 30     # 이슈 하나에 싣는 기사 목록 상한(기사 수는 전부 센다)


def _feeds():
    """받는 곳 목록 — {이름: {나라, 갈래}}. 기사의 source 는 받는 곳 이름(label)이다."""
    try:
        with open(os.path.join(HOLDINGS_DIR, "data", "news-topics.json"), encoding="utf-8") as f:
            feeds = json.load(f).get("feeds") or []
    except Exception:
        return None
    return {(x.get("label") or x.get("id") or ""): {"nation": x.get("나라"), "kind": x.get("갈래") or ""}
            for x in feeds if isinstance(x, dict)}


def issues(now=None):
    """이슈 판 — {issues, rising, meta}. 서버 주소 /api/news/hot 이 그대로 낸다."""
    now = int(now or time.time())
    since = now - ISSUE_WINDOW_H * 3600
    fd = _feeds()
    nations = {v["nation"] for v in (fd or {}).values() if v["nation"]}
    can_count = fd is not None and len(nations) > 1
    by = {}
    with _conn() as c:
        fs = foreign_sources()
        for r in c.execute("SELECT * FROM news_items WHERE at_ts >= ? ORDER BY at_ts", (since,)):
            if _untranslated(r, fs):
                continue
            by.setdefault(r["group_id"], []).append(r)
    rise0, rise1 = now - ISSUE_RISE_H * 3600, now - 2 * ISSUE_RISE_H * 3600
    out = []
    for gid, arts in by.items():
        if len(arts) < ISSUE_MIN_ARTICLES:
            continue
        lead = next((a for a in arts if a["is_lead"]), arts[0])
        presses = {a["source"] or "" for a in arts} - {""}
        info = [(fd or {}).get(a["source"] or "") for a in arts]
        nat = {i["nation"] for i in info if i and i["nation"]}
        unknown = sum(1 for i in info if not i or not i["nation"])
        labels = {}
        for a in arts:
            if a["topic_label"]:
                labels[a["topic_label"]] = labels.get(a["topic_label"], 0) + 1
        recent = sum(1 for a in arts if a["at_ts"] >= rise0)
        before = sum(1 for a in arts if rise1 <= a["at_ts"] < rise0)
        primary = any(i and str(i["kind"]).startswith("(가)") for i in info)
        out.append({
            "id": gid,
            "name": lead["title"],
            "kind": max(labels, key=lambda k: labels[k]) if labels else None,
            "where": None,                                   # 사건 나라 — 아직 못 가름(「모름」 · meta.where)
            "pressNations": sorted(nat) if nat else None,
            "first": arts[0]["at"], "last": arts[-1]["at"],
            "articles": len(arts),
            "presses": len(presses),
            "nations": len(nat) if can_count else None,
            "nationsUnknown": unknown,
            "recent": recent, "before": before,
            "confirm": "1차 출처" if primary else "기사만",
            "items": [{"title": a["title"], "source": a["source"], "at": a["at"], "link": a["link"], "titleOrig": _orig(a)}
                      for a in reversed(arts)][:ISSUE_ARTICLES_MAX],
        })
    out.sort(key=lambda x: (x["presses"], x["nations"] if x["nations"] is not None else -1, x["articles"], x["last"] or ""), reverse=True)
    rising = sorted([x for x in out if x["recent"] > x["before"]],
                    key=lambda x: (x["recent"] - x["before"], x["recent"]), reverse=True)[:ISSUE_RISING_TOP]
    meta = {"windowH": ISSUE_WINDOW_H, "riseH": ISSUE_RISE_H, "minArticles": ISSUE_MIN_ARTICLES, "found": len(out),
            "nations": "셈" if can_count else ("못 잼 — 받는 곳 목록이 한 나라뿐" if fd is not None else "못 잼 — 받는 곳 목록 못 읽음"),
            "feedNations": sorted(nations),
            "where": "모름 — 사건 난 나라를 가르는 셈이 아직 없음(pressNations 는 언론사 나라)",
            "note": "뜨거운 정도는 숫자 그대로(합친 점수 없음) · 줄 세우기 언론사 수 → 나라 수 → 기사 수 → 마지막 보도 · "
                    "rising 은 최근 riseH 시간 기사 수(recent)가 그 앞 같은 시간(before)보다 많은 이슈 · 종목 대입은 산업 분석 몫"}
    return {"issues": out[:ISSUE_LIMIT], "rising": [x["id"] for x in rising], "meta": meta}


def _orig(r):
    """옮긴 제목의 원문 칸 — 칸을 더하기 전 DB(읽기 전용 서버가 8765 보다 먼저 뜬 때)에서도 안 깨지게 없으면 None."""
    return r["title_orig"] if "title_orig" in r.keys() else None


def foreign_sources():
    """해외 받는 곳 이름 — 목록(news-topics.json)의 「나라」 칸이 KR 이 아닌 것. 목록을 못 읽으면 빈 set."""
    return {k for k, v in (_feeds() or {}).items() if v["nation"] and v["nation"] != "KR"}


def _untranslated(r, fs):
    """해외 받는 곳 기사인데 한국어로 안 옮긴 줄(원문 칸 없음) — 화면 · 알림에 내지 않는다(재권님 「내가 볼것만 한국어로」 11-17)."""
    return (r["source"] or "") in fs and not _orig(r)


def ko_backfill():
    """이미 쌓인 해외 기사 중 영어 제목 그대로인 것(옮기기 전에 쌓임)을 옮겨 둔 한국어로 바꾼다 — 쓰기 되는 서버(8765)만.
    아직 안 옮긴 제목은 뒤에서 옮기기를 걸고 다음 바퀴에 바꾼다. 바꾼 수."""
    fs = foreign_sources()
    if not fs or not marketdb.writable():
        return 0
    try:
        with _conn() as c:
            q = "SELECT link, title FROM news_items WHERE title_orig IS NULL AND source IN (%s)" % ",".join("?" * len(fs))
            rows = [(r["link"], r["title"]) for r in c.execute(q, sorted(fs))]
    except sqlite3.Error:
        return 0
    if not rows:
        return 0
    have = tr_get([t for _, t in rows])
    upd = [(have[t], t, l) for l, t in rows if have.get(t)]
    if upd:
        with _lock, _conn() as c:
            c.executemany("UPDATE news_items SET title = ?, title_orig = ? WHERE link = ?", upd)
    miss = [t for _, t in rows if not have.get(t)]
    if miss:
        import news
        news._tr_kick(miss)
    return len(upd)


def tr_get(origs):
    """옮겨 둔 제목 {원문: 한국어}. 못 읽으면 빈 dict(옮김 없음으로 — 원문을 화면에 내지 않는 쪽으로 간다)."""
    origs = [o for o in set(origs) if o]
    if not origs:
        return {}
    try:
        with _conn() as c:
            q = "SELECT orig, ko FROM news_tr WHERE orig IN (%s)" % ",".join("?" * len(origs))
            return {o: k for o, k in c.execute(q, origs)}
    except sqlite3.Error:
        return {}


def tr_put(pairs):
    """옮긴 제목을 남긴다 — 쓰기 되는 서버(8765)만. 남긴 수."""
    if not pairs or not marketdb.writable():
        return 0
    now = int(time.time())
    with _lock, _conn() as c:
        c.executemany("INSERT OR REPLACE INTO news_tr VALUES (?,?,?)", [(o, k, now) for o, k in pairs.items()])
    return len(pairs)


def counts(hours=24):
    """주제별 개수. 화면이 칸을 나눌 때 쓴다."""
    since = int(time.time()) - hours * 3600
    with _conn() as c:
        return {(r["topic_label"] or "기타"): r["n"] for r in c.execute(
            """SELECT topic_label, COUNT(*) n FROM news_items
               WHERE at_ts >= ? GROUP BY topic_label ORDER BY n DESC""", (since,))}


def total():
    with _conn() as c:
        r = c.execute("SELECT COUNT(*) n, MIN(at) a, MAX(at) b FROM news_items").fetchone()
        return {"count": r["n"], "from": r["a"], "to": r["b"]}


# ---------------------------------------------------------------- 발송 표시

def unsent_digest(limit=200):
    """정기 발송에 아직 안 실린 것. 묶음의 대표만 고른다."""
    fs = foreign_sources()
    with _conn() as c:
        return [dict(r) for r in c.execute(
            """SELECT * FROM news_items
               WHERE digest_at IS NULL AND is_lead = 1
               ORDER BY at_ts DESC LIMIT ?""", (limit,)) if not _untranslated(r, fs)]


def unsent_alerts(limit=20, flash=None):
    """즉시 알림을 아직 안 보낸 「중요」 기사 · 속보(제목에 FLASH_WORD — 2026-11-18 한 길로 합침)."""
    flash = TG_NEW if flash is None else flash
    fs = foreign_sources()
    with _conn() as c:
        return [dict(r) for r in c.execute(
            """SELECT * FROM news_items
               WHERE (alert IS NOT NULL OR title LIKE ?) AND alerted_at IS NULL
               ORDER BY at_ts DESC LIMIT ?""", ("%" + FLASH_WORD + "%" if flash else "\x00", limit)) if not _untranslated(r, fs)]


def mark_sent(links, field):
    """보낸 것을 표시한다. field 는 'digest_at' 또는 'alerted_at'."""
    if field not in ("digest_at", "alerted_at") or not links:
        return 0
    now = int(time.time())
    with _lock, _conn() as c:
        c.executemany("UPDATE news_items SET %s = ? WHERE link = ?" % field,
                      [(now, l) for l in links])
    return len(links)


# ---------------------------------------------------------------- 텔레그램

# 정기 발송 시각 (2026-09-21 지시 — "아침7시반 오후1시반 저역 10시").
# **주말에도 보낸다** — "주말에도 이슈는 계속있으니 매일 받으면 좋을거같아".
# 22:00 → 21:50 (2026-10-12 · 재권님 「가」) — 22:00 부터 조용한 시간(`dart.QUIET_FROM`)이라 그 앞으로 당겼다.
# 밤(21:50 뒤) 기사는 다음 날 07:30 묶음에 실린다.
DIGEST_SLOTS = [(7, 30), (13, 30), (21, 50)]

# 그 시각을 놓쳤을 때 몇 분까지 따라잡아 보낼 것인가. 서버가 잠깐 꺼져 있었다고
# 하루치를 통째로 건너뛰면 안 된다.
SLOT_GRACE_MIN = 90

# 한 번에 보낼 줄 수. 그보다 많으면 「외 N건」으로 줄인다 — 텔레그램은
# 한 메시지가 길면 잘린다.
DIGEST_MAX = 15

# 정기 묶음에서 주제 하나에 싣는 묶음 수 (2026-10-12). 넘는 것은 「외 N묶음」.
DIGEST_PER_TOPIC = 3

# 즉시 알림 하루 상한 (2026-10-12). **`None` 이면 상한 없음** — 재권님이 아직 안 정하셨다.
# 숫자를 넣으면 그날 그만큼 보낸 뒤로는 바로 안 보내고 정기 묶음으로 넘긴다.
ALERT_DAILY_MAX = None

# 즉시 알림은 **이보다 오래된 기사에는 보내지 않는다.**
#
# 텔레그램이 꺼져 있는 동안에도 쌓이기 때문에, 나중에 설정을 켜는 순간
# 며칠치 「중요」가 한꺼번에 날아간다. dart.py 가 `quiet_first_run` 으로
# 막는 것과 같은 자리다 — 지난 것은 **보내지 않고 보낸 것으로 표시**해
# 조용히 넘긴다. 정기 발송에는 그대로 들어가므로 사라지지 않는다.
ALERT_MAX_AGE_H = 1            # 3 → 1(2026-11-18 재권님 「응 그래」 — 「1시간 넘게 지난 속보는 낮에 보내지 않음」 · 정기 글에는 그대로 실린다 · 밤 속보 07:00 길은 FLASH_NIGHT_MAX_H 그대로)

# 비슷한 속보는 한 통만 (2026-11-18 재권님 「응 그래」 — 「30분 안에 같은 회사 · 같은 일을 다룬 속보는 첫 한 통만」).
# 13:05 엔비디아 실적 속보 넷이 언론사 · 제목이 달라 묶음(group_id)이 갈려 네 통 갔다 — 묶음 말고 제목 낱말로 한 번 더 본다.
# 바로 간 알림 중 SIMILAR_WINDOW_MIN 분 안의 것과 제목 낱말(2글자 이상 · 숫자 · 흔한 시황 낱말 빼고)이 SIMILAR_MIN_SHARED 개 이상 겹치고
# 짧은 쪽 낱말의 SIMILAR_RATIO 이상이 겹치고, 두 제목의 주어(앞쪽 흔하지 않은 낱말 — 회사 · 기관 이름)가 글자 그대로 같으면 같은 일로 보고 안 보낸다(정기 글에는 그대로 · similar_title).
# 낱말은 앞이 같으면 같다고 본다(「시간외」 · 「시간외에서」 — 조사).
SIMILAR_WINDOW_MIN = 30
SIMILAR_MIN_SHARED = 2
SIMILAR_RATIO = 0.25          # 0.4 는 엔비디아 넷 중 셋 짝을 놓쳤다(11-18 13:05 제목으로 잼)
SIMILAR_TURN = ("부인", "철회", "취소", "번복", "반박", "사실무근", "일축", "정정")   # 한쪽 제목에만 있으면 앞 소식을 뒤집는 다른 일로 본다(qa 검수 11-18 — 「카카오 매각 추진」 뒤 「매각 추진 공식 부인」 이 묶였다)
SIMILAR_COMMON = {"속보", "단독", "종합", "상승", "하락", "급등", "급락", "마감", "주가", "시간외", "거래", "거래서", "전망", "발표", "기록",
                  "코스피", "코스닥", "증시", "개장", "출발", "오전", "오후", "장중", "반등", "약세", "강세", "외국인", "기관", "개인"}

# 속보도 즉시 알림 길로 간다 (2026-11-18 재권님 「커밋해」 — 속보 정리를 바로 알림 · 낱말 「중요」 알림과 같은 사건은 한 번).
# 속보 정리(news_brief.flash_once)가 붙기를 이만큼(초) 기다리고, 넘으면 제목만으로 보낸다.
FLASH_WORD = "속보"
FLASH_WAIT_SEC = 300

# 켜기 — 새 글(정기 글 이슈 정리 · 속보 바로 알림)은 이 스위치가 켜진 서버만 보낸다. **기본 꺼짐**(개념정의 검수 11-18 —
# 받는 글이 바뀌는 「켜기」 자리 · 알림으로 나간 것은 못 지운다 · 켤지는 재권님이 정하신다 · 여쭙는 것은 시황분석).
# 꺼져 있으면 옛 길 그대로(정기 = 제목 묶음 · 바로 = 「중요」 규칙만). 미리보기(preview)는 꺼져 있어도 새 글을 보여 준다(켤 때 셈 자료).
TG_NEW = (os.environ.get("KJC_NEWS_TG") or "").strip() == "1"

# 밤(조용한 시간)에 나온 속보는 07:30 정기 글로 넘기지 않고 조용한 시간이 끝나는 07:00 에 바로 알림으로 보낸다
# (재권님 11-18 「밤속보는 아침 7시로 해줘」). 이 시간(시)보다 오래된 것은 ALERT_MAX_AGE_H 그대로 넘긴다 — 조용한 시간 길이(22~07)를 덮는 값.
FLASH_NIGHT_MAX_H = 10


def _telegram(text, send=None):
    """보낸다. **`send` 가 없으면 보내지 않는다.**

    ⚠️ **여기서 `dart.telegram_send` 를 직접 부르지 않는다** (2026-09-23).
    이 파일은 **자기가 몇 번 포트인지 모른다.** 직접 부르면 **뜬 서버가
    전부 보낸다** — 그날 `--slow` 아닌 셋(8765·8767·8770)이 **같은 기사를
    각각 보내** 재권님 폰에 **두세 번** 갔다.

        15:59  HBM4 날개 단 삼성전자…   8765
        15:58  **같은 기사**            8770     ← 1분 차이로 따로

    **`market.db` 가 폴더마다 따로**(`HOLDINGS_DIR/market.db`)라
    「보냈다」 표시가 공유되지 않는다. 각자 「아직 안 보냈다」 로 읽는다.

    **데일리(`kis_proxy.py` 의 `send=`)와 같은 꼴로 바꿨다** — 부르는 쪽이
    포트를 보고 `send` 를 주거나 `None` 을 준다.
    """
    if send is None:
        return (False, "이 서버에서는 보내지 않습니다 (메인에서만 보냅니다)")
    return send(text)


def _meta(key, value=None):
    import dart
    if value is None:
        return dart._meta_get(key)
    dart._meta_set(key, value)
    return value


def _hhmm(at):
    return (at or "")[11:16]


def send_alerts(send=None):
    """「중요」로 걸린 것을 바로 보낸다. 보낸 건수를 돌려준다.

    `send` 가 없으면 **한 건도 안 보내고 표시도 안 한다** — 첫 발송에서
    `ok` 가 `False` 라 그 자리에서 멈춘다. **안 보냈으니 안 적는 것이 맞다.**
    """
    rows = unsent_alerts()
    if not rows:
        return 0

    # 오래된 것은 조용히 넘긴다 (위 ALERT_MAX_AGE_H 참고)
    cutoff = int(time.time()) - ALERT_MAX_AGE_H * 3600
    # 안 보낸 것은 `alerted_at = -1`(「안 보냄」)로 적는다 — 「이미 갔다」(양수)와 갈린다.
    # **조용한 시간에 나온 기사도 같은 길이다** (2026-10-12 재권님 「밤 10시~아침 7시까지는 알림을 주지 않는다」).
    # 07:00 에 몰아 보내지 않고 07:30 정기 묶음에 ❗ 로 실린다 — `alert` 를 지금 규칙으로 남겨 두는 까닭이다.
    import dart
    for r in rows:
        r["_name"] = _alert_name(r)
    night = int(time.time()) - FLASH_NIGHT_MAX_H * 3600
    # 밤 속보 07:00 길은 우리가 그 기사를 **밤(조용한 시간)에 처음 본 것**만 — 낮에 새 받는 곳이 밤 속보를 처음 가져오면 그것은 1시간 넘은 속보라
    # 낮 길(ALERT_MAX_AGE_H)을 따른다(qa 11-19 — 8765 14:09 재시작 첫 바퀴에 06:05 속보가 14:10 에 감 · 「1시간 넘은 속보는 낮에 안 보냄」 과 어긋남)
    morning = [r for r in rows if TG_NEW and FLASH_WORD in (r["title"] or "") and dart.in_quiet(r["at_ts"]) and (r["at_ts"] or 0) >= night
               and dart.in_quiet(r.get("seen_at") or r["at_ts"])]
    late = [r for r in rows if r not in morning and ((r["at_ts"] or 0) < cutoff or dart.in_quiet(r["at_ts"]))]
    rows = [r for r in rows if r not in late]
    if dart.in_quiet():
        _hold_for_digest(late)
        return 0                # 지금이 조용한 시간 — 남은 것(밤 속보 morning 포함)은 07:00 뒤 바퀴에
    _hold_for_digest(late)

    # **보낼 때 지금 규칙으로 다시 본다** (2026-10-12). 쌓을 때 적어 둔 `alert` 는 그때 규칙이라,
    # 규칙을 고쳐도 이미 쌓인 것은 옛 규칙으로 나갔다. 안 걸리면 보내지 않고 표시만 한다 —
    # 정기 묶음에는 그대로 실린다(`digest_at` 은 안 건드린다).
    #
    # **같은 사건은 한 번만 간다** (2026-10-12 — 「1~10일 수출 역대 최대」 한 건이 한 시간에 5통 갔다).
    # 묶음(`group_id`)에서 이미 하나가 바로 갔으면 나머지는 건너뛴다.
    day = datetime.now(KST).strftime("%Y%m%d")
    count_key = "news_alert_count_" + day
    done_today = int(_meta(count_key) or 0)

    sent, skip, seen = [], [], set()
    recent = _recent_alert_titles()                 # 비슷한 속보 — 30분 안에 간 것(이번 바퀴에 간 것도 더해 간다)
    for r in sorted(rows, key=lambda x: x["at_ts"] or 0):       # 이른 기사가 그 묶음 대표로 간다
        name = r["_name"]
        if not name or r["group_id"] in seen or _group_alerted(r["group_id"], r["link"]) \
                or any(similar_title(r["title"], t) for t in recent):
            skip.append(r["link"])
            continue
        if ALERT_DAILY_MAX is not None and done_today + len(sent) >= ALERT_DAILY_MAX:
            skip.append(r["link"])               # 상한을 넘었다 — 정기 묶음으로 간다
            continue
        text = alert_text(r, name)
        if text is None:
            continue                             # 속보 정리를 기다린다 — 다음 바퀴에
        ok, _why = _telegram(text, send)
        if not ok:
            # 설정이 없거나 막혔다. 다음 바퀴에 다시 본다 — 오래된 것만 적는다
            return _finish_alerts(sent, [], count_key, done_today)
        sent.append((r["link"], name))
        seen.add(r["group_id"])
        recent.append(r["title"])
        time.sleep(0.4)      # 텔레그램 초당 제한
    return _finish_alerts(sent, skip, count_key, done_today)


def _alert_name(r, flash=None):
    """바로 보낼 까닭 — 「중요」 규칙 이름 · 아니면 속보(스위치 TG_NEW 가 켜졌을 때) · 둘 다 아니면 None."""
    flash = TG_NEW if flash is None else flash
    return match_alert(r["title"]) or (FLASH_WORD if flash and FLASH_WORD in (r["title"] or "") else None)


def alert_text(r, name, wait=True):
    """즉시 알림 글. 속보는 정리(news_brief)가 붙으면 그 글을 넣는다 — 아직이고 FLASH_WAIT_SEC 안이면 None(기다림)."""
    summary = None
    if FLASH_WORD in (r["title"] or ""):
        import news_brief
        summary = news_brief.flash_summary(r["link"])
        if summary is None and wait and news_brief.ON and time.time() - (r["at_ts"] or 0) < FLASH_WAIT_SEC:
            return None
    return "%s%s\n%s%s · %s\n%s" % (
        "" if name == FLASH_WORD else "[%s] " % name, r["title"], (summary + "\n") if summary else "", r["source"] or "", _hhmm(r["at"]), r["link"])


def _finish_alerts(sent, skip, count_key, done_today):
    """보낸 것과 건너뛴 것을 표시한다. 보낸 것만 `alert` 를 남긴다 — 「이 묶음은 이미 갔다」 의 근거다.
    sent 는 (링크, 까닭) — 속보로만 간 것도 `alert` 에 까닭을 적어 같은 묶음이 다시 안 가게 한다."""
    if sent:
        mark_sent([l for l, _ in sent], "alerted_at")
        with _lock, _conn() as c:
            c.executemany("UPDATE news_items SET alert = ? WHERE link = ?", [(n, l) for l, n in sent])
        _meta(count_key, str(done_today + len(sent)))
    if skip:
        with _lock, _conn() as c:
            c.executemany("UPDATE news_items SET alerted_at = ?, alert = NULL WHERE link = ?",
                          [(int(time.time()), l) for l in skip])
    return len(sent)


def _hold_for_digest(rows):
    """바로 안 보내고 정기 묶음으로 넘긴다 — `alerted_at = -1` · `alert` 는 지금 규칙으로(묶음의 ❗)."""
    if not rows:
        return
    with _lock, _conn() as c:
        c.executemany("UPDATE news_items SET alerted_at = -1, alert = ? WHERE link = ?",
                      [(_alert_name(r), r["link"]) for r in rows])


def _title_words(title):
    """비슷한 속보 가르기용 제목 낱말 — 대괄호 꼬리표 · 따옴표 · 문장부호를 떼고 2글자 이상 · 숫자만 된 것(%, 억 등 붙어도) 뺌."""
    t = re.sub(r"\[[^\]]*\]", " ", title or "")
    out = []
    for w in re.split(r"[^0-9A-Za-z가-힣%]+", t):
        if len(w) >= 2 and not re.fullmatch(r"[0-9.,%]+[가-힣]{0,2}", w):
            out.append(w)
    return out


def _same_word(a, b):
    return a == b or (len(a) >= 2 and len(b) >= 2 and (a.startswith(b) or b.startswith(a)))


def _subjects(words, n=2):
    """제목 앞쪽의 흔하지 않은 낱말 n 개 — 그 기사의 주어(회사 · 기관 · 품목) 자리."""
    return [w for w in words if not any(_same_word(w, c) for c in SIMILAR_COMMON)][:n]


def similar_title(a, b):
    """두 제목이 같은 회사 · 같은 일인가(위 SIMILAR_* 셈).
    같은 회사 — 한쪽 제목의 첫 주어 낱말이 다른 쪽 앞 두 주어 낱말 안에 **글자 그대로** 있어야 한다(「삼성」 ↔ 「삼성전자」 는 다르다) —
    qa 검수(11-18): 「삼성전자 3분기 실적 발표」 ↔ 「SK하이닉스 3분기 실적 발표」 처럼 다른 회사의 같은 갈래 기사가 일 낱말(실적 · 유상증자 · 관세)만으로 묶였다.
    같은 일 — 겹치는 낱말이 SIMILAR_MIN_SHARED 개 이상 · 짧은 쪽의 SIMILAR_RATIO 이상(낱말은 앞이 같으면 같다 — 조사)."""
    if any((w in (a or "")) != (w in (b or "")) for w in SIMILAR_TURN):
        return False                                   # 뒤집는 소식(부인 · 철회 · 취소 …)은 따로 간다
    wa, wb = _title_words(a), _title_words(b)
    if not wa or not wb:
        return False
    sa, sb = _subjects(wa), _subjects(wb)
    if not (sa and sb and (sa[0] in sb or sb[0] in sa)):
        return False
    shared = [w for w in wa if any(_same_word(w, x) for x in wb)]
    return len(shared) >= SIMILAR_MIN_SHARED and len(shared) >= SIMILAR_RATIO * min(len(wa), len(wb))


def _recent_alert_titles():
    """SIMILAR_WINDOW_MIN 분 안에 바로 간 알림 제목들."""
    with _conn() as c:
        return [r[0] for r in c.execute(
            "SELECT title FROM news_items WHERE alert IS NOT NULL AND alerted_at > ?",
            (int(time.time()) - SIMILAR_WINDOW_MIN * 60,))]


def _group_alerted(gid, link):
    """그 묶음에서 다른 기사가 이미 바로 갔나."""
    with _conn() as c:
        return c.execute(
            """SELECT 1 FROM news_items WHERE group_id = ? AND link != ?
               AND alert IS NOT NULL AND alerted_at > 0 LIMIT 1""",
            (gid, link)).fetchone() is not None


def _slot_now(now=None):
    """지금이 어느 정기 발송 시각인가. 아니면 None."""
    now = now or datetime.now(KST)
    for h, m in DIGEST_SLOTS:
        start = now.replace(hour=h, minute=m, second=0, microsecond=0)
        gap = (now - start).total_seconds() / 60
        if 0 <= gap <= SLOT_GRACE_MIN:
            return "%s-%02d%02d" % (now.strftime("%Y%m%d"), h, m)
    return None


def send_digest(force=False, send=None):
    """정기 발송. 같은 시각을 두 번 보내지 않는다.

    ⚠️ **여기도 가려야 한다.** 첫 칸이 **07:30** 이라 `daily.py` 의 `SEND_AT`
    와 **같은 시각**이다. 안 가리면 그 시각에 **데일리 1 + 뉴스 3 = 4통**이
    간다. 「같은 시각을 두 번 안 보낸다」 는 `_meta` 로 막는데,
    **그 `_meta` 도 폴더별 `market.db`** 라 서버마다 따로 센다.

    보내는 것은 **지난 발송 뒤에 쌓인 것**이라 하루가 세 토막으로 이어진다.
    """
    slot = "강제-%d" % int(time.time()) if force else _slot_now()
    if not slot:
        return 0
    if not force and _meta("news_digest_slot") == slot:
        return 0

    rows = unsent_digest()
    if not rows:
        _meta("news_digest_slot", slot)
        return 0
    if send is None:
        return 0                                  # 보내지 않는 서버 — 정리 글도 안 짓는다(Claude 부르기)

    ok, _why = _telegram(slot_digest_text(rows, slot) if TG_NEW else digest_text(rows), send)
    if not ok:
        return 0
    mark_sent([r["link"] for r in rows], "digest_at")
    _meta("news_digest_slot", slot)
    return len(rows)


def slot_digest_text(rows, slot, make=True, now=None):
    """정기 글 (2026-11-18) — 그 시각 이슈 정리(news_brief.slot_brief) · 못 구하면 옛 제목 묶음 + 「정리 못 지음」 한 줄."""
    now = now or datetime.now(KST)
    hm = (int(slot[-4:-2]), int(slot[-2:])) if slot and slot[-4:].isdigit() else (now.hour, now.minute)
    import news_brief
    try:
        data, why = news_brief.slot_brief(hm, now, make=make)
    except Exception as e:
        data, why = None, "못 지음(%s · %s)" % (now.strftime("%H:%M"), type(e).__name__)
    if make:
        news_brief._st["slotFail"] = why             # 미리보기(make=False)는 상태를 안 고친다
    if data and data.get("issues"):
        return news_brief.slot_text(data, hm, now)
    return digest_text(rows, now) + "\n\n(정리 못 지음 — %s · 제목 묶음으로 보냄)" % (why or "까닭 모름")


def preview(days=7):
    """보내지 않는 미리보기 (2026-11-18) — 지금 정기 시각 글 셋(새로 짓지 않음) · 즉시 알림 첫 글 몇 · 지난 days 날 하루 몇 건 갈지.
    아무것도 표시하지 않는다."""
    now = datetime.now(KST)
    rows = unsent_digest()
    slots = {}
    for h, m in DIGEST_SLOTS:
        key = "%s-%02d%02d" % (now.strftime("%Y%m%d"), h, m)
        slots["%02d:%02d" % (h, m)] = slot_digest_text(rows, key, make=False, now=now) if rows else None
    alerts = [alert_text(r, _alert_name(r, True), wait=False) for r in unsent_alerts(flash=True) if _alert_name(r, True)][:5]
    return {"digest": slots, "alerts": alerts, "perDay": alert_counts(days)}


def alert_counts(days=7):
    """지난 days 날 — 날마다 즉시 알림이 몇 건 갈 셈인가(지금 규칙 · 같은 묶음 한 번 · 조용한 시간은 정기 글로).
    {날짜: {"send": 바로 갈 수, "morning": 밤 속보라 07:00 에, "held": 밤 「중요」 라 07:30 정기로, "flash": 그중 속보, "rule": 그중 「중요」 규칙}}."""
    import dart
    since = int(time.time()) - days * 86400
    with _conn() as c:
        rs = c.execute("SELECT title, group_id, at_ts FROM news_items WHERE at_ts >= ? ORDER BY at_ts", (since,)).fetchall()
    out, seen = {}, set()
    for r in rs:
        name = _alert_name(r, True)
        if not name or r["group_id"] in seen:
            continue
        seen.add(r["group_id"])
        d = out.setdefault(datetime.fromtimestamp(r["at_ts"], KST).strftime("%Y-%m-%d"), {"send": 0, "morning": 0, "held": 0, "flash": 0, "rule": 0})
        d[("morning" if name == FLASH_WORD or FLASH_WORD in (r["title"] or "") else "held") if dart.in_quiet(r["at_ts"]) else "send"] += 1
        d["flash" if name == FLASH_WORD else "rule"] += 1
    return out


def digest_text(rows, now=None):
    """정기 묶음 글 (2026-10-12 — 「뉴스들을 정리해서 보내주면 더 좋을 것 같아」).

    **관심종목**(규칙 「모아서」)이 맨 위, 그 밑은 **주제별**로 묶음마다 대표 한 줄 + 「외 N건」.
    주제마다 `DIGEST_PER_TOPIC` 묶음, 전체 `DIGEST_MAX` 줄까지 — 넘는 것은 「외 N묶음」.
    바로 간 것(`alert` 가 남은 것)은 ❗ 를 붙인다.
    """
    now = now or datetime.now(KST)
    sizes = _group_sizes([r["group_id"] for r in rows])
    total = sum(sizes.get(r["group_id"], 1) for r in rows)

    watch, by_topic = [], {}
    for r in sorted(rows, key=lambda x: -(sizes.get(x["group_id"], 1))):   # 기사가 많은 사건 먼저
        if match_alert(r["title"], "모아서"):
            watch.append(r)
        else:
            by_topic.setdefault(r["topic_label"] or "기타", []).append(r)

    def line(r):
        more = sizes.get(r["group_id"], 1) - 1
        return "%s• %s%s\n   %s · %s" % (
            "❗ " if r["alert"] else "", r["title"], " (외 %d건)" % more if more else "",
            r["source"] or "", _hhmm(r["at"]))

    lines = ["📰 뉴스 정리 — %d묶음 · 기사 %d건 (%s 기준)" % (len(rows), total, now.strftime("%m/%d %H:%M"))]
    used, left = 0, 0
    sections = [("⭐ 관심종목", watch)] + sorted(
        (("[%s]" % k, v) for k, v in by_topic.items()), key=lambda kv: -len(kv[1]))
    for title, items in sections:
        if not items:
            continue
        room = min(len(items), DIGEST_PER_TOPIC, DIGEST_MAX - used)
        if room <= 0:
            left += len(items)
            continue
        lines += ["", title] + [line(r) for r in items[:room]]
        used += room
        if len(items) > room:
            lines.append("   … 외 %d묶음" % (len(items) - room))
    if left:
        lines += ["", "… 그 밖 %d묶음" % left]
    return "\n".join(lines)


def _group_sizes(gids):
    """묶음마다 기사 수."""
    if not gids:
        return {}
    with _conn() as c:
        q = ",".join("?" * len(gids))
        return {r["group_id"]: r["n"] for r in c.execute(
            "SELECT group_id, COUNT(*) n FROM news_items WHERE group_id IN (%s) GROUP BY group_id" % q,
            list(gids))}


# ---------------------------------------------------------------- 루프

def collect_once(send=None):
    """한 바퀴 — 받아서 쌓고, 중요한 것은 바로 보내고, 시각이 되면 묶어 보낸다.

    **받아서 쌓는 것은 어느 폴더에서나 한다** — 그 폴더 화면이 읽어야 한다.
    **`send` 로 가리는 것은 발송 둘뿐이다.**
    """
    import news
    got = news.fetch_issues()
    added = store(got.get("rows") or [])
    purge_old()
    ko_backfill()
    alerted = send_alerts(send)
    digested = send_digest(send=send)
    return {"added": len(added), "alerted": alerted, "digested": digested}


def start_collector(send=None):
    """서버가 뜰 때 부른다. **주말·밤에도 돈다** — dart 의 공시 폴러와 다른 점이다.

    `send` 는 **부르는 쪽이 포트를 보고** 준다. 안 주면 **쌓기만 하고
    안 보낸다.** 데일리(`daily.start_daily` 의 `send=`)와 같은 꼴이다.

    공시는 평일 07~20 에만 접수되지만 뉴스는 그렇지 않고, 정기 발송이 22시에도
    있어서 그 시간대에 루프가 자고 있으면 안 된다.
    """
    init()

    def loop():
        time.sleep(8)        # 서버가 막 뜬 참이라 잠깐 기다렸다 시작한다
        while True:
            try:
                r = collect_once(send)
                if r["added"] or r["alerted"] or r["digested"]:
                    print("  [뉴스] 새 %d건 · 즉시알림 %d · 정기 %d"
                          % (r["added"], r["alerted"], r["digested"]))
            except Exception as e:
                print("  [뉴스] 예기치 못한 오류: %s" % type(e).__name__)
            time.sleep(COLLECT_INTERVAL)

    threading.Thread(target=loop, daemon=True, name="news-collector").start()
    return True
