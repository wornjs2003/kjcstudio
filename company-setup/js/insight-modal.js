// Insight 모달 — data-modal="page" 링크를 누르면 그 페이지를 홀딩스 모달 안에 띄운다 (2026-10-02 지시).
// 띄우고 닫는 것은 holdings/js/components/modal.js 가 한다 — 여기서 새로 만들지 않는다.
// 링크는 목록이 나중에 그려지므로 문서에 한 번 걸어 받는다
import { openModal } from '../../holdings/js/components/modal.js';

document.addEventListener('click', e => {
  const a = e.target.closest('a[data-modal="page"]');
  if (!a || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;   // 새 탭 · 가운데 클릭은 그대로 둔다
  e.preventDefault();
  const { body } = openModal({ label: a.textContent, width: 1320 });
  body.style.overflow = 'hidden';
  body.innerHTML = `<iframe src="${a.getAttribute('href')}" title="${a.textContent}"
    style="width:100%;height:100%;border:0;display:block"></iframe>`;
});
