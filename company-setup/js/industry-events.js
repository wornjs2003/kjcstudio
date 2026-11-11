// 산업 분석 「이벤트」 칩 — 사건 → 국내 수혜 · 피해 섹터 표(2026-11-11 재권님 「맞아 이대로 만들어」 · 「맨 왼쪽으로 이벤트라고 넣어줘」 · 시안 temp/시황분석-ev7)
// 값은 data/event-impact.json(사건 · 수혜 · 피해 · 연쇄 · 근거) · data/industry-topics.json(섹터 이름) 그대로 — 이름 · 섹터를 코드에 두지 않는다.
// 연쇄(chain)는 근거 없는 세션 판단이라 격자에서 옅게 · 괄호로, 카드에서 「세션 판단」 을 밝힌다(개념정의 검수 덧 11-11).
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const CHK = { '검색 요약': '원문 못 열고 검색 요약만 봄', '원문 읽음': '원문 읽음', '우리 셈': '우리 셈', '세션 판단': '세션 판단(근거 없음)' };

export function renderEvents(box, d, topics) {
  if (!d) { box.innerHTML = '<h1>이벤트</h1><p class="sub">사건 표(data/event-impact.json)를 못 받음</p>'; box.hidden = false; return; }
  const secs = [...topics.sectors.map((s) => s.name), '여러 섹터'];
  const evs = d.axes.flatMap((a, i) => ['up', 'down'].filter((k) => a[k]).map((k) => ({ ...a[k], ax: i })));
  const evAx = Object.fromEntries(evs.map((e) => [e.event, e.ax]));
  const mark = (e, s) => {
    const g = e.good.some((x) => x.sector === s), b = e.bad.some((x) => x.sector === s);
    if (g || b) return g && b ? ['pm', '±'] : g ? ['p', '＋'] : ['m', '−'];
    const ch = (e.chain || []).filter((x) => x.sector === s);
    const g2 = ch.some((x) => x.effect === 'good'), b2 = ch.some((x) => x.effect === 'bad');
    return g2 && b2 ? ['pm2', '(±)'] : g2 ? ['p2', '(＋)'] : b2 ? ['m2', '(−)'] : ['', ''];
  };
  const item = (x, c) => `<div class="evx-it"><span class="evx-chip ${c}">${esc(x.sector)}</span><span class="t">${esc(x.topic)}</span>${x.stocks.length ? `<span class="s">${esc(x.stocks.join(' · '))}</span>` : ''}</div>`;
  const chain = (e) => (e.chain || []).length
    ? e.chain.map((x) => `<div class="evx-ch"><span class="via">${esc(x.via)} →</span> <span class="to ${x.effect === 'good' ? 'g' : 'b'}">${x.effect === 'good' ? '수혜' : '피해'} ${esc(x.topic)}</span>${x.stocks.length ? ` <span class="s">${esc(x.stocks.join(' · '))}</span>` : ''}${x.link && evAx[x.link] != null ? `<a class="lk" href="#evx-ax${evAx[x.link]}">「${esc(x.link)}」 ${x.reverse ? '거꾸로' : '카드'} ›</a>` : ''}</div>`).join('')
      + `<div class="evx-none">연쇄는 ${[...new Set(e.chain.map((x) => CHK[x.checked] || x.checked))].join(' · ')}</div>`
    : '<div class="evx-none">—</div>';
  const side = (e) => !e ? '' : `<div class="evx-side"><div class="ev">${esc(e.event)}<span>${esc(e.dir)}</span></div>
    <div class="evx-lab g">수혜</div>${e.good.length ? e.good.map((x) => item(x, 'g')).join('') : '<div class="evx-none">—</div>'}
    <div class="evx-lab b">피해</div>${e.bad.length ? e.bad.map((x) => item(x, 'b')).join('') : '<div class="evx-none">—</div>'}
    <div class="evx-lab c">연쇄 — 거쳐서 닿는 곳</div>${chain(e)}
    <div class="evx-note">${esc(e.note)}</div>
    <details><summary>근거 ${e.basis.length ? e.basis.length + '개' : '없음 — 세션 판단'}</summary>${e.basis.map((b) => `<div><a href="${esc(b.url)}">${esc(b.source)}</a> — ${esc(CHK[b.checked] || b.checked)}</div>`).join('')}</details></div>`;
  let h = `<h1>사건 → 국내 수혜 · 피해 섹터</h1><p class="sub">사건 ${evs.length}개(축 ${d.axes.length}) · 섹터 = WICS 대분류 · ＋ 수혜 · − 피해 · 칸을 누르면 그 카드로 · 섹터 배정 · 종목은 세션 안 · 근거는 카드마다</p>
    <div class="evx-gh">한눈에 — 섹터 × 사건<small>위에서 보고 칸을 눌러 아래 카드로</small></div>
    <div class="evx-box"><div class="evx-scroll"><table class="evx-mx"><tr><th class="sec">섹터</th>${evs.map((e) => `<th>${esc(e.event.replace(/\(.*\)/, '')).replace(' · ', '<br>')}</th>`).join('')}</tr>`
    + secs.map((s) => `<tr><td class="sec">${esc(s)}</td>${evs.map((e) => { const [c, t] = mark(e, s); return `<td class="${c}">${t ? `<a href="#evx-ax${e.ax}">${t}</a>` : ''}</td>`; }).join('')}</tr>`).join('')
    + `</table></div><div class="evx-leg">＋ 그 사건이 그 섹터에 수혜 · − 피해 · ± 같은 섹터 안에서 갈림(업종마다 다름) · 괄호 (＋)(−) = 연쇄(다른 길을 거쳐 늦게 · 약하게 닿음 · 세션 판단) · 빈칸 = 표에 안 적음</div></div>`;
  d.groups.forEach((g) => {
    const as = d.axes.map((a, i) => [a, i]).filter(([a]) => a.group === g);
    if (!as.length) return;
    h += `<div class="evx-gh">${esc(g)}<small>${esc(as.map(([a]) => a.axis).join(' · '))}</small></div><div class="evx-grid">`
      + as.map(([a, i]) => `<div class="evx-ax" id="evx-ax${i}"><h3>${esc(a.axis)}</h3><div class="evx-two ${a.up && a.down ? 'both' : ''}">${side(a.up)}${side(a.down)}</div></div>`).join('') + '</div>';
  });
  box.innerHTML = `<div class="evx-wrap">${h}</div>`;
  box.hidden = false;
}
