/* ==========================================================================
   즐겨찾기 (2026-09-18 지시)

   재권님 말씀 — "실시간 순위에 나오는 종목에 즐겨찾기 (하트모양) 이 있고
   이걸 클릭하면 하트모양안에 색이 노란색으로 채워지고 즐겨찾기 목록에
   들어가게 해야할거같아."

   **한 곳에만 둔다.** 순위표의 하트와 관심 사이드바가 같은 목록을 본다.
   한쪽에서 누르면 다른 쪽이 바로 따라간다 (2026-09-18 지시 —
   "종목화면에 적용되거나 모델에 적용되는건 동기화가 되야해").

   처음 켜면 `WATCHLIST` 가 담겨 있다. 사이드바가 그동안 보여주던 것이라,
   빈 목록으로 시작하면 있던 것이 사라진 것처럼 보인다.

   ── 서버 관심목록이 이것이다 (2026-10-26) ──

   재권님 「관심종목 등록하면 서버에도 적용되게 해줘」 → 「하트 목록을 서버 관심목록으로
   합칠까요」 에 「응 우선 그렇게 해줘」. 그 전에는 하트가 이 브라우저에만 있고 텔레그램
   알림은 `server/dart.py` 의 목록을 따로 봤다. 이제 **하트를 끄면 공시 · 실적 · 신호 알림도 멈춘다.**

       원천    문서 저장 `/api/board/doc/watchlist` — `{items: [{code, name}]}`.
               세션 서버 · 서비스방은 그 주소를 8765 로 넘기므로(`KJC_BOARD_UPSTREAM`) 목록은 하나다
       서버    `dart.watchlist()` 가 그 문서를 읽는다 — 재시작 없이 따라간다
       여기    localStorage 는 **들고 있는 값**이다(그리기가 기다리지 않게 · 서버가 안 닿을 때).
               화면이 뜰 때와 탭을 다시 볼 때 서버 것을 받아 바꾼다 — 묻는 주기 숫자는 없다

   `items` 로 감싸는 까닭 — 문서 층은 빈 값(`[]`)을 안 쓴다. 하트를 다 끈 것이 저장 안 되면
   서버가 옛 목록으로 알림을 계속 보낸다.

   **이 브라우저에서 처음 서버와 맞출 때는 합친다** — 이 브라우저 하트를 서버 목록에 더한다.
   그 뒤로는 서버가 원천이다. 그래야 기기마다 따로 담아 둔 하트가 첫날 사라지지 않는다.
   서버에 문서가 아직 없으면 이 브라우저 목록으로 만든다.
   ========================================================================== */

import { WATCHLIST } from '../data/market.js';

const KEY = 'kh:favorites:v1';
const SYNCED = 'kh:favorites:synced';      // 이 브라우저 하트를 서버에 한 번 합쳤나
const DOC = '/api/board/doc/watchlist';

/* 바뀔 때마다 알려줄 곳 — 순위표 · 사이드바가 각각 건다 */
const listeners = [];

let serverAt = null;                        // 서버 문서를 마지막으로 읽은 때(updatedAt) — PUT 에 돌려보낸다
let queue = Promise.resolve();              // 서버 쓰기 차례

function clean(arr) {
  const out = [];
  for (const x of arr || []) {
    const v = typeof x === 'string' ? { code: x, name: x } : x;
    if (v && typeof v.code === 'string' && !out.some(o => o.code === v.code)) {
      out.push({ code: v.code, name: v.name || v.code });
    }
  }
  return out;
}

/* 담을 때 **이름도 같이 넣는다.** 관심 사이드바가 목록을 그릴 때 이름이
   필요한데, 코드만 있으면 `WATCHLIST` 밖 종목은 이름을 알 수 없다.
   순위표에서 담는 순간에는 화면이 이름을 갖고 있으므로 그때 함께 적는다. */
function read() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) return clean(arr);
    }
  } catch (_) { /* 저장을 못 읽어도 화면은 돌아야 한다 */ }
  return WATCHLIST.map(s => ({ code: s.code, name: s.name }));   // 처음 켠 사람
}

function store(arr) {
  try { localStorage.setItem(KEY, JSON.stringify(arr)); } catch (_) {}
  listeners.forEach(fn => { try { fn(arr); } catch (_) {} });
}

function flag(k, v) {
  try {
    if (v === undefined) return localStorage.getItem(k) === '1';
    localStorage.setItem(k, '1');
  } catch (_) {}
  return false;
}

/* ── 서버 ──────────────────────────────────────────────────────────── */

/** 서버 목록. 문서가 없으면 `null` · 못 닿으면 `undefined` */
async function fetchServer() {
  try {
    const r = await fetch(DOC, { cache: 'no-store' });
    if (!r.ok) return undefined;
    const j = await r.json();
    if (!j.ok) return undefined;
    serverAt = j.updatedAt || null;
    const items = j.data && Array.isArray(j.data.items) ? j.data.items : null;
    return items ? clean(items) : null;
  } catch (_) {
    return undefined;
  }
}

/** 통째로 쓴다. 그 사이 남이 썼으면(409) 다시 읽어 `redo` 를 얹고 한 번 더 쓴다 */
async function pushServer(arr, redo) {
  for (let i = 0; i < 2; i++) {
    try {
      const r = await fetch(DOC, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: { items: arr }, updatedAt: serverAt }),
      });
      const j = await r.json().catch(() => ({}));
      if (r.ok && j.ok) { serverAt = j.updatedAt || serverAt; return true; }
      if (r.status !== 409 || !redo) break;
      const fresh = await fetchServer();
      if (!Array.isArray(fresh)) break;
      arr = redo(fresh);
      store(arr);
    } catch (_) { break; }
  }
  console.warn('[관심종목] 서버에 못 썼습니다 — 이 브라우저에만 바뀌었습니다');
  return false;
}

function same(a, b) {
  return a.length === b.length && a.every((x, i) => x.code === b[i].code && x.name === b[i].name);
}

/** 서버 것을 받아 들고 있는 값을 바꾼다 */
async function pull() {
  const srv = await fetchServer();
  if (srv === undefined) return;                       // 못 닿음 — 들고 있는 값 그대로
  const local = read();
  if (srv === null) {                                  // 서버에 아직 없다 — 이 브라우저 목록으로 만든다
    if (await pushServer(local)) flag(SYNCED, true);
    return;
  }
  let arr = srv;
  if (!flag(SYNCED)) {                                 // 이 브라우저에서 처음 — 하트를 더한다
    const add = local.filter(x => !srv.some(s => s.code === x.code));
    if (add.length) {
      arr = srv.concat(add);
      if (!(await pushServer(arr, f => f.concat(add.filter(x => !f.some(s => s.code === x.code))))))
        return;
    }
    flag(SYNCED, true);
  }
  if (!same(arr, local)) store(arr);
}

/* ── 밖에 내는 것 ───────────────────────────────────────────────────── */

/** 담은 종목 목록 `[{code, name}]`. **담은 순서대로** 돌려준다 */
export function favList() { return read(); }

/** 이 종목이 담겨 있나 */
export function isFav(code) { return read().some(x => x.code === code); }

/** 담거나 뺀다. 담은 뒤 상태(true=담김)를 돌려준다. 서버에는 뒤에서 쓴다 */
export function toggleFav(code, name) {
  const apply = (arr, on) => {
    const out = arr.filter(x => x.code !== code);
    if (on) out.push({ code, name: name || code });
    return out;
  };
  const on = !isFav(code);
  store(apply(read(), on));
  /* 쓰기는 한 줄로 세운다 — 빨리 여러 번 누르면 PUT 이 같은 `updatedAt` 으로 겹쳐 서로 409 를 내고
     마지막 상태가 어긋났다(2026-10-26 헤드리스 시험). 차례가 오면 그때의 목록을 보낸다 */
  queue = queue.then(() => pushServer(read(), fresh => apply(fresh, on)));
  return on;
}

/** 목록이 바뀔 때마다 부른다 */
export function onFavChange(fn) { if (typeof fn === 'function') listeners.push(fn); }

/* 화면이 뜰 때 · 탭을 다시 볼 때 서버 것을 받는다 — 다른 기기에서 담은 것이 따라온다. 쓰기와 같은 줄에 선다 */
const pullQueued = () => { queue = queue.then(pull); };
pullQueued();
document.addEventListener('visibilitychange', () => { if (!document.hidden) pullQueued(); });
