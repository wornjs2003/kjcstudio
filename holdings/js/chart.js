/* ==========================================================================
   주식 차트 (TradingView Lightweight Charts v5)

   라이브러리는 js/vendor/lightweight-charts.js 에 두고 전역으로 불러온다.
   (holdings 자립 원칙 — 외부 CDN 에 의존하지 않는다)

   데이터는 /api/kis/chart 에서 받는다. 서버가 저장해 둔 일봉이라
   같은 종목을 여러 번 열어도 KIS 호출은 하루 한 번뿐이다.
   ========================================================================== */

import { color, alpha } from './theme.js';

/* 차트는 canvas 라 CSS 를 상속받지 못해 색을 문자열로 넘겨야 한다.
   그 값은 theme.js 가 css/theme.css 에서 읽어 오므로, 색을 바꿀 곳은
   여전히 css/theme.css 한 곳뿐이다. */
const COLOR = {
  get up()     { return color('up'); },        // 한국식: 상승 빨강
  get down()   { return color('down'); },      // 하락 파랑
  get text()   { return color('chart-axis'); },
  get grid()   { return color('chart-grid'); },
  get border() { return color('chart-border'); },
  get cross()  { return color('chart-crosshair'); },
  get label()  { return color('chart-label-bg'); },
  get ma5()    { return color('ma5'); },
  get ma20()   { return color('ma20'); },
  get ma60()   { return color('ma60'); },
};

/* 화면의 기간 버튼 → 서버가 쓰는 기간 코드 */
export const PERIOD_MAP = {
  '5m': '5m',   // 5분봉
  '1d': 'D',    // 일봉
  '1w': 'W',    // 주봉
  '1M': 'M',    // 월봉
  '1y': 'Y',    // 년봉
};

const MINUTE_PERIODS = new Set(['1m', '5m']);

/* 서버 ts → 라이브러리 시간 형식
   일/주/월/년봉: 'YYYY-MM-DD'
   분봉: UNIX 초 (같은 날 안에서 시각을 구분해야 하므로) */
function toChartTime(ts, period) {
  const s = String(ts);
  const date = `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
  if (!MINUTE_PERIODS.has(period) || s.length < 12) return date;
  const hh = Number(s.slice(8, 10));
  const mm = Number(s.slice(10, 12));
  // 한국 시간 기준으로 만든 뒤 UTC 초로 변환
  return Math.floor(
    Date.UTC(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8), hh - 9, mm) / 1000
  );
}

/* 단순 이동평균 */
function movingAverage(candles, period, barPeriod) {
  const out = [];
  let sum = 0;
  for (let i = 0; i < candles.length; i++) {
    sum += candles[i].close;
    if (i >= period) sum -= candles[i - period].close;
    if (i >= period - 1) {
      out.push({ time: toChartTime(candles[i].ts, barPeriod), value: sum / period });
    }
  }
  return out;
}

/* 서버에서 캔들 가져오기. periodId 는 화면 버튼 값('1d','5m' 등) */
export async function fetchCandles(code, periodId = '1d', limit = 240) {
  const period = PERIOD_MAP[periodId] || 'D';
  const r = await fetch(
    `/api/kis/chart?code=${code}&period=${period}&limit=${limit}`,
    { cache: 'no-store' }
  );
  if (!r.ok) throw new Error(`차트 데이터를 불러오지 못했습니다 (${r.status})`);
  const j = await r.json();
  if (!j || !j.ok) throw new Error(j?.error || '차트 데이터를 불러오지 못했습니다');
  return { candles: j.data.candles || [], meta: j.meta || {}, period };
}

/* ──────────────────────────────────────────────────────────────────────────
   차트 하나를 만들어 반환한다.
   반환값의 destroy() 를 호출해 정리한다 (화면을 다시 그릴 때 필요).
   ────────────────────────────────────────────────────────────────────────── */
export function createStockChart(container, candles, opts = {}) {
  const LC = window.LightweightCharts;
  if (!LC) throw new Error('차트 라이브러리를 불러오지 못했습니다');
  if (!candles || !candles.length) throw new Error('표시할 데이터가 없습니다');

  const showVolume = opts.showVolume !== false;
  const showMA = opts.showMA !== false;
  const period = opts.period || 'D';
  const isMinute = MINUTE_PERIODS.has(period);

  const chart = LC.createChart(container, {
    layout: {
      background: { color: 'transparent' },
      textColor: COLOR.text,
      fontFamily: "'Noto Sans KR', system-ui, sans-serif",
      fontSize: 11,
    },
    grid: {
      vertLines: { color: COLOR.grid },
      horzLines: { color: COLOR.grid },
    },
    rightPriceScale: {
      borderColor: COLOR.border,
      scaleMargins: { top: 0.08, bottom: showVolume ? 0.26 : 0.08 },
    },
    timeScale: {
      borderColor: COLOR.border,
      rightOffset: 4,
      fixLeftEdge: true,
      timeVisible: isMinute,      // 분봉이면 시:분까지 표시
      secondsVisible: false,
    },
    crosshair: {
      mode: LC.CrosshairMode.Normal,
      vertLine: { color: COLOR.cross, labelBackgroundColor: COLOR.label },
      horzLine: { color: COLOR.cross, labelBackgroundColor: COLOR.label },
    },
    localization: {
      locale: 'ko-KR',
      priceFormatter: (v) => Math.round(v).toLocaleString('ko-KR'),
    },
    autoSize: true,
  });

  // 캔들
  const candleSeries = chart.addSeries(LC.CandlestickSeries, {
    upColor: COLOR.up,
    downColor: COLOR.down,
    borderUpColor: COLOR.up,
    borderDownColor: COLOR.down,
    wickUpColor: COLOR.up,
    wickDownColor: COLOR.down,
  });
  candleSeries.setData(candles.map((c) => ({
    time: toChartTime(c.ts, period),
    open: c.open, high: c.high, low: c.low, close: c.close,
  })));

  // 거래량 (아래쪽에 겹쳐 표시)
  let volumeSeries = null;
  if (showVolume) {
    volumeSeries = chart.addSeries(LC.HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
      lastValueVisible: false,
      priceLineVisible: false,
    });
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.78, bottom: 0 },
      visible: false,
    });
    volumeSeries.setData(candles.map((c) => ({
      time: toChartTime(c.ts, period),
      value: c.volume,
      color: c.close >= c.open ? alpha('up', 0.30) : alpha('down', 0.30),
    })));
  }

  // 이동평균선
  const maSeries = [];
  if (showMA) {
    [[5, COLOR.ma5], [20, COLOR.ma20], [60, COLOR.ma60]].forEach(([maPeriod, color]) => {
      if (candles.length < maPeriod) return;
      const s = chart.addSeries(LC.LineSeries, {
        color, lineWidth: 1,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      s.setData(movingAverage(candles, maPeriod, period));
      maSeries.push({ period: maPeriod, color, series: s });
    });
  }

  chart.timeScale().fitContent();

  return {
    chart,
    candleSeries,
    volumeSeries,
    maSeries,
    destroy() {
      try { chart.remove(); } catch { /* 이미 정리됨 */ }
    },
  };
}

/* 범례용 — 어떤 이동평균이 그려졌는지 */
export function maLegend(maSeries) {
  return maSeries
    .map((m) => `<span style="color:${m.color}">MA${m.period}</span>`)
    .join(' · ');
}
