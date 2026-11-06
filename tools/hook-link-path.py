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

셋째 — 주소 바로 뒤에 붙은 글자(2026-11-06 재권님 「…market.html로 이렇게 주면 링크열때 에러나잖아」 · 「주소는 백틱으로 감싼다」 아래 줄).
  확인란 줄 — 백틱으로 감싼 http 주소의 닫는 백틱 바로 뒤가 띄어쓰기 · 줄 끝이 아니면 막는다(괄호 · 마침표 · 쉼표도 · 누르면 그 글자까지 주소로 잡힌다).
  본문 줄 — 같은 꼴을 알리기만. 긴 한글 주소(한글 GLUE_HANGUL 자 넘게)는 줄이 꺾여 앞부분만 눌릴 수 있어 알리기만.
  안 세는 것 — 코드블록 안 · 「 」 인용 안 · 백틱 없는 맨 주소(hook-confirm-box 의 「백틱 없는 http」 가 잡는다).

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


# 찍은 그림 원본 — 확인란 ▶ 줄에 temp/….png 주소가 있고, 그 그림 옆에 같은 이름의 -보기.html 이 디스크에 있으면 알린다
# (2026-10-14 「찍은 그림은 창에 맞춰 한눈에 보이게 드린다」). 보기 페이지가 없는 그림(shot 밖)은 안 센다. 「확대해서」 줄은 안 센다
TEMP_PNG = re.compile(r"/temp/([^\s`'\"()<>?#]+?\.png)", re.I)
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")


def raw_pngs(text):
    from urllib.parse import unquote
    out = []
    for l in (text or "").splitlines():
        if not CONFIRM.match(l) or "확대해서" in l:
            continue
        for m in TEMP_PNG.findall(l):
            name = unquote(m)
            stem = os.path.splitext(os.path.basename(name))[0]
            if os.path.exists(os.path.join(TEMP_DIR, os.path.dirname(name), stem + "-보기.html")):
                out.append(name)
    return out


TEMP_VIEW = re.compile(r"/temp/([^\s`'\"()<>?#]+?-%EB%B3%B4%EA%B8%B0\.html|[^\s`'\"()<>?#]+?-보기\.html)", re.I)
SHOT_URL = re.compile(r'<meta name="kjc-shot-url" content="([^"]*)"')


def stock_views(text):
    """확인란 줄의 보기 페이지 중 종목 화면(holdings/stock.html)을 찍은 것 — shot.py 가 남긴 kjc-shot-url 로 가른다 (2026-11-06)."""
    from urllib.parse import unquote
    out = []
    for l in (text or "").splitlines():
        if not CONFIRM.match(l):
            continue
        for m in TEMP_VIEW.findall(l):
            name = unquote(m)
            try:
                head = open(os.path.join(TEMP_DIR, name), encoding="utf-8").read(2000)
            except Exception:
                continue
            u = SHOT_URL.search(head)
            if u and "holdings/stock.html" in u.group(1):
                out.append(name)
    return out


GLUED = re.compile(r"`(https?://[^`\s]+)`(?=[^\s])")
# 확인란 줄은 닫는 백틱 뒤에 무엇이든 붙으면 막는다 — 괄호 · 마침표 · 쉼표도(11-06 재권님 「나 처럼 링크주면 에러난다고 몇번을 말하지?」 ·
# 열리는지 꼴마다 가리지 않는다 · 한 칸 띄우면 끝이라 싸다)
TICK_URL = re.compile(r"`(https?://[^`\s]+)`")
GLUE_HANGUL = 20                # 주소 안 한글이 이만큼 넘으면 줄이 꺾여 앞부분만 눌릴 수 있다(10-14 「긴 한글 주소는 403」)


def glued(text):
    """(확인란 줄 붙은 주소, 본문 줄 붙은 주소, 긴 한글 주소) — 코드블록 · 「 」 안은 뺀다."""
    from urllib.parse import unquote
    box, body, long_ = [], [], []
    fence = False
    for l in (text or "").splitlines():
        if l.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        line = re.sub(r"「[^」]*」", "", l)
        for m in GLUED.finditer(line):
            nxt = line[m.end():m.end() + 1]
            (box if CONFIRM.match(l) else body).append(m.group(1))
        for u in TICK_URL.findall(line):
            if sum(1 for ch in unquote(u) if "\uac00" <= ch <= "\ud7a3") > GLUE_HANGUL:
                long_.append(u)
    return box, body, long_


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if MODE == "off" or data.get("stop_hook_active"):
        return 0
    text = data.get("last_assistant_message") or last_text(data.get("transcript_path") or "")
    gbox, gbody, glong = glued(text)
    if gbox and MODE == "block":
        print(json.dumps({"decision": "block", "reason":
            "확인란 주소 바로 뒤에 글자가 붙어 있습니다 — 누르면 그 글자까지 주소로 잡혀 안 열립니다. 닫는 백틱 뒤를 한 칸 띄우거나 "
            "주소를 줄 끝에 두고 다시 써 주십시오(CLAUDE.md 「주소는 백틱으로 감싼다」 아래 「주소 바로 뒤에 글자를 붙이지 않는다」).\n"
            + "\n".join("  · " + u for u in gbox[:5])}, ensure_ascii=False))
        return 0
    hits = find(text)
    if not hits:
        notes = []
        # 홀딩스 종목 화면 링크 — 알리기만 (2026-10-07 지시 · CLAUDE.md 「홀딩스 작업은 홈 첫 화면으로 보여 드린다」).
        # 종목 화면 자체를 고친 때는 맞는 링크라 막지 않는다
        if any(CONFIRM.match(l) and "holdings/stock.html" in l for l in (text or "").splitlines()):
            notes.append("확인란에 종목 화면(holdings/stock.html) 링크가 있습니다 — 홀딩스 일은 홈 첫 화면(/holdings/)으로 보여 드립니다. "
                         "모달이면 /holdings/?code=<종목>. 종목 화면 자체를 고쳤으면 지나가도 됩니다 "
                         "(CLAUDE.md 「홀딩스 작업은 홈 첫 화면으로 보여 드린다」).")
        if gbox or gbody:
            notes.append("주소 바로 뒤에 글자가 붙어 있습니다 — " + " · ".join((gbox + gbody)[:3]) + ". 한 칸 띄우거나 주소를 줄 끝에 두십시오.")
        if glong:
            notes.append("한글이 긴 주소가 있습니다 — 줄이 꺾여 앞부분만 눌릴 수 있습니다(403). 파일 이름을 짧게 해 주십시오: " + " · ".join(glong[:2]))
        sv = stock_views(text)
        if sv:
            notes.append("확인란 그림이 종목 화면(holdings/stock.html)을 찍은 것입니다 — " + " · ".join(sv[:3]) + ". 홀딩스 일은 "
                         "홈 큰 차트(/holdings/) + 모달(/holdings/?code=<종목>) 그림으로 다시 드려 주십시오 · 종목 화면은 check-layout 값과 줄 꺾임을 글로. "
                         "종목 화면 자체를 고쳤으면 지나가도 됩니다(CLAUDE.md 「홀딩스 작업은 홈 첫 화면으로 보여 드린다」).")
        raw = raw_pngs(text)
        if raw:
            notes.append("확인란에 찍은 그림 원본 주소가 있습니다 — 그대로 열면 배율만큼 화면보다 크게 보입니다. 옆에 있는 보기 페이지 주소로 "
                         "드려 주십시오: " + " · ".join(raw[:3]) + " (CLAUDE.md 「찍은 그림은 창에 맞춰 한눈에 보이게 드린다」 · "
                         "크게 보셔야 하는 그림이면 「확대해서 보시려면」 줄로 덧붙인 것은 안 셉니다).")
        if notes:
            print(json.dumps({"systemMessage": "\n".join(notes)}, ensure_ascii=False))
        return 0
    reason = ("확인란에 파일 경로가 있습니다 — Herdr 는 파일 경로를 자기 뷰어로 열고 크롬으로 안 넘깁니다. "
              "CLAUDE.md 「그림 · 화면은 http 주소로 드린다」. 파일을 저장소 temp/ 에 두고 "
              "`http://localhost:<포트>/temp/<세션이름>-<무엇>.png` 꼴로 백틱에 감싸 다시 써 주십시오 "
              "(개발 폴더 세션은 8765 · 외부접속이면 파일을 보내고 그 말은 본문에).\n"
              + "\n".join("  · " + h for h in hits[:5]))
    if MODE == "block":
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    else:
        print(json.dumps({"systemMessage": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
