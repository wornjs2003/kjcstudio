/* ==========================================================================
   세계 주요 이슈 — 주제별 아코디언
   주제: 전쟁 / AI / 방산 / 북극항로 / 조선 (추후 확장)
   높이: 지수 스트립에 맞춤, 주제 추가 시 내부 스크롤
   ========================================================================== */

import { MOCK_GLOBAL_ISSUES } from '../data/mock.js';

const TOPIC_COLOR = {
  '전쟁':     '#ff5f5f',
  'AI':       '#4f7eff',
  '방산':     '#f5a623',
  '북극항로': '#6fd2b8',
  '조선':     '#c48bff',
};

/* 주제별 그룹핑 (등장 순서 유지) */
function groupByTopic(issues) {
  const map = new Map();
  for (const item of issues) {
    if (!map.has(item.topic)) map.set(item.topic, []);
    map.get(item.topic).push(item);
  }
  return map;
}

export function mountGlobalIssues(el) {
  const groups = groupByTopic(MOCK_GLOBAL_ISSUES);
  const expandedSet = new Set();

  /* 지수 스트립 높이에 카드 높이 동기화 */
  function syncHeight() {
    const strip = document.getElementById('kh-index-strip');
    if (!strip) return;
    const h = strip.offsetHeight;
    if (h > 0) el.style.height = h + 'px';
  }

  function render() {
    const rows = [];
    for (const [topic, items] of groups) {
      const isOpen = expandedSet.has(topic);
      const color = TOPIC_COLOR[topic] || 'var(--kh-text-muted)';
      const extra = items.length - 1;

      rows.push(`
        <li class="kh-gi-row">
          <span class="kh-gi-topic" style="color:${color}">${topic}</span>
          <span class="kh-gi-title">${items[0].title}</span>
          ${extra > 0 ? `
            <button type="button" class="kh-gi-toggle" data-topic="${topic}"
                    title="${isOpen ? '접기' : extra + '건 더보기'}">
              ${isOpen ? '−' : '+' + extra}
            </button>
          ` : ''}
        </li>
      `);

      if (isOpen) {
        for (let i = 1; i < items.length; i++) {
          rows.push(`
            <li class="kh-gi-row kh-gi-sub">
              <span class="kh-gi-topic" style="color:${color}"></span>
              <span class="kh-gi-title">${items[i].title}</span>
            </li>
          `);
        }
      }
    }

    el.innerHTML = `
      <div class="kh-card-header">
        <h3 class="kh-card-title">세계 주요 이슈</h3>
      </div>
      <div class="kh-gi-scroll">
        <ul class="kh-gi-list">
          ${rows.join('')}
        </ul>
      </div>
    `;

    syncHeight();

    el.querySelectorAll('.kh-gi-toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        const t = btn.dataset.topic;
        if (expandedSet.has(t)) expandedSet.delete(t);
        else expandedSet.add(t);
        render();
      });
    });
  }

  render();

  /* 지수 스트립 크기 변동 → 높이 재동기화 */
  const strip = document.getElementById('kh-index-strip');
  if (strip && typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(() => syncHeight()).observe(strip);
  }
}
