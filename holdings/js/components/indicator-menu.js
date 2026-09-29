/* ==========================================================================
   「보조지표」 메뉴 (2026-09-18 지시)

   기간 단추(5분·일·주·월·년) 오른쪽에 붙는다. 누르면 목록이 펼쳐지고
   체크로 켜고 끈다. 이름에 마우스를 올리면 설명이 뜬다.

   **켠 목록은 chart.js 가 들고 있다.** 여기서는 그것을 읽고 쓰기만 한다 —
   그래야 첫 화면·종목 화면·모달이 같은 상태를 본다 (2026-09-18 지시
   — "종목화면에 적용되거나 모델에 적용되는건 동기화가 되야해").

   설명 글은 data/indicators.json 한 곳에서만 고친다. 코드를 안 건드린다.
   ========================================================================== */

import { INDICATORS, indOn, toggleIndicator, onIndicatorChange } from '../chart.js';

/* 설명은 한 번만 읽어 모든 메뉴가 나눠 쓴다 */
let docs = null;
let docsPromise = null;

function loadDocs() {
  if (docs) return Promise.resolve(docs);
  if (!docsPromise) {
    docsPromise = fetch('./data/indicators.json', { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : {}))
      .then((j) => { docs = j || {}; return docs; })
      .catch(() => { docs = {}; return docs; });   // 못 읽으면 설명만 안 뜬다
  }
  return docsPromise;
}

/* 풍선은 화면에 하나만 둔다 */
let tip = null;
function showTip(key, el) {
  if (!docs) return;
  const d = docs[key];
  if (!d) return;
  if (!tip) {
    tip = document.createElement('div');
    tip.className = 'kh-ind-tip';
    document.body.appendChild(tip);
  }
  tip.innerHTML =
    `<b>${d.name}${d.par ? ` <span>(${d.par})</span>` : ''}</b>` +
    `<div class="why">${d.why}</div>` +
    (d.how || []).map((x) => `<p>${x}</p>`).join('');
  tip.hidden = false;
  const r = el.getBoundingClientRect();
  tip.style.left = `${Math.min(r.left, window.innerWidth - 348)}px`;
  tip.style.top = `${r.bottom + 7}px`;
}
function hideTip() { if (tip) tip.hidden = true; }

/**
 * 「보조지표」 메뉴를 붙인다.
 *
 * **떼는 것을 돌려준다** (2026-09-23). 전에는 화면이 뜰 때 한 번만 붙였는데
 * (`home.js` · `stock.js` 각 한 번), 종목 **모달**이 열릴 때마다 붙게 되면서
 * 자리가 생겼다 — 이 함수는 `document` 에 손잡이 **셋**(바깥 누르기 ·
 * `mouseover` · `mouseout`)을 걸고 `onIndicatorChange` 에 하나를 더 건다.
 * 모달을 열고 닫기를 되풀이하면 그만큼 쌓이고, 닫힌 모달의 목록(이미
 * 문서에서 떨어진 것)을 계속 고치게 된다.
 *
 * @returns {{destroy: Function}|undefined} 붙일 자리가 없으면 `undefined`
 */
export function mountIndicatorMenu(root) {
  if (!root) return;
  const btn = root.querySelector('.kh-ind-open');
  const list = root.querySelector('.kh-ind-list');
  if (!btn || !list) return;

  list.innerHTML = INDICATORS.map((x) =>
    `<label data-doc="${x.key}">
       <input type="checkbox" data-ind="${x.key}"><span>${x.name}</span>
     </label>`).join('');

  const sync = () => {
    list.querySelectorAll('input[data-ind]').forEach((b) => {
      b.checked = indOn().has(b.dataset.ind);
    });
  };
  sync();
  const offSync = onIndicatorChange(sync);

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    list.hidden = !list.hidden;
    if (!list.hidden) loadDocs();
  });

  /* `document` 에 거는 것은 **이름을 붙여 둔다** — 떼려면 같은 함수를
     넘겨야 한다. 익명 함수로 걸면 `removeEventListener` 가 못 뗀다. */
  const onDocClick = (e) => {
    if (!root.contains(e.target)) { list.hidden = true; hideTip(); }
  };
  const onOver = (e) => {
    const n = e.target.closest('[data-doc]');
    if (n) showTip(n.dataset.doc, n);
  };
  const onOut = (e) => { if (e.target.closest('[data-doc]')) hideTip(); };

  document.addEventListener('click', onDocClick);

  list.addEventListener('change', (e) => {
    const b = e.target.closest('input[data-ind]');
    if (b) toggleIndicator(b.dataset.ind);
  });

  /* 설명 풍선 — 목록에서도, 차트 칸 이름표에서도 뜬다 */
  loadDocs();
  document.addEventListener('mouseover', onOver);
  document.addEventListener('mouseout', onOut);

  return {
    /** 모달처럼 **떴다 사라지는 자리**에서 부른다. 안 부르면 열 때마다 쌓인다 */
    destroy() {
      offSync();
      document.removeEventListener('click', onDocClick);
      document.removeEventListener('mouseover', onOver);
      document.removeEventListener('mouseout', onOut);
      hideTip();
    },
  };
}
