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
import sys, os, json, base64, struct, socket, subprocess, time, urllib.request, argparse

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
BASE = "http://localhost:8765/holdings/"

# 칸이 몇 px 까지 달라져도 넘어가나. 0 이면 한 픽셀도 못 바뀐다.
TOL = 1

MEASURE = r"""
(() => {
  const root = document.querySelector('.kh-app') || document.body;
  const out = {};
  const seen = {};
  const walk = (el, depth) => {
    if (depth > 3) return;
    for (const c of el.children) {
      const cn = (typeof c.className === 'string') ? c.className.trim() : '';
      const cls = cn ? cn.split(/\s+/)[0] : '';
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
    while True:
        h = rd(2)
        op, n = h[0] & 0x0F, h[1] & 0x7F
        if n == 126:   n = struct.unpack("!H", rd(2))[0]
        elif n == 127: n = struct.unpack("!Q", rd(8))[0]
        payload = rd(n)
        if op == 1:
            return json.loads(payload.decode())


def measure_all():
    """모든 화면을 재서 {화면: {칸: [폭, 높이]}} 를 돌려준다."""
    try:
        urllib.request.urlopen(BASE, timeout=5)
    except Exception:
        print("서버가 없습니다 — holdings/preview.bat 로 8765(holdings 미리보기) 를 먼저 띄우십시오")
        sys.exit(2)

    if not os.path.exists(CHROME):
        print("크롬을 못 찾았습니다: %s" % CHROME)
        sys.exit(2)

    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
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
        result = {}
        for page in PAGES:
            call("Page.navigate", {"url": BASE + page})
            time.sleep(7)          # 시세·차트가 그려질 때까지
            r = call("Runtime.evaluate", {"expression": MEASURE, "returnByValue": True})
            val = r.get("result", {}).get("result", {}).get("value")
            if not val:
                print("  %s — 재지 못했습니다" % page)
                continue
            result[page] = json.loads(val)
        return result
    finally:
        proc.terminate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true", help="지금 화면을 기준으로 삼는다")
    args = ap.parse_args()

    now = measure_all()

    if args.save:
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"view": [VIEW_W, VIEW_H], "headless": True,
                       "잰날": time.strftime("%Y-%m-%d"), "pages": now}, f,
                      ensure_ascii=False, indent=1, sort_keys=True)
        cnt = sum(len(v) for v in now.values())
        print("기준을 잡았습니다 — 화면 %d장 · 칸 %d개" % (len(now), cnt))
        print("  %s" % BASELINE)
        return 0

    if not os.path.exists(BASELINE):
        print("기준이 없습니다. 먼저 --save 로 잡으십시오")
        return 2

    with open(BASELINE, encoding="utf-8") as f:
        base = json.load(f)

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
        for key, (w, h) in cells.items():
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

    if not moved and not added and not gone:
        cnt = sum(len(v) for v in base["pages"].values())
        print("칸 크기 그대로 — 화면 %d장 · 칸 %d개" % (len(base["pages"]), cnt))
        return 0

    for page, key, (w, h), (w2, h2) in moved:
        dw, dh = w2 - w, h2 - h
        print("%s  %s" % (page, key))
        print("    %d x %d  →  %d x %d   (%+d, %+d)" % (w, h, w2, h2, dw, dh))
    for page, key in gone:
        print("%s  %s — 없어졌습니다" % (page, key))
    for page, key in added:
        print("%s  %s — 새로 생겼습니다" % (page, key))
    print()
    print("바뀐 것이 맞으면 --save 로 기준을 다시 잡으십시오.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
