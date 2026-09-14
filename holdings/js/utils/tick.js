/* ==========================================================================
   값이 새로 들어왔다는 것을 눈에 보이게 한다

   숫자가 소리 없이 바뀌면 갱신이 도는지 알 수가 없다. 그래서
     · 새로 받아올 때마다 숫자가 살짝 커졌다 돌아온다 (값이 그대로여도)
     · 값이 바뀌었으면 방향에 따라 배경이 한 번 물든다 (오르면 빨강 · 내리면 파랑)

   쓰는 법
     tickClass('price:005930', 262000)  → 'kh-tick kh-tick-up' 같은 클래스 문자열
     이 문자열을 새로 그리는 요소의 class 에 붙이면 애니메이션이 한 번 돈다.
     (화면을 innerHTML 로 다시 그리므로 클래스를 붙이는 것만으로 매번 재생된다)
   ========================================================================== */

/* 직전 값 기억. 키는 부르는 쪽이 정한다 (예: 'row:005930') */
const previous = new Map();

export function tickClass(key, value) {
  if (value == null) return '';
  const before = previous.get(key);
  previous.set(key, value);

  // 처음 그리는 것이면 조용히 — 페이지를 열자마자 전부 깜빡이면 정신없다
  if (before === undefined) return '';

  if (value === before) return 'kh-tick';                    // 갱신만 알림
  return value > before ? 'kh-tick kh-tick-up' : 'kh-tick kh-tick-down';
}

/* 종목이 바뀌는 등 비교가 의미 없어질 때 기억을 지운다 */
export function forgetTicks(prefix) {
  if (!prefix) { previous.clear(); return; }
  for (const key of previous.keys()) {
    if (key.startsWith(prefix)) previous.delete(key);
  }
}
