# -*- coding: utf-8 -*-
"""토스증권 Open API 연결 (2026-10-07 재권님 지시 — 「토큰 받아 놨으니 연결할 수 있게」).

**지금은 연결 확인 하나뿐이다.** 화면에는 아직 아무것도 안 올린다 — `/api/toss/health` 가
현재가를 한 번 불러 「연결됨」 만 낸다. 무엇을 토스에서 받을지는 그 다음에 정한다.

── 공식 명세 (openapi.tossinvest.com/openapi-docs/latest/openapi.json · v1.2.19 · 2026-10-07 직접 읽음) ──

    토큰    POST https://openapi.tossinvest.com/oauth2/token
            form: grant_type=client_credentials · client_id · client_secret
            → access_token(JWT) · token_type Bearer · expires_in(초 · 예시 86400) · refresh 없음
    호출    Authorization: Bearer {access_token}
    현재가  GET /api/v1/prices?symbols=005930,000660   최대 200
    한도    인증 5/초 · 시세 15/초 (holdings/docs/sources.json)

⚠️ **client 하나에 살아 있는 토큰은 하나다 — 다시 받으면 앞 토큰이 바로 무효가 된다** (명세 원문).
서버가 여럿(8765 · 8764 · 세션 서버)이라 제각각 받으면 서로 끊는다. 그래서 **토큰은 8765(MAIN_PORT)
하나만 받는다** — 신호 · 공시를 8765 만 보내는 것과 같은 자리다. 다른 서버는 토스를 부르지 않는다.

── 키는 어디에 ──

`holdings/secrets.json` 의 `toss` 칸 — client_id · client_secret · access_token(비워 두면 서버가 받는다).
access_token 이 차 있으면 그것을 먼저 쓰고, 401 이면 client_id · secret 으로 새로 받는다.
**키 · 토큰은 응답 · 로그에 안 나간다** — 오류 문구는 `secrets_guard.safe_message` 를 거치고, 서버가 받은
토큰은 파일에 없으므로 따로 지운다.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from secrets_guard import safe_message

BASE = "https://openapi.tossinvest.com"
SECRETS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "secrets.json")
RENEW_BEFORE = 600            # 만료 10분 전에 다시 받는다
TIMEOUT = 10

_lock = threading.Lock()
_last_code = [None]          # 바로 앞 시도의 상태 코드 — 401 일 때만 토큰을 새로 받는다
_tok = {"value": None, "until": 0.0, "from": None}     # from: 「붙여넣은 것」 · 「서버가 받은 것」


def _conf():
    try:
        with open(SECRETS_PATH, encoding="utf-8") as f:
            t = (json.load(f) or {}).get("toss") or {}
    except (OSError, ValueError):
        return None
    if not (t.get("client_id") and t.get("client_secret")):
        return None
    return t


def _hide(text):
    """오류 문구에서 키 · 토큰을 지운다. 서버가 받은 토큰은 secrets.json 에 없어 따로 지운다."""
    s = safe_message(text, 200)
    if _tok["value"]:
        s = s.replace(_tok["value"], "<가림>")
    return s


def _issue(conf):
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": conf["client_id"],
        "client_secret": conf["client_secret"],
    }).encode()
    req = urllib.request.Request(BASE + "/oauth2/token", data=body, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        j = json.loads(r.read().decode("utf-8"))
    _tok.update(value=j["access_token"],
                until=time.time() + int(j.get("expires_in") or 3600),
                **{"from": "서버가 받은 것"})


def _token(conf, renew=False):
    with _lock:
        if renew:
            _tok.update(value=None, until=0.0)
        if not _tok["value"]:
            pasted = (conf.get("access_token") or "").strip()
            if pasted and not renew:
                # 붙여넣은 토큰은 만료 시각을 모른다 — 401 이 오면 그때 새로 받는다
                _tok.update(value=pasted, until=float("inf"), **{"from": "붙여넣은 것"})
            else:
                _issue(conf)
        elif time.time() > _tok["until"] - RENEW_BEFORE:
            _issue(conf)
        return _tok["value"]


# 상태 코드마다 무엇을 뜻하나 — 재권님이 붙여 주신 공식 문서(2026-10-07 · temp/작업우선순위-toss-openapi-doc.md)
HINT = {
    401: "토큰이 무효(다른 곳에서 새로 받으면 앞 것이 끊긴다 · token-revoked)",
    403: "허용 IP 목록 밖일 수 있음 — 토스 설정 > Open API > 허용 IP 관리 · 맥미니 공인 IP 가 바뀌면 여기서 걸린다",
    429: "초당 한도 넘음 — Retry-After 만큼 기다렸다 다시",
}


def get(path, params=None):
    """토스 GET. 401 이면 한 번 새 토큰으로, 429 면 Retry-After(최대 4초)만큼 쉬고 한 번 다시 부른다.
    실패하면 예외(문구는 가려서 · 상태 코드 뜻을 붙여서)."""
    conf = _conf()
    if not conf:
        raise RuntimeError("secrets.json 의 toss 칸에 client_id · client_secret 이 없습니다")
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in (0, 1):
        tok = _token(conf, renew=attempt == 1 and _last_code[0] == 401)
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            _last_code[0] = e.code
            if attempt == 0 and e.code == 401:
                continue
            if attempt == 0 and e.code == 429:
                try:
                    wait = float(e.headers.get("Retry-After") or 1)
                except ValueError:
                    wait = 1.0
                time.sleep(min(max(wait, 0.2), 4.0))
                continue
            raise RuntimeError("토스 %d (%s) — %s" % (e.code, HINT.get(e.code, "그 밖"),
                                                    _hide(e.read().decode("utf-8", "replace")[:200])))
    raise RuntimeError("토스 401 — 새 토큰으로도 거절")


def health(main_only_ok):
    """연결 확인 — 현재가 한 번. 키 · 토큰은 안 낸다.

    main_only_ok: 이 서버가 토큰을 받아도 되는 자리인가(8765). 아니면 부르지 않는다.
    """
    if not main_only_ok:
        return {"ok": False, "connected": None,
                "error": "토스는 8765 에서만 부릅니다 — 키 하나에 토큰이 하나라 서버마다 받으면 서로 끊습니다"}
    if not _conf():
        return {"ok": False, "connected": False, "error": "secrets.json 의 toss 칸에 client_id · client_secret 이 없습니다"}
    try:
        j = get("/api/v1/prices", {"symbols": "005930"})
    except Exception as e:
        return {"ok": False, "connected": False, "error": _hide(e)}
    return {"ok": True, "connected": True, "token": _tok["from"],
            "sample": {"symbol": "005930", "body": _first(j)}}


def _first(j):
    """현재가 응답에서 첫 줄만 — 모양을 아직 안 정했으므로 있는 그대로 짧게."""
    d = j.get("result") if isinstance(j, dict) else None
    d = d if d is not None else (j.get("data") if isinstance(j, dict) else j)
    if isinstance(d, list):
        d = d[0] if d else None
    return d
