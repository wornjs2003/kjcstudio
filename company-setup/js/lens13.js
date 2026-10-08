// 「보는 것」 13칸을 종목마다 같은 틀로 — 값 · 판정 · 왜 · 비는 이유 · 출처 (2026-10-08 재권님 「여기 있는 제목에 있는 칸들이 다 그렇게 대입되도록 해야해.
// 그래야 같은 룰에 맞춰 특색에 맞게 데이터가 나오지」 · 「응 한번 해봐 보고 정리하자」).
// 규칙의 원본은 종목 분석 화면(analysis.html #s0w 「보는 것」 표)의 「분석」 칸이다 — 여기는 그 규칙을 계산으로 옮긴 것이다. 규칙을 바꾸면 그 표와 여기를 함께 고친다.
// 판정은 넷 — 좋다 · 보통 · 나쁘다 · 못 가름. 재료가 모자라거나 기준이 정해지지 않았으면 「못 가름」 으로 내고 지어내지 않는다(빈칸 이유를 gap 에 적는다).
// 단계(2026-10-08) — 1단계 일곱(실적 · 재무 · 회계 · 적정가 · 지배구조 · 주주환원 · 수급추세)은 판정까지 · 2단계(성장성 · 경쟁력)는 값만 · 3단계(돈의 흐름 · 불확실성 · 대외변수 · 위험)는 기준 미정

const fin = (v) => v != null && Number.isFinite(v);
const median = (a) => { const s = [...a].sort((x, y) => x - y); const n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : null; };

// ── 5년 PER 밴드 — 월봉 종가 ÷ 그 시점 4분기 합 EPS (종목 분석 「지금 계산 ③(나)」 과 같은 셈 · 여기 한 곳) ──
export function quarterEps(fin) {
  // epsYtd 는 연 누적 — 분기 값 = 이번 누적 − 같은 해 앞 분기 누적 (1분기는 그대로). 앞 분기가 없으면 null (지어내지 않는다)
  const out = [];
  for (let i = 0; i < fin.length; i++) {
    const r = fin[i], ym = String(r.ym), q = +ym.slice(4, 6);
    let eps = null;
    if (r.epsYtd != null) {
      if (q === 3) eps = r.epsYtd;
      else { const p = fin[i - 1]; if (p && String(p.ym).slice(0, 4) === ym.slice(0, 4) && p.epsYtd != null) eps = r.epsYtd - p.epsYtd; }
    }
    out.push({ ym, eps });
  }
  return out;
}
export function perBand5y(monthly, fin) {   // monthly: [{ts, close}]
  const qs = quarterEps(fin);
  const ttm = [];
  for (let i = 3; i < qs.length; i++) {
    const w = qs.slice(i - 3, i + 1);
    if (w.every((x) => x.eps != null)) ttm.push({ ym: qs[i].ym, eps: w.reduce((a, x) => a + x.eps, 0) });
  }
  const last60 = monthly.slice(-60);
  const pers = [];
  for (const m of last60) {
    const ym = m.ts.slice(0, 6);
    let hit = null; for (const t of ttm) { if (t.ym <= ym) hit = t; else break; }
    if (hit && hit.eps > 0) pers.push(m.close / hit.eps);
  }
  if (pers.length < 12) return { ok: false, n: pers.length, months: last60.length };
  return { ok: true, n: pers.length, months: last60.length, lo: Math.min(...pers), mid: median(pers), hi: Math.max(...pers), from: last60[0].ts, to: last60[last60.length - 1].ts };
}


// ── 세계 돈의 흐름 — 종목분석의 위(上位) 층 (2026-10-08 재권님 「돈의 흐름은 종목분석 안이 아니고 종목분석의 상위 개념으로 적용되어야 하고
// 이걸 바탕으로 해당 종목의 흐름이 어떤가 판단한다. 이게 룰이 되어야」). 어느 종목을 열어도 같은 값 — data/world-flow.json(tools/fetch-world-flow.py)
// 한국 업종(표준산업분류 앞 두 자리) → 미국 섹터 ETF 짝 — 임시 대응표(여기 한 곳). 없는 업종은 짝 없음으로 낸다
export const KSIC_TO_US = { '20': 'XLB', '21': 'XLV', '24': 'XLB', '26': 'SOXX', '27': 'XLV', '28': 'XLI', '29': 'XLI', '30': 'XLY', '35': 'XLU', '46': 'XLY', '50': 'XLI', '58': 'XLK', '62': 'XLK', '63': 'XLC', '64': 'XLF', '65': 'XLF', '66': 'XLF' };
export function worldView(w) {
  if (!w || !w.countries) return null;
  const acwi = w.countries.find((c) => c.code === 'ACWI');
  const ctry = w.countries.filter((c) => c.code !== 'ACWI' && fin(c.m1)).sort((a, b) => b.m1 - a.m1);
  const sect = (w.sectors || []).filter((c) => fin(c.m1)).sort((a, b) => b.m1 - a.m1);
  const kr = ctry.find((c) => c.code === 'EWY');
  const y = (n) => (w.yields || []).find((v) => v.name === n);
  const be = (c) => (w.bondEtfs || []).find((v) => v.code === c);
  const hyg = be('HYG'), ief = be('IEF');
  return { at: w.fetchedAt, acwi, ctry, sect, kr, krRank: kr ? ctry.indexOf(kr) + 1 : null, y, be, kf: w.kospiForeign,
    riskOn: hyg && ief && fin(hyg.m1) && fin(ief.m1) ? hyg.m1 > ief.m1 : null, errors: w.errors || {} };
}

const pc = (v, d = 1) => fin(v) ? `${v > 0 ? '+' : ''}${v.toFixed(d)}%` : '—';
const p0 = (v, d = 1) => fin(v) ? `${v.toFixed(d)}%` : '—';
const jo = (v) => fin(v) ? (Math.abs(v) >= 1e12 ? `${(v / 1e12).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}조` : `${Math.round(v / 1e8).toLocaleString('ko-KR')}억`) : '—';
const eok = (v) => fin(v) ? (Math.abs(v) >= 10000 ? `${(v / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}조` : `${Math.round(v).toLocaleString('ko-KR')}억`) : '—';
const R = (id, name, rule, o) => ({ id, name, rule, value: o.value || '—', verdict: o.verdict || '못 가름', why: o.why || '', gap: o.gap || '', src: o.src || '' });

/**
 * x — 종목 리포트가 이미 받은 것: { code, px, fq(KIS 분기 재무), card(회사 카드), monthly([{ts,close}]), daily([{c,h,l}]), cnsPer, per,
 *   inv(KIS 투자자 30일 · 최신 먼저), MA{5,20,60,224}, adx, industry(industry.json), competitors(T.competitors) }
 */
export function lens13(x) {
  const out = [];
  const dart = (x.card && x.card.dart) || {};
  const ksic = dart.industryCode ? String(dart.industryCode) : '';
  const isFin = /^6[456]/.test(ksic);   // 금융 · 보험 — 부채비율 · ROIC 를 안 쓴다(보는 것 표)
  const inv = x.inv || [];
  const invSum = (n, side) => inv.slice(0, n).reduce((s, r) => s + ((r[side] && r[side].netAmt) || 0), 0) / 100;   // 억원

  // ① 흐름 속 이 종목 — 위 세계 흐름(worldView)을 바탕으로: 나라(한국이 세계보다 강한가) · 업종(짝 미국 섹터가 세계보다 강한가) · 돈(이 종목 외국인 20일)
  //    셋 다 플러스면 좋다 · 셋 다 마이너스면 나쁘다 · 엇갈리면 보통 — 보는 것 표의 「돈이 몰리는 나라 · 업종 안에 있고 외국인이 사고 있다」 그대로
  const f20 = inv.length ? invSum(20, 'foreign') : null;
  const W = x.world; const pair = ksic ? KSIC_TO_US[String(+ksic.slice(0, 2))] : null; const ps = W && pair ? W.sect.find((c) => c.code === pair) : null;
  if (W && W.kr && W.acwi && fin(W.acwi.m1)) {
    const sKr = W.kr.m1 > W.acwi.m1, sSec = ps ? ps.m1 > W.acwi.m1 : null, sMoney = fin(f20) ? f20 > 0 : null;
    const sig = [sKr, sSec, sMoney].filter((v) => v !== null);
    const v = sig.length < 3 ? '못 가름' : sig.every(Boolean) ? '좋다' : sig.every((b) => !b) ? '나쁘다' : '보통';
    out.push(R('flow', '흐름 속 이 종목', 'analysis.html#s0w', {
      value: `한국 ${pc(W.kr.m1)} vs 세계 ${pc(W.acwi.m1)}(1개월) · 업종 짝 ${ps ? `${ps.name}(${ps.code}) ${pc(ps.m1)}` : '없음'} · 이 종목 외국인 20일 ${fin(f20) ? (f20 > 0 ? '+' : '') + eok(f20) : '—'}`,
      verdict: v, why: v === '못 가름' ? '' : `나라 ${sKr ? '강함' : '약함'} · 업종 ${sSec ? '강함' : '약함'} · 돈 ${sMoney ? '들어옴' : '빠짐'}`,
      gap: v === '못 가름' ? (ps ? '이 종목 외국인 자료가 없다' : '이 업종의 미국 섹터 짝이 대응표에 없다') : '', src: `세계 흐름 ${W.at} · KIS`,
    }));
  } else out.push(R('flow', '흐름 속 이 종목', 'analysis.html#s0w', { gap: '세계 흐름 자료(data/world-flow.json)가 없다 — tools/fetch-world-flow.py', src: '' }));

  // ② 시황 · 사업 성장성 — 종목 분석 ⑥-11 「산업 덕 · 점유율 덕 가르는 순서」 그대로(2026-10-08 2단계)
  //    ① 점유율 표(금액 기준만 · 수량 · 기준 안 적힘은 참고만) → 가격 · 물량(기간이 같을 때만) → ② 업종 증가율과 견줌(경쟁 몫 = 회사 − 업종 · 같은 분기) → ③ 못 가름
  const k2 = ksic ? String(+ksic.slice(0, 2)) : null; const ind = x.industry && x.industry.byKsic2 && k2 ? x.industry.byKsic2[k2] : null;
  const tb = (dart.business && dart.business.tables) || {};
  const SS = Array.isArray(tb.shareSeries) ? tb.shareSeries : [];
  // 주요 매출원 셋과 점유율 짝(⑥-12 1 · 2) — 성장성 ① 도 이 짝을 쓴다: 주요 매출원에 붙은 금액 기준 점유율만 가르는 데 쓴다(작은 부문 하나로 회사 성장을 가르지 않게)
  const prow = (tb.product && tb.product.rows) || [];
  const segs = prow.slice(1).map((r) => { const m = String(r[r.length - 1]).match(/([\d.]+)%\)?$/); return m && !/계|합|기타/.test(r[0]) ? { name: r[0], items: r.slice(1, -1).join(' '), p: +m[1] } : null; })
    .filter(Boolean).sort((a2, b2) => b2.p - a2.p).slice(0, 3);
  // 점유율 제품 → 부문 짝: 제품 이름의 낱말이 가장 많이 들어 있는 부문 하나에 붙인다(같으면 매출이 큰 부문) — 이름이 달라 못 붙인 것은 「짝 못 지음」 으로 따로 낸다
  const toks = (t) => t.toLowerCase().split(/[\s·/()]+/).filter(Boolean);
  const hit = (sg, r) => { const hay = (sg.items + ' ' + sg.name).toLowerCase().replace(/\s+/g, ''); return toks(r.product).filter((w) => hay.includes(w)).length; };
  const home = new Map(SS.map((r) => { let best = null, bn = 0; segs.forEach((sg) => { const n2 = hit(sg, r); if (n2 > bn) { bn = n2; best = sg.name; } }); return [r, best]; }));
  const segShare = (sg) => SS.filter((r) => home.get(r) === sg.name);
  const unmatched = SS.filter((r) => !home.get(r));
  const shareAmt = SS.filter((r) => r.basis === '금액' && r.vals.length >= 2 && home.get(r));
  const trend = (r) => r.vals[0] > r.vals[1] ? 1 : r.vals[0] < r.vals[1] ? -1 : 0;   // vals[0] = 가장 최근(보고서 머리 순서)
  const fq0 = (x.fq || []); const qa = fq0[fq0.length - 1]; const qb = qa ? fq0.find((r) => +r.ym === +qa.ym - 100) : null;
  const coG = qa && qb && fin(qa.sale) && fin(qb.sale) && qb.sale ? (qa.sale / qb.sale - 1) * 100 : null;
  const qLabel = qa ? `${String(qa.ym).slice(0, 4)}Q${Math.ceil(+String(qa.ym).slice(4, 6) / 3)}` : null;
  const ss = (ind && ind.sales && ind.sales.series) || []; const indHit = ss.find((v) => v[0] === qLabel);
  const indG = indHit ? indHit[1] : null;
  const PP = (tb.productPrice && tb.productPrice.items) || [];
  const steps = [];
  if (shareAmt.length) steps.push(`주요 매출원 점유율(금액 기준 · 내려가는지 확인용) ${shareAmt.map((r) => `${r.product} ${r.vals[1]}→${r.vals[0]}%${r.org ? '(' + r.org + ')' : r.estimate ? '(회사 추정)' : ''}`).join(' · ')}`);
  const ref = SS.filter((r) => !shareAmt.includes(r));
  if (ref.length) steps.push(`참고만(수량 · 기준 안 적힘 · 주요 매출원과 짝 못 지음) ${ref.map((r) => `${r.product} ${r.vals[1]}→${r.vals[0]}%`).join(' · ')}`);
  if (PP.length) steps.push(`가격 ${PP.map((i) => `${i.item} ${i.pct > 0 ? '+' : ''}${i.pct}%`).join(' · ')}(${PP[0].basis || '기준 안 적힘'} — 매출 증가율과 기간이 같지 않아 참고만)`);
  if (fin(coG)) steps.push(`② 회사 매출 ${qLabel} ${pc(coG)} · 업종 ${fin(indG) ? pc(indG) : '—'}${fin(coG) && fin(indG) ? ` → 경쟁 몫 ${pc(coG - indG)}(넓은 업종과 견줌)` : ''}`);
  // ⑥-11 ① 은 「그 제품의 매출과 점유율이 2년 이상 있을 때」 만 — 회사 카드의 제품 매출은 이번 보고서 한 기간뿐이라 ① 은 못 한다(점유율만으로 가르지 않는다).
  //   그래서 ② 업종 견줌으로 가르고, 주요 매출원 점유율(금액 기준)은 「나쁘다 — 점유율이 내려간다」 를 확인하는 데만 쓴다(보는 것 표의 나쁘다 줄)
  steps.unshift('① 못 함 — 제품 매출이 한 기간뿐(⑥-11 「그 제품의 매출과 점유율이 2년 이상 있을 때」)');
  let gv2 = '못 가름', gw = '', gg = '';
  const t3 = shareAmt.map(trend), dnN = t3.filter((v) => v < 0).length, upN = t3.filter((v) => v > 0).length;
  if (fin(indG) && indG < 0) { gv2 = '나쁘다'; gw = '업종이 줄고 있다'; }
  else if (shareAmt.length && dnN > upN) { gv2 = '나쁘다'; gw = `주요 매출원 점유율이 내려간 제품이 더 많다(${dnN}/${t3.length})`; }
  else if (fin(coG) && fin(indG)) {
    gv2 = coG - indG > 0 ? '좋다' : '보통'; gw = coG - indG > 0 ? `② 회사가 업종보다 빨리 컸다(경쟁 몫 ${pc(coG - indG)})` : `② 업종만큼 또는 업종보다 덜 컸다(경쟁 몫 ${pc(coG - indG)}) — 산업 덕`;
    if (shareAmt.length) gw += ` · 주요 매출원 점유율 ${upN > dnN ? '오름' : '그대로'}(${upN}/${t3.length})`;
  } else gg = !ind ? '업종 지표가 없다(금융 · 보험은 세 통계가 없음)' : '같은 분기의 회사 · 업종 증가율이 없다';
  out.push(R('growth', '시황 · 사업 성장성', 'analysis.html#r11', {
    value: (ind ? `업종(${ind.sales ? ind.sales.name : k2}) 매출 ${ss.length ? ss[ss.length - 1][0] + ' ' + pc(ss[ss.length - 1][1]) : '—'} · 생산 ${ind.prod ? pc(ind.prod.yoy) : '—'} · 업황 전망 ${(ind.bsi && ind.bsi.series || []).slice(-1).map((v) => v[1])[0] ?? '—'}` : '업종 지표 없음') + (steps.length ? ' — ' + steps.join(' / ') : ''),
    verdict: gv2, why: gw, gap: [gg, '업종 묶음이 넓다(⑥-11 「넓은 업종과 견줌」)'].filter(Boolean).join(' · '), src: 'ECOS · DART · KIS',
  }));

  // ③ 경쟁력 — 종목 분석 ⑥-12 다섯 걸음 그대로: 1 주요 매출원 셋 → 2 그 제품 점유율(추세) → 3 경쟁사 둘 → 4 이익률 한 표 → 5 판단
  const cpx = x.competitors; const cards = x.cards || {};
  const margin = (key) => { const c = cards[key]; if (!c) return null;
    if (c.dart && c.dart.fs && c.dart.fs.now && c.dart.fs.now.revenue) return { v: c.dart.fs.now.opIncome / c.dart.fs.now.revenue * 100, at: `${c.dart.fs.year} 회사 전체` };
    const f = c.edgar && c.edgar.financials; if (f && f.revenue && f.operatingIncome) { const ks = Object.keys(f.revenue.values).sort(); const k = ks[ks.length - 1]; if (f.operatingIncome.values[k] != null) return { v: f.operatingIncome.values[k] / f.revenue.values[k] * 100, at: `${k.slice(0, 4)} 회사 전체(EDGAR)` }; }
    return null; };
  const me = dart.fs && dart.fs.now && dart.fs.now.revenue ? dart.fs.now.opIncome / dart.fs.now.revenue * 100 : null;
  // 제품(부문)마다 ⑥-12 2~5 — 경쟁사는 리포트 글(competitors)의 제품이 이 부문 점유율 제품과 같을 때만 붙인다
  const perSeg = segs.map((sg) => {
    const sh = segShare(sg).filter((r) => r.basis === '금액');
    const cp = cpx && cpx.list && sh.some((r) => r.product.toLowerCase() === String(cpx.product).toLowerCase()) ? cpx : null;
    const peers = cp ? cp.list.slice(0, 2).map((c) => ({ name: c.name, share: c.share, m: margin(c.key) })) : [];
    const cells = { share: sh.length ? sh.map((r) => `${r.product} ${r.vals[1]}→${r.vals[0]}%(${r.org || (r.estimate ? '회사 추정' : '출처 안 적힘')})`).join(' · ') : '아직',
      sales: `${sg.p}%(부문 비중)`, margin: fin(me) ? `${me.toFixed(1)}%(회사 전체)` : '아직', price: '아직' };
    let v = '판단 못 함', w = '';
    if (sh.length && peers.length && fin(me) && peers.every((p2) => p2.m)) {
      const up = sh.filter((r) => trend(r) > 0).length > sh.filter((r) => trend(r) < 0).length, dn = sh.filter((r) => trend(r) < 0).length > sh.filter((r) => trend(r) > 0).length;
      const better = peers.every((p2) => me > p2.m.v), worse = peers.every((p2) => me < p2.m.v);
      v = up && better ? '좋다' : dn && worse ? '나쁘다' : '보통';
      w = `점유율 ${up ? '오름' : dn ? '내림' : '그대로'} · 이익률 ${better ? '경쟁사보다 높다' : worse ? '경쟁사보다 낮다' : '엇갈림'}`;
    }
    const nAjik = [cells.share, peers.length ? '' : '아직', cells.margin, cells.price].filter((c) => c === '아직').length;
    return { sg, sh, peers, cells, v, w, nAjik };
  });
  const judged = perSeg.filter((p2) => p2.v !== '판단 못 함');
  // ⑥-12 5 — 「표에 아직이 많으면 판단 못 함」: 판단한 제품이 고른 제품의 절반을 넘을 때만 칸 판정을 낸다(매출 큰 제품의 판정을 쓴다)
  let mv = '못 가름', mw = '', mg = '';
  if (judged.length && judged.length * 2 > perSeg.length) { mv = judged[0].v; mw = `${judged[0].sg.name}: ${judged[0].w}`; }
  else mg = perSeg.length ? `판단 못 함 — 고른 제품 ${perSeg.length} 중 판단한 것 ${judged.length}(⑥-12 5 「아직이 많으면 판단 못 함」)` : '주요 매출원을 못 뽑음';
  const segTxt = perSeg.map((p2) => `${p2.sg.name}[점유율 ${p2.cells.share} · 매출 ${p2.cells.sales} · 경쟁사 ${p2.peers.length ? p2.peers.map((q) => `${q.name} ${q.share}${q.m ? ' 이익률 ' + q.m.v.toFixed(1) + '%' : ''}`).join(' · ') : '아직'} · 이익률 ${p2.cells.margin} · 1년 주가 ${p2.cells.price} → ${p2.v}${p2.w ? '(' + p2.w + ')' : ''}]`);
  out.push(R('moat', '경쟁력(해자)', 'analysis.html#r12', {
    value: `${segTxt.length ? segTxt.join(' / ') : '주요 매출원 못 뽑음'}${unmatched.length ? ` · 짝 못 지은 점유율 ${unmatched.map((r) => `${r.product} ${r.vals[1]}→${r.vals[0]}%`).join(' · ')}` : ''}`,
    verdict: mv, why: mw, gap: [mg, '1년 주가 · 부문 이익률은 아직 · 해자 원천 · ROIC 10년은 한 해치뿐이라 「오래 가나」 는 못 본다'].filter(Boolean).join(' · '), src: 'DART · 리포트 글 · EDGAR',
  }));

  // ④ 실적 — 최근 분기 영업이익이 1년 전보다 크고 영업이익률이 전 분기 이상이면 좋다 · 줄거나 적자면 나쁘다
  const fq = x.fq || []; const q0 = fq[fq.length - 1], q1 = fq[fq.length - 2]; const qy = q0 ? fq.find((r) => +r.ym === +q0.ym - 100) : null;
  if (q0 && qy && fin(q0.op) && fin(qy.op)) {
    const up = q0.op > qy.op, mUp = q1 && fin(q0.opMargin) && fin(q1.opMargin) ? q0.opMargin >= q1.opMargin : null;
    const v = q0.op < 0 || !up ? '나쁘다' : (mUp ? '좋다' : '보통');
    out.push(R('earn', '실적', 'analysis.html#calc-earn', { value: `${q0.ym} 영업이익 ${eok(q0.op)}(1년 전 ${eok(qy.op)} · ${pc((q0.op / Math.abs(qy.op) - 1) * 100)}) · 영업이익률 ${p0(q0.opMargin)}(전 분기 ${q1 ? p0(q1.opMargin) : '—'})`,
      verdict: v, why: v === '좋다' ? '영업이익이 1년 전보다 크고 이익률이 전 분기 이상' : v === '나쁘다' ? '영업이익이 1년 전보다 줄었거나 적자' : '영업이익은 늘었지만 이익률이 전 분기보다 낮다', src: 'KIS 분기 재무' }));
  } else out.push(R('earn', '실적', 'analysis.html#calc-earn', { gap: '1년 전 같은 분기 재무가 없다', src: 'KIS' }));

  // ⑤ 재무 건전성 — 부채비율 낮고(100% 아래면 튼튼한 편) 유동비율 100% 위 · 이익의 질 1배 위 · 잉여현금흐름 플러스면 좋다
  const fs = dart.fs; const n = fs && fs.now, p = fs && fs.prev;
  if (n && !isFin) {
    const debt = n.liab / n.equity * 100, debtP = p ? p.liab / p.equity * 100 : null, cur = n.curAssets / n.curLiab * 100, q = n.opCF / n.netIncome, fcf = n.opCF - n.capex;
    const good = debt < 100 && cur > 100 && q >= 1 && fcf > 0, bad = fin(debtP) && debt > debtP && q < 1;
    out.push(R('fs', '재무 건전성', 'analysis.html#calc-fs', { value: `부채비율 ${p0(debt, 0)}(전년 ${p0(debtP, 0)}) · 유동비율 ${p0(cur, 0)} · 이익의 질 ${q.toFixed(2)}배 · 잉여현금 ${jo(fcf)}`,
      verdict: good ? '좋다' : bad ? '나쁘다' : '보통', why: good ? '네 가지가 다 기준 안' : bad ? '부채비율이 오르고 이익이 현금으로 덜 들어온다' : '기준 일부만 맞는다', src: `DART ${fs.year} ${fs.fsDiv}` }));
  } else out.push(R('fs', '재무 건전성', 'analysis.html#calc-fs', { gap: isFin ? '금융업은 부채비율로 보지 않는다(보는 것 표)' : '사업보고서 재무제표를 못 받았다', src: 'DART' }));

  // ⑥ 회계 신뢰도 — 감사의견 적정 · 계속기업 없음이면 좋다 · 한정 · 부적정 · 의견거절 · 계속기업이면 바로 경고
  const au = dart.audit && dart.audit.rows || [];
  if (au.length) {
    const warn = au.some((r) => /한정|부적정|거절/.test(r.opinion || '') || r.goingConcern);
    const auditors = new Set(au.map((r) => r.auditor)).size;
    out.push(R('audit', '회계 신뢰도', 'analysis.html#calc-audit', { value: `${new Set(au.map((r) => r.term)).size}기 의견 ${[...new Set(au.map((r) => r.opinion))].join(' · ')} · 감사인 ${auditors}곳(${[...new Set(au.map((r) => r.auditor))].join(' · ')})`,
      verdict: warn ? '나쁘다' : (auditors > 2 ? '보통' : '좋다'), why: warn ? '비적정 의견이나 계속기업 불확실성 — 바로 경고' : auditors > 2 ? '의견은 적정이나 감사인이 해마다 바뀌었다' : '적정 · 계속기업 기재 없음', src: 'DART 감사의견' }));
  } else out.push(R('audit', '회계 신뢰도', 'analysis.html#calc-audit', { gap: '감사의견을 못 받았다', src: 'DART' }));

  // ⑦ 시세 · 적정가 — 추정 PER 이 5년 범위 중간 이하 싸다 · 중간~상단 적정 · 상단 위 비싸다
  const band = x.monthly && x.fq ? perBand5y(x.monthly, x.fq) : { ok: false };
  const perNow = fin(x.cnsPer) ? x.cnsPer : x.per, perKind = fin(x.cnsPer) ? '추정' : '확정';
  if (band.ok && fin(perNow)) {
    const v = perNow <= band.mid ? '좋다' : perNow <= band.hi ? '보통' : '나쁘다';
    out.push(R('value', '시세 · 적정가', 'analysis.html#calc-band', { value: `${perKind} PER ${perNow.toFixed(1)}배 · 5년 범위 ${band.lo.toFixed(1)} ~ 중간 ${band.mid.toFixed(1)} ~ ${band.hi.toFixed(1)}배`,
      verdict: v, why: v === '좋다' ? '5년 범위 중간 이하 — 싸다' : v === '보통' ? '중간 ~ 상단 — 적정' : '5년 상단 위 — 비싸다', src: 'KIS · 네이버' }));
  } else out.push(R('value', '시세 · 적정가', 'analysis.html#calc-band', { value: fin(perNow) ? `${perKind} PER ${perNow.toFixed(1)}배` : '—', gap: band.ok ? 'PER 이 없다(적자 등)' : `5년 PER 범위를 못 셌다(쓸 수 있는 달 ${band.n || 0} · 12달 넘어야 셈)`, src: 'KIS' }));

  // ⑧ 불확실성 · 안전마진 — 3단계(등급 계산 미정) · 재료 하나(주가 흔들림)만 낸다
  const d = x.daily || []; const rets = []; for (let i = Math.max(1, d.length - 250); i < d.length; i++) if (d[i - 1].c) rets.push(Math.log(d[i].c / d[i - 1].c));
  const sd = rets.length > 20 ? Math.sqrt(rets.reduce((s, r) => s + r * r, 0) / rets.length - (rets.reduce((s, r) => s + r, 0) / rets.length) ** 2) * Math.sqrt(250) * 100 : null;
  out.push(R('unc', '불확실성 · 안전마진', 'analysis.html#r10', { value: `주가 흔들림(1년 · 연율) ${p0(sd, 0)}`, gap: '등급 다섯 칸을 매기는 계산이 아직 없다(기준 미정)', src: 'KIS 일봉' }));

  // ⑨ 경영진 · 지배구조 — 사외이사 비율이 높아 견제되면 좋다 · 대주주 지분이 낮은데 지배력이 크면 나쁘다
  const gv = dart.gov || {}; const bd = gv.board || {}; const mj = gv.major || {};
  if (fin(bd.registered) && bd.registered > 0) {
    const ratio = bd.outside / bd.registered * 100;
    out.push(R('gov', '경영진 · 지배구조', 'analysis.html#calc-gov', { value: `사외이사 ${bd.outside}/${bd.registered}명(${p0(ratio, 0)}) · 최대주주 + 특수관계인 ${p0(mj.totalPct)} · 등기임원 평균 보수 ${jo(gv.pay && gv.pay.avg)}`,
      verdict: ratio > 50 ? '좋다' : '보통', why: ratio > 50 ? '이사회 과반이 사외이사(상법의 대규모 상장사 요건을 임시 기준으로 씀)' : '사외이사가 과반이 아니다', gap: '보수가 실적과 맞게 움직이나는 한 해치뿐이라 못 본다', src: 'DART' }));
  } else out.push(R('gov', '경영진 · 지배구조', 'analysis.html#calc-gov', { gap: '임원 현황을 못 받았다', src: 'DART' }));

  // ⑩ 주주환원 — 주당 배당금이 오르고 자사주를 소각하면 좋다 · 사기만 하고 쌓아 두면 나쁘다
  const dv = gv.dividend || {}; const tr = gv.treasury || {};
  if ((dv.dps && dv.dps.length) || fin(tr.acquired)) {
    const dpsUp = dv.dps && dv.dps.length > 1 ? dv.dps[0] > dv.dps[1] : null, burn = (tr.retired || 0) > 0, hoard = (tr.acquired || 0) > 0 && !burn;
    const v = hoard ? '나쁘다' : (dpsUp && burn) ? '좋다' : '보통';
    out.push(R('ret', '주주환원', 'analysis.html#calc-gov', { value: `주당 배당금 ${dv.dps ? dv.dps.map((v2) => Math.round(v2).toLocaleString('ko-KR') + '원').join(' ← ') : '—'} · 배당성향 ${dv.payout ? p0(dv.payout[0]) : '—'} · 자사주 취득 ${fin(tr.acquired) ? Math.round(tr.acquired).toLocaleString('ko-KR') + '주' : '—'} · 소각 ${fin(tr.retired) ? Math.round(tr.retired).toLocaleString('ko-KR') + '주' : '—'}`,
      verdict: v, why: v === '좋다' ? '배당금이 올랐고 자사주를 소각했다' : v === '나쁘다' ? '자사주를 사기만 하고 소각하지 않았다' : `${dpsUp ? '배당금은 올랐지만' : '배당금이 안 올랐고'} ${burn ? '소각은 했다' : '소각이 없다'}`, src: 'DART' }));
  } else out.push(R('ret', '주주환원', 'analysis.html#calc-gov', { gap: '배당 · 자기주식 자료가 없다', src: 'DART' }));

  // ⑪ 수급 · 추세 — 20일 외국인 + 기관 순매수 플러스 · 단기 정배열 · 224일선 위면 좋다 · ADX 20 아래면 늘 보통
  const fi = inv.length ? invSum(20, 'foreign') + invSum(20, 'inst') : null; const M = x.MA || {};
  if (fin(fi) && fin(M[5]) && fin(M[20]) && fin(M[60]) && fin(M[224]) && fin(x.px)) {
    const up = M[5] > M[20] && M[20] > M[60], dn = M[5] < M[20] && M[20] < M[60], above = x.px > M[224];
    let v = fi > 0 && up && above ? '좋다' : (fi < 0 && (dn || !above)) ? '나쁘다' : '보통';
    let why = v === '좋다' ? '외국인 + 기관이 사고 · 정배열 · 224일선 위' : v === '나쁘다' ? '외국인 + 기관이 팔고 역배열이거나 224일선 아래' : '셋이 엇갈린다';
    if (fin(x.adx) && x.adx < 20) { v = '보통'; why = `ADX ${x.adx.toFixed(0)} — 추세가 없어 보통으로 둔다`; }
    out.push(R('trend', '수급 · 추세', 'analysis.html#r3', { value: `20일 외국인 + 기관 ${fi > 0 ? '+' : ''}${eok(fi)} · 이평 ${up ? '정배열' : dn ? '역배열' : '혼조'} · 224일선 ${above ? '위' : '아래'} · ADX ${fin(x.adx) ? x.adx.toFixed(0) : '—'}`, verdict: v, why, src: 'KIS' }));
  } else out.push(R('trend', '수급 · 추세', 'analysis.html#r3', { gap: '투자자 자료나 일봉이 모자라다', src: 'KIS' }));

  // ⑫ 대외변수 — 3단계(국면 판정 미정)
  out.push(R('macro', '대외변수', 'analysis.html#r9', { gap: '경기 네 국면 중 지금이 어디인지 판정하는 계산이 아직 없다(기준 미정)' }));

  // ⑬ 위험 — 3단계(크기 매기기 미정) · 바로 경고(감사)와 사업 집중만 낸다
  const pt = dart.business && dart.business.tables && dart.business.tables.product; let top = null;
  if (pt && pt.rows) for (const r of pt.rows.slice(1)) { const m = String(r[r.length - 1]).match(/([\d.]+)%\)?$/); if (m && !/계|합/.test(r[0]) && (!top || +m[1] > top.p)) top = { name: r[0], p: +m[1] }; }   // 「33.0%」 · 「131,895,033(100%)」 둘 다
  const auWarn = au.some((r) => /한정|부적정|거절/.test(r.opinion || '') || r.goingConcern);
  out.push(R('risk', '위험', 'analysis.html#r6', { value: `${top ? `가장 큰 부문 ${top.name} ${top.p}%` : '부문 비중 없음'} · 감사 경고 ${au.length ? (auWarn ? '있음' : '없음') : '—'}`,
    verdict: auWarn ? '나쁘다' : '못 가름', why: auWarn ? '감사 경고 — 바로 경고' : '', gap: auWarn ? '' : '위험마다 크기를 매기는 기준이 아직 없다(기준 미정)', src: 'DART' }));

  return out;
}
