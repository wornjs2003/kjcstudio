/**
 * KJC Holdings — 한국투자증권(KIS) 중계 서버 (Cloudflare Workers)
 *
 * 브라우저는 앱키를 절대 보지 못한다. 앱키는 Cloudflare Secret 으로만 존재하고,
 * 브라우저는 /api/kis/... 로 종목코드만 보낸다.
 *
 * 이 Worker 는 thekjcstudio.com/api/* 에 붙으므로 Cloudflare Access 뒤에 놓인다.
 * 즉 로그인한 사람만 호출할 수 있다.
 *
 * ── 필요한 설정 ────────────────────────────────────────────────
 *  Secret (암호화 저장, 대시보드에서 직접 입력)
 *    KIS_APP_KEY      발급받은 App Key
 *    KIS_APP_SECRET   발급받은 App Secret
 *  Variable (일반 변수)
 *    KIS_MODE         "prod" = 실전투자, "vts" = 모의투자
 *  KV 바인딩
 *    KIS_KV           접근토큰 보관용 (24시간)
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
const MARKET_DIV = "UN";

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
const QUOTE_CACHE_TTL = 10;
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
    throw new Error(`토큰 발급 실패 (HTTP ${res.status}): ${text.slice(0, 200)}`);
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

async function kisGet(cfg, env, path, params, trId, cacheTtl) {
  const token = await getToken(cfg, env);
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
    throw new Error(`KIS 호출 실패 (HTTP ${res.status}): ${text.slice(0, 200)}`);
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
    { FID_COND_MRKT_DIV_CODE: MARKET_DIV, FID_INPUT_ISCD: code },
    "FHKST01010100",
    QUOTE_CACHE_TTL
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
      errors[code] = String(e.message || e);
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
      errors[name] = String(e.message || e);
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
      FID_COND_MRKT_DIV_CODE: MARKET_DIV,
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
async function fetchMinutesFromKis(cfg, env, code, hour = "200000") {
  const data = await kisGet(
    cfg, env,
    "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
    {
      FID_ETC_CLS_CODE: "",
      FID_COND_MRKT_DIV_CODE: MARKET_DIV,
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
async function fetchMinutesDay(cfg, env, code) {
  const bars = new Map();
  for (let t = MINUTE_DAY_END; t >= MINUTE_DAY_START; t -= 30) {
    const hour = `${String(Math.floor(t / 60)).padStart(2, "0")}${String(t % 60).padStart(2, "0")}00`;
    try {
      for (const b of await fetchMinutesFromKis(cfg, env, code, hour)) bars.set(b.ts, b);
    } catch {
      // 해당 구간에 데이터가 없을 수 있다. 계속 진행.
    }
  }
  return [...bars.values()].sort((a, b) => a.ts.localeCompare(b.ts));
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
  if (!rows.length || stale) {
    let bars;
    if (conf.kis) {                       // 일/주/월/년
      bars = await fetchBarsFromKis(cfg, env, code, period, ymdOffset(conf.spanDays), ymd(new Date()));
    } else {                              // 분봉
      // 처음이면 하루치를 모으고, 이후에는 최근 구간만 갱신한다
      const raw = rows.length
        ? await fetchMinutesFromKis(cfg, env, code)
        : await fetchMinutesDay(cfg, env, code);
      bars = period === "5m" ? aggregateMinutes(raw, 5) : raw;
    }
    fetched = await saveCandles(env, code, period, bars);
    await metaSet(env, mkey, Date.now());
    if (fetched) rows = await readCandles(env, code, period, limit);
  }
  return { rows, fetched, source: fetched ? "KIS+DB" : "DB" };
}

/* ── 라우팅 ────────────────────────────────────────────────── */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const route = url.pathname.replace(/^\/api\/kis\/?/, "").replace(/\/$/, "");

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
        return json({ ok: false, configured: false, error: String(e.message || e) });
      }
      return fail(String(e.message || e), 503);
    }

    try {
      if (route === "health") {
        let tokenOk = true;
        let error = null;
        try {
          await getToken(cfg, env);
        } catch (e) {
          tokenOk = false;
          error = String(e.message || e);
        }
        // 저장 계층 상태도 함께 알려준다
        let db = { bound: !!env.KJC_DB, ready: false, error: null };
        if (env.KJC_DB) {
          try {
            Object.assign(db, { ready: true }, await dbStatus(env));
          } catch (e) {
            db.error = String(e.message || e);   // 테이블 미생성 등
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
          meta: { requested: codes.length, cacheTtl: QUOTE_CACHE_TTL },
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

        const { rows, fetched, source } = await getChart(cfg, env, code, period, limit);
        return json({
          ok: true,
          data: { code, period, candles: rows },
          meta: { count: rows.length, fetched, source, label: PERIODS[period].label },
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
      return fail(String(e.message || e), 502);
    }
  },
};
