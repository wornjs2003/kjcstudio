// 투자 전략 「종목 고르는 룰」 — 홀딩스 실시간 순위 「관심」 아래 칩 여덟의 룰 (2026-11-11 · 시황분석1)
//   · 재권님 「strategy.html 여기에 실시간순위에 관심이라고 있는데 거기에 하위의 버튼별로 룰 정리해주고 그거 수정 가능하도록」(16:3x · 작업우선순위 경유) →
//     「우선 비밀번호는 나중에 하고 … 이미지부터」 → 시안 temp/시황분석1-rules3 「이런거고 지금 관심 하위의 버튼별로 있는 룰 여기에 다 넣어줘야해」 → 「응 시작해」
//   · 칩 차례는 홀딩스 「관심」 아래 줄 그대로(home.js FAV_SUB_ORDER) + 수급. 수급 = 지금까지의 「전일 거래량 급등」 룰(js/strategy-rule.js 가 그대로 그린다)
//   · 나머지 일곱은 지금은 보기만 — 고치기는 수정 비밀번호와 함께 뒤에(재권님 「우선 비밀번호는 나중에」)
//   · 룰 숫자는 그 칩을 내는 서버 응답의 meta 를 그대로 쓴다(화면에 박지 않는다) · 서버가 안 주는 숫자(홀딩스 화면 코드에만 있는 것)는 — 로 두고 그렇다고 적는다
//     (그 값을 룰 문서로 옮기는 것은 개발1 카드 「서버 칩 룰이 룰 문서 값을 읽게」)
//   · 종목은 홀딩스와 같은 서버 주소 — 목록 주소가 없는 칩(단타 · 현재상승 · 장외 — 홀딩스 화면이 순위 목록에서 셈)은 —
import { signClass, NUM } from '/assets/js/sign.js';
import { watch } from '/holdings/js/store/longpoll.js';   // 오늘 칩 목록 다시 받기 — 홀딩스 첫 화면과 같은 길(서버 롱폴 · 서버 주기)
import { chipName } from './strategy-chipname.js';
import { COND } from './strategy-chipinfo.js';   // 칩 고르는 조건 글 한 곳 — 단타 판 칩 풍선과 같은 글(11-20 재권님 「응」)   // 서버 칩 이름 「수급」 → 화면 「자동」 — 바꾸는 표는 그 파일 한 곳
import { setDtScore, dtChips, VI_SUBS, subName } from './strategy-dt30.js';   // 조건별 점수 — 단타 판과 같은 룰 문서 · 같은 저장 길 · 하위 이름 · 보이는 이름(매수 ①~④ → 사는 쪽)도 그 파일 한 곳

const $ = (id) => document.getElementById(id);
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (x, d = 0) => (x == null || !Number.isFinite(Number(x)) ? '—' : Number(x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (x) => { if (x == null || !Number.isFinite(Number(x))) return '—'; const c = signClass(Number(x), NUM); const t = `${x > 0 ? '+' : ''}${num(x, 2)}%`; return c ? `<span class="${c}">${t}</span>` : t; };
const v = (x) => `<b class="rl-v">${x == null || x === '' ? '—' : esc(x)}</b>`;   // 룰 값 — 진한 칸(나중에 고칠 자리)
const eok = (won) => { if (won == null || !Number.isFinite(Number(won))) return '—'; const e = Number(won) / 1e8; return `${num(e, Math.abs(e) < 10 ? 1 : 0)}억`; };   // 10억 아래는 소수 한 자리 — 「-0억」 이 안 나오게
const capTxt = (e) => (e == null ? '—' : `${num(e)}억`);
const MKT = { KOSPI: '코스피', KOSDAQ: '코스닥' };
const HOLD = '<span class="rl-sug">숫자는 홀딩스 화면 코드에만 있음 — 룰 문서로 옮기면 여기 나옴</span>';
const CAPROW = ['시가총액', `${v(null)} 이상 ${HOLD}`];

async function getJson(u) {
  try { const r = await fetch(u, { cache: 'no-store' }); return { st: r.status, j: r.ok ? await r.json() : null }; }
  catch (e) { return { st: 0, j: null }; }
}
// 볼린저 줄 시각 — 그날(day) 것이 아니면 날짜를 붙인다(장 뒤 신호가 다음 날 목록에 남는 때 · ts = YYYYMMDDHHMM)
const bbWhen = (x, day) => { const t = String(x.ts || ''); return t.length >= 12 && day && t.slice(0, 8) !== day ? `${t.slice(4, 6)}-${t.slice(6, 8)} ${t.slice(8, 10)}:${t.slice(10, 12)}` : (x.t || '—'); };
const tb = (head, rows) => `<div class="st-scroll"><table class="aw-tb"><tr>${head.map((h) => `<th>${h}</th>`).join('')}</tr>${rows.join('')}</table></div>`;
const nm = (x) => `<td class="st-name"><b>${esc(x.name || '—')}</b> <small>${esc(x.code || '')}</small></td>`;

// 칩마다 — 이름 · 받을 주소(없으면 null) · 룰 줄(meta → [[머리, 글]]) · 목록(응답 → { cap, html })
const RULES = {
  ov: {
    // 목록은 서버 단타 목록 한 곳(/api/kis/dt-list · 홈 「단타」 와 같은 주소 · 지금 값) — 11-18 재권님 「둘이 동기화해서 홈이든 단테든 한곳에 있어야 하는 정본데」 → 「응 이거 바로 해야할거같아」
    //   서버는 칩 하나 이상 줄을 다 주고 문턱은 meta.minChips(서버 한 곳) — 화면은 n ≥ minChips · 하락(down) 아닌 줄만 보임(값을 화면에 안 둠)
    //   그 주소가 아직 없는 서버(합치기 전)에서는 단타 판(/api/kis/dt30 · 그날 판)으로 — 문턱이 없으면 줄을 다 보임
    name: '단타', url: '/api/kis/dt-list', alt: '/api/kis/dt30', metaOf: (j) => ({ ...(j.meta || {}), ...((j.data && j.data.meta) || {}) }),
    rows: (m) => [['고르는 조건', `아래 칩 중 ${v(m.minChips == null ? null : num(m.minChips))}개 이상에 든 종목 · 하락 뺌 — 홈 「단타」 와 같은 서버 목록<br>세는 칩 — ${esc((m.chips || []).map(chipName).join(' · ') || '—')} <span class="rl-sug">장외는 장 뒤에만 셈${m.wait && m.wait.length ? ` · 정규장 전에는 ${esc(m.wait.join(' · '))} 기다림` : ''}</span>`],
      ['시가총액', `${v(m.capMinEok == null ? null : num(m.capMinEok))}억원 이상(관심 · 프리장 · 매수) · 나머지는 칩마다의 문턱`], ['줄 세우기', esc(m.order || '겹친 칩 수 많은 순 → 초반상승 높은 순 → 시가총액 순')]],
    list: (j) => {
      const m = { ...(j.meta || {}), ...((j.data && j.data.meta) || {}) }, all = Array.isArray(j.data) ? j.data : (j.data && Array.isArray(j.data.rows) ? j.data.rows : []);
      const k = Number(m.minChips), d = all.filter((x) => !x.down && (!(k > 0) || x.n >= k));
      const chipTxt = (x) => (x.chips || []).map(chipName).join(' · ');
      return { cap: `${Array.isArray(j.data) ? `지금 ${esc(m.at || '—')}` : '그날 단타 판'} · ${num(d.length)}종목${k > 0 ? ` · 칩 ${num(k)}개 이상 · 후보 ${num(all.length)}` : ' · 문턱 없음(서버 단타 목록 전 — 그날 판 전부)'}`,
        html: d.length ? tb(['종목', '겹친 칩', '칩', '등락률(전일 종가 대비)', '시가총액'], d.map((x) => `<tr>${nm(x)}<td><b>${num(x.n)}</b></td><td>${esc(chipTxt(x))}</td><td>${pct(x.pct)}</td><td>${capTxt(x.cap)}</td></tr>`)) : null };
    },
  },
  // 거래 칩 둘(11-23 개발2 fece17c · 재권님 「두개야 / 전일대비 현시점거래비율 이랑 유통주식대비 현시점 거래비율」) — 목록은 서버 /api/kis/vol-chip 한 곳(단타 판 칩과 같은 셈) · 문턱은 아래 「고치는 값」 칸
  turn: {
    name: '현시간 유통회전', url: '/api/kis/vol-chip',
    rows: (m) => [['고르는 조건', `거래 비율(오늘 누적 거래대금 ÷ 풀린 시가총액 × 100)이 ${v(m.turnPct)}% 이상인 종목 · ETF 뺌`], ['시가총액', `${v(m.capMinEok == null ? null : num(m.capMinEok))}억원 이상`], ['줄 세우기', '등락률 큰 순']],
    list: (j) => volList(j, '현시간 유통회전', (x) => x.turn != null && Number(x.turn) >= Number((j.meta || {}).turnPct)),
  },
  turnup: {
    name: '전일 현시간 대비 급증', url: '/api/kis/vol-chip',
    rows: (m) => [['고르는 조건', `거래 비율이 전날 같은 시각보다 ${v(m.turnPrevPct ?? m.prevSamePct)}% 이상인 종목(전날 같은 시각 거래 비율 = 100%) · ETF 뺌`], ['시가총액', `${v(m.capMinEok == null ? null : num(m.capMinEok))}억원 이상`], ['줄 세우기', '등락률 큰 순']],
    list: (j) => volList(j, '전일 현시간 대비 급증', (x) => (x.by || []).includes('prev')),
  },
  // 돈몰림(11-25 개발2 0fd1035 · 재권님 「돈이 몰리는 섹터나 테마에 속한 종목들 단타에 칩하나」 → (가) → 「시간과 배수는 ()로 빼서 내가 조절하게」) — 셈은 서버 섹터수급 5분 칸 · 문턱은 서버 칩 룰 한 곳
  //   목록은 서버 단타 목록(/api/kis/dt-list)에서 그 칩이 붙은 줄 · 걸린 묶음은 서버 subs.돈몰림 그대로 · 고치는 값은 시간 · 배수 둘(재권님 지시 온 칸)
  money: {
    name: '돈몰림', url: '/api/kis/dt-list', alt: '/api/kis/dt30', metaOf: (j) => ({ ...(j.meta || {}), ...((j.data && j.data.meta) || {}) }),
    rows: () => { const c = (k) => { const x = (crCache || []).find((y) => y.chip === '돈몰림' && y.key === k); return x ? num(x.value, Number(x.value) % 1 ? 1 : 0) : null; };
      return [['고르는 조건', `업종 · 테마 묶음의 최근 ${v(c('winMin'))}분 거래대금이 전날 같은 때의 ${v(c('mult'))}배 이상 · 그 시간 대금 ${v(c('minEok'))}억 이상 · 정규장은 산 금액 비중 ${v(c('buyShare'))}% 이상(프리장은 그 사이 묶음 등락 오름)인지 5분 칸마다 셈해 최근 ${v(c('holdMin'))}분 동안 맞은 칸이 안 맞은 칸보다 많으면 그 묶음의 종목에 붙임(다수결) · 아니면 뗌`],   // 다수결 — 개발2 78f9178 · 재권님 「응 해」(11-25 15:0x) · 창 길이 holdMin 은 서버 칩 룰 한 곳
        ['값', '서버 섹터수급(업종 · 테마 5분 칸) — 매수 · 매도는 체결강도로 나눈 어림 · 정규장만'], ['장 전', '셈 안 함']]; },
    list: (j) => {
      const all = Array.isArray(j.data) ? j.data : (j.data && Array.isArray(j.data.rows) ? j.data.rows : []), d = all.filter((x) => (x.chips || []).includes('돈몰림'));
      const grp = (x) => ((x.subs || {})['돈몰림'] || []).join(' · ') || '—';
      return { cap: `${Array.isArray(j.data) ? '지금' : '그날 단타 판'} · 돈몰림 칩이 붙은 ${num(d.length)}종목`,
        html: d.length ? tb(['종목', '걸린 묶음', '등락률(전일 종가 대비)', '시가총액'], d.map((x) => `<tr>${nm(x)}<td>${esc(grp(x))}</td><td>${pct(x.pct)}</td><td>${capTxt(x.cap)}</td></tr>`)) : null };
    },
  },
  // 미국강세(11-25 개발2 d0ecebb · 재권님 「미국장 상승 섹터나 테마에 속한 종목은 단타에 칩하나」) — 어제 미국 오른 묶음 상위 ( ) 의 국내 짝(서버 us-kr-groups · 짝 표는 서버 한 곳) · 문턱은 서버 칩 룰
  usup: {
    name: '미국강세', url: '/api/kis/dt-list', alt: '/api/kis/dt30', metaOf: (j) => ({ ...(j.meta || {}), ...((j.data && j.data.meta) || {}) }),
    rows: () => { const x = (crCache || []).find((y) => y.chip === '미국강세' && y.key === 'topN');
      return [['고르는 조건', `어제 미국장에서 오른 섹터 · 테마 묶음 중 등락 상위 ${v(x ? num(x.value) : null)}개의 국내 짝 업종 · 테마에 속한 종목`], ['값', '서버 「미국 → 다음 날 국내」 칸과 같은 값(us-kr-groups) — 짝 표는 서버 한 곳'], ['장 전', '붙음(어제 미국 값이라)']]; },
    list: (j) => {
      const all = Array.isArray(j.data) ? j.data : (j.data && Array.isArray(j.data.rows) ? j.data.rows : []), d = all.filter((x) => (x.chips || []).includes('미국강세'));
      const grp = (x) => ((x.subs || {})['미국강세'] || []).join(' · ') || '—';
      return { cap: `${Array.isArray(j.data) ? '지금' : '그날 단타 판'} · 미국강세 칩이 붙은 ${num(d.length)}종목`,
        html: d.length ? tb(['종목', '걸린 묶음', '등락률(전일 종가 대비)', '시가총액'], d.map((x) => `<tr>${nm(x)}<td>${esc(grp(x))}</td><td>${pct(x.pct)}</td><td>${capTxt(x.cap)}</td></tr>`)) : null };
    },
  },
  // 관심 탭은 뺐다(11-12 재권님 「관심을 없애고 수급으로 대처한다」) — 같은 종목 · 같은 룰이 「자동(전일 거래량 급등)」 칩에 있다(11-18 「수급」 에서 바꿈 · 실시간 순위 이름)
  pre: {
    name: '프리장', url: '/api/kis/pre-flow',
    rows: (m) => [['고르는 조건', COND.프리장(m, v)],
      ['시간', `${v(m.preOpen)} ~ ${v(m.preClose)} · 그 뒤 09:00 전까지 그날 판으로 굳힘`], CAPROW, ['줄 세우기', '등락률 큰 순(고르기는 거래대금 순)']],
    list: (j) => {
      const d = Array.isArray(j.data) ? j.data : [], m = j.meta || {};
      return { cap: `${esc(m.day ? `${m.day.slice(4, 6)}-${m.day.slice(6)}` : '—')} 프리장 · ${num(d.length)}종목${m.builtAt ? ` · ${esc(m.builtAt)} 굳힘` : ''}`,
        html: d.length ? tb(['종목', '등락률', '거래대금', '프로그램 순매수'], d.map((x) => `<tr>${nm(x)}<td>${pct(x.pct)}</td><td>${eok(x.amt)}</td><td><b>${eok(x.program)}</b></td></tr>`)) : null };
    },
  },
  rise: {
    name: '초반상승', url: '/api/kis/open-rise',
    rows: (m) => [['고르는 조건', COND.초반상승(m, v)],   // 「장 시작 몇 분 뒤」 — 11-20 재권님 「단타에 초반상승이 장시작 몇분후인지 설명에 넣어줘」 · 값은 서버 meta.barMin 그대로
      ['시가총액', `${v(m.minCapEok == null ? null : num(m.minCapEok))}억원 이상`], ['줄 세우기', '첫 봉 상승률 큰 순 · 그날 판으로 굳힘']],
    list: (j) => {
      const d = Array.isArray(j.data) ? j.data : [], m = j.meta || {};
      return { cap: `${esc(m.day ? `${m.day.slice(4, 6)}-${m.day.slice(6)}` : '—')} 첫 봉 · ${num(d.length)}종목 · 살핀 ${num(m.candidates)}(ETF 뺌 ${num(m.etfOut)})`,
        html: d.length ? tb(['종목', '시장', '시가 → 첫 봉 종가', '첫 봉 상승률', '시가총액'], d.map((x) => `<tr>${nm(x)}<td>${esc(MKT[x.market] || x.market || '—')}</td><td>${num(x.open)} → ${num(x.close)}</td><td><b>${pct(x.pct)}</b></td><td>${capTxt(x.cap)}</td></tr>`)) : null };
    },
  },
  nowup: {
    name: '현재상승', url: null,
    rows: () => [['고르는 조건', `지금 값이 오늘 시가보다 ${v(null)}% 이상 높은 종목 ${HOLD}`], CAPROW, ['줄 세우기', '시가 대비 큰 순']],
  },
  vi: {
    name: 'VI·급등', url: '/api/alerts/today',
    rows: (m) => [['고르는 조건', `정규장(${v(m.session)})에 상승 VI 가 걸렸거나 전일 대비 ${v(m.surgePct)}% 이상 오른 종목`], CAPROW, ['줄 세우기', '최근 것이 위']],
    list: (j) => {
      const d = (j.data && Array.isArray(j.data.items)) ? j.data.items : [];
      const seen = new Set(), rows = [...d].sort((a, b) => String(b.t).localeCompare(String(a.t))).filter((x) => !seen.has(x.code) && seen.add(x.code));   // 한 종목은 가장 최근 한 줄
      return { cap: `${esc(j.data && j.data.day ? `${j.data.day.slice(4, 6)}-${j.data.day.slice(6)}` : '—')} · ${num(rows.length)}종목 · 시가총액 문턱 거르기 전 전부(문턱은 홀딩스 화면이 거름)`,
        html: rows.length ? tb(['종목', '시각', '무엇', '등락률', '시가총액'], rows.map((x) => `<tr>${nm(x)}<td>${esc(String(x.t || '').slice(0, 5) || '—')}</td><td>${x.kind === 'surge' ? '급등' : `VI ${esc(x.sub || '')}`}</td><td>${pct(x.pct)}</td><td>${capTxt(x.cap)}</td></tr>`)) : null };
    },
  },
  bb: {
    name: '볼린저', url: '/api/signals/today',
    rows: (m) => [['고르는 조건', `같은 ${v(m.period == null ? null : String(m.period).replace(/^(\d+)m$/, '$1분'))} 봉에서 셋이 함께 —<br>① 저가가 볼린저 하단(${v(m.bb)})에 닿고 양봉<br>② MACD 히스토그램이 음수인데 직전보다 커짐<br>③ RSI 가 ${v(m.rsi)} 아래에서 오르기 시작`],
      CAPROW, ['줄 세우기', '최근 것이 위 · 텔레그램 「바닥 신호」 와 같은 기록']],
    list: (j) => {
      const d = (j.data && Array.isArray(j.data.items)) ? [...j.data.items].sort((a, b) => String(b.ts || b.t).localeCompare(String(a.ts || a.t))) : [];
      return { cap: `${esc(j.data && j.data.day ? `${j.data.day.slice(4, 6)}-${j.data.day.slice(6)}` : '—')} · ${num(d.length)}번 · 시가총액 문턱 거르기 전 전부(문턱은 홀딩스 화면이 거름)`,
        html: d.length ? tb(['종목', '시각', '그 봉 종가', '저가', '시가총액'], d.map((x) => `<tr>${nm(x)}<td>${esc(bbWhen(x, j.data.day))}</td><td>${num(x.close)}</td><td>${num(x.low)}</td><td>${capTxt(x.cap)}</td></tr>`)) : null };
    },
  },
  after: {
    name: '장외', url: null,
    rows: () => [['고르는 조건', `${COND.장외()}<br><span class="rl-sug">평일 09:00 ~ 15:40 은 비어 있음</span>`], CAPROW, ['줄 세우기', '종가 대비 등락률 순']],
  },
};

// 거래 칩 목록 — 서버 rows[].chips 에 그 칩 이름이 있으면 그것으로 · 칩 이름이 없는 옛 서버 응답은 by 로(서버를 합치는 사이 · 열쇠 셈은 서버 한 곳)
function volList(j, chip, old) {
  const all = Array.isArray(j.data) ? j.data : [], m = j.meta || {};
  const d = all.filter((x) => (Array.isArray(x.chips) ? x.chips.map(chipName).includes(chip) : old(x)));
  const prevOf = (x) => x.turnPrevPct ?? x.prevSamePct;
  return { cap: `지금 ${esc(m.at || '—')} · ${num(d.length)}종목 · 살핀 ${num(m.candidates)}(ETF 뺌 ${num(m.etfOut)})`,
    html: d.length ? tb(['종목', '거래 비율', '전날 같은 시각 대비', '등락률(전일 종가 대비)', '풀린 시총'], d.map((x) => `<tr>${nm(x)}<td><b>${x.turn == null ? '—' : `${num(x.turn, 2)}%`}</b></td><td>${prevOf(x) == null ? '—' : `${num(prevOf(x))}%`}</td><td>${pct(x.pct)}</td><td>${capTxt(x.floatCap)}</td></tr>`)) : null };
}

// 고치는 값 (11-23 재권님 「초반급상승에 들어간 2가지 룰 수정할수있는 ()%는 아직 안만들었나?」 · 「유통주식대비 현재거래대금 비교와 전날대비 현시간 거래대금 비교 룰이 어디에 들어가지?」)
//   · 문턱은 서버 칩 룰 한 곳(/api/kis/chip-rules — 값 · 기본 · 범위 · 룰 문서 자리 docPath) · 넣은 값은 그 자리(rules.chips.<칩>.<열쇠>)에 저장 → 서버가 다음 셈부터 씀
//   · 빈칸으로 두면 넣은 값을 지워 서버 기본으로 · 범위 밖은 되돌림 · 칸은 이 칩들만(지시 온 자리)
const EDIT = { rise: ['초반상승'], turn: ['현시간 유통회전'], turnup: ['전일 현시간 대비 급증'], money: ['돈몰림'], usup: ['미국강세'] };
const EDIT_KEYS = { money: ['winMin', 'mult', 'holdMin'] };   // 칩 중 고치는 칸만 — 돈몰림은 시간 · 배수 둘(재권님 「시간과 배수는 ()로 빼서」 11-25) · 나머지는 서버 기본   // 화면 이름(chipName 을 거쳐 견줌)
let crCache = null, crMsg = '';   // crMsg — 저장 알림 글 · 칸을 다시 그려도 남게(qa 11-23)
async function crLoad() { const { j } = await getJson('/api/kis/chip-rules'); crCache = j && j.ok && Array.isArray(j.data) ? j.data : null; return crCache; }
const crRow = (id) => {
  const cs = EDIT[id]; if (!cs) return null;
  if (!crCache) return ['고치는 값', '<span class="st-err">— 서버 칩 룰을 못 받음</span>'];
  const xs = crCache.filter((x) => cs.includes(chipName(x.chip)) && x.docPath && x.unit !== '목록' && (!EDIT_KEYS[id] || EDIT_KEYS[id].includes(x.key)));
  if (!xs.length) return ['고치는 값', '<span class="st-err">— 서버 칩 룰에 이 칩 칸이 없음(서버를 합치기 전)</span>'];
  return ['고치는 값', `<span class="rl-cr">${xs.map((x) => `<label class="dt-fee">${esc(x.name)} <input data-cr="${esc(x.docPath)}" data-lo="${esc((x.range || [])[0] ?? '')}" data-hi="${esc((x.range || [])[1] ?? '')}" class="rl-in rl-num" inputmode="decimal" placeholder="( )" value="${x.source === 'default' ? '' : esc(x.value)}" aria-label="${esc(x.name)}">${esc(x.unit || '')} <span class="rl-sug">${x.source === 'default' ? `빈칸 = 서버 기본 ${esc(num(x.default, 2).replace(/\.?0+$/, ''))}${esc(x.unit || '')}` : `기본 ${esc(num(x.default, 2).replace(/\.?0+$/, ''))}${esc(x.unit || '')}`}</span></label>`).join(' ')} <span id="rl-cr-msg" class="rl-sug">${esc(crMsg)}</span></span>`];
};
async function crSave(path, val) {
  const keys = path.split('.');
  for (let n = 0; n < 2; n++) {
    const g = await fetch(DOC, { cache: 'no-store' });
    if (!g.ok && g.status !== 404) throw new Error(`문서를 못 읽어 저장 안 함 · ${g.status}`);   // 못 읽으면 쓰지 않는다 — 빈 문서로 덮으면 다른 룰 값이 사라짐(qa 11-11)
    const j = g.ok ? await g.json().catch(() => null) : null;
    if (g.ok && !(j && j.data && typeof j.data === 'object')) throw new Error('문서를 못 읽어 저장 안 함');
    const doc = g.ok ? j.data : {}, at = g.ok ? (j.updatedAt ?? j.data.updatedAt ?? null) : null;
    let o = doc; keys.slice(0, -1).forEach((k) => { o[k] = o[k] && typeof o[k] === 'object' ? o[k] : {}; o = o[k]; });
    if (val == null) delete o[keys[keys.length - 1]]; else o[keys[keys.length - 1]] = val;
    const r = await fetch(DOC, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ data: doc, ...(at ? { updatedAt: at } : {}) }) });
    if (r.status === 409) continue;
    if (!r.ok) throw new Error(String(r.status));
    return;
  }
  throw new Error('다른 곳에서 계속 고치는 중');
}

// ── 칩 바꾸기 — 수급(volsurge)은 strategy-rule.js 의 칸 그대로 · 나머지는 같은 자리에 갈아 끼운다(칸 높이는 CSS 가 같게 잡는다)
const chips = [...document.querySelectorAll('#rl-chips [data-rule]')];
const tb1 = $('rl-tb'), tb2 = $('rl-tb2'), title = $('rl-title'), go = $('rl-go');
const awH = document.querySelector('h3.aw-tabs[role="tablist"]'), crH = $('cr-h'), how = $('aw-how');
const panes = [...document.querySelectorAll('.aw-pane')], crPane = document.querySelector('.aw-pane[data-pane="chip"]');
let seq = 0, cur = '';

async function show(id, again = false) {
  chips.forEach((c) => { const on = c.dataset.rule === id; c.classList.toggle('is-active', on); c.setAttribute('aria-selected', on ? 'true' : 'false'); });
  const vol = id === 'volsurge';
  tb1.hidden = !vol; tb2.hidden = vol; if ($('rl-score') && id !== 'ov') $('rl-score').hidden = true; go.hidden = !vol; awH.hidden = !vol; crH.hidden = vol;
  how.style.visibility = vol ? '' : 'hidden';   // 「이 룰은 이렇게 셈합니다」 는 수급 것 — 자리는 남겨 칩을 바꿔도 판 높이 그대로(「보는 것을 바꿔도 자리는 그대로다」)
  if (vol) {
    title.textContent = '룰 — 전일 거래량 급등';
    (document.querySelector('.aw-tab.is-on') || document.querySelector('.aw-tab'))?.click();   // 현재 · 어제 판을 고르던 그대로 되살림
    return;
  }
  cur = id;
  const R = RULES[id], my = ++seq;
  panes.forEach((p) => { p.hidden = p !== crPane; });
  title.textContent = `룰 — ${R.name}`;
  if (EDIT[id] && !crCache) await crLoad();
  if (my !== seq) return;
  const rowsOf = (m, ex) => [...R.rows(m, ex), ...(crRow(id) ? [crRow(id)] : [])];
  if (!again) tb2.innerHTML = rowsOf({}, null).map(([h, t]) => `<tr><th>${h}</th><td>${t}</td></tr>`).join('');   // 다시 받을 때(again)는 빈 값으로 먼저 그리지 않음 — 조건 줄이 「—」 로 깜빡이고 저장 알림 글이 지워졌음(qa 11-23)
  if (!R.url) { $('cr-cap').textContent = `「${R.name}」 종목`; $('cr').innerHTML = '<div class="st-err">— 서버에 이 칩의 종목 목록 주소가 없음(홀딩스 화면이 순위 목록에서 셈)</div>'; return; }
  if (!again) { $('cr-cap').textContent = '값을 받는 중…'; $('cr').innerHTML = '<div class="st-err">—</div>'; }
  let [{ st, j }, ex] = await Promise.all([getJson(R.url), R.extra ? getJson(R.extra) : Promise.resolve({ j: null })]);
  if ((!j || j.ok === false) && R.alt) ({ st, j } = await getJson(R.alt));   // 그 주소가 아직 없는 서버 — 옛 주소로
  if (my !== seq) return;
  if (!j || j.ok === false) { $('cr-cap').textContent = `「${R.name}」 종목`; $('cr').innerHTML = `<div class="st-err">— 서버 값을 못 받음(${esc((j && j.error) || st || '연결 안 됨')})</div>`; return; }
  const m = (R.metaOf ? R.metaOf(j) : null) || j.meta || (j.data && j.data.meta) || {};
  if (!tb2.contains(document.activeElement)) tb2.innerHTML = rowsOf(m, ex.j).map(([h, t]) => `<tr><th>${h}</th><td>${t}</td></tr>`).join('');   // 치는 중이면 다시 그리지 않음
  if (id === 'ov') scoreShow(m); else if ($('rl-score')) $('rl-score').hidden = true;
  const L = R.list(j, ex.j);
  $('cr-cap').textContent = L.cap.replace(/<[^>]+>/g, '');
  $('cr').innerHTML = L.html || '<div class="st-err">— 이 룰에 걸린 종목 없음</div>';
}
chips.forEach((c) => c.addEventListener('click', () => { crMsg = ''; show(c.dataset.rule); }));   // 다른 탭으로 가면 알림 글을 비움
tb2.addEventListener('change', async (e) => {
  const el = e.target.closest('[data-cr]'); if (!el) return;
  const say = (t) => { crMsg = t; const m = $('rl-cr-msg'); if (m) m.textContent = t; };
  const raw = el.value.trim(), val = raw === '' ? null : Number(raw), lo = Number(el.dataset.lo), hi = Number(el.dataset.hi);
  if (val != null && (!Number.isFinite(val) || (el.dataset.lo !== '' && val < lo) || (el.dataset.hi !== '' && val > hi))) { say(`${el.dataset.lo} ~ ${el.dataset.hi} 사이 숫자 · 빈칸 = 서버 기본 — 되돌렸습니다`); crLoad().then(() => show(cur, true)); return; }
  say('저장하는 중…');
  try { await crSave(el.dataset.cr, val); await crLoad(); say('저장됨 — 서버가 다음 셈부터 씀'); el.blur(); show(cur, true); }
  catch (err) { say(`저장 못 함(${err.message || '연결 안 됨'})`); }
});

// 조건별 점수 (11-18 재권님 「여기도 내가 조건들 넣을수 있게 해줘. 있는조건이면 고르면 되고 조건별로 점수를 매겨서 우선순위 정할거야」 → 홈 「단타」 도 같은 차례 「응」)
//   · 「룰 — 단타」 칸 아래 · 있는 조건(서버 meta.chips + VI·급등 09:25 전 · 이후)을 골라 점수를 넣음 · 표는 룰 문서 rules.dt30.score 한 곳(단타 판 · 서버가 같은 표를 읽음)
//   · 칸은 한 번 만들고 값만 바꿈(치는 도중 다시 그려 글자가 사라지지 않게) · 표가 비면 줄 세우기는 지금 셈(겹친 칩 수)
const DOC = '/api/board/doc/strategy-rules';
const VI_SUB = VI_SUBS.slice(0, 2);   // 「시각 모름」 은 점수 조건이 아님
let score = {}, conds = [];
const condTxt = (k) => { const [c, x] = k.split('|'); return x == null ? k : `${c} ${subName(c, x)}`; };   // 열쇠는 그대로 · 글자만(11-19 개념정의 덧)
async function scoreLoad() { const { j } = await getJson(DOC); const S = j && j.data && j.data.rules && j.data.rules.dt30 && j.data.rules.dt30.score; score = S && typeof S === 'object' ? { ...S } : {}; }
function scoreBox() {
  let b = $('rl-score'); if (b) return b;
  b = document.createElement('div'); b.id = 'rl-score'; b.className = 'rl-score'; tb2.after(b);
  b.addEventListener('change', async (e) => {
    const el = e.target; if (!el.matches('[data-k], [data-new]')) return;
    const n = { ...score };
    if (el.dataset.new != null) { if (!el.value) return; n[el.value] = 1; }
    else { const v = el.value.trim() === '' ? null : Number(el.value); if (v != null && !Number.isFinite(v)) { scorePaint(); return; } if (v == null) delete n[el.dataset.k]; else n[el.dataset.k] = v; }
    await scoreSave(n);
  });
  b.addEventListener('click', async (e) => { const x = e.target.closest('[data-del]'); if (!x) return; const n = { ...score }; delete n[x.dataset.del]; await scoreSave(n); });
  return b;
}
async function scoreSave(n) {
  score = n; scorePaint(); const msg = $('rl-score-msg'); if (msg) msg.textContent = '저장하는 중…';
  try { await setDtScore(n); if (msg) msg.textContent = '저장됨 — 단타 판 다시 셈'; } catch (e) { if (msg) msg.textContent = `저장 못 함(${e.message || '연결 안 됨'})`; }
}
function scorePaint() {
  // 한 칩에 칩 점수와 시각(하위) 점수를 함께 둘 수 없음(11-18 재권님 「함께 있을수 없는 값이야 둘중 하나만 기입하도록 해줘」) — 하나가 표에 있으면 다른 쪽은 고를 수 없게
  const top = (k) => k.split('|')[0], clash = (k) => ks.some((x) => x !== k && top(x) === top(k) && (x.includes('|') !== k.includes('|')));
  const b = scoreBox(), ks = Object.keys(score), rest = conds.filter((k) => !ks.includes(k) && !clash(k));
  b.innerHTML = `<div class="rl-sh"><b>조건별 점수</b> <span class="rl-sug">걸린 조건 점수를 더해 큰 순으로 줄 세움 · 비우면 겹친 칩 수 순 · 표에 없는 조건은 0점</span></div>
    ${ks.map((k) => `<label class="dt-fee">${esc(condTxt(k))} <input data-k="${esc(k)}" class="rl-in rl-num" inputmode="decimal" value="${esc(score[k])}" aria-label="${esc(condTxt(k))} 점수">점 <button type="button" class="kh-chip" data-del="${esc(k)}" data-tip="이 조건 빼기" aria-label="${esc(condTxt(k))} 빼기">✕</button></label>`).join('')}
    ${rest.length ? `<select data-new class="rl-in" aria-label="조건 더하기"><option value="">+ 조건</option>${rest.map((k) => `<option value="${esc(k)}">${esc(condTxt(k))}</option>`).join('')}</select>` : ''} <span id="rl-score-msg" class="rl-sug"></span>${(() => { const c = [...new Set(ks.filter((k) => clash(k)).map(top))]; return c.length ? ` <span class="st-err">${esc(c.join(' · '))} — 칩 점수와 시각 점수가 함께 있음 · 시각 점수만 씀 · 하나를 빼 주십시오</span>` : ''; })()}`;
}
async function scoreShow(m) {
  const b = scoreBox(); b.hidden = false;
  const cs = (m.chips && m.chips.length ? m.chips : dtChips()).map(chipName); conds = cs.flatMap((c) => (c === 'VI·급등' ? [c, ...VI_SUB.map((x) => `${c}|${x}`)] : [c]));
  if (b.contains(document.activeElement)) return;   // 치는 중이면 다시 그리지 않음
  await scoreLoad(); scorePaint();
}
// 오늘 것은 계속 다시 받는다(11-12 재권님 「오늘자는 계속 값을 갱신하고 있어야해」) — 보고 있는 칩 하나만 · 주기는 서버 값(홀딩스 home.js 와 같은 열쇠)
//   서버 롱폴이 켜져 있으면 바뀔 때 · 아니면 그 열쇠의 주기로 · 열쇠가 없으면(VI·급등 · 볼린저) 아래 FALLBACK 은 홀딩스와 같은 값 — 서버가 롱폴을 못 줄 때만
const VI_FALLBACK_MS = 30000, BB_FALLBACK_MS = 60000, CHIP_FALLBACK_MS = 300000;
const LIVE = { turn: ['vol_chip.CACHE_TTL', CHIP_FALLBACK_MS], turnup: ['vol_chip.CACHE_TTL', CHIP_FALLBACK_MS],   /* 거래 칩 둘 — 서버 칩 셈 주기(/api/kis/stats timing · 개념정의 덧 11-23) */ ov: ['dt30.LIVE_TTL', CHIP_FALLBACK_MS], pre: ['pre_flow.FLOW_TTL', CHIP_FALLBACK_MS], rise: ['open_rise.CACHE_TTL', CHIP_FALLBACK_MS], vi: [null, VI_FALLBACK_MS], bb: [null, BB_FALLBACK_MS] };
Object.entries(LIVE).forEach(([id, [key, fallbackMs]]) => { if (RULES[id] && RULES[id].url) watch({ url: () => (cur === id ? RULES[id].url : null), onChange: () => show(id, true), key, fallbackMs }); });
