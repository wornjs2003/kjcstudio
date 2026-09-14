/* ==========================================================================
   지수 당일 차트

   네이버 증권 메인의 코스피 영역을 참고해 만들었습니다 (2026-09-14 지시).
   캔들 차트(TradingView)를 쓰지 않고 SVG 로 직접 그립니다. 선 하나에
   눈금과 점선만 있으면 되는 그림이라, 라이브러리를 쓰면 오히려 맞추기 어렵습니다.

   들어오는 것: /api/kis/index-minutes 의 bars
     [{ ts: "202609141530", open, high, low, close }, ...]  옛것부터

   어제와 오늘이 함께 옵니다. 어제 구간은 회색으로 가라앉히고 오늘만 흰 바탕에
   둡니다. 그래야 "오늘 얼마나 움직였나" 가 한눈에 들어옵니다.

   시간 라벨은 SVG 안에 넣습니다. 바깥에 div 로 빼면 점선과 어긋납니다.
   ========================================================================== */

import { color } from './theme.js';

/* 그림 크기 — 실제 화면 크기는 CSS 가 정하고, 이 값은 비율만 잡는다 */
const W = 1000, H = 342;
const PLOT = { x0: 0, x1: 920, y0: 20, y1: 310 };   // 오른쪽 80 은 값 라벨 자리

const fmt = n => n.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/* "202609141530" → 분(0~1439) */
function minutesOf(ts) {
  return Number(ts.slice(8, 10)) * 60 + Number(ts.slice(10, 12));
}

function esc(s) {
  return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/**
 * 지수 당일 차트를 SVG 문자열로 돌려준다.
 * 값이 모자라면 빈 문자열 — 부르는 쪽이 "불러오는 중" 을 그대로 두면 된다.
 */
export function indexChartSvg(bars) {
  if (!bars || bars.length < 2) return '';

  const closes = bars.map(b => b.close);
  const lo = Math.min(...closes), hi = Math.max(...closes);
  const pad = Math.max((hi - lo) * 0.12, 0.01);
  const top = hi + pad, bot = lo - pad;
  const span = Math.max(1e-9, top - bot);

  const px = i => PLOT.x0 + (i / (bars.length - 1)) * (PLOT.x1 - PLOT.x0);
  const py = v => PLOT.y1 - ((v - bot) / span) * (PLOT.y1 - PLOT.y0);

  /* ── 어제 / 오늘 나누기 ──
     마지막 봉의 날짜가 오늘이다. 그 앞 날짜는 전부 어제 구간으로 본다. */
  const today = bars[bars.length - 1].ts.slice(0, 8);
  const firstToday = bars.findIndex(b => b.ts.slice(0, 8) === today);
  const boundary = firstToday > 0 ? px(firstToday) : null;

  /* 전일 종가 — 어제 마지막 봉. 없으면 선을 그리지 않는다 */
  const prevClose = firstToday > 0 ? bars[firstToday - 1].close : null;

  const up = bars[bars.length - 1].close >= (prevClose ?? bars[0].close);
  const line = up ? color('up') : color('down');

  /* ── 가로 눈금 5줄 + 값 라벨 ── */
  const rows = 4;
  let grid = '', labels = '';
  for (let i = 0; i <= rows; i++) {
    const y = PLOT.y0 + (i / rows) * (PLOT.y1 - PLOT.y0);
    const v = top - (i / rows) * span;
    grid += `<line x1="${PLOT.x0}" y1="${y.toFixed(1)}" x2="${PLOT.x1}" y2="${y.toFixed(1)}"
      stroke="${color('chart-grid')}" stroke-width="1" stroke-dasharray="3 3"/>`;
    labels += `<text x="${PLOT.x1 + 10}" y="${(y + 4).toFixed(1)}" font-size="12"
      fill="${color('chart-axis')}">${fmt(v)}</text>`;
  }

  /* ── 세로 30분 점선 + 시간 라벨 ──
     어제 구간은 폭이 좁아 라벨만 1시간 간격으로 줄인다. 점선은 30분마다 둔다. */
  let vlines = '', times = '';
  let lastLabelX = -999;
  bars.forEach((b, i) => {
    const m = minutesOf(b.ts);
    if (m % 30 !== 0) return;
    const x = px(i);
    vlines += `<line x1="${x.toFixed(1)}" y1="${PLOT.y0}" x2="${x.toFixed(1)}" y2="${PLOT.y1}"
      stroke="${color('chart-grid')}" stroke-width="1" stroke-dasharray="2 4"/>`;

    const isToday = b.ts.slice(0, 8) === today;
    if (!isToday && m % 60 !== 0) return;        // 어제는 정시만
    /* 날짜 경계 자리는 날짜 라벨("09.14.")이 쓴다. 시간까지 넣으면 겹쳐서
       "09.14." 와 "09:00" 이 서로 뭉개진다. */
    if (i === firstToday) return;
    if (x - lastLabelX < 34) return;             // 너무 붙으면 건너뛴다
    lastLabelX = x;
    const hh = String(Math.floor(m / 60)).padStart(2, '0');
    const mm = String(m % 60).padStart(2, '0');
    /* 양 끝은 기준점을 옮긴다. 가운데 정렬로 두면 글자 절반이 그림 밖으로
       나가 잘린다 (왼쪽 첫 라벨이 "14:00" → "4:00" 으로 보였다). */
    const anchor = x < 20 ? 'start' : (i >= bars.length - 2 ? 'end' : 'middle');
    times += `<text x="${x.toFixed(1)}" y="${PLOT.y1 + 22}" font-size="12"
      fill="${color('chart-axis')}" text-anchor="${anchor}">${hh}:${mm}</text>`;
  });

  /* 날짜 경계 — 어디부터 오늘인지 */
  let dateMark = '';
  if (boundary != null) {
    const d = today.slice(4, 6) + '.' + today.slice(6, 8) + '.';
    dateMark = `
      <line x1="${boundary.toFixed(1)}" y1="${PLOT.y0}" x2="${boundary.toFixed(1)}" y2="${PLOT.y1}"
        stroke="${color('chart-axis')}" stroke-width="1" opacity=".45"/>
      <text x="${boundary.toFixed(1)}" y="${PLOT.y1 + 22}" font-size="12" font-weight="700"
        fill="${color('text-secondary')}" text-anchor="middle">${d}</text>`;
  }

  /* ── 선과 면 ── */
  const pts = bars.map((b, i) => `${px(i).toFixed(1)},${py(b.close).toFixed(1)}`).join(' ');
  const area = `${PLOT.x0},${PLOT.y1} ${pts} ${px(bars.length - 1).toFixed(1)},${PLOT.y1}`;

  /* ── 전일 종가선 + 오른쪽 말풍선 ── */
  let prevLine = '';
  if (prevClose != null) {
    const y = py(prevClose);
    prevLine = `
      <line x1="${PLOT.x0}" y1="${y.toFixed(1)}" x2="${PLOT.x1}" y2="${y.toFixed(1)}"
        stroke="${color('text-muted')}" stroke-width="1" stroke-dasharray="4 3"/>
      <rect x="${PLOT.x1 - 86}" y="${(y - 11).toFixed(1)}" width="86" height="22" rx="5"
        fill="${color('chart-label-bg')}"/>
      <text x="${PLOT.x1 - 43}" y="${(y + 4).toFixed(1)}" font-size="12" font-weight="600"
        fill="${color('chart-label-fg')}" text-anchor="middle">${fmt(prevClose)}</text>`;
  }

  /* ── 최고 · 최저 · 현재 ── */
  const iHi = closes.indexOf(hi), iLo = closes.indexOf(lo);
  const dot = (i, v, label, below) => `
    <circle cx="${px(i).toFixed(1)}" cy="${py(v).toFixed(1)}" r="3.5"
      fill="${color('bg-card')}" stroke="${color('text-primary')}" stroke-width="2"/>
    <text x="${px(i).toFixed(1)}" y="${(py(v) + (below ? 20 : -12)).toFixed(1)}" font-size="12"
      fill="${color('text-secondary')}" text-anchor="middle">${label} ${fmt(v)}</text>`;

  const iEnd = bars.length - 1;
  const endDot = `
    <circle cx="${px(iEnd).toFixed(1)}" cy="${py(closes[iEnd]).toFixed(1)}" r="8"
      fill="${line}" opacity=".18"/>
    <circle cx="${px(iEnd).toFixed(1)}" cy="${py(closes[iEnd]).toFixed(1)}" r="4" fill="${line}"/>`;

  const gid = 'khidx' + Math.random().toString(36).slice(2, 8);

  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"
      style="width:100%;height:100%;display:block" role="img"
      aria-label="지수 당일 흐름">
    <defs>
      <linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"   stop-color="${line}" stop-opacity=".16"/>
        <stop offset="100%" stop-color="${line}" stop-opacity="0"/>
      </linearGradient>
    </defs>

    <!-- 어제 구간은 가라앉힌다 -->
    ${boundary != null ? `<rect x="${PLOT.x0}" y="${PLOT.y0}"
      width="${(boundary - PLOT.x0).toFixed(1)}" height="${PLOT.y1 - PLOT.y0}"
      fill="${color('chart-grid')}"/>` : ''}

    ${grid}${vlines}
    <polygon points="${esc(area)}" fill="url(#${gid})"/>
    ${prevLine}
    <polyline points="${esc(pts)}" fill="none" stroke="${line}"
      stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>
    ${iHi !== iEnd ? dot(iHi, hi, '최고', false) : ''}
    ${iLo !== iEnd ? dot(iLo, lo, '최저', true) : ''}
    ${endDot}
    ${dateMark}${labels}${times}
  </svg>`;
}
