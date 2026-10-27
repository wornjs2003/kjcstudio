# -*- coding: utf-8 -*-
"""실시간 순위 「테마」 — 큰 테마 · 작은 테마 두 줄과 「수급」(넥스트 5분 거래량 2배) (2026-10-27).

재권님 — 「반도체 관련된 종목과 그날 급등하거나 수급이 몰리는 테마만」 → 「넥스트장에 5분봉별로 거래량 체크하고 전날 5분봉과
거래량이 2배 이상인 종목들의 등락률과 해당 종목이 많은 섹터를 실시간으로」 → 「거래량2배 - 수급 이라는 이름으로 · 반도체는 반도체처럼
큰테마들로 옆으로 나열 · 큰테마 밑에 작은테마 클릭하면 해당 종목들」 → 이슈 여덟 안 「응 그려줘」 · 「수급은 섹터에 없는 종목도 수급에는
나와야해 수급 하위의 테마에 기타」 · 「수급옆에 숫자는 없어도」 · 「이대로 한번 해줘」(개발1 창 · 17:2x).

── 큰 테마 (big) ──

    네이버 테마 전부(naver.groups_all · 264개 · 2026-10-27)를 아래 BIG 표의 낱말로 나눈다 — **네이버 분류가 아니다.**
    맞는 낱말이 없거나 묶음 테마(LUMP — 밸류업 · 지주사 · 신규상장 · 대표주)면 「기타」. 새 테마가 생기면 낱말에 안 걸려 「기타」 로 간다 —
    `big()` 의 `unmatched` 가 그 수를 낸다. 나누기를 고칠 자리는 BIG 한 곳이다.

── 수급 (flow) ──

    무엇     넥스트(NX) 5분 구간마다 종목 거래량 — 그 구간 거래량 ≥ 어제 같은 구간 × RATIO · 어제 그 구간 MIN_PREV 주 이상
    언제     평일 08:00~20:00 넥스트가 열린 동안 5분 경계마다(08:05 · 08:10 …) 한 바퀴 — 8765 만(`is_sender`)
    어떻게   멀티 시세(시장구분 NX) 누적 거래량을 종목 마스터 전부(nxt_pre.master_codes · 2026-10-27 2717)에 대해 30종목씩 —
             한 바퀴 90번쯤 · 앞 경계의 누적과의 차가 그 구간 거래량. 넥스트에서 안 사고파는 종목(누적 0)은 안 적는다
    빠진 구간 앞 경계가 안 적혔으면(서버가 내려가 있었음) 그 구간은 견주지 않는다 — 두 구간이 섞인다
    저장     market.db `nx_slot`(날 · 구간 끝 HHMM · 종목 · 누적 · 구간 거래량) — 어제와 견줄 재료. KEEP_DAYS 날만 둔다
    테마     종목이 든 테마는 `theme_member`(하루 한 번 네이버 264번) — 어느 테마에도 없으면(ETF 등) 수급 「기타」
    첫날     어제 값이 없으면 수급 종목이 0 이다 — `prevDay` 가 null 로 그것을 알린다(「없음」 을 0 으로 꾸미지 않는다)

읽기(`flow` · `big`)는 어느 서버든 자기 DB · 네이버 캐시로 — 8764 · 세션 서버는 메인 DB 를 읽기 전용으로 읽는다.
"""

import threading
import time
from datetime import datetime, timedelta, timezone

import naver
import nxt_board
import nxt_pre
from secrets_guard import safe_message

KST = timezone(timedelta(hours=9))

OPEN, CLOSE = (8, 0), (20, 0)       # 넥스트 프리 08:00 ~ 애프터 20:00
SLOT_MIN = 5
RATIO = 2.0                          # 「2배 이상」
MIN_PREV = 10000                     # 어제 그 구간 거래량 문턱(주) — 장 전 알림(nxt_pre.MIN_PREV)과 같은 값 · 이슈 ⑥ 안 「응」
KEEP_DAYS = 4
TICK = 10
FLOW_TTL = 30                        # 읽기 캐시(초) — 롱폴이 같은 값을 거듭 읽을 때 DB 를 덜 연다

LUMP = ("밸류업", "지주사", "신규상장", "대표주")
BIG = (
    ("반도체", "반도체 HBM CXL 소캠 기판 PCB MLCC 뉴로모픽 S7 LED 카메라모듈 OLED 디스플레이 갤럭시 아이폰 스마트폰 폴더블폰 무선충전 전자파 퓨리오사 온디바이스".split()),
    ("AI·통신", "AI 챗봇 클라우드 SI NI 보안주(정보) 딥페이크 음성인식 메타버스 가상현실 증강현실 인터넷 SNS 마이데이터 블록체인 NFT 웹툰 게임 모바일 양자 키오스크 스마트홈 재택 통신 5G 유심".split()),
    ("2차전지·차", "2차전지 리튬 니켈 폐배터리 전기차 자율주행 스마트카 리비안 자동차 타이어 UAM 렌터카 화재".split()),
    ("에너지", "전력 원자력 핵융합 태양광 풍력 수소 연료전지 SOFC ESS 스마트그리드 전선 LNG LPG 셰일 정유 석유 도시가스 주유소 냉각 온실가스 자원개발".split()),
    ("로봇·방산", "로봇 휴머노이드 우주 스페이스X 드론 방위산업 항공기부품 조선 공작기계 건설기계 스마트팩토리 3D 철도 GTX 피팅".split()),
    ("바이오", "바이오 제약 백신 코로나 치료 줄기세포 제대혈 보톡스 마이크로바이옴 유전자 오가노이드 mRNA 화이자 모더나 의료기기 의료AI 원격진료 치매 비만 탈모 임플란트 면역항암 건강기능 고령화 미용기기 마스크 마이코플라스마 구제역 돼지열병".split()),
    ("금융", "증권 은행 보험 카카오뱅크 핀테크 전자결제 페이 토스 두나무 가상화폐 스테이블 STO 창투사 SPAC 리츠 화폐 지역화폐".split()),
    ("소비", "화장품 패션 백화점 편의점 면세점 홈쇼핑 소매유통 쿠팡 마켓컬리 야놀자 여행 호텔 카지노 테마파크 골프 자전거 항공 영화 엔터 음원 미디어 광고 영상콘텐츠 캐릭터 교육 스포츠 음식료 주류 김밥 육계 수산 사료 콩 농업 비료 출산 제습기 공기청정기 겨울 여름 황사 태풍 엔젤".split()),
    ("소재·건설", "철강 강관 비철 귀금속 희귀금속 그래핀 탄소나노튜브 초전도체 화학섬유 석유화학 페인트 윤활유 제지 골판지 플라스틱 요소수 시멘트 아스콘 건설 모듈러 리모델링 부동산 해저터널 재건 재난 수자원 폐기물 조림 종합상사 물류 해운 콜드체인".split()),
)
ETC = "기타"

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS nx_slot (
        day TEXT NOT NULL, slot TEXT NOT NULL, code TEXT NOT NULL, cum INTEGER, vol INTEGER,
        PRIMARY KEY (day, slot, code))""",
    """CREATE TABLE IF NOT EXISTS theme_member (no INTEGER NOT NULL, code TEXT NOT NULL, name TEXT, PRIMARY KEY (no, code))""",
    """CREATE TABLE IF NOT EXISTS theme_member_meta (k TEXT PRIMARY KEY, v TEXT)""",
)

_status = {"lastSlot": None, "lastSweepAt": None, "lastSweepSec": None, "lastCodes": None, "memberDay": None,
           "memberThemes": None, "error": None}
_cache = {}


def _now():
    return datetime.now(KST)


def _init(proxy):
    with proxy._db_lock, proxy.db_conn() as conn:
        for q in _SCHEMA:
            conn.execute(q)


def big_of(name):
    """테마 이름 → 큰 테마 이름. 묶음 테마 · 낱말에 안 걸린 것은 「기타」."""
    n = name or ""
    if any(k in n for k in LUMP) and "반도체" not in n:
        return ETC
    for b, words in BIG:
        if any(w in n for w in words):
            return b
    return ETC


def big():
    """{groups: [{name, themes: [{no, name, pct, count}]}] (BIG 차례 + 기타), unmatched: 기타로 간 수, total}.

    작은 테마는 그 큰 테마 안에서 오늘 등락률 순(네이버가 준 차례)."""
    g = naver.groups_all("theme")
    out = {b: [] for b, _w in BIG}
    out[ETC] = []
    for t in g["rows"]:
        out[big_of(t["name"])].append(t)
    return {"groups": [{"name": b, "themes": ts} for b, ts in out.items()],
            "unmatched": len(out[ETC]), "total": g.get("total")}


# ── 테마 소속 — 하루 한 번 ─────────────────────────────────────────

def refresh_members(proxy, day):
    """네이버 테마 전부의 종목을 받아 theme_member 를 갈아 끼운다. 받은 테마 수."""
    _init(proxy)
    rows, got = [], 0
    for t in naver.groups_all("theme")["rows"]:
        try:
            for s in naver.stocks("theme", t["no"], True)["rows"]:
                rows.append((int(t["no"]), s["code"], s.get("name")))
            got += 1
        except Exception:
            pass
        time.sleep(0.05)
    if not got:
        return 0
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute("DELETE FROM theme_member")
        conn.executemany("INSERT OR IGNORE INTO theme_member (no, code, name) VALUES (?, ?, ?)", rows)
        conn.execute("INSERT OR REPLACE INTO theme_member_meta (k, v) VALUES ('day', ?)", (day,))
    _status.update(memberDay=day, memberThemes=got)
    return got


def _member_day(proxy):
    try:
        with proxy._db_lock, proxy.db_conn() as conn:
            r = conn.execute("SELECT v FROM theme_member_meta WHERE k = 'day'").fetchone()
        return r[0] if r else None
    except Exception:
        return None


# ── 넥스트 5분 거래량 ─────────────────────────────────────────────

def _slot_of(now):
    """지금 시각의 마지막 5분 경계 'HHMM'."""
    m = (now.hour * 60 + now.minute) // SLOT_MIN * SLOT_MIN
    return "%02d%02d" % (m // 60, m % 60)


def _prev_slot(slot):
    m = int(slot[:2]) * 60 + int(slot[2:]) - SLOT_MIN
    return "%02d%02d" % (m // 60, m % 60)


def sweep(proxy, day, slot):
    """한 바퀴 — 그 경계의 NX 누적 거래량을 적고 앞 경계와의 차를 그 구간 거래량으로. 적은 종목 수."""
    _init(proxy)
    t0 = time.time()
    cfg = proxy.load_secrets()
    codes = nxt_pre.master_codes()
    nx = nxt_board._multi(proxy, cfg, codes, "NX")
    cum = {c: r["vol"] for c, r in nx.items() if (r.get("vol") or 0) > 0}
    if not cum:
        _status.update(lastSlot=slot, lastSweepAt=_now().isoformat(timespec="seconds"), lastCodes=0,
                       error="NX 거래량 합이 0 — 휴장이거나 아직 거래 전")
        return 0
    with proxy._db_lock, proxy.db_conn() as conn:
        prev_slot = _prev_slot(slot)
        first = slot == "%02d%02d" % (OPEN[0], OPEN[1] + SLOT_MIN)
        prev = {r[0]: r[1] for r in conn.execute("SELECT code, cum FROM nx_slot WHERE day = ? AND slot = ?", (day, prev_slot))}
        have_prev = first or bool(prev)
        rows = []
        for c, v in cum.items():
            vol = (v - (prev.get(c) or 0)) if have_prev else None    # 앞 경계가 없으면 구간을 못 가른다
            rows.append((day, slot, c, v, vol if (vol is None or vol >= 0) else None))
        conn.executemany("INSERT OR REPLACE INTO nx_slot (day, slot, code, cum, vol) VALUES (?,?,?,?,?)", rows)
        days = [r[0] for r in conn.execute("SELECT DISTINCT day FROM nx_slot ORDER BY day DESC")]
        for d in days[KEEP_DAYS:]:
            conn.execute("DELETE FROM nx_slot WHERE day = ?", (d,))
    _status.update(lastSlot=slot, lastSweepAt=_now().isoformat(timespec="seconds"), lastSweepSec=round(time.time() - t0, 1),
                   lastCodes=len(rows), error=None)
    return len(rows)


# ── 읽기 — 수급 ──────────────────────────────────────────────────

def flow(proxy):
    """{day, slot, prevDay, ratio, minPrev, compared, hits: [{code, name, vol, prevVol, ratio}](배율 순),
        themes: [{no, name, big, n, total, codes}](수급 종목 2개 이상 · 묶음 테마 뺌 · n 큰 순), etc: [code](어느 테마에도 없음)}

    값이 없으면 hits 는 [] · prevDay 는 null — 「없음」 을 0 으로 꾸미지 않는다."""
    hit = _cache.get("flow")
    if hit and time.time() - hit[0] < FLOW_TTL:
        return hit[1]
    empty = {"day": None, "slot": None, "prevDay": None, "ratio": RATIO, "minPrev": MIN_PREV, "compared": 0,
             "hits": [], "themes": [], "etc": []}
    with proxy._db_lock, proxy.db_conn() as conn:
        try:
            r = conn.execute("SELECT day, MAX(slot) FROM nx_slot WHERE day = (SELECT MAX(day) FROM nx_slot) "
                             "AND vol IS NOT NULL").fetchone()
        except Exception:
            return empty                          # 표가 아직 없다 — 한 번도 안 돈 서버
        if not r or not r[0]:
            return empty
        day, slot = r[0], r[1]
        pd = conn.execute("SELECT MAX(day) FROM nx_slot WHERE day < ?", (day,)).fetchone()
        prev_day = pd[0] if pd else None
        today = {c: v for c, v in conn.execute("SELECT code, vol FROM nx_slot WHERE day = ? AND slot = ? AND vol IS NOT NULL",
                                               (day, slot))}
        before = {c: v for c, v in conn.execute("SELECT code, vol FROM nx_slot WHERE day = ? AND slot = ? AND vol IS NOT NULL",
                                                (prev_day, slot))} if prev_day else {}
        names = {}
        try:
            for c, n in conn.execute("SELECT code, name FROM nxt_board WHERE day = (SELECT MAX(day) FROM nxt_board)"):
                names[c] = n
        except Exception:
            pass
        member = {}
        try:
            for no, c, n in conn.execute("SELECT no, code, name FROM theme_member"):
                member.setdefault(c, []).append(no)
                if n and not names.get(c):
                    names[c] = n                 # 넥장 보드 표가 없는 서버 · 그 표에 없는 종목
        except Exception:
            pass
    compared = [c for c in today if c in before]
    hits = []
    for c in compared:
        pv, v = before[c], today[c]
        if pv and pv >= MIN_PREV and v >= RATIO * pv:
            hits.append({"code": c, "name": names.get(c), "vol": v, "prevVol": pv, "ratio": round(v / pv, 2)})
    hits.sort(key=lambda h: -h["ratio"])
    info = {t["no"]: t for t in naver.groups_all("theme")["rows"]}
    by_theme, etc = {}, []
    for h in hits:
        # 묶음 테마(밸류업 · 지주사 …)는 수급 테마로 안 센다 — 그것뿐인 종목은 「기타」(재권님 「섹터에 없는 종목 … 기타」)
        nos = [no for no in member.get(h["code"], []) if no in info and not any(k in info[no]["name"] for k in LUMP)]
        if not nos:
            etc.append(h["code"])
        for no in nos:
            by_theme.setdefault(no, []).append(h["code"])
    themes = [{"no": no, "name": info[no]["name"], "big": big_of(info[no]["name"]), "n": len(cs),
               "total": info[no].get("count"), "codes": cs}
              for no, cs in by_theme.items() if len(cs) >= 2]
    themes.sort(key=lambda t: (-t["n"], t["total"] or 0))
    out = {"day": day, "slot": slot, "prevDay": prev_day, "ratio": RATIO, "minPrev": MIN_PREV, "compared": len(compared),
           "hits": hits, "themes": themes, "etc": etc}
    _cache["flow"] = (time.time(), out)
    return out


def status():
    return dict(_status, open="%02d:%02d" % OPEN, close="%02d:%02d" % CLOSE, slotMin=SLOT_MIN)


def start(proxy):
    """보내는 서버가 뜰 때 한 번 — 평일 08:05~20:00 5분 경계마다 한 바퀴 · 하루 한 번 테마 소속."""
    def loop():
        time.sleep(60)
        done = None
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = now.hour * 60 + now.minute
                if now.weekday() < 5:
                    if _member_day(proxy) != day and _status.get("memberTry") != day:
                        _status["memberTry"] = day             # 실패해도 그날은 한 번
                        try:
                            n = refresh_members(proxy, day)
                            print("  [수급] %s 테마 소속 %s테마 받음" % (day, n), flush=True)
                        except Exception as e:
                            _status["error"] = "테마 소속: " + safe_message(e, 120)
                    slot = _slot_of(now)
                    if OPEN[0] * 60 + OPEN[1] + SLOT_MIN <= hm <= CLOSE[0] * 60 + CLOSE[1] and done != (day, slot):
                        done = (day, slot)
                        try:
                            sweep(proxy, day, slot)
                            _cache.pop("flow", None)
                        except Exception as e:
                            _status["error"] = safe_message(e, 160)
                            print("  [수급] %s %s 바퀴 실패: %s" % (day, slot, type(e).__name__), flush=True)
            except Exception as e:
                print("  [수급] 예기치 못한 오류: %s" % type(e).__name__, flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="theme-flow").start()
    return True
