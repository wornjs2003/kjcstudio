/* ==========================================================================
   첫 화면 (index.html)

   지수 · 순위 표 · 고른 종목 미리보기를 그립니다.
   값은 서버(/api/kis/*)에서 받고, 못 받으면 '—' 또는 '연결 예정' 이 남습니다.
   ========================================================================== */

import { WATCHLIST, brandColor } from './data/market.js';
import * as lastSeen from './store/last-seen.js';
import { fetchCandles, createStockChart, maLegend } from './chart.js';
import { color } from './theme.js';
import { fmtNum, fmtWon, fmtPct, fmtMoneyKr, fmtDelta, fmtDeltaAmount, fmtShareCount,
  dirClass, marketPhase } from './utils/format.js';
import { favList, isFav, toggleFav, onFavChange } from './store/favorites.js';
/* mountWatchSide · mountVBar 는 첫 화면에서 안 쓴다 (2026-09-17).
   관심 목록은 순위표의 「관심」 칩으로 들어갔고, 세로 아이콘 바는
   그만큼 오른쪽 칸을 넓히려고 감췄다. 다른 화면은 그대로 쓴다. */
import { mountFootStrip, startLiveLoop } from './components/frame.js';
import { iconHtml, paintIcon } from './components/stock-icon.js';
import { openModal, closeModal } from './components/modal.js';
import { loadStockMain, mountStockView } from './components/stock-view.js';
import { mountDisclosures } from './components/disclosures.js';
import { mountIndicatorMenu } from './components/indicator-menu.js';
import { mountSchedule } from './components/schedule.js';
import { bindDailyMenu } from './components/daily-view.js';
import { mountSectors } from './components/sectors.js';
import { mountStockPanel } from './components/stock-panel.js';
import { mountStockDetail } from './components/stock-detail.js';
/* fetchIndexMinutes · fetchIndexCandles 는 여기서 안 쓴다 (2026-09-17).
   큰 차트가 지수에서 종목으로 바뀌면서 종목 캔들(chart.js 의 fetchCandles)로
   갈아탔다. 두 함수는 지수 화면을 만들 때 쓸 수 있게 live.js 에 남겨 뒀다. */
import { fetchQuotes } from './data/live.js';
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

/* 큰 차트에 무엇을 띄울까 (2026-09-17 지시 —
   "처음켰을때는 코스피 최상위 종목으로 해주고 그다음부터는 마지막에
   마우스 오버된 종목으로 해줘").

   처음 켜면 비어 있고, 목록이 들어온 뒤 맨 위 종목으로 채운다.
   순위표가 거래대금 순이라 그 시점의 1위가 들어간다.

   last-seen 은 1분이 지나면 스스로 버리므로 여기에는 못 쓴다.
   어제 본 종목도 이어져야 한다. */
const LAST_KEY = 'kh:lastStock';

function rememberStock(code) {
  try { localStorage.setItem(LAST_KEY, code); } catch { /* 사생활 보호 창 */ }
}

function keptStock() {
  try { return localStorage.getItem(LAST_KEY) || null; } catch { return null; }
}

let selectedCode = keptStock() || WATCHLIST[0].code;

/* 마지막으로 시세를 받은 시각.
   가격이 한동안 그대로일 때가 있어서(체결이 같은 값에 머무는 구간),
   "언제 받았는지" 를 보여줘야 갱신이 돌고 있다는 걸 알 수 있다. */
let lastTickAt = null;

/* 작은 추이선(sparkSvg)은 2026-09-17 에 지웠다 (지시 — "주요지수에 있는건
   차트는 안쓰니 차트관련된건 필요없고 가격변동과 등락률만 있으면 돼").
   만들어 놓고 CSS 로 가리고 있었는데, 그리지 않는 편이 맞다.
   받아오는 쪽도 함께 껐다 — data/live.js 의 chart=0 참고. */

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
/* 상승·하락 종목 수를 어느 시장 기준으로 보여줄까. 코스피로 고정한다.
   전에는 눌러 고른 지수를 따랐는데, 큰 차트가 종목으로 바뀌면서
   지수를 고르는 일 자체가 없어졌다 (2026-09-17). */
const COUNT_MARKET = 'KOSPI';
let lastIndices = null;

function paintMkt() {
  const el = $('kh-mkt');
  if (!el) return;
  const phase = marketPhase();
  const live = phase.id === 'regular' || phase.id === 'single';

  /* 시장 현황(상승·보합·하락 종목 수)을 장 상태 바로 옆에 둔다 (2026-09-15 지시).
     지수 조회 응답에 이미 들어 있어서 따로 부르지 않는다.
     코스피 기준이다 — 코스닥을 고르면 그쪽 숫자로 바뀐다. */
  const idx = (lastIndices || []).find(x => x.code === COUNT_MARKET)
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
  /* 단일가(15:20~15:30)도 KRX 가 도는 시간이라 값이 움직인다.
     애프터 준비(15:30~15:40)는 주문만 받고 체결이 없어 값이 멈춰 있다. */
  if (phase.id === 'regular' || phase.id === 'single') return { live: true, text: '실시간' };
  if (phase.id === 'pre' || phase.id === 'after') return { live: false, text: '넥장' };
  return { live: false, text: '장마감' };
}

function paintStrip(indices) {
  const byCode = Object.fromEntries((indices || []).map(i => [i.code, i]));
  const host = $('kh-strip');
  if (!host) return;

  /* 자주 보는 넷은 장 상태 줄 위에, 나머지는 「주요 지수」 카드에 (2026-09-17 지시).
     같은 그림을 두 자리에 나눠 그린다 — 만드는 코드는 하나다. */
  const top = $('kh-top-ix');
  const draw = cells => cells.map(cell => {
    const i = cell.code ? byCode[cell.code] : null;
    if (!i) {
      /* 둘을 구분해 적는다.
         받아올 곳이 아직 없는 칸  → "연결 예정" · 값은 "—"
         연결은 됐는데 안 온 칸    → "불러오는 중"
         섞어 쓰면 연결이 안 된 건지 아직 안 온 건지 알 수 없다. */
      const soon = !cell.code;
      return `<div class="kh-ix">
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
    return `<div class="kh-ix">
      <div class="kh-ix-h">${cellIcon(cell.icon)}<span class="kh-ix-n">${cell.name}</span>
        <span class="kh-bd ${badge.live ? 'kh-bd-on' : (badge.text === '넥장' ? 'kh-bd-nx' : '')}"
          >${badge.text}</span></div>
      <div class="kh-ix-b">
        <div>
          <div class="kh-ix-v kh-num ${cls}"
            >${fmtNum(i.value, 2)}</div>
          <div class="kh-ix-c kh-num ${cls}">${fmtDelta(i.change, i.changePct, '', 2)}</div>
        </div>
      </div>
    </div>`;
  }).join('');

  /* 누르는 동작은 뺐다 (2026-09-17). 전에는 눌러서 아래 큰 차트를 그 지수로
     바꿨는데, 그 자리가 종목 차트가 되어 눌러도 갈 곳이 없어졌다.
     지수 화면을 만들면 그때 다시 붙인다 — 동작하지 않는 단추를 남기지 않는다. */

  /* 위 줄은 자주 보는 넷만, 카드는 전부다 (2026-09-17 지시 — "주요지수에
     코스닥은 안나오네"). 위에 올린 것을 카드에서 빼면 「주요 지수」인데
     코스피·코스닥이 없는 목록이 된다. */
  if (top) top.innerHTML = draw(INDEX_CELLS.filter(c => TOP_CELLS.includes(c.name)));
  host.innerHTML = draw(INDEX_CELLS);
  paintIxFilter();
}

/* 장 상태 줄 위에 올리는 넷. 이름으로 고른다 — INDEX_CELLS 의 name 과 같다. */
const TOP_CELLS = ['코스피', '코스닥', '나스닥 종합', 'S&P 500'];

/* 카드 안의 지수를 칩으로 거른다.

     국내  코스피200 · KRX100          (국기 kr)
     미국  USD · 나스닥100 · 필라델피아 반도체 · VIX   (국기 us · 배지 vix)
     해외  유로STOXX50 · 홍콩H         (배지 eu · hk)
     기타  WTI 원유 · 금               (배지 oil · au)

   무리는 칸 앞의 표시로 가른다. 목록을 따로 두면 INDEX_CELLS 와 두 곳이 된다. */
const IX_GROUP = { kr: 'kr', us: 'us', vix: 'us', eu: 'ov', hk: 'ov', oil: 'etc', au: 'etc' };
let ixGroup = 'kr';

function ixGroupOf(cell) {
  if (cell.icon === 'kr' || cell.icon === 'us') return cell.icon;
  return IX_GROUP[cell.icon] || 'etc';
}

function paintIxFilter() {
  const host = $('kh-strip');
  if (!host) return;
  [...host.children].forEach((el, i) => {
    el.hidden = INDEX_CELLS[i] ? ixGroupOf(INDEX_CELLS[i]) !== ixGroup : true;
  });
}

function setupIxChips() {
  const chips = document.querySelectorAll('.kh-ix-chips .kh-chip');
  chips.forEach(b => b.addEventListener('click', () => {
    chips.forEach(x => x.classList.remove('is-active'));
    b.classList.add('is-active');
    ixGroup = b.dataset.g;
    paintIxFilter();
  }));
}

/* 좌우로 미는 단추는 2026-09-17 에 없앴다. 지수가 카드 안으로 들어가면서
   줄을 바꿔 다 보이게 됐고, 많으면 칩으로 거른다. */

/* ── 고른 지수의 큰 차트 ─────────────────────
   기간을 고를 수 있다 (2026-09-15 지시).

     5분  당일 흐름. 선으로 그린다 — 5분 간격이라 캔들로 그리면 몸통이 거의 없다
     일·주·월·년  캔들. 종목 화면과 같은 그림(js/chart.js)을 쓴다

   선 그림은 어제 구간을 눌러 담고 시간에 비례해 자리를 잡는 등 당일용으로
   따로 만든 것이라, 5분봉에서만 쓴다. */
/* id 는 chart.js 의 PERIOD_MAP 키를 그대로 쓴다. 전에는 지수 전용 코드
   ('D'·'W')여서 따로였는데, 종목 캔들을 그리게 되면서 한 벌로 합쳤다. */
const BIG_PERIODS = [
  { id: '5m', label: '5분' },
  { id: '1d', label: '일'  },
  { id: '1w', label: '주'  },
  { id: '1M', label: '월'  },
  { id: '1y', label: '년'  },
];
let bigPeriod = '5m';
let bigChart = null;          // 그려 둔 차트 (지울 때 필요)
let bigChartKey = null;

function paintBigPeriods() {
  const host = $('kh-idx-per');
  if (!host) return;
  host.innerHTML = BIG_PERIODS.map(p =>
    `<button data-p="${p.id}" class="${p.id === bigPeriod ? 'is-on' : ''}">${p.label}</button>`
  ).join('');
  host.querySelectorAll('button').forEach(b =>
    b.addEventListener('click', () => {
      bigPeriod = b.dataset.p;
      paintBigPeriods();
      paintBigChart();
    }));
}

/* 캔들을 지운다. 새로 그리기 전과 선 그림으로 돌아갈 때 부른다. */
function dropBigChart() {
  if (bigChart) { bigChart.destroy(); bigChart = null; }
}

/* 큰 차트에 얼마나 담을까. 5분봉은 이틀치, 나머지는 넉넉히 받아
   200일선까지 그려지게 한다 (chart.js 의 MA_LINES 가 200 을 쓴다). */
const BIG_LIMIT = { '5m': 180, '1d': 400, '1w': 300, '1M': 300, '1y': 40 };

/* 머리줄의 이름·현재가. 차트보다 먼저 바뀌어야 한다 —
   봉을 받는 데 시간이 걸리는데 이름이 옛 종목인 채로 있으면
   다른 종목 차트를 보고 있는 것처럼 보인다. */
function paintBigHead(s2) {
  paintIcon($('kh-big-ic'), s2);
  /* 옆 패널 「세부사항」 제목에도 같은 아이콘을 둔다 (2026-09-18 지시).
     패널 넷이 다 이 종목 이야기인데 어느 종목인지는 여기 머리줄에만 있었다. */
  paintIcon($('kh-dt-ic'), s2);
  const nameEl = $('kh-idx-name');
  if (nameEl) nameEl.textContent = s2.name;

  const link = $('kh-big-link');
  if (link) {
    /* 주소는 남겨 둔다 — 가운데 단추로 새 탭에 열거나 링크를 복사하는
       길이 막히지 않게 한다 (미리보기 카드가 하던 것 그대로다). */
    link.href = `./stock.html?code=${s2.code}`;
    link.onclick = e => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
      e.preventDefault();
      openStockModal(s2.code);
    };
  }
  paintBigPrice();
}

/* 현재가와 등락률. 시세가 들어올 때마다 불린다. */
let bigShown = null;
function paintBigPrice() {
  const el = $('kh-big-v');
  if (!el) return;
  const live = rowPrices && rowPrices[selectedCode];
  if (!live) {
    el.className = 'kh-idx-v kh-num kh-mut';
    el.textContent = '불러오는 중';
    bigShown = null;
    return;
  }
  /* 값이 그대로면 손대지 않는다. 0.2초마다 받는데 매번 클래스를 다시 붙이면
     깜빡임이 계속 돌아 숫자가 쉬지 않고 흔들린다 (2026-09-14 지적). */
  const stamp = `${selectedCode}|${live.price}|${live.pct}`;
  if (bigShown === stamp) return;
  bigShown = stamp;
  el.className = 'kh-idx-v kh-num ' + dirClass(live.pct);
  el.textContent = `${fmtWon(live.price)}  ${fmtPct(live.pct)}`;
}

/* 큰 차트 — 고른 종목을 그린다.
 *
 * **2026-09-17 까지 여기는 지수 차트였다.** 지수는 하루에 몇 번 보지 않는데
 * 화면에서 가장 큰 자리를 먹고 있었다. 지수 값은 위 카드 띠에 그대로 있다.
 *
 * 무엇을 그리나 — selectedCode 다. 목록에 마우스를 올리면 그것이 바뀌고
 * 여기가 따라온다. 없애 버린 미리보기 카드가 하던 일을, 더 큰 자리에서 한다.
 */
async function paintBigChart() {
  const st = findStock(selectedCode);
  if (!st) return;

  const key = st.code + ':' + bigPeriod;
  bigChartKey = key;
  paintBigHead(st);

  const host = $('kh-big-chart');
  const foot = $('kh-big-foot');
  if (!host) return;

  let candles, period;
  try {
    ({ candles, period } = await fetchCandles(st.code, bigPeriod, BIG_LIMIT[bigPeriod] || 240));
  } catch {
    if (bigChartKey !== key) return;        // 그 사이 다른 종목을 골랐다
    dropBigChart();
    host.innerHTML = `<div class="kh-soon">
      <div class="kh-soon-t">차트를 불러오지 못했습니다</div></div>`;
    if (foot) foot.innerHTML = '<span></span><span>한국투자증권</span>';
    return;
  }
  if (bigChartKey !== key) return;

  if (!candles || !candles.length) {
    dropBigChart();
    host.innerHTML = `<div class="kh-soon">
      <div class="kh-soon-t">봉이 없습니다</div></div>`;
    return;
  }

  /* **차트를 다시 만들지 않는다 (2026-09-17 지시).** 이미 있으면 봉만
     갈아끼운다. 만드는 일이 가장 비싸고, 없애는 것을 한 번이라도 빠뜨리면
     객체가 쌓여 어느 순간부터 새 차트가 아예 안 그려진다
     (2026-09-17 아침 — "위로 올려서 삼성전자 볼려고 하니까 안나온다").

     칸이 비어 있으면(오류 문구를 띄웠던 자리) 새로 만든다. */
  if (bigChart && host.querySelector('canvas')) {
    bigChart.setData(candles, period);
  } else {
    dropBigChart();
    host.innerHTML = '';
    bigChart = createStockChart(host, candles, { period, showVolume: true });
  }

  /* 5분봉에는 전일 종가선을 그어 둔다. 오늘 올랐는지 내렸는지의 기준이다.
     어제 마지막 봉의 종가가 그 값이다. */
  /* addPriceLine 으로 긋는다 — 다음에 봉을 갈아끼울 때 저절로 지워진다.
     직접 createPriceLine 을 부르면 종목을 옮길 때마다 선이 쌓인다. */
  if (bigPeriod === '5m' && bigChart) {
    const today = candles[candles.length - 1].ts.slice(0, 8);
    const firstToday = candles.findIndex(b => b.ts.slice(0, 8) === today);
    if (firstToday > 0) {
      bigChart.addPriceLine({
        price: candles[firstToday - 1].close,
        color: color('text-muted'),
        lineWidth: 1,
        lineStyle: 2,               // 점선
        axisLabelVisible: true,
        title: '전일',
      });
    }
  }

  if (foot) {
    const label = (BIG_PERIODS.find(p => p.id === bigPeriod) || {}).label || '';
    /* 이동평균 범례를 함께 둔다. 어느 선이 그려졌는지, 봉이 모자라 못 그린
       선이 무엇인지 여기서 보인다 (2026-09-16). */
    const ma = bigChart ? maLegend(bigChart.maSeries) : '';
    foot.innerHTML = bigPeriod === '5m'
      ? `<span>${ma} · 점선은 전일 종가</span><span>한국투자증권 실시간</span>`
      : `<span>${ma} · ${label}봉 ${candles.length}개</span><span>한국투자증권</span>`;
  }
}

function paintIndices(indices) {
  lastIndices = indices;
  paintStrip(indices);
  paintMkt();          // 상승·하락 종목 수가 여기 들어 있다
}

/* 52주 최저·최고 — 고른 종목 기준.
 *
 * **지수와 기간이 다르다.** 지수 응답은 '올해 들어'(yearHigh·yearLow)를 주는데
 * 종목은 KIS 가 52주(high52·low52)로 준다. 같은 칸이지만 뜻이 달라
 * 화면 이름도 「52주」로 바꿔 적었다 (index.html).
 *
 * 날짜는 안 온다. 지수에는 yearHighDate 가 있었는데 종목 응답에는 없어서
 * 「최저 03.14」 같은 꼬리말이 빠졌다.
 */
const _range = new Map();          // 종목코드 → { lo, hi }
let rangeKey = null;

async function paintYearRange() {
  const el = $('kh-year-range');
  if (!el) return;
  const code = selectedCode;
  rangeKey = code;

  let r = _range.get(code);
  if (!r) {
    el.textContent = '불러오는 중';
    /* 52주 값은 하루에 한 번 바뀔까 말까다. 한 번 받으면 쥐고 있는다 —
       마우스로 종목을 훑을 때마다 부르면 요청이 그만큼 늘어난다. */
    try {
      const res = await apiFetch(`/api/kis/price?code=${code}`, { cache: 'no-store' });
      if (!res || !res.ok) return;
      const j2 = await res.json();
      if (!j2 || !j2.ok || !j2.data) return;
      r = { lo: j2.data.low52, hi: j2.data.high52, price: j2.data.price };
      _range.set(code, r);
    } catch { return; }
  }
  if (rangeKey !== code) return;              // 그 사이 다른 종목을 골랐다
  if (r.lo == null || r.hi == null) { el.textContent = '값이 없습니다'; return; }

  /* 지금 값은 시세 쪽이 더 새것이다. 없으면 받아둔 값으로 물러선다. */
  const live = rowPrices && rowPrices[code];
  const cur = (live && live.price != null) ? live.price : r.price;
  const at = Math.max(0, Math.min(1, (cur - r.lo) / Math.max(1e-9, r.hi - r.lo)));
  el.innerHTML = `
    <div class="kh-yr">
      <span class="kh-num kh-down">${fmtWon(r.lo)}</span>
      <span class="kh-yr-bar"><i style="left:calc(${(at * 100).toFixed(1)}% - 5px)"></i></span>
      <span class="kh-num kh-up">${fmtWon(r.hi)}</span>
    </div>
    <div class="kh-head-yr-note kh-mut">
      지금 <b>${fmtWon(cur)}</b> · 최저에서 <b>${(at * 100).toFixed(0)}%</b> 자리</div>`;
}

/* 세부사항(거래대금 · 시가총액 · 매수매도)은 차트 머리줄로 갔다 (2026-09-21 지시).
   그리는 것은 components/stock-detail.js 다. 여기 있던 paintVolBox 는 지웠다. */

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

/* ── 순위 단추 (2026-09-18 지시) ─────────────
 *
 * **KIS 순위 API 를 안 쓴다.** 넷 다 있지만 30행까지만 주고, 같은 값을 두
 * 곳에서 받으면 어긋난다 (docs/data-sources.md 의 PER 71% 차이 사례).
 * 시세 응답에 pct · volume · value 가 이미 다 들어 있어 여기서 줄만 세운다.
 * 그래서 **단추를 눌러도 서버를 안 부르고**, 30행 제한도 없다.
 *
 * 급상승·급하락은 거래대금이 적은 종목을 뺀다. 100원이 130원 되면 +30% 라,
 * 안 거르면 몇 십 원짜리가 위를 다 차지한다. 기준은 화면에 적는다 —
 * 보고 고칠 수 있어야 한다.
 */
/* 거래대금은 멀티 조회의 value 를 쓰고, 없으면 현재가×거래량으로 어림한다.
   components/stock-detail.js 와 같은 계산이다. */
const valueOf = (p) => (p ? (p.value ?? (p.price != null && p.volume != null
  ? p.price * p.volume : null)) : null);

/* 줄 세운 기준값을 화면에 보여준다 (2026-09-18 지시 —
   "해당 칩을 클릭하면 해당값들이 보여줘야 할거같은데. 그래야 제대로 되는지
   확인이 가능할거같아"). 「전일대비」 자리를 이 값이 대신한다.

   급상승·급하락은 등락률로 세우는데 그것은 맨 오른쪽에 이미 있다. 대신
   **걸러내는 기준인 거래대금**을 보여준다 — 왜 이 종목이 올라왔는지가 보인다. */
const showValue = (code, p) => {
  const won = valueOf(p);
  return won == null ? '—' : fmtMoneyKr(Math.round(won / 1e8));
};

const SORTS = {
  cap:  { label: '시가총액', key: null,
          head: '시가총액', show: (code) => {
            const c = capOf(code);
            return c == null ? '—' : fmtMoneyKr(c);
          } },
  value:{ label: '거래대금', key: (p) => valueOf(p),
          head: '거래대금', show: showValue },
  vol:  { label: '거래량',   key: (p) => p.volume,
          head: '거래량',   show: (code, p) => (p ? fmtShareCount(p.volume) : '—') },
  up:   { label: '급상승',   key: (p) => p.pct,  dir: -1, minValue: true,
          head: '거래대금', show: showValue },
  down: { label: '급하락',   key: (p) => p.pct,  dir: 1,  minValue: true,
          head: '거래대금', show: showValue },
};

/* 급상승·급하락에서 이보다 적게 거래된 종목은 뺀다 (지시 — 1000억) */
const MIN_VALUE_WON = 1000 * 1e8;

let sortBy = 'cap';

function rowList() {
  if (!universe) return WATCHLIST.map((s, i) => ({ ...s, rank: i + 1 }));

  const base = universe.map(x => ({
    code: x.code, name: x.name, sector: '',
    brand: brandColor(x.code, x.name), rank: x.rank,
  }));

  const sort = SORTS[sortBy];
  if (!sort || !sort.key) return base;      // 시가총액은 목록 순서 그대로

  /* 값이 아직 안 온 종목은 뒤로 보낸다. 0 으로 치면 「거래량 0위」 가 된다 */
  const val = (s) => {
    const p = rowPrices && rowPrices[s.code];
    if (!p) return null;
    if (sort.minValue) {
      const v = valueOf(p);
      if (!(v >= MIN_VALUE_WON)) return null;
    }
    const n = sort.key(p);
    return Number.isFinite(n) ? n : null;
  };

  const dir = sort.dir ?? -1;               // 기본은 큰 것부터
  return base
    .map(s => ({ s, v: val(s) }))
    .sort((a, b) => {
      if (a.v == null && b.v == null) return a.s.rank - b.s.rank;
      if (a.v == null) return 1;
      if (b.v == null) return -1;
      return (a.v - b.v) * dir;
    })
    .map(({ s }, i) => ({ ...s, rank: i + 1 }));
}

/* 단추를 누르면 줄 세우는 기준이 바뀐다. 서버는 안 부른다 —
   이미 가진 시세로 다시 세우기만 한다. */
function setupSorts() {
  const host = $('kh-sorts');
  if (!host) return;
  host.addEventListener('click', (e) => {
    const b = e.target.closest('[data-sort]');
    if (!b || b.dataset.sort === sortBy) return;
    sortBy = b.dataset.sort;
    host.querySelectorAll('[data-sort]').forEach(x =>
      x.classList.toggle('is-active', x === b));
    paintRows(rowPrices);
  });
}

/* 지금 무엇을 보고 있는지 한 줄로 적는다 (2026-09-18 지시).
 *
 * **단추를 눌러도 서버를 안 부르므로 기다릴 일이 없다.** 대신 두 가지가
 * 뒤처질 수 있어 그것을 적는다 —
 *
 *   값이 몇 초 전 것인가     시세는 돌아가며 받으므로 방금 값이 아니다
 *   몇 종목이나 찼는가       200개가 다 차기 전에는 순서가 불완전하다
 *
 * 숫자만 보이면 지금 값인 줄로 읽힌다. 「140/200」 이 보이면 아직 순서를
 * 믿을 때가 아니라는 걸 알 수 있다.
 */
let noteAt = 0;

function paintSortNote() {
  const el = $('kh-sort-note');
  if (!el) return;
  const s = SORTS[sortBy];

  const total = (universe || []).length;
  const got = (universe || []).filter(x => rowPrices && rowPrices[x.code]).length;

  /* 마지막으로 값이 들어온 때부터 몇 초 지났나 */
  const sec = lastTickAt ? Math.max(0, Math.round((Date.now() - lastTickAt) / 1000)) : null;

  const bits = [`${s.label} 순`];
  if (s.minValue) bits.push(`거래대금 ${fmtMoneyKr(MIN_VALUE_WON / 1e8)} 이상만`);

  if (total && got < total) {
    bits.push(`<b class="kh-accent">${got}/${total}종목 채우는 중</b>`);
  } else if (sec != null && sec >= 3) {
    bits.push(`<b class="${sec >= 60 ? 'kh-down' : 'kh-mut'}">${
      sec >= 60 ? `${Math.floor(sec / 60)}분` : `${sec}초`} 전 값</b>`);
  }
  el.innerHTML = bits.join(' <span class="kh-mut">·</span> ');
  noteAt = Date.now();
}

/* ── 즐겨찾기 하트 (2026-09-18 지시) ─────────
 *
 * 재권님 말씀 — "실시간 순위에 나오는 종목에 즐겨찾기 (하트모양) 이 있고
 * 이걸 클릭하면 하트모양안에 색이 노란색으로 채워지고 즐겨찾기 목록에
 * 들어가게 해야할거같아."
 *
 * 담긴 것은 `store/favorites.js` 한 곳에 있다. 관심 사이드바도 같은 것을
 * 보므로 한쪽에서 누르면 다른 쪽이 따라간다.
 */
/* **칸을 늘리지 않는다** (2026-09-18 지시 — "하트대신에 숫자를 클릭하면
   숫자 색이 바뀌는게 더 좋을거같아 추가 안해도 된깐").

   하트 칸을 따로 두었더니 그만큼 종목명이 좁아졌다. 그래서 왼쪽 순위
   숫자가 그 일을 한다 — 누르면 담기고, 담긴 종목은 숫자가 노래진다. */
function paintFavCell(td) {
  const on = isFav(td.dataset.fav);
  td.classList.toggle('is-fav', on);
  td.title = on ? '즐겨찾기에서 빼기' : '즐겨찾기에 담기';
}

/* 그려 둔 순위 숫자에 동작을 건다. 표를 다시 그릴 때마다 부른다 */
function bindHearts(root) {
  if (!root) return;
  root.querySelectorAll('.kh-rk[data-fav]').forEach(td => {
    td.addEventListener('click', (e) => {
      e.stopPropagation();          // 줄 고르기로 번지지 않게
      toggleFav(td.dataset.fav, td.dataset.favName);
    });
  });
}

/* 목록이 바뀌면 화면의 모든 순위 숫자를 맞춘다 — 한 줄만 고치면 같은
   종목이 다른 자리에 또 있을 때 어긋난다 */
onFavChange(() => {
  document.querySelectorAll('.kh-rk[data-fav]').forEach(paintFavCell);
  paintFavCount();
});

/* 「N개 담음」 을 순위 단추 줄에 적는다. 담은 것이 어디 갔는지 보여야 한다 */
function paintFavCount() {
  const el = $('kh-fav-count');
  if (!el) return;
  const n = favList().length;
  el.textContent = n ? `♥ ${n}개 담음` : '';
}

/* 지금 줄 세운 기준의 값 한 칸 */
function sortCell(code, live) {
  const s = SORTS[sortBy];
  if (!s || !s.show) return '—';
  return s.show(code, live);
}

/* 표 머리글도 기준에 따라 바뀐다 */
function paintRowHead() {
  const th = $('kh-th-metric');
  if (th) th.textContent = (SORTS[sortBy] || {}).head || '전일대비';
}

function paintRows(priceMap) {
  const list = rowList();
  $('kh-rows').innerHTML = list.map(s => {
    const live = priceMap && priceMap[s.code];
    const cls = live ? dirClass(live.pct) : 'kh-mut';
    /* 거래대금 · 시가총액 · 매수매도 비율 · 산업은 2026-09-17 에 뺐다.
       칸이 368px 로 좁아져 아홉 열이 안 들어갔고, 그 넷은 고른 종목 것만
       차트 옆 패널에 보여주기로 했다 (지시). */
    return `<tr data-code="${s.code}" class="${s.code === selectedCode ? 'is-active' : ''}">
      <td class="kh-rk${isFav(s.code) ? ' is-fav' : ''}" data-fav="${s.code}"
        data-fav-name="${s.name}" title="${isFav(s.code) ? '즐겨찾기에서 빼기' : '즐겨찾기에 담기'}"
        >${s.rank}</td>
      <td class="l"><span class="kh-nm">
        ${iconHtml(s)}
        <b>${s.name}</b></span></td>
      <td class="kh-num"><span
        >${live ? fmtWon(live.price) : '···'}</span></td>
      <td class="kh-num kh-metric">${sortCell(s.code, live)}</td>
      <td class="kh-num ${cls}" style="font-weight:500">${live ? fmtPct(live.pct) : '—'}</td>
    </tr>`;
  }).join('');

  /* 줄을 누르면 차트가 그 종목으로 바뀐다 (2026-09-17 지시).

       ~09-16  한 번이 「고르기」, 두 번이 「열기」
       09-16   고르기를 마우스 올림으로 옮기고, 한 번 누르면 창이 뜨게
       09-17   올림을 없애고 누르기로 되돌림. 창은 「자세히 ›」 로만 뜬다

     올림으로 바꾸니 목록을 훑기만 해도 차트가 계속 따라와서, 보려던
     종목에 닿기 전에 여러 번 바뀌었다. 누를 때만 바꾸면 그 일이 없다. */
  $('kh-rows').querySelectorAll('tr[data-code]').forEach(tr => {
    tr.addEventListener('click', (e) => {
      /* 순위 숫자는 담는 자리라 줄 고르기와 겹치지 않는다. 담으려다
         차트까지 바뀌면 무엇을 눌렀는지 알 수 없다. */
      if (e.target.closest('.kh-rk[data-fav]')) return;
      selectStock(tr.dataset.code);
    });
  });
  bindHearts($('kh-rows'));
  watchRows();
  paintRowHead();
  paintRowFoot();
  paintSortNote();
  paintFavCount();
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
  if (!nextCodes().length) return;
  fetching = true;
  try {
    for (;;) {
      /* 덩어리마다 다시 고른다. 받는 동안 스크롤했으면 그쪽이 앞으로 온다 */
      const want = nextCodes();
      if (!want.length) break;
      const chunk = want.slice(0, PRICE_CHUNK);
      chunk.forEach(c => asked.add(c));
      const map = await fetchQuotes(chunk);
      if (!map) {
        /* 실패한 것은 다시 묻게 되돌리고 이번 바퀴는 끝낸다.
           같은 것을 곧바로 또 고르면 무한히 돈다. */
        chunk.forEach(c => asked.delete(c));
        break;
      }
      applyPrices(map);
    }
  } finally {
    fetching = false;
    /* 실패로 끊겼거나 그새 줄이 늘었으면 한 번 더 돈다 */
    if (nextCodes().length) scheduleFetch();
  }
}

/* 다음에 받을 종목 — **보이는 것이 먼저, 그다음 순위표 나머지**다
   (2026-09-18 지시).

   순위 단추(거래대금 · 거래량 · 급상승 · 급하락)가 200종목 전체에서 줄을
   세우려면 값이 다 있어야 한다. 그런데 처음부터 200개를 부르면 첫 화면이
   한 바퀴(30종목씩 일곱 번)를 기다린다. 그래서 순서를 둔다 — 보이는 줄을
   먼저 채우고, 나머지를 뒤에서 이어 받는다. **첫 화면 체감은 전과 같다.**

   그 전에는 보이는 줄만 받았다. 그래서 단추를 눌러도 받아 둔 스무남은
   종목 안에서만 줄이 섰다 (2026-09-18 실측 — 36초가 지나도 23/200). */
function nextCodes() {
  const watch = WATCHLIST.map(s => s.code);
  const rest = (universe || []).map(x => x.code);
  return [...new Set([...watch, ...visibleCodeList(), ...rest])]
    .filter(c => !asked.has(c));
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
  paintBigPrice();                 // 큰 차트 머리줄의 현재가
  if (typeof detail !== 'undefined' && detail) {
    detail.update(rowPrices && rowPrices[selectedCode]);   // 거래대금 · 시가총액
  }
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
    /* 「전일대비」 자리에는 지금 줄 세운 기준값이 온다. 오르내림이 아니라
       크기라서 등락 색을 입히지 않는다. */
    tr.children[3].className = 'kh-num kh-metric';
    tr.children[3].textContent = sortCell(code, live);
    tr.children[4].className = 'kh-num ' + cls;
    tr.children[4].style.fontWeight = '500';
    tr.children[4].textContent = fmtPct(live.pct);
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
  /* **보이는 줄만** 다시 받는다. 통째로 비우면 탭을 오갈 때마다
     200종목 한 바퀴(30종목씩 일곱 번)가 또 돈다 (2026-09-18). */
  WATCHLIST.forEach(s => asked.delete(s.code));
  visibleCodeList().forEach(c => asked.delete(c));
  scheduleFetch();
  paintBigChart();        // 그 사이 장이 움직였을 수 있다
});

/* ── 미리보기 ───────────────────────────── */

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

/* 미리보기 카드(paintPreview · drawPreviewChart)는 2026-09-17 에 지웠다.
   위의 큰 차트가 같은 종목을 더 크게 그리고 있어서 5분봉이 두 번 나왔다.
   하던 일은 paintBigHead · paintBigPrice · paintBigChart 가 이어받았다. */

/* 마우스 올림으로 고르던 코드(hoverPreview · HOVER_OK)는 2026-09-17 에 지웠다.
   누르기로 되돌렸기 때문이다. 위 「줄을 누르면」 주석에 경위가 있다. */

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
  paintBigChart();
  paintYearRange();
  if (typeof panel3 !== 'undefined' && panel3) panel3.setCode(code);
  if (typeof detail !== 'undefined' && detail) {
    detail.setCode(code);
    detail.update(rowPrices && rowPrices[code]);   // 받아 둔 시세로 바로 그린다
  }
  rememberStock(code);
}

/* ── 시작 ───────────────────────────────── */

/* 오른쪽 칸(실시간 순위 · 공시)은 index.html 에 마크업으로 들어 있다.
   전에는 mountWatchSide 가 관심 목록을 그리고 그 아래 slot 에
   일정·뉴스·공시를 끼워 넣었는데, 자리가 바뀌면서 필요 없어졌다. */

const foot = mountFootStrip($('kh-foot'));

paintClock();
setInterval(paintClock, 30000);
paintMkt();
setInterval(paintMkt, 30000);
setupIxChips();
setupSorts();
/* 몇 초 전 값인지는 가만히 있어도 늘어난다. 1초마다 다시 적는다 */
setInterval(() => { if (!document.hidden) paintSortNote(); }, 1000);
mountIndicatorMenu(document.querySelector('.kh-ind-menu'));

/* 「지금 뜨는 산업」 — 업종 이름 단추를 누르면 그 종목이 나온다 (2026-09-18 지시).
   값은 네이버에서 오고 첫 화면을 막지 않는다 — 목록 한 번이 0.03초다. */
mountSectors(document.querySelector('.kh-sc-card'));

/* 투자자 정보 · 매수매도 비율 — 고른 종목 것이다 (2026-09-18 지시).
   차트 종목이 바뀌면 selectStock 이 setCode 로 알린다. */
/* 고른 종목 패널 — 투자자 정보 · AI 분석 · 종목 뉴스가 1/3씩 (2026-09-21 지시).
   **마크업까지 그 컴포넌트가 만든다** — 모달·종목 화면이 같은 것을 쓴다. */
const panel3 = mountStockPanel($('kh-panel3'), { code: selectedCode });

/* 세부사항 — 차트 머리줄의 보조지표 옆 */
const detail = mountStockDetail($('kh-dt'));
if (selectedCode) detail.setCode(selectedCode);

paintBigPeriods();

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
if (keptPrices) paintBigPrice();

/* 순위표 목록을 받아 200줄을 깐다. 시세는 보이는 줄부터 채워진다.
   목록을 못 받으면 관심종목으로 물러선다 (rowList 안에서 처리). */
loadUniverse().then(() => {
  /* 기억해 둔 종목이 지금 목록에 없으면(상장폐지·순위 밖) 맨 위로 물러선다.
     처음 켠 것도 같은 길로 간다 — keptStock 이 null 이면 findStock 도 null 이다. */
  if (!findStock(selectedCode)) {
    const top = rowList()[0];
    if (top) selectedCode = top.code;
  }
  paintRows(rowPrices);
  paintBigChart();
  paintYearRange();
  panel3.setCode(selectedCode);
  detail.setCode(selectedCode);
  detail.update(rowPrices && rowPrices[selectedCode]);
  /* 보고 있는 것만 주기적으로 다시 받는다. 시세 띠·관심 사이드바와 별개다. */
  /* 0.2초마다 다섯 묶음 중 하나씩. 전체는 1초에 한 바퀴 돈다. */
  setInterval(rotateTick, ROW_REFRESH_MS);

  /* 큰 차트도 계속 다시 받는다. 한 번 그린 뒤 장이 진행돼도 선이 멈춰
     있으면 안 된다 (2026-09-15 지적).
     5분봉이라 그보다 자주 부를 이유가 없다. 받아 둔 봉은 chart.js 가
     60초 쥐고 있으므로, 같은 종목을 계속 보고 있으면 KIS 로 가지도 않는다. */
  setInterval(() => { if (!document.hidden) paintBigChart(); }, INDEX_CHART_MS);
});


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
/* 종목 뉴스는 이제 패널 셋 중 하나다(stock-panel.js). 여기서는 전체 공시만 본다 */
setInterval(() => { dcAll.reload(); }, 5 * 60 * 1000);

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
    paintBigPrice();
    /* 모달이 떠 있으면 같은 값을 넘긴다. 모달이 따로 받으면 두 자리의
       숫자가 어긋나고 KIS 를 겹쳐 부르게 된다. */
    if (stockModal && prices[stockModal.code]) {
      stockModal.view.paint(prices[stockModal.code]);
    }
  },
});

/* 공지 배너 닫기 */
/* 공지 띠는 2026-09-17 에 마크업에서 뺐다. 닫기 단추도 함께 없앴다. */

/* 주소에 ?code= 가 붙어 있으면 그 종목을 열어 둔 채로 시작한다.
   모달 주소를 복사해 두었거나 새로고침한 경우다. */
{
  const code = new URLSearchParams(location.search).get('code');
  if (code) {
    history.replaceState({ stock: code }, '', location.href);
    openStockModal(code, { push: false });
  }
}

/* 「데일리분석」 메뉴를 누르면 화면을 떠나지 않고 모달로 띄운다
   (2026-09-21 지시 — "데일리분석 을 누르면 모델이 올라오고").
   `href` 는 그대로 두므로 새 탭·직접 주소로는 전용 화면이 열린다.
   메인에 칸을 만드는 2단계는 따로 지시를 받는다. */
bindDailyMenu();
