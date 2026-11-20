// 투자 전략 「단타 30」 — 09:06 매수 → 30분마다 14:00 까지 · 30거래일 (2026-11-11 · 시황분석1)
//   · 재권님 「단타 목록 상위 30개를 소팅해서 9시 6분에 배수하고 9시반 10시 등 30분 단위로 2시까지 가격 추적하도록 셋팅해줘, 아래에 프리장 넣기 처럼 그 위에 종목 넣어서」 →
//     시안 temp/시황분석1-dt30-1743 → 「응 이대로 만드는데 위에 날짜도 넣어줘 30일 추적가능하도록」
//   · 그날 판(09:06 에 굳힌 단타 상위 30 · 매수가 · 각 시각 값)과 쌓인 날 목록은 서버 한 곳 — 화면은 그리기만(매수가 대비 % · 평균은 받은 값으로 셈)
//     응답(안 · 서버 레인과 맞춤): data { day, buyAt, times[HHMM], rows[{rank, code, name, cap(억원), sector(WICS), chips[], buy, px{HHMM: 값}}] } · meta { days[YYYYMMDD …최근 먼저] }
//   · 값이 없으면 — (0 이 아니다) · 서버를 다시 묻는 주기는 없다(날을 누를 때 · 처음 열 때 한 번)
import { signClass, NUM } from '/assets/js/sign.js';
import { bindWin } from './strategy-dtwin.js';
import { renameChips, chipName } from './strategy-chipname.js';   // 칩 이름을 실시간 순위와 같게(「수급」 → 「자동」 · 11-18) — 서버 값을 받는 자리에서
import { loadTiming, serverData } from '/holdings/js/store/timing.js';   // 서버 시각 값(장외 비우는 시각 · 11-19)
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
const WK = ['일', '월', '화', '수', '목', '금', '토'];
const dayTxt = (d) => { const m = String(d || '').match(/^(\d{4})(\d{2})(\d{2})$/); return m ? `${m[2]}-${m[3]}(${WK[new Date(+m[1], +m[2] - 1, +m[3]).getDay()]})` : '—'; };
const hmTxt = (t) => (/^\d{4}$/.test(String(t)) ? `${String(t).slice(0, 2)}:${String(t).slice(2)}` : esc(t || '—'));

// 이벤트 칸 — 그 종목이 걸린 홀딩스 「관심」 아래 룰(칩) 이름을 홀딩스 칩 줄 차례로 · 이름은 서버 rows[].chips 그대로(재권님 11-11 「종목과 매수가 사이에 이벤트를 추가하고 이벤트가 뭐뭐 걸렸는지 넣어줘 vi 초반급등 긍 관심하위의 룰들」)
const EV_ORDER = ['관심', '프리장', '초반상승', '현재상승', 'VI·급등', '볼린저', '장외', '매수', '자동'];
const evHtml = (c, r) => evChips(c, r, r ? [...st.miss].filter((x) => !(c || []).includes(x)) : []);   // 못 받은 칩은 종목마다 이름만 회색으로 붙임 · 「못 받음」 글씨 없음 · 늦게 채워 이미 붙은 칩은 뺌(11-12 재권님 「못받음 이라는 글씨만 빼주고 비활성화 된거같이 회색으로」 → 「각 종목에도 넣어줘」)
const evChips = (c, r, miss = []) => { const a = [...(Array.isArray(c) ? c : []), ...miss]; if (!a.length) return '<span class="st-err">—</span>'; a.sort((x, y) => (EV_ORDER.indexOf(x) + 99) % 99 - (EV_ORDER.indexOf(y) + 99) % 99); return a.map((x) => { const sb = r ? subsOf(r, x) : []; const dim = r && colsOf().includes(x) && !liveChip(r, x); if (miss.includes(x)) return `<span class="dt-evc is-miss" data-tip="${esc(`그날 판에 ${x} 값을 ${missWord()} — 이 종목이 걸렸는지 모름`)}">${esc(x)}</span>`; const vt = r && x === 'VI·급등' ? viTxt(r) : ''; return `<span class="dt-evc${dim ? ' is-off' : ''}">${esc(x)}${sb.length ? `<small>${esc(subTxt(x, sb))}</small>` : ''}${vt ? `<small>${esc(vt)}</small>` : ''}</span>`; }).join(''); };

const DOC = '/api/board/doc/strategy-rules';   // 수수료 % 를 두는 곳 — 투자 전략 룰 값과 같은 문서(rules.dt30.feePct)
const WIDE = matchMedia('(min-width: 701px)');   // 701 — strategy.css 가 쓰는 넓힘 폭(홀딩스 · Insight 700 경계) · 그보다 좁으면 좁은 폭 차례
const st = { lockSel: 0, set: null, cols: null, mon: '', off: new Set(), subOff: new Set(), order: '', fee: null, day: null, days: [], seq: 0, last: {}, only: '', data: null, score: {} };   // only — 이벤트 거르기(재권님 11-11 「vi없는건 제외하고 다시 셈해봐」) · 빈칸이면 전체
const ONLY = [['', '전체'], ['VI·급등', 'VI·급등 든 것만']];
// 줄 세우기 (재권님 11-11 「상위 16종목을 vi급등이 있고 초반매수 가 있고 시가총액이 높은순으로 다시 정렬해서 계산해봐」 — 「초반매수」 는 초반상승 칩으로 읽음)
//   기본 = 서버 차례(단타 순) · vi = VI·급등 든 것 먼저 → 그 안에서 초반상승 든 것 먼저 → 시가총액 큰 순 — 상위 PNL_TOP · 손익을 이 차례로 다시 셈
const ORDER = [['', '단타 순(켜진 칩)'], ['vi', 'VI·급등 → 초반상승 → 시가총액 순']];
const has = (r, c) => (liveChip(r, c) ? 1 : 0);   // 켜진 칩 · 하위 칩만(11-18 재권님 「VI·급등 칩 아래를 이렇게 나누고 소팅도 되게 해야해」 — 「09:25 이후」 를 끄면 그 종목은 VI·급등 묶음에서 빠져 뒤로)
const ORDER_FN = { vi: (a, b) => has(b, 'VI·급등') - has(a, 'VI·급등') || has(b, '초반상승') - has(a, '초반상승') || (Number(b.cap) || 0) - (Number(a.cap) || 0) };   // last — 날마다 14:00(마지막 시각) 평균 · 날짜 칩에 붙임

// 단타 칩 켜고 끄기 (11-11 재권님 「평균 옆에 단타 하위 버튼들 추가하고 하위 버튼들의 하위 칩도 필요해 상위버튼과 하위버튼을 활성화 비활성화 되는게 보여야 하고
//   활성화 될때와 비활성화 될때 이에 맞게 순위 조절이 되야하고 거기에 맞춰서 상위 16개 종목의 주가 및 수익률이 갱신되어야해」 → 「100개까지 늘려놔 그리고 그대로 개발해」)
//   · 단타가 세는 칩(홀딩스 home.js OV_CHIPS 와 같은 일곱 · 서버 개발2 가 「앞의 일곱」 으로 줌) 마다 단추 · 그 아래 하위 칩(서버 rows[].subs 에서 모음 — 이름을 박지 않음)
//   · 켜진 칩 · 하위 칩에 걸린 수(n)로 다시 줄 세움: n 많은 순 → 초반상승 % → 시가총액 — 서버 차례와 같은 셈 · n 0 인 종목은 뺌 · 상위 PNL_TOP · 손익 · 평균이 그 차례로 다시 셈
const DT_CHIPS = ['관심', '프리장', 'VI·급등', '장외', '매수', '초반상승', '자동'];
// 칩 칸 (11-12 재권님 「칩을 추가해도 칩을 활성화 비활성화되도록 우리꺼에 맞게 그려봐」 → 시안 temp/시황분석1-cols-1800 → 「오 좋아 이런거야 이대로 먼저 개선해서 올려줘」)
//   넓은 폭 표는 칩마다 세로 칸 · 칸 이름을 누르면 차림(켜기 · 끄기 · 룰 보기 · 옮기기 · 칸 지우기) · 끝 「+ 칩」 으로 서버가 주는 다른 칩(현재상승 · 볼린저 · 지운 칩)을 칸으로 더함
//   셈에 드는 칩 = 칸에 있고 켜진 칩(겹친 수 · 순위 · 손익이 그것으로 다시 셈) · 칸 차례 · 꺼진 칩은 보는 사람 브라우저에만(보는 상태 — 저장 못 해도 기본 칸으로 돈다)
const COLS_KEY = 'dt30-cols-v1';
// 11-18 서버 바뀜(개발2 · 재권님 「관심 하트는 누르는거 없애고 자동으로 관심으로」 → 「응 맞아」) — meta.watchRule 「자동」 인 날은 관심 = 자동 관심 룰 · 「수급(자동)」 칩이 안 옴
//   그날은 「자동」 칸을 빼고(빈 칸으로 남기지 않음) · 지난 날 판(옛 셈)은 그대로
const colsOf = () => (st.cols || DT_CHIPS).filter((c) => !(st.watchAuto && c === '자동'));
(() => { try { const v = JSON.parse(localStorage.getItem(COLS_KEY) || 'null'); if (v && Array.isArray(v.cols) && v.cols.length) { st.cols = v.cols.map(String).map(chipName); st.off = new Set((v.off || []).map(String).map(chipName)); } } catch (e) { /* 기본 칸 */ } })();
const colsSave = () => { try { localStorage.setItem(COLS_KEY, JSON.stringify({ cols: colsOf(), off: [...st.off] })); } catch (e) { /* 이 브라우저에 못 남겨도 화면은 돈다 */ } };
const CHIP_SEEN = [...DT_CHIPS];   // 칩 색 차례 — 단타 일곱 뒤로 처음 본 차례(색 변수는 일곱이라 돌려 씀)
const colorOf = (c) => { if (!CHIP_SEEN.includes(c)) CHIP_SEEN.push(c); return CHIP_SEEN.indexOf(c) % 7; };
const RULE_OF = { 프리장: 'pre', 초반상승: 'rise', 현재상승: 'nowup', 'VI·급등': 'vi', 볼린저: 'bb', 장외: 'after', 자동: 'volsurge' };   // 「종목 고르는 룰」 칩(data-rule) — 없는 칩은 룰 칸 없음
const subsRaw = (r, c) => { const v = r.subs && r.subs[c]; return Array.isArray(v) ? v : (v ? [v] : []); };
// VI·급등 하위는 겹치지 않게 둘로 (11-11 재권님 「그중 6개는 따로 분류가 가능하게 해줘」 → 「vi급등칩에 하위에 칩이 2개 있게 해줘」 — VI 43 · 급등 6 이 겹쳐 헷갈림)
//   서버 subs 의 VI · 급등을 읽어 급등이 들었으면 「VI 급등」(VI 도 함께 걸린 것 포함), VI 만이면 「VI 급상승」 — 둘을 더하면 상위 칩 숫자 · 서버 이름이 둘이 아니면 그대로 둠
const BOTH = { 'VI·급등': [['VI', '급등'], ['VI 급상승', 'VI 급등']] };   // 이름 — 재권님 「아래로 vi급상승 vi급등 이렇게 넣어줘」
// VI·급등 하위를 시각으로 둘 (11-18 재권님 「vi급등을 9시 25분전 그이후 로 버튼 2개로 나눠줘」) — 그날 처음 VI · 급등 시각(서버 viAt · surgeAt, 없으면 오늘 알림 목록)이
//   VI_SPLIT 앞이면 「09:25 전」 · 그 시각부터는 「09:25 이후」 · 시각을 못 받으면 「시각 모름」(어느 쪽으로도 안 셈) — 앞의 「VI 급상승 · VI 급등」 둘은 이것으로 바뀜
const VI_SPLIT = '0925';   // 서버 값이 없을 때 · 늦게 여는 날 옮기는 셈은 서버가 meta.viSplit 으로 내줌(11-19 재권님 「응 만들어」 · 화면이 따로 밀면 서버 점수와 갈림) · 하위 이름(점수표 열쇠)은 그대로
// 장 시작 시각 — 서버 판 meta.openAt(「HH:MM」 · 개발2 56f58cb) · lateMin(늦게 여는 분) · 없는 옛 판은 보통 날(09:00 · 0)
const DM = () => (st.data && st.data.meta) || {};
const addHM = (t, m) => { const x = +t.slice(0, 2) * 60 + +t.slice(2) + (m || 0); return `${String(Math.floor(x / 60)).padStart(2, '0')}${String(x % 60).padStart(2, '0')}`; };
const openHM = () => { const o = String(DM().openAt || '').replace(':', ''); return /^\d{4}$/.test(o) ? o : '0900'; };
const viSplit = () => { const v = String(DM().viSplit || '').replace(':', ''); return /^\d{4}$/.test(v) ? v : VI_SPLIT; };   // 나누는 시각은 서버 한 곳 — 판 meta.viSplit(점수 셈과 같은 값 · 개발2 배분 중)이 오면 그 값 · 없으면 09:25(서버 점수와 같게 · 개념정의 267a17d 검수)
const hmS = (t) => `${t.slice(0, 2)}:${t.slice(2)}`;
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
// 칩 설명 — 마우스를 1초 올려 두면 뜨는 공용 풍선(data-tip · glossary.js) (11-11 재권님 「vi급등 옆에 vi 랑 급등이 따로 있는데 이건 각각 뭔지 설명을 넣어놔」)
//   뜻은 서버 holdings/server/intraday_alerts.py 머리 글 그대로 · 급등 기준 % 는 서버 상수(SURGE_PCT) 한 곳이라 여기 숫자를 안 적음
const TIP = {   // 칩 풍선 — 쉬운 말로(11-18 재권님 「설명들 직관적이고 이해하기 쉽게 개선해줘」)
  'VI·급등': '오르는 쪽 VI 가 걸렸거나, 하루 사이 크게 뛴(급등) 종목 — 오른쪽 작은 칩 둘(VI 급상승 · VI 급등)로 따로 켜고 끔 · 둘을 더하면 이 숫자',
  'VI·급등|VI 급상승': 'VI 만 걸리고 급등 기준까지는 안 오른 종목\nVI — 값이 짧은 사이 크게 움직이면 거래소가 2분 동안 거래를 멈추고 한꺼번에 값을 정하는 것(여기서는 오르는 쪽만)',
  'VI·급등|VI 급등': '전날 종가보다 급등 기준 넘게 오른 종목(VI 가 함께 걸린 것도 여기)\n급등 기준은 서버가 정한 값 · 그날 처음 넘을 때 한 번 셈',
  '매수|①': '① 외국인 · 기관 · 연기금 · 프로그램 넷 다 산 종목',
  '매수|②': '② 외국인 · 기관 · 프로그램이 함께 산 종목',
  '매수|③': '③ 기관 · 연기금이 함께 산 종목',
  '매수|④': '④ 외국인만 산 종목',
  '매수|어림': '어림 — 외국인 · 기관 집계가 나오기 전에 먼저 보는 값\n외국계 증권사 창구와 프로그램이 둘 다 산 종목(장 열기 전에는 프로그램만) · 집계가 나오면 ①~④ 로 바뀜',
};
// 칩마다 「무엇 · 조건 · 언제 받나 · 얼마마다」 (11-18 재권님 「칩에 마우스 올리면 칩설명과 시간 주기 등등 정보도 넣어줘」)
//   문턱 값은 서버가 판에 싣는 룰(data.meta.rules) 그대로 읽는다 — 화면에 숫자를 안 둔다 · 못 받으면 그 줄은 「서버 값 못 받음」
//   받는 시각 · 주기 글은 서버가 아직 안 준다 — 서버가 data.meta.chipInfo{칩: 글} 을 주면 그것만 쓴다(개발2 카드 「단타 판 08:00 부터 짓기 · 굳히기 10:30」 덧). 그때 아래 WHEN 을 지운다
//   WHEN 의 시각은 11-18 서버 코드(pre_flow · intraday_alerts · kis_proxy 가집계 · open_rise · auto_watch)에서 읽은 그대로
let riseMeta = null;   // 초반상승 봉 길이 · 시각 — 서버 /api/kis/open-rise meta(룰 칸과 같은 주소) · 풍선에 씀
(async () => { try { const r = await fetch('/api/kis/open-rise', { cache: 'no-store' }); const j = r.ok ? await r.json() : null; riseMeta = (j && j.meta) || null; } catch (e) { riseMeta = null; } })();
loadTiming();   // 한 번 받아 둠 — 풍선은 마우스를 올릴 때 읽으므로 그때는 와 있음 · 못 받으면 「서버 값 못 받음」
const WHEN = {
  관심: '언제 — 전날 장 마감 뒤 정해지고, 장중에는 5분마다 그때 값으로 다시 거름',
  프리장: '언제 — 장 열기 전 08:00~08:50 몇 분마다 셈 · 08:50~09:00 에 그날 것으로 정함',
  'VI·급등': '언제 — 08:00 부터 10초마다(장 열기 전은 넥스트레이드 값) · 단타 판에는 판을 굳히기 전까지 걸린 것만',
  get 장외() { const c = serverData('afterClear') || serverData('chipReset'); return `언제 — 장 끝난 15:40 뒤부터 다음 날 ${c && c.from ? c.from : '아침(비우는 시각 — 서버 값 못 받음)'} 까지 · 아침 단타 판에는 거의 안 듦`; },   // 비우는 시각은 서버 /api/kis/stats afterClear(= market_hours.CHIP_RESET 한 곳 · 11-19 07:30 → 07:50 개발1)
  매수: '언제 — 외국인 첫 집계 09:30 · 기관 첫 집계 10:00 · 그 전에는 「어림」 으로 먼저 봄',
  get 초반상승() { const m = riseMeta; return m && m.barMin != null ? `언제 — 장 시작 ${m.barMin}분 뒤(${m.barFrom || '—'} ~ ${m.barTo || '—'} 첫 ${m.barMin}분봉이 끝난 뒤) · 늦게 여는 날은 여는 시각부터` : '언제 — 장 시작 첫 봉이 끝난 뒤부터(몇 분 뒤인지 — 서버 값 못 받음)'; },   // 「장 시작 몇 분 뒤」 — 11-20 재권님 「단타에 초반상승이 장시작 몇분후인지 설명에 넣어줘」 · 값은 서버 open-rise meta.barMin · barFrom · barTo 그대로
  자동: '언제 — 전날 장 마감 뒤 정해지고, 장중에는 5분마다 그때 값으로 다시 거름',
};
const WHAT = {
  관심: (R) => `관심 목록에 하트로 담은 종목 · 시가총액 ${R && R.capMinEok != null ? `${R.capMinEok.toLocaleString()}억 이상` : '문턱 — 서버 값 못 받음'}`,
  프리장: () => '장 열기 전(넥스트레이드 프리마켓) 전날보다 오르면서 거래대금이 큰 종목',
  장외: () => '장 끝난 뒤(넥스트레이드 애프터마켓 · 다음 날 프리마켓) 그날 종가보다 오른 종목',
  매수: () => '외국인 · 기관이 많이 산 종목(증권사 집계) · ①~④ 는 누가 함께 샀는지',
  초반상승: () => `장 시작 첫 봉에서 시가보다 ${riseMeta && riseMeta.risePct != null ? `${riseMeta.risePct}%` : '(문턱 — 서버 값 못 받음)'} 이상 오른 종목 · 시가총액 ${riseMeta && riseMeta.minCapEok != null ? `${Number(riseMeta.minCapEok).toLocaleString()}억 이상` : '(서버 값 못 받음)'} · ETF 는 뺌`,   // 정해진 값은 값으로(11-20 재권님 「서버 코드에 있는데 왜 이걸 설명에 안넣는거지?」) · 값은 서버 open-rise meta.risePct · minCapEok
  자동: (R) => (R ? `전날 거래량이 크게 늘며 오른 종목을 서버가 자동으로 담음 — 전날 +${R.prevPct}% 이상 올랐고${R.sectorPct != null ? ` · 그 업종이 +${R.sectorPct}% 이상` : ''}${R.nearHighPct != null ? ` · 1년 최고가에서 ${R.nearHighPct}% 안` : ''}${R.maDays ? ` · ${R.maDays}일 평균값 위${R.maUpCandle ? '에서 오른 날' : ''}` : ''}${R.scoreW ? ` · 순서는 오른 폭 ${R.scoreW.pct}% · 거래량 ${R.scoreW.vol}% 로 셈` : ''}` : '전날 거래량이 크게 늘며 오른 종목을 서버가 자동으로 담음 — 조건 값은 서버 값 못 받음'),
};
const tipOf = (k) => {
  if (k.includes('|')) return TIP[k] || '';
  const ci = st.chipInfo && st.chipInfo[k];
  if (typeof ci === 'string' && ci) return ci;
  const R = st.rules || {};
  if (k === '관심' && st.watchAuto) return [`관심 — 하트 대신 서버가 자동으로 담은 종목\n${WHAT.자동(R.관심).replace(/^전날 거래량이 크게 늘며 오른 종목을 서버가 자동으로 담음 — /, '조건 — ')}`, WHEN.자동].filter(Boolean).join('\n');
  const head = TIP[k] || (WHAT[k] ? WHAT[k](R[k]) : '');
  return [head, WHEN[k]].filter(Boolean).join('\n');
};
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
export const SUB_NAME = { '매수|①': '외·기·연·프', '매수|②': '외·기·프', '매수|③': '기·연', '매수|④': '외국인만' };
export const subName = (c, x) => SUB_NAME[`${c}|${x}`] || x;
const subTxt = (c, sb) => sb.map((x) => subName(c, x)).join(sb.some((x) => SUB_NAME[`${c}|${x}`]) ? ' / ' : '·');   // 이름 안에 「·」 가 있어 여럿이면 「 / 」 로 가름
const tipAt = (k) => { const t = tipOf(k); return t ? ` data-tip="${esc(t)}"` : ''; };
function chipPanel(all) {
  return colsOf().map((c) => { const i = colorOf(c);
    const n = all.filter((r) => (r.chips || []).includes(c)).length;
    const subs = subOrder(c, [...new Set(all.flatMap((r) => subsOf(r, c)))]);
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
//   · 기본값은 지금 룰 그대로(손절 −1 · 꺾임 켬 · 고점 빈칸) — 값은 아래 DEF_SET 한 곳 · 넣은 값은 룰 문서(rules.dt30) 한 곳에 저장
// 매수 타이밍 (11-18 재권님 「매수 타이밍을 9시1분 과 vi발동 두개를 고를수 있게 해줘. 그것에 맞춰서 차익도 달라지게」 → (가) 「그뒤 30분이 아니고 시간으로 30분단위로」)
//   · open = 서버 매수가(09:00 시가) · p1 = rows[].px1(09:01 · 개발2) · vi = rows[].viPx(VI 걸린 때 값 · 개발2) — 값이 없는 종목은 안 산다(몫도 안 나눔 · 0 으로 안 봄)
//   · 파는 룰은 시계 30분 칸(09:30 · 10:00 …) 중 산 시각 뒤 칸부터 본다 — 산 시각 앞 칸은 비움
// 사는 시각 고르기 (11-19 재권님 「사는 시간도 쓸수있게 해줘 9시 1분~ 5분 사이에 살거야」 → 「늦게 여는 시간만큼 늦춰줘」) — p1~p5 = 여는 시각 + 1~5분 · 값은 서버 rows[].pxMin["N"] · 시각은 meta.pxMinAt["N"](개발2 5d6c962)
//   · 열쇠 p1 은 옛 「09:01」 그대로(저장해 둔 셈 칸이 안 깨짐) · pxMin 이 없는 옛 판은 p1 만 px1 로 · p2~p5 는 「서버 값 아직」(0 으로 안 봄 · 안 삼)
const PMIN = [1, 2, 3, 4, 5];
const BUYS = [['open', '09:00 시가'], ...PMIN.map((n) => [`p${n}`, `09:0${n}`]), ['vi', 'VI 발동']];   // 이름의 시각은 판을 받으면 서버 openAt · pxMinAt 로 바꿔 씀(buyName)
const pmOf = (k) => (/^p[1-5]$/.test(k || '') ? +k.slice(1) : 0);
const minHM = (n) => { const o = String((DM().pxMinAt || {})[n] || '').replace(':', ''); return /^\d{4}$/.test(o) ? o : n === 1 ? p1HM() : addHM(openHM(), n); };
const minVal = (r, n) => (r.pxMin && typeof r.pxMin === 'object' ? r.pxMin[n] : n === 1 ? r.px1 : undefined);   // undefined = 서버가 이 칸을 아직 안 줌 · null = 못 잼
// 새 매수가 규칙(11-20 · 서버 개발2)으로 지은 판 — 줄에 buyTs · buySrc 「9시 1분 값」 이 있으면 기본 매수가는 「들어온 때」 가격 · 옛 판(11-19 까지)은 시가
const newBuyOf = (d) => ((d && d.rows) || []).some((r) => r.buyTs || /9시 1분/.test(String(r.buySrc || '')));
const buyName = (k, t) => (k === 'open' ? (newBuyOf(st.data) ? '들어온 때' : `${hmS(openHM())} 시가`) : pmOf(k) ? hmS(minHM(pmOf(k))) : t);   // 「들어온 때」 — 11-20 재권님 「응 그렇게 해」(옛 판만 「09:00 시가」)
const hhmm = (t) => String(t || '').replace(/:/g, '').slice(0, 4);
function buyOf(r) {   // → { px, at(HHMM), src } | null
  const k = st.set.buy || 'open';
  const n = pmOf(k);
  // 판에 들어오기 전 시각의 값으로는 사지 않음 — 그 시각이 들어온 때(buyAt)보다 앞이면 들어온 때 가격(r.buy)으로(11-20 재권님 「단타 목록에 들어온 시점부터 등락률 계산되게 되야해」)
  const inAt = hhmm(r.buyAt), late = (at) => newBuyOf(st.data) && /^\d{4}$/.test(inAt) && /^\d{4}$/.test(at) && at < inAt && Number(r.buy) > 0;
  const inB = () => ({ px: Number(r.buy), at: inAt, src: `들어온 때 ${hmS(inAt)}` });
  if (n) { const o = minVal(r, n), t = hmS(minHM(n)); if (late(hhmm((o && o.at) || minHM(n)))) return inB(); return o && Number(o.px) > 0 ? { px: Number(o.px), at: hhmm(o.at || minHM(n)), src: o.src === 'now' ? `${t} 그때 현재가` : t } : null; }
  if (k === 'vi') { const o = r.viPx; if (o && o.at && late(hhmm(o.at))) return inB(); return o && Number(o.px) > 0 && o.at ? { px: Number(o.px), at: hhmm(o.at), src: `VI ${String(o.at).slice(0, 5)}` } : null; }
  return Number(r.buy) > 0 ? { px: Number(r.buy), at: hhmm(r.buyAt || openHM()), src: r.buySrc || '시가' } : null;
}
function sellAt(p) {   // p — 시각마다 매수가 대비 %(null 은 값 없음) → { k: 판 시각 차례 또는 -1, why }
  const S = st.set; let pk = 0;
  for (let k = 0; k < p.length; k++) {
    if (p[k] == null) continue;
    if (S.stop != null && p[k] <= S.stop) return { k, why: '손절' };
    let a = k - 1; while (a >= 0 && p[a] == null) a--;
    // 꺾임 폭(11-18 재권님 「꺽임룰에 1%이하는 무시한다로 룰 잡아」 → 「그거말고 꺽임 에 내가 %를 추가할수있게 해줘」) — 셈 칸에 넣은 turnPct% 넘게 앞 시각보다 내릴 때만 꺾임 · 기본 0(지금 룰 그대로)
    // 꺾임 기준 두 단추(11-20 재권님 「앞시각이랑 고점대비 2개 버튼으로 선택할수 있게 해줘」) — turnBy prev(앞 시각 대비 · turnPct) · peak(고점 대비 · trail) 중 하나만 · % 는 기준마다 따로 남김
    // 11-20 재권님 「선택할수 있게 해줘. 각각도 되고 둘다도 되게」 — both(둘 다) 더함 · 기준이 저장 안 된 옛 설정은 both(바꾸기 전 셈 그대로)
    if (S.turn && (S.turnBy || 'both') !== 'peak' && a >= 0 && p[a] > 0 && ((100 + p[k]) / (100 + p[a]) - 1) * 100 < -S.turnPct) return { k, why: '꺾임' };
    if (S.turn && (S.turnBy || 'both') !== 'prev' && S.trail != null && pk > 0 && ((100 + p[k]) / (100 + pk) - 1) * 100 <= -S.trail) return { k, why: '고점' };
    pk = Math.max(pk, p[k]);
  }
  return { k: -1, why: '' };
}
// 손익 셈 (11-11 재권님 「각 종목별로 천만원씩 샀다고 하고 상위 16종목을 해당룰로 했을때 수익은 얼마지?」 → 「결과 옆에 거래세랑 세금 퍼센트를 넣어줘
//   세금은 코스피와 코스닥세금 내는거 룰찾아서 넣고 증권수수료는 내가 기입하면 그 숫자에 맞춰서 대입되게 해줘」)
//   · 상위 PNL_TOP 종목을 한 종목에 PNL_WON 원어치(주 단위 내림) 09:06 매수가에 사서 위 룰대로 판 값에 판다
//   · 세금은 팔 때만 — 판 금액 × (거래세 + 농어촌특별세) · 시장마다 TAX 표 · 증권수수료는 팔 때만 판 금액 × 수수료 %(11-18 재권님 「증권수수료는 팔때만」 — 그 전에는 살 때 · 팔 때 각각)
//   · 수수료 % 는 재권님이 칸에 넣으신 값 — 서버 룰 문서(strategy-rules · rules.dt30.feePct) 한 곳 · 빈칸이면 수수료는 안 셈(「빈칸」 이라 적음 · 0 으로 보지 않음)
//   · 2026 세율(KB증권 「2026년 증권거래세율 변경 안내」 · 머니투데이 2025-12-01 「내년 1월부터 증권거래세 오른다」) — 세율이 바뀌면 TAX 한 곳만 고친다
const PNL_TOP = 30, PNL_WON = 10_000_000;   // 기본값 — 재권님이 칸에 넣으면 st.set 이 이김
// 셈 칸 기본값 (11-18) — minChip 칩 N개 이상만(0 = 전체) · top 상위 몇 종목 · 돈은 전체 금액 dayWon 을 그 종목 수로 똑같이 나눔
//   11-18 재권님 「금액은 전체 금액으로 해주고 종목만큼 나눈다 라는 룰로 해줘 금액을 맨앞으로」 — 종목마다(each) 갈래는 걷음 · 기본 전체 금액 = 지금까지의 기본(상위 30 × 1,000만원)과 같은 3억
const DEF_SET = { minChip: 0, top: PNL_TOP, mode: 'day', perWon: PNL_WON, dayWon: PNL_TOP * PNL_WON, stop: -1, turn: true, turnBy: 'both', turnPct: 0, trail: null, pyr: false, buy: 'open' };   // buy — 매수 타이밍 open(09:00 시가 · 지금까지 셈) · p1(09:01) · vi(VI 발동)   // pyr — 불타기(손절로 판 돈을 그 시각 가장 많이 오른 종목에 더 삼) · 기본 끔
st.set = { ...DEF_SET };
const TAX = { KOSPI: { tx: 0.05, rural: 0.15 }, KOSDAQ: { tx: 0.20, rural: 0 } };   // % · 코스피 = 거래세 0.05 + 농특세 0.15 · 코스닥 = 거래세 0.20
const MKT = { KOSPI: '코스피', KOSDAQ: '코스닥' };
const manTxt = (w) => { const m = Number(w) / 10000; return !Number.isFinite(m) ? '—' : m >= 10000 && m % 10000 === 0 ? `${num(m / 10000)}억원` : `${num(m)}만원`; };   // 원 → 만원 · 1억 단위면 억원
const won = (x) => (x == null || !Number.isFinite(x) ? '—' : `${x < 0 ? '-' : x > 0 ? '+' : ''}${Math.abs(Math.round(x)).toLocaleString('ko-KR')}원`);
const wonPlain = (x) => (x == null || !Number.isFinite(x) ? '—' : `${Math.round(x).toLocaleString('ko-KR')}원`);
const taxTxt = (r) => { const m = String(r.market || '').toUpperCase(), T = TAX[m]; return T ? `${MKT[m]} ${num(T.tx, 2)}${T.rural ? ` + ${num(T.rural, 2)}` : ''}%` : '<span class="st-err">—</span>'; };
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
function calc(d) {
  const S = st.set;
  const times = Array.isArray(d.times) ? d.times : [];
  const all = Array.isArray(d.rows) ? d.rows : [];
  const live = all.filter((r) => nLive(r) > 0).sort(byLive);   // 켜진 칩으로 다시 셈한 단타 차례
  const rows1 = st.only ? live.filter((r) => liveChip(r, st.only)) : live;   // 거르고 나서 순번 · 상위 N · 평균을 다시 셈
  const rows0 = S.minChip > 0 ? rows1.filter((r) => nLive(r) >= S.minChip) : rows1;   // 칩 N개 이상만(11-18) — 켜진 칩으로 센 겹침 수
  const rows = st.order ? [...rows0].sort(ORDER_FN[st.order]) : rows0;   // 줄 세우기를 바꾸면 순번 · 상위 N 을 그 차례로
  const L = times.length - 1;
  // 그날 판 실시간 (11-11 재권님 「그날은 변동에 맞춰서 실시간으로 적용되야 하고 그날 2시가 지나면 값이 저장되도록 해줘. 다만 필터나 수수료등을 바꿨을때 값이 바뀌는건 되야되」 → 「응 진행해」)
  //   서버(개발2 dt30)가 장중에는 rows[].now · data.nowAt 을 새로 주고, 14:00 뒤 굳혀 저장하면 data.closed = true — 화면은 closed 가 아니고 now 가 있을 때만 「장중」
  const LIVE = d.closed !== true && all.some((r) => r.now != null);
  // 돈 넣는 법(11-18) — each: 상위 N 종목마다 perWon · day: 하루 dayWon 을 상위 N(보이는 종목이 적으면 그 수)으로 똑같이 나눔
  const n = Math.min(S.top, rows.length), nb = rows.slice(0, n).filter((r) => buyOf(r)).length;   // 매수가 없는 종목 몫은 나누지 않음(qa 11-18 — 안 쓰는 돈이 생겼음)
  const per = S.mode === 'day' ? (nb ? S.dayWon / nb : 0) : S.perWon;
  const ch = (r, t) => { const B = buyOf(r), v = Number((r.px || {})[t]); return !B || hhmm(t) <= B.at || (r.px || {})[t] == null || !Number.isFinite(v) ? null : (v / B.px - 1) * 100; };   // 산 시각 앞 칸은 비움
  const R = rows.map((r) => { const p = times.map((t) => ch(r, t)); const s = sellAt(p); let last = L; while (last >= 0 && p[last] == null) last--; const nowCh = LIVE && s.k < 0 && Number(r.now) > 0 && buyOf(r) ? (Number(r.now) / buyOf(r).px - 1) * 100 : null;   // 장중 · 안 판 종목 — 결과 · 손익은 서버 지금 값(rows[].now)
    const at = s.k >= 0 ? s.k : last, sellPx = nowCh != null ? Number(r.now) : at >= 0 ? Number((r.px || {})[times[at]]) : null;
    const b = buyOf(r) ? buyOf(r).px : 0, qty = b > 0 ? Math.floor(per / b) : 0;
    const T = TAX[String(r.market || '').toUpperCase()] || null;
    const pnl = qty > 0 && Number.isFinite(sellPx) ? (() => {
      const buyAmt = qty * b, sellAmt = qty * sellPx;
      const tx = T ? sellAmt * T.tx / 100 : null, rural = T ? sellAmt * T.rural / 100 : null;
      const fee = st.fee == null ? null : sellAmt * st.fee / 100;   // 팔 때만
      return { buyAmt, sellAmt, gross: sellAmt - buyAmt, tx, rural, fee, net: T ? sellAmt - buyAmt - tx - rural - (fee || 0) : null };
    })() : null;
    return { r, p, s, pnl, sellPx, T, now: nowCh != null, res: s.k >= 0 ? p[s.k] : nowCh != null ? nowCh : (last >= 0 ? p[last] : null) }; });
  if (S.pyr) pyrCalc(R.slice(0, n), times);
  const top = R.slice(0, n).filter((x) => x.pnl), sum = (k) => top.reduce((a, x) => a + (x.pnl[k] || 0), 0);
  const noMkt = top.filter((x) => x.pnl.net == null).length;   // 시장을 모르는 종목 — 세금을 못 셈
  const P = top.length ? { n: top.length, buy: sum('buyAmt'), sell: sum('sellAmt'), gross: sum('gross'), tx: sum('tx'), rural: sum('rural'), fee: st.fee == null ? null : sum('fee'), net: sum('net'), pyr: sum('pyr'), pyrN: top.reduce((a, x) => a + (x.pnl.adds || []).length, 0), win: top.filter((x) => x.pnl.net > 0).length } : null;
  return { times, all, live, rows1, rows, L, LIVE, R, n, nb, per, top, noMkt, P };
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

function paint(d) {
  atText(d.buyAt);
  st.rules = (d.meta && d.meta.rules) || null; st.chipInfo = (d.meta && d.meta.chipInfo) || null;   // 칩 풍선 — 서버 룰 값 · 받는 때 글(tipOf)
  st.miss = new Set(names(d.meta && d.meta.missing)); st.wait = new Set(names(d.meta && d.meta.wait)); st.watchAuto = !!(d.meta && d.meta.watchRule === '자동'); st.openAt = (d.meta && d.meta.openAt) || ((d.rows || []).find((r) => r.buySrc && r.buyAt) || {}).buyAt || null; st.rebuilt = !!(d.meta && d.meta.rebuilt === true);   // openAt — 서버 meta.openAt · 없으면(다시 센 판) 줄의 buyAt
  { const k = Number(d.meta && d.meta.minChips); if (root) root.querySelectorAll('.dt-min').forEach((e) => { e.textContent = k > 0 ? `칩 ${k}개 이상 든 종목` : '칩 하나 이상 든 종목(옛 셈 판)'; }); }   // 문턱은 서버 meta.minChips 한 곳(11-18 판부터 둘 이상)
  const C = calc(d), { times, all, live, rows1, rows, L, LIVE, R, n: topN, per, top, noMkt, P } = C;
  usLoad(d.day);
  // 칩 줄은 표 안 「종목」 머리 줄과 「평균」 줄 사이에 (11-11 재권님 「칩위치는 종목과 평균사이에 넣어줘」) · 표가 옆으로 밀려도 칩은 왼쪽에 붙어 있음(strategy.css)
  const chipRow = (n) => `<tr class="dt-chiprow"><td colspan="${n}"><div class="dt-chips" id="dt-chips" aria-label="단타 칩 — 눌러서 켜고 끄기"><span class="dt-hd">단타 칩</span>${chipPanel(all)}<span class="dt-us" id="dt-us" data-day="${esc(d.day || '')}">${usHtml(d.day)}</span></div></td></tr>`;
  $('dt-only').innerHTML = ONLY.map(([k, t]) => `<button type="button" class="kh-chip${st.only === k ? ' is-active' : ''}" data-only="${k}">${t}${k ? ` ${all.filter((r) => (r.chips || []).includes(k)).length}` : ` ${all.length}`}</button>`).join('');
  $('dt-order').innerHTML = ORDER.map(([k, t]) => `<button type="button" class="kh-chip${st.order === k ? ' is-active' : ''}" data-order="${k}">${t}</button>`).join('');
  // 평균 (11-18 재권님 「평균값이 뭔가 이상한데」 → (나)) — 판 종목은 판 값으로 고정해 그 뒤 시각에도 넣는다 · 그 시각까지 실제로 번 수익률
  //   전에는 판 칸부터 뺐는데(11-11) 오후에 끝까지 오른 몇 종목만 남아 평균이 부풀었다(11-17 12:30~ 2종목 +21.79%)
  const atK = (x, k) => (x.s.k >= 0 && k >= x.s.k ? x.p[x.s.k] : x.p[k]);
  const avg = times.map((_, k) => mean(R.map((x) => atK(x, k)).filter((v) => v != null)));
  const res = R.map((x) => x.res).filter((v) => v != null), resAvg = mean(res);
  const sold = R.filter((x) => x.s.k >= 0);
  st.last[d.day] = resAvg;
  const bm = d.meta || {}, nm = (a) => names(a).join(' · ');   // 되채운 날 · 못 받은 칩 — 칩 이름은 서버가 준 그대로
  const rebuilt = bm.rebuilt === true ? ` · 되채운 날${nm(bm.missing) ? ` · ${nm(bm.missing)} 못 셈` : ''}${nm(bm.approx) ? ` · ${nm(bm.approx)} 어림` : ''}` : `${nm(bm.missing) ? ` · 못 받은 칩 ${nm(bm.missing)}` : ''}${nm(bm.early) ? ` · ${nm(bm.early)} 어림(집계 전)` : ''}${bm.late && typeof bm.late === 'object' && Object.keys(bm.late).length ? ` · 늦게 채움 ${Object.entries(bm.late).map(([k, v]) => `${k} ${v}`).join(' · ')}` : ''}`;
  $('dt-meta').textContent = `${dayTxt(d.day)}${rebuilt}${LIVE ? ` · 장중 실시간(${esc(String(d.nowAt || '—'))} 값 · 14:00 뒤 굳혀 저장)` : d.closed === true ? ' · 14:00 뒤 굳힌 값' : ''} · 후보 ${num(all.length)} 중 켜진 칩에 걸린 ${num(live.length)} · 보이는 ${num(rows.length)} · ${d.buyAt ? (st.openAt ? `${hmTxt(d.buyAt)} 부터 판 · 매수가 = 정규장 ${hmTxt(String(st.openAt).replace(':', ''))} 시가` : `${hmTxt(d.buyAt)} 매수`) : '매수 시각 —'} · 판 것 ${sold.length}(손절 ${sold.filter((x) => x.s.why === '손절').length} · 꺾임 ${sold.filter((x) => x.s.why === '꺾임').length} · 고점 ${sold.filter((x) => x.s.why === '고점').length}) · 끝까지 들고 감 ${R.length - sold.length} · 결과 평균 ${sgn(resAvg)} · 이긴 것 ${res.filter((v) => v > 0).length} · 진 것 ${res.filter((v) => v < 0).length}`;
  // 상위 몇 종목 · 금액은 이 줄에서 바로 넣는다(11-18 재권님 「상위종목 갯수넣을수 있게 금액도 넣을수 있게 … 이거 수정하면 일별로 다 값이 다시 적용되서 그달 총액 다시 정산되게」) — 바꾸면 그날 판 · 달 합계(monthPaint)가 같은 셈으로 다시 셈
  const IN_TOP = '<input data-set="top" class="rl-in rl-num" inputmode="numeric" aria-label="상위 몇 종목">', IN_WON = '<input data-set="won" class="rl-in rl-num" inputmode="numeric" aria-label="금액(만원)">';
  const head = `총 ${IN_WON}만원 ÷ 상위 ${IN_TOP}종목`;   // 재권님 「종목에 똑같이 나눠 - 종목마다 3000만원 이것을 종목 으로 바꿔」 → 「앞에 금액은 총금액이고 종목수로 나눠서 사는걸로」 — 총액을 종목 수로 똑같이 나눠 삼(종목마다 몫은 손익 칸 머리에)
  // 칸 둘은 한 번만 만들고 뒤 글만 바꾼다(qa 11-18 — 장중 다시 그릴 때마다 칸을 새로 만들어 치는 도중 글자 · 커서가 사라졌음)
  const sumEl = $('dt-pnl-sum'); if (!sumEl.querySelector('.dt-pnl-rest')) sumEl.innerHTML = `<b>${head}</b><span class="dt-pnl-rest"></span>`;
  sumEl.querySelector('.dt-pnl-rest').innerHTML = P ? ` · 산 ${wonPlain(P.buy)} · 판 ${wonPlain(P.sell)} · 빼기 전 ${won(P.gross)}`
    + ` · 거래세 ${wonPlain(P.tx)} · 농특세 ${wonPlain(P.rural)} · 수수료 ${P.fee == null ? '빈칸 — 안 셈' : wonPlain(P.fee)}`
    + `${P.pyrN ? ` · 불타기 ${P.pyrN}번 ${won(P.pyr)}` : st.set.pyr ? ' · 불타기 0번' : ''} · <b>세후 손익 <span class="${signClass(P.net, NUM) || ''}">${won(P.net)}</span> (${pct(P.net / P.buy * 100)})</b>${noMkt ? ` · 시장 모름 ${noMkt}종목은 세후에서 뺌` : ''}` : ' · — 손익을 셀 값이 없음';
  setFill();
  // 0종목일 때 까닭 (11-19 재권님 「응」 — 거르기 칸 때문에 다 가려진 것을 「판이 없다」 로 읽지 않게) — 판이 빔 · 켜진 칩에 0 · 「든 것만」 거르기 · 「칩 N개 이상」 칸을 갈라 적음
  if (!rows.length) {
    const why = !all.length ? '이 날 굳힌 단타 종목 없음'
      : !live.length ? `켜진 칩에 걸린 종목 0 · 그날 판은 ${num(all.length)}종목 — 꺼 둔 칩을 켜면 보입니다`
      : !rows1.length ? `「${st.only} 든 것만」 거르기에 0종목 · 켜진 칩에 걸린 ${num(live.length)}종목 — 거르기를 「전체」 로 하면 보입니다`
      : `칩 ${st.set.minChip}개 이상인 종목 0 · 켜진 칩에 걸린 ${num(rows1.length)}종목 — 칩 칸을 비우면 다 보입니다`;
    $('dt-box').innerHTML = `<div class="st-err">— ${esc(why)}</div>`; return;
  }
  const cell = (x, k) => {
    const v = x.p[k];
    // 그 시각 가격을 % 위에 · 글씨는 검정(색은 아래 % 만) — 11-20 재권님 「등락률 위에 가격도 같이 보이게 해줘」 → 색을 넣어 보시고 「글씨는 그냥 검정으로 하자 보기 힘드네」
    const px = Number((x.r.px || {})[times[k]]);
    const pxT = v == null || !Number.isFinite(px) ? '' : `<span style="display: block; line-height: 1.25;">${num(px)}</span>`;   // 줄 높이를 좌우 두 줄 칸(51px)에 맞춤 — 그대로 두 줄이면 56px 라 10번째 줄이 잘림(qa 11-20) · strategy.css 는 남의 미커밋이 있어 여기 둠
    if (x.s.k >= 0 && k === x.s.k) return `<td class="dt-sold">${pxT}${pct(v)}<em>${x.s.why}</em>${x.pyrTo ? `<small class="dt-pyr"> → ${esc(x.pyrTo.name || '—')} 불타기</small>` : ''}</td>`;
    { const ad = x.pnl && (x.pnl.adds || []).filter((o) => o.k === k); if (ad && ad.length) return `<td class="${k === L ? 'dt-last' : ''}">${pxT}${pct(v)}<small class="dt-pyr"> ← ${ad.map((o) => esc(o.from || '—')).join(' · ')} 손절 돈 불타기</small></td>`; }
    if (x.s.k >= 0 && k > x.s.k) return `<td class="dt-after">${v == null ? '—' : sgn(v)}</td>`;
    return `<td class="${k === L ? 'dt-last' : ''}">${pxT}${pct(v)}</td>`;
  };
  const plTd = (x, i) => `<td class="dt-pl">${i < topN && x.pnl ? (x.pnl.net == null ? '<span class="st-err">시장 모름</span>' : `<span class="${signClass(x.pnl.net, NUM) || ''}">${won(x.pnl.net)}</span><small>빼기 전 ${won(x.pnl.gross)}${x.pnl.adds && x.pnl.adds.length ? ` · 불타기 ${won(x.pnl.pyr)}` : ''}</small>`) : '<span class="st-err">—</span>'}</td>`;
  const resTd = (x) => `<td class="dt-res">${pct(x.res)}<small>${x.s.k >= 0 ? `${hmTxt(times[x.s.k])} ${x.s.why}` : x.now ? `지금 ${esc(String(d.nowAt || '').slice(0, 5))}` : '끝까지'}</small></td>`;
  const rk = (r, i) => `<td class="dt-rk">${i + 1}</td>`;
  // 매수가 (11-18 서버 바뀜) — 정규장 전에 든 종목은 buy null + buyWait → 「09:00 시가 기다림」 · 채워지면 buySrc(시가 · 지금 값) · 그 시각
  const NM0 = d.meta || {};
  const buyTd = (r) => ((st.set.buy || 'open') !== 'open' ? (() => { const B = buyOf(r); return B ? `<td class="dt-buy">${num(B.px)}<small>${esc(B.src)}</small></td>` : `<td class="dt-buy"><span class="dt-nxm">${st.set.buy === 'vi' ? (r.viAt ? 'VI 값 못 받음 · 안 삼' : 'VI 없음 · 안 삼') : minVal(r, pmOf(st.set.buy)) === undefined ? '서버 값 아직 · 안 삼' : `${hmS(minHM(pmOf(st.set.buy)))} 값 없음 · 안 삼`}</span></td>`; })()
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
  const p1Avg = `<td class="dt-nx">${p1V.length ? pct(mean(p1V)) : '—'}</td>`;
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
  const gk = (x) => rankOf(x.r);   // 점수표가 있으면 점수로 묶음
  const grp = (i, span) => { if (st.order || (i > 0 && gk(R[i - 1]) === gk(R[i]))) return ''; const g = gk(R[i]), xs = R.filter((y) => gk(y) === g);
    const tp = xs.filter((y) => R.indexOf(y) < topN && y.pnl && y.pnl.net != null), net = tp.reduce((a, y) => a + y.pnl.net, 0);
    return `<tr class="dt-chiprow"><td colspan="${span}"><span class="st-cap"><b>${hasScore() ? `점수 ${num(g, 1)}` : `칩 ${g}개`}</b> · ${xs.length}종목${tp.length ? ` · 세후 <span class="${signClass(net, NUM) || ''}">${won(net)}</span> · 이긴 것 ${tp.filter((y) => y.pnl.net > 0).length}/${tp.length}` : ' · 손익 셈 밖(상위 밖)'}</span></td></tr>`; };
  // 굳힘 묶음 셈 — 넓은 · 좁은 표 함께(서버 rows[].lock · lockRank · meta.lockAt · lockN)
  const DMk = d.meta || {}, lkAt = Array.isArray(DMk.lockAt) ? DMk.lockAt : [], lkN = Number(DMk.lockN) || null;
  const lkIdx = R.map((x, i) => i).filter((i) => Number(R[i].r.lock) > 0), lkHas = lkIdx.length > 0;
  const lkGroups = lkAt.map((at, j) => ({ n: j + 1, at, idx: lkIdx.filter((i) => Number(R[i].r.lock) === j + 1).sort((p, q) => (Number(R[p].r.lockRank) || 0) - (Number(R[q].r.lockRank) || 0)) }));
  if (lkHas && !lkGroups.some((g) => g.n === st.lockSel && g.idx.length)) st.lockSel = Math.max(...lkIdx.map((i) => Number(R[i].r.lock)));
  const lkAct = lkGroups.find((g) => g.n === st.lockSel);
  const lkRest = R.map((x, i) => i).filter((i) => !(Number(R[i].r.lock) > 0));
  if (!WIDE.matches) {
    // 좁은 폭(모바일 퍼스트 · 재권님 「모바일 퍼스트 적용시킨 화면도」) — 종목 칸 안에 시가총액 · 섹터 · 이벤트를 접어 넣고, 결과 · 손익을 종목 바로 옆에 · 시각 칸은 그 뒤로 밀어 봄
    // 굳힘 목록 — 넓은 표와 같은 셈(좁은 폭 · qa · 개념정의 검수 덧)
    const rowN = (x, i) => { const r = x.r; return `${grp(i, times.length + 9)}<tr>${rk(r, i)}<td class="st-name" data-co="${esc(r.code || '')}"><b>${esc(r.name || '—')}</b><small class="dt-sub">${capTxt(r.cap)} · ${esc(r.sector || '섹터 —')}</small><span class="dt-evs">${evHtml(r.chips, r)}</span></td>${resTd(x)}${plTd(x, i)}${buyTd(r)}${p1Td(r)}${inTd(r)}${times.map((t, k) => cell(x, k)).join('')}${nxTd(r)}<td class="dt-tx">${taxTxt(x.r)}</td></tr>`; };
    const strip = (h) => h.replace(/^<tr class="dt-chiprow">[\s\S]*?<\/tr>/, '');
    const lkN2 = !lkHas ? '' : `<tr class="dt-chiprow dt-lock"><td colspan="${times.length + 9}"><span class="st-cap"><b>굳힘</b> ${lkGroups.map((g) => `<button type="button" class="kh-chip${g.n === st.lockSel ? ' is-active' : ''}" data-lock="${g.n}"${g.idx.length ? '' : ' disabled'}>${esc(String(g.at))} · ${g.idx.length ? num(g.idx.length) : '아직'}</button>`).join(' ')}</span></td></tr>${lkAct ? lkAct.idx.map((i) => strip(rowN(R[i], i))).join('') : ''}`;
    const lkLive2 = !lkHas ? '' : `<tr class="dt-chiprow"><td colspan="${times.length + 9}"><span class="st-cap"><b>진행 중</b> · ${num(lkRest.length)}종목 — 아직 안 굳음</span></td></tr>`;
    const lkBody2 = !lkHas ? R.map(rowN).join('') : lkRest.map((i) => strip(rowN(R[i], i))).join('');
    $('dt-box').innerHTML = `<table class="dt-tb dt-narrow">
    <tr><th class="dt-rk"></th><th class="st-name">종목</th><th class="dt-res">결과</th><th class="dt-pl">손익</th><th>매수가</th><th class="dt-nx">${p1At}<small>9시1분</small></th><th class="dt-in">들어온 가격</th>${times.map((t) => `<th>${hmTxt(t)}</th>`).join('')}<th class="dt-nx">다음 날 프리장 ${nxAt || ''}</th><th class="dt-tx">세금 %</th></tr>
    ${chipRow(times.length + 9)}
    ${lkN2}<tr class="dt-avg"><td class="dt-rk"></td><td class="st-name">평균</td><td class="dt-res">${pct(resAvg)}</td><td class="dt-pl">${P ? won(P.net) : '—'}</td><td></td>${p1Avg}<td class="dt-in"></td>${avg.map((x) => `<td>${pct(x)}</td>`).join('')}${nxAvg}<td class="dt-tx"></td></tr>
    ${lkLive2}${lkBody2}
  </table>`;
    return;
  }
  // 넓은 폭 — 칩마다 세로 칸(위 「칩 칸」) · 칩 줄 자리에는 어제 미국장만 남김
  const CS = colsOf(), nCol = CS.length;
  // 매수가 규칙(11-20 재권님 「판에 들어있으면 9시 1분가격으로 적고 판에 들어오면 들어올때 가격으로」 · 서버 개발2) — 그 규칙으로 지은 판(줄에 buyTs · buySrc 「9시 1분 값」)만 머리 글을 바꿈 · 옛 판은 「시가」 그대로
  const newBuy = newBuyOf(d);
  const chHead = (c) => { const on = !st.off.has(c), ms = st.miss.has(c), n = all.filter((r) => (r.chips || []).includes(c)).length;
    const subs = subOrder(c, [...new Set(all.flatMap((r) => subsOf(r, c)))]);
    const tip = ms ? ` data-tip="${esc(`그날 판에 ${c} 값을 ${missWord()} — 걸린 종목이 있어도 0 으로 셈됨`)}"` : tipAt(c);
    return `<th class="dt-chc${on ? '' : ' is-off'}"><span class="dt-cg${on ? '' : ' is-off'}${ms ? ' is-miss' : ''}" data-i="${colorOf(c)}"><button type="button" class="dt-mc${on ? ' is-on' : ''}" data-col="${esc(c)}"${tip} aria-haspopup="menu">${esc(c)}${ms ? '' : `<b>${n}</b>`}</button>${
      subs.length ? `<span class="dt-subs">${subs.map((x) => { const k = `${c}|${x}`, son = on && !st.subOff.has(k); return `<button type="button" class="dt-sub-chip${son ? ' is-on' : ''}" data-sub="${esc(k)}"${tipAt(k)} aria-pressed="${son}"${on ? '' : ' disabled'}>${esc(subName(c, x))}<b>${all.filter((r) => subsOf(r, c).includes(x)).length}</b></button>`; }).join('')}</span>` : ''}</span><small>${on ? (ms ? missWord() : st.wait.has(c) ? `${st.openAt ? hmTxt(String(st.openAt).replace(':', '')) : '정규장'} 뒤` : '켜짐') : '꺼짐'}</small></th>`; };
  const chCell = (r, c) => { const on = !st.off.has(c), has = (r.chips || []).includes(c), sb = has ? subsOf(r, c) : [];
    const vt = has && c === 'VI·급등' ? viTxt(r) : '';
    // 하위 칩을 붙은 차례대로 각각 · 그 옆에 처음 붙은 시각(11-20 재권님 「외국인 기관으로 바뀌면 둘다 있어야해 수급칩은 각각 다 보이게 해주고 추가된 칩은 추가된 시간도」) — 서버 rows[].subAt{칩:{하위:HH:MM:SS}}(개발2) 이 있을 때만 · 없으면 옛 모양
    const at = has && r.subAt && r.subAt[c], raw = at ? subsRaw(r, c) : [];
    const each = raw.length ? raw.map((x) => `<i class="dt-chs">${esc(subName(c, x))}</i>${at[x] ? `<small>${esc(String(at[x]))}</small>` : ''}`).join('') : '';
    const v = has ? `<span class="dt-cg" data-i="${colorOf(c)}">${each || (sb.length ? `<i class="dt-chs">${esc(subTxt(c, sb))}</i>` : '<b class="dt-dot" aria-label="걸림"></b>')}${vt ? `<small>${esc(vt)}</small>` : ''}</span>`
      : st.miss.has(c) ? `<span class="dt-chq" data-tip="${esc(`그날 판에 ${c} 값을 ${missWord()} — 이 종목이 걸렸는지 모름`)}">—</span>`
      : st.wait.has(c) ? `<span class="dt-chq" data-tip="${esc(`아직 때가 아님 — ${c} 은 정규장${st.openAt ? `(${st.openAt})` : ''} 뒤에 셈`)}">·</span>` : '';
    return `<td class="dt-chc${on ? '' : ' is-off'}">${v}</td>`; };
  const chBlank = (th) => CS.map(() => `<${th} class="dt-chc"></${th}>`).join('') + `<${th} class="dt-ovn"></${th}><${th} class="dt-addc"></${th}>`;
  // 어제 미국장 — 시각 눈금 줄(둘째 머리줄)의 왼쪽 빈칸(종목 ~ 매수가 아래)에 넣음 · 머리줄과 함께 위에 붙음(11-19 재권님 「단타에 어제미국장 목록을 시간나오는곳 라인으로 맞춰서 거기에 있도록 해줘」) — 전에는 머리줄 아래 따로 한 줄
  const usTh = `<th class="dt-ust" colspan="${CS.length + 7}" style="text-align: left; white-space: normal; font-weight: 400;"><span class="dt-us" id="dt-us" data-day="${esc(d.day || '')}">${usHtml(d.day)}</span></th>`;   // 줄바꿈 · 왼쪽 맞춤은 이 칸만(머리 칸 기본은 한 줄 · 오른쪽)
  // 굳힘 목록(11-20 재권님 「평균 바로 위에 굳힘목록 만들어줘 굳힘시간() 넣어서」 → 「굳힌 종목은 시간대별로 버튼 누르면 볼수있게 해줘」 → 그림에 「응 올려」)
  //   서버(개발2) rows[].lock(몇 번째 굳힘) · lockAt · lockRank · meta.lockAt · lockN — 굳힌 줄은 평균 위에 누른 시각 묶음만 · 안 굳은 줄은 평균 아래 「진행 중」 · 굳힘 없으면(09:05 전 · 옛 판) 지금 모양
  const rowOf = (x, i) => { const r = x.r; return `${grp(i, times.length + nCol + 13)}<tr>${rk(r, i)}<td class="st-name" data-co="${esc(r.code || '')}"><b>${esc(r.name || '—')}</b> <small>${esc(r.code || '')}</small></td><td>${capTxt(r.cap)}</td><td class="dt-sec">${esc(r.sector || '—')}</td>${CS.map((c) => chCell(r, c)).join('')}<td class="dt-ovn"><b>${nLive(r)}</b>${hasScore() ? `<small>· 점수 ${num(scoreOf(r), 1)}</small>` : ''}${(() => { const k = CS.filter((c) => !st.off.has(c) && st.miss.has(c) && !(r.chips || []).includes(c)).length; return k ? `<small class="dt-ovm">못 받은 칩 ${k}</small>` : ''; })()}</td><td class="dt-addc"></td>${buyTd(r)}${p1Td(r)}${inTd(r)}${times.map((t, k) => cell(x, k)).join('')}${resTd(x)}${nxTd(r)}<td class="dt-tx">${taxTxt(x.r)}</td>${plTd(x, i)}</tr>`; };
  const lkSpan = times.length + nCol + 13;
  const lkTop = !lkHas ? '' : `<tr class="dt-chiprow dt-lock"><td colspan="${lkSpan}"><span class="st-cap"><b>굳힘</b> ${lkGroups.map((g) => `<button type="button" class="kh-chip${g.n === st.lockSel ? ' is-active' : ''}" data-lock="${g.n}"${g.idx.length ? '' : ' disabled'}>${esc(String(g.at))} · ${g.idx.length ? num(g.idx.length) : '아직'}</button>`).join(' ')} — 누른 시각에 굳힌 종목${lkN ? `(그때까지 든 종목 중 차례 위 ${num(lkN)}개)` : ''} · 이 뒤로 안 바뀜</span></td></tr>${lkAct ? lkAct.idx.map((i) => rowOf(R[i], i).replace(/^<tr class="dt-chiprow">[\s\S]*?<\/tr>/, '')).join('') : ''}`;
  const lkLive = !lkHas ? '' : `<tr class="dt-chiprow"><td colspan="${lkSpan}"><span class="st-cap"><b>진행 중</b> · ${num(lkRest.length)}종목 — 아직 안 굳음 · 다음 굳힘 때 그 시각 단추로 옮겨 감</span></td></tr>`;
  const lkBody = !lkHas ? R.map(rowOf).join('') : lkRest.map((i) => rowOf(R[i], i).replace(/^<tr class="dt-chiprow">[\s\S]*?<\/tr>/, '')).join('');
  $('dt-box').innerHTML = `<table class="dt-tb dt-cols">
    <tr><th class="dt-rk"></th><th class="st-name">종목</th><th>시가총액</th><th class="dt-sec">섹터</th>${CS.map(chHead).join('')}<th class="dt-ovn" data-tip="켜진 칩 중 몇 개에 걸렸나 — 순위가 이 수로 정해짐">겹침</th><th class="dt-addc"><button type="button" class="kh-chip" data-addcol aria-haspopup="menu">+ 칩</button></th><th>매수가 ${(st.set.buy || 'open') !== 'open' ? buyName(...(BUYS.find(([k]) => k === st.set.buy) || BUYS[0])) : newBuy ? '<small>9시 1분 값 · 뒤에 든 종목은 든 때 값</small>' : st.openAt ? `${hmTxt(String(st.openAt).replace(':', ''))} 시가` : hmTxt(d.buyAt)}</th><th class="dt-nx" data-tip="이쯤 산다면 — 09:01 값의 09:00 시가 대비 % (매수 타이밍을 바꿔도 이 칸은 시가 대비)">${p1At}</th><th class="dt-in" data-tip="9시 1분 뒤 판에 든 종목 — 든 순간 가격 · 그 아래 든 시각">들어온 가격</th><th class="dt-gp" colspan="${times.length}"><span>매수가 대비</span></th><th class="dt-res">결과</th>${nxH1}<th class="dt-tx">세금 %</th><th class="dt-pl">손익 · 종목마다 ${manTxt(per)}</th></tr>
    <tr class="dt-t2">${usTh}<th class="dt-nx">9시1분</th><th class="dt-in">든 시각</th>${times.map((t) => `<th>${hmTxt(t)}</th>`).join('')}<th class="dt-res">판 값 · 시각</th>${nxH2}<th class="dt-tx">거래세 · 농특세</th><th class="dt-pl">세금 · 수수료 뺌 · 상위 ${topN}</th></tr>
    ${lkTop}<tr class="dt-avg"><td class="dt-rk"></td><td class="st-name">평균 <small>판 종목은 판 값으로</small></td><td></td><td class="dt-sec"></td>${chBlank('td')}<td></td>${p1Avg}<td class="dt-in"></td>${avg.map((x, i) => `<td class="${i === L ? 'dt-last' : ''}">${pct(x)}</td>`).join('')}<td class="dt-res">${pct(resAvg)}</td>${nxAvg}<td class="dt-tx"></td><td class="dt-pl">${P ? won(P.net) : '—'}<small>${P ? `빼기 전 ${won(P.gross)}` : ''}</small></td></tr>
    ${lkLive}${lkBody}
  </table>`;
  // 둘째 머리 줄(시각)은 첫 머리 줄(칩) 높이만큼 내려 붙임 — 둘 다 top 0 이라 스크롤하면 시각 줄이 칩 줄을 덮었음(11-18 재권님 「단타 목록 스크롤하면 칩들이 안보이는 현상이 있는데 이거 고쳐줘」)
  { const tb = $('dt-box').querySelector('.dt-cols'), h1 = tb && tb.rows[0] ? tb.rows[0].getBoundingClientRect().height : 0; if (tb) tb.querySelectorAll('.dt-t2 th').forEach((th) => { th.style.top = `${h1}px`; }); }
}

// 날짜 — 달 줄 위 · 고른 달의 날짜 줄 아래(11-12 재권님 「달이 있어야 되고 해당달하위로 날짜가 있도록 해줘 이정보는 많이 쌓아가야 할거같아. 현재 30개이지만 룰이 확립되면 많이 늘릴거야」)
//   몇 날을 두는지는 서버(meta.daysKeep) 한 곳 — 화면은 서버가 준 날을 다 그린다 · 달 칩 옆 수 = 그 달에 쌓인 날 수
const monOf = (d) => String(d || '').slice(0, 6);
const monTxt = (m) => (m.length === 6 ? `${m.slice(0, 4)}년 ${+m.slice(4)}월` : '—');
// 이달 합계 (11-18 재권님 「11월달 세후손익 다 더해봐」 · 「지금 내가 물어본거를 단타 에서 소팅할수 있게」) — 고른 달의 날마다 판을 서버에서 받아 같은 셈(calc) · 지금 셈 칸 · 칩 켜고 끔을 따름
//   지난 날 판은 한 번 받아 두고(굳힌 값이라 안 바뀜) · 장중인 날은 지금 보는 판(st.data)을 씀 · 못 받은 날은 「못 받음」 으로 내고 합계에서 뺌(0 으로 안 셈)
const dayData = {};
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
      st.rng = F && T ? (F <= T ? { from: F, to: T } : { from: T, to: F }) : null; rngSave(); monthPaint(); });
    b.addEventListener('click', (e) => { if (e.target.closest('[data-rng-off]')) { st.rng = null; rngSave(); monthPaint(); }
      if (e.target.closest('[data-bymon]')) { st.byMon = !st.byMon; try { localStorage.setItem(RNG_KEY + '-mon', st.byMon ? '1' : '0'); } catch (x) { /* 못 남겨도 됨 */ } monthPaint(); } });
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
  if (need.length) {
    el.textContent = `${ttl} 날마다 판 받는 중… (${ds.length - need.length}/${ds.length})`;
    await Promise.all(need.map(async (d) => { try { const r = await fetch(`${API}?day=${d}`, { cache: 'no-store' }); const j = r.ok ? await r.json() : null; dayData[d] = j && j.data && j.data.day === d ? renameChips(j.data) : null; } catch (e) { dayData[d] = null; } }));
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
  const parts = ds.slice().reverse().map((d) => { const D = get(d); if (!D) { miss.push(dayTxt(d)); return `<span>${dayTxt(d)} <span class="st-err">못 받음</span></span>`; }
    const C = calc(D); if (!C.P) return `<span>${dayTxt(d)} 매매 없음</span>`;
    cnt++; tot += C.P.net; if (C.P.net > 0) won0++; else if (C.P.net < 0) lost++;
    return `<span>${dayTxt(d)} <span class="${signClass(C.P.net, NUM) || ''}">${won(C.P.net)}</span>${C.LIVE ? '<small>장중</small>' : ''}</span>`; });
  el.innerHTML = `<b>${ttl} 합계 — 지금 칸 · 칩대로 · 세후 <span class="${signClass(tot, NUM) || ''}">${won(tot)}</span></b> · 매매한 날 ${cnt} · 번 날 ${won0} · 잃은 날 ${lost}${miss.length ? ` · 못 받은 날 ${miss.length}(합계에서 뺌)` : ''}<br>${parts.join(' · ')}`;
}
function chips() {
  if (!st.days.length) { $('dt-days').innerHTML = ''; monthPaint(); return; }
  const mons = [...new Set(st.days.map(monOf))];
  if (!mons.includes(st.mon)) st.mon = monOf(st.day) || mons[0];
  const cnt = (m) => st.days.filter((d) => monOf(d) === m).length;
  const dayBtn = (d) => { const a = st.last[d]; return `<button type="button" class="kh-chip${d === st.day ? ' is-active' : ''}" role="tab" aria-selected="${d === st.day}" data-day="${d}">${dayTxt(d)}${a == null ? '' : `<small class="${signClass(a, NUM) || ''}">${a > 0 ? '+' : ''}${num(a, 1)}%</small>`}</button>`; };
  $('dt-days').innerHTML = `<div class="dt-mons" role="tablist" aria-label="달">${mons.map((m) => `<button type="button" class="dt-mon${m === st.mon ? ' is-on' : ''}" role="tab" aria-selected="${m === st.mon}" data-mon="${m}">${monTxt(m)}<small>${cnt(m)}일</small></button>`).join('')}</div>`
    + `<div class="dt-dlist" role="tablist" aria-label="날짜">${st.days.filter((d) => monOf(d) === st.mon).map(dayBtn).join('')}</div>`;
  monthPaint();   // 달이 정해진 뒤 — 고른 달 합계
}
BIND.push(() => $('dt-days').addEventListener('click', (e) => {
  const mb = e.target.closest('[data-mon]');
  if (mb) { if (mb.dataset.mon !== st.mon) { st.mon = mb.dataset.mon; chips(); } return; }   // 달만 바꿈 — 날짜는 그 달 줄에서 고름(판은 그대로)
  const b = e.target.closest('[data-day]'); if (b && b.dataset.day !== st.day) { st.mon = monOf(b.dataset.day); load(b.dataset.day); }
}));

// 장중이면 서버가 정한 주기(meta.refreshMs)로 같은 날을 다시 받는다 — 주기 숫자를 화면에 두지 않는다(「캐시·주기·한도 값을 화면에 박지 않는다」) · 서버가 안 주면 다시 안 받음
let again = null;
async function load(day, quiet) {
  const my = ++st.seq;
  clearTimeout(again); again = null;
  if (!quiet) $('dt-meta').textContent = '값을 받는 중…';
  let r = null, j = null;
  try { r = await fetch(day ? `${API}?day=${day}` : API, { cache: 'no-store' }); j = await r.json().catch(() => null); } catch (e) { r = null; }
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
  const d = renameChips(j.data), m = renameChips(j.meta || {});
  st.days = Array.isArray(m.days) ? m.days : [d.day];   // 몇 날을 두는지는 서버(daysKeep) 한 곳 — 화면은 자르지 않음(11-12 재권님 「룰이 확립되면 많이 늘릴거야」)
  st.day = d.day; st.data = d;
  if (st.sfDay !== d.day) { st.sfDay = d.day; loadSector(d.day); }   // 날을 바꿀 때만 — 다시 받는 간격은 섹터수급 쪽이 서버 값으로
  if (d.day === st.days[0]) viLoad(d.day);   // 오늘(맨 앞 날) 판만 — 시각 주소가 오늘 것만 준다
  if (d.day === st.days[0] && !wx.data && !wx.timer) wxLoad();   // 지금 바깥 값 — 처음 한 번 · 그 뒤는 서버 ttlSec 대로
  if (st.vdDay !== d.day) { st.vdDay = d.day; vdLoad(d.day); }   // 그날 VI 목록 — 날을 바꿀 때만(지난 날은 굳은 값 · 오늘은 판을 다시 열 때)
  paint(d);
  chips();
  const ms = Number(m.refreshMs ?? (d.meta && d.meta.refreshMs)); st.ms = ms > 0 ? ms : 0;   // 서버는 판 안 meta(data.meta)에 둔다(개발2 2단계 · 11-12 09:07 잼) — 바깥 meta 도 읽음
  // 오늘 판이면 굳기(closed) 전까지 서버 주기로 다시 받음 — 장 전(08:00~09:00) 줄에 now 가 없어도 칩이 바뀌므로 now 로 가르지 않음(11-20 재권님 「8시되면 갱신되야 되는거지? 실시간으로?」 → 「응 고쳐」)
  const t0 = new Date(), today = `${t0.getFullYear()}${String(t0.getMonth() + 1).padStart(2, '0')}${String(t0.getDate()).padStart(2, '0')}`;
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
BIND.push(() => $('dt-order').addEventListener('click', (e) => { const b = e.target.closest('[data-order]'); if (!b || b.dataset.order === st.order) return; st.order = b.dataset.order; if (st.data) { paint(st.data); chips(); } }));
BIND.push(() => $('dt-box').addEventListener('click', (e) => { const b = e.target.closest('[data-lock]'); if (!b || b.disabled) return; st.lockSel = Number(b.dataset.lock); if (st.data) paint(st.data); }));   // 굳힘 시각 단추
BIND.push(() => $('dt-only').addEventListener('click', (e) => { const b = e.target.closest('[data-only]'); if (!b || b.dataset.only === st.only) return; st.only = b.dataset.only; if (st.data) { paint(st.data); chips(); } }));

async function loadFee() {
  try { const r = await fetch(DOC, { cache: 'no-store' }); const j = r.ok ? await r.json() : null; const R0 = j && j.data && j.data.rules && j.data.rules.dt30 ? j.data.rules.dt30 : {}; const v = R0.feePct; st.fee = v == null || v === '' ? null : Number(v);
    st.set = { ...DEF_SET, ...(R0.set && typeof R0.set === 'object' ? R0.set : {}), mode: 'day' };
    st.score = R0.score && typeof R0.score === 'object' ? R0.score : {};   // 돈은 늘 전체 금액 ÷ 종목 수
    if (R0.set && R0.set.mode === 'each' && R0.set.perWon) st.set.dayWon = R0.set.perWon * (st.set.top || PNL_TOP); }   // 옛 저장값(종목마다)은 같은 돈이 되게 옮김
  catch (e) { st.fee = null; st.set = { ...DEF_SET }; }
  $('dt-fee').value = st.fee == null ? '' : String(st.fee);
  setFill();
}
// 셈 칸에 지금 값 채우기 · 단추 켜짐 표시
function setFill() {
  const S = st.set, box = $('dt-pnl'); if (!box) return;
  const v = { minChip: S.minChip || '', top: S.top, won: (S.mode === 'day' ? S.dayWon : S.perWon) / 10000, stop: S.stop == null ? '' : S.stop, trail: S.trail == null ? '' : S.trail, turnPct: S.turnPct || '' };
  box.querySelectorAll('[data-set]').forEach((el) => { if (document.activeElement !== el) el.value = String(v[el.dataset.set] ?? ''); });
  box.querySelectorAll('[data-mode]').forEach((b) => b.classList.toggle('is-active', b.dataset.mode === S.mode));
  box.querySelectorAll('[data-turn]').forEach((b) => b.classList.toggle('is-active', (b.dataset.turn === '1') === !!S.turn));
  box.querySelectorAll('[data-turnby]').forEach((b) => b.classList.toggle('is-active', b.dataset.turnby === (S.turnBy || 'both')));
  box.querySelectorAll('[data-turnfor]').forEach((el) => { const tb = S.turnBy || 'both'; el.hidden = tb !== 'both' && el.dataset.turnfor !== tb; });
  box.querySelectorAll('[data-turnsep]').forEach((el) => { el.hidden = (S.turnBy || 'both') !== 'both'; });   // 둘 다일 때 두 설명 사이 · (qa 11-20 좁은 폭에서 붙어 보임)
  box.querySelectorAll('[data-buy]').forEach((b) => { b.classList.toggle('is-active', b.dataset.buy === (S.buy || 'open')); const B = BUYS.find(([k]) => k === b.dataset.buy); if (B) b.textContent = buyName(...B); });   // 이름 시각은 그 판 서버 값(늦게 여는 날)
  box.querySelectorAll('[data-pyr]').forEach((b) => b.classList.toggle('is-active', (b.dataset.pyr === '1') === !!S.pyr));
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
  const msg = $('dt-set-msg');
  st.set = next; setFill();
  if (st.data) { paint(st.data); chips(); }
  msg.textContent = '저장하는 중…';
  try { await saveDt({ set: next }); msg.textContent = '저장됨 — 다시 셈'; }
  catch (e) { msg.textContent = `화면은 다시 셈 · 저장 못 함(${e.message || '연결 안 됨'})`; }
}
function setRead(el) {
  const k = el.dataset.set, raw = el.value.trim().replace(/,/g, ''), S = { ...st.set };
  const bad = (t) => { $('dt-set-msg').textContent = `${t} — 되돌렸습니다`; setFill(); return null; };
  const v = raw === '' ? null : Number(raw);
  if (v != null && !Number.isFinite(v)) return bad('숫자만');
  if (k === 'minChip') { if (v != null && (v < 0 || !Number.isInteger(v))) return bad('0 이상 정수'); S.minChip = v || 0; }
  else if (k === 'top') { if (v == null || v < 1 || !Number.isInteger(v)) return bad('1 이상 정수'); S.top = v; }
  else if (k === 'won') { if (v == null || v <= 0) return bad('0 보다 큰 만원'); S[S.mode === 'day' ? 'dayWon' : 'perWon'] = Math.round(v * 10000); }
  else if (k === 'stop') { if (v === 0) return bad('0 은 못 씀 · 빈칸이면 손절 안 함'); S.stop = v == null ? null : -Math.abs(v); }   // 1 · −1 둘 다 「−1%」 로
  else if (k === 'turnPct') { S.turnPct = v == null ? 0 : Math.abs(v); }
  else if (k === 'trail') { if (v === 0) return bad('0 은 못 씀 · 빈칸이면 안 씀'); S.trail = v == null ? null : Math.abs(v); }
  return S;
}
BIND.push(() => {
  const box = $('dt-pnl');   // 셈 칸 줄 + 손익 머리 줄(상위 · 금액)
  box.addEventListener('change', (e) => { const el = e.target.closest('[data-set]'); if (!el) return; const S = setRead(el); if (S) setChange(S); });
  box.addEventListener('click', (e) => {
    const m = e.target.closest('[data-mode]'); if (m) { e.preventDefault(); if (m.dataset.mode !== st.set.mode) setChange({ ...st.set, mode: m.dataset.mode }); return; }
    const bb = e.target.closest('[data-buy]'); if (bb) { e.preventDefault(); if (bb.dataset.buy !== (st.set.buy || 'open')) setChange({ ...st.set, buy: bb.dataset.buy }); return; }
    const y = e.target.closest('[data-pyr]'); if (y) { e.preventDefault(); const on = y.dataset.pyr === '1'; if (on !== !!st.set.pyr) setChange({ ...st.set, pyr: on }); return; }
    const tb = e.target.closest('[data-turnby]'); if (tb) { e.preventDefault(); if (tb.dataset.turnby !== (st.set.turnBy || 'both')) setChange({ ...st.set, turnBy: tb.dataset.turnby }); return; }
    const t = e.target.closest('[data-turn]'); if (t) { e.preventDefault(); const on = t.dataset.turn === '1'; if (on !== !!st.set.turn) setChange({ ...st.set, turn: on }); return; }
    if (e.target.closest('[data-reset]')) setChange({ ...DEF_SET });
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
BIND.push(() => bindWin($('dt-win')));
BIND.push(() => mountSector($('dt-sf')));
WIDE.addEventListener('change', () => { if (root && st.data) paint(st.data); });   // 창 폭이 700 을 넘나들면 칸 차례만 다시


// 그릇에 그리기 (11-13 재권님 「단타 창 모달로 띄울수있게 자세히 버튼 넣어줘」 · 개발1 과 맞춤 · 같은 날 재권님이 홈 모달은 거두심 「홈 모달말고 단타 창에서 모달로 바로」) — 지금은 투자 전략 화면(#dt-host)만 쓴다 · 다른 자리에서 띄울 때 이 한 벌을 가져다 쓴다
//   mountDt30(host)  host 안에 판 칸을 만들고 그림 · 칸은 host 안에서만 찾는다 · 모양은 company-setup/css/strategy.css 의 .dt 묶음(거는 쪽이 그 파일을 건다)
//   unmountDt30()    다시 받기 타이머 · 열린 칸 메뉴를 거둠 — 모달을 닫을 때 부른다(안 부르면 장중 주기로 계속 받는다)
//   host 에 class 「st dt」 가 없으면 붙인다(.dt 아래 모양이 듣게)
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
          <div class="dt-set" id="dt-set" aria-label="셈 칸 — 넣으면 저장되고 바로 다시 셈">
            <div style="display:flex;justify-content:flex-end;align-items:baseline;gap:8px"><span id="dt-set-msg" class="rl-sug"></span> <button type="button" class="kh-chip" data-reset>기본값으로</button></div>
            <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:stretch;margin:4px 0">
              <div class="dt-set-buy" style="flex:1 1 360px;min-width:0;word-break:keep-all;display:flex;flex-direction:column;gap:4px;padding:8px 12px;border-radius:var(--kh-radius-sm);background:var(--kh-bg-card)"><b style="font-size:12px">매수</b>
                <label class="dt-fee">칩 <input data-set="minChip" class="rl-in rl-num" inputmode="numeric" aria-label="칩 몇 개 이상만">개 이상 <span class="rl-sug">빈칸 = 전체</span></label>
                <label class="dt-fee" data-tip="고른 때 값에 삽니다 · 그 값이 없는 종목은 안 삽니다 · 파는 룰은 산 뒤 30분 칸(09:30 · 10:00 …)부터">매수 <span class="dt-seg">${BUYS.map(([k, t]) => `<button type="button" class="kh-chip" data-buy="${k}">${t}</button>`).join('')}</span></label>
                <label class="dt-fee" data-tip="손절로 판 돈을 그 시각 가장 많이 오른 종목에 더 삽니다 · 더 산 몫은 그 종목을 팔 때 함께 팝니다">불타기 <span class="dt-seg"><button type="button" class="kh-chip" data-pyr="1">켬</button><button type="button" class="kh-chip" data-pyr="0">끔</button></span></label>
              </div>
              <div class="dt-set-sell" style="flex:1 1 360px;min-width:0;word-break:keep-all;display:flex;flex-direction:column;gap:4px;padding:8px 12px;border-radius:var(--kh-radius-sm);background:var(--kh-bg-card)"><b style="font-size:12px">매도</b>
                <label class="dt-fee">손절 <input data-set="stop" class="rl-in rl-num" inputmode="decimal" aria-label="손절(매수가 대비 %)">% <span class="rl-sug">빈칸 = 안 함</span></label>
                <label class="dt-fee">꺾임 <span class="dt-seg"><button type="button" class="kh-chip" data-turn="1">켬</button><button type="button" class="kh-chip" data-turn="0">끔</button></span> <span class="dt-seg"><button type="button" class="kh-chip" data-turnby="prev">앞 시각 대비</button><button type="button" class="kh-chip" data-turnby="peak">고점 대비</button><button type="button" class="kh-chip" data-turnby="both">둘 다</button></span> <span data-turnfor="prev">앞 시각보다 <input data-set="turnPct" class="rl-in rl-num" inputmode="decimal" aria-label="꺾임 — 앞 시각보다 몇 % 넘게 내리면 팜">% 넘게 내리면 팜 <span class="rl-sug">그 이하는 무시 · 빈칸 = 0</span></span><span data-turnsep hidden> · </span><span data-turnfor="peak" hidden>오른 뒤 가장 높던 값보다 <input data-set="trail" class="rl-in rl-num" inputmode="decimal" aria-label="꺾임 — 고점 대비 몇 % 내리면 팜">% 내리면 팜 <span class="rl-sug">빈칸 = 안 씀</span></span></label>
                <label class="dt-fee">증권수수료 <input id="dt-fee" class="rl-in rl-num" inputmode="decimal" aria-label="증권수수료(%) — 팔 때만" placeholder="( )">% <span class="rl-sug">팔 때만 · 넣으면 저장되고 바로 다시 셈</span> <span id="dt-fee-msg" class="rl-sug"></span></label>
              </div>
            </div>
          </div>
          <div class="st-cap" id="dt-month">—</div>
          <details class="dt-win" id="dt-win"><summary>칩별 승률 — 지난 30거래일 · 세후 · 칩 묶음마다 승률 · 날마다 이익 큰 종목</summary><div class="dw-body"></div></details>
          <details class="dt-win" id="dt-vi"><summary>그날 VI 목록 — 발동 · 풀림 시각 · 정적/동적 · 발동가 · <span class="dt-vi-sum">—</span></summary><div class="dw-body"></div></details></div>
        <div class="dt-box st-scroll wheel-stop" id="dt-box"><div class="st-err">—</div></div>
        <div class="st-cap dt-foot">각 시각 = 그 시각에 끝난 5분봉 종가 · 평균 = 그 시각 값이 있는 종목만 · 단타 목록은 <span class="dt-at">—</span> 에 그날 판을 열고, 굳히기 전까지는 다시 세어 줄이 바뀜(늦게 든 칩 · 빠진 종목 · 빠졌다 다시 든 종목은 다시 든 때 가격) · 굳힘 시각마다 그때 차례 위 종목을 굳히고 굳힌 종목은 그날 안 빠짐 · 굳힌 뒤에는 늦게 나온 칩만 채움</div>
      </div>
      <div class="st-card sf" id="dt-sf"><div class="sf-h"><b>섹터수급 — 같은 업종 · 테마에 돈이 들어오나 · 프리장 08:00 ~ 정규장 09:30</b> <span class="dt-seg sf-by" role="tablist" aria-label="업종 · 테마"></span></div><div class="sf-body"><div class="st-err">—</div></div></div>`;
// 「룰 — 단타」 칸이 점수표를 바꿀 때 — 바로 다시 셈하고 룰 문서에 저장(같은 문서 · 같은 저장 길)
export async function setDtScore(score) {
  st.score = score && typeof score === 'object' ? score : {};
  if (root && st.data) { paint(st.data); chips(); }
  await saveDt({ score: st.score });
}
export const dtChips = () => [...colsOf()];   // 단타 판 칸의 칩 — 서버가 칩 목록을 안 줄 때 점수 칸이 고를 조건
export function mountDt30(host) {
  if (!host) return;
  unmountDt30();
  host.classList.add('st', 'dt');
  host.innerHTML = TPL;
  root = host;
  BIND.forEach((f) => f());
  loadFee().then(() => { if (root === host) load(); });
}
export function unmountDt30() {
  clearTimeout(again); again = null; st.seq++;   // 받는 중이던 값은 버린다(load 가 seq 로 가름)
  menuClose(); root = null; st.sfDay = null; mountSector(null);
}
const host0 = document.getElementById('dt-host');
if (host0) mountDt30(host0);
