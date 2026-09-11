/* 종목 상세 슬라이드 패널 */
import { fmtPrice, fmtPct, fmtChange, fmtVolume, changeDirection,
         fmtMoneyM, fmtMoneyMSigned, fmtShares, fmtKrw } from '../utils/format.js';
import { getState, subscribe, closeDetail, setDetailTab,
         setTradeSubTab, toggleInstExpanded, setChartPeriod } from '../store/state.js';
import { applyTicks } from '../utils/tick.js';
import { liveOnly, liveClass, liveTitle } from '../utils/live-value.js';
import { fetchCandles, createStockChart, maLegend } from '../chart.js';
import { getMemo, setMemo } from '../store/memo.js';
import { generateMockCandles, generateMockTrading,
         generateMockTimeSeries, generateMockIndicators,
         CHART_PERIODS } from '../data/mock.js';

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
            <!-- 실제 일봉 차트가 붙는 자리. 데이터가 없으면 아래 목업 SVG 로 대체된다 -->
            <div class="kh-chart-live" id="kh-chart-live" data-code="${s.code}">
              <div class="kh-chart-loading">차트 불러오는 중…</div>
            </div>
            <div class="kh-chart-fallback" id="kh-chart-fallback" hidden>
              ${renderPriceVolumeChart(s, selectedChartPeriod)}
            </div>
          </div>
          <div class="kh-detail-indicators">
            ${renderIndicatorCharts(s)}
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
   기존 목업 SVG 를 대신 보여준다.
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

  if (!window.LightweightCharts) return useFallback('목업 데이터');

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
    useFallback('목업 데이터');
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

  /* ── 요일별 등락률 계산 (30일 일봉 기준) ── */
  const { points } = generateMockTimeSeries(s, '1d');
  const DAY_NAMES = ['일', '월', '화', '수', '목', '금', '토'];
  const dayBucket = {};          // { 1: [pct, ...], 2: [...], ... }
  for (let i = 1; i < points.length; i++) {
    const dow = points[i].time.getDay();
    if (dow === 0 || dow === 6) continue;  // 주말 제외
    const prev = points[i - 1].price;
    const pct = ((points[i].price - prev) / prev) * 100;
    (dayBucket[dow] = dayBucket[dow] || []).push(pct);
  }
  const dayRows = [1, 2, 3, 4, 5].map(dow => {
    const arr = dayBucket[dow] || [];
    const avg = arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
    const upCnt  = arr.filter(v => v > 0).length;
    const downCnt = arr.filter(v => v < 0).length;
    const dir = changeDirection(avg);
    return { name: DAY_NAMES[dow], avg, dir, total: arr.length, upCnt, downCnt };
  });

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
      <div class="kh-section-title">요일별 등락률</div>
      <div style="color: var(--kh-text-muted); font-size: 0.78rem; margin-bottom: 8px;">최근 30거래일 평균</div>
      <table class="kh-trade-table">
        <thead>
          <tr>
            <th>요일</th>
            <th class="kh-align-right">평균</th>
            <th class="kh-align-right">상승</th>
            <th class="kh-align-right">하락</th>
          </tr>
        </thead>
        <tbody>
          ${dayRows.map(d => `
            <tr>
              <td>${d.name}요일</td>
              <td class="kh-align-right kh-mono kh-${d.dir}">${d.avg >= 0 ? '+' : ''}${d.avg.toFixed(2)}%</td>
              <td class="kh-align-right kh-mono kh-up">${d.upCnt}회</td>
              <td class="kh-align-right kh-mono kh-down">${d.downCnt}회</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
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

/* ==========================================================================
   가격·거래량 통합 차트
   선차트(가격) + 시간/가격 축 라벨 + 거래량 바(하단)
   ========================================================================== */
function renderPriceVolumeChart(stock, periodId) {
  const { points } = generateMockTimeSeries(stock, periodId);
  if (!points.length) return '';

  // 크기 추가 축소 (priceH 128→64, volH 40→20, gap 5→3 — 기존의 50%)
  const W = 520;
  const priceH = 64;
  const volH = 20;
  const gap = 3;
  const H = priceH + gap + volH;
  const padL = 52;    // 왼쪽 가격 축 라벨 공간
  const padR = 8;
  const padT = 4;
  const padB = 14;    // 하단 시간 라벨 공간

  const prices = points.map(p => p.price);
  const pMin = Math.min(...prices);
  const pMax = Math.max(...prices);
  const pRange = Math.max(1, pMax - pMin);
  const pPadded = pRange * 0.1;
  const yMin = pMin - pPadded;
  const yMax = pMax + pPadded;
  const yRange = Math.max(1, yMax - yMin);

  const vols = points.map(p => p.volume);
  const vMax = Math.max(...vols, 1);

  const plotW = W - padL - padR;
  const plotX = i => padL + (i / Math.max(1, points.length - 1)) * plotW;
  const priceY = v => padT + (1 - (v - yMin) / yRange) * (priceH - padT);
  const volY = v => priceH + gap + (1 - v / vMax) * volH;

  // 가격 라인
  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${plotX(i).toFixed(1)},${priceY(p.price).toFixed(1)}`).join(' ');
  // 면적 채우기 (선 밑 그라데이션)
  const areaPath = linePath +
    ` L${plotX(points.length - 1).toFixed(1)},${(priceH).toFixed(1)}` +
    ` L${plotX(0).toFixed(1)},${(priceH).toFixed(1)} Z`;

  // 상승/하락 색상 — 구간 전체 기준 (시작 → 끝)
  const isUp = points[points.length - 1].price >= points[0].price;
  const lineColor = isUp ? 'var(--kh-up)' : 'var(--kh-down)';
  const areaColor = isUp ? 'rgba(255,95,95,0.12)' : 'rgba(79,158,255,0.12)';

  // 가격 눈금 (5칸)
  const yTicks = 5;
  const priceTicks = [];
  for (let i = 0; i <= yTicks; i++) {
    const v = yMin + (yRange * i) / yTicks;
    const y = padT + (1 - i / yTicks) * (priceH - padT);
    priceTicks.push({ v, y });
  }
  const yTicksSvg = priceTicks.map(t => `
    <line x1="${padL}" y1="${t.y.toFixed(1)}" x2="${W - padR}" y2="${t.y.toFixed(1)}"
          stroke="var(--kh-border)" stroke-width="1" stroke-dasharray="2 4" opacity="0.5"/>
    <text x="${padL - 6}" y="${(t.y + 3).toFixed(1)}" font-size="10"
          fill="var(--kh-text-muted)" text-anchor="end" font-family="var(--kh-font-mono, monospace)">
      ${fmtPrice(Math.round(t.v))}
    </text>
  `).join('');

  // 시간 라벨 (5개 지점)
  const xTickCount = 5;
  const xTicks = [];
  for (let i = 0; i < xTickCount; i++) {
    const idx = Math.round((i / (xTickCount - 1)) * (points.length - 1));
    xTicks.push({
      x: plotX(idx),
      label: formatTimeLabel(points[idx].time, periodId),
    });
  }
  const xTicksSvg = xTicks.map(t => `
    <text x="${t.x.toFixed(1)}" y="${H - 4}" font-size="10"
          fill="var(--kh-text-muted)" text-anchor="middle"
          font-family="var(--kh-font-mono, monospace)">${t.label}</text>
  `).join('');

  // 거래량 바
  const barW = Math.max(1, (plotW / points.length) * 0.7);
  const volBars = points.map((p, i) => {
    const x = plotX(i) - barW / 2;
    const y = volY(p.volume);
    const h = (priceH + gap + volH) - y;
    const up = i > 0 ? p.price >= points[i - 1].price : true;
    const color = up ? 'rgba(255,95,95,0.6)' : 'rgba(79,158,255,0.6)';
    return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${Math.max(0, h).toFixed(1)}" fill="${color}"/>`;
  }).join('');

  // 가격·거래량 구분선
  const divider = `<line x1="${padL}" y1="${priceH + gap / 2}" x2="${W - padR}" y2="${priceH + gap / 2}" stroke="var(--kh-border)" stroke-width="1" opacity="0.6"/>`;

  // "거래량" 라벨
  const volLabel = `<text x="${padL - 6}" y="${(priceH + gap + 12).toFixed(1)}" font-size="10"
        fill="var(--kh-text-muted)" text-anchor="end">거래량</text>`;

  return `
    <svg class="kh-chart-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="가격·거래량 차트">
      ${yTicksSvg}
      <path d="${areaPath}" fill="${areaColor}" />
      <path d="${linePath}" fill="none" stroke="${lineColor}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
      ${divider}
      ${volBars}
      ${volLabel}
      ${xTicksSvg}
    </svg>
  `;
}

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
function renderIndicatorCharts(stock) {
  const ind = generateMockIndicators(stock);

  return `
    ${indicatorBlock({
      title: '보유비중',
      subtitle: '외국인 / 외국인+기관 — 최근 90일',
      svg: chartOwnership(ind),
      legend: `
        <span class="kh-ind-legend-item"><i style="background:#4f9eff"></i>외국인</span>
        <span class="kh-ind-legend-item"><i style="background:#f5a623"></i>외국인+기관</span>
      `,
    })}
    ${indicatorBlock({
      title: '심리도 (Psychology Line)',
      subtitle: '최근 12일 중 상승일 비율 — 75↑ 과열 / 25↓ 침체',
      svg: chartPsychology(ind),
      legend: `<span class="kh-ind-legend-item"><i style="background:#7b61ff"></i>심리도</span>`,
    })}
    ${indicatorBlock({
      title: '스토캐스틱 (Slow %K, %D)',
      subtitle: '%K(14,3), %D(3) — 80↑ 과매수 / 20↓ 과매도',
      svg: chartStochastic(ind),
      legend: `
        <span class="kh-ind-legend-item"><i style="background:#ff5f5f"></i>%K</span>
        <span class="kh-ind-legend-item"><i style="background:#4f9eff"></i>%D</span>
      `,
    })}
    ${indicatorBlock({
      title: 'MACD (12,26,9)',
      subtitle: 'MACD · Signal · Histogram',
      svg: chartMacd(ind),
      legend: `
        <span class="kh-ind-legend-item"><i style="background:#4f9eff"></i>MACD</span>
        <span class="kh-ind-legend-item"><i style="background:#f5a623"></i>Signal</span>
        <span class="kh-ind-legend-item"><i style="background:#6a6a76"></i>Histogram</span>
      `,
    })}
  `;
}

function indicatorBlock({ title, subtitle, svg, legend }) {
  return `
    <div class="kh-ind-block">
      <div class="kh-ind-head">
        <div>
          <div class="kh-ind-title">${title}</div>
          <div class="kh-ind-sub">${subtitle}</div>
        </div>
        <div class="kh-ind-legend">${legend}</div>
      </div>
      ${svg}
    </div>
  `;
}

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
      const color = histColorFn ? histColorFn(v, i) : (v >= 0 ? 'rgba(255,95,95,0.55)' : 'rgba(79,158,255,0.55)');
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

function chartOwnership(ind) {
  const { dates, ownership } = ind;
  // 추가 축소 (H 104→52 — 기존의 50%)
  const W = 640, H = 52, padL = 42, padR = 8, padT = 4, padB = 12;
  const all = ownership.foreign.concat(ownership.combined);
  const yMin = Math.floor(Math.min(...all) - 2);
  const yMax = Math.ceil(Math.max(...all) + 2);

  const { gridSvg, yTicksSvg, linesSvg, xLabelsSvg } = _plotLines({
    series: [
      { values: ownership.foreign,  color: '#4f9eff', width: 1.6 },
      { values: ownership.combined, color: '#f5a623', width: 1.6 },
    ],
    dates, yMin, yMax, W, plotH: H, padL, padR, padT, padB,
    refLines: [],
  });
  return `<svg class="kh-ind-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
    ${gridSvg}${yTicksSvg}${linesSvg}${xLabelsSvg}
  </svg>`;
}

function chartPsychology(ind) {
  const { dates, psychology } = ind;
  // 추가 축소 (H 88→44 — 기존의 50%)
  const W = 640, H = 44, padL = 42, padR = 8, padT = 4, padB = 12;
  const { gridSvg, yTicksSvg, linesSvg, xLabelsSvg } = _plotLines({
    series: [{ values: psychology, color: '#7b61ff', width: 1.6 }],
    dates, yMin: 0, yMax: 100, W, plotH: H, padL, padR, padT, padB,
    refLines: [
      { v: 75, label: '75 과열', color: 'rgba(255,95,95,0.4)' },
      { v: 25, label: '25 침체', color: 'rgba(79,158,255,0.4)' },
      { v: 50, color: 'rgba(255,255,255,0.08)', dash: '1 3' },
    ],
  });
  return `<svg class="kh-ind-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
    ${gridSvg}${yTicksSvg}${linesSvg}${xLabelsSvg}
  </svg>`;
}

function chartStochastic(ind) {
  const { dates, stochastic } = ind;
  // 추가 축소 (H 96→48 — 기존의 50%)
  const W = 640, H = 48, padL = 42, padR = 8, padT = 4, padB = 12;
  const { gridSvg, yTicksSvg, linesSvg, xLabelsSvg } = _plotLines({
    series: [
      { values: stochastic.k, color: '#ff5f5f', width: 1.6 },
      { values: stochastic.d, color: '#4f9eff', width: 1.4 },
    ],
    dates, yMin: 0, yMax: 100, W, plotH: H, padL, padR, padT, padB,
    refLines: [
      { v: 80, label: '80 과매수', color: 'rgba(255,95,95,0.4)' },
      { v: 20, label: '20 과매도', color: 'rgba(79,158,255,0.4)' },
    ],
  });
  return `<svg class="kh-ind-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
    ${gridSvg}${yTicksSvg}${linesSvg}${xLabelsSvg}
  </svg>`;
}

function chartMacd(ind) {
  const { dates, macd } = ind;
  // 추가 축소 (H 104→52 — 기존의 50%)
  const W = 640, H = 52, padL = 42, padR = 8, padT = 4, padB = 12;
  const allVals = [
    ...macd.macd.filter(v => v != null),
    ...macd.signal.filter(v => v != null),
    ...macd.histogram.filter(v => v != null),
  ];
  const absMax = Math.max(...allVals.map(v => Math.abs(v)), 1);
  const yMin = -absMax * 1.15;
  const yMax = +absMax * 1.15;

  const { gridSvg, yTicksSvg, histSvg, linesSvg, xLabelsSvg } = _plotLines({
    series: [
      { values: macd.macd,   color: '#4f9eff', width: 1.6 },
      { values: macd.signal, color: '#f5a623', width: 1.4 },
    ],
    dates, yMin, yMax, W, plotH: H, padL, padR, padT, padB,
    refLines: [{ v: 0, color: 'rgba(255,255,255,0.15)' }],
    histogram: macd.histogram,
    histColorFn: (v, i) => {
      const prev = macd.histogram[i - 1];
      const rising = prev == null ? true : v >= prev;
      if (v >= 0) return rising ? 'rgba(255,95,95,0.7)' : 'rgba(255,95,95,0.35)';
      return rising ? 'rgba(79,158,255,0.35)' : 'rgba(79,158,255,0.7)';
    },
  });
  return `<svg class="kh-ind-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
    ${gridSvg}${histSvg}${yTicksSvg}${linesSvg}${xLabelsSvg}
  </svg>`;
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

function tradeTab(s) {
  const { selectedTradeSub, tradeInstExpanded } = getState();
  const data = generateMockTrading(s);

  let body = '';
  switch (selectedTradeSub) {
    case 'investors': body = investorsSection(data, tradeInstExpanded); break;
    case 'short':     body = shortSection(data); break;
    case 'futures':   body = futuresSection(data, s); break;
    default:          body = investorsSection(data, tradeInstExpanded);
  }

  return `
    <div class="kh-subtabs" role="tablist">
      ${TRADE_SUBS.map(sub => `
        <button class="kh-subtab ${selectedTradeSub === sub.id ? 'is-active' : ''}" data-sub="${sub.id}">${sub.label}</button>
      `).join('')}
    </div>
    <div class="kh-trade-date">기준일: ${data.date} · 당일 기준 (임시 데이터)</div>
    ${body}
  `;
}

/* 투자자별 매매동향 */
function investorsSection(data, instExpanded) {
  const inv = data.investors;
  const rows = [
    investorRow('개인',       inv.individual),
    investorRow('외국인',     inv.foreign),
    investorRow('기타외국인', inv.foreignOther, true),
    instRow(inv.institutionTotal, inv.institutionBreakdown, instExpanded),
    investorRow('기타법인',   inv.corporation),
  ];

  return `
    <div class="kh-section">
      <div class="kh-section-title">투자자별 매매동향</div>
      <table class="kh-trade-table">
        <thead>
          <tr>
            <th>투자자</th>
            <th class="kh-align-right">매수</th>
            <th class="kh-align-right">매도</th>
            <th class="kh-align-right">순매수</th>
          </tr>
        </thead>
        <tbody>
          ${rows.join('')}
        </tbody>
      </table>
      <div class="kh-trade-note">
        단위: 금액(원) · 순매수 부호 <span class="kh-up">+ 빨강</span> / <span class="kh-down">− 파랑</span>
      </div>
    </div>
  `;
}

function investorRow(label, d, isSub = false) {
  if (!d) return '';
  const dir = changeDirection(d.net);
  return `
    <tr class="${isSub ? 'is-sub' : ''}">
      <td class="kh-inv-name">${label}</td>
      <td class="kh-align-right kh-mono">${fmtMoneyM(d.buy)}</td>
      <td class="kh-align-right kh-mono">${fmtMoneyM(d.sell)}</td>
      <td class="kh-align-right kh-mono kh-${dir}">${fmtMoneyMSigned(d.net)}</td>
    </tr>
  `;
}

function instRow(total, breakdown, expanded) {
  const dir = changeDirection(total.net);
  const chev = expanded ? '▾' : '▸';
  const subRows = expanded
    ? Object.entries(breakdown).map(([key, d]) => {
        const ddir = changeDirection(d.net);
        return `
          <tr class="is-sub kh-inst-sub">
            <td class="kh-inv-name">  └ ${INSTITUTION_LABELS[key]}</td>
            <td class="kh-align-right kh-mono">${fmtMoneyM(d.buy)}</td>
            <td class="kh-align-right kh-mono">${fmtMoneyM(d.sell)}</td>
            <td class="kh-align-right kh-mono kh-${ddir}">${fmtMoneyMSigned(d.net)}</td>
          </tr>
        `;
      }).join('')
    : '';

  return `
    <tr class="kh-inst-row" data-action="toggle-inst" style="cursor:pointer;">
      <td class="kh-inv-name"><span class="kh-chev">${chev}</span> 기관계</td>
      <td class="kh-align-right kh-mono">${fmtMoneyM(total.buy)}</td>
      <td class="kh-align-right kh-mono">${fmtMoneyM(total.sell)}</td>
      <td class="kh-align-right kh-mono kh-${dir}">${fmtMoneyMSigned(total.net)}</td>
    </tr>
    ${subRows}
  `;
}

/* 공매도 */
function shortSection(data) {
  const s = data.shortSell;
  return `
    <div class="kh-section">
      <div class="kh-section-title">당일 공매도</div>
      <div class="kh-metric-row"><span class="kh-metric-label">공매도 수량</span><span class="kh-metric-value">${fmtShares(s.shortVolume)}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">공매도 거래대금</span><span class="kh-metric-value">${fmtMoneyM(s.shortAmountMil)}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">공매도 비중</span><span class="kh-metric-value">${s.shortRatio}%</span></div>
    </div>
    <div class="kh-section">
      <div class="kh-section-title">공매도 잔고</div>
      <div class="kh-metric-row"><span class="kh-metric-label">잔고 수량</span><span class="kh-metric-value">${fmtShares(s.balanceVolume)}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">잔고 금액</span><span class="kh-metric-value">${fmtMoneyM(s.balanceAmountMil)}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">잔고 비율</span><span class="kh-metric-value">${s.balanceRatio}%</span></div>
    </div>
    <div class="kh-trade-note">
      공매도 비중이 높을수록 하락 베팅 수요가 강함. 잔고 비율 추이로 기조 확인.
    </div>
  `;
}

/* 선물 */
function futuresSection(data, stock) {
  const f = data.futures;
  if (!f.available) {
    return `<div class="kh-empty" style="padding: 40px 0;">
      ${stock.name}은(는) 개별주식선물 대상 종목이 아닙니다.
    </div>`;
  }
  const ind = f.investors.individual.net;
  const frn = f.investors.foreign.net;
  const inst = f.investors.institution.net;
  const oiDir = changeDirection(f.openInterestChange);

  return `
    <div class="kh-section">
      <div class="kh-section-title">개별주식선물 정보</div>
      <div class="kh-metric-row"><span class="kh-metric-label">선물 코드</span><span class="kh-metric-value">${f.code}</span></div>
      <div class="kh-metric-row"><span class="kh-metric-label">최근월물</span><span class="kh-metric-value">${f.expiry}</span></div>
      <div class="kh-metric-row">
        <span class="kh-metric-label">미결제약정</span>
        <span class="kh-metric-value">${f.openInterest.toLocaleString('ko-KR')}계약
          <span class="kh-${oiDir}" style="font-size:0.78rem; margin-left:6px;">
            ${f.openInterestChange >= 0 ? '+' : ''}${f.openInterestChange.toLocaleString('ko-KR')}
          </span>
        </span>
      </div>
    </div>
    <div class="kh-section">
      <div class="kh-section-title">투자자별 선물 순매수</div>
      <table class="kh-trade-table">
        <thead>
          <tr>
            <th>투자자</th>
            <th class="kh-align-right">순매수</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>개인</td><td class="kh-align-right kh-mono kh-${changeDirection(ind)}">${fmtMoneyMSigned(ind)}</td></tr>
          <tr><td>외국인</td><td class="kh-align-right kh-mono kh-${changeDirection(frn)}">${fmtMoneyMSigned(frn)}</td></tr>
          <tr><td>기관</td><td class="kh-align-right kh-mono kh-${changeDirection(inst)}">${fmtMoneyMSigned(inst)}</td></tr>
        </tbody>
      </table>
    </div>
    <div class="kh-trade-note">
      선물 순매수 방향과 현물 순매수 방향이 엇갈릴 때는 차익거래·헷지 의심.
    </div>
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
