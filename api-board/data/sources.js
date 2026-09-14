/* ==========================================================================
   KJC Studio · API 보드 — 출처와 항목 정의

   ── 이 파일만 고치면 보드 화면이 따라 바뀝니다.

   ── 체크 기준 (중요)
      "지금 홈페이지가 실제로 받아 쓰고 있는가" 입니다.
      받을 수 있다는 것만으로는 체크하지 않습니다.

      on    초록 체크    지금 연결됨 — 화면이 이 값을 받아 쓰고 있음
      todo  빈 체크박스  아직 안 씀 — 받을 수는 있으나 연결 전
      none  회색         불러올 수 없음 — 그 API 가 주지 않는 항목

      빈 체크박스가 곧 할 일 목록이 됩니다.

   ── 2026-09-14 기준, 프론트가 실제로 부르는 것은 여섯 개뿐입니다.
      /api/kis/prices · /api/kis/indices · /api/kis/index-minutes · /api/kis/chart
      /api/dart/disclosures · /api/dart/status
      그래서 on 은 세 줄만 켜져 있습니다.

   ── 참고: holdings/docs/sources.json 에 같은 취지의 등록부가 있습니다.
      그쪽은 주식 페이지가 쓰는 문서이고 이 파일은 보드 화면용입니다.
      나중에 하나로 합치면 좋겠지만, 지금은 구역이 달라 각자 둡니다.
   ========================================================================== */

/* 표의 세로줄 — 왼쪽부터 순서대로 놓입니다 */
const COLS = [
  { id: "toss",   label: "토스" },
  { id: "kis",    label: "KIS" },
  { id: "dart",   label: "DART" },
  { id: "naver",  label: "네이버" }
];

/* 출처 카드 — 위쪽 색 띠로 상태를 구분합니다 */
const SOURCES = [
  {
    id: "toss",
    name: "토스증권",
    state: "key",                       /* 키 받음 */
    desc: "실시간 시세 · 수급",
    tags: ["실시간 200종목", "투자자 수급(당일)", "프로그램매매", "공매도", "대차잔고", "종목명", "발행주식수", "랭킹"],
    limitLeft: "시세 15/초 · 차트 20/초",
    limitRight: "WS 2×100"
  },
  {
    id: "kis",
    name: "한국투자증권",
    state: "live",                      /* 쓰는 중 */
    desc: "시세 요약 · 기본 지표",
    tags: ["현재가", "등락률", "시가총액", "PER", "PBR", "52주 최고저", "캔들", "지수"],
    limitLeft: "20 TPS · 토큰 24시간",
    limitRight: "WS 41종목"
  },
  {
    id: "dart",
    name: "OpenDART",
    state: "live",
    desc: "공시 · 재무 원천",
    tags: ["공시", "재무제표", "EPS 원천", "BPS 원천", "배당", "최대주주", "지분공시", "감사의견"],
    limitLeft: "하루 20,000건",
    limitRight: "분기 · 연 단위"
  },
  {
    id: "naver",
    name: "네이버 금융",
    state: "unofficial",                /* 비공식 */
    desc: "컨센서스 · 뉴스",
    tags: ["목표주가", "투자의견", "리포트", "뉴스"],
    limitLeft: "문서 없음 · 예고 없이 막힐 수 있음",
    limitRight: ""
  }
];

/* 상태 배지 문구 */
const STATE_LABEL = {
  live:       "쓰는 중",
  key:        "키 받음",
  unofficial: "비공식"
};

/* ── 표 ──────────────────────────────────────
   owner : 그 항목을 어느 곳에서 받을지 정해 둔 주인. 배경으로 강조합니다.
           두 곳에서 받으면 값이 어긋나기 때문에 하나만 정합니다.
   cell  : { s: 상태, t: 표시할 글자, n: 작은 덧말 }
   ───────────────────────────────────────── */
const FIELDS = [
  {
    label: "성격",
    cells: {
      toss:  { s: "todo", t: "시세 · 수급" },
      kis:   { s: "on",   t: "시세 · 지표" },
      dart:  { s: "on",   t: "공시 · 재무 원천" },
      naver: { s: "on",   t: "종합", n: "비공식" }
    }
  },
  {
    label: "실시간 구독", owner: "toss",
    cells: {
      toss:  { s: "todo", t: "200종목" },
      kis:   { s: "todo", t: "41종목" },
      dart:  { s: "none" },
      naver: { s: "none" }
    }
  },
  {
    label: "현재가 한 번에", owner: "kis",
    cells: {
      toss:  { s: "todo", t: "가격만" },
      kis:   { s: "on",   t: "등락률·시총·PER·52주" },
      dart:  { s: "none" },
      naver: { s: "todo", t: "있음" }
    }
  },
  {
    label: "투자자 수급", owner: "toss",
    cells: {
      toss:  { s: "todo", t: "당일 · 공식" },
      kis:   { s: "none", t: "없음" },
      dart:  { s: "none" },
      naver: { s: "todo", t: "전일까지" }
    }
  },
  {
    label: "프로그램·공매도·대차", owner: "toss",
    cells: {
      toss:  { s: "todo", t: "있음" },
      kis:   { s: "none", t: "없음" },
      dart:  { s: "none" },
      naver: { s: "todo", t: "일부" }
    }
  },
  {
    label: "종목명", owner: "toss",
    cells: {
      toss:  { s: "todo", t: "한글·영문" },
      kis:   { s: "none", t: "없음" },
      dart:  { s: "todo", t: "있음", n: "기업개황" },
      naver: { s: "todo", t: "있음" }
    }
  },
  {
    label: "발행주식수", owner: "toss",
    cells: {
      toss:  { s: "todo", t: "있음" },
      kis:   { s: "none" },
      dart:  { s: "todo", t: "있음", n: "주식총수" },
      naver: { s: "none" }
    }
  },
  {
    label: "PER · PBR", owner: "kis",
    cells: {
      toss:  { s: "none", t: "없음" },
      kis:   { s: "on",   t: "있음" },
      dart:  { s: "todo", t: "계산 필요" },
      naver: { s: "todo", t: "있음", n: "TTM" }
    }
  },
  {
    label: "EPS · BPS", owner: "dart",
    cells: {
      toss:  { s: "none", t: "없음" },
      kis:   { s: "none", t: "없음" },
      dart:  { s: "todo", t: "원천 있음" },
      naver: { s: "todo", t: "있음" }
    }
  },
  {
    label: "배당", owner: "dart",
    cells: {
      toss:  { s: "none", t: "없음" },
      kis:   { s: "none", t: "없음" },
      dart:  { s: "todo", t: "있음" },
      naver: { s: "todo", t: "있음" }
    }
  },
  {
    label: "공시", owner: "dart",
    cells: {
      toss:  { s: "none", t: "없음" },
      kis:   { s: "none", t: "없음" },
      dart:  { s: "on",   t: "유일" },
      naver: { s: "todo", t: "링크만" }
    }
  },
  {
    label: "재무제표", owner: "dart",
    cells: {
      toss:  { s: "none", t: "없음" },
      kis:   { s: "none", t: "없음" },
      dart:  { s: "todo", t: "유일" },
      naver: { s: "todo", t: "요약만" }
    }
  },
  {
    label: "최대주주 · 지분", owner: "dart",
    cells: {
      toss:  { s: "none", t: "없음" },
      kis:   { s: "none", t: "없음" },
      dart:  { s: "todo", t: "유일" },
      naver: { s: "none", t: "없음" }
    }
  },
  {
    /* 이 줄은 정보만 적습니다. 체크할 것이 아닙니다 */
    label: "지연", plain: true,
    cells: {
      toss:  { t: "실시간" },
      kis:   { t: "실시간" },
      dart:  { t: "분기 · 연 단위", warn: true },
      naver: { t: "실시간~전일" }
    }
  }
];

/* 맨 위 통계 — 표에서 셀 수 없는 것만 여기 적습니다 */
const REVIEWING = 5;            /* 검토 중인 곳 (아직 카드로 만들지 않은 후보) */
const UPDATED_AT = "2026. 09. 14.";
