// 종목 리포트 — 참고 화면(ILOULI 보드 · 2026-10-06)의 틀을 우리 자료로 채운다 (2026-10-06 재권님 지시).
//
// 숫자는 전부 서버에서 받아 여기서 센다 — 값을 지어내지 않는다. 못 받는 것은 「아직」(빨강).
//   KIS   /api/kis/chart(일 520 · 주 · 월) · /api/kis/index-candles(코스피) · /api/kis/price · /api/kis/investor(30일) ·
//         /api/kis/investor-estimate(장중 추정) · /api/kis/finance(분기 30)
//   네이버 /api/naver/integration(지표 18 · 외국인 보유율 흐름) · /api/naver/news · data/company-cards.json(연간 표 · 추정(E) · 컨센서스)
//   DART  /api/dart/disclosures
//   글    data/stock-report/<코드>.json — 세션이 손으로 쓴다(판정 · 요약 · 시나리오 · 전략 · 촉매 해석 · 한계)
// 지표 식은 교과서(Wilder) 그대로이고 이동평균 · 볼린저 · RSI · MACD 는 holdings/js/chart.js · server/signal_watch.py 와 같은 식이다.
// 가격표(매수 · 손절 · 목표)는 재권님 결정 전 — 참고 화면 방식으로 임시 계산(priceRule). 주기 숫자 없음 — 열 때 한 번 받는다.
// 캔버스 색은 holdings/js/theme.js 의 color() 로 — theme.css 를 읽고 폴백은 그 파일 한 곳(check-theme-sync 가 대조). 여기에 hex 를 두지 않는다 (창구 검수 2026-10-06)
import { color } from '../../holdings/js/theme.js';
import { mountToc } from './toc.js';
const $ = (id) => document.getElementById(id);
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fin = (v) => v != null && Number.isFinite(v);
const n0 = (v, d = 0) => fin(v) ? v.toLocaleString('ko-KR', { maximumFractionDigits: d, minimumFractionDigits: d }) : '—';
const won = (v) => fin(v) ? n0(Math.round(v)) + '원' : '—';
const pct = (v, d = 1) => fin(v) ? `${v > 0 ? '+' : ''}${v.toFixed(d)}%` : '—';
const pp = (v, d = 1) => fin(v) ? `${v > 0 ? '+' : ''}${v.toFixed(d)}%p` : '—';
const eok = (v) => fin(v) ? (Math.abs(v) >= 10000 ? `${(v / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}조` : n0(v) + '억') : '—';
const man = (v) => fin(v) ? `${v > 0 ? '+' : ''}${(v / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}만주` : '—';
const ymd = (s) => s ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}` : '';
const md = (s) => s ? `${+s.slice(4, 6)}월 ${+s.slice(6, 8)}일` : '';
const pill = (k, t) => `<span class="in-pill ${k}">${esc(t)}</span>`;
const SOON = pill('no', '아직');
const src = (t) => `<span class="in-src" data-src="${esc(String(t).split(/[\s·(]/)[0])}">${esc(t)}</span>`;   // data-src = 받는 곳(첫 낱말) — 점 색은 insight.css
const S = { kis: src('KIS'), naver: src('네이버'), dart: src('DART'), calc: src('계산'), me: src('세션 글') };
const signCls = (v) => v > 0 ? 'rp-up' : v < 0 ? 'rp-down' : '';
const sgn = (v, f) => `<span class="${signCls(v)}">${f(v)}</span>`;

async function api(u) {
  const r = await fetch(u, { cache: 'no-store' });
  if (!r.ok) throw new Error(`${u} ${r.status}`);
  const j = await r.json();
  if (j && j.ok === false) throw new Error(j.error || u);
  return j;
}
const candles = (j) => ((j.data && (j.data.candles || j.data.bars)) || []).map((b) => ({ ts: String(b.ts || b.date || ''), o: +b.open, h: +b.high, l: +b.low, c: +b.close, v: +b.volume })).filter((b) => b.ts && fin(b.c));

// ── 지표 ──────────────────────────────────────────────────────────
const sma = (a, n) => a.map((_, i) => i + 1 < n ? null : a.slice(i + 1 - n, i + 1).reduce((s, x) => s + x, 0) / n);
function ema(a, n) { const k = 2 / (n + 1); const out = []; let e = null; for (const x of a) { e = e == null ? x : x * k + e * (1 - k); out.push(e); } return out; }
function rsi(c, n = 14) {                       // Wilder — chart.js · signal_watch.py 와 같은 식
  const out = new Array(c.length).fill(null); let g = 0, l = 0;
  for (let i = 1; i < c.length; i++) {
    const d = c[i] - c[i - 1], up = Math.max(d, 0), dn = Math.max(-d, 0);
    if (i <= n) { g += up; l += dn; if (i === n) { g /= n; l /= n; out[i] = l === 0 ? 100 : 100 - 100 / (1 + g / l); } continue; }
    g = (g * (n - 1) + up) / n; l = (l * (n - 1) + dn) / n; out[i] = l === 0 ? 100 : 100 - 100 / (1 + g / l);
  }
  return out;
}
function macd(c, f = 12, s = 26, g = 9) { const ef = ema(c, f), es = ema(c, s); const line = ef.map((x, i) => x - es[i]); const sig = ema(line, g); return { line, sig, hist: line.map((x, i) => x - sig[i]) }; }
function bollinger(c, n = 20, k = 2) { const m = sma(c, n); return c.map((x, i) => { if (m[i] == null) return null; const w = c.slice(i + 1 - n, i + 1); const sd = Math.sqrt(w.reduce((s, y) => s + (y - m[i]) ** 2, 0) / n); return { mid: m[i], up: m[i] + k * sd, lo: m[i] - k * sd, pb: sd ? (x - (m[i] - k * sd)) / (2 * k * sd) * 100 : null }; }); }
function stoch(b, n = 14, d = 3) { const k = b.map((_, i) => { if (i + 1 < n) return null; const w = b.slice(i + 1 - n, i + 1); const hh = Math.max(...w.map((x) => x.h)), ll = Math.min(...w.map((x) => x.l)); return hh === ll ? 50 : (b[i].c - ll) / (hh - ll) * 100; }); const dd = k.map((_, i) => { const w = k.slice(Math.max(0, i - d + 1), i + 1); return w.some((x) => x == null) ? null : w.reduce((s, x) => s + x, 0) / w.length; }); return { k, d: dd }; }
function trueRange(b, i) { if (i === 0) return b[0].h - b[0].l; const p = b[i - 1].c; return Math.max(b[i].h - b[i].l, Math.abs(b[i].h - p), Math.abs(b[i].l - p)); }
function atrAdx(b, n = 14) {                     // Wilder — ATR · +DI · −DI · ADX
  const len = b.length; const atr = new Array(len).fill(null), adx = new Array(len).fill(null), pdi = new Array(len).fill(null), mdi = new Array(len).fill(null);
  let tr = 0, dmp = 0, dmm = 0, dx = [], adxv = null;
  for (let i = 1; i < len; i++) {
    const up = b[i].h - b[i - 1].h, dn = b[i - 1].l - b[i].l;
    const p = up > dn && up > 0 ? up : 0, m = dn > up && dn > 0 ? dn : 0, t = trueRange(b, i);
    if (i <= n) { tr += t; dmp += p; dmm += m; if (i < n) continue; } else { tr = tr - tr / n + t; dmp = dmp - dmp / n + p; dmm = dmm - dmm / n + m; }
    atr[i] = tr / n; const di1 = tr ? dmp / tr * 100 : 0, di2 = tr ? dmm / tr * 100 : 0; pdi[i] = di1; mdi[i] = di2;
    const dxi = (di1 + di2) ? Math.abs(di1 - di2) / (di1 + di2) * 100 : 0;
    if (adxv == null) { dx.push(dxi); if (dx.length === n) adxv = dx.reduce((s, x) => s + x, 0) / n; } else adxv = (adxv * (n - 1) + dxi) / n;
    adx[i] = adxv;
  }
  return { atr, adx, pdi, mdi };
}
function obv(b) { const out = [0]; for (let i = 1; i < b.length; i++) out.push(out[i - 1] + (b[i].c > b[i - 1].c ? b[i].v : b[i].c < b[i - 1].c ? -b[i].v : 0)); return out; }
function ichimoku(b, a = 9, m = 26, l = 52) {   // chart.js 와 같은 기간(9 · 26 · 52)
  const mid = (i, n) => { if (i + 1 < n) return null; const w = b.slice(i + 1 - n, i + 1); return (Math.max(...w.map((x) => x.h)) + Math.min(...w.map((x) => x.l))) / 2; };
  const i = b.length - 1, j = i - m;                                   // 구름은 26봉 전 값이 지금 자리에 그려진다
  const tenkan = mid(i, a), kijun = mid(i, m);
  const spanA = j >= 0 && mid(j, a) != null && mid(j, m) != null ? (mid(j, a) + mid(j, m)) / 2 : null, spanB = j >= 0 ? mid(j, l) : null;
  const chikou = b[i].c, chikouRef = j >= 0 ? b[j].c : null;
  return { tenkan, kijun, spanA, spanB, chikou, chikouRef };
}
function zigzag(b, thr = 0.03) {                 // 고점 · 저점 — 3% 넘게 되돌리면 꺾인 것으로 본다
  const piv = []; if (!b.length) return piv; let dir = 0, ext = b[0], exti = 0;
  for (let i = 1; i < b.length; i++) {
    const x = b[i];
    if (dir >= 0 && x.h > ext.h) { ext = x; exti = i; }
    if (dir <= 0 && x.l < ext.l) { ext = x; exti = i; }
    if (dir >= 0 && x.l < ext.h * (1 - thr)) { piv.push({ kind: 'high', ts: ext.ts, p: ext.h, i: exti }); dir = -1; ext = x; exti = i; }
    else if (dir <= 0 && x.h > ext.l * (1 + thr)) { piv.push({ kind: 'low', ts: ext.ts, p: ext.l, i: exti }); dir = 1; ext = x; exti = i; }
  }
  return piv;
}
function crosses(c, fast, slow, b) {             // 골든 · 데드크로스 이력 + 뒤 5 · 20 봉 수익률
  const f = sma(c, fast), s = sma(c, slow), out = [];
  for (let i = 1; i < c.length; i++) {
    if (f[i] == null || s[i - 1] == null) continue;
    const was = f[i - 1] - s[i - 1], now = f[i] - s[i];
    if (was <= 0 && now > 0) out.push({ kind: '골든', i, ts: b[i].ts, r5: c[i + 5] != null ? (c[i + 5] / c[i] - 1) * 100 : null, r20: c[i + 20] != null ? (c[i + 20] / c[i] - 1) * 100 : null });
    if (was >= 0 && now < 0) out.push({ kind: '데드', i, ts: b[i].ts, r5: c[i + 5] != null ? (c[i + 5] / c[i] - 1) * 100 : null, r20: c[i + 20] != null ? (c[i + 20] / c[i] - 1) * 100 : null });
  }
  return out;
}
const last = (a) => { for (let i = a.length - 1; i >= 0; i--) if (a[i] != null) return a[i]; return null; };
function monthsAgo(ts, m) { const d = new Date(+ts.slice(0, 4), +ts.slice(4, 6) - 1 - m, +ts.slice(6, 8)); return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`; }
const atOrBefore = (arr, ts) => { let hit = null; for (const b of arr) { if (b.ts <= ts) hit = b; else break; } return hit; };
function relReturn(stock, index, months) {
  if (!stock.length || !index.length) return null;
  const l = stock[stock.length - 1], il = index[index.length - 1], t = monthsAgo(l.ts, months), s0 = atOrBefore(stock, t), i0 = atOrBefore(index, t);
  if (!s0 || !i0 || s0.ts === l.ts) return null;
  const rs = (l.c / s0.c - 1) * 100, ri = (il.c / i0.c - 1) * 100; return { rs, ri, rel: rs - ri, from: s0.ts };
}
const numStr = (s) => { const m = String(s ?? '').replace(/,/g, '').match(/-?\d+(\.\d+)?/); return m ? +m[0] : null; };
const sumBy = (rows, f) => rows.reduce((s, r) => s + (f(r) || 0), 0);

// ── 가격표 규칙 (임시 · 참고 화면 방식 · 재권님 결정 전) ──
function priceRule({ price, atr, support, resist }) {
  const s1 = support[0], r1 = resist[0];
  if (!fin(price) || !fin(atr) || !s1 || !r1) return null;
  const buy = price, stop = s1.p - atr * 0.5, target = r1.p;
  return { buy, stop, target, atr, rr: (target - buy) / (buy - stop), s1, r1 };
}

// ── 그리기 ────────────────────────────────────────────────────────
const row = (cells, head = false) => `<tr>${cells.map((c, i) => head ? `<th${i ? ' class="num"' : ''}>${c}</th>` : `<td${i ? ' class="num"' : ''}>${c}</td>`).join('')}</tr>`;
const trow = (cells, head = false) => `<tr>${cells.map((c, i) => head ? `<th>${c}</th>` : `<td${i ? ' class="wrap"' : ''}>${c}</td>`).join('')}</tr>`;   // 글이 든 표 — 칸을 접는다
const tbl = (rows) => `<div class="rp-tw"><table class="in-tbl">${rows.join('')}</table></div>`;   // 폰에서는 .rp-tw 가 가로로 민다
// 글이 긴 표(시나리오 · 전략 · 모니터링 · 10줄)는 폰에서 옆으로 잘려 카드로 — 폰 한 열 · 넓은 화면 두 열 (모바일 퍼스트)
const cards = (items) => `<div class="rp-cards">${items.map((it) => `<div class="rp-item"><b>${it.head}</b>${it.lines.map((l) => `<div>${l}</div>`).join('')}</div>`).join('')}</div>`;
const list = (items) => items && items.length ? `<ul class="rp-list">${items.map((x) => `<li>${x}</li>`).join('')}</ul>` : `<p class="rp-text">${SOON} 세션이 아직 안 썼습니다</p>`;

// 회사 재료 — 사업 구성(제품 · 지역 매출) · 경쟁 비교(ROIC) · 일정 (2026-10-08 재권님 「일부 항목들 할수있는것들은 채워줘」 →
// 「분석 화면에는 판단 근거 재료만 · 그 룰 안에서 움직여」 → 「응 그렇게 해」). 규칙은 종목 분석 문서 ⑥-11 에 있고 여기는 그 규칙대로 값을 그린다.
// 표는 회사 카드(tools/fetch-company-cards.py)가 DART 정기보고서 원문에서 줄 · 칸 그대로 옮긴 것 — 해석하지 않는다
const FIN_RE = /금융|지주|생명|화재|증권|은행|보험/;
function roicOf(c) {                                  // 약식 — 영업이익 × (1 − 세율) ÷ (자본 + 차입금 − 현금) · 세율이 0~60% 밖이면 24.2%(법정 최고)
  const n = c && c.dart && c.dart.fs && c.dart.fs.now; if (!n || n.opIncome == null || n.equity == null) return null;
  let t = (n.tax != null && n.preTax) ? n.tax / n.preTax : null; if (t == null || t < 0 || t > 0.6) t = 0.242;
  const ic = n.equity + ['stBorrow', 'curLTD', 'ltBorrow', 'bonds'].reduce((a, k) => a + (n[k] || 0), 0) - (n.cash || 0);
  return ic > 0 ? n.opIncome * (1 - t) / ic * 100 : null;
}
function rawTable(t) {                                // 칸이 합쳐진 표는 줄마다 칸 수가 달라 모자란 칸을 첫 칸 뒤에 채운다
  const w = Math.max(...t.rows.map((r) => r.length));
  const fill = (r) => r.length < w ? [r[0], ...Array(w - r.length).fill(''), ...r.slice(1)] : r;
  return tbl(t.rows.map((r, i) => trow(fill(r).map(esc), !i))) + `<p class="in-rp-note">${esc(t.unit || '')}${t.cut ? ' · 앞 14줄만' : ''} · 사업보고서 표를 줄 · 칸 그대로 옮김 — 합쳐진 칸은 비워 둠</p>`;
}
function bizHtml(card) {
  const b = card && card.dart && card.dart.business; const tb = b && b.tables;
  let h = `<h3>사업 구성 — 제품별 · 지역별 매출 ${S.dart} <small>${esc(b ? b.report : '')}${b ? ` · <a href="${esc(b.from)}" target="_blank" rel="noopener">원문 ›</a>` : ''}</small></h3>`;
  if (!tb) return h + `<p class="rp-text">${SOON} 정기보고서 원문이 회사 카드에 없습니다</p>`;
  h += `<p class="rp-text"><b>제품별</b> — 「주요 제품 및 서비스」</p>` + (tb.product ? rawTable(tb.product) : `<p class="rp-text">${pill('no', '못 뽑음')} 그 절에 매출 · 비율 표가 없거나 글로만 적혀 있습니다</p>`);
  h += `<p class="rp-text"><b>지역별</b> — 「매출 및 수주상황」</p>` + (tb.region ? rawTable(tb.region) : `<p class="rp-text">${pill('no', '못 뽑음')} 그 절에 지역 · 내수/수출 표가 없습니다 — 회사에 따라 재무제표 주석(부문 정보)에만 있다</p>`);
  // 점유율 · 매출처 · 원재료 (2026-10-08 재권님 「응 해줘」) — 회사가 사업보고서에 적은 것 그대로. 점유율은 회사가 인용한 조사기관(IDC · Omdia 등) 값이다
  const sh = tb.share;
  h += `<p class="rp-text"><b>시장점유율</b> — 「사업의 내용」 · 회사가 인용한 조사기관 값</p>` + (sh ? (sh.table ? rawTable(sh.table) : '') + (sh.text && !sh.table ? `<p class="rp-text">${esc(sh.text)}</p>` : '') : `<p class="rp-text">${pill('no', '못 뽑음')} 사업보고서에 점유율을 안 적었습니다</p>`);
  h += `<p class="rp-text"><b>주요 매출처</b> — 고객이 몰렸나</p>` + (tb.customers ? `<p class="rp-text">${esc(tb.customers)}</p>` : `<p class="rp-text">${pill('no', '못 뽑음')} 「주요 매출처」 글이 없습니다</p>`);
  h += `<p class="rp-text"><b>원재료 매입</b> — 무엇을 누구에게서 사나</p>` + (tb.materials ? rawTable(tb.materials) : `<p class="rp-text">${pill('no', '못 뽑음')} 「원재료」 절에 매입 표가 없습니다</p>`)
    + (tb.materialPrice ? `<p class="rp-text"><b>원재료 가격 추이</b></p>` + rawTable(tb.materialPrice) : '');
  return h;
}
// 산업 성장성 — 한국은행 ECOS 업종 지표 셋(data/industry.json · tools/fetch-industry.py). 종목 → 업종은 DART 업종코드 앞 두 자리
function industryHtml(card, ind) {
  const k = card && card.dart && card.dart.industryCode ? String(+String(card.dart.industryCode).slice(0, 2)) : null;
  const r = ind && ind.byKsic2 && k ? ind.byKsic2[k] : null;
  let h = `<h3>산업 성장성 — 업종이 크고 있나 ${src('ECOS')} <small>한국은행 · 업종(표준산업분류) ${esc(k || '—')} · ${esc(ind ? ind.fetchedAt : '')} 받음</small></h3>`;
  if (!r) return h + `<p class="rp-text">${SOON} 업종 지표를 못 받았습니다</p>`;
  const rows = [row(['지표', '최근', '이전', '읽는 법'], true)];
  const ss = r.sales && r.sales.series || [];
  rows.push(ss.length ? row([`매출액 증가율(${esc(r.sales.name)} · 기업경영분석)`, `${esc(ss[ss.length - 1][0])} ${pct(ss[ss.length - 1][1])}`, ss.length > 1 ? `${esc(ss[ss.length - 2][0])} ${pct(ss[ss.length - 2][1])}` : '—', '1년 전 같은 분기보다 업종 매출이 얼마나 늘었나'])
    : row(['매출액 증가율', '—', '—', esc(r.errors.sales || '못 받음')]));
  const pr = r.prod;
  rows.push(pr ? row(['생산지수(광업제조업동향)', `${esc(pr.at)} ${n0(pr.value, 1)}`, pr.yearAgo != null ? `1년 전 ${n0(pr.yearAgo, 1)}` : '—', `1년 전보다 ${pct(pr.yoy)} — 업종이 실제로 더 만들고 있나`])
    : row(['생산지수', '—', '—', esc(r.errors.prod || '못 받음')]));
  const bs = r.bsi && r.bsi.series || [];
  rows.push(bs.length ? row(['업황 전망 BSI(기업경기조사)', `${esc(bs[bs.length - 1][0])} ${n0(bs[bs.length - 1][1])}`, bs.length > 1 ? `${esc(bs[bs.length - 2][0])} ${n0(bs[bs.length - 2][1])}` : '—', '100 위면 좋아질 거라는 회사가 더 많다'])
    : row(['업황 전망 BSI', '—', '—', esc(r.errors.bsi || '못 받음')]));
  return h + tbl(rows) + `<p class="in-rp-note">업종 전체 값이라 이 회사 몫이 아니다 — 회사 매출 증가율(실적 표)과 견줘 「산업 덕인지 점유율 덕인지」 를 본다(⑥-11). 업종 묶음이 넓다(예: 반도체는 「전자영상통신장비」 안)</p>`;
}
// 경쟁 비교 — 동종기업은 종목 분석 ⑥-12 「경쟁력 재는 순서」 대로 고른 점유율 상위 경쟁사(리포트 글의 competitors · 세션이 출처와 함께 적는다).
// 그 글이 없으면 같은 지도 칸 종목으로 대신하고 「점유율 순위로 고른 것이 아님」 을 적는다 (2026-10-08 재권님 「응 그렇게 해줘」)
function peerHtml(code, card, all, comp) {
  const me = card || {};
  const fsRow = (c, label, share) => {
    const n = (c && c.dart && c.dart.fs && c.dart.fs.now) || {};
    if (c && c.edgar && c.edgar.financials) {                 // 해외 경쟁사 — 미국 증권위 EDGAR 회계연도 값(회사 전체 · 통화 그대로)
      const f = c.edgar.financials, lastOf = (x) => x && x.values ? Object.entries(x.values).sort().pop() : null;
      const rv = lastOf(f.revenue), op = lastOf(f.operatingIncome), cur = f.revenue && f.revenue.unit;
      return row([label, esc(share || '—'), rv ? `${n0(rv[1] / 1e9, 1)}십억 ${esc(cur)}` : '—', pct(rv && op ? op[1] / rv[1] * 100 : null), '—', '—', rv ? `${esc(rv[0].slice(0, 7))} 회계연도 · EDGAR` : '—']);
    }
    return row([label, esc(share || '—'), n.revenue != null ? eok(n.revenue / 1e8) : '—', pct(n.revenue ? n.opIncome / n.revenue * 100 : null),
      pct(n.equity ? n.netIncome / n.equity * 100 : null), c && FIN_RE.test(c.name) ? '금융업 안 씀' : pct(roicOf(c)), esc(c && c.dart && c.dart.fs ? c.dart.fs.year + ' ' + c.dart.fs.fsDiv + ' · DART' : '—')]);
  };
  const head = row(['', '점유율', '매출', '영업이익률', 'ROE', 'ROIC(약식)', '기준'], true);
  const note = `<p class="in-rp-note">매출 · 이익률은 회사 전체 값(부문 값 아님) · ROIC = 영업이익 × (1 − 세율) ÷ (자본 + 차입금 − 현금) · 국내 억원(1조 이상 조) · 해외는 그 회사 통화 · 규칙은 종목 분석 ⑥-11 · ⑥-12</p>`;
  if (comp && comp.list && comp.list.length) {
    const rows = [fsRow(me, `${esc(me.name || code)} <b>(이 종목)</b>`, comp.self && comp.self.share ? `${comp.self.share}${comp.self.rank ? ` · ${comp.self.rank}위` : ''}` : '')];
    for (const x of comp.list) rows.push(fsRow((all || {})[x.key], esc(x.name), `${x.share || '—'}${x.rank ? ` · ${x.rank}위` : ''}`));
    return `<h3>경쟁 비교 — ${esc(comp.product || '')} 점유율 상위 경쟁사 ${S.dart} ${src('EDGAR')} ${S.me} <small>⑥-12 순서로 고름 · 점유율 출처 ${esc(comp.source || '—')}</small></h3>${tbl([head, ...rows])}${comp.note ? `<p class="in-rp-note">${esc(comp.note)}</p>` : ''}${note}`;
  }
  const keys = new Set((me.maps || []).map((m) => m.map + '/' + m.node));
  const peers = Object.values(all || {}).filter((c) => c.code && c.code !== code && (c.maps || []).some((m) => keys.has(m.map + '/' + m.node)));
  return `<h3>경쟁 비교 — 동종기업(임시) ${S.dart} ${S.calc} <small>${pill('no', '점유율 순위로 고른 것이 아님')} 리포트 글에 ⑥-12 경쟁사가 아직 없어 같은 지도 칸(${esc((me.maps || []).map((m) => m.node).filter(Boolean).join(' · ') || '없음')}) 국내 종목으로 대신</small></h3>`
    + (me.code ? tbl([head, fsRow(me, `${esc(me.name)} <b>(이 종목)</b>`, ''), ...peers.slice(0, 6).map((c) => fsRow(c, esc(c.name), ''))]) : `<p class="rp-text">${SOON} 회사 카드 없음</p>`)
    + note + (peers.length ? '' : `<p class="in-rp-note">같은 지도 칸에 다른 국내 종목도 없어 비교할 회사가 없다</p>`);
}
function eventHtml(card) {
  const ev = (card && card.dart && card.dart.events && card.dart.events.events) || [];
  const KIND = { ir: '기업설명회(실적 발표)', dividend: '배당 기준일', agm: '주주총회' };
  return `<h3>일정 — 실적 발표 · 배당 기준일 · 주주총회 ${S.dart} <small>공시 본문 · 종류마다 최근 공시 하나</small></h3>`
    + (ev.length ? tbl([row(['', '날짜', '자세히', '공시'], true), ...ev.map((e) => trow([esc(KIND[e.kind] || e.kind), e.date ? esc(e.date) + (e.upcoming ? ' ' + pill('ok', '다가옴') : '') : pill('no', '못 읽음'),
      esc([e.what, e.pay ? '지급 ' + e.pay : '', e.dps ? '주당 ' + e.dps + '원' : ''].filter(Boolean).join(' · ') || '—'), `<a href="${esc(e.from)}" target="_blank" rel="noopener">${esc(e.filed)} ›</a>`]))])
      + `<p class="in-rp-note">「다가옴」 이 없는 줄은 지난 일정 — 다음 공시가 나오면 바뀐다 · 신제품 · 규제 날짜는 받을 길이 없다</p>`
      : `<p class="rp-text">${SOON} 최근 400일 안에 일정 공시가 없습니다</p>`);
}

function drawChart(b, levels) {
  const cv = $('rp-canvas'); if (!cv) return; const ctx = cv.getContext('2d');
  const W = cv.width, H = cv.height, padL = 70, padR = 16, padT = 12, padB = 24;
  const n = Math.min(120, b.length), w = b.slice(-n), c = b.map((x) => x.c);
  const m20 = sma(c, 20).slice(-n), m60 = sma(c, 60).slice(-n), m224 = sma(c, 224).slice(-n);
  const allY = [...w.map((x) => x.h), ...w.map((x) => x.l), ...levels.map((l) => l.p)].filter(fin);
  const lo = Math.min(...allY) * 0.98, hi = Math.max(...allY) * 1.02;
  const x = (i) => padL + (W - padL - padR) * (i + 0.5) / n, y = (p) => padT + (H - padT - padB) * (1 - (p - lo) / (hi - lo));
  ctx.clearRect(0, 0, W, H); ctx.font = '12px sans-serif'; ctx.textBaseline = 'middle';
  ctx.strokeStyle = color('border'); ctx.fillStyle = color('text-muted');
  for (let g = 0; g < 5; g++) { const p = lo + (hi - lo) * g / 4; ctx.beginPath(); ctx.moveTo(padL, y(p)); ctx.lineTo(W - padR, y(p)); ctx.stroke(); ctx.textAlign = 'right'; ctx.fillText(n0(p), padL - 6, y(p)); }
  const up = color('up'), dn = color('down');
  const bw = Math.max(2, (W - padL - padR) / n * 0.6);
  w.forEach((k, i) => { const u = k.c >= k.o; ctx.strokeStyle = ctx.fillStyle = u ? up : dn; ctx.beginPath(); ctx.moveTo(x(i), y(k.h)); ctx.lineTo(x(i), y(k.l)); ctx.stroke(); const t = y(Math.max(k.o, k.c)), h = Math.max(1, Math.abs(y(k.o) - y(k.c))); ctx.fillRect(x(i) - bw / 2, t, bw, h); });
  const line = (arr, color) => { ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath(); let s = false; arr.forEach((v, i) => { if (v == null) return; if (!s) { ctx.moveTo(x(i), y(v)); s = true; } else ctx.lineTo(x(i), y(v)); }); ctx.stroke(); ctx.lineWidth = 1; };
  line(m20, color('ma20')); line(m60, color('ma60')); line(m224, color('ma200'));
  ctx.setLineDash([4, 4]);
  levels.forEach((l) => { ctx.strokeStyle = l.kind === 'resist' ? up : dn; ctx.beginPath(); ctx.moveTo(padL, y(l.p)); ctx.lineTo(W - padR, y(l.p)); ctx.stroke(); ctx.fillStyle = ctx.strokeStyle; ctx.textAlign = 'left'; ctx.fillText(`${l.kind === 'resist' ? '저항' : '지지'} ${n0(l.p)}`, padL + 4, y(l.p) - 8); });
  ctx.setLineDash([]); ctx.fillStyle = color('text-muted'); ctx.textAlign = 'center';
  [0, Math.floor(n / 2), n - 1].forEach((i) => ctx.fillText(ymd(w[i].ts), x(i), H - padB / 2));
}

// ── 목차(js/toc.js) — 절(details.rp-fold)의 이름(배지 뺀 글)으로 항목을 만든다. 요약은 접힌 줄(.rp-sum)에만 둔다
function tocItems(folds) {
  return [...folds].map((d) => { const h = d.querySelector('summary h2'); if (!h || !d.id) return null; const c = h.cloneNode(true); c.querySelectorAll('.in-src').forEach((x) => x.remove()); return { id: d.id, title: c.textContent.trim() }; }).filter(Boolean);
}

async function main() {
  const code = new URLSearchParams(location.search).get('code') || '005930';
  const got = {}, errs = {};
  const tasks = {
    d: api(`/api/kis/chart?code=${code}&period=D&limit=520`).then(candles), w: api(`/api/kis/chart?code=${code}&period=W`).then(candles), m: api(`/api/kis/chart?code=${code}&period=M`).then(candles),
    kd: api('/api/kis/index-candles?code=KOSPI&period=D&limit=300').then(candles), kw: api('/api/kis/index-candles?code=KOSPI&period=W').then(candles),
    price: api(`/api/kis/price?code=${code}`).then((j) => j.data), inv: api(`/api/kis/investor?code=${code}`).then((j) => ({ rows: j.data || [], meta: j.meta || {} })),
    est: api(`/api/kis/investor-estimate?code=${code}`).then((j) => ({ data: j.data, meta: j.meta })), fin: api(`/api/kis/finance?code=${code}`).then((j) => ({ rows: j.data || [], meta: j.meta || {} })),
    nv: api(`/api/naver/integration?code=${code}`).then((j) => j.data), news: api(`/api/naver/news?code=${code}`).then((j) => j.data || []),
    dart: api(`/api/dart/disclosures?code=${code}`).then((j) => j.data || []),
    cards: fetch('data/company-cards.json', { cache: 'no-store' }).then((r) => r.json()), text: fetch(`data/stock-report/${code}.json`, { cache: 'no-store' }).then((r) => r.ok ? r.json() : null),
    industry: fetch('data/industry.json', { cache: 'no-store' }).then((r) => r.ok ? r.json() : null),
    brokers: fetch('data/stock-report/brokers.json', { cache: 'no-store' }).then((r) => r.ok ? r.json() : null),   // 증권사별 목표가 — tools/fetch-broker-targets.py(KIS 종목투자의견)
  };
  await Promise.all(Object.entries(tasks).map(([k, p]) => p.then((v) => { got[k] = v; }, (e) => { errs[k] = String(e.message || e); })));
  const now = new Date(), at = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${now.getHours()}:${String(now.getMinutes()).padStart(2, '0')}`;
  const T = got.text || {}; const card = got.cards && got.cards.cards ? got.cards.cards[code] : null; const nvc = card && card.naver || {};
  const b = got.d || [], c = b.map((x) => x.c), L = b.length - 1, lastBar = b[L] || null;
  const price = got.price || {}; const px = fin(price.price) ? price.price : (lastBar ? lastBar.c : null);
  const name = (got.nv && got.nv.name) || (card && card.name) || code;
  const info = (got.nv && got.nv.info) || {}; const iv = (k) => numStr(info[k] && info[k].value);

  // ── 지표 셈 ──
  const MA = {}; [5, 20, 60, 112, 224, 448].forEach((n) => { MA[n] = last(sma(c, n)); });
  const R = last(rsi(c)), M = macd(c), BB = last(bollinger(c)), ST = stoch(b), AA = atrAdx(b), OB = obv(b);
  const atr = last(AA.atr), adx = last(AA.adx), pdi = last(AA.pdi), mdi = last(AA.mdi);
  const ich = b.length > 60 ? ichimoku(b) : null;
  // 꺾임 기준 = ATR 의 두 배(최소 3%) — 삼성전자처럼 ATR 이 4% 면 3% 로는 꺾임이 너무 잦다. 지지 · 저항은 현재가에서 ATR×0.5 넘게 떨어진 것만
  const zzThr = fin(atr) && fin(px) ? Math.max(0.03, atr / px * 2) : 0.03;
  const piv = zigzag(b.slice(-260), zzThr); const lows = piv.filter((p) => p.kind === 'low').slice(-3), highs = piv.filter((p) => p.kind === 'high').slice(-3);
  const gap = fin(atr) ? atr * 0.5 : 0;
  const resist = piv.filter((p) => p.kind === 'high' && p.p > px + gap).sort((a, b2) => a.p - b2.p).slice(0, 2);
  const support = piv.filter((p) => p.kind === 'low' && p.p < px - gap).sort((a, b2) => b2.p - a.p).slice(0, 2);
  const b250 = b.slice(-250); const hi250 = b250.length ? Math.max(...b250.map((x) => x.h)) : null, lo250 = b250.length ? Math.min(...b250.map((x) => x.l)) : null;
  const x520 = crosses(c, 5, 20, b), x2060 = crosses(c, 20, 60, b), x60112 = crosses(c, 60, 112, b);
  const s224 = sma(c, 224); const stay = (() => { const w = b.slice(-120); let k = 0, t = 0; w.forEach((x, i) => { const j = b.length - 120 + i; if (s224[j] != null) { t++; if (x.c > s224[j]) k++; } }); return t ? k / t * 100 : null; })();
  const v250 = b.slice(-250); const vwap = v250.length ? sumBy(v250, (x) => x.c * x.v) / sumBy(v250, (x) => x.v) : null;
  const vol20 = b.length > 21 ? b.slice(-21, -1).reduce((s, x) => s + x.v, 0) / 20 : null, volRatio = vol20 && lastBar ? lastBar.v / vol20 : null;
  const obvUp = OB.length > 20 ? OB[OB.length - 1] > OB[OB.length - 21] : null;
  const r1 = relReturn(b, got.kd || [], 1), r6 = relReturn(b, got.kd || [], 6), r12 = relReturn(got.w || [], got.kw || [], 12);
  const pr = priceRule({ price: px, atr, support, resist });
  // 수급
  const inv = (got.inv && got.inv.rows) || []; const invSum = (n) => { const w = inv.slice(0, n); return { f: sumBy(w, (r) => r.foreign.net), i: sumBy(w, (r) => r.inst.net), p: sumBy(w, (r) => r.person.net), fa: sumBy(w, (r) => r.foreign.netAmt) / 100, ia: sumBy(w, (r) => r.inst.netAmt) / 100, pa: sumBy(w, (r) => r.person.netAmt) / 100 }; };
  const streak = (side) => { let k = 0; for (const r of inv) { if (r[side].net > 0) k++; else break; } return k; };
  const flowN = (got.nv && got.nv.flow) || []; const frNow = flowN[0] ? flowN[0].foreignRate : iv('foreignRate'), frAgo = flowN[flowN.length - 1] ? flowN[flowN.length - 1].foreignRate : null;
  // 실적
  const fq = (got.fin && got.fin.rows) || []; const fl = fq[fq.length - 1] || {}; const q5 = fq.slice(-5); const yoy = (r) => { const p = fq.find((x) => +x.ym === +r.ym - 100); return p && p.sale ? (r.sale / p.sale - 1) * 100 : null; };
  const cs = nvc.consensus || {}; const cols = nvc.columns || [], RW = nvc.rows || {}; const est = cols.find((x) => x.estimate);
  const cell = (r, k, f) => RW[r] && RW[r][k] != null ? f(RW[r][k]) : '—';

  // ── 머리 ──
  const chg = fin(price.changePct) ? price.changePct : (b.length > 1 ? (b[L].c / b[L - 1].c - 1) * 100 : null);
  $('rp-meta').textContent = `${T.author || '시황분석1'} 손글 · 기준 ${at} · 숫자는 KIS · 네이버 · DART 에서 받음 · 글은 ${T.asOf ? T.asOf + ' 에 씀' : '아직'}`;
  $('rp-title').innerHTML = `${esc(name)} <span class="rp-px">${won(px)}</span> <span class="rp-chg ${signCls(chg)}">${pct(chg, 2)}</span>`;
  const V = T.verdict || {};
  $('rp-verdict').innerHTML = V.label ? `${esc(V.label)}<small>${esc(V.direction || '')}</small>` : `${SOON} 판정은 세션이 숫자를 본 뒤 씁니다`;
  $('rp-tags').innerHTML = `${src('#stockreport')}${src('#' + code)}${src(T.author || '시황분석1')}`;

  // ── 가격표 ──
  $('rp-pricekv').innerHTML = pr ? [
    [won(pr.buy), `매수가 · 지금 사면(현재가) ${S.kis}`], [n0(pr.rr, 2), `손익비 = (목표 − 매수) ÷ (매수 − 손절) ${S.calc}`],
    [`${won(pr.stop)} <small class="rp-down">${pct((pr.stop / pr.buy - 1) * 100)}</small>`, `손절가 = 1차 지지 ${n0(pr.s1.p)} − ATR×0.5 ${S.calc}`],
    [`${won(pr.target)} <small class="rp-up">${pct((pr.target / pr.buy - 1) * 100)}</small>`, `목표가 = 1차 저항(${md(pr.r1.ts)} 고점) ${S.calc}`],
    [pr.rr >= 1.5 ? '진입 가능' : '진입 보류', '판단 · 손익비 1.5 미만이면 보류(참고 화면 기준)'],
  ].map(([v, l]) => `<div><b>${v}</b><span>${l}</span></div>`).join('') : `<div><b>—</b><span>${SOON} 지지 · 저항 · ATR 중 못 센 것이 있어 가격표를 못 만듭니다</span></div>`;
  $('rp-pricenote').textContent = `ATR(14) ${won(atr)} · 1차 지지 ${pr ? won(pr.s1.p) + '(' + md(pr.s1.ts) + ' 저점)' : '—'} · 1차 저항 ${pr ? won(pr.r1.p) + '(' + md(pr.r1.ts) + ' 고점)' : '—'} — 지지 · 저항은 최근 260봉 ZigZag(꺾임 ${n0(zzThr * 100, 1)}% = ATR×2) 저점 · 고점 중 현재가에서 ATR×0.5 넘게 떨어진 가장 가까운 것. 전부 임시 규칙이다`;

  // ── 핵심 지표 한 줄 ──
  $('rp-keykv').innerHTML = [
    [pct(fl.roe, 1).replace('+', ''), `ROE · 최근 분기 ${fl.ym || ''} ${S.kis}`], [pct(fl.opMargin, 2).replace('+', ''), `영업이익률 ${S.kis}`], [pct(fl.netMargin, 2).replace('+', ''), `순이익률 ${S.kis}`],
    [fin(price.per) ? n0(price.per, 2) + '배' : '—', `PER 확정 연간 ${S.kis} · 최근 4분기 ${iv('per') != null ? n0(iv('per'), 2) + '배' : '—'} · 추정 ${iv('cnsPer') != null ? n0(iv('cnsPer'), 2) + '배' : '—'} ${S.naver}`], [fin(price.pbr) ? n0(price.pbr, 2) + '배' : '—', `PBR ${S.kis} · ${iv('pbr') != null ? n0(iv('pbr'), 2) + '배' : '—'} ${S.naver}`],
  ].map(([v, l]) => `<div><b>${v}</b><span>${l}</span></div>`).join('');
  const f5 = invSum(5);
  $('rp-flowline').innerHTML = inv.length ? `수급 5일 외국인 ${sgn(f5.fa, (v) => eok(v))} · 기관 ${sgn(f5.ia, (v) => eok(v))} · 개인 ${sgn(f5.pa, (v) => eok(v))} ${S.kis} (금액 · 확정치)` : `${SOON} 투자자 자료 못 받음`;

  // ── 핵심 요약 · 종합 판정 ──
  // ── 갈래별 분석 (세션 글 · T.lenses) — 분석 문서 「보는 것」 표의 갈래 중 골라 쓴 것만. 없으면 절이 숨는다 (2026-10-08) ──
  const LN = Array.isArray(T.lenses) ? T.lenses : [];
  $('rp-lens').hidden = !LN.length;
  if (LN.length) {
    // 모양(2026-10-08 재권님 「인지가 더 잘되도록 정리」 → 「응 이게 더 좋네」) — 판단 먼저 · 숫자는 표(blocks) · 출처(from)와 못 본 것(gaps)은 아래 한 줄.
    // 글 안 **굵게** 만 받는다. 옛 모양(points)도 그대로 그린다
    const em = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
    const block = (k) => (k.title ? `<p class="rp-text"><b>${em(k.title)}</b></p>` : '')
      + (k.table ? tbl([trow(k.table.head.map(em), true), ...k.table.rows.map((r) => trow(r.map(em)))]) : '')
      + (k.list ? list(k.list.map(em)) : '');
    $('rp-lens-body').innerHTML = LN.map((x) => `<h3>${esc(x.name)} ${(x.sources || []).map(src).join(' ')}</h3>`
      + (x.call ? `<p class="rp-text"><b>판단</b> ${em(x.call)}</p>` : '')
      + (x.blocks || []).map(block).join('') + (x.points ? list(x.points.map(em)) : '')
      + (x.from ? `<p class="in-rp-note">출처 · 시각 — ${em(x.from)}</p>` : '')
      + (x.gaps ? `<p class="in-rp-note">못 본 것 — ${em(x.gaps)}</p>` : '')).join('');
    $('rp-lens-sum').textContent = LN.map((x) => x.name).join(' · ');
  }
  $('rp-summary-body').innerHTML = (V.label ? `<p class="rp-text"><b>판정</b> ${esc(V.label)}<br><b>방향</b> ${esc(V.direction)}<br><b>강점</b> ${esc(V.strength)}<br><b>리스크</b> ${esc(V.risk)}</p>` : `<p class="rp-text">${SOON} 판정 · 방향 · 강점 · 리스크 — 세션 글</p>`) + `<h3>종합 판정</h3>` + list((T.overall || []).map(esc));

  // ── 기본 지표 ──
  const annual = cols.length ? tbl([row(['', ...cols.map((x) => `${esc(x.label)}${x.estimate ? '(E)' : ''}`)], true), ...['매출액', '영업이익', '당기순이익', '영업이익률', 'ROE', 'EPS', 'PER', 'BPS', 'PBR'].map((r) => row([r, ...cols.map((x) => cell(r, x.key, (v) => ['매출액', '영업이익', '당기순이익'].includes(r) ? eok(v) : ['영업이익률', 'ROE'].includes(r) ? n0(v, 2) + '%' : ['PER', 'PBR'].includes(r) ? n0(v, 2) + '배' : n0(v)))]))]) : `<p class="rp-text">${SOON} 회사 카드 없음</p>`;
  const quarters = q5.length ? tbl([row(['분기', '매출액', '영업이익', '순이익', '영업이익률', '매출 YoY'], true), ...q5.map((r) => row([r.ym.slice(0, 4) + '.' + r.ym.slice(4), eok(r.sale), eok(r.op), eok(r.net), n0(r.opMargin, 2) + '%', pct(yoy(r))]))]) : `<p class="rp-text">${SOON}</p>`;
  const key2 = tbl([row(['지표', '값', '출처'], true),
    row(['PER(확정 연간 EPS 기준)', fin(price.per) ? n0(price.per, 2) + '배' : '—', 'KIS']), row(['PER(최근 4분기 EPS 기준) · 그 EPS', `${iv('per') != null ? n0(iv('per'), 2) + '배' : '—'} · ${won(iv('eps'))}`, '네이버']), row(['추정 PER · 추정 EPS', `${iv('cnsPer') != null ? n0(iv('cnsPer'), 2) + '배' : '—'} · ${won(iv('cnsEps'))}`, '네이버']),
    row(['PBR · BPS', `${fin(price.pbr) ? n0(price.pbr, 2) + '배' : '—'} · ${won(iv('bps'))}`, 'KIS · 네이버']), row(['EPS(확정)', won(fin(price.eps) ? price.eps : iv('eps')), 'KIS']),
    row(['부채비율 · ROE(분기)', `${n0(fl.debtRatio, 2)}% · ${n0(fl.roe, 2)}%`, `KIS 재무 ${fl.ym || ''}`]), row(['외국인 지분율', frNow != null ? n0(frNow, 2) + '%' : '—', '네이버']),
    row(['시가총액', info.marketValue ? esc(info.marketValue.value) : (fin(price.marketCap) ? eok(price.marketCap / 100000000) : '—'), '네이버']), row(['52주 최고 · 최저', `${won(iv('highPriceOf52Weeks'))} · ${won(iv('lowPriceOf52Weeks'))}`, '네이버']), row(['250봉 최고 · 최저(일봉 고가 · 저가)', `${won(hi250)} · ${won(lo250)}`, 'KIS 차트 · 계산']),
    row(['배당수익률 · 주당배당금', `${info.dividendYieldRatio ? esc(info.dividendYieldRatio.value) : '—'} · ${won(iv('dividend'))}`, '네이버']),
    row(['목표가 평균 · 투자의견 평균', `${won(cs.targetPriceMean)} (${fin(px) && cs.targetPriceMean ? pct((cs.targetPriceMean / px - 1) * 100) : '—'}) · ${cs.recommMean != null ? n0(cs.recommMean, 2) + ' / 5' : '—'}`, `네이버(FnGuide) ${esc(cs.asOf || '')}`]),
  ]);
  // 증권사별 목표가 — 최고 · 평균 · 최저 세 칸 (2026-10-07 재권님 「증권사별로 책정된 값을 넣어주면 좋을거같은데」 → 「너무 많은데 최고와 최저 평균으로」).
  // 네이버는 평균만 준다 — KIS 종목투자의견을 tools/fetch-broker-targets.py 가 받아 둔 파일(증권사마다 가장 최근 값)에서 센다
  const BK = got.brokers && got.brokers.items ? got.brokers.items[code] : null, bl = BK ? BK.brokers || [] : [];
  const vsPx = (v) => fin(px) ? ` <small class="rp-up">${pct((v / px - 1) * 100)}</small>` : '';
  let brokerBox = `<h3>증권사별 목표가 ${S.kis}</h3><p class="rp-text">${SOON} 받아 둔 값이 없습니다 — tools/fetch-broker-targets.py</p>`;
  if (bl.length) {
    const hi = bl.reduce((a, b) => b.target > a.target ? b : a), lo = bl.reduce((a, b) => b.target < a.target ? b : a);
    const avg = bl.reduce((s, b) => s + b.target, 0) / bl.length, md = (s) => `${s.slice(4, 6)}-${s.slice(6, 8)}`;
    brokerBox = `<h3>증권사별 목표가 ${S.kis} <small>${bl.length}곳 · 증권사마다 가장 최근 값 · ${ymd(BK.from)} 이후 · 받은 시각 ${esc(BK.fetchedAt)}</small></h3>
      <div class="rp-kv rp-kv3">
        <div><b>${won(hi.target)}${vsPx(hi.target)}</b><span>최고 · ${esc(hi.broker)} ${md(hi.date)}</span></div>
        <div><b>${won(avg)}${vsPx(avg)}</b><span>평균 · ${bl.length}곳 · 네이버 평균 ${won(cs.targetPriceMean)}</span></div>
        <div><b>${won(lo.target)}${vsPx(lo.target)}</b><span>최저 · ${esc(lo.broker)} ${md(lo.date)}</span></div>
      </div>
      <p class="in-rp-note">% 는 현재가 ${won(px)} 대비 · 네이버 평균과 다른 까닭 — 평균에 넣는 기간이 다르다 · 실적 추정은 증권사별로 못 받는다(위 (E)는 네이버 평균)</p>`;
  }
  $('rp-fund-body').innerHTML = `<h3>연간 실적 · 증권사 추정(E) ${S.naver} <small>억원 · 회사 카드 ${esc(card && card.fetchedAt || got.cards && got.cards.fetchedAt || '')}</small></h3>${annual}<h3>최근 5분기 ${S.kis} <small>억원</small></h3>${quarters}<h3>핵심 지표</h3>${key2}<h3>최근 리포트 ${S.naver}</h3>${nvc.reports && nvc.reports.length ? tbl([row(['날짜', '증권사', '제목'], true), ...nvc.reports.slice(0, 5).map((r) => trow([ymd(r.date), esc(r.broker), `<a href="${esc(r.from)}" target="_blank" rel="noopener">${esc(r.title)}</a>`]))]) : `<p class="rp-text">${SOON}</p>`}${brokerBox}${industryHtml(card, got.industry)}${bizHtml(card)}${peerHtml(code, card, got.cards && got.cards.cards, T.competitors)}`;

  // ── 차트 ──
  const levels = [...resist.map((p) => ({ kind: 'resist', p: p.p })), ...support.map((p) => ({ kind: 'support', p: p.p }))];
  if (b.length) drawChart(b, levels);
  $('rp-chart-note').textContent = `일봉 ${Math.min(120, b.length)}개 · 선 = MA20 · MA60 · MA224(홀딩스 차트와 같은 색) · 점선 = 지지 · 저항 · ${lastBar ? '마지막 봉 ' + ymd(lastBar.ts) : ''}`;

  // ── 기술적 지표 ──
  const maRows = [5, 20, 60, 112, 224, 448].map((n) => row([`MA${n}${n === 5 ? '(1주)' : n === 20 ? '(1개월)' : n === 60 ? '(3개월)' : n === 112 ? '(6개월)' : n === 224 ? '(1년)' : '(2년)'}`, won(MA[n]), MA[n] ? pct((px / MA[n] - 1) * 100) : '—']));
  const arrS = MA[5] > MA[20] && MA[20] > MA[60] ? '정배열' : MA[5] < MA[20] && MA[20] < MA[60] ? '역배열' : '혼조', arrL = MA[112] > MA[224] && MA[224] > MA[448] ? '정배열' : MA[112] < MA[224] && MA[224] < MA[448] ? '역배열' : '혼조';
  const mom = tbl([row(['지표', '값', '읽기'], true),
    row(['RSI(14)', n0(R, 1), R == null ? '—' : R >= 70 ? '과매수' : R <= 30 ? '과매도' : '중립']),
    row(['MACD 히스토그램(12·26·9)', n0(last(M.hist), 0), last(M.hist) > 0 ? '강세' : '약세']),
    row(['볼린저 %B(20·2)', BB ? n0(BB.pb, 1) : '—', BB ? (BB.pb > 100 ? '상단 밖' : BB.pb > 80 ? '상단' : BB.pb < 0 ? '하단 밖' : BB.pb < 20 ? '하단' : '중간') : '—']),
    row(['스토캐스틱 %K · %D(14·3)', `${n0(last(ST.k), 1)} · ${n0(last(ST.d), 1)}`, last(ST.k) >= 80 ? '과매수' : last(ST.k) <= 20 ? '과매도' : '중립']),
    row(['ADX(14) · +DI · −DI', `${n0(adx, 1)} · ${n0(pdi, 1)} · ${n0(mdi, 1)}`, adx == null ? '—' : adx < 20 ? '추세 약함' : adx > 40 ? '추세 강함' : '추세 있음']),
    row(['ATR(14)', won(atr), fin(atr) && fin(px) ? `현재가의 ${n0(atr / px * 100, 2)}%` : '—']),
    row(['OBV', obvUp == null ? '—' : obvUp ? '상승(20봉 전보다 위)' : '하락', '거래량 누적 흐름']),
    row(['거래량 배율', fin(volRatio) ? n0(volRatio, 2) + '배' : '—', '마지막 봉 ÷ 20일 평균']),
    row(['224선 체류율(최근 120봉)', stay != null ? n0(stay, 0) + '%' : '—', '종가가 MA224 위에 있던 비율']),
    row(['250일 VWAP', won(vwap), fin(vwap) && fin(px) ? `현재가 ${pct((px / vwap - 1) * 100)}` : '—']),
  ]);
  const ichT = ich ? tbl([row(['일목균형표(9·26·52)', '값'], true), row(['전환선', won(ich.tenkan)]), row(['기준선', won(ich.kijun)]), row(['구름(선행 A · B)', `${won(ich.spanA)} 〜 ${won(ich.spanB)}`]), row(['캔들 위치', ich.spanA != null && ich.spanB != null ? (px > Math.max(ich.spanA, ich.spanB) ? '구름 위' : px < Math.min(ich.spanA, ich.spanB) ? '구름 아래' : '구름 안') : '—']), row(['전환선 vs 기준선', ich.tenkan != null && ich.kijun != null ? (ich.tenkan > ich.kijun ? '전환선이 위' : '전환선이 아래') : '—']), row(['후행스팬', ich.chikouRef != null ? `${won(ich.chikou)} · 26일 전 종가 ${won(ich.chikouRef)}보다 ${ich.chikou > ich.chikouRef ? '위' : '아래'}` : '—'])]) : `<p class="rp-text">${SOON}</p>`;
  const xr = (arr, name2) => { const l2 = arr.slice(-3).reverse(); return l2.length ? l2.map((x) => row([`${name2} ${x.kind}크로스`, md(x.ts), pct(x.r5), pct(x.r20)])).join('') : row([name2, '없음(520봉 안)', '', '']); };
  const xT = tbl([row(['이평 교차', '날짜', '뒤 5봉', '뒤 20봉'], true), xr(x520, 'MA5×20'), xr(x2060, 'MA20×60'), xr(x60112, 'MA60×112')]);
  const zz = tbl([row(['ZigZag(3%)', '날짜', '가격'], true), ...lows.map((p) => row(['저점', md(p.ts), won(p.p)])), ...highs.map((p) => row(['고점', md(p.ts), won(p.p)]))]);
  const rel = tbl([row(['코스피 대비 상대수익률', '종목', '코스피', '상대'], true), ...[['1개월', r1], ['6개월', r6], ['12개월(주봉)', r12]].map(([lb, r]) => r ? row([lb, pct(r.rs), pct(r.ri), pp(r.rel)]) : row([lb, SOON, '', '']))]);
  $('rp-tech-body').innerHTML = `<div class="rp-cols"><div><h3>이동평균 · 배열 — 단기 ${arrS} · 장기 ${arrL}</h3>${tbl([row(['이평', '값', '현재가 이격'], true), ...maRows])}${xT}</div><div><h3>모멘텀 · 변동성</h3>${mom}${ichT}</div></div><div class="rp-cols">${zz}${rel}</div>`;

  // ── 수급 ──
  const two = (a, q) => `${sgn(a, eok)}<br><small>${man(q)}</small>`;   // 금액 위 · 수량 아래 — 폰에서 한 줄에 안 들어간다
  const fT = tbl([row(['기간', '외국인', '기관', '개인'], true), ...[3, 5, 10, 20].map((n) => { const s = invSum(n); return row([`${n}일`, two(s.fa, s.f), two(s.ia, s.i), two(s.pa, s.p)]); })]);
  const estD = got.est && got.est.data && got.est.data.latest;
  $('rp-flow-body').innerHTML = `${inv.length ? fT : `<p class="rp-text">${SOON}</p>`}<p class="in-rp-note">금액 억원 · 수량 주 · KIS 투자자 ${inv.length}일치(${inv.length ? ymd(inv[inv.length - 1].date) + '〜' + ymd(inv[0].date) : ''}) · 30일 넘는 기간은 못 센다</p>
    ${tbl([row(['항목', '값', '출처'], true), row(['외국인 연속 순매수', `${streak('foreign')}일`, 'KIS']), row(['기관 연속 순매수', `${streak('inst')}일`, 'KIS']),
      row(['외국인 보유율', `${frAgo != null ? n0(frAgo, 2) + '% → ' : ''}${frNow != null ? n0(frNow, 2) + '%' : '—'}${flowN.length ? ` (${flowN.length}일 사이)` : ''}`, '네이버']),
      row(['장중 추정(외국인 · 기관)', estD ? `${man(estD.foreign)} · ${man(estD.inst)} (${estD.seq}차)` : '—', 'KIS 가집계 · 확정치와 다름']),
      row(['공매도 비율 · 잔고', SOON + ' KIS 공매도 API 실호출 전', '—']), row(['3개월 · 6개월 수급', SOON + ' 30일 넘는 자료 없음', '—'])])}`;

  // ── 촉매 ──
  const C = T.catalysts || {};
  const dT = got.dart && got.dart.length ? tbl([row(['접수일', '공시', '제출인'], true), ...got.dart.slice(0, 5).map((d) => trow([ymd(d.date), `<a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a>`, esc(d.filer)]))]) : `<p class="rp-text">${SOON} 공시 못 받음</p>`;
  const nT = got.news && got.news.length ? tbl([row(['시각', '매체', '제목'], true), ...got.news.slice(0, 5).map((x) => trow([`${x.at.slice(4, 6)}/${x.at.slice(6, 8)} ${x.at.slice(8, 10)}:${x.at.slice(10, 12)}`, esc(x.office), `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>`]))]) : `<p class="rp-text">${SOON} 뉴스 못 받음</p>`;
  $('rp-cat-body').innerHTML = `<div class="rp-cols"><div><h3>주요 호재 ${S.me}</h3>${list((C.positive || []).map(esc))}</div><div><h3>주요 위험 ${S.me}</h3>${list((C.negative || []).map(esc))}</div></div><h3>예정 · 진행 이벤트 ${S.me}</h3>${list((C.events || []).map(esc))}${eventHtml(card)}<h3>최근 공시 ${S.dart}</h3>${dT}<h3>관련 뉴스 ${S.naver}</h3>${nT}`;

  // ── 지지 · 저항 ──
  $('rp-sr-body').innerHTML = tbl([row(['구분', '가격', '현재가에서', '근거'], true), ...resist.slice().reverse().map((p) => row(['저항', won(p.p), pct((p.p / px - 1) * 100), `${md(p.ts)} 고점(ZigZag)`])), ...support.map((p) => row(['지지', won(p.p), pct((p.p / px - 1) * 100), `${md(p.ts)} 저점(ZigZag)`]))].concat(ich && ich.spanA != null ? [row(['구름 상단 · 하단', `${won(Math.max(ich.spanA, ich.spanB))} · ${won(Math.min(ich.spanA, ich.spanB))}`, '', '일목'])] : [])) + `<p class="in-rp-note">임시 규칙 — 최근 260봉 ZigZag(3%) 꺾임점. 규칙은 재권님 결정 뒤 바꾼다</p>`;

  // ── 시나리오 · 전략 ──
  const SC = T.scenarios || [];
  $('rp-scn-body').innerHTML = SC.length ? cards(SC.map((s) => ({ head: `${esc(s.name)} · ${esc(s.prob)}`, lines: [`<b>목표</b> ${esc(s.target)}`, `<b>조건</b> ${esc(s.cond)}`] }))) : `<p class="rp-text">${SOON} 세션 글</p>`;
  const ST2 = T.strategy || {};
  const posT = ST2.positions && ST2.positions.length ? cards(ST2.positions.map((p) => ({ head: esc(p.name), lines: [`<b>목표</b> ${esc(p.target)}`, `<b>매수</b> ${esc(p.buy)}`, `<b>손절</b> ${esc(p.stop)}`, `<b>판단</b> ${esc(p.call)}`] }))) : (pr ? cards([{ head: '지금 사면(임시 규칙)', lines: [`<b>목표</b> ${won(pr.target)}`, `<b>매수</b> ${won(pr.buy)}`, `<b>손절</b> ${won(pr.stop)}`, `<b>손익비</b> ${n0(pr.rr, 2)}`] }]) : `<p class="rp-text">${SOON}</p>`);
  const monT = ST2.monitor && ST2.monitor.length ? cards(ST2.monitor.map((m2) => ({ head: esc(m2.name), lines: [`<b class="rp-up">강세</b> ${esc(m2.bull)}`, `<b class="rp-down">약세</b> ${esc(m2.bear)}`] }))) : `<p class="rp-text">${SOON} 모니터링 표 — 세션 글</p>`;
  $('rp-plan-body').innerHTML = `${posT}<h3>모니터링 지표</h3>${monT}`;

  // ── 10줄 · 한계 ──
  $('rp-ten-body').innerHTML = T.summary10 && T.summary10.length ? cards(T.summary10.map((s, i) => ({ head: `${i + 1}. ${esc(s.item)} — ${esc(s.now)}`, lines: [esc(s.mean)] }))) : `<p class="rp-text">${SOON} 세션 글</p>`;
  const gaps = [];
  if (errs.inv) gaps.push('투자자 자료 못 받음'); gaps.push('공매도 — KIS 공매도 API 실호출 전'); if (!bl.length) gaps.push('증권사별 목표가 — 받아 둔 값 없음(tools/fetch-broker-targets.py)'); gaps.push('3개월 · 6개월 수급 — 30일 넘는 자료 없음'); gaps.push('업종 밸류에이션 — 자료 없음'); gaps.push('가격표 · 지지저항 규칙 — 임시(참고 화면 방식)');
  Object.entries(errs).forEach(([k, v]) => gaps.push(`${k} 못 받음 — ${esc(v)}`));
  $('rp-limit-body').innerHTML = `<h3>데이터 공백 ${S.calc}</h3>${list(gaps)}<h3>세션이 적은 한계 ${S.me}</h3>${list((T.limits || []).map(esc))}<p class="rp-text"><b>신뢰도</b> ${T.confidence ? esc(T.confidence) : SOON}</p>`;
  $('rp-foot').textContent = `기준 ${at} · 투자 판단의 참고 자료이며 투자 책임은 본인에게 있습니다 · 이 리포트는 세션이 손으로 쓴 것이고 규칙은 삼성전자로 다듬어 정한 뒤 다른 종목으로 넓힌다 (2026-10-06 재권님 지시)`;
  // ── 절마다 한 줄 요약(접힌 채로 읽히는 줄) + 전부 펼치기 · 접기 ──
  const sum = (id, text) => { const el = $(id + '-sum'); if (el) el.textContent = text; };
  sum('rp-summary', V.label ? `${V.direction || ''}` : '세션 글 아직');
  sum('rp-fund', `추정 PER ${iv('cnsPer') != null ? n0(iv('cnsPer'), 1) + '배' : '—'} · 확정 ${fin(price.per) ? n0(price.per, 1) + '배' : '—'} · ROE ${n0(fl.roe, 1)}% · 목표가 평균 ${won(cs.targetPriceMean)}`);
  sum('rp-chart', `단기 ${arrS} · 장기 ${arrL} · MA224 대비 ${MA[224] ? pct((px / MA[224] - 1) * 100) : '—'}`);
  sum('rp-tech', `RSI ${n0(R, 0)} · ADX ${n0(adx, 0)}(${adx == null ? '—' : adx < 20 ? '추세 약함' : adx > 40 ? '추세 강함' : '추세 있음'}) · 볼린저 %B ${BB ? n0(BB.pb, 0) : '—'} · 일목 ${ich && ich.spanA != null ? (px > Math.max(ich.spanA, ich.spanB) ? '구름 위' : px < Math.min(ich.spanA, ich.spanB) ? '구름 아래' : '구름 안') : '—'}`);
  sum('rp-flow', inv.length ? `5일 외국인 ${eok(f5.fa)} · 기관 ${eok(f5.ia)} · 개인 ${eok(f5.pa)} · 외국인 보유율 ${frNow != null ? n0(frNow, 2) + '%' : '—'}` : '투자자 자료 없음');
  sum('rp-cat', `호재 ${(C.positive || []).length} · 위험 ${(C.negative || []).length} · 공시 ${Math.min(5, (got.dart || []).length)} · 뉴스 ${Math.min(5, (got.news || []).length)}`);
  sum('rp-sr', `지지 ${support.map((p) => won(p.p)).join(' · ') || '—'} / 저항 ${resist.map((p) => won(p.p)).join(' · ') || '—'}`);
  sum('rp-scn', SC.length ? SC.map((x) => `${x.name} ${x.prob}`).join(' · ') : '세션 글 아직');
  sum('rp-plan', ST2.positions && ST2.positions.length ? ST2.positions.map((x) => x.name).join(' · ') + ` · 모니터링 ${(ST2.monitor || []).length}` : '세션 글 아직');
  sum('rp-ten', T.summary10 && T.summary10.length ? T.summary10.map((x) => x.item).join(' · ') : '세션 글 아직');
  sum('rp-limit', `데이터 공백 ${gaps.length} · 신뢰도 ${T.confidence ? T.confidence.split(' ')[0] : '—'}`);
  const folds = document.querySelectorAll('details.rp-fold:not([hidden])');   // 숨은 절(글이 없는 갈래별 분석)은 목차에서 뺀다
  mountToc(tocItems(folds));   // 목차(오른쪽 기둥 · 폰 단추)
  $('rp-open-all').addEventListener('click', () => folds.forEach((d) => { d.open = true; }));
  $('rp-close-all').addEventListener('click', () => folds.forEach((d) => { d.open = false; }));
  // 주소로 절을 가리키면 그 절을 펼치고 거기로 간다 — ?open=all 은 전부 펼침, #rp-tech 는 그 절만 (링크로 자리를 넘길 때 · 폰 그림 찍을 때)
  const q = new URLSearchParams(location.search);
  if (q.get('open') === 'all') folds.forEach((d) => { d.open = true; });
  if (location.hash) { const t = document.querySelector(location.hash); if (t) { if (t.tagName === 'DETAILS' && q.get('open') !== 'none') t.open = true; t.scrollIntoView({ block: 'start' }); } }   // open=none 이면 접힌 채 그 자리로만
  window.__rp = { px, hi250, lo250, zzThr, MA, R, M, BB, ST, atr, adx, pdi, mdi, ich, piv, resist, support, pr, stay, vwap, volRatio, obvUp, r1, r6, r12, invSum: { 3: invSum(3), 5: invSum(5), 10: invSum(10), 20: invSum(20) }, fl, frNow, frAgo, errs };
}
main();
