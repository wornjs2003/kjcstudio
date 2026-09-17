/* ==========================================================================
   첫 화면 (index.html)

   지수 · 순위 표 · 고른 종목 미리보기를 그립니다.
   값은 서버(/api/kis/*)에서 받고, 못 받으면 '—' 또는 '연결 예정' 이 남습니다.
   ========================================================================== */

import { WATCHLIST, brandColor } from './data/market.js';
import * as lastSeen from './store/last-seen.js';
import { fetchCandles, createStockChart, maLegend } from './chart.js';
import { color } from './theme.js';
import { fmtNum, fmtWon, fmtPct, fmtMoneyKr, fmtDelta, fmtDeltaAmount, dirClass, marketPhase }
  from './utils/format.js';
import { mountWatchSide, mountVBar, mountFootStrip, startLiveLoop } from './components/frame.js';
import { iconHtml, paintIcon } from './components/stock-icon.js';
import { openModal, closeModal } from './components/modal.js';
import { loadStockMain, mountStockView } from './components/stock-view.js';
import { mountDisclosures } from './components/disclosures.js';
import { mountSchedule } from './components/schedule.js';
import { fetchIndexMinutes, fetchIndexCandles, fetchQuotes } from './data/live.js';
import { apiFetch } from './data/api.js';

/* 지수 띠에 놓을 칸.
 *
 * **다우존스는 뺐다** (2026-09-17 지시 — "받을 수 없는 지수는 메인 UI 상에서도
 * 없애고 만들지 않는다"). 증권사 두 곳 어디에도 없어서 자리만 차지하고
 * 있었다. 「아직 안 붙인 것」이 아니라 「받을 수 없는 것」이다.
 *
 *     KIS    DJI · .DJI · DJIA · INDU · DJX · US30 · DJ30 · DWJ · DIA
 *            13개 후보를 네 시장구분으로 훑었는데 전부 0
 *            (DOW 는 다우社 주식이라 30달러가 나온다)
 *     토스증권 Open API   개별 주식만 준다. 지수가 없다
 *
 * **WTI·금은 남긴다.** 받을 곳은 찾았고 거래소 신청만 하면 된다 —
 * 못 찾은 것이 아니라 아직 안 붙인 것이다. wait 에 무엇을 하면 채워지는지
 * 적어 둔다 (holdings/CLAUDE.md 데이터 규칙).
 */
const INDEX_CELLS = [
  { code: 'KOSPI',    name: '코스피',     icon: 'kr' },
  { code: 'KOSDAQ',   name: '코스닥',     icon: 'kr' },
  { code: 'KOSPI200', name: '코스피200',  icon: 'kr' },
  { code: 'KRX100',   name: 'KRX100',   icon: 'kr' },
  { code: 'USDKRW', name: '미국 USD',  icon: 'us' },
  { code: 'SPX',    name: 'S&P 500',  icon: 'us' },
  { code: 'NASDAQ', name: '나스닥 종합', icon: 'us' },
  { code: 'NDX',    name: '나스닥100',  icon: 'us' },
  { code: 'SOX',    name: '필라델피아 반도체', icon: 'us' },
  { code: 'SX5E',   name: '유로STOXX50', icon: 'eu' },
  { code: 'HSCE',   name: '홍콩H',      icon: 'hk' },
  { code: 'VIX',    name: 'VIX',      icon: 'vix' },
  /* NYMEX · COMEX 거래소를 신청하면 채워진다 (EGW00551, 2026-09-17 실측) */
  { name: 'WTI 원유',  wait: '거래소 신청 필요', icon: 'oil' },
  { name: '금',       wait: '거래소 신청 필요', icon: 'au' },
];

/* 칸 앞에 붙는 표시.
   국기는 <use> 로 꺼내 쓰고(index.html 맨 위에 정의), 나머지는 글자 배지로 만든다.
   이모지를 쓰면 윈도우에서 "KR" 같은 지역코드 글자로 나와서 직접 그렸다. */
function cellIcon(kind) {
  if (kind === 'kr' || kind === 'us') {
    return `<svg class="kh-ix-flag" viewBox="0 0 24 24" aria-hidden="true"
      ><use href="#kh-flag-${kind}"/></svg>`;
  }
  const badge = { vix: 'V', oil: '油', au: 'Au', eu: 'EU', hk: 'HK' }[kind];
  return badge ? `<span class="kh-ix-badge ${kind}" aria-hidden="true">${badge}</span>` : '';
}

const $ = id => document.getElementById(id);
let selectedCode = WATCHLIST[0].code;

/* 마지막으로 시세를 받은 시각.
   가격이 한동안 그대로일 때가 있어서(체결이 같은 값에 머무는 구간),
   "언제 받았는지" 를 보여줘야 갱신이 돌고 있다는 걸 알 수 있다. */
let lastTickAt = null;

/* ── 작은 추이선 ─────────────────────────── */
/* 작은 추이 그래프.
   색은 한국식으로 — 오름 빨강 · 내림 파랑 · 보합 검정.
   전에는 `changePct >= 0` 으로 넘겨서 0.00% 일 때도 빨강이 됐다 (2026-09-15). */
function sparkSvg(series, pct, w, h) {
  if (!series || series.length < 2) return '';
  const lo = Math.min(...series), hi = Math.max(...series);
  const range = Math.max(1e-9, hi - lo);
  const pts = series.map((v, i) =>
    `${(i / (series.length - 1) * w).toFixed(1)},${((1 - (v - lo) / range) * h).toFixed(1)}`);
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"
            style="width:100%;height:100%;display:block">
            <polyline points="${pts.join(' ')}" fill="none"
              stroke="${pct == null || pct === 0 ? color('flat')
                        : (pct > 0 ? color('up') : color('down'))}"
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

  /* 시장 현황(상승·보합·하락 종목 수)을 장 상태 바로 옆에 둔다 (2026-09-15 지시).
     지수 조회 응답에 이미 들어 있어서 따로 부르지 않는다.
     코스피 기준이다 — 코스닥을 고르면 그쪽 숫자로 바뀐다. */
  const idx = (lastIndices || []).find(x => x.code === pickedIndex)
           || (lastIndices || [])[0];
  const counts = idx && idx.up != null ? `
    <span class="kh-mkt-cnt">
      <b class="kh-up">${fmtNum(idx.up)}</b><span class="kh-mut">상승</span>
      <b class="kh-flat">${fmtNum(idx.flat)}</b><span class="kh-mut">보합</span>
      <b class="kh-down">${fmtNum(idx.down)}</b><span class="kh-mut">하락</span>
      ${idx.upperLimit ? `<span class="kh-mut">상한 ${idx.upperLimit}</span>` : ''}
      ${idx.lowerLimit ? `<span class="kh-mut">하한 ${idx.lowerLimit}</span>` : ''}
    </span>` : '';

  /* 현물 · 선물 · 야간 (2026-09-15 지시).

       현물   코스피200 지수. 이미 카드로 받고 있는 값을 그대로 쓴다
       선물   코스피200 최근월물. 지수보다 먼저 움직여 방향을 가늠하는 데 쓴다
       야간   아직 코드를 못 찾았다. 자리만 만들어 둔다

     선물은 월물 이름("F 202612")을 함께 보여줘 어느 월물인지 알 수 있게 한다. */
  const spot = (lastIndices || []).find(x => x.code === 'KOSPI200');
  const f = (lastIndices || {}).futures;

  const one = (label, value, pct, change, note) => `
    <span class="kh-fut-1">
      <span class="kh-mut">${label}</span>
      ${value == null
        ? '<span class="kh-mut">연결 예정</span>'
        : `<b class="kh-num ${dirClass(pct)}">${fmtNum(value, 2)}</b>
           <span class="kh-num ${dirClass(pct)}">${fmtPct(pct)}</span>`}
      ${note ? `<span class="kh-mut">${note}</span>` : ''}
    </span>`;

  const futures = `
    <span class="kh-mkt-fut">
      ${one('현물', spot ? spot.value : null, spot && spot.changePct)}
      ${one('선물', f ? f.price : null, f && f.changePct, null, f ? f.name : '')}
      ${one('야간', null, null, null, '코드 찾는 중')}
    </span>`;

  el.innerHTML = `
    <span><i class="kh-pdot ${live ? '' : 'off'}"></i>국내
      <span class="kh-chip ${live ? 'live' : ''}">${phase.label}</span>
      <b class="kh-mkt-note">${phase.note}</b></span>
    ${counts}${futures}`;
}

/* 카드에 붙일 표시. 무엇을 보고 있는지가 한눈에 들어와야 한다. */
function badgeFor(i) {
  if (i.market === 'overseas') {
    const d = i.asOf || '';
    /* 20260914 → "09.14 종가" */
    const label = d.length === 8 ? `${d.slice(4, 6)}.${d.slice(6, 8)} 종가` : '해외장';
    return { live: false, text: label };
  }
  /* 국내는 셋으로만 나눈다 (2026-09-15 지시).

       실시간   09:00~15:30  KRX 정규장. 값이 계속 움직인다
       넥장     08:00~08:50 · 15:30~20:00  넥스트레이드에서만 거래된다
       장마감   그 밖. 값이 멈춰 있다

     08:50~09:00 은 프리마켓이 끝나고 정규장 전이라 거래가 없다. 장마감으로 묶는다.
     이 구분은 시세를 어느 시장 기준으로 받는지와 짝이 맞는다
     (정규장은 KRX, 그 밖은 통합 — CLAUDE.md 의 시세 표기 규칙). */
  const phase = marketPhase();
  if (phase.id === 'regular') return { live: true, text: '실시간' };
  if (phase.id === 'pre' || phase.id === 'after') return { live: false, text: '넥장' };
  return { live: false, text: '장마감' };
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
        <div class="kh-ix-h">${cellIcon(cell.icon)}<span class="kh-ix-n">${cell.name}</span>
          ${soon ? '<span class="kh-bd kh-bd-soon">연결 예정</span>' : ''}</div>
        <div class="kh-ix-v kh-num kh-mut"
          style="${soon ? '' : 'font-size:.9rem;font-weight:500'}"
          >${soon ? '—' : '불러오는 중'}</div>
        <div class="kh-ix-c kh-mut">${cell.wait || ''}</div>
      </div>`;
    }
    const cls = dirClass(i.changePct);
    /* 언제 기준 값인지 적는다.
       국내는 지금 장이 열려 있으면 실시간, 아니면 장 상태 그대로.
       해외는 국내 낮 시간에 닫혀 있으므로 받은 값의 날짜를 적는다.
       전에는 값만 있으면 무조건 "실시간" 이라 어제 종가도 실시간으로 보였다
       (2026-09-15 지적). */
    const badge = badgeFor(i);
    return `<div class="kh-ix ${on ? 'is-on' : ''}" data-idx="${i.code}">
      <div class="kh-ix-h">${cellIcon(cell.icon)}<span class="kh-ix-n">${cell.name}</span>
        <span class="kh-bd ${badge.live ? 'kh-bd-on' : (badge.text === '넥장' ? 'kh-bd-nx' : '')}"
          >${badge.text}</span></div>
      <div class="kh-ix-b">
        <div>
          <div class="kh-ix-v kh-num ${cls}"
            >${fmtNum(i.value, 2)}</div>
          <div class="kh-ix-c kh-num ${cls}">${fmtDelta(i.change, i.changePct, '', 2)}</div>
        </div>
        <div class="kh-ix-s">${sparkSvg(i.series, i.changePct, 74, 30)}</div>
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

/* ── 고른 지수의 큰 차트 ─────────────────────
   기간을 고를 수 있다 (2026-09-15 지시).

     5분  당일 흐름. 선으로 그린다 — 5분 간격이라 캔들로 그리면 몸통이 거의 없다
     일·주·월·년  캔들. 종목 화면과 같은 그림(js/chart.js)을 쓴다

   선 그림은 어제 구간을 눌러 담고 시간에 비례해 자리를 잡는 등 당일용으로
   따로 만든 것이라, 5분봉에서만 쓴다. */
const INDEX_PERIODS = [
  { id: '5m', label: '5분' },
  { id: 'D',  label: '일'  },
  { id: 'W',  label: '주'  },
  { id: 'M',  label: '월'  },
  { id: 'Y',  label: '년'  },
];
let indexPeriod = '5m';
let bigChart = null;          // 캔들일 때 만들어 둔 것 (지울 때 필요)
let bigChartKey = null;

function paintIndexPeriods() {
  const host = $('kh-idx-per');
  if (!host) return;
  host.innerHTML = INDEX_PERIODS.map(p =>
    `<button data-p="${p.id}" class="${p.id === indexPeriod ? 'is-on' : ''}">${p.label}</button>`
  ).join('');
  host.querySelectorAll('button').forEach(b =>
    b.addEventListener('click', () => {
      indexPeriod = b.dataset.p;
      paintIndexPeriods();
      paintBigChart();
    }));
}

/* 캔들을 지운다. 새로 그리기 전과 선 그림으로 돌아갈 때 부른다. */
function dropBigChart() {
  if (bigChart) { bigChart.destroy(); bigChart = null; }
}

async function paintBigChart() {
  const key = pickedIndex + ':' + indexPeriod;
  bigChartKey = key;

  const name = (INDEX_CELLS.find(c => c.code === pickedIndex) || {}).name || '';
  const nameEl = $('kh-idx-name');
  if (nameEl) nameEl.textContent = name;

  const host = $('kh-big-chart');
  const foot = $('kh-big-foot');
  if (!host) return;

  /* 다섯 기간 모두 캔들로 그린다 (2026-09-15 지시).
     5분봉만 선으로 두었더니 "왜 캔들이 아니냐" 는 물음을 받았다.
     전일 종가선은 캔들에서도 살려 둔다 — 오늘 오르내림의 기준선이다. */
  const bars = indexPeriod === '5m'
    ? await fetchIndexMinutes(pickedIndex)
    : await fetchIndexCandles(pickedIndex, indexPeriod);
  if (bigChartKey !== key) return;          // 그 사이 다른 것을 골랐다

  if (!bars) {
    dropBigChart();
    host.innerHTML = `<div class="kh-soon">
      <div class="kh-soon-t">차트를 불러오지 못했습니다</div></div>`;
    return;
  }

  dropBigChart();
  host.innerHTML = '';
  /* 지수는 거래량을 함께 보여줄 만한 값이 아니라 끈다.
     ts 는 일봉 YYYYMMDD · 분봉 YYYYMMDDHHMM 로 종목 캔들과 같은 형식이다. */
  bigChart = createStockChart(host, bars, { period: indexPeriod, showVolume: false });

  /* 5분봉에는 전일 종가선을 그어 둔다. 오늘 올랐는지 내렸는지의 기준이다.
     어제 마지막 봉의 종가가 그 값이다. */
  if (indexPeriod === '5m' && bigChart && bigChart.candleSeries) {
    const today = bars[bars.length - 1].ts.slice(0, 8);
    const firstToday = bars.findIndex(b => b.ts.slice(0, 8) === today);
    if (firstToday > 0) {
      try {
        bigChart.candleSeries.createPriceLine({
          price: bars[firstToday - 1].close,
          color: color('text-muted'),
          lineWidth: 1,
          lineStyle: 2,               // 점선
          axisLabelVisible: true,
          title: '전일',
        });
      } catch { /* 라이브러리 버전이 다르면 선만 생략한다 */ }
    }
  }

  if (foot) {
    const label = (INDEX_PERIODS.find(p => p.id === indexPeriod) || {}).label || '';
    /* 이동평균 범례를 함께 둔다. 어느 선이 그려졌는지, 봉이 모자라 못 그린
       선이 무엇인지 여기서 보인다 (2026-09-16). */
    const ma = bigChart ? maLegend(bigChart.maSeries) : '';
    foot.innerHTML = indexPeriod === '5m'
      ? `<span>${ma} · 점선은 전일 종가</span><span>한국투자증권 실시간</span>`
      : `<span>${ma} · ${label}봉 ${bars.length}개</span><span>한국투자증권</span>`;
  }
}

function paintIndices(indices) {
  lastIndices = indices;
  paintStrip(indices);
  paintBigChart();
  paintMkt();          // 상승·하락 종목 수가 여기 들어 있다
  paintYearRange();
}

/* 연중 최저·최고. 52주가 아니라 '올해 들어' 기준이라 그렇게 적는다.
   지수 조회 응답에 날짜까지 함께 온다. */
function paintYearRange() {
  const el = $('kh-year-range');
  if (!el) return;
  const i = (lastIndices || []).find(x => x.code === pickedIndex);
  if (!i || i.yearHigh == null) { el.textContent = '불러오는 중'; return; }
  const day = d => (d && d.length === 8) ? `${d.slice(4, 6)}.${d.slice(6, 8)}` : '';
  const cur = i.value;
  const lo = i.yearLow, hi = i.yearHigh;
  const at = Math.max(0, Math.min(1, (cur - lo) / Math.max(1e-9, hi - lo)));
  el.innerHTML = `
    <div class="kh-yr">
      <span class="kh-num kh-down">${fmtNum(lo, 2)}</span>
      <span class="kh-yr-bar"><i style="left:calc(${(at * 100).toFixed(1)}% - 5px)"></i></span>
      <span class="kh-num kh-up">${fmtNum(hi, 2)}</span>
    </div>
    <div class="kh-mut" style="margin-top:6px">
      ${i.name} · 최저 ${day(i.yearLowDate)} · 최고 ${day(i.yearHighDate)}</div>`;
}

/* ── 순위 표 ────────────────────────────── */
/* ── 순위표 ─────────────────────────────
   코스피 시가총액 상위 200종목. 목록은 서버가 하루 한 번 받아 DB 에 넣어 둔 것을
   읽는다 (공시 감시 대상과 같은 목록이다).

   **줄은 200개를 처음부터 다 깔고, 시세는 보이는 것만 받는다.**
   그래야 스크롤바 길이가 처음부터 맞고, 위로 올리든 아래로 내리든 그 자리 것이
   채워진다. "더 보기" 로 끊어 붙이면 스크롤이 중간에 걸리고, 위로 올라갔을 때
   할 일이 없어진다 (2026-09-14 지시).

   200종목 시세를 한꺼번에 받으면 한국투자증권을 200번 불러야 한다. 보이는 것은
   열 몇 개뿐이라 그 몫만 받는다. */

let universe = null;        // [{code, name, rank, cap}]

/* 화면이 함께 보는 시세 한 곳.

   전에는 관심 사이드바와 순위표가 따로 받았다. 조회 방식도 주기도 달라서
   같은 삼성전자인데 두 자리의 숫자가 어긋났다 (8종목 중 2개가 달랐다,
   2026-09-14 확인). 어느 쪽이 받든 여기에 모으고 두 화면이 이것을 쓴다. */
let rowPrices = {};
const asked = new Set();          // 이미 부탁한 종목 (두 번 부르지 않게)

/* 200종목 목록을 받는다.

   들어오자마자 빈 표를 보여주지 않으려고, 지난번에 받아둔 것이 있으면
   그것부터 깔고 새로 받는다. 목록(이름·순위·시가총액)은 하루에 한 번
   바뀌므로 몇 시간 묵어도 쓸 만하다 — 그래서 slow 로 저장한다.
   시세는 여기 들어 있지 않다. 빈 칸으로 깔리고 곧 채워진다. */
async function loadUniverse() {
  const kept = lastSeen.load('universe');
  if (kept) universe = kept.value;

  try {
    const r = await apiFetch('/api/dart/universe', { cache: 'no-store' });
    if (!r) return null;   // 로그인이 풀렸다
    const j = await r.json();
    if (j && j.ok && Array.isArray(j.data) && j.data.length) {
      universe = j.data;
      lastSeen.save('universe', j.data, { slow: true });
      return;
    }
  } catch { /* 아래에서 관심종목으로 물러선다 */ }
  if (!kept) universe = null;      // 받아둔 것도 없으면 관심종목으로 간다
}

/* 시가총액은 목록(dart_universe)이 갖고 있다. 네이버 시총 순위에서 온 값이고
   단위는 억원이라 fmtMoneyKr 이 그대로 받는다. */
function capOf(code) {
  if (!universe) return null;
  const hit = universe.find(x => x.code === code);
  return hit ? hit.cap : null;
}

function rowList() {
  if (!universe) return WATCHLIST.map((s, i) => ({ ...s, rank: i + 1 }));
  return universe.map(x => ({
    code: x.code, name: x.name, sector: '',
    brand: brandColor(x.code, x.name), rank: x.rank,
  }));
}

function paintRows(priceMap) {
  const list = rowList();
  $('kh-rows').innerHTML = list.map(s => {
    const live = priceMap && priceMap[s.code];
    const cls = live ? dirClass(live.pct) : 'kh-mut';
    /* 거래대금은 멀티 조회가 실제 값(value)을 준다. 없으면 현재가×거래량으로 어림한다. */
    const value = live
      ? fmtMoneyKr(Math.round((live.value ?? live.price * live.volume) / 1e8))
      : '—';
    return `<tr data-code="${s.code}" class="${s.code === selectedCode ? 'is-active' : ''}">
      <td class="kh-rk">${s.rank}</td>
      <td class="l"><span class="kh-nm">
        ${iconHtml(s)}
        <b>${s.name}</b></span></td>
      <td class="kh-num"><span
        >${live ? fmtWon(live.price) : '···'}</span></td>
      <td class="kh-num ${cls}">${live ? fmtDeltaAmount(live.amt) : '—'}</td>
      <td class="kh-num ${cls}" style="font-weight:500">${live ? fmtPct(live.pct) : '—'}</td>
      <td class="kh-num">${value}</td>
      <td class="kh-num">${capOf(s.code) != null ? fmtMoneyKr(capOf(s.code)) : '—'}</td>
      <td><span class="kh-ratio"><span class="kh-mut">연결 예정</span>
        <span class="kh-ratio-bar"></span></span></td>
      <td class="l"><span class="kh-sect kh-mut">연결 예정</span></td>
    </tr>`;
  }).join('');

  /* 마우스를 올리면 미리보기가 바뀌고, 한 번 누르면 모달이 뜬다
     (2026-09-16 지시).

       올림   가볍게 훑어보기 — 오른쪽 미리보기가 그 종목으로
       클릭   자세히 보기 — 모달

     전에는 한 번이 「고르기」, 두 번이 「열기」였는데 **만든 사람 말고는
     두 번 누를 생각을 안 한다.** 고르기는 올림 쪽으로 옮겼다. */
  $('kh-rows').querySelectorAll('tr[data-code]').forEach(tr => {
    tr.addEventListener('click', () => {
      selectStock(tr.dataset.code);
      openStockModal(tr.dataset.code);
    });
    if (HOVER_OK) {
      tr.addEventListener('mouseenter', () => hoverPreview(tr.dataset.code));
      tr.addEventListener('mouseleave', cancelHoverPreview);
    }
  });
  watchRows();
  paintRowFoot();
}

function paintRowFoot() {
  const host = $('kh-more');
  if (!host) return;
  const total = rowList().length;
  const got = Object.keys(rowPrices).length;
  host.innerHTML = got >= total
    ? `<span class="kh-mut">${total}종목</span>`
    : `<span class="kh-mut">${total}종목 · 보이는 것부터 채웁니다 (${got})</span>`;
}

/* 지금 상자 안에 보이는 줄을 직접 잰다.

   처음에는 IntersectionObserver 를 썼는데, 스크롤한 뒤 새 줄을 잡아내지 못했다
   (100위가 보이는데 1~17위만 채워졌다, 2026-09-14 확인). 원인을 더 파는 대신
   자리를 직접 재는 쪽으로 바꿨다. 줄이 200개뿐이고 스크롤이 멈춘 뒤에만 재므로
   부담이 없고, 무엇이 보이는지 눈으로 확인하기도 쉽다. */
const LOOK_AHEAD = 400;      // 화면 밖 이만큼까지 미리 받아 둔다
/* 갱신 주기는 한국투자증권 한도가 아니라 **Cloudflare 무료 한도**가 정한다
   (2026-09-15 지시 — "우선 안 죽게 넉넉하게").

   전에는 KIS 초당 20건만 보고 0.2초로 잡았다. 그런데 화면이 워커를 부르는
   횟수는 따로 센다. 무료 요금제는 **하루 10만 요청**이고, 넘으면 Error 1027 로
   사이트가 통째로 죽는다.

     장중 6.5시간 = 23,400초

     전            후
     ─────────────────────────────────────────────────
     순위표  5.000    1.000  건/초   ROW_REFRESH_MS 200→1000, 묶음 5→2
     지수    1.000    0.500  건/초   indexMs 1000→2000
     큰 차트 0.033    0.017  건/초   INDEX_CHART_MS 30000→60000
     공시    0.007    0.007  건/초   그대로
     ─────────────────────────────────────────────────
     합계    6.040    1.524  건/초
     장중    141,000  35,700 건      한도 10만 대비 141% → 36%

   탭을 두 장 열어도 71% 다. 전에는 한 장으로 5.2시간이면 바닥났다.

   **주기를 바꿀 때는 이 표를 다시 계산해서 커밋 메시지에 적을 것.**
   0.2초로 두었던 것도 계산을 안 해서 생긴 일이다. */
const ROW_REFRESH_MS = 1000;
const INDEX_CHART_MS = 60000;   // 큰 차트. 분봉이 5분 간격이라 1분이면 넉넉하다

function visibleCodeList() {
  const box = $('kh-rank-scroll');
  const body = $('kh-rows');
  if (!box || !body) return [];
  const br = box.getBoundingClientRect();
  const top = br.top - LOOK_AHEAD;
  const bottom = br.bottom + LOOK_AHEAD;
  const out = [];
  for (const tr of body.children) {
    const r = tr.getBoundingClientRect();
    if (r.bottom >= top && r.top <= bottom) out.push(tr.dataset.code);
    else if (r.top > bottom) break;          // 아래로는 더 볼 것 없다
  }
  return out;
}

function watchRows() {
  const box = $('kh-rank-scroll');
  if (!box) return;
  if (!box.dataset.bound) {
    box.addEventListener('scroll', scheduleFetch, { passive: true });
    window.addEventListener('resize', scheduleFetch);
    box.dataset.bound = '1';
  }
  scheduleFetch();
}

/* 스크롤 중에는 계속 바뀐다. 멈춘 뒤 한 번만 부른다.
   움직일 때마다 부르면 같은 종목을 몇 번씩 묻게 된다. */
let fetchTimer = null;
function scheduleFetch() {
  clearTimeout(fetchTimer);
  fetchTimer = setTimeout(fetchVisible, 180);
}

const PRICE_CHUNK = 30;
let fetching = false;

async function fetchVisible() {
  if (fetching) return;
  /* 다른 탭을 보고 있으면 부르지 않는다. 창을 여러 개 띄워 두면 그만큼
     호출이 곱해지고, 정작 보고 있는 창의 차례가 뒤로 밀린다 (2026-09-14 지시). */
  if (document.hidden) return;
  /* 관심종목은 늘 함께 받는다. 오른쪽 사이드바에 계속 떠 있으므로,
     빼면 그쪽만 옛 값으로 남아 순위표와 어긋난다. */
  const watch = WATCHLIST.map(s => s.code);
  const visible = [...new Set([...watch, ...visibleCodeList()])];
  const want = visible.filter(c => !asked.has(c));
  if (!want.length) return;
  fetching = true;
  try {
    for (let i = 0; i < want.length; i += PRICE_CHUNK) {
      const chunk = want.slice(i, i + PRICE_CHUNK);
      chunk.forEach(c => asked.add(c));
      const map = await fetchQuotes(chunk);
      if (!map) { chunk.forEach(c => asked.delete(c)); continue; }  // 실패하면 다시 묻게
      applyPrices(map);
    }
  } finally {
    fetching = false;
    /* 받는 동안 더 스크롤했을 수 있다. 남은 것이 있으면 한 번 더 돈다. */
    if (visibleCodeList().some(c => !asked.has(c))) scheduleFetch();
  }
}

/* 새로 받은 값을 모으고 양쪽 화면에 반영한다. */
function applyPrices(map) {
  if (!map) return;
  rowPrices = { ...rowPrices, ...map };
  /* 다시 들어왔을 때 빈 칸부터 시작하지 않도록 남겨 둔다.

     frame.js 도 같은 키에 저장한다. 거기는 관심종목 8개뿐이고 여기는
     순위표 200종목까지 모여 있어, 둘 다 합쳐서 넣도록 해 두었다.
     어느 쪽이 나중에 쓰든 값이 줄지 않는다. */
  lastSeen.save('prices', rowPrices);
  updateRowCells(map);
  side.update(rowPrices);          // 관심 사이드바
  paintPreview(rowPrices);         // 옆의 미리보기 카드
}

/* 값이 들어온 줄만 고쳐 쓴다. 표를 통째로 다시 그리면 스크롤 위치가 튀고
   지켜보던 줄도 전부 다시 걸어야 한다. */
const lastShown = {};        // 줄마다 마지막으로 그린 값

/* 한 번에 받은 것을 한꺼번에 그리지 않고 위에서 아래로 조금씩 밀어 준다.
   30줄이 동시에 번쩍이면 눈이 어디를 봐야 할지 모른다. 위에서부터 물결처럼
   번지면 무엇이 바뀌었는지 따라가기 쉽다 (2026-09-14 지시).

   값이 늦게 보이는 것은 아니다. 받은 값은 이미 갖고 있고, 화면에 칠하는
   순서만 미룬다. */
const STAGGER_MS = 14;        // 줄 사이 간격
const STAGGER_MAX = 150;      // 아무리 많아도 이 시간 안에는 다 칠한다
                              // (한 묶음이 6줄쯤이라 0.2초 주기 안에 여유롭게 끝난다)

function updateRowCells(map) {
  /* 실제로 값이 바뀐 줄만 추린다.
     1초(나중에는 0.2초)마다 받는데 대부분은 그 사이 움직이지 않는다.
     그래도 매번 고쳐 쓰면 화면만 바쁘고 깜빡임도 의미 없이 계속 돈다. */
  const changed = [];
  for (const [code, live] of Object.entries(map)) {
    if (!live) continue;
    const stamp = `${live.price}|${live.pct}|${live.volume}|${live.value}`;
    if (lastShown[code] === stamp) continue;
    lastShown[code] = stamp;
    changed.push([code, live]);
  }
  if (!changed.length) { paintRowFoot(); return; }

  /* 화면에 보이는 순서(위→아래)대로 칠한다 */
  const order = [...$('kh-rows').children].map(tr => tr.dataset.code);
  changed.sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]));

  const step = Math.min(STAGGER_MS, STAGGER_MAX / changed.length);
  changed.forEach(([code, live], i) => {
    if (i === 0) { paintOneRow(code, live); return; }
    setTimeout(() => paintOneRow(code, live), i * step);
  });
  paintRowFoot();
}

function paintOneRow(code, live) {
  {
    const tr = $('kh-rows').querySelector(`tr[data-code="${code}"]`);
    if (!tr || !live) return;
    const cls = dirClass(live.pct);
    tr.children[2].innerHTML =
      `<span>${fmtWon(live.price)}</span>`;
    tr.children[3].className = 'kh-num ' + cls;
    tr.children[3].textContent = fmtDeltaAmount(live.amt);
    tr.children[4].className = 'kh-num ' + cls;
    tr.children[4].style.fontWeight = '500';
    tr.children[4].textContent = fmtPct(live.pct);
    tr.children[5].textContent =
      fmtMoneyKr(Math.round((live.value ?? live.price * live.volume) / 1e8));
    /* 시가총액은 멀티 조회에 없다. 목록을 받을 때 함께 온 값을 쓴다. */
    const cap = capOf(code);
    tr.children[6].textContent = cap != null ? fmtMoneyKr(cap) : '—';
  }
}

/* ── 돌아가며 갱신 ──────────────────────
   보이는 종목을 다섯 묶음으로 나눠 0.2초마다 한 묶음씩 다시 받는다.
   전체는 1초에 한 바퀴 돈다 (2026-09-14 지시).

   한꺼번에 받아 한꺼번에 칠하면 1초마다 화면 전체가 번쩍인다. 나눠 돌리면
   종목별로 차례차례 깜빡여서 어디가 움직였는지 눈에 들어온다.
   호출은 0.2초마다 1건 = 초당 5건으로, 한국투자증권 한도(초당 20건)의 1/4 이다.

   받은 값은 applyPrices 가 순위표·관심 주식·미리보기 세 곳에 함께 넣는다. */
/* 묶음을 5 → 2 로 줄였다. 간격이 0.2초에서 1초가 되었으니, 묶음까지 그대로면
   전체 한 바퀴가 5초가 된다. 2 로 하면 2초에 한 바퀴다.
   한 묶음이 커져도 워커가 30종목씩 묶어 부르므로 KIS 호출은 거의 안 는다. */
const ROTATE_GROUPS = 2;
let rotateAt = 0;
let rotating = false;

async function rotateTick() {
  if (document.hidden || rotating) return;
  const watch = WATCHLIST.map(x => x.code);
  const codes = [...new Set([...watch, ...visibleCodeList()])];
  if (!codes.length) return;

  const size = Math.ceil(codes.length / ROTATE_GROUPS);
  const start = (rotateAt % ROTATE_GROUPS) * size;
  rotateAt++;
  const chunk = codes.slice(start, start + size);
  if (!chunk.length) return;

  rotating = true;
  try {
    applyPrices(await fetchQuotes(chunk));
  } finally {
    rotating = false;
  }
}

/* 다른 탭에 갔다 돌아오면 곧바로 한 번 받는다.
   다음 차례까지 기다리면 멈춘 값을 한동안 보게 된다. */
document.addEventListener('visibilitychange', () => {
  if (document.hidden) return;
  asked.clear();
  scheduleFetch();
  paintBigChart();        // 그 사이 장이 움직였을 수 있다
});

/* ── 미리보기 ───────────────────────────── */
let chartKey = null;

/** 코드로 종목을 찾는다. **순위표에 뜨는 것을 먼저 본다.**
 *
 * 순위표(rowList)는 수백 개인데 WATCHLIST 는 관심종목 여덟뿐이다. 좁은 쪽만
 * 보면 관심종목이 아닌 줄에서 못 찾고 조용히 빠져나간다 — 그래서 마우스를
 * 올려도 이름·아이콘이 안 바뀌고 차트만 바뀌었다 (2026-09-17).
 *
 * 찾는 자리가 둘이라 한쪽만 넓은 목록을 보고 있었다. 한 곳에 모은다.
 */
function findStock(code) {
  return rowList().find(s => s.code === code)
      || WATCHLIST.find(s => s.code === code)
      || null;
}

function paintPreview(priceMap) {
  const s = findStock(selectedCode);
  if (!s) return;
  const live = priceMap && priceMap[s.code];

  paintIcon($('kh-pv-ic'), s);
  $('kh-pv-n').textContent = s.name;
  /* 「자세히 ›」 는 모달을 연다. 주소는 남겨 둔다 — 가운데 단추로 눌러
     새 탭에서 열거나 링크를 복사하는 길이 막히지 않게 한다. */
  const link = $('kh-pv-link');
  link.href = `./stock.html?code=${s.code}`;
  link.onclick = e => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    openStockModal(s.code);
  };

  const el = $('kh-pv-v');
  if (!live) {
    el.className = 'kh-pv-v kh-num kh-mut';
    el.textContent = '불러오는 중';
    return;
  }

  /* 값이 그대로면 손대지 않는다. 0.2초마다 받는데 매번 클래스를 다시 붙이면
     깜빡임이 계속 돌아 숫자가 쉬지 않고 흔들린다 (2026-09-14 지적). */
  const stamp = `${s.code}|${live.price}|${live.pct}`;
  if (pvShown === stamp) return;
  pvShown = stamp;

  el.className = 'kh-pv-v kh-num ' + dirClass(live.pct);
  el.textContent = `${fmtWon(live.price)}  ${fmtPct(live.pct)}`;
}

let pvShown = null;

/* 지금 그려져 있는 미리보기 차트.
 *
 * **반드시 destroy 해야 한다.** innerHTML 을 비우면 그림은 사라지지만
 * 차트 객체는 살아서 크기 감시와 그리기를 계속한다. 마우스로 종목을
 * 옮길 때마다 하나씩 쌓여, 어느 순간부터 **새 차트가 아예 안 그려졌다**
 * (2026-09-17 — "내렸다가 보는데 안나오는 종목들이 있고 다시 위로 올려서
 * 삼성전자 볼려고 하니까 안나온다").
 *
 * 큰 차트(dropBigChart)와 종목 화면(stock-view)은 처음부터 정리하고
 * 있었는데 여기만 빠져 있었다. */
let previewChart = null;

function dropPreviewChart() {
  if (previewChart) { previewChart.destroy(); previewChart = null; }
}

async function drawPreviewChart() {
  const key = selectedCode;
  chartKey = key;
  const host = $('kh-pv-chart');
  dropPreviewChart();
  host.innerHTML = '';
  try {
    const { candles, period } = await fetchCandles(key, '5m', 90);
    if (chartKey !== key) return;                 // 그 사이 다른 종목을 골랐다
    if (!candles.length) throw new Error('빈 응답');
    /* 기다리는 사이에 다른 차트가 그려졌을 수 있다. 치우고 시작한다 */
    dropPreviewChart();
    host.innerHTML = '';
    previewChart = createStockChart(host, candles, { period, showVolume: true });
  } catch {
    if (chartKey !== key) return;
    dropPreviewChart();
    host.innerHTML = `<div class="kh-soon">
      <div class="kh-soon-t">차트를 불러오지 못했습니다</div></div>`;
  }
}

/* ── 마우스를 올리면 미리보기가 바뀐다 (2026-09-16 지시) ──
 *
 * **머무를 때만 바꾼다.** 지나가기만 한 줄까지 받아오면 목록을 한 번
 * 훑을 때 종목 수만큼 요청이 나간다. 오늘 배포본이 터진 것이 동시 요청
 * 때문이었고, 5분봉은 서버에 캐시가 없어 부를 때마다 KIS 로 간다.
 * (받아온 봉은 chart.js 가 60초 쥐고 있다 — 같은 종목에 다시 올리면 안 부른다.)
 *
 * 목록 밖으로 나가면 **마지막 것을 그대로 둔다.** 되돌리면 그때 또 부른다.
 */
const HOVER_DELAY_MS = 250;

/* 마우스가 있는 기기에서만. 터치 기기는 hover 가 없거나 한 번 누를 때
   hover 로 잡혔다가 클릭으로 이어져서, 미리보기만 바뀌고 모달이 안 열릴 수 있다. */
const HOVER_OK = window.matchMedia && window.matchMedia('(hover: hover)').matches;

let hoverTimer = null;

function hoverPreview(code) {
  if (!code || code === selectedCode) return;
  clearTimeout(hoverTimer);
  hoverTimer = setTimeout(() => selectStock(code), HOVER_DELAY_MS);
}

function cancelHoverPreview() {
  clearTimeout(hoverTimer);
  hoverTimer = null;
}

/* ── 종목 모달 ───────────────────────────
   목록에서 종목을 눌렀을 때 페이지를 옮기지 않고 그 자리에 띄운다
   (2026-09-16 지시). 담기는 것은 stock.html 의 본문 그대로다 —
   마크업도 그리는 코드도 한 곳에만 둔다.

   시세 루프를 새로 돌리지 않는다. 이 화면이 이미 돌고 있으므로 그 값을
   넘겨준다. 같은 화면에서 루프가 둘이 되면 KIS 를 겹쳐 부르게 되고,
   2026-09-16 에 그것으로 서버가 터졌다. */
let stockModal = null;

/* 다른 종목으로 갈아타는 중인가.
   새 모달을 열면 openModal 이 옛 모달부터 닫는데, 그때 옛 모달의 onClose 가
   주소까지 되돌리면 방금 밀어 넣은 새 종목을 도로 뱉는다. 갈아타는 동안에는
   주소를 새 모달에 맡긴다. */
let switchingStock = false;

/* 브라우저가 히스토리를 이미 옮겼나 (뒤로가기·앞으로가기).
   그 경우 닫으면서 back() 을 또 부르면 **한 칸 더 나가 페이지를 떠난다.**
   주소도 브라우저가 이미 바꿔 놓았으므로 손댈 것이 없다. */
let historyMoved = false;

/** 주소에서 ?code= 만 뺀다. 다른 값이 붙어 있어도 건드리지 않는다. */
function dropCodeFromUrl() {
  const u = new URL(location.href);
  if (!u.searchParams.has('code')) return;
  u.searchParams.delete('code');
  history.replaceState(null, '', u.pathname + u.search + u.hash);
}

async function openStockModal(code, { push = true } = {}) {
  const stock = findStock(code);
  if (!stock || (stockModal && stockModal.code === code)) return;

  let main;
  try {
    main = await loadStockMain();
  } catch (e) {
    /* 본문을 못 받으면 예전처럼 페이지를 옮긴다. 아무 일도 안 일어나는 것보다 낫다 */
    location.href = `./stock.html?code=${code}`;
    return;
  }

  /* 이 모달이 히스토리에 항목을 **밀어 넣었나**. 닫을 때 뒤로 갈지,
     주소만 털지를 가른다. history.state 로는 알 수 없다 — 그 값은 지금
     어디인지를 말할 뿐 내가 밀어 넣었는지를 말하지 않는다 (2026-09-16). */
  const pushedHere = push;
  if (push) history.pushState({ stock: code }, '', `?code=${code}`);

  switchingStock = true;
  const { body } = openModal({
    label: `${stock.name} 종목 정보`,
    /* 양옆 서랍. 처음에는 접혀 있고, 한 번 펼치면 기억한다 (2026-09-16 지시).
       key 는 펼친 상태를 적어 두는 이름이라 화면 글자와 따로 둔다 —
       이름을 바꿔도 펼쳐둔 것이 풀리지 않는다. */
    drawers: {
      left:  { key: 'stock-memo', label: '내 메모' },
      right: { key: 'stock-news', label: '뉴스 · 공시' },
    },
    onToggle() {
      /* 모달 폭이 바뀌었으니 차트도 다시 재야 한다. 캔버스는 CSS 로 늘어나지
         않아서, 이 줄이 없으면 차트만 옛 폭으로 남는다. */
      if (stockModal) stockModal.view.resize();
    },
    onClose() {
      if (stockModal && stockModal.code === code) {
        stockModal.view.destroy();
        stockModal = null;
      }

      /* 갈아타는 중이면 주소는 새 모달이 들고 있다. 여기서 건드리면 안 된다 */
      if (switchingStock) return;

      /* 뒤로가기로 닫힌 것이면 히스토리도 주소도 이미 제자리다 */
      if (historyMoved) return;

      if (pushedHere) {
        /* 목록에서 연 것이다. 되돌아갈 자리가 있다 */
        history.back();
      } else {
        /* 주소로 바로 들어왔거나 뒤로가기로 열린 것이다. 되돌아갈 자리가
           없으므로 back() 하면 **모달이 아니라 페이지를 떠난다.**
           주소에서 ?code= 만 턴다 — 안 그러면 새로고침 때 또 열린다. */
        dropCodeFromUrl();
      }
    },
  });
  switchingStock = false;

  body.appendChild(main);
  addModalActions(main, code);

  const view = mountStockView(main, stock, { onBack: closeModal });
  stockModal = { code, view };
  view.paint(rowPrices[code] || null);
}

/* 머리 오른쪽에 「전체 화면」과 닫기를 붙인다. stock.html 에는 없는 것이라
   — 그 화면은 이미 전체 화면이다 — 모달에서만 더한다. */
function addModalActions(main, code) {
  const top = main.querySelector('.kh-head-top');
  if (!top || top.querySelector('.kh-head-act')) return;
  const act = document.createElement('div');
  act.className = 'kh-head-act';
  act.innerHTML = `
    <a class="kh-chip-btn" href="./stock.html?code=${code}">전체 화면 ↗</a>
    <button class="kh-modal-x" title="닫기 (Esc)" aria-label="닫기">✕</button>`;
  act.querySelector('.kh-modal-x').addEventListener('click', closeModal);
  top.appendChild(act);
}

/* 뒤로가기로도 닫힌다. 주소를 복사해 두면 그 종목이 열린 채로 뜬다. */
window.addEventListener('popstate', () => {
  const code = history.state && history.state.stock;
  if (code) { openStockModal(code, { push: false }); return; }

  /* 히스토리는 브라우저가 이미 옮겼다. 닫기만 하고 주소는 건드리지 않는다 */
  historyMoved = true;
  closeModal();
  historyMoved = false;
});

function selectStock(code) {
  selectedCode = code;
  document.querySelectorAll('#kh-rows tr').forEach(tr =>
    tr.classList.toggle('is-active', tr.dataset.code === code));
  paintPreview(rowPrices);
  drawPreviewChart();
  drawPickedDisclosures();
}

/* ── 시작 ───────────────────────────────── */

const side = mountWatchSide($('kh-side'), { activeCode: null });

/* 주요 일정 · 최근 공시는 관심종목 아래에 둔다 (2026-09-14 지시).
   사이드바는 시세가 들어와도 목록만 다시 그리므로 여기 넣은 것은 깜빡이지 않는다. */
if (side.slot) {
  /* 두 칸 다 '더보기' 로 뉴스·공시 화면에 간다 (2026-09-15 지시).
     여기 보이는 것은 맛보기고, 전체는 그 화면에 있다. */
  side.slot.innerHTML = `
    <div class="kh-side-sec">
      <div class="kh-sched-h"><span>주요 일정</span><span class="kh-mut">2주</span></div>
      <div class="kh-sched-b" id="kh-side-sched"></div>
      <a class="kh-sec-more" href="./news.html">더보기</a>
    </div>
    <div class="kh-side-sec">
      <div class="kh-sched-h"><span>뉴스</span><span class="kh-mut">경제지</span></div>
      <div class="kh-sched-b" id="kh-side-news"></div>
      <a class="kh-sec-more" href="./news.html">더보기</a>
    </div>
    <div class="kh-side-sec">
      <div class="kh-sched-h"><span>공시</span><span class="kh-mut">OpenDART</span></div>
      <div class="kh-sched-b"><div class="kh-dc" id="kh-dc-all"></div></div>
      <a class="kh-sec-more" href="./news.html">더보기</a>
    </div>`;
}
mountVBar($('kh-vbar'), 'watch');
const foot = mountFootStrip($('kh-foot'));

paintClock();
setInterval(paintClock, 30000);
paintMkt();
setInterval(paintMkt, 30000);
setupStrip();
paintIndexPeriods();

/* 지난번에 본 값이 남아 있으면 그것부터 그린다 (2026-09-15).

   화면을 오갈 때마다 "불러오는 중" 이 몇 초씩 떠 있었다. 서버에서 값이
   오기까지의 그 시간을, 조금 묵었더라도 숫자로 채운다. 곧 새 값이 덮는다.

   남은 것이 없으면(처음 열었거나 1분이 지났으면) 전과 같이 빈 칸이다.
   묵은 값을 실시간인 양 보여주지 않도록, 1분이 넘으면 last-seen 이
   스스로 버린다. */
const keptPrices = lastSeen.load('prices');
if (keptPrices) rowPrices = keptPrices.value;

/* 지수는 startLiveLoop 이 남은 값으로 한 번 불러 주므로 여기서는 비워 둔다.
   그쪽이 세 화면 공통이라 한 곳에서만 하는 편이 맞다. */
paintIndices(null);
paintRows(keptPrices ? rowPrices : null);
if (keptPrices) { side.update(rowPrices); paintPreview(rowPrices); }

/* 순위표 목록을 받아 200줄을 깐다. 시세는 보이는 줄부터 채워진다.
   목록을 못 받으면 관심종목으로 물러선다 (rowList 안에서 처리). */
loadUniverse().then(() => {
  paintRows(rowPrices);
  /* 보고 있는 것만 주기적으로 다시 받는다. 시세 띠·관심 사이드바와 별개다. */
  /* 0.2초마다 다섯 묶음 중 하나씩. 전체는 1초에 한 바퀴 돈다. */
  setInterval(rotateTick, ROW_REFRESH_MS);

  /* 큰 차트도 계속 다시 받는다. 전에는 지수를 바꿀 때만 그려서, 한 번 그린 뒤
     장이 진행돼도 선이 멈춰 있었다 (2026-09-15 지적).
     지수 분봉은 5분 간격이라 그보다 자주 부를 이유가 없다. */
  setInterval(() => { if (!document.hidden) paintBigChart(); }, INDEX_CHART_MS);
});
paintPreview(null);
drawPreviewChart();

/* ── 공시 ──
   서버(server/dart.py)가 5분마다 받아 두므로 화면도 같은 주기로 다시 읽는다.
   오른쪽은 감시 대상 200종목 전체, 미리보기 안쪽은 지금 고른 종목만. */
const dcAll = mountDisclosures($('kh-dc-all'), { limit: 10, showName: true });

/* 주요 일정 — 금리·물가·실적 발표 중 앞으로 2주 안의 것.
   사이드바는 좁으므로 설명을 빼고 네 줄만 (전체는 '더보기'). */
const sched = mountSchedule($('kh-side-sched'), {
  compact: true, limit: 4, watch: WATCHLIST.map(s => s.code),
});
setInterval(() => { if (!document.hidden) sched.refresh(); }, 10 * 60 * 1000);

/* ── 사이드바 뉴스 ──
   맛보기로 몇 줄만 보여준다. 전체는 '더보기' 로 뉴스·공시 화면에서 본다
   (2026-09-15 지시). 주제어와 걸러내는 규칙은 서버가 쥐고 있으므로
   여기서는 받아서 줄만 그린다. */
const SIDE_NEWS_N = 5;
const SIDE_NEWS_MS = 180_000;        // 서버 캐시와 같은 주기. 더 자주 물을 이유가 없다

function esc(t) {
  return String(t == null ? '' : t).replace(/[&<>"]/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

async function drawSideNews() {
  const host = $('kh-side-news');
  if (!host) return;
  let rows = null;
  try {
    const r = await apiFetch('/api/news/issues', { cache: 'no-store' });
    if (!r) return null;   // 로그인이 풀렸다
    const j = await r.json();
    if (j && j.ok && Array.isArray(j.data)) rows = j.data;
  } catch { /* 아래에서 못 받았다고 적는다 */ }

  if (!rows) {
    host.innerHTML = `<div class="kh-sched-i kh-mut">뉴스를 불러오지 못했습니다</div>`;
    return;
  }
  if (!rows.length) {
    host.innerHTML = `<div class="kh-sched-i kh-mut">받은 뉴스가 없습니다</div>`;
    return;
  }
  host.innerHTML = rows.slice(0, SIDE_NEWS_N).map(x => `
    <a class="kh-side-news-i" href="${esc(x.link)}" target="_blank" rel="noopener">
      <i>${esc(x.topicLabel || '')}</i>
      <span>${esc(x.title)}</span>
    </a>`).join('');
}

drawSideNews();
setInterval(() => { if (!document.hidden) drawSideNews(); }, SIDE_NEWS_MS);
let dcOne = null;
function drawPickedDisclosures() {
  dcOne = mountDisclosures($('kh-dc-one'),
    { code: selectedCode, limit: 6, showName: false });
}
drawPickedDisclosures();
setInterval(() => { dcAll.reload(); dcOne && dcOne.reload(); }, 5 * 60 * 1000);

/* 종목 시세는 받지 않는다(prices: false). 순위표가 멀티 조회로
   관심종목까지 함께 받아 한 곳에 모으기 때문이다. 여기서 또 받으면
   같은 값을 두 경로로 부르게 된다 (2026-09-14 정리). */
startLiveLoop({
  prices: false,
  /* 지수·선물을 1초마다 받는다. 전에는 30초였다 — 관심종목과 함께 받던
     느린 갈래에 묶여 있었기 때문이다. 순위표는 0.2초인데 지수만 30초라
     같은 화면에서 갱신 속도가 제각각이었다 (2026-09-15 지적).
     해외 지수는 서버가 60초 캐시로 받아내므로 호출이 늘지 않는다. */

  /* 1초로 두니 배포본에서 지수가 한 번 갱신되고 멈춘 적이 있다 (2026-09-15).
     /api/kis/indices 한 번이 KIS 를 11번 부르는데(국내 현재값 3 + 추이 3 +
     해외 4 + 선물 1), 워커가 200ms 간격을 강제해 2.2초가 걸렸다.
     2.2초 걸리는 일을 1초마다 시키니 대기 줄이 밀렸다.

     원인은 워커에 자체 캐시가 없어서였다. 엣지 캐시(cf.cacheTtl)에만
     기댔는데 무료 요금제는 최소 보관이 2시간이라 1초·60초·600초가 전부
     무시됐다. 로컬 서버는 처음부터 메모리에 들고 있어 멀쩡했다.

     워커에 같은 캐시를 넣어 11번 → 4번(현재값 3 + 선물 1)이 되었다.
     0.8초라 1초 주기도 감당한다. 워커 코드를 직접 돌려 실측한 값이다.

     그래도 2초로 둔다. KIS 는 감당해도 Cloudflare 무료 한도(하루 10만 요청)가
     따로 있고, 화면이 워커를 부르는 횟수는 캐시로 줄지 않는다.
     위 ROW_REFRESH_MS 의 계산표 참고 (2026-09-15 지시). */
  indexMs: 2000,
  onIndices(indices) { paintIndices(indices); foot.update(indices); },
  onPrices(prices)   {
    lastTickAt = new Date();
    paintClock();                 // 받은 시각을 바로 반영
    /* 관심 사이드바도 순위표와 같은 값을 써야 한다. 여기서 따로 받은 값을
       바로 넣으면 두 자리의 숫자가 어긋난다. 모으는 곳을 거친다. */
    applyPrices(prices);
    paintPreview(prices);
    /* 모달이 떠 있으면 같은 값을 넘긴다. 모달이 따로 받으면 두 자리의
       숫자가 어긋나고 KIS 를 겹쳐 부르게 된다. */
    if (stockModal && prices[stockModal.code]) {
      stockModal.view.paint(prices[stockModal.code]);
    }
  },
});

/* 공지 배너 닫기 */
$('kh-notice-x')?.addEventListener('click', () => $('kh-notice')?.remove());

/* 주소에 ?code= 가 붙어 있으면 그 종목을 열어 둔 채로 시작한다.
   모달 주소를 복사해 두었거나 새로고침한 경우다. */
{
  const code = new URLSearchParams(location.search).get('code');
  if (code) {
    history.replaceState({ stock: code }, '', location.href);
    openStockModal(code, { push: false });
  }
}
