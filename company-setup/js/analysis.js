// 종목 분석 페이지 — 「받을 수 있는 값 — 지금 계산」 카드 (2026-10-06 재권님 「해줘봐」 · 창구 경유)
//
// 조사 문서(①~⑤)가 「이런 값을 쓴다」 고 적은 것을 **우리 서버 · 회사 카드 자료만으로** 지금 계산해 보여 준다.
// 값을 지어내지 않는다 — 못 받는 것은 「아직」 알약 · 못 세는 것은 — 으로 낸다. 칸마다 출처와 받은 시각을 적는다.
//
//   ① 지수 대비 상대수익률 1 · 6 · 12개월   = (종목 현재가 ÷ N개월 전 종가 − 1) − (코스피 같은 식)     KIS 일봉 · 주봉 · 코스피 일봉 · 주봉
//   ② 실적 + 증권사 추정(E) 열               네이버 증권(FnGuide 집계) 연간 표 — data/company-cards.json(fetch-company-cards.py 가 받아 둠)
//   ③ 적정가 밴드 = 추정 EPS(E) × 과거 PER 하단 / 중간 / 상단
//        (가) 연간 PER 밴드 — 네이버 연간 PER(양수만 · 추정 열 제외)
//        (나) 5년 PER 밴드 — KIS 월봉 종가(60개) ÷ KIS 분기 EPS 4분기 합(개발3 실측 방식 · 2026-10-06)
//   주기 숫자를 두지 않는다 — 고를 때 한 번 받는다.
const $ = (id) => document.getElementById(id);
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const n0 = (v, d = 0) => (v == null || !Number.isFinite(v)) ? '—' : v.toLocaleString('ko-KR', { maximumFractionDigits: d });
const pct = (v, d = 1) => (v == null || !Number.isFinite(v)) ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(d)}%`;
const won = (v) => (v == null || !Number.isFinite(v)) ? '—' : (Math.abs(v) >= 10000 ? `${(v / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}조` : n0(v));
const pill = (k, t) => `<span class="in-pill ${k}">${esc(t)}</span>`;
const SOON = pill('no', '아직');   // 못 받는 값은 빨강 (2026-10-06 재권님 「못가져오는 색은 빨간색」) — 전에는 파랑(soon)
// 출처 배지 (2026-10-06 재권님 「종목 분석에 있는 정보들 어디서 가져올수 있는지 표기해서 보여줘」 → 「응 해줘」).
// 값마다 어디서 온 것인지를 값 옆에 적는다 — KIS(한국투자증권 · 우리 서버) · 네이버(증권 · FnGuide 집계 · 회사 카드) ·
// DART(금감원 · 회사 카드) · 계산(위 값으로 셈). 글자 배지라 칸 높이를 안 바꾼다(insight.css .in-src)
const src = (t) => `<span class="in-src">${esc(t)}</span>`;
const S = { kis: src('KIS'), naver: src('네이버'), dart: src('DART'), calc: src('계산') };

async function api(u) {
  const r = await fetch(u, { cache: 'no-store' });
  if (!r.ok) throw new Error(`${u} ${r.status}`);
  const j = await r.json();
  if (j && j.ok === false) throw new Error(j.error || u);
  return j;
}
const bars = (j) => { const d = j.data; const a = Array.isArray(d) ? d : (d.candles || d.bars || []); return a.map((b) => ({ ts: String(b.ts || b.date || ''), close: Number(b.close) })).filter((b) => b.ts && Number.isFinite(b.close)); };
const ymd = (s) => `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
function monthsAgo(ts, m) { const d = new Date(+ts.slice(0, 4), +ts.slice(4, 6) - 1 - m, +ts.slice(6, 8)); return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`; }
const atOrBefore = (arr, ts) => { let hit = null; for (const b of arr) { if (b.ts <= ts) hit = b; else break; } return hit; };
const median = (a) => { const s = [...a].sort((x, y) => x - y); const n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : null; };

// ── ① 상대수익률 ──
function relReturn(stock, index, months) {
  if (!stock.length || !index.length) return null;
  const last = stock[stock.length - 1], ilast = index[index.length - 1];
  const t = monthsAgo(last.ts, months);
  const s0 = atOrBefore(stock, t), i0 = atOrBefore(index, t);
  if (!s0 || !i0 || s0.ts === last.ts) return null;                // 그 전 자료가 없다 → 못 센다
  const rs = last.close / s0.close - 1, ri = ilast.close / i0.close - 1;
  return { rs: rs * 100, ri: ri * 100, rel: (rs - ri) * 100, from: s0.ts };
}

// ── ③(나) 5년 PER 밴드 — 월봉 종가 ÷ 그 시점 4분기 합 EPS ──
function quarterEps(fin) {
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
function perBand5y(monthly, fin) {
  const qs = quarterEps(fin);
  const ttm = [];                                                  // 분기 끝마다 4분기 합
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

// ── 그리기 ──
let CARDS = null, CARDS_AT = '';
function row(label, cells) { return `<tr><td>${label}</td>${cells.map((c) => `<td${typeof c === 'string' && c.startsWith('-') ? ' class="neg"' : ''}>${c}</td>`).join('')}</tr>`; }

async function paint(code) {
  const box = $('calc-body');
  box.innerHTML = '<p class="in-doc-p">받는 중…</p>';
  const card = CARDS ? CARDS[code] : null;
  const nv = card && card.naver;
  const got = {};
  const tasks = {
    d: api(`/api/kis/chart?code=${code}&period=D`).then(bars), w: api(`/api/kis/chart?code=${code}&period=W`).then(bars), m: api(`/api/kis/chart?code=${code}&period=M`).then(bars),
    kd: api('/api/kis/index-candles?code=KOSPI&period=D').then(bars), kw: api('/api/kis/index-candles?code=KOSPI&period=W').then(bars),
    fin: api(`/api/kis/finance?code=${code}`).then((j) => j.data || []),
  };
  const errs = {};
  await Promise.all(Object.entries(tasks).map(([k, p]) => p.then((v) => { got[k] = v; }, (e) => { errs[k] = String(e.message || e); })));
  const now = new Date(); const at = `${now.getHours()}:${String(now.getMinutes()).padStart(2, '0')}`;
  const price = got.d && got.d.length ? got.d[got.d.length - 1] : null;
  let h = '';
  // 머리 — 현재가 · 목표가 · 투자의견
  const cs = nv && nv.consensus || {};
  h += `<div class="in-kv">
    <div><b>${price ? n0(price.close) + '원' : '—'}</b><span>${S.kis} 현재가 · 일봉 종가 ${price ? ymd(price.ts) : ''}</span></div>
    <div><b>${cs.targetPriceMean != null ? n0(cs.targetPriceMean) + '원' : '—'}</b><span>${S.naver} 목표가 평균 · FnGuide 집계 ${esc(cs.asOf || '')}</span></div>
    <div><b>${cs.recommMean != null ? n0(cs.recommMean, 2) + ' / 5' : '—'}</b><span>${S.naver} 투자의견 평균(5 매수)</span></div>
    <div><b>${price && cs.targetPriceMean ? pct((cs.targetPriceMean / price.close - 1) * 100) : '—'}</b><span>${S.calc} 상승여력 = 목표가 ÷ 현재가 − 1</span></div></div>`;
  // ① 상대수익률
  const r1 = got.d && got.kd ? relReturn(got.d, got.kd, 1) : null, r6 = got.d && got.kd ? relReturn(got.d, got.kd, 6) : null, r12 = got.w && got.kw ? relReturn(got.w, got.kw, 12) : null;
  h += `<h3>① 지수(코스피) 대비 상대수익률 ${S.calc} <span class="src">KIS 일봉 · 주봉 · 코스피 일봉 · 주봉 · ${at} 받음</span></h3>
    <div class="in-tblx"><table class="in-tbl"><tr><th></th><th>종목 ${S.kis}</th><th>코스피 ${S.kis}</th><th>상대(%p) ${S.calc}</th><th>기준일</th></tr>
    ${[['1개월', r1], ['6개월', r6], ['12개월(주봉)', r12]].map(([lb, r]) => r ? row(lb, [pct(r.rs), pct(r.ri), pct(r.rel), ymd(r.from)]) : row(lb, [SOON + ' 자료 부족', '', '', ''])).join('')}
    </table></div>`;
  // ② 실적 + (E)
  if (nv && nv.columns && nv.columns.length) {
    const cols = nv.columns, R = nv.rows || {};
    const cell = (k, r, f = won) => R[r] ? f(R[r][k]) : '—';
    h += `<h3>② 실적 · 증권사 추정(E) ${S.naver} <span class="src">네이버 증권(FnGuide 집계) · 억원 · 회사 카드 ${esc(card.fetchedAt || CARDS_AT)} 받음</span></h3>
      <div class="in-tblx"><table class="in-tbl"><tr><th></th>${cols.map((c) => `<th${c.estimate ? ' class="est"' : ''}>${esc(c.label)}${c.estimate ? '(E)' : ''} ${S.naver}</th>`).join('')}</tr>
      ${row('매출액', cols.map((c) => cell(c.key, '매출액')))}${row('영업이익', cols.map((c) => cell(c.key, '영업이익')))}${row('당기순이익', cols.map((c) => cell(c.key, '당기순이익')))}
      ${row('EPS 원', cols.map((c) => cell(c.key, 'EPS', (v) => n0(v))))}${row('PER 배', cols.map((c) => cell(c.key, 'PER', (v) => n0(v, 2))))}
      </table></div><p class="in-rp-note">(E) 열은 증권사 추정 평균 — 아직 안 난 실적. 1조 이상은 조로 적음</p>`;
  } else {
    h += `<h3>② 실적 · 증권사 추정(E)</h3><p class="in-doc-p">${SOON} 이 종목의 회사 카드가 없습니다 — tools/fetch-company-cards.py 가 받은 종목만 됩니다</p>`;
  }
  // ③ 적정가 밴드
  const est = nv && nv.columns ? nv.columns.find((c) => c.estimate) : null;
  const epsE = est && nv.rows && nv.rows.EPS ? nv.rows.EPS[est.key] : null;
  const annualPer = nv && nv.columns && nv.rows && nv.rows.PER ? nv.columns.filter((c) => !c.estimate).map((c) => nv.rows.PER[c.key]).filter((v) => v != null && v > 0) : [];
  const bandA = annualPer.length ? { lo: Math.min(...annualPer), mid: median(annualPer), hi: Math.max(...annualPer), n: annualPer.length } : null;
  const band5 = got.m && got.fin ? perBand5y(got.m, got.fin) : { ok: false, n: 0 };
  const fair = (b) => b ? [b.lo, b.mid, b.hi].map((p) => epsE != null ? n0(Math.round(epsE * p)) + '원' : '—') : ['—', '—', '—'];
  h += `<h3>③ 적정가 밴드 = 추정 EPS(E) × 과거 PER ${S.calc} <span class="src">EPS(E) ${epsE != null ? n0(epsE) + '원 · ' + esc(est.label) : '—'} · 네이버 / PER 밴드 KIS · 네이버 · ${at}</span></h3>
    <div class="in-tblx"><table class="in-tbl"><tr><th>밴드</th><th>PER 하단</th><th>중간</th><th>상단</th><th>적정가 하단 ${S.calc}</th><th>중간</th><th>상단</th></tr>
    ${bandA ? row(`(가) 연간 PER ${bandA.n}년(양수만) ${S.naver}`, [n0(bandA.lo, 2), n0(bandA.mid, 2), n0(bandA.hi, 2), ...fair(bandA)]) : row(`(가) 연간 PER ${S.naver}`, [SOON + ' 회사 카드 없음', '', '', '', '', ''])}
    ${band5.ok ? row(`(나) 5년 PER — 월봉 ${band5.months}개 ÷ 분기 EPS 4분기 합(${band5.n}개월 셈) ${S.kis}`, [n0(band5.lo, 2), n0(band5.mid, 2), n0(band5.hi, 2), ...fair(band5)]) : row(`(나) 5년 PER ${S.kis}`, [SOON + ` 셀 수 있는 달 ${band5.n}개뿐${errs.fin ? ' · 재무 못 받음' : ''}`, '', '', '', '', ''])}
    </table></div>
    <p class="in-rp-note">현재가 ${price ? n0(price.close) + '원' : '—'} · 목표가 평균 ${cs.targetPriceMean != null ? n0(cs.targetPriceMean) + '원' : '—'} 과 견준다 — 밴드의 어디(하단 · 중간 · 상단)를 기준으로 삼을지는 아직 안 정했다(재권님 결정). 분기 EPS 는 KIS 손익계산서 누적 EPS 의 차로 셈 · 적자 분기가 끼면 그 달은 셈에서 뺀다</p>`;
  // 못 받는 것
  // 못 받는 값의 줄 — 출처 배지(파랑)를 안 붙인다. 파랑은 「받을 수 있다」 는 뜻이라서다. 어디서 받을 예정인지는 글로만
  h += `<p class="in-doc-p">${SOON} EBITDA · EV/EBITDA · FCF · ROIC(DART 현금흐름표로 계산 예정) · 공매도 잔고(KIS API 유무 미확인) · 해외 종목 컨센서스(출처 미정)</p>`;
  if (Object.keys(errs).length) h += `<p class="in-rp-note">못 받은 것 — ${esc(Object.entries(errs).map(([k, v]) => `${k}: ${v}`).join(' · '))}</p>`;
  box.innerHTML = h;
}

(async () => {
  const sel = $('calc-code'); if (!sel) return;
  try {
    const r = await fetch('data/company-cards.json', { cache: 'no-store' }); const j = await r.json();
    CARDS = j.cards || {}; CARDS_AT = j.fetchedAt || '';
  } catch { CARDS = {}; }
  const kr = Object.values(CARDS).filter((c) => c.code).sort((a, b) => a.name.localeCompare(b.name, 'ko'));
  sel.innerHTML = kr.map((c) => `<option value="${esc(c.code)}">${esc(c.name)} ${esc(c.code)}</option>`).join('') || '<option value="000660">SK하이닉스 000660</option>';
  const q = new URLSearchParams(location.search).get('code');
  sel.value = q && CARDS[q] ? q : (CARDS['000660'] ? '000660' : (kr[0] ? kr[0].code : '000660'));
  sel.addEventListener('change', () => paint(sel.value));
  paint(sel.value);
})();

// ── 갈래 접기 · 펼치기(2026-10-07) — 「전부 펼치기 · 접기」 단추, 주소(#s6r · #r5 …)가 가리키는 절이 접힌 갈래 안이면 그 갈래를 열고 거기로 간다
(() => {
  const folds = document.querySelectorAll('details.rp-fold');
  const oa = $('doc-open-all'), ca = $('doc-close-all');
  if (oa) oa.addEventListener('click', () => folds.forEach((d) => { d.open = true; }));
  if (ca) ca.addEventListener('click', () => folds.forEach((d) => { d.open = false; }));
  const go = () => {
    if (!location.hash) return;
    const t = document.querySelector(location.hash); if (!t) return;
    let p = t.closest('details'); while (p) { p.open = true; p = p.parentElement && p.parentElement.closest('details'); }
    t.scrollIntoView({ block: 'start' });
  };
  go(); window.addEventListener('hashchange', go);
})();

