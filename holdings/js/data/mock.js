/* ==========================================================================
   Mock 데이터
   실제 데이터 소스(네이버 금융·DART)가 붙기 전까지 사용
   ========================================================================== */

/* 결정적 시계열 생성 (코드 기반 시드) — 새로고침해도 값 동일 */
function _indexSeries(seed, base, volatility, drift, N = 60) {
  let s = seed;
  const rnd = () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
  const arr = [];
  let v = base;
  for (let i = 0; i < N; i++) {
    const step = (rnd() - 0.5) * volatility + drift;
    v = Math.max(1, v * (1 + step / 100));
    arr.push(v);
  }
  return arr;
}

function _buildIndex({ code, name, seed, base, volatility, drift, unit }) {
  const series = _indexSeries(seed, base, volatility, drift);
  const value = series[series.length - 1];
  const prev = series[series.length - 2];
  const change = value - prev;
  const changePct = (change / prev) * 100;
  return { code, name, value, change, changePct, series, unit };
}

export const MOCK_INDICES = [
  _buildIndex({ code: 'KOSPI',    name: 'KOSPI',    seed: 7301, base: 2620,  volatility: 1.2, drift: 0.02,  unit: 'pt' }),
  _buildIndex({ code: 'KOSDAQ',   name: 'KOSDAQ',   seed: 4412, base: 890,   volatility: 1.8, drift: -0.03, unit: 'pt' }),
  _buildIndex({ code: 'KOSPI200', name: 'KOSPI200', seed: 5127, base: 355,   volatility: 1.1, drift: 0.02,  unit: 'pt' }),
  _buildIndex({ code: 'KRX100',   name: 'KRX100',   seed: 3903, base: 5840,  volatility: 1.2, drift: 0.01,  unit: 'pt' }),
  _buildIndex({ code: 'SP500',    name: 'S&P 500',  seed: 9118, base: 4480,  volatility: 0.9, drift: 0.05,  unit: 'pt' }),
  _buildIndex({ code: 'NASDAQ',   name: 'NASDAQ',   seed: 6024, base: 14100, volatility: 1.3, drift: 0.07,  unit: 'pt' }),
  _buildIndex({ code: 'DOW',      name: '다우존스',   seed: 2815, base: 35200, volatility: 0.7, drift: 0.03,  unit: 'pt' }),
  _buildIndex({ code: 'NIKKEI',   name: '닛케이225',  seed: 1577, base: 32500, volatility: 1.0, drift: 0.02,  unit: 'pt' }),
  _buildIndex({ code: 'SHANGHAI', name: '상해종합',   seed: 8329, base: 3050,  volatility: 0.9, drift: -0.01, unit: 'pt' }),
  _buildIndex({ code: 'USDKRW',   name: '원/달러',    seed: 4861, base: 1340,  volatility: 0.4, drift: -0.005, unit: '원' }),
];

export const MOCK_STOCKS = [
  {
    code: '005930', name: '삼성전자', sector: '반도체',
    price: 83400, change: +1000, changePct: +1.21,
    prevClose: 82400, open: 82500, high: 83800, low: 82300,
    volume: 24_100_000, marketCap: '498조',
    memo: 'HBM 기대로 장기 보유 중',
    metrics: { per: 12.3, pbr: 1.4, eps: 6780, bps: 59570, dividend: 2.1, dividendYield: 2.1 }
  },
  {
    code: '000660', name: 'SK하이닉스', sector: '반도체',
    price: 195500, change: -600, changePct: -0.31,
    prevClose: 196100, open: 196000, high: 197200, low: 194500,
    volume: 8_300_000, marketCap: '142조',
    memo: 'HBM3E 양산 주목',
    metrics: { per: 9.8, pbr: 1.8, eps: 19940, bps: 108610, dividend: 1200, dividendYield: 0.6 }
  },
  {
    code: '035420', name: 'NAVER', sector: 'IT',
    price: 210000, change: +1050, changePct: +0.50,
    prevClose: 208950, open: 209000, high: 211500, low: 208500,
    volume: 2_100_000, marketCap: '32조',
    memo: '커머스·AI 회복 확인 중',
    metrics: { per: 18.5, pbr: 1.1, eps: 11350, bps: 190900, dividend: 914, dividendYield: 0.4 }
  },
  {
    code: '035720', name: '카카오', sector: 'IT',
    price: 55700, change: -620, changePct: -1.10,
    prevClose: 56320, open: 56300, high: 56400, low: 55500,
    volume: 15_200_000, marketCap: '24조',
    memo: '리스크 확인 전 보류',
    metrics: { per: 33.1, pbr: 1.0, eps: 1680, bps: 55700, dividend: 0, dividendYield: 0 }
  },
  {
    code: '005380', name: '현대차', sector: '자동차',
    price: 238500, change: +4900, changePct: +2.10,
    prevClose: 233600, open: 234000, high: 239500, low: 233500,
    volume: 3_400_000, marketCap: '50조',
    memo: '미국 현지 생산 이슈 주시',
    metrics: { per: 6.1, pbr: 0.65, eps: 39100, bps: 367000, dividend: 11000, dividendYield: 4.6 }
  },
  {
    code: '373220', name: 'LG에너지솔루션', sector: '2차전지',
    price: 362000, change: +1500, changePct: +0.42,
    prevClose: 360500, open: 360500, high: 364000, low: 359000,
    volume: 1_800_000, marketCap: '84조',
    memo: '전기차 수요 회복 대기',
    metrics: { per: 74.8, pbr: 4.2, eps: 4840, bps: 86190, dividend: 0, dividendYield: 0 }
  },
  {
    code: '207940', name: '삼성바이오로직스', sector: '바이오',
    price: 802000, change: -7000, changePct: -0.86,
    prevClose: 809000, open: 808000, high: 810000, low: 800000,
    volume: 180_000, marketCap: '57조',
    memo: '4공장 가동률 체크',
    metrics: { per: 54.2, pbr: 6.1, eps: 14800, bps: 131500, dividend: 0, dividendYield: 0 }
  },
  {
    code: '068270', name: '셀트리온', sector: '바이오',
    price: 178000, change: -500, changePct: -0.28,
    prevClose: 178500, open: 178300, high: 179200, low: 177000,
    volume: 920_000, marketCap: '38조',
    memo: '짐펜트라 실적 기다림',
    metrics: { per: 28.4, pbr: 2.1, eps: 6270, bps: 84760, dividend: 750, dividendYield: 0.4 }
  },
];

/* ==========================================================================
   시장 전체 종목 풀 — 거래상위·상승상위·하락상위·시가총액·공매상위 랭킹용
   실제로는 네이버 금융 랭킹 API(sise_upjong.nhn / rank.nhn)로 대체 예정
   ========================================================================== */
export const MOCK_MARKET_STOCKS = [
  { code: '005930', name: '삼성전자',         market: 'KOSPI',  sector: '반도체',  price:  83400, change:  +1000, changePct:  +1.21, volume: 24_100_000, marketCapNum: 498_0000, shortRatio: 3.2 },
  { code: '000660', name: 'SK하이닉스',        market: 'KOSPI',  sector: '반도체',  price: 195500, change:   -600, changePct:  -0.31, volume:  8_300_000, marketCapNum: 142_0000, shortRatio: 4.8 },
  { code: '373220', name: 'LG에너지솔루션',    market: 'KOSPI',  sector: '2차전지', price: 362000, change:  +1500, changePct:  +0.42, volume:  1_800_000, marketCapNum:  84_0000, shortRatio: 5.1 },
  { code: '207940', name: '삼성바이오로직스',  market: 'KOSPI',  sector: '바이오',  price: 802000, change:  -7000, changePct:  -0.86, volume:    180_000, marketCapNum:  57_0000, shortRatio: 2.5 },
  { code: '005380', name: '현대차',            market: 'KOSPI',  sector: '자동차',  price: 238500, change:  +4900, changePct:  +2.10, volume:  3_400_000, marketCapNum:  50_0000, shortRatio: 2.7 },
  { code: '005490', name: 'POSCO홀딩스',       market: 'KOSPI',  sector: '철강',    price: 418000, change:  -5500, changePct:  -1.30, volume:    620_000, marketCapNum:  35_0000, shortRatio: 3.8 },
  { code: '068270', name: '셀트리온',          market: 'KOSPI',  sector: '바이오',  price: 178000, change:   -500, changePct:  -0.28, volume:    920_000, marketCapNum:  38_0000, shortRatio: 6.2 },
  { code: '035420', name: 'NAVER',             market: 'KOSPI',  sector: 'IT',      price: 210000, change:  +1050, changePct:  +0.50, volume:  2_100_000, marketCapNum:  32_0000, shortRatio: 2.1 },
  { code: '035720', name: '카카오',            market: 'KOSPI',  sector: 'IT',      price:  55700, change:   -620, changePct:  -1.10, volume: 15_200_000, marketCapNum:  24_0000, shortRatio: 4.3 },
  { code: '051910', name: 'LG화학',            market: 'KOSPI',  sector: '화학',    price: 452000, change:  +7000, changePct:  +1.57, volume:    520_000, marketCapNum:  31_0000, shortRatio: 5.5 },
  { code: '006400', name: '삼성SDI',           market: 'KOSPI',  sector: '2차전지', price: 408500, change: -12000, changePct:  -2.85, volume:    640_000, marketCapNum:  28_0000, shortRatio: 7.1 },
  { code: '055550', name: '신한지주',          market: 'KOSPI',  sector: '금융',    price:  48950, change:   +250, changePct:  +0.51, volume:  1_900_000, marketCapNum:  25_0000, shortRatio: 1.2 },
  { code: '105560', name: 'KB금융',            market: 'KOSPI',  sector: '금융',    price:  77600, change:   +600, changePct:  +0.78, volume:  1_100_000, marketCapNum:  31_0000, shortRatio: 1.1 },
  { code: '017670', name: 'SK텔레콤',          market: 'KOSPI',  sector: '통신',    price:  53700, change:   -300, changePct:  -0.56, volume:    710_000, marketCapNum:  11_5000, shortRatio: 1.8 },
  { code: '012330', name: '현대모비스',        market: 'KOSPI',  sector: '자동차',  price: 237500, change:  +4500, changePct:  +1.93, volume:    410_000, marketCapNum:  22_0000, shortRatio: 2.9 },
  { code: '028260', name: '삼성물산',          market: 'KOSPI',  sector: '건설',    price: 148300, change:   -800, changePct:  -0.54, volume:    560_000, marketCapNum:  27_6000, shortRatio: 3.4 },
  { code: '066570', name: 'LG전자',            market: 'KOSPI',  sector: '전기전자',price:  97500, change:  +2200, changePct:  +2.31, volume:  2_300_000, marketCapNum:  15_9000, shortRatio: 3.0 },
  { code: '003550', name: 'LG',                market: 'KOSPI',  sector: '지주회사',price:  80200, change:   -100, changePct:  -0.12, volume:    320_000, marketCapNum:  12_6000, shortRatio: 1.5 },
  { code: '015760', name: '한국전력',          market: 'KOSPI',  sector: '전력',    price:  22050, change:   +550, changePct:  +2.56, volume:  3_800_000, marketCapNum:  14_2000, shortRatio: 2.3 },
  { code: '009150', name: '삼성전기',          market: 'KOSPI',  sector: '전기전자',price: 152000, change:  -1500, changePct:  -0.98, volume:    480_000, marketCapNum:  11_3000, shortRatio: 5.8 },
  { code: '034730', name: 'SK',                market: 'KOSPI',  sector: '지주회사',price: 155000, change:  -4000, changePct:  -2.52, volume:    280_000, marketCapNum:  11_4000, shortRatio: 4.5 },
  { code: '086790', name: '하나금융지주',      market: 'KOSPI',  sector: '금융',    price:  62400, change:   +200, changePct:  +0.32, volume:    890_000, marketCapNum:  18_2000, shortRatio: 1.0 },
  { code: '096770', name: 'SK이노베이션',      market: 'KOSPI',  sector: '에너지',  price: 125800, change:  +2800, changePct:  +2.28, volume:    720_000, marketCapNum:  11_8000, shortRatio: 6.9 },
  { code: '010130', name: '고려아연',          market: 'KOSPI',  sector: '비철금속',price: 532000, change: +21000, changePct:  +4.11, volume:    120_000, marketCapNum:  11_0000, shortRatio: 3.3 },
  { code: '032830', name: '삼성생명',          market: 'KOSPI',  sector: '보험',    price:  92500, change:   -700, changePct:  -0.75, volume:    540_000, marketCapNum:  18_5000, shortRatio: 2.4 },
  { code: '018260', name: '삼성에스디에스',    market: 'KOSPI',  sector: 'IT',      price: 168900, change:  -1100, changePct:  -0.65, volume:    180_000, marketCapNum:  13_0000, shortRatio: 2.0 },
  { code: '030200', name: 'KT',                market: 'KOSPI',  sector: '통신',    price:  40150, change:   +350, changePct:  +0.88, volume:    820_000, marketCapNum:  10_4000, shortRatio: 1.3 },
  { code: '323410', name: '카카오뱅크',        market: 'KOSPI',  sector: '금융',    price:  24200, change:  -1100, changePct:  -4.35, volume:  6_200_000, marketCapNum:  11_5000, shortRatio: 8.4 },
  { code: '259960', name: '크래프톤',          market: 'KOSPI',  sector: '게임',    price: 278500, change:  +8500, changePct:  +3.15, volume:    410_000, marketCapNum:  13_7000, shortRatio: 7.5 },
  { code: '267260', name: 'HD현대일렉트릭',    market: 'KOSPI',  sector: '전기전자',price: 285500, change: +12000, changePct:  +4.39, volume:    580_000, marketCapNum:  10_3000, shortRatio: 4.6 },
  { code: '064350', name: '현대로템',          market: 'KOSPI',  sector: '기계',    price:  45200, change:  +2150, changePct:  +4.99, volume:  1_780_000, marketCapNum:   3_9000, shortRatio: 5.3 },
  { code: '377300', name: '카카오페이',        market: 'KOSPI',  sector: '금융',    price:  32100, change:  -1550, changePct:  -4.61, volume:  3_820_000, marketCapNum:   4_2000, shortRatio: 8.8 },
  { code: '024110', name: '기업은행',          market: 'KOSPI',  sector: '금융',    price:  13620, change:   +180, changePct:  +1.34, volume:  4_100_000, marketCapNum:  10_9000, shortRatio: 1.5 },
  { code: '251270', name: '넷마블',            market: 'KOSDAQ', sector: '게임',    price:  51700, change:  -2300, changePct:  -4.26, volume:    960_000, marketCapNum:   4_4000, shortRatio: 9.2 },
  { code: '036570', name: '엔씨소프트',        market: 'KOSDAQ', sector: '게임',    price: 168500, change:  -4200, changePct:  -2.43, volume:    230_000, marketCapNum:   3_7000, shortRatio: 8.9 },
  { code: '196170', name: '알테오젠',          market: 'KOSDAQ', sector: '바이오',  price: 342000, change: +18500, changePct:  +5.72, volume:    870_000, marketCapNum:  18_3000, shortRatio:10.3 },
  { code: '247540', name: '에코프로비엠',      market: 'KOSDAQ', sector: '2차전지', price: 192000, change:  -8200, changePct:  -4.10, volume:  1_650_000, marketCapNum:  18_8000, shortRatio: 9.8 },
  { code: '086520', name: '에코프로',          market: 'KOSDAQ', sector: '2차전지', price: 115800, change:  -5400, changePct:  -4.45, volume:  2_150_000, marketCapNum:  12_3000, shortRatio:11.5 },
  { code: '091990', name: '셀트리온헬스케어',  market: 'KOSDAQ', sector: '바이오',  price:  82500, change:  +1900, changePct:  +2.36, volume:  1_440_000, marketCapNum:  13_0000, shortRatio: 6.8 },
  { code: '042700', name: '한미반도체',        market: 'KOSDAQ', sector: '반도체',  price: 148500, change:  +6500, changePct:  +4.58, volume:  2_850_000, marketCapNum:  14_4000, shortRatio: 7.2 },
];

/* 시가총액 숫자(억원) → "000조 000억" 라벨 */
export function fmtMarketCapNum(num) {
  const jo = Math.floor(num / 10000);
  const eok = num % 10000;
  if (jo > 0 && eok > 0) return `${jo.toLocaleString('ko-KR')}조 ${eok.toLocaleString('ko-KR')}억`;
  if (jo > 0) return `${jo.toLocaleString('ko-KR')}조`;
  return `${eok.toLocaleString('ko-KR')}억`;
}

/* ==========================================================================
   세계 주요 이슈 — 주제별 헤드라인
   주제: 전쟁, AI, 방산, 북극항로, 조선
   ========================================================================== */
export const MOCK_GLOBAL_ISSUES = [
  { topic: '전쟁', title: '러-우 교전 격화, 흑해 곡물 수출 차질' },
  { topic: '전쟁', title: '이란-이스라엘 긴장 고조, 호르무즈 해협 위험 경고' },
  { topic: '전쟁', title: '중국-대만 해협 군사훈련 재개, 반도체 공급망 리스크' },
  { topic: 'AI',  title: 'AI 에이전트 시대 본격화, 기업 생산성 30% 향상' },
  { topic: 'AI',  title: '엔비디아 차세대 GPU 발표, 데이터센터 투자 급증' },
  { topic: 'AI',  title: '글로벌 빅테크 AI 설비투자 올해 3000억 달러 돌파 전망' },
  { topic: '방산', title: '유럽 방산 지출 사상 최대, NATO 회원국 목표치 상향' },
  { topic: '방산', title: '한국 방산 수출 100억 달러 돌파, 중동·동유럽 수주 호조' },
  { topic: '방산', title: '우주 기반 감시체계 경쟁 가속, 민간 위성 수요 급증' },
  { topic: '북극항로', title: '북극 해빙 가속, 북극항로 연중 운항 가능성 부각' },
  { topic: '북극항로', title: '러시아 북극항로 화물량 전년 대비 40% 증가' },
  { topic: '북극항로', title: '북극권 자원 개발 본격화, 희토류·가스전 신규 탐사' },
  { topic: '조선', title: 'LNG 운반선 발주 폭증, 한국 조선 3사 수주잔고 역대 최대' },
  { topic: '조선', title: '친환경 선박 전환 의무화 임박, 선박 교체 수요 확대' },
  { topic: '조선', title: '초대형 컨테이너선 경쟁, 글로벌 물동량 회복세' },
];

export const MOCK_FEED = [
  { time: '10:32', type: 'dart',   ticker: '005930', name: '삼성전자',   title: '현금·현물배당 결정 (전기 대비 +50원)' },
  { time: '10:28', type: 'news',   ticker: '000660', name: 'SK하이닉스', title: '엔비디아 차기 AI 칩용 HBM4 공급 협상 진전' },
  { time: '10:15', type: 'news',   ticker: '000660', name: 'SK하이닉스', title: '美 패키징 투자 확대 검토 — 외신 보도' },
  { time: '09:58', type: 'dart',   ticker: '035420', name: 'NAVER',      title: '자기주식 취득 신탁계약 체결' },
  { time: '09:44', type: 'news',   ticker: '005380', name: '현대차',     title: '美 앨라배마 공장 생산량 10% 확대 계획' },
  { time: '09:30', type: 'notice', ticker: '373220', name: 'LG에너지솔루션', title: '시간외 단일가 거래 이상 — 감시 조치' },
  { time: '09:12', type: 'news',   ticker: '035720', name: '카카오',     title: '일본 자회사 실적 개선 — 1분기 전년比 흑전' },
  { time: '08:55', type: 'dart',   ticker: '207940', name: '삼성바이오로직스', title: '분기보고서 제출 (2026.1Q)' },
];

/* ==========================================================================
   거래 데이터 — 투자자별 매매동향, 공매도, 선물
   금액 단위: 백만원, 수량 단위: 주
   실제로는 네이버 금융(investor.asp / shortStock.nhn / futures) API 연동 예정
   ========================================================================== */

const _tradingCache = new Map();

export function generateMockTrading(stock) {
  if (_tradingCache.has(stock.code)) return _tradingCache.get(stock.code);
  const result = _buildTrading(stock);
  _tradingCache.set(stock.code, result);
  return result;
}

function _buildTrading(stock) {
  const price = stock.price;
  const volume = stock.volume;
  const dailyValueWon = price * volume;
  const totalMil = Math.round(dailyValueWon / 1_000_000); // 총 거래대금 (백만원)

  // 주체별 분배 (합계 ≈ 1)
  const dist = {
    individual:   0.45,
    foreign:      0.30,
    foreignOther: 0.02,
    institution:  0.21,
    corporation:  0.02,
  };

  // 특정 주체의 매수·매도·순매수 생성
  //   bias: -1~+1 방향 편향 (양수 → 순매수 성향)
  function pair(weightMil, bias = 0) {
    const total = Math.round(totalMil * weightMil);
    const netPct = (Math.random() - 0.5 + bias * 0.2) * 0.25;
    const net = Math.round(total * netPct);
    const buy = Math.round(total / 2 + net / 2);
    const sell = Math.round(total / 2 - net / 2);
    return { buy: Math.abs(buy), sell: Math.abs(sell), net };
  }

  // 기관 세부 (기관 합계를 이 비율로 쪼갬)
  const instSubDist = {
    financial:      0.25, // 금융투자
    insurance:      0.13, // 보험
    trust:          0.20, // 투신(투자신탁)
    privateFund:    0.15, // 사모
    bank:           0.04, // 은행
    otherFinancial: 0.03, // 기타금융
    pension:        0.18, // 연기금 등
    state:          0.02, // 국가·지자체
  };

  const institutionBreakdown = {};
  for (const [key, w] of Object.entries(instSubDist)) {
    institutionBreakdown[key] = pair(dist.institution * w, (Math.random() - 0.5) * 2);
  }

  // 기관계 합산 (세부의 합)
  const instTotal = Object.values(institutionBreakdown).reduce(
    (acc, v) => ({ buy: acc.buy + v.buy, sell: acc.sell + v.sell, net: acc.net + v.net }),
    { buy: 0, sell: 0, net: 0 }
  );

  // 공매도
  const shortRatio = +(3 + Math.random() * 8).toFixed(2); // 3~11%
  const balRatio = +(0.5 + Math.random() * 3).toFixed(2);
  const shortVolume = Math.round(volume * (shortRatio / 100));
  const shortAmountMil = Math.round((shortVolume * price) / 1_000_000);

  // 선물 (개별주식선물 대상 종목만 — 시총 큰 종목은 대체로 해당)
  const hasFutures = volume > 500_000;
  const futures = hasFutures
    ? {
        available: true,
        code: stock.code + 'F',
        expiry: '2026-06',
        openInterest: Math.round(volume * (0.08 + Math.random() * 0.06)),
        openInterestChange: Math.round((Math.random() - 0.5) * volume * 0.02),
        investors: {
          individual:  { net: Math.round((Math.random() - 0.5) * totalMil * 0.05) },
          foreign:     { net: Math.round((Math.random() - 0.5) * totalMil * 0.06) },
          institution: { net: Math.round((Math.random() - 0.5) * totalMil * 0.05) },
        },
      }
    : { available: false };

  return {
    date: new Date().toISOString().slice(0, 10),
    totalMil,
    investors: {
      individual:       pair(dist.individual, (Math.random() - 0.5) * 2),
      foreign:          pair(dist.foreign,    (Math.random() - 0.5) * 2),
      foreignOther:     pair(dist.foreignOther, 0),
      institutionTotal: instTotal,
      institutionBreakdown,
      corporation:      pair(dist.corporation, 0),
    },
    shortSell: {
      shortVolume,
      shortAmountMil,
      shortRatio,
      balanceVolume: Math.round(volume * (0.5 + Math.random() * 2)),
      balanceAmountMil: Math.round(volume * (0.5 + Math.random() * 2) * price / 1_000_000),
      balanceRatio: balRatio,
    },
    futures,
  };
}

/* ==========================================================================
   시계열 차트 데이터
   기간별 (5분봉·1일·1주일·1개월·1년) time/price/volume 포인트 생성
   실제로는 네이버 금융 시세 API 연동 예정
   ========================================================================== */
const _chartCache = new Map();

export const CHART_PERIODS = [
  { id: '5m', label: '5분봉' },
  { id: '1d', label: '1일'   },
  { id: '1w', label: '1주일' },
  { id: '1M', label: '1개월' },
  { id: '1y', label: '1년'   },
];

export function generateMockTimeSeries(stock, periodId) {
  const key = stock.code + '|' + periodId;
  if (_chartCache.has(key)) return _chartCache.get(key);
  const result = _buildTimeSeries(stock, periodId);
  _chartCache.set(key, result);
  return result;
}

function _buildTimeSeries(stock, periodId) {
  const basePrice = stock.price;
  const baseVol   = stock.volume;

  // 기간별 파라미터: count(포인트 수), stepMs(간격 ms), volatility(변동성)
  const params = {
    '5m': { count: 78, stepMs: 5 * 60 * 1000,          volatility: 0.002 }, // 오늘 5분봉 (약 6시간반)
    '1d': { count: 30, stepMs: 24 * 60 * 60 * 1000,    volatility: 0.012 }, // 최근 30일 일봉
    '1w': { count: 26, stepMs: 7 * 24 * 60 * 60 * 1000, volatility: 0.022 }, // 최근 6개월 주봉
    '1M': { count: 24, stepMs: 30 * 24 * 60 * 60 * 1000, volatility: 0.035 }, // 최근 2년 월봉
    '1y': { count: 10, stepMs: 365 * 24 * 60 * 60 * 1000, volatility: 0.120 }, // 최근 10년 연봉
  };
  const p = params[periodId] || params['1d'];

  const points = [];
  // 현재가에서 시작해서 과거로 거슬러 올라가며 랜덤워크
  // 마지막 포인트가 현재가에 가까워야 함 → 앞에서 뒤로 가되 drift를 현재가 쪽으로 수렴
  let price = basePrice * (1 - p.volatility * p.count * 0.3);
  const now = Date.now();

  for (let i = 0; i < p.count; i++) {
    const remain = p.count - i;
    const target = basePrice;
    // 랜덤 드리프트 + 타겟(현재가)로의 약한 인력
    const rand = (Math.random() - 0.5) * price * p.volatility * 2;
    const pull = (target - price) / remain * 0.6;
    price = Math.max(basePrice * 0.3, price + rand + pull);
    const vol = Math.floor(baseVol * (0.6 + Math.random() * 0.8) / (periodId === '5m' ? 78 : 1));
    const t = now - (p.count - 1 - i) * p.stepMs;
    points.push({
      time: new Date(t),
      price: Math.round(price),
      volume: vol,
    });
  }
  // 마지막 포인트를 현재가로 보정
  points[points.length - 1].price = basePrice;

  return { periodId, points };
}

/* ==========================================================================
   보조 지표 — 보유비중 / 심리도 / 스토캐스틱 / MACD
   90일 일봉 기반으로 계산 (mock)
   ========================================================================== */
const _indicatorsCache = new Map();

export function generateMockIndicators(stock) {
  if (_indicatorsCache.has(stock.code)) return _indicatorsCache.get(stock.code);
  const result = _buildIndicators(stock);
  _indicatorsCache.set(stock.code, result);
  return result;
}

function _buildIndicators(stock) {
  const N = 90;
  const basePrice = stock.price;
  const now = Date.now();

  // 1. 90일 종가 시계열 (OHLC 있어야 Stochastic 계산되므로 high/low도 생성)
  const bars = [];
  let p = basePrice * 0.82;
  for (let i = 0; i < N; i++) {
    const remain = N - i;
    const rand = (Math.random() - 0.5) * p * 0.02;
    const pull = (basePrice - p) / remain * 0.7;
    p = Math.max(basePrice * 0.3, p + rand + pull);
    const high = p * (1 + Math.random() * 0.012);
    const low  = p * (1 - Math.random() * 0.012);
    bars.push({
      date: new Date(now - (N - 1 - i) * 86400000),
      close: p, high, low,
    });
  }
  bars[N - 1].close = basePrice;

  const closes = bars.map(b => b.close);
  const highs  = bars.map(b => b.high);
  const lows   = bars.map(b => b.low);
  const dates  = bars.map(b => b.date);

  // 2. 보유비중 (랜덤 워크, 외국인 30~55%, 기관 5~25%)
  const ownership = _buildOwnership(stock, dates);

  // 3. 심리도 (Psychology Line) — 최근 12일 중 상승일 비율 × 100
  const psychoPeriod = 12;
  const psychology = dates.map((d, i) => {
    if (i < psychoPeriod) return null;
    let up = 0;
    for (let j = i - psychoPeriod + 1; j <= i; j++) {
      if (closes[j] > closes[j - 1]) up++;
    }
    return (up / psychoPeriod) * 100;
  });

  // 4. 스토캐스틱 — %K(14,3) 와 %D(3)
  const kPeriod = 14;
  const kSmooth = 3;
  const dPeriod = 3;
  const rawK = closes.map((c, i) => {
    if (i < kPeriod - 1) return null;
    let hh = -Infinity, ll = Infinity;
    for (let j = i - kPeriod + 1; j <= i; j++) {
      if (highs[j] > hh) hh = highs[j];
      if (lows[j]  < ll) ll = lows[j];
    }
    const denom = Math.max(1e-9, hh - ll);
    return ((c - ll) / denom) * 100;
  });
  const fastK = _sma(rawK, kSmooth);
  const slowD = _sma(fastK, dPeriod);

  // 5. MACD — EMA12 - EMA26, Signal = EMA9(MACD), Histogram = MACD - Signal
  const ema12 = _ema(closes, 12);
  const ema26 = _ema(closes, 26);
  const macd  = closes.map((_, i) => {
    if (ema12[i] == null || ema26[i] == null) return null;
    return ema12[i] - ema26[i];
  });
  const signal = _ema(macd, 9);
  const histogram = macd.map((v, i) => (v == null || signal[i] == null) ? null : v - signal[i]);

  return {
    dates,
    ownership,
    psychology,
    stochastic: { k: fastK, d: slowD },
    macd:       { macd, signal, histogram },
  };
}

function _buildOwnership(stock, dates) {
  // 종목별 시작 비중 — 시총 큰 종목은 외국인 지분 높게
  const bigCaps = new Set(['005930', '000660', '035420']);
  const base = bigCaps.has(stock.code) ? 50 : 35;
  let foreign = base + (Math.random() - 0.5) * 4;
  let inst    = 12 + (Math.random() - 0.5) * 4;

  const foreignArr = [];
  const combinedArr = [];
  for (let i = 0; i < dates.length; i++) {
    foreign += (Math.random() - 0.5) * 0.25;
    inst    += (Math.random() - 0.5) * 0.18;
    foreign = Math.max(20, Math.min(60, foreign));
    inst    = Math.max(3,  Math.min(28, inst));
    foreignArr.push(+foreign.toFixed(2));
    combinedArr.push(+(foreign + inst).toFixed(2));
  }
  return { foreign: foreignArr, combined: combinedArr };
}

function _sma(arr, period) {
  const out = new Array(arr.length).fill(null);
  for (let i = 0; i < arr.length; i++) {
    if (i < period - 1) continue;
    let sum = 0, valid = true;
    for (let j = i - period + 1; j <= i; j++) {
      if (arr[j] == null) { valid = false; break; }
      sum += arr[j];
    }
    if (valid) out[i] = sum / period;
  }
  return out;
}

function _ema(arr, period) {
  const out = new Array(arr.length).fill(null);
  const k = 2 / (period + 1);
  // 초기값: 앞 period개의 SMA로 시작
  let seed = 0, seedCount = 0, started = false;
  for (let i = 0; i < arr.length; i++) {
    if (arr[i] == null) continue;
    if (!started) {
      seed += arr[i]; seedCount++;
      if (seedCount === period) {
        out[i] = seed / period;
        started = true;
      }
    } else {
      out[i] = arr[i] * k + out[i - 1] * (1 - k);
    }
  }
  return out;
}

/* 차트 데이터: 캔들 (open, high, low, close, volume) — 단순 랜덤 워크 */
export function generateMockCandles(basePrice, count = 60) {
  const candles = [];
  let price = basePrice;
  const now = Date.now();
  for (let i = count - 1; i >= 0; i--) {
    const open = price;
    const drift = (Math.random() - 0.5) * basePrice * 0.02;
    const close = Math.max(basePrice * 0.5, open + drift);
    const high = Math.max(open, close) + Math.random() * basePrice * 0.008;
    const low = Math.min(open, close) - Math.random() * basePrice * 0.008;
    const volume = Math.floor(basePrice * 10000 * (0.5 + Math.random()));
    candles.push({
      date: new Date(now - i * 86400000).toISOString().slice(0, 10),
      open: Math.round(open), high: Math.round(high),
      low: Math.round(low), close: Math.round(close), volume
    });
    price = close;
  }
  return candles;
}
