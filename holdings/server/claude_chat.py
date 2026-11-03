#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""홀딩스 오른쪽 Claude 창 — 서버가 맥미니에 로그인된 claude 를 한 번씩 부른다.

2026-11-03 재권님 「홀딩스 창에 클로드 연결하기 위해 준비한 것들 있는데 이거 이제 연결해야 할 거 같아」 →
길 둘((가) 맥미니 claude · (나) API 키)을 여쭈어 「가로 해줘 나중에 나를 고민해보자」.

어떻게 도나
  화면(claude-rail.js) → POST /api/claude/ask → 여기 ask() → `claude -p` 한 번 → 글 하나를 돌려준다.
  미국 섹터 아침 도구(company-setup/tools/us-sector-morning.py)가 쓰는 길과 같다 — 키가 없고 그 계정 사용량에서 나간다.

  - 기록을 남기지 않는다(`--no-session-persistence`) · 도구와 띄우는 폴더는 아래 18:5x 바꿈
  - 한 번에 쓰는 돈의 상한은 BUDGET_USD — 넘으면 claude 가 스스로 멈춘다
  - **한 번에 하나만** — 물음마다 프로그램이 새로 뜨므로 겹치면 맥미니가 무거워진다. 돌고 있으면 Busy
  - 앞 대화는 화면이 들고 와서 함께 보낸다(서버는 대화를 저장하지 않는다 · 화면이 이 브라우저에 남긴다)
  - 시세 숫자는 화면이 아니라 서버가 붙인다 — kis_proxy 가 quote 로 넘긴다

(나) API 키 길은 「나중에 고민」 — 그때 이 파일의 _run 만 바꾸면 화면 · 주소는 그대로다.

2026-11-03 18:5x 바꿈 — 재권님 외부접속에서 「오늘 코스피 폭락인데 이유 찾아봐」 → 도구가 없어 「못 찾는다」 →
「이건 의도한게 아닌데?」 · 「만들어놓은 룰을 참고해서 알아보게끔 … 질문에 맞는 룰을 찾아서 알아봐주고」 → 「응 그렇게 해」.
  - **그 서버의 저장소 폴더에서 띄운다**(REPO) — 세션처럼 CLAUDE.md · holdings/CLAUDE.md · 스킬을 읽고 시작한다.
    --safe-mode 를 뺐다(그것이 룰을 안 읽게 했다). 개발 서버(8765)는 개발 폴더, 메인(8764)은 서비스방 폴더다
  - **도구는 읽기만** — 파일 읽기 · 찾기 · 웹 검색 · 웹 읽기(TOOLS). 명령 실행 · 파일 고치기는 없다(목록에 없으면 못 쓴다)
  - 지수(코스피 · 코스닥)도 서버가 붙인다 — kis_proxy 가 indices 로 넘긴다
  - 창에서 답하는 법(맞는 룰을 찾아 따르고 근거를 붙인다)은 창 지침서(스킬)가 정한다 — 개념정의 몫 · 그 전까지는 SYSTEM 이 대신한다
"""

import json
import os
import shutil
import subprocess
import threading
import time

from secrets_guard import safe_message

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 저장소 폴더(holdings/server 의 두 칸 위)
TOOLS = "Read,Grep,Glob,WebSearch,WebFetch"
# 띄울 때의 설정 — 세션용 훅은 끄고(확인란 · 한국어 · 보드 훅이 창 답을 붙잡거나 줄을 덧붙였다) 비밀 · 데이터 파일 읽기를 거부한다.
# 왜 거부가 필요한가(2026-11-03 개념정의 검수): 읽기 도구와 웹 읽기를 함께 쥐면, 웹에서 읽은 글 속 지시로 비밀 파일을 읽어 웹 주소에
# 실어 내보낼 길이 생긴다. 훅을 끄면 메인 가드도 안 돕는다.
#   - 저장소 폴더 밖은 「물어야 읽는」 자리라 -p 에서는 저절로 거부된다 — 그래서 Read · Grep · Glob 은 --allowedTools 에 안 넣는다
#   - 폴더 안 · 밖의 비밀 · 데이터는 아래 거부 규칙이 막는다(거부는 허용보다 먼저다)
#   - --restricted 는 안 쓴다 — 그것은 CLAUDE.md 까지 안 읽게 해 룰을 못 찾는다(같은 날 실측)
# 잰 것(가짜 파일 · Haiku): secrets.json · 토큰 캐시 · .db · logs · .env · ~/.kjc · /tmp · 홈의 폴더 밖 파일 전부 「못 읽음」 · 보통 파일 읽힘 · CLAUDE.md 들어옴
SETTINGS = json.dumps({"disableAllHooks": True, "permissions": {"deny": [
    "Read(**/secrets*.json)", "Read(**/.kis-token-cache*)", "Read(**/*.db)", "Read(**/*.db-*)", "Read(**/logs/**)",
    "Read(**/holdings/data/**)", "Read(**/.env*)", "Read(~/.kjc/**)", "Read(~/.ssh/**)", "Read(~/.claude/**)",
    "Read(//tmp/**)", "Read(//private/tmp/**)", "Read(**/.claude/settings*.json)", "Read(**/.git/**)"]}})
AUTO_OK = ["WebSearch", "WebFetch"]   # 묻지 않고 쓰는 도구 — 파일 도구는 폴더 안만 저절로 된다

PATH_ADD = ["/opt/homebrew/bin", os.path.expanduser("~/.local/bin"), "/usr/local/bin"]
MODEL = "claude-opus-5-5"  # 재권님 「opus 5.5」(11-03 18:5x) — 같은 물음 실측 29초 · 1.62달러(Sonnet 38초 0.88 · Haiku 33초 0.25)
BUDGET_USD = "3"          # 한 물음에 이 이상 쓰면 claude 가 스스로 멈춘다
TIMEOUT = 300             # 초 — 이보다 오래 걸리면 끊고 「못 받음」
MAX_QUESTION = 2000       # 글자 — 물음 한 번
MAX_HISTORY = 12          # 앞 대화 몇 줄까지 함께 보내나(물음 · 답 한 줄씩)
MAX_HISTORY_CHARS = 1500  # 앞 대화 한 줄의 글자 상한

SYSTEM = (
    "너는 KJC Holdings 주식 화면 오른쪽 창의 도우미다. 상대는 이 화면을 보는 재권님이다.\n"
    "- 한국어로만, 존댓말로, 짧게 답한다. 표 · 제목(#) 같은 꾸밈 없이 문장과 줄바꿈만 쓴다.\n"
    "- 먼저 이 저장소의 룰(CLAUDE.md · holdings/CLAUDE.md · .claude/skills)에서 물음에 맞는 것을 찾아 그 룰대로 알아본다. 파일은 읽기만 한다.\n"
    "- 시세 · 지수 숫자는 아래 「화면」 에 준 값(서버가 방금 받은 것)을 쓴다. 거기 없는 숫자는 지어내지 말고 「지금 받은 값에 없다」 고 말한다.\n"
    "- 오늘 뉴스 · 까닭은 웹 검색으로 찾고, 확인한 기사 주소를 답 끝에 붙인다. 못 찾으면 못 찾았다고 말한다.\n"
    "- 답 끝에 근거로 삼은 룰이 있으면 그 절 이름을 한 줄로 적는다.\n"
    "- 너는 세션이 아니라 화면 옆 창이다. 세션끼리의 일(보드 카드 · 커밋 · 확인란 줄 · 「지금 답하실 것은 없습니다」)은 하지도 쓰지도 않는다.\n"
    "- 사라 · 팔라는 말은 하지 않는다. 판단 재료와 볼 점을 말한다."
)

_lock = threading.Lock()
_stat = {"calls": 0, "fails": 0, "lastAt": None, "lastSecs": None, "lastError": None}


class Busy(Exception):
    """다른 물음이 돌고 있다."""


def _claude():
    p = shutil.which("claude", path=os.pathsep.join(PATH_ADD + [os.environ.get("PATH", "")]))
    if not p:
        raise RuntimeError("claude 를 못 찾았습니다(PATH) — 맥미니에 claude 가 설치 · 로그인돼 있어야 합니다")
    return p


def _prompt(question, ctx, history, quote, indices=None):
    screen = {"보는 화면": ctx or {}}
    if indices:
        screen["지수(서버가 방금 받은 값)"] = indices
    if quote:
        keep = ("price", "change", "changePct", "open", "high", "low", "volume", "value",
                "marketCap", "per", "pbr", "eps", "bps", "high52", "low52")
        screen["시세(서버가 방금 받은 값 · 원)"] = {k: quote.get(k) for k in keep if quote.get(k) is not None}
    lines = ["화면:", json.dumps(screen, ensure_ascii=False)]
    talk = [h for h in (history or []) if isinstance(h, dict) and h.get("text")][-MAX_HISTORY:]
    if talk:
        lines.append("\n앞 대화:")
        for h in talk:
            who = "재권님" if h.get("who") == "me" else "너"
            lines.append("%s: %s" % (who, str(h["text"])[:MAX_HISTORY_CHARS]))
    lines.append("\n물음: " + question)
    return "\n".join(lines)


def _run(prompt):
    r = subprocess.run([_claude(), "-p", "--model", MODEL, "--tools", TOOLS, "--allowedTools", *AUTO_OK,
                        "--no-session-persistence", "--settings", SETTINGS, "--output-format", "json", "--max-budget-usd", BUDGET_USD,
                        "--append-system-prompt", SYSTEM],
                       input=prompt, capture_output=True, text=True, timeout=TIMEOUT, cwd=REPO)
    try:
        out = json.loads(r.stdout)
    except ValueError:
        raise RuntimeError("claude 종료 %d · 글이 아닌 응답" % r.returncode)
    if r.returncode != 0 or out.get("is_error"):
        raise RuntimeError("claude 종료 %d · %s" % (r.returncode, str(out.get("result") or out.get("subtype") or "")[:200]))
    text = (out.get("result") or "").strip()
    if not text:
        raise RuntimeError("claude 가 빈 답을 냈습니다")
    return text, out.get("total_cost_usd")


def ask(question, ctx=None, history=None, quote=None, indices=None):
    """물음 하나 → {"text", "secs", "costUsd"}. 돌고 있으면 Busy · 실패면 RuntimeError(문구는 가린 것)."""
    question = (question or "").strip()
    if not question:
        raise ValueError("물음이 비었습니다")
    if len(question) > MAX_QUESTION:
        raise ValueError("물음은 %d 자까지입니다" % MAX_QUESTION)
    if not _lock.acquire(blocking=False):
        raise Busy("앞 물음에 답하는 중입니다 — 끝나면 다시 보내 주십시오")
    t0 = time.time()
    try:
        _stat["calls"] += 1
        try:
            text, cost = _run(_prompt(question, ctx, history, quote, indices))
        except Exception as e:
            _stat["fails"] += 1
            _stat["lastError"] = ("%d 초 안에 답이 안 왔습니다" % TIMEOUT
                                  if isinstance(e, subprocess.TimeoutExpired) else safe_message(e, 160))
            raise RuntimeError(_stat["lastError"])
        secs = round(time.time() - t0, 1)
        _stat["lastSecs"] = secs
        return {"text": text, "secs": secs, "costUsd": cost}
    finally:
        _stat["lastAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _lock.release()


def status():
    return dict(_stat, busy=_lock.locked(), budgetUsd=float(BUDGET_USD), timeout=TIMEOUT)
