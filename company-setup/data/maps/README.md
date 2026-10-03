# 지도 자료 파일 모양 (company-setup/data/maps/<이름>.json) — 엔진 flowmap.html 이 읽는다

{
  "id": "rates",                                  // 파일 이름과 같게
  "title": "금리 · 유가 · 주식 — 돈이 흐르는 길",   // 화면 제목
  "sub": "한 줄 설명 — 왼쪽에서 오른쪽으로 무엇이 흐르나",
  "asOf": "2026-10-03",                           // 판단 시점
  "note": "자료 출처 · 판단 근거 한두 줄",

  "columns": [                                    // 왼쪽→오른쪽 열. 열마다 머리와 칸들
    { "head": "통화 정책",
      "items": [
        { "id": "fed", "type": "node", "k": "중앙은행", "t": "기준금리", "d": "연준 · 한국은행", "choke": false },
        { "id": "krbank", "type": "cell", "k": "국내 은행", "t": "(종목은 stocks 에서 채움)" }
      ] }
  ],
  // type: "node" = 큰 칸(k 작은 머리 · t 제목 · d 설명/회사) · "cell" = 작은 칸(k 머리 · t 종목 — stocks 가 있으면 칩으로 바뀜)
  // choke: true 면 병목(빨간 고리). id 는 영문 소문자 짧게 · 열 안에 { "gap": true } 를 넣으면 빈 줄

  "lineTypes": {                                  // 선 종류 — 색은 토큰 이름만: ok(초록) · accent(파랑) · warn(주황) · danger(빨강)
    "rate":  { "label": "금리 · 통화", "color": "accent" },
    "oil":   { "label": "유가 · 원자재", "color": "warn" },
    "equity":{ "label": "주식 · 업종",  "color": "ok" }
  },
  "links":  [ ["fed", "bond", "rate"], ["bond", "usd", "rate"] ],   // [from, to, lineType] — 왼쪽에서 오른쪽으로
  "extra":  [ ["usd", "oil", "oil"] ],                              // 칸을 골랐을 때만 보이는 보조 연결

  "info": {                                       // 칸 설명 — 오른쪽 칸에 뜬다
    "fed": { "what": "무엇인가 한두 문장", "watch": "볼 것(지표 · 일정)", "choke": "(병목이면) 왜 병목인가" }
  },

  "scenarios": [                                  // (선택) 「오를 때 / 내릴 때」 단추 — 켜면 칸에 + − 배지
    { "id": "up", "label": "금리 오를 때", "effects": { "bank": "+", "growth": "-", "oilref": "±" } },
    { "id": "down", "label": "금리 내릴 때", "effects": { "bank": "-", "growth": "+" } }
  ],

  "grades": { "lead": "대장주", "driver": "주도주", "parts": "소부장주" },   // 지도마다 이름을 바꿔도 된다(예: 수혜주 · 피해주)
  "stocks": [                                     // 종목 — node 는 칸 id. code 는 KRX 6자리 — 확실하지 않으면 null
    { "name": "KB금융", "code": null, "node": "krbank", "grade": "lead", "market": "KR" }
  ],
  "sites": [                                      // (선택) 세계 지도의 점 — 회사 본사 · 항만 · 산유지. 좌표 [경도, 위도] 도시 수준
    { "name": "뉴욕 연준", "company": "연준", "node": "fed", "at": [-74.01, 40.71] }
  ],
  "routes": [                                     // (선택) 지도에 그릴 길 — 항로 · 송유관. coords 는 [경도, 위도] 차례
    { "name": "북극항로(북동항로)", "type": "equity", "coords": [[129.0, 35.1], [141.0, 41.0]] }
  ]
}

규칙
- 숫자(코드 · 좌표)를 지어내지 않는다. 모르면 null 로 두고 note 에 적는다. 좌표는 도시 수준으로, 알고 있는 큰 도시·항만만
- 색은 토큰 이름만(ok · accent · warn · danger). #색 · rgb 금지
- 등급 · 연결은 분석 판단이다 — note 에 「무엇을 근거로」 한 줄
- 칸은 열 다섯 이내 · 칸 20개 안팎 · links 20줄 안팎(AI 생태계 지도와 비슷한 크기)
