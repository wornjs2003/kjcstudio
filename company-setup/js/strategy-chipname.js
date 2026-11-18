// 단타 칩 이름을 홀딩스 실시간 순위와 같게 (2026-11-18 · 시황분석)
//   · 재권님 「실시간 순위랑 단타랑 내용은 같은데 제목이 다른건 실시간 순위를 기반으로 해서 단타에 있는 목록들 바꿔줘」 → 「응 바꿔」
//     다른 것은 「수급」 하나 — 실시간 순위에서는 「관심」 안 「자동」 묶음(전일 거래량 급등 룰)이다. 실시간 순위의 「수급」 은 테마 쪽(넥스트 거래량 2배)이라 뜻이 다르다
//   · 서버(dt30 · dt30-win · 주식 레인)가 아직 「수급」 으로 보낸다 — 받는 자리에서 이 표로 바꿔 그린다. 서버가 「자동」 으로 바꾸면 이 표는 할 일이 없다(그때 지운다)
//   · 바꾸는 것은 칩 이름 글자 그대로인 값 · 열쇠와 「A + B」 로 이은 묶음 이름뿐 — 설명 글 안의 낱말은 건드리지 않는다
const RENAME = { 수급: '자동' };

const one = (s) => RENAME[s] || s;
const str = (s) => (RENAME[s] ? RENAME[s] : s.includes(' + ') ? s.split(' + ').map(one).join(' + ') : s);

export const chipName = (s) => (typeof s === 'string' ? str(s) : s);

export function renameChips(o) {
  if (typeof o === 'string') return str(o);
  if (Array.isArray(o)) return o.map(renameChips);
  if (o && typeof o === 'object') { const r = {}; for (const [k, v] of Object.entries(o)) r[one(k)] = renameChips(v); return r; }
  return o;
}
