/* ==========================================================================
   주요 일정

   시장 전체가 같이 보는 일정만 담는다 — 금리 · 물가 · 실적 발표.
   종목 하나짜리(배당기준일·주주총회·유상증자)는 여기가 아니라 종목 화면 몫이다.
   자세한 정의는 holdings/CLAUDE.md 「주요 일정 규칙」에 있다.

   두 갈래에서 모은다.

     고정 일정   data/market-calendar.json
                 FOMC·금통위·CPI 는 1년치 날짜가 미리 공개된다. 매일 물어볼
                 이유가 없어 파일로 둔다
     실적 발표   /api/dart/disclosures 의 「기업설명회(IR)개최」
                 수시로 새로 올라오므로 받아서 골라낸다

   첫 화면 사이드바와 뉴스·공시 화면이 이 부품을 함께 쓴다.
   ========================================================================== */

import { apiFetch } from '../data/api.js';

/* 앞으로 며칠 치를 보여줄 것인가. 지난 것은 보여주지 않는다 —
   일정 칸은 "앞으로 뭐가 있나" 를 보는 자리다 (2026-09-15 지시). */
export const AHEAD_DAYS = 14;

const CAL_PATH = './data/market-calendar.json';

/* 공시 제목에서 실적 발표를 골라내는 말. OpenDART 가 쓰는 보고서 이름이다. */
const IR_WORDS = ['기업설명회', 'IR개최', '실적발표'];

const KIND_COLOR = {
  금리: 'violet',
  물가: 'amber',
  실적: 'teal',
  지표: 'indigo',
  수출: 'slate',
};

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/* 오늘 0시. 시각을 지워야 "오늘 것" 이 지난 것으로 빠지지 않는다. */
function today0() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

/* '2026-10-27' → Date. 시간대 해석이 갈리지 않게 숫자로 만든다. */
function parseDay(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s || ''));
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
}

/* 20260915 → Date */
function parseStamp(s) {
  const t = String(s || '');
  return t.length === 8
    ? new Date(+t.slice(0, 4), +t.slice(4, 6) - 1, +t.slice(6, 8))
    : null;
}

/* 며칠 남았나 → '오늘' · '내일' · '3일 뒤' */
function untilText(d) {
  const days = Math.round((d - today0()) / 86400000);
  if (days <= 0) return '오늘';
  if (days === 1) return '내일';
  return `${days}일 뒤`;
}

/* 10.27 */
function dayLabel(d) {
  return `${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
}

/* ── 모으기 ─────────────────────────────────────────────── */

async function loadCalendar() {
  try {
    const r = await fetch(CAL_PATH, { cache: 'no-store' });
    if (!r) return null;   // 로그인이 풀렸다
    const j = await r.json();
    return j && Array.isArray(j.events) ? j : null;
  } catch {
    return null;
  }
}

async function loadEarnings() {
  try {
    const r = await apiFetch('/api/dart/disclosures?limit=200', { cache: 'no-store' });
    if (!r) return null;   // 로그인이 풀렸다
    const j = await r.json();
    if (!j || !j.ok || !Array.isArray(j.data)) return null;
    return j.data.filter((d) => IR_WORDS.some((w) => (d.title || '').includes(w)));
  } catch {
    return null;
  }
}

/* 지수 구성종목 — { 종목코드: ['KPI200', ...] }

   IR 은 하루 15건쯤 올라오는데 대부분 이름 모를 중소형주다. 그대로 두면
   금리·물가 일정이 그 아래로 묻힌다. 코스피200·코스닥150 에 드는 것만
   남긴다 (2026-09-15 지시). 관심종목은 지수에 없어도 남긴다. */
let membersCache = null;

async function loadMembers() {
  if (membersCache) return membersCache;
  try {
    const r = await apiFetch('/api/dart/members', { cache: 'no-store' });
    if (!r) return null;   // 로그인이 풀렸다
    const j = await r.json();
    membersCache = (j && j.ok && j.data) ? j.data : {};
  } catch {
    membersCache = {};
  }
  return membersCache;
}

/**
 * 앞으로 AHEAD_DAYS 안의 일정을 모아 날짜순으로 돌려준다.
 *
 * 돌려주는 것
 *   rows   [{ when, kind, title, note, color, until, url }]
 *   stale  true 면 일정표에 앞으로 것이 하나도 없다 (갱신할 때가 됐다)
 *   calOk  일정표 파일을 읽었나
 */
export async function collectSchedule({ days = AHEAD_DAYS, watch = null } = {}) {
  const [cal, earnings, members] = await Promise.all([
    loadCalendar(), loadEarnings(), loadMembers(),
  ]);
  const mine = new Set(watch || []);

  const from = today0();
  const to = new Date(from.getTime() + days * 86400000);
  const rows = [];

  let future = 0;        // 오늘 이후 일정이 일정표에 몇 개 남았나
  for (const e of (cal && cal.events) || []) {
    const d = parseDay(e.date);
    if (!d) continue;
    if (d >= from) future++;
    if (d < from || d > to) continue;
    rows.push({
      when: d,
      kind: e.kind || '일정',
      title: e.title || '',
      note: e.note || '',
      color: KIND_COLOR[e.kind] || 'slate',
      until: untilText(d),
      url: null,
    });
  }

  /* 실적 발표는 공시로 들어온다. 공시는 '언제 한다' 는 안내라 접수일을
     그대로 쓴다 — 발표일이 따로 적혀 오지 않는다. */
  let irAll = 0;
  for (const d of earnings || []) {
    const day = parseStamp(d.date);
    if (!day || day < from || day > to) continue;
    irAll++;

    /* 관심종목이거나 두 지수에 드는 것만. 그 밖은 세기만 하고 넘긴다. */
    const inIndex = members[d.code] || [];
    const isMine = mine.has(d.code);
    if (!isMine && !inIndex.length) continue;

    rows.push({
      when: day,
      kind: '실적',
      title: `${d.name} 기업설명회`,
      note: d.title || '',
      color: KIND_COLOR['실적'],
      until: untilText(day),
      url: d.url || null,
      code: d.code,
      tags: isMine ? ['watch', ...inIndex] : inIndex,
    });
  }

  rows.sort((a, b) => a.when - b.when);
  return {
    rows, stale: !!cal && future === 0, calOk: !!cal,
    irAll, irKept: rows.filter((r) => r.kind === '실적').length,
    /* 받아올 곳을 아직 못 찾은 것. 날짜가 없어 rows 에 못 섞고 따로 준다.
       화면 맨 아래에 '연결 예정' 으로 적는다 — 무엇이 비어 있는지 보이지
       않으면 없는 건지 못 받는 건지 알 수 없다 (2026-09-15 지시). */
    soon: (cal && cal['연결예정']) || [],
  };
}

/* ── 그리기 ─────────────────────────────────────────────── */

/* 아직 못 붙인 것 한 줄. 날짜가 없으므로 자리만 적어 둔다. */
function soonHtml(r) {
  return `<div class="kh-sc-i is-soon">
    <i class="kh-sc-kind">${esc(r.kind || '일정')}</i>
    <span class="kh-sc-t">${esc(r.title || '')}</span>
    <span class="kh-sc-u">연결 예정</span>
    ${r.note ? `<span class="kh-sc-n">${esc(r.note)}</span>` : ''}
  </div>`;
}

function rowHtml(r, { compact }) {
  /* 한 줄에 종류·제목·날짜·남은 날을 놓고, 설명만 아래로 내린다.
     설명을 가운데 두면 날짜가 다음 줄로 밀려 세 줄이 된다. */
  const inner = `
    <i class="kh-sc-kind is-${esc(r.color)}">${esc(r.kind)}</i>
    <span class="kh-sc-t">${esc(r.title)}</span>
    <span class="kh-sc-u">${esc(r.until)}</span>
    <span class="kh-sc-d kh-num">${esc(dayLabel(r.when))}</span>
    ${(!compact && r.note) ? `<span class="kh-sc-n">${esc(r.note)}</span>` : ''}`;
  return r.url
    ? `<a class="kh-sc-i" href="${esc(r.url)}" target="_blank" rel="noopener">${inner}</a>`
    : `<div class="kh-sc-i">${inner}</div>`;
}

/**
 * 일정을 그린다. 없으면 왜 없는지 적는다 — 빈 칸만 두면 고장인지
 * 일정이 없는 건지 알 수 없다 (CLAUDE.md 데이터 규칙).
 *
 * @param {Element} host   그릴 자리
 * @param {boolean} compat compact=true 면 설명을 빼고 줄만 (사이드바용)
 */
/* 필터 칩. 공시 칸과 같은 모양으로 둔다 (2026-09-15 지시).
   실제로 들어온 것만 만든다 — 없는 묶음이 0 으로 자리만 차지하지 않게. */
const FILTERS = [
  { id: '', label: '전체', hit: () => true },
  { id: 'watch', label: '관심종목', hit: (r) => (r.tags || []).includes('watch') },
  { id: 'KPI200', label: '코스피200', hit: (r) => (r.tags || []).includes('KPI200') },
  { id: 'KQI150', label: '코스닥150', hit: (r) => (r.tags || []).includes('KQI150') },
  { id: '금리', label: '금리', hit: (r) => r.kind === '금리' },
  { id: '물가', label: '물가', hit: (r) => r.kind === '물가' },
];

export function mountSchedule(host, { compact = false, limit = 0, watch = null,
                                      chipHost = null } = {}) {
  if (!host) return { refresh() {} };
  let picked = '';
  let all = [];
  let soon = [];

  function paintChips() {
    if (!chipHost) return;
    const shown = FILTERS.filter((f) => !f.id || all.some(f.hit));
    chipHost.innerHTML = shown.map((f) => {
      const n = f.id ? all.filter(f.hit).length : all.length;
      return `<button class="${picked === f.id ? 'is-on' : ''}" data-f="${esc(f.id)}"
        >${esc(f.label)}<i>${n}</i></button>`;
    }).join('');
    chipHost.querySelectorAll('button').forEach((b) =>
      b.addEventListener('click', () => {
        picked = b.dataset.f || '';
        paintChips();
        paintRows();
      }));
  }

  function paintRows() {
    const f = FILTERS.find((x) => x.id === picked) || FILTERS[0];
    const rows = all.filter(f.hit);

    /* 아직 못 붙인 것은 맨 아래에. 좁은 사이드바에서는 자리가 없어 뺀다 —
       거기는 '더보기' 로 넓은 화면에 가서 본다. */
    const tail = (!compact && soon.length)
      ? `<div class="kh-sc-sep">아직 붙이지 못한 것</div>`
        + soon.map(soonHtml).join('')
      : '';

    if (!rows.length) {
      host.innerHTML = `<div class="kh-soon">
        <div class="kh-soon-t">해당하는 일정이 없습니다</div></div>` + tail;
      return;
    }
    const show = limit > 0 ? rows.slice(0, limit) : rows;
    host.innerHTML = show.map((r) => rowHtml(r, { compact })).join('') + tail;
  }

  async function refresh() {
    const got = await collectSchedule({ watch });
    const { rows, stale, calOk } = got;
    all = rows;
    soon = got.soon;

    if (!calOk) {
      host.innerHTML = `<div class="kh-soon">
        <div class="kh-soon-t">일정을 불러오지 못했습니다</div>
        <div class="kh-soon-s">data/market-calendar.json</div></div>`;
      return;
    }
    if (stale) {
      host.innerHTML = `<div class="kh-soon">
        <div class="kh-soon-t">일정표를 갱신할 때입니다</div>
        <div class="kh-soon-s">앞으로의 일정이 비어 있습니다 — data/market-calendar.json</div>
        </div>`;
      return;
    }
    if (!rows.length) {
      host.innerHTML = `<div class="kh-soon">
        <div class="kh-soon-t">${AHEAD_DAYS}일 안에 예정된 일정이 없습니다</div>
        <div class="kh-soon-s">금리 · 물가 · 실적 발표를 봅니다</div></div>`;
      return;
    }

    paintChips();
    paintRows();
  }

  refresh();
  return { refresh };
}
