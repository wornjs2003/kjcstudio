/* ==========================================================================
   주식 회고 (review.html) — 구글 캘린더 모양 · 월 · 주 · 일 (2026-10-07 재권님 「응 이대로 해줘」)

   매매 하나 = 띠 하나(종목 아이콘 + 이름 · 매수 빨강 / 매도 파랑). 날짜를 누르면 그날 매매 줄 +
   기록 더하기 + 그날 회고. **예시 데이터는 없다** — 적은 것만 보인다(holdings/CLAUDE.md 「데이터 규칙」).

   ── 저장 ──
   문서 하나 `/api/board/doc/stock-review` (docstore — 저장마다 직전 것을 남긴다 · 저장소 git 에는 안 올라감).
   주소 · 모아 보내기 · 409 합치기 · 「이 브라우저에만」 은 projects/js/board-store.js 의 createBoardStore 가 한다.
   이 파일은 문서 모양과 합치는 법만 갖는다.

       { v: 1,
         trades: [{ id, d: 'YYYYMMDD', code, name, side: 'buy'|'sell', qty, price, why, at }],
         days:   { 'YYYYMMDD': '그날 회고 글' } }

   ── 홀딩스 데이터 ──
   종목 고르기 = /api/dart/universe(코스피 200 · 코스닥 150) + 관심종목 · 그날 종가 = /api/kis/chart 일봉 close
   (가격 칸에 미리 채우기만 한다 — 고칠 수 있다). 휴장일 · 앞날은 종가가 없어 비워 둔다.
   ========================================================================== */

import { iconHtml } from './components/stock-icon.js';
import { brandColor, WATCHLIST } from './data/market.js';
import { apiFetch } from './data/api.js';

const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LS_KEY = 'kh:review:v1';
const DOW = ['일', '월', '화', '수', '목', '금', '토'];
const VIEWS = ['month', 'week', 'day'];

/* 칸이 넘칠 때 보이는 띠 수 — 미정(빨간 칸 「몇 줄까지」). 폰은 칸이 좁아 아이콘만 쓴다 */
const MAX_CHIPS = () => (matchMedia('(min-width: 701px)').matches ? 3 : 2);

/* ── 날짜 ── */
const ymd = (dt) => `${dt.getFullYear()}${String(dt.getMonth() + 1).padStart(2, '0')}${String(dt.getDate()).padStart(2, '0')}`;
const fromYmd = (s) => new Date(Number(s.slice(0, 4)), Number(s.slice(4, 6)) - 1, Number(s.slice(6, 8)));
const addDays = (s, n) => { const d = fromYmd(s); d.setDate(d.getDate() + n); return ymd(d); };
const todayYmd = () => ymd(new Date());
const dayLabel = (s) => { const d = fromYmd(s); return `${d.getMonth() + 1}월 ${d.getDate()}일 (${DOW[d.getDay()]})`; };

/* ── 상태 ── */
let doc = { v: 1, trades: [], days: {} };
let view = 'month';
let pick = todayYmd();          // 고른 날
let side = 'buy';               // 기록 칸의 매수/매도
let stocks = [];                // [{ code, name }]

/* 보는 상태(보기 · 고른 날)는 사람마다 다르다 — 브라우저에만 둔다 */
try {
  const s = JSON.parse(sessionStorage.getItem('kh:review:view') || '{}');
  if (VIEWS.includes(s.view)) view = s.view;
  if (/^\d{8}$/.test(s.pick || '')) pick = s.pick;
} catch { /* 없으면 오늘 · 월 */ }
const keepView = () => { try { sessionStorage.setItem('kh:review:view', JSON.stringify({ view, pick })); } catch { /* 못 남겨도 화면은 돈다 */ } };

/* ── 저장 층 ── */
const clone = (x) => JSON.parse(JSON.stringify(x));
function normalize(d) {
  const o = d && typeof d === 'object' ? d : {};
  return { v: 1, trades: Array.isArray(o.trades) ? o.trades : [], days: o.days && typeof o.days === 'object' ? o.days : {} };
}

/* 셋(그때 · 내 것 · 서버 것)으로 합친다 — 매매는 id 단위, 회고는 날짜 단위.
   한쪽만 바꿨으면 그쪽을 쓰고, 같은 자리를 둘 다 다르게 바꿨으면 충돌로 낸다 */
function merge(base, mine, theirs) {
  base = normalize(base); mine = normalize(mine); theirs = normalize(theirs);
  const conflicts = [];
  const same = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
  const pick3 = (b, m, t, label) => {
    if (same(m, t)) return m;
    if (same(b, m)) return t;
    if (same(b, t)) return m;
    conflicts.push(label);
    return m;
  };
  const byId = (arr) => Object.fromEntries(arr.map((x) => [x.id, x]));
  const B = byId(base.trades), M = byId(mine.trades), T = byId(theirs.trades);
  const ids = [...new Set([...Object.keys(M), ...Object.keys(T), ...Object.keys(B)])];
  const trades = ids.map((id) => pick3(B[id], M[id], T[id], `매매 ${(M[id] || T[id] || B[id]).name || id}`)).filter(Boolean);
  const keys = [...new Set([...Object.keys(mine.days), ...Object.keys(theirs.days), ...Object.keys(base.days)])];
  const days = {};
  keys.forEach((k) => { const v = pick3(base.days[k], mine.days[k], theirs.days[k], `${dayLabel(k)} 회고`); if (v) days[k] = v; });
  return { doc: { v: 1, trades, days }, conflicts };
}

function setStatus(text, cls) {
  const el = $('#rv-status');
  if (!el) return;
  el.textContent = text || '';
  el.className = 'rv-status' + (cls ? ' ' + cls : '');
}

const store = window.createBoardStore({
  name: 'stock-review',
  delay: 800,
  snapshot: () => clone(doc),
  apply: (d) => { doc = normalize(d); paint(); },
  hasData: (d) => !!d && ((d.trades && d.trades.length) || (d.days && Object.keys(d.days).length)),
  empty: { v: 1, trades: [], days: {} },
  hasLocal: () => doc.trades.length > 0 || Object.keys(doc.days).length > 0,
  persistLocal: () => { try { localStorage.setItem(LS_KEY, JSON.stringify(doc)); } catch { /* 가득 찼다 */ } },
  merge,
  decide: (conflicts) => Promise.resolve(window.confirm(
    `다른 곳에서 같은 자리를 고쳤습니다 — ${conflicts.join(' · ')}\n\n` +
    '[확인] 서버 것으로 (이 화면에서 고친 것이 사라집니다)\n[취소] 이 화면 것으로 (서버 쪽 고친 것이 사라집니다)')),
  status: setStatus,
});

/* ── 그리기 ── */
const tradesOn = (d) => doc.trades.filter((t) => t.d === d);
const stockOf = (t) => ({ code: t.code, name: t.name, brand: brandColor(t.code, t.name) });
const chip = (t) => `<span class="rv-chip ${t.side === 'sell' ? 'sell' : 'buy'}" title="${esc(t.name)} ${t.side === 'sell' ? '매도' : '매수'}">${iconHtml(stockOf(t))}<span>${esc(t.name)}</span></span>`;
const won = (n) => (Number.isFinite(n) ? n.toLocaleString('ko-KR') + '원' : '—');

function monthCells(anchor) {
  const a = fromYmd(anchor);
  const first = new Date(a.getFullYear(), a.getMonth(), 1);
  const last = new Date(a.getFullYear(), a.getMonth() + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < first.getDay(); i++) cells.push(null);
  for (let d = 1; d <= last; d++) cells.push(ymd(new Date(a.getFullYear(), a.getMonth(), d)));
  while (cells.length % 7) cells.push(null);
  return cells;
}

function paintMonth() {
  const today = todayYmd(), max = MAX_CHIPS();
  const head = `<div class="rv-dow">${DOW.map((w, i) => `<div class="${i === 0 ? 'sun' : i === 6 ? 'sat' : ''}">${w}</div>`).join('')}</div>`;
  const grid = monthCells(pick).map((d) => {
    if (!d) return '<div class="rv-cell is-out"></div>';
    const list = tradesOn(d);
    return `<div class="rv-cell${d === pick ? ' is-pick' : ''}" data-day="${d}">
      <span class="rv-d${d === today ? ' is-today' : ''}">${Number(d.slice(6))}</span>
      ${list.slice(0, max).map(chip).join('')}
      ${list.length > max ? `<span class="rv-more">+${list.length - max}</span>` : ''}</div>`;
  }).join('');
  return head + `<div class="rv-grid">${grid}</div>`;
}

function weekDays() {
  const d = fromYmd(pick);
  const start = addDays(pick, -d.getDay());
  return Array.from({ length: 7 }, (_, i) => addDays(start, i));
}

function paintWeek() {
  const today = todayYmd();
  return `<div class="rv-week">${weekDays().map((d, i) => {
    const list = tradesOn(d);
    return `<div class="rv-wd${d === pick ? ' is-pick' : ''}" data-day="${d}">
      <div class="rv-wd-h"><span class="${i === 0 ? 'sun' : i === 6 ? 'sat' : ''}">${DOW[i]}</span><b class="rv-d${d === today ? ' is-today' : ''}">${Number(d.slice(6))}</b></div>
      <div class="rv-wd-b">${list.map(chip).join('') || '<span class="rv-none">매매 없음</span>'}</div></div>`;
  }).join('')}</div>`;
}

function paintDay() {
  const list = tradesOn(pick);
  const rows = list.length ? list.map((t) => `<div class="rv-rowwrap">
      <div class="rv-row">
        ${iconHtml(stockOf(t))}
        <a class="rv-nm" href="./stock.html?code=${esc(t.code)}">${esc(t.name)}</a>
        <span class="rv-side ${t.side === 'sell' ? 'sell' : 'buy'}">${t.side === 'sell' ? '매도' : '매수'}</span>
        <span class="rv-q">${Number(t.qty || 0).toLocaleString('ko-KR')}주</span>
        <span class="rv-p">${t.price == null || t.price === '' ? '—' : won(Number(t.price))}</span>
        <button class="rv-del" type="button" data-del="${esc(t.id)}" title="지우기" aria-label="지우기">✕</button>
      </div>
      ${t.why ? `<div class="rv-why">${esc(t.why)}</div>` : ''}</div>`).join('')
    : '<div class="rv-empty">이날 적은 매매가 없습니다</div>';

  return `<div class="rv-day-h"><b>${dayLabel(pick)}</b></div>
    ${rows}
    <form class="rv-form" id="rv-form" autocomplete="off">
      <input class="full" id="rv-stock" list="rv-stocks" placeholder="종목 이름 또는 코드" required />
      <div class="rv-sidebtn full">
        <button type="button" class="buy${side === 'buy' ? ' is-on' : ''}" data-side="buy">매수</button>
        <button type="button" class="sell${side === 'sell' ? ' is-on' : ''}" data-side="sell">매도</button>
      </div>
      <input id="rv-qty" type="number" min="0" step="1" inputmode="numeric" placeholder="수량(주)" required />
      <input id="rv-price" type="number" min="0" step="1" inputmode="numeric" placeholder="가격(원)" />
      <span class="rv-hint" id="rv-hint">종목을 고르면 그날 종가를 가격 칸에 미리 넣습니다 — 고칠 수 있습니다</span>
      <input class="full" id="rv-why" placeholder="왜 샀나 · 왜 팔았나 (한 줄)" />
      <button class="rv-go" type="submit">기록 더하기</button>
    </form>
    <div class="rv-memo-h">그날 회고</div>
    <textarea class="rv-memo" id="rv-memo" placeholder="잘한 것 · 아쉬운 것 · 다음엔 어떻게">${esc(doc.days[pick] || '')}</textarea>`;
}

function paintTitle() {
  const d = fromYmd(pick);
  let t;
  if (view === 'month') t = `${d.getFullYear()}년 ${d.getMonth() + 1}월`;
  else if (view === 'week') { const w = weekDays(); const a = fromYmd(w[0]), b = fromYmd(w[6]); t = `${a.getMonth() + 1}월 ${a.getDate()}일 – ${b.getMonth() + 1 === a.getMonth() + 1 ? '' : (b.getMonth() + 1) + '월 '}${b.getDate()}일`; }
  else t = dayLabel(pick);
  $('#rv-title').textContent = t;
  document.querySelectorAll('#rv-seg [data-view]').forEach((b) => b.classList.toggle('is-on', b.dataset.view === view));
}

function paint() {
  paintTitle();
  $('#rv-cal').innerHTML = view === 'month' ? paintMonth() : view === 'week' ? paintWeek() : '';
  $('#rv-day').innerHTML = paintDay();
  bindDay();
}

/* ── 그날 칸 손잡이 ── */
function findStock(text) {
  const q = String(text || '').trim();
  if (!q) return null;
  return stocks.find((s) => s.code === q) || stocks.find((s) => s.name === q)
    || stocks.find((s) => `${s.name} (${s.code})` === q) || null;
}

/* 그날 종가 — 일봉에서 그 날짜 봉을 찾는다. 오래된 날이면 더 많이 받는다 */
const closeCache = {};
async function closeOn(code, d) {
  const key = code + d;
  if (key in closeCache) return closeCache[key];
  const days = Math.ceil((Date.now() - fromYmd(d).getTime()) / 86400000);
  if (days < 0) return (closeCache[key] = null);                 // 앞날
  const limit = Math.min(500, Math.max(20, Math.ceil(days * 0.75) + 10));
  try {
    const r = await apiFetch(`/api/kis/chart?code=${code}&period=D&limit=${limit}`, { cache: 'no-store' });
    const j = r ? await r.json() : null;
    const bar = ((j && j.data && j.data.candles) || []).find((b) => String(b.ts).slice(0, 8) === d);
    return (closeCache[key] = bar ? bar.close : null);
  } catch { return null; }
}

function bindDay() {
  const form = $('#rv-form');
  if (!form) return;
  form.querySelectorAll('[data-side]').forEach((b) => b.addEventListener('click', () => {
    side = b.dataset.side;
    form.querySelectorAll('[data-side]').forEach((x) => x.classList.toggle('is-on', x === b));
  }));
  const stockIn = $('#rv-stock'), priceIn = $('#rv-price'), hint = $('#rv-hint');
  stockIn.addEventListener('change', async () => {
    const s = findStock(stockIn.value);
    if (!s) { hint.textContent = '목록에 없는 종목입니다 — 이름이나 6자리 코드로 적어 주십시오'; return; }
    hint.textContent = `${s.name} — 그날 종가 받는 중`;
    const c = await closeOn(s.code, pick);
    if (Number.isFinite(c)) {
      if (!priceIn.value) priceIn.value = c;
      hint.textContent = `${s.name} — 그날 종가 ${won(c)}을 넣었습니다(고칠 수 있습니다)`;
    } else {
      hint.textContent = `${s.name} — 이날 종가가 없습니다(휴장 · 앞날) · 가격을 적어 주십시오`;
    }
  });
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const raw = stockIn.value.trim();
    const s = findStock(raw) || (/^\d{6}$/.test(raw) ? { code: raw, name: raw } : null);
    if (!s) { hint.textContent = '종목을 목록에서 고르거나 6자리 코드로 적어 주십시오'; return; }
    const qty = Number($('#rv-qty').value);
    if (!(qty > 0)) { hint.textContent = '수량을 적어 주십시오'; return; }
    const price = priceIn.value === '' ? null : Number(priceIn.value);
    doc.trades.push({
      id: `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
      d: pick, code: s.code, name: s.name, side, qty, price,
      why: $('#rv-why').value.trim(), at: new Date().toISOString(),
    });
    store.save();
    paint();
  });
  $('#rv-day').querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', () => {
    const t = doc.trades.find((x) => x.id === b.dataset.del);
    if (!t || !window.confirm(`${t.name} ${t.side === 'sell' ? '매도' : '매수'} 기록을 지울까요?`)) return;
    doc.trades = doc.trades.filter((x) => x.id !== t.id);
    store.save();
    paint();
  }));
  const memo = $('#rv-memo');
  let memoTimer = null;
  memo.addEventListener('input', () => {
    clearTimeout(memoTimer);
    memoTimer = setTimeout(() => {
      const v = memo.value.trim();
      if (v) doc.days[pick] = memo.value; else delete doc.days[pick];
      store.save();
      if (view !== 'day') $('#rv-cal').innerHTML = view === 'month' ? paintMonth() : paintWeek();
    }, 500);
  });
}

/* ── 머리줄 · 달력 손잡이(한 번만) ── */
function move(dir) {
  if (view === 'month') { const d = fromYmd(pick); pick = ymd(new Date(d.getFullYear(), d.getMonth() + dir, 1)); }
  else pick = addDays(pick, view === 'week' ? 7 * dir : dir);
  keepView(); paint();
}
document.querySelectorAll('[data-move]').forEach((b) => b.addEventListener('click', () => move(Number(b.dataset.move))));
$('#rv-today').addEventListener('click', () => { pick = todayYmd(); keepView(); paint(); });
$('#rv-seg').addEventListener('click', (e) => {
  const b = e.target.closest('[data-view]');
  if (!b || b.dataset.view === view) return;
  view = b.dataset.view; keepView(); paint();
});
$('#rv-cal').addEventListener('click', (e) => {
  const c = e.target.closest('[data-day]');
  if (!c) return;
  pick = c.dataset.day; keepView(); paint();
  /* 폰은 그날 칸이 달력 아래라 눌러도 안 보일 수 있다 — 그 칸으로 내린다 */
  if (!matchMedia('(min-width: 701px)').matches) $('#rv-day').scrollIntoView({ behavior: 'smooth', block: 'start' });
});
addEventListener('resize', () => { if (view === 'month') $('#rv-cal').innerHTML = paintMonth(); });

/* ── 시작 ── */
try { const kept = JSON.parse(localStorage.getItem(LS_KEY) || 'null'); if (kept) doc = normalize(kept); } catch { /* 처음 */ }
paint();
store.load();

(async () => {
  const seen = new Set();
  const add = (code, name) => { if (code && name && !seen.has(code)) { seen.add(code); stocks.push({ code, name }); } };
  WATCHLIST.forEach((s) => add(s.code, s.name));
  try {
    const r = await apiFetch('/api/dart/universe', { cache: 'no-store' });
    const j = r ? await r.json() : null;
    ((j && j.data) || []).forEach((x) => add(x.code, x.name));
  } catch { /* 관심종목만으로 간다 */ }
  $('#rv-stocks').innerHTML = stocks.map((s) => `<option value="${esc(s.name)}">${esc(s.code)}</option>`).join('');
})();
