/* ==========================================================================
   서비스 워커 켜고 끄기

   세 화면(index · stock · news)이 같은 12줄을 각자 들고 있었다.
   한 곳으로 모은다 (CLAUDE.md 「같은 값은 한 곳에만 둔다」, 2026-09-15).

   ── 개발 중에는 등록한다 ──
   sw.js 가 같은 출처 요청을 no-store 로 받아온다. JS·CSS 를 고치면
   새로고침 한 번에 반영된다. 이게 이 워커를 만든 이유다.

   ── 배포본에서는 등록하지 않는다. 있으면 지운다 ──
   조건 없이 등록되고 있어서 사이트에서도 돌았다. HTML·CSS·JS·폰트가
   매번 새로 내려와 캐시가 0 이었고, 다른 화면에 갔다 오면 처음부터
   다시 받았다.

   **등록을 멈추는 것만으로는 부족하다.** 이미 방문한 브라우저에는 워커가
   남아 계속 가로챈다. 그래서 배포본에서는 이 폴더의 워커를 찾아 지운다.
   지우고 나면 다음 방문부터 브라우저 캐시가 정상으로 돈다.

   전에도 폴더 밖('/' 스코프) 워커를 지우는 코드는 있었다. 주소가
   /holdings/ 로 바뀌면서 옛 워커가 새 요청까지 가로챘기 때문이다
   (2026-09-14). 그건 그대로 두고, 안쪽 워커까지 다루도록 넓혔다.
   ========================================================================== */

const SCOPE = location.origin + '/holdings/';

/* 손으로 띄워 보는 자리인가. 파일로 직접 열었을 때(file://)는 호스트가
   비어 있는데, 그때는 워커가 어차피 등록되지 않는다. */
const isLocal = location.hostname === 'localhost'
             || location.hostname === '127.0.0.1'
             || location.hostname === '[::1]';

export function bootServiceWorker() {
  if (!('serviceWorker' in navigator)) return;

  navigator.serviceWorker.getRegistrations().then((regs) => {
    for (const r of regs) {
      /* 이 폴더 밖에 등록된 것은 어느 환경이든 지운다.
         배포본에서는 안쪽 것까지 지운다. */
      const outside = r.scope.indexOf(SCOPE) !== 0;
      if (outside || !isLocal) r.unregister();
    }
    if (isLocal) return navigator.serviceWorker.register('./sw.js');
  }).catch(() => { /* 워커가 없어도 화면은 돈다 */ });
}
