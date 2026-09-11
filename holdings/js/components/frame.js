/* ==========================================================================
   공통 틀 — 관심종목 사이드바 · 세로 아이콘 바 · 하단 시세 띠

   홈과 종목 화면이 같은 틀을 씁니다. 값은 전부 서버(/api/kis/*)에서 받고,
   못 받으면 '—' 나 '연결 예정' 이 남습니다. 예시 숫자는 두지 않습니다.
   ========================================================================== */

import { WATCHLIST } from '../data/market.js';
import { fetchLivePrices, fetchLiveIndices, applyLiveToStock } from '../data/live.js';
import { fmtWon, fmtPct, fmtNum, dirClass } from '../utils/format.js';

/* 아직 받아올 곳이 없는 시세 띠 항목 */
const FOOT_NOT_READY = ['달러 인덱스', '달러 환율', '나스닥', 'S&P 500', '필라델피아 반도체'];

/* ── 관심종목 사이드바 ───────────────────── */
export function mountWatchSide(el, { activeCode } = {}) {
  if (!el) return { update() {} };

  function render(priceMap) {
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

      ${WATCHLIST.map(s => {
        const live = priceMap && priceMap[s.code];
        const cls = live ? dirClass(live.pct) : 'kh-mut';
        return `
          <a class="kh-wl ${s.code === activeCode ? 'is-active' : ''}"
             href="./stock.html?code=${s.code}">
            <span class="kh-ic" style="background:${s.brand}">${s.name.slice(0, 2)}</span>
            <span class="kh-wl-name">${s.name}</span>
            <span class="kh-wl-price">
              <span class="kh-wl-v kh-num">${live ? fmtWon(live.price) : '—'}</span>
              <span class="kh-wl-c kh-num ${cls}">${live ? fmtPct(live.pct) : ''}</span>
            </span>
            <span class="kh-wl-heart">♡</span>
          </a>`;
      }).join('')}

      <div class="kh-side-add"><span class="plus">＋</span>추가하기</div>
    `;
  }

  render(null);
  return { update: render };
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

   1회 갱신에 드는 KIS 호출 = 지수 3 + 관심종목 수.
   서버 예산이 초당 1건(한도의 1/10)이라 15초 간격이면 예산 안에 든다.
   ────────────────────────────────────────────────────────────────────────── */
const REFRESH_MS = 15000;

export function startLiveLoop({ onPrices, onIndices } = {}) {
  const codes = WATCHLIST.map(s => s.code);

  async function tick() {
    if (document.hidden) return;          // 다른 탭을 보고 있으면 쉬어간다
    const [indices, prices] = await Promise.all([
      fetchLiveIndices(),
      fetchLivePrices(codes),
    ]);
    if (indices && onIndices) onIndices(indices);
    if (prices) {
      WATCHLIST.forEach(s => {
        const live = prices[s.code];
        if (live) applyLiveToStock(s, live);
      });
      if (onPrices) onPrices(prices);
    }
  }

  tick();
  setInterval(tick, REFRESH_MS);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
}
