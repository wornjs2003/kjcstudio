/* 좌측 사이드바 내비게이션 */
import { getState, setActiveNav, subscribe } from '../store/state.js';

const NAV_ITEMS = [
  { id: 'home',      icon: '🏠', label: 'Home' },
  { id: 'portfolio', icon: '📊', label: 'Portfolio' },
  { id: 'news',      icon: '📰', label: 'News' },
  { id: 'notes',     icon: '📝', label: 'Notes' },
  { id: 'calendar',  icon: '📅', label: 'Calendar' },
];

const FOOTER_ITEMS = [
  { id: 'settings', icon: '⚙', label: 'Settings' },
];

export function mountSidebar(el) {
  function render() {
    const { activeNav } = getState();
    el.innerHTML = `
      <div class="kh-sidebar-logo">KJC</div>
      <nav class="kh-sidebar-nav">
        ${NAV_ITEMS.map(it => navItem(it, activeNav === it.id)).join('')}
      </nav>
      <div class="kh-sidebar-footer">
        ${FOOTER_ITEMS.map(it => navItem(it, activeNav === it.id)).join('')}
      </div>
    `;
    el.querySelectorAll('.kh-nav-item').forEach(node => {
      node.addEventListener('click', () => {
        setActiveNav(node.dataset.id);
      });
    });
  }
  render();
  subscribe(render);
}

function navItem(it, active) {
  return `
    <button class="kh-nav-item ${active ? 'is-active' : ''}" data-id="${it.id}" data-tooltip="${it.label}">
      <span>${it.icon}</span>
    </button>
  `;
}
