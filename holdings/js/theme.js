/* ==========================================================================
   KJC Holdings — 차트용 색 읽기

   canvas 와 SVG 는 CSS 를 상속받지 못합니다. 그래서 차트 색만은 JS 가
   직접 문자열로 넘겨야 하는데, 그 값을 여기서 css/theme.css 를 읽어 가져옵니다.
   결과적으로 색을 정하는 곳은 css/theme.css 한 곳뿐입니다.

   쓰는 법
     import { color, alpha } from '../theme.js';
     color('up')            → '#d92d20'          (--kh-up)
     alpha('up', 0.3)       → 'rgba(217,45,32,0.3)'  (--kh-up-rgb 기준)

   fallback 이 붙어 있는 이유
     CSS 로드가 끝나기 전에 호출되면 빈 문자열이 돌아옵니다. 그때 화면이
     색 없이 깨지지 않도록 theme.css 와 같은 값을 예비로 들고 있습니다.
     (theme.css 값을 바꾸면 아래 FALLBACK 도 같이 맞춰 주세요)
   ========================================================================== */

const FALLBACK = {
  'up': '#d92d20', 'down': '#0b63ce', 'flat': '#7a7a86',
  'accent': '#3a6ae8',
  'text-primary': '#17171b', 'text-secondary': '#5e5e6a',
  'text-muted': '#8c8c98', 'text-dim': '#b2b2bd',
  'bg-card': '#ffffff', 'border': 'rgba(0,0,0,0.09)',
  'chart-grid': 'rgba(0,0,0,0.06)', 'chart-border': 'rgba(0,0,0,0.10)',
  'chart-axis': '#6a6a76', 'chart-crosshair': 'rgba(0,0,0,0.28)',
  'chart-label-bg': '#3a3a44', 'chart-label-fg': '#ffffff',
  'ma5': '#b25e09', 'ma20': '#3a6ae8', 'ma60': '#7c3aed',
  'ind-1': '#3a6ae8', 'ind-2': '#b25e09', 'ind-3': '#7c3aed',
  'ind-4': '#d92d20', 'ind-5': '#6a6a76',
  'topic-war': '#d92d20', 'topic-ai': '#3a6ae8', 'topic-defense': '#b25e09',
  'topic-arctic': '#0f7a5f', 'topic-ship': '#7c3aed',
};

/* 반투명 계산의 기준이 되는 삼원색 (--kh-*-rgb) */
const FALLBACK_RGB = {
  'ink': '0 0 0', 'paper': '255 255 255', 'accent': '58 106 232',
  'up': '217 45 32', 'down': '11 99 206',
  'ok': '15 122 95', 'warn': '178 94 9',
};

const cache = new Map();

function read(varName) {
  if (cache.has(varName)) return cache.get(varName);
  let v = '';
  try {
    v = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  } catch { /* 문서가 아직 없으면 fallback 을 쓴다 */ }
  // 값이 비어 있으면 CSS 가 아직 안 붙은 것 — 캐시하지 않고 다음에 다시 읽는다
  if (v) cache.set(varName, v);
  return v;
}

/** theme.css 의 --kh-<name> 값. 예: color('up') */
export function color(name) {
  return read(`--kh-${name}`) || FALLBACK[name] || '#000000';
}

/** --kh-<name>-rgb 을 기준으로 만든 반투명 색. 예: alpha('up', 0.3) */
export function alpha(name, a) {
  const triplet = read(`--kh-${name}-rgb`) || FALLBACK_RGB[name] || '0 0 0';
  const [r, g, b] = triplet.split(/[\s,]+/);
  return `rgba(${r},${g},${b},${a})`;
}
