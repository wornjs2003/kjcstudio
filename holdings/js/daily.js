/* ==========================================================================
   데일리분석 화면

   그날의 일정 · 지수 · 뉴스를 한 장으로 모은다. 같은 내용을 아침에 텔레그램으로
   보낼 예정이고, 오른쪽 미리보기가 그 문안 그대로다 — 화면과 문안이 갈리지
   않도록 한 곳(buildTelegram)에서 만든다.

   지금 붙은 것과 아직 아닌 것

     일정   data/market-calendar.json      components/schedule.js 를 그대로 쓴다
     지수   /api/kis/indices
     뉴스   /api/news/feed 의 issues       주제어는 서버가 붙여 온다
     ─────────────────────────────────────────────────────────────────────
     주도 섹터   업종 지수를 받아올 곳을 확정하지 못했다
     저장·발송   날짜별로 쌓는 자리와 07:30 발송이 아직 없다

   안 붙은 자리는 화면에 빨간 바탕으로 남긴다. 문서에만 적으면 아무도 다시
   안 읽고 그대로 굳는다 (CLAUDE.md 「아직 안 정해진 자리」 2026-09-15 지시).
   ========================================================================== */

/* mountWatchSide 는 부르지 않는다. 이 화면의 오른쪽 칸은 관심종목이 아니라
   보낼 문안이다 (2026-09-16 지시). */
import { mountVBar, mountFootStrip, startLiveLoop }
  from './components/frame.js';
import { collectSchedule } from './components/schedule.js';

const $ = (id) => document.getElementById(id);

/* 화면을 열어둔 채로도 새 것이 들어오도록. 서버가 5분마다 받으므로 그보다 짧게. */
const REFRESH_MS = 60_000;

/* 화면에 올릴 지수와 부르는 이름.
   서버가 주는 name 이 'KOSPI' 처럼 영문이거나 '미국 USD' 처럼 길어서 여기서 고친다. */
const INDEX_ROWS = [
  { code: 'KOSPI',    label: 'KOSPI' },
  { code: 'KOSDAQ',   label: 'KOSDAQ' },
  { code: 'KOSPI200', label: '코스피200' },
  { code: 'SPX',      label: 'S&P 500',   match: /S&P/i },
  { code: 'COMP',     label: '나스닥 종합', match: /나스닥/ },
  { code: 'USD',      label: '달러 · 원',  match: /USD|달러/ },
  { code: 'VIX',      label: 'VIX',       match: /VIX/i },
];

let indices = [];
let issues = [];
let schedule = [];

/* ── 잔손질 ─────────────────────────────── */

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function num(v, digits = 2) {
  if (v == null || isNaN(v)) return '—';
  return Number(v).toLocaleString('ko-KR',
    { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/* 등락을 색 이름으로. 한국식 — 오르면 빨강, 내리면 파랑 */
function tone(v) {
  if (v == null || isNaN(v) || Number(v) === 0) return 'flat';
  return Number(v) > 0 ? 'up' : 'down';
}

function signed(v, digits = 2) {
  if (v == null || isNaN(v)) return '—';
  const n = Number(v);
  const mark = n > 0 ? '▲' : n < 0 ? '▼' : '—';
  return `${mark} ${num(Math.abs(n), digits)}`;
}

function pct(v) {
  if (v == null || isNaN(v)) return '';
  const n = Number(v);
  return `${n > 0 ? '+' : n < 0 ? '−' : ''}${num(Math.abs(n), 2)}%`;
}

/* 2026-09-16T17:12:52+09:00 → 17:12 · 어제 것이면 09.15 */
function hhmm(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return '';
  const sameDay = d.toDateString() === new Date().toDateString();
  const p = (n) => String(n).padStart(2, '0');
  return sameDay
    ? `${p(d.getHours())}:${p(d.getMinutes())}`
    : `${p(d.getMonth() + 1)}.${p(d.getDate())}`;
}

function todayLabel() {
  const d = new Date();
  const wd = ['일', '월', '화', '수', '목', '금', '토'][d.getDay()];
  return `${d.getMonth() + 1}월 ${d.getDate()}일 (${wd})`;
}

/* ── 받아오기 ───────────────────────────── */

async function loadIndices() {
  try {
    const r = await fetch('/api/kis/indices', { cache: 'no-store' });
    if (!r.ok) throw new Error(r.status);
    const b = await r.json();
    indices = Array.isArray(b.data) ? b.data : [];
  } catch {
    indices = [];          /* 화면에 「받지 못했습니다」 가 남는다 */
  }
}

async function loadNews() {
  try {
    const r = await fetch('/api/news/feed', { cache: 'no-store' });
    if (!r.ok) throw new Error(r.status);
    const b = await r.json();
    /* 서버는 {ok, data:{issues, moves, topics}} 로 준다. news.js 와 같은 자리를 읽는다. */
    issues = (b.data && Array.isArray(b.data.issues)) ? b.data.issues : [];
  } catch {
    issues = [];
  }
}

async function loadSchedule() {
  try {
    /* 오늘과 앞으로 사흘치만. 데일리분석은 「그날」 이 중심이라 2주는 길다. */
    schedule = await collectSchedule({ days: 3 });
  } catch {
    schedule = [];
  }

  /* 여러 날에 걸친 일정을 따로 줍는다.
     components/schedule.js 는 시작일(date)만 보고 endDate 를 읽지 않는다.
     그래서 어제 시작해 오늘까지 가는 FOMC 같은 것이 「오늘」 에서 빠진다.
     공용 파일이라 여기서 고치지 않고 주식페이지_개발 에 넘겼다 (2026-09-16).
     고쳐지면 이 함수를 지운다. */
  try {
    const r = await fetch('./data/market-calendar.json', { cache: 'no-store' });
    if (!r.ok) return;
    const cal = await r.json();
    const t0 = new Date(); t0.setHours(0, 0, 0, 0);
    const already = new Set(schedule.map((e) => e.title));

    for (const e of (cal.events || [])) {
      if (!e.endDate || already.has(e.title)) continue;
      const from = new Date(e.date + 'T00:00:00');
      const to = new Date(e.endDate + 'T00:00:00');
      if (isNaN(from) || isNaN(to)) continue;
      if (from <= t0 && t0 <= to) {
        schedule.unshift({
          when: t0, kind: e.kind || '일정', title: e.title || '',
          note: e.note || '', ongoing: true,
        });
      }
    }
  } catch { /* 못 읽으면 위에서 받은 것만 쓴다 */ }
}

/* ── ① 오늘 일정 ────────────────────────── */

function drawSchedule() {
  const box = $('kh-dl-sch');
  if (!box) return;

  if (!schedule.length) {
    box.innerHTML = '<div class="kh-dl-sch-row">'
      + '<span class="kh-dl-sch-t">사흘 안에 예정된 일정이 없습니다</span></div>';
    return;
  }

  const today = new Date().toDateString();
  box.innerHTML = schedule.map((e) => {
    const isToday = e.ongoing || (e.when && e.when.toDateString() === today);
    const p = (n) => String(n).padStart(2, '0');
    const when = e.ongoing ? '진행 중'
      : isToday ? '오늘'
      : e.when ? `${p(e.when.getMonth() + 1)}/${p(e.when.getDate())}` : '';
    return `<div class="kh-dl-sch-row${isToday ? ' is-now' : ''}">
      <span class="kh-dl-sch-when">${esc(when)}</span>
      <span class="kh-dl-sch-kind">${esc(e.kind)}</span>
      <span class="kh-dl-sch-t">${esc(e.title)}</span>
      ${e.note ? `<span class="kh-dl-sch-n">${esc(e.note)}</span>` : ''}
    </div>`;
  }).join('');
}

/* ── ② 주요 지수 ────────────────────────── */

function pickIndex(row) {
  return indices.find((x) => x.code === row.code)
      || (row.match ? indices.find((x) => row.match.test(x.name || '')) : null);
}

function drawIndices() {
  const box = $('kh-dl-idx');
  if (!box) return;

  if (!indices.length) {
    box.innerHTML = '<div class="kh-dl-todo"><b>지수를 받지 못했습니다</b>'
      + '<span>중계 서버가 꺼져 있으면 이 칸이 비어 있습니다.</span></div>';
    return;
  }

  const cells = INDEX_ROWS.map((row) => {
    const x = pickIndex(row);
    if (!x) return '';
    const t = tone(x.change);
    /* 상승·하락 종목 수는 지수에만 있다. 환율·VIX 에는 없다. */
    const breadth = (x.up || x.down)
      ? `상승 ${x.up} · 하락 ${x.down}`
      : (x.unit && x.unit !== 'pt' ? x.unit : '');
    return `<div class="kh-dl-idx-c">
      <div class="kh-dl-idx-n">${esc(row.label)}</div>
      <div class="kh-dl-idx-v">${num(x.value)}</div>
      <div class="kh-dl-idx-d kh-dl-${t}">${signed(x.change)} (${pct(x.changePct)})</div>
      ${breadth ? `<div class="kh-dl-idx-sub">${esc(breadth)}</div>` : ''}
    </div>`;
  }).filter(Boolean).join('');

  /* 미정: 야간선물과 다우존스는 아직 못 붙였다.
     야간선물 — 전용 시세 API 가 없어 일반 선물(FHMIF10000000)에 야간 종목코드를
     넣어 실측해야 한다.
     다우존스 — DJI · .DJI · DJIA 를 네 가지 시장구분으로 다 불러봤지만 전부 0 이었다
     (DOW 는 다우社 주식이라 28원이 나온다). js/home.js 의 INDEX_CELLS 주석 참조. */
  box.innerHTML = cells + `
    <div class="kh-dl-idx-c" style="background:var(--kh-up-dim)">
      <div class="kh-dl-idx-n" style="color:var(--kh-up)">야간선물 · 다우존스</div>
      <div class="kh-dl-idx-d kh-dl-up" style="margin-top:6px">연결 예정</div>
      <div class="kh-dl-idx-sub" style="color:var(--kh-up)">받아올 곳을 찾는 중입니다</div>
    </div>`;
}

/* ── ③ 오늘 뉴스 ────────────────────────── */

function drawNews() {
  const box = $('kh-dl-news');
  const src = $('kh-dl-news-src');
  if (!box) return;

  if (!issues.length) {
    box.innerHTML = '<div class="kh-dl-todo"><b>뉴스를 받지 못했습니다</b>'
      + '<span>중계 서버가 꺼져 있으면 이 칸이 비어 있습니다.</span></div>';
    return;
  }
  if (src) src.textContent = `경제지 RSS · 오늘 ${issues.length}건`;

  /* 주제가 겹치지 않게 앞에서부터 고른다. 같은 주제 기사가 줄줄이 오는 것을 막는다. */
  const seen = new Set();
  const picked = [];
  for (const n of issues) {
    const key = n.topic || n.topicLabel || '';
    if (key && seen.has(key)) continue;
    if (key) seen.add(key);
    picked.push(n);
    if (picked.length >= 6) break;
  }

  box.innerHTML = picked.map((n) => `
    <a class="kh-dl-news-row" href="${esc(n.link)}" target="_blank" rel="noopener">
      <span class="kh-dl-topic">${esc(n.topicLabel || '기타')}</span>
      <span>
        <span class="kh-dl-news-t">${esc(n.title)}</span>
        <span class="kh-dl-news-m">${esc(n.source || '')} · ${esc(hhmm(n.at))}</span>
      </span>
    </a>`).join('');
}

/* ── 텔레그램 문안 ──────────────────────── */
/* 화면과 문안이 갈리지 않도록 같은 데이터에서 한 번에 만든다. */

function buildTelegram() {
  const L = [];
  L.push(`📊 데일리분석 · ${todayLabel()}`);

  const today = new Date().toDateString();
  const todayEvents = schedule.filter(
    (e) => e.ongoing || (e.when && e.when.toDateString() === today));
  if (todayEvents.length) {
    L.push('', '오늘 일정');
    for (const e of todayEvents) {
      L.push(`· ${e.title}${e.ongoing ? ' (진행 중)' : ''}`);
      if (e.note) L.push(`  → ${e.note}`);
    }
  }

  const line = (row) => {
    const x = pickIndex(row);
    if (!x) return null;
    const mark = Number(x.change) > 0 ? '▲' : Number(x.change) < 0 ? '▼' : '—';
    return `${row.label} ${num(x.value)} ${mark}${num(Math.abs(x.changePct), 2)}%`;
  };

  const home = ['KOSPI', 'KOSDAQ'].map((c) => line(INDEX_ROWS.find((r) => r.code === c)))
    .filter(Boolean);
  if (home.length) {
    L.push('', '국내', ...home);
    const k = pickIndex(INDEX_ROWS[0]);
    if (k && (k.up || k.down)) L.push(`상승 ${k.up} · 하락 ${k.down}`);
  }

  const away = ['SPX', 'COMP', 'USD'].map((c) => line(INDEX_ROWS.find((r) => r.code === c)))
    .filter(Boolean);
  if (away.length) L.push('', '해외 (현지 마감)', ...away);

  if (issues.length) {
    L.push('', '오늘 뉴스');
    const seen = new Set();
    let n = 0;
    for (const it of issues) {
      const key = it.topic || '';
      if (key && seen.has(key)) continue;
      if (key) seen.add(key);
      L.push(`· ${it.topicLabel ? `${it.topicLabel} — ` : ''}${it.title}`);
      if (++n >= 3) break;
    }
  }

  /* 화면에는 빨간 자국으로 남아 있는 칸들이다. 문안에서 통째로 빼면 폰에서는
     무엇이 빠졌는지 알 수 없다. 붙으면 이 줄을 지운다. */
  L.push('', '연결 예정', '· 주도 섹터 (국내·미국 업종)', '· 야간선물 · 다우존스');

  L.push('', '전문 보기 › thekjcstudio.com/holdings/daily.html');
  return L.join('\n');
}

function drawTelegram() {
  const box = $('kh-dl-tg');
  if (box) box.textContent = buildTelegram();
}

/* ── 그리기 ─────────────────────────────── */

function drawAll() {
  drawSchedule();
  drawIndices();
  drawNews();
  drawTelegram();

  const sub = $('kh-dl-sub');
  if (sub) {
    sub.textContent = `${todayLabel()} · 그날의 일정 · 지수 · 뉴스를 한 장으로 모읍니다`;
  }
}

/* ── 시작 ───────────────────────────────── */

async function load() {
  await Promise.all([loadIndices(), loadNews(), loadSchedule()]);
  drawAll();
}

/* 세로 아이콘바에는 아직 이 화면 자리가 없어 아무것도 켜지지 않는다.
   ITEMS 는 components/frame.js 안에 있고 네 화면이 함께 쓴다.
   추가는 주식페이지_개발 에 넘겼다 (2026-09-16). */
mountVBar($('kh-vbar'), 'daily');
mountFootStrip($('kh-foot'));
startLiveLoop({ prices: true });

load();
setInterval(load, REFRESH_MS);
