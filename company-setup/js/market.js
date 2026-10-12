// 시황분석 탭 — 세계지도 말풍선 값으로 그날 시황을 화면이 쓰고, 지표 흐름을 그래프로 보인다 (2026-10-12 재권님 「시황분석을 클릭하면 지금 분석해놓은게 나오면 ·
// 실시간 분석을 여기에 연결 · 나라별로 껐다 켰다 · 금값그래프도」 → temp 시안 → 「응 좋아 붙여줘」).
//   · 글은 세션이 손으로 쓰지 않는다 — 아래 write() 의 규칙 여섯(금리 방향 · 물가와 다음 회의 · 한 달 돈 간 곳 · 1년 흐름과 고점 · 경기선행 방향 · 금과 달러)이
//     값을 보고 정해진 문장을 고른다. 문단마다 근거(값 · 시각 · 출처)와 읽는 법을 접어 둔다
//   · 값 — 주가 · 금은 열 때마다 이 서버 /api/kis/chart(KIS 해외 일봉). 금리 · 물가 · 환율 · 기간 흐름은 data/world-macro.json(tools/fetch-world-macro.py · 지도 말풍선과 같은 파일)
//   · 나라 칩을 끄면 모든 그래프에서 그 나라가 빠진다. 글은 아홉 곳 전부로 쓴다
//   · 색은 theme.css 토큰을 읽는다(canvas 는 CSS 를 못 읽는다)
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const K = ['US', 'EZ', 'JP', 'BR', 'CL', 'VN', 'AU', 'KR', 'CN'];
const NAME = { US: '미국', EZ: '유로존', JP: '일본', BR: '브라질', CL: '칠레', VN: '베트남', AU: '호주', KR: '한국', CN: '중국', GOLD: '금', DXY: '달러지수' };
const COL = { US: css('--accent'), EZ: css('--kh-cat-indigo'), JP: css('--kh-cat-rose'), BR: css('--kh-cat-teal'), CL: css('--kh-cat-amber'), VN: css('--kh-cat-violet'),
              AU: css('--kh-ma5'), KR: css('--kh-up'), CN: css('--kh-cat-slate'), GOLD: css('--kh-cat-amber'), DXY: css('--kh-cat-slate') };
const ETF = { US: 'SPY', EZ: 'EZU', JP: 'EWJ', BR: 'EWZ', CL: 'ECH', VN: 'VNM', AU: 'EWA', KR: 'EWY', CN: 'MCHI', GOLD: 'GLD' };
// 채권 — 국채 금리는 world-macro.json series.yld(미국 2 · 10년 FRED · 한국 3 · 10년 ECOS), 채권 ETF 는 열 때 서버에서 (2026-10-12 재권님 「시황에 채권도 있어야」)
// ── 해석 틀 둘 (2026-10-12 재권님 「응 넣어줘」 · 근거는 아래 각 주석의 원문)
// ① 침체 확률 — 뉴욕 연준 에스트레야 · 미시킨(1996) 「The Yield Curve as a Predictor of U.S. Recessions」 표: 10년 − 3개월 금리차(분기 평균)
//    → 4분기 뒤 침체 확률. 표 사이는 직선으로 잇는다 · 1.21%p 넘으면 「5% 미만」. newyorkfed.org/research/current_issues/ci2-7.pdf
const RECESSION = [[1.21, 5], [0.76, 10], [0.46, 15], [0.22, 20], [0.02, 25], [-0.17, 30], [-0.50, 40], [-0.82, 50], [-1.13, 60], [-1.46, 70], [-1.85, 80], [-2.40, 90]];
function recessionProb(sp) {
  if (sp >= RECESSION[0][0]) return null;                    // 5% 미만
  if (sp <= RECESSION[RECESSION.length - 1][0]) return 90;
  for (let i = 1; i < RECESSION.length; i++) {
    const [s0, p0] = RECESSION[i - 1], [s1, p1] = RECESSION[i];
    if (sp >= s1) return p0 + (s0 - sp) / (s0 - s1) * (p1 - p0);
  }
}
function termSpread(Y) {                                       // [(날짜, 10년 − 3개월)] 매일
  if (!Y || !Y.US10 || !Y.US3M) return [];
  const m = new Map(Y.US3M); return Y.US10.filter(([d]) => m.has(d)).map(([d, v]) => [d, +(v - m.get(d)).toFixed(3)]);
}
const qAvg = (ser, i) => { const w = ser.slice(Math.max(0, i - 62), i + 1); return w.reduce((a, b) => a + b[1], 0) / w.length; };   // 분기 ≈ 63 거래일
// ② 투자 시계 — 메릴린치(2004) 「The Investment Clock」: 성장(평소보다 빨라지나) × 물가(오르나) 네 국면과 그때 강했던 자산.
//    원래는 산출 갭 · 물가 추세로 정하는데, 여기서는 OECD 경기선행지수와 월 물가의 석 달 방향으로 어림한다(「어림」 이라 적는다)
const CLOCK = { '1,0': ['회복', '주식'], '1,1': ['과열', '원자재'], '0,1': ['스태그플레이션', '현금'], '0,0': ['리플레이션', '채권'] };
function clockOf(S, k) {
  const c = S.cli[k], p = S.cpi[k];
  if (!c || !p || c.length < 4 || p.length < 4) return null;
  const old = new Date(); old.setMonth(old.getMonth() - 6);
  if (p[p.length - 1][0] < old.toISOString().slice(0, 7)) return null;   // 물가가 반년 넘게 멈춘 나라(유로존 2025-12)는 국면을 안 매긴다
  const g = c[c.length - 1][1] - c[c.length - 4][1], f = p[p.length - 1][1] - p[p.length - 4][1];
  return { g, f, gAt: c[c.length - 1][0], fAt: p[p.length - 1][0], ph: CLOCK[`${g > 0 ? 1 : 0},${f > 0 ? 1 : 0}`] };
}
const YLD = { US2: ['US', '미국 2년'], US10: ['US', '미국 10년'], KR3: ['KR', '한국 3년'], KR10: ['KR', '한국 10년'] };   // 나라 칩으로 함께 켜고 끈다
const BOND = { SHY: '미국 국채 단기(1~3년)', IEF: '미국 국채 중기(7~10년)', TLT: '미국 국채 장기(20년+)', LQD: '미국 우량 회사채', HYG: '미국 하이일드 회사채', EMB: '신흥국 달러 채권', BNDX: '미국 밖 선진국 채권' };
const MON = ym => `${+ym.slice(5, 7)}월`;
const pct = (v, d = 1) => v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(d)}%`;
// 받침에 맞는 조사 — 「한국이」 · 「미국이」 · 「브라질이」 · 「호주가」
const josa = (w, a, b) => { const c = w.charCodeAt(w.length - 1) - 0xac00; return w + (c >= 0 && c <= 11171 && c % 28 ? a : b); };
const day = s => s.length === 8 ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6)}` : s;
Chart.defaults.font.family = "'Noto Sans KR', sans-serif"; Chart.defaults.font.size = 11; Chart.defaults.color = css('--text-secondary');
const grid = { color: css('--kh-chart-grid') };
const charts = [];
const on = new Set(K);   // 켜 둔 나라 — 그래프만 거른다. 글은 아홉 곳 전부로 쓴다

// ── 값 받기 — 주가 · 금은 열 때마다 서버에서(실시간 쪽), 나머지는 파일
async function chart(code) {
  const j = await (await fetch(`/api/kis/chart?code=${code}&period=D`)).json();
  return j.data.candles.filter(c => c.close).map(c => [day(c.ts), c.close]);
}
async function load() {
  const [M, N, ...px] = await Promise.all([
    fetch('data/world-macro.json', { cache: 'no-store' }).then(r => r.json()),
    fetch('data/naver-macro.json', { cache: 'no-store' }).then(r => r.json()).catch(() => null),   // 그 밖의 지표 — 못 받아도 위 셋은 그린다
    ...[...K, 'GOLD'].map(k => chart(ETF[k]).catch(() => null)),
    ...Object.keys(BOND).map(b => chart(b).catch(() => null))]);
  const P = {}; [...K, 'GOLD', ...Object.keys(BOND)].forEach((k, i) => { P[k] = px[i] ? px[i].slice(-252) : null; });
  return { M, N, S: M.series, P };
}

// ── 규칙으로 쓰는 문단 R1~R6 — 각 문단은 { 글, 근거[], 읽는 법 }
function rateTurns(ser) {   // 기간 값에서 바뀐 때 [(월, 앞, 뒤)]
  const out = []; for (let i = 1; i < ser.length; i++) if (ser[i][1] !== ser[i - 1][1]) out.push([ser[i][0], ser[i - 1][1], ser[i][1]]); return out;
}
function write({ M, S, P }) {
  const C = M.countries, paras = [];
  const yr = String(new Date().getFullYear());
  // R1 금리 방향
  const up = K.filter(k => C[k].rate && C[k].rate.dir === 'up'), dn = K.filter(k => C[k].rate && C[k].rate.dir === 'down');
  const turned = K.filter(k => S.rate[k]).map(k => { const t = rateTurns(S.rate[k]); const now = t.filter(x => x[0].startsWith(yr)); const before = t.filter(x => !x[0].startsWith(yr));
    const dirOf = x => x[2] > x[1] ? 1 : -1; return { k, now, flip: now.length && before.length && dirOf(now[now.length - 1]) !== dirOf(before[before.length - 1]) }; });
  const flips = turned.filter(t => t.flip);
  paras.push({ t: `직전 결정이 인상인 곳이 ${up.length}곳(${up.map(k => NAME[k]).join(' · ')}), 인하는 ${dn.length}곳(${dn.map(k => NAME[k]).join(' · ') || '없음'})이다. `
      + (flips.length ? `지난해까지와 방향을 바꾼 곳은 ${flips.map(f => `${NAME[f.k]}(${f.now.map(x => MON(x[0])).join(' · ')})`).join(' · ')}이다.` : ''),
    ev: [...K.filter(k => C[k].rate).map(k => `${NAME[k]} ${C[k].rate.v}% · 직전 ${C[k].rate.prev ?? '—'} → ${C[k].rate.v} (${C[k].rate.since}) · ${C[k].rate.src}`), '베트남 — 받는 곳 없음'],
    why: '인상 · 인하 곳 수는 지도 말풍선의 「직전 결정」 을 센 것이다. 「방향을 바꿨다」 는 2024년부터의 정책금리에서 올해 마지막 변경과 지난해까지 마지막 변경의 방향이 다른 곳이다.' });
  // R2 물가와 다음 회의
  const hot = K.filter(k => C[k].cpi && !C[k].cpi.annual && C[k].cpi.v > 2.5);
  paras.push({ t: `월 물가가 목표(2%)보다 0.5%p 넘게 높은 곳은 ${hot.map(k => `${NAME[k]} ${C[k].cpi.v}%`).join(' · ') || '없다'}. `
      + (C.US.meet ? `다음 고비는 미국 연준 회의(${C.US.meet.v})다.` : ''),
    ev: K.filter(k => C[k].cpi).map(k => `${NAME[k]} 물가 ${C[k].cpi.v}% (${C[k].cpi.date}${C[k].cpi.annual ? ' · 연간' : ''}) · 정책금리 − 물가 ${C[k].rate ? (C[k].rate.v - C[k].cpi.v).toFixed(2) : '—'}%p · ${C[k].cpi.src}`),
    why: '물가가 목표보다 높고 실질 금리(정책금리 − 물가)가 0 에 가까우면 더 올릴 여지가 있다고 읽는다. 지난해 연간 값만 있는 나라는 셈에서 뺐다.' });
  // R3 돈이 간 곳 — 1개월 · 달러지수
  const m1 = K.filter(k => C[k].eq).map(k => [k, C[k].eq.m1]).sort((a, b) => b[1] - a[1]);
  const dx = C.US.dxy;
  paras.push({ t: `한 달 동안 가장 많이 오른 곳은 ${m1.slice(0, 2).map(([k, v]) => `${NAME[k]} ${pct(v)}`).join(' · ')}, 가장 많이 내린 곳은 ${m1.slice(-2).reverse().map(([k, v]) => `${NAME[k]} ${pct(v)}`).join(' · ')}이다. `
      + (dx ? `달러지수는 ${pct(dx.m1)} ${dx.m1 > 0 ? '강해져 달러로 매긴 나라 주가가 실제보다 나쁘게 보인다' : '약해져 달러로 매긴 나라 주가가 실제보다 좋게 보인다'}.` : ''),
    ev: [...m1.map(([k, v]) => `${NAME[k]} ${C[k].eq.etf} 1개월 ${pct(v)} (${day(C[k].eq.date)} · ${C[k].eq.src})`), dx ? `달러지수 ${dx.v} · 1개월 ${pct(dx.m1)} (${dx.date} · ${dx.src})` : '달러지수 —'],
    why: '나라 ETF 는 달러로 값을 매겨 그 나라 통화 변화가 섞인다. 달러가 강하면 다른 나라 ETF 가 통화 몫만큼 덜 오른다.' });
  // R4 1년 흐름 — 가장 많이 오른 나라와 고점에서 얼마
  const y1 = K.filter(k => P[k]).map(k => { const s = P[k], last = s[s.length - 1][1], first = s[0][1], top = s.reduce((a, b) => b[1] > a[1] ? b : a);
    return { k, y: (last / first - 1) * 100, dd: (last / top[1] - 1) * 100, top: top[0] }; }).sort((a, b) => b.y - a.y);
  const best = y1[0], worst = y1[y1.length - 1];
  const cliPeak = k => { const s = S.cli[k]; if (!s) return null; const top = s.reduce((a, b) => b[1] > a[1] ? b : a); return top[0] !== s[s.length - 1][0] ? top : null; };
  const kr = y1.find(x => x.k === 'KR'), krPeak = cliPeak('KR'), krTurn = S.rate.KR ? rateTurns(S.rate.KR).filter(x => x[0].startsWith(yr)) : [];
  paras.push({ t: `1년으로는 ${josa(NAME[best.k], '이', '가')} ${pct(best.y, 0)}로 가장 많이 올랐고 ${josa(NAME[worst.k], '이', '가')} ${pct(worst.y, 0)}로 가장 나쁘다. `
      + (kr ? `한국은 1년 ${pct(kr.y, 0)}이지만 ${+kr.top.slice(5, 7)}월 ${+kr.top.slice(8)}일 고점에서 ${pct(kr.dd, 0)} 내려와 있다`
        + (krTurn.length ? ` — 그 사이 기준금리를 ${krTurn.map(x => MON(x[0])).join(' · ')}에 올렸고` : '')
        + (krPeak ? ` 경기선행지수는 ${MON(krPeak[0])}(${krPeak[1]})에 꼭짓점을 찍고 꺾였다.` : '.') : ''),
    ev: y1.map(x => `${NAME[x.k]} 1년 ${pct(x.y, 1)} · 고점 ${x.top} 에서 ${pct(x.dd, 1)} (KIS 해외 일봉 · ${ETF[x.k]})`),
    why: '한 달 값만 보면 크게 오른 뒤 쉬는 나라와 처음부터 약한 나라가 똑같이 「내림」 으로 보인다. 1년 등락과 고점에서 얼마나 내려왔는지를 함께 본다.' });
  // R5 경기선행 — 오르는 곳 · 내리는 곳
  const cliDir = K.filter(k => S.cli[k] && S.cli[k].length > 3).map(k => { const s = S.cli[k], a = s[s.length - 4][1], b = s[s.length - 1][1]; return { k, v: b, d: b - a }; });
  const rising = cliDir.filter(x => x.d > 0.05), falling = cliDir.filter(x => x.d < -0.05);
  paras.push({ t: `경기선행지수가 석 달 동안 오르는 곳은 ${rising.map(x => `${NAME[x.k]} ${x.v.toFixed(2)}`).join(' · ') || '없고'}, 내리는 곳은 ${falling.map(x => `${NAME[x.k]} ${x.v.toFixed(2)}`).join(' · ') || '없다'}. `
      + (falling.filter(x => x.v < 100).length ? `${falling.filter(x => x.v < 100).map(x => NAME[x.k]).join(' · ')} — 장기 평균(100) 아래에서 더 내려가 식는 쪽이다.` : ''),
    ev: cliDir.map(x => `${NAME[x.k]} ${x.v.toFixed(2)} · 석 달 ${x.d > 0 ? '+' : ''}${x.d.toFixed(2)} (OECD · ${S.cli[x.k][S.cli[x.k].length - 1][0]})`),
    why: '경기선행지수는 100 이 장기 평균이다. 높이보다 방향이 먼저다 — 100 위라도 내려가면 「좋은데 덜 좋아지는 중」 이다. 석 달 차이가 ±0.05 안이면 제자리로 본다.' });
  // R7 채권 — 국채 금리 1개월 변화 · 장단기 차이 · 장기채 값 · 하이일드 vs 국채
  const Y = S.yld || {}, bp = (ser) => ser && ser.length > 21 ? Math.round((ser[ser.length - 1][1] - ser[ser.length - 22][1]) * 100) : null;
  const lastY = n => Y[n] && Y[n].length ? Y[n][Y[n].length - 1] : null;
  const m1of = c => P[c] && P[c].length > 21 ? (P[c][P[c].length - 1][1] / P[c][P[c].length - 22][1] - 1) * 100 : null;
  if (lastY('US10')) {
    const us10 = lastY('US10'), us2 = lastY('US2'), kr10 = lastY('KR10'), kr3 = lastY('KR3');
    const sp = us2 ? us10[1] - us2[1] : null, spPrev = Y.US2 && Y.US2.length > 21 ? Y.US10[Y.US10.length - 22][1] - Y.US2[Y.US2.length - 22][1] : null;
    const tlt = m1of('TLT'), hyg = m1of('HYG'), ief = m1of('IEF');
    const bps = v => v == null ? '—' : `${v > 0 ? '+' : ''}${v}bp`;
    paras.push({ t: `미국 10년 국채 금리는 ${us10[1].toFixed(2)}%로 한 달 ${bps(bp(Y.US10))}` + (kr10 ? `, 한국 10년은 ${kr10[1].toFixed(2)}%로 ${bps(bp(Y.KR10))}` : '') + ' 움직였다. '
        + (bp(Y.US10) > 0 ? '금리가 오르면 이미 있는 채권 값은 내린다' : '금리가 내리면 이미 있는 채권 값은 오른다') + (tlt != null ? ` — 미국 장기채(TLT)가 한 달 ${pct(tlt)}다. ` : '. ')
        + (sp != null ? `미국 10년 − 2년 차이는 ${sp.toFixed(2)}%p${spPrev != null ? `(한 달 전 ${spPrev.toFixed(2)})` : ''}로 ${sp > 0 ? '바로 서 있다' : '거꾸로 서 있다(경기 침체 신호로 읽힌다)'}. ` : '')
        + (hyg != null && ief != null ? (hyg - ief > 0.5 ? `하이일드 회사채(${pct(hyg)})가 국채(${pct(ief)})보다 강해 위험을 사는 돈이 아직 많다.` : hyg - ief < -0.5 ? `하이일드 회사채(${pct(hyg)})가 국채(${pct(ief)})보다 약해 위험을 피하는 쪽으로 돈이 움직인다.` : `하이일드 회사채와 국채가 비슷하게(${pct(hyg)} · ${pct(ief)}) 움직였다.`) : ''),
      ev: [...['US2', 'US10', 'KR3', 'KR10'].filter(n => lastY(n)).map(n => `${YLD[n][1]} ${lastY(n)[1].toFixed(2)}% (${lastY(n)[0]}) · 한 달 ${bps(bp(Y[n]))} · ${n.startsWith('US') ? 'FRED ' + (n === 'US2' ? 'DGS2' : 'DGS10') : '한국은행 ECOS 817Y002'}`),
           ...Object.keys(BOND).filter(b => P[b]).map(b => `${BOND[b]} ${b} 한 달 ${pct(m1of(b))} (KIS 해외 일봉 · ${P[b][P[b].length - 1][0]})`)],
      why: '채권 값과 금리는 거꾸로 간다. 10년 − 2년 차이가 0 아래면 앞날 경기를 나쁘게 본다는 뜻으로 읽는다. 하이일드(부실 위험이 큰 회사채)가 국채보다 강하면 위험을 사는 돈, 약하면 피하는 돈으로 읽는다(차이 ±0.5%p 안은 비슷함). 지도 말풍선의 10년 금리도 미국 · 한국은 같은 매일 값이고, 다른 나라는 달마다 값이라 늦다.' });
  }
  // R8 침체 확률 — 뉴욕 연준 표
  const ts = termSpread(Y);
  if (ts.length > 63) {
    const q = qAvg(ts, ts.length - 1), qPrev = qAvg(ts, ts.length - 64), pr = recessionProb(q), prP = recessionProb(qPrev);
    const say = v => v == null ? '5% 미만' : `약 ${Math.round(v)}%`;
    paras.push({ t: `미국 10년 − 3개월 국채 금리차는 최근 석 달 평균 ${q.toFixed(2)}%p다. 뉴욕 연준 표로 읽으면 1년 뒤 경기 침체 확률은 ${say(pr)}(석 달 전 ${say(prP)})로, `
        + (pr == null || pr < 15 ? '아직 낮은 편이다.' : pr < 40 ? '눈여겨볼 만큼 올라왔다.' : '높다 — 금리차가 거꾸로 서 있다.'),
      ev: [`미국 10년 ${lastY('US10')[1].toFixed(2)}% · 3개월 ${lastY('US3M') ? lastY('US3M')[1].toFixed(2) : '—'}% (${ts[ts.length - 1][0]} · FRED DGS10 · DGS3MO)`,
           `금리차 석 달 평균 ${q.toFixed(2)}%p → ${say(pr)} · 석 달 전 평균 ${qPrev.toFixed(2)}%p → ${say(prP)}`,
           '뉴욕 연준 표(금리차 → 4분기 뒤 침체 확률): 1.21 → 5% · 0.76 → 10% · 0.46 → 15% · 0.22 → 20% · 0.02 → 25% · −0.17 → 30% · −0.50 → 40% · −0.82 → 50% · −1.13 → 60% · −1.46 → 70% · −1.85 → 80% · −2.40 → 90% (에스트레야 · 미시킨 1996 · 1960~1995 자료)'],
      why: '긴 금리가 짧은 금리보다 낮아지면(금리차가 0 아래) 시장이 앞날 경기를 나쁘게 본다는 뜻이다. 표는 1960~1995 년 자료로 만든 것이라 지금 경제에 그대로 맞는다는 보장은 없다 — 확률은 「얼마나 경계할지」 의 눈금으로 쓴다. 표 사이 값은 직선으로 이어 어림했다.' });
  }
  // R9 투자 시계 국면 — 메릴린치
  const ck = K.map(k => [k, clockOf(S, k)]).filter(([, v]) => v);
  if (ck.length) {
    const by = {}; ck.forEach(([k, v]) => { (by[v.ph[0]] = by[v.ph[0]] || []).push(k); });
    paras.push({ t: '투자 시계로 어림한 국면은 ' + Object.entries(by).map(([ph, ks]) => `${ks.map(k => NAME[k]).join(' · ')} — ${ph}(${Object.values(CLOCK).find(x => x[0] === ph)[1]} 강세 국면)`).join(', ') + '이다.',
      ev: ck.map(([k, v]) => `${NAME[k]} 경기선행 석 달 ${v.g > 0 ? '+' : ''}${v.g.toFixed(2)}(${v.gAt}) · 물가 석 달 ${v.f > 0 ? '+' : ''}${v.f.toFixed(2)}%p(${v.fAt}) → ${v.ph[0]}`),
      why: '메릴린치 투자 시계(2004)는 성장이 평소보다 빨라지는지와 물가가 오르는지로 네 국면을 나눈다 — 회복(성장↑ · 물가↓ · 주식), 과열(성장↑ · 물가↑ · 원자재), 스태그플레이션(성장↓ · 물가↑ · 현금), 리플레이션(성장↓ · 물가↓ · 채권). 원래 틀은 산출 갭과 물가 추세를 쓰는데 여기서는 경기선행지수와 물가의 석 달 방향으로 어림했다. 국면별 강한 자산은 과거 평균이지 이번에도 그렇다는 약속이 아니다 — 학계 시험에서 이런 지표로 시장 시점을 맞히기는 어려웠다(웰치 · 고얄 2008).' });
  }
  // R6 금 · 달러
  const g = P.GOLD;
  if (g) {
    const gy = (g[g.length - 1][1] / g[0][1] - 1) * 100, gm = (g[g.length - 1][1] / g[g.length - 22][1] - 1) * 100;
    const dy = S.dxy && S.dxy.length > 21 ? (S.dxy[S.dxy.length - 1][1] / S.dxy[S.dxy.length - 22][1] - 1) * 100 : null;
    const both = dy != null && gm > 0 && dy > 0;
    paras.push({ t: `금값(GLD)은 1년 ${pct(gy, 0)}, 한 달 ${pct(gm)}이다. ` + (dy == null ? '' : both ? `달러가 강해지는데도 금이 함께 올라, 보통의 「달러 강세 = 금 약세」 가 아니라 불안해서 사는 돈이 섞여 있다고 본다.`
        : gm > 0 ? '달러가 약해지며 금이 올랐다 — 보통의 짝이다.' : dy > 0 ? '달러가 강해지며 금이 내렸다 — 보통의 짝이다.' : '달러와 금이 함께 내렸다.'),
      ev: [`금 GLD ${g[g.length - 1][1]} 달러 (${g[g.length - 1][0]} · KIS 해외 일봉) · 1년 ${pct(gy)} · 1개월 ${pct(gm)}`, dy != null ? `달러지수 1개월 ${pct(dy)} (FRED · ${S.dxy[S.dxy.length - 1][0]})` : '달러지수 —'],
      why: '금은 달러로 값을 매겨 보통 달러와 반대로 간다. 둘이 함께 오르면 금리 · 환율 밖의 이유(불안 · 중앙은행 매입)가 있다고 읽는다. 무엇이 이유인지는 이 값들로는 모른다.' });
  }
  // 한 줄 — 위 규칙의 앞머리를 잇는다
  const one = `금리를 올리는 곳 ${up.length} · 내리는 곳 ${dn.length} — 한 달 사이 돈은 ${m1.slice(0, 2).map(([k]) => NAME[k]).join(' · ')}로, 1년으로는 ${josa(NAME[best.k], "이", "가")} 가장 많이 올랐다`
    + (kr && kr.dd < -10 ? ` · 한국은 고점에서 ${pct(kr.dd, 0)} 쉬어 가는 중` : '')
    + (ts.length > 63 ? ` · 미국 1년 뒤 침체 확률 ${recessionProb(qAvg(ts, ts.length - 1)) == null ? '5% 미만' : '약 ' + Math.round(recessionProb(qAvg(ts, ts.length - 1))) + '%'}(뉴욕 연준 표)` : '')
    + (lastY('US10') && bp(Y.US10) != null ? ` · 미국 10년 금리 ${lastY('US10')[1].toFixed(2)}%(한 달 ${bp(Y.US10) > 0 ? '+' : ''}${bp(Y.US10)}bp)` : '') + (C.US.meet ? ` · 다음 볼 것 미국 연준 ${C.US.meet.v}` : '') + '.';
  return { one, paras };
}

// ── 그래프
const line = (k, pts, extra = {}) => ({ key: k, label: NAME[k], data: pts.map(([x, y]) => ({ x, y })), borderColor: COL[k], backgroundColor: COL[k],
  borderWidth: k === 'KR' || k === 'GOLD' ? 2.4 : 1.5, pointRadius: 0, tension: 0, ...extra });
const opt = (yTitle, more = {}) => ({ maintainAspectRatio: false, animation: false, interaction: { mode: 'index', intersect: false },
  plugins: { legend: { display: false } }, scales: { x: { type: 'category', grid, ticks: { maxTicksLimit: 7 } }, y: { grid, title: { display: true, text: yTitle } }, ...more } });
const ref = (labels, y, text) => ({ key: '_', label: text, data: labels.map(x => ({ x, y })), borderColor: css('--text-muted'), borderDash: [4, 4], borderWidth: 1, pointRadius: 0 });
function draw({ M, S, P }) {
  const C = M.countries, add = (id, cfg) => charts.push(new Chart(document.getElementById(id), cfg));
  const days = (P.US || P.GOLD || [[]]).map(p => p[0]);
  add('c-eq', { type: 'line', data: { labels: days, datasets: K.filter(k => P[k]).map(k => line(k, P[k].map(([d, v]) => [d, +(v / P[k][0][1] * 100).toFixed(2)]))) }, options: opt('처음 = 100') });
  if (P.GOLD) add('c-gold', { type: 'line', data: { labels: P.GOLD.map(p => p[0]), datasets: [line('GOLD', P.GOLD, { yAxisID: 'y' }),
      line('DXY', (() => { const m = new Map(S.dxy || []); let last = null; return P.GOLD.map(([d]) => [d, m.has(d) ? (last = m.get(d)) : last]); })(), { yAxisID: 'y2', borderDash: [3, 3] })] },
    options: { ...opt('금 GLD 달러', { y2: { position: 'right', grid: { display: false }, title: { display: true, text: '달러지수' } } }),
      plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 12, boxHeight: 2 } } } } });
  else document.getElementById('cap-gold').innerHTML = '<span class="err">금값을 받지 못했습니다</span>';
  const tsr = termSpread(S.yld);
  if (tsr.length > 63) {
    const pts = tsr.map((p, i) => i < 62 ? null : [p[0], qAvg(tsr, i)]).filter(Boolean);
    add('c-rec', { type: 'line', data: { labels: pts.map(p => p[0]), datasets: [
        { key: 'US', label: '금리차 석 달 평균(%p · 왼쪽)', data: pts.map(([x, v]) => ({ x, y: +v.toFixed(3) })), borderColor: COL.US, backgroundColor: COL.US, borderWidth: 1.6, pointRadius: 0, yAxisID: 'y' },
        { key: 'US', label: '침체 확률(% · 오른쪽 · 5% 미만은 5)', data: pts.map(([x, v]) => ({ x, y: +(recessionProb(v) ?? 5).toFixed(1) })), borderColor: css('--kh-up'), backgroundColor: css('--kh-up'), borderWidth: 2, pointRadius: 0, yAxisID: 'y2' }] },
      options: { ...opt('금리차 %p', { y2: { position: 'right', min: 0, grid: { display: false }, title: { display: true, text: '침체 확률 %' } } }), plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 12, boxHeight: 2 } } } } });
  }
  const clk = document.getElementById('clock');
  if (clk) {
    const cells = { '회복': [], '과열': [], '스태그플레이션': [], '리플레이션': [] };
    K.forEach(k => { const v = clockOf(S, k); if (v) cells[v.ph[0]].push(`<span class="ck-c" style="--c:${COL[k]}">${NAME[k]}</span>`); });
    const cell = (ph, side) => `<div class="ck-q"><b>${ph}</b><span class="ck-s">${side}</span><div>${cells[ph].join('') || '<span class="ck-none">—</span>'}</div></div>`;
    clk.innerHTML = cell('과열', '성장↑ 물가↑ · 원자재') + cell('회복', '성장↑ 물가↓ · 주식') + cell('스태그플레이션', '성장↓ 물가↑ · 현금') + cell('리플레이션', '성장↓ 물가↓ · 채권');
  }
  if (S.yld && S.yld.US10) {
    const yd = [...new Set(Object.values(S.yld).flat().map(p => p[0]))].sort();
    const at = ser => { const m = new Map(ser); let last = null; return yd.map(d => [d, m.has(d) ? (last = m.get(d)) : last]); };
    add('c-yld', { type: 'line', data: { labels: yd, datasets: Object.keys(YLD).filter(n => S.yld[n]).map(n => ({ ...line(YLD[n][0], at(S.yld[n]), { borderDash: n.endsWith('10') ? [] : [4, 3] }), label: YLD[n][1] })) },
      options: { ...opt('금리 %'), plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 12, boxHeight: 2 } } } } });
  }
  const bk = Object.keys(BOND).filter(b => P[b]);
  if (bk.length) {
    const bc = [css('--accent'), css('--kh-cat-indigo'), css('--kh-cat-violet'), css('--kh-cat-teal'), css('--kh-up'), css('--kh-cat-amber'), css('--kh-cat-slate')];
    add('c-bond', { type: 'line', data: { labels: P[bk[0]].map(p => p[0]), datasets: bk.map((b, i) => ({ key: '_bond', label: `${BOND[b]} ${b}`, data: P[b].map(([x, v]) => ({ x, y: +(v / P[b][0][1] * 100).toFixed(2) })),
      borderColor: bc[i], backgroundColor: bc[i], borderWidth: b === 'TLT' || b === 'HYG' ? 2.2 : 1.4, pointRadius: 0 })) },
      options: { ...opt('처음 = 100'), plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 12, boxHeight: 2, font: { size: 10 } } } } } });
  }
  const months = [...new Set(Object.values(S.rate).flat().map(p => p[0]))].sort();
  const fill = pts => { const m = new Map(pts); let last = null; return months.map(x => [x, m.has(x) ? (last = m.get(x)) : last]); };
  add('c-rate', { type: 'line', data: { labels: months, datasets: K.filter(k => S.rate[k]).map(k => line(k, fill(S.rate[k]), { stepped: true, yAxisID: k === 'BR' ? 'y2' : 'y' })) },
    options: opt('정책금리 %', { y2: { position: 'right', grid: { display: false }, title: { display: true, text: '브라질 %' } } }) });
  const cm = [...new Set(Object.values(S.cpi).flat().map(p => p[0]))].sort();
  add('c-cpi', { type: 'line', data: { labels: cm, datasets: [...K.filter(k => S.cpi[k]).map(k => line(k, S.cpi[k])), ref(cm, 2, '목표 2%')] }, options: opt('전년비 %') });
  const lm = [...new Set(Object.values(S.cli).flat().map(p => p[0]))].sort();
  add('c-cli', { type: 'line', data: { labels: lm, datasets: [...K.filter(k => S.cli[k]).map(k => line(k, S.cli[k])), ref(lm, 100, '장기 평균')] }, options: opt('지수') });
  const local = k => { const c = C[k]; if (!c.eq) return null; if (k === 'US') return c.eq.m1; if (!c.fx) return null; const e = 1 + c.eq.m1 / 100, f = 1 + c.fx.m1 / 100;
    return +(((k === 'EZ') ? e / f : e * f) * 100 - 100).toFixed(1); };
  // 막대 그래프는 나라가 x 축이라, 끈 나라는 그 칸을 빼고 다시 그린다
  const bars = (id, build) => { const ch = new Chart(document.getElementById(id), build(K)); ch._rebuild = () => { const b = build(K.filter(k => on.has(k))); ch.data = b.data; ch.update(); }; charts.push(ch); };
  bars('c-m1', ks => ({ type: 'bar', data: { labels: ks.map(k => NAME[k]), datasets: [
    { label: '달러로', data: ks.map(k => C[k].eq ? C[k].eq.m1 : null), backgroundColor: css('--kh-cat-slate') },
    { label: '그 나라 돈으로(어림)', data: ks.map(local), backgroundColor: css('--accent') }] },
    options: { ...opt('1개월 %'), plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 12 } } }, scales: { x: { grid }, y: { grid, title: { display: true, text: '1개월 %' } } } } }));
  bars('c-real', ks => { const rk = ks.filter(k => C[k].rate && C[k].cpi); return { type: 'bar', data: { labels: rk.map(k => NAME[k]), datasets: [
    { label: '정책금리 − 물가', data: rk.map(k => +(C[k].rate.v - C[k].cpi.v).toFixed(2)), backgroundColor: rk.map(k => C[k].cpi.annual ? css('--kh-cat-slate-dim') : COL[k]) }] },
    options: { ...opt('%p'), scales: { x: { grid }, y: { grid, min: -2.5, max: 3, title: { display: true, text: '%p' } } } } }; });
}
// ── 그 밖의 지표 — data/naver-macro.json(tools/fetch-naver-macro.py · 손으로 돌림 · 2026-10-12 재권님 「응 붙여줘」 · 받는 방식 (가)).
//    홀딩스에 시장지표 차트가 들어와 서버가 이 값을 내주면 거기서 받는다(재권님 10-12) — 그때 이 파일 받기를 그쪽 주소로 바꾼다
const CURVE = { USA: 'US', KOR: 'KR', JPN: 'JP', DEU: 'EZ', CHN: 'CN', BRA: 'BR', AUS: 'AU', GBR: 'GB' };   // 독일 = 유로존 칩으로 켜고 끈다 · 영국은 칩이 없어 늘 보인다
function others(N) {
  const nv = document.getElementById('meta-nv');
  if (!N) { nv.innerHTML = '<span class="err">그 밖의 지표 값을 받지 못했습니다 — company-setup/tools/fetch-naver-macro.py 를 돌리면 생긴다</span>'; return; }
  nv.textContent = `${N.fetchedAt} 받음 · ${N.src}` + (Object.keys(N.errors || {}).length ? ` · 못 받은 것 ${Object.keys(N.errors).join(', ')}` : '');
  const add = (id, cfg) => charts.push(new Chart(document.getElementById(id), cfg));
  const H = N.hist || {}, pal = [css('--accent'), css('--kh-cat-amber'), css('--kh-cat-slate'), css('--kh-cat-teal'), css('--kh-cat-violet'), css('--kh-cat-rose')];
  const legend = { legend: { display: true, position: 'bottom', labels: { boxWidth: 12, boxHeight: 2, font: { size: 10 } } } };
  const days = names => [...new Set(names.filter(n => H[n]).flatMap(n => H[n].s.map(p => p[0])))].sort();
  const at = (ser, ds) => { const m = new Map(ser); let last = null; return ds.map(d => (m.has(d) ? (last = m.get(d)) : last)); };
  const set = (n, i, ds, f = v => v, more = {}) => ({ key: '_nv', label: n, data: at(H[n].s, ds).map(f), borderColor: pal[i], backgroundColor: pal[i], borderWidth: 1.6, pointRadius: 0, spanGaps: true, ...more });
  const oil = ['WTI', '브렌트유', '두바이유'].filter(n => H[n]), od = days(oil);
  if (oil.length) add('c-oil', { type: 'line', data: { labels: od, datasets: oil.map((n, i) => set(n, i, od)) }, options: { ...opt('달러/배럴'), plugins: legend } });
  const cmd = ['은', '구리(선물)', 'BDI 건화물선지수', '상하이컨테이너 운임지수', '중국컨테이너 운임지수'].filter(n => H[n]), cd = days(cmd);
  if (cmd.length) add('c-cmd', { type: 'line', data: { labels: cd, datasets: cmd.map((n, i) => { const b = H[n].s[0][1]; return set(n, i, cd, v => v == null ? null : +(v / b * 100).toFixed(2), { borderDash: i > 1 ? [4, 3] : [] }); }) },
    options: { ...opt('처음 = 100'), plugins: legend } });
  const kr = ['콜금리 (1일)', 'CD금리 (91일)', '한국 국채 3년', '회사채 (3년, AA-)', '회사채 (3년, BBB-)'].filter(n => H[n]), kd = days(kr);
  if (kr.length) add('c-krr', { type: 'line', data: { labels: kd, datasets: kr.map((n, i) => set(n, i, kd, v => v, n.includes('BBB') ? { yAxisID: 'y2', borderDash: [4, 3] } : {})) },
    options: { ...opt('금리 %', { y2: { position: 'right', grid: { display: false }, title: { display: true, text: 'BBB- %' } } }), plugins: legend } });
  const yrs = name => { const m = name.match(/(\d+)(년|개월)/); return m ? (m[2] === '년' ? +m[1] : +m[1] / 12) : null; };
  const cv = Object.keys(N.bond || {}).filter(n => n !== 'BRA' && (N.bond[n] || []).length);   // 브라질은 12%대라 한 눈금에 넣으면 나머지가 납작해져 뺀다
  if (cv.length) add('c-curve', { type: 'line', data: { datasets: cv.map(n => { const k = CURVE[n], c = COL[k] || css('--kh-cat-slate');
      const pts = N.bond[n].map(x => ({ x: yrs(x.name), y: x.v })).filter(p => p.x != null && p.y != null).sort((a, b) => a.x - b.x);
      return { key: k, label: N.bond[n][0].name.replace(/\s*국채.*$/, ''), data: pts, borderColor: c, backgroundColor: c, borderWidth: k === 'KR' ? 2.4 : 1.5, pointRadius: 2, borderDash: k === 'GB' ? [4, 3] : [] }; }) },
    options: { maintainAspectRatio: false, animation: false, interaction: { mode: 'nearest', intersect: false },
      plugins: legend, scales: { x: { type: 'logarithmic', grid, title: { display: true, text: '만기(년 · 로그 눈금)' }, ticks: { callback: v => [0.25, 1, 2, 5, 10, 30].includes(+v) ? (v < 1 ? '3개월' : v + '년') : '' } },
        y: { grid, title: { display: true, text: '금리 %' } } } } });
  const box = document.getElementById('nv-now'), row = x => x.v == null ? '' :
    `<div class="r"><span>${x.name}</span><span><b>${x.v.toLocaleString('ko-KR', { maximumFractionDigits: 3 })}${x.unit || ''}</b>${x.pct == null ? '' : `<span class="p ${x.pct > 0 ? 'up' : x.pct < 0 ? 'dn' : ''}">${pct(x.pct, 2)}</span>`}</span></div>`;
  const pick = (cat, n) => (N[cat] || []).slice(0, n);
  const rate = xs => xs.map(x => ({ ...x, name: x.name, v: x.v, unit: '%' }));
  box.innerHTML = [['에너지', pick('energy', 6)], ['금속', pick('metals', 6)], ['운임', pick('transport', 6)], ['농산물', pick('agricultural', 6)],
    ['국내 금리', rate(pick('domesticInterest', 8))], ['기준금리', rate(pick('standardInterest', 8))]]
    .map(([g, xs]) => `<div><div class="g">${g}</div>${xs.map(row).join('')}</div>`).join('');
}
function apply() {
  charts.forEach(ch => {
    if (ch._rebuild) return ch._rebuild();
    ch.data.datasets.forEach((d, i) => { if (K.includes(d.key)) ch.setDatasetVisibility(i, on.has(d.key)); });
    ch.update();
  });
  document.querySelectorAll('#ctl button[data-k]').forEach(b => b.classList.toggle('on', on.has(b.dataset.k)));
}
function controls() {
  const box = document.getElementById('ctl');
  box.innerHTML = K.map(k => `<button data-k="${k}" class="on"><i style="background:${COL[k]}"></i>${NAME[k]}</button>`).join('')
    + '<button class="all" data-all="1">전부</button><button class="all" data-only="KR">한국만</button>';
  box.addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.k) { on.has(b.dataset.k) ? on.delete(b.dataset.k) : on.add(b.dataset.k); }
    if (b.dataset.all) K.forEach(k => on.add(k));
    if (b.dataset.only) { on.clear(); on.add(b.dataset.only); }
    apply();
  });
}

(async () => {
  let D;
  try { D = await load(); } catch (e) { document.getElementById('meta').innerHTML = '<span class="err">값을 받지 못했습니다</span>'; return; }
  const now = new Date(), hm = `${now.getHours()}:${String(now.getMinutes()).padStart(2, '0')}`;
  const lastEq = D.P.US ? D.P.US[D.P.US.length - 1][0] : '—';
  document.getElementById('meta').textContent = `주가 · 금 ${hm} 에 받음(마지막 거래일 ${lastEq}) · 금리 · 물가 · 환율 ${D.M.fetchedAt} 받음 · 글은 이 값들로 화면이 만든다`;
  const w = write(D);
  document.getElementById('one').textContent = w.one;
  const box = document.getElementById('text');
  w.paras.forEach((p, i) => {
    box.insertAdjacentHTML('beforeend', `<p class="para">${p.t}</p><details class="ev"><summary>근거 ${i + 1}</summary><ul>${p.ev.map(x => `<li>${x}</li>`).join('')}</ul><div class="why">읽는 법 — ${p.why}</div></details>`);
  });
  controls(); draw(D); others(D.N);
})();
