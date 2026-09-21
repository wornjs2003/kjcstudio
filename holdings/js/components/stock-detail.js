/* ==========================================================================
   세부사항 — 차트 머리줄의 보조지표 옆 (2026-09-21 지시)

   재권님 말씀 —

       세부사항에 있는 정보들은 오른쪽 차트의 보조지표 옆으로 옮겨서
       보여주는게 좋다
       기존 세부사항에는 자세히 버튼은 없어도 될거같네

   ── 무엇을 보이나 ──

       거래대금     서버가 주는 실제 값(`value`)을 먼저 쓴다. 없으면 현재가 ×
                    거래량으로 어림하고 **어림이라고 적는다** — 오른 날에는
                    장중 평균가보다 현재가가 높아 부풀려진다
       시가총액
       매수·매도    **지금 걸려 있는 주문** 비율이다. 체결된 것이 아니다 —
                    장이 끝나면 뜻이 옅어진다. 좁은 줄이라 띠와 퍼센트만 둔다

   ── 왜 패널에서 뺐나 ──

   패널은 이제 셋(투자자 정보 · AI 분석 · 종목 뉴스)이 1/3씩 쓴다. 세부사항은
   **차트를 보며 곁눈질하는 값**이라 차트 머리줄이 제자리다.

   ── 「자세히」 단추는 두지 않는다 ──

   지시 그대로다. 종목 이름 줄의 「자세히 ›」 하나만 남는다.
   ========================================================================== */

import { apiFetch } from '../data/api.js';
import { fmtMoneyKr } from '../utils/format.js';

/* 호가는 계속 움직인다. 서버 캐시가 3초라 그보다 자주 부를 이유가 없다 */
const ASK_RELOAD_MS = 5000;

/* **시가총액은 고른 종목만 따로 받는다.**

   순위표는 멀티 조회(`/api/kis/quotes`)로 200종목을 한 번에 받는데, 그것은
   **시가총액·PER·PBR·52주를 안 준다**(live.js 주석). 그래서 이 칸이 「—」로
   나왔다. 단건(`/api/kis/price`)에는 있으므로 고른 하나만 받는다.

   서버 캐시가 25초라 그보다 자주 부를 이유가 없다. */
const LIVE_RELOAD_MS = 30_000;

export function mountStockDetail(host) {
  if (!host) return { setCode() {}, update() {}, destroy() {} };

  let code = null;
  let live = null;          // 순위표가 준 시세 (가격·거래량)
  let one = null;           // 고른 종목만 따로 받은 것 (시가총액·거래대금)
  let buyPct = null;        // 매수 잔량 비중
  let seq = 0;
  let timer = null;
  let liveTimer = null;

  async function loadAsking() {
    if (!code) return;
    const mine = ++seq;
    try {
      const r = await apiFetch(`/api/kis/asking?code=${code}`, { cache: 'no-store' });
      if (!r || !r.ok) throw new Error(r && r.status);
      const b = await r.json();
      if (mine !== seq) return;          // 그새 종목이 바뀌었다
      buyPct = (b.data && b.data.buyPct != null) ? b.data.buyPct : null;
    } catch {
      buyPct = null;
    }
    paint();
  }

  async function loadLive() {
    if (!code) return;
    const mine = seq;
    try {
      const r = await apiFetch(`/api/kis/price?code=${code}`, { cache: 'no-store' });
      if (!r || !r.ok) throw new Error(r && r.status);
      const b = await r.json();
      if (mine !== seq) return;          // 그새 종목이 바뀌었다
      one = (b && b.ok && b.data) ? b.data : null;
    } catch {
      one = null;
    }
    paint();
  }

  function paint() {
    /* 실제 거래대금(value)이 오면 그것을 쓴다. 없을 때만 어림하고
       **어림인 것을 숨기지 않는다** — 오른 날에는 부풀려지기 때문이다. */
    const src = { ...(live || {}), ...(one || {}) };
    const exact = src.value != null;
    const raw = src.value ?? (src.price != null && src.volume != null
      ? src.price * src.volume : null);
    const amt = raw != null ? fmtMoneyKr(Math.round(raw / 1e8)) : '—';
    const cap = src.marketCap != null ? fmtMoneyKr(src.marketCap) : '—';

    const bs = buyPct == null ? '' : `
      <span class="kh-dt-i">
        <span class="kh-dt-l">매수·매도</span>
        <b class="kh-up">${buyPct}%</b><b class="kh-down"> · ${(Math.round((100 - buyPct) * 10) / 10)}%</b>
      </span>
      <span class="kh-dt-bar" title="지금 걸려 있는 주문입니다 — 체결된 것이 아닙니다">
        <i class="buy" style="width:${buyPct}%"></i><i class="sell" style="width:${100 - buyPct}%"></i>
      </span>`;

    host.innerHTML = `
      <span class="kh-dt-i" title="${exact ? '서버가 준 실제 거래대금입니다'
        : '현재가 × 거래량으로 어림한 값입니다'}">
        <span class="kh-dt-l">거래대금${exact ? '' : '<i>어림</i>'}</span><b>${amt}</b></span>
      <span class="kh-dt-i"><span class="kh-dt-l">시가총액</span><b>${cap}</b></span>
      ${bs}`;
  }

  timer = setInterval(() => { if (!document.hidden) loadAsking(); }, ASK_RELOAD_MS);
  liveTimer = setInterval(() => { if (!document.hidden) loadLive(); }, LIVE_RELOAD_MS);
  paint();

  return {
    setCode(next) {
      if (!next || next === code) return;
      code = next;
      buyPct = null;
      one = null;
      paint();
      loadAsking();
      loadLive();
    },
    /** 시세가 새로 왔을 때 부른다 — 거래대금·시가총액이 그것으로 그려진다 */
    update(nextLive) {
      live = nextLive || null;
      paint();
    },
    destroy() {
      if (timer) clearInterval(timer);
      if (liveTimer) clearInterval(liveTimer);
    },
  };
}
