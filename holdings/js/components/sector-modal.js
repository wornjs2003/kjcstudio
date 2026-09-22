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

   **카드보다 많이 보여준다.** 받아 온 것은 같은데 카드가 좁아 잘라 놓았다.

       카드    묶음 여섯 칩 · 종목 넷 · 이름/가격/등락률
       모달    **스무 칩 · 종목 열** · 거래대금 · 거래량까지

   ── 종류를 바꿔도 카드는 안 바뀐다 ──

   모달에서 테마를 보다 닫았는데 카드가 테마로 바뀌어 있으면 **무엇을 눌러
   그렇게 됐는지 알 수 없다.** 실시간 순위 모달이 정렬 기준을 따로 두는 것과
   같다 (`home.js` 의 `rankModalSort`).
   ========================================================================== */

import { openModal } from './modal.js';
import { fmtWon, fmtPct, fmtMoneyKr, fmtShareCount, dirClass } from '../utils/format.js';

/* **고정 px 이다.** `max-content` 면 탭(업종↔테마)을 바꿀 때 묶음 이름 길이에
   따라 폭이 달라진다. 900 은 칩 스물이 세 줄에 들어가고 표 다섯 열이
   안 눌리는 값이다 (2026-09-22 실측). */
const WIDTH = 900;

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

export function openSectorModal(snap) {
  if (!snap) return null;

  /* 모달이 들고 있는 것. 카드와 **따로** 움직인다 */
  let kind = snap.kind;
  let groups = snap.groups || [];
  let total = snap.total || groups.length;
  let pick = snap.pick;
  let rows = snap.stocks || null;      // 고른 묶음의 종목. null 이면 불러오는 중
  let seq = 0;

  const m = openModal({
    label: '지금 뜨는 산업',
    width: WIDTH,
    head: {
      icon: '산',
      name: '지금 뜨는 산업',
      sub: '네이버',
      caret: true,
      /* 「전체 화면 ↗」 이 없다. 산업만 볼 화면이 없어서다 — 없는 주소를
         적어 두면 눌렀을 때 빈 곳으로 간다. 실시간 순위와 같은 자리이고,
         만들지 말지는 아직 안 정해져 빨간 바탕으로 둔다
         (CLAUDE.md 「아직 안 정해진 자리는 빨간 바탕으로 남긴다」). */
      actions: [{ label: '전체 화면 없음', todo: true }],
      big: headBig(),
      stats: headStats(),
      /* 900px 에서 세 열이면 눌려 줄바꿈된다 (2026-09-22 실측) */
      statCols: 2,
      tabs: [
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
  if (!rows) loadStocks();
  return m;

  /* ── 머리 ── */

  /** 대표값은 **가장 많이 오른 묶음**이다. 이 모달의 주제 그대로다 */
  function headBig() {
    const top = groups[0];
    if (!top) return null;
    return {
      value: top.name,
      change: fmtPct(top.pct),
      changeCls: dirClass(top.pct),
      note: `가장 많이 오른 ${KIND_LABEL[kind]}`,
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
    rows = null;
    m.head.setTab(id);
    paint();                       // 「불러오는 중」 을 먼저 보여준다

    const got = await snap.listGroups(id);
    if (mine !== seq) return;      // 그새 다시 눌렀다
    if (!got) {
      paint('불러오지 못했습니다');
      return;
    }
    groups = got.rows;
    total = got.total;
    pick = groups.length ? groups[0].no : null;
    refreshHead();
    paint();
    loadStocks();
  }

  /* ── 고른 묶음의 종목 ── */

  async function loadStocks() {
    if (pick == null) return;
    const mine = seq;
    const got = await snap.pickGroup(kind, pick);
    if (mine !== seq) return;      // 그새 종류가 바뀌었다
    rows = got;
    paint(got ? '' : '불러오지 못했습니다');
  }

  /* ── 그리기 ── */

  function paint(err) {
    if (!groups.length) {
      m.body.innerHTML =
        `<div class="kh-scm"><div class="kh-scm-empty kh-mut">${esc(err || '불러오는 중')}</div></div>`;
      return;
    }
    const g = groups.find(x => x.no === pick) || groups[0];

    m.body.innerHTML = `<div class="kh-scm">
      <div class="kh-scm-chips">${groups.map(x => `
        <button class="kh-chip${x.no === g.no ? ' is-active' : ''}" data-no="${x.no}">
          ${esc(x.name)}<b class="${dirClass(x.pct)}">${fmtPct(x.pct)}</b>
        </button>`).join('')}</div>
      ${groupHead(g)}
      ${stockTable(err)}
    </div>`;

    m.body.querySelectorAll('[data-no]').forEach(b => {
      b.addEventListener('click', () => {
        const no = Number(b.dataset.no);
        if (no === pick) return;
        pick = no;
        rows = null;
        paint();
        loadStocks();
      });
    });
  }

  function groupHead(g) {
    const sum = (g.rise + g.steady + g.fall) || 1;
    return `
      <div class="kh-scm-gh">
        <b class="kh-scm-gn">${esc(g.name)}</b>
        <b class="${dirClass(g.pct)}">${fmtPct(g.pct)}</b>
        <span class="kh-sc-bar" title="상승 ${g.rise} · 보합 ${g.steady} · 하락 ${g.fall}">
          <i class="up" style="width:${g.rise / sum * 100}%"></i>
          <i class="fl" style="width:${g.steady / sum * 100}%"></i>
          <i class="dn" style="width:${g.fall / sum * 100}%"></i>
        </span>
        <span class="kh-scm-cnt">
          <b class="kh-up">${g.rise}</b> 오름 · <b class="kh-down">${g.fall}</b> 내림
          <span class="kh-mut">· 종목 ${g.count}개</span>
        </span>
      </div>`;
  }

  /* **`border-collapse: separate` 라야 표머리가 붙어 있는다** —
     `collapse` 로는 sticky 가 −892px 로 사라진다 (주식페이지_개발3 실측).
     그 값은 `css/home.css` 의 `.kh-scm table` 에 있다. */
  function stockTable(err) {
    if (rows == null) {
      return `<div class="kh-scm-empty kh-mut">${esc(err || '불러오는 중')}</div>`;
    }
    if (!rows.length) {
      return '<div class="kh-scm-empty kh-mut">종목이 없습니다</div>';
    }
    return `
      <table>
        <thead><tr>
          <th>종목</th><th class="r">현재가</th><th class="r">등락률</th>
          <th class="r">거래대금</th><th class="r">거래량</th>
        </tr></thead>
        <tbody>${rows.map(s => `
          <tr data-code="${esc(s.code)}">
            <td><b>${esc(s.name)}</b></td>
            <td class="r kh-num">${fmtWon(s.price)}</td>
            <td class="r kh-num ${dirClass(s.pct)}">${fmtPct(s.pct)}</td>
            <td class="r kh-num">${s.value != null ? fmtMoneyKr(s.value / 100) : '—'}</td>
            <td class="r kh-num">${fmtShareCount(s.volume)}</td>
          </tr>`).join('')}</tbody>
      </table>`;
  }
}
