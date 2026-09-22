# 문서 저장

`holdings/server/docstore.py` 가 여기에 씁니다. **git 에 안 올립니다** —
CLAUDE.md 「저장은 이 PC 안에만 둔다」.

    <이름>.json              문서 하나
    history/<이름>-<시각>.json  직전 것

**이 폴더가 비어 있어도 맞습니다.** 아직 아무도 안 썼다는 뜻입니다.
나중에 맥미니에 백업서버를 세우면 **이 폴더만** 옮기면 됩니다 —
경로는 `docstore.py` 의 `DOC_ROOT` 한 곳에서 정합니다.
