/* ==========================================================================
   KJC Holdings — 차트 그리기 도구(추세선 · 수평선 · 지우개)

   재권님 2026-10-15 17:59 「차트에서 여기처럼 왼쪽 위에 추세선 그리는것과 수평선 그리는게 있는게 이게 필요해 지우는 버튼도」
   → 시안 둘 → 18:1x 「오른쪽 위에가 더 좋겠는데, 칸은 좀더 작게」 → 「응 좋아」.

   자리   가격 칸 안 오른쪽 위(가격축 바로 왼쪽)에 겹쳐 얹는다 — 칸 크기 · 배치는 그대로
   단추   추세선 — 차트를 두 번 눌러 두 점 · 수평선 — 한 번 눌러 그 가격 · 지우개 — 켜고 선을 누르면 그 선 하나 ·
          휴지통 — 이 종목에 그린 것 전부 (재권님 11-05 13:1x 「추세선 한꺼번에 지우는거랑 지우개 버튼 만들어서 클릭하면
          추세선과 저항선 지울수 있게」 — 한꺼번에 지우기는 휴지통이 이미 하고 있어 그대로 두고 지우개를 더함)
          고른 단추는 다시 누르거나 Esc 를 누를 때까지 켜져 있다 — 이어서 여러 줄을 긋는다
          (재권님 18:2x 「첫번째 추세선 그리고 두번째 그리는데 안그려져」 — 앞에는 한 줄을 그으면 저절로 꺼졌다)
   미리 보기  추세선 첫 점을 찍은 뒤(또는 끄는 동안) 마우스가 있는 봉까지 점선이 따라 그려지고 둘째 점을 찍으면 굳는다
          (재권님 11-05 10:3x 「차트에 선그릴때 클릭후 마우스 이동하면 이동하는 곳에 맞춰서 선이 미리 보여지게」).
          수평선은 한 번에 그어지고 십자선 가로줄이 이미 그 자리를 보여 따로 두지 않는다
   빈칸     차트 오른쪽 봉 없는 빈칸(미래 쪽)에도 점을 찍는다 — 선은 두 점 사이만
          (재권님 11-05 13:1x 「추세선 그리는거 차트 안그려진곳까지도 그려지도록」 → 「가」).
          빈칸의 점은 「그때 마지막 봉 시각 + 몇 봉 뒤」 로 적는다 — 봉 칸 수라 **찍은 주기에서만** 그린다(다른 주기에서는 그 자리를 모른다).
          그래서 추세선 · 첫 점 · 미리 보기는 라이브러리 선이 아니라 칸 위 덧그림 캔버스에 긋는다(일목 구름과 같은 길 ·
          logicalToCoordinate) — 라이브러리 선에 미래 시각을 넣으면 시간축이 늘어 봉 자리가 움직인다. 세로 범위는 안 건드린다
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
  eraser: '<svg width="14" height="14" viewBox="0 0 18 18" aria-hidden="true"><path d="M10.5 3.5l4 4-7 7H4.5l-2-2z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M7 7l4 4M8 14.5h7" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
  erase: '<svg width="14" height="14" viewBox="0 0 18 18" aria-hidden="true"><path d="M3 5h12M7 5V3h4v2M5 5l1 10h6l1-10" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
};
const TIP = {
  trend: '추세선 — 차트를 두 번 눌러 두 점을 잇습니다',
  hline: '수평선 — 누른 자리 가격에 가로선을 긋습니다',
  eraser: '지우개 — 누른 추세선 · 수평선 하나만 지웁니다',
  erase: '이 종목에 그린 선을 모두 지웁니다',
};

let mode = null;          // 'trend' · 'hline' · 'eraser' · null — 칸을 다시 만들어도 이어진다
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
  const drawn = { h: [] };            // 그린 수평선(라이브러리 것) — 지울 때 쓴다
  let ghostTo = null;                 // 미리 보기 점선의 끝(마우스 자리 점) — 첫 점(또는 누른 자리)에서 여기까지
  let ghostFrom = null;
  const box = pane.querySelector('.kh-pane-box') || pane;
  /* 추세선 · 첫 점(재권님 「클릭하면 점 나오고 다시 클릭하면 연결」) · 미리 보기를 긋는 덧그림 — 칸 크기는 그대로 */
  const cv = document.createElement('canvas');
  cv.className = 'kh-draw-cv';
  box.appendChild(cv);

  const bar = document.createElement('div');
  bar.className = 'kh-draw';
  bar.style.right = (axisW + 6) + 'px';
  bar.innerHTML = Object.keys(ICON).map((k) =>
    `<button type="button" class="kh-draw-b" data-draw="${k}" title="${TIP[k]}" aria-label="${TIP[k]}">${ICON[k]}</button>`).join('');
  pane.appendChild(bar);

  const paintBar = () => {
    bar.querySelectorAll('[data-draw]').forEach((b) => b.classList.toggle('is-on', b.dataset.draw === mode));
    pane.classList.toggle('kh-drawing', !!mode);
    pane.classList.toggle('kh-erasing', mode === 'eraser');
  };

  function clearGhost() { ghostFrom = null; ghostTo = null; paint(); }


  function clearFirst() {
    pend = null;
    clearGhost();
  }

  /* 적어 둔 점 → 지금 봉 줄의 논리 자리(봉 번호 · 빈칸이면 마지막 봉 번호보다 크다). 못 정하면 -1 */
  function idxOf(pt) {
    if (!pt) return -1;
    const base = snap(candles, pt.ts);
    if (base < 0) return -1;
    if (!pt.k) return base;
    return pt.per === period ? base + pt.k : -1;     // 빈칸 점은 찍은 주기에서만
  }

  /* 덧그림 — 그릴 것이 바뀌었거나 끌기 · 확대 · 칸 크기가 바뀌면 다시 긋는다 */
  /* 쉬는 동안 값싸게 — 그릴 것이 바뀌면 ver 를 올리고(paint), 돌기는 숫자 몇 개만 견준다.
     그릴 것이 없으면(추세선 · 첫 점 · 미리 보기 다 없음) 한 번 비우고 아무것도 안 잰다
     (qa 검수 11-05 13:4x — 서명을 JSON 으로 매 그림 세어 가만히 둔 화면 10초에 브라우저 일이 0.1 → 0.44초) */
  let sig = '';
  let ver = 0;
  let empty = false;
  function paint() {
    ver++;
    redraw();
  }
  function redraw() {
    if (!cv.isConnected) return;
    const none = !data.t.length && !(mode === 'trend' && (pend || ghostTo));
    if (none) {
      if (!empty) { const c = cv.getContext('2d'); c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, cv.width, cv.height); empty = true; sig = ''; }
      return;
    }
    empty = false;
    const W = box.clientWidth, H = box.clientHeight, dpr = window.devicePixelRatio || 1;
    let tsc, lr;
    try { tsc = chart.timeScale(); lr = tsc.getVisibleLogicalRange(); } catch { return; }
    let y0 = null, y1 = null;
    try { y0 = series.coordinateToPrice(0); y1 = series.coordinateToPrice(H); } catch { /* 아직 */ }
    const s2 = [W, H, dpr, lr && lr.from, lr && lr.to, y0, y1, ver].join('|');
    if (s2 === sig) return;
    sig = s2;
    if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) {
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      cv.style.width = W + 'px'; cv.style.height = H + 'px';
    }
    const ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const xy = (i, p) => {
      try {
        const x = tsc.logicalToCoordinate(i), y = series.priceToCoordinate(p);
        return x == null || y == null ? null : [x, y];
      } catch { return null; }
    };
    ctx.save();
    ctx.beginPath(); ctx.rect(0, 0, Math.max(0, W - axisW), H); ctx.clip();
    const dotAt = (q, c) => { ctx.fillStyle = c; ctx.beginPath(); ctx.arc(q[0], q[1], DOT_R, 0, Math.PI * 2); ctx.fill(); };
    const seg = (a, b, c, dash) => {
      ctx.strokeStyle = c; ctx.lineWidth = 2; ctx.setLineDash(dash ? [6, 4] : []);
      ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); ctx.setLineDash([]);
    };
    data.t.forEach((t) => {
      const ia = idxOf(t.a), ib = idxOf(t.b);
      if (ia < 0 || ib < 0 || ia === ib) return;     // 받아 둔 봉 밖 · 같은 봉 · 다른 주기의 빈칸 점 — 긋지 않는다
      const a = xy(ia, t.a.p), b = xy(ib, t.b.p);
      if (!a || !b) return;
      const c = inkOf(t.c);
      seg(a, b, c, false); dotAt(a, c); dotAt(b, c);
    });
    if (mode === 'trend') {
      const fi = idxOf(ghostFrom || pend);
      const f = fi >= 0 ? xy(fi, (ghostFrom || pend).p) : null;
      if (f && ghostTo) {
        const gi = idxOf(ghostTo);
        const g = gi >= 0 && gi !== fi ? xy(gi, ghostTo.p) : null;
        if (g) seg(f, g, inkOf(nextC()), true);     // 미리 보기는 점선 · 다음에 그을 색
      }
      if (f && pend) dotAt(f, ink);                 // 첫 점
    }
    ctx.restore();
  }
  /* 다시 긋는 때 — 끌기 · 확대(시간축 범위) · 칸 크기 · 칸 위 마우스(세로축 끌기 · 휠 포함) · 새 봉.
     매 그림 돌지 않는다(qa 검수 11-05 13:4x — 선이 있으면 가만히 둔 화면 10초에 브라우저 일이 0.1 → 0.45초). 한 그림에 한 번으로 묶는다 */
  let qRaf = 0;
  const queue = () => { if (!qRaf) qRaf = requestAnimationFrame(() => { qRaf = 0; redraw(); }); };
  let ro = null;
  try { chart.timeScale().subscribeVisibleLogicalRangeChange(queue); } catch { /* 칸이 사라졌다 */ }
  try { ro = new ResizeObserver(queue); ro.observe(box); } catch { /* 없으면 크기 바뀔 때 못 따라간다 */ }
  ['pointermove', 'wheel', 'pointerup'].forEach((t) => pane.addEventListener(t, queue, { passive: true }));

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
    } catch { drawn.h.push(null); /* 칸이 막 사라졌다 — 자리만 맞춰 둔다(지우개가 data.h 와 같은 번호로 지운다) */ }
  }

  data.h.forEach(addH);
  if (mode === 'trend' && pend && idxOf(pend) < 0) pend = null;   // 칸이 다시 만들어졌다 — 찍어 둔 첫 점은 덧그림이 다시 보인다

  /* 누르기는 차트 라이브러리의 클릭이 아니라 칸에서 직접 받는다 (재권님 18:3x 「선끼리 크로스 시키면 안그려지는데」).
     라이브러리 클릭은 누르는 사이 손이 조금만 움직여도 「끌기」 로 읽혀 안 온다 — 그리는 동안은 차트 끌기 · 확대를 멈추고
     눌렀다 뗀 자리를 직접 잰다. 끌어서 긋는 것도 된다(누른 자리 → 뗀 자리) */
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

  /* 칸 안 좌표 → { i(봉 자리), k(마지막 봉 뒤 몇 봉 — 오른쪽 빈칸), p(가격) } — 왼쪽 봉 밖은 i · k 가 다 null */
  function at(e) {
    const r = box.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    let p = null, time = null, lg = null;
    try { p = series.coordinateToPrice(y); time = chart.timeScale().coordinateToTime(x); lg = chart.timeScale().coordinateToLogical(x); } catch { /* 칸이 사라졌다 */ }
    let i = time != null ? idxOfTime(time) : null;
    let k = null;
    const last = candles.length - 1;
    if (i == null && lg != null && Math.round(lg) > last) k = Math.round(lg) - last;   // 오른쪽 빈칸
    return { i: i == null ? null : i, k, p: p != null && Number.isFinite(p) ? p : null, x: e.clientX, y: e.clientY };
  }

  function pointAt(q) {
    if (q.p == null || !candles.length) return null;
    if (q.i != null) return { ts: String(candles[q.i].ts), p: q.p };
    if (q.k) return { ts: String(candles[candles.length - 1].ts), k: q.k, per: period, p: q.p };
    return null;
  }

  function trend(a, b) {
    const t = { a, b, c: nextC() };
    clearFirst();
    data.t.push(t);
    save(code, data);
    paint();
  }

  let down = null;
  const onDown = (e) => {
    if (!mode || bar.contains(e.target) || (e.pointerType === 'mouse' && e.button !== 0)) return;
    const r = box.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right - axisW || e.clientY < r.top || e.clientY > r.bottom) return;   // 가격축 · 칸 밖은 아니다
    down = at(e);
    e.preventDefault();
  };
  const onMove = (e) => {
    if (mode !== 'trend') return;
    const from = pend || (down ? pointAt(down) : null);
    if (!from) return;
    ghostFrom = pend ? null : from;
    ghostTo = pointAt(at(e));
    paint();                                         // 미리 보기
  };
  const onUp = (e) => {
    if (!down || !mode) { down = null; return; }
    const d = down, u = at(e);
    down = null;
    clearGhost();
    if (mode === 'eraser') { eraseAt(u); return; }
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
    if (!pend) { pend = pt; paint(); return; }
    trend(pend, pt);
  };

  /* 지우개 — 누른 자리에서 HIT px 안에 있는 선 중 가장 가까운 하나를 지운다. 없으면 아무것도 안 한다 */
  const HIT = 6;
  function eraseAt(u) {
    const r = box.getBoundingClientRect();
    const x = u.x - r.left, y = u.y - r.top;
    let best = null;
    const take = (kind, i, dist) => { if (dist <= HIT && (!best || dist < best.dist)) best = { kind, i, dist }; };
    data.h.forEach((h, i) => {
      let hy = null;
      try { hy = series.priceToCoordinate(hOf(h).p); } catch { /* 칸이 사라졌다 */ }
      if (hy != null) take('h', i, Math.abs(hy - y));
    });
    let tsc = null;
    try { tsc = chart.timeScale(); } catch { /* 칸이 사라졌다 */ }
    data.t.forEach((t, i) => {
      const ia = idxOf(t.a), ib = idxOf(t.b);
      if (!tsc || ia < 0 || ib < 0 || ia === ib) return;     // 지금 안 보이는 선은 못 누른다
      let ax, ay, bx, by;
      try { ax = tsc.logicalToCoordinate(ia); ay = series.priceToCoordinate(t.a.p); bx = tsc.logicalToCoordinate(ib); by = series.priceToCoordinate(t.b.p); } catch { return; }
      if ([ax, ay, bx, by].some((v) => v == null)) return;
      const dx = bx - ax, dy = by - ay, L2 = dx * dx + dy * dy;
      const k = L2 ? Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / L2)) : 0;
      take('t', i, Math.hypot(x - (ax + k * dx), y - (ay + k * dy)));
    });
    if (!best) return;
    if (best.kind === 'h') {
      const l = drawn.h[best.i];
      if (l) { try { series.removePriceLine(l); } catch { /* 이미 사라짐 */ } }
      drawn.h.splice(best.i, 1);
      data.h.splice(best.i, 1);
    } else {
      data.t.splice(best.i, 1);
    }
    save(code, data);
    paint();
  }

  function eraseAll() {
    clearFirst();
    drawn.h.forEach((l) => { if (l) { try { series.removePriceLine(l); } catch { /* 이미 사라짐 */ } } });
    drawn.h = [];
    data = { h: [], t: [] };
    save(code, data);
    paint();
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
  pane.addEventListener('pointermove', onMove, true);
  window.addEventListener('pointerup', onUp, true);
  nav(!mode);
  paintBar();
  paint();

  return {
    destroy() {
      pane.removeEventListener('pointerdown', onDown, true);
      pane.removeEventListener('pointermove', onMove, true);
      window.removeEventListener('pointerup', onUp, true);
      if (qRaf) cancelAnimationFrame(qRaf);
      try { chart.timeScale().unsubscribeVisibleLogicalRangeChange(queue); } catch { /* 칸이 사라졌다 */ }
      if (ro) ro.disconnect();
      ['pointermove', 'wheel', 'pointerup'].forEach((t) => pane.removeEventListener(t, queue));
      cv.remove();
      document.removeEventListener('keydown', onKey);
      bar.remove();
      pane.classList.remove('kh-drawing', 'kh-erasing');
    },
  };
}
