/* 코드로 종목 이름을 찾는 한 곳 (2026-10-12 · 재권님 「응 가로 해줘」).

   종목 화면(stock.js)과 첫 화면의 주소 진입(home.js · ?code=)이 함께 쓴다.
   전에는 종목 화면에만 있어서, 첫 화면은 관심종목 밖 종목을 주소로 받으면
   이름을 못 찾아 모달을 아예 안 열었다(첫 로드 때 순위 목록이 아직 없다 · 8765 실측).

   순위표(/api/dart/universe · 네이버 시총 순위 저장본) → 상장사 대응표(/api/dart/search)
   순서로 찾는다. 둘 다 증권사(KIS) 호출이 아니다. 못 찾으면 null — 코드 이름으로 열지는
   부르는 쪽이 정한다. */

import { apiFetch } from './api.js';

export async function lookupStock(code) {
  if (!/^\d{6}$/.test(code || '')) return null;
  try {
    const r = await apiFetch('/api/dart/universe', { cache: 'no-store' });
    const j = r && await r.json();
    const hit = j && j.ok && Array.isArray(j.data) && j.data.find(x => x.code === code);
    if (hit) return { code, name: hit.name };
    /* 순위 목록 밖이면 상장사 대응표에서 이름을 찾는다(갈래 줄 검색칸과 같은 /api/dart/search · 2026-10-06) */
    const r2 = await apiFetch(`/api/dart/search?q=${code}&limit=1`, { cache: 'no-store' });
    const j2 = r2 && await r2.json();
    const hit2 = j2 && j2.ok && Array.isArray(j2.data) && j2.data.find(x => x.code === code);
    if (hit2) return { code, name: hit2.name };
  } catch { /* 못 찾았다 */ }
  return null;
}
