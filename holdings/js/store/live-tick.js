/* 실시간 체결 — 보고 있는 종목 하나의 마지막 체결을 서버가 알려 준다 (2026-11-05 재권님 「나로 하는걸 진행해봐」).

   전에는 차트 맨 오른쪽 봉이 묶음 시세(서버 `MULTI_CACHE_TTL` 2초)를 따라 2초 계단으로 움직였다.
   서버(server/kis_ws.py)가 증권사 실시간 체결을 받아 들고 있다가, 이 모듈이 묻는
   `/api/kis/live?code=…&seq=…` 를 **새 체결이 올 때까지 쥐었다가** 바로 낸다 — 화면이 주기로 다시 묻지 않는다.

   쉬는 간격 · 낡음 기준은 서버 값이다(`kis_ws.LIVE_GAP_SEC` · `LIVE_STALE_SEC` · `LIVE_OFF_RETRY_SEC`) — 숫자는 서버가 없을 때 쓰는 대체값뿐.
   서버가 `kisWs` 를 참으로 안 주면(꺼짐) 아예 묻지 않는다. 묶음 시세는 그대로 돈다 — 이것은 그 위에 얹는 것이다.

   `withLive(code, row)` — 묶음 시세 한 줄에 그보다 새 체결을 얹는다. 묶음 시세가 2초 묵은 값으로
   다시 와도 가격이 한 칸 뒤로 돌아가지 않게, 시세 줄을 쓰는 자리(머리 가격 · 차트 끝 봉)는 이것을 거친다. */

import { apiFetch } from '../data/api.js';
import { loadTiming, serverFlag, serverMs } from './timing.js';

const GAP_FALLBACK_MS = 200;
const STALE_FALLBACK_MS = 5000;
const OFF_FALLBACK_MS = 60000;

const last = new Map();          // 종목 → { tick, at(받은 시각 ms) }

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** 그 종목의 새 체결(낡지 않은 것) — 없으면 null */
export function freshTick(code) {
  const v = code && last.get(code);
  if (!v) return null;
  return Date.now() - v.at < serverMs('kis_ws.LIVE_STALE_SEC', STALE_FALLBACK_MS) ? v.tick : null;
}

/** 묶음 시세 한 줄에 새 체결을 얹는다. 체결이 없거나 낡았으면 그 줄 그대로 */
export function withLive(code, row) {
  const t = freshTick(code);
  if (!t) return row;
  const out = { ...(row || {}) };
  for (const k of ['price', 'amt', 'pct', 'open', 'volume', 'value']) {
    if (t[k] != null) out[k] = t[k];
  }
  if (t.high != null) out.high = out.high != null ? Math.max(out.high, t.high) : t.high;
  if (t.low != null) out.low = out.low != null ? Math.min(out.low, t.low) : t.low;
  return out;
}

/**
 * 고른 종목의 체결을 지켜본다. `getCode()` 가 null 이면 쉰다.
 * @returns {{ stop: () => void }}
 */
export function watchLive(getCode, onTick) {
  let dead = false;
  let ctrl = null;
  let code = null;
  /* 쥐고 있는 사이 종목이 바뀌면 그 물음을 끊는다 — 안 끊으면 새 종목 체결이 쥔 시간(서버 `LIVE_HOLD_SEC`)만큼 늦는다.
     서버에 묻는 주기가 아니라 이 화면 안의 값만 본다 */
  const watchCode = setInterval(() => { if (ctrl && code && getCode() !== code) ctrl.abort(); }, 300);
  (async () => {
    await loadTiming();
    if (!serverFlag('kisWs')) { clearInterval(watchCode); return; }   // 서버에 실시간이 없다 — 묶음 시세만
    let seq = 0;
    while (!dead) {
      if (document.hidden) { await sleep(1000); continue; }
      const want = getCode();
      if (!want) { await sleep(1000); continue; }
      if (want !== code) { code = want; seq = 0; }
      ctrl = new AbortController();
      let j = null;
      try {
        const r = await apiFetch(`/api/kis/live?code=${encodeURIComponent(code)}&seq=${seq}`,
                                 { cache: 'no-store', signal: ctrl.signal });
        j = await r.json();
      } catch {
        if (dead) return;
        if (getCode() !== code) continue;                // 종목이 바뀌어 끊었다 — 바로 새 종목으로
        await sleep(serverMs('kis_ws.LIVE_OFF_RETRY_SEC', OFF_FALLBACK_MS) / 10);   // 서버가 잠깐 없다
        continue;
      }
      if (dead) return;
      if (!j || j.on === false || j.ok === false) {
        await sleep(serverMs('kis_ws.LIVE_OFF_RETRY_SEC', OFF_FALLBACK_MS));
        continue;
      }
      if (j.changed && j.tick && j.tick.code === code && getCode() === code) {
        seq = j.tick.seq;
        last.set(code, { tick: j.tick, at: Date.now() });
        try { onTick(j.tick); } catch (e) { console.error(e); }
      } else if (j.seq != null) {
        seq = Math.max(seq, j.seq);
      }
      await sleep(serverMs('kis_ws.LIVE_GAP_SEC', GAP_FALLBACK_MS));
    }
  })();
  return {
    stop() {
      dead = true;
      clearInterval(watchCode);
      if (ctrl) { try { ctrl.abort(); } catch { /* 이미 끝남 */ } }
    },
  };
}
