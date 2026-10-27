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
       그래프   거래대금 순 종목들 — 순매수 막대 하나(순매도는 왼쪽 파랑 · 순매수는 오른쪽 빨강). 개인 · 외국인 · 기관 · 기간을 고른다.
                아래에 개인 · 외국인 · 기관별 금액 칸 셋(위 종목들 합). 「오늘」 옆에 어느 날 확정치인지 적는다 —
                장중에는 오늘 줄이 비어 지난 거래일 값이 나온다(2026-10-22 재권님 「응 해줘」 · 시안 다섯 자리)
       차트     고른 종목(또는 코스피 · 코스닥)의 분 · 일 · 월봉 + 아래 그 종목의 개인 · 외국인 · 기관 양쪽 막대.
                기간은 **점선 네모로 고른 구간**, 안 골랐으면 **차트에 보이는 구간**이다
       당일     오늘 장중 5분마다 — 코스피 외국인 · 기관 · 개인 · 코스피 프로그램 · 고른 종목 프로그램의 매수 · 매도 · 순매수(막대 + 표) ·
                고른 종목의 장중 잠정치(하루 다섯 번) · 기관 안 · 증권사 상위 5 (2026-10-27 재권님 시안 「ㄴ · 매수랑 매도 둘다」 ·
                「모달 창 밖으로 길어지지 않게」 — 칸마다 높이를 잡고 표는 칸 안에서 내린다)

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
       당일              /api/kis/flow-today?code=&step=5(서버가 1분마다 쌓은 것 · server/intraday_flow.py) · investor-estimate ·
                         investor-member · investor?span=5 의 instDetail(확정치 · 15:40 뒤) — 다시 묻는 주기는 서버 값(intraday_flow.CACHE_TTL)
   투자자 값은 하루 단위뿐이다 — 분봉에서 고른 구간은 **그 날짜들의 하루 값**을 더한다. 장중 오늘 줄(확정 전)은 빼고 그렇다고 적는다.
   ========================================================================== */

import { apiFetch } from '../data/api.js';
import { openModal } from './modal.js';
import { mountStockSearch } from './stock-search.js';
import { signClass } from '../../../assets/js/sign.js';
import { watch } from '../store/longpoll.js';

const CSS_HREF = new URL('../../css/investor-modal.css', import.meta.url).href;
const SIDES = [['person', '개인'], ['foreign', '외국인'], ['inst', '기관']];
const SIDE_NAME = Object.fromEntries(SIDES);
const DAYS = [['today', '오늘', 1], ['d5', '5일', 5], ['m1', '한달', 20], ['q3', '3달', 60]];
const TOP_N = 15;
const INDEX = { KOSPI: '코스피', KOSDAQ: '코스닥' };
const PERIODS = [['5m', '분봉'], ['D', '일봉'], ['M', '월봉']];
const SHOW_BARS = { '5m': 156, D: 60, M: 24 };
const FLOW_KEY = 'intraday_flow.CACHE_TTL';    // 「당일」 탭이 다시 묻는 주기 — 서버 값
const FLOW_FALLBACK_MS = 60000;   // 처음 보이는 봉 수 — 5분봉 이틀 · 일봉 석 달 · 월봉 2년

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

/** 순매수 막대 하나 — 순매도는 왼쪽(파랑) · 순매수는 오른쪽(빨강). 매수 · 매도를 따로 그리지 않는다 */
/* 줄마다 매도(왼쪽) · 매수(오른쪽) 막대 둘 + 그 금액 (2026-10-26 재권님 「사고 파는 금액 다 나오도록」 → 「글이 안보이는거 말고
   그래프도 안보이는데」 · 작업우선순위 경유). 10-16 의 「매도 매수를 다 그리지 말고 둘의 차이만」 을 이 말씀이 바꿨다 —
   순매수는 가운데 글(대금 · ±순매수)에 남는다. 막대 길이 기준은 화면에 나온 줄들의 매수 · 매도 금액 중 가장 큰 것(max) */
function grossSide(amt, max, left) {
  const w = amt == null || !max ? 0 : Math.max(1.5, (amt / max) * 82);
  const bar = amt == null ? '' : `<div class="kh-ivm-fill ${left ? 'sell' : 'buy'}" style="width:${w}%"></div>`;
  const g = `<span class="kh-ivm-gross">${left ? '매도' : '매수'} ${eok(amt)}</span>`;
  return `<div class="kh-ivm-side ${left ? 'l' : 'r'}">${left ? g + bar : bar + g}</div>`;
}

/** 여러 종목의 한 투자자 합 — 한 종목이라도 순매수 금액이 비면 순매수 합은 「—」 · cnt 는 실제로 더한 종목 수 */
function sumMany(list) {
  let buy = 0, sell = 0, net = 0, cnt = 0, miss = false, guess = false;
  for (const s of list) {
    if (!s) continue;
    cnt += 1;
    buy += s.buy; sell += s.sell;
    if (s.net == null) miss = true; else net += s.net;
    if (s.guess) guess = true;
  }
  return cnt ? { buy, sell, net: miss ? null : net, guess, cnt } : null;
}
const mmdd = (d) => (d ? `${d.slice(4, 6)}-${d.slice(6, 8)}` : '');

/** 열 곳: 투자자 정보 칸의 「자세히 ›」 — code 는 그 칸이 보던 종목 */
export function openInvestorModal({ code } = {}) {
  ensureCss();
  const st = { tab: 'graph', side: 'foreign', days: 'today', mkt: 'ALL', target: code || '005930', names: {},
    period: 'D', box: null };
  let chart = null, series = null, bars = [], main = null, flowWatch = null;

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
      tabs: [{ id: 'graph', label: '그래프' }, { id: 'chart', label: '차트' }, { id: 'today', label: '당일' }],
      tab: st.tab,
      tabsNote: rankCard ? '오른쪽 ▶ 실시간 순위에서 종목을 누르면 차트가 그 종목으로' : '',
      onTab: (id) => { st.tab = id; paint(); },
    },
    onToggle: (side, on) => {
      if (rankCard && rankBox) { if (on) rankBox.appendChild(rankCard); else putBack(); }
      requestAnimationFrame(() => resizeChart());
    },
    onClose: () => { putBack(); stopFlow(); if (chart) { chart.remove(); chart = null; } },
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
    if (st.tab !== 'chart' && st.tab !== 'today') { st.tab = 'chart'; m.head.setTab('chart'); }   // 당일 탭에서 고르면 그 탭 그대로 · 그 종목으로
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
        ${chips('days', DAYS.map(([id, l]) => [id, l]), st.days)}<span class="kh-ivm-asof"></span>
        ${chips('mkt', [['ALL', '전체'], ['KOSPI', '코스피'], ['KOSDAQ', '코스닥']], st.mkt)}</div>
      <div class="kh-ivm-g"><span class="kh-ivm-mut">불러오는 중</span></div>`;
    bindChips((g, v) => { st[g] = v; paintGraph(); });
    const n = (DAYS.find((d) => d[0] === st.days) || [])[2] || 1;
    const rows = (await loadBoard(st.mkt, n)).slice(0, TOP_N).map((x) => {
      st.names[x.code] = x.name;
      const d = (x.rows || []).filter(confirmed).slice(0, n);
      return { ...x, d, s: sumSide(d, st.side) };
    });
    if (st.tab !== 'graph' || !main.querySelector('.kh-ivm-g')) return;
    /* 「오늘」 이 어느 날 값인지 — 장중에는 맨 위 줄(오늘)이 비어 지난 거래일 확정치가 나온다 */
    const asof = main.querySelector('.kh-ivm-asof');
    const lead = rows.find((r) => r.d.length);
    if (asof && st.days === 'today' && lead) {
      asof.textContent = `${lead.rows[0] && !confirmed(lead.rows[0]) ? '장중 · ' : ''}${mmdd(lead.d[0].date)} 확정치`;
    }
    const max = Math.max(...rows.map((r) => (r.s ? Math.max(r.s.buy || 0, r.s.sell || 0) : 0))) || 1;   // 막대 기준 — 가장 큰 매수 · 매도 금액
    const guess = rows.some((r) => r.s && r.s.guess);
    const nm = SIDE_NAME[st.side];
    const totals = SIDES.map(([k, n2]) => ({ n: n2, t: sumMany(rows.map((r) => sumSide(r.d, k))) }));
    main.querySelector('.kh-ivm-g').innerHTML = `
      <div class="kh-ivm-cap"><div>← ${nm} 매도</div><div class="kh-ivm-mid">종목 · 거래대금 · 순매수</div><div>${nm} 매수 →</div></div>
      ${rows.map((r, i) => `<div class="kh-ivm-row${r.code === st.target ? ' is-on' : ''}" data-code="${r.code}">
          ${grossSide(r.s ? r.s.sell : null, max, true)}
          <div class="kh-ivm-mid"><b>${i + 1}. ${esc(r.name)}</b><br>
            <small>대금 ${wonEok(r.value)} · <span class="${signClass(r.s ? r.s.net : null)}">${eokS(r.s ? r.s.net : null)}</span></small></div>
          ${grossSide(r.s ? r.s.buy : null, max, false)}</div>`).join('')}
      <div class="kh-ivm-tot">${totals.map(({ n: n2, t }) => `<div class="kh-ivm-tot-c">
          <div class="kh-ivm-tot-h">${n2} · ${t ? `위 ${t.cnt}종목 합` : '값 없음'}</div>
          <div class="kh-ivm-tot-v ${signClass(t ? t.net : null)}">${eokS(t ? t.net : null)}</div>
          <div class="kh-ivm-tot-s">매수 ${eok(t ? t.buy : null)} · 매도 ${eok(t ? t.sell : null)}</div></div>`).join('')}</div>
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
      /* attributionLogo — 왼쪽 아래 「TV」 글자를 끈다(2026-10-22 재권님 「문자같은거 필요없는데 지워」 · chart.js 와 같은 옵션) */
      layout: { background: { color: 'transparent' }, textColor: cssVar('--kh-chart-axis'), attributionLogo: false },
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

  /* ── 당일 탭 — 5분마다 매수 · 매도 · 순매수 ──
     금액 단위가 칸마다 다르다 — 시장 · 시장 프로그램 백만원 · 종목 프로그램 원(서버 meta.units). 「없음」 은 null 그대로 「—」 */
  const fmtMil = (v, sign = true) => (v == null ? '—' : `${sign && v > 0 ? '+' : ''}${(v / 100).toFixed(Math.abs(v) < 1000 ? 1 : 0)}억`);
  const fmtWon = (v, sign = true) => (v == null ? '—' : `${sign && v > 0 ? '+' : ''}${(v / 1e8).toFixed(1)}억`);
  const fmtChu = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${Math.round(v).toLocaleString()}천주`);
  const fmtJu = (v, sign = true) => (v == null ? '—' : `${sign && v > 0 ? '+' : ''}${Math.abs(v) >= 10000 ? (v / 10000).toFixed(1) + '만' : Math.round(v).toLocaleString()}주`);
  const hhmm = (t) => (t ? `${t.slice(0, 2)}:${t.slice(2, 4)}` : '');
  const stockCode = () => (/^\d{6}$/.test(st.target) ? st.target : null);
  function stopFlow() { if (flowWatch) { flowWatch.stop(); flowWatch = null; } }

  /* 막대 칸 — 구간마다 위 매수 · 아래 매도 · 검은 가로줄 순매수. groups 가 여럿이면 나란히(색 = 그 투자자) */
  function bsSvg(rows, groups) {
    if (!rows.length) return '<div class="kh-ivt-empty">아직 쌓인 구간이 없습니다 · 평일 09:00~15:30</div>';
    const W = 600, H = 110;
    const vals = rows.flatMap((r) => groups.flatMap((g) => [g.v(r).buy || 0, -(g.v(r).sell || 0)]));
    const top = Math.max(1, ...vals) * 1.08, bot = Math.min(-1, ...vals) * 1.08;
    const y = (v) => (top - v) / (top - bot) * H;
    const cw = (W - 12) / rows.length, gw = cw * 0.8 / groups.length, bw = Math.max(2, gw * 0.8);
    const marks = rows.map((r, i) => groups.map((g, j) => {
      const v = g.v(r), x = 6 + cw * i + cw * 0.1 + gw * (j + 0.5), y0 = y(0);
      return `${v.buy == null ? '' : `<rect x="${x - bw / 2}" width="${bw}" y="${y(v.buy)}" height="${Math.max(0.5, y0 - y(v.buy))}" style="fill:var(${g.up})"/>`}
        ${v.sell == null ? '' : `<rect x="${x - bw / 2}" width="${bw}" y="${y0}" height="${Math.max(0.5, y(-v.sell) - y0)}" style="fill:var(${g.down})${g.up === g.down ? ';opacity:.45' : ''}"/>`}
        ${v.net == null ? '' : `<line x1="${x - bw / 2 - 1}" x2="${x + bw / 2 + 1}" y1="${y(v.net)}" y2="${y(v.net)}" style="stroke:var(--kh-text-primary);stroke-width:2"/>`}`;
    }).join('')).join('');
    const every = Math.ceil(rows.length / 8);
    const lab = rows.map((r, i) => (i % every ? '' : `<text x="${6 + cw * (i + 0.5)}" y="${H + 14}" text-anchor="middle" style="fill:var(--kh-text-secondary);font-size:12px">${hhmm(r.t)}</text>`)).join('');
    return `<svg class="kh-ivt-svg" viewBox="0 -2 ${W} ${H + 20}"><line x1="0" x2="${W}" y1="${y(0)}" y2="${y(0)}" style="stroke:var(--kh-border-strong)"/>${marks}${lab}</svg>`;
  }
  /* 표 — 시각이 세로 · 최근이 위. 칸 안에서 내린다(모달이 안 길어지게) */
  const bsCell = (v, f, fq) => `<td><b class="${signClass(v.net)}">${f(v.net)}</b>${fq ? ` <small>${fq(v.netQty)}</small>` : ''}<br>
    <small><span class="kh-up">${f(v.buy, false)}</span> / <span class="kh-down">${f(v.sell, false)}</span></small></td>`;
  const bsTable = (rows, cols) => `<div class="kh-ivt-tb"><table><thead><tr><th>구간</th>${cols.map((c) => `<th>${c.h}</th>`).join('')}</tr></thead>
    <tbody>${rows.slice().reverse().map((r) => `<tr><td>${hhmm(r.t)}~</td>${cols.map((c) => c.f(r)).join('')}</tr>`).join('')}</tbody></table></div>`;
  const KEY_NOTE = '<div class="kh-ivt-note">위 막대 매수 · 아래 막대 매도 · 검은 줄 순매수 · 표는 굵게 순매수 · 작게 <span class="kh-up">매수</span> / <span class="kh-down">매도</span></div>';
  const WHO3 = [['frgn', '외국인', '--kh-ind-1'], ['orgn', '기관', '--kh-ind-2'], ['prsn', '개인', '--kh-ind-3']];
  const PG = { up: '--kh-up', down: '--kh-down' };

  async function loadToday() {
    const code = stockCode();
    const [flow, est, mem, inv] = await Promise.all([
      getJson(`/api/kis/flow-today?step=5${code ? `&code=${code}` : ''}`),
      code ? getJson(`/api/kis/investor-estimate?code=${code}`) : null,
      code ? getJson(`/api/kis/investor-member?code=${code}`) : null,
      code ? getJson(`/api/kis/investor?code=${code}&span=5`) : null,
    ]);
    if (code && !st.names[code]) {      // 처음 연 종목은 이름표가 아직 없다 — 시세에서 이름만 받는다(서버 캐시)
      const q = await getJson(`/api/kis/quotes?codes=${code}`);
      const nmq = q && q.data && q.data[code] && q.data[code].name;
      if (nmq) st.names[code] = nmq;
    }
    if (st.tab !== 'today' || !main.querySelector('.kh-ivt')) return;
    const d = (flow && flow.data) || {};
    const mk = d.market || { rows: [] }, pg = d.program || { rows: [] }, sk = d.stock || null;
    const last = mk.last || null, nm = nameOf(code || '') || code;
    const card = (cls, head, body) => `<section class="kh-ivt-card ${cls}"><div class="kh-ivt-h">${head}</div>${body}</section>`;

    const total = last ? `${WHO3.map(([k, n]) => { const v = (last[k] || {}).net;
      return `<div class="kh-ivt-tot"><span>${n}</span><b class="${signClass(v)}">${fmtMil(v)}</b></div>`; }).join('')}
      <div class="kh-ivt-inst">기관 안 —${[['scrt', '증권'], ['ivtr', '투신'], ['pe_fund', '사모'], ['bank', '은행'], ['insu', '보험'], ['mrbn', '종금'], ['fund', '기금'], ['etc_corp', '기타법인']]
        .map(([k, n]) => ` <span>${n} <b class="${signClass((last.inst || {})[k])}">${fmtMil((last.inst || {})[k])}</b></span>`).join('')}</div>`
      : '<div class="kh-ivt-empty">아직 쌓인 값이 없습니다</div>';

    const mkBody = bsSvg(mk.rows, WHO3.map(([k, , c]) => ({ v: (r) => r[k] || {}, up: c, down: c })))
      + `<div class="kh-ivt-lg">${WHO3.map(([, n, c]) => `<span style="color:var(${c})">■ ${n}</span>`).join('')}</div>`
      + bsTable(mk.rows, WHO3.map(([k, n, c]) => ({ h: `<span style="color:var(${c})">${n}</span>`, f: (r) => bsCell(r[k] || {}, fmtMil, fmtChu) })));
    const pgBody = bsSvg(pg.rows, [{ v: (r) => r, ...PG }]) + bsTable(pg.rows, [{ h: '금액', f: (r) => bsCell(r, fmtMil) }]);
    const skBody = !code ? '<div class="kh-ivt-empty">「차트」 탭 · 검색 · 실시간 순위에서 종목을 고르면 그 종목이 나옵니다</div>'
      : bsSvg((sk && sk.rows) || [], [{ v: (r) => r, ...PG }])
        + bsTable((sk && sk.rows) || [], [{ h: '금액', f: (r) => bsCell(r, fmtWon) },
          { h: '수량', f: (r) => bsCell({ net: r.netQty, buy: r.buyQty, sell: r.sellQty }, fmtJu) }]);

    /* 종목 장중 잠정치 — 하루 다섯 번 · 외국인 · 기관 누적(주) · 응답에 시각이 없다 */
    const er = (est && est.data && est.data.rows) || [];
    const estBody = !code ? '' : `<div class="kh-ivt-seg">${[1, 2, 3, 4, 5].map((g) => { const e = er.find((x) => x.seq === g);
      return `<div><small>${g}회차</small>외 <b class="${signClass(e && e.foreign)}">${e ? fmtJu(e.foreign).replace('주', '') : '—'}</b><br>기 <b class="${signClass(e && e.inst)}">${e ? fmtJu(e.inst).replace('주', '') : '—'}</b></div>`; }).join('')}</div>
      <div class="kh-ivt-note">증권사 집계 잠정치 · 마감 뒤 확정치와 다름 · 개인은 안 줌</div>`;

    /* 기관 안 · 외국인 등록/미등록 — 확정치(마감 15:40 뒤). 맨 위 확정 줄 */
    const ir = ((inv && inv.data) || []).find((r) => r.instDetail);
    const names = (inv && inv.meta && inv.meta.instDetail) || [];
    const instBody = !code ? '' : !ir ? '<div class="kh-ivt-empty">확정치 없음 — 15:40 뒤</div>'
      : `<div class="kh-ivt-inst">${mmdd(ir.date)} 확정 —${names.map(([k, n]) => { const v = (ir.instDetail[k] || {}).netAmt;
        return ` <span>${esc(n)} <b class="${signClass(v)}">${fmtMil(v)}</b></span>`; }).join('')}
        ${[['foreignReg', '외국인 등록'], ['foreignNreg', '외국인 미등록'], ['etcCorp', '기타법인']].map(([k, n]) => { const v = (ir[k] || {}).netAmt;
          return ` <span>${n} <b class="${signClass(v)}">${fmtMil(v)}</b></span>`; }).join('')}</div>`;

    /* 증권사 상위 5 — 오늘 장중 누적 */
    const mb = mem && mem.data;
    const side = (arr, cls) => (arr || []).map((x, i) => `<li><span>${i + 1}. ${esc(x.name)}${x.foreign ? ' <small>외국계</small>' : ''}</span><b class="${cls}">${fmtJu(x.qty, false)}</b></li>`).join('') || '<li>—</li>';
    const memBody = !code ? '' : !mb ? '<div class="kh-ivt-empty">못 받음</div>'
      : `<div class="kh-ivt-mem"><div><small>매도 상위</small><ol>${side(mb.sell, 'kh-down')}</ol></div><div><small>매수 상위</small><ol>${side(mb.buy, 'kh-up')}</ol></div></div>`;

    const at = mk.lastAt ? `${hhmm(mk.lastAt)} 까지` : '';
    main.querySelector('.kh-ivt').innerHTML = `
      <div class="kh-ivt-col">
        ${card('', `코스피 — 투자자별 순매수 <small>오늘 누계 · ${at}</small>`, total)}
        ${code ? card('', `${esc(nm)} — 외국인 · 기관 장중 <small>하루 다섯 번 · 주</small>`, estBody) : ''}
        ${code ? card('', `${esc(nm)} — 증권사 상위 5 <small>오늘 장중 누적</small>`, memBody) : ''}
      </div>
      <div class="kh-ivt-col">
        ${card('is-tall', `코스피 투자자별 5분마다 <small>매수 · 매도 · 순매수 · 금액 · 수량(천주)</small>`, mkBody + KEY_NOTE)}
        ${code ? card('', `${esc(nm)} — 기관 안 · 외국인 등록/미등록`, instBody) : ''}
      </div>
      <div class="kh-ivt-col">
        ${card('', `코스피 프로그램 5분마다 <small>차익 + 비차익 · 수량은 KIS 가 안 줌</small>`, pgBody)}
        ${card('', `${code ? esc(nm) : '종목'} 프로그램 5분마다 <small>${sk && !sk.rows.length && sk.watching ? '지금부터 쌓는 중' : '금액 · 수량'}</small>`, skBody)}
      </div>`;
  }

  function paintToday() {
    main.innerHTML = `<div class="kh-ivm-bar-row"><span class="kh-ivm-asof">오늘 장중 · 5분마다 · 코스피</span>
      <span class="kh-ivm-mut">관심종목은 장중 내내 · 고른 종목은 고른 때부터 쌓입니다</span></div><div class="kh-ivt"><span class="kh-ivm-mut">불러오는 중</span></div>`;
    loadToday();
    stopFlow();
    flowWatch = watch({ url: () => `/api/kis/flow-today?step=5${stockCode() ? `&code=${stockCode()}` : ''}`,
      onChange: () => loadToday(), key: FLOW_KEY, fallbackMs: FLOW_FALLBACK_MS });
  }

  function paint() {
    if (st.tab !== 'today') stopFlow();
    if (st.tab === 'graph' || st.tab === 'today') { if (chart) { chart.remove(); chart = null; } }
    if (st.tab === 'graph') paintGraph();
    else if (st.tab === 'today') paintToday();
    else paintChart();
  }
  paint();
  return m;
}
