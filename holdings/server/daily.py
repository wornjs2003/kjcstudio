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

# **폰 문안에 쓸 것.** 화면 카드는 `js/components/daily-view.js` 의 같은 이름이
# 따로 갖고 있고, **둘은 맞출 필요가 없다** — `buildTelegram` 이 이리로 옮겨온
# 뒤로 JS 는 문안을 안 만든다 (2026-09-22 실측: JS 에 `buildTelegram` **0곳**).
#
# 전에는 「JS 와 이름까지 같아야 문안이 같아진다」 고 적혀 있었다. **옮기면서
# 그 줄을 안 고쳐 낡았다** — 다음 사람이 「JS 를 고치면 폰 문안이 바뀐다」 로 읽는다.
#
# **같은 지수를 화면과 폰이 다른 이름으로 부르는 것은 남아 있다**
# (화면 `코스피200` · 폰 `KOSPI200` / 화면 `VIX` · 폰 `VIX(공포지수)`).
# 기계가 갈리는 문제가 아니라 **읽는 사람이 헷갈리는 자리**다.
#
# **이름은 `kis_proxy.py` 의 `OVERSEAS_DEFS` · `INDEX_DEFS` 와 맞춘다.**
# 화면도 그것을 쓰므로, 여기만 다르면 **같은 지수가 두 이름으로 보인다.**
# 2026-09-22 에 `SX5E` 를 「유로스톡스」 로 적었다가 걸렸다 — 실측으로
# 「유로STOXX50」 을 보고도 **전달받은 이름을 그대로 넣었다.**
#
# **일부러 다른 것 둘** — 고치기 전에 아래를 읽는다.
#
#     `VIX` → **`VIX(공포지수)`**   폰에는 글만 간다. 숫자만 보면 무엇인지
#                                   모른다 (「숫자에는 뜻을 붙인다」)
#     `USDKRW` → **`달러 · 원`**    응답 이름은 「미국 USD」 인데, 그것은
#                                   **환율이라는 것이 안 읽힌다.**
#                                   첫 화면 띠는 「미국 USD」 라 **이미 갈려 있다** —
#                                   이 커밋이 만든 것이 아니다
#
# **세 번째 칸은 폴백 정규식이다.** code 로 먼저 찾고 못 찾을 때만 쓴다.
# 응답이 주는 code 를 그대로 적어 두었으므로 평소에는 안 쓰인다 —
# 응답 code 가 바뀌는 날을 위한 보험이다. **넓게 쓰지 않는다** —
# `r"유로"` 는 「유로」 가 들어간 것이 하나 더 생기는 날 엉뚱한 것을 집는다.
#
# **열둘을 다 적는다** (2026-09-22 지시 — 「12개 해줘」). 전에는 다섯이라
# 저장본에는 열둘이 있는데 폰에는 다섯 줄만 갔다.
#
# **정규식은 폴백이고 좁게 쓴다.** `code` 가 안 맞을 때만 이름으로 찾는데,
# `r"나스닥"` 처럼 넓게 쓰면 **「나스닥 종합」 자리에 「나스닥100」 이 잡힌다.**
# 겹칠 것은 아예 `None` 으로 둔다 — 못 찾는 것이 엉뚱한 것을 집는 것보다 낫다.
#
# **이름은 사람이 읽는 말로 쓴다.** `VIX` 는 숫자만 보면 무엇인지 모르므로
# 뜻을 붙인다 (「숫자에는 뜻을 붙인다」).
INDEX_ROWS = [
    ("KOSPI", "KOSPI", None),
    ("KOSDAQ", "KOSDAQ", None),
    ("KOSPI200", "KOSPI200", None),
    ("KRX100", "KRX100", None),
    ("SPX", "S&P 500", r"S&P"),
    ("NASDAQ", "나스닥 종합", r"나스닥\s*종합"),
    ("NDX", "나스닥100", r"나스닥\s*100"),
    ("SOX", "필라델피아 반도체", r"필라델피아"),
    ("SX5E", "유로STOXX50", r"유로STOXX"),
    ("HSCE", "홍콩H", r"홍콩"),
    ("VIX", "VIX(공포지수)", None),
    ("USDKRW", "달러 · 원", r"USD|달러"),
]
HOME_CODES = ["KOSPI", "KOSDAQ", "KOSPI200", "KRX100"]
# 환율을 맨 뒤에 둔다 — 지수끼리 묶여 있어야 읽힌다.
AWAY_CODES = ["SPX", "NASDAQ", "NDX", "SOX", "SX5E", "HSCE", "VIX", "USDKRW"]

# 제목이 이보다 길면 자른다. JS 와 같은 값이어야 한다.
TITLE_MAX = 34
NEWS_MAX = 3            # 주제가 겹치지 않는 것으로 셋까지
SECTOR_TOP = 3
# 지수 대비 강한 종목 (2026-10-22 재권님 — 「코스피랑 코스닥 지수 대비 더 강한 종목들 10개 정도씩 … 아침에 텔레그램 올 때
# 같이」 · 「전일 대비, 일주일 대비, 한 달 대비로 묶어서」 · 안에 「응」). 대상은 지수 구성 종목이라 ETF · 우선주가 저절로 빠진다.
STRONG_TOP = 10
STRONG_SPANS = [("전일", 1), ("일주일", 5), ("한 달", 20)]      # (이름, 거래일 수)
# **발송 문안에는 아직 안 넣는다** — 보내는 글이 바뀌는 「켜기」 라 재권님 승인 뒤 True. 저장본에는 늘 담는다.
STRONG_SEND = False


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
    # **「(전일)」 은 장 전에 만든 줄이라는 표시다** (2026-10-06 재권님 「응 해줘」). 07:30 에는 장이 안 열려
    # KIS 지수 시세가 등락 0 을 준다 — 그때는 `kis_proxy` 가 지수 일봉 마지막 두 종가로 채우고
    # `basis` 를 붙인다. 붙이지 않으면 「오늘 등락」 으로 읽힌다
    tag = "(전일) " if x.get("basis") == "전일" else ""
    return f"{label} {num(x.get('value'))} {tag}{mark}{num(abs(float(x.get('changePct') or 0)), 2)}%"


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


def strong_rank(index_bars, stocks, n, top=STRONG_TOP):
    """지수보다 n 거래일 동안 더 오른 폭이 큰 순. `index_bars` · 종목 `bars` 는 [(날짜, 종가), …] 오래된 것부터.

    **날짜로 맞춘다** — 끝 날짜가 지수와 다른 종목(거래 정지 등)이나 기준일 종가가 없는 종목은 뺀다.
    줄 수로만 견주면 하루 쉰 종목이 다른 날끼리 견주어진다. 지수 봉이 모자라면 빈 목록이다(못 쟀다 · 0 이 아니다).
    """
    if not index_bars or len(index_bars) <= n:
        return []
    last_d, last_v = index_bars[-1]
    base_d, base_v = index_bars[-1 - n]
    if not base_v:
        return []
    ir = (last_v / base_v - 1) * 100
    out = []
    for st in stocks or []:
        m = dict(st.get("bars") or [])
        a, b = m.get(base_d), m.get(last_d)
        if not a or not b:
            continue
        r = (b / a - 1) * 100
        out.append({"code": st.get("code"), "name": st.get("name") or st.get("code"),
                    "pct": round(r, 2), "index": round(ir, 2), "gap": round(r - ir, 2)})
    out.sort(key=lambda x: x["gap"], reverse=True)
    return out[:top]


def build_strong(markets):
    """[{label, index:[(날짜,종가)], stocks:[…]}] → 저장본에 담을 모양. 시장마다 기간 셋."""
    res = []
    for mk in markets or []:
        idx = mk.get("index") or []
        res.append({
            "label": mk.get("label"),
            "asOf": idx[-1][0] if idx else None,
            "count": len(mk.get("stocks") or []),
            "spans": [{"name": nm, "days": n, "rows": strong_rank(idx, mk.get("stocks"), n)}
                      for nm, n in STRONG_SPANS],
        })
    return res


def strong_lines(strong):
    """문안 줄. 기간에 줄이 없으면 「못 셈」 — 0 개로 적지 않는다."""
    L = []
    for mk in strong or []:
        for sp in mk.get("spans") or []:
            rows = sp.get("rows") or []
            idx = rows[0]["index"] if rows else None
            L += ["", f"{mk.get('label')} 지수보다 강한 종목 · {sp.get('name')}"
                  + (f" (지수 {pct(idx)})" if idx is not None else "")]
            if not rows:
                L.append("· 못 셈 (봉을 못 받음)")
                continue
            for i, r in enumerate(rows, 1):
                L.append(f"{i}. {r['name']} {pct(r['pct'])} (지수보다 {'+' if r['gap'] > 0 else ''}{r['gap']:.2f}%p)")
    return L


def sector_sides(sectors):
    """오름·내림으로 가른다. **`pct` 가 없는 것은 뺀다** — 섞여 오는 날이 있다."""
    ok = [s for s in (sectors or []) if s.get("pct") is not None]
    ok.sort(key=lambda s: s["pct"], reverse=True)
    up = [s for s in ok if s["pct"] > 0]
    down = [s for s in ok if s["pct"] < 0]
    down.reverse()          # 많이 내린 것부터
    return up, down


# ── 문안 ──

def build_telegram(indices=None, sectors=None, issues=None, schedule=None, now=None, strong=None):
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

    if strong and STRONG_SEND:
        L += strong_lines(strong)

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

from secrets_guard import safe_message

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


def save_today(indices, sectors, issues, schedule=None, now=None, strong=None):
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
        "strong": strong or [],
        "telegram": build_telegram(indices, sectors, issues, sch, now, strong),
    }
    # `history=False` — 날짜가 키라 같은 이름을 다시 쓰는 일이 같은 날 두 번뿐이고,
    # 그때는 덮는 것이 맞다. 열 장이 이미 이력이다.
    ok = docstore.write_doc(name, data, history=False)
    return data if ok else None


def start_daily(get_indices, get_sectors, get_issues, send=None, keep=KEEP, get_strong=None):
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
        # 강한 종목은 KIS 를 종목마다 한 번(구성 종목 수만큼) 부른다 — 못 받아도 나머지는 저장한다
        strong = None
        if get_strong:
            try:
                strong = build_strong(get_strong())
            except Exception as e:
                print("데일리분석 강한 종목 못 셈 — %s: %s" % (type(e).__name__, safe_message(e)), flush=True)
        data = save_today(get_indices(), get_sectors(), get_issues(), None, now, strong)
        if not data:
            return
        purge_old(keep)
        if send:
            # **보냈는지 남긴다** (2026-10-06 재권님 「응 해줘」). 전에는 실패를 `pass` 로 삼키고
            # 성공도 안 적어 「갔나」 를 아무도 못 셌다. 못 보내도 저장은 남는다(그대로).
            # 오류 문구는 `safe_message` 로 가린다 — 로그와 저장본(API 로 나간다) 둘 다 「밖」 이다
            #
            # **`send` 는 실패해도 예외를 안 낸다** — `dart.telegram_send` 는 `(ok, 까닭)` 을 돌려준다.
            # 전에는 그 값을 안 봐서 실패도 `sent = True` 로 적혔다 (2026-10-12). 예외는 그대로 잡는다.
            sent, err = False, None
            try:
                r = send(data["telegram"])
                if isinstance(r, tuple) and r and not r[0]:
                    err = safe_message(Exception(r[1] if len(r) > 1 else "보내지 못함"))
                else:
                    sent = True
            except Exception as e:
                err = "%s: %s" % (type(e).__name__, safe_message(e))
            if sent:
                print("데일리분석 발송함 — %s" % now.strftime("%H:%M"), flush=True)
            else:
                print("데일리분석 발송 실패 — %s" % err, flush=True)
            data["sent"] = sent
            data["sendError"] = err
            docstore.write_doc(doc_name(now), data, history=False)

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
                # **`safe_message` 로 거른다** — `scrub` 뒤 자르기다.
                # 오류 문구에 앱키·토큰이 섞여 들어올 수 있고, 이 줄은
                # `logs/<포트>.log` 에 남는다. **로그는 「안」 인데 세션이
                # 읽어 세션 간 메시지로 옮긴다** — 2026-09-23 에 실제로
                # 그 경로를 탔다(`개념정의` 가 이 파일 로그를 읽어 전했다).
                # **타입 이름은 그대로 둔다** — 「같은 오류인가」 를 그것으로 센다.
                key = "%s: %s" % (type(e).__name__, safe_message(e))
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
