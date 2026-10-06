/*
 * 이 워커는 꺼짐 감시만 한다 — 2026-10-06 재권님 「ㄴ」.
 *
 * 붙여 넣는 곳: Cloudflare 워커 kjc-kis-kv (Edit code → 전부 지우고 붙여 넣기 → Deploy).
 * 끝이 `};` 인지 본다.
 *
 * ── 하는 일 둘 ──
 *
 *   fetch      받은 요청을 손대지 않고 원래 가던 곳(터널 → 맥미니)으로 넘긴다.
 *   scheduled  Cron(5분)마다 맥미니가 KV 에 남긴 「살아 있다」 신호를 읽어
 *              문제가 생기거나 풀리면 텔레그램으로 한 번 알린다.
 *
 * **꺼진 맥미니는 스스로 못 알린다.** 그래서 밖에서 본다 — 맥미니
 * (`holdings/server/heartbeat.py`)가 5분마다 KV 키 `alive:main` 에 상태를 덮어쓰고,
 * 여기서 그것을 읽는다.
 *
 * **상태가 바뀔 때만 보낸다.** 지금 문제를 한 줄로 만들어 KV 키 `alive:state` 에
 * 적힌 지난번 것과 견주고, 다를 때만 보낸다. 그래서 같은 알림은 한 번이고,
 * 풀리면 「돌아왔다」 가 한 번 간다.
 *
 * ── 필요한 설정 (옛 kjc-kis-kv 설정 그대로) ──
 *
 *   KV 바인딩   KIS_KV               맥미니가 쓰는 그 KV
 *   Secret      TELEGRAM_BOT_TOKEN   알림 봇 — 없으면 알림만 안 간다
 *   Secret      TELEGRAM_CHAT_ID     받는 대화방
 *   Cron        5분마다
 *
 * **꺼졌다고 보는 기준(초)은 맥미니가 신호에 실어 보낸다**(`aliveStaleSec`).
 * 값은 heartbeat.py 의 ALIVE_STALE_SEC 한 곳이다 — 여기 따로 두지 않는다.
 * 신호에 없으면 900(15분)을 쓴다.
 *
 * 되돌리기: 통과만 하려면 맨 아래 `scheduled` 안을 비운다. 옛 전체 워커는
 * git 이력의 holdings/worker/kis-worker.js(4651907 직전).
 */

const ALIVE_KEY = "alive:main";
const STATE_KEY = "alive:state";
const STALE_DEFAULT_SEC = 900;

/** 지금 문제를 [견줄 이름, 보낼 글] 목록으로. 비어 있으면 멀쩡하다.

    **견주는 것은 이름이지 글이 아니다.** 글에는 「16분째」 처럼 시간이 들어가
    Cron 마다 바뀌는데, 그것으로 견주면 꺼져 있는 동안 5분마다 다시 울린다
    (2026-10-06 가짜 시험에서 찾았다). */
function aliveProblems(beat, nowSec) {
  const out = [];
  if (!beat || !beat.ts) {
    out.push(["never", "신호가 한 번도 안 왔습니다"]);
    return out;
  }
  const stale = Number(beat.aliveStaleSec) > 0 ? Number(beat.aliveStaleSec) : STALE_DEFAULT_SEC;
  const age = nowSec - beat.ts;
  if (age > stale) {
    out.push(["down", `맥미니가 꺼진 것 같습니다 — 신호가 ${Math.floor(age / 60)}분째 없습니다`]);
    return out;   // 꺼졌으면 나머지 값은 낡은 것이라 안 본다
  }
  if (beat.tokenOk === false) out.push(["token", "KIS 토큰이 안 됩니다 — 시세가 안 옵니다"]);
  if (beat.dartLastError) out.push(["dart", `공시 수집 오류 — ${String(beat.dartLastError).slice(0, 80)}`]);
  if (beat.dailyToday === false) out.push(["daily", "오늘 데일리분석이 저장되지 않았습니다"]);
  return out;
}

async function telegramSend(env, text) {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) return false;
  try {
    const res = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        chat_id: String(env.TELEGRAM_CHAT_ID), text, disable_web_page_preview: "true",
      }),
    });
    const body = await res.json();
    return !!body.ok;
  } catch {
    return false;
  }
}

async function checkAlive(env) {
  if (!env.KIS_KV) return;
  let raw = null;
  try { raw = await env.KIS_KV.get(ALIVE_KEY); } catch { return; }

  let beat = null;
  try { beat = raw ? JSON.parse(raw) : null; } catch { beat = null; }

  const nowSec = Math.floor(Date.now() / 1000);
  const problems = aliveProblems(beat, nowSec);
  const now = problems.map((p) => p[0]).join(" | ");
  let before = "";
  try { before = (await env.KIS_KV.get(STATE_KEY)) || ""; } catch { return; }

  if (now === before) return;          // 안 바뀌었으면 아무 말도 안 한다

  const text = problems.length
    ? "⚠️ 서버 상태\n\n" + problems.map((p) => "· " + p[1]).join("\n")
    : "✅ 서버가 정상으로 돌아왔습니다";
  /* **먼저 기록하고 보낸다.** 반대로 하면 보내기가 실패했을 때 다음 Cron 에
     또 보내려 하는데, 그때는 이미 상태가 같아 보여 영영 안 간다. */
  try { await env.KIS_KV.put(STATE_KEY, now); } catch { return; }
  await telegramSend(env, text);
}

export default {
  async fetch(request) {
    try {
      return await fetch(request);
    } catch (e) {
      return new Response("통과 워커가 맥미니로 넘기지 못했습니다.", {
        status: 502,
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }
  },

  async scheduled(controller, env, ctx) {
    ctx.waitUntil(checkAlive(env).catch(() => {}));
  },
};
