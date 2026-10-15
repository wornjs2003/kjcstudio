// 오르내림 숫자의 방향과 글씨 색 — 모든 화면이 함께 쓴다 (2026-10-15 재권님 「+/− 숫자 오르내림 색은 전부 같은 룰이야」 ·
// 「룰 어긋난 것들 체크해서 수정하라고 해줘」 · 문안에 「응 해줘」). 룰은 CLAUDE.md 「오르내림 숫자의 글씨 색은 한 셈이다」.
//   import { side, signClass, signColor, KH, NUM } from '/assets/js/sign.js';
//   side(1.2)  → 'up'   side(-3) → 'down'   side(0) → 'flat'   side(null) → null(값 없음 — 0 이 아니다)
//   signClass(-0.4)        → 'kh-down'      홀딩스 이름(KH) — 기본
//   signClass(0.4, NUM)    → 'num-up'       Insight 이름(NUM)
//   signColor('… +2.8% …') → '… <span class="num-up">+2.8%</span> …'   글 속 부호 붙은 숫자만(이미 만든 HTML 을 받는다)
// · 색 값은 들고 있지 않는다 — 클래스만 낸다. 색은 그 클래스가 theme.css 의 --kh-up · --kh-down 으로 칠한다
// · 0(보합)은 색 없음 · 값 없음(null · 숫자 아님)은 흐림 — 「못 쟀으면 0 이 아니라 「못 쟀다」 고 낸다」
// · 기준이 있는 수치의 짙기(tone.js)도 방향은 여기 `side` 를 부른다 — 셈이 둘이 되지 않게
// · 클래스 이름이 구역마다 둘(KH · NUM)인 것은 그대로 두었다 — 셈만 한 곳이다. 까닭과 합칠 때는 그 룰 절에 있다

export const KH = { up: 'kh-up', down: 'kh-down', flat: 'kh-flat', none: 'kh-mut' };
export const NUM = { up: 'num-up', down: 'num-dn', flat: '', none: '' };

/** 방향 — 'up' · 'down' · 'flat'(0) · null(값 없음). 숫자 글자('1.5')도 받는다 */
export function side(n) {
  if (n == null || n === '' || !Number.isFinite(+n)) return null;
  return +n > 0 ? 'up' : +n < 0 ? 'down' : 'flat';
}

/** 방향에 맞는 클래스 이름 — 이름 묶음은 KH(홀딩스) · NUM(Insight) */
export function signClass(n, names = KH) {
  return names[side(n) || 'none'] || '';
}

// 부호가 숫자에 바로 붙은 것만 — 「+2.8%」 · 「-14bp」 · 「−2조 103억원」. 띄운 빼기(「10년 − 2년」) · 날짜(2026-10-13) · 부호 없는 수는 안 칠한다
// (2026-10-14 시황분석1 company-setup/js/sign-color.js 에서 옮김)
const NUMRE = /(^|[\s(·,:→/~])([+\-−])(\d[\d,]*(?:\.\d+)?(?:%p|%|bp|조(?:\s\d[\d,]*억원?)?|억원|억|원|배|p)?)/g;

/** 글 속 부호 붙은 숫자에 오르내림 클래스를 씌운다. 태그 안 글자는 건드리지 않는다. 0 은 부호가 붙어도 칠하지 않는다 */
export function signColor(html, names = NUM) {
  return String(html).split(/(<[^>]+>)/).map((part) => part.startsWith('<') ? part
    : part.replace(NUMRE, (m, pre, sg, n) => {
      const v = parseFloat(n.replace(/,/g, ''));
      const cls = v === 0 ? '' : names[sg === '+' ? 'up' : 'down'];
      return cls ? `${pre}<span class="${cls}">${sg}${n}</span>` : m;
    })).join('');
}
