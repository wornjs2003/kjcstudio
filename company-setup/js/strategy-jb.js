// 투자 전략 「종가배팅」 — 단타 판 위 탭 「단타 · 종가배팅」 과 종가배팅 판 (2026-11-18 · 시황분석)
//   · 재권님 「단타 옆에 종가배팅 이라고 만들어서 넣으면 좋을거 같은데 이미지로 먼저 그려봐」 → 시안 temp/시황분석-jb-1156 → 「버튼이 아래에 나오는표와 분리되는 느낌인데
//     하나처럼 보이게 수정해서 먼저 그려봐」 → 시안 temp/시황분석-jb-1205(탭을 판 위에 붙임) → 「응 만들어」
//   · 룰(디앤서 영상 대입 · 시황분석 계산) — 정규장 강한 종목 중 장 뒤(넥스트레이드 15:40~20:00)에서 정규장 종가를 지킨 것을 17시 뒤 종가 가격에 사고,
//     다음 날 프리장 첫 값에 판다(높으면 익절 · 낮으면 손절) · 시황(지수 20일선 · 고점 대비)이 나쁘면 안 한다
//   · 후보 · 통과 여부 · 시황 판정은 서버 한 곳(/api/nxt/closing-bet · 주식 레인 개발1 — 작업우선순위 11-18 배분) — 화면은 그리기만.
//     화면이 세는 것은 결과 % (프리장 첫 값 ÷ 정규장 종가 − 1) 하나 · 비용은 안 뺌
//     응답(개발1 11-18 확정): data { day, preDay, mkt{kospi{chg, ma20Above, fromHigh, go}, kosdaq{…}}, rows[{code, name, market, cap, chg, pos, value, close,
//       rebreakAt, afterLow, afterLast, pre, pass{rise, pos, top, rebreak, mkt}, buy}] } · meta { days[YYYYMMDD …최근 먼저], rule{rise, limitUp, pos, top, big, cand, ma, highDays, fromHigh}, afterEverySec } · 모르는 판정은 null(모름)
//   · 값이 없으면 — (0 이 아니다) · 서버를 다시 묻는 주기는 없다(날을 누를 때 · 처음 열 때 한 번)
//   · 탭은 단타 판(#dt-host · strategy-dt30.js · 시황분석1)과 이 판(#jb-host) 둘 다의 카드 바로 위에 같은 줄로 붙인다 — 단타 판 코드는 안 건드린다
import { signClass, NUM } from '/assets/js/sign.js';

const API = '/api/nxt/closing-bet';
const KEY = 'insight.strategy.jbTab';   // 고른 탭 — 보는 사람 브라우저에만(편의 · 없어도 단타가 기본)
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (x, d = 0) => (x == null || !Number.isFinite(Number(x)) ? '—' : Number(x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (x, d = 2) => { if (x == null || !Number.isFinite(x)) return '—'; const c = signClass(x, NUM); const t = `${x > 0 ? '+' : ''}${num(x, d)}%`; return c ? `<span class="${c}">${t}</span>` : t; };
const capTxt = (e) => { const v = Number(e); if (e == null || !Number.isFinite(v)) return '—'; return v >= 10000 ? `${num(v / 10000, 1)}조` : `${num(v)}억`; };
const WK = ['일', '월', '화', '수', '목', '금', '토'];
const dayTxt = (d) => { const m = String(d || '').match(/^(\d{4})(\d{2})(\d{2})$/); return m ? `${m[2]}-${m[3]}(${WK[new Date(+m[1], +m[2] - 1, +m[3]).getDay()]})` : '—'; };
const hmTxt = (t) => (/^\d{4}$/.test(String(t)) ? `${String(t).slice(0, 2)}:${String(t).slice(2)}` : '—');
const MKT = { kospi: '코스피', kosdaq: '코스닥' };
const ok = (b) => (b == null ? '<span class="jb-unk" aria-label="모름">모름</span>' : b ? '<b class="jb-ok" aria-label="통과">●</b>' : '<span class="jb-no" aria-label="안 됨">—</span>');

const host = document.getElementById('jb-host');
const st = { day: null, days: [], seq: 0, tab: 'dt' };
try { if (localStorage.getItem(KEY) === 'jb') st.tab = 'jb'; } catch (e) { /* 저장 못 쓰는 창 — 단타가 기본 */ }

// 탭 줄 — 두 판 카드 위에 같은 것을 하나씩
const TABS = `<div class="jb-ftabs" role="tablist" aria-label="단타 · 종가배팅">
  <button type="button" class="jb-ft" role="tab" data-jbtab="dt">단타<small>09:01 매수 → 30분마다 14:00</small></button><button type="button" class="jb-ft" role="tab" data-jbtab="jb">종가배팅<small>장 뒤 매수 → 프리장 첫 값</small></button>
</div>`;
function tabsInto(h) {
  if (!h || h.querySelector(':scope > .jb-ftabs')) return;
  const card = h.querySelector(':scope > .st-card');
  if (!card) return;
  card.insertAdjacentHTML('beforebegin', TABS);
  card.classList.add('jb-attached');
  paintTabs();
}
// 탭을 바꿔도 판 자리는 그대로(「보는 것을 바꿔도 자리는 그대로다」 — 갈아 끼우기) — 지금 보이던 판 높이를 새로 보일 판의 최소 높이로 · qa 11-18 실측 1096 → 303
function holdHeight(from, to) {
  if (!from || !to || from.hidden) return;
  const h = from.getBoundingClientRect().height;
  if (h > 0) to.style.minHeight = `${Math.max(h, parseFloat(to.style.minHeight) || 0)}px`;
}
function paintTabs() {
  document.querySelectorAll('[data-jbtab]').forEach((b) => { const on = b.dataset.jbtab === st.tab; b.classList.toggle('is-on', on); b.setAttribute('aria-selected', String(on)); });
  const dt = document.getElementById('dt-host');
  if (dt) dt.hidden = st.tab !== 'dt';
  if (host) host.hidden = st.tab !== 'jb';
}
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-jbtab]');
  if (!b) return;
  const dt = document.getElementById('dt-host');
  if (b.dataset.jbtab !== st.tab) holdHeight(st.tab === 'dt' ? dt : host, st.tab === 'dt' ? host : dt);
  st.tab = b.dataset.jbtab;
  try { localStorage.setItem(KEY, st.tab); } catch (err) { /* 저장 못 해도 지금 창은 바뀜 */ }
  paintTabs();
  if (st.tab === 'jb' && !st.loaded) load();
});

const TPL = `
  <div class="st-meta" id="jb-meta">값을 받는 중…</div>
  <h2 class="st-sec">종가배팅 — 장 뒤 정규장 종가 지킴 확인 → 장 뒤 매수 → 다음 날 프리장 첫 값에 팜</h2>
  <div class="st-tg jb-days" id="jb-days" role="tablist" aria-label="날짜"></div>
  <div class="st-card">
    <div class="st-cap">당일 강했던 종목 중 장 뒤(넥스트레이드 15:40~20:00)에서 정규장 종가를 지킨 것을 17시 뒤 종가 가격에 사고, 다음 날 프리장 첫 값에 팜(높으면 익절 · 낮으면 손절) · 날마다 쌓음</div>
    <div class="jb-mk" id="jb-mk">—</div>
    <div class="jb-rules" id="jb-rules"></div>
    <div class="st-scroll" id="jb-box"><div class="st-err">—</div></div>
    <div class="st-cap jb-foot">결과 = 다음 날 프리장 첫 값 ÷ 정규장 종가 − 1(비용 전) · 「안 삼」 종목도 샀다면 얼마였는지 함께 적음 · 2년 대입(2025-03 ~ 2026-11 · 장 뒤 지킴 + 시황 할 때) 233건 · 승률 73% · 한 건 평균 +1.65%(비용 0.23% 뺌 · 시황분석 11-18 계산)</div>
  </div>`;

function rulesHtml(r) {
  // 기준 값은 서버 meta.rule 한 곳(개발1 · 11-18) — 화면에 숫자를 두지 않는다
  const v = (k, d = 0) => (r?.[k] != null ? num(r[k], d) : '—');
  return `<span class="st-cap jb-lb">룰</span>
    <span class="jb-rule">① 정규장 +${v('rise')}% ↑ (삼성전자 · 하이닉스 +${v('big')}% · +${v('limitUp', 1)}% ↑ 는 종가에 못 사서 뺌)</span><span class="jb-rule">② 종가가 고가 바로 밑(${v('pos', 1)} ↑)</span><span class="jb-rule">③ ①② 통과 중 거래대금 상위 ${v('top')}</span>
    <span class="jb-rule">④ 17시 뒤 정규장 종가 다시 넘음</span><span class="jb-rule">⑤ 시황 — 그 종목 시장 지수가 ${v('ma')}일선 위 · 앞 ${v('highDays')}거래일 종가 최고 대비 ${v('fromHigh')}% 안</span>`;
}
function mkHtml(d) {
  const m = d.mkt || {};
  // 시장마다 판정(mkt.kospi.go · mkt.kosdaq.go) — 판정 알약은 오르내림 색을 안 쓴다(개념정의 11-18 · 오르내림 숫자가 아님)
  const goTxt = (g) => (g == null ? '<span class="jb-go is-unk">판정 없음</span>' : g ? '<span class="jb-go is-go">함</span>' : '<span class="jb-go is-stop">안 함</span>');
  const one = (k) => { const x = m[k]; if (!x) return `<span>${MKT[k]} —</span>`; return `<span>${MKT[k]} ${pct(x.chg)} · 20일선 ${x.ma20Above == null ? '—' : x.ma20Above ? '위' : '아래'} · 고점 대비 ${pct(x.fromHigh, 1)} ${goTxt(x.go)}</span>`; };
  return `<b>${dayTxt(d.day)} 시황</b>${one('kospi')}${one('kosdaq')}`;
}
function tableHtml(d) {
  const rows = Array.isArray(d.rows) ? d.rows : [];
  if (!rows.length) return '<div class="st-err">— 이 날 후보 없음</div>';
  const pre = d.preDay ? `${dayTxt(d.preDay)} 프리장 첫 값` : '다음 날 프리장 첫 값';
  const line = (r, i) => {
    const res = r.pre != null && r.close ? (r.pre / r.close - 1) * 100 : null;
    const why = res == null ? (d.preDay ? '프리장 값 없음' : '아직') : `${res > 0 ? '익절' : res < 0 ? '손절' : '본전'}${r.buy ? '' : '(샀다면)'}`;
    const p = r.pass || {};
    return `<tr class="${r.buy ? 'jb-buy' : ''}"><td>${i + 1}</td><td class="st-name" data-co="${esc(r.code)}"><b>${esc(r.name || '—')}</b><small>${esc(r.code || '')} · ${MKT[r.market] || '—'} · ${capTxt(r.cap)}</small></td>
      <td>${pct(r.chg)}</td><td>${num(r.pos, 2)}</td><td>${r.value == null ? '—' : `${num(r.value)}억`}</td><td>${num(r.close)}</td>
      <td>${hmTxt(r.rebreakAt)}</td><td>${num(r.afterLow)}</td><td>${num(r.afterLast)}<small>${r.afterLast != null && r.close ? pct((r.afterLast / r.close - 1) * 100) : ''}</small></td>
      <td class="jb-c">${ok(p.rise)}</td><td class="jb-c">${ok(p.pos)}</td><td class="jb-c">${ok(p.top)}</td><td class="jb-c">${ok(p.rebreak)}</td><td class="jb-c">${ok(p.mkt)}</td>
      <td class="jb-c"><b>${r.buy == null ? '모름' : r.buy ? '삼' : '안 삼'}</b></td><td>${num(r.pre)}</td><td class="jb-res">${pct(res)}<small>${why}</small></td></tr>`;
  };
  return `<table class="jb-tb"><tr><th></th><th class="st-name">종목</th><th>정규장 등락</th><th>종가 위치</th><th>거래대금</th><th>정규장 종가</th><th>17시 뒤 넘은 때</th><th>장 뒤 저가</th><th>20:00 값</th>
    <th class="jb-c">①</th><th class="jb-c">②</th><th class="jb-c">③</th><th class="jb-c">④</th><th class="jb-c">⑤</th><th class="jb-c">판단</th><th>${pre}</th><th>결과</th></tr>${rows.map(line).join('')}</table>`;
}
function paintDays() {
  const box = host.querySelector('#jb-days');
  box.innerHTML = st.days.map((d) => `<button type="button" class="kh-chip${d === st.day ? ' is-active' : ''}" role="tab" aria-selected="${d === st.day}" data-jbday="${d}">${dayTxt(d)}</button>`).join('');
}
async function load(day) {
  st.loaded = true;
  const seq = ++st.seq;
  const meta = host.querySelector('#jb-meta');
  meta.textContent = '값을 받는 중…';
  let j = null, why = '';
  try {
    const res = await fetch(`${API}${day ? `?day=${day}` : ''}`, { cache: 'no-store' });
    if (res.status === 404 || res.status === 403) why = '서버 값 기다림 — 후보를 뽑는 서버 칸(주식 레인)이 아직 없음';
    else if (!res.ok) why = `서버 응답 ${res.status}(받지 못함)`;
    else j = await res.json();
  } catch (e) { why = '서버에 닿지 못함'; }
  if (seq !== st.seq) return;
  if (!j || !j.data) {
    meta.textContent = why || '값 없음';
    host.querySelector('#jb-box').innerHTML = `<div class="st-err">— ${esc(why || '값 없음')}</div>`;
    host.querySelector('#jb-rules').innerHTML = rulesHtml(null);
    return;
  }
  paint(j.data, j.meta || {});
}
// 그리기 — 받은 값 그대로(시안 · 시험에서도 이것을 부른다)
export function paint(d, m = {}) {
  st.day = d.day; st.days = Array.isArray(m.days) && m.days.length ? m.days : [d.day];
  host.querySelector('#jb-meta').textContent = `${dayTxt(d.day)} 판 · 후보 ${Array.isArray(d.rows) ? d.rows.length : 0} · 산 것 ${(d.rows || []).filter((r) => r.buy).length}`;
  paintDays();
  host.querySelector('#jb-mk').innerHTML = mkHtml(d);
  host.querySelector('#jb-rules').innerHTML = rulesHtml(m.rule);
  host.querySelector('#jb-box').innerHTML = tableHtml(d);
}

if (host) {
  host.classList.add('st', 'jb');
  host.innerHTML = TPL;
  host.addEventListener('click', (e) => { const b = e.target.closest('[data-jbday]'); if (b && b.dataset.jbday !== st.day) load(b.dataset.jbday); });
  tabsInto(host);
  const dt = document.getElementById('dt-host');
  tabsInto(dt);
  if (dt) new MutationObserver(() => tabsInto(dt)).observe(dt, { childList: true });   // 단타 판이 다시 그려져도(mountDt30) 탭을 다시 붙인다
  paintTabs();
  if (st.tab === 'jb') load();
}
