#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenDART 인증키를 secrets.json 에 저장하고 바로 확인한다.

입력한 키는 화면에 보이지 않는다. secrets.json 은 .gitignore 에 있어
깃에 올라가지 않는다. 키를 채팅창이나 메일에 붙여넣지 말 것.

인증키는 https://opendart.fss.or.kr 에서 발급받는다 (40자리).
"""

import getpass
import io
import json
import os
import sys
import urllib.parse
import urllib.request

# Windows 기본 콘솔(cp949)에서 한글 출력에 실패하지 않도록 고정한다.
# **없으면 조용히 깨진다** — 2026-09-21 에 setup-dart.bat 을 cp949 셸에서
# 돌렸더니 「OpenDART 인증키 설정」 이 「OpenDART ����Ű ����」 로 나왔다.
# setup_kis.py 에는 있고 이 파일에는 없어서 둘이 갈려 있었다.
for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass

# 오류 문구에서 비밀을 지운다. 이 파일은 인증키를 주소에 담아 부르므로,
# 예외 문구에 주소가 섞이면 키가 화면에 찍힌다.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from docstore import read_json, write_json_atomic
from secrets_guard import forget, safe_message

HERE = os.path.dirname(os.path.abspath(__file__))
HOLDINGS_DIR = os.path.dirname(HERE)
SECRETS = os.path.join(HOLDINGS_DIR, "secrets.json")

KEY_LEN = 40


def load():
    if not os.path.exists(SECRETS):
        return {}
    # 없거나 깨졌으면 {} — 가르는 것은 read_json 한 곳이다
    return read_json(SECRETS, {}) or {}


def save(data):
    """**안전하게** 쓴다 (2026-09-22 지시).

    전에는 `io.open(SECRETS, "w")` 로 바로 덮어썼다. 그 한 줄이 **여는
    순간 파일을 비우므로**, 거기서 죽으면 KIS·DART 키가 통째로 날아간다.
    gitignore 라 저장소에도 없어 **되살릴 곳이 없다.**

    `write_json_atomic` 은 임시 파일에 다 쓰고 `os.replace` 로 옮긴다 —
    쓰다 죽어도 옛 내용이 그대로 남는다 (docstore.py 참고).
    """
    write_json_atomic(SECRETS, data)


def check(key):
    """실제로 한 번 불러서 키가 살아 있는지 본다.

    OpenDART 는 키가 틀려도 HTTP 200 을 주고 본문의 status 로 알려준다.
      000 정상 · 010 등록되지 않은 인증키 · 011 사용할 수 없는 키
      013 조회된 데이터 없음 (키는 정상)
    """
    url = "https://opendart.fss.or.kr/api/list.json?" + urllib.parse.urlencode({
        "crtfc_key": key,
        "bgn_de": "20260101",
        "end_de": "20260101",
        "page_count": "1",
    })
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            body = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return None, "연결 실패: %s" % safe_message(e, 80)

    status = body.get("status")
    message = body.get("message") or ""
    if status in ("000", "013"):
        return True, "정상"
    return False, "%s %s" % (status, message)


def main():
    print()
    print("  OpenDART 인증키 설정")
    print("  " + "-" * 46)
    print("  발급: https://opendart.fss.or.kr  (무료, 40자리)")
    print("  입력한 키는 화면에 보이지 않습니다.")
    print()

    data = load()
    if (data.get("dart") or {}).get("api_key"):
        print("  이미 저장된 키가 있습니다.")
        if input("  새로 입력하시겠습니까? (y/N): ").strip().lower() != "y":
            print()
            key = data["dart"]["api_key"]
            ok, msg = check(key)
            print("  확인: %s" % ("정상입니다" if ok else "문제 있음 — " + msg))
            return 0 if ok else 1
        print()

    print("  인증키를 붙여넣고 엔터를 누르세요.")
    print("  ※ 입력 중에는 글자가 보이지 않습니다. 붙여넣은 뒤 그냥 엔터를 치면 됩니다.")
    print("     (붙여넣기: 마우스 오른쪽 버튼 또는 Ctrl+V)")
    print()

    while True:
        key = getpass.getpass("  인증키: ").strip()
        print("  → %d 자를 받았습니다." % len(key))
        if len(key) == KEY_LEN:
            break
        if len(key) == 0:
            print("     아무것도 안 들어왔습니다. 붙여넣기가 됐는지 확인해 주세요.")
        else:
            print("     40자여야 합니다. 앞뒤 공백이나 줄바꿈이 섞였거나,")
            print("     여러 번 붙여넣어져 길어졌을 수 있습니다.")
        print()

    print()
    print("  확인 중…  (%s…%s)" % (key[:2], key[-2:]))
    ok, msg = check(key)
    if not ok:
        print()
        print("  [실패] %s" % msg)
        print("  저장하지 않았습니다.")
        print()
        if msg.startswith("010"):
            print("  → OpenDART 에 등록되지 않은 키입니다. 키를 다시 확인해 주세요.")
            print("     https://opendart.fss.or.kr 로그인 후 [오픈API 이용현황] 에서 볼 수 있습니다.")
        elif msg.startswith("011"):
            print("  → 사용할 수 없는 키입니다. 발급 상태를 확인해 주세요.")
        else:
            print("  → 인터넷 연결이나 방화벽을 확인해 주세요.")
        return 1

    data.setdefault("dart", {})["api_key"] = key
    save(data)
    forget()        # 방금 넣은 키도 이제부터 가려야 한다
    print("  [성공] 키가 살아 있습니다.")
    print("  저장 완료: secrets.json  (깃에 올라가지 않습니다)")
    print()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  취소했습니다.")
        sys.exit(1)
