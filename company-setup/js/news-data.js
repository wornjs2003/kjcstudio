// 뉴스 데이터 구축 현황 (2026-11-03 재권님 「뉴스를 분석하기 위한 데이터를 구축」 → 「이대로 만들어봐. 만들면서 개선하자」 · 시황분석1).
// 값은 전부 서버 주소 — 화면이 바깥 출처를 따로 받지 않는다(「두 구역이 같은 값을 쓰면」 1번).
//   /api/news/stored   쌓아 둔 기사(묶음 단위 · 묶음 안 기사는 others) · meta.total · meta.topics   (holdings/server/news_store.py)
//   /api/news/topics   뉴스 주제어 묶음 (holdings/data/news-topics.json)
//   /api/dart/status   공시 · 회사 목록 · 상위 종목 수
//   /holdings/data/disclosure-tags.json   공시 딱지 묶음(홀딩스 공시 칸과 같은 파일)
// 못 받은 값은 「—」 · 「못 받음」 으로 낸다(0 으로 메우지 않는다).
// 층 상태(쌓이는 중 · 재료만 · 없음)는 받은 값으로 가른다 — 값이 있는데 「없음」 으로 남지 않게.

const $ = id => document.getElementById(id);
const get = async u => { try { const r = await fetch(u, { cache: 'no-store' }); return r.ok ? await r.json() : null; } catch (e) { return null; } };
const nf = x => (x == null || !isFinite(x) ? '—' : Number(x).toLocaleString('ko-KR'));
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const md = s => (s ? `${s.slice(5, 10)} ${s.slice(11, 16)}` : '—');
const ST = { ok: '쌓이는 중', part: '재료만', no: '없음', miss: '못 받음' };
const st = k => `<span class="nd-st ${k === 'miss' ? 'no' : k}">${ST[k]}</span>`;

(async () => {
  // 보관 기간은 서버가 정한다(news_store.py NEWS_KEEP_DAYS · 2026-11-03 재권님 「한 달」) — 화면은 기간을 들지 않는다.
  // 「서버가 가진 것 전부」 를 받으려고 hours 를 아주 크게 묻는다 — 서버는 가진 만큼만 준다. 화면에는 보관 일수 대신 가장 오래된 기사 날짜를 보인다
  const [ns, tp, ds, tg] = await Promise.all([
    get('/api/news/stored?hours=100000&limit=20000'), get('/api/news/topics'), get('/api/dart/status'), get('/holdings/data/disclosure-tags.json'),
  ]);
  const groups = (ns && ns.ok && ns.data) || null;
  const total = ns && ns.meta && ns.meta.total;
  const items = groups ? groups.flatMap(g => [g, ...(g.others || [])]) : null;
  // 서버는 묶음 안 기사를 넷까지만 실어 준다(news_store.groups) — 나머지는 수(more)만 온다. 날짜 · 언론사를 모르는 그 수를 따로 낸다(합이 머리 건수와 맞게 · 2026-11-03 qa 검수)
  const hidden = groups ? groups.reduce((a, g) => a + Math.max(0, (g.more || 0) - (g.others || []).length), 0) : 0;
  const dart = (ds && ds.ok && ds.data) || null;
  const bundles = (tg && tg['묶음']) || null;
  const topics = (tp && tp.ok && tp.data) || null;

  $('nd-meta').textContent = `잰 시각 ${new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })} · 쌓는 곳 서버 DB · `
    + (total ? `기사 ${md(total.from)} ~ ${md(total.to)}` : '기사 못 받음') + (dart ? ` · 공시 마지막 받음 ${md(dart.lastReceivedAt)}` : ' · 공시 못 받음');

  // ── 층 여섯 ──
  const multi = groups ? groups.filter(g => g.more > 0) : null;
  const L = [
    { n: '①', name: '기사 원본', what: '제목 · 언론사 · 시각 · 원문 주소 · 공시',
      st: items ? 'ok' : 'miss',
      now: items ? `기사 <b>${nf(total ? total.count : items.length)}건</b>` + (dart ? ` · 공시 <b>${nf(dart.disclosures)}건</b>` : '') : '—',
      gap: `본문 없음(제목만) · 해외 기사 없음 · 오래된 기사는 서버가 지움(지금 가장 오래된 것 ${total ? total.from.slice(5, 10) : '—'})` },
    { n: '②', name: '종목 이름표', what: '기사 속 회사 이름 → 종목코드 · 별명',
      st: dart ? 'part' : 'miss', now: dart ? `회사 목록 <b>${nf(dart.corps)}</b>(공시 회사표)` : '—',
      gap: '기사와 종목을 잇는 표 없음 · 별명(「삼전닉스」 등) 없음' },
    { n: '③', name: '사건 갈래 사전', what: '큰 갈래 · 작은 갈래와 거기 걸리는 낱말',
      st: bundles ? 'part' : 'miss', now: `공시 딱지 묶음 <b>${bundles ? bundles.length : '—'}</b> · 뉴스 주제 <b>${topics ? topics.length : '—'}</b>`,
      gap: '뉴스 기사용 사건 갈래 없음 · 방향(좋음 · 나쁨) 없음' },
    { n: '④', name: '크기 재료', what: '회사 매출 · 시가총액 — 금액 ÷ 매출',
      st: dart ? 'part' : 'miss', now: dart ? `시가총액 상위 <b>${nf(dart.universe)}</b> 종목 · 매출은 종목마다 서버 재무(/api/kis/finance)` : '—',
      gap: '사건 금액과 매출을 대는 자리 없음 · 상위 밖 종목 시가총액 없음' },
    { n: '⑤', name: '같은 사건 묶음', what: '첫 보도 시각 · 묶인 기사',
      st: groups ? 'ok' : 'miss', now: groups ? `묶음 <b>${nf(groups.length)}</b> · 둘 이상 묶인 것 <b>${nf(multi.length)}</b>` : '—',
      gap: '제목 낱말 겹침으로만 묶음 · 공시와 기사는 따로' },
    { n: '⑥', name: '사후 반응', what: '사건 뒤 그날 · 다음 날 주가 · 거래량',
      st: 'no', now: '—', gap: '주가는 서버에 있으나 사건과 잇는 기록 없음' },
  ];
  $('nd-layers').innerHTML = `<div class="r h"><span></span><span>층</span><span>무엇을 쌓나</span><span>상태</span><span>지금 쌓인 것</span><span>빠진 것</span></div>`
    + L.map(l => `<div class="r"><span class="n">${l.n}</span><b>${l.name}</b><span class="what">${l.what}</span><span>${st(l.st)}</span><span>${l.now}</span><span class="gap">${l.gap}</span></div>`).join('');
  const cnt = k => L.filter(l => l.st === k).length;
  $('nd-one').textContent = `여섯 층 중 쌓이는 중 ${cnt('ok')} · 재료만 ${cnt('part')} · 없음 ${cnt('no')}` + (cnt('miss') ? ` · 못 받음 ${cnt('miss')}` : '');

  // ── 여덟 칸 — 어느 층이 채우나 ── (층 상태에서 가른다)
  const S = Object.fromEntries(L.map(l => [l.n, l.st]));
  const F = [
    ['7 출처 · 시각', S['①'], '① 기사 원본'],
    ['3 처음 소식인가', S['⑤'], '⑤ 묶음의 첫 보도'],
    ['6 확인 정도(공시 / 기사만)', S['①'], '① 공시와 기사'],
    ['2 사건 갈래', S['③'], '③ — 공시만 딱지로 · 기사는 없음'],
    ['1 누구 이야기 · 8 연결 종목', S['②'], '② 이름표'],
    ['4 방향', 'no', '③ 갈래 사전에 방향이 생기면'],
    ['5 크기', S['④'], '④ 크기 재료'],
  ];
  const lab = { ok: '됨', part: '반', no: '안 됨', miss: '못 받음' };
  $('nd-fill').innerHTML = F.map(([k, s, why]) => `<span class="nd-st ${s === 'miss' ? 'no' : s}">${lab[s]}</span> ${k} — ${why}`).join('<br>');

  // ── 날마다 쌓인 수 ──
  if (items) {
    const by = {};
    items.forEach(x => { const d = (x.at || '').slice(0, 10); if (d) by[d] = (by[d] || 0) + 1; });
    const days = Object.keys(by).sort(), mx = Math.max(...days.map(d => by[d]));
    $('nd-days').innerHTML = days.map(d => `<div class="b"><span>${d.slice(5)}</span><i style="width:${(by[d] / mx * 100).toFixed(0)}%"></i><span>${by[d]}</span></div>`).join('')
      + (hidden ? `<div class="b"><span>모름</span><span class="gap">묶음 안에서 잘려 날짜를 모름</span><span>${hidden}</span></div>` : '');
  } else $('nd-days').textContent = '못 받음';

  // ── 층 펼친 칸 ──
  const kv = (o, n) => Object.entries(o).sort((a, b) => b[1] - a[1]).slice(0, n).map(([k, v]) => `<div><b>${nf(v)}</b>${esc(k)}</div>`).join('');
  if (items) {
    const src = {}; items.forEach(x => { src[x.source || '—'] = (src[x.source || '—'] || 0) + 1; });
    const nSrc = Object.keys(src).length; // 언론사 수는 「모름」 을 넣기 전에 센다(qa 11-04)
    if (hidden) src['모름(묶음 안에서 잘림)'] = hidden;
    $('nd-src').innerHTML = kv(src, 8);
    $('sum-nd1').innerHTML = `<span class="sl"><b>기사 ${nf(total ? total.count : items.length)}${dart ? ` · 공시 ${nf(dart.disclosures)}` : ''}</b>언론사 ${nSrc} · 주제 ${ns.meta.topics ? Object.keys(ns.meta.topics).length : '—'} · 「중요」 규칙에 걸린 묶음 ${groups.filter(g => g.alert).length}</span>`;
  } else { $('nd-src').textContent = '못 받음'; $('sum-nd1').textContent = '못 받음'; }
  $('nd-topic').innerHTML = ns && ns.meta && ns.meta.topics ? kv(ns.meta.topics, 8) : '못 받음';

  $('sum-nd2').innerHTML = dart ? `<span class="sl"><b>회사 ${nf(dart.corps)}</b>기사와 잇는 표 · 별명 — 없음</span>` : '못 받음';
  $('nd-tags').innerHTML = bundles ? bundles.map(b => `<span title="${esc(b['뜻'])}"><b>${esc(b.label)}</b>${(b['말'] || []).length}낱말</span>`).join('') : '못 받음';
  $('nd-topics').innerHTML = topics ? topics.filter(t => t.on !== false).map(t => `<span><b>${esc(t.label)}</b>${(t.keywords || []).length}낱말</span>`).join('') : '못 받음';
  $('sum-nd3').innerHTML = `<span class="sl"><b>공시 딱지 ${bundles ? bundles.length : '—'}묶음</b>뉴스 기사 갈래 · 방향 — 없음</span>`;
  $('sum-nd4').innerHTML = dart ? `<span class="sl"><b>시가총액 상위 ${nf(dart.universe)}</b>매출은 종목마다 서버 재무 · 사건과 대는 자리 — 없음</span>` : '못 받음';
  if (groups) {
    $('sum-nd5').innerHTML = `<span class="sl"><b>묶음 ${nf(groups.length)}</b>기사 ${nf(total ? total.count : items.length)} — 둘 이상 묶인 것 ${nf(multi.length)} · 제목 낱말 겹침</span>`;
    $('nd-groups').innerHTML = multi.sort((a, b) => b.more - a.more).slice(0, 12)
      .map(g => `<div class="r"><a href="${esc(g.link)}" target="_blank" rel="noopener">${esc(g.title)}</a><small>${esc(g.source)} · ${md(g.at)} · 기사 ${g.more + 1}</small></div>`).join('') || '둘 이상 묶인 것 없음';
  } else { $('sum-nd5').textContent = '못 받음'; $('nd-groups').textContent = '못 받음'; }
  $('sum-nd6').innerHTML = '<span class="sl"><b>없음</b>사건과 주가를 잇는 기록 — 아직 안 만듦</span>';
})();
