/* ==========================================================================
   주식 회고 (review.html) — 구글 캘린더 모양 · 월 · 주 · 일 (2026-10-07 재권님 「응 이대로 해줘」)

   매매 하나 = 띠 하나(종목 아이콘 + 이름 · 시세차익 + 빨강 / − 파랑 — 2026-10-26). 날짜를 누르면 그날 매매 줄 +
   기록 더하기 + 그날 회고. **예시 데이터는 없다** — 적은 것만 보인다(holdings/CLAUDE.md 「데이터 규칙」).

   ── 저장 ──
   문서 하나 `/api/board/doc/stock-review` (docstore — 저장마다 직전 것을 남긴다 · 저장소 git 에는 안 올라감).
   주소 · 모아 보내기 · 409 합치기 · 「이 브라우저에만」 은 projects/js/board-store.js 의 createBoardStore 가 한다.
   이 파일은 문서 모양과 합치는 법만 갖는다.

       { v: 1,
         trades: [{ id, d: 'YYYYMMDD', code, name, pnl, pct, why, at }],     pnl 시세차익(원) · pct 퍼센트 — 빈 칸은 null
                                                                            (2026-10-26 전 기록은 side · qty · price 를 그대로 갖는다)
         days:   { 'YYYYMMDD': '그날 회고 글' } }

   ── 홀딩스 데이터 ──
   종목 고르기 = /api/dart/universe(코스피 200 · 코스닥 150) + 관심종목. (그날 종가를 가격 칸에 미리 넣던 것은 2026-10-26 가격 칸과 함께 뺐다)
   ========================================================================== */

import { iconHtml } from './components/stock-icon.js';
import { brandColor, WATCHLIST } from './data/market.js';
import { apiFetch } from './data/api.js';
import { side as dirOf, signClass } from '../../assets/js/sign.js';

const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LS_KEY = 'kh:review:v1';
const DOW = ['일', '월', '화', '수', '목', '금', '토'];
const VIEWS = ['month', 'week', 'day'];

/* 칸이 넘칠 때 보이는 띠 수 — 좁은 폭 2 · 넓은 화면 3 뒤 「+N」(2026-10-26 재권님 「응」 — 정하실 자리 ②). 폰은 칸이 좁아 아이콘만 쓴다 */
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
let stocks = [];                // [{ code, name }]
let editId = null;              // 다시 불러 고치는 매매 id — 없으면 새 기록 (2026-10-26 「다 작성하지 않아도 저장되도록」)

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
/* 종목을 안 적고 저장한 기록도 있다(2026-10-26) — 이름 자리에 그것을 적는다 */
const nameOf = (t) => t.name || '종목 안 적음';
/* 띠 · 줄 색은 시세차익(없으면 퍼센트)의 부호 — 오름 빨강 · 내림 파랑 · 0 · 빈 칸은 색 없음(assets/js/sign.js 한 셈 ·
   2026-10-26 재권님 「매수 매도 는 필요없고 시세차익금과 퍼센트만」). 옛 기록의 매수 · 매도는 색에 안 쓴다 */
const pnlOf = (t) => (t.pnl != null && t.pnl !== '' ? t.pnl : t.pct);
/* 띠에 차익을 짧게 — 「이름 +12.3만」(2026-10-26 재권님 「응」 — 정하실 자리 ①). 차익이 없으면 퍼센트 · 둘 다 없으면 이름만.
   좁은 폭 월 칸은 아이콘만 보인다(글자 칸을 CSS 가 감춘다) — 색으로 +/− */
const short = (n) => {
  const a = Math.abs(n), f = (x) => x.toLocaleString('ko-KR', { maximumFractionDigits: 1 });
  return plus(n) + (n < 0 ? '−' : '') + (a >= 1e8 ? f(a / 1e8) + '억' : a >= 1e4 ? f(a / 1e4) + '만' : f(a) + '원');
};
const chipAmt = (t) => (Number.isFinite(+t.pnl) && t.pnl !== null && t.pnl !== '' ? short(+t.pnl)
  : Number.isFinite(+t.pct) && t.pct !== null && t.pct !== '' ? pctS(t.pct) : '');
const chip = (t) => `<span class="rv-chip ${dirOf(pnlOf(t)) || 'none'}" title="${esc(nameOf(t))}${t.pnl != null ? ' ' + esc(wonS(t.pnl)) : ''}">${iconHtml(stockOf(t))}<span>${esc(nameOf(t))}${chipAmt(t) ? ` <b class="rv-amt">${chipAmt(t)}</b>` : ''}</span></span>`;
const won = (n) => (Number.isFinite(n) ? n.toLocaleString('ko-KR') + '원' : '—');
const plus = (n) => (n > 0 ? '+' : '');
const wonS = (n) => (n == null || n === '' || !Number.isFinite(+n) ? '—' : plus(+n) + (+n).toLocaleString('ko-KR') + '원');
const pctS = (n) => (n == null || n === '' || !Number.isFinite(+n) ? '—' : plus(+n) + (+n).toLocaleString('ko-KR', { maximumFractionDigits: 2 }) + '%');

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

/* 종목 이름은 홈 모달 주소(`./?code=`)로 간다 — 회고 화면에는 종목 모달이 없어 홈으로 넘어가 그 종목 모달이 열린다
   (2026-10-16 · `components/news-list.js` moveRowHtml 과 같은 까닭). 코드가 없는 기록(목록 밖 이름 · 안 적음)은 글자만.
   **줄을 누르면 그 기록을 아래 칸에 다시 불러 이어 쓴다**(2026-10-26 — 빈 칸을 남기고 저장하게 됐으니 나중에 채울 길) */
function paintDay() {
  const list = tradesOn(pick);
  const ed = editId ? doc.trades.find((x) => x.id === editId && x.d === pick) : null;
  if (!ed) editId = null;
  const val = (k) => esc(ed && ed[k] != null ? ed[k] : '');
  const rows = list.length ? list.map((t) => `<div class="rv-rowwrap${t.id === editId ? ' is-edit' : ''}" data-edit="${esc(t.id)}" title="눌러서 이어 쓰기">
      <div class="rv-row">
        ${iconHtml(stockOf(t))}
        ${t.code ? `<a class="rv-nm" href="./?code=${esc(t.code)}">${esc(nameOf(t))}</a>` : `<span class="rv-nm">${esc(nameOf(t))}</span>`}
        <span class="rv-p ${signClass(t.pnl)}">${wonS(t.pnl)}</span>
        <span class="rv-q ${signClass(t.pct)}">${pctS(t.pct)}</span>
        <button class="rv-del" type="button" data-del="${esc(t.id)}" title="지우기" aria-label="지우기">✕</button>
      </div>
      ${t.why ? `<div class="rv-why">${esc(t.why)}</div>` : ''}
      ${t.qty != null || t.price != null ? `<div class="rv-why">옛 기록 — ${t.side === 'sell' ? '매도' : '매수'}${t.qty != null ? ' · ' + Number(t.qty).toLocaleString('ko-KR') + '주' : ''}${t.price != null ? ' · ' + won(Number(t.price)) : ''}</div>` : ''}</div>`).join('')
    : '<div class="rv-empty">이날 적은 매매가 없습니다</div>';

  /* 「저장하기」 는 그날 칸 날짜 줄 오른쪽(2026-10-26 「기록더하기는 저장하기로 바꾸고 버튼이 위쪽에」) — 아래 기록 칸을 보낸다 */
  return `<div class="rv-day-h"><b>${dayLabel(pick)}</b><button class="rv-save" type="submit" form="rv-form">저장하기</button></div>
    ${rows}
    <form class="rv-form" id="rv-form" autocomplete="off">
      <input class="full" id="rv-stock" list="rv-stocks" placeholder="종목 이름 또는 코드" value="${ed ? esc(ed.name || ed.code || '') : ''}" />
      <input id="rv-pnl" type="number" step="1" inputmode="numeric" placeholder="시세차익(원) · 손해는 −" value="${val('pnl')}" />
      <input id="rv-pct" type="number" step="0.01" inputmode="decimal" placeholder="퍼센트(%)" value="${val('pct')}" />
      <span class="rv-hint" id="rv-hint">${ed ? `${esc(nameOf(ed))} 기록을 고치는 중 — 위 「저장하기」 · <button type="button" class="rv-new" id="rv-new">새로 적기</button>`
        : '빈 칸이 있어도 위 「저장하기」 로 남습니다 — 줄을 누르면 다시 불러 이어 씁니다'}</span>
      <input class="full" id="rv-why" placeholder="한 줄 — 왜 그랬나" value="${val('why')}" />
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

function bindDay() {
  const form = $('#rv-form');
  if (!form) return;
  const stockIn = $('#rv-stock'), hint = $('#rv-hint');
  /* 저장 — 날짜 줄의 「저장하기」(form="rv-form") · 엔터. **빈 칸이 있어도 남긴다**(2026-10-26 재권님 「다 작성하지 않아도 저장되도록」).
     안 남기는 것은 기록 칸 넷(종목 · 차익 · 퍼센트 · 한 줄)이 다 빈 때 하나다 — 그때는 그날 회고 글만 바로 남긴다.
     목록에 없는 이름은 코드 없이 이름 그대로 둔다 · 빈 차익 · 퍼센트는 null(화면에 —).
     옛 기록의 매수 · 매도 · 수량 · 가격 칸은 지우지 않는다 — 줄 아래 「옛 기록」 으로 보인다 */
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    flushMemo();
    const raw = stockIn.value.trim();
    const pnlRaw = $('#rv-pnl').value, pctRaw = $('#rv-pct').value, why = $('#rv-why').value.trim();
    if (!raw && pnlRaw === '' && pctRaw === '' && !why) {
      if (!editId) {
        hint.textContent = doc.days[pick] ? '매매 칸이 비어 그날 회고 글만 남겼습니다' : '적은 것이 없어 저장할 것이 없습니다';
        return;
      }
    }
    const s = findStock(raw) || (/^\d{6}$/.test(raw) ? { code: raw, name: raw } : { code: '', name: raw });
    const num = (v) => (v === '' || !Number.isFinite(Number(v)) ? null : Number(v));
    const rec = { code: s.code, name: s.name, pnl: num(pnlRaw), pct: num(pctRaw), why };
    const old = editId && doc.trades.find((x) => x.id === editId);
    if (old) Object.assign(old, rec, { at: new Date().toISOString() });
    else doc.trades.push({ id: `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`, d: pick, ...rec, at: new Date().toISOString() });
    editId = null;
    store.save();
    paint();
  });
  const nw = $('#rv-new');
  if (nw) nw.addEventListener('click', () => { editId = null; paint(); });
  $('#rv-day').querySelectorAll('[data-edit]').forEach((w) => w.addEventListener('click', (e) => {
    if (e.target.closest('a, [data-del]')) return;
    const t = doc.trades.find((x) => x.id === w.dataset.edit);
    if (!t) return;
    editId = t.id;
    paint();
  }));
  $('#rv-day').querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', () => {
    const t = doc.trades.find((x) => x.id === b.dataset.del);
    if (!t || !window.confirm(`${nameOf(t)} 기록을 지울까요?`)) return;
    doc.trades = doc.trades.filter((x) => x.id !== t.id);
    if (editId === t.id) editId = null;
    store.save();
    paint();
  }));
  const memo = $('#rv-memo');
  memo.addEventListener('input', () => {
    clearTimeout(memoTimer);
    memoTimer = setTimeout(flushMemo, 500);
  });
}

/* 그날 회고 글 — 쓰는 대로 0.5초 뒤 남기고, 「저장」 을 누르면 그 자리에서 남긴다 */
let memoTimer = null;
function flushMemo() {
  clearTimeout(memoTimer);
  const memo = $('#rv-memo');
  if (!memo) return;
  const now = doc.days[pick] || '';
  const v = memo.value.trim() ? memo.value : '';
  if (v === now) return;
  if (v) doc.days[pick] = v; else delete doc.days[pick];
  store.save();
  if (view !== 'day') $('#rv-cal').innerHTML = view === 'month' ? paintMonth() : paintWeek();
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
