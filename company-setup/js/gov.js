// 종목 분석 — 「분석」 · 「지배구조」 두 갈래 (2026-11-05 재권님 「종목분석에다가 지금 있는 내용은 분석 그리고 지배구조 라고 하나 만들어.
// 지배구조는 종목별로 지분관계라든가 회사간의 관계를 정리해놓을려고해」 → 흐름도 시안 → 「삼성전자 현대차 등등 표기해줘야 할 종목이 여러개니까」 →
// 「응 이런식으로 해서 우리나라 상장사들 다 찾아서 지배구조 넣어놔」).
//
// 값은 서버 한 곳에서 받는다(루트 「두 구역이 같은 값을 쓰면」) — OpenDART 사업보고서의 두 표를 서버가 상장사마다 받아 둔다.
//   GET /api/dart/gov?code=<6자리>   → data: { code, name, year, major:[최대주주 현황 원문 줄], invest:[타법인 출자 현황 원문 줄] } · 안 받았으면 data:null
//                                      줄마다 matchedCode — 서버가 맞춘 상장사 6자리 · 못 맞추면 null(맞추는 셈은 서버 한 곳 · 화면은 안 맞춘다 · 2026-11-05 개념정의 검수)
//   GET /api/dart/gov/links          → data: { edges, names:{code:name}, heads:{code:[최대주주 이름, 상장사 code|null, 지분%]},
//                                      groups:[{ top(사람 · 비상장 이름|null), holding(code), cycle:[code…], members:[{ code, parent, pct, depth }] }] } · meta: { done, total }
// 화면은 원문 줄을 갈래로 나눠 흐름도 자료(flowmap.html 의 지도 모양 · data/maps/README.md)를 만들고, 흐름도 틀에 postMessage 로 넘긴다.
// 「지배구조 상위」 는 서버가 셈한 links.groups 다 — 종목마다 최대주주를 위로 따라가 닿는 끝(사람 · 비상장 아래 첫 상장사, 또는 서로 물린 고리째).
//   삼성전자 → 삼성생명 → 삼성물산 → 이재용 이면 상위 삼성물산 · 맨 위 이재용. SK하이닉스 → SK스퀘어 → SK → 최태원 이면 상위 SK(2026-11-05 재권님
//   「하이닉스도 sk 계열사 중에 하난데 모회사처럼 해줘서」 → 서버 groups · 개발1). 셈은 서버 한 곳 — 화면은 다시 셈하지 않는다.
//   그룹 이름을 짐작해 붙이지 않는다 — 상위 회사 이름으로 부른다
//   (2026-11-05 재권님 「재배구조의 상위가 거기 있어야 되고 그걸 클릭하면 그 종목과 엮인 다른 종목들이 보여줘야」).
// 못 받은 값은 0 · 빈칸으로 메우지 않고 「아직」 · — 로 낸다.
const $ = (s, r = document) => r.querySelector(s);
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const show = (n) => String(n || '').replace(/㈜|\(주\)|\n/g, '').replace(/(?<=[가-힣]) (?=[가-힣](\s|$))/g, '').trim();   // 「이 재 용」 → 「이재용」
const num = (v) => { const x = parseFloat(String(v ?? '').replace(/,/g, '')); return Number.isFinite(x) ? x : null; };
const pc = (p) => p == null ? '' : ` ${+p.toFixed(1)}%`;
const COMMON = new Set(['보통주', '의결권있는주식']);   // 띄어쓰기를 빼고 견준다 — 「보통주」 · 「의결권 있는 주식」 · 「의결권있는 주식」(SK스퀘어) 셋 다(2026-11-05 실측 · 개발1)
const isCommon = (k) => COMMON.has(String(k || '').replace(/\s/g, ''));
const SUM = new Set(['계', '합계']);

async function api(u) {
  const r = await fetch(u, { cache: 'no-store' });
  if (!r.ok) throw new Error(`${u} ${r.status}`);
  return r.json();
}

// ── 원문 줄 → 갈래 ──
function holderKind(t) {
  t = t || '';
  if (/본인|^최대주주$/.test(t)) return '최대주주 본인';   // 회사마다 「최대주주 본인」 · 「본인」 · 「최대주주」 (2026-11-05 실측)
  if (/임원/.test(t)) return '임원';
  if (/재단|비영리/.test(t)) return '재단';
  if (/계열/.test(t)) return '계열회사';
  return '특수관계인';
}
function split(d) {
  const major = (d.major || []).filter((r) => isCommon(r.stock_knd));
  const total = major.find((r) => SUM.has(r.nm));
  const H = {};
  for (const r of major) {
    if (SUM.has(r.nm) || !r.relate) continue;
    const k = holderKind(r.relate), n = show(r.nm).replace('(특별계정)', '');
    const o = (H[k] ||= new Map()).get(n) || { v: 0, code: null };
    o.v += num(r.trmend_posesn_stock_qota_rt) || 0; o.code = o.code || r.matchedCode || null; H[k].set(n, o);
  }
  const B = { sub: [], rel: [], part: [], abroad: [], fund: [], simple: [] };
  for (const r of d.invest || []) {
    const n = r.inv_prm; if (!n || SUM.has(n)) continue;
    const p = num(r.trmend_blce_qota_rt), it = { n: show(n), p, code: r.matchedCode || null };   // 영문 약칭(해외 법인 「HMM」 등)은 상장사 이름과 우연히 같다 — 한글 이름만 맞춘다(2026-11-05 시험에서 현대차 해외 법인 HMM 이 상장사 HMM 으로 붙음)
    if (r.invstmnt_purps !== '경영참여') B.simple.push(it);
    else if (/조합|투자신탁|펀드|사모/.test(n)) B.fund.push(it);
    else if (!/[가-힣]/.test(n)) B.abroad.push(it);
    else if (p != null && p > 50) B.sub.push(it);
    else if (p != null && p >= 20) B.rel.push(it);
    else B.part.push(it);
  }
  Object.values(B).forEach((L) => L.sort((a, b) => (b.p ?? -1) - (a.p ?? -1)));
  return { H, B, total: total ? num(total.trmend_posesn_stock_qota_rt) : null, investN: Object.values(B).reduce((s, L) => s + L.length, 0) };
}

// ── 흐름도 자료(flowmap 지도 모양) ──
function mapOf(d, S) {
  const listed = (o) => o.code ? '▶ ' : '';
  const hold = ['최대주주 본인', '계열회사', '특수관계인', '재단', '임원'].filter((k) => S.H[k]).map((k, i) => {
    const L = [...S.H[k]].sort((a, b) => b[1].v - a[1].v), sum = L.reduce((s, x) => s + x[1].v, 0);
    if (k === '임원' && L.length > 3) return { id: 'h' + i, type: 'node', k, t: `${L.length}명`, d: `합 ${sum.toFixed(2)}%` };
    return { id: 'h' + i, type: 'node', k, t: L.slice(0, 4).map(([n, o]) => listed(o) + n).join(' · ') + (L.length > 4 ? ` 외 ${L.length - 4}` : ''),
      d: L.slice(0, 4).map(([n, o]) => `${n} ${o.v.toFixed(2)}%`).join(' · ') + (L.length > 1 ? ` · 합 ${sum.toFixed(2)}%` : '') };
  });
  const few = (L, c) => L.slice(0, c).map((x) => x.n + pc(x.p)).join(' · ') + (L.length > c ? ` 외 ${L.length - c}곳` : '');
  const r1 = [['sub', '자회사 — 50% 넘게'], ['rel', '관계회사 — 20~50%'], ['part', '경영참여 — 20% 아래']].filter(([k]) => S.B[k].length)
    .map(([k, lab]) => ({ id: k, type: 'cell', k: `${lab} · ${S.B[k].length}곳`, t: '' }));
  const r2 = [['abroad', '해외 법인', '해외 판매 · 생산 법인', 8], ['fund', '투자조합 · 펀드', '조합 · 사모 펀드', 3], ['simple', '단순투자', '지배 목적 아님', 5]]
    .filter(([k]) => S.B[k].length).map(([k, lab, t, c]) => ({ id: k, type: 'node', k: `${lab} ${S.B[k].length}곳`, t, d: few(S.B[k], c) }));
  const me = { id: 'me', type: 'node', k: d.code, t: d.name, d: `최대주주 + 특수관계인 보통주 ${S.total != null ? S.total + '%' : '—'}` };
  return {
    id: 'gov-' + d.code, title: `${d.name} 지배구조`, asOf: `DART ${d.year} 사업보고서`, note: `DART 최대주주 현황 · 타법인 출자 현황(${d.year} 사업보고서)`,
    columns: [{ head: '주주 — 누가 가졌나 · 보통주', items: hold.length ? hold : [{ id: 'h0', type: 'node', k: '아직', t: '주주 표 없음', d: '사업보고서에 최대주주 현황이 없다' }] },
      { head: '이 회사', items: [me] },
      ...(r1.length ? [{ head: '가진 회사 — 경영참여 · 국내', items: r1 }] : []),
      ...(r2.length ? [{ head: '가진 회사 — 그 밖', items: r2 }] : [])],
    lineTypes: { own: { label: '주주 → 이 회사', color: 'accent' }, ctl: { label: '경영참여', color: 'ok' }, etc: { label: '그 밖 출자', color: 'warn' } },
    links: [...(hold.length ? hold : [{ id: 'h0' }]).map((h) => [h.id, 'me', 'own']), ...r1.map((x) => ['me', x.id, 'ctl']), ...r2.map((x) => ['me', x.id, 'etc'])],
    extra: [], info: {}, grades: { sub: '자회사', rel: '관계회사', part: '참여', listed: '상장' },
    stocks: ['sub', 'rel', 'part'].flatMap((k) => S.B[k].map((x) => ({ name: x.n + pc(x.p), code: x.code, node: k, grade: x.code ? 'listed' : k, market: 'KR' }))),
  };
}


const box = $('[data-gov]'), art = $('#in-doc');
let LINKS = null, NAMES = {}, HEADS = {}, TOP = new Map(), GROUPS = [], view = 'flow', cur = null, curTop = null, frameMap = null;
const nm = (c) => NAMES[c] || c;

// ── 지배구조 상위 — 서버가 셈한 묶음(links.groups)을 그대로 쓴다 · 화면은 다시 셈하지 않는다 ──
const gid = (g) => g.holding || 'cycle:' + [...(g.cycle || [])].sort().join('-');
function buildTops() {
  TOP = new Map();
  GROUPS = (LINKS.groups || []).map((g) => ({ ...g, id: gid(g), by: new Map((g.members || []).map((m) => [m.code, m])) }));
  for (const g of GROUPS) for (const m of g.members || []) TOP.set(m.code, g.id);
}
const topName = (g) => g.cycle && g.cycle.length ? g.cycle.map(nm).join(' · ') : nm(g.holding);
const codesOf = (g) => (g.members || []).map((m) => m.code);
function pathOf(g, c) {   // 그 종목에서 최대주주 상장사(parent)를 따라 위로 — 묶음 안에서만
  const out = [c], seen = new Set([c]);
  for (let m = g.by.get(c); m && m.parent && g.by.has(m.parent) && !seen.has(m.parent); m = g.by.get(m.parent)) { out.push(m.parent); seen.add(m.parent); }
  return out.reverse();
}

// 상위 하나의 흐름도 — 맨 위(사람 · 비상장) → 지주 · 고리(depth 0) → 그 아래 단마다 한 칸
function groupMap(g) {
  const cols = [];
  for (const m of g.members || []) (cols[(m.depth ?? 0)] ||= []).push(m);
  const node = (m) => ({ id: 'c' + m.code, type: 'node', k: m.code, t: nm(m.code),
    d: m.parent ? `최대주주 ${nm(m.parent)} ${m.pct ?? '—'}%` : (HEADS[m.code] ? `최대주주 ${HEADS[m.code][0]} ${HEADS[m.code][2] ?? '—'}%` : '최대주주 자료 아직') });
  const columns = [];
  if (g.top) columns.push({ head: '맨 위', items: [{ id: 'apex', type: 'node', k: '최대주주', t: g.top, d: '사람 · 비상장' }] });
  cols.forEach((L, i) => { if (L) columns.push({ head: i === 0 ? (g.cycle && g.cycle.length ? '서로 물린 고리' : '지배구조 상위') : `${i}단 아래`, items: L.map(node) }); });
  const links = [];
  if (g.top) for (const m of (cols[0] || [])) links.push(['apex', 'c' + m.code, 'own']);
  for (const m of g.members || []) if (m.parent && g.by.has(m.parent) && (g.by.get(m.parent).depth ?? 0) < (m.depth ?? 0)) links.push(['c' + m.parent, 'c' + m.code, 'own']);
  return { id: 'gov-top', title: topName(g), asOf: 'DART 사업보고서 · 최대주주', note: '서버가 최대주주 줄로 묶은 것 — 칸 아래 「최대주주 …」 가 그 줄의 지분',
    columns, lineTypes: { own: { label: '최대주주 → 회사', color: 'accent' } }, links, extra: [], info: {}, stocks: [] };
}

function setTab(t) {
  for (const b of document.querySelectorAll('[data-doc-tab]')) b.classList.toggle('is-active', b.dataset.docTab === t);
  for (const el of art.children) {
    if (el.matches('[data-doc-tabs]')) continue;
    if (el === box) el.hidden = t !== 'gov';
    else el.classList.toggle('in-gov-off', t === 'gov');
  }
  const u = new URL(location.href);
  if (t === 'gov') u.searchParams.set('gov', cur || u.searchParams.get('gov') || '005930'); else u.searchParams.delete('gov');
  history.replaceState(null, '', u);
  if (t === 'gov' && !box.dataset.ready) { box.dataset.ready = '1'; start(); }
}

function frame() {
  return `<iframe class="in-gov-frame" data-gov-frame src="flowmap.html?map=parent&view=flow&embed=1" title="지배구조 흐름도"></iframe>`;
}
addEventListener('message', (e) => {
  if (e.origin !== location.origin || !e.data || !e.data.kjcMapReady || !frameMap) return;
  const f = $('[data-gov-frame]', box); if (f && e.source === f.contentWindow) f.contentWindow.postMessage({ kjcMap: frameMap }, location.origin);
});

function table(d, S) {
  const hr = ['최대주주 본인', '계열회사', '특수관계인', '재단', '임원'].filter((k) => S.H[k])
    .flatMap((k) => [...S.H[k]].sort((a, b) => b[1].v - a[1].v).map(([n, { v }]) => `<tr><td>${esc(n)}</td><td>${esc(k)}</td><td class="num">${v.toFixed(2)}%</td></tr>`)).join('');
  const lab = { sub: '자회사', rel: '관계회사', part: '경영참여 20% 아래', abroad: '해외 법인', fund: '투자조합 · 펀드', simple: '단순투자' };
  const ir = Object.entries(S.B).flatMap(([k, L]) => L.map((x) => `<tr><td>${esc(x.n)}${x.code ? ' <span class="in-pill ok">상장</span>' : ''}</td><td>${lab[k]}</td><td class="num">${x.p == null ? '—' : x.p + '%'}</td></tr>`)).join('');
  return `<div class="in-gov-tbls"><div class="in-tblx"><table class="in-tbl"><tr><th>주주</th><th>관계</th><th>보통주 지분</th></tr>${hr || '<tr><td colspan="3">—</td></tr>'}</table></div>
    <div class="in-tblx"><table class="in-tbl"><tr><th>가진 회사</th><th>갈래</th><th>지분</th></tr>${ir || '<tr><td colspan="3">—</td></tr>'}</table></div></div>`;
}

// 줄 셋 — ① 지배구조 상위(맨 위 줄 · 누르면 그 상위) ② 그 상위 아래 종목(누르면 그 종목) ③ 고른 종목의 위로 가는 길
function rows() {
  const tops = $('[data-gov-tops]', box), mem = $('[data-gov-group]', box), path = $('[data-gov-ring]', box);
  const shown = GROUPS.slice(0, 40); const g = GROUPS.find((x) => x.id === curTop);
  if (g && !shown.includes(g)) shown.push(g);
  tops.innerHTML = `<b>지배구조 상위</b>${shown.map((x) => `<button type="button" class="kh-chip${x.id === curTop ? ' is-active' : ''}" data-gov-top="${esc(x.id)}">${esc(topName(x))}<span class="in-gov-n">${(x.members || []).length}</span></button>`).join('')}`
    + (GROUPS.length > shown.length ? `<span class="in-gov-more">외 ${GROUPS.length - shown.length}곳 — 위 찾기 칸으로</span>` : '')
    + (GROUPS.length ? '' : '<span class="in-gov-more">상장사가 둘 이상 매달린 상위가 아직 없다</span>');
  mem.innerHTML = g ? `<b>${esc(topName(g))} 아래</b>${codesOf(g).map((c) => `<button type="button" class="kh-chip${c === cur ? ' is-active' : ''}" data-gov-code="${esc(c)}">${esc(nm(c))}</button>`).join('')}` : '';
  const cg = cur && GROUPS.find((x) => x.id === TOP.get(cur));
  path.innerHTML = cg ? `<b>위에서 이 종목까지</b> — ${cg.top ? `${esc(cg.top)} › ` : ''}${pathOf(cg, cur).map((c) => `<a href="#" data-gov-code="${esc(c)}">${esc(nm(c))}</a>`).join(' › ')}${cg.cycle && cg.cycle.length ? ' (맨 위가 서로 물린 고리)' : ''}` : '';
}

async function drawTop(id) {
  curTop = id; cur = null; rows();
  const g = GROUPS.find((x) => x.id === id), body = $('[data-gov-body]', box), src = $('[data-gov-src]', box);
  if (!g) return;
  src.textContent = `${topName(g)} 아래 상장사 ${(g.members || []).length}곳 — 서버가 최대주주 줄로 묶었다 · 칸 이름 아래 칩을 누르면 그 종목의 주주 · 가진 회사`;
  frameMap = groupMap(g); body.innerHTML = frame();
}

async function draw(code) {
  cur = code; const u = new URL(location.href); u.searchParams.set('gov', code); history.replaceState(null, '', u);
  curTop = TOP.get(code) || null; rows();
  const body = $('[data-gov-body]', box), src = $('[data-gov-src]', box);
  let j;
  try { j = await api(`/api/dart/gov?code=${encodeURIComponent(code)}`); }
  catch (e) { body.innerHTML = `<p class="in-doc-p"><span class="in-pill no">못 받음</span> 서버의 지배구조 주소를 못 읽었습니다(${esc(e.message)})</p>`; src.textContent = ''; return; }
  if (cur !== code) return;
  const d = j.data;
  if (!d) { body.innerHTML = `<p class="in-doc-p"><span class="in-pill no">아직</span> ${esc(nm(code))} 의 사업보고서 두 표를 서버가 아직 받지 않았습니다${j.meta && j.meta.total ? `(${j.meta.done ?? '—'} / ${j.meta.total}곳 받음)` : ''}</p>`; src.textContent = ''; return; }
  const S = split(d);
  src.innerHTML = `DART ${esc(d.year)}년 사업보고서 · 최대주주 현황 · 타법인 출자 현황 ${S.investN}곳 · 서버 ${esc((j.meta && j.meta.fetchedAt) || '')} 받음 · ▶ 붙은 이름 = 상장사`;
  if (view === 'table') { frameMap = null; body.innerHTML = table(d, S); return; }
  frameMap = mapOf(d, S);
  body.innerHTML = frame();
}

async function start() {
  box.innerHTML = `<div class="in-gov-head"><h2>지배구조</h2>
      <span class="in-gov-views"><button type="button" class="kh-chip is-active" data-gov-view="flow">흐름도</button><button type="button" class="kh-chip" data-gov-view="table">표</button></span>
      <label class="in-calc-pick in-gov-find">종목 <input type="search" list="gov-names" placeholder="이름 · 코드" data-gov-find><datalist id="gov-names"></datalist></label></div>
    <div class="in-gov-group in-gov-tops" data-gov-tops></div>
    <div class="in-gov-group" data-gov-group></div>
    <p class="in-rp-note in-gov-ring" data-gov-ring></p>
    <p class="in-rp-note" data-gov-src></p>
    <div class="in-gov-body" data-gov-body></div>`;
  try {
    const j = await api('/api/dart/gov/links');
    LINKS = j.data || {}; NAMES = LINKS.names || {}; HEADS = LINKS.heads || {};
    buildTops();
    $('#gov-names').innerHTML = Object.entries(NAMES).map(([c, n]) => `<option value="${esc(n)} ${esc(c)}">`).join('');
    if (j.meta && j.meta.total && j.meta.done < j.meta.total) $('[data-gov-src]', box).insertAdjacentHTML('beforebegin', `<p class="in-rp-note"><span class="in-pill half">받는 중</span> 서버가 ${j.meta.done} / ${j.meta.total}곳 받았다 — 상위 · 아래 종목은 받은 회사까지만 보인다</p>`);
  } catch (e) {
    $('[data-gov-tops]', box).innerHTML = `<span class="in-pill no">못 받음</span> 상장사 최대주주 줄(/api/dart/gov/links)을 못 읽었습니다`;
  }
  box.addEventListener('click', (e) => {
    const t = e.target.closest('[data-gov-top]'); if (t) { drawTop(t.dataset.govTop); return; }
    const b = e.target.closest('[data-gov-code]'); if (b) { e.preventDefault(); draw(b.dataset.govCode); return; }
    const v = e.target.closest('[data-gov-view]');
    if (v) { view = v.dataset.govView; box.querySelectorAll('[data-gov-view]').forEach((x) => x.classList.toggle('is-active', x === v)); if (cur) draw(cur); else if (curTop) drawTop(curTop); }
  });
  $('[data-gov-find]', box).addEventListener('change', (e) => {
    const m = String(e.target.value).match(/\b(\d{6}|[0-9A-Z]{6})\s*$/) || [null, Object.keys(NAMES).find((c) => NAMES[c] === e.target.value.trim())];
    if (m[1]) { draw(m[1]); e.target.value = ''; }
  });
  const q = new URL(location.href).searchParams;
  if (q.get('govtop')) drawTop(q.get('govtop')); else draw(q.get('gov') || '005930');
}

document.querySelectorAll('[data-doc-tab]').forEach((b) => b.addEventListener('click', () => setTab(b.dataset.docTab)));
if (new URL(location.href).searchParams.get('gov') || new URL(location.href).searchParams.get('govtop')) setTab('gov');
