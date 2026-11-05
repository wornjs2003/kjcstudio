"""KIS 실시간 체결 웹소켓 — 보고 있는 종목의 캔들을 체결마다 움직인다 (2026-11-05 재권님 「나로 하는걸 진행해봐」 · 「응 그렇게 해」).

전에는 차트 · 모달의 맨 오른쪽 봉이 멀티 시세(`MULTI_CACHE_TTL` 2초)를 따라 2초 계단으로 움직였다(11-05 16:13 8765 실측).
이 모듈은 증권사 실시간 체결(웹소켓)을 받아 **누군가 지금 보고 있는 종목**의 마지막 체결을 들고 있다가,
화면이 `/api/kis/live?code=…&seq=…` 로 물으면 **새 체결이 올 때까지 쥐고 있다가** 바로 낸다.

리소스를 넘지 않게 — 재권님 「우리가 사용할수있는 리소스를 넘기지 않게끔해야해」
    연결        **8765 하나.** 다른 서버는 이 주소를 8765 로 넘긴다(`KJC_KIS_UPSTREAM` · kis_proxy 의 live 자리)
    받는 종목    지금 묻는 종목만 · `LIVE_MAX_CODES` 개까지 — 넘으면 가장 오래 안 물은 종목부터 뺀다.
                KIS 한도는 연결 하나에 41(11-05 16:22 실측 — 45 를 넣으니 42번째부터 OPSP0008 MAX SUBSCRIBE OVER)
    안 보면 뺀다  `LIVE_IDLE_SEC` 동안 아무도 안 물은 종목은 등록을 푼다 · 다 빠지면 연결도 닫는다
    다시 붙기    끊기면 `RECONNECT_MIN_SEC` 부터 두 배씩 · `RECONNECT_MAX_SEC` 까지 쉬고 붙는다
    접속키       한 번 받아 `APPROVAL_REUSE_SEC` 동안 다시 쓴다 — 받는 주기는 「아직 안 잼」(만료 시각을 응답이 안 준다)
    REST 한도    이 연결은 초당 호출 한도(`KIS_CALLS_PER_SEC`)를 쓰지 않는다 — 접속키 받기 한 번만 REST 다
    스위치       `KJC_KIS_WS=1` 일 때만 돈다(기본 꺼짐 · 켜기는 재권님 지시)

받는 것 — 시세 기준(`quote_market_div`)과 같게: 정규장(J)이면 KRX 체결 `H0STCNT0`, 그 밖은 통합 체결 `H0UNCNT0`.
기준이 바뀌면(09:00 · 15:30) 등록을 바꿔 낀다. 칸 순서는 11-05 16:27 삼성전자 통합 체결을 멀티 시세와 대 보고 맞췄다 —
0 종목 · 1 체결 시각 · 2 현재가 · 4 전일 대비 · 5 등락률 · 7 시가 · 8 고가 · 9 저가 · 13 누적 거래량 · 14 누적 거래대금 · 18 체결강도.

연결 주소는 실전 `ws://ops.koreainvestment.com:21000`(11-05 16:22 실측 101). 모의 서버는 안 쓴다 — 실전 키일 때만 돈다.
웹소켓은 파이썬 기본 부품(socket)으로 짰다 — 맥미니에 웹소켓 라이브러리가 없다(11-05 확인).
"""

import base64
import json
import os
import socket
import struct
import threading
import time
import urllib.request

from secrets_guard import safe_message

KIS_WS_ON = (os.environ.get("KJC_KIS_WS") or "").strip().lower() in ("1", "true", "yes", "on")

WS_HOST = "ops.koreainvestment.com"
WS_PORT = 21000
APPROVAL_URL = "https://openapi.koreainvestment.com:9443/oauth2/Approval"

LIVE_MAX_CODES = 20          # 한 번에 받는 종목 수 상한 — KIS 한도 41 의 절반
LIVE_IDLE_SEC = 60           # 아무도 안 물은 지 이만큼 지나면 그 종목 등록을 푼다
LIVE_HOLD_SEC = 10           # 화면 한 번의 물음을 쥐는 상한 — 넘기기 timeout(15초)보다 짧게
LIVE_GAP_SEC = 0.2           # 화면이 다음에 다시 묻기 전 쉬는 바닥 — 체결이 몰려도 1초에 다섯 번까지
LIVE_STALE_SEC = 5           # 마지막 체결이 이보다 오래되면 화면은 멀티 시세를 그대로 쓴다
LIVE_OFF_RETRY_SEC = 60      # 꺼진 서버면 화면이 이만큼 쉬고 다시 본다
LIVE_MAX_WAITERS = 32        # 동시에 쥐는 물음 상한 — 넘으면 쥐지 않고 지금 값을 바로 낸다(롱폴과 같은 선)
RECONNECT_MIN_SEC = 5
RECONNECT_MAX_SEC = 60
APPROVAL_REUSE_SEC = 6 * 3600
READ_TIMEOUT_SEC = 0.5       # 받기 한 번 기다리는 시간 — 이 간격으로 등록 · 빼기를 본다

_lock = threading.Lock()
_cond = threading.Condition(_lock)
_want = {}                   # 종목 → 마지막으로 물은 시각(monotonic)
_subs = {}                   # 종목 → 등록한 tr_id
_ticks = {}                  # 종목 → 마지막 체결 {seq, at(epoch), …}
_seq = [0]
_waiters = [0]
_thread = [None]
_cfg = {"get": None, "div": None}
_approval = {"key": None, "at": 0.0}
_stat = {"connected": False, "connects": 0, "ticks": 0, "rejects": 0, "lastError": None,
         "lastErrorAt": None, "nextTryAt": None}


def configure(get_cfg, market_div):
    """kis_proxy 가 부른다 — 키 읽기(`load_secrets`)와 시세 기준(`quote_market_div`)을 넘겨받는다."""
    _cfg["get"], _cfg["div"] = get_cfg, market_div


def _tr_now():
    try:
        return "H0STCNT0" if _cfg["div"]() == "J" else "H0UNCNT0"
    except Exception:
        return "H0UNCNT0"


def _num(v, cast=float):
    try:
        return cast(v)
    except (TypeError, ValueError):
        return None


def _parse(fields):
    """체결 한 줄의 칸 → 화면이 쓰는 이름(멀티 시세 `quotes` 와 같은 이름)."""
    return {
        "code": fields[0],
        "time": fields[1],
        "price": _num(fields[2], int),
        "amt": _num(fields[4], int),
        "pct": _num(fields[5]),
        "open": _num(fields[7], int),
        "high": _num(fields[8], int),
        "low": _num(fields[9], int),
        "volume": _num(fields[13], int),
        "value": _num(fields[14], int),
        "power": _num(fields[18]),          # 체결강도(100 기준) — 11-05 16:27 삼성 실측 61.61 · /api/kis/ticks 의 power(tday_rltv)와 같은 값
    }


# ── 아주 작은 웹소켓 (RFC 6455 · 글자 · 핑만) ──────────────────────────
class _Ws:
    def __init__(self):
        self.s = socket.create_connection((WS_HOST, WS_PORT), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(("GET /tryitout/H0STCNT0 HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\n"
                        "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n"
                        % (WS_HOST, WS_PORT, key)).encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            c = self.s.recv(4096)
            if not c:
                raise OSError("웹소켓 첫 응답 전에 끊김")
            buf += c
        head, _, self.buf = buf.partition(b"\r\n\r\n")
        if b" 101 " not in head.split(b"\r\n")[0] + b" ":
            raise OSError("웹소켓 연결 거절 — %s" % head.split(b"\r\n")[0][:60].decode("latin-1"))
        self.s.settimeout(READ_TIMEOUT_SEC)

    def send(self, data, op=1):
        if isinstance(data, str):
            data = data.encode()
        n = len(data)
        h = bytes([0x80 | op])
        if n < 126:
            h += struct.pack("!B", n | 0x80)
        elif n < 65536:
            h += struct.pack("!BH", 126 | 0x80, n)
        else:
            h += struct.pack("!BQ", 127 | 0x80, n)
        m = os.urandom(4)
        self.s.sendall(h + m + bytes(b ^ m[i % 4] for i, b in enumerate(data)))

    def _parse_one(self):
        """`buf` 에 다 온 틀 하나가 있으면 (op, 본문), 아직 덜 왔으면 `None`."""
        b = self.buf
        if len(b) < 2:
            return None
        op, n, i = b[0] & 15, b[1] & 127, 2
        if n == 126:
            if len(b) < 4:
                return None
            n, i = struct.unpack("!H", b[2:4])[0], 4
        elif n == 127:
            if len(b) < 10:
                return None
            n, i = struct.unpack("!Q", b[2:10])[0], 10
        if b[1] & 128:
            i += 4
        if len(b) < i + n:
            return None
        self.buf = b[i + n:]
        return op, b[i:i + n]

    def frame(self):
        """(op, 본문) · 기다리다 시간이 다 되면 `socket.timeout` — 덜 받은 것은 `buf` 에 남아 다음에 이어진다."""
        while True:
            f = self._parse_one()
            if f:
                return f
            c = self.s.recv(65536)
            if not c:
                raise EOFError("웹소켓이 닫힘")
            self.buf += c

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def _approval_key(cfg):
    now = time.time()
    if _approval["key"] and now - _approval["at"] < APPROVAL_REUSE_SEC:
        return _approval["key"]
    body = json.dumps({"grant_type": "client_credentials", "appkey": cfg["app_key"],
                       "secretkey": cfg["app_secret"]}).encode()
    req = urllib.request.Request(APPROVAL_URL, data=body,
                                 headers={"content-type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        key = json.load(resp).get("approval_key")
    if not key:
        raise RuntimeError("접속키를 못 받음")
    _approval.update(key=key, at=now)
    return key


def _sub_msg(key, tr, code, on):
    return json.dumps({"header": {"approval_key": key, "custtype": "P", "tr_type": "1" if on else "2",
                                  "content-type": "utf-8"},
                       "body": {"input": {"tr_id": tr, "tr_key": code}}})


def _err(e):
    _stat["lastError"] = safe_message(e)
    _stat["lastErrorAt"] = time.strftime("%H:%M:%S")
    print("  [실시간] %s %s" % (_stat["lastErrorAt"], _stat["lastError"]), flush=True)


def _sweep(now):
    """오래 안 물은 종목을 뺀다 · 상한을 넘으면 오래된 것부터. 잠금 안에서 부른다."""
    for code, at in list(_want.items()):
        if now - at > LIVE_IDLE_SEC:
            _want.pop(code, None)
    if len(_want) > LIVE_MAX_CODES:
        for code, _at in sorted(_want.items(), key=lambda kv: kv[1])[:len(_want) - LIVE_MAX_CODES]:
            _want.pop(code, None)


def _run():
    backoff = RECONNECT_MIN_SEC
    ws = None
    key = None
    while True:
        with _lock:
            _sweep(time.monotonic())
            if not _want:
                _subs.clear()
                _thread[0] = None
                _stat["connected"] = False
                if ws:
                    ws.close()
                return
            want = set(_want)
        if ws is None:
            try:
                cfg = _cfg["get"]() if _cfg["get"] else None
                if not cfg or cfg.get("mode") != "prod":
                    raise RuntimeError("실전 키가 아니라 실시간 연결을 안 씁니다")
                key = _approval_key(cfg)
                ws = _Ws()
                _stat["connected"], _stat["nextTryAt"] = True, None
                _stat["connects"] += 1
                backoff = RECONNECT_MIN_SEC
            except Exception as e:      # 연결 · 접속키 · 키 읽기 — 무엇이든 쉬고 다시
                _err(e)
                ws = None
                _approval["key"] = None   # 접속키가 상했을 수 있다 — 다음엔 새로
                _stat["connected"] = False
                _stat["nextTryAt"] = time.strftime("%H:%M:%S", time.localtime(time.time() + backoff))
                time.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_MAX_SEC)
                continue
        try:
            tr = _tr_now()
            with _lock:
                drop = [c for c, t in _subs.items() if c not in want or t != tr]
                add = [c for c in want if c not in _subs or _subs[c] != tr]
            for c in drop:
                ws.send(_sub_msg(key, _subs[c], c, False))
                with _lock:
                    _subs.pop(c, None)
            for c in add:
                if len(_subs) >= LIVE_MAX_CODES:
                    break
                ws.send(_sub_msg(key, tr, c, True))
                with _lock:
                    _subs[c] = tr
            t_end = time.monotonic() + 1.0
            while time.monotonic() < t_end:
                try:
                    op, data = ws.frame()
                except socket.timeout:
                    break
                if op == 9:
                    ws.send(data, 10)
                    continue
                if op == 8:
                    raise EOFError("증권사가 닫음")
                if op not in (1, 2):
                    continue
                text = data.decode("utf-8", "replace")
                if text[:1] in "01":
                    _on_data(text)
                    continue
                try:
                    j = json.loads(text)
                except ValueError:
                    continue
                h = j.get("header") or {}
                if h.get("tr_id") == "PINGPONG":
                    ws.send(text)
                    continue
                b = j.get("body") or {}
                if b.get("rt_cd") not in (None, "0"):
                    _stat["rejects"] += 1
                    _err(RuntimeError("등록 거절 %s %s" % (h.get("tr_key"), b.get("msg1"))))
                    with _lock:
                        if _subs.get(h.get("tr_key")) == h.get("tr_id"):
                            _subs.pop(h.get("tr_key"), None)
                            _want.pop(h.get("tr_key"), None)    # 다시 넣다 같은 거절을 되풀이하지 않게
        except Exception as e:          # 끊김 · 보내기 실패 — 닫고 위에서 다시 붙는다
            _err(e)
            if ws:
                ws.close()
            ws = None
            with _lock:
                _subs.clear()
            _stat["connected"] = False


def _on_data(text):
    """`0|H0UNCNT0|001|칸^칸^…` — 셋째가 건수다. 여러 건이면 마지막 건이 가장 새것이다."""
    parts = text.split("|", 3)
    if len(parts) < 4:
        return
    n = _num(parts[2], int) or 1
    fields = parts[3].split("^")
    per = len(fields) // n if n else len(fields)
    if per < 15:
        return
    row = _parse(fields[(n - 1) * per:n * per])
    if not row["code"] or not row["price"]:
        return
    with _cond:
        _seq[0] += 1
        row["seq"], row["at"] = _seq[0], time.time()
        _ticks[row["code"]] = row
        _stat["ticks"] += 1
        _cond.notify_all()


def want(code):
    """이 종목을 지금 누가 본다 — 등록하고 연결이 없으면 띄운다."""
    with _lock:
        _want[code] = time.monotonic()
        _sweep(time.monotonic())
        if _thread[0] is None:
            t = threading.Thread(target=_run, name="kis-ws", daemon=True)
            _thread[0] = t
            t.start()


def live(code, after_seq, hold):
    """새 체결(`seq` 가 `after_seq` 보다 큰 것)이 올 때까지 `hold` 초 기다린다 → 응답 dict."""
    want(code)
    hold = max(0.0, min(float(hold), LIVE_HOLD_SEC))
    with _cond:
        busy = _waiters[0] >= LIVE_MAX_WAITERS
        if not busy:
            _waiters[0] += 1
        try:
            end = time.monotonic() + (0.0 if busy else hold)
            while True:
                t = _ticks.get(code)
                if t and t["seq"] > after_seq and time.time() - t["at"] < LIVE_STALE_SEC:
                    return {"ok": True, "on": True, "changed": True, "tick": dict(t)}
                left = end - time.monotonic()
                if left <= 0:
                    return {"ok": True, "on": True, "changed": False, "connected": _stat["connected"],
                            "seq": t["seq"] if t else after_seq}
                _cond.wait(left)
        finally:
            if not busy:
                _waiters[0] -= 1


def stats():
    with _lock:
        return {"on": KIS_WS_ON, "connected": _stat["connected"], "codes": len(_subs),
                "wanted": len(_want), "maxCodes": LIVE_MAX_CODES, "waiters": _waiters[0],
                "connects": _stat["connects"], "ticks": _stat["ticks"], "rejects": _stat["rejects"],
                "lastError": _stat["lastError"], "lastErrorAt": _stat["lastErrorAt"],
                "nextTryAt": _stat["nextTryAt"]}
