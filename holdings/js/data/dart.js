/* ==========================================================================
   공시 (OpenDART)

   서버(server/dart.py)가 5분마다 받아 저장해 둔 것을 읽기만 한다.
   브라우저에서 OpenDART 를 직접 부를 수는 없다 — CORS 를 열어 주지 않는다.

   중계 서버가 없으면(배포본 등) null 을 돌려준다. 화면은 비워 둔다.
   ========================================================================== */

import { apiFetch } from './api.js';

let _ready = null;
let _saidMissing = false;      // 「서버 없음」 을 콘솔에 한 번만 적는다

/* 같은 바퀴에서 여러 칸이 한꺼번에 부르면 **한 번만** 묻는다. 서버가 꺼진 동안
   칸마다 따로 물으면 10초에 45번이 나갔다(2026-10-02 실측 · 8770). */
let _asking = null;

/* **됐을 때만 기억한다 (2026-10-02 지시).** `live.js` 의 `kisReady` 와 같다 —
   실패를 기억하면 서버가 재시작 중일 때 연 화면이 새로고침 전까지 「공시 서버
   없음」 으로 남는다. 실패면 비워 두고 다음 부름에서 다시 본다. */
function dartReady() {
  if (_ready) return Promise.resolve(true);
  if (!_asking) _asking = ask().finally(() => { _asking = null; });
  return _asking;
}

async function ask() {
  let ok = false;
  try {
    const r = await apiFetch('/api/dart/status', { cache: 'no-store' });
    if (!r) return null;   // 로그인이 풀렸다
    const j = await r.json();
    ok = !!(j && j.ok && j.data && j.data.configured);
    if (ok) {
      console.info('[KJC] 공시 연결됨 — 감시 ' + j.data.universe + '종목');
    }
  } catch { /* 아래에서 비워 둔다 */ }
  if (ok) { _ready = true; _saidMissing = false; return true; }
  if (!_saidMissing) {
    console.info('[KJC] 공시 서버 없음 — 공시 칸은 비워 둡니다 (살아나면 다음 바퀴에 받습니다)');
    _saidMissing = true;
  }
  return false;
}

/* **같은 주소를 받는 중이면 그 받기를 같이 쓴다** (2026-10-03 재권님 「맞다」).
   뉴스 모달 하나를 열면 공시 목록 · 일정의 실적 발표(`schedule.js`) · 모달 머리 숫자
   (`news-modal.js`) · 그 숫자가 다시 부르는 일정이 `?limit=200` 을 **거의 동시에 네 번**
   불렀다(2026-10-01 실측). 서버 캐시가 받아 줘 느리지는 않았고 낭비였다.

   **시간으로 묵히지 않는다** — 받는 동안만 같이 쓰고, 다 받으면 잊는다. 그래서 박는 값이
   없고, 다음에 부르면 새로 받는다(롱폴 알림 뒤의 다시 받기도 그대로 새 값이다).
   돌려주는 것은 **응답 본문(JSON)** — 못 받았으면 `null`. 본문은 여럿이 같이 읽으므로
   **고치지 말고 읽기만** 한다. */
const _inflight = new Map();
export function getDisclosuresBody(limit, code = null) {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (code) qs.set('code', code);
  const url = '/api/dart/disclosures?' + qs;
  if (_inflight.has(url)) return _inflight.get(url);
  const p = (async () => {
    try {
      const r = await apiFetch(url, { cache: 'no-store' });
      if (!r || !r.ok) return null;          // 로그인이 풀렸거나 서버가 실패
      return await r.json();
    } catch {
      return null;
    }
  })().finally(() => { _inflight.delete(url); });
  _inflight.set(url, p);
  return p;
}

/* 최근 공시. code 를 주면 그 종목만, 안 주면 감시 대상 전체.
   실패하면 null — 빈 배열([])과 구분해야 한다.
   null 은 '못 받았다', 빈 배열은 '받았는데 없다' 이다. */
export async function fetchDisclosures(code = null, limit = 20) {
  if (!(await dartReady())) return null;
  const j = await getDisclosuresBody(limit, code);
  if (!j || !j.ok || !Array.isArray(j.data)) return null;
  return j.data;
}

export async function fetchDartStatus() {
  try {
    const r = await apiFetch('/api/dart/status', { cache: 'no-store' });
    if (!r) return null;   // 로그인이 풀렸다
    const j = await r.json();
    return j && j.ok ? j.data : null;
  } catch {
    return null;
  }
}
