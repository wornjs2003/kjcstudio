/* 재무 카드 다섯 — 모달 「투자 지표」 칸 (2026-10-02 지시)
 *
 * 재권님 — 재무 카드 시안 v3 를 보시고 「방향이 맞아 개발해」. 시안 그대로다.
 *
 *     ① 실적          매출 · 영업이익 막대(나란히) + 주가 선(우)
 *     ② 재무현황      자본 · 부채 막대(쌓기) + 부채비율 선(우)
 *     ③ PER 밴드      수정주가(일봉) + TTM EPS × 배수 선 셋
 *     ④ 이익률        매출총이익률 · 영업이익률 · 순이익률 (누적 기준)
 *     ⑤ 매출 성장률   매출 · 자본 · 총자산 증가율
 *
 * **SVG 로 그린다 — 라이브러리 없이.** `lightweight-charts` 는 시간축 차트라 막대를
 * 나란히 세우거나 쌓지 못한다. 창구가 「SVG 로」 정했다 (2026-10-02 12:2x).
 *
 * **모달에서만 그린다.** 종목 화면(stock.html)의 「투자 지표」 칸은 3열 여섯 칸 그대로다 —
 * 지시가 모달 왼쪽 열이었다. 모달이 원본이고 종목 화면이 덜어낸 쪽이라 룰과 맞는다.
 *
 * **카드 높이는 고정이다** — 칸 높이를 다섯으로 나눠 갖고, 값이 바뀌어도 자리는 안 움직인다
 * (「보는 것을 바꿔도 자리는 그대로다」). 값이 없으면 같은 틀에 「데이터 없음」 을 쓴다.
 *
 * **값은 서버가 준 것만** — `/api/kis/finance`(KIS 재무 다섯) · 일봉 · 월봉. 지어내지 않는다.
 * 다시 받는 주기는 서버의 `FINANCE_TTL` 이다 — 화면에 박지 않는다.
 */

import { fetchFinance, perBand, quarterEndCloses, ttmEps } from '../data/finance.js';
import { fetchCandles } from '../chart.js';
import { everyServerMs } from '../store/timing.js';

const RELOAD_KEY = 'kis_proxy.FINANCE_TTL';
/* 서버가 아직 안 왔을 때만 쓰는 값 — 「화면이 정한 주기」 가 아니다 (store/timing.js) */
const RELOAD_FALLBACK_MS = 6 * 3600 * 1000;
/* 그리는 분기 수 — 화면 폭 몫이다. 시안 v3 가 8분기였다 */
const QUARTERS = 8;
const NS = 'http://www.w3.org/2000/svg';

const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/** 눈금이 깔끔하게 끊기는 위 끝. 4칸으로 나눈다. */
function niceMax(v) {
  if (!(v > 0)) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  for (const m of [1, 1.2, 1.6, 2, 2.4, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}
const finite = a => a.filter(v => v != null && isFinite(v));

/* ── 카드 하나의 틀 — 축 · 눈금 · 가로 이름표 · 범례. 안의 모양은 draw 가 그린다 ── */
function frame(svg, w, h, opt) {
  const L = 28, R = opt.right ? 28 : 8, T = 20, B = 26;
  const pw = Math.max(10, w - L - R), ph = Math.max(10, h - T - B);
  const parts = [];
  parts.push(`<text x="${w / 2}" y="12" text-anchor="middle" class="fc-t">${esc(opt.title)}</text>`);
  const lo = opt.min || 0, hi = opt.max;
  /* **눈금 수는 카드 높이에서 정한다** — 창이 낮으면 카드가 70px 남짓이 되어 숫자 다섯이
     겹쳤다(2026-10-02 실측). 글자 높이(8px)의 두 배 남짓마다 하나, 많아야 넷 */
  const N = Math.max(1, Math.min(4, Math.floor(ph / 14)));
  for (let k = 0; k <= N; k++) {
    const y = T + ph - ph * k / N;
    parts.push(`<line x1="${L}" x2="${L + pw}" y1="${y}" y2="${y}" class="fc-grid"/>`);
    if (hi != null) parts.push(`<text x="${L - 3}" y="${y + 3}" text-anchor="end" class="fc-ax">${esc(opt.fmt(lo + (hi - lo) * k / N))}</text>`);
    if (opt.right && opt.right.max != null) {
      const r = opt.right;
      parts.push(`<text x="${L + pw + 3}" y="${y + 3}" class="fc-ax">${esc(r.fmt((r.min || 0) + (r.max - (r.min || 0)) * k / N))}</text>`);
    }
  }
  if (opt.unit) parts.push(`<text x="2" y="12" class="fc-ax">(${esc(opt.unit)})</text>`);
  if (opt.right && opt.right.unit) parts.push(`<text x="${w - 2}" y="12" text-anchor="end" class="fc-ax">(${esc(opt.right.unit)})</text>`);
  (opt.xlabels || []).forEach(([x, s]) => parts.push(`<text x="${L + x * pw}" y="${T + ph + 10}" text-anchor="middle" class="fc-ax">${esc(s)}</text>`));
  // 범례 — 색 점 + 이름. 출처는 title(마우스 올리면)로
  let lx = 0; const items = opt.legend.map(([cls, name, src]) => {
    const s = `<g transform="translate(${lx},0)"><title>${esc(src)}</title><rect width="7" height="7" y="-6" rx="1.5" class="${cls}"/><text x="10" class="fc-lg">${esc(name)}</text></g>`;
    lx += 16 + name.length * 7.2; return s;
  });
  parts.push(`<g transform="translate(${(w - lx) / 2},${h - 4})">${items.join('')}</g>`);
  if (opt.empty) parts.push(`<text x="${L + pw / 2}" y="${T + ph / 2}" text-anchor="middle" class="fc-nd">데이터 없음</text>`
    + (opt.emptyWhy ? `<text x="${L + pw / 2}" y="${T + ph / 2 + 12}" text-anchor="middle" class="fc-ax">${esc(opt.emptyWhy)}</text>` : ''));
  return { L, T, pw, ph, parts };
}

const linePath = pts => pts.filter(p => p).map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('');

/* ── 다섯 카드 ───────────────────────────── */
function cardResults(w, h, q, px) {
  const sale = q.map(r => r.sale), op = q.map(r => r.op);
  const pr = px.map(p => p.close);
  const empty = !finite(sale).length && !finite(op).length;
  const mx = niceMax(Math.max(...finite([...sale, ...op]), 0) / 1e4);
  const pmx = niceMax(Math.max(...finite(pr), 0));
  const f = frame(null, w, h, {
    title: '실적', unit: '조', max: mx, fmt: v => v.toFixed(0),
    right: finite(pr).length ? { max: pmx, unit: '원', fmt: v => (v / 1e4).toFixed(0) + '만' } : null,
    xlabels: q.map((r, i) => [(i + .5) / q.length, i % 2 ? '' : r.ym.slice(2, 4) + '.' + r.ym.slice(4)]).filter(x => x[1]),
    legend: [['fc-c-dim', '매출', 'KIS 손익계산서 FHKST66430200 sale_account · 연 누적에서 앞 분기를 뺀 분기 값 · 억원'],
             ['fc-c-acc', '영업이익', 'KIS 손익계산서 FHKST66430200 bsop_prti · 분기 값 · 억원'],
             ['fc-c-pri', '주가(우)', '분기 마지막 거래일 종가 · 일봉(없으면 월봉) · 마지막 점은 오늘']],
    empty,
  });
  const { L, T, pw, ph, parts } = f; const gw = pw / q.length, bw = gw * .32;
  q.forEach((r, i) => {
    const cx = L + gw * i + gw / 2;
    [[sale[i], 'fc-c-dim', cx - bw], [op[i], 'fc-c-acc', cx]].forEach(([v, cls, x]) => {
      if (v == null) return;
      const hh = Math.max(0, ph * (v / 1e4) / mx);
      parts.push(`<rect x="${x.toFixed(1)}" y="${(T + ph - hh).toFixed(1)}" width="${bw.toFixed(1)}" height="${hh.toFixed(1)}" rx="1" class="${cls}"/>`);
    });
  });
  if (finite(pr).length) {
    const pts = pr.map((v, i) => v == null ? null : [px[i].now ? L + pw : L + gw * (i + .5), T + ph - ph * v / pmx]);
    parts.push(`<path d="${linePath(pts)}" class="fc-l fc-s-pri"/>`);
    pts.forEach(p => p && parts.push(`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="2" class="fc-c-pri"/>`));
  }
  return parts.join('');
}

function cardBalance(w, h, q) {
  const eq = q.map(r => r.equity), li = q.map(r => r.liab), dr = q.map(r => r.debtRatio);
  const tot = q.map((r, i) => eq[i] != null && li[i] != null ? eq[i] + li[i] : null);
  const mx = niceMax(Math.max(...finite(tot), 0) / 1e4), rmx = niceMax(Math.max(...finite(dr), 0));
  const f = frame(null, w, h, {
    title: '재무현황', unit: '조', max: mx, fmt: v => v.toFixed(0),
    right: finite(dr).length ? { max: rmx, unit: '%', fmt: v => v.toFixed(0) } : null,
    xlabels: q.map((r, i) => [(i + .5) / q.length, i % 2 ? '' : r.ym.slice(2, 4) + '.' + r.ym.slice(4)]).filter(x => x[1]),
    legend: [['fc-c-acc', '자본총계', 'KIS 대차대조표 FHKST66430100 total_cptl · 억원'],
             ['fc-c-dim', '부채총계', 'KIS 대차대조표 FHKST66430100 total_lblt · 억원'],
             ['fc-c-grn', '부채비율(우)', 'KIS 재무비율 FHKST66430300 lblt_rate · %']],
    empty: !finite(tot).length,
  });
  const { L, T, pw, ph, parts } = f; const gw = pw / q.length, bw = gw * .5;
  q.forEach((r, i) => {
    if (tot[i] == null) return;
    const cx = L + gw * i + gw / 2, he = ph * (eq[i] / 1e4) / mx, hl = ph * (li[i] / 1e4) / mx;
    parts.push(`<rect x="${(cx - bw / 2).toFixed(1)}" y="${(T + ph - he).toFixed(1)}" width="${bw.toFixed(1)}" height="${he.toFixed(1)}" class="fc-c-acc"/>`);
    parts.push(`<rect x="${(cx - bw / 2).toFixed(1)}" y="${(T + ph - he - hl).toFixed(1)}" width="${bw.toFixed(1)}" height="${hl.toFixed(1)}" class="fc-c-dim"/>`);
  });
  if (finite(dr).length) {
    const pts = dr.map((v, i) => v == null ? null : [L + gw * i + gw / 2, T + ph - ph * v / rmx]);
    parts.push(`<path d="${linePath(pts)}" class="fc-l fc-s-grn"/>`);
    pts.forEach(p => p && parts.push(`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="2" class="fc-c-grn"/>`));
  }
  return parts.join('');
}

function cardPerBand(w, h, band, why) {
  const pts = band ? band.points : [];
  const lines = band ? band.multiples.map(m => pts.map(p => p.ttm * m)) : [];
  const all = finite([...pts.map(p => p.close), ...lines.flat()]);
  const mx = niceMax(Math.max(...all, 0));
  const n = pts.length;
  const f = frame(null, w, h, {
    title: 'PER 밴드', unit: '원', max: band ? mx : null, fmt: v => (v / 1e4).toFixed(0) + '만',
    xlabels: n ? [[0, pts[0].ts.slice(2, 4) + '.' + pts[0].ts.slice(4, 6)], [.5, pts[Math.floor(n / 2)].ts.slice(2, 4) + '.' + pts[Math.floor(n / 2)].ts.slice(4, 6)], [1, pts[n - 1].ts.slice(2, 4) + '.' + pts[n - 1].ts.slice(4, 6)]] : [],
    legend: band ? [['fc-c-pri', '수정주가', '일봉 종가'],
                    ...band.multiples.map((m, i) => [['fc-c-grn', 'fc-c-acc', 'fc-c-dim'][i], `${m}배`, `TTM EPS(KIS 재무비율 eps · 분기 4개 합) × 이 기간 PER ${['최저', '가운데', '최고'][i]} · 분기 말부터 그 EPS 를 썼다(실제 발표는 늦다)`])]
                 : [['fc-c-pri', '수정주가', '일봉 종가']],
    empty: !band, emptyWhy: why || 'EPS 나 일봉이 모자람',
  });
  if (!band) return f.parts.join('');
  const { L, T, pw, ph, parts } = f;
  // 점이 수백 개라 폭만큼만 고른다 — 모양은 그대로다
  const step = Math.max(1, Math.floor(n / pw));
  const xs = i => L + pw * i / Math.max(1, n - 1);
  const pick = arr => arr.map((v, i) => (i % step && i !== n - 1) ? null : [xs(i), T + ph - ph * v / mx]).filter(Boolean);
  ['fc-s-grn', 'fc-s-acc', 'fc-s-dim'].forEach((cls, k) => parts.push(`<path d="${linePath(pick(lines[k]))}" class="fc-l fc-dash ${cls}"/>`));
  parts.push(`<path d="${linePath(pick(pts.map(p => p.close)))}" class="fc-l fc-s-pri"/>`);
  return parts.join('');
}

function cardLines(w, h, q, title, unit, series, minZero = true) {
  const vals = finite(series.flatMap(s => q.map(r => r[s.key])));
  const hi = niceMax(Math.max(...vals, 0));
  /* 음수가 있을 때만 아래로 연다 — 없는데 `-niceMax(0)` 을 쓰면 −1 이 아래 끝이 됐다(2026-10-02) */
  const minv = Math.min(...vals, 0);
  const lo = minZero && minv < 0 ? -niceMax(-minv) : 0;
  const f = frame(null, w, h, {
    title, unit, max: vals.length ? hi : null, min: lo, fmt: v => v.toFixed(0),
    xlabels: q.map((r, i) => [(i + .5) / q.length, i % 2 ? '' : r.ym.slice(2, 4) + '.' + r.ym.slice(4)]).filter(x => x[1]),
    legend: series.map(s => [s.dot, s.name, s.src]),
    empty: !vals.length,
  });
  const { L, T, pw, ph, parts } = f; const gw = pw / q.length;
  for (const s of series) {
    const pts = q.map((r, i) => r[s.key] == null ? null : [L + gw * i + gw / 2, T + ph - ph * (r[s.key] - lo) / (hi - lo)]);
    parts.push(`<path d="${linePath(pts)}" class="fc-l ${s.stroke}"/>`);
    pts.forEach(p => p && parts.push(`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="2" class="${s.dot}"/>`));
  }
  return parts.join('');
}

/**
 * @param {Element} root   mountStockView 의 root
 * @param {{code:string}} stock
 * @returns {{ destroy: Function }}
 */
export function mountFinanceCards(root, stock) {
  const card = root.querySelector('[data-p="metric"]');
  const inModal = !!(root.closest && root.closest('.kh-modal'));
  if (!card || !inModal) return { destroy() {} };
  const body = card.querySelector('.kh-w-body');
  const host = document.createElement('div');
  host.className = 'kh-fin';
  const slots = Array.from({ length: 5 }, () => {
    const s = document.createElementNS(NS, 'svg');
    s.setAttribute('class', 'kh-fin-c');
    host.appendChild(s);
    return s;
  });
  body.appendChild(host);
  card.classList.add('has-fin');

  let dead = false, state = null;
  function draw() {
    if (dead || !state) return;
    const { q, px, band } = state;
    const makers = [
      (w, h) => cardResults(w, h, q, px),
      (w, h) => cardBalance(w, h, q),
      (w, h) => cardPerBand(w, h, band, state.bandWhy),
      (w, h) => cardLines(w, h, q, '이익률', '%·누적', [
        { key: 'grossMargin', name: '매출총이익률', dot: 'fc-c-dim', stroke: 'fc-s-dim', src: 'KIS 수익성비율 FHKST66430400 sale_totl_rate · 누적' },
        { key: 'opMargin', name: '영업이익률', dot: 'fc-c-acc', stroke: 'fc-s-acc', src: '손익계산서 누적 영업이익 ÷ 누적 매출 (서버 계산)' },
        { key: 'netMargin', name: '순이익률', dot: 'fc-c-grn', stroke: 'fc-s-grn', src: 'KIS 수익성비율 FHKST66430400 sale_ntin_rate · 누적' }]),
      (w, h) => cardLines(w, h, q, '매출 성장률 (YoY)', '%', [
        { key: 'growSale', name: '매출', dot: 'fc-c-acc', stroke: 'fc-s-acc', src: 'KIS 성장성비율 FHKST66430800 grs' },
        { key: 'growEquity', name: '자본', dot: 'fc-c-grn', stroke: 'fc-s-grn', src: 'KIS 성장성비율 FHKST66430800 equt_inrt' },
        { key: 'growAssets', name: '총자산', dot: 'fc-c-dim', stroke: 'fc-s-dim', src: 'KIS 성장성비율 FHKST66430800 totl_aset_inrt · 영업이익 증가율은 폭이 커 뺐다' }]),
    ];
    slots.forEach((s, i) => {
      const r = s.getBoundingClientRect();
      if (!r.width || !r.height) return;              // 서랍이 닫혀 있다 — 펼칠 때 다시 그린다
      s.setAttribute('viewBox', `0 0 ${r.width} ${r.height}`);
      s.innerHTML = makers[i](r.width, r.height);
    });
  }

  async function load() {
    const [fin, d, m] = await Promise.all([
      fetchFinance(stock.code),
      fetchCandles(stock.code, '1d', { view: 'modal' }).catch(() => null),   // 모달에서만 붙는 카드 — 서버에 「모달이 보고 있다」
      fetchCandles(stock.code, '1M', { view: 'modal' }).catch(() => null),
    ]);
    if (dead) return;
    const rows = fin ? fin.rows : [];
    const q = rows.slice(-QUARTERS);
    const daily = d ? d.candles : [], monthly = m ? m.candles : [];
    const px = quarterEndCloses(q.map(r => r.ym), daily, monthly);
    const last = daily[daily.length - 1];
    if (last && last.close != null) px.push({ ym: String(last.ts), close: last.close, from: 'D', now: true });
    const band = rows.length ? perBand(rows, daily) : null;
    /* 밴드가 없을 때 **왜 없는지**를 가른다 — 적자면 PER 이 성립하지 않는다(2026-10-02 · 373220 실측) */
    let bandWhy = null;
    if (!band && rows.length) {
      const t = [...ttmEps(rows).entries()].sort().pop();
      bandWhy = t && t[1] <= 0 ? '최근 4분기 EPS 합이 0 이하(적자)라 PER 이 없음' : null;
    }
    state = { q, px, band, bandWhy };
    draw();
  }

  const ro = new ResizeObserver(() => draw());
  ro.observe(host);
  load();
  const stop = everyServerMs(RELOAD_KEY, RELOAD_FALLBACK_MS, load);

  return {
    destroy() {
      dead = true;
      ro.disconnect();
      if (stop) stop();
      host.remove();
      card.classList.remove('has-fin');
    },
  };
}
