/* 호가 10단 — 투자자 정보 칸 아래 작은 막대 그래프 · 종목 화면 「호가」 칸 10단 표 (2026-11-06)

   재권님 — 홈 훑기 12 「단기매매 정보 더하기」 후보 넷을 보시고 「이거 다 넣으면 좋을 거 같은데 마우스 올리면 설명도 넣고」 →
   그림(가) 「응 만들어」. 투자자 정보 칸에 남던 빈자리에 넣는다 — 칸 높이를 안 바꾼다(css/depth.css).

   왼쪽 열 개가 매도(먼 값 → 가까운 값) · 가운데 선이 지금 자리 · 오른쪽 열 개가 매수(가까운 값 → 먼 값).
   막대 높이는 그 가격에 걸린 잔량 — 스무 개 중 가장 큰 것에 맞춘다. 마우스를 올리면 가격 · 잔량.

   값은 서버 /api/kis/asking 그대로다(차트 머리줄의 매수 · 매도 비율과 같은 주소 — 한 연결로 지켜본다 · store/longpoll.js).
   **주기를 갖지 않는다** — 바뀌면 서버가 알린다. 아래 숫자는 서버 값(kis_proxy.ASKING_TTL)마저 못 받았을 때의 대체값이다. */
import { apiFetch } from '../data/api.js';
import { watch } from '../store/longpoll.js';
import { isUsCode } from '../utils/format.js';

const ASK_RELOAD_KEY = 'kis_proxy.ASKING_TTL';
const ASK_RELOAD_FALLBACK_MS = 5000;
const URL = code => `/api/kis/asking?code=${code}`;

const fmt = n => Number(n).toLocaleString('ko-KR');

/* 같은 값을 받아 그리는 두 모양이 같은 받기를 쓴다 — 작은 막대(홈 · 서랍 패널)와 10단 표(종목 화면 「호가」 칸) */
function makeDepth(host, paintWith) {
  if (!host) return { setCode() {}, destroy() {} };
  let code = null, seq = 0, data = null, failed = false;
  const paint = () => paintWith(host, code, data, failed);

  async function load() {
    if (!code || isUsCode(code)) { data = null; paint(); return; }
    const mine = ++seq;
    try {
      const r = await apiFetch(URL(code), { cache: 'no-store' });
      if (!r || !r.ok) throw new Error(r && r.status);
      const b = await r.json();
      if (mine !== seq) return;
      data = b && b.data; failed = false;
    } catch {
      if (mine !== seq) return;
      data = null; failed = true;
    }
    paint();
  }

  const timer = watch({ url: () => (code && !isUsCode(code) ? URL(code) : null),
                        onChange: () => load(), key: ASK_RELOAD_KEY, fallbackMs: ASK_RELOAD_FALLBACK_MS });
  paint();

  return {
    setCode(next) {
      if (!next || next === code) return;
      code = next; data = null; failed = false; seq++;
      paint(); load(); timer.refresh();
    },
    destroy() { timer.stop(); },
  };
}

/* 10단에서 걸린 것만 — 매도는 먼 값 → 가까운 값(위 → 아래), 매수는 가까운 값 → 먼 값 */
const sides = data => ({
  ask: ((data && data.ask && data.ask.levels) || []).filter(l => l.qty > 0).slice().reverse(),
  bid: ((data && data.bid && data.bid.levels) || []).filter(l => l.qty > 0),
});
const emptyText = (data, failed) => data ? '걸린 주문 없음' : failed ? '불러오지 못함' : '불러오는 중';

/* 종목 화면 「호가」 칸 — 10단 표(2026-11-06 재권님 「응 해줘」 · 원래 「연결 예정」 으로 비워 둔 칸).
   한 줄에 매도 잔량 | 가격 | 매수 잔량 · 잔량 칸 바탕 막대 폭은 스무 칸 중 가장 큰 잔량에 맞춘다 */
export function mountDepthTable(host) {
  return makeDepth(host, (host, code, data, failed) => {
    host.classList.add('kh-dpt');
    if (isUsCode(code)) { host.innerHTML = '<div class="kh-dpt-e">미국 종목은 호가를 안 받습니다</div>'; return; }
    const { ask, bid } = sides(data);
    if (!ask.length && !bid.length) { host.innerHTML = `<div class="kh-dpt-e">${emptyText(data, failed)}</div>`; return; }
    const max = Math.max(1, ...ask.map(l => l.qty), ...bid.map(l => l.qty));
    const w = q => Math.round(q / max * 100);
    const row = (l, side) => side === 'ask'
      ? `<div class="kh-dpt-r is-ask"><span class="kh-dpt-q"><i style="width:${w(l.qty)}%"></i>${fmt(l.qty)}</span><b>${fmt(l.price)}</b><span></span></div>`
      : `<div class="kh-dpt-r is-bid"><span></span><b>${fmt(l.price)}</b><span class="kh-dpt-q"><i style="width:${w(l.qty)}%"></i>${fmt(l.qty)}</span></div>`;
    host.innerHTML = `
      <div class="kh-dpt-hd"><span>매도 잔량</span><span>가격</span><span>매수 잔량</span></div>
      ${ask.map(l => row(l, 'ask')).join('')}${bid.map(l => row(l, 'bid')).join('')}
      <div class="kh-dpt-ft"><span class="kh-down">${data.ask ? fmt(data.ask.total) : '—'}</span><span>합계(주)</span><span class="kh-up">${data.bid ? fmt(data.bid.total) : '—'}</span></div>`;
  });
}

export function mountDepth(host) {
  return makeDepth(host, (host, code, data, failed) => {
    host.classList.add('kh-dp');
    const head = '<b class="kh-dp-t">호가 10단</b>';
    if (isUsCode(code)) { host.innerHTML = `<div class="kh-dp-h">${head}<span>미국 종목은 호가를 안 받습니다</span></div>`; return; }
    const { ask, bid } = sides(data);
    if (!ask.length && !bid.length) { host.innerHTML = `<div class="kh-dp-h">${head}<span>${emptyText(data, failed)}</span></div>`; return; }
    const max = Math.max(1, ...ask.map(l => l.qty), ...bid.map(l => l.qty));
    const bar = (l, side) => `<i class="kh-dp-${side}" title="${fmt(l.price)}원 · ${fmt(l.qty)}주" style="height:${Math.max(6, Math.round(l.qty / max * 100))}%"></i>`;
    const near = bid[0] || ask[ask.length - 1];
    host.innerHTML = `
      <div class="kh-dp-h">${head}
        <span>매도 <b class="kh-down">${data.ask ? fmt(data.ask.total) : '—'}</b> · 매수 <b class="kh-up">${data.bid ? fmt(data.bid.total) : '—'}</b>주</span></div>
      <div class="kh-dp-g">${ask.map(l => bar(l, 'ask')).join('')}<em></em>${bid.map(l => bar(l, 'bid')).join('')}</div>
      <div class="kh-dp-x"><span>${ask.length ? fmt(ask[0].price) : ''}</span><span>매도 ← ${fmt(near.price)} → 매수</span><span>${bid.length ? fmt(bid[bid.length - 1].price) : ''}</span></div>`;
  });
}
