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
       차트     종목은 날마다 순매수 금액 막대 + 쌓은 선(일봉만 · 11-05) · 코스피 · 코스닥은 분 · 일 · 월봉 +
                아래 그 종목의 개인 · 외국인 · 기관 양쪽 막대.
                기간은 **점선 네모로 고른 구간**, 안 골랐으면 **차트에 보이는 구간**이다
       1분 흐름 오늘 장중 1분마다 코스피 투자자 갈래 누계 선 + 분마다 표 — 개인 · 외국인 · 기관계 · 기타법인 + 기관 안 여덟.
                누계 칸을 누르면 선을 켜고 끈다(2026-11-04 재권님 「투자자지표 모달에다가 연결 · 실시간」 → 시안 「응 그렇게 해줘」)
       날마다 수급  날짜를 세로로(새 날이 위 · 맨 위 「오늘 · 장중 잠정」) · 가로는 지수 등락률 → 투자자 갈래(서버 groups 순서 · 세부는 머리 글자 옅게) ·
                코스피 · 코스닥 칩 · 억원 (2026-11-05 재권님 「날짜 쌓는걸 가로로 하지말고 세로로」 → 「투자자 지표 모달에 들어가야」 · 시황분석 · 작업우선순위 경유)
       매매 동향  외국인 · 기관 순매수 순위(가집계 · 코스피 · 코스닥 합쳐 100까지) · 「특이 매수」 = 전일 순매도 → 오늘 순매수 「전환」 강도 순 ·
                날짜를 고르면 그날 남긴 판(2026-11-06 재권님 사진 「이거 만들고 싶어」 → (가) 외국인 · 기관 먼저 · 「순차로 해줘」)
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
       날마다 수급       /api/kis/flow-board?days=20 의 days(확정치) · today.net(코스피 장중 잠정)
       1분 흐름          /api/kis/flow-board?days=1&step=1 의 today(server/flow_board.py · 장중 잠정 · 코스피만)
       매매 동향         /api/kis/flow-rank?who=&day=(server/flow_rank.py) — 다시 묻는 주기는 서버 값(kis_proxy.INVESTOR_TOP_TTL)
       당일              /api/kis/flow-today?code=&step=5(서버가 1분마다 쌓은 것 · server/intraday_flow.py) · investor-estimate ·
                         investor-member · investor?span=5 의 instDetail(확정치 · 15:40 뒤) — 다시 묻는 주기는 서버 값(intraday_flow.CACHE_TTL)
   투자자 값은 하루 단위뿐이다 — 분봉에서 고른 구간은 **그 날짜들의 하루 값**을 더한다. 장중 오늘 줄(확정 전)은 빼고 그렇다고 적는다.
   ========================================================================== */

import { apiFetch } from '../data/api.js';
import { openModal } from './modal.js';
import { mountStockSearch } from './stock-search.js';
import { signClass } from '../../../assets/js/sign.js';
import { watch } from '../store/longpoll.js';
import { serverMs } from '../store/timing.js';

const CSS_HREF = new URL('../../css/investor-modal.css', import.meta.url).href;
const SIDES = [['person', '개인'], ['foreign', '외국인'], ['inst', '기관']];
const SIDE_NAME = Object.fromEntries(SIDES);
const DAYS = [['today', '오늘', 1], ['d5', '5일', 5], ['m1', '한달', 20], ['q3', '3달', 60]];
const TOP_N = 15;
const INDEX = { KOSPI: '코스피', KOSDAQ: '코스닥' };
const PERIODS = [['5m', '분봉'], ['D', '일봉'], ['M', '월봉']];
/* 종목 금액 차트 — 일봉만. 분봉은 투자자 값이 하루 단위라 없고, 월봉은 서버 투자자 값이 60거래일까지라 막대가 서너 개뿐이라 뺐다
   (11-05 qa 덧 → 재권님 「가」) */
const AMT_PERIODS = PERIODS.filter(([k]) => k === 'D');
const CHART_SIDES = [['foreign', '외국인', '--kh-ind-1'], ['inst', '기관', '--kh-ind-2'], ['person', '개인', '--kh-ind-3']];
const SHOW_BARS = { '5m': 156, D: 60, M: 24 };   // 처음 보이는 봉 수 — 5분봉 이틀 · 일봉 석 달 · 월봉 2년
const FLOW_KEY = 'intraday_flow.CACHE_TTL';    // 「당일」 탭이 다시 묻는 주기 — 서버 값
const FLOW_FALLBACK_MS = 60000;
const EST_KEY = 'kis_proxy.INVESTOR_EST_TTL';   // 「차트」 탭 오늘 줄(장중 가집계)을 다시 묻는 주기 — 서버 값
const RANK_KEY = 'kis_proxy.INVESTOR_TOP_TTL';  // 「매매 동향」 탭이 다시 묻는 주기 — 서버 값(가집계 순위 캐시)
const INV_KEY = 'kis_proxy.INVESTOR_TTL';       // 투자자 줄을 다시 받는 주기 — 서버 값(15:40 확정치가 모달을 연 채로도 들어오게)

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

/* 투자자 줄은 종목마다 들고 있다가 서버 캐시 주기(INV_KEY)가 지나면 다시 받는다 — 전에는 모달이 떠 있는 동안 한 번뿐이라
   장 마감 뒤 확정치가 열린 모달에 안 들어왔다(2026-11-05) */
const invCache = new Map();
function investorRows(code) {
  const hit = invCache.get(code);
  if (!hit || Date.now() - hit.at >= serverMs(INV_KEY, FLOW_FALLBACK_MS)) {
    invCache.set(code, { at: Date.now(), p: getJson(`/api/kis/investor?code=${code}&span=60`).then((j) => (j && Array.isArray(j.data) ? j.data : [])) });
  }
  return invCache.get(code).p;
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
  const st = { tab: 'graph', trWho: 'foreign', trView: 'actor', trDay: '', fdMkt: 'KOSPI', side: 'foreign', days: 'today', mkt: 'ALL', target: code || '005930', names: {},
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
      tabs: [{ id: 'graph', label: '그래프' }, { id: 'chart', label: '차트' }, { id: 'today', label: '당일' }, { id: 'flow1m', label: '1분 흐름' }, { id: 'flowday', label: '날마다 수급' }, { id: 'trend', label: '매매 동향' }],
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
  /* 종목이면 주가가 아니라 금액이다(2026-11-05 재권님 「차트 투자자 지표에 주가 아니고 금액으로」 → 시안 vc 「응」) —
     날마다 개인 · 외국인 · 기관 순매수 금액(막대 · 왼쪽 축) + 그 기간 첫날부터 쌓은 금액(선 · 오른쪽 축). 값은 투자자 줄의
     netAmt(백만원 → 억) 그대로 · 없는 날은 그리지 않는다(0 아님) · 확정 전 오늘 줄도 비운다. 투자자 값은 하루 단위라 분봉은 없다.
     지수(코스피 · 코스닥)는 종목별 투자자 값이 없어 전처럼 지수 봉을 그린다 */
  async function amountBars() {
    const rows = (await investorRows(st.target)).slice().reverse();          // 오래된 날 → 최근
    const day = rows.map((r) => ({ ts: r.date, last: r.date, close: r.close,
      v: CHART_SIDES.map(([k]) => (confirmed(r) && (r[k] || {}).netAmt != null ? r[k].netAmt / 100 : null)) }));
    return day;
  }
  /** 한 날에 막대 셋을 나란히 — 라이브러리 히스토그램은 같은 날 막대를 겹쳐 그려 직접 그린다(custom series) */
  function groupBarSeries(colors) {
    let data = null;
    const renderer = {
      draw(target, toY) {
        if (!data || !data.visibleRange) return;
        target.useBitmapCoordinateSpace(({ context: c, horizontalPixelRatio: hr, verticalPixelRatio: vr }) => {
          const sp = data.barSpacing, w = (sp * 0.8) / colors.length, y0 = toY(0);
          if (y0 == null) return;
          c.globalAlpha = 0.45;
          for (let i = data.visibleRange.from; i < data.visibleRange.to; i++) {
            const b = data.bars[i];
            (b.originalData.v || []).forEach((x, j) => {
              if (x == null) return;
              const y = toY(x);
              if (y == null) return;
              c.fillStyle = colors[j];
              c.fillRect(Math.round((b.x - sp * 0.4 + w * j) * hr), Math.round(Math.min(y, y0) * vr),
                Math.max(1, Math.floor((w - 0.5) * hr)), Math.max(1, Math.round(Math.abs(y - y0) * vr)));
            });
          }
          c.globalAlpha = 1;
        });
      },
    };
    return {
      renderer: () => renderer,
      update: (d) => { data = d; },
      priceValueBuilder: (d) => { const v = (d.v || []).filter((x) => x != null); return v.length ? [Math.min(0, ...v), Math.max(0, ...v), v[v.length - 1]] : [0, 0, 0]; },
      isWhitespace: (d) => !d.v || d.v.every((x) => x == null),
      defaultOptions: () => ({}),
      destroy: () => {},
    };
  }
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
  /* 시간 좌표는 그림 칸 기준이라 왼쪽 눈금(금액 차트 · 11-05)이 있으면 그 폭만큼 차트 칸 왼쪽에서 밀린다 —
     상자를 잡을 때 빼고 그릴 때 더한다(2026-11-11 재권님 「6일 이후로 데이터가 없는데」 — 상자가 그 폭만큼 뒤 날짜를 골라 오늘(확정 전)이 잡혔다) */
  const paneLeft = () => {
    const sc = chart && chart.options().leftPriceScale;
    return sc && sc.visible ? chart.priceScale('left').width() : 0;
  };

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
    el.style.left = `${paneLeft() + Math.min(a, b) - half}px`;
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
    return { from: bars[from].ts.slice(0, 8), to: (bars[to].last || bars[to].ts).slice(0, 8), boxed: !!st.box };
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
    /* 오늘(확정 전) 줄 — 장중 가집계 최신 회차로 따로 보인다(2026-11-05 재권님 「응 해줘」). 가집계는 외국인 · 기관 **수량(주)** 뿐이고
       개인이 없어 위 금액 합에 더하지 않는다. 금액은 마지막 봉 종가 × 수량 어림 */
    const open = d.find((r) => !confirmed(r));
    let estLine = '';
    if (open) {
      const ej = await getJson(`/api/kis/investor-estimate?code=${st.target}`);
      const e = ej && ej.data && ej.data.latest;
      const lb = bars[bars.length - 1];
      const px = lb && lb.ts.slice(0, 8) === open.date ? lb.close : null;
      const one = (n, q) => `${n} <b class="${signClass(q)}">${fmtJu(q)}</b>${q != null && px ? ` <small>(≈${eokS(q * px / 1e6)})</small>` : ''}`;
      estLine = !ej ? '<div class="kh-ivm-est kh-ivm-mut">오늘 장중 가집계 — 못 받음</div>'
        : !e ? '<div class="kh-ivm-est kh-ivm-mut">오늘 장중 가집계 — 아직 없음(첫 회차 09:30 무렵)</div>'
        : `<div class="kh-ivm-est">오늘 ${mmdd(open.date)} 장중 가집계 ${e.seq}회차 — ${one('외국인', e.foreign)} · ${one('기관', e.inst)}
            <small>· 증권사 잠정치 · 개인은 안 줌 · 위 합에 안 넣음</small></div>`;
    }
    const sums = SIDES.map(([k, n]) => ({ k, n, s: sumSide(days, k) }));
    const max = Math.max(...sums.flatMap((x) => (x.s ? [x.s.buy, x.s.sell] : [0]))) || 1;
    const guess = sums.some((x) => x.s && x.s.guess);
    const oldest = all.length ? all[all.length - 1].date : null;
    const short = oldest && rg.from < oldest;
    if (rangeNow() && rangeNow().from !== rg.from) return;     // 그새 기간이 또 바뀌었다
    box.innerHTML = `<div class="kh-ivm-period"><b>${rg.boxed ? '점선 네모 안' : '보이는 기간'} ${range}</b> ·
        투자자 값 ${days.length}거래일${skipped ? ` · 오늘(확정 전) ${skipped}일 뺌` : ''}${short ? ` · ${oldest.slice(4, 6)}.${oldest.slice(6)} 앞은 받은 값이 없어 그 뒤만` : ''}</div>
      ${estLine}
      <div class="kh-ivm-cap"><div>← 매도</div><div class="kh-ivm-mid">투자자 · 순매수</div><div>매수 →</div></div>
      ${sums.map((x) => `<div class="kh-ivm-row kh-ivm-big">
          ${sideHtml(x.s && x.s.sell, max, true)}
          <div class="kh-ivm-mid"><b>${x.n}</b><br><small><span class="${signClass(x.s ? x.s.net : null)}">${eokS(x.s ? x.s.net : null)}</span></small></div>
          ${sideHtml(x.s && x.s.buy, max, false)}</div>`).join('')}
      <div class="kh-ivm-note">금액은 한국투자증권 확정치 합${guess ? ' · 매수 · 매도 금액 일부는 수량 × 종가 어림' : ''} ·
        투자자 값은 하루 단위라 분봉에서는 그 날짜들의 하루 값을 더함</div>`;
  }

  /* 막대(왼쪽 축) · 선(오른쪽 축) — 선은 제 값 범위에 꽉 차게(11-05 재권님 「선으로 된거는 좀더 디테일하게」 — 0 을 가운데 두니 선이
     칸의 반쯤에 눌려 있었다). 막대 축은 0 이 선 축의 0 과 같은 높이에 오게 맞춘다(위 = 산 쪽 · 아래 = 판 쪽) */
  function paintAmount(LC, el) {
    const colors = CHART_SIDES.map(([, , c]) => cssVar(c));
    const fmt = (v) => `${v > 0 ? '+' : ''}${Math.round(v).toLocaleString()}`;
    /* 범례 자리 — 폭을 숫자로 가르지 않고 범례가 실제로 차지한 높이만큼 위를 비운다(좁은 폭은 두 줄 · 기준 폭은 CSS 한 곳 · 개념정의 검수) */
    const leg = document.createElement('div');
    leg.className = 'kh-ivm-leg';
    el.appendChild(leg);
    chart.applyOptions({ leftPriceScale: { visible: true, borderColor: cssVar('--kh-chart-border') }, localization: { priceFormatter: fmt } });
    const cum = CHART_SIDES.map((_, j) => { let s = 0; return bars.map((b) => { if (b.v[j] == null) return null; s += b.v[j]; return s; }); });
    /* 보이는 봉만으로 범위를 잡는다 — 밀거나 넓히면 그 구간에 맞게 다시 꽉 찬다 */
    const vis = () => { const r = chart.timeScale().getVisibleLogicalRange(); return r ? [Math.max(0, Math.floor(r.from)), Math.min(bars.length - 1, Math.ceil(r.to))] : [0, bars.length - 1]; };
    const ranges = () => {
      const [a, b] = vis();
      const lv = cum.flatMap((c) => c.slice(a, b + 1)).filter((x) => x != null), bv = bars.slice(a, b + 1).flatMap((x) => x.v).filter((x) => x != null);
      let hi = Math.max(0, ...lv), lo = Math.min(0, ...lv);
      const pad = (hi - lo || 1) * 0.06; hi += hi > 0 ? pad : 0; lo -= lo < 0 ? pad : 0;
      let f = (hi - 0) / ((hi - lo) || 1);                  // 위에서 0 까지의 몫
      f = Math.min(0.85, Math.max(0.15, f));                // 0 이 맨 끝이면 막대 한쪽이 안 보인다 — 15% 는 남긴다
      const span = Math.max(hi / f, -lo / (1 - f)); hi = span * f; lo = -span * (1 - f);
      const k = Math.max(1, Math.max(0, ...bv) / f, -Math.min(0, ...bv) / (1 - f));
      return { line: { minValue: lo, maxValue: hi }, bar: { minValue: -k * (1 - f), maxValue: k * f } };
    };
    const bs = chart.addCustomSeries(groupBarSeries(colors), { priceScaleId: 'left', lastValueVisible: false, priceLineVisible: false,
      autoscaleInfoProvider: () => ({ priceRange: ranges().bar }) });
    bs.setData(bars.map((b) => (b.v.every((x) => x == null) ? { time: toTime(b.ts) } : { time: toTime(b.ts), v: b.v })));
    CHART_SIDES.forEach((_, j) => {
      const ls = chart.addSeries(LC.LineSeries, { color: colors[j], lineWidth: 2, priceScaleId: 'right', lastValueVisible: true, priceLineVisible: false,
        crosshairMarkerVisible: true, crosshairMarkerRadius: 3, autoscaleInfoProvider: () => ({ priceRange: ranges().line }) });
      ls.setData(bars.map((b, i) => (cum[j][i] == null ? { time: toTime(b.ts) } : { time: toTime(b.ts), value: cum[j][i] })));
    });
    series = bs;
    const last = (a) => { for (let i = a.length - 1; i >= 0; i--) if (a[i] != null) return a[i]; return null; };
    leg.innerHTML = `<span class="kh-ivm-mut">막대 날마다 · 선 쌓은 값(억)</span>${CHART_SIDES.map(([, n, c], j) => {
      const d = last(bars.map((b) => b.v[j])), s = last(cum[j]);
      return `<span><i style="background:var(${c})"></i>${n} <b class="${signClass(d)}">${d == null ? '—' : fmt(d)}</b> · 쌓은 <b class="${signClass(s)}">${s == null ? '—' : fmt(s)}</b></span>`;
    }).join('')}`;
    const top = Math.min(0.35, (leg.offsetHeight + 8) / (el.clientHeight || 1));
    chart.applyOptions({ leftPriceScale: { scaleMargins: { top, bottom: 0.04 } }, rightPriceScale: { scaleMargins: { top, bottom: 0.04 } } });
  }

  async function paintChart() {
    if (chart) { chart.remove(); chart = null; }
    /* 종목이면 장중 가집계 회차가 바뀔 때 오늘 줄을 다시 그린다 — 주기는 서버 값(EST_KEY) */
    stopFlow();
    if (/^\d{6}$/.test(st.target)) {
      flowWatch = watch({ url: () => (st.tab === 'chart' && /^\d{6}$/.test(st.target) ? `/api/kis/investor-estimate?code=${st.target}` : null),
        onChange: () => paintSides(), key: EST_KEY, fallbackMs: FLOW_FALLBACK_MS });
    }
    if (!INDEX[st.target] && st.period !== 'D') st.period = 'D';   // 칩을 그리기 전에 — 지수 분봉 · 월봉에서 종목으로 오면 「일봉」 이 켜진 채로(qa 덧 11-05)
    main.innerHTML = `<div class="kh-ivm-bar-row">
        ${chips('target', [[INDEX[st.target] ? (st.lastStock || code || '005930') : st.target, '종목'], ['KOSPI', '코스피'], ['KOSDAQ', '코스닥']], st.target)}
        ${chips('period', INDEX[st.target] ? PERIODS : AMT_PERIODS, st.period)}
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
    const amt = !INDEX[st.target];
    const got = amt ? await amountBars() : await candles();
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
    if (amt) paintAmount(LC, el);
    else {
      series = chart.addSeries(LC.CandlestickSeries, {
        upColor: cssVar('--kh-up'), downColor: cssVar('--kh-down'), borderVisible: false,
        wickUpColor: cssVar('--kh-up'), wickDownColor: cssVar('--kh-down'),
      });
      series.setData(bars.map((b) => ({ time: toTime(b.ts), open: b.open, high: b.high, low: b.low, close: b.close })));
    }
    if (bars.length) {
      const n = SHOW_BARS[st.period] || 60;
      chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, bars.length - n), to: bars.length - 1 });
    }

    /* 점선 네모 고르기 — 「구간 고르기」 를 켜면 차트 위 덮개가 끌기를 받는다(차트 밀기와 안 섞이게) */
    const pickEl = el.querySelector('.kh-ivm-pick');
    let start = null;
    const idxAt = (ev) => {
      const x = ev.clientX - el.getBoundingClientRect().left - paneLeft();
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
  /* 빈 칸 문구 — 못 받았으면 「못 받음」 · 받았는데 비었으면 「아직 없음」. 둘을 한 문구로 내면 「못 받음」 이 「없음」 으로 둔갑한다.
     다른 서버(세션 · 8764)도 8765 로 넘기거나 메인 DB 를 읽어 같은 값을 보므로 「여기서는 안 쌓는다」 갈래는 두지 않는다(10-27 정정) */
  const FLOW_EMPTY = {
    wait: '아직 쌓인 구간이 없습니다 · 평일 09:00~15:30',
    fail: '당일 수급을 못 받았습니다',
  };
  let flowEmpty = FLOW_EMPTY.wait;
  function stopFlow() { if (flowWatch) { flowWatch.stop(); flowWatch = null; } }

  /* 막대 칸 — 구간마다 위 매수 · 아래 매도 · 검은 가로줄 순매수. groups 가 여럿이면 나란히(색 = 그 투자자) */
  function bsSvg(rows, groups) {
    if (!rows.length) return `<div class="kh-ivt-empty">${flowEmpty}</div>`;
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

  /* 받는 대로 먼저 그린다(2026-11-05 재권님 「응 해줘」) — 전에는 네 주소를 다 받을 때까지 기다렸다. 칸 틀을 먼저 세우고
     주소마다 오는 대로 제 칸을 채운다. 틀은 종목이 바뀔 때만 다시 세운다(다시 받을 때 칸이 「불러오는 중」 으로 깜빡이지 않게) */
  const WAIT = '<span class="kh-ivm-mut">불러오는 중</span>';
  const card = (cls, head, slot) => `<section class="kh-ivt-card ${cls}"><div class="kh-ivt-h">${head}</div><div data-slot="${slot}">${WAIT}</div></section>`;
  function todayShell(code) {
    const nm = `<span data-nm>${esc(nameOf(code || '') || code || '')}</span>`;
    return `
      <div class="kh-ivt-col">
        ${card('', `코스피 — 투자자별 순매수 <small>오늘 누계 · <span data-slot="at"></span></small>`, 'total')}
        ${code ? card('', `${nm} — 외국인 · 기관 장중 <small>하루 다섯 번 · 주</small>`, 'est') : ''}
        ${code ? card('', `${nm} — 증권사 상위 5 <small>오늘 장중 누적</small>`, 'mem') : ''}
      </div>
      <div class="kh-ivt-col">
        ${card('is-tall', `코스피 투자자별 5분마다 <small>매수 · 매도 · 순매수 · 금액 · 수량(천주)</small>`, 'mk')}
        ${code ? card('', `${nm} — 기관 안 · 외국인 등록/미등록`, 'inst') : ''}
      </div>
      <div class="kh-ivt-col">
        ${card('', `코스피 프로그램 5분마다 <small>차익 + 비차익 · 수량은 KIS 가 안 줌</small>`, 'pg')}
        ${card('', `${code ? nm : '종목'} 프로그램 5분마다 <small data-slot="skh">금액 · 수량</small>`, 'sk')}
      </div>`;
  }

  function loadToday() {
    const code = stockCode();
    const box = main.querySelector('.kh-ivt');
    if (!box) return;
    if (box.dataset.code !== (code || '')) { box.dataset.code = code || ''; box.innerHTML = todayShell(code); }
    const live = () => st.tab === 'today' && box.isConnected && box.dataset.code === (code || '');
    const put = (slot, html) => { const el = live() && box.querySelector(`[data-slot="${slot}"]`); if (el) el.innerHTML = html; };

    if (code && !st.names[code]) {      // 처음 연 종목은 이름표가 아직 없다 — 시세에서 이름만 받는다(서버 캐시)
      getJson(`/api/kis/quotes?codes=${code}`).then((q) => {
        const nmq = q && q.data && q.data[code] && q.data[code].name;
        if (!nmq) return;
        st.names[code] = nmq;
        if (live()) box.querySelectorAll('[data-nm]').forEach((el) => { el.textContent = nmq; });
      });
    }

    getJson(`/api/kis/flow-today?step=5${code ? `&code=${code}` : ''}`).then((flow) => {
      const d = (flow && flow.data) || {};
      const mk = d.market || { rows: [] }, pg = d.program || { rows: [] }, sk = d.stock || null;
      flowEmpty = !flow || !flow.data ? FLOW_EMPTY.fail : FLOW_EMPTY.wait;
      const last = mk.last || null;
      put('at', mk.lastAt ? `${hhmm(mk.lastAt)} 까지` : '');
      put('total', last ? `${WHO3.map(([k, n]) => { const v = (last[k] || {}).net;
        return `<div class="kh-ivt-tot"><span>${n}</span><b class="${signClass(v)}">${fmtMil(v)}</b></div>`; }).join('')}
        <div class="kh-ivt-inst">기관 안 —${[['scrt', '증권'], ['ivtr', '투신'], ['pe_fund', '사모'], ['bank', '은행'], ['insu', '보험'], ['mrbn', '종금'], ['fund', '기금'], ['etc_corp', '기타법인']]
          .map(([k, n]) => ` <span>${n} <b class="${signClass((last.inst || {})[k])}">${fmtMil((last.inst || {})[k])}</b></span>`).join('')}</div>`
        : `<div class="kh-ivt-empty">${flowEmpty === FLOW_EMPTY.wait ? '아직 쌓인 값이 없습니다' : flowEmpty}</div>`);
      put('mk', bsSvg(mk.rows, WHO3.map(([k, , c]) => ({ v: (r) => r[k] || {}, up: c, down: c })))
        + `<div class="kh-ivt-lg">${WHO3.map(([, n, c]) => `<span style="color:var(${c})">■ ${n}</span>`).join('')}</div>`
        + bsTable(mk.rows, WHO3.map(([k, n, c]) => ({ h: `<span style="color:var(${c})">${n}</span>`, f: (r) => bsCell(r[k] || {}, fmtMil, fmtChu) })))
        + KEY_NOTE);
      put('pg', bsSvg(pg.rows, [{ v: (r) => r, ...PG }]) + bsTable(pg.rows, [{ h: '금액', f: (r) => bsCell(r, fmtMil) }]));
      put('skh', sk && !sk.rows.length && sk.watching ? '지금부터 쌓는 중' : '금액 · 수량');
      put('sk', !code ? '<div class="kh-ivt-empty">「차트」 탭 · 검색 · 실시간 순위에서 종목을 고르면 그 종목이 나옵니다</div>'
        : bsSvg((sk && sk.rows) || [], [{ v: (r) => r, ...PG }])
          + bsTable((sk && sk.rows) || [], [{ h: '금액', f: (r) => bsCell(r, fmtWon) },
            { h: '수량', f: (r) => bsCell({ net: r.netQty, buy: r.buyQty, sell: r.sellQty }, fmtJu) }]));
    });
    if (!code) return;

    /* 종목 장중 잠정치 — 하루 다섯 번 · 외국인 · 기관 누적(주) · 응답에 시각이 없다 */
    getJson(`/api/kis/investor-estimate?code=${code}`).then((est) => {
      const er = (est && est.data && est.data.rows) || [];
      put('est', !est ? '<div class="kh-ivt-empty">못 받음</div>' : `<div class="kh-ivt-seg">${[1, 2, 3, 4, 5].map((g) => { const e = er.find((x) => x.seq === g);
        return `<div><small>${g}회차</small>외 <b class="${signClass(e && e.foreign)}">${e ? fmtJu(e.foreign).replace('주', '') : '—'}</b><br>기 <b class="${signClass(e && e.inst)}">${e ? fmtJu(e.inst).replace('주', '') : '—'}</b></div>`; }).join('')}</div>
        <div class="kh-ivt-note">증권사 집계 잠정치 · 마감 뒤 확정치와 다름 · 개인은 안 줌</div>`);
    });

    /* 증권사 상위 5 — 오늘 장중 누적 */
    getJson(`/api/kis/investor-member?code=${code}`).then((mem) => {
      const mb = mem && mem.data;
      const side = (arr, cls) => (arr || []).map((x, i) => `<li><span>${i + 1}. ${esc(x.name)}${x.foreign ? ' <small>외국계</small>' : ''}</span><b class="${cls}">${fmtJu(x.qty, false)}</b></li>`).join('') || '<li>—</li>';
      put('mem', !mb ? '<div class="kh-ivt-empty">못 받음</div>'
        : `<div class="kh-ivt-mem"><div><small>매도 상위</small><ol>${side(mb.sell, 'kh-down')}</ol></div><div><small>매수 상위</small><ol>${side(mb.buy, 'kh-up')}</ol></div></div>`);
    });

    /* 기관 안 · 외국인 등록/미등록 — 확정치(마감 15:40 뒤). 맨 위 확정 줄 */
    getJson(`/api/kis/investor?code=${code}&span=5`).then((inv) => {
      const ir = ((inv && inv.data) || []).find((r) => r.instDetail);
      const names = (inv && inv.meta && inv.meta.instDetail) || [];
      put('inst', !inv ? '<div class="kh-ivt-empty">못 받음</div>' : !ir ? '<div class="kh-ivt-empty">확정치 없음 — 15:40 뒤</div>'
        : `<div class="kh-ivt-inst">${mmdd(ir.date)} 확정 —${names.map(([k, n]) => { const v = (ir.instDetail[k] || {}).netAmt;
          return ` <span>${esc(n)} <b class="${signClass(v)}">${fmtMil(v)}</b></span>`; }).join('')}
          ${[['foreignReg', '외국인 등록'], ['foreignNreg', '외국인 미등록'], ['etcCorp', '기타법인']].map(([k, n]) => { const v = (ir[k] || {}).netAmt;
            return ` <span>${n} <b class="${signClass(v)}">${fmtMil(v)}</b></span>`; }).join('')}</div>`);
    });
  }

  function paintToday() {
    main.innerHTML = `<div class="kh-ivm-bar-row"><span class="kh-ivm-asof">오늘 장중 · 5분마다 · 코스피</span>
      <span class="kh-ivm-mut">관심종목은 장중 내내 · 고른 종목은 고른 때부터 쌓입니다</span></div><div class="kh-ivt"><span class="kh-ivm-mut">불러오는 중</span></div>`;
    loadToday();
    stopFlow();
    flowWatch = watch({ url: () => `/api/kis/flow-today?step=5${stockCode() ? `&code=${stockCode()}` : ''}`,
      onChange: () => loadToday(), key: FLOW_KEY, fallbackMs: FLOW_FALLBACK_MS });
  }

  /* ── 1분 흐름 탭 — 코스피 투자자 갈래 1분 누계 ──
     값은 장중 잠정(확정치와 다르다 — server/flow_board.py 머리). 「없음」 은 null 그대로 「—」 · 선에서도 끊는다 */
  const F1_ON = new Set(['foreign', 'inst', 'person']);
  const F1_COLOR = { foreign: '--kh-ind-1', inst: '--kh-ind-2', person: '--kh-ind-3', etcCorp: '--kh-ind-4', scrt: '--kh-ind-5' };
  let f1 = null;
  const f1Eok = (mil) => (mil == null ? null : Math.round(mil) / 100);
  const f1Fmt = (v, d = 1) => { if (v == null) return '—'; const r = Number(v.toFixed(d)) || 0; return `${r > 0 ? '+' : ''}${r.toLocaleString('ko-KR', { maximumFractionDigits: d })}`; };
  const f1Cls = (v) => signClass(v == null ? v : Number(v.toFixed(1)));
  const f1Cum = (rows, k) => { let s = 0, any = false; return rows.map((r) => { if (r[k] == null) return any ? s / 100 : null; any = true; s += r[k]; return s / 100; }); };
  function f1Svg(rows, keys) {
    if (!rows.length) return `<div class="kh-ivt-empty">${flowEmpty}</div>`;
    const W = 1000, H = 260, P = 52;
    const ser = keys.map((k) => ({ k, v: f1Cum(rows, k) }));
    const all = ser.flatMap((x) => x.v).filter((v) => v != null);
    const lo = Math.min(0, ...all), hi = Math.max(0, ...all), n = Math.max(rows.length - 1, 1);
    const x = (i) => P + (W - P - 12) * i / n, y = (v) => 6 + (H - 30) * (hi - v) / ((hi - lo) || 1);
    const t = (tx, ty, a, txt) => `<text x="${tx}" y="${ty}" text-anchor="${a}" style="fill:var(--kh-text-secondary);font-size:12px">${txt}</text>`;
    let g = `<line x1="${P}" x2="${W - 12}" y1="${y(0)}" y2="${y(0)}" style="stroke:var(--kh-border-strong)"/>`;
    g += [hi, 0, lo].filter((v, i, a) => a.indexOf(v) === i).map((v) => t(P - 6, y(v) + 4, 'end', f1Fmt(v, 0))).join('');
    g += rows.map((r, i) => (/(00|30)$/.test(r.t) ? t(x(i), H - 4, 'middle', hhmm(r.t)) : '')).join('');
    for (const sr of ser) {
      let d = '', pen = false;
      sr.v.forEach((v, i) => { if (v == null) { pen = false; return; } d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`; pen = true; });
      g += `<path d="${d}" fill="none" style="stroke:var(${F1_COLOR[sr.k] || '--kh-text-secondary'});stroke-width:2"/>`;
    }
    return `<svg class="kh-ivf-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${g}</svg>`;
  }
  function f1Draw() {
    const box = main.querySelector('.kh-ivf');
    if (!box || !f1) return;
    const t = f1.today || {}, rows = t.rows || [];
    const groups = (f1.groups || []).filter((g) => g.of !== 'foreign');    // 외국인 등록 · 미등록은 장중 칸이 없다
    const keys = groups.filter((g) => F1_ON.has(g.key)).map((g) => g.key);
    const last = t.net || {};
    const tot = (list) => list.map((g) => { const v = f1Eok(last[g.key]), on = F1_ON.has(g.key);
      return `<button type="button" class="kh-ivf-tot${on ? ' is-on' : ''}" data-k="${g.key}"><span>${on ? `<i style="background:var(${F1_COLOR[g.key] || '--kh-text-secondary'})"></i>` : ''}${esc(g.name)}</span>
        <b class="${f1Cls(v)}">${v == null ? '—' : `${f1Fmt(v, 0)}억`}</b></button>`; }).join('');
    const fc = f1Cum(rows, 'foreign');
    const body = rows.map((r, i) => `<tr><td>${hhmm(r.t)}</td>${groups.map((g) => { const v = f1Eok(r[g.key]);
      return `<td class="${f1Cls(v)}">${f1Fmt(v)}</td>`; }).join('')}<td class="${f1Cls(fc[i])}">${f1Fmt(fc[i], 0)}</td></tr>`).reverse().join('');
    box.innerHTML = `
      <div class="kh-ivf-row">${tot(groups.filter((g) => !g.of))}</div>
      <div class="kh-ivf-row">${tot(groups.filter((g) => g.of === 'inst'))}</div>
      ${f1Svg(rows, keys)}
      <div class="kh-ivt-tb kh-ivf-tb"><table><thead><tr><th>시각</th>${groups.map((g) => `<th>${esc(g.name)}</th>`).join('')}<th>외국인 누계</th></tr></thead>
        <tbody>${body || `<tr><td colspan="${groups.length + 2}">${flowEmpty}</td></tr>`}</tbody></table></div>
      <div class="kh-ivt-note">누계 칸을 누르면 선을 켜고 끕니다 · 표는 그 1분 동안 순매수(억원) · 최근이 위</div>`;
  }
  async function loadFlow1m() {
    const r = await getJson('/api/kis/flow-board?days=1&step=1');
    if (st.tab !== 'flow1m' || !main.querySelector('.kh-ivf')) return;
    f1 = r && r.data;
    flowEmpty = !f1 ? FLOW_EMPTY.fail : FLOW_EMPTY.wait;
    const t = (f1 && f1.today) || {};
    const asof = main.querySelector('.kh-ivm-asof');
    if (asof) asof.textContent = `오늘 장중 · 1분마다 · 코스피 · 누계(억원)${t.lastAt ? ` · ${hhmm(t.lastAt)} 까지` : ''}`;
    if (!f1) { main.querySelector('.kh-ivf').innerHTML = `<div class="kh-ivt-empty">${FLOW_EMPTY.fail}</div>`; return; }
    f1Draw();
  }
  function paintFlow1m() {
    main.innerHTML = `<div class="kh-ivm-bar-row"><span class="kh-ivm-asof">오늘 장중 · 1분마다 · 코스피</span>
      <span class="kh-ivm-mut">장중 잠정 — 확정치와 다를 수 있습니다 · 코스피만</span></div><div class="kh-ivf"><span class="kh-ivm-mut">불러오는 중</span></div>`;
    main.querySelector('.kh-ivf').addEventListener('click', (e) => {
      const b = e.target.closest('.kh-ivf-tot');
      if (!b) return;
      F1_ON.has(b.dataset.k) ? F1_ON.delete(b.dataset.k) : F1_ON.add(b.dataset.k);
      f1Draw();
    });
    loadFlow1m();
    stopFlow();
    flowWatch = watch({ url: () => '/api/kis/flow-board?days=1&step=1', onChange: () => loadFlow1m(), key: FLOW_KEY, fallbackMs: FLOW_FALLBACK_MS });
  }

  /* ── 날마다 수급 탭 — 날짜 세로 · 투자자 갈래 가로 ──
     days 는 확정치 · 맨 위 오늘 줄만 장중 잠정(코스피만). 「없음」 은 null 그대로 「—」 */
  const FD_DAYS = 20;
  let fd = null;
  const fdEok = (mil) => { if (mil == null) return '<td>—</td>'; const v = Math.round(mil / 100) || 0;
    return `<td class="${signClass(v)}">${v > 0 ? '+' : ''}${v.toLocaleString('ko-KR')}</td>`; };
  const fdPct = (n) => (n == null ? '<td>—</td>' : `<td class="${signClass(n)}">${n > 0 ? '+' : ''}${Number(n).toFixed(2)}%</td>`);
  function fdDraw() {
    const box = main.querySelector('.kh-ivd');
    if (!box) return;
    if (!fd || !Array.isArray(fd.groups) || !fd.days) { box.innerHTML = `<div class="kh-ivt-empty">${FLOW_EMPTY.fail}</div>`; return; }
    const G = fd.groups, mk = st.fdMkt;
    const days = (fd.days[mk] || []).slice().sort((a, b) => String(b.date).localeCompare(String(a.date)));
    const t = mk === 'KOSPI' ? fd.today : null;
    const why = mk === 'KOSPI' ? ((t && t.reason) || '장중 값 없음') : '코스닥 장중 값은 서버가 아직 안 줍니다';
    const today = `<tr class="kh-ivd-today"><td>오늘 · 장중 잠정${t && t.lastAt ? ` ${hhmm(t.lastAt)}` : ''}</td>${t && t.net
      ? `<td>—</td>${G.map((g) => fdEok(t.net[g.key])).join('')}` : `<td colspan="${G.length + 1}" class="kh-ivm-mut">${esc(why)}</td>`}</tr>`;
    const line = (x) => `<tr><td>${fdDate(x.date)}</td>${fdPct(x.indexPct)}${G.map((g) => fdEok((x.net || {})[g.key])).join('')}</tr>`;
    const err = Object.keys(fd.errors || {}).filter((k) => k.startsWith('days') || k === 'today');
    box.innerHTML = `<div class="kh-ivt-tb kh-ivd-tb"><table><thead><tr><th>날짜</th><th>지수</th>${G.map((g) => `<th class="${g.of ? 'kh-ivd-sub' : ''}">${esc(g.name)}</th>`).join('')}</tr></thead>
      <tbody>${today}${days.length ? days.map(line).join('') : `<tr><td colspan="${G.length + 2}">아직 쌓인 날이 없습니다</td></tr>`}</tbody></table></div>
      <div class="kh-ivt-note">순매수 · 억원 · 새 날이 위 · 옅은 머리는 묶음 안 세부(외국인 안 · 기관계 안)${err.length ? ` · 못 받은 자리 ${esc(err.join(', '))}` : ''}</div>`;
  }
  async function loadFlowDay() {
    const r = await getJson(`/api/kis/flow-board?days=${FD_DAYS}`);
    if (st.tab !== 'flowday' || !main.querySelector('.kh-ivd')) return;
    fd = r && r.data;
    fdDraw();
  }
  function paintFlowDay() {
    main.innerHTML = `<div class="kh-ivm-bar-row">${chips('fdMkt', [['KOSPI', '코스피'], ['KOSDAQ', '코스닥']], st.fdMkt)}
      <span class="kh-ivm-asof">날마다 투자자별 순매수 · 확정치 · 최근 ${FD_DAYS}거래일</span>
      <span class="kh-ivm-mut">오늘 줄만 장중 잠정 — 확정치와 다를 수 있습니다</span></div><div class="kh-ivd"><span class="kh-ivm-mut">불러오는 중</span></div>`;
    bindChips((g, v) => { st[g] = v; main.querySelectorAll('.kh-chips[data-g="fdMkt"] .kh-chip').forEach((b) => b.classList.toggle('is-active', b.dataset.v === v)); fdDraw(); });
    if (fd) fdDraw();
    loadFlowDay();
    stopFlow();
    flowWatch = watch({ url: () => `/api/kis/flow-board?days=${FD_DAYS}`, onChange: () => loadFlowDay(), key: FLOW_KEY, fallbackMs: FLOW_FALLBACK_MS });
  }

  /* ── 매매 동향 탭 — 외국인 · 기관 순매수 순위 · 특이 매수(전일 순매도 → 오늘 순매수) ──
     오늘은 가집계(증권사 장중 입력 · 하루 네 번) · 전일은 확정치 · 날짜를 고르면 그날 남긴 판. 줄을 누르면 차트 탭이 그 종목 */
  /* 날짜 「MM-DD(요일)」 — 매매 동향 · 날마다 수급이 함께 쓴다 */
  const KDAY = '일월화수목금토';
  const fdDate = (s) => { const x = new Date(`${s}T00:00:00Z`); return s && !isNaN(x) ? `${s.slice(5)}(${KDAY[x.getUTCDay()]})` : esc(s || '—'); };
  let tr = null;
  const trUrl = () => (st.trView === 'actor' ? '/api/kis/flow-rank?view=actor'
    : `/api/kis/flow-rank?who=${st.trWho}${st.trDay ? `&day=${st.trDay}` : ''}`);
  /* 주체별 — 종목마다 주체 순매수(확정치) · 매수 우위 주체가 많은 종목이 위. 기관계는 기관 안 여덟의 합이라 칸만 두고 세지 않는다(서버 sumOf) */
  function actorDraw(box, b) {
    const acts = b.actors || [];
    const sub = new Set(Object.values(b.sumOf || {}).flat());
    const lead = new Set(b.lead || []);
    const head = acts.map(([k, n]) => `<th class="${sub.has(k) && !lead.has(k) ? 'kh-ivd-sub' : ''}${lead.has(k) ? ' kh-ivr-lead' : ''}">${esc(n)}</th>`).join('');
    const cell = (v) => (v == null ? '<td>—</td>' : `<td class="${signClass(v)}${v > 0 ? ' kh-ivr-buy' : ''}">${trEok(v)}</td>`);
    const tags = (x) => (x.top ? '<span class="kh-ivr-tag">기관 · 외국인 · 프로그램 매수</span>' : '') + (x.fund ? '<span class="kh-ivr-tag is-both">연기금 매수</span>' : '');
    const line = (x) => `<tr data-code="${esc(x.code)}" class="${x.top ? 'is-top' : ''}"><td><b>${esc(x.name)}</b>${tags(x)}</td>
      <td class="kh-ivr-n"><b>${x.buyers}</b><small>/${x.counted}</small></td>${acts.map(([k]) => cell((x.net || {})[k])).join('')}</tr>`;
    const day = b.day ? fdDate(`${b.day.slice(0, 4)}-${b.day.slice(4, 6)}-${b.day.slice(6)}`) : '—';
    box.innerHTML = `<div class="kh-ivt-tb kh-ivr-tb"><table><thead><tr><th>종목</th><th>매수 우위</th>${head}</tr></thead>
      <tbody>${(b.rows || []).length ? b.rows.map(line).join('') : '<tr><td colspan="99" class="kh-ivm-mut">쌓인 종목이 없습니다</td></tr>'}</tbody></table></div>
      <div class="kh-ivt-note">${esc(b.basis || '')} ${day} · 순매수 억원 · 바탕 칠한 칸이 순매수 · 줄 차례 = ① 기관 · 외국인 · 프로그램 셋 다 매수 ② 연기금 매수 ③ 셋 중 산 수 ④ 매수 우위 주체 수 ⑤ 순매수 금액 합 ·
        「매수 우위」 = 순매수인 주체 수 / 값이 있는 주체 수(개인 · 외국인 · 기관 안 여덟 · 기타법인 — 기관계는 기관 안의 합 · 프로그램은 매매 방식이라 세지 않음) ·${b.pgMissing ? ` 프로그램 받는 중 ${b.pgMissing}종목 ·` : ''}
        종목별 주체 세부는 KIS 가 15:40 뒤에만 줘서 장중에는 지난 거래일 값 · 지금은 화면에서 열어 본 ${(b.rows || []).length}종목만 쌓여 있음</div>`;
    box.querySelectorAll('tr[data-code]').forEach((el) => el.addEventListener('click', () => pick(el.dataset.code, el.querySelector('b').textContent)));
  }
  /* 억원 · 10억 아래는 소수 한 자리 — 1억 안쪽 순매도가 「−0억」 으로 보이지 않게 */
  const trEok = (mil) => { if (mil == null) return '—'; const v = mil / 100, t = Math.abs(v) < 10 ? v.toFixed(1) : Math.round(v).toLocaleString();
    return `${v > 0 ? '+' : ''}${t}억`; };
  const trPct = (n) => (n == null ? '—' : `${n > 0 ? '+' : ''}${Number(n).toFixed(2)}%`);
  function trDraw() {
    const box = main.querySelector('.kh-ivr');
    if (!box) return;
    const b = tr && tr.data;
    const meta = (tr && tr.meta) || {};
    const sel = main.querySelector('.kh-ivr-day');
    if (sel) {
      const today = b && !st.trDay ? b.day : '';
      const days = [...new Set([...(today ? [today] : []), ...(meta.days || [])])];
      sel.innerHTML = `<option value="">오늘 · 가집계</option>${days.filter((d) => d !== (b && !st.trDay ? b.day : '')).map((d) =>
        `<option value="${esc(d)}"${d === st.trDay ? ' selected' : ''}>${fdDate(`${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6)}`)} 남긴 판</option>`).join('')}`;
    }
    if (b && st.trView === 'actor') { actorDraw(box, b); return; }
    if (!b) { box.innerHTML = `<div class="kh-ivt-empty">${tr && tr.ok === false ? esc(tr.error || '못 받았습니다') : (st.trDay ? '그날 남긴 판이 없습니다' : '불러오는 중')}</div>`; return; }
    const byCode = Object.fromEntries((b.rows || []).map((x) => [x.code, x]));
    const sp = (b.special || []).map((c) => byCode[c]).filter(Boolean);
    main.querySelectorAll('.kh-chips[data-g="trView"] .kh-chip').forEach((el) => {
      if (el.dataset.v === 'special') el.textContent = `특이 매수(${sp.length})`;
    });
    const list = st.trView === 'special' ? sp : (b.rows || []);
    const other = st.trWho === 'foreign' ? '기관' : '외국인';
    const line = (x) => {
      const tags = [x.flip ? '<span class="kh-ivr-tag">전환</span>' : '', x.both ? `<span class="kh-ivr-tag is-both">${other}도 순매수</span>` : ''].join('');
      const prev = trEok(x.prevNet);
      return `<tr data-code="${esc(x.code)}"><td><b>${esc(x.name || x.code)}</b> <small>${x.market === 'KOSDAQ' ? '코스닥' : '코스피'} · 순매수 ${x.rank}위</small>${tags}</td>
        <td class="${signClass(x.net)}">${trEok(x.net)}</td><td class="${signClass(x.prevNet)}">${prev}</td>
        <td>${x.power == null ? '—' : `${x.power.toFixed(1)}%`}</td><td class="${signClass(x.pct)}">${trPct(x.pct)}</td></tr>`;
    };
    const wait = b.prevMissing ? ` · 전일 확정치 받는 중 ${b.prevMissing}종목` : '';
    box.innerHTML = `<div class="kh-ivt-tb kh-ivr-tb"><table><thead><tr><th>종목</th><th>오늘 순매수</th><th>전일 순매수</th><th>강도</th><th>등락률</th></tr></thead>
      <tbody>${list.length ? list.map(line).join('') : `<tr><td colspan="5" class="kh-ivm-mut">${st.trView === 'special' ? (b.prevMissing ? '전일 확정치를 받는 중입니다' : '전일 순매도 → 오늘 순매수로 바뀐 종목이 없습니다') : '순매수 종목이 없습니다'}</td></tr>`}</tbody></table></div>
      <div class="kh-ivt-note">${esc(b.basis || '')} ${esc(b.at || '')} 기준 · 순위는 코스피 · 코스닥 순매수 상위(수량 · 금액)를 합친 ${b.rows.length}종목 안 차례 · 억원 · 강도 = 오늘 순매수 ÷ 거래대금(거래량 × 현재가)${b.rows.some((x) => x.both) ? ` · ${other}도 순매수면 그 몫을 더함` : ''} · 전일은 확정치${wait}${b.errors ? ` · 못 받음 ${esc(b.errors)}` : ''}</div>`;
    box.querySelectorAll('tr[data-code]').forEach((el) => el.addEventListener('click', () => pick(el.dataset.code, (byCode[el.dataset.code] || {}).name)));
  }
  async function loadTrend() {
    const want = trUrl();
    const r = await getJson(want);
    if (st.tab !== 'trend' || trUrl() !== want || !main.querySelector('.kh-ivr')) return;
    tr = r;
    trDraw();
  }
  function paintTrend() {
    const actor = st.trView === 'actor';   // 주체별 — 서버가 프로그램을 뒤에서 채우는 동안 같은 주소를 서버 주기로 다시 묻는다
    main.innerHTML = `<div class="kh-ivm-bar-row">${chips('trView', [['actor', '주체별'], ['rank', '순위'], ['special', '특이 매수']], st.trView)}
      ${actor ? '<span class="kh-ivm-mut">기관 · 외국인 · 프로그램이 함께 산 종목이 맨 위 · 그다음 연기금</span>'
        : `${chips('trWho', [['foreign', '외국인'], ['inst', '기관']], st.trWho)}
      <select class="kh-ivr-day" aria-label="날짜"><option value="">오늘 · 가집계</option></select>
      <span class="kh-ivm-mut">특이 매수 = 전일 순매도 → 오늘 순매수 · 강도 순</span>`}</div><div class="kh-ivr"><span class="kh-ivm-mut">불러오는 중</span></div>`;
    bindChips((g, v) => { const was = st.trView; st[g] = v;
      if (g === 'trWho' || (g === 'trView' && (v === 'actor') !== (was === 'actor'))) { tr = null; paintTrend(); } else {
      main.querySelectorAll(`.kh-chips[data-g="${g}"] .kh-chip`).forEach((el) => el.classList.toggle('is-active', el.dataset.v === v)); trDraw(); } });
    if (!actor) main.querySelector('.kh-ivr-day').addEventListener('change', (e) => { st.trDay = e.target.value; tr = null; trDraw(); loadTrend(); });
    if (tr) trDraw();
    loadTrend();
    stopFlow();
    flowWatch = watch({ url: () => trUrl(), onChange: () => loadTrend(), key: RANK_KEY, fallbackMs: FLOW_FALLBACK_MS });
  }

  function paint() {
    if (st.tab !== 'today' && st.tab !== 'flow1m' && st.tab !== 'flowday' && st.tab !== 'trend') stopFlow();
    if (st.tab !== 'chart') { if (chart) { chart.remove(); chart = null; } }
    if (st.tab === 'graph') paintGraph();
    else if (st.tab === 'today') paintToday();
    else if (st.tab === 'flow1m') paintFlow1m();
    else if (st.tab === 'flowday') paintFlowDay();
    else if (st.tab === 'trend') paintTrend();
    else paintChart();
  }
  paint();
  return m;
}
