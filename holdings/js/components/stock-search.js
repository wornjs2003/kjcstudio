/* ==========================================================================
   종목 검색칸 — 갈래 줄 오른쪽 끝 (2026-10-06 지시 — 「홈 오른쪽 맨 옆에 내기록 이걸
   검색창으로 해주고 종목 검색 가능하도록해줘」 · 「답대기는 6번까지 순서대로」)

   이름 일부나 코드를 치면 서버 `/api/dart/search` 가 후보를 준다. 서버가 읽는 것은 이미
   있는 표 둘뿐이다(순위 목록 · OpenDART 상장사 대응표) — 무엇을 찾고 무엇을 못 찾는지는
   `server/dart.py` 의 `search` 주석에 있다. 여기 다시 적지 않는다.

   고르면 `onPick(code, name)`. 안 넘기면 종목 화면(`stock.html?code=`)으로 간다.
   첫 화면은 순위표 줄과 같은 길(큰 차트 · 패널이 그 종목)을 넘긴다 — 산업 칸과 같은 룰이다.

   **후보 목록은 `body` 에 붙인다.** 갈래 줄은 좁은 화면에서 `overflow-x: auto` 라 그 안에
   두면 목록이 잘린다. 열 때마다 검색칸 자리를 재서 그 아래에 띄운다.
   ========================================================================== */

import { apiFetch } from '../data/api.js';

const WAIT_MS = 150;          // 치기를 멈추고 이만큼 뒤에 묻는다 — 글자마다 묻지 않게

/* ── 최근 고른 종목 (2026-10-14 지시 — 「검색을 누르면 최근 검색종목 5개 기억되게 하고 밑으로 나열되어서
   보여지게도 해줘. 코스피끼리야. 코스피 코스닥 나스닥 등등 각각 5개씩 기억되도록 해줘」 · 「응」) ──
   칸이 비어 있을 때 누르면 시장별로 묶어 최근 것부터 보인다. 고를 때마다 그 시장 맨 앞에 넣고 같은 종목은
   한 번만 둔다. 이 부품을 쓰는 검색칸(홈 갈래 줄 · 데일리 · 뉴스 · 종목 모달)이 **한 기억**을 함께 쓴다.
   이 브라우저에만 남는다(localStorage — 보는 사람의 편의라 서버에 두지 않는다 · 기기마다 따로).
   시장은 검색 결과의 `market` 그대로다 — 순위 목록 밖 종목은 서버가 시장을 안 줘 「그 밖」 으로 간다.
   나스닥 묶음은 검색이 미국 종목을 찾게 되면 채워진다(지금 검색은 국내만 — 아직 안 만든 것) */
const RECENT_KEY = 'kh:stock-search:recent';
const RECENT_N = 5;
const MARKET_NAME = { KOSPI: '코스피', KOSDAQ: '코스닥', NASDAQ: '나스닥', NYSE: '뉴욕', AMEX: '아멕스', ETC: '그 밖' };
const MARKET_ORDER = ['KOSPI', 'KOSDAQ', 'NASDAQ', 'NYSE', 'AMEX'];
const mktOf = (r) => (r && r.market) || 'ETC';
const mktRank = (m) => m === 'ETC' ? 999 : (MARKET_ORDER.indexOf(m) + 1 || 100);

function loadRecent() {
  try {
    const v = JSON.parse(localStorage.getItem(RECENT_KEY) || '{}');
    return v && typeof v === 'object' ? v : {};
  } catch { return {}; }       // 사생활 보호 창 · 깨진 값
}

function rememberPick(r) {
  if (!r || !r.code) return;
  const all = loadRecent();
  const m = mktOf(r);
  for (const k of Object.keys(all)) all[k] = (all[k] || []).filter(x => x.code !== r.code);  // 시장이 바뀌어 온 것도 한 번만
  all[m] = [{ code: r.code, name: r.name || r.code, market: r.market || null }, ...(all[m] || [])].slice(0, RECENT_N);
  for (const k of Object.keys(all)) if (!all[k].length) delete all[k];
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(all)); } catch { /* 사생활 보호 창 */ }
}

/** 시장 순서대로 펼친 목록 — 각 줄에 묶음 이름을 단다 */
function recentRows() {
  const all = loadRecent();
  return Object.keys(all).sort((a, b) => mktRank(a) - mktRank(b) || a.localeCompare(b))
    .flatMap(m => (all[m] || []).slice(0, RECENT_N).map(x => ({ ...x, grp: m })));
}

export function mountStockSearch(host, { onPick } = {}) {
  if (!host) return null;

  const box = document.createElement('div');
  box.className = 'kh-cat-search';
  box.innerHTML = `
    <button type="button" class="kh-cs-btn" aria-label="종목 검색 열기">⌕</button>
    <input type="search" class="kh-cs-in" placeholder="종목 이름 · 코드" autocomplete="off"
           spellcheck="false" aria-label="종목 검색" aria-autocomplete="list" aria-expanded="false">`;
  host.replaceWith(box);

  const input = box.querySelector('.kh-cs-in');
  const btn = box.querySelector('.kh-cs-btn');
  const list = document.createElement('ul');
  list.className = 'kh-cs-list';
  list.hidden = true;
  list.setAttribute('role', 'listbox');
  document.body.appendChild(list);

  let rows = [];
  let at = -1;
  let recentMode = false;     // 지금 목록이 최근 고른 것인가(검색 결과가 아니라)
  let timer = null;
  let seq = 0;

  const go = onPick || ((code) => { location.href = `./stock.html?code=${code}`; });

  function place() {
    const r = input.getBoundingClientRect();
    list.style.top = `${Math.round(r.bottom + 4)}px`;
    /* 칸 오른쪽 끝에 맞춘다 — 목록이 칸보다 넓어도 화면 밖으로 안 나가게 */
    const w = Math.max(r.width, 260);
    list.style.left = `${Math.round(Math.max(8, Math.min(r.right - w, window.innerWidth - w - 8)))}px`;
    list.style.width = `${Math.round(w)}px`;
  }

  function close() {
    list.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    at = -1;
  }

  function paint(note) {
    if (!rows.length) {
      list.innerHTML = `<li class="kh-cs-none kh-mut">${note || '찾는 종목이 없습니다'}</li>`;
    } else {
      list.innerHTML = rows.map((r, i) => `${recentMode && (i === 0 || rows[i - 1].grp !== r.grp)
          ? `<li class="kh-cs-grp kh-mut" role="presentation">최근 · ${MARKET_NAME[r.grp] || esc(r.grp)}</li>` : ''}
        <li role="option" data-i="${i}" class="kh-cs-row${i === at ? ' is-on' : ''}">
          <b class="kh-cs-name">${esc(r.name)}</b>
          <span class="kh-cs-code kh-num">${r.code}</span>
          <span class="kh-cs-mkt kh-mut">${recentMode ? '' : (r.market && MARKET_NAME[r.market]) || ''}</span>
        </li>`).join('');
    }
    place();
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
  }

  /* 칸이 비었을 때 — 최근 고른 것. 하나도 없으면 목록을 안 연다 */
  function showRecent() {
    rows = recentRows();
    recentMode = true;
    at = -1;
    if (rows.length) paint(); else close();
  }

  async function ask(q) {
    const mine = ++seq;
    try {
      const r = await apiFetch(`/api/dart/search?q=${encodeURIComponent(q)}`, { cache: 'no-store' });
      const j = r && r.ok ? await r.json() : null;
      if (mine !== seq) return;                 // 그새 더 쳤다
      recentMode = false;
      rows = (j && j.ok && Array.isArray(j.data)) ? j.data : [];
      at = rows.length ? 0 : -1;
      paint(j && j.ok ? null : '찾지 못했습니다 — 서버에 닿지 않습니다');
    } catch {
      if (mine !== seq) return;
      recentMode = false;
      rows = [];
      paint('찾지 못했습니다 — 서버에 닿지 않습니다');
    }
  }

  function pick(i) {
    const r = rows[i];
    if (!r) return;
    rememberPick(r);
    close();
    input.value = '';
    box.classList.remove('is-open');
    input.blur();
    go(r.code, r.name);
  }

  input.addEventListener('input', () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (!q) { seq++; showRecent(); return; }
    timer = setTimeout(() => ask(q), WAIT_MS);
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!rows.length) return;
      e.preventDefault();
      at = (at + (e.key === 'ArrowDown' ? 1 : -1) + rows.length) % rows.length;
      paint();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (at >= 0) pick(at);
    } else if (e.key === 'Escape') {
      close();
      input.blur();
      box.classList.remove('is-open');
    }
  });
  input.addEventListener('focus', () => {
    if (!input.value.trim()) showRecent();
    else if (rows.length) paint();
  });
  /* 이미 칸에 있는 채로 다시 누르면 focus 가 안 온다 — 닫혀 있으면 같은 것을 연다 */
  input.addEventListener('click', () => {
    if (!list.hidden) return;
    if (!input.value.trim()) showRecent();
    else if (rows.length) paint();
  });
  /* 누르기 전에 칸이 흐려지면(blur) 목록이 먼저 닫혀 고를 수 없다 — mousedown 에서 고른다 */
  list.addEventListener('mousedown', (e) => {
    const li = e.target.closest('li[data-i]');
    if (!li) return;
    e.preventDefault();
    pick(+li.dataset.i);
  });
  document.addEventListener('mousedown', (e) => {
    if (!box.contains(e.target) && !list.contains(e.target)) { close(); box.classList.remove('is-open'); }
  });
  window.addEventListener('resize', () => { if (!list.hidden) place(); });
  window.addEventListener('scroll', () => { if (!list.hidden) place(); }, { passive: true });

  /* 좁은 화면 — 돋보기만 보이다가 누르면 칸이 펼쳐진다(css/home.css) */
  btn.addEventListener('click', () => {
    box.classList.add('is-open');
    input.focus();
  });

  return { input, destroy() { list.remove(); } };
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
