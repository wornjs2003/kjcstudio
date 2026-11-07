/* 시장 전체 사건 띠 — 서킷브레이커 (2026-11-07 · 작업우선순위 배분 ① · 재권님 「응 그래 다른이벤트들도 대응해야해」)

   서버(`/api/alerts/market-event` · server/market_event.py)가 지수로 추정한 서킷 · 거래소 공시로 확인한 것을 그대로 그린다 —
   셈은 서버 한 곳이고 화면은 「지금 걸려 있는 것」 만 띄운다(매매 중단 · 단일가 · 그날 장 끝).
   **화면 흐름 밖에 띄운다** — 「작업용」 띠(frame.css `.kh-envbar`)처럼 fixed 라 칸 크기 · 자리가 안 움직인다.
   받는 주기는 서버 값(`market_event.TICK_SEC`)이고 롱폴이 켜져 있으면 바뀔 때 받는다. */
import { watch } from '../store/longpoll.js';

const URL = '/api/alerts/market-event';
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
  const st = ev.stage ? `${ev.stage}단계` : '단계 모름';
  const tag = ev.confirmed ? '확인됨' : '추정';
  const until = ev.phase === 'halt' ? ` · ${ev.haltUntil.slice(0, 5)} 까지 ${PHASE.halt}`
    : ev.phase === 'single' ? ` · ${ev.singleUntil.slice(0, 5)} 까지 ${PHASE.single}` : ` · ${PHASE.closed}`;
  return `${name} 서킷 ${st}(${tag}) ${ev.at.slice(0, 5)} 발동${until}`;
}

let box = null;
async function draw() {
  let j = null;
  try { const r = await fetch(URL, { cache: 'no-store' }); j = r.ok ? await r.json() : null; } catch { j = null; }
  if (!(j && j.ok && j.data && j.data.markets)) return;   // 못 받았으면 지난 모습 그대로 — 띠를 지우지 않는다
  const ms = j.data.markets;
  const rows = Object.entries(ms).filter(([, m]) => m && m.now).map(([name, m]) => line(name, m.now));
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
