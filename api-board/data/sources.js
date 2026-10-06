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

   ── 몇 개가 켜져 있는지는 여기 적지 않습니다. 세면 나오는 값이라 낡습니다
      (CLAUDE.md 「세면 나오는 값은 본문에 적지 않는다」).

      지금 무엇을 부르는지는 이렇게 셉니다.

          grep -rhoE "/api/[a-z-]+/[a-z-]+" holdings/js/ holdings/*.html company-setup/ --include='*.js' --include='*.html' | sort -u

      **html 을 빼면 하나가 덜 나옵니다.** 화면이 부르는 곳이 js 에만
      있지 않습니다 — 적어둔 명령과 적어둔 숫자가 어긋나면 다음 사람이
      「숫자가 틀렸다」 로 읽습니다 (2026-09-21 에 실제로 그랬습니다).

      **각 줄의 `api` 가 그 주소들입니다 (2026-10-06).** 위 명령의 결과에서 `api` 들과
      `NOT_DATA_API` 를 빼면 아무것도 남지 않아야 합니다 — 남으면 표에 없는 주소, 거꾸로
      `api` 에만 있으면 화면이 안 부르는데 표가 「쓰는 중」 이라 적은 것입니다.
      API 는 지금 다듬어 가는 중이라 자주 어긋납니다 (재권님 2026-10-06 — 「앞으로 자주
      정리되어야 함」). 맞춰 보는 검사는 아직 손으로 합니다.

      **부르는 것과 되는 것은 다릅니다.** 화면이 부르는데 서버에 경로가
      없을 수 있으니, 센 다음 하나씩 눌러 봐야 on 인지 알 수 있습니다.

   ── 2026-09-14 에는 여섯 개였고 on 이 세 줄이었습니다. 2026-09-21 에
      다시 세니 스물셋이었고, **투자자 수급이 「KIS 없음(회색)」 으로 남아
      있었습니다.** 회색은 「그 API 가 주지 않는다」 는 뜻인데 KIS 가 주고
      있었고 화면이 이미 쓰고 있었습니다. **일주일이면 이만큼 낡습니다.**

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
    label: "현재가 한 번에", owner: "kis", api: ["/api/kis/price", "/api/kis/prices", "/api/kis/quotes"],
    cells: {
      toss:  { s: "todo", t: "가격만" },
      kis:   { s: "on",   t: "등락률·시총·PER·52주" },
      dart:  { s: "none" },
      naver: { s: "todo", t: "있음" }
    }
  },
  {
    /* owner 를 toss 에서 kis 로 옮겼다 — 토스를 기다릴 것 없이 KIS 가
       주고 있고 이미 쓰는 중이다 (2026-09-21 실측). */
    label: "투자자 수급", owner: "kis", api: ["/api/kis/investor", "/api/kis/investor-estimate", "/api/naver/integration"],
    cells: {
      toss:  { s: "todo", t: "당일 · 공식" },
      kis:   { s: "on",   t: "종목별 30일", n: "확정치" },
      dart:  { s: "none" },
      naver: { s: "on",   t: "5일 · 외국인 보유율", n: "종목 모달 머리 통계" }
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
    /* 아래 넷은 2026-09-14 뒤에 붙었다. 그때 표에 없던 것들이다. */
    label: "호가 · 매수/매도 비율", owner: "kis", api: ["/api/kis/asking"],
    cells: {
      toss:  { s: "todo", t: "있음" },
      kis:   { s: "on",   t: "10단계 · buyPct" },
      dart:  { s: "none" },
      naver: { s: "none" }
    }
  },
  {
    label: "업종 등락률", owner: "kis", api: ["/api/kis/sectors", "/api/naver/groups", "/api/naver/stocks"],
    cells: {
      toss:  { s: "none" },
      kis:   { s: "on",   t: "코스피·코스닥 전 업종" },
      dart:  { s: "none" },
      naver: { s: "on",   t: "업종 · 테마 묶음", n: "홈 업종 카드 · KIS 에 테마는 없음" }
    }
  },
  {
    label: "등락률 순위 · 순매수 상위", owner: "kis",
    cells: {
      toss:  { s: "todo", t: "랭킹" },
      /* 서버는 주는데 화면이 안 부른다 — EPS·BPS 와 같은 자리다.
         2026-09-21 에 내가 on 으로 적었다가 홈페이지_정리가 잡았다.
         **초록인데 실제로는 안 쓰면 할 일이 목록에서 빠진다.** */
      kis:   { s: "todo", t: "30행 고정", n: "받는 중 · 화면이 안 씀 · 순매수 상위는 가집계" },
      dart:  { s: "none" },
      naver: { s: "none" }
    }
  },
  {
    label: "뉴스", owner: "naver", api: ["/api/naver/news", "/api/news/feed", "/api/news/issues", "/api/news/alerts", "/api/news/stored"],
    cells: {
      toss:  { s: "none" },
      kis:   { s: "none" },
      dart:  { s: "none", t: "없음" },
      naver: { s: "on",   t: "종목별 · 주제별", n: "언론사 RSS 도 함께 씀" }
    }
  },
  {
    label: "PER · PBR", owner: "kis", api: ["/api/kis/price"],
    cells: {
      toss:  { s: "none", t: "없음" },
      kis:   { s: "on",   t: "있음" },
      dart:  { s: "todo", t: "계산 필요" },
      naver: { s: "todo", t: "있음", n: "TTM" }
    }
  },
  {
    /* owner 를 dart 에서 kis 로 옮겼다 — 종목 모달 재무 카드가 KIS 값을 쓴다 (2026-10-06 실측).
       전에는 「받는 중 · 화면이 안 씀」 이라 todo 였다 (2026-09-21). */
    label: "EPS · BPS", owner: "kis", api: ["/api/kis/price", "/api/kis/finance"],
    cells: {
      toss:  { s: "none", t: "없음" },
      kis:   { s: "on",   t: "있음", n: "재무 카드가 씀" },
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
    label: "공시", owner: "dart", api: ["/api/dart/disclosures"],
    cells: {
      toss:  { s: "none", t: "없음" },
      kis:   { s: "none", t: "없음" },
      dart:  { s: "on",   t: "유일" },
      naver: { s: "todo", t: "링크만" }
    }
  },
  {
    /* KIS 칸이 「없음」 이었다 — KIS 재무 다섯(대차 · 손익 · 비율 · 수익성 · 성장성)을 분기 30개로 받아
       종목 모달 재무 카드가 쓴다 (2026-10-06 실측). 현금흐름표 · EBITDA 는 KIS 에 없어 DART 몫으로 남는다. */
    label: "재무제표", owner: "kis", api: ["/api/kis/finance"],
    cells: {
      toss:  { s: "none", t: "없음" },
      kis:   { s: "on",   t: "분기 30개", n: "현금흐름표 없음" },
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
    /* 아래 넷은 2026-10-06 첫 정리에서 붙였다 — 화면이 부르는데 표에 줄이 없던 것 */
    label: "차트 봉 (분 · 일 · 주 · 월)", owner: "kis", api: ["/api/kis/chart"],
    cells: {
      toss:  { s: "todo", t: "차트 20/초" },
      kis:   { s: "on",   t: "분봉 · 일봉 · 주봉 · 월봉" },
      dart:  { s: "none" },
      naver: { s: "todo", t: "일봉", n: "비공식" }
    }
  },
  {
    label: "지수 (코스피 · 코스닥 · 해외)", owner: "kis", api: ["/api/kis/indices", "/api/kis/index-candles", "/api/kis/index-minutes"],
    cells: {
      toss:  { s: "none" },
      kis:   { s: "on",   t: "시세 · 일봉 · 분봉", n: "해외지수 · 환율도" },
      dart:  { s: "none" },
      naver: { s: "none" }
    }
  },
  {
    label: "체결 (틱)", owner: "kis", api: ["/api/kis/ticks"],
    cells: {
      toss:  { s: "todo", t: "있음" },
      kis:   { s: "on",   t: "종목 모달 체결" },
      dart:  { s: "none" },
      naver: { s: "none" }
    }
  },
  {
    label: "종목 목록 · 지수 구성종목", owner: "dart", api: ["/api/dart/universe", "/api/dart/members"],
    cells: {
      toss:  { s: "todo", t: "종목명" },
      kis:   { s: "none" },
      dart:  { s: "on",   t: "시장 전체 목록 · 구성종목", n: "순위표 · 일정이 씀" },
      naver: { s: "none" }
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
/* 검토 중인 곳 — 조사 기록(holdings/docs/sources.json)에 있는데 아직 위 출처 카드로 만들지 않은 것.
   전에는 「5」 를 손으로 박아 무엇을 셌는지가 없었다 (2026-09-21). 2026-10-06 에 세어 보니 이 다섯이었다. */
const REVIEW_LIST = ["야후 파이낸스", "KRX Open API", "한국은행 ECOS", "CNN 공포탐욕지수", "업비트"];
const REVIEWING = REVIEW_LIST.length;
const UPDATED_AT = "2026. 10. 06.";

/* 데이터가 아닌 주소 — 화면이 부르지만 표의 줄이 될 것이 아니다(살아 있나 · 보드 저장 · 롱폴 · 서버 통계).
   각 줄의 `api` 와 이 목록을 합치면 화면이 부르는 /api/* 주소가 빠짐없이 들어 있어야 한다 — 대조는 맨 위 주석 */
const NOT_DATA_API = ["/api/board/doc", "/api/kis/health", "/api/kis/stats", "/api/kis/poll", "/api/dart/status"];
