#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""한국투자증권(KIS) 앱키를 secrets.json 에 저장하고 즉시 연결을 확인한다.

입력받은 앱시크릿은 화면에 표시되지 않으며, secrets.json 은 .gitignore 에
등록되어 있어 깃에 올라가지 않는다.

실행: holdings 폴더에서  setup-kis.bat  더블클릭
"""

import getpass
import json
import os
import sys

# Windows 기본 콘솔(cp949)에서 한글 출력에 실패하지 않도록 고정한다.
for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kis_proxy  # noqa: E402

SECRETS_PATH = kis_proxy.SECRETS_PATH


def _mask(v):
    """앞 4자만 보여주고 나머지는 가린다. 붙여넣기 확인용."""
    if len(v) <= 8:
        return "(" + "*" * len(v) + ")"
    return "(%s%s)" % (v[:4], "*" * (len(v) - 4))


def ask(prompt, default=None):
    suffix = " [%s]" % default if default else ""
    while True:
        v = input("  %s%s: " % (prompt, suffix)).strip()
        if v:
            return v
        if default:
            return default
        print("     값을 입력해 주세요.")


def main():
    print()
    print("=" * 54)
    print("  한국투자증권 API 키 설정")
    print("=" * 54)
    print()

    if os.path.exists(SECRETS_PATH):
        print("  이미 저장된 키가 있습니다: secrets.json")
        if input("  새로 입력하시겠습니까? (y/N): ").strip().lower() != "y":
            print("  취소했습니다.")
            return 0
        print()

    print("  1) 어느 계좌의 키인가요?")
    print("     1. 모의투자")
    print("     2. 실전투자")
    choice = ask("번호 선택", "1")
    mode = "prod" if choice.strip() == "2" else "vts"
    print("     -> %s 로 설정합니다." % kis_proxy.MODE_LABEL[mode])
    print()

    print("  2) App Key 를 붙여넣어 주세요.")
    print("     (붙여넣기: 마우스 우클릭 또는 Ctrl+V, 그 다음 엔터)")
    app_key = ask("App Key")
    print("     -> %d자 입력되었습니다. %s" % (len(app_key), _mask(app_key)))
    print()

    print("  3) App Secret 을 붙여넣어 주세요.")
    print("     보안을 위해 화면에 아무것도 표시되지 않습니다.")
    print("     빈 화면이어도 정상이니, 붙여넣은 뒤 엔터를 누르세요.")
    app_secret = getpass.getpass("  App Secret: ").strip()
    while not app_secret:
        print("     입력된 값이 없습니다. 다시 붙여넣고 엔터를 눌러주세요.")
        app_secret = getpass.getpass("  App Secret: ").strip()
    print("     -> %d자 입력되었습니다. %s" % (len(app_secret), _mask(app_secret)))
    print()

    print("  4) 계좌번호 (잔고 조회에만 필요, 나중에 해도 됩니다)")
    account = input("  계좌번호 8자리-2자리 (건너뛰려면 엔터): ").strip()
    print()

    data = {"kis": {"mode": mode, "app_key": app_key, "app_secret": app_secret}}
    if account:
        data["kis"]["account"] = account

    with open(SECRETS_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("  저장 완료: secrets.json  (깃에 올라가지 않습니다)")
    print()

    return run_check()


def run_check():
    """저장된 키로 실제 연결을 확인한다."""
    print("-" * 54)
    print("  연결을 확인합니다...")
    print()
    try:
        cfg = kis_proxy.load_secrets()
    except RuntimeError as e:
        print("  [실패] %s" % e)
        return 1

    if not cfg:
        print("  [실패] secrets.json 이 없습니다.")
        print("         setup-kis.bat 을 먼저 실행해 주세요.")
        return 1

    print("  설정: %s / App Key %s" % (
        kis_proxy.MODE_LABEL[cfg["mode"]], _mask(cfg["app_key"])))
    print()

    try:
        kis_proxy.get_token(cfg)
        print("  [1/2] 접근토큰 발급 성공")
    except RuntimeError as e:
        print("  [1/2] 접근토큰 발급 실패")
        print("        %s" % e)
        print()
        print("  이럴 때 확인해 보세요.")
        print("   - App Key / App Secret 에 공백이나 줄바꿈이 섞이지 않았는지")
        print("   - 모의투자 키를 실전으로 고르지 않았는지 (반대도 마찬가지)")
        print("   - KIS Developers 에서 실전투자용 키를 실제로 발급받았는지")
        print("   - 발급 직후라면 반영에 몇 분 걸릴 수 있습니다")
        print()
        print("  키를 다시 넣으시려면 setup-kis.bat 을 실행하세요.")
        return 1

    try:
        info = kis_proxy.fetch_price(cfg, "005930")
        print("  [2/2] 시세 조회 성공")
        print()
        print("        삼성전자(005930)")
        print("        현재가 %s원  (전일대비 %s / %s%%)" % (
            format(info["price"], ",") if info["price"] else "-",
            format(info["change"], ",") if info["change"] is not None else "-",
            info["changePct"] if info["changePct"] is not None else "-",
        ))
        if info.get("per") is not None:
            print("        PER %s   PBR %s" % (info["per"], info["pbr"]))
    except RuntimeError as e:
        print("  [2/2] 시세 조회 실패")
        print("        %s" % e)
        return 1

    print()
    print("=" * 54)
    print("  정상입니다.")
    print("  preview.bat 을 실행하면 KIS 연동이 켜진 상태로 뜹니다.")
    print("=" * 54)
    return 0


if __name__ == "__main__":
    try:
        if "--check" in sys.argv:
            sys.exit(run_check())
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  취소했습니다.")
        sys.exit(1)
    except EOFError:
        print("\n  입력이 끊겨서 중단했습니다. setup-kis.bat 을 다시 실행해 주세요.")
        sys.exit(1)
