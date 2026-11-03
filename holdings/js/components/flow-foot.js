/* ==========================================================================
   큰 차트 바닥 줄 — 외국계 창구 · 프로그램 매수세 / 매도세 (2026-11-03)

   재권님 — 「차트 아래에 현재 기관과 외국인 프로그램 들이 사는게 강한지 파는게 약한지 알수 있으면 좋을거 같은데」
   → 시안 여덟 판 → 「종목 프로그램 매매 · 외국계 창구 매수 매도 필요」 · 「한줄로」 · 「금액은 빼고 시간을 넣어줘
   정보가 들어온 시간」 · 「룰대로 넣어줘」(11-03 · 보드 카드 「기관 · 외국인 · 프로그램」).

       외국계 창구 [──●──] 13:55   프로그램 [──●──] 13:55

   원 자리 = **오늘 누적 매수 몫**(매수 ÷ (매수 + 매도) · 가운데 50%). 오른쪽으로 갈수록 매수 쪽 · 멀수록 짙다.
   원 색 = **앞 값과 견준 새 몫**(재권님 11-03 「1분마다 정보를 가져오니 그정보가 전값이랑 비교해서 매수세면 원이 빨강
   매도세면 파랑」) — 새로 받은 값의 매수 · 매도가 앞 값보다 각각 얼마 늘었나를 견줘 매수가 더 늘었으면 빨강 · 매도가 더 늘었으면 파랑.
   늘어난 것이 없으면 앞 색 그대로 · 앞 값이 아직 없으면(이 화면에서 첫 값) 회색. 짙기는 누적 몫의 짙기 그대로다.
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

/* 앞 값과 견준 쪽 — 같은 종목의 앞 값이 있을 때만. 늘어난 것이 없으면 앞 쪽 그대로 */
function dirOf(prev, buy, sell, c) {
  if (!prev || prev.code !== c || prev.buy == null || buy == null) return null;
  const db = buy - prev.buy, ds = sell - prev.sell;
  if (db === ds) return prev.dir || null;
  return db > ds ? 'up' : 'down';
}
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
    { n: '외국계 창구', p: ff ? share(ff.buy, ff.sell) : null, t: data.mem && data.mem.code === code ? data.mem.at : null, d: data.mem && data.mem.code === code ? data.mem.dir : null },
    { n: '프로그램', p: share(sum('buy'), sum('sell')), t: sk ? hm(sk.lastAt) : null, d: sk ? sk.dir : null },
  ];
}

function dot(p, d) {
  const { side, k } = p == null ? { side: null, k: 0 } : tone(ID, p);
  if (side !== 'up' && side !== 'down') return '<span class="kh-ff-bar"><i class="kh-ff-mid"></i></span>';
  const x = 50 + (side === 'up' ? 1 : -1) * k * 50;
  /* 색은 앞 값과 견준 쪽(d) · 짙기는 누적 몫(p) 그대로 — 쪽만 다르면 기준을 사이에 두고 뒤집은 값으로 tone.js 에 묻는다 */
  const c = !d ? 'var(--kh-text-muted)' : paint(ID, d === side ? p : 100 - p, 'line');
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
    `<span class="kh-ff-it" title="${x.n} — 원 자리는 오늘 누적(오른쪽 매수 · 왼쪽 매도) · 원 색은 앞 값보다 매수가 더 늘면 빨강 · 매도가 더 늘면 파랑 · 시각은 정보가 들어온 때">` +
    `<span class="kh-ff-n">${x.n}</span>${dot(x.p, x.d)}<span class="kh-ff-t">${x.t || '—'}</span></span>`).join('');
}

async function loadMem() {
  const c = code;
  if (!c) return;
  const j = await get(`/api/kis/investor-member?code=${c}`);
  if (c !== code) return;
  if (j && j.data) {
    const ff = j.data.foreignFirms || null;
    const prev = data.mem && data.mem.foreignFirms ? { code: data.mem.code, buy: data.mem.foreignFirms.buy, sell: data.mem.foreignFirms.sell, dir: data.mem.dir } : null;
    data.mem = { code: c, foreignFirms: ff, at: j.data.at || null, dir: ff ? dirOf(prev, ff.buy, ff.sell, c) : null };
  }
  render();
}

async function loadFlow() {
  const c = code;
  if (!c) return;
  const j = await get(`/api/kis/flow-today?step=5&code=${c}`);
  if (c !== code) return;
  const sk = j && j.data && j.data.stock;
  if (sk) {
    const rows = sk.rows || [];
    const sum = (k) => (rows.length ? rows.reduce((a, r) => a + (r[k] || 0), 0) : null);
    const buy = sum('buy'), sell = sum('sell');
    data.flow = { code: c, rows, lastAt: sk.lastAt || null, buy, sell, dir: dirOf(data.flow, buy, sell, c) };
  }
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
