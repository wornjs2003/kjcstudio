#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""관세청 수출입 현황 잠정치를 발표 날 받아 쌓는다 — 시황분석 탭 「무역 발표」 문단이 읽는다.

2026-10-12 재권님 — 「수출입 무역통계가 발표되면 그시간에 맞춰서 읽고 정리해서 시황분석이든 어울리는곳에」 → 「니가 다 해」.

발표 — 관세청(목록에는 재정경제부) · 보도시점 09:00 (원문 PDF 첫 줄 · 2026-10 실측)

    1~10일 잠정치    11일(주말이면 다음 평일)
    1~20일 잠정치    21일 전후
    한 달 잠정치     다음 달 1일(「9월 1일~30일」)
    한 달 확정치     15일 전후 · 기업 규모별은 하순 — 이 둘은 제목만 쌓는다

받는 곳 — KDI 경제교육 · 정보센터 「경제정책자료」(관세청 원문 PDF 를 그대로 붙여 둔다 · 비공식 통로가 아니라 공공기관 게시판)

    목록   https://eiec.kdi.re.kr/policy/materialList.do?search_txt=수출입 현황
    글     /policy/materialView.do?num=<번호>  → 첨부 /policy/callDownload.do?num=…&filenum=1&dtime=…
    PDF    같은 폴더 pdf-text.swift(맥 PDFKit)로 글자를 꺼낸다 — 맥 기준이다(「기준은 맥이다」)

읽는 것 — 요약(수출 · 수입 · 무역수지와 전년 대비) · 조업일수와 일평균 수출 증감 · 주요 품목 · 나라 표(1~10일 · 1~20일 PDF 에만 있다).
**못 읽은 칸은 null + 이유** — 0 으로 메우지 않는다.

    python3 company-setup/tools/fetch-trade.py          새 발표가 있으면 받아 쌓는다
    python3 company-setup/tools/fetch-trade.py --all    목록에 보이는 것을 전부 다시 읽는다(처음 채울 때)
    … --also <경로>                                      받은 파일을 그 경로에도 한 벌 쓴다(여러 번 줄 수 있다)

**서비스방에도 쓴다 (2026-10-12 재권님 「서비스방에도 무역지수 올려줘」)** — 데이터 파일이 .gitignore 라 옮기기(service-deploy)로는
안 간다. launchd 등록 파일이 --also 로 서비스방 경로를 준다 — **경로는 도구에 박지 않고 등록 파일 한 곳에만 둔다.**
그 폴더가 없으면 건너뛰고 알린다(만들지 않는다).

종료 — 0 새 발표를 받음 · 3 새 것 없음 · 2 못 받음(목록 · PDF · 읽기). 발표 날 09:00 부터 0 이 나올 때까지 돌린다.
저장 — company-setup/data/trade-flash.json  {"fetchedAt", "source", "items": [최신순]}
"""
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://eiec.kdi.re.kr"
LIST = BASE + "/policy/materialList.do?search_txt=" + urllib.parse.quote("수출입 현황")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "data", "trade-flash.json")
PDF_TEXT = os.path.join(HERE, "pdf-text.swift")
KST = timezone(timedelta(hours=9))
KEEP = 36                  # 쌓아 두는 발표 수 — 한 달에 셋(1 · 11 · 21일) × 1년
UA = {"User-Agent": "Mozilla/5.0", "Referer": BASE + "/"}


def get(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    return raw if binary else raw.decode("utf-8", errors="replace")


def listing():
    """목록에서 수출입 현황 글 — (번호, 제목, 날짜) 최신순."""
    s = get(LIST)
    rows = []
    for m in re.finditer(r'materialView\.do\?num=(\d+)[^>]*>(.*?)</a>', s, flags=re.S):
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        hit = re.match(r"(.*?수출입 현황\s*\[(잠정치|확정치)\])\s*(\S+)\s+(\d{4}\.\d{2}\.\d{2})", t)
        if hit:
            rows.append((int(m.group(1)), hit.group(1).strip(), hit.group(4).replace(".", "-")))
    return rows


def kind_of(title):
    if "확정치" in title:
        return "final"
    if "기업규모별" in title:
        return "size"
    m = re.search(r"~\s*\d+월\s*(\d+)일", title)
    if m:
        return "1-" + m.group(1)           # 1-10 · 1-20
    return "month"                          # 한 달 잠정치(1일 발표)


def pdf_text(num):
    view = get("%s/policy/materialView.do?num=%d" % (BASE, num))
    m = re.search(r'/policy/callDownload\.do\?num=%d[^"]*' % num, view)
    if not m:
        raise RuntimeError("첨부 링크 없음")
    raw = get(BASE + html.unescape(m.group(0)), binary=True)
    if not raw.startswith(b"%PDF"):
        raise RuntimeError("첨부가 PDF 가 아님")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(raw)
        path = f.name
    try:
        r = subprocess.run(["swift", PDF_TEXT, path], capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(path)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("PDF 글자를 못 꺼냄")
    return r.stdout


def num(s):
    return float(s.replace(",", "").replace("△", "-"))


def signed(v, word):
    return -v if word in ("감소", "적자") else v


def parse(text):
    """요약 · 일평균 · 품목 · 나라. 못 찾은 칸은 None 이고 why 에 이유."""
    flat = re.sub(r"\s+", " ", text)
    tight = re.sub(r"\s+", "", text)
    out, why = {}, []
    m = re.search(r"보도시점.*?(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*\(\S\)\s*(\d{2}:\d{2})", flat)
    out["releasedAt"] = "%s-%02d-%02d %s" % (m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)) if m else None
    m = re.search(r"(\d+월\s*\d+일\s*[~∼]\s*\d+일)\s*기간", flat)
    out["period"] = m.group(1).replace(" ", "") if m else None
    for key, pat in (("export", r"수출은\s*([\d,.]+)억\s*달러로\s*(?:전년동기대비\s*)?([\d.]+)%\s*(증가|감소)"),
                     ("import", r"수입은\s*([\d,.]+)억\s*달러로\s*(?:전년동기대비\s*)?([\d.]+)%\s*(증가|감소)")):
        m = re.search(pat, flat)
        out[key] = {"amt": num(m.group(1)), "yoy": signed(num(m.group(2)), m.group(3)), "unit": "억 달러"} if m else None
        if not m:
            why.append(key + " 요약 줄 없음")
    m = re.search(r"무역수지는\s*([\d,.]+)억\s*달러\s*(흑자|적자)", flat)
    out["balance"] = signed(num(m.group(1)), m.group(2)) if m else None
    if not m:
        why.append("무역수지 줄 없음")
    m = re.search(r"조업일수\[\([’']?(\d+)\)([\d.]+)일,?\([’']?(\d+)\)([\d.]+)일\]고려시일평균수출액"
                  r"\[\([^)]*\)([\d.]+),\([^)]*\)([\d.]+)억달러\]([\d.]+)%(증가|감소)", tight)
    if m:
        out["workdays"] = {"prev": float(m.group(2)), "now": float(m.group(4))}
        out["dailyExport"] = {"prev": float(m.group(5)), "now": float(m.group(6)), "yoy": signed(float(m.group(7)), m.group(8))}
    else:
        out["workdays"] = out["dailyExport"] = None
        why.append("조업일수 · 일평균 줄 없음")
    m = re.search(r"반도체\s*수출\s*비중은\s*([\d.]+)%", flat)
    out["chipShare"] = float(m.group(1)) if m else None

    def table(head, stop):
        a = text.find(head)
        if a < 0:
            return None
        b = text.find(stop, a + 1) if stop else -1
        seg = text[a:b if b > 0 else len(text)]
        ex, im = [], []
        for line in seg.splitlines():
            pairs = re.findall(r"([가-힣][가-힣 ]*?)\s+([\d,]+)\s+(△?[\d.]+)", line)
            for i, (name, amt, yoy) in enumerate(pairs[:2]):
                (ex if i == 0 else im).append({"name": name.replace(" ", ""), "amt": num(amt) / 100, "yoy": num(yoy)})
        return {"export": ex, "import": im} if ex else None
    out["items"] = table("□ 주요품목", "□ 주요국가")
    out["countries"] = table("□ 주요국가", None)
    out["why"] = why
    return out


def main():
    redo = "--all" in sys.argv
    also = [sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == "--also"]
    now = datetime.now(KST)
    try:
        rows = listing()
    except Exception as e:
        print("목록을 못 받았습니다: %s" % type(e).__name__)
        return 2
    if not rows:
        print("목록에서 수출입 현황 글을 하나도 못 찾았습니다 — 모양이 바뀌었을 수 있습니다")
        return 2
    try:
        with open(OUT, encoding="utf-8") as f:
            store = json.load(f)
    except (OSError, ValueError):
        store = {"items": []}
    have = {x["num"]: x for x in store["items"]}
    new, failed = 0, 0
    for n, title, date in rows[:KEEP]:
        if n in have and not redo:
            continue
        rec = {"num": n, "title": title, "date": date, "kind": kind_of(title), "url": "%s/policy/materialView.do?num=%d" % (BASE, n)}
        if rec["kind"] in ("1-10", "1-20", "month"):
            try:
                rec.update(parse(pdf_text(n)))
            except Exception as e:
                rec["why"] = ["원문을 못 읽음: %s" % e]
                failed += 1
        have[n] = rec
        new += 0 if n in store.get("seen", []) else 1
    store = {"fetchedAt": now.isoformat(timespec="seconds"),
             "source": "관세청 수출입 현황 잠정치 원문 PDF · KDI 경제교육·정보센터 경제정책자료",
             "items": sorted(have.values(), key=lambda x: -x["num"])[:KEEP],
             "seen": sorted(have)[-KEEP:]}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(store, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    for dst in also:                        # 서비스방 등 — 같은 내용을 한 벌 더(쓰는 중에 읽혀도 깨지지 않게 임시 파일 → 바꿔 끼우기)
        if not os.path.isdir(os.path.dirname(dst)):
            print("한 벌 더 쓸 폴더가 없어 건너뜀: %s" % os.path.dirname(dst))
            continue
        with open(dst + ".tmp", "w", encoding="utf-8", newline="\n") as f:
            json.dump(store, f, ensure_ascii=False, indent=1)
        os.replace(dst + ".tmp", dst)
        print("한 벌 더 씀: %s" % dst)
    top = store["items"][0]
    print("최신 %s · %s · 수출 %s" % (top["date"], top["title"], (top.get("export") or {}).get("amt", "—")))
    if failed:
        print("원문을 못 읽은 것 %d건 — why 칸에 이유" % failed)
    if new == 0:
        print("새 발표 없음")
        return 3
    print("새로 받음 %d건" % new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
