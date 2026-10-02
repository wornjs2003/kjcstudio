/* ==========================================================================
   마지막으로 본 값을 남겨 둔다

   화면을 오갈 때마다 빈 칸부터 시작했다. 값이 서버에서 올 때까지
   "불러오는 중" 이 몇 초씩 떠 있었다. 파일은 캐시로 해결했지만(sw-boot.js·
   no-cache) 값은 매번 새로 받는다 (2026-09-15 지적).

   그래서 마지막으로 받은 것을 여기 남긴다. 다시 들어오면 그것부터 그리고,
   새 값이 오면 덮는다. 처음 0.5초가 빈 화면이 아니라 조금 묵은 화면이 된다.

   ── sessionStorage 인 이유 ──
   탭을 닫으면 지워진다. 시세는 하루만 지나도 쓸모가 없는데 localStorage 에
   두면 내일 아침에 어제 값이 먼저 뜬다. 탭 안에서 오가는 동안만 살면 된다.

   ── 버리지 않고, 몇 분 전 값인지 적는다 (2026-10-02 지시) ──
   값마다 시각을 함께 넣는다. **얼마나 묵었든 버리지 않는다** — 재권님 말씀
   「직전에 받은값 이여 할거같은데」. 화면에는 "○분 전 값" 이라는 표시가
   서야 한다 — 그건 부르는 쪽 몫이다(`frame.js` 의 `markStale`).
   묵은 숫자를 실시간인 양 보여주면 데이터 규칙에 어긋난다.
   ========================================================================== */

const PREFIX = 'kh:last:';

/* **묵었다고 버리지 않는다** (2026-10-02 지시 — 「직전에 받은값 이여 할거같은데」).
 *
 * 전에는 장중 5분 · 장 밖 12시간 · 목록 6시간이 지나면 버렸다(2026-09-18 지시).
 * 그래서 새로고침하면 **맞을 수도 있는 값을 버리고 빈 칸**부터 보였다. 버려도
 * 서버를 더 묻지 않으므로 룰 위반은 아니었고, **보여 주는 방식**을 정한 것이다.
 *
 * 대신 **몇 분 전 값인지 화면에 적는다** — `load` 가 `ageMs` 를 함께 돌려주는
 * 것이 그 때문이다. 서버 값이 오면 덮고 표시도 사라진다.
 *
 * **며칠 뒤 지우는 장치를 두지 않는다.** `sessionStorage` 라 탭을 닫으면
 * 사라진다. 탭을 밤새 열어 두었다 새로고침하면 어제 값이 뜨는데, 그때도
 * 「○시간 전 값」 이 함께 서므로 실시간인 양 보이지 않는다.
 *
 * `slow` 는 그대로 받아 적어 둔다. 지금은 버리는 기준에 안 쓰지만, 부르는
 * 쪽(`home.js` 의 목록)이 넘기고 있어 뜻을 남긴다 — 「하루에 한 번 바뀌는 값」.
 */

/* 한 항목이 너무 크면 sessionStorage 가 통째로 막힌다 (보통 5MB).
   200종목 시세가 대략 40KB 라 넉넉하지만, 위쪽은 막아 둔다. */
const MAX_BYTES = 512 * 1024;

export function save(key, value, { slow = false } = {}) {
  try {
    const body = JSON.stringify({ at: Date.now(), slow, v: value });
    if (body.length > MAX_BYTES) return false;
    sessionStorage.setItem(PREFIX + key, body);
    return true;
  } catch {
    /* 저장 공간이 꽉 찼거나 브라우저가 막아 둔 경우.
       화면은 값 없이도 돌아야 하므로 조용히 넘어간다. */
    return false;
  }
}

/* 저장해 둔 것을 돌려준다. 없으면 null — **묵었다고 null 이 되지 않는다.**

   { value, ageMs } 로 돌려주는 이유 — 부르는 쪽이 "몇 초 전 값" 인지
   화면에 적을 수 있어야 한다. */
export function load(key) {
  try {
    const raw = sessionStorage.getItem(PREFIX + key);
    if (!raw) return null;
    const box = JSON.parse(raw);
    if (!box || typeof box.at !== 'number') return null;
    return { value: box.v, ageMs: Math.max(0, Date.now() - box.at) };
  } catch {
    return null;
  }
}

/* 저장해 둔 것을 전부 지운다. 값이 이상할 때 손으로 부를 수 있게 둔다.
   콘솔에서 쓰라고 남겨 두는 것이라 화면 코드에서는 부르지 않는다. */
export function clearAll() {
  try {
    const keys = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i);
      if (k && k.startsWith(PREFIX)) keys.push(k);
    }
    keys.forEach((k) => sessionStorage.removeItem(k));
    return keys.length;
  } catch {
    return 0;
  }
}
