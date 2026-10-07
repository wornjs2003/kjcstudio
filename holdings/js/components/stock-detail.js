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

import { apiFetch, viewUrl } from '../data/api.js';
import { fmtMoneyKr, fmtUsdBig, isUsCode } from '../utils/format.js';
import { watch } from '../store/longpoll.js';

/* **주기를 갖지 않는다 — 바뀌면 서버가 알려 준다** (2026-10-02 · 재권님 「주는 대로
   받아야」). `store/longpoll.js` 가 한 연결로 묻는다. 서버가 롱폴을 모르면 호가는
   `ASKING_TTL`, 시세는 `PRICE_CACHE_TTL` 주기로 묻는다 — 아래 숫자는 **그 값마저
   못 받았을 때의 대체값**이다 */
const ASK_RELOAD_KEY = 'kis_proxy.ASKING_TTL';
const ASK_RELOAD_FALLBACK_MS = 5000;

/* **시가총액은 고른 종목만 따로 받는다.**

   순위표는 멀티 조회(`/api/kis/quotes`)로 200종목을 한 번에 받는데, 그것은
   **시가총액·PER·PBR·52주를 안 준다**(live.js 주석). 그래서 이 칸이 「—」로
   나왔다. 단건(`/api/kis/price`)에는 있으므로 고른 하나만 받는다.

   주기는 서버의 `PRICE_CACHE_TTL` 이다(위). */
const LIVE_RELOAD_KEY = 'kis_proxy.PRICE_CACHE_TTL';
const LIVE_RELOAD_FALLBACK_MS = 30_000;

/* `onOne(code, 단건)` — 단건을 받을 때마다 알린다 (2026-10-06 지시 — 「로딩 순서 체크해 봐」 → 「응」).
   첫 화면의 52주 칸과 큰 차트 머리 현재가가 **같은 단건을 따로 또 부르거나**(같은 주소 두 번)
   **1초 넘는 묶음 시세를 기다리던** 것을 이 응답 하나로 칠한다. 증권사 호출이 한 건 준다. */
export function mountStockDetail(host, { view, onOne } = {}) {
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
      const r = await apiFetch(viewUrl(`/api/kis/asking?code=${code}`, view), { cache: 'no-store' });
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
      const r = await apiFetch(viewUrl(`/api/kis/price?code=${code}`, view), { cache: 'no-store' });
      if (!r || !r.ok) throw new Error(r && r.status);
      const b = await r.json();
      if (mine !== seq) return;          // 그새 종목이 바뀌었다
      one = (b && b.ok && b.data) ? b.data : null;
    } catch {
      one = null;
    }
    paint();
    if (one && onOne) onOne(code, one);
  }

  function paint() {
    /* 실제 거래대금(value)이 오면 그것을 쓴다. 없을 때만 어림하고
       **어림인 것을 숨기지 않는다** — 오른 날에는 부풀려지기 때문이다. */
    const src = { ...(live || {}), ...(one || {}) };
    const exact = src.value != null;
    const raw = src.value ?? (src.price != null && src.volume != null
      ? src.price * src.volume : null);
    /* 미국 종목(2026-10-07)은 거래대금 · 시가총액이 달러 그대로 온다 — 원 · 억원으로 읽으면 「576,568,400조원」 이 됐다 */
    const us = isUsCode(code);
    const amt = raw == null ? '—' : (us ? fmtUsdBig(raw) : fmtMoneyKr(Math.round(raw / 1e8)));
    const cap = src.marketCap == null ? '—' : (us ? fmtUsdBig(src.marketCap) : fmtMoneyKr(src.marketCap));

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

  /* 주소는 고른 종목을 따라간다 — `setCode` 가 `refresh()` 로 알린다 */
  timer = watch({ url: () => (code ? viewUrl(`/api/kis/asking?code=${code}`, view) : null),
                  onChange: () => loadAsking(), key: ASK_RELOAD_KEY, fallbackMs: ASK_RELOAD_FALLBACK_MS });
  liveTimer = watch({ url: () => (code ? viewUrl(`/api/kis/price?code=${code}`, view) : null),
                      onChange: () => loadLive(), key: LIVE_RELOAD_KEY, fallbackMs: LIVE_RELOAD_FALLBACK_MS });
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
      timer.refresh();          // 쥔 연결이 옛 종목을 보고 있다
    },
    /** **받아 둔 단건 응답을 그대로 내준다** (2026-09-30 지시 —
     *  「모달에 있는건 가져와야지 왜 안가져오고있지?」).
     *
     *  모달 위 요약 줄(`stock-view.js` 의 `paintHead`)은 카드에서 오는
     *  **멀티 조회** 값을 받는데, 거기에는 시가총액·52주·PER·PBR 이 **없다**
     *  (`/api/kis/quotes` 11필드 ↔ `/api/kis/prices` 14필드).
     *  그래서 한 모달 안에서 **위는 `—`, 아래 차트 머리줄은 1,572.6조원** 이
     *  나란히 보였다 — 2026-09-30 실측.
     *
     *  **여기는 이미 단건(`/api/kis/price`)을 받고 있다.** 새로 받지 않고
     *  그것을 나눠 쓴다 — **증권사 호출이 안 는다.**
     *
     *  아직 안 왔으면 `null` 이다. 받는 쪽은 `{ ...멀티, ...이것 }` 으로
     *  합친다 — 아래 `paint()` 가 쓰는 그 방식이고, **뒤에 놓아야
     *  멀티가 덮지 못한다.** */
    full() {
      return one;
    },

    /** 시세가 새로 왔을 때 부른다 — 거래대금·시가총액이 그것으로 그려진다 */
    update(nextLive) {
      live = nextLive || null;
      paint();
    },
    destroy() {
      if (timer) timer.stop();
      if (liveTimer) liveTimer.stop();
    },
  };
}
