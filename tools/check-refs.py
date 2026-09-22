# -*- coding: utf-8 -*-
"""문서가 「…」 로 가리키는 절이 **실재하는지** 센다.

    python tools/check-refs.py     맞으면 0, 깨진 것이 있으면 1 + 어디인지

**왜 있나** — 2026-09-22 에 하루 동안 참조가 **다섯 번** 깨졌다. 넷은 절 제목을
바꾸면서, 하나는 **없는 절을 가리키는 문장을 새로 쓰면서** 났다. 가리키는 곳이
사라지면 읽는 쪽은 **그 룰이 없는 줄 안다.**

**두 문서를 함께 본다.** `holdings/CLAUDE.md` 가 루트 절을 가리키는 일이 흔하다 —
한 파일 안만 보면 그것이 전부 위반으로 잡힌다 (만들자마자 그렇게 걸렸다).
"""
import io
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DOCS = ["CLAUDE.md", "holdings/CLAUDE.md"]

# 「…」 뒤에 이런 말이 오면 **절을 가리키는 것**으로 본다. 그냥 인용한 것과 가른다.
POINTS = r"(?:절|참조|에 있다|에 적|를 따른다|와 같|그대로다)"


def main():
    heads, texts = [], {}
    for p in DOCS:
        try:
            t = io.open(p, encoding="utf-8").read()
        except OSError:
            continue
        texts[p] = t
        # 굵게·백틱을 뺀 제목. 「**맨 아래**」 처럼 강조가 섞이면 못 찾는다
        heads += [re.sub(r"\s+", " ", re.sub(r"[*`]", "", h)).strip()
                  for h in re.findall(r"^#{2,4} (.+)$", t, re.M)]

    bad = 0
    for p, t in texts.items():
        for r in sorted(set(re.findall(r"「([^」]{6,40})」\s*" + POINTS, t))):
            # **양쪽에서 똑같이 뺀다.** 제목에서만 백틱을 빼고 참조에서 안 빼면
            # 「`0` 이 나오면…」 이 영영 안 맞는다 — 2026-09-22 에 만들자마자 그랬다.
            # 날짜 꼬리(「… (2026-09-18 지시)」)도 떼고 견준다.
            # **줄바꿈을 공백 하나로 편다.** 참조가 두 줄에 걸치는 일이 흔한데
            # 제목은 한 줄이라 그대로 견주면 영영 안 맞는다 — 2026-09-22 에
            # 이 도구가 **자기 버그로 세 번째** 걸렸다.
            key = re.sub(r"\s+", " ", re.sub(r"[*`]", "", r)).strip().split(" (")[0]
            if not any(key in h for h in heads):
                print("  %s — 「%s」 가 절 제목에 없습니다" % (p, r))
                bad += 1

    if bad:
        print()
        print("  제목을 바꿨으면 가리키는 곳도 함께 고친다.")
        print("  가리키는 곳이 **본문 굵은 글씨**면 절로 올린다 — 그래야 찾을 수 있다.")
        return 1
    print("  가리키는 곳이 전부 실재합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
