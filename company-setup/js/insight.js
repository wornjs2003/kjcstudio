// Insight — 네이버 증권 뉴스에서 받아 둔 것을 칸에 채운다.
// 받는 것은 tools/fetch-naver-news.py 가 한다. 네이버가 다른 사이트의 직접 호출을 막아서다.
// 2026-10-06 — 10분 주기로 받는 쪽은 8765 문서 저장소(naver-news)에 둔다(--to-board). 그 문서를 먼저 읽고,
// 없거나(아직 안 켜짐 → data: null) 못 읽으면 손으로 받아 둔 파일(data/naver-news.json)로 돌아간다.
// 주기 값은 화면에 없다 — 문서의 fetchedAt 이 곧 받은 시각이다(「캐시·주기·한도 값을 화면에 박지 않는다」)
// 파일이 없거나 비면 「불러오지 못함」 · 「—」 를 적는다 — 예시 데이터를 두지 않는다
(async () => {
  const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const hm = at => (at || '').slice(11, 16);
  const lists = document.querySelectorAll('[data-feed]');
  let d;
  try {
    try {
      const b = await (await fetch('/api/board/doc/naver-news', { cache: 'no-store' })).json();
      if (b && b.ok && b.data && b.data.fetchedAt) d = b.data;
    } catch (e) { /* 문서 저장소를 못 읽으면 파일로 */ }
    if (!d) d = await (await fetch('data/naver-news.json', { cache: 'no-store' })).json();
  } catch (e) {
    lists.forEach(ul => { ul.innerHTML = '<li class="in-empty">불러오지 못함</li>'; });
    return;
  }
  // 출처 표시 (2026-10-06 지시) — 머리줄마다 「<출처> · <받은 시각> 받음」. 출처 이름은 data-asof 값, 비면 「네이버 증권」
  document.querySelectorAll('[data-asof]').forEach(el => {
    el.textContent = `${el.dataset.asof || '네이버 증권'} · ${d.fetchedAt} 받음`;
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

// 돈의 흐름 — 칸에 지도를 바로 (2026-10-06 지시 · 「나」 — 칸 안 지구본은 손대기 전까지 멈춤).
// data/stock-analysis.json 의 지도 글(page 가 flowmap.html?map=…)을 칩으로 만들고, 칩을 누르면 틀(iframe)의 지도를 바꾼다.
// 제목 링크(모달)도 같은 지도로 맞춘다. 머리줄 출처는 그 지도 자료(data/maps/<id>.json)의 asOf — 못 읽으면 「—」
(async () => {
  const chips = document.querySelector('[data-map-chips]'), frame = document.querySelector('[data-map-frame]');
  if (!chips || !frame) return;
  const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const asofEl = document.querySelector('[data-asof-map]'), titleLink = document.querySelector('.kh-idx-name a[data-modal]');
  const setAsof = async id => {
    if (!asofEl) return;
    try { const asOf = (await (await fetch(`data/maps/${id}.json`, { cache: 'no-store' })).json()).asOf; asofEl.textContent = asOf ? `시황분석 자료 · ${asOf}` : '시황분석 자료 · —'; }
    catch (e) { asofEl.textContent = '시황분석 자료 · —'; }
  };
  const setMap = id => {
    frame.src = `flowmap.html?map=${encodeURIComponent(id)}&view=geo&embed=1`;
    if (titleLink) titleLink.href = `flowmap.html?map=${encodeURIComponent(id)}&view=geo`;
    chips.querySelectorAll('.kh-chip').forEach(b => b.classList.toggle('is-active', b.dataset.map === id));
    setAsof(id);
  };
  const current = () => new URLSearchParams(frame.getAttribute('src').split('?')[1] || '').get('map') || 'ai';
  try {
    const r = await fetch('data/stock-analysis.json', { cache: 'no-store' });
    const maps = ((await r.json()).items || []).map(x => ({ x, id: (String(x.page || '').match(/flowmap\.html\?map=([a-z0-9_-]+)/i) || [])[1] })).filter(m => m.id);
    chips.innerHTML = maps.map(m => `<button class="kh-chip${m.id === current() ? ' is-active' : ''}" data-map="${esc(m.id)}" title="${esc(m.x.title)}">${esc(m.x.name || m.id)}</button>`).join('');
    chips.addEventListener('click', e => { const b = e.target.closest('.kh-chip'); if (b) setMap(b.dataset.map); });
    setAsof(current());
  } catch (e) {
    chips.innerHTML = '<span class="in-empty">불러오지 못함</span>';
    setAsof(current());
  }
})();
