/* ==========================================================================
   큰 차트 바닥 줄 — 외국계 창구 · 프로그램 매수세 / 매도세 (2026-11-03)

   재권님 — 「차트 아래에 현재 기관과 외국인 프로그램 들이 사는게 강한지 파는게 약한지 알수 있으면 좋을거 같은데」
   → 시안 여덟 판 → 「종목 프로그램 매매 · 외국계 창구 매수 매도 필요」 · 「한줄로」 · 「금액은 빼고 시간을 넣어줘
   정보가 들어온 시간」 · 「룰대로 넣어줘」(11-03 · 보드 카드 「기관 · 외국인 · 프로그램」).

       외국계 창구 [──●──] 13:55   프로그램 [──●──] 13:55

   원 자리 = **매수 몫**(매수 ÷ (매수 + 매도) · 가운데 50%). 오른쪽이 매수세 · 왼쪽이 매도세 · 멀수록 짙다.
   기준 · 폭은 지표 표(data/metrics.json 의 buy_share)에 있고 쪽 · 짙기 셈은 assets/js/tone.js 한 곳이다
   (「기준이 있는 수치는 위 빨강 · 아래 파랑, 멀수록 짙게」) — 표에 없으면 원을 가운데 회색으로 두고 tone.js 가 콘솔에 알린다.
   글자는 **정보가 들어온 시각**이다 — 금액은 안 쓴다.

   값 출처 — 둘 다 서버가 이미 받는 주소다(KIS 호출을 새로 만들지 않는다)
     외국계 창구  /api/kis/investor-member 의 foreignFirms.buy · sell(수량 · KRX 회원사 중 외국계 합 · 외국인 전체 아님)
                  시각 = 서버가 KIS 에서 받은 시각(at)
     프로그램     /api/kis/flow-today?code=&step=5 의 stock.rows 의 buy · sell 합(원 · 서버가 1분마다 쌓음)
                  시각 = 서버가 마지막으로 쌓은 시각(stock.lastAt)
   기관 · 외국인 전체는 장중 실시간 원천이 없어 뺐다(종목 가집계는 하루 다섯 번뿐).

   다시 묻는 주기는 서버가 준다(롱폴 · 폴백은 각 주소의 서버 캐시 값) — 화면에 주기 숫자를 두지 않는다.
   ========================================================================== */

import { watch } from '../store/longpoll.js';
import { ready as toneReady, tone, paint } from '../../../assets/js/tone.js';

const ID = 'buy_share';                         // data/metrics.json 의 이름
const KEYS = { mem: 'kis_proxy.INVESTOR_MEMBER_TTL', flow: 'intraday_flow.CACHE_TTL' };
const FALLBACK_MS = 60000;                      // 서버 값마저 못 받았을 때만

let code = null;
let data = { mem: null, flow: null };           // 마지막으로 받은 값 — 바닥 줄을 다시 그려도 깜빡이지 않게 들고 있는다
let watches = null;
let footEl = null;

const get = (u) => fetch(u, { cache: 'no-store' }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
const hm = (s) => (s ? String(s).replace(/^(\d\d)(\d\d)$/, '$1:$2') : null);

function share(buy, sell) {
  if (buy == null || sell == null || !(buy + sell > 0)) return null;
  return buy / (buy + sell) * 100;
}

function items() {
  const ff = data.mem && data.mem.code === code ? data.mem.foreignFirms : null;
  const sk = data.flow && data.flow.code === code ? data.flow : null;
  const rows = (sk && sk.rows) || [];
  const sum = (k) => (rows.length ? rows.reduce((a, r) => a + (r[k] || 0), 0) : null);
  return [
    { n: '외국계 창구', p: ff ? share(ff.buy, ff.sell) : null, t: data.mem && data.mem.code === code ? data.mem.at : null },
    { n: '프로그램', p: share(sum('buy'), sum('sell')), t: sk ? hm(sk.lastAt) : null },
  ];
}

function dot(p) {
  const { side, k } = p == null ? { side: null, k: 0 } : tone(ID, p);
  if (side !== 'up' && side !== 'down') return '<span class="kh-ff-bar"><i class="kh-ff-mid"></i></span>';
  const x = 50 + (side === 'up' ? 1 : -1) * k * 50;
  const c = paint(ID, p, 'line');
  const fill = side === 'up' ? `left:50%;width:${(x - 50).toFixed(1)}%` : `left:${x.toFixed(1)}%;width:${(50 - x).toFixed(1)}%`;
  return `<span class="kh-ff-bar"><i class="kh-ff-mid"></i><i class="kh-ff-fill ${side}" style="${fill};background:${c}"></i>` +
    `<i class="kh-ff-dot" style="left:${x.toFixed(1)}%;background:${c};--kh-ff-c:${c}"></i></span>`;
}

function render() {
  if (!footEl || !footEl.isConnected || !code) return;
  let el = footEl.querySelector('.kh-flow-foot');
  if (!el) {
    el = document.createElement('span');
    el.className = 'kh-flow-foot';
    footEl.insertBefore(el, footEl.lastElementChild);   // 왼쪽 설명 뒤 · 오른쪽 출처 앞
  }
  el.innerHTML = items().map((x) =>
    `<span class="kh-ff-it" title="${x.n} — 원이 오른쪽이면 매수세 · 왼쪽이면 매도세 · 시각은 정보가 들어온 때">` +
    `<span class="kh-ff-n">${x.n}</span>${dot(x.p)}<span class="kh-ff-t">${x.t || '—'}</span></span>`).join('');
}

async function loadMem() {
  const c = code;
  if (!c) return;
  const j = await get(`/api/kis/investor-member?code=${c}`);
  if (c !== code) return;
  if (j && j.data) data.mem = { code: c, foreignFirms: j.data.foreignFirms || null, at: j.data.at || null };
  render();
}

async function loadFlow() {
  const c = code;
  if (!c) return;
  const j = await get(`/api/kis/flow-today?step=5&code=${c}`);
  if (c !== code) return;
  const sk = j && j.data && j.data.stock;
  if (sk) data.flow = { code: c, rows: sk.rows || [], lastAt: sk.lastAt || null };
  render();
}

/**
 * 바닥 줄에 붙인다 · 고른 종목이 바뀌거나 바닥 줄을 새로 썼을 때마다 부른다.
 * @param {HTMLElement} foot  `#kh-big-foot` — 안의 글을 다시 써도 이 함수를 부르면 다시 붙는다
 * @param {string|null} c     종목 코드. 없으면(시장 지표를 보는 중) 줄을 뺀다
 */
export function paintFlowFoot(foot, c) {
  footEl = foot;
  if (!c) {
    const el = foot && foot.querySelector('.kh-flow-foot');
    if (el) el.remove();
    code = null;
    return;
  }
  const changed = c !== code;
  code = c;
  toneReady.then(render);
  if (!watches) {
    watches = [
      watch({ url: () => (code ? `/api/kis/investor-member?code=${code}` : null), onChange: loadMem, key: KEYS.mem, fallbackMs: FALLBACK_MS }),
      watch({ url: () => (code ? `/api/kis/flow-today?step=5&code=${code}` : null), onChange: loadFlow, key: KEYS.flow, fallbackMs: FALLBACK_MS }),
    ];
  }
  if (changed) {
    watches.forEach((w) => w.refresh());
    loadMem();
    loadFlow();
  }
}
