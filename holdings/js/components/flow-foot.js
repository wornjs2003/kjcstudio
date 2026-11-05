/* ==========================================================================
   큰 차트 바닥 줄 — 그 종목의 외국계 창구 · 프로그램 매수세 / 매도세 · 외국인 · 기관 가집계 (2026-11-03 · 11-04 · 11-05 고침)

   재권님 — 「차트 아래에 현재 기관과 외국인 프로그램 들이 사는게 강한지 파는게 약한지 알수 있으면 좋을거 같은데」
   → 시안 여덟 판 → 「종목 프로그램 매매 · 외국계 창구 매수 매도 필요」 · 「한줄로」 · 「금액은 빼고 시간을 넣어줘
   정보가 들어온 시간」 · 「룰대로 넣어줘」(11-03 · 보드 카드 「기관 · 외국인 · 프로그램」).
   11-04 — 「1분별로 이지표를 이용해서 … 대입해주면 좋을거 같아. 매수가 강하면 빨간색이 바뀌어야 되는데 이부분 잘안되는거
   같아. 그리고 외국인 프로그램만 있는데 좀더 필요한것들도 추가로 넣어줘」 → 시안 「응 그래」(개발2 창).

   11-05 — 「코스피 외국인도 있고 외국계 창구도 있는데 이유가 뭐야?」 → 「전부다 그종목에 매수매도가 필요한건데」 → 안 「응」(개발2 창).
   코스피 전체 묶음을 빼고 그 종목의 외국인 · 기관을 넣었다.

       외국계 창구 [──●──] 13:55   종목 프로그램 [──●┃─] 13:55  │  외국인 +12.3만주 · 기관 −4.1만주 3회차 가집계

   원 자리 · 색 짙기 = **최근 5분(RECENT 칸 — 거래가 있던 1분 칸만 센다) 매수 몫**(매수 ÷ (매수 + 매도) · 가운데 50%).
   오른쪽 · 빨강이면 지금 사는 쪽이 세다 · 멀수록 짙다. 세로 눈금 = **오늘 누적 매수 몫**.
   11-03 판은 원 자리를 오늘 누적으로 · 색을 「화면을 연 뒤 앞 값과 견준 것」 으로 셌다 — 누적은 하루치가 쌓여 잘 안 움직이고
   (11-04 삼성전자 프로그램 누적 38.5% 인데 막판 1분 몫 53~78%) 앞 값이 없을 때(처음 연 때 · 장 마감 뒤)는 회색으로 남아
   「매수가 강한데 빨강이 안 된다」 가 됐다.
   외국계 창구는 1분 값이 없어(KIS 회원사 누적만 줌) 원이 오늘 누적이고 눈금이 없다.
   기준 · 폭은 지표 표(data/metrics.json 의 buy_share)에 있고 쪽 · 짙기 셈은 assets/js/tone.js 한 곳이다
   (「기준이 있는 수치는 위 빨강 · 아래 파랑, 멀수록 짙게」) — 표에 없으면 원을 가운데 회색으로 두고 tone.js 가 콘솔에 알린다.
   글자는 **정보가 들어온 시각**이다 — 금액은 안 쓴다.

   값 출처 — 서버가 이미 받는 주소다(KIS 호출을 새로 만들지 않는다)
     외국계 창구    /api/kis/investor-member 의 foreignFirms.buy · sell(수량 · KRX 회원사 중 외국계 합 · 외국인 전체 아님)
                    시각 = 서버가 KIS 에서 받은 시각(at)
     프로그램       /api/kis/flow-today?code=&step=1 의 stock.rows(원 · 서버가 1분마다 쌓음)
                    시각 = 거래가 있던 마지막 1분 칸
     외국인 · 기관   /api/kis/investor-estimate?code= 의 latest(증권사 추정가집계 · 순매수 수량 하나 — 매수 · 매도가 따로 없어 원으로
                    못 그린다 · 오름 빨강 · 내림 파랑 글씨는 assets/js/sign.js). 하루 다섯 회차(입력 외국인 09:30 · 11:20 · 13:20 · 14:30 /
                    기관 10:00 · 11:20 · 13:20 · 14:30) · 응답에 시각이 없어 회차로 적는다 · 마감 뒤 확정치와 다르다

   다시 묻는 주기는 서버가 준다(롱폴 · 폴백은 각 주소의 서버 캐시 값) — 화면에 주기 숫자를 두지 않는다.
   ========================================================================== */

import { watch } from '../store/longpoll.js';
import { ready as toneReady, tone, paint } from '../../../assets/js/tone.js';
import { signClass } from '../../../assets/js/sign.js';

const ID = 'buy_share';                         // data/metrics.json 의 이름
const RECENT = 5;                               // 원이 보는 최근 1분 칸 수 — 셈 범위이지 다시 묻는 주기가 아니다
const KEYS = { mem: 'kis_proxy.INVESTOR_MEMBER_TTL', flow: 'intraday_flow.CACHE_TTL', est: 'kis_proxy.INVESTOR_EST_TTL' };
const FALLBACK_MS = 60000;                      // 서버 값마저 못 받았을 때만

const CSS_HREF = new URL('../../css/flow-foot.css', import.meta.url).href;   // 줄 모양 — 이 줄을 쓰는 화면이 따로 안 걸어도 되게
function ensureCss() {
  if ([...document.querySelectorAll('link[rel="stylesheet"]')].some((l) => l.href === CSS_HREF)) return;   // 화면이 미리 건 것도 센다
  const l = document.createElement('link');
  l.rel = 'stylesheet';
  l.href = CSS_HREF;
  document.head.appendChild(l);
}

const get = (u) => fetch(u, { cache: 'no-store' }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
const hm = (s) => (s ? String(s).replace(/^(\d\d)(\d\d)$/, '$1:$2') : null);
const flowUrl = (c) => `/api/kis/flow-today?step=1&code=${c}`;

function share(buy, sell) {
  if (buy == null || sell == null || !(buy + sell > 0)) return null;
  return buy / (buy + sell) * 100;
}

/* 1분 칸들 → { p: 최근 RECENT 칸 몫, c: 오늘 누적 몫, t: 거래가 있던 마지막 칸 시각 }. pick 은 칸에서 {buy, sell} 을 꺼낸다 */
function shares(rows, pick) {
  const live = (rows || []).map((r) => ({ t: r.t, v: pick(r) })).filter((x) => x.v && (x.v.buy || x.v.sell));
  if (!live.length) return { p: null, c: null, t: null };
  const sum = (list, k) => list.reduce((a, x) => a + (x.v[k] || 0), 0);
  const last = live.slice(-RECENT);
  return { p: share(sum(last, 'buy'), sum(last, 'sell')), c: share(sum(live, 'buy'), sum(live, 'sell')), t: live[live.length - 1].t };
}

/* 수량(주) → 「+12.3만주」 · 없으면 「—」 */
function ju(v) {
  if (v == null) return '—';
  const a = Math.abs(v), sg = v > 0 ? '+' : v < 0 ? '−' : '';
  return sg + (a >= 10000 ? `${(a / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}만주` : `${a.toLocaleString('ko-KR')}주`);
}

function dot(p, c) {
  const { side, k } = p == null ? { side: null, k: 0 } : tone(ID, p);
  const tick = c == null ? '' : (() => { const t = tone(ID, c);
    const x = t.side === 'up' || t.side === 'down' ? 50 + (t.side === 'up' ? 1 : -1) * t.k * 50 : 50;
    return `<i class="kh-ff-cum" style="left:${x.toFixed(1)}%"></i>`; })();
  // 값이 없거나(장 전 · 거래 없음) 정확히 가운데면 원을 가운데 회색으로 둔다(11-05 재권님 「장전이면 중간으로 해놓고」)
  if (side !== 'up' && side !== 'down') return `<span class="kh-ff-bar"><i class="kh-ff-mid"></i>${tick}` +
    '<i class="kh-ff-dot is-none" style="left:50%"></i></span>';
  const x = 50 + (side === 'up' ? 1 : -1) * k * 50;
  const col = paint(ID, p, 'line');
  const fill = side === 'up' ? `left:50%;width:${(x - 50).toFixed(1)}%` : `left:${x.toFixed(1)}%;width:${(50 - x).toFixed(1)}%`;
  return `<span class="kh-ff-bar"><i class="kh-ff-mid"></i><i class="kh-ff-fill ${side}" style="${fill};background:${col}"></i>${tick}` +
    `<i class="kh-ff-dot" style="left:${x.toFixed(1)}%;background:${col};--kh-ff-c:${col}"></i></span>`;
}

const TIP = '원 자리 · 색은 최근 5분 매수 몫(오른쪽 · 빨강 = 사는 쪽이 셈 · 멀수록 짙게) · 세로 눈금은 오늘 누적 · 시각은 정보가 들어온 때';

/* 바닥 줄 하나 — 홈 큰 차트와 종목 화면(모달) 차트가 각자 하나씩 갖는다 (2026-11-05 재권님 「모달로 띄우면 거기에도 나와야해」 → 「응 해」).
   전에는 모듈에 하나만 있어 둘째 자리가 첫째를 빼앗았다 */
export function createFlowFoot() {
  let code = null;
  let data = { mem: null, flow: null, est: null };         // 마지막으로 받은 값 — 바닥 줄을 다시 그려도 깜빡이지 않게 들고 있는다
  let watches = null;
  let footEl = null;

  function items() {
    const mem = data.mem && data.mem.code === code ? data.mem : null;
    const ff = mem && mem.foreignFirms;
    const fl = data.flow && data.flow.code === code ? data.flow : null;
    const sk = shares(fl && fl.stock && fl.stock.rows, (r) => r);
    return [
      [{ n: '외국계 창구', p: ff ? share(ff.buy, ff.sell) : null, c: null, t: mem ? mem.at : null }],
      [{ n: '종목 프로그램', ...sk, t: hm(sk.t) }],
    ];
  }

  function estHtml() {
    const est = data.est && data.est.code === code ? data.est.latest : null;
    const one = (n, v) => `<span class="kh-ff-n">${n}</span><b class="kh-ff-q ${signClass(v)}">${ju(v)}</b>`;
    return `<span class="kh-ff-it" title="증권사 추정가집계 · 순매수 수량 · 하루 다섯 회차 · 마감 뒤 확정치와 다름">` +
      `${one('외국인', est ? est.foreign : null)}${one('기관', est ? est.inst : null)}` +
      `<span class="kh-ff-t">${est && est.seq ? `${est.seq}회차 가집계` : '가집계 전'}</span></span>`;
  }

  function render() {
    if (!footEl || !footEl.isConnected || !code) return;
    let el = footEl.querySelector('.kh-flow-foot');
    if (!el) {
      el = document.createElement('span');
      el.className = 'kh-flow-foot';
      footEl.insertBefore(el, footEl.lastElementChild);   // 왼쪽 설명 뒤 · 오른쪽 출처 앞
    }
    el.innerHTML = items().map((grp, gi) => grp.map((x, i) =>
      `<span class="kh-ff-it" title="${x.n} — ${x.c == null && gi === 0 ? '원은 오늘 누적(창구는 1분 값 없음)' : TIP}">` +
      `<span class="kh-ff-n">${x.n}</span>${dot(x.p, x.c)}${i === grp.length - 1 ? `<span class="kh-ff-t">${x.t || '—'}</span>` : ''}</span>`).join('')).join('') +
      '<span class="kh-ff-sep"></span>' + estHtml();
  }

  async function loadMem() {
    const c = code;
    if (!c) return;
    const j = await get(`/api/kis/investor-member?code=${c}`);
    if (c !== code) return;
    if (j && j.data) data.mem = { code: c, foreignFirms: j.data.foreignFirms || null, at: j.data.at || null };
    render();
  }

  async function loadEst() {
    const c = code;
    if (!c) return;
    const j = await get(`/api/kis/investor-estimate?code=${c}`);
    if (c !== code) return;
    if (j && j.data) data.est = { code: c, latest: j.data.latest || null };
    render();
  }

  async function loadFlow() {
    const c = code;
    if (!c) return;
    const j = await get(flowUrl(c));
    if (c !== code) return;
    if (j && j.data) data.flow = { code: c, stock: j.data.stock || null, market: j.data.market || null, program: j.data.program || null };
    render();
  }

  /**
   * 바닥 줄에 붙인다 · 고른 종목이 바뀌거나 바닥 줄을 새로 썼을 때마다 부른다.
   * @param {HTMLElement} foot  바닥 줄 칸(홈 `#kh-big-foot` · 종목 화면 `.kh-chart-foot`) — 안의 글을 다시 써도 이것을 부르면 다시 붙는다
   * @param {string|null} c     종목 코드. 없으면(시장 지표를 보는 중) 줄을 뺀다
   */
  function paintFoot(foot, c) {
    ensureCss();
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
        watch({ url: () => (code ? flowUrl(code) : null), onChange: loadFlow, key: KEYS.flow, fallbackMs: FALLBACK_MS }),
        watch({ url: () => (code ? `/api/kis/investor-estimate?code=${code}` : null), onChange: loadEst, key: KEYS.est, fallbackMs: FALLBACK_MS }),
      ];
    }
    if (changed) {
      watches.forEach((w) => w.refresh());
      loadMem();
      loadFlow();
      loadEst();
    }
  }

  /** 떼어 낸다 — 모달을 닫을 때. 안 부르면 안 보이는 줄이 계속 묻는다 */
  function destroy() {
    if (watches) watches.forEach((w) => w.stop());
    watches = null;
    code = null;
    footEl = null;
  }

  return { paint: paintFoot, destroy };
}

/* 홈 큰 차트의 바닥 줄 — 홈은 한 벌만 쓴다 */
const homeFoot = createFlowFoot();
export const paintFlowFoot = (foot, c) => homeFoot.paint(foot, c);
