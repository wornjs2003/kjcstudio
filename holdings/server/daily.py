"""데일리분석 문안을 만든다.

**브라우저에 있던 것을 여기로 옮겼다** (2026-09-22 지시 — 「항상 켜놓는
서버가 있을 거야 거기에 맞춰서 해」). 07:30 에 저장하고 텔레그램으로
보내야 하는데, 그 시각에 브라우저가 열려 있다는 보장이 없다.

    전    `js/components/daily-view.js` 의 `buildTelegram()` 73줄
    후    **여기 한 곳.** 화면은 서버가 만든 글을 받아 보여주기만 한다

**복제가 아니라 이동이다.** JS 쪽은 지웠다 — 두 곳에 두면 한쪽만 고쳐도
화면은 멀쩡해 보이고 폰으로 가는 글만 갈린다. 그것을 잡을 검사는 만들 수
없다. 문안은 **값이 아니라 문장**이라 「같다/다르다」 로 판정하면 글을
못 고치게 된다 (CLAUDE.md 「합칠 수 있으면 대조 도구보다 먼저 합친다」).

── 값을 모으지 않는다 ──

이 파일은 **조립만** 한다. 지수·업종·뉴스·공시는 부르는 쪽이 넘긴다.
`kis_proxy` 를 여기서 import 하면 순환이 된다 — 그쪽이 이 파일을 부르기
때문이다. `dart.py` 의 `fetch_moves(kis_get, cfg)` 가 같은 꼴이다.
"""

import io
import json
import re
import os
import sys
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CAL_PATH = os.path.join(HERE, "..", "data", "market-calendar.json")

# 지수 줄에 쓸 것. JS 의 `INDEX_ROWS` 와 **이름까지 같아야** 문안이 같아진다.
#
# **세 번째 칸이 없으면 둘이 빠진다.** `/api/kis/indices` 가 주는 code 는
# `NASDAQ` · `USDKRW` 인데 우리가 부르는 이름은 `COMP` · `USD` 다. JS 의
# `pickIndex` 가 **code 로 못 찾으면 이름을 정규식으로** 찾는데, 옮길 때
# 그것을 빠뜨려 처음에 「해외」 줄에 S&P 500 하나만 나왔다 (2026-09-22 실측).
INDEX_ROWS = [
    ("KOSPI", "KOSPI", None),
    ("KOSDAQ", "KOSDAQ", None),
    ("SPX", "S&P 500", r"S&P"),
    ("COMP", "나스닥 종합", r"나스닥"),
    ("USD", "달러 · 원", r"USD|달러"),
]
HOME_CODES = ["KOSPI", "KOSDAQ"]
AWAY_CODES = ["SPX", "COMP", "USD"]

# 제목이 이보다 길면 자른다. JS 와 같은 값이어야 한다.
TITLE_MAX = 34
NEWS_MAX = 3            # 주제가 겹치지 않는 것으로 셋까지
SECTOR_TOP = 3


# ── 숫자 표기 ──
# **JS 와 글자까지 같아야 한다.** `toLocaleString('ko-KR', {소수 2자리})` 가
# 파이썬의 `f"{v:,.2f}"` 와 같은 결과를 낸다 — 천단위 쉼표와 소수 두 자리다.

def num(v, digits=2):
    """1234.5 → '1,234.50'. 값이 없으면 '—'."""
    if v is None:
        return "—"
    try:
        return f"{float(v):,.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def pct(v):
    """0.6 → '+0.60%' · -0.6 → '−0.60%' (빼기표는 U+2212, JS 와 같다)."""
    if v is None:
        return ""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return ""
    mark = "+" if n > 0 else ("−" if n < 0 else "")
    return f"{mark}{num(abs(n), 2)}%"


def today_label(now=None):
    """'9월 22일 (월)' — JS 의 todayLabel 과 같은 모양."""
    d = now or datetime.now()
    week = "일월화수목금토"[(d.weekday() + 1) % 7]
    return f"{d.month}월 {d.day}일 ({week})"


# ── 조각 ──

def _pick(code, pat, indices):
    """code 로 먼저 찾고, 없으면 **이름을 정규식으로** 찾는다.
    JS 의 `pickIndex` 와 같은 순서다 — 순서가 다르면 `나스닥 종합` 대신
    `나스닥100` 을 집을 수 있다."""
    for x in indices:
        if x.get("code") == code:
            return x
    if not pat:
        return None
    rx = re.compile(pat, re.I)
    for x in indices:
        if rx.search(x.get("name") or ""):
            return x
    return None


def _index_line(code, label, pat, indices):
    x = _pick(code, pat, indices)
    if not x or x.get("value") is None:
        return None
    ch = x.get("change")
    try:
        c = float(ch) if ch is not None else 0.0
    except (TypeError, ValueError):
        c = 0.0
    mark = "▲" if c > 0 else ("▼" if c < 0 else "—")
    return f"{label} {num(x.get('value'))} {mark}{num(abs(float(x.get('changePct') or 0)), 2)}%"


def _today_events(schedule, now=None):
    """오늘 것과 진행 중인 것. `schedule` 은 [{when, kind, title, note, ongoing}]."""
    d0 = (now or datetime.now()).date()
    out = []
    for e in schedule or []:
        if e.get("ongoing"):
            out.append(e)
            continue
        w = e.get("when")
        if isinstance(w, datetime) and w.date() == d0:
            out.append(e)
    return out


def load_calendar():
    """`data/market-calendar.json` 을 읽는다. 화면은 `./data/` 로 받는데
    서버는 같은 파일을 직접 연다."""
    try:
        with io.open(CAL_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def calendar_today(now=None):
    """오늘 일정 + **여러 날에 걸쳐 오늘을 지나는 것**.

    뒤엣것이 있어야 어제 시작해 오늘까지 가는 FOMC 같은 것이 안 빠진다.
    JS 에서는 `daily-view.js` 가 따로 줍고 있었다 (`schedule.js` 가
    `endDate` 를 안 봐서다).
    """
    cal = load_calendar()
    if not cal:
        return []
    d0 = (now or datetime.now()).date()
    out = []
    for e in cal.get("events") or []:
        try:
            start = datetime.strptime(e.get("date", ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        end = start
        if e.get("endDate"):
            try:
                end = datetime.strptime(e["endDate"], "%Y-%m-%d").date()
            except ValueError:
                end = start
        if not (start <= d0 <= end):
            continue
        out.append({
            "when": datetime.combine(d0, datetime.min.time()),
            "kind": e.get("kind") or "일정",
            "title": e.get("title") or "",
            "note": e.get("note") or "",
            "ongoing": start < d0,
        })
    return out


def sector_sides(sectors):
    """오름·내림으로 가른다. **`pct` 가 없는 것은 뺀다** — 섞여 오는 날이 있다."""
    ok = [s for s in (sectors or []) if s.get("pct") is not None]
    ok.sort(key=lambda s: s["pct"], reverse=True)
    up = [s for s in ok if s["pct"] > 0]
    down = [s for s in ok if s["pct"] < 0]
    down.reverse()          # 많이 내린 것부터
    return up, down


# ── 문안 ──

def build_telegram(indices=None, sectors=None, issues=None, schedule=None, now=None):
    """폰으로 가는 글을 만든다. `buildTelegram()` 을 그대로 옮긴 것이다."""
    L = [f"📊 데일리분석 · {today_label(now)}"]

    ev = _today_events(schedule, now)
    if ev:
        L += ["", "오늘 일정"]
        # 실적 발표는 하루에 여러 건이 몰린다. 다섯 줄을 그대로 적으면 폰에서
        # 문안이 화면 하나를 넘어간다. 시장 전체가 보는 것만 줄로 적고
        # 나머지는 개수로 묶는다.
        big = [e for e in ev if e.get("kind") != "실적"]
        ir = [e for e in ev if e.get("kind") == "실적"]
        for e in big:
            L.append(f"· {e.get('title', '')}{' (진행 중)' if e.get('ongoing') else ''}")
            if e.get("note"):
                L.append(f"  → {e['note']}")
        if ir:
            names = [e.get("title", "").replace(" 기업설명회", "").rstrip()
                     for e in ir[:2]]
            tail = f" 외 {len(ir) - len(names)}" if len(ir) > len(names) else ""
            L.append(f"· 기업설명회 {len(ir)}건 — {' · '.join(names)}{tail}")

    rows = {c: (label, pat) for c, label, pat in INDEX_ROWS}
    ix = list(indices or [])

    home = [ln for ln in (_index_line(c, *rows[c], ix) for c in HOME_CODES) if ln]
    if home:
        L += ["", "국내"] + home
        k = _pick("KOSPI", None, ix)
        if k and (k.get("up") or k.get("down")):
            L.append(f"상승 {k.get('up')} · 하락 {k.get('down')}")

    away = [ln for ln in (_index_line(c, *rows[c], ix) for c in AWAY_CODES) if ln]
    if away:
        L += ["", "해외 (현지 마감)"] + away

    if issues:
        L += ["", "오늘 뉴스"]
        seen = set()
        n = 0
        for it in issues:
            key = it.get("topic") or ""
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            t = it.get("title") or ""
            if len(t) > TITLE_MAX:
                t = t[:TITLE_MAX - 1] + "…"
            lab = f"{it['topicLabel']} — " if it.get("topicLabel") else ""
            more = f" (외 {it['more']}건)" if it.get("more") else ""
            L.append(f"· {lab}{t}{more}")
            n += 1
            if n >= NEWS_MAX:
                break

    if sectors:
        up, down = sector_sides(sectors)
        one = lambda s: f"{s.get('name')} {pct(s.get('pct'))}"
        L += ["", "주도 섹터 (국내)"]
        if up:
            L.append("· 오름 — " + " · ".join(one(s) for s in up[:SECTOR_TOP]))
        if down:
            L.append("· 내림 — " + " · ".join(one(s) for s in down[:SECTOR_TOP]))

    # 화면에는 빨간 자국으로 남아 있는 칸들이다. 문안에서 통째로 빼면 폰에서는
    # 무엇이 빠졌는지 알 수 없다. 붙으면 이 줄을 지운다.
    L += ["", "연결 예정", "· 미국 업종", "· 야간선물 · 다우존스"]
    L += ["", "전문 보기 › thekjcstudio.com/holdings/daily.html"]
    return "\n".join(L)


# ──────────────────────────────────────────────────────────────
# 아침 07:30 — 저장하고 보낸다
# ──────────────────────────────────────────────────────────────
#
# 재권님 지시 — 「데일리는 아침 7시반에 저장하고 그걸 요약한 텔레그램용을
# 나한테 보내줘」 · 「항상 켜놓는 서버가 있을 거야 거기에 맞춰서 해」.
#
# **브라우저에 안 기댄다.** 그 시각에 화면이 열려 있다는 보장이 없다.
#
# ── 왜 여기에 루프가 있나 ──
#
# `kis_proxy.py` 는 여러 세션이 함께 쓰는 파일이라, 거기에 판단과 조립을
# 넣으면 부딪힌다. **부르는 줄 하나만** 그쪽에 두고 나머지는 여기에 둔다.
# `signal_watch.py` 가 같은 꼴이다.
#
# ── 값을 인자로 받는다 ──
#
# `kis_proxy` 를 여기서 import 하면 순환이 된다 — 그쪽이 이 파일을 부르기
# 때문이다. 지수·업종·뉴스를 **함수로 받아** 그때 부른다.

import threading
import time

import docstore

KEEP = 10                    # 몇 장까지 쌓나 (2026-09-22 지시 — 「30개는 많고 10개만」)
SEND_AT = 7 * 60 + 30        # 07:30 (분)
TICK = 300                   # 5분마다 깨어난다. `dart-poller` 와 같은 주기다
DOC_PREFIX = "daily-"


def doc_name(now=None):
    """`daily-20260922`. **이름이 날짜라 정렬이 곧 시간 순**이다."""
    return DOC_PREFIX + (now or datetime.now()).strftime("%Y%m%d")


def purge_old(keep=KEEP):
    """열한 번째부터 지운다.

    **층은 안 지운다.** `docstore` 는 문서 하나를 안전하게 읽고 쓰는 것까지이고
    「몇 장까지」 는 쓰는 쪽이 정한다.

    이름이 `daily-YYYYMMDD` 라 **그냥 정렬하면 오래된 것이 앞**이다.
    날짜를 따로 뜯을 필요가 없다.
    """
    names = sorted(docstore.list_docs(DOC_PREFIX))
    if len(names) <= keep:
        return 0
    gone = 0
    for name in names[:len(names) - keep]:
        try:
            os.remove(os.path.join(docstore.DOC_ROOT, name + ".json"))
            gone += 1
        except OSError:
            pass          # 이미 없거나 잠겨 있으면 다음 바퀴에 다시 본다
    return gone


def save_today(indices, sectors, issues, schedule=None, now=None):
    """그날 것을 저장한다. 이미 있으면 **안 쓰고** `None` 을 돌려준다.

    **원본을 그대로 담는다.** 화면이 그리는 것만 추리면 나중에 다른 것을
    보고 싶어도 못 본다 — 이 API 들은 **날짜를 지정해 부를 수 없어**
    그날을 다시 만들 수 없다 (2026-09-22 실측: 날짜 인자 0곳).

    10개면 원본 그대로도 **448KB** 라 추릴 값이 없다 (`market.db` 가 5.2MB).
    """
    name = doc_name(now)
    if docstore.read_doc(name) is not None:
        return None                     # 오늘 것이 이미 있다
    sch = schedule if schedule is not None else calendar_today(now)
    data = {
        "date": (now or datetime.now()).strftime("%Y-%m-%d"),
        "at": (now or datetime.now()).isoformat(timespec="seconds"),
        "indices": indices or [],
        "sectors": sectors or [],
        "issues": issues or [],
        # 저장할 때는 날짜를 글자로 바꾼다. datetime 은 JSON 이 못 담는다.
        "schedule": [{**e, "when": e["when"].isoformat()} if e.get("when") else e
                     for e in (sch or [])],
        # **그날 실제로 보낸 글**을 남긴다. 다시 만들 수는 있지만, 그때 코드로
        # 만든 것이라 나중에 코드가 바뀌면 달라진다.
        "telegram": build_telegram(indices, sectors, issues, sch, now),
    }
    # `history=False` — 날짜가 키라 같은 이름을 다시 쓰는 일이 같은 날 두 번뿐이고,
    # 그때는 덮는 것이 맞다. 열 장이 이미 이력이다.
    ok = docstore.write_doc(name, data, history=False)
    return data if ok else None


def start_daily(get_indices, get_sectors, get_issues, send=None, keep=KEEP):
    """07:30 루프를 띄운다. `kis_proxy` 가 한 줄로 부른다.

    `send(text)` 를 주면 저장한 뒤 그 글을 보낸다. 안 주면 저장만 한다 —
    **저장과 발송을 나눈다.** 발송이 실패해도 그날 것은 남아야 하고,
    열쇠가 없는 폴더(세션 워크트리)에서도 저장은 돌아야 한다.
    """
    def once():
        now = datetime.now()
        if now.hour * 60 + now.minute < SEND_AT:
            return                              # 아직 07:30 전
        if docstore.read_doc(doc_name(now)) is not None:
            return                              # 오늘 것이 이미 있다
        data = save_today(get_indices(), get_sectors(), get_issues(), None, now)
        if not data:
            return
        purge_old(keep)
        if send:
            try:
                send(data["telegram"])
            except Exception:
                pass        # 못 보내도 저장은 남는다

    # **같은 오류는 한 번만 적는다** (2026-09-22 지시).
    #
    # 전에는 `except: pass` 였는데, 그것이 **결함을 통째로 삼켰다** —
    # 튜플을 그대로 넘겨 `once()` 가 매번 죽고 있었는데 로그에는
    # 「07:30 에 저장」 만 찍혀서 **하루 종일 조용히 실패했다.**
    #
    # **동작은 하나도 안 바꾼다.** 저장도 발송도 5분 재시도도 그대로이고,
    # 콘솔에 남느냐만 다르다. 매번 적으면 **5분마다 하루 이백 줄**이 쌓여
    # 다른 줄이 묻히므로 같은 것은 한 번만 적는다.
    #
    # **오류가 바뀌면 다시 적는다.** 안 그러면 **두 번째 결함이 첫 번째에
    # 가려진다.** 성공하면 비워서, 다시 실패할 때 또 보이게 한다.
    last_err = [None]

    def loop():
        time.sleep(5)       # 서버가 막 뜬 참이라 잠깐 기다렸다 시작한다
        while True:
            try:
                once()
                last_err[0] = None
            except Exception as e:
                key = "%s: %s" % (type(e).__name__, e)
                if key != last_err[0]:
                    last_err[0] = key
                    # `pythonw` 로 떠서 콘솔이 없다. `startup.bat` 이
                    # `logs/<포트>.log` 로 받으므로 **flush 해야 바로 보인다.**
                    print("데일리분석 저장 실패 — %s" % key, flush=True)
                    print("  (같은 오류는 다시 안 적습니다. 5분마다 계속 시도합니다)",
                          flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="daily-0730").start()
    return True
