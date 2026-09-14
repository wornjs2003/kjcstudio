/* ==========================================================================
   첫 화면 (index.html)

   지수 · 순위 표 · 고른 종목 미리보기를 그립니다.
   값은 서버(/api/kis/*)에서 받고, 못 받으면 '—' 또는 '연결 예정' 이 남습니다.
   ========================================================================== */

import { WATCHLIST } from './data/market.js';
import { fetchCandles, createStockChart } from './chart.js';
import { color } from './theme.js';
import { fmtNum, fmtWon, fmtPct, fmtMoneyKr, fmtDelta, dirClass, marketPhase }
  from './utils/format.js';
import { mountWatchSide, mountVBar, mountFootStrip, startLiveLoop } from './components/frame.js';
import { tickClass } from './utils/tick.js';
import { mountDisclosures } from './components/disclosures.js';

/* 서버가 주는 지수 3개 + 아직 받아올 곳이 없는 것들.
   ─ 할 일: 해외 지수·환율·원자재를 우리 서버가 야후에서 받아 중계하기 */
const INDEX_CELLS = [
  { code: 'KOSDAQ',   name: '코스닥' },
  { code: 'KOSPI200', name: '코스피200' },
  { name: '나스닥',    wait: '야후 ^IXIC' },
  { name: 'S&P 500',  wait: '야후 ^GSPC' },
  { name: '다우존스',  wait: '야후 ^DJI' },
  { name: '달러 환율', wait: '야후 KRW=X' },
  { name: 'VIX',      wait: '야후 ^VIX' },
  { name: 'WTI 원유',  wait: '야후 CL=F' },
  { name: '금',       wait: '야후 GC=F' },
];

const $ = id => document.getElementById(id);
let selectedCode = WATCHLIST[0].code;

/* 마지막으로 시세를 받은 시각.
   가격이 한동안 그대로일 때가 있어서(체결이 같은 값에 머무는 구간),
   "언제 받았는지" 를 보여줘야 갱신이 돌고 있다는 걸 알 수 있다. */
let lastTickAt = null;

/* ── 작은 추이선 ─────────────────────────── */
function sparkSvg(series, isUp, w, h) {
  if (!series || series.length < 2) return '';
  const lo = Math.min(...series), hi = Math.max(...series);
  const range = Math.max(1e-9, hi - lo);
  const pts = series.map((v, i) =>
    `${(i / (series.length - 1) * w).toFixed(1)},${((1 - (v - lo) / range) * h).toFixed(1)}`);
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"
            style="width:100%;height:100%;display:block">
            <polyline points="${pts.join(' ')}" fill="none"
              stroke="${isUp ? color('up') : color('down')}"
              stroke-width="1.6" stroke-linejoin="round"/></svg>`;
}

/* ── 장 상태 · 기준 시각 ─────────────────── */
function paintClock() {
  const now = new Date();
  const p = x => String(x).padStart(2, '0');
  const phase = marketPhase(now);

  /* "· 10:05:32 받음 · 장중 (15:30까지)"
     앞쪽은 시세를 마지막으로 받은 시각(초까지), 괄호 안은 장이 언제까지인지.
     괄호는 흐리게 — 장 이름이 먼저 눈에 들어와야 한다. */
  const el = $('kh-asof');
  if (el) {
    const got = lastTickAt
      ? `${p(lastTickAt.getHours())}:${p(lastTickAt.getMinutes())}:${p(lastTickAt.getSeconds())} 받음`
      : '불러오는 중';
    el.innerHTML = `· ${got} · ${phase.label}` +
      `<span class="kh-mut"> (${phase.note})</span>`;
  }

  /* 지수는 정규장에만 산출된다. 프리마켓·애프터마켓에는 0.00% 로 멈춰 있는데,
     고장이 아니라는 걸 적어 둔다. */
  const foot = $('kh-big-foot');
  if (foot) {
    foot.innerHTML = phase.id === 'regular' || phase.id === 'closed'
      ? `<span>60거래일 추이</span><span>한국투자증권 실시간</span>`
      : `<span>60거래일 추이</span>
         <span class="kh-mut">지수는 정규장(09:00~15:30)에만 움직입니다</span>`;
  }
}

/* ── 지수 ───────────────────────────────── */
function paintIndices(indices) {
  const byCode = Object.fromEntries((indices || []).map(i => [i.code, i]));

  const kospi = byCode.KOSPI;
  if (kospi) {
    const cls = dirClass(kospi.changePct);
    $('kh-big-v').className = 'kh-big-v kh-num ' + cls + ' ' + tickClass('idx:KOSPI', kospi.value);
    $('kh-big-v').textContent = fmtNum(kospi.value, 2);
    $('kh-big-c').className = 'kh-big-c kh-num ' + cls;
    $('kh-big-c').textContent = fmtDelta(kospi.change, kospi.changePct, '', 2);
    $('kh-big-chart').innerHTML = sparkSvg(kospi.series, kospi.changePct >= 0, 300, 92);
  }

  $('kh-igrid').innerHTML = INDEX_CELLS.map(cell => {
    const i = cell.code ? byCode[cell.code] : null;
    if (!i) {
      return `<div class="kh-ig">
        <div class="kh-ig-spark"></div>
        <div class="kh-ig-txt">
          <div class="kh-ig-n">${cell.name}</div>
          <div class="kh-ig-go">실시간 시세 보기 ›</div>
          <div class="kh-ig-wait">${cell.wait || '불러오는 중'}</div>
        </div></div>`;
    }
    const cls = dirClass(i.changePct);
    return `<div class="kh-ig">
      <div class="kh-ig-spark">${sparkSvg(i.series, i.changePct >= 0, 52, 28)}</div>
      <div class="kh-ig-txt">
        <div class="kh-ig-n">${cell.name}</div>
        <div class="kh-ig-v kh-num ${cls} ${tickClass('idx:' + i.code, i.value)}">${fmtNum(i.value, 2)}</div>
        <div class="kh-ig-c kh-num ${cls}">${fmtDelta(i.change, i.changePct, '', 2)}</div>
      </div></div>`;
  }).join('');
}

/* ── 순위 표 ────────────────────────────── */
function paintRows(priceMap) {
  $('kh-rows').innerHTML = WATCHLIST.map((s, idx) => {
    const live = priceMap && priceMap[s.code];
    const cls = live ? dirClass(live.pct) : 'kh-mut';
    const value = live ? fmtMoneyKr(Math.round(live.price * live.volume / 1e8)) : '—';
    return `<tr data-code="${s.code}" class="${s.code === selectedCode ? 'is-active' : ''}">
      <td class="kh-rk">${idx + 1}</td>
      <td class="l"><span class="kh-nm">
        <span class="kh-ic" style="background:${s.brand}">${s.name.slice(0, 2)}</span>
        <b>${s.name}</b></span></td>
      <td class="kh-num"><span class="${tickClass('row:' + s.code, live && live.price)}"
        >${live ? fmtWon(live.price) : '—'}</span></td>
      <td class="kh-num ${cls}" style="font-weight:500">${live ? fmtPct(live.pct) : '—'}</td>
      <td class="kh-num">${value}</td>
      <td class="kh-num">${live ? fmtMoneyKr(live.marketCap) : '—'}</td>
      <td><span class="kh-ratio"><span class="kh-mut">연결 예정</span>
        <span class="kh-ratio-bar"></span></span></td>
      <td class="l"><span class="kh-sect">${s.sector}</span></td>
    </tr>`;
  }).join('');

  $('kh-rows').querySelectorAll('tr[data-code]').forEach(tr => {
    tr.addEventListener('click', () => selectStock(tr.dataset.code));
    tr.addEventListener('dblclick', () => {
      location.href = `./stock.html?code=${tr.dataset.code}`;
    });
  });
}

/* ── 미리보기 ───────────────────────────── */
let chartKey = null;

function paintPreview(priceMap) {
  const s = WATCHLIST.find(x => x.code === selectedCode);
  if (!s) return;
  const live = priceMap && priceMap[s.code];

  $('kh-pv-ic').style.background = s.brand;
  $('kh-pv-ic').textContent = s.name.slice(0, 2);
  $('kh-pv-n').textContent = s.name;
  $('kh-pv-link').href = `./stock.html?code=${s.code}`;

  const el = $('kh-pv-v');
  if (live) {
    el.className = 'kh-pv-v kh-num ' + dirClass(live.pct) + ' ' + tickClass('pv:' + s.code, live.price);
    el.textContent = `${fmtWon(live.price)}  ${fmtPct(live.pct)}`;
  } else {
    el.className = 'kh-pv-v kh-num kh-mut';
    el.textContent = '불러오는 중';
  }
}

async function drawPreviewChart() {
  const key = selectedCode;
  chartKey = key;
  const host = $('kh-pv-chart');
  host.innerHTML = '';
  try {
    const { candles, period } = await fetchCandles(key, '5m', 90);
    if (chartKey !== key) return;                 // 그 사이 다른 종목을 골랐다
    if (!candles.length) throw new Error('빈 응답');
    createStockChart(host, candles, { period, showVolume: true });
  } catch {
    if (chartKey !== key) return;
    host.innerHTML = `<div class="kh-soon">
      <div class="kh-soon-t">차트를 불러오지 못했습니다</div></div>`;
  }
}

function selectStock(code) {
  selectedCode = code;
  document.querySelectorAll('#kh-rows tr').forEach(tr =>
    tr.classList.toggle('is-active', tr.dataset.code === code));
  paintPreview(lastPrices);
  drawPreviewChart();
  drawPickedDisclosures();
}

/* ── 시작 ───────────────────────────────── */
let lastPrices = null;

const side = mountWatchSide($('kh-side'), { activeCode: null });
mountVBar($('kh-vbar'), 'watch');
const foot = mountFootStrip($('kh-foot'));

paintClock();
setInterval(paintClock, 30000);
paintIndices(null);
paintRows(null);
paintPreview(null);
drawPreviewChart();

/* ── 공시 ──
   서버(server/dart.py)가 5분마다 받아 두므로 화면도 같은 주기로 다시 읽는다.
   오른쪽은 감시 대상 200종목 전체, 미리보기 안쪽은 지금 고른 종목만. */
const dcAll = mountDisclosures($('kh-dc-all'), { limit: 10, showName: true });
let dcOne = null;
function drawPickedDisclosures() {
  dcOne = mountDisclosures($('kh-dc-one'),
    { code: selectedCode, limit: 6, showName: false });
}
drawPickedDisclosures();
setInterval(() => { dcAll.reload(); dcOne && dcOne.reload(); }, 5 * 60 * 1000);

startLiveLoop({
  onIndices(indices) { paintIndices(indices); foot.update(indices); },
  onPrices(prices)   {
    lastTickAt = new Date();
    lastPrices = prices;
    paintClock();                 // 받은 시각을 바로 반영
    paintRows(prices);
    side.update(prices);
    paintPreview(prices);
  },
});

/* 공지 배너 닫기 */
$('kh-notice-x')?.addEventListener('click', () => $('kh-notice')?.remove());
