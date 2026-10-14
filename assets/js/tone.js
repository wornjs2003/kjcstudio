// 기준이 있는 수치의 색 짙기 — 모든 화면이 함께 쓴다 (2026-10-14 재권님 「달러인덱스를 100을 기준으로 높아질때 빨간색 낮아질때
// 파란색으로 … 편차가 커질수록 색이 짙어져야해」 · 「기준이 있고 높낮이가 있는 수치들은 전부 같은 룰이여야」).
// 룰은 CLAUDE.md 「기준이 있는 수치는 위 빨강 · 아래 파랑, 멀수록 짙게」. 수치마다의 기준 · 폭은 data/tone.json 한 곳이다.
//   import { ready, tone, paint } from '/assets/js/tone.js';
//   await ready;
//   tone('dxy', 102.18)          → { side: 'up', k: 0.58 }      쪽 · 짙기(0~1). 이름이 없거나 값이 없으면 { side: null, k: 0 }
//   paint('dxy', 102.18, 'bg')   → 'rgb(240 68 82 / 20%)'         바탕 · 'line' 은 선 · 점. 색을 안 칠할 자리는 ''
// · 색 값은 들고 있지 않는다 — 부를 때마다 theme.css 의 --kh-up-rgb · --kh-down-rgb · --kh-text-secondary 를 읽는다
// · 짙기를 불투명도로 옮기는 범위만 여기 한 곳에 둔다(바탕은 옅게 · 선은 진하게)
// · 글씨에는 쓰지 않는다 — 옅은 글씨는 안 읽힌다(「색 바탕 위의 글씨」)
// · tone.json 에 없는 이름은 색을 안 칠하고 콘솔에 한 번 알린다 — 짐작한 색을 내지 않는다
const DATA = new URL('../../data/tone.json', import.meta.url);
const RANGE = { bg: [0.06, 0.30], line: [0.35, 1] };   // 선 · 점은 35% 부터 — 그보다 옅으면 가는 선이 안 보인다

let byId = new Map();
const warned = new Set();
const warn = (key, msg) => { if (!warned.has(key)) { warned.add(key); console.warn('[tone] ' + msg); } };
export const ready = (async () => {
  try { byId = new Map(((await (await fetch(DATA, { cache: 'no-store' })).json()).items || []).map((it) => [it.id, it])); }
  catch { byId = new Map(); }
})();

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export function tone(id, v) {
  const it = byId.get(id);
  if (!it || !(it.full > 0)) {
    warn(id, `data/tone.json 에 「${id}」 가 없거나 폭이 비었습니다 — 색을 안 칠합니다`);
    return { side: null, k: 0 };
  }
  if (v == null || !Number.isFinite(+v)) return { side: null, k: 0 };
  const d = +v - it.base;
  return { side: d > 0 ? 'up' : d < 0 ? 'down' : 'flat', k: Math.min(Math.abs(d) / it.full, 1) };
}

export function paint(id, v, where = 'bg') {
  const { side, k } = tone(id, v);
  if (!side) return '';
  if (side === 'flat') return where === 'line' ? css('--kh-text-secondary') : '';   // 못 읽으면 '' 로 떨어진다
  if (!RANGE[where]) { warn('where:' + where, `paint 의 자리는 'bg' · 'line' 둘입니다(받은 것 「${where}」) — 색을 안 칠합니다`); return ''; }
  const [lo, hi] = RANGE[where];
  const rgb = css(side === 'up' ? '--kh-up-rgb' : '--kh-down-rgb');
  if (!rgb) { warn('css', 'theme.css 의 --kh-up-rgb · --kh-down-rgb 를 못 읽었습니다 — 색을 안 칠합니다'); return ''; }
  return `rgb(${rgb} / ${Math.round((lo + (hi - lo) * k) * 100)}%)`;
}
