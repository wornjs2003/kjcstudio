/* 모달 머리 — **세 모달이 같은 것을 쓴다.**
 *
 * 2026-09-22 지시 — "모달창은 이거 참고해서 UI 구성을 통일해줘야 할거같은데
 * 상단에는 모달창의 이름 및 주요 정보들, 탭들이 있고 그 하위에 정보들이
 * 표기되는 방향으로". 기준은 **종목 모달(stock.html 의 `.kh-head`)** 이다.
 *
 *     ① 이름 줄     아이콘 · 이름 · 부제 · 오른쪽 닫기(✕)
 *     ② 주요 정보    왼쪽은 **대표값 하나**, 오른쪽은 **수치 격자**
 *     ③ 탭 줄       무엇을 볼지 고르는 곳. 오른쪽에 한 줄 설명
 *     ─────────
 *       본문        **여기만 굴러간다**
 *
 * ── 왜 파일을 따로 두는가 ──
 *
 * 세 모달(실시간 순위 · 뉴스·공시 · 데일리분석)이 각자 머리를 만들면
 * **그 순간 복제가 셋**이 된다. 「같은 값은 한 곳에만 둔다」 다.
 * `modal.js` 는 「띄우고 닫는 것만」 맡기로 적혀 있어서 그쪽에 넣지 않고
 * 옆에 뒀다 — `openModal({ head })` 로 부르면 이 파일이 그린다.
 *
 * ── 머리가 굴러가지 않는 방법 ──
 *
 * 종목 모달은 머리를 `.kh-modal-scroll` **안에** 두고 `position: sticky` 로
 * 붙여 놨다. 그 길을 안 쓴다 — 표가 있는 모달에서는 표머리(`thead th`)도
 * 붙어야 하고, 그러면 그 `top` 이 **머리 높이만큼** 이어야 한다.
 * 머리 높이는 부제·격자 줄 수에 따라 달라지므로 어딘가에 숫자를 박게 된다.
 *
 * 그래서 머리를 **스크롤 칸 바깥의 형제**로 두고 모달을 세로 flex 로 만든다.
 * 굴러가는 것은 본문뿐이고, `thead th { top: 0 }` 이 그냥 맞는다.
 *
 * ── 붙이고 나서 이 한 줄을 돌려 본다 ──
 *
 *     [...document.querySelectorAll('.kh-modal [hidden]')]
 *       .filter((e) => getComputedStyle(e).display !== 'none' || e.offsetHeight > 0)
 *
 * **비어야 정상이다.** `hidden` 을 붙였는데 `display: flex` 같은 규칙이
 * 이겨서 **안 숨는 일**이 잦다 — 2026-09-22 에 뉴스·공시 탭 칸이 숨은 채
 * 8694px 를 차지하고 있었다. `hasAttribute('hidden')` 만 보면 「숨었다」 로
 * 나오니, **계산된 `display` 와 높이까지** 봐야 갈린다.
 *
 * `modal.css` 의 `.kh-modal [hidden] { display: none !important }` 가
 * 모달 안에서는 막아 주지만, **화면 쪽(모달 아닌 자리)은 각자 봐야 한다.**
 *
 * ── 스크롤바 ──
 *
 * 굵기·화살표는 `assets/css/common.css` 한 곳이 정한다 (6px · 화살표 없음).
 * **여기서 `::-webkit-scrollbar` 를 건드리지 않는다.** 본문이 새 스크롤 칸이
 * 되지만 그 규칙은 문서 전체에 걸려 있어 그대로 물려받는다.
 */

const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

/* 오른쪽 단추(`actions`)는 2026-09-22 에 뺐다 (지시 — "모달칸에 전체화면
   이런게 들어가 있는데 이거 다 빼줘").

   여기서 막으면 **네 모달(실시간 순위 · 데일리 · 뉴스·공시 · 지금 뜨는
   산업)에서 한 번에 사라진다.** 각 모달이 넘기는 `actions:` 는 무시된다 —
   그 줄은 자기 차례에 각자 지운다.

   **닫기(✕)는 남는다.** 그것까지 없어지면 닫을 길이 줄어든다. */

function statHtml(s) {
  /* 값이 안 온 칸은 「—」 로 두지 않고 부르는 쪽이 정한 글자를 그대로 쓴다.
     0 이나 「—」 를 여기서 박으면 「연결이 안 된 것」 과 구분이 안 된다. */
  return `<div class="kh-mh-st"><span>${esc(s.label)}</span
    ><b class="${esc(s.cls || '')}">${s.html || esc(s.value)}</b></div>`;
}

function bigHtml(b) {
  if (!b) return '';
  return `<div class="kh-mh-big-box">
    <div class="kh-mh-big kh-num">${b.html || esc(b.value)}</div>
    ${b.change ? `<div class="kh-mh-big-s ${esc(b.changeCls || '')}">${esc(b.change)}</div>` : ''}
    ${b.note ? `<div class="kh-mh-big-w">${esc(b.note)}</div>` : ''}
  </div>`;
}

/**
 * 머리를 만든다. 붙이는 것은 `modal.js` 가 한다.
 *
 * @param {object} spec
 *   icon      아이콘 칸에 넣을 글자(두 자 정도) 또는 HTML
 *   name      모달 이름. **필수**
 *   sub       이름 옆 작은 글씨 (기준 시각 · 범위 등)
 *   caret     ⌄ 를 붙일지
 *   noClose   ✕ 를 빼려면 true (기본은 붙인다)
 *             ※ `actions` 는 2026-09-22 에 없앴다. 넘겨도 안 그려진다
 *   big       { value|html, change, changeCls, note } — 왼쪽 대표값. 없으면 생략
 *   stats     [{ label, value|html, cls }] — 오른쪽 수치 격자
 *   statCols  격자 열 수 (2 또는 3). 기본 3. **좁은 모달은 2 로 한다** —
 *             850px 에서 3 열이면 눌려 줄바꿈된다 (재서 확인)
 *   tabs      [{ id, label }]
 *   tab       처음 고를 탭 id
 *   tabsNote  탭 줄 오른쪽 한 줄 설명
 *   onTab     탭을 눌렀을 때 (id)
 *   onClose   ✕ 를 눌렀을 때
 *
 * **② 주요 정보가 없는 모달**은 `big` 과 `stats` 를 둘 다 비워 둔다.
 * 그 줄이 아예 안 그려진다 — 억지로 채우지 않는다
 * (holdings/CLAUDE.md 「받을 수 없는 것은 자리도 만들지 않는다」).
 */
export function buildHead(spec = {}) {
  const el = document.createElement('header');
  el.className = 'kh-mh';

  const state = {
    big: spec.big || null,
    stats: spec.stats || [],
    tab: spec.tab || (spec.tabs && spec.tabs[0] && spec.tabs[0].id) || null,
    tabsNote: spec.tabsNote || '',
    sub: spec.sub || '',
  };

  function draw() {
    const hasMain = !!(state.big || (state.stats && state.stats.length));
    const cols = spec.statCols === 2 ? ' is-2' : '';

    el.innerHTML = `
      <div class="kh-mh-top">
        ${spec.icon ? `<span class="kh-mh-ic">${spec.iconHtml ? spec.icon : esc(spec.icon)}</span>` : ''}
        <span class="kh-mh-name">${esc(spec.name)}</span>
        <span class="kh-mh-sub kh-num" data-mh-sub>${esc(state.sub)}</span>
        ${spec.caret ? '<span class="kh-mh-caret">⌄</span>' : ''}
        <span class="kh-mh-act">
          ${spec.noClose ? '' : '<button class="kh-mh-x" type="button" aria-label="닫기">✕</button>'}
        </span>
      </div>

      ${hasMain ? `<div class="kh-mh-main">
        ${bigHtml(state.big)}
        ${state.stats.length
          ? `<div class="kh-mh-stats${cols}">${state.stats.map(statHtml).join('')}</div>` : ''}
      </div>` : ''}

      ${(spec.tabs && spec.tabs.length) ? `<div class="kh-mh-tabs">
        ${spec.tabs.map((t) => `<button class="kh-mh-tab${t.id === state.tab ? ' is-on' : ''}"
          type="button" data-mh-tab="${esc(t.id)}">${esc(t.label)}</button>`).join('')}
        ${state.tabsNote ? `<span class="kh-mh-tabs-r">${esc(state.tabsNote)}</span>` : ''}
      </div>` : ''}`;

    el.querySelectorAll('[data-mh-tab]').forEach((b) => {
      b.addEventListener('click', () => {
        if (b.dataset.mhTab === state.tab) return;
        state.tab = b.dataset.mhTab;
        /* 눌린 표시만 바꾼다 — 머리를 통째로 다시 그리면 본문을 그리는
           쪽에서 잡아 둔 요소가 끊긴다 (지금은 없지만 다음 사람이 붙인다). */
        el.querySelectorAll('[data-mh-tab]').forEach((x) =>
          x.classList.toggle('is-on', x.dataset.mhTab === state.tab));
        if (spec.onTab) spec.onTab(state.tab);
      });
    });

    const x = el.querySelector('.kh-mh-x');
    if (x && spec.onClose) x.addEventListener('click', spec.onClose);
  }

  draw();

  return {
    el,
    /** 지금 고른 탭 */
    tab: () => state.tab,
    /** 대표값을 갈아끼운다. 자리는 그대로다 */
    setBig(big) { state.big = big; draw(); },
    /** 수치 격자를 갈아끼운다 */
    setStats(stats) { state.stats = stats || []; draw(); },
    /** 이름 옆 작은 글씨 (기준 시각 등) — 자주 바뀌므로 통째로 안 그린다 */
    setSub(sub) {
      state.sub = sub == null ? '' : sub;
      const s = el.querySelector('[data-mh-sub]');
      if (s) s.textContent = state.sub;
    },
    setTabsNote(note) { state.tabsNote = note || ''; draw(); },
    setTab(id) {
      state.tab = id;
      el.querySelectorAll('[data-mh-tab]').forEach((x) =>
        x.classList.toggle('is-on', x.dataset.mhTab === id));
    },
  };
}
