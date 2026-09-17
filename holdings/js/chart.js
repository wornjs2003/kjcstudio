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
 * **봉이 적어도 창은 그대로 둔다.** 왼쪽이 비고 봉 굵기는 늘 같다
 * (2026-09-17 지시 — "없으면 비워두면되고 크기는 통일").
 * 처음엔 적을 때 fitContent 로 물러섰는데, 그러면 있는 만큼 펼쳐져
 * 다시 굵어졌다 — LG화학 98개가 삼성전자 200개보다 눈에 띄게 굵었다.
 * 빈 자리는 "아직 덜 쌓였다" 를 보여주는 것이라 숨길 이유가 없다.
 *
 * 5분봉 120개면 10시간, 일봉이면 반년쯤이다.
 */
const VISIBLE_BARS = 120;

function showLastBars(chart, total) {
  const ts = chart.timeScale();
  try {
    /* from 이 음수여도 된다. 그만큼 왼쪽이 빈다 */
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
  const showLegend = opts.showLegend !== false;
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
      /* 범례가 왼쪽 위에 겹쳐 앉으므로 그만큼 위를 비워 둔다.
         안 비우면 높이 오른 봉의 꼭대기가 범례 뒤로 들어간다 */
      scaleMargins: {
        top: showLegend ? 0.16 : 0.08,
        bottom: showVolume ? 0.26 : 0.08,
      },
    },
    timeScale: {
      borderColor: COLOR.border,
      rightOffset: 4,
      /* 왼쪽 끝을 묶지 않는다. 봉이 VISIBLE_BARS 보다 적을 때 그만큼
         왼쪽을 비워야 봉 굵기가 종목마다 같아진다 (showLastBars 참고).
         묶어 두면 라이브러리가 범위를 데이터 안으로 되돌려 다시 굵어진다. */
      fixLeftEdge: false,
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
        maSeries.push({
          period: maPeriod, key, color,
          series: null, values: [], short: candles.length,
        });
        return;
      }
      const s = chart.addSeries(LC.LineSeries, {
        color, lineWidth: 1,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false,
        /* 전에 끈 선은 끈 채로 연다 (maOff 참고) */
        visible: !maOff().has(maPeriod),
      });
      const data = movingAverage(candles, maPeriod, period);
      s.setData(data);
      /* 범례가 봉 번호로 값을 찾는다. 앞의 maPeriod-1 개는 아직 값이 없다.
         라인 시리즈에 물어보면 꺼 둔 선은 답이 없어서 따로 들고 있는다 */
      const values = new Array(candles.length).fill(null);
      data.forEach((d, i) => { values[i + maPeriod - 1] = d.value; });
      maSeries.push({ period: maPeriod, key, color, series: s, values });
    });
  }

  showLastBars(chart, candles.length);

  const legend = showLegend
    ? mountLegend(container, chart, { candles, period, maSeries, showVolume })
    : null;

  return {
    chart,
    candleSeries,
    volumeSeries,
    maSeries,
    legend,

    /** 보는 창을 처음 상태로 되돌린다. 칸 크기가 바뀐 뒤에 부른다 —
     *  여기서 fitContent 를 부르면 봉 크기가 종목마다 다시 갈린다. */
    resetView() { showLastBars(chart, candles.length); },

    destroy() {
      if (legend) legend.destroy();
      try { chart.remove(); } catch { /* 이미 정리됨 */ }
    },
  };
}

/* ──────────────────────────────────────────────────────────────────────────
   범례 (2026-09-17)

   봉 위에 마우스를 올리면 그 봉의 시·고·저·종·거래량과 그 시점의 이동평균
   값을 적는다. 마우스가 차트 밖으로 나가면 **마지막 봉**으로 되돌린다 —
   빈 줄로 두면 줄이 접혔다 펴지며 칸 높이가 출렁인다.

   범례는 차트 칸 **안에** 겹쳐 둔다. 바깥에 두면 위와 같은 이유로 자리를
   따로 잡아야 하고, 세 화면(종목·모달·미리보기)이 각자 자리를 만들어야 한다.

   모양은 css/stock.css 의 `.kh-lg*` 가 정한다 (첫 화면도 그 파일을 읽는다).
   색은 거기서 var(--kh-*) 로만 쓴다.
   ────────────────────────────────────────────────────────────────────────── */

/* 끈 이동평균은 브라우저에 기억해 둔다. 차트마다 따로 두지 않는다 —
   첫 화면에는 지수 차트와 미리보기 차트가 함께 떠 있어서, 한쪽에서 끈 선이
   다른 쪽에 그대로 있으면 "껐다" 로 읽히지 않는다. */
const MA_OFF_KEY = 'kh.chart.ma-off';
let _maOff = null;

/* 지금 떠 있는 범례들의 새로고침 함수. 한 곳에서 끄면 전부 따라 바뀐다 */
const _legendSync = new Set();

function maOff() {
  if (_maOff) return _maOff;
  let saved = [];
  try { saved = JSON.parse(localStorage.getItem(MA_OFF_KEY) || '[]'); } catch { /* 저장 못 씀 */ }
  _maOff = new Set(Array.isArray(saved) ? saved.map(Number).filter(Number.isFinite) : []);
  return _maOff;
}

function saveMaOff() {
  try { localStorage.setItem(MA_OFF_KEY, JSON.stringify([..._maOff])); } catch { /* 저장 못 씀 */ }
}

/* 차트 밖(패널 머리·차트 아래 줄)에 뿌려 둔 maLegend 도 함께 흐려 준다.
   그리는 곳이 달라 한 번에 못 고치므로 DOM 에서 찾아 맞춘다 */
function syncOuterLegends() {
  const off = maOff();
  document.querySelectorAll('.kh-lg-out [data-ma]').forEach((n) => {
    n.classList.toggle('is-off', off.has(Number(n.dataset.ma)));
  });
}

/* 라이브러리가 돌려주는 시간 → 우리가 만든 키.
   문자열('YYYY-MM-DD')이나 UNIX 초가 그대로 오지만, 판이 바뀌어
   {year,month,day} 로 와도 같은 키가 되도록 해 둔다 */
function timeKey(t) {
  if (t == null) return '';
  if (typeof t === 'object') {
    const p = (n) => String(n).padStart(2, '0');
    return `${t.year}-${p(t.month)}-${p(t.day)}`;
  }
  return String(t);
}

function fmtPrice(v, dec) {
  if (v == null || !Number.isFinite(v)) return '—';
  return v.toLocaleString('ko-KR', { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

function fmtVol(v) {
  if (v == null || !Number.isFinite(v)) return '—';
  const unit = (n, d) => (n / d).toLocaleString('ko-KR', { maximumFractionDigits: 1 });
  if (v >= 1e8) return `${unit(v, 1e8)}억`;
  if (v >= 1e4) return `${unit(v, 1e4)}만`;
  return Math.round(v).toLocaleString('ko-KR');
}

/* 이보다 좁거나 낮으면 한 줄로 줄인다.
   미리보기 차트는 168px 높이라 두 줄이 차트의 3분의 1을 덮는다 */
const LEGEND_COMPACT_W = 420;
const LEGEND_COMPACT_H = 200;

function maChip(m) {
  if (m.series == null) {
    /* 못 그린 선은 왜 없는지 적는다. 빠뜨린 것과 자료가 모자란 것은 다르다.
       「끈 것」(색이 남은 채 흐림)과도 구분된다 */
    return `<span class="kh-lg-c is-short"
      title="봉이 ${m.short}개뿐입니다. ${m.period}개가 있어야 그립니다"
      >MA${m.period} 봉 부족</span>`;
  }
  return `<button type="button" class="kh-lg-c" data-ma="${m.period}"
    style="color: var(--kh-${m.key})" title="눌러서 끄고 켭니다"
    ><span>MA${m.period}</span><b data-f="ma${m.period}">—</b></button>`;
}

function mountLegend(container, chart, { candles, period, maSeries, showVolume }) {
  container.classList.add('kh-lg-host');

  /* 지수는 소수점이 있고 종목은 정수다. 받은 값을 보고 정한다 */
  const dec = candles.some((c) => Math.abs(c.close - Math.round(c.close)) > 1e-9) ? 2 : 0;

  const idxByTime = new Map();
  candles.forEach((c, i) => idxByTime.set(timeKey(toChartTime(c.ts, period)), i));

  const el = document.createElement('div');
  el.className = 'kh-lg';
  el.innerHTML = `
    <div class="kh-lg-ohlc kh-num">
      <span><i>시</i><b data-f="open">—</b></span>
      <span><i>고</i><b data-f="high" class="kh-up">—</b></span>
      <span><i>저</i><b data-f="low" class="kh-down">—</b></span>
      <span><i>종</i><b data-f="close">—</b></span>
      ${showVolume ? '<span class="kh-lg-vol"><i>거래량</i><b data-f="volume">—</b></span>' : ''}
    </div>
    <div class="kh-lg-ma">${maSeries.map(maChip).join('')}</div>`;
  container.appendChild(el);

  const nodes = {};
  el.querySelectorAll('[data-f]').forEach((n) => { nodes[n.dataset.f] = n; });

  function render(i) {
    const c = candles[i];
    if (!c) return;
    nodes.open.textContent = fmtPrice(c.open, dec);
    nodes.high.textContent = fmtPrice(c.high, dec);
    nodes.low.textContent = fmtPrice(c.low, dec);
    nodes.close.textContent = fmtPrice(c.close, dec);
    /* 종가 색은 직전 봉 종가와 견준다 (한국식 — 오르면 빨강, 내리면 파랑).
       첫 봉은 견줄 것이 없어 그 봉의 시가를 쓴다 */
    const prev = i > 0 ? candles[i - 1].close : c.open;
    nodes.close.className =
      c.close > prev ? 'kh-up' : c.close < prev ? 'kh-down' : 'kh-flat';
    if (nodes.volume) nodes.volume.textContent = fmtVol(c.volume);
    maSeries.forEach((m) => {
      const n = nodes[`ma${m.period}`];
      if (n) n.textContent = fmtPrice(m.values[i], dec);
    });
  }

  /* 끈 선을 선·칩 양쪽에 반영한다 */
  function syncOff() {
    const off = maOff();
    maSeries.forEach((m) => {
      if (m.series) m.series.applyOptions({ visible: !off.has(m.period) });
    });
    el.querySelectorAll('[data-ma]').forEach((b) => {
      b.classList.toggle('is-off', off.has(Number(b.dataset.ma)));
    });
  }
  _legendSync.add(syncOff);

  el.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-ma]');
    if (!btn) return;
    const p = Number(btn.dataset.ma);
    const off = maOff();
    if (off.has(p)) off.delete(p); else off.add(p);
    saveMaOff();
    _legendSync.forEach((fn) => fn());
    syncOuterLegends();
  });

  /* 좁으면 한 줄만 남긴다 */
  let ro = null;
  function fit() {
    el.classList.toggle(
      'is-compact',
      container.clientWidth < LEGEND_COMPACT_W || container.clientHeight < LEGEND_COMPACT_H
    );
  }

  const onMove = (param) => {
    const i = (param && param.time != null && param.point)
      ? idxByTime.get(timeKey(param.time))
      : null;
    /* 차트 밖으로 나가면 마지막 봉. 빈 줄로 두지 않는다 */
    render(i == null ? candles.length - 1 : i);
  };
  chart.subscribeCrosshairMove(onMove);

  syncOff();
  render(candles.length - 1);
  fit();
  if (window.ResizeObserver) {
    ro = new ResizeObserver(fit);
    ro.observe(container);
  }

  return {
    destroy() {
      _legendSync.delete(syncOff);
      if (ro) ro.disconnect();
      try { chart.unsubscribeCrosshairMove(onMove); } catch { /* 이미 정리됨 */ }
      el.remove();
      container.classList.remove('kh-lg-host');
    },
  };
}

/* 차트 칸 밖에 두는 범례 — 패널 머리(stock.html)와 지수 차트 아래 줄에서 쓴다.
   어떤 이동평균이 그려졌는지, 못 그린 것이 있으면 왜인지 적는다.
   값과 켜고 끄기는 차트 안 범례(.kh-lg)가 맡는다. */
export function maLegend(maSeries) {
  const off = maOff();
  const items = maSeries
    .map((m) => (m.short != null
      ? `<span class="kh-lg-short" title="봉이 ${m.short}개뿐입니다. ${m.period}개가 있어야 그립니다"
           >MA${m.period} 봉 부족</span>`
      /* 색만 인라인이다. 선 색과 같아야 어느 선인지 알아보는데, 그 값은
         MA_LINES 가 정하므로 CSS 에 네 줄을 또 적으면 목록이 둘이 된다.
         값 자체는 theme.css 의 var(--kh-ma*) 를 가리킨다 */
      : `<span class="kh-lg-n${off.has(m.period) ? ' is-off' : ''}" data-ma="${m.period}"
           style="color: var(--kh-${m.key})">MA${m.period}</span>`))
    .join(' · ');
  return `<span class="kh-lg-out">${items}</span>`;
}
