/* ==========================================================================
   뉴스 · 공시 · 주요 일정 모달

   「더보기」 를 누르면 화면을 벗어나지 않고 그 자리에 뜬다
   (holdings/CLAUDE.md 「「자세히」 · 「더보기」 는 모달로 연다」).

   ── 모달 하나에 탭 셋 ──

   `news.html` 이 뉴스 · 공시 · 주요 일정 세 칸을 나란히 갖고 있다.
   모달은 좁으므로 **나란히 두지 않고 탭으로 갈아끼운다.** 어느 탭으로
   열지는 부르는 쪽이 정한다 — 뉴스 「더보기」 는 뉴스로, 주요 일정
   「더보기」 는 일정으로 열려야 **누른 것과 나온 것이 맞는다.**

   ── 모달이 원본이다 ──

   첫 화면 칸은 여기서 몇 줄만 덜어낸 것이다. 그래서 **새 항목이 생기면
   여기에 먼저 넣는다** (holdings/CLAUDE.md). 목록에만 넣으면 눌렀을 때
   빈 자리가 된다.

   ── 여는 쪽이 갖는 것 ──

   그리는 것은 이미 있는 부품을 그대로 쓴다. 여기서 새로 만들지 않는다.

       뉴스    components/news-list.js
       공시    components/disclosures.js   limit 만 크게
       일정    components/schedule.js      limit 0 이면 전부
   ========================================================================== */

import { openModal } from './modal.js';
import { fetchFeed, paintIssues, moveRowHtml } from './news-list.js';
import { mountDisclosures } from './disclosures.js';
import { mountSchedule } from './schedule.js';

/* 모달이 열려 있는 동안만 다시 받는다. 서버 캐시와 같은 주기라
   더 자주 물을 이유가 없다 (server/news.py 의 NEWS_TTL). */
const REFRESH_MS = 180_000;

const TABS = [
  { k: 'news',  label: '뉴스' },
  { k: 'dc',    label: '공시' },
  { k: 'sched', label: '주요 일정' },
];

/**
 * @param {object}   opts
 * @param {string}   [opts.tab]    'news' | 'dc' | 'sched' — 어느 탭으로 열지
 * @param {string[]} [opts.watch]  관심종목 코드. 내 종목 뉴스를 표시하는 데 쓴다
 */
export function openNewsModal({ tab = 'news', watch = null } = {}) {
  let timer = null;

  const { body, close } = openModal({
    label: '뉴스 · 공시 · 주요 일정',
    onClose() { if (timer) clearInterval(timer); timer = null; },
  });

  body.innerHTML = `
    <div class="kh-nwm">
      <div class="kh-nw-seg" id="kh-nwm-seg">
        ${TABS.map(t => `<button type="button" data-k="${t.k}">${t.label}</button>`).join('')}
      </div>
      <div class="kh-nw-list" id="kh-nwm-news"></div>
      <div class="kh-nw-list" id="kh-nwm-dc" hidden></div>
      <div class="kh-nw-list" id="kh-nwm-sched" hidden></div>
    </div>`;

  const seg    = body.querySelector('#kh-nwm-seg');
  const panes  = {
    news:  body.querySelector('#kh-nwm-news'),
    dc:    body.querySelector('#kh-nwm-dc'),
    sched: body.querySelector('#kh-nwm-sched'),
  };

  /* 공시·일정은 mount 하면 스스로 받아 그린다. limit 을 크게 두어
     **모달이 전부를 갖는다** — 첫 화면 칸이 그중 몇 줄만 쓴다. */
  mountDisclosures(panes.dc, { limit: 200, showName: true });
  mountSchedule(panes.sched, { compact: false, limit: 0, watch });

  const watchSet = watch ? new Set(watch) : null;

  async function drawNews() {
    const feed = await fetchFeed();
    if (feed === null) { paintIssues(panes.news, null); return; }
    const issues = feed.issues || [];
    const moves  = feed.moves  || [];
    /* 종목이 붙은 뉴스를 위에 둔다 — 내 종목이 섞여 있어 먼저 보게 된다. */
    const head = moves.length
      ? `<div class="kh-nw-sub-h">종목 뉴스</div>` +
        moves.map(x => moveRowHtml(x, watchSet)).join('') +
        `<div class="kh-nw-sub-h">시장 이슈</div>`
      : '';
    if (!issues.length && !moves.length) { paintIssues(panes.news, []); return; }
    panes.news.innerHTML = head;
    const box = document.createElement('div');
    paintIssues(box, issues);
    panes.news.append(...box.childNodes);
  }

  function show(k) {
    for (const t of TABS) {
      panes[t.k].hidden = (t.k !== k);
      const b = seg.querySelector(`[data-k="${t.k}"]`);
      if (b) b.classList.toggle('is-on', t.k === k);
    }
  }

  seg.addEventListener('click', (e) => {
    const b = e.target.closest('[data-k]');
    if (b) show(b.dataset.k);
  });

  show(TABS.some(t => t.k === tab) ? tab : 'news');
  drawNews();
  timer = setInterval(() => { if (!document.hidden) drawNews(); }, REFRESH_MS);

  return { close };
}

/**
 * `data-modal` 이 붙은 링크를 모달로 돌린다.
 *
 * 룰이 `href` 를 지우지 말라고 한다 (holdings/CLAUDE.md, 2026-09-21) —
 * `<a href="./news.html" data-modal="news">더보기</a>`. 그래야 새 탭 ·
 * 가운데 클릭 · JS 가 안 뜰 때가 **그대로 그 화면으로** 간다.
 *
 * 요소마다 따로 건다. `document` 하나에 걸면 다른 모달(데일리)과
 * 같은 자리를 다투게 된다 — `daily-view.js` 의 `bindDailyMenu` 와 같은 꼴이다.
 *
 * @param {ParentNode} root
 * @param {object}     [opts]
 * @param {string[]}   [opts.watch]  관심종목 코드
 */
export function bindNewsModal(root = document, { watch = null } = {}) {
  for (const a of root.querySelectorAll('[data-modal="news"], [data-modal="dc"], [data-modal="sched"]')) {
    /* 자기 화면이면 누를 일이 없다. 눌러도 같은 것이 두 겹이 된다 */
    if (a.classList.contains('is-on')) continue;
    if (a.dataset.nwBound) continue;          /* 두 번 걸지 않는다 */
    a.dataset.nwBound = '1';

    a.addEventListener('click', (e) => {
      /* 새 탭·새 창으로 여는 것은 건드리지 않는다. 그 사람은 화면을 원한 것이다. */
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      openNewsModal({ tab: a.dataset.modal, watch });
    });
  }
}
