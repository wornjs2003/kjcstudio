/* ==========================================================================
   KJC Holdings — 메인 엔트리
   ========================================================================== */

import { MOCK_INDICES, MOCK_STOCKS, MOCK_MARKET_STOCKS } from './data/mock.js';
import { fetchLiveIndices, fetchLivePrices, applyLiveToStock, LIVE_CODES } from './data/live.js';
import { markRefresh, endRefresh } from './utils/tick.js';
import { markLoaded } from './utils/live-value.js';
import { setStocks, openDetail, closeDetail, getState, setState } from './store/state.js';
import { mountSidebar } from './components/sidebar.js';
import { mountIndexStrip, updateIndices } from './components/index-strip.js';
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

/* ──────────────────────────────────────────────────────────────────────────
   실시간 데이터 적용 (한국투자증권)
   지수(KOSPI/KOSDAQ/KOSPI200)와 삼성전자·SK하이닉스만 실제 값으로 바꾼다.
   나머지 항목은 아직 목업이며, 중계 서버가 없으면 전부 목업으로 남는다.
   ────────────────────────────────────────────────────────────────────────── */
/* 갱신 주기(ms).
   1회 갱신에 KIS 호출 5회(지수 3 + 종목 2)가 든다.
   서버 예산이 초당 1건(한도의 1/10)이므로 5초가 예산을 꽉 채우는 값이고,
   10초면 예산의 절반만 쓴다. 종목 클릭 같은 즉석 조회에 여유를 두려고 10초로 잡았다. */
const LIVE_REFRESH_MS = 10000;

async function refreshLiveData() {
  if (document.hidden) return;   // 다른 탭을 보고 있으면 호출하지 않는다

  const [indices, prices] = await Promise.all([
    fetchLiveIndices(),
    fetchLivePrices(LIVE_CODES),
  ]);

  if (!indices && !prices) return;

  // 이 구간에서 그려지는 실시간 숫자는 값이 그대로여도 깜빡인다.
  // (갱신이 돌고 있다는 걸 눈으로 확인할 수 있게)
  markRefresh();
  try {
    if (indices) updateIndices(indices);

    if (prices) {
      // 상세 패널용 목록과 시세 테이블용 목록 양쪽 모두 같은 종목을 갱신한다
      [MOCK_STOCKS, MOCK_MARKET_STOCKS].forEach(list => {
        if (!Array.isArray(list)) return;
        list.forEach(s => {
          const live = prices[s.code];
          if (live) applyLiveToStock(s, live);
        });
      });
      setStocks(MOCK_STOCKS);      // 구독자에게 갱신 알림
      setState({});                // 열려 있는 상세 패널도 다시 그리도록
    }
  } finally {
    endRefresh();
    markLoaded();   // 이제부터 값이 없으면 '로딩중' 대신 '—' 로 표시
  }
}

refreshLiveData();
setInterval(refreshLiveData, LIVE_REFRESH_MS);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refreshLiveData();
});

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
