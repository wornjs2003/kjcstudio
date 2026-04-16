/* ==========================================================================
   글로벌 상태 관리 (아주 얕은 pub/sub)
   Vue/React 없이 컴포넌트 간 상태 공유용
   ========================================================================== */

const listeners = new Set();

const state = {
  stocks: [],            // 관심종목 전체 (데이터)
  selectedStock: null,   // 현재 상세 패널에 열린 종목
  selectedDetailTab: 'summary',
  detailOpen: false,
  activeNav: 'home',
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
  setState({ selectedStock: stock, detailOpen: true, selectedDetailTab: 'summary' });
}

export function closeDetail() {
  setState({ detailOpen: false });
}

export function setDetailTab(tab) {
  setState({ selectedDetailTab: tab });
}

export function setActiveNav(nav) {
  setState({ activeNav: nav });
}

export function setStocks(stocks) {
  setState({ stocks });
}
