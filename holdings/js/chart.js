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
  /* 보조지표 — theme.css 에 이미 다섯이 있다 (--kh-ind-1 … 5) */
  get ind1()   { return color('ind-1'); },     // 파랑
  get ind2()   { return color('ind-2'); },     // 주황
  get ind3()   { return color('ind-3'); },     // 보라
  get ind4()   { return color('ind-4'); },     // 빨강
  get ind5()   { return color('ind-5'); },     // 회색

  /* 보조지표 전용 */
  get band()     { return color('band'); },        // 볼린저 실선 (노랑)
  get bandFill() { return alpha('band', 0.10); },  // 밴드 안 옅은 노랑
  get cardBg()   { return color('bg-card'); },     // 띠 아래를 덮는 카드 색
  get rsi()      { return color('rsi'); },
  get rsiSig()   { return color('ma20'); },
  get rsiBand()  { return alpha('rsi-band', 0.10); },   // 30~70 띠 — 옅은 파랑

  /* 값이 없는 구간 — **미래**(아직 안 온 봉). 2026-09-29 지시 —
     「미래에 아직 안나온 값은 파란색으로」. 진하기는 아래 NODATA_ALPHA 한 곳에서 정한다 */
  get noData()   { return alpha('nodata', NODATA_ALPHA); },
};

/* 미래 영역의 진하기. **가장 뒤에 깔리는 배경이라 차트의 파란 것 중 가장 옅다** —
   하락 봉 1.0 · 매물대 VP_ALPHA · RSI 띠 0.10 · 여기.
   재권님이 화면을 보시고 조절하실 값이라 **한 곳에만** 둔다. */
const NODATA_ALPHA = 0.06;

/* 그릴 이동평균선. 늘리려면 여기 한 줄과 theme.css·theme.js 의 색만 더한다.
   (2026-09-16 지시 — 5 · 20 · 60 · 200) */
const MA_LINES = [[5, 'ma5'], [20, 'ma20'], [60, 'ma60'], [200, 'ma200']];

/* 지표 기간을 **한 곳에** 모은다 (2026-09-29).
 *
 * 전에는 각 함수의 기본 인자에만 있었다. 그러면 「몇 봉을 받아야 하나」 를
 * 셀 때 그 숫자를 **다시 적게 되고**, 그 순간 목록이 둘이 된다.
 * 아래 BARS_FOR_IND 가 이것을 보고 센다. */
export const IND_PERIOD = {
  bb: 20,                                  // 볼린저 밴드
  rsi: 14,
  macdFast: 12, macdSlow: 26, macdSig: 9,
  vol: 20,                                 // 거래량 이동평균
  ichA: 9, ichB: 26, ichC: 52,             // 일목균형표
};

/* 보조지표 (2026-09-17 지시 — "필요한 보조지표들 추가").
 *
 * **기본은 전부 꺼짐이다.** 다섯을 한꺼번에 켜면 선이 열 개를 넘어 봉이 안 보인다.
 * 켠 것은 localStorage 에 남아 다음에 열 때 이어진다 — 이동평균과 같은 방식이다.
 *
 *   pane  price   가격 그림 위에 겹친다
 *         volume  거래량 칸에 겹친다
 *         own     제 칸을 아래에 새로 만든다 (그만큼 가격 그림이 줄어든다)
 */
export const INDICATORS = [
  /* 매물대는 **배경**이다. 가장 먼저 깔리고 그 위에 봉과 보조지표가 온다
     (2026-09-18 지시). 차트 canvas 가 아니라 그 뒤의 층에 그린다 —
     캔들 위에 겹치면 봉이 가려진다. */
  { key: 'vp',   name: '매물대',      pane: 'price' },
  { key: 'bb',   name: '볼린저 밴드', pane: 'price' },
  { key: 'ma',   name: '이동평균선',  pane: 'price' },
  { key: 'vol',  name: '거래량',      pane: 'own'   },
  { key: 'macd', name: 'MACD',       pane: 'own'   },
  { key: 'rsi',  name: 'RSI',        pane: 'own'   },
];

/* 같은 화면의 차트들이 함께 맞춘다. 한 곳에서 켜면 나머지도 따라간다 */
const _indSync = new Set();

const IND_ON_KEY = 'kh.chart.ind-on';
/* 사용자가 이미 본 적 있는 지표. 나중에 붙인 것을 한 번 켜 주는 데 쓴다 */
const IND_SEEN_KEY = 'kh.chart.ind-seen';
const IND_NEW = ['vp'];          // 2026-09-18 에 붙인 것
let _indOn = null;

export function indOn() {
  if (_indOn) return _indOn;
  let saved = null;
  try {
    const raw = localStorage.getItem(IND_ON_KEY);
    saved = raw == null ? null : JSON.parse(raw);
  } catch { /* 저장 못 씀 */ }
  const names = INDICATORS.map((x) => x.key);
  _indOn = new Set(Array.isArray(saved)
    ? saved.filter((k) => names.includes(k))
    : ['ma', 'vol', 'vp']);    // 처음 열면 이동평균 · 거래량 · 매물대

  /* **나중에 생긴 지표는 처음 한 번 켜 준다** (2026-09-18).
     저장된 설정이 있으면 기본값을 안 보므로, 새로 붙인 것이 화면에
     영영 안 나온다. 「본 적 있는 지표」를 따로 적어 두고 처음 한 번만
     켠다. 사용자가 끄면 그때부터 꺼진 채로 남는다. */
  try {
    const raw2 = localStorage.getItem(IND_SEEN_KEY);
    const seen = new Set(raw2 == null ? [] : JSON.parse(raw2));
    if (saved) IND_NEW.forEach((k) => { if (!seen.has(k)) _indOn.add(k); });
    localStorage.setItem(IND_SEEN_KEY, JSON.stringify(names));
  } catch { /* 저장 못 써도 화면은 돌아야 한다 */ }

  return _indOn;
}

function saveIndOn() {
  try { localStorage.setItem(IND_ON_KEY, JSON.stringify([..._indOn])); } catch { /* 저장 못 씀 */ }
}

/* 아래 칸 하나가 먹는 높이 비율. 셋이 다 켜지면 가격이 절반 아래로 내려간다 */
const PANE_H = 0.18;

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
 *
 * ⚠️ **이 값은 「처음에 보이는 봉」 이 아니다 (2026-09-29).** 처음 보이는 것은
 * 기간마다 다르고(`CHART_PERIODS` 의 `initBars`), 이 값은 **지표가 끊기지
 * 않을 것을 보장하는 범위**다. 아래 `BARS_FOR_IND` 가 이것을 쓴다.
 *
 * **둘을 한 값으로 두면 안 된다.** 초기 봉을 줄이는 순간 받는 봉도 함께
 * 줄어 **확대를 풀었을 때 지표가 왼쪽에서 끊긴다.** 초기 봉은 재권님이
 * 화면을 보시고 정하는 값이라 자주 바뀐다 — 2026-09-29 하루에 한 번
 * 바뀌었다(5분 30 → 120 · 일 30 → 90).
 */
const VISIBLE_BARS = 120;

/* 보이는 구간 **전체**에 **모든 지표**가 있으려면 이만큼 받아야 한다.
 *
 * movingAverage 는 p-1 번째 봉부터 값을 채운다(위 drawOverlay 의 values).
 * 그래서 보이는 120봉의 왼쪽 끝이 그 지점보다 뒤에 있어야 선이 끊기지 않는다.
 *
 *     필요한 봉 = VISIBLE_BARS + 가장 긴 MA = 120 + 200 = 320
 *
 * **개수를 박지 않는다.** MA_LINES 에 더 긴 선이 들어오면 저절로 따라온다.
 * 박아 두면 선을 하나 늘릴 때마다 이 값도 같이 고쳐야 하고, 그 순간 목록이
 * 둘이 된다.
 *
 * 2026-09-29 실측 — 카드가 180봉만 받아서 **200일선이 어느 종목에서도
 * 안 그려지고 있었다**(candles.length < 200 이면 series: null). 모달은
 * 300봉이라 그려지긴 했지만 보이는 구간 앞 20봉이 비어 있었다.
 * 재권님 지시 — 「5분본부터 200일선까지 안그려진 거 다 그려」.
 *
 * DB 를 재보니 112종목 중 101종목이 이미 320봉 이상 갖고 있었다. 모자란
 * 종목은 범례가 「MA200 봉 부족」 으로 적는다 — 그것은 그대로 둔다.
 *
 * **KIS 호출은 안 늘어난다.** 서버의 read_candles 가 DB 를 읽을 때만 쓰는
 * 값이고, 분봉을 KIS 에서 받는 횟수는 limit 과 무관하다(kis_proxy.py 의
 * get_chart — 하루치 또는 최근 구간, 둘 중 하나다).
 */
const IND_WARMUP = [
  ...MA_LINES.map(([p]) => p),                            // 이동평균 — 지금은 200 이 가장 길다
  IND_PERIOD.macdSlow + IND_PERIOD.macdSig - 1,           // MACD 신호선
  IND_PERIOD.bb, IND_PERIOD.rsi, IND_PERIOD.vol,
  IND_PERIOD.ichC + IND_PERIOD.ichB,                      // 일목 선행스팬2 (뒤로 b 만큼 민다)
];

export const BARS_FOR_IND = VISIBLE_BARS + Math.max(...IND_WARMUP);

/* 기간마다 **받아올** 봉 수. 처음 보이는 개수(`initBars`)와 다른 값이다.
 *
 * **한 곳에만 둔다** — 2026-09-30 지시 「모달과 카드는 봉수가 다르면 안돼
 * 정보는 같아야돼」. 그 전에는 카드(`home.js` 의 `BIG_LIMIT`)와 모달
 * (`stock-view.js`)이 **각자 값을 들고 있어서 일봉만 400 ↔ 320 으로 갈렸다.**
 * 같은 종목·같은 기간인데 두 화면이 다른 개수를 받았다.
 *
 * 그래서 `fetchCandles` 가 **개수를 인자로 받지 않는다.** 부르는 쪽이 줄 수
 * 없으면 갈릴 자리가 없다 — 「같은 값은 한 곳에만 둔다」. 400 으로 맞추는
 * 것만으로는 **예외를 둘 수 있는 자리가 양쪽에 그대로 남는다.**
 *
 * 기본은 `BARS_FOR_IND`(선이 끊기지 않는 최소)이고 여기 적은 기간만 예외다.
 *
 *   일봉 400   **이 값이 보관량을 정한다.** 서버가 `limit` 까지 과거를 거슬러
 *              받으므로(`kis_proxy.py` 의 `fetch_bars_back`), 320 으로 내리면
 *              앞으로 모든 종목이 320 에서 멈춘다. 2026-09-30 실측 —
 *              삼성전자만 401봉이고 나머지 관심종목은 107~108봉이다
 *
 * **년봉은 200일선이 안 그려진다.** 46봉(1985-12~)뿐이라 200봉을 못 채운다 —
 * 그 칸은 범례가 「MA200 봉 부족」 으로 적는다. **고칠 수 있는 것이 아니다.**
 */
const FETCH_BARS = { '1d': 400 };

export function barsToFetch(periodId) {
  return FETCH_BARS[periodId] || BARS_FOR_IND;
}

function showLastBars(chart, total, bars = VISIBLE_BARS) {
  const ts = chart.timeScale();
  try {
    /* from 이 음수여도 된다. 그만큼 왼쪽이 빈다 */
    ts.setVisibleLogicalRange({ from: total - bars, to: total - 1 });
  } catch {
    ts.fitContent();          // 라이브러리 판이 다르면 예전대로
  }
}


/* ── 기간 선택을 페이지 너머로 들고 간다 (2026-09-29 지시) ──────────
 *
 * 재권님 말씀 — 「종목의 5분봉을 보다 다른종목으로 가면 5분봉 / 일봉을 보다가
 * 다른종목으로 가면 일봉」.
 *
 * **첫 화면에서 종목 화면으로 갈 때 페이지가 새로 뜬다**
 * (`home.js` 의 `location.href = './stock.html?code=…'`). 그래서 화면 안
 * 변수로는 못 지킨다.
 *
 * **`sessionStorage` 를 고른 이유** — 두 요건을 다 만족하는 것이 이것뿐이다.
 *
 *     페이지 이동에 남나    `sessionStorage` **남는다** · `localStorage` 남는다
 *     탭을 닫으면          `sessionStorage` **사라진다** · `localStorage` 남는다
 *
 * 재권님이 「창을 닫았다 열면 안 남아도 된다」 고 하셨다. 둘 다 앞 요건을
 * 만족하는데 뒤엣것까지 맞는 쪽을 골랐다. **2026-09-29 에 실제로 옮겨 보고
 * 확인했다** — `location.href` 로 옮긴 뒤에도 값이 그대로 읽혔다.
 *
 * **보이는 위치·확대는 여기 저장하지 않는다.** 그것은 종목이 바뀌면 버리는
 * 값이라, 저장하면 「종목을 바꾸면 초기값」 이 깨진다. */
const PERIOD_KEY = 'kh-chart-period';

export function savePeriodId(id) {
  try { sessionStorage.setItem(PERIOD_KEY, id); } catch { /* 사생활 모드 등 */ }
}

export function loadPeriodId(fallback) {
  try { return sessionStorage.getItem(PERIOD_KEY) || fallback; } catch { return fallback; }
}


/* ── 카드와 모달이 **같은 것을 본다** (2026-09-29 지시) ──────────────
 *
 * 재권님 말씀 — 「차트 분봉 일봉 월봉 년봉 적용된게 모달열면 모달에 동기화
 * 되야해」 · 「캔들갯수등도 조절하면 모델에 그대로 적용되야해」.
 *
 * **모달이 값을 따로 들면 두 곳이 되어 갈린다.** 재권님이 「모달에 이값이
 * 있어야 되나?」 로 물으셨고 **「소유는 한 곳, 읽는 것은 둘」** 로 정해졌다 —
 * 「같은 값은 한 곳에만 둔다」 그대로다.
 *
 * **두 값이 저장되는 자리가 다르다.**
 *
 *     기간    페이지를 넘어야 한다      →  `sessionStorage` (위 두 함수)
 *     자리    같은 페이지 안에서만 쓰고
 *             종목이 바뀌면 버린다      →  **여기 변수**
 *
 * 카드와 모달은 같은 페이지에 있으므로 변수로 닿는다. **저장을 늘리지 않는다.** */
const _view = { code: null, byPeriod: {} };

/* 그 기간에서 보던 자리. 없으면 `undefined` — 부르는 쪽이 초기값으로 간다 */
export function chartView(periodId) { return _view.byPeriod[periodId]; }

export function setChartView(periodId, v) { _view.byPeriod[periodId] = v; }

/* 종목이 바뀌면 자리를 전부 버린다 (2026-09-29 지시 — 「종목을 바꾸면 각각이
   초기화 값으로 돌아가서 보여지고」).

   **기간은 안 버린다** — 「5분봉을 보다 다른종목으로 가면 5분봉」. 그래서
   자리만 여기서 다루고 기간은 `sessionStorage` 에 그대로 둔다. */
export function chartStockChanged(code) {
  if (_view.code !== code) { _view.code = code; _view.byPeriod = {}; }
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

/* ──────────────────────────────────────────────────────────────────────────
   보조지표 계산 (2026-09-17 지시 — "필요한 보조지표들 추가")

   전부 순수 계산이다. 봉 배열을 받아 { time, value } 목록을 돌려준다.
   값이 아직 없는 앞쪽 구간은 **넣지 않는다** — 라이브러리가 빈 값을 0 으로
   그려 선이 바닥에서 솟아오르는 것을 막기 위해서다.
   ────────────────────────────────────────────────────────────────────────── */

/* 지수이동평균 — 최근 값에 무게를 더 준다. MACD 가 쓴다. */
/* export 는 `tools/check-indicators.py` 가 node 로 불러 쓰려고 붙였다
   (2026-09-22). 서버(`server/signal_watch.py`)에 같은 계산이 파이썬으로 한 벌
   더 있어서, **같은 봉에서 같은 값이 나오는지** 대 본다. 화면과 알림이 갈리면
   「화면엔 신호가 보이는데 알림은 안 온다」 가 된다.

   이름이 `signal_watch` 인 이유 — **`signal` 은 파이썬 기본 모듈 이름**이라
   `server/signal.py` 로 두면 그 폴더에서 돌리는 것이 죄다 기본 `signal` 대신
   이 파일을 집는다. 겉으로는 엉뚱한 자리의 `AttributeError` 로만 보여서
   찾기 어렵다. 짧아 보여도 되돌리면 안 된다. */
export function ema(values, period) {
  const k = 2 / (period + 1);
  const out = new Array(values.length).fill(null);
  let acc = 0;
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) { acc += values[i]; continue; }
    if (i === period - 1) { acc += values[i]; out[i] = acc / period; continue; }
    out[i] = values[i] * k + out[i - 1] * (1 - k);
  }
  return out;
}

/* 볼린저 밴드 — 20일 이동평균에서 표준편차 두 배만큼 떨어진 위아래 선.
   값이 이 띠를 벗어나면 평소 범위 밖이라는 뜻이다.
   **가운데 선은 안 그린다.** 20일 이동평균과 같은 값이라 MA20 이 이미 그리고 있다. */
export function bollinger(candles, barPeriod, period = IND_PERIOD.bb, mult = 2) {
  const up = [], lo = [];
  const vUp = new Array(candles.length).fill(null);
  const vLo = new Array(candles.length).fill(null);
  for (let i = period - 1; i < candles.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += candles[j].close;
    const mean = sum / period;
    let sq = 0;
    for (let j = i - period + 1; j <= i; j++) sq += (candles[j].close - mean) ** 2;
    const sd = Math.sqrt(sq / period);
    const t = toChartTime(candles[i].ts, barPeriod);
    vUp[i] = mean + sd * mult;
    vLo[i] = mean - sd * mult;
    up.push({ time: t, value: vUp[i] });
    lo.push({ time: t, value: vLo[i] });
  }
  return { up, lo, vUp, vLo, period };
}

/* RSI — 오른 폭과 내린 폭의 비를 0~100 으로 (Wilder 방식).
   70 위면 많이 샀다, 30 아래면 많이 팔았다고 본다. */
export function rsi(candles, barPeriod, period = IND_PERIOD.rsi) {
  const out = [];
  const vals = new Array(candles.length).fill(null);
  if (candles.length <= period) return { data: out, values: vals, period };

  let gain = 0, loss = 0;
  for (let i = 1; i <= period; i++) {
    const d = candles[i].close - candles[i - 1].close;
    if (d >= 0) gain += d; else loss -= d;
  }
  gain /= period; loss /= period;

  const put = (i) => {
    const v = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
    vals[i] = v;
    out.push({ time: toChartTime(candles[i].ts, barPeriod), value: v });
  };
  put(period);

  for (let i = period + 1; i < candles.length; i++) {
    const d = candles[i].close - candles[i - 1].close;
    gain = (gain * (period - 1) + (d > 0 ? d : 0)) / period;
    loss = (loss * (period - 1) + (d < 0 ? -d : 0)) / period;
    put(i);
  }
  return { data: out, values: vals, period };
}

/* MACD — 12일선과 26일선의 차이(macd), 그것의 9일 지수이동평균(signal),
   그리고 둘의 차이(hist). hist 가 0 을 넘나드는 자리가 추세가 바뀌는 자리다. */
export function macd(candles, barPeriod, fast = IND_PERIOD.macdFast,
                     slow = IND_PERIOD.macdSlow, sig = IND_PERIOD.macdSig) {
  const close = candles.map((c) => c.close);
  const eF = ema(close, fast);
  const eS = ema(close, slow);

  const diff = close.map((_, i) =>
    (eF[i] == null || eS[i] == null) ? null : eF[i] - eS[i]);

  /* 신호선은 diff 가 생긴 뒤부터 센다 */
  const start = diff.findIndex((v) => v != null);
  const sigRaw = start < 0 ? [] : ema(diff.slice(start).map((v) => v), sig);
  const signal = new Array(candles.length).fill(null);
  sigRaw.forEach((v, i) => { if (v != null) signal[start + i] = v; });

  const line = [], sgn = [], hist = [];
  const vHist = new Array(candles.length).fill(null);
  for (let i = 0; i < candles.length; i++) {
    const t = toChartTime(candles[i].ts, barPeriod);
    if (diff[i] != null) line.push({ time: t, value: diff[i] });
    if (signal[i] != null) sgn.push({ time: t, value: signal[i] });
    if (diff[i] != null && signal[i] != null) {
      const h = diff[i] - signal[i];
      vHist[i] = h;
      hist.push({
        time: t, value: h,
        color: h >= 0 ? alpha('up', 0.55) : alpha('down', 0.55),
      });
    }
  }
  return { line, signal: sgn, hist, vLine: diff, vSignal: signal, vHist };
}

/* 일목균형표 — 다섯 선으로 지지·저항을 본다.
 *
 *   전환선   최근 9봉의 (최고+최저)/2
 *   기준선   최근 26봉의 (최고+최저)/2
 *   선행1    (전환+기준)/2 를 26봉 **앞으로** 민 것
 *   선행2    최근 52봉의 (최고+최저)/2 를 26봉 앞으로 민 것
 *   후행     종가를 26봉 **뒤로** 민 것
 *
 * **구름(선행1과 선행2 사이 색칠)은 안 그린다.** 두 선 사이를 채우려면
 * 라이브러리에 없는 기능이라 따로 만들어야 한다. 선 둘로 경계만 보여준다.
 * 선행선은 봉보다 앞을 가리키므로, 라이브러리가 모르는 시각이 되지 않도록
 * **있는 봉 범위 안에서만** 그린다.
 */
function ichimoku(candles, barPeriod, a = IND_PERIOD.ichA,
                  b = IND_PERIOD.ichB, c = IND_PERIOD.ichC) {
  const hl = (from, to) => {
    let hi = -Infinity, lo = Infinity;
    for (let i = from; i <= to; i++) {
      if (candles[i].high > hi) hi = candles[i].high;
      if (candles[i].low < lo) lo = candles[i].low;
    }
    return (hi + lo) / 2;
  };

  const conv = [], base = [], sp1 = [], sp2 = [], lag = [];
  const vConv = new Array(candles.length).fill(null);
  const vBase = new Array(candles.length).fill(null);

  for (let i = 0; i < candles.length; i++) {
    const t = toChartTime(candles[i].ts, barPeriod);
    if (i >= a - 1) { vConv[i] = hl(i - a + 1, i); conv.push({ time: t, value: vConv[i] }); }
    if (i >= b - 1) { vBase[i] = hl(i - b + 1, i); base.push({ time: t, value: vBase[i] }); }

    /* 앞으로 민 선 — i 번째 값이 i+b 자리에 놓인다. 봉이 있는 데까지만 */
    const fwd = i + b;
    if (fwd < candles.length) {
      const ft = toChartTime(candles[fwd].ts, barPeriod);
      if (vConv[i] != null && vBase[i] != null) {
        sp1.push({ time: ft, value: (vConv[i] + vBase[i]) / 2 });
      }
      if (i >= c - 1) sp2.push({ time: ft, value: hl(i - c + 1, i) });
    }

    /* 뒤로 민 선 — 지금 종가를 26봉 전 자리에 놓는다 */
    const bwd = i - b;
    if (bwd >= 0) {
      lag.push({ time: toChartTime(candles[bwd].ts, barPeriod), value: candles[i].close });
    }
  }
  return { conv, base, sp1, sp2, lag, vConv, vBase, a, b, c };
}

/* 거래량 이동평균 — 오늘 거래가 평소보다 많은지 본다 */
function volumeMA(candles, barPeriod, period = IND_PERIOD.vol) {
  const out = [];
  const vals = new Array(candles.length).fill(null);
  let sum = 0;
  for (let i = 0; i < candles.length; i++) {
    sum += candles[i].volume || 0;
    if (i >= period) sum -= candles[i - period].volume || 0;
    if (i >= period - 1) {
      vals[i] = sum / period;
      out.push({ time: toChartTime(candles[i].ts, barPeriod), value: vals[i] });
    }
  }
  return { data: out, values: vals, period };
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

/* 서버에서 캔들 가져오기. periodId 는 화면 버튼 값('1d','5m' 등)
 *
 * **몇 개 받을지는 부르는 쪽이 정하지 않는다** — 위 `barsToFetch` 한 곳이
 * 정한다. 전에는 인자였는데 두 화면이 서로 다른 값을 주어 일봉이 갈렸다.
 * 240 이었던 기본값도 240-120=120 이라 200일선이 앞 79봉 비어 있었다
 * (2026-09-29). **줄 수 있게 두면 언젠가 다시 갈린다.** */
export async function fetchCandles(code, periodId = '1d', opt = {}) {
  const period = PERIOD_MAP[periodId] || 'D';
  const limit = barsToFetch(periodId);
  const key = `${code}:${period}:${limit}`;

  /* `fresh` 면 캐시를 건너뛴다 (2026-09-30 지시 — 「5번」).
   *
   * **개수 인자를 없앤 것과 다른 이야기다.** 개수는 **양쪽이 같아야 하는 값**
   * 이라 줄 수 없게 했고(위 `barsToFetch`), 이것은 **부르는 상황**이다 —
   * 「지금 당장 새로 받아야 하는 자리인가」. 값이 갈릴 여지가 없다.
   *
   * 쓰는 곳은 **모달을 닫을 때 하나**다. 모달을 보는 동안 카드 차트는
   * 안 그려지는데, 닫고 나서 캐시(60초)에 걸리면 **최대 1분 옛 그림**이
   * 남는다. 닫는 순간에 한 번이라 **총량은 거의 안 는다.** */
  if (!opt.fresh) {
    const hit = _candleCache.get(key);
    if (hit && Date.now() - hit.at < CANDLE_TTL_MS) return hit.value;
  }

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
/* 오른쪽 가격축 폭. **모든 칸이 같은 값을 쓴다.**
 *
 * 칸마다 차트를 따로 만들기 때문에, 축 폭을 라이브러리에 맡기면 값의 글자 수를
 * 따라 저절로 갈린다 — 가격은 「1,402,000」 열 자, RSI 는 「49.82」 다섯 자다.
 * 그러면 그림이 시작하고 끝나는 자리가 칸마다 달라져 봉과 지표가 세로로 안 맞는다.
 * 못 박아 두고, 아래 checkAlign 이 어긋나면 화면에 표시한다.
 * (holdings/CLAUDE.md 「차트 칸의 좌우 끝은 반드시 맞는다」) */
const AXIS_W = 76;

/* 아래 칸 기본 높이와 최소값. 끌어서 바꾼 값은 브라우저에 남는다 */
/* 바깥(보조지표 메뉴)이 켜고 끌 때 쓴다. 켠 목록은 여기 한 곳에만 둔다 —
   그래야 첫 화면·종목 화면·모달이 같은 상태를 본다. */
export function toggleIndicator(key) {
  const on = indOn();
  if (on.has(key)) on.delete(key); else on.add(key);
  saveIndOn();
  _indSync.forEach((fn) => fn());
}

/* 켠 목록이 바뀌면 알려준다 (메뉴의 체크를 맞추는 데 쓴다) */
export function onIndicatorChange(fn) {
  _indSync.add(fn);
  return () => _indSync.delete(fn);
}

const PANE_H_KEY = 'kh.chart.pane-h';
const PANE_H_DEF = { vol: 110, macd: 110, rsi: 110 };

/* ── 매물대 (2026-09-18 지시) ─────────────────
 *
 * 가격을 몇 칸으로 나누고 **각 봉의 거래량을 그 봉의 고가~저가에 고르게
 * 나눠 담는다.** 그래서 **칸 합계 = 기간 전체 거래량**이 반드시 맞는다 —
 * 1주라도 어긋나면 버그다. 눈으로 볼 필요 없이 검사로 잡을 수 있는 자리다
 * (2026-09-18 실측, 삼성전자 일봉 105개로 차이 0).
 *
 * 새 호출이 없다. 화면이 이미 갖고 있는 봉으로 계산한다.
 */
const VP_BINS = 20;              // 가격을 몇 칸으로 나눌지
/* 가장 긴 막대가 그림 영역 오른쪽 끝에 거의 닿는다 (2026-09-18 지시 —
   "가장 긴게 차트 화면 오른쪽 거의 끝에맞춰져서 정렬"). 1.0 이면 딱 닿아서
   가격축 선과 붙어 보이므로 조금 남긴다. */
const VP_WIDE = 0.97;
/* ── 막대 색 (2026-09-18 지시) ──
 *
 * "가장 많은건 빨간색 가장 적은건 파란색 이고 이두색 사이로 나머지 매물대들
 * 조절해서 넣어줘."
 *
 * 상승 빨강 · 하락 파랑과 **같은 두 색**을 쓴다(`--kh-up` · `--kh-down`).
 * 색을 직접 박지 않고 theme.css 의 rgb 토큰을 읽어 섞는다 — 테마를 바꾸면
 * 이것도 따라 바뀐다.
 *
 * 배경이라 옅게 깐다. 짙으면 봉이 안 보인다. */
const VP_ALPHA = 0.16;

/* 칸 높이가 이보다 크면 퍼센트를 적는다. 글씨가 0.66rem 이라 이만큼이면 들어간다 */
const VP_LABEL_MIN_H = 11;

/* **자리가 좁아도 이 비중을 넘으면 적는다** (2026-09-18 지시 — "글씨보다
   작아도 10%가 넘으면표기"). 두꺼운 칸은 봐야 하는 값이라, 글씨가 칸보다
   조금 커서 넘치더라도 적는 편이 낫다. */
const VP_LABEL_MIN_PCT = 10;

function vpColor(t) {                      // t: 0 = 가장 적음(파랑) ~ 1 = 가장 많음(빨강)
  const rgb = (name) => {
    const m = alpha(name, 1).match(/rgba?\(([^)]+)\)/);
    const [r, g, b] = (m ? m[1] : '0,0,0').split(/[\s,]+/).map(Number);
    return [r, g, b];
  };
  const lo = rgb('down');
  const hi = rgb('up');
  const k = Math.max(0, Math.min(1, t));
  const mix = lo.map((v, i) => Math.round(v + (hi[i] - v) * k));
  return `rgba(${mix[0]},${mix[1]},${mix[2]},${VP_ALPHA})`;
}
const VP_REFRESH_MS = 2000;      // 다시 그리는 주기 (지시)

/* ── 겹쳐 그리는 것은 세로 축 계산에서 뺀다 ──
 *
 * 볼린저에만 넣어 두었더니 **MA60 을 껐다 켜면 차트 크기가 바뀌었다**
 * (2026-09-18 지적 — "일괄로 값빼서 적용이 안된거 같은데"). 이동평균선이
 * 봉보다 위아래로 넓으면 켜는 순간 값 축이 그만큼 벌어져 봉이 작아진다.
 *
 * **한 곳에 두고 겹치는 것 전부가 가져다 쓴다.** 새 겹침을 더할 때도
 * 이것을 펴 넣으면 된다. */
const NO_SCALE = { autoscaleInfoProvider: () => null };

function volumeProfile(candles, bins = VP_BINS) {
  const rows = (candles || []).filter((c) =>
    Number.isFinite(c.high) && Number.isFinite(c.low));
  if (rows.length < 2) return null;

  const lo = Math.min(...rows.map((c) => c.low));
  const hi = Math.max(...rows.map((c) => c.high));
  if (!(hi > lo)) return null;
  const step = (hi - lo) / bins;

  const acc = new Array(bins).fill(0);
  let total = 0;
  for (const c of rows) {
    const v = Number(c.volume);
    if (!Number.isFinite(v) || v <= 0) continue;   // 거래량이 없는 봉은 건너뛴다
    const a = Math.max(0, Math.min(bins - 1, Math.floor((c.low - lo) / step)));
    const b = Math.max(0, Math.min(bins - 1, Math.floor((c.high - lo) / step)));
    const share = v / (b - a + 1);
    for (let i = a; i <= b; i++) acc[i] += share;
    total += v;
  }
  if (!total) return null;

  const max = Math.max(...acc);
  const min = Math.min(...acc);
  return {
    total, max, min,
    span: max - min,          // 색을 섞는 데 쓴다. 0 이면 전부 같은 값이다
    bins: acc.map((vol, i) => ({
      lo: lo + step * i, hi: lo + step * (i + 1),
      vol, pct: vol / total * 100,
    })),
  };
}
const PANE_MIN = 60, PRICE_MIN = 120;

let _paneH = null;
function paneH() {
  if (_paneH) return _paneH;
  _paneH = { ...PANE_H_DEF };
  try {
    const v = JSON.parse(localStorage.getItem(PANE_H_KEY) || '{}');
    Object.keys(_paneH).forEach((k) => {
      if (Number.isFinite(v[k]) && v[k] >= PANE_MIN) _paneH[k] = v[k];
    });
  } catch { /* 없으면 기본값 */ }
  return _paneH;
}
function savePaneH() {
  try { localStorage.setItem(PANE_H_KEY, JSON.stringify(_paneH)); } catch { /* 저장 못 씀 */ }
}

/* 제 칸을 갖는 지표. 순서가 곧 위에서 아래 순서다 */
const OWN_PANES = [
  { key: 'vol',  label: '거래량', par: '20' },
  { key: 'macd', label: 'MACD',  par: '12, 26, 9' },
  { key: 'rsi',  label: 'RSI',   par: '14' },
];

export function createStockChart(container, candles, opts = {}) {
  /* candles 는 setData 로 바뀐다 (인자를 그대로 쓰지 않는다) */
  const LC = window.LightweightCharts;
  if (!LC) throw new Error('차트 라이브러리를 불러오지 못했습니다');
  if (!candles || !candles.length) throw new Error('표시할 데이터가 없습니다');

  const showVolume = opts.showVolume !== false;
  const showMA = opts.showMA !== false;
  const showLegend = opts.showLegend !== false;
  let period = opts.period || 'D';

  container.classList.add('kh-panes');

  let panes = [];
  let maSeries = [];
  let candleSeries = null;
  let vpLayer = null;          // 매물대가 깔리는 층 (가격 칸 뒤)
  let vpTimer = null;
  let legend = null;
  const priceLines = [];
  let syncing = false;

  function mkChart(box, h, axis) {
    return LC.createChart(box, {
      width: box.clientWidth || container.clientWidth, height: h,
      layout: {
        background: { color: 'transparent' }, textColor: COLOR.text,
        fontFamily: "'Noto Sans KR', system-ui, sans-serif", fontSize: 11,
        /* 차트 왼쪽 아래에 라이브러리가 제 로고(TradingView)를 그린다.
           칸마다 하나씩 생겨 네 칸이면 넷이다 — 봉·거래량·MACD·RSI 위에
           겹쳐 보인다 (2026-09-21 지시 — "차트에서 어디서 가져와서 표기하는
           문양 같은거 없애줘"). 라이브러리가 공식으로 주는 옵션이다. */
        attributionLogo: false,
      },
      grid: { vertLines: { color: COLOR.grid }, horzLines: { color: COLOR.grid } },
      rightPriceScale: {
        borderColor: COLOR.border,
        scaleMargins: { top: showLegend ? 0.16 : 0.08, bottom: 0.08 },
        minimumWidth: AXIS_W,            // 좌우 끝을 맞추는 핵심. 위 주석 참고
      },
      timeScale: {
        borderColor: COLOR.border, rightOffset: 4, fixLeftEdge: false,
        timeVisible: MINUTE_PERIODS.has(period), secondsVisible: false,
        visible: axis,
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
    });
  }

  const addLine = (ch, o) => ch.addSeries(LC.LineSeries, {
    lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
    crosshairMarkerVisible: false, ...o,
  });

  /* 값이 없는 앞 구간을 **빈 자리(time 만)** 로 채운다.
     걸러 내면 칸마다 봉 개수가 달라지고, 시간축을 맞출 때 쓰는 「몇 번째 봉」이
     어긋나 오른쪽이 잘린다 — MACD 가 앞 25봉이 없어 그랬다 (2026-09-18). */
  const put = (vals) => vals.map((v, i) =>
    v == null ? { time: toChartTime(candles[i].ts, period) }
              : { time: toChartTime(candles[i].ts, period), value: v });

  /* 가격 칸 위에 얹히는 지표(볼린저·이동평균)를 따로 들고 있는다.
     칸 구성이 안 바뀌는데 통째로 다시 만들면 화면이 깜빡인다 (2026-09-18 지시). */
  let overlay = [];

  /* 겹침 시리즈와 maSeries 는 한 몸이다. 여기서만 비운다 */
  function dropOverlay(ch) {
    overlay.forEach((sr) => { try { ch.removeSeries(sr); } catch { /* 이미 없음 */ } });
    overlay = [];
    maSeries = [];
  }

  /* **봉과 겹침을 따로 만든다 (2026-09-18).**
     한 함수가 둘을 같이 만들면, 겹침만 바꾸려 할 때 봉이 딸려 온다.
     전에는 「새로 만든 봉을 지우고 옛 것을 되돌리는」 우회를 썼는데,
     그 사이 캔들 시리즈가 잠깐 둘이 되어 **세로 축이 두 번 흔들렸다.**
     볼린저를 켤 때마다 봉이 커졌다 작아진 것이 이 때문이다. */
  /* ── 매물대 그리기 (2026-09-18 지시) ──
   *
   * 퍼센트를 **왼쪽**에 적는다. 오른쪽에 두면 가격축이 밀려 아래 보조지표
   * 칸과 좌우 끝이 어긋난다 — holdings/CLAUDE.md 의 「차트 칸의 좌우 끝은
   * 반드시 맞는다」 와 부딪히는 자리다. 왼쪽은 그림 영역 안이라 축을
   * 건드리지 않는다.
   */
  function drawProfile() {
    if (!vpLayer) return;
    if (!indOn().has('vp') || !candleSeries) { vpLayer.innerHTML = ''; return; }

    const prof = volumeProfile(candles);
    if (!prof) { vpLayer.innerHTML = ''; return; }

    const w = Math.max(0, vpLayer.clientWidth - AXIS_W);   // 가격축 자리는 비운다
    const last = candles[candles.length - 1];
    const now = last ? last.close : null;
    const out = [];

    for (const b of prof.bins) {
      let yTop, yBot;
      try {
        yTop = candleSeries.priceToCoordinate(b.hi);
        yBot = candleSeries.priceToCoordinate(b.lo);
      } catch { return; }                    // 아직 그릴 준비가 안 됐다
      if (yTop == null || yBot == null) continue;

      const h = Math.max(1, yBot - yTop - 1);
      const bw = prof.max ? b.vol / prof.max * w * VP_WIDE : 0;
      const here = now != null && now >= b.lo && now < b.hi;
      /* 가장 많은 칸이 빨강, 가장 적은 칸이 파랑. 사이는 섞는다 */
      const t = prof.span ? (b.vol - prof.min) / prof.span : 1;

      out.push(`<div class="kh-vp-b${here ? ' is-now' : ''}" style="top:${yTop}px;` +
               `height:${h}px;width:${bw}px;background:${vpColor(t)}"></div>`);
      /* **글씨는 자리가 있으면 적는다.** 전에는 「3% 넘으면」 이라는 임의
         기준이라 어떤 칸은 나오고 어떤 칸은 안 나왔다 (2026-09-18 지적).
         칸 높이가 글씨보다 크면 적고, 좁으면 건너뛴다 — 기간을 바꿔 봉이
         촘촘해져도 같은 규칙으로 간다. */
      if (h >= VP_LABEL_MIN_H || b.pct >= VP_LABEL_MIN_PCT) {
        out.push(`<div class="kh-vp-t${here ? ' is-now' : ''}" ` +
                 `style="top:${yTop + h / 2}px">${b.pct.toFixed(1)}%</div>`);
      }
    }
    vpLayer.innerHTML = out.join('');
  }

  /* ── 미래 영역 — 아직 안 온 봉 자리를 옅은 파랑으로 깐다 (2026-09-29 지시) ──
   *
   * 재권님 말씀 — 「**미래에 아직 안나온 값은 파란색으로**」.
   *
   * **오른쪽은 늘 비어 있다.** 위 mkChart 의 `rightOffset: 4` 라 마지막 봉
   * 오른쪽에 4봉만큼 자리가 남고, 끌거나 줄이면 더 넓어진다. 거기가 「아직
   * 안 온」 자리다 — 없는 자리를 새로 만드는 것이 아니다.
   *
   * **칸마다 깐다.** 가격 칸만 칠하면 아래 거래량·MACD·RSI 에서 띠가 끊겨
   * 보인다. 그 칸들도 미래에는 값이 없으므로 같이 칠하는 것이 맞다.
   *
   * **매물대와 같은 층 방식이다** — 차트 canvas **뒤**에 DOM 을 깔고,
   * `.kh-pane-box` 가 곱하기로 섞여 비쳐 보인다 (stock.css 의 그 주석 참고).
   * 위에 얹으면 봉과 축 글자가 가려진다.
   *
   * ⚠️ **왼쪽(과거쪽)은 칠하지 않는다.** 거기는 「정말 없는 것」 과 「아직 안
   * 받은 것」 이 갈리는 자리다. 받아올 수 있는데 칠하면 **「없다」 고 거짓으로
   * 알린다.** 오른쪽은 받을 방법이 없어 언제나 칠해도 맞는다 —
   * **색 이름은 하나(`--kh-nodata-rgb`)지만 판정은 둘이다.**
   */
  function drawFuture() {
    const total = candles.length;
    for (const p of panes) {
      const band = p.futB;
      if (!band) continue;
      const hide = () => { band.style.display = 'none'; };
      if (total < 2) { hide(); continue; }

      let x0;
      try {
        const ts = p.chart.timeScale();
        const xLast = ts.logicalToCoordinate(total - 1);
        const xPrev = ts.logicalToCoordinate(total - 2);
        if (xLast == null || xPrev == null) { hide(); continue; }
        x0 = xLast + (xLast - xPrev) / 2;          // 마지막 봉의 오른쪽 끝
      } catch { hide(); continue; }                // 아직 그릴 준비가 안 됐다

      /* 가격축 자리는 비운다 — 매물대와 같은 이유다(좌우 끝이 어긋난다) */
      const right = Math.max(0, p.fut.clientWidth - AXIS_W);
      if (!(x0 < right)) { hide(); continue; }     // 미래 자리가 없다

      /* 시간축이 보이는 칸(맨 아래)은 그 띠를 덮지 않는다 — 날짜 뒤가 파래진다 */
      let axisH = 0;
      try { axisH = p.chart.timeScale().height() || 0; } catch { /* 없으면 0 */ }

      band.style.display = '';
      band.style.left = Math.max(0, x0) + 'px';
      band.style.width = (right - Math.max(0, x0)) + 'px';
      band.style.bottom = axisH + 'px';
      band.style.background = COLOR.noData;
    }
  }

  /* 2초마다 다시 그린다 (지시). 차트를 끌거나 확대하면 그 자리에서 따라
     그린다 — 2초를 기다리면 봉과 어긋나 보인다. */
  function startProfileLoop() {
    if (vpTimer) clearInterval(vpTimer);
    vpTimer = setInterval(() => {
      if (document.hidden) return;           // 안 보이는 탭은 쉰다
      drawProfile();
      /* 미래 영역도 여기서 다시 잰다. **창 크기가 바뀌는 것을 잡는 자리가
         이것뿐이다** — 확대·끌기는 위 구독이 잡지만 크기 변경은 구독이 안 온다 */
      drawFuture();
    }, VP_REFRESH_MS);
  }

  /* **매물대를 켜면 그때 보이던 세로 범위를 그대로 굳힌다** (2026-09-18 지시 —
     "차트창을 움직이거나 해도 매물대는 고정이여야해").

     차트를 좌우로 끌면 보이는 봉이 달라지고 세로 축이 그때마다 다시 잡힌다.
     매물대는 가격에 붙어 있으므로 그 축을 따라 **위아래로 출렁였다**
     (실측 485 → 554px).

     ⚠️ **처음에는 전체 기간(고가~저가)으로 바꾸게 만들었는데 그것이 틀렸다.**
     켜는 순간 축이 바뀌어 화면이 조절됐다 — 「지표를 켜고 끌 때 차트 크기가
     바뀌면 안 된다」 는 룰을 정확히 어긴 것이다. 오늘 같은 자리가 세 번째였다
     (볼린저 · 이동평균 · 매물대).

     **지금 보이던 범위를 그대로 다시 먹인다.** 같은 값이라 켤 때 안 움직이고,
     그 뒤로는 그 값에 묶여 있어 끌어도 고정이다. 끄면 빈 값을 먹여 예전처럼
     보이는 구간에 맞춰 움직인다. */
  let vpRange = null;          // 매물대를 켠 순간의 세로 범위

  function priceFix() {
    if (!indOn().has('vp') || !vpRange) return { autoscaleInfoProvider: undefined };
    const { min, max } = vpRange;
    return { autoscaleInfoProvider: () => ({ priceRange: { minValue: min, maxValue: max } }) };
  }

  /* 지금 보이는 세로 범위를 재서 굳힌다. 봉이 이미 그려져 있어야 잴 수 있으므로
     그린 뒤에 부른다.

     **한 번 굳히면 끌 때도 풀지 않는다.** 풀면 자동 스케일이 돌아오면서
     그 순간 화면이 바뀐다 — 「지표를 켜고 꺼도 차트 크기가 바뀌지 않는다」
     를 끄는 쪽에서 어기게 된다 (2026-09-18 실측 420 → 484px).
     차트를 새로 그리거나 종목·기간이 바뀔 때만 다시 잡는다. */
  function lockPriceRange() {
    if (!indOn().has('vp')) return;            // 끌 때는 건드리지 않는다
    if (vpRange) return;                       // 이미 굳혀 두었다
    const box = panes[0] && panes[0].box;
    if (!candleSeries || !box) return;
    try {
      const top = candleSeries.coordinateToPrice(0);
      const bot = candleSeries.coordinateToPrice(box.clientHeight);
      if (top == null || bot == null || !(top > bot)) return;
      vpRange = { min: bot, max: top };
      candleSeries.applyOptions(priceFix());
    } catch { /* 아직 그릴 준비가 안 됐다 */ }
  }

  function drawCandle(ch) {
    candleSeries = ch.addSeries(LC.CandlestickSeries, {
      upColor: COLOR.up, downColor: COLOR.down, borderUpColor: COLOR.up,
      borderDownColor: COLOR.down, wickUpColor: COLOR.up, wickDownColor: COLOR.down,
      ...priceFix(),      // 이미 굳혀 둔 값이 있으면 그대로, 없으면 자동
    });
    candleSeries.setData(candles.map((c) => ({
      time: toChartTime(c.ts, period),
      open: c.open, high: c.high, low: c.low, close: c.close,
    })));
  }

  /* 가격 그림 위에 얹히는 것만. 봉은 건드리지 않는다.
   *
   * **채우기 전에 먼저 비운다.** 이 함수가 maSeries·overlay 를 채우는
   * 유일한 곳이므로 비우는 것도 여기가 맞다. 전에는 dropOverlay 에서만
   * 비웠는데, build() 는 그것을 안 거쳐서 **1분마다(setData) 넷씩 쌓였다.**
   * 선은 안 겹쳤지만 범례가 maSeries 를 그대로 그려서 MA 가 네 벌씩 보였다
   * (2026-09-18). */
  function drawOverlay(ch) {
    maSeries = [];
    overlay = [];
    if (indOn().has('bb')) {
      const bb = bollinger(candles, period);
      /* 밴드 안을 옅게 채운다. 라이브러리에 「두 선 사이 채우기」가 없어서,
         위 선을 아래로 채운 뒤 아래 선을 카드 색으로 덮어 띠만 남긴다.

         **세로 자동 맞춤에서 뺀다.** 띠는 봉보다 위아래로 넓어서, 안 빼면
         켜는 순간 값 축이 그만큼 벌어져 봉이 작아진다. */
      const noScale = NO_SCALE;          // 위 공통 상수. 겹침은 전부 이것을 쓴다
      const up = ch.addSeries(LC.AreaSeries, {
        lineColor: COLOR.band, lineWidth: 1,
        topColor: COLOR.bandFill, bottomColor: COLOR.bandFill,
        priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        ...noScale,
      });
      const lo = ch.addSeries(LC.AreaSeries, {
        lineColor: COLOR.band, lineWidth: 1,
        topColor: COLOR.cardBg, bottomColor: COLOR.cardBg,
        priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        ...noScale,
      });
      up.setData(put(bb.vUp));
      lo.setData(put(bb.vLo));

      /* **띠를 캔들 뒤로 보낸다** (2026-09-22 지시 — 「볼린져밴드가 차트의
         캔들을 가리게 되는 현상이 있는데 이거 수정해줘」).

         바로 위 `lo` 의 채우기가 **불투명한 카드 색**이다. 두 선 사이를
         칠하는 길이 라이브러리에 없어 그렇게 만든 것인데, 그 흰 면이
         **아래 밴드보다 아래에 있는 것을 전부 덮는다.** 그리는 차례도
         캔들이 먼저라(`drawCandle` → `drawOverlay`) 띠가 위에 온다.

         2026-09-22 실측 (8766 · 삼성전자 5분봉, 껐다 켜고 같은 자리 캡처)

             끔   왼쪽 아래 캔들 선명 · 매물대 막대가 끝까지 이어짐
             켬   **캔들이 가려짐** · **매물대 막대가 밴드 아래에서 잘림**

         **캔들만이 아니라 매물대도 잘린다.**

         고치는 길 셋 중 이것을 골랐다.

             그리는 차례를 나눈다   `drawOverlay` 를 쪼개야 하고
                                   **이동평균선까지 캔들 뒤로 갈 위험**이 남는다
             흰 덮기를 없앤다       **못 한다** — 5.2.1 에 두 선 사이 채우기가
                                   없다(`BaselineSeries` 는 기준선 하나다).
                                   없애면 위 밴드 아래가 **전부** 노래진다
             **순서만 바꾼다**      이 두 줄. 다른 겹침은 안 건드린다

         `setSeriesOrder(n)` 은 **그 칸 안에서의 앞뒤**다. 0·1 이면 맨 뒤라
         캔들·이동평균·매물대가 전부 그 위에 온다. */
      up.setSeriesOrder(0);
      lo.setSeriesOrder(1);

      overlay.push(up, lo);
    }

    if (showMA && indOn().has('ma')) {
      MA_LINES.forEach(([p, key]) => {
        const color = COLOR[key];
        if (candles.length < p) {
          maSeries.push({ period: p, key, color, series: null, values: [], short: candles.length });
          return;
        }
        const sr = addLine(ch, { color, visible: !maOff().has(p), ...NO_SCALE });
        const data = movingAverage(candles, p, period);
        sr.setData(data);
        const values = new Array(candles.length).fill(null);
        data.forEach((d, k) => { values[k + p - 1] = d.value; });
        maSeries.push({ period: p, key, color, series: sr, values });
        overlay.push(sr);
      });
    }
  }

  /* 겹침만 갈아끼운다. 봉과 칸은 그대로 둔다 */
  function redrawOverlay() {
    const ch = panes[0] && panes[0].chart;
    if (!ch) return;

    /* 켜기 직전의 세로 범위를 적어 둔다. 다 그린 뒤 견줘서 움직였으면 알린다 */
    const scaleBefore = readScale();

    /* 보던 구간을 붙잡아 둔다. 시리즈를 넣고 빼면 라이브러리가 보이는 범위를
       다시 잡는다 — 46.67~183 이 60~179 로 좁아졌다 (2026-09-18 실측).
       세로는 봉을 안 건드리니 저절로 그대로다. */
    let keep = null;
    try { keep = ch.timeScale().getVisibleLogicalRange(); } catch { /* 없으면 그대로 */ }

    dropOverlay(ch);
    drawOverlay(ch);
    /* 매물대를 켜고 끄면 세로 축 규칙이 바뀐다. 봉을 새로 만들지 않고
       옵션만 다시 먹인다 — 다시 만들면 축이 두 번 흔들린다. */
    lockPriceRange();

    if (keep) {
      const back = () => {
        try { ch.timeScale().setVisibleLogicalRange(keep); } catch { /* 이미 정리됨 */ }
      };
      back();
      requestAnimationFrame(back);   // 라이브러리가 나중에 제 계산을 밀어넣는다
    }

    drawProfile();          // 매물대도 새 축에 맞춰 다시 그린다
    drawFuture();           // 미래 영역도 (봉 자리가 바뀌었다)
    /* 라이브러리가 나중에 제 계산을 밀어넣으므로 한 박자 뒤에 잰다 */
    requestAnimationFrame(() => checkScale(scaleBefore));

    if (showLegend && legend) {
      legend.destroy();
      legend = mountLegend(panes[0].box, ch,
        { candles, period, maSeries, showVolume: false, ind: {} });
      api.legend = legend;
    }
  }

  function drawVol(ch) {
    const h = ch.addSeries(LC.HistogramSeries, {
      priceFormat: { type: 'volume' }, lastValueVisible: true, priceLineVisible: false,
    });
    /* 색을 진하게 두고 오름·내림 대비를 크게 한다 — 투명하면 한 덩어리로 보인다 */
    h.setData(candles.map((c) => ({
      time: toChartTime(c.ts, period), value: c.volume,
      color: c.close >= c.open ? COLOR.up : COLOR.down,
    })));
    const v = volumeMA(candles, period);
    addLine(ch, { color: COLOR.ma20, lineWidth: 2, lastValueVisible: true })
      .setData(put(v.values));
    return { values: v.values };
  }

  function drawMacd(ch) {
    const m = macd(candles, period);
    const peak = Math.max(...m.vHist.filter((x) => x != null).map(Math.abs), 1);
    const hs = ch.addSeries(LC.HistogramSeries, { lastValueVisible: true, priceLineVisible: false });
    /* 막대 농도로 힘을 나타낸다 — 약하면 12%, 세면 100% */
    hs.setData(m.vHist.map((v, i) => v == null
      ? { time: toChartTime(candles[i].ts, period) }
      : {
          time: toChartTime(candles[i].ts, period), value: v,
          color: (v >= 0 ? COLOR.up : COLOR.down) +
            Math.round(30 + 225 * Math.min(1, Math.abs(v) / peak)).toString(16).padStart(2, '0'),
        }));
    addLine(ch, { color: COLOR.ma20, lineWidth: 2, lastValueVisible: true }).setData(put(m.vLine));
    addLine(ch, { color: COLOR.ma5, lineWidth: 2, lastValueVisible: true }).setData(put(m.vSignal));
    return m;
  }

  function drawRsi(ch) {
    const r = rsi(candles, period);
    const flat = (v, col) => {
      const sr = ch.addSeries(LC.AreaSeries, {
        lineColor: 'transparent', topColor: col, bottomColor: col,
        priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      });
      sr.setData(candles.map((c) => ({ time: toChartTime(c.ts, period), value: v })));
    };
    flat(70, COLOR.rsiBand);        // 30~70 을 옅게
    flat(30, COLOR.cardBg);         // 아래를 카드 색으로 덮어 띠만 남긴다

    /* 70 위·30 아래로 넘어간 만큼만 색을 채운다 */
    const over = ch.addSeries(LC.BaselineSeries, {
      baseValue: { type: 'price', price: 70 },
      topFillColor1: COLOR.up + '55', topFillColor2: COLOR.up + '22',
      bottomFillColor1: 'transparent', bottomFillColor2: 'transparent',
      topLineColor: 'transparent', bottomLineColor: 'transparent',
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    });
    over.setData(put(r.values.map((v) => v == null ? null : Math.max(v, 70))));

    const under = ch.addSeries(LC.BaselineSeries, {
      baseValue: { type: 'price', price: 30 },
      topFillColor1: 'transparent', topFillColor2: 'transparent',
      bottomFillColor1: COLOR.down + '22', bottomFillColor2: COLOR.down + '55',
      topLineColor: 'transparent', bottomLineColor: 'transparent',
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    });
    under.setData(put(r.values.map((v) => v == null ? null : Math.min(v, 30))));

    const ln = addLine(ch, { color: COLOR.rsi, lineWidth: 2, lastValueVisible: true });
    ln.setData(put(r.values));

    /* 두 번째 선 — RSI 의 14봉 평균 */
    const sig = smaOf(r.values, 14);
    addLine(ch, { color: COLOR.rsiSig, lineWidth: 1, lastValueVisible: true }).setData(put(sig));

    /* 기준선 70 · 50 · 30 은 점선. 오른쪽 축에 배지는 붙이지 않는다 */
    [70, 50, 30].forEach((v) => {
      try {
        ln.createPriceLine({ price: v, color: COLOR.cross, lineWidth: 1,
          lineStyle: 2, axisLabelVisible: false, title: '' });
      } catch { /* 라이브러리 버전이 다르면 선만 생략 */ }
    });
    return { values: r.values, sig };
  }

  function build() {
    /* 보던 자리를 기억했다가 되돌린다. 지표를 켜고 끌 때마다 창이
       처음으로 돌아가면 보던 구간을 다시 찾아가야 한다 (2026-09-18 지시). */
    let keep = null;
    if (panes[0]) {
      try { keep = panes[0].chart.timeScale().getVisibleLogicalRange(); } catch { /* 없으면 기본 */ }
    }

    panes.forEach((p) => { try { p.chart.remove(); } catch { /* 이미 정리됨 */ } });
    panes = [];
    container.innerHTML = '';

    /* **세 화면이 같은 규칙으로 간다 (2026-09-18 지시).** 좁다고 칸을 빼지 않는다 —
       종목 화면에서 켠 것이 모달과 첫 화면에도 그대로 있어야 한다. */
    const own = OWN_PANES.filter((x) =>
      indOn().has(x.key) && (x.key !== 'vol' || showVolume));
    const list = [{ key: 'price' }, ...own];
    const below = own.reduce((a, x) => a + paneH()[x.key], 0);

    list.forEach((p, idx) => {
      const el = document.createElement('div');
      el.className = 'kh-pane';
      const box = document.createElement('div');
      box.className = 'kh-pane-box';
      /* 매물대 층을 **차트보다 먼저** 넣는다. 배경처럼 가장 아래에 깔리고
         봉과 보조지표는 차트 canvas 안이라 저절로 그 위에 온다
         (2026-09-18 지시 — "배경처럼 가장 먼저그려지고 그위에 봉 나오고"). */
      if (p.key === 'price') {
        vpLayer = document.createElement('div');
        vpLayer.className = 'kh-vp';
        el.appendChild(vpLayer);
      }
      /* 미래 영역도 배경이라 차트보다 먼저 넣는다. **칸마다** 하나씩이다 —
         가격 칸만 두면 아래 칸에서 띠가 끊겨 보인다 (drawFuture 주석 참고) */
      const fut = document.createElement('div');
      fut.className = 'kh-fut';
      const futB = document.createElement('div');
      futB.className = 'kh-fut-b';
      futB.style.display = 'none';        // 자리를 잴 수 있을 때 drawFuture 가 켠다
      fut.appendChild(futB);
      el.appendChild(fut);
      el.appendChild(box);
      container.appendChild(el);

      const h = p.key === 'price'
        ? Math.max(PRICE_MIN, container.clientHeight - below)
        : paneH()[p.key];
      box.style.height = h + 'px';

      const ch = mkChart(box, h, idx === list.length - 1);
      const item = { key: p.key, el, box, chart: ch, fut, futB };
      panes.push(item);

      if (p.key === 'price') { drawCandle(ch); drawOverlay(ch); }
      if (p.key === 'vol')   item.calc = drawVol(ch);
      if (p.key === 'macd')  item.calc = drawMacd(ch);
      if (p.key === 'rsi')   item.calc = drawRsi(ch);

      /* 아래 칸에는 이름표와 닫기, 위쪽 경계에는 끌개 */
      if (p.key !== 'price') {
        const def = OWN_PANES.find((x) => x.key === p.key);
        const tag = document.createElement('div');
        tag.className = 'kh-pane-tag';
        tag.innerHTML =
          '<span class="x" data-pane-close="' + p.key + '" title="닫기">✕</span>' +
          '<span class="nm" data-doc="' + p.key + '">' + def.label + ' (' + def.par + ')</span>' +
          '<span class="v" data-pane-v="' + p.key + '"></span>';
        el.appendChild(tag);

        const grip = document.createElement('div');
        grip.className = 'kh-grip';
        grip.dataset.pane = p.key;
        el.appendChild(grip);
      }

      if (keep) {
        try { ch.timeScale().setVisibleLogicalRange(keep); } catch { showLastBars(ch, candles.length); }
      } else {
        showLastBars(ch, candles.length);
      }
      ch.timeScale().subscribeVisibleLogicalRangeChange((r) => {
        if (syncing || !r) return;
        syncing = true;
        panes.forEach((o) => {
          if (o.chart !== ch) {
            try { o.chart.timeScale().setVisibleLogicalRange(r); } catch { /* 아직 없음 */ }
          }
        });
        syncing = false;
        /* 봉이 움직이면 매물대도 그 자리에서 따라간다. 2초를 기다리면
           띠와 봉이 어긋나 보인다 (2026-09-18). */
        drawProfile();
        /* 미래 영역은 **봉의 자리로 왼쪽 끝을 잡으므로** 확대·끌기마다
           다시 잰다. 안 하면 봉만 움직이고 파란 자리가 남는다 */
        drawFuture();
      });

      ch.subscribeCrosshairMove((param) => {
        const i = (param && param.time != null && param.point)
          ? byTime.get(timeKey(param.time)) : null;
        paintPaneTags(i == null ? candles.length - 1 : i);
      });
    });

    if (showLegend) {
      if (legend) legend.destroy();
      legend = mountLegend(panes[0].box, panes[0].chart,
        { candles, period, maSeries, showVolume: false, ind: {} });
      api.legend = legend;
    }
    curOwn = ownKeys();
    paintPaneTags(candles.length - 1);
    /* 매물대는 배경이라 칸이 다 그려진 뒤에 얹는다. 자리를 잡으려면
       가격축이 정해져 있어야 해서 한 박자 뒤에 한 번 더 그린다. */
    /* 봉이 자리를 잡은 뒤에 세로 범위를 굳힌다. 그려지기 전에 재면 값이 없다 */
    lockPriceRange();
    drawProfile();
    drawFuture();
    requestAnimationFrame(() => { lockPriceRange(); drawProfile(); drawFuture(); });
    startProfileLoop();
    checkAlign();
  }

  /* 칸의 현재값. 마우스로 짚으면 그 봉, 아니면 마지막 봉 */
  function paintPaneTags(i) {
    panes.forEach((p) => {
      const n = p.el && p.el.querySelector('[data-pane-v="' + p.key + '"]');
      if (!n || !p.calc) return;
      if (p.key === 'vol') n.textContent = fmtVol(p.calc.values[i]);
      if (p.key === 'macd') {
        const one = (v, col) => '<span style="color:' + col + '">' +
          (v == null ? '—' : Math.round(v).toLocaleString('ko-KR')) + '</span>';
        n.innerHTML = [
          one(p.calc.vLine[i], COLOR.ma20),
          one(p.calc.vSignal[i], COLOR.ma5),
          one(p.calc.vHist[i], p.calc.vHist[i] >= 0 ? COLOR.up : COLOR.down),
        ].join('<span class="kh-mut" style="margin:0 3px">·</span>');
      }
      if (p.key === 'rsi') {
        const f = (v, col) => '<span style="color:' + col + '">' +
          (v == null ? '—' : v.toFixed(2)) + '</span>';
        n.innerHTML = f(p.calc.values[i], COLOR.rsi) +
          '<span class="kh-mut" style="margin:0 3px">·</span>' +
          f(p.calc.sig[i], COLOR.rsiSig);
      }
    });
  }

  /* 좌우 끝이 맞는지 본다. 어긋나면 화면에 표시한다 —
     「맞춰 둔다」 는 주석은 지켜지지 않는다 (holdings/CLAUDE.md). */
  /* ── 세로가 움직였는지 검사한다 (2026-09-18 지시) ──
   *
   * holdings/CLAUDE.md 「지표를 켜고 꺼도 차트 크기가 바뀌지 않는다」 를
   * 기계가 잡게 한다. 그 룰은 **코드 주석에만 있고 검사가 없어서** 하루에
   * 세 번 깨졌다 — 볼린저 · 이동평균 · 매물대. 셋 다 새 지표를 붙이면서 났다.
   *
   * 좌우 끝(checkAlign)과 짝이다. 그것은 가로, 이것은 세로다.
   */
  function readScale() {
    const box = panes[0] && panes[0].box;
    if (!candleSeries || !box || !box.clientHeight) return null;
    try {
      const top = candleSeries.coordinateToPrice(0);
      const bot = candleSeries.coordinateToPrice(box.clientHeight);
      if (top == null || bot == null || !(top > bot)) return null;
      return { top, bot };
    } catch { return null; }
  }

  /* 켜기 직전과 켠 뒤가 다르면 알린다. 값이 조금씩 흔들리는 것은 넘어가고
     **눈에 보일 만큼**(범위의 1%) 달라졌을 때만 잡는다. */
  const SCALE_TOL = 0.01;

  function checkScale(before) {
    const old = container.querySelector('.kh-scale-warn');
    if (old) old.remove();
    if (!before) return;
    const now = readScale();
    if (!now) return;

    const span = Math.abs(before.top - before.bot) || 1;
    const moved = (Math.abs(now.top - before.top) + Math.abs(now.bot - before.bot)) / span;
    if (moved <= SCALE_TOL) return;

    const tag = document.createElement('div');
    tag.className = 'kh-scale-warn';
    tag.textContent = '세로가 움직임 — ' +
      Math.round(before.bot) + '~' + Math.round(before.top) + ' → ' +
      Math.round(now.bot) + '~' + Math.round(now.top) +
      ' (' + (moved * 100).toFixed(1) + '%)';
    container.appendChild(tag);
  }

  function checkAlign() {
    const old = container.querySelector('.kh-align-warn');
    if (old) old.remove();
    if (panes.length < 2) return;
    const w = panes.map((p) => {
      const cv = p.box.querySelector('canvas');
      return cv ? Math.round(cv.getBoundingClientRect().width) : null;
    }).filter((v) => v != null);
    if (!w.length || w.every((x) => Math.abs(x - w[0]) <= 1)) return;
    const tag = document.createElement('div');
    tag.className = 'kh-align-warn';
    tag.textContent = '좌우 끝이 어긋남 — ' + w.join(' · ') + 'px';
    container.appendChild(tag);
  }

  function toggleInd(key) {
    const on = indOn();
    if (on.has(key)) on.delete(key); else on.add(key);
    saveIndOn();
    _indSync.forEach((fn) => fn());
  }
  /* 칸이 늘거나 줄 때만 전부 다시 만든다. 가격 칸 위 지표는 그 자리에서 */
  function ownKeys() {
    return OWN_PANES
      .filter((x) => indOn().has(x.key) && (x.key !== 'vol' || showVolume))
      .map((x) => x.key).join(',');
  }
  let curOwn = '';

  function syncInd() {
    if (ownKeys() === curOwn) redrawOverlay();
    else build();
  }
  _indSync.add(syncInd);

  /* ── 칸 높이 끌기 — 그 경계의 위아래 둘만 바뀐다 ── */
  let drag = null;
  container.addEventListener('mousedown', (e) => {
    const g = e.target.closest('.kh-grip');
    if (!g) return;
    e.preventDefault();
    const at = panes.findIndex((p) => p.key === g.dataset.pane);
    if (at <= 0) return;
    g.classList.add('is-drag');
    drag = {
      g, y: e.clientY, above: panes[at - 1], below: panes[at],
      aH: panes[at - 1].box.clientHeight, bH: panes[at].box.clientHeight,
    };
    document.body.style.userSelect = 'none';
  });

  function onMove(e) {
    if (!drag) return;
    const d = e.clientY - drag.y;
    const minA = drag.above.key === 'price' ? PRICE_MIN : PANE_MIN;
    const a = Math.max(minA, Math.min(drag.aH + drag.bH - PANE_MIN, drag.aH + d));
    setPaneH(drag.above, a);
    setPaneH(drag.below, drag.aH + drag.bH - a);
  }
  function onUp() {
    if (!drag) return;
    drag.g.classList.remove('is-drag');
    drag = null;
    document.body.style.userSelect = '';
    savePaneH();
    checkAlign();
  }
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);

  function setPaneH(p, h) {
    p.box.style.height = h + 'px';
    try { p.chart.applyOptions({ height: h }); } catch { /* 이미 정리됨 */ }
    if (p.key !== 'price') paneH()[p.key] = h;
  }

  /* 닫기 단추 */
  container.addEventListener('click', (e) => {
    const x = e.target.closest('[data-pane-close]');
    if (!x) return;
    toggleInd(x.dataset.paneClose);
  });

  /* 마우스로 짚은 봉을 찾는 표 */
  const byTime = new Map();
  const remap = () => {
    byTime.clear();
    candles.forEach((c, i) => byTime.set(timeKey(toChartTime(c.ts, period)), i));
  };
  remap();

  const api = {
    get chart() { return panes[0] && panes[0].chart; },
    get candleSeries() { return candleSeries; },
    get maSeries() { return maSeries; },
    legend: null,

    addPriceLine(o) {
      try {
        const l = candleSeries.createPriceLine(o);
        priceLines.push(l);
        return l;
      } catch { return null; }
    },

    setData(next, nextPeriod) {
      if (!next || !next.length) return;
      candles = next;
      if (nextPeriod) period = nextPeriod;
      vpRange = null;          // 종목·기간이 바뀌면 세로 범위를 다시 잡는다
      priceLines.length = 0;
      remap();
      build();
    },

    resetView(bars) {
      panes.forEach((p) => showLastBars(p.chart, candles.length, bars));
      checkAlign();
    },

    /* ── 현재가로 맨 오른쪽 막대만 갱신한다 (2026-09-30 지시) ────────
     *
     * 재권님이 고르신 길이다 — 봉을 다시 받지 않고 **이미 오는 현재가**로
     * 진행 중인 막대의 종가·고가·저가만 고친다. **증권사 호출이 0건 는다.**
     *
     * **왜 이것으로 충분한가** — 5분봉은 5분에 한 번만 새 막대가 생긴다.
     * 그 사이 움직이는 것은 **맨 오른쪽 막대 하나**이고 그 종가는 현재가와
     * 같다. 봉 400개를 다시 받는 것은 **막대 하나를 위해 전부 다시 받는 것**
     * 이었다. 일봉 이상도 같다 — 마지막 봉이 「오늘」 이다.
     *
     * **`build()` 를 부르지 않는다.** 그것이 이 함수의 값이다 — 지표·매물대·
     * 범례를 다시 계산하면 막대 하나 고치는 비용이 전체 다시 그리기가 된다.
     * 그래서 **지표는 다음 `setData` 때 따라온다.**
     *
     * **거래량은 건드리지 않는다.** 5분봉의 거래량은 그 5분간의 것이고
     * `live.volume` 은 **하루 누적**이다. 섞으면 막대 하나가 하루치가 된다.
     *
     * `time` 을 기존 마지막 봉과 **같게** 만들어야 갱신이 된다 — 다르면
     * 라이브러리가 **새 봉을 붙인다.** */
    updateLast(live) {
      if (!live || !Number.isFinite(live.price) || live.price <= 0) return;
      const i = candles.length - 1;
      const last = candles[i];
      if (!last) return;
      const px = live.price;
      if (last.close === px) return;          // 안 움직였으면 그릴 것이 없다
      const next = {
        ...last,
        close: px,
        high: Math.max(last.high, px),
        low: Math.min(last.low, px),
      };
      candles[i] = next;
      try {
        candleSeries.update({
          time: toChartTime(next.ts, period),
          open: next.open, high: next.high, low: next.low, close: next.close,
        });
      } catch { /* 칸이 아직 없다 */ }
    },

    /* ── 보던 자리를 기간마다 따로 들고 가기 (2026-09-29 지시) ──────
     *
     * 재권님 말씀 — 「차트에서 월에가서 이동시키고 년으로 가면 년도 이동되는데
     * 각각 이동되는정보를 가지고 있어야지」.
     *
     * **원인은 `setData` 였다.** 첫 화면 카드는 차트를 다시 만들지 않고 봉만
     * 갈아끼우는데(`home.js` — 2026-09-17 지시로 그렇게 만들었다), `setData` 가
     * 부르는 `build()` 안의 `keep` 이 **이전 기간의 보이는 구간을 그대로**
     * 새 칸에 먹인다. 그래서 다섯 기간이 자리를 공유했다.
     *
     * 종목 화면은 `destroy()` 뒤 새로 만들어 `panes` 가 비므로 안 그랬다 —
     * **같은 증상이 한쪽에만 났던 이유다.**
     *
     * **`keep` 자체는 그대로 둔다.** 그것은 지표를 켜고 끌 때 보던 자리를
     * 지키는 장치다(2026-09-18 지시). 기간이 바뀔 때만 화면 쪽이 아래 둘로
     * 갈아끼운다. */

    /* 보이는 구간을 **오른쪽 끝 기준**으로 읽는다.
       `{from, to}` 를 그대로 저장하면 새 봉이 오른쪽에 붙을 때마다 화면이
       왼쪽으로 밀린다 — 5분봉은 5분에 하나씩 붙는다. */
    getView() {
      const ch = panes[0] && panes[0].chart;
      if (!ch) return null;
      try {
        const r = ch.timeScale().getVisibleLogicalRange();
        if (!r) return null;
        const last = candles.length - 1;
        return { fromRight: last - r.to, bars: r.to - r.from };
      } catch { return null; }
    },

    /* 기억해 둔 구간으로 되돌린다. `v` 가 없으면 **최신 쪽 `bars` 개**를 본다.

       두 번 먹인다 — 라이브러리가 한 박자 뒤에 제 계산을 밀어넣는다.
       `redrawOverlay` 가 같은 이유로 `requestAnimationFrame` 을 쓴다. */
    setView(v, bars) {
      const last = candles.length - 1;
      const to = v ? last - v.fromRight : last;
      const from = v ? to - v.bars : to - (bars || VISIBLE_BARS);
      const put = () => panes.forEach((p) => {
        try { p.chart.timeScale().setVisibleLogicalRange({ from, to }); }
        catch { /* 칸이 아직 없다 */ }
      });
      put();
      requestAnimationFrame(put);
    },

    destroy() {
      _indSync.delete(syncInd);
      if (vpTimer) { clearInterval(vpTimer); vpTimer = null; }   // 매물대 타이머
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      if (legend) legend.destroy();
      panes.forEach((p) => { try { p.chart.remove(); } catch { /* 이미 정리됨 */ } });
      panes = [];
      container.classList.remove('kh-panes');
    },
  };

  build();

  return api;
}

/* 값 배열의 단순 이동평균 (RSI 의 두 번째 선이 쓴다) */
function smaOf(vals, p) {
  const out = new Array(vals.length).fill(null);
  let sum = 0, cnt = 0;
  for (let i = 0; i < vals.length; i++) {
    const v = vals[i];
    if (v != null) { sum += v; cnt++; }
    if (i >= p) { const old = vals[i - p]; if (old != null) { sum -= old; cnt--; } }
    if (cnt >= p) out[i] = sum / p;
  }
  return out;
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

/* 보조지표 이름 줄은 **없앴다** (2026-09-18 지시 — "매물대 볼린저밴드
   이동평균선 거래량 MACD RSI 글씨는 없애줘").

   거래량 · MACD · RSI 는 제 칸에 이름표와 값이 따로 있어 중복이었고,
   차트 위 글씨가 봉을 가렸다. 켜고 끄는 것은 기간 줄의 「보조지표」 메뉴에서
   한다. 이동평균 값은 바로 위 MA 줄에 그대로 있다. */

function mountLegend(container, chart, { candles, period, maSeries, showVolume, ind }) {
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
    renderInd(i);
  }

  /* 켜 둔 보조지표의 그 봉 값. 꺼 둔 것은 빈칸이다 */
  /* 이름 줄을 없앴으므로 붙일 자리가 없다. 부르는 곳이 남아 있어 함수는
     두되 값이 갈 칸을 못 찾으면 그냥 지나간다. */
  function renderInd(i) {
    INDICATORS.forEach((x) => {
      const n = nodes[`ind-${x.key}`];
      if (!n) return;
      const it = ind && ind[x.key];
      if (!it) { n.textContent = ''; return; }
      const c = it.calc;
      let t = '';
      if (x.key === 'bb' && c.vUp[i] != null) {
        t = `${fmtPrice(c.vLo[i], dec)}~${fmtPrice(c.vUp[i], dec)}`;
      } else if (x.key === 'rsi' && c.values[i] != null) {
        t = c.values[i].toFixed(1);
      } else if (x.key === 'macd' && c.vHist[i] != null) {
        t = fmtPrice(c.vHist[i], 2);
      } else if (x.key === 'vma' && c.values[i] != null) {
        t = fmtVol(c.values[i]);
      } else if (x.key === 'ich' && c.vBase[i] != null) {
        t = `${fmtPrice(c.vConv[i], dec)} / ${fmtPrice(c.vBase[i], dec)}`;
      }
      n.textContent = t;
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

  /* 보조지표 칩은 이제 누르는 것이 아니다 — 값만 보여준다.
     끄고 켜는 것은 「보조지표」 메뉴 한 곳에서 한다 (2026-09-18 지시). */
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
    /* 지표를 켜고 끈 뒤 값을 다시 칠한다. 칩의 켜짐/꺼짐 표시는 없앴다 —
       켠 것만 칩이 생기므로 따로 흐리게 할 것이 없다. */
    refreshInd() {
      renderInd(candles.length - 1);
    },

    destroy() {
      _legendSync.delete(syncOff);
      if (ro) ro.disconnect();
      try { chart.unsubscribeCrosshairMove(onMove); } catch { /* 이미 정리됨 */ }
      el.remove();
      container.classList.remove('kh-lg-host');
    },
  };
}

/* ── 전일 종가 점선 (2026-09-23) ──────────────────────────────
 *
 * **오늘 올랐는지 내렸는지의 기준선**이다. 어제 마지막 봉의 종가에 점선을
 * 긋는다. 5분봉에만 뜻이 있다 — 일봉 이상이면 「어제」 가 봉 하나다.
 *
 * **여기 한 곳에 둔다.** 전에는 `home.js` 안에만 있어서, 같은 5분봉인데
 * **첫 화면 차트에는 선이 있고 종목 모달·종목 화면에는 없었다**
 * (2026-09-23 모달 검수). 룰이 「화면에 있는데 모달에 없으면 위반」 이므로
 * 모달에도 있어야 하는데, 옮기지 않고 베끼면 그 순간 복제가 둘이 된다.
 *
 * `addPriceLine` 으로 긋는다 — 다음에 봉을 갈아끼울 때 저절로 지워진다.
 * 직접 `createPriceLine` 을 부르면 종목을 옮길 때마다 선이 쌓인다.
 *
 * **그었나를 돌려준다.** 부르는 쪽이 아래 줄에 「점선은 전일 종가」 를 적을지
 * 정하는 데 쓴다 — 오늘 봉이 첫 봉이면 기준이 될 어제 봉이 없어 선을 못 긋는데,
 * 그때 설명만 남으면 없는 선을 가리킨다.
 */
export const PREV_CLOSE_NOTE = '점선은 전일 종가';

export function addPrevCloseLine(chart, candles) {
  if (!chart || !candles || candles.length < 2) return false;
  const today = candles[candles.length - 1].ts.slice(0, 8);
  const firstToday = candles.findIndex((b) => b.ts.slice(0, 8) === today);
  if (firstToday <= 0) return false;      // 오늘 봉이 없거나 첫 봉이 오늘이다
  chart.addPriceLine({
    price: candles[firstToday - 1].close,
    color: color('text-muted'),
    lineWidth: 1,
    lineStyle: 2,               // 점선
    axisLabelVisible: true,
    title: '전일',
  });
  return true;
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
