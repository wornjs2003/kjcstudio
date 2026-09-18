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

   ── 적어둔 값을 믿지 않는다 ──
   값마다 시각을 함께 넣고, 너무 묵으면 없는 셈 친다. 그리고 화면에는
   "묵은 값" 이라는 표시가 서야 한다 — 그건 부르는 쪽 몫이다.
   묵은 숫자를 실시간인 양 보여주면 데이터 규칙에 어긋난다.
   ========================================================================== */

import { marketPhase } from '../utils/format.js';

const PREFIX = 'kh:last:';

/* 얼마나 지나면 버릴 것인가 — **장이 도는지에 따라 다르다** (2026-09-18 지시).
 *
 *   장중 · 단일가   5분.  값이 계속 바뀌므로 오래된 것은 쓸모가 없다
 *   그 밖           12시간. 값이 멈춰 있어 어제 것이 오늘 아침까지 맞다
 *
 * 전에는 언제나 1분이었다. 그래서 장 마감 뒤에 화면을 열면 **맞는 값을
 * 버리고 빈 칸**을 보여줬다. 반대로 장중에 1분은 짧아, 잠깐 다른 탭에
 * 다녀오면 순위가 통째로 빈 칸이 됐다.
 *
 * **묵은 값을 쓸 때는 화면에 그렇다고 적어야 한다.** load 가 ageMs 를 함께
 * 돌려주는 것이 그 때문이다 (아래 주석 참고). 급상승·급하락은 몇 분 만에도
 * 뒤집히므로, 부르는 쪽이 그 나이를 보고 더 눈에 띄게 적는다.
 */
const MAX_AGE_LIVE_MS = 5 * 60_000;
const MAX_AGE_CLOSED_MS = 12 * 60 * 60 * 1000;

/* 값이 움직이는 시간인가. KRX 가 도는 동안만 참이다 */
function marketLive() {
  try {
    const id = marketPhase().id;
    return id === 'regular' || id === 'single';
  } catch { return true; }        // 못 읽으면 짧은 쪽으로 (안전한 쪽)
}

function maxAge(slow) {
  if (slow) return MAX_AGE_SLOW_MS;
  return marketLive() ? MAX_AGE_LIVE_MS : MAX_AGE_CLOSED_MS;
}

/* 목록은 하루에 한 번 바뀐다. 시세보다 훨씬 오래 들고 있어도 된다. */
const MAX_AGE_SLOW_MS = 6 * 60 * 60 * 1000;

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

/* 저장해 둔 것을 돌려준다. 없거나 너무 묵었으면 null.

   { value, ageMs } 로 돌려주는 이유 — 부르는 쪽이 "몇 초 전 값" 인지
   화면에 적을 수 있어야 한다. */
export function load(key) {
  try {
    const raw = sessionStorage.getItem(PREFIX + key);
    if (!raw) return null;
    const box = JSON.parse(raw);
    if (!box || typeof box.at !== 'number') return null;
    const ageMs = Date.now() - box.at;
    if (ageMs > maxAge(box.slow)) {
      sessionStorage.removeItem(PREFIX + key);
      return null;
    }
    return { value: box.v, ageMs };
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
