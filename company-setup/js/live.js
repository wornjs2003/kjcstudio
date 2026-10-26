// 시황분석 탭 값 읽기 — 자동으로 받은 새 값(data/<이름>-live.json · .gitignore)을 먼저, 없으면 커밋된 씨앗(data/<이름>.json)
// (2026-10-12 재권님 (가) 「응 해줘」 · (ㄴ) 판 — 자동 받기가 안 도는 자리도 빈 화면이 아니라 마지막 커밋 값으로 뜬다). market.js · market-ext.js 가 함께 쓴다
export async function live(name) {
  try { const r = await fetch(`data/${name}-live.json`, { cache: 'no-store' }); if (r.ok) return await r.json(); } catch (e) { /* 없으면 씨앗으로 */ }
  return (await fetch(`data/${name}.json`, { cache: 'no-store' })).json();
}

// 시황 글 — 세션이 쓴 글(data/market-note.json)과 자동 글(data/market-note-live.json · tools/write-market-note.py)을 둘 다 읽어 쓴 시각이 새 것을 고른다
// (2026-10-26 재권님 (가) 「응」 — 손 글이 더 새로우면 손 글). 쓴 시각 「2026-10-13 09:5x」 꼴은 x 를 0 으로 읽는다. 둘 다 없으면 null
export async function latestNote() {
  const get = n => fetch(`data/${n}.json`, { cache: 'no-store' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  const [S, A] = await Promise.all([get('market-note'), get('market-note-live')]);
  const t = N => (N && N.writtenAt ? String(N.writtenAt).slice(0, 16).replace(/x/g, '0') : '');
  return !A ? S : !S ? A : t(A) > t(S) ? A : S;
}
