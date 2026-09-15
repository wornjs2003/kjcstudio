/* ==========================================================================
   뉴스 · 공시 화면

   두 칸이다. 왼쪽 뉴스, 오른쪽 공시.

   뉴스는 갈래가 둘이고 성격이 달라 섞지 않는다 (2026-09-15 지시).
     시장 이슈    구글 뉴스 RSS · 주제어별 · 원문 링크로 나간다
     종목 움직임  KIS · 종목코드가 붙어 온다 · 눌러서 그 종목 화면으로 간다

   주제 칩은 data/news-topics.json 이 만든다. 코드를 고치지 않고 늘어난다.
   왜 이렇게 나눴는지는 server/news.py 머리말에 적어 두었다.
   ========================================================================== */

import { mountWatchSide, mountVBar, mountFootStrip, startLiveLoop }
  from './components/frame.js';
import { WATCHLIST } from './data/market.js';

const $ = (id) => document.getElementById(id);
const WATCH = new Set(WATCHLIST.map((s) => s.code));

/* 화면을 열어둔 채로도 새 것이 들어오도록. 서버가 5분마다 받으므로
   그보다 조금 짧게 둔다. */
const REFRESH_MS = 60_000;

let feed = { issues: [], moves: [], topics: [] };
let disclosures = null;          // null = 못 받음, [] = 받았는데 없음
let seg = 'issues';              // 어느 갈래를 보고 있나
let topicOn = null;              // null = 전체, 아니면 주제 id
let dcOn = null;                 // 공시 필터: null | 'watch' | 꼬리표

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/* 2026-09-15T12:17:41+09:00 → 12:17 · 어제 것이면 09.14 */
function hhmm(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return '';
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return sameDay
    ? `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    : `${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
}

/* 20260915 → 09.15 */
function shortDate(s) {
  return (!s || s.length !== 8) ? (s || '') : `${s.slice(4, 6)}.${s.slice(6, 8)}`;
}

/* 제목 앞 [기재정정] 같은 꼬리표를 떼어낸다 */
function splitTag(title) {
  const m = /^\[([^\]]{1,10})\]\s*(.*)$/.exec(title || '');
  return m ? { tag: m[1], rest: m[2] } : { tag: null, rest: title || '' };
}

/* ── 카테고리 색 ────────────────────────────────────────────

   색 값은 여기 없다. assets/css/theme.css 의 --kh-cat-<이름> 을 가리키는
   이름만 다룬다 (CLAUDE.md 「색상 하드코딩 금지」).

   어느 이름을 쓸지는 데이터가 정한다.
     뉴스  data/news-topics.json 의 color
     공시  data/disclosure-tags.json 의 묶음
   둘 다 없으면 이름으로 자동 배정한다. 새 주제를 넣으며 색을 깜빡해도
   회색으로 뭉개지지 않고, 같은 이름이면 늘 같은 색이 나온다.            */

const CAT_COLORS = ['indigo', 'amber', 'violet', 'teal', 'rose', 'slate'];

let dcTagRules = [];        // disclosure-tags.json 의 묶음
let dcOther = {};           // 어디에도 안 걸린 것을 담는 묶음

function autoColor(key) {
  /* 글자를 더해 나머지를 구한다. 같은 글자면 늘 같은 값이 나온다. */
  let n = 0;
  for (const ch of String(key || '')) n = (n * 31 + ch.charCodeAt(0)) % 9973;
  return CAT_COLORS[n % CAT_COLORS.length];
}

function topicColor(id) {
  const t = (feed.topics || []).find((x) => x.id === id);
  return (t && t.color) || autoColor(id);
}

/* 공시 종류가 어느 묶음인지 찾는다. 색과 딱지 글자를 함께 준다.
   딱지는 "주주총회소집결의" 같은 제목을 그대로 쓰지 않고 "일정" 처럼
   성격을 적는다 — 아래 제목 줄과 같은 말이 두 번 나오면 읽기 나쁘다. */
function dcGroup(kind) {
  for (const g of dcTagRules) {
    if ((g["말"] || []).some((w) => w && kind.includes(w))) {
      return { color: g.color, label: g.label || kind };
    }
  }
  /* 어디에도 안 걸리면 기타로 모은다. 그대로 두면 하루 40가지가
     낱개 칩이 되어 필터가 오히려 안 보인다 (2026-09-15). */
  return { color: dcOther.color || 'slate', label: dcOther.label || '기타' };
}

/* 칩은 묶음 라벨만 들고 있다. 거기서 색을 되찾는다. */
function dcGroupColor(label) {
  const g = dcTagRules.find((x) => x.label === label);
  return (g && g.color) || autoColor(label);
}

/* ── 받아오기 ───────────────────────────────────────────── */

async function loadFeed() {
  try {
    const r = await fetch('/api/news/feed', { cache: 'no-store' });
    const j = await r.json();
    if (j && j.ok && j.data) feed = j.data;
  } catch { /* 그대로 둔다 — 화면에 "불러오지 못함" 이 남는다 */ }
}

async function loadDcTags() {
  if (dcTagRules.length) return;            // 한 번만 읽으면 된다
  try {
    const r = await fetch('./data/disclosure-tags.json', { cache: 'no-store' });
    const j = await r.json();
    dcTagRules = j["묶음"] || [];
    dcOther = j["기타"] || {};
  } catch { dcTagRules = []; dcOther = {}; }
}

async function loadDisclosures() {
  try {
    const r = await fetch('/api/dart/disclosures?limit=200', { cache: 'no-store' });
    const j = await r.json();
    disclosures = (j && j.ok && Array.isArray(j.data)) ? j.data : null;
  } catch {
    disclosures = null;
  }
}

/* ── 통계 4칸 ───────────────────────────────────────────── */

function paintStats() {
  const host = $('kh-nw-stats');
  if (!host) return;
  const all = disclosures || [];
  const watch = all.filter((d) => WATCH.has(d.code));
  const codes = new Set(all.map((d) => d.code)).size;

  const cell = (label, value, unit, cls = '') => `
    <div class="kh-nw-stat">
      <div class="kh-nw-stat-l">${esc(label)}</div>
      <div class="kh-nw-stat-v ${cls}">${esc(value)}<span>${esc(unit)}</span></div>
    </div>`;

  host.innerHTML =
    cell('저장된 공시', all.length, '건') +
    cell('관심종목 공시', watch.length, '건', watch.length ? 'kh-up' : '') +
    cell('공시 나온 종목', codes, '개') +
    cell('뉴스', feed.issues.length + feed.moves.length, '건');
}

/* ── 뉴스 ───────────────────────────────────────────────── */

function paintChips() {
  const host = $('kh-nw-chips');
  if (!host) return;

  /* 종목 움직임에는 주제가 없다. 칩을 숨겨 자리를 비운다. */
  if (seg === 'moves') { host.innerHTML = ''; return; }

  const n = (id) => feed.issues.filter((x) => x.topic === id).length;
  host.innerHTML =
    `<button class="${topicOn === null ? 'is-on' : ''}" data-t="">전체
       <i>${feed.issues.length}</i></button>` +
    (feed.topics || []).map((t) =>
      `<button class="is-${esc(topicColor(t.id))} ${topicOn === t.id ? 'is-on' : ''}"
         data-t="${esc(t.id)}">${esc(t.label)}<i>${n(t.id)}</i></button>`).join('');

  host.querySelectorAll('button').forEach((b) =>
    b.addEventListener('click', () => {
      topicOn = b.dataset.t || null;
      paintChips();
      paintNews();
    }));
}

function issueRow(x) {
  return `<a class="kh-nw-i" href="${esc(x.link)}" target="_blank" rel="noopener">
    <span class="kh-nw-i-top">
      <i class="kh-nw-topic is-${esc(topicColor(x.topic))}">${esc(x.topicLabel || '')}</i>
      <i class="kh-nw-src">${esc(x.source || '')}</i>
      <i class="kh-nw-at kh-num">${esc(hhmm(x.at))}</i>
    </span>
    <span class="kh-nw-i-t">${esc(x.title)}</span>
  </a>`;
}

function moveRow(x) {
  const s = x.stocks || [];
  const first = s[0] || {};
  const more = s.length > 1 ? `<i class="kh-nw-more">외 ${s.length - 1}</i>` : '';
  const mine = s.some((v) => WATCH.has(v.code));
  return `<a class="kh-nw-i ${mine ? 'is-mine' : ''}"
      href="./stock.html?code=${esc(first.code)}">
    <span class="kh-nw-i-top">
      <i class="kh-nw-topic">${esc(x.market || '')}</i>
      <i class="kh-nw-stock">${esc(first.name)}</i>${more}
      <i class="kh-nw-at kh-num">${esc(hhmm(x.at))}</i>
    </span>
    <span class="kh-nw-i-t">${esc(x.title)}</span>
  </a>`;
}

function paintNews() {
  const host = $('kh-nw-news');
  if (!host) return;

  if (seg === 'moves') {
    const rows = feed.moves || [];
    host.innerHTML = rows.length
      ? rows.map(moveRow).join('')
      : `<div class="kh-soon"><div class="kh-soon-t">종목이 붙은 뉴스가 없습니다</div>
           <div class="kh-soon-s">장이 열리면 채워집니다</div></div>`;
    return;
  }

  const rows = (feed.issues || []).filter((x) => !topicOn || x.topic === topicOn);
  host.innerHTML = rows.length
    ? rows.map(issueRow).join('')
    : `<div class="kh-soon"><div class="kh-soon-t">뉴스를 불러오지 못했습니다</div>
         <div class="kh-soon-s">주제어는 data/news-topics.json 에 있습니다</div></div>`;
}

function bindSeg() {
  const host = $('kh-nw-seg');
  if (!host) return;
  host.querySelectorAll('button').forEach((b) =>
    b.addEventListener('click', () => {
      seg = b.dataset.k;
      host.querySelectorAll('button').forEach((x) =>
        x.classList.toggle('is-on', x === b));
      paintChips();
      paintNews();
    }));
}

/* ── 공시 ───────────────────────────────────────────────── */

/* 공시 하나가 어느 묶음인지. 목록과 칩이 같은 판정을 쓰도록 한 곳에 둔다. */
function dcLabel(d) {
  const { tag } = splitTag(d.title);
  return dcGroup(tag || firstWord(d.title)).label;
}

/* 칩은 묶음 단위로 만든다.

   종류 그대로 세면 하루 44가지가 나와 칩이 넘친다 (2026-09-15 실측).
   성격으로 묶으면 여섯 개로 줄고, 무엇을 고르는지도 분명해진다.
   실제로 들어온 것만 만든다 — 안 나온 묶음이 0 으로 자리만 차지하지 않게. */
function dcTags() {
  const c = new Map();
  for (const d of disclosures || []) {
    const k = dcLabel(d);
    c.set(k, (c.get(k) || 0) + 1);
  }
  return [...c.entries()].sort((a, b) => b[1] - a[1]);
}

/* 꼬리표가 없으면 제목 앞머리를 종류로 친다 ("단일판매ㆍ공급계약체결") */
function firstWord(title) {
  const t = String(title || '');
  const cut = t.search(/[ (（]/);
  return (cut > 0 ? t.slice(0, cut) : t).slice(0, 12);
}

function paintDcChips() {
  const host = $('kh-dc-chips');
  if (!host) return;
  const all = disclosures || [];
  const watch = all.filter((d) => WATCH.has(d.code)).length;

  host.innerHTML =
    `<button class="${dcOn === null ? 'is-on' : ''}" data-f="">전체<i>${all.length}</i></button>` +
    `<button class="${dcOn === 'watch' ? 'is-on' : ''}" data-f="watch">관심종목<i>${watch}</i></button>` +
    dcTags().map(([t, n]) =>
      `<button class="is-${esc(dcGroupColor(t))} ${dcOn === t ? 'is-on' : ''}"
         data-f="${esc(t)}">${esc(t)}<i>${n}</i></button>`).join('');

  host.querySelectorAll('button').forEach((b) =>
    b.addEventListener('click', () => {
      dcOn = b.dataset.f || null;
      paintDcChips();
      paintDc();
    }));
}

function dcRow(d) {
  const { tag, rest } = splitTag(d.title);
  const mine = WATCH.has(d.code);
  /* 딱지는 꼬리표가 있으면 그것, 없으면 제목 앞머리를 쓴다.
     같은 종류면 늘 같은 색이 되도록 색도 그 글자로 고른다. */
  const kind = tag || firstWord(d.title);
  const g = dcGroup(kind);
  return `<a class="kh-nw-i ${mine ? 'is-mine' : ''}"
      href="${esc(d.url)}" target="_blank" rel="noopener">
    <span class="kh-nw-i-top">
      <i class="kh-nw-topic is-${esc(g.color)}">${esc(g.label)}</i>
      <i class="kh-nw-stock">${esc(d.name)}</i>
      <i class="kh-nw-code kh-num">${esc(d.code)}</i>
      ${mine ? '<i class="kh-nw-mine">관심종목</i>' : ''}
      <i class="kh-nw-at kh-num">${esc(shortDate(d.date))}</i>
    </span>
    <span class="kh-nw-i-t">${esc(rest)}</span>
  </a>`;
}

function paintDc() {
  const host = $('kh-nw-dc');
  if (!host) return;

  if (disclosures === null) {
    host.innerHTML = `<div class="kh-soon">
      <div class="kh-soon-t">공시를 불러오지 못했습니다</div>
      <div class="kh-soon-s">중계 서버가 꺼져 있을 수 있습니다</div></div>`;
    return;
  }

  let rows = disclosures;
  if (dcOn === 'watch') rows = rows.filter((d) => WATCH.has(d.code));
  else if (dcOn) rows = rows.filter((d) => dcLabel(d) === dcOn);

  host.innerHTML = rows.length
    ? rows.slice(0, 120).map(dcRow).join('')
    : `<div class="kh-soon"><div class="kh-soon-t">해당하는 공시가 없습니다</div></div>`;
}

/* ── 주요 일정 ──────────────────────────────────────────────

   아직 받아올 곳을 붙이지 않았다. 무엇이 비어 있고 무엇을 붙이면 채워지는지
   화면에 적어 둔다 (CLAUDE.md 데이터 규칙 — 그럴듯한 숫자를 박아두지 않는다). */
function paintSched() {
  const host = $('kh-nw-sched');
  if (!host) return;
  host.innerHTML = `
    <div class="kh-soon">
      <div class="kh-soon-t">실적 발표 · 지표 발표 일정</div>
      <div class="kh-soon-s">붙일 것: 한국은행 경제통계 · 거래소 실적 일정</div>
    </div>`;
}

/* ── 머리말 ─────────────────────────────────────────────── */

function paintHead() {
  const sub = $('kh-nw-sub');
  const when = $('kh-nw-when');
  if (sub) {
    sub.textContent = '코스피 · 코스닥 공시를 5분마다 받아 둡니다. '
      + '뉴스는 주제어로 모읍니다.';
  }
  if (when) {
    const t = new Date();
    when.innerHTML = `<i class="kh-pdot"></i>방금 확인함 · `
      + `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}`;
  }
}

/* ── 시작 ───────────────────────────────────────────────── */

async function refresh() {
  await Promise.all([loadFeed(), loadDisclosures(), loadDcTags()]);
  paintStats();
  paintChips();
  paintNews();
  paintDcChips();
  paintDc();
  paintSched();
  paintHead();
}

/* 사이드바·세로바·시세 띠는 다른 화면과 같은 부품을 쓴다 */
mountWatchSide($('kh-side'), {});
mountVBar($('kh-vbar'), 'news');
mountFootStrip($('kh-foot'));

bindSeg();
refresh();
setInterval(() => { if (!document.hidden) refresh(); }, REFRESH_MS);

/* 관심 사이드바와 시세 띠는 다른 화면과 같은 것을 쓴다 */
startLiveLoop({ prices: true, indexMs: 0 });
