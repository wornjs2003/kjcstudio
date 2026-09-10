/* ==========================================================================
   실시간 데이터 (한국투자증권 KIS)

   preview.bat 으로 띄운 로컬 서버에서만 동작한다.
   GitHub Pages 배포본에는 중계 서버가 없으므로 조회가 실패하고,
   호출한 쪽은 null 을 받아 기존 목업 데이터를 그대로 쓰게 된다.
   ========================================================================== */

/* 실제로 연결된 종목 — 나머지는 아직 목업이다 */
export const LIVE_CODES = ['005930', '000660'];

let _ready = null;

/* 중계 서버가 살아 있고 키가 설정되어 있는지 (한 번만 확인) */
async function kisReady() {
  if (_ready !== null) return _ready;
  try {
    const r = await fetch('/api/kis/health', { cache: 'no-store' });
    const j = await r.json();
    _ready = !!(j && j.ok && j.configured);
    if (_ready) console.info('[KJC] 한국투자증권 API 연결됨 (' + (j.modeLabel || '') + ')');
  } catch {
    _ready = false;
  }
  if (!_ready) console.info('[KJC] 중계 서버 없음 — 목업 데이터로 표시합니다');
  return _ready;
}

/* 주요 지수 (KOSPI / KOSDAQ / KOSPI200). 실패 시 null */
export async function fetchLiveIndices() {
  if (!(await kisReady())) return null;
  try {
    const r = await fetch('/api/kis/indices', { cache: 'no-store' });
    if (!r.ok) return null;
    const j = await r.json();
    if (!j || !j.ok || !Array.isArray(j.data) || !j.data.length) return null;
    return j.data;
  } catch {
    return null;
  }
}

/* 종목 시세. { '005930': {price, prev, amt, pct, ...} } 형태. 실패 시 null */
export async function fetchLivePrices(codes = LIVE_CODES) {
  if (!(await kisReady())) return null;
  try {
    const r = await fetch('/api/kis/prices?codes=' + codes.join(','), { cache: 'no-store' });
    if (!r.ok) return null;
    const j = await r.json();
    if (!j || !j.ok || !j.data || !Object.keys(j.data).length) return null;
    return j.data;
  } catch {
    return null;
  }
}

/* KIS 응답을 대시보드가 쓰는 종목 형태로 옮겨 담는다 (있는 값만 덮어쓴다) */
export function applyLiveToStock(stock, live) {
  if (!stock || !live) return stock;
  if (live.price != null) stock.price = live.price;
  if (live.amt != null) stock.change = live.amt;
  if (live.pct != null) stock.changePct = live.pct;
  if (live.prev != null) stock.prevClose = live.prev;
  if (live.open != null) stock.open = live.open;
  if (live.high != null) stock.high = live.high;
  if (live.low != null) stock.low = live.low;
  if (live.volume != null) stock.volume = live.volume;
  if (live.per != null) stock.per = live.per;
  if (live.pbr != null) stock.pbr = live.pbr;
  // 시가총액: KIS 는 억원 단위 정수로 준다 -> 조 단위 문자열로 표기
  if (live.marketCap != null) {
    stock.marketCapNum = live.marketCap;
    const jo = live.marketCap / 10000;
    stock.marketCap = jo >= 1
      ? jo.toLocaleString('ko-KR', { maximumFractionDigits: 0 }) + '조'
      : live.marketCap.toLocaleString('ko-KR') + '억';
  }
  stock.isLive = true;
  return stock;
}
