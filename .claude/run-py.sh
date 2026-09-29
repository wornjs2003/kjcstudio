#!/bin/sh
# 파이썬을 **있는 이름으로** 부른다.
#
# 맥에는 `python3` 만 있고 윈도우에는 `python` 만 있다. 한쪽 이름을 박으면
# **다른 기계에서 조용히 안 돈다** — 2026-09-28~29 에 같은 병이 셋 났다
# (`statusline.sh` · `.githooks/pre-commit` · `settings.json` 의 편집 감시 훅).
#
# 훅은 실패해도 아무 말이 없어서, 안 도는 것을 **몇 달 뒤에야** 알게 된다.
if command -v python3 >/dev/null 2>&1; then exec python3 "$@"; fi
if command -v python  >/dev/null 2>&1; then exec python  "$@"; fi
exit 0   # 파이썬이 없으면 조용히 넘어간다 — 훅이 작업을 막으면 안 된다
