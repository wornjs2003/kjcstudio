// 투자 전략 「단타 30」 — 09:06 매수 → 30분마다 14:00 까지 · 30거래일 (2026-11-11 · 시황분석1)
//   · 재권님 「단타 목록 상위 30개를 소팅해서 9시 6분에 배수하고 9시반 10시 등 30분 단위로 2시까지 가격 추적하도록 셋팅해줘, 아래에 프리장 넣기 처럼 그 위에 종목 넣어서」 →
//     시안 temp/시황분석1-dt30-1743 → 「응 이대로 만드는데 위에 날짜도 넣어줘 30일 추적가능하도록」
//   · 그날 판(09:06 에 굳힌 단타 상위 30 · 매수가 · 각 시각 값)과 쌓인 날 목록은 서버 한 곳 — 화면은 그리기만(매수가 대비 % · 평균은 받은 값으로 셈)
//     응답(안 · 서버 레인과 맞춤): data { day, buyAt, times[HHMM], rows[{rank, code, name, cap(억원), sector(WICS), chips[], buy, px{HHMM: 값}}] } · meta { days[YYYYMMDD …최근 먼저] }
//   · 값이 없으면 — (0 이 아니다) · 서버를 다시 묻는 주기는 없다(날을 누를 때 · 처음 열 때 한 번)
import { signClass, NUM } from '/assets/js/sign.js';
import { bindWin } from './strategy-dtwin.js';
import { renameChips, chipName } from './strategy-chipname.js';   // 칩 이름을 실시간 순위와 같게(「수급」 → 「자동」 · 11-18) — 서버 값을 받는 자리에서
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
const evChips = (c, r, miss = []) => { const a = [...(Array.isArray(c) ? c : []), ...miss]; if (!a.length) return '<span class="st-err">—</span>'; a.sort((x, y) => (EV_ORDER.indexOf(x) + 99) % 99 - (EV_ORDER.indexOf(y) + 99) % 99); return a.map((x) => { const sb = r ? subsOf(r, x) : []; const dim = r && colsOf().includes(x) && !liveChip(r, x); if (miss.includes(x)) return `<span class="dt-evc is-miss" data-tip="${esc(`그날 판에 ${x} 값을 ${missWord()} — 이 종목이 걸렸는지 모름`)}">${esc(x)}</span>`; const vt = r && x === 'VI·급등' ? viTxt(r) : ''; return `<span class="dt-evc${dim ? ' is-off' : ''}">${esc(x)}${sb.length ? `<small>${esc(sb.join('·'))}</small>` : ''}${vt ? `<small>${esc(vt)}</small>` : ''}</span>`; }).join(''); };

const DOC = '/api/board/doc/strategy-rules';   // 수수료 % 를 두는 곳 — 투자 전략 룰 값과 같은 문서(rules.dt30.feePct)
const WIDE = matchMedia('(min-width: 701px)');   // 701 — strategy.css 가 쓰는 넓힘 폭(홀딩스 · Insight 700 경계) · 그보다 좁으면 좁은 폭 차례
const st = { set: null, cols: null, mon: '', off: new Set(), subOff: new Set(), order: '', fee: null, day: null, days: [], seq: 0, last: {}, only: '', data: null };   // only — 이벤트 거르기(재권님 11-11 「vi없는건 제외하고 다시 셈해봐」) · 빈칸이면 전체
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
const VI_SPLIT = '0925';
const VI_SUBS = ['09:25 전', '09:25 이후', '시각 모름'];
const hm4 = (t) => String(t || '').replace(/:/g, '').slice(0, 4);   // 이 칩 셈만으로 돌게 — 아래 매수 타이밍의 hhmm 에 기대지 않음(11-18 메인에 이 커밋만 먼저 가 hhmm 없음으로 단타 판이 멈췄음)
const viFirst = (r) => {
  const t = [r.viAt, r.surgeAt].filter(Boolean).map(hm4);
  if (!t.length) { const o = viAt.map && viAt.day === (st.data && st.data.day) ? viAt.map[r.code] : null; if (o) [o.vi, o.surge].filter(Boolean).forEach((x) => t.push(hm4(x))); }
  return t.length ? t.sort()[0] : null;
};
const subsOf = (r, c) => {
  if (c === 'VI·급등') { if (!(r.chips || []).includes(c)) return []; const t = viFirst(r), rest = subsRaw(r, c).filter((v) => v !== 'VI' && v !== '급등'); return [t == null ? VI_SUBS[2] : t < VI_SPLIT ? VI_SUBS[0] : VI_SUBS[1], ...rest]; }
  const a = subsRaw(r, c), b = BOTH[c]; if (!b) return a;
  const [[x, y], [onlyX, withY]] = b, hx = a.includes(x), hy = a.includes(y);
  const rest = a.filter((v) => v !== x && v !== y);
  return hy ? [withY, ...rest] : hx ? [onlyX, ...rest] : rest;
};
const subOrder = (c, xs) => { const o = c === 'VI·급등' ? VI_SUBS : BOTH[c] ? BOTH[c][1] : []; return xs.sort((p, q) => ((o.indexOf(p) + 99) % 99) - ((o.indexOf(q) + 99) % 99) || p.localeCompare(q)); };
const liveChip = (r, c) => { if (st.off.has(c) || !(r.chips || []).includes(c)) return false; const sb = subsOf(r, c); return !sb.length || sb.some((x) => !st.subOff.has(`${c}|${x}`)); };
const nLive = (r) => colsOf().reduce((a, c) => a + (liveChip(r, c) ? 1 : 0), 0);   // 칸에 있고 켜진 칩만
const riseOf = (r) => (r.rise == null || !Number.isFinite(Number(r.rise)) ? -Infinity : Number(r.rise));   // 초반상승 % — 안 든 종목은 null → 맨 뒤
const byLive = (a, b) => nLive(b) - nLive(a) || (riseOf(b) - riseOf(a) || 0) || (Number(b.cap) || 0) - (Number(a.cap) || 0);   // 겹친 칩 수 → 초반상승 % → 시가총액(재권님 19:1x 말씀 · 개발2 서버 19:14 와 같은 셈 · rows[].rise)
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
const WHEN = {
  관심: '언제 — 전날 장 마감 뒤 정해지고, 장중에는 5분마다 그때 값으로 다시 거름',
  프리장: '언제 — 장 열기 전 08:00~08:50 몇 분마다 셈 · 08:50~09:00 에 그날 것으로 정함',
  'VI·급등': '언제 — 08:00 부터 10초마다(장 열기 전은 넥스트레이드 값) · 단타 판에는 판을 굳히기 전까지 걸린 것만',
  장외: '언제 — 장 끝난 15:40 뒤부터 다음 날 07:30 까지 · 아침 단타 판에는 거의 안 듦',
  매수: '언제 — 외국인 첫 집계 09:30 · 기관 첫 집계 10:00 · 그 전에는 「어림」 으로 먼저 봄',
  초반상승: '언제 — 장 시작 첫 봉이 끝난 뒤부터',   // 봉 길이는 서버 open-rise meta.barMin(11-18 첫 1분봉으로 바뀜 · 시각을 글에 안 박음)
  자동: '언제 — 전날 장 마감 뒤 정해지고, 장중에는 5분마다 그때 값으로 다시 거름',
};
const WHAT = {
  관심: (R) => `관심 목록에 하트로 담은 종목 · 시가총액 ${R && R.capMinEok != null ? `${R.capMinEok.toLocaleString()}억 이상` : '문턱 — 서버 값 못 받음'}`,
  프리장: () => '장 열기 전(넥스트레이드 프리마켓) 전날보다 오르면서 거래대금이 큰 종목',
  장외: () => '장 끝난 뒤(넥스트레이드 애프터마켓 · 다음 날 프리마켓) 그날 종가보다 오른 종목',
  매수: () => '외국인 · 기관이 많이 산 종목(증권사 집계) · ①~④ 는 누가 함께 샀는지',
  초반상승: () => '장 시작 첫 봉에서 시가보다 일정 % 넘게 오른 종목 · ETF 는 뺌',
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
const tipAt = (k) => { const t = tipOf(k); return t ? ` data-tip="${esc(t)}"` : ''; };
function chipPanel(all) {
  return colsOf().map((c) => { const i = colorOf(c);
    const n = all.filter((r) => (r.chips || []).includes(c)).length;
    const subs = subOrder(c, [...new Set(all.flatMap((r) => subsOf(r, c)))]);
    const on = !st.off.has(c);
    // data-i — 칩마다 색(strategy.css 의 .dt-cg[data-i] · theme.css 변수) · 하위 칩은 상위 칩 색을 물려받음
    const ms = st.miss.has(c), tip = ms ? ` data-tip="${esc(`그날 판에 ${c} 값을 ${missWord()} — 걸린 종목이 있어도 0 으로 셈됨${tipOf(c) ? `\n${tipOf(c)}` : ''}`)}"` : tipAt(c);
    return `<span class="dt-cg${on ? '' : ' is-off'}${ms ? ' is-miss' : ''}" data-i="${i}"><button type="button" class="dt-mc${on ? ' is-on' : ''}" data-chip="${esc(c)}"${tip} aria-pressed="${on}">${esc(c)}${ms ? '' : `<b>${n}</b>`}</button>${
      subs.length ? `<span class="dt-subs">${subs.map((x) => { const k = `${c}|${x}`, son = on && !st.subOff.has(k); return `<button type="button" class="dt-sub-chip${son ? ' is-on' : ''}" data-sub="${esc(k)}"${tipAt(k)} aria-pressed="${son}"${on ? '' : ' disabled'}>${esc(x)}<b>${all.filter((r) => subsOf(r, c).includes(x)).length}</b></button>`; }).join('')}</span>` : ''}</span>`;
  }).join('');
}

// 파는 룰 (11-11 재권님 「매수가 대비 1%이상 하락은 매도한다. 상승추세가 꺾이면 판다 라는룰을 추가해서 표기해줘. 표기된 부분부터는 평균에 포함시키지 않는다」)
//   · 30분 시각마다 본다(값이 30분마다라서) — ① 매수가 대비 STOP_PCT% 이하면 판다 ② 앞 시각에 매수가보다 위였는데 이번 시각이 앞 시각보다 낮으면 「상승추세 꺾임」 으로 판다
//   · 판 시각 칸에 「손절」 · 「꺾임」 을 붙이고, 그 칸부터는 흐리게 · 평균에서 뺀다 · 「결과」 칸 = 판 시각 값(안 팔았으면 마지막 시각 값)
//   · ② 「꺾임」 = 앞 시각보다 낮아지면(재권님 11-11 「낮아지면으로 해」) · 숫자는 룰 문서로 옮길 때까지 이 한 곳
// 파는 룰 값을 재권님이 넣는 칸으로 (11-18 재권님 「값을 내가 넣으면 거기에 맞게 소팅되야해 … 파는룰도 내가 바꾸면서 볼려고 하는거야」)
//   · 손절 % (빈칸이면 손절 안 함) · 꺾임 켬/끔 · 고점 대비 −X% (빈칸이면 안 씀 — 11-18 「상승중에 -2%가 되면 매도」 · 매수가보다 오른 뒤 그때까지 가장 높던 값에서 X% 내리면 판다)
//   · 기본값은 지금 룰 그대로(손절 −1 · 꺾임 켬 · 고점 빈칸) — 값은 아래 DEF_SET 한 곳 · 넣은 값은 룰 문서(rules.dt30) 한 곳에 저장
function sellAt(p) {   // p — 시각마다 매수가 대비 %(null 은 값 없음) → { k: 판 시각 차례 또는 -1, why }
  const S = st.set; let pk = 0;
  for (let k = 0; k < p.length; k++) {
    if (p[k] == null) continue;
    if (S.stop != null && p[k] <= S.stop) return { k, why: '손절' };
    let a = k - 1; while (a >= 0 && p[a] == null) a--;
    // 꺾임 폭(11-18 재권님 「꺽임룰에 1%이하는 무시한다로 룰 잡아」 → 「그거말고 꺽임 에 내가 %를 추가할수있게 해줘」) — 셈 칸에 넣은 turnPct% 넘게 앞 시각보다 내릴 때만 꺾임 · 기본 0(지금 룰 그대로)
    if (S.turn && a >= 0 && p[a] > 0 && ((100 + p[k]) / (100 + p[a]) - 1) * 100 < -S.turnPct) return { k, why: '꺾임' };
    if (S.trail != null && pk > 0 && ((100 + p[k]) / (100 + pk) - 1) * 100 <= -S.trail) return { k, why: '고점' };
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
const DEF_SET = { minChip: 0, top: PNL_TOP, mode: 'day', perWon: PNL_WON, dayWon: PNL_TOP * PNL_WON, stop: -1, turn: true, turnPct: 0, trail: null, pyr: false };   // pyr — 불타기(손절로 판 돈을 그 시각 가장 많이 오른 종목에 더 삼) · 기본 끔
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
  return `<span class="dt-hd">어제 미국장</span>${US_NAMES.map(one).join('')}${ovH}`;
};
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
  const n = Math.min(S.top, rows.length), nb = rows.slice(0, n).filter((r) => Number(r.buy) > 0).length;   // 매수가 없는 종목 몫은 나누지 않음(qa 11-18 — 안 쓰는 돈이 생겼음)
  const per = S.mode === 'day' ? (nb ? S.dayWon / nb : 0) : S.perWon;
  const ch = (r, t) => { const b = Number(r.buy), v = Number((r.px || {})[t]); return r.buy == null || (r.px || {})[t] == null || !(b > 0) || !Number.isFinite(v) ? null : (v / b - 1) * 100; };
  const R = rows.map((r) => { const p = times.map((t) => ch(r, t)); const s = sellAt(p); let last = L; while (last >= 0 && p[last] == null) last--; const nowCh = LIVE && s.k < 0 && Number(r.now) > 0 && Number(r.buy) > 0 ? (Number(r.now) / Number(r.buy) - 1) * 100 : null;   // 장중 · 안 판 종목 — 결과 · 손익은 서버 지금 값(rows[].now)
    const at = s.k >= 0 ? s.k : last, sellPx = nowCh != null ? Number(r.now) : at >= 0 ? Number((r.px || {})[times[at]]) : null;
    const b = Number(r.buy), qty = b > 0 ? Math.floor(per / b) : 0;
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
  return { times, all, live, rows, L, LIVE, R, n, nb, per, top, noMkt, P };
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
  const C = calc(d), { times, all, live, rows, L, LIVE, R, n: topN, per, top, noMkt, P } = C;
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
  if (!rows.length) { $('dt-box').innerHTML = '<div class="st-err">— 이 날 굳힌 단타 종목 없음</div>'; return; }
  const cell = (x, k) => {
    const v = x.p[k];
    if (x.s.k >= 0 && k === x.s.k) return `<td class="dt-sold">${pct(v)}<em>${x.s.why}</em>${x.pyrTo ? `<small class="dt-pyr"> → ${esc(x.pyrTo.name || '—')} 불타기</small>` : ''}</td>`;
    { const ad = x.pnl && (x.pnl.adds || []).filter((o) => o.k === k); if (ad && ad.length) return `<td class="${k === L ? 'dt-last' : ''}">${pct(v)}<small class="dt-pyr"> ← ${ad.map((o) => esc(o.from || '—')).join(' · ')} 손절 돈 불타기</small></td>`; }
    if (x.s.k >= 0 && k > x.s.k) return `<td class="dt-after">${v == null ? '—' : sgn(v)}</td>`;
    return `<td class="${k === L ? 'dt-last' : ''}">${pct(v)}</td>`;
  };
  const plTd = (x, i) => `<td class="dt-pl">${i < topN && x.pnl ? (x.pnl.net == null ? '<span class="st-err">시장 모름</span>' : `<span class="${signClass(x.pnl.net, NUM) || ''}">${won(x.pnl.net)}</span><small>빼기 전 ${won(x.pnl.gross)}${x.pnl.adds && x.pnl.adds.length ? ` · 불타기 ${won(x.pnl.pyr)}` : ''}</small>`) : '<span class="st-err">—</span>'}</td>`;
  const resTd = (x) => `<td class="dt-res">${pct(x.res)}<small>${x.s.k >= 0 ? `${hmTxt(times[x.s.k])} ${x.s.why}` : x.now ? `지금 ${esc(String(d.nowAt || '').slice(0, 5))}` : '끝까지'}</small></td>`;
  const rk = (r, i) => `<td class="dt-rk">${i + 1}</td>`;
  // 매수가 (11-18 서버 바뀜) — 정규장 전에 든 종목은 buy null + buyWait → 「09:00 시가 기다림」 · 채워지면 buySrc(시가 · 지금 값) · 그 시각
  const NM0 = d.meta || {};
  const buyTd = (r) => (r.buy == null && r.buyWait ? `<td class="dt-buy"><span class="dt-nxm">${st.openAt ? hmTxt(String(st.openAt).replace(':', '')) : '정규장'} 시가 기다림</span></td>`
    : `<td class="dt-buy">${num(r.buy)}${r.buySrc ? `<small>${r.buyAt ? `${hmTxt(String(r.buyAt).replace(':', ''))} ` : ''}${esc(r.buySrc)}</small>` : ''}</td>`);
  // 09:01 값 (11-18 재권님 「9시 1분 등락도 넣어줘 이쯤 살거니깐」 → 「응 그렇게 해」) — 서버 rows[].px1(개발2 · 첫 1분봉 종가 「1m」 · 없으면 그때 현재가 「now」) · 시각은 meta.px1At
  //   화면은 매수가 대비 % 만 셈 · px1 칸이 없으면 「아직」(서버가 아직 안 줌 · 그날 09:02 전) · px 가 null 이면 「—」 못 잼(0 아님)
  const p1At = NM0.px1At ? hmTxt(String(NM0.px1At).replace(':', '')) : '09:01';
  const p1Ch = (r) => (r.px1 && r.px1.px != null && Number(r.buy) > 0 ? (Number(r.px1.px) / Number(r.buy) - 1) * 100 : null);
  const p1Td = (r) => { const o = r.px1;
    if (o === undefined) return '<td class="dt-nx"><span class="dt-nxm">아직</span></td>';
    if (!o || o.px == null) return '<td class="dt-nx">—<small>못 잼</small></td>';
    return `<td class="dt-nx">${pct(p1Ch(r))}<small>${num(o.px)}${o.src === 'now' ? ' · 그때 현재가' : ''}</small></td>`; };
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
  const gk = (x) => nLive(x.r);
  const grp = (i, span) => { if (st.order || (i > 0 && gk(R[i - 1]) === gk(R[i]))) return ''; const g = gk(R[i]), xs = R.filter((y) => gk(y) === g);
    const tp = xs.filter((y) => R.indexOf(y) < topN && y.pnl && y.pnl.net != null), net = tp.reduce((a, y) => a + y.pnl.net, 0);
    return `<tr class="dt-chiprow"><td colspan="${span}"><span class="st-cap"><b>칩 ${g}개</b> · ${xs.length}종목${tp.length ? ` · 세후 <span class="${signClass(net, NUM) || ''}">${won(net)}</span> · 이긴 것 ${tp.filter((y) => y.pnl.net > 0).length}/${tp.length}` : ' · 손익 셈 밖(상위 밖)'}</span></td></tr>`; };
  if (!WIDE.matches) {
    // 좁은 폭(모바일 퍼스트 · 재권님 「모바일 퍼스트 적용시킨 화면도」) — 종목 칸 안에 시가총액 · 섹터 · 이벤트를 접어 넣고, 결과 · 손익을 종목 바로 옆에 · 시각 칸은 그 뒤로 밀어 봄
    $('dt-box').innerHTML = `<table class="dt-tb dt-narrow">
    <tr><th class="dt-rk"></th><th class="st-name">종목</th><th class="dt-res">결과</th><th class="dt-pl">손익</th><th>매수가</th><th class="dt-nx">${p1At}</th>${times.map((t) => `<th>${hmTxt(t)}</th>`).join('')}<th class="dt-nx">다음 날 프리장 ${nxAt || ''}</th><th class="dt-tx">세금 %</th></tr>
    ${chipRow(times.length + 8)}
    <tr class="dt-avg"><td class="dt-rk"></td><td class="st-name">평균</td><td class="dt-res">${pct(resAvg)}</td><td class="dt-pl">${P ? won(P.net) : '—'}</td><td></td>${p1Avg}${avg.map((x) => `<td>${pct(x)}</td>`).join('')}${nxAvg}<td class="dt-tx"></td></tr>
    ${R.map((x, i) => { const r = x.r; return `${grp(i, times.length + 8)}<tr>${rk(r, i)}<td class="st-name" data-co="${esc(r.code || '')}"><b>${esc(r.name || '—')}</b><small class="dt-sub">${capTxt(r.cap)} · ${esc(r.sector || '섹터 —')}</small><span class="dt-evs">${evHtml(r.chips, r)}</span></td>${resTd(x)}${plTd(x, i)}${buyTd(r)}${p1Td(r)}${times.map((t, k) => cell(x, k)).join('')}${nxTd(r)}<td class="dt-tx">${taxTxt(x.r)}</td></tr>`; }).join('')}
  </table>`;
    return;
  }
  // 넓은 폭 — 칩마다 세로 칸(위 「칩 칸」) · 칩 줄 자리에는 어제 미국장만 남김
  const CS = colsOf(), nCol = CS.length;
  const chHead = (c) => { const on = !st.off.has(c), ms = st.miss.has(c), n = all.filter((r) => (r.chips || []).includes(c)).length;
    const subs = subOrder(c, [...new Set(all.flatMap((r) => subsOf(r, c)))]);
    const tip = ms ? ` data-tip="${esc(`그날 판에 ${c} 값을 ${missWord()} — 걸린 종목이 있어도 0 으로 셈됨`)}"` : tipAt(c);
    return `<th class="dt-chc${on ? '' : ' is-off'}"><span class="dt-cg${on ? '' : ' is-off'}${ms ? ' is-miss' : ''}" data-i="${colorOf(c)}"><button type="button" class="dt-mc${on ? ' is-on' : ''}" data-col="${esc(c)}"${tip} aria-haspopup="menu">${esc(c)}${ms ? '' : `<b>${n}</b>`}</button>${
      subs.length ? `<span class="dt-subs">${subs.map((x) => { const k = `${c}|${x}`, son = on && !st.subOff.has(k); return `<button type="button" class="dt-sub-chip${son ? ' is-on' : ''}" data-sub="${esc(k)}"${tipAt(k)} aria-pressed="${son}"${on ? '' : ' disabled'}>${esc(x)}<b>${all.filter((r) => subsOf(r, c).includes(x)).length}</b></button>`; }).join('')}</span>` : ''}</span><small>${on ? (ms ? missWord() : st.wait.has(c) ? `${st.openAt ? hmTxt(String(st.openAt).replace(':', '')) : '정규장'} 뒤` : '켜짐') : '꺼짐'}</small></th>`; };
  const chCell = (r, c) => { const on = !st.off.has(c), has = (r.chips || []).includes(c), sb = has ? subsOf(r, c) : [];
    const vt = has && c === 'VI·급등' ? viTxt(r) : '';
    const v = has ? `<span class="dt-cg" data-i="${colorOf(c)}">${sb.length ? `<i class="dt-chs">${esc(sb.join('·'))}</i>` : '<b class="dt-dot" aria-label="걸림"></b>'}${vt ? `<small>${esc(vt)}</small>` : ''}</span>`
      : st.miss.has(c) ? `<span class="dt-chq" data-tip="${esc(`그날 판에 ${c} 값을 ${missWord()} — 이 종목이 걸렸는지 모름`)}">—</span>`
      : st.wait.has(c) ? `<span class="dt-chq" data-tip="${esc(`아직 때가 아님 — ${c} 은 정규장${st.openAt ? `(${st.openAt})` : ''} 뒤에 셈`)}">·</span>` : '';
    return `<td class="dt-chc${on ? '' : ' is-off'}">${v}</td>`; };
  const chBlank = (th) => CS.map(() => `<${th} class="dt-chc"></${th}>`).join('') + `<${th} class="dt-ovn"></${th}><${th} class="dt-addc"></${th}>`;
  const usRow = `<tr class="dt-chiprow"><td colspan="${times.length + nCol + 12}"><div class="dt-chips" id="dt-chips"><span class="dt-us" id="dt-us" data-day="${esc(d.day || '')}">${usHtml(d.day)}</span></div></td></tr>`;
  $('dt-box').innerHTML = `<table class="dt-tb dt-cols">
    <tr><th class="dt-rk"></th><th class="st-name">종목</th><th>시가총액</th><th class="dt-sec">섹터</th>${CS.map(chHead).join('')}<th class="dt-ovn" data-tip="켜진 칩 중 몇 개에 걸렸나 — 순위가 이 수로 정해짐">겹침</th><th class="dt-addc"><button type="button" class="kh-chip" data-addcol aria-haspopup="menu">+ 칩</button></th><th>매수가 ${st.openAt ? `${hmTxt(String(st.openAt).replace(':', ''))} 시가` : hmTxt(d.buyAt)}</th><th class="dt-nx" data-tip="이쯤 산다면 — 09:01 값의 매수가 대비 %">${p1At}</th><th class="dt-gp" colspan="${times.length}"><span>매수가 대비</span></th><th class="dt-res">결과</th>${nxH1}<th class="dt-tx">세금 %</th><th class="dt-pl">손익 · 종목마다 ${manTxt(per)}</th></tr>
    <tr class="dt-t2"><th class="dt-rk"></th><th class="st-name"></th><th></th><th class="dt-sec"></th>${chBlank('th')}<th></th><th class="dt-nx">매수가 대비</th>${times.map((t) => `<th>${hmTxt(t)}</th>`).join('')}<th class="dt-res">판 값 · 시각</th>${nxH2}<th class="dt-tx">거래세 · 농특세</th><th class="dt-pl">세금 · 수수료 뺌 · 상위 ${topN}</th></tr>
    ${usRow}
    <tr class="dt-avg"><td class="dt-rk"></td><td class="st-name">평균 <small>판 종목은 판 값으로</small></td><td></td><td class="dt-sec"></td>${chBlank('td')}<td></td>${p1Avg}${avg.map((x, i) => `<td class="${i === L ? 'dt-last' : ''}">${pct(x)}</td>`).join('')}<td class="dt-res">${pct(resAvg)}</td>${nxAvg}<td class="dt-tx"></td><td class="dt-pl">${P ? won(P.net) : '—'}<small>${P ? `빼기 전 ${won(P.gross)}` : ''}</small></td></tr>
    ${R.map((x, i) => { const r = x.r; return `${grp(i, times.length + nCol + 12)}<tr>${rk(r, i)}<td class="st-name" data-co="${esc(r.code || '')}"><b>${esc(r.name || '—')}</b> <small>${esc(r.code || '')}</small></td><td>${capTxt(r.cap)}</td><td class="dt-sec">${esc(r.sector || '—')}</td>${CS.map((c) => chCell(r, c)).join('')}<td class="dt-ovn"><b>${nLive(r)}</b>${(() => { const k = CS.filter((c) => !st.off.has(c) && st.miss.has(c) && !(r.chips || []).includes(c)).length; return k ? `<small class="dt-ovm">못 받은 칩 ${k}</small>` : ''; })()}</td><td class="dt-addc"></td>${buyTd(r)}${p1Td(r)}${times.map((t, k) => cell(x, k)).join('')}${resTd(x)}${nxTd(r)}<td class="dt-tx">${taxTxt(x.r)}</td>${plTd(x, i)}</tr>`; }).join('')}
  </table>`;
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
  paint(d);
  chips();
  const ms = Number(m.refreshMs ?? (d.meta && d.meta.refreshMs)); st.ms = ms > 0 ? ms : 0;   // 서버는 판 안 meta(data.meta)에 둔다(개발2 2단계 · 11-12 09:07 잼) — 바깥 meta 도 읽음
  if (d.closed !== true && (d.rows || []).some((r) => r.now != null) && ms > 0 && d.day === st.days[0]) again = setTimeout(() => { if (st.day === d.day) load(d.day, true); }, ms);
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
BIND.push(() => $('dt-only').addEventListener('click', (e) => { const b = e.target.closest('[data-only]'); if (!b || b.dataset.only === st.only) return; st.only = b.dataset.only; if (st.data) { paint(st.data); chips(); } }));

async function loadFee() {
  try { const r = await fetch(DOC, { cache: 'no-store' }); const j = r.ok ? await r.json() : null; const R0 = j && j.data && j.data.rules && j.data.rules.dt30 ? j.data.rules.dt30 : {}; const v = R0.feePct; st.fee = v == null || v === '' ? null : Number(v);
    st.set = { ...DEF_SET, ...(R0.set && typeof R0.set === 'object' ? R0.set : {}), mode: 'day' };   // 돈은 늘 전체 금액 ÷ 종목 수
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
    const y = e.target.closest('[data-pyr]'); if (y) { e.preventDefault(); const on = y.dataset.pyr === '1'; if (on !== !!st.set.pyr) setChange({ ...st.set, pyr: on }); return; }
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
          <label class="dt-fee">증권수수료 <input id="dt-fee" class="rl-in rl-num" inputmode="decimal" aria-label="증권수수료(%) — 팔 때만" placeholder="( )">% <span class="rl-sug">팔 때만 · 넣으면 저장되고 바로 다시 셈</span> <span id="dt-fee-msg" class="rl-sug"></span></label>
          <div class="dt-set" id="dt-set" aria-label="셈 칸 — 넣으면 저장되고 바로 다시 셈" style="display:flex;flex-wrap:wrap;align-items:baseline;gap:0 18px">
            <label class="dt-fee">칩 <input data-set="minChip" class="rl-in rl-num" inputmode="numeric" aria-label="칩 몇 개 이상만">개 이상 <span class="rl-sug">빈칸 = 전체</span></label>
            <label class="dt-fee">손절 <input data-set="stop" class="rl-in rl-num" inputmode="decimal" aria-label="손절(매수가 대비 %)">% <span class="rl-sug">빈칸 = 안 함</span></label>
            <label class="dt-fee" data-tip="손절로 판 돈을 그 시각 가장 많이 오른 종목에 더 삽니다 · 더 산 몫은 그 종목을 팔 때 함께 팝니다">불타기 <span class="dt-seg"><button type="button" class="kh-chip" data-pyr="1">켬</button><button type="button" class="kh-chip" data-pyr="0">끔</button></span></label>
            <label class="dt-fee">꺾임 <span class="dt-seg"><button type="button" class="kh-chip" data-turn="1">켬</button><button type="button" class="kh-chip" data-turn="0">끔</button></span> 앞 시각보다 <input data-set="turnPct" class="rl-in rl-num" inputmode="decimal" aria-label="꺾임 — 앞 시각보다 몇 % 넘게 내리면 팜">% 넘게 내리면 <span class="rl-sug">그 이하는 무시 · 빈칸 = 0</span></label>
            <label class="dt-fee">고점 대비 − <input data-set="trail" class="rl-in rl-num" inputmode="decimal" aria-label="고점 대비 몇 % 내리면 팜">% 내리면 팜 <span class="rl-sug">빈칸 = 안 씀 · 꺾임을 켜 두면 꺾임이 먼저 걸려 이 칸은 거의 안 듦</span></label>
            <button type="button" class="kh-chip" data-reset>기본값으로</button> <span id="dt-set-msg" class="rl-sug"></span>
          </div>
          <div class="st-cap" id="dt-month">—</div>
          <details class="dt-win" id="dt-win"><summary>칩별 승률 — 지난 30거래일 · 세후 · 칩 묶음마다 승률 · 날마다 이익 큰 종목</summary><div class="dw-body"></div></details></div>
        <div class="dt-box st-scroll" id="dt-box"><div class="st-err">—</div></div>
        <div class="st-cap dt-foot">각 시각 = 그 시각에 끝난 5분봉 종가 · 평균 = 그 시각 값이 있는 종목만 · 단타 목록은 <span class="dt-at">—</span> 에 그날 판을 열고, 서버가 굳히기 전까지는 다시 세어 줄이 바뀜(늦게 든 칩 · 빠진 종목) · 굳힌 뒤에는 늦게 나온 칩만 채움</div>
      </div>
      <div class="st-card sf" id="dt-sf"><div class="sf-h"><b>섹터수급 — 같은 업종 · 테마에 돈이 들어오나 · 프리장 08:00 ~ 정규장 09:30</b> <span class="dt-seg sf-by" role="tablist" aria-label="업종 · 테마"></span></div><div class="sf-body"><div class="st-err">—</div></div></div>`;
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
