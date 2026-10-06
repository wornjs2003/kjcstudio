# vendor — 바깥에서 받아 온 라이브러리·글꼴 (2026-10-06 · 「로딩이 넘 느린데 개선」)

우리 코드가 아니다. 고치지 않는다 — 갱신하면 되돌아간다. 색 검사 · 룰 검사는 `vendor` 폴더를 뺀다.

| 무엇 | 어디서 | 판 |
|---|---|---|
| maplibre-gl.js · .css | unpkg.com/maplibre-gl | 5.24.0 |
| pmtiles.js | unpkg.com/pmtiles | 4.5.0 |
| basemaps.js | unpkg.com/@protomaps/basemaps | 5.7.2 |
| three/three.module.min.js · addons 넷 | cdn.jsdelivr.net/npm/three | 0.160.0 |
| basemaps-assets/fonts · sprites | protomaps.github.io/basemaps-assets | 지구본이 실제로 요청한 글꼴 넷 · 스프라이트 둘만 |

왜 — 지구본이 unpkg · protomaps 를 매번 거쳐 글꼴 하나에 2.6~4.7초(헤드리스 실측)였고, 3D 는 jsdelivr 에서 three.js 를 받았다.
우리 서버(맥미니)가 내면 바깥 변동이 없다. 지도 타일(pmtiles)은 저장소 밖 `/maps/` 그대로.
