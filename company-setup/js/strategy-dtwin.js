// 단타 판 「칩별 승률」 — 손익 칸 안 접기 (2026-11-18 · 시황분석1)
//   · 재권님 카드 「투자 전략 — 칩별 승률을 날마다 기록 · 이익 큰 것 추려 룰 점검」 — 셈은 서버 /api/kis/dt30-win?days= 한 곳(개발2 · 세후 · 09:01 매수 → 14:00 매도)
//   · 화면은 받은 값을 표로만 그림 — 묶음(칩 하나 · 둘 · 셋 · 칩 개수 · 오른 칩 개수) · 날마다(그날 이익 큰 종목)
//   · 접기를 열 때 한 번 받음 · 다시 묻는 주기 없음 · 값이 없으면 —
import { signClass, NUM } from '/assets/js/sign.js';
import { renameChips } from './strategy-chipname.js';   // 칩 이름을 실시간 순위와 같게(「수급」 → 「자동」 · 11-18)

const API = '/api/kis/dt30-win?days=30';
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (x, d = 0) => (x == null || !Number.isFinite(Number(x)) ? '—' : Number(x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (x) => { if (x == null || !Number.isFinite(x)) return '—'; const c = signClass(x, NUM); const t = `${x > 0 ? '+' : ''}${num(x, 2)}%`; return c ? `<span class="${c}">${t}</span>` : t; };
const WK = ['일', '월', '화', '수', '목', '금', '토'];
const dayTxt = (d) => { const m = String(d || '').match(/^(\d{4})(\d{2})(\d{2})$/); return m ? `${m[2]}-${m[3]}(${WK[new Date(+m[1], +m[2] - 1, +m[3]).getDay()]})` : '—'; };
const hm = (t) => (/^\d{4}$/.test(String(t)) ? `${String(t).slice(0, 2)}:${String(t).slice(2)}` : esc(t || '—'));

const TABS = [['chip', '칩 하나'], ['pair', '칩 둘'], ['triple', '칩 셋'], ['count', '칩 개수'], ['countRise', '현재상승 든 종목 · 칩 개수'], ['days', '날마다']];
const KEY = { chip: '칩', pair: '칩 둘', triple: '칩 셋', count: '칩 개수', countRise: '칩 개수(현재상승 든 종목만)' };
let data = null, meta = null, tab = 'chip', busy = false, local = null, step = '';   // local — 단타 판이 넘긴 화면 셈(11-24 · 있으면 서버 표 대신)

const head = (k) => `<tr><th class="dw-l">${k}</th><th>종목</th><th>이김</th><th>승률</th><th>평균</th><th>중앙값</th><th>+${num(meta && meta.bigPct, 0)}% 넘음</th><th>못 잼</th></tr>`;
const cells = (g) => `<td>${num(g.n)}</td><td>${num(g.win)}</td><td><b>${g.winRate == null ? '—' : `${num(g.winRate, 1)}%`}</b></td><td>${pct(g.avg)}</td><td>${pct(g.median)}</td><td>${num(g.over3)}</td><td class="dw-mut">${num(g.unmeasured)}</td>`;

function table() {
  if (!data) return '';
  const all = data.all ? `<tr class="dw-all"><td class="dw-l">전체</td>${cells(data.all)}</tr>` : '';
  if (tab === 'days') {
    const rows = (data.days || []).map((d) => `<tr><td class="dw-l">${dayTxt(d.day)}</td>${cells(d)}<td class="dw-l dw-top">${(d.top || []).map((t) => `${esc(t.name)} ${pct(t.ret)}`).join(' · ') || '—'}</td></tr>`).join('');
    return `<table class="dw-tb"><thead>${head('날').replace('</tr>', `<th class="dw-l">그날 이익 큰 종목 ${num(meta && meta.topDay)}</th></tr>`)}</thead><tbody>${all.replace('</tr>', '<td></td></tr>')}${rows}</tbody></table>`;
  }
  const rows = (data[tab] || []).map((g) => `<tr><td class="dw-l">${esc(tab.startsWith('count') ? `${g.key}개` : g.key)}</td>${cells(g)}</tr>`).join('');
  return `<table class="dw-tb"><thead>${head(KEY[tab])}</thead><tbody>${all}${rows || '<tr><td class="dw-l st-err" colspan="8">—</td></tr>'}</tbody></table>`;
}

function paint(box) {
  const body = box.querySelector('.dw-body');
  if (!data) { body.innerHTML = `<div class="st-err">— ${busy ? `받는 중${step}` : '칩별 승률을 못 받음'}</div>`; return; }
  const m = meta || {};
  if (m.local) {   // 화면 셈 — 지금 셈 칸 그대로(11-24)
    body.innerHTML = `<div class="st-cap">${dayTxt(m.from)} ~ ${dayTxt(m.to)} · ${num(m.days)}거래일${m.miss ? ` · 판 못 받은 날 ${num(m.miss)}` : ''} · <b>지금 셈 칸 · 켜진 칩 · 매수 · 매도 룰 그대로 화면이 셈</b>(저장 안 해도 고친 대로 · 접었다 펴면 다시 셈) · 세후 %(팔 때 거래세 · 농특세 · 수수료 ${m.fee == null ? '안 셈' : `${num(m.fee, 3)}%`}) · ${m.minChips ? `칩 ${num(m.minChips)}개 이상 · ` : ''}판에 드는 종목만 · 이김 = 세후 0 보다 큼 · 지난 날은 칩이 처음 붙은 때만 남아 빠졌다 다시 붙은 칩은 못 가름</div>
    ${Array.isArray(m.rules) && m.rules.length ? `<div class="st-cap"><b>셈한 룰</b>${m.rules.map(([g, xs]) => `<br>${esc(g)} — ${(xs || []).map(([k, t]) => `${esc(k)} <b>${esc(t)}</b>`).join(' · ')}`).join('')}</div>` : ''}
    <div class="dt-seg dw-tabs" role="tablist" aria-label="칩별 승률 묶음">${TABS.map(([k, t]) => `<button type="button" class="kh-chip${k === tab ? ' is-active' : ''}" data-dw="${k}">${t}</button>`).join('')}</div>
    <div class="st-scroll dw-tw wheel-stop">${table()}</div>`;
    return;
  }
  const fee = m.fee == null ? '수수료 안 셈' : `수수료 ${num(m.fee, 3)}%(${esc(m.feeSides || '')})`;
  body.innerHTML = `<div class="st-cap">${dayTxt(m.from)} ~ ${dayTxt(m.to)} · ${num(m.days)}거래일 · 세후 %(팔 때 거래세 + 농특세) · ${fee} · ${m.minChips ? `칩 ${num(m.minChips)}개 이상 든 종목만 · ` : ''}그날 판 매수가(11-18 판부터 09:00 시가 · 그 전 09:01) → ${hm(m.sell)} 값에 팜 · 이김 = 세후 0 보다 큼 · 못 잼 = 그 시각 값이 없음(승률 셈에서 뺌) · 서버가 ${esc(m.filledAt || '—')} 에 셈</div>
    <div class="dt-seg dw-tabs" role="tablist" aria-label="칩별 승률 묶음">${TABS.map(([k, t]) => `<button type="button" class="kh-chip${k === tab ? ' is-active' : ''}" data-dw="${k}">${t}</button>`).join('')}</div>
    <div class="st-scroll dw-tw wheel-stop">${table()}</div>`;
}

async function load(box) {
  busy = true; step = ''; paint(box);
  if (local) { try { const o = await local((k, n) => { step = ` · 날마다 판 ${k}/${n}`; paint(box); }); data = o.data; meta = o.meta; } catch (e) { data = null; } busy = false; paint(box); return; }
  try {
    const r = await fetch(API, { cache: 'no-store' });
    const j = r.ok ? await r.json() : null;
    data = j && j.ok ? renameChips(j.data) : null; meta = j ? j.meta : null;
  } catch (e) { data = null; }
  busy = false; paint(box);
}

// 단타 판이 그릴 때마다 새 칸에 붙임 — 처음 열 때만 받음
export function bindWin(box, calcLocal) {
  if (!box) return;
  local = calcLocal || null;
  box.addEventListener('toggle', () => { if (box.open && !busy && (local || !data)) load(box); else if (box.open) paint(box); });   // 화면 셈이면 펼 때마다 지금 셈 칸으로 다시 셈
  box.addEventListener('click', (e) => { const b = e.target.closest('[data-dw]'); if (!b || b.dataset.dw === tab) return; tab = b.dataset.dw; paint(box); });
}
