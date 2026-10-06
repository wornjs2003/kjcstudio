/* ==========================================================================
   종목 화면 (stock.html)

   주소의 ?code= 로 종목을 정합니다. 예: stock.html?code=005930
   값은 서버(/api/kis/*)에서 받고, 못 받으면 '—' 또는 '연결 예정' 이 남습니다.

   그리는 일은 js/components/stock-view.js 가 맡습니다. 첫 화면의 모달이
   같은 화면을 띄우는데, 그리는 코드를 두 벌 두면 한쪽만 고쳐져 갈라집니다
   (2026-09-16). 이 파일에는 「이 페이지를 열었을 때 할 일」만 남깁니다.
   ========================================================================== */

import { WATCHLIST, MARKET_STOCKS } from './data/market.js';
import { fetchLivePrices } from './data/live.js';
import { apiFetch } from './data/api.js';
import { mountWatchSide, mountVBar, startLiveLoop } from './components/frame.js';
import { mountStockView } from './components/stock-view.js';
import { mountIndicatorMenu } from './components/indicator-menu.js';

const $ = id => document.getElementById(id);

/* ── 어느 종목인가 ─────────────────────────
   주소의 코드를 그대로 쓴다. 이름은 우리 목록 → 순위표(/api/dart/universe ·
   네이버 시총 순위 저장본 · 첫 화면이 쓰는 그것) → 코드 순으로 찾는다.
   전에는 우리 목록(market.js)에 없으면 첫 관심종목으로 돌아가, 순위표 200 중
   대부분이 삼성전자로 떴다 (2026-10-06 · qa). 코드가 없거나 6자리가 아닐 때만
   첫 관심종목이다. */
const params = new URLSearchParams(location.search);
const ALL = [...WATCHLIST, ...MARKET_STOCKS];
const stock = await resolveStock(params.get('code'));

async function resolveStock(code) {
  if (!/^\d{6}$/.test(code || '')) return WATCHLIST[0];
  const known = ALL.find(s => s.code === code);
  if (known) return known;
  try {
    const r = await apiFetch('/api/dart/universe', { cache: 'no-store' });
    const j = r && await r.json();
    const hit = j && j.ok && Array.isArray(j.data) && j.data.find(x => x.code === code);
    if (hit) return { code, name: hit.name };
  } catch { /* 이름을 못 찾아도 그 종목으로 연다 */ }
  return { code, name: code };
}

document.title = `${stock.name} — KJC Holdings`;

/* ── 시작 ───────────────────────────────── */
const side = mountWatchSide($('kh-side'), { activeCode: stock.code });
mountVBar($('kh-vbar'), 'watch');

/* onBack 을 넘기지 않는다 — 이 페이지의 「← 목록」 은 첫 화면으로 가는
   링크가 맞다. 모달에서만 닫기로 바뀐다. */
const view = mountStockView(document.querySelector('.kh-main'), stock, { view: 'direct' });   // 검색 · ?code= 로 들어온 종목

/* 관심종목에 없는 종목도 헤더 시세는 받아온다 */
const inWatchlist = WATCHLIST.some(s => s.code === stock.code);
if (!inWatchlist) {
  fetchLivePrices([stock.code]).then(map => { if (map) view.paint(map[stock.code]); });
}

startLiveLoop({

  onPrices(prices) {
    side.update(prices);
    if (prices[stock.code]) view.paint(prices[stock.code]);
  },
});

mountIndicatorMenu(document.querySelector('.kh-ind-menu'));
