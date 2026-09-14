#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""오류 문구에서 비밀을 지운다.

왜 있는가
  2026-09-14 에 OpenDART 인증키가 실제로 새어 나갔다. 코드에 키를 적은 것이
  아니다. 외부 호출이 실패했을 때 런타임이 만드는 오류 문구에 요청 주소가
  통째로 들어가는데, 그 주소에 `crtfc_key=...` 가 붙어 있었다. 그것을 그대로
  저장하고 상태 조회 응답으로 돌려줘서, 그 화면을 여는 사람이면 40자 인증키를
  볼 수 있었다.

  길이를 자르는 것(`str(e)[:120]`)으로는 막지 못한다. 키는 앞쪽에 온다.
  내용을 지워야 한다.

어떻게 막는가 — 두 겹이다
  1. 쿼리스트링 패턴 : "키처럼 생긴 자리" 의 값을 지운다 (우리 키가 아니어도)
  2. 설정값 직접 비교 : secrets.json 에 든 값 그 자체를 지운다
  한쪽이 놓쳐도 다른 쪽이 잡는다.

  2번은 secrets.json 의 **모든 값**을 훑는다. 이름을 가려 받지 않는다.
  알림을 끄면서 `bot_token` 을 `_off_bot_token` 으로 옮겨둔 적이 있는데,
  이름으로 찾으면 그런 것을 놓친다 (2026-09-14 확인).

쓰는 법
    from secrets_guard import safe_message, scrub
    except Exception as e:
        return safe_message(e)          # 사람에게 보여줄 문구
"""

import json
import os
import re
import time

HOLDINGS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS_PATH = os.path.join(HOLDINGS_DIR, "secrets.json")

# 값을 지울 최소 길이. 너무 짧은 값까지 지우면 (예: mode "vts")
# 멀쩡한 문구가 알아볼 수 없게 된다.
MIN_SECRET_LEN = 8

# "키처럼 생긴 자리". 우리 키가 아니어도 값을 지운다.
SECRET_QS = re.compile(
    r"([?&](?:crtfc_key|appkey|app_key|appsecret|app_secret|api_key"
    r"|access_token|token|secret|password|passwd|pwd)=)[^&\s\"']*",
    re.IGNORECASE,
)

MASK = "<가림>"

_cache = {"at": 0.0, "values": []}
_CACHE_TTL = 5.0          # 오류가 몰아칠 때 파일을 매번 읽지 않도록


def _secret_values():
    """secrets.json 에 든 모든 문자열 값. 이름은 보지 않는다.

    설정이 바뀌면(알림을 켜고 끄는 등) 몇 초 안에 따라간다.
    """
    now = time.monotonic()
    if now - _cache["at"] < _CACHE_TTL:
        return _cache["values"]

    values = []
    try:
        with open(SECRETS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = None

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif node is not None and not isinstance(node, bool):
            s = str(node)
            if len(s) >= MIN_SECRET_LEN:
                values.append(s)

    if data is not None:
        walk(data)

    # 긴 것부터 지운다. 짧은 값이 긴 값의 일부일 때 반쪽만 지워지는 것을 막는다.
    values.sort(key=len, reverse=True)
    _cache["at"] = now
    _cache["values"] = values
    return values


def scrub(text):
    """문구에서 비밀을 지운다. 어떤 문자열이든 넣어도 된다."""
    s = str(text if text is not None else "")
    s = SECRET_QS.sub(lambda m: m.group(1) + MASK, s)
    for v in _secret_values():
        if v in s:
            s = s.replace(v, MASK)
    return s


def safe_message(e, limit=160):
    """예외를 사람이 볼 문구로. 비밀은 지우고 길이도 줄인다."""
    return scrub(e)[:limit]


def forget():
    """설정을 방금 바꿨을 때 즉시 다시 읽게 한다 (설정 도구용)."""
    _cache["at"] = 0.0
