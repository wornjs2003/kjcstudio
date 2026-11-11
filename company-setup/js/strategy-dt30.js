// 투자 전략 「단타 30」 — 09:06 매수 → 30분마다 14:00 까지 · 30거래일 (2026-11-11 · 시황분석1)
//   · 재권님 「단타 목록 상위 30개를 소팅해서 9시 6분에 배수하고 9시반 10시 등 30분 단위로 2시까지 가격 추적하도록 셋팅해줘, 아래에 프리장 넣기 처럼 그 위에 종목 넣어서」 →
//     시안 temp/시황분석1-dt30-1743 → 「응 이대로 만드는데 위에 날짜도 넣어줘 30일 추적가능하도록」
//   · 그날 판(09:06 에 굳힌 단타 상위 30 · 매수가 · 각 시각 값)과 쌓인 날 목록은 서버 한 곳 — 화면은 그리기만(매수가 대비 % · 평균은 받은 값으로 셈)
//     응답(안 · 서버 레인과 맞춤): data { day, buyAt, times[HHMM], rows[{rank, code, name, cap(억원), sector(WICS), chips[], buy, px{HHMM: 값}}] } · meta { days[YYYYMMDD …최근 먼저] }
//   · 값이 없으면 — (0 이 아니다) · 서버를 다시 묻는 주기는 없다(날을 누를 때 · 처음 열 때 한 번)
import { signClass, NUM } from '/assets/js/sign.js';

const API = '/api/kis/dt30';   // 서버 주소 — 개발2(11-11 18:2x 정함 · 아직 커밋 전)
const $ = (id) => document.getElementById(id);
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (x, d = 0) => (x == null || !Number.isFinite(Number(x)) ? '—' : Number(x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (x) => { if (x == null || !Number.isFinite(x)) return '—'; const c = signClass(x, NUM); const t = `${x > 0 ? '+' : ''}${num(x, 2)}%`; return c ? `<span class="${c}">${t}</span>` : t; };
// 시가총액 — 억원(서버 cap) · 1조 이상은 조 단위 한 자리
const capTxt = (e) => { const v = Number(e); if (e == null || !Number.isFinite(v)) return '—'; return v >= 10000 ? `${num(v / 10000, 1)}조` : `${num(v)}억`; };
const WK = ['일', '월', '화', '수', '목', '금', '토'];
const dayTxt = (d) => { const m = String(d || '').match(/^(\d{4})(\d{2})(\d{2})$/); return m ? `${m[2]}-${m[3]}(${WK[new Date(+m[1], +m[2] - 1, +m[3]).getDay()]})` : '—'; };
const hmTxt = (t) => (/^\d{4}$/.test(String(t)) ? `${String(t).slice(0, 2)}:${String(t).slice(2)}` : esc(t || '—'));

// 이벤트 칸 — 그 종목이 걸린 홀딩스 「관심」 아래 룰(칩) 이름을 홀딩스 칩 줄 차례로 · 이름은 서버 rows[].chips 그대로(재권님 11-11 「종목과 매수가 사이에 이벤트를 추가하고 이벤트가 뭐뭐 걸렸는지 넣어줘 vi 초반급등 긍 관심하위의 룰들」)
const EV_ORDER = ['관심', '프리장', '초반상승', '현재상승', 'VI·급등', '볼린저', '장외', '매수', '수급'];
const evHtml = (c) => { const a = Array.isArray(c) ? [...c] : []; if (!a.length) return '<span class="st-err">—</span>'; a.sort((x, y) => (EV_ORDER.indexOf(x) + 99) % 99 - (EV_ORDER.indexOf(y) + 99) % 99); return a.map((x) => `<span class="dt-evc">${esc(x)}</span>`).join(''); };

const DOC = '/api/board/doc/strategy-rules';   // 수수료 % 를 두는 곳 — 투자 전략 룰 값과 같은 문서(rules.dt30.feePct)
const st = { order: '', fee: null, day: null, days: [], seq: 0, last: {}, only: '', data: null };   // only — 이벤트 거르기(재권님 11-11 「vi없는건 제외하고 다시 셈해봐」) · 빈칸이면 전체
const ONLY = [['', '전체'], ['VI·급등', 'VI·급등 든 것만']];
// 줄 세우기 (재권님 11-11 「상위 16종목을 vi급등이 있고 초반매수 가 있고 시가총액이 높은순으로 다시 정렬해서 계산해봐」 — 「초반매수」 는 초반상승 칩으로 읽음)
//   기본 = 서버 차례(단타 순) · vi = VI·급등 든 것 먼저 → 그 안에서 초반상승 든 것 먼저 → 시가총액 큰 순 — 상위 16 · 손익을 이 차례로 다시 셈
const ORDER = [['', '단타 순'], ['vi', 'VI·급등 → 초반상승 → 시가총액 순']];
const has = (r, c) => (r.chips || []).includes(c) ? 1 : 0;
const ORDER_FN = { vi: (a, b) => has(b, 'VI·급등') - has(a, 'VI·급등') || has(b, '초반상승') - has(a, '초반상승') || (Number(b.cap) || 0) - (Number(a.cap) || 0) };   // last — 날마다 14:00(마지막 시각) 평균 · 날짜 칩에 붙임

// 파는 룰 (11-11 재권님 「매수가 대비 1%이상 하락은 매도한다. 상승추세가 꺾이면 판다 라는룰을 추가해서 표기해줘. 표기된 부분부터는 평균에 포함시키지 않는다」)
//   · 30분 시각마다 본다(값이 30분마다라서) — ① 매수가 대비 STOP_PCT% 이하면 판다 ② 앞 시각에 매수가보다 위였는데 이번 시각이 앞 시각보다 낮으면 「상승추세 꺾임」 으로 판다
//   · 판 시각 칸에 「손절」 · 「꺾임」 을 붙이고, 그 칸부터는 흐리게 · 평균에서 뺀다 · 「결과」 칸 = 판 시각 값(안 팔았으면 마지막 시각 값)
//   · ② 「꺾임」 = 앞 시각보다 낮아지면(재권님 11-11 「낮아지면으로 해」) · 숫자는 룰 문서로 옮길 때까지 이 한 곳
const STOP_PCT = -1;
function sellAt(p) {   // p — 시각마다 매수가 대비 %(null 은 값 없음) → { k: 판 시각 차례 또는 -1, why }
  for (let k = 0; k < p.length; k++) {
    if (p[k] == null) continue;
    if (p[k] <= STOP_PCT) return { k, why: '손절' };
    let a = k - 1; while (a >= 0 && p[a] == null) a--;
    if (a >= 0 && p[a] > 0 && p[k] < p[a]) return { k, why: '꺾임' };
  }
  return { k: -1, why: '' };
}
// 손익 셈 (11-11 재권님 「각 종목별로 천만원씩 샀다고 하고 상위 16종목을 해당룰로 했을때 수익은 얼마지?」 → 「결과 옆에 거래세랑 세금 퍼센트를 넣어줘
//   세금은 코스피와 코스닥세금 내는거 룰찾아서 넣고 증권수수료는 내가 기입하면 그 숫자에 맞춰서 대입되게 해줘」)
//   · 상위 PNL_TOP 종목을 한 종목에 PNL_WON 원어치(주 단위 내림) 09:06 매수가에 사서 위 룰대로 판 값에 판다
//   · 세금은 팔 때만 — 판 금액 × (거래세 + 농어촌특별세) · 시장마다 TAX 표 · 증권수수료는 살 때 · 팔 때 각각 그 금액 × 수수료 %
//   · 수수료 % 는 재권님이 칸에 넣으신 값 — 서버 룰 문서(strategy-rules · rules.dt30.feePct) 한 곳 · 빈칸이면 수수료는 안 셈(「빈칸」 이라 적음 · 0 으로 보지 않음)
//   · 2026 세율(KB증권 「2026년 증권거래세율 변경 안내」 · 머니투데이 2025-12-01 「내년 1월부터 증권거래세 오른다」) — 세율이 바뀌면 TAX 한 곳만 고친다
const PNL_TOP = 16, PNL_WON = 10_000_000;
const TAX = { KOSPI: { tx: 0.05, rural: 0.15 }, KOSDAQ: { tx: 0.20, rural: 0 } };   // % · 코스피 = 거래세 0.05 + 농특세 0.15 · 코스닥 = 거래세 0.20
const MKT = { KOSPI: '코스피', KOSDAQ: '코스닥' };
const won = (x) => (x == null || !Number.isFinite(x) ? '—' : `${x < 0 ? '-' : x > 0 ? '+' : ''}${Math.abs(Math.round(x)).toLocaleString('ko-KR')}원`);
const wonPlain = (x) => (x == null || !Number.isFinite(x) ? '—' : `${Math.round(x).toLocaleString('ko-KR')}원`);
const taxTxt = (r) => { const m = String(r.market || '').toUpperCase(), T = TAX[m]; return T ? `${MKT[m]} ${num(T.tx, 2)}${T.rural ? ` + ${num(T.rural, 2)}` : ''}%` : '<span class="st-err">—</span>'; };
const mean = (v) => (v.length ? v.reduce((a, b) => a + b, 0) / v.length : null);
const sgn = (x) => (x == null ? '—' : `${x > 0 ? '+' : ''}${num(x, 2)}%`);

function paint(d) {
  const times = Array.isArray(d.times) ? d.times : [];
  const all = Array.isArray(d.rows) ? d.rows : [];
  const rows0 = st.only ? all.filter((r) => (r.chips || []).includes(st.only)) : all;   // 거르고 나서 순번 · 상위 16 · 평균을 다시 셈
  const rows = st.order ? [...rows0].sort(ORDER_FN[st.order]) : rows0;   // 줄 세우기를 바꾸면 순번 · 상위 16 을 그 차례로
  const L = times.length - 1;
  $('dt-only').innerHTML = ONLY.map(([k, t]) => `<button type="button" class="kh-chip${st.only === k ? ' is-active' : ''}" data-only="${k}">${t}${k ? ` ${all.filter((r) => (r.chips || []).includes(k)).length}` : ` ${all.length}`}</button>`).join('');
  $('dt-order').innerHTML = ORDER.map(([k, t]) => `<button type="button" class="kh-chip${st.order === k ? ' is-active' : ''}" data-order="${k}">${t}</button>`).join('');
  const ch = (r, t) => { const b = Number(r.buy), v = Number((r.px || {})[t]); return r.buy == null || (r.px || {})[t] == null || !(b > 0) || !Number.isFinite(v) ? null : (v / b - 1) * 100; };
  const R = rows.map((r) => { const p = times.map((t) => ch(r, t)); const s = sellAt(p); let last = L; while (last >= 0 && p[last] == null) last--; const at = s.k >= 0 ? s.k : last, sellPx = at >= 0 ? Number((r.px || {})[times[at]]) : null;
    const b = Number(r.buy), qty = b > 0 ? Math.floor(PNL_WON / b) : 0;
    const T = TAX[String(r.market || '').toUpperCase()] || null;
    const pnl = qty > 0 && Number.isFinite(sellPx) ? (() => {
      const buyAmt = qty * b, sellAmt = qty * sellPx;
      const tx = T ? sellAmt * T.tx / 100 : null, rural = T ? sellAmt * T.rural / 100 : null;
      const fee = st.fee == null ? null : (buyAmt + sellAmt) * st.fee / 100;
      return { buyAmt, sellAmt, gross: sellAmt - buyAmt, tx, rural, fee, net: T ? sellAmt - buyAmt - tx - rural - (fee || 0) : null };
    })() : null;
    return { r, p, s, pnl, res: s.k >= 0 ? p[s.k] : (last >= 0 ? p[last] : null) }; });
  const held = (x, k) => x.s.k < 0 || k < x.s.k;   // 판 시각 칸부터는 평균에서 뺀다
  const avg = times.map((_, k) => mean(R.filter((x) => held(x, k) && x.p[k] != null).map((x) => x.p[k])));
  const res = R.map((x) => x.res).filter((v) => v != null), resAvg = mean(res);
  const sold = R.filter((x) => x.s.k >= 0);
  const top = R.slice(0, PNL_TOP).filter((x) => x.pnl), sum = (k) => top.reduce((a, x) => a + (x.pnl[k] || 0), 0);
  const noMkt = top.filter((x) => x.pnl.net == null).length;   // 시장을 모르는 종목 — 세금을 못 셈
  const P = top.length ? { n: top.length, buy: sum('buyAmt'), sell: sum('sellAmt'), gross: sum('gross'), tx: sum('tx'), rural: sum('rural'), fee: st.fee == null ? null : sum('fee'), net: sum('net') } : null;
  st.last[d.day] = resAvg;
  $('dt-meta').textContent = `${dayTxt(d.day)} · 단타 상위 ${num(rows.length)} · ${d.buyAt ? `${hmTxt(d.buyAt)} 매수` : '매수 시각 —'} · 판 것 ${sold.length}(손절 ${sold.filter((x) => x.s.why === '손절').length} · 꺾임 ${sold.filter((x) => x.s.why === '꺾임').length}) · 끝까지 들고 감 ${R.length - sold.length} · 결과 평균 ${sgn(resAvg)} · 이긴 것 ${res.filter((v) => v > 0).length} · 진 것 ${res.filter((v) => v < 0).length}`;
  $('dt-pnl-sum').innerHTML = P ? `<b>상위 ${P.n}종목 × ${(PNL_WON / 10000).toLocaleString('ko-KR')}만원</b> · 산 ${wonPlain(P.buy)} · 판 ${wonPlain(P.sell)} · 빼기 전 ${won(P.gross)}`
    + ` · 거래세 ${wonPlain(P.tx)} · 농특세 ${wonPlain(P.rural)} · 수수료 ${P.fee == null ? '빈칸 — 안 셈' : wonPlain(P.fee)}`
    + ` · <b>세후 손익 <span class="${signClass(P.net, NUM) || ''}">${won(P.net)}</span> (${pct(P.net / P.buy * 100)})</b>${noMkt ? ` · 시장 모름 ${noMkt}종목은 세후에서 뺌` : ''}` : '— 손익을 셀 값이 없음';
  if (!rows.length) { $('dt-box').innerHTML = '<div class="st-err">— 이 날 굳힌 단타 종목 없음</div>'; return; }
  const cell = (x, k) => {
    const v = x.p[k];
    if (x.s.k >= 0 && k === x.s.k) return `<td class="dt-sold">${pct(v)}<em>${x.s.why}</em></td>`;
    if (x.s.k >= 0 && k > x.s.k) return `<td class="dt-after">${v == null ? '—' : sgn(v)}</td>`;
    return `<td class="${k === L ? 'dt-last' : ''}">${pct(v)}</td>`;
  };
  $('dt-box').innerHTML = `<table class="dt-tb">
    <tr><th class="dt-rk"></th><th class="st-name">종목</th><th>시가총액</th><th class="dt-sec">섹터</th><th class="dt-ev">이벤트</th><th>매수가 ${hmTxt(d.buyAt)}</th><th class="dt-gp" colspan="${times.length}"><span>매수가 대비</span></th><th class="dt-res">결과</th><th class="dt-tx">세금 %</th><th class="dt-pl">손익 · 1천만원</th></tr>
    <tr class="dt-t2"><th class="dt-rk"></th><th class="st-name"></th><th></th><th class="dt-sec"></th><th class="dt-ev"></th><th></th>${times.map((t) => `<th>${hmTxt(t)}</th>`).join('')}<th class="dt-res">판 값 · 시각</th><th class="dt-tx">거래세 · 농특세</th><th class="dt-pl">세금 · 수수료 뺌 · 상위 ${PNL_TOP}</th></tr>
    <tr class="dt-avg"><td class="dt-rk"></td><td class="st-name">평균 <small>판 칸부터 뺌</small></td><td></td><td class="dt-sec"></td><td class="dt-ev"></td><td></td>${avg.map((x, i) => `<td class="${i === L ? 'dt-last' : ''}">${pct(x)}</td>`).join('')}<td class="dt-res">${pct(resAvg)}</td><td class="dt-tx"></td><td class="dt-pl">${P ? won(P.net) : '—'}<small>${P ? `빼기 전 ${won(P.gross)}` : ''}</small></td></tr>
    ${R.map((x, i) => { const r = x.r; return `<tr><td class="dt-rk">${st.only || st.order ? i + 1 : esc(r.rank ?? i + 1)}</td><td class="st-name" data-co="${esc(r.code || '')}"><b>${esc(r.name || '—')}</b> <small>${esc(r.code || '')}</small></td><td>${capTxt(r.cap)}</td><td class="dt-sec">${esc(r.sector || '—')}</td><td class="dt-ev">${evHtml(r.chips)}</td><td class="dt-buy">${num(r.buy)}</td>${times.map((t, k) => cell(x, k)).join('')}<td class="dt-res">${pct(x.res)}<small>${x.s.k >= 0 ? `${hmTxt(times[x.s.k])} ${x.s.why}` : '끝까지'}</small></td><td class="dt-tx">${taxTxt(x.r)}</td><td class="dt-pl">${i < PNL_TOP && x.pnl ? (x.pnl.net == null ? '<span class="st-err">시장 모름</span>' : `<span class="${signClass(x.pnl.net, NUM) || ''}">${won(x.pnl.net)}</span><small>빼기 전 ${won(x.pnl.gross)}</small>`) : '<span class="st-err">—</span>'}</td></tr>`; }).join('')}
  </table>`;
}

function chips() {
  $('dt-days').innerHTML = st.days.length
    ? st.days.map((d) => { const a = st.last[d]; return `<button type="button" class="kh-chip${d === st.day ? ' is-active' : ''}" role="tab" aria-selected="${d === st.day}" data-day="${d}">${dayTxt(d)}${a == null ? '' : `<small class="${signClass(a, NUM) || ''}">${a > 0 ? '+' : ''}${num(a, 1)}%</small>`}</button>`; }).join('')
    : '';
}
$('dt-days').addEventListener('click', (e) => { const b = e.target.closest('[data-day]'); if (b && b.dataset.day !== st.day) load(b.dataset.day); });

async function load(day) {
  const my = ++st.seq;
  $('dt-meta').textContent = '값을 받는 중…';
  let r = null, j = null;
  try { r = await fetch(day ? `${API}?day=${day}` : API, { cache: 'no-store' }); j = await r.json().catch(() => null); } catch (e) { r = null; }
  if (my !== st.seq) return;
  if (!r || !r.ok || !j || j.ok === false || !j.data) {
    const why = !r ? '연결 안 됨' : r.status === 404 ? '서버가 아직 단타 30 을 쌓지 않음' : (j && j.error) || `서버 ${r.status}`;
    $('dt-meta').textContent = `— 단타 30 값을 못 받음: ${why}`;
    $('dt-box').innerHTML = `<div class="st-err">— ${esc(why)}</div>`;
    return;
  }
  const d = j.data, m = j.meta || {};
  st.days = (Array.isArray(m.days) ? m.days : [d.day]).slice(0, 30);   // 30거래일 — 그 밖은 서버가 지우고 화면도 30 까지만
  st.day = d.day; st.data = d;
  paint(d);
  chips();
}

$('dt-order').addEventListener('click', (e) => { const b = e.target.closest('[data-order]'); if (!b || b.dataset.order === st.order) return; st.order = b.dataset.order; if (st.data) { paint(st.data); chips(); } });
$('dt-only').addEventListener('click', (e) => { const b = e.target.closest('[data-only]'); if (!b || b.dataset.only === st.only) return; st.only = b.dataset.only; if (st.data) { paint(st.data); chips(); } });

async function loadFee() {
  try { const r = await fetch(DOC, { cache: 'no-store' }); const j = r.ok ? await r.json() : null; const v = j && j.data && j.data.rules && j.data.rules.dt30 ? j.data.rules.dt30.feePct : null; st.fee = v == null || v === '' ? null : Number(v); }
  catch (e) { st.fee = null; }
  $('dt-fee').value = st.fee == null ? '' : String(st.fee);
}
async function saveFee() {
  const el = $('dt-fee'), raw = el.value.trim(), v = raw === '' ? null : Number(raw);
  if (v != null && (!Number.isFinite(v) || v < 0)) { $('dt-fee-msg').textContent = '0 이상 숫자만 — 되돌렸습니다'; el.value = st.fee == null ? '' : String(st.fee); return; }
  $('dt-fee-msg').textContent = '저장하는 중…';
  for (let n = 0; n < 2; n++) {   // 그 사이 다른 칸(종목 고르는 룰)이 고쳐졌으면 다시 읽고 한 번 더
    try {
      const g = await fetch(DOC, { cache: 'no-store' }); const j = g.ok ? await g.json() : null;
      const doc = (j && j.data && typeof j.data === 'object') ? j.data : { rules: {} }; const at = j ? (j.updatedAt ?? (j.data && j.data.updatedAt)) : null;
      doc.rules = doc.rules || {}; doc.rules.dt30 = { ...(doc.rules.dt30 || {}), feePct: v };
      const r = await fetch(DOC, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ data: doc, ...(at ? { updatedAt: at } : {}) }) });
      if (r.status === 409) continue;
      if (!r.ok) throw new Error(String(r.status));
      st.fee = v; $('dt-fee-msg').textContent = v == null ? '빈칸 — 수수료 안 셈' : '저장됨 — 다시 셈';
      if (st.data) paint(st.data);
      return;
    } catch (e) { $('dt-fee-msg').textContent = `저장 못 함(${e.message || '연결 안 됨'})`; return; }
  }
  $('dt-fee-msg').textContent = '저장 못 함 — 다른 곳에서 계속 고치는 중';
}
$('dt-fee').addEventListener('change', saveFee);

loadFee().then(load);
