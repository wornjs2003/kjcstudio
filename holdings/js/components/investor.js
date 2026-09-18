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

   순매수 상위 목록(investor-top)만 가집계인데, 그것은 여기서 안 쓴다.
   ========================================================================== */

import { apiFetch } from '../data/api.js';
import { dirClass } from '../utils/format.js';

/* 「5일」 에서 보여줄 날 수. 30일치가 오지만 칸이 좁다 */
const DAYS_SHORT = 5;

/* 다시 받는 주기. 일별 자료라 장중에 한 번 바뀐다 — 서버 캐시도 60초다 */
const REFRESH_MS = 60 * 1000;

const SIDES = [
  { key: 'person',  name: '개인' },
  { key: 'foreign', name: '외국인' },
  { key: 'inst',    name: '기관' },
];

/* 주 → 만주. 칸이 좁아 그대로 쓰면 자리를 다 먹는다 */
function man(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  const v = n / 10000;
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}만주`;
}

export function mountInvestor(root) {
  if (!root) return { setCode() {}, destroy() {} };

  const box = root.querySelector('#kh-iv-box');
  const tabs = root.querySelector('#kh-iv-tabs');
  const bsBox = root.querySelector('#kh-bs-box');
  if (!box) return { setCode() {}, destroy() {} };

  let code = null;
  let rows = null;          // 투자자 30일
  let asking = null;        // 호가
  let view = 'today';       // today | days
  let timer = null;
  let seq = 0;              // 늦게 온 응답이 새 종목을 덮지 않게

  /* ── 받아오기 ── */
  async function load() {
    if (!code) return;
    const mine = ++seq;
    const [iv, ak] = await Promise.all([get(`/api/kis/investor?code=${code}`),
                                        get(`/api/kis/asking?code=${code}`)]);
    if (mine !== seq) return;              // 그새 종목이 바뀌었다
    rows = (iv && iv.ok && Array.isArray(iv.data)) ? iv.data : null;
    asking = (ak && ak.ok && ak.data) ? ak.data : null;
    paint();
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
    paintAsking();
  }

  function paintToday(d) {
    const max = Math.max(...SIDES.map((s) => Math.abs((d[s.key] || {}).net || 0))) || 1;
    const bars = SIDES.map((s) => {
      const v = (d[s.key] || {}).net || 0;
      const h = Math.abs(v) / max * 46;      // 0선 위아래로 각각 46% 까지
      return `<div class="kh-iv-c">
        <span class="kh-iv-v ${dirClass(v)}">${man(v)}</span>
        <span class="kh-iv-box"><i class="${v >= 0 ? 'up' : 'dn'}" style="height:${h}%"></i></span>
        <span class="kh-iv-n">${s.name}</span></div>`;
    }).join('');
    return `<div class="kh-iv-bars">${bars}</div>
      <div class="kh-iv-note">${dateText(d.date)} 하루치 · <b class="kh-up">위가 순매수</b>
        · <b class="kh-down">아래가 순매도</b></div>`;
  }

  function paintDays(days) {
    let max = 1;
    days.forEach((d) => SIDES.forEach((s) => {
      max = Math.max(max, Math.abs((d[s.key] || {}).net || 0));
    }));
    const lines = SIDES.map((s) => {
      const now = (days[0][s.key] || {}).net || 0;
      /* 받은 순서가 최신부터라 뒤집어 그린다 — 오른쪽 끝이 오늘이다 */
      const spark = days.slice().reverse().map((d) => {
        const v = (d[s.key] || {}).net || 0;
        return `<i class="${v >= 0 ? 'up' : 'dn'}" style="height:${Math.abs(v) / max * 46}%"></i>`;
      }).join('');
      return `<div class="kh-iv-r">
        <span class="kh-iv-rn">${s.name}</span>
        <span class="kh-iv-sp"><span class="zero"></span>${spark}</span>
        <span class="kh-iv-rv ${dirClass(now)}">${man(now)}</span></div>`;
    }).join('');
    /* **오른쪽 숫자는 오늘 값이다** — 5일 합계가 아니다 (2026-09-18 지적
       — "우측에 있는 수치는 5일치를합친건가?"). 막대는 5일이고 숫자는
       오늘이라 갈리므로 그 사실을 적는다. */
    return `<div class="kh-iv-days">${lines}</div>
      <div class="kh-iv-note">막대는 최근 ${days.length}일 · 오른쪽 끝이 오늘
        · <b>숫자는 오늘 값</b> (5일 합계가 아닙니다)</div>`;
  }

  function dateText(d) {
    if (!d || d.length !== 8) return '';
    return `${d.slice(4, 6)}.${d.slice(6)}`;
  }

  /* ── 매수 · 매도 비율 ── */
  function paintAsking() {
    if (!bsBox) return;
    if (!asking || asking.buyPct == null) {
      bsBox.innerHTML = '<span class="kh-mut">불러오지 못했습니다</span>';
      return;
    }
    const buy = asking.buyPct;
    const sell = Math.round((100 - buy) * 10) / 10;
    /* 막대 안에는 글씨를 안 넣는다(높이가 7px 라 안 들어간다). **퍼센트는
       막대 위 줄에 적는다** (2026-09-18 지시 — "매수 매도비율도 퍼센티지가
       있으면좋을거같음").

       **기간이 없는 값이다** — 투자자 정보와 달리 「오늘」도 「5일」도
       아니고 지금 이 순간 걸려 있는 주문이다. 그래서 「지금」이라고 적는다
       (지시 — "매수매도는 하루인지 5일인지 인지가 안됨"). */
    bsBox.innerHTML =
      `<div class="kh-bs-h">
         <span>매수 · 매도 비율<b class="kh-bs-when">지금</b></span>
         <span class="kh-bs-pct"><b class="kh-up">${buy}%</b>
           <i>·</i><b class="kh-down">${sell}%</b></span>
       </div>
       <div class="kh-bs" title="매수 ${buy}% · 매도 ${sell}%">
         <i class="buy" style="width:${buy}%"></i>
         <i class="sell" style="width:${sell}%"></i>
       </div>
       <div class="kh-iv-note">지금 <b>걸려 있는 주문</b>입니다 — 체결된 것이 아닙니다</div>`;
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
      rows = null; asking = null;
      box.innerHTML = '<span class="kh-mut">불러오는 중</span>';
      if (bsBox) bsBox.innerHTML = '<span class="kh-mut">불러오는 중</span>';
      load();
    },
    destroy() { if (timer) clearInterval(timer); },
  };
}
