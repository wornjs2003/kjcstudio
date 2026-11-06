// 투자 전략 「종목 고르는 룰」 — 빈칸 값을 재권님이 직접 넣는다 (2026-11-05 재권님 「그 숫자는 내가 넣을 수 있게 해줘」).
//   · 값은 서버 문서 한 곳 — /api/board/doc/strategy-rules (GET 읽기 · PUT {data} 쓰기 · 세션 서버는 개발 서버 8765 로 넘긴다).
//     자동 관심종목(보드 카드 「전일 거래량 급등 종목 기준 확인」)을 만들게 되면 서버도 이 문서를 읽는다 — 기준은 이 한 곳(「같은 값은 한 곳에만 둔다」)
//   · 모양: { rules: { volsurge: { prevPct, volMult, sectorPct, sortBy('mult' 배수 순 | 'pct' 등락률 순), autoMax(정수 · 몇 종목까지),
//                                   buyWhen, targetPct, stopPct, holdDays, perStockPct, maxStocks, exclude } } } — 빈칸은 null(0 이 아니다) · sortBy 가 null 이면 서버가 배수 순
//   · 「오늘 이 룰에 걸린 종목」 — 서버 /api/auto-watch 가 이 문서를 부를 때마다 다시 읽어 거르고 줄 세운다. 화면은 그 결과를 그리기만 하고(거르는 셈을 두지 않는다)
//     칸은 바꾸면 바로 저장되고, 「검색」 단추를 누르면 저장이 끝난 뒤 다시 부른다(11-05 재권님 「숫자 바꾸고 나서 오른쪽 위에 검색 버튼 누르면 검색되게 해줘」) · 「없음」(null) 은 0 이 아니라 「—」 · 받는 방법 줄도 응답의 meta 로 쓴다(서버 상수를 화면에 다시 적지 않는다)
//   · 칸을 떠나면(change) 바로 저장 · 숫자 칸에 숫자가 아닌 글 · data-min 밑 · data-int 칸의 소수는 넣지 않고 그 칸을 되돌린다 · 남이 그 사이 고쳤으면(409) 다시 읽고 알린다
import { signClass, NUM } from '/assets/js/sign.js';   // 오르내림 글씨 색 — 셈은 sign.js 한 곳
import { everyServerMs } from '/holdings/js/store/timing.js';   // 장중 다시 받는 주기 — 서버 auto_watch.LIVE_SEC 값(화면에 안 박는다)
const DOC = '/api/board/doc/strategy-rules';
const AW = '/api/auto-watch';
const RULE = 'volsurge';
const meta = document.getElementById('rl-meta');
const ins = [...document.querySelectorAll('#rl-tb .rl-in')];
let doc = { rules: {} }, at = null;
let lastWarn = '';   // 마지막으로 칸을 되돌리거나 저장하지 못한 까닭 — 검색 단추가 덮지 않게 이어 쓴다 · 저장이 되면 비운다
const hm = () => { const d = new Date(); return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };

function fill() {
  const r = (doc.rules || {})[RULE] || {};
  ins.forEach((el) => {
    const v = r[el.dataset.k];
    if (el.tagName === 'SELECT') { el.value = v || el.options[0].value; el.dataset.v = el.value; return; }   // 고르는 칸은 빈칸이 없다 — 안 고르면 첫 것(배수 순)
    el.value = v == null ? '' : String(v); el.dataset.v = el.value; el.placeholder = '( )';
  });
  const n = ins.filter((el) => el.value === '').length;
  meta.textContent = n ? `빈칸 ${n}개는 아직 정하지 않음(빨간 칸) · 눌러서 넣으시면 바로 저장됩니다` : '룰 값이 다 들어감 · 고치시면 바로 저장됩니다';
}

async function load() {
  try {
    const r = await fetch(DOC, { cache: 'no-store' });
    const j = r.ok ? await r.json() : null;
    if (r.ok && j) { doc = (j.data && typeof j.data === 'object') ? j.data : { rules: {} }; at = j.updatedAt ?? (j.data && j.data.updatedAt) ?? null; }
    else if (r.status !== 404) throw new Error(String(r.status));
    fill();
  } catch (e) {
    ins.forEach((el) => { el.disabled = true; el.placeholder = '( )'; });
    meta.textContent = `룰 값을 못 받음(${e.message || '연결 안 됨'}) — 지금은 넣을 수 없습니다`;
  }
}

async function save(el) {
  const k = el.dataset.k, raw = el.value.trim();
  let v = raw === '' ? null : raw;
  if (v != null && !el.classList.contains('rl-txt') && el.tagName !== 'SELECT') {
    const x = Number(raw.replace(/,/g, ''));
    const back = (msg) => { el.value = el.dataset.v || ''; lastWarn = `${msg} — 그 칸은 되돌렸습니다`; meta.textContent = lastWarn; };
    if (!Number.isFinite(x)) return back('숫자만 넣을 수 있습니다');
    if ('min' in el.dataset && x < Number(el.dataset.min)) return back(`${el.dataset.min} 이상만 넣을 수 있습니다(손절은 빼기표 없이 넣습니다)`);
    if ('int' in el.dataset && !Number.isInteger(x)) return back('정수만 넣을 수 있습니다');
    v = x;
  }
  doc.rules = doc.rules || {};
  doc.rules[RULE] = { ...(doc.rules[RULE] || {}), [k]: v };
  meta.textContent = '저장하는 중…';
  try {
    const r = await fetch(DOC, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ data: doc, ...(at ? { updatedAt: at } : {}) }) });
    if (r.status === 409) { await load(); lastWarn = '그 사이 다른 곳에서 고쳐 다시 읽었습니다 — 한 번 더 넣어 주십시오'; meta.textContent = lastWarn; return; }
    if (!r.ok) throw new Error(String(r.status));
    const j = await r.json().catch(() => null);
    at = (j && (j.updatedAt ?? (j.data && j.data.updatedAt))) ?? at;
    el.value = v == null ? '' : String(v); // 「1,000」 · 「1e3」 을 저장된 값(1000)으로 보인다
    el.dataset.v = el.value;
    const n = ins.filter((x) => x.value === '').length;
    lastWarn = '';
    meta.textContent = `저장됨 ${hm()}${n ? ` · 빈칸 ${n}개 남음` : ' · 다 들어감'}`;
  } catch (e) {
    lastWarn = `저장 못 함(${e.message || '연결 안 됨'}) — 넣은 값은 이 화면에만 있습니다`; meta.textContent = lastWarn;
  }
}

// ── 오늘 이 룰에 걸린 종목 ──
const awBox = document.getElementById('aw'), awCap = document.getElementById('aw-cap'), awHow = document.getElementById('aw-how');
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (x, d = 0) => (x == null || !Number.isFinite(Number(x)) ? '—' : Number(x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d }));
const pctTxt = (x) => { if (x == null || !Number.isFinite(Number(x))) return '—'; const c = signClass(Number(x), NUM); const t = `${x > 0 ? '+' : ''}${num(x, 2)}%`; return c ? `<span class="${c}">${t}</span>` : t; };
const IDX = { KOSPI: '코스피', KOSDAQ: '코스닥' };
const mmdd = (d) => { const m = String(d || '').match(/(\d{4})-?(\d{2})-?(\d{2})/); return m ? `${m[2]}-${m[3]}` : (d || '—'); };

// 신고가 부근 표시 (11-05 「가랑 나랑 구분만 되면」) — 서버가 붙여 주는 nearHigh(부근인가) · nearHighOnly(위 조건 밖인데 부근이라 더 넣음) 그대로 · 맨 위로 올리는 것도 서버 순서
const nhTag = (p) => (!p.nearHigh ? '' : `<span class="aw-nh${p.nearHighOnly ? ' only' : ''}"${p.high52 != null ? ` title="52주 최고 종가 ${num(p.high52)} · ${p.highGapPct == null ? '—' : `${p.highGapPct > 0 ? '+' : ''}${num(p.highGapPct, 2)}%`}"` : ''}>${p.nearHighOnly ? '신고가 부근만' : '신고가 부근'}</span>`);
// 장중 상위 (11-06 재권님 「관심종목에 실시간으로」 · 「장중 값으로 갱신」 · 「상위 20개만」) — 서버 meta.live 그대로(순서 · 개수도 서버) ·
// 그날 확정 판(d.day)이 같은 날로 나오면 장중 표는 내린다 — 못 받았으면 서버 글(liveError)을 그대로
const liveHm = (at) => (String(at || '').match(/T(\d{2}:\d{2})/) || [])[1] || '—';
function liveHtml(m, d) {
  const L = m.live;
  if (m.liveError && !L) return `<div class="st-err">— 장중: ${esc(m.liveError)}</div>`;
  if (!L || !L.day || (d.day && ymd(d.day) >= ymd(L.day))) return '';
  const top = Array.isArray(L.top) ? L.top : [];
  const cap = `장중 ${liveHm(L.at)} · 장 ${L.frac == null ? '—' : num(L.frac * 100)}% 지남 · 관심종목에 넣는 상위 ${num(top.length)}${L.hitAll != null ? `(걸린 ${num(L.hitAll)})` : ''}`;
  if (L.ready === false) return `<div class="aw-why-s">${cap}</div><div class="st-err">— 기준 칸이 비어 장중에도 안 거름</div>`;
  if (!top.length) return `<div class="aw-why-s">${cap}</div><div class="st-err">— 지금 걸린 종목 없음</div>`;
  return `<div class="aw-why-s">${cap}</div><div class="st-scroll"><table class="aw-tb"><tr><th>종목</th><th>등락률</th><th>배수(장 지난 비율 대비)</th></tr>${top.map((p) =>
    `<tr><td class="st-name"><b>${esc(p.name || '—')}</b> <small>${esc(p.code || '')}</small>${nhTag(p)}</td><td>${pctTxt(p.pct)}</td><td><b>${p.mult == null ? '—' : `${num(p.mult, 2)}배`}</b></td></tr>`).join('')}</table></div>
    <div class="aw-why-s">${mmdd(d.day)} 확정 판(15:41)</div>`;
}
async function loadAw() {
  let j = null, st = 0;
  try { const r = await fetch(AW, { cache: 'no-store' }); st = r.status; j = r.ok ? await r.json() : null; } catch (e) { j = null; }
  const d = j && j.data, m = (j && j.meta) || {};
  if (!d) { awBox.innerHTML = `<div class="st-err">— 서버 값을 못 받음(${st || '연결 안 됨'})</div>`; awCap.textContent = '서버가 위 룰 값으로 고른 종목'; awHow.textContent = ''; return; }
  const rule = d.rule || {}, picked = Array.isArray(d.picked) ? d.picked : [];
  awPicked = d.day ? picked : []; awDay = d.day || '';
  if (ahD) renderAh();
  if (why.code && !awPicked.some((p) => p.code === why.code)) { why.code = ''; whyBox.innerHTML = '<div class="st-err">— 종목을 누르면 여기 나옵니다</div>'; }   // 다시 고른 목록에 없으면 비움
  const by = rule.sortBy === 'pct' ? '등락률 순' : '배수 순';
  const unset = d.day && d.ready === false;   // 기준 칸(등락률 · 배수)이 비면 서버가 거르지 않는다 — 「없음」 이 아니라 「안 거름」(개념정의 검수 11-05)
  awCap.textContent = unset ? `${mmdd(d.day)} 기준 · 아직 안 거름`
    : d.day
    ? `${mmdd(d.day)} 기준 · 걸린 ${num(d.hitAll)}종목${rule.autoMax != null ? ` 중 ${num(picked.length)}개 보임` : ''} · 셈한 ${num(d.measured)}(그날 값 없음 ${num(d.noToday)} · 앞 20거래일 모자람 ${num(d.short)}) · ${by}${m.runAt ? ` · 셈 ${esc(String(m.runAt).slice(11, 16) || m.runAt)}` : ''}`
    : '서버가 위 룰 값으로 고른 종목';
  if (!d.day) awBox.innerHTML = `${liveHtml(m, d)}<div class="st-err">— 아직 셈이 없음${m.runWindow ? `(${esc(m.runWindow)} 에 셈)` : ''}</div>`;
  else if (unset) awBox.innerHTML = '<div class="st-err">— 기준(등락률 · 배수) 칸이 비어 아직 안 거름 — 왼쪽 칸을 채우고 검색을 누르십시오</div>';
  else if (!picked.length) awBox.innerHTML = `${liveHtml(m, d)}<div class="st-err">— 이 룰에 걸린 종목 없음</div>`;
  else awBox.innerHTML = `${liveHtml(m, d)}<div class="st-scroll"><table class="aw-tb"><tr><th>종목</th><th>시장</th><th>종가</th><th>등락률</th><th>거래량</th><th>20일 평균</th><th>배수</th></tr>${picked.map((p) =>
    `<tr data-code="${esc(p.code || '')}"${p.code && p.code === why.code ? ' class="is-on"' : ''}><td class="st-name"><b>${esc(p.name || '—')}</b> <small>${esc(p.code || '')}</small>${nhTag(p)}</td><td>${esc(IDX[p.idx] || p.idx || '—')}</td><td>${num(p.close)}</td><td>${pctTxt(p.pct)}</td><td>${num(p.vol)}</td><td>${num(p.avg20)}</td><td><b>${p.mult == null ? '—' : `${num(p.mult, 2)}배`}</b></td></tr>`).join('')}</table></div>`;
  // 이 룰은 이렇게 셈합니다 — 재권님 11-05 「이거를 투자전략에다가 넣어줘」(개발 그림 dev-autowatch) · 수 · 시각 · 빠진 칸은 응답 그대로(화면에 박지 않는다)
  const u = m.universe || {};
  const KNAME = { sectorPct: '재료(미국장 섹터) 칸', exclude: '빼는 것 칸' };   // 서버가 칸 열쇠로 적어 보낸다 — 화면에는 칸 이름으로
  const have = new Set(ins.map((el) => el.dataset.k));   // 화면에 없는 칸(11-05 뺀 「빼는 것」 등)은 「아직 없음」 에 안 적는다
  const not = (m.notCounted || []).filter((x) => { const k = (String(x).match(/^(\w+)/) || [])[1]; return !k || !(k in KNAME) || have.has(k); }).map((x) => String(x).replace(/^(\w+)/, (k) => KNAME[k] || k));
  const li = (h, t) => `<li><b>${h}</b> ${esc(t)}</li>`;
  awHow.innerHTML = `<div class="aw-how-h">이 룰은 이렇게 셈합니다</div><ul>${[
    li('대상', `코스피 · 코스닥 시가총액 상위 ${num(u.rows)}종목 중 주권(ETF 뺌) — 지금 ${num(d.pool ?? u.stocks)}종목`),
    li('언제', `${m.runWindow || '—'} · 그날 종가 · 등락률 · 거래량을 쌓음 · 거래량 기준은 앞 20거래일 평균`),
    ...(m.liveWindow ? [li('장중', `${m.liveWindow} — 그때 시세로 거래량을 「20일 평균 × 장 지난 비율」 과 견줌 · 장중 값은 쌓지 않고 그날 확정은 위 셈`)] : []),
    li('기준', '위 룰 칸 값 — 칸을 고치면 시세를 다시 받지 않고 쌓인 값으로 바로 다시 거르고 줄 세움'),
    ...(m.add ? [li('관심종목에 넣기', m.add)] : []),   // 켜짐 · 꺼짐은 서버 글 그대로 — 「아직 없음」 머리에 두면 켜진 뒤 틀림(qa 11-06)
    ...not.map((x) => li('아직 없음', x)),
  ].join('')}</ul>${d.note && d.day ? `<div>${esc(d.note)}</div>` : ''}`;
}

// 오른 까닭 (11-05 재권님 「오늘종목 옆에 칸 추가해서 거기에 종목 클릭하면 상승이유 넣어줘」) — 누른 종목 하나만 서버 두 주소를 부른다(종목 뉴스 · 공시) ·
// 그날과 앞 WHY_BACK 날(달력)에 나온 것만 날짜로 모은다 — 까닭인지 가리는 셈은 두지 않는다 · 받는 곳 목록 밖 언론사는 표시만(서버 listed 값 그대로)
const whyBox = document.getElementById('aw-why');
const WHY_BACK = 3;   // 그날 앞 며칠까지 볼지 — 화면이 고르는 보기 범위(서버를 다시 묻는 주기가 아니다)
let awPicked = [], awDay = '';
const why = { code: '', seq: 0 };
const ymd = (x) => String(x || '').replace(/\D/g, '').slice(0, 8);
const fromDay = (day) => { const m = ymd(day).match(/(\d{4})(\d{2})(\d{2})/); if (!m) return ''; const t = new Date(+m[1], +m[2] - 1, +m[3] - WHY_BACK); return `${t.getFullYear()}${String(t.getMonth() + 1).padStart(2, '0')}${String(t.getDate()).padStart(2, '0')}`; };
const hmTxt = (at) => { const t = String(at || ''); return t.length >= 12 ? `${t.slice(4, 6)}-${t.slice(6, 8)} ${t.slice(8, 10)}:${t.slice(10, 12)}` : mmdd(t); };
async function getJson(u) { try { const r = await fetch(u, { cache: 'no-store' }); return { st: r.status, j: r.ok ? await r.json() : null }; } catch (e) { return { st: 0, j: null }; } }
async function showWhy(code) {
  const p = awPicked.find((x) => x.code === code); if (!p) return;
  why.code = code; const seq = ++why.seq;
  awBox.querySelectorAll('tr[data-code]').forEach((tr) => tr.classList.toggle('is-on', tr.dataset.code === code));
  const head = `<div class="aw-why-h">${esc(p.name || code)} <small>${esc(code)} · ${mmdd(awDay)} ${pctTxt(p.pct)} · 거래량 ${p.mult == null ? '—' : `${num(p.mult, 2)}배`}</small></div>`;
  whyBox.innerHTML = `${head}<div class="st-err">— 받는 중…</div>`;
  const [ds, nw] = await Promise.all([getJson(`/api/dart/disclosures?code=${encodeURIComponent(code)}&limit=40`), getJson(`/api/naver/news?code=${encodeURIComponent(code)}`)]);
  if (seq !== why.seq) return;   // 그사이 다른 종목을 눌렀다
  const lo = fromDay(awDay), hi = ymd(awDay);
  const inWin = (d) => { const x = ymd(d); return x && x >= lo && x <= hi; };
  const sec = (title, res, rows, item) => `<div class="aw-why-s">${title}</div>${!res.j ? `<div class="st-err">— 서버 값을 못 받음(${res.st || '연결 안 됨'})</div>` : rows.length ? `<ul>${rows.map(item).join('')}</ul>` : '<div class="st-err">— 이 기간에 없음</div>'}`;
  const dis = ((ds.j && ds.j.data) || []).filter((x) => inWin(x.date));
  const nws = ((nw.j && nw.j.data) || []).filter((x) => inWin(x.at)).sort((a, b) => (b.listed === true) - (a.listed === true) || String(b.at).localeCompare(String(a.at)));
  const link = (u, t) => (u ? `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(t)}</a>` : esc(t));
  whyBox.innerHTML = head
    + `<div class="st-cap">${mmdd(lo)} ~ ${mmdd(hi)} 에 나온 것</div>`
    + sec('공시', ds, dis, (x) => `<li>${link(x.url, x.title || '—')}<small>${mmdd(x.date)}${x.filer && x.filer !== p.name ? ` · ${esc(x.filer)}` : ''}</small></li>`)
    + sec('뉴스', nw, nws, (x) => `<li>${link(x.url, x.title || '—')}<small>${hmTxt(x.at)} · ${esc(x.office || '—')}</small>${x.listed === false ? '<span class="aw-out">목록 밖</span>' : ''}</li>`);
}
awBox.addEventListener('click', (e) => { const tr = e.target.closest('tr[data-code]'); if (tr) showWhy(tr.dataset.code); });

const pend = new Set();   // 아직 끝나지 않은 저장 — 검색은 이것이 다 끝난 뒤 부른다
ins.forEach((el) => el.addEventListener('change', () => { const p = save(el); pend.add(p); p.finally(() => pend.delete(p)); }));
const go = document.getElementById('rl-go');
go.addEventListener('click', async () => {
  go.disabled = true; go.textContent = '찾는 중…';
  const a = document.activeElement; if (a && ins.includes(a)) a.blur();   // 칸에 커서가 있으면 그 값부터 저장(change)
  await Promise.allSettled([...pend]);
  await loadAw();
  go.disabled = false; go.textContent = '검색';
  meta.textContent = `${lastWarn ? `${lastWarn} · ` : ''}검색함 ${hm()} — 위 룰 값으로 서버가 다시 고름`;
});
// 지난 성적 (11-05 재권님 「…투자전략에다가 데이터 넣어줘야해」 · 작업우선순위 배분) — 서버 /api/auto-watch/history 그대로 그린다 ·
// 오름 · 내림 · 비율 · 평균은 서버 셈(summary · total) · 결과가 아직이면 null → 「아직」(0 이 아니다) · 날 수는 화면이 고르는 보기 범위
const AH = '/api/auto-watch/history', AH_DAYS = 30;
const ahBox = document.getElementById('ah'), ahCap = document.getElementById('ah-cap');
const nOr = (x, t) => (x == null ? t : num(x));
const pctOr = (x) => (x == null ? '아직' : pctTxt(x));
// 어제 판 단추 (11-05 재권님 「하루전 2일전 3일전 4일전 이 있어야 되고 5일 10일 한달 이버튼도 따로 있어야해」) —
// 날 단추는 서버가 남긴 날 목록에서 「현재」 날을 뺀 순서(n번째 앞 남긴 날 · 단추에 날짜는 안 붙임 — 11-05 「어제옆에 날짜는 필요없어」 · 그 날짜는 표 머리 줄이 보인다) ·
// 기간 단추(가장 많이 걸린 종목 상위 20 · 기간 상승률)는 서버 data.top 그대로 — 화면은 세지 않는다
const AH_SPAN = [['5d', '5일', 'd5'], ['10d', '10일', 'd10'], ['1m', '한달', 'd20']];
let ahD = null, ahSt = 0, ahSel = 'b0';
const tabs = [...document.querySelectorAll('.aw-tab')], panes = [...document.querySelectorAll('.aw-pane')];
async function loadAh() {
  const { st, j } = await getJson(`${AH}?days=${AH_DAYS}`);
  ahSt = st; ahD = (j && j.data) || null;
  renderAh();
}
function renderAh() {
  const d = ahD;
  if (!d) { ahBox.innerHTML = `<div class="st-err">— 서버 값을 못 받음(${ahSt || '연결 안 됨'})</div>`; return; }
  const t = d.total || {};
  const list = (Array.isArray(d.list) ? d.list : []).filter((g) => !awDay || ymd(g.day) !== ymd(awDay)).sort((x, y) => ymd(y.day).localeCompare(ymd(x.day)));
  ahCap.textContent = `걸렸던 종목이 다음 거래일 종가에 어떻게 됐나 — 지난 ${AH_DAYS}일 쌓인 것 · 룰이 맞는지 보는 칸`;
  const sum = `<div class="ah-sum"><span>지난 ${AH_DAYS}일 · 오늘 포함 합계</span><span>걸림 <b>${nOr(t.picks, '—')}</b></span><span>결과 남 <b>${nOr(t.done, '—')}</b> · 아직 ${nOr(t.pending, '—')}${t.missing ? ` · 값 없음 ${num(t.missing)}` : ''}</span>`
    + `<span>오름 <b>${nOr(t.up, '—')}</b> · 내림 <b>${nOr(t.down, '—')}</b> · 보합 ${nOr(t.flat, '—')}</span>`
    + `<span>오른 비율 <b>${t.upRate == null ? '아직' : `${num(t.upRate, 1)}%`}</b></span><span>다음날 평균 <b>${t.avgNext == null ? '아직' : pctTxt(t.avgNext)}</b></span></div>`;
  let body;
  if (ahSel[0] === 'b') {
    const g = list[Number(ahSel.slice(1))];
    if (!g) body = `<div class="st-err">— 그날 남긴 것 없음${list.length ? ` — 남긴 날 ${num(list.length)}일뿐` : (d.note ? ` — ${esc(d.note)}` : '')}</div>`;
    else {
      const s2 = g.summary || {};
      const head = `<tr class="ah-day"><td colspan="5"><b>${mmdd(g.day)} 걸림</b> → ${g.nextDay ? `${mmdd(g.nextDay)} 종가` : '다음 거래일 아직'} · ${num((g.picks || []).length)}종목`
        + `${s2.missing ? ` · 값 없음 ${num(s2.missing)}` : ''}${s2.done ? ` · 오름 ${nOr(s2.up, '—')} · 내림 ${nOr(s2.down, '—')}${s2.avgNext == null ? '' : ` · 평균 ${pctTxt(s2.avgNext)}`}` : ''}</td></tr>`;
      const row = (p) => `<tr><td class="st-name"><b>${esc(p.name || '—')}</b> <small>${esc(p.code || '')}</small></td><td>${esc(IDX[p.idx] || p.idx || '—')}</td><td>${pctTxt(p.pct)}</td><td>${p.mult == null ? '—' : `${num(p.mult, 2)}배`}</td><td><b>${p.missing ? '값 없음' : pctOr(p.next && p.next.pct)}</b></td></tr>`;   // missing — 다음 거래일은 왔는데 그 종목 값이 없음(거래정지 · 못 받음 · 개발 5e499c2) · 「아직」 과 가른다
      body = `<div class="st-scroll"><table class="ah-tb"><tr><th>종목</th><th>시장</th><th>그날</th><th>배수</th><th>다음날</th></tr>${head}${(g.picks || []).map(row).join('')}</table></div>`;
    }
  } else {
    // 기간 상위 20 — 서버 data.top(d5 · d10 · d20 — 한달 = 20거래일 · 개발 891bc95) 그대로 · 상승 % 는 그 기간 처음 걸린 날 종가 → 마지막 종가(재권님 「가」)
    const span = AH_SPAN.find(([k]) => k === ahSel), tp = (d.top || {})[span[2]];
    if (!tp) body = `<div class="st-err">— ${esc(span[1])} 상위 — 서버 값 없음(아직 안 올라옴)</div>`;
    else if (!(tp.items || []).length) body = `<div class="st-err">— ${esc(span[1])} 동안 걸린 종목 없음</div>`;
    else {
      const row = (x, i) => `<tr><td class="st-name"><b>${i + 1}. ${esc(x.name || '—')}</b> <small>${esc(x.code || '')}</small></td><td><b>${nOr(x.count, '—')}번</b></td><td>${mmdd(x.firstDay)} ~ ${mmdd(x.lastDay)}</td><td>${num(x.firstClose)} → ${num(x.close)}</td><td><b>${x.gainPct == null ? '—' : pctTxt(x.gainPct)}</b></td></tr>`;
      body = `<div class="st-scroll"><table class="ah-tb"><tr><th>종목</th><th>걸린 횟수</th><th>처음 ~ 마지막 걸림</th><th>처음 걸린 날 종가 → 지금</th><th>상승</th></tr><tr class="ah-day"><td colspan="5"><b>${esc(span[1])}</b> · ${mmdd(tp.from)} ~ ${mmdd(tp.to)} · 걸린 날 ${nOr(tp.days, '—')}일 · 걸린 횟수 많은 순 상위 ${num(tp.items.length)}</td></tr>${tp.items.map(row).join('')}</table></div>`;
    }
  }
  ahBox.innerHTML = sum + body;
}

// 현재 · 어제 판 바꾸기 — 같은 자리에서 갈아 끼운다(높이는 CSS 가 같게 잡는다)
tabs.forEach((b) => b.addEventListener('click', () => {
  tabs.forEach((x) => { const on = x === b; x.classList.toggle('is-on', on); x.setAttribute('aria-selected', on ? 'true' : 'false'); });
  panes.forEach((p) => { p.hidden = p.dataset.pane !== b.dataset.pane; });
  if (b.dataset.ah) { ahSel = b.dataset.ah; renderAh(); }   // 어제 · 2~4일전 · 5일 · 10일 · 한달 — 같은 어제 판에 그 단추 것을 그림
}));

load();
loadAw();
everyServerMs('auto_watch.LIVE_SEC', 300_000, loadAw);   // 서버 장중 바퀴 주기를 그대로 — 뒤 숫자는 서버가 그 값을 안 줄 때만(FALLBACK)
loadAh();
