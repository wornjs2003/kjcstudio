/* ==========================================================================
   종목 화면 (stock.html)

   주소의 ?code= 로 종목을 정합니다. 예: stock.html?code=005930
   값은 서버(/api/kis/*)에서 받고, 못 받으면 '—' 또는 '연결 예정' 이 남습니다.
   ========================================================================== */

import { WATCHLIST, MARKET_STOCKS, CHART_PERIODS } from './data/market.js';
import { fetchLivePrices } from './data/live.js';
import { fetchCandles, createStockChart, maLegend } from './chart.js';
import { getMemo, setMemo } from './store/memo.js';
import { fmtNum, fmtWon, fmtPct, fmtMoneyKr, fmtShareCount, fmtDelta, dirClass }
  from './utils/format.js';
import { mountWatchSide, mountVBar, mountFootStrip, startLiveLoop } from './components/frame.js';

const $ = id => document.getElementById(id);

/* ── 어느 종목인가 ─────────────────────────
   목록에 없는 코드가 들어오면 첫 관심종목으로 돌아간다. */
const params = new URLSearchParams(location.search);
const ALL = [...WATCHLIST, ...MARKET_STOCKS];
const stock = ALL.find(s => s.code === params.get('code')) || WATCHLIST[0];

document.title = `${stock.name} — KJC Holdings`;

/* ── 헤더 ───────────────────────────────── */
function paintHead(live) {
  $('kh-ic').style.background = stock.brand;
  $('kh-ic').textContent = stock.name.slice(0, 2);
  $('kh-name').textContent = stock.name;
  $('kh-code').textContent = stock.code;

  const price = $('kh-price');
  const sub = $('kh-price-sub');
  if (!live) {
    price.className = 'kh-price kh-num kh-mut';
    price.textContent = '불러오는 중';
    sub.textContent = '';
    return;
  }
  const cls = dirClass(live.pct);
  price.className = 'kh-price kh-num ' + cls;
  price.textContent = fmtWon(live.price);
  sub.className = 'kh-price-sub kh-num ' + cls;
  sub.textContent = '어제보다 ' + fmtDelta(live.amt, live.pct);

  $('kh-r1').innerHTML  = rangeBar(live.low, live.high, live.price);
  $('kh-r52').innerHTML = rangeBar(live.low52, live.high52, live.price);
  $('kh-amt').textContent = fmtMoneyKr(Math.round(live.price * live.volume / 1e8));
  $('kh-vol').textContent = fmtShareCount(live.volume);
  $('kh-cap').textContent = fmtMoneyKr(live.marketCap);

  $('kh-m-per').textContent = live.per != null ? live.per + '배' : '—';
  $('kh-m-pbr').textContent = live.pbr != null ? live.pbr + '배' : '—';
  $('kh-m-cap').textContent = fmtMoneyKr(live.marketCap);
  $('kh-m-vol').textContent = fmtShareCount(live.volume);
  $('kh-m-hi').textContent  = fmtWon(live.high52);
  $('kh-m-lo').textContent  = fmtWon(live.low52);

  $('kh-ord-price').value = fmtNum(live.price);
}

/* 현재가가 범위 어디쯤인지 점으로 */
function rangeBar(lo, hi, cur) {
  if (lo == null || hi == null || cur == null) return '<b class="kh-mut">—</b>';
  const p = Math.max(0, Math.min(1, (cur - lo) / Math.max(1, hi - lo)));
  return `<b class="kh-num">${fmtNum(lo)}</b>
    <span class="kh-rng-bar"><i style="left:calc(${(p * 100).toFixed(1)}% - 4px)"></i></span>
    <b class="kh-num">${fmtNum(hi)}</b>`;
}

/* ── 차트 ───────────────────────────────── */
let chart = null;
let periodId = '1d';

function paintPeriods() {
  $('kh-per').innerHTML = CHART_PERIODS.map(p => `
    <button data-period="${p.id}" class="${p.id === periodId ? 'is-active' : ''}">${p.label}</button>
  `).join('') + `<span class="kh-per-tools">⊞ ／ ⇄ ⤢</span>`;

  $('kh-per').querySelectorAll('button').forEach(b =>
    b.addEventListener('click', () => { periodId = b.dataset.period; paintPeriods(); drawChart(); }));
}

async function drawChart() {
  const host = $('kh-chart');
  const legend = $('kh-chart-legend');
  const key = periodId;
  if (chart) { chart.destroy(); chart = null; }
  host.innerHTML = `<div class="kh-soon"><div class="kh-soon-t">차트 불러오는 중…</div></div>`;
  try {
    const { candles, meta, period } = await fetchCandles(stock.code, periodId, 300);
    if (key !== periodId) return;                  // 그 사이 기간을 바꿨다
    if (!candles.length) throw new Error('빈 응답');
    host.innerHTML = '';
    chart = createStockChart(host, candles, { period, showVolume: true });
    if (legend) {
      legend.innerHTML = maLegend(chart.maSeries) +
        `<span class="kh-mut" style="margin-left:8px;font-size:.74rem">
          ${meta.label || ''}봉 · ${meta.source === 'DB' ? '저장됨' : '갱신됨'}</span>`;
    }
  } catch {
    if (key !== periodId) return;
    host.innerHTML = `<div class="kh-soon">
      <div class="kh-soon-t">차트를 불러오지 못했습니다</div>
      <div class="kh-soon-s">중계 서버가 꺼져 있거나 응답이 없습니다</div></div>`;
    if (legend) legend.innerHTML = '';
  }
}

/* ── 내 메모 ────────────────────────────── */
function setupMemo() {
  const box = $('kh-memo');
  if (!box) return;
  box.value = getMemo(stock.code) || '';
  box.addEventListener('input', () => setMemo(stock.code, box.value));
}

/* ── 시작 ───────────────────────────────── */
const side = mountWatchSide($('kh-side'), { activeCode: stock.code });
mountVBar($('kh-vbar'), 'watch');
const foot = mountFootStrip($('kh-foot'));

paintHead(null);
paintPeriods();
drawChart();
setupMemo();

/* 관심종목에 없는 종목도 헤더 시세는 받아온다 */
const inWatchlist = WATCHLIST.some(s => s.code === stock.code);
if (!inWatchlist) {
  fetchLivePrices([stock.code]).then(map => { if (map) paintHead(map[stock.code]); });
}

startLiveLoop({
  onIndices(indices) { foot.update(indices); },
  onPrices(prices) {
    side.update(prices);
    if (prices[stock.code]) paintHead(prices[stock.code]);
  },
});
