// 미국 → 다음 날 국내 섹터 · 테마 (11-25 재권님 「미국섹터와 테마를 국내와 동일하게」 → 표 → 「단타에 섹터 수급과 옵션 만기 사이로 이거 넣어주고 잘 동작하는지 체크해줘」)
//   값  서버 /api/kis/us-kr-groups?by=sector|theme&month=YYYYMM (개발2 · 날마다 쌓음 · 짝 표는 서버 us_kr_map.json) — days [{us, kr}] 최근 먼저 · rows [{name, pair, us{날:%}, kr{날:%}}] · meta.months
//       오늘 한국 칸은 진행 중이라 /api/kis/sector-flow?by= 의 지금 값으로 덮고 서버가 준 meta.refreshMs 마다 다시 받음(주기를 화면이 정하지 않음)
//   짝  미국 하루 → 그다음 한국 장날 · 오르내림 방향이 같으면 빨강 바탕 · 다르면 파랑 · 한쪽 값 없으면 바탕 없음
//   위  날마다 미국에서 가장 많이 오른 다섯(그 묶음 안) · 오늘 칸에서 미국 오름과 한국 오름이 맞으면 숫자가 깜박임
import { signClass, NUM } from '/assets/js/sign.js';   // 오르내림 글씨 색 — 셈은 sign.js 한 곳

const box = document.getElementById('uk');
const API = '/api/kis/us-kr-groups', LIVE_API = '/api/kis/sector-flow';
const TOP_N = 5;   // 위 칸에 보일 수(재권님 「가장 많이 오른 5개씩」)
const KINDS = [['sector', '섹터(업종)'], ['theme', '테마']];
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (v) => { if (v == null || !Number.isFinite(Number(v))) return '<span class="uk-na">—</span>'; const x = Number(v), c = signClass(x, NUM); const t = `${x > 0 ? '+' : ''}${x.toFixed(2)}`; return c ? `<span class="${c}">${t}</span>` : t; };
const WD = '일월화수목금토';
const md = (s) => { const d = new Date(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6)); return `${+s.slice(4, 6)}/${+s.slice(6)}(${WD[d.getDay()]})`; };
const hm = (t) => (t ? `${t.slice(0, 2)}:${t.slice(2, 4)}` : '');
const has = (v) => v != null && Number.isFinite(Number(v));
// 짝 색(11-25 재권님 — 둘 다 내린 날 빨강 바탕에 파랑 숫자였던 것을 고침 · 「짝이 안맞는 한국은 노란색」 → 「응」) — 같은 쪽은 방향 색(둘 다 오름 빨강 · 둘 다 내림 파랑) · 반대로 간 날은 한국 칸만 노랑
const pairCls = (a, b) => (has(a) && has(b) ? ((Number(a) > 0) === (Number(b) > 0) ? (Number(a) > 0 ? ' same up' : ' same dn') : ' diff') : '');
const usCls = (c) => c.replace(' diff', '');   // 미국 칸은 반대인 날 색 없음
async function getJson(u) { try { const r = await fetch(u, { cache: 'no-store' }); return { st: r.status, j: r.ok ? await r.json() : null }; } catch (e) { return { st: 0, j: null }; } }

const st = { kind: 'sector', month: '', data: {}, live: {}, liveAt: {}, timer: null, months: [] };
const today = () => { const t = new Date(); return `${t.getFullYear()}${String(t.getMonth() + 1).padStart(2, '0')}${String(t.getDate()).padStart(2, '0')}`; };

function pairTxt(p) {
  if (!p) return '미국 짝 없음';
  if (p.kind === 'etf') return `테마 ETF <b>${esc((p.tickers || [])[0])}</b> ${esc(p.label || '')}`;
  if (p.kind === 'gics') return `S&amp;P 500 <b>${esc(p.n ?? (p.tickers || []).length)}종목</b> · ${esc(p.label || '')}`;
  return `${(p.tickers || []).map((t) => `<b>${esc(t)}</b>`).join(' · ')} ${esc(p.label || '')}${p.weak ? ' <span class="uk-weak">짝 약함</span>' : ''}${p.why ? `<br>${esc(p.why)}` : ''}`;
}

function draw() {
  const D = st.data[`${st.kind}|${st.month}`];
  const body = box.querySelector('.uk-body');
  if (!D) { body.innerHTML = '<div class="st-err">받는 중…</div>'; return; }
  if (D.err) { body.innerHTML = `<div class="st-err">${esc(D.err)}</div>`; return; }
  const days = D.days || [], T = today(), L = st.live[st.kind] || {}, lat = st.liveAt[st.kind];
  const krOf = (r, d) => (d.kr === T && has(L[r.name]) ? L[r.name] : (r.kr || {})[d.kr]);
  const isLive = (d) => d.kr === T;
  const liveTag = `<span class="uk-lv">진행중${lat ? ` · ${hm(lat)} 값` : ''}</span>`;
  // 위 — 날마다 미국 상위 다섯
  const top = days.map((d) => D.rows.filter((r) => has((r.us || {})[d.us])).sort((a, b) => b.us[d.us] - a.us[d.us]).slice(0, TOP_N));
  let h = `<div class="uk-ttl">미국에서 가장 많이 오른 ${KINDS.find((k) => k[0] === st.kind)[1]} ${TOP_N} — 날별(최근 왼쪽) · 큰 숫자 = 미국 · 아래 = 다음 한국 장날</div><div class="uk-top"><table><tr><td></td>`
    + days.map((d) => `<td class="uk-dh${isLive(d) ? ' uk-now' : ''}">${md(d.us)} → ${md(d.kr)}${isLive(d) ? liveTag : ''}</td>`).join('') + '</tr>';
  for (let i = 0; i < TOP_N; i++) {
    h += `<tr><td class="uk-rk">${i + 1}</td>` + days.map((d, k) => { const r = top[k][i]; if (!r) return '<td></td>';
      const a = r.us[d.us], b = krOf(r, d), hit = isLive(d) && Number(a) > 0 && has(b) && Number(b) > 0;
      const pc = pairCls(a, b); return `<td class="${usCls(pc).trim()}${hit ? ' uk-hit' : ''}"><span class="uk-nm">${esc(r.name)}</span><span class="uk-us">${num(a)}</span><span class="uk-kr${pc.includes('diff') ? ' diff' : ''}"><i>${isLive(d) ? '한국 진행중' : '한국'}</i><span class="${isLive(d) ? 'uk-blink' : ''}">${num(b)}</span></span></td>`; }).join('') + '</tr>';
  }
  h += '</table></div>';
  // 아래 — 국내 묶음마다 두 줄(미국 · 한국) · 그 달 맞은 몫 높은 순
  const rs = D.rows.map((r) => { let hit = 0, tot = 0; days.forEach((d) => { const a = (r.us || {})[d.us], b = krOf(r, d); if (has(a) && has(b)) { tot++; if ((a > 0) === (b > 0)) hit++; } }); return { r, hit, tot, q: tot ? hit / tot : -1 }; })
    .sort((x, y) => y.q - x.q || y.tot - x.tot);
  h += `<div class="uk-box"><table><tr><th class="uk-k" rowspan="2">국내</th><th class="uk-pr" rowspan="2">미국 짝</th><th rowspan="2" class="uk-c">맞은 수</th><th class="uk-who">미국</th>`
    + days.map((d) => `<th class="${isLive(d) ? 'uk-now' : ''}">${md(d.us)}</th>`).join('') + `</tr><tr><th class="uk-who uk-h2">한국</th>`
    + days.map((d) => `<th class="uk-h2${isLive(d) ? ' uk-now' : ''}">${md(d.kr)}${isLive(d) ? liveTag : ''}</th>`).join('') + '</tr>';
  rs.forEach(({ r, hit, tot }) => {
    const us = [], kr = [];
    days.forEach((d) => { const a = (r.us || {})[d.us], b = krOf(r, d), c = pairCls(a, b) + (isLive(d) ? ' uk-now' : '');
      us.push(`<td class="uk-d${usCls(c)}">${num(a)}</td>`); kr.push(`<td class="uk-d${c}"><span class="${isLive(d) ? 'uk-blink' : ''}">${num(b)}</span></td>`); });
    h += `<tr class="uk-us-r"><td class="uk-k" rowspan="2">${esc(r.name)}</td><td class="uk-pr" rowspan="2">${pairTxt(r.pair)}</td><td class="uk-c" rowspan="2">${tot ? `<b>${hit}/${tot}</b><small>${Math.round(hit / tot * 100)}%</small>` : '<small>짝 없음</small>'}</td><td class="uk-who">미국</td>${us.join('')}</tr>`
      + `<tr class="uk-kr-r"><td class="uk-who">한국</td>${kr.join('')}</tr>`;
  });
  body.innerHTML = h + '</table></div>';
}

function bar() {
  box.querySelector('.uk-bar').innerHTML = `<span class="uk-bt">보기</span>${KINDS.map(([k, n]) => `<button type="button" class="kh-chip${st.kind === k ? ' is-active' : ''}" data-uk="${k}">${n}</button>`).join('')}`
    + `<span class="uk-bt">달</span>${st.months.map((m) => `<button type="button" class="kh-chip${st.month === m ? ' is-active' : ''}" data-ukm="${m}">${+m.slice(4)}월</button>`).join('')}`;
}

async function load() {
  const kind = st.kind, month = st.month, key = `${kind}|${month}`;   // 물은 때의 보기 · 달로 담음 — 받는 사이에 단추를 또 눌러도 다른 칸에 안 섞임
  if (!st.data[key]) {
    draw();
    const { st: code, j } = await getJson(`${API}?by=${kind}${month ? `&month=${month}` : ''}`);
    if (!j || !j.ok) { st.data[key] = { err: code === 404 ? '서버 값이 아직 없음 — 미국 섹터 · 테마 날마다 쌓기 준비 중' : `못 받음(${code || '연결 안 됨'})` }; }
    else {
      const d = j.data || {}, m = j.meta || {};
      if (m.months) st.months = m.months;
      const got = { days: d.days || [], rows: d.rows || [] };
      st.data[key] = got;
      if (!month) { const mk = st.months[0] || ''; st.data[`${kind}|${mk}`] = got; if (!st.month) st.month = mk; }   // 달 없이 물으면 서버가 준 맨 앞 달
      if (m.refreshMs) st.refreshMs = m.refreshMs;
    }
  }
  bar(); draw();
}

// 오늘 한국 칸 — 섹터수급 지금 값(묶음 pct 의 마지막 칸) · 서버 meta.refreshMs 마다
async function live() {
  clearTimeout(st.timer);
  let ms = st.refreshMs || null;
  for (const [k] of KINDS) {
    const { j } = await getJson(`${LIVE_API}?by=${k}`);
    if (!j || !j.ok || !j.data || j.data.day !== today()) continue;
    const v = {}; let last = '';
    (j.data.rows || []).forEach((r) => { const p = r.pct || {}, ks = Object.keys(p).filter((x) => has(p[x])).sort(); if (ks.length) { v[r.name] = p[ks[ks.length - 1]]; if (ks[ks.length - 1] > last) last = ks[ks.length - 1]; } });
    st.live[k] = v; st.liveAt[k] = last; if (j.meta && j.meta.refreshMs) ms = j.meta.refreshMs;
  }
  draw();
  if (ms) st.timer = setTimeout(live, ms);   // 주기는 서버가 준 값만 — 없으면 다시 안 받음
}

if (box) {
  box.addEventListener('click', (e) => {
    const k = e.target.closest('[data-uk]'), m = e.target.closest('[data-ukm]');
    if (k) { st.kind = k.dataset.uk; load(); }
    if (m) { st.month = m.dataset.ukm; load(); }
  });
  load().then(live);
}
