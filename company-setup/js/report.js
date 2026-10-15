// 영상 분석 보고서 한 편을 그린다 — ?id=<문서 이름>
(async () => {
  const box = document.getElementById('in-report');
  const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  let id = new URLSearchParams(location.search).get('id');
  // 갈래 탭으로 들어오면 id 가 없다 — 목록의 가장 새것(맨 앞)을 연다 (2026-10-15 「영상분석 텝 … 연결되어야해」)
  if (!id) {
    try { id = ((((await (await fetch('/api/board/doc/insight-video-index', { cache: 'no-store' })).json()).data || {}).items || [])[0] || {}).id; } catch (e) { id = null; }
    if (!id) { box.innerHTML = '<p class="in-empty">영상 분석 목록을 불러오지 못함</p>'; return; }
  }
  let d;
  try {
    const r = await fetch('/api/board/doc/' + encodeURIComponent(id), { cache: 'no-store' });
    d = (await r.json()).data;
  } catch (e) { d = null; }
  if (!d) { box.innerHTML = '<p class="in-empty">불러오지 못함</p>'; return; }
  const s = d.source || {};
  // 본문 속 주소는 누를 수 있게 — 유튜브 원본(새 창) · 다른 보고서(report.html?id=…) (2026-10-15 재권님 「링크도 같이 첨부해주고」)
  const linked = t => esc(t).replace(/https?:\/\/[^\s<]+|report\.html\?id=[A-Za-z0-9_-]+/g, u => u.startsWith('http')
    ? `<a href="${u}" target="_blank" rel="noopener">${u}</a>` : `<a href="${u}">다른 보고서 열기 ›</a>`);
  document.title = (d.headline || '영상 분석') + ' · Insight';
  box.innerHTML = `
    <div class="in-rp-head">
      <div class="in-rp-text">
        <div class="in-rp-meta">${esc(s.channel)} · ${esc(s.show)} · ${esc(d.date)} · ${esc(s.duration)}</div>
        <h1>${esc(d.headline)}</h1>
        <p>${esc(d.summary)}</p>
        ${s.url ? `<a class="kh-fold" href="${esc(s.url)}" target="_blank" rel="noopener">유튜브에서 보기 ›</a>` : ''}
      </div>
      ${s.thumbnail ? `<img src="${esc(s.thumbnail)}" alt="영상 썸네일">` : ''}
    </div>
    ${(d.sections || []).map(x => `<section class="in-rp-sec"><h2>${esc(x.title)}</h2>
      <ul>${(x.points || []).map(p => `<li>${linked(p)}</li>`).join('')}</ul></section>`).join('')}
    <p class="in-rp-note">${esc(d.method)} · 정리 ${esc(d.writer)}</p>`;
})();
