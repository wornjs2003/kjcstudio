/* 종목 모달 — 종목을 누르면 페이지를 옮기지 않고 그 자리에 종목 화면(stock.html 본문)을 띄운다.

   홈(home.js) 안에 있던 것을 꺼냈다 (2026-11-23 재권님 「단타 창에서 종목 클릭하면 차트 모달 띄워줄수있나?」 → 「응 해」 ·
   공용 부품 안에 「응」). 홈 밖(Insight 투자전략 단타 판)에서도 같은 모달을 부른다.

   여기 두는 것 — 모달 띄우기 · 양옆 서랍 · 닫기 단추 · 모달 안 종목 검색 · 종목 찾기(목록 밖 종목도 서버에서 이름을 찾는다).
   부르는 화면에 두는 것 — 주소(?code=) 넣고 빼기 · 닫은 뒤 할 일(홈은 큰 차트 다시 그리기). 걸이(beforeShow · onClose · onPick)로 잇는다.

   차트 그리기 도구(lightweight-charts · 전역 스크립트)는 화면에 없으면 이 파일이 한 번 불러온다 — 홈 · 종목 화면은 이미 건다.
   모달이 거는 CSS — 부르는 화면이 건다(이 파일은 CSS 를 걸지 않는다):
     holdings/css/frame.css · stock.css · flow-foot.css · depth.css · news.css · modal.css
     + 모달 안 종목 검색칸 모양이 holdings/css/home.css 에 있다(.kh-cat-search) — 홈 밖이면 그 칸만 맨 모양이다

   시세 루프를 새로 돌리지 않는다 — 첫 값은 부르는 쪽이 `price` 로 넘기고, 그 뒤는 stock-view 가 자기 종목을 지켜본다. */

import { openModal, closeModal } from './modal.js';
import { loadStockMain, mountStockView } from './stock-view.js';
import { mountStockSearch } from './stock-search.js';
import { lookupStock } from '../data/lookup-stock.js';
import { brandColor } from '../data/market.js';

/* 사이트 맨 위 기준 — 홈 밖 화면에서도 같은 본문을 받는다 */
const STOCK_PAGE = '/holdings/stock.html';

let cur = null;   // { code, view, search }

/** 지금 떠 있는 종목 모달 { code, view } · 없으면 null — 부르는 화면이 받은 시세를 view.paint 로 넘긴다 */
export function currentStockModal() { return cur; }

/**
 * 종목 모달을 연다. 같은 종목이 이미 떠 있으면 아무것도 안 한다.
 * @param {string} code
 * @param {object} [o]
 * @param {object} [o.stock]       { code, name, brand } — 없으면 서버에서 이름을 찾는다
 * @param {object} [o.price]       첫 그림에 쓸 시세 · 없으면 stock-view 가 받아 그린다
 * @param {Function} [o.beforeShow] 본문을 받은 뒤 · 모달을 띄우기 직전 (홈은 주소를 여기서 넣는다)
 * @param {Function} [o.onClose]   ({ code, switching }) — 다른 종목 모달로 갈아타는 중이면 switching 이 참
 * @param {Function} [o.onPick]    (next, name) — 모달 안 검색에서 고름 · 없으면 그 종목 모달로 갈아탄다
 * @returns {Promise<boolean>} 열었으면 참
 */
export async function openStockModal(code, o = {}) {
  if (cur && cur.code === code) return false;
  const stock = o.stock || await findAnywhere(code);
  if (!stock) return false;

  let main;
  try {
    await loadChartLib();
    main = await loadStockMain(STOCK_PAGE);
  } catch {
    /* 본문을 못 받으면 종목 화면으로 옮긴다. 아무 일도 안 일어나는 것보다 낫다 */
    location.href = `${STOCK_PAGE}?code=${code}`;
    return false;
  }
  if (o.beforeShow) o.beforeShow();

  /* 새 모달을 열면 openModal 이 옛 모달부터 닫는다 — 그 onClose 가 갈아타는 중인지 알게 한다 */
  switching = true;
  const { body } = openModal({
    label: `${stock.name} 종목 정보`,
    closeButton: false,   // 닫기는 머리(.kh-head)에 제 것이 있다
    /* **`key` 는 그대로 둔다** — 펼쳐둔 것을 적어 두는 이름이라 바꾸면 재권님이 펼쳐 두신 것이 접힌다.
       서랍에 무엇이 드는지는 `css/modal.css` 의 자리 이름이 정한다 */
    drawers: {
      left:  { key: 'stock-memo', label: '투자 지표 · 체결' },
      right: { key: 'stock-news', label: '투자자 정보 · AI 분석 · 종목 뉴스' },
    },
    onToggle() {
      /* 모달 폭이 바뀌었으니 차트도 다시 잰다 — 캔버스는 CSS 로 안 늘어난다 */
      if (cur) cur.view.resize();
    },
    onClose() {
      if (cur && cur.code === code) {
        if (cur.search) cur.search.destroy();   // 후보 목록은 body 에 붙어 있다
        cur.view.destroy();
        cur = null;
      }
      if (o.onClose) o.onClose({ code, switching });
    },
  });
  switching = false;

  body.appendChild(main);
  addActions(main);
  const search = addSearch(main, code, (next, name) => {
    if (o.onPick) o.onPick(next, name);
    else if (next !== code) openStockModal(next, { onClose: o.onClose });
  });

  const view = mountStockView(main, stock, { onBack: closeModal, view: 'modal' });
  cur = { code, view, search };
  view.paint(o.price || null);
  return true;
}
let switching = false;

/* 차트 그리기 도구 — 홈 · 종목 화면은 <script> 로 이미 걸어 둔다. 없으면 한 번만 불러온다 */
const CHART_LIB = '/holdings/js/vendor/lightweight-charts.js';
let chartLib = null;
function loadChartLib() {
  if (window.LightweightCharts) return Promise.resolve();
  if (!chartLib) {
    chartLib = new Promise((ok, no) => {
      const el = document.createElement('script');
      el.src = CHART_LIB;
      el.onload = () => ok();
      el.onerror = () => { chartLib = null; no(new Error('차트 그리기 도구를 못 받음')); };
      document.head.appendChild(el);
    });
  }
  return chartLib;
}

/** 목록 밖 종목 — 서버(순위표 · 상장사 대응표)에서 이름을 찾는다 */
async function findAnywhere(code) {
  const x = await lookupStock(code);
  return x ? { code, name: x.name, sector: '', brand: brandColor(code, x.name) } : null;
}

/* 머리 오른쪽 닫기. stock.html 에는 없다 — 그 화면은 이미 전체 화면이다 */
function addActions(main) {
  const top = main.querySelector('.kh-head-top');
  if (!top || top.querySelector('.kh-head-act')) return;
  const act = document.createElement('div');
  act.className = 'kh-head-act';
  act.innerHTML = `
    <button class="kh-modal-x" data-tip="닫기 (Esc)" aria-label="닫기">✕</button>`;
  act.querySelector('.kh-modal-x').addEventListener('click', closeModal);
  top.appendChild(act);
}

/* 머리 왼쪽 종목 이름 옆에 종목 검색 (2026-10-14 지시 — 「차트 모달창에서 종목검색 넣어주고 검색된 종목 모달로
   이동되도록 해줘」). 좁은 폭은 돋보기만 ✕ 옆에 둔다(css/modal.css) */
function addSearch(main, code, onPick) {
  const top = main.querySelector('.kh-head-top');
  const act = top && top.querySelector('.kh-head-act');
  if (!act) return null;
  const slot = document.createElement('span');
  top.insertBefore(slot, act);
  const search = mountStockSearch(slot, { onPick });
  /* 칸 안의 Esc 는 목록만 닫는다 — 문서까지 가면 모달이 통째로 닫힌다(components/modal.js) */
  if (search) search.input.addEventListener('keydown', (e) => { if (e.key === 'Escape') e.stopPropagation(); });
  return search;
}
