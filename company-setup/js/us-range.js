// 오늘 밤 미국장 예상 범위 — S&P 500 (2026-10-26 재권님 「가능한 부분만 통계적으로 가면 될거같아」 → 「응 해봐」 · 시황분석1).
// 방향은 예측하지 않는다 — 하루 방향은 통계로 잘 안 맞고(뉴욕 연준 「개장 반전」 2021), 맞출 수 있는 것은 움직일 크기다.
//   하루 1표준편차 = 기준 종가 × VIX/100 ÷ √252   (VIX = 앞으로 30일 연율 흔들림 · 252 = 1년 거래일)
//   68% 범위 = 1배 · 95% 범위 = 1.96배 (정규분포 가정 — 실제 수익은 꼬리가 두꺼워 95% 밖이 더 자주 난다)
// 값은 서버 둘 — /api/kis/indices 의 S&P 500 · VIX(KIS · 홀딩스 지수 띠와 같은 값) · /api/market/us-outlook(선물 · 옵션 · 지표 · FOMC · VIX 1년).
// 2단계(2026-10-27 재권님 시안 → 「응 해줘」) — 옵션이 매긴 오늘 흔들림 · VIX 1년 위치 · 선물 기울기 · FOMC · 오늘 밤 지표.
// 못 받은 값은 「—」 이거나 그 줄을 뺀다(0 으로 메우지 않는다).
import { signClass, NUM } from '/assets/js/sign.js';

// 지표 이름 — 서버(나스닥 일정)가 영어로 준다. 여기 이름이 없는 지표는 화면에 안 낸다(화면 글은 한국어 · 2026-10-08 룰).
// 이 표를 쓰는 화면이 하나뿐이라 여기 둔다 — 둘째 화면이 생기면 서버 쪽 한 곳으로 옮긴다(「같은 값은 한 곳에만 둔다」).
const KO = {
  'CPI': '소비자물가(CPI)', 'Core CPI': '근원 소비자물가', 'CPI (MoM)': '소비자물가(전월비)', 'CPI (YoY)': '소비자물가(전년비)',
  'Core CPI (MoM)': '근원 소비자물가(전월비)', 'Core CPI (YoY)': '근원 소비자물가(전년비)',
  'PPI': '생산자물가(PPI)', 'Core PPI': '근원 생산자물가', 'PPI (MoM)': '생산자물가(전월비)', 'Core PPI (MoM)': '근원 생산자물가(전월비)',
  'Core PCE Price Index': '근원 PCE 물가', 'Core PCE Price Index (MoM)': '근원 PCE 물가(전월비)', 'Core PCE Price Index (YoY)': '근원 PCE 물가(전년비)',
  'PCE Price Index': 'PCE 물가', 'GDP': '국내총생산(GDP)', 'GDP (QoQ)': '국내총생산(전기비)',
  'Nonfarm Payrolls': '비농업 고용', 'Unemployment Rate': '실업률', 'Average Hourly Earnings (MoM)': '시간당 임금(전월비)',
  'Initial Jobless Claims': '신규 실업수당 청구', 'Continuing Jobless Claims': '계속 실업수당 청구',
  'ADP Nonfarm Employment Change': 'ADP 민간 고용', 'JOLTs Job Openings': '구인 건수(JOLTS)',
  'ISM Manufacturing PMI': 'ISM 제조업', 'ISM Non-Manufacturing PMI': 'ISM 서비스업', 'ISM Services PMI': 'ISM 서비스업',
  'S&P Global Manufacturing PMI': 'S&P 제조업 PMI', 'S&P Global Services PMI': 'S&P 서비스업 PMI',
  'Retail Sales (MoM)': '소매판매(전월비)', 'Core Retail Sales (MoM)': '근원 소매판매(전월비)',
  'Durable Goods Orders': '내구재 주문', 'Core Durable Goods Orders': '근원 내구재 주문',
  'Industrial Production (MoM)': '산업생산(전월비)', 'Housing Starts': '주택 착공', 'New Home Sales': '신규 주택 판매',
  'Existing Home Sales': '기존 주택 판매', 'Pending Home Sales (MoM)': '주택 매매 계약(전월비)', 'House Price Index': '주택가격지수',
  'CB Consumer Confidence': '소비자 신뢰지수(CB)', 'Michigan Consumer Sentiment': '미시간 소비자 심리',
  'Philadelphia Fed Manufacturing Index': '필라델피아 제조업 지수', 'NY Empire State Manufacturing Index': '뉴욕 제조업 지수',
  'Richmond Manufacturing Index': '리치먼드 제조업 지수', 'Goods Trade Balance': '상품 무역수지', 'Trade Balance': '무역수지',
  'Crude Oil Inventories': '원유 재고', 'Fed Interest Rate Decision': '미국 기준금리 결정',
};

(async () => {
  const box = document.getElementById('us-range');
  if (!box) return;
  const out = box.querySelector('[data-range]');
  const n = (x, d = 2) => (x == null || !isFinite(x) ? '—' : Number(x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const pct = x => { const c = signClass(x, NUM), t = x == null || !isFinite(x) ? '—' : `${x > 0 ? '+' : ''}${n(x)}%`; return c ? `<span class="${c}">${t}</span>` : t; };
  const day = s => (s && /^\d{8}$/.test(s) ? `${s.slice(4, 6)}-${s.slice(6)}` : '—');
  const get = async u => { try { return await (await fetch(u, { cache: 'no-store' })).json(); } catch (e) { return null; } };
  const [ix, uo] = await Promise.all([get('/api/kis/indices'), get('/api/market/us-outlook')]);
  const rows = (ix && ix.data) || [];
  const spx = rows.find(x => x.code === 'SPX'), vix = rows.find(x => x.code === 'VIX');
  const blk = k => (uo && uo[k] && uo[k].data) || null;
  const F = (blk('futures') || {}).rows || [], fut = s => (F.find(r => r.sym === s) || {}).pct;
  const O = blk('options'), V = blk('vix'), M = blk('fomc'), E = (blk('econ') || {}).rows || [];
  const r = (k, v) => `<div class="r"><span>${k}</span><span>${v}</span></div>`;
  const g = t => `<div class="g">${t}</div>`;
  const html = [g('통계로 잰 크기')];
  if (spx && vix && spx.value > 0 && vix.value > 0) {
    const sd = vix.value / 100 / Math.sqrt(252), pt = spx.value * sd;
    const band = k => `${n(spx.value - k * pt)} ~ ${n(spx.value + k * pt)}`;
    html.push(
      r('기준 종가', `<b>${n(spx.value)}</b> (${day(spx.asOf)})`),
      r('VIX', `<b>${n(vix.value)}</b>`),   // 날짜는 안 붙인다 — KIS 가 asOf 를 오늘 날짜로 주지만 값은 마지막 미국 종가다(10-26 실측 · Cboe 10-23 종가 19.45 와 같음)
      V ? r('VIX 지난 1년 중 위치', `<b>${n(V.pctile1y, 0)}%</b> · 1년 ${n(V.min1y)} ~ ${n(V.max1y)}`) : '',
      r('하루 흔들림(VIX 셈)', `<b>±${n(sd * 100)}%</b> · ±${n(pt, 1)}`),
      O ? r('하루 흔들림(옵션 시장)', `<b>±${n(O.expectedMovePct)}%</b> · ±${n(O.expectedMove, 1)} · 만기 ${O.expiry ? O.expiry.slice(5) : '—'}`) : '',
      r('68% 범위', `<b>${band(1)}</b>`),
      r('95% 범위', `<b>${band(1.96)}</b>`),
    );
  } else html.push(r('S&amp;P 500 · VIX 를 서버에서 못 받음', '<b>—</b>'));

  // 지금 기울기 — 선물 · FOMC(회의가 사흘 안일 때만)
  const lean = [];
  if (F.length) lean.push(r('S&amp;P · 나스닥 선물', `<b>${pct(fut('ES=F'))}</b> · <b>${pct(fut('NQ=F'))}</b>`));
  if (M && M.meeting) {
    const left = (new Date(M.meeting + 'T00:00:00-05:00') - Date.now()) / 864e5;
    if (left > -1 && left <= 3) {
      const hold = 100 - (M.cut25Prob || 0) - (M.hike25Prob || 0);
      lean.push(r(`FOMC ${M.meeting.slice(5)} (금리 결정)`, `인하 <b>${n(M.cut25Prob, 0)}%</b> · 동결 <b>${n(hold, 0)}%</b> · 인상 <b>${n(M.hike25Prob, 0)}%</b>`));
    }
  }
  if (lean.length) html.push(g('지금 기울기 — 방향 예측이 아님'), ...lean);

  // 오늘 밤 지표 — 서버는 미국 동부 날짜 · 시각을 준다. 한국 시각으로 바꿔 지금부터 20시간 안의 것만 · 예상치 있는 것만.
  const etToMs = (d, t) => {   // 미국 동부 벽시계 → 실제 시각. 서머타임(4시간) · 아닐 때(5시간) 중 그 시각이 맞는 쪽
    const [y, mo, dd] = d.split('-').map(Number), [h, mi] = t.split(':').map(Number);
    for (const off of [4, 5]) {
      const ms = Date.UTC(y, mo - 1, dd, h + off, mi);
      const hh = Number(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', hourCycle: 'h23' }).format(ms));
      if (hh === h) return ms;
    }
    return NaN;
  };
  const kst = ms => new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(ms);
  const now = Date.now(), seen = new Set();
  const ev = E.map(e => ({ ...e, ms: e.date && e.time ? etToMs(e.date, e.time) : NaN }))
    .filter(e => KO[e.name] && e.consensus && e.ms >= now - 36e5 && e.ms < now + 20 * 36e5)
    .filter(e => { const k = e.name + e.ms; if (seen.has(k)) return false; seen.add(k); return true; })   // 같은 지표가 단위만 달리 두 줄 오면 앞 것
    .sort((a, b) => a.ms - b.ms);
  if (ev.length) html.push(g('오늘 밤 지표 — 한국 시각 · 예상 / 지난'),
    ...ev.map(e => r(`${kst(e.ms)} ${KO[e.name]}`, `${e.actual ? `결과 <b>${e.actual}</b> · ` : ''}<b>${e.consensus}</b> / ${e.previous || '—'}`)));

  const at = uo && uo.futures && uo.futures.fetchedAt ? uo.futures.fetchedAt.slice(11, 16) : null;
  html.push(`<div class="src">S&amp;P 500 · VIX — KIS · 선물 야후(10분 늦음) · 옵션 Cboe(15분 늦음) · 지표 나스닥 · FOMC 연방기금 선물${at ? ` · ${at} 받음` : ' · 서버 값 못 받음'}</div>`);
  out.innerHTML = html.join('');
})();
