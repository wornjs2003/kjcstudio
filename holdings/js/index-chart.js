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

/* 데이터는 플롯 영역의 이만큼까지만 그린다. 나머지는 앞으로 올 시간의 자리다.

   전에는 마지막 점이 오른쪽 끝에 딱 붙어서, 현재가 표시와 시각 라벨이 잘려
   나갔다. 지금 시각이 90% 자리에 오면 오른쪽에 숨 쉴 틈이 생기고, 장이 진행될수록
   선이 그쪽으로 채워지는 것이 보인다 (2026-09-15 지시). */
const DATA_RIGHT = 0.9;

/* 어제 구간이 차지할 최대 폭.

   장이 막 열린 09:19 에는 어제 봉이 80개, 오늘 봉이 4개다. 개수대로 그리면
   화면의 95%가 어제 것이 되어 "어제 것만 나온다" 고 보인다. 어제는 왼쪽
   한 귀퉁이로 밀어 두고 오늘에 자리를 내준다. */
const PAST_MAX = 0.22;

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

  const py = v => PLOT.y1 - ((v - bot) / span) * (PLOT.y1 - PLOT.y0);

  /* ── 어제 / 오늘 나누기 ──
     마지막 봉의 날짜가 오늘이다. 그 앞 날짜는 전부 어제 구간으로 본다. */
  const today = bars[bars.length - 1].ts.slice(0, 8);
  const firstToday = bars.findIndex(b => b.ts.slice(0, 8) === today);
  const hasPast = firstToday > 0;

  /* 어제와 오늘에 폭을 나눠 준다.
     어제는 개수와 상관없이 PAST_MAX 안쪽으로 눌러 담고, 남은 자리를 오늘이 쓴다.
     오늘 구간은 09:00~15:30 을 기준으로 시간에 비례해 자리를 잡으므로,
     장 초반에는 왼쪽에만 선이 있고 시간이 갈수록 오른쪽으로 채워진다. */
  const W_ALL = (PLOT.x1 - PLOT.x0) * DATA_RIGHT;
  const pastW = hasPast ? Math.min(W_ALL * PAST_MAX, W_ALL * (firstToday / bars.length)) : 0;
  const todayW = W_ALL - pastW;
  const DAY_OPEN = 9 * 60, DAY_CLOSE = 15 * 60 + 30;

  function px(i) {
    if (!hasPast) return PLOT.x0 + (i / Math.max(1, bars.length - 1)) * W_ALL;
    if (i < firstToday) {
      return PLOT.x0 + (i / Math.max(1, firstToday - 1)) * pastW;
    }
    const m = minutesOf(bars[i].ts);
    const r = Math.max(0, Math.min(1, (m - DAY_OPEN) / (DAY_CLOSE - DAY_OPEN)));
    return PLOT.x0 + pastW + r * todayW;
  }

  const boundary = hasPast ? PLOT.x0 + pastW : null;

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
    /* 어제 구간은 왼쪽에 눌러 담아 폭이 좁다. 같은 간격으로 두면 라벨이 겹쳐
       "15:0012:0014:00" 처럼 뭉친다 (2026-09-15 확인). 더 드물게 찍는다. */
    if (x - lastLabelX < (isToday ? 34 : 52)) return;
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
  const lastX = px(bars.length - 1);

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
  /* 라벨이 그림 밖으로 나가면 글자가 잘린다("6,932.07" → "5,932.07" 처럼 보였다).
     왼쪽 끝에서는 오른쪽으로, 오른쪽 끝에서는 왼쪽으로 붙인다. */
  const dot = (i, v, label, below) => {
    const x = px(i);
    const anchor = x < 60 ? 'start' : (x > PLOT.x1 - 60 ? 'end' : 'middle');
    return `
      <circle cx="${x.toFixed(1)}" cy="${py(v).toFixed(1)}" r="3.5"
        fill="${color('bg-card')}" stroke="${color('text-primary')}" stroke-width="2"/>
      <text x="${x.toFixed(1)}" y="${(py(v) + (below ? 20 : -12)).toFixed(1)}" font-size="12"
        fill="${color('text-secondary')}" text-anchor="${anchor}">${label} ${fmt(v)}</text>`;
  };

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
