/* ==========================================================================
   「지금 뜨는 산업」 (2026-09-18 지시)

   재권님 말씀 — "지금뜨는 산업안에 통신장비 전기장비 컴퓨터와주변기기 등
   이름을만들고 그걸 누르면 해당 종목이 보이면 될거같은데."

   시안 셋을 보시고 **「나안」** 을 고르셨다 (temp/sector-plan.html) —
   업종 이름이 단추로 한 줄에 놓이고, 고른 것의 종목이 아래에 나온다.

   ── 값은 네이버에서 온다 ──

   KIS 로는 업종 등락률까지만 된다. 이 화면이 보여주는 둘이 KIS 에 없다.

       그 업종에서 몇이 오르고 내렸나   riseCount · fallCount · steadyCount
       그 업종 안의 종목 목록           단추를 눌렀을 때 나오는 것

   테마는 KIS 에 아예 없다. 자세한 것은 server/naver.py 머리글과
   docs/sector-sources.md 에 있다.

   ── 로딩 ──

   첫 화면을 막지 않는다. 목록 한 번(0.03초) + 고른 것의 종목 한 번이고,
   받아 온 것은 들고 있어 단추를 오갈 때 다시 부르지 않는다.
   ========================================================================== */

import { apiFetch } from '../data/api.js';
import { fmtWon, fmtPct, dirClass } from '../utils/format.js';

/* 단추로 내놓을 개수. 카드가 339px 라 여섯이면 한 줄에서 옆으로 밀린다 */
const CHIP_COUNT = 6;
const STOCK_COUNT = 4;          // 본문에 보여줄 종목 수

/* 장중에는 계속 움직인다. 서버도 30초 캐시라 그보다 잦게 불러야 뜻이 없다 */
const REFRESH_MS = 60 * 1000;

export function mountSectors(root) {
  if (!root) return { refresh() {} };

  const kindHost = root.querySelector('#kh-sc-kind');
  const nameHost = root.querySelector('#kh-sc-names');
  const body = root.querySelector('#kh-sc-body');
  const note = root.querySelector('#kh-sc-note');
  if (!nameHost || !body) return { refresh() {} };

  let kind = 'industry';
  let groups = [];
  let pick = null;
  const stockCache = {};        // "industry:294" → 종목 배열

  const key = (k, no) => `${k}:${no}`;

  /* 안내는 본문 머리 오른쪽에 작게 붙는다. 줄을 따로 두면 카드가 길어지고
     같은 줄의 카드 넷이 함께 늘어난다. */
  let noteText = '';
  function setNote(text, cls) {
    noteText = cls ? `<span class="${cls}">${text}</span>` : text;
    if (note) note.innerHTML = noteText;
  }

  /* ── 업종·테마 목록 ── */
  async function loadGroups() {
    setNote('불러오는 중');
    let j = null;
    try {
      const r = await apiFetch(`/api/naver/groups?kind=${kind}`, { cache: 'no-store' });
      if (r && r.ok) j = await r.json();
    } catch { /* 아래에서 없다고 적는다 */ }

    if (!j || !j.ok || !Array.isArray(j.data) || !j.data.length) {
      groups = [];
      nameHost.innerHTML = '';
      body.innerHTML = '<div class="kh-sc-empty kh-mut">불러오지 못했습니다</div>';
      setNote('네이버에서 받지 못했습니다', 'kh-down');
      return;
    }

    groups = j.data;
    const total = (j.meta && j.meta.total) || groups.length;
    setNote(`${kind === 'industry' ? '업종' : '테마'} ${total}개 · 네이버`);

    /* 종류를 바꾸면 고른 것도 새로 잡는다 */
    if (!groups.some(g => g.no === pick)) pick = groups[0].no;
    paintChips();
    loadStocks();
  }

  function paintChips() {
    nameHost.innerHTML = groups.slice(0, CHIP_COUNT).map(g =>
      `<button class="kh-chip${g.no === pick ? ' is-active' : ''}" data-no="${g.no}"
        >${g.name}</button>`).join('');
  }

  /* ── 고른 묶음의 종목 ── */
  async function loadStocks() {
    const g = groups.find(x => x.no === pick);
    if (!g) return;

    const cached = stockCache[key(kind, pick)];
    paintBody(g, cached || null);
    if (cached) return;

    let rows = null;
    try {
      const r = await apiFetch(`/api/naver/stocks?kind=${kind}&no=${pick}`, { cache: 'no-store' });
      if (r && r.ok) {
        const j = await r.json();
        if (j && j.ok && Array.isArray(j.data)) rows = j.data;
      }
    } catch { /* 아래에서 없다고 적는다 */ }

    if (rows) stockCache[key(kind, pick)] = rows;
    /* 받는 사이에 다른 단추를 눌렀으면 그쪽이 이긴다 */
    if (g.no === pick) paintBody(g, rows);
  }

  function paintBody(g, rows) {
    const total = (g.rise + g.steady + g.fall) || 1;
    const pcCls = dirClass(g.pct);
    const head =
      `<div class="kh-sc-head">
         <b>${g.name}</b>
         <b class="${pcCls}">${fmtPct(g.pct)}</b>
         <span class="kh-sc-bar" title="상승 ${g.rise} · 보합 ${g.steady} · 하락 ${g.fall}">
           <i class="up" style="width:${g.rise / total * 100}%"></i>
           <i class="fl" style="width:${g.steady / total * 100}%"></i>
           <i class="dn" style="width:${g.fall / total * 100}%"></i>
         </span>
         <span class="kh-sc-cnt"><b class="kh-up">${g.rise}</b>/<b class="kh-down">${g.fall}</b></span>
       </div>
       <div class="kh-sc-sub">상승률 TOP<span class="kh-sc-src">${noteText}</span></div>`;

    if (!rows) {
      body.innerHTML = head + '<div class="kh-sc-empty kh-mut">불러오는 중</div>';
      return;
    }
    if (!rows.length) {
      body.innerHTML = head + '<div class="kh-sc-empty kh-mut">종목이 없습니다</div>';
      return;
    }

    body.innerHTML = head + rows.slice(0, STOCK_COUNT).map(s =>
      `<a class="kh-sc-st" href="./stock.html?code=${s.code}">
         <b>${s.name}</b>
         <span class="kh-num">${fmtWon(s.price)}</span>
         <span class="kh-num ${dirClass(s.pct)}">${fmtPct(s.pct)}</span>
       </a>`).join('');
  }

  /* ── 누르기 ── */
  if (kindHost) {
    kindHost.addEventListener('click', (e) => {
      const b = e.target.closest('[data-kind]');
      if (!b || b.dataset.kind === kind) return;
      kind = b.dataset.kind;
      kindHost.querySelectorAll('[data-kind]').forEach(x =>
        x.classList.toggle('is-active', x === b));
      loadGroups();
    });
  }

  nameHost.addEventListener('click', (e) => {
    const b = e.target.closest('[data-no]');
    if (!b) return;
    const no = Number(b.dataset.no);
    if (no === pick) return;
    pick = no;
    paintChips();
    loadStocks();
  });

  loadGroups();
  setInterval(() => {
    if (document.hidden) return;        // 안 보이는 탭은 쉰다
    for (const k in stockCache) delete stockCache[k];
    loadGroups();
  }, REFRESH_MS);

  return { refresh: loadGroups };
}
