/* 홈 지수 띠 「국외」 갈래 끝 칸 — 바이낸스 한국 종목 무기한선물 · SK하이닉스 미국 상장분 · 원/유로 (2026-11-19)
 *
 * 재권님 「https://apt2.me/global_index.jsp 여기 정보들 가져올수있나?」 → 조사 → 서버가 받는 셋 「응」 → 자리 「가」(「국외」 갈래 끝에 칸으로).
 * 값은 서버 /api/market/world-extra(server/world_extra.py) 한 곳 · 이 파일은 받은 대로 그린다.
 * 모양은 지수 칸(.kh-ix)과 같다 — 띠 높이가 안 바뀐다. 누르면 차트로 가지 않는다(data-ix 없음 · 큰 차트에 그릴 일봉이 없다).
 * 「국외」 갈래를 보는 동안만 받는다 — 다시 받는 간격은 서버가 내는 meta.ttlSec(「화면은 서버에 주기로 묻지 않는다 — 서버가 알려준다」).
 */
import { apiFetch } from '../data/api.js';
import { fmtNum, fmtDelta, dirClass } from '../utils/format.js';

let data = null;          // 마지막으로 받은 값 — 못 받아도 지우지 않는다
let fail = null;          // 못 받은 까닭(서버 · 바깥)
let timer = 0;
let ttlMs = 0;            // 서버가 낸 가장 짧은 TTL — 받기 전에는 0(다시 받지 않음)

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const md = (d) => (d && d.length >= 10 ? `${d.slice(5, 7)}.${d.slice(8, 10)}` : '');

function rows() {
  const d = data || {};
  const out = [];
  for (const b of d.binance || []) {
    out.push({ key: 'bn-' + b.symbol, icon: 'bn', name: b.name + ' 선물', badge: '24시간', value: b.last,
      change: b.last != null && b.open24h != null ? b.last - b.open24h : null, pct: b.chgPct24h,
      tip: `바이낸스 ${b.symbol} 무기한선물(USDT) · 마지막 체결 · 등락은 24시간 전 대비\n펀딩비 ${b.funding == null ? '—' : (b.funding * 100).toFixed(4) + '%'} · ${(d.sources || {}).binance || ''}` });
  }
  if (d.skhy) {
    const s = d.skhy;
    out.push({ key: 'skhy', icon: 'us', name: '하이닉스 나스닥', badge: 'SKHY', value: s.last,
      change: s.last != null && s.base != null ? s.last - s.base : null, pct: s.chgPct,
      tip: `${s.name} · 달러 · 등락은 전날 종가 대비\n${(d.sources || {}).skhy || ''}` });
  }
  if (d.eurkrw) {
    const e = d.eurkrw;
    out.push({ key: 'eurkrw', icon: 'eu', name: '원/유로', badge: md(e.date), value: e.value,
      change: e.value != null && e.prev != null ? e.value - e.prev : null, pct: e.chgPct,
      tip: `원/유로 · 등락은 앞 날 대비\n${(d.sources || {}).eurkrw || ''}` });
  }
  return out;
}

function icon(kind) {
  if (kind === 'us') return `<svg class="kh-ix-flag" viewBox="0 0 24 24" aria-hidden="true"><use href="./img/flags.svg#kh-flag-us"/></svg>`;
  return `<span class="kh-ix-badge ${kind}" aria-hidden="true">${{ bn: 'B', eu: 'EU' }[kind] || ''}</span>`;
}

/** 띠 끝에 붙일 칸들. 아직 안 받았으면 빈 글(칸 없음) — 「국외」 에 들어가면 곧 받는다 */
export function worldExtraCells() {
  const list = rows();
  const failTip = fail ? `\n못 받음: ${Object.entries(fail).map(([k, v]) => `${k} ${v}`).join(' · ')}` : '';
  return list.map((r) => {
    const cls = r.pct == null ? 'kh-mut' : dirClass(r.pct);
    return `<div class="kh-ix" data-wx="${esc(r.key)}" data-tip="${esc(r.tip + failTip)}">
      <div class="kh-ix-h">${icon(r.icon)}<span class="kh-ix-n">${esc(r.name)}</span><span class="kh-bd">${esc(r.badge)}</span></div>
      <div class="kh-ix-b"><div>
        <div class="kh-ix-v kh-num ${cls}">${r.value == null ? '—' : fmtNum(r.value, 2)}</div>
        <div class="kh-ix-c kh-num ${cls}">${r.change == null || r.pct == null ? '—' : fmtDelta(r.change, r.pct, '', 2)}</div>
      </div></div>
    </div>`;
  }).join('');
}

/** 받는다 — onDone 은 받은 뒤(성공 · 실패 둘 다) 띠를 다시 그리게 부른다. active() 가 false 면 다음 받기를 걸지 않는다 */
export async function loadWorldExtra(onDone, active) {
  clearTimeout(timer);
  try {
    const r = await apiFetch('/api/market/world-extra', { cache: 'no-store' });
    const j = await r.json();
    if (j && j.data) {
      data = j.data;
      fail = Object.keys(j.data.fail || {}).length ? j.data.fail : null;
    }
    const t = Object.values((j && j.meta && j.meta.ttlSec) || {}).filter((x) => x > 0);
    ttlMs = t.length ? Math.min(...t) * 1000 : 0;
  } catch (e) {
    fail = { server: '서버에 못 닿음' };
  }
  onDone && onDone();
  if (ttlMs && active && active()) timer = setTimeout(() => loadWorldExtra(onDone, active), ttlMs);
}

export function stopWorldExtra() { clearTimeout(timer); }
