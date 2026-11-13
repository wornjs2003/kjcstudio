// 옵션 만기일 (11-12 재권님 배분 「투자 전략에 「옵션 만기일」 칸 — 올해 만기일 · 다음 거래일 코스피 시가 · 종가 표 + 그래프」 →
//   시안 temp/시황분석1-expiry-1142 에 「응 해」 11-13) — 단타 판 아래
//   값  만기일 목록은 서버 /api/kis/opt-expiry?year= (개발 · 달 · 날 · witch 선물 동시 만기 · sure 휴장일 표에 있나)
//       코스피 일봉은 서버 /api/kis/index-daily?codes=KOSPI (올해 1월 1일부터) — 화면은 등락률만 셈(받은 시가 · 종가끼리)
//   다음 거래일 = 일봉에서 만기일 다음 봉 · 아직 안 왔으면 「아직」(0 이 아니다) · 그날 봉이 없으면 —
import { signClass, NUM } from '/assets/js/sign.js';   // 오르내림 글씨 색 — 셈은 sign.js 한 곳

const box = document.getElementById('mx');
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const f2 = (v) => (v == null ? '—' : Number(v).toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const pct = (a, b) => (a == null || b == null || !b ? null : (a / b - 1) * 100);
const pc = (v) => { if (v == null) return '<span class="mx-mut">—</span>'; const c = signClass(v, NUM); const t = `${v > 0 ? '+' : ''}${v.toFixed(2)}%`; return c ? `<span class="${c}">${t}</span>` : t; };
const WD = '일월화수목금토';
const dd = (s) => { const d = new Date(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6)); return `${+s.slice(4, 6)}-${s.slice(6)}(${WD[d.getDay()]})`; };
async function getJson(u) { try { const r = await fetch(u, { cache: 'no-store' }); return { st: r.status, j: r.ok ? await r.json() : null }; } catch (e) { return { st: 0, j: null }; } }

let rows = [], bars = [];

function graph() {
  const svg = box.querySelector('.mx-g'); if (!svg) return;
  const W = svg.getBoundingClientRect().width, H = svg.getBoundingClientRect().height, pl = 46, pr = 8, pt = 10, pb = 22;
  if (!W || bars.length < 2) { svg.innerHTML = ''; return; }
  const cs = bars.map((b) => b.close), lo = Math.min(...cs), hi = Math.max(...cs);
  const idx = new Map(bars.map((b, i) => [b.date, i]));
  const x = (i) => pl + (i / (bars.length - 1)) * (W - pl - pr), y = (v) => pt + (1 - (v - lo) / (hi - lo || 1)) * (H - pt - pb);
  let s = '';
  for (let k = 0; k <= 4; k++) { const v = lo + (hi - lo) * k / 4; s += `<line class="mx-gl" x1="${pl}" x2="${W - pr}" y1="${y(v)}" y2="${y(v)}"/><text x="${pl - 6}" y="${y(v) + 4}" text-anchor="end">${Math.round(v).toLocaleString('ko-KR')}</text>`; }
  rows.forEach(({ e }) => { const i = idx.get(e.day); if (i == null) return; s += `<line class="mx-ex${e.witch ? ' w' : ''}" x1="${x(i)}" x2="${x(i)}" y1="${pt}" y2="${H - pb}"/><text x="${x(i)}" y="${H - 6}" text-anchor="middle">${e.month}월</text>`; });
  s += `<polyline class="mx-ln" points="${bars.map((b, i) => `${x(i)},${y(b.close)}`).join(' ')}"/>`;
  rows.forEach(({ b, n }) => { if (!b || !n) return; const c = signClass(n.close - b.close, NUM); s += `<circle class="mx-pt ${c || ''}" cx="${x(idx.get(n.date))}" cy="${y(n.close)}" r="4"/>`; });
  svg.innerHTML = s;
}

async function load() {
  const year = new Date().getFullYear();
  const [L, K] = await Promise.all([getJson(`/api/kis/opt-expiry?year=${year}`), getJson('/api/kis/index-daily?codes=KOSPI')]);
  const meta = box.querySelector('.st-meta'), body = box.querySelector('.mx-body');
  const list = L.j && L.j.ok && Array.isArray(L.j.data) ? L.j.data : null;
  const kb = K.j && K.j.data && K.j.data.KOSPI ? K.j.data.KOSPI.bars : null;
  if (!list) { meta.textContent = `— 만기일 목록을 못 받음(${L.st || '연결 안 됨'})`; body.innerHTML = '<div class="st-err">— 서버 /api/kis/opt-expiry 값이 없음</div>'; return; }
  bars = Array.isArray(kb) ? kb : [];
  const idx = new Map(bars.map((b, i) => [b.date, i]));
  rows = list.map((e) => { const i = idx.get(e.day); return { e, b: i == null ? null : bars[i], p: i ? bars[i - 1] : null, n: i == null ? null : bars[i + 1] || null }; });
  const today = bars.length ? bars[bars.length - 1].date : '';
  const unsure = list.filter((e) => e.sure === false).length;
  meta.textContent = `${year}년 · 만기일 ${list.length}번 · 코스피 일봉 ${bars.length}개(${bars.length ? `${dd(bars[0].date)} ~ ${dd(today)}` : '못 받음'})${unsure ? ` · 휴장일 표에 아직 없어 평일로 셈 ${unsure}` : ''} · 만기일 = 그 달 둘째 목요일(휴장이면 앞 거래일) · 3 · 6 · 9 · 12월은 선물도 함께 만기(세마녀)`;
  const tr = rows.map(({ e, b, p, n }) => `<tr>
    <td>${e.month}월</td><td><b${e.sure === false ? ' data-tip="휴장일 표에 아직 그날이 없어 평일로 셈"' : ''}>${dd(e.day)}</b>${e.witch ? ' <span class="mx-w">세마녀</span>' : ''}${e.sure === false ? ' <span class="mx-mut">평일로 셈</span>' : ''}</td>
    <td>${b ? f2(b.open) : '—'}</td><td>${b ? f2(b.close) : '—'}</td><td>${pc(b && p ? pct(b.close, p.close) : null)}</td><td>${pc(b ? pct(b.close, b.open) : null)}</td>
    <td class="mx-sep">${n ? dd(n.date) : `<span class="mx-mut">${b ? '아직' : e.day > today ? '아직 안 옴' : '—'}</span>`}</td>
    <td>${n ? f2(n.open) : '—'}</td><td>${n ? f2(n.close) : '—'}</td><td>${pc(n && b ? pct(n.open, b.close) : null)}</td><td>${pc(n && b ? pct(n.close, b.close) : null)}</td><td>${pc(n ? pct(n.close, n.open) : null)}</td></tr>`).join('');
  body.innerHTML = `<div class="st-scroll mx-tw"><table class="mx-tb">
      <thead><tr class="mx-grp"><th></th><th colspan="5">만기일</th><th colspan="6" class="mx-sep">다음 거래일</th></tr>
      <tr><th>달</th><th>날</th><th>시가</th><th>종가</th><th>등락률</th><th>시가→종가</th><th class="mx-sep">날</th><th>시가</th><th>종가</th><th>갭</th><th>등락률</th><th>시가→종가</th></tr></thead>
      <tbody>${tr}</tbody></table>
      <div class="st-cap">등락률 = 전 거래일 종가 대비 · 갭 = 만기일 종가 → 다음 날 시가 · 다음 날 등락률 = 만기일 종가 대비 · 오늘 봉은 장중이면 아직 안 끝난 값</div></div>
    <div><svg class="mx-g" role="img" aria-label="올해 코스피 종가와 만기일"></svg>
      <div class="st-cap">올해 코스피 종가 · 세로 줄 = 만기일(굵은 줄 = 세마녀) · 점 = 다음 거래일 종가(빨강 오름 · 파랑 내림 — 만기일 종가 대비)</div></div>`;
  graph();
}

if (box) {
  load();
  new ResizeObserver(() => graph()).observe(box);   // 폭이 바뀌면 그래프만 다시 그림(값은 다시 안 받음)
}
