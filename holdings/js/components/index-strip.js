/* 상단 지수 스트립 */
import { fmtPct, changeDirection } from '../utils/format.js';

export function renderIndexStrip(indices) {
  return `
    <div class="kh-index-strip" role="region" aria-label="시장 지수">
      ${indices.map(idx => {
        const dir = changeDirection(idx.change);
        return `
          <div class="kh-index-item">
            <span class="kh-index-name">${idx.name}</span>
            <span class="kh-index-value kh-mono">${idx.value.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            <span class="kh-index-change kh-${dir}">${fmtPct(idx.changePct)}</span>
          </div>
        `;
      }).join('')}
    </div>
  `;
}
