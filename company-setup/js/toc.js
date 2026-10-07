// 목차 — 오른쪽 기둥 카드 + 폰 떠 있는 단추 · 종목 리포트(stock-report.js) · 종목 분석 문서(analysis.js)가 같이 쓴다 (2026-10-07 재권님 「목차가 옆에 떠 있고 누르면 해당 칸으로」)
// items: [{id, title, subs:[{id,title}]}] — 각 화면이 자기 절(details)에서 만들어 넘긴다. 여기서는 그리기 · 열기 · 지금 칸 표시(IntersectionObserver)만.
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
export function mountToc(items) {
  const lists = document.querySelectorAll('[data-toc-list]'); if (!lists.length) return;
  const html = items.map((it) => `<li><a href="#${it.id}" data-toc="${it.id}">${esc(it.title)}</a>${it.subs && it.subs.length ? `<ol>${it.subs.map((s) => `<li><a href="#${s.id}" data-toc="${it.id}">${esc(s.title)}</a></li>`).join('')}</ol>` : ''}</li>`).join('');
  lists.forEach((ol) => { ol.innerHTML = html; });
  const sheet = document.querySelector('[data-toc-sheet]');
  const close = () => { if (sheet) sheet.hidden = true; };
  document.querySelectorAll('[data-toc-open]').forEach((b) => b.addEventListener('click', () => { if (sheet) sheet.hidden = false; }));
  document.querySelectorAll('[data-toc-close]').forEach((b) => b.addEventListener('click', close));
  // 누르면 그 칸(접힌 details)을 열고 주소로 이동(기본 동작) · 폰 창은 닫는다
  document.querySelectorAll('[data-toc-list] a[data-toc]').forEach((a) => a.addEventListener('click', () => {
    let d = document.getElementById(a.dataset.toc); while (d) { if (d.tagName === 'DETAILS') d.open = true; d = d.parentElement && d.parentElement.closest('details'); }
    close();
  }));
  // 지금 보는 칸 — 고정 메뉴 선(--nav-height) 위로 올라간 절 중 가장 아래 것을 굵게 · 아무것도 안 올라갔으면 첫 절. 스크롤마다 한 프레임에 한 번 센다
  const nav = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--nav-height')) || 72;
  const mark = (id) => document.querySelectorAll('[data-toc-list] > li > a').forEach((a) => a.classList.toggle('is-now', a.dataset.toc === id));
  const spy = () => {
    let best = null, bestTop = -Infinity;
    for (const it of items) { const el = document.getElementById(it.id); if (!el) continue; const top = el.getBoundingClientRect().top; if (top <= nav + 16 && top > bestTop) { bestTop = top; best = it.id; } }
    mark(best || (items[0] && items[0].id));
  };
  let tick = false;
  addEventListener('scroll', () => { if (tick) return; tick = true; requestAnimationFrame(() => { tick = false; spy(); }); }, { passive: true });
  spy(); window.__tocSpy = spy;   // __tocSpy 는 측정용
}
