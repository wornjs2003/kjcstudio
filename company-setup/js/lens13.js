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

  // ② 시황 · 사업 성장성 — 2단계(회사 3년 추이 · 가격 · 물량은 다음 단계)
  const k2 = ksic ? String(+ksic.slice(0, 2)) : null; const ind = x.industry && x.industry.byKsic2 && k2 ? x.industry.byKsic2[k2] : null;
  const ss = ind && ind.sales && ind.sales.series || []; const bs = ind && ind.bsi && ind.bsi.series || [];
  out.push(R('growth', '시황 · 사업 성장성', 'analysis.html#r11', {
    value: ind ? `업종(${ind.sales ? ind.sales.name : k2}) 매출 ${ss.length ? ss[ss.length - 1][0] + ' ' + pc(ss[ss.length - 1][1]) : '—'} · 생산 ${ind.prod ? pc(ind.prod.yoy) : '—'} · 업황 전망 ${bs.length ? bs[bs.length - 1][1] : '—'}` : '업종 지표 없음',
    gap: '회사 쪽(부문 매출 3년 · 가격 · 물량 · 점유율 추이)은 다음 단계에서 붙인다 — 산업 덕 · 점유율 덕을 아직 못 가른다', src: 'ECOS',
  }));

  // ③ 경쟁력 — 2단계
  const cp = x.competitors;
  out.push(R('moat', '경쟁력(해자)', 'analysis.html#r12', {
    value: cp && cp.self ? `${cp.product} 점유율 ${cp.self.share} · ${cp.self.rank}위${(cp.list || []).length ? ' · ' + cp.list.map((c) => `${c.name} ${c.share}`).join(' · ') : ''}` : '경쟁사 · 점유율 글 없음',
    gap: '점유율이 한 시점뿐이라 오르는지 모른다 · 경쟁사 이익률 · ROIC 비교는 다음 단계', src: cp ? '조사기관(글)' : '',
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
