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
import { indexChartSvg } from './index-chart.js';
import { fetchIndexMinutes } from './data/live.js';

/* 지수 띠에 놓을 칸.
   code 가 있는 셋만 서버에서 값이 온다. 나머지는 아직 받아올 곳이 없어
   "연결 예정" 으로 남는다. 무엇을 붙이면 채워지는지 wait 에 적어 둔다.
   ─ 할 일: 해외 지수·환율·원자재를 우리 서버가 야후에서 받아 중계하기
     (한 번 부르면 13종이 한꺼번에 온다. docs/data-sources.md 참고) */
const INDEX_CELLS = [
  { code: 'KOSPI',    name: '코스피' },
  { code: 'KOSDAQ',   name: '코스닥' },
  { code: 'KOSPI200', name: '코스피200' },
  { name: '미국 USD',  wait: '야후 KRW=X' },
  { name: 'S&P 500',  wait: '야후 ^GSPC' },
  { name: '나스닥 종합', wait: '야후 ^IXIC' },
  { name: '다우존스',  wait: '야후 ^DJI' },
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
  /* 차트 아래 문구는 paintBigChart 가 맡는다.
     여기서도 건드렸더니 30초마다 서로 덮어써서 문구가 왔다 갔다 했다. */
}

/* ── 지수 띠 ─────────────────────────────
   카드를 누르면 아래 큰 차트가 그 지수로 바뀐다. */
let pickedIndex = 'KOSPI';
let lastIndices = null;

function paintMkt() {
  const el = $('kh-mkt');
  if (!el) return;
  const phase = marketPhase();
  const live = phase.id === 'regular';
  el.innerHTML = `
    <span><i class="kh-pdot ${live ? '' : 'off'}"></i>국내
      <span class="kh-chip ${live ? 'live' : ''}">${phase.label}</span>
      <b>${phase.note}</b></span>
    <span><i class="kh-pdot off"></i>해외
      <span class="kh-chip">연결 예정</span></span>`;
}

function paintStrip(indices) {
  const byCode = Object.fromEntries((indices || []).map(i => [i.code, i]));
  const host = $('kh-strip');
  if (!host) return;

  host.innerHTML = INDEX_CELLS.map(cell => {
    const i = cell.code ? byCode[cell.code] : null;
    const on = cell.code === pickedIndex;
    if (!i) {
      /* 둘을 구분해 적는다.
         받아올 곳이 아직 없는 칸  → "연결 예정" · 값은 "—"
         연결은 됐는데 안 온 칸    → "불러오는 중"
         섞어 쓰면 연결이 안 된 건지 아직 안 온 건지 알 수 없다. */
      const soon = !cell.code;
      return `<div class="kh-ix ${on ? 'is-on' : ''}" ${cell.code ? `data-idx="${cell.code}"` : ''}>
        <div class="kh-ix-h"><span class="kh-ix-n">${cell.name}</span>
          ${soon ? '<span class="kh-bd kh-bd-soon">연결 예정</span>' : ''}</div>
        <div class="kh-ix-v kh-num kh-mut"
          style="${soon ? '' : 'font-size:.9rem;font-weight:500'}"
          >${soon ? '—' : '불러오는 중'}</div>
        <div class="kh-ix-c kh-mut">${cell.wait || ''}</div>
      </div>`;
    }
    const cls = dirClass(i.changePct);
    return `<div class="kh-ix ${on ? 'is-on' : ''}" data-idx="${i.code}">
      <div class="kh-ix-h"><span class="kh-ix-n">${cell.name}</span>
        <span class="kh-bd kh-bd-on">실시간</span></div>
      <div class="kh-ix-b">
        <div>
          <div class="kh-ix-v kh-num ${cls} ${tickClass('idx:' + i.code, i.value)}"
            >${fmtNum(i.value, 2)}</div>
          <div class="kh-ix-c kh-num ${cls}">${fmtDelta(i.change, i.changePct, '', 2)}</div>
        </div>
        <div class="kh-ix-s">${sparkSvg(i.series, i.changePct >= 0, 74, 30)}</div>
      </div>
    </div>`;
  }).join('');

  host.querySelectorAll('.kh-ix[data-idx]').forEach(el =>
    el.addEventListener('click', () => {
      pickedIndex = el.dataset.idx;
      paintStrip(lastIndices);
      paintBigChart();
    }));

  /* 방금 innerHTML 을 바꿨으므로 폭이 아직 잡히지 않았다. 한 프레임 뒤에
     다시 재야 맨 왼쪽에서 '이전' 버튼이 제대로 숨는다. */
  updateStripButtons();
  requestAnimationFrame(updateStripButtons);
}

/* 좌우 이동 — 카드 폭만큼 밀어 준다. 끝에 닿으면 버튼을 숨긴다. */
function updateStripButtons() {
  const st = $('kh-strip');
  const prev = $('kh-strip-prev');
  const next = $('kh-strip-next');
  if (!st || !prev || !next) return;
  /* 딱 0 / 딱 최대가 되지 않는다. 띠에 준 1px 안쪽 여백과 스크롤 스냅 때문에
     맨 왼쪽에서도 scrollLeft 가 1 로 잡힌다 (2026-09-14 재서 확인).
     여유를 두지 않으면 '이전' 버튼이 안 숨어 첫 카드의 숫자를 가린다. */
  const EDGE = 6;
  const max = st.scrollWidth - st.clientWidth;
  prev.disabled = st.scrollLeft <= EDGE;
  next.disabled = st.scrollLeft >= max - EDGE;
}

function setupStrip() {
  const st = $('kh-strip');
  if (!st) return;
  const step = () => Math.max(262, Math.round(st.clientWidth * 0.8));
  $('kh-strip-prev')?.addEventListener('click',
    () => st.scrollBy({ left: -step(), behavior: 'smooth' }));
  $('kh-strip-next')?.addEventListener('click',
    () => st.scrollBy({ left: step(), behavior: 'smooth' }));
  st.addEventListener('scroll', updateStripButtons, { passive: true });
  window.addEventListener('resize', updateStripButtons);
}

/* 고른 지수의 큰 차트 — 당일 5분 흐름.
   시간 눈금과 지표줄을 그리려면 분 단위 값이 필요해서 따로 받아온다.
   못 받으면 60거래일 일봉으로 물러선다. */
let bigChartKey = null;

async function paintBigChart() {
  const key = pickedIndex;
  bigChartKey = key;

  const name = (INDEX_CELLS.find(c => c.code === key) || {}).name || '';
  const nameEl = $('kh-idx-name');
  if (nameEl) nameEl.textContent = name;

  const host = $('kh-big-chart');
  const foot = $('kh-big-foot');
  if (!host) return;

  const bars = await fetchIndexMinutes(key);
  if (bigChartKey !== key) return;            // 그 사이 다른 지수를 골랐다

  const svg = bars ? indexChartSvg(bars) : '';
  if (svg) {
    host.innerHTML = svg;
    if (foot) {
      foot.innerHTML = `<span>오늘 5분 흐름 · 어제 구간은 흐리게</span>
        <span>한국투자증권 실시간</span>`;
    }
    return;
  }

  /* 물러서기 — 일봉이라도 보여 준다 */
  const i = (lastIndices || []).find(x => x.code === key);
  if (!i) {
    host.innerHTML = `<div class="kh-soon"><div class="kh-soon-t">불러오는 중</div></div>`;
    return;
  }
  host.innerHTML = sparkSvg(i.series, i.changePct >= 0, 1000, 300);
  if (foot) {
    foot.innerHTML = `<span>60거래일 추이</span>
      <span class="kh-mut">당일 흐름을 불러오지 못했습니다</span>`;
  }
}

function paintIndices(indices) {
  lastIndices = indices;
  paintStrip(indices);
  paintBigChart();
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

/* 주요 일정 · 최근 공시는 관심종목 아래에 둔다 (2026-09-14 지시).
   사이드바는 시세가 들어와도 목록만 다시 그리므로 여기 넣은 것은 깜빡이지 않는다. */
if (side.slot) {
  side.slot.innerHTML = `
    <div class="kh-side-sec">
      <div class="kh-sched-h"><span>주요 일정</span><span class="kh-mut">›</span></div>
      <div class="kh-sched-i"><span class="d"></span>연결 예정 — 한국은행 경제통계</div>
      <div class="kh-sched-i"><span class="d"></span>연결 예정 — 실적 발표 일정</div>
    </div>
    <div class="kh-side-sec">
      <div class="kh-sched-h"><span>최근 공시</span><span class="kh-mut">OpenDART</span></div>
      <div class="kh-dc" id="kh-dc-all"></div>
    </div>`;
}
mountVBar($('kh-vbar'), 'watch');
const foot = mountFootStrip($('kh-foot'));

paintClock();
setInterval(paintClock, 30000);
paintMkt();
setInterval(paintMkt, 30000);
setupStrip();
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
