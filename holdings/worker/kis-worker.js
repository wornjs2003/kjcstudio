/**
 * KJC Holdings — 한국투자증권(KIS) 중계 서버 (Cloudflare Workers)
 *
 * 브라우저는 앱키를 절대 보지 못한다. 앱키는 Cloudflare Secret 으로만 존재하고,
 * 브라우저는 /api/kis/... 로 종목코드만 보낸다.
 *
 * 이 Worker 는 thekjcstudio.com/api/* 에 붙으므로 Cloudflare Access 뒤에 놓인다.
 * 즉 로그인한 사람만 호출할 수 있다.
 *
 * 두 가지를 맡는다.
 *   /api/kis/...   시세 · 지수 · 캔들 (한국투자증권)
 *   /api/dart/...  공시 (OpenDART) — 5분마다 Cron 으로 받아 D1 에 쌓는다
 *
 * ── 필요한 설정 ────────────────────────────────────────────────
 *  Secret (암호화 저장, 대시보드에서 직접 입력)
 *    KIS_APP_KEY         발급받은 App Key
 *    KIS_APP_SECRET      발급받은 App Secret
 *    DART_API_KEY        OpenDART 인증키 40자 — 없으면 공시만 꺼진다
 *    TELEGRAM_BOT_TOKEN  알림 봇 — 없으면 알림만 꺼진다 (화면에는 쌓인다)
 *    TELEGRAM_CHAT_ID    알림을 받을 대화방
 *  Variable (일반 변수)
 *    KIS_MODE         "prod" = 실전투자, "vts" = 모의투자
 *  KV 바인딩
 *    KIS_KV           접근토큰 보관용 (24시간)
 *  D1 바인딩
 *    KJC_DB           캔들 · 공시 저장
 *  Cron Trigger
 *    5분마다. Settings > Triggers > Cron Triggers 에서 건다.
 *    UTC 로 돌기 때문에 한국 시각 판단은 dartShouldPoll() 이 맡는다.
 * ─────────────────────────────────────────────────────────────
 */

const HOSTS = {
  prod: "https://openapi.koreainvestment.com:9443",
  vts: "https://openapivts.koreainvestment.com:29443",
};
const MODE_LABEL = { prod: "실전투자", vts: "모의투자" };

// 시장 구분
//   J  = KRX 정규장만 (09:00~15:30)
//   NX = 넥스트레이드(대체거래소)만
//   UN = 통합 — 정규장 + 넥스트레이드. 08:00~20:00 내내 값이 움직이고 거래량도 합산된다.
//
// 차트는 통합으로 고정한다. 과거 봉이라 "지금 몇 시인가"를 따질 일이 없다.
const MARKET_DIV_CHART = "UN";

/* 시세를 어느 시장 기준으로 볼지 정한다 (CLAUDE.md 의 시세 표기 규칙).

   정규장 중에는 KRX 값을 그대로 쓴다. 남들이 보는 숫자와 같아야 하기 때문이다.
   장이 끝나면 통합으로 넘겨서, 넥스트레이드에서 더 움직인 값이 있으면 그것을 쓴다.

   통합(UN)을 그냥 써도 되는 이유 — 넥스트레이드에 거래가 없으면 KRX 종가를
   그대로 돌려준다. 2026-09-12 에 실제로 호출해 확인했다.
     삼성전자우 193300 / 흥아해운 1878 / 동양3우B 5750  (NX 는 셋 다 0)

   Workers 는 UTC 로 돈다. 한국 시각은 +9 시간이라 직접 더해서 본다.
   공휴일은 가리지 못하지만, 휴장일에는 어느 쪽을 봐도 전일 값이라 문제되지 않는다. */
function quoteMarketDiv(now = new Date()) {
  const kst = new Date(now.getTime() + 9 * 3600 * 1000);
  const day = kst.getUTCDay();                 // 0 일요일 · 6 토요일
  if (day === 0 || day === 6) return "UN";
  const mins = kst.getUTCHours() * 60 + kst.getUTCMinutes();
  return mins >= 9 * 60 && mins < 15 * 60 + 30 ? "J" : "UN";
}

// 기간별 설정
//   freshSec : 이 시간이 지나면 최근 구간을 다시 받는다 (장중 캔들 갱신용)
const PERIODS = {
  D:    { kis: "D", label: "일",  freshSec: 60,   spanDays: 400 },
  W:    { kis: "W", label: "주",  freshSec: 300,  spanDays: 2000 },
  M:    { kis: "M", label: "월",  freshSec: 600,  spanDays: 4000 },
  Y:    { kis: "Y", label: "년",  freshSec: 3600, spanDays: 8000 },
  "1m": { kis: null, label: "1분", freshSec: 30,  spanDays: 1 },
  "5m": { kis: null, label: "5분", freshSec: 30,  spanDays: 1 },
};

// 분봉 수집 범위 (분 단위). 통합 시장 기준 08:00~20:00
const MINUTE_DAY_START = 8 * 60;
const MINUTE_DAY_END = 20 * 60;

// 시세 응답을 이 시간(초) 동안 캐시한다. KIS 호출량을 줄이는 핵심 장치.
//
// TTL 은 화면 갱신 주기보다 1~5초 짧게 잡는다. 그래야 자기 탭은 늘 새 값을 받고,
// 같은 종목을 거의 동시에 묻는 다른 탭만 캐시가 받아낸다.
// 갈래는 js/components/frame.js 의 PRIORITY_CODES 와 짝을 이룬다.
const FAST_CODES = new Set(["005930", "000660"]);   // 5초마다 갱신 — 삼성전자 · SK하이닉스
const QUOTE_CACHE_TTL_FAST = 4;                     // 빠른 갈래 (갱신 5초)
const QUOTE_CACHE_TTL = 25;                         // 느린 갈래 · 지수 (갱신 30초)

/* 종목이 어느 갈래인지에 따라 캐시 수명을 정한다. */
function quoteCacheTtl(code) {
  return FAST_CODES.has(code) ? QUOTE_CACHE_TTL_FAST : QUOTE_CACHE_TTL;
}
// 지수 일봉은 자주 바뀌지 않으므로 길게 캐시한다.
const CHART_CACHE_TTL = 600;
// 한 번에 조회할 수 있는 종목 수 상한 (과다 요청 방지)
const MAX_CODES = 40;

const INDEX_DEFS = [
  ["0001", "KOSPI"],
  ["1001", "KOSDAQ"],
  ["2001", "KOSPI200"],
];

/* ── 응답 헬퍼 ─────────────────────────────────────────────── */

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function fail(message, status = 502) {
  return json({ ok: false, error: message }, status);
}

/* ── 오류 메시지에서 비밀을 지운다 ────────────────────────────
   2026-09-14 에 실제로 인증키가 새어 나갔다. OpenDART 호출이 실패했을 때
   Cloudflare 런타임이 "Too many redirects.<요청 URL>" 처럼 요청 URL 을
   메시지에 붙이는데, 그 URL 에 crtfc_key 가 들어 있었다. 그것을 그대로
   저장하고 /api/dart/status 로 돌려줘서, 그 주소를 여는 사람이면
   누구나 40자 인증키를 볼 수 있었다.

   길이를 자르는 것으로는 막지 못한다(앞쪽에 키가 온다). 내용을 지워야 한다.
   저장할 때와 돌려줄 때 양쪽에서 거른다 — 이미 저장된 값도 가려야 하기 때문이다.

   외부 호출의 오류 메시지를 사람에게 보여줄 때는 반드시 이 함수를 거친다. */
const SECRET_QS = /([?&](?:crtfc_key|appkey|app_key|appsecret|app_secret|api_key|access_token|token|secret)=)[^&\s"']*/gi;

function scrub(text, env) {
  let s = String(text ?? "");
  s = s.replace(SECRET_QS, "$1<가림>");
  // 설정값이 쿼리스트링이 아닌 형태로 섞여 있을 수도 있다
  const secrets = [
    env?.DART_API_KEY, env?.KIS_APP_KEY, env?.KIS_APP_SECRET,
    env?.TELEGRAM_BOT_TOKEN, env?.TELEGRAM_CHAT_ID,
  ];
  for (const v of secrets) {
    const t = v ? String(v) : "";
    if (t.length >= 8) s = s.split(t).join("<가림>");
  }
  return s;
}

/* 예외를 사람이 볼 문구로. 비밀은 지우고 길이도 줄인다. */
function safeMessage(e, env, max = 160) {
  return scrub((e && e.message) || e, env).slice(0, max);
}

/* ── 설정 읽기 ─────────────────────────────────────────────── */

function readConfig(env) {
  const appKey = env.KIS_APP_KEY;
  const appSecret = env.KIS_APP_SECRET;
  const mode = (env.KIS_MODE || "prod").toLowerCase();

  if (!appKey || !appSecret) {
    throw new Error("KIS_APP_KEY / KIS_APP_SECRET 이 설정되지 않았습니다.");
  }
  if (!HOSTS[mode]) {
    throw new Error('KIS_MODE 는 "prod"(실전) 또는 "vts"(모의) 여야 합니다.');
  }
  return { appKey, appSecret, mode, host: HOSTS[mode] };
}

/* ── 접근토큰 (KV 에 24시간 보관) ───────────────────────────── */

async function getToken(cfg, env) {
  if (!env.KIS_KV) {
    throw new Error("KV 바인딩(KIS_KV)이 없습니다. 토큰을 보관할 수 없습니다.");
  }

  const key = `token:${cfg.mode}`;
  const cached = await env.KIS_KV.get(key, { type: "json" });
  // 만료 5분 전이면 새로 받는다
  if (cached && cached.expiresAt > Date.now() + 5 * 60 * 1000) {
    return cached.token;
  }

  const res = await fetch(`${cfg.host}/oauth2/tokenP`, {
    method: "POST",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({
      grant_type: "client_credentials",
      appkey: cfg.appKey,
      appsecret: cfg.appSecret,
    }),
  });

  const text = await res.text();
  if (!res.ok) {
    throw new Error(`토큰 발급 실패 (HTTP ${res.status}): ${scrub(text, env).slice(0, 200)}`);
  }

  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("토큰 응답을 해석할 수 없습니다.");
  }
  if (!data.access_token) {
    throw new Error("토큰 응답에 access_token 이 없습니다.");
  }

  const expiresIn = Number(data.expires_in || 86400);
  await env.KIS_KV.put(
    key,
    JSON.stringify({ token: data.access_token, expiresAt: Date.now() + expiresIn * 1000 }),
    { expirationTtl: Math.max(600, Math.min(expiresIn, 86400)) }
  );
  return data.access_token;
}

/* ── KIS 호출 ──────────────────────────────────────────────── */

/* ── 호출 간격 ──────────────────────────────────────────────
   KIS 는 초당 호출 건수를 제한한다(초과 시 EGW00201). 기본 한도는 초당 20건이다.

   이 장치가 없어서 차트가 안 나왔다 (2026-09-14 확인). 메인 화면은 열릴 때
   지수 3건 + 시세 8건 + 분봉 채우기 13~24건을 한꺼번에 쏜다. 분봉 쪽이 한도에
   걸려 전부 실패했고, 아래 fetchMinutesDay 의 catch 가 그 실패를 삼켜서
   "데이터가 없나 보다" 하고 넘어갔다. 그래서 D1 에 봉이 한 개도 쌓이지 않았다.

   200ms = 초당 5건. 기본 한도의 1/4 이다. 로컬(server/kis_proxy.py)은 1초
   간격이지만, 분봉 24번이면 24초라 화면이 못 기다린다. 여기만 다르게 잡는다.

   Workers 는 요청마다 격리되지만 한 요청 안의 순차 호출은 같은 isolate 에서
   돌기 때문에, 아래 약속 사슬로 줄을 세우면 간격이 지켜진다. */
const KIS_MIN_INTERVAL_MS = 200;
let _kisChain = Promise.resolve();
let _kisLastAt = 0;

function kisPace() {
  const turn = _kisChain.then(async () => {
    const wait = _kisLastAt + KIS_MIN_INTERVAL_MS - Date.now();
    if (wait > 0) await new Promise((r) => setTimeout(r, wait));
    _kisLastAt = Date.now();
  });
  _kisChain = turn.catch(() => {});   // 한 번 실패해도 줄이 끊기지 않게
  return turn;
}

async function kisGet(cfg, env, path, params, trId, cacheTtl) {
  const token = await getToken(cfg, env);
  await kisPace();
  const url = `${cfg.host}${path}?${new URLSearchParams(params)}`;

  // 같은 URL 요청은 Cloudflare 엣지 캐시가 받아낸다 -> KIS 호출이 줄어든다
  const res = await fetch(url, {
    headers: {
      authorization: `Bearer ${token}`,
      appkey: cfg.appKey,
      appsecret: cfg.appSecret,
      tr_id: trId,
      custtype: "P",
      "content-type": "application/json; charset=utf-8",
    },
    cf: cacheTtl ? { cacheTtl, cacheEverything: true } : undefined,
  });

  const text = await res.text();
  if (!res.ok) {
    // 초당 건수 초과는 호출한 쪽이 알아볼 수 있게 그대로 전달
    throw new Error(`KIS 호출 실패 (HTTP ${res.status}): ${scrub(text, env).slice(0, 200)}`);
  }

  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("KIS 응답을 해석할 수 없습니다.");
  }
  if (String(data.rt_cd ?? "0") !== "0") {
    throw new Error(`KIS 오류: ${data.msg1 || "알 수 없음"} (${data.msg_cd || ""})`);
  }
  return data;
}

const num = (v) => {
  const n = Number(String(v ?? "").trim());
  return Number.isFinite(n) ? n : null;
};

/* ── 종목 시세 ─────────────────────────────────────────────── */

async function fetchPrice(cfg, env, code) {
  const data = await kisGet(
    cfg, env,
    "/uapi/domestic-stock/v1/quotations/inquire-price",
    { FID_COND_MRKT_DIV_CODE: quoteMarketDiv(), FID_INPUT_ISCD: code },
    "FHKST01010100",
    quoteCacheTtl(code)
  );
  const o = data.output || {};
  const price = num(o.stck_prpr);
  const amt = num(o.prdy_vrss);
  return {
    code,
    price,
    prev: price != null && amt != null ? price - amt : null,
    amt,
    pct: num(o.prdy_ctrt),
    open: num(o.stck_oprc),
    high: num(o.stck_hgpr),
    low: num(o.stck_lwpr),
    volume: num(o.acml_vol),
    marketCap: num(o.hts_avls),
    per: num(o.per),
    pbr: num(o.pbr),
    eps: num(o.eps),
    bps: num(o.bps),
    high52: num(o.w52_hgpr),
    low52: num(o.w52_lwpr),
  };
}

async function fetchPrices(cfg, env, codes) {
  const data = {};
  const errors = {};
  // 순차 호출 — KIS 초당 건수 제한을 넘지 않도록. 캐시가 대부분 받아낸다.
  for (const code of codes) {
    try {
      data[code] = await fetchPrice(cfg, env, code);
    } catch (e) {
      errors[code] = safeMessage(e, env);
    }
  }
  return { data, errors };
}

/* ── 지수 ──────────────────────────────────────────────────
   지수는 주식과 다른 창구를 쓴다.
     주식: inquire-price       / FHKST01010100 / 시장구분 J / 값 stck_prpr
     지수: inquire-index-price / FHPUP02100000 / 시장구분 U / 값 bstp_nmix_prpr
   ─────────────────────────────────────────────────────────── */

async function fetchIndex(cfg, env, code) {
  const data = await kisGet(
    cfg, env,
    "/uapi/domestic-stock/v1/quotations/inquire-index-price",
    { FID_COND_MRKT_DIV_CODE: "U", FID_INPUT_ISCD: code },
    "FHPUP02100000",
    QUOTE_CACHE_TTL
  );
  const o = data.output || {};
  return {
    value: num(o.bstp_nmix_prpr),
    change: num(o.bstp_nmix_prdy_vrss),
    changePct: num(o.bstp_nmix_prdy_ctrt),
  };
}

function ymd(d) {
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
}

async function fetchIndexSeries(cfg, env, code, days = 60) {
  const end = new Date();
  const start = new Date(end.getTime() - (days * 2 + 30) * 86400000); // 휴장일 감안
  const data = await kisGet(
    cfg, env,
    "/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice",
    {
      FID_COND_MRKT_DIV_CODE: "U",
      FID_INPUT_ISCD: code,
      FID_INPUT_DATE_1: ymd(start),
      FID_INPUT_DATE_2: ymd(end),
      FID_PERIOD_DIV_CODE: "D",
    },
    "FHKUP03500100",
    CHART_CACHE_TTL
  );
  const rows = data.output2 || [];
  return rows
    .filter((r) => r.stck_bsop_date && num(r.bstp_nmix_prpr) != null)
    .sort((a, b) => String(a.stck_bsop_date).localeCompare(String(b.stck_bsop_date)))
    .map((r) => num(r.bstp_nmix_prpr))
    .slice(-days);
}

async function fetchIndices(cfg, env, withChart = true) {
  const out = [];
  const errors = {};
  for (const [code, name] of INDEX_DEFS) {
    try {
      const info = await fetchIndex(cfg, env, code);
      let series = [];
      if (withChart) {
        try {
          series = await fetchIndexSeries(cfg, env, code);
        } catch {
          series = []; // 차트만 실패해도 현재값은 보여준다
        }
      }
      out.push({ code: name, name, unit: "pt", ...info, series, source: "KIS" });
    } catch (e) {
      errors[name] = safeMessage(e, env);
    }
  }
  return { data: out, errors };
}

/* ── 저장 계층 (Cloudflare D1) ──────────────────────────────
   차트는 과거 데이터가 필요한데 볼 때마다 KIS 를 부르면 호출량을 감당할 수 없다.
   한 번 받은 일봉을 여기 쌓아두고, 이후에는 DB 에서 바로 꺼내 쓴다.
   ─────────────────────────────────────────────────────────── */

// ts 형식: 일/주/월/년봉은 YYYYMMDD, 분봉은 YYYYMMDDHHMM
const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS candles (
     code   TEXT    NOT NULL,
     period TEXT    NOT NULL,
     ts     TEXT    NOT NULL,
     open   INTEGER,
     high   INTEGER,
     low    INTEGER,
     close  INTEGER,
     volume INTEGER,
     PRIMARY KEY (code, period, ts)
   )`,
  `CREATE INDEX IF NOT EXISTS idx_candles ON candles (code, period, ts DESC)`,
  `CREATE TABLE IF NOT EXISTS sync_meta (
     key        TEXT PRIMARY KEY,
     value      TEXT,
     updated_at TEXT
   )`,
];

function requireDb(env) {
  if (!env.KJC_DB) {
    throw new Error("D1 바인딩(KJC_DB)이 없습니다. Worker 설정에서 연결해 주세요.");
  }
  return env.KJC_DB;
}

async function dbInit(env) {
  const db = requireDb(env);
  for (const sql of SCHEMA) await db.prepare(sql).run();
  return { created: SCHEMA.length };
}

async function dbStatus(env) {
  const db = requireDb(env);
  // 테이블이 아직 없으면 여기서 오류가 난다 -> init 이 필요하다는 뜻
  const rows = await db.prepare(
    `SELECT COUNT(*) AS rows, COUNT(DISTINCT code) AS codes,
            MIN(ts) AS firstTs, MAX(ts) AS lastTs
       FROM candles`
  ).first();
  return {
    rows: rows?.rows ?? 0,
    codes: rows?.codes ?? 0,
    firstTs: rows?.firstTs ?? null,
    lastTs: rows?.lastTs ?? null,
  };
}

async function metaGet(env, key) {
  const r = await requireDb(env)
    .prepare(`SELECT value FROM sync_meta WHERE key = ?`).bind(key).first();
  return r?.value ?? null;
}

async function metaSet(env, key, value) {
  await requireDb(env).prepare(
    `INSERT INTO sync_meta (key, value, updated_at) VALUES (?, ?, ?)
     ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at`
  ).bind(key, String(value), new Date().toISOString()).run();
}

/* 일/주/월/년봉. 같은 API 에서 기간 구분 코드만 바뀐다 (한 번에 최대 100개) */
async function fetchBarsFromKis(cfg, env, code, period, from, to) {
  const data = await kisGet(
    cfg, env,
    "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
    {
      FID_COND_MRKT_DIV_CODE: MARKET_DIV_CHART,
      FID_INPUT_ISCD: code,
      FID_INPUT_DATE_1: from,
      FID_INPUT_DATE_2: to,
      FID_PERIOD_DIV_CODE: PERIODS[period].kis,
      FID_ORG_ADJ_PRC: "0",       // 0 = 수정주가 반영
    },
    "FHKST03010100",
    QUOTE_CACHE_TTL
  );
  return (data.output2 || [])
    .filter((r) => r.stck_bsop_date && num(r.stck_clpr) != null)
    .map((r) => ({
      ts: String(r.stck_bsop_date),
      open: num(r.stck_oprc),
      high: num(r.stck_hgpr),
      low: num(r.stck_lwpr),
      close: num(r.stck_clpr),
      volume: num(r.acml_vol),
    }));
}

/* 1분봉. 별도 API 이며 기준 시각부터 과거 30개만 돌려준다 */
/* hour 를 주지 않으면 '지금까지' 를 기준으로 삼는다.
   예전 기본값은 "200000"(20:00) 이라, 장중에 최근 구간을 갱신할 때마다
   아직 오지 않은 시각에 가짜 봉이 생겼다. 서버(kis_proxy.py)와 같은 규칙이다. */
async function fetchMinutesFromKis(cfg, env, code, hour = null) {
  if (hour === null) {
    const m = minuteScanStart();
    hour = String(Math.floor(m / 60)).padStart(2, "0") + String(m % 60).padStart(2, "0") + "00";
  }
  const data = await kisGet(
    cfg, env,
    "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
    {
      FID_ETC_CLS_CODE: "",
      FID_COND_MRKT_DIV_CODE: MARKET_DIV_CHART,
      FID_INPUT_ISCD: code,
      FID_INPUT_HOUR_1: hour,
      FID_PW_DATA_INCU_YN: "Y",
    },
    "FHKST03010200",
    QUOTE_CACHE_TTL
  );
  return (data.output2 || [])
    .filter((r) => r.stck_bsop_date && r.stck_cntg_hour && num(r.stck_prpr) != null)
    .map((r) => ({
      ts: `${r.stck_bsop_date}${String(r.stck_cntg_hour).slice(0, 4)}`,
      open: num(r.stck_oprc),
      high: num(r.stck_hgpr),
      low: num(r.stck_lwpr),
      close: num(r.stck_prpr),
      volume: num(r.cntg_vol),
    }));
}

/* 하루치 1분봉. 30분씩 거슬러 올라가며 여러 번 부른다 */
/* 분봉을 어느 시각부터 거슬러 내려갈지 정한다.

   아직 오지 않은 시각은 묻지 않는다. 장중에 20:00 같은 미래 시각을 요청하면
   KIS 가 마지막 체결값을 그 시각의 봉인 것처럼 돌려주고, 그대로 저장하면
   체결되지도 않은 시간대에 가짜 봉이 생긴다.
   (2026-09-14 11:52 에 로컬 서버에서 종목당 98개씩 확인)

   서버(kis_proxy.py)의 minute_scan_start() 와 같은 판단을 해야 한다.
   한쪽만 고치면 로컬과 배포본의 캔들이 갈린다. */
function minuteScanStart(now = new Date()) {
  const kst = new Date(now.getTime() + 9 * 3600 * 1000);
  const day = kst.getUTCDay();
  if (day === 0 || day === 6) return MINUTE_DAY_END;      // 주말 — 하루치
  const cur = kst.getUTCHours() * 60 + kst.getUTCMinutes();
  if (cur >= MINUTE_DAY_END) return MINUTE_DAY_END;       // 20:00 이후 — 하루치
  return cur;                                             // 그 밖에는 지금까지만
}

/* 실패를 삼키지 않는다. 구간마다 진짜로 데이터가 없을 수도 있으므로 한 번
   실패했다고 전체를 접지는 않지만, 몇 번 실패했고 마지막 이유가 무엇인지는
   응답에 실어 보낸다. 예전에는 조용히 넘어가서 차트가 왜 비는지 알 수 없었다. */
async function fetchMinutesDay(cfg, env, code) {
  const bars = new Map();
  let tried = 0;
  let failed = 0;
  let lastError = null;

  for (let t = minuteScanStart(); t >= MINUTE_DAY_START; t -= 30) {
    const hour = `${String(Math.floor(t / 60)).padStart(2, "0")}${String(t % 60).padStart(2, "0")}00`;
    tried++;
    try {
      for (const b of await fetchMinutesFromKis(cfg, env, code, hour)) bars.set(b.ts, b);
    } catch (e) {
      failed++;
      lastError = safeMessage(e, env);
    }
  }
  return {
    bars: [...bars.values()].sort((a, b) => a.ts.localeCompare(b.ts)),
    tried, failed, lastError,
  };
}

/* 1분봉을 N분봉으로 묶는다 (KIS 는 5분봉을 직접 주지 않는다) */
function aggregateMinutes(bars, minutes) {
  const buckets = new Map();
  for (const b of [...bars].sort((x, y) => x.ts.localeCompare(y.ts))) {
    const hhmm = b.ts.slice(8, 12);
    const slot = Math.floor((Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(2))) / minutes) * minutes;
    const key = b.ts.slice(0, 8)
      + String(Math.floor(slot / 60)).padStart(2, "0")
      + String(slot % 60).padStart(2, "0");
    const g = buckets.get(key);
    if (!g) {
      buckets.set(key, { ts: key, open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume || 0 });
    } else {
      g.high = Math.max(g.high, b.high);
      g.low = Math.min(g.low, b.low);
      g.close = b.close;
      g.volume += (b.volume || 0);
    }
  }
  return [...buckets.values()].sort((a, b) => a.ts.localeCompare(b.ts));
}

async function saveCandles(env, code, period, candles) {
  if (!candles.length) return 0;
  const db = requireDb(env);
  const stmt = db.prepare(
    `INSERT INTO candles (code, period, ts, open, high, low, close, volume)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(code, period, ts) DO UPDATE SET
       open=excluded.open, high=excluded.high, low=excluded.low,
       close=excluded.close, volume=excluded.volume`
  );
  // D1 batch 는 한 번에 보낼 수 있는 양에 한계가 있어 나눠 보낸다
  const CHUNK = 100;
  for (let i = 0; i < candles.length; i += CHUNK) {
    await db.batch(candles.slice(i, i + CHUNK).map((c) =>
      stmt.bind(code, period, c.ts, c.open, c.high, c.low, c.close, c.volume)
    ));
  }
  return candles.length;
}

async function readCandles(env, code, period, limit) {
  const res = await requireDb(env).prepare(
    `SELECT ts, open, high, low, close, volume
       FROM candles WHERE code = ? AND period = ?
       ORDER BY ts DESC LIMIT ?`
  ).bind(code, period, limit).all();
  // 차트는 과거 -> 최신 순서가 필요하다
  return (res.results || []).reverse();
}

function ymdOffset(daysAgo) {
  return ymd(new Date(Date.now() - daysAgo * 86400000));
}

/* 차트 데이터: DB 를 먼저 보고, 최근 구간이 오래됐으면 KIS 에서 받아 덮어쓴다.
   당일 캔들은 장중에 계속 바뀌므로 freshSec 이 지나면 다시 받는다. */
async function getChart(cfg, env, code, period, limit) {
  const conf = PERIODS[period];
  let rows = await readCandles(env, code, period, limit);

  const mkey = `sync:${code}:${period}`;
  const lastSync = Number(await metaGet(env, mkey)) || 0;
  const stale = Date.now() - lastSync > conf.freshSec * 1000;

  let fetched = 0;
  let warn = null;          // 받아오다 일부 실패했으면 이유를 남긴다
  if (!rows.length || stale) {
    let bars;
    if (conf.kis) {                       // 일/주/월/년
      bars = await fetchBarsFromKis(cfg, env, code, period, ymdOffset(conf.spanDays), ymd(new Date()));
    } else {                              // 분봉
      // 처음이면 하루치를 모으고, 이후에는 최근 구간만 갱신한다
      let raw;
      if (rows.length) {
        raw = await fetchMinutesFromKis(cfg, env, code);
      } else {
        const day = await fetchMinutesDay(cfg, env, code);
        raw = day.bars;
        if (day.failed) {
          warn = `분봉 ${day.tried}구간 중 ${day.failed}구간 실패 (${day.lastError || "이유 없음"})`;
        }
      }
      bars = period === "5m" ? aggregateMinutes(raw, 5) : raw;
    }
    fetched = await saveCandles(env, code, period, bars);
    await metaSet(env, mkey, Date.now());
    if (fetched) rows = await readCandles(env, code, period, limit);
  }
  return { rows, fetched, warn, source: fetched ? "KIS+DB" : "DB" };
}

/* ══ 공시 (OpenDART) ═════════════════════════════════════════
   로컬은 server/dart.py 가 같은 일을 한다. 두 곳이 같은 판단을 해야 한다.

   여기서는 기업 대응표(corpCode.xml)를 받지 않는다. 그것은 ZIP 이라
   Workers 에서 풀려면 압축 해제를 직접 구현해야 하는데, 정작 화면에는
   쓰이지 않는다. 공시 목록(list.json)이 종목코드와 회사명을 이미 준다.

   필요한 설정
     Secret    DART_API_KEY         OpenDART 인증키 (40자)
     Secret    TELEGRAM_BOT_TOKEN   알림을 보낼 봇 (없으면 알림만 꺼진다)
     Secret    TELEGRAM_CHAT_ID     받을 대화방
     Cron      5분마다 (분 자리에 "*" 와 "/5" 를 붙여 쓴다). UTC 기준으로 돈다
   ══════════════════════════════════════════════════════════ */

const DART_API = "https://opendart.fss.or.kr/api";
const DART_VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=";
const UNIVERSE_SIZE = 200;          // 코스피 시가총액 상위 몇 종목을 볼 것인가

/* 텔레그램을 보낼 종목. server/dart.py 의 WATCH_CODES 와 같아야 한다.
   순위(200종목)가 양쪽에서 조금 달라져도 알림은 이 목록에만 가므로 영향이 없다. */
const DART_WATCH_CODES = [
  "005930", "000660", "035420", "035720",
  "005380", "373220", "207940", "068270",
];

const DART_SCHEMA = [
  `CREATE TABLE IF NOT EXISTS dart_universe (
     stock_code TEXT PRIMARY KEY,
     name       TEXT,
     rank       INTEGER,
     market_cap INTEGER,
     updated_at TEXT
   )`,
  `CREATE TABLE IF NOT EXISTS dart_disclosures (
     rcept_no    TEXT PRIMARY KEY,
     corp_code   TEXT,
     stock_code  TEXT,
     corp_name   TEXT,
     report_nm   TEXT,
     flr_nm      TEXT,
     rcept_dt    TEXT,
     rm          TEXT,
     received_at TEXT,
     notified    INTEGER DEFAULT 0
   )`,
  `CREATE INDEX IF NOT EXISTS idx_disc_stock ON dart_disclosures (stock_code, rcept_no DESC)`,
  `CREATE INDEX IF NOT EXISTS idx_disc_recent ON dart_disclosures (rcept_no DESC)`,
];

async function dartInit(env) {
  const db = requireDb(env);
  // sync_meta 는 시세 쪽 SCHEMA 에 있지만, 공시가 먼저 돌 수도 있으므로 여기서도 보장한다
  await db.prepare(`CREATE TABLE IF NOT EXISTS sync_meta (
     key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)`).run();
  for (const sql of DART_SCHEMA) await db.prepare(sql).run();
  return db;
}

/* 한국 시각 기준 오늘 (YYYYMMDD). Workers 는 UTC 로 돈다. */
function kstToday(now = new Date()) {
  const kst = new Date(now.getTime() + 9 * 3600 * 1000);
  return `${kst.getUTCFullYear()}${String(kst.getUTCMonth() + 1).padStart(2, "0")}${String(kst.getUTCDate()).padStart(2, "0")}`;
}

/* 물어볼 시간대인가. DART 접수는 평일에만 있다.
   server/dart.py 의 _should_poll() 과 같은 판단이어야 한다. */
function dartShouldPoll(now = new Date()) {
  const kst = new Date(now.getTime() + 9 * 3600 * 1000);
  const day = kst.getUTCDay();
  if (day === 0 || day === 6) return false;
  const mins = kst.getUTCHours() * 60 + kst.getUTCMinutes();
  return mins >= 7 * 60 && mins < 20 * 60;
}

/* ── 감시 대상 200종목 (네이버 시가총액 순위) ──
   공식 API 가 아니다. 한국투자증권 순위 API 는 30건까지만 주기 때문에
   200종목을 만들 수 없어서 이쪽을 쓴다. 못 받으면 기존 목록을 그대로 둔다. */
async function fetchKospiTop(size = UNIVERSE_SIZE) {
  const out = [];
  for (let page = 1; out.length < size && page <= 10; page++) {
    const res = await fetch(
      `https://m.stock.naver.com/api/stocks/marketValue/KOSPI?page=${page}&pageSize=100`,
      { headers: { "user-agent": "Mozilla/5.0", referer: "https://m.stock.naver.com/" } }
    );
    if (!res.ok) throw new Error(`네이버 시가총액 순위 HTTP ${res.status}`);
    const body = await res.json();
    const items = body.stocks || [];
    if (!items.length) break;
    for (const it of items) {
      const code = String(it.itemCode || "").trim();
      if (!/^\d{6}$/.test(code)) continue;
      out.push({
        code,
        name: String(it.stockName || "").trim(),
        cap: parseInt(String(it.marketValue ?? "").replace(/[^0-9-]/g, ""), 10) || null,
      });
    }
  }
  return out.slice(0, size);
}

async function refreshUniverse(env, size = UNIVERSE_SIZE) {
  const db = await dartInit(env);
  let items;
  try {
    items = await fetchKospiTop(size);
  } catch (e) {
    return { ok: false, error: `시가총액 순위를 받지 못했습니다: ${safeMessage(e, env)}` };
  }
  if (items.length < 50) {
    return { ok: false, error: `받은 종목이 ${items.length}개뿐이라 반영하지 않았습니다.` };
  }

  const now = new Date().toISOString();
  const stmt = db.prepare(
    `INSERT INTO dart_universe (stock_code, name, rank, market_cap, updated_at)
     VALUES (?, ?, ?, ?, ?)
     ON CONFLICT(stock_code) DO UPDATE SET
       name=excluded.name, rank=excluded.rank,
       market_cap=excluded.market_cap, updated_at=excluded.updated_at`
  );
  await db.prepare(`DELETE FROM dart_universe`).run();
  const CHUNK = 100;
  for (let i = 0; i < items.length; i += CHUNK) {
    await db.batch(items.slice(i, i + CHUNK).map((it, j) =>
      stmt.bind(it.code, it.name, i + j + 1, it.cap, now)
    ));
  }
  await metaSet(env, "dart_universe_date", kstToday());
  return { ok: true, count: items.length };
}

async function universeCodes(env) {
  const db = await dartInit(env);
  const res = await db.prepare(`SELECT stock_code FROM dart_universe`).all();
  return new Set((res.results || []).map((r) => r.stock_code));
}

/* ── 공시 목록 ──
   corp_cls  Y=유가증권(코스피) K=코스닥 N=코넥스 E=기타
   status    000 정상 · 013 데이터 없음 · 020 하루 한도 초과 · 800 점검 */
async function fetchDartList(key, bgn, end, corpCls = "Y", maxPages = 12) {
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    const qs = new URLSearchParams({
      crtfc_key: key, bgn_de: bgn, end_de: end,
      corp_cls: corpCls, page_no: String(page), page_count: "100",
    });

    /* redirect:"manual" 로 둔다. 기본값(follow)으로 두었더니 배포본에서
       "Too many redirects" 가 났고, 그 오류 메시지에 요청 URL 이 통째로
       들어가면서 인증키가 새어 나갔다 (2026-09-14).

       왜 Workers 에서만 리다이렉트가 도는지는 확인하지 못했다. 같은 호출이
       로컬 파이썬과 Node 에서는 헤더 유무·redirect 설정과 무관하게 바로 200 이
       온다. Cloudflare 공식 문서에도 fetch 의 리다이렉트 한도나 동작이 적혀
       있지 않았다.

       그래서 원인을 모른 채로도 안전하도록, 따라가지 않고 그 자리에서 멈춘다.
       루프가 생기지 않고, 어디로 보내려 했는지가 오류 문구에 남아 다음에
       원인을 좁힐 수 있다. 로컬 파이썬과 같은 헤더도 함께 보낸다. */
    const res = await fetch(`${DART_API}/list.json?${qs}`, {
      redirect: "manual",
      headers: {
        "user-agent": "KJC-Holdings/1.0",
        accept: "application/json",
      },
    });

    if (res.status >= 300 && res.status < 400) {
      const to = res.headers.get("location") || "(Location 없음)";
      throw new Error(`OpenDART 가 ${res.status} 로 다른 곳을 가리킵니다: ${to}`);
    }
    if (!res.ok) throw new Error(`OpenDART HTTP ${res.status}`);
    const body = await res.json();

    if (body.status === "013") break;              // 아직 공시가 없다
    if (body.status !== "000") {
      throw new Error(`${body.status} ${body.message || ""}`);
    }
    out.push(...(body.list || []));
    if (page >= Number(body.total_page || 1)) break;
  }
  return out;
}

/* 감시 대상 것만 저장하고, 새로 들어온 것만 돌려준다.
   notified=1 로 넣으면 '이미 알린 것으로 친다'. 처음 켤 때 쌓여 있던 것을
   전부 보내면 텔레그램이 도배된다. */
async function saveDisclosures(env, items, onlyCodes, notified = 0) {
  const db = await dartInit(env);
  const fresh = [];
  const rows = [];

  for (const it of items) {
    const code = String(it.stock_code || "").trim();
    if (!onlyCodes.has(code)) continue;
    const rcept = String(it.rcept_no || "").trim();
    if (!rcept) continue;
    rows.push({
      rcept_no: rcept,
      corp_code: String(it.corp_code || "").trim(),
      stock_code: code,
      corp_name: String(it.corp_name || "").trim(),
      report_nm: String(it.report_nm || "").trim(),
      flr_nm: String(it.flr_nm || "").trim(),
      rcept_dt: String(it.rcept_dt || "").trim(),
      rm: String(it.rm || "").trim(),
    });
  }
  if (!rows.length) return fresh;

  // 이미 있는 것을 한 번에 가려낸다 (건마다 묻지 않는다)
  const known = new Set();
  const CHECK = 100;
  for (let i = 0; i < rows.length; i += CHECK) {
    const slice = rows.slice(i, i + CHECK);
    const marks = slice.map(() => "?").join(",");
    const res = await db.prepare(
      `SELECT rcept_no FROM dart_disclosures WHERE rcept_no IN (${marks})`
    ).bind(...slice.map((r) => r.rcept_no)).all();
    for (const r of res.results || []) known.add(r.rcept_no);
  }

  const now = new Date().toISOString();
  const stmt = db.prepare(
    `INSERT INTO dart_disclosures
       (rcept_no, corp_code, stock_code, corp_name, report_nm,
        flr_nm, rcept_dt, rm, received_at, notified)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(rcept_no) DO NOTHING`
  );
  const todo = rows.filter((r) => !known.has(r.rcept_no));
  for (let i = 0; i < todo.length; i += CHECK) {
    await db.batch(todo.slice(i, i + CHECK).map((r) =>
      stmt.bind(r.rcept_no, r.corp_code, r.stock_code, r.corp_name,
                r.report_nm, r.flr_nm, r.rcept_dt, r.rm, now, notified)
    ));
  }
  fresh.push(...todo);
  return fresh;
}

async function readDisclosures(env, code, limit) {
  const db = await dartInit(env);
  const n = Math.min(Math.max(parseInt(limit, 10) || 30, 1), 200);
  const res = code
    ? await db.prepare(
        `SELECT rcept_no, stock_code, corp_name, report_nm, flr_nm, rcept_dt, rm
           FROM dart_disclosures WHERE stock_code = ?
           ORDER BY rcept_no DESC LIMIT ?`).bind(code, n).all()
    : await db.prepare(
        `SELECT rcept_no, stock_code, corp_name, report_nm, flr_nm, rcept_dt, rm
           FROM dart_disclosures ORDER BY rcept_no DESC LIMIT ?`).bind(n).all();

  return (res.results || []).map((r) => ({
    rceptNo: r.rcept_no,
    code: r.stock_code,
    name: r.corp_name,
    title: r.report_nm,
    filer: r.flr_nm,
    date: r.rcept_dt,
    note: r.rm,
    url: DART_VIEWER + r.rcept_no,
  }));
}

/* ── 텔레그램 ── */

function telegramConfig(env) {
  if (env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_CHAT_ID) {
    return { token: env.TELEGRAM_BOT_TOKEN, chat: String(env.TELEGRAM_CHAT_ID) };
  }
  return null;
}

async function telegramSend(env, text) {
  const cfg = telegramConfig(env);
  if (!cfg) return false;
  try {
    const res = await fetch(`https://api.telegram.org/bot${cfg.token}/sendMessage`, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        chat_id: cfg.chat, text, disable_web_page_preview: "true",
      }),
    });
    const body = await res.json();
    return !!body.ok;
  } catch {
    return false;
  }
}

function dartMessage(row) {
  const dt = row.rcept_dt || "";
  const when = dt.length === 8 ? `${dt.slice(4, 6)}-${dt.slice(6, 8)}` : dt;
  const lines = [`📢 ${row.corp_name} (${row.stock_code})`, row.report_nm];
  if (row.flr_nm && row.flr_nm !== row.corp_name) lines.push(`제출: ${row.flr_nm}`);
  lines.push(`접수 ${when}`);
  lines.push(DART_VIEWER + row.rcept_no);
  return lines.join("\n");
}

/* 관심종목 공시만 보낸다. 보낸 것은 표시해 두어 두 번 보내지 않는다. */
async function dartNotify(env, rows) {
  const db = requireDb(env);
  let sent = 0;
  for (const row of rows) {
    if (!DART_WATCH_CODES.includes(row.stock_code)) continue;
    const ok = await telegramSend(env, dartMessage(row));
    await db.prepare(`UPDATE dart_disclosures SET notified = ? WHERE rcept_no = ?`)
      .bind(ok ? 1 : 0, row.rcept_no).run();
    if (ok) sent++;
  }
  return sent;
}

/* ── 한 바퀴 ── */

async function dartPollOnce(env, quietFirstRun = true) {
  const key = env.DART_API_KEY;
  if (!key) return { ok: false, error: "DART_API_KEY 가 설정되지 않았습니다." };

  await dartInit(env);
  const today = kstToday();

  if ((await metaGet(env, "dart_universe_date")) !== today) {
    const u = await refreshUniverse(env);
    if (!u.ok) await metaSet(env, "dart_last_error", u.error);
  }

  const codes = await universeCodes(env);
  if (!codes.size) {
    const msg = "감시 대상 목록이 비어 있습니다";
    await metaSet(env, "dart_last_error", msg);
    return { ok: false, error: msg };
  }

  let items;
  try {
    items = await fetchDartList(key, today, today);
  } catch (e) {
    const msg = safeMessage(e, env);
    await metaSet(env, "dart_last_error", msg);
    return { ok: false, error: msg };
  }

  const firstRun = !(await metaGet(env, "dart_last_poll"));
  const mark = firstRun && quietFirstRun ? 1 : 0;

  const fresh = await saveDisclosures(env, items, codes, mark);
  const notified = mark ? 0 : await dartNotify(env, fresh);

  await metaSet(env, "dart_last_poll", new Date().toISOString());
  await metaSet(env, "dart_last_error", "");
  return { ok: true, received: items.length, matched: fresh.length, notified, firstRun };
}

async function dartStatus(env) {
  let universe = 0, disclosures = 0, lastReceivedAt = null, dbError = null;
  try {
    const db = await dartInit(env);
    universe = (await db.prepare(`SELECT COUNT(*) n FROM dart_universe`).first()).n;
    const d = await db.prepare(
      `SELECT COUNT(*) n, MAX(received_at) t FROM dart_disclosures`).first();
    disclosures = d.n;
    lastReceivedAt = d.t;
  } catch (e) {
    dbError = safeMessage(e, env);
  }
  // status 는 화면이 "공시를 쓸 수 있는가" 를 판단하는 곳이다. 절대 터지면 안 된다.
  // D1 바인딩이 없으면 위에서 dbError 가 잡히는데, 그 상태로 메모를 읽으면 또 터진다.
  let lastPollAt = null;
  let lastPollError = null;
  try {
    lastPollAt = await metaGet(env, "dart_last_poll");
    const stored = await metaGet(env, "dart_last_error");
    // 저장할 때 이미 걸렀지만, 고치기 전에 저장된 값이 남아 있을 수 있어
    // 돌려줄 때 한 번 더 거른다.
    lastPollError = stored ? scrub(stored, env) : null;
  } catch {
    // dbError 에 이미 사유가 담겨 있다
  }

  return {
    configured: !!env.DART_API_KEY,
    telegram: !!telegramConfig(env),
    universe, disclosures, lastReceivedAt,
    lastPollAt, lastPollError,
    watchCodes: DART_WATCH_CODES,
    dbError,
    runtime: "workers",
  };
}

/* ── 라우팅 ────────────────────────────────────────────────── */

export default {
  // Cron Trigger 진입점. 대시보드에서 5분마다로 건다 (표현식은 이 파일 위쪽 설명 참고).
  // Cron 은 UTC 로 돌기 때문에, 한국 시각·요일 판단은 dartShouldPoll() 이 맡는다.
  async scheduled(controller, env, ctx) {
    ctx.waitUntil((async () => {
      if (!dartShouldPoll()) return;
      try {
        await dartPollOnce(env);
      } catch (e) {
        try { await metaSet(env, "dart_last_error", safeMessage(e, env)); } catch {}
      }
    })());
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    const route = url.pathname.replace(/^\/api\/kis\/?/, "").replace(/\/$/, "");

    // ── 공시 ──
    if (url.pathname.startsWith("/api/dart")) {
      if (request.method !== "GET") return fail("GET 요청만 지원합니다.", 405);
      const dartRoute = url.pathname.replace(/^\/api\/dart\/?/, "").replace(/\/$/, "");
      try {
        if (dartRoute === "status") {
          return json({ ok: true, data: await dartStatus(env) });
        }
        if (!env.DART_API_KEY) {
          return fail("OpenDART 인증키(DART_API_KEY)가 설정되지 않았습니다.", 503);
        }
        if (dartRoute === "disclosures") {
          const code = (url.searchParams.get("code") || "").trim();
          if (code && !/^\d{6}$/.test(code)) {
            return fail("code 는 6자리 숫자여야 합니다.", 400);
          }
          const rows = await readDisclosures(env, code || null, url.searchParams.get("limit") || "30");
          return json({
            ok: true,
            data: rows,
            meta: { count: rows.length, code: code || null,
                    lastPollAt: await metaGet(env, "dart_last_poll") },
          });
        }
        if (dartRoute === "poll") {       // 5분을 기다리지 않고 지금 한 번
          return json({ ok: true, data: await dartPollOnce(env) });
        }
        if (dartRoute === "universe") {
          const db = await dartInit(env);
          const res = await db.prepare(
            `SELECT rank, stock_code, name, market_cap FROM dart_universe ORDER BY rank`).all();
          return json({ ok: true, data: (res.results || []).map((r) => ({
            rank: r.rank, code: r.stock_code, name: r.name, cap: r.market_cap,
          })) });
        }
        return fail(`알 수 없는 경로입니다: ${dartRoute}`, 404);
      } catch (e) {
        return fail(safeMessage(e, env), 500);
      }
    }

    if (!url.pathname.startsWith("/api/kis")) {
      return fail("알 수 없는 경로입니다.", 404);
    }
    if (request.method !== "GET") {
      return fail("GET 요청만 지원합니다.", 405);
    }

    // 설정 확인 — health 는 설정이 없어도 상태를 알려준다
    let cfg;
    try {
      cfg = readConfig(env);
    } catch (e) {
      if (route === "health") {
        return json({ ok: false, configured: false, error: safeMessage(e, env) });
      }
      return fail(safeMessage(e, env), 503);
    }

    try {
      if (route === "health") {
        let tokenOk = true;
        let error = null;
        try {
          await getToken(cfg, env);
        } catch (e) {
          tokenOk = false;
          error = safeMessage(e, env);
        }
        // 저장 계층 상태도 함께 알려준다
        let db = { bound: !!env.KJC_DB, ready: false, error: null };
        if (env.KJC_DB) {
          try {
            Object.assign(db, { ready: true }, await dbStatus(env));
          } catch (e) {
            db.error = safeMessage(e, env);   // 테이블 미생성 등
          }
        } else {
          db.error = "D1 바인딩(KJC_DB)이 없습니다.";
        }

        return json({
          ok: tokenOk,
          configured: true,
          mode: cfg.mode,
          modeLabel: MODE_LABEL[cfg.mode],
          tokenOk,
          error,
          db,
          runtime: "workers",
        });
      }

      if (route === "stats") {
        // Workers 는 요청마다 격리되어 누적 통계를 들고 있지 않다.
        // 실제 호출량은 Cloudflare 대시보드의 Workers 분석에서 확인한다.
        return json({
          ok: true,
          data: {
            runtime: "workers",
            quoteCacheTtl: QUOTE_CACHE_TTL,
            quoteCacheTtlFast: QUOTE_CACHE_TTL_FAST,
            fastCodes: [...FAST_CODES],
            chartCacheTtl: CHART_CACHE_TTL,
            note: "호출량은 Cloudflare 대시보드 > Workers > 분석에서 확인하세요.",
          },
        });
      }

      if (route === "price") {
        const code = (url.searchParams.get("code") || "").trim();
        if (!/^\d{6}$/.test(code)) {
          return fail("code 는 6자리 숫자여야 합니다.", 400);
        }
        return json({ ok: true, data: await fetchPrice(cfg, env, code) });
      }

      if (route === "prices") {
        const raw = url.searchParams.get("codes") || "";
        const codes = [...new Set(
          raw.split(",").map((c) => c.trim()).filter((c) => /^\d{6}$/.test(c))
        )].slice(0, MAX_CODES);
        if (!codes.length) {
          return fail("codes 에 6자리 종목코드가 없습니다.", 400);
        }
        const { data, errors } = await fetchPrices(cfg, env, codes);
        return json({
          ok: true,
          data,
          errors: Object.keys(errors).length ? errors : null,
          meta: {
            requested: codes.length,
            cacheTtl: QUOTE_CACHE_TTL,
            cacheTtlFast: QUOTE_CACHE_TTL_FAST,
          },
        });
      }

      if (route === "db/init") {
        return json({ ok: true, data: await dbInit(env) });
      }

      if (route === "db/status") {
        return json({ ok: true, data: await dbStatus(env) });
      }

      if (route === "chart") {
        const code = (url.searchParams.get("code") || "").trim();
        if (!/^\d{6}$/.test(code)) {
          return fail("code 는 6자리 숫자여야 합니다.", 400);
        }
        const period = (url.searchParams.get("period") || "D").trim();
        if (!PERIODS[period]) {
          return fail(`period 는 ${Object.keys(PERIODS).join(", ")} 중 하나여야 합니다.`, 400);
        }
        const raw = url.searchParams.get("limit") || url.searchParams.get("days") || "240";
        const limit = Math.min(Math.max(parseInt(raw, 10) || 240, 1), 1000);

        const { rows, fetched, warn, source } = await getChart(cfg, env, code, period, limit);
        return json({
          ok: true,
          data: { code, period, candles: rows },
          // warn — 받아오다 일부 실패했으면 이유가 담긴다. 예전에는 조용히 삼켜서
          // 차트가 왜 비는지 알 수 없었다 (2026-09-14).
          meta: { count: rows.length, fetched, source, warn: warn || null,
                  label: PERIODS[period].label },
        });
      }

      if (route === "indices") {
        const withChart = url.searchParams.get("chart") !== "0";
        const { data, errors } = await fetchIndices(cfg, env, withChart);
        return json({
          ok: data.length > 0,
          data,
          errors: Object.keys(errors).length ? errors : null,
        });
      }

      return fail(`알 수 없는 경로입니다: ${route}`, 404);
    } catch (e) {
      // 예기치 못한 오류에도 앱키가 새지 않도록 메시지만 전달
      return fail(safeMessage(e, env), 502);
    }
  },
};
