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
import { MARKET_STOCKS, fmtMarketCapNum } from '../data/market.js';

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
  switch (view) {
    case 'watchlist':
      return { rows: watchlistStocks, lastCol: { key: 'memo', label: '메모' } };

    /* 시장 전체 목록 — 시세는 서버가 채운다.
       순서는 목록에 적힌 순서 그대로다. 시가총액순으로 세우려면
       시가총액(= 상장주식수 × 현재가)을 받아와야 한다. */
    case 'kospi':
      return {
        rows: MARKET_STOCKS.filter(s => s.market === 'KOSPI'),
        lastCol: { key: 'marketCap', label: '시가총액' },
      };
    case 'kosdaq':
      return {
        rows: MARKET_STOCKS.filter(s => s.market === 'KOSDAQ'),
        lastCol: { key: 'marketCap', label: '시가총액' },
      };

    /* 아래 탭들은 순위를 매길 기준값 자체가 없다. 예전에는 예시 숫자로
       순위를 만들어 보여줬는데 실제 순위처럼 보여서 오해를 부른다.
       기준값이 붙기 전까지는 비워 두고, 무엇이 필요한지 화면에 적는다.
       ─ 할 일: KIS 국내주식 순위분석 (거래대금·등락률) · 상장주식수 · KRX 공매도 통계 */
    case 'topVolume':
      return { rows: [], notReady: ['거래상위', 'KIS 순위분석 (거래대금)'],
               lastCol: { key: 'tradeValue', label: '거래대금' } };
    case 'topGainers':
      return { rows: [], notReady: ['상승상위', 'KIS 순위분석 (등락률)'],
               lastCol: { key: 'marketCap', label: '시가총액' } };
    case 'topLosers':
      return { rows: [], notReady: ['하락상위', 'KIS 순위분석 (등락률)'],
               lastCol: { key: 'marketCap', label: '시가총액' } };
    case 'topMarketCap':
      return { rows: [], notReady: ['시가총액 순위', '상장주식수 (KIS 기본조회 또는 KRX)'],
               lastCol: { key: 'marketCap', label: '시가총액' } };
    case 'topShort':
      return { rows: [], notReady: ['공매상위', '공매도 잔고비율 (KRX 공매도 통계)'],
               lastCol: { key: 'shortRatio', label: '공매비율' } };

    default:
      return { rows: watchlistStocks, lastCol: { key: 'memo', label: '메모' } };
  }
}

function lastColValue(s, key) {
  const none = '<span class="kh-nodata">—</span>';
  switch (key) {
    case 'memo': {
      const memo = getMemo(s.code) || '';
      return `<span class="kh-memo-cell" title="${memo}">${memo}</span>`;
    }
    case 'tradeValue':
      // 거래대금 = 현재가 × 거래량. 둘 다 받아온 값일 때만 계산한다
      return (s.isLive && s.price != null && s.volume != null)
        ? `<span class="kh-mono">${fmtKrw(s.price * s.volume)}</span>` : none;
    case 'marketCap':
      // 시가총액 = 상장주식수 × 현재가. 상장주식수를 아직 받아오지 않는다
      return s.marketCapNum != null
        ? `<span class="kh-mono">${fmtMarketCapNum(s.marketCapNum)}</span>` : none;
    case 'shortRatio':
      return typeof s.shortRatio === 'number'
        ? `<span class="kh-mono">${s.shortRatio.toFixed(2)}%</span>` : none;
    default:
      return '';
  }
}

export function mountWatchlistTable(el) {
  function render() {
    const { stocks: watchlist, selectedStock, watchlistView } = getState();
    const { rows, lastCol, notReady } = getRows(watchlistView, watchlist);
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
            <span class="kh-card-subtitle">${rows.length ? `상위 ${rows.length}개` : ''}</span>
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
                   ${notReady
                     ? `${notReady[0]} — 아직 연결하지 않았습니다
                        <div class="kh-empty-todo">붙일 것: ${notReady[1]}</div>`
                     : '목록이 비어있어요. 종목을 추가해보세요.'}
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

    // 행 클릭 → 상세 열기 (관심종목은 watchlist 에서, 그 외는 MARKET_STOCKS 에서)
    el.querySelectorAll('tbody tr[data-code]').forEach(tr => {
      tr.addEventListener('click', () => {
        const code = tr.dataset.code;
        const pool = activeTab.id === 'watchlist' ? watchlist : MARKET_STOCKS;
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
