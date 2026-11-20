// 단타 칩 설명 한 곳 — 「종목 고르는 룰」 칸(strategy-chips.js)과 단타 판 칩 풍선(strategy-dt30.js)이 같은 글을 가져다 쓴다
//   (11-20 재권님 「응」 — 「칩 설명(무엇 · 조건 · 언제)을 공용 파일 하나에 모아 두 자리가 가져다 쓰게」 · 작업우선순위 카드 「단타 칩 설명이 두 자리에 박힘 — 한 곳으로 합치기」)
//   · 고르는 조건(COND) — 두 자리에 다 있던 칩(프리장 · 초반상승 · 장외)은 룰 칸 글 하나로. 값 칸을 그리는 꼴(val)만 부르는 쪽이 준다(룰 칸은 진한 칸 · 풍선은 맨 글)
//   · 언제(WHEN) · 풍선 머리(TIP · WHAT) — 풍선만 쓰던 글을 그대로 옮김
//   · 숫자는 서버 값 그대로 — 룰 칸은 칩마다 받은 meta · 풍선은 이 파일이 한 번 받아 둔 meta(pre-flow · open-rise) · 못 받으면 「서버 값 못 받음」(「설명 글에는 정해진 값을 적는다」)
import { loadTiming, serverData } from '/holdings/js/store/timing.js';   // 서버 시각 값(장외 비우는 시각 · 11-19)

const plain = (x) => (x == null || x === '' ? '(서버 값 못 받음)' : String(x));

// 풍선이 쓰는 칩 meta — 룰 칸과 같은 주소를 한 번 받아 둠(풍선은 마우스를 올릴 때 읽으므로 그때는 와 있음)
const metaCache = {};
const META_URL = { 프리장: '/api/kis/pre-flow', 초반상승: '/api/kis/open-rise' };
Object.entries(META_URL).forEach(([k, u]) => { (async () => { try { const r = await fetch(u, { cache: 'no-store' }); const j = r.ok ? await r.json() : null; metaCache[k] = (j && j.meta) || null; } catch (e) { metaCache[k] = null; } })(); });
loadTiming();

// 고르는 조건 — 두 자리 공용(m = 그 칩 서버 meta · val = 값 칸 꼴)
export const COND = {
  프리장: (m, val) => `넥스트레이드 프리마켓 거래대금 상위 ${val(m.topN)}위 안 · 프로그램 순매수인 종목`,
  초반상승: (m, val) => `장 시작 ${val(m.barMin)}분 뒤 — ${val(m.barFrom)} ~ ${val(m.barTo)} 첫 ${val(m.barMin)}분봉이 시가 대비 ${val(m.risePct)}% 이상 오름 · ETF 뺌 · 늦게 여는 날은 여는 시각부터`,   // 「장 시작 몇 분 뒤」 — 11-20 재권님 「단타에 초반상승이 장시작 몇분후인지 설명에 넣어줘」 · 값은 서버 meta.barMin 그대로
  장외: () => '정규장 종가 뒤(넥스트레이드 애프터 · 다음 날 프리마켓)에 종가보다 오른 종목 · 문턱 없음',
};

// 칩 풍선 — 쉬운 말로(11-18 재권님 「설명들 직관적이고 이해하기 쉽게 개선해줘」) · 뜻은 서버 holdings/server/intraday_alerts.py 머리 글 그대로 · 급등 기준 % 는 서버 상수(SURGE_PCT) 한 곳
const TIP = {
  'VI·급등': '오르는 쪽 VI 가 걸렸거나, 하루 사이 크게 뛴(급등) 종목 — 오른쪽 작은 칩 둘(VI 급상승 · VI 급등)로 따로 켜고 끔 · 둘을 더하면 이 숫자',
  'VI·급등|VI 급상승': 'VI 만 걸리고 급등 기준까지는 안 오른 종목\nVI — 값이 짧은 사이 크게 움직이면 거래소가 2분 동안 거래를 멈추고 한꺼번에 값을 정하는 것(여기서는 오르는 쪽만)',
  'VI·급등|VI 급등': '전날 종가보다 급등 기준 넘게 오른 종목(VI 가 함께 걸린 것도 여기)\n급등 기준은 서버가 정한 값 · 그날 처음 넘을 때 한 번 셈',
  '매수|①': '① 외국인 · 기관 · 연기금 · 프로그램 넷 다 산 종목',
  '매수|②': '② 외국인 · 기관 · 프로그램이 함께 산 종목',
  '매수|③': '③ 기관 · 연기금이 함께 산 종목',
  '매수|④': '④ 외국인만 산 종목',
  '매수|어림': '어림 — 외국인 · 기관 집계가 나오기 전에 먼저 보는 값\n외국계 증권사 창구와 프로그램이 둘 다 산 종목(장 열기 전에는 프로그램만) · 집계가 나오면 ①~④ 로 바뀜',
};
// 언제 받나 · 얼마마다(11-18 재권님 「칩에 마우스 올리면 칩설명과 시간 주기 등등 정보도 넣어줘」) — 서버가 data.meta.chipInfo{칩: 글} 을 주면 그것만 쓴다(그때 지운다) · 시각은 11-18 서버 코드에서 읽은 그대로
const WHEN = {
  관심: '언제 — 전날 장 마감 뒤 정해지고, 장중에는 5분마다 그때 값으로 다시 거름',
  프리장: '언제 — 장 열기 전 08:00~08:50 몇 분마다 셈 · 08:50~09:00 에 그날 것으로 정함',
  'VI·급등': '언제 — 08:00 부터 10초마다(장 열기 전은 넥스트레이드 값) · 단타 판에는 판을 굳히기 전까지 걸린 것만',
  get 장외() { const c = serverData('afterClear') || serverData('chipReset'); return `언제 — 장 끝난 15:40 뒤부터 다음 날 ${c && c.from ? c.from : '아침(비우는 시각 — 서버 값 못 받음)'} 까지 · 아침 단타 판에는 거의 안 듦`; },   // 비우는 시각은 서버 /api/kis/stats afterClear(= market_hours.CHIP_RESET 한 곳)
  매수: '언제 — 외국인 첫 집계 09:30 · 기관 첫 집계 10:00 · 그 전에는 「어림」 으로 먼저 봄',
  get 초반상승() { const m = metaCache.초반상승; return m && m.barMin != null ? `언제 — 장 시작 ${m.barMin}분 뒤(${m.barFrom || '—'} ~ ${m.barTo || '—'} 첫 ${m.barMin}분봉이 끝난 뒤) · 늦게 여는 날은 여는 시각부터` : '언제 — 장 시작 첫 봉이 끝난 뒤부터(몇 분 뒤인지 — 서버 값 못 받음)'; },
  자동: '언제 — 전날 장 마감 뒤 정해지고, 장중에는 5분마다 그때 값으로 다시 거름',
};
const autoTxt = (R) => (R ? `전날 거래량이 크게 늘며 오른 종목을 서버가 자동으로 담음 — 전날 +${R.prevPct}% 이상 올랐고${R.sectorPct != null ? ` · 그 업종이 +${R.sectorPct}% 이상` : ''}${R.nearHighPct != null ? ` · 1년 최고가에서 ${R.nearHighPct}% 안` : ''}${R.maDays ? ` · ${R.maDays}일 평균값 위${R.maUpCandle ? '에서 오른 날' : ''}` : ''}${R.scoreW ? ` · 순서는 오른 폭 ${R.scoreW.pct}% · 거래량 ${R.scoreW.vol}% 로 셈` : ''}` : '전날 거래량이 크게 늘며 오른 종목을 서버가 자동으로 담음 — 조건 값은 서버 값 못 받음');
const WHAT = {
  관심: (R) => `관심 목록에 하트로 담은 종목 · 시가총액 ${R && R.capMinEok != null ? `${R.capMinEok.toLocaleString()}억 이상` : '문턱 — 서버 값 못 받음'}`,
  프리장: () => COND.프리장(metaCache.프리장 || {}, plain),
  장외: () => COND.장외(),
  매수: () => '외국인 · 기관이 많이 산 종목(증권사 집계) · ①~④ 는 누가 함께 샀는지',
  초반상승: () => { const m = metaCache.초반상승 || {}; return `${COND.초반상승(m, plain)} · 시가총액 ${m.minCapEok != null ? `${Number(m.minCapEok).toLocaleString()}억 이상` : '(서버 값 못 받음)'}`; },
  자동: autoTxt,
};
// 풍선 글 — ctx: rules(서버 data.meta.rules) · chipInfo(서버 칩 글 · 있으면 그것만) · watchAuto(관심이 서버 자동 목록인 판)
export function chipTip(k, ctx = {}) {
  if (k.includes('|')) return TIP[k] || '';
  const ci = ctx.chipInfo && ctx.chipInfo[k];
  if (typeof ci === 'string' && ci) return ci;
  const R = ctx.rules || {};
  if (k === '관심' && ctx.watchAuto) return [`관심 — 하트 대신 서버가 자동으로 담은 종목\n${autoTxt(R.관심).replace(/^전날 거래량이 크게 늘며 오른 종목을 서버가 자동으로 담음 — /, '조건 — ')}`, WHEN.자동].filter(Boolean).join('\n');
  const head = TIP[k] || (WHAT[k] ? WHAT[k](R[k]) : '');
  return [head, WHEN[k]].filter(Boolean).join('\n');
}
