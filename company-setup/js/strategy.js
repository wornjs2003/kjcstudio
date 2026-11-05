// 투자 전략 — 장외 → 다음 날 아침 표 (2026-10-26 재권님 지시 · 시안 temp/넥장시안3.png → 「응 세로로 2배 늘려서 진행해줘」).
// 값은 열 때 홀딩스 서버에서 받는다(「두 구역이 같은 값을 쓰면」) — /api/nxt/board?market=kospi|kosdaq&days=N (주식 레인 · 개발1 이 만드는 중).
//   · 세로 — 종목. 그날그날 장외에서 많이 오른 · 내린 20종목(「세로 2배」 = 시안 10 → 20)을 합친 것. 오름 무리 · 내림 무리로 나눈다
//   · 가로 — 날마다 한 묶음: 정규장 종가 · 장외 마지막(20:00) · 야간선물(시장 하나 — 맨 윗줄에만) · 다음 날 프리장(08:50). 오래된 날이 왼쪽 · 새 날이 오른쪽에 붙는다
//   · 장외 · 프리장 · 야간선물은 % 로 — 장외 · 프리장은 정규장 종가 대비, 야간선물은 서버가 준 전일비
//   · 없는 값은 null 로 오고 「—」 로 낸다(0 이 아니다 · 「못 쟀으면 0 이 아니라 못 쟀다」)
// 서버 응답 모양(개발1 · 2026-10-26 17:4x 알림): data.days[{day:YYYYMMDD, preDay, fut{kospi200|kosdaq150: {name, last, pct}|null}}](최신이 앞) ·
//   rows[{code, name, side:up|down, rank, cells{<day>:{close, after, afterPct, pre, prePct}}}] — rank 는 그 종목이 든 가장 최근 날 것 · 없음은 null
import { signClass, NUM } from '../../assets/js/sign.js';

const DAYS = 20;   // 몇 날을 받나 — 가로로 이만큼 쌓아 보이고 그보다 오래된 것은 서버에 남는다
const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const KDAY = '일월화수목금토';
const ymd = s => (s && /^\d{8}$/.test(s) ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6)}` : s);
const dlabel = v => { const s = ymd(v); if (!s) return '—'; const x = new Date(s + 'T00:00:00Z'); return `${s.slice(5)}(${KDAY[x.getUTCDay()]})`; };
const won = n => (n == null ? '—' : Number(n).toLocaleString('ko-KR'));
const pct = n => (n == null ? '—' : `<span class="${signClass(n, NUM)}">${n > 0 ? '+' : ''}${Number(n).toFixed(2)}%</span>`);
const SUB = ['종가', '장외', '야간선물', '프리장'];
const FUT = { kospi: 'kospi200', kosdaq: 'kosdaq150' };   // 시장 → 그 시장 야간선물 열쇠
const both = (v, p) => (v == null && p == null ? '—' : `${won(v)} ${pct(p)}`);   // 값 · % 가 다 없으면 「—」 하나

const box = document.getElementById('st-box'), meta = document.getElementById('st-meta');
let market = 'kospi';

async function load() {
  box.innerHTML = '—';
  let J = null, status = 0;
  try { const r = await fetch(`/api/nxt/board?market=${market}&days=${DAYS}`, { cache: 'no-store' }); status = r.status; J = r.ok ? await r.json() : null; } catch (e) { J = null; }
  const d = J && (J.data || J);
  if (!d || !Array.isArray(d.days)) {
    box.innerHTML = `<span class="st-err">서버가 아직 이 값을 내주지 않습니다(/api/nxt/board · ${status || '연결 안 됨'}) — 주식 레인이 만드는 중 · 켠 다음 날부터 쌓입니다</span>`;
    meta.textContent = '값 — 못 받음';
    return;
  }
  const days = d.days.slice().sort((a, b) => String(a.day).localeCompare(String(b.day)));   // 오래된 날 → 새 날
  if (!days.length) { box.innerHTML = '<span class="st-err">아직 쌓인 날이 없습니다 — 서버가 켜진 다음 날부터 하루 한 묶음씩 붙습니다</span>'; meta.textContent = '값 — 쌓인 날 없음'; return; }
  const rows = d.rows || [];
  const rank = r => r.rank || 999;
  const group = s => rows.filter(r => r.side === s).sort((a, b) => rank(a) - rank(b));
  const head = `<tr><th rowspan="2" class="st-name">종목</th>${days.map(x => `<th colspan="4" class="st-day">${dlabel(x.day)} 종가 → ${dlabel(x.preDay)} 프리장</th>`).join('')}</tr>
    <tr>${days.map(() => SUB.map((s, i) => `<th class="${i ? '' : 'st-first'}">${s}</th>`).join('')).join('')}</tr>`;
  const futOf = x => (x.fut && x.fut[FUT[market]]) || {};
  const fut = days.map(futOf).find(f => f.name) || {};
  const futRow = `<tr class="st-fut"><td class="st-name">${esc(fut.name || (market === 'kospi' ? '코스피200 야간선물' : '코스닥150 야간선물'))}</td>${days.map(x => { const f = futOf(x);
    return `<td class="st-first"></td><td></td><td>${f.last == null && f.pct == null ? '—' : `${f.last == null ? '—' : esc(f.last)} ${pct(f.pct)}`}</td><td></td>`; }).join('')}</tr>`;
  const line = r => `<tr><td class="st-name">${esc(r.name)} <small>${esc(r.code)}</small></td>${days.map(x => { const c = (r.cells || {})[x.day] || {};
    return `<td class="st-first">${won(c.close)}</td><td>${both(c.after, c.afterPct)}</td><td class="st-dot">·</td><td>${both(c.pre, c.prePct)}</td>`; }).join('')}</tr>`;
  const sep = t => `<tr class="st-grp"><td class="st-name">${t}</td><td colspan="${days.length * 4}"></td></tr>`;
  box.innerHTML = `<div class="st-scroll"><table>${head}${futRow}${sep('장외 오름')}${group('up').map(line).join('')}${sep('장외 내림')}${group('down').map(line).join('')}</table></div>`;
  const sc = box.querySelector('.st-scroll'); sc.scrollLeft = sc.scrollWidth;   // 새 날(오른쪽)이 먼저 보이게
  meta.textContent = `서버 /api/nxt/board · ${days.length}날(${dlabel(days[0].day)} ~ ${dlabel(days[days.length - 1].day)}) · 종목 ${rows.length}`;
}

document.getElementById('st-tg').addEventListener('click', e => {
  const b = e.target.closest('button[data-market]'); if (!b || b.dataset.market === market) return;
  market = b.dataset.market;
  document.querySelectorAll('#st-tg button').forEach(x => x.classList.toggle('is-active', x === b));
  load();
});
load();
