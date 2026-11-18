// 단타 판 「섹터수급」 — 같은 업종에 돈이 들어오나 · 프리장 08:00 ~ 정규장 09:30 (2026-11-18 · 시황분석1)
//   · 재권님 「섹터수급 이라고 단타창에 칸 추가해줘. 이건 동일업종에 돈이 들어오는거 체크하는거야. 프리장부터 정규장 9시 30분까지 재야해」 →
//     시안 temp/시황분석1-sf-1315 → 「응 만들어줘」(11-18)
//   · 셈은 서버 한 곳(/api/kis/sector-flow · 서버 레인 배분 중) — 화면은 받은 값을 그리기만(전날 대비 배 · 합은 받은 칸끼리)
//     응답(안): data { day, prev(전 거래일), slots[HHMM], rows[{ name(WICS), n(종목 수), amt{HHMM: 억원}, prev{HHMM: 억원}, pct{HHMM: 업종 평균 등락률 %} }] }
//              meta { asof, phase(pre · open · closed), refreshMs(다시 받을 간격 — 서버가 정함 · closed 면 안 받음) }
//   · 칸 색 = 그 칸 업종 값 방향(매수 우위 빨강 · 매도 우위 파랑) · 짙기 = 거래대금 전날 같은 시각 대비(tone.js · 지표 표 amt_prev_pct)
//   · 값이 없으면 — (0 이 아니다) · 서버가 아직 없으면 「서버 값 없음」 으로 냄
import { signClass, NUM } from '/assets/js/sign.js';
import { ready as toneReady, paint as tonePaint } from '/assets/js/tone.js';

const API = '/api/kis/sector-flow';
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (x, d = 0) => (x == null || !Number.isFinite(Number(x)) ? '—' : Number(x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (x) => { if (x == null || !Number.isFinite(x)) return '—'; const c = signClass(x, NUM); const t = `${x > 0 ? '+' : ''}${num(x, 2)}%`; return c ? `<span class="${c}">${t}</span>` : t; };
const hm = (t) => (/^\d{4}$/.test(String(t)) ? `${String(t).slice(0, 2)}:${String(t).slice(2)}` : esc(t || '—'));
const won = (v) => (v == null ? '—' : v >= 10000 ? `${num(v / 10000, 1)}조` : `${num(v)}억`);
const MAIN_HM = '0900';   // 정규장 첫 칸 — 칸 사이 구분선 자리만(셈 아님)

let box = null, timer = null, seq = 0;
// 칸 바탕 — 색 = 그 칸 동안 업종 값이 오른 쪽(매수 우위 · 빨강) · 내린 쪽(매도 우위 · 파랑) · 짙기 = 거래대금 전날 같은 시각 대비 %(기준 100)
//   (11-18 재권님 「이미지로 색도 있던데 색도 넣어줘. 매수와 매도에 맞게」) · 셈은 tone.js 한 곳(쪽을 정해 칠하기) · 기준 · 폭은 지표 표 amt_prev_pct — 없으면 색 없이(콘솔에 알림)
const bg = (t, p, mv) => { if (t == null || !p || mv == null || mv === 0) return ''; const c = tonePaint('amt_prev_pct', t / p * 100, 'bg', mv > 0 ? 'up' : 'down'); return c ? `background:${c}` : ''; };
const ratioTxt = (x) => { if (x == null) return '—'; const c = signClass(x - 1, NUM); const t = `${num(x, 1)}배`; return c ? `<b class="${c}">${t}</b>` : `<b>${t}</b>`; };

function paint(j) {
  if (!box) return;
  const meta = box.querySelector('.sf-meta'), body = box.querySelector('.sf-body');
  const d = j && j.ok !== false ? j.data : null;
  if (!d || !Array.isArray(d.rows)) { meta.textContent = j && j._st ? `— 서버 값 없음(${j._st}) · 서버 셈을 붙이면 채워짐(/api/kis/sector-flow)` : '— 서버 값 없음'; body.innerHTML = '<div class="st-err">—</div>'; return; }
  const m = j.meta || {}, SL = Array.isArray(d.slots) ? d.slots : [];
  const sum = (o) => { const v = SL.map((k) => (o || {})[k]).filter((x) => x != null); return v.length ? v.reduce((a, b) => a + b, 0) : null; };
  const rows = d.rows.map((r) => { const t = sum(r.amt), p = sum(r.prev); return { ...r, t, p, x: t != null && p ? t / p : null }; })
    .sort((a, b) => (b.x ?? -1) - (a.x ?? -1));
  const last = [...SL].reverse().find((k) => rows.some((r) => r.pct && r.pct[k] != null));
  meta.textContent = `${hm(SL[0])} ~ 09:30 · 줄 = 업종(네이버 WICS) · 칸 = 그 ${SL.length > 1 ? `${(+SL[1].slice(2) - +SL[0].slice(2) + 60) % 60}분` : '칸'} 동안 거래대금(억) · 칸 색 = 그 칸 동안 업종 값이 오름(매수 우위 · 빨강) · 내림(매도 우위 · 파랑) · 글씨도 같은 쪽 색 · 짙을수록 전날 같은 시각보다 거래대금이 많음 · 줄 차례 = 전날 대비 배 큰 순 · 서버 ${esc(m.asof || '—')}`;
  const th = SL.map((k) => `<th class="${k === MAIN_HM ? 'sf-sep' : ''}">${hm(k)}</th>`).join('');
  const nPre = SL.filter((k) => k < MAIN_HM).length, nReg = SL.length - nPre;
  const tr = rows.map((r, i) => `<tr><td class="sf-i">${i + 1}</td><td class="sf-l">${esc(r.name)}${r.n != null ? ` <small>${num(r.n)}</small>` : ''}</td>${SL.map((k, i) => { const a = (r.amt || {})[k], q = r.pct || {}, b = i ? q[SL[i - 1]] : 0, mv = q[k] == null || b == null ? null : q[k] - b; return `<td class="${k === MAIN_HM ? 'sf-sep' : ''}" style="${bg(a, (r.prev || {})[k], mv)}">${a == null ? '—' : (() => { const c = mv == null ? '' : signClass(mv, NUM); return c ? `<span class="${c}">${num(a)}</span>` : num(a); })()}</td>`; }).join('')}<td class="sf-sep">${won(r.t)}</td><td>${ratioTxt(r.x)}</td><td>${pct(last && r.pct ? r.pct[last] : null)}</td></tr>`).join('');
  body.innerHTML = `<div class="st-scroll sf-tw"><table class="sf-tb"><thead>
      <tr class="sf-grp"><th></th><th></th>${nPre ? `<th colspan="${nPre}">프리장(넥스트레이드)</th>` : ''}${nReg ? `<th colspan="${nReg}" class="sf-sep">정규장</th>` : ''}<th colspan="3" class="sf-sep">합 · 09:30 까지</th></tr>
      <tr><th></th><th class="sf-l">업종</th>${th}<th class="sf-sep">거래대금</th><th>전날 대비</th><th>등락률</th></tr></thead>
      <tbody>${tr || `<tr><td class="sf-l st-err" colspan="${SL.length + 5}">— 아직 칸이 없음(08:00 전)</td></tr>`}</tbody></table></div>
    <div class="st-cap">거래대금 = 그 칸 동안 업종 종목들의 5분봉 종가 × 거래량 합 · 08:50~09:00 은 장이 없어 칸을 뺌 · 등락률 = 마지막 칸 시각에 업종 종목 평균(전날 정규장 종가 대비) · 전날 대비 = 같은 칸들의 합끼리</div>`;
}

export async function loadSector(day) {
  if (!box) return;
  const my = ++seq; clearTimeout(timer); timer = null;
  let j = null;
  try { const r = await fetch(`${API}${day ? `?day=${encodeURIComponent(day)}` : ''}`, { cache: 'no-store' }); j = r.ok ? await r.json() : { _st: r.status }; }
  catch (e) { j = { _st: '연결 안 됨' }; }
  if (my !== seq || !box) return;
  await toneReady; if (my !== seq || !box) return;
  paint(j);
  const m = (j && j.meta) || {}, ms = Number(m.refreshMs);
  if (m.phase && m.phase !== 'closed' && ms > 0) timer = setTimeout(() => loadSector(day), ms);   // 다시 받는 간격은 서버가 정함
}

export function mountSector(el) { clearTimeout(timer); timer = null; seq++; box = el; }
