/* 종목 상세 슬라이드 패널 */
import { fmtPrice, fmtPct, fmtChange, fmtVolume, changeDirection,
         fmtMoneyM, fmtMoneyMSigned, fmtShares, fmtKrw } from '../utils/format.js';
import { getState, subscribe, closeDetail, setDetailTab,
         setTradeSubTab, toggleInstExpanded, setChartPeriod } from '../store/state.js';
import { applyTicks } from '../utils/tick.js';
import { liveOnly, liveClass, liveTitle } from '../utils/live-value.js';
import { fetchCandles, createStockChart, maLegend } from '../chart.js';
import { getMemo, setMemo } from '../store/memo.js';
import { CHART_PERIODS } from '../data/market.js';
import { notConnected } from './empty-state.js';

const TABS = [
  { id: 'summary', label: '요약' },
  { id: 'trade',   label: '거래' },
  { id: 'fin',     label: '재무' },
  { id: 'news',    label: '뉴스' },
  { id: 'dart',    label: '공시' },
  { id: 'memo',    label: '메모' },
];

const TRADE_SUBS = [
  { id: 'investors', label: '투자자별' },
  { id: 'short',     label: '공매도' },
  { id: 'futures',   label: '선물' },
];

const INSTITUTION_LABELS = {
  financial:      '금융투자',
  insurance:      '보험',
  trust:          '투신',
  privateFund:    '사모',
  bank:           '은행',
  otherFinancial: '기타금융',
  pension:        '연기금 등',
  state:          '국가·지자체',
};

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

    const { selectedChartPeriod } = getState();
    const tradingValueWon = s.price * s.volume;

    panelEl.innerHTML = `
      <div class="kh-detail-header">
        <div class="kh-detail-title-row">
          <div>
            <span class="kh-detail-name">${s.name}</span>
            <span class="kh-detail-code">${s.code}</span>
          </div>
          <button class="kh-detail-close" data-action="close" aria-label="닫기">✕</button>
        </div>
        <div class="kh-detail-price-main">
          <div class="kh-detail-price-col">
            <div class="kh-detail-price-row">
              <span class="kh-detail-price ${s.isLive ? 'kh-' + dir : 'kh-nodata'}" title="${liveTitle(s.isLive)}" data-tick-key="detail-${s.code}" data-tick-value="${s.price}" data-tick-live="${s.isLive ? '1' : '0'}">${liveOnly(s.isLive, fmtPrice(s.price))}</span>
              ${s.isLive
                ? `<span class="kh-change-pill ${dir}">${fmtChange(s.change)} (${fmtPct(s.changePct)})</span>`
                : `<span class="kh-nodata">${liveOnly(false, null)}</span>`}
            </div>
            <div class="kh-detail-marketcap ${liveClass(s.isLive)}">시총 ${liveOnly(s.isLive, s.marketCap)}</div>
          </div>
          <dl class="kh-detail-stats">
            <div class="kh-stat"><dt>전일</dt><dd class="${liveClass(s.isLive)}">${liveOnly(s.isLive, fmtPrice(s.prevClose))}</dd></div>
            <div class="kh-stat"><dt>시가</dt><dd class="${liveClass(s.isLive)}">${liveOnly(s.isLive, fmtPrice(s.open))}</dd></div>
            <div class="kh-stat"><dt>고가</dt><dd class="${s.isLive ? 'kh-up' : 'kh-nodata'}">${liveOnly(s.isLive, fmtPrice(s.high))}</dd></div>
            <div class="kh-stat"><dt>저가</dt><dd class="${s.isLive ? 'kh-down' : 'kh-nodata'}">${liveOnly(s.isLive, fmtPrice(s.low))}</dd></div>
            <div class="kh-stat"><dt>거래량</dt><dd class="${liveClass(s.isLive)}">${liveOnly(s.isLive, fmtVolume(s.volume))}</dd></div>
            <div class="kh-stat"><dt>거래대금</dt><dd class="${liveClass(s.isLive)}">${liveOnly(s.isLive, fmtKrw(tradingValueWon))}</dd></div>
          </dl>
        </div>
      </div>
      <div class="kh-detail-split">
        <div class="kh-detail-left">
          <div class="kh-detail-chart">
            <div class="kh-chart-periods" role="tablist">
              ${CHART_PERIODS.map(p => `
                <button class="kh-chart-period ${selectedChartPeriod === p.id ? 'is-active' : ''}" data-period="${p.id}">${p.label}</button>
              `).join('')}
              <span class="kh-chart-legend" id="kh-chart-legend"></span>
            </div>
            <!-- 실제 일봉 차트가 붙는 자리 (js/chart.js) -->
            <div class="kh-chart-live" id="kh-chart-live" data-code="${s.code}">
              <div class="kh-chart-loading">차트 불러오는 중…</div>
            </div>
            <!-- 예전에는 차트를 못 받으면 난수로 만든 가짜 차트를 그렸다.
                 진짜 주가 흐름처럼 보여서 지웠고, 이제는 못 받았다고 적는다. -->
            <div class="kh-chart-fallback" id="kh-chart-fallback" hidden>
              <div class="kh-chart-loading">차트를 불러오지 못했습니다</div>
            </div>
          </div>
          <div class="kh-detail-indicators">
            ${notConnected('보조지표 (보유비중 · 심리도 · 스토캐스틱 · MACD)',
                           '투자자별 매매동향 (KIS 또는 KRX) · 일봉 기록')}
          </div>
        </div>
        <div class="kh-detail-right">
          <div class="kh-detail-tabs" role="tablist">
            ${TABS.map(t => `
              <button class="kh-tab ${selectedDetailTab === t.id ? 'is-active' : ''}" data-tab="${t.id}">${t.label}</button>
            `).join('')}
          </div>
          <div class="kh-detail-body">
            ${renderTabContent(s, selectedDetailTab)}
          </div>
        </div>
      </div>
    `;

    // 닫기
    panelEl.querySelector('[data-action="close"]').addEventListener('click', closeDetail);
    // 탭
    panelEl.querySelectorAll('.kh-tab').forEach(btn => {
      btn.addEventListener('click', () => setDetailTab(btn.dataset.tab));
    });
    // 차트 기간
    panelEl.querySelectorAll('.kh-chart-period').forEach(btn => {
      btn.addEventListener('click', () => setChartPeriod(btn.dataset.period));
    });
    // 거래 서브탭
    panelEl.querySelectorAll('.kh-subtab').forEach(btn => {
      btn.addEventListener('click', () => setTradeSubTab(btn.dataset.sub));
    });
    // 기관 확장·접기
    const instToggle = panelEl.querySelector('[data-action="toggle-inst"]');
    if (instToggle) {
      instToggle.addEventListener('click', toggleInstExpanded);
    }
    // 메모 자동 저장
    const memoEl = panelEl.querySelector('.kh-memo-box');
    if (memoEl) {
      memoEl.addEventListener('input', () => setMemo(s.code, memoEl.value));
    }

    applyTicks(panelEl);   // 값이 바뀐 숫자에 갱신 표시
    mountLiveChart(panelEl, s.code, selectedChartPeriod);
  }

  render();
  subscribe(render);
}

/* ──────────────────────────────────────────────────────────────────────────
   실제 일봉 차트 마운트

   패널은 innerHTML 로 통째로 다시 그려지므로, 그릴 때마다 이전 차트를 정리하고
   새로 만든다. 차트 데이터를 못 받으면(중계 서버가 없는 배포본 등)
   그 사실을 화면에 적는다. (예전에는 난수로 만든 가짜 차트를 그렸다)
   ────────────────────────────────────────────────────────────────────────── */
let _chart = null;
let _chartKey = null;

async function mountLiveChart(panelEl, code, periodId) {
  if (_chart) { _chart.destroy(); _chart = null; }

  const host = panelEl.querySelector('#kh-chart-live');
  const fallback = panelEl.querySelector('#kh-chart-fallback');
  const legend = panelEl.querySelector('#kh-chart-legend');
  if (!host) return;

  const useFallback = (msg) => {
    host.hidden = true;
    if (fallback) fallback.hidden = false;
    if (legend) legend.textContent = msg || '';
  };

  if (!window.LightweightCharts) return useFallback('차트 라이브러리 없음');

  const key = `${code}|${periodId}`;
  _chartKey = key;
  try {
    const { candles, meta, period } = await fetchCandles(code, periodId, 300);
    if (_chartKey !== key) return;     // 그 사이 종목이나 기간이 바뀜
    if (!candles.length) return useFallback('데이터 없음');

    host.innerHTML = '';
    host.hidden = false;
    if (fallback) fallback.hidden = true;

    _chart = createStockChart(host, candles, { period });
    if (legend) {
      legend.innerHTML = maLegend(_chart.maSeries) +
        `<span class="kh-chart-src">${meta.label || ''}봉 · ${meta.source === 'DB' ? '저장됨' : '갱신됨'}</span>`;
    }
  } catch (e) {
    console.warn('[KJC] 차트 실패:', e.message);
    useFallback('불러오지 못함');
  }
}

function renderTabContent(s, tab) {
  switch (tab) {
    case 'summary': return summaryTab(s);
    case 'trade':   return tradeTab(s);
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
      ${notConnected('시가총액 · PER · PBR · EPS · BPS · 배당수익률',
                     'KIS 국내주식 기본조회 · 상장주식수')}
    </div>
    <div class="kh-section">
      <div class="kh-section-title">요일별 등락률</div>
      ${notConnected('요일별 등락률',
                     '일봉 기록 — /api/kis/chart 로 이미 받고 있어 계산만 붙이면 됩니다')}
    </div>
    <div class="kh-section">
      <div class="kh-section-title">내 메모</div>
      <div style="color: var(--kh-text-secondary); font-size: 0.85rem;">${memo || '(비어있음 — 메모 탭에서 작성)'}</div>
    </div>
  `;
}

function chartTab(s) {
  // 이 패널의 차트는 위쪽 기간 버튼이 그리는 실제 캔들(js/chart.js)이 담당한다.
  // 예전에는 여기에 난수로 만든 가짜 캔들을 그렸는데 진짜처럼 보여서 지웠다.
  return `
    <div class="kh-section">
      <div class="kh-section-title">일봉 차트</div>
      ${notConnected('이 탭의 차트', '위쪽 기간 버튼(5분·일·주·월·년)이 실제 캔들을 그립니다')}
    </div>
  `;
}

/* ==========================================================================
   가격·거래량 통합 차트
   선차트(가격) + 시간/가격 축 라벨 + 거래량 바(하단)
   ========================================================================== */

function formatTimeLabel(date, periodId) {
  const pad = n => String(n).padStart(2, '0');
  switch (periodId) {
    case '5m':
      return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
    case '1d':
    case '1w':
      return `${pad(date.getMonth() + 1)}/${pad(date.getDate())}`;
    case '1M':
      return `${String(date.getFullYear()).slice(2)}/${pad(date.getMonth() + 1)}`;
    case '1y':
      return String(date.getFullYear());
    default:
      return `${pad(date.getMonth() + 1)}/${pad(date.getDate())}`;
  }
}

/* ==========================================================================
   보조 지표 차트 (삼성증권 POP 스타일)
   1) 외국인 / 외국인+기관 보유비중
   2) 심리도 (Psychology Line)
   3) 스토캐스틱 (%K, %D)
   4) MACD (MACD, Signal, Histogram)
   ========================================================================== */

/* 공통 라인 플로터 — series: [{values:[], color:'', width, dash?}] */
function _plotLines({ series, dates, yMin, yMax, W, plotH, padL, padR, padT, padB,
                      refLines = [], histogram = null, histColorFn = null }) {
  const N = dates.length;
  const plotW = W - padL - padR;
  const plotX = i => padL + (i / Math.max(1, N - 1)) * plotW;
  const yRange = Math.max(1e-9, yMax - yMin);
  const yAt = v => padT + (1 - (v - yMin) / yRange) * (plotH - padT - padB);

  // 배경 가이드 라인
  const gridSvg = refLines.map(r => `
    <line x1="${padL}" y1="${yAt(r.v).toFixed(1)}" x2="${W - padR}" y2="${yAt(r.v).toFixed(1)}"
          stroke="${r.color || 'var(--kh-border)'}" stroke-width="1"
          stroke-dasharray="${r.dash || '2 4'}" opacity="0.6"/>
    ${r.label ? `<text x="${W - padR - 2}" y="${(yAt(r.v) - 2).toFixed(1)}" font-size="9"
                  text-anchor="end" fill="var(--kh-text-muted)">${r.label}</text>` : ''}
  `).join('');

  // Y 좌/우 눈금 (간단히 min/max + 중간 1개)
  const yTicks = [yMin, (yMin + yMax) / 2, yMax];
  const yTicksSvg = yTicks.map(v => `
    <text x="${padL - 4}" y="${(yAt(v) + 3).toFixed(1)}" font-size="9"
          text-anchor="end" fill="var(--kh-text-muted)"
          font-family="var(--kh-font-mono, monospace)">${_fmtNum(v)}</text>
  `).join('');

  // 히스토그램 (있을 경우)
  let histSvg = '';
  if (histogram) {
    const barW = Math.max(0.6, (plotW / N) * 0.6);
    const zeroY = yAt(0);
    histSvg = histogram.map((v, i) => {
      if (v == null) return '';
      const x = plotX(i) - barW / 2;
      const y = v >= 0 ? yAt(v) : zeroY;
      const h = Math.abs(yAt(v) - zeroY);
      const color = histColorFn ? histColorFn(v, i) : (v >= 0 ? 'rgb(var(--kh-up-rgb) / 55%)' : 'rgb(var(--kh-down-rgb) / 55%)');
      return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${Math.max(0, h).toFixed(1)}" fill="${color}"/>`;
    }).join('');
  }

  // 선 그리기
  const linesSvg = series.map(s => {
    let started = false;
    const parts = [];
    s.values.forEach((v, i) => {
      if (v == null) { started = false; return; }
      const x = plotX(i).toFixed(1);
      const y = yAt(v).toFixed(1);
      parts.push((started ? 'L' : 'M') + x + ',' + y);
      started = true;
    });
    if (!parts.length) return '';
    return `<path d="${parts.join(' ')}" fill="none" stroke="${s.color}"
              stroke-width="${s.width || 1.4}"
              ${s.dash ? `stroke-dasharray="${s.dash}"` : ''}
              stroke-linejoin="round" stroke-linecap="round"/>`;
  }).join('');

  // X축 라벨 (5개)
  const xCount = 5;
  const xLabels = [];
  for (let i = 0; i < xCount; i++) {
    const idx = Math.round((i / (xCount - 1)) * (N - 1));
    xLabels.push({
      x: plotX(idx),
      label: `${String(dates[idx].getMonth() + 1).padStart(2, '0')}/${String(dates[idx].getDate()).padStart(2, '0')}`,
    });
  }
  const xLabelsSvg = xLabels.map(t => `
    <text x="${t.x.toFixed(1)}" y="${plotH - 4}" font-size="9"
          text-anchor="middle" fill="var(--kh-text-muted)"
          font-family="var(--kh-font-mono, monospace)">${t.label}</text>
  `).join('');

  return { gridSvg, yTicksSvg, histSvg, linesSvg, xLabelsSvg };
}

function _fmtNum(v) {
  if (v == null) return '';
  if (Math.abs(v) >= 1000) return Math.round(v).toLocaleString('ko-KR');
  if (Math.abs(v) >= 10)   return v.toFixed(1);
  return v.toFixed(2);
}

function tradeTab(s) {
  const { selectedTradeSub } = getState();

  /* 투자자별 매매동향·공매도·선물은 난수로 만들어 보여주고 있었다.
     그럴듯한 숫자라 실제 수급으로 읽히기 쉬워서 걷어냈다.
     ─ 할 일: KIS 투자자별 매매동향 · KRX 공매도 통계 · 선물 시세 붙이기 */
  const NEEDS = {
    investors: ['투자자별 매매동향', 'KIS 국내주식 투자자별 매매동향'],
    short:     ['공매도',           'KRX 공매도 종합 포털 통계'],
    futures:   ['선물',             'KIS 선물옵션 시세'],
  };
  const need = NEEDS[selectedTradeSub] || NEEDS.investors;

  return `
    <div class="kh-subtabs" role="tablist">
      ${TRADE_SUBS.map(sub => `
        <button class="kh-subtab ${selectedTradeSub === sub.id ? 'is-active' : ''}" data-sub="${sub.id}">${sub.label}</button>
      `).join('')}
    </div>
    ${notConnected(need[0], need[1])}
  `;
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
