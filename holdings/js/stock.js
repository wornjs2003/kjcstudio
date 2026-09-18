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
import { mountWatchSide, mountVBar, mountFootStrip, startLiveLoop } from './components/frame.js';
import { mountStockView } from './components/stock-view.js';
import { mountIndicatorMenu } from './components/indicator-menu.js';

const $ = id => document.getElementById(id);

/* ── 어느 종목인가 ─────────────────────────
   목록에 없는 코드가 들어오면 첫 관심종목으로 돌아간다. */
const params = new URLSearchParams(location.search);
const ALL = [...WATCHLIST, ...MARKET_STOCKS];
const stock = ALL.find(s => s.code === params.get('code')) || WATCHLIST[0];

document.title = `${stock.name} — KJC Holdings`;

/* ── 시작 ───────────────────────────────── */
const side = mountWatchSide($('kh-side'), { activeCode: stock.code });
mountVBar($('kh-vbar'), 'watch');
const foot = mountFootStrip($('kh-foot'));

/* onBack 을 넘기지 않는다 — 이 페이지의 「← 목록」 은 첫 화면으로 가는
   링크가 맞다. 모달에서만 닫기로 바뀐다. */
const view = mountStockView(document.querySelector('.kh-main'), stock);

/* 관심종목에 없는 종목도 헤더 시세는 받아온다 */
const inWatchlist = WATCHLIST.some(s => s.code === stock.code);
if (!inWatchlist) {
  fetchLivePrices([stock.code]).then(map => { if (map) view.paint(map[stock.code]); });
}

startLiveLoop({
  onIndices(indices) { foot.update(indices); },
  onPrices(prices) {
    side.update(prices);
    if (prices[stock.code]) view.paint(prices[stock.code]);
  },
});

mountIndicatorMenu(document.querySelector('.kh-ind-menu'));
