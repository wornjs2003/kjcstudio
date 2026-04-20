/* ==========================================================================
   KJC Holdings — 개발용 서비스 워커
   모든 동일 출처 자원을 캐시 우회(no-store)로 받아와서
   JS/CSS 수정 사항이 새로고침 한 번으로 즉시 반영되도록 한다.
   ========================================================================== */

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (e) => {
  try {
    const url = new URL(e.request.url);
    // 동일 출처만 처리 (구글 폰트 등 외부 자원은 기본 캐시 유지)
    if (url.origin !== self.location.origin) return;
    // 네트워크 강제 — 디스크/메모리 캐시 우회
    e.respondWith(fetch(e.request, { cache: 'no-store' }));
  } catch (_) {
    // URL 파싱 실패 시 통과
  }
});
