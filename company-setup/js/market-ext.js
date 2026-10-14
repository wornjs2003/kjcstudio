import { live } from './live.js';   // 새 값(-live) 먼저 · 없으면 씨앗
// 시황분석 탭 「대외변수」 층 — 전쟁 · 정치 · 무역 같은 외부 요인을 숫자로 센 지수(2026-10-12 재권님 「대외변수에 들어갈만한것들 찾아보라」 → 「응 해줘」).
// 값 data/external-risk.json(tools/fetch-external-risk.py · 매일 아침 launchd 가 -live 로) · 사건 data/external-events.json(세션이 손으로 적음).
// market.js 와 따로 둔 까닭 — 같은 화면을 다른 세션이 고치는 일이 잦아 섞이지 않게. 층 접기는 market.js 의 folds() 가 맡고, 펼칠 때 여기 그래프만 다시 잰다
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const grid = { color: css('--kh-chart-grid') };
const mine = [];
const legend = { legend: { display: true, position: 'bottom', labels: { boxWidth: 12, boxHeight: 2, font: { size: 10 } } } };
const opt = (y, more = {}) => ({ maintainAspectRatio: false, animation: false, interaction: { mode: 'index', intersect: false }, plugins: legend,
  scales: { x: { type: 'category', grid, ticks: { maxTicksLimit: 7 } }, y: { grid, title: { display: true, text: y } }, ...more } });
const ds = (label, pts, col, more = {}) => ({ label, data: pts.map(([x, y]) => ({ x, y })), borderColor: col, backgroundColor: col, borderWidth: 1.6, pointRadius: 0, spanGaps: true, ...more });
const ref = (labels, y, text) => ({ label: text, data: labels.map(x => ({ x, y })), borderColor: css('--text-muted'), borderDash: [4, 4], borderWidth: 1, pointRadius: 0 });
const add = (id, cfg) => { const el = document.getElementById(id); if (el) mine.push(new Chart(el, cfg)); };
const last = s => s && s.length ? s[s.length - 1] : null;
// 한 달 전 = 날짜로 30일 전에 가장 가까운 앞 값 — 지수마다 주기(매일 · 거래일)가 달라 칸 수로 세지 않는다(qa 지적 · 주간 값에서 틀린 셈이 났다)
const monthAgo = s => { if (!s || !s.length) return null; const t = new Date(new Date(s[s.length - 1][0]).getTime() - 30 * 864e5).toISOString().slice(0, 10); let r = null; for (const p of s) { if (p[0] <= t) r = p; else break; } return r; };
(async () => {
  const sum = document.getElementById('sum-ext');
  let R, E;
  try { [R, E] = await Promise.all([live('external-risk'), fetch('data/external-events.json', { cache: 'no-store' }).then(r => r.json()).catch(() => ({ events: [] }))]); }
  catch (e) { if (sum) sum.innerHTML = '<span class="err">대외변수 값을 받지 못했습니다 — company-setup/tools/fetch-external-risk.py 를 돌리면 생긴다</span>'; return; }
  document.getElementById('meta-ext').textContent = `${R.fetchedAt} 받음 · ${R.src}` + (Object.keys(R.errors || {}).length ? ` · 못 받은 것 ${Object.keys(R.errors).join(', ')}` : '');
  const blue = css('--accent'), red = css('--kh-up'), amber = css('--kh-cat-amber'), slate = css('--kh-cat-slate'), violet = css('--kh-cat-violet');
  // 지정학 위험 — 세계 매일 · 30일 평균
  const g = R.gpr || [], gl = g.map(p => p[0]);
  if (g.length) add('c-gpr', { type: 'line', data: { labels: gl, datasets: [ds('매일', g.map(p => [p[0], p[1]]), css('--kh-cat-slate-dim'), { borderWidth: 1 }), ds('30일 평균', g.map(p => [p[0], p[2]]), red, { borderWidth: 2.2 }), ref(gl, 100, '평소(1985~2019 평균 = 100)')] }, options: opt('지수') });
  // 한국 — 달마다 · 기사 중 비율
  const m = R.gprMonthly || [], ml = m.map(p => p[0]);
  const kv = m.map(p => p[2]).filter(v => v != null && Number.isFinite(v)), kAvg = kv.length ? kv.reduce((a, v) => a + v, 0) / kv.length : null;   // 빈 달은 빼고 센다 — 0 으로 더하지 않는다
  if (kv.length) add('c-gpr-kr', { type: 'line', data: { labels: ml, datasets: [ds('한국 관련 지정학 위험 기사 비율(%)', m.map(p => [p[0], p[2]]), red, { borderWidth: 2.2 }), ref(ml, +kAvg.toFixed(2), `2020년부터 평균 ${kAvg.toFixed(2)}%`)] }, options: opt('기사 중 %') });
  // 정책 · 무역 불확실성 — 30일 평균
  const ep = R.epu || [], tp = R.tpu || [];
  const dl = [...new Set([...ep.map(p => p[0]), ...tp.map(p => p[0])])].sort();
  const at = (ser, i) => { const mm = new Map(ser.map(p => [p[0], p[i]])); let lv = null; return dl.map(d => [d, mm.has(d) ? (lv = mm.get(d)) : lv]); };
  if (dl.length) add('c-unc', { type: 'line', data: { labels: dl, datasets: [ds('정책 불확실성(미국 · 30일 평균)', at(ep, 2), blue), ds('무역정책 불확실성(30일 평균)', at(tp, 2), amber), ref(dl, 100, '평소 = 100')] }, options: opt('지수') });
  // 공포 지수
  const vx = R.vix || [], ov = R.ovx || [], fl = [...new Set([...vx.map(p => p[0]), ...ov.map(p => p[0])])].sort();
  const at2 = ser => { const mm = new Map(ser); let lv = null; return fl.map(d => [d, mm.has(d) ? (lv = mm.get(d)) : lv]); };
  if (fl.length) add('c-fear', { type: 'line', data: { labels: fl, datasets: [ds('VIX(미국 주가)', at2(vx), violet, { yAxisID: 'y' }), ds('OVX(원유 · 오른쪽)', at2(ov), slate, { yAxisID: 'y2', borderDash: [4, 3] })] },
    options: opt('VIX', { y2: { position: 'right', grid: { display: false }, title: { display: true, text: 'OVX' } } }) });
  // 급한 대외 사건 — 세션이 적은 것 + 지난 RECENT_DAYS 일의 튄 날 중 안 적은 날(「—」 · 2026-10-14 재권님 「응 해줘」)
  // 튄 날 = external-risk.json 의 spikes(받는 도구가 지수마다 지난 1년 위 5% 로 매번 다시 센다) · 화면은 경계를 안 들고 그 값만 읽는다
  // 지정학 위험 파일의 큰 사건 날(gprEvents)은 영어 원문이고 2022년이 마지막이라 화면에 안 낸다 — 세션이 한국어로 적은 것만
  const RECENT_DAYS = 30, COVER_DAYS = 3;   // 보여 줄 튄 날의 폭 · 적은 사건이 그 앞 며칠의 튄 날까지 덮나(지수는 기사가 나온 다음 날 튀기도 한다)
  const SP = R.spikes || null, names = (SP && SP.names) || {};
  const day = s => new Date(s + 'T00:00:00Z').getTime();
  const ev = (E.events || []).map(x => ({ d: x.date, t: x.what, c: x.cause, s: x.src })).sort((a, b) => b.d.localeCompare(a.d));
  const lastDay = [g, ep, tp, vx, ov].map(s => last(s)).filter(Boolean).map(p => p[0]).sort().pop();
  const from = lastDay ? new Date(day(lastDay) - RECENT_DAYS * 864e5).toISOString().slice(0, 10) : null;
  const covered = d => ev.some(x => day(d) - day(x.d) >= -COVER_DAYS * 864e5 && day(d) - day(x.d) <= COVER_DAYS * 864e5);
  const sp = SP && from ? SP.days.filter(x => x[0] >= from) : [];
  const spBy = new Map(); sp.forEach(x => { if (!spBy.has(x[0])) spBy.set(x[0], []); spBy.get(x[0]).push(x); });
  const spTxt = xs => xs.map(x => `${esc(names[x[1]] || x[1])} ${x[3]}배`).join(' · ');
  const rows = [
    ...ev.map(x => ({ d: x.d, h: `${x.c ? `<b>${esc(x.c)}</b> — ` : ''}${esc(x.t)}${x.s ? ` <a href="${esc(x.s)}" target="_blank" rel="noopener">기사</a>` : ''}` })),
    ...[...spBy].filter(([d]) => !covered(d)).map(([d, xs]) => ({ d, h: `<b>—</b> 안 적음 · 튄 지수 ${spTxt(xs)}(앞 20일 평균 대비)` })),
  ].sort((a, b) => b.d.localeCompare(a.d));
  const box = document.getElementById('ext-events');
  const cuts = SP ? Object.entries(SP.cut || {}).map(([k, c]) => `${esc(names[k] || k)} ${c == null ? '못 쟀음' : c + '배'}`).join(' · ') : null;
  box.innerHTML = `<div class="cap">${cuts ? `튄 날 경계(지난 1년 위 5% · 받을 때마다 다시 셈): ${cuts} · 지난 ${RECENT_DAYS}일 튄 날 ${spBy.size}일 중 안 적은 날 ${[...spBy.keys()].filter(d => !covered(d)).length}일` : '튄 날 값이 아직 없다 — 받는 도구가 다음에 돌면 생긴다'}</div>`;
  box.innerHTML += rows.length ? rows.map(x => `<div class="r"><span>${esc(x.d)}</span><span class="why">${x.h}</span></div>`).join('') : '<div class="cap">적은 사건도 안 적은 튄 날도 없다</div>';
  // 층 제목 아래 요약
  const lg = last(g), lg30 = monthAgo(g), lm = last(m), le = last(ep), lt = last(tp), lv = last(vx), lo = last(ov), lv21 = monthAgo(vx);
  const line = (h, t) => `<span class="sl"><b>${h}</b> ${t}</span>`;
  const vs = v => v == null ? '—' : `평소의 ${(v / 100).toFixed(1)}배`;
  if (sum) sum.innerHTML = [
    line('지정학 위험', lg ? `세계 30일 평균 ${lg[2]}(${vs(lg[2])}) · 한 달 전 ${lg30 ? lg30[2] : '—'} · 한국 관련 기사 ${lm ? lm[2] + '%' : '—'}(${lm ? lm[0] : ''} · 2020년부터 평균 ${kAvg == null ? '—' : kAvg.toFixed(2) + '%'})` : '—'),
    line('불확실성', `정책(미국) 30일 평균 ${le ? le[2] : '—'}(${vs(le && le[2])}) · 무역 ${lt ? lt[2] : '—'}(${vs(lt && lt[2])})`),
    line('공포 지수', `VIX ${lv ? lv[1] : '—'}(한 달 전 ${lv21 ? lv21[1] : '—'}) · OVX ${lo ? lo[1] : '—'}`),
  ].join('');
  // 펼칠 때 여기 그래프만 다시 잰다 — 접힌 채 그려 폭이 0 이라서
  const d = document.querySelector('details[data-fold="ext"]');
  if (d) d.addEventListener('toggle', () => { if (d.open) mine.forEach(ch => ch.resize()); });
})();
