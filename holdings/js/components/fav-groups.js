/* ==========================================================================
   관심종목 묶음 고르기 창 (2026-11-05 재권님 「관심종목 카테고리화」 → (가) 한 종목이 여러 묶음에 → 시안 10:44 「응 해줘」)

   하트(순위 숫자 · 큰 차트 머리줄)를 **켤 때** 그 옆에 뜬다. 체크하면 바로 그 묶음에 들어간다(저장 단추 없음).
   하나도 안 고르면 「미분류」 다. 새 묶음은 아래 칸에 이름을 적어 더한다 — 더하면 이 종목이 그 묶음에 든다.
   바깥을 누르거나 Esc 로 닫힌다. 묶음 저장은 store/favorites.js 한 곳이다.
   ========================================================================== */

import { favGroups, setInGroup, addGroup, isFav, onFavChange } from '../store/favorites.js';

let box = null;
let off = null;
let boxCode = null;

/* 다른 곳에서 하트를 끄면 닫는다 */
onFavChange(() => { if (box && !isFav(boxCode)) closeGroupPicker(); });

function esc(t) { return String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

export function closeGroupPicker() {
  if (off) { off(); off = null; }
  box?.remove();
  box = null;
  boxCode = null;
}

/** anchor 옆에 code 종목의 묶음 고르기 창을 연다 */
export function openGroupPicker(anchor, code, name) {
  closeGroupPicker();
  boxCode = code;
  box = document.createElement('div');
  box.className = 'kh-fg';
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-label', `${name || code} 담을 묶음`);

  const paint = () => {
    const groups = favGroups();
    box.innerHTML = `<b class="kh-fg-hd">${esc(name || code)} — 담을 묶음</b>
      <div class="kh-fg-list">${groups.length ? groups.map((g) => `<label class="kh-fg-row">
        <input type="checkbox" data-g="${esc(g.id)}"${g.codes.includes(code) ? ' checked' : ''}> ${esc(g.name)}</label>`).join('')
        : '<div class="kh-fg-none">아직 묶음이 없습니다</div>'}</div>
      <div class="kh-fg-hint">하나도 안 고르면 「미분류」</div>
      <form class="kh-fg-add"><input type="text" maxlength="20" placeholder="새 묶음 이름"><button type="submit">더하기</button></form>`;
  };
  paint();
  document.body.append(box);

  /* 자리 — anchor 오른쪽, 화면 밖으로 나가면 왼쪽 · 위로 */
  const r = anchor.getBoundingClientRect();
  const w = box.offsetWidth, h = box.offsetHeight;
  let left = r.right + 6, top = r.top - 4;
  if (left + w > innerWidth - 8) left = Math.max(8, r.left - w - 6);
  if (top + h > innerHeight - 8) top = Math.max(8, innerHeight - h - 8);
  box.style.left = left + 'px';
  box.style.top = top + 'px';

  box.addEventListener('change', (e) => {
    const cb = e.target.closest('input[data-g]');
    if (cb) setInGroup(code, cb.dataset.g, cb.checked);
  });
  box.addEventListener('submit', (e) => {
    e.preventDefault();
    const inp = box.querySelector('.kh-fg-add input');
    const id = addGroup(inp.value);
    if (!id) return;
    setInGroup(code, id, true);
    paint();
    box.querySelector('.kh-fg-add input')?.focus();
  });

  const onDown = (e) => { if (box && !box.contains(e.target) && e.target !== anchor) closeGroupPicker(); };
  const onKey = (e) => { if (e.key === 'Escape') closeGroupPicker(); };
  /* 다음 틱부터 듣는다 — 연 그 누름이 곧바로 닫지 않게 */
  setTimeout(() => {
    document.addEventListener('pointerdown', onDown, true);
    document.addEventListener('keydown', onKey);
  });
  off = () => {
    document.removeEventListener('pointerdown', onDown, true);
    document.removeEventListener('keydown', onKey);
  };
}
