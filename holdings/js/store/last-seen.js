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

const PREFIX = 'kh:last:';

/* 얼마나 지나면 버릴 것인가. 장중 시세는 금방 낡는다.
   1분이면 "조금 전 값" 이고, 그보다 오래된 것은 차라리 빈 칸이 낫다. */
const MAX_AGE_MS = 60_000;

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
    if (ageMs > (box.slow ? MAX_AGE_SLOW_MS : MAX_AGE_MS)) {
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
