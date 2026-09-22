/* ==========================================================================
   투자자 정보 · 매수매도 비율 (2026-09-18 지시)

   차트 옆 패널의 두 칸이 쓴다. 시안(temp/inv-plan.html)을 보시고 정하신 대로다.

     투자자 정보        **오늘 / 5일 둘 다.** 단추로 오간다
     매수 · 매도 비율    **막대만.** 글씨 없이, 높이는 시안의 1/3

   ── 매수는 위, 매도는 아래 ──

   재권님 지시 — "매도는 아래방향으로 나오게 해줘". 0선을 그어 위아래로
   가른다. 가로 막대로는 그 방향을 말할 수 없어 세로로 세웠다.

   ── 두 값의 성격이 다르다 ──

     투자자        **확정치**다 (docs/kis-sector-investor.md)
     매수·매도 비율  체결이 아니라 **지금 걸려 있는 주문**이다.
                    장이 끝나면 뜻이 옅어진다 — 그래서 화면에 적는다

   ── 장중에는 확정치가 없다 (2026-09-22 지시) ──

   재권님 말씀 — 「응 보고싶어」 · 「**우선되는거 연결해놓고 나중에 퀄업한다.
   출처만 알수있게 해놔**」.

   `/api/kis/investor` 는 장중에 오늘 줄을 `net: null` 로 준다 (11:03 · 12:00
   실측). **네이버는 대안이 못 된다** — 경로 셋이 전부 어제까지이고 다른
   이름 셋은 404 다 (2026-09-22 실측). 표본이 아니라 구조다.

   그래서 **종목별 추정가집계**(`/api/kis/investor-estimate`)로 메운다.

       장중    외국인 · 기관   KIS 추정가집계 (investor-trend-estimate)
               개인            **없다** — 응답에 그 필드가 아예 없다
       마감 뒤  셋 다          KIS 확정치 (investor)

   **개인이 모자란 채로 붙인다.** 재권님이 아시고 정하셨다 — 종목별로
   개인까지 주는 곳을 두 세션이 갈라 찾았는데 못 찾았다(네이버·다음·
   FnGuide·인베스팅·KRX·공공데이터포털).

   **그래서 출처를 화면에 적는다** (지시 — 「출처만 알수있게 해놔」).
   같은 칸에 성격이 다른 값이 섞이므로, 무엇이 가집계이고 무엇이 확정치인지
   보이지 않으면 읽을 수 없다.

   **하루 네 번만 바뀐다는 것도 적는다** — 외국인 09:30·11:20·13:20·14:30,
   기관 10:00·11:20·13:20·14:30 (±10분). 그 사이에는 값이 안 움직이는데,
   안 적으면 「멈춘 것 아니냐」 가 된다.
   ========================================================================== */

import { apiFetch } from '../data/api.js';
import { dirClass } from '../utils/format.js';

/* 「5일」 에서 보여줄 날 수. 30일치가 오지만 칸이 좁다 */
const DAYS_SHORT = 5;

/* 다시 받는 주기. 일별 자료라 장중에 한 번 바뀐다 — 서버 캐시도 60초다 */
const REFRESH_MS = 60 * 1000;

/* ── 장중 가집계는 **종목별로** 받는다 (2026-09-22) ──────────────
   처음에는 순매수 상위 목록(`investor-top`)으로 메웠는데, 그것은
   **상위 30줄에 든 종목만** 나온다(서로 다른 종목 47개가 한계 — `limit` 을
   100·200·500 으로 키워도 KIS 가 30줄까지만 준다). 재권님이 종목별 경로로
   정하셔서 그쪽으로 옮겼다 — **어느 종목이든 나온다.** */

const SIDES = [
  { key: 'person',  name: '개인' },
  { key: 'foreign', name: '외국인' },
  { key: 'inst',    name: '기관' },
];

/* 막대 한 칸. **자리를 인라인으로 준다** — 왼쪽/오른쪽을 CSS 클래스에
   맡겼더니 판 쪽이 오른쪽으로 뻗었다 (2026-09-21 실측). 방향이 값에 따라
   갈리는 자리라, 그리는 쪽에서 직접 정하는 편이 헷갈리지 않는다.

   가운데가 0이므로 한쪽이 최대 50% 다. */
function bar(v, w) {
  /* **칸을 좌우 반반으로 나눈다.** 왼쪽 반은 오른쪽 끝(가운데)에 붙여 자라고,
     오른쪽 반은 왼쪽 끝(가운데)에서 자란다. `position: absolute` 와 퍼센트로
     자리를 잡으려다 두 번 어긋나서, **자리 계산이 필요 없는 구조**로 바꿨다
     (2026-09-21). w 는 반쪽 안에서의 비율이라 최대 100 이다. */
  const pct = Math.min(100, w * 2).toFixed(1);
  const sell = v < 0 ? `<i class="dn" style="width:${pct}%"></i>` : '';
  const buy = v >= 0 ? `<i class="up" style="width:${pct}%"></i>` : '';
  return `<span class="kh-iv-half l">${sell}</span>`
       + `<span class="kh-iv-half r">${buy}</span>`;
}

/* 주 → 만주. 칸이 좁아 그대로 쓰면 자리를 다 먹는다 */
function man(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  const v = n / 10000;
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}만주`;
}

/**
 * 투자자 정보를 그린다.
 *   box  : 내용이 들어갈 칸
 *   tabs : 오늘/5일 단추 줄
 *
 * **id 로 찾지 않는다.** 첫 화면과 모달이 동시에 떠 있으면 같은 id 가 둘이
 * 되어 엉뚱한 칸을 칠한다 (stock-view.js 가 같은 이유로 root 안에서 찾는다).
 */
export function mountInvestor({ box, tabs } = {}) {
  if (!box) return { setCode() {}, destroy() {} };

  let code = null;
  let rows = null;          // 투자자 30일
  let view = 'today';       // today | days
  let timer = null;
  let seq = 0;              // 늦게 온 응답이 새 종목을 덮지 않게
  let top = null;           // 장중 가집계 — { foreign, inst }
  let topMiss = false;      // 상위 목록에 이 종목이 없다

  /* ── 받아오기 ── */
  async function load() {
    if (!code) return;
    const mine = ++seq;
    const iv = await get(`/api/kis/investor?code=${code}`);
    if (mine !== seq) return;              // 그새 종목이 바뀌었다
    rows = (iv && iv.ok && Array.isArray(iv.data)) ? iv.data : null;
    paint();

    /* **확정치가 없을 때만 가집계를 부른다.** 마감 뒤에는 부를 이유가 없다.
       먼저 확정치로 한 번 그리고, 가집계가 오면 다시 그린다 — 기다렸다가
       한 번에 그리면 장중에 칸이 오래 비어 있다. */
    if (!todayMissing()) { top = null; topMiss = false; return; }
    const est = await get(`/api/kis/investor-estimate?code=${code}`);
    if (mine !== seq) return;
    const l = est && est.ok && est.data ? est.data.latest : null;
    top = l && (l.foreign != null || l.inst != null) ? l : null;
    topMiss = !top;
    paint();
  }

  /** 오늘 줄의 확정치가 아직 안 나왔나 (장중) */
  function todayMissing() {
    const d = rows && rows[0];
    if (!d) return false;
    return SIDES.every((sd) => (d[sd.key] || {}).net == null);
  }

  async function get(url) {
    try {
      const r = await apiFetch(url, { cache: 'no-store' });
      if (!r || !r.ok) return null;
      return await r.json();
    } catch { return null; }
  }

  /* ── 투자자 ── */
  function paint() {
    if (!rows || !rows.length) {
      box.innerHTML = '<span class="kh-mut">불러오지 못했습니다</span>';
    } else if (view === 'today') {
      box.innerHTML = paintToday(rows[0]);
    } else {
      box.innerHTML = paintDays(rows.slice(0, DAYS_SHORT));
    }
    if (tabs) {
      tabs.querySelectorAll('[data-view]').forEach((b) =>
        b.classList.toggle('is-active', b.dataset.view === view));
    }
  }

  /* **가운데가 0이고 양쪽으로 뻗는다** (2026-09-21 지시 —
     "중간지점에서 사는게 많으면 빨간색으로 오른쪽으로 보이고
      파는게 많으면 왼쪽으로 보이고 파란색").

     세로로 세우던 것을 눕혔고(칸이 1/3 로 줄어 세로로는 몇 px 밖에 안 남는다),
     0선을 **가운데**에 두었다. 길이와 방향을 함께 읽는다 — 색만으로 방향을
     말하면 빨강·파랑을 알고 있어야 하지만, **어느 쪽으로 뻗었는지는 그냥 보인다.**

     한쪽이 최대 50% 다. 그래서 `w` 는 100 이 아니라 50 을 곱한다. */
  function paintToday(d) {
    /* **`|| 0` 을 쓰지 않는다** (2026-09-21). 서버는 아직 집계 전이면
       `net: null` 을 준다 — `kis_proxy.py` 의 `_num()` 이 숫자로 못 바꾸면
       `None` 을 돌려주고 그대로 나간다. `|| 0` 으로 받으면 그 `null` 이
       **`0.0만주` 로 둔갑해** 「0주 거래됐다」 와 구분되지 않는다.

       `man()` 과 `dirClass()` 에는 이미 `null → 「—」 · 회색` 이 있는데,
       부르는 쪽이 먼저 0 으로 바꿔서 **죽은 코드**였다.

       **raw 와 숫자를 나눈다.** 글자·색은 raw 가 필요하고(`null` 이면 「—」),
       막대 폭은 숫자여야 한다(`null` 이면 `NaN` 이 된다). */
    /* **확정치가 없으면 가집계로 메운다** (2026-09-22 지시).
       `top` 에는 외국인·기관만 있다 — 개인은 그 목록에 아예 없어 `null`
       그대로 두고 「—」 가 나간다. */
    const prov = todayMissing() && !!top;
    const net = (s) => {
      const v = (d[s.key] || {}).net;
      if (v != null) return v;
      return prov && top[s.key] != null ? top[s.key] : null;
    };
    const max = Math.max(...SIDES.map((s) => Math.abs(net(s) ?? 0))) || 1;
    const rows2 = SIDES.map((s) => {
      const v = net(s);                      // null 일 수 있다 — 글자·색용
      const n = v ?? 0;                      // 숫자 — 막대 폭·방향용
      const w = Math.abs(n) / max * 50;      // 가운데에서 한쪽으로 최대 50%
      return `<div class="kh-iv-r2">
        <span class="kh-iv-n2">${s.name}</span>
        <span class="kh-iv-v2 ${dirClass(v)}">${man(v)}</span>
        <span class="kh-iv-bar">${bar(n, w)}</span></div>`;
    }).join('');
    return `<div class="kh-iv-rows">${rows2}</div>
      <div class="kh-iv-note">${todayNote(d)}</div>`;
  }

  /* **출처를 적는다** (2026-09-22 지시 — 「출처만 알수있게 해놔」).
     같은 칸에 성격이 다른 값이 섞이므로, 무엇이 가집계인지 보이지 않으면
     읽을 수 없다. 「값이 없다」 와 「상위 목록에 없다」 도 갈라 적는다. */
  function todayNote(d) {
    const dir = '<b class="kh-up">오른쪽 순매수</b> · <b class="kh-down">왼쪽 순매도</b>';
    if (!todayMissing()) {
      return `${dateText(d.date)} 확정 · 한국투자증권 · ${dir}`;
    }
    if (top) {
      /* **시각을 적지 않는다.** 응답에 시각이 없다 — `bsop_hour_gb` 는 회차
         번호일 뿐이고, 회차와 시각의 대응은 아직 못 박지 않았다.
         대신 「하루 네 번만 바뀐다」 를 적어 **멈춘 것으로 오해하지 않게** 한다. */
      return `장중 <b>추정가집계</b> · 한국투자증권 ·
        <span class="kh-mut">하루 네 번 갱신 · 개인은 마감 뒤</span> · ${dir}`;
    }
    if (topMiss) {
      return `장중 가집계를 <b>못 받았습니다</b> ·
        <span class="kh-mut">마감 뒤 확정치로 채워집니다</span>`;
    }
    return `장중 확정치는 <b>마감 뒤</b>에 나옵니다 ·
      <span class="kh-mut">가집계를 불러오는 중</span>`;
  }

  function paintDays(days) {
    let max = 1;
    days.forEach((d) => SIDES.forEach((s) => {
      max = Math.max(max, Math.abs((d[s.key] || {}).net || 0));
    }));
    /* 5일도 가로 막대다. **합계가 아니라 닷새를 더한 값**을 보여준다 —
       오늘 것만 보면 하루 흐름이고, 닷새를 더하면 추세가 읽힌다. */
    const lines = SIDES.map((s) => {
      /* **여기서는 `|| 0` 이 맞다** — 더하는 자리라 `null` 을 그냥 두면
         합이 통째로 `NaN` 이 된다. 다만 **닷새가 전부 `null` 이면**
         합이 0 이 되어 「0주」 처럼 보이므로, 그때만 「—」 로 낸다. */
      const vals = days.map((d) => (d[s.key] || {}).net);
      const any = vals.some((v) => v != null);
      const sum = vals.reduce((a2, v) => a2 + (v || 0), 0);
      const shown = any ? sum : null;        // 글자·색용
      const w = Math.min(50, Math.abs(sum) / (max * days.length) * 50);
      return `<div class="kh-iv-r2">
        <span class="kh-iv-n2">${s.name}</span>
        <span class="kh-iv-v2 ${dirClass(shown)}">${man(shown)}</span>
        <span class="kh-iv-bar">${bar(sum, w)}</span></div>`;
    }).join('');
    /* **오른쪽 숫자는 오늘 값이다** — 5일 합계가 아니다 (2026-09-18 지적
       — "우측에 있는 수치는 5일치를합친건가?"). 막대는 5일이고 숫자는
       오늘이라 갈리므로 그 사실을 적는다. */
    return `<div class="kh-iv-rows">${lines}</div>
      <div class="kh-iv-note">최근 ${days.length}일을 <b>더한 값</b>입니다 ·
        한국투자증권 확정치</div>`;
  }

  function dateText(d) {
    if (!d || d.length !== 8) return '';
    return `${d.slice(4, 6)}.${d.slice(6)}`;
  }

  /* ── 보는 것을 바꿔도 자리는 그대로다 ──

     루트 CLAUDE.md 의 그 룰이다. 칸 높이는 css/home.css 가 잡아 두었는데,
     **주석과 CSS 만으로는 지켜지는지 알 수 없다.** 차트가 세로 범위를
     재서 견주는 것(`chart.js` 의 checkScale)과 같은 방식으로, 바꾸기 직전
     높이를 재 두고 바뀌면 화면에 빨간 표시를 낸다.

     1px 도 안 봐준다 — 여기서 움직이면 아래 칸이 통째로 밀린다. */
  const HEIGHT_TOL = 1;

  function boxHeight() {
    return Math.round(box.getBoundingClientRect().height);
  }

  function checkHeight(before) {
    const sec = box.closest('.kh-iv-s');
    if (!sec) return;
    const old = sec.querySelector('.kh-scale-warn');
    if (old) old.remove();
    const now = boxHeight();
    if (Math.abs(now - before) <= HEIGHT_TOL) return;

    const tag = document.createElement('div');
    tag.className = 'kh-scale-warn';
    tag.textContent = `칸이 움직임 — ${before} → ${now}px`;
    sec.appendChild(tag);
  }

  /* ── 단추 ── */
  if (tabs) {
    tabs.addEventListener('click', (e) => {
      const b = e.target.closest('[data-view]');
      if (!b || b.dataset.view === view) return;
      const before = boxHeight();
      view = b.dataset.view;
      paint();
      checkHeight(before);
    });
  }

  timer = setInterval(() => { if (!document.hidden) load(); }, REFRESH_MS);

  return {
    setCode(next) {
      if (!next || next === code) return;
      code = next;
      top = null; topMiss = false;
      rows = null;
      box.innerHTML = '<span class="kh-mut">불러오는 중</span>';
      load();
    },
    destroy() { if (timer) clearInterval(timer); },
  };
}
