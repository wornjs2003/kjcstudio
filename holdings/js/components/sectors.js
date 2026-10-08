/* ==========================================================================
   「지금 뜨는 산업」 (2026-09-18 지시)

   재권님 말씀 — "지금뜨는 산업안에 통신장비 전기장비 컴퓨터와주변기기 등
   이름을만들고 그걸 누르면 해당 종목이 보이면 될거같은데."

   **2026-09-22 에 다시 바뀌었다.** 재권님 말씀 —

       지금뜨는 산업 하나에 다 들어있어서 잘 보여지지가 않는데
       **가로 너비는 2/3이면 될거같아** · 국내 태극기 미국 미국국기 넣어주고
       **차트 폭이랑 맞춰줘** 그옆에 데일리 분석 들어가면 칸이 딱 맞을거같아
       **3위까지만 봐도 댐**

   그래서 **업종 이름 칩 줄을 없애고 1·2·3위를 나란히** 놓는다. 카드는
   `grid-column: span 3` 으로 817px 이 되어 위 줄 차트(818)와 폭이 같다.

   **4위 아래로 가는 길은 「자세히 ›」 모달이다** — 거기에는 스무 묶음이
   다 있다 (`components/sector-modal.js`).

   옛 모양은 시안 셋 중 「나안」 이었다 (temp/sector-plan.html) — 업종 이름이
   단추로 한 줄에 놓이고 고른 것의 종목이 아래에 나오는 것.

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
import { fmtPriceOf, fmtPct, dirClass } from '../utils/format.js';
import { everyServerMs } from '../store/timing.js';
import { patchRows } from '../utils/reconcile.js';

/* **1·2·3위를 나란히 놓는다** (2026-09-22 지시 — 「지금뜨는 산업 하나에
   다 들어있어서 잘 보여지지가 않는데」 · 「3위까지만 봐도 댐」).
   업종 이름 칩 줄은 없앴다 — 4위 아래는 「자세히 ›」 모달에 스무 개가 다 있다. */
const TOP_GROUPS = 3;
/* **받아 온 것을 다 그린다** (2026-09-22 지시 — 「뜨는산업들 목록이 3개만
   보이는데 해당섹터나 업종에 관련된거 더 볼수있어야 할거같아 스크롤창
   넣어서 더 볼수있또록 해줘」).

   전에는 셋만 잘랐다. 네이버가 묶음마다 **열**을 주므로 그대로 내놓고,
   **칸 안에서 굴러가게** 한다 — 카드 높이는 안 바뀐다. */
const STOCK_COUNT = 0;          // 0 이면 자르지 않는다

/* **서버가 정한다** (2026-09-30). `kis_proxy` 의 `SECTOR_TTL` 을 따른다.
   ⚠️ 여기 주석이 **「서버도 30초 캐시」 로 낡아 있었다** — 실제 `SECTOR_TTL` 은
   60 이다. **주석이 값을 들고 있으면 이렇게 갈린다**, 그래서 서버에 묻는다.
   아래는 서버가 없을 때의 대체값이다 (`store/timing.js` 참고) */
const REFRESH_KEY = 'kis_proxy.SECTOR_TTL';
const REFRESH_FALLBACK_MS = 60 * 1000;

/* ── 기간 칩 (2026-09-23) ──────────────────────────────────────
 *
 * 재권님 지시 — 「**가로 해줘 만들거야**」. 카드에만 있던 이 셋을 모달에도
 * 둔다(모달 검수 ⑥). 룰이 「화면에 있는데 모달에 없으면 위반」 이다
 * (holdings/CLAUDE.md:332).
 *
 * **미국은 셋 다 눌린다 · 국내는 일간만** (2026-10-08). `/api/naver/groups` 가 기간을
 * 안 받아 국내 주간·월간은 아직 `disabled` 다 — 아래 `SPAN_READY`.
 *
 * ⚠️ **「받을 수 없는 것은 자리도 만들지 않는다」 가 여기 안 걸린다.**
 * 그 룰은 **어디서도 못 받는 것**을 두고 한 말이고, 이것은 **재권님이
 * 만드실 예정**인 자리다. 「영영 못 받는다」 로 읽어 지우면 안 된다 —
 * 2026-09-23 에 세션 둘이 그렇게 읽었다가 갈렸다.
 *
 * **여기 한 곳에 둔다.** 전에는 `index.html` 에 단추 셋이 박혀 있었다.
 * 모달에 같은 것을 또 적으면 복제가 둘이 되고, **서버에 기간이 붙는 날
 * 한쪽만 살아난다.** 카드도 이 목록으로 그린다.
 */
export const SPANS = [
  { id: 'd', label: '일간' },
  { id: 'w', label: '주간' },
  { id: 'm', label: '월간' },
];

/* **시장마다 받을 수 있는 기간이 다르다** (2026-10-08 지시 — 「미국클릭이 안되고 주간 월간도 안되는데」).
 * 미국은 섹터 ETF 일봉으로 셋 다 낸다(서버 `us_sectors.py`). 국내 주간·월간은 받는 방법을 고르는 중이라
 * 아직 빨간 칩이다 — 정해지면 여기 `kr` 에 더한다. */
const SPAN_READY = { kr: ['d'], us: ['d', 'w', 'm'] };

const SPAN_NOT_READY = '네이버가 기간을 안 줍니다 — 국내 주간·월간은 받는 방법을 정하는 중입니다';

/** 기간 칩 줄의 속을 만든다. 카드와 모달이 같은 것을 쓴다.
 *  @param {string} cur  지금 고른 기간
 *  @param {string} mkt  'kr' · 'us' — 시장마다 눌리는 기간이 다르다 */
export function spanChipsHtml(cur = 'd', mkt = 'kr') {
  const ready = SPAN_READY[mkt] || ['d'];
  return SPANS.map((s) => {
    const ok = ready.includes(s.id);
    return `<button class="kh-chip${s.id === cur ? ' is-active' : ''}${
      ok ? '' : ' kh-todo-chip'}" data-span="${s.id}"${
      ok ? '' : ` disabled title="${SPAN_NOT_READY}"`}>${s.label}</button>`;
  }).join('');
}

/** 시장 · 기간에 맞는 주소 — 카드와 모달(스냅숏)이 같은 것을 쓴다 */
export function groupsUrl(mkt, kind, span) {
  return mkt === 'us' ? `/api/kis/us-sectors?span=${span}` : `/api/naver/groups?kind=${kind}`;
}
export function stocksUrl(mkt, kind, no, span) {
  return mkt === 'us' ? `/api/kis/us-sector-stocks?no=${no}&span=${span}`
    : `/api/naver/stocks?kind=${kind}&no=${no}`;
}
/** 출처 한 낱말 (2026-10-06 재권님 「가로 해」 — 개수는 모달에) */
export const sourceOf = (mkt) => (mkt === 'us' ? 'State Street · KIS' : '네이버');

export function mountSectors(root) {
  if (!root) return { refresh() {} };

  const kindHost = root.querySelector('#kh-sc-kind');
  const body = root.querySelector('#kh-sc-body');
  const note = root.querySelector('#kh-sc-note');
  if (!body) return { refresh() {} };

  /* 기간 칩을 `SPANS` 로 그린다 (2026-09-23) — 전에는 `index.html` 에 박혀
     있었다. 모달도 같은 목록으로 그리므로 둘이 갈리지 않는다. */
  const spanHost = root.querySelector('#kh-sc-span');
  const mktHost = root.querySelector('#kh-sc-mkt');

  let mkt = 'kr';               // 'kr' · 'us' (2026-10-08)
  let span = 'd';
  let kind = 'industry';
  if (spanHost) spanHost.innerHTML = spanChipsHtml(span, mkt);
  let groups = [];
  /* **고른 하나가 아니라 위 셋을 다 그린다** (2026-09-22). `pick` 은
     모달이 「어느 것부터 보여줄지」 에 쓰므로 1위로 둔다. */
  let pick = null;
  let seq = 0;                  // 늦게 온 응답이 새 갈래를 덮지 않게
  let lastTotal = 0;            // 전체 묶음 수 (받은 것은 그중 일부다)
  let lastAt = null;            // 마지막으로 받은 시각 — 모달이 적는다
  const stockCache = {};        // "industry:294" → 종목 배열

  /* 시장 · 기간이 갈리면 같은 묶음 번호라도 다른 값이다 */
  const key = (k, no, m = mkt, sp = span) => `${m}:${sp}:${k}:${no}`;

  /* 안내는 본문 머리 오른쪽에 작게 붙는다. 줄을 따로 두면 카드가 길어지고
     같은 줄의 카드 넷이 함께 늘어난다. */
  let noteText = '';
  function setNote(text, cls) {
    noteText = cls ? `<span class="${cls}">${text}</span>` : text;
    if (note) note.innerHTML = noteText;
  }

  /* ── 업종·테마 목록 ── */
  let gseq = 0;                 // 시장 · 기간 · 종류를 빨리 바꾸면 늦게 온 목록이 새것을 덮는다
  async function loadGroups(force = false) {
    const mine = ++gseq;
    setNote('불러오는 중');
    let j = null;
    try {
      const r = await apiFetch(groupsUrl(mkt, kind, span), { cache: 'no-store' });
      if (r && r.ok) j = await r.json();
    } catch { /* 아래에서 없다고 적는다 */ }
    if (mine !== gseq) return;

    if (!j || !j.ok || !Array.isArray(j.data) || !j.data.length) {
      groups = [];
      body.innerHTML = '<div class="kh-sc-empty kh-mut">불러오지 못했습니다</div>';
      setNote(`${sourceOf(mkt)}에서 받지 못했습니다`, 'kh-down');
      return;
    }

    groups = j.data;
    lastAt = new Date();
    const total = (j.meta && j.meta.total) || groups.length;
    lastTotal = total;
    setNote(sourceOf(mkt));   // 출처만 — 개수는 모달이 적는다 (2026-10-06 재권님 「가로 해」)

    pick = groups[0].no;          // 모달이 이것부터 보여준다
    paintBody();
    loadTop(force);
  }

  /** 위 셋의 종목을 **한꺼번에** 받는다. 받아 둔 것은 다시 안 부른다.
   *  `force` 면 받아 둔 것이 있어도 다시 받는다 — **다만 지우지 않는다.**
   *  지우면 응답이 오기까지 그 칸이 「불러오는 중」 이 되고, 그 사이 칸이
   *  새로 만들어져 **굴려 둔 자리가 맨 위로 돌아간다** (2026-10-02). */
  async function loadTop(force = false) {
    const top = groups.slice(0, TOP_GROUPS);
    const mine = ++seq;
    await Promise.all(top.map(async (g) => {
      if (!force && stockCache[key(kind, g.no)]) return;
      try {
        const r = await apiFetch(stocksUrl(mkt, kind, g.no, span), { cache: 'no-store' });
        if (r && r.ok) {
          const j = await r.json();
          if (j && j.ok && Array.isArray(j.data)) stockCache[key(kind, g.no)] = j.data;
        }
      } catch { /* 그 칸만 「불러오지 못했습니다」 가 된다 */ }
    }));
    if (mine !== seq) return;     // 그새 종류가 바뀌었다
    paintBody();
  }

  /* ── 그리기 — 위 셋을 나란히 ── */

  /** 한 칸. 순위 · 이름 · 등락률 · 오름/내림 띠 · 상승률 TOP 셋 */
  function column(g, rank) {
    const sum = (g.rise + g.steady + g.fall) || 1;
    const rows = stockCache[key(kind, g.no)];
    /* **1위에만 불을 붙인다.** 셋 다 붙이면 무엇이 1위인지 안 보인다 */
    const head =
      `<div class="kh-sc-ch">
         ${rank === 1 ? '<span class="kh-sc-fire" aria-hidden="true">🔥</span>' : ''}
         <b class="kh-sc-rk">${rank}위</b>
         <span class="kh-sc-nm" title="${g.name}">${g.name}</span>
         <b class="kh-sc-pc ${dirClass(g.pct)}">${fmtPct(g.pct)}</b>
       </div>
       <span class="kh-sc-bar" title="상승 ${g.rise} · 보합 ${g.steady} · 하락 ${g.fall}">
         <i class="up" style="width:${g.rise / sum * 100}%"></i>
         <i class="fl" style="width:${g.steady / sum * 100}%"></i>
         <i class="dn" style="width:${g.fall / sum * 100}%"></i>
       </span>
       <div class="kh-sc-cnt">
         <b class="kh-up">상승 ${g.rise}</b>
         <span class="kh-mut">보합 ${g.steady}</span>
         <b class="kh-down">하락 ${g.fall}</b>
       </div>
       <div class="kh-sc-lb">상승률 TOP</div>`;

    if (!rows) return head + '<div class="kh-sc-empty kh-mut">불러오는 중</div>';
    if (!rows.length) return head + '<div class="kh-sc-empty kh-mut">종목이 없습니다</div>';

    /* **목록만 굴러간다.** 머리(이름 · 띠 · 상승/보합/하락 · 「상승률 TOP」)는
       붙어 있어야 어느 묶음을 보고 있는지 안 사라진다. */
    const list = (STOCK_COUNT ? rows.slice(0, STOCK_COUNT) : rows).map(stockRowHtml).join('');
    return head + `<div class="kh-sc-list">${list}</div>`;
  }

  /** 종목 한 줄. **처음 그릴 때와 새로 들어온 종목에 같은 것을 쓴다** —
   *  두 곳에 적으면 한쪽만 고쳐져 줄 모양이 갈린다 */
  function stockRowHtml(st) {
    return `<a class="kh-sc-st" data-code="${st.code}" href="./stock.html?code=${st.code}">
         <span class="kh-sc-stn" title="${st.name}">${st.name}</span>
         <span class="kh-sc-stp">
           <b class="kh-num">${fmtPriceOf(st.code, st.price)}</b>
           <i class="kh-num ${dirClass(st.pct)}">${fmtPct(st.pct)}</i>
         </span>
       </a>`;
  }

  /* ── 그려진 것을 고친다 — 다시 만들지 않는다 (2026-10-02) ──
   *
   * `body.innerHTML` 로 갈아끼우면 `.kh-sc-list` 가 **새 노드**가 된다.
   * 그 칸은 `overflow-y: auto` 라(`css/home.css`) **굴려 둔 자리가 맨 위로
   * 돌아간다** — 갱신마다 그러면 읽던 자리를 빼앗는다. 값만 바뀌는 갱신에서는
   * 자리를 그대로 두고 **글자·폭만 고친다.**
   *
   * **모양이 바뀌는 자리는 고치지 않는다** — 묶음 순서가 바뀌었거나
   * 「불러오는 중」 ↔ 목록처럼 칸의 짜임이 달라지면 그때만 다시 만든다.
   * 그것은 값이 아니라 **내용이 바뀐 것**이라 자리가 돌아가도 맞다. */

  /** 고칠 수 있으면 고치고 `true`. 못 고치면 아무것도 안 하고 `false` */
  function patchBody(top) {
    const cols = body.querySelectorAll('.kh-sc-col');
    if (cols.length !== top.length) return false;
    for (let i = 0; i < top.length; i++) {
      if (cols[i].dataset.no !== String(top[i].no)) return false;
      if (!canPatchCol(cols[i], top[i])) return false;
    }
    top.forEach((g, i) => patchCol(cols[i], g, i + 1));
    return true;
  }

  /** 짜임이 그대로인가 — 고치기 전에 **전부** 본다. 한 칸이라도 아니면
   *  손대지 않고 다시 만든다 (반쯤 고친 상태를 남기지 않는다).
   *
   *  **줄 순서나 종목이 바뀌는 것은 「짜임이 달라진 것」 이 아니다** (2026-10-02).
   *  이 목록은 **상승률 TOP** 이라 갱신마다 순서가 바뀌고 들락날락한다 —
   *  2026-10-02 실측에서 **한 바퀴 만에 세 칸 다 바뀌었다.** 그것까지 「못
   *  고친다」 로 보면 **고치는 길이 사실상 안 쓰인다**(처음 쓴 것이 그 꼴이었다).
   *  굴러가는 칸(`.kh-sc-list`)만 그대로 두면 자리는 지켜지므로, 줄은
   *  **코드로 맞춰 옮겨 쓴다.** */
  function canPatchCol(col, g) {
    const rows = stockCache[key(kind, g.no)];
    const list = col.querySelector('.kh-sc-list');
    if (!rows) return !list;                 // 아직 안 온 칸끼리
    if (!rows.length) return false;          // 「종목이 없습니다」 는 다시 만든다
    return !!list;
  }

  function patchCol(col, g, rank) {
    const set = (sel, text) => {
      const el = col.querySelector(sel);
      if (el && el.textContent !== text) el.textContent = text;
    };
    set('.kh-sc-rk', `${rank}위`);
    const nm = col.querySelector('.kh-sc-nm');
    if (nm && nm.textContent !== g.name) { nm.textContent = g.name; nm.title = g.name; }
    const pc = col.querySelector('.kh-sc-pc');
    if (pc) {
      const t = fmtPct(g.pct);
      if (pc.textContent !== t) pc.textContent = t;
      const cls = `kh-sc-pc ${dirClass(g.pct)}`;
      if (pc.className !== cls) pc.className = cls;
    }

    const sum = (g.rise + g.steady + g.fall) || 1;
    const bar = col.querySelector('.kh-sc-bar');
    if (bar) {
      const title = `상승 ${g.rise} · 보합 ${g.steady} · 하락 ${g.fall}`;
      if (bar.title !== title) bar.title = title;
      const w = (sel, v) => {
        const el = bar.querySelector(sel);
        const t = `${v / sum * 100}%`;
        if (el && el.style.width !== t) el.style.width = t;
      };
      w('i.up', g.rise); w('i.fl', g.steady); w('i.dn', g.fall);
    }
    set('.kh-sc-cnt .kh-up', `상승 ${g.rise}`);
    set('.kh-sc-cnt .kh-mut', `보합 ${g.steady}`);
    set('.kh-sc-cnt .kh-down', `하락 ${g.fall}`);

    const rows = stockCache[key(kind, g.no)];
    if (!rows) return;                       // 머리만 고친다
    patchList(col.querySelector('.kh-sc-list'),
              STOCK_COUNT ? rows.slice(0, STOCK_COUNT) : rows);
  }

  /** 종목 줄을 **코드로 맞춰** 고친다. 있던 줄은 옮겨 쓰고, 새로 든 것만
   *  만들고, 빠진 것만 지운다 — **굴러가는 칸은 그대로 남는다**.
   *  뉴스·공시와 같은 공용(`utils/reconcile.js`)을 쓴다 — 복제를 두지 않는다 */
  function patchList(list, want) {
    patchRows(list, want, {
      key: (st) => st.code, attr: 'code', html: stockRowHtml, patch: patchRow,
    });
  }

  function patchRow(a, st) {
    const n = a.querySelector('.kh-sc-stn');
    if (n && n.textContent !== st.name) { n.textContent = st.name; n.title = st.name; }
    const price = a.querySelector('.kh-sc-stp b');
    const pt = fmtPriceOf(st.code, st.price);
    if (price && price.textContent !== pt) price.textContent = pt;
    const ip = a.querySelector('.kh-sc-stp i');
    if (ip) {
      const t = fmtPct(st.pct);
      if (ip.textContent !== t) ip.textContent = t;
      const cls = `kh-num ${dirClass(st.pct)}`;
      if (ip.className !== cls) ip.className = cls;
    }
    const href = `./stock.html?code=${st.code}`;
    if (a.getAttribute('href') !== href) a.setAttribute('href', href);
  }

  function paintBody() {
    if (!groups.length) {
      body.innerHTML = '<div class="kh-sc-empty kh-mut">불러오는 중</div>';
      return;
    }
    const top = groups.slice(0, TOP_GROUPS);
    if (patchBody(top)) return;
    /* **세로줄은 칸 사이에만** 넣는다 (2026-09-22 시안 — 「줄로 해달라」).
       테두리 상자가 아니라 한 줄이다. */
    body.innerHTML = top.map((g, i) =>
      (i ? '<i class="kh-sc-vr" aria-hidden="true"></i>' : '')
      + `<div class="kh-sc-col" data-no="${g.no}">${column(g, i + 1)}</div>`).join('');
  }

  /* ── 누르기 ── */

  /** 미국은 업종(섹터)만 있다 — 테마 칩을 끈다 */
  function syncKindChips() {
    if (!kindHost) return;
    kindHost.querySelectorAll('[data-kind]').forEach((x) => {
      const off = mkt === 'us' && x.dataset.kind !== 'industry';
      x.disabled = off;
      x.title = off ? '미국은 업종(섹터 ETF)만 있습니다' : '';
      x.classList.toggle('is-active', x.dataset.kind === kind);
    });
  }

  /* 시장 칩 (2026-10-08) — 국내 ↔ 미국. 기간이 그 시장에 없으면 일간으로 돌린다 */
  if (mktHost) {
    mktHost.addEventListener('click', (e) => {
      const b = e.target.closest('[data-mkt]');
      if (!b || b.disabled || b.dataset.mkt === mkt) return;
      mkt = b.dataset.mkt;
      mktHost.querySelectorAll('[data-mkt]').forEach(x =>
        x.classList.toggle('is-active', x === b));
      if (mkt === 'us') kind = 'industry';
      if (!(SPAN_READY[mkt] || []).includes(span)) span = 'd';
      if (spanHost) spanHost.innerHTML = spanChipsHtml(span, mkt);
      syncKindChips();
      groups = [];
      paintBody();
      loadGroups();
    });
  }

  /* 기간 칩 (2026-10-08) — 눌리지 않는 칩은 `disabled` 라 클릭이 안 온다 */
  if (spanHost) {
    spanHost.addEventListener('click', (e) => {
      const b = e.target.closest('[data-span]');
      if (!b || b.disabled || b.dataset.span === span) return;
      span = b.dataset.span;
      spanHost.querySelectorAll('[data-span]').forEach(x =>
        x.classList.toggle('is-active', x === b));
      loadGroups();
    });
  }

  if (kindHost) {
    kindHost.addEventListener('click', (e) => {
      const b = e.target.closest('[data-kind]');
      if (!b || b.disabled || b.dataset.kind === kind) return;
      kind = b.dataset.kind;
      kindHost.querySelectorAll('[data-kind]').forEach(x =>
        x.classList.toggle('is-active', x === b));
      loadGroups();
    });
  }

  loadGroups();
  /* `everyServerMs` 가 `document.hidden` 을 함께 본다 */
  everyServerMs(REFRESH_KEY, REFRESH_FALLBACK_MS, () => loadGroups(true));

  /* **모달에 넘겨줄 것** (2026-09-22 지시 — 「지금 뜨는 산업도 모달로」).

     모달이 따로 받지 않는다. 같은 화면에서 두 번 받으면 **두 자리의 숫자가
     어긋나고** 네이버를 겹쳐 부른다 — 종목 모달이 첫 화면 시세 루프에
     얹혀 있는 것과 같은 생각이다 (holdings/CLAUDE.md 「최적화는 멈춘다가
     아니라 늦춘다다」).

     카드는 여섯 칩·네 종목만 보여주지만 **받아 온 것은 스무 묶음이고
     종목도 열**이다. 모달은 그것을 다 쓴다. */
  function snapshot() {
    return {
      kind, mkt, span, groups, pick, total: lastTotal, at: lastAt,
      stocks: stockCache[key(kind, pick)] || null,
      /* 모달에서 다른 묶음을 골랐을 때 쓰라고 함께 넘긴다.
         받아 둔 것이 있으면 그것을, 없으면 이쪽이 받아 캐시에 넣는다. */
      /* 시장은 스냅숏을 뜬 때의 것이다 — 모달은 시장을 안 바꾼다. 기간은 모달이 바꿀 수 있다 */
      async pickGroup(k, no, sp = span) {
        const m = mkt;
        const c = stockCache[key(k, no, m, sp)];
        if (c) return c;
        try {
          const r = await apiFetch(stocksUrl(m, k, no, sp), { cache: 'no-store' });
          if (r && r.ok) {
            const j = await r.json();
            if (j && j.ok && Array.isArray(j.data)) {
              stockCache[key(k, no, m, sp)] = j.data;
              return j.data;
            }
          }
        } catch { /* 모달이 「불러오지 못했습니다」 를 적는다 */ }
        return null;
      },
      /* 모달이 종류를 바꿨을 때 목록을 받아 온다. 카드는 안 건드린다 —
         모달에서 테마를 보다 닫았는데 카드가 테마로 바뀌어 있으면
         무엇을 눌러 그렇게 됐는지 알 수 없다 (실시간 순위 모달과 같다). */
      async listGroups(k, sp = span) {
        if (k === kind && sp === span && groups.length) return { rows: groups, total: lastTotal };
        try {
          const r = await apiFetch(groupsUrl(mkt, k, sp), { cache: 'no-store' });
          if (r && r.ok) {
            const j = await r.json();
            if (j && j.ok && Array.isArray(j.data)) {
              return { rows: j.data, total: (j.meta && j.meta.total) || j.data.length };
            }
          }
        } catch { /* 아래에서 없다고 적는다 */ }
        return null;
      },
    };
  }

  return { refresh: loadGroups, snapshot };
}
