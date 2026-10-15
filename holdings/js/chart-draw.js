/* ==========================================================================
   KJC Holdings — 차트 그리기 도구(추세선 · 수평선 · 지우개)

   재권님 2026-10-15 17:59 「차트에서 여기처럼 왼쪽 위에 추세선 그리는것과 수평선 그리는게 있는게 이게 필요해 지우는 버튼도」
   → 시안 둘 → 18:1x 「오른쪽 위에가 더 좋겠는데, 칸은 좀더 작게」 → 「응 좋아」.

   자리   가격 칸 안 오른쪽 위(가격축 바로 왼쪽)에 겹쳐 얹는다 — 칸 크기 · 배치는 그대로
   단추   추세선 — 차트를 두 번 눌러 두 점 · 수평선 — 한 번 눌러 그 가격 · 지우개 — 이 종목에 그린 것 전부
          고른 단추는 다시 누르거나 Esc 를 누를 때까지 켜져 있다 — 이어서 여러 줄을 긋는다
          (재권님 18:2x 「첫번째 추세선 그리고 두번째 그리는데 안그려져」 — 앞에는 한 줄을 그으면 저절로 꺼졌다)
   기억   종목마다 브라우저에 둔다(localStorage · 「값을 들고 있는 것」). 주기를 바꿔도 같은 선이 보인다 —
          점은 봉 시각(서버 ts)으로 적어 두고 그릴 때 지금 주기의 그 시각 봉에 붙인다.
          지금 받아 둔 봉 밖에 있는 점이 있으면 그 추세선은 그리지 않는다(지어낸 자리에 긋지 않는다)

   쓰는 법(chart.js 의 build() 안에서만)
     mountDraw({ pane, chart, series, code, period, candles, timeOf, idxOfTime, axisW, LC })
     → { destroy() } — 칸을 다시 만들 때마다 앞 것을 지우고 새로 붙인다. 고른 단추는 종목이 같으면 이어진다
   ========================================================================== */

import { color } from './theme.js';

const KEY = (code) => `kh.chartDraw.${code}`;
const DOT_R = 2;          // 점 반지름(px) — 재권님 18:2x 「점은 지금보다 작게」(라이브러리 기본은 선 굵기에 따라 더 컸다)
const H_WIDTH = 2;        // 수평선 굵기(px) — 재권님 18:2x 「수평선은 지금보다 2배 굵게」(앞 1)
const CSS_HREF = new URL('../css/chart-draw.css', import.meta.url).href;

/* 단추 꼴 — 선 색은 글자색(currentColor)을 따른다 */
const ICON = {
  trend: '<svg width="14" height="14" viewBox="0 0 18 18" aria-hidden="true"><line x1="3" y1="15" x2="15" y2="3" stroke="currentColor" stroke-width="1.6"/><circle cx="3" cy="15" r="2" fill="currentColor"/><circle cx="15" cy="3" r="2" fill="currentColor"/></svg>',
  hline: '<svg width="14" height="14" viewBox="0 0 18 18" aria-hidden="true"><line x1="1" y1="9" x2="17" y2="9" stroke="currentColor" stroke-width="1.6"/><circle cx="9" cy="9" r="2" fill="currentColor"/></svg>',
  erase: '<svg width="14" height="14" viewBox="0 0 18 18" aria-hidden="true"><path d="M3 5h12M7 5V3h4v2M5 5l1 10h6l1-10" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
};
const TIP = {
  trend: '추세선 — 차트를 두 번 눌러 두 점을 잇습니다',
  hline: '수평선 — 누른 자리 가격에 가로선을 긋습니다',
  erase: '이 종목에 그린 선을 모두 지웁니다',
};

let mode = null;          // 'trend' · 'hline' · null — 칸을 다시 만들어도 이어진다
let modeCode = null;
let pend = null;          // 추세선 첫 점 { ts, p } — 두 번 누르는 사이에 칸이 다시 만들어져도(시세 갱신) 이어진다

function ensureCss() {
  if (document.querySelector(`link[href="${CSS_HREF}"]`)) return;
  const l = document.createElement('link');
  l.rel = 'stylesheet';
  l.href = CSS_HREF;
  document.head.appendChild(l);
}

function load(code) {
  try {
    const v = JSON.parse(localStorage.getItem(KEY(code)) || 'null');
    return v && Array.isArray(v.h) && Array.isArray(v.t) ? v : { h: [], t: [] };
  } catch { return { h: [], t: [] }; }
}

function save(code, v) {
  try {
    if (!v.h.length && !v.t.length) localStorage.removeItem(KEY(code));
    else localStorage.setItem(KEY(code), JSON.stringify(v));
  } catch { /* 저장이 막힌 창(사생활 모드 등) — 이번 화면에서만 보인다 */ }
}

/* 봉 시각(서버 ts) 끼리 견주려고 12자리로 맞춘다 — 일봉 '20261015' · 5분봉 '202610150905' */
const norm = (ts) => String(ts).padEnd(12, '0').slice(0, 12);

/* 적어 둔 ts 를 지금 봉 줄의 자리로 — 그 시각을 넘지 않는 마지막 봉. 받아 둔 봉 밖이면 -1 */
function snap(candles, ts) {
  const k = norm(ts);
  if (!candles.length || k < norm(candles[0].ts)) return -1;
  let lo = 0, hi = candles.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (norm(candles[mid].ts) <= k) lo = mid; else hi = mid - 1;
  }
  /* 마지막 봉보다 뒤(다른 주기에서 오늘 더 늦은 시각에 찍음)는 마지막 봉에 붙인다 — 같은 날 안이면 */
  if (lo === candles.length - 1 && k.slice(0, 8) > norm(candles[lo].ts).slice(0, 8)) return -1;
  return lo;
}

export function mountDraw({ pane, chart, series, code, period, candles, timeOf, idxOfTime, axisW, LC }) {
  if (!pane || !chart || !series || !code) return { destroy() {} };
  ensureCss();
  if (modeCode !== code) { mode = null; pend = null; modeCode = code; }

  const ink = color('accent');           // 고른 단추 · 첫 점
  /* 선 색 — 그을 때마다 1 → 5 → 다시 1(추세선 · 수평선 함께 센다 · 지우개 뒤에는 1 부터). 색 값은 theme.css 의 --kh-draw-1~5
     (재권님 18:3x 「그릴때마다 색이 5개가 다르게 나오게 해줘 5개 다 되면 다시 1번으로」 — 앞서 「수평선은 검은색으로」 는 1번이 검정이다) */
  const DRAW_N = 5;
  const inkOf = (c) => color(`draw-${((c || 0) % DRAW_N) + 1}`);
  const nextC = () => (data.h.length + data.t.length) % DRAW_N;
  /* 수평선 한 칸 — 옛 저장(숫자만)도 받는다 */
  const hOf = (x) => (typeof x === 'number' ? { p: x, c: 0 } : x);
  let data = load(code);
  const drawn = { h: [], t: [] };     // 그린 선(라이브러리 것) — 지울 때 쓴다
  let firstMark = null;               // 첫 점 — 눌렀다는 표시로 그 자리에 점 하나(재권님 「클릭하면 점 나오고 다시 클릭하면 연결」)

  const bar = document.createElement('div');
  bar.className = 'kh-draw';
  bar.style.right = (axisW + 6) + 'px';
  bar.innerHTML = Object.keys(ICON).map((k) =>
    `<button type="button" class="kh-draw-b" data-draw="${k}" title="${TIP[k]}" aria-label="${TIP[k]}">${ICON[k]}</button>`).join('');
  pane.appendChild(bar);

  const paintBar = () => {
    bar.querySelectorAll('[data-draw]').forEach((b) => b.classList.toggle('is-on', b.dataset.draw === mode));
    pane.classList.toggle('kh-drawing', !!mode);
  };

  function clearFirst() {
    pend = null;
    if (firstMark) { try { chart.removeSeries(firstMark); } catch { /* 이미 사라짐 */ } firstMark = null; }
  }

  function setMode(m) {
    mode = mode === m ? null : m;
    clearFirst();
    nav(!mode);
    paintBar();
  }

  function addH(x) {
    const { p, c } = hOf(x);
    try {
      drawn.h.push(series.createPriceLine({
        price: p, color: inkOf(c), lineWidth: H_WIDTH, lineStyle: LC.LineStyle.Solid, axisLabelVisible: true, title: '',
      }));
    } catch { /* 칸이 막 사라졌다 */ }
  }

  function addT(t) {
    const ia = snap(candles, t.a.ts), ib = snap(candles, t.b.ts);
    if (ia < 0 || ib < 0 || ia === ib) return;     // 받아 둔 봉 밖 · 같은 봉 — 긋지 않는다
    const [x, y] = ia < ib ? [t.a, t.b] : [t.b, t.a];
    const [i0, i1] = ia < ib ? [ia, ib] : [ib, ia];
    try {
      const s = chart.addSeries(LC.LineSeries, {
        color: inkOf(t.c), lineWidth: 2, lastValueVisible: false, priceLineVisible: false,
        crosshairMarkerVisible: false, pointMarkersVisible: true, pointMarkersRadius: DOT_R,
        autoscaleInfoProvider: () => null,          // 그린 선이 세로 범위를 움직이지 않게
      });
      s.setData([{ time: timeOf(i0), value: x.p }, { time: timeOf(i1), value: y.p }]);
      drawn.t.push(s);
    } catch { /* 칸이 막 사라졌다 */ }
  }

  data.h.forEach(addH);
  data.t.forEach(addT);
  if (mode === 'trend' && pend) {              // 칸이 다시 만들어졌다 — 찍어 둔 첫 점을 다시 보인다
    const i = snap(candles, pend.ts);
    if (i >= 0) showFirst(timeOf(i), pend.p); else pend = null;
  }

  /* 누르기는 차트 라이브러리의 클릭이 아니라 칸에서 직접 받는다 (재권님 18:3x 「선끼리 크로스 시키면 안그려지는데」).
     라이브러리 클릭은 누르는 사이 손이 조금만 움직여도 「끌기」 로 읽혀 안 온다 — 그리는 동안은 차트 끌기 · 확대를 멈추고
     눌렀다 뗀 자리를 직접 잰다. 끌어서 긋는 것도 된다(누른 자리 → 뗀 자리) */
  const box = pane.querySelector('.kh-pane-box') || pane;
  /* 깊은 사본으로 쥔다 — `chart.options()` 가 돌려주는 객체는 라이브러리 안의 것 그대로라, 끌 때 같이 false 로 바뀌어
     되돌릴 값이 사라졌다(qa 검수 18:5x — 켰다 끄면 큰 차트가 안 끌림 · 18:5x 직접 재서 확인) */
  const keepNav = (() => { try { const o = chart.options(); return JSON.parse(JSON.stringify({ handleScroll: o.handleScroll, handleScale: o.handleScale })); } catch { return null; } })();
  /* 끄는 값도 같은 모양의 객체에 false 를 채워 준다 — 켤 때 그 객체를 그대로 돌려 끼운다 */
  const allOff = (o) => (o && typeof o === 'object'
    ? Object.fromEntries(Object.entries(o).map(([k, v]) => [k, allOff(v)])) : false);
  const navOff = keepNav ? { handleScroll: allOff(keepNav.handleScroll), handleScale: allOff(keepNav.handleScale) } : null;
  const nav = (on) => {
    if (!keepNav) return;
    try { chart.applyOptions(on ? keepNav : navOff); } catch { /* 칸이 사라졌다 */ }
  };

  /* 칸 안 좌표 → { i(봉 자리), time, p(가격) } — 봉이 없는 자리(오른쪽 빈칸)는 i 가 null */
  function at(e) {
    const r = box.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    let p = null, time = null;
    try { p = series.coordinateToPrice(y); time = chart.timeScale().coordinateToTime(x); } catch { /* 칸이 사라졌다 */ }
    const i = time != null ? idxOfTime(time) : null;
    return { i: i == null ? null : i, time, p: p != null && Number.isFinite(p) ? p : null, x: e.clientX, y: e.clientY };
  }

  function pointAt(q) { return q.i == null || q.p == null ? null : { ts: String(candles[q.i].ts), p: q.p }; }

  function trend(a, b) {
    const t = { a, b, c: nextC() };
    clearFirst();
    data.t.push(t);
    save(code, data);
    addT(t);
  }

  let down = null;
  const onDown = (e) => {
    if (!mode || bar.contains(e.target) || (e.pointerType === 'mouse' && e.button !== 0)) return;
    const r = box.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right - axisW || e.clientY < r.top || e.clientY > r.bottom) return;   // 가격축 · 칸 밖은 아니다
    down = at(e);
    e.preventDefault();
  };
  const onUp = (e) => {
    if (!down || !mode) { down = null; return; }
    const d = down, u = at(e);
    down = null;
    if (mode === 'hline') {
      if (u.p == null) return;
      const h = { p: u.p, c: nextC() };
      data.h.push(h);
      save(code, data);
      addH(h);
      return;
    }
    const dragged = Math.hypot(u.x - d.x, u.y - d.y) > 6;
    if (dragged) {                                   // 끌어서 그음 — 누른 자리에서 뗀 자리까지
      const a = pointAt(d), b = pointAt(u);
      if (a && b) trend(a, b);
      return;
    }
    const pt = pointAt(u);
    if (!pt) return;                                 // 봉 없는 빈자리
    if (!pend) { pend = pt; showFirst(u.time, pt.p); return; }
    trend(pend, pt);
  };

  function showFirst(time, p) {
    try {
      firstMark = chart.addSeries(LC.LineSeries, {
        color: ink, lineVisible: false, lastValueVisible: false, priceLineVisible: false,
        crosshairMarkerVisible: false, pointMarkersVisible: true, pointMarkersRadius: DOT_R,
        autoscaleInfoProvider: () => null,
      });
      firstMark.setData([{ time, value: p }]);
    } catch { /* 없어도 된다 — 둘째 점에서 그대로 이어진다 */ }
  }

  function eraseAll() {
    clearFirst();
    drawn.h.forEach((l) => { try { series.removePriceLine(l); } catch { /* 이미 사라짐 */ } });
    drawn.t.forEach((s) => { try { chart.removeSeries(s); } catch { /* 이미 사라짐 */ } });
    drawn.h = []; drawn.t = [];
    data = { h: [], t: [] };
    save(code, data);
    mode = null;
    nav(true);
    paintBar();
  }

  const onBar = (e) => {
    const b = e.target.closest('[data-draw]');
    if (!b) return;
    e.stopPropagation();
    if (b.dataset.draw === 'erase') eraseAll(); else setMode(b.dataset.draw);
  };
  const onKey = (e) => { if (e.key === 'Escape' && mode) { mode = null; clearFirst(); nav(true); paintBar(); } };

  bar.addEventListener('click', onBar);
  document.addEventListener('keydown', onKey);
  pane.addEventListener('pointerdown', onDown, true);
  window.addEventListener('pointerup', onUp, true);
  nav(!mode);
  paintBar();

  return {
    destroy() {
      pane.removeEventListener('pointerdown', onDown, true);
      window.removeEventListener('pointerup', onUp, true);
      document.removeEventListener('keydown', onKey);
      bar.remove();
      pane.classList.remove('kh-drawing');
    },
  };
}
