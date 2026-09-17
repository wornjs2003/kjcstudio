/* ==========================================================================
   주식 차트 (TradingView Lightweight Charts v5)

   라이브러리는 js/vendor/lightweight-charts.js 에 두고 전역으로 불러온다.
   (holdings 자립 원칙 — 외부 CDN 에 의존하지 않는다)

   데이터는 /api/kis/chart 에서 받는다. 서버가 저장해 둔 일봉이라
   같은 종목을 여러 번 열어도 KIS 호출은 하루 한 번뿐이다.
   ========================================================================== */

import { color, alpha } from './theme.js';
import { apiFetch } from './data/api.js';

/* 차트는 canvas 라 CSS 를 상속받지 못해 색을 문자열로 넘겨야 한다.
   그 값은 theme.js 가 ../assets/css/theme.css 에서 읽어 오므로, 색을 바꿀
   곳은 여전히 그 한 곳뿐이다. */
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
  get ma200()  { return color('ma200'); },
};

/* 그릴 이동평균선. 늘리려면 여기 한 줄과 theme.css·theme.js 의 색만 더한다.
   (2026-09-16 지시 — 5 · 20 · 60 · 200) */
const MA_LINES = [[5, 'ma5'], [20, 'ma20'], [60, 'ma60'], [200, 'ma200']];

/* 한 화면에 몇 봉을 보일 것인가.
 *
 * **봉 크기를 종목마다 같게 하려고 둔다** (2026-09-17 지시 —
 * "마우스 움직일때마다 차트 스케일도 각각 다르네").
 *
 * 전에는 fitContent() 로 **있는 봉을 전부** 채워 넣었다. 그래서 받아둔
 * 개수가 다르면 봉 굵기도 달라졌다 — 삼성전자 300개는 촘촘하고
 * 삼성전자우 47개는 듬성했다. 개수가 아니라 **보는 창을 고정**한다.
 *
 * 봉이 이보다 적으면 있는 만큼만 보인다. 더 많으면 끌어서 과거를 본다.
 * 5분봉 120개면 10시간, 일봉이면 반년쯤이다.
 */
const VISIBLE_BARS = 120;

function showLastBars(chart, total) {
  const ts = chart.timeScale();
  if (total <= VISIBLE_BARS) { ts.fitContent(); return; }
  try {
    ts.setVisibleLogicalRange({ from: total - VISIBLE_BARS, to: total - 1 });
  } catch {
    ts.fitContent();          // 라이브러리 판이 다르면 예전대로
  }
}

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
  /* 한국 시각을 그대로 UTC 자리에 넣는다.
     라이브러리는 받은 초를 UTC 로 읽어 눈금에 적는다. 그래서 09:00(한국)을
     진짜 UTC(00:00)로 바꿔 넣으면 눈금에 00:00 이 찍힌다. 실제로 장 마감
     15:30 자리에 05:00 이 나왔다 (2026-09-15 확인). 옮기지 않고 넣어야
     눈금이 한국 시각으로 읽힌다. 이 값은 눈금과 순서에만 쓰인다. */
  return Math.floor(
    Date.UTC(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8), hh, mm) / 1000
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

/* 받아둔 봉을 잠깐 쥐고 있는다.
 *
 * 목록에 마우스를 올리면 미리보기가 그 종목으로 바뀌는데(2026-09-16 지시),
 * 목록을 훑으면 종목 수만큼 요청이 나간다. **5분봉은 서버에 캐시가 없어
 * 부를 때마다 KIS 로 간다.** 오늘 배포본이 터진 것이 동시 요청 때문이었다.
 *
 * 화면에서 잠깐 쥐면 같은 종목에 다시 올려도 안 부른다. 종목 화면에서
 * 기간 단추를 왔다 갔다 할 때도 함께 덕을 본다.
 *
 * 서버에도 캐시를 두는 편이 근본이지만 kis_proxy.py 와 kis-worker.js 를
 * 같이 고쳐야 한다. 그것은 따로 잡는다.
 */
const CANDLE_TTL_MS = 60_000;
const CANDLE_MAX = 60;              // 이보다 쌓이면 오래된 것부터 버린다
const _candleCache = new Map();

/* 서버에서 캔들 가져오기. periodId 는 화면 버튼 값('1d','5m' 등) */
export async function fetchCandles(code, periodId = '1d', limit = 240) {
  const period = PERIOD_MAP[periodId] || 'D';
  const key = `${code}:${period}:${limit}`;

  const hit = _candleCache.get(key);
  if (hit && Date.now() - hit.at < CANDLE_TTL_MS) return hit.value;

  const r = await apiFetch(
    `/api/kis/chart?code=${code}&period=${period}&limit=${limit}`,
    { cache: 'no-store' }
  );
  if (!r) throw new Error('로그인이 만료되었습니다');
  if (!r.ok) throw new Error(`차트 데이터를 불러오지 못했습니다 (${r.status})`);
  const j = await r.json();
  if (!j || !j.ok) throw new Error(j?.error || '차트 데이터를 불러오지 못했습니다');

  const value = { candles: j.data.candles || [], meta: j.meta || {}, period };
  _candleCache.set(key, { at: Date.now(), value });
  if (_candleCache.size > CANDLE_MAX) {
    _candleCache.delete(_candleCache.keys().next().value);
  }
  return value;
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

  /* 이동평균선 — 5 · 20 · 60 · 200 (2026-09-16 지시).
   *
   * **봉이 모자라면 그렇게 적는다.** 전에는 조용히 건너뛰었는데, 지수 봉이
   * 50개만 오는 바람에 MA60 부터 안 그려지는 것을 아무도 몰랐다. 안 나오는
   * 것과 못 그리는 것은 다르고, 화면이 그 차이를 말해야 한다
   * (holdings/CLAUDE.md 데이터 규칙). */
  const maSeries = [];
  if (showMA) {
    MA_LINES.forEach(([maPeriod, key]) => {
      const color = COLOR[key];
      if (candles.length < maPeriod) {
        maSeries.push({ period: maPeriod, color, series: null, short: candles.length });
        return;
      }
      const s = chart.addSeries(LC.LineSeries, {
        color, lineWidth: 1,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      s.setData(movingAverage(candles, maPeriod, period));
      maSeries.push({ period: maPeriod, color, series: s });
    });
  }

  showLastBars(chart, candles.length);

  return {
    chart,
    candleSeries,
    volumeSeries,
    maSeries,

    /** 보는 창을 처음 상태로 되돌린다. 칸 크기가 바뀐 뒤에 부른다 —
     *  여기서 fitContent 를 부르면 봉 크기가 종목마다 다시 갈린다. */
    resetView() { showLastBars(chart, candles.length); },

    destroy() {
      try { chart.remove(); } catch { /* 이미 정리됨 */ }
    },
  };
}

/* 범례용 — 어떤 이동평균이 그려졌는지 */
export function maLegend(maSeries) {
  return maSeries
    .map((m) => (m.short != null
      /* 못 그린 선은 왜 없는지 적는다. 빠뜨린 것과 자료가 모자란 것은 다르다 */
      ? `<span class="kh-mut" title="봉이 ${m.short}개뿐입니다. ${m.period}개가 있어야 그립니다"
           >MA${m.period} 봉 부족</span>`
      : `<span style="color:${m.color}">MA${m.period}</span>`))
    .join(' · ');
}
