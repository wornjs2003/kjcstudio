// Insight — 네이버 증권 뉴스에서 받아 둔 파일(data/naver-news.json)을 칸에 채운다.
// 받는 것은 tools/fetch-naver-news.py 가 한다. 네이버가 다른 사이트의 직접 호출을 막아서다.
// 파일이 없거나 비면 「불러오지 못함」 · 「—」 를 적는다 — 예시 데이터를 두지 않는다
(async () => {
  const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const hm = at => (at || '').slice(11, 16);
  const lists = document.querySelectorAll('[data-feed]');
  let d;
  try {
    const r = await fetch('data/naver-news.json', { cache: 'no-store' });
    d = await r.json();
  } catch (e) {
    lists.forEach(ul => { ul.innerHTML = '<li class="in-empty">불러오지 못함</li>'; });
    return;
  }
  document.querySelectorAll('[data-asof]').forEach(el => {
    el.textContent = `네이버 증권 · ${d.fetchedAt} 받음`;
  });
  lists.forEach(ul => {
    const items = (d[ul.dataset.feed] || []).slice(0, Number(ul.dataset.n) || 99);
    if (!items.length) { ul.innerHTML = '<li class="in-empty">—</li>'; return; }
    ul.innerHTML = items.map((x, i) => {
      const t = x.link ? `<a href="${esc(x.link)}" target="_blank" rel="noopener">${esc(x.title)}</a>` : `<span>${esc(x.title)}</span>`;
      const rank = ul.classList.contains('in-rank') ? `<b class="in-no">${i + 1}</b>` : '';
      const kind = x.kind ? `<span class="in-kind">${esc(x.kind)}</span>` : '';
      return `<li>${rank}<div class="in-li">${t}<div class="in-meta">${kind}${esc(x.source)} · ${esc(hm(x.at))}</div></div></li>`;
    }).join('');
  });
})();
