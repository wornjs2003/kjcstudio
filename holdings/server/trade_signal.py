# -*- coding: utf-8 -*-
"""매수 목록 보내기 · 매매일지 — 단타 판 위 종목을 슬랙으로 주문 컴퓨터에 넘기고, 매도 결과를 받아 적는다 (2026-11-23).

재권님 말씀 —
    「내가 고른 종목들 HTS 에 자동으로 매수 혹은 매매 하고싶은데」(14:1x) → 「단타 리스트에서 리스트업되는 종목들 선별 후 메세지 보내 /
    메세지 받으면 다른 pc에서 주문」 → 「슬렉 프로그램 깔아서 하고싶어」 → 「지금은 단타 9시5분 굳힘 목록에 들어가는 상위 3개로만」 →
    「이건 돈이 들어가는 거니깐 하나하나 정확히 관리가 되야」 → 「서버에서는 주문 목록과 매수금액만 보낸다 … 매수 후 매도한 이후에
    매수가격 매도가격 시세차익 세금 정보를 메세지로 보낸다 / 해당 메세지를 서버에서 받으면 매매일지에 기록한다」 → 안에 「응 그래」(14:4x).

하는 일
    매도     보낸 종목을 판 매도 룰(dt30_win.sell_of)로 SEND_CHECK_SEC 마다 보고 걸리면 SELL 을 한 번 보낸다
    보내기   그날 단타 판 첫 굳힘(lock 1 · 09:05 · dt30.lock_at 첫 칸) 줄 중 굳힘 차례(lockRank) 위 PICK_N 종목 + 종목마다 매수금액을 슬랙 채널에 한 번(수신 웹훅) — 개발 서버(is_sender)에서만
    받기     슬랙 채널을 READ_SEC 마다 읽어(conversations.history · 공개 주소 없음) 「RESULT」 줄을 매매일지에 적는다
    매매일지  market.db trade_journal — 줄을 지우지 않는다(돈이 드는 기록) · /api/kis/trade-journal

메시지 꼴(서버 ↔ 주문 컴퓨터가 함께 읽는 한 곳 — 바꾸면 주문 컴퓨터 프로그램도 같이 바꾼다)
    서버 → 주문 컴퓨터   첫 줄 「[KJC 매수 목록] YYYY-MM-DD HH:MM:SS」 · 종목마다 한 줄
                        BUY|<일지 번호>|<종목 코드>|<종목 이름>|<매수금액 원>|<보낸 시각 YYYYMMDDHHMMSS>|<서명>
    서버 → 주문 컴퓨터   (매도) 판 매도 룰에 걸리면 종목마다 한 번 — 첫 줄 「[KJC 매도] YYYY-MM-DD HH:MM:SS」
                        SELL|<일지 번호>|<종목 코드>|<종목 이름>|<까닭>|<보낸 시각 YYYYMMDDHHMMSS>|<서명>
                        까닭 — 손절 · 꺾임 · 고점 · 미달 · 횡보 · 매도 시각(dt30_win.sell_of — 승률 표 · 단타 판 화면과 같은 셈 · 매수가는 판 매수가)
                        재권님 「가」(11-23 14:5x — 단타 판 매도 룰에 걸리면 서버가 슬랙으로 「팔아라」)
                        판 값은 30분 칸(dt30 times)마다 붙어 걸림도 그 칸에 안다 · 주문 컴퓨터는 가진 수량을 전부 판다
    주문 컴퓨터 → 서버   매도가 끝난 종목마다 한 줄(여러 줄 한 메시지도 됨)
                        RESULT|<일지 번호>|<종목 코드>|<매수가>|<매도가>|<수량>|<시세차익 원>|<세금 원>|<매도 시각 YYYYMMDDHHMMSS>|<서명>
                        못 산 종목은 RESULT|<번호>|<코드>|-|-|0|0|0|<시각>|<서명> (수량 0 = 안 삼)
    서명            마지막 「|」 앞까지 글(앞뒤 빈칸 뺌)을 sign_key 로 HMAC-SHA256 한 16진 64자 — 재권님 「보완도 엄청 중요한데」(11-23 14:4x)
                   슬랙 채널에 누가 같은 꼴의 줄을 써도 열쇠가 없으면 주문 · 일지가 안 움직인다. 주문 컴퓨터도 BUY 줄의 서명을 같은 셈으로 본다
                   서명이 틀리거나 없는 줄은 일지에 아무것도 안 적는다(남의 줄 메모도 안 바꿈 · 서버 로그 · status 에만 · 개념정의 덧 11-23) · 이미 결과가 적힌 번호에 다시 온 결과는 안 덮는다(되풀이 막기)
    주문 컴퓨터가 지킬 것(BUY 되풀이 막기 — 서버는 못 막는다 · 옛 BUY 메시지를 누가 채널에 다시 올리면 또 살 수 있다 · 개념정의 · qa 덧 11-23)
                   서명이 맞는 BUY · SELL 줄만 · 보낸 시각이 주문 컴퓨터 설정의 「늦은 메시지 버림 초」 를 넘으면 버림 ·
                   같은 일지 번호의 BUY 는 한 번만 주문 · SELL 도 한 번만(받은 번호를 그 컴퓨터에 남김 · 옛 SELL 줄을 다시 올려도 두 번 안 팖) ·
                   SELL 은 그 번호로 실제로 산 수량이 있을 때만 판다 ·
                   그 컴퓨터 설정의 한 번 · 하루 한도와 멈춤 스위치를 서버 매수금액보다 먼저 본다
    숫자는 쉼표 없이 · 금액은 원 · 칸이 모자라거나 숫자가 아니면 그 줄은 「못 읽음」 으로 일지에 남기고 값은 안 적는다

켜기 · 지킴
    SEND           슬랙으로 보내는 스위치 — False 면 판도 안 읽고 일지 줄도 안 만든다 · 켜기는 재권님 지시(되돌릴 수 없는 발송)
    설정 문서       docstore 「trade-set」 {amountWon: 종목마다 매수금액(원) | null, stop: 전체 멈춤 true/false} — 화면이 고친다
                   amountWon 이 비었거나 0 이하 · stop 이 true 면 매수 목록을 보내지 않는다(그 까닭을 일지 상태에 적음) ·
                   stop 은 새 매수만 막고 산 종목의 매도 신호는 계속 보낸다(산 것이 안 팔리지 않게 · qa 덧 11-23 · 재권님께 여쭈는 중)
    비밀           비밀 파일(secrets_guard.secrets_path() 한 벌 — 지금 ~/.kjc 의 것 · 서버가 load_secrets 로 읽음)의 「slack」 칸 — webhook_url(보내기) · bot_token(읽기 · channels:history) · channel_id(읽을 채널) ·
                   sign_key(서명 열쇠 — 주문 컴퓨터와 같은 값 · 슬랙 · 메시지 · 저장소에 안 둔다) · sign_key 가 비면 보내지도 받지도 않는다
                   하나라도 비면 그쪽 일을 안 한다(「못 함」 으로 status 에)
"""
import hashlib
import hmac
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
SEND = False                  # 슬랙으로 매수 목록 보내기 — 켜기는 재권님 지시 때만(되돌릴 수 없는 발송 · CLAUDE.md 「켜기」)
PICK_N = 3                    # 보낼 종목 수 — 재권님 「지금은 단타 9시5분 굳힘 목록에 들어가는 상위 3개로만」(11-23 · 고르는 조건은 나중에 다듬음)
READ_SEC = 5                  # 슬랙 채널 읽는 간격(초) — 재권님 「메세지가 가면 바로 읽을수 있으면」(11-23 14:4x) · conversations.history 는 분당 50회 넘게 되는 등급(Tier 3 · 슬랙 문서) · 12회/분
READ_FROM, READ_TO = (8, 0), (21, 0)   # 평일 이 사이에만 읽는다 — 매도 결과는 장중 · 넥스트레이드 끝(20:00) 뒤 조금까지
SET_DOC = "trade-set"
MAX_PAGES = 10                # 한 바퀴에 읽는 쪽 수(쪽마다 200)
SELL_RETRY_SEC = 60          # 슬랙이 매도 신호를 거절했을 때 다시 보내기까지(초)
_sell_hold = {"until": 0.0}
SEND_CHECK_SEC = 10          # 첫 굳힘이 났나 판을 보는 간격(초)
TICK = 1                      # 도는 틀 간격(초) — READ_SEC 이 실제 읽는 간격이 되게 그보다 잘게(qa 덧 11-23 — 틀이 10초라 5초가 10초였음)
SLACK_HISTORY = "https://slack.com/api/conversations.history"
_SCHEMA = ("CREATE TABLE IF NOT EXISTS trade_journal (id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL, rank INTEGER, code TEXT, name TEXT, "
           "amount_won INTEGER, made_at TEXT, sent_at TEXT, status TEXT, note TEXT, buy_px REAL, sell_px REAL, qty INTEGER, profit_won REAL, "
           "tax_won REAL, sell_at TEXT, result_at TEXT, result_raw TEXT)")
_ADD_COLS = (("sell_sent_at", "TEXT"), ("sell_why", "TEXT"))   # 매도 신호 칸(11-23 · 옛 표에는 더한다)
_STATE = ("CREATE TABLE IF NOT EXISTS trade_journal_state (k TEXT PRIMARY KEY, v TEXT)")
_status = {"sentDay": None, "sendAt": None, "sendNote": None, "readAt": None, "readNote": None, "got": 0, "error": None}
_lock = threading.Lock()


def _now():
    return datetime.now(KST)


def settings():
    """{amountWon: int | None, stop: bool} — 문서가 없거나 못 읽으면 amountWon None(보내지 않음)."""
    try:
        import docstore
        d = docstore.read_doc(SET_DOC) or {}
        d = d.get("data", d) if isinstance(d, dict) else {}
    except Exception:
        d = {}
    a = d.get("amountWon")
    a = int(a) if isinstance(a, (int, float)) and not isinstance(a, bool) and a > 0 else None
    return {"amountWon": a, "stop": d.get("stop") is True}


def _slack(proxy):
    s = (proxy.load_secrets() or {}).get("slack") or {}
    return {k: (s.get(k) or "").strip() for k in ("webhook_url", "bot_token", "channel_id", "sign_key")}


def sign(key, body):
    return hmac.new(key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def _signed(key, line):
    """서명이 맞으면 서명 뺀 글 · 아니면 None."""
    body, _, sig = line.rpartition("|")
    return body if body and key and hmac.compare_digest(sign(key, body), sig.strip().lower()) else None


def _db(proxy, fn):
    with proxy._db_lock, proxy.db_conn() as conn:
        conn.execute(_SCHEMA)
        conn.execute(_STATE)
        have = {r[1] for r in conn.execute("PRAGMA table_info(trade_journal)")}
        for c, t in _ADD_COLS:
            if c not in have:
                conn.execute("ALTER TABLE trade_journal ADD COLUMN %s %s" % (c, t))
        return fn(conn)


def journal(proxy, days=30):
    """매매일지 줄 — 최근 days 날 · 새 것이 위."""
    since = (_now() - timedelta(days=days * 2)).strftime("%Y%m%d")
    try:
        def q(conn):
            conn.row_factory = None
            cur = conn.execute("SELECT * FROM trade_journal WHERE day >= ? ORDER BY day DESC, rank ASC, id ASC", (since,))
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        return _db(proxy, q)
    except Exception:
        return []


def _post_webhook(url, text):
    req = urllib.request.Request(url, data=json.dumps({"text": text}).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        body = r.read().decode("utf-8", "replace").strip()
    if body != "ok":
        raise RuntimeError("슬랙 응답이 ok 가 아님 — %s" % body[:60])


def send_today(proxy, day):
    """그날 판이 굳었으면 위 PICK_N 줄을 일지에 만들고(한 번) 조건이 맞으면 슬랙에 보낸다 → 상태 글."""
    import dt30
    b = dt30.board(proxy, day)
    if not b or b.get("day") != day:
        return "판 아직 없음"
    rows = sorted([r for r in b.get("rows") or [] if r.get("lock") == 1], key=lambda r: (r.get("lockRank") or 1e9, r.get("rank") or 1e9))[:PICK_N]
    if not rows:
        return "첫 굳힘 전"                             # 첫 굳힘(09:05 · dt30.lock_at 첫 칸) 줄이 아직 없음 — 다음 바퀴에 다시 본다
    st = settings()
    now = _now()
    if not SEND:
        return "안 보냄 — 꺼짐(SEND) · 일지에 안 적음"      # 꺼진 동안은 줄을 안 쌓는다 — 일지는 실제로 돈이 움직일 수 있었던 날만(qa 덧 11-23)
    have = _db(proxy, lambda c: c.execute("SELECT COUNT(*) FROM trade_journal WHERE day = ?", (day,)).fetchone()[0])
    if have:
        return "이미 만듦"
    sk = _slack(proxy)
    try:
        import dt30_win
        nob = 1 in dt30_win.no_buy_locks()             # 첫 굳힘에 「사지 않음」 을 켜셨으면 보내지 않는다(승률 표와 같은 셈)
    except Exception:
        nob = False
    why = ("첫 굳힘 사지 않음" if nob else "전체 멈춤" if st["stop"] else "매수금액 빔" if st["amountWon"] is None
           else "보내기 주소 없음" if not sk["webhook_url"] else "서명 열쇠 없음" if not sk["sign_key"] else None)
    made = now.strftime("%Y%m%d%H%M%S")

    def ins(conn):
        ids = []
        for r in rows:
            cur = conn.execute("INSERT INTO trade_journal (day, rank, code, name, amount_won, made_at, status, note) VALUES (?,?,?,?,?,?,?,?)",
                               (day, r["rank"], r["code"], r.get("name"), st["amountWon"], made, "보낼 차례" if why is None else "안 보냄", why))
            ids.append(cur.lastrowid)
        return ids
    ids = _db(proxy, ins)
    if why is not None:
        return "안 보냄 — %s" % why
    lines = ["[KJC 매수 목록] %s" % now.strftime("%Y-%m-%d %H:%M:%S")]
    body = ["BUY|%d|%s|%s|%d|%s" % (i, r["code"], (r.get("name") or "").replace("|", " ").replace("\n", " "), st["amountWon"], made) for i, r in zip(ids, rows)]
    lines += ["%s|%s" % (b, sign(sk["sign_key"], b)) for b in body]
    try:
        _post_webhook(sk["webhook_url"], "\n".join(lines))
    except urllib.error.HTTPError as e:                # 슬랙이 받고 거절했다 — 안 갔다
        msg = proxy.safe_message(e, 120)
        _db(proxy, lambda c: c.executemany("UPDATE trade_journal SET status = '못 보냄', note = ? WHERE id = ?", [(msg, i) for i in ids]))
        return "못 보냄 — %s" % msg
    except Exception as e:                             # 시간 초과 · 끊김 — 슬랙에는 갔을 수 있다(qa 덧 11-23) · 다시 보내지 않고 「모름」 으로
        msg = proxy.safe_message(e, 120)
        _db(proxy, lambda c: c.executemany("UPDATE trade_journal SET status = '보냈는지 모름', note = ? WHERE id = ?", [(msg, i) for i in ids]))
        return "보냈는지 모름 — %s" % msg
    sent = _now().strftime("%Y%m%d%H%M%S")
    _db(proxy, lambda c: c.executemany("UPDATE trade_journal SET status = '보냄', sent_at = ? WHERE id = ?", [(sent, i) for i in ids]))
    return "보냄 %d종목" % len(ids)


def sell_check(proxy, day):
    """보낸 매수 줄 중 아직 매도 신호를 안 보낸 것을 판 매도 룰로 본다 — 걸린 것만 SELL 을 보낸다 → 보낸 수."""
    import dt30
    import dt30_win
    todo = _db(proxy, lambda c: c.execute("SELECT id, code, name FROM trade_journal WHERE day = ? AND sent_at IS NOT NULL AND sell_sent_at IS NULL "
                                          "AND result_at IS NULL", (day,)).fetchall())
    if not todo:
        return 0
    sk = _slack(proxy)
    if not SEND or not sk["webhook_url"] or not sk["sign_key"] or time.time() < _sell_hold["until"]:
        return 0                                       # 전체 멈춤은 새 매수만 막는다 — 산 종목은 계속 판다(qa 덧 11-23 · 재권님께 여쭈는 중)
    b = dt30.board(proxy, day)
    if not b or b.get("day") != day:
        return 0
    rows = {r["code"]: r for r in b.get("rows") or []}
    S = dt30_win.sell_rule()
    end = S["endAt"] or dt30_win.SELL_AT
    now = _now()
    hm = now.strftime("%H%M")
    if now.hour * 60 + now.minute >= dt30._close_min(proxy, now):
        return 0                                       # 정규장이 끝난 뒤에는 안 보낸다 — 서버가 늦게 떠도 장 뒤에 「매도 시각」 이 나가지 않게(개념정의 덧 11-23 · 판은 정규장 종목)
    out = []
    for jid, code, name in todo:
        r = rows.get(code)
        why = dt30_win.sell_of(r, end, S)[1] if r else "판에 없음"
        if why in ("매도 시각", "옛 줄", "판에 없음"):
            if hm < end:
                continue                               # 아직 어느 룰에도 안 걸렸고 매도 시각 전 · 판 값을 못 셈
            why = "매도 시각"                          # 매도 시각 뒤에는 판 값과 상관없이 아직 안 보낸 줄 전부(qa 덧 11-23 — 판 값이 비거나 판에서 빠진 종목이 영영 안 팔리던 것)
        out.append((jid, code, name, why))
    if not out:
        return 0
    made = now.strftime("%Y%m%d%H%M%S")
    body = ["SELL|%d|%s|%s|%s|%s" % (j, c, (n or "").replace("|", " ").replace("\n", " "), w, made) for j, c, n, w in out]
    text = "\n".join(["[KJC 매도] %s" % now.strftime("%Y-%m-%d %H:%M:%S")] + ["%s|%s" % (x, sign(sk["sign_key"], x)) for x in body])
    try:
        _post_webhook(sk["webhook_url"], text)
        st = "SELL 보냄"
    except urllib.error.HTTPError as e:
        _sell_hold["until"] = time.time() + SELL_RETRY_SEC   # 안 갔다 — SELL_RETRY_SEC 뒤에 다시(10초마다 두드리지 않게 · qa 덧 11-23)
        print("  [매매일지] 매도 신호 못 보냄 — %s · %d초 뒤 다시" % (proxy.safe_message(e, 120), SELL_RETRY_SEC), flush=True)
        return 0
    except Exception as e:
        st = "SELL 보냈는지 모름 — %s" % proxy.safe_message(e, 80)   # 갔을 수 있다 — 다시 안 보냄
    _db(proxy, lambda c: c.executemany("UPDATE trade_journal SET sell_sent_at = ?, sell_why = ?, note = COALESCE(note || ' · ', '') || ? WHERE id = ?",
                                       [(made, w, st, j) for j, _, _, w in out]))   # 앞 메모를 덮지 않고 뒤에 붙인다(개념정의 덧 11-23)
    return len(out)


_NUM = re.compile(r"^-?\d+(\.\d+)?$")


def _apply_result(conn, line, key):
    """RESULT 한 줄(서명 포함) → 일지에 적음 · (적음 True/False, 글)."""
    body = _signed(key, line)
    if body is None:
        _status["badSig"] = _status.get("badSig", 0) + 1     # 일지는 안 건드린다 — 열쇠 없는 줄이 남의 줄 메모를 바꾸지 못하게(개념정의 덧 11-23)
        print("  [매매일지] 서명 틀린 결과 줄 — 안 적음 · %s" % line[:40], flush=True)
        return False, "서명 틀림"
    p = [x.strip() for x in body.split("|")]
    if len(p) < 9:
        return False, "칸 모자람"
    _, jid, code, bpx, spx, qty, profit, tax, sell_at = p[:9]
    if not jid.isdigit():
        return False, "일지 번호가 숫자 아님"
    row = conn.execute("SELECT code, result_at FROM trade_journal WHERE id = ?", (int(jid),)).fetchone()
    now = _now().strftime("%Y%m%d%H%M%S")
    if not row:
        return False, "없는 일지 번호 %s" % jid
    if row[0] != code:
        return False, "번호 %s 의 종목이 다름(%s ↔ %s)" % (jid, row[0], code)
    if row[1]:
        return False, "번호 %s 는 이미 결과가 있음(안 덮음)" % jid
    nums = [bpx, spx, qty, profit, tax]
    if not all(_NUM.match(x) or x == "-" for x in nums):
        conn.execute("UPDATE trade_journal SET note = ?, result_raw = ? WHERE id = ?", ("결과 못 읽음(숫자 아님)", line[:300], int(jid)))
        return False, "숫자 아님"
    f = lambda x: None if x == "-" else float(x)
    q = int(float(qty)) if _NUM.match(qty) else None
    conn.execute("UPDATE trade_journal SET status = ?, buy_px = ?, sell_px = ?, qty = ?, profit_won = ?, tax_won = ?, sell_at = ?, result_at = ?, "
                 "result_raw = ? WHERE id = ?",
                 ("안 삼" if q == 0 else "매도 끝", f(bpx), f(spx), q, f(profit), f(tax), sell_at, now, line[:300], int(jid)))
    return True, "적음"


def read_once(proxy):
    """슬랙 채널에서 마지막으로 읽은 뒤 온 메시지를 읽어 RESULT 줄을 일지에 적는다 → 적은 줄 수."""
    sk = _slack(proxy)
    if not sk["bot_token"] or not sk["channel_id"] or not sk["sign_key"]:
        _status["readNote"] = "못 함 — 읽기 열쇠 · 채널 · 서명 열쇠 중 빈 것"
        return 0
    oldest = _db(proxy, lambda c: (c.execute("SELECT v FROM trade_journal_state WHERE k = 'oldest'").fetchone() or [None])[0])
    if oldest is None:                                 # 처음 읽음 — 채널의 옛 글은 안 읽고 지금부터(qa 덧 11-23 · 0 부터면 쓰던 채널에서 끝없이 밀림)
        oldest = "%.6f" % time.time()
        _db(proxy, lambda c: c.execute("INSERT OR REPLACE INTO trade_journal_state (k, v) VALUES ('oldest', ?)", (oldest,)))
        return 0
    msgs, cursor = [], None
    for _ in range(MAX_PAGES):                         # 한 번에 200 넘게 밀렸으면 다음 쪽까지 — 앞을 건너뛰지 않는다(qa 덧 11-23)
        q = {"channel": sk["channel_id"], "oldest": oldest, "limit": 200}
        if cursor:
            q["cursor"] = cursor
        req = urllib.request.Request(SLACK_HISTORY + "?" + urllib.parse.urlencode(q), headers={"Authorization": "Bearer " + sk["bot_token"]})
        with urllib.request.urlopen(req, timeout=15) as r:
            j = json.loads(r.read().decode("utf-8"))
        if not j.get("ok"):
            raise RuntimeError("슬랙 읽기 실패 — %s" % str(j.get("error"))[:60])
        msgs += j.get("messages") or []
        cursor = (j.get("response_metadata") or {}).get("next_cursor")
        if not j.get("has_more") or not cursor:
            break
    else:
        # 다 못 읽음 — 슬랙은 새 것부터 주어 다시 읽어도 앞쪽에 못 닿는다(qa 덧 11-23) · 자리는 옮기고 건너뛴 것을 크게 알린다
        _status["readNote"] = "밀린 메시지가 %d쪽 넘어 그 앞을 건너뜀 — 매매일지와 주문 컴퓨터 기록을 맞춰 보십시오" % MAX_PAGES
        print("  [매매일지] %s" % _status["readNote"], flush=True)
    msgs = sorted(msgs, key=lambda m: float(m.get("ts") or 0))
    if not msgs:
        return 0
    got = 0

    def put(conn):
        nonlocal got
        for m in msgs:
            for line in (m.get("text") or "").splitlines():
                if line.strip().startswith("RESULT|"):
                    ok, _ = _apply_result(conn, line.strip(), sk["sign_key"])
                    got += 1 if ok else 0
        conn.execute("INSERT OR REPLACE INTO trade_journal_state (k, v) VALUES ('oldest', ?)", (msgs[-1]["ts"],))
    _db(proxy, put)
    return got


def status():
    return dict(_status, send=SEND, pickN=PICK_N, readSec=READ_SEC, settings=settings())


def start(proxy):
    """쓰는 서버(개발 서버)가 뜰 때 한 번 — 평일 판이 굳은 뒤 한 번 보내기 · READ_FROM~READ_TO 동안 READ_SEC 마다 읽기."""
    if not proxy.marketdb.writable():
        return False
    import dt30

    def loop():
        time.sleep(45)
        last_read = last_send = last_sell = 0.0
        while True:
            try:
                now = _now()
                day = now.strftime("%Y%m%d")
                hm = now.hour * 60 + now.minute
                if now.weekday() < 5:
                    end = dt30.BUY_LATE[0] * 60 + dt30.BUY_LATE[1]
                    if (SEND and _status["sentDay"] != day and dt30.OPEN_AT[0] * 60 + dt30.OPEN_AT[1] <= hm <= end
                            and time.time() - last_send >= SEND_CHECK_SEC):   # 꺼져 있으면 판을 안 읽는다 · 켜져도 SEND_CHECK_SEC 마다(개념정의 덧 11-23)
                        last_send = time.time()
                        note = send_today(proxy, day)
                        _status.update(sendAt=now.strftime("%H:%M:%S"), sendNote=note)
                        if note not in ("판 아직 없음", "첫 굳힘 전"):
                            _status["sentDay"] = day
                            print("  [매매일지] %s 매수 목록 — %s" % (day, note), flush=True)
                    if SEND and time.time() - last_sell >= SEND_CHECK_SEC and dt30.OPEN_AT[0] * 60 + dt30.OPEN_AT[1] <= hm:
                        last_sell = time.time()
                        n = sell_check(proxy, day)
                        if n:
                            print("  [매매일지] 매도 신호 %d종목" % n, flush=True)
                    if READ_FROM[0] * 60 + READ_FROM[1] <= hm < READ_TO[0] * 60 + READ_TO[1] and time.time() - last_read >= READ_SEC:
                        last_read = time.time()
                        n = read_once(proxy)
                        _status.update(readAt=now.strftime("%H:%M:%S"), got=_status["got"] + n, error=None)
                        if n:
                            print("  [매매일지] 매도 결과 %d줄 적음" % n, flush=True)
            except Exception as e:
                _status["error"] = proxy.safe_message(e, 120)
                print("  [매매일지] 멈춤 — %s" % _status["error"], flush=True)
            time.sleep(TICK)

    threading.Thread(target=loop, daemon=True, name="trade_signal").start()
    return True
