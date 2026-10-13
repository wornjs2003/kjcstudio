#!/usr/bin/env python3
"""시황분석 글 검사 — 저장 전에 틀을 센다. 걸리면 저장하지 않는다 (2026-10-12 재권님 「스킬로 만들어서 항상 같은 룰 안에 글이 나와야」 ·
창구 권함 — 「검사에 걸리게 쓴다」). 스킬 market-brief 가 부른다.

    python3 company-setup/tools/check-market-note.py [글 json]     기본 company-setup/data/market-note.json

센다 — 한 줄 요지 · 갈래 다섯이 이 순서(제목이 낱말로 시작) · 갈래마다 값 줄 2~5 · 「읽기」 · 앞으로 볼 것 1 이상 · 한계 1 이상 ·
writtenAt · basis · 한국어(tools/hook-korean.py 의 judge 를 가져다 쓴다 — 기준을 두 곳에 두지 않는다) ·
「오늘」 낱말(날짜로 쓴다 · 스킬 1-1) · 원인을 말한 줄에 출처 주소 · 「읽기」 가 단정으로 끝남(「~입니다」 만 — 「~로 읽힌다 · ~일 수 있다」 를 쓴다)
(qa 시뮬레이션 2026-10-12 의견 — 첫 판에서 셋 다 났다). 글의 숫자가 화면 파일에 있는지는 아직 안 센다
종료 0 통과 · 1 걸림(어긋난 자리를 낸다) · 2 못 읽음
"""
import importlib.util, json, os, re, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ORDER = ["금리", "경기", "시장 반응", "한국", "원자재"]   # 갈래 제목의 머리 낱말 — 「1. 금리 · 물가 — …」 처럼 번호 뒤에 온다
OPTIONAL = ["대외변수"]   # 뒤에 붙을 수 있는 갈래 — 화면에 대외변수 칸이 있으면 쓰고 없으면 안 쓴다(재권님 10-12 · 10-13 「응 넣어줘」 로 여섯째 갈래 판을 넣음)


def korean_judge():
    spec = importlib.util.spec_from_file_location("hook_korean", os.path.join(ROOT, "tools", "hook-korean.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.judge


def texts(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            if not k.startswith("_"):
                yield from texts(v)
    elif isinstance(x, list):
        for v in x:
            yield from texts(v)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "data", "market-note.json")
    try:
        N = json.load(open(path, encoding="utf-8"))
    except Exception as ex:
        print("못 읽음:", path, type(ex).__name__)
        return 2
    bad = []
    for k in ("writtenAt", "basis", "one"):
        if not str(N.get(k) or "").strip():
            bad.append("%s 이 비었다" % k)
    S = N.get("sections") or []
    heads = [re.sub(r"^\s*\d+\.\s*", "", s.get("h", "")) for s in S]
    if not len(ORDER) <= len(S) <= len(ORDER) + len(OPTIONAL):
        bad.append("갈래가 %d개 — %d개(+ 뒤에 %s)여야 한다(%s)" % (len(S), len(ORDER), " · ".join(OPTIONAL), " · ".join(ORDER)))
    for i, want in enumerate(ORDER + OPTIONAL):
        if i < len(heads) and not heads[i].startswith(want):
            bad.append("%d번째 갈래가 「%s」 — 「%s」 로 시작해야 한다" % (i + 1, heads[i], want))
    for s in S:
        n = len(s.get("items") or [])
        if not 2 <= n <= 5:
            bad.append("「%s」 값 줄이 %d개 — 2~5" % (s.get("h"), n))
        if not str(s.get("read") or "").strip():
            bad.append("「%s」 에 「읽기」 가 없다" % s.get("h"))
    flat = lambda x: " ".join(texts(x))
    for s in S:
        for it in s.get("items") or []:
            t = flat(it)
            if "오늘" in t.replace("오늘의 시황", ""):   # 화면 칸 이름 「오늘의 시황」 은 낱말이 아니라 이름이다
                bad.append("「오늘」 낱말 — 날짜로 쓴다: " + t[:40])
            if "기사" in t and "http" not in t:
                bad.append("기사를 말한 줄에 출처 주소가 없다: " + t[:40])
        r = str(s.get("read") or "").strip()
        # 「읽기」 의 마지막 문장만 어간으로 본다(qa 재시뮬레이션 · 앞에 해석 낱말이 있어도 끝이 단정이면 건다)
        lastsent = [x for x in re.split(r"(?<=[.!?。])\s+", r) if x.strip()][-1:] or [""]
        if r and not re.search(r"(읽히|읽힌|읽힙|보이|보인|보입|수 있|수도 있|가능성|듯|추정|판단)", lastsent[0]):
            bad.append("「%s」 의 「읽기」 가 단정으로 끝난다 — 「~로 읽힌다 · ~일 수 있다」" % s.get("h"))
    if "오늘" in str(N.get("one", "")):
        bad.append("한 줄 요지에 「오늘」 — 날짜로 쓴다")
    if not N.get("next"):
        bad.append("앞으로 볼 것이 없다")
    if not N.get("limits"):
        bad.append("한계가 없다")
    try:
        judge = korean_judge()
        why = judge(" ".join(texts({k: v for k, v in N.items() if k != "basis"})))
        if why:
            bad.append("한국어가 아니다 — " + why)
    except Exception as ex:
        bad.append("한국어 검사를 못 돌렸다(%s)" % type(ex).__name__)
    if bad:
        print("걸림 %d — %s" % (len(bad), os.path.normpath(path)))
        for b in bad:
            print("  ·", b)
        return 1
    print("통과 — 갈래 %d · 값 줄 %d · 앞으로 볼 것 %d · 한계 %d · %s" % (
        len(S), sum(len(s.get("items") or []) for s in S), len(N["next"]), len(N["limits"]), os.path.normpath(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
