/* ==========================================================================
   데일리분석 — 그리는 부분

   **한 벌만 둔다.** 전용 화면(`daily.html`)과 모달이 이 파일을 함께 쓴다
   (2026-09-21 지시 — "데일리분석 누르면 페이지 이동하는 게 아니고 모달로").

   `holdings/CLAUDE.md` 「모달이 원본이고, 목록·카드는 거기서 덜어낸 일부다」
   가 요구하는 모양이다. 두 벌로 두면 새 칸을 한쪽에만 넣게 되고, 그때
   눌러서 연 쪽이 빈다.

   ── 붙이는 쪽이 주는 것 ──

       root       본문이 들어갈 자리. 이 안에 머리말·카드·「지난 분석」을 만든다
       side       보낼 문안이 들어갈 자리 (없으면 안 그린다)
       onIndices  지수를 받았을 때 알려준다 — 페이지가 시세 띠를 갱신하는 자리

   ── 왜 `root.querySelector` 인가 ──

   전에는 `document.getElementById` 로 찾았다. 그대로 모달에 넣으면 문서에
   같은 `id` 가 두 벌 생겨 **먼저 나온 쪽**만 그려진다. 찾는 범위를 자기
   `root` 안으로 좁히면 그 문제가 없어진다.

   `id` 자체는 마크업에 그대로 둔다 — `tools/check-layout.py` 의 기준
   (`tools/layout-baseline.json`)이 칸을 그 이름으로 부르고, 룰이
   「칸 이름은 `id` 가 있으면 `id` 를 쓴다」 이기 때문이다. 빼면 기준이 깨진다.

   **다만 한 문서에 두 벌을 동시에 띄우지는 않는다.** 모달은 다른 화면에서
   열고, `daily.html` 에는 모달을 여는 자리를 두지 않는다. 띄우면 `id` 가
   겹친다 — 그리는 것은 멀쩡하지만 HTML 로서는 어긋난 상태가 된다.
   ========================================================================== */

import { collectSchedule } from './schedule.js';
import { openModal } from './modal.js';
import { apiFetch } from '../data/api.js';

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

/* 몇 시간치를 보여줄 것인가. 하루를 넘겨서 봐야 「어제 이슈」가 남는다
   (2026-09-21 지시 — "그전날 이슈를 놓치지 않게"). */
const NEWS_HOURS = 36;

/* 한 주제 칸에 몇 줄까지 펼쳐 둘 것인가. 나머지는 접는다 —
   80줄을 한 줄로 늘어놓으면 못 읽는다. */
const PER_TOPIC = 3;

/* 41개를 다 적으면 읽을 것만 늘어난다. 오른 쪽과 내린 쪽에서 넷씩만 뽑는다.
   pct 가 null 인 업종이 섞여 오는 날이 있어 (docs 참조) 걸러낸 뒤 센다. */
const SECTOR_TOP = 4;

/* ── 잔손질 ─────────────────────────────── */
/* 상태를 안 쓰므로 바깥에 둔다. 인스턴스마다 다시 만들 이유가 없다. */

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

/* ── 마크업 ─────────────────────────────── */
/* 전에는 `daily.html` 안에 있었다. 모달도 같은 것을 써야 해서 이리 옮겼다.
   **클래스와 `id` 를 그대로 옮긴다** — `daily.css` 와 레이아웃 기준이
   이 이름으로 걸려 있다. */

const BODY_HTML = `
    <header class="kh-dl-head">
      <div>
        <h1 class="kh-dl-title">데일리분석</h1>
        <p class="kh-dl-sub" id="kh-dl-sub">불러오는 중</p>
      </div>
      <!-- 미정: 아침 07:30 자동 발송은 아직 없다. 워커에 telegramSend 와 5분 Cron 이
           이미 있으므로 "07:30 인가 · 오늘 안 보냈나" 판단만 붙이면 된다.
           붙기 전까지 빨간 바탕으로 둔다 (CLAUDE.md 「아직 안 정해진 자리」). -->
      <span class="kh-dl-chip is-todo" id="kh-dl-send">발송 예정</span>
    </header>

    <div class="kh-dl-body">

        <!-- ① 주요 지수 -->
        <section class="kh-dl-card">
          <div class="kh-dl-ch">
            <b>주요 지수</b>
            <span class="kh-dl-why">국내는 오늘 마감 · 해외는 현지 마감</span>
            <span class="kh-dl-src">KIS</span>
          </div>
          <div class="kh-dl-idx" id="kh-dl-idx"></div>
        </section>

        <!-- ② 주도 섹터 -->
        <section class="kh-dl-card">
          <div class="kh-dl-ch">
            <b>주도 섹터</b>
            <span class="kh-dl-why">업종 지수 등락</span>
            <span class="kh-dl-src">KIS 업종별 시세</span>
          </div>
          <div class="kh-dl-sec" id="kh-dl-sec"></div>

          <!-- 미정: 미국 업종은 아직 못 붙였다. industry-theme (HHDFS76370000) 이
               후보인데 실측이 남았다. 국내만 붙은 상태라는 것이 화면에 보여야 한다. -->
          <div class="kh-dl-todo kh-dl-sec-todo">
            <b>미국 업종은 아직입니다</b>
            <span>국내(코스피·코스닥)만 붙었습니다. 미국 업종은 받아올 곳을
                  확정하는 중입니다.</span>
          </div>
        </section>

        <!-- 왼쪽 — 오늘 일정 · 중요 알림 / 오른쪽 — 오늘 뉴스
             (2026-09-21 지시 — "중요알람은 오늘뉴스의 왼쪽으로",
              뒤이어 "오늘 일정도 오늘뉴스 옆으로 이동해줘").
             왼쪽은 폭이 정해진 것들(일정 줄·낱말 칩)이고, 오른쪽 뉴스는
             제목이 길수록 좋아 남는 폭을 다 준다.
             좁은 화면에서는 아래 CSS 가 한 열로 되돌린다. -->
        <div class="kh-dl-row">
          <div class="kh-dl-col">
        <!-- 오늘 일정 -->
        <section class="kh-dl-card">
          <div class="kh-dl-ch">
            <b>오늘 일정</b>
            <span class="kh-dl-why">날짜가 미리 정해진 것만</span>
            <span class="kh-dl-src">market-calendar.json</span>
          </div>
          <div class="kh-dl-sch" id="kh-dl-sch"></div>
        </section>

        <!-- 중요 알림 — 무엇을 바로 받을지 정하는 자리 (2026-09-21 지시)

             재권님 말씀 — "중요한 데이터라고 정의할수 있는 공간도 있어야 할거같아",
             "정의 파일은 데일리 분석에다가 공간 만들어서 거기서 지정하거나 타이핑 하게".

             여기서 고친 것은 data/news-alerts.json 에 저장된다. 서버가 그 파일을
             읽어 판정하므로, 낱말을 넣으면 다음 수집부터 바로 걸린다. -->
        <section class="kh-dl-card">
          <div class="kh-dl-ch">
            <b>중요 알림</b>
            <span class="kh-dl-why">걸리면 하루 3번을 기다리지 않고 바로 보냅니다</span>
            <span class="kh-dl-src" id="kh-dl-al-src">news-alerts.json</span>
          </div>
          <div class="kh-dl-alerts" id="kh-dl-alerts">불러오는 중</div>
          <p class="kh-dl-al-note" id="kh-dl-al-note">
            낱말이 제목에 들어 있으면 걸립니다. <b>정규식도 됩니다</b> — 예: <code>수출 .*억달러</code>
          </p>
        </section>

          </div>
        <!-- 오늘 뉴스 -->
        <section class="kh-dl-card">
          <div class="kh-dl-ch">
            <b>오늘 뉴스</b>
            <span class="kh-dl-why">주제로 묶어 최근 순서로</span>
            <span class="kh-dl-src" id="kh-dl-news-src">경제지 RSS</span>
          </div>
          <div class="kh-dl-news" id="kh-dl-news"></div>
        </section>

        </div>


    </div>

`;

/* 「지난 분석」 — 2026-09-22 에 `BODY_HTML` 에서 뗐다.

   모달이 탭 셋(오늘 · 보낼 문안 · 지난 분석)이 되면서 이 블록이 **세 번째
   탭**으로 가야 하는데, 전용 화면에서는 지금처럼 본문 끝에 이어져야 한다.
   그래서 `side` 와 같은 꼴로 **받는 쪽이 자리를 정한다** —
   `past` 를 넘기면 거기에, 안 넘기면 본문 끝에 붙는다.

   **이 블록에는 `id` 가 하나도 없다.** `mountDaily` 가 `$(id)` 로 찾는
   열 개(kh-dl-al-note · kh-dl-alerts · kh-dl-idx · kh-dl-news ·
   kh-dl-news-src · kh-dl-sch · kh-dl-sec · kh-dl-sub · kh-dl-tg ·
   kh-dl-tg-cap) 중 여기 있는 것이 없어서, 어디로 옮겨도 조회가 안 끊긴다.
   양쪽에서 세어 확인했다 (2026-09-22 · 홈페이지_정리 교차). */
const PAST_HTML = `
    <h2 class="kh-dl-sect">지난 분석</h2>
    <p class="kh-dl-sect-s">30일이 지난 것은 자동으로 지워집니다</p>
    <!-- 미정: 위 「보관」 과 같은 자리다. 저장이 붙으면 여기에 카드가 쌓인다. -->
    <div class="kh-dl-todo is-wide">
      <b>아직 없습니다</b>
      <span>저장이 붙으면 날짜별 카드가 여기에 쌓입니다.</span>
    </div>
`;

/* 오른쪽 칸 — 이 화면에서는 관심종목 대신 보낼 문안을 둔다.
   본문과 같은 데이터로 만들기 때문에 나란히 놓고 보면 어긋난 곳이 바로 보인다. */
const SIDE_HTML = `
    <div class="kh-side-head">
      <b>텔레그램</b>
      <span class="kh-side-toggle" id="kh-dl-tg-w">아직 보내지 않았습니다</span>
    </div>
    <!-- 폰에서는 이 칸이 맨 위라 화면 제목보다 먼저 나온다.
         무슨 화면의 무슨 날짜인지 여기서 읽히게 적는다. -->
    <p class="kh-side-sub" id="kh-dl-tg-cap">폰에 이렇게 도착합니다</p>
    <div class="kh-dl-tg-b" id="kh-dl-tg">문안을 만드는 중…</div>

    <div class="kh-side-sec">
      <div class="kh-sched-h"><span>보관</span><span>30일</span></div>
      <!-- 미정: 날짜별로 쌓아 두는 자리가 아직 없다. 워커 D1 에 표를 하나
           만들면 되고, 30일이 지난 것은 지운다. -->
      <div class="kh-dl-todo">
        <b>아직 쌓이지 않습니다</b>
        <span>매일 아침 하나씩 저장하고 30일이 지나면 지우는 자리입니다.
              지금은 오늘 것만 그때그때 만들어 보여 줍니다.</span>
      </div>
    </div>
`;

/* ── 붙이기 ─────────────────────────────── */

/**
 * @param {HTMLElement} root              본문이 들어갈 자리
 * @param {object}      [opts]
 * @param {HTMLElement} [opts.side]       보낼 문안이 들어갈 자리
 * @param {HTMLElement|false} [opts.past]  「지난 분석」 이 들어갈 자리.
 *                                        **안 넘기면 본문 끝**(전용 화면),
 *                                        **`false` 면 아예 안 그린다**(모달 — 번호 탭이 대신)
 * @param {Function}    [opts.onIndices]  지수를 받았을 때 (시세 띠 갱신용)
 * @param {Function}    [opts.onHead]     머리에 얹을 값이 준비됐을 때.
 *                                        `{ big, stats }` 를 넘긴다 — 모달 머리가 쓴다.
 *                                        전용 화면은 머리가 없어 안 넘긴다
 * @returns {{ destroy: Function, reload: Function }}
 */
export function mountDaily(root, { side = null, past = null,
                                   onIndices = null, onHead = null } = {}) {
  if (!root) return { destroy() {}, reload() {} };

  root.insertAdjacentHTML('beforeend', BODY_HTML);
  if (side) side.insertAdjacentHTML('beforeend', SIDE_HTML);
  /* 「지난 분석」 — 자리를 받으면 거기에, 안 받으면 본문 끝에.
     **`false` 를 주면 아예 안 그린다** — 모달은 번호 탭이 그 자리를
     대신하므로 그릴 것이 없다 (2026-09-22).
     `$(id)` 로 찾는 것이 이 블록에 없어 어디로 가든 조회가 안 끊긴다. */
  if (past !== false) (past || root).insertAdjacentHTML('beforeend', PAST_HTML);

  /* 찾는 범위를 자기 자리 안으로 좁힌다. 문서 전체에서 찾지 않는 이유는
     파일 맨 위 주석에 있다. */
  const $ = (id) => root.querySelector(`#${id}`);
  const $side = (id) => (side ? side.querySelector(`#${id}`) : null);

  /* 인스턴스마다 따로 갖는다. 모듈 바깥에 두면 두 벌이 떴을 때 섞인다. */
  let indices = [];
  let issues = [];
  let newsMeta = null;
  let schedule = [];
  let sectors = [];
  let alertRules = null;

  /* 쌓아 둔 것을 읽었나, RSS 로 물러섰나. 화면이 그 차이를 적는다 */
  let stored = true;

  /* 멈출 수 있게 손잡이를 쥐고 있는다. 모달을 닫고도 계속 돌면 보이지도
     않는 칸 때문에 KIS 를 계속 부른다. */
  let timer = null;
  let dead = false;

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
    const box = $side('kh-dl-tg');
    if (box) box.textContent = buildTelegram();
    /* 폰에서는 이 칸이 화면 제목보다 위에 온다. 어느 날 것인지 여기 적는다. */
    const cap = $side('kh-dl-tg-cap');
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
    /* 받는 사이에 닫혔으면 그린 것이 갈 곳이 없다. 떨어져 나간 요소를
       건드리게 되고, 그 사이 또 부르는 것도 헛일이다. */
    if (dead) return;
    drawAll();
    drawAlerts();
    /* 시세 띠는 붙인 쪽이 갱신한다. 이 컴포넌트는 띠를 모른다 —
       모달에는 띠가 없기 때문이다. */
    if (onIndices) onIndices(indices);
    /* 모달 머리도 같은 자리에서 넘긴다. 값을 받은 뒤라야 채울 수 있고,
       전용 화면은 머리가 없어 안 넘긴다. */
    if (onHead) onHead(headValues());
  }

  /* ── 모달 머리에 얹을 값 ──
     시안이 「코스피 마감」 과 「주도 업종」 을 넣기로 했다 (2026-09-22).

     **받은 값이 없으면 `null` 을 돌려준다.** 뼈대가 `big` 과 `stats` 를
     둘 다 비우면 그 줄을 안 그린다 — 억지로 채우지 않는다. */
  function headValues() {
    const ix = (code) => indices.find((x) => x.code === code);
    const kospi = ix('KOSPI');
    const kosdaq = ix('KOSDAQ');

    const big = kospi ? {
      value: `KOSPI ${num(kospi.value, 2)}`,
      change: `${signed(kospi.change, 2)} ${pct(kospi.changePct)}`,
      changeCls: `kh-${tone(kospi.changePct)}`,
      note: todayLabel(),
    } : null;

    /* 업종은 **`pct` 가 없는 것을 거르고** 센다. 섞여 오는 날이 있다
       (`:60` 주석). 2026-09-22 실측으로는 41행에 null 이 0개였는데,
       「그날은 안 걸렸다」 이지 「안 온다」 가 아니라 거르기를 둔다. */
    const top = sectors.filter((x) => x.pct != null)
                       .sort((a, b) => b.pct - a.pct)[0];

    const stats = [];
    if (top) stats.push({ label: '주도 업종', value: `${top.name} ${pct(top.pct)}` });
    if (kosdaq) {
      stats.push({ label: 'KOSDAQ',
                   value: `${num(kosdaq.value, 2)} ${pct(kosdaq.changePct)}` });
    }
    if (kospi && kospi.up != null) {
      stats.push({ label: '오른 종목', value: `${kospi.up} / ${kospi.down}` });
    }

    return { big, stats: stats.length ? stats : null };
  }

  load();
  timer = setInterval(load, REFRESH_MS);

  return {
    /* 모달이 닫힐 때 부른다. 안 멈추면 보이지도 않는 칸 때문에 KIS 를
       계속 부른다 — 「최적화는 멈춘다가 아니라 늦춘다」 는 목록 폴링
       이야기이고, 이쪽은 칸 자체가 사라지므로 멈추는 것이 맞다. */
    destroy() {
      dead = true;
      if (timer) { clearInterval(timer); timer = null; }
    },
    reload: load,
  };
}

/* ── 모달로 열기 ─────────────────────────── */

/**
 * 데일리분석을 모달로 띄운다.
 *
 * 2026-09-21 지시 — "데일리분석 을 누르면 모델이 올라오고 그다음에 데일리
 * 분석이랑 필요한 메인페이지에 공간을 만든다". **여기까지가 1단계**다.
 * 메인에 칸을 만드는 2단계는 따로 지시를 받는다.
 */
export function openDailyModal() {
  let inst = null;

  /* ── 번호 탭 ──
     2026-09-22 지시 — 「지난분석은 따로 필요없고 데일리분석에 날별로 쌓여지고
     가장 최신이 모달 열었을 때 보여지면 될 거 같아. **1.2.3.... 이렇게 해서 보면**
     될 듯」.

     **지금은 하나뿐이다.** 날짜별 저장이 아직 없어서 오늘 것밖에 없다.
     저장이 붙으면 최신부터 1 · 2 · 3 … 열까지 늘어난다.

     **그때 `modal-head.js` 에 탭을 다시 그리는 길이 필요하다** — 지금은
     `setTabsNote` 만 있고 `setTabs` 가 없어, 목록을 받은 뒤에 탭을 못 늘린다.
     모달을 열기 전에 목록을 받아 두는 방법도 있는데, 그러면 누른 뒤 잠깐
     아무 일도 안 일어난다. 저장을 붙일 때 정한다. */
  const TABS = [{ id: 'today', label: '1' }];

  const m = openModal({
    label: '데일리분석',
    /* 본문 1100 + 보낼 문안 320 + 틈 14.
       320·14 는 `modal.css` 의 `--kh-drawer` · `--kh-gap` 과 같은 값이다 —
       종목 모달이 오른쪽 칸을 펼칠 때 늘어나는 폭이 그것이라, 같은 값을 쓰면
       두 모달의 오른쪽 칸 폭이 같아진다.

       **고정 px 로 둔다.** 탭을 바꿔도 폭이 안 변해야 한다. */
    width: 1434,
    head: {
      icon: '데',
      name: '데일리분석',
      sub: todayLabel(),
      caret: true,
      statCols: 3,
      tabs: TABS,
      tab: 'today',
      /* 아직 하나뿐이라는 것을 화면이 스스로 말한다. 빈 탭을 아홉 개
         만들어 두는 것보다 낫다 — 눌러도 아무 일이 없으면 고장으로 읽힌다. */
      tabsNote: '저장이 붙으면 열 장까지 쌓입니다',
      onTab(id) { showPane(id); },
    },
    onClose() { if (inst) { inst.destroy(); inst = null; } },
  });

  /* ── 2열 ──
     2026-09-22 지시 — 「화살표 없이 처음부터 텔레그램보여지게 **창 가로로 넓혀서**」.

     **`drawers` 를 안 쓴다.** 서랍은 손잡이를 눌러 여닫는 것인데, 여기는
     접는 기능 없이 늘 보여야 한다. 화살표도 안 만든다.

     **「보낼 문안」 은 탭에서 뺐다.** 서랍과 탭 양쪽에 두면 같은 내용이
     두 곳이 된다. */
  const wrap = document.createElement('div');
  wrap.className = 'kh-dl-wrap';

  const main = document.createElement('div');
  main.className = 'kh-dl-main';

  /* **`.kh-side` 를 안 붙인다.** `frame.css` 가 1280px 이하에서 그것을 숨기는데,
     되살리는 규칙(`daily.css` 의 `@media`)은 **`.kh-daily` 조상이 있어야** 한다.
     모달은 index · stock 에서도 열리므로 그 조상이 없다 (2026-09-22 확인).
     안쪽 모양(`.kh-side-head` · `.kh-dl-tg-b` …)은 최상위 선택자라 그대로 먹는다. */
  const msg = document.createElement('aside');
  msg.className = 'kh-dl-msg';
  msg.setAttribute('aria-label', '보낼 문안');

  wrap.append(main, msg);
  m.body.appendChild(wrap);

  /* 번호가 늘면 여기서 갈아끼운다. 지금은 하나라 할 일이 없다. */
  const panes = { today: main };
  function showPane(id) {
    for (const [k, el] of Object.entries(panes)) el.hidden = (k !== id);
  }

  inst = mountDaily(main, {
    side: msg,
    /* 「지난 분석」 칸은 없앴다 — 번호 탭이 그 자리다. */
    past: false,
    onHead({ big, stats }) {
      m.head.setBig(big);
      m.head.setStats(stats);
    },
  });
  return inst;
}

export function bindDailyMenu(root = document) {
  for (const a of root.querySelectorAll('a[href$="daily.html"]')) {
    /* 자기 화면이면 누를 일이 없다. 눌러도 모달을 띄우면 같은 것이 두 겹이 된다 */
    if (a.classList.contains('is-on')) continue;
    if (a.dataset.dlBound) continue;          /* 두 번 걸지 않는다 */
    a.dataset.dlBound = '1';

    a.addEventListener('click', (e) => {
      /* 새 탭·새 창으로 여는 것은 건드리지 않는다. 그 사람은 화면을
         원한 것이다. */
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      openDailyModal();
    });
  }
}
