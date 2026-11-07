// 용어 풍선 — 모든 화면이 함께 쓴다. 뜻은 data/glossary.json 한 곳에만 있다 (2026-10-12 재권님 「설명만 해놓는 문서 만들어 놓고
// 거기에서 불러오도록 … 하나 써놓으면 전체 페이지에 다 들어가도록」). 룰은 CLAUDE.md 「용어 설명은 한 곳에만 쓴다」.
//   · 화면은 이 파일 한 줄만 건다:  <script type="module" src="/assets/js/glossary.js"></script>   (모양 파일은 이 코드가 스스로 건다)
//   · (가) 표시 — <span data-term="RSI">RSI</span>. 다시 그리는 화면 · 칸 크기가 민감한 화면(홀딩스)
//   · (나) 자동 — 글 덩어리에 data-glossary 를 달면 그 안의 낱말을 찾아 감싼다(문서 · 리포트). 건너뛸 칸은 data-no-glossary,
//     또는 그 덩어리에 data-glossary-skip=".클래스,…" — 클래스 이름은 화면이 들고 이 파일에 박지 않는다
//   · 나중에 그린 칸은 import { wrap } 해서 wrap(칸) 을 부르거나, data-term 으로 달면 된다 — 풍선은 document 에 한 번만 건다
//   · 낱말 경계로만 찾는다 — 영문 약어(MA · PER)는 앞뒤가 영문 · 숫자면 안 걸리고, 한글은 앞이 한글 · 영문 · 숫자면 안 걸리며
//     조사가 붙은 것까지만 같은 낱말이다(「11차 지지」 의 「1차 지지」 · 「1224선」 의 「224선」 은 안 걸린다)
//   · 옛 자리(company-setup/js/glossary.js · 2026-10-07)에서 옮겼다
//   · (다) 그 자리 설명 글 — 용어집 항목이 아닌 한 줄 설명(「즐겨찾기에 담기」 · 잘린 이름 전체)은 data-tip="글"(글자 그대로 · \n 줄바꿈) ·
//     머리 줄은 data-tip-h="머리" · <code> 같은 꼴이 필요하면 data-tip-ref="#아이디" 로 같은 화면의 숨은 <template id> 안 html 을 쓴다.
//     title= · CSS :hover 자체 풍선을 쓰지 않는다 — 같은 .gl-tip · 같은 1초 · 같은 길게 누르기 (2026-11-07 개발1 · 시황분석 물음)
const DATA = new URL('../../data/glossary.json', import.meta.url);
const CSS = new URL('../css/glossary.css', import.meta.url);
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const SKIP = new Set(['CODE', 'PRE', 'A', 'SCRIPT', 'STYLE', 'H1', 'H2', 'H3', 'SUMMARY', 'TEXTAREA', 'INPUT', 'SELECT', 'OPTION', 'BUTTON']);
const JOSA = '에이가은는을를의도로와과만다든';   // 낱말 뒤에 붙어도 같은 낱말로 치는 조사

/* 설명 풍선이 뜨는 때 — 한 곳 (CLAUDE.md 「설명 풍선은 그 단추 · 종목 · 낱말 위에 마우스를 1초 올려 두면 뜬다」 · 2026-11-07 재권님 「1초이상」).
   다른 풍선 코드(holdings/js/components/company-tip.js 등)는 이것을 import 해 쓴다 — 화면 코드에 숫자를 두지 않는다 */
export const HOVER_DELAY_MS = 1000;   // 마우스를 올려 두고 이만큼 머무르면 뜬다 — 그 전에 벗어나면 안 뜬다
export const LONG_MS = 450;           // 터치 — 이만큼 길게 누르면 뜬다(회사 풍선 company-tip.js 에서 옮긴 값 그대로) · 짧게 누르기는 그 자리 본래 일
const ANCHOR = '[data-term],[data-tip],[data-tip-ref]';   // 풍선을 다는 자리 — 용어(data-term) · 그 자리 설명 글(data-tip · data-tip-ref)

let items = [], byId = new Map(), re = null, parts = [];
const ready = load();

async function load() {
  if (!document.querySelector(`link[href="${CSS.pathname}"]`)) {
    const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = CSS.pathname; document.head.appendChild(l);
  }
  try { items = (await (await fetch(DATA, { cache: 'no-store' })).json()).items || []; } catch { items = []; }
  byId = new Map(items.map((it) => [it.id, it]));
  items.forEach((it, idx) => (it.match || []).forEach((m) => parts.push({ m, idx })));
  parts.sort((a, b) => b.m.length - a.m.length);              // 긴 글자부터(「손절가」 가 「손절」 보다 먼저)
  if (parts.length) re = new RegExp(parts.map((p) => `(${pattern(p.m)})`).join('|'), 'g');
}

function pattern(m) {
  const e = m.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  if (/[가-힣]/.test(m)) return `(?<![가-힣A-Za-z0-9])${e}(?=$|[^가-힣]|[${JOSA}](?![가-힣]))`;
  return `(?<![A-Za-z0-9%+−])${e}(?![A-Za-z0-9])`;
}

// 낱말 → 항목. data-term 은 id · term · match 어느 것이든 받는다
function find(key) {
  if (byId.has(key)) return byId.get(key);
  return items.find((it) => it.term === key || (it.match || []).includes(key));
}

export function wrap(root) {
  if (!re || !root) return 0;
  const skipSel = root.dataset.glossarySkip || '';
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode(n) {
    for (let p = n.parentElement; p && p !== root.parentElement; p = p.parentElement) {
      if (SKIP.has(p.tagName) || p.hasAttribute('data-no-glossary') || p.hasAttribute('data-term') || p.classList.contains('gl-tip')) return NodeFilter.FILTER_REJECT;
      if (skipSel && p !== root && p.matches(skipSel)) return NodeFilter.FILTER_REJECT;
    }
    return /\S/.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
  } });
  const nodes = []; for (let n = walker.nextNode(); n; n = walker.nextNode()) nodes.push(n);
  let count = 0;
  for (const n of nodes) {
    const text = n.nodeValue; re.lastIndex = 0; let last = 0, mm, hit = false; const frag = document.createDocumentFragment();
    while ((mm = re.exec(text))) {
      const gi = mm.slice(1).findIndex((g) => g !== undefined); const it = items[parts[gi].idx];
      if (mm.index > last) frag.appendChild(document.createTextNode(text.slice(last, mm.index)));
      const sp = document.createElement('span'); sp.dataset.term = it.id; sp.textContent = mm[0];
      frag.appendChild(sp); last = mm.index + mm[0].length; hit = true; count++;
    }
    if (!hit) continue;
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    n.parentNode.replaceChild(frag, n);
  }
  mark(root);
  root.dataset.terms = String(count);       // 몇 자리에 풍선이 달렸나 — 검사용
  return count;
}

// data-term 표시에 모양 · 초점을 붙인다(손으로 단 것 · 자동으로 단 것 둘 다)
function mark(scope = document) {
  scope.querySelectorAll('[data-term]:not(.gl-term)').forEach((sp) => { sp.classList.add('gl-term'); sp.tabIndex = 0; });
  // 설명 글 자리는 밑줄 없이 키보드로만 닿게 — 단추 · 링크는 원래 닿는다
  scope.querySelectorAll('[data-tip]:not([tabindex]),[data-tip-ref]:not([tabindex])').forEach((el) => {
    if (!el.matches('a[href],button,input,select,textarea')) el.tabIndex = 0;
  });
}

// 그 자리 설명 글 풍선 — 용어집이 아니다. 글은 글자 그대로 넣고(esc) html 은 같은 화면의 숨은 <template> 에서만 받는다
function noteHtml(el) {
  const h = el.dataset.tipH ? `<b class="gl-h">${esc(el.dataset.tipH)}</b>` : '';
  let body = '';
  if (el.dataset.tipRef) { const t = document.querySelector(el.dataset.tipRef); if (t && t.tagName === 'TEMPLATE') body = t.innerHTML; }
  else if (el.dataset.tip) body = `<p class="gl-short">${esc(el.dataset.tip).replace(/\n/g, '<br>')}</p>`;
  return body ? `<div class="gl-tip" role="tooltip">${h}${body}</div>` : '';
}

function tipHtml(it) {
  const q = (it.quotes || []).map((x) => `<blockquote>${esc(x.text)}${x.translated ? '<span class="gl-tr">번역은 세션이 함</span>' : ''}</blockquote>`
    + (x.orig ? `<details class="gl-orig"><summary>원문 보기</summary><p>${esc(x.orig)}</p></details>` : '')
    + `<div class="gl-src">${x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.source)} ›</a>` : esc(x.source)}</div>`).join('');
  const miss = it.missing ? `<div class="gl-none">권위 출처 못 찾음 — 우리 정의. ${esc(it.missing.replace(/^출처 못 찾음 —\s*/, ''))}</div>` : '';
  const weak = it.weak ? '<div class="gl-none">원문을 직접 못 열어 본 인용 — 확인 필요</div>' : '';
  const note = (it.note || []).length ? `<p class="gl-note">${it.note.map(esc).join('<br>')}</p>` : '';
  const al = it.aliases && it.aliases !== '—' ? `<div class="gl-kv"><span>다른 이름</span>${esc(it.aliases)}</div>` : '';
  return `<div class="gl-tip" role="tooltip"><b class="gl-h">${esc(it.term)}</b><p class="gl-short">${esc(it.short)}</p>${al}${q}${miss}${weak}${note}</div>`;
}

/* 풍선은 화면 맨 바깥(body)에 붙이고 낱말 자리에 맞춰 띄운다 (2026-11-07 재권님 「응」 · 개발1 이 찾음).
   전에는 낱말 바로 안에 붙여서, 스크롤 · 넘침 숨김 칸(실시간 순위 · 종목 화면 칸) 안의 낱말이면 칸 가장자리에서 잘렸고
   그 줄의 글씨 크기 · 줄바꿈 안 함도 물려받았다. 스크롤하면 자리가 어긋나므로 닫는다 — 풍선 안 스크롤은 그대로 */
let open = null, openFor = null, hideTimer = 0, showTimer = 0, pending = null;
function show(sp) {
  closeTip();
  let html = '';
  if (sp.dataset.term != null) {
    const it = find(sp.dataset.term); if (!it) return;
    if (!sp.classList.contains('gl-term')) { sp.classList.add('gl-term'); sp.tabIndex = 0; }   // 나중에 그린 표시
    html = tipHtml(it);
  } else html = noteHtml(sp);
  if (!html) return;
  document.body.insertAdjacentHTML('beforeend', html); open = document.body.lastElementChild; openFor = sp;
  // 화면 안에 들어오게 — 아래가 모자라면 낱말 위로, 좌우는 8px 안쪽으로(좁은 폭 · 표 칸 안)
  const sr = sp.getBoundingClientRect(), w = open.offsetWidth, h = open.offsetHeight;
  const left = Math.max(8, Math.min(sr.left, window.innerWidth - 8 - w));
  let top = sr.bottom + 6;
  if (top + h > window.innerHeight - 8) {
    if (sr.top - 6 - h >= 8) { top = sr.top - 6 - h; open.classList.add('up'); }
    else top = Math.max(8, window.innerHeight - 8 - h);   // 위아래 다 모자라면 화면 안에 붙인다 — 넘친 만큼은 풍선 안 스크롤(company-tip 의 place 와 같음 · qa 11-07 좁은 폭 「호가 10단」)
  }
  open.style.left = `${Math.round(left)}px`; open.style.top = `${Math.round(top)}px`;
}
function closeTip() { clearTimeout(hideTimer); if (open) { open.remove(); open = openFor = null; } }   // 열린 풍선만 닫는다 — 다음 낱말을 기다리는 1초는 그대로(qa 11-07 · A 에서 B 로 바로 옮기면 B 가 안 뜨던 것)
function hide() { clearTimeout(showTimer); pending = null; closeTip(); }                                // 기다리는 것까지 다 거둔다 — Esc · 스크롤 · 창 크기 · 바깥 누르기
const inOpen = (n) => !!(open && n instanceof Node && (open.contains(n) || openFor.contains(n)));   // 낱말이나 그 풍선 안

(async () => {
  await ready;
  document.querySelectorAll('[data-glossary]').forEach(wrap);
  mark();
  const fine = window.matchMedia('(hover: hover)').matches;
  /* 마우스 — 1초(HOVER_DELAY_MS) 머무르면 뜬다. 그 전에 벗어나면 취소 · 뜬 뒤 풍선 위로 옮겨도 안 닫는다(출처 링크 · 안 스크롤) */
  document.addEventListener('mouseover', (e) => {
    if (!fine) return;
    if (inOpen(e.target)) { clearTimeout(hideTimer); return; }
    const sp = e.target.closest(ANCHOR);
    if (!sp || sp === pending) return;
    clearTimeout(showTimer); pending = sp;
    showTimer = setTimeout(() => { if (pending === sp && sp.isConnected) show(sp); }, HOVER_DELAY_MS);
  });
  document.addEventListener('mouseout', (e) => {
    if (!fine) return;
    if (pending && pending.contains(e.target) && !pending.contains(e.relatedTarget)) { clearTimeout(showTimer); pending = null; }
    if (!inOpen(e.target) || inOpen(e.relatedTarget)) return;
    clearTimeout(hideTimer); hideTimer = setTimeout(closeTip, 150);    // 낱말과 풍선 사이 6px 틈을 지나는 동안은 기다린다
  });
  /* 키보드(Tab) — 바로 뜬다. 누름으로 생긴 포커스는 안 연다(2026-11-07 qa) */
  let pressed = null;
  document.addEventListener('focusin', (e) => { const sp = e.target.closest(ANCHOR); if (sp && sp !== openFor && sp !== pressed) show(sp); });
  /* 터치 — 길게 누르기(LONG_MS) 하나. 짧게 누르기는 그 자리 본래 일(단추 · 종목 열기)을 한다 · 길게 누른 뒤 따라오는 누르기는 삼킨다 */
  let longTimer = 0, sx = 0, sy = 0, swallow = false;
  document.addEventListener('pointerdown', (e) => {
    pressed = e.target.closest(ANCHOR); swallow = false;   // 새 누르기 — 앞 길게 누르기 뒤 click 이 안 와(스크롤 등) 남은 삼킴 표시를 비운다
    if (e.pointerType === 'mouse') return;
    if (e.target.closest('.gl-tip')) return;
    if (!pressed) { hide(); return; }
    const sp = pressed; sx = e.clientX; sy = e.clientY; clearTimeout(longTimer);
    longTimer = setTimeout(() => { swallow = true; show(sp); }, LONG_MS);
  }, true);
  const cancelLong = () => clearTimeout(longTimer);
  document.addEventListener('pointerup', cancelLong, true);
  document.addEventListener('pointercancel', cancelLong, true);
  document.addEventListener('pointermove', (e) => { if (Math.abs(e.clientX - sx) > 8 || Math.abs(e.clientY - sy) > 8) cancelLong(); }, true);
  document.addEventListener('click', (e) => {
    pressed = null;
    if (swallow) { swallow = false; e.stopPropagation(); e.preventDefault(); return; }
    if (e.target.closest('.gl-tip')) return;                     // 풍선 안(출처 링크 · 원문 보기)은 그대로
    if (open && !inOpen(e.target)) hide();                       // 바깥을 누르면 닫는다
  }, true);
  document.addEventListener('contextmenu', (e) => { if (!fine && e.target.closest(ANCHOR)) e.preventDefault(); });   // 길게 누르기 메뉴 대신 풍선
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
  document.addEventListener('scroll', (e) => { if (open && !open.contains(e.target)) hide(); }, true);   // 칸 · 화면 스크롤
  window.addEventListener('resize', hide);
  // 나중에 그린 칸(순위 표 · 모달)에도 밑줄 · 키보드 닿기를 붙인다 — 그린 뒤 한 번 몰아서(qa 11-07)
  let markQ = 0;
  new MutationObserver(() => { if (!markQ) markQ = requestAnimationFrame(() => { markQ = 0; mark(); }); })
    .observe(document.body, { childList: true, subtree: true });
  // 주소에 ?term=낱말 이 있으면 그 낱말로 가서 풍선을 연 채 둔다 — 링크로 가리키기 · 찍어서 보여 드릴 때
  const q = new URLSearchParams(location.search).get('term');
  if (q) { const sp = [...document.querySelectorAll('.gl-term')].find((x) => x.dataset.term.startsWith(q) || x.textContent === q); if (sp) { sp.scrollIntoView({ block: 'center' }); setTimeout(() => show(sp), 150); } }   // 스크롤이 끝난 뒤 연다 — 스크롤하면 닫히므로
})();
