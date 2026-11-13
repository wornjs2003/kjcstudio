# -*- coding: utf-8 -*-
"""뉴스 정리 글 둘 — 아침 정리(/api/news/brief) · 속보 정리(/api/news/flash) (2026-11-13).

재권님 — 「아침 7시로 하고 속보는 그 아래로 또 만들어야 할거같아」 · 「속보도 읽고 정리하는거 실시간으로 갱신되도록 해줘」(시황분석 창 12:0x ·
작업우선순위 배분) → 착수 안 「뉴스 정리 둘」 에 「응 커밋해」(개발2 창 12:1x).

    아침 정리   매일 BRIEF_AT(07:00) 한 번 — news_store.issues() 의 뜨거운 이슈 BRIEF_IN 개와 기사 제목으로 맥미니 claude 를 한 번 불러
                「주요 이슈 BRIEF_PICK 개 · 이슈마다 두세 문장」 을 짓는다. 모양은 Insight 가 쓰던 company-setup/data/news-brief.json 그대로
                (writtenAt · range · by · issues[{name · text · articles[{title · source · at · link}]}]).
                서버가 07:00 뒤에 떴고 그날 글이 없으면 뜰 때 한 번 짓는다.
    속보 정리   제목에 「속보」 가 든 기사가 새로 쌓이면(FLASH_TICK 마다 봄) 그 기사 · 같은 묶음 기사 제목으로 한두 문장(무슨 일 · 왜 중요한가)을 붙인다.
                주소는 지난 FLASH_HOURS 시간 속보 — 새것부터 · 정리 전이면 summary null.
    이슈 분석   뜨거운 이슈 위 ANALYZE_TOP 개마다 묶인 기사 본문을 claude 가 WebFetch 로 읽고(ANALYZE_LINKS 건까지) 한두 문단 분석
                (무슨 일 · 왜 중요한가 · 시장에 무엇) — /api/news/hot 의 issues[].analysis · analyzedAt. **본문은 우리 쪽에 저장하지 않는다**(언론사 약관 자리 ·
                재권님 「나」 11-13 12:1x — 본문까지 읽되 저장 안 함). 처음 · 기사가 ANALYZE_REGROW 건 넘게 늘었을 때만 다시 · ANALYZE_TICK 마다 한 건.
                잰 값(12:1x 한 건) — 30초 · 0.12달러(여쭐 때 어림 0.03 의 네 배) → 한도로 하루 약 10~15번 · 약 1.5달러
    공통        쓰기 되는 서버(8765)만 짓는다 — 메인 · 세션 서버는 DB 에 남은 것을 읽는다. 알림은 없다.
                못 지으면 지난 글을 그대로 두고 meta.failed 에 「못 지음(시각 · 까닭)」 · 실패 뒤 RETRY_SEC 쉰다.
                글은 기사 제목 안의 말로만 쓰게 시킨다 · 응답 by 칸에 「Claude 가 지음」.
    비용        잰 값(11-13 12:0x · 이슈 15개 · 제목 8개씩) — Opus 13초 0.07달러 · 속보 한 건은 어림 0.03달러 안팎
"""
import json
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone

import marketdb
import news_store
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))
MODEL = "claude-opus-5-5"     # 오른쪽 Claude 창과 같은 모델(claude_chat.MODEL · 재권님 11-03 「opus 5.5」)
BRIEF_AT = (7, 0)             # 아침 정리 짓는 시각
BRIEF_IN = 15                 # 넣는 이슈 수(news_store.issues 줄 세운 위에서부터)
BRIEF_TITLES = 8              # 이슈마다 넣는 기사 제목 수
BRIEF_PICK = 5                # 골라 쓰는 이슈 수
BRIEF_ARTICLES = 8            # 이슈마다 붙여 내는 기사 수
ANALYZE_TOP = 10              # 분석하는 이슈 수(줄 세운 위에서부터)
ANALYZE_REGROW = 3            # 기사가 이만큼 늘면 다시 분석
ANALYZE_TICK = 600            # 분석 한 건 간격(초) — 몰아 부르지 않게
ANALYZE_LINKS = 3             # 이슈마다 읽는 기사 본문 수
FLASH_WORD = "속보"
FLASH_HOURS = 24              # 속보 주소가 내는 기간
FLASH_TICK = 60               # 새 속보를 보는 간격(초)
FLASH_PER_TICK = 5            # 한 바퀴에 정리하는 속보 수(한꺼번에 몰려도 몇 건씩)
RETRY_SEC = 600               # 못 지으면 이만큼 쉬고 다시
TIMEOUT = 180
BUDGET_USD = "1"              # 한 번 부를 때 비용 상한(달러)
BY = "Claude(Opus)가 서버에 쌓인 기사 제목으로 지음"

_st = {"briefFail": None, "briefFailAt": 0.0, "flashFail": None, "flashFailAt": 0.0, "calls": 0,
       "anFail": None, "anAt": 0.0}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS news_brief (day TEXT PRIMARY KEY, data TEXT NOT NULL, at TEXT);
CREATE TABLE IF NOT EXISTS news_flash (link TEXT PRIMARY KEY, summary TEXT NOT NULL, at TEXT);
CREATE TABLE IF NOT EXISTS news_analysis (issue TEXT PRIMARY KEY, articles INTEGER, analysis TEXT NOT NULL, at TEXT);
"""


def _now():
    return datetime.now(KST)


def _conn():
    return marketdb.connect(timeout=10)


def _claude(prompt, tools=""):
    """맥미니 claude 를 한 번 — 결과 글. 도구는 tools 만(기본 없음 · 분석은 WebFetch) · 기록 안 남김(claude_chat 과 같은 길)."""
    import claude_chat
    extra = ["--allowedTools", tools] if tools else []
    r = subprocess.run([claude_chat._claude(), "-p", "--model", MODEL, "--tools", tools, *extra, "--no-session-persistence",
                        "--settings", claude_chat.SETTINGS, "--output-format", "json", "--max-budget-usd", BUDGET_USD],
                       input=prompt, capture_output=True, text=True, timeout=TIMEOUT, cwd="/tmp")
    _st["calls"] += 1
    try:
        out = json.loads(r.stdout)
    except ValueError:
        raise RuntimeError("claude 종료 %d · 글이 아닌 응답" % r.returncode)
    if r.returncode != 0 or out.get("is_error"):
        raise RuntimeError("claude 종료 %d" % r.returncode)
    return (out.get("result") or "").strip()


def _json_part(text, open_ch="[", close_ch="]"):
    return json.loads(text[text.find(open_ch): text.rfind(close_ch) + 1])


# ---------------------------------------------------------------- 아침 정리
def make_brief(now=None):
    """지금 이슈로 아침 정리 하나를 지어 남긴다 → 글(dict). 못 지으면 RuntimeError."""
    now = now or _now()
    hot = news_store.issues()
    iss = hot["issues"][:BRIEF_IN]
    if not iss:
        raise RuntimeError("이슈 없음")
    src = [{"i": n, "name": x["name"], "presses": x["presses"], "articles": x["articles"],
            "titles": [{"title": a["title"], "source": a["source"], "at": a["at"]} for a in x["items"][:BRIEF_TITLES]]}
           for n, x in enumerate(iss)]
    prompt = ("아래는 서버가 쌓은 기사를 같은 사건끼리 묶은 이슈다(i 번호). 가장 중요한 이슈 %d개를 골라 이슈마다 한 줄 이름(name)과 "
              "두세 문장 요약(text)을 한국어로 써라. 기사 제목에 없는 사실 · 숫자 · 전망은 쓰지 마라. "
              "JSON 배열 [{\"pick\": i, \"name\": ..., \"text\": ...}] 하나만 내라.\n" % BRIEF_PICK) + json.dumps(src, ensure_ascii=False)
    got = _json_part(_claude(prompt))
    out = []
    for g in got[:BRIEF_PICK]:
        i = g.get("pick")
        if not isinstance(i, int) or not (0 <= i < len(iss)) or not g.get("text"):
            continue
        out.append({"name": str(g.get("name") or iss[i]["name"]), "text": str(g["text"]), "issue": iss[i]["id"],
                    "articles": [{"title": a["title"], "source": a["source"], "at": a["at"], "link": a["link"]}
                                 for a in iss[i]["items"][:BRIEF_ARTICLES]]})
    if not out:
        raise RuntimeError("고른 이슈가 없음")
    feeds = hot["meta"].get("feedNations") or []
    data = {"writtenAt": now.isoformat(timespec="seconds"),
            "range": "서버가 쌓은 기사 · 지난 %d시간 · 받는 곳 나라 %s" % (hot["meta"]["windowH"], " · ".join(feeds) or "모름"),
            "by": BY, "issues": out}
    with _conn() as c:
        c.executescript(_SCHEMA)
        c.execute("INSERT OR REPLACE INTO news_brief VALUES (?,?,?)", (now.strftime("%Y%m%d"), json.dumps(data, ensure_ascii=False),
                                                                        now.strftime("%H:%M:%S")))
    return data


def brief():
    """주소 /api/news/brief — {data(마지막 글 · 없으면 None), meta}."""
    data, day = None, None
    try:
        with _conn() as c:
            r = c.execute("SELECT day, data FROM news_brief ORDER BY day DESC LIMIT 1").fetchone()
        if r:
            day, data = r[0], json.loads(r[1])
    except Exception:
        pass                                    # 표가 아직 없다(8765 가 처음 짓기 전) — 글 없음
    return {"data": data, "meta": {"day": day, "at": "%02d:%02d" % BRIEF_AT, "by": BY,
                                   "failed": _st["briefFail"], "today": day == _now().strftime("%Y%m%d")}}


# ---------------------------------------------------------------- 속보 정리
def _flash_rows(hours=FLASH_HOURS):
    since = int(time.time()) - hours * 3600
    with _conn() as c:
        return c.execute("SELECT * FROM news_items WHERE at_ts >= ? AND title LIKE ? ORDER BY at_ts DESC",
                         (since, "%" + FLASH_WORD + "%")).fetchall()


def flash():
    """주소 /api/news/flash — 지난 FLASH_HOURS 시간 속보 · 새것부터 · 정리 전이면 summary null."""
    rows = _flash_rows()
    sums = {}
    try:
        with _conn() as c:
            links = [r["link"] for r in rows]
            if links:
                q = "SELECT link, summary, at FROM news_flash WHERE link IN (%s)" % ",".join("?" * len(links))
                sums = {l: (s, a) for l, s, a in c.execute(q, links)}
    except Exception:
        pass
    items = [{"title": r["title"], "source": r["source"], "at": r["at"], "link": r["link"],
              "summary": (sums.get(r["link"]) or (None, None))[0], "summarizedAt": (sums.get(r["link"]) or (None, None))[1]}
             for r in rows]
    return {"items": items, "meta": {"hours": FLASH_HOURS, "word": FLASH_WORD, "by": BY, "failed": _st["flashFail"]}}


def flash_once():
    """정리 안 된 속보를 몇 건 정리해 남긴다 → 남긴 수."""
    rows = _flash_rows()
    with _conn() as c:
        c.executescript(_SCHEMA)
        done = {l for (l,) in c.execute("SELECT link FROM news_flash")}
    todo = [r for r in rows if r["link"] not in done][:FLASH_PER_TICK]
    n = 0
    for r in todo:
        with _conn() as c:
            same = [t for (t,) in c.execute("SELECT title FROM news_items WHERE group_id = ? AND link != ? LIMIT 6",
                                            (r["group_id"], r["link"]))]
        prompt = ("아래 속보 제목(같은 사건 다른 기사 제목도 함께)을 읽고 한국어 한두 문장으로 정리하라 — 무슨 일인지 · 왜 중요한지. "
                  "제목에 없는 사실 · 숫자 · 전망은 쓰지 마라. 정리 글만 내라.\n속보: %s\n같은 사건: %s"
                  % (r["title"], json.dumps(same, ensure_ascii=False)))
        text = _claude(prompt).strip().strip('"')
        if not text:
            raise RuntimeError("빈 정리")
        with _conn() as c:
            c.execute("INSERT OR REPLACE INTO news_flash VALUES (?,?,?)", (r["link"], text, _now().strftime("%H:%M:%S")))
        n += 1
    return n


# ---------------------------------------------------------------- 이슈 분석
def analyses(ids):
    """{이슈 id: (분석, 시각)} — 표가 없으면 빈 값."""
    ids = [i for i in ids if i]
    if not ids:
        return {}
    try:
        with _conn() as c:
            q = "SELECT issue, analysis, at FROM news_analysis WHERE issue IN (%s)" % ",".join("?" * len(ids))
            return {i: (a, t) for i, a, t in c.execute(q, ids)}
    except Exception:
        return {}


def analyze_once():
    """분석이 없거나 기사가 늘어난 이슈 하나를 분석해 남긴다 → 이슈 id 또는 None."""
    iss = news_store.issues()["issues"][:ANALYZE_TOP]
    with _conn() as c:
        c.executescript(_SCHEMA)
        have = {i: n for i, n in c.execute("SELECT issue, articles FROM news_analysis")}
    x = next((x for x in iss if x["id"] not in have or x["articles"] - (have[x["id"]] or 0) >= ANALYZE_REGROW), None)
    if x is None:
        return None
    arts = [{"title": a["title"], "source": a["source"], "at": a["at"], "link": a["link"]} for a in x["items"][:ANALYZE_LINKS]]
    prompt = ("아래는 같은 사건을 다룬 기사들이다. 링크의 기사 본문을 WebFetch 로 읽고 한국어 한두 문단으로 분석하라 — 무슨 일인지 · 왜 중요한지 · "
              "시장(주식 · 섹터)에 무엇을 뜻하는지. 기사에 없는 사실 · 숫자는 쓰지 말고, 추측은 「~로 보인다」 로 갈라 써라. "
              "기사 본문을 그대로 옮겨 적지 마라. 분석 글만 내라.\n이슈: %s\n기사: %s" % (x["name"], json.dumps(arts, ensure_ascii=False)))
    text = _claude(prompt, tools="WebFetch")
    if not text:
        raise RuntimeError("빈 분석")
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO news_analysis VALUES (?,?,?,?)", (x["id"], x["articles"], text, _now().strftime("%Y-%m-%d %H:%M")))
    return x["id"]


# ---------------------------------------------------------------- 돌리기
def start():
    """쓰는 서버(8765)가 뜰 때 한 번 — 아침 정리 · 속보 정리 바퀴."""
    if not marketdb.writable():
        return False
    with _conn() as c:
        c.executescript(_SCHEMA)

    def loop():
        time.sleep(60)                              # 뉴스 수집이 먼저 한 바퀴 돌게
        while True:
            now = _now()
            day = now.strftime("%Y%m%d")
            if (now.hour, now.minute) >= BRIEF_AT and time.time() - _st["briefFailAt"] >= RETRY_SEC:
                b = brief()
                if b["meta"]["day"] != day:
                    try:
                        d = make_brief(now)
                        _st["briefFail"] = None
                        print("  [뉴스 정리] %s 아침 정리 %d 이슈" % (day, len(d["issues"])), flush=True)
                    except Exception as e:
                        _st["briefFailAt"] = time.time()
                        _st["briefFail"] = "못 지음(%s · %s)" % (now.strftime("%H:%M"), safe_message(e, 100))
            if time.time() - _st["anAt"] >= ANALYZE_TICK:
                _st["anAt"] = time.time()                   # 성공 · 실패 모두 다음 한 건까지 ANALYZE_TICK 쉰다
                try:
                    if analyze_once():
                        _st["anFail"] = None
                except Exception as e:
                    _st["anFail"] = "못 지음(%s · %s)" % (now.strftime("%H:%M"), safe_message(e, 100))
            if time.time() - _st["flashFailAt"] >= RETRY_SEC:
                try:
                    n = flash_once()
                    if n:
                        _st["flashFail"] = None
                        print("  [뉴스 정리] 속보 %d건 정리" % n, flush=True)
                except Exception as e:
                    _st["flashFailAt"] = time.time()
                    _st["flashFail"] = "못 지음(%s · %s)" % (now.strftime("%H:%M"), safe_message(e, 100))
            time.sleep(FLASH_TICK)

    threading.Thread(target=loop, daemon=True, name="news-brief").start()
    return True
