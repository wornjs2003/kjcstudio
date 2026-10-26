/* ==========================================================================
   「지금 뜨는 산업」 모달 (2026-09-22 지시)

   재권님 말씀 — 「**지금 뜨는 산업도 모달로 띄울 수 있어야 할 거 같어**」.

   ── 뼈대를 새로 만들지 않는다 ──

   `components/modal-head.js` 위에 얹는다. 실시간 순위 · 뉴스 · 데일리에
   이어 **네 번째**다. `openModal({ head })` 로 부르면 `modal.js` 가 머리를
   붙인다 — `modal-head.js` 와 `css/modal.css` 는 건드리지 않는다.

   ── 카드가 받아 둔 것을 넘겨받는다 ──

   모달이 따로 받지 않는다. 같은 화면에서 두 번 받으면 **두 자리의 숫자가
   어긋나고** 네이버를 겹쳐 부른다. `mountSectors` 가 내주는 `snapshot()`
   을 쓴다.

   **카드와 같은 셋을 나란히 보여준다** (2026-09-22 지시 — 「모달 띄우면
   업종일때는 업종 3개가 보여져야하고 테마일때는 테마가 3개 보여지도록」).

       카드    묶음 셋 · 이름/가격/등락률
       모달    묶음 셋 · **거래대금 · 거래량까지** · 칩으로 4위 아래도 본다

   ~~칩을 누르면 그 칩부터 셋~~ — **2026-10-26 에 바뀌었다**(재권님 「가 · 받아」): 칩을 누르면 **그 칩 줄 바로 아래**에
   그 묶음 하나의 종목이 펼쳐진다 · 같은 칩 다시 누름 · ✕ 로 접는다. 테마가 257개라 칩 아래 셋 표가 화면 밖이었다.

   ── 종류를 바꿔도 카드는 안 바뀐다 ──

   모달에서 테마를 보다 닫았는데 카드가 테마로 바뀌어 있으면 **무엇을 눌러
   그렇게 됐는지 알 수 없다.** 실시간 순위 모달이 정렬 기준을 따로 두는 것과
   같다 (`home.js` 의 `rankModalSort`).
   ========================================================================== */

import { openModal } from './modal.js';
import { fmtPriceOf, fmtPct, fmtMoneyKr, dirClass } from '../utils/format.js';
/* 기간 칩은 **카드와 같은 목록**으로 그린다 — 새로 적으면 복제가 된다 */
import { spanChipsHtml, sourceOf } from './sectors.js';

/* **고정 px 이다.** `max-content` 면 탭(업종↔테마)을 바꿀 때 묶음 이름 길이에
   따라 폭이 달라진다.

   **900 → 1100** (2026-09-22). 셋을 나란히 놓으니 한 칸이 228px 로 좁아
   **종목 이름이 현재가를 덮었다** — 「우성머티리얼즈」 가 「45원」 위로
   올라탔다. 1100 이면 한 칸이 약 300px 이고 네 열이 안 눌린다.
   데일리분석 모달이 쓰는 값과 같다. */
const WIDTH = 1100;

const KIND_LABEL = { industry: '업종', theme: '테마' };


function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/** 받은 시각을 「14:31 기준」 으로 */
function atText(at) {
  if (!at) return '';
  const p = (n) => String(n).padStart(2, '0');
  return `${p(at.getHours())}:${p(at.getMinutes())} 기준`;
}

/* `opt.onPick(code, name)` — 표 줄을 누르면 모달을 닫고 부른다. 홈이 카드 종목을 누를 때와 같은 길을 넘긴다
   (2026-10-08 재권님 「같은 룰이니 그렇게 하면 될거같은데」 — 전에는 줄이 눌리는 것처럼 보이는데 아무 일이 없었다) */
export function openSectorModal(snap, opt = {}) {
  if (!snap) return null;

  /* 모달이 들고 있는 것. 카드와 **따로** 움직인다 */
  let kind = snap.kind;
  /* 시장은 카드에서 고른 그대로 · 기간은 모달 칩으로 바꿀 수 있다 (2026-10-08) */
  const mkt = snap.mkt || 'kr';
  let span = snap.span || 'd';
  let groups = snap.groups || [];
  let total = snap.total || groups.length;
  /* **펼친 칩**의 자리 (2026-10-26 재권님 「가 · 받아」 — 칩을 누르면 그 칩 줄 바로 아래에 그 묶음 종목이 펼쳐진다).
     전에는 「그 칩부터 셋」 을 칩 줄 **아래** 표 셋으로 그렸는데, 테마가 257개라 그 표가 칩 밑 화면 밖이어서
     「눌러도 안 나온다」 로 보였다. 이제 하나만 · 칩 바로 아래. 같은 칩을 다시 누르거나 ✕ 면 접는다(`open = false`).
     처음 열 때는 카드에서 고른 묶음(보통 1위)을 펼친 채로 연다 — 전에도 그것부터 보였다 */
  let from = Math.max(0, groups.findIndex((g) => g.no === snap.pick));
  let open = true;
  let seq = 0;

  /* 묶음마다 받아 둔 종목. `snap.pickGroup` 이 받아 오고 여기에 쌓인다 */
  let rowsBy = {};
  if (snap.pick != null && snap.stocks) rowsBy[snap.pick] = snap.stocks;

  const m = openModal({
    label: '지금 뜨는 산업',
    width: WIDTH,
    head: {
      icon: '산',
      name: '지금 뜨는 산업',
      sub: sourceOf(mkt),
      caret: true,
      /* **단추를 두지 않는다** (2026-09-22 지시 — 「전체 화면 없음 이거
         없애줘」). 전에는 「산업만 볼 화면이 없다」 를 빨간 칩으로 적어
         두었는데, 재권님이 그 자리를 빼기로 정하셨다 —
         holdings/CLAUDE.md 「받을 수 없는 것은 자리도 만들지 않는다」. */
      big: headBig(),
      stats: headStats(),
      /* 900px 에서 세 열이면 눌려 줄바꿈된다 (2026-09-22 실측) */
      statCols: 2,
      /* 미국은 업종(섹터 ETF)만 있다 */
      tabs: mkt === 'us' ? [{ id: 'industry', label: '업종' }] : [
        { id: 'industry', label: '업종' },
        { id: 'theme', label: '테마' },
      ],
      tab: kind,
      tabsNote: '카드에서 잘렸던 거래대금 · 거래량까지',
      onTab: switchKind,
    },
  });

  /* **`m.body` 의 클래스를 바꾸지 않는다.** 그것이 `.kh-modal-scroll` —
     굴러가는 칸이다. 처음에 `m.body.className = 'kh-scm'` 로 덮었더니
     그 클래스가 지워져 **본문이 안 굴러가고 모달 밖으로 넘쳤다**
     (모달 510px 에 본문 627px, 2026-09-22 실측).
     앞선 셋(`kh-rkm` · `kh-nwm` · `kh-dlm`)도 전부 **안쪽에 div 를 둔다.** */
  paint();
  loadShown();
  return m;

  /* ── 머리 ── */

  /** 대표값은 **지금 보고 있는 첫 칸**이다.
      1위 고정으로 뒀더니 칩으로 7·8·9위를 볼 때 머리와 본문이 어긋났다
      (2026-09-22). 머리가 「가장 많이 오른 테마」 라고 적고 있는데
      아래는 7위부터 나와서, 어느 쪽을 믿을지 알 수 없었다. */
  function headBig() {
    const top = groups[from];
    if (!top) return null;
    return {
      value: top.name,
      change: fmtPct(top.pct),
      changeCls: dirClass(top.pct),
      note: from === 0
        ? `가장 많이 오른 ${KIND_LABEL[kind]}`
        : `${from + 1}위 ${KIND_LABEL[kind]}`,
    };
  }

  /** **억지로 채우지 않는다** — 셀 수 있는 것만 적는다 */
  function headStats() {
    /* 오른/내린 묶음 수는 **받아 온 것 안에서만** 셀 수 있다.
       네이버가 상위 스물만 주고 전체(79)는 개수만 준다. 그래서
       「스물 중 몇」 이라고 적는다 — 「79 중 몇」 으로 읽히면 안 된다. */
    const up = groups.filter(g => g.pct > 0).length;
    const dn = groups.filter(g => g.pct < 0).length;
    const st = [
      { label: `${KIND_LABEL[kind]} 수`, value: `${total}개` },
      { label: `받아 온 ${KIND_LABEL[kind]}`, value: `상위 ${groups.length}개` },
      {
        label: `그중 오름 / 내림`,
        html: `<b class="kh-up">${up}</b> / <b class="kh-down">${dn}</b>`,
      },
    ];
    if (snap.at) st.push({ label: '받은 시각', value: atText(snap.at) });
    return st;
  }

  /* **네이버 `value` 는 백만원이고 `fmtMoneyKr` 은 억원을 받는다** — 100 으로
     나눈다. 두 종목으로 대봤다 (2026-09-22):

         LG전자   215,500 × 1,487,408 = 3,205억   value 320,827 백만원 = 3,208억
         LG전자우  71,800 ×   145,582 =   104억   value  10,492 백만원 =   105억

     안 나누면 **100배로 나가** 3,208억이 32조가 된다. */

  function refreshHead() {
    m.head.setBig(headBig());
    /* `statCols` 는 처음 만들 때만 정해진다(`modal-head.js` 의 setStats 는
       열 수를 안 받는다). 위 head 에서 2 로 줬으므로 그대로 간다. */
    m.head.setStats(headStats());
  }

  /* ── 종류 바꾸기 ── */

  async function switchKind(id) {
    if (id === kind) return;
    const mine = ++seq;
    kind = id;
    groups = [];
    from = 0;
    open = true;
    m.head.setTab(id);
    paint();                       // 「불러오는 중」 을 먼저 보여준다

    const got = await snap.listGroups(id, span);
    if (mine !== seq) return;      // 그새 다시 눌렀다
    if (!got) {
      paint('불러오지 못했습니다');
      return;
    }
    groups = got.rows;
    total = got.total;
    refreshHead();
    paint();
    loadShown();
  }

  /* ── 기간 바꾸기 (2026-10-08) — 목록 · 종목을 그 기간으로 다시 받는다 ── */

  async function switchSpan(id) {
    if (id === span) return;
    const mine = ++seq;
    span = id;
    groups = [];
    rowsBy = {};
    from = 0;
    open = true;
    paint();
    const got = await snap.listGroups(kind, span);
    if (mine !== seq) return;
    if (!got) {
      paint('불러오지 못했습니다');
      return;
    }
    groups = got.rows;
    total = got.total;
    refreshHead();
    paint();
    loadShown();
  }

  /* ── 보이는 셋의 종목 ── */

  /** 지금 펼친 묶음 — 접혀 있으면 없음 */
  function shown() {
    return open && groups[from] ? [groups[from]] : [];
  }

  /** 셋을 **한꺼번에** 받는다. 받아 둔 것은 다시 안 부른다 */
  async function loadShown() {
    const mine = seq;
    const want = shown();
    await Promise.all(want.map(async (g) => {
      if (rowsBy[g.no]) return;
      const got = await snap.pickGroup(kind, g.no, span);
      if (got) rowsBy[g.no] = got;
    }));
    if (mine !== seq) return;      // 그새 갈래가 바뀌었다
    paint();
  }

  /* ── 그리기 ── */

  function paint(err) {
    if (!groups.length) {
      m.body.innerHTML =
        `<div class="kh-scm"><div class="kh-scm-empty kh-mut">${esc(err || '불러오는 중')}</div></div>`;
      return;
    }
    const want = shown();

    /* **칩을 누르면 그 칩부터 셋**이다. 지금 보고 있는 셋에 불을 켠다 —
       고른 하나만 켜면 「왜 옆 둘도 보이지」 가 된다. */
    m.body.innerHTML = `<div class="kh-scm">
      <!-- 기간 칩 — **카드와 같은 SPANS** 로 그린다 (2026-09-23, 모달 검수 ⑥).
           재권님 지시 「가로 해줘 만들거야」. 2026-10-08 부터 국내 · 미국 다 셋이
           눌린다 — 누르면 아래 switchSpan 이 그 기간으로 다시 받는다.
           (백틱을 쓰지 않는다 — 이 주석은 템플릿 문자열 **안**이라
            백틱 하나가 문자열을 끊는다. 2026-09-23 에 한 번 끊었다.) -->
      <div class="kh-chips kh-scm-span">${spanChipsHtml(span, mkt)}</div>
      <div class="kh-scm-chips">${groups.map((x, i) => `
        <button class="kh-chip${open && i === from ? ' is-active' : ''}"
          data-i="${i}" title="${open && i === from ? '다시 누르면 접습니다' : '이 묶음의 종목을 바로 아래에 펼칩니다'}">
          ${esc(x.name)}<b class="${dirClass(x.pct)}">${fmtPct(x.pct)}</b>
        </button>`).join('')}</div>
    </div>`;

    /* 펼친 칸은 **그 칩이 있는 줄의 마지막 칩 뒤**에 끼운다 — 줄 전체 폭(flex-basis 100%)이라 그 아래 칩 줄들만 밀린다.
       어느 칩이 같은 줄인지는 그려 본 뒤 자리(top)로 가른다 — 모달 폭 · 이름 길이에 따라 줄이 바뀌어서다 */
    const g = want[0];
    if (g) {
      const btns = [...m.body.querySelectorAll('.kh-scm-chips [data-i]')];
      const top = btns[from].getBoundingClientRect().top;
      let last = btns[from];
      for (let i = from + 1; i < btns.length && Math.abs(btns[i].getBoundingClientRect().top - top) < 4; i++) last = btns[i];
      last.insertAdjacentHTML('afterend', `<div class="kh-scm-open">
        <button type="button" class="kh-scm-x" data-scm-close aria-label="접기">✕</button>
        ${groupHead(g, from + 1)}${stockTable(g, err)}</div>`);
      m.body.querySelector('[data-scm-close]').addEventListener('click', () => { open = false; refreshHead(); paint(); });
    }

    /* 기간 칩 — 눌리지 않는 칩은 disabled 라 클릭이 안 온다 (2026-10-08) */
    m.body.querySelectorAll('.kh-scm-span [data-span]').forEach((b) => {
      b.addEventListener('click', () => switchSpan(b.dataset.span));
    });

    if (opt.onPick) m.body.querySelectorAll('tr[data-code]').forEach((tr) => {
      tr.style.cursor = 'pointer';
      tr.addEventListener('click', () => {
        const name = (tr.querySelector('b')?.textContent || '').trim();
        m.close();
        opt.onPick(tr.dataset.code, name);
      });
    });

    m.body.querySelectorAll('[data-i]').forEach((b) => {
      b.addEventListener('click', () => {
        const i = Number(b.dataset.i);
        /* 같은 칩을 다시 누르면 접는다 · 다른 칩이면 그것을 펼친다(펼친 칸은 하나) */
        if (open && i === from) { open = false; refreshHead(); paint(); return; }
        from = i;
        open = true;
        refreshHead();            // 머리의 대표값도 함께 옮긴다
        paint();
        loadShown();
      });
    });
  }

  function groupHead(g, rank) {
    const sum = (g.rise + g.steady + g.fall) || 1;
    return `
      <div class="kh-scm-gh">
        ${rank === 1 ? '<span class="kh-scm-fire" aria-hidden="true">🔥</span>' : ''}
        <b class="kh-scm-rk">${rank}위</b>
        <b class="kh-scm-gn" title="${esc(g.name)}">${esc(g.name)}</b>
        <b class="kh-scm-pc ${dirClass(g.pct)}">${fmtPct(g.pct)}</b>
      </div>
      <span class="kh-sc-bar" title="상승 ${g.rise} · 보합 ${g.steady} · 하락 ${g.fall}">
        <i class="up" style="width:${g.rise / sum * 100}%"></i>
        <i class="fl" style="width:${g.steady / sum * 100}%"></i>
        <i class="dn" style="width:${g.fall / sum * 100}%"></i>
      </span>
      <div class="kh-scm-cnt">
        <b class="kh-up">상승 ${g.rise}</b>
        <span class="kh-mut">보합 ${g.steady}</span>
        <b class="kh-down">하락 ${g.fall}</b>
        <span class="kh-mut kh-scm-tot">종목 ${g.count}개</span>
      </div>`;
  }

  /* **`border-collapse: separate` 라야 표머리가 붙어 있는다** —
     `collapse` 로는 sticky 가 −892px 로 사라진다 (주식페이지_개발3 실측).
     그 값은 `css/home.css` 의 `.kh-scm table` 에 있다. */
  function stockTable(g, err) {
    const rows = rowsBy[g.no];
    if (rows == null) {
      return `<div class="kh-scm-empty kh-mut">${esc(err || '불러오는 중')}</div>`;
    }
    if (!rows.length) {
      return '<div class="kh-scm-empty kh-mut">종목이 없습니다</div>';
    }
    /* 주간 · 월간 거래대금은 서버가 날마다 거래량 × 종가를 더한 **추정**이다(naver_period.py) — 표머리에 적는다.
       시총은 네이버 칸 그대로(억원) · 일간도 같은 칸을 받는다 (2026-10-26 재권님 「받아」) */
    const valHead = span === 'd' ? '거래대금' : `거래대금(${span === 'w' ? '주간' : '월간'} · 추정)`;
    const pcHead = span === 'd' ? '등락률' : (span === 'w' ? '주간 등락률' : '월간 등락률');
    return `
      <div class="kh-scm-list"><table>
        <colgroup><col class="c-nm"><col class="c-pr"><col class="c-pc"><col class="c-am"><col class="c-cap"></colgroup>
        <thead><tr>
          <th>종목</th><th class="r">${span === 'd' ? '현재가' : '현재가(마지막 종가)'}</th><th class="r">${pcHead}</th>
          <th class="r">${valHead}</th><th class="r">시총</th>
        </tr></thead>
        <tbody>${rows.map(st => `
          <tr data-code="${esc(st.code)}">
            <td><b title="${esc(st.name)}">${esc(st.name)}</b><span class="kh-mut kh-scm-cd">${esc(st.code)}</span></td>
            <td class="r kh-num">${fmtPriceOf(st.code, st.price)}</td>
            <td class="r kh-num ${dirClass(st.pct)}">${fmtPct(st.pct)}</td>
            <td class="r kh-num">${st.value != null ? fmtMoneyKr(st.value / 100) : '—'}</td>
            <td class="r kh-num">${st.cap != null ? fmtMoneyKr(st.cap) : '—'}</td>
          </tr>`).join('')}</tbody>
      </table></div>`;
  }
}
