/* ==========================================================================
   공통 틀 — 관심종목 사이드바 · 세로 아이콘 바 · 하단 시세 띠

   홈과 종목 화면이 같은 틀을 씁니다. 값은 전부 서버(/api/kis/*)에서 받고,
   못 받으면 '—' 나 '연결 예정' 이 남습니다. 예시 숫자는 두지 않습니다.
   ========================================================================== */

import { WATCHLIST, PRIORITY_CODES } from '../data/market.js';
import { fetchLivePrices, fetchLiveIndices, applyLiveToStock } from '../data/live.js';
import { fmtWon, fmtPct, fmtNum, dirClass } from '../utils/format.js';
import { tickClass } from '../utils/tick.js';

/* 아직 받아올 곳이 없는 시세 띠 항목 */
const FOOT_NOT_READY = ['달러 인덱스', '달러 환율', '나스닥', 'S&P 500', '필라델피아 반도체'];

/* ── 관심종목 사이드바 ───────────────────── */
export function mountWatchSide(el, { activeCode } = {}) {
  if (!el) return { update() {}, slot: null };

  /* 뼈대는 한 번만 그린다. 시세가 들어올 때마다 통째로 갈아치우면
     아래 붙여 둔 것(주요 일정·최근 공시)이 5초마다 다시 그려져 깜빡인다.
     그래서 종목 목록만 따로 갱신한다. (2026-09-14) */
  el.innerHTML = `
    <div class="kh-side-head">
      <b>관심</b>
      <span class="kh-side-toggle">₩ 원</span>
    </div>

    <div class="kh-oneline">
      <div class="kh-oneline-h">✨ 오늘의 한 줄</div>
      <div class="kh-oneline-b">연결 예정 — 관심종목에서 가장 크게 움직인 종목을
        한 줄로 알려줍니다.</div>
    </div>

    <div class="kh-side-title">관심 주식 TOP ${WATCHLIST.length}</div>
    <div class="kh-side-sub">관심 그룹에 담아보세요</div>

    <div class="kh-wl-list"></div>

    <div class="kh-side-add"><span class="plus">＋</span>추가하기</div>

    <!-- 부르는 쪽이 채워 넣는 자리 (첫 화면: 주요 일정 · 최근 공시) -->
    <div class="kh-side-slot"></div>
  `;

  const list = el.querySelector('.kh-wl-list');

  function render(priceMap) {
    list.innerHTML = `
      ${WATCHLIST.map(s => {
        const live = priceMap && priceMap[s.code];
        const cls = live ? dirClass(live.pct) : 'kh-mut';
        return `
          <a class="kh-wl ${s.code === activeCode ? 'is-active' : ''}"
             href="./stock.html?code=${s.code}">
            <span class="kh-ic" style="background:${s.brand}">${s.name.slice(0, 2)}</span>
            <span class="kh-wl-name">${s.name}</span>
            <span class="kh-wl-price">
              <span class="kh-wl-v kh-num ${live ? tickClass('side:' + s.code, live.price) : ''}"
                >${live ? fmtWon(live.price) : '—'}</span>
              <span class="kh-wl-c kh-num ${cls}">${live ? fmtPct(live.pct) : ''}</span>
            </span>
            <span class="kh-wl-heart">♡</span>
          </a>`;
      }).join('')}
    `;
  }

  render(null);
  return { update: render, slot: el.querySelector('.kh-side-slot') };
}

/* ── 세로 아이콘 바 ─────────────────────── */
export function mountVBar(el, active) {
  if (!el) return;
  /* href 가 있는 항목은 실제로 이동한다. 없는 항목은 아직 만들지 않은 화면이다. */
  const ITEMS = [
    { id: 'watch',    icon: '♥', label: '관심',   href: './index.html' },
    { id: 'analysis', icon: '▤', label: '분석',   href: './analysis/' },
    { id: 'roadmap',  icon: '◫', label: '로드맵', href: './roadmap.html' },
    { id: 'record',   icon: '▥', label: '내 기록' },
    { id: 'recent',   icon: '◷', label: '최근 본' },
    { id: 'studio',   icon: '↗', label: 'Studio', href: '../index.html' },
  ];
  el.innerHTML = ITEMS.map(i => {
    const cls = `kh-vb ${i.id === active ? 'is-active' : ''}`;
    const body = `<span class="sq">${i.icon}</span>${i.label}`;
    return i.href
      ? `<a class="${cls}" href="${i.href}">${body}</a>`
      : `<span class="${cls}" title="아직 만들지 않은 화면입니다">${body}</span>`;
  }).join('');
}

/* ── 하단 시세 띠 ───────────────────────── */
export function mountFootStrip(el) {
  if (!el) return { update() {} };

  function render(indices) {
    const live = (indices || []).map(i => `
      <span class="kh-fi">
        <span>${i.name}</span>
        <b class="kh-num ${dirClass(i.changePct)}">${fmtNum(i.value, 2)}</b>
        <span class="kh-num ${dirClass(i.changePct)}">${fmtPct(i.changePct)}</span>
      </span>`).join('');

    const soon = FOOT_NOT_READY.map(name => `
      <span class="kh-fi"><span>${name}</span><b class="kh-mut">연결 예정</b></span>`).join('');

    el.innerHTML = `<span class="kh-foot-warn">투자 유의사항</span>` +
      (live || `<span class="kh-fi"><span>지수</span><b class="kh-mut">불러오는 중</b></span>`) +
      soon + `<span class="kh-foot-arrows">⌃ ⌄</span>`;
  }

  render(null);
  return { update: render };
}

/* ──────────────────────────────────────────────────────────────────────────
   시세 갱신 — 한 화면에서 한 번만 돌린다.

   두 갈래로 나눠 돈다 (2026-09-14 지시).
     빠른 쪽 : PRIORITY_CODES 2종목만 5초마다
     느린 쪽 : 나머지 관심종목 + 지수 3개를 30초마다

   분당 호출은 2×12 + 9×2 = 42건으로, 전부 15초마다 부르던 44건보다 적다.
   자주 볼 필요 없는 종목의 주기를 늘려 그 몫을 앞의 둘로 옮긴 것이다.

   호출 간격은 서버가 1초씩 벌려 주므로(_rate_limit), 빠른 쪽 2건은 2초,
   느린 쪽 9건은 9초가 걸린다. 둘 다 자기 주기 안에 든다.
   ────────────────────────────────────────────────────────────────────────── */
const REFRESH_FAST_MS = 5000;
const REFRESH_SLOW_MS = 30000;

export function startLiveLoop({ onPrices, onIndices } = {}) {
  const fastCodes = WATCHLIST.filter(s => PRIORITY_CODES.includes(s.code)).map(s => s.code);
  const slowCodes = WATCHLIST.filter(s => !PRIORITY_CODES.includes(s.code)).map(s => s.code);

  /* 갈래마다 일부 종목만 받아오지만, 화면에는 항상 전체를 넘겨야 한다.
     받은 것을 여기에 쌓아 두고 합쳐서 전달한다. */
  const latest = {};

  function applyPrices(prices) {
    if (!prices) return;
    Object.assign(latest, prices);
    WATCHLIST.forEach(s => {
      const live = latest[s.code];
      if (live) applyLiveToStock(s, live);
    });
    if (onPrices) onPrices(latest);
  }

  async function tickFast() {
    if (document.hidden) return;          // 다른 탭을 보고 있으면 쉬어간다
    if (!fastCodes.length) return;
    applyPrices(await fetchLivePrices(fastCodes));
  }

  async function tickSlow() {
    if (document.hidden) return;
    const [indices, prices] = await Promise.all([
      fetchLiveIndices(),
      slowCodes.length ? fetchLivePrices(slowCodes) : Promise.resolve(null),
    ]);
    if (indices && onIndices) onIndices(indices);
    applyPrices(prices);
  }

  tickFast();
  tickSlow();
  setInterval(tickFast, REFRESH_FAST_MS);
  setInterval(tickSlow, REFRESH_SLOW_MS);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    tickFast();
    tickSlow();
  });
}
