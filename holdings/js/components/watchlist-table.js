/* ==========================================================================
   관심종목 테이블 — 탭 포함
   탭: 코스피 / 코스닥 / 관심종목 / 거래상위 / 상승상위 / 하락상위 / 시가총액 / 공매상위
   ※ 코스피·코스닥 탭은 해당 시장 전 종목을 시가총액 내림차순으로 표시
   ========================================================================== */

import { fmtPrice, fmtPct, fmtVolume, fmtKrw, changeDirection } from '../utils/format.js';
import { applyTicks } from '../utils/tick.js';
import { liveOnly, liveClass, liveTitle } from '../utils/live-value.js';
import { openDetail, getState, subscribe, setWatchlistView } from '../store/state.js';
import { getMemo } from '../store/memo.js';
import { MOCK_MARKET_STOCKS, fmtMarketCapNum } from '../data/mock.js';

const VIEW_TABS = [
  { id: 'kospi',        label: '코스피' },
  { id: 'kosdaq',       label: '코스닥' },
  { id: 'watchlist',    label: '관심종목' },
  { id: 'topVolume',    label: '거래상위' },
  { id: 'topGainers',   label: '상승상위' },
  { id: 'topLosers',    label: '하락상위' },
  { id: 'topMarketCap', label: '시가총액' },
  { id: 'topShort',     label: '공매상위' },
];

/* 뷰별 정렬·필터 + 5번째 컬럼 정의 */
function getRows(view, watchlistStocks) {
  const top = (arr, n = 20) => arr.slice(0, n);
  switch (view) {
    case 'watchlist':
      return { rows: watchlistStocks, lastCol: { key: 'memo', label: '메모' } };
    case 'kospi':
      // 코스피 전 종목 — 시가총액 내림차순
      return {
        rows: MOCK_MARKET_STOCKS
          .filter(s => s.market === 'KOSPI')
          .slice()
          .sort((a, b) => b.marketCapNum - a.marketCapNum),
        lastCol: { key: 'marketCap', label: '시가총액' },
      };
    case 'kosdaq':
      // 코스닥 전 종목 — 시가총액 내림차순
      return {
        rows: MOCK_MARKET_STOCKS
          .filter(s => s.market === 'KOSDAQ')
          .slice()
          .sort((a, b) => b.marketCapNum - a.marketCapNum),
        lastCol: { key: 'marketCap', label: '시가총액' },
      };
    case 'topVolume':
      return {
        rows: top([...MOCK_MARKET_STOCKS].sort((a, b) => b.volume - a.volume)),
        lastCol: { key: 'tradeValue', label: '거래대금' },
      };
    case 'topGainers':
      return {
        rows: top([...MOCK_MARKET_STOCKS].sort((a, b) => b.changePct - a.changePct)),
        lastCol: { key: 'marketCap', label: '시가총액' },
      };
    case 'topLosers':
      return {
        rows: top([...MOCK_MARKET_STOCKS].sort((a, b) => a.changePct - b.changePct)),
        lastCol: { key: 'marketCap', label: '시가총액' },
      };
    case 'topMarketCap':
      return {
        rows: top([...MOCK_MARKET_STOCKS].sort((a, b) => b.marketCapNum - a.marketCapNum)),
        lastCol: { key: 'marketCap', label: '시가총액' },
      };
    case 'topShort':
      return {
        rows: top([...MOCK_MARKET_STOCKS].sort((a, b) => b.shortRatio - a.shortRatio)),
        lastCol: { key: 'shortRatio', label: '공매비율' },
      };
    default:
      return { rows: watchlistStocks, lastCol: { key: 'memo', label: '메모' } };
  }
}

function lastColValue(s, key) {
  switch (key) {
    case 'memo': {
      const memo = getMemo(s.code) || s.memo || '';
      return `<span class="kh-memo-cell" title="${memo}">${memo}</span>`;
    }
    case 'tradeValue': {
      const value = s.price * s.volume;
      return `<span class="kh-mono">${fmtKrw(value)}</span>`;
    }
    case 'marketCap': {
      const mc = s.marketCapNum
        ? fmtMarketCapNum(s.marketCapNum)
        : (s.marketCap || '');
      return `<span class="kh-mono">${mc}</span>`;
    }
    case 'shortRatio': {
      const r = typeof s.shortRatio === 'number' ? s.shortRatio.toFixed(2) : '0.00';
      return `<span class="kh-mono">${r}%</span>`;
    }
    default:
      return '';
  }
}

export function mountWatchlistTable(el) {
  function render() {
    const { stocks: watchlist, selectedStock, watchlistView } = getState();
    const { rows, lastCol } = getRows(watchlistView, watchlist);
    const showRank = watchlistView !== 'watchlist';
    const activeTab = VIEW_TABS.find(t => t.id === watchlistView) || VIEW_TABS[0];

    el.innerHTML = `
      <div class="kh-card-header">
        <div class="kh-wl-tabs" role="tablist">
          ${VIEW_TABS.map(t => `
            <button type="button" class="kh-wl-tab ${t.id === watchlistView ? 'is-active' : ''}"
                    data-view="${t.id}" role="tab" aria-selected="${t.id === watchlistView}">
              ${t.label}
            </button>
          `).join('')}
        </div>
        <div class="kh-card-actions">
          ${watchlistView === 'watchlist' ? `
            <button class="kh-btn" title="추가">+ 추가</button>
            <button class="kh-btn" title="정렬">정렬</button>
          ` : `
            <span class="kh-card-subtitle">상위 ${rows.length}개</span>
          `}
        </div>
      </div>
      <div class="kh-card-body">
        <table class="kh-table">
          <thead>
            <tr>
              ${showRank ? '<th class="kh-align-right" style="width:40px;">#</th>' : ''}
              <th>종목</th>
              <th class="kh-align-right">현재가</th>
              <th class="kh-align-right">등락</th>
              <th class="kh-align-right">거래량</th>
              <th${lastCol.key === 'memo' ? '' : ' class="kh-align-right"'}>${lastCol.label}</th>
            </tr>
          </thead>
          <tbody>
            ${rows.length === 0
              ? `<tr><td colspan="${showRank ? 6 : 5}" class="kh-empty-row">
                   목록이 비어있어요. 종목을 추가해보세요.
                 </td></tr>`
              : rows.map((s, i) => row(s, i, selectedStock?.code === s.code, lastCol, showRank)).join('')}
          </tbody>
        </table>
      </div>
    `;

    // 탭 클릭
    el.querySelectorAll('.kh-wl-tab').forEach(btn => {
      btn.addEventListener('click', () => setWatchlistView(btn.dataset.view));
    });

    // 행 클릭 → 상세 열기 (관심종목은 watchlist 에서, 랭킹은 MOCK_MARKET_STOCKS 에서)
    el.querySelectorAll('tbody tr[data-code]').forEach(tr => {
      tr.addEventListener('click', () => {
        const code = tr.dataset.code;
        const pool = activeTab.id === 'watchlist' ? watchlist : MOCK_MARKET_STOCKS;
        const stock = pool.find(s => s.code === code);
        // 랭킹 종목은 메모·일부 지표가 없을 수 있으므로 기본값 채움
        if (stock) openDetail(hydrateStock(stock));
      });
    });

    applyTicks(el);   // 값이 바뀐 숫자에 갱신 표시
  }
  render();
  subscribe(render);
}

/* 랭킹 종목을 상세 패널에서 열 수 있도록 누락 필드 보강 */
function hydrateStock(s) {
  if (s.metrics) return s; // 이미 완전한 관심종목
  return {
    ...s,
    prevClose: s.price - s.change,
    open: s.price - Math.round(s.change * 0.4),
    high: s.price + Math.abs(s.change),
    low:  s.price - Math.abs(s.change),
    marketCap: s.marketCapNum ? fmtMarketCapNum(s.marketCapNum) : (s.marketCap || '-'),
    memo: '',
    metrics: s.metrics || { per: '-', pbr: '-', eps: 0, bps: 0, dividend: 0, dividendYield: 0 },
  };
}

function row(s, i, selected, lastCol, showRank) {
  const dir = changeDirection(s.change);
  return `
    <tr data-code="${s.code}" data-index="${i}" class="${selected ? 'is-selected' : ''}">
      ${showRank ? `<td class="kh-align-right kh-rank">${i + 1}</td>` : ''}
      <td>
        <div class="kh-stock-name">
          <span class="kh-stock-name-main">${s.name}</span>
          <span class="kh-stock-name-code">${s.code}</span>
        </div>
      </td>
      <td class="kh-align-right"><span class="kh-price ${s.isLive ? 'kh-' + dir : 'kh-nodata'}" title="${liveTitle(s.isLive)}" data-tick-key="wl-${s.code}" data-tick-value="${s.price}" data-tick-live="${s.isLive ? '1' : '0'}">${liveOnly(s.isLive, fmtPrice(s.price))}</span></td>
      <td class="kh-align-right">${s.isLive ? `<span class="kh-change-pill ${dir}">${fmtPct(s.changePct)}</span>` : `<span class="kh-nodata">${liveOnly(false, null)}</span>`}</td>
      <td class="kh-align-right"><span class="kh-volume ${liveClass(s.isLive)}">${liveOnly(s.isLive, fmtVolume(s.volume))}</span></td>
      <td${lastCol.key === 'memo' ? '' : ' class="kh-align-right"'}>${lastColValue(s, lastCol.key)}</td>
    </tr>
  `;
}
