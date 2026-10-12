// 시황분석 탭 맨 위 「세션이 쓴 시황」 — data/market-note.json 을 그린다(2026-10-12 재권님 「이 분석 시황분석의 맨위에 넣어줘」 →
// 「응 똑같이 해줘」 — 대화에 드린 글과 같은 문장 · 같은 순서 · 근거 펼친 채). market.js(규칙으로 쓰는 글)와 섞지 않으려고 따로 둔다.
// 글 안의 **굵게** 와 주소(→ 「기사」 링크)만 받는다 — 그 밖의 표시는 글자 그대로
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/https?:\/\/[^\s)]+/g, u => `<a href="${u}" target="_blank" rel="noopener">기사</a>`);   // 주소는 「기사」 링크로 — 좁은 폭에서 긴 주소가 칸을 넘는다
const list = xs => `<ul>${xs.map(x => typeof x === 'string' ? `<li>${fmt(x)}</li>` : `<li>${fmt(x.t)}${x.sub ? list(x.sub) : ''}</li>`).join('')}</ul>`;
(async () => {
  const box = document.getElementById('note');
  if (!box) return;
  let N;
  try { N = await (await fetch('data/market-note.json', { cache: 'no-store' })).json(); }
  catch (e) { box.innerHTML = '<span class="err">세션이 쓴 시황을 읽지 못했습니다 — data/market-note.json</span>'; return; }
  box.innerHTML = `<div class="cap">이 화면의 값을 읽고 쓴 글 · 쓴 이 ${esc(N.by)} · ${esc(N.writtenAt)} 씀 · 값 기준 ${esc(N.basis)} — 그 뒤 아래 그래프 값과 다를 수 있다</div>`
    + `<h3>한 줄 요지</h3><p class="one">${fmt(N.one)}</p>`
    + N.sections.map(s => `<h3>${fmt(s.h)}</h3>${list([...s.items, ...(s.read ? [{ t: `**읽기:** ${s.read}` }] : [])])}`).join('')
    + `<h3>앞으로 볼 것</h3>${list(N.next)}`
    + `<h3>한계</h3>${list(N.limits)}`;
})();
