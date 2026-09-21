/* ==========================================================================
   고른 종목 패널 — 투자자 정보 · AI 분석 · 종목 뉴스 (2026-09-21 지시)

   재권님 말씀 —

       여기 모달에 있는걸 홀딩스의 메인화면에서 가져다 쓴다
       투자자 정보 · ai분석 · 종목뉴스는 해당 ui 높이의 각각 1/3 을 차지한다

   ── 한 벌로 두는 이유 ──

   같은 셋이 **두 자리**에 나온다.

       첫 화면      차트 오른쪽 세로 칸
       모달·종목화면  오른쪽 열 (전에는 「뉴스·공시」와 「개인·외국인·기관」이 있던 자리)

   마크업을 양쪽 HTML 에 두면 한쪽만 고쳐져 갈라진다. 그래서 **이 파일이
   마크업까지 만든다** — 붙일 자리만 건네받는다. `stock-view.js` 가
   stock.html 을 원본으로 삼는 것과 같은 생각이다.

   ── 셋이 1/3씩 ──

   높이는 CSS 가 `grid-template-rows: 1fr 1fr 1fr` 로 나눈다. 글이 길어도
   칸은 안 늘어나고 **그 칸 안에서 굴러간다** — 오늘만 세 번 겪은
   「칸이 늘면 차트가 끌려간다」 를 구조로 막는다.
   ========================================================================== */

import { mountInvestor } from './investor.js';
import { mountAiAnalysis } from './ai-analysis.js';
import { mountStockNews } from './stock-news.js';

const HTML = `
  <div class="kh-p3-s kh-iv-s">
    <div class="kh-p3-h"><b>투자자 정보</b>
      <span class="kh-chips kh-iv-tabs">
        <button class="kh-chip is-active" data-view="today">오늘</button>
        <button class="kh-chip" data-view="days">5일</button>
      </span>
      <span class="kh-bd kh-bd-on">한국투자증권</span></div>
    <div class="kh-p3-b kh-iv-box">불러오는 중</div>
  </div>

  <div class="kh-p3-s kh-ai-s">
    <div class="kh-p3-h"><b>AI 분석</b>
      <span class="kh-bd kh-bd-on kh-ai-when">—</span></div>
    <div class="kh-p3-b kh-ai-box">불러오는 중</div>
  </div>

  <div class="kh-p3-s">
    <div class="kh-p3-h"><b>종목 뉴스</b>
      <span class="kh-bd kh-bd-on">네이버</span></div>
    <div class="kh-p3-b kh-nw-box">불러오는 중</div>
  </div>`;

/* ══ 칸 높이 끌어서 조절 (2026-09-21 지시) ══════════════════════

   재권님 말씀 —

       투자자정보랑 ai분석이랑 종목뉴스 **여기 칸별로 높이조절**하는거 진행해줘
       가르는 선에 마우스 올리면 종목들의 크기를 위아래로 조절 가능하도록

   ── px 이 아니라 **비율**로 기억한다 ──

   같은 한 벌이 **높이가 다른 두 자리**에 붙는다.

       첫 화면    패널 690px  →  칸 219씩
       모달·종목   패널 340px  →  칸 113씩

   첫 화면에서 한 칸을 400px 로 늘려 두고 모달을 열면 **340px 안에 400px
   칸이 들어간다.** 그래서 비율로 저장하고 각 자리에서 그 비율로 나눈다.

   ── 위아래 두 칸만 주고받는다 ──

   끌 때 나머지 한 칸은 안 건드린다. **그래서 패널 전체 높이가 안 움직인다** —
   루트 CLAUDE.md 「보는 것을 바꿔도 자리는 그대로다」 의 바깥 칸(`kh-card#2`,
   690px)이 그대로 남는다.

   ── 최소 58px ──

   한 칸이 0 이 되면 **머리줄까지 사라져 되돌릴 손잡이가 없어진다.**
   머리줄 22 + 안쪽여백 8 + 머리줄 아래 7 + 본문 한 줄 20 + 선 1 = 58
   (2026-09-21 실측). 머리줄과 본문 한 줄은 늘 보인다.

   ── 되돌리는 길 ──

   **선을 더블클릭하면 1:1:1 로 돌아간다.** 없으면 잘못 끌었을 때
   `localStorage` 에 그 상태가 남아 다음에 열어도 그대로다. */

const ROWS_KEY = 'kh.panel3.rows';
const MIN_PX = 58;
const GRAB_PX = 5;          // 선 위아래 이 범위 안이면 잡은 것으로 본다

/* **열려 있는 패널을 전부 들고 있는다.** 첫 화면 뒤에 모달이 뜨면 같은 셋이
   두 벌이라, 한쪽에서 끌면 다른 쪽도 같이 바뀌어야 한다. */
const MOUNTED = new Set();

function readRows() {
  try {
    const v = JSON.parse(localStorage.getItem(ROWS_KEY));
    if (Array.isArray(v) && v.length === 3 && v.every((n) => Number.isFinite(n) && n > 0)) return v;
  } catch { /* 사파리 사생활 보호 모드 등 — 기본값으로 간다 */ }
  return [1, 1, 1];
}

function writeRows(rows) {
  try { localStorage.setItem(ROWS_KEY, JSON.stringify(rows)); } catch { /* 못 써도 화면은 돈다 */ }
}

/* **비율은 옮겨 가는데 최소 높이는 안 따라간다** (2026-09-21 실측).

       첫 화면 690px 에서 58px 까지 줄인다   →  비율 0.252
       그 비율을 종목 화면 340px 에 주면      →  **28px**   머리줄이 잘린다

   그래서 **붙일 때 그 자리 높이로 다시 잰다.** 모자란 칸을 58 로 올리고
   그만큼을 여유 있는 칸에서 비례로 뺀다. 저장된 비율은 안 건드린다 —
   큰 자리로 돌아가면 원래 뜻이 그대로 살아나야 한다. */
function clampRows(el, rows) {
  /* **`clientHeight` 를 그대로 쓰면 안 된다** — 패딩을 포함한다.
     칸이 나뉘는 것은 **콘텐츠 상자**다. 첫 화면 패널이 `clientHeight` 690
     인데 위아래 패딩 16px 씩이라 실제로 나뉘는 높이는 **658** 이다.
     690 으로 재서 「58px 이니 괜찮다」 로 지나갔는데 화면은 55.3px 였다
     (2026-09-21 실측). 줄 사이 틈(`row-gap`)도 빼 둔다 — 지금은 0 이다. */
  const cs = getComputedStyle(el);
  const gap = (parseFloat(cs.rowGap) || 0) * (rows.length - 1);
  const H = el.clientHeight
    - (parseFloat(cs.paddingTop) || 0) - (parseFloat(cs.paddingBottom) || 0) - gap;
  if (!(H > 0) || H < MIN_PX * rows.length) return rows;   // 셋이 다 들어갈 자리가 없다
  const sum = rows.reduce((a, b) => a + b, 0) || 1;
  const px = rows.map((n) => (n / sum) * H);

  let debt = 0;
  px.forEach((h, i) => { if (h < MIN_PX) { debt += MIN_PX - h; px[i] = MIN_PX; } });
  if (debt > 0) {
    const spare = px.map((h) => Math.max(0, h - MIN_PX));
    const room = spare.reduce((a, b) => a + b, 0);
    if (room > 0) px.forEach((h, i) => { px[i] = h - debt * (spare[i] / room); });
  }
  return px.map((h) => (h / H) * rows.length);
}

function applyRows(el, rows) {
  el.style.gridTemplateRows = clampRows(el, rows)
    .map((n) => `${n.toFixed(4)}fr`).join(' ');
}

/** 열려 있는 모든 패널에 같은 비율을 준다 */
function applyAll(rows) {
  MOUNTED.forEach((el) => applyRows(el, rows));
}

/**
 * 끌어서 높이를 바꾸는 손잡이를 단다.
 * 손잡이는 CSS 의 `.kh-p3-s + .kh-p3-s::before` 라 **마크업이 안 늘어난다.**
 * 그 대신 「선 근처인가」 를 여기서 잰다.
 */
function mountResize(root) {
  const secs = () => [...root.querySelectorAll('.kh-p3-s')];

  /** 이 좌표가 어느 경계선 위인가 — 아니면 0 */
  function boundaryAt(y) {
    const ss = secs();
    for (let i = 1; i < ss.length; i += 1) {
      const top = ss[i].getBoundingClientRect().top;
      if (Math.abs(y - top) <= GRAB_PX) return i;
    }
    return 0;
  }

  /* 마우스를 올리면 선이 굵어지고 커서가 바뀐다.
     `::before` 는 `:hover` 를 못 쓰므로(의사요소 뒤에 의사클래스를 못 붙인다)
     여기서 클래스를 붙였다 뗀다. */
  function onMove(e) {
    if (root.dataset.dragging) return;
    const i = boundaryAt(e.clientY);
    secs().forEach((s, k) => s.classList.toggle('is-grab', k === i && i > 0));
  }
  function onLeave() {
    secs().forEach((s) => s.classList.remove('is-grab'));
  }

  function onDown(e) {
    const i = boundaryAt(e.clientY);
    if (!i) return;
    e.preventDefault();

    const ss = secs();
    const hs = ss.map((s) => s.getBoundingClientRect().height);
    const total = hs.reduce((a, b) => a + b, 0);
    const startY = e.clientY;
    root.dataset.dragging = '1';
    root.setPointerCapture(e.pointerId);

    let next = null;

    const move = (ev) => {
      /* **위아래 두 칸만 주고받는다.** 남은 한 칸은 그대로다 */
      let dy = ev.clientY - startY;
      dy = Math.max(MIN_PX - hs[i - 1], Math.min(hs[i] - MIN_PX, dy));
      const now = hs.slice();
      now[i - 1] = hs[i - 1] + dy;
      now[i] = hs[i] - dy;
      next = now.map((h) => (h / total) * 3);   // 합이 3 이 되게 — 1:1:1 이 기본
      applyRows(root, next);
    };
    const up = (ev) => {
      root.releasePointerCapture(ev.pointerId);
      delete root.dataset.dragging;
      root.removeEventListener('pointermove', move);
      root.removeEventListener('pointerup', up);
      root.removeEventListener('pointercancel', up);
      if (next) { writeRows(next); applyAll(next); }
    };
    root.addEventListener('pointermove', move);
    root.addEventListener('pointerup', up);
    root.addEventListener('pointercancel', up);
  }

  /* 선을 더블클릭하면 1:1:1 로 되돌린다 */
  function onDbl(e) {
    if (!boundaryAt(e.clientY)) return;
    e.preventDefault();
    const base = [1, 1, 1];
    writeRows(base);
    applyAll(base);
  }

  root.addEventListener('pointermove', onMove);
  root.addEventListener('pointerleave', onLeave);
  root.addEventListener('pointerdown', onDown);
  root.addEventListener('dblclick', onDbl);

  /* **자리 높이가 바뀌면 최소 58px 을 다시 잰다.** 모달은 숨은 채로 붙을 수
     있어 그때는 `clientHeight` 가 0 이다 — 보일 때 여기서 잡힌다.
     `grid-template-rows` 는 root 높이를 안 바꾸므로 되돌이가 안 생긴다. */
  let ro = null;
  if (typeof ResizeObserver === 'function') {
    ro = new ResizeObserver(() => {
      if (!root.dataset.dragging) applyRows(root, readRows());
    });
    ro.observe(root);
  }

  return () => {
    if (ro) ro.disconnect();
    root.removeEventListener('pointermove', onMove);
    root.removeEventListener('pointerleave', onLeave);
    root.removeEventListener('pointerdown', onDown);
    root.removeEventListener('dblclick', onDbl);
  };
}

/**
 * 셋을 한 칸에 그린다.
 *   root : 이 안에 마크업을 만든다 (.kh-p3)
 * setCode(code) 로 종목을 바꾸고, destroy() 로 끝낸다.
 */
export function mountStockPanel(root, { code = null } = {}) {
  if (!root) return { setCode() {}, destroy() {} };

  root.classList.add('kh-p3');
  root.innerHTML = HTML;

  applyRows(root, readRows());
  MOUNTED.add(root);
  const unResize = mountResize(root);

  /* **id 를 쓰지 않는다.** 첫 화면과 모달이 동시에 떠 있으면 같은 id 가
     둘이 되어 엉뚱한 칸을 칠한다. 각자 제 root 안에서만 찾는다. */
  const q = (sel) => root.querySelector(sel);

  const investor = mountInvestor({ box: q('.kh-iv-box'), tabs: q('.kh-iv-tabs') });
  const ai = mountAiAnalysis({ box: q('.kh-ai-box'), when: q('.kh-ai-when') });
  const news = mountStockNews(q('.kh-nw-box'), { limit: 8 });

  if (code) { investor.setCode(code); ai.setCode(code); news.setCode(code); }

  return {
    setCode(next) {
      if (!next) return;
      investor.setCode(next);
      ai.setCode(next);
      news.setCode(next);
    },
    destroy() {
      investor.destroy();
      ai.destroy();
      if (news.destroy) news.destroy();
      MOUNTED.delete(root);
      unResize();
    },
  };
}
