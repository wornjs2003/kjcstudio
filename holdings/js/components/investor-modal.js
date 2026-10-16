/* ==========================================================================
   투자자 지표 모달 — 투자자 정보 칸의 「자세히 ›」 (2026-10-15)

   재권님 말씀 —
       「투자자 지표 모달 켜면 이런 모양(양방향 막대)으로 · 거래대금 순으로 위에서 아래로 ·
         차트로 보는 거는 종목이나 코스피 코스닥의 일봉 월봉 분봉이 보여야 하고 보여지는 기간이나
         체크한 기간 동안 투자자별로 거래가 얼마나 되는지」(개발 경유)
       「하나의 모달로 합쳐 · 투자자 지표 이름에 그래프 차트 이렇게 구분 · 실시간 순위를 옆에
         접었다 폈다 · 해당 종목 누르면 그 차트」
       「버튼이 있고 누르면 실시간 순위 · 홀딩스 메인 구성된 거 그대로 가져와서 거기 넣어」
       「화면 확장하면 모달창이 확장된 만큼 가로로 넓어지게」
       「차트를 눌렀을 때 양방향 그래프로 해당 종목의 개인 기관 외국인 · 선택된 목록은 필요 없어 ·
         차트에서 점선 네모를 칠 수 있게 · 이 안에 있는 기간 동안의 값 · 투자자 지표 옆에 종목 검색」

   ── 탭 둘 ──
       그래프   거래대금 순 종목들 — 왼쪽 매도 · 오른쪽 매수 · 가운데 순매수. 개인 · 외국인 · 기관 · 기간을 고른다
       차트     고른 종목(또는 코스피 · 코스닥)의 분 · 일 · 월봉 + 아래 그 종목의 개인 · 외국인 · 기관 양쪽 막대.
                기간은 **점선 네모로 고른 구간**, 안 골랐으면 **차트에 보이는 구간**이다

   ── 실시간 순위 ──
   공용 모달의 오른쪽 서랍 손잡이(▶)로 연다. 내용은 **홈 실시간 순위 칸(.kh-rank-card) 그 자체**를 옮겨 온다 —
   시장 · 정렬 칩 · 시세 갱신이 홈 코드(home.js) 그대로 돈다. 서랍을 접거나 모달을 닫으면 제자리로 돌려 놓는다.
   순위 줄을 누르면 종목 모달 대신 이 모달의 차트가 그 종목이 된다(잡는 쪽에서 먼저 받는다).
   홈이 아닌 화면(순위 칸이 없는 곳)에서는 손잡이를 두지 않는다.

   ── 값 ──
       그래프 탭         /api/kis/investor-board?mkt=&days= — 서버가 들고 있는 거래대금 순 판 한 번(2026-10-16 ·
                         전에는 시세 18묶음을 차례로 물어 여는 데 3초가 넘었다). 줄마다 rows 가 아래 투자자 줄과 같은 모양
       투자자            /api/kis/investor?code=&span=60 — net · netAmt(백만원) · buyAmt · sellAmt(백만원)
                         매수 · 매도 금액이 없는 줄(옛 서버)은 수량 × 종가로 어림하고 「어림」 이라 적는다
       차트              /api/kis/chart · /api/kis/index-candles · /api/kis/index-minutes
   투자자 값은 하루 단위뿐이다 — 분봉에서 고른 구간은 **그 날짜들의 하루 값**을 더한다. 장중 오늘 줄(확정 전)은 빼고 그렇다고 적는다.
   ========================================================================== */

import { apiFetch } from '../data/api.js';
import { openModal } from './modal.js';
import { mountStockSearch } from './stock-search.js';
import { signClass } from '../../../assets/js/sign.js';

const CSS_HREF = new URL('../../css/investor-modal.css', import.meta.url).href;
const SIDES = [['person', '개인'], ['foreign', '외국인'], ['inst', '기관']];
const SIDE_NAME = Object.fromEntries(SIDES);
const DAYS = [['today', '오늘', 1], ['d5', '5일', 5], ['m1', '한달', 20], ['q3', '3달', 60]];
const TOP_N = 15;
const INDEX = { KOSPI: '코스피', KOSDAQ: '코스닥' };
const PERIODS = [['5m', '분봉'], ['D', '일봉'], ['M', '월봉']];
const SHOW_BARS = { '5m': 156, D: 60, M: 24 };   // 처음 보이는 봉 수 — 5분봉 이틀 · 일봉 석 달 · 월봉 2년

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const eok = (mil) => (mil == null ? '—' : `${Math.round(mil / 100).toLocaleString()}억`);           // 백만원 → 억
const eokS = (mil) => (mil == null ? '—' : `${mil > 0 ? '+' : ''}${Math.round(mil / 100).toLocaleString()}억`);
const wonEok = (won) => (won == null ? '—' : `${Math.round(won / 1e8).toLocaleString()}억`);
const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const confirmed = (row) => SIDES.some(([k]) => (row[k] || {}).net != null);

function ensureCss() {
  if (document.querySelector(`link[href="${CSS_HREF}"]`)) return;
  const l = document.createElement('link');
  l.rel = 'stylesheet';
  l.href = CSS_HREF;
  document.head.appendChild(l);
}

async function getJson(url) {
  try {
    const r = await apiFetch(url, { cache: 'no-store' });
    return r && r.ok ? await r.json() : null;
  } catch { return null; }
}

/* 투자자 줄은 모달이 떠 있는 동안 종목마다 한 번만 받는다 — 서버도 60초 들고 있다 */
const invCache = new Map();
function investorRows(code) {
  if (!invCache.has(code)) {
    invCache.set(code, getJson(`/api/kis/investor?code=${code}&span=60`).then((j) => (j && Array.isArray(j.data) ? j.data : [])));
  }
  return invCache.get(code);
}

/** 줄들의 한 투자자 합 — 금액은 백만원. 매수 · 매도 금액이 없는 줄은 수량 × 종가로 어림 */
function sumSide(rows, side) {
  let buy = 0, sell = 0, net = 0, guess = false, any = false, netMissing = false;
  for (const r of rows) {
    const s = r[side] || {};
    if (s.net == null) continue;
    any = true;
    /* 순매수 금액이 빈 날이 끼면 합을 내지 않는다 — 0 으로 더하면 조용히 틀린다(개념정의 검수 · 「못 쟀으면 0 이 아니라」) */
    if (s.netAmt == null) netMissing = true; else net += s.netAmt;
    if (s.buyAmt != null && s.sellAmt != null) { buy += s.buyAmt; sell += s.sellAmt; }
    else if (r.close) { guess = true; buy += (s.buy || 0) * r.close / 1e6; sell += (s.sell || 0) * r.close / 1e6; }
  }
  return any ? { buy, sell, net: netMissing ? null : net, guess } : null;
}

function sideHtml(v, max, left) {
  const w = v == null ? 0 : Math.max(1.5, (v / max) * 82);
  const amt = `<span class="kh-ivm-amt">${eok(v)}</span>`;
  return `<div class="kh-ivm-side ${left ? 'l' : 'r'}">${left ? amt : ''}<div class="kh-ivm-fill ${left ? 'sell' : 'buy'}"
    style="width:${w}%"></div>${left ? '' : amt}</div>`;
}

/** 열 곳: 투자자 정보 칸의 「자세히 ›」 — code 는 그 칸이 보던 종목 */
export function openInvestorModal({ code } = {}) {
  ensureCss();
  const st = { tab: 'graph', side: 'foreign', days: 'today', mkt: 'ALL', target: code || '005930', names: {},
    period: 'D', box: null };
  let chart = null, series = null, bars = [], main = null;

  const rankCard = document.querySelector('.kh-rank-card');
  const home = rankCard && { parent: rankCard.parentNode, next: rankCard.nextSibling };
  let rankBox = null;
  const putBack = () => { if (rankCard && home && rankCard.parentNode !== home.parent) home.parent.insertBefore(rankCard, home.next); };

  const m = openModal({
    label: '투자자 지표',
    /* width 를 주지 않는다 — 주면 고정 폭이 박혀 서랍을 펴도 안 넓어진다. 안 주면 판(css/modal.css)이 서랍만큼 넓힌다 */
    drawers: rankCard ? { right: { key: 'iv-rank', label: '실시간 순위' } } : null,
    head: {
      icon: '수',
      name: '투자자 지표',
      sub: '한국투자증권 확정치',
      tabs: [{ id: 'graph', label: '그래프' }, { id: 'chart', label: '차트' }],
      tab: st.tab,
      tabsNote: rankCard ? '오른쪽 ▶ 실시간 순위에서 종목을 누르면 차트가 그 종목으로' : '',
      onTab: (id) => { st.tab = id; paint(); },
    },
    onToggle: (side, on) => {
      if (rankCard && rankBox) { if (on) rankBox.appendChild(rankCard); else putBack(); }
      requestAnimationFrame(() => resizeChart());
    },
    onClose: () => { putBack(); if (chart) { chart.remove(); chart = null; } },
  });

  m.body.innerHTML = `<div class="kh-ivm"><div class="kh-ivm-main"></div>
    ${rankCard ? '<div class="kh-ivm-rank kh-app-wide"><div class="kh-side"><div class="kh-side-wrap"></div></div></div>' : ''}</div>`;
  main = m.body.querySelector('.kh-ivm-main');
  rankBox = m.body.querySelector('.kh-ivm-rank .kh-side-wrap');     // 홈과 같은 감싸개 — 순위표 모양 규칙이 그 안에서 걸린다
  if (rankCard && rankBox && m.isDrawerOpen('right')) rankBox.appendChild(rankCard);

  /* 순위 줄을 누르면 종목 모달 대신 이 모달의 차트 — 잡는 쪽(capture)에서 먼저 받아 홈 줄 동작을 막는다 */
  if (rankBox) {
    rankBox.addEventListener('click', (e) => {
      const tr = e.target.closest('tr[data-code]');
      if (!tr) return;
      e.stopPropagation();
      e.preventDefault();
      const b = tr.querySelector('td.l b');
      pick(tr.dataset.code, b ? b.textContent.trim() : '');
    }, true);
  }

  /* 머리 「투자자 지표」 옆 종목 검색 — 종목 모달과 같은 부품 */
  const top = m.shell.querySelector('.kh-mh-top');
  const nameEl = top && top.querySelector('.kh-mh-name');
  if (nameEl) {
    const slot = document.createElement('span');
    nameEl.after(slot);
    const search = mountStockSearch(slot, { onPick: (c, n) => pick(c, n) });
    /* 칸 안의 Esc 는 목록만 닫는다 — 문서까지 가면 모달이 통째로 닫힌다 */
    if (search) search.input.addEventListener('keydown', (e) => { if (e.key === 'Escape') e.stopPropagation(); });
  }

  function pick(c, name) {
    if (!c) return;
    st.target = c;
    if (name) st.names[c] = name;
    st.box = null;
    if (st.tab !== 'chart') { st.tab = 'chart'; m.head.setTab('chart'); }
    paint();
  }

  /* ── 거래대금 순 판 — 서버가 들고 있다 내준다. 모달이 떠 있는 동안 시장 · 기간마다 한 번 ── */
  const boardP = new Map();
  function loadBoard(mkt, days) {
    const k = `${mkt}:${days}`;
    if (!boardP.has(k)) {
      boardP.set(k, getJson(`/api/kis/investor-board?mkt=${mkt}&days=${days}`).then((j) => {
        if (j && j.names) Object.entries(j.names).forEach(([c, n]) => { if (!st.names[c]) st.names[c] = n; });
        return j && Array.isArray(j.data) ? j.data : [];
      }));
    }
    return boardP.get(k);
  }
  const nameOf = (c) => INDEX[c] || st.names[c] || c;

  const chips = (g, items, cur) => `<span class="kh-chips" data-g="${g}">${items.map(([id, label]) =>
    `<button class="kh-chip${id === cur ? ' is-active' : ''}" type="button" data-v="${id}">${label}</button>`).join('')}</span>`;
  function bindChips(on) {
    main.querySelectorAll('.kh-chips[data-g] .kh-chip').forEach((b) =>
      b.addEventListener('click', () => on(b.parentElement.dataset.g, b.dataset.v)));
  }

  /* ── 그래프 탭 ── */
  async function paintGraph() {
    main.innerHTML = `<div class="kh-ivm-bar-row">${chips('side', SIDES, st.side)}
        ${chips('days', DAYS.map(([id, l]) => [id, l]), st.days)}
        ${chips('mkt', [['ALL', '전체'], ['KOSPI', '코스피'], ['KOSDAQ', '코스닥']], st.mkt)}</div>
      <div class="kh-ivm-g"><span class="kh-ivm-mut">불러오는 중</span></div>`;
    bindChips((g, v) => { st[g] = v; paintGraph(); });
    const n = (DAYS.find((d) => d[0] === st.days) || [])[2] || 1;
    const rows = (await loadBoard(st.mkt, n)).slice(0, TOP_N).map((x) => {
      st.names[x.code] = x.name;
      return { ...x, s: sumSide((x.rows || []).filter(confirmed).slice(0, n), st.side) };
    });
    if (st.tab !== 'graph' || !main.querySelector('.kh-ivm-g')) return;
    const max = Math.max(...rows.flatMap((r) => (r.s ? [r.s.buy, r.s.sell] : [0]))) || 1;
    const guess = rows.some((r) => r.s && r.s.guess);
    const nm = SIDE_NAME[st.side];
    main.querySelector('.kh-ivm-g').innerHTML = `
      <div class="kh-ivm-cap"><div>← ${nm} 매도</div><div class="kh-ivm-mid">종목 · 거래대금 · 순매수</div><div>${nm} 매수 →</div></div>
      ${rows.map((r, i) => `<div class="kh-ivm-row${r.code === st.target ? ' is-on' : ''}" data-code="${r.code}">
          ${sideHtml(r.s && r.s.sell, max, true)}
          <div class="kh-ivm-mid"><b>${i + 1}. ${esc(r.name)}</b><br>
            <small>대금 ${wonEok(r.value)} · <span class="${signClass(r.s ? r.s.net : null)}">${eokS(r.s ? r.s.net : null)}</span></small></div>
          ${sideHtml(r.s && r.s.buy, max, false)}</div>`).join('')}
      <div class="kh-ivm-note">${(DAYS.find((d) => d[0] === st.days) || [])[1]} 합 · 금액은 확정치${guess ? ' · 매수 · 매도 금액 일부는 수량 × 종가 어림' : ''} ·
        장중 오늘 줄(확정 전)은 빼고 더함 · 줄을 누르면 차트 탭에서 그 종목</div>`;
    main.querySelectorAll('.kh-ivm-row[data-code]').forEach((el) =>
      el.addEventListener('click', () => pick(el.dataset.code, st.names[el.dataset.code])));
  }

  /* ── 차트 탭 ── */
  async function candles() {
    const t = st.target;
    if (INDEX[t]) {
      const j = st.period === '5m' ? await getJson(`/api/kis/index-minutes?code=${t}`)
        : await getJson(`/api/kis/index-candles?code=${t}&period=${st.period}`);
      return (j && j.data && j.data.bars) || [];
    }
    const j = await getJson(`/api/kis/chart?code=${t}&period=${st.period}`);
    return (j && j.data && j.data.candles) || [];
  }
  /* 분봉 시각은 한국 시각 그대로 UTC 자리에 둔다 — 축에 한국 시각이 찍힌다 */
  const toTime = (ts) => (ts.length > 8
    ? Date.UTC(+ts.slice(0, 4), +ts.slice(4, 6) - 1, +ts.slice(6, 8), +ts.slice(8, 10), +ts.slice(10, 12)) / 1000
    : `${ts.slice(0, 4)}-${ts.slice(4, 6)}-${ts.slice(6, 8)}`);

  function resizeChart() {
    const el = main && main.querySelector('.kh-ivm-chart');
    if (chart && el) { chart.applyOptions({ width: el.clientWidth }); placeBox(); }
  }

  /* 점선 네모 — 봉 순번(logical)으로 들고 있어 끌거나 넓혀도 그 봉에 붙어 있다 */
  function placeBox() {
    const el = main && main.querySelector('.kh-ivm-box');
    if (!el) return;
    if (!chart || !st.box) { el.style.display = 'none'; return; }
    const ts = chart.timeScale();
    /* 소수 순번은 0 을 낸다(이 판 실측) — 정수 순번의 가운데 좌표에 봉 반 칸씩 더한다 */
    const a = ts.logicalToCoordinate(st.box.from), b = ts.logicalToCoordinate(st.box.to);
    if (a == null || b == null) { el.style.display = 'none'; return; }
    const half = (ts.options().barSpacing || 6) / 2;
    el.style.display = '';
    el.style.left = `${Math.min(a, b) - half}px`;
    el.style.width = `${Math.abs(b - a) + half * 2}px`;
  }

  /** 지금 기간 — 네모가 있으면 그 봉들, 없으면 보이는 봉들. 날짜(YYYYMMDD) 범위로 낸다 */
  function rangeNow() {
    if (!bars.length) return null;
    let from, to;
    if (st.box) { from = st.box.from; to = st.box.to; }
    else {
      const r = chart && chart.timeScale().getVisibleLogicalRange();
      if (!r) return null;
      from = Math.ceil(r.from); to = Math.floor(r.to);
    }
    from = Math.max(0, Math.min(bars.length - 1, from));
    to = Math.max(0, Math.min(bars.length - 1, to));
    if (from > to) [from, to] = [to, from];
    return { from: bars[from].ts.slice(0, 8), to: bars[to].ts.slice(0, 8), boxed: !!st.box };
  }

  async function paintSides() {
    const box = main.querySelector('.kh-ivm-sides');
    if (!box) return;
    const rg = rangeNow();
    if (!rg) { box.innerHTML = ''; return; }
    const range = `${rg.from.slice(4, 6)}.${rg.from.slice(6)} ~ ${rg.to.slice(4, 6)}.${rg.to.slice(6)}`;
    if (INDEX[st.target]) {
      box.innerHTML = `<div class="kh-ivm-period"><b>${range}</b></div>
        <div class="kh-ivm-mut">지수에는 종목별 투자자 값이 없습니다 — 오른쪽 순위나 검색에서 종목을 고르면 그 종목의 개인 · 외국인 · 기관이 나옵니다</div>`;
      return;
    }
    const all = await investorRows(st.target);
    const d = all.filter((r) => r.date >= rg.from && r.date <= rg.to);
    const days = d.filter(confirmed);
    const skipped = d.length - days.length;
    const sums = SIDES.map(([k, n]) => ({ k, n, s: sumSide(days, k) }));
    const max = Math.max(...sums.flatMap((x) => (x.s ? [x.s.buy, x.s.sell] : [0]))) || 1;
    const guess = sums.some((x) => x.s && x.s.guess);
    const oldest = all.length ? all[all.length - 1].date : null;
    const short = oldest && rg.from < oldest;
    if (rangeNow() && rangeNow().from !== rg.from) return;     // 그새 기간이 또 바뀌었다
    box.innerHTML = `<div class="kh-ivm-period"><b>${rg.boxed ? '점선 네모 안' : '보이는 기간'} ${range}</b> ·
        투자자 값 ${days.length}거래일${skipped ? ` · 오늘(확정 전) ${skipped}일 뺌` : ''}${short ? ` · ${oldest.slice(4, 6)}.${oldest.slice(6)} 앞은 받은 값이 없어 그 뒤만` : ''}</div>
      <div class="kh-ivm-cap"><div>← 매도</div><div class="kh-ivm-mid">투자자 · 순매수</div><div>매수 →</div></div>
      ${sums.map((x) => `<div class="kh-ivm-row kh-ivm-big">
          ${sideHtml(x.s && x.s.sell, max, true)}
          <div class="kh-ivm-mid"><b>${x.n}</b><br><small><span class="${signClass(x.s ? x.s.net : null)}">${eokS(x.s ? x.s.net : null)}</span></small></div>
          ${sideHtml(x.s && x.s.buy, max, false)}</div>`).join('')}
      <div class="kh-ivm-note">금액은 한국투자증권 확정치 합${guess ? ' · 매수 · 매도 금액 일부는 수량 × 종가 어림' : ''} ·
        투자자 값은 하루 단위라 분봉에서는 그 날짜들의 하루 값을 더함</div>`;
  }

  async function paintChart() {
    if (chart) { chart.remove(); chart = null; }
    main.innerHTML = `<div class="kh-ivm-bar-row">
        ${chips('target', [[INDEX[st.target] ? (st.lastStock || code || '005930') : st.target, '종목'], ['KOSPI', '코스피'], ['KOSDAQ', '코스닥']], st.target)}
        ${chips('period', PERIODS, st.period)}
        <span class="kh-chips"><button class="kh-chip kh-ivm-pickbtn${st.picking ? ' is-active' : ''}" type="button">▭ 구간 고르기</button>
          <button class="kh-chip kh-ivm-clear" type="button">구간 지우기</button></span>
        <span class="kh-ivm-name">${esc(nameOf(st.target))}</span></div>
      <div class="kh-ivm-chart${st.picking ? ' is-picking' : ''}"><div class="kh-ivm-box" style="display:none"></div><div class="kh-ivm-pick"></div></div>
      <div class="kh-ivm-sides"><span class="kh-ivm-mut">불러오는 중</span></div>`;
    if (!INDEX[st.target]) st.lastStock = st.target;
    bindChips((g, v) => { st[g] = v; st.box = null; paintChart(); });
    main.querySelector('.kh-ivm-pickbtn').addEventListener('click', () => {
      st.picking = !st.picking;
      main.querySelector('.kh-ivm-chart').classList.toggle('is-picking', st.picking);
      main.querySelector('.kh-ivm-pickbtn').classList.toggle('is-active', st.picking);
    });
    main.querySelector('.kh-ivm-clear').addEventListener('click', () => { st.box = null; placeBox(); paintSides(); });

    if (!st.names[st.target] && !INDEX[st.target]) {
      loadBoard('ALL', 1).then(() => { const f = st.names[st.target]; if (f) { const n = main.querySelector('.kh-ivm-name'); if (n) n.textContent = f; } });
    }
    const want = `${st.target}|${st.period}`;
    const got = await candles();
    if (st.tab !== 'chart' || want !== `${st.target}|${st.period}`) return;
    const el = main.querySelector('.kh-ivm-chart');
    const LC = window.LightweightCharts;
    if (!LC || !el) { main.querySelector('.kh-ivm-sides').innerHTML = '<span class="kh-ivm-mut">차트를 그리지 못했습니다</span>'; return; }
    bars = got;
    chart = LC.createChart(el, {
      width: el.clientWidth, height: el.clientHeight,
      layout: { background: { color: 'transparent' }, textColor: cssVar('--kh-chart-axis') },
      grid: { vertLines: { color: cssVar('--kh-chart-grid') }, horzLines: { color: cssVar('--kh-chart-grid') } },
      timeScale: { timeVisible: st.period === '5m', borderColor: cssVar('--kh-chart-border') },
      rightPriceScale: { borderColor: cssVar('--kh-chart-border') },
      crosshair: { vertLine: { color: cssVar('--kh-chart-crosshair') }, horzLine: { color: cssVar('--kh-chart-crosshair') } },
    });
    series = chart.addSeries(LC.CandlestickSeries, {
      upColor: cssVar('--kh-up'), downColor: cssVar('--kh-down'), borderVisible: false,
      wickUpColor: cssVar('--kh-up'), wickDownColor: cssVar('--kh-down'),
      ...(INDEX[st.target] ? {} : { priceFormat: { type: 'custom', minMove: 1, formatter: (v) => Math.round(v).toLocaleString() } }),
    });
    series.setData(bars.map((b) => ({ time: toTime(b.ts), open: b.open, high: b.high, low: b.low, close: b.close })));
    if (bars.length) {
      const n = SHOW_BARS[st.period] || 60;
      chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, bars.length - n), to: bars.length - 1 });
    }

    /* 점선 네모 고르기 — 「구간 고르기」 를 켜면 차트 위 덮개가 끌기를 받는다(차트 밀기와 안 섞이게) */
    const pickEl = el.querySelector('.kh-ivm-pick');
    let start = null;
    const idxAt = (ev) => {
      const x = ev.clientX - el.getBoundingClientRect().left;
      const l = chart.timeScale().coordinateToLogical(x);
      return l == null ? null : Math.max(0, Math.min(bars.length - 1, Math.round(l)));
    };
    pickEl.addEventListener('pointerdown', (ev) => {
      start = idxAt(ev);
      if (start == null) return;
      pickEl.setPointerCapture(ev.pointerId);
      st.box = { from: start, to: start };
      placeBox();
    });
    pickEl.addEventListener('pointermove', (ev) => {
      if (start == null) return;
      const i = idxAt(ev);
      if (i == null) return;
      st.box = { from: Math.min(start, i), to: Math.max(start, i) };
      placeBox();
    });
    pickEl.addEventListener('pointerup', () => {
      if (start == null) return;
      start = null;
      paintSides();
    });

    let tm = null;
    chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
      placeBox();
      if (st.box) return;                       // 네모가 있으면 기간은 네모 — 밀어도 안 바뀐다
      clearTimeout(tm);
      tm = setTimeout(paintSides, 150);
    });
    paintSides();
  }

  function paint() {
    if (st.tab === 'graph') { if (chart) { chart.remove(); chart = null; } paintGraph(); }
    else paintChart();
  }
  paint();
  return m;
}
