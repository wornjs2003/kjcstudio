/* ==========================================================================
   KJC Holdings — 차트용 색 읽기

   canvas 와 SVG 는 CSS 를 상속받지 못합니다. 그래서 차트 색만은 JS 가
   직접 문자열로 넘겨야 하는데, 그 값을 여기서 css/theme.css 를 읽어 가져옵니다.
   결과적으로 색을 정하는 곳은 css/theme.css 한 곳뿐입니다.

   쓰는 법
     import { color, alpha } from '../theme.js';
     color('up')            → '#f04452'          (--kh-up)
     alpha('up', 0.3)       → 'rgba(240,68,82,0.3)'  (--kh-up-rgb 기준)

   fallback 이 붙어 있는 이유
     CSS 로드가 끝나기 전에 호출되면 빈 문자열이 돌아옵니다. 그때 화면이
     색 없이 깨지지 않도록 theme.css 와 같은 값을 예비로 들고 있습니다.
     (theme.css 값을 바꾸면 아래 FALLBACK 도 같이 맞춰 주세요)
   ========================================================================== */

const FALLBACK = {
  'up': '#f04452', 'down': '#3182f6', 'flat': '#8b95a1',
  'accent': '#3182f6',
  'text-primary': '#101013', 'text-secondary': '#4e5968',
  'text-muted': '#8b95a1', 'text-dim': '#b0b8c1',
  'bg-card': '#ffffff', 'border': '#f2f4f6',
  'chart-grid': 'rgba(16,16,19,0.06)', 'chart-border': '#f2f4f6',
  'chart-axis': '#8b95a1', 'chart-crosshair': 'rgba(16,16,19,0.28)',
  'chart-label-bg': '#101013', 'chart-label-fg': '#ffffff',
  'ma5': '#f29300', 'ma20': '#3182f6', 'ma60': '#8b5cf6',
  'ind-1': '#3182f6', 'ind-2': '#f29300', 'ind-3': '#8b5cf6',
  'ind-4': '#f04452', 'ind-5': '#8b95a1',
  'topic-war': '#f04452', 'topic-ai': '#3182f6', 'topic-defense': '#f29300',
  'topic-arctic': '#02a262', 'topic-ship': '#8b5cf6',
};

/* 반투명 계산의 기준이 되는 삼원색 (--kh-*-rgb) */
const FALLBACK_RGB = {
  'ink': '16 16 19', 'paper': '255 255 255', 'accent': '49 130 246',
  'up': '240 68 82', 'down': '49 130 246',
  'ok': '2 162 98', 'warn': '242 147 0',
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
