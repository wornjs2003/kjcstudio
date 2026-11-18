/* 레버리지 지표 — 홈 위 지수 띠 끝 「신용융자」 칸 · 누르면 모달 (2026-11-17 · 11-18 자리 옮김)
 *
 * 재권님 「홀딩스 화면에서 보고싶은데. 실시간이면 더 좋고」 · 「세마녀의날 옆에 있으면 좋을거같아」 → 시안 「가로 해줘」 ·
 * 「가에 신용융자 누르면 모달 띄워지게 버튼처럼」 · 「모달로 띄워지면 변동이 그래프로 보여지게」.
 *
 * 값과 셈은 서버 하나다 — GET /api/market/leverage (server/leverage.py). 실시간 자료는 없다(한국 매일 · 하루 늦게 / 미국 달 · 분기) —
 * 값마다 기준 날짜를 붙인다. 다시 묻는 주기를 두지 않는다 — 화면을 열 때 한 번 · 모달을 열 때 한 번 받는다(서버가 들고 있다).
 * 그래프는 홈 큰 차트와 같은 라이브러리 · 조작 옵션은 기본값 그대로다(「그래프 움직이기는 홈 큰 차트가 기준이다」).
 * 탭을 바꿔도 칸 높이는 그대로다(CSS 가 잡는다 — 「보는 것을 바꿔도 자리는 그대로다」).
 */
import { openModal } from './modal.js';
import { apiFetch } from '../data/api.js';
import { signClass } from '/assets/js/sign.js';

const URL = '/api/market/leverage';
const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

let last = null;                 // 받은 응답 — 못 받았으면 null
const jo = (m) => (m == null ? '—' : (m / 1e6).toFixed(1) + '조');                  // 백만 원 → 조
const usd = (m) => (m == null ? '—' : (m / 1e6).toFixed(2) + '조$');                // 백만 달러 → 조 달러
const md = (d) => (d ? d.slice(5).replace('-', '-') : '—');
const tail = (a) => (a && a.length ? a[a.length - 1] : null);

/* 탭 넷 — 줄마다 [값 열쇠, 이름, 색 변수] · 값 꼴 · 앞과의 차이 꼴 */
const TABS = [
  { id: 'kr', name: '한국 신용융자', src: 'kr', unit: '조 원', fmt: (v) => (v / 1e6).toFixed(2),
    lines: [['total', '신용융자 전체', '--kh-text-primary'], ['kospi', '코스피', '--kh-cat-indigo'], ['kosdaq', '코스닥', '--kh-cat-teal'],
            ['deposit', '예탁증권담보융자', '--kh-cat-amber']],
    note: '빚을 내 산 주식(신용융자)과 가진 주식을 맡기고 빌린 돈(예탁증권담보융자)' },
  { id: 'finra', name: '미국 개인 빚투', src: 'finra', unit: '조 달러', fmt: (v) => (v / 1e6).toFixed(3),
    lines: [['v', '증거금 계좌 빚', '--kh-text-primary']],
    note: '미국 증권사 고객 증거금 계좌의 빚(Debit Balances) · 달마다' },
  { id: 'lev', name: '헤지펀드 레버리지', src: 'hfLev', unit: '배', fmt: (v) => v.toFixed(2),
    lines: [['v', '주식 전략 레버리지', '--kh-text-primary']],
    note: '주식 전략 헤지펀드의 총자산 ÷ 순자산(자산 가중 평균) · 분기' },
  { id: 'gn', name: '헤지펀드 총 · 넷', src: 'hfGross', unit: '%', fmt: (v) => v.toFixed(1),
    lines: [['gross', '총 노출(매수 + 공매도)', '--kh-cat-rose'], ['net', '넷 노출(매수 − 공매도)', '--kh-cat-indigo']],
    note: '헤지펀드 주식 매수 · 공매도를 순자산으로 나눈 근사 · 분기' },
];

/* 탭마다 그래프 줄 — {열쇠: [{time, value}]} */
function seriesOf(t, d) {
  if (t.id === 'kr') {
    const o = {};
    for (const [k] of t.lines) o[k] = (d.kr || []).filter((r) => r[k] != null).map((r) => ({ time: r.d, value: r[k] }));
    return o;
  }
  if (t.id === 'finra') return { v: (d.finra || []).map((r) => ({ time: r.d + '-01', value: r.v })) };
  if (t.id === 'lev') return { v: (d.hfLev || []).map((r) => ({ time: r.d, value: r.v })) };
  return { gross: (d.hfGross || []).map((r) => ({ time: r.d, value: r.v })), net: (d.hfNet || []).map((r) => ({ time: r.d, value: r.v })) };
}

async function load() {
  try {
    const r = await apiFetch(URL, { cache: 'no-store' });
    const j = r && r.ok ? await r.json() : null;
    return j && j.data ? j : null;
  } catch { return null; }
}

/* 지수 띠 끝 칸 — 받기 전 · 못 받으면 빈 글(자리를 안 만든다 · 받으면 다시 그린다).
 * 처음에는 장 상태 줄의 옵션 만기 칩 옆이었는데 그 줄이 두 줄로 꺾여 큰 차트가 12px 줄어 재권님 「나」(11-18) — 위 지수 띠 끝으로.
 * 모양은 지수 칸(.kh-ix)과 같다 — 칸 크기가 같아 띠 높이가 안 바뀐다. 값은 한국 신용융자 전체 · 앞 날 대비 */
export function leverageCell() {
  const d = last && last.data;
  const kr = d && d.kr;
  const k = tail(kr);
  if (!k) return '';
  const p = kr.length > 1 ? kr[kr.length - 2] : null;
  const dv = p && p.total != null ? k.total - p.total : null;
  const f = tail(d.finra), l = tail(d.hfLev), g = tail(d.hfGross), n = tail(d.hfNet);
  const tip = [
    '레버리지 지표 — 누르면 그래프',
    `한국 신용융자 ${jo(k.total)} 원(코스피 ${jo(k.kospi)} · 코스닥 ${jo(k.kosdaq)}) · 예탁증권담보융자 ${jo(k.deposit)} — ${k.d} · 하루 늦게 나옴`,
    f ? `미국 개인 빚투 ${usd(f.v)} — ${f.d}` : '미국 개인 빚투 — 못 받음',
    l ? `헤지펀드 레버리지 ${l.v.toFixed(2)}배 — ${l.d.slice(0, 7)}` : '헤지펀드 레버리지 — 못 받음',
    g && n ? `헤지펀드 총 ${Math.round(g.v)}% · 넷 ${Math.round(n.v)}% — ${g.d.slice(0, 7)}` : '헤지펀드 총 · 넷 — 못 받음',
  ].join('\n');
  const cls = dv == null ? 'kh-mut' : signClass(dv);
  const chg = dv == null ? '—' : `${dv > 0 ? '▲' : dv < 0 ? '▼' : ''}${(Math.abs(dv) / 1e6).toFixed(2)}조 <span class="kh-mut">앞 날 대비</span>`;
  return `<div class="kh-ix kh-lev-ix" data-lev role="button" tabindex="0" data-tip="${tip}" aria-label="레버리지 지표 열기">
      <div class="kh-ix-h"><span class="kh-ix-n">신용융자</span><span class="kh-bd">${md(k.d)}</span></div>
      <div class="kh-ix-b"><div>
        <div class="kh-ix-v kh-num">${jo(k.total)}</div>
        <div class="kh-ix-c kh-num ${cls}">${chg}</div>
      </div></div>
    </div>`;
}

function open() {
  let chart = null;
  const m = openModal({ label: '레버리지 지표', width: 760, fade: false,
    head: { name: '레버리지 지표', sub: '빚을 내 산 돈 — 실시간 자료가 없어 기준 날짜를 함께 봅니다' },
    onClose: () => { if (chart) { chart.remove(); chart = null; } } });
  m.body.innerHTML = `<div class="lv-wrap"><div class="fg-tabs">${TABS.map((t) => `<button type="button" data-k="${t.id}">${t.name}</button>`).join('')}</div>
    <div class="lv-body"><div class="lv-top"></div><div class="lv-legend"></div><div class="lv-chart"></div><div class="lv-note kh-mut"></div></div></div>`;
  const $q = (s) => m.body.querySelector(s);
  let cur = 'kr';

  const show = (id) => {
    cur = id;
    m.body.querySelectorAll('.fg-tabs button').forEach((b) => b.classList.toggle('is-on', b.dataset.k === id));
    if (chart) { chart.remove(); chart = null; }
    const d = last && last.data;
    const t = TABS.find((x) => x.id === id);
    const ser = d ? seriesOf(t, d) : {};
    const main = ser[t.lines[0][0]] || [];
    const box = $q('.lv-chart');
    if (!main.length) {
      $q('.lv-top').innerHTML = '';
      $q('.lv-legend').innerHTML = '';
      box.innerHTML = `<div class="fg-empty">${last ? '이 자료를 못 받았습니다' : '불러오는 중'}</div>`;
      $q('.lv-note').textContent = t.note;
      return;
    }
    box.innerHTML = '';
    /* 머리 — 마지막 값 · 기준 날짜 · 앞 값과의 차이 */
    const a = main[main.length - 1], b = main.length > 1 ? main[main.length - 2] : null;
    const dv = b ? a.value - b.value : null;
    const dfmt = dv == null ? '' : `<b class="${signClass(dv)}">${dv > 0 ? '▲' : dv < 0 ? '▼' : ''}${t.fmt(Math.abs(dv))}</b> <span class="kh-mut">앞 자료(${b.time}) 대비</span>`;
    $q('.lv-top').innerHTML = `<b class="lv-big">${t.fmt(a.value)}</b> <span>${t.unit}</span> <span class="kh-mut">${a.time} 기준</span> ${dfmt}`;
    $q('.lv-legend').innerHTML = t.lines.map(([k, nm, c]) => ser[k] && ser[k].length
      ? `<span><i style="background:var(${c})"></i>${nm} <b>${t.fmt(ser[k][ser[k].length - 1].value)}</b></span>` : '').join('');
    const fail = d.fail && d.fail[t.src === 'kr' ? 'kr' : t.src === 'finra' ? 'finra' : 'hf'];
    $q('.lv-note').textContent = t.note + ` · 출처 ${(d.sources || {})[t.src === 'kr' ? 'kr' : t.src === 'finra' ? 'finra' : 'hf'] || ''}`
      + (fail ? ` · 이번에 못 받아 앞 값(${fail})` : '');

    const LC = window.LightweightCharts;
    if (!LC) { box.innerHTML = '<div class="fg-empty">차트를 그리지 못했습니다</div>'; return; }
    chart = LC.createChart(box, {
      width: box.clientWidth, height: box.clientHeight,
      layout: { background: { color: 'transparent' }, textColor: cssVar('--kh-chart-axis'), attributionLogo: false },
      grid: { vertLines: { color: cssVar('--kh-chart-grid') }, horzLines: { color: cssVar('--kh-chart-grid') } },
      timeScale: { borderColor: cssVar('--kh-chart-border') },
      rightPriceScale: { borderColor: cssVar('--kh-chart-border') },
      crosshair: { vertLine: { color: cssVar('--kh-chart-crosshair') }, horzLine: { color: cssVar('--kh-chart-crosshair') } },
      localization: { priceFormatter: (v) => t.fmt(v) },
    });
    for (const [k, , c] of t.lines) {
      if (!ser[k] || !ser[k].length) continue;
      const s = chart.addSeries(LC.LineSeries, { color: cssVar(c), lineWidth: k === t.lines[0][0] ? 2 : 1, priceLineVisible: false });
      s.setData(ser[k]);
    }
    chart.timeScale().fitContent();
  };

  m.body.querySelector('.fg-tabs').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-k]');
    if (b) show(b.dataset.k);
  });
  show(cur);
  /* 모달을 열 때 한 번 더 받는다 — 서버가 들고 있어 바깥을 또 부르지는 않는다 */
  load().then((j) => { if (j) { last = j; if (m.body.isConnected) show(cur); } });
}

/* root — 칸이 들어가는 줄(지수 띠). 그 줄은 자주 다시 그려져 누르기 · Enter 는 줄에 한 번 건다 · repaint — 받은 뒤 줄을 다시 그리기 */
export function mountLeverage(root, repaint) {
  if (!root) return;
  root.addEventListener('click', (e) => { if (e.target.closest('[data-lev]')) open(); });
  root.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.closest('[data-lev]')) open(); });
  load().then((j) => {
    if (!j) return;
    last = j;
    repaint();
    if (new URLSearchParams(location.search).get('lev') === '1') open();     // 주소로 바로 열기(?lev=1) — 그림으로 보여 드릴 때
  });
}
