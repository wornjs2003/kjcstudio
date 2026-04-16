/* 뉴스·공시 피드 */
import { MOCK_FEED } from '../data/mock.js';
import { getState, openDetail } from '../store/state.js';

const TAG_LABEL = { dart: '공시', news: '뉴스', notice: '공지' };

export function mountNewsFeed(el) {
  el.innerHTML = `
    <div class="kh-card-header">
      <h3 class="kh-card-title">최근 뉴스 · 공시</h3>
      <div class="kh-card-actions">
        <button class="kh-btn">전체보기</button>
      </div>
    </div>
    <div class="kh-card-body">
      ${MOCK_FEED.map(item => feedItem(item)).join('')}
    </div>
  `;
  el.querySelectorAll('.kh-feed-item').forEach(node => {
    node.addEventListener('click', () => {
      const code = node.dataset.code;
      const stock = getState().stocks.find(s => s.code === code);
      if (stock) openDetail(stock);
    });
  });
}

function feedItem(item) {
  return `
    <div class="kh-feed-item" data-code="${item.ticker}">
      <div class="kh-feed-meta">
        <span class="kh-feed-time">${item.time}</span>
        <span class="kh-tag kh-tag-${item.type}">${TAG_LABEL[item.type] || item.type}</span>
        <span class="kh-feed-ticker">${item.name} · ${item.ticker}</span>
      </div>
      <div class="kh-feed-title">${item.title}</div>
    </div>
  `;
}
