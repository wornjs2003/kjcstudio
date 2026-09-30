/* 주기·캐시 값을 **서버에서 받는다** (2026-09-23 룰 · 2026-09-30 구현).
 *
 * 「캐시·주기·한도 값을 화면에 박지 않는다 — 서버가 내주고 화면이 받는다」.
 * 화면에 박으면 **서버 캐시를 고쳐도 화면이 안 따라오고**, 고쳤는지 아닌지를
 * 눈으로는 못 찾는다.
 *
 * 내주는 쪽은 `kis_proxy.py` 의 `timing_values()` 다 — 서버 폴더의 모듈을
 * **이름 규칙**(`*_TTL` · `*_INTERVAL` · `*_SEC`)으로 훑어 `/api/kis/stats` 의
 * `timing` 에 담는다. **목록을 적지 않으므로 서버에 상수가 늘어도 따라온다.**
 *
 * ⚠️ **서버 TTL 은 「이만큼 자주 물어라」 가 아니다.**
 * 「이보다 자주 물어도 **같은 값이 온다**」 는 뜻이다 — **하한이지 목표가 아니다.**
 * 그래서 이 모듈은 값을 **그대로 돌려주고**, 얼마로 돌릴지는 부르는 쪽이 정한다.
 *
 * ⚠️ **같은 이름인데 포트마다 값이 다르다.** `apply_slow()` 가 모듈 전역을
 * 갈아끼우므로 `--slow` 서버에서는 `PRICE_CACHE_TTL` 이 25 가 아니라 300 이다.
 * **그래서 소스를 읽으면 안 되고 그 서버에 물어야 한다** — 이 모듈이 하는 일이다.
 *
 * **한 번만 받는다.** 받는 주기를 두면 그 주기가 또 하나의 박힌 값이 된다.
 * 서버 값이 바뀌면 새로고침하면 된다.
 */

/** 받아 둔 값. 아직 안 왔으면 `null` */
let _timing = null;
/** 받는 중인 약속. 여러 곳에서 불러도 한 번만 나간다 */
let _pending = null;

/** 서버에서 한 번 받아 둔다. 실패하면 조용히 넘어간다 — 부르는 쪽이 대체값을 쓴다 */
export function loadTiming() {
  if (_timing) return Promise.resolve(_timing);
  if (_pending) return _pending;
  _pending = fetch('/api/kis/stats', { cache: 'no-store' })
    .then((r) => (r.ok ? r.json() : null))
    .then((j) => {
      _timing = (j && j.data && j.data.timing) || {};
      return _timing;
    })
    .catch(() => {
      /* 서버가 없거나 옛 판이라 `timing` 이 없을 수 있다.
         **그때도 화면은 돌아야 하므로** 빈 것으로 두고 대체값을 쓴다 */
      _timing = {};
      return _timing;
    });
  return _pending;
}

/** 서버가 정한 **초**. 아직 안 왔거나 그 이름이 없으면 `null` */
export function serverSec(key) {
  if (!_timing) return null;
  const v = _timing[key];
  return typeof v === 'number' ? v : null;
}

/** 서버가 정한 값을 **밀리초**로. 아직 안 왔으면 `fallbackMs`.
 *
 * `fallbackMs` 는 **서버가 없을 때만 쓰는 값**이지 「화면이 정한 주기」 가
 * 아니다. 그 둘을 섞으면 이 모듈을 쓰는 뜻이 없어진다.
 */
export function serverMs(key, fallbackMs) {
  const s = serverSec(key);
  return s == null ? fallbackMs : Math.round(s * 1000);
}

/** `setInterval` 대신 쓴다 — **돌 때마다 주기를 다시 읽는다.**
 *
 * `setInterval` 은 주기가 처음 한 번만 정해져서, 서버 값이 **나중에 도착하면**
 * 반영할 길이 없다. 이 꼴이면 첫 바퀴는 대체값으로 돌고 **그 다음부터 서버 값**
 * 으로 돈다.
 *
 * **`document.hidden` 을 여기서 함께 본다.** 22곳이 각자 그 검사를 들고 있어서
 * 빠뜨리기 쉬웠다 — 안 보는 탭에서 도는 것은 **KIS 예산을 그냥 쓰는 것**이다.
 * 2026-09-30 실측: 홈 화면을 안 보면 60초에 0건, 띄운 직후 24건.
 *
 * @returns {Function} 멈추는 함수
 */
export function everyServerMs(key, fallbackMs, fn) {
  let timer = null;
  let dead = false;
  const tick = () => {
    if (dead) return;
    timer = setTimeout(() => {
      if (!dead && !document.hidden) fn();
      tick();
    }, serverMs(key, fallbackMs));
  };
  tick();
  return () => { dead = true; if (timer) clearTimeout(timer); };
}

/* 화면이 뜨면 바로 받아 둔다. 첫 바퀴가 돌기 전에 도착하면 그때부터 서버 값이다 */
loadTiming();
