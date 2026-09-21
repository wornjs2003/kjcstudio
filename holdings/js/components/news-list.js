/* ==========================================================================
   뉴스 목록 그리기

   첫 화면 사이드 칸과 뉴스 모달이 같은 것을 쓴다. 전에는 `home.js` 안에
   인라인으로, `news.js` 에 또 따로 있어서 **같은 데이터를 두 벌 그리고
   있었다.** 한 곳에 모은다 (CLAUDE.md 「같은 값은 한 곳에만 둔다」).

   ── 모달이 원본이고 사이드 칸은 덜어낸 일부다 ──

   받아오는 것은 같고 **보이는 밀도만 다르다.**

       full     주제 · 매체 · 시각 · 제목        모달
       compact  주제 · 제목                      사이드 칸

   그래서 `rowHtml` 하나에 `compact` 를 넘긴다. 마크업을 둘로 두면
   새 항목이 생길 때 한쪽만 고치게 된다.

   ── 무엇을 받나 ──

       /api/news/issues   시장 이슈만          가볍다. 사이드 칸이 쓴다
       /api/news/feed     이슈 + 종목 움직임    모달이 쓴다

   **받는 것은 부르는 쪽이 정한다.** 모달이 닫혀 있을 때까지 무거운 쪽을
   받으면 KIS 를 겹쳐 부르게 된다 (CLAUDE.md 모달 룰 ④ — 멈추지 말고 늦춘다).
   서버가 `issues` · `moves` 를 따로 캐시하므로(server/news.py 의 `_cached`)
   둘을 다 불러도 외부를 두 번 치지는 않는다.
   ========================================================================== */

import { apiFetch } from '../data/api.js';

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/* 2026-09-21T14:58:04+09:00 → 14:58 */
function hhmm(iso) {
  if (!iso) return '';
  const m = /T(\d{2}):(\d{2})/.exec(iso);
  return m ? `${m[1]}:${m[2]}` : '';
}

/* 주제어마다 색을 달리한다. 이름은 news.css 의 `.kh-nw-topic.is-*` 에 있다. */
const TOPIC_CLASS = {
  rate: 'rate', fx: 'rate', price: 'price', policy: 'policy',
  corp: 'corp', global: 'global',
};
function topicClass(id) {
  return TOPIC_CLASS[id] || 'etc';
}

/**
 * 뉴스 한 줄.
 * @param {object}  x          서버가 준 항목
 * @param {boolean} compact    사이드 칸이면 true — 매체·시각을 뺀다
 */
export function rowHtml(x, compact = false) {
  const topic = `<i class="kh-nw-topic is-${esc(topicClass(x.topic))}">${esc(x.topicLabel || '')}</i>`;
  if (compact) {
    return `<a class="kh-side-news-i" href="${esc(x.link)}" target="_blank" rel="noopener">
      ${topic}<span>${esc(x.title)}</span>
    </a>`;
  }
  return `<a class="kh-nw-i" href="${esc(x.link)}" target="_blank" rel="noopener">
    <span class="kh-nw-i-top">
      ${topic}
      <i class="kh-nw-src">${esc(x.source || '')}</i>
      <i class="kh-nw-at kh-num">${esc(hhmm(x.at))}</i>
    </span>
    <span class="kh-nw-i-t">${esc(x.title)}</span>
  </a>`;
}

/* 종목이 붙은 뉴스. 누르면 그 종목으로 간다 — 링크가 없는 자료라 그렇다. */
export function moveRowHtml(x, watch = null) {
  const s = x.stocks || [];
  const first = s[0] || {};
  const more = s.length > 1 ? `<i class="kh-nw-more">외 ${s.length - 1}</i>` : '';
  const mine = watch && s.some(v => watch.has(v.code));
  return `<a class="kh-nw-i ${mine ? 'is-mine' : ''}" href="./stock.html?code=${esc(first.code)}">
    <span class="kh-nw-i-top">
      <i class="kh-nw-topic">${esc(x.market || '')}</i>
      <i class="kh-nw-stock">${esc(first.name)}</i>${more}
      <i class="kh-nw-at kh-num">${esc(hhmm(x.at))}</i>
    </span>
    <span class="kh-nw-i-t">${esc(x.title)}</span>
  </a>`;
}

/* 못 받았을 때와 받았는데 없을 때를 가른다 (CLAUDE.md 데이터 규칙).
   그래야 연결이 안 된 건지 뉴스가 없는 건지 알 수 있다. */
function emptyHtml(kind, compact) {
  const t = kind === 'fail' ? '뉴스를 불러오지 못했습니다' : '받은 뉴스가 없습니다';
  const s = kind === 'fail' ? '중계 서버가 꺼져 있거나 인증키가 없습니다'
                            : '경제지에 새 기사가 올라오면 채워집니다';
  if (compact) return `<div class="kh-sched-i kh-mut">${t}</div>`;
  return `<div class="kh-soon"><div class="kh-soon-t">${t}</div>
    <div class="kh-soon-s">${s}</div></div>`;
}

/** 시장 이슈만 받는다. 사이드 칸이 쓴다. 못 받으면 null. */
export async function fetchIssues() {
  try {
    const r = await apiFetch('/api/news/issues', { cache: 'no-store' });
    if (!r) return null;                 // 로그인이 풀렸다
    const j = await r.json();
    if (j && j.ok && Array.isArray(j.data)) return j.data;
  } catch { /* 아래에서 못 받았다고 적는다 */ }
  return null;
}

/** 이슈 + 종목 움직임. 모달이 쓴다. 못 받으면 null. */
export async function fetchFeed() {
  try {
    const r = await apiFetch('/api/news/feed', { cache: 'no-store' });
    if (!r) return null;
    const j = await r.json();
    if (j && j.ok && j.data) return j.data;
  } catch { /* 위와 같다 */ }
  return null;
}

/**
 * 받아둔 줄을 host 에 그린다.
 *   rows    null 이면 「못 받았다」, 빈 배열이면 「없다」
 *   limit   0 이면 전부 — 모달이 그렇게 부른다
 */
export function paintIssues(host, rows, { compact = false, limit = 0 } = {}) {
  if (!host) return;
  if (rows === null) { host.innerHTML = emptyHtml('fail', compact); return; }
  if (!rows.length)  { host.innerHTML = emptyHtml('none', compact); return; }
  const show = limit > 0 ? rows.slice(0, limit) : rows;
  host.innerHTML = show.map(x => rowHtml(x, compact)).join('');
}
