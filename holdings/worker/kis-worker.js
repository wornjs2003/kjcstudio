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
 *   /api/kis/...   시세 · 지수 · 캔들 · 지수 당일 흐름 · 업종 · 순위 · 투자자 (한국투자증권)
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
/* 정규장 시각 (분). 시세 판정과 분봉 시장구분이 같이 쓴다 —
   두 곳에 숫자를 적어 두면 한쪽만 고쳐진다.
   server/kis_proxy.py 의 KRX_OPEN · KRX_CLOSE 와 같아야 한다. */
const KRX_OPEN_MIN = 9 * 60;              // 09:00
const KRX_CLOSE_MIN = 15 * 60 + 30;       // 15:30

function quoteMarketDiv(now = new Date()) {
  const kst = new Date(now.getTime() + 9 * 3600 * 1000);
  const day = kst.getUTCDay();                 // 0 일요일 · 6 토요일
  if (day === 0 || day === 6) return "UN";
  const mins = kst.getUTCHours() * 60 + kst.getUTCMinutes();
  return mins >= KRX_OPEN_MIN && mins < KRX_CLOSE_MIN ? "J" : "UN";
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
// ── 모든 종목이 같은 수명을 쓴다 (2026-09-18 지시) ──
//
// 재권님 말씀 — "삼성전자 하이닉스도 같은값이여야 할거같은데 모든값은 통일해야해".
// 전에는 그 둘만 4초, 나머지는 25초라 **같은 화면에서 종목마다 기준 시각이
// 달랐다.** 자세한 것은 server/kis_proxy.py 의 PRICE_CACHE_TTL 주석에 있다.
const QUOTE_CACHE_TTL = 25;                         // 모든 종목 · 지수 (화면 갱신 30초)

/* 지수·선물 캐시.

   화면이 1초마다 다시 받는다. 종목 시세 캐시(25초)를 함께 쓰고 있었는데
   그건 화면이 30초마다 묻던 시절 값이라, 새로 받아도 묵은 값이 나왔다.

   서버(server/kis_proxy.py)는 0.7 초다. 여기만 1 인 이유 —
   워커는 Cloudflare 엣지 캐시(cf.cacheTtl)를 쓰는데 공식 문서가 소수를
   받는지 밝히지 않았다 (2026-09-15 확인). 확인 못 한 값을 넣지 않는다.
   화면이 1초 주기라 1초면 충분하다. holdings/tools/check-kis-consts.py 가
   이 차이를 알고 비교한다. */
/* ── 워커 자체 캐시 ─────────────────────────────────────────

   엣지 캐시(cf.cacheTtl)에만 기대고 있었다. 그런데 Cloudflare 무료 요금제는
   엣지 캐시 최소 보관이 2시간이라, 여기서 주는 1초·60초·600초가 전부
   무시된다 (2026-09-15 확인). 캐시가 하나도 안 먹은 채로 돌았다.

   그래서 지수 응답 한 번에 KIS 를 11번 부르고(국내 3×2 + 해외 4 + 선물 1),
   kisPace 가 호출마다 200ms 를 강제하니 2.2초가 걸렸다. 화면은 1초마다
   부르므로 줄이 계속 밀렸다. "한 번 갱신되고 멈춘다" 가 이것이었다.

   로컬 서버(server/kis_proxy.py)는 처음부터 자기 메모리에 들고 있어서
   멀쩡했다. 같은 방식을 여기에도 둔다. Worker 는 isolate 가 사는 동안
   전역을 유지하므로 이것이 실제로 받아낸다.

   cf.cacheTtl 은 지우지 않는다. 엣지가 먹히는 환경에서는 그것대로 이득이고,
   안 먹혀도 이 캐시가 앞에서 받는다.                                       */

const _mem = new Map();

/* isolate 가 오래 살면 키가 쌓인다. 지수·해외처럼 키가 몇 개뿐이라 커질
   일은 없지만, 종목별 키가 섞여 들어올 때를 대비해 위쪽을 막아 둔다. */
const MEM_MAX = 500;

async function memo(key, ttlSec, make) {
  const now = Date.now();
  const hit = _mem.get(key);
  if (hit && now - hit.at < ttlSec * 1000) return hit.v;

  const v = await make();
  if (_mem.size >= MEM_MAX) {
    // 가장 오래 전에 넣은 것부터 버린다 (Map 은 넣은 순서를 지킨다)
    const oldest = _mem.keys().next().value;
    _mem.delete(oldest);
  }
  _mem.set(key, { at: now, v });
  return v;
}

/* 지수 추이(작은 꺾은선). 60일치 과거 일봉이라 하루에 한 번 바뀐다.
   1초마다 다시 받을 이유가 없다. server/kis_proxy.py 의 INDEX_CHART_TTL 과 같다. */
const SERIES_TTL = 600;

/* 지수 캐시 (2026-09-18 지시 — 5초).
   화면이 2초마다 부르는데 캐시가 그보다 짧으면 한 번도 안 맞는다.
   server/kis_proxy.py 의 INDEX_TTL 과 같아야 한다 — check-kis-consts.py 가 본다. */
const INDEX_TTL = 5;
const FUTURES_TTL = 1;

/* 캐시 수명. **모든 종목이 같다** (2026-09-18 지시). 위 주석 참고. */
function quoteCacheTtl() {
  return QUOTE_CACHE_TTL;
}
// 지수 일봉은 자주 바뀌지 않으므로 길게 캐시한다.
const CHART_CACHE_TTL = 600;
// 한 번에 조회할 수 있는 종목 수 상한 (과다 요청 방지)
const MAX_CODES = 40;

const INDEX_DEFS = [
  ["0001", "KOSPI"],
  ["1001", "KOSDAQ"],
  ["2001", "KOSPI200"],
  ["4001", "KRX100"],      // 2026-09-17 에 코드를 찾았다. 01xx 대역이 아니라 4xxx 다
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

// 값을 지울 최소 길이. 너무 짧은 것까지 지우면 (예: KIS_MODE = "prod")
// 멀쩡한 문구가 알아볼 수 없게 된다.
const MIN_SECRET_LEN = 8;

/* env 에 든 문자열 값 전부. 이름을 가려 받지 않는다.
   이름으로 골라내면 Secret 이 늘었을 때 그것만 빠진다. 실제로 로컬에서
   알림을 끄며 bot_token 을 _off_bot_token 으로 옮겨둔 적이 있는데,
   이름으로 찾는 방식이었다면 그 토큰은 안 가려졌다 (2026-09-14 확인).
   D1·KV 바인딩은 객체라 저절로 걸러진다. */
function envSecrets(env) {
  if (!env) return [];
  const out = [];
  for (const v of Object.values(env)) {
    if (typeof v === "string" && v.length >= MIN_SECRET_LEN) out.push(v);
  }
  // 긴 것부터 지운다. 짧은 값이 긴 값의 일부일 때 반쪽만 지워지는 것을 막는다.
  return out.sort((a, b) => b.length - a.length);
}

function scrub(text, env) {
  let s = String(text ?? "");
  s = s.replace(SECRET_QS, "$1<가림>");
  for (const v of envSecrets(env)) {
    if (s.includes(v)) s = s.split(v).join("<가림>");
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
  /* pace 는 이 요청 몫의 호출 간격 지킴이다. readConfig 가 요청마다 불리므로
     요청별로 하나씩 생긴다. 전역으로 두면 요청 사이를 넘나들며 멈춘다
     (위 makeKisPacer 설명 참조). */
  return { appKey, appSecret, mode, host: HOSTS[mode], pace: makeKisPacer() };
}

/* ── 접근토큰 (KV 에 24시간 보관) ───────────────────────────── */

/* KIS 가 거부한 토큰을 버린다 (2026-09-22 지시 — 「응 해줘」).
   server/kis_proxy.py 의 `_drop_token_cache` 와 **같은 판정**이어야 한다.

   **캐시가 「아직 안 만료」 라고 믿는데 KIS 는 거부하는 구간이 있다.**
   그 상태에서는 `getToken` 이 거부당한 토큰을 계속 돌려주어, 캐시가 스스로
   만료될 때까지 몇십 분이고 계속 실패한다 (2026-09-22 로컬 실측 —
   가장 오래된 토큰을 든 폴더 하나만 해외 지수 여덟이 전부 EGW00123 였고,
   같은 토큰으로 국내는 통했다).

   **지우는 대신 만료로 표시해 덮어쓴다** — 지우면 「없음」 과 「거부됨」 이
   구분되지 않는다. 로컬은 파일, 여기는 KV 라 저장소만 다르다. */
async function dropToken(cfg, env) {
  if (!env.KIS_KV) return;
  try {
    await env.KIS_KV.put(`token:${cfg.mode}`,
      JSON.stringify({ token: "", expiresAt: 0 }));
  } catch { /* 못 지워도 아래 재시도는 해 본다 */ }
}

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

/* ⚠️ 줄은 요청 하나 안에서만 세운다. 전역으로 두면 안 된다.

   전에는 _kisChain 을 모듈 전역에 두고 모든 요청이 그 사슬에 붙었다.
   위 설명대로 "한 요청 안의 순차 호출" 만 생각한 것인데, 전역이라 요청
   **사이**로도 넘어갔다. 그래서 이런 일이 생겼다.

     요청 A  타이머를 걸고 기다린다
     요청 A  응답 끝 → Workers 가 A 의 실행 환경을 정리 → 그 타이머도 사라짐
     요청 B  사슬을 기다린다 = 사라진 타이머를 기다린다 → 영원히 안 끝남

   Cloudflare 가 그 요청을 끊으며 로그에 이렇게 남겼다 (2026-09-16 원문).

     The Workers runtime canceled this request because it detected that
     your Worker's code had hung and would never generate a response.

   한 시간에 성공 1,203 · 오류 2,350 이었다. 혼자 부르면 8종목짜리도
   성공하고 겹칠 때만 멈춘 것이 증거였다 — 양이 아니라 동시성 문제다.

   그래서 페이서를 요청마다 새로 만든다. readConfig 가 요청마다 불리므로
   cfg 에 얹어 두면 그 요청 안에서만 줄을 선다. 요청끼리는 서로 기다리지
   않는다. KIS 초당 한도는 캐시(MULTI_CACHE_TTL 등)가 막는다.

   로컬(server/kis_proxy.py)은 한 프로세스라 전역 락이 맞다. 거기는 그대로 둔다. */
function makeKisPacer() {
  let chain = Promise.resolve();
  let lastAt = 0;
  return function pace() {
    const turn = chain.then(async () => {
      const wait = lastAt + KIS_MIN_INTERVAL_MS - Date.now();
      if (wait > 0) await new Promise((r) => setTimeout(r, wait));
      lastAt = Date.now();
    });
    chain = turn.catch(() => {});     // 한 번 실패해도 줄이 끊기지 않게
    return turn;
  };
}

/* KIS 응답에서 배열을 꺼낸다.

   `data.output || []` 로 쓰면 output 이 객체나 빈 문자열로 왔을 때
   for...of 가 "object is not iterable" 로 터지고, 그 요청 전체가 500 이
   된다. 한 종목이 이상해서 순위표와 지수가 통째로 비는 일이 생긴다
   (2026-09-15). 배열이 아니면 빈 배열로 친다. */
function outRows(data, key) {
  const v = data && data[key];
  return Array.isArray(v) ? v : [];
}

async function kisGet(cfg, env, path, params, trId, cacheTtl, _retry = 1) {
  const token = await getToken(cfg, env);
  /* 이 요청 몫의 페이서. 없으면(예전 경로로 불렸으면) 기다리지 않는다 —
     전역으로 물러서면 다시 요청 사이를 넘나들게 된다. */
  if (cfg && cfg.pace) await cfg.pace();
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
    /* **거부당한 토큰(EGW00123)은 버리고 한 번만 다시 받는다** (2026-09-22 지시).
       `_retry > 0` 한 번뿐이라 되풀이되지 않는다 — 다시 받아도 또 거부되면
       그때는 던진다. `kis_proxy.py` 의 EGW00201 이 도는 그 모양 그대로다. */
    if (text.includes("EGW00123") && _retry > 0) {
      await dropToken(cfg, env);
      return kisGet(cfg, env, path, params, trId, cacheTtl, _retry - 1);
    }
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
    if (data.msg_cd === "EGW00123" && _retry > 0) {
      await dropToken(cfg, env);
      return kisGet(cfg, env, path, params, trId, cacheTtl, _retry - 1);
    }
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
    /* **거래대금** (2026-09-22). `server/kis_proxy.py` 의 `fetch_price` 와
       같은 판정이어야 한다 — 한쪽만 넣으면 로컬과 배포본의 숫자가 갈린다.
       단위는 원이다 (`acml_tr_pbmn` = 누적 거래 대금). */
    value: num(o.acml_tr_pbmn),
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
  return memo(`index:${code}`, INDEX_TTL, () => fetchIndexLive(cfg, env, code));
}

async function fetchIndexLive(cfg, env, code) {
  const data = await kisGet(
    cfg, env,
    "/uapi/domestic-stock/v1/quotations/inquire-index-price",
    { FID_COND_MRKT_DIV_CODE: "U", FID_INPUT_ISCD: code },
    "FHPUP02100000",
    INDEX_TTL
  );
  const o = data.output || {};
  return {
    value: num(o.bstp_nmix_prpr),
    change: num(o.bstp_nmix_prdy_vrss),
    changePct: num(o.bstp_nmix_prdy_ctrt),

    /* 아래 둘은 이미 이 응답에 들어 있었는데 쓰지 않고 버리던 것이다.
       따로 부르지 않아도 되므로 호출이 늘지 않는다 (2026-09-15).
       server/kis_proxy.py 의 fetch_index 와 같은 이름으로 내보내야 한다. */
    up: num(o.ascn_issu_cnt),
    flat: num(o.stnr_issu_cnt),
    down: num(o.down_issu_cnt),
    upperLimit: num(o.uplm_issu_cnt),
    lowerLimit: num(o.lslm_issu_cnt),

    /* 연중 최고·최저. 52주가 아니라 '올해 들어' 기준이다 (dryy = during year). */
    yearHigh: num(o.dryy_bstp_nmix_hgpr),
    yearHighDate: String(o.dryy_bstp_nmix_hgpr_date || "").trim() || null,
    yearLow: num(o.dryy_bstp_nmix_lwpr),
    yearLowDate: String(o.dryy_bstp_nmix_lwpr_date || "").trim() || null,
  };
}

/* 날짜를 YYYYMMDD 로. **한국 날짜로 찍는다.**
 *
 * Workers 는 UTC 로 돈다. getFullYear 계열을 그냥 쓰면 KST 00:00~09:00 사이에
 * 하루 전 날짜가 나온다 — 로컬 서버(datetime.now(KST))와 갈린다.
 * 지금은 그 시간대에 장이 안 열려 결과가 같지만, 장중에 도는 자리가 하나
 * 붙으면 그때 깨진다. 위 quoteMarketDiv 가 쓰는 방법과 맞춘다 (2026-09-16).
 */
function ymd(d) {
  const kst = new Date(d.getTime() + 9 * 3600 * 1000);
  return `${kst.getUTCFullYear()}${String(kst.getUTCMonth() + 1).padStart(2, "0")}`
       + `${String(kst.getUTCDate()).padStart(2, "0")}`;
}

async function fetchIndexSeries(cfg, env, code, days = 60) {
  return memo(`series:${code}:${days}`, SERIES_TTL,
              () => fetchIndexSeriesLive(cfg, env, code, days));
}

async function fetchIndexSeriesLive(cfg, env, code, days = 60) {
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
  return outRows(data, "output2")
    .filter((r) => r.stck_bsop_date && num(r.bstp_nmix_prpr) != null)
    .sort((a, b) => String(a.stck_bsop_date).localeCompare(String(b.stck_bsop_date)))
    .map((r) => num(r.bstp_nmix_prpr))
    .slice(-days);
}

/* 지수 당일 흐름 (5분 간격).

   FID_INPUT_HOUR_1 은 시각이 아니라 **초 단위 간격**이다. 여기서 한참 헤맸다.
   "150000"(15시) 처럼 시각을 넣으면 날짜별 요약이 돌아오고,
   "300"(300초=5분)을 넣으면 09:00~15:30 하루치가 99건으로 온다.
   (2026-09-14 직접 호출해 확인. 공식 문서에는 값이 적혀 있지 않았다)

   한 번에 101건까지 온다. 5분 간격이면 505분이라 정규장(390분)을 다 덮는다.
   로컬(server/kis_proxy.py)의 fetch_index_minutes 와 같은 값을 써야 한다. */
const INDEX_MINUTE_STEP = "300";      // 5분
const INDEX_MINUTE_TTL = 30;          // 장중에는 계속 바뀌므로 짧게

/* 지수 5분봉. **받아둔 것을 D1 에 쌓아 며칠치를 들고 있는다** (2026-09-16 지시).

   KIS 는 한 번에 100건쯤 준다. 그것만 쓰면 하루 조금 넘는 분량이라
   200일선이 안 그려지고, 워커가 새로 뜨면 그만큼으로 되돌아간다.
   받은 것을 버리지 않고 합치면 날이 갈수록 쌓인다. **호출은 안 늘어난다** —
   지금도 부르고 있고, 그 결과를 저장만 하는 것이다. */
async function fetchIndexMinutes(cfg, env, code) {
  await dbInit(env);
  const keep = INDEX_KEEP["5m"];
  let rows = await readCandles(env, code, "5m", keep);

  const mkey = `idx:${code}:5m`;
  const stale = (Date.now() / 1000 - Number((await metaGet(env, mkey)) || 0)) > INDEX_MINUTE_TTL;
  if (rows.length && !stale) return rows;

  const bars = await fetchIndexMinutesLive(cfg, env, code);
  if (bars.length) {
    await saveCandles(env, code, "5m", bars);
    rows = await readCandles(env, code, "5m", keep);
  }
  await metaSet(env, mkey, Date.now() / 1000);
  return rows;
}

async function fetchIndexMinutesLive(cfg, env, code) {
  const data = await kisGet(
    cfg, env,
    "/uapi/domestic-stock/v1/quotations/inquire-time-indexchartprice",
    {
      FID_COND_MRKT_DIV_CODE: "U",
      FID_INPUT_ISCD: code,
      FID_INPUT_HOUR_1: INDEX_MINUTE_STEP,
      FID_PW_DATA_INCU_YN: "Y",
      FID_ETC_CLS_CODE: "0",
    },
    "FHKUP03500200",
    INDEX_MINUTE_TTL
  );

  const bars = [];
  for (const r of outRows(data, "output2")) {
    const hhmmss = String(r.stck_cntg_hour || "").trim();
    // 888888 · 999999 는 시각이 아니라 요약 표시다. 버린다.
    if (!/^\d+$/.test(hhmmss) || hhmmss === "888888" || hhmmss === "999999") continue;
    const close = num(r.bstp_nmix_prpr);
    if (close == null) continue;
    bars.push({
      ts: String(r.stck_bsop_date || "") + hhmmss.slice(0, 4),
      open: num(r.bstp_nmix_oprc),
      high: num(r.bstp_nmix_hgpr),
      low: num(r.bstp_nmix_lwpr),
      close,
      volume: 0,          // 지수 분봉에는 거래량이 없다. 표가 요구해서 채운다
    });
  }
  bars.sort((a, b) => a.ts.localeCompare(b.ts));
  return bars;
}

/* ── 해외 지수·환율 ──────────────────────────────────────────────────
   국내 계약으로도 받아진다 (2026-09-15 직접 호출해 확인).
   docs/data-sources.md 의 "KIS 국내 계약으로는 해외를 못 받는다" 는 사실과 다르다.

     시장구분 N = 해외지수 · X = 환율

   다우존스는 코드를 못 찾았다. DJI · .DJI · DJIA 를 네 가지 시장구분으로
   시도했지만 전부 0 이다 (DOW 는 다우社 주식이라 28원이 나온다).
   WTI·금은 해외선물 쪽을 따로 봐야 한다.

   server/kis_proxy.py 의 fetch_overseas 와 같은 모양으로 돌려줘야 한다. */
/* 2026-09-17 에 약 70개 심볼을 네 시장구분으로 훑어 받아지는 것만 남겼다.
   **KIS 해외지수 목록에 몇 개만 들어 있다** — 다우 · 닛케이 · 상해 · FTSE ·
   DAX · 항셍 · 대만 · 인도는 전부 0 이다. 아시아라서가 아니다(홍콩H·유로는 된다).
   server/kis_proxy.py 의 OVERSEAS_DEFS 와 같아야 한다. */
const OVERSEAS_DEFS = [
  ["USDKRW", "X", "FX@KRW", "미국 USD",   "원"],
  ["SPX",    "N", "SPX",    "S&P 500",    "pt"],
  ["NASDAQ", "N", "COMP",   "나스닥 종합",  "pt"],
  ["NDX",    "N", "NDX",    "나스닥100",   "pt"],
  ["SOX",    "N", "SOX",    "필라델피아 반도체", "pt"],
  ["SX5E",   "N", "SX5E",   "유로STOXX50", "pt"],
  ["HSCE",   "N", "HSCE",   "홍콩H",       "pt"],
  ["VIX",    "N", "VIX",    "VIX",        "pt"],
];
const OVERSEAS_TTL = 60;      // 해외장은 국내 장중에 거의 멈춰 있다

/* ── 지수 캔들 ───────────────────────────────────────────────────────
   첫 화면 큰 차트가 쓴다. 5분봉은 fetchIndexMinutes 가 맡고, 일·주·월·년봉은
   여기서 받는다. 네 기간 모두 시·고·저·종이 온다 (2026-09-15 확인).
   server/kis_proxy.py 의 fetch_index_candles 와 같은 모양이어야 한다. */
const INDEX_PERIODS = { D: "일", W: "주", M: "월", Y: "년" };

/* 봉마다 얼마나 받아 두는가 (2026-09-16 지시).

   200일 이동평균을 그리려면 봉이 200개 넘게 있어야 한다. 그런데 KIS 는
   **한 번에 50개까지만** 준다 — 400일을 달라고 해도 50개다 (실측).
   그래서 구간을 뒤로 밀어가며 여러 번 받아 채운다.

       일  300개  약 1년 3개월
       주  260개  약 5년
       월  250개  약 21년
       년   40개  1993년부터가 34개뿐이다. **MA200 을 못 그린다** —
                  자료가 없는 것이지 덜 받는 것이 아니다. 화면이 그렇게 적는다 */
const INDEX_KEEP = { "5m": 400, D: 300, W: 260, M: 250, Y: 40 };
//                    ↑ 5분봉은 하루 78봉이라 400개면 약 닷새다 (2026-09-16 지시)

// 한 번에 오는 개수 (KIS 제한, 2026-09-16 실측)
const INDEX_PAGE = 50;

// 나눠 받을 때 최대 몇 번까지. 끝없이 도는 것을 막는다
const INDEX_PAGES = 8;

// 얼마나 지나면 다시 받나. 과거 봉은 변하지 않으므로 오늘 것만 새로 온다
const INDEX_FRESH = { D: 60, W: 300, M: 600, Y: 3600 };

// 한 번 부를 때 훑는 기간. 어차피 50개만 오지만, 좁으면 그보다 적게 온다
const INDEX_SPAN_DAYS = { D: 400, W: 1500, M: 4000, Y: 12000 };

/* 한 구간을 받아 온다. 최대 INDEX_PAGE 개. */
async function indexBarsFromKis(cfg, env, code, period, from, to) {
  const data = await kisGet(
    cfg, env,
    "/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice",
    {
      FID_COND_MRKT_DIV_CODE: "U", FID_INPUT_ISCD: code,
      FID_INPUT_DATE_1: ymd(from), FID_INPUT_DATE_2: ymd(to),
      FID_PERIOD_DIV_CODE: period,
    },
    "FHKUP03500100"
  );
  const out = [];
  for (const r of outRows(data, "output2")) {
    const day = String(r.stck_bsop_date || "").trim();
    const close = num(r.bstp_nmix_prpr);
    if (!day || close == null) continue;
    out.push({
      ts: day,
      open: num(r.bstp_nmix_oprc),
      high: num(r.bstp_nmix_hgpr),
      low: num(r.bstp_nmix_lwpr),
      close,
      volume: num(r.acml_vol) || 0,
    });
  }
  out.sort((a, b) => a.ts.localeCompare(b.ts));
  return out;
}

/* 구간을 뒤로 밀어가며 want 개가 모일 때까지 받는다. */
async function indexBackfill(cfg, env, code, period, want) {
  const span = INDEX_SPAN_DAYS[period] * 86400000;
  const got = new Map();
  let to = new Date();
  for (let i = 0; i < INDEX_PAGES; i++) {
    const bars = await indexBarsFromKis(cfg, env, code, period, new Date(to.getTime() - span), to);
    if (!bars.length) break;                    // 더 옛날 자료가 없다
    for (const b of bars) got.set(b.ts, b);
    if (got.size >= want) break;
    const oldest = bars[0].ts;                  // 오름차순이라 첫 개가 가장 옛것
    to = new Date(Date.UTC(+oldest.slice(0, 4), +oldest.slice(4, 6) - 1, +oldest.slice(6, 8)) - 86400000);
  }
  return [...got.values()].sort((a, b) => a.ts.localeCompare(b.ts));
}

/* 지수 봉. **받아둔 것을 D1 에서 읽고, 모자라거나 묵었을 때만 부른다.**

   전에는 메모리 캐시 5분짜리만 있어서 워커가 새로 뜨면 사라졌고, 매번
   새로 받은 50개로 그렸다. 그래서 MA60 부터 조용히 빠졌다 (2026-09-16).

   종목 봉이 쓰는 candles 표를 그대로 쓴다. 지수 코드(0001)는 네 자리라
   종목코드 여섯 자리와 겹치지 않는다. */
async function fetchIndexCandles(cfg, env, code, period) {
  await dbInit(env);
  const want = INDEX_KEEP[period];
  let rows = await readCandles(env, code, period, want);

  const mkey = `idx:${code}:${period}`;
  const stale = (Date.now() / 1000 - Number((await metaGet(env, mkey)) || 0)) > INDEX_FRESH[period];
  if (rows.length >= want && !stale) return rows;

  let bars;
  if (rows.length < want) {
    bars = await indexBackfill(cfg, env, code, period, want);   // 처음이거나 모자라다
  } else {
    const now = new Date();
    const span = INDEX_SPAN_DAYS[period] * 86400000;
    bars = await indexBarsFromKis(cfg, env, code, period, new Date(now.getTime() - span), now);
  }

  if (bars.length) {
    await saveCandles(env, code, period, bars);
    rows = await readCandles(env, code, period, want);
  }
  await metaSet(env, mkey, Date.now() / 1000);
  return rows;
}

/* ── 코스피200 선물 ──────────────────────────────────────────────────
   종목코드 "10100000" 이 최근월물을 가리킨다. 응답의 hts_kor_isnm 에
   "F 202612" 처럼 어느 월물인지 적혀 온다.

   101W09 · 101U6000 같은 월물 표기는 전부 output1(선물 자리)이 비어 오고
   output2(기초자산 = 코스피 지수)만 돌아온다. 8자리가 맞다 (2026-09-15 확인).
   server/kis_proxy.py 의 fetch_futures 와 같은 모양으로 돌려줘야 한다. */
const FUTURES_CODE = "10100000";

async function fetchFutures(cfg, env) {
  return memo("futures", FUTURES_TTL, () => fetchFuturesLive(cfg, env));
}

async function fetchFuturesLive(cfg, env) {
  let data;
  try {
    data = await kisGet(
      cfg, env,
      "/uapi/domestic-futureoption/v1/quotations/inquire-price",
      { FID_COND_MRKT_DIV_CODE: "F", FID_INPUT_ISCD: FUTURES_CODE },
      "FHMIF10000000",
      FUTURES_TTL
    );
  } catch {
    return null;         // 못 받으면 그 칸만 비운다
  }
  const o = data.output1 || {};
  const price = num(o.futs_prpr);
  if (price == null) return null;
  return {
    name: String(o.hts_kor_isnm || "").trim(),
    price,
    change: num(o.futs_prdy_vrss),
    changePct: num(o.futs_prdy_ctrt),
    volume: num(o.acml_vol),
    source: "KIS",
  };
}

async function fetchOverseas(cfg, env) {
  return memo("overseas", OVERSEAS_TTL, () => fetchOverseasLive(cfg, env));
}

async function fetchOverseasLive(cfg, env) {
  const out = [];
  const errors = {};
  const now = new Date();
  const to = ymd(now);
  const from = ymd(new Date(now.getTime() - 100 * 86400000));

  for (const [key, div, code, name, unit] of OVERSEAS_DEFS) {
    try {
      /* 기간을 넓게 잡아 현재값(output1)과 추이(output2)를 한 번에 받는다 */
      const data = await kisGet(
        cfg, env,
        "/uapi/overseas-price/v1/quotations/inquire-daily-chartprice",
        {
          FID_COND_MRKT_DIV_CODE: div, FID_INPUT_ISCD: code,
          FID_INPUT_DATE_1: from, FID_INPUT_DATE_2: to,
          FID_PERIOD_DIV_CODE: "D",
        },
        "FHKST03030100",
        OVERSEAS_TTL
      );
      const o = data.output1 || {};
      const value = num(o.ovrs_nmix_prpr);
      if (value == null || value === 0) {
        errors[key] = "값이 오지 않았습니다";
        continue;
      }
      const series = outRows(data, "output2")
        .slice()
        .sort((a, b) => String(a.stck_bsop_date || "").localeCompare(String(b.stck_bsop_date || "")))
        .map((r) => num(r.ovrs_nmix_prpr))
        .filter((v) => v)
        .slice(-60);

      /* 언제 기준 값인지. 해외장은 국내 낮 시간에 닫혀 있어서, 이것을 안 적으면
         어제 종가를 실시간인 줄 알게 된다 (2026-09-15 지적). */
      const last = outRows(data, "output2")
        .map((r) => String(r.stck_bsop_date || ""))
        .filter(Boolean)
        .sort()
        .pop() || null;

      out.push({
        code: key, name, unit, value,
        asOf: last, market: "overseas",
        change: num(o.ovrs_nmix_prdy_vrss),
        changePct: num(o.prdy_ctrt),
        series,
        source: "KIS",
      });
    } catch (e) {
      errors[key] = safeMessage(e, env);
    }
  }
  return { data: out, errors };
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


/* 빈 문자열을 0 이 아니라 null 로 본다.

   워커의 num("") 은 Number("") === 0 이라 **0 을 돌려준다.** 파이썬 쪽
   _num("") 은 None 이다. 업종의 acml_tr_pbmn_rlim 처럼 KIS 가 빈 값을 주는
   칸이 있어서, 그대로 두면 로컬은 「값 없음」 인데 배포본은 「0.00%」 로
   보인다. 2026-09-17 에 워커를 Node 로 돌려 서버 응답과 맞춰보다 찾았다.   */
function numOrNull(v) {
  return String(v ?? "").trim() === "" ? null : num(v);
}

/* ── 업종 · 순위 · 투자자 ────────────────────────────────────

   첫 화면의 「지금 뜨는 산업」 과 「외국인 · 기관 매매」 두 칸이 쓴다.
   server/kis_proxy.py 의 같은 이름 함수와 **한 쌍**이다. 한쪽만 고치면
   로컬과 배포본의 숫자가 갈린다 — holdings/tools/check-kis-consts.py 가 대조한다.

   응답 필드와 실제 값은 docs/kis-sector-investor.md 에 있다.              */

// (KIS 시장구분, 우리가 쓰는 이름, 업종 기준 지수코드, 순위 API 의 종목코드)
const SECTOR_MARKETS = [
  ["K", "KOSPI", "0001", "0001"],
  ["Q", "KOSDAQ", "1001", "1001"],
];

// FID_BLNG_CLS_CODE. 3 이 업종(산업별)이다. 0(전체) 은 파생지수까지 섞여 온다
const SECTOR_BLNG = "3";

// blng=3 인데도 업종이 아닌 것이 코스피 쪽에 둘 섞여 온다 (2026-09-17 실측)
const SECTOR_SKIP = ["0244", "2283"];

const SECTOR_TTL = 60;
const MOVERS_TTL = 30;
const MOVERS_MAX = 30;          // KIS 가 한 번에 주는 행 수
const INVESTOR_TOP_TTL = 120;
const INVESTOR_FLOW_TTL = 600;
const INVESTOR_FLOW_DAYS = 30;

/* KIS 는 등락률을 양수로 주고 부호를 따로 준다 — 1상한 2상승 3보합 4하한 5하락 */
function signPct(row, key, value) {
  if (value === null || value === undefined) return null;
  const sign = String(row[key] ?? "").trim();
  return (sign === "4" || sign === "5") && value > 0 ? -value : value;
}

async function fetchSectors(cfg, env, markets) {
  const want = SECTOR_MARKETS.filter(([, name]) => !markets || markets.includes(name));
  const out = [];
  const errors = {};
  for (const [mrkt, name, iscd] of want) {
    try {
      const rows = await memo(`SECTOR:${name}`, SECTOR_TTL, async () => {
        const data = await kisGet(
          cfg, env,
          "/uapi/domestic-stock/v1/quotations/inquire-index-category-price",
          { FID_COND_MRKT_DIV_CODE: "U", FID_INPUT_ISCD: iscd,
            FID_COND_SCR_DIV_CODE: "20214", FID_MRKT_CLS_CODE: mrkt,
            FID_BLNG_CLS_CODE: SECTOR_BLNG },
          "FHPUP02140000", SECTOR_TTL,
        );
        return outRows(data, "output2")
          .filter((r) => {
            const code = String(r.bstp_cls_code || "").trim();
            return code && !SECTOR_SKIP.includes(code);
          })
          .map((r) => ({
            code: String(r.bstp_cls_code).trim(),
            name: String(r.hts_kor_isnm || "").trim(),
            market: name,
            price: numOrNull(r.bstp_nmix_prpr),
            amt: signPct(r, "prdy_vrss_sign", numOrNull(r.bstp_nmix_prdy_vrss)),
            pct: signPct(r, "prdy_vrss_sign", numOrNull(r.bstp_nmix_prdy_ctrt)),
            volume: numOrNull(r.acml_vol),
            value: numOrNull(r.acml_tr_pbmn),
            volShare: numOrNull(r.acml_vol_rlim),
            valueShare: numOrNull(r.acml_tr_pbmn_rlim),
            source: "KIS",
          }));
      });
      out.push(...rows);
    } catch (e) {
      errors[name] = safeMessage(e, env);
    }
  }
  return { data: out, errors };
}

async function fetchMovers(cfg, env, direction = "up", market = "all", limit = MOVERS_MAX) {
  const iscd = market && market !== "all"
    ? (SECTOR_MARKETS.find(([, n]) => n === market) || [])[3] || "0000"
    : "0000";
  const sort = direction === "down" ? "1" : "0";
  const rows = await memo(`MOVERS:${sort}:${iscd}`, MOVERS_TTL, async () => {
    const data = await kisGet(
      cfg, env,
      "/uapi/domestic-stock/v1/ranking/fluctuation",
      // fid_prc_cls_code 0 은 저가대비, 1 은 전일종가대비다. 0 으로 두면
      // 등락률이 마이너스인 종목이 1위로 온다 (2026-09-17 실측). 1 이 맞다.
      { fid_cond_mrkt_div_code: "J", fid_cond_scr_div_code: "20170",
        fid_input_iscd: iscd, fid_rank_sort_cls_code: sort,
        fid_input_cnt_1: "0", fid_prc_cls_code: "1",
        fid_input_price_1: "", fid_input_price_2: "", fid_vol_cnt: "",
        fid_trgt_cls_code: "0", fid_trgt_exls_cls_code: "0",
        fid_div_cls_code: "0", fid_rsfl_rate1: "", fid_rsfl_rate2: "" },
      "FHPST01700000", MOVERS_TTL,
    );
    return outRows(data, "output")
      .filter((r) => String(r.stck_shrn_iscd || "").trim())
      .map((r) => ({
        code: String(r.stck_shrn_iscd).trim(),
        name: String(r.hts_kor_isnm || "").trim(),
        rank: numOrNull(r.data_rank),
        price: numOrNull(r.stck_prpr),
        amt: signPct(r, "prdy_vrss_sign", numOrNull(r.prdy_vrss)),
        pct: signPct(r, "prdy_vrss_sign", numOrNull(r.prdy_ctrt)),
        volume: numOrNull(r.acml_vol),
        high: numOrNull(r.stck_hgpr),
        low: numOrNull(r.stck_lwpr),
        source: "KIS",
      }));
  });
  return rows.slice(0, Math.max(1, Math.min(limit, MOVERS_MAX)));
}

function investorSide(r, prefix) {
  return { qty: numOrNull(r[`${prefix}_ntby_qty`]), amt: numOrNull(r[`${prefix}_ntby_tr_pbmn`]) };
}

/* 시장 전체의 개인 · 외국인 · 기관 일별 순매수.

   FID_INPUT_DATE_1 이 **가장 최근 날짜**이고 거기서 과거로 300영업일이
   한 번에 온다 (2026-09-17 실측). 30일치도 호출 한 번이다.
   KIS 는 최근 → 과거 순으로 주는데, 추이선은 왼쪽이 과거여야 해서
   여기서 뒤집어 돌려준다.                                                */
async function fetchInvestorFlow(cfg, env, market = "KOSPI", days = INVESTOR_FLOW_DAYS) {
  const iscd1 = market === "KOSDAQ" ? "KSQ" : "KSP";
  const iscd = market === "KOSDAQ" ? "1001" : "0001";
  const rows = await memo(`INVFLOW:${market}`, INVESTOR_FLOW_TTL, async () => {
    const today = ymd(new Date());
    const data = await kisGet(
      cfg, env,
      "/uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market",
      { FID_COND_MRKT_DIV_CODE: "U", FID_INPUT_ISCD: iscd,
        FID_INPUT_DATE_1: today, FID_INPUT_ISCD_1: iscd1,
        FID_INPUT_DATE_2: today, FID_INPUT_ISCD_2: iscd },
      "FHPTJ04040000", INVESTOR_FLOW_TTL,
    );
    const list = outRows(data, "output")
      .filter((r) => String(r.stck_bsop_date || "").trim().length === 8)
      .map((r) => {
        const d = String(r.stck_bsop_date).trim();
        return {
          date: `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6)}`,
          index: numOrNull(r.bstp_nmix_prpr),
          indexAmt: signPct(r, "prdy_vrss_sign", numOrNull(r.bstp_nmix_prdy_vrss)),
          indexPct: signPct(r, "prdy_vrss_sign", numOrNull(r.bstp_nmix_prdy_ctrt)),
          retail: investorSide(r, "prsn"),
          foreign: investorSide(r, "frgn"),
          inst: investorSide(r, "orgn"),
          source: "KIS",
        };
      });
    list.reverse();                      // 과거 → 최근
    return list;
  });
  const want = Math.max(1, Math.min(days, rows.length));
  return rows.slice(rows.length - want);
}

/* 외국인 · 기관 순매수(순매도) 상위.

   ⚠️ **가집계다.** KIS 공식 설명에 "증권사 직원이 장중에 집계/입력한 자료를
   단순 누계한 수치" 라고 적혀 있다. 입력 시각은 외국인 09:30·11:20·13:20·14:30,
   기관 10:00·11:20·13:20·14:30 (±10분). 마감 뒤 확정치와 다를 수 있다.     */
/* ── 종목별 투자자 · 호가 (2026-09-18 지시) ────────────────────────
 *
 * server/kis_proxy.py 의 fetch_investor · fetch_asking 과 **같은 판정**이어야
 * 한다. 필드 이름과 계산을 그대로 맞춰 두었다.
 *
 * 아래 investor-top 과 다르다 — 그쪽은 「상위 목록」이고 가집계이며,
 * 이쪽은 「지금 보고 있는 이 종목」이고 확정치다. */
const INVESTOR_DAYS = 30;       // 한 번에 오는 일수. 늘릴 수 없다
const ASKING_LEVELS = 10;       // 호가 단계
const INVESTOR_TTL = 60;        // 일별 자료라 장중에 한 번 바뀐다
const ASKING_TTL = 3;           // 호가는 계속 움직인다
const TICKS_TTL = 3;            // 체결도 계속 쌓인다. server/kis_proxy.py 와 같아야 한다

async function fetchInvestor(cfg, env, code, days = INVESTOR_DAYS) {
  const data = await kisGet(
    cfg, env,
    "/uapi/domestic-stock/v1/quotations/inquire-investor",
    { FID_COND_MRKT_DIV_CODE: "J", FID_INPUT_ISCD: code },
    "FHKST01010900",
    INVESTOR_TTL
  );
  const rows = outRows(data, "output").slice(0, days);
  return rows.map((r) => {
    const side = (p) => ({
      net: num(r[`${p}_ntby_qty`]),
      netAmt: num(r[`${p}_ntby_tr_pbmn`]),
      buy: num(r[`${p}_shnu_vol`]),
      sell: num(r[`${p}_seln_vol`]),
    });
    return {
      date: r.stck_bsop_date,
      close: num(r.stck_clpr),
      amt: num(r.prdy_vrss),
      person: side("prsn"),
      foreign: side("frgn"),
      inst: side("orgn"),
    };
  });
}

/* ── 종목별 장중 추정가집계 (2026-09-22 지시) ──────────────────────
 *
 * server/kis_proxy.py 의 fetch_investor_estimate() 와 **같은 판정**이어야 한다.
 * 한쪽만 고치면 로컬과 배포본의 숫자가 갈린다.
 *
 * 위 fetchInvestor 는 장중에 오늘 줄을 net: null 로 준다. 네이버는 대안이
 * 못 된다 — 경로 셋이 전부 어제까지다 (2026-09-22 실측).
 *
 * ⚠️ **가집계다.** 마감 뒤 숫자가 달라진다. 화면에 그대로 적는다.
 * ⚠️ **개인이 없다.** 응답 필드가 외국인·기관·합계 셋뿐이다.
 *
 * `bsop_hour_gb` 는 **회차 번호**다 — 큰 것이 최신. 응답에 시각은 없다. */
const INVESTOR_EST_TTL = 60;    // 하루 네 번만 바뀐다

async function fetchInvestorEstimate(cfg, env, code) {
  const data = await kisGet(
    cfg, env,
    "/uapi/domestic-stock/v1/quotations/investor-trend-estimate",
    { MKSC_SHRN_ISCD: code },
    "HHPTJ04160200",
    INVESTOR_EST_TTL
  );
  const rows = outRows(data, "output2").map((r) => ({
    seq: num(r.bsop_hour_gb),
    foreign: num(r.frgn_fake_ntby_qty),
    inst: num(r.orgn_fake_ntby_qty),
    sum: num(r.sum_fake_ntby_qty),
  }));
  /* **최신이 앞에 오게 한다.** 화면은 첫 줄만 쓴다 */
  rows.sort((a, b) => (b.seq ?? -1) - (a.seq ?? -1));
  return { latest: rows[0] || null, rows };
}

/* 최근 체결 30줄. **한 번에 30줄이 오고 그게 전부다** — 더 과거는 안 준다.
   server/kis_proxy.py 의 fetch_ticks() 와 같은 판정이어야 한다. */
async function fetchTicks(cfg, env, code) {
  const data = await kisGet(
    cfg, env,
    "/uapi/domestic-stock/v1/quotations/inquire-ccnl",
    { FID_COND_MRKT_DIV_CODE: quoteMarketDiv(), FID_INPUT_ISCD: code },
    "FHKST01010300",
    TICKS_TTL
  );
  const out = (data.output || []).map((o) => {
    const t = String(o.stck_cntg_hour || "").trim();
    return {
      /* 091646 → 09:16:46. 화면에서 자르지 않게 여기서 넣는다 */
      at: t.length === 6 ? `${t.slice(0, 2)}:${t.slice(2, 4)}:${t.slice(4, 6)}` : t,
      price: num(o.stck_prpr),
      volume: num(o.cntg_vol),
      diff: num(o.prdy_vrss),
      pct: num(o.prdy_ctrt),
      /* 1 상한 · 2 상승 · 3 보합 · 4 하한 · 5 하락 (KIS 공통) */
      dir: String(o.prdy_vrss_sign || "3").trim(),
    };
  });
  /* 체결강도. 100 이 기준이고 넘으면 산 쪽이 세다. 줄마다 같은 값이 온다 */
  const power = num((data.output || [{}])[0].tday_rltv);
  return { rows: out, power };
}

async function fetchAsking(cfg, env, code) {
  const data = await kisGet(
    cfg, env,
    "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
    { FID_COND_MRKT_DIV_CODE: "J", FID_INPUT_ISCD: code },
    "FHKST01010200",
    ASKING_TTL
  );
  const o = data.output1 || {};
  const ask = [];
  const bid = [];
  for (let i = 1; i <= ASKING_LEVELS; i++) {
    ask.push({ price: num(o[`askp${i}`]), qty: num(o[`askp_rsqn${i}`]) });
    bid.push({ price: num(o[`bidp${i}`]), qty: num(o[`bidp_rsqn${i}`]) });
  }
  const totAsk = num(o.total_askp_rsqn) || 0;
  const totBid = num(o.total_bidp_rsqn) || 0;
  const both = totAsk + totBid;
  return {
    ask: { total: totAsk, levels: ask },
    bid: { total: totBid, levels: bid },
    /* 사자 비중. 50 보다 크면 사려는 주문이 더 쌓여 있다는 뜻이다 */
    buyPct: both ? Math.round((totBid / both) * 1000) / 10 : null,
  };
}

async function fetchInvestorTop(cfg, env, direction = "buy", market = "all",
                                by = "qty", limit = 10) {
  const iscd = market && market !== "all"
    ? (SECTOR_MARKETS.find(([, n]) => n === market) || [])[3] || "0000"
    : "0000";
  const sort = direction === "sell" ? "1" : "0";     // 0 순매수상위 · 1 순매도상위
  const div = by === "amt" ? "1" : "0";              // 0 수량정렬 · 1 금액정렬
  const out = {};
  const errors = {};
  // FID_ETC_CLS_CODE — 0 전체 · 1 외국인 · 2 기관계 · 3 기타
  for (const [who, etc] of [["foreign", "1"], ["inst", "2"]]) {
    try {
      const rows = await memo(`INVTOP:${who}:${sort}:${div}:${iscd}`, INVESTOR_TOP_TTL, async () => {
        const data = await kisGet(
          cfg, env,
          "/uapi/domestic-stock/v1/quotations/foreign-institution-total",
          { FID_COND_MRKT_DIV_CODE: "V", FID_COND_SCR_DIV_CODE: "16449",
            FID_INPUT_ISCD: iscd, FID_DIV_CLS_CODE: div,
            FID_RANK_SORT_CLS_CODE: sort, FID_ETC_CLS_CODE: etc },
          "FHPTJ04400000", INVESTOR_TOP_TTL,
        );
        return outRows(data, "output")
          .filter((r) => String(r.mksc_shrn_iscd || "").trim())
          .map((r) => ({
            code: String(r.mksc_shrn_iscd).trim(),
            name: String(r.hts_kor_isnm || "").trim(),
            price: numOrNull(r.stck_prpr),
            amt: signPct(r, "prdy_vrss_sign", numOrNull(r.prdy_vrss)),
            pct: signPct(r, "prdy_vrss_sign", numOrNull(r.prdy_ctrt)),
            volume: numOrNull(r.acml_vol),
            // net — 이 줄이 무엇으로 줄 세워졌는지에 해당하는 값
            net: investorSide(r, who === "foreign" ? "frgn" : "orgn"),
            foreign: investorSide(r, "frgn"),
            inst: investorSide(r, "orgn"),
            source: "KIS",
          }));
      });
      out[who] = rows.slice(0, Math.max(1, Math.min(limit, MOVERS_MAX)));
    } catch (e) {
      errors[who] = safeMessage(e, env);
    }
  }
  return { data: out, errors };
}

/* ── 뉴스 ───────────────────────────────────────────────────

   두 갈래를 따로 받는다. 성격이 달라 섞으면 둘 다 안 읽힌다.

     시장 이슈    구글 뉴스 RSS · 주제어마다 한 번씩
                  반도체·유가·금리처럼 주가에 영향을 주는 것. 원문 링크가 있다
     종목 움직임  KIS news-title · 시장구분 01(코스피) 02(코스닥)
                  지금 움직이는 종목. 링크는 없지만 종목코드가 정확히 붙어 온다

   왜 나눴는지는 server/news.py 머리말에 자세히 적혀 있다.

   ★ 아래 NEWS_TOPICS 는 data/news-topics.json 의 복제다.
     워커는 대시보드에 코드만 붙여넣는 방식이라 파일을 같이 올릴 수 없다.
     합칠 수 없는 복제이므로 holdings/tools/check-news-topics.py 가 대조한다.
     주제를 늘릴 때는 JSON 과 여기를 함께 고친다.                          */

const NEWS_TOPICS = [
  { id: "semi", color: "indigo", label: "반도체",
    keywords: ["반도체", "HBM", "파운드리", "엔비디아", "메모리", "D램", "칩"], on: true },
  { id: "commodity", color: "amber", label: "원자재",
    keywords: ["유가", "WTI", "금값", "원유", "국제유가", "구리", "천연가스"], on: true },
  { id: "rate", color: "violet", label: "금리·환율",
    keywords: ["금리", "연준", "원달러 환율", "환율", "FOMC", "금통위", "국채"], on: true },
  { id: "trade", color: "teal", label: "무역",
    keywords: ["관세", "미중 무역", "수출규제", "수출", "수입", "무역", "통상", "교역"], on: true },
  { id: "sector", color: "rose", label: "업종",
    keywords: ["이차전지", "바이오", "조선", "방산", "배터리", "제약", "자동차", "원전"], on: true },
  { id: "market", color: "slate", label: "시장",
    keywords: ["코스피", "외국인 순매수", "공매도", "코스닥", "증시", "상장", "실적"], on: true }
];

// 자동으로 찍어내는 시세 기사. 읽을 것이 없어 버린다.
const NEWS_DROP = ["소폭 상승세", "소폭 하락세", "상승폭 확대", "하락폭 확대", "특징주", "상위 20종목", "상승률 상위", "하락률 상위", "기술적 분석", "인기검색"];

/* 받아올 곳. data/news-topics.json 의 feeds 와 같아야 한다.
   holdings/tools/check-news-topics.py 가 대조한다. */
const NEWS_FEEDS = [
  { id: "hk", label: "한국경제", url: "https://www.hankyung.com/feed/finance" },
  { id: "hk-ec", label: "한국경제", url: "https://www.hankyung.com/feed/economy" },
  { id: "mk", label: "매일경제", url: "https://www.mk.co.kr/rss/50200011/" },
  { id: "mk-ec", label: "매일경제", url: "https://www.mk.co.kr/rss/30100041/" },
  { id: "asiae", label: "아시아경제", url: "https://www.asiae.co.kr/rss/economy.htm" },
  { id: "mt", label: "머니투데이", url: "https://rss.mt.co.kr/mt_news.xml" }
];

const NEWS_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KJC-Holdings/1.0";

// 한 출처에서 몇 건까지 볼 것인가. 주제어에 걸리는 것만 남으므로 넉넉히.
const PER_FEED = 150;

// 화면에 몇 건까지 보낼 것인가. 그보다 많아도 아래는 안 읽힌다.
const MAX_ROWS = 80;

const NEWS_TTL = 180;      // 뉴스는 초 단위로 바뀌지 않는다
const MOVES_TTL = 60;      // 장중에 빨리 바뀌므로 짧게

const NEWS_PATH = "/uapi/domestic-stock/v1/quotations/news-title";
const NEWS_TR = "FHKST01011800";
const MOVE_MARKETS = ["01", "02"];

function newsDropped(title) {
  return NEWS_DROP.some((w) => w && title.includes(w));
}

/* RSS 한 항목에서 뽑아낼 것들.

   정규식을 문자열로 조립하지 않고 리터럴로 둔다. 템플릿 문자열
   `<${tag}[^>]*>([\s\S]*?)` 로 만들면 \s 가 s 로 뭉개져 ([sS]*?) 가 되고
   아무것도 안 잡힌다. 2026-09-15 에 그래서 뉴스가 0건이었다. */
const RSS_TAG = {
  title:  /<title[^>]*>([\s\S]*?)<\/title>/,
  link:   /<link[^>]*>([\s\S]*?)<\/link>/,
  pubDate: /<pubDate[^>]*>([\s\S]*?)<\/pubDate>/,
  source: /<source[^>]*>([\s\S]*?)<\/source>/,
};

/* CDATA 를 벗기고 HTML 문자표기를 푼다.

   손으로 목록을 만들다 &#039; 를 빠뜨려 제목에 그대로 남았다 (2026-09-15).
   숫자로 쓴 것(&#039; &#x27;)까지 한 번에 다루도록 정규식으로 바꿨다.

   일부 언론사는 두 번 감싸 &amp;#039; 로 보낸다. 바뀌지 않을 때까지
   되풀이하되, 끝없이 돌지 않도록 세 번에서 멈춘다.
   server/news.py 의 _unescape 와 같은 동작이어야 한다. */
const XML_NAMED = { lt: "<", gt: ">", quot: '"', apos: "'", amp: "&", nbsp: " " };

function unescapeOnce(t) {
  return t.replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z]+);/g, (all, body) => {
    if (body[0] === "#") {
      const code = body[1] === "x" || body[1] === "X"
        ? parseInt(body.slice(2), 16)
        : parseInt(body.slice(1), 10);
      return Number.isFinite(code) ? String.fromCodePoint(code) : all;
    }
    const hit = XML_NAMED[body.toLowerCase()];
    return hit === undefined ? all : hit;
  });
}

function unescapeXml(s) {
  let t = String(s || "").replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1");
  for (let i = 0; i < 3; i++) {
    const once = unescapeOnce(t);
    if (once === t) break;
    t = once;
  }
  return t.replace(/<[^>]+>/g, "").trim();
}

/* RSS 의 GMT 시각을 한국 시각 문자열로. 못 읽으면 원문을 그대로 둔다. */
function toKst(pubdate) {
  const d = new Date(pubdate);
  if (isNaN(d)) return pubdate || "";
  return new Date(d.getTime() + 9 * 3600000).toISOString().replace("Z", "+09:00");
}

/* 제목에 주제어가 들어 있으면 그 주제를 돌려준다. 없으면 null.
   앞에 적힌 주제부터 본다 — 여러 주제에 걸리면 먼저 적힌 것이 이긴다. */
function pickTopic(title, topics) {
  for (const t of topics) {
    for (const kw of t.keywords || []) {
      if (kw && title.includes(kw)) return t;
    }
  }
  return null;
}

/* 한 출처를 받아 주제어에 걸리는 것만 돌려준다.

   주제가 없는 기사는 버린다. 경제지라도 절반 넘게는 주가와 상관없는
   일반 기사다 (2026-09-15 실측: 100건 중 20건만 걸렸다). */
async function fetchFeedNews(feed, topics) {
  const res = await fetch(feed.url, { headers: { "user-agent": NEWS_UA } });
  if (!res.ok) throw new Error(`${feed.label} 응답 ${res.status}`);
  const xml = await res.text();

  const out = [];
  let seen = 0;
  for (const m of xml.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
    if (++seen > PER_FEED) break;
    const block = m[1];
    const pick = (tag) => {
      const hit = block.match(RSS_TAG[tag]);
      return hit ? unescapeXml(hit[1]) : "";
    };
    const title = pick("title");
    if (!title || newsDropped(title)) continue;
    const topic = pickTopic(title, topics);
    if (!topic) continue;

    out.push({
      title, link: pick("link"), at: toKst(pick("pubDate")),
      source: feed.label || feed.id || "",
      topic: topic.id, topicLabel: topic.label,
    });
  }
  return out;
}

/* 켜져 있는 출처를 모두 받아 시각 역순으로 합친다.
   한 곳이 실패해도 나머지는 보여준다. */
async function fetchNewsIssues(env) {
  return memo("news:issues", NEWS_TTL, async () => {
    const on = NEWS_TOPICS.filter((t) => t.on !== false);
    const rows = [];
    const errors = {};
    const seen = new Set();

    for (const f of NEWS_FEEDS) {
      try {
        for (const row of await fetchFeedNews(f, on)) {
          // 같은 기사가 여러 곳에 실린다. 제목으로 한 번만 담는다.
          if (seen.has(row.title)) continue;
          seen.add(row.title);
          rows.push(row);
        }
      } catch (e) {
        errors[f.id] = safeMessage(e, env);
      }
    }
    rows.sort((a, b) => String(b.at).localeCompare(String(a.at)));
    return {
      rows: rows.slice(0, MAX_ROWS),
      errors: Object.keys(errors).length ? errors : null,
      topics: on.map((t) => ({ id: t.id, label: t.label, color: t.color })),
    };
  });
}

/* 20260915 + 121741 → 2026-09-15T12:17:41+09:00 */
function newsStamp(d, t) {
  if (!d || d.length !== 8) return "";
  const hm = (String(t || "") + "000000").slice(0, 6);
  return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`
       + `T${hm.slice(0, 2)}:${hm.slice(2, 4)}:${hm.slice(4, 6)}+09:00`;
}

async function fetchNewsMoves(cfg, env) {
  return memo("news:moves", MOVES_TTL, async () => {
    const rows = [];
    const errors = {};
    const seen = new Set();

    for (const mk of MOVE_MARKETS) {
      let data;
      try {
        data = await kisGet(cfg, env, NEWS_PATH, {
          FID_NEWS_OFER_ENTP_CODE: "", FID_COND_MRKT_CLS_CODE: mk,
          FID_INPUT_ISCD: "", FID_TITL_CNTT: "",
          FID_INPUT_DATE_1: "", FID_INPUT_HOUR_1: "",
          FID_RANK_SORT_CLS_CODE: "", FID_INPUT_SRNO: "",
        }, NEWS_TR, MOVES_TTL);
      } catch (e) {
        errors[mk] = safeMessage(e, env);
        continue;
      }

      for (const r of outRows(data, "output")) {
        const srno = String(r.cntt_usiq_srno || "").trim();
        if (!srno || seen.has(srno)) continue;
        const title = String(r.hts_pbnt_titl_cntt || "").trim();
        if (!title) continue;

        // 관련 종목은 최대 10개까지 코드와 이름이 따로 온다
        const stocks = [];
        for (let i = 1; i <= 10; i++) {
          const c = String(r[`iscd${i}`] || "").trim();
          if (!c) continue;
          stocks.push({ code: c, name: String(r[`kor_isnm${i}`] || "").trim() });
        }
        if (!stocks.length) continue;   // 종목이 안 붙었으면 이 갈래의 몫이 아니다

        seen.add(srno);
        rows.push({
          id: srno, title,
          at: newsStamp(String(r.data_dt || "").trim(), String(r.data_tm || "").trim()),
          source: String(r.dorg || "").trim(),
          market: mk === "01" ? "코스피" : "코스닥",
          stocks,
        });
      }
    }
    rows.sort((a, b) => String(b.at).localeCompare(String(a.at)));
    return { rows, errors: Object.keys(errors).length ? errors : null };
  });
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
  return outRows(data, "output2")
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

/* 분봉을 어느 시장에서 받을까. **구간의 시각으로 정한다.**

       정규장 09:00~15:30   J  (KRX)
       그 밖                UN (통합)

   일봉과 달리 **분봉은 한쪽만으로는 못 채운다** (2026-09-17 실측).

       08:30 프리마켓   J  0개      UN 30개   ← 넥스트레이드는 통합에만 있다
       10:30 장중       J 30개      UN 30개
       우선주 장중      J 30개      UN  0개   ← 통합은 값이 비어 온다

   삼성전자우 5분봉이 하루 종일 194,600원에 거래량 0 이었던 것이 이 때문이다.
   server/kis_proxy.py 의 minute_market_div 와 같은 규칙이어야 한다. */
function minuteMarketDiv(hour) {
  const m = parseInt(String(hour).slice(0, 2), 10) * 60
          + parseInt(String(hour).slice(2, 4), 10);
  if (!Number.isFinite(m)) return MARKET_DIV_CHART;
  return (m >= KRX_OPEN_MIN && m < KRX_CLOSE_MIN) ? "J" : MARKET_DIV_CHART;
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
      FID_COND_MRKT_DIV_CODE: minuteMarketDiv(hour),
      FID_INPUT_ISCD: code,
      FID_INPUT_HOUR_1: hour,
      FID_PW_DATA_INCU_YN: "Y",
    },
    "FHKST03010200",
    QUOTE_CACHE_TTL
  );
  return outRows(data, "output2")
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
/* 마지막 봉이 이보다 오래됐으면 최근 구간만 받지 않고 하루치를 다시 모은다.
   장중 한 시간이면 12개가 비는 셈이라, 그 정도면 통째로 받는 편이 낫다. */
const MINUTE_REFILL_GAP = 60;

/* 하루치를 통째로 받아야 하나.

   **두 가지를 본다. 하나만 보면 구멍이 남는다.**

     1. 오늘 하루치를 아직 안 받았다        → 받는다
     2. 마지막 봉이 한 시간 넘게 오래됐다   → 받는다

   처음에는 2번만 봤는데, 최근 봉이 있으면 **앞쪽 구멍을 안 메웠다.**
   삼성전자우가 10:15~10:50 만 있고 09:00~10:15 가 빈 채로 남았다
   (2026-09-17). 마지막 봉만 보면 "방금 받았으니 됐다" 가 되어 버린다.

   1번은 하루 한 번만 걸린다. 날짜를 값에 넣어 키가 늘어나지 않게 한다. */
async function minutesNeedDay(env, code, period, rows) {
  const today = ymd(new Date());
  if ((await metaGet(env, `dayfill:${code}:${period}`)) !== today) return true;
  if (!rows.length) return true;
  try {
    const ts = rows[rows.length - 1].ts;        // YYYYMMDDHHMM
    const kstNow = new Date(Date.now() + 9 * 3600 * 1000);
    const last = Date.UTC(+ts.slice(0, 4), +ts.slice(4, 6) - 1, +ts.slice(6, 8),
                          +ts.slice(8, 10), +ts.slice(10, 12));
    return (kstNow.getTime() - last) / 60000 > MINUTE_REFILL_GAP;
  } catch {
    return true;                                 // 읽을 수 없으면 다시 받는 쪽으로
  }
}

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
      // 많이 비었으면 하루치를 모으고, 조금이면 최근 구간만.
      //
      // **「있나 없나」로 가르면 안 된다.** 전에는 rows 가 하나라도 있으면
      // 최근 구간만 받았는데, 며칠 전 것이 남아 있는 종목은 오늘 것이
      // 통째로 비었다 — 삼성전자우가 09:00~10:15 가 없이 7개뿐이었다
      // (2026-09-17). 거래가 잦은 종목만 자주 열려 저절로 채워지고
      // 있었던 것이라, 종목마다 봉 개수가 크게 갈렸다.
      let raw;
      if (await minutesNeedDay(env, code, period, rows)) {
        const day = await fetchMinutesDay(cfg, env, code);
        raw = day.bars;
        if (day.failed) {
          warn = `분봉 ${day.tried}구간 중 ${day.failed}구간 실패 (${day.lastError || "이유 없음"})`;
        }
        await metaSet(env, `dayfill:${code}:${period}`, ymd(new Date()));
      } else {
        raw = await fetchMinutesFromKis(cfg, env, code);
      }
      bars = period === "5m" ? aggregateMinutes(raw, 5) : raw;
    }
    fetched = await saveCandles(env, code, period, bars);
    await metaSet(env, mkey, Date.now());
    if (fetched) rows = await readCandles(env, code, period, limit);
  }
  return { rows, fetched, warn, source: fetched ? "KIS+DB" : "DB" };
}

/* ── 여러 종목을 한 번에 ────────────────────────────────────────────────
   현재가 API(inquire-price)는 한 번에 한 종목만 준다. 순위표처럼 수십 종목을
   보여주는 화면에서는 그만큼 호출이 곱해져 한참 걸린다.

     30종목을 받을 때   단건 조회 30번 7.9초  vs  멀티 조회 1번 2.1초

   관심종목(멀티종목) 시세조회는 **한 번에 30종목까지** 준다.
   40개를 보내면 앞 30개만 돌아온다 (2026-09-14 직접 호출해 확인).

   주는 항목이 단건보다 적다. 시가총액·PER·PBR·52주 최고저가 없다. 그래서
   종목 화면은 단건 조회를 쓰고, 이것은 목록용이다.

   server/kis_proxy.py 의 fetch_quotes_multi 와 **같은 모양으로 돌려줘야 한다.**
   화면은 같은 코드로 로컬과 배포본을 함께 읽는다. */
const MULTI_MAX = 30;

/* 목록 시세를 몇 초 동안 들고 있을 것인가.

   순위표가 0.2초마다 다섯 묶음 중 하나씩 도므로 같은 묶음은 1초마다 다시
   온다. 캐시를 1초로 두면 매번 아슬아슬하게 만료되어 효과가 없다. 2초면
   한 번 걸러 내보내므로 KIS 호출이 절반이 된다 (2026-09-16 지시).

   값이 최대 2초 묵는다. 그 대신 요청이 겹쳐도 워커가 1101(예외로 죽음)로
   떨어지지 않는다. 2026-09-16 에 실제로 그랬다 — 화면 한 장이 30초에
   102번을 부르는데 quotes 에만 캐시가 없었다.

   server/kis_proxy.py 의 MULTI_CACHE_TTL 과 같아야 한다. */
const MULTI_CACHE_TTL = 2;

/* 묶음이 같으면 같은 키. 순서가 달라도 같은 것으로 본다. */
function quotesKey(codes, div) {
  return `quotes:${div}:${[...codes].sort().join(",")}`;
}

async function fetchQuotesMulti(cfg, env, codes) {
  return memo(quotesKey(codes, quoteMarketDiv()), MULTI_CACHE_TTL,
              () => fetchQuotesMultiLive(cfg, env, codes));
}

async function fetchQuotesMultiLive(cfg, env, codes) {
  const div = quoteMarketDiv();
  const out = {};
  const errors = {};

  for (let i = 0; i < codes.length; i += MULTI_MAX) {
    const chunk = codes.slice(i, i + MULTI_MAX);
    const params = {};
    chunk.forEach((code, n) => {
      params[`FID_COND_MRKT_DIV_CODE_${n + 1}`] = div;
      params[`FID_INPUT_ISCD_${n + 1}`] = code;
    });

    let data;
    try {
      /* kisGet 이 cfg.pace() 로 호출 간격을 지킨다. 그것을 건너뛰면 분봉 때처럼
         초당 한도에 걸려 조용히 빈 값이 돌아온다. */
      data = await kisGet(
        cfg, env,
        "/uapi/domestic-stock/v1/quotations/intstock-multprice",
        params, "FHKST11300006",
        MULTI_CACHE_TTL               // 목록은 자주 바뀌므로 짧게
      );
    } catch (e) {
      for (const code of chunk) errors[code] = safeMessage(e, env);
      continue;
    }

    for (const r of outRows(data, "output")) {
      const code = String(r.inter_shrn_iscd || "").trim();
      if (!code) continue;
      const price = num(r.inter2_prpr);
      out[code] = {
        price,
        prev: num(r.inter2_prdy_clpr),
        amt: num(r.inter2_prdy_vrss),
        pct: num(r.prdy_ctrt),
        name: String(r.inter_kor_isnm || "").trim(),
        open: num(r.inter2_oprc),
        high: num(r.inter2_hgpr),
        low: num(r.inter2_lwpr),
        volume: num(r.acml_vol),
        // 거래대금은 실제 값이 온다. 현재가×거래량으로 어림하지 않아도 된다.
        value: num(r.acml_tr_pbmn),
        source: "KIS",
      };
    }
  }
  return { data: out, errors };
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

/* 어느 시장의 공시를 받을 것인가 (2026-09-15 지시로 넓혔다).
     Y 유가증권(코스피) · K 코스닥 · N 코넥스 · E 기타
   코넥스는 하루 한 건 남짓이고, 기타는 75건 중 68건이 비상장·펀드라
   종목코드가 없다. 종목코드가 없으면 화면에 붙일 종목이 없어 쓸 수 없다.
   server/dart.py 의 COLLECT_MARKETS 와 같아야 한다. */
const COLLECT_MARKETS = ["Y", "K"];

// 며칠 치를 들고 있을 것인가. 넘긴 것은 폴링할 때 지운다.
const RETENTION_DAYS = 30;

/* 텔레그램을 보낼 종목. server/dart.py 의 WATCH_CODES 와 같아야 한다.
   순위(200종목)가 양쪽에서 조금 달라져도 알림은 이 목록에만 가므로 영향이 없다. */
const DART_WATCH_CODES = [
  "005930", "000660", "035420", "035720",
  "005380", "373220", "207940", "068270",
];

const DART_SCHEMA = [
  `CREATE TABLE IF NOT EXISTS index_members (
     stock_code TEXT NOT NULL,
     index_code TEXT NOT NULL,
     name       TEXT,
     updated_at TEXT,
     PRIMARY KEY (stock_code, index_code)
   )`,
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
/* ── 알림 예약 ───────────────────────────────────────────────

   정해둔 시각이 지나면 텔레그램으로 한 번 보낸다. Cron 이 5분마다 도므로
   정각이 아니라 그 안쪽 어딘가에 도착한다.

   보낸 것은 sync_meta 에 적어 두 번 가지 않게 한다 — 공시가 "오늘 보냈나"를
   기억하는 것과 같은 방식이다.

   지나간 것은 지운다. 목록이 쌓이면 무엇이 살아 있는지 알 수 없다.        */

const REMINDERS = [
  { id: "20260916-0900", at: "2026-09-16T09:00",
    text: "오늘 할 일 — 숫자 깜빡임 제거 부분 수정" },
];

/* 지금 한국 시각을 '2026-09-16T09:00' 꼴로. 문자열끼리 비교하면
   시간대 계산을 한 번 더 하지 않아도 된다. */
function kstStamp(now = new Date()) {
  const k = new Date(now.getTime() + 9 * 3600 * 1000);
  const p = (n) => String(n).padStart(2, "0");
  return `${k.getUTCFullYear()}-${p(k.getUTCMonth() + 1)}-${p(k.getUTCDate())}`
       + `T${p(k.getUTCHours())}:${p(k.getUTCMinutes())}`;
}

async function sendReminders(env) {
  if (!REMINDERS.length) return 0;
  const now = kstStamp();
  let sent = 0;
  for (const r of REMINDERS) {
    if (now < r.at) continue;                       // 아직 때가 아니다
    const key = `remind_${r.id}`;
    if (await metaGet(env, key)) continue;          // 이미 보냈다
    const ok = await telegramSend(env, r.text);
    if (ok) {
      await metaSet(env, key, now);
      sent++;
    }
  }
  return sent;
}

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
/* ── 네이버 업종 · 테마 (2026-09-18) ──────────────────────────────
 *
 * 「지금 뜨는 산업」 이 쓴다. **server/naver.py 와 같은 판정이어야 한다** —
 * 로컬과 배포본의 숫자가 갈리면 안 된다. 상수·필드·콤마 처리를 맞춰 두었다.
 *
 * KIS 에 없는 둘 때문에 여기서 받는다 — 업종 안에서 몇이 오르내렸는지,
 * 그리고 그 업종의 종목 목록이다. 테마는 KIS 에 아예 없다.
 * 조사 기록은 docs/sector-sources.md 에 있다. */
const NAVER_BASE = "https://m.stock.naver.com/api/stocks";
const NAVER_HEADERS = { "user-agent": "Mozilla/5.0", referer: "https://m.stock.naver.com/" };
const NAVER_TTL = 30;           // server/naver.py 의 TTL 과 같은 값
const NAVER_LIST_SIZE = 20;     // 〃 LIST_SIZE
const NAVER_STOCK_SIZE = 10;    // 〃 STOCK_SIZE

/* 「기타」 는 업종이 아니다 (2026-09-18).
   네이버 업종 목록에 `기타`(no=25)가 끼어 있는데 1,538종목이다. 분류가 안 된
   나머지를 다 모아둔 칸이라 등락률이 시장 평균과 같고, 「지금 뜨는 산업」에
   올라오면 아무 뜻이 없다. **이름이나 번호가 아니라 크기로 거른다** — 실제
   업종 중 가장 큰 것이 반도체 171종목이라 아홉 배 넘게 벌어져 있다.
   server/naver.py 의 MAX_GROUP_COUNT 와 같은 값이어야 한다. */
const NAVER_MAX_GROUP_COUNT = 1000;
/* 종목별 뉴스에서 받아 둘 묶음 수. server/naver.py 의 NEWS_SIZE 와 같아야 한다 */
const NAVER_NEWS_SIZE = 12;
/* 종목토론에서 받아 둘 글 수. server/naver.py 의 DISCUSS_SIZE 와 같아야 한다 */
const NAVER_DISCUSS_SIZE = 12;

/* 네이버는 "60,700" 처럼 **콤마가 든 문자열**로 준다. 그대로 Number() 에
   넣으면 NaN 이 되므로 여기서 푼다 — 화면이 또 풀지 않게 한다. */
function naverNum(v) {
  if (v === null || v === undefined) return null;
  const t = String(v).replace(/[,\s%]/g, "");
  if (t === "" || t === "-" || t === "+") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

async function naverGet(path) {
  const res = await fetch(NAVER_BASE + path, { headers: NAVER_HEADERS });
  if (!res.ok) throw new Error(`네이버 HTTP ${res.status}`);
  return res.json();
}

/* 업종 또는 테마 목록. **등락률 내림차순이 기본**이라 그대로 쓴다 */
async function naverGroups(env, kind) {
  return memo(`nv:g:${kind}`, NAVER_TTL, async () => {
    const j = await naverGet(`/${kind}?page=1&pageSize=${NAVER_LIST_SIZE}`);
    const all = (j.groups || []).map((g) => ({
      no: g.no,
      name: g.name,
      pct: naverNum(g.changeRate),
      rise: naverNum(g.riseCount) || 0,
      steady: naverNum(g.steadyCount) || 0,
      fall: naverNum(g.fallCount) || 0,
      count: naverNum(g.totalCount) || 0,
    }));
    const rows = all.filter((r) => r.count <= NAVER_MAX_GROUP_COUNT);
    const dropped = all.length - rows.length;
    /* 거른 만큼 빼서 돌려준다 — 화면이 「79개 중」 이라고 적는데 실제로는
       하나를 빼고 보여주므로 숫자가 어긋나면 안 된다 */
    const total = naverNum(j.totalCount);
    return {
      rows, dropped, marketStatus: j.marketStatus,
      total: total == null ? null : total - dropped,
    };
  });
}

/* 제목이 `&quot;직접 대화하자&quot;` 처럼 HTML 로 이스케이프되어 온다.
   화면이 다시 이스케이프하므로 여기서 풀어야 글자가 제대로 보인다.
   워커에는 파이썬의 html.unescape 같은 것이 없어 직접 푼다
   (server/naver.py 와 같은 결과여야 한다). */
function unescapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&");   /* 마지막에 푼다 — 먼저 풀면 &amp;quot; 가 두 번 풀린다 */
}

/* 종목 한 장 요약 — 일별 매매동향 5일과 지표 18개가 한 번에 온다.
   server/naver.py 의 integration() 과 같은 판정이어야 한다.

   ⚠️ **시가총액 순위는 여기서 못 준다.** 서버는 공시 수집이 아침마다 받아 두는
   표(market.db 의 dart_universe)에서 읽는데, **워커에는 그 표가 없다.**
   그래서 rank 는 늘 null 이고 화면은 「—」로 적는다 — 로컬에서만 순위가 보인다. */
async function naverIntegration(env, code) {
  return memo(`nv:i:${code}`, NAVER_TTL, async () => {
    const res = await fetch(`https://m.stock.naver.com/api/stock/${code}/integration`,
                            { headers: NAVER_HEADERS });
    if (!res.ok) throw new Error(`네이버 HTTP ${res.status}`);
    const j = await res.json();

    const flow = (j.dealTrendInfos || []).slice(0, 5).map((d) => ({
      date: d.bizdate,
      foreign: naverNum(d.foreignerPureBuyQuant),
      inst: naverNum(d.organPureBuyQuant),
      person: naverNum(d.individualPureBuyQuant),
      foreignRate: naverNum(d.foreignerHoldRatio),
      close: naverNum(d.closePrice),
      volume: naverNum(d.accumulatedTradingVolume),
    }));

    const info = {};
    for (const t of (j.totalInfos || [])) {
      info[t.code] = { name: t.key, value: t.value };
    }
    return { name: j.stockName, flow, info, rank: null };
  });
}

/* 종목별 뉴스. **바깥이 배열**이고 각 묶음 안에 items 가 있다.
   같은 사건을 여러 언론사가 쓰면 한 묶음으로 오므로 묶음마다 첫 기사만 쓴다.
   server/naver.py 의 news() 와 같은 판정이어야 한다. */
async function naverNews(env, code) {
  return memo(`nv:n:${code}`, NAVER_TTL, async () => {
    const res = await fetch(
      `https://m.stock.naver.com/api/news/stock/${code}?pageSize=${NAVER_NEWS_SIZE}&page=1`,
      { headers: NAVER_HEADERS }
    );
    if (!res.ok) throw new Error(`네이버 HTTP ${res.status}`);
    const j = await res.json();
    const rows = [];
    for (const g of (Array.isArray(j) ? j : [])) {
      const items = g.items || [];
      if (!items.length) continue;
      const it = items[0];
      const oid = String(it.officeId || "").trim();
      const aid = String(it.articleId || "").trim();
      rows.push({
        title: unescapeHtml(String(it.title || "").trim()),
        office: String(it.officeName || "").trim(),
        at: String(it.datetime || "").trim(),
        more: Math.max(0, items.length - 1),
        url: oid && aid ? `https://n.news.naver.com/mnews/article/${oid}/${aid}` : null,
      });
    }
    return rows;
  });
}

/* 종목토론실 글. **호스트가 stock.naver.com 이다** — 이 파일의 다른 네이버
   호출과 달리 m.stock · api.stock 은 404 다 (2026-09-18 실측).
   server/naver.py 의 discuss() 와 같은 판정이어야 한다. */
async function naverDiscuss(env, code) {
  return memo(`nv:d:${code}`, NAVER_TTL, async () => {
    const res = await fetch(
      "https://stock.naver.com/api/community/discussion/posts" +
      `?itemCode=${code}&discussionType=DOMESTIC_STOCK&isHolderOnly=false` +
      `&excludesItemNews=true&isItemNewsOnly=false&pageSize=${NAVER_DISCUSS_SIZE}`,
      { headers: NAVER_HEADERS }
    );
    if (!res.ok) throw new Error(`네이버 HTTP ${res.status}`);
    const j = await res.json();
    return (j.posts || []).map((p) => {
      const pid = String(p.id || "").trim();
      return {
        title: unescapeHtml(String(p.title || "").trim()),
        writer: String((p.writer || {}).nickname || "").trim(),
        at: String(p.writtenAt || "").trim(),
        comments: Number(p.commentCount) || 0,
        likes: Number(p.recommendCount) || 0,
        url: pid ? `https://stock.naver.com/domestic/stock/${code}/discussion/${pid}` : null,
      };
    });
  });
}

/* 그 묶음의 종목. **등락률 내림차순**이라 앞에서부터 상승률 TOP 이다 */
async function naverStocks(env, kind, no) {
  return memo(`nv:s:${kind}:${no}`, NAVER_TTL, async () => {
    const j = await naverGet(`/${kind}/${no}?page=1&pageSize=${NAVER_STOCK_SIZE}`);
    const rows = [];
    for (const s of (j.stocks || [])) {
      const code = String(s.itemCode || "").trim();
      if (code.length !== 6) continue;
      rows.push({
        code,
        name: s.stockName,
        price: naverNum(s.closePrice),
        amt: naverNum(s.compareToPreviousClosePrice),
        pct: naverNum(s.fluctuationsRatio),
        volume: naverNum(s.accumulatedTradingVolume),
        value: naverNum(s.accumulatedTradingValue),
      });
    }
    return { rows, name: j.groupName || j.name };
  });
}

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

/* 지수 구성종목. server/dart.py 의 INDEX_LISTS 와 같아야 한다.

   네이버에서 받는다 — KIS 에 구성종목을 주는 API 를 찾지 못했다
   (2026-09-15 확인). 분기에 한 번 바뀌는 값이라 하루 한 번만 받는다. */
const INDEX_LISTS = [["KPI200", "코스피200"], ["KQI150", "코스닥150"]];

const MEMBER_ROW = /code=(\d{6})[^>]*>\s*([^<]+?)\s*<\/a>/g;

async function fetchIndexMembers(indexCode, maxPage = 25) {
  const out = [];
  const seen = new Set();
  for (let page = 1; page <= maxPage; page++) {
    const url = "https://finance.naver.com/sise/entryJongmok.naver"
              + `?&type=${indexCode}&page=${page}`;
    const res = await fetch(url, {
      headers: {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        referer: "https://finance.naver.com/",
      },
    });
    if (!res.ok) throw new Error(`네이버 응답 ${res.status}`);
    // 이 페이지는 EUC-KR 이다. 그대로 읽으면 이름이 깨진다.
    const body = new TextDecoder("euc-kr").decode(await res.arrayBuffer());

    let fresh = 0;
    for (const m of body.matchAll(MEMBER_ROW)) {
      const code = m[1];
      if (seen.has(code)) continue;
      seen.add(code);
      out.push({ code, name: unescapeXml(m[2]) });
      fresh++;
    }
    if (!fresh) break;
  }
  return out;
}

async function refreshIndexMembers(env) {
  const db = await dartInit(env);
  const now = new Date().toISOString();
  const done = {};
  for (const [indexCode, label] of INDEX_LISTS) {
    let rows;
    try {
      rows = await fetchIndexMembers(indexCode);
    } catch (e) {
      await metaSet(env, "dart_last_error", `${label}: ${safeMessage(e, env)}`);
      continue;
    }
    if (!rows.length) continue;
    await db.prepare(`DELETE FROM index_members WHERE index_code = ?`)
      .bind(indexCode).run();
    const stmt = db.prepare(
      `INSERT INTO index_members (stock_code, index_code, name, updated_at)
       VALUES (?, ?, ?, ?)`);
    // D1 batch 는 한 번에 보낼 수 있는 양에 한계가 있어 나눠 보낸다
    for (let i = 0; i < rows.length; i += 50) {
      await db.batch(rows.slice(i, i + 50).map(
        (r) => stmt.bind(r.code, indexCode, r.name, now)));
    }
    done[indexCode] = rows.length;
  }
  if (Object.keys(done).length) await metaSet(env, "dart_members_date", kstToday());
  return done;
}

async function indexMembersMap(env) {
  const db = await dartInit(env);
  const res = await db.prepare(
    `SELECT stock_code, index_code FROM index_members`).all();
  const out = {};
  for (const r of res.results || []) {
    (out[r.stock_code] = out[r.stock_code] || []).push(r.index_code);
  }
  return out;
}

async function indexMembersCount(env) {
  const db = await dartInit(env);
  const res = await db.prepare(
    `SELECT index_code, COUNT(*) n FROM index_members GROUP BY index_code`).all();
  const out = {};
  for (const r of res.results || []) out[r.index_code] = r.n;
  return out;
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
/* onlyCodes 가 null 이면 종목코드가 있는 것을 전부 담는다 (2026-09-15 지시).
   목록을 주면 그것만 담는다. server/dart.py 의 save_disclosures 와 같다. */
async function saveDisclosures(env, items, onlyCodes = null, notified = 0) {
  const db = await dartInit(env);
  const fresh = [];
  const rows = [];

  for (const it of items) {
    const code = String(it.stock_code || "").trim();
    if (!code) continue;                            // 비상장·펀드
    if (onlyCodes && !onlyCodes.has(code)) continue;
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

/* 보관 기간이 지난 공시를 지운다. 지운 건수를 돌려준다.

   rcept_dt 는 'YYYYMMDD' 문자열이라 문자열 비교로 자를 수 있다.
   server/dart.py 의 purge_old 와 같다. */
async function purgeOldDisclosures(env, days = RETENTION_DAYS) {
  const db = await dartInit(env);
  const cut = new Date(Date.now() - days * 86400000)
    .toISOString().slice(0, 10).replace(/-/g, "");
  const res = await db.prepare(
    `DELETE FROM dart_disclosures WHERE rcept_dt < ?`).bind(cut).run();
  return (res.meta && res.meta.changes) || 0;
}

/* ── 5분봉 미리 받아두기 ──────────────────────────────────────────
 *
 * 화면이 종목을 처음 열 때 하루치를 받으면 **3.1초**가 걸린다 (2026-09-17 실측).
 * 30분씩 거슬러 올라가며 여러 번 부르기 때문이고, 저녁일수록 구간이 늘어
 * 더 느려진다. 마우스로 순위표를 훑으면 종목마다 그만큼 걸린다.
 *
 * 그래서 **Cron 이 돌 때마다 몇 종목씩 미리 받아 둔다** (2026-09-17 지시).
 * 코스피 시가총액 상위 순으로 간다.
 *
 * 로컬(server/kis_proxy.py)은 스레드로 한 바퀴씩 돌지만, 워커는 한 번에
 * 오래 못 돈다. **어디까지 했는지 메타에 적어 두고 이어서 간다.**
 */
const PREFILL_TOP = 100;        // 코스피 상위 몇 종목까지
const PREFILL_PER_RUN = 5;      // Cron 한 번에 몇 종목씩

/* 새 봉이 생겼을 때만 받는다 (2026-09-18 지시).
 *
 * 재권님 말씀 — "5분봉 미리받기 → 5분봉 갱신될때만 받기".
 *
 * 5m 의 freshSec 은 30초인데 한 바퀴는 그보다 훨씬 오래 걸린다. 돌아왔을
 * 때는 이미 지나 있어 **매번 다시 받았다.** 5분봉은 5분에 한 번만 새 봉이
 * 생기므로 그 사이에 받는 것은 같은 값을 또 받는 것이다.
 *
 * **로컬 서버와 앱키가 같다.** 둘이 같은 한도(초당 10회)를 나눠 쓰므로
 * 한쪽만 고치면 절반만 고치는 셈이다 — server/kis_proxy.py 의
 * PREFILL_FRESH_SEC 과 같은 값이어야 하고 check-kis-consts.py 가 대조한다.
 *
 * 화면이 직접 여는 종목은 이 길로 오지 않는다. getChart 가 freshSec 으로
 * 따로 판단하므로 보고 있는 종목만 실시간이 된다. */
const PREFILL_FRESH_SEC = 300;

async function prefillMinutes(cfg, env) {
  let codes;
  try {
    const res = await requireDb(env).prepare(
      "SELECT stock_code FROM dart_universe ORDER BY rank LIMIT ?"
    ).bind(PREFILL_TOP).all();
    codes = (res.results || []).map((r) => r.stock_code);
  } catch {
    codes = [];
  }
  if (!codes.length) codes = DART_WATCH_CODES.slice();
  if (!codes.length) return 0;

  /* 어디까지 했는지 이어서 간다. 한 바퀴 돌면 처음으로 */
  let at = Number((await metaGet(env, "prefill_at")) || 0);
  if (!Number.isFinite(at) || at < 0 || at >= codes.length) at = 0;

  let done = 0;
  for (let i = 0; i < PREFILL_PER_RUN && at < codes.length; i++, at++) {
    /* 새 봉이 생겼을 때만 받는다. 5분봉은 5분에 하나씩 생긴다 */
    const last = Number(await metaGet(env, `sync:${codes[at]}:5m`)) || 0;
    if (Date.now() - last < PREFILL_FRESH_SEC * 1000) continue;
    try {
      await getChart(cfg, env, codes[at], "5m", 1);
      done++;
    } catch { /* 한 종목이 실패해도 나머지는 간다 */ }
  }
  await metaSet(env, "prefill_at", at >= codes.length ? 0 : at);
  return done;
}

async function dartPollOnce(env, quietFirstRun = true) {
  const key = env.DART_API_KEY;
  if (!key) return { ok: false, error: "DART_API_KEY 가 설정되지 않았습니다." };

  await dartInit(env);
  const today = kstToday();

  if ((await metaGet(env, "dart_universe_date")) !== today) {
    const u = await refreshUniverse(env);
    if (!u.ok) await metaSet(env, "dart_last_error", u.error);
  }
  if ((await metaGet(env, "dart_members_date")) !== today) {
    await refreshIndexMembers(env);
  }

  // 시장마다 한 번씩 받는다. 기간 조회라 종목 수와 무관하게 호출이 일정하다.
  const items = [];
  for (const cls of COLLECT_MARKETS) {
    try {
      items.push(...(await fetchDartList(key, today, today, cls)));
    } catch (e) {
      // 한 시장이 막혀도 나머지는 담는다. 전부 실패했을 때만 오류로 친다.
      const msg = `${cls}: ${safeMessage(e, env)}`;
      await metaSet(env, "dart_last_error", msg);
      if (cls === COLLECT_MARKETS[COLLECT_MARKETS.length - 1] && !items.length) {
        return { ok: false, error: msg };
      }
    }
  }

  const firstRun = !(await metaGet(env, "dart_last_poll"));
  const mark = firstRun && quietFirstRun ? 1 : 0;

  /* 종목코드가 있는 것은 전부 담는다 (2026-09-15 지시).
     텔레그램은 그대로 관심종목만 간다 — dartNotify 가 DART_WATCH_CODES 로 거른다. */
  const fresh = await saveDisclosures(env, items, null, mark);
  const notified = mark ? 0 : await dartNotify(env, fresh);

  const purged = await purgeOldDisclosures(env);

  await metaSet(env, "dart_last_poll", new Date().toISOString());
  await metaSet(env, "dart_last_error", "");
  return { ok: true, received: items.length, matched: fresh.length,
           notified, purged, firstRun };
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
      // 공시와 별개로 먼저 본다. 주말·장 시간과 무관하게 가야 한다.
      try { await sendReminders(env); } catch {}

      /* 5분봉을 몇 종목씩 미리 받아 둔다. 화면이 기다리지 않게 하려는 것이라
         공시보다 먼저 두지 않는다 — 실패해도 공시는 돌아야 한다. */
      if (!dartShouldPoll()) return;
      try {
        await dartPollOnce(env);
      } catch (e) {
        try { await metaSet(env, "dart_last_error", safeMessage(e, env)); } catch {}
      }
      try {
        const cfg = readConfig(env);
        if (cfg) await prefillMinutes(cfg, env);
      } catch {}
    })());
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    const route = url.pathname.replace(/^\/api\/kis\/?/, "").replace(/\/$/, "");

    // ── 공시 ──
    /* ── 뉴스 ──
       두 갈래를 따로 받는다. server/kis_proxy.py 의 _handle_news 와 같은 경로다. */
    if (url.pathname.startsWith("/api/news")) {
      if (request.method !== "GET") return fail("GET 요청만 지원합니다.", 405);
      const newsRoute = url.pathname.replace(/^\/api\/news\/?/, "").replace(/\/$/, "");
      try {
        if (newsRoute === "topics") {
          return json({ ok: true, data: NEWS_TOPICS.filter((t) => t.on !== false) });
        }
        if (newsRoute === "issues") {
          const r = await fetchNewsIssues(env);
          return json({ ok: true, data: r.rows,
                        meta: { topics: r.topics, errors: r.errors } });
        }

        const cfg = readConfig(env);
        if (newsRoute === "moves") {
          const r = await fetchNewsMoves(cfg, env);
          return json({ ok: true, data: r.rows, meta: { errors: r.errors } });
        }
        if (newsRoute === "feed") {        // 화면이 한 번에 받아가는 자리
          const [iss, mov] = await Promise.all([
            fetchNewsIssues(env), fetchNewsMoves(cfg, env),
          ]);
          return json({
            ok: true,
            data: { issues: iss.rows, moves: mov.rows, topics: iss.topics },
            meta: { errors: { issues: iss.errors, moves: mov.errors } },
          });
        }
        return fail(`알 수 없는 경로입니다: ${newsRoute}`, 404);
      } catch (e) {
        return fail(safeMessage(e, env), 500);
      }
    }

    /* ── 네이버 업종 · 테마 (2026-09-18) ──
     *
     * 「지금 뜨는 산업」 이 쓴다. **server/naver.py 와 같은 판정이어야 한다** —
     * 로컬과 배포본의 값이 갈리면 안 된다. 콤마 푸는 것과 no 가 없을 때의
     * 400 문구까지 맞춰 두었다.
     *
     * 이 계통을 안 만들어서 배포본이 404 로 빌 뻔했다 (2026-09-18, 검증에서
     * 잡았다). 화면을 새 경로로 바꾸면 워커에도 그 경로가 있어야 한다 —
     * 2026-09-14 의 `/api/kis/quotes` 와 같은 사고다. */
    if (url.pathname.startsWith("/api/naver")) {
      if (request.method !== "GET") return fail("GET 요청만 지원합니다.", 405);
      const nvRoute = url.pathname.replace(/^\/api\/naver\/?/, "").replace(/\/$/, "");
      const kind = (url.searchParams.get("kind") || "industry").trim();
      try {
        if (kind !== "industry" && kind !== "theme") {
          return fail("kind 는 industry 또는 theme 여야 합니다.", 400);
        }
        if (nvRoute === "groups") {
          const g = await naverGroups(env, kind);
          return json({
            ok: true, data: g.rows,
            meta: { kind, total: g.total, marketStatus: g.marketStatus,
                    count: g.rows.length, source: "네이버" },
          });
        }
        if (nvRoute === "integration") {
          const code = (url.searchParams.get("code") || "").trim();
          if (!/^\d{6}$/.test(code)) return fail("code 는 6자리 숫자여야 합니다.", 400);
          const d = await naverIntegration(env, code);
          return json({ ok: true, data: d,
                        meta: { code, days: d.flow.length, source: "네이버" } });
        }

        if (nvRoute === "news") {
          const code = (url.searchParams.get("code") || "").trim();
          if (!/^\d{6}$/.test(code)) return fail("code 는 6자리 숫자여야 합니다.", 400);
          const rows = await naverNews(env, code);
          return json({ ok: true, data: rows,
                        meta: { code, count: rows.length, source: "네이버" } });
        }

        if (nvRoute === "discuss") {
          const code = (url.searchParams.get("code") || "").trim();
          if (!/^\d{6}$/.test(code)) return fail("code 는 6자리 숫자여야 합니다.", 400);
          const rows = await naverDiscuss(env, code);
          return json({ ok: true, data: rows,
                        meta: { code, count: rows.length, source: "네이버" } });
        }

        if (nvRoute === "stocks") {
          const no = (url.searchParams.get("no") || "").trim();
          if (!/^\d+$/.test(no)) return fail("no 에 묶음 번호가 필요합니다.", 400);
          const r = await naverStocks(env, kind, Number(no));
          return json({
            ok: true, data: r.rows,
            meta: { kind, no: Number(no), name: r.name,
                    count: r.rows.length, source: "네이버" },
          });
        }
        return fail(`알 수 없는 경로입니다: ${nvRoute}`, 404);
      } catch (e) {
        /* 네이버가 막히거나 모양이 바뀐 경우. 화면은 「불러오지 못했습니다」로
           물러선다 — 엣지에서 네이버가 열리는지는 아직 못 봤다 */
        return fail(safeMessage(e, env), 502);
      }
    }

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
        if (dartRoute === "members") {
          // 지수 구성종목. 화면이 IR 을 걸러낼 때 쓴다 (2026-09-15).
          return json({
            ok: true,
            data: await indexMembersMap(env),
            meta: { counts: await indexMembersCount(env),
                    updatedAt: await metaGet(env, "dart_members_date") },
          });
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

      if (route === "sectors") {
        const want = (url.searchParams.get("market") || "all").trim().toUpperCase();
        const markets = want === "ALL" || want === "" ? null : [want];
        const names = SECTOR_MARKETS.map(([, n]) => n);
        if (markets && !names.includes(markets[0])) {
          return fail(`market 은 ${names.join(", ")} 중 하나여야 합니다.`, 400);
        }
        const { data, errors } = await fetchSectors(cfg, env, markets);
        return json({
          ok: data.length > 0,
          data,
          errors: Object.keys(errors).length ? errors : null,
          meta: {
            count: data.length,
            markets: markets || names,
            // 단위는 화면이 되묻지 않게 응답에 적어 보낸다
            volumeUnit: "천주", valueUnit: "백만원",
            cacheTtl: SECTOR_TTL,
          },
        });
      }

      if (route === "movers") {
        const dir = (url.searchParams.get("dir") || "up").trim().toLowerCase();
        if (dir !== "up" && dir !== "down") {
          return fail("dir 은 up 또는 down 이어야 합니다.", 400);
        }
        let market = (url.searchParams.get("market") || "all").trim().toUpperCase();
        if (market === "ALL" || market === "") market = "all";
        const limit = parseInt(url.searchParams.get("limit") || String(MOVERS_MAX), 10) || MOVERS_MAX;
        const rows = await fetchMovers(cfg, env, dir, market, limit);
        return json({
          ok: true,
          data: rows,
          meta: { count: rows.length, dir, market, max: MOVERS_MAX, cacheTtl: MOVERS_TTL },
        });
      }

      if (route === "investor-flow") {
        const market = (url.searchParams.get("market") || "KOSPI").trim().toUpperCase();
        if (market !== "KOSPI" && market !== "KOSDAQ") {
          return fail("market 은 KOSPI 또는 KOSDAQ 이어야 합니다.", 400);
        }
        const days = parseInt(url.searchParams.get("days") || String(INVESTOR_FLOW_DAYS), 10)
                     || INVESTOR_FLOW_DAYS;
        const rows = await fetchInvestorFlow(cfg, env, market, days);
        return json({
          ok: rows.length > 0,
          data: rows,
          meta: { count: rows.length, market, days, order: "과거→최근",
                  qtyUnit: "천주", amtUnit: "백만원", cacheTtl: INVESTOR_FLOW_TTL },
        });
      }

      /* 지금 보고 있는 그 종목 (2026-09-18 지시).
         아래 investor-top 과 다르다 — 그쪽은 「상위 목록」이고 가집계이며,
         이쪽은 「이 종목」이고 확정치다. */
      if (route === "investor") {
        const code = (url.searchParams.get("code") || "").trim();
        if (!/^\d{6}$/.test(code)) return fail("code 는 6자리 숫자여야 합니다.", 400);
        const data = await fetchInvestor(cfg, env, code);
        return json({
          ok: data.length > 0, data,
          meta: {
            code, count: data.length, days: INVESTOR_DAYS,
            qtyUnit: "주", amtUnit: "백만원",
            /* 종목별은 확정치다. 상위 목록(investor-top)만 가집계다 */
            provisional: false,
          },
        });
      }

      /* 종목별 장중 추정가집계 (2026-09-22 지시) */
      if (route === "investor-estimate") {
        const code = (url.searchParams.get("code") || "").trim();
        if (!/^\d{6}$/.test(code)) return fail("code 는 6자리 숫자여야 합니다.", 400);
        const data = await fetchInvestorEstimate(cfg, env, code);
        return json({
          ok: !!(data && data.latest), data,
          meta: {
            code, qtyUnit: "주",
            /* **확정치가 아니다. 화면에 그대로 적어야 한다** */
            provisional: true,
            person: false,      /* 개인은 이 응답에 없다 */
            note: "장중 추정가집계 — 증권사 집계치. 마감 뒤 확정치와 다르다. "
                + "입력 외국인 09:30·11:20·13:20·14:30 / "
                + "기관 10:00·11:20·13:20·14:30 (±10분)",
            cacheTtl: INVESTOR_EST_TTL,
          },
        });
      }

      if (route === "ticks") {
        const code = (url.searchParams.get("code") || "").trim();
        if (!/^\d{6}$/.test(code)) return fail("code 는 6자리 숫자여야 합니다.", 400);
        const data = await fetchTicks(cfg, env, code);
        return json({ ok: true, data: data.rows,
                      meta: { code, count: data.rows.length, power: data.power,
                              market: quoteMarketDiv() } });
      }

      if (route === "asking") {
        const code = (url.searchParams.get("code") || "").trim();
        if (!/^\d{6}$/.test(code)) return fail("code 는 6자리 숫자여야 합니다.", 400);
        const data = await fetchAsking(cfg, env, code);
        return json({
          ok: true, data,
          meta: {
            code, levels: ASKING_LEVELS, qtyUnit: "주",
            /* 체결된 것이 아니라 **대기 중인 주문**이다. 장이 끝나면
               의미가 옅어진다 — 화면에 적어야 한다 */
            resting: true,
          },
        });
      }

      if (route === "investor-top") {
        const dir = (url.searchParams.get("dir") || "buy").trim().toLowerCase();
        if (dir !== "buy" && dir !== "sell") {
          return fail("dir 은 buy 또는 sell 이어야 합니다.", 400);
        }
        const by = (url.searchParams.get("by") || "qty").trim().toLowerCase();
        if (by !== "qty" && by !== "amt") {
          return fail("by 는 qty 또는 amt 여야 합니다.", 400);
        }
        let market = (url.searchParams.get("market") || "all").trim().toUpperCase();
        if (market === "ALL" || market === "") market = "all";
        const limit = parseInt(url.searchParams.get("limit") || "10", 10) || 10;
        const { data, errors } = await fetchInvestorTop(cfg, env, dir, market, by, limit);
        return json({
          ok: Object.keys(data).length > 0,
          data,
          errors: Object.keys(errors).length ? errors : null,
          meta: {
            dir, by, market,
            qtyUnit: "주", amtUnit: "백만원",
            // 확정치가 아니다. 화면에 그대로 적어 주어야 한다
            provisional: true,
            note: "증권사 집계 가집계치 — 외국인 09:30·11:20·13:20·14:30, "
                + "기관 10:00·11:20·13:20·14:30 에 갱신 (±10분)",
            cacheTtl: INVESTOR_TOP_TTL,
          },
        });
      }

      if (route === "quotes") {
        const raw = url.searchParams.get("codes") || "";
        let codes = raw.split(",").map((c) => c.trim()).filter((c) => /^\d{6}$/.test(c));
        codes = [...new Set(codes)].slice(0, 120);   // 멀티 4묶음까지
        if (!codes.length) {
          return fail("codes 에 6자리 종목코드가 없습니다.", 400);
        }
        const { data, errors } = await fetchQuotesMulti(cfg, env, codes);
        return json({
          ok: true,
          data,
          errors: Object.keys(errors).length ? errors : null,
          meta: { requested: codes.length, perCall: MULTI_MAX },
        });
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

      if (route === "index-candles") {
        const name = (url.searchParams.get("code") || "KOSPI").trim().toUpperCase();
        const found = (INDEX_DEFS.find(([, n]) => n === name) || [])[0];
        if (!found) return fail("code 가 올바르지 않습니다.", 400);
        const period = (url.searchParams.get("period") || "D").trim().toUpperCase();
        if (!INDEX_PERIODS[period]) {
          return fail(`period 는 ${Object.keys(INDEX_PERIODS).join(", ")} 중 하나여야 합니다.`, 400);
        }
        const bars = await fetchIndexCandles(cfg, env, found, period);
        return json({
          ok: true,
          data: { code: name, period, bars },
          meta: { count: bars.length, label: INDEX_PERIODS[period] },
        });
      }

      if (route === "index-minutes") {
        const name = (url.searchParams.get("code") || "KOSPI").trim().toUpperCase();
        const found = (INDEX_DEFS.find(([, n]) => n === name) || [])[0];
        if (!found) {
          return fail(
            `code 는 ${INDEX_DEFS.map(([, n]) => n).join(", ")} 중 하나여야 합니다.`, 400);
        }
        const bars = await fetchIndexMinutes(cfg, env, found);
        return json({
          ok: true,
          data: { code: name, bars },
          meta: { count: bars.length, stepSec: Number(INDEX_MINUTE_STEP) },
        });
      }

      if (route === "indices") {
        const withChart = url.searchParams.get("chart") !== "0";
        let { data, errors } = await fetchIndices(cfg, env, withChart);
        // 해외 지수·환율도 같은 응답에 실어 보낸다. 화면이 한 번만 부르면 된다.
        if (url.searchParams.get("overseas") !== "0") {
          const ovs = await fetchOverseas(cfg, env);
          data = data.concat(ovs.data);
          errors = { ...errors, ...ovs.errors };
        }
        const futures = await fetchFutures(cfg, env);
        return json({
          ok: data.length > 0,
          data,
          futures,
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
