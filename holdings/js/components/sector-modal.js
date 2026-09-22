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

   **칩을 누르면 그 칩부터 셋**이 나온다 — 1위를 누르면 1·2·3위, 4위를
   누르면 4·5·6위다. 그래서 스무 묶음을 다 볼 수 있으면서 **언제나 셋**이다.
   (전에는 칩으로 하나를 골라 그 종목만 표로 봤다.)

   ── 종류를 바꿔도 카드는 안 바뀐다 ──

   모달에서 테마를 보다 닫았는데 카드가 테마로 바뀌어 있으면 **무엇을 눌러
   그렇게 됐는지 알 수 없다.** 실시간 순위 모달이 정렬 기준을 따로 두는 것과
   같다 (`home.js` 의 `rankModalSort`).
   ========================================================================== */

import { openModal } from './modal.js';
import { fmtWon, fmtPct, fmtMoneyKr, dirClass } from '../utils/format.js';

/* **고정 px 이다.** `max-content` 면 탭(업종↔테마)을 바꿀 때 묶음 이름 길이에
   따라 폭이 달라진다.

   **900 → 1100** (2026-09-22). 셋을 나란히 놓으니 한 칸이 228px 로 좁아
   **종목 이름이 현재가를 덮었다** — 「우성머티리얼즈」 가 「45원」 위로
   올라탔다. 1100 이면 한 칸이 약 300px 이고 네 열이 안 눌린다.
   데일리분석 모달이 쓰는 값과 같다. */
const WIDTH = 1100;

const KIND_LABEL = { industry: '업종', theme: '테마' };

/* **한 번에 보여줄 묶음 수** (2026-09-22 지시 — 「업종 3개 … 테마가 3개」).
   카드와 같은 셋이다. 칩을 누르면 그 칩부터 셋이 나온다. */
const SHOW = 3;

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
  /* **시작 자리**다. 여기서부터 셋을 보여준다 — 칩을 누르면 이것이 바뀐다 */
  let from = Math.max(0, groups.findIndex((g) => g.no === snap.pick));
  let seq = 0;

  /* 묶음마다 받아 둔 종목. `snap.pickGroup` 이 받아 오고 여기에 쌓인다 */
  const rowsBy = {};
  if (snap.pick != null && snap.stocks) rowsBy[snap.pick] = snap.stocks;

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
        : `${from + 1}위 ${KIND_LABEL[kind]} — 아래 셋의 첫째`,
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
    refreshHead();
    paint();
    loadShown();
  }

  /* ── 보이는 셋의 종목 ── */

  /** 지금 보여줄 묶음 셋 */
  function shown() {
    return groups.slice(from, from + SHOW);
  }

  /** 셋을 **한꺼번에** 받는다. 받아 둔 것은 다시 안 부른다 */
  async function loadShown() {
    const mine = seq;
    const want = shown();
    await Promise.all(want.map(async (g) => {
      if (rowsBy[g.no]) return;
      const got = await snap.pickGroup(kind, g.no);
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
      <div class="kh-scm-chips">${groups.map((x, i) => `
        <button class="kh-chip${i >= from && i < from + SHOW ? ' is-active' : ''}"
          data-i="${i}" title="여기부터 ${SHOW}개를 봅니다">
          ${esc(x.name)}<b class="${dirClass(x.pct)}">${fmtPct(x.pct)}</b>
        </button>`).join('')}</div>
      <div class="kh-scm-cols">${want.map((g, i) => `
        <div class="kh-scm-col">${groupHead(g, from + i + 1)}${stockTable(g, err)}</div>`)
        .join('<i class="kh-scm-vr" aria-hidden="true"></i>')}</div>
    </div>`;

    m.body.querySelectorAll('[data-i]').forEach((b) => {
      b.addEventListener('click', () => {
        const i = Number(b.dataset.i);
        /* **끝에서는 뒤로 물린다** — 19번을 누르면 17·18·19 가 나온다.
           안 물리면 마지막 칩을 눌렀을 때 한 칸만 보인다. */
        const next = Math.min(i, Math.max(0, groups.length - SHOW));
        if (next === from) return;
        from = next;
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
    return `
      <div class="kh-scm-list"><table>
        <colgroup><col class="c-nm"><col class="c-pr"><col class="c-pc"><col class="c-am"></colgroup>
        <thead><tr>
          <th>종목</th><th class="r">현재가</th><th class="r">등락률</th>
          <th class="r">거래대금</th>
        </tr></thead>
        <tbody>${rows.map(st => `
          <tr data-code="${esc(st.code)}">
            <td><b title="${esc(st.name)}">${esc(st.name)}</b></td>
            <td class="r kh-num">${fmtWon(st.price)}</td>
            <td class="r kh-num ${dirClass(st.pct)}">${fmtPct(st.pct)}</td>
            <td class="r kh-num">${st.value != null ? fmtMoneyKr(st.value / 100) : '—'}</td>
          </tr>`).join('')}</tbody>
      </table></div>`;
  }
}
