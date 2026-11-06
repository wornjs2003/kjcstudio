/* 공포·탐욕 지수 — 큰 차트 위 단추 · 누르면 모달 (2026-11-06)
 *
 * 재권님 「이걸 차트에 위쪽에 버튼을 만들고 누르면 보여지게 해줘」 · 「공포지수 25에 세로선을 넣어주고 25 아래에서 25를 통과할 때
 * 내가 알 수 있게 · 코스피 삼전 닉스 이렇게만」 → 「1차로 만들어」.
 *
 * 값과 셈은 서버 하나다 — GET /api/market/fear-greed?key=KOSPI|005930|000660 (server/fear_greed.py). 화면은 받은 대로 그린다.
 * 단추는 코스피 점수 · 모달은 셋을 탭으로 갈아 끼운다(칸 높이는 CSS 가 잡는다 — 「보는 것을 바꿔도 자리는 그대로다」).
 * 25 풀림 알림은 서버가 마감 뒤 본다 — 지금은 꺼짐(server/fear_greed.py SEND). 화면은 풀림 날을 그래프에 점으로 보인다.
 * 다시 묻는 주기를 두지 않는다 — 열 때 한 번 받는다(서버가 CACHE_SEC 동안 들고 있다).
 */
import { openModal } from './modal.js';
import { apiFetch } from '../data/api.js';
import { signClass, KH } from '/assets/js/sign.js';
import { tone as toneOf, paint, ready as toneReady } from '/assets/js/tone.js';

const URL = '/api/market/fear-greed';
const TABS = [['KOSPI', '코스피'], ['005930', '삼성전자'], ['000660', 'SK하이닉스']];
const ZN = ['극도의 공포', '공포', '중립', '탐욕', '극도의 탐욕'];

const md = d => d ? d.slice(4, 6) + '-' + d.slice(6) : '—';
/* 점수의 위 · 아래와 막대 짙기는 지표 표(data/metrics.json · fear_greed)의 기준 · 폭으로 tone.js 가 셈한다 — 화면은 기준을 들지 않는다
   (「기준이 있는 수치는 위 빨강 · 아래 파랑, 멀수록 짙게 — 셈은 한 곳」 · 개념정의 검수 11-06) */
const METRIC = 'fear_greed';
const tone = s => { const t = toneOf(METRIC, s).side; return t ? KH[t] : KH.none; };
const STOPS = [0, 10, 25, 40, 50, 60, 75, 90, 100];
const gaugeBg = () => 'linear-gradient(90deg, ' + STOPS.map(v => `${paint(METRIC, v, 'bg') || 'var(--kh-bg-surface)'} ${v}%`).join(', ') + ')';
const delta = v => v == null ? '<b class="kh-mut">—</b>'
  : `<b class="${signClass(v)}">${v > 0 ? '▲' : v < 0 ? '▼' : ''}${Math.abs(v)}</b>`;
const pct = (v, n = 1) => v == null ? '—' : (v * 100).toFixed(n) + '%';
const jo = v => v == null ? '—' : (v / 1e6).toFixed(1) + '조 원';      // 서버 값 단위 백만원

async function load(key) {
  const r = await apiFetch(`${URL}?key=${encodeURIComponent(key)}`);
  const j = await r.json();
  return j;
}

/* 지금 자리 원 옆 화살표 — 5일 전보다 내려왔으면 원 왼쪽 ◀(파랑) · 올라왔으면 오른쪽 ▶(빨강) · 같으면 없음
   (재권님 「내려가는 추세면 원 왼쪽에 화살표 · 올라가는 추세면 원 오른쪽에」 11-06) */
function trend(v) {
  if (!v) return '';
  /* 글자(◀ ▶)는 글꼴에 따라 비스듬히 찌그러져 보여 도형으로 그린다(재권님 「화살표 찌그러져 보이는데」 11-06) */
  const pts = v < 0 ? '10,0 10,12 0,6' : '0,0 0,12 10,6';
  return `<b class="fg-ar ${v < 0 ? 'fg-ar-l' : 'fg-ar-r'} ${signClass(v)}"><svg viewBox="0 0 10 12" width="10" height="12"><polygon points="${pts}" fill="currentColor"/></svg></b>`;
}

function rows(d) {
  const P = d.parts || {}, R = d.raw || {}, mk = d.kind === 'market';
  return [
    ['모멘텀', P.mom, `${mk ? '코스피' : '주가'} 125일선 대비 ${pct(R.mom)}`],
    ['주가 강도', P.hl, mk ? (R.hl == null ? '52주 신고가 − 신저가 — 그날 종목 일봉이 다 쌓이면 셈' : `52주 신고가 − 신저가 = 잰 ${d.hlN}종목의 ${pct(R.hl)}`)
                         : `52주 최저~최고 사이 ${pct(R.hl, 0)} 자리`],
    [mk ? '시장 폭' : '오른 날 비중', P.breadth, mk ? (R.breadth == null ? '20일 오른 종목의 거래대금 비중 — 그날 종목 일봉이 다 쌓이면 셈' : `20일 오른 종목의 거래대금 비중 ${pct(R.breadth)}`)
                                             : `20일 중 오른 날의 거래대금 비중 ${pct(R.breadth)}`],
    ['변동성', P.vol, d.volRatio == null ? '20일 변동성 —' : `20일 변동성 = 1년 평균의 ${d.volRatio.toFixed(2)}배`],
    ['외국인 수급', P.frn, R.frn == null ? '외국인 20일 누적 — 오늘 것이 아직 안 쌓임' : `외국인 20일 누적 ${jo(R.frn)}`],
    ['투자심리선', P.psy, `10일 중 오른 날 ${R.psy == null ? '—' : Math.round(R.psy * 10) + '일'}`],
    ['미국 VIX', P.vix, R.vix == null ? '간밤 VIX —' : `간밤 VIX = 50일 평균의 ${R.vix.toFixed(2)}배`],
  ];
}

function chart(d, line) {
  const h = d.hist || [], n = h.length;
  if (n < 2) return '<div class="kh-mut">그래프 값이 없습니다</div>';
  const W = 460, H = 120, x = i => i / (n - 1) * W, y = v => H - v / 100 * H;
  let path = '', pen = false;
  h.forEach((p, i) => { if (p[1] == null) { pen = false; return; } path += (pen ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(p[1]).toFixed(1) + ' '; pen = true; });
  const at = Object.fromEntries(h.map((p, i) => [p[0], i]));
  const dots = (d.crossings || []).filter(c => c.day in at).map(c => {
    const i = at[c.day], v = h[i][1];
    return c.kind === 'first'
      ? `<circle cx="${x(i)}" cy="${y(v)}" r="3.5" class="fg-first"/><text x="${x(i)}" y="${y(v) - 7}" class="fg-lbl" text-anchor="middle">${md(c.day)}</text>`
      : `<circle cx="${x(i)}" cy="${y(v)}" r="3" class="fg-again"/>`;
  }).join('');
  return `<svg class="fg-svg" viewBox="0 -14 ${W} ${H + 30}" preserveAspectRatio="none">
    <rect x="0" y="${y(line)}" width="${W}" height="${H - y(line)}" class="fg-fear"/>
    <line x1="0" x2="${W}" y1="${y(line)}" y2="${y(line)}" class="fg-l25"/>
    <path d="${path}" class="fg-path"/>${dots}
    <text x="0" y="${H + 14}" class="fg-ax">${md(h[0][0])}</text>
    <text x="${W}" y="${H + 14}" class="fg-ax" text-anchor="end">${md(h[n - 1][0])}</text>
    <text x="${W - 2}" y="${y(line) - 3}" class="fg-ax" text-anchor="end">${line}</text></svg>`;
}

function render(box, j) {
  const d = j && j.data;
  if (!d || !d.ready) { box.innerHTML = `<div class="fg-empty">불러오지 못함 — ${(d && d.why) || (j && j.error) || '서버 응답 없음'}</div>`; return; }
  const line = j.line, z = ZN.indexOf(d.zone);
  const lf = d.lastFirst ? `마지막 풀림 첫날 ${md(d.lastFirst)}` : '지난 120거래일에 풀림 없음';
  const runBox = d.below > 0
    ? `<b>${line} 아래 ${d.below}일째</b> — ${lf}. ${line} 위로 올라서는 날 그래프에 빨간 점이 찍힙니다.`
    : `<b>${line} 위</b> — ${lf}.`;
  box.innerHTML = `
    <div class="fg-top"><span class="kh-mut">${d.live ? '오늘 장중(마감 전)' : md(d.day) + ' 장 마감'} 기준 · 0~100 낮을수록 공포</span></div>
    <div class="fg-big"><b class="${tone(d.score)}">${d.score}</b><span class="${tone(d.score)}">${d.zone}</span></div>
    <div class="fg-gauge" style="background:${gaugeBg()}"><i class="fg-25" style="left:${line}%"><em>${line}</em></i><i class="fg-now" style="left:${d.score}%">${trend(d.d5)}</i></div>
    <div class="fg-zones">${ZN.map((t, i) => `<span class="${i === z ? 'on' : ''}">${t}</span>`).join('')}</div>
    <div class="fg-chg">5일 전 대비 ${delta(d.d5)} · 20일 전 대비 ${delta(d.d20)}</div>
    <div class="fg-box">${runBox}</div>
    <h4>최근 120거래일 <span class="kh-mut">장 마감 값 · ● 풀림 첫날 · ○ 다시 넘음(첫날 뒤 ${j.regroup}거래일 안)</span></h4>
    ${chart(d, line)}
    <h4>요소 일곱 <span class="kh-mut">각 0~100 · 같은 무게 · 못 잰 요소는 빼고 평균</span></h4>
    ${rows(d).map(r => `<div class="fg-f"><span class="nm">${r[0]}</span><div class="bar">${r[1] == null ? '' : `<i style="left:${r[1]}%"></i>`}</div><span class="sc">${r[1] ?? '—'}</span><span class="ds">${r[2]}</span></div>`).join('')}
    <div class="fg-note kh-mut">${line} 풀림 알림(텔레그램)은 만들어 두고 꺼 둔 상태입니다. ${d.kind === 'stock' ? '종목판은 시장에만 있는 두 요소를 그 종목 것(52주 자리 · 오른 날 비중)으로 바꿔 셉니다. ' : ''}바닥을 알려 주는 지표가 아니라 심리가 어느 쪽에 쏠렸는지 보는 도구입니다.</div>`;
}

function open(first) {
  const m = openModal({ label: '공포·탐욕 지수', width: 560, fade: false,
    head: { name: '공포·탐욕 지수', sub: '코스피 · 삼성전자 · SK하이닉스 — 요소 일곱' } });
  m.body.innerHTML = `<div class="fg-wrap"><div class="fg-tabs">${TABS.map(([k, n]) => `<button type="button" data-k="${k}">${n}</button>`).join('')}</div><div class="fg-body"></div></div>`;
  const box = m.body.querySelector('.fg-body');
  let want = null;
  const show = async key => {
    want = key;
    m.body.querySelectorAll('.fg-tabs button').forEach(b => b.classList.toggle('is-on', b.dataset.k === key));
    box.innerHTML = '<div class="fg-empty">불러오는 중</div>';
    try {
      const j = key === 'KOSPI' && first ? first : await load(key);
      first = null;
      if (want === key) render(box, j);
    } catch (e) {
      if (want === key) box.innerHTML = '<div class="fg-empty">불러오지 못함</div>';
    }
  };
  m.body.querySelector('.fg-tabs').addEventListener('click', e => { const b = e.target.closest('button'); if (b) show(b.dataset.k); });
  show('KOSPI');
}

export function mountFearGreed(btn) {
  if (!btn) return;
  let last = null;
  const b = btn.querySelector('b');
  Promise.all([load('KOSPI'), toneReady]).then(([j]) => {
    last = j;
    const s = j && j.data && j.data.ready ? j.data.score : null;
    b.textContent = s == null ? '—' : s;
    b.className = tone(s);
    if (new URLSearchParams(location.search).get('fg') === '1') open(last);     // 주소로 바로 열기(?fg=1) — 링크로 보여 드릴 때
  }).catch(() => { b.textContent = '—'; });
  btn.addEventListener('click', () => open(last));
}
