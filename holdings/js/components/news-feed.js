/* 뉴스·공시 피드 */
import { notConnected } from './empty-state.js';

export function mountNewsFeed(el) {
  el.innerHTML = `
    <div class="kh-card-header">
      <h3 class="kh-card-title">최근 뉴스 · 공시</h3>
    </div>
    <div class="kh-card-body">
      ${notConnected('뉴스 · 공시', 'DART 공시 API (OpenDART) · 뉴스 수집')}
    </div>
  `;
}
