/* ==========================================================================
   글로벌 상태 관리 (아주 얕은 pub/sub)
   Vue/React 없이 컴포넌트 간 상태 공유용
   ========================================================================== */

const listeners = new Set();

const state = {
  stocks: [],            // 관심종목 전체 (데이터)
  selectedStock: null,   // 현재 상세 패널에 열린 종목
  selectedDetailTab: 'summary',
  selectedChartPeriod: '1d',       // 5m / 1d / 1w / 1M / 1y
  selectedTradeSub: 'investors',  // 거래 탭 내부 서브탭: investors/short/futures
  tradeInstExpanded: false,        // 기관 세부 펼침 여부
  detailOpen: false,
  activeNav: 'home',
  selectedIndex: 'KOSPI',          // 상단 지수 스트립에서 선택된 지수 (코드)
  watchlistView: 'watchlist',      // watchlist / topVolume / topGainers / topLosers / topMarketCap / topShort
};

export function getState() {
  return state;
}

export function setState(patch) {
  Object.assign(state, patch);
  listeners.forEach(fn => fn(state));
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/* 액션 */
export function openDetail(stock) {
  setState({
    selectedStock: stock,
    detailOpen: true,
    selectedDetailTab: 'summary',
    selectedChartPeriod: '1d',
    selectedTradeSub: 'investors',
    tradeInstExpanded: false,
  });
}

export function setChartPeriod(periodId) {
  setState({ selectedChartPeriod: periodId });
}

export function closeDetail() {
  setState({ detailOpen: false });
}

export function setDetailTab(tab) {
  setState({ selectedDetailTab: tab });
}

export function setTradeSubTab(sub) {
  setState({ selectedTradeSub: sub });
}

export function toggleInstExpanded() {
  setState({ tradeInstExpanded: !state.tradeInstExpanded });
}

export function setActiveNav(nav) {
  setState({ activeNav: nav });
}

export function setStocks(stocks) {
  setState({ stocks });
}

export function setSelectedIndex(code) {
  setState({ selectedIndex: code });
}

export function setWatchlistView(view) {
  setState({ watchlistView: view });
}
