# -*- coding: utf-8 -*-
"""KJC 주문 컴퓨터 — 실행 시작점. 실행 파일은 이 파일을 묶어 만든다."""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from kjc_trader.app import main

if __name__ == "__main__":
    main()
