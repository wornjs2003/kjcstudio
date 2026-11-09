// 틀 배율 셈 한 곳 — 홀딩스 첫 화면(holdings/js/home.js fitScale)과 Insight(company-setup/js/fit.js)가 함께 쓴다 (2026-11-09).
// 재권님 「홀딩스 기준으로 다 맞춰」 → (가) 의 짝. 두 화면이 같은 식을 따로 들고 「고치면 둘을 함께 고친다」 주석을 달았던 것을 합쳤다
// (CLAUDE.md 「같은 값은 한 곳에만 둔다」 — 「같아야 한다」 는 주석은 지켜지지 않는다 · 합칠 수 있으면 먼저 합친다).
//   · 순수 함수 — DOM · 색 · 저장을 안 든다. 재는 것(칸 높이 · 창 크기 · CSS 변수)은 부르는 쪽이 재서 넘긴다
//   · 식은 home.js fitScale 에 있던 그대로다 — 옮기면서 값이 바뀌면 안 된다
//
//   fixed  s=1 · z=1 일 때 안 커지는 높이(px)        grow  s 만큼 커지는 높이(px) — 없으면(0 · null) 창 폭으로만 푼다
//   rail   오른쪽 Claude 줄 폭(px)                    w · h 창 안쪽 폭 · 높이(px)
//   nav    상단 메뉴 높이(px)                          grid  틀 최대 폭(--grid-max px) · gap 창 가장자리 여백(--kh-fit-gap px)
//   → { s: 틀을 키우는 배율(글자 그대로 · 1 이상), z: 통째로 줄이는 배율(1 이하 · 0.1 아래로는 안 내려감) }
export function solveFit({ fixed = 0, grow = 0, rail = 0, w, h, nav = 0, grid, gap = 0 }) {
  const room = h - nav - gap, wide = (w - rail - 2 * gap) / grid;
  const byH = grow > 0;
  let s = byH ? Math.min(wide, (room - fixed) / grow) : wide, z = 1;
  if (s < 1) { s = 1; z = Math.max(0.1, byH ? Math.min(wide, room / (fixed + grow)) : wide); }   // 0.1 — 0 · 음수만 막는다
  return { s, z };
}
