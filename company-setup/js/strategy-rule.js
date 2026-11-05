// 투자 전략 「종목 고르는 룰」 — 빈칸 값을 재권님이 직접 넣는다 (2026-11-05 재권님 「그 숫자는 내가 넣을 수 있게 해줘」).
//   · 값은 서버 문서 한 곳 — /api/board/doc/strategy-rules (GET 읽기 · PUT {data} 쓰기 · 세션 서버는 개발 서버 8765 로 넘긴다).
//     자동 관심종목(보드 카드 「전일 거래량 급등 종목 기준 확인」)을 만들게 되면 서버도 이 문서를 읽는다 — 기준은 이 한 곳(「같은 값은 한 곳에만 둔다」)
//   · 모양: { rules: { volsurge: { prevPct, volMult, sectorPct, buyWhen, targetPct, stopPct, holdDays, perStockPct, maxStocks, exclude } } } — 빈칸은 null(0 이 아니다)
//   · 칸을 떠나면(change) 바로 저장 · 숫자 칸에 숫자가 아닌 글은 넣지 않고 그 칸을 되돌린다 · 남이 그 사이 고쳤으면(409) 다시 읽고 알린다
const DOC = '/api/board/doc/strategy-rules';
const RULE = 'volsurge';
const meta = document.getElementById('rl-meta');
const ins = [...document.querySelectorAll('#rl-tb .rl-in')];
let doc = { rules: {} }, at = null;
const hm = () => { const d = new Date(); return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };

function fill() {
  const r = (doc.rules || {})[RULE] || {};
  ins.forEach((el) => { const v = r[el.dataset.k]; el.value = v == null ? '' : String(v); el.dataset.v = el.value; el.placeholder = '( )'; });
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
  if (v != null && !el.classList.contains('rl-txt')) {
    const x = Number(raw.replace(/,/g, ''));
    if (!Number.isFinite(x)) { el.value = el.dataset.v || ''; meta.textContent = '숫자만 넣을 수 있습니다 — 그 칸은 되돌렸습니다'; return; }
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
    el.dataset.v = el.value;
    const n = ins.filter((x) => x.value === '').length;
    meta.textContent = `저장됨 ${hm()}${n ? ` · 빈칸 ${n}개 남음` : ' · 다 들어감'}`;
  } catch (e) {
    meta.textContent = `저장 못 함(${e.message || '연결 안 됨'}) — 넣은 값은 이 화면에만 있습니다`;
  }
}

ins.forEach((el) => el.addEventListener('change', () => save(el)));
load();
