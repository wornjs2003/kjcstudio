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
import { fmtWon, fmtPct, dirClass } from '../utils/format.js';

/* **1·2·3위를 나란히 놓는다** (2026-09-22 지시 — 「지금뜨는 산업 하나에
   다 들어있어서 잘 보여지지가 않는데」 · 「3위까지만 봐도 댐」).
   업종 이름 칩 줄은 없앴다 — 4위 아래는 「자세히 ›」 모달에 스무 개가 다 있다. */
const TOP_GROUPS = 3;
const STOCK_COUNT = 3;          // 한 칸에 보여줄 종목 수

/* 장중에는 계속 움직인다. 서버도 30초 캐시라 그보다 잦게 불러야 뜻이 없다 */
const REFRESH_MS = 60 * 1000;

export function mountSectors(root) {
  if (!root) return { refresh() {} };

  const kindHost = root.querySelector('#kh-sc-kind');
  const body = root.querySelector('#kh-sc-body');
  const note = root.querySelector('#kh-sc-note');
  if (!body) return { refresh() {} };

  let kind = 'industry';
  let groups = [];
  /* **고른 하나가 아니라 위 셋을 다 그린다** (2026-09-22). `pick` 은
     모달이 「어느 것부터 보여줄지」 에 쓰므로 1위로 둔다. */
  let pick = null;
  let seq = 0;                  // 늦게 온 응답이 새 갈래를 덮지 않게
  let lastTotal = 0;            // 전체 묶음 수 (받은 것은 그중 일부다)
  let lastAt = null;            // 마지막으로 받은 시각 — 모달이 적는다
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
      body.innerHTML = '<div class="kh-sc-empty kh-mut">불러오지 못했습니다</div>';
      setNote('네이버에서 받지 못했습니다', 'kh-down');
      return;
    }

    groups = j.data;
    lastAt = new Date();
    const total = (j.meta && j.meta.total) || groups.length;
    lastTotal = total;
    setNote(`${kind === 'industry' ? '업종' : '테마'} ${total}개 · 네이버`);

    pick = groups[0].no;          // 모달이 이것부터 보여준다
    paintBody();
    loadTop();
  }

  /** 위 셋의 종목을 **한꺼번에** 받는다. 받아 둔 것은 다시 안 부른다 */
  async function loadTop() {
    const top = groups.slice(0, TOP_GROUPS);
    const mine = ++seq;
    await Promise.all(top.map(async (g) => {
      if (stockCache[key(kind, g.no)]) return;
      try {
        const r = await apiFetch(`/api/naver/stocks?kind=${kind}&no=${g.no}`, { cache: 'no-store' });
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

    return head + rows.slice(0, STOCK_COUNT).map((st) =>
      `<a class="kh-sc-st" href="./stock.html?code=${st.code}">
         <span class="kh-sc-stn" title="${st.name}">${st.name}</span>
         <span class="kh-sc-stp">
           <b class="kh-num">${fmtWon(st.price)}</b>
           <i class="kh-num ${dirClass(st.pct)}">${fmtPct(st.pct)}</i>
         </span>
       </a>`).join('');
  }

  function paintBody() {
    if (!groups.length) {
      body.innerHTML = '<div class="kh-sc-empty kh-mut">불러오는 중</div>';
      return;
    }
    /* **세로줄은 칸 사이에만** 넣는다 (2026-09-22 시안 — 「줄로 해달라」).
       테두리 상자가 아니라 한 줄이다. */
    body.innerHTML = groups.slice(0, TOP_GROUPS).map((g, i) =>
      (i ? '<i class="kh-sc-vr" aria-hidden="true"></i>' : '')
      + `<div class="kh-sc-col">${column(g, i + 1)}</div>`).join('');
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

  loadGroups();
  setInterval(() => {
    if (document.hidden) return;        // 안 보이는 탭은 쉰다
    for (const k in stockCache) delete stockCache[k];
    loadGroups();
  }, REFRESH_MS);

  /* **모달에 넘겨줄 것** (2026-09-22 지시 — 「지금 뜨는 산업도 모달로」).

     모달이 따로 받지 않는다. 같은 화면에서 두 번 받으면 **두 자리의 숫자가
     어긋나고** 네이버를 겹쳐 부른다 — 종목 모달이 첫 화면 시세 루프에
     얹혀 있는 것과 같은 생각이다 (holdings/CLAUDE.md 「최적화는 멈춘다가
     아니라 늦춘다다」).

     카드는 여섯 칩·네 종목만 보여주지만 **받아 온 것은 스무 묶음이고
     종목도 열**이다. 모달은 그것을 다 쓴다. */
  function snapshot() {
    return {
      kind, groups, pick, total: lastTotal, at: lastAt,
      stocks: stockCache[key(kind, pick)] || null,
      /* 모달에서 다른 묶음을 골랐을 때 쓰라고 함께 넘긴다.
         받아 둔 것이 있으면 그것을, 없으면 이쪽이 받아 캐시에 넣는다. */
      async pickGroup(k, no) {
        const c = stockCache[key(k, no)];
        if (c) return c;
        try {
          const r = await apiFetch(`/api/naver/stocks?kind=${k}&no=${no}`, { cache: 'no-store' });
          if (r && r.ok) {
            const j = await r.json();
            if (j && j.ok && Array.isArray(j.data)) {
              stockCache[key(k, no)] = j.data;
              return j.data;
            }
          }
        } catch { /* 모달이 「불러오지 못했습니다」 를 적는다 */ }
        return null;
      },
      /* 모달이 종류를 바꿨을 때 목록을 받아 온다. 카드는 안 건드린다 —
         모달에서 테마를 보다 닫았는데 카드가 테마로 바뀌어 있으면
         무엇을 눌러 그렇게 됐는지 알 수 없다 (실시간 순위 모달과 같다). */
      async listGroups(k) {
        if (k === kind && groups.length) return { rows: groups, total: lastTotal };
        try {
          const r = await apiFetch(`/api/naver/groups?kind=${k}`, { cache: 'no-store' });
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
