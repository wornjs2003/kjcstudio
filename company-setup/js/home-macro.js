// Insight 홈 — 「오늘의 시황 한 줄」 자리에 세션이 쓴 시황 한 줄, 「오늘의 핵심」 줄에 매크로 지표 칩 (2026-10-14 재권님
// 「매크로 지표를 Insight 홈에 하나로 모아서」 → 시안 → 「홈의 오늘의 핵심 옆에다가 / 그리고 홈에 오늘의 시황한줄 옆에 시황분석한게 있어야」 →
// 「옆으로 밀기로 해줘」). 칩이 넘치면 가로로 민다 — 줄 높이는 그대로(insight.css .in-mac). 종목 리포트에는 안 더한다(창구 (나)).
//   · 값은 시황분석 탭과 같은 파일 · 주소에서 — data/world-macro · naver-macro · external-risk(live.js · 새 값 먼저 · 없으면 씨앗) · js/dxy.js(ICE 달러인덱스)
//   · 시황 글은 data/market-note.json 한 곳(시황분석 탭 맨 위 「세션이 쓴 시황」 과 같은 파일) — 쓴 시각을 함께 보인다
//   · 색 — 달러인덱스 칩 바탕은 tone.js(100 위 빨강 · 아래 파랑 · 멀수록 짙게) · 오르내림 숫자는 글씨만 빨강 · 파랑(num-up · num-dn)
//   · 칩을 누르면 시황분석 탭의 그 그래프로 — 그 칸이 접혀 있으면 열어 둔다(시황분석 탭이 기억하는 열린 칸 목록에 더한다)
//   · 못 받은 값은 「—」
import { live } from './live.js';
import { dxyIce } from './dxy.js';
import { ready as toneReady, paint } from '/assets/js/tone.js';

const FOLD_KEY = 'kjc.market.open';   // 시황분석 탭 market.js 의 접기 기억과 같은 열쇠
const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (x, d) => x == null || !Number.isFinite(+x) ? '—' : (+x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: Math.max(d, 3) });
const ud = (x, t) => x == null || !x ? t : `<span class="${x > 0 ? 'num-up' : 'num-dn'}">${t}</span>`;
const pc = x => x == null ? '' : ' ' + ud(x, `${x > 0 ? '+' : ''}${(+x).toFixed(1)}%`);
const last = a => a && a.length ? a[a.length - 1] : null;
const pair = (a, b, d, u = '') => `미국 ${num(a, d)}${a == null ? '' : u} · 한국 ${num(b, d)}${b == null ? '' : u}`;

async function note() {
  const box = document.querySelector('[data-home-note]');
  if (!box) return;
  let N = null;
  try { N = await (await fetch('data/market-note.json', { cache: 'no-store' })).json(); } catch (e) { /* 아래에서 「—」 */ }
  box.classList.add('in-note');
  box.innerHTML = '<b class="in-note-h">오늘의 시황 한 줄</b>'
    + `<span class="in-note-t" title="${esc(N && N.one)}">${N ? esc(N.one) : '—'}</span>`
    + (N ? `<span class="in-note-at">${esc(N.writtenAt)} 씀</span>` : '')
    + '<a class="in-note-more" href="market.html">자세히 ›</a>';
}

async function macro() {
  const row = document.querySelector('[data-home-macro]');
  if (!row) return;
  const [W, N, E, X] = await Promise.all([live('world-macro').catch(() => null), live('naver-macro').catch(() => null),
    live('external-risk').catch(() => null), dxyIce().catch(() => null), toneReady]);
  const C = (W && W.countries) || {}, us = C.US || {}, kr = C.KR || {}, v = o => o && o.v;
  const krw = N && N.majors && N.majors.find(m => m.code === 'FX_USDKRW'), wti = N && N.energy && N.energy.find(m => m.name === 'WTI');
  const g = E && last(E.gpr), ep = E && last(E.epu), vx = E && last(E.vix);
  // [이름, 값 글, 시황분석 탭의 접는 칸, 그 그래프, 바탕]
  const CH = [
    ['정책금리', pair(v(us.rate), v(kr.rate), 2, '%'), 'macro', 'c-rate'],
    ['국채 10년', pair(v(us.y10), v(kr.y10), 2, '%'), 'macro', 'c-yld'],
    ['물가', pair(v(us.cpi), v(kr.cpi), 1, '%'), 'macro', 'c-cpi'],
    ['경기선행', pair(v(us.cli), v(kr.cli), 1), 'macro', 'c-cli'],
    ['달러인덱스', X ? `${num(X.v, 2)}${X.m1 == null ? '' : ' · 한 달' + pc(X.m1)}` : '—', 'market', 'c-gold', X ? paint('dxy', X.v, 'bg') : ''],
    ['원/달러', krw ? num(krw.v, 1) + pc(krw.pct) : '—', 'macro', 'nv-now'],
    ['WTI', wti ? num(wti.v, 2) + pc(wti.pct) : '—', 'macro', 'c-oil'],
    ['지정학 위험', g && g[2] != null ? `30일 평균 ${num(g[2], 1)}` : '—', 'ext', 'c-gpr'],
    ['정책 불확실성', ep && ep[2] != null ? `30일 평균 ${num(ep[2], 1)}` : '—', 'ext', 'c-unc'],
    ['VIX', vx ? num(vx[1], 2) : '—', 'ext', 'c-fear'],
  ];
  row.classList.add('in-mac');
  row.innerHTML = '<span class="in-mac-h">오늘의 핵심</span>'
    + CH.map(([n, t, fold, id, bg]) => `<a class="in-mac-c" href="market.html#${id}" data-fold="${fold}"${bg ? ` style="background:${bg}"` : ''}><b>${n}</b><span>${t}</span></a>`).join('')
    + '<span class="in-mac-more" aria-hidden="true">›</span>';
  row.addEventListener('click', e => {
    const a = e.target.closest('a.in-mac-c'); if (!a) return;
    try { const o = JSON.parse(localStorage.getItem(FOLD_KEY) || '[]'); if (!o.includes(a.dataset.fold)) localStorage.setItem(FOLD_KEY, JSON.stringify([...o, a.dataset.fold])); }
    catch (err) { /* 저장이 막힌 창 — 접힌 채로 열린다 */ }
  });
  const more = row.querySelector('.in-mac-more');   // 끝까지 밀었거나 다 들어가면 「›」 를 감춘다
  const edge = () => { more.hidden = row.scrollLeft + row.clientWidth >= row.scrollWidth - 2; };
  row.addEventListener('scroll', edge, { passive: true }); addEventListener('resize', edge); edge();
}

note(); macro();
