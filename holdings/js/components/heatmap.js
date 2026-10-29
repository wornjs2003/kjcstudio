/* ==========================================================================
   첫 화면 시장 지도(히트맵) — 칸 넓이 = 시가총액 · 색 = 오늘 등락률 (2026-10-27)

   재권님 말씀 — 「홈이나 국내 미국 을 누르면 첫화면이 이런식으로 코스피 코스닥 등등이 보여지면 좋을거 같은데」
   → 시안(큰 차트 자리를 갈아 끼움 · (가)) 「응 맞아」 → 「응 시작해」.

   값은 서버 `/api/kis/heatmap?market=kr|us`(server/heatmap.py) — 화면은 주기를 갖지 않고 롱폴로 받는다.
   **큰 차트 카드 위에 덮개로 얹는다** — 카드 크기 · 다른 칸 자리는 그대로다(「보는 것을 바꿔도 자리는 그대로다」).
   종목을 누르면 onPick(code, name) — 부르는 쪽(home.js)이 순위표 줄과 같은 길(selectStock)로 차트를 띄우고 이 덮개를 내린다.

   색 — 오르면 --kh-up · 내리면 --kh-down · 0 은 색 없음 · 값 없음은 흐림(방향은 sign.js).
   짙기 폭 FULL_PCT 는 시안 값이다 — 「기준이 있는 수치는 … 셈은 tone.js 한 곳」 에 들어 tone.js 로 옮긴다(2026-10-28 검수 걸림 · 재권님 「응」)
   ========================================================================== */

import { side } from '/assets/js/sign.js';
import { apiFetch } from '../data/api.js';
import { watch } from '../store/longpoll.js';

const FULL_PCT = 10;                     // 이 등락률(±%)에서 가장 짙다 — 재권님 「0~10까지 · 그 이상은 같은 색」(10-28) · tone.js 로 옮기기 전 임시
const ALPHA = [0.18, 1];                 // 가장 옅음 · 가장 짙음
const INK_PCT = 4;                       // 바탕 농도 k 0.4 부터 흰 글씨 — tone.js onFill 로 옮기기 전 임시
const TITLE = { kr: '국내 시장 지도', us: '미국 시장 지도' };
const FOOT = {
  kr: '코스피 시가총액 상위 70 · 코스닥 상위 40 · 업종은 KIS 종목 목록의 지수업종',
  us: 'S&P 섹터 ETF 구성 종목 중 시가총액 상위 110 · 반도체는 기술에 든다',
};

/* squarified treemap — 넓이 순으로 줄을 채운다 */
function squarify(items, x, y, w, h) {
  const out = [];
  const total = items.reduce((s, i) => s + i.v, 0);
  if (!total || w <= 0 || h <= 0) return out;
  const sc = (w * h) / total;
  let rest = items.map((i) => ({ ...i, a: i.v * sc }));
  while (rest.length) {
    const short = Math.min(w, h);
    let row = [rest[0]], best = worst(row, short), k = 1;
    while (k < rest.length) {
      const nr = row.concat(rest[k]);
      const nw = worst(nr, short);
      if (nw > best) break;
      row = nr; best = nw; k++;
    }
    const sum = row.reduce((s, r) => s + r.a, 0);
    if (w >= h) {
      const cw = sum / h; let cy = y;
      for (const r of row) { const ch = r.a / cw; out.push({ ...r, x, y: cy, w: cw, h: ch }); cy += ch; }
      x += cw; w -= cw;
    } else {
      const ch = sum / w; let cx = x;
      for (const r of row) { const cw = r.a / ch; out.push({ ...r, x: cx, y, w: cw, h: ch }); cx += cw; }
      y += ch; h -= ch;
    }
    rest = rest.slice(k);
  }
  return out;
}
function worst(row, short) {
  const s = row.reduce((t, r) => t + r.a, 0);
  const mx = Math.max(...row.map((r) => r.a));
  const mn = Math.min(...row.map((r) => r.a));
  return Math.max((short * short * mx) / (s * s), (s * s) / (short * short * mn));
}

function fill(pct) {
  const sd = side(pct);
  if (!sd) return 'var(--kh-border)';
  if (sd === 'flat') return 'var(--kh-bg)';
  const k = Math.min(Math.abs(pct) / FULL_PCT, 1);
  return `rgb(var(--kh-${sd}-rgb) / ${(ALPHA[0] + (ALPHA[1] - ALPHA[0]) * k).toFixed(2)})`;
}
function inkClass(pct) {
  const sd = side(pct);
  if (sd === 'up' || sd === 'down') return Math.abs(pct) >= INK_PCT ? 'is-fill' : `kh-${sd}`;
  return 'kh-mut';
}
const pctTxt = (p) => (side(p) ? (p > 0 ? '+' : '') + p.toFixed(2) + '%' : '—');
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/**
 * @param {HTMLElement} card  큰 차트 카드(.kh-idx-main)
 * @param {{ onPick: (code: string, name: string) => void }} opt
 */
export function mountHeatmap(card, { onPick }) {
  const box = document.createElement('div');
  box.className = 'kh-hm';
  box.hidden = true;
  box.innerHTML = `<div class="kh-hm-head"><span class="kh-hm-title"></span>
      <span class="kh-hm-sub">칸 넓이 = 시가총액 · 색 = 오늘 등락률 · 종목을 누르면 이 자리에 그 종목 차트</span></div>
    <div class="kh-hm-area"></div><div class="kh-hm-foot"></div>`;
  card.appendChild(box);
  const area = box.querySelector('.kh-hm-area');
  let market = null, last = null, sub = null, ro = null;

  const url = () => (market ? '/api/kis/heatmap?market=' + market : null);

  async function load() {
    const want = market;
    if (!want) return;
    try {
      const j = await (await apiFetch(url(), { cache: 'no-store' })).json();
      if (want !== market) return;                 // 받는 사이 갈래가 바뀌었다
      if (!j.ok) { area.innerHTML = `<div class="kh-hm-empty">지도를 못 받았습니다 — ${esc(j.error)}</div>`; return; }
      last = j.data;
      draw();
    } catch {
      if (want === market && !last) area.innerHTML = '<div class="kh-hm-empty">지도를 못 받았습니다</div>';
    }
  }

  function draw() {
    if (!last || box.hidden) return;
    const W = area.clientWidth, H = area.clientHeight;
    if (!W || !H) return;
    const groups = last.groups.map((g) => {
      const secs = g.sectors.map((s) => ({ n: s.name, rs: s.stocks.filter((x) => x.cap > 0).map((x) => ({ ...x, v: x.cap })) }))
        .filter((s) => s.rs.length).map((s) => ({ ...s, v: s.rs.reduce((t, r) => t + r.v, 0) }));
      return { name: g.name, secs, v: secs.reduce((t, s) => t + s.v, 0) };
    });
    /* 시장이 둘이면(국내) 큰 쪽이 72% 를 넘지 않게 — 넘으면 작은 쪽이 띠가 된다 */
    const parts = [];
    if (groups.length === 2) {
      const tot = groups[0].v + groups[1].v;
      const w0 = Math.min(W * 0.72, (W * groups[0].v) / tot);
      parts.push({ ...groups[0], x: 0, w: w0 - 3 }, { ...groups[1], x: w0 + 3, w: W - w0 - 3 });
    } else if (groups.length) parts.push({ ...groups[0], x: 0, w: W });
    let html = '';
    const lab = groups.length > 1 ? 18 : 0;
    for (const p of parts) {
      if (lab) html += `<div class="kh-hm-mk" style="left:${p.x}px">${esc(p.name)}</div>`;
      for (const s of squarify(p.secs, p.x, lab, p.w, H - lab)) {
        html += `<div class="kh-hm-sec" style="left:${s.x + 1}px;top:${s.y + 1}px;width:${s.w - 2}px;height:${s.h - 2}px"></div>`;
        const head = s.h > 40 && s.w > 50 ? 15 : 0;
        if (head) html += `<div class="kh-hm-secn" style="left:${s.x + 4}px;top:${s.y + 1}px;width:${s.w - 8}px">${esc(s.n)}</div>`;
        for (const c of squarify(s.rs, s.x, s.y + head, s.w, s.h - head)) {
          /* 큰 칸은 이름 아래 등락률 · 낮은 칸(24~40px)은 두 줄이 들어가게 글씨를 줄인다(재권님 「퍼센트는 안나오는건가?」 → (가) 2026-10-28) */
          const low = c.h <= 40;
          let fs = Math.max(9, Math.min(22, Math.min(c.w, c.h) / 4.2, (c.w - 6) / (String(c.name).length * 1.05)));
          if (low) fs = Math.max(8, Math.min(fs, (c.h - 4) / 2.3));
          const pf = low ? fs : Math.max(10, fs * 0.72);
          const pctFits = c.h >= 24 && (c.w - 6) >= pctTxt(c.pct).length * pf * 0.6;
          const txt = c.w > 34 && c.h > 22
            ? `<b style="font-size:${fs.toFixed(1)}px">${esc(c.name)}</b>${pctFits ? `<span style="font-size:${pf.toFixed(1)}px">${pctTxt(c.pct)}</span>` : ''}` : '';
          html += `<button type="button" class="kh-hm-cell ${inkClass(c.pct)}" data-code="${esc(c.code)}" data-name="${esc(c.name)}"
            title="${esc(c.name)} ${pctTxt(c.pct)}" style="left:${c.x + 1}px;top:${c.y + 1}px;width:${c.w - 2}px;height:${c.h - 2}px;background:${fill(c.pct)}">${txt}</button>`;
        }
      }
    }
    area.innerHTML = html;
  }

  area.addEventListener('click', (e) => {
    const b = e.target.closest('.kh-hm-cell');
    if (b) onPick(b.dataset.code, b.dataset.name);
  });

  return {
    /** 'kr' | 'us' 지도를 띄운다 */
    show(next) {
      if (market !== next) { last = null; area.innerHTML = '<div class="kh-hm-empty">지도를 받는 중</div>'; }
      market = next;
      box.querySelector('.kh-hm-title').textContent = TITLE[next];
      box.querySelector('.kh-hm-foot').textContent = FOOT[next];
      box.hidden = false;
      card.classList.add('is-hm');
      if (!sub) sub = watch({ url, onChange: load, key: 'heatmap.HEATMAP_TTL', fallbackMs: 60 * 1000 });
      else sub.refresh();
      if (!ro) { ro = new ResizeObserver(() => draw()); ro.observe(area); }
      load();
    },
    hide() {
      if (box.hidden) return;
      market = null;
      box.hidden = true;
      card.classList.remove('is-hm');
      if (sub) { sub.stop(); sub = null; }
    },
    get market() { return market; },
  };
}
