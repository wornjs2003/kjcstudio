// 투자 전략 「단타 30」 — 09:06 매수 → 30분마다 14:00 까지 · 30거래일 (2026-11-11 · 시황분석1)
//   · 재권님 「단타 목록 상위 30개를 소팅해서 9시 6분에 배수하고 9시반 10시 등 30분 단위로 2시까지 가격 추적하도록 셋팅해줘, 아래에 프리장 넣기 처럼 그 위에 종목 넣어서」 →
//     시안 temp/시황분석1-dt30-1743 → 「응 이대로 만드는데 위에 날짜도 넣어줘 30일 추적가능하도록」
//   · 그날 판(09:06 에 굳힌 단타 상위 30 · 매수가 · 각 시각 값)과 쌓인 날 목록은 서버 한 곳 — 화면은 그리기만(매수가 대비 % · 평균은 받은 값으로 셈)
//     응답(안 · 서버 레인과 맞춤): data { day, buyAt, times[HHMM], rows[{rank, code, name, cap(억원), sector(WICS), chips[], buy, px{HHMM: 값}}] } · meta { days[YYYYMMDD …최근 먼저] }
//   · 값이 없으면 — (0 이 아니다) · 서버를 다시 묻는 주기는 없다(날을 누를 때 · 처음 열 때 한 번)
import { signClass, NUM } from '/assets/js/sign.js';
import { ready as toneReady, has as toneHas, paint as tonePaint } from '/assets/js/tone.js';   // 거래 비율 글씨 짙기 — 전날 같은 시각 대비(지표 표 turn_prev_pct · 11-23)
import { bindWin } from './strategy-dtwin.js';
import { renameChips, chipName, serverChip } from './strategy-chipname.js';   // 칩 이름을 실시간 순위와 같게(「수급」 → 「자동」 · 11-18) — 서버 값을 받는 자리에서
import { chipTip } from './strategy-chipinfo.js';   // 칩 설명 한 곳 — 룰 칸과 같은 글(11-20)
// 종목 이름을 누르면 홀딩스 홈과 같은 종목 모달(11-24 재권님 「가」) — 누를 때 부름(11-26 재권님 「판이 그려지는것도 너무 느린데 이유가 뭐지?」 — 모달 부품 서른 개 남짓을 판보다 먼저 줄줄이 받아 판 받기가 3초쯤 늦었음)
const openStockModal = (code) => import('/holdings/js/components/stock-modal.js').then((m) => m.openStockModal(code));
import { mountSector, loadSector } from './strategy-sectorflow.js';   // 섹터수급 칸 — 단타 판 맨 위(11-18)   // 칩별 승률 접기 — 손익 칸 안

const API = '/api/kis/dt30';   // 서버 주소 — 개발2(11-11 18:2x 정함 · 아직 커밋 전)
let root = null;   // 판을 그린 그릇(mountDt30) — 칸은 이 안에서만 찾는다
const BIND = [];   // 그릇에 붙일 누르기 처리 — mountDt30 이 그릴 때마다 새 칸에 붙인다
const $ = (id) => (root ? root.querySelector(`#${id}`) : null);
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (x, d = 0) => (x == null || !Number.isFinite(Number(x)) ? '—' : Number(x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (x) => { if (x == null || !Number.isFinite(x)) return '—'; const c = signClass(x, NUM); const t = `${x > 0 ? '+' : ''}${num(x, 2)}%`; return c ? `<span class="${c}">${t}</span>` : t; };
// 시가총액 — 억원(서버 cap) · 1조 이상은 조 단위 한 자리
const capTxt = (e) => { const v = Number(e); if (e == null || !Number.isFinite(v)) return '—'; return v >= 10000 ? `${num(v / 10000, 1)}조` : `${num(v)}억`; };
// 풀린 시총 · 거래 비율 — 종목 이름 아래 종목코드 옆에 나열(11-23 재권님 「종목이름 아래 종목코드 옆으로 나열해줘」) · 좁은 표는 종목 칸 아래 줄(11-23 재권님 「전종목의 거래되는 총 시가 … 거래되는 총량에 비해 몇%가 거래되는지도 … 단타쪽이면 좋을거 같아」 → 「응 그래 진행해」) — 서버(개발2) rows[].floatCap(억원) · turn(%) 를 받기만 · 셈은 서버 한 곳(meta.turnNote)
//   못 잰 칸(null · 우선주 등)은 「—」
//   글씨 짙기 — 거래 비율 % 자체가 아니라 전날 같은 시각 대비(rows[].turnPrevPct · 기준 100 · 많을 때만 빨강)로 셈 · 지표 표 turn_prev_pct · 셈은 tone.js 한 곳(재권님 「나」 → 「전날 동시간 대비로」 11-23)
//   전날 값이 없으면(쌓기 11-23 시작 · null) 색 없음 · 지표 표를 아직 못 읽었으면 다음 그리기 때 칠함
const turnTxt = (x, prev) => { const v = Number(x); if (x == null || !Number.isFinite(v)) return '—';
  const c = prev != null && toneHas('turn_prev_pct') ? tonePaint('turn_prev_pct', prev, 'text') : '', tip = prev != null && Number.isFinite(Number(prev)) ? ` data-tip="전날 같은 시각 대비 ${num(Number(prev), 0)}%"` : '';
  return c || tip ? `<span${c ? ` style="color: ${c}"` : ''}${tip}>${num(v, 2)}%</span>` : `${num(v, 2)}%`; };
// 거래총량 — 종목 이름 칸 셋째 줄(넓은 폭) · 좁은 표는 종목 칸 아래 줄 끝 · 서버(개발2) rows[].accVol(주) · accValue(억원) · volPrevPct · valuePrevPct(전날 같은 시각 대비 %)를 받기만 · 셈은 서버 한 곳(meta.turnNote)
//   전날 값이 없으면(쌓기 11-23 시작 · 그날 판이 아직 안 냄) 「—」 · 0 으로 안 냄 · 글씨 짙기는 지표 표 vol_prev_pct · amt_prev_pct(tone.js) · 재권님 「단타에 지금 있는 종목들 거래총량이랑 전일대비 거래 이런거 누락된거 다 넣어줘」 · 「누적 거래량.거래대금 이것도 지금하면 좋을거같아」(11-23)
const volTxt = (x) => { const v = Number(x); if (x == null || !Number.isFinite(v)) return '—'; return v >= 1e8 ? `${num(v / 1e8, 1)}억주` : v >= 1e4 ? `${num(v / 1e4, v >= 1e6 ? 0 : 1)}만주` : `${num(v)}주`; };
const amtTxt = (e) => { const v = Number(e); if (e == null || !Number.isFinite(v)) return '—'; return v >= 10000 ? `${num(v / 10000, 2)}조` : `${num(v, v < 10 ? 1 : 0)}억`; };
const prevPctTxt = (p, key) => { const v = Number(p); if (p == null || !Number.isFinite(v)) return '—'; const c = toneHas(key) ? tonePaint(key, v, 'text') : ''; return `<span${c ? ` style="color: ${c}"` : ''}>${num(v, 0)}%</span>`; };
// 전일 하루 거래량 대비 지금 거래량(%) — 서버 accVol(오늘 누적 · 한국거래소라 프리장 빠짐) ÷ prevDayVol(전날 하루) × 100 · 못 잰 종목은 null(11-24 재권님 「프리장 미포함으로 하고 전일대비 거래량 … 종목에는 전일대비 현재거래량인데 지금 하고자 하는 방향으로 바꾸자」)
//   색 없음 — 뜻이 vol_prev_pct(전날 같은 시각 대비)와 달라 그 이름을 안 씀 · 지표 표에 새 항목(기준 · 폭은 재권님 값 · 개념정의가 여쭘)이 들어오면 그 id 로 칠함(개념정의 검수 16:56)
//   09:25(여는 시각 + 25분 · 늦게 연 날은 그만큼 뒤) 전에는 안 보이고 거르기에도 안 씀 — 값이 있든 없든(11-24 재권님 「전일 거래량 대비는 9시 25분부터 보여진다로 해놓고 그전에 값이 있던없던 소팅에 적용이 안되게」) · 지금 시각은 판 nowAt(서버) · 없으면 이 기계 시계 · 끝난 판(closed)은 늘 보임
const VOL_FROM_MIN = 25;   // 여는 시각부터 몇 분 뒤부터 — 재권님 값
const volFrom = () => { const v = hhmm(DM().volDayAt); return /^\d{4}$/.test(v) ? v : addHM(openHM(), VOL_FROM_MIN + lateOf()); };   // 서버 판 meta.volDayAt(늦게 연 날 서버가 밀어 줌 · 개발2 fb15d94)이 오면 그 값 · 서버가 주면 위 25분 셈은 안 씀
const volOpen = () => { const d = curD(); if (!d || d.closed === true) return true; const t0 = new Date(), today = `${t0.getFullYear()}${String(t0.getMonth() + 1).padStart(2, '0')}${String(t0.getDate()).padStart(2, '0')}`; if (d.day && String(d.day) !== today) return true; const n = hhmm(d.nowAt) || t0.toTimeString().slice(0, 5).replace(':', ''); return n >= volFrom(); };
const dayVolPct = (r) => { if (!volOpen()) return null; const a = Number(r.accVol), b = Number(r.prevDayVol); return r.accVol != null && r.prevDayVol != null && Number.isFinite(a) && b > 0 ? a / b * 100 : null; };
// 괄호 색 — 거르기 칸 「전일 거래량 대비 ( )% 이상」 에 넣은 값(set.volMin) 이상인 종목만 빨강(--kh-up) · 빈칸 · 못 잼 · 25분 전은 색 없음 · 짙기 없음 · 사용자 값이라 지표 표 · tone.js 안 씀(11-24 재권님 「() 에 변수값을 넣으면 그걸 넘어가는것만 빨간색으로」 · 개념정의 전달)
const dayVolTxt = (r) => { const x = dayVolPct(r), m = Number(st.set.volMin) || 0; if (x == null) return '—'; const t = `${num(x, 0)}%`; return m > 0 && x >= m ? `<span style="color: var(--kh-up)">${t}</span>` : t; };
const accTxt = (r) => `<span data-tip="오늘 누적 · 량 괄호는 전날 하루 거래량 대비(프리장 빠짐 · 장 시작 25분 뒤부터) · 대금 괄호는 전날 같은 시각 대비">량 ${volTxt(r.accVol)}(${dayVolTxt(r)}) · 대금 ${amtTxt(r.accValue)}(${prevPctTxt(r.valuePrevPct, 'amt_prev_pct')})</span>`;
const WK = ['일', '월', '화', '수', '목', '금', '토'];
const dayTxt = (d) => { const m = String(d || '').match(/^(\d{4})(\d{2})(\d{2})$/); return m ? `${m[2]}-${m[3]}(${WK[new Date(+m[1], +m[2] - 1, +m[3]).getDay()]})` : '—'; };
const hmTxt = (t) => (/^\d{4}$/.test(String(t)) ? `${String(t).slice(0, 2)}:${String(t).slice(2)}` : esc(t || '—'));

// 이벤트 칸 — 그 종목이 걸린 홀딩스 「관심」 아래 룰(칩) 이름을 홀딩스 칩 줄 차례로 · 이름은 서버 rows[].chips 그대로(재권님 11-11 「종목과 매수가 사이에 이벤트를 추가하고 이벤트가 뭐뭐 걸렸는지 넣어줘 vi 초반급등 긍 관심하위의 룰들」)
const EV_ORDER = ['관심', '현시간 유통회전', '전일 현시간 대비 급증', '돈몰림', '미국강세', '프리장', '초반상승', '현재상승', 'VI·급등', '볼린저', '장외', '매수', '자동'];
const evHtml = (c, r) => evChips(c, r, r ? [...st.miss].filter((x) => !(c || []).includes(x)) : []);   // 못 받은 칩은 종목마다 이름만 회색으로 붙임 · 「못 받음」 글씨 없음 · 늦게 채워 이미 붙은 칩은 뺌(11-12 재권님 「못받음 이라는 글씨만 빼주고 비활성화 된거같이 회색으로」 → 「각 종목에도 넣어줘」)
const evChips = (c, r, miss = []) => { const a = [...(Array.isArray(c) ? c : []), ...miss]; if (!a.length) return '<span class="st-err">—</span>'; a.sort((x, y) => (EV_ORDER.indexOf(x) + 99) % 99 - (EV_ORDER.indexOf(y) + 99) % 99); return a.map((x) => { const sb = r ? subsOf(r, x) : []; const dim = r && colsOf().includes(x) && !liveChip(r, x); if (miss.includes(x)) return `<span class="dt-evc is-miss" data-tip="${esc(`그날 판에 ${x} 값을 ${missWord()} — 이 종목이 걸렸는지 모름`)}">${esc(x)}</span>`; const vt = r && x === 'VI·급등' ? viTxt(r) : ''; return `<span class="dt-evc${dim ? ' is-off' : ''}">${esc(x)}${sb.length ? `<small>${esc(subTxt(x, sb))}</small>` : ''}${vt ? `<small>${esc(vt)}</small>` : ''}</span>`; }).join(''); };

const DOC = '/api/board/doc/strategy-rules';   // 수수료 % 를 두는 곳 — 투자 전략 룰 값과 같은 문서(rules.dt30.feePct)
const WIDE = matchMedia('(min-width: 701px)');   // 701 — strategy.css 가 쓰는 넓힘 폭(홀딩스 · Insight 700 경계) · 그보다 좁으면 좁은 폭 차례
const st = { lockSel: 0, set: null, cols: null, mon: '', off: new Set(), subOff: new Set(), order: '', fee: null, day: null, days: [], seq: 0, last: {}, only: '', data: null, score: {}, pre: null, grp: null };   // grp — 섹터 · 테마 칸에서 누른 묶음 {k: 'sec' | 'th', v} · 본 표를 그 종목만(11-24)   // only — 이벤트 거르기(재권님 11-11 「vi없는건 제외하고 다시 셈해봐」) · 빈칸이면 전체
const ONLY = [['', '전체'], ['VI·급등', 'VI·급등 든 것만']];
// 줄 세우기 (재권님 11-11 「상위 16종목을 vi급등이 있고 초반매수 가 있고 시가총액이 높은순으로 다시 정렬해서 계산해봐」 — 「초반매수」 는 초반상승 칩으로 읽음)
//   기본 = 서버 차례(단타 순) · vi = VI·급등 든 것 먼저 → 그 안에서 초반상승 든 것 먼저 → 시가총액 큰 순 — 상위 PNL_TOP · 손익을 이 차례로 다시 셈
const ORDER = [['', '단타 순(켜진 칩)'], ['vi', 'VI·급등 → 초반상승 → 시가총액 순'], ['open', '상승률 순(시가 대비)']];   // open — 보는 차례만(묶음 안에서) · 사는 종목 · 상위 N 은 그대로(11-24 재권님 「그걸로 정열 가능하게」 → 「나」)
const has = (r, c) => (liveChip(r, c) ? 1 : 0);   // 켜진 칩 · 하위 칩만(11-18 재권님 「VI·급등 칩 아래를 이렇게 나누고 소팅도 되게 해야해」 — 「09:25 이후」 를 끄면 그 종목은 VI·급등 묶음에서 빠져 뒤로)
const ORDER_FN = { vi: (a, b) => has(b, 'VI·급등') - has(a, 'VI·급등') || has(b, '초반상승') - has(a, '초반상승') || (Number(b.cap) || 0) - (Number(a.cap) || 0) };   // last — 날마다 14:00(마지막 시각) 평균 · 날짜 칩에 붙임

// 단타 칩 켜고 끄기 (11-11 재권님 「평균 옆에 단타 하위 버튼들 추가하고 하위 버튼들의 하위 칩도 필요해 상위버튼과 하위버튼을 활성화 비활성화 되는게 보여야 하고
//   활성화 될때와 비활성화 될때 이에 맞게 순위 조절이 되야하고 거기에 맞춰서 상위 16개 종목의 주가 및 수익률이 갱신되어야해」 → 「100개까지 늘려놔 그리고 그대로 개발해」)
//   · 단타가 세는 칩(홀딩스 home.js OV_CHIPS 와 같은 일곱 · 서버 개발2 가 「앞의 일곱」 으로 줌) 마다 단추 · 그 아래 하위 칩(서버 rows[].subs 에서 모음 — 이름을 박지 않음)
//   · 켜진 칩 · 하위 칩에 걸린 수(n)로 다시 줄 세움: n 많은 순 → 초반상승 % → 시가총액 — 서버 차례와 같은 셈 · n 0 인 종목은 뺌 · 상위 PNL_TOP · 손익 · 평균이 그 차례로 다시 셈
// 칩 목록은 서버 칩 룰 표 한 곳(/api/kis/chip-rules 단타.ovChips · 11-20 개발1 표 · 개발2 받기로) — 이름은 chipName 으로(수급 → 자동) · 판을 처음 받기 전에 한 번 받는다 · 못 받으면 빈 목록(칸은 st.cols 저장값 · 판에 온 칩으로)
const DT_CHIPS = [];
// 매도 셈 기본값(손절 · 꺾임 · 고점 · 시각 미달 · 횡보 열한 칸)도 같은 주소 meta.sellDef 한 곳(11-20 재권님 「가」 · 개발2 3523082 — 칩별 승률 표 서버 셈과 한 벌) · 못 받으면 비워 두고 「서버 값 못 받음」 · 짐작 안 함
const SELL_DEF = {};
async function loadDtChips() {
  try {
    const r = await fetch('/api/kis/chip-rules', { cache: 'no-store' }); const j = r.ok ? await r.json() : null;
    const v = j && j.ok && Array.isArray(j.data) ? (j.data.find((x) => x.chip === '단타' && x.key === 'ovChips') || {}).value : null;
    const sd = j && j.meta && j.meta.sellDef; if (sd && typeof sd === 'object') { Object.assign(SELL_DEF, sd); st.sellFail = false; } else st.sellFail = true;
    if (Array.isArray(v) && v.length) { DT_CHIPS.splice(0, DT_CHIPS.length, ...volNext(v.map(chipName))); if (!CHIP_SEEN.length) CHIP_SEEN.push(...v.map(chipName));   /* 칩 색은 서버 목록 차례 그대로 — 칸을 옮겨도 색이 안 바뀜 */ st.chipFail = false; addNewChips(v.map(chipName)); }
  } catch (e) { st.sellFail = true; /* 못 받음 — 빈 목록 그대로 · 다음 판 받기 때 다시 */ }
}
// 칩 칸 (11-12 재권님 「칩을 추가해도 칩을 활성화 비활성화되도록 우리꺼에 맞게 그려봐」 → 시안 temp/시황분석1-cols-1800 → 「오 좋아 이런거야 이대로 먼저 개선해서 올려줘」)
//   넓은 폭 표는 칩마다 세로 칸 · 칸 이름을 누르면 차림(켜기 · 끄기 · 룰 보기 · 옮기기 · 칸 지우기) · 끝 「+ 칩」 으로 서버가 주는 다른 칩(현재상승 · 볼린저 · 지운 칩)을 칸으로 더함
//   셈에 드는 칩 = 칸에 있고 켜진 칩(겹친 수 · 순위 · 손익이 그것으로 다시 셈) · 칸 차례 · 꺼진 칩은 보는 사람 브라우저에만(보는 상태 — 저장 못 해도 기본 칸으로 돈다)
const COLS_KEY = 'dt30-cols-v1';
// 거래 칩 둘(거래비율 · 거래비율급증)은 관심 바로 뒤(11-23 재권님 「거래량 급증은 프리장 과 관심 사이로 이동」 · 개발2 fece17c 가 옛 「거래량급증」(하위 비율 · 전일)을 칩 둘로 나눔 — 재권님 「두개야 / 전일대비 현시점거래비율 이랑 유통주식대비 현시점 거래비율」)
//   기본 칸과 이 브라우저에 저장된 칸에 한 번 적용(COLS_MOVED) · 저장된 칸의 옛 「거래량급증」 은 둘로 바꿈 · 그 뒤 손으로 옮긴 차례는 그대로
const VOL_CHIPS = ['현시간 유통회전', '전일 현시간 대비 급증'];   // 화면 이름(strategy-chipname.js 가 서버 「거래비율」 · 「거래비율급증」 을 바꿈 · 11-23 재권님 「다」)
const volNext = (a) => { const v = VOL_CHIPS.filter((x) => a.includes(x) || a.includes('거래량급증')); if (!v.length || !a.includes('관심')) return a; const b = a.filter((x) => x !== '거래량급증' && !VOL_CHIPS.includes(x)); b.splice(b.indexOf('관심') + 1, 0, ...v); return b; };
const COLS_MOVED = 'dt30-cols-vol2-1123';
// 11-18 서버 바뀜(개발2 · 재권님 「관심 하트는 누르는거 없애고 자동으로 관심으로」 → 「응 맞아」) — meta.watchRule 「자동」 인 날은 관심 = 자동 관심 룰 · 「수급(자동)」 칩이 안 옴
//   그날은 「자동」 칸을 빼고(빈 칸으로 남기지 않음) · 지난 날 판(옛 셈)은 그대로
// 관심 칩을 「자동」 으로 셈하는 날인지는 그 날 판의 meta.watchRule — 셈하는 판(calcD)이 있으면 그 판 것 · 없으면 고른 날 것(11-24 qa · 기간 줄의 다른 날 차익이 고른 날 meta 로 셈돼 날을 누르면 값이 바뀌던 것)
const wAuto = () => { const m = (calcD && calcD.meta) || null; return m ? m.watchRule === '자동' : st.watchAuto; };
const colsOf = () => (st.cols || DT_CHIPS).filter((c) => !(wAuto() && c === '자동'));
(() => { try { const v = JSON.parse(localStorage.getItem(COLS_KEY) || 'null'); if (v && Array.isArray(v.cols) && v.cols.length) { st.cols = v.cols.map(String).map(chipName); st.off = new Set((v.off || []).map(String).map(chipName)); if (!localStorage.getItem(COLS_MOVED) && (st.cols.includes('거래량급증') || VOL_CHIPS.some((x) => st.cols.includes(x)))) { if (st.off.has('거래량급증')) VOL_CHIPS.forEach((x) => st.off.add(x)); st.off.delete('거래량급증'); st.cols = volNext(st.cols); localStorage.setItem(COLS_MOVED, '1'); localStorage.setItem(COLS_KEY, JSON.stringify({ ...v, cols: st.cols, off: [...st.off] })); } } } catch (e) { /* 기본 칸 */ } })();   // 꺼 둔 칩(off)을 먼저 읽고 옛 이름을 바꾼 뒤 저장 — 빈 목록으로 덮지 않음(개념정의 검수 11-23)
const colsSave = () => { try { localStorage.setItem(COLS_KEY, JSON.stringify({ cols: colsOf(), off: [...st.off] })); } catch (e) { /* 이 브라우저에 못 남겨도 화면은 돈다 */ } };
// 서버가 새로 보낸 칩은 저장된 칸에 저절로 넣는다(11-23 재권님 「넣어」 — 메인 브라우저에 두 거래 칩 생기기 전 칸이 저장돼 있어 그 칩 칸이 영영 안 생김)
//   이 브라우저가 본 서버 칩(KNOWN_KEY)에 없던 칩만 넣는다 — 손으로 지운 칩은 이미 본 칩이라 다시 안 넣음 · 거래 칩은 volNext 로 관심 뒤 · 그 밖은 끝
//   처음 도는 브라우저는 거래 칩 둘만 새 칩으로 본다(그 전에 지운 칩까지 되살리지 않게) · 거래 칩을 이미 받은 브라우저는 그것도 안 넣음
const KNOWN_KEY = 'dt30-chips-known-v1';
function addNewChips(list) {
  try {
    const raw = localStorage.getItem(KNOWN_KEY), known = raw ? JSON.parse(raw) : localStorage.getItem(COLS_MOVED) ? list : list.filter((c) => !VOL_CHIPS.includes(c));   // 거래 칩을 이미 옮겨 받은 브라우저(COLS_MOVED)는 그 뒤 손으로 지웠을 수 있어 새 칩으로 안 봄(창구 검수 11-23)
    const fresh = list.filter((c) => !known.includes(c));
    if (st.cols && fresh.length) { const add = fresh.filter((c) => !st.cols.includes(c)); if (add.length) { st.cols = volNext([...st.cols, ...add]); colsSave(); } }
    localStorage.setItem(KNOWN_KEY, JSON.stringify([...new Set([...known, ...list])]));
  } catch (e) { /* 이 브라우저에 못 남겨도 화면은 돈다 — 칸은 「+ 칩」 으로 */ }
}
const CHIP_SEEN = [];   // 칩 색 차례 — 서버 단타 칩 차례(loadDtChips 가 채움) 뒤로 처음 본 차례(색 변수는 일곱이라 돌려 씀)
const HOT = { '현시간 유통회전': 'vol', '전일 현시간 대비 급증': 'vol2', 'VI·급등': 'vi', 매수: 'buy' };   // 튀는 색 칩 — 진한 바탕 · 하위 단추마다 다른 색(strategy.css · 11-23 재권님 「색은 완전히 튀는 색으로 해주고 각각 버튼 색 다르게」 → 「vi 랑 매수도 이렇게 각각 색이랑 튀도록 해줘」)
const colorOf = (c) => { if (HOT[c]) return HOT[c];   /* 거래 칩 · VI · 매수는 서로 안 겹치는 따로 색(strategy.css data-i) */ if (!CHIP_SEEN.includes(c)) CHIP_SEEN.push(c); return CHIP_SEEN.indexOf(c) % 7; };
const GRP_CHIPS = ['돈몰림', '미국강세'];   // 묶음 칩 — 칩 칸 줄 대신 종목 이름 옆에 · 머리 · 좁은 폭 칩 줄 둘 다 업종 · 테마 목록 없이(11-26 한 곳으로 · 개념정의 검수 덧)
const RULE_OF = { 돈몰림: 'money', 미국강세: 'usup', 프리장: 'pre', 초반상승: 'rise', 현재상승: 'nowup', 'VI·급등': 'vi', 볼린저: 'bb', 장외: 'after', 자동: 'volsurge' };   // 「종목 고르는 룰」 칩(data-rule) — 없는 칩은 룰 칸 없음
const subsRaw = (r, c) => { const v = r.subs && r.subs[c]; return Array.isArray(v) ? v : (v ? [v] : []); };
// VI·급등 하위는 겹치지 않게 둘로 (11-11 재권님 「그중 6개는 따로 분류가 가능하게 해줘」 → 「vi급등칩에 하위에 칩이 2개 있게 해줘」 — VI 43 · 급등 6 이 겹쳐 헷갈림)
//   서버 subs 의 VI · 급등을 읽어 급등이 들었으면 「VI 급등」(VI 도 함께 걸린 것 포함), VI 만이면 「VI 급상승」 — 둘을 더하면 상위 칩 숫자 · 서버 이름이 둘이 아니면 그대로 둠
const BOTH = { 'VI·급등': [['VI', '급등'], ['VI 급상승', 'VI 급등']] };   // 이름 — 재권님 「아래로 vi급상승 vi급등 이렇게 넣어줘」
// VI·급등 하위를 시각으로 둘 (11-18 재권님 「vi급등을 9시 25분전 그이후 로 버튼 2개로 나눠줘」) — 그날 처음 VI · 급등 시각(서버 viAt · surgeAt, 없으면 오늘 알림 목록)이
//   VI_SPLIT 앞이면 「09:25 전」 · 그 시각부터는 「09:25 이후」 · 시각을 못 받으면 「시각 모름」(어느 쪽으로도 안 셈) — 앞의 「VI 급상승 · VI 급등」 둘은 이것으로 바뀜
const VI_SPLIT = '0925';   // 서버 값이 없을 때 · 늦게 여는 날 옮기는 셈은 서버가 meta.viSplit 으로 내줌(11-19 재권님 「응 만들어」 · 화면이 따로 밀면 서버 점수와 갈림) · 하위 이름(점수표 열쇠)은 그대로
// 장 시작 시각 — 서버 판 meta.openAt(「HH:MM」 · 개발2 56f58cb) · lateMin(늦게 여는 분) · 없는 옛 판은 보통 날(09:00 · 0)
// 셈하는 판 — 여러 날 합계는 calc(그날 판)을 부르므로 그동안은 그날 판의 meta(여는 시각 · 9시 1분 시각)로 셈(qa 11-23 — 11-19 수능 10:00 연 날이 오늘 판 09:00 으로 셈돼 「매매 없음」)
let calcD = null;
const curD = () => calcD || st.data;
const DM = () => (curD() && curD().meta) || {};
const addHM = (t, m) => { const x = +t.slice(0, 2) * 60 + +t.slice(2) + (m || 0); return `${String(Math.floor(x / 60)).padStart(2, '0')}${String(x % 60).padStart(2, '0')}`; };
const RULE_MIN_DEF = 5, RULE_MIN_LO = 5, RULE_MIN_HI = 30;   // 매수 룰 기준 시각 = 여는 시각 + (set.ruleMin)분(11-24 재권님 「여는 시각 +()분으로 해주고 지정한 시간에 되도록 해줘」 · 「09:05분~30분이 최종」) — 여는 시각은 openHM()(서버 meta.openAt · 없으면 09:00) 이라 늦게 연 날 저절로 밀림 · 쓰는 자리에서 addHM(openHM(), 분 + lateOf()) · 열쇠는 판 · 줄 · 서버 buyAt(든 시각)과 겹치지 않게 ruleMin
const REG_OPEN_DEF = '0900';   // 보통 날 정규장 여는 시각 — 서버 판 meta.openAt 이 없는 판에서만(CLAUDE.md 「장 시각으로 셈하는 코드는 늦게 여는 날 그만큼 옮긴다」 3번)
const openHM = () => { const o = String(DM().openAt || '').replace(':', ''); return /^\d{4}$/.test(o) ? o : REG_OPEN_DEF; };   // 서버가 주면 안 씀
const viSplit = () => { const v = String(DM().viSplit || '').replace(':', ''); return /^\d{4}$/.test(v) ? v : VI_SPLIT; };   // 나누는 시각은 서버 한 곳 — 판 meta.viSplit(점수 셈과 같은 값 · 개발2 배분 중)이 오면 그 값 · 없으면 09:25(서버 점수와 같게 · 개념정의 267a17d 검수)
const hmS = (t) => `${t.slice(0, 2)}:${t.slice(2)}`;
// 종목 이름 — 고른 칩 조합이 된 종목은 빨강 + 된 시각(11-26 재권님 「해당 조합이 되면 종목의 이름색이 빨간색으로 바뀌게」) · 조합을 안 골랐으면 그대로
// 조합이 된 종목 — 이름 밑 「조합 HH:MM」 옆에 그 조합을 이룬 칩(위 칩 칸 색) · 그 밖 칩은 다음 줄에 붙은 시각과 함께(11-26 재권님 「처음 조합의 조건에 걸린 칩들을 조합 옆으로 나열해주고 그이후에 들어온 칩들은 줄바꿔서 시간까지 해서 나열해줘」)
const chipFirst = (r, c) => { if (spanRow(r)) { const t = spansOf(r, c).map(([a]) => hm4(a)).filter(Boolean).sort()[0]; if (t) return t; } return chipTsOf(r)[c] || ''; };   // 그 칩이 처음 붙은 때(HHMM)
const cbPill = (c, t) => `<span class="dt-cg dt-ovc" data-i="${colorOf(c)}">${esc(c)}${t ? ` <small class="dt-ovt">${t === '0000' ? '장 전' : hmS(t)}</small>` : ''}</span>`;
// 조합이 된 뒤 다른 고른 조합을 마저 채운 칩 — 조합 줄에 그 칩이 들어온 시각과 함께(11-26 재권님 「칩조합조건이 겹치는 칩이 추가되면 그칩이 들어온 시간을 나열한다 · 칩조합 조건이 걸리지 않은 칩이 추가되는건 가로로 줄을 그어서 그아래로」)
const comboAdds = (r, h) => { const S = [...comboSel()].map((k) => k.split(' + ')), have = new Set(h.key.split(' + ')), out = [];
  comboEvents(r).forEach(([t, cs]) => { if (t <= h.t) return; const on = new Set(cs);
    S.forEach((ks) => { if (ks.every((c) => on.has(c))) ks.forEach((c) => { if (!have.has(c)) { have.add(c); out.push(c); } }); }); });
  return out.map((c) => [c, chipFirst(r, c)]).sort((a, b) => (a[1] || '9999').localeCompare(b[1] || '9999')); };
const nameB = (r) => { const h = comboHit(r); if (!h) return `<b>${esc(r.name || '—')}</b>`; const ks = h.key.split(' + '); return `<b class="dt-cbn">${esc(r.name || '—')}</b><small class="dt-cbt" data-tip="${esc(`고른 조합 ${h.key} — ${hmS(h.t)} 에 됨`)}"><span class="dt-cbt-t">조합 ${hmS(h.t)}</span>${ks.map((c) => cbPill(c)).join('')}${comboAdds(r, h).map(([c, t]) => cbPill(c, t || null)).join('')}</small>`; };   // 풍선은 아래 작은 글에 — 이름에 달면 이름을 눌러도 종목 창이 안 뜸(openCo 가 풍선 칸은 넘김 · 11-26)
const p1HM = () => { const o = String(DM().px1At || '').replace(':', ''); return /^\d{4}$/.test(o) && o > openHM() ? o : addHM(openHM(), 1); };   // 여는 시각보다 앞이면(늦게 연 날 옛 서버가 09:01 을 줌) 여는 시각 + 1분
export const VI_SUBS = ['09:25 전', '09:25 이후', '시각 모름'];   // 점수표 열쇠(「VI·급등|09:25 전」)도 이 이름 — strategy-chips.js 가 가져다 씀
const hm4 = (t) => String(t || '').replace(/:/g, '').slice(0, 4);   // 이 칩 셈만으로 돌게 — 아래 매수 타이밍의 hhmm 에 기대지 않음(11-18 메인에 이 커밋만 먼저 가 hhmm 없음으로 단타 판이 멈췄음)
const viFirst = (r) => {
  const t = [r.viAt, r.surgeAt].filter(Boolean).map(hm4);
  if (!t.length) { const o = viAt.map && viAt.day === (st.data && st.data.day) ? viAt.map[r.code] : null; if (o) [o.vi, o.surge].filter(Boolean).forEach((x) => t.push(hm4(x))); }
  return t.length ? t.sort()[0] : null;
};
const subsOf = (r, c) => {
  if (c === 'VI·급등') { if (!(r.chips || []).includes(c)) return []; const t = viFirst(r), rest = subsRaw(r, c).filter((v) => v !== 'VI' && v !== '급등'); return [t == null ? VI_SUBS[2] : t < viSplit() ? VI_SUBS[0] : VI_SUBS[1], ...rest]; }
  const a = subsRaw(r, c), b = BOTH[c]; if (!b) return a;
  const [[x, y], [onlyX, withY]] = b, hx = a.includes(x), hy = a.includes(y);
  const rest = a.filter((v) => v !== x && v !== y);
  return hy ? [withY, ...rest] : hx ? [onlyX, ...rest] : rest;
};
const subOrder = (c, xs) => { const o = c === 'VI·급등' ? VI_SUBS : BOTH[c] ? BOTH[c][1] : []; return xs.sort((p, q) => ((o.indexOf(p) + 99) % 99) - ((o.indexOf(q) + 99) % 99) || p.localeCompare(q)); };
const liveChip = (r, c) => { if (st.off.has(c) || !(r.chips || []).includes(c)) return false; const sb = subsOf(r, c); return !sb.length || sb.some((x) => !st.subOff.has(`${c}|${x}`)); };
const nLive = (r) => colsOf().reduce((a, c) => a + (liveChip(r, c) ? 1 : 0), 0);   // 칸에 있고 켜진 칩만
// 한 번 붙었다 빠진 칩도 센다 — 서버 rows[].chipTime(칩마다 처음 붙은 시각 · 빠져도 남음)에 있으면 붙었던 것(11-24 재권님 「서버는 정보만 있고 셈은 화면에서 한다」 → 「응 차레대로 해」 ·
//   이수스페셜티케미컬(프리장 칩) · 하이젠알앤엠(매수 칩)이 빠지자 칩 5개에 못 미쳐 판에서 사라지던 것 · 09:30 전에 산 종목은 굳음)
//   빠진 칩의 하위 칩(외 · 기 · 프 · 어림)은 기록에 없어 하위 끄기를 못 가름 — 칩이 켜져 있으면 셈 · 다시 붙은 칩의 「나중 시각」 은 서버 칩 쌓임 기록(개발2)이 오면
const everChip = (r, c) => { if (st.off.has(c)) return false; if ((r.chips || []).includes(c)) return liveChip(r, c); return !!((r.chipTime || {})[c]); };
// 칩 붙음 · 빠짐 구간(11-25 재권님 「칩 빠진 시각도 넣어줘」 · 서버 개발2 rows[].chipSpans {칩: [[붙음, 빠짐 | null] …]} HH:MM · 끝 null = 지금도 붙음)
//   있는 줄은 「같은 시각에 함께 붙어 있던 칩」 으로 셈(서버 매수 셈과 같게 — 칩 N개가 동시에 붙어 있던 첫 순간) · 없는 줄(11-24 전 판)은 한 번 붙은 칩(everChip) 그대로
//   구간 기록이 없는 칩 — 지금 붙어 있으면 처음 붙은 때부터 지금까지 · 빠졌으면 언제까지인지 몰라 안 셈 · 끄기 · 하위 끄기는 everChip 과 같게
const spanRow = (r) => !!(r && r.chipSpans && typeof r.chipSpans === 'object');
const spansOf = (r, c) => { const s = r.chipSpans[c]; if (Array.isArray(s) && s.length) return s; if (!(r.chips || []).includes(c)) return []; const t = (r.chipTime || {})[c] || (r.chipAt || {})[c]; return t ? [[t, null]] : []; };
const chipAtT = (r, c, t) => everChip(r, c) && spansOf(r, c).some(([a, b]) => hm4(a) && hm4(a) <= t && (b == null || t < hm4(b)));
const nAtT = (r, t) => colsOf().reduce((a, c) => a + (chipAtT(r, c, t) ? 1 : 0), 0);
const spanTs = (r) => [...new Set(colsOf().filter((c) => everChip(r, c)).flatMap((c) => spansOf(r, c).map((x) => hm4(x[0])).filter(Boolean)))].sort();
const ovSet = (r) => { if (spanRow(r)) { let best = null, m = -1; spanTs(r).forEach((t) => { const k = nAtT(r, t); if (k > m) { m = k; best = t; } }); return best ? colsOf().filter((c) => chipAtT(r, c, best)) : []; } return colsOf().filter((c) => everChip(r, c)); };   // 가장 많이 함께 붙어 있던 때의 칩(겹친 칩 이름 · 11-26)
const nEver = (r) => (spanRow(r) ? spanTs(r).reduce((m, t) => Math.max(m, nAtT(r, t)), 0) : colsOf().reduce((a, c) => a + (everChip(r, c) ? 1 : 0), 0));   // 구간이 있으면 가장 많이 함께 붙어 있던 수
const riseOf = (r) => (r.rise == null || !Number.isFinite(Number(r.rise)) ? -Infinity : Number(r.rise));   // 초반상승 % — 안 든 종목은 null → 맨 뒤
// 조건별 점수 (11-18 재권님 「여기도 내가 조건들 넣을수 있게 해줘. 있는조건이면 고르면 되고 조건별로 점수를 매겨서 우선순위 정할거야」 → 홈 「단타」 도 같은 차례로 「응」)
//   · 점수표는 룰 문서 rules.dt30.score 한 곳 — { 칩: 점수 · 'VI·급등|09:25 전': 점수 … } · 「룰 — 단타」 칸(strategy-chips.js)에서 넣음 · 홈 차례는 서버(개발2)가 같은 표로 셈
//   · 표가 비면 지금 셈(겹친 칩 수) 그대로 · 표에 없는 조건은 0점 · 켜진 칩 · 하위 칩만 셈
const hasScore = () => Object.keys(st.score || {}).length > 0;
// 서버가 점수(rows[].score)와 칩별 몫(rows[].scoreBy)을 주면 그 값에서 화면에서 꺼진 칩 · 꺼진 하위 칩 몫만 뺌 — 셈은 서버 한 곳(개발2 3e54a3b · 11-18)
//   서버 값이 없는 판(옛 판 · 서버 고침 전)만 아래 화면 셈
const scoreOf = (r) => (r.score != null && r.scoreBy && typeof r.scoreBy === 'object'
  ? Number(r.score) - Object.entries(r.scoreBy).reduce((a, [c, v]) => a + (liveChip(r, c) ? 0 : Number(v) || 0), 0)
  : scoreLocal(r));
const scoreLocal = (r) => colsOf().reduce((a, c) => { if (!liveChip(r, c)) return a; const sb = subsOf(r, c).filter((x) => !st.subOff.has(`${c}|${x}`)), S = st.score;
  const k = sb.find((x) => S[`${c}|${x}`] != null); return a + Number(k ? S[`${c}|${k}`] : S[c] ?? 0); }, 0);
const rankOf = (r) => (hasScore() ? scoreOf(r) : nLive(r));
const byLive = (a, b) => rankOf(b) - rankOf(a) || (riseOf(b) - riseOf(a) || 0) || (Number(b.cap) || 0) - (Number(a.cap) || 0);   // 겹친 칩 수 → 초반상승 % → 시가총액(재권님 19:1x 말씀 · 개발2 서버 19:14 와 같은 셈 · rows[].rise)
// 종목 차례 점수(11-23 재권님 「점수가 높은게 순위가 높게」 → (가)) — 셈은 서버(개발2 dt30.sort_rows · 328d256) 한 곳 · 셈 칸 set.ordScore{기준: 점수}를 서버가 읽어
//   줄마다 rows[].ordTotal(기준마다 판 안 순위 0~1 × 점수 합)을 주고 그 합이 큰 순 · 같으면 지금 차례 — 화면은 ordTotal 로 세우기만(판정은 서버 · 개념정의 11-23)
//   ordTotal 이 없으면(점수가 다 빈칸 · 옛 판 · 서버 고침 전) 지금 차례(byLive) · 켜고 끈 칩은 지금처럼 화면 byLive 의 칩 수에만 듦
const ordSort = (rows) => (rows.some((r) => r.ordTotal != null)
  ? rows.sort((a, b) => (Number(b.ordTotal) || 0) - (Number(a.ordTotal) || 0) || byLive(a, b))
  : rows.sort(byLive));
// 칩 설명 — 마우스를 1초 올려 두면 뜨는 공용 풍선(data-tip · glossary.js) · 글은 strategy-chipinfo.js 한 곳(「종목 고르는 룰」 칸과 같은 글 · 11-20 재권님 「응」)
const tipOf = (k) => chipTip(k, { rules: st.rules, chipInfo: st.chipInfo, watchAuto: st.watchAuto, subTips: SUB_TIP });
// VI · 급등 걸린 시각 (11-18 재권님 「vi급등 방생시기도 단타판에 넣어줘」 → 「vi발동시간도 넣어달라고 했는데」 → 「응 오늘판이라도 해줘」)
//   단타 판 서버 값(dt30)에는 아직 시각 칸이 없다 — 서버 칸은 개발2 몫(작업우선순위에 올림) · 그때까지 오늘 판만 서버 /api/alerts/today(그날 상승 VI · +20% 급등 목록 · 시각 t)에서 그 종목의 처음 시각을 붙인다
//   그 주소는 오늘 것만 준다 — 지난 날 판에는 시각을 안 붙인다(지어내지 않음) · 받는 때는 판을 받을 때(load)와 같다(따로 묻는 주기 없음)
const viAt = { day: null, map: null };
async function viLoad(day) {
  try { const r = await fetch('/api/alerts/today', { cache: 'no-store' }); const j = r.ok ? await r.json() : null; const D = j && j.data;
    if (!D || D.day !== day || !Array.isArray(D.items)) { viAt.day = day; viAt.map = null; return; }
    const m = {}; D.items.forEach((x) => { const k = x.kind === 'surge' ? 'surge' : x.kind === 'vi' ? 'vi' : null; if (!k || !x.code || !x.t) return; const o = (m[x.code] = m[x.code] || {}); if (!o[k] || x.t < o[k]) o[k] = x.t; });
    viAt.day = day; viAt.map = m; }
  catch (e) { viAt.day = day; viAt.map = null; }
  if (root && st.data && st.data.day === day) { paint(st.data); chips(); }
}
// 그날 VI 목록 (11-19 재권님 「vi급등 지난것들 정보 받을수 있나? 발등한것과 발등조건 발등시간」 → 「응 해줘」) — 날짜를 고르면 그날 VI 발동 전부
//   값은 서버 /api/kis/vi-day?day=(개발2 019b957 · 평일 20:10 그날 것 · 지난 120일 되채움) 한 곳 · 화면은 받은 대로 그린다
//   meta.state 「안 받음」(아직 안 쌓은 날) · 「못 받음」 은 「0건」 과 가른다(0 으로 안 냄) · 「장중 쌓는 중」(오늘 20:10 전) · 「종목 채움」(지난 날 굳은 값 — 한 번 받아 둠)
//   KIS 가 전 시장은 하루 끝 30건만 줘서 서버가 셋(장중 본 오르는 VI · 그날 단타 판 종목 · 끝 30건)으로 모음(개발2 32e4358) — 전 종목 다는 아님을 머리 줄에 적음
const vdCache = {};
let vdSeq = 0;
async function vdLoad(day) {
  const box = root && root.querySelector('#dt-vi'); if (!box || !day) return;
  const sum = box.querySelector('.dt-vi-sum'), body = box.querySelector('.dw-body');
  let j = vdCache[day];
  if (!j) {
    const my = ++vdSeq; sum.textContent = '받는 중…';
    try { const r = await fetch(`/api/kis/vi-day?day=${encodeURIComponent(day)}`, { cache: 'no-store' }); j = r.ok ? await r.json() : { http: r.status }; }
    catch (e) { j = { http: '연결 안 됨' }; }
    if (my !== vdSeq) return;
    const M = (j && j.meta) || {}; if (M.state === '종목 채움' && st.days && day !== st.days[0]) vdCache[day] = j;
  }
  if (!st.data || st.data.day !== day) return;
  const M = (j && j.meta) || {}, rows = Array.isArray(j && j.data) ? j.data : null;
  if (!rows) { sum.textContent = j && j.http === 404 ? '서버 주소 아직 없음(404 · 서버 재시작 뒤 생김)' : `못 받음(${j && j.http != null ? j.http : j && j.error ? String(j.error).slice(0, 60) : '—'})`; body.innerHTML = ''; return; }
  if (M.state === '안 받음') { sum.textContent = `${dayTxt(day)} — 아직 안 쌓은 날(서버가 차례로 채움)`; body.innerHTML = ''; return; }
  if (M.state === '못 받음') { sum.textContent = `${dayTxt(day)} — 못 받음${M.error ? `(${M.error})` : ''}`; body.innerHTML = ''; return; }
  const storeAt = String((M.status && M.status.storeAt) || M.storeAt || '').slice(0, 5);   // 쌓는 시각은 서버 한 곳(meta.status.storeAt · 개념정의 6b02b9e 덧)
  const nIn = rows.filter((x) => x.regular === true).length, nOut = rows.filter((x) => x.regular === false).length;
  sum.textContent = `${dayTxt(day)} — ${num(rows.length)}건 · 정규장 ${num(nIn)} · 밖 ${num(nOut)}${rows.length - nIn - nOut ? ` · 모름 ${rows.length - nIn - nOut}` : ''}${M.state === '장중 쌓는 중' ? ` · 장중 쌓는 중(${storeAt ? `${storeAt} 에 ` : '저녁에 '}그날 것 채움)` : M.state === '종목 채움' ? ` · 전 종목이 아니라 서버가 물은 종목${Number(M.codes) > 0 ? ` ${num(M.codes)}` : ''}(시가총액 순위 · 단타 판 종목) · 장중 본 오르는 VI · 끝 30건` : M.state === '앞쪽 못 받음' ? ' · 하루 끝 30건만 받음 — 이른 시각이 빠졌을 수 있음' : ''}`;
  if (!rows.length) { body.innerHTML = '<div class="st-err">— 이 날 VI 0건</div>'; return; }
  const gap = (x) => { const g = x.kind === '동적' ? x.dynamicGap : x.kind === '정적' ? x.staticGap : [x.staticGap, x.dynamicGap].filter((v) => v != null).sort((a, b) => Math.abs(b) - Math.abs(a))[0];   // 둘 다면 큰 쪽(서버 알림 줄과 같게)
    if (g == null || !Number.isFinite(Number(g))) return '—'; const v = Math.abs(Number(g)); return x.up === true ? pct(v) : x.up === false ? pct(-v) : `${num(v, 2)}%`; };   // 부호는 서버 up(오름 · 내림)으로 · 모르면 부호 없이
  const base = (x) => num(x.kind === '동적' ? x.dynamicBase : x.staticBase != null ? x.staticBase : x.dynamicBase);
  body.innerHTML = `<div class="st-scroll dw-tw wheel-stop"><table class="dw-tb"><tr><th class="dw-l">발동</th><th class="dw-l">풀림</th><th class="dw-l">종목</th><th class="dw-l">조건</th><th class="dw-l">방향</th><th>발동가</th><th>기준가</th><th>기준가 대비</th><th>그날 몇 번째</th><th class="dw-l">장</th></tr>${rows.map((x) => {
    const m = x.regular === false ? ' dw-mut' : '';   // 정규장 밖은 흐리게 — 칸(td)마다 붙임(td 가 글자색을 따로 정해 줄(tr)에 붙이면 안 먹음 · 개념정의 f99bbe0 검수 덧)
    return `<tr><td class="dw-l${m}">${esc(x.at || '—')}</td><td class="dw-l${m}">${esc(x.cancel || '—')}</td><td class="dw-l${m}" data-co="${esc(x.code || '')}"><b>${esc(x.name || '—')}</b> <small>${esc(x.code || '')}</small></td><td class="dw-l${m}">${esc(x.kind || '—')}</td><td class="dw-l${m}">${x.up === true ? '오름' : x.up === false ? '내림' : '모름'}</td><td class="${m.trim()}">${num(x.price)}</td><td class="${m.trim()}">${base(x)}</td><td class="${m.trim()}">${gap(x)}</td><td class="${m.trim()}">${x.count != null ? num(x.count) : '—'}</td><td class="dw-l${m}">${x.regular === true ? '정규장' : x.regular === false ? '정규장 밖' : '모름'}</td></tr>`; }).join('')}</table></div>`;   // 감싸개 안에서만 옆으로 밀림 — 좁은 폭에서 페이지가 넘치지 않게(칩별 승률 표와 같음 · qa f99bbe0 검수)
}
// 11-18 서버가 줄마다 viAt · surgeAt(그날 처음 시각 · 지난 날 다시 센 판은 surgeApprox — 5분봉 「HH:MM~」 어림)을 준다 — 그것을 먼저 쓰고, 없을 때만 오늘 알림 목록으로
const viTxt = (r) => { const hm = (t) => String(t).slice(0, 5);
  if (r.viAt || r.surgeAt) return [r.viAt ? `VI ${hm(r.viAt)}` : '', r.surgeAt ? `급등 ${r.surgeApprox ? String(r.surgeAt) : hm(r.surgeAt)}` : ''].filter(Boolean).join(' · ');
  const o = viAt.map && viAt.day === (st.data && st.data.day) ? viAt.map[r.code] : null; if (!o) return '';
  return [o.vi ? `VI ${hm(o.vi)}` : '', o.surge ? `급등 ${hm(o.surge)}` : ''].filter(Boolean).join(' · '); };
// 그날 판에 서버가 못 받은 칩(data.meta.missing) — 재권님 11-12 「못가져온 값은 못가져온대로 하면될거같고 무슨값인지만 인지되도록」 · 이름은 서버가 준 그대로(목록이든 {칩: 까닭} 이든)
const names = (a) => (Array.isArray(a) ? a : a && typeof a === 'object' ? Object.keys(a) : []).map(String);
const missWord = () => (st.rebuilt ? '못 셈' : '못 받음');
// 굳힌 시각 — 서버 buyAt("09:01" · 「HHMM」 둘 다) 그대로 머리 · 설명 줄에(11-12 09:06 → 09:01 · 재권님 「9시 1분에 바로 단타 리스트 뜨도록」)
const atText = (v) => { const m = String(v || '').match(/^(\d{2}):?(\d{2})$/); if (m && root) root.querySelectorAll('.dt-at').forEach((e) => { e.textContent = `${m[1]}:${m[2]}`; }); };
// 하위 칩 보이는 이름 (11-19 재권님 「단타에 매수에 숫자가 있는데 숫자로 하지말고 사고있는 주체를 간단히 넣는 방향으로 해줘」 → 「응 좋아」) — 열쇠(서버 subs · 점수표 「매수|①」)는 그대로 · 화면 글자만 · 풀어 쓴 설명은 TIP 그대로
//   이름 · 풀어 쓴 뜻은 서버 한 곳(kis_proxy.JOINT_TIER_NAME → 판 meta.subNames · meta.subTips · 개발2 · 11-20 재권님 「고치면 될거같아」) — 받은 판의 값을 둠(서버 고침 전 지은 지난 판도 같은 이름으로) · 한 번도 못 받으면 열쇠(①~④) 그대로
export const SUB_NAME = {}, SUB_TIP = {};
export const subName = (c, x) => SUB_NAME[`${c}|${x}`] || x;
const subTxt = (c, sb) => sb.map((x) => subName(c, x)).join(sb.some((x) => SUB_NAME[`${c}|${x}`]) ? ' / ' : '·');   // 이름 안에 「·」 가 있어 여럿이면 「 / 」 로 가름
const tipAt = (k) => { const t = tipOf(k); return t ? ` data-tip="${esc(t)}"` : ''; };
function chipPanel(all) {
  return colsOf().map((c) => { const i = colorOf(c);
    const n = all.filter((r) => (r.chips || []).includes(c)).length;
    const subs = GRP_CHIPS.includes(c) ? [] : subOrder(c, [...new Set(all.flatMap((r) => subsOf(r, c)))]);   // 묶음 칩은 좁은 폭에서도 업종 · 테마 목록 없이 단추만(11-26 재권님 「돈몰림 미국장 여기아래로 목록 나올필요는 없어 종목옆에만 있으면되」 · 넓은 폭 grpHead 와 같게)
    const on = !st.off.has(c);
    // data-i — 칩마다 색(strategy.css 의 .dt-cg[data-i] · theme.css 변수) · 하위 칩은 상위 칩 색을 물려받음
    const ms = st.miss.has(c), tip = ms ? ` data-tip="${esc(`그날 판에 ${c} 값을 ${missWord()} — 걸린 종목이 있어도 0 으로 셈됨${tipOf(c) ? `\n${tipOf(c)}` : ''}`)}"` : tipAt(c);
    return `<span class="dt-cg${on ? '' : ' is-off'}${ms ? ' is-miss' : ''}" data-i="${i}"><button type="button" class="dt-mc${on ? ' is-on' : ''}" data-chip="${esc(c)}"${tip} aria-pressed="${on}">${esc(c)}${ms ? '' : `<b>${n}</b>`}</button>${
      subs.length ? `<span class="dt-subs">${subs.map((x) => { const k = `${c}|${x}`, son = on && !st.subOff.has(k); return `<button type="button" class="dt-sub-chip${son ? ' is-on' : ''}" data-sub="${esc(k)}"${tipAt(k)} aria-pressed="${son}"${on ? '' : ' disabled'}>${esc(subName(c, x))}<b>${all.filter((r) => subsOf(r, c).includes(x)).length}</b></button>`; }).join('')}</span>` : ''}</span>`;
  }).join('');
}

// 파는 룰 (11-11 재권님 「매수가 대비 1%이상 하락은 매도한다. 상승추세가 꺾이면 판다 라는룰을 추가해서 표기해줘. 표기된 부분부터는 평균에 포함시키지 않는다」)
//   · 30분 시각마다 본다(값이 30분마다라서) — ① 매수가 대비 STOP_PCT% 이하면 판다 ② 앞 시각에 매수가보다 위였는데 이번 시각이 앞 시각보다 낮으면 「상승추세 꺾임」 으로 판다
//   · 판 시각 칸에 「손절」 · 「꺾임」 을 붙이고, 그 칸부터는 흐리게 · 평균에서 뺀다 · 「결과」 칸 = 판 시각 값(안 팔았으면 마지막 시각 값)
//   · ② 「꺾임」 = 앞 시각보다 낮아지면(재권님 11-11 「낮아지면으로 해」) · 숫자는 룰 문서로 옮길 때까지 이 한 곳
// 파는 룰 값을 재권님이 넣는 칸으로 (11-18 재권님 「값을 내가 넣으면 거기에 맞게 소팅되야해 … 파는룰도 내가 바꾸면서 볼려고 하는거야」)
//   · 손절 % (빈칸이면 손절 안 함) · 꺾임 켬/끔 · 고점 대비 −X% (빈칸이면 안 씀 — 11-18 「상승중에 -2%가 되면 매도」 · 매수가보다 오른 뒤 그때까지 가장 높던 값에서 X% 내리면 판다)
//   · 기본값은 지금 룰 그대로(손절 −1 · 꺾임 켬 · 고점 빈칸) — 값은 서버 /api/kis/chip-rules meta.sellDef 한 곳(SELL_DEF · 11-20 「가」) · 넣은 값은 룰 문서(rules.dt30) 한 곳에 저장
// 매수 타이밍 (11-18 재권님 「매수 타이밍을 9시1분 과 vi발동 두개를 고를수 있게 해줘. 그것에 맞춰서 차익도 달라지게」 → (가) 「그뒤 30분이 아니고 시간으로 30분단위로」)
//   · open = 서버 매수가(09:00 시가) · p1 = rows[].px1(09:01 · 개발2) · vi = rows[].viPx(VI 걸린 때 값 · 개발2) — 값이 없는 종목은 안 산다(몫도 안 나눔 · 0 으로 안 봄)
//   · 파는 룰은 시계 30분 칸(09:30 · 10:00 …) 중 산 시각 뒤 칸부터 본다 — 산 시각 앞 칸은 비움
// 사는 시각 고르기 (11-19 재권님 「사는 시간도 쓸수있게 해줘 9시 1분~ 5분 사이에 살거야」 → 「늦게 여는 시간만큼 늦춰줘」) — p1~p5 = 여는 시각 + 1~5분 · 값은 서버 rows[].pxMin["N"] · 시각은 meta.pxMinAt["N"](개발2 5d6c962)
//   · 열쇠 p1 은 옛 「09:01」 그대로(저장해 둔 셈 칸이 안 깨짐) · pxMin 이 없는 옛 판은 p1 만 px1 로 · p2~p5 는 「서버 값 아직」(0 으로 안 봄 · 안 삼)
const PMIN = [1, 2, 3, 4, 5];
// 매수 고르기 둘(11-23 재권님 「매수칸에 매수에 들어온때와 9시1분만 남기고 9시 1분의 이름을 9시1분~5분사이 들어온 종목 이라고 바꿔. 그 앞에 들어온때는 바꾼이름 뒤로 하고」 · 개발2 창 09:2x)
//   p1 — 여는 시각+1분 전에 든 종목은 9시 1분 값 · 그 뒤 ~ inUntil(HHMM 의 59초)에 든 종목은 든 때 가격(r.buy) · 그 뒤는 안 삼(재권님 「9시 1분부터 5분까지는 들어올때 산다 라는룰로」)
//   open — 들어온 때(옛 판은 여는 시각 시가) · 빠진 고르기(9시 2~5분 · VI)로 저장된 셈 칸은 p1 로 읽음(재권님 지시에 없음 · 시황분석1 이 정함 — 9시 1분 몫을 넓힌 룰이라)
const BUYS = [['p1', '9시1분~5분사이 들어온 종목'], ['open', '들어온 때']];
const buyKey = () => { const k = st.set.buy || 'open'; return BUYS.some(([x]) => x === k) ? k : 'p1'; };
// inUntil — 9시 1분 몫의 끝 분(HHMM) · 셈 칸 값 우선 · 없으면 서버 /api/kis/chip-rules meta.sellDef.inUntil(개발2) · 못 받으면 ''(그때는 9시 1분 뒤 든 종목은 안 삼 — 짐작 안 함)
//   늦게 여는 날(수능 등)은 여는 시각이 늦은 분만큼 뒤로 밂 — 「9시 1분」 은 여는 시각 + 1분(개념정의 덧 · 승률 표 서버 셈 개발2 1ec832e 와 같게)
const inUntil = () => { let v = String(st.set.inUntil || SELL_DEF.inUntil || '').replace(/:/g, ''); if (/^\d{3}$/.test(v)) v = `0${v}`; if (!/^\d{4}$/.test(v)) return '';   // 「9:05」 · 「905」 는 앞 0 을 채워 읽음(서버 8315a24 와 같게 · 개념정의 덧)
  const o = openHM(), late = (+o.slice(0, 2) * 60 + +o.slice(2)) - 540; return late > 0 ? addHM(v, late) : v; };
const pmOf = (k) => (/^p[1-5]$/.test(k || '') ? +k.slice(1) : 0);
const minHM = (n) => { const o = String((DM().pxMinAt || {})[n] || '').replace(':', ''); return /^\d{4}$/.test(o) ? o : n === 1 ? p1HM() : addHM(openHM(), n); };
const minVal = (r, n) => (Number(n) === 1 && Number(r.px1Db) > 0 ? { px: Number(r.px1Db), at: hmS(minHM(1)), src: 'db' } : r.pxMin && typeof r.pxMin === 'object' ? r.pxMin[n] : n === 1 ? r.px1 : undefined);   // 9시 1분 값은 서버 rows[].px1Db(여는 분 1분봉 종가 · chipPx 와 같은 셈) 먼저 — 판 pxMin[1] 은 장중 덜 쌓인 봉으로 적혀 갈린 줄이 있었음(대주전자재료 86,900 ↔ 87,900 · 개발2 62875e4 · 11-26)   // undefined = 서버가 이 칸을 아직 안 줌 · null = 못 잼
// 새 매수가 규칙(11-20 · 서버 개발2)으로 지은 판 — 줄에 buyTs · buySrc 「9시 1분 값」 이 있으면 기본 매수가는 「들어온 때」 가격 · 옛 판(11-19 까지)은 시가
const newBuyOf = (d) => ((d && d.rows) || []).some((r) => r.buyTs || /9시 1분/.test(String(r.buySrc || '')));
const buyName = (k, t) => (k === 'open' ? (st.data && st.data.flat930 ? `칩 ${num(chipNeed())}개 찬 때` : newBuyOf(st.data) ? '들어온 때' : `${hmS(openHM())} 시가`) : t);   // 「들어온 때」 — 11-20 재권님 「응 그렇게 해」(옛 판만 「09:00 시가」)
const hhmm = (t) => String(t || '').replace(/:/g, '').slice(0, 4);
// 들어온 때(초까지 · 서버 buyTs · 없으면 buyAt 의 0초) — 새 매수가 규칙 판만(옛 판 buyAt 은 여는 시각이라 안 가름)
const inTs = (r) => { const t = String(r.buyTs || '').replace(/:/g, ''), a = hhmm(r.buyAt); return /^\d{6}$/.test(t) ? t : /^\d{4}$/.test(a) ? `${a}00` : ''; };
// 고른 매수 시각 at(HH:MM · HH:MM:SS) 에 판에 아직 없었나 → 들어온 시각 글 | ''
//   9시 1분 몫이면 at 대신 inUntil 59초까지를 「아직 안 듦」 경계로(그 사이 든 종목은 든 때 가격에 삼)
const notYetIn = (r, at) => { if (pmOf(buyKey()) === 1 && Number(r.lock) > 0) return '';   // 굳힌 줄은 든 때 산 것(11-23)
  if (pmOf(buyKey()) === 1 && inUntil()) at = `${inUntil()}59`; const e = inTs(r), a = String(at || '').replace(/:/g, '').padEnd(6, '0').slice(0, 6); return newBuyOf(curD()) && e && /^\d{6}$/.test(a) && a < e ? (r.buyTs ? String(r.buyTs) : hmS(hhmm(r.buyAt))) : ''; };
let FILL = new WeakSet();   // 그 날 셈에서 칩 N−1개로 채운 줄(11-24 · calcDay 가 날마다 새로)
const chipNeed = (r) => Math.max(1, (Number(st.set.minChip) || 1) - (r && FILL.has(r) ? 1 : 0));   // r — 채운 줄이면 N−1(그 줄의 사는 순간 · 찬 시각도 N−1 번째 칩으로)
// 켜진 칩이 붙은 시각을 세워 N번째(칩 수 기준) — HHMM · 시각 모르는 칩은 그 줄이 판에 처음 든 때로 봄(칩은 든 때보다 앞설 수 없음 · 든 때도 모르면 장 시작 전) · 칩이 모자라면 null
// 칩 시각은 서버 rows[].chipTime(칩마다 처음 붙은 시각 · 한 번 붙었다 빠져도 남음 · 개발2 a3ea7ff)이 있으면 그것 먼저
// 칩 조합(11-26 재권님 「칩선택에서 지금은 개수만 있어서 조합을 만들수가 없어서 조합에 대한 정보를 단타판 조합에 갱신하고 해당 조합이 되면 종목의 이름색이 빨간색으로」 → 안에 「응 해」)
//   조합 = 그 시각에 함께 붙어 있던 켜진 칩 묶음(칩 칸 차례 · 「 + 」 로 이음) · 구간 없는 판은 그 시각까지 처음 붙은 칩 전부 · 고른 조합은 셈 칸 set.combos(화면 칩 이름)
//   종목이 고른 조합 중 하나가 된 첫 시각 = comboHit · 「조합으로 사기」(set.comboOn)를 켜면 칩 N개 대신 그 시각에 삼(nthChipAt 이 그 시각을 냄 · 값 셈은 칩 N개와 같은 길)
// 시각이 없어도 되는 칩 — 장 전에 앞 날 · 밤 값으로 정해지는 칩(자동 = 앞 거래일 거래량 급등 · 프리장 · 미국강세)은 시각이 없으면 장 시작 전(0000)으로 봄
//   그 밖(거래비율 둘 · 초반상승 · VI 등 장중에 붙는 칩)은 시각이 있어야 함 — 없으면 그 종목은 조합 셈에서 뺌(11-26 재권님 「시각 없는 칩중 없어도 되는것과 있어야 되는것도 구분해서」)
const NO_TIME_OK = ['자동', '프리장', '미국강세'];
const chipTsOf = (r) => { const at = { ...(r.chipAt || {}), ...(r.chipTime || {}) }, o = {}; colsOf().filter((c) => everChip(r, c)).forEach((c) => { o[c] = String(at[c] || (c === 'VI·급등' ? r.viAt || '' : '')).replace(/:/g, '').slice(0, 4) || (NO_TIME_OK.includes(c) ? '0000' : inTs(r).slice(0, 4) || '0000'); }); return o; };
const comboEvents = (r) => { if (spanRow(r)) return spanTs(r).map((t) => [t, colsOf().filter((c) => chipAtT(r, c, t))]); const o = chipTsOf(r); return [...new Set(Object.values(o))].sort().map((t) => [t, colsOf().filter((c) => o[c] != null && o[c] <= t)]); };
const comboKey = (cs) => cs.join(' + ');
// 고른 조합은 화면 칩 이름으로 저장(set.combos) — 칩 이름 다리 표(strategy-chipname.js)를 걷는 날 저장된 조합 이름도 함께 옮김(개념정의 덧 11-26)
//   자동(set.comboAuto · 기본) — 지난 판 셈(st.cbStat)에서 문턱(오른 비율 · 건수)을 넘는 조합 전부 · 판을 열면 뒤에서 셈해 이름에 바로 적용(11-26 재권님 「이것도 단타판 종목이름에 적용되어야해」)
//   체크를 손으로 넣고 빼면 「직접 고름」(set.combos) · 「문턱 넘는 조합 고르기」 를 누르면 다시 자동
let cbAutoMemo = { k: '', v: new Set() };
const comboAutoSel = () => { const C = st.cbStat, S = st.set; if (!C || C.busy || S.comboUp == null || S.comboN == null) return new Set();
  const k = `${C.sig}|${C.used.length}|${S.comboUp}|${S.comboN}`; if (cbAutoMemo.k !== k) cbAutoMemo = { k, v: new Set(C.rows.filter((o) => o.upPct >= Number(S.comboUp) && o.cnt >= Number(S.comboN)).map((o) => o.key)) }; return cbAutoMemo.v; };
// 서버가 고른 조합 · 줄마다 조합 산 값(개발2 143916b · 재권님 「칩 조합 된것들도 서버에 있어야 할거같은데 하루하루 칩조합 승률을 갱신하고 그것중 70%이상만 단타창에서 적용한다」 → 「가」 11-26)
//   판 meta.comboPick{up · n · sig · keys · from · why} · rows[].comboBuy{key · chips · at 초 · buyAt · px · src} | null — 저장된 셈 칸(저장 전 아님 · 자동 · 문턱 · 켠 칩이 같음)일 때만 그대로 · 아니면 화면 셈
const chipsSaved = () => st.chipSig == null || chipSig() === st.chipSig;   // 켠 칩 · 하위 칩이 불러온(저장된) 그대로인가 — 서버 sig 글자와 견주면 칩 목록(장외 · 수급 등) 차이로 늘 갈렸음(qa 11-26 d58efb2 크로스 검수 · 서버 고르기는 저장 문서로 셈)
const svPick = () => { const P = ((curD() || {}).meta || {}).comboPick, S = st.set; return !st.setDirty && S.comboAuto !== false && P && Array.isArray(P.keys) && P.keys.length && Number(S.comboUp) === Number(P.up) && Number(S.comboN) === Number(P.n) && chipsSaved() ? P : null; };
const svKey = (k) => String(k || '').split(' + ').map(chipName).join(' + ');   // 서버 칩 이름 → 화면 이름
const comboSel = () => { const P = svPick(); if (P) return new Set(P.keys.map(svKey)); return st.set.comboAuto !== false ? comboAutoSel() : new Set(Array.isArray(st.set.combos) ? st.set.combos : []); };
const comboPending = () => !!st.set.comboOn && st.set.comboAuto !== false && (!st.cbStat || !!st.cbStat.busy);   // 자동 조합으로 사는데 지난 판 셈이 아직 — 그동안은 아무것도 안 삼(칩 N개로 샀다가 바뀌어 보이지 않게 · 개념정의 덧 11-26)
const comboMode = () => !!st.set.comboOn && (comboSel().size > 0 || comboPending());
// 조합이 됐다 = 그 시각 붙어 있던 켜진 칩이 고른 조합의 칩을 다 품음 — 칩이 더 있어도 됨(11-26 재권님 「「고른 조합을 다 품으면 됨(칩이 더 있어도 됨)」당연히 이렇게 되야할거같은데」 · 11-03 한진칼이 09:00 에 셋이 한꺼번에 붙어 둘짜리 조합을 안 거쳤음)
//   여럿을 품으면 가장 먼저 품은 시각 · 같은 시각이면 칩이 많은 조합 이름
let cbSelMemo = { s: null, v: [] };
const comboSelArr = (S) => { if (cbSelMemo.s !== S) cbSelMemo = { s: S, v: [...S].map((k) => [k, k.split(' + ')]).sort((a, b) => b[1].length - a[1].length) }; return cbSelMemo.v; };
const comboHit = (r) => { if (svPick()) { const B = r.comboBuy; return B && B.at ? { t: hm4(B.at), key: svKey(B.key) } : null; }   // 서버가 고른 판이면 서버 조합 시각 그대로
  const S = comboSel(); if (!S.size) return null; const A = comboSelArr(S); for (const [t, cs] of comboEvents(r)) { if (!cs.length) continue; const has = new Set(cs), h = A.find(([, ks]) => ks.every((c) => has.has(c))); if (h) return { t, key: h[0] }; } return null; };
// 칩 묶음의 부분 묶음 열쇠(차례는 cs 그대로 · 칩 CB_SUB_MAX 개까지) — 조합 셈이 「그 조합을 처음 품은 때」 로 세게
const CB_SUB_MAX = 6;
const subKeys = (cs) => { const out = []; const go = (i, pick) => { if (pick.length) out.push(comboKey(pick)); if (pick.length >= CB_SUB_MAX) return; for (let j = i; j < cs.length; j++) go(j + 1, [...pick, cs[j]]); }; go(0, []); return out; };
const needTxt = (r) => { const X = CONDX.get(r) || { why: [] }, w = X.why.length ? ` · ${X.why.map((k) => (k === '유통' ? '유통 대비 거래' : '전일 대비 거래량')).join(' · ')} 넘은 때` : ''; return `${comboMode() ? '조합 된 때' : `칩 ${chipNeed(r)}개 찬 때`}${w}${X.approx ? ' · 거래 칸 어림' : ''}`; };   // 매수가 글 — 조합으로 살 때는 「조합 된 때」
const chipOnlyAt = (r) => { if (comboMode()) { const h = comboHit(r); return h ? h.t : null; }
  if (spanRow(r)) { const N = chipNeed(r); return spanTs(r).find((t) => nAtT(r, t) >= N) || null; }   // 구간이 있으면 칩 N개가 함께 붙어 있던 첫 시각
  const at = { ...(r.chipAt || {}), ...(r.chipTime || {}) }; const ts = colsOf().filter((c) => everChip(r, c)).map((c) => String(at[c] || (c === 'VI·급등' ? r.viAt || '' : '')).replace(/:/g, '').slice(0, 4) || inTs(r).slice(0, 4) || '0000').sort(); const N = chipNeed(r); return ts.length >= N ? ts[N - 1] : null; };
// 거래 칸 문턱을 넘은 첫 분(11-26 재권님 「0.1로 해놓으면 해당종목이 0.1이상이 된기점 같은데 계산으로 되어있어야」 · 「전일 거래량이 얼마인지는 정보가 있을거고 유통 거래량을 체크하면 어제보다 현재 얼마인지로 알수있지않나?」 → 「응 만들어」)
//   유통 대비 거래 — 서버 rows[].turnMin {i: {at, turn}}(분마다 거래 비율 · 지금은 09:01~09:30)에서 문턱을 넘은 첫 분
//   전일 거래량 대비 — 분마다 거래량이 없어 어림: 끝 전일 대비 %(accVol ÷ prevDayVol) × (그 분 거래 비율 ÷ 끝 거래 비율) · 거래대금 흐름으로 거래량 흐름을 짐작(주가가 크게 움직이면 어긋남)
//   분마다 값 안에서 못 넘었는데 끝 값은 넘은 종목 — 넘은 분을 모름 → 칩 찬 때 그대로 · 「어림」(서버가 프리장~종가 분마다 값을 쌓으면 정확히 · 개발2 카드 11-26)
//   사는 때 = 칩 찬 때 · 두 칸이 넘은 때 중 가장 늦은 때 · 켜진 칸만(거르기 칸과 같은 켬 · % 값)
let CONDX = new WeakMap();   // 줄 → { why: ['유통' | '전일'], approx: bool } — 매수가 글에 적음 · calcDay 마다 새로
const turnSer = (r) => (r.turnMin && typeof r.turnMin === 'object' ? Object.values(r.turnMin).filter((o) => o && o.at && Number.isFinite(Number(o.turn))).map((o) => [hm4(o.at), Number(o.turn)]).sort((a, b) => (a[0] < b[0] ? -1 : 1)) : []);
const crossAt = (ser, f, min) => { for (const [t, v] of ser) { const x = f(v); if (x != null && x >= min) return t; } return null; };
const condAt = (r, T) => { const S = st.set, X = { why: [], approx: false }; let at = T;
  const ser = turnSer(r), tEnd = Number(r.turn);
  if (S.turnOn && S.turnMin > 0) { const c = crossAt(ser, (v) => v, S.turnMin); if (c) { if (c > at) { at = c; X.why.push('유통'); } } else X.approx = true; }
  if (S.volOn && S.volMin > 0) { const a = Number(r.accVol), b = Number(r.prevDayVol), E = a > 0 && b > 0 ? a / b * 100 : null;
    const c = E != null && tEnd > 0 ? crossAt(ser, (v) => E * v / tEnd, S.volMin) : null;
    if (c) { if (c > at) { at = c; X.why = X.why.filter((w) => w !== '유통'); X.why.push('전일'); } X.approx = true; } else X.approx = true; }   // 전일 칸은 늘 어림
  CONDX.set(r, X); return at; };
const nthChipAt = (r) => { const T = chipOnlyAt(r); return T == null ? null : condAt(r, T); };
// 보기만 줄의 가정 매수 — 판에 들어올 때 값(서버 r.buy)으로 샀다고 치고 셈만 보임(11-24 재권님 「들어올때 샀다는 전제로 셈을 하도록 하고 진짜 산건 아닌거처럼 해줘」) · 합계 · 평균 · 상위 N 에는 안 듦
// 칩이 다 찬 순간의 값 — 서버 dt30._moment_px 와 같은 갈래(개발2 8a0e2af · qa 11-26 「시계 칩은 T:ss 에 앎 · T:00 값은 앞당김」)
//   그 분(T)에 붙은 켜진 칩 중 가장 늦게 안 초(rows[].chipSec{칩: {HH:MM: HH:MM:SS}}) → 그 순간 본 값(rows[].seenPx[초]) · 없으면 정각(00초)이면 앞 분 1분봉 종가 · 그 밖은 그 분 1분봉 종가(chipPx[T])
//   서버는 「조합이 다 찬 칩」 중 가장 늦은 초 · 화면은 그 분에 새로 붙은 켜진 칩 전부 중 가장 늦은 초(같은 분 다른 칩이 더 늦으면 조금 늦은 값 · 미래는 안 봄) · 서버가 주면 안 씀(buy930 · comboBuy)
const momentPx = (r, T, only, need) => {   // only — 조합 칩(화면 이름 배열) · 주면 그 칩만으로 가름(서버 143916b 「조합 · 칩 N개를 채운 칩만으로」 · 칩 N개는 그 분에 새로 붙은 칩이 곧 채운 칩)
  const hm = hmS(T), CS = r.chipSec || {}, SP = r.seenPx || {}, on = new Set(colsOf()); let sec = null; const onlyS = only ? new Set(only) : null; const newOn0 = spanRow(r) ? colsOf().filter((c) => everChip(r, c) && spansOf(r, c).some(([a]) => hm4(a) === T)) : (() => { const o = chipTsOf(r); return Object.keys(o).filter((c) => o[c] === T); })(); const newOn = onlyS ? newOn0.filter((c) => onlyS.has(c)) : newOn0;   // 구간 없는 줄은 처음 시각으로(서버 done 과 같게 · 개념정의 덧 11-26)
  Object.entries(CS).forEach(([c, o]) => { const cn = chipName(c); if (!on.has(cn) || !everChip(r, cn) || (onlyS && !onlyS.has(cn))) return; if (spanRow(r) && !spansOf(r, cn).some(([a]) => hm4(a) === T)) return; const s = o && o[hm]; if (s && (!sec || s > sec)) sec = s; });   // 그 분에 새로 붙은 칩만(이미 붙어 있던 칩의 다시 본 초는 안 셈)
  const secs = newOn.map((c) => { const o = CS[serverChip(c)] || CS[c]; return o && o[hm]; }).filter(Boolean).sort();
  const prior = need ? (onlyS ? [...onlyS] : colsOf()).filter((c) => everChip(r, c) && !newOn.includes(c) && (spanRow(r) ? chipAtT(r, c, T) : (chipTsOf(r)[c] || '9999') < T)).length : 0;
  const kth = need ? Math.max(1, need - prior) : 0; if (kth && secs[kth - 1]) sec = secs[kth - 1];   // 서버 _moment_px need 셈(개발2 11-26 — 그 분 칩 초를 차례로 세워 need − 앞서 붙어 있던 칩 수 번째가 순간)
  if (sec && Number(SP[sec]) > 0) return { px: Number(SP[sec]), how: `${sec} 본 값` };
  const prev = hmS(addHM(T, -1)), C = r.chipPx || {};
  const allSec = newOn.length > 0 && secs.length >= (kth ? Math.min(kth, newOn.length) : newOn.length);   // 그 분에 새로 붙은 칩이 모두 초를 알 때만 정각 값(서버 len(secs) == len(done) 과 같게 · 개념정의 덧 11-26)
  if (sec && allSec && /:00$/.test(sec) && Number(C[prev]) > 0) return { px: Number(C[prev]), how: `${sec} 정각 값` };
  const v = Number(C[hm]); return v > 0 ? { px: v, how: `${hm} 1분봉` } : null; };
// 조합 된 분의 상승률 — 그 분 산 값(buyOf · 서버 comboBuy 가 있으면 그 값) ÷ 시가 · 지나간 분 값이라 한 번 정해지면 안 바뀜 · 어림 · 대체 값이면 못 잼(null · 0 으로 안 봄 → 같은 분 맨 뒤)
const comboRise = (r) => { const B = buyOf(r), o = Number(r.open); return B && Number(B.px) > 0 && o > 0 && !/어림|대체/.test(B.src || '') ? (Number(B.px) / o - 1) * 100 : null; };
let SVNO = new WeakSet();   // 서버 산 값이 없는 줄(저장된 셈 칸으로 서버가 안 삼) · 매수가 칸 「서버 산 값 없음 · 안 삼」 · calcDay 마다 새로
let NOPX = new WeakMap();   // 칩 찬 분의 1분봉 값이 서버에 없는 줄 → 그 시각(HH:MM) · 매수가 칸 「매수값 미확인」 · calcDay 마다 새로
let HYPO = new WeakMap();   // calcDay 를 돌 때마다 새로 — 판 줄 객체가 다시 그릴 때 그대로 쓰여, 셈 칸을 바꿔 본 표로 든 줄에 가정 값이 남지 않게(개념정의 검수 11-24)
function buyOf(r) {   // → { px, at(HHMM), src } | null
  if (HYPO.has(r)) return HYPO.get(r);
  if (curD() && (curD().fb905 || fbDays.has(curD().day))) return fb905Of(r);
  // 서버가 산 줄을 정해 주는 판(meta.buy930 이 있는 판)에서 rows[].buy930 이 없는 줄은 안 삼 — 서버 셈으로 칩 N개가 안 찬 종목(개발2 11-24 · 화면이 30분 칸으로 파는 셈을 따로 하지 않게)
  //   셈 칸을 고치고 아직 저장 전이면(st.setDirty) 서버 buy930 은 저장된 값으로 센 것이라 이 거름을 쓰지 않음 — 화면 셈만(개념정의 덧 11-24)
  // 서버 buy930 이 안 산 줄을 안 사던 거름은 걷음 — 11-24 재권님 「서버는 정보만 있고 셈은 화면에서 한다」 · 사는지는 아래 화면 셈(칩 N개 찬 때)이 정함
  const k = buyKey();
  const n = pmOf(k);
  // 9시 1분 몫 — 여는 시각+1분 ~ inUntil 59초 사이에 든 종목은 든 때 가격(서버 r.buy)
  // 창(11-23 서버 253689d) — 창에 든 줄은 필터에 든 분 1분봉 값(서버 r.buy · winAt) · 문턱 밑 줄(lock 없음)은 안 삼
  if (n === 1 && winMode()) { if (!(Number(r.lock) > 0) || !(Number(r.buy) > 0)) return null; const w = String(r.winAt || r.buyAt || '').replace(/:/g, ''); return { px: Number(r.buy), at: w.slice(0, 4), src: w.length >= 4 ? `${w.slice(0, 2)}:${w.slice(2, 4)} 창 1분봉` : '창 1분봉' }; }
  // 굳힘 없앤 판(flat930 · 11-23) — 칩 수 기준(셈 칸 「칩 N개 이상」 · 빈칸 = 1)을 넘은 순간에 삼(재권님 「내가 칩 갯수 바꿀때마다 사는게 바뀌게 되야돼」)
  //   그 순간 = 켜진 칩을 붙은 시각(chipAt · VI 는 viAt · 시각 모름 = 장 시작 전)으로 세운 N번째 · 09:01 전이면 9시 1분 값 · 09:01~09:05 는 그 분 값(pxMin)
  //   그 뒤는 판에 든 때가 그 순간 이후면 든 때 값(r.buy) · 아니면 그 순간 뒤 첫 30분 칸 값(그 분 값을 서버가 안 줌 — 짐작 안 함 · 칸 이름에 적음)
  // 「들어온 때」(open)도 굳힘 없앤 판에서는 칩 N개가 함께 붙은 때 삼(11-25 재권님 「매수에 칩이 ()개 이상 붙었을때 로 하고 붙은시간에 셈하는걸로 개선해줘」 — 판에 든 때 값이 아니라)
  if ((n === 1 || k === 'open') && curD() && curD().flat930) { const T = nthChipAt(r); if (T == null) return null;
    if (T > chipUntil().replace(':', '') && !st.set.buyLate930) return null;   // 09:30 뒤에 칩이 찬 종목 — 셈 칸 「삼 / 안 삼」(set.buyLate930 · 기본 안 삼 = 서버 buy930 · 승률 표와 같음) · 재권님 「살지말지 내가 정할수 있어야해」(11-23 19:4x)
    // 9시 1분 · 1~5분 값이 없는 날(1분봉은 11-12 부터 쌓임)은 안 사지 않고 아래 「든 때 → 다음 30분 칸」 으로 — 서버 buy930 과 같은 차례(11-23 재권님 「누락된 이유가 뭐지? 코드가 뭔가 일괄적이지 않은거 같은데」 → 「응」)
    // 9시 1분 이하에 찬 줄 — 들어온 때(open) 모드는 r.buy(든 순간 현재가 · 장 전부터 있던 줄은 여는 시각+1분 직후 현재가) · 칩 찬 때(p1) 모드는 9시 1분 값 — 서버 buy930 과 같은 셈(개발2 buy_point · 11-25 qa 제일기획 19,210 ↔ 19,200)
    // 9시 1분 이하에 찬 줄은 「들어온 때」 모드도 9시 1분 값(11-26 재권님 「칩을 바꾸면 바꾼칩갯수가 다찬시간에 매수가 되야하는데」 → 「응」 — 판에 든 때 값(r.buy)으로 사던 것 걷음 · RFHIC 08:05 찬 줄을 09:45 값으로 샀음) · 서버 buy930 은 아직 든 때 값(개발2 에 알림)
    const p1 = minHM(1);
    // 저장된 셈 칸 · 칩 N개로 살 때는 서버가 줄마다 정한 산 값(rows[].buy930 · 개발2 _moment_px)을 그대로(11-26 재권님 「서버값과 항상 동기화 되야돼 엄청 중요한거야」 → 「가」) · 저장 전 · 칩조합 · 서버 값 없음만 아래 화면 셈(같은 갈래)
    if (comboMode() && svPick()) { const B = r.comboBuy; if (B && Number(B.px) > 0) return { px: Number(B.px), at: hm4(B.at), src: `${B.at} ${B.src || ''} · 조합 된 때 · 서버 값` }; if (B && B.at) NOPX.set(r, `${hmS(hm4(B.at))} 서버 값 없음`); return null; }   // 조합은 됐는데 서버 산 값이 없으면 「매수값 미확인」(qa ecd26ab 검수 ① · 재권님 「못 잰 종목이 나와야 사야되는데」)   // 칩조합 — 서버 조합 산 값 그대로
    // 서버가 저장된 셈 칸 · 같은 사는 때(meta.buy930.mode)로 셈한 판이면 두 사는 때 다 서버 산 값만 — 없는 종목은 서버가 안 산 것 · 화면이 따로 셈하지 않음(11-26 재권님 「서버값은 없으면 안되는건데」 → 「응 맞아」 · 단타 리뷰 ① ⑵) · 저장 전 고침 · 칩 바꿈만 아래 화면 셈
    const B9 = (curD().meta || {}).buy930;
    if (!st.setDirty && chipsSaved() && !comboMode() && B9 && B9.mode === k) { const b9 = r.buy930; if (b9 && Number(b9.px) > 0) { const a9 = String(b9.atSec || b9.at || ''); return { px: Number(b9.px), at: hm4(a9), src: `${a9} ${b9.src || ''} · ${needTxt(r)} · 서버 값` }; } SVNO.add(r); return null; }
    if (!st.setDirty && k === 'open' && !comboMode() && r.buy930 && Number(r.buy930.px) > 0) { const b9 = r.buy930, a9 = String(b9.atSec || b9.at || ''); return { px: Number(b9.px), at: hm4(a9), src: `${a9} ${b9.src || ''} · ${needTxt(r)} · 서버 값` }; }   // 사는 때 기록이 없는 옛 판
    // 9시 1분 전에 찬 줄만 9시 1분 값 · 9시 1분 분에 찬 줄은 아래 순간 값(서버 _moment_px 와 같게 · 정각이면 같은 9시 1분 값)
    if (T < p1) { const o = minVal(r, 1); if (o && Number(o.px) > 0) return { px: Number(o.px), at: p1, src: `${hmS(p1)} 값 · ${needTxt(r)} ${hmS(T)}` }; }
    const CPM = (curD().meta || {}).chipPx;   // 서버 칩 찬 분 1분봉 값 — {ok} 인 판만 쓴다 · {ok:false} 면 아래 옛 셈(어림)
    if ((CPM && CPM.ok !== false) || r.chipPx) { const ck = comboMode() ? ((comboHit(r) || {}).key || '').split(' + ').filter(Boolean) : null; const M = momentPx(r, T, ck, ck ? ck.length : chipNeed(r)); if (M) return { px: M.px, at: T, src: `${M.how} · ${needTxt(r)}` };
      if ((CONDX.get(r) || { why: [] }).why.length) { const bc = (Array.isArray(r.bars) ? r.bars : []).find((b) => Array.isArray(b) && hm4(b[0]) === T), bv = bc && Number(bc[4]); if (bv > 0) return { px: bv, at: T, src: `${hmS(T)} 1분봉 · ${needTxt(r)}` }; const t2 = ((curD().times) || []).find((x) => hhmm(x) >= T), v2 = t2 && Number((r.px || {})[t2]); if (v2 > 0) return { px: v2, at: hhmm(t2), src: `${hmS(hhmm(t2))} 칸 값 · ${needTxt(r)} ${hmS(T)} · 어림` }; }   // 거래 칸이 넘은 분은 칩 찬 분이 아니라 chipPx 에 없음 — 그 분 1분봉(rows[].bars) · 없으면 다음 30분 칸 값 · 어림(서버 분마다 값이 오면 정확히)
      NOPX.set(r, CPM && CPM.settledTo && hmS(T) >= String(CPM.settledTo) ? `${hmS(T)} 분봉 굳는 중` : `${hmS(T)} 분봉 없음`); return null; }   /* 1분봉이 있는 판에서 그 분 값이 없으면 어림하지 않고 안 삼 — 옛 판도(서버 같은 셈 · 개발2 11-25) · 그날 1분봉이 아예 없으면 서버가 meta.chipPx {ok:false} 로 내 아래 어림 */   /* settledTo — 이 분부터 굳는 중(서버 _chip_px_fill 은 그 앞 분만 실음 · 개발2 1719020) */   // 9시 1분 뒤는 서버 buy930 과 같은 값(개발2 df182ad · 분 1분봉 종가)
    for (const k of PMIN) { const h = minHM(k); if (T <= h) { const o = minVal(r, k); if (o && Number(o.px) > 0) return { px: Number(o.px), at: h, src: `${hmS(h)} 값 · ${needTxt(r)}` }; break; } }
    // 09:05 뒤 — 칩 N개가 함께 붙은 그 분의 그 종목 1분봉 종가(서버가 분봉에서 읽어 rows[].chipPx {HH:MM: 원} · 붙음 · 빠짐 시각마다 · 개발2)
    //   (11-25 재권님 「매수에 칩이 ()개 이상 붙었을때 로 하고 붙은시간에 셈하는걸로」 → 「산값은 정확해야 할거같은데. 서버에 해당종목의 분봉을 읽어서 셈해야해」 → 「응 그게 맞아」)
    //   그 값을 주는 판(meta.chipPx)에서 그 분 값이 없으면 어림하지 않고 「산 값 못 잼」 · 셈 밖 — 그 칸이 없는 옛 판만 아래 어림(든 때 · 다음 30분 칸)에 「어림」 을 붙임
    const e = inTs(r).slice(0, 4); if (e && e >= T && Number(r.buy) > 0) return { px: Number(r.buy), at: e, src: `${hmS(e)} 든 때 · ${needTxt(r)} ${hmS(T)} · 어림` };
    const t = ((curD().times) || []).find((x) => hhmm(x) >= T), v = t && Number((r.px || {})[t]); return v > 0 ? { px: v, at: hhmm(t), src: `${hmS(hhmm(t))} 칸 값 · ${needTxt(r)} ${hmS(T)} · 어림` } : null; }
  if (n === 1) { const e = inTs(r), p1 = `${minHM(1)}00`, u = inUntil();
    // 굳힘마다 산 값이 다름(11-23 재권님 「각 굳힘별로 산 가격은 다르게 해줘야해 9시 5분 굳힘은 현재 만들어놓은 룰이고. 그이후에 굳힘 종목은 들어올때로 만들어줘」)
    //   첫 굳힘(09:05 · lock 1)은 아래 룰 그대로 · 둘째 굳힘부터(lock 2 · 3)는 판에 처음 든 때 가격(r.buy) · 산 시각 든 때
    // 대기 줄(굳힌 판에서 아직 안 굳은 종목)도 처음 든 때 가격에 산 것으로 셈(11-23 재권님 「단타판에 보이는 종목들은 다 셈해」)
    const lkd = ((curD() && curD().rows) || []).some((x) => Number(x.lock) > 0);
    if (Number(r.lock) >= 2 || (lkd && !(Number(r.lock) > 0))) return Number(r.buy) > 0 ? { px: Number(r.buy), at: (e || `${minHM(1)}00`).slice(0, 4), src: e ? `${e.slice(0, 2)}:${e.slice(2, 4)}:${e.slice(4, 6)} 든 때` : '든 때' } : null;
    // 굳힌 줄(rows[].lock > 0)은 inUntil 뒤 들었어도 처음 든 때 가격에 산 것(09:30 · 10:00 굳힘 · 재권님 「9시 30분과 10시에 굳힘 목록에 들어온 종목들도 들어올때를 시점으로 샀다라고 하고 계산해」 11-23 · 승률 표 서버 4f2aa0e 와 같게)
    if (e && e >= p1) { if (!(Number(r.lock) > 0) && (!u || e > `${u}59`) || !(Number(r.buy) > 0)) return null; return { px: Number(r.buy), at: e.slice(0, 4), src: `${e.slice(0, 2)}:${e.slice(2, 4)}:${e.slice(4, 6)} 든 때` }; } }
  // 고른 시각에 판에 아직 없던 종목은 사지 않음 — 그 시각이 들어온 때보다 앞이면 안 삼(11-20 15:26 재권님 「매수에서 든시간 말고 지정된 시간을 누르면 그시간이후에 들어온건 안사지는걸로 계산되도록 해줘」)
  //   손익 · 평균 · 합계 · 승률에서 빠지고(몫도 안 나눔) 매수가 칸에 「안 삼 · HH:MM 뒤 듦」 — 그 전(같은 날 낮)에는 들어온 때 가격으로 샀다
  if (n) { const o = minVal(r, n), t = hmS(minHM(n)); if (notYetIn(r, (o && o.at) || minHM(n))) return null; return o && Number(o.px) > 0 ? { px: Number(o.px), at: hhmm(o.at || minHM(n)), src: o.src === 'now' ? `${t} 그때 현재가` : t } : null; }
  if (k === 'vi') { const o = r.viPx; if (o && o.at && notYetIn(r, o.at)) return null; return o && Number(o.px) > 0 && o.at ? { px: Number(o.px), at: hhmm(o.at), src: `VI ${String(o.at).slice(0, 5)}` } : null; }
  // 「들어온 때」 도 칩 N개가 09:30(서버 meta.buy930.until) 뒤에 찬 줄은 「09:30 뒤에 찬 종목」 단추를 따름 — 서버 c35818f 와 같게(개념정의 덧 11-23)
  if (curD() && curD().flat930 && !st.set.buyLate930) { const T = nthChipAt(r); if (T && T > chipUntil().replace(':', '')) return null; }
  return Number(r.buy) > 0 ? { px: Number(r.buy), at: hhmm(r.buyAt || openHM()), src: r.buySrc || '시가' } : null;
}
// 산 시각 → 판정 시각(HHMM) — 30분 단위 반올림(분 15 이상이면 다음 30분) 뒤 min 분 · 값을 모르면 ''
const cutTime = (at, min) => { const t = hhmm(at); if (!/^\d{4}$/.test(t)) return ''; const m0 = +t.slice(0, 2) * 60 + +t.slice(2), r = Math.floor((m0 + 15) / 30) * 30 + (Number(min) || 0); return String(Math.floor(r / 60)).padStart(2, '0') + String(r % 60).padStart(2, '0'); };
// 코스피 조건 매도 줄(11-24 재권님 「매도봉 라인을 하나추가하고 상승일때와 하락일때를 다르게 매도하고싶어서」 → 「코스피가 ()시에 시가보다 ()%이하 하락일때 · ()%이상 상승일때」 →
//   「시가 여기를 고가 시가 저가 구분가능하도록 해줘」 → 그림에 「응 커밋해」 → 「코스피가 () 에 이건 필요없고 시가 앞에 전일 도 넣어줘」)
//   · 셈 칸 set.mk = { up: {ref, pct, sellBar, stop}, dn: {…} } — ref prev(전일 종가) · open(시가) · high(그때까지 고가) · low(그때까지 저가) · pct 기준 대비 %
//   · 그 날 코스피 5분봉(서버 /api/kis/index-minutes)을 봉마다 끝난 종가로 기준과 견줌 · 전일 종가는 일봉(/api/kis/index-candles) — 화면은 받은 값으로만 셈
//   · 조건이 처음 맞은 봉이 끝난 때부터 그 줄의 매도 봉 · 손절로 봄 · 그 전은 맨 윗줄 · 같은 봉에 둘 다 맞으면 상승 줄 · 나머지 매도 룰(꺾임 · 시각 미달 · 횡보 · 매도 시각)은 한 벌
//   · 그 날 코스피 봉이 없으면(서버가 그 날을 안 쥠) 맨 윗줄 그대로 — 셈한 룰 줄에 「코스피 값 없는 날」 수를 적음
const KX = { bars: null, prev: null, busy: false, at: 0, step: null };   // prev — 날 → 전일 종가(일봉)   // step — 봉 길이(분) · 서버 meta.stepSec   // 코스피 5분봉 — 날(YYYYMMDD) → [[HHMM 시작, 시, 고, 저, 종]]
async function kxLoad() {
  if (KX.busy) return; KX.busy = true;
  try { const rd = await fetch('/api/kis/index-candles?code=KOSPI', { cache: 'no-store' }); const jd = rd.ok ? await rd.json() : null; const P = {};
    const db = ((jd && jd.data && jd.data.bars) || []).map((b) => [String(b.ts || '').slice(0, 8), +b.close]).filter((x) => x[0].length === 8 && x[1] > 0).sort((a, b) => (a[0] < b[0] ? -1 : 1));
    db.forEach((x, i) => { if (i > 0) P[x[0]] = db[i - 1][1]; }); KX.prev = P; } catch (e) { /* 전일 종가 못 받으면 「전일」 기준 줄은 안 씀 */ }
  try { const r = await fetch('/api/kis/index-minutes?code=KOSPI', { cache: 'no-store' }); const j = r.ok ? await r.json() : null; const D = {};
    ((j && j.data && j.data.bars) || []).forEach((b) => { const ts = String(b.ts || ''); if (ts.length < 12) return; (D[ts.slice(0, 8)] = D[ts.slice(0, 8)] || []).push([ts.slice(8, 12), +b.open, +b.high, +b.low, +b.close]); });
    Object.values(D).forEach((v) => v.sort((a, b) => (a[0] < b[0] ? -1 : 1))); KX.bars = D; KX.at = Date.now(); const sec = Number(j && j.meta && j.meta.stepSec); KX.step = sec > 0 ? sec / 60 : null; } catch (e) { /* 못 받으면 맨 윗줄 그대로 */ }
  KX.busy = false; if (st.data && root) { paint(st.data); chips(); }
}
// 그 날 코스피 봉 — 장이 열린 첫 봉부터 있는 날만(qa 11-24 — 서버가 반나절만 쥔 날은 13:35 봉을 「시가」 로 견줬음) · 여는 시각은 그 날 판 meta.openAt(늦게 연 날) · 없으면 09:00
const kxDay = (day) => { const B = KX.bars && KX.bars[day]; if (!B || !B.length || !KX.step) return null;
  const D = (calcD && calcD.day === day && calcD) || (st.data && st.data.day === day && st.data) || dayData[day] || null, op = hhmm((D && D.meta && D.meta.openAt) || '') || REG_OPEN_DEF;   // 서버가 주면 안 씀 — 판 meta.openAt(늦게 연 날 포함) 먼저
  return B[0][0] <= op ? B : null; };
function mkLine(day) {   // 그 날 고른 줄 → { at 그 봉이 끝난 시각, side 'up' | 'dn', line, q } 또는 null(맨 윗줄)
  const M = (st.set && st.set.mk) || {}, B = kxDay(day); if (!B) return null;   // 첫 봉부터 없거나 봉 길이를 서버가 안 주면 — 맨 윗줄
  const sides = ['up', 'dn'].filter((sd) => { const L = M[sd]; return mkUse(L) && (L.ref !== 'prev' || (KX.prev && KX.prev[day] > 0)); }); if (!sides.length) return null;
  let hi = -Infinity, lo = Infinity;
  for (const b of B) { hi = Math.max(hi, b[2]); lo = Math.min(lo, b[3]); const now = b[4]; if (!(now > 0)) continue;
    for (const sd of sides) { const L = M[sd], ref = L.ref === 'prev' ? KX.prev[day] : L.ref === 'high' ? hi : L.ref === 'low' ? lo : B[0][1]; if (!(ref > 0)) continue;
      const q = (now / ref - 1) * 100; if (sd === 'up' ? q >= Number(L.pct) : q <= Number(L.pct)) return { at: hmAdd(b[0], KX.step), side: sd, line: L, q }; } }
  return null;
}
const mkHas = (day) => { const M = (st.set && st.set.mk) || {}, B = kxDay(day); if (!B) return false;   // 그 날 조건 시각까지 끝난 코스피 봉이 있나 — 없으면 조건 줄을 못 봐 맨 윗줄로 셈
  return ['up', 'dn'].every((sd) => { const L = M[sd]; return !mkUse(L) || L.ref !== 'prev' || (KX.prev && KX.prev[day] > 0); }); };
const mkUse = (L) => !!L && L.on !== false && L.pct != null && L.pct !== '';   // 줄 앞 체크(11-24 재권님 「앞에 체크박스 만들어서 적용되게 안되게도 해줘」) — 끄면 안 씀 · 값은 남김
const mkOn = () => { const M = (st.set && st.set.mk) || {}; return ['up', 'dn'].some((k) => mkUse(M[k])); };
function sellAt(p, times = [], inAt = '', o = {}) {   // p — 시각마다 매수가 대비 %(null 은 값 없음) · times — 그 칸 시각 · inAt — 산 시각(HHMM) → { k: 판 시각 차례 또는 -1, why } · o — 코스피 조건 줄(mkSell) {S 셈 칸 · from 이 시각부터 봄 · until 이 시각 전까지만 봄}
  const S = o.S || st.set; let pk = 0, cutDone = false;
  const cutHM = S.cut ? cutTime(inAt, S.cutMin) : '';
  if (o.from && cutHM && cutHM < o.from) cutDone = true;   // 앞 줄(그 시각 전)이 이미 본 것
  // 횡보 매도(11-20 재권님 「매수후 ()분이 지났는데 -+()% 면 매도한다」 → (가) 그때 등락이 −X%~+X% 안이면) — 산 시각(30분 반올림)부터 flatMin 분 칸(값 없으면 그 뒤 첫 칸) 한 번 · 분 · % 둘 다 넣어야 셈
  const flatHM = S.flat && S.flatMin != null && S.flatPct != null ? cutTime(inAt, S.flatMin) : ''; let flatDone = !!(o.from && flatHM && flatHM < o.from);
  // 매도 시각(11-20 재권님 「단타 매도에 매도시간 넣어주고 거기에 시간넣으면 그시간에 모두 파는걸로 적용되게 해줘 안넣으면 2시고」) — 그 시각을 넘는 칸은 안 보고,
  //   그때까지 손절 · 꺾임 · 시각 미달로 안 팔린 종목은 그 시각 이하 마지막 값 있는 칸에 판다 · 빈칸이면 판 끝 칸(서버 times 마지막)까지 — 지금 셈 그대로
  let lastK = -1, cut = false;
  for (let k = 0; k < p.length; k++) {
    if (S.endAt && hhmm(times[k]) > S.endAt) { cut = true; break; }
    if (o.until && hhmm(times[k]) >= o.until) return { k: -1, why: '' };
    if (p[k] == null) continue;
    if (o.from && hhmm(times[k]) < o.from) { pk = Math.max(pk, p[k]); continue; }   // 그 시각 전 칸은 앞 줄이 봄 — 고점만 이어 셈
    lastK = k;
    if (S.stop != null && p[k] <= S.stop) return { k, why: '손절' };
    let a = k - 1; while (a >= 0 && p[a] == null) a--;
    // 꺾임 폭(11-18 재권님 「꺽임룰에 1%이하는 무시한다로 룰 잡아」 → 「그거말고 꺽임 에 내가 %를 추가할수있게 해줘」) — 셈 칸에 넣은 turnPct% 넘게 앞 시각보다 내릴 때만 꺾임 · 기본 0(지금 룰 그대로)
    // 꺾임 기준 두 단추(11-20 재권님 「앞시각이랑 고점대비 2개 버튼으로 선택할수 있게 해줘」) — turnBy prev(앞 시각 대비 · turnPct) · peak(고점 대비 · trail) 중 하나만 · % 는 기준마다 따로 남김
    // 11-20 재권님 「선택할수 있게 해줘. 각각도 되고 둘다도 되게」 — both(둘 다) 더함 · 기준이 저장 안 된 옛 설정은 both(바꾸기 전 셈 그대로)
    if (S.turn && (S.turnBy || 'both') !== 'peak' && a >= 0 && p[a] > 0 && ((100 + p[k]) / (100 + p[a]) - 1) * 100 < -S.turnPct) return { k, why: '꺾임' };
    if (S.turn && (S.turnBy || 'both') !== 'prev' && S.trail != null && pk > 0 && ((100 + p[k]) / (100 + pk) - 1) * 100 <= -S.trail) return { k, why: '고점' };
    // 시각 미달 매도(11-20 재권님 「10시 30분까지 2%초과되지 않는 종목은 매도한다. 버튼 켰다 끄게 해줘」 → (가) 그 시각 값) — 손절 · 꺾임을 먼저 보고 안 팔린 종목만
    //   11-20 재권님 「들어온 시간대를 보고 30분의 반올림 값으로 16분이면 30분으로 적용하고 14분이면 정시로 … 그시각 부터 몇분 은 내가 조절할수있게」
    //   산 시각을 30분 단위로 반올림(15분부터 올림)한 때 + cutMin 분 칸(그 칸 값이 없으면 그 뒤 첫 값 있는 칸) 한 번만 본다 · 매수가 대비 cutPct% 를 넘지 못했으면(같아도) 그 칸 값에 판다
    if (S.cut && !cutDone && cutHM && hhmm(times[k]) >= cutHM) { cutDone = true; if (p[k] <= S.cutPct) return { k, why: '미달' }; }
    if (flatHM && !flatDone && hhmm(times[k]) >= flatHM) { flatDone = true; if (Math.abs(p[k]) <= S.flatPct) return { k, why: '횡보' }; }
    pk = Math.max(pk, p[k]);
  }
  if (cut && lastK >= 0) return { k: lastK, why: '매도 시각' };
  return { k: -1, why: '' };
}
// 봉으로 매도 타점 (11-23 재권님 「매도타점 정확히 계산해」 → 「30분 칸 말고 분봉으로」) — 서버 rows[].bars [[HH:MM 봉 시작, 시가, 고가, 저가, 종가]] · barSrc 1m|5m 가 있으면
//   손절 · 고점은 봉에서 처음 닿은 때 값 · 꺾임 · 시각 미달 · 횡보 · 매도 시각은 30분 칸 그대로(그 시각 봉이 시작될 때 먼저 봄) · 한 봉에 손절 · 고점이 둘 다면 손절 먼저
//   셈 규칙은 서버 dt30_win._sell_bars(개발2 1f95235 · 승률 표)와 같다 — 봉이 없는 줄은 아래 sellAt(30분 칸) 그대로
//   → { k: 결과를 그릴 30분 칸 차례(봉 매도면 그 봉이 끝나는 칸), why, px: 판 값, at: 판 때 HHMM }
const hmAdd = (t, m) => { const x = +t.slice(0, 2) * 60 + +t.slice(2) + m; return String(Math.floor(x / 60)).padStart(2, '0') + String(x % 60).padStart(2, '0'); };
// 매도 봉 고르기(11-23 재권님 「매도타이밍은 5분봉으로 하자」 → 「1분봉과 5분봉을 선택할수 있게 해줘 30분봉도」 · 「그래서 최적의 값을 찾아가야 할거같아」) — 셈 칸 set.sellBar 1m · 5m(기본) · 30m(30분 칸 셈 sellAt 그대로)
//   5분봉 = 서버 rows[].bars5 · 없으면 1분봉(rows[].bars · barSrc 1m)을 5분씩 묶음(시가 첫 · 고가 최대 · 저가 최소 · 종가 끝) · 1분봉이 없고 barSrc 5m 이면 그것
const barsOf = (r, m) => { const b1 = Array.isArray(r.bars) ? r.bars : [];
  if (m === '1m') return b1.length ? b1 : null;   // 1분봉이 없는 날(barSrc 5m)은 5분봉으로 셈 — 서버 a4c6d00 과 같게(개념정의 덧)
  if (Array.isArray(r.bars5) && r.bars5.length) return r.bars5;
  if (r.barSrc === '5m') return b1.length ? b1 : null;
  const g = []; b1.forEach(([t0, o, h, l, c]) => { const t = String(t0).replace(/:/g, '').slice(0, 4), m0 = +t.slice(0, 2) * 60 + +t.slice(2), k = m0 - (m0 % 5), st0 = String(Math.floor(k / 60)).padStart(2, '0') + String(k % 60).padStart(2, '0'), z = g[g.length - 1];
    if (z && z[0] === st0) { z[2] = Math.max(z[2], h); z[3] = Math.min(z[3], l); z[4] = c; } else g.push([st0, o, h, l, c]); });
  return g.length ? g : null; };
// 봉으로 매도 타점 — 고른 봉(1분 · 5분)마다 차례로 본다 · 산 시각이 든 봉은 뺌(그 봉 값은 사기 전 움직임이 섞임 · 11-23 재권님 「계산이 어떻게 된건데?」 짚음)
//   손절  봉 저가 ≤ 매수가 × (1 + 손절%) → 손절가(봉 시가가 이미 밑이면 시가)
//   고점  앞 봉들 고가 중 최고(매수가보다 높을 때) × (1 − 고점%) 에 저가가 닿으면 그 값(시가가 이미 밑이면 시가)
//   꺾임  봉 종가가 앞 봉 종가보다 꺾임% 넘게 내리면(앞 봉이 매수가보다 위일 때) 그 종가
//   시각 미달 · 횡보  정한 시각(산 시각 30분 반올림 + 분)이 끝나는 봉의 종가로 판정 · 그 값에 팖
//   매도 시각  그 시각에 시작하는 봉의 시가 · 한 봉에 여럿이면 손절 → 고점 → 꺾임 → 미달 → 횡보
//   서버 승률 표(dt30_win)도 같은 셈 · 같은 열쇠를 읽게 개발2 에 넘김 → { k: 결과를 그릴 30분 칸, why, px, at }
function sellBars(r, B, times, bars, step, oo = {}) {   // o — sellAt 과 같음(코스피 조건 줄)
  const S = oo.S || st.set, buy = B.px, bAt = B.at, last = times.length ? hhmm(times[times.length - 1]) : '';
  const end = S.endAt || last; const stopPx = S.stop != null ? buy * (1 + Number(S.stop) / 100) : null;
  const tby = S.turnBy || 'both', tr = S.turn && tby !== 'prev' && S.trail != null ? Number(S.trail) : null, tp = S.turn && tby !== 'peak' ? (Number(S.turnPct) || 0) : null;
  const cutHM = S.cut && S.cutPct != null ? cutTime(bAt, S.cutMin) : '', flatHM = S.flat && S.flatMin != null && S.flatPct != null ? cutTime(bAt, S.flatMin) : '';
  const kOf = (t) => { const j = times.findIndex((x) => hhmm(x) >= t); return j >= 0 ? j : times.length - 1; };
  let peak = null, prevC = null, cutDone = !!(oo.from && cutHM && cutHM < oo.from), flatDone = !!(oo.from && flatHM && flatHM < oo.from), lastC = null, lastT = '';
  for (const [t0, o, h, l, c] of bars) { const t = String(t0).replace(/:/g, '').slice(0, 4), te = hmAdd(t, step);
    if (te <= bAt || (t <= bAt && bAt < te)) continue;   // 산 시각이 든 봉 · 그 앞 봉은 안 봄
    if (oo.until && t >= oo.until) return { k: -1, why: '' };
    if (oo.from && t < oo.from) { if (h > buy) peak = Math.max(peak ?? h, h); prevC = c; lastC = c; lastT = te; continue; }   // 그 시각 전 봉은 앞 줄이 봄
    if (t >= end) return { k: kOf(t), why: '매도 시각', px: o, at: t };
    if (stopPx != null && l <= stopPx) return { k: kOf(te), why: '손절', px: o < stopPx ? o : stopPx, at: t };
    if (tr != null && peak != null && peak > buy) { const line = peak * (1 - tr / 100); if (l <= line) return { k: kOf(te), why: '고점', px: o < line ? o : line, at: t }; }
    if (tp != null && prevC != null && prevC > buy && (c / prevC - 1) * 100 < -tp) return { k: kOf(te), why: '꺾임', px: c, at: te };
    const q = (c / buy - 1) * 100;
    if (cutHM && !cutDone && te >= cutHM) { cutDone = true; if (q <= Number(S.cutPct)) return { k: kOf(te), why: '미달', px: c, at: te }; }
    if (flatHM && !flatDone && te >= flatHM) { flatDone = true; if (Math.abs(q) <= Number(S.flatPct)) return { k: kOf(te), why: '횡보', px: c, at: te }; }
    peak = peak == null ? h : Math.max(peak, h); prevC = c; lastC = c; lastT = te; }
  if (oo.until) return { k: -1, why: '' };   // 앞 줄 — 그 시각 전에 안 팔렸으면 뒤 줄이 봄
  return lastC != null ? { k: kOf(lastT), why: '매도 시각', px: lastC, at: lastT } : { k: -1, why: '' };
}
// 손익 셈 (11-11 재권님 「각 종목별로 천만원씩 샀다고 하고 상위 16종목을 해당룰로 했을때 수익은 얼마지?」 → 「결과 옆에 거래세랑 세금 퍼센트를 넣어줘
//   세금은 코스피와 코스닥세금 내는거 룰찾아서 넣고 증권수수료는 내가 기입하면 그 숫자에 맞춰서 대입되게 해줘」)
//   · 상위 PNL_TOP 종목을 한 종목에 PNL_WON 원어치(주 단위 내림) 09:06 매수가에 사서 위 룰대로 판 값에 판다
//   · 세금은 팔 때만 — 판 금액 × (거래세 + 농어촌특별세) · 시장마다 TAX 표 · 증권수수료는 팔 때만 판 금액 × 수수료 %(11-18 재권님 「증권수수료는 팔때만」 — 그 전에는 살 때 · 팔 때 각각)
//   · 수수료 % 는 재권님이 칸에 넣으신 값 — 서버 룰 문서(strategy-rules · rules.dt30.feePct) 한 곳 · 빈칸이면 수수료는 안 셈(「빈칸」 이라 적음 · 0 으로 보지 않음)
//   · 2026 세율(KB증권 「2026년 증권거래세율 변경 안내」 · 머니투데이 2025-12-01 「내년 1월부터 증권거래세 오른다」) — 세율이 바뀌면 TAX 한 곳만 고친다
const PNL_TOP = 30, PNL_WON = 10_000_000, SHOW_MAX = 30;   // SHOW_MAX — 칩 N개 칸을 넣었을 때 판에 보이는 종목 수 합(11-26 재권님 「보여져야 하는 총 개수는 30개로」)   // 기본값 — 재권님이 칸에 넣으면 st.set 이 이김
// 셈 칸 기본값 (11-18) — minChip 칩 N개 이상만(0 = 전체) · top 상위 몇 종목 · 돈은 전체 금액 dayWon 을 그 종목 수로 똑같이 나눔
//   11-18 재권님 「금액은 전체 금액으로 해주고 종목만큼 나눈다 라는 룰로 해줘 금액을 맨앞으로」 — 종목마다(each) 갈래는 걷음 · 기본 전체 금액 = 지금까지의 기본(상위 30 × 1,000만원)과 같은 3억
const DEF_SET = { comboAuto: true, comboOn: false, combos: [], comboUp: 70, comboN: 2, minChip: 0,   /* comboUp · comboN 기본은 서버 chip-rules meta.sellDef 가 덮음(SELL_DEF · 개발2 11-26 — 칸 없음 = 기본 · 비워 저장 = 안 고름) · 여기 값은 서버 못 받을 때만 */ top: PNL_TOP, mode: 'day', perWon: PNL_WON, dayWon: PNL_TOP * PNL_WON, pyr: false, buy: 'open', turnOn: true, turnMin: 1 };   // 유통 대비 거래 거르기 — 기본 켬 · 1% 이상(11-24 재권님 「유통거래대비 1%가 기본으로 해주고 이걸 내가 조절할수 있게」) · 칸에서 바꾸면 저장값이 이김   // 매도 셈 열한 칸은 서버 SELL_DEF   // buy — 매수 타이밍 open(09:00 시가 · 지금까지 셈) · p1(09:01) · vi(VI 발동)   // pyr — 불타기(손절로 판 돈을 그 시각 가장 많이 오른 종목에 더 삼) · 기본 끔
Object.assign(DEF_SET, { endAt: '', sellBar: '5m', mk: {}, riseRank: true });   // riseRank — 상승률 순위(11-24 · 끄면 단타 순)   // mk — 코스피 조건 줄 둘(11-24 · mkLine)   // sellBar — 매도 봉 1m · 5m · 30m(11-23 재권님 「매도타이밍은 5분봉으로 하자」 → 고르기 · 기본 5분)   // endAt — 매도 시각(HHMM · 빈칸이면 판 끝 칸까지 · 11-20) · 손절 · 꺾임 · 고점 · 시각 미달 · 횡보 기본값은 서버 SELL_DEF
st.set = { ...DEF_SET };
// 「· 어림」 — 서버 rows[].turnApprox(개발2 abf96b9) · 재권님 「응」 11-23 · 풍선은 어림 방법만(코드 이름은 이 주석에)
const fltChk = (k, t, f, tip) => `<label class="dt-flt" data-tip="${tip} · 체크를 끄면 안 거름(값은 남김) · 넣으면 저장"><input type="checkbox" data-fltchk="${k}"${st.set[`${k}On`] ? ' checked' : ''} aria-label="${t} 거르기 켜기">${t} <input data-set="${f}" class="rl-in rl-num" inputmode="decimal" placeholder="( )" value="${st.set[f] > 0 ? st.set[f] : ''}" aria-label="${t} 몇 % 이상">% 이상</label>`;
const fltIn = () => `${fltChk('turn', '유통 대비 거래', 'turnMin', '풀린 주식 대비 오늘 거래(서버 거래 비율 · 누적 거래대금 ÷ 풀린 시총)가 이 % 이상인 종목만 · 못 잰 종목(값 없음)은 뺌')}${fltChk('vol', '전일 거래량 대비 지금 거래량', 'volMin', '전날 하루 거래량 대비 오늘 지금까지 거래량(프리장 빠짐)이 이 % 이상인 종목만 · 장 시작 25분 뒤(보통 09:25)부터 거름 — 그 전엔 안 거름 · 못 잰 종목은 남김')}`;   // 종목 머리 칸 — 유통 시총 거르기(11-23) · 유통 ( )억 이하 칸은 뺌(11-24 재권님 「유통 ()이하 이건 없애」) · 거르기 둘(11-24 재권님 「체크박스가 2개 … 유통주식대비 현재 거래되는 거래량 ()%이상 전일 동시간대비 거래량()%이상」)
const WIN_KEY = 'dt30-windows';   // 마지막으로 받은 창 이름표 — 창이 없는 옛 날 판을 볼 때도 셈 칸은 지금 창으로(보는 상태 · 이 브라우저에만)
const winsOf = () => { const m = (curD() && curD().meta) || {}; if (Array.isArray(m.windows) && m.windows.length) { try { localStorage.setItem(WIN_KEY, JSON.stringify(m.windows)); } catch (e) { /* 못 남겨도 됨 */ } return m.windows; } try { const v = JSON.parse(localStorage.getItem(WIN_KEY) || 'null'); return Array.isArray(v) && v.length ? v : null; } catch (e) { return null; } };
const LKW = () => (winMode() ? '창' : '굳힘');   // 화면 낱말 — 창 판은 「창」(11-23 개발2 253689d · 「굳힘 낱말을 창으로」)
const winMode = () => (((curD() && curD().meta) || {}).lockMode === 'window');
function lkGridHtml(W) {
  if (W) return `<b style="font-size:12px">창</b><span class="rl-sug">금액(만원)</span><span class="rl-sug">사지 않음</span>`
    + W.map((w, k) => { const i = (Number(w.lock) || k + 1) - 1, nm = esc(w.name || `${i + 1}째`), tm = w.from && !String(w.name || '').includes(w.from) ? ` <small>${esc(w.from)}${w.to ? ` ~ ${esc(w.to)}` : ' ~'}</small>` : ''; return `<span class="rl-sug">${nm}${tm}</span><input data-set="gw${i}" class="rl-in rl-num" inputmode="numeric" placeholder="( )" aria-label="${nm} 금액(만원)">${NOBUY(i)}`; }).join('');
  return `<b style="font-size:12px">굳힘</b><span class="rl-sug">시각</span><span class="rl-sug">금액(만원)</span><span class="rl-sug">종목 수</span><span class="rl-sug">칩 몇 개 이상</span><span class="rl-sug">사지 않음</span>`
    + ['첫째', '둘째', '셋째'].map((nm, i) => `<span class="rl-sug">${nm}</span><input data-set="lock${i}" class="rl-in rl-num" aria-label="${nm} 굳힘 시각"><input data-set="gw${i}" class="rl-in rl-num" inputmode="numeric" placeholder="( )" aria-label="${nm} 굳힘 금액(만원)"><input data-set="gn${i}" class="rl-in rl-num" inputmode="numeric" aria-label="${nm} 굳힐 종목 수"><input data-set="gc${i}" class="rl-in rl-num" inputmode="numeric" placeholder="( )" aria-label="${nm} 굳힘 칩 몇 개 이상">${NOBUY(i)}`).join('');
}
const NOBUY = (i) => `<span class="dt-seg" data-tip="켜면 이 묶음은 판에는 남기고 돈은 안 넣음 · 승률 표에서도 뺌"><button type="button" class="kh-chip" data-nobuy="${i}" aria-label="사지 않음">안 삼</button></span>`;   // 굳힘 칸마다 「사지 않음」 단추(i 0~3 · 넷째 = 장중)
const noBuyOf = (j) => j > 0 && !!(st.set.lockNoBuy || [])[j - 1];   // 굳힘 차례 j(1~4)가 「사지 않음」 인가
// 거래세 · 농특세(%) — 서버 한 곳(dt30_win.TAX)이 판 meta.tax 로 준다 · 화면은 보이기만 · 바꾸는 것은 증권수수료 칸 하나(11-20 재권님 「증권사 세율만 조절되도록 남기면되, 단타에 표기는 해놓고」) · 못 받으면 세금 못 셈(「—」)
const taxOf = (m) => (((curD() && curD().meta && curD().meta.tax) || (st.data && st.data.meta && st.data.meta.tax)) || {})[String(m || '').toUpperCase()] || null;   // 그 날 판의 세율(셈하는 판 먼저 · 11-24)
const MKT = { KOSPI: '코스피', KOSDAQ: '코스닥' };
const manTxt = (w) => { const m = Number(w) / 10000; return !Number.isFinite(m) ? '—' : m >= 10000 && m % 10000 === 0 ? `${num(m / 10000)}억원` : `${num(m)}만원`; };   // 원 → 만원 · 1억 단위면 억원
const won = (x) => (x == null || !Number.isFinite(x) ? '—' : `${x < 0 ? '-' : x > 0 ? '+' : ''}${Math.abs(Math.round(x)).toLocaleString('ko-KR')}원`);
const wonPlain = (x) => (x == null || !Number.isFinite(x) ? '—' : `${Math.round(x).toLocaleString('ko-KR')}원`);
const taxTxt = (r) => { const m = String(r.market || '').toUpperCase(), T = taxOf(m); return T ? `${MKT[m]} ${num(T.tx, 2)}${T.rural ? ` + ${num(T.rural, 2)}` : ''}%` : '<span class="st-err">—</span>'; };
const mean = (v) => (v.length ? v.reduce((a, b) => a + b, 0) / v.length : null);
const sgn = (x) => (x == null ? '—' : `${x > 0 ? '+' : ''}${num(x, 2)}%`);

// 어제 미국장 주요 값 — 그날 07:00 미국 데일리 텔레그램과 같은 저장본(/api/board/doc/usdaily-<그날> · 개발1 daily 서버가 씀) 그대로 · 칩 줄 오른쪽
//   재권님 「오늘이면 어제장 미국 주요지수들 넣어줘 … 선물 반도체 에스앤피 나스닥」 → 자리 「단타 안에 칩 옆으로」(11-12) · 날짜를 바꾸면 그날 아침 것
const US_NAMES = [['선물', (D) => D.night && D.night.rows && D.night.rows.kospi200, '야간선물 코스피200(그 전날 밤 · 06:00 마감)'], ['반도체', '필라델피아 반도체'], ['S&P', 'S&P 500'], ['나스닥', '나스닥 종합'],
  // 11-18 재권님 「이정보도 그날 새벽 미국장 정보 다 넣어서 저장되게 해줘. 미국장이 안좋을때는 금액조절하는걸 만들려고 해」 → 「응」 — 저장본에 있는 값 더함 · 없는 넷(다우 · 러셀2000 · 미국 10년 국채 · 달러인덱스)은 개발1 이 저장본에 넣으면 그 이름으로 나옴
  ['나스닥100', '나스닥100'], ['VIX', 'VIX', 'VIX(미국 공포 지수) · 오르면 겁이 커진 것'], ['원/달러', '미국 USD', '원/달러 환율'],
  ['코스닥150 선물', (D) => D.night && D.night.rows && D.night.rows.kosdaq150, '야간선물 코스닥150(그 전날 밤 · 06:00 마감)'],
  ['다우', '#DJI'], ['러셀2000', '#RUT'], ['미국 10년 국채', '#US10Y', '미국 10년 국채 금리 · % 는 금리의 변화율'], ['달러인덱스', '#DXY', '달러인덱스(ICE 1973=100)']];   // '#' 은 저장본 줄의 code(개발1 · 11-18)
const usCache = {};
const usHtml = (day) => {
  const D = usCache[day];
  if (D === undefined) return '<span class="dt-hd">어제 미국장</span><span class="st-err">받는 중…</span>';
  if (D === null) return '<span class="dt-hd">어제 미국장</span><span class="st-err" data-tip="그날 아침 07:00 미국 데일리 저장본이 없음(07:00 전 · 주말 · 못 받음)">—</span>';
  const one = ([lb, k, tip]) => { const x = typeof k === 'function' ? k(D) : (D.indices || []).find((i) => (k[0] === '#' ? i.code === k.slice(1) : i.name === k)); const v = x && (x.changePct ?? x.pct), val = x && (x.value ?? x.last);
    if (x && x.value == null && x.error) return `<span class="dt-usi" data-tip="${esc(`${lb} — 이 날 못 받음(${x.error})`)}">${esc(lb)} <span class="st-err">—</span></span>`;
    if (!x) return `<span class="dt-usi" data-tip="${esc(`${lb} — 이 날 저장본에 없음(아직 저장 안 함 · 못 받음)`)}">${esc(lb)} <span class="st-err">—</span></span>`;
    return `<span class="dt-usi" data-tip="${esc(tip || `${x.name || k} · 현지 마감 · 07:00 텔레그램과 같은 값`)}">${esc(lb)} <b>${num(val, 2)}</b> ${pct(v == null ? null : Number(v))}</span>`; };
  const ov = Array.isArray(D.overnight) ? D.overnight : [];   // 밤사이 미국 지표 발표 — 저장본 글 그대로(풍선)
  const ovH = ov.length ? `<span class="dt-usi" data-tip="${esc(ov.join('\n\n'))}">밤 지표 발표 <b>${ov.length}</b></span>` : '<span class="dt-usi" data-tip="그 밤 미국 지표 발표 없음(저장본 기준)">밤 지표 발표 <b>0</b></span>';
  return `<span class="dt-hd">어제 미국장</span>${US_NAMES.map(one).join('')}${ovH}${wxHtml(day)}`;
};
// 지금 바깥 값 — 바이낸스 한국 종목 무기한선물 · 하이닉스 나스닥(SKHY) · 원/유로 (11-19 재권님 「응 해줘. 이거 단타에도 전날미국장 옆에도 넣어주고」 · 홈 「국외」 끝 칸과 같은 값)
//   값은 서버 /api/market/world-extra 한 곳 · 지금 값이라 오늘 판(맨 앞 날)에만 붙임(지난 날 판에 지금 값을 붙이지 않음) · 다시 받는 간격은 서버 meta.ttlSec(화면에 숫자 안 둠 · 없으면 다시 안 받음)
//   홈 holdings/js/components/world-extra.js 는 홈 지수 칸 모양만 내보내 가져다 쓰지 못함 — 이름 · 등락 기준은 그 파일과 같게(바이낸스 24시간 전 대비 · SKHY 전날 종가 대비 · 원/유로 앞 날 대비)
const wx = { data: null, fail: null, timer: 0 };
const wxHtml = (day) => {
  if (!st.days || day !== st.days[0]) return '';
  const D = wx.data; if (!D) return wx.fail ? `<span class="dt-usi" data-tip="${esc(`지금 바깥 값 못 받음(${wx.fail})`)}">지금 바깥 <span class="st-err">—</span></span>` : '';
  const it = (lb, val, p, tip, d = 2) => `<span class="dt-usi" data-tip="${esc(tip)}">${esc(lb)} <b>${val == null ? '—' : num(val, d)}</b> ${pct(p == null ? null : Number(p))}</span>`;
  const S = D.sources || {};
  const a = (D.binance || []).map((b) => it(`${b.name} 선물`, b.last, b.chgPct24h, `바이낸스 ${b.symbol} 무기한선물(USDT) · 마지막 체결 · 등락은 24시간 전 대비 · 펀딩비 ${b.funding == null ? '—' : `${(b.funding * 100).toFixed(4)}%`}${S.binance ? `\n${S.binance}` : ''}`));
  if (D.skhy) a.push(it('하이닉스 나스닥', D.skhy.last, D.skhy.chgPct, `${D.skhy.name || 'SKHY'} · 달러 · 등락은 전날 종가 대비${S.skhy ? `\n${S.skhy}` : ''}`));
  if (D.eurkrw) a.push(it('원/유로', D.eurkrw.value, D.eurkrw.chgPct, `원/유로 · 등락은 앞 날 대비${D.eurkrw.date ? ` · ${D.eurkrw.date}` : ''}${S.eurkrw ? `\n${S.eurkrw}` : ''}`));
  return a.length ? `<span class="dt-hd">지금 바깥</span>${a.join('')}` : '';
};
async function wxLoad() {
  clearTimeout(wx.timer);
  let ttl = 0;
  try { const r = await fetch('/api/market/world-extra', { cache: 'no-store' }); const j = r.ok ? await r.json() : null;
    if (j && j.data) { wx.data = j.data; wx.fail = null; } else wx.fail = r.ok ? '빈 값' : r.status;
    const T = j && j.meta && j.meta.ttlSec; const xs = (T && typeof T === 'object' ? Object.values(T) : [T]).map(Number).filter((x) => x > 0); ttl = xs.length ? Math.min(...xs) : 0; }   // ttlSec 는 이름별 묶음 {binance · skhy · eurkrw} — 가장 짧은 것(홈 world-extra.js 와 같은 셈 · 개념정의 e43ddfd 검수)
  catch (e) { wx.fail = '연결 안 됨'; }   // 지난 값은 지우지 않음
  const el = $('dt-us'); if (el && st.data) el.innerHTML = usHtml(el.dataset.day);
  if (ttl > 0 && root) wx.timer = setTimeout(wxLoad, ttl * 1000);
}
async function usLoad(day) {
  if (!day || usCache[day] !== undefined) return;
  try { const r = await fetch(`/api/board/doc/usdaily-${day}`, { cache: 'no-store' }); const j = r.ok ? await r.json() : null; usCache[day] = (j && j.data && (j.data.indices || j.data.night)) ? j.data : null; }
  catch (e) { usCache[day] = null; }
  const el = $('dt-us'); if (el && el.dataset.day === day) el.innerHTML = usHtml(day);
}

// 한 날 판의 셈 — 화면 그리기(paint)와 이달 합계(monthPaint)가 같은 셈을 쓴다 · 값은 서버 판 그대로 · 칩 켜고 끔 · 셈 칸(st.set)을 따름
// 굳힘(창) 없앰 · 칩은 09:30 까지 붙은 것만(11-23 재권님 「추가된 칩이랑 시간들 받아서 매매계산 … 9시 30분기준으로 해서 계산되도록 굳힘 없애줘」 → 「9시 30분까지 칩이 적용된것들이야 9시 30분에 사는게 아니고」)
//   서버 rows[].lock · meta.lockMode · windows · lockAt 을 받는 자리에서 지움 → 창 단추 · 창 셈 칸 · 진행 중 묶음이 안 생김 · 사는 때는 매수 칸 룰 그대로
//   칩 시각 = rows[].chipAt(VI 는 viAt 도) — 09:30 뒤에 붙은 칩은 그 줄에서 뺌(겹친 수 · 순위 · 셈에서 빠짐) · 시각을 모르는 칩은 남김(짐작해 빼지 않음)
const CHIP_UNTIL_DEF = '09:30';   // 서버 값이 없는 옛 판만
// 늦게 연 날(11-19 10:00 등)에 서버가 여는 시각을 안 남긴 판(다시 지은 판 · meta.openAt · lateMin 없음)은 1분 값 시각(pxMin["1"].at 10:01)으로 늦은 분을 알아 마감도 그만큼 옮김
//   11-24 재권님 「그럼 9시 30분에 찬 종목이라고 쓰지를 말든가」 — 서버가 옮겨 주면(개발2 · meta.lateMin) 이 셈은 안 씀
const lateOf = () => { const m = DM() || {}; if (m.openAt || m.lateMin != null) return 0; const r = ((curD() || {}).rows || []).find((x) => x.pxMin && x.pxMin['1'] && x.pxMin['1'].at); const t = r ? String(r.pxMin['1'].at).replace(':', '') : ''; if (!/^\d{4}$/.test(t)) return 0; const d = (+t.slice(0, 2) * 60 + +t.slice(2)) - (9 * 60 + 1); return d > 0 ? d : 0; };
const chipUntil = () => { const u0 = String(((DM() || {}).buy930 || {}).until || ''), u = /^\d{2}:\d{2}$/.test(u0) ? u0 : CHIP_UNTIL_DEF, L = lateOf(); if (!L) return u; const h = hmAdd(u.replace(':', ''), L); return `${h.slice(0, 2)}:${h.slice(2)}`; };   // 칩을 세는 끝 — 서버 meta.buy930.until 한 곳(화면에 따로 두면 갈림 · 11-23)
const flat930 = (d) => { if (!d || d.flat930) return d; const m = { ...(d.meta || {}) }; ['lockMode', 'windows', 'lockAt', 'lockN'].forEach((k) => delete m[k]);
  const rows = (Array.isArray(d.rows) ? d.rows : []).map((r) => {
    return { ...r, lock: null, lockAt: null, lock0: r.lock }; });   // lock0 — 서버 굳힘 번호 그대로(장중 창 「보기만」 표가 meta.intra.lock 으로 고름 · 11-24)   // 칩은 다 남김(19:3x 재권님 「칩들의 시간이 정확히 필요함. 칩이 걸리는걸 바꾸면 거기에 맞게 소팅이 다시」) — 09:30 은 줄을 가르는 선(grp)
  return { ...d, meta: m, rows, flat930: true }; };
// 매매가 하나도 안 나온 날은 여는 시각 + 5분(보통 9시 5분 · 늦게 연 날은 그만큼 뒤 · 11-19 는 10시 5분)에 산 것으로 다시 셈하고 표시(11-24 재권님 「11월 19일은 한시간 늦게 적용하고 그이외에 매매가 없다고 나온날은 9시 5분에 매매한걸로 적용해서 해놔. 표기도 해놓고」)
const fbDays = new Set();   // 대체 매수로 셈한 날 — 판 그리기(calc 밖의 buyOf)도 같은 매수가를 쓰게
function calc(d) { const p = calcD; calcD = flat930(d); const k = d && d.day; try { if (k) fbDays.delete(k); const C = calcDay(calcD); if (C.P || !C.rows.length || d.closed !== true) return C;   /* 굳힌 지난 판만 — 장중 · 오늘 판은 대체하지 않음 */ if (k) fbDays.add(k); calcD = { ...calcD, fb905: true }; const C2 = calcDay(calcD); C2.fb905 = true; return C2; } finally { calcD = p; } }
// 대체 매수가 — 여는 시각 + 5분 1분 값(서버 pxMin["5"] · 그 시각 at) · 없으면 서버 판의 든 때 값(지난 판 다시 짓기는 09:05 봉 시가)
const fb905Of = (r) => { const o = r.pxMin && r.pxMin['5']; if (o && Number(o.px) > 0) { const at = String(o.at || '').replace(':', ''); return { px: Number(o.px), at: /^\d{4}$/.test(at) ? at : addHM(openHM(), 5 + lateOf()), src: `${o.at || ''} 값 · 매매 없던 날 9시 5분 대체` }; }
  if (Number(r.buy) > 0) return { px: Number(r.buy), at: addHM(openHM(), 5 + lateOf()), src: '든 때 값 · 매매 없던 날 9시 5분 대체' };
  // 그 시각 값도 없으면(11-06 처럼 5분봉 09:05~09:25 가 빠진 날) 그 뒤 첫 30분 칸 값 — 시각을 그대로 적음(9시 5분이라 쓰지 않음)
  const h = addHM(openHM(), 5 + lateOf()), t = ((curD() || {}).times || []).find((x) => hhmm(x) >= h && Number((r.px || {})[x]) > 0);
  return t ? { px: Number(r.px[t]), at: hhmm(t), src: `${hmS(h)} 값 없음 · ${hmS(hhmm(t))} 칸 값으로 대체` } : null; };
// 서버가 실제로 보낸 종목의 차례(판 meta.buyRule.sent · 없으면 meta.tgBuy — {code: {order, sentAt, kind}}) · 안 보냈으면 null — 셈 · 그리기 두 곳이 함께 씀(11-24)
const sentOrdOf = (d, r) => { const m = (d && d.meta) || {}, x = (m.buyRule && m.buyRule.sent) || m.tgBuy, o = x && typeof x === 'object' ? x[r.code] : null; return o && Number.isFinite(Number(o.order)) ? Number(o.order) : null; };
function calcDay(d) {
  HYPO = new WeakMap(); NOPX = new WeakMap(); SVNO = new WeakSet(); CONDX = new WeakMap();   // 보기만 줄 가정 매수 · 분봉 값 없음 표시는 이번 셈에서만
  const S = st.set;
  // 매도 시각보다 늦게(같은 때 포함) 든 종목은 안 산 것으로 — 셈 · 돈 나누기에서 뺌(11-20 qa 덧 → 재권님 「가」)
  const boughtOf = (r) => { const B = buyOf(r); return B && S.endAt && B.at >= S.endAt ? null : B; };
  const times = Array.isArray(d.times) ? d.times : [];
  const all = Array.isArray(d.rows) ? d.rows : [];
  const MKL = mkOn() ? mkLine(d.day) : null;   // 그 날 코스피 조건 줄(11-24) — 없으면 맨 윗줄만
  const live0 = ordSort(all.filter((r) => nEver(r) > 0));
  // 굳힘 없앤 판 — 켠 칩으로 N번째 칩이 먼저 찬 순(같으면 지금 차례) · 칩 수 · 켠 칩을 바꾸면 다시 세움(19:3x 재권님 「칩이 들어오는 순서를 기억하고 칩의 개수를 조절하면 순위가 소팅되어야함」) · 못 찬 줄은 뒤
// 칩조합으로 살 때 조합 된 분이 같은 종목끼리는 그 분 1분 값(산 값)의 시가 대비 상승률 높은 순 → 초반상승 % → 시가총액 — 지금 붙은 칩 수는 안 씀(뒤에 칩이 붙어도 순위 고정 · 11-26 재권님 「칩조합의 조건이 처음걸리는 순간 고정이여야」 → 「응 해줘」) · 「상승률 순위」 체크는 안 봄(11-26 재권님 「9시1분에 들어왔는데 5분을 쓰면 안되는데 상승률 순위는 1분단위로」 · 「나 로 해주고」 — 그 전에는 체크면 09:05 까지 상승률)
const live = d.flat930 || comboMode() ? live0.map((r, i) => [r, nthChipAt(r) || '9999', i, comboMode() ? comboRise(r) : null]).sort((a, b) => (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : (comboMode() ? (b[3] ?? -Infinity) - (a[3] ?? -Infinity) || (riseOf(b[0]) - riseOf(a[0]) || 0) || (Number(b[0].cap) || 0) - (Number(a[0].cap) || 0) : 0) || a[2] - b[2])).map((x) => x[0]) : live0;   // 켜진 칩으로 다시 셈한 단타 차례 · 차례 점수를 넣었으면 그 합으로(11-23)
  // 장중 줄 먼저 · 다시 지으며 더한 줄은 아래(11-24 재권님 「나」 — 장중 종목은 장중 값 · 3천억 이상 칩 하나라도 든 종목은 아래에 더함) — 서버 rows[].live 가 있는 판만 · 각 묶음 안 차례는 그대로
  const liveP = all.some((r) => r.live) ? [...live.filter((r) => r.live), ...live.filter((r) => !r.live)] : live;
  const rows1 = st.only ? liveP.filter((r) => liveChip(r, st.only)) : liveP;   // 거르고 나서 순번 · 상위 N · 평균을 다시 셈
  const rows0 = comboMode() ? rows1.filter((r) => comboHit(r)) : S.minChip > 0 ? rows1.filter((r) => nEver(r) >= S.minChip) : rows1;   // 조합으로 사기면 고른 조합이 된 종목만(11-26)   // 칩 N개 이상만(11-18) — 켜진 칩으로 센 수 · 한 번 붙었다 빠진 칩도 셈(nEver · 11-24)
  // 유통 시총 거르기(11-23 재권님 「종목 옆에 유통주식 필터 넣어줘 ()억 이라고 해서 해당금액 하위로 필터링되게」) — 풀린 시총(서버 rows[].floatCap · 억원)이 넣은 값 이하인 종목만 · 못 잰 종목(우선주 등 null)은 가를 수 없어 남김 · 빈칸 = 전체
  const atLeast = (x, m) => x == null || !Number.isFinite(Number(x)) || Number(x) >= m;   // 못 잰 종목은 남김(유통 거르기와 같음)
  const has = (x) => x != null && Number.isFinite(Number(x));
  const fOk = (r) => (!(S.turnOn && S.turnMin > 0) || (has(r.turn) && Number(r.turn) >= S.turnMin))   /* 유통 대비 거래 — 못 잰 종목(값 없음)은 뺌(11-24 재권님 「유통대비 거래에 안걸리면 목록에 안나와야해」 → 「가」 · 되돌렸다가 19:3x 「잘못 말했어 이거 넣어야돼 … 넣어놓고 풀린 주식수 다 받으면 그걸로 되게 해야해」 — 풀린 주식수는 서버 DART 밤 받기(개발2)가 채움) */ && (!(S.volOn && S.volMin > 0) || !volOpen() || atLeast(dayVolPct(r), S.volMin));   // 유통 대비 거래 · 전일 하루 거래량 대비 지금 거래량(11-24 · 프리장 빠짐)
  let rowsF = rows0.filter(fOk); FILL = new WeakSet(); let fillAdd = 0;
  // 칩 N개 종목이 모자라면 N−1개로 채움(11-24 재권님 「칩이 n개인데 5개가 안되면 n-1개로 가는것도 있으면 좋을거같은데」 → 「채움 채우지않음 선택되게해줘」)
  //   칩 N개 종목을 먼저 · 모자란 만큼 칩 N−1개 종목을 N−1번째 칩이 찬 시각별로 뒤에 붙임 · N−2 로는 안 내려감 · 채운 줄은 사는 순간도 N−1번째 칩이 찬 때
  // 채움 목표 = 「총 ( )만원 ÷ 상위 ( )종목」 칸(top) — 상위 N 에서 모자란 만큼(11-24 재권님 「가 상위종목에 지정된 숫자에서 부족한 숫자만큼」 · 채움 칸 종목 수 fillN 은 걷음)
  if (!comboMode() && S.fill && S.minChip > 1 && Number(S.top) > 0 && rowsF.length < Number(S.top)) {
    const add = rows1.filter((r) => nEver(r) === S.minChip - 1 && fOk(r)); add.forEach((r) => FILL.add(r));
    const pick = add.map((r, i) => [r, nthChipAt(r) || '9999', i]).sort((a, b) => (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : a[2] - b[2])).map((x) => x[0]).slice(0, Number(S.top) - rowsF.length);
    add.forEach((r) => { if (!pick.includes(r)) FILL.delete(r); }); fillAdd = pick.length; rowsF = rowsF.concat(pick); }
  const rowsG = st.grp && grpOn ? rowsF.filter((r) => grpHas(r, st.grp)) : rowsF;   // 섹터 · 테마 칸에서 누른 묶음만(11-24 · 칸 셈은 거르기 전 rowsF) · 본 표 그릴 때만(grpOn) — 칩별 승률 · 기간 줄 날마다 차익에는 안 듦(개념정의 덧 14:32)
  // 묶음(09:30 까지 찬 / 뒤에 찬 · 더한 줄)은 그대로 두고 그 안에서 높은 순 — 묶음 차례는 본디 차례에서 처음 나온 순(재권님 「09:30 뒤에 찬 종목」 은 그 뒤에 사는 묶음이라)
  const rgk = (r) => (d.flat930 ? (r.live === false || (all.some((y) => y.live) && !r.live) ? '더함' : '') + (FILL.has(r) ? '채움' : '') + ((nthChipAt(r) || '9999') <= chipUntil().replace(':', '') ? '앞' : '뒤') : '');
  const rgi = new Map(); rowsG.forEach((r) => { const g = rgk(r); if (!rgi.has(g)) rgi.set(g, rgi.size); });
  // 칩조합으로 살 때는 상승률 순을 안 씀 — 조합 된 시각 빠른 순(11-26 재권님 「칩조합이 먼저된 종목이 맨위에」)
  const rowsR = S.riseRank !== false && !comboMode() ? rowsG.map((r, i) => [r, orV(r), i, rgi.get(rgk(r))]).sort((a, b) => a[3] - b[3] || b[1] - a[1] || a[2] - b[2]).map((x) => x[0]) : rowsG;   // 상승률 순위(11-24) — 켜면 09:05 까지 1분 값 상승률 높은 순으로 순번 · 사는 종목 · 값 모름은 뒤(본디 차례)
  const rows0s = st.order && ORDER_FN[st.order] ? [...rowsR].sort(ORDER_FN[st.order]) : rowsR;
  // 칩조합으로 살 때는 보낸 종목을 맨 위에 고정하지 않음 — 조합이 먼저 된 종목이 맨 위(11-26 재권님 「칩조합이 먼저된 종목이 맨위에 보여지게」) · 서버 보냄은 칩 N개 룰이라 섞이면 차례가 흐트러짐
  // 서버가 실제로 보낸 종목(판 meta.buyRule.sent · 없으면 meta.tgBuy — {code: {order, sentAt, kind}})은 보낸 차례로 맨 위에 고정 · 그 뒤 상승률이 바뀌어도 안 움직임(11-24 재권님 「카드에 있것들 해」 · 개발2)
  const sentOrd = (r) => sentOrdOf(d, r);
  const rows = !comboMode() && rows0s.some((r) => sentOrd(r) != null) ? [...rows0s.filter((r) => sentOrd(r) != null).sort((a, b) => sentOrd(a) - sentOrd(b)), ...rows0s.filter((r) => sentOrd(r) == null)] : rows0s;   // 줄 세우기를 바꾸면 순번 · 상위 N 을 그 차례로
  const L = times.length - 1;
  // 그날 판 실시간 (11-11 재권님 「그날은 변동에 맞춰서 실시간으로 적용되야 하고 그날 2시가 지나면 값이 저장되도록 해줘. 다만 필터나 수수료등을 바꿨을때 값이 바뀌는건 되야되」 → 「응 진행해」)
  //   서버(개발2 dt30)가 장중에는 rows[].now · data.nowAt 을 새로 주고, 14:00 뒤 굳혀 저장하면 data.closed = true — 화면은 closed 가 아니고 now 가 있을 때만 「장중」
  const LIVE = d.closed !== true && all.some((r) => r.now != null);
  // 돈 넣는 법(11-18) — each: 상위 N 종목마다 perWon · day: 하루 dayWon 을 상위 N(보이는 종목이 적으면 그 수)으로 똑같이 나눔
  // 칩조합으로 살 때 — 조합 된 차례대로 사는 종목(산 값이 있거나 그 분 1분봉이 아직 없어 「매수값 미확인」 인 종목)을 상위 ( )종목까지 · 미확인 종목도 산 것으로 세고 돈 몫을 줌 · 값은 서버에 들어오는 대로 화면이 다시 받을 때 채움
  //   (11-26 재권님 「9시 30분까지 칩조건이 들어오는 순서대로 갯수를 채운다」 → 「칩조합으로 살때 산값을 못 잰 종목이 나와야 사야되는데」 → 「매수값미확인 이라고 하고 이값은 들어오는대로 넣어줘야해」 · 서버 알림 차례와 같게)
  const cbPick = comboMode() ? new Set(rows.filter((r) => boughtOf(r) || NOPX.has(r)).slice(0, Math.max(0, Number(S.top) || 0))) : null;
  const n = Math.min(S.top, rows.length), nb = cbPick ? cbPick.size : rows.slice(0, n).filter((r) => boughtOf(r)).length;   // 매수가 없는 종목 몫은 나누지 않음(qa 11-18 — 안 쓰는 돈이 생겼음)
  const per = S.mode === 'day' ? (nb ? S.dayWon / nb : 0) : S.perWon;
  // 굳힘 묶음마다 돈 (11-20 재권님 「굳힘 창별로 금액을 추가하는걸로」 → (가) → 「응 만들어」) — 굳힌 판이면 굳힘마다 grpWon 을 그 묶음(보이는 · 매수가 있는) 종목 수로 똑같이 나눠 삼
  //   상위 N 은 안 씀 · 아직 안 굳은 「진행 중」 은 돈 안 넣음 · 굳힘 없는 판(09:05 전 · 지난 날)은 위 셈 그대로 · grpWon 이 비면 dayWon 과 같게
  //   이름이 lock 으로 시작하지 않게(grpWon) — 셈 칸의 굳힘 시각 칸을 data-set^="lock" 으로 고름
  // 「사지 않음」 굳힘 묶음은 돈을 안 넣음(셈 칸 set.lockNoBuy [첫째 · 둘째 · 셋째 · 장중] — 승률 표 서버 dt30_win 과 같은 열쇠 · 판에는 남김 · 재권님 「굳힘에 사지않는다 라는 버튼도 하나 만들어줘」 11-23)
  const lkMode = all.some((r) => Number(r.lock) > 0), lkWon = S.grpWon > 0 ? S.grpWon : S.dayWon;
  const lkCnt = {}; if (lkMode) rows.forEach((r) => { const j = Number(r.lock); if (boughtOf(r) && !noBuyOf(j)) { const g = j > 0 ? j : 0; lkCnt[g] = (lkCnt[g] || 0) + 1; }   /* 매도 시각보다 늦게 든 종목은 몫을 안 받음(nb 와 같은 셈 · qa 11-20) */ });
  const perOf = (r) => { if (!lkMode) return per; const j = Number(r.lock); const g = j > 0 ? j : 0, gw = g > 0 ? Number((S.grpWons || [])[g - 1]) : 0; return lkCnt[g] ? (gw > 0 ? gw : lkWon) / lkCnt[g] : 0; };   // 굳힘 칸마다 금액(11-23 · 셈 칸 grpWons) · 빈칸이면 「굳힘마다 금액」   // 대기 묶음(0)도 굳힘 금액을 그 수로 나눠 산 것으로(11-23) · 합계(P)는 굳은 줄만
  const ch = (r, t) => { const B = boughtOf(r), v = Number((r.px || {})[t]); return !B || hhmm(t) <= B.at || (r.px || {})[t] == null || !Number.isFinite(v) ? null : (v / B.px - 1) * 100; };   // 산 시각 앞 칸은 비움
  const mkR = (r) => { const p = times.map((t) => ch(r, t)); const B0 = boughtOf(r), one = (SS, oo) => { const sb = SS.sellBar === '1m' || SS.sellBar === '5m' ? SS.sellBar : '', bs = sb && B0 && !LIVE ? barsOf(r, sb) : null; return bs ? sellBars(r, B0, times, bs, sb === '1m' && r.barSrc !== '5m' ? 1 : 5, { ...oo, S: SS }) : sellAt(p, times, (B0 || {}).at, { ...oo, S: SS }); };
    const s = !MKL || !B0 ? one(S, {}) : (() => { const s1 = one(S, { until: MKL.at }); if (s1.k >= 0) return s1; const SS = { ...S, sellBar: MKL.line.sellBar || S.sellBar, stop: MKL.line.stop == null || MKL.line.stop === '' ? null : Number(MKL.line.stop) }; const s2 = one(SS, { from: MKL.at }); return s2.k >= 0 ? { ...s2, why: `${s2.why}(코스피 ${MKL.side === 'up' ? '상승' : '하락'})` } : s2; })();   // 코스피 조건 줄(11-24) — 그 시각 전은 맨 윗줄 · 뒤는 고른 줄   // 매도 봉 1분 · 5분(기본)이면 봉으로 · 30분이거나 봉이 없는 줄 · 장중은 30분 칸   // 봉 줄이 있으면 봉으로 판 때 · 값(11-23 · 장중은 30분 칸 그대로)
    if (s.px != null && s.k >= 0) p[s.k] = (s.px / B0.px - 1) * 100;   // 판 칸에는 판 값의 % (봉 매도면 칸 시각 값이 아니라 판 값)
    let last = L; while (last >= 0 && p[last] == null) last--; const nowCh = LIVE && s.k < 0 && Number(r.now) > 0 && boughtOf(r) ? (Number(r.now) / boughtOf(r).px - 1) * 100 : null;   // 장중 · 안 판 종목 — 결과 · 손익은 서버 지금 값(rows[].now)
    const at = s.k >= 0 ? s.k : last, sellPx = s.px != null ? s.px : nowCh != null ? Number(r.now) : at >= 0 ? Number((r.px || {})[times[at]]) : null;
    const b = boughtOf(r) ? boughtOf(r).px : 0, qty = b > 0 ? Math.floor(perOf(r) / b) : 0;
    const T = taxOf(r.market);
    const pnl = qty > 0 && Number.isFinite(sellPx) ? (() => {
      const buyAmt = qty * b, sellAmt = qty * sellPx;
      const tx = T ? sellAmt * T.tx / 100 : null, rural = T ? sellAmt * T.rural / 100 : null;
      const fee = st.fee == null ? null : sellAmt * st.fee / 100;   // 팔 때만
      return { buyAmt, sellAmt, gross: sellAmt - buyAmt, tx, rural, fee, net: T ? sellAmt - buyAmt - tx - rural - (fee || 0) : null };
    })() : null;
    return { r, p, s, pnl, sellPx, T, now: nowCh != null, res: s.k >= 0 ? p[s.k] : nowCh != null ? nowCh : (last >= 0 ? p[last] : null) }; };
  // 09:30 뒤에 찬 종목(셈 칸 「안 삼」) — 장중 창 보기만 줄과 같은 룰: 판에 든 때 값으로 샀다고 친 가정 셈 · 매도 룰 그대로 · 상위 N · 손익 · 평균 · 합계에는 안 듦
  //   (11-25 재권님 「9시 30분 뒤에 찬 종목도 셈은 해야해」 → 「산다라는 룰은 아니고 셈에서만 빠지는거야」 → 「장중 창과 같은룰로 해야지」) · 몫(nb · lkCnt)을 다 센 뒤에 가정 값을 넣어 돈 나누기에 안 섞임
  const late = new Set(d.flat930 && !S.buyLate930 ? rows.filter((r) => !buyOf(r) && Number(r.buy) > 0 && (nthChipAt(r) || '') > chipUntil().replace(':', '')) : []);
  late.forEach((r) => { const t = inTs(r); HYPO.set(r, { px: Number(r.buy), at: t.slice(0, 4), src: `${t.length >= 6 ? `${t.slice(0, 2)}:${t.slice(2, 4)}:${t.slice(4, 6)}` : '—'} 든 때 · 가정(산 것 아님)` }); });
  const R = rows.map((r) => { const x = mkR(r); if (late.has(r)) x.hypo = true; return x; });
  const inv = (lkMode ? R.filter((x) => Number(x.r.lock) > 0) : cbPick ? R.filter((x) => cbPick.has(x.r)) : R.slice(0, n)).filter((x) => !x.hypo);   // 돈을 넣은 줄 — 굳힌 판은 굳힌 종목 전부 · 아니면 상위 N · 가정 줄은 뺌
  inv.forEach((x) => { x.inv = true; });
  if (S.pyr) pyrCalc(inv, times);
  const top = inv.filter((x) => x.pnl), sum = (k) => top.reduce((a, x) => a + (x.pnl[k] || 0), 0);
  const noMkt = top.filter((x) => x.pnl.net == null).length;   // 시장을 모르는 종목 — 세금을 못 셈
  const P = top.length ? { n: top.length, buy: sum('buyAmt'), sell: sum('sellAmt'), gross: sum('gross'), tx: sum('tx'), rural: sum('rural'), fee: st.fee == null ? null : sum('fee'), net: sum('net'), pyr: sum('pyr'), pyrN: top.reduce((a, x) => a + (x.pnl.adds || []).length, 0), win: top.filter((x) => x.pnl.net > 0).length } : null;
  // 굳힘 묶음마다 넣은 돈 · 세후 손익 — 굳힘 단추 줄에 · 묶음 합 = 위 P(굳힌 판이면 굳힌 줄만 셈)
  const G = {}; if (lkMode) top.forEach((x) => { const j = Number(x.r.lock), g = G[j] || (G[j] = { n: 0, buy: 0, net: 0, noMkt: 0 }); g.n++; g.buy += x.pnl.buyAmt; if (x.pnl.net == null) g.noMkt++; else g.net += x.pnl.net; });
  // 장중 창에 든 종목 중 칩 수가 셈 칸에 모자라 걸러진 것 — 본 표 아래 같은 모양으로 「보기만」(11-24 재권님 「가」 → 「위에 있는것과 같은 룰로 보여지게」)
  //   같은 셈(mkR)으로 칸 값을 내되 inv 를 안 붙여 상위 N · 손익 · 평균 · 합계에는 안 듦 · 어느 줄인지는 서버 meta.intra.lock 한 곳 · 유통 시총 거르기는 본 표와 같게
  const IX = (d.meta || {}).intra, fMax = 0;   // 유통 ( )억 이하 거르기는 뺌(11-24)
  const RV = IX && IX.lock != null ? rows1.filter((r) => Number(r.lock0 != null ? r.lock0 : r.lock) === Number(IX.lock) && !rows.includes(r) && !(fMax > 0 && Number.isFinite(Number(r.floatCap)) && Number(r.floatCap) > fMax))
    .sort((a, b) => String(a.buyTs || a.buyAt || '').localeCompare(String(b.buyTs || b.buyAt || ''))).map((r) => { const t = inTs(r);
      if (Number(r.buy) > 0) HYPO.set(r, { px: Number(r.buy), at: t.slice(0, 4), src: `${t.length >= 6 ? `${t.slice(0, 2)}:${t.slice(2, 4)}:${t.slice(4, 6)}` : '—'} 든 때 · 가정(산 것 아님)` });
      const x = mkR(r); x.hypo = true; return x; }) : [];
  // 칩 N개 칸 밑 종목도 아래에 보기만(11-26 재권님 「칩을 고르면 해당칩 개수에 찬것만 보여지는게 아니고 … 5개를 하면 5개가 위로 보여지고 4개이하는 그하위로」 · 「보여져야 하는 총 개수는 30개로」)
  //   칩 N개 이상(+ 채운 줄)은 위 본 표 그대로 사고 셈 · 그 밖 켜진 칩에 걸린 종목은 칩 수 많은 순(같으면 본디 차례)으로 그 아래 · 사지 않음 · 상위 N · 손익 · 평균 · 합계에 안 듦
  //   유통 대비 거래 · 섹터 · 테마 거름은 위와 같게 · 본 표 + 장중 창 보기만 + 이 줄 합이 SHOW_MAX 까지
  const RVs = new Set(RV.map((x) => x.r));
  const RB = S.minChip > 0 || comboMode() ? rows1.map((r, i) => [r, nEver(r), i]).filter(([r]) => !rows.includes(r) && !RVs.has(r) && fOk(r) && !(st.grp && grpOn && !grpHas(r, st.grp)))
    .sort((a, b) => b[1] - a[1] || a[2] - b[2]).slice(0, Math.max(0, SHOW_MAX - rows.length - RV.length)).map(([r]) => { const x = mkR(r); x.below = true; return x; }) : [];
  return { fillAdd, times, all, live, rows1, rowsF, rows, L, LIVE, R, n, nb, per, top, noMkt, P, lkMode, lkWon, lkCnt, G, RV, IX, RB };
}

// 날별 합계에서 손익이 없는 날의 까닭 (11-23 재권님 「응」) — 매수가가 분 칸(09:01 ~ 09:05)인데 돈 넣을 줄 전부 그 분 값이 없으면(1분봉을 11-12 부터 쌓아 그 앞 날은 비어 있음)
//   「09:01 값 없음」 · 그 밖은 「매매 없음」 그대로
//   그날 판(D)으로 셈 — 분 칸 시각 · 매수가가 그날 meta(여는 시각 · pxMinAt)를 따르게. 전에는 calc 밖이라 보고 있는 날 시각을 써서 11-19(10시 개장)를 보면 다른 날도 「10:01」 (11-25 재권님 「1 고쳐」)
function noTradeWhy(C, D) {
  const keep = calcD; calcD = D ? flat930(D) : calcD;
  try {
    const n = pmOf(buyKey()), xs = C.lkMode ? C.R.filter((x) => Number(x.r.lock) > 0) : C.R.slice(0, C.n);
    return n && xs.length && xs.every((x) => { const o = minVal(x.r, n); return !buyOf(x.r) && !(o && Number(o.px) > 0); }) ? `${hmS(minHM(n))} 값 없음` : '매매 없음';
  } finally { calcD = keep; }
}

// 불타기 (11-18 재권님 「손절한 종목을 상승한 종목에 불타기 하는것도 추가해줘」 → (가) 「가로 해줘. 이걸 할지말지를 넣을수 있게」)
//   · 상위 종목 중 손절로 판 종목이 있으면, 그 판 돈(세금 · 수수료 뺀 것)을 그 30분 시각에 아직 들고 있는 종목 중 매수가 대비 가장 많이 오른 한 종목에 그 시각 값으로 더 산다
//   · 더 산 몫은 그 종목이 파는 때 · 값에 함께 판다(세금 · 수수료 같은 셈) · 번 돈은 그 종목 손익(net)에 더해 합계 · 칩 묶음 · 달 합계가 함께 따라감
//   · 그 종목도 나중에 손절되면 더 산 몫까지 판 돈이 다시 불타기로 감 · 오르는 종목이 없거나 시장을 모르면 판 돈은 그대로 둠
function pyrCalc(top, times) {
  const fee = (amt) => (st.fee == null ? 0 : amt * st.fee / 100);
  const outOf = (T, amt) => amt - (T ? amt * (T.tx + T.rural) / 100 : 0) - fee(amt);   // 판 금액 → 손에 남는 돈
  top.forEach((x) => { if (x.pnl) { x.pnl.adds = []; x.pnl.pyr = 0; } x.pyrTo = null; });
  const ev = top.filter((x) => x.pnl && x.s.k >= 0 && x.s.why === '손절').sort((a, b) => a.s.k - b.s.k);
  ev.forEach((x) => {
    const k = x.s.k;
    const cash = outOf(x.T, x.pnl.sellAmt) + x.pnl.adds.reduce((a, o) => a + o.back, 0);
    const c = top.filter((y) => y !== x && y.pnl && y.T && (y.s.k < 0 || y.s.k > k) && y.p[k] != null && y.p[k] > 0 && Number.isFinite(y.sellPx));
    if (!c.length) return;
    const y = c.reduce((a, b) => (b.p[k] > a.p[k] ? b : a));
    const px = Number((y.r.px || {})[times[k]]), qty = px > 0 ? Math.floor(cash / px) : 0;
    if (!(qty > 0)) return;
    const buyAmt = qty * px, sellAmt = qty * y.sellPx, back = outOf(y.T, sellAmt), gain = back - buyAmt;
    y.pnl.adds.push({ from: x.r.name, k, qty, px, buyAmt, sellAmt, back, gain });
    y.pnl.pyr += gain; if (y.pnl.net != null) y.pnl.net += gain;
    x.pyrTo = { name: y.r.name, k };
  });
}

// 다시 그려도 종목 머리 칸 유통 거르기에 치던 글 · 커서를 지킴(판은 서버 주기마다 다시 그림 · 11-23)
function paint(d) {
  const ae = document.activeElement, fk = ae && ae.matches && ae.matches('#dt-box [data-set="floatMax"]') ? { v: ae.value, p: ae.selectionStart } : null;
  paint0(d);
  if (fk) { const el = document.querySelector('#dt-box [data-set="floatMax"]'); if (el) { el.value = fk.v; el.focus(); try { el.setSelectionRange(fk.p, fk.p); } catch (e) { /* 숫자 칸 */ } } }
}
function paint0(d) {
  atText(d.buyAt);
  if (d.meta && d.meta.subNames && typeof d.meta.subNames === 'object') Object.assign(SUB_NAME, d.meta.subNames); if (d.meta && d.meta.subTips && typeof d.meta.subTips === 'object') Object.assign(SUB_TIP, d.meta.subTips);
  st.rules = (d.meta && d.meta.rules) || null; st.chipInfo = (d.meta && d.meta.chipInfo) || null;   // 칩 풍선 — 서버 룰 값 · 받는 때 글(tipOf)
  st.miss = new Set(names(d.meta && d.meta.missing)); st.wait = new Set(names(d.meta && d.meta.wait)); st.watchAuto = !!(d.meta && d.meta.watchRule === '자동'); st.openAt = (d.meta && d.meta.openAt) || ((d.rows || []).find((r) => r.buySrc && r.buyAt) || {}).buyAt || null; st.rebuilt = !!(d.meta && d.meta.rebuilt === true);   // openAt — 서버 meta.openAt · 없으면(다시 센 판) 줄의 buyAt
  { const k = Number(d.meta && d.meta.minChips); if (root) root.querySelectorAll('.dt-min').forEach((e) => { e.textContent = k > 0 ? `칩 ${k}개 이상 든 종목` : '칩 하나 이상 든 종목(옛 셈 판)'; }); }   // 문턱은 서버 meta.minChips 한 곳(11-18 판부터 둘 이상)
  grpOn = true; let C; try { C = calc(d); } finally { grpOn = false; }
  const { RV, RB, IX, times, all, live, rows1, rows, L, LIVE, R, n: topN, per, top, noMkt, P, lkMode, lkWon, lkCnt, G } = C;
  stPaint(C.rowsF || []);
  usLoad(d.day);
  // 칩 줄은 표 안 「종목」 머리 줄과 「평균」 줄 사이에 (11-11 재권님 「칩위치는 종목과 평균사이에 넣어줘」) · 표가 옆으로 밀려도 칩은 왼쪽에 붙어 있음(strategy.css)
  const chipRow = (n) => `<tr class="dt-chiprow"><td colspan="${n}"><div class="dt-chips" id="dt-chips" aria-label="단타 칩 — 눌러서 켜고 끄기"><span class="dt-hd">단타 칩</span>${chipPanel(all)}<span class="dt-us" id="dt-us" data-day="${esc(d.day || '')}">${usHtml(d.day)}</span></div></td></tr>`;
  $('dt-only').innerHTML = ONLY.map(([k, t]) => `<button type="button" class="kh-chip${st.only === k ? ' is-active' : ''}" data-only="${k}">${t}${k ? ` ${all.filter((r) => (r.chips || []).includes(k)).length}` : ` ${all.length}`}</button>`).join('');
  $('dt-order').innerHTML = ORDER.map(([k, t]) => `<button type="button" class="kh-chip${st.order === k ? ' is-active' : ''}" data-order="${k}">${t}</button>`).join('');
  // 평균 (11-18 재권님 「평균값이 뭔가 이상한데」 → (나)) — 판 종목은 판 값으로 고정해 그 뒤 시각에도 넣는다 · 그 시각까지 실제로 번 수익률
  //   전에는 판 칸부터 뺐는데(11-11) 오후에 끝까지 오른 몇 종목만 남아 평균이 부풀었다(11-17 12:30~ 2종목 +21.79%)
  const atK = (x, k) => (x.s.k >= 0 && k >= x.s.k ? x.p[x.s.k] : x.p[k]);
  const RA = R.filter((x) => !x.hypo);   // 09:30 뒤에 찬 종목(가정 셈)은 평균에 안 듦 — 장중 창 보기만과 같게
  const avg = times.map((_, k) => mean(RA.map((x) => atK(x, k)).filter((v) => v != null)));
  const res = RA.map((x) => x.res).filter((v) => v != null), resAvg = mean(res);
  const sold = RA.filter((x) => x.s.k >= 0);
  st.last[d.day] = resAvg;
  const bm = d.meta || {}, nm = (a) => names(a).join(' · ');   // 되채운 날 · 못 받은 칩 — 칩 이름은 서버가 준 그대로
  const rebuilt = bm.rebuilt === true ? ` · 되채운 날${nm(bm.missing) ? ` · ${nm(bm.missing)} 못 셈` : ''}${nm(bm.approx) ? ` · ${nm(bm.approx)} 어림` : ''}` : `${nm(bm.missing) ? ` · 못 받은 칩 ${nm(bm.missing)}` : ''}${nm(bm.early) ? ` · ${nm(bm.early)} 어림(집계 전)` : ''}${bm.late && typeof bm.late === 'object' && Object.keys(bm.late).length ? ` · 늦게 채움 ${Object.entries(bm.late).map(([k, v]) => `${k} ${v}`).join(' · ')}` : ''}`;
  $('dt-meta').textContent = `${dayTxt(d.day)}${rebuilt}${C.fb905 ? ' · 그날 룰로는 매매가 없어 여는 시각 + 5분(9:05 · 늦게 연 날은 그만큼 뒤)에 산 것으로 셈' : ''}${LIVE ? ` · 장중 실시간(${esc(String(d.nowAt || '—'))} 값 · 14:00 뒤 굳혀 저장)` : d.closed === true ? ' · 14:00 뒤 굳힌 값' : ''} · 후보 ${num(all.length)} 중 켜진 칩에 걸린 ${num(live.length)} · 보이는 ${num(rows.length)} · ${d.flat930 && buyKey() === 'p1' ? `줄 = 켠 칩 ${chipNeed()}개 먼저 찬 순(${chipUntil()} 앞 · 뒤로 가름) · 매수가 = 찬 때 값(줄마다 매수가 칸 아래)` : d.buyAt ? (st.openAt ? `${hmTxt(d.buyAt)} 부터 판 · 매수가 = 정규장 ${hmTxt(String(st.openAt).replace(':', ''))} 시가` : `${hmTxt(d.buyAt)} 매수`) : '매수 시각 —'} · 판 것 ${sold.length}(손절 ${sold.filter((x) => x.s.why === '손절').length} · 꺾임 ${sold.filter((x) => x.s.why === '꺾임').length} · 고점 ${sold.filter((x) => x.s.why === '고점').length} · 산 뒤 ${st.set.cutMin}분 미달 ${sold.filter((x) => x.s.why === '미달').length}${st.set.flat ? ` · 횡보 ${sold.filter((x) => x.s.why === '횡보').length}` : ''}${st.set.endAt ? ` · ${hmTxt(st.set.endAt)} 매도 시각 ${sold.filter((x) => x.s.why === '매도 시각').length}` : ''}) · 끝까지 들고 감 ${R.length - sold.length} · 결과 평균 ${sgn(resAvg)} · 이긴 것 ${res.filter((v) => v > 0).length} · 진 것 ${res.filter((v) => v < 0).length}`;
  if (C.fillAdd) $('dt-meta').textContent += ` · 칩 ${st.set.minChip}개 종목이 상위 ${st.set.top}종목이 안 돼 칩 ${st.set.minChip - 1}개 종목 ${C.fillAdd}개로 채움`;   // 11-24
  if (mkOn() && KX.bars && !mkHas(d.day)) $('dt-meta').textContent += ' · 이 날 코스피 값 없음 — 코스피 조건 매도 줄 안 씀(맨 윗줄로 셈)';   // 11-24 개념정의 덧
  // 상위 몇 종목 · 금액은 이 줄에서 바로 넣는다(11-18 재권님 「상위종목 갯수넣을수 있게 금액도 넣을수 있게 … 이거 수정하면 일별로 다 값이 다시 적용되서 그달 총액 다시 정산되게」) — 바꾸면 그날 판 · 달 합계(monthPaint)가 같은 셈으로 다시 셈
  { const nob = rows.filter((r) => { const B = buyOf(r); return !B || (st.set.endAt && B.at >= st.set.endAt); }).length   /* 매도 시각보다 늦게 든 종목도 안 삼(calc 의 boughtOf 와 같은 셈) */; if (nob) $('dt-meta').textContent = $('dt-meta').textContent.replace(/끝까지 들고 감 (\d+)/, (m, k) => `끝까지 들고 감 ${+k - nob} · 안 삼 ${nob}`); }   // 안 산 종목(고른 시각 뒤에 듦 · 값 없음)은 들고 간 것이 아님 — 따로 셈(11-20)
  if (st.chipFail) $('dt-meta').textContent += ' · 칩 목록 — 서버 값 못 받음(이 판에 실린 칩으로 셈)';   // 그리기마다 다시 붙임 — 폴링으로 다시 그리면 머리 글을 통째로 다시 써서 load 쪽에서 붙인 것이 지워지던 것(qa 11-20 15:41)
  const IN_TOP = '<input data-set="top" class="rl-in rl-num" inputmode="numeric" aria-label="상위 몇 종목">', IN_WON = '<input data-set="won" class="rl-in rl-num" inputmode="numeric" aria-label="금액(만원)">';
  const IN_GRW = '<input data-set="grpWon" class="rl-in rl-num" inputmode="numeric" aria-label="묶음마다 금액(만원)">';
  const head = lkMode ? `${LKW()}마다 ${IN_GRW}만원 ÷ 그 묶음 종목 수` : `총 ${IN_WON}만원 ÷ 상위 ${IN_TOP}종목`;   // 굳힌 판은 굳힘마다 돈(11-20) · 굳힘 없는 판은 지금 그대로   // 재권님 「종목에 똑같이 나눠 - 종목마다 3000만원 이것을 종목 으로 바꿔」 → 「앞에 금액은 총금액이고 종목수로 나눠서 사는걸로」 — 총액을 종목 수로 똑같이 나눠 삼(종목마다 몫은 손익 칸 머리에)
  // 칸 둘은 한 번만 만들고 뒤 글만 바꾼다(qa 11-18 — 장중 다시 그릴 때마다 칸을 새로 만들어 치는 도중 글자 · 커서가 사라졌음)
  const sumEl = $('dt-pnl-sum'); if (!sumEl.querySelector('.dt-pnl-rest') || sumEl.dataset.lk !== String(lkMode)) { sumEl.innerHTML = `<b>${head}</b><span class="dt-pnl-rest"></span>`; sumEl.dataset.lk = String(lkMode); }   // 굳힌 판 ↔ 아닌 판을 오갈 때만 칸을 다시 만듦
  sumEl.querySelector('.dt-pnl-rest').innerHTML = P ? ` · 산 ${wonPlain(P.buy)} · 판 ${wonPlain(P.sell)} · 빼기 전 ${won(P.gross)}`
    + ` · 거래세 ${wonPlain(P.tx)} · 농특세 ${wonPlain(P.rural)} · 수수료 ${P.fee == null ? '빈칸 — 안 셈' : wonPlain(P.fee)}`
    + `${P.pyrN ? ` · 불타기 ${P.pyrN}번 ${won(P.pyr)}` : st.set.pyr ? ' · 불타기 0번' : ''} · <b>세후 손익 <span class="${signClass(P.net, NUM) || ''}">${won(P.net)}</span> (${pct(P.net / P.buy * 100)})</b>${lkMode ? ` <span class="rl-sug">${winMode() ? '창에 든 묶음 합 · 문턱 밑 종목은 셈 밖' : '굳힌 묶음 합 · 안 굳은 종목은 셈 밖'}</span>` : ''}${noMkt ? ` · 시장 모름 ${noMkt}종목은 세후에서 뺌` : ''}` : ' · — 손익을 셀 값이 없음';
  setFill();
  // 0종목일 때 까닭 (11-19 재권님 「응」 — 거르기 칸 때문에 다 가려진 것을 「판이 없다」 로 읽지 않게) — 판이 빔 · 켜진 칩에 0 · 「든 것만」 거르기 · 「칩 N개 이상」 칸을 갈라 적음
  if (!rows.length && !RB.length) {   // 칩 N개 종목이 없어도 그 밑 종목(보기만)이 있으면 표를 그림(11-26)
    // 꺼 둔 칩 · 칸에서 뺀 칩 · 꺼 둔 하위 칩 이름과 그날 판에서 그 칩이 든 종목 수(11-20 재권님 「가하라고 해」 — 11-19 「vi가 왜 안나오지?」 때 VI·급등 칩이 꺼져 있었는데 까닭 글에 이름이 없었다)
    const cnt = (c) => all.filter((r) => (r.chips || []).includes(c)).length, cols = colsOf();
    const offTxt = [...new Set(all.flatMap((r) => r.chips || []))].map((c) => (st.off.has(c) ? `${c} 꺼 둠(${num(cnt(c))})` : !cols.includes(c) ? `${c} 칸에 없음(${num(cnt(c))})` : ''))
      .concat([...st.subOff].map((k) => { const [c, x] = k.split('|'), n = all.filter((r) => subsOf(r, c).includes(x)).length; return n ? `${c} 〉 ${x} 꺼 둠(${num(n)})` : ''; })).filter(Boolean).join(' · ');
    const onlyOff = st.only && (st.off.has(st.only) || !cols.includes(st.only));
    const why = !all.length ? '이 날 굳힌 단타 종목 없음'
      : !live.length ? `켜진 칩에 걸린 종목 0 · 그날 판은 ${num(all.length)}종목 — ${offTxt || '꺼 둔 칩'}${offTxt ? ' — 켜면 보입니다' : '을 켜면 보입니다'}`
      : !rows1.length && onlyOff ? `「${st.only} 든 것만」 거르기인데 ${st.only} 칩이 ${st.off.has(st.only) ? '꺼져' : '칸에 없어'} 0종목 · 그 칩이 든 종목 ${num(cnt(st.only))} — 칩을 켜거나 거르기를 「전체」 로`
      : !rows1.length ? `「${st.only} 든 것만」 거르기에 0종목 · 켜진 칩에 걸린 ${num(live.length)}종목${offTxt ? ` · ${offTxt}` : ''} — 거르기를 「전체」 로 하거나 꺼 둔 칩을 켜면 보입니다`
      : `칩 ${st.set.minChip}개 이상인 종목 0 · 켜진 칩에 걸린 ${num(rows1.length)}종목${offTxt ? ` · ${offTxt}` : ''} — 칩 칸을 비우거나 꺼 둔 칩을 켜면 보입니다`;
    // 판이 비면 칩 칸(표 머리)도 같이 사라져 다시 켤 자리가 없다 — 꺼 둔 칩이 있으면 여기서 한 번에 켬
    // 칸에 없는 칩도 「+ 칩」 단추가 표 머리에 있어 같이 사라진다 — 이 단추가 칸에 다시 넣고 켬(qa 11-20 덧 「칸에 없음 뿐이면 단추가 안 뜸」)
    const miss = [...new Set(all.flatMap((r) => r.chips || []))].filter((c) => !cols.includes(c) && !(st.watchAuto && c === '자동'));
    const allOn = st.off.size || st.subOff.size || miss.length ? `<div style="margin-top:12px"><button type="button" class="kh-chip" data-allon style="font-size:14px;padding:6px 16px">${miss.length ? '꺼 둔 칩 · 칸에 없는 칩 다 켜기' : '꺼 둔 칩 다 켜기'}</button></div>` : '';
    // 빈 판 까닭은 가운데 크게(11-20 재권님 「가운데에 좀더 크게」)
    // 어제 미국장 · 지금 바깥 줄은 판이 비어도 위에 남김(11-25 재권님 「필라델피아 반도체지수 선물 등등 … 없어졌어」 → 「응 그렇게 해줘」 — 표 머리 안에 있어 표와 함께 사라졌음) · id 같아 usLoad 가 받은 뒤 채움
    $('dt-box').innerHTML = `<div style="padding:8px 0 0"><span class="dt-us" id="dt-us" data-day="${esc(d.day || '')}" style="border-left:0;padding-left:0">${usHtml(d.day)}</span></div><div class="st-err" style="text-align:center;font-size:16px;line-height:1.7;padding:48px 16px;color:var(--kh-text-secondary)">${esc(why)}${allOn}</div>`; return;
  }
  const shr = (a) => (a >= 1e4 ? `${(a / 1e4).toFixed(a >= 1e5 ? 0 : 1).replace(/\.0$/, '')}만` : a >= 1e3 ? `${Math.round(a / 1e3)}천` : String(a));   // 주
  const wonS = (a) => (a >= 1e8 ? `${(a / 1e8).toFixed(a >= 1e9 ? 0 : 1).replace(/\.0$/, '')}억` : a >= 1e4 ? `${Math.round(a / 1e4)}만` : String(a));   // 원
  // 진행 중(창 문턱 밑 · 안 산 줄)도 그 시각 가격 · 처음 든 때 값 대비 % 를 보임(11-23 재권님 「다 보이게 해줘. 칩이랑 룰 체크해서 하면 다시 되야되는 종목들이야」) — 보기만 · 손익 · 평균 · 합계 셈(x.p)에는 안 듦
  const pvOf = (r, t) => { if (buyOf(r) || !(Number(r.buy) > 0)) return null; const e = String(r.buyAt || '').replace(/:/g, '').slice(0, 4), v = Number((r.px || {})[t]); return (r.px || {})[t] == null || !Number.isFinite(v) || (e && hhmm(t) <= e) ? null : (v / Number(r.buy) - 1) * 100; };
  const cell = (x, k) => {
    const v = x.p[k] != null ? x.p[k] : pvOf(x.r, times[k]);
    // 그 시각 가격을 % 위에 · 글씨는 검정(색은 아래 % 만) — 11-20 재권님 「등락률 위에 가격도 같이 보이게 해줘」 → 색을 넣어 보시고 「글씨는 그냥 검정으로 하자 보기 힘드네」
    const px = Number((x.r.px || {})[times[k]]);
    // 안 산 줄도 그 시각 가격은 보임(11-24 재권님 「장이 늦게 열리든 말든 가격변동이아 주가가 보여야지」) — % 는 매수가가 있을 때만
    const pxT = (x.r.px || {})[times[k]] == null || !Number.isFinite(px) ? '' : `<span style="display: block; line-height: 1.25;">${num(px)}</span>`;
    // 그 시각까지 쌓인 수급 한 줄(11-18 재권님 「시간별로 % 아래에서 … 시간이 지나면 그값이 고정」 → 11-20 그림 (나) 「이방향으로」) — 서버 rows[].flow{시각: {fr 외국인 · inst 기관 · pg 프로그램(원) · ff 외국계 창구}}(개발2 · 장 시작부터의 합) · 못 받은 칸은 줄 없음
    const fl = (x.r.flow || {})[times[k]];
    const flT = !fl ? '' : `<small style="display: block; font-size: 10px; line-height: 1.3; white-space: nowrap; font-weight: 400;">${[['외', fl.fr, shr], ['기', fl.inst, shr], ['프', fl.pg, wonS], ['창', fl.ff, shr]].map(([t, n, f]) => { const c = n == null ? '' : signClass(n, NUM); return `${t}${n == null ? '—' : `<span class="${c || ''}">${n > 0 ? '+' : n < 0 ? '−' : ''}${f(Math.abs(n))}</span>`}`; }).join(' ')}</small>`;   // 줄 높이를 좌우 두 줄 칸(51px)에 맞춤 — 그대로 두 줄이면 56px 라 10번째 줄이 잘림(qa 11-20) · strategy.css 는 남의 미커밋이 있어 여기 둠
    // 봉으로 판 줄(x.s.px · x.s.at)은 그 칸 시각 값이 아니라 판 값 · 판 시각을 보임(11-23 — 칸 시각 값을 두면 % 와 안 맞아 보임)
    if (x.s.k >= 0 && k === x.s.k && x.s.px != null) return `<td class="dt-sold"><span style="display: block; line-height: 1.25;">${num(x.s.px)}</span>${pct(v)}<em>${hmTxt(x.s.at)} ${x.s.why}</em>${flT}${x.pyrTo ? `<small class="dt-pyr"> → ${esc(x.pyrTo.name || '—')} 불타기</small>` : ''}</td>`;
    if (x.s.k >= 0 && k === x.s.k) return `<td class="dt-sold">${pxT}${pct(v)}<em>${x.s.why}</em>${flT}${x.pyrTo ? `<small class="dt-pyr"> → ${esc(x.pyrTo.name || '—')} 불타기</small>` : ''}</td>`;
    { const ad = x.pnl && (x.pnl.adds || []).filter((o) => o.k === k); if (ad && ad.length) return `<td class="${k === L ? 'dt-last' : ''}">${pxT}${pct(v)}${flT}<small class="dt-pyr"> ← ${ad.map((o) => esc(o.from || '—')).join(' · ')} 손절 돈 불타기</small></td>`; }
    if (x.s.k >= 0 && k > x.s.k) return `<td class="dt-after">${v == null ? '—' : sgn(v)}${flT}</td>`;   // 판 뒤 칸도 외 · 기 · 프 · 창 줄(11-25 재권님 「단타에 칩 걸려서 보여지는 종목들은 외기창 다 나오게 해줘」)
    return `<td class="${k === L ? 'dt-last' : ''}">${pxT}${v == null && pxT ? '' : pct(v)}${flT}</td>`;
  };
  const plTd = (x, i) => (x.hypo ? `<td class="dt-pl dt-hypo" data-tip="들어올 때 값으로 샀다고 치고 셈한 값 — 실제로 산 것이 아니라 합계 · 평균에 안 듦">${x.pnl && x.pnl.net != null ? `<span class="${signClass(x.pnl.net, NUM) || ''}">${won(x.pnl.net)}</span><small>가정 · 산 것 아님</small>` : '<span class="st-err">—</span>'}</td>` : `<td class="dt-pl">${x.inv && x.pnl ? (x.pnl.net == null ? '<span class="st-err">시장 모름</span>' : `<span class="${signClass(x.pnl.net, NUM) || ''}">${won(x.pnl.net)}</span><small>빼기 전 ${won(x.pnl.gross)}${x.pnl.adds && x.pnl.adds.length ? ` · 불타기 ${won(x.pnl.pyr)}` : ''}</small>`) : x.pnl && x.pnl.net != null ? `<span class="${signClass(x.pnl.net, NUM) || ''}" data-tip="상위 종목 밖이라 산 것은 아니지만, 산 종목과 같은 금액 · 같은 파는 룰로 셈한 값 — 합계 · 평균에 안 듦">${won(x.pnl.net)}</span><small>가정 · 상위 밖 · 산 것 아님</small>` : '<span class="st-err">—</span>'}</td>`);   // 상위 밖 줄도 가정 셈(11-26 재권님 「사지 않았지만 계산해달라고 해논거는 왜 안댐?」)
  // 결과 칸에 지금 가격(11-23 재권님 「결과에 지금가격도 보여지고 갱신되도록해」) — 서버 rows[].now · data.nowAt(장중 · 굳기 전) · 갱신은 판을 다시 받는 서버 주기(meta.refreshMs) 그대로 · 칸을 통째로 다시 그려 거르는 표 없음
  const nowTxt = (r) => (LIVE && Number(r.now) > 0 ? `지금 ${num(Number(r.now))}` : '');
  // 판 때를 판 가격 위에(11-25 재권님 「매도가 이루어질때를 맨오른쪽 가격위에 써주면 좋을거같아 단타에 칩 있는 모든종목들 넣어줘」) — 위 줄 판 때(시각 · 까닭 / 지금 / 끝까지) · 가운데 판 가격(x.sellPx · 산 값보다 오르면 빨강 · 내리면 파랑 — 재권님 「판값이 샀을때보다 상승이면 빨강 하락이면 파랑으로 해줘」 · 셈은 sign.js) · 아래 수익률
  const WHEN = 'display: block; line-height: 1.25; font-size: 11px; color: var(--kh-text-secondary);';
  const resTd = (x) => { const nt = nowTxt(x.r), top = x.s.k >= 0 ? `${hmTxt(x.s.at || times[x.s.k])} ${x.s.why}` : x.now ? `지금 ${esc(String(d.nowAt || '').slice(0, 5))}` : `${hmTxt(times[times.length - 1])} 끝까지`;
    return `<td class="dt-res"><small style="${WHEN}">${top}</small>${Number.isFinite(Number(x.sellPx)) && Number(x.sellPx) > 0 ? `<span class="${signClass(x.res, NUM) || ''}" style="display: block; line-height: 1.25;">${num(Number(x.sellPx))}</span>` : ''}${pct(x.res)}${x.s.k >= 0 && nt ? `<small>${nt}</small>` : ''}</td>`; };
  // 산 때를 산 가격 위에(같은 말씀 「매수를 시간으로 하거나 칩이 들어온때로」) — 위 줄 산 시각 · 아래 출처 글은 그대로
  const buyCell = (B, r) => `<td class="dt-buy">${/^\d{4}$/.test(String(B.at || '')) ? `<small style="${WHEN}">${hmS(String(B.at))} ${HYPO.has(r) ? '든 때(가정)' : '삼'}</small>` : ''}${num(B.px)}<small>${esc(B.src)}</small></td>`;
  const rk = (r, i) => `<td class="dt-rk">${i + 1}</td>`;
  // 매수가 (11-18 서버 바뀜) — 정규장 전에 든 종목은 buy null + buyWait → 「09:00 시가 기다림」 · 채워지면 buySrc(시가 · 지금 값) · 그 시각
  const NM0 = d.meta || {};
  // 대기 줄(아직 안 굳은 종목) — 「안 삼」 대신 굳으면 살 값(처음 든 때 가격)을 흐리게(qa 11-23 — 10:00 에 살 줄이 「안 삼」 으로 읽힘)
  const waitTd = (r) => { if (!(pmOf(buyKey()) === 1 && !(Number(r.lock) > 0) && (d.rows || []).some((x) => Number(x.lock) > 0) && Number(r.buy) > 0)) return ''; const e = inTs(r);
    return `<td class="dt-buy">${num(Number(r.buy))}<small>${lkNext && lkNext.live ? '장중' : '대기'}${e ? ` · ${e.slice(0, 2)}:${e.slice(2, 4)}:${e.slice(4, 6)} 든 때` : ''}</small></td>`; };   // 11-23 「보이는 종목들은 다 셈해」 — 대기 줄도 이 값에 산 것으로 셈
  const buyTd = (r) => (fbDays.has(d.day) ? (() => { const B = buyOf(r); return B ? buyCell(B, r) : '<td class="dt-buy"><span class="dt-nxm">대체 값도 없음 · 안 삼</span></td>'; })() : buyKey() !== 'open' || d.flat930 ? (() => { const B = buyOf(r); if (waitTd(r)) return waitTd(r); return B ? buyCell(B, r) : NOPX.has(r) ? `<td class="dt-buy"><span class="dt-nxm dt-nobuy" data-tip="칩이 찬 분의 1분봉 값이 서버에 아직 없어 산 값을 어림하지 않음 · 손익 셈 밖 · 서버에 들어오면 다시 받을 때 채움">매수값 미확인 · ${esc(NOPX.get(r))}</span></td>` : SVNO.has(r) ? '<td class="dt-buy"><span class="dt-nxm" data-tip="저장된 셈 칸으로 서버가 사지 않은 종목 — 화면이 따로 셈하지 않음">서버 산 값 없음 · 안 삼</span></td>' : `<td class="dt-buy"><span class="dt-nxm">${d.flat930 && nthChipAt(r) == null ? (comboMode() ? '고른 조합 안 됨 · 안 삼' : `칩 ${num(chipNeed(r))}개 안 참 · 안 삼`) : notYetIn(r, buyKey() === 'vi' ? (r.viPx || {}).at : ((minVal(r, pmOf(buyKey())) || {}).at || minHM(pmOf(buyKey())))) ? `안 삼 · ${esc(notYetIn(r, buyKey() === 'vi' ? (r.viPx || {}).at : ((minVal(r, pmOf(buyKey())) || {}).at || minHM(pmOf(buyKey())))))} 뒤 듦` : buyKey() === 'vi' ? (r.viAt ? 'VI 값 못 받음 · 안 삼' : 'VI 없음 · 안 삼') : minVal(r, pmOf(buyKey())) === undefined ? '서버 값 아직 · 안 삼' : `${hmS(minHM(pmOf(buyKey())))} 값 없음 · 안 삼`}</span></td>`; })()
    : r.buy == null && r.buyWait ? `<td class="dt-buy"><span class="dt-nxm">${st.openAt ? hmTxt(String(st.openAt).replace(':', '')) : '정규장'} 시가 기다림</span></td>`
    : `<td class="dt-buy">${num(r.buy)}${r.buySrc ? `<small>${r.buyAt ? `${hmTxt(String(r.buyAt).replace(':', ''))} ` : ''}${esc(r.buySrc)}</small>` : ''}</td>`);
  // 09:01 값 (11-18 재권님 「9시 1분 등락도 넣어줘 이쯤 살거니깐」 → 「응 그렇게 해」) — 서버 rows[].px1(개발2 · 첫 1분봉 종가 「1m」 · 없으면 그때 현재가 「now」) · 시각은 meta.px1At
  //   화면은 매수가 대비 % 만 셈 · px1 칸이 없으면 「아직」(서버가 아직 안 줌 · 그날 09:02 전) · px 가 null 이면 「—」 못 잼(0 아님)
  const p1At = NM0.px1At ? hmTxt(String(NM0.px1At).replace(':', '')) : '첫 1분';   // 시각은 서버 meta.px1At 한 곳 — 없으면 시각을 안 적음(개념정의 11-18)
  const lateIn = (r) => { const a = hhmm(r.buyAt); return newBuyOf(d) && (!!r.buyTs || (/^\d{4}$/.test(a) && a > minHM(1))); };   // 새 규칙 판만 — 옛 판(11-19 까지)은 buyAt 이 여는 시각이라 안 가름(개념정의 검수 덧 · 머리 글과 기준 하나)   // 9시 1분 뒤 판에 든 종목 — 등락률은 들어온 가격 대비(매수가 = 들어온 가격)라 9시 1분 칸은 셈 밖(11-20 재권님 「든가격에 정보있는건 그가격대비로 등락률 계산되게 해줘」)
  const p1Ch = (r) => (!lateIn(r) && r.px1 && r.px1.px != null && Number(r.buy) > 0 ? (Number(r.px1.px) / Number(r.buy) - 1) * 100 : null);
  const p1Td = (r) => { const o = r.px1;
    // 「아직」 은 서버가 09:01 을 세는 판(meta.px1At)이고 아직 안 굳은 날만 — 그 밖은 영영 안 오므로 「—」(개념정의 11-18 · 「못 한다」 와 「아직 안 했다」 를 가른다)
    if (o === undefined) return NM0.px1At && d.closed !== true ? '<td class="dt-nx"><span class="dt-nxm">아직</span></td>' : '<td class="dt-nx" data-tip="이 날은 서버가 시작 1분 뒤 값을 안 셈">—</td>';
    if (!o || o.px == null) return '<td class="dt-nx">—<small>못 잼</small></td>';
    if (lateIn(r)) return `<td class="dt-nx" data-tip="9시 1분 뒤 판에 든 종목 — 등락률은 들어온 가격 대비">—<small>${num(o.px)} · 들기 전</small></td>`;
    // 9시 1분에 판에 있던 종목 — 좌우 칸(매수가 · 들어온 가격)과 같은 꼴: 큰 굵은 가격 + 작은 둘째 줄(%) · 11-20 재권님 「9시 1분에 들어있는 종목들은 좌우에 맞게 글씨 크기랑 폰트 맞춰줘」
    // % 는 새 판만 뺌 — 매수가가 9시 1분 값이면 늘 0 이라(11-20 재권님 「응」 · 09:45 물음) · 옛 판(11-19 까지)은 매수가가 시가라 % 에 뜻이 있어 그대로(개념정의 검수 덧)
    if (newBuyOf(d)) return `<td class="dt-nx dt-buy">${num(o.px)}${o.src === 'now' ? '<small>그때 현재가</small>' : ''}</td>`;
    return `<td class="dt-nx dt-buy">${num(o.px)}<small>${pct(p1Ch(r))}${o.src === 'now' ? ' · 그때 현재가' : ''}</small></td>`; };
  // 들어온 가격 (11-20 재권님 「그칸 왼쪽에다가 들어온 가격 이라고 만들어서 넣어놔」 · 「9시 이후에 들어온거는 들어온 시간도 작성해주고 들어온 시간 가격을 써줘야해」)
  //   값은 서버 rows[].buyAt(든 시각) · buy(든 순간 가격) — buyAt 이 시작 1분 뒤(minHM(1))보다 늦은 줄만 「9시 1분 뒤 들어온」 종목 · 초는 서버가 주면 buyTs(개발2 · 11-20)
  //   그 밖(9시 1분 전부터 판에 있던 줄)은 「—」 — 매수가가 9시 1분 값이라 따로 적을 것이 없음
  const inTd = (r) => { const at = hhmm(r.buyAt);
    if (!(Number(r.buy) > 0) || !lateIn(r)) return '<td class="dt-in" data-tip="9시 1분 전부터 판에 있던 종목 — 매수가가 9시 1분 값">—</td>';
    return `<td class="dt-buy dt-in">${num(r.buy)}<small>${esc(String(r.buyTs || hmS(at)))}${r.buySrc ? ` · ${esc(r.buySrc)}` : ''}</small></td>`; };
  const p1V = R.map((x) => p1Ch(x.r)).filter((v) => v != null);
  const p1Avg = `<td class="dt-nx">${p1V.length && !newBuyOf(d) ? pct(mean(p1V)) : '—'}</td>`;   // 새 판은 「—」 — 매수가가 9시 1분 값이라 거의 늘 0(11-20 재권님 「응」 · 옛 판은 그대로)
  // 다음 날 프리장 08:05 (11-18 재권님 「이종목들 내일 프리장에 8시 5분에 얼마인지 체크해서 넣어줘 … 어제에 프리장 8시5분 이라고 칸이 있어야 되고 여기에 값 넣어줘」)
  //   값은 서버 rows[].nx(개발2 · 다음 거래일 넥스트레이드 그 시각 값) · 시각은 meta.nxAt · 화면은 매수가 대비 % 만 셈
  //   nx 칸이 없으면 「아직」(다음 날 그 시각 전) · px 가 null 이면 「—」(넥스트레이드 거래 없음 · 못 받음 — 0 아님)
  const NM = d.meta || {}, nxAt = NM.nxAt ? hmTxt(String(NM.nxAt).replace(':', '')) : null;
  const nxCh = (r) => (r.nx && r.nx.px != null && Number(r.buy) > 0 ? (Number(r.nx.px) / Number(r.buy) - 1) * 100 : null);
  const nxTd = (r) => { const n = r.nx;
    if (!n) return '<td class="dt-nx"><span class="dt-nxm">아직</span></td>';
    if (n.px == null) return '<td class="dt-nx">—<small>거래 없음</small></td>';
    return `<td class="dt-nx">${pct(nxCh(r))}<small>${num(n.px)}${n.src === '1m' ? ' · 1분봉' : ''}</small></td>`; };
  const nxV = R.map((x) => nxCh(x.r)).filter((v) => v != null);
  const nxAvg = `<td class="dt-nx">${nxV.length ? pct(nxV.reduce((a, v) => a + v, 0) / nxV.length) : '—'}</td>`;
  const nxH1 = `<th class="dt-nx" data-tip="${esc(NM.nxNote || '이 판 종목의 다음 거래일 넥스트레이드 프리장 값 · 매수가 대비')}">다음 날 프리장</th>`;
  const nxH2 = `<th class="dt-nx">${nxAt || '—'}${NM.nxDay ? ` <small>${esc(dayTxt(NM.nxDay))}</small>` : ''}</th>`;
  // 칩 수 구분 줄 (11-18 재권님 「칩 개수별로 종목 소팅되게」) — 기본 차례(겹친 칩 수 순)일 때만 · 칩 수가 바뀌는 자리에 「칩 N개 · 종목 수 · 그 묶음 세후 합(상위 안만) · 이긴 수」
  const addD = (d.rows || []).some((r) => r.live), addOf = (x) => (addD && !x.r.live ? '더함' : '');   // 장중 줄이 있는 판 — 더한 줄 묶음을 따로(11-24)
  const gk = (x) => !comboMode() && sentOrdOf(d, x.r) != null ? '보냄' : (d.flat930 ? addOf(x) + (FILL.has(x.r) ? '채움' : '') + ((nthChipAt(x.r) || '9999') <= chipUntil().replace(':', '') ? '앞' : '뒤') : rankOf(x.r));   // 점수표가 있으면 점수로 묶음 · 굳힘 없앤 판은 09:30 까지 찬 종목 / 뒤에 찬 종목
  // 상승률 순(시가 대비) — 다 셈한 뒤 보는 차례만 바꿈 · 묶음(09:30 까지 / 뒤 · 더한 줄)은 그대로 두고 그 안에서 큰 순 · 값 없는 줄은 묶음 끝(11-24)
  if (st.order === 'open') { const gi = new Map(); R.forEach((x) => { const g = gk(x); if (!gi.has(g)) gi.set(g, gi.size); }); R.sort((a, b) => gi.get(gk(a)) - gi.get(gk(b)) || (gk(a) === '보냄' ? sentOrdOf(d, a.r) - sentOrdOf(d, b.r) : orV(b.r) - orV(a.r))); }   // 보낸 종목은 보낸 차례 그대로
  const grp = (i, span) => { if (!R[i] || (st.order && st.order !== 'open') || (i > 0 && gk(R[i - 1]) === gk(R[i]))) return ''; const g = gk(R[i]), xs = R.filter((y) => gk(y) === g);
    const tp = xs.filter((y) => y.inv && y.pnl && y.pnl.net != null), net = tp.reduce((a, y) => a + y.pnl.net, 0);
    return `<tr class="dt-chiprow"><td colspan="${span}"><span class="st-cap"><b>${g === '보냄' ? '보낸 종목 — 서버가 매수 알림을 보낸 차례(맨 위 고정 · 상승률이 바뀌어도 안 움직임)' : ''}${g !== '보냄' && d.flat930 && String(g).includes('채움') ? `칩 ${st.set.minChip}개 종목이 모자라 칩 ${st.set.minChip - 1}개로 채운 종목(N−1번째 칩이 찬 때 삼) — ` : ''}${d.flat930 && String(g).startsWith('더함') ? '다시 지으며 더한 종목(장중 판에 없던 · 3천억 이상 · 칩 하나라도) — ' : ''}${g === '보냄' ? '' : d.flat930 ? (String(g).endsWith('앞') ? `${chipUntil()} 까지 ${comboMode() ? '고른 조합이 된' : `칩 ${String(g).includes('채움') ? chipNeed() - 1 : chipNeed()}개 찬`} 종목 — ${st.order === 'open' ? '상승률 순(시가 대비)' : comboMode() ? '조합 된 순' : st.set.riseRank !== false ? '상승률 높은 순(09:05 까지 1분 값)' : '먼저 찬 순'}` : `${chipUntil()} 뒤에 ${comboMode() ? '조합이 된' : '찬'} 종목 — ${st.order === 'open' ? '상승률 순(시가 대비)' : comboMode() ? '조합 된 순' : st.set.riseRank !== false ? '상승률 높은 순(09:05 까지 1분 값)' : '먼저 찬 순'}`) : hasScore() ? `점수 ${num(g, 1)}` : `칩 ${g}개`}</b> · ${xs.length}종목${xs.every((y) => y.hypo) ? (() => { const t = xs.filter((y) => y.pnl && y.pnl.net != null), v = t.reduce((a, y) => a + y.pnl.net, 0); return ` · 장중 창과 같은 룰 — 들어올 때 샀다고 친 가정 셈 · 세후 가정 합 ${t.length ? `<span class="${signClass(v, NUM) || ''}">${won(v)}</span> · 오른 것 ${t.filter((y) => y.pnl.net > 0).length}/${t.length}` : '—'} · 실제로 산 것 아님 — 위 합계 · 평균에 안 듦`; })() : tp.length ? ` · 세후 <span class="${signClass(net, NUM) || ''}">${won(net)}</span> · 이긴 것 ${tp.filter((y) => y.pnl.net > 0).length}/${tp.length}` : ` · 손익 셈 밖(${lkMode ? '안 굳음' : '상위 밖'})`}${(() => { const k = xs.filter((y) => y.inv && NOPX.has(y.r)).length; return k ? ` · <b class="dt-nobuy">매수값 미확인 ${k}종목</b>` : ''; })()}</span>${comboMode() && d.flat930 && g === '앞' ? `<span class="st-cap dt-cbrule">들어옴 — 고른 조합의 칩이 한 시각에 다 붙어 있는 종목(칩이 더 있어도 됨)<br>순위 — ① 조합이 된 분이 빠른 순 ② 같은 분이면 그 분 1분 값(산 값)의 시가 대비 상승률이 높은 순 · 그 분에 정해져 뒤로 안 바뀜 · 매수값 미확인 종목은 그 분 맨 뒤 · 값이 들어오면 그 값으로 다시 자리 ③ 그래도 같으면 초반상승 % → 시가총액 순 · 뒤에 칩이 더 붙어도 순위는 그대로<br>삼 — 위에서 상위 ${num(st.set.top)}종목을 조합이 된 때 값에(그 분 1분봉이 아직 없는 종목도 산 것으로 셈 · 「매수값 미확인」 · 값은 들어오는 대로) · ${chipUntil()} 뒤에 조합이 된 종목은 아래 칸 · 고른 조합이 안 된 종목은 맨 아래 보기만</span>` : ''}</td></tr>`; };
  // 굳힘 묶음 셈 — 넓은 · 좁은 표 함께(서버 rows[].lock · lockRank · meta.lockAt · lockN)
  const DMk = d.meta || {}, lkAt = Array.isArray(DMk.lockAt) ? DMk.lockAt : [], lkN = Number(DMk.lockN) || null;
  const lkIdx = R.map((x, i) => i).filter((i) => Number(R[i].r.lock) > 0), lkHas = lkIdx.length > 0;
  const lkGroups = lkAt.map((at, j) => ({ n: j + 1, at, idx: lkIdx.filter((i) => Number(R[i].r.lock) === j + 1).sort((p, q) => (Number(R[p].r.lockRank) || 0) - (Number(R[q].r.lockRank) || 0)) }));
  // 아직 안 굳은 종목(진행 중)은 다음 굳힘 단추 묶음 안에 「대기」 로(11-23 재권님 「9시5분에 굳히는곳인데 그 이후에 든 종목은 9시 30분 굳힘 으로 이동되어야지」 → 「응 그래」)
  //   굳은 묶음을 볼 때는 안 보임 · 다음 굳힘이 없으면(마지막 굳힘 뒤) 지금처럼 평균 아래 「진행 중」
  const lkRest0 = R.map((x, i) => i).filter((i) => !(Number(R[i].r.lock) > 0));
  // 「장중」 묶음 — 서버(개발2 be5004d)가 마지막 굳힘 뒤 칩에 걸린 종목을 lock 넷째(meta.intra.lock)로 더함 · 든 때 가격에 산 것 · 셈 칸 넷째 줄(금액 · 종목 수 · 칩) · 안 굳은 종목은 이 묶음이 아님
  const lkIn = DMk.intra && typeof DMk.intra === 'object' ? DMk.intra : null, lkInN = lkIn ? Number(lkIn.lock) || lkAt.length + 1 : 0;
  if (lkIn && !winMode()) lkGroups.push({ n: lkInN, at: lkIn.name || '장중', idx: lkIdx.filter((i) => Number(R[i].r.lock) === lkInN).sort((p, q) => (Number(R[p].r.lockRank) || 0) - (Number(R[q].r.lockRank) || 0)), intra: true });
  // 마지막 굳힘 뒤 든 종목은 굳힘 단추 줄 맨 끝 「장중」 묶음(11-23 재권님 「10시 30분 이후에 걸리는 종목은 10시 30분 옆에 장중 이라고 칸 만들어서 거기에 걸리게 해줘」) — 굳힐 칸이 더 없을 때
  if (!winMode() && !lkIn && lkHas && lkRest0.length && !lkGroups.some((g) => !g.idx.length)) lkGroups.push({ n: lkGroups.length + 1, at: '장중', idx: [], live: true });
  const lkNext = lkHas && lkRest0.length && !winMode() ? lkGroups.find((g) => !g.idx.length && !g.intra) : null;   // 창(시간 창 거르기)은 다음 묶음으로 넘기는 대기가 없음 — 문턱 밑 줄은 진행 중
  if (lkHas && !lkGroups.some((g) => g.n === st.lockSel && (g.idx.length || g === lkNext))) st.lockSel = Math.max(...lkIdx.map((i) => Number(R[i].r.lock)));
  const lkAct = lkGroups.find((g) => g.n === st.lockSel);
  const lkBtn = (g) => `<button type="button" class="kh-chip${g.n === st.lockSel ? ' is-active' : ''}" data-lock="${g.n}"${g.idx.length || g === lkNext ? '' : ' disabled'}>${esc(String(g.at))} · ${g.idx.length ? num(g.idx.length) : g === lkNext ? (g.live ? num(lkRest0.length) : `대기 ${num(lkRest0.length)}`) : '아직'}${lkMoney(g.n)}</button>`;
  const lkWaitCap = (span) => `<tr class="dt-chiprow"><td colspan="${span}"><span class="st-cap">${lkNext && lkNext.live ? `<b>장중</b> · ${num(lkRest0.length)}종목 — 마지막 굳힘 뒤 든 종목 · 든 때 값으로 셈` : `<b>대기</b> · ${num(lkRest0.length)}종목 — 아직 안 굳음 · ${lkNext ? esc(String(lkNext.at)) : ''} 굳힘 때 차례 위 종목이 이 묶음이 됨`}</span></td></tr>`;
  // 고른 차례가 굳을 때 빠져 있던 칩(11-20 재권님 「응 해줘」) — 서버 meta.lockMiss{차례: {missing · approx · wait}}(개발2 7d27f4a) · 키가 없는 판(서버 고침 전 · 아직 안 굳은 차례)은 안 적음
  const lkMiss = (() => { const M = DMk.lockMiss && DMk.lockMiss[String(st.lockSel)]; if (!M) return '';
    const nm = (a) => (Array.isArray(a) ? a : []).map(chipName).join(' · '), p = [];
    if (nm(M.missing)) p.push(`못 받음 ${nm(M.missing)}`); if (nm(M.approx)) p.push(`어림 값으로 셈 ${nm(M.approx)}`); if (nm(M.wait)) p.push(`아직 시각 전 ${nm(M.wait)}`);
    return ` · 그때 빠진 칩 — ${p.length ? esc(p.join(' · ')) : '없음'}`; })();
  const lkRest = R.map((x, i) => i).filter((i) => !(Number(R[i].r.lock) > 0));
  // 평균 줄 · 손익은 지금 보이는 종목만(11-23 재권님 「단타판에 보이는 종목들은 다 셈해」) — 굳힌 판이면 고른 굳힘 묶음(대기 단추면 대기 줄) · 굳힘 없는 판은 지금처럼 전부
  //   손익 합계(머리 글 · 달 합계)는 굳은 줄 전부 그대로(calc 의 P)
  const shownI = !lkHas ? null : lkAct && lkAct === lkNext ? lkRest0 : lkAct ? lkAct.idx : lkRest0;
  const SR0 = shownI ? shownI.map((i) => R[i]) : R;
  const avgS = shownI ? times.map((_, k) => mean(SR0.map((x) => atK(x, k)).filter((v) => v != null))) : avg;
  const resAvgS = shownI ? mean(SR0.map((x) => x.res).filter((v) => v != null)) : resAvg;
  const PS = !shownI ? P : (() => { const t = SR0.filter((x) => x.pnl); if (!t.length) return null; const sm = (k) => t.reduce((a, x) => a + (x.pnl[k] || 0), 0); return { net: sm('net'), gross: sm('gross') }; })();
  const lkMoney = (j) => { const g = G[j]; if (noBuyOf(j)) return ' · 안 삼'; if (!lkCnt[j]) return ''; const gw = Number((st.set.grpWons || [])[j - 1]); return ` · 넣은 ${manTxt(gw > 0 ? gw : lkWon)}${g ? ` · 세후 <span class="${signClass(g.net, NUM) || ''}">${won(g.net)}</span>${g.noMkt ? ` · 시장 모름 ${g.noMkt}` : ''}` : ' · 손익 셀 값 없음'}`; };   // 굳힘 묶음마다 넣은 돈 · 세후 손익(11-20)
  if (!WIDE.matches) {
    // 좁은 폭(모바일 퍼스트 · 재권님 「모바일 퍼스트 적용시킨 화면도」) — 종목 칸 안에 시가총액 · 섹터 · 이벤트를 접어 넣고, 결과 · 손익을 종목 바로 옆에 · 시각 칸은 그 뒤로 밀어 봄
    // 굳힘 목록 — 넓은 표와 같은 셈(좁은 폭 · qa · 개념정의 검수 덧)
    const rowN = (x, i) => { const r = x.r; return `${grp(i, times.length + 9)}<tr>${rk(r, i)}<td class="st-name" data-co="${esc(r.code || '')}">${nameB(r)}<small class="dt-sub">${capTxt(r.cap)} · 풀린 ${capTxt(r.floatCap)} · 거래 ${turnTxt(r.turn, r.turnPrevPct)}${r.turnApprox ? '<span class=\"dt-approx\" data-tip=\"지난 판 — 그날 유통주식 수 기록이 없어 지금 풀린 주식 수 × 그날 종가로 어림\"> · 어림</span>' : ''} · ${accTxt(r)} · ${esc(r.sector || '섹터 —')}</small><span class="dt-evs">${evHtml(r.chips, r)}</span></td>${resTd(x)}${plTd(x, i)}${buyTd(r)}${p1Td(r)}${inTd(r)}${times.map((t, k) => cell(x, k)).join('')}${nxTd(r)}<td class="dt-tx">${taxTxt(x.r)}</td></tr>`; };
    const strip = (h) => h.replace(/^<tr class="dt-chiprow">[\s\S]*?<\/tr>/, '');
    const lkN2 = !lkHas ? '' : `<tr class="dt-chiprow dt-lock"><td colspan="${times.length + 9}"><span class="st-cap"><b>${LKW()}</b> ${lkGroups.map(lkBtn).join(' ')}${lkMiss}</span></td></tr>${lkAct && lkAct === lkNext ? lkWaitCap(times.length + 9) + lkRest0.map((i) => strip(rowN(R[i], i))).join('') : lkAct ? lkAct.idx.map((i) => strip(rowN(R[i], i))).join('') : ''}`;
    const lkLive2 = !lkHas || lkNext || !lkRest0.length ? '' : `<tr class="dt-chiprow"><td colspan="${times.length + 9}"><span class="st-cap"><b>진행 중</b> · ${num(lkRest.length)}종목 — 아직 안 굳음</span></td></tr>`;
    const lkBody2 = !lkHas ? R.map(rowN).join('') : lkNext ? '' : lkRest.map((i) => strip(rowN(R[i], i))).join('');
    $('dt-box').innerHTML = `<table class="dt-tb dt-narrow">
    <tr><th class="dt-rk"></th><th class="st-name">종목${fltIn()}</th><th class="dt-res">결과</th><th class="dt-pl">손익</th><th>매수가</th><th class="dt-nx">${p1At}<small>9시1분</small></th><th class="dt-in">들어온 가격</th>${times.map((t) => `<th>${hmTxt(t)}</th>`).join('')}<th class="dt-nx">다음 날 프리장 ${nxAt || ''}</th><th class="dt-tx">세금 %</th></tr>
    ${chipRow(times.length + 9)}
    ${lkN2}<tr class="dt-avg"><td class="dt-rk"></td><td class="st-name">평균</td><td class="dt-res">${pct(resAvgS)}</td><td class="dt-pl">${PS ? won(PS.net) : '—'}</td><td></td>${p1Avg}<td class="dt-in"></td>${avgS.map((x) => `<td>${pct(x)}</td>`).join('')}${nxAvg}<td class="dt-tx"></td></tr>
    ${lkLive2}${lkBody2}${RB.length ? `<tr class="dt-chiprow"><td colspan="${times.length + 9}"><span class="st-cap"><b>${comboPending() ? '조합 셈하는 중 — 끝나면 조합대로 삼' : comboMode() ? '고른 조합 안 됨' : `칩 ${num(st.set.minChip)}개 미만`} — 보기만</b> · ${RB.length}종목 · 칩 수 많은 순 · 사지 않음</span></td></tr>` + RB.map((x, k) => strip(rowN(x, R.length + k))).join('') : ''}
  </table>`;
    return;
  }
  // 넓은 폭 — 칩마다 세로 칸(위 「칩 칸」) · 칩 줄 자리에는 어제 미국장만 남김
  const CS = colsOf(), nCol = CS.length;
  // 매수가 규칙(11-20 재권님 「판에 들어있으면 9시 1분가격으로 적고 판에 들어오면 들어올때 가격으로」 · 서버 개발2) — 그 규칙으로 지은 판(줄에 buyTs · buySrc 「9시 1분 값」)만 머리 글을 바꿈 · 옛 판은 「시가」 그대로
  const newBuy = newBuyOf(d);
  // 한 종목 두 줄(11-20 재권님 「한진칼에 대한 칩들이 다 있고 그아래줄을 추가해서 매수에 대한 오른쪽 줄이 다 있는걸」 → 그림 다듬기 넷 → 「응 맞아」)
  //   윗줄 = 시가총액 · 섹터 · 오늘 프리장 · 칩 칸(칸마다 같은 폭으로 왼쪽부터 · 그리고 나서 폭을 맞춤 fitTop) / 아랫줄 = 매수가 ~ 손익 · 순번 · 종목 칸은 두 줄을 걸침
  //   칩 이름은 알약 · 들어온 시각은 이름 아래(「옆으로 시간쓰지말고 아래로」) · 초반상승은 프리장 뒤(「프리장과 vi급등 사이로」) · 겹침은 종목 이름 옆 배지(「5개 빨강 4개 보라 3개 노랑」)
  //   좁은 창에선 순번 ~ 들어온 가격 · 결과 ~ 손익은 붙고 시각 칸만 옆으로 밀림(「해상도가 낮아지면 든시각 옆에서 2시까지가 가로로 스크롤」 · fitSticky)
  const DS = (() => { const a = CS.filter((c) => c !== '초반상승'), p = a.indexOf('프리장'); if (a.length < CS.length) a.splice(p >= 0 ? p + 1 : a.length, 0, '초반상승'); return a; })();   // 보이는 차례만 바꿈 — 칸 목록(colsOf) 차례는 그대로
  // 묶음 칩(업종 · 테마에 붙는 칩) — 칩 칸 줄에서 빼고 머리는 「종목」 칸에, 줄마다 종목 이름 옆에(11-25 재권님 「이거 왼쪽 종목위에 있어야대고 종목 이름 옆으로 칩이 붙으면 좋을거같은데」 · 「요기 종목 옆에 있고 칩은 그아래 종목이름 옆으로」)
  const GRP = GRP_CHIPS, DSC = DS.filter((c) => !GRP.includes(c)), DSG = DS.filter((c) => GRP.includes(c));
  const grpHead = () => (DSG.length ? `<div class="dt-grph">${DSG.map((c) => box(chHead(c, true))).join('')}</div>` : '');
  const grpBadge = (r) => { const h = DSG.map((c) => [c, chCell(r, c).replace(/^<td[^>]*>/, '').replace(/<\/td>$/, '')]).filter(([, v]) => v).map(([c, v]) => `<span class="dt-grpb${st.off.has(c) ? ' is-off' : ''}"><span class="dt-cg" data-i="${colorOf(c)}"${(subsOf(r, c) || []).length ? ` data-tip="${esc(`걸린 묶음 — ${subsOf(r, c).join(' · ')}`)}"` : ''}><i class="dt-chs">${esc(c)}</i></span>${v}</span>`).join(''); return h ? `<span class="dt-grpw">${h}</span>` : ''; };
  const NB = times.length + 7;   // 아랫줄 칸 수 — 매수가 · 9시1분 · 들어온 가격 · 시각들 · 결과 · 다음 날 프리장 · 세금 · 손익
  const addC = (h, k) => h.replace(/^<(td|th)(?: class="([^"]*)")?/, (m, t, c) => `<${t} class="${k}${c ? ` ${c}` : ''}"`);   // 칸 글 맨 앞 태그에 클래스 더하기
  const box = (h) => addC(h, 'dt-bx').replace(/^<t[dh]/, '<div').replace(/<\/t[dh]>$/, '</div>');   // 칸(td · th) 글을 윗줄 상자(div)로
  const SL = (h) => addC(h, 'dt-sl'), SR = (h) => addC(h, 'dt-sr');   // 옆으로 밀 때 왼쪽 · 오른쪽에 붙는 칸
  const chHead = (c, noSubs) => { const on = !st.off.has(c), ms = st.miss.has(c), n = all.filter((r) => (r.chips || []).includes(c)).length;
    const subs = noSubs ? [] : subOrder(c, [...new Set(all.flatMap((r) => subsOf(r, c)))]);   // noSubs — 묶음 칩(돈몰림 · 미국강세) 머리는 업종 · 테마 목록 없이 단추만(11-26 재권님 「돈몰림 미국장 여기아래로 목록 나올필요는 없어 종목옆에만 있으면되」)
    const tip = ms ? ` data-tip="${esc(`그날 판에 ${c} 값을 ${missWord()} — 걸린 종목이 있어도 0 으로 셈됨`)}"` : tipAt(c);
    return `<th class="dt-chc${on ? '' : ' is-off'}"><span class="dt-cg${on ? '' : ' is-off'}${ms ? ' is-miss' : ''}" data-i="${colorOf(c)}"><button type="button" class="dt-mc${on ? ' is-on' : ''}" data-col="${esc(c)}"${tip} aria-haspopup="menu">${esc(c)}${ms ? '' : `<b>${n}</b>`}</button>${
      subs.length ? `<span class="dt-subs">${subs.map((x) => { const k = `${c}|${x}`, son = on && !st.subOff.has(k); return `<button type="button" class="dt-sub-chip${son ? ' is-on' : ''}" data-sub="${esc(k)}"${tipAt(k)} aria-pressed="${son}"${on ? '' : ' disabled'}>${esc(subName(c, x))}<b>${all.filter((r) => subsOf(r, c).includes(x)).length}</b></button>`; }).join('')}</span>` : ''}</span><small>${on ? (ms ? missWord() : st.wait.has(c) ? `${st.openAt ? hmTxt(String(st.openAt).replace(':', '')) : '정규장'} 뒤` : '켜짐') : '꺼짐'}</small></th>`; };
  const chCell = (r, c) => { const on = !st.off.has(c), has = (r.chips || []).includes(c), sb = has ? subsOf(r, c) : [];
    const vt = has && c === 'VI·급등' ? viTxt(r) : '';
    const ct = has ? String((r.chipTime || {})[c] || (r.chipAt || {})[c] || '').slice(0, 5) : '';   // 칩이 처음 붙은 시각(19:3x 재권님 「각 칩별로 들어온 시간대를 다 알고 있어야함」) — 서버 chipTime · 없으면 chipAt · 모르면 안 적음
    // 하위 칩을 붙은 차례대로 각각 · 그 아래 처음 붙은 시각(11-20 재권님 「외국인 기관으로 바뀌면 둘다 있어야해 수급칩은 각각 다 보이게 해주고 추가된 칩은 추가된 시간도」) — 서버 rows[].subAt{칩:{하위:HH:MM:SS}}(개발2) 이 있을 때만 · 없으면 옛 모양
    const at = has && r.subAt && r.subAt[c], raw = at ? subsRaw(r, c) : [];
    const g = (nm, t) => `<span class="dt-chg"><i class="dt-chs">${nm}</i>${t ? `<small>${t}</small>` : ''}</span>`;   // 칩 이름 알약 + 그 아래 시각 한 묶음
    const each = raw.length ? raw.map((x) => g(esc(subName(c, x)), at[x] ? esc(String(at[x])) : '')).join('') : '';
    const v = has ? `<span class="dt-cg" data-i="${colorOf(c)}">${each ? `${each}${vt ? `<small class="dt-vt">${esc(vt)}</small>` : ''}` : sb.length ? g(esc(subTxt(c, sb)), vt ? esc(vt) : '') : `<b class="dt-dot" aria-label="걸림"></b>${vt ? `<small class="dt-vt">${esc(vt)}</small>` : ct ? `<small class="dt-vt">${esc(ct)}</small>` : ''}`}</span>`
      : (r.chipTime || {})[c] && everChip(r, c) ? `<span class="dt-cg dt-gone" data-i="${colorOf(c)}" data-tip="${spanRow(r) ? '지금은 빠진 칩 — 적힌 시각은 마지막 구간의 붙은 때 · 빠진 때(「빠짐 모름」 = 서버 기록에 빠진 때가 아직 없어 붙은 것으로 셈) · 겹침 셈은 같은 시각에 함께 붙어 있던 칩만' : '붙었다 빠진 칩 — 적힌 시각은 처음 붙은 때(빠진 때 아님) · 겹침 셈(칩 N개 거르기 · 산 때)에 듦 · 이 날은 빠진 시각 기록이 없음'}"><b class="dt-dot" aria-label="붙었다 빠짐"></b><small class="dt-vt">${(() => { const sp = spanRow(r) && Array.isArray(r.chipSpans[c]) ? r.chipSpans[c] : null, l = sp && sp[sp.length - 1]; return l ? (l[1] ? `${esc(String(l[0]).slice(0, 5))} 붙음 · ${esc(String(l[1]).slice(0, 5))} 빠짐` : `${esc(String(l[0]).slice(0, 5))} 붙음 · 빠짐 모름`) : `${esc(String(r.chipTime[c]).slice(0, 5))} 붙음 · 빠짐`; })()}</small></span>`   // 11-25 재권님 「나로 해」 — 거르기가 세는 칩이 칸에 안 보여 「안 걸린 것을 산 것처럼」 보였음
      : st.miss.has(c) ? `<span class="dt-chq" data-tip="${esc(`그날 판에 ${c} 값을 ${missWord()} — 이 종목이 걸렸는지 모름`)}">—</span>`
      : st.wait.has(c) ? `<span class="dt-chq" data-tip="${esc(`아직 때가 아님 — ${c} 은 정규장${st.openAt ? `(${st.openAt})` : ''} 뒤에 셈`)}">·</span>` : '';
    return `<td class="dt-chc${on ? '' : ' is-off'}">${v}</td>`; };
  // 겹침 배지 — 수마다 색(5 이상 빨강 · 4 보라 · 3 노랑 · 그 밖 회색) · 점수표가 있으면 점수 · 못 받은 칩 수는 그 아래
  // 겹침 수는 거르기(칩 N개 이상) · 산 때와 같은 셈(nEver — 붙었다 빠진 칩도) · 지금 붙어 있는 수가 다르면 「지금 M」 을 함께(11-25 재권님 「나로 해」 — 「겹침 3」 인데 칩 4개 거르기로 산 것처럼 보였음)
  const ovB = (r) => { const n = nEver(r), nl = nLive(r), k = CS.filter((c) => !st.off.has(c) && st.miss.has(c) && !(r.chips || []).includes(c)).length;
    // 겹친 칩 이름(11-26 재권님 「겹침 숫자로 하지말고 어떤칩이 겹쳤는지 종목믿으로 써주먼 좋을거같아」) — 가장 많이 함께 붙어 있던 때의 칩(구간 없는 판은 한 번 붙은 칩 전부) · 지금 빠진 칩은 흐리게
    //   돈몰림 · 미국강세는 이름 옆 알약(grpBadge)에 따로 있어 여기서는 뺌 · 수는 안 씀(셈 · 줄 세우기는 그대로 nEver) · 색은 위 칩 칸 색 그대로(colorOf · 재권님 「칩색은 왜 맘대로 바꾸지? 위에 있는거 가져오면 되잖아」)
    const hh = comboHit(r); if (hh) { const ks = new Set([...hh.key.split(' + '), ...comboAdds(r, hh).map(([c]) => c)]), ex = colsOf().filter((c) => everChip(r, c) && !ks.has(c) && !GRP_CHIPS.includes(c)).map((c) => [c, chipFirst(r, c)]).sort((a, b) => (a[1] || '9999').localeCompare(b[1] || '9999'));
      return `${ex.length ? `<span class="dt-ovl dt-ovx" data-tip="조합 밖 칩 — 붙은 시각 차례">${ex.map(([c, t]) => cbPill(c, t || null)).join('')}</span>` : ''}${hasScore() ? `<small class="dt-ovm">점수 ${num(scoreOf(r), 1)}</small>` : ''}`; }   // 조합 칩은 이름 밑 「조합」 줄에(11-26)
    const cs = ovSet(r).filter((c) => !GRP_CHIPS.includes(c)), lv = (c) => (r.chips || []).includes(c);
    return `<span class="dt-ovl" data-n="${n >= 5 ? 5 : n >= 3 ? n : 0}" data-tip="함께 붙어 있던 칩(켜진 칩 · 붙었다 빠진 칩도 셈 — 칩 N개 거르기 · 산 때와 같은 셈 · 흐린 칩은 지금 빠짐) — 순위가 이 칩 수로 정해짐">${cs.length ? cs.map((c) => `<span class="dt-cg dt-ovc${lv(c) ? '' : ' is-gone'}" data-i="${colorOf(c)}">${esc(c)}</span>`).join('') : '—'}</span>${hasScore() ? `<small class="dt-ovm">점수 ${num(scoreOf(r), 1)}</small>` : ''}${k ? `<small class="dt-ovm">못 받은 칩 ${k}</small>` : ''}`; };
  // 어제 미국장 — 머리 둘째 줄 한 줄 통째(11-19 재권님 「단타에 어제미국장 목록을 시간나오는곳 라인으로 맞춰서」 — 두 줄 모양에선 칩 머리 아래 · 매수 머리 위)
  const usTh = `<th class="dt-ust" colspan="${NB + 2}" style="text-align: left; white-space: normal; font-weight: 400;"><span class="dt-us" id="dt-us" data-day="${esc(d.day || '')}">${usHtml(d.day)}</span></th>`;   // 줄바꿈 · 왼쪽 맞춤은 이 칸만(머리 칸 기본은 한 줄 · 오른쪽)
  // 굳힘 목록(11-20 재권님 「평균 바로 위에 굳힘목록 만들어줘 굳힘시간() 넣어서」 → 「굳힌 종목은 시간대별로 버튼 누르면 볼수있게 해줘」 → 그림에 「응 올려」)
  //   서버(개발2) rows[].lock(몇 번째 굳힘) · lockAt · lockRank · meta.lockAt · lockN — 굳힌 줄은 평균 위에 누른 시각 묶음만 · 안 굳은 줄은 평균 아래 「진행 중」 · 굳힘 없으면(09:05 전 · 옛 판) 지금 모양
  const rowOf = (x, i, view) => { const r = x.r, z = i % 2 ? ' dt-z' : '', vw = view === true;   // view — 보기만 줄(묶음 줄 · 순번 없음) · R.map(rowOf) 이 셋째 인자로 배열을 넘기므로 참 그대로만 봄
    return `${vw ? '' : grp(i, NB + 2)}<tr class="dt-up${z}"><td class="dt-rk dt-sl" rowspan="2">${vw ? '—' : i + 1}</td><td class="st-name dt-sl" rowspan="2" data-co="${esc(r.code || '')}">${nameB(r)}${ovB(r)}${grpBadge(r)}<small class="dt-code">${esc(r.code || '')} · <span data-term="풀린 시총">풀린</span> ${capTxt(r.floatCap)} · <span data-term="거래 비율">거래</span> ${turnTxt(r.turn, r.turnPrevPct)}${r.turnApprox ? '<span class=\"dt-approx\" data-tip=\"지난 판 — 그날 유통주식 수 기록이 없어 지금 풀린 주식 수 × 그날 종가로 어림\"> · 어림</span>' : ''}</small><small class="dt-code dt-acc">${accTxt(r)}</small></td><td class="dt-tw" colspan="${NB}"><div class="dt-fx"><div class="dt-bx">${capTxt(r.cap)}</div><div class="dt-bx dt-sec">${esc(r.sector || '—')}</div>${box(orTd(r))}${box(preTd(r))}${DSC.map((c) => box(chCell(r, c))).join('')}<div class="dt-bx dt-addc"></div></div></td></tr>`
      + `<tr class="dt-dn${z}">${SL(buyTd(r))}${SL(p1Td(r))}${SL(inTd(r))}${times.map((t, k) => cell(x, k)).join('')}${SR(resTd(x))}${SR(nxTd(r))}<td class="dt-tx dt-sr">${taxTxt(x.r)}</td>${SR(plTd(x, i))}</tr>`; };
  const lkSpan = NB + 2;
  const lkTop = !lkHas ? '' : `<tr class="dt-chiprow dt-lock"><td colspan="${lkSpan}"><span class="st-cap"><b>${LKW()}</b> ${lkGroups.map(lkBtn).join(' ')} — ${winMode() ? '칩이 문턱(서버 값)에 든 시각의 창에 든 종목 · 산 값은 그 분 1분봉' : `누른 시각에 굳힌 종목${lkN ? `(그때까지 든 종목 중 차례 위 ${num(lkN)}개)` : ''} · 이 뒤로 안 바뀜`}${lkMiss}</span></td></tr>${lkAct && lkAct === lkNext ? lkWaitCap(lkSpan) + lkRest0.map((i) => rowOf(R[i], i).replace(/^<tr class="dt-chiprow">[\s\S]*?<\/tr>/, '')).join('') : lkAct ? lkAct.idx.map((i) => rowOf(R[i], i).replace(/^<tr class="dt-chiprow">[\s\S]*?<\/tr>/, '')).join('') : ''}`;
  const lkLive = !lkHas || lkNext || !lkRest0.length ? '' : `<tr class="dt-chiprow"><td colspan="${lkSpan}"><span class="st-cap"><b>진행 중</b> · ${num(lkRest.length)}종목 — ${winMode() ? '아직 칩 문턱 밑 · 문턱에 들면 그때 창으로' : '아직 안 굳음 · 다음 굳힘 때 그 시각 단추로 옮겨 감'}</span></td></tr>`;
  const lkBody = !lkHas ? R.map(rowOf).join('') : lkNext ? '' : lkRest.map((i) => rowOf(R[i], i).replace(/^<tr class="dt-chiprow">[\s\S]*?<\/tr>/, '')).join('');
  const preH = `<div class="dt-bx dt-pre" data-tip="전날 종가 대비 넥스트레이드 프리장 등락 — 홀딩스 시세와 같은 값">오늘 프리장${st.pre && st.pre.day === d.day && !(d.rows || []).some((r) => r.pre) ? `<small style="display: block; font-weight: 400;">${esc(st.pre.at)} 값</small>` : ''}</div>`;
  const buyH = `매수가 ${d.flat930 ? `<small>${comboMode() ? '조합 된 때' : `칩 ${num(chipNeed())}개 찬 때`} 그 분 값</small>` : buyKey() !== 'open' ? buyName(...(BUYS.find(([k]) => k === buyKey()) || BUYS[0])) : newBuy ? '<small>9시 1분 값 · 뒤에 든 종목은 든 때 값</small>' : st.openAt ? `${hmTxt(String(st.openAt).replace(':', ''))} 시가` : hmTxt(d.buyAt)}`;
  const viewH = !RV.length ? '' : `<tr class="dt-chiprow"><td colspan="${NB + 2}"><span class="st-cap"><b>${esc(IX.name || '장중')} 창${IX.from ? `(${esc(IX.from)}${IX.until ? `~${esc(IX.until)}` : ' ~'})` : ''}에 든 종목 — 보기만</b> · ${RV.length}종목 · 칩이 셈 칸(${num(chipNeed())}개)에 모자라 셈 밖 · 들어올 때 샀다고 친 가정 셈 · 세후 가정 합 ${(() => { const t = RV.filter((x) => x.pnl && x.pnl.net != null), v = t.reduce((a, x) => a + x.pnl.net, 0); return t.length ? `<span class="${signClass(v, NUM) || ''}">${won(v)}</span> · 오른 것 ${t.filter((x) => x.pnl.net > 0).length}/${t.length}` : '—'; })()} · 실제로 산 것 아님 — 위 합계 · 평균에 안 듦 · 든 시각 순</span></td></tr>`
    + RV.map((x, k) => rowOf(x, R.length + k, true)).join('');
  const belowCap = (span) => !RB.length ? '' : `<tr class="dt-chiprow"><td colspan="${span}"><span class="st-cap"><b>${comboPending() ? '조합 셈하는 중 — 끝나면 조합대로 삼' : comboMode() ? '고른 조합 안 됨' : `칩 ${num(st.set.minChip)}개 미만`} — 보기만</b> · ${RB.length}종목 · 칩 수 많은 순 · 사지 않음 — 위 합계 · 평균에 안 듦</span></td></tr>`;
  const belowH = belowCap(NB + 2) + RB.map((x, k) => rowOf(x, R.length + RV.length + k, true)).join('');
  $('dt-box').innerHTML = `<table class="dt-tb dt-cols dt-2row">
    <tr class="dt-h"><th class="dt-rk dt-sl"></th><th class="st-name dt-sl">종목${fltIn()}${grpHead()}</th><th class="dt-tw" colspan="${NB}"><div class="dt-fx"><div class="dt-bx">시가총액</div><div class="dt-bx dt-sec">섹터</div><div class="dt-bx dt-or" data-tip="${esc(orTip(d))}"><label class="dt-rrk${comboMode() ? ' is-off' : ''}"${comboMode() ? ' data-tip="칩 조합으로 살 때는 안 씀 — 같은 분은 늘 그 분 1분 값 상승률 높은 순"' : ''}><input type="checkbox" data-riserank${st.set.riseRank !== false ? ' checked' : ''}${comboMode() ? ' disabled' : ''} aria-label="상승률 순위 — 켜면 높은 순으로 순번 · 사는 종목 · 칩 조합으로 살 때는 안 씀">상승률 순위</label></div>${preH}${DSC.map((c) => box(chHead(c))).join('')}<div class="dt-bx dt-addc"><button type="button" class="kh-chip" data-addcol aria-haspopup="menu">+ 칩</button></div></div></th></tr>
    <tr class="dt-h">${usTh}</tr>
    <tr class="dt-h"><th class="dt-rk dt-sl"></th><th class="st-name dt-sl"></th><th class="dt-sl">${buyH}</th><th class="dt-nx dt-sl" data-tip="이쯤 산다면 — 09:01 값의 09:00 시가 대비 % (매수 타이밍을 바꿔도 이 칸은 시가 대비)">${p1At}</th><th class="dt-in dt-sl" data-tip="9시 1분 뒤 판에 든 종목 — 든 순간 가격 · 그 아래 든 시각">들어온 가격</th><th class="dt-gp" colspan="${times.length}"><span>매수가 대비</span></th><th class="dt-res dt-sr">결과</th>${SR(nxH1)}<th class="dt-tx dt-sr">세금 %</th><th class="dt-pl dt-sr">${lkMode ? `손익 · ${LKW()}마다 ${manTxt(lkWon)} ÷ 묶음 종목` : `손익 · 종목마다 ${manTxt(per)}`}</th></tr>
    <tr class="dt-h dt-t2"><th class="dt-rk dt-sl"></th><th class="st-name dt-sl"></th><th class="dt-sl"></th><th class="dt-nx dt-sl">9시1분</th><th class="dt-in dt-sl">든 시각</th>${times.map((t) => `<th>${hmTxt(t)}</th>`).join('')}<th class="dt-res dt-sr">판 값 · 시각</th>${SR(nxH2)}<th class="dt-tx dt-sr">거래세 · 농특세</th><th class="dt-pl dt-sr">세금 · 수수료 뺌 · ${lkMode ? (winMode() ? '창에 든 종목' : '굳힌 종목') : `상위 ${topN}`}</th></tr>
    ${lkTop}<tr class="dt-avg"><td class="dt-rk dt-sl"></td><td class="st-name dt-sl">평균 <small>판 종목은 판 값으로</small></td><td class="dt-sl"></td>${SL(p1Avg)}<td class="dt-in dt-sl"></td>${avgS.map((x, i) => `<td class="${i === L ? 'dt-last' : ''}">${pct(x)}</td>`).join('')}<td class="dt-res dt-sr">${pct(resAvgS)}</td>${SR(nxAvg)}<td class="dt-tx dt-sr"></td><td class="dt-pl dt-sr">${PS ? won(PS.net) : '—'}<small>${PS ? `빼기 전 ${won(PS.gross)}` : ''}</small></td></tr>
    ${lkLive}${lkBody}${viewH}${belowH}
  </table>`;
  fit2row($('dt-box').querySelector('.dt-2row'));
}

// 두 줄 표 다 그린 뒤 맞춤(11-20) — ① 윗줄 상자 폭을 칸마다 가장 넓은 것에 맞춰 종목마다 세로가 맞게 ② 옆으로 밀 때 붙는 칸(dt-sl · dt-sr)의 자리
//   ③ 머리 네 줄이 위에 차례로 붙게(전에는 둘째 줄 top 을 첫 줄 높이로 — 11-18 재권님 「단타 목록 스크롤하면 칩들이 안보이는 현상」)
function fit2row(tb) {
  if (!tb) return;
  // 잰 값은 화면 배율(작은 창에서 통째로 줄이는 zoom)을 되돌려 CSS 값으로 — getBoundingClientRect 는 줄어든 값을 줌(11-20 좁은 창에서 붙는 칸이 3/4 자리에 섰음)
  const k = tb.offsetWidth / (tb.getBoundingClientRect().width || 1), W = (el) => el.getBoundingClientRect().width * k;
  const fx = [...tb.querySelectorAll('.dt-fx')], n = Math.max(0, ...fx.map((f) => f.children.length));
  for (let i = 0; i < n; i++) { let w = 0; fx.forEach((f) => { const b = f.children[i]; if (b) w = Math.max(w, Math.ceil(W(b))); }); fx.forEach((f) => { const b = f.children[i]; if (b) b.style.width = `${w}px`; }); }
  const sc = tb.closest('.dt-box'), sx = sc ? sc.scrollLeft : 0; if (sc) sc.scrollLeft = 0;   // 옆으로 민 채 다시 그려지면 붙은 칸이 밀린 자리로 재짐 — 0 으로 두고 잰 뒤 되돌림
  const T = tb.getBoundingClientRect();
  tb.querySelectorAll('.dt-sl').forEach((c) => { c.style.left = `${(c.getBoundingClientRect().left - T.left) * k}px`; });
  tb.querySelectorAll('.dt-sr').forEach((c) => { c.style.right = `${(T.right - c.getBoundingClientRect().right) * k}px`; });
  const nm = tb.querySelector('th.st-name'); if (nm) tb.style.setProperty('--dt-fx-l', `${(nm.getBoundingClientRect().right - T.left) * k}px`);   // 윗줄 상자 묶음은 종목 칸 오른쪽에 붙음
  if (sc) sc.scrollLeft = sx;
  let top = 0; tb.querySelectorAll('tr.dt-h').forEach((tr) => { tr.querySelectorAll('th').forEach((th) => { th.style.top = `${top}px`; }); top += tr.offsetHeight; });
}

// 날짜 — 달 줄 위 · 고른 달의 날짜 줄 아래(11-12 재권님 「달이 있어야 되고 해당달하위로 날짜가 있도록 해줘 이정보는 많이 쌓아가야 할거같아. 현재 30개이지만 룰이 확립되면 많이 늘릴거야」)
//   몇 날을 두는지는 서버(meta.daysKeep) 한 곳 — 화면은 서버가 준 날을 다 그린다 · 달 칩 옆 수 = 그 달에 쌓인 날 수
const monOf = (d) => String(d || '').slice(0, 6);
const monTxt = (m) => (m.length === 6 ? `${m.slice(0, 4)}년 ${+m.slice(4)}월` : '—');
// 이달 합계 (11-18 재권님 「11월달 세후손익 다 더해봐」 · 「지금 내가 물어본거를 단타 에서 소팅할수 있게」) — 고른 달의 날마다 판을 서버에서 받아 같은 셈(calc) · 지금 셈 칸 · 칩 켜고 끔을 따름
//   지난 날 판은 한 번 받아 두고(굳힌 값이라 안 바뀜) · 장중인 날은 지금 보는 판(st.data)을 씀 · 못 받은 날은 「못 받음」 으로 내고 합계에서 뺌(0 으로 안 셈)
const dayData = {};
// 지난 판 받기 한 곳 — 달 합계 · 승률 칸 · 칩 조합 셈이 같은 날을 따로 받던 것을 한 번으로(11-26 재권님 「단타쪽 리로드 하는데 엄청 느려졌는데 이유 찾아서 고쳐」 — 메인에서 11-24 · 11-25 판을 서너 번씩 받았음)
//   받는 중인 날은 그 약속을 같이 기다림 · 받은 판은 dayData 에 남음(전과 같음)
const dayProm = {};
const dayGet = (d) => (dayData[d] !== undefined ? Promise.resolve(dayData[d]) : dayProm[d] || (dayProm[d] = (async () => { try { const r = await fetch(`${API}?day=${d}`, { cache: 'no-store' }); const j = r.ok ? await r.json() : null; dayData[d] = j && j.data && j.data.day === d ? renameChips(j.data) : null; } catch (e) { dayData[d] = null; } finally { delete dayProm[d]; } return dayData[d]; })()));
let monSeq = 0;
// 합계 기간 (11-18 재권님 「합계 날짜를 내가 지정할 수 있도록 해줘」) — 시작 · 끝 날을 쌓인 날 중에서 고름 · 안 고르면 지금처럼 고른 달 · 「달로」 로 되돌림
//   고른 기간은 이 브라우저에만 남김(보는 편의 · 공용 값 아님)
const RNG_KEY = 'kjc-dt30-rng';
(() => { try { const v = JSON.parse(localStorage.getItem(RNG_KEY) || 'null'); if (v && v.from && v.to) st.rng = v; } catch (e) { /* 없으면 달 */ } })();
st.byMon = (() => { try { return localStorage.getItem(RNG_KEY + '-mon') === '1'; } catch (e) { return false; } })();   // 달별 보기(11-18 재권님 「달별로 보는것도 그다음에 추가해줘」)
const rngSave = () => { try { if (st.rng) localStorage.setItem(RNG_KEY, JSON.stringify(st.rng)); else localStorage.removeItem(RNG_KEY); } catch (e) { /* 못 남겨도 화면은 돈다 */ } };
function rngBox(el) {
  let b = el.querySelector('.dt-rng'), o = el.querySelector('.dt-msum');
  if (!b) {
    el.innerHTML = '<span class="dt-rng"></span><span class="dt-msum"></span>'; b = el.querySelector('.dt-rng'); o = el.querySelector('.dt-msum');
    b.addEventListener('change', () => { const f = b.querySelector('[data-rng="from"]').value, t = b.querySelector('[data-rng="to"]').value; const lat = st.days.slice().sort().pop(), F = f || (t ? t : ''), T = t || (f ? lat : '');   // 한쪽만 고르면 — 시작만이면 끝은 가장 최근 날 · 끝만이면 그 날 하루
      st.rng = F && T ? (F <= T ? { from: F, to: T } : { from: T, to: F }) : null; rngSave(); chips();   /* 달 단추 칠함도 다시(11-24) */ });
    b.addEventListener('click', (e) => { if (e.target.closest('[data-rng-off]')) { st.rng = null; rngSave(); chips();   /* 달 단추 칠함도 다시(11-24) */ }
      if (e.target.closest('[data-bymon]')) { st.byMon = !st.byMon; try { localStorage.setItem(RNG_KEY + '-mon', st.byMon ? '1' : '0'); } catch (x) { /* 못 남겨도 됨 */ } chips();   /* 달 단추 칠함도 다시(11-24) */ } });
  }
  const all = st.days.slice().sort().reverse(), R = st.rng && all.includes(st.rng.from) && all.includes(st.rng.to) ? st.rng : null;
  const opt = (sel) => all.map((d) => `<option value="${d}"${d === sel ? ' selected' : ''}>${dayTxt(d)}</option>`).join('');
  if (!b.contains(document.activeElement)) b.innerHTML = `기간 <select class="rl-in" data-rng="from" aria-label="합계 시작 날"><option value="">${R ? '' : '달'}</option>${opt(R && R.from)}</select> ~ <select class="rl-in" data-rng="to" aria-label="합계 끝 날"><option value="">${R ? '' : '달'}</option>${opt(R && R.to)}</select>${R ? ' <button type="button" class="kh-chip" data-rng-off>달로</button>' : ''} <button type="button" class="kh-chip${st.byMon ? ' is-active' : ''}" data-bymon aria-pressed="${!!st.byMon}">달별</button> `;
  return { o, R };
}
async function monthPaint() {
  const el0 = $('dt-month'); if (!el0) return;
  const { o: el, R } = rngBox(el0);
  const my = ++monSeq, ds = (st.byMon ? st.days : R ? st.days.filter((d) => d >= R.from && d <= R.to) : st.days.filter((d) => monOf(d) === st.mon)).slice().sort();
  const ttl = st.byMon ? '달별' : R ? `${dayTxt(R.from)} ~ ${dayTxt(R.to)}` : monTxt(st.mon);
  if (!ds.length) { el.textContent = '—'; return; }
  const get = (d) => (st.data && st.data.day === d && (st.data.closed !== true) ? st.data : dayData[d]);
  const need = ds.filter((d) => get(d) === undefined);
  const dB = (d, inner) => `<button type="button" class="kh-chip dt-dayb${d === st.day ? ' is-active' : ''}" role="tab" aria-selected="${d === st.day}" data-day="${d}">${inner}</button>`;   // 날짜를 누르면 그날 판(11-24)
  if (need.length) {   // 날마다 판을 다 받기 전에도 날짜는 바로 고를 수 있게 — 차익은 받은 뒤 채움(개념정의 덧 11-24)
    el.innerHTML = `${ttl} 날마다 판 받는 중… (${ds.length - need.length}/${ds.length})<br>${st.monsH || ''}<span role="tablist" aria-label="날짜 — 누르면 그날 판">${ds.slice().reverse().map((d) => dB(d, dayTxt(d))).join('')}</span>`;
    await Promise.all(need.map(async (d) => { await dayGet(d); }));
    if (my !== monSeq || !root) return;
  }
  if (st.byMon) {   // 달마다 한 줄 — 최근 달이 위 · 셈은 날 합계와 같은 calc · 지금 칸 · 칩대로
    const M = {};
    ds.forEach((d) => { const m = monOf(d), o = M[m] || (M[m] = { tot: 0, cnt: 0, w: 0, l: 0, miss: 0 }); const D = get(d); if (!D) { o.miss++; return; } const C = calc(D); if (!C.P) return; o.cnt++; o.tot += C.P.net; if (C.P.net > 0) o.w++; else if (C.P.net < 0) o.l++; });
    const all = Object.values(M).reduce((a, o) => a + o.tot, 0);
    el.innerHTML = `<b>달별 합계 — 지금 칸 · 칩대로 · 세후 · 쌓인 날 전부 <span class="${signClass(all, NUM) || ''}">${won(all)}</span></b><br>${Object.keys(M).sort().reverse().map((m) => { const o = M[m];
      return `<span>${monTxt(m)} <span class="${signClass(o.tot, NUM) || ''}">${won(o.tot)}</span> <small>매매한 날 ${o.cnt} · 번 날 ${o.w} · 잃은 날 ${o.l}${o.miss ? ` · 못 받은 날 ${o.miss}` : ''}</small></span>`; }).join(' · ')}`;
    return;
  }
  let tot = 0, won0 = 0, lost = 0, cnt = 0; const miss = [];
  // 최근 날이 앞(11-18 재권님 「11월 합계는 최근날짜가 앞으로 오게」)
  const parts = ds.slice().reverse().map((d) => { const D = get(d); if (!D) { miss.push(dayTxt(d)); return dB(d, `${dayTxt(d)} <span class="st-err">못 받음</span>`); }
    const C = calc(D); if (!C.P) return dB(d, `${dayTxt(d)} ${noTradeWhy(C, D)}`); const fbT = C.fb905 ? '<small data-tip="그날 룰로는 매매가 없어 여는 시각 + 5분(9시 5분 · 늦게 연 날은 그만큼 뒤)에 산 것으로 셈"> · 9:05 대체</small>' : '';
    cnt++; tot += C.P.net; if (C.P.net > 0) won0++; else if (C.P.net < 0) lost++;
    return dB(d, `${dayTxt(d)} <span class="${signClass(C.P.net, NUM) || ''}">${won(C.P.net)}</span>${C.LIVE ? '<small>장중</small>' : ''}${fbT}`); });
  el.innerHTML = `<b>${ttl} 합계 — 지금 칸 · 칩대로 · 세후 <span class="${signClass(tot, NUM) || ''}">${won(tot)}</span></b> · 매매한 날 ${cnt} · 번 날 ${won0} · 잃은 날 ${lost}${miss.length ? ` · 못 받은 날 ${miss.length}(합계에서 뺌)` : ''}<br>${st.monsH || ''}<span role="tablist" aria-label="날짜 — 누르면 그날 판">${parts.join('')}</span>`;
}
function chips() {
  if (!st.days.length) { $('dt-days').innerHTML = ''; monthPaint(); return; }
  const mons = [...new Set(st.days.map(monOf))];
  if (!mons.includes(st.mon)) st.mon = monOf(st.day) || mons[0];
    const dayBtn = (d) => { const a = st.last[d]; return `<button type="button" class="kh-chip${d === st.day ? ' is-active' : ''}" role="tab" aria-selected="${d === st.day}" data-day="${d}">${dayTxt(d)}${a == null ? '' : `<small class="${signClass(a, NUM) || ''}">${a > 0 ? '+' : ''}${num(a, 1)}%</small>`}</button>`; };
  // 날짜 줄은 아래 기간 줄 하나로 합침(11-24 재권님 「믿에로 하나로 합쳐줄래? 믿에 날짜와 차익같이 보이고 날짜 누르면 그날그날 종목 보이게」) — 달 단추도 그 줄 머리로
  // 달 단추(11-24 재권님 「달단추옆에 날은 없애줘 헷갈리네. 그리고 년도도 필요없고 , 년도는 따로 고르게 하면될거같아」) — 달 단추는 「11월」 만 · 해는 앞 해 단추로 따로 · 기간 · 달별로 볼 때는 달 단추를 안 칠함
  const yrs = [...new Set(mons.map((m) => m.slice(0, 4)))].sort().reverse(); if (!yrs.includes(st.year)) st.year = (st.mon || mons[0] || '').slice(0, 4) || yrs[0];
  const monOn = (m) => m === st.mon && !st.byMon && !st.rng;
  st.monsH = `<span class="dt-mons dt-mons-in" role="tablist" aria-label="달"><span class="dt-seg dt-years" role="tablist" aria-label="해">${yrs.map((y) => `<button type="button" class="kh-chip${y === st.year ? ' is-active' : ''}" data-year="${y}">${y}년</button>`).join('')}</span>${mons.filter((m) => m.slice(0, 4) === st.year).map((m) => `<button type="button" class="dt-mon${monOn(m) ? ' is-on' : ''}" role="tab" aria-selected="${monOn(m)}" data-mon="${m}">${+m.slice(4)}월</button>`).join('')}</span>`;
  $('dt-days').innerHTML = ''; void dayBtn;
  monthPaint();   // 달이 정해진 뒤 — 고른 달 합계
}
BIND.push(() => { const f = $('dt-setf'); if (!f) return; try { if (localStorage.getItem('dt-setf') === '0') f.open = false; } catch (e) { /* 못 읽어도 펼침 */ }   // 셈 칸 접기 — 이 브라우저에 남김(보는 상태 · 11-24)
  f.addEventListener('toggle', () => { try { localStorage.setItem('dt-setf', f.open ? '1' : '0'); } catch (e) { /* 못 남겨도 됨 */ } }); });
BIND.push(() => ['dt-days', 'dt-month'].forEach((id) => $(id) && $(id).addEventListener('click', (e) => {
  const yb = e.target.closest('[data-year]'); if (yb) { if (yb.dataset.year !== st.year) { st.year = yb.dataset.year; const ms = [...new Set(st.days.map(monOf))].filter((m) => m.slice(0, 4) === st.year); if (ms.length && !ms.includes(st.mon)) st.mon = ms[0]; chips(); } return; }   // 해 고르기(11-24)
  const mb = e.target.closest('[data-mon]');
  if (mb) { if (mb.dataset.mon !== st.mon) { st.mon = mb.dataset.mon; chips(); } return; }   // 달만 바꿈 — 날짜는 그 달 줄에서 고름(판은 그대로)
  const b = e.target.closest('[data-day]'); if (b && b.dataset.day !== st.day) { st.mon = monOf(b.dataset.day); load(b.dataset.day); }
})));

// 장중이면 서버가 정한 주기(meta.refreshMs)로 같은 날을 다시 받는다 — 주기 숫자를 화면에 두지 않는다(「캐시·주기·한도 값을 화면에 박지 않는다」) · 서버가 안 주면 다시 안 받음
let again = null;
async function load(day, quiet) {
  const my = ++st.seq;
  clearTimeout(again); again = null;
  if (!DT_CHIPS.length || st.chipFail) await loadDtChips();   // 칩 목록 — 서버 칩 룰 표(처음 한 번 · 못 받았으면 다음 받기 때 다시)
  if (!quiet) $('dt-meta').textContent = '값을 받는 중…';
  let r = null, j = null;
  try { const pre = !day && st.pre0; st.pre0 = null; r = await (pre || fetch(day ? `${API}?day=${day}` : API, { cache: 'no-store' })); j = await r.json().catch(() => null); } catch (e) { r = null; }   // 처음 판은 셈 칸 문서 · 칩 목록과 함께 받기 시작한 것(st.pre0)을 씀
  if (my !== st.seq) return;
  if (quiet && (!r || !r.ok || !j || j.ok === false || !j.data)) {
    // 장중 다시 받기가 한 번 실패하면 표 · 마지막 값은 두고 머리 줄에만 「못 받음」 · 다음 주기에 다시(qa 11-11 — 덮으면 표가 지워지고 다시 받기가 멈춤)
    const hm = new Date().toTimeString().slice(0, 5);
    $('dt-meta').textContent = `${$('dt-meta').textContent.replace(/ · 새 값 못 받음\([^)]*\)$/, '')} · 새 값 못 받음(${hm} · 다음 주기에 다시)`;
    if (st.ms > 0 && st.day === day) again = setTimeout(() => { if (st.day === day) load(day, true); }, st.ms);
    return;
  }
  if (!r || !r.ok || !j || j.ok === false || !j.data) {
    // 쌓인 날이 없으면 서버가 200 · ok false · meta.days [] 로 답함(개발2 0a3d5eb) — 「못 받음」 이 아니라 「아직 없음」(qa 11-11)
    const none = r && r.ok && j && j.ok === false && Array.isArray(j.meta && j.meta.days) && !j.meta.days.length;
    atText(j && j.meta && j.meta.buyAt);
    const at0 = ((root && root.querySelector('.dt-at')) || {}).textContent || '—';
    const why = !r ? '연결 안 됨' : none ? `아직 쌓인 날 없음 — 첫 판은 평일 ${at0}` : r.status === 404 ? '서버가 아직 단타 30 을 쌓지 않음' : (j && j.error) || `서버 ${r.status}`;
    $('dt-meta').textContent = none ? `— 단타 30: ${why}` : `— 단타 30 값을 못 받음: ${why}`;
    $('dt-box').innerHTML = none
      ? `<div class="dt-empty"><b>아직 쌓인 날 없음</b><span>오늘 ${esc(at0)} 첫 판이 나오고, 지난 30일은 서버 되채움이 들어간 날 밤에 채워집니다</span></div>`
      : `<div class="st-err">— ${esc(why)}</div>`;
    // 아침에 열어 둔 빈 화면 — 서버가 준 매수 시각(meta.buyAt)의 다음 분에 한 번 다시 받는다(주기로 묻지 않음 · 그 판이 생기면 그 뒤는 refreshMs)
    const bm2 = String((j && j.meta && j.meta.buyAt) || '').match(/^(\d{2}):(\d{2})$/);
    if (none && bm2) {
      const at = new Date(); at.setHours(+bm2[1], +bm2[2] + 1, 0, 0);
      const wait = at - Date.now();
      if (wait > 0) again = setTimeout(() => load(), wait);
    }
    return;
  }
  let d = renameChips(j.data); const m = renameChips(j.meta || {});
  st.days = Array.isArray(m.days) ? m.days : [d.day];   // 몇 날을 두는지는 서버(daysKeep) 한 곳 — 화면은 자르지 않음(11-12 재권님 「룰이 확립되면 많이 늘릴거야」)
  d = flat930(d); st.day = d.day; st.data = d;   // 굳힘 없앰 · 09:30 까지 칩(위 flat930) — 아래 그리기도 이 판으로
  if (!DT_CHIPS.length || st.chipFail) {   // 칩 룰 표를 못 받음(옛 서버 404 · 끊김) — 판을 비우지 않고 이 판 줄에 실린 칩(처음 본 차례)으로 칸을 세움 · 머리 글에 「서버 값 못 받음」(11-20 개발 서버에서 판이 빈 것)
    const seen = []; (d.rows || []).forEach((r) => (r.chips || []).forEach((c) => { if (!seen.includes(c)) seen.push(c); }));
    DT_CHIPS.splice(0, DT_CHIPS.length, ...seen); if (!CHIP_SEEN.length) CHIP_SEEN.push(...seen); st.chipFail = true;
  }
  { const T = (d.meta || {}).tax, f = (x) => `${num(x, 2)}%`, el = $('dt-tax');   // 세율 글 — 서버 고정값 그대로(설명 글 룰 1번 · 괄호는 재권님이 넣는 값 자리라 안 씀)
    if (el) el.innerHTML = T && T.KOSPI && T.KOSDAQ ? `거래세 · 농특세 <span class="rl-sug">코스피 거래세 ${f(T.KOSPI.tx)} · 농특세 ${f(T.KOSPI.rural)} · 코스닥 거래세 ${f(T.KOSDAQ.tx)} · 농특세 ${f(T.KOSDAQ.rural)} · 팔 때만 · 서버 고정값</span>` : '거래세 · 농특세 <span class="rl-sug">서버 값 못 받음</span>'; }
  if (st.sfDay !== d.day) { st.sfDay = d.day; loadSector(d.day); }   // 날을 바꿀 때만 — 다시 받는 간격은 섹터수급 쪽이 서버 값으로
  if (d.day === st.days[0]) viLoad(d.day);   // 오늘(맨 앞 날) 판만 — 시각 주소가 오늘 것만 준다
  if (mkOn() && (!KX.bars || (d.day === st.days[0] && d.closed !== true))) kxLoad();   // 코스피 5분봉 — 조건 줄을 쓸 때만 · 오늘 판은 판을 다시 받을 때마다 함께(서버 주기)
  if (d.day === st.days[0] && !wx.data && !wx.timer) wxLoad();   // 지금 바깥 값 — 처음 한 번 · 그 뒤는 서버 ttlSec 대로
  if (st.vdDay !== d.day) { st.vdDay = d.day; vdLoad(d.day); }   // 그날 VI 목록 — 날을 바꿀 때만(지난 날은 굳은 값 · 오늘은 판을 다시 열 때)
  paint(d);
  if (!st.modalPre) { st.modalPre = true; (window.requestIdleCallback || ((f) => setTimeout(f, 1)))(() => { import('/holdings/js/components/stock-modal.js').catch(() => {}); }); }   // 종목 창 부품 — 판을 그린 뒤 한가할 때 미리 받아 둠(처음 누를 때도 바로 뜨게 · 11-26)
  if (st.set.comboAuto !== false && !st.cbStat) comboOpen();   // 칩 조합 자동 — 판을 처음 열 때 지난 판으로 뒤에서 셈해 이름에 적용(11-26)
  chips();
  const ms = Number(m.refreshMs ?? (d.meta && d.meta.refreshMs)); st.ms = ms > 0 ? ms : 0;   // 서버는 판 안 meta(data.meta)에 둔다(개발2 2단계 · 11-12 09:07 잼) — 바깥 meta 도 읽음
  // 오늘 판이면 굳기(closed) 전까지 서버 주기로 다시 받음 — 장 전(08:00~09:00) 줄에 now 가 없어도 칩이 바뀌므로 now 로 가르지 않음(11-20 재권님 「8시되면 갱신되야 되는거지? 실시간으로?」 → 「응 고쳐」)
  const t0 = new Date(), today = `${t0.getFullYear()}${String(t0.getMonth() + 1).padStart(2, '0')}${String(t0.getDate()).padStart(2, '0')}`;
  if (d.day === today) preLoad(d);
  if (d.closed !== true && ms > 0 && d.day === st.days[0] && d.day === today) again = setTimeout(() => { if (st.day === d.day) load(d.day, true); }, ms);
  // 어제 판을 보는 채로 열어 둔 화면 — 오늘 판이 생기는 서버 매수 시각(meta.buyAt)의 다음 분에 한 번 맨 앞 날을 다시 받음(주기로 묻지 않음 · 빈 화면 때와 같은 셈)
  const bm = String(m.buyAt || d.buyAt || '').match(/^(\d{2}):?(\d{2})$/);
  if (!again && bm && d.day === st.days[0] && d.day <= today) {
    const at = new Date(t0); at.setHours(+bm[1], +bm[2] + 1, 0, 0);
    if (at <= t0) at.setDate(at.getDate() + 1);   // 이미 지났으면 다음 날 그 시각 — 밤에 연 채 자정을 넘긴 화면도 넘어감(qa b1e0cd3 검수 덧)
    const wait = at - t0;
    if (wait > 0) again = setTimeout(() => { if (st.day === d.day) load(); }, wait);
  }
}

// 「오늘 프리장」 칸(11-20 재권님 08:35 그림에 「응 맞아」) — 전날 종가 대비 넥스트레이드 프리장 등락
//   값 · 서버 rows[].pre.pct(프리장 끝 값 — 개발2 에 부탁 · 오기 전에는 없음)가 있으면 그것 · 없으면 오늘 판을 정규장(st.openAt) 전에 받을 때마다
//   홀딩스 시세 /api/kis/prices 의 pct 를 받아 둠(판과 함께 · 따로 주기 없음) · 정규장 뒤에는 새로 안 받고 마지막 받은 값과 그 시각을 둠 · 못 받았으면 「—」(0 아님)
async function preLoad(d) {
  const hm = new Date().toTimeString().slice(0, 5), open = String(st.openAt || hmTxt(REG_OPEN_DEF)).slice(0, 5);   // 서버가 주면 안 씀
  if (hm >= open || (d.rows || []).some((r) => r.pre)) return;
  const codes = [...new Set((d.rows || []).map((r) => r.code).filter(Boolean))]; if (!codes.length) return;
  let j = null; try { const r = await fetch(`/api/kis/prices?codes=${codes.join(',')}`, { cache: 'no-store' }); j = r.ok ? await r.json() : null; } catch (e) { j = null; }
  if (!j || !j.data || st.day !== d.day) return;
  const rows = {}; for (const c of codes) { const v = j.data[c] && Number(j.data[c].pct); if (Number.isFinite(v)) rows[c] = v; }
  st.pre = { day: d.day, at: hm, rows };
  if (st.data === d) paint(d);
}
const preOf = (r) => { const p = r.pre && Number(r.pre.pct); if (Number.isFinite(p)) return { v: p, at: r.pre.at || '' };
  const s = st.pre; return s && s.day === st.day && r.code in s.rows ? { v: s.rows[r.code], at: s.at } : null; };
// 「상승률」 칸(11-24 재권님 「섹터와 프리장 사이에 상승률」 → 「나」 오늘 시가 대비) — 서버 rows[].openRise(지금 값 ÷ 오늘 시가) · 없으면 「—」(0 아님)
// 풍선 — 서버가 지금 값으로 셈한 시각(meta.openRiseAt)을 주면 「지금 등락 · 그 시각」 · 안 주는 판(서버 고침 전 · 지난 판)은 「판 지은 때 값」(개발2 11-24)
const orTip = (d) => { const m = (d && d.meta) || {}, raw = String(m.openRiseAt || ''), at = (raw.includes('T') ? raw.split('T')[1] : raw).slice(0, 8);
  return `${at ? `오늘 시가 대비 지금 등락 — 서버가 ${at} 에 셈` : '오늘 시가 대비 등락 — 서버가 판을 마지막으로 다시 센 때 값(지금 값이 아닐 수 있음 · 지난 판은 개장 5분 값)'}${m.openRiseNote ? ` · ${m.openRiseNote}` : ''} · 「상승률 순」 으로 묶음 안에서 줄 세움`; };
// 상승률 — 09:05 까지 1분봉(11-24 재권님 「상승률은 9시 5분까지 분봉으로 바뀌고 높은순으로 실시간으로 순위 적용되게」 → 「응 맞아」)
//   오늘 시가(서버 r.open) 대비 그때까지 받은 마지막 1분 값(서버 r.pxMin 1~5 · 여는 시각 + 1~5분) — 09:05 값이 오면 그 값으로 굳음 · 1분 값이 없는 지난 판은 서버 openRise(지난 판은 개장 5분 값) · 장중 판에 1분 값이 없으면 「—」
const rise5 = (r) => { const o = Number(r.open), M = r.pxMin || {};
  if (o > 0) for (const k of ['5', '4', '3', '2', '1']) { const v = minVal(r, k);   /* 9시 1분 값은 서버 px1Db 먼저(minVal · 개념정의 덧 11-26) */ if (v && Number(v.px) > 0) return { v: (Number(v.px) / o - 1) * 100, at: v.at || '' }; }
  const D = curD(); if (D && D.closed === true && r.openRise != null && Number.isFinite(Number(r.openRise))) return { v: Number(r.openRise), at: '' };
  return null; };
const orV = (r) => { const x = rise5(r); return x ? x.v : -Infinity; };
const orTd = (r) => { const x = rise5(r); return !x ? '<td class="dt-or" data-tip="시가 대비 값을 못 받음 — 서버가 시가 · 1분 값을 안 줌">—</td>' : `<td class="dt-or"${x.at ? ` data-tip="${esc(x.at)} 1분 값 · 오늘 시가 대비"` : ''}>${pct(x.v)}</td>`; };
const preTd = (r) => { const o = preOf(r);
  return o ? `<td class="dt-pre">${pct(o.v)}</td>` : `<td class="dt-pre" data-tip="프리장 값을 못 받음 — 서버가 프리장 끝 값을 아직 안 줌 · 정규장 전에 연 화면만 받아 둠">—</td>`; };

// 칩 칸 차림 — 칸 이름(data-col) · 「+ 칩」(data-addcol)을 누르면 그 아래에 뜸 · 바깥을 누르거나 Esc 면 닫힘
let menu = null;
const menuClose = () => { if (menu) { menu.remove(); menu = null; } };
function menuOpen(at, html) {
  menuClose(); menu = document.createElement('div'); menu.className = 'dt-colmenu'; menu.setAttribute('role', 'menu'); menu.innerHTML = html;
  document.body.appendChild(menu); const r = at.getBoundingClientRect();
  menu.style.left = `${Math.max(8, Math.min(r.left + scrollX, scrollX + innerWidth - menu.offsetWidth - 8))}px`; menu.style.top = `${r.bottom + scrollY + 4}px`;
}
const redraw = () => { colsSave(); menuClose(); if (st.data) { paint(st.data); chips(); } };
document.addEventListener('click', (e) => {
  if (!menu || menu.contains(e.target) || e.target.closest('[data-col],[data-addcol]')) return; menuClose();
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') menuClose(); });
document.addEventListener('click', (e) => {
  const m = e.target.closest('.dt-colmenu [data-act]'); if (!m || m.disabled) return;
  const c = m.dataset.c, cs = [...colsOf()], i = cs.indexOf(c);
  if (m.dataset.act === 'tg') st.off.has(c) ? st.off.delete(c) : st.off.add(c);
  else if (m.dataset.act === 'left' && i > 0) [cs[i - 1], cs[i]] = [cs[i], cs[i - 1]];
  else if (m.dataset.act === 'right' && i >= 0 && i < cs.length - 1) [cs[i + 1], cs[i]] = [cs[i], cs[i + 1]];
  else if (m.dataset.act === 'del') { cs.splice(i, 1); st.off.delete(c); }
  else if (m.dataset.act === 'add') { cs.push(c); st.off.delete(c); }
  else if (m.dataset.act === 'rule') { menuClose(); const rb = document.querySelector(`#rl-chips [data-rule="${RULE_OF[c]}"]`); if (rb) { rb.click(); rb.scrollIntoView({ block: 'center' }); } return; }
  st.cols = cs; redraw();
});
BIND.push(() => $('dt-box').addEventListener('click', (e) => {   // 칩 줄은 표와 함께 다시 그려져 표 칸(dt-box)에서 받음
  const col = e.target.closest('[data-col]');
  if (col) { const c = col.dataset.col, on = !st.off.has(c), cs = colsOf(), i = cs.indexOf(c);
    menuOpen(col, `<button type="button" data-act="tg" data-c="${esc(c)}">${on ? '끄기 — 셈에서 뺌' : '켜기 — 셈에 넣음'}</button>`
      + `<button type="button" data-act="rule" data-c="${esc(c)}"${RULE_OF[c] ? '' : ' disabled'}>${RULE_OF[c] ? '룰 보기 · 고치기' : '룰 보기 — 이 칩은 룰 칸 없음'}</button>`
      + `<button type="button" data-act="left" data-c="${esc(c)}"${i > 0 ? '' : ' disabled'}>← 왼쪽으로</button><button type="button" data-act="right" data-c="${esc(c)}"${i < cs.length - 1 ? '' : ' disabled'}>오른쪽으로 →</button>`
      + `<button type="button" data-act="del" data-c="${esc(c)}">칸 지우기 — 「+ 칩」 으로 다시 더함</button>`); return; }
  const add = e.target.closest('[data-addcol]');
  if (add) { const all = (st.data && st.data.rows) || [], cs = colsOf();
    const pool = [...new Set([...DT_CHIPS, ...all.flatMap((r) => r.chips || [])])].filter((c) => !cs.includes(c));
    menuOpen(add, pool.length ? `<span class="dt-cmh">칩 칸 더하기 — 더하면 켜진 채로 셈에 듦</span>${pool.map((c) => `<button type="button" data-act="add" data-c="${esc(c)}">${esc(c)} <small>${all.filter((r) => (r.chips || []).includes(c)).length}종목</small></button>`).join('')}`
      : '<span class="dt-cmh">더할 칩 없음 — 서버가 주는 칩이 다 칸에 있음</span>'); return; }
  const b = e.target.closest('[data-chip],[data-sub]'); if (!b || b.disabled) return;
  if (b.dataset.chip) { const c = b.dataset.chip; st.off.has(c) ? st.off.delete(c) : st.off.add(c); }
  else { const k = b.dataset.sub; st.subOff.has(k) ? st.subOff.delete(k) : st.subOff.add(k); }
  colsSave(); if (st.data) { paint(st.data); chips(); }
}));
/* 종목 이름을 누르면 홀딩스 홈과 같은 종목 모달 — 단타 판 표 · VI 목록 둘 다(11-24 재권님 「가」 · 공용 부품 openStockModal)
   칩 · 단추 · 풀이 글을 누른 것은 그쪽 일을 한다. 길게 누르기(회사 풍선)는 company-tip 이 따로 받는다 */
const openCo = (e) => {
  if (e.target.closest('button, a, input, [data-chip], [data-sub], [data-col], .dt-evs, [data-tip]')) return;
  const c = e.target.closest('[data-co]'), code = c && c.dataset.co; if (code) openStockModal(code);   // 이름 · 색은 부품이 서버에서 찾는다(brand 까지)
};
BIND.push(() => ['dt-box', 'dt-vi'].forEach((id) => { const el = $(id); if (el) el.addEventListener('click', openCo); }));
BIND.push(() => $('dt-order').addEventListener('click', (e) => { const b = e.target.closest('[data-order]'); if (!b || b.dataset.order === st.order) return; st.order = b.dataset.order; if (st.data) { paint(st.data); chips(); } }));
BIND.push(() => $('dt-box').addEventListener('click', (e) => { if (!e.target.closest('[data-allon]')) return; st.off.clear(); st.subOff.clear(); const cs = colsOf(), add = [...new Set(((st.data && st.data.rows) || []).flatMap((r) => r.chips || []))].filter((c) => !cs.includes(c) && !(st.watchAuto && c === '자동')); if (add.length) st.cols = [...cs, ...add]; colsSave(); if (st.data) { paint(st.data); chips(); } }));   // 빈 판의 「꺼 둔 칩 다 켜기」
BIND.push(() => $('dt-box').addEventListener('click', (e) => { const b = e.target.closest('[data-lock]'); if (!b || b.disabled) return; st.lockSel = Number(b.dataset.lock); if (st.data) paint(st.data); }));   // 굳힘 시각 단추
BIND.push(() => $('dt-only').addEventListener('click', (e) => { const b = e.target.closest('[data-only]'); if (!b || b.dataset.only === st.only) return; st.only = b.dataset.only; if (st.data) { paint(st.data); chips(); } }));

async function loadFee() {
  if (!DT_CHIPS.length || st.chipFail || st.sellFail !== false) await loadDtChips();   // 매도 기본값(SELL_DEF)이 셈 칸보다 먼저
  try { const r = await fetch(DOC, { cache: 'no-store' }); const j = r.ok ? await r.json() : null; const R0 = j && j.data && j.data.rules && j.data.rules.dt30 ? j.data.rules.dt30 : {}; const v = R0.feePct; st.fee = v == null || v === '' ? null : Number(v);
    st.set = { ...DEF_SET, ...SELL_DEF, ...(R0.set && typeof R0.set === 'object' ? R0.set : {}), mode: 'day' }; st.setSaved = { ...st.set }; st.setDirty = false; st.chipSig = chipSig();   // chipSig — 이 화면을 연 때의 끈 칩(자동 저장은 이 화면에서 칩을 바꿨을 때만 · 다른 브라우저가 열려 있다 저장값을 덮지 않게 · 11-24)   // 저장된 값 — 차례 점수만 바로 저장할 때 안 누른 고침을 섞지 않으려고(개념정의 덧 11-23)
    st.score = R0.score && typeof R0.score === 'object' ? R0.score : {};   // 돈은 늘 전체 금액 ÷ 종목 수
    if (R0.set && R0.set.mode === 'each' && R0.set.perWon) st.set.dayWon = R0.set.perWon * (st.set.top || PNL_TOP); }   // 옛 저장값(종목마다)은 같은 돈이 되게 옮김
  catch (e) { st.fee = null; st.set = { ...DEF_SET, ...SELL_DEF }; }
  if (st.sellFail) $('dt-set-msg').textContent = '매도 기본값 — 서버 값 못 받음(넣지 않은 매도 칸은 셈 안 함)';
  $('dt-fee').value = st.fee == null ? '' : String(st.fee);
  setFill();
}
// 셈 칸에 지금 값 채우기 · 단추 켜짐 표시
function setFill() {
  const S = st.set, box = $('dt-pnl'); if (!box) return;
  { const g = $('dt-lkgrid'), W = winsOf(), sig = JSON.stringify(W); if (g && g.dataset.sig !== sig && !g.contains(document.activeElement)) { g.innerHTML = ''; g.dataset.sig = sig;   /* 굳힘 없앰(11-23) — 굳힘 · 창 설정 표를 안 그림 · lkGridHtml 은 되돌릴 때 쓰려고 남김 */ g.style.gridTemplateColumns = W ? 'auto auto auto' : 'auto auto auto auto auto auto'; } }   // 창 여섯 · 옛 판은 굳힘 넷
  const v = { minChip: S.minChip || '', top: S.top, won: (S.mode === 'day' ? S.dayWon : S.perWon) / 10000, grpWon: (S.grpWon > 0 ? S.grpWon : S.dayWon) / 10000, stop: S.stop == null ? '' : S.stop, trail: S.trail == null ? '' : S.trail, turnPct: S.turnPct || '', cutMin: S.cutMin ?? '', flatMin: S.flatMin ?? '', flatPct: S.flatPct ?? '', endAt: S.endAt ? hmTxt(S.endAt) : '', cutPct: S.cutPct ?? '', lock0: (S.lockAt || [])[0] || '', lock1: (S.lockAt || [])[1] || '', lock2: (S.lockAt || [])[2] || '' };
  ORD_KEYS.forEach(([k]) => { v[`ord:${k}`] = (S.ordScore || {})[k] ?? ''; });
  v.ruleMin = S.ruleMin ?? ''; v.turnMin = S.turnMin || '';   // 매수 룰 정의(11-24)
  box.querySelectorAll('.dt-fill-n').forEach((e) => { e.textContent = S.minChip > 0 ? String(S.minChip) : ' '; }); box.querySelectorAll('.dt-fill-m').forEach((e) => { e.textContent = S.minChip > 1 ? String(S.minChip - 1) : ' '; }); box.querySelectorAll('[data-fill]').forEach((b) => b.classList.toggle('is-active', (b.dataset.fill === '1') === !!S.fill));   // 칩 모자라면 채움(11-24)   // 매수 메시지 보내기(11-24)
  box.querySelectorAll('.dt-send-n').forEach((e) => { e.textContent = S.minChip > 0 ? String(S.minChip) : ' '; }); box.querySelectorAll('.dt-top-n').forEach((e) => { e.textContent = S.top > 0 ? String(S.top) : ' '; });   // 칩 수 · 채움 목표 = 상위 N(11-24) — 옛 「매수 메시지 보내기」 칸의 .dt-send-u 갱신은 칸과 함께 걷음(개념정의 덧)
  ['up', 'dn'].forEach((sd) => { const L = (S.mk || {})[sd] || {}; v[`mk:${sd}:pct`] = L.pct ?? ''; v[`mk:${sd}:stop`] = L.stop ?? ''; });   // 코스피 조건 줄(11-24)
  [0, 1, 2, 3, 4, 5].forEach((i) => { const gw = (S.grpWons || [])[i]; v[`gw${i}`] = gw > 0 ? gw / 10000 : ''; v[`gn${i}`] = (S.lockNs || [])[i] ?? ''; v[`gc${i}`] = (S.lockMinChip || [])[i] ?? ''; });   // 굳힘 칸마다(11-23)   // 종목 차례 점수(11-23)
  box.querySelectorAll('[data-set]').forEach((el) => { if (document.activeElement !== el) el.value = String(v[el.dataset.set] ?? ''); });
  box.querySelectorAll('[data-mode]').forEach((b) => b.classList.toggle('is-active', b.dataset.mode === S.mode));
  box.querySelectorAll('[data-nobuy]').forEach((b) => b.classList.toggle('is-active', !!(S.lockNoBuy || [])[+b.dataset.nobuy]));
  box.querySelectorAll('[data-turn]').forEach((b) => b.classList.toggle('is-active', (b.dataset.turn === '1') === !!S.turn));
  box.querySelectorAll('[data-turnby]').forEach((b) => b.classList.toggle('is-active', b.dataset.turnby === (S.turnBy || 'both')));
  box.querySelectorAll('[data-turnfor]').forEach((el) => { const tb = S.turnBy || 'both'; el.hidden = tb !== 'both' && el.dataset.turnfor !== tb; });
  box.querySelectorAll('[data-turnsep]').forEach((el) => { el.hidden = (S.turnBy || 'both') !== 'both'; });   // 둘 다일 때 두 설명 사이 · (qa 11-20 좁은 폭에서 붙어 보임)
  box.querySelectorAll('[data-buy]').forEach((b) => { b.classList.toggle('is-active', b.dataset.buy === buyKey() && !S.comboOn); const B = BUYS.find(([k]) => k === b.dataset.buy); if (B) b.textContent = buyName(...B); });   // 이름 시각은 그 판 서버 값(늦게 여는 날)
  { const D = (st.data && st.data.meta && (st.data.meta.lockDef || st.data.meta.lockAt)) || []; box.querySelectorAll('[data-set^="lock"]').forEach((el, i) => { el.placeholder = D[i] || '( )'; }); }
  { const n0 = st.data && st.data.meta && Number(st.data.meta.lockN); box.querySelectorAll('[data-set^="gn"]').forEach((el) => { el.placeholder = n0 > 0 ? String(n0) : '( )'; }); const w0 = (S.grpWon > 0 ? S.grpWon : S.dayWon) / 10000; box.querySelectorAll('[data-set^="gw"]').forEach((el) => { el.placeholder = w0 > 0 ? String(w0) : '( )'; }); }   // 빈칸에 보이는 기본 — 종목 수 서버 meta.lockN · 금액 「굳힘마다 금액」   // 빈칸에 보이는 기본 시각은 서버 값(meta.lockDef · 없으면 지금 굳힘 시각 meta.lockAt) — 화면에 시각을 안 박음
  // 판 아래 설명 — 「9시1분~5분사이 들어온 종목」 매수의 셈(11-23) · 끝 분은 서버 값(inUntil)을 끼움 · 못 받으면 「서버 값 못 받음」(「설명 글에는 정해진 값을 적는다」)
  { const el = root && root.querySelector('.dt-buyrule'); if (el) { const u = inUntil();
    el.textContent = buyKey() === 'p1' ? ` · 매수(9시1분~5분사이 들어온 종목) — 첫 굳힘 종목은 9시 1분 전에 든 것 9시 1분 값 · 9시 1분 ~ ${u ? `${hmS(u)}:59` : '(서버 값 못 받음)'} 에 든 것 든 때 값 · 둘째 굳힘부터와 아직 안 굳은 종목(다음 굳힘 단추 「대기」)은 처음 든 때 값 · 평균 줄 · 손익은 고른 굳힘 단추의 종목만` : ''; } }
  box.querySelectorAll('[data-pyr]').forEach((b) => b.classList.toggle('is-active', (b.dataset.pyr === '1') === !!S.pyr));
  { const T = (st.data && st.data.times) || [], end = T.length ? hmTxt(hhmm(T[T.length - 1])) : '( )'; box.querySelectorAll('[data-set="endAt"]').forEach((el) => { el.placeholder = end; }); box.querySelectorAll('[data-endsug]').forEach((el) => { el.textContent = `빈칸 = ${end}(판 끝 칸 · 서버 값)`; }); }
  box.querySelectorAll('[data-flat]').forEach((b) => b.classList.toggle('is-active', (b.dataset.flat === '1') === !!S.flat));
  box.querySelectorAll('[data-sbar]').forEach((b) => b.classList.toggle('is-active', b.dataset.sbar === (S.sellBar === '1m' || S.sellBar === '5m' ? S.sellBar : '30m')));
  box.querySelectorAll('[data-mkon]').forEach((b) => { const L = (S.mk || {})[b.dataset.mkon] || {}; b.checked = L.on !== false; const row = b.closest('.dt-mkrow'); if (row) row.classList.toggle('is-off', L.on === false); });
  box.querySelectorAll('[data-mkref]').forEach((b) => { const [sd, k] = b.dataset.mkref.split(':'); b.classList.toggle('is-active', ((((S.mk || {})[sd] || {}).ref) || 'open') === k); });
  box.querySelectorAll('[data-mksbar]').forEach((b) => { const [sd, k] = b.dataset.mksbar.split(':'); const L = (S.mk || {})[sd] || {}; b.classList.toggle('is-active', (L.sellBar || (S.sellBar === '1m' || S.sellBar === '5m' ? S.sellBar : '30m')) === k); });
  box.querySelectorAll('[data-late]').forEach((b) => b.classList.toggle('is-active', (b.dataset.late === '1') === !!S.buyLate930));
  box.querySelectorAll('[data-cut]').forEach((b) => b.classList.toggle('is-active', (b.dataset.cut === '1') === !!S.cut));
  comboPaint();   // 칩 조합 칸 — 고른 수 · 체크(11-26)
}
// 룰 문서에 한 칸 고쳐 쓰기 — 수수료 · 셈 칸이 같은 길(못 읽으면 안 씀 · 409 면 한 번 더)
async function saveDt(patch) {
  for (let n = 0; n < 2; n++) {
    const g = await fetch(DOC, { cache: 'no-store' });
    if (!g.ok && g.status !== 404) throw new Error(`문서를 못 읽어 저장 안 함 · ${g.status}`);
    const j = g.ok ? await g.json().catch(() => null) : null;
    if (g.ok && !(j && j.data && typeof j.data === 'object')) throw new Error('문서를 못 읽어 저장 안 함');
    const doc = g.ok ? j.data : { rules: {} }; const at = g.ok ? (j.updatedAt ?? j.data.updatedAt ?? null) : null;
    doc.rules = doc.rules || {}; doc.rules.dt30 = { ...(doc.rules.dt30 || {}), ...patch };
    const r = await fetch(DOC, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ data: doc, ...(at ? { updatedAt: at } : {}) }) });
    if (r.status === 409) continue;
    if (!r.ok) throw new Error(String(r.status));
    return;
  }
  throw new Error('다른 곳에서 계속 고치는 중');
}
// 셈 칸 고침 — 값을 읽어 맞으면 바로 다시 셈하고 저장 · 틀리면 되돌림
async function setChange(next) {
  const msg = $('dt-set-msg'), prevOrd = (st.set && st.set.ordScore) || {};
  st.set = next; setFill();
  if (st.data) { paint(st.data); chips(); }
  if (mkOn() && !KX.bars) kxLoad();   // 코스피 조건 줄을 처음 넣으면 코스피 봉을 받아 다시 셈(11-24)
  // 저장은 「저장」 단추로(11-23 재권님 「매도 내가 수정하고 저장하게 저장버튼 만들어줘」) — 고치면 화면만 다시 셈 · 차례 점수만은 서버가 셈하므로 바로 저장
  if (JSON.stringify(prevOrd) === JSON.stringify(next.ordScore || {})) { st.setDirty = true; setDirtyMark(); return; }
  // 차례 점수만 바로 저장 — 저장 안 누른 다른 칸 고침은 섞지 않음(저장된 값 + 차례 점수 · 개념정의 덧 11-23)
  msg.textContent = '차례 점수 저장하는 중…';
  try { const base = { ...(st.setSaved || st.set), ordScore: next.ordScore }; await saveDt({ set: base }); st.setSaved = base; setDirtyMark(); if (!st.setDirty) msg.textContent = '차례 점수 저장됨'; }
  catch (e) { msg.textContent = `차례 점수 저장 못 함(${e.message || '연결 안 됨'})`; }
  load(st.day, true);   // 차례 점수는 서버가 셈 — 저장 뒤 판을 다시 받아 새 차례(11-23)
}
// 저장 안 한 고침 — 서버는 그날 여는 시각 + 1분에 저장된 셈 칸을 굳혀 알림을 보냄(dt30.buy_set_freeze) · 그 전 · 뒤를 함께 적음(11-26 재권님 「화면이 셈칸을 저절로 저장하는걸 없애면?」 → 「응」)
const freezeTxt = () => { const t0 = new Date(), today = `${t0.getFullYear()}${String(t0.getMonth() + 1).padStart(2, '0')}${String(t0.getDate()).padStart(2, '0')}`; if ((curD() || {}).day !== today) return ''; const fz = addHM(openHM(), 1), now = `${String(t0.getHours()).padStart(2, '0')}${String(t0.getMinutes()).padStart(2, '0')}`; return now < fz ? ` · ${hmS(fz)} 전에 저장해야 오늘 알림에 듦` : ` · 오늘 알림은 ${hmS(fz)} 에 굳은 셈 칸 — 이 고침은 내일부터`; };
const setDirtyMark = () => { const msg = $('dt-set-msg'); if (msg) msg.textContent = st.setDirty ? `고침 — 화면만 다시 셈 · 「저장」 을 눌러야 남음${freezeTxt()}` : ''; document.querySelectorAll('[data-setsave]').forEach((b) => b.classList.toggle('is-active', !!st.setDirty)); };
// 저장 안 하고 떠나면 브라우저가 묻게(개념정의 덧 11-23)
window.addEventListener('beforeunload', (e) => { if (st.setDirty) { e.preventDefault(); e.returnValue = ''; } });
// 자동 저장(11-24 · 여는 시각 + 4분 직전)은 걷음 — 서버가 여는 시각 + 1분에 셈 칸을 굳히게 된 뒤(11-26 1f5e96e) 그날 알림에 안 들고 장중 셈 칸만 바꿨음 · 재권님 「화면이 셈칸을 저절로 저장하는걸 없애면?」 → 「응」(11-26) · 저장은 「저장」 단추로만
// chipCols 는 「자동」 칸을 늘 뺀다 — 서버 장중 판은 늘 watchRule 「자동」 이라 화면이 그 칸을 안 셈(colsOf · wAuto) · 옛 날 판(자동 아님)을 보다 저장해도 서버가 「자동」 칩을 세지 않게(개념정의 덧 11-24)
// 저장은 서버 이름으로(11-25 qa — 서버 매수 셈이 「거래비율」 · 「거래비율급증」 으로 읽는데 화면 이름 「현시간 유통회전」 · 「전일 현시간 대비 급증」 이 들어가 칸 밖으로 셌음) · 비교 값(chipSig)도 같은 셈이라 함께 바뀜
function chipSave() { return { chipOff: [...st.off].map(serverChip), subOff: [...st.subOff].map((k) => { const i = k.indexOf('|'); return i < 0 ? serverChip(k) : `${serverChip(k.slice(0, i))}${k.slice(i)}`; }), chipCols: (st.cols || DT_CHIPS).filter((c) => c !== '자동').map(serverChip), chipKnown: [...new Set([...DT_CHIPS, ...(st.cols || []), '자동'])].map(serverChip) }; }   // chipKnown — 저장할 때 화면이 알던 서버 칩 전부 · 서버는 그 밖 칩(저장 뒤 새로 생긴 칩)을 켬으로 셈(11-25 개발2 · 재권님 「처음부터 셈이되도록 켜줘」) · chipCols 밖이면서 여기 있는 칩은 칸에서 지운 것 = 안 셈 · 「자동」 은 넣는다(chipCols 에서만 뺌 — 빼면 서버가 새 칩으로 읽어 다시 셈 · 개념정의 검수 덧 11-25)   // 함수 선언 — loadFee 가 이 줄보다 먼저 돌아도 쓰이게
function chipSig() { return JSON.stringify(chipSave()); }
async function setSave() {
  const msg = $('dt-set-msg'); msg.textContent = '저장하는 중…';
  // 끈 칩 · 하위 칩 · 칩 칸도 함께(11-24 재권님 「카드에 있것들 해」 · 개발2 — 서버 매수 알림이 화면 everChip · liveChip · subsOf 와 같게 셈) · 열쇠 chipOff · subOff · chipCols
  const S = { ...st.set, ...chipSave() };
  try { await saveDt({ set: S }); st.set = S; st.setSaved = { ...S }; st.setDirty = false; st.chipSig = chipSig(); setDirtyMark(); msg.textContent = '저장됨'; }
  catch (e) { msg.textContent = `저장 못 함(${e.message || '연결 안 됨'}) — 화면은 고친 값으로 셈 · 다시 「저장」`; }
}
function setRead(el) {
  const k = el.dataset.set, raw = el.value.trim().replace(/,/g, ''), S = { ...st.set };
  const bad = (t) => { $('dt-set-msg').textContent = `${t} — 되돌렸습니다`; setFill(); return null; };
  if (/^lock[0-2]$/.test(k)) {   // 굳힘 시각(11-20 재권님 「값이 없으면 9시 5분 9시 30분 10시로 고정되게 하고 값이 있으면 그 값을 오버라이드」) — 빈칸 = 서버 기본 · HH:MM 또는 HHMM
    const m = raw.match(/^(\d{1,2}):?(\d{2})$/), L = [...(S.lockAt || [null, null, null])];
    if (raw && (!m || +m[1] > 23 || +m[2] > 59)) return bad('시각은 09:05 꼴');
    L[+k.slice(4)] = raw ? `${m[1].padStart(2, '0')}:${m[2]}` : null; S.lockAt = L; return S;
  }
  if (k.startsWith('ord:')) {   // 종목 차례 점수(11-23) — 빈칸 = 안 씀 · 0 이상
    const w = raw === '' ? null : Number(raw); if (w != null && (!Number.isFinite(w) || w < 0)) return bad('0 이상 숫자 · 빈칸 = 안 씀');
    const O = { ...(S.ordScore || {}) }; if (w == null || w === 0) delete O[k.slice(4)]; else O[k.slice(4)] = w; S.ordScore = O; return S;
  }
  if (/^g[wnc][0-5]$/.test(k)) {   // 굳힘 칸마다 금액(만원) · 굳힐 종목 수 · 칩 몇 개 이상(11-23) — 빈칸 = 기본
    const w = raw === '' ? null : Number(raw), i = +k[2], key = { w: 'grpWons', n: 'lockNs', c: 'lockMinChip' }[k[1]];
    if (w != null && (!Number.isFinite(w) || w <= 0 || (k[1] !== 'w' && !Number.isInteger(w)))) return bad(k[1] === 'w' ? '0 보다 큰 만원 · 빈칸 = 기본' : '1 이상 정수 · 빈칸 = 기본');
    const A = [...(S[key] || [])]; while (A.length <= i) A.push(null); A[i] = w == null ? null : k[1] === 'w' ? Math.round(w * 10000) : w; S[key] = A; return S;
  }
  if (k.startsWith('mk:')) {   // 코스피 조건 줄(11-24) — at 시각 · pct 기준 대비 % · stop 손절 %
    const [, sd, f] = k.split(':'), M = { ...(S.mk || {}) }, L = { ...(M[sd] || {}) };
    if (f === 'at') return S;   // 시각 칸은 11-24 재권님 「코스피가 () 에 이건 필요없고」 로 뺌
    { const x = raw === '' ? null : Number(raw); if (x != null && !Number.isFinite(x)) return bad('숫자만');
      if (f === 'pct') L.pct = x == null ? null : sd === 'up' ? Math.abs(x) : -Math.abs(x);   // 상승은 + · 하락은 − 로
      else { if (x === 0) return bad('0 은 못 씀 · 빈칸이면 손절 안 함'); L.stop = x == null ? null : -Math.abs(x); } }
    M[sd] = L; S.mk = M; return S;
  }
  if (k === 'endAt') { if (raw === '') { S.endAt = ''; return S; } const m = /^(\d{1,2}):?(\d{2})$/.exec(raw); if (!m || +m[1] > 15 || +m[2] > 59) return bad('시각은 13:30 꼴 · 빈칸이면 판 끝'); S.endAt = m[1].padStart(2, '0') + m[2]; return S; }   // 「13:30」 꼴이라 숫자 검사 앞에서
  const v = raw === '' ? null : Number(raw);
  if (v != null && !Number.isFinite(v)) return bad('숫자만');
  if (k === 'ruleMin') { if (v != null && (!Number.isInteger(v) || v < RULE_MIN_LO || v > RULE_MIN_HI)) return bad(`${RULE_MIN_LO}~${RULE_MIN_HI} 정수(분) · 빈칸 = ${RULE_MIN_DEF}분`); S.ruleMin = v; return S; }   // 매수 룰 기준 시각(11-24)
  if (k === 'turnMin' || k === 'volMin') { if (v != null && v < 0) return bad('0 이상 % · 빈칸 = 안 거름'); S[k] = v || 0; return S; }   // 11-24
  if (k === 'floatMax') { if (v != null && v < 0) return bad('0 이상 억 · 빈칸 = 전체'); S.floatMax = v || 0; return S; }
  if (k === 'minChip') { if (v != null && (v < 0 || !Number.isInteger(v))) return bad('0 이상 정수'); S.minChip = v || 0; }
  else if (k === 'top') { if (v == null || v < 1 || !Number.isInteger(v)) return bad('1 이상 정수'); S.top = v; }
  else if (k === 'won') { if (v == null || v <= 0) return bad('0 보다 큰 만원'); S[S.mode === 'day' ? 'dayWon' : 'perWon'] = Math.round(v * 10000); }
  else if (k === 'grpWon') { if (v == null || v <= 0) return bad('0 보다 큰 만원'); S.grpWon = Math.round(v * 10000); }   // 굳힘마다 금액(11-20) · DEF_SET 에 없으면 dayWon 과 같게 셈
  else if (k === 'stop') { if (v === 0) return bad('0 은 못 씀 · 빈칸이면 손절 안 함'); S.stop = v == null ? null : -Math.abs(v); }   // 1 · −1 둘 다 「−1%」 로
  else if (k === 'turnPct') { S.turnPct = v == null ? 0 : Math.abs(v); }
  else if (k === 'cutMin') { if (v == null || v < 0 || !Number.isInteger(v)) return bad('0 이상 정수(분)'); S.cutMin = v; }
  else if (k === 'flatMin') { if (v != null && (v < 0 || !Number.isInteger(v))) return bad('0 이상 정수(분) · 빈칸 = 안 씀'); S.flatMin = v; }
  else if (k === 'flatPct') { if (v === 0) return bad('0 은 못 씀 · 빈칸 = 안 씀'); S.flatPct = v == null ? null : Math.abs(v); }
  else if (k === 'cutPct') { if (v == null) return bad('빈칸은 못 씀'); S.cutPct = v; }
  else if (k === 'trail') { if (v === 0) return bad('0 은 못 씀 · 빈칸이면 안 씀'); S.trail = v == null ? null : Math.abs(v); }
  return S;
}
BIND.push(() => {
  const box = $('dt-pnl');   // 셈 칸 줄 + 손익 머리 줄(상위 · 금액)
  box.addEventListener('change', (e) => { const el = e.target.closest('[data-set]'); if (!el) return; const S = setRead(el); if (S) setChange(S); });
  $('dt-box').addEventListener('change', (e) => { const ck = e.target.closest('[data-fltchk]'); if (ck) { setChange({ ...st.set, [`${ck.dataset.fltchk}On`]: !!ck.checked }); return; } const el = e.target.closest('[data-set="floatMax"], [data-set="turnMin"], [data-set="volMin"]'); if (!el) return; const S = setRead(el); if (S) setChange(S); });   // 거르기 둘 체크 · 칸(11-24)   // 종목 머리 칸 유통 거르기(11-23)
  box.addEventListener('click', (e) => {
    const m = e.target.closest('[data-mode]'); if (m) { e.preventDefault(); if (m.dataset.mode !== st.set.mode) setChange({ ...st.set, mode: m.dataset.mode }); return; }
    const bb = e.target.closest('[data-buy]'); if (bb) { e.preventDefault(); if (bb.dataset.buy !== buyKey() || st.set.comboOn) setChange({ ...st.set, buy: bb.dataset.buy, comboOn: false }); return; }   // 조합으로 사던 중이면 끔
    const y = e.target.closest('[data-pyr]'); if (y) { e.preventDefault(); const on = y.dataset.pyr === '1'; if (on !== !!st.set.pyr) setChange({ ...st.set, pyr: on }); return; }
    const nb = e.target.closest('[data-nobuy]'); if (nb) { e.preventDefault(); const A = [...(st.set.lockNoBuy || [])], i = +nb.dataset.nobuy; while (A.length <= i) A.push(null); A[i] = A[i] ? null : true; setChange({ ...st.set, lockNoBuy: A }); return; }
    if (e.target.closest('[data-setsave]')) { e.preventDefault(); setSave(); return; }   // 셈 칸 저장(11-23)
    const fb = e.target.closest('[data-fill]'); if (fb) { e.preventDefault(); const on = fb.dataset.fill === '1'; if (on !== !!st.set.fill) setChange({ ...st.set, fill: on }); return; }   // 채움 · 채우지 않음(11-24)
    const mo = e.target.closest('[data-mkon]'); if (mo) { const sd = mo.dataset.mkon, M = { ...(st.set.mk || {}) }; M[sd] = { ...(M[sd] || {}), on: !!mo.checked }; setChange({ ...st.set, mk: M }); return; }   // 줄 켜고 끄기(11-24)
    const mr = e.target.closest('[data-mkref]'); if (mr) { e.preventDefault(); const [sd, k] = mr.dataset.mkref.split(':'); const M = { ...(st.set.mk || {}) }; M[sd] = { ...(M[sd] || {}), ref: k }; setChange({ ...st.set, mk: M }); return; }   // 코스피 조건 기준(11-24)
    const ms = e.target.closest('[data-mksbar]'); if (ms) { e.preventDefault(); const [sd, k] = ms.dataset.mksbar.split(':'); const M = { ...(st.set.mk || {}) }; M[sd] = { ...(M[sd] || {}), sellBar: k }; setChange({ ...st.set, mk: M }); return; }
    const sbb = e.target.closest('[data-sbar]'); if (sbb) { e.preventDefault(); const v = sbb.dataset.sbar; if (v !== st.set.sellBar) setChange({ ...st.set, sellBar: v }); return; }
    const lt = e.target.closest('[data-late]'); if (lt) { e.preventDefault(); const on = lt.dataset.late === '1'; if (on !== !!st.set.buyLate930) setChange({ ...st.set, buyLate930: on }); return; }
    const fl = e.target.closest('[data-flat]'); if (fl) { e.preventDefault(); const on = fl.dataset.flat === '1'; if (on !== !!st.set.flat) setChange({ ...st.set, flat: on }); return; }
    const cu = e.target.closest('[data-cut]'); if (cu) { e.preventDefault(); const on = cu.dataset.cut === '1'; if (on !== !!st.set.cut) setChange({ ...st.set, cut: on }); return; }
    const tb = e.target.closest('[data-turnby]'); if (tb) { e.preventDefault(); if (tb.dataset.turnby !== (st.set.turnBy || 'both')) setChange({ ...st.set, turnBy: tb.dataset.turnby }); return; }
    const t = e.target.closest('[data-turn]'); if (t) { e.preventDefault(); const on = t.dataset.turn === '1'; if (on !== !!st.set.turn) setChange({ ...st.set, turn: on }); return; }
    if (e.target.closest('[data-reset]')) setChange({ ...DEF_SET, ...SELL_DEF });
  });
});
async function saveFee() {
  const el = $('dt-fee'), raw = el.value.trim(), v = raw === '' ? null : Number(raw);
  if (v != null && (!Number.isFinite(v) || v < 0)) { $('dt-fee-msg').textContent = '0 이상 숫자만 — 되돌렸습니다'; el.value = st.fee == null ? '' : String(st.fee); return; }
  $('dt-fee-msg').textContent = '저장하는 중…';
  // 문서를 못 읽으면 쓰지 않는다 — 빈 문서로 PUT 하면 종목 고르는 룰 값까지 덮어쓴다(qa 11-11) · 404(아직 없는 문서)만 빈 문서로 새로 만든다(saveDt)
  try { await saveDt({ feePct: v }); }
  catch (e) { $('dt-fee-msg').textContent = `저장 못 함(${e.message || '연결 안 됨'})`; el.value = st.fee == null ? '' : String(st.fee); return; }
  st.fee = v; $('dt-fee-msg').textContent = v == null ? '빈칸 — 수수료 안 셈' : '저장됨 — 다시 셈';
  if (st.data) { paint(st.data); chips(); }
}
BIND.push(() => $('dt-fee').addEventListener('change', saveFee));
// 칩별 승률 — 화면 셈(11-24 재권님 「칩별 승률표도 서버정보를 바탕으로 내가 바꿔가면서 알고싶을때 알수있게 홈페이지에서 되야할거같은데」 · 「서버는 정보만 있고 셈은 화면에서 한다」)
//   지금 셈 칸 · 켜진 칩 · 매수 · 매도 룰 그대로 — 날마다 판(서버 정보)을 받아 calc 로 종목마다 세후 % → 칩마다 · 둘 · 셋 · 칩 개수로 묶음
//   종목은 판에 드는 줄(칩 N개 · 유통 거르기 · 매수가 있음)만 · 세후 % = 세후 손익 ÷ 산 돈 · 못 잼 = 매수가나 판 값이 없음 · 저장 안 해도 고친 그대로 셈
const WIN_DAYS = 30, WIN_BIG = 3, WIN_TOP = 5;   // 볼 거래일 · 「크게 이김」 % · 날마다 위 몇 종목 — 서버 표(dt30_win)와 같은 값
// 칩 조합 셈(11-26) — 굳힌 지난 판마다 종목이 처음 그 조합이 된 분 값에 샀다면 판 마지막 시각 값(보통 14:00)에 얼마 · 세금 · 수수료 빼기 전
//   조합이 된 분 값 — 09:01 이하면 9시 1분 값 · 그 뒤는 서버 칩 찬 분 1분봉(rows[].chipPx) · 1~5분 값 · 없으면 그 조합은 그 종목에서 셈 안 함(어림 안 함)
//   손절 · 익절을 넣은 셈은 1분봉이 판에 거의 없어 서버(개발2 · 「단타 판 칩 조합 셈 값」 카드)가 주면 씀 — 그 전은 「서버 값 기다림」
//   서버 조합 셈 값이 오면 이 화면 셈과 두 곳이 됨 — 그때 이 셈은 서버 값이 없는 판에서만 쓰고 이 줄에 「서버가 주면 안 씀」 을 적음(개념정의 덧 11-26)
// 칩 시각이 다 있나 — 켜진 칩 중 붙은 시각(구간 · chipTime · chipAt · VI 는 viAt)이 없는 칩이 하나라도 있으면 그 종목은 조합 셈에서 뺌
//   (11-26 재권님 「칩이 들어온 시간이 정확히 기입된게 있고 제대로 안된게 있는데 이거 고려되서 승률이 나온건가?」 → 「응 그렇게 다시해서」) — 시각 없는 칩을 판에 든 때로 치면 조합이 된 때가 앞당겨져 산 값이 틀림
const chipTimed = (r) => { const at = { ...(r.chipAt || {}), ...(r.chipTime || {}) }; return colsOf().filter((c) => everChip(r, c)).every((c) => NO_TIME_OK.includes(c) || (spanRow(r) && Array.isArray(r.chipSpans[c]) && r.chipSpans[c].length) || at[c] || (c === 'VI·급등' && r.viAt)); };
const comboPx = (r, t, ks) => { const v1 = (o) => (o && Number(o.px) > 0 ? Number(o.px) : null); if (t < minHM(1)) return v1(minVal(r, 1));
  const M = momentPx(r, t, ks, ks ? ks.length : 0); if (M) return M.px; const k = PMIN.find((n) => minHM(n) === t); return k ? v1(minVal(r, k)) : null; };
async function comboLoad(onStep) {
  const ds = st.days.slice().sort().reverse();
  const get = (d) => (st.data && st.data.day === d && st.data.closed !== true ? st.data : dayData[d]);
  const need = ds.filter((d) => get(d) === undefined); let k = 0;
  for (let i = 0; i < need.length; i += CB_FETCH) await Promise.all(need.slice(i, i + CB_FETCH).map(async (d) => { await dayGet(d); if (onStep) onStep(++k, need.length); }));   // 몇 개씩 나눠 받음 — 브라우저 연결 여섯 벽(롱폴 · 다른 칸)을 안 막게(개념정의 덧 11-26)
  const M = new Map(), used = []; let untimed = 0, rowsN = 0;
  ds.forEach((d) => { const D = get(d); if (!D || D.closed !== true) return; used.push(d); const keep = calcD; calcD = flat930(D);
    try { const T = D.times || [], last = T.length ? T[T.length - 1] : null;
      (D.rows || []).forEach((r) => { if (!colsOf().some((c) => everChip(r, c))) return; rowsN++; if (!chipTimed(r)) { untimed++; return; } const ex = last ? Number((r.px || {})[last]) : 0; if (!(ex > 0)) return; const seen = new Set();
        comboEvents(r).forEach(([t, cs]) => { if (!cs.length) return; subKeys(cs).forEach((key) => { if (seen.has(key)) return; seen.add(key); const p = comboPx(r, t, key.split(' + ')); if (!(p > 0)) return;   // 그 시각 붙은 칩의 부분 묶음마다 · 같은 조합은 처음 품은 때 한 번(11-26 품음)
          const o = M.get(key) || { key, n: key.split(' + ').length, cnt: 0, up: 0, sum: 0, days: new Set() }, ret = (ex / p - 1) * 100; o.cnt++; if (ret > 0) o.up++; o.sum += ret; o.days.add(d); M.set(key, o); }); }); }); }
    finally { calcD = keep; } });
  return { rows: [...M.values()].map((o) => ({ key: o.key, n: o.n, cnt: o.cnt, days: o.days.size, upPct: o.up / o.cnt * 100, avg: o.sum / o.cnt })), used, untimed, rowsN, sig: chipSig() };
}
const CB_API = '/api/kis/dt30-combo';   // 서버 조합 표(개발2)
const CB_FETCH = 3;   // 지난 판을 한 번에 받는 수
const CB_SHOW_MIN = 2, CB_SHOW_MAX = 80;   // 목록에 보일 조합 — 2건 이상(11-26 재권님 「건수가 2건이여도 승률이 높은건 적용되야 할거같은데」 · 고르기 문턱 기본도 2건) · 많아야 80줄(고른 조합은 늘 보임)
function comboPaint() {
  if (!root) return; const S = st.set, sel = comboSel();
  root.querySelectorAll('[data-buycombo]').forEach((b) => { b.classList.toggle('is-active', !!S.comboOn); });
  root.querySelectorAll('.dt-cbq-up').forEach((e) => { e.textContent = S.comboUp == null ? '( )' : String(S.comboUp); });
  const box = $('dt-cb'); if (!box) return;
  root.querySelectorAll('.dt-cb-n').forEach((e) => { e.textContent = String(sel.size); });
  root.querySelectorAll('.dt-cb-on').forEach((e) => { e.textContent = `${S.comboAuto !== false ? ' · 자동(문턱 넘는 조합)' : ' · 직접 고름'}${comboMode() ? ' · 조합으로 사는 중' : ''}${st.cbStat && st.cbStat.busy ? ' · 셈하는 중' : ''}`; });
  const C = st.cbStat; if (!C) return;
  if (C.busy) { box.textContent = `지난 판 받는 중… ${C.busy}`; return; }
  const up = S.comboUp == null ? Infinity : Number(S.comboUp), nn = S.comboN == null ? Infinity : Number(S.comboN);   // 빈칸 = 문턱 없음(옅은 빨강 안 칠함)
  const list = C.rows.filter((o) => sel.has(o.key) || o.cnt >= CB_SHOW_MIN).sort((a, b) => (sel.has(b.key) - sel.has(a.key)) || b.upPct - a.upPct || b.cnt - a.cnt).slice(0, Math.max(CB_SHOW_MAX, sel.size));
  const gone = [...sel].filter((k) => !C.rows.some((o) => o.key === k));   // 고른 조합인데 지난 판에 한 번도 없던 것(칩을 끄면 생김)
  box.innerHTML = `<label class="dt-fee"><input type="checkbox" data-cbon${S.comboOn ? ' checked' : ''}> 조합으로 사기 <span class="rl-sug">켜면 「칩 ( )개 이상」 대신 고른 조합이 된 때 삼 · 된 시각이 빠른 순 · 상위 종목 수 · 금액 · 파는 룰은 위 칸 그대로</span></label>
    <div class="dt-fee">오른 비율 <input data-cbset="comboUp" class="rl-in rl-num" inputmode="decimal" value="${esc(String(S.comboUp ?? ''))}" aria-label="오른 비율 몇 % 이상">% 이상 · <input data-cbset="comboN" class="rl-in rl-num" inputmode="numeric" value="${esc(String(S.comboN ?? ''))}" aria-label="몇 건 이상">건 이상 <button type="button" class="kh-chip${S.comboAuto !== false ? ' is-active' : ''}" data-cbpick>문턱 넘는 조합 고르기${S.comboAuto !== false ? '(자동)' : ''}</button> <button type="button" class="kh-chip" data-cbclear>다 빼기</button> <button type="button" class="kh-chip" data-cbredo>다시 셈</button> <span id="dt-cb-msg" class="rl-sug"></span></div>
    <span class="rl-sug">지난 판 ${C.used.length}날(${C.used.length ? `${dayTxt(C.used[C.used.length - 1])} ~ ${dayTxt(C.used[0])}` : '—'}) · 종목이 처음 그 조합이 된 분 값에 사서 판 마지막 시각 값에 판다고 셈 · 세금 · 수수료 빼기 전 · 켜진 칩만 · 장중 칩인데 붙은 시각이 없는 종목 ${num(C.untimed || 0)}건 뺌(전체 ${num(C.rowsN || 0)}건 · 자동 · 프리장 · 미국강세는 시각 없으면 장 전으로 봄) · 손절 · 익절 넣은 셈은 서버 값 기다림 · ${CB_SHOW_MIN}건 이상인 조합만 보임</span>
    ${gone.length ? `<span class="rl-sug">고른 조합 중 지난 판에 없는 것 — ${esc(gone.join(' · '))}</span>` : ''}
    <table class="st dt-cbt-tb"><thead><tr><th>고름</th><th>칩 수</th><th>오른 비율</th><th>조합</th><th>건수</th><th>날</th><th>평균</th></tr></thead><tbody>${list.map((o) => `<tr${o.upPct >= up && o.cnt >= nn ? ' class="dt-cb-ok"' : ''}><td><input type="checkbox" data-cb="${esc(o.key)}"${sel.has(o.key) ? ' checked' : ''} aria-label="${esc(o.key)} 고름"></td><td>${o.n}</td><td>${num(o.upPct, 0)}%</td><td class="dt-cbk">${esc(o.key)}</td><td>${num(o.cnt)}</td><td>${o.days}</td><td class="${signClass(o.avg, NUM) || ''}">${o.avg > 0 ? '+' : ''}${num(o.avg, 2)}%</td></tr>`).join('')}</tbody></table>`;
}
async function comboOpen(force) {
  if (st.cbStat && !st.cbStat.busy && !force && st.cbStat.sig === chipSig()) { comboPaint(); return; }
  st.cbStat = { busy: '…', rows: [], used: [] }; comboPaint();
  // 서버 조합 표(/api/kis/dt30-combo · 날마다 셈 · 개발2)를 먼저 — 켠 칩이 저장값과 같고 서버가 셈을 마쳤을 때만 · 아니면 화면 셈(서버가 주면 안 씀)
  try { const res = await fetch(CB_API, { cache: 'no-store' }), j = res.ok ? await res.json() : null, M = (j && j.meta) || {}, D = (j && (j.data || j)) || {};
    if (Array.isArray(D.rows) && D.rows.length && !M.busy && chipsSaved()) {
      st.cbStat = { rows: D.rows.map((o) => ({ key: (o.chips || String(o.key).split(' + ')).map(chipName).join(' + '), n: o.n, cnt: o.cnt, days: o.days, upPct: o.upPct, avg: o.avg })), used: D.used || [], untimed: D.untimed, rowsN: D.rowsN, sig: chipSig(), server: M.at || true };
      comboPaint(); if (st.data) paint(st.data); return; } } catch (e) { /* 서버 표 못 받음 — 화면 셈 */ }
  const C = await comboLoad((k, n) => { if (st.cbStat && st.cbStat.busy) { st.cbStat.busy = `(${k}/${n})`; comboPaint(); } });
  st.cbStat = C; comboPaint(); if (st.data) paint(st.data);   // 이름 빨강이 셈 뒤에 바로(11-26)
}
BIND.push(() => { const b = $('dt-pnl'); if (b) b.addEventListener('click', (e) => { if (!e.target.closest('[data-buycombo]')) return; e.preventDefault(); if (!st.set.comboOn) setChange({ ...st.set, comboOn: true }); }); });   // 매수 셋째 칸 「승률 ( )% 칩이 찰 때」 — 조합으로 사기(11-26 재권님 「매수가 9시1~5분에 든종목 / 칩이찰때 / 승률칩이찰때 이렇게 있으면 좋을거같은데」 · 앞선 「승률 칩조합」 단추를 여기로 옮김)
BIND.push(() => {
  const d = $('dt-cbf'); if (!d) return;
  d.addEventListener('toggle', () => { if (d.open) comboOpen(); });
  d.addEventListener('change', (e) => {
    const c = e.target.closest('[data-cb]'); if (c) { const A = new Set(comboSel()); if (c.checked) A.add(c.dataset.cb); else A.delete(c.dataset.cb); setChange({ ...st.set, comboAuto: false, combos: [...A] }); return; }   // 손으로 넣고 빼면 직접 고름
    if (e.target.closest('[data-cbon]')) { setChange({ ...st.set, comboOn: !!e.target.checked }); return; }
    const v = e.target.closest('[data-cbset]'); if (v) { const x = v.value.trim() === '' ? null : Number(v.value); if (x != null && (!Number.isFinite(x) || x < 0)) { v.value = String(st.set[v.dataset.cbset] ?? ''); return; } setChange({ ...st.set, [v.dataset.cbset]: x }); }
  });
  d.addEventListener('click', (e) => {
    if (e.target.closest('[data-cbpick]')) { e.preventDefault(); const C = st.cbStat; if (!C || C.busy) return; if (st.set.comboUp == null || st.set.comboN == null) { const m = $('dt-cb-msg'); if (m) m.textContent = '오른 비율 · 건수 칸이 비어 있어 고르지 않음 — 둘 다 넣으십시오'; return; }   /* 빈칸을 0 으로 셈하면 전부 골라짐(개념정의 덧 11-26) */ setChange({ ...st.set, comboAuto: true }); return; }   // 다시 자동 — 문턱 넘는 조합 전부(셈이 바뀌면 따라감)
    if (e.target.closest('[data-cbclear]')) { e.preventDefault(); setChange({ ...st.set, comboAuto: false, combos: [], comboOn: false }); return; }
    if (e.target.closest('[data-cbredo]')) { e.preventDefault(); comboOpen(true); }
  });
});
async function winLocal(onStep) {
  const ds = st.days.slice().sort().reverse().slice(0, WIN_DAYS);
  const get = (d) => (st.data && st.data.day === d && st.data.closed !== true ? st.data : dayData[d]);
  const need = ds.filter((d) => get(d) === undefined); let k = 0;
  await Promise.all(need.map(async (d) => { await dayGet(d); if (onStep) onStep(++k, need.length); }));
  const all = [];
  ds.forEach((d) => { const D = get(d); if (!D) return; const C = calc(D), keep = calcD; calcD = flat930(D);
    try { C.R.forEach((x) => { const r = x.r, cs = colsOf().filter((c) => everChip(r, c)), ret = x.pnl && x.pnl.net != null && x.pnl.buyAmt > 0 ? x.pnl.net / x.pnl.buyAmt * 100 : null;
      all.push({ day: d, name: r.name, chips: cs, n: cs.length, rise: (r.chips || []).includes('현재상승'), ret }); }); } finally { calcD = keep; } });
  const stat = (v) => { const m = v.filter((x) => x.ret != null).map((x) => x.ret).sort((a, b) => a - b), w = m.filter((x) => x > 0).length;
    return { n: m.length, win: w, winRate: m.length ? w / m.length * 100 : null, avg: mean(m), median: m.length ? (m.length % 2 ? m[(m.length - 1) / 2] : (m[m.length / 2 - 1] + m[m.length / 2]) / 2) : null, over3: m.filter((x) => x > WIN_BIG).length, unmeasured: v.length - m.length }; };
  const grp = (keyOf, src = all) => { const G = new Map(); src.forEach((x) => keyOf(x).forEach((k) => { if (!G.has(k)) G.set(k, []); G.get(k).push(x); }));
    return [...G].map(([key, v]) => ({ key, ...stat(v) })).sort((a, b) => b.n - a.n || String(a.key).localeCompare(String(b.key))); };
  const combo = (cs, m) => { const out = []; const go = (i, pick) => { if (pick.length === m) { out.push(pick.join(' + ')); return; } for (let j = i; j < cs.length; j++) go(j + 1, [...pick, cs[j]]); }; go(0, []); return out; };
  const S = st.set, days = ds.filter((d) => get(d)).map((d) => { const v = all.filter((x) => x.day === d); return { day: d, ...stat(v), top: v.filter((x) => x.ret != null).sort((a, b) => b.ret - a.ret).slice(0, WIN_TOP).map((x) => ({ name: x.name, ret: x.ret })) }; });
  return { data: { all: stat(all), chip: grp((x) => x.chips), pair: grp((x) => combo(x.chips, 2)), triple: grp((x) => combo(x.chips, 3)), count: grp((x) => [x.n]), countRise: grp((x) => [x.n], all.filter((x) => x.rise)), days },
    meta: { local: true, from: ds[ds.length - 1], to: ds[0], days: days.length, openDay: ds.find((d) => { const D = get(d); return D && D.closed === false; }) || null, miss: ds.length - days.length, bigPct: WIN_BIG, topDay: WIN_TOP, fee: st.fee, minChips: Number(S.minChip) || 0, sell: S.endAt ? String(S.endAt).replace(':', '') : '1400', rules: winRules(ds.filter((d) => get(d))) } };
}
// 승률 표 머리에 적는 「셈한 룰」(11-24 재권님 「셈을 한 룰을 승률표에서 확인할수 있도록 해줘」) — 셈 칸 · 칩 켜고 끄기 값을 그대로 [묶음, [[이름, 값] …]] 으로 · 값은 st.set 한 곳에서 읽기만(따로 두지 않음)
function winRules(days) {   // days — 승률 표가 셈한 날(코스피 값 없는 날 수를 그 날들로 셈 · 11-24 개념정의 덧)
  const S = st.set || {}, v = (x, u = '') => (x == null || x === '' ? '( )' : `${x}${u}`), on = (b) => (b ? '켬' : '끔');
  const cs = colsOf(), onC = cs.filter((c) => !st.off.has(c)), offC = cs.filter((c) => st.off.has(c)), subOff = [...st.subOff].map((k) => k.replace('|', ' 〉 '));
  const tb = S.turnBy || 'both', turn = !S.turn ? '끔' : [tb !== 'peak' ? `앞 시각보다 ${v(S.turnPct, '%')} 넘게 내리면` : '', tb !== 'prev' ? `고점보다 ${v(S.trail, '%')} 내리면` : ''].filter(Boolean).join(' · ');
  const ord = ORD_KEYS.filter(([k]) => (S.ordScore || {})[k]).map(([k, t]) => `${t} ${S.ordScore[k]}점`).join(' · ');
  return [
    ['칩', [['켜진 칩', onC.join(' · ') || '없음'], ['꺼 둔 칩', [...offC, ...subOff].join(' · ') || '없음']]],
    ['종목 차례', [['점수', ord || '빈칸(칩 수 → 초반상승 → 시가총액)']]],
    ['매수', [['칩 개수', S.minChip ? `${S.minChip}개 이상` : '전체'], ['칩 모자라면', !(S.fill && S.minChip > 1) ? '채우지 않음' : S.top ? `채움(상위 ${S.top}종목이 안 되면 칩 ${S.minChip - 1}개 종목으로)` : '안 채움(상위 종목 수 빔)'], ['상승률 순위', S.riseRank !== false ? '켬(09:05 까지 1분 값 높은 순)' : '끔(단타 순)'], ['09:30 뒤에 찬 종목', S.buyLate930 ? '삼' : '안 삼'],
    ['유통 대비 거래', S.turnOn && S.turnMin > 0 ? `${S.turnMin}% 이상 · 못 잰 종목 뺌` : S.turnOn ? '안 거름(% 빔)' : '끔'], ['전일 거래량 대비 지금 거래량(프리장 빠짐)', S.volOn && S.volMin > 0 ? `${S.volMin}% 이상 · ${hmTxt(volFrom())} 부터` : S.volOn ? '안 거름(% 빔)' : '끔'],
    ['매수', (() => { const B = BUYS.find(([k]) => k === buyKey()); return B ? buyName(B[0], B[1]) : '( )'; })()], ['불타기', on(S.pyr)]]],
    ['매도', [['매도 봉', S.sellBar === '1m' ? '1분' : S.sellBar === '5m' ? '5분' : '30분'], ['손절', S.stop == null || S.stop === '' ? '안 함' : `${S.stop}%`],
    ['꺾임', turn], ['시각 미달', S.cut ? `산 뒤 ${v(S.cutMin, '분')} · ${v(S.cutPct, '%')} 못 넘으면 팜` : '끔'],
    ['횡보', S.flat ? `산 뒤 ${v(S.flatMin, '분')} · ${v(S.flatPct, '%')} 안쪽이면 팜` : '끔'], ['매도 시각', S.endAt ? hmTxt(S.endAt) : '판 끝 칸'],
    ['증권수수료', st.fee == null ? '안 셈' : `${st.fee}%`]]],
    ['코스피 조건 매도 줄', ['up', 'dn'].map((sd) => { const L = (S.mk || {})[sd] || {}, ok = mkUse(L);
      return [sd === 'up' ? '상승 줄' : '하락 줄', !ok ? '안 씀' : `${{ prev: '전일', high: '고가', low: '저가' }[L.ref] || '시가'} 대비 ${L.pct}% ${sd === 'up' ? '이상' : '이하'} → 매도 봉 ${{ '1m': '1분', '5m': '5분', '30m': '30분' }[L.sellBar || S.sellBar] || '30분'} · 손절 ${L.stop == null || L.stop === '' ? '안 함' : `${L.stop}%`}`]; })
      .concat(mkOn() ? [['코스피 값', !KX.bars ? '못 받음 — 모든 날 맨 윗줄로 셈' : Array.isArray(days) ? `이번 셈 ${num(days.length)}일 중 코스피 값 없는 날 ${num(days.filter((d) => !mkHas(d)).length)}일(그 날은 맨 윗줄)` : '그 날 값 없으면 맨 윗줄']] : [])],
  ];
}
BIND.push(() => bindWin($('dt-win'), winLocal));
BIND.push(() => mountSector($('dt-sf')));
WIDE.addEventListener('change', () => { if (root && st.data) paint(st.data); });   // 창 폭이 700 을 넘나들면 칸 차례만 다시


// 그릇에 그리기 (11-13 재권님 「단타 창 모달로 띄울수있게 자세히 버튼 넣어줘」 · 개발1 과 맞춤 · 같은 날 재권님이 홈 모달은 거두심 「홈 모달말고 단타 창에서 모달로 바로」) — 지금은 투자 전략 화면(#dt-host)만 쓴다 · 다른 자리에서 띄울 때 이 한 벌을 가져다 쓴다
//   mountDt30(host)  host 안에 판 칸을 만들고 그림 · 칸은 host 안에서만 찾는다 · 모양은 company-setup/css/strategy.css 의 .dt 묶음(거는 쪽이 그 파일을 건다)
//   unmountDt30()    다시 받기 타이머 · 열린 칸 메뉴를 거둠 — 모달을 닫을 때 부른다(안 부르면 장중 주기로 계속 받는다)
//   host 에 class 「st dt」 가 없으면 붙인다(.dt 아래 모양이 듣게)
// 종목 차례 점수 기준 — 칩 수는 점수표가 있으면 점수 합(11-23 재권님 (가))
const ORD_KEYS = [['chips', '칩 수(점수)'], ['rise', '초반상승 %'], ['cap', '시가총액'], ['floatCap', '풀린 시총'], ['turn', '거래 비율'], ['turnPrev', '전날 같은 시각 대비'], ['pre', '오늘 프리장 %']];
// 섹터 · 테마 칸 — 판에 든 종목(셈 칸 · 켜진 칩 · 유통 거르기 뒤)을 섹터 · 테마로 묶음(11-24 재권님 「칩에 걸린 종목들중에 같은 섹터를 구분할수 있나 · 섹터와 테마를 둘다 보고싶네」 → 자리 (가) 「커밋해」)
//   섹터 = 판 줄 sector(서버 · 네이버 WICS) · 테마 = 판 줄 themes(종목이 든 네이버 테마 번호 — 서버 개발2 몫 · 없으면 「서버 값 못 받음」) · 테마 이름 · 큰 테마 = /api/nxt/themes(실시간 순위 「테마」 와 같은 묶음)
//   줄을 누르면 본 표가 그 묶음 종목만(st.grp) · 다시 누르면 풂 · 셈은 화면 · 「기타」(밸류업 · 지주사 같은 묶음 테마)는 같은 종류끼리 묶은 것이 아니라 뺌
let grpOn = false;   // 섹터 · 테마 거름을 걸 셈인가 — 그날 본 표를 그릴 때만 참
const TH = { map: null, busy: false };   // 테마 번호 → {name, big}
async function thLoad() {
  if (TH.map || TH.busy) return; TH.busy = true;
  try { const r = await fetch('/api/nxt/themes', { cache: 'no-store' }); const j = r.ok ? await r.json() : null; const m = new Map();
    ((j && j.data && j.data.groups) || []).forEach((g) => (g.themes || []).forEach((t) => m.set(Number(t.no), { name: t.name, big: g.name }))); TH.map = m; } catch (e) { TH.map = null; }
  TH.busy = false; if (st.data) stPaint((calc(st.data).rowsF) || []);
}
const thOf = (r) => (Array.isArray(r.themes) ? r.themes : []).map((n) => TH.map && TH.map.get(Number(n))).filter((t) => t && t.big !== '기타');
const grpHas = (r, g) => (g.k === 'sec' ? (r.sector || '섹터 모름') === g.v : g.k === 'big' ? thOf(r).some((t) => t.big === g.v) : thOf(r).some((t) => t.name === g.v));
function stPaint(rows) {
  const box = root && root.querySelector('#dt-st'); if (!box) return;
  const sum = box.querySelector('.dt-st-sum'), body = box.querySelector('.dw-body');
  const grp = (keyOf) => { const G = new Map(); rows.forEach((r) => keyOf(r).forEach((k) => { if (!G.has(k)) G.set(k, []); G.get(k).push(r); }));
    const mean = (v) => { const xs = v.filter((r) => r.pct != null).map((r) => Number(r.pct)).filter(Number.isFinite); return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null; };
    return [...G].map(([k, v]) => ({ k, v: [...v].sort((a, b) => { const x = Number(a.pct), y = Number(b.pct), fx = a.pct != null && Number.isFinite(x), fy = b.pct != null && Number.isFinite(y); return fx && fy ? y - x : fx ? -1 : fy ? 1 : 0; }), avg: mean(v) })).sort((a, b) => b.v.length - a.v.length || (b.avg ?? -1e9) - (a.avg ?? -1e9)); };
  const sec = grp((r) => [r.sector || '섹터 모름']);
  const hasTh = rows.some((r) => Array.isArray(r.themes));
  const sm = hasTh && TH.map ? grp((r) => [...new Set(thOf(r).map((t) => t.name))]) : [];
  const big = hasTh && TH.map ? grp((r) => [...new Set(thOf(r).map((t) => t.big))]) : [];
  const bigOf = (name) => { for (const t of (TH.map ? TH.map.values() : [])) if (t.name === name) return t.big; return ''; };
  const on = (k, v) => st.grp && st.grp.k === k && st.grp.v === v;
  const names = (v) => v.slice(0, 3).map((r) => `${esc(r.name)} ${pct(r.pct == null ? null : Number(r.pct))}`).join(' · ') + (v.length > 3 ? ' …' : '');
  const tr = (k, g, extra = '') => `<tr class="dt-st-row${on(k, g.k) ? ' is-active' : ''}" data-stg="${k}" data-stv="${esc(g.k)}"><td class="dw-l">${esc(g.k)}</td>${extra}<td>${num(g.v.length)}</td><td>${pct(g.avg)}</td><td class="dw-l dw-top">${names(g.v)}</td></tr>`;
  const thBox = !hasTh ? '<div class="st-err">종목별 테마 — 서버 값 못 받음(판 줄에 테마 번호가 아직 없음 · 개발2)</div>'
    : !TH.map ? `<div class="st-err">테마 이름 — ${TH.busy ? '받는 중' : '못 받음'}</div>`
    : `<div class="dt-seg dt-st-big">${big.map((g) => `<button type="button" class="kh-chip${on('big', g.k) ? ' is-active' : ''}" data-stg="big" data-stv="${esc(g.k)}">${esc(g.k)} ${num(g.v.length)}</button>`).join('')}</div>
       <table class="dw-tb"><thead><tr><th class="dw-l">작은 테마</th><th class="dw-l">큰 테마</th><th>종목</th><th>평균 등락</th><th class="dw-l">종목(많이 오른 순)</th></tr></thead><tbody>${(() => { const L = sm.filter((g) => !(st.grp && st.grp.k === 'big') || bigOf(g.k) === st.grp.v), K = 12, sh = L.slice(0, K).concat(st.grp && st.grp.k === 'th' && L.findIndex((g) => g.k === st.grp.v) >= K ? L.filter((g) => g.k === st.grp.v) : []); return sh.map((g) => tr('th', g, `<td class="dw-l">${esc(bigOf(g.k))}</td>`)).join('') + (L.length > K ? `<tr><td class="dw-l rl-sug" colspan="5">… 외 작은 테마 ${num(L.length - K)}개(종목 수 적은 것) — 큰 테마 단추로 좁혀 보기</td></tr>` : ''); })() || '<tr><td class="dw-l st-err" colspan="5">—</td></tr>'}</tbody></table>`;
  if (sum) sum.textContent = `${num(rows.length)}종목 · 섹터 ${num(sec.length)}${hasTh && TH.map ? ` · 큰 테마 ${num(big.length)}` : ''}${st.grp ? ` · 거름: ${st.grp.v}` : ''}`;
  body.innerHTML = `<div class="st-cap">판에 든 종목(셈 칸 · 켜진 칩 · 유통 거르기 뒤)을 섹터 · 테마로 묶음 · 줄을 누르면 아래 본 표가 그 종목만 · 다시 누르면 풂${st.grp ? ` · <button type="button" class="kh-chip" data-stg="" data-stv="">거름 풀기 — ${esc(st.grp.v)}</button>` : ''} · 평균 등락 = 오늘 등락률 · 셈은 화면 · 테마 「기타」(밸류업 · 지주사 같은 묶음 테마)는 뺌</div>
    <div class="dt-st-grid">
      <div><b>섹터</b> <span class="rl-sug">네이버 WICS · 종목 하나에 섹터 하나</span><table class="dw-tb"><thead><tr><th class="dw-l">섹터</th><th>종목</th><th>평균 등락</th><th class="dw-l">종목(많이 오른 순)</th></tr></thead><tbody>${sec.map((g) => tr('sec', g)).join('') || '<tr><td class="dw-l st-err" colspan="4">—</td></tr>'}</tbody></table></div>
      <div><b>테마</b> <span class="rl-sug">네이버 테마 · 종목 하나가 여러 테마에 듦</span>${thBox}</div>
    </div>`;
  if (hasTh && !TH.map && !TH.busy) thLoad();
}
BIND.push(() => { const el = $('dt-box'); if (el) el.addEventListener('change', (e) => { const c = e.target.closest('[data-riserank]'); if (!c) return; setChange({ ...st.set, riseRank: !!c.checked }); }); });   // 상승률 순위 켜고 끄기(11-24)
BIND.push(() => { const el = $('dt-st'); if (el) el.addEventListener('click', (e) => { const b = e.target.closest('[data-stg]'); if (!b) return; const k = b.dataset.stg, v = b.dataset.stv;
  st.grp = !k || (st.grp && st.grp.k === k && st.grp.v === v) ? null : { k, v }; if (st.data) { paint(st.data); chips(); } }); });

const TPL = `
      <div class="st-meta" id="dt-meta">값을 받는 중…</div>
      <h2 class="st-sec">단타 — <span class="dt-at">—</span> 매수 → 30분마다 14:00 까지</h2>
      <div class="st-tg dt-days" id="dt-days" role="tablist" aria-label="날짜"></div>
      <div class="st-card">
        <div class="st-cap dt-cap" id="dt-cap">단타 목록(<span class="dt-at">—</span> 에 연 <span class="dt-min">후보</span> · 아래 칩을 켜고 끄면 겹친 수로 다시 줄 세움)을 그 시각 값에 산 것으로 보고, 매수가 대비 몇 % 인지 30분마다 · 날마다 쌓음 · 30거래일</div>
        <!-- 칩 영역 두 줄 (11-11 재권님 「여기 계층구조에 맞게 인지가 잘되고 보기 편하게 색도 넣어서 해줘」) — ① 단타 칩: 표 안 종목 머리 줄과 평균 줄 사이(js 가 그림) · 상위 칩마다 색 · 하위 칩은 같은 색 작은 칩으로 붙임 ② 보기: 거르기 · 줄 세우기는 회색 나눔 단추 -->
        <div class="dt-ctl">
          <div class="dt-row"><span class="dt-hd">보기</span><div class="dt-bar"><span class="dt-lb">거르기</span><div class="dt-seg" id="dt-only" role="tablist" aria-label="이벤트 거르기"></div><span class="dt-lb">줄 세우기</span><div class="dt-seg" id="dt-order" role="tablist" aria-label="줄 세우기"></div></div></div>
        </div>
        <div class="dt-pnl" id="dt-pnl"><div id="dt-pnl-sum">—</div>
          <!-- 셈 칸 — 매수 · 매도 좌우 두 칸(11-20 재권님 「매수 매도를 나눠서 좌우로 칸 나눠줄래?」 → 그림에 「응 맞아」) · 스타일은 이 칸에만 인라인(strategy.css 에 남의 미커밋이 있음) -->
          <details class="dt-setf" id="dt-setf" open><summary class="dt-cap">셈 칸 — 종목 차례 점수 · 매수 · 매도 <small>(누르면 접기 · 펴기)</small></summary>
          <div class="dt-set" id="dt-set" aria-label="셈 칸 — 고치면 화면만 다시 셈 · 「저장」 을 눌러야 남음">
            <div style="display:flex;justify-content:flex-end;align-items:baseline;gap:8px"><span id="dt-set-msg" class="rl-sug"></span> <button type="button" class="kh-chip" data-setsave>저장</button> <button type="button" class="kh-chip" data-reset>기본값으로</button></div>
            <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:stretch;margin:4px 0">
              <!-- 종목 차례 칸 — 매수 왼쪽(11-23 재권님 「단타 창의 매수 왼쪽에 그 룰을 적어주고 내가 수정하면 거기에 맞게 종목순위 바뀌게 해야할거같아」 → 「이거를 옆에 점수로 넣을수 있게하고 점수가 높은게 순위가 높게 해줘」 → (가))
                   기준마다 판 안 순위를 0~1(1등 1 · 꼴찌 0 · 값 없음 0)로 바꿔 넣은 점수를 곱해 합한 값이 높은 종목이 위 · 다 빈칸이면 지금 차례 · 셈은 서버(개발2) · 저장 열쇠는 개발2 가 정함 -->
              <div class="dt-set-ord" style="flex:0 1 440px;min-width:0;word-break:keep-all;display:flex;flex-direction:column;gap:4px;padding:8px 12px;border-radius:var(--kh-radius-sm);background:var(--kh-bg-card)"><b style="font-size:12px">종목 차례 점수 <span class="rl-sug">합이 높은 종목이 위</span></b>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:2px 12px">${ORD_KEYS.map(([k, t]) => `<label class="dt-fee" style="display:flex;justify-content:space-between;gap:6px">${t} <span><input data-set="ord:${k}" class="rl-in rl-num" inputmode="decimal" placeholder="( )" aria-label="${t} 점수">점</span></label>`).join('')}</div>
                <span class="rl-sug">기준마다 판 안 1등 = 점수 그대로 · 꼴찌 = 0 · 다 빈칸 = 지금 차례(칩 수 → 초반상승 → 시가총액)</span>
              </div>
              <div class="dt-set-buy" style="flex:1 1 360px;min-width:0;word-break:keep-all;display:flex;flex-direction:column;gap:4px;padding:8px 12px;border-radius:var(--kh-radius-sm);background:var(--kh-bg-card)"><b style="font-size:12px">매수</b>
                <label class="dt-fee">칩 <input data-set="minChip" class="rl-in rl-num" inputmode="numeric" aria-label="칩 몇 개 이상만">개 이상 <span class="rl-sug">빈칸 = 전체</span></label>
                <!-- 칩 조합(11-26 재권님 「칩선택에서 지금은 개수만 있어서 조합을 만들수가 없어서 …」 → 「응 해」) — 펴면 지난 판 전부로 조합마다 셈 · 고른 조합이 된 종목은 이름 빨강 · 「조합으로 사기」 를 켜면 칩 개수 대신 조합으로 삼 -->
                <details class="dt-win dt-cbf" id="dt-cbf"><summary>칩 조합 — 고른 조합 <span class="dt-cb-n">0</span>개<span class="dt-cb-on"></span> <small>(판을 열면 지난 판으로 셈 · 펴면 목록)</small></summary><div class="dw-body" id="dt-cb">—</div></details>
                <label class="dt-fee" data-tip="칩 N개 종목을 먼저 사고, 모자란 만큼 칩 하나 적은 종목을 그 칩이 찬 시각별로 더합니다 · 그래도 모자라면 거기까지(두 개 적은 것으로는 안 내려감) · 채우지 않음이면 칩 N개 종목만 · 저장 단추로 남김">칩 (<span class="dt-fill-n">—</span>)개 찬 종목이 상위 (<span class="dt-top-n">—</span>)종목이 안 되면 칩 (<span class="dt-fill-m">—</span>)개 종목으로 <span class="dt-seg"><button type="button" class="kh-chip" data-fill="1">채움</button><button type="button" class="kh-chip" data-fill="0">채우지 않음</button></span></label>
                <label class="dt-fee" data-tip="칩 수가 09:30 뒤에 찬 종목(판 아래 「09:30 뒤에 찬 종목」 묶음)을 살지 정합니다 · 안 삼이면 그 줄은 판에 남고 손익 셈에서 빠집니다 · 저장 단추로 남김">09:30 뒤에 찬 종목 <span class="dt-seg"><button type="button" class="kh-chip" data-late="1">삼</button><button type="button" class="kh-chip" data-late="0">안 삼</button></span></label>
                <label class="dt-fee" data-tip="고른 때 값에 삽니다 · 그 값이 없는 종목은 안 삽니다 · 파는 룰은 산 뒤 30분 칸(09:30 · 10:00 …)부터">매수 <span class="dt-seg">${BUYS.map(([k, t]) => `<button type="button" class="kh-chip" data-buy="${k}">${t}</button>`).join('')}<button type="button" class="kh-chip" data-buycombo>칩조합</button></span></label>
                <label class="dt-fee" data-tip="손절로 판 돈을 그 시각 가장 많이 오른 종목에 더 삽니다 · 더 산 몫은 그 종목을 팔 때 함께 팝니다">불타기 <span class="dt-seg"><button type="button" class="kh-chip" data-pyr="1">켬</button><button type="button" class="kh-chip" data-pyr="0">끔</button></span></label>
                <!-- 매수 메시지 보내기 칸(sendFrom · sendN)은 11-24 걷음 — 재권님 「가」(새 매수 룰이 돌면 없애고 사는 종목 수는 「칩 모자라면 채움」 칸 하나) · 서버 e07cd5e 가 더는 안 읽음 -->
                <!-- 매수 룰 정의(11-24 재권님 「이거 추가해서 다 정리하고 정리한거 단타에다가 매수룰정의에 넣어줘 접기로해서」 → 「매수룰을 여기안에 접기로 넣어줄래? 언제든 수정가능하도록 대비해놓」) — 정한 룰 글 · 칩 수는 위 칸 값(minChip)을 글로만 · 사는 종목 수는 상위 ( )종목 칸(top)을 글로만 · ( ) 칸은 셈 칸 값과 같은 열쇠(turnMin)라 어디서 바꿔도 같음 · 기준 시각(set.ruleMin · 여는 시각 + 분)만 새 열쇠 · 판 셈 · 서버는 아직 이 룰대로 안 돎 · 3번 다음 상위 — 재권님 「상승률이 우선이고 유통대비거래는 조건이야」 -->
                <details class="dt-win dt-buydef" id="dt-buydef"><summary>매수 룰 정의 (11-24 정함)</summary><div class="dw-body dt-rdef"><ol>
                  <li><b>기준 시각</b> — 여는 시각 + <input data-set="ruleMin" class="rl-in rl-num dt-send-in" inputmode="numeric" placeholder="( )" aria-label="기준 시각 — 여는 시각 몇 분 뒤">분 · ${RULE_MIN_LO}~${RULE_MIN_HI}분 · 빈칸 = ${RULE_MIN_DEF}분(보통 날 09:05) · 늦게 연 날은 여는 시각부터 세어 저절로 밀림</li>
                  <li><b>기준 시각 전</b> — 칩 (<span class="dt-send-n">—</span>)개가 찬 순간 삼 <span class="rl-sug">위 「칩 ( )개 이상」 값</span> · 서버에 알리고 텔레그램 「○○ 매수하세요」 가 바로 감 · 판에는 찬 순서대로 위에서부터</li>
                  <li><b>기준 시각에</b> — 찬 종목이 상위 (<span class="dt-top-n">—</span>)종목에 모자라면 칩이 하나 모자란 종목 중 다음 상위로 채워 그 시각에 삼 · 텔레그램 · 2번 종목 바로 아래<br>다음 상위 — 유통 대비 거래 <input data-set="turnMin" class="rl-in rl-num dt-send-in" inputmode="decimal" placeholder="( )" aria-label="유통 대비 거래 몇 %">% 이상은 조건(넘은 종목만) · 그 안에서 상승률 높은 순 · 같으면 칩 개수 많은 순</li>
                  <li><b>기준 시각 뒤에 찬 종목</b> — 사지 않음 · 텔레그램 안 감</li>
                  <li><b>산 뒤</b> — 순위는 그대로 · 더 붙은 칩은 배지에 「+n」 으로 따로</li>
                  <li><b>서버에 보내는 룰</b> — 기준 시각 · 칩 개수 · 사는 종목 수 · 유통 대비 거래 % · 사는 종목 수는 「총 ( )만원 ÷ 상위 ( )종목」 칸 하나 — 채움도 텔레그램도 그 상위 N 까지(채움 칸 종목 수는 걷음 · 11-24 재권님 「가 상위종목에 지정된 숫자에서 부족한 숫자만큼」) · 「매수 메시지 보내기」 칸은 없앰(11-24 재권님 「가」) · 텔레그램은 위에서 차례대로 상위 N 까지만 감(11-24 재권님 「위에서 순서대로 지정된 숫자만」 · 서버 60258ff)</li>
                  <li><b>전일 거래량 대비</b> — 화면 보기에만 · 서버에 안 보냄 · 장 시작 25분 뒤(보통 09:25)부터 걸려, 기준 시각이 그 앞이면 매수에는 안 걸림</li>
                  <li><b>보기 둘</b> — 서버 순위(실제로 보낸 차례 · 화면 체크로 안 바뀜) / 내 화면 체크(지금 켠 칩 · 거르기로 다시 셈)</li>
                </ol><div class="rl-sug">칩 수는 위 「칩 ( )개 이상」 을 가져다 씀 · 종목 수 · 유통 대비 거래 칸은 위 셈 칸 · 종목 머리 칸과 같은 값 — 어디서 바꿔도 함께 바뀜 · 저장 단추로 남김 · 지금 상태 — 정의만 적었음 · 서버 텔레그램은 이 룰대로 보냄(개발2 · 8765 재시작 뒤) · 판 셈은 아직 이 룰대로 돌지 않음(화면 시황분석1 만드는 중)</div></div></details>
              </div>
              <div class="dt-set-sell" style="flex:2 1 360px;min-width:0;word-break:keep-all;display:flex;flex-direction:column;gap:4px;padding:8px 12px;border-radius:var(--kh-radius-sm);background:var(--kh-bg-card)"><div style="display:flex;align-items:center;gap:8px"><b style="font-size:12px">매도</b><button type="button" class="kh-chip" data-setsave>저장</button></div>
                <div class="dt-mkrow"><b class="dt-mkh">조건 맞기 전 · 안 맞을 때</b><label class="dt-fee" data-tip="손절 · 고점 · 꺾임 · 시각 미달 · 횡보 · 매도 시각을 어느 봉으로 볼지 · 산 시각이 든 봉은 빼고 다음 봉부터 · 봉이 없는 줄은 30분 칸 · 저장 단추로 남김">매도 봉 <span class="dt-seg"><button type="button" class="kh-chip" data-sbar="1m">1분</button><button type="button" class="kh-chip" data-sbar="5m">5분</button><button type="button" class="kh-chip" data-sbar="30m">30분</button></span></label> <label class="dt-fee">손절 <input data-set="stop" class="rl-in rl-num" inputmode="decimal" aria-label="손절(매수가 대비 %)">% <span class="rl-sug">빈칸 = 안 함</span></label></div><div class="dt-mkrow" data-mkside="up"><label class="dt-mkon"><input type="checkbox" data-mkon="up" aria-label="코스피 상승 줄 적용"></label><span class="dt-mkh dt-fee">코스피가 <span class="dt-seg"><button type="button" class="kh-chip" data-mkref="up:prev">전일</button><button type="button" class="kh-chip" data-mkref="up:open">시가</button><button type="button" class="kh-chip" data-mkref="up:high">고가</button><button type="button" class="kh-chip" data-mkref="up:low">저가</button></span>보다 <input data-set="mk:up:pct" class="rl-in rl-num" inputmode="decimal" placeholder="( )" aria-label="코스피 조건 — 기준 대비 %">% 이상 상승일 때</span><label class="dt-fee">매도 봉 <span class="dt-seg"><button type="button" class="kh-chip" data-mksbar="up:1m">1분</button><button type="button" class="kh-chip" data-mksbar="up:5m">5분</button><button type="button" class="kh-chip" data-mksbar="up:30m">30분</button></span></label> <label class="dt-fee">손절 <input data-set="mk:up:stop" class="rl-in rl-num" inputmode="decimal" aria-label="코스피 조건 줄 손절(매수가 대비 %)">% <span class="rl-sug">빈칸 = 안 함</span></label></div><div class="dt-mkrow" data-mkside="dn"><label class="dt-mkon"><input type="checkbox" data-mkon="dn" aria-label="코스피 하락 줄 적용"></label><span class="dt-mkh dt-fee">코스피가 <span class="dt-seg"><button type="button" class="kh-chip" data-mkref="dn:prev">전일</button><button type="button" class="kh-chip" data-mkref="dn:open">시가</button><button type="button" class="kh-chip" data-mkref="dn:high">고가</button><button type="button" class="kh-chip" data-mkref="dn:low">저가</button></span>보다 <input data-set="mk:dn:pct" class="rl-in rl-num" inputmode="decimal" placeholder="( )" aria-label="코스피 조건 — 기준 대비 %">% 이하 하락일 때</span><label class="dt-fee">매도 봉 <span class="dt-seg"><button type="button" class="kh-chip" data-mksbar="dn:1m">1분</button><button type="button" class="kh-chip" data-mksbar="dn:5m">5분</button><button type="button" class="kh-chip" data-mksbar="dn:30m">30분</button></span></label> <label class="dt-fee">손절 <input data-set="mk:dn:stop" class="rl-in rl-num" inputmode="decimal" aria-label="코스피 조건 줄 손절(매수가 대비 %)">% <span class="rl-sug">빈칸 = 안 함</span></label></div><div class="rl-sug dt-mknote">코스피 5분봉이 끝날 때마다 고른 기준과 견줘 넣은 % 이상 오르면 상승 줄 · 넣은 % 이하로 내리면 하락 줄 — 처음 맞은 때부터 그 줄의 매도 봉 · 손절로 봄 · 그 전과 끝까지 안 맞으면 맨 윗줄 · 전일 = 전일 종가 · 고가 · 저가 = 장이 열린 뒤 그때까지 · % 가 빈칸이면 그 줄은 안 씀 · 아래 룰은 셋 다 같음</div><div class="dt-mkrest"><label class="dt-fee" data-tip="산 시각을 30분 단위로 반올림합니다(09:14 → 09:00 · 09:16 → 09:30) · 거기서 넣은 분이 지난 칸 값으로 봅니다 · 손절 · 꺾임으로 안 팔린 종목이 매수가 대비 그 % 를 넘지 못했으면 그 값에 팝니다 · 그 칸 값이 없으면 그 뒤 첫 칸">시각 미달 <span class="dt-seg"><button type="button" class="kh-chip" data-cut="1">켬</button><button type="button" class="kh-chip" data-cut="0">끔</button></span> 산 시각(30분 반올림)부터 <input data-set="cutMin" class="rl-in rl-num" inputmode="numeric" aria-label="시각 미달 — 산 시각부터 몇 분">분에 <input data-set="cutPct" class="rl-in rl-num" inputmode="decimal" aria-label="시각 미달 — 매수가 대비 몇 %">% 넘지 못하면 팜</label> <label class="dt-fee" data-tip="산 시각을 30분 단위로 반올림한 때부터 넣은 분이 지난 칸 값으로 봅니다 · 그때 매수가 대비 ±(%) 이내면(별로 안 움직였으면) 그 값에 팝니다 · 분 · % 둘 다 넣어야 셈 · 손절 · 꺾임 · 시각 미달이 먼저 걸리면 그것">횡보 <span class="dt-seg"><button type="button" class="kh-chip" data-flat="1">켬</button><button type="button" class="kh-chip" data-flat="0">끔</button></span> 매수 후 <input data-set="flatMin" class="rl-in rl-num" inputmode="numeric" placeholder="( )" aria-label="횡보 — 산 시각부터 몇 분">분에 ±<input data-set="flatPct" class="rl-in rl-num" inputmode="decimal" placeholder="( )" aria-label="횡보 — 매수가 대비 ± 몇 %">% 이내면 팜</label></div>
                <label class="dt-fee">꺾임 <span class="dt-seg"><button type="button" class="kh-chip" data-turn="1">켬</button><button type="button" class="kh-chip" data-turn="0">끔</button></span> <span class="dt-seg"><button type="button" class="kh-chip" data-turnby="prev">앞 시각 대비</button><button type="button" class="kh-chip" data-turnby="peak">고점 대비</button><button type="button" class="kh-chip" data-turnby="both">둘 다</button></span> <span data-turnfor="prev">앞 시각보다 <input data-set="turnPct" class="rl-in rl-num" inputmode="decimal" aria-label="꺾임 — 앞 시각보다 몇 % 넘게 내리면 팜">% 넘게 내리면 팜 <span class="rl-sug">그 이하는 무시 · 빈칸 = 0</span></span><span data-turnsep hidden> · </span><span data-turnfor="peak" hidden>오른 뒤 가장 높던 값보다 <input data-set="trail" class="rl-in rl-num" inputmode="decimal" aria-label="꺾임 — 고점 대비 몇 % 내리면 팜">% 내리면 팜 <span class="rl-sug">빈칸 = 안 씀</span></span></label>
                <label class="dt-fee">증권수수료 <input id="dt-fee" class="rl-in rl-num" inputmode="decimal" aria-label="증권수수료(%) — 팔 때만" placeholder="( )">% <span class="rl-sug">팔 때만 · 넣으면 저장되고 바로 다시 셈</span> <span id="dt-fee-msg" class="rl-sug"></span></label>
                <span class="dt-fee" id="dt-tax">거래세 · 농특세 <span class="rl-sug">서버 값 못 받음</span></span>
                <label class="dt-fee" data-tip="이 시각 전에 손절 · 꺾임 · 시각 미달에 걸린 종목은 그때 판 것으로 · 그때까지 안 팔린 종목은 이 시각(이하 마지막 30분 칸) 값에 모두 팝니다">매도 시각 <input data-set="endAt" class="rl-in rl-num" inputmode="numeric" style="width:4.2em" aria-label="매도 시각 — 이 시각에 남은 종목을 모두 팜"> <span class="rl-sug" data-endsug>빈칸 = 판 끝 칸</span></label>
              </div>
                <!-- 굳힘 칸마다 시각 · 금액 · 굳힐 종목 수 · 칩 몇 개 이상(11-23 재권님 「각 굳힘 칸별로 사는 금액과 종목 조건 다르게 셋팅할수 잇게 해줘」 → 「다」) — 빈칸 = 서버 기본(시각 · 종목 수) · 금액은 「굳힘마다 금액」 · 칩은 조건 없음
                     금액은 화면 셈 · 종목 수 · 칩 조건은 서버(개발2 dt30 굳히기)가 set.lockNs · set.lockMinChip 을 읽어 굳힘 · 고치면 다음 판부터 -->
                <!-- 창마다 금액 · 사지 않음(11-23 재권님 「굳힘이 아니고 이걸 필터로 만들어야 할거같은데 9시~30분까지 목록 …」 → 「응 해」 · 서버 개발2 253689d meta.windows) — 줄은 setFill 이 그날 판의 창 이름으로 그림(lkGridHtml) · 창 이름을 못 받은 판(옛 판)은 옛 굳힘 표 -->
                <div class="dt-fee dt-lkgrid" id="dt-lkgrid" style="display:grid;grid-template-columns:auto auto auto auto auto auto;gap:2px 8px;align-items:center"></div>
            </div>
          </div></details>
          <div class="st-cap" id="dt-month">—</div>
          <details class="dt-win" id="dt-win"><summary>칩별 승률 — 지난 30거래일 · 세후 · 칩 묶음마다 승률 · 날마다 이익 큰 종목</summary><div class="dw-body"></div></details>
          <details class="dt-win" id="dt-vi"><summary>그날 VI 목록 — 발동 · 풀림 시각 · 정적/동적 · 발동가 · <span class="dt-vi-sum">—</span></summary><div class="dw-body"></div></details>
          <details class="dt-win" id="dt-st"><summary>섹터 · 테마 — 판 종목 묶기 · <span class="dt-st-sum">—</span></summary><div class="dw-body"></div></details></div>
        <div class="dt-box st-scroll wheel-stop" id="dt-box"><div class="st-err">—</div></div>
        <div class="st-cap dt-foot">각 시각 = 그 시각에 끝난 5분봉 종가 · 평균 = 그 시각 값이 있는 종목만 · 단타 목록은 <span class="dt-at">—</span> 에 그날 판을 열고, 굳히기 전까지는 다시 세어 줄이 바뀜(늦게 든 칩 · 빠진 종목 · 빠졌다 다시 든 종목은 다시 든 때 가격) · 굳힘 시각마다 그때 차례 위 종목을 굳히고 굳힌 종목은 그날 안 빠짐 · 굳힌 뒤에는 늦게 나온 칩만 채움<span class="dt-buyrule"></span></div>
      </div>
      <div class="st-card sf" id="dt-sf"><div class="sf-h"><b>섹터수급 — 같은 업종 · 테마에 돈이 들어오나 · 프리장 08:00 ~ 정규장 09:30</b> <span class="dt-seg sf-by" role="tablist" aria-label="업종 · 테마"></span></div><div class="sf-body"><div class="st-err">—</div></div></div>`;
// 「룰 — 단타」 칸이 점수표를 바꿀 때 — 바로 다시 셈하고 룰 문서에 저장(같은 문서 · 같은 저장 길)
export async function setDtScore(score) {
  st.score = score && typeof score === 'object' ? score : {};
  if (root && st.data) { paint(st.data); chips(); }
  await saveDt({ score: st.score });
}
export const dtChips = () => [...colsOf()];   // 단타 판 칸의 칩 — 서버가 칩 목록을 안 줄 때 점수 칸이 고를 조건
// 주소 끝 #dt-buydef 로 들어오면 「매수 룰 정의」 칸(과 그것을 싼 셈 칸)을 펴고 그 자리로 — API 화면이 이 칸을 링크로 가리킴(개발3 · 재권님 「나」 11-24 18:2x) · 칸은 이 스크립트가 그린 뒤라 브라우저가 스스로 못 찾음
const openByHash = (host) => { const id = decodeURIComponent(String(location.hash || '').slice(1)); if (!/^dt-[\w-]+$/.test(id)) return; const el = host.querySelector(`#${id}`); if (!el) return; for (let p = el; p && p !== host; p = p.parentElement) if (p.tagName === 'DETAILS') p.open = true; requestAnimationFrame(() => el.scrollIntoView({ block: 'start' })); };
export function mountDt30(host) {
  if (!host) return;
  unmountDt30();
  host.classList.add('st', 'dt');
  host.innerHTML = TPL;
  root = host;
  BIND.forEach((f) => f());
  openByHash(host);
  st.pre0 = fetch(API, { cache: 'no-store' });   // 오늘 판 — 셈 칸 문서 · 칩 목록을 기다리지 않고 함께 받기 시작(11-26 · 판이 늦게 뜨던 것)
  loadFee().then(() => { if (root === host) load(); });
}
export function unmountDt30() {
  clearTimeout(again); again = null; st.seq++;   // 받는 중이던 값은 버린다(load 가 seq 로 가름)
  menuClose(); root = null; st.sfDay = null; mountSector(null);
}
const host0 = document.getElementById('dt-host');
if (host0) mountDt30(host0);
// 지표 표(색 짙기 기준)를 다 읽으면 한 번 다시 그림 — 첫 그리기가 먼저 끝나 거래 비율 글씨 색이 빠지는 것을 막음(11-23)
toneReady.then(() => { if (root && st.data) paint(st.data); }).catch(() => { /* 못 읽으면 색 없이 그대로 */ });
