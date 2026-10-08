// 차트분석 화면 — 갈래 접기 · 목차 (2026-10-08). 종목 분석(analysis.js)의 접기 · 목차와 같은 모양 · 목차 그리기는 toc.js 한 곳
import { mountToc } from './toc.js';
const folds = document.querySelectorAll('#in-doc > details.rp-fold');   // 갈래만 — 안의 「원문 해석」 접기(.ca-orig)는 목차에 안 넣는다
const txt = (h) => h.textContent.replace(/\s+/g, ' ').trim();
mountToc([...folds].map((d) => { const h = d.querySelector('summary h2'); if (!h || !d.id) return null;
  return { id: d.id, title: txt(h), subs: [...d.querySelectorAll('.rp-fold-body > section[id] > h2')].map((sh) => ({ id: sh.parentElement.id, title: txt(sh) })) }; }).filter(Boolean));
document.getElementById('doc-open-all').addEventListener('click', () => folds.forEach((d) => { d.open = true; }));
document.getElementById('doc-close-all').addEventListener('click', () => folds.forEach((d) => { d.open = false; }));
const go = () => {
  if (!location.hash) return;
  const t = document.querySelector(location.hash); if (!t) return;
  let p = t.closest('details'); while (p) { p.open = true; p = p.parentElement && p.parentElement.closest('details'); }
  t.scrollIntoView({ block: 'start' });
};
go(); addEventListener('hashchange', go);

// ── ⓪ 차트에 대입해 보기 — 종목을 고르면 일봉 1년을 그리고 ① 의 네 근거를 대입한다 (2026-10-08 재권님 「차트 이미지를 보면서 대입해서 분석되면」)
// 판정은 논문이 쓴 규칙만 — 추세: 12개월 수익률의 부호(Moskowitz 외 2012) · 이동평균: 종가가 200일선 위/아래(Brock 외 1992).
// 52주 고점 · 거래량은 논문이 종목끼리 순위로 쓰거나 절대 기준이 없어 값만 낸다(「미정」 — 기준은 재권님 결정 전)
import { color } from '../../holdings/js/theme.js';
const fin = (v) => v != null && Number.isFinite(v);
const n0 = (v) => fin(v) ? Math.round(v).toLocaleString('ko-KR') : '—';
const pct = (v) => fin(v) ? `${v > 0 ? '+' : ''}${v.toFixed(1)}%` : '—';
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const ymd = (s) => s ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}` : '';
const sma = (a, n) => a.map((_, i) => i + 1 < n ? null : a.slice(i + 1 - n, i + 1).reduce((t, x) => t + x, 0) / n);
const pill = (k, t) => `<span class="in-pill ${k}">${esc(t)}</span>`;
const N = 250;   // 1년 — 52주 고점 · 12개월 수익률과 같은 창

async function load(code) {
  const r = await fetch(`/api/kis/chart?code=${code}&period=D&limit=520`, { cache: 'no-store' });
  if (!r.ok) throw new Error(String(r.status));
  const j = await r.json();
  return ((j.data && j.data.candles) || []).map((b) => ({ ts: String(b.ts), o: +b.open, h: +b.high, l: +b.low, c: +b.close, v: +b.volume })).filter((b) => fin(b.c));
}

function judge(b) {
  const c = b.map((x) => x.c), last = b[b.length - 1], w = b.slice(-N);
  const m200 = sma(c, 200), m20 = sma(c, 20), m60 = sma(c, 60);
  const ago = b.length > N ? b[b.length - 1 - N].c : null;
  const r12 = ago ? (last.c / ago - 1) * 100 : null;
  const hi = Math.max(...w.map((x) => x.h)), hiAt = w.find((x) => x.h === hi);
  const toHi = (last.c / hi - 1) * 100;
  const avg = (a) => a.reduce((t, x) => t + x, 0) / a.length;
  const v5 = avg(b.slice(-5).map((x) => x.v)), v20 = avg(b.slice(-20).map((x) => x.v)), vr = v20 ? v5 / v20 : null;
  const r5 = b.length > 5 ? (last.c / b[b.length - 6].c - 1) * 100 : null;
  return { last, r12, m200: m200[m200.length - 1], m20: m20[m20.length - 1], m60: m60[m60.length - 1], hi, hiAt, toHi, vr, r5, m200s: m200, m20s: m20, m60s: m60 };
}

function draw(b, J) {
  // 캔버스를 보이는 폭에 맞춰 다시 잡는다 — 고정 폭(1200)을 줄여 보이면 좁은 폭에서 글자가 깨알이 된다
  const cv = document.getElementById('ca-canvas'), dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth || 1200, H = W < 600 ? 280 : 380;
  cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); cv.style.height = H + 'px';
  const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const padL = W < 600 ? 62 : 78, padR = 16, padT = 14, padB = 24, volH = W < 600 ? 50 : 70;
  const w = b.slice(-N), n = w.length, off = b.length - n;
  const lo = Math.min(...w.map((x) => x.l)) * 0.97, hi = J.hi * 1.03;
  const pH = H - padT - padB - volH - 10;
  const x = (i) => padL + (W - padL - padR) * (i + 0.5) / n, y = (p) => padT + pH * (1 - (p - lo) / (hi - lo));
  ctx.clearRect(0, 0, W, H); ctx.font = `${W < 600 ? 11 : 13}px sans-serif`; ctx.textBaseline = 'middle';
  ctx.strokeStyle = color('border'); ctx.fillStyle = color('text-muted'); ctx.textAlign = 'right';
  for (let g = 0; g < 5; g++) { const p = lo + (hi - lo) * g / 4; ctx.beginPath(); ctx.moveTo(padL, y(p)); ctx.lineTo(W - padR, y(p)); ctx.stroke(); ctx.fillText(n0(p), padL - 6, y(p)); }
  const up = color('up'), dn = color('down'), bw = Math.max(1, (W - padL - padR) / n * 0.6);
  w.forEach((k, i) => { ctx.strokeStyle = ctx.fillStyle = k.c >= k.o ? up : dn; ctx.beginPath(); ctx.moveTo(x(i), y(k.h)); ctx.lineTo(x(i), y(k.l)); ctx.stroke(); ctx.fillRect(x(i) - bw / 2, y(Math.max(k.o, k.c)), bw, Math.max(1, Math.abs(y(k.o) - y(k.c)))); });
  const line = (arr, col) => { ctx.strokeStyle = col; ctx.lineWidth = 1.6; ctx.beginPath(); let s = false; arr.slice(off).forEach((v, i) => { if (v == null) return; if (!s) { ctx.moveTo(x(i), y(v)); s = true; } else ctx.lineTo(x(i), y(v)); }); ctx.stroke(); ctx.lineWidth = 1; };
  line(J.m20s, color('ma20')); line(J.m60s, color('ma60')); line(J.m200s, color('ma200'));
  ctx.setLineDash([5, 4]); ctx.strokeStyle = ctx.fillStyle = up; ctx.beginPath(); ctx.moveTo(padL, y(J.hi)); ctx.lineTo(W - padR, y(J.hi)); ctx.stroke(); ctx.setLineDash([]);
  ctx.textAlign = 'left'; ctx.fillText(`52주 고점 ${n0(J.hi)}원 (${ymd(J.hiAt.ts)})`, padL + 6, y(J.hi) + 12);
  // 거래량 — 아래 띠 · 20일 평균 선
  const vTop = padT + pH + 10, vMax = Math.max(...w.map((k) => k.v));
  w.forEach((k, i) => { ctx.fillStyle = k.c >= k.o ? up : dn; ctx.globalAlpha = 0.45; const h = volH * k.v / vMax; ctx.fillRect(x(i) - bw / 2, vTop + volH - h, bw, h); });
  ctx.globalAlpha = 1; ctx.fillStyle = color('text-muted'); ctx.textAlign = 'right'; ctx.fillText('거래량', padL - 6, vTop + volH / 2);
  [[0, 'left'], [Math.floor(n / 2), 'center'], [n - 1, 'right']].forEach(([i, al]) => { ctx.textAlign = al; ctx.fillText(ymd(w[i].ts), al === 'right' ? W - padR : al === 'left' ? padL : x(i), H - padB / 2); });
}

function table(J) {
  const UNDECIDED = pill('no', '미정');   // 미정: 52주 고점 · 거래량의 판정 기준 — 논문은 종목끼리 순위로 쓰거나 절대 기준이 없다. 재권님 결정 전
  const rows = [
    ['<a href="#c-yes-trend">추세</a>', `12개월 수익률 <b>${pct(J.r12)}</b>`, fin(J.r12) ? (J.r12 > 0 ? pill('ok', '좋다') : pill('half', '나쁘다')) : '—', '12개월 수익률이 플러스면 좋다 · 마이너스면 나쁘다(Moskowitz 외 2012)'],
    ['<a href="#c-yes-ma">이동평균</a>', `종가 ${n0(J.last.c)}원 · 200일선 ${n0(J.m200)}원 <b>${pct((J.last.c / J.m200 - 1) * 100)}</b>`, fin(J.m200) ? (J.last.c > J.m200 ? pill('ok', '좋다') : pill('half', '나쁘다')) : '—', '종가가 200일선 위면 좋다 · 아래면 나쁘다(Brock 외 1992)'],
    ['<a href="#c-yes-high">52주 고점</a>', `고점 대비 <b>${pct(J.toHi)}</b>`, UNDECIDED, '고점에 가까울수록 더 갔다(George · Hwang 2004) — 몇 % 안을 「가깝다」 로 볼지 기준이 없다'],
    ['<a href="#c-yes-vol">거래량</a>', `최근 5일 평균 ÷ 20일 평균 <b>${fin(J.vr) ? J.vr.toFixed(2) + '배' : '—'}</b> · 5일 등락 ${pct(J.r5)}`, UNDECIDED, '돌파에 거래량이 붙었나 본다 · 거래량 몰린 상승은 되돌림이 빠르다(Lee · Swaminathan 2000) — 몇 배를 「붙었다」 로 볼지 기준이 없다'],
  ];
  return `<tr><th>근거</th><th>이 종목 값</th><th>판정</th><th>기준 · 논문</th></tr>` + rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('');
}

async function show(code, name) {
  document.querySelectorAll('[data-apply-stocks] .kh-chip').forEach((b) => b.classList.toggle('is-active', b.dataset.code === code));
  const tb = document.querySelector('[data-apply-table]');
  try {
    const b = await load(code); if (b.length < 210) throw new Error('일봉이 모자람');
    const J = judge(b); draw(b, J);
    document.querySelector('[data-apply-legend]').innerHTML = `${esc(name)} · ${ymd(J.last.ts)} 까지 일봉 1년 · 선 — 20일 · 60일 · 200일 이동평균 · 점선 = 52주 고점 · 아래 띠 = 거래량`;
    tb.innerHTML = table(J);
  } catch (e) { tb.innerHTML = `<tr><td>${pill('no', '못 받음')} 일봉을 받지 못했습니다(${esc(e.message)})</td></tr>`; }
}

(async () => {
  const box = document.querySelector('[data-apply-stocks]'); if (!box) return;
  let items = [];
  try { items = (await (await fetch('data/stock-report/index.json', { cache: 'no-store' })).json()).items || []; } catch (e) { /* 목록 없음 */ }
  if (!items.length) items = [{ code: '005930', name: '삼성전자' }];
  box.innerHTML = items.map((it) => `<button type="button" class="kh-chip" data-code="${esc(it.code)}">${esc(it.name)}</button>`).join('');
  box.querySelectorAll('.kh-chip').forEach((b) => b.addEventListener('click', () => show(b.dataset.code, b.textContent)));
  const q = new URLSearchParams(location.search).get('code');
  const first = items.find((it) => it.code === q) || items.find((it) => it.code === '000660') || items[0];
  show(first.code, first.name);
})();
