# -*- coding: utf-8 -*-
"""세션 현황판 — 터미널 칸 하나에 그린다 (2026-10-01 지시 · B 안).

재권님 —
    「각 세션별로 하는 업무 실시간으로 볼 수 있는 거 없을까」
    「세션 하나 열어서 그것만 실시간으로 갱신되는 걸 말한 거야」
    「가로를 좁게 … 마지막 커밋은 그번호를 볼필요는 없을거같고 세로로길게」
    → A·B·C 중 **「b 로하면 될거같아」**

    python3 tools/현황판.py              한 번 그린다
    python3 tools/현황판.py --watch      3초마다 다시 그린다

**읽는 곳 셋** — 모두 남이 적은 것이고 이 판은 읽기만 한다.

    상태        `herdr agent list` 의 `agent_status`
    하는 일      **8765 보드**의 그 담당 `doing` 카드 (가장 최근 것 + 외 N개)
    확인대기     그 카드 메모의 **`묻는 중:`** 줄 — 「일은 보드에서 시작한다」 가 정한 표기
                 뒤에 **`답:`** 이 오면 닫힌 것으로 본다

**커밋은 안 적는다** — 재권님 「그번호를 볼필요는 없을거같고」.
"""
import json, os, re, subprocess, sys, time, unicodedata

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DIM, OFF, BOLD = "\033[2m", "\033[0m", "\033[1m"
BLUE, YEL, GRAY, GREEN = "\033[94m", "\033[33m", "\033[90m", "\033[92m"
BOARD = (os.environ.get("KJC_BOARD_URL") or "http://127.0.0.1:8765").rstrip("/")

def w(s):
    """보이는 폭. **모호한 폭 글자(「—」 · 「·」 · 「…」 · 「▶」 등 A)도 두 칸으로 센다** (2026-10-02).
    한글 터미널은 그것을 두 칸으로 그리는 일이 많아, 한 칸으로 세면 줄이 폭을 넘어 접혔다
    (작업우선순위 12:3x 실측). 좁게 그리는 터미널이면 자리가 조금 남을 뿐 넘치지 않는다."""
    return sum(2 if unicodedata.east_asian_width(c) in "WFA" else 1 for c in s)

def pad(s, n):
    s = str(s)
    while w(s) > n:
        s = s[:-1]
    return s + " " * max(0, n - w(s))

def 접기(s, n, 최대=2):
    """n 칸에서 끊어 나눈다. **자르지 않는다** — 재권님이 하실 일이 적힌 자리다.
       2026-10-01 실측 — 보드 21장을 38칸에 넣으면 두 줄이 16장, 세 줄은 0장이다."""
    줄, 지금 = [], ""
    for c in s:
        if w(지금) + w(c) > n:
            줄.append(지금); 지금 = ""
            if len(줄) >= 최대:
                return 줄
        지금 += c
    if 지금:
        줄.append(지금)
    return 줄 or [""]

def 접기_꼬리(본문, 꼬리, n, 최대=2):
    """`(외 N개)` 같은 꼬리는 **늘 보이게** 한다 — 잘리면 「(외 1」 이 되어 뜻이 없다.
       자리가 모자라면 **본문을 줄여서** 꼬리 자리를 만든다."""
    조각 = 접기(본문, n, 최대)
    if not 꼬리:
        return 조각
    마지막 = 조각[-1]
    while 마지막 and w(마지막) + w(꼬리) > n:
        마지막 = 마지막[:-1]
    조각[-1] = 마지막 + 꼬리
    return 조각

def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=5)
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""
    except Exception:
        return ""

def 칸폭(기본=40):
    """이 판이 도는 터미널의 폭.

    **먼저 터미널에 직접 묻는다** (2026-10-02). 전에는 `herdr pane current` 로 물었는데, 그것은
    **지금 앞에 있는 칸**을 답해서 75열 창에 139자 가름줄이 나와 접히고 겹쳤다(작업우선순위 실측).
    터미널이 아닐 때(파이프 등)만 herdr 에 묻는다.
    """
    try:
        if sys.stdout.isatty():
            return max(32, os.get_terminal_size(sys.stdout.fileno()).columns - 1)
    except OSError:
        pass
    try:
        나 = json.loads(run(["herdr", "pane", "current"]))["result"]["pane"]["pane_id"]
        d = json.loads(run(["herdr", "pane", "layout"]))
        for p in d["result"]["layout"]["panes"]:
            if p["pane_id"] == 나:
                return max(32, p["rect"]["width"] - 2)
    except Exception:
        pass
    return 기본

# 세션 블록 순서 — **재권님이 정하신 순서다** (2026-10-02 12:4x · 「순서만 조절하자」).
# ⚠️ **복제다.** 세션 이름 목록이 `CLAUDE.md` 「세션 역할 분담」 표에도 있다 — 순서는 그 표와
# **다르다**(그 표는 홈페이지_정리 · 주식 넷 · 개념정의 · 엔진_개발 · 작업우선순위 · 시황분석 · qa).
# 세션이 늘거나 이름이 바뀌면 두 곳을 봐야 한다. 여기 없는 이름은 맨 아래로 간다 — 사라지지 않는다.
세션순서 = ["작업우선순위", "개념정의", "qa", "홈페이지_정리", "주식페이지_개발",
            "주식페이지_개발1", "주식페이지_개발2", "주식페이지_개발3", "시황분석"]

def _창이름들():
    """{세션 기록 id: Herdr 창 이름} — `tools/session-addr.py` 의 `labels()` 를 그대로 쓴다.

    **터미널 제목으로 이름을 읽지 않는다** (2026-10-02). 재시작하면 제목이 「Claude Code」 로
    지워져 아홉 블록이 전부 그 이름 · 「보드에 카드 없음」 이 됐다(작업우선순위 12:18 실측).
    Herdr 창 이름(재권님이 붙이신 이름)은 재시작에도 남는다. **같은 셈을 두 곳에 두지 않으려고**
    그 도구를 불러 쓴다 — 못 부르면 `None`(아래가 옛 방식으로 떨어진다).
    """
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "..", "tools", "session-addr.py"),
                 os.path.join(here, "session-addr.py")):
        try:
            spec = importlib.util.spec_from_file_location("session_addr", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            got = mod.labels()
            if got is not None:
                return {sid: v[0] for sid, v in got.items()}
        except Exception:
            continue
    return None

def 세션들():
    try:
        d = json.loads(run(["herdr", "agent", "list"]))
    except Exception:
        return []
    창 = _창이름들() or {}
    def 이름(a):
        sid = (a.get("agent_session") or {}).get("value")
        n = 창.get(sid) if sid else None
        if n and n != "?":
            return n
        # 창 이름을 못 얻은 때만 — 이 이름은 재시작하면 「Claude Code」 로 낡는다
        return (a.get("terminal_title_stripped") or a.get("name") or "").strip()
    # **순서를 고정한다** — herdr 순서는 바뀐다. 훑어보는 판이라 같은 세션이 늘 같은 줄에 있어야 한다.
    # 표에 없는 이름은 맨 아래, 그 안에서는 이름순.
    자리 = {n: i for i, n in enumerate(세션순서)}
    return sorted(({"이름": 이름(a), "상태": a.get("agent_status")} for a in d["result"]["agents"]),
                  key=lambda x: (자리.get(x["이름"], len(세션순서)), x["이름"]))

# 세션 이름 색 — **묶음 넷** (2026-10-02 12:5x 재권님 · 작업우선순위 경유).
# 같은 묶음은 같은 색, 묶음끼리는 다른 색. **색은 박지 않고 `theme.css` 의 있는 변수에서 읽는다.**
# ⚠️ **보드 담당 동그라미 색(이름 해시 · projects/index.html 의 whoColor)과 갈린다** — 재권님이 현황판만
# 두고 정하신 것이라 보드는 그대로다. 묶음에 없는 이름은 회색(멈춤 색)이다.
색묶음 = [
    (("작업우선순위", "개념정의", "qa"), "--kh-accent"),          # 파랑 #3182f6
    (("홈페이지_정리",), "--kh-cat-violet"),                    # 보라 #8b5cf6
    (("주식페이지_개발", "주식페이지_개발1", "주식페이지_개발2", "주식페이지_개발3"), "--kh-cat-teal"),  # 청록 #0ca678
    (("시황분석",), "--kh-cat-amber"),                          # 호박 #c77700
]
# **이름 색에는 빨강 · 초록 · 노랑을 안 쓴다** (12:5x) — 아래 상태 색과 헷갈리지 않게.
# ⚠️ theme.css 에 그 셋을 피한 색이 넉넉지 않아 청록(③)은 초록과, 호박(④)은 노랑과 가깝다 — 재권님이 보고 정하신다.

# 상태 줄 색 (2026-10-02 12:5x 재권님) — 멈춤 빨강 · 진행 중 초록 · 확인 필요(질문 걸림 · 확인대기) 노랑.
상태색변수 = {"멈춤": "--kh-danger", "진행": "--pj-done", "확인": "--kh-fav"}

def _변수색(이름):
    """theme.css 에서 그 변수의 #색을 읽어 터미널 색 글자로. 못 읽으면 빈 글자."""
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        theme = open(os.path.join(here, "..", "assets", "css", "theme.css"), encoding="utf-8").read()
        v = re.search(r"^\s*" + re.escape(이름) + r"\s*:\s*#([0-9a-fA-F]{6})", theme, re.M)
        if v:
            h = v.group(1)
            return "\033[38;2;%d;%d;%dm" % (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except Exception:
        pass
    return ""

_묶음색 = {n: _변수색(var) for names, var in 색묶음 for n in names}
대기색 = _변수색("--kh-accent") or BLUE      # 파랑 #3182f6 (13:4x 재권님)

def 대기깜빡():
    """「답 기다림」 은 **늘** 깜빡인다 — 두 겹으로 건다.
    ① 터미널 깜빡임 `\033[5m` — 재권님 터미널(cmux · ghostty)에서 듣는지는 이쪽에서 못 잰다
    ② 듣지 않아도 보이게 갱신(3초)마다 반전 ↔ 보통을 번갈아 그린다"""
    return "\033[5m" + (REV if int(time.time() // 3) % 2 == 0 else "")

멈춤색 = _변수색(상태색변수["멈춤"]) or GRAY
진행색 = _변수색(상태색변수["진행"]) or GREEN
확인색 = _변수색(상태색변수["확인"]) or YEL

def 이름색(세션이름):
    """묶음 색. 묶음에 없거나 색을 못 읽으면 회색."""
    return _묶음색.get(세션이름) or GRAY

def 라벨(이름):
    """`tools/board-card.py` 와 **같은 규칙**이라야 카드를 찾는다."""
    return 이름.replace("주식페이지_", "")

def 보드():
    """{담당: [카드…]} — 못 읽으면 None(「없다」 와 다르다)."""
    try:
        import urllib.request
        with urllib.request.urlopen(BOARD + "/api/board/doc/projects", timeout=5) as r:
            d = json.load(r)
    except Exception:
        return None
    표 = {}
    for p in (d.get("data") or {}).get("projects") or []:
        for t in p.get("tasks") or []:
            s = t.get("text") or ""
            태그 = re.findall(r"\[([^\]]*)\]", s[:40])
            담당 = 태그[1].strip() if len(태그) > 1 else ""
            표.setdefault(담당, []).append({
                "제목": re.sub(r"^\s*(\[[^\]]*\]\s*){1,2}", "", s).strip(),
                "열": t.get("column") or "todo",
                "때": t.get("updatedAt") or t.get("createdAt") or 0,
                "메모": t.get("memo") or "",
            })
    return 표

# **`doing` 만 보면 안 된다** — 「열은 검수 흐름을 따른다」(2026-10-01) 뒤로
# 커밋한 카드는 훅이 **`review`** 로 옮긴다. 빼면 **커밋하자마자 「카드 없음」** 이 된다.
# `doing` 을 먼저 보여 주고 `review` 는 「검수 대기」 로 붙인다.
도는열 = ("doing", "review")

def 묻는중(메모):
    """`묻는 중:` 줄 중 마지막. 그 뒤에 `답:` 이 오면 닫힌 것으로 본다."""
    # **줄 앞에 있을 때만 센다** (시각 「HH:MM」 은 건너뛴다) — 「일은 보드에서 시작한다」 가
    # 「메모 줄 **앞에** `묻는 중:`」 이라 정했다. 줄 가운데 낱말로 세면 그 표기를 **설명한 줄**까지
    # 물음으로 잡힌다(2026-10-02 실측 — 「기준은 묻는 중:/답: 과 …」 가 물음이 됐다).
    머리 = re.compile(r"^\s*(?:\d{1,2}:\d{2}\s+)?(묻는 중|답):\s*(.*)$")
    남은 = None
    for 줄 in 메모.split("\n"):
        m = 머리.match(줄)
        if not m:
            continue
        if m.group(1) == "묻는 중":
            남은 = m.group(2).strip()
        elif 남은:
            남은 = None
    return 남은

_커밋대기글 = re.compile(r"커밋\s*(지시)?\s*대기|커밋대기중|커밋할까요")

def _커밋대기(메모):
    """메모 **마지막 줄**이 커밋 지시를 기다린다고 적었나. 앞 줄에 있던 것은 지난 일이다."""
    줄들 = [x for x in (메모 or "").split("\n") if x.strip()]
    return bool(줄들) and bool(_커밋대기글.search(줄들[-1]))

def _대기사정(돌고):
    """doing 카드 중 메모 **마지막 줄**에 「대기」 가 있는 것의 그 줄(시각은 뗀다). 없으면 빈 글자.
    최신 카드부터 본다 — `돌고` 는 최신 먼저로 정렬돼 온다."""
    for c in 돌고:
        줄들 = [x for x in (c["메모"] or "").split("\n") if x.strip()]
        if 줄들 and "대기" in 줄들[-1]:
            return re.sub(r"^\s*\d{1,2}:\d[\dxX]\s+", "", 줄들[-1]).strip()   # 「13:1x」 처럼 끝이 x 인 시각도 뗀다
    return ""

def 물음들(카드):
    """그 세션이 지금 걸어 둔 물음 전부."""
    return [q for q in (묻는중(c["메모"]) for c in 카드) if q]

# ── 바뀐 세션 깜빡이기 (2026-10-02 13:0x 재권님 「중간에 진행이 바뀌면 인지되게 깜빡이게」) ──
# **전 판을 들고 있다가** 상태(멈춤 · 일하는 중 · 질문 걸림 · 검수 대기)나 하는 일 줄이 바뀐 세션의
# 이름 줄을 `깜빡임초` 동안 **갱신마다 반전 ↔ 보통으로 번갈아** 그린다.
# ANSI 5(blink)는 쓰지 않는다 — 재권님 터미널에서 실제로 깜빡이는지 이쪽에서 잴 방법이 없다.
# 반전(7)은 어느 터미널이나 보인다. 처음 그린 판은 견줄 「전 판」 이 없어 안 깜빡인다.
깜빡임초 = 30
REV = "\033[7m"
_전판 = {}       # 세션 이름 → (상태 글, 하는 일 첫 줄, 물음)
_바뀐때 = {}     # 세션 이름 → 바뀐 시각

def _깜빡일까(이름, 표시):
    지금 = time.time()
    if 이름 in _전판 and _전판[이름] != 표시:
        _바뀐때[이름] = 지금
    _전판[이름] = 표시
    t = _바뀐때.get(이름)
    if t is None or 지금 - t >= 깜빡임초:
        return False
    # 갱신(3초)마다 번갈아 — 바뀐 순간부터 센다
    return int((지금 - t) // 3) % 2 == 0

def 그리기():
    W = 칸폭()
    표 = 보드()
    세션 = 세션들()
    줄 = "─" * W
    쓸 = []

    def 적기(s=""):
        쓸.append(s)

    적기(BOLD + pad(" 세션 현황판", W - 9) + OFF + DIM + time.strftime("%H:%M:%S") + OFF)
    적기(DIM + 줄 + OFF)

    # ── 맨 위 「재권님이 하실 것」 — 몇 개 걸려 있는지 한눈에 보이는 자리 ──
    물음 = []
    if 표 is not None:
        for s in 세션:
            카드 = [c for c in 표.get(라벨(s["이름"]), []) if c["열"] in 도는열]
            qs = 물음들(카드)
            if qs:
                물음.append((s["이름"], qs))
    if 표 is None:
        적기(YEL + " ▶ 보드를 못 읽었습니다 — " + BOARD + OFF)
        적기(DIM + "   「없다」 가 아니라 「못 봤다」 입니다" + OFF)
    elif 물음:
        적기(확인색 + BOLD + " ▶ 재권님이 하실 것  " + str(sum(len(q) for _, q in 물음)) + OFF)
        for 누구, 무엇들 in 물음:
            적기("   " + 확인색 + 누구 + OFF)
            for 무엇 in 무엇들:
                # **여기서는 네 줄까지 둔다** — 재권님이 하실 일이 적힌 자리라
                # 뒷말이 없어지면 안 된다. 아래 세션 블록은 훑어보는 자리라 두 줄이다.
                조각 = 접기(무엇, W - 7, 최대=4)
                적기("     · " + 조각[0])
                for 더 in 조각[1:]:
                    적기("       " + 더)
    else:
        적기(DIM + " ▶ 재권님이 하실 것  없음" + OFF)
    적기(DIM + 줄 + OFF)

    # ── 세션마다 세로 블록 ──
    for s in 세션:
        # **`doing` 을 먼저, 그 안에서 최신 먼저.**
        # 파이썬 `sorted` 는 안정 정렬이라 **두 번 나눠 거는 것이 맞다** —
        # 뒤에 건 기준이 1차, 앞서 건 기준이 그 안의 2차로 남는다.
        # ⚠️ **`doing` 과 `review` 를 섞어 「외 N개」 로 묶으면 검수 대기가 묻힌다.**
        # 2026-10-01 실측 — 카드 하나를 review 로 옮겨도 **판이 한 글자도 안 바뀌었다**
        # (doing 이 둘 더 있어 맨 위가 그대로였다). **가르지 못하는 값이었다.**
        # 그래서 **따로 센다** — 하는 일은 `doing` 만, 검수 대기는 제 줄을 갖는다.
        전부 = (표 or {}).get(라벨(s["이름"]), [])
        목록 = [c for c in 전부 if c["열"] in 도는열]
        돌고 = sorted([c for c in 목록 if c["열"] == "doing"],
                      key=lambda c: str(c["때"]), reverse=True)
        검수 = [c for c in 목록 if c["열"] == "review"]
        카드 = 돌고 + 검수
        qs = 물음들(카드)
        q = qs[0] if qs else None

        # 상태 다섯 — CLAUDE.md 「현황 보고는 표로만 한다」 의 상태에 맞춘다 (2026-10-02 13:1x 재권님
        # 「멈춤과 응답대기는 달라야 할 것 같다」). Herdr 상태 + 보드 카드 메모로 센다.
        #     일하는 중   Herdr working                                   초록
        #     답 기다림    idle · 카드에 답 없는 「묻는 중:」 줄            파랑 · 늘 깜빡임 (확인대기중)
        #     커밋대기     idle · doing 카드 메모 마지막 줄이 커밋 지시 대기  노랑
        #     세션 기다림  idle · doing 카드 메모 마지막 줄에 「대기」 — 사정을 붙인다  흐린 회색
        #     일 없음      idle · 담당 doing 카드가 없다                    회색   (지시대기중)
        # 이름에 「대기」 를 겹쳐 쓰지 않는다 (2026-10-02 13:5x 재권님 「색이 달르고 이름도 다르게」)
        #     멈춤         idle · doing 은 있는데 묻는 것도 커밋대기도 없다  빨강   ← 왜 서 있는지 모르는 자리
        # 표기는 「일은 보드에서 시작한다」 의 `묻는 중:` · `답:` 이다. 낱말이 다르면 못 가르고 「멈춤」 이 된다.
        if s["상태"] == "working":
            글, 색 = "일하는 중", 진행색
        elif q:
            글, 색 = "답 기다림", 대기색 + 대기깜빡()   # 13:5x 재권님 「가」 — 파랑 깜빡임은 이쪽
        elif any(_커밋대기(c["메모"]) for c in 돌고):
            글, 색 = "커밋대기", 확인색
        elif _대기사정(돌고):
            # 여섯째 갈래 「대기」 (2026-10-02 13:3x 재권님 「응 넣어줘」) — 사정이 적힌 기다림. 회색.
            # 낱말 위치는 세션마다 갈려 있어(「대기:」 로 시작 · 「… 재검 대기」 로 끝) 어디 있든 잡는다.
            # 13:4x 재권님 「대기는 파란색으로 해주고 깜빡이고 있게」 — 파랑 · 계속 깜빡임(아래 대기깜빡)
            # 13:5x 재권님 — 이름 「세션 기다림」 · 흐린 회색 · 안 깜빡임
            글, 색 = "세션 기다림 · " + _대기사정(돌고), DIM + GRAY
        elif not 돌고:
            글, 색 = "일 없음", GRAY            # 멈춤 빨강과 가른다 (13:5x)
        else:
            글, 색 = "멈춤", 멈춤색

        앞 = 돌고 or 검수
        표시 = (글, 앞[0]["제목"] if (돌고 or 검수) else "", q or "")
        반전 = REV if _깜빡일까(s["이름"], 표시) else ""
        # ① 상태는 이름 옆에 (2026-10-02 13:1x 재권님) — 상태 줄은 따로 안 둔다
        # 깜빡일 때는 이름과 상태 글 둘 다 반전 — 사이에서 색을 끊으므로 반전을 다시 건다
        적기(BOLD + 반전 + 이름색(s["이름"]) + s["이름"] + OFF + 반전 + "  " + 색 + 글 + OFF)
        if 앞:
            더 = (" (외 %d개)" % (len(앞) - 1)) if len(앞) > 1 else ""
            조각 = 접기_꼬리(앞[0]["제목"], 더, W - 4)
            적기("  - " + (GREEN if not 돌고 else "") + 조각[0] + (OFF if not 돌고 else ""))
            for 더줄 in 조각[1:]:
                적기("    " + 더줄)
        elif 표 is not None:
            # ⚠️ **두 가지 「없다」 를 가른다.** 섞으면 신호가 죽는다 —
            # 「일은 보드에서 시작한다」 가 잡으려는 것은 **앞엣것**이다.
            #     카드가 아예 없다      → 아직 안 만들었다. **신호다**
            #     있는데 다 끝났다      → 정상이다
            적기("  - " + DIM + ("보드에 카드 없음" if not 전부
                                 else "들고 있는 것 없음") + OFF)
        # **검수 대기는 제 줄을 갖는다** — 「외 N개」 에 묻히면 안 보인다
        if 검수 and 돌고:
            적기("  - " + GREEN + "검수 대기 %d건" % len(검수) + OFF)
        if q:
            더q = (" (외 %d개)" % (len(qs) - 1)) if len(qs) > 1 else ""
            조각 = 접기_꼬리("확인대기 · " + q, 더q, W - 4)
            적기("  - " + 확인색 + BOLD + 조각[0] + OFF)
            for 더줄 in 조각[1:]:
                적기("    " + 확인색 + 더줄 + OFF)
        # ② 그다음 업무 — 그 담당의 todo 카드를 **보드 순서 그대로** (2026-10-02 13:1x 재권님).
        # 하는 일(doing)과 갈리게 「다음 ·」 머리말. 두 줄까지, 넘으면 「외 N개」.
        다음들 = [c for c in 전부 if c["열"] == "todo"]
        for i, c in enumerate(다음들[:2]):
            꼬리 = (" (외 %d개)" % (len(다음들) - 2)) if (i == 1 and len(다음들) > 2) else ""
            머리 = "다음 · " if i == 0 else "       "
            조각 = 접기_꼬리(c["제목"], 꼬리, W - 4 - w(머리), 최대=1)
            적기("  " + DIM + 머리 + OFF + 조각[0])
        # 세션 사이 가름줄 (2026-10-02 · 재권님 「세션별로 줄도 그어서 인지가 잘 되게」)
        적기(DIM + 줄 + OFF)

    for 조각 in 접기("상태 herdr · 하는 일과 확인대기 8765 보드 카드", W - 2, 최대=3):
        적기(DIM + " " + 조각 + OFF)
    return "\n".join(자르기(x, W) for x in 쓸)

_ANSI = re.compile(r"\033\[[0-9;?]*[A-Za-z]")

def 자르기(줄, n):
    """보이는 폭이 n 을 넘으면 「…」 로 끊는다. 색 글자(ANSI)는 폭으로 안 센다.
    **접혀 다음 줄로 넘어가면 갱신 때 그 자리가 안 지워져 글이 겹친다** — 그래서 넘기지 않는다."""
    if w(_ANSI.sub("", 줄)) <= n:
        return 줄
    out, 폭, i = "", 0, 0
    while i < len(줄):
        m = _ANSI.match(줄, i)
        if m:
            out += m.group(0); i = m.end(); continue
        c = 줄[i]
        if 폭 + w(c) > n - w("…"):     # 「…」 자리를 그 폭만큼 남긴다
            break
        out += c; 폭 += w(c); i += 1
    return out + "…" + OFF

def main():
    보기 = "--watch" in sys.argv
    if not 보기:
        print(그리기()); return
    try:
        sys.stdout.write("\033[?25l")                 # 커서 감추기
        나 = os.path.abspath(__file__)
        처음 = os.path.getmtime(나)
        while True:
            # **지우고 그리지 않는다** — 깜빡인다. 홈으로 보내고 덮어쓴 뒤 아래를 지운다.
            # 줄 끝마다 `\033[K` — 앞 갱신이 더 길었으면 그 꼬리가 남아 겹쳐 보인다
            판 = 그리기().replace("\n", "\033[K\n")
            sys.stdout.write("\033[H" + 판 + "\033[K\033[J")
            sys.stdout.flush()
            time.sleep(3)
            # **이 파일이 바뀌면 스스로 다시 뜬다** (2026-10-02) — 고칠 때마다 창을 다시 띄우지 않게
            try:
                if os.path.getmtime(나) != 처음:
                    sys.stdout.write("\033[?25h")
                    sys.stdout.flush()
                    os.execv(sys.executable, [sys.executable] + sys.argv)
            except OSError:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h\n")               # 커서 되돌리기

main()
