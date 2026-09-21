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
import time
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

HERE = os.path.dirname(os.path.abspath(__file__))
HOLDINGS_DIR = os.path.dirname(HERE)
DB_PATH = os.path.join(HOLDINGS_DIR, "market.db")
ALERTS_PATH = os.path.join(HOLDINGS_DIR, "data", "news-alerts.json")

# 얼마나 자주 받아 쌓나. news.py 의 캐시(180초)보다 길면 캐시가 소용없고,
# 짧으면 같은 것을 되풀이해 받는다. **주말·밤에도 돈다** (2026-09-21 지시).
COLLECT_INTERVAL = 300

# 같은 사건으로 묶을 때 견주는 범위. 이보다 오래된 기사와는 안 묶는다 —
# 며칠 지나 같은 낱말이 나오는 것은 대개 다른 사건이다.
GROUP_WINDOW_H = 24

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
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


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
          alerted_at  INTEGER,            -- 즉시 알림을 보낸 시각
          digest_at   INTEGER,            -- 정기 묶음에 실어 보낸 시각
          seen_at     INTEGER             -- 우리가 처음 받은 시각
        );
        CREATE INDEX IF NOT EXISTS ix_news_at   ON news_items(at_ts DESC);
        CREATE INDEX IF NOT EXISTS ix_news_grp  ON news_items(group_id);
        CREATE INDEX IF NOT EXISTS ix_news_sent ON news_items(digest_at);
        """)


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


def match_alert(title):
    """제목이 어떤 「중요」 규칙에 걸리나. 안 걸리면 None."""
    for rule in (load_alerts().get("즉시알림") or []):
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
                 group_id, is_lead, alert, seen_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                      (link, title, row.get("source"), row.get("topic"),
                       row.get("topicLabel"), at, at_ts, gid, is_lead, alert, now))
            added.append({"link": link, "title": title, "at": at,
                          "source": row.get("source"), "topic": row.get("topic"),
                          "topicLabel": row.get("topicLabel"),
                          "group": gid, "alert": alert})
    return added


# ---------------------------------------------------------------- 읽기

def groups(hours=24, limit=80):
    """쌓인 것을 **묶음 단위**로 돌려준다. 화면이 읽는 모양이다.

    한 묶음은 대표 기사 하나와 「외 N건」이다. 네이버 종목 뉴스가 같은 모양이라
    화면에서 두 칸이 같아 보인다.
    """
    since = int(time.time()) - hours * 3600
    out = {}
    with _conn() as c:
        for r in c.execute(
                "SELECT * FROM news_items WHERE at_ts >= ? ORDER BY at_ts DESC",
                (since,)):
            g = out.setdefault(r["group_id"], {
                "group": r["group_id"], "title": r["title"], "link": r["link"],
                "at": r["at"], "source": r["source"], "topic": r["topic"],
                "topicLabel": r["topic_label"], "alert": r["alert"],
                "more": 0, "others": [],
            })
            if g["link"] == r["link"]:
                continue
            g["more"] += 1
            if len(g["others"]) < 4:
                g["others"].append({"title": r["title"], "link": r["link"],
                                    "source": r["source"], "at": r["at"]})
            # 묶음 안에 중요한 것이 있으면 묶음도 중요로 친다
            if r["alert"] and not g["alert"]:
                g["alert"] = r["alert"]
    rows = sorted(out.values(), key=lambda g: g["at"] or "", reverse=True)
    return rows[:limit]


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
    with _conn() as c:
        return [dict(r) for r in c.execute(
            """SELECT * FROM news_items
               WHERE digest_at IS NULL AND is_lead = 1
               ORDER BY at_ts DESC LIMIT ?""", (limit,))]


def unsent_alerts(limit=20):
    """즉시 알림을 아직 안 보낸 「중요」 기사."""
    with _conn() as c:
        return [dict(r) for r in c.execute(
            """SELECT * FROM news_items
               WHERE alert IS NOT NULL AND alerted_at IS NULL
               ORDER BY at_ts DESC LIMIT ?""", (limit,))]


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
DIGEST_SLOTS = [(7, 30), (13, 30), (22, 0)]

# 그 시각을 놓쳤을 때 몇 분까지 따라잡아 보낼 것인가. 서버가 잠깐 꺼져 있었다고
# 하루치를 통째로 건너뛰면 안 된다.
SLOT_GRACE_MIN = 90

# 한 번에 보낼 줄 수. 그보다 많으면 「외 N건」으로 줄인다 — 텔레그램은
# 한 메시지가 길면 잘린다.
DIGEST_MAX = 15

# 즉시 알림은 **이보다 오래된 기사에는 보내지 않는다.**
#
# 텔레그램이 꺼져 있는 동안에도 쌓이기 때문에, 나중에 설정을 켜는 순간
# 며칠치 「중요」가 한꺼번에 날아간다. dart.py 가 `quiet_first_run` 으로
# 막는 것과 같은 자리다 — 지난 것은 **보내지 않고 보낸 것으로 표시**해
# 조용히 넘긴다. 정기 발송에는 그대로 들어가므로 사라지지 않는다.
ALERT_MAX_AGE_H = 3


def _telegram(text):
    """dart.py 의 발송을 빌려 쓴다. 설정이 없으면 (False, 이유) 가 온다."""
    import dart
    return dart.telegram_send(text)


def _meta(key, value=None):
    import dart
    if value is None:
        return dart._meta_get(key)
    dart._meta_set(key, value)
    return value


def _hhmm(at):
    return (at or "")[11:16]


def send_alerts():
    """「중요」로 걸린 것을 바로 보낸다. 보낸 건수를 돌려준다."""
    rows = unsent_alerts()
    if not rows:
        return 0

    # 오래된 것은 조용히 넘긴다 (위 ALERT_MAX_AGE_H 참고)
    cutoff = int(time.time()) - ALERT_MAX_AGE_H * 3600
    stale = [r["link"] for r in rows if (r["at_ts"] or 0) < cutoff]
    if stale:
        mark_sent(stale, "alerted_at")
    rows = [r for r in rows if (r["at_ts"] or 0) >= cutoff]

    sent = []
    for r in rows:
        text = "[%s] %s\n%s · %s\n%s" % (
            r["alert"], r["title"], r["source"] or "", _hhmm(r["at"]), r["link"])
        ok, _why = _telegram(text)
        if not ok:
            break            # 설정이 없거나 막혔다. 다음 바퀴에 다시 본다
        sent.append(r["link"])
        time.sleep(0.4)      # 텔레그램 초당 제한
    if sent:
        mark_sent(sent, "alerted_at")
    return len(sent)


def _slot_now(now=None):
    """지금이 어느 정기 발송 시각인가. 아니면 None."""
    now = now or datetime.now(KST)
    for h, m in DIGEST_SLOTS:
        start = now.replace(hour=h, minute=m, second=0, microsecond=0)
        gap = (now - start).total_seconds() / 60
        if 0 <= gap <= SLOT_GRACE_MIN:
            return "%s-%02d%02d" % (now.strftime("%Y%m%d"), h, m)
    return None


def send_digest(force=False):
    """정기 발송. 같은 시각을 두 번 보내지 않는다.

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

    head = "📰 쌓인 뉴스 %d건 (%s 기준)" % (len(rows), datetime.now(KST).strftime("%m/%d %H:%M"))
    lines = [head, ""]
    for r in rows[:DIGEST_MAX]:
        mark = "❗ " if r["alert"] else ""
        lines.append("%s[%s] %s\n   %s · %s" % (
            mark, r["topic_label"] or "기타", r["title"],
            r["source"] or "", _hhmm(r["at"])))
    if len(rows) > DIGEST_MAX:
        lines.append("")
        lines.append("… 외 %d건" % (len(rows) - DIGEST_MAX))

    ok, _why = _telegram("\n".join(lines))
    if not ok:
        return 0
    mark_sent([r["link"] for r in rows], "digest_at")
    _meta("news_digest_slot", slot)
    return len(rows)


# ---------------------------------------------------------------- 루프

def collect_once():
    """한 바퀴 — 받아서 쌓고, 중요한 것은 바로 보내고, 시각이 되면 묶어 보낸다."""
    import news
    got = news.fetch_issues()
    added = store(got.get("rows") or [])
    alerted = send_alerts()
    digested = send_digest()
    return {"added": len(added), "alerted": alerted, "digested": digested}


def start_collector():
    """서버가 뜰 때 부른다. **주말·밤에도 돈다** — dart 의 공시 폴러와 다른 점이다.

    공시는 평일 07~20 에만 접수되지만 뉴스는 그렇지 않고, 정기 발송이 22시에도
    있어서 그 시간대에 루프가 자고 있으면 안 된다.
    """
    init()

    def loop():
        time.sleep(8)        # 서버가 막 뜬 참이라 잠깐 기다렸다 시작한다
        while True:
            try:
                r = collect_once()
                if r["added"] or r["alerted"] or r["digested"]:
                    print("  [뉴스] 새 %d건 · 즉시알림 %d · 정기 %d"
                          % (r["added"], r["alerted"], r["digested"]))
            except Exception as e:
                print("  [뉴스] 예기치 못한 오류: %s" % type(e).__name__)
            time.sleep(COLLECT_INTERVAL)

    threading.Thread(target=loop, daemon=True, name="news-collector").start()
    return True
