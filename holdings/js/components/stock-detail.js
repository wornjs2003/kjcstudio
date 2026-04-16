/* 종목 상세 슬라이드 패널 */
import { fmtPrice, fmtPct, fmtChange, fmtVolume, changeDirection } from '../utils/format.js';
import { getState, subscribe, closeDetail, setDetailTab } from '../store/state.js';
import { getMemo, setMemo } from '../store/memo.js';
import { generateMockCandles } from '../data/mock.js';

const TABS = [
  { id: 'summary', label: '요약' },
  { id: 'chart',   label: '차트' },
  { id: 'fin',     label: '재무' },
  { id: 'news',    label: '뉴스' },
  { id: 'dart',    label: '공시' },
  { id: 'memo',    label: '메모' },
];

export function mountStockDetail(panelEl, backdropEl) {
  function render() {
    const { selectedStock, detailOpen, selectedDetailTab } = getState();

    panelEl.classList.toggle('is-open', detailOpen);
    backdropEl.classList.toggle('is-open', detailOpen);

    if (!selectedStock) {
      panelEl.innerHTML = '';
      return;
    }

    const s = selectedStock;
    const dir = changeDirection(s.change);

    panelEl.innerHTML = `
      <div class="kh-detail-header">
        <div class="kh-detail-title-row">
          <div>
            <span class="kh-detail-name">${s.name}</span>
            <span class="kh-detail-code">${s.code}</span>
          </div>
          <button class="kh-detail-close" data-action="close" aria-label="닫기">✕</button>
        </div>
        <div class="kh-detail-price-row">
          <span class="kh-detail-price kh-${dir}">${fmtPrice(s.price)}</span>
          <span class="kh-change-pill ${dir}">${fmtChange(s.change)} (${fmtPct(s.changePct)})</span>
        </div>
        <div class="kh-detail-volume">거래량 ${fmtVolume(s.volume)} · 시총 ${s.marketCap}</div>
      </div>
      <div class="kh-detail-tabs" role="tablist">
        ${TABS.map(t => `
          <button class="kh-tab ${selectedDetailTab === t.id ? 'is-active' : ''}" data-tab="${t.id}">${t.label}</button>
        `).join('')}
      </div>
      <div class="kh-detail-body">
        ${renderTabContent(s, selectedDetailTab)}
      </div>
    `;

    // 닫기
    panelEl.querySelector('[data-action="close"]').addEventListener('click', closeDetail);
    // 탭
    panelEl.querySelectorAll('.kh-tab').forEach(btn => {
      btn.addEventListener('click', () => setDetailTab(btn.dataset.tab));
    });
    // 메모 자동 저장
    const memoEl = panelEl.querySelector('.kh-memo-box');
    if (memoEl) {
      memoEl.addEventListener('input', () => setMemo(s.code, memoEl.value));
    }
  }

  render();
  subscribe(render);
}

function renderTabContent(s, tab) {
  switch (tab) {
    case 'summary': return summaryTab(s);
    case 'chart':   return chartTab(s);
    case 'fin':     return finTab(s);
    case 'news':    return newsTab(s);
    case 'dart':    return dartTab(s);
    case 'memo':    return memoTab(s);
    default:        return summaryTab(s);
  }
}

function summaryTab(s) {
  const memo = getMemo(s.code) || s.memo || '';
  return `
    <div class="kh-section">
      <div class="kh-section-title">핵심 지표</div>
      <div class="kh-metric-row"><span class="kh-metric-label">시가총액</span><span class="kh-metric-value">${s.marketCap}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">PER</span><span class="kh-metric-value">${s.metrics.per}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">PBR</span><span class="kh-metric-value">${s.metrics.pbr}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">EPS</span><span class="kh-metric-value">${fmtPrice(s.metrics.eps)}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">BPS</span><span class="kh-metric-value">${fmtPrice(s.metrics.bps)}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">배당수익률</span><span class="kh-metric-value">${s.metrics.dividendYield}%</span></div>
    </div>
    <div class="kh-section">
      <div class="kh-section-title">내 메모</div>
      <div style="color: var(--kh-text-secondary); font-size: 0.85rem;">${memo || '(비어있음 — 메모 탭에서 작성)'}</div>
    </div>
  `;
}

function chartTab(s) {
  return `
    <div class="kh-section">
      <div class="kh-section-title">일봉 차트 (임시 — 목업 데이터)</div>
      ${renderMiniCandles(s.price)}
      <div style="margin-top: 12px; color: var(--kh-text-muted); font-size: 0.78rem;">
        실제 네이버 금융 차트는 단계적으로 연결 예정.
      </div>
    </div>
  `;
}

function renderMiniCandles(basePrice) {
  const candles = generateMockCandles(basePrice, 40);
  const highs = candles.map(c => c.high);
  const lows = candles.map(c => c.low);
  const max = Math.max(...highs);
  const min = Math.min(...lows);
  const range = Math.max(1, max - min);
  const W = 460, H = 180, pad = 8;
  const bw = (W - pad*2) / candles.length;

  const scaleY = v => H - pad - ((v - min) / range) * (H - pad*2);

  const bodies = candles.map((c, i) => {
    const x = pad + i * bw + bw * 0.15;
    const w = bw * 0.7;
    const y = scaleY(Math.max(c.open, c.close));
    const h = Math.max(1, Math.abs(scaleY(c.open) - scaleY(c.close)));
    const up = c.close >= c.open;
    const color = up ? 'var(--kh-up)' : 'var(--kh-down)';
    const xc = x + w / 2;
    return `
      <line x1="${xc}" y1="${scaleY(c.high)}" x2="${xc}" y2="${scaleY(c.low)}" stroke="${color}" stroke-width="1"/>
      <rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${color}" />
    `;
  }).join('');

  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%; height:auto; display:block;" preserveAspectRatio="xMidYMid meet">${bodies}</svg>`;
}

function finTab(s) {
  return `
    <div class="kh-section">
      <div class="kh-section-title">재무 지표</div>
      <div class="kh-metric-row"><span class="kh-metric-label">PER</span><span class="kh-metric-value">${s.metrics.per}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">PBR</span><span class="kh-metric-value">${s.metrics.pbr}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">EPS</span><span class="kh-metric-value">${fmtPrice(s.metrics.eps)}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">BPS</span><span class="kh-metric-value">${fmtPrice(s.metrics.bps)}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">DPS</span><span class="kh-metric-value">${fmtPrice(s.metrics.dividend)}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">배당수익률</span><span class="kh-metric-value">${s.metrics.dividendYield}%</span></div>
    </div>
    <div class="kh-empty" style="padding: 20px 0;">
      상세 재무제표·연간 추이는 네이버 금융/DART 연동 후 표시됩니다.
    </div>
  `;
}

function newsTab(s) {
  return `<div class="kh-empty">${s.name} 관련 뉴스 — 실데이터 연동 예정</div>`;
}

function dartTab(s) {
  return `<div class="kh-empty">${s.name} 관련 DART 공시 — 실데이터 연동 예정</div>`;
}

function memoTab(s) {
  const memo = getMemo(s.code) || s.memo || '';
  return `
    <div class="kh-section">
      <div class="kh-section-title">투자 메모</div>
      <textarea class="kh-memo-box" placeholder="이 종목에 대해 생각 정리... (자동 저장)">${memo}</textarea>
    </div>
  `;
}
