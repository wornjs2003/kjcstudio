/* 시장 전체 사건 띠 — 서킷브레이커 · 사이드카 (2026-11-07 · 작업우선순위 배분 ① · 재권님 「응 그래 다른이벤트들도 대응해야해」)

   서버(`/api/alerts/market-event` · server/market_event.py)가 · 장 시각 한 곳(`/api/alerts/market-hours`)이 오늘 휴장 · 바뀐 시각을 주고 · 지수로 추정한 서킷 · 거래소 공시로 확인한 것을 그대로 그린다 —
   셈은 서버 한 곳이고 화면은 「지금 걸려 있는 것」 만 띄운다(매매 중단 · 단일가 · 그날 장 끝 · 사이드카 5분).
   **화면 흐름 밖에 띄운다** — 「작업용」 띠(frame.css `.kh-envbar`)처럼 fixed 라 칸 크기 · 자리가 안 움직인다.
   받는 주기는 서버 값(`market_event.TICK_SEC`)이고 롱폴이 켜져 있으면 바뀔 때 받는다. */
import { watch } from '../store/longpoll.js';

const URL = '/api/alerts/market-event';
const HOURS_URL = '/api/alerts/market-hours';   // 장 시각 한 곳 — 오늘 휴장 · 바뀐 시각(server/market_hours.py)
const hm = (t) => `${t.slice(0, 2)}:${t.slice(2, 4)}`;
const KEY = 'market_event.TICK_SEC';
const FALLBACK_MS = 10_000;          // 서버 값을 못 받았을 때만
const PHASE = { halt: '매매 중단', single: '단일가', closed: '그날 장 끝' };

function css() {
  if (document.querySelector('link[data-market-event]')) return;
  const l = document.createElement('link');
  l.rel = 'stylesheet'; l.href = '/holdings/css/market-event.css'; l.dataset.marketEvent = '';
  document.head.appendChild(l);
}

function line(name, ev) {
  if (ev.type === 'sc') {
    const side = ev.side === 'buy' ? '매수' : ev.side === 'sell' ? '매도' : '';
    const tag = ev.confirmed ? '확인됨' : '추정';
    const until = ev.until ? ` · ${ev.until.slice(0, 5)} 까지 프로그램 ${side} 호가 정지` : '';
    return `${name} ${side} 사이드카(${tag}) ${ev.at.slice(0, 5)} 발동${until}`;
  }
  const st = ev.stage ? `${ev.stage}단계` : '단계 모름';
  const tag = ev.confirmed ? '확인됨' : '추정';
  const until = ev.phase === 'halt' ? ` · ${ev.haltUntil.slice(0, 5)} 까지 ${PHASE.halt}`
    : ev.phase === 'single' ? ` · ${ev.singleUntil.slice(0, 5)} 까지 ${PHASE.single}` : ` · ${PHASE.closed}`;
  return `${name} 서킷 ${st}(${tag}) ${ev.at.slice(0, 5)} 발동${until}`;
}

let box = null;
async function get(u) {
  try { const r = await fetch(u, { cache: 'no-store' }); const j = r.ok ? await r.json() : null; return j && j.ok ? j.data : null; } catch { return null; }
}

/* 오늘 장 — 평일인데 쉬는 날 · 시각이 바뀐 날만 한 줄(주말 · 평소 날은 안 띄운다) */
function hoursLine(h) {
  const t = h && h.today;
  if (!t) return null;
  const wd = new Date(+t.day.slice(0, 4), +t.day.slice(4, 6) - 1, +t.day.slice(6, 8)).getDay();
  if (t.open === false && wd !== 0 && wd !== 6) return `오늘 휴장${t.why && t.why !== '휴장일' ? `(${t.why})` : ''}`;
  if (t.open !== false && t.changed) return `오늘 ${t.why || '장 시각 바뀜'} — 정규장 ${hm(t.reg[0])}~${hm(t.reg[1])}`;
  return null;
}

let lastEv = null, lastHours = null;
async function draw() {
  const [ev, hours] = await Promise.all([get(URL), get(HOURS_URL)]);
  if (ev && ev.markets) lastEv = ev;              // 못 받았으면 지난 모습 그대로 — 띠를 지우지 않는다
  if (hours) lastHours = hours;
  const ms = (lastEv && lastEv.markets) || {};
  const rows = Object.entries(ms).flatMap(([name, m]) => ((m && (m.live || (m.now ? [m.now] : []))) || []).map((e) => line(name, e)));
  const hl = hoursLine(lastHours);
  if (hl) rows.unshift(hl);
  if (!rows.length) { if (box) box.hidden = true; return; }
  if (!box) {
    css();
    box = document.createElement('div');
    box.className = 'kh-mkev';
    box.setAttribute('role', 'alert');
    document.body.appendChild(box);
  }
  box.hidden = false;
  box.innerHTML = rows.map((t) => `<div>⚠ ${t}</div>`).join('');
}

draw();
watch({ url: () => URL, onChange: draw, key: KEY, fallbackMs: FALLBACK_MS });
