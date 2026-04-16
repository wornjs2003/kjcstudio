/* ==========================================================================
   KJC Holdings — 메인 엔트리
   ========================================================================== */

import { MOCK_INDICES, MOCK_STOCKS } from './data/mock.js';
import { setStocks, openDetail, closeDetail, getState } from './store/state.js';
import { mountSidebar } from './components/sidebar.js';
import { renderIndexStrip } from './components/index-strip.js';
import { mountWatchlistTable } from './components/watchlist-table.js';
import { mountNewsFeed } from './components/news-feed.js';
import { mountStockDetail } from './components/stock-detail.js';

/* ── 초기 데이터 로드 ── */
setStocks(MOCK_STOCKS);

/* ── 사이드바 ── */
mountSidebar(document.getElementById('kh-sidebar'));

/* ── 상단 지수 스트립 ── */
document.getElementById('kh-index-strip').outerHTML = renderIndexStrip(MOCK_INDICES);

/* ── 관심종목 테이블 ── */
mountWatchlistTable(document.getElementById('kh-watchlist'));

/* ── 뉴스 피드 ── */
mountNewsFeed(document.getElementById('kh-feed'));

/* ── 종목 상세 패널 ── */
mountStockDetail(
  document.getElementById('kh-detail'),
  document.getElementById('kh-detail-backdrop')
);

/* ── 백드롭 클릭 시 닫기 ── */
document.getElementById('kh-detail-backdrop').addEventListener('click', closeDetail);

/* ── 키보드 단축키 ── */
document.addEventListener('keydown', (e) => {
  const tag = (e.target.tagName || '').toLowerCase();
  const editing = tag === 'input' || tag === 'textarea' || e.target.isContentEditable;

  // Esc — 상세 닫기 (편집 중이어도 허용)
  if (e.key === 'Escape') {
    if (getState().detailOpen) {
      closeDetail();
      e.preventDefault();
    }
    return;
  }

  if (editing) return;

  const stocks = getState().stocks;
  const current = getState().selectedStock;
  const idx = current ? stocks.findIndex(s => s.code === current.code) : -1;

  switch (e.key) {
    case 'j': /* 아래 */
      if (stocks.length) {
        const next = idx < 0 ? 0 : Math.min(stocks.length - 1, idx + 1);
        openDetail(stocks[next]);
        e.preventDefault();
      }
      break;
    case 'k': /* 위 */
      if (stocks.length) {
        const prev = idx < 0 ? 0 : Math.max(0, idx - 1);
        openDetail(stocks[prev]);
        e.preventDefault();
      }
      break;
    case 'Enter':
      if (idx < 0 && stocks.length) openDetail(stocks[0]);
      break;
    case '/':
      const search = document.querySelector('.kh-search-input');
      if (search) { search.focus(); e.preventDefault(); }
      break;
  }
});
