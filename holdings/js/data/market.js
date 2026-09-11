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

/* ── 관심종목 ──
   시세는 /api/kis/prices 가 채운다. 메모는 브라우저에 저장된다(store/memo.js). */
export const WATCHLIST = [
  { code: '005930', name: '삼성전자',            sector: '반도체' },
  { code: '000660', name: 'SK하이닉스',          sector: '반도체' },
  { code: '035420', name: 'NAVER',               sector: 'IT' },
  { code: '035720', name: '카카오',              sector: 'IT' },
  { code: '005380', name: '현대차',              sector: '자동차' },
  { code: '373220', name: 'LG에너지솔루션',      sector: '2차전지' },
  { code: '207940', name: '삼성바이오로직스',    sector: '바이오' },
  { code: '068270', name: '셀트리온',            sector: '바이오' },
];

/* ── 시장 전체 종목 ──
   순위 탭(거래상위·상승률 등)이 쓰는 목록. 정렬 기준이 되는 값(거래량·시총·
   공매도 비율)은 아직 받아올 곳이 없어서, 해당 탭은 비어 있다고 표시한다.
   ─ 할 일: 거래량·시가총액·공매도 잔고비율 받아오기 (KIS 순위분석 또는 KRX) */
export const MARKET_STOCKS = [
  { code: '005930', name: '삼성전자',            market: 'KOSPI', sector: '반도체' },
  { code: '000660', name: 'SK하이닉스',          market: 'KOSPI', sector: '반도체' },
  { code: '373220', name: 'LG에너지솔루션',      market: 'KOSPI', sector: '2차전지' },
  { code: '207940', name: '삼성바이오로직스',    market: 'KOSPI', sector: '바이오' },
  { code: '005380', name: '현대차',              market: 'KOSPI', sector: '자동차' },
  { code: '005490', name: 'POSCO홀딩스',         market: 'KOSPI', sector: '철강' },
  { code: '068270', name: '셀트리온',            market: 'KOSPI', sector: '바이오' },
  { code: '035420', name: 'NAVER',               market: 'KOSPI', sector: 'IT' },
  { code: '035720', name: '카카오',              market: 'KOSPI', sector: 'IT' },
  { code: '051910', name: 'LG화학',              market: 'KOSPI', sector: '화학' },
  { code: '006400', name: '삼성SDI',             market: 'KOSPI', sector: '2차전지' },
  { code: '055550', name: '신한지주',            market: 'KOSPI', sector: '금융' },
  { code: '105560', name: 'KB금융',              market: 'KOSPI', sector: '금융' },
  { code: '017670', name: 'SK텔레콤',            market: 'KOSPI', sector: '통신' },
  { code: '012330', name: '현대모비스',          market: 'KOSPI', sector: '자동차' },
  { code: '028260', name: '삼성물산',            market: 'KOSPI', sector: '건설' },
  { code: '066570', name: 'LG전자',              market: 'KOSPI', sector: '전기전자' },
  { code: '003550', name: 'LG',                  market: 'KOSPI', sector: '지주회사' },
  { code: '015760', name: '한국전력',            market: 'KOSPI', sector: '전력' },
  { code: '009150', name: '삼성전기',            market: 'KOSPI', sector: '전기전자' },
  { code: '034730', name: 'SK',                  market: 'KOSPI', sector: '지주회사' },
  { code: '086790', name: '하나금융지주',        market: 'KOSPI', sector: '금융' },
  { code: '096770', name: 'SK이노베이션',        market: 'KOSPI', sector: '에너지' },
  { code: '010130', name: '고려아연',            market: 'KOSPI', sector: '비철금속' },
  { code: '032830', name: '삼성생명',            market: 'KOSPI', sector: '보험' },
  { code: '018260', name: '삼성에스디에스',      market: 'KOSPI', sector: 'IT' },
  { code: '030200', name: 'KT',                  market: 'KOSPI', sector: '통신' },
  { code: '323410', name: '카카오뱅크',          market: 'KOSPI', sector: '금융' },
  { code: '259960', name: '크래프톤',            market: 'KOSPI', sector: '게임' },
  { code: '267260', name: 'HD현대일렉트릭',      market: 'KOSPI', sector: '전기전자' },
  { code: '064350', name: '현대로템',            market: 'KOSPI', sector: '기계' },
  { code: '377300', name: '카카오페이',          market: 'KOSPI', sector: '금융' },
  { code: '024110', name: '기업은행',            market: 'KOSPI', sector: '금융' },
  { code: '251270', name: '넷마블',              market: 'KOSDAQ', sector: '게임' },
  { code: '036570', name: '엔씨소프트',          market: 'KOSDAQ', sector: '게임' },
  { code: '196170', name: '알테오젠',            market: 'KOSDAQ', sector: '바이오' },
  { code: '247540', name: '에코프로비엠',        market: 'KOSDAQ', sector: '2차전지' },
  { code: '086520', name: '에코프로',            market: 'KOSDAQ', sector: '2차전지' },
  { code: '091990', name: '셀트리온헬스케어',    market: 'KOSDAQ', sector: '바이오' },
  { code: '042700', name: '한미반도체',          market: 'KOSDAQ', sector: '반도체' },
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
