/* ==========================================================================
   상단 지수 스트립 + 선택 지수 차트 패널
   - 기본 선택: KOSPI
   - 클릭하면 해당 지수의 차트·수치로 전환
   ========================================================================== */

import { fmtPct, changeDirection } from '../utils/format.js';
import { getState, setSelectedIndex, subscribe } from '../store/state.js';

/* 지수 값 포맷: 원/달러만 정수, 나머지는 소수 둘째 자리 */
function fmtIndexValue(v, unit) {
  if (unit === '원') {
    return v.toLocaleString('ko-KR', { maximumFractionDigits: 0 });
  }
  return v.toLocaleString('ko-KR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/* 지수 시계열을 단순 라인 차트 SVG 로 렌더 */
function renderIndexChart(series, isUp) {
  if (!series || series.length < 2) return '';
  const W = 640;
  const H = 160;
  const padL = 48, padR = 8, padT = 10, padB = 22;

  const yMin = Math.min(...series);
  const yMax = Math.max(...series);
  const yRange = Math.max(1e-9, yMax - yMin);
  const pad = yRange * 0.1;
  const yLo = yMin - pad;
  const yHi = yMax + pad;
  const yR = Math.max(1e-9, yHi - yLo);

  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const plotX = i => padL + (i / (series.length - 1)) * plotW;
  const plotY = v => padT + (1 - (v - yLo) / yR) * plotH;

  const linePath = series
    .map((v, i) => `${i === 0 ? 'M' : 'L'}${plotX(i).toFixed(1)},${plotY(v).toFixed(1)}`)
    .join(' ');

  const areaPath =
    linePath +
    ` L${plotX(series.length - 1).toFixed(1)},${(padT + plotH).toFixed(1)}` +
    ` L${plotX(0).toFixed(1)},${(padT + plotH).toFixed(1)} Z`;

  const lineColor = isUp ? 'var(--kh-up)' : 'var(--kh-down)';
  const areaColor = isUp ? 'rgba(255,95,95,0.12)' : 'rgba(79,158,255,0.12)';

  // Y축 눈금 5개
  const yTicks = 5;
  const yTicksSvg = [];
  for (let i = 0; i <= yTicks; i++) {
    const v = yLo + (yR * i) / yTicks;
    const y = padT + (1 - i / yTicks) * plotH;
    yTicksSvg.push(`
      <line x1="${padL}" y1="${y.toFixed(1)}" x2="${W - padR}" y2="${y.toFixed(1)}"
            stroke="var(--kh-border)" stroke-width="1" stroke-dasharray="2 4" opacity="0.45"/>
      <text x="${padL - 6}" y="${(y + 3).toFixed(1)}" font-size="10"
            fill="var(--kh-text-muted)" text-anchor="end"
            font-family="var(--kh-font-mono, monospace)">
        ${v.toLocaleString('ko-KR', { maximumFractionDigits: 1 })}
      </text>
    `);
  }

  // X축 라벨 (5지점 — 60일 기준 12일 간격)
  const xTickCount = 5;
  const xLabelsSvg = [];
  const totalDays = series.length;
  for (let i = 0; i < xTickCount; i++) {
    const idx = Math.round((i / (xTickCount - 1)) * (totalDays - 1));
    const daysAgo = totalDays - 1 - idx;
    const label = daysAgo === 0 ? '오늘' : `-${daysAgo}일`;
    xLabelsSvg.push(`
      <text x="${plotX(idx).toFixed(1)}" y="${H - 6}" font-size="10"
            fill="var(--kh-text-muted)" text-anchor="middle"
            font-family="var(--kh-font-mono, monospace)">${label}</text>
    `);
  }

  return `
    <svg class="kh-index-chart-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet"
         role="img" aria-label="지수 추이">
      ${yTicksSvg.join('')}
      <path d="${areaPath}" fill="${areaColor}" />
      <path d="${linePath}" fill="none" stroke="${lineColor}" stroke-width="1.6"
            stroke-linejoin="round" stroke-linecap="round"/>
      ${xLabelsSvg.join('')}
    </svg>
  `;
}

/* 스트립 + 패널 전체 마크업 */
function renderStripMarkup(indices, selectedCode) {
  const selected = indices.find(i => i.code === selectedCode) || indices[0];
  const selDir = changeDirection(selected.change);
  const isUp = selected.change >= 0;

  const tabs = indices.map(idx => {
    const dir = changeDirection(idx.change);
    const active = idx.code === selected.code ? 'is-active' : '';
    return `
      <button type="button" class="kh-index-tab ${active}" data-index="${idx.code}">
        <span class="kh-index-name">${idx.name}</span>
        <span class="kh-index-value kh-mono">${fmtIndexValue(idx.value, idx.unit)}</span>
        <span class="kh-index-change kh-${dir}">${fmtPct(idx.changePct)}</span>
      </button>
    `;
  }).join('');

  return `
    <section class="kh-index-strip-wrap" aria-label="시장 지수">
      <div class="kh-index-strip" role="tablist">
        ${tabs}
      </div>
      <div class="kh-index-detail">
        <div class="kh-index-detail-head">
          <div class="kh-index-detail-name">${selected.name}</div>
          <div class="kh-index-detail-value-row">
            <span class="kh-index-detail-value kh-mono kh-${selDir}">
              ${fmtIndexValue(selected.value, selected.unit)}
            </span>
            <span class="kh-index-detail-change kh-${selDir}">
              ${selected.change >= 0 ? '+' : ''}${selected.change.toFixed(2)}
              (${fmtPct(selected.changePct)})
            </span>
          </div>
          <div class="kh-index-detail-meta">
            60거래일 추이 · 목업 데이터
          </div>
        </div>
        <div class="kh-index-detail-chart">
          ${renderIndexChart(selected.series, isUp)}
        </div>
      </div>
    </section>
  `;
}

/* 컴포넌트 마운트 — 지수 탭 클릭 이벤트 + 상태 구독 */
export function mountIndexStrip(hostEl, indices) {
  function render() {
    const { selectedIndex } = getState();
    hostEl.innerHTML = renderStripMarkup(indices, selectedIndex);

    // 탭 클릭 이벤트 연결
    hostEl.querySelectorAll('.kh-index-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        setSelectedIndex(btn.dataset.index);
      });
    });
  }

  render();
  subscribe(render);
}

/* 하위호환 — 기존 renderIndexStrip 호출부가 있으면 경고만 */
export function renderIndexStrip() {
  console.warn('renderIndexStrip 은 mountIndexStrip 으로 대체되었습니다.');
  return '<div class="kh-index-strip-wrap"></div>';
}
