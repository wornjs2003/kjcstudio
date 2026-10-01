/* 지수 띠 — 홀딩스 첫 화면 맨 위의 띠와 데일리분석 「주요 지수」 가 같이 쓴다.
 *
 * 2026-10-01 에 js/home.js 에서 빼냈다 — 재권님 「주요지수는 … 홀딩스화면에서 나오는거랑 똑같이
 * 보여달라」. 데일리 쪽에 같은 모양을 한 벌 더 만들면 두 곳이 되므로(「같은 값은 한 곳에만 둔다」)
 * 칸 목록(INDEX_CELLS) · 앞 표시(cellIcon) · 상태 배지(badgeFor) · 칸 그리기(stripHtml) 를 여기 모았다.
 * **동작은 옮기기 전과 같다** — 첫 화면은 tools/check-layout.py 로 0 차이를 확인한다.
 *
 * 국기는 holdings/img/flags.svg 의 <symbol> 을 <use href="./img/flags.svg#kh-flag-kr"> 로 꺼낸다 —
 * 상대 경로라 holdings/ 바로 아래 화면(index · daily)에서만 맞다. 다른 깊이에서 쓰면 경로를 넘겨받게 고친다.
 */
import { fmtNum, fmtDelta, dirClass, marketPhase } from '../utils/format.js';

/* 지수 띠에 놓을 칸.
 *
 * **다우존스는 뺐다** (2026-09-17 지시 — "받을 수 없는 지수는 메인 UI 상에서도
 * 없애고 만들지 않는다"). 증권사 두 곳 어디에도 없어서 자리만 차지하고
 * 있었다. 「아직 안 붙인 것」이 아니라 「받을 수 없는 것」이다.
 *
 *     KIS    DJI · .DJI · DJIA · INDU · DJX · US30 · DJ30 · DWJ · DIA
 *            13개 후보를 네 시장구분으로 훑었는데 전부 0
 *            (DOW 는 다우社 주식이라 30달러가 나온다)
 *     토스증권 Open API   개별 주식만 준다. 지수가 없다
 *
 * **WTI·금은 남긴다.** 받을 곳은 찾았고 거래소 신청만 하면 된다 —
 * 못 찾은 것이 아니라 아직 안 붙인 것이다. wait 에 무엇을 하면 채워지는지
 * 적어 둔다 (holdings/CLAUDE.md 데이터 규칙).
 */
export const INDEX_CELLS = [
  { code: 'KOSPI',    name: '코스피',     icon: 'kr' },
  { code: 'KOSDAQ',   name: '코스닥',     icon: 'kr' },
  { code: 'KOSPI200', name: '코스피200',  icon: 'kr' },
  { code: 'KRX100',   name: 'KRX100',   icon: 'kr' },
  { code: 'USDKRW', name: '미국 USD',  icon: 'us' },
  { code: 'SPX',    name: 'S&P 500',  icon: 'us' },
  { code: 'NASDAQ', name: '나스닥 종합', icon: 'us' },
  { code: 'NDX',    name: '나스닥100',  icon: 'us' },
  { code: 'SOX',    name: '필라델피아 반도체', icon: 'us' },
  { code: 'SX5E',   name: '유로STOXX50', icon: 'eu' },
  { code: 'HSCE',   name: '홍콩H',      icon: 'hk' },
  { code: 'VIX',    name: 'VIX',      icon: 'vix' },
  /* NYMEX · COMEX 거래소를 신청하면 채워진다 (EGW00551, 2026-09-17 실측) */
  { name: 'WTI 원유',  wait: '거래소 신청 필요', icon: 'oil' },
  { name: '금',       wait: '거래소 신청 필요', icon: 'au' },
];

/* 칸 앞에 붙는 표시.
   국기는 <use> 로 꺼내 쓰고(index.html 맨 위에 정의), 나머지는 글자 배지로 만든다.
   이모지를 쓰면 윈도우에서 "KR" 같은 지역코드 글자로 나와서 직접 그렸다. */
export function cellIcon(kind) {
  if (kind === 'kr' || kind === 'us') {
    return `<svg class="kh-ix-flag" viewBox="0 0 24 24" aria-hidden="true"
      ><use href="./img/flags.svg#kh-flag-${kind}"/></svg>`;
  }
  const badge = { vix: 'V', oil: '油', au: 'Au', eu: 'EU', hk: 'HK' }[kind];
  return badge ? `<span class="kh-ix-badge ${kind}" aria-hidden="true">${badge}</span>` : '';
}

/* 카드에 붙일 표시. 무엇을 보고 있는지가 한눈에 들어와야 한다. */
export function badgeFor(i) {
  if (i.market === 'overseas') {
    const d = i.asOf || '';
    /* 20260914 → "09.14 종가" */
    const label = d.length === 8 ? `${d.slice(4, 6)}.${d.slice(6, 8)} 종가` : '해외장';
    return { live: false, text: label };
  }
  /* 국내는 셋으로만 나눈다 (2026-09-15 지시).

       실시간   09:00~15:30  KRX 정규장. 값이 계속 움직인다
       넥장     08:00~08:50 · 15:30~20:00  넥스트레이드에서만 거래된다
       장마감   그 밖. 값이 멈춰 있다

     08:50~09:00 은 프리마켓이 끝나고 정규장 전이라 거래가 없다. 장마감으로 묶는다.
     이 구분은 시세를 어느 시장 기준으로 받는지와 짝이 맞는다
     (정규장은 KRX, 그 밖은 통합 — CLAUDE.md 의 시세 표기 규칙). */
  const phase = marketPhase();
  /* 단일가(15:20~15:30)도 KRX 가 도는 시간이라 값이 움직인다.
     애프터 준비(15:30~15:40)는 주문만 받고 체결이 없어 값이 멈춰 있다. */
  if (phase.id === 'regular' || phase.id === 'single') return { live: true, text: '실시간' };
  if (phase.id === 'pre' || phase.id === 'after') return { live: false, text: '넥장' };
  return { live: false, text: '장마감' };
}

/** 띠 칸들을 그린다. indices 는 /api/kis/indices 의 data 배열 */
export function stripHtml(indices, cells = INDEX_CELLS) {
  const byCode = Object.fromEntries((indices || []).map(i => [i.code, i]));
  return cells.map(cell => {
    const i = cell.code ? byCode[cell.code] : null;
    if (!i) {
      /* 둘을 구분해 적는다.
         받아올 곳이 아직 없는 칸  → "연결 예정" · 값은 "—"
         연결은 됐는데 안 온 칸    → "불러오는 중"
         섞어 쓰면 연결이 안 된 건지 아직 안 온 건지 알 수 없다. */
      const soon = !cell.code;
      return `<div class="kh-ix">
        <div class="kh-ix-h">${cellIcon(cell.icon)}<span class="kh-ix-n">${cell.name}</span>
          ${soon ? '<span class="kh-bd kh-bd-soon">연결 예정</span>' : ''}</div>
        <div class="kh-ix-v kh-num kh-mut"
          style="${soon ? '' : 'font-size:.9rem;font-weight:500'}"
          >${soon ? '—' : '불러오는 중'}</div>
        <div class="kh-ix-c kh-mut">${cell.wait || ''}</div>
      </div>`;
    }
    const cls = dirClass(i.changePct);
    /* 언제 기준 값인지 적는다.
       국내는 지금 장이 열려 있으면 실시간, 아니면 장 상태 그대로.
       해외는 국내 낮 시간에 닫혀 있으므로 받은 값의 날짜를 적는다.
       전에는 값만 있으면 무조건 "실시간" 이라 어제 종가도 실시간으로 보였다
       (2026-09-15 지적). */
    const badge = badgeFor(i);
    return `<div class="kh-ix">
      <div class="kh-ix-h">${cellIcon(cell.icon)}<span class="kh-ix-n">${cell.name}</span>
        <span class="kh-bd ${badge.live ? 'kh-bd-on' : (badge.text === '넥장' ? 'kh-bd-nx' : '')}"
          >${badge.text}</span></div>
      <div class="kh-ix-b">
        <div>
          <div class="kh-ix-v kh-num ${cls}"
            >${fmtNum(i.value, 2)}</div>
          <div class="kh-ix-c kh-num ${cls}">${fmtDelta(i.change, i.changePct, '', 2)}</div>
        </div>
      </div>
    </div>`;
  }).join('');
}
