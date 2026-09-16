/* ==========================================================================
   공시 (OpenDART)

   서버(server/dart.py)가 5분마다 받아 저장해 둔 것을 읽기만 한다.
   브라우저에서 OpenDART 를 직접 부를 수는 없다 — CORS 를 열어 주지 않는다.

   중계 서버가 없으면(배포본 등) null 을 돌려준다. 화면은 비워 둔다.
   ========================================================================== */

import { apiFetch } from './api.js';

let _ready = null;

async function dartReady() {
  if (_ready !== null) return _ready;
  try {
    const r = await apiFetch('/api/dart/status', { cache: 'no-store' });
    if (!r) return null;   // 로그인이 풀렸다
    const j = await r.json();
    _ready = !!(j && j.ok && j.data && j.data.configured);
    if (_ready) {
      console.info('[KJC] 공시 연결됨 — 감시 ' + j.data.universe + '종목');
    }
  } catch {
    _ready = false;
  }
  if (!_ready) console.info('[KJC] 공시 서버 없음 — 공시 칸은 비워 둡니다');
  return _ready;
}

/* 최근 공시. code 를 주면 그 종목만, 안 주면 감시 대상 전체.
   실패하면 null — 빈 배열([])과 구분해야 한다.
   null 은 '못 받았다', 빈 배열은 '받았는데 없다' 이다. */
export async function fetchDisclosures(code = null, limit = 20) {
  if (!(await dartReady())) return null;
  const qs = new URLSearchParams({ limit: String(limit) });
  if (code) qs.set('code', code);
  try {
    const r = await apiFetch('/api/dart/disclosures?' + qs, { cache: 'no-store' });
    if (!r || !r.ok) return null;
    const j = await r.json();
    if (!j || !j.ok || !Array.isArray(j.data)) return null;
    return j.data;
  } catch {
    return null;
  }
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
