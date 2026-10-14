// 서버 시장지표 한 계열 — 이 서버 /api/market/indicator?key=<지표>(네이버 증권 시장지표 · 홀딩스 「시장지표」 칩 · 차트와 같은 주소)를
// [[날, 종가], …] 로 받는다 (2026-10-14 재권님 「이건 그대로 두고 이값을 가져와서 읽도록 구조를 짜는게 어때?」 → 「응 해」).
// 시황분석 탭 그래프 · 달러인덱스(dxy.js) · 홈 매크로 줄이 함께 쓴다. 지표 목록 · 봉/선은 서버가 정한다(holdings/server/market_index.py).
// 못 받으면 null — 부르는 쪽이 06:30 파일 값으로 남기거나 「—」 로 낸다
export async function indicatorSeries(key) {
  const j = await (await fetch(`/api/market/indicator?key=${encodeURIComponent(key)}`)).json();
  const s = (j.bars || []).filter(b => b.c != null).map(b => [b.d, b.c]);
  if (!j.ok || s.length < 2) return null;
  return { s, fetchedAt: j.fetchedAt || null, name: j.item && j.item.name };
}
