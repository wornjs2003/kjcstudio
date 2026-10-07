# -*- coding: utf-8 -*-
"""확인란에 그림 · 화면 파일 경로를 드리면 턴 끝에서 잡는다 — Stop 훅 (2026-10-06 지시).

재권님 말씀 — 「주소 클릭하면 herdr 에서 보여지는데 크롬으로 열리도록 해달라했잖아.
룰체크하고 이 룰 개념정의한테 전달해서 훅 만들어 달라해」(16:2x · 시황분석 창). 확인란에
`/private/tmp/…/insight-mock-1612.png` 를 드렸더니 Herdr 가 자기 뷰어로 열었다. Herdr 는
파일 경로를 자기 뷰어로 열고 `http` 주소만 크롬으로 넘긴다.

룰은 CLAUDE.md 「재권님이 확인하실 것은 맨 아래에 둔다」 의 「그림 · 화면은 http 주소로 드린다」.

무엇을 세나 — 마지막 답의 **확인란 줄(`▶` 로 시작)** 만. 본문은 안 센다 — 재권님이 손으로
돌리실 `.command` 처럼 전체 경로를 드려야 하는 정상 안내가 본문에 있다(창구 검토).
  걸리는 것 — `/` · `~` · `file://` 로 시작하고 끝이 그림 · 화면 확장자(png · jpg · gif · webp · svg · html)인 경로.
  안 걸리는 것 — `http(s)://` 주소 안의 경로 · `.command` · `.md` 같은 그 밖 확장자 · 본문.

외부접속일 때는 `localhost` 주소가 안 열려 파일을 보낸다(SendUserFile). 그때 「보냈습니다: <경로>」
를 확인란에 넣으면 걸린다 — 그 줄은 본문에 둔다.

둘째 — 확인란 줄의 `holdings/stock.html` 은 알리기만 한다(2026-10-07 · 「홀딩스 작업은 홈 첫 화면으로 보여 드린다」).

걸리면 턴을 끝내지 않고(decision: block) 「http 주소로 다시」 를 돌려준다. 같은 턴에 두 번 막지 않는다
(`stop_hook_active`). `KJC_LINK_HOOK=block|look|off` — 기본은 알리기만.
"""
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODE = os.environ.get("KJC_LINK_HOOK", "look")
CONFIRM = re.compile(r"^\s*(?:[-*>]\s*)?(?:\*\*)?▶")    # 확인란 줄 — 목록 · 인용 · 굵게 꼴도
# 앞이 글자 · 콜론 · 슬래시 · 점이면 주소 안의 경로다(http://localhost:8771/temp/x.png 의 /temp/x.png) — 안 센다
PATH = re.compile(r"(?<![\w:/.])(?:file://)?(?:~|/)[^\s`'\"()<>]*?\.(?:png|jpe?g|gif|webp|svg|html?)\b", re.I)


def find(text):
    hits = []
    for line in (text or "").splitlines():
        if CONFIRM.match(line):
            hits += PATH.findall(line)
    return hits


def last_text(path):
    """입력에 마지막 답이 없을 때만 기록 파일 끝에서 찾는다."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - (1 << 20)))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("type") != "assistant" or r.get("isSidechain"):
            continue
        t = [b.get("text", "") for b in (r.get("message") or {}).get("content") or []
             if isinstance(b, dict) and b.get("type") == "text"]
        if any(x.strip() for x in t):
            return "\n".join(t)
    return ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if MODE == "off" or data.get("stop_hook_active"):
        return 0
    text = data.get("last_assistant_message") or last_text(data.get("transcript_path") or "")
    hits = find(text)
    if not hits:
        # 홀딩스 종목 화면 링크 — 알리기만 (2026-10-07 지시 · CLAUDE.md 「홀딩스 작업은 홈 첫 화면으로 보여 드린다」).
        # 종목 화면 자체를 고친 때는 맞는 링크라 막지 않는다
        if any(CONFIRM.match(l) and "holdings/stock.html" in l for l in (text or "").splitlines()):
            print(json.dumps({"systemMessage":
                "확인란에 종목 화면(holdings/stock.html) 링크가 있습니다 — 홀딩스 일은 홈 첫 화면(/holdings/)으로 보여 드립니다. "
                "모달이면 /holdings/?code=<종목>. 종목 화면 자체를 고쳤으면 지나가도 됩니다 "
                "(CLAUDE.md 「홀딩스 작업은 홈 첫 화면으로 보여 드린다」)."}, ensure_ascii=False))
        return 0
    reason = ("확인란에 파일 경로가 있습니다 — Herdr 는 파일 경로를 자기 뷰어로 열고 크롬으로 안 넘깁니다. "
              "CLAUDE.md 「그림 · 화면은 http 주소로 드린다」. 파일을 저장소 temp/ 에 두고 "
              "`http://localhost:<포트>/temp/<세션이름>-<무엇>.png` 꼴로 백틱에 감싸 다시 써 주십시오 "
              "(메인 폴더 세션은 8765 · 외부접속이면 파일을 보내고 그 말은 본문에).\n"
              + "\n".join("  · " + h for h in hits[:5]))
    if MODE == "block":
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    else:
        print(json.dumps({"systemMessage": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
