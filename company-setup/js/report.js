// 영상 분석 보고서 한 편을 그린다 — ?id=<문서 이름>
(async () => {
  const box = document.getElementById('in-report');
  const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const id = new URLSearchParams(location.search).get('id');
  if (!id) { box.innerHTML = '<p class="in-empty">어느 보고서인지 주소에 없습니다 (?id=…)</p>'; return; }
  let d;
  try {
    const r = await fetch('/api/board/doc/' + encodeURIComponent(id), { cache: 'no-store' });
    d = (await r.json()).data;
  } catch (e) { d = null; }
  if (!d) { box.innerHTML = '<p class="in-empty">불러오지 못함</p>'; return; }
  const s = d.source || {};
  document.title = (d.headline || '영상 분석') + ' · Insight';
  box.innerHTML = `
    <div class="in-rp-head">
      <div class="in-rp-text">
        <div class="in-rp-meta">${esc(s.channel)} · ${esc(s.show)} · ${esc(d.date)} · ${esc(s.duration)}</div>
        <h1>${esc(d.headline)}</h1>
        <p>${esc(d.summary)}</p>
        <a class="kh-fold" href="${esc(s.url)}" target="_blank" rel="noopener">유튜브에서 보기 ›</a>
      </div>
      ${s.thumbnail ? `<img src="${esc(s.thumbnail)}" alt="영상 썸네일">` : ''}
    </div>
    ${(d.sections || []).map(x => `<section class="in-rp-sec"><h2>${esc(x.title)}</h2>
      <ul>${(x.points || []).map(p => `<li>${esc(p)}</li>`).join('')}</ul></section>`).join('')}
    <p class="in-rp-note">${esc(d.method)} · 정리 ${esc(d.writer)}</p>`;
})();
