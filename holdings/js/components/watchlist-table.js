/* 관심종목 테이블 */
import { fmtPrice, fmtPct, fmtVolume, changeDirection } from '../utils/format.js';
import { openDetail, getState, subscribe } from '../store/state.js';
import { getMemo } from '../store/memo.js';

export function mountWatchlistTable(el) {
  function render() {
    const { stocks, selectedStock } = getState();
    el.innerHTML = `
      <div class="kh-card-header">
        <div style="display:flex; align-items:center;">
          <h3 class="kh-card-title">관심종목</h3>
          <span class="kh-card-subtitle">${stocks.length}개</span>
        </div>
        <div class="kh-card-actions">
          <button class="kh-btn" title="추가">+ 추가</button>
          <button class="kh-btn" title="정렬">정렬</button>
        </div>
      </div>
      <div class="kh-card-body">
        <table class="kh-table">
          <thead>
            <tr>
              <th>종목</th>
              <th class="kh-align-right">현재가</th>
              <th class="kh-align-right">등락</th>
              <th class="kh-align-right">거래량</th>
              <th>메모</th>
            </tr>
          </thead>
          <tbody>
            ${stocks.map((s, i) => row(s, i, selectedStock?.code === s.code)).join('')}
          </tbody>
        </table>
      </div>
    `;
    el.querySelectorAll('tbody tr').forEach(tr => {
      tr.addEventListener('click', () => {
        const code = tr.dataset.code;
        const stock = getState().stocks.find(s => s.code === code);
        if (stock) openDetail(stock);
      });
    });
  }
  render();
  subscribe(render);
}

function row(s, i, selected) {
  const dir = changeDirection(s.change);
  const memo = getMemo(s.code) || s.memo || '';
  return `
    <tr data-code="${s.code}" data-index="${i}" class="${selected ? 'is-selected' : ''}">
      <td>
        <div class="kh-stock-name">
          <span class="kh-stock-name-main">${s.name}</span>
          <span class="kh-stock-name-code">${s.code}</span>
        </div>
      </td>
      <td class="kh-align-right"><span class="kh-price">${fmtPrice(s.price)}</span></td>
      <td class="kh-align-right"><span class="kh-change-pill ${dir}">${fmtPct(s.changePct)}</span></td>
      <td class="kh-align-right"><span class="kh-volume">${fmtVolume(s.volume)}</span></td>
      <td><span class="kh-memo-cell" title="${memo}">${memo}</span></td>
    </tr>
  `;
}
