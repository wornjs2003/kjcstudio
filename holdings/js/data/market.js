/* ==========================================================================
   종목·지수 목록

   여기에는 '무엇이 있는지'만 둡니다. 가격·등락·거래량·재무처럼 시시각각
   바뀌는 값은 두지 않습니다. 예시 숫자를 넣어 두면 화면에 실제 시세처럼
   보여서, 연결이 안 된 건지 시세가 그런 건지 구분할 수 없기 때문입니다.

   값은 전부 서버(/api/kis/*)에서 받아 채웁니다. 못 받으면 화면에
   "불러오는 중" 또는 "—" 이 남습니다. 그게 아직 연결되지 않았다는 표시입니다.
   ========================================================================== */

/* ── 지수 ──
   값·등락·추이는 /api/kis/indices 가 채운다. */
export const INDEX_LIST = [
  { code: 'KOSPI',    name: 'KOSPI',    unit: 'pt' },
  { code: 'KOSDAQ',   name: 'KOSDAQ',   unit: 'pt' },
  { code: 'KOSPI200', name: 'KOSPI200', unit: 'pt' },
];

/* 서버가 아직 주지 않는 지수. 목록에서 빼 두고, 받아올 곳이 생기면 위로 옮긴다.
   ─ 할 일: 해외 지수·환율 (KRX100 · S&P 500 · NASDAQ · 다우 · 닛케이 · 상해 · 원/달러) */
export const INDEX_NOT_CONNECTED = [
  'KRX100', 'S&P 500', 'NASDAQ', '다우존스', '닛케이225', '상해종합', '원/달러',
];

/* 아이콘에 쓰는 회사 색(brand)은 각 기업이 쓰는 대표색입니다.
   로고 이미지는 저작권 문제가 있어 쓰지 않고, 색 위에 이름 두 글자를 얹습니다. */

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

/* ── 자주 보는 종목 ──
   이 둘만 5초마다 갱신하고, 나머지 관심종목과 지수는 30초마다 갱신한다.
   나머지의 주기를 늘려서 확보한 몫을 여기로 옮긴 것이라 총 호출량은 늘지 않는다
   (2026-09-14 지시). 서버 쪽 캐시 TTL 도 이 목록에 맞춰져 있다 —
   server/kis_proxy.py 의 FAST_CODES 와 같아야 한다. */
export const PRIORITY_CODES = ['005930', '000660'];

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
  { code: '003550', name: 'LG',                  market: 'KOSPI', sector: '지주회사', brand: '#8b95a1' },
  { code: '015760', name: '한국전력',            market: 'KOSPI', sector: '전력', brand: '#8b95a1' },
  { code: '009150', name: '삼성전기',            market: 'KOSPI', sector: '전기전자', brand: '#1428a0' },
  { code: '034730', name: 'SK',                  market: 'KOSPI', sector: '지주회사', brand: '#8b95a1' },
  { code: '086790', name: '하나금융지주',        market: 'KOSPI', sector: '금융', brand: '#008485' },
  { code: '096770', name: 'SK이노베이션',        market: 'KOSPI', sector: '에너지', brand: '#e60012' },
  { code: '010130', name: '고려아연',            market: 'KOSPI', sector: '비철금속', brand: '#004098' },
  { code: '032830', name: '삼성생명',            market: 'KOSPI', sector: '보험', brand: '#8b95a1' },
  { code: '018260', name: '삼성에스디에스',      market: 'KOSPI', sector: 'IT', brand: '#8b95a1' },
  { code: '030200', name: 'KT',                  market: 'KOSPI', sector: '통신', brand: '#8b95a1' },
  { code: '323410', name: '카카오뱅크',          market: 'KOSPI', sector: '금융', brand: '#8b95a1' },
  { code: '259960', name: '크래프톤',            market: 'KOSPI', sector: '게임', brand: '#8b95a1' },
  { code: '267260', name: 'HD현대일렉트릭',      market: 'KOSPI', sector: '전기전자', brand: '#8b95a1' },
  { code: '064350', name: '현대로템',            market: 'KOSPI', sector: '기계', brand: '#8b95a1' },
  { code: '377300', name: '카카오페이',          market: 'KOSPI', sector: '금융', brand: '#8b95a1' },
  { code: '024110', name: '기업은행',            market: 'KOSPI', sector: '금융', brand: '#8b95a1' },
  { code: '251270', name: '넷마블',              market: 'KOSDAQ', sector: '게임', brand: '#8b95a1' },
  { code: '036570', name: '엔씨소프트',          market: 'KOSDAQ', sector: '게임', brand: '#8b95a1' },
  { code: '196170', name: '알테오젠',            market: 'KOSDAQ', sector: '바이오', brand: '#8b95a1' },
  { code: '247540', name: '에코프로비엠',        market: 'KOSDAQ', sector: '2차전지', brand: '#8b95a1' },
  { code: '086520', name: '에코프로',            market: 'KOSDAQ', sector: '2차전지', brand: '#8b95a1' },
  { code: '091990', name: '셀트리온헬스케어',    market: 'KOSDAQ', sector: '바이오', brand: '#8b95a1' },
  { code: '042700', name: '한미반도체',          market: 'KOSDAQ', sector: '반도체', brand: '#8b95a1' },
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
   실제 대표색을 적어 둔 회사는 40개뿐이고, 나머지 160여 개는 색이 없습니다.

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
