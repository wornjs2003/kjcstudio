/* ==========================================================================
   실시간 데이터 (한국투자증권 KIS)

   preview.bat 으로 띄운 로컬 서버에서만 동작한다.
   GitHub Pages 배포본에는 중계 서버가 없으므로 조회가 실패하고,
   호출한 쪽은 null 을 받고, 화면에는 '불러오는 중' 또는 '—' 이 남는다.
   ========================================================================== */

/* 시세를 받아오는 종목 — 관심종목 전체.
   목록에 없는 종목(시장 전체 탭 등)은 화면에 '—' 로 남는다.
   종목이 늘면 호출량도 느니, 갱신 주기(main.js)와 함께 보고 정할 것. */
import { WATCHLIST } from './market.js';
import { apiFetch } from './api.js';
export const LIVE_CODES = WATCHLIST.map(s => s.code);

let _ready = null;

/* 중계 서버가 살아 있고 키가 설정되어 있는지 (한 번만 확인) */
async function kisReady() {
  if (_ready !== null) return _ready;
  try {
    const r = await apiFetch('/api/kis/health', { cache: 'no-store' });
    if (!r) return null;   // 로그인이 풀렸다
    const j = await r.json();
    _ready = !!(j && j.ok && j.configured);
    if (_ready) console.info('[KJC] 한국투자증권 API 연결됨 (' + (j.modeLabel || '') + ')');
  } catch {
    _ready = false;
  }
  if (!_ready) console.info('[KJC] 중계 서버 없음 — 시세 칸은 비워 둡니다');
  return _ready;
}

/* 주요 지수 (KOSPI / KOSDAQ / KOSPI200). 실패 시 null */
export async function fetchLiveIndices() {
  if (!(await kisReady())) return null;
  try {
    const r = await apiFetch('/api/kis/indices', { cache: 'no-store' });
    if (!r || !r.ok) return null;
    const j = await r.json();
    if (!j || !j.ok || !Array.isArray(j.data) || !j.data.length) return null;
    /* 선물은 목록이 아니라 따로 온다. 배열에 실어 보내면 지수 카드가 하나 더
       생겨 버리므로, 목록에 표시만 달아 둔다. */
    j.data.futures = j.futures || null;
    return j.data;
  } catch {
    return null;
  }
}

/* 종목 시세. { '005930': {price, prev, amt, pct, ...} } 형태. 실패 시 null */
export async function fetchLivePrices(codes = LIVE_CODES) {
  if (!(await kisReady())) return null;
  try {
    const r = await apiFetch('/api/kis/prices?codes=' + codes.join(','), { cache: 'no-store' });
    if (!r || !r.ok) return null;
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

/* 지수의 당일 5분 흐름. 큰 차트가 쓴다.
   실패하면 null — 부르는 쪽이 일봉으로 물러선다. */
export async function fetchIndexMinutes(code) {
  if (!(await kisReady())) return null;
  try {
    const r = await apiFetch('/api/kis/index-minutes?code=' + encodeURIComponent(code),
      { cache: 'no-store' });
    if (!r || !r.ok) return null;
    const j = await r.json();
    if (!j || !j.ok || !Array.isArray(j.data?.bars) || !j.data.bars.length) return null;
    return j.data.bars;
  } catch {
    return null;
  }
}

/* 목록용 시세 — 한 번에 30종목씩 받는다.

   현재가 API 는 한 종목씩만 주지만, 관심종목(멀티종목) 시세조회는 30개를
   한 번에 준다. 순위표처럼 수십 종목을 보여주는 곳은 이것을 써야 한다.
     30종목 기준  단건 30번 7.9초  →  멀티 1번 2.1초 (2026-09-14 실측)

   주는 항목이 단건보다 적다. 시가총액·PER·PBR·52주 최고저가 없으므로,
   그런 값이 필요한 종목 화면은 fetchLivePrices 를 그대로 쓴다. */
export async function fetchQuotes(codes) {
  if (!codes || !codes.length) return null;
  if (!(await kisReady())) return null;
  try {
    const r = await apiFetch('/api/kis/quotes?codes=' + codes.join(','), { cache: 'no-store' });
    if (!r || !r.ok) return null;
    const j = await r.json();
    if (!j || !j.ok || !j.data) return null;
    return j.data;
  } catch {
    return null;
  }
}

/* 지수 캔들 (일·주·월·년). 5분봉은 fetchIndexMinutes 가 맡는다.
   실패하면 null — 부르는 쪽이 화면을 비운다. */
export async function fetchIndexCandles(code, period) {
  if (!(await kisReady())) return null;
  try {
    const qs = new URLSearchParams({ code, period });
    const r = await apiFetch('/api/kis/index-candles?' + qs, { cache: 'no-store' });
    if (!r || !r.ok) return null;
    const j = await r.json();
    if (!j || !j.ok || !Array.isArray(j.data?.bars) || !j.data.bars.length) return null;
    return j.data.bars;
  } catch {
    return null;
  }
}
