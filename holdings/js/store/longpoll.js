/* ==========================================================================
   값이 바뀌면 서버가 알려 준다 — 롱폴링 묶음 (2026-10-02)

   재권님 말씀 — 「주어진 서버 리소스 안에서 쏴 주면 그 값을 **주는 대로
   받아야** 할 것 같다」. 그래서 화면은 **주기를 갖지 않는다.** 바뀌면 서버가
   바로 내려주고, 화면은 그때 그린다.

       GET /api/kis/poll?u=<주소1>&h=<해시1>&u=<주소2>&h=<해시2>…
       → { items: [{ u, hash, changed, status, body? }, …] }

   서버(`kis_proxy.py` · 서버리소스 2단계 ⓓ)는 안쪽 주소를 **자기 캐시로**
   다시 불러 해시를 견준다 — KIS 를 더 부르지 않는다. 얼마나 쥐고 있을지
   (`hold`)도 서버 기본값을 쓴다. 화면이 숫자를 들고 있지 않는다.

   ── 한 화면 = 연결 하나 ──

   **브라우저는 한 주소에 동시 연결을 6개까지만 연다**(HTTP/1.1 · 개발2 지적).
   자리마다 롱폴을 따로 쥐면 그것만으로 꽉 차서 차트·그림·다른 API 가 줄을
   선다. 그래서 이 모듈이 **한 탭의 구독을 전부 모아 한 연결로** 묻는다.

   ── 서버가 롱폴을 모를 때 (폴백) ──

   스위치(`KJC_LONGPOLL`)가 꺼진 서버는 `404`, 묶음을 모르는 옛 서버는
   `items` 없이 답한다. 그때는 자리마다 **서버가 정한 캐시 값 주기**로 묻는다
   (`timing.js` 의 `everyServerMs` — 그 값도 서버가 준다). 화면은 두 길을
   몰라도 된다 — 어느 길이든 `onChange` 가 불린다.
   ========================================================================== */

import { everyServerMs, serverMs, serverFlag, loadTiming } from './timing.js';

const subs = new Set();
let mode = 'long';          // 'long' | 'fallback'
let running = false;

/**
 * 구독한다.
 * @param {object}   opt
 * @param {Function} opt.url        → 지금 볼 `/api/kis/…` 주소. 없으면 `null`(쉰다)
 * @param {Function} opt.onChange   값이 바뀌었을 때. **스스로 다시 받아 그린다** —
 *                                   서버 캐시에 걸리므로 KIS 는 안 는다
 * @param {string}   opt.key        폴백 때 따를 서버 값 이름 (예: `kis_proxy.INDEX_TTL`)
 * @param {number}   opt.fallbackMs 그 값마저 못 받았을 때
 * @returns {{ stop: Function, refresh: Function }}
 *          `refresh()` — 주소가 바뀌었다(종목을 골랐다). **쥔 연결은 끊지 않는다** —
 *          다음 바퀴에 새 주소로 묻는다. 새 값은 부르는 쪽이 바로 받아 그리므로
 *          화면은 기다리지 않는다
 */
export function watch({ url, onChange, key, fallbackMs }) {
  const s = { url, onChange, key, fallbackMs, hash: '', lastUrl: null, stopFb: null };
  subs.add(s);
  if (mode === 'fallback') startFallback(s);
  restart();
  return {
    stop() {
      subs.delete(s);
      if (s.stopFb) s.stopFb();
      restart();
    },
    refresh: restart,
  };
}

/** 지금 어느 길로 받고 있나 — 실측·화면 안내용 */
export function pollMode() { return mode; }

/* **쥔 연결을 끊지 않는다** (2026-10-02 실측). 브라우저는 끊어도 서버 쪽 스레드는
   쥐는 시간이 끝날 때까지 남는다 — 첫 화면에서 종목 줄에 마우스를 올릴 때마다
   끊었더니 한 탭이 서버 스레드를 **넷** 쥐었다. 한 탭 = 한 연결을 지키려면
   다음 바퀴를 기다린다. */
function restart() {
  if (!running && mode === 'long') loop();
}

function startFallback(s) {
  if (s.stopFb) return;
  s.stopFb = everyServerMs(s.key, s.fallbackMs, () => {
    if (s.url()) return s.onChange();
  });
}

function goFallback() {
  mode = 'fallback';
  subs.forEach(startFallback);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const visible = () => new Promise((r) => {
  const on = () => { if (!document.hidden) { document.removeEventListener('visibilitychange', on); r(); } };
  document.addEventListener('visibilitychange', on);
});

async function loop() {
  running = true;
  try {
    /* **켜져 있는지 먼저 본다.** 꺼진 서버에 물으면 `404` 가 나고 브라우저가 그것을
       콘솔 오류로 찍는다 — 차트 연기 검사가 그것을 「걸림」 으로 센다 (2026-10-02 실측) */
    await loadTiming();
    if (!serverFlag('longpoll')) { goFallback(); return; }
    while (subs.size && mode === 'long') {
      /* 안 보는 탭은 쥐지 않는다 — 서버 스레드를 그냥 쥐는 것이다 */
      if (document.hidden) { await visible(); continue; }

      const list = [];
      subs.forEach((s) => {
        const u = s.url();
        if (!u) return;
        if (u !== s.lastUrl) { s.lastUrl = u; s.hash = ''; }   // 주소가 바뀌면 처음부터
        list.push({ s, u });
      });
      if (!list.length) return;            // 볼 것이 없다 — 다음 watch/refresh 가 깨운다

      const qs = list.map(({ s, u }) => `u=${encodeURIComponent(u)}&h=${s.hash}`).join('&');
      const askedAt = Date.now();
      let j;
      try {
        const r = await fetch('/api/kis/poll?' + qs, { cache: 'no-store' });
        if (r.status === 404 || r.status === 400) { goFallback(); return; }
        j = await r.json();
      } catch (e) {
        /* 서버가 잠깐 없다 — 서버 값 주기만큼 쉬고 다시 묻는다 */
        await sleep(serverMs(list[0].s.key, list[0].s.fallbackMs));
        continue;
      }

      /* 묶음을 모르는 옛 서버는 `items` 가 없다. 주소가 하나면 맨 위 키가 곧 그것이다 */
      const items = Array.isArray(j && j.items) ? j.items
        : (list.length === 1 && j && 'hash' in j) ? [j] : null;
      if (!items || items.length !== list.length) { goFallback(); return; }

      items.forEach((it, i) => {
        const { s, u } = list[i];
        if (s.lastUrl !== u || !subs.has(s)) return;          // 그 사이 바뀌었다
        s.hash = it.hash || '';
        if (it.changed && it.status === 200) {
          try { s.onChange(); } catch (e) { console.error(e); }
        }
      });
      /* 서버가 붐벼(`busy`) 쥐지 못하고 바로 냈다 — 그대로 다시 물으면 맴돈다 */
      if (j.busy) { await sleep(serverMs(list[0].s.key, list[0].s.fallbackMs)); continue; }
      /* **바닥 쉼** (2026-10-02 · 창구 검수). 서버는 첫 비교를 곧바로 하므로, 응답에
         받은 시각처럼 매번 달라지는 값이 섞인 주소를 구독하면 쉼 없이 되돌아온다.
         서버가 다시 보는 간격(`LONGPOLL_STEP_SEC`)보다 자주 묻지 않는다 — 그 값도
         서버가 준다. 대체값 1초는 서버가 그 값을 안 줄 때만 쓴다 */
      const gap = serverMs('kis_proxy.LONGPOLL_STEP_SEC', 1000) - (Date.now() - askedAt);
      if (gap > 0) await sleep(gap);
    }
  } finally {
    running = false;
  }
}
