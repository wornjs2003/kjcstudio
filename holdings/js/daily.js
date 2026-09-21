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
import { apiFetch } from './data/api.js';

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
let newsMeta = null;

/* 쌓아 둔 것을 읽었나, RSS 로 물러섰나. 화면이 그 차이를 적는다 */
let stored = true;

/* 몇 시간치를 보여줄 것인가. 하루를 넘겨서 봐야 「어제 이슈」가 남는다
   (2026-09-21 지시 — "그전날 이슈를 놓치지 않게"). */
const NEWS_HOURS = 36;

/* 한 주제 칸에 몇 줄까지 펼쳐 둘 것인가. 나머지는 접는다 —
   80줄을 한 줄로 늘어놓으면 못 읽는다. */
const PER_TOPIC = 3;
let schedule = [];
let sectors = [];

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
    const r = await apiFetch('/api/kis/indices', { cache: 'no-store' });
    if (!r || !r.ok) throw new Error(r.status);
    const b = await r.json();
    indices = Array.isArray(b.data) ? b.data : [];
  } catch {
    indices = [];          /* 화면에 「받지 못했습니다」 가 남는다 */
  }
}

/* 업종 등락률. 파라미터 없이 부르면 코스피·코스닥이 함께 온다
   (2026-09-18 실측 — 41개 · 1.1초). tr_id 와 필드 이름은
   holdings/docs/kis-sector-investor.md 에 실측으로 적혀 있다. */
async function loadSectors() {
  try {
    const r = await apiFetch('/api/kis/sectors', { cache: 'no-store' });
    if (!r || !r.ok) throw new Error(r.status);
    const b = await r.json();
    sectors = Array.isArray(b.data) ? b.data : [];
  } catch {
    sectors = [];
  }
}

/* **쌓아 둔 것을 읽는다** (2026-09-21 지시 — "받는족족 쌓아놓고 데일리분석에
   계속 쌓아지게").

   전에는 `/api/news/feed` 로 **그때 RSS 를 받아** 그렸다. 화면을 열 때마다
   파싱해서 느렸고(0.62초), 화면을 안 열고 있으면 그 사이 기사는 사라졌다.
   이제 서버가 5분마다 쌓아 두고 **같은 사건끼리 묶어** 둔다 — 화면은 읽기만
   한다(0.005초 실측).

   한 줄이 묶음 하나다 — 대표 기사 + `more`(같은 사건을 쓴 기사 수). */
async function loadNews() {
  try {
    const r = await apiFetch(`/api/news/stored?hours=${NEWS_HOURS}`, { cache: 'no-store' });
    if (!r || !r.ok) throw new Error(r.status);
    const b = await r.json();
    const rows = Array.isArray(b.data) ? b.data : [];
    /* **빈 것도 물러선다.** 확인용 서버(--slow)는 뉴스 수집을 안 돌려서
       표가 비어 있다. 「쌓인 것이 없다」 를 「뉴스가 없다」 로 보여주면
       그 서버에서는 이 칸이 영영 빈다 (2026-09-21 실측). */
    if (!rows.length) throw new Error('쌓인 것이 없습니다');
    issues = rows;
    newsMeta = b.meta || null;
    stored = true;
    return;
  } catch { /* 아래에서 물러선다 */ }

  /* **쌓아 둔 것이 없으면 그때 RSS 를 받는다** (2026-09-21).

     `stored` 는 이 PC 의 market.db 를 읽는 자리라 **워커에는 넣을 수 없다.**
     배포본에서 열면 404 이고, 그대로 두면 뉴스 칸이 통째로 빈다 —
     쌓기를 붙이기 전에는 `feed` 로 잘 나오던 자리다. 그래서 물러선다.

     물러선 쪽은 **묶음이 없다.** 서버가 쌓을 때 묶는 것이라 그때그때 받은
     것에는 `more` 가 없다. 화면이 그 사실을 적는다. */
  try {
    const r = await apiFetch('/api/news/feed', { cache: 'no-store' });
    if (!r || !r.ok) throw new Error(r && r.status);
    const b = await r.json();
    issues = (b.data && Array.isArray(b.data.issues)) ? b.data.issues : [];
    newsMeta = null;
    stored = false;
  } catch {
    issues = [];
    newsMeta = null;
    stored = false;
  }
}

async function loadSchedule() {
  try {
    /* 오늘과 앞으로 사흘치만. 데일리분석은 「그날」 이 중심이라 2주는 길다.
       돌려주는 것은 배열이 아니라 { rows, stale, calOk, … } 다.
       배열인 줄 알고 그대로 받았다가 schedule.filter 에서 터졌다 — 화면은
       멀쩡한데 문안만 비어 있었다 (2026-09-16). */
    const got = await collectSchedule({ days: 3 });
    schedule = Array.isArray(got) ? got : (got && got.rows) || [];
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
    if (!r || !r.ok) return;
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

/* ── ④ 주도 섹터 ────────────────────────── */

/* 41개를 다 적으면 읽을 것만 늘어난다. 오른 쪽과 내린 쪽에서 넷씩만 뽑는다.
   pct 가 null 인 업종이 섞여 오는 날이 있어 (docs 참조) 걸러낸 뒤 센다. */
const SECTOR_TOP = 4;

function sectorSides() {
  const rows = sectors.filter((s) => typeof s.pct === 'number');
  const byPct = [...rows].sort((a, b) => b.pct - a.pct);
  return {
    up: byPct.slice(0, SECTOR_TOP).filter((s) => s.pct > 0),
    down: byPct.slice(-SECTOR_TOP).reverse().filter((s) => s.pct < 0),
  };
}

function drawSectors() {
  const box = $('kh-dl-sec');
  if (!box) return;

  if (!sectors.length) {
    box.innerHTML = '<div class="kh-dl-todo"><b>업종을 받지 못했습니다</b>'
      + '<span>중계 서버가 꺼져 있으면 이 칸이 비어 있습니다.</span></div>';
    return;
  }

  const { up, down } = sectorSides();

  const col = (title, rows, toneName) => {
    if (!rows.length) {
      return `<div class="kh-dl-sec-col">
        <div class="kh-dl-sec-h">${esc(title)}</div>
        <div class="kh-dl-sec-row"><span class="kh-dl-sec-n kh-dl-flat">없습니다</span></div>
      </div>`;
    }
    return `<div class="kh-dl-sec-col">
      <div class="kh-dl-sec-h kh-dl-${toneName}">${esc(title)}</div>
      ${rows.map((s) => `<div class="kh-dl-sec-row">
        <span class="kh-dl-sec-m">${esc(s.market === 'KOSDAQ' ? '코스닥' : '코스피')}</span>
        <span class="kh-dl-sec-n">${esc(s.name)}</span>
        <span class="kh-dl-sec-p kh-dl-${tone(s.pct)}">${pct(s.pct)}</span>
      </div>`).join('')}
    </div>`;
  };

  box.innerHTML = col('오른 업종', up, 'up') + col('내린 업종', down, 'down');
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
  if (src) {
    if (stored) {
      const total = (newsMeta && newsMeta.total && newsMeta.total.count) || issues.length;
      src.textContent = `쌓아 둔 것 ${total}건 · 최근 ${NEWS_HOURS}시간 ${issues.length}묶음`;
    } else {
      /* 배포본에서 열면 이쪽이다 — 쌓는 것은 이 PC 의 서버가 한다 */
      src.textContent = `경제지 RSS ${issues.length}건 · 묶음은 이 PC 에서만 보입니다`;
    }
  }

  /* **주제별로 칸을 나눈다** (2026-09-21 지시 — "뉴스별로 정리해서 보면").
     한 줄로 길게 늘어놓으면 80줄이 되어 무슨 일이 있었는지가 안 읽힌다.
     칸마다 위에서 PER_TOPIC 줄만 펼치고 나머지는 접는다. */
  const byTopic = new Map();
  for (const n of issues) {
    const key = n.topicLabel || '기타';
    if (!byTopic.has(key)) byTopic.set(key, []);
    byTopic.get(key).push(n);
  }
  const topics = [...byTopic.entries()].sort((a, b) => b[1].length - a[1].length);

  box.innerHTML = topics.map(([label, rows]) => {
    const head = rows.slice(0, PER_TOPIC);
    const rest = rows.slice(PER_TOPIC);
    const line = (n) => `
      <a class="kh-dl-news-row" href="${esc(n.link)}" target="_blank" rel="noopener">
        <span>
          <span class="kh-dl-news-t">${n.alert ? `<i class="kh-dl-hot">${esc(n.alert)}</i>` : ''}${esc(n.title)}</span>
          <span class="kh-dl-news-m">${esc(n.source || '')} · ${esc(hhmm(n.at))}${
            n.more ? ` · <b>외 ${n.more}건</b>` : ''}</span>
        </span>
      </a>`;
    return `
      <div class="kh-dl-topic-box">
        <div class="kh-dl-topic-h"><span class="kh-dl-topic">${esc(label)}</span>
          <i>${rows.length}묶음</i></div>
        ${head.map(line).join('')}
        ${rest.length ? `<details class="kh-dl-more">
          <summary>나머지 ${rest.length}묶음</summary>${rest.map(line).join('')}</details>` : ''}
      </div>`;
  }).join('');
}

/* ── ④ 중요 알림 규칙 ──────────────────────

   **무엇을 바로 받을지 재권님이 여기서 정하신다** (2026-09-21 지시 —
   "정의 파일은 데일리 분석에다가 공간 만들어서 거기서 지정하거나 타이핑 하게").

   저장되는 곳은 `data/news-alerts.json` 이고, 서버가 그 파일을 읽어 판정한다.
   **이 PC 의 서버에서만 고칠 수 있다** — 배포본(워커)에는 파일을 쓸 곳이 없다.
   그래서 저장이 안 되면 그 사실을 칸에 적는다. */

let alertRules = null;

async function loadAlerts() {
  try {
    const r = await apiFetch('/api/news/alerts', { cache: 'no-store' });
    if (!r || !r.ok) throw new Error(r.status);
    const b = await r.json();
    alertRules = (b.data && Array.isArray(b.data['즉시알림'])) ? b.data : null;
  } catch {
    alertRules = null;
  }
}

async function saveAlerts() {
  const note = $('kh-dl-al-note');
  try {
    const r = await apiFetch('/api/news/alerts', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(alertRules),
    });
    if (!r || !r.ok) throw new Error(r && r.status);
    if (note) note.innerHTML = '<b>저장했습니다.</b> 다음 수집(5분 안)부터 걸립니다.';
  } catch {
    if (note) {
      note.innerHTML = '<b>저장하지 못했습니다.</b> 이 PC 의 서버에서만 고칠 수 있습니다'
        + ' — 배포본에는 파일을 쓸 곳이 없습니다.';
    }
  }
}

function drawAlerts() {
  const box = $('kh-dl-alerts');
  if (!box) return;
  if (!alertRules) {
    /* 배포본에서 열면 여기다 — 규칙 파일은 이 PC 에만 있고 워커에는 없다.
       「못 받았다」 로만 적으면 고장으로 읽힌다 (2026-09-21). */
    box.innerHTML = '<div class="kh-dl-todo"><b>이 PC 에서만 보입니다</b>'
      + '<span>중요 낱말은 이 PC 의 서버가 파일로 들고 있습니다. '
      + '배포본에는 파일을 쓸 곳이 없어 규칙을 보여주거나 고칠 수 없습니다.</span></div>';
    return;
  }

  box.innerHTML = alertRules['즉시알림'].map((rule, ri) => `
    <div class="kh-dl-al-rule${rule['켬'] === false ? ' is-off' : ''}">
      <div class="kh-dl-al-h">
        <label><input type="checkbox" data-rule="${ri}"
          ${rule['켬'] === false ? '' : 'checked'}> ${esc(rule['이름'] || '이름 없음')}</label>
        <i>${(rule['제목에'] || []).length}개</i>
      </div>
      <div class="kh-dl-al-words">
        ${(rule['제목에'] || []).map((w, wi) => `
          <span class="kh-dl-al-w">${esc(w)}
            <button type="button" data-del="${ri}:${wi}" title="빼기">×</button></span>`).join('')}
        <input class="kh-dl-al-add" data-add="${ri}" placeholder="낱말을 적고 Enter">
      </div>
    </div>`).join('');

  box.querySelectorAll('[data-rule]').forEach((el) => {
    el.addEventListener('change', () => {
      alertRules['즉시알림'][Number(el.dataset.rule)]['켬'] = el.checked;
      drawAlerts(); saveAlerts();
    });
  });
  box.querySelectorAll('[data-del]').forEach((el) => {
    el.addEventListener('click', () => {
      const [ri, wi] = el.dataset.del.split(':').map(Number);
      alertRules['즉시알림'][ri]['제목에'].splice(wi, 1);
      drawAlerts(); saveAlerts();
    });
  });
  box.querySelectorAll('[data-add]').forEach((el) => {
    el.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const word = el.value.trim();
      if (!word) return;
      alertRules['즉시알림'][Number(el.dataset.add)]['제목에'].push(word);
      drawAlerts(); saveAlerts();
    });
  });
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
    /* 실적 발표는 하루에 여러 건이 몰린다. 다섯 줄을 그대로 적으면 폰에서
       문안이 화면 하나를 넘어간다. 시장 전체가 보는 것만 줄로 적고
       나머지는 개수로 묶는다. */
    const big = todayEvents.filter((e) => e.kind !== '실적');
    const ir = todayEvents.filter((e) => e.kind === '실적');
    for (const e of big) {
      L.push(`· ${e.title}${e.ongoing ? ' (진행 중)' : ''}`);
      if (e.note) L.push(`  → ${e.note}`);
    }
    if (ir.length) {
      const names = ir.slice(0, 2).map((e) => e.title.replace(/\s*기업설명회$/, ''));
      L.push(`· 기업설명회 ${ir.length}건 — ${names.join(' · ')}`
        + (ir.length > names.length ? ` 외 ${ir.length - names.length}` : ''));
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
      const t = it.title.length > 34 ? `${it.title.slice(0, 33)}…` : it.title;
      L.push(`· ${it.topicLabel ? `${it.topicLabel} — ` : ''}${t}${it.more ? ` (외 ${it.more}건)` : ''}`);
      if (++n >= 3) break;
    }
  }

  if (sectors.length) {
    const { up, down } = sectorSides();
    const one = (s) => `${s.name} ${pct(s.pct)}`;
    L.push('', '주도 섹터 (국내)');
    if (up.length) L.push(`· 오름 — ${up.slice(0, 3).map(one).join(' · ')}`);
    if (down.length) L.push(`· 내림 — ${down.slice(0, 3).map(one).join(' · ')}`);
  }

  /* 화면에는 빨간 자국으로 남아 있는 칸들이다. 문안에서 통째로 빼면 폰에서는
     무엇이 빠졌는지 알 수 없다. 붙으면 이 줄을 지운다. */
  L.push('', '연결 예정', '· 미국 업종', '· 야간선물 · 다우존스');

  L.push('', '전문 보기 › thekjcstudio.com/holdings/daily.html');
  return L.join('\n');
}

function drawTelegram() {
  const box = $('kh-dl-tg');
  if (box) box.textContent = buildTelegram();
  /* 폰에서는 이 칸이 화면 제목보다 위에 온다. 어느 날 것인지 여기 적는다. */
  const cap = $('kh-dl-tg-cap');
  if (cap) cap.textContent = `데일리분석 ${todayLabel()} · 폰에 이렇게 도착합니다`;
}

/* ── 그리기 ─────────────────────────────── */

function drawAll() {
  /* 한 칸이 터져도 나머지는 그려지게 따로따로 부른다.
     전에는 drawTelegram 이 맨 끝이라, 앞에서 무엇이 잘못되면 문안만 조용히
     비어 있고 다른 칸은 멀쩡해 보였다. 어느 칸이 문제인지 알 수 없다. */
  for (const [name, fn] of [
    ['일정', drawSchedule], ['지수', drawIndices],
    ['섹터', drawSectors], ['뉴스', drawNews], ['문안', drawTelegram],
  ]) {
    try { fn(); } catch (e) { console.error(`[데일리분석] ${name} 칸을 그리지 못했습니다`, e); }
  }

  const sub = $('kh-dl-sub');
  if (sub) {
    sub.textContent = `${todayLabel()} · 그날의 일정 · 지수 · 뉴스를 한 장으로 모읍니다`;
  }
}

/* ── 시작 ───────────────────────────────── */

async function load() {
  await Promise.all([loadIndices(), loadNews(), loadSchedule(), loadSectors(),
                     loadAlerts()]);
  drawAll();
  drawAlerts();
  /* 하단 띠는 mountFootStrip 이 돌려준 손잡이로만 갱신된다. 손잡이를 버리면
     mount 때 그린 「지수 불러오는 중」 에서 영영 안 바뀐다 — 실제로 그랬다
     (2026-09-18). home.js·stock.js 는 받아서 쓰고 있었다. */
  foot.update(indices);
}

/* 세로 아이콘바에는 아직 이 화면 자리가 없어 아무것도 켜지지 않는다.
   ITEMS 는 components/frame.js 안에 있고 네 화면이 함께 쓴다.
   추가는 주식페이지_개발 에 넘겼다 (2026-09-16). */
mountVBar($('kh-vbar'), 'daily');
const foot = mountFootStrip($('kh-foot'));
startLiveLoop({ prices: true });

load();
setInterval(load, REFRESH_MS);
