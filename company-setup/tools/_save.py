"""시황분석 탭 받는 도구 넷이 함께 쓰는 저장 — --out · --also (2026-10-12 재권님 「가 를 먼저」 → (ㄴ) 판 「응 해줘」).

    (없음)          씨앗 파일(company-setup/data/<이름>.json · git 에 담김)에 쓴다 — 손으로 돌릴 때. 지금까지와 같다
    --out <경로>    그 경로에 쓴다 — 자동 받기는 <이름>-live.json(.gitignore)에. 화면은 -live 를 먼저 읽고 없으면 씨앗
    --also <경로>   같은 내용을 그 경로에도 한 벌(여러 번 줄 수 있다 · 서비스방 등). 경로는 도구에 박지 않고 launchd 등록 파일 한 곳에

--out 이 있을 때(사람 없이 돌 때) 못 받은 것이 하나라도 있으면 **옛 파일을 그대로 두고** 종료 1 — 반쯤 빈 값으로 덮지 않는다.
쓰기는 임시 파일 → 바꿔 끼우기(os.replace) — 쓰는 중에 화면이 읽어도 안 깨진다. 무역 발표 도구(fetch-trade.py --also)와 같은 길.
"""
import json, os, sys


def targets(default):
    a = sys.argv
    out = a[a.index("--out") + 1] if "--out" in a and a.index("--out") + 1 < len(a) else None
    also = [a[i + 1] for i, x in enumerate(a[:-1]) if x == "--also"]
    return out, [out or default] + also


def save(data, default, failed, **dump):
    """data 를 쓴다. 돌려주는 값 = (쓴 경로들, 종료코드 덧셈용 0/1)."""
    out, paths = targets(default)
    if out and failed:
        print("못 받은 것이 있어 옛 파일을 그대로 둡니다(%s) — %s" % (", ".join(failed), ", ".join(map(os.path.normpath, paths))))
        return [], 1
    for p in paths:
        d = os.path.dirname(os.path.abspath(p))
        os.makedirs(d, exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, **dump)
        os.replace(tmp, p)
    return paths, 0
