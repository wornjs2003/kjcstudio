// 종목 목록 — data/stock-report/index.json 을 읽어 오른쪽 「종목」 칸([data-stocks])과 좁은 화면의 종목 줄([data-stocks-row])을 채운다.
// analysis.html · stock-report.html 이 함께 쓴다 (2026-10-06 재권님 「오른쪽 차례 대신에 종목 · 삼성전자 누르면 해당 목록」). 값을 지어내지 않는다 — 목록이 비면 「—」
(async () => {
  const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const cur = new URLSearchParams(location.search).get('code') || '';
  const onReport = /stock-report\.html$/.test(location.pathname);
  let items = [];
  try { items = ((await (await fetch('data/stock-report/index.json', { cache: 'no-store' })).json()).items || []); } catch (e) { items = []; }
  const link = (x) => `<a href="stock-report.html?code=${esc(x.code)}"${onReport && x.code === cur ? ' class="is-on" aria-current="page"' : ''}>${esc(x.name)} <span class="in-meta">${esc(x.code)}</span></a>`;
  document.querySelectorAll('[data-stocks]').forEach((ul) => { ul.innerHTML = items.length ? items.map((x) => `<li><div class="in-li">${link(x)}</div></li>`).join('') : '<li class="in-empty">—</li>'; });
  document.querySelectorAll('[data-stocks-row]').forEach((el) => { el.innerHTML = items.length ? items.map((x) => `<a class="kh-chip${onReport && x.code === cur ? ' is-active' : ''}" href="stock-report.html?code=${esc(x.code)}">${esc(x.name)}</a>`).join('') : '—'; });
})();
