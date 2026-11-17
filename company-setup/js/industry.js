// 산업 분석 — 섹터 분류 줄 · 「반도체 소부장」 화면 (2026-11-10 재권님 「섹터별로 클릭하면 거기에 섹터별로 정리해야할것들」 → 시안 temp/시황분석-sbx4 → 「응 그렇게 만들어줘」)
// 섹터 · 주제 이름은 data/industry-topics.json · 소부장 화면의 칸 · 판정 규칙 · 근거는 data/industry-sobu.json — 코드에 이름 · 숫자를 두지 않는다.
// 값은 서버(/api/kis/indices · /api/kis/us-board · /api/market/materials · /api/news/stored)와 Insight 자료(trade-flash · external-risk-live)에서 받는다. 못 받은 칸은 「못 받음」(0 으로 두지 않음).
// 판정 = 움직인 방향 × 그 칸의 dir(오르면 소부장에 호재 1 · 악재 -1 · 양면 0). 알약 색은 호재 빨강 · 악재 파랑 · 중립 회색 — 산업 분석 안 판정 색을 이벤트 칩(수혜 · 피해)과 하나로(재권님 「나」 11-11 · 그 전 초록 · 주황).
import { signClass } from '/assets/js/sign.js';
import { renderEvents } from './industry-events.js';

const q = new URLSearchParams(location.search);
const T = q.get('t'), S = q.get('s'), V = q.get('v');   // v=events — 「이벤트」 칩(사건 표)
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (v, dp = 2) => v == null ? '—' : Number(v).toLocaleString('ko-KR', { minimumFractionDigits: dp, maximumFractionDigits: dp });
const pctTxt = (p) => p == null ? '' : (p > 0 ? '+' : '') + p.toFixed(2) + '%';
const round2 = (p) => p == null ? null : Math.round(p * 100) / 100 || 0;

async function get(u) {
  try { const r = await fetch(u, { cache: 'no-cache' }); if (!r.ok) throw new Error(u + ' ' + r.status); return await r.json(); }
  catch (e) { console.warn('[산업 분석] 못 받음', u, e); return null; }
}

function chips(topics) {
  const pages = topics.sectors.flatMap((s) => s.topics.filter((t) => t.page));
  const on = T || (!S && !V && pages[0] && pages[0].page);
  const chip = (href, name, act) => `<a class="kh-chip${act ? ' is-active' : ''}" href="${href}">${esc(name)}</a>`;
  $('[data-ind-chips]').innerHTML = chip('industry.html?v=events', '이벤트', V === 'events')
    + pages.map((t) => chip('industry.html?t=' + encodeURIComponent(t.page), t.name, on === t.page)).join('')
    + topics.sectors.map((s) => chip('industry.html?s=' + encodeURIComponent(s.name), s.name, S === s.name)).join('');
}

// 섹터 칩 — 아직 그 섹터 화면이 없으면 주제 목록과 「준비 중」
function sectorStub(topics) {
  const s = topics.sectors.find((x) => x.name === S);
  if (!s) return;
  $('section.sb').hidden = true;
  const box = $('[data-ind-board]');
  box.innerHTML = `<h1>${esc(s.name)}</h1><p class="sub">섹터 = ${esc(topics.source)} · 이 섹터 화면은 준비 중 — 주제 목록만</p>
    <div class="sw-card"><ul class="ind-topics">${s.topics.map((t) => t.page
      ? `<li><a href="industry.html?t=${encodeURIComponent(t.page)}">${esc(t.name)}</a> <small class="on">있음</small></li>`
      : `<li>${esc(t.name)} <small>준비 중</small></li>`).join('')}</ul></div>`;
  box.hidden = false;
}

// 칸 하나의 값 · 움직임 — 받는 곳마다
function readItem(it, src) {
  const out = { v: null, mv: null, note: '' };
  if (it.src === 'idx') {
    const r = src.idx[it.code];   // /api/kis/indices — 지금 값 · 전날 대비(국내는 장중이면 장중 값 · 미국은 전날 밤 종가)
    if (r && r.value != null) { out.v = r.value; out.mv = round2(r.changePct); }
  } else if (it.src === 'mat') {
    const r = src.mat[it.code];
    if (r) { out.v = r.v; out.mv = round2(r.pct); out.note = (r.at || '').slice(5, 10).replace('-', '.'); }
  } else if (it.src === 'us') {
    const rs = it.codes.map((c) => src.us[c]).filter(Boolean);
    if (rs.length === it.codes.length) {   // 서버 us-board 에 전날 종가 대비가 없어 정규장 시가→종가로 — 칸에 밝힌다
      out.vs = rs.map((r) => r.regularPrice); out.mvs = rs.map((r) => round2((r.regularPrice / r.open - 1) * 100));
      out.v = out.vs[0]; out.mv = round2(out.mvs.reduce((a, b) => a + b, 0) / out.mvs.length); out.note = '시가→종가';
    }
  } else if (it.src === 'trade') {
    // 맨 위 발표가 원문을 못 읽어 품목이 비면 품목 값이 있는 가장 최근 발표로 (2026-11-13 재권님 「응」 — 11-11 발표 PDF 시간 초과로 칸이 비었다)
    let t = null, x = null;
    for (const r of (src.trade && src.trade.items) || []) {
      x = r.items && (r.items[it.side] || []).find((y) => y.name === it.item);
      if (x) { t = r; break; }
    }
    if (x) { out.v = x.amt; out.mv = round2(x.yoy); out.note = (t.period || '') + ' · 전년 대비'; }
  } else if (it.src === 'gpr') {
    const g = src.gpr && src.gpr.gpr;
    const last = g && g[g.length - 1];
    if (last && last[2]) { out.v = last[1]; out.mv = round2((last[1] / last[2] - 1) * 100); out.note = `30일 평균 ${num(last[2], 1)} 대비 · ${last[0].slice(5).replace('-', '.')} 값`; }
  }
  return out;
}

const judge = (mv, dir) => mv == null || !dir ? 0 : Math.sign(mv) * dir;
const pill = (x, none) => none ? '<span class="sw-pill z">못 받음</span>'
  : `<span class="sw-pill ${x > 0 ? 'u' : x < 0 ? 'd' : 'z'}">${x > 0 ? '호재' : x < 0 ? '악재' : '중립'}</span>`;

function tile(it, src) {
  if (it.parts) {   // 환율처럼 두 값을 한 칸에
    const ps = it.parts.map((p) => ({ p, r: readItem(p, src) }));
    const none = ps.every((x) => x.r.v == null);
    return { x: 0, none, it, html: `<div class="sw-t"><div><div class="n">${esc(it.name)}</div>${ps.map(({ p, r }) =>
      `<div class="v2">${esc(p.label)} <b>${num(r.v, 2)}</b> <span class="${signClass(r.mv)}">${pctTxt(r.mv)}</span></div>`).join('')}</div>${pill(0, none)}<div class="why" data-tip="${esc(it.why)}">${esc(it.why)}</div></div>` };
  }
  const r = readItem(it, src), x = judge(r.mv, it.dir), none = r.v == null;
  const val = none ? '—' : it.src === 'us' && r.vs.length > 1 ? r.vs.map((v) => num(v, 2)).join(' · ') : num(r.v, it.src === 'trade' ? 1 : 2) + (it.unit ? `<small>${esc(it.unit)}</small>` : '');
  const mv = it.src === 'us' && r.mvs && r.mvs.length > 1 ? r.mvs.map(pctTxt).join(' · ') : pctTxt(r.mv);
  return { x, none, it, r, html: `<div class="sw-t"><div><div class="n">${esc(it.name)}</div><span class="v">${val}</span><span class="p ${signClass(r.mv)}">${mv}</span></div>${pill(x, none)}
    <div class="why" data-tip="${esc(it.why + (r.note ? ' · ' + r.note : ''))}">${esc(it.why)}${r.note ? ` <span class="sw-stale">· ${esc(r.note)}</span>` : ''}</div></div>` };
}

async function sobu() {
  const def = await get('data/industry-sobu.json');
  if (!def) return;
    const [idx, us, mat, trade, gpr, news] = await Promise.all([
    get('/api/kis/indices'), get('/api/kis/us-board'), get('/api/market/materials'),
    get('data/trade-flash.json'), get('data/external-risk-live.json'), get('/api/news/stored')]);
  const src = {
    idx: Object.fromEntries(((idx && idx.data) || []).map((r) => [r.code, r])), trade, gpr,
    us: Object.fromEntries(((us && us.data) || []).map((r) => [r.code, r])),
    mat: Object.fromEntries(((mat && mat.groups) || []).flatMap((g) => (g.parts || []).flatMap((p) => p.rows || [])).map((r) => [r.code, r])),
  };
  const groups = def.groups.map((g) => ({ g, tiles: g.items.map((it) => tile(it, src)) }));
  const all = groups.flatMap((x) => x.tiles).filter((t) => !t.none);
  const cnt = (ts) => ts.reduce((a, t) => { if (!t.none) a[t.x > 0 ? 0 : t.x < 0 ? 1 : 2]++; return a; }, [0, 0, 0]);
  const [u, dn, z] = cnt(all), n = all.length || 1;
  const ratio = (u + dn) ? u / (u + dn) : 0.5;
  const [word, cls] = ratio >= 0.65 ? ['맑음 — 호재 우세', 'u'] : ratio <= 0.35 ? ['흐림 — 악재 우세', 'd'] : ['구름 조금 — 엇갈림', 'z'];
  const lead = all.filter((t) => t.x > 0 && t.r && t.it.src !== 'trade' && t.it.src !== 'gpr').sort((a, b) => Math.abs(b.r.mv) - Math.abs(a.r.mv)).slice(0, 3);
  const bad = all.filter((t) => t.x < 0);
  const nm = (t) => `${t.it.name} ${pctTxt(t.r.mv)}`;
  const items = (news && news.data) || [];
  const pick = (words) => items.filter((a) => words.some((w) => (a.title || '').includes(w))).slice(0, 5);
  const li = (a) => `<li><a href="${esc(a.link)}" target="_blank" rel="noopener">${esc(a.title)}</a><small>${esc(a.source || '')}</small></li>`;
  const now = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });
  const box = $('[data-ind-board]');
  box.classList.add('sw');
  box.innerHTML = `
  <h2 class="sw-h" style="margin-top:6px">오늘 소부장 날씨<small>값마다 「오르면 소부장에 좋은가」 규칙으로 호재 · 악재를 셈</small></h2>
  <div class="sw-hero">
    <div><div class="k">${now} 에 받은 값</div><div class="big ${cls}">${word}</div>
      <div class="sw-leg">값 ${all.length}개 중 <b class="u">호재 ${u}</b> · <b class="d">악재 ${dn}</b> · 중립 ${z}</div>
      <div class="sw-bar"><i class="u" style="width:${u / n * 100}%"></i><i class="z" style="width:${z / n * 100}%"></i><i class="d" style="width:${dn / n * 100}%"></i></div></div>
    <div class="one">${lead.length ? `<b>이끈 값</b> — ${lead.map(nm).join(' · ')}` : '호재로 움직인 값이 없음'}<br>
      <a href="#sb-table">그때 볼 종목 표 ↓</a><br>
      <span class="sub">${bad.length ? '걸리는 것 — ' + bad.map((t) => t.it.name).join(' · ') : '악재로 움직인 값 없음'}</span></div>
  </div>
  <h2 class="sw-h">지금 시황<small>세계 · 미국장 · 국내 — 칸마다 지금 값 · 등락 · 소부장에 무엇인가</small></h2>
  <div class="sw-cols">${groups.map(({ g, tiles }) => { const [a, b, c] = cnt(tiles);
    return `<div class="sw-col"><h3>${esc(g.title)}</h3><div class="cnt">${esc(g.sub)} · 호재 ${a} · 악재 ${b}${c ? ' · 중립 ' + c : ''}</div>${tiles.map((t) => t.html).join('')}</div>`; }).join('')}</div>
  <h2 class="sw-h">뉴스<small>서버가 쌓은 기사에서 제목 낱말로 고름</small></h2>
  <div class="sw-news">
    <div class="sw-card"><h2>전쟁 · 무역 · 제재 뉴스</h2><ul>${pick(def.newsWords.world).map(li).join('') || '<li>—</li>'}</ul></div>
    <div class="sw-card"><h2>소부장 호재 뉴스 — 투자 · 수주 · 증설</h2><ul>${pick(def.newsWords.good).map(li).join('') || '<li>—</li>'}</ul>
      <div class="sw-stale">제목 낱말로 고름 — 호재가 아닌 기사가 섞일 수 있음</div></div>
  </div>
  <h2 class="sw-h">근거<small>증권가 · 기관 자료</small></h2>
  <details class="sw-fold"><summary>왜 이게 호재인가<span class="s">증권가 · 기관이 꼽은 소부장 호재 ${def.research.length}가지 · 원문 읽음 ${def.research.filter((r) => r.checked === '원문 읽음').length} · 검색 요약 ${def.research.filter((r) => r.checked !== '원문 읽음').length}</span></summary>
    <div class="sw-scroll"><table><tr><th>호재</th><th>왜</th><th>출처</th><th>확인</th></tr>${def.research.map((r) =>
      `<tr><td><b>${esc(r.name)}</b></td><td>${esc(r.why)}</td><td><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.source)}</a></td><td>${esc(r.checked)}</td></tr>`).join('')}</table></div>
    <div class="sw-stale">같은 자료가 꼽는 악재 — ${esc(def.researchBad)} · 판정 규칙(오르면 호재/악재)은 세션이 쓴 안</div></details>
  <h2 class="sw-h" id="sb-table">그때 볼 종목<small>3년 성장 소부장 — 아래 표</small></h2>`;
  box.hidden = false;
}

async function main() {
  const topics = await get('data/industry-topics.json');
  if (!topics) return;   // 목록을 못 받으면 소부장 표만 그대로
  chips(topics);
  if (S) return sectorStub(topics);
  if (V === 'events') { $('section.sb').hidden = true; return renderEvents($('[data-ind-board]'), await get('data/event-impact.json'), topics); }
  await sobu();
}
main();
