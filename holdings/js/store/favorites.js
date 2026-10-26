/* ==========================================================================
   즐겨찾기 (2026-09-18 지시)

   재권님 말씀 — "실시간 순위에 나오는 종목에 즐겨찾기 (하트모양) 이 있고
   이걸 클릭하면 하트모양안에 색이 노란색으로 채워지고 즐겨찾기 목록에
   들어가게 해야할거같아."

   **한 곳에만 둔다.** 순위표의 하트와 관심 사이드바가 같은 목록을 본다.
   한쪽에서 누르면 다른 쪽이 바로 따라간다 (2026-09-18 지시 —
   "종목화면에 적용되거나 모델에 적용되는건 동기화가 되야해").

   처음 켜면 `WATCHLIST` 여덟이 담겨 있다. 사이드바가 그동안 보여주던 것이라,
   빈 목록으로 시작하면 있던 것이 사라진 것처럼 보인다.

   ⚠️ **텔레그램 공시 알림 대상은 여기가 아니다.** 그쪽은 `server/dart.py` 의
   `WATCH_CODES` 이고 `market.js` 의 `WATCHLIST` 와 대조된다
   (`holdings/tools/check-watchlist-sync.py`). 하트를 꺼도 알림은 계속 온다 —
   알림은 서버가 보내는 것이라 이 브라우저 저장을 볼 수 없다.
   ========================================================================== */

import { WATCHLIST } from '../data/market.js';

const KEY = 'kh:favorites:v1';

/* 바뀔 때마다 알려줄 곳 — 순위표 · 사이드바가 각각 건다 */
const listeners = [];

/* 담을 때 **이름도 같이 넣는다.** 관심 사이드바가 목록을 그릴 때 이름이
   필요한데, 코드만 있으면 `WATCHLIST` 밖 종목은 이름을 알 수 없다.
   순위표에서 담는 순간에는 화면이 이름을 갖고 있으므로 그때 함께 적는다. */
function read() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) {
        return arr
          .map(x => (typeof x === 'string' ? { code: x, name: x } : x))
          .filter(x => x && typeof x.code === 'string');
      }
    }
  } catch (_) { /* 저장을 못 읽어도 화면은 돌아야 한다 */ }
  return WATCHLIST.map(s => ({ code: s.code, name: s.name }));   // 처음 켠 사람
}

function write(arr) {
  try { localStorage.setItem(KEY, JSON.stringify(arr)); } catch (_) {}
  listeners.forEach(fn => { try { fn(arr); } catch (_) {} });
}

/** 담은 종목 목록 `[{code, name}]`. **담은 순서대로** 돌려준다 */
export function favList() { return read(); }

/** 이 종목이 담겨 있나 */
export function isFav(code) { return read().some(x => x.code === code); }

/** 담거나 뺀다. 담은 뒤 상태(true=담김)를 돌려준다 */
export function toggleFav(code, name) {
  const arr = read();
  const at = arr.findIndex(x => x.code === code);
  if (at >= 0) arr.splice(at, 1);
  else arr.push({ code, name: name || code });
  write(arr);
  return at < 0;
}

/** 목록이 바뀔 때마다 부른다 */
export function onFavChange(fn) { if (typeof fn === 'function') listeners.push(fn); }
