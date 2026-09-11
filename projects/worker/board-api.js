/* ==========================================================================
   KJC Studio · 프로젝트 보드 저장 서버 (Cloudflare Worker)

   하는 일
     GET  /api/board   내 보드 불러오기
     PUT  /api/board   내 보드 저장하기

   누가 쓰는지 확인하는 방법
     Cloudflare Access 가 로그인한 사람에게 붙여주는 CF_Authorization 토큰을
     읽어서 이메일을 확인합니다. 비밀번호를 따로 만들지 않습니다.

     토큰은 서명까지 검증합니다. 공식 문서에 "헤더만 확인하는 것으로는
     충분하지 않으며 신원 위조를 막으려면 JWT 와 서명을 반드시 검증해야 한다"
     고 되어 있기 때문입니다.

   필요한 설정 (Cloudflare 대시보드에서 재권님이 입력)
     D1 바인딩   BOARD_DB      → kjc-board-db
     변수        ACCESS_TEAM   → 팀 이름 (xxx.cloudflareaccess.com 의 xxx)
     변수        ACCESS_AUD    → Access 애플리케이션의 Application Audience 태그

   자세한 절차는 같은 폴더의 README.md 참고.
   ========================================================================== */

/* 보드를 통째로 한 줄에 저장합니다.
   저장 한 번에 1행만 쓰이므로 D1 무료 한도(하루 10만 행)에 닿을 일이 없습니다. */
const SCHEMA = `
  CREATE TABLE IF NOT EXISTS board (
    owner      TEXT PRIMARY KEY,
    data       TEXT NOT NULL,
    updated_at TEXT NOT NULL
  )
`;

/* ── 응답 도우미 ─────────────────────────────── */
function json(body, status) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function fail(status, message) {
  return json({ ok: false, error: message }, status);
}

/* ── base64url 디코딩 ─────────────────────────────── */
function b64urlToBytes(s) {
  const pad = s.length % 4 ? "=".repeat(4 - (s.length % 4)) : "";
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + pad;
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function b64urlToJson(s) {
  return JSON.parse(new TextDecoder().decode(b64urlToBytes(s)));
}

/* ── Access 공개키 (서명 검증용) ─────────────────────────────── */
/* 같은 Worker 인스턴스가 살아 있는 동안만 기억합니다. 매 요청 받아오지 않으려고 둡니다. */
let certCache = { at: 0, keys: null };

async function getAccessKeys(env) {
  const now = Date.now();
  if (certCache.keys && now - certCache.at < 60 * 60 * 1000) return certCache.keys;

  const url = `https://${env.ACCESS_TEAM}.cloudflareaccess.com/cdn-cgi/access/certs`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Access 공개키를 받지 못했습니다 (" + res.status + ")");

  const body = await res.json();
  const keys = body.keys || [];
  certCache = { at: now, keys: keys };
  return keys;
}

/* ── 토큰 검증 후 이메일 돌려주기 ─────────────────────────────── */
async function whoIsAsking(request, env) {
  if (!env.ACCESS_TEAM || !env.ACCESS_AUD) {
    throw new Error("설정이 빠졌습니다. ACCESS_TEAM 과 ACCESS_AUD 를 Worker 변수에 넣어 주세요.");
  }

  /* 브라우저는 쿠키로, 서버 간 호출은 헤더로 옵니다 */
  const header = request.headers.get("Cf-Access-Jwt-Assertion");
  const cookie = (request.headers.get("cookie") || "")
    .split(";")
    .map(function (s) { return s.trim(); })
    .find(function (s) { return s.startsWith("CF_Authorization="); });

  const token = header || (cookie ? cookie.slice("CF_Authorization=".length) : null);
  if (!token) return null;

  const parts = token.split(".");
  if (parts.length !== 3) return null;

  const head = b64urlToJson(parts[0]);
  const payload = b64urlToJson(parts[1]);

  /* 이 애플리케이션에 발급된 토큰이 맞는지 */
  const aud = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (aud.indexOf(env.ACCESS_AUD) === -1) return null;

  /* 만료 확인 */
  if (payload.exp && payload.exp * 1000 < Date.now()) return null;

  /* 서명 확인 — 이게 있어야 위조를 막습니다 */
  const keys = await getAccessKeys(env);
  const jwk = keys.find(function (k) { return k.kid === head.kid; });
  if (!jwk) return null;

  const key = await crypto.subtle.importKey(
    "jwk",
    jwk,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"]
  );

  const signed = new TextEncoder().encode(parts[0] + "." + parts[1]);
  const ok = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    key,
    b64urlToBytes(parts[2]),
    signed
  );
  if (!ok) return null;

  return payload.email || null;
}

/* ── 데이터베이스 ─────────────────────────────── */
function requireDb(env) {
  if (!env.BOARD_DB) {
    throw new Error("D1 바인딩(BOARD_DB)이 없습니다. Worker 설정에서 연결해 주세요.");
  }
  return env.BOARD_DB;
}

/* 표가 없으면 만들어 둡니다. 이미 있으면 아무 일도 하지 않습니다. */
let schemaReady = false;
async function ensureTable(env) {
  if (schemaReady) return;
  await requireDb(env).prepare(SCHEMA).run();
  schemaReady = true;
}

async function readBoard(env, owner) {
  await ensureTable(env);
  const row = await requireDb(env)
    .prepare("SELECT data, updated_at FROM board WHERE owner = ?")
    .bind(owner)
    .first();

  if (!row) return { data: null, updatedAt: null };
  return { data: JSON.parse(row.data), updatedAt: row.updated_at };
}

async function writeBoard(env, owner, data) {
  await ensureTable(env);
  const now = new Date().toISOString();

  await requireDb(env)
    .prepare(
      `INSERT INTO board (owner, data, updated_at) VALUES (?, ?, ?)
       ON CONFLICT(owner) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at`
    )
    .bind(owner, JSON.stringify(data), now)
    .run();

  return now;
}

/* ── 입구 ─────────────────────────────── */
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (!url.pathname.startsWith("/api/board")) {
      return fail(404, "여기는 보드 저장 서버입니다. /api/board 로 요청하세요.");
    }

    /* 설정이 제대로 됐는지 눈으로 확인하는 용도 */
    if (url.pathname === "/api/board/health") {
      let email = null;
      let error = null;
      try { email = await whoIsAsking(request, env); }
      catch (e) { error = String(e.message || e); }

      return json({
        ok: true,
        db: !!env.BOARD_DB,
        accessTeam: !!env.ACCESS_TEAM,
        accessAud: !!env.ACCESS_AUD,
        signedInAs: email,
        error: error,
      });
    }

    let owner;
    try {
      owner = await whoIsAsking(request, env);
    } catch (e) {
      return fail(500, String(e.message || e));
    }

    if (!owner) {
      return fail(401, "로그인 정보를 확인하지 못했습니다. 사이트에 다시 로그인해 주세요.");
    }

    try {
      if (request.method === "GET") {
        const got = await readBoard(env, owner);
        return json({ ok: true, owner: owner, data: got.data, updatedAt: got.updatedAt });
      }

      if (request.method === "PUT") {
        const body = await request.json();
        if (!body || typeof body !== "object" || !("data" in body)) {
          return fail(400, "저장할 내용(data)이 없습니다.");
        }
        const at = await writeBoard(env, owner, body.data);
        return json({ ok: true, updatedAt: at });
      }

      return fail(405, "GET 또는 PUT 만 됩니다.");
    } catch (e) {
      return fail(500, String(e.message || e));
    }
  },
};
