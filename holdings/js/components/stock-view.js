/* 종목 화면 그리기 — 종목 페이지와 모달이 함께 쓴다.
 *
 * ── 왜 한 곳에 모았나 ──
 *
 * 같은 화면이 두 자리에 나온다.
 *
 *     stock.html            주소로 직접 연 종목 페이지
 *     첫 화면의 모달         목록에서 종목을 눌렀을 때
 *
 * 그리는 코드를 두 벌 두면 한쪽만 고쳐져 갈라진다. 오늘(2026-09-16)
 * 로컬과 배포본의 동작이 갈려 하루를 썼는데 원인이 같은 종류였다.
 *
 * **마크업도 베끼지 않는다.** 모달은 stock.html 을 읽어다 그 안의
 * `.kh-main` 을 떼어 쓴다 (loadStockMain). 그래서 종목 페이지를 고치면
 * 모달도 같이 바뀐다. 원본은 늘 stock.html 하나다.
 *
 * ── id 로 찾지 않고 root 안에서 찾는다 ──
 *
 * 모달이 열리면 문서에 `#kh-price` 같은 것이 생긴다. 지금은 첫 화면에
 * 같은 이름이 없지만, 나중에 생기면 엉뚱한 칸을 칠하게 된다. 그래서
 * 문서 전체가 아니라 건네받은 root 안에서만 찾는다.
 */

import { CHART_PERIODS } from '../data/market.js';
import { fetchCandles, createStockChart, maLegend } from '../chart.js';
import { getMemo, setMemo } from '../store/memo.js';
import { fmtNum, fmtWon, fmtMoneyKr, fmtShareCount, fmtDelta, dirClass }
  from '../utils/format.js';
import { paintIcon } from './stock-icon.js';
import { mountDisclosures } from './disclosures.js';

/* 서버가 5분마다 공시를 받아 두므로 화면도 그 주기에 맞춘다 */
const DISCLOSURE_RELOAD_MS = 5 * 60 * 1000;

/* stock.html 을 한 번만 받아 두고 복제해 쓴다. 종목을 바꿀 때마다
   다시 받으면 같은 파일을 되풀이해 내려받게 된다. */
let mainTemplate = null;

/**
 * stock.html 에서 `.kh-main` 을 떼어 온다. 모달이 쓴다.
 * @param {string} url 첫 화면 기준 상대 주소
 */
export async function loadStockMain(url = './stock.html') {
  if (!mainTemplate) {
    const res = await fetch(url, { cache: 'default' });
    if (!res.ok) throw new Error('종목 화면을 불러오지 못했습니다 (' + res.status + ')');
    const doc = new DOMParser().parseFromString(await res.text(), 'text/html');
    mainTemplate = doc.querySelector('.kh-main');
    if (!mainTemplate) throw new Error('종목 화면에서 본문을 찾지 못했습니다');
  }
  return mainTemplate.cloneNode(true);
}

/**
 * 종목 화면을 그린다.
 *
 * @param {HTMLElement} root   `.kh-main` 또는 그것을 담은 요소
 * @param {object} stock       market.js 의 종목 (code · name · brand)
 * @param {object} [opts]
 * @param {Function} [opts.onBack]  「← 목록」 을 눌렀을 때. 없으면 링크 그대로 둔다
 * @returns {{ paint: Function, destroy: Function }}
 */
export function mountStockView(root, stock, { onBack } = {}) {
  const $ = sel => root.querySelector(sel);

  let chart = null;
  let periodId = CHART_PERIODS[0] ? CHART_PERIODS[0].id : '1d';
  let disclosures = null;
  let reloadTimer = null;
  let dead = false;

  /* ── 헤더 ─────────────────────────────── */
  function paintHead(live) {
    paintIcon($('#kh-ic'), stock);
    setText('#kh-name', stock.name);
    setText('#kh-code', stock.code);

    const price = $('#kh-price');
    const sub = $('#kh-price-sub');
    if (!price) return;

    if (!live) {
      price.className = 'kh-price kh-num kh-mut';
      price.textContent = '불러오는 중';
      if (sub) sub.textContent = '';
      return;
    }
    const cls = dirClass(live.pct);
    price.className = 'kh-price kh-num ' + cls;
    price.textContent = fmtWon(live.price);
    if (sub) {
      sub.className = 'kh-price-sub kh-num ' + cls;
      sub.textContent = '어제보다 ' + fmtDelta(live.amt, live.pct);
    }

    setHtml('#kh-r1',  rangeBar(live.low, live.high, live.price));
    setHtml('#kh-r52', rangeBar(live.low52, live.high52, live.price));
    setText('#kh-amt', fmtMoneyKr(Math.round(live.price * live.volume / 1e8)));
    setText('#kh-vol', fmtShareCount(live.volume));
    setText('#kh-cap', fmtMoneyKr(live.marketCap));

    setText('#kh-m-per', live.per != null ? live.per + '배' : '—');
    setText('#kh-m-pbr', live.pbr != null ? live.pbr + '배' : '—');
    setText('#kh-m-cap', fmtMoneyKr(live.marketCap));
    setText('#kh-m-vol', fmtShareCount(live.volume));
    setText('#kh-m-hi',  fmtWon(live.high52));
    setText('#kh-m-lo',  fmtWon(live.low52));

    const ord = $('#kh-ord-price');
    if (ord) ord.value = fmtNum(live.price);
  }

  function setText(sel, v) { const el = $(sel); if (el) el.textContent = v; }
  function setHtml(sel, v) { const el = $(sel); if (el) el.innerHTML = v; }

  /* 현재가가 범위 어디쯤인지 점으로 */
  function rangeBar(lo, hi, cur) {
    if (lo == null || hi == null || cur == null) return '<b class="kh-mut">—</b>';
    const p = Math.max(0, Math.min(1, (cur - lo) / Math.max(1, hi - lo)));
    return `<b class="kh-num">${fmtNum(lo)}</b>
      <span class="kh-rng-bar"><i style="left:calc(${(p * 100).toFixed(1)}% - 4px)"></i></span>
      <b class="kh-num">${fmtNum(hi)}</b>`;
  }

  /* ── 차트 ─────────────────────────────── */
  function paintPeriods() {
    const box = $('#kh-per');
    if (!box) return;
    box.innerHTML = CHART_PERIODS.map(p => `
      <button data-period="${p.id}" class="${p.id === periodId ? 'is-active' : ''}">${p.label}</button>
    `).join('') + `<span class="kh-per-tools">⊞ ／ ⇄ ⤢</span>`;

    box.querySelectorAll('button').forEach(b =>
      b.addEventListener('click', () => { periodId = b.dataset.period; paintPeriods(); drawChart(); }));
  }

  async function drawChart() {
    const host = $('#kh-chart');
    const legend = $('#kh-chart-legend');
    if (!host) return;
    const key = periodId;
    if (chart) { chart.destroy(); chart = null; }
    host.innerHTML = `<div class="kh-soon"><div class="kh-soon-t">차트 불러오는 중…</div></div>`;
    try {
      const { candles, meta, period } = await fetchCandles(stock.code, periodId, 300);
      /* 그 사이 기간을 바꿨거나 모달을 닫았다 */
      if (dead || key !== periodId) return;
      if (!candles.length) throw new Error('빈 응답');
      host.innerHTML = '';
      chart = createStockChart(host, candles, { period, showVolume: true });
      if (legend) {
        legend.innerHTML = maLegend(chart.maSeries) +
          `<span class="kh-mut" style="margin-left:8px;font-size:.74rem">
            ${meta.label || ''}봉 · ${meta.source === 'DB' ? '저장됨' : '갱신됨'}</span>`;
      }
    } catch {
      if (dead || key !== periodId) return;
      host.innerHTML = `<div class="kh-soon">
        <div class="kh-soon-t">차트를 불러오지 못했습니다</div>
        <div class="kh-soon-s">중계 서버가 꺼져 있거나 응답이 없습니다</div></div>`;
      if (legend) legend.innerHTML = '';
    }
  }

  /* ── 내 메모 ──────────────────────────── */
  function setupMemo() {
    const box = $('#kh-memo');
    if (!box) return;
    box.value = getMemo(stock.code) || '';
    box.addEventListener('input', () => setMemo(stock.code, box.value));
  }

  /* ── 「← 목록」 ───────────────────────────
     모달에서는 페이지를 옮기는 것이 아니라 닫는 자리다. 목록은 이미 뒤에 있다. */
  function setupBack() {
    const btn = root.querySelector('.kh-chip-btn');
    if (!btn || !onBack) return;
    btn.removeAttribute('href');
    btn.addEventListener('click', e => { e.preventDefault(); onBack(); });
  }

  /* ── 시작 ─────────────────────────────── */
  paintHead(null);
  paintPeriods();
  drawChart();
  setupMemo();
  setupBack();

  const dcHost = $('#kh-dc');
  if (dcHost) {
    disclosures = mountDisclosures(dcHost, { code: stock.code, limit: 12, showName: false });
    reloadTimer = setInterval(() => disclosures.reload(), DISCLOSURE_RELOAD_MS);
  }

  return {
    /** 새 시세가 왔을 때 */
    paint: paintHead,

    /** 담긴 칸의 폭이 바뀌었을 때 (모달 서랍을 여닫는 자리).
     *
     * 폭 자체는 차트가 스스로 따라간다 — chart.js 가 `autoSize: true` 로
     * 만든다. 여기서는 봉이 새 폭에 고르게 퍼지도록 다시 맞추기만 한다. */
    resize() {
      if (chart && chart.chart) {
        try { chart.chart.timeScale().fitContent(); } catch { /* 이미 정리됨 */ }
      }
    },

    /** 모달을 닫을 때 부른다. 안 부르면 안 보이는 차트가 계속 돈다. */
    destroy() {
      dead = true;
      if (chart) { chart.destroy(); chart = null; }
      if (reloadTimer) { clearInterval(reloadTimer); reloadTimer = null; }
    },
  };
}
