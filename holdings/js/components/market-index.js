/* 시장지표 — 홈 갈래 「시장지표」 의 칩 열하나와 큰 차트 (2026-10-12 · 재권님 「응 해줘」 · 시안 2판).
 *
 * 값은 서버 `/api/market/*` 가 네이버 증권 시장지표에서 받아 둔 것이다(server/market_index.py 머리 주석).
 * 어느 지표가 봉이고 어느 지표가 선인지도 서버가 정한다(`kind`) — 여기서 다시 가르지 않는다.
 *
 *     봉   시가·고가·저가·종가가 오는 지표 — 일봉
 *     선   종가만 오는 지표 — 종가 선 (재권님 「캔들이 없으면 그래프로만 그려도 돼」)
 *
 * 화면은 주기로 묻지 않는다 — 갈래를 열 때 · 칩을 누를 때 받는다. 받은 값은 들고 있다(빈칸으로 깜빡이지 않게).
 * 붙이는 자리(지수 띠 · 큰 차트 머리)는 home.js 가 정한다. 이 파일은 그리는 것만 맡는다.
 */

import { apiFetch } from '../data/api.js';
import { color } from '../theme.js';
import { ready as toneReady, has as toneHas, paint as tonePaint } from '/assets/js/tone.js';

/* 큰 차트 머리 이름에 다는 용어 풍선 — 지표 key → 용어집(data/glossary.json) id. 칩에는 안 단다:
   지수 띠가 옆으로 미는 칸이라 풍선이 그 안에 갇혀 잘린다(2026-10-12 실측 · 재권님 「가로 해줘」) */
export const MK_TERM = { dxy: '달러인덱스' };

let listCache = null;              // 마지막 칩 목록 — 다시 열 때 먼저 보여 준다
const barsCache = new Map();       // key → 응답

export async function loadIndicators() {
  const r = await apiFetch('/api/market/indicators', { cache: 'no-store' });
  const j = r && await r.json();
  if (!j || !j.ok) throw new Error((j && j.error) || '시장지표를 못 받았습니다');
  await toneReady;                 // 칩 바탕 색의 기준표(data/tone.json)를 먼저 — 받자마자 그리는 칩에 색이 빠지지 않게
  listCache = j;
  return j;
}
export const peekIndicators = () => listCache;

export async function loadIndicator(key) {
  const r = await apiFetch(`/api/market/indicator?key=${encodeURIComponent(key)}`, { cache: 'no-store' });
  const j = r && await r.json();
  if (!j || !j.ok) throw new Error((j && j.error) || '그 지표를 못 받았습니다');
  barsCache.set(key, j);
  return j;
}
export const peekIndicator = (key) => barsCache.get(key) || null;

export function fmtIx(v, digits) {
  return v == null ? '—'
    : Number(v).toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
/* 값 뒤 글자 — % · %p 만 붙인다(원 · 단위 없는 지수는 칩이 좁아 안 붙인다) */
const tail = (it) => (it.unit === '%' || it.unit === '%p') ? it.unit : '';
const md = (d) => d ? d.slice(5).replace('-', '.') : '';
const dir = (c) => c == null ? 'kh-mut' : c > 0 ? 'kh-up' : c < 0 ? 'kh-down' : '';

/* 지수 띠의 칩 — 국내·미국 지수 칩(index-strip.js)과 같은 모양 · 날짜 옆에 「봉」 · 「선」
   기준이 있는 지표는 칩 **바탕에 한 겹** 덧칠한다 — 기준 위 빨강 · 아래 파랑 · 멀수록 짙게 (2026-10-14 재권님 「달러인덱스를
   100을 기준으로 …」 · 「홀딩스 시장지표도 같아야 하고」 · 「그렇게 해」). 셈 · 기준 · 폭은 assets/js/tone.js · data/tone.json 한 곳이고
   여기는 지표 key 를 넘기기만 한다 — 그 표에 없는 지표는 칠하지 않는다. 글씨 색(그날 등락)과 칩 크기는 그대로다.
   덧칠(background-image)이라 고른 칩 · 마우스 올림의 바탕 규칙(home.css)은 그 밑에서 그대로 돈다 */
export function chipsHtml(list, sel) {
  return list.items.map((it) => {
    const v = it.last ? it.last.c : null;
    const tint = toneHas(it.key) ? tonePaint(it.key, v, 'bg') : '';   // 표에 없는 지표는 묻지 않는다 — 경고 없이 넘긴다
    const c = (it.last && it.prev) ? it.last.c - it.prev.c : null;
    const unitC = it.unit === '%' ? '%p' : tail(it);
    const ch = c == null ? (it.error ? '못 받음' : '') : `${c > 0 ? '+' : ''}${fmtIx(c, it.digits)}${unitC}`;
    return `<div class="kh-ix${it.key === sel ? ' is-on' : ''}" data-mk="${it.key}"${tint ? ` style="background-image:linear-gradient(${tint},${tint})"` : ''}>
      <div class="kh-ix-h"><span class="kh-ix-n">${it.name}</span>
        <span class="kh-bd">${md(it.last && it.last.d)}${it.freq ? ' ' + it.freq : ''} · ${it.kind === 'candle' ? '봉' : '선'}</span></div>
      <div class="kh-ix-b"><div>
        <div class="kh-ix-v kh-num ${dir(c)}">${fmtIx(v, it.digits)}${tail(it)}</div>
        <div class="kh-ix-c kh-num ${dir(c)}">${ch}</div>
      </div></div></div>`;
  }).join('');
}

/* 큰 차트 머리에 넣을 글 — home.js 가 제 칸에 넣는다 */
export function headOf(j) {
  const it = j.item, b = j.bars, last = b[b.length - 1], prev = b[b.length - 2];
  const c = prev ? last.c - prev.c : null;
  const lo = Math.min(...b.map(x => it.kind === 'candle' ? x.l : x.c));
  const hi = Math.max(...b.map(x => it.kind === 'candle' ? x.h : x.c));
  const u = it.unit === '원' ? '원' : tail(it);
  return {
    name: it.name,
    value: `${fmtIx(last.c, it.digits)}${u}  ${c == null ? '' : (c > 0 ? '+' : '') + fmtIx(c, it.digits)}`,
    dirClass: dir(c),
    range: `1년 최저 ${fmtIx(lo, it.digits)} · 최고 ${fmtIx(hi, it.digits)}`,
    per: `1년 · ${it.kind === 'candle' ? '일봉' : '종가 선'}`,
    /* 아래 줄은 짧게 — 종목 차트의 줄보다 길면 폰에서 한 줄 더 넘어가 카드가 커진다(2026-10-12 실측 17px).
       자세한 말은 마우스를 올리면 뜬다 */
    foot: [`1년 ${it.kind === 'candle' ? '일봉' : '종가'} ${b.length}개 · ${md(last.d)}까지`
             + (it.kind === 'candle' && j.fixed ? ` · 메운 날 ${j.fixed}` : ''),
           `네이버 · ${md((j.fetchedAt || '').slice(0, 10))} ${(j.fetchedAt || '').slice(11, 16)} 받음`],
    footTitle: it.kind === 'candle'
      ? (j.fixed ? `고가·저가가 비었거나 종가가 고가·저가 밖인 날 ${j.fixed}개는 시가·종가로 메웠습니다` : '')
      : '네이버가 시가·고가·저가를 주지 않아 종가 선으로 그립니다',
  };
}

/* 큰 차트 칸 위에 얹어 그린다 — 종목 차트는 그대로 두고 가린다(돌아갈 때 다시 안 만든다).
   돌려주는 것: 지우는 함수 */
export function drawIndicator(host, j) {
  const LC = window.LightweightCharts;
  if (!LC) throw new Error('차트 라이브러리를 불러오지 못했습니다');
  if (getComputedStyle(host).position === 'static') host.style.position = 'relative';
  let box = host.querySelector(':scope > .kh-mk-c');
  if (!box) {
    box = document.createElement('div');
    box.className = 'kh-mk-c';
    box.style.cssText = 'position:absolute;inset:0;z-index:4;background:var(--kh-bg-card)';
    host.appendChild(box);
  }
  box.replaceChildren();
  const it = j.item;
  const ch = LC.createChart(box, {
    autoSize: true,
    layout: { background: { color: 'transparent' }, textColor: color('chart-axis'),
      fontFamily: "'Noto Sans KR', system-ui, sans-serif", fontSize: 11, attributionLogo: false },
    grid: { vertLines: { color: color('chart-grid') }, horzLines: { color: color('chart-grid') } },
    rightPriceScale: { borderColor: color('chart-border') },
    timeScale: { borderColor: color('chart-border'), rightOffset: 4 },
    crosshair: { mode: LC.CrosshairMode.Normal,
      vertLine: { color: color('chart-crosshair'), labelBackgroundColor: color('chart-label-bg') },
      horzLine: { color: color('chart-crosshair'), labelBackgroundColor: color('chart-label-bg') } },
    localization: { locale: 'ko-KR', priceFormatter: (v) => fmtIx(v, it.digits) },
  });
  if (it.kind === 'candle') {
    const up = color('up'), dn = color('down');
    const s = ch.addSeries(LC.CandlestickSeries, { upColor: up, downColor: dn, borderUpColor: up,
      borderDownColor: dn, wickUpColor: up, wickDownColor: dn });
    s.setData(j.bars.map(b => ({ time: b.d, open: b.o, high: b.h, low: b.l, close: b.c })));
  } else {
    const s = ch.addSeries(LC.LineSeries, { color: color('accent'), lineWidth: 2 });
    s.setData(j.bars.map(b => ({ time: b.d, value: b.c })));
  }
  ch.timeScale().fitContent();
  return () => { ch.remove(); box.remove(); };
}

/* ── 오른쪽 칸 「시장지표 재료」 (2026-10-12 · 재권님 「응 그래」 · 시안 3) ──
 * 「시장지표」 갈래에서 오른쪽 실시간 순위 카드 자리에 환율 · 금리 · 에너지 · 금속 · 농산 · 운임의 지금 값을 둔다.
 * 순위 카드를 고치지 않고 **같은 클래스로 만든 판을 카드 위에 얹는다** — 카드 크기는 밑의 순위 카드가 정하므로
 * 안 바뀐다(「보는 것을 바꿔도 자리는 그대로다」). 순위 카드는 가려 둔 채 그대로 돈다. 줄을 눌러 큰 차트로 가는 것은 아직 없다. */
let matCache = null;
export async function loadMaterials() {
  const r = await apiFetch('/api/market/materials', { cache: 'no-store' });
  const j = r && await r.json();
  if (!j || !j.ok) throw new Error((j && j.error) || '시장지표 재료를 못 받았습니다');
  matCache = j;
  return j;
}
export const peekMaterials = () => matCache;

const matFmt = (v) => v == null ? '—'
  : v.toLocaleString('ko-KR', { maximumFractionDigits: Math.abs(v) >= 1000 ? 0 : Math.abs(v) >= 100 ? 2 : 3 });
const matPct = (p) => p == null ? '—' : `${p > 0 ? '+' : ''}${p.toFixed(2)}%`;
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export function materialsShell() {
  return `<div class="kh-tabs"><button class="kh-tab is-active" type="button">시장지표 재료</button></div>
    <div class="kh-chips" data-mat-chips></div>
    <div class="kh-sort-note">값 · 기준일 · 그날 등락률</div>
    <div class="kh-asof" data-mat-asof>· 불러오는 중</div>
    <div class="kh-rank-scroll" data-mat-scroll><table><thead><tr>
      <th></th><th class="l">지표</th><th>값</th><th>기준일</th><th>등락률</th></tr></thead>
      <tbody data-mat-rows></tbody></table></div>`;
}

/* 판 안을 채운다 — grp 는 '전체' 또는 칩 이름 */
export function paintMaterials(root, j, grp) {
  const ids = ['전체', ...((j && j.groups) || []).map((g) => g.id)];
  root.querySelector('[data-mat-chips]').innerHTML = ids.map((id) =>
    `<button class="kh-chip${id === grp ? ' is-active' : ''}" type="button" data-mat="${id}">${id}</button>`).join('');
  const asof = root.querySelector('[data-mat-asof]');
  const body = root.querySelector('[data-mat-rows]');
  if (!j) { asof.textContent = '· 불러오는 중'; body.innerHTML = ''; return; }
  const t = (j.fetchedAt || '').slice(11, 16);
  asof.textContent = `· ${t} 받음 · 네이버 증권 시장지표`;
  const rows = [];
  for (const g of j.groups) {
    if (grp !== '전체' && grp !== g.id) continue;
    for (const p of g.parts) {
      if (grp === '전체' || g.parts.length > 1) {
        rows.push(`<tr><td></td><td class="l" colspan="4" style="padding-top:12px"><b class="kh-mut" style="font-size:.76rem">${esc(p.label)}</b></td></tr>`);
      }
      if (!p.rows.length) rows.push('<tr><td></td><td class="l kh-mut" colspan="4">불러오지 못함</td></tr>');
      const pctUnit = p.path.endsWith('Interest');
      for (const x of p.rows) {
        const c = x.pct == null ? 'kh-mut' : x.pct > 0 ? 'kh-up' : x.pct < 0 ? 'kh-down' : '';
        rows.push(`<tr title="${esc(x.unit || '')}">
          <td class="kh-rk"></td><td class="l"><span class="kh-nm"><b>${esc(x.name)}</b></span></td>
          <td class="kh-num">${matFmt(x.v)}${pctUnit ? '%' : ''}</td>
          <td class="kh-num kh-metric kh-mut">${md(x.at)}</td>
          <td class="kh-num ${c}" style="font-weight:500">${matPct(x.pct)}</td></tr>`);
      }
    }
  }
  body.innerHTML = rows.join('');
}
