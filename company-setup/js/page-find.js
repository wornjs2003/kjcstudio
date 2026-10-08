// 종목 분석 화면 찾기 칸 — 낱말을 치고 「찾기」 를 누르면(또는 Enter) 그 자리로 간다 (2026-10-08 재권님 「종목분석 위에 단어 검색하는거 만들어줘」 ·
// 「찾기 버튼누르면 거기로 이동하게」). 종목 리포트 · 분석 문서 두 화면이 함께 쓴다 — 각 화면 HTML 에는 <div data-page-find></div> 자리 하나.
// 찾는 범위는 본문 카드(article) 하나 · 접힌 절(details) 안이면 펼친다 · 같은 낱말을 또 누르면 다음 자리로 · ▲ ▼ 로 앞뒤 · Esc 로 지운다.
// 칠하기는 글 마디를 <mark> 로 감쌌다가 지울 때 풀어 원래 글로 돌린다 — 화면이 다시 그려지면(종목을 바꾸면) 처음부터 다시 찾는다
const box = document.querySelector('[data-page-find]');
if (box) {
  box.className = 'in-find';
  box.innerHTML = `<input type="search" class="in-find-q" placeholder="이 화면에서 찾기 — 예: 산업 성장성" aria-label="이 화면에서 찾기">
    <button type="button" class="in-find-go">찾기</button>
    <button type="button" class="in-find-nav" data-d="-1" aria-label="앞 자리">▲</button><button type="button" class="in-find-nav" data-d="1" aria-label="다음 자리">▼</button>
    <span class="in-find-n" aria-live="polite"></span>`;
  const q = box.querySelector('.in-find-q'), n = box.querySelector('.in-find-n');
  let hits = [], cur = -1, last = '';
  const root = () => document.querySelector('main article') || document.querySelector('main');
  const clear = () => {
    document.querySelectorAll('mark.in-find-hit').forEach((m) => { const p = m.parentNode; p.replaceChild(document.createTextNode(m.textContent), m); p.normalize(); });
    hits = []; cur = -1; n.textContent = '';
  };
  // 띄어쓰기를 못 맞춰도 찾는다(2026-10-08 재권님 「띄워쓰기 못해도 검색되게 해줘」) — 낱말과 글 양쪽에서 빈칸을 빼고 견준 뒤,
  // 찾은 자리를 원래 글의 위치로 되짚어 칠한다(「산업성장성」 으로 쳐도 「산업 성장성」 이 칠해진다). 한 글 마디 안에서만 찾는다
  const squeeze = (s) => { const idx = []; let t = ''; for (let i = 0; i < s.length; i++) if (!/\s/.test(s[i])) { t += s[i].toLowerCase(); idx.push(i); } return { t, idx }; };
  const mark = (word) => {
    const r = root(); if (!r) return;
    const w = word.replace(/\s+/g, '').toLowerCase(); if (!w) return; const nodes = [];
    const tw = document.createTreeWalker(r, NodeFilter.SHOW_TEXT, { acceptNode: (t) => {
      const p = t.parentElement; if (!p || p.closest('script, style, .in-find, canvas')) return NodeFilter.FILTER_REJECT;
      return squeeze(t.nodeValue).t.includes(w) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP; } });
    while (tw.nextNode()) nodes.push(tw.currentNode);
    for (const t of nodes) {
      const s = t.nodeValue, { t: c, idx } = squeeze(s); let i = 0, from = 0, k; const frag = document.createDocumentFragment();
      while ((k = c.indexOf(w, from)) >= 0) {
        const a = idx[k], b = idx[k + w.length - 1] + 1;
        if (a > i) frag.appendChild(document.createTextNode(s.slice(i, a)));
        const m = document.createElement('mark'); m.className = 'in-find-hit'; m.textContent = s.slice(a, b); frag.appendChild(m); hits.push(m);
        i = b; from = k + w.length;
      }
      if (i < s.length) frag.appendChild(document.createTextNode(s.slice(i)));
      t.parentNode.replaceChild(frag, t);
    }
  };
  const go = (d) => {
    if (!hits.length) return;
    if (cur >= 0) hits[cur].classList.remove('is-cur');
    cur = (cur + d + hits.length) % hits.length;
    const m = hits[cur]; m.classList.add('is-cur');
    let p = m.closest('details'); while (p) { p.open = true; p = p.parentElement && p.parentElement.closest('details'); }
    m.scrollIntoView({ block: 'center' });
    n.textContent = `${cur + 1} / ${hits.length}`;
  };
  const find = () => {
    const word = q.value.trim();
    if (!word) { clear(); last = ''; return; }
    if (word.replace(/\s+/g, '') === last.replace(/\s+/g, '') && hits.length && hits[0].isConnected) { go(1); return; }   // 같은 낱말을 또 누르면 다음 자리
    clear(); last = word; mark(word);
    if (!hits.length) { n.textContent = '없음'; return; }
    go(1);
  };
  box.querySelector('.in-find-go').addEventListener('click', find);
  box.querySelectorAll('.in-find-nav').forEach((b) => b.addEventListener('click', () => { if (!hits.length || !hits[0].isConnected) find(); else go(+b.dataset.d); }));
  q.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); if (e.shiftKey && hits.length) go(-1); else find(); }
    else if (e.key === 'Escape') { q.value = ''; clear(); last = ''; }
  });
}
