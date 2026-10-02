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
import { fetchFeed, lastFeed, paintIssues, paintLoading, moveRowHtml, rowHtml } from './news-list.js';
import { patchRows } from '../utils/reconcile.js';
import { mountDisclosures } from './disclosures.js';
import { mountSchedule, collectSchedule, AHEAD_DAYS } from './schedule.js';
import { apiFetch } from '../data/api.js';
import { everyServerMs } from '../store/timing.js';

/* 모달이 열려 있는 동안만 다시 받는다. 서버 캐시와 같은 주기라
   더 자주 물을 이유가 없다 (server/news.py 의 NEWS_TTL). */
/* **서버가 정한다** (2026-10-02 · 서버리소스 화면 묶음 ⑥).
   `news.py` 의 `NEWS_TTL` 을 따른다. 아래는 **서버가 없을 때의 대체값**이다. */
const REFRESH_KEY = 'news.NEWS_TTL';
const REFRESH_FALLBACK_MS = 180_000;

/* **서버가 200 에서 자른다.** `limit` 을 500 · 1000 으로 올려도 200 만 온다
   (2026-09-22 실측). 그래서 이 값은 「우리가 정한 한도」 가 아니라
   **서버 상한**이고, 꽉 찼을 때 화면이 그 사실을 적는다 —
   「200건」 으로만 적으면 정확한 수로 읽힌다. */
const DC_LIMIT = 200;

const TABS = [
  { k: 'news',  label: '뉴스' },
  { k: 'dc',    label: '공시' },
  { k: 'sched', label: '주요 일정' },
];

/* 2026-09-22T12:14:47+09:00 → 12:14 · **어제 것이면 09.21 12:14**
 *
 * 시각만 찍으면 **어제 값이 오늘로 읽힌다.** 세션 서버(`--slow`)는
 * 공시·뉴스 수집을 안 돌려서 하루 넘은 것을 들고 있다 —
 * 2026-09-22 12:17 에 8768 이 「어제 10:47」 을 주고 있었다.
 * 그 상태에서 「10:47 받음」 만 보이면 방금 것으로 보인다. */
function stamp(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return '';
  const p = (n) => String(n).padStart(2, '0');
  const hm = `${p(d.getHours())}:${p(d.getMinutes())}`;
  const sameDay = d.toDateString() === new Date().toDateString();
  return sameDay ? hm : `${p(d.getMonth() + 1)}.${p(d.getDate())} ${hm}`;
}

/* 탭마다 **무엇을 보고 있는지** 한 줄로 적는다. 개수만 보이면 「0건」 이
   고장인지 정말 없는 것인지 갈리지 않는다 — 범위가 함께 보여야 한다. */
function tabNote(k, capped) {
  if (k === 'sched') return `앞으로 ${AHEAD_DAYS}일`;
  if (k === 'dc')    return capped ? `서버가 ${DC_LIMIT}건까지 줍니다` : '받아 둔 전부';
  return '최근 순서';
}

/**
 * @param {object}   opts
 * @param {string}   [opts.tab]    'news' | 'dc' | 'sched' — 어느 탭으로 열지
 * @param {string[]} [opts.watch]  관심종목 코드. 내 종목 뉴스를 표시하는 데 쓴다
 */
export function openNewsModal({ tab = 'news', watch = null } = {}) {
  let timer = null;
  /* 공시가 서버 상한에 걸렸나. 탭 줄 설명이 이것을 보고 갈린다. */
  let dcCapped = false;

  const first = TABS.some(t => t.k === tab) ? tab : 'news';

  /* 머리(이름 줄 · 주요 정보 · 탭 줄)는 `modal-head.js` 가 그린다.
     여기서 만들지 않는다 — 모달 셋이 같은 머리를 써야 해서 한 곳에 뒀다. */
  const m = openModal({
    label: '뉴스 · 공시 · 주요 일정',
    /* 폭을 고정한다. 탭을 바꿀 때 폭이 달라지면 「보는 것을 바꿔도 자리는
       그대로다」 를 깬다 — 탭마다 담는 글자 길이가 다르다. */
    width: 980,
    head: {
      icon: '뉴',
      name: '뉴스 · 공시',
      caret: true,
      /* 「전체 화면 ↗」 단추는 2026-09-22 에 뼈대에서 없어졌다
         (지시 — "모달칸에 전체화면 이런게 들어가 있는데 이거 다 빼줘").
         넘겨도 안 그려지므로 **넘기지 않는다** — 죽은 줄이 남으면
         다음에 읽는 쪽이 「왜 안 나오지」 를 찾게 된다.
         `news.html` 로 가는 길은 메뉴의 `href` 가 그대로 갖고 있다. */
      /* 격자를 둘로 둔다. 큰 값(뉴스)이 왼쪽을 차지하므로 오른쪽은
         공시 · 일정 둘뿐이다. */
      statCols: 2,
      tabs: TABS.map(t => ({ id: t.k, label: t.label })),
      tab: first,
      tabsNote: tabNote(first, false),
      onTab(id) { show(id); head.setTabsNote(tabNote(id, dcCapped)); },
    },
    onClose() { if (timer) timer(); timer = null; },   // everyServerMs 가 준 멈추는 함수
  });

  const body = m.body;
  const head = m.head;

  body.innerHTML = `
    <div class="kh-nwm">
      <div class="kh-nw-list" id="kh-nwm-news"></div>
      <div class="kh-nw-list" id="kh-nwm-dc" hidden></div>
      <div class="kh-nw-list" id="kh-nwm-sched" hidden></div>
    </div>`;

  const panes = {
    news:  body.querySelector('#kh-nwm-news'),
    dc:    body.querySelector('#kh-nwm-dc'),
    sched: body.querySelector('#kh-nwm-sched'),
  };

  /* 공시·일정은 mount 하면 스스로 받아 그린다. limit 을 크게 두어
     **모달이 전부를 갖는다** — 첫 화면 칸이 그중 몇 줄만 쓴다. */
  mountDisclosures(panes.dc, { limit: DC_LIMIT, showName: true });
  mountSchedule(panes.sched, { compact: false, limit: 0, watch });

  const watchSet = watch ? new Set(watch) : null;

  /* **그리기와 받기를 가른다.** 받아 둔 것으로 즉시 그릴 때와 새로 받아
     다시 그릴 때가 같은 함수를 써야 둘이 안 갈린다 (2026-10-01).
     머리에 쓸 것이 있으면 feed 를 그대로 돌려준다 — 못 받았거나 한 건도
     없으면 아무것도 돌려주지 않아 머리를 비워 둔다 (데이터 규칙). */
  function paintNews(feed) {
    if (feed === null) { paintIssues(panes.news, null); return; }
    const issues = feed.issues || [];
    const moves  = feed.moves  || [];
    if (!issues.length && !moves.length) { paintIssues(panes.news, []); return; }
    /* 종목이 붙은 뉴스를 위에 둔다 — 내 종목이 섞여 있어 먼저 보게 된다.
       **머리줄도 이름 붙은 항목으로 넘겨** 한 목록으로 끼워 넣는다 (2026-10-02) —
       통째로 다시 그리면 모달 안에서 굴려 둔 자리가 맨 위로 돌아간다 */
    const items = moves.length
      ? [{ k: 'h:moves', h: `<div class="kh-nw-sub-h">종목 뉴스</div>` },
         ...moves.map(x => ({ k: 'm:' + (x.link || x.title), h: moveRowHtml(x, watchSet) })),
         { k: 'h:issues', h: `<div class="kh-nw-sub-h">시장 이슈</div>` }]
      : [];
    issues.forEach(x => items.push({ k: 'i:' + x.link, h: rowHtml(x) }));
    patchRows(panes.news, items, { key: (it) => it.k, html: (it) => it.h });
    return feed;
  }

  async function drawNews() {
    return paintNews(await fetchFeed());
  }

  /* ── 머리 채우기 ─────────────────────────────
     **셋을 따로 받는다.** 한 곳이 터져도 나머지 칸은 채워진다.
     받기 전에는 그 칸을 만들지 않는다 — 0 이나 「—」 를 먼저 박으면
     「연결이 안 된 것」 과 구분이 안 된다 (데이터 규칙). */

  /* 공시 마지막 수집 시각. **머리 두 곳이 함께 쓴다** — 격자 아래 「… 기준」
     과 큰 숫자의 안내줄. 가르면서 한 곳에 뒀다 (CLAUDE.md 「같은 값은 한
     곳에만 둔다」). */
  let polledAt = '';
  /* 큰 숫자에 마지막으로 쓴 feed. 공시 시각이 뒤늦게 오면 다시 맞춘다. */
  let bigFeed = null;

  /* 큰 숫자 — **뉴스가 와야 그릴 수 있다.** 그래서 격자와 갈라 두었다. */
  function paintBig(feed) {
    if (!feed) return;
    bigFeed = feed;
    const issues = (feed.issues || []).length;
    const moves  = (feed.moves  || []).length;
    head.setBig({
      value: String(issues + moves),
      change: `시장 이슈 ${issues} · 종목 뉴스 ${moves}`,
      changeCls: 'kh-mut',
      note: polledAt ? `경제지 RSS · OpenDART ${stamp(polledAt)} 받음` : '경제지 RSS · OpenDART',
    });
  }

  /* 격자 · 탭 줄 — **뉴스와 상관없다.** 전에는 `paintHead(feed)` 하나라
     뉴스를 기다렸는데, 공시·일정은 0.03초에 오는데도 **뉴스 때문에 1초를
     기다렸다** (2026-10-01 실측). 가르면 각자 오는 대로 찬다. */
  async function paintStats() {
    const stats = [];

    /* 공시 — mountDisclosures 는 개수를 안 돌려준다. 공용 파일이라
       고치지 않고 한 번 더 부른다. 서버 캐시가 있어 부담은 작다. */
    let polled = '';
    try {
      const r = await apiFetch(`/api/dart/disclosures?limit=${DC_LIMIT}`, { cache: 'no-store' });
      if (r && r.ok) {
        const b = await r.json();
        const n = (b.data || []).length;
        polled = ((b.meta || {}).lastPollAt) || '';
        /* 꽉 찼으면 **더 있다는 것**이 보여야 한다. 서버가 자른 값이다. */
        dcCapped = n >= DC_LIMIT;
        stats.push({ label: '공시', value: dcCapped ? `${n}건 +` : `${n}건` });
      }
    } catch { /* 못 받으면 그 칸을 안 만든다 */ }

    /* 일정 — **`AHEAD_DAYS` 안**만 센다. 달력 전체를 세면 화면과 어긋난다.
       2026-09-22 실측: 달력에 오늘 이후 15건인데 14일 안은 0건이었다.
       기간은 라벨에 넣지 않고 **탭 줄 설명**이 맡는다 — 격자 칸이 좁다. */
    try {
      const g = await collectSchedule({ watch });
      stats.push({ label: '주요 일정', value: `${(g.rows || []).length}건` });
    } catch { /* 〃 */ }

    polledAt = polled;
    if (stats.length) head.setStats(stats);
    head.setSub(polled ? `${stamp(polled)} 기준` : '');
    /* 공시가 꽉 찼는지는 여기서 정해진다. 탭 줄 설명을 다시 맞춘다. */
    head.setTabsNote(tabNote(head.tab(), dcCapped));
    /* 큰 숫자의 안내줄이 방금 받은 공시 시각을 쓴다. 뉴스가 먼저 와서
       이미 그려 둔 것이 있으면 그 줄만 맞춘다. */
    if (bigFeed) paintBig(bigFeed);
  }

  function show(k) {
    for (const t of TABS) panes[t.k].hidden = (t.k !== k);
  }

  show(first);

  /* ── 받아 둔 것으로 먼저 그린다 (2026-10-01 지시) ──
   *
   * 재권님 말씀 — **「모달이 켜질때 보여지는 정보를 미리 받아노면 다 되는거
   * 아닌가?」**. 첫 화면이 주기마다 받아 둔 것을 `news-list.js` 가 쥐고 있다.
   * 꺼내 쓰면 **증권사를 한 번도 더 부르지 않고** 뉴스 칸이 즉시 찬다.
   *
   * 묵은 값을 보여주고 끝내지 않는다 — 바로 아래에서 새로 받아 다시 그린다. */
  const held = lastFeed();
  if (held) { paintNews(held.data); paintBig(held.data); }
  else paintLoading(panes.news);

  /* 격자는 뉴스를 기다리지 않는다. 공시·일정이 오는 대로 찬다 */
  paintStats();
  drawNews().then(paintBig);
  /* `everyServerMs` 가 `document.hidden` 을 함께 보고, **멈추는 함수**를 돌려준다 */
  timer = everyServerMs(REFRESH_KEY, REFRESH_FALLBACK_MS, () => {
    drawNews().then(paintBig);
    paintStats();
  });

  return { close: m.close };
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
