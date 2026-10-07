// 종목 분석 문서의 용어 풍선 — data/glossary.json(한 곳)을 읽어, 문서에 나오는 낱말에 마우스를 올리면(폰은 눌러서) 뜻 · 출처가 뜬다.
// (2026-10-07 재권님 「용어집을 종목분석에 있는 말이 있으면 마우스 올리면 설명으로 뜨도록 … 없으면 같이 있어도 되는 칸 찾아서 용어 넣고 설명」 · 창구 경유)
//   · 재료는 시황분석1 조사(temp/시황분석1-glossary.html) → company-setup/tools/glossary-from-html.py → data/glossary.json. 글은 JSON 에만 있다.
//   · 출처 못 찾은 낱말(missing)은 빨간 줄 「권위 출처 못 찾음 — 우리 정의」 를 그대로 보인다 · 원문을 직접 못 연 것(weak)은 「원문 확인 필요」.
//   · 문서의 정의 · 낱말은 안 바꾼다 — 풍선만 얹는다. 긴 글자부터 맞춘다(「손절가」 가 「손절」 보다 먼저).
//   · 한글 낱말은 조사가 붙어도 찾는다(「눌림에」 · 「보류다」) — 다만 앞뒤가 한글 글자로 이어지는 것(「지지선」 안의 「지지」)은 그 긴 낱말이 따로 맞는다.
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const SKIP = new Set(['CODE', 'A', 'SCRIPT', 'STYLE', 'H1', 'H2', 'H3', 'SUMMARY', 'TEXTAREA', 'SELECT', 'OPTION', 'BUTTON']);   // 제목은 안 감싼다
// flex + gap 인 칸(.in-vt-box-v · .in-vt-verdict · .in-vt-meta · .in-vt-chips)은 감싸면 글자 사이가 벌어진다(2026-10-07 실측 「손익비 가」) — 안 감싼다
const SKIP_CLS = ['in-pill', 'in-src', 'in-term', 'in-term-tip', 'in-vt-stat-v', 'in-vt-price', 'in-vt-tags', 'in-vt-box-v', 'in-vt-verdict', 'in-vt-meta', 'in-vt-chips', 'kh-chip', 'rp-toc-card'];
const JOSA = '에이가은는을를의도로와과만다든';   // 낱말 뒤에 붙어도 같은 낱말로 치는 조사

function pattern(m) {
  const e = m.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const ko = /[가-힣]/.test(m);
  if (ko) return `(?<![가-힣A-Za-z])${e}(?=$|[^가-힣]|[${JOSA}](?![가-힣]))`;
  return `(?<![A-Za-z0-9%+−])${e}(?![A-Za-z0-9])`;
}

function tipHtml(it) {
  const q = it.quotes.map((x) => `<blockquote>${esc(x.text)}</blockquote><div class="in-term-src">${x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.source)} ›</a>` : esc(x.source)}</div>`).join('');
  const miss = it.missing ? `<div class="in-term-none">권위 출처 못 찾음 — 우리 정의. ${esc(it.missing.replace(/^출처 못 찾음 —\s*/, ''))}</div>` : '';
  const weak = it.weak ? `<div class="in-term-none">원문을 직접 못 열어 본 인용 — 확인 필요</div>` : '';
  const note = it.note.length ? `<p class="in-term-note">${it.note.map(esc).join('<br>')}</p>` : '';
  return `<div class="in-term-tip" role="tooltip"><b class="in-term-h">${esc(it.term)}</b>${it.aliases && it.aliases !== '—' ? `<div class="in-term-kv"><span>다른 이름</span>${esc(it.aliases)}</div>` : ''}${q}${miss}${weak}${it.cell ? `<div class="in-term-kv"><span>리포트 칸</span>${esc(it.cell)}</div>` : ''}${note}</div>`;
}

function wrap(root, items) {
  const parts = [];
  items.forEach((it, idx) => it.match.forEach((m) => parts.push({ m, idx })));
  parts.sort((a, b) => b.m.length - a.m.length);
  const re = new RegExp(parts.map((p) => `(${pattern(p.m)})`).join('|'), 'g');
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode(n) {
    let p = n.parentElement;
    for (; p && p !== root; p = p.parentElement) {
      if (SKIP.has(p.tagName) || SKIP_CLS.some((c) => p.classList.contains(c))) return NodeFilter.FILTER_REJECT;
    }
    return /\S/.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
  } });
  const nodes = []; for (let n = walker.nextNode(); n; n = walker.nextNode()) nodes.push(n);
  let count = 0;
  for (const n of nodes) {
    const text = n.nodeValue; re.lastIndex = 0; let last = 0, mm; const frag = document.createDocumentFragment(); let hit = false;
    while ((mm = re.exec(text))) {
      const gi = mm.slice(1).findIndex((g) => g !== undefined); const it = items[parts[gi].idx];
      if (mm.index > last) frag.appendChild(document.createTextNode(text.slice(last, mm.index)));
      const sp = document.createElement('span'); sp.className = 'in-term'; sp.tabIndex = 0; sp.dataset.term = it.id; sp.textContent = mm[0];
      frag.appendChild(sp); last = mm.index + mm[0].length; hit = true; count++;
    }
    if (!hit) continue;
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    n.parentNode.replaceChild(frag, n);
  }
  return count;
}

let open = null;
function show(sp, items) {
  if (open) { open.remove(); open = null; }
  const it = items.find((x) => x.id === sp.dataset.term); if (!it) return;
  sp.insertAdjacentHTML('beforeend', tipHtml(it)); open = sp.lastElementChild;
  // 화면 안에 들어오게 — 왼쪽은 낱말 자리에서 시작하되 오른쪽이 넘치면 왼쪽으로 밀고, 왼쪽도 넘치면 8px 안쪽으로(폰 · 표 칸 안)
  const sr = sp.getBoundingClientRect(); const w = open.offsetWidth; let left = 0;
  if (sr.left + w > window.innerWidth - 8) left = window.innerWidth - 8 - w - sr.left;
  if (sr.left + left < 8) left = 8 - sr.left;
  open.style.left = `${Math.round(left)}px`;
  const r = open.getBoundingClientRect();
  if (r.bottom > window.innerHeight - 8 && r.top > r.height + 16) open.classList.add('up');
}
function hide() { if (open) { open.remove(); open = null; } }

(async () => {
  const root = document.getElementById('in-doc'); if (!root) return;
  let g; try { g = await (await fetch('data/glossary.json', { cache: 'no-store' })).json(); } catch { return; }
  const items = g.items || [];
  const n = wrap(root, items);
  root.dataset.terms = String(n);          // 몇 자리에 풍선이 달렸나 — 검사용
  const fine = window.matchMedia('(hover: hover)').matches;
  root.addEventListener('mouseover', (e) => { if (!fine) return; const sp = e.target.closest('.in-term'); if (sp && !sp.contains(open)) show(sp, items); });
  root.addEventListener('mouseout', (e) => { if (!fine) return; const sp = e.target.closest('.in-term'); if (sp && open && sp.contains(open) && !sp.contains(e.relatedTarget)) hide(); });
  root.addEventListener('focusin', (e) => { const sp = e.target.closest('.in-term'); if (sp) show(sp, items); });
  document.addEventListener('click', (e) => {                       // 폰 — 누르면 열고 다른 곳을 누르면 닫는다
    const sp = e.target.closest('.in-term');
    if (e.target.closest('.in-term-tip')) return;                    // 풍선 안(출처 링크)은 그대로
    if (sp) { if (open && sp.contains(open)) hide(); else show(sp, items); } else hide();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
  // 주소에 ?term=낱말 이 있으면 그 낱말로 가서 풍선을 연 채 둔다 — 링크로 가리키기 · 찍어서 보여 드릴 때
  const q = new URLSearchParams(location.search).get('term');
  if (q) { const sp = [...root.querySelectorAll('.in-term')].find((x) => x.dataset.term.startsWith(q) || x.textContent === q); if (sp) { sp.scrollIntoView({ block: 'center' }); show(sp, items); } }
})();
