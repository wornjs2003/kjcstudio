/* ==========================================================================
   세계 주요 이슈 — 주제별 아코디언

   예전에는 예시 기사 제목을 넣어 두었는데, 읽는 사람 입장에서는 실제
   뉴스와 구분이 되지 않았다. 받아올 곳을 붙이기 전까지는 비워 둔다.
   ========================================================================== */

import { notConnected } from './empty-state.js';

export function mountGlobalIssues(el) {
  /* 지수 스트립 높이에 카드 높이 맞추기 */
  function syncHeight() {
    const strip = document.getElementById('kh-index-strip');
    if (!strip) return;
    const h = strip.offsetHeight;
    if (h > 0) el.style.height = h + 'px';
  }

  el.innerHTML = `
    <div class="kh-card-header">
      <h3 class="kh-card-title">세계 주요 이슈</h3>
    </div>
    <div class="kh-card-body">
      ${notConnected('세계 주요 이슈', '뉴스 수집 (주제별 분류)')}
    </div>
  `;

  syncHeight();
  window.addEventListener('resize', syncHeight);
  setTimeout(syncHeight, 100);
}
