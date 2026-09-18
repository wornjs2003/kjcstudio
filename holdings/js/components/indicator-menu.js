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
  onIndicatorChange(sync);

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    list.hidden = !list.hidden;
    if (!list.hidden) loadDocs();
  });
  document.addEventListener('click', (e) => {
    if (!root.contains(e.target)) { list.hidden = true; hideTip(); }
  });

  list.addEventListener('change', (e) => {
    const b = e.target.closest('input[data-ind]');
    if (b) toggleIndicator(b.dataset.ind);
  });

  /* 설명 풍선 — 목록에서도, 차트 칸 이름표에서도 뜬다 */
  loadDocs();
  document.addEventListener('mouseover', (e) => {
    const n = e.target.closest('[data-doc]');
    if (n) showTip(n.dataset.doc, n);
  });
  document.addEventListener('mouseout', (e) => {
    if (e.target.closest('[data-doc]')) hideTip();
  });
}
