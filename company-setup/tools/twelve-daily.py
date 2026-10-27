#!/usr/bin/env python3
"""「12시에 만나요」 그날 회차를 맥미니가 혼자 정리해 Insight 영상 분석에 쌓는다 (2026-10-27 지시).

재권님 — 「이대로 12시는 하루에 한번씩 해서 인사이트에 저장해」 → 「맥미니로 옮겨」 →
「맥미니에서 1주일동안 돌게 해주고 그다음에 다되면 나한테 다시 물어보게 해」.

하는 일 (평일 launchd `launchd/kr.kjcstudio.twelve-daily.plist` 가 부른다)
    1 채널 라이브 목록에서 제목에 [12시에 만나요] 와 오늘 날짜가 든 끝난 라이브를 찾는다 — 없으면 끝(쉬는 날 · 아직 방송 중)
    2 그 회차 문서가 이미 있으면 끝 — 하루 두 번 불려도 한 번만 쓴다
    3 한국어 자동자막을 받아 줄을 정리한다(yt-dlp · 돈 안 듦)
    4 무인 claude -p 한 번 — 도구 없음 · 설정 · 훅 안 읽음(--safe-mode) · 글(JSON)만 돌려받는다.
      저장은 이 스크립트가 한다 — 클로드에게 쓰기 권한을 주지 않는다
    5 8765 보드 문서(insight-video-<날짜>-<id>)에 PUT · 목록(insight-video-index) 맨 앞에 넣는다
    6 보드 카드 「매일 정리해 쌓기」 에 한 줄 — 비용(달러) · 토큰 · 걸린 초

비용 — 2026-10-27 실측 한 번 1.34달러(claude-fable-5-1 정가 기준 · 101초 · 입력 47,649 · 출력 8,075 토큰).

시험 기간 — END 다음 날부터는 돌지 않고, 카드에 「계속할까요」 물음을 한 번만 적는다(재권님 지시 그대로).
기간을 늘리거나 끝내는 것은 재권님이 정하신다 — 그때 END 를 고치거나 등록을 내린다.

    python3 company-setup/tools/twelve-daily.py              그날 회차
    python3 company-setup/tools/twelve-daily.py --dry-run    저장 · 카드 없이 결과만 화면에
    python3 company-setup/tools/twelve-daily.py --result-file out.json --video <id> --dry-run
                                                            클로드를 안 부르고 저장 길만 시험
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "holdings", "server"))
from secrets_guard import safe_message  # noqa: E402 — 오류 문구는 카드(밖)로 나가므로 가려 적는다

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHANNEL = "https://www.youtube.com/channel/UCAAvO0ehWox1bbym3rXKBZw/streams"
SHOW = "12시에 만나요"
BOARD = os.environ.get("KJC_BOARD_URL", "http://localhost:8765").rstrip("/") + "/api/board/doc/"
INDEX = "insight-video-index"
EXAMPLE = "insight-video-20261027-D-rmioWI33w"     # 세션이 쓴 첫 회차 — 모양 예시
CARD = "매일 정리해 쌓기"
END = dt.date(2026, 11, 3)                         # 시험 1주일 끝 — 재권님 10-27 「1주일동안」
BUDGET_USD = "3"                                   # 한 번에 이 이상 쓰면 claude 가 스스로 멈춘다(실측 1.34)
ASKED = os.path.join(ROOT, "logs", "twelve-daily.asked")
PATH_ADD = ["/opt/homebrew/bin", os.path.expanduser("~/.local/bin"), "/usr/local/bin"]


def log(msg):
    print("%s %s" % (dt.datetime.now().strftime("%m-%d %H:%M:%S"), msg), flush=True)


def tool(name):
    p = shutil.which(name, path=os.pathsep.join(PATH_ADD + [os.environ.get("PATH", "")]))
    if not p:
        raise SystemExit("%s 를 못 찾았습니다(PATH)" % name)
    return p


def http(method, name, body=None):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(BOARD + name, method=method, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def card(line, ask=False):
    args = [sys.executable, os.path.join(ROOT, "tools", "board-card.py"), CARD]
    args += ["--ask", line] if ask else [line]
    subprocess.run(args, cwd=ROOT, timeout=30, capture_output=True)


def find_today(today):
    out = subprocess.run([tool("yt-dlp"), "--flat-playlist", "--playlist-end", "15", "--print",
                          "%(id)s|%(title)s|%(live_status)s", CHANNEL],
                         capture_output=True, text=True, timeout=120).stdout
    want = "%d년 %d월 %d일" % (today.year, today.month, today.day)
    for row in out.splitlines():
        vid, _, rest = row.partition("|")
        title, _, status = rest.rpartition("|")
        if "[%s]" % SHOW in title and want in title:
            return vid, title, status
    return None


def fetch_subs(vid, work):
    subprocess.run([tool("yt-dlp"), "--skip-download", "--write-auto-subs", "--sub-langs", "ko",
                    "--sub-format", "vtt", "--write-info-json", "-o", os.path.join(work, "%(id)s.%(ext)s"),
                    "https://www.youtube.com/watch?v=" + vid], capture_output=True, timeout=300)
    vtt = os.path.join(work, vid + ".ko.vtt")
    if not os.path.exists(vtt):
        return None, None
    info = json.load(open(os.path.join(work, vid + ".info.json"), encoding="utf-8"))
    rows, last, cur, seen = [], "", 0, set()
    for l in open(vtt, encoding="utf-8").read().split("\n"):
        m = re.match(r"(\d\d):(\d\d):(\d\d)\.\d+ -->", l)
        if m:
            cur = int(m[1]) * 60 + int(m[2])
            continue
        if not l.strip() or "-->" in l or l.startswith(("WEBVTT", "Kind", "Language")):
            continue
        t = re.sub(r"<[^>]+>", "", l).strip().replace("&gt;&gt;", "·")
        if t and t != last and t not in seen:
            rows.append((cur, t))
            seen.add(t)
            last = t
    blocks = {}
    for c, t in rows:
        blocks.setdefault(c // 2, []).append(t)
    text = "\n".join("[%d:%02d] %s" % (k * 2 // 60, k * 2 % 60, " ".join(v)) for k, v in sorted(blocks.items()))
    return text, info


def write(text, example):
    ex = {k: example[k] for k in ("headline", "summary", "method", "sections")}
    prompt = (
        "너는 「12시에 만나요」(김어준의 겸손은힘들다 뉴스공장 유튜브 라이브) 한 회를 정리하는 사람이다. "
        "아래 자동자막을 끝까지 읽고, 예시와 똑같은 JSON 모양으로 오늘 회차를 정리해 **JSON 하나만** 출력하라(설명 · 코드블록 없이).\n"
        "규칙: 한국어로만 · 자막에 있는 말만(지어내지 않음) · 숫자 · 이름은 자막 그대로이되 자동자막이라 틀릴 수 있음을 method 에 적음 · "
        "sections 의 title 끝에 「(분:초 ~)」 · 출연진 주장과 사실을 가름(「…라는 출연진 셈」) · 키는 headline · summary · method · sections 넷.\n"
        "예시:\n" + json.dumps(ex, ensure_ascii=False) + "\n\n자막:\n" + text)
    t0 = time.time()
    r = subprocess.run([tool("claude"), "-p", "--safe-mode", "--tools", "", "--no-session-persistence",
                        "--output-format", "json", "--max-budget-usd", BUDGET_USD],
                       input=prompt, capture_output=True, text=True, timeout=900, cwd=tempfile.gettempdir())
    if r.returncode != 0:
        raise RuntimeError("claude 종료 %d" % r.returncode)
    out = json.loads(r.stdout)
    out["_secs"] = round(time.time() - t0)
    return out


def parse(result):
    s = result.get("result") or ""
    s = s[s.find("{"): s.rfind("}") + 1]
    d = json.loads(s)
    for k in ("headline", "summary", "sections"):
        if not d.get(k):
            raise ValueError("결과에 %s 가 비었습니다" % k)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--video", help="오늘 회차 대신 이 영상 id")
    ap.add_argument("--result-file", help="claude 를 부르지 않고 이 결과(JSON)를 쓴다 — 시험용")
    a = ap.parse_args()

    today = dt.date.today()
    if today > END and not a.dry_run:
        if not os.path.exists(ASKED):
            card("「12시에 만나요」 맥미니 1주일 시험(~%s)이 끝났습니다 — 계속 돌릴까요, 멈출까요(비용은 이 카드의 날마다 줄)" % END, ask=True)
            open(ASKED, "w").write(dt.datetime.now().isoformat())
            log("시험 기간 끝 — 카드에 물음을 적었습니다")
        else:
            log("시험 기간 끝 — 이미 물었습니다 · 아무것도 안 함")
        return 0

    if a.video:
        vid, title = a.video, None
    else:
        hit = find_today(today)
        if not hit:
            log("오늘 회차 없음(쉬는 날이거나 목록에 아직 없음)")
            return 0
        vid, title, status = hit
        if status != "was_live":
            log("오늘 회차 아직 끝나지 않음(%s) · %s" % (status, vid))
            return 0

    with tempfile.TemporaryDirectory() as work:
        text, info = fetch_subs(vid, work)
        if not text:
            log("자막 아직 없음 · %s" % vid)
            if not a.dry_run:
                card("%s 자막 아직 없음(%s) — 다음 회에 다시" % (dt.datetime.now().strftime("%H:%M"), vid))
            return 0

    day = dt.datetime.strptime(info.get("upload_date") or today.strftime("%Y%m%d"), "%Y%m%d").date()
    doc_id = "insight-video-%s-%s" % (day.strftime("%Y%m%d"), vid)
    if not a.dry_run and http("GET", doc_id):
        log("이미 있음 · %s" % doc_id)
        return 0

    example = http("GET", EXAMPLE)["data"]
    result = json.load(open(a.result_file, encoding="utf-8")) if a.result_file else write(text, example)
    body = parse(result)
    doc = {
        "id": doc_id, "kind": "video", "date": day.isoformat(),
        "source": {
            "channel": info.get("channel") or example["source"]["channel"], "show": SHOW,
            "title": info.get("title") or title, "url": "https://www.youtube.com/watch?v=" + vid,
            "thumbnail": "https://i.ytimg.com/vi/%s/hqdefault.jpg" % vid,
            "duration": info.get("duration_string") or "",
        },
        "method": body.get("method") or example["method"],
        "writer": "맥미니(무인 claude -p)",
        "headline": body["headline"], "summary": body["summary"], "sections": body["sections"],
    }
    cost = result.get("total_cost_usd")
    u = result.get("usage") or {}
    tok_in = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    note = "%s 맥미니 정리 %s · %s초 · 입력 %s · 출력 %s 토큰 · %s달러" % (
        dt.datetime.now().strftime("%H:%M"), doc_id, result.get("_secs", "—"), tok_in or "—",
        u.get("output_tokens") or "—", ("%.2f" % cost) if cost is not None else "못 잼")

    if a.dry_run:
        print(json.dumps(doc, ensure_ascii=False, indent=1)[:2000])
        log("(시험 · 저장 안 함) " + note)
        return 0

    http("PUT", doc_id, {"data": doc})
    idx = http("GET", INDEX)
    d = idx["data"]
    item = {"id": doc_id, "date": doc["date"], "headline": doc["headline"], "show": SHOW,
            "duration": doc["source"]["duration"], "group": SHOW}
    d["items"] = [item] + [i for i in d["items"] if i.get("id") != doc_id]
    http("PUT", INDEX, {"data": d, "updatedAt": idx.get("updatedAt")})
    card(note)
    log(note)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        msg = "%s 맥미니 정리 실패 — %s: %s" % (dt.datetime.now().strftime("%H:%M"), type(e).__name__, safe_message(e, 200))
        log(msg)
        try:
            card(msg)
        except Exception:
            pass
        sys.exit(1)
