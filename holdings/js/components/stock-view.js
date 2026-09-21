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
import { apiFetch } from '../data/api.js';

/* 서버가 5분마다 공시를 받아 두므로 화면도 그 주기에 맞춘다 */
const DISCLOSURE_RELOAD_MS = 5 * 60 * 1000;

/* 체결은 장중에 계속 쌓인다. 서버 캐시가 3초라 그보다 짧게 부를 이유가 없다.
   **확인용 서버(--slow)에서는 5분 캐시**라 값이 그만큼 묵어 보인다 — 정상이다. */
const TICKS_RELOAD_MS = 5 * 1000;

/* 일별 매매동향은 하루 한 번 바뀐다. 화면을 열어둔 채로도 날짜가 넘어가게 */
const FLOW_RELOAD_MS = 10 * 60 * 1000;

/* 체결을 몇 줄까지 보일 것인가. 서버는 30줄을 준다.
   **12줄이면 그 줄이 1행보다 76px 길어진다**(2026-09-21 지적 — "또 세로로
   길어졌는데"). 같은 줄의 「내 메모」·「개인·외국인·기관」이 끌려서 함께
   커지므로, 1행(차트 줄)에 맞춰 줄인다. 나머지는 칸 안에서 굴러간다. */
const TICKS_SHOWN = 9;

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

  /* ── 체결 · 일별 매매동향 (2026-09-21 지시 — A 종목 화면) ──

     둘 다 종목 화면에만 있다. 첫 화면 오른쪽 패널의 「투자자 정보」와
     겹쳐 보이지만 **출처와 기간이 다르다** —

         첫 화면    KIS · 30일 · 개인/외국인/기관 순매수
         여기       네이버 · 5일 · 위 셋 + **외인 보유율**

     네이버 쪽은 KIS 예산을 안 쓰고 지표 18개(PER·PBR·52주·배당)가 함께 온다. */

  async function loadTicks() {
    const box = $('#kh-ticks');
    if (!box) return;
    try {
      const r = await apiFetch(`/api/kis/ticks?code=${stock.code}`, { cache: 'no-store' });
      if (!r || !r.ok) throw new Error(r && r.status);
      const b = await r.json();
      const rows = Array.isArray(b.data) ? b.data : [];
      const power = b.meta && b.meta.power;

      const p = $('#kh-tick-power');
      if (p) {
        p.textContent = power != null ? power.toFixed(2) : '—';
        /* 100 이 기준이다. 넘으면 산 쪽이 세다 — 상승색으로 읽게 한다 */
        p.className = 'kh-num ' + (power == null ? '' : dirClass(power - 100));
      }
      if (!rows.length) {
        box.innerHTML = '<div class="kh-mut">체결이 아직 없습니다</div>';
        return;
      }
      box.innerHTML = rows.slice(0, TICKS_SHOWN).map((t) => `
        <div class="kh-tick">
          <span class="kh-tick-t">${t.at}</span>
          <b class="kh-num ${dirClass(t.pct)}">${fmtNum(t.price)}</b>
          <span class="kh-num kh-tick-q">${fmtNum(t.volume)}</span>
          <span class="kh-num ${dirClass(t.pct)}">${t.pct > 0 ? '+' : ''}${t.pct.toFixed(2)}%</span>
        </div>`).join('');
    } catch {
      box.innerHTML = '<div class="kh-mut">체결을 불러오지 못했습니다</div>';
    }
  }

  async function loadFlow() {
    const box = $('#kh-flow');
    try {
      const r = await apiFetch(`/api/naver/integration?code=${stock.code}`, { cache: 'no-store' });
      if (!r || !r.ok) throw new Error(r && r.status);
      const b = await r.json();
      const d = b.data || {};
      const flow = Array.isArray(d.flow) ? d.flow : [];

      /* 머리 통계 — 가장 최근 날짜의 순매수와 시총 순위 */
      const last = flow[0];
      if (last) {
        setHtml('#kh-foreign', shares(last.foreign));
        setHtml('#kh-inst', shares(last.inst));
      }
      /* **배포본에서는 늘 「—」다.** 순위는 공시 수집이 아침마다 받아 두는
         표(market.db)에서 오는데 워커에는 그 표가 없다. 로컬에서는 숫자가
         나오므로 그냥 「—」만 두면 **고장으로 읽힌다** (2026-09-21 지적).
         칸이 좁아 문구를 못 넣으니 마우스를 올렸을 때 이유가 보이게 한다. */
      const rankEl = $('#kh-rank');
      if (rankEl) {
        rankEl.textContent = d.rank != null ? `${d.rank}위` : '—';
        rankEl.title = d.rank != null
          ? '코스피 시가총액 순위 (매일 아침 갱신)'
          : '코스피 200위 밖이거나, 이 PC 의 서버가 아니어서 순위를 모릅니다';
      }

      if (!box) return;
      if (!flow.length) {
        box.innerHTML = '<div class="kh-mut">매매동향을 받지 못했습니다</div>';
        return;
      }
      /* 막대는 그 닷새 안에서 가장 큰 값을 기준으로 잡는다 */
      let max = 1;
      flow.forEach((f) => ['person', 'foreign', 'inst'].forEach((k) => {
        max = Math.max(max, Math.abs(f[k] || 0));
      }));
      const line = (label, key) => {
        const v = last[key] || 0;
        const w = Math.abs(v) / max * 100;
        return `<div class="kh-flow"><span class="kh-flow-l">${label}</span>
          <span class="kh-flow-v kh-num ${dirClass(v)}">${shares(v)}</span>
          <span class="kh-flow-bar"><i class="${v >= 0 ? 'up' : 'dn'}"
            style="width:${w.toFixed(1)}%"></i></span></div>`;
      };
      box.innerHTML = line('개인', 'person') + line('외국인', 'foreign') + line('기관', 'inst')
        + `<div class="kh-flow-note">${dateText(last.date)} 하루치 ·
             외국인 보유 ${last.foreignRate != null ? last.foreignRate + '%' : '—'}
             · 최근 ${flow.length}일 중 가장 큰 값을 100% 로 그립니다</div>`;
    } catch {
      if (box) box.innerHTML = '<div class="kh-mut">매매동향을 불러오지 못했습니다</div>';
    }
  }

  /* 주 → 만주. 순매수는 자릿수가 커서 그대로 쓰면 칸을 넘는다 */
  function shares(n) {
    if (n == null || !Number.isFinite(n)) return '—';
    const v = n / 10000;
    return `${v > 0 ? '+' : ''}${v.toFixed(1)}만주`;
  }

  /* 20260918 → 09.18 */
  function dateText(d) {
    const t = String(d || '');
    return t.length === 8 ? `${t.slice(4, 6)}.${t.slice(6)}` : t;
  }

  loadTicks();
  loadFlow();
  const tickTimer = setInterval(() => { if (!document.hidden && !dead) loadTicks(); }, TICKS_RELOAD_MS);
  const flowTimer = setInterval(() => { if (!document.hidden && !dead) loadFlow(); }, FLOW_RELOAD_MS);

  return {
    /** 새 시세가 왔을 때 */
    paint: paintHead,

    /** 담긴 칸의 폭이 바뀌었을 때 (모달 서랍을 여닫는 자리).
     *
     * 폭 자체는 차트가 스스로 따라간다 — chart.js 가 `autoSize: true` 로
     * 만든다. 여기서는 보는 창을 다시 맞추기만 한다.
     *
     * fitContent() 를 부르면 안 된다. 있는 봉을 전부 채워 넣어서 봉 크기가
     * 종목마다 갈린다 — 그것을 고치려고 chart.js 가 창을 고정해 뒀다. */
    resize() {
      if (chart && chart.resetView) {
        try { chart.resetView(); } catch { /* 이미 정리됨 */ }
      }
    },

    /** 모달을 닫을 때 부른다. 안 부르면 안 보이는 차트가 계속 돈다. */
    destroy() {
      dead = true;
      if (chart) { chart.destroy(); chart = null; }
      if (reloadTimer) { clearInterval(reloadTimer); reloadTimer = null; }
      clearInterval(tickTimer);
      clearInterval(flowTimer);
    },
  };
}
