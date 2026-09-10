/* ==========================================================================
   시세 갱신 표시

   숫자가 갱신될 때 잠깐 확대해서 "방금 새로 불러왔다"를 눈으로 알린다.

   깜빡이는 조건은 두 가지다.
     1) 값이 실제로 바뀐 경우            → 언제나
     2) 실시간 항목을 새로 불러온 경우    → 값이 같아도 (markRefresh 구간)
   목업 항목은 2)에서 제외한다. 갱신되지도 않았는데 깜빡이면
   실제로 새로 받아온 것처럼 오해되기 때문이다.

   컴포넌트가 innerHTML 로 통째로 다시 그려도 동작하도록,
   이전 값은 DOM 이 아니라 이 모듈의 Map 에 보관한다.

   사용법:
     1) 숫자 요소에 data-tick-key(고유 식별자)와 data-tick-value(값)를 붙인다.
        실시간 항목이면 data-tick-live="1" 도 함께 붙인다.
     2) 다시 그린 뒤 applyTicks(hostEl) 를 호출한다.
     3) API 로 새로 불러온 직후라면 markRefresh() ... endRefresh() 로 감싼다.
   ========================================================================== */

const _prevValues = new Map();
let _refreshing = false;

/* 이 구간에서 그려지는 실시간 항목은 값이 같아도 깜빡인다 */
export function markRefresh() { _refreshing = true; }
export function endRefresh() { _refreshing = false; }

function flash(el) {
  el.classList.remove('kh-tick');
  void el.offsetWidth;          // 리플로우를 강제해 애니메이션을 다시 시작시킨다
  el.classList.add('kh-tick');
}

export function applyTicks(root) {
  const scope = root || document;
  scope.querySelectorAll('[data-tick-key]').forEach(el => {
    const key = el.dataset.tickKey;
    const val = el.dataset.tickValue != null ? el.dataset.tickValue : el.textContent;
    const prev = _prevValues.get(key);
    const isLive = el.dataset.tickLive === '1';

    const valueChanged = prev !== undefined && prev !== val;
    const refreshed = _refreshing && isLive;

    if (valueChanged || refreshed) flash(el);

    _prevValues.set(key, val);
  });
}
