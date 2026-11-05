// 투자 전략 「종목 고르는 룰」 — 빈칸 값을 재권님이 직접 넣는다 (2026-11-05 재권님 「그 숫자는 내가 넣을 수 있게 해줘」).
//   · 값은 서버 문서 한 곳 — /api/board/doc/strategy-rules (GET 읽기 · PUT {data} 쓰기 · 세션 서버는 개발 서버 8765 로 넘긴다).
//     자동 관심종목(보드 카드 「전일 거래량 급등 종목 기준 확인」)을 만들게 되면 서버도 이 문서를 읽는다 — 기준은 이 한 곳(「같은 값은 한 곳에만 둔다」)
//   · 모양: { rules: { volsurge: { prevPct, volMult, sectorPct, sortBy('mult' 배수 순 | 'pct' 등락률 순), autoMax(정수 · 몇 종목까지),
//                                   buyWhen, targetPct, stopPct, holdDays, perStockPct, maxStocks, exclude } } } — 빈칸은 null(0 이 아니다) · sortBy 가 null 이면 서버가 배수 순
//   · 「오늘 이 룰에 걸린 종목」 — 서버 /api/auto-watch 가 이 문서를 부를 때마다 다시 읽어 거르고 줄 세운다. 화면은 그 결과를 그리기만 하고(거르는 셈을 두지 않는다)
//     칸은 바꾸면 바로 저장되고, 「검색」 단추를 누르면 저장이 끝난 뒤 다시 부른다(11-05 재권님 「숫자 바꾸고 나서 오른쪽 위에 검색 버튼 누르면 검색되게 해줘」) · 「없음」(null) 은 0 이 아니라 「—」 · 받는 방법 줄도 응답의 meta 로 쓴다(서버 상수를 화면에 다시 적지 않는다)
//   · 칸을 떠나면(change) 바로 저장 · 숫자 칸에 숫자가 아닌 글 · data-min 밑 · data-int 칸의 소수는 넣지 않고 그 칸을 되돌린다 · 남이 그 사이 고쳤으면(409) 다시 읽고 알린다
import { signClass, NUM } from '/assets/js/sign.js';   // 오르내림 글씨 색 — 셈은 sign.js 한 곳
const DOC = '/api/board/doc/strategy-rules';
const AW = '/api/auto-watch';
const RULE = 'volsurge';
const meta = document.getElementById('rl-meta');
const ins = [...document.querySelectorAll('#rl-tb .rl-in')];
let doc = { rules: {} }, at = null;
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
    const back = (msg) => { el.value = el.dataset.v || ''; meta.textContent = `${msg} — 그 칸은 되돌렸습니다`; };
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
    if (r.status === 409) { await load(); meta.textContent = '그 사이 다른 곳에서 고쳐 다시 읽었습니다 — 한 번 더 넣어 주십시오'; return; }
    if (!r.ok) throw new Error(String(r.status));
    const j = await r.json().catch(() => null);
    at = (j && (j.updatedAt ?? (j.data && j.data.updatedAt))) ?? at;
    el.value = v == null ? '' : String(v); // 「1,000」 · 「1e3」 을 저장된 값(1000)으로 보인다
    el.dataset.v = el.value;
    const n = ins.filter((x) => x.value === '').length;
    meta.textContent = `저장됨 ${hm()}${n ? ` · 빈칸 ${n}개 남음` : ' · 다 들어감'}`;
  } catch (e) {
    meta.textContent = `저장 못 함(${e.message || '연결 안 됨'}) — 넣은 값은 이 화면에만 있습니다`;
  }
}

// ── 오늘 이 룰에 걸린 종목 ──
const awBox = document.getElementById('aw'), awCap = document.getElementById('aw-cap'), awHow = document.getElementById('aw-how');
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (x, d = 0) => (x == null || !Number.isFinite(Number(x)) ? '—' : Number(x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d }));
const pctTxt = (x) => { if (x == null || !Number.isFinite(Number(x))) return '—'; const c = signClass(Number(x), NUM); const t = `${x > 0 ? '+' : ''}${num(x, 2)}%`; return c ? `<span class="${c}">${t}</span>` : t; };
const IDX = { KOSPI: '코스피', KOSDAQ: '코스닥' };
const mmdd = (d) => { const m = String(d || '').match(/(\d{4})-?(\d{2})-?(\d{2})/); return m ? `${m[2]}-${m[3]}` : (d || '—'); };

async function loadAw() {
  let j = null, st = 0;
  try { const r = await fetch(AW, { cache: 'no-store' }); st = r.status; j = r.ok ? await r.json() : null; } catch (e) { j = null; }
  const d = j && j.data, m = (j && j.meta) || {};
  if (!d) { awBox.innerHTML = `<div class="st-err">— 서버 값을 못 받음(${st || '연결 안 됨'})</div>`; awCap.textContent = '서버가 위 룰 값으로 고른 종목'; awHow.textContent = ''; return; }
  const rule = d.rule || {}, picked = Array.isArray(d.picked) ? d.picked : [];
  const by = rule.sortBy === 'pct' ? '등락률 순' : '배수 순';
  awCap.textContent = d.day
    ? `${mmdd(d.day)} 기준 · 걸린 ${num(d.hitAll)}종목${rule.autoMax != null ? ` 중 ${num(picked.length)}개 보임` : ''} · 셈한 ${num(d.measured)}(그날 값 없음 ${num(d.noToday)} · 앞 20거래일 모자람 ${num(d.short)}) · ${by}${m.runAt ? ` · 셈 ${esc(String(m.runAt).slice(11, 16) || m.runAt)}` : ''}`
    : '서버가 위 룰 값으로 고른 종목';
  if (!d.day) awBox.innerHTML = `<div class="st-err">— 아직 셈이 없음${m.runWindow ? `(${esc(m.runWindow)} 에 셈)` : ''}</div>`;
  else if (!picked.length) awBox.innerHTML = '<div class="st-err">— 이 룰에 걸린 종목 없음</div>';
  else awBox.innerHTML = `<div class="st-scroll"><table class="aw-tb"><tr><th>종목</th><th>시장</th><th>종가</th><th>등락률</th><th>거래량</th><th>20일 평균</th><th>배수</th></tr>${picked.map((p) =>
    `<tr><td class="st-name"><b>${esc(p.name || '—')}</b> <small>${esc(p.code || '')}</small></td><td>${esc(IDX[p.idx] || p.idx || '—')}</td><td>${num(p.close)}</td><td>${pctTxt(p.pct)}</td><td>${num(p.vol)}</td><td>${num(p.avg20)}</td><td><b>${p.mult == null ? '—' : `${num(p.mult, 2)}배`}</b></td></tr>`).join('')}</table></div>`;
  // 이 룰은 이렇게 셈합니다 — 재권님 11-05 「이거를 투자전략에다가 넣어줘」(개발 그림 dev-autowatch) · 수 · 시각 · 빠진 칸은 응답 그대로(화면에 박지 않는다)
  const u = m.universe || {};
  const KNAME = { sectorPct: '재료(미국장 섹터) 칸', exclude: '빼는 것 칸' };   // 서버가 칸 열쇠로 적어 보낸다 — 화면에는 칸 이름으로
  const not = (m.notCounted || []).map((x) => String(x).replace(/^(\w+)/, (k) => KNAME[k] || k));
  if (m.add) not.unshift(`관심종목에 넣기 — ${m.add}`);
  const li = (h, t) => `<li><b>${h}</b> ${esc(t)}</li>`;
  awHow.innerHTML = `<div class="aw-how-h">이 룰은 이렇게 셈합니다</div><ul>${[
    li('대상', `코스피 · 코스닥 시가총액 상위 ${num(u.rows)}종목 중 주권(ETF 뺌) — 지금 ${num(d.pool ?? u.stocks)}종목`),
    li('언제', `${m.runWindow || '—'} · 그날 종가 · 등락률 · 거래량을 쌓음 · 거래량 기준은 앞 20거래일 평균`),
    li('기준', '위 룰 칸 값 — 칸을 고치면 시세를 다시 받지 않고 쌓인 값으로 바로 다시 거르고 줄 세움'),
    ...not.map((x) => li('아직 없음', x)),
  ].join('')}</ul>${d.note && d.day ? `<div>${esc(d.note)}</div>` : ''}`;
}

const pend = new Set();   // 아직 끝나지 않은 저장 — 검색은 이것이 다 끝난 뒤 부른다
ins.forEach((el) => el.addEventListener('change', () => { const p = save(el); pend.add(p); p.finally(() => pend.delete(p)); }));
const go = document.getElementById('rl-go');
go.addEventListener('click', async () => {
  go.disabled = true; go.textContent = '찾는 중…';
  const a = document.activeElement; if (a && ins.includes(a)) a.blur();   // 칸에 커서가 있으면 그 값부터 저장(change)
  await Promise.allSettled([...pend]);
  await loadAw();
  go.disabled = false; go.textContent = '검색';
  meta.textContent = `검색함 ${hm()} — 위 룰 값으로 서버가 다시 고름`;
});
load();
loadAw();
