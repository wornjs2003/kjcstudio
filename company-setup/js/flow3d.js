// 흐름도 3D — 자료 파일에 "flow3d": true 가 있는 지도는 흐름도 칸을 3D 그물로 그린다 (2026-10-07 재권님 — 연관 종목 그물을
// 「흐름도에 대입해줘」 → (가) 흐름도 자체를 3D 로 → 그림 확인 뒤 「응 좋아」).
// 큰 점 = 흐름도의 칸(열 순서대로 왼쪽 → 오른쪽) · 선 = links 그대로(색 = lineTypes) · 작은 점 = stocks(자기 칸 둘레 · 색 = 등급).
// 큰 점을 누르면 flowmap 의 pick() — 오른쪽 패널 · 회사 점은 openCard() — 회사 카드. 둘 다 flowmap.html 의 것을 그대로 쓴다.
// 단추 줄(▶ 흐름 · 선 종류 · 병목 · 시나리오)은 flowmap 이 #map 에 거는 클래스를 읽어 따라간다 — sync() 를 draw() 가 부른다.
// 2D 칸(#map)은 그대로 지어 두고 감춘다 — pick() · 세계 지도 점이 그 칸을 읽는다.
// 라이브러리는 vendor/3d-force-graph.min.js(three 를 안에 품은 한 파일) — 이 지도에서만 그때 불러온다.
// 이 파일은 flowmap.html 의 전역(D · STOCKS · GRADES · TYPES · TOKEN · INFO · EMBED · sel · scenario · pick · openCard · openParts · draw · map · $)을 쓴다.
const Flow3D = (() => {
  let G = null, box = null, tags = null, nodes = [], links = [], label = {}, loading = null;
  const css = () => getComputedStyle(document.documentElement);
  const C = n => css().getPropertyValue(n).trim();
  const rgbVar = n => 'rgb(' + C(n).split(/\s+/).join(',') + ')';
  const GRADE_TOK = ['--accent-rgb', '--kh-ok-rgb', '--kh-warn-rgb', '--kh-danger-rgb'];   // 등급 배지와 같은 차례(.g-1 · .g-2 · .g-3 · .g-4)
  const GAP = 70;   // 열 사이 거리(3D 단위)

  const on = () => !!(D && D.flow3d);
  function load() {
    if (window.ForceGraph3D) return Promise.resolve();
    return loading || (loading = new Promise((ok, no) => {
      const s = document.createElement('script'); s.src = 'vendor/3d-force-graph.min.js'; s.onload = ok; s.onerror = no; document.head.appendChild(s);
    }));
  }
  function data() {
    const colOf = {}, stages = [];
    D.columns.forEach((col, ci) => col.items.forEach(it => {
      if (!it.id) return;
      colOf[it.id] = ci;
      stages.push({ id: it.id, kind: 'stage', name: it.type === 'node' ? `${it.k} · ${it.t}` : it.k, col: ci, choke: !!it.choke });
    }));
    const n = D.columns.length;
    stages.forEach(s => { s.fx = (s.col - (n - 1) / 2) * GAP; });
    const typeOf = {};
    (D.links || []).forEach(([a, b, t]) => { typeOf[a] = typeOf[a] || t; typeOf[b] = typeOf[b] || t; });
    stages.forEach(s => { s.t = typeOf[s.id]; });
    const cos = STOCKS.map(st => ({ id: 'co:' + (st.code || st.ticker || st.name), kind: 'co', name: st.name, key: st.code || st.ticker || '', st }));
    nodes = [...stages, ...cos];
    links = [
      ...(D.links || []).filter(([a, b]) => colOf[a] != null && colOf[b] != null).map(([a, b, t]) => ({ source: a, target: b, kind: 'flow', t })),
      ...cos.flatMap(c => [c.st.node, ...(c.st.also || [])].filter(id => colOf[id] != null).map(id => ({ source: c.id, target: id, kind: 'own' }))),
    ];
  }
  const lineColor = t => rgbVar(TOKEN[(TYPES[t] || {}).color] || TOKEN.accent);
  const stageColor = s => lineColor(s.t);
  const coColor = c => { const i = Object.keys(GRADES).indexOf(c.st.grade); return i >= 0 ? rgbVar(GRADE_TOK[i] || GRADE_TOK[3]) : C('--text-muted'); };
  const endId = x => (x && typeof x === 'object') ? x.id : x;

  // 지금 단추 줄 상태 — flowmap 이 #map 에 거는 클래스 그대로 읽는다
  function state() {
    const only = Object.keys(TYPES).find(k => map.classList.contains('only-' + k)) || null;
    const choke = document.querySelector('#bar [data-act="choke"]').classList.contains('is-on');
    const near = new Set();
    if (sel) { near.add(sel); [...(D.links || []), ...(D.extra || [])].forEach(([a, b]) => { if (a === sel) near.add(b); if (b === sel) near.add(a); }); }
    return { only, choke, near, flow: map.classList.contains('flow') && !matchMedia('(prefers-reduced-motion: reduce)').matches };
  }
  function lit(n, s) {
    const home = n.kind === 'stage' ? [n.id] : [n.st.node, ...(n.st.also || [])];
    if (s.choke) return n.kind === 'stage' ? n.choke : false;
    if (sel) return home.some(id => s.near.has(id));
    return true;
  }
  function linkLit(l, s) {
    if (l.kind === 'own') return lit(typeof l.source === 'object' ? l.source : nodes.find(n => n.id === l.source), s);
    if (s.choke) return false;
    if (sel) return endId(l.source) === sel || endId(l.target) === sel;
    return !s.only || l.t === s.only;
  }

  // 점 · 이름표를 누르면 — 회사는 회사 카드 · 칸은 오른쪽 패널. 부품 분해도가 있는 칸(HBM)은 그 창도 바로 연다
  // (2026-10-07 재권님 「HBM 누르면 창이 안뜨는데?」 — 전에는 패널의 단추를 한 번 더 눌러야 했고, 이름표는 눌리지 않았다)
  function hit(n) {
    if (n.kind !== 'stage') { if (n.key) openCard(n.key); return; }
    const was = sel === n.id;
    pick(n.id);
    const info = INFO[n.id];
    if (was || !info || !info.parts) return;   // 같은 칸을 다시 누르면 고르기만 풀린다
    // 칸 안 모드는 부모(Insight)에 알려 모달로 (2D 흐름도와 같은 길 · 2026-10-06 지시) · 큰 화면은 작은 창
    if (EMBED) { if (window.parent !== window) window.parent.postMessage({ type: 'kjc-parts', page: info.parts.page, label: info.parts.label }, location.origin); }
    else openParts(info.parts.page.replace(/[^A-Za-z0-9._-]/g, ''));
  }
  async function mount() {
    const v = $('v-flow');
    map.classList.add('is-3d');
    if (!box) {
      box = document.createElement('div'); box.className = 'f3d'; v.appendChild(box);
    }
    try { await load(); } catch (e) {
      box.innerHTML = '<div class="err">3D 라이브러리를 못 불러왔습니다(vendor/3d-force-graph.min.js).</div>'; return;
    }
    if (G) { resize(); return; }
    data();
    try {
      G = ForceGraph3D({ controlType: 'orbit' })(box);
    } catch (e) {
      // GPU 가 없는 기기 — 3D 를 못 그린다. 빈 칸 대신 알리고 2D 흐름도로 (세계 지도와 같은 자리)
      console.error('[흐름도 3D] 못 그렸습니다', e);
      box.remove(); box = null; map.classList.remove('is-3d'); D.flow3d = false; draw(); return;
    }
    G.backgroundColor(C('--bg-card')).showNavInfo(false)
      .nodeRelSize(2).nodeVal(n => n.kind === 'stage' ? 6 : 1).nodeOpacity(.95)
      .nodeLabel(() => '')
      .linkWidth(l => l.kind === 'flow' ? .8 : 0)
      .linkDirectionalParticleWidth(1.6).linkDirectionalParticleSpeed(.006)
      .onNodeClick(hit)
      .onBackgroundClick(() => { if (sel) pick(sel); })
      .cooldownTime(3000)
      .graphData({ nodes, links });
    G.d3Force('link').distance(l => l.kind === 'own' ? 24 : GAP).strength(l => l.kind === 'own' ? 1 : .05);
    G.d3Force('charge').strength(-40);
    G.cameraPosition({ x: 120, y: 160, z: 420 });   // 살짝 비스듬히 — 처음부터 3D 로 보이게
    setTimeout(() => G.zoomToFit(600, 30), 3200);
    // 이름표 — 그래프가 상자를 비우므로 그린 뒤에 붙인다. 화면 좌표로 매 프레임 옮긴다
    tags = document.createElement('div'); tags.className = 'f3d-tags'; box.appendChild(tags);
    label = {};
    nodes.forEach(n => { const s = document.createElement('span'); s.className = n.kind === 'stage' ? 'st' : 'cn' /* 'co' 는 회사 카드 창 클래스라 피한다 */; s.textContent = n.name; s.addEventListener('click', () => hit(n)); tags.appendChild(s); label[n.id] = s; });
    resize(); sync(); loop();
  }
  let lastHide = 0;
  function loop() {
    if (!G) return;
    if (!$('v-flow').hidden) {
      nodes.forEach(n => { if (n.x == null) return; const p = G.graph2ScreenCoords(n.x, n.y, n.z); const s = label[n.id]; s.style.transform = `translate(${p.x + 6}px, ${p.y}px) translateY(-50%)`; s._x = p.x; s._y = p.y; });
      const now = performance.now();
      if (now - lastHide > 250) { lastHide = now; declutter(); }
    }
    requestAnimationFrame(loop);
  }
  // 회사 이름표가 겹치면 뒤의 것을 감춘다(칸 이름표는 늘 보인다) — 확대하면 다시 나온다
  function declutter() {
    const shown = [];
    nodes.filter(n => n.kind === 'stage').forEach(n => { const s = label[n.id]; if (!s.classList.contains('dim')) shown.push(s.getBoundingClientRect()); });
    nodes.filter(n => n.kind === 'co').forEach(n => {
      const s = label[n.id]; s.hidden = false;
      const r = s.getBoundingClientRect();
      if (shown.some(q => !(r.right < q.left || q.right < r.left || r.bottom < q.top || q.bottom < r.top))) s.hidden = true; else shown.push(r);
    });
  }
  function resize() { if (G && box) G.width(box.clientWidth).height(box.clientHeight); }
  // 단추 줄 · 고른 칸 · 시나리오를 3D 에 옮긴다 — draw() 가 부른다
  function sync() {
    if (!G) return;
    const s = state(), DIM = C('--border-strong');
    const sc = (D.scenarios || []).find(x => x.id === scenario);
    G.nodeColor(n => lit(n, s) ? (n.kind === 'stage' ? stageColor(n) : coColor(n)) : DIM)
     .linkColor(l => l.kind === 'flow' ? lineColor(l.t) : C('--border-strong'))
     .linkOpacity(.45)
     .linkVisibility(l => linkLit(l, s) || (!sel && !s.choke && l.kind === 'own'))
     .linkDirectionalParticles(l => s.flow && l.kind === 'flow' && linkLit(l, s) ? 3 : 0);
    nodes.forEach(n => {
      const t = label[n.id]; if (!t) return;
      t.classList.toggle('dim', !lit(n, s));
      t.classList.toggle('sel', n.id === sel);
      const eff = n.kind === 'stage' && sc && sc.effects ? sc.effects[n.id] : null;
      t.textContent = n.name + (eff ? ` ${eff}` : '');
    });
  }
  function hide() { map.classList.remove('is-3d'); }
  return { on, mount, sync, resize, hide };
})();
addEventListener('resize', () => Flow3D.resize());
