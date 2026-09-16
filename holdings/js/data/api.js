/* 서버(/api/*)를 부르는 한 곳.
 *
 * ── 왜 따로 두나 ──
 *
 * 배포본은 Cloudflare Access 뒤에 있다. 화면을 켜 둔 채로 **로그인이
 * 만료되면** 서버가 아니라 로그인 화면으로 넘기라는 302 가 돌아온다.
 * 그런데 그 로그인 화면은 다른 도메인이라, `fetch` 가 따라가면 브라우저가
 * CORS 로 막는다. 2026-09-16 에 실제로 이렇게 나왔다.
 *
 *     from origin 'https://thekjcstudio.com' has been blocked by CORS policy
 *
 * 그때까지 화면은 **아무 말도 하지 않았다.** 부르는 쪽이 전부
 * `catch { return null }` 이라 「서버가 죽은 것」과 「로그인이 풀린 것」이
 * 똑같이 null 로 왔다. 그래서 옛 숫자를 든 채 30초마다 영원히 다시 불렀고
 * 162건 · 265kB 가 쌓였다.
 *
 * ── 어떻게 가려내나 ──
 *
 *     fetch(url, { redirect: 'manual' })
 *       → 302 면 브라우저가 따라가지 않고 type 이 'opaqueredirect' 가 된다
 *       → CORS 도 안 걸리고 콘솔에 빨간 줄도 안 남는다
 *
 * 한 번 만료되면 **그 뒤로는 아예 부르지 않는다.** setInterval 을 하나하나
 * 찾아 끄는 것보다 확실하다 — home.js 에만 일곱 개가 있다.
 *
 * ── 왜 여기서 띠까지 그리나 ──
 *
 * 데이터 쪽이 화면을 만지는 것이 깔끔하진 않다. 그런데 네 화면(첫 화면 ·
 * 종목 · 뉴스 · 데일리)이 모두 이 파일을 거치므로, 여기 한 번 두면 갈라질
 * 일이 없다. 화면마다 붙이면 한쪽만 고쳐지는 일이 또 난다.
 *
 * ── 왜 자동으로 로그인 화면에 못 보내나 ──
 *
 *     주소창이 302 를 받으면   브라우저가 따라간다 → 로그인 화면
 *     fetch 가 302 를 받으면   화면 코드가 받는다  → 보던 화면이 유지된다
 *
 * 브라우저는 배경 요청 때문에 사용자를 끌고 가지 않는다. 그래서 띠를 띄우고
 * 누르게 한다. 새로고침은 주소창 요청이라 로그인 화면으로 제대로 간다.
 */

const BANNER_ID = 'kh-auth-expired';

let expired = false;

/** 로그인이 풀린 상태인가. 부르는 쪽이 「서버가 죽었나」와 가릴 때 쓴다. */
export function isAuthExpired() {
  return expired;
}

/**
 * `/api/*` 를 부른다.
 *
 * @returns {Promise<Response|null>} 로그인이 풀렸으면 null.
 *   그 밖의 실패는 지금까지처럼 예외를 던지거나 실패한 Response 를 준다 —
 *   부르는 쪽의 `catch { return null }` 이 그대로 받는다.
 */
export async function apiFetch(url, opts = {}) {
  if (expired) return null;                 // 이미 풀렸다. 내보내지 않는다

  const res = await fetch(url, { ...opts, redirect: 'manual' });

  /* 302 를 따라가지 않고 받은 모양. 상태 코드도 본문도 못 읽는다 */
  if (res.type === 'opaqueredirect' || (res.type === 'opaque' && res.status === 0)) {
    markExpired();
    return null;
  }
  return res;
}

function markExpired() {
  if (expired) return;
  expired = true;
  console.info('[KJC] 로그인이 만료되었습니다 — 값 받아오기를 멈춥니다');
  showBanner();
}

function showBanner() {
  if (!document.body || document.getElementById(BANNER_ID)) return;

  const el = document.createElement('div');
  el.id = BANNER_ID;
  el.className = 'kh-authbar';
  el.setAttribute('role', 'status');
  el.innerHTML = `
    <i></i>
    <span>로그인이 만료되었습니다. 지금 보이는 값은 멈춰 있습니다.</span>
    <button type="button">다시 로그인</button>`;

  /* 새로고침은 주소창 요청이라 브라우저가 302 를 따라가 로그인 화면을 띄운다 */
  el.querySelector('button').addEventListener('click', () => location.reload());
  document.body.appendChild(el);
}
