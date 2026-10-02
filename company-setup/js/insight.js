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

// 영상 분석 — 시황분석 세션이 로컬 문서 저장소에 쓴 목록(insight-video-index)을 읽는다.
// 저장은 git 이 아니라 이 PC 안(holdings/data/docs/)이다 — 루트 CLAUDE.md 「저장은 이 PC 안에만 둔다」
(async () => {
  const ul = document.querySelector('[data-videos]');
  if (!ul) return;
  const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  try {
    const r = await fetch('/api/board/doc/insight-video-index', { cache: 'no-store' });
    const items = ((await r.json()).data || {}).items || [];
    ul.innerHTML = items.length ? items.map(x => `<li><div class="in-li">
      <a href="report.html?id=${encodeURIComponent(x.id)}">${esc(x.headline)}</a>
      <div class="in-meta">${esc(x.show)} · ${esc(x.date)} · ${esc(x.duration)}</div></div></li>`).join('')
      : '<li class="in-empty">—</li>';
  } catch (e) {
    ul.innerHTML = '<li class="in-empty">불러오지 못함</li>';
  }
})();

// 종목 분석 — data/stock-analysis.json 의 items 를 날짜 최신순으로 그린다 (2026-10-02 지시).
// 항목 모양: { "date": "2026-10-02", "code": "005930", "name": "삼성전자", "title": "…", "summary": "…", "page": "(있으면) 모달로 열 페이지" }
(async () => {
  const ul = document.querySelector('[data-analysis]');
  if (!ul) return;
  const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  try {
    const r = await fetch('data/stock-analysis.json', { cache: 'no-store' });
    const items = ((await r.json()).items || []).slice().sort((a, b) => String(b.date).localeCompare(String(a.date)));
    // page 가 있으면 그 페이지를 모달로 연다 — href 는 남겨 새 탭 · 직접 주소가 그대로 된다 (모달 룰)
    const head = x => x.page ? `<a href="${esc(x.page)}" data-modal="page">${esc(x.title)}</a>` : `<span>${esc(x.title)}</span>`;
    ul.innerHTML = items.length ? items.map(x => `<li><div class="in-li">${head(x)}
      <div class="in-meta">${x.name ? `<span class="in-kind">${esc(x.name)}</span>` : ''}${esc(x.summary)} · ${esc(x.date)}</div></div></li>`).join('')
      : '<li class="in-empty">아직 분석이 없습니다</li>';
  } catch (e) {
    ul.innerHTML = '<li class="in-empty">불러오지 못함</li>';
  }
})();
