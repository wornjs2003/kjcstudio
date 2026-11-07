// 투자 전략 하위 탭 · 종목 기록 (2026-11-07 · 시황분석1)
//   · 재권님 「기록을 어디에다가 쌓아놔야 하는데 투자전략에다가 하위로 텝 만들어서 넣어노면 좋을거같은데」(개발2 창) → 시안 temp/시황분석1-wl-rec.png 에 「응」
//   · 값은 서버 한 곳 — GET /api/watch-log?day=YYYYMMDD (server/watch_log.py · 주식 레인). 셈(전일비 · 프리 · 정규 · 애프터)은 서버가 하고 화면은 그린다
//     data { day, saved, days[], counts{어디서: 수}, rows[{code,name,src[],prev,last,pct,pre,reg,aft,n,line[[HHMM,종가]]}] } · 값이 없으면 — (0 이 아니다)
//   · 날짜는 서버가 쌓은 날(days) + 오늘만 넘긴다 · 오늘 줄이 비었으면(장 없는 날 · 아직 이른 때) 쌓인 가장 최근 날을 연다
//   · 탭은 주소 꼬리 #log 로 기억한다(새로고침해도 그 탭) — 서버를 다시 묻는 주기는 없다(평일 20:05 하루 한 번 쌓임)
import { signClass, side, NUM } from '/assets/js/sign.js';   // 오르내림 글씨 · 선 색 — 셈은 sign.js 한 곳

const API = '/api/watch-log';
const SRC = ['관심', '자동', 'VI', '급등', '매수'];   // 칩 차례 — 서버 src 이름 그대로(개발2 시안)
const T0 = 8 * 60, T1 = 20 * 60;                     // 선의 가로 — 08:00 ~ 20:00(서버가 쌓는 5분봉 범위)
const PRE_END = '0900', REG_END = '1530';            // 회색 구간 경계 — 프리 끝 · 정규장 끝(서버 셈 경계와 같은 시각)
const W = 260, H = 30;

const $ = (id) => document.getElementById(id);
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const pct = (x) => {
  if (x == null || !Number.isFinite(Number(x))) return '—';
  const t = `${x > 0 ? '+' : ''}${Number(x).toFixed(2)}%`;
  const c = signClass(Number(x), NUM);
  return c ? `<span class="${c}">${t}</span>` : t;
};
const WK = ['일', '월', '화', '수', '목', '금', '토'];
const dayTxt = (d) => { const m = String(d || '').match(/^(\d{4})(\d{2})(\d{2})$/); if (!m) return '—'; const w = WK[new Date(+m[1], +m[2] - 1, +m[3]).getDay()]; return `${m[2]}-${m[3]}(${w})`; };
const todayYmd = () => { const d = new Date(); return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`; };

// ── 하위 탭 ─────────────────────────────────────────────
const btns = [...document.querySelectorAll('.st-sub-b')];
const panes = [...document.querySelectorAll('.st-tab')];
let loaded = false;
function showTab(t) {
  btns.forEach((b) => { const on = b.dataset.tab === t; b.classList.toggle('is-on', on); b.setAttribute('aria-selected', on ? 'true' : 'false'); });
  panes.forEach((p) => { p.hidden = p.dataset.tab !== t; });
  if (t === 'log' && !loaded) { loaded = true; load(); }
}
btns.forEach((b) => b.addEventListener('click', () => {
  const t = b.dataset.tab;
  history.replaceState(null, '', t === 'log' ? '#log' : location.pathname + location.search);
  showTab(t);
}));

// ── 종목 기록 ───────────────────────────────────────────
const st = { day: null, days: [], data: null, src: '전체', seq: 0 };

const x = (hm) => ((+hm.slice(0, 2) * 60 + +hm.slice(2) - T0) / (T1 - T0)) * W;
function line(r) {
  const L = Array.isArray(r.line) ? r.line.filter((p) => Number.isFinite(Number(p[1]))) : [];
  if (!L.length) return '<span class="st-err">—</span>';
  const ys = L.map((p) => Number(p[1])); if (Number.isFinite(Number(r.prev))) ys.push(Number(r.prev));
  const lo = Math.min(...ys), hi = Math.max(...ys);
  const y = (v) => (H - 2 - ((v - lo) / ((hi - lo) || 1)) * (H - 4)).toFixed(1);
  const pts = L.map((p) => `${x(p[0]).toFixed(1)},${y(Number(p[1]))}`).join(' ');
  const a = x(PRE_END), b = x(REG_END);
  const pv = Number.isFinite(Number(r.prev)) ? `<line class="wl-pv" x1="0" x2="${W}" y1="${y(Number(r.prev))}" y2="${y(Number(r.prev))}"/>` : '';
  return `<svg width="${W}" height="${H}" aria-hidden="true"><rect class="wl-ss" x="0" y="0" width="${a}" height="${H}"/><rect class="wl-ss" x="${b}" y="0" width="${W - b}" height="${H}"/>
    <line class="wl-sl" x1="${a}" x2="${a}" y1="0" y2="${H}"/><line class="wl-sl" x1="${b}" x2="${b}" y1="0" y2="${H}"/>${pv}
    <polyline class="wl-ln ${side(r.pct) || ''}" points="${pts}"/></svg>`;
}

function chips() {
  const d = st.data, c = (d && d.counts) || {};
  const all = d ? d.rows.length : 0;
  const list = [['전체', all], ...SRC.filter((s) => s !== '급등' || c[s]).map((s) => [s, c[s]])];
  $('wl-chips').innerHTML = list.map(([s, n]) => `<button type="button" class="kh-chip${st.src === s ? ' is-active' : ''}" data-src="${esc(s)}" role="tab">${esc(s)} ${n == null ? '—' : n}</button>`).join('');
}
$('wl-chips').addEventListener('click', (e) => { const b = e.target.closest('[data-src]'); if (!b) return; st.src = b.dataset.src; chips(); table(); });

function table() {
  const d = st.data, box = $('wl-box');
  if (!d) return;
  const rows = st.src === '전체' ? d.rows : d.rows.filter((r) => (r.src || []).includes(st.src));
  if (!rows.length) { box.innerHTML = `<div class="st-err">— ${d.rows.length ? `${esc(st.src)} 종목 없음` : '이 날 쌓인 종목 없음'}</div>`; return; }
  box.innerHTML = `<table class="wl-tb"><tr><th class="st-name">종목</th><th>어디서</th><th>전일비</th><th>프리장</th><th>정규장</th><th>애프터</th><th>08:00 · 09:00 │ 15:30 · 20:00</th></tr>${
    rows.map((r) => `<tr><td class="st-name"><b>${esc(r.name || '—')}</b> <small>${esc(r.code)}</small></td><td class="wl-src">${(r.src || []).map((s) => `<span>${esc(s)}</span>`).join('')}</td><td>${pct(r.pct)}</td><td>${pct(r.pre)}</td><td>${pct(r.reg)}</td><td>${pct(r.aft)}</td><td>${line(r)}</td></tr>`).join('')}</table>`;
}

function nav() {
  const i = st.days.indexOf(st.day);
  $('wl-day').textContent = dayTxt(st.day);
  $('wl-prev').disabled = i < 0 || i >= st.days.length - 1;
  $('wl-next').disabled = i <= 0;
}
$('wl-prev').addEventListener('click', () => { const i = st.days.indexOf(st.day); if (i >= 0 && i < st.days.length - 1) load(st.days[i + 1]); });
$('wl-next').addEventListener('click', () => { const i = st.days.indexOf(st.day); if (i > 0) load(st.days[i - 1]); });

async function load(day, fallback = !day) {
  const seq = ++st.seq;
  $('wl-meta').textContent = '값을 받는 중…';
  let d;
  try {
    const res = await fetch(day ? `${API}?day=${day}` : API, { cache: 'no-store' });
    const j = await res.json();
    if (!res.ok || !j.ok || !j.data) throw new Error(j.error || `서버 ${res.status}`);
    d = j.data;
  } catch (e) {
    if (seq !== st.seq) return;
    $('wl-meta').textContent = `— 기록을 못 받음: ${e.message}`;
    $('wl-box').innerHTML = '<div class="st-err">—</div>';
    return;
  }
  if (seq !== st.seq) return;
  d.rows = Array.isArray(d.rows) ? d.rows : [];
  const days = Array.isArray(d.days) ? d.days : [];
  // 오늘 줄이 비었으면 쌓인 가장 최근 날로 — 주말 · 이른 아침에 빈 표가 첫 화면이 되지 않게
  if (fallback && !d.rows.length && days.length && days[0] !== d.day) return load(days[0], false);
  const t = todayYmd();
  st.days = [...new Set([...(days.includes(t) || d.day !== t ? [] : [t]), ...days, d.day])].sort().reverse();
  st.day = d.day; st.data = d;
  if (st.src !== '전체' && !d.rows.some((r) => (r.src || []).includes(st.src))) st.src = '전체';
  $('wl-meta').textContent = d.saved ? `${dayTxt(d.day)} 20:05 쌓은 값 · 종목 ${d.rows.length}` : `${dayTxt(d.day)} 아직 안 쌓임 — 지금 값으로 셈(평일 20:05 에 남김) · 종목 ${d.rows.length}`;
  chips(); nav(); table();
}

showTab(location.hash === '#log' ? 'log' : 'rule');   // 맨 끝 — 기록 상태(st)를 만든 뒤에 연다
