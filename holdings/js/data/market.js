/* ==========================================================================
   종목·지수 목록

   여기에는 '무엇이 있는지'만 둡니다. 가격·등락·거래량·재무처럼 시시각각
   바뀌는 값은 두지 않습니다. 예시 숫자를 넣어 두면 화면에 실제 시세처럼
   보여서, 연결이 안 된 건지 시세가 그런 건지 구분할 수 없기 때문입니다.

   값은 전부 서버(/api/kis/*)에서 받아 채웁니다. 못 받으면 화면에
   "불러오는 중" 또는 "—" 이 남습니다. 그게 아직 연결되지 않았다는 표시입니다.
   ========================================================================== */

/* ── 지수 ──
   지수 목록은 여기 없다. 화면이 쓰는 것은 js/home.js 의 INDEX_CELLS 하나다.
   전에는 INDEX_LIST · INDEX_NOT_CONNECTED 가 여기 있었는데 **둘 다 아무 데서도
   import 되지 않는 죽은 목록**이었다 (2026-09-17 확인). 지수 띠 구현이 home.js 로
   옮겨가면서 남은 것으로 보이고, 내용도 낡아 있었다 — 「아직 안 준다」는 일곱 중
   셋(S&P 500 · NASDAQ · 원/달러)이 이미 화면에 나오고 있었다. */

/* 아이콘에 쓰는 회사 색(brand)은 각 기업이 쓰는 대표색입니다.
   그림이 있으면 그림을 깔고, 없으면 이 색 위에 이름 두 글자를 얹습니다
   (js/components/stock-icon.js).

   ── 색을 어디서 가져왔나 (2026-09-17) ──

   대표색을 모르는 종목에는 #8b95a1 (회색)을 넣어 두었습니다. 그렇게 남아 있던
   19개를 uidata/icons/<종목코드>.png 에서 뽑아 17개를 채웠습니다.
   아이콘은 토스 종목 아이콘이고 96px 입니다 (uidata/README.md).

   뽑는 방법입니다.
     1. 불투명 픽셀만 본다
     2. 흰 바탕은 뺀다. 안 빼면 어느 로고나 흰색이 나온다
     3. 채도 있는 픽셀을 색상(hue) 15도 바구니로 나눠, 채도 가중 합이 가장 큰
        바구니의 중앙값을 쓴다 — 가장 많이 쓰인 색이 아니라 눈에 띄는 색이다
     4. 유채색이 3% 도 안 되면 회색조 로고로 본다. KT 는 검은 바탕이다
     5. 흰 바탕에 묻히거나 검정으로 뭉개질 때만 밝기를 당긴다
        (WCAG 상대휘도 0.015 ~ 0.78. 위 한계는 이미 쓰고 있던 카카오
         노랑 #f7e600 의 0.763 에 맞췄다)

   아이콘이 그룹 로고를 그대로 쓰는 곳 — 삼성생명·삼성에스디에스는 둘 다
   SAMSUNG 워드마크입니다 — 은 아이콘이 그룹색을 확인해 준 것으로 보고
   아래 BRAND_GROUPS 에 이미 있는 값을 그대로 적었습니다. 같은 빨강을 두 가지
   값으로 적지 않기 위해서입니다 (삼성전자가 전부터 그렇게 되어 있습니다).
     LG(003550) · SK(034730) · 삼성생명 · 삼성에스디에스 ·
     카카오뱅크 · 카카오페이 · 현대로템

   아직 #8b95a1 인 두 개 — 이 회색이 곧 "대표색을 모른다" 는 표시입니다.
     넷마블(251270)           아이콘 바탕이 베이지고 눈에 띄는 색은 마스코트
                              노랑뿐인데, 카카오 노랑과 구분되지 않고 그 위에
                              얹는 흰 글자도 안 읽힙니다
     셀트리온헬스케어(091990)   아이콘이 없습니다. 2023년 셀트리온에 합병되어
                              시가총액 목록에 아예 없습니다
                              (uidata/icons/index.json 의 '없음' 에도 없다) */

/* ── 관심종목 ──
   시세는 /api/kis/prices 가 채운다. 메모는 브라우저에 저장된다(store/memo.js). */
export const WATCHLIST = [
  { code: '005930', name: '삼성전자',            sector: '반도체', brand: '#1428a0' },
  { code: '000660', name: 'SK하이닉스',          sector: '반도체', brand: '#e5231b' },
  { code: '035420', name: 'NAVER',               sector: 'IT', brand: '#03c75a' },
  { code: '035720', name: '카카오',              sector: 'IT', brand: '#f7e600' },
  { code: '005380', name: '현대차',              sector: '자동차', brand: '#002c5f' },
  { code: '373220', name: 'LG에너지솔루션',      sector: '2차전지', brand: '#a50034' },
  { code: '207940', name: '삼성바이오로직스',    sector: '바이오', brand: '#0d4a9a' },
  { code: '068270', name: '셀트리온',            sector: '바이오', brand: '#00a0e9' },
];

/* 「자주 보는 종목」(PRIORITY_CODES) 은 2026-09-18 에 없앴다.
   그 둘만 5초, 나머지는 30초로 받았는데 **같은 화면에서 종목마다 기준
   시각이 달라졌다** (재권님 지시 — "모든값은 통일해야해").
   서버·워커의 FAST_CODES 도 같이 사라졌다. */

/* ── 시장 전체 종목 ──
   순위 탭(거래상위·상승률 등)이 쓰는 목록. 정렬 기준이 되는 값(거래량·시총·
   공매도 비율)은 아직 받아올 곳이 없어서, 해당 탭은 비어 있다고 표시한다.
   ─ 할 일: 거래량·시가총액·공매도 잔고비율 받아오기 (KIS 순위분석 또는 KRX) */
export const MARKET_STOCKS = [
  { code: '005930', name: '삼성전자',            market: 'KOSPI', sector: '반도체', brand: '#1428a0' },
  { code: '000660', name: 'SK하이닉스',          market: 'KOSPI', sector: '반도체', brand: '#e5231b' },
  { code: '373220', name: 'LG에너지솔루션',      market: 'KOSPI', sector: '2차전지', brand: '#a50034' },
  { code: '207940', name: '삼성바이오로직스',    market: 'KOSPI', sector: '바이오', brand: '#0d4a9a' },
  { code: '005380', name: '현대차',              market: 'KOSPI', sector: '자동차', brand: '#002c5f' },
  { code: '005490', name: 'POSCO홀딩스',         market: 'KOSPI', sector: '철강', brand: '#00a5e5' },
  { code: '068270', name: '셀트리온',            market: 'KOSPI', sector: '바이오', brand: '#00a0e9' },
  { code: '035420', name: 'NAVER',               market: 'KOSPI', sector: 'IT', brand: '#03c75a' },
  { code: '035720', name: '카카오',              market: 'KOSPI', sector: 'IT', brand: '#f7e600' },
  { code: '051910', name: 'LG화학',              market: 'KOSPI', sector: '화학', brand: '#a50034' },
  { code: '006400', name: '삼성SDI',             market: 'KOSPI', sector: '2차전지', brand: '#1428a0' },
  { code: '055550', name: '신한지주',            market: 'KOSPI', sector: '금융', brand: '#0046ff' },
  { code: '105560', name: 'KB금융',              market: 'KOSPI', sector: '금융', brand: '#544f4b' },
  { code: '017670', name: 'SK텔레콤',            market: 'KOSPI', sector: '통신', brand: '#ea1917' },
  { code: '012330', name: '현대모비스',          market: 'KOSPI', sector: '자동차', brand: '#002c5f' },
  { code: '028260', name: '삼성물산',            market: 'KOSPI', sector: '건설', brand: '#1428a0' },
  { code: '066570', name: 'LG전자',              market: 'KOSPI', sector: '전기전자', brand: '#a50034' },
  { code: '003550', name: 'LG',                  market: 'KOSPI', sector: '지주회사', brand: '#a50034' },
  { code: '015760', name: '한국전력',            market: 'KOSPI', sector: '전력', brand: '#ed1c24' },
  { code: '009150', name: '삼성전기',            market: 'KOSPI', sector: '전기전자', brand: '#1428a0' },
  { code: '034730', name: 'SK',                  market: 'KOSPI', sector: '지주회사', brand: '#e5231b' },
  { code: '086790', name: '하나금융지주',        market: 'KOSPI', sector: '금융', brand: '#008485' },
  { code: '096770', name: 'SK이노베이션',        market: 'KOSPI', sector: '에너지', brand: '#e60012' },
  { code: '010130', name: '고려아연',            market: 'KOSPI', sector: '비철금속', brand: '#004098' },
  { code: '032830', name: '삼성생명',            market: 'KOSPI', sector: '보험', brand: '#1428a0' },
  { code: '018260', name: '삼성에스디에스',      market: 'KOSPI', sector: 'IT', brand: '#1428a0' },
  { code: '030200', name: 'KT',                  market: 'KOSPI', sector: '통신', brand: '#252525' },
  { code: '323410', name: '카카오뱅크',          market: 'KOSPI', sector: '금융', brand: '#f7e600' },
  { code: '259960', name: '크래프톤',            market: 'KOSPI', sector: '게임', brand: '#363245' },
  { code: '267260', name: 'HD현대일렉트릭',      market: 'KOSPI', sector: '전기전자', brand: '#002f87' },
  { code: '064350', name: '현대로템',            market: 'KOSPI', sector: '기계', brand: '#002c5f' },
  { code: '377300', name: '카카오페이',          market: 'KOSPI', sector: '금융', brand: '#f7e600' },
  { code: '024110', name: '기업은행',            market: 'KOSPI', sector: '금융', brand: '#015198' },
  { code: '251270', name: '넷마블',              market: 'KOSDAQ', sector: '게임', brand: '#8b95a1' },
  { code: '036570', name: '엔씨소프트',          market: 'KOSDAQ', sector: '게임', brand: '#004385' },
  { code: '196170', name: '알테오젠',            market: 'KOSDAQ', sector: '바이오', brand: '#009ade' },
  { code: '247540', name: '에코프로비엠',        market: 'KOSDAQ', sector: '2차전지', brand: '#004097' },
  { code: '086520', name: '에코프로',            market: 'KOSDAQ', sector: '2차전지', brand: '#004097' },
  { code: '091990', name: '셀트리온헬스케어',    market: 'KOSDAQ', sector: '바이오', brand: '#8b95a1' },
  { code: '042700', name: '한미반도체',          market: 'KOSDAQ', sector: '반도체', brand: '#14429d' },
];

/* ── 차트 기간 버튼 ── */
export const CHART_PERIODS = [
  { id: '5m', label: '5분' },
  { id: '1d', label: '일'  },
  { id: '1w', label: '주'  },
  { id: '1M', label: '월'  },
  { id: '1y', label: '년'  },
];

/* 시가총액(백만원 단위 숫자)을 '498조' 처럼 읽기 쉽게 */
export function fmtMarketCapNum(num) {
  if (num == null) return '—';
  const 조 = num / 10000;
  if (조 >= 1) return 조.toFixed(조 >= 10 ? 0 : 1) + '조';
  return Math.round(num).toLocaleString('ko-KR') + '억';
}

/* ──────────────────────────────────────────────────────────────────────────
   종목 아이콘 색

   순위표가 코스피 상위 200종목을 보여주게 되면서 필요해졌습니다. 위 목록에
   실제 대표색을 적어 둔 회사는 마흔 남짓이고, 나머지 160여 개는 색이 없습니다.
   (개수를 여기 박아두면 목록이 늘 때마다 주석이 어긋납니다. 세려면 위 목록에서
    brand 가 #8b95a1 이 아닌 줄을 셉니다.)

   세 단계로 정합니다.
     1. 위 목록에 있는 회사        → 적어 둔 대표색 그대로
     2. 같은 그룹으로 읽히는 회사   → 그룹 색 (삼성전자우 → 삼성 파랑)
     3. 그 밖                     → 이름에서 만든 색

   3번은 진짜 대표색이 아닙니다. 다만 같은 종목은 언제나 같은 색이 나오고
   서로 구분되기 때문에, 회색으로 전부 같게 두는 것보다 알아보기 쉽습니다.
   실제 색을 알게 되면 위 목록에 적어 넣으면 1번이 그것을 씁니다.
   ────────────────────────────────────────────────────────────────────────── */

/* 이름이 이것으로 시작하면 그 그룹으로 본다. 긴 것부터 본다
   (SK텔레콤이 SK보다 먼저 걸려야 제 색이 나온다). */
const BRAND_GROUPS = [
  ['삼성바이오', '#0d4a9a'],
  ['삼성',       '#1428a0'],
  ['SK텔레콤',   '#ea1917'],
  ['SK이노베이션', '#e60012'],
  ['SK',         '#e5231b'],
  ['LG',         '#a50034'],
  ['현대',       '#002c5f'],
  ['POSCO',      '#00a5e5'],
  ['포스코',      '#00a5e5'],
  ['NAVER',      '#03c75a'],
  ['카카오',      '#f7e600'],
  ['셀트리온',    '#00a0e9'],
  ['신한',       '#0046ff'],
  ['하나',       '#008485'],
  ['KB',         '#544f4b'],
  ['고려아연',    '#004098'],
];

/* 위 목록(WATCHLIST · MARKET_STOCKS)에서 코드→색 표를 한 번 만들어 둔다 */
const KNOWN_BRANDS = (() => {
  const map = {};
  for (const s of [...WATCHLIST, ...MARKET_STOCKS]) {
    /* #8b95a1 은 "모른다" 는 뜻으로 넣어 둔 회색이다. 진짜 대표색이 아니므로
       아래 그룹·이름 규칙이 대신 정하게 둔다. */
    if (s.brand && s.brand.toLowerCase() !== '#8b95a1') map[s.code] = s.brand;
  }
  return map;
})();

/* 이름에서 만든 색. 같은 이름이면 언제나 같은 색이 나온다. */
function colorFromName(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  const hue = h % 360;
  /* 채도·밝기는 고정한다. 아이콘 위에 흰 글자를 얹으므로 너무 밝으면 안 읽힌다. */
  return `hsl(${hue} 42% 42%)`;
}

export function brandColor(code, name) {
  if (KNOWN_BRANDS[code]) return KNOWN_BRANDS[code];
  const n = (name || '').trim();
  for (const [prefix, color] of BRAND_GROUPS) {
    if (n.startsWith(prefix)) return color;
  }
  return colorFromName(n || code || '');
}
