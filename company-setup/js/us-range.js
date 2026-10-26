// 오늘 밤 미국장 예상 범위 — S&P 500 (2026-10-26 재권님 「가능한 부분만 통계적으로 가면 될거같아」 → 「응 해봐」 · 시황분석1).
// 방향은 예측하지 않는다 — 하루 방향은 통계로 잘 안 맞고(뉴욕 연준 「개장 반전」 2021), 맞출 수 있는 것은 움직일 크기다.
//   하루 1표준편차 = 기준 종가 × VIX/100 ÷ √252   (VIX = 앞으로 30일 연율 흔들림 · 252 = 1년 거래일)
//   68% 범위 = 1배 · 95% 범위 = 1.96배 (정규분포 가정 — 실제 수익은 꼬리가 두꺼워 95% 밖이 더 자주 난다)
// 값은 서버 /api/kis/indices 의 S&P 500 · VIX(KIS) 하나 — 홀딩스 지수 띠와 같은 값. 못 받으면 「—」(0 으로 메우지 않는다).
// 옵션이 매긴 오늘 범위(스트래들) · 지수 선물 · 지표 예상치는 서버에 오면 이 칸에 더한다 — 지금은 없다(temp/시황분석1-미장예측.html)
(async () => {
  const box = document.getElementById('us-range');
  if (!box) return;
  const out = box.querySelector('[data-range]');
  const n = (x, d = 2) => Number(x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d });
  const day = s => (s && /^\d{8}$/.test(s) ? `${s.slice(4, 6)}-${s.slice(6)}` : '—');
  let rows = [];
  try { rows = ((await (await fetch('/api/kis/indices', { cache: 'no-store' })).json()).data) || []; } catch (e) { rows = []; }
  const spx = rows.find(x => x.code === 'SPX'), vix = rows.find(x => x.code === 'VIX');
  if (!spx || !vix || !(spx.value > 0) || !(vix.value > 0)) { out.innerHTML = '<div class="r"><span>S&amp;P 500 · VIX 를 서버에서 못 받음</span><b>—</b></div>'; return; }
  const sd = vix.value / 100 / Math.sqrt(252);            // 하루 1표준편차(비율)
  const pt = spx.value * sd;
  const band = k => `${n(spx.value - k * pt)} ~ ${n(spx.value + k * pt)}`;
  out.innerHTML = [
    ['기준 종가', `<b>${n(spx.value)}</b> (${day(spx.asOf)})`],
    ['VIX', `<b>${n(vix.value)}</b>`],   // 날짜는 안 붙인다 — KIS 가 asOf 를 오늘 날짜로 주지만 값은 마지막 미국 종가다(10-26 실측 · Cboe 10-23 종가 19.45 와 같음)
    ['하루 흔들림(1표준편차)', `<b>±${n(sd * 100)}%</b> · ±${n(pt, 1)}`],
    ['68% 범위', `<b>${band(1)}</b>`],
    ['95% 범위', `<b>${band(1.96)}</b>`],
  ].map(([k, v]) => `<div class="r"><span>${k}</span><span>${v}</span></div>`).join('');
})();
