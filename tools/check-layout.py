# -*- coding: utf-8 -*-
"""화면의 칸 치수를 재서 기준과 대조한다.

    python tools/check-layout.py --save     지금 화면을 기준으로 삼는다
    python tools/check-layout.py            기준과 대조한다 (어긋나면 1)

**높이만 본다.** 폭은 글자 수를 타서 흔들린다 (아래 `watch_w` 주석).

**왜 있나** — 「보는 것을 바꿔도 자리는 그대로다」 가 룰인데 검사가 없어서
세 번 재발했다(차트 · 투자자 정보 · 첫 화면). 룰은 기억해야 지켜지고,
기억해야 지켜지는 룰은 지켜지지 않는다.

**대상 값을 박지 않는다.** 잴 선택자를 여기 적지 않고 화면에서 뽑는다.
칸이 늘면 기준에 저절로 들어오고, 그때 `--save` 로 다시 잡는다.

크롬을 헤드리스로 띄워 CDP 로 붙는다. 이 PC 에 websocket 라이브러리가
없어서 표준 라이브러리만으로 프로토콜을 직접 쓴다.
"""
import sys, os, json, base64, struct, socket, subprocess, tempfile, time, urllib.request, argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "tools", "layout-baseline.json")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9334

# 재는 창 크기. 화면이 반응형이라 폭이 바뀌면 높이도 바뀐다 — 기준과 같은
# 폭에서 재야 뜻이 있다. 이 값을 바꾸면 기준을 다시 잡아야 한다.
VIEW_W, VIEW_H = 1600, 1000

# 어디를 재나. 경로만 적고 **무엇을 잴지는 안 적는다**
PAGES = ["index.html", "stock.html", "daily.html", "news.html"]
# 어느 서버를 재나. `--port` 로 바꾼다 — 세션마다 자기 포트가 있어서,
# 8765 로 박아 두면 **세션 폴더 화면을 못 잰다** (2026-09-21 · 주식페이지_개발1).
PORT_DEFAULT = 8765
BASE_FMT = "http://localhost:%d/holdings/"
BASE = BASE_FMT % PORT_DEFAULT

# 칸이 몇 px 까지 달라져도 넘어가나. 0 이면 한 픽셀도 못 바뀐다.
TOL = 1

# 다 그려졌다고 보는 조건 — **높이가 연달아 같게 나오면** 그만 기다린다.
SETTLE_STEP  = 0.5    # 재는 간격(초)
SETTLE_SAME  = 3      # 연달아 같아야 하는 횟수
SETTLE_TRIES = 60     # 최대 이만큼 재고 포기한다 (0.5 x 60 = 30초)
SETTLE_MIN   = 6      # **이만큼은 무조건 기다린다** (0.5 x 6 = 3초)
SAVE_MIN     = 30     # 기준을 잡을 때는 이만큼 (0.5 x 30 = 15초)

# SETTLE_MIN 이 왜 필요한가 — 페이지가 열리자마자는 칸이 거의 없는데,
# **그 빈 상태도 연달아 같게 나온다.** 안정 판정만으로는 빈 화면을
# 「다 그려졌다」 로 읽는다.
#
# **기준을 잡을 때가 가장 위험하다.** 대조할 때는 「기준에 있는 칸이 다
# 나왔나」 라는 목표가 있는데, 기준을 잡을 때는 그것이 없다. 덜 그려진 채로
# 박히면 **그 뒤로 늘 그 상태에 맞춰진다** — 덜 그려진 화면이 「정상」 이 되고,
# 제대로 그려진 날이 「칸이 새로 생겼다」 로 나온다. 2026-09-21 에 실제로 났다.
# 그래서 `--save` 는 느려도 길게 기다린다. 기준은 가끔만 잡는다.

MEASURE = r"""
(() => {
  const root = document.querySelector('.kh-app') || document.body;
  const out = {};
  const seen = {};
  const walk = (el, depth) => {
    // 깊이 3까지만 본다. 2026-09-21 에 6 으로 늘려 보았더니 **작은 글자 칸이
    // 흔들렸다** — `kh-mut` 하나가 두 번 재는 사이 20px 에서 17px 이 됐다.
    // 글자 수를 타는 자리라 검사가 못 된다. 칸은 746개에서 다시 줄었다.
    if (depth > 3) return;
    for (const c of el.children) {
      // **id 가 있으면 id 를 쓴다.** 세션끼리 그 이름으로 부르기 때문이다 —
      // 2026-09-21 에 class 만 보다가, 다른 세션이 `#kh-iv-box` 라고 넘겨준 칸을
      // 이 도구는 `kh-idxp-b` 로 부르고 있었다. **같은 칸을 서로 다른 이름으로
      // 불러서, 재고 있는데도 「기준에 없다」 로 읽혔다.**
      const cn = (typeof c.className === 'string') ? c.className.trim() : '';
      const cls = (c.id && /^(kh|h)-/.test(c.id)) ? c.id
                : (cn ? cn.split(/\s+/)[0] : '');
      const named = cls.startsWith('kh-') || cls.startsWith('h-');
      if (named) {
        seen[cls] = (seen[cls] || 0) + 1;
        const key = seen[cls] > 1 ? cls + '#' + seen[cls] : cls;
        const r = c.getBoundingClientRect();
        out[key] = [Math.round(r.width), Math.round(r.height)];
      }
      // 내부 스크롤 칸의 **안**은 재지 않는다. 줄이 늘어도 화면이 안 움직이므로
      // 그 안을 기준으로 박으면 데이터가 바뀔 때마다 헛경보가 난다 —
      // 2026-09-21 실측: 순위표 #kh-rows 가 10597px 인데 문서 전체는 1237px.
      const ov = getComputedStyle(c).overflowY;
      if (ov === 'auto' || ov === 'scroll') continue;
      walk(c, named ? depth + 1 : depth);
    }
  };
  walk(root, 0);
  out['(문서 전체)'] = [document.documentElement.scrollWidth,
                        document.documentElement.scrollHeight];
  // **지금 보고 있는 화면이 어디인가.** 이것을 안 보면 앞 화면을 재고도
  // 모른다 — 2026-09-21 에 두 세션이 각각 그 꼴을 봤다.
  out['(주소)'] = location.pathname;
  out['(스크롤바 폭)'] = [innerWidth - document.documentElement.clientWidth, 0];
  return JSON.stringify(out);
})()"""


def ws_connect(ws_url):
    _, rest = ws_url.split("://", 1)
    hostport, path = rest.split("/", 1)
    host, port = hostport.split(":")
    s = socket.create_connection((host, int(port)), timeout=30)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall(("GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\n"
               "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
               "Sec-WebSocket-Version: 13\r\n\r\n" % (path, hostport, key)).encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += s.recv(4096)
    if b"101" not in buf.split(b"\r\n")[0]:
        raise IOError("CDP 핸드셰이크 실패")
    return s


def _send(s, msg):
    data = json.dumps(msg).encode()
    n = len(data)
    head = b"\x81"
    if n < 126:      head += struct.pack("!B", n | 0x80)
    elif n < 65536:  head += struct.pack("!BH", 126 | 0x80, n)
    else:            head += struct.pack("!BQ", 127 | 0x80, n)
    mask = os.urandom(4)
    s.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))


def _recv(s):
    def rd(n):
        b = b""
        while len(b) < n:
            c = s.recv(n - len(b))
            if not c:
                raise IOError("CDP 연결이 끊겼습니다")
            b += c
        return b
    # **프레임 종류를 전부 다룬다 (2026-09-21).** 전에는 `op == 1` 만 보고
    # 나머지를 버렸는데 그래서 셋이 한꺼번에 샜다 — 두 세션이 코드를 읽고
    # 같은 자리를 짚었다.
    #
    #     FIN    큰 응답이 쪼개지면 **첫 조각만 파싱하고 return** 했다.
    #            남은 조각이 스트림에 남아 다음 `_recv` 가 그것을 헤더로 읽는다.
    #            **한 번 어긋나면 그 뒤가 전부 깨진다**
    #     op 9   ping — **pong 을 안 보내면 크롬이 끊는다**
    #     op 8   닫기 — 끊긴 것을 모르고 계속 읽었다
    #
    # **다만 이것이 원인이라고 단정하지 않는다 (2026-09-21).**
    # `주식페이지_개발1` 이 같은 조건으로 프레임 헤더를 직접 재 보니
    # **쪼개진 메시지 0 · ping 0 · 끊김 0** 이었다. 응답이 2KB 남짓이라
    # 쪼개질 크기가 아니다. **FIN 가설은 재현되지 않았다.**
    #
    # 위 처리는 **프로토콜상 맞는 구현**이라 그대로 둔다. 하지만 같은 커밋에
    # `--user-data-dir` 도 넣었고, **둘 중 어느 것이 들었는지 안 갈랐다.**
    # 고친 뒤 세 번 연속 통과했지만 그 전에도 4회 중 1회는 정상이었다 —
    # **세 번으로는 모자란다.**
    #
    # **가장 유력한 것은 프로세스 누적이었다 (2026-09-21 실측).**
    # `terminate()` 가 부모만 죽여 크롬이 **36개까지 쌓였고**, 그 상태에서는
    # 끊겼다. 헤드리스만 골라 정리하니 34 → 15 가 됐고, 그 뒤 **세 번 연속
    # 통과에 크롬도 15개로 고정**됐다. `Browser.close` 를 보내니 안 쌓인다.
    #
    # **그래도 확정은 아니다.** FIN · ping · close · 임시 프로필 · 누적
    # 다섯을 함께 고쳤고 **어느 것이 들었는지 안 갈랐다.** 다섯 다
    # 맞는 조치라 되돌리며 가르지 않았다 — 갈라야 할 이유가 생기면 그때 한다.
    buf = b""
    op0 = None
    while True:
        h = rd(2)
        fin, op, n = h[0] & 0x80, h[0] & 0x0F, h[1] & 0x7F
        if n == 126:   n = struct.unpack("!H", rd(2))[0]
        elif n == 127: n = struct.unpack("!Q", rd(8))[0]
        payload = rd(n)

        if op == 0x9:                       # ping → 같은 내용으로 pong
            _frame(s, 0xA, payload)
            continue
        if op == 0xA:                       # pong → 무시
            continue
        if op == 0x8:                       # 닫기
            raise IOError("CDP 가 연결을 닫았습니다")

        if op in (0x1, 0x2):
            buf, op0 = payload, op
        elif op == 0x0:
            buf += payload
        if fin and op0 == 0x1:
            return json.loads(buf.decode())


def _measure_once(expect=None):
    """모든 화면을 재서 {화면: {칸: [폭, 높이]}} 를 돌려준다.

    `expect` 는 기준(이미 잡아 둔 것)이다. 주면 **그 칸이 전부 나타날 때까지**
    기다린다. 목표를 알고 있으니 「덜 그려진 것」 과 「진짜 없어진 것」 이 갈린다.
    없으면(`--save`) 높이가 연달아 같아질 때까지만 기다린다.
    """
    try:
        urllib.request.urlopen(BASE, timeout=5)
    except Exception:
        print("서버가 없습니다 — holdings/preview.bat 로 8765(holdings 미리보기) 를 먼저 띄우십시오")
        sys.exit(2)

    if not os.path.exists(CHROME):
        print("크롬을 못 찾았습니다: %s" % CHROME)
        sys.exit(2)

    proc = subprocess.Popen(
        # `--hide-scrollbars` 를 주지 않는다. 숨기면 콘텐츠 폭이 실제보다
        # 넓게 재지고, 「(스크롤바 폭)」 항목이 늘 0 이 되어 뜻을 잃는다.
        # 두는 편이 재권님 화면과 조건이 가깝고, 덤으로 「스크롤바는 한 벌만
        # 쓴다」 의 6px 이 깨지는 것도 이 도구가 잡는다 (2026-09-21).
        # **임시 프로필을 준다.** 안 주면 기본 프로필을 잡으려다
        # `ConnectionResetError` 로 죽는다 — 2026-09-21 에 두 번 연속 났고,
        # 그때 창 없는 크롬이 여럿 떠 있었다. 재권님 크롬과도 섞이지 않는다.
        [CHROME, "--headless=new", "--disable-gpu",
         "--user-data-dir=" + tempfile.mkdtemp(prefix="kjc-layout-"),
         "--no-first-run", "--no-default-browser-check",
         "--remote-debugging-port=%d" % PORT,
         "--window-size=%d,%d" % (VIEW_W, VIEW_H), "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        tabs = None
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen(
                    "http://127.0.0.1:%d/json" % PORT, timeout=2))
                break
            except Exception:
                time.sleep(0.5)
        if not tabs:
            print("크롬이 디버깅 포트를 안 열었습니다")
            sys.exit(2)

        ws = ws_connect([t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"])
        counter = [0]

        def call(method, params=None):
            counter[0] += 1
            _send(ws, {"id": counter[0], "method": method, "params": params or {}})
            while True:
                m = _recv(ws)
                if m.get("id") == counter[0]:
                    return m

        call("Page.enable")

        def measure_once():
            r = call("Runtime.evaluate", {"expression": MEASURE, "returnByValue": True})
            val = r.get("result", {}).get("result", {}).get("value")
            return json.loads(val) if val else None

        def shape(cells):
            """안정 판정에 쓰는 모습 — **높이만** 본다.

            폭은 종목 이름·가격의 자릿수를 타서 계속 흔들린다. 그대로 견주면
            영영 안정되지 않는다. 검사도 높이만 보므로 기준을 맞춘다."""
            return {k: v[1] for k, v in cells.items()}

        result = {}
        for page in PAGES:
            call("Page.navigate", {"url": BASE + page})
            # **시간이 아니라 상태로 기다린다.** 초를 세어 기다리면 느린 날에
            # 덜 그려진 화면을 재고, 그 값이 기준으로 박히면 그 뒤로 늘 어긋난다.
            # 칸이 몇 개 덜 잡힌 것이 「칸이 사라졌다」 로 나온다
            # (2026-09-21 · 홈페이지_정리 지적. 같은 날 다른 세션이 AI 분석이
            #  그려지기 전에 재서 두 번 잘못 보고한 일이 있었다).
            prev, stable, cells = None, 0, None
            for tries in range(SETTLE_TRIES):
                time.sleep(SETTLE_STEP)
                cells = measure_once()
                if cells is None:
                    continue

                # **화면이 정말 바뀌었나 먼저 본다 (2026-09-21).**
                # `Page.navigate` 는 비동기라 **앞 화면이 그대로 떠 있을 수
                # 있다.** 전에는 「칸이 나왔나」 만 보고 어느 화면인지는 안 봤다.
                #
                # 그래서 `daily.html` 자리에 `index.html` 높이(1306)가,
                # `news.html` 자리에 데일리 화면(2461 · `kh-dl-*` 26개)이
                # 들어갔다. **두 세션이 각각 다른 자리에서 같은 꼴을 봤다.**
                #
                # **`0` 이 아니라 그럴듯한 숫자가 나오는 쪽**이라 더 위험하다 —
                # `+1398` 을 보고 「내가 창을 늘렸나」 로 읽게 된다.
                here = (cells.get("(주소)") or "")
                if not here.endswith("/" + page):
                    stable = 0
                    prev = None
                    continue
                cur = shape(cells)
                want = (expect or {}).get(page)
                if want is not None:
                    # 기준이 있으면 **그 칸이 다 나올 때까지** 기다린다.
                    # 덜 그려진 화면을 재서 「칸이 없어졌다」 로 내는 것을 막는다 —
                    # 2026-09-21 에 news.html 의 통계 칸 열셋이 그렇게 빠졌다.
                    # **다 나올 때까지 기다리지 않는다 (2026-09-21).**
                    # 기준이 낡아 **진짜 없어진 칸**이 있으면 영영 못 기다린다 —
                    # 30초를 쓰고 실패한다. 「덜 그려진 것」 과 「없어진 것」 을
                    # 기다림으로는 가를 수 없다.
                    #
                    # **거의 다 나왔으면 그려진 것으로 본다.** 나머지는
                    # 「이번엔 안 나왔습니다」 알림으로 나가고, 그것이 진짜
                    # 없어진 것인지는 사람이 본다.
                    got = len(set(want) & set(cells))
                    enough = got >= len(want) * 0.9
                    if enough and tries >= SETTLE_MIN:
                        stable += 1
                        if stable >= SETTLE_SAME:
                            break
                    else:
                        stable = 0
                elif cur == prev:
                    stable += 1
                    if stable >= SETTLE_SAME and tries >= SAVE_MIN:
                        break
                else:
                    stable = 0
                prev = cur
            if cells is None:
                print("  %s — 재지 못했습니다" % page)
                continue
            if stable < SETTLE_SAME:
                miss = sorted(set((expect or {}).get(page, {})) - set(cells))
                if miss:
                    print("  %s — %d초를 기다렸는데 칸 %d개가 끝내 안 나왔습니다: %s"
                          % (page, SETTLE_TRIES * SETTLE_STEP, len(miss),
                             " · ".join(miss[:4]) + (" …" if len(miss) > 4 else "")))
                else:
                    print("  %s — 아직 그려지는 중입니다 (%d초를 기다렸습니다). "
                          "이 값은 기준으로 삼지 마십시오"
                          % (page, SETTLE_TRIES * SETTLE_STEP))
                result[page] = None
                continue
            # **기다리다 실패했으면 그 화면을 안 넣는다 (2026-09-21).**
            # 전에는 「안 나왔습니다」 라고 말하고서 **그 시점 화면을 그대로
            # 넣었다.** 앞 화면이 아직 떠 있으면 그것이 이 화면 값으로 들어가,
            # `news.html` 자리에 데일리 화면이 재진 일이 있었다 —
            # 문서 높이가 **+1398** 로 나와 「내가 창을 늘렸나」 로 읽힌다.
            #
            # **`0` 이 아니라 그럴듯한 숫자가 나오는 쪽**이라 더 위험하다.
            # 주식페이지_개발2 가 재서 찾았다.
            result[page] = cells
        return result
    finally:
        # **CDP 로 닫는다.** `terminate()` 는 부모만 죽이고 크롬은 렌더러 ·
        # GPU 등 여러 프로세스를 띄운다. 2026-09-21 에 **36개가 쌓여 있었다** —
        # 도구를 돌릴 때마다 남은 것이다. 주식 레인이 넷이라 더 빨리 쌓인다.
        # 쌓인 프로세스가 불안정의 원인일 수 있다 (아직 확정은 못 했다).
        try:
            _send(ws, {"id": 99999, "method": "Browser.close"})
            time.sleep(0.5)
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass


def measure_all(expect=None):
    """끊기면 다시 붙어 잰다. 그래도 안 되면 **못 쟀다고 낸다.**

    **원인을 못 찾아도 고칠 수 있다 (2026-09-21 · 주식페이지_개발1 제안).**
    그 세션이 네 가설을 재서 전부 걸러냈다 — 응답 쪼개짐 · 왕복 수 ·
    서버 오감 · 프로필 공유. 남은 것은 **여럿이 동시에 헤드리스를 띄우는
    것**인데 다른 세션을 멈출 수가 없어 확정 못 했다.

    **원인이 무엇이든 증상은 「가끔 끊긴다」 다.**

    **「못 쟀다」 를 「달라졌다」 로 내지 않는 것이 더 중요하다.** 전에는
    끊기거나 덜 잰 것이 **「칸 101개가 끝내 안 나왔습니다」** 로 나와
    화면이 깨진 것처럼 읽혔다. 실제로 그 값이 헛경보였고, 그것을 보고
    남의 작업을 되돌려 보낼 뻔했다.
    """
    last = None
    for attempt in range(3):
        try:
            got = _measure_once(expect)
            # **한 화면이라도 못 쟀으면 실패로 본다.** 예외가 안 나도
            # 그 화면이 `None` 이면 값이 비어 있는 것이다 — 전에는 그것이
            # 그대로 대조에 들어가 「화면을 못 열었습니다」 로만 나왔다.
            if got and all(v for v in got.values()) and len(got) == len(PAGES):
                if attempt:
                    print("  (%d번째 시도에서 쟀습니다)" % (attempt + 1))
                return got
        except Exception as e:
            last = e
            print("  연결이 끊겼습니다 — 다시 붙습니다 (%d/3)" % (attempt + 1))
            time.sleep(2)
    print()
    print("세 번 다 못 쟀습니다. **화면이 바뀐 것이 아닙니다.**")
    if last:
        print("  마지막 오류: %s" % last)
    print("  헤드리스 크롬이 쌓여 있으면 정리하고 다시 해 보십시오.")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true", help="지금 화면을 기준으로 삼는다")
    ap.add_argument("--port", type=int, default=PORT_DEFAULT,
                    help="어느 서버를 잴지 (기본 %d)" % PORT_DEFAULT)
    ap.add_argument("--against", type=int, metavar="PORT",
                    help="기준 파일 대신 **다른 서버와 견준다** "
                         "(세션 폴더는 이쪽이 맞는 물음이다)")
    args = ap.parse_args()

    # **기준은 포트마다 따로 둔다.** 세션 폴더 화면과 메인 화면은 다른 것이라
    # 한 파일에 섞으면 서로를 어긋남으로 읽는다.
    global BASE, BASELINE
    BASE = BASE_FMT % args.port
    if args.port != PORT_DEFAULT:
        BASELINE = BASELINE.replace(".json", "-%d.json" % args.port)


    # **세션 폴더는 「메인과 다른가」 가 맞는 물음이다 (2026-09-21 · 주식페이지_개발1).**
    # 기준 파일은 포트마다 따로 잡아야 하는데, 세션이 넷이라 넷을 잡고
    # 넷을 갱신해야 한다. **두 서버를 각각 재서 대면 기준이 필요 없다.**
    if args.against:
        BASE = BASE_FMT % args.against
        old = measure_all()
        BASE = BASE_FMT % args.port
        new = measure_all(old)
        if old is None or new is None:
            return 2
        moved = []
        for page, cells in (old or {}).items():
            cur = (new or {}).get(page)
            if not cells or not cur:
                print("  %s — 한쪽을 못 쟀습니다" % page)
                return 2
            for key, v in cells.items():
                if key == "(주소)" or key not in cur:
                    continue
                if abs(v[1] - cur[key][1]) > TOL:
                    moved.append((page, key, v[1], cur[key][1]))
        if not moved:
            print("%d 과 %d 이 같습니다 — 화면 %d장"
                  % (args.against, args.port, len(old)))
            return 0
        for page, key, a, b in moved:
            print("%s  %s   %d  →  %d   (%+d)" % (page, key, a, b, b - a))
        return 1

    base = None
    if not args.save and os.path.exists(BASELINE):
        with open(BASELINE, encoding="utf-8") as f:
            base = json.load(f)

    now = measure_all(base["pages"] if base else None)
    if now is None:
        return 2                       # **2 = 못 쟀다.** 1(달라졌다)과 가른다

    if args.save:
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"view": [VIEW_W, VIEW_H], "headless": True,
                       "잰날": time.strftime("%Y-%m-%d"), "pages": now}, f,
                      ensure_ascii=False, indent=1, sort_keys=True)
        cnt = sum(len(v) for v in now.values())
        print("기준을 잡았습니다 — 화면 %d장 · 칸 %d개" % (len(now), cnt))
        print("  %s" % BASELINE)
        return 0

    if base is None:
        print("기준이 없습니다. 먼저 --save 로 잡으십시오")
        return 2

    if base.get("view") != [VIEW_W, VIEW_H]:
        print("기준을 잰 창 크기가 다릅니다 (기준 %s · 지금 %s) — 다시 잡으십시오"
              % (base.get("view"), [VIEW_W, VIEW_H]))
        return 2

    moved, added, gone = [], [], []
    for page, cells in base["pages"].items():
        cur = now.get(page)
        if cur is None:
            print("%s — 화면을 못 열었습니다" % page)
            return 2
        for key, v in cells.items():
            if key == "(주소)":            # 문자열이라 크기 비교가 아니다
                continue
            w, h = v
            if key not in cur:
                gone.append((page, key))
                continue
            w2, h2 = cur[key]
            # 높이만 본다. 폭은 글자 수에 따라 흔들려서 검사가 못 된다 —
            # 2026-09-21 실측: 칸 310개를 연달아 두 번 재니 높이는 전부
            # 그대로였고, 폭만 넷이 움직였다(종목 이름·가격 자릿수).
            # 재권님이 말씀하신 「창 크기가 바뀐다」 도 세로 이야기다.
            # 다만 괄호로 표시한 것(문서 전체 · 스크롤바 폭)은 폭도 본다.
            watch_w = key.startswith("(")
            if abs(h - h2) > TOL or (watch_w and abs(w - w2) > TOL):
                moved.append((page, key, (w, h), (w2, h2)))
        for key in cur:
            if key not in cells:
                added.append((page, key))

    cnt = sum(len(v) for v in base["pages"].values())

    # **칸이 생기고 없어지는 것은 오류가 아니다.** 데이터에 따라 나타나는
    # 칸이 있다 — 2026-09-21 에 지수 값·변동 칸(`kh-ix-v` · `kh-ix-c`)이
    # 시세가 안 들어온 시각에 통째로 없었다. 재권님이 말씀하신 것은
    # **「창 크기가 바뀐다」** 이고, 그것은 **남아 있는 칸의 크기**다.
    # 칸 유무까지 오류로 잡으면 장중·장후에 따라 매번 걸려서 아무도 안 믿게 된다.
    if added or gone:
        for page, key in gone:
            print("  (알림) %s  %s — 이번엔 안 나왔습니다" % (page, key))
        for page, key in added:
            print("  (알림) %s  %s — 이번에 나왔습니다" % (page, key))
        print("  └ 데이터에 따라 나타나는 칸입니다. 크기 검사와는 별개입니다.")
        print()

    if not moved:
        print("칸 크기 그대로 — 화면 %d장 · 칸 %d개" % (len(base["pages"]), cnt))
        return 0

    for page, key, (w, h), (w2, h2) in moved:
        dw, dh = w2 - w, h2 - h
        print("%s  %s" % (page, key))
        print("    %d x %d  →  %d x %d   (%+d, %+d)" % (w, h, w2, h2, dw, dh))
    print()
    print("바뀐 것이 맞으면 --save 로 기준을 다시 잡으십시오.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
