// 투자 전략 「종목 고르는 룰」 — 홀딩스 실시간 순위 「관심」 아래 칩 여덟의 룰 (2026-11-11 · 시황분석1)
//   · 재권님 「strategy.html 여기에 실시간순위에 관심이라고 있는데 거기에 하위의 버튼별로 룰 정리해주고 그거 수정 가능하도록」(16:3x · 작업우선순위 경유) →
//     「우선 비밀번호는 나중에 하고 … 이미지부터」 → 시안 temp/시황분석1-rules3 「이런거고 지금 관심 하위의 버튼별로 있는 룰 여기에 다 넣어줘야해」 → 「응 시작해」
//   · 칩 차례는 홀딩스 「관심」 아래 줄 그대로(home.js FAV_SUB_ORDER) + 수급. 수급 = 지금까지의 「전일 거래량 급등」 룰(js/strategy-rule.js 가 그대로 그린다)
//   · 나머지 일곱은 지금은 보기만 — 고치기는 수정 비밀번호와 함께 뒤에(재권님 「우선 비밀번호는 나중에」)
//   · 룰 숫자는 그 칩을 내는 서버 응답의 meta 를 그대로 쓴다(화면에 박지 않는다) · 서버가 안 주는 숫자(홀딩스 화면 코드에만 있는 것)는 — 로 두고 그렇다고 적는다
//     (그 값을 룰 문서로 옮기는 것은 개발1 카드 「서버 칩 룰이 룰 문서 값을 읽게」)
//   · 종목은 홀딩스와 같은 서버 주소 — 목록 주소가 없는 칩(단타 · 현재상승 · 장외 — 홀딩스 화면이 순위 목록에서 셈)은 —
import { signClass, NUM } from '/assets/js/sign.js';

const $ = (id) => document.getElementById(id);
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (x, d = 0) => (x == null || !Number.isFinite(Number(x)) ? '—' : Number(x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (x) => { if (x == null || !Number.isFinite(Number(x))) return '—'; const c = signClass(Number(x), NUM); const t = `${x > 0 ? '+' : ''}${num(x, 2)}%`; return c ? `<span class="${c}">${t}</span>` : t; };
const v = (x) => `<b class="rl-v">${x == null || x === '' ? '—' : esc(x)}</b>`;   // 룰 값 — 진한 칸(나중에 고칠 자리)
const eok = (won) => { if (won == null || !Number.isFinite(Number(won))) return '—'; const e = Number(won) / 1e8; return `${num(e, Math.abs(e) < 10 ? 1 : 0)}억`; };   // 10억 아래는 소수 한 자리 — 「-0억」 이 안 나오게
const capTxt = (e) => (e == null ? '—' : `${num(e)}억`);
const MKT = { KOSPI: '코스피', KOSDAQ: '코스닥' };
const HOLD = '<span class="rl-sug">숫자는 홀딩스 화면 코드에만 있음 — 룰 문서로 옮기면 여기 나옴</span>';
const CAPROW = ['시가총액', `${v(null)} 이상 ${HOLD}`];

async function getJson(u) {
  try { const r = await fetch(u, { cache: 'no-store' }); return { st: r.status, j: r.ok ? await r.json() : null }; }
  catch (e) { return { st: 0, j: null }; }
}
// 볼린저 줄 시각 — 그날(day) 것이 아니면 날짜를 붙인다(장 뒤 신호가 다음 날 목록에 남는 때 · ts = YYYYMMDDHHMM)
const bbWhen = (x, day) => { const t = String(x.ts || ''); return t.length >= 12 && day && t.slice(0, 8) !== day ? `${t.slice(4, 6)}-${t.slice(6, 8)} ${t.slice(8, 10)}:${t.slice(10, 12)}` : (x.t || '—'); };
const tb = (head, rows) => `<div class="st-scroll"><table class="aw-tb"><tr>${head.map((h) => `<th>${h}</th>`).join('')}</tr>${rows.join('')}</table></div>`;
const nm = (x) => `<td class="st-name"><b>${esc(x.name || '—')}</b> <small>${esc(x.code || '')}</small></td>`;

// 칩마다 — 이름 · 받을 주소(없으면 null) · 룰 줄(meta → [[머리, 글]]) · 목록(응답 → { cap, html })
const RULES = {
  ov: {
    name: '단타', url: null,
    rows: () => [['고르는 조건', `아래 칩 중 ${v(null)}개 이상에 든 종목 ${HOLD}<br>세는 칩 — 관심 · 프리장 · VI·급등 · 장외 · 매수 · 초반상승 · 수급 <span class="rl-sug">장외는 장 뒤에만 셈</span>`],
      ['시가총액', '세는 칩마다의 문턱을 따름'], ['줄 세우기', '겹친 칩 수 많은 순 → 같으면 시가총액 순']],
  },
  pre: {
    name: '프리장', url: '/api/kis/pre-flow',
    rows: (m) => [['고르는 조건', `넥스트레이드 프리마켓 거래대금 상위 ${v(m.topN)}위 안 · 프로그램 순매수인 종목`],
      ['시간', `${v(m.preOpen)} ~ ${v(m.preClose)} · 그 뒤 09:00 전까지 그날 판으로 굳힘`], CAPROW, ['줄 세우기', '프로그램 순매수 큰 순']],
    list: (j) => {
      const d = Array.isArray(j.data) ? j.data : [], m = j.meta || {};
      return { cap: `${esc(m.day ? `${m.day.slice(4, 6)}-${m.day.slice(6)}` : '—')} 프리장 · ${num(d.length)}종목${m.builtAt ? ` · ${esc(m.builtAt)} 굳힘` : ''}`,
        html: d.length ? tb(['종목', '등락률', '거래대금', '프로그램 순매수'], d.map((x) => `<tr>${nm(x)}<td>${pct(x.pct)}</td><td>${eok(x.amt)}</td><td><b>${eok(x.program)}</b></td></tr>`)) : null };
    },
  },
  rise: {
    name: '초반상승', url: '/api/kis/open-rise',
    rows: (m) => [['고르는 조건', `${v(m.barFrom)} ~ ${v(m.barTo)} 첫 5분봉이 시가 대비 ${v(m.risePct)}% 이상 오름 · ETF 뺌`],
      ['시가총액', `${v(m.minCapEok == null ? null : num(m.minCapEok))}억원 이상`], ['줄 세우기', '첫 봉 상승률 큰 순 · 그날 판으로 굳힘']],
    list: (j) => {
      const d = Array.isArray(j.data) ? j.data : [], m = j.meta || {};
      return { cap: `${esc(m.day ? `${m.day.slice(4, 6)}-${m.day.slice(6)}` : '—')} 첫 봉 · ${num(d.length)}종목 · 살핀 ${num(m.candidates)}(ETF 뺌 ${num(m.etfOut)})`,
        html: d.length ? tb(['종목', '시장', '시가 → 첫 봉 종가', '첫 봉 상승률', '시가총액'], d.map((x) => `<tr>${nm(x)}<td>${esc(MKT[x.market] || x.market || '—')}</td><td>${num(x.open)} → ${num(x.close)}</td><td><b>${pct(x.pct)}</b></td><td>${capTxt(x.cap)}</td></tr>`)) : null };
    },
  },
  nowup: {
    name: '현재상승', url: null,
    rows: () => [['고르는 조건', `지금 값이 오늘 시가보다 ${v(null)}% 이상 높은 종목 ${HOLD}`], CAPROW, ['줄 세우기', '시가 대비 큰 순']],
  },
  vi: {
    name: 'VI·급등', url: '/api/alerts/today',
    rows: (m) => [['고르는 조건', `정규장(${v(m.session)})에 상승 VI 가 걸렸거나 전일 대비 ${v(m.surgePct)}% 이상 오른 종목`], CAPROW, ['줄 세우기', '최근 것이 위']],
    list: (j) => {
      const d = (j.data && Array.isArray(j.data.items)) ? j.data.items : [];
      const seen = new Set(), rows = [...d].sort((a, b) => String(b.t).localeCompare(String(a.t))).filter((x) => !seen.has(x.code) && seen.add(x.code));   // 한 종목은 가장 최근 한 줄
      return { cap: `${esc(j.data && j.data.day ? `${j.data.day.slice(4, 6)}-${j.data.day.slice(6)}` : '—')} · ${num(rows.length)}종목 · 시가총액 문턱 거르기 전 전부(문턱은 홀딩스 화면이 거름)`,
        html: rows.length ? tb(['종목', '시각', '무엇', '등락률', '시가총액'], rows.map((x) => `<tr>${nm(x)}<td>${esc(String(x.t || '').slice(0, 5) || '—')}</td><td>${x.kind === 'surge' ? '급등' : `VI ${esc(x.sub || '')}`}</td><td>${pct(x.pct)}</td><td>${capTxt(x.cap)}</td></tr>`)) : null };
    },
  },
  bb: {
    name: '볼린저', url: '/api/signals/today',
    rows: (m) => [['고르는 조건', `같은 ${v(m.period == null ? null : String(m.period).replace(/^(\d+)m$/, '$1분'))} 봉에서 셋이 함께 —<br>① 저가가 볼린저 하단(${v(m.bb)})에 닿고 양봉<br>② MACD 히스토그램이 음수인데 직전보다 커짐<br>③ RSI 가 ${v(m.rsi)} 아래에서 오르기 시작`],
      CAPROW, ['줄 세우기', '최근 것이 위 · 텔레그램 「바닥 신호」 와 같은 기록']],
    list: (j) => {
      const d = (j.data && Array.isArray(j.data.items)) ? [...j.data.items].sort((a, b) => String(b.ts || b.t).localeCompare(String(a.ts || a.t))) : [];
      return { cap: `${esc(j.data && j.data.day ? `${j.data.day.slice(4, 6)}-${j.data.day.slice(6)}` : '—')} · ${num(d.length)}번 · 시가총액 문턱 거르기 전 전부(문턱은 홀딩스 화면이 거름)`,
        html: d.length ? tb(['종목', '시각', '그 봉 종가', '저가', '시가총액'], d.map((x) => `<tr>${nm(x)}<td>${esc(bbWhen(x, j.data.day))}</td><td>${num(x.close)}</td><td>${num(x.low)}</td><td>${capTxt(x.cap)}</td></tr>`)) : null };
    },
  },
  after: {
    name: '장외', url: null,
    rows: () => [['고르는 조건', '정규장 종가 뒤(넥스트레이드 애프터 · 다음 날 프리마켓)에 종가보다 오른 종목 · 문턱 없음<br><span class="rl-sug">평일 09:00 ~ 15:40 은 비어 있음</span>'], CAPROW, ['줄 세우기', '종가 대비 등락률 순']],
  },
};

// ── 칩 바꾸기 — 수급(volsurge)은 strategy-rule.js 의 칸 그대로 · 나머지는 같은 자리에 갈아 끼운다(칸 높이는 CSS 가 같게 잡는다)
const chips = [...document.querySelectorAll('#rl-chips [data-rule]')];
const tb1 = $('rl-tb'), tb2 = $('rl-tb2'), title = $('rl-title'), go = $('rl-go');
const awH = document.querySelector('h3.aw-tabs[role="tablist"]'), crH = $('cr-h'), how = $('aw-how');
const panes = [...document.querySelectorAll('.aw-pane')], crPane = document.querySelector('.aw-pane[data-pane="chip"]');
let seq = 0;

async function show(id) {
  chips.forEach((c) => { const on = c.dataset.rule === id; c.classList.toggle('is-active', on); c.setAttribute('aria-selected', on ? 'true' : 'false'); });
  const vol = id === 'volsurge';
  tb1.hidden = !vol; tb2.hidden = vol; go.hidden = !vol; awH.hidden = !vol; crH.hidden = vol;
  how.style.visibility = vol ? '' : 'hidden';   // 「이 룰은 이렇게 셈합니다」 는 수급 것 — 자리는 남겨 칩을 바꿔도 판 높이 그대로(「보는 것을 바꿔도 자리는 그대로다」)
  if (vol) {
    title.textContent = '룰 — 전일 거래량 급등';
    (document.querySelector('.aw-tab.is-on') || document.querySelector('.aw-tab'))?.click();   // 현재 · 어제 판을 고르던 그대로 되살림
    return;
  }
  const R = RULES[id], my = ++seq;
  panes.forEach((p) => { p.hidden = p !== crPane; });
  title.textContent = `룰 — ${R.name}`;
  tb2.innerHTML = R.rows({}).map(([h, t]) => `<tr><th>${h}</th><td>${t}</td></tr>`).join('');
  if (!R.url) { $('cr-cap').textContent = `「${R.name}」 종목`; $('cr').innerHTML = '<div class="st-err">— 서버에 이 칩의 종목 목록 주소가 없음(홀딩스 화면이 순위 목록에서 셈)</div>'; return; }
  $('cr-cap').textContent = '값을 받는 중…'; $('cr').innerHTML = '<div class="st-err">—</div>';
  const { st, j } = await getJson(R.url);
  if (my !== seq) return;
  if (!j || j.ok === false) { $('cr-cap').textContent = `「${R.name}」 종목`; $('cr').innerHTML = `<div class="st-err">— 서버 값을 못 받음(${esc((j && j.error) || st || '연결 안 됨')})</div>`; return; }
  const m = j.meta || (j.data && j.data.meta) || {};
  tb2.innerHTML = R.rows(m).map(([h, t]) => `<tr><th>${h}</th><td>${t}</td></tr>`).join('');
  const L = R.list(j);
  $('cr-cap').textContent = L.cap.replace(/<[^>]+>/g, '');
  $('cr').innerHTML = L.html || '<div class="st-err">— 이 룰에 걸린 종목 없음</div>';
}
chips.forEach((c) => c.addEventListener('click', () => show(c.dataset.rule)));
