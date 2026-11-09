/* Insight 틀을 홀딩스 첫 화면과 같은 넓이 · 자리로 (2026-11-07 재권님 「홀딩스 기준으로 다 맞춰」 → (가) 「홀딩스가 정한 넓이를 그대로 받아 씀」)

   홀딩스 첫 화면은 창에 맞춰 틀을 키우거나(--kh-s · 글자 그대로) 통째로 줄인다(--kh-z) — holdings/js/home.js fitScale.
   그 배율은 홀딩스 칸 높이(큰 차트 · 아래 줄)로 푼다. Insight 에는 그 칸이 없어서, 홀딩스가 이 브라우저에 남긴 바탕값
   (localStorage 'kh-fit-base' = {fixed, grow, rail} · s=1 · z=1 로 되돌린 px)을 받아 **같은 식을 이 창 크기로 다시 푼다** —
   창 크기를 바꿔도 두 화면 틀이 같다. 바탕값이 없으면(홀딩스를 이 브라우저에서 아직 안 열었다) 창 폭으로만 푼다.
   틀에 배율을 거는 CSS 는 holdings/css/home.css 「칸을 창에 맞춰 키운다」 한 곳이다(Insight 선택자도 거기).
   1281px 아래는 홀딩스처럼 아무것도 안 준다 — 그 폭은 frame.css 1280px 규칙이 틀을 바꾼다. */

const KEY = 'kh-fit-base';

function base() {
  try {
    const b = JSON.parse(localStorage.getItem(KEY) || 'null');
    return b && b.grow > 0 && b.fixed >= 0 ? b : null;
  } catch { return null; }   // 못 읽으면 창 폭으로만 — 화면은 그대로 뜬다
}

function fit() {
  const root = document.documentElement;
  if (!matchMedia('(min-width: 1281px)').matches) {
    ['--kh-s', '--kh-z', '--kh-rail-w'].forEach((k) => root.style.removeProperty(k));
    return;
  }
  const css = getComputedStyle(root);
  const nav = parseFloat(css.getPropertyValue('--nav-height')) || 0;
  const grid = parseFloat(css.getPropertyValue('--grid-max'));
  const gap = parseFloat(css.getPropertyValue('--kh-fit-gap')) || 0;   // home.css 한 곳
  if (!grid) return;
  const b = base();
  const rail = b ? (b.rail || 0) : 0;
  const room = innerHeight - nav - gap, wide = (root.clientWidth - rail - 2 * gap) / grid;
  // 아래 넷은 home.js fitScale 과 같은 식이다 — 고치면 둘을 함께 고친다
  let s = b ? Math.min(wide, (room - b.fixed) / b.grow) : wide, z = 1;
  if (s < 1) { s = 1; z = Math.max(0.1, b ? Math.min(wide, room / (b.fixed + b.grow)) : wide); }
  root.style.setProperty('--kh-s', s.toFixed(4));
  root.style.setProperty('--kh-z', z.toFixed(4));
  root.style.setProperty('--kh-rail-w', rail + 'px');   // 홀딩스 오른쪽 Claude 줄 자리만큼 비워 가운데가 같게 — nav.css 메뉴 기준선도 이것을 본다
}

fit();
addEventListener('resize', fit);
addEventListener('storage', (e) => { if (e.key === KEY) fit(); });   // 다른 탭에서 홀딩스가 새 값을 남기면
