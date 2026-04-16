/* ==========================================================================
   Mock 데이터
   실제 데이터 소스(네이버 금융·DART)가 붙기 전까지 사용
   ========================================================================== */

export const MOCK_INDICES = [
  { name: 'KOSPI',    value: 2654.31, change: +7.82, changePct: +0.30 },
  { name: 'KOSDAQ',   value: 890.14,  change: -4.47, changePct: -0.50 },
  { name: 'S&P 500',  value: 4521.33, change: +4.52, changePct: +0.10 },
  { name: 'USD/KRW',  value: 1342.50, change: -2.70, changePct: -0.20 },
];

export const MOCK_STOCKS = [
  {
    code: '005930', name: '삼성전자', sector: '반도체',
    price: 83400, change: +1000, changePct: +1.21,
    volume: 24_100_000, marketCap: '498조',
    memo: 'HBM 기대로 장기 보유 중',
    metrics: { per: 12.3, pbr: 1.4, eps: 6780, bps: 59570, dividend: 2.1, dividendYield: 2.1 }
  },
  {
    code: '000660', name: 'SK하이닉스', sector: '반도체',
    price: 195500, change: -600, changePct: -0.31,
    volume: 8_300_000, marketCap: '142조',
    memo: 'HBM3E 양산 주목',
    metrics: { per: 9.8, pbr: 1.8, eps: 19940, bps: 108610, dividend: 1200, dividendYield: 0.6 }
  },
  {
    code: '035420', name: 'NAVER', sector: 'IT',
    price: 210000, change: +1050, changePct: +0.50,
    volume: 2_100_000, marketCap: '32조',
    memo: '커머스·AI 회복 확인 중',
    metrics: { per: 18.5, pbr: 1.1, eps: 11350, bps: 190900, dividend: 914, dividendYield: 0.4 }
  },
  {
    code: '035720', name: '카카오', sector: 'IT',
    price: 55700, change: -620, changePct: -1.10,
    volume: 15_200_000, marketCap: '24조',
    memo: '리스크 확인 전 보류',
    metrics: { per: 33.1, pbr: 1.0, eps: 1680, bps: 55700, dividend: 0, dividendYield: 0 }
  },
  {
    code: '005380', name: '현대차', sector: '자동차',
    price: 238500, change: +4900, changePct: +2.10,
    volume: 3_400_000, marketCap: '50조',
    memo: '미국 현지 생산 이슈 주시',
    metrics: { per: 6.1, pbr: 0.65, eps: 39100, bps: 367000, dividend: 11000, dividendYield: 4.6 }
  },
  {
    code: '373220', name: 'LG에너지솔루션', sector: '2차전지',
    price: 362000, change: +1500, changePct: +0.42,
    volume: 1_800_000, marketCap: '84조',
    memo: '전기차 수요 회복 대기',
    metrics: { per: 74.8, pbr: 4.2, eps: 4840, bps: 86190, dividend: 0, dividendYield: 0 }
  },
  {
    code: '207940', name: '삼성바이오로직스', sector: '바이오',
    price: 802000, change: -7000, changePct: -0.86,
    volume: 180_000, marketCap: '57조',
    memo: '4공장 가동률 체크',
    metrics: { per: 54.2, pbr: 6.1, eps: 14800, bps: 131500, dividend: 0, dividendYield: 0 }
  },
  {
    code: '068270', name: '셀트리온', sector: '바이오',
    price: 178000, change: -500, changePct: -0.28,
    volume: 920_000, marketCap: '38조',
    memo: '짐펜트라 실적 기다림',
    metrics: { per: 28.4, pbr: 2.1, eps: 6270, bps: 84760, dividend: 750, dividendYield: 0.4 }
  },
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
