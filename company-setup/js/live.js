// 시황분석 탭 값 읽기 — 자동으로 받은 새 값(data/<이름>-live.json · .gitignore)을 먼저, 없으면 커밋된 씨앗(data/<이름>.json)
// (2026-10-12 재권님 (가) 「응 해줘」 · (ㄴ) 판 — 자동 받기가 안 도는 자리도 빈 화면이 아니라 마지막 커밋 값으로 뜬다). market.js · market-ext.js 가 함께 쓴다
export async function live(name) {
  try { const r = await fetch(`data/${name}-live.json`, { cache: 'no-store' }); if (r.ok) return await r.json(); } catch (e) { /* 없으면 씨앗으로 */ }
  return (await fetch(`data/${name}.json`, { cache: 'no-store' })).json();
}
