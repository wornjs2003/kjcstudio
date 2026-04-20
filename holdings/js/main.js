/* ==========================================================================
   KJC Holdings — 메인 엔트리
   ========================================================================== */

import { MOCK_INDICES, MOCK_STOCKS } from './data/mock.js';
import { setStocks, openDetail, closeDetail, getState } from './store/state.js';
import { mountSidebar } from './components/sidebar.js';
import { mountIndexStrip } from './components/index-strip.js';
import { mountWatchlistTable } from './components/watchlist-table.js';
import { mountNewsFeed } from './components/news-feed.js';
import { mountGlobalIssues } from './components/global-issues.js';
import { mountStockDetail } from './components/stock-detail.js';

/* ── 초기 데이터 로드 ── */
setStocks(MOCK_STOCKS);

/* ── 사이드바 ── */
mountSidebar(document.getElementById('kh-sidebar'));

/* ── 상단 지수 스트립 + 차트 패널 ── */
mountIndexStrip(document.getElementById('kh-index-strip'), MOCK_INDICES);

/* ── 세계 주요 이슈 ── */
mountGlobalIssues(document.getElementById('kh-global-issues'));

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

/* ── 초기 부팅 오버레이 제거 — 웹폰트 로드 대기 + 최소 노출 시간 ── */
(function removeBoot() {
  const boot = document.getElementById('kh-boot');
  if (!boot) return;
  const startedAt = performance.now();
  const minVisibleMs = 320;  // 스피너 깜빡이지 않도록 최소 노출
  const ready = document.fonts && document.fonts.ready
    ? document.fonts.ready
    : Promise.resolve();
  ready.then(() => {
    const elapsed = performance.now() - startedAt;
    const wait = Math.max(0, minVisibleMs - elapsed);
    setTimeout(() => {
      boot.classList.add('is-hidden');
      setTimeout(() => boot.remove(), 500);
    }, wait);
  });
})();

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
