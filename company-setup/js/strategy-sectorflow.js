// 단타 판 「섹터수급」 — 같은 업종에 돈이 들어오나 · 프리장 08:00 ~ 서버 칸 끝까지(11-18 09:30 → 같은 날 재권님 「2시까지 보여지게 해줘」 14:00 · 끝 시각은 서버 slots 로 셈) (2026-11-18 · 시황분석1)
//   · 재권님 「섹터수급 이라고 단타창에 칸 추가해줘. 이건 동일업종에 돈이 들어오는거 체크하는거야. 프리장부터 정규장 9시 30분까지 재야해」 →
//     시안 temp/시황분석1-sf-1315 → 「응 만들어줘」(11-18)
//   · 셈은 서버 한 곳(/api/kis/sector-flow · 서버 레인 배분 중) — 화면은 받은 값을 그리기만(전날 대비 배 · 합은 받은 칸끼리)
//     응답(안): data { day, prev(전 거래일), slots[HHMM], rows[{ name(WICS), n(종목 수), amt{HHMM: 억원}, prev{HHMM: 억원}, pct{HHMM: 업종 평균 등락률 %} }] }
//              meta { asof, phase(pre · open · closed), refreshMs(다시 받을 간격 — 서버가 정함 · closed 면 안 받음) }
//   · 칸 색 = 그 칸 업종 값 방향(매수 우위 빨강 · 매도 우위 파랑) · 짙기 = 거래대금 전날 같은 시각 대비(tone.js · 지표 표 amt_prev_pct)
//   · 값이 없으면 — (0 이 아니다) · 서버가 아직 없으면 「서버 값 없음」 으로 냄
import { signClass, side, NUM } from '/assets/js/sign.js';
import { ready as toneReady, paint as tonePaint } from '/assets/js/tone.js';

const API = '/api/kis/sector-flow';   // ?by=sector|theme · ?day=
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (x, d = 0) => (x == null || !Number.isFinite(Number(x)) ? '—' : Number(x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (x) => { if (x == null || !Number.isFinite(x)) return '—'; const c = signClass(x, NUM); const t = `${x > 0 ? '+' : ''}${num(x, 2)}%`; return c ? `<span class="${c}">${t}</span>` : t; };
const hm = (t) => (/^\d{4}$/.test(String(t)) ? `${String(t).slice(0, 2)}:${String(t).slice(2)}` : esc(t || '—'));
const won = (v) => (v == null ? '—' : v >= 10000 ? `${num(v / 10000, 1)}조` : `${num(v)}억`);
const MAIN_HM = '0900';   // 정규장 첫 칸 — 칸 사이 구분선 자리만(셈 아님)
// 보는 칸 묶기 (11-19 재권님 「10시 30분부터 30분 칸으로」) — 서버 칸(slots · 11-19 개발1 8d0274a 부터 5분)을 10:30 부터 30분씩 한 칸으로 합쳐 보여 줌(셈 아님 · 거래대금은 합 · 등락률은 그 칸 마지막 값)
const WIDE_HM = '1030', WIDE_MIN = 30;
const toM = (k) => +k.slice(0, 2) * 60 + +k.slice(2);
const toHM = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}${String(m % 60).padStart(2, '0')}`;
const group = (SL) => SL.reduce((a, k) => { const key = k < WIDE_HM ? k : toHM(toM(WIDE_HM) + Math.floor((toM(k) - toM(WIDE_HM)) / WIDE_MIN) * WIDE_MIN); const c = a[a.length - 1]; if (c && c.k === key) c.ks.push(k); else a.push({ k: key, ks: [k] }); return a; }, []);
const sumOf = (o, ks) => { const v = ks.map((k) => (o || {})[k]).filter((x) => x != null); return v.length ? v.reduce((a, b) => a + b, 0) : null; };
const lastOf = (o, ks) => { for (let i = ks.length - 1; i >= 0; i--) { const v = (o || {})[ks[i]]; if (v != null) return v; } return null; };

let box = null, timer = null, seq = 0, by = 'sector', lastDay = null;
const BY = [['sector', '업종'], ['theme', '테마']];   // 재권님 「그럼 테마도 만들어줘」 · 「다로 해줘」(11-18) — 업종(네이버 WICS) · 테마(네이버 작은 테마) 탭
// 칸 바탕 — 색 = 그 칸 동안 업종 값이 오른 쪽(매수 우위 · 빨강) · 내린 쪽(매도 우위 · 파랑) · 짙기 = 거래대금 전날 같은 시각 대비 %(기준 100)
//   (11-18 재권님 「이미지로 색도 있던데 색도 넣어줘. 매수와 매도에 맞게」) · 셈은 tone.js 한 곳(쪽을 정해 칠하기) · 기준 · 폭은 지표 표 amt_prev_pct — 없으면 색 없이(콘솔에 알림)
// 칸 색 (11-18 재권님 「많을때 글씨만 적용 색은 글씨가 보이게 적당히 조절하면 돼」 → 「응 커밋해 배경색은 옅게 파랑 빨강 으로 해주고」 · 작업우선순위 경유)
//   바탕 = 그 칸 매수 · 매도 쪽 옅은 색 고정(theme 변수) · 글씨 = 거래대금 전날 같은 시각 대비 짙기(tone.js 'text' · 지표 표 amt_prev_pct) — 빈 글이면 검정
// 값 출처 (11-18 개발1 되채움) — snap = 서버 칸(slots)마다 찍은 사진(11-19 부터 5분) · 5m = 5분봉으로 되채움(두 셈은 조금 다를 수 있음 · meta.srcNote)
const srcTxt = (o, who) => (o && o.src === '5m' ? ` · ${who} 값은 5분봉으로 되채움(봉 있는 종목 ${num(o.codes)})` : '');
const ud = (mv) => { const k = side(mv); return k === 'up' || k === 'down' ? k : null; };   // 쪽은 sign.js 한 셈 — 0 · 없음은 쪽 없음(색 없음)
const bg = (mv) => { const k = ud(mv); return k ? `background:var(--kh-${k}-dim)` : ''; };
const fg = (t, p, mv) => { const k = ud(mv); if (t == null || !p || !k) return ''; const c = tonePaint('amt_prev_pct', t / p * 100, 'text', k); return c ? `color:${c}` : ''; };
// 매수 · 매도 합 (11-19 재권님 「현시간까지 매수 매도 총합도 필요해」 → 「나」 — 서버 rows[].buy · sell{칸: 억} · 개발1 · 정규장 칸만 · 프리장 · 5분봉 되채운 판은 null → 「—」) — 큰 쪽만 그 쪽 색
const bsTxt = (v, o, k) => { if (v == null) return '—'; const c = o == null ? '' : signClass(k === 'up' ? v - o : o - v, NUM); return c && side(k === 'up' ? v - o : o - v) === k ? `<span class="${c}">${won(v)}</span>` : won(v); };   // 쪽 셈은 sign.js — 매수가 크면 매수 칸 빨강 · 매도가 크면 매도 칸 파랑
const ratioTxt = (x) => { if (x == null) return '—'; const c = signClass(x - 1, NUM); const t = `${num(x, 1)}배`; return c ? `<b class="${c}">${t}</b>` : `<b>${t}</b>`; };

function paint(j) {
  if (!box) return;
  const body = box.querySelector('.sf-body'), meta = { textContent: '' };   // 설명 줄은 높이를 잡은 칸(.sf-body) 안에 그림 — 탭 · 값 없음마다 길이가 달라도 아래가 안 밀림(qa 11-18 좁은 폭)
  const d = j && j.ok !== false ? j.data : null;
  if (!d || !Array.isArray(d.rows)) { meta.textContent = j && j._st ? `— 서버 값 없음(${j._st}) · 서버 셈을 붙이면 채워짐(/api/kis/sector-flow)` : '— 서버 값 없음'; body.innerHTML = `<div class="st-cap sf-meta">${esc(meta.textContent)}</div><div class="st-err">—</div>`; return; }
  const m = j.meta || {}, SL = Array.isArray(d.slots) ? d.slots : [];
  const sum = (o) => { const v = SL.map((k) => (o || {})[k]).filter((x) => x != null); return v.length ? v.reduce((a, b) => a + b, 0) : null; };
  // 이 날 · 전날 셈이 다르면(사진 ↔ 5분봉 되채움) 전날 대비 배 · 글씨 짙기를 안 낸다 — 5분봉 판은 봉 있는 종목만 세어 작게 나와 배가 부풂(개발1 · qa 11-18) · 줄 차례는 거래대금 순
  const same = !(m.src && m.prevSrc && m.src.src && m.prevSrc.src && m.src.src !== m.prevSrc.src);
  const rows = d.rows.map((r) => { const t = sum(r.amt), p = same ? sum(r.prev) : null; return { ...r, prev: same ? r.prev : {}, t, p, x: t != null && p ? t / p : null, b: sum(r.buy), s: sum(r.sell) }; })
    .sort((a, b) => (same ? (b.x ?? -1) - (a.x ?? -1) : (b.t ?? -1) - (a.t ?? -1)));
  const last = [...SL].reverse().find((k) => rows.some((r) => r.pct && r.pct[k] != null));
  // 끝 시각 = 마지막 칸 + 칸 간격(서버 slots 로 셈 · 화면에 박지 않음) — 머리 글 · 「합」 머리도 같은 값
  const step = SL.length > 1 ? ((+SL[1].slice(0, 2) * 60 + +SL[1].slice(2)) - (+SL[0].slice(0, 2) * 60 + +SL[0].slice(2))) : 0;
  const endM = SL.length ? (+SL[SL.length - 1].slice(0, 2) * 60 + +SL[SL.length - 1].slice(2) + step) : null;
  const END = endM == null ? '—' : `${String(Math.floor(endM / 60)).padStart(2, '0')}:${String(endM % 60).padStart(2, '0')}`;
  const C = group(SL);
  const ttl = box.querySelector('.sf-h b'); if (ttl) ttl.textContent = `섹터수급 — 같은 업종 · 테마에 돈이 들어오나 · 프리장 ${SL.length ? hm(SL[0]) : '—'} ~ 정규장 ${END}`;
  meta.textContent = `${hm(SL[0])} ~ ${END} · 줄 = ${by === 'theme' ? '테마(네이버 · 한 종목이 여러 테마면 각각 셈)' : '업종(네이버 WICS)'} · 칸 = 그 ${SL.length > 1 ? `${step}분` : '칸'}(${hm(WIDE_HM)} 부터 ${WIDE_MIN}분) 동안 거래대금(억) · 칸 색 = 그 칸 동안 그 줄 값이 오름(매수 우위 · 옅은 빨강) · 내림(매도 우위 · 옅은 파랑) · 글씨는 같은 쪽 색으로 전날 같은 시각보다 거래대금이 많을수록 짙음 · 줄 차례 = 전날 대비 배 큰 순 · 서버 ${m.asof || '—'}${srcTxt(m.src, '이 날')}${srcTxt(m.prevSrc, '전날')}${same ? '' : ' · 이 날과 전날 셈이 달라(사진 · 5분봉) 전날 대비 · 글씨 짙기를 안 냄 — 줄 차례는 거래대금 순'}${m.bsNote ? ` · 매수 · 매도 — ${m.bsNote}` : ''}`;
  const th = C.map((c) => `<th class="${c.k === MAIN_HM ? 'sf-sep' : ''}">${hm(c.k)}</th>`).join('');
  const nPre = C.filter((c) => c.k < MAIN_HM).length, nReg = C.length - nPre;
  const tr = rows.map((r, i) => `<tr><td class="sf-i">${i + 1}</td><td class="sf-l">${esc(r.name)}${r.n != null ? ` <small>${num(r.n)}</small>` : ''}</td>${C.map((cl, i) => { const a = sumOf(r.amt, cl.ks), q = r.pct || {}, e = lastOf(q, cl.ks), b = i ? lastOf(q, C[i - 1].ks) : 0, mv = e == null || b == null ? null : e - b; return `<td class="${cl.k === MAIN_HM ? 'sf-sep' : ''}" style="${bg(mv)}">${a == null ? '—' : (() => { const c = fg(a, sumOf(r.prev, cl.ks), mv); return c ? `<span style="${c}">${num(a)}</span>` : num(a); })()}</td>`; }).join('')}<td class="sf-sep">${won(r.t)}</td><td>${bsTxt(r.b, r.s, 'up')}</td><td>${bsTxt(r.s, r.b, 'down')}</td><td>${ratioTxt(r.x)}</td><td>${pct(last && r.pct ? r.pct[last] : null)}</td></tr>`).join('');
  body.innerHTML = `<div class="st-cap sf-meta">${esc(meta.textContent)}</div><div class="st-scroll sf-tw wheel-stop"><table class="sf-tb"><thead>
      <tr class="sf-grp"><th></th><th></th>${nPre ? `<th colspan="${nPre}">프리장(넥스트레이드)</th>` : ''}${nReg ? `<th colspan="${nReg}" class="sf-sep">정규장</th>` : ''}<th colspan="5" class="sf-sep">합 · ${END} 까지</th></tr>
      <tr><th></th><th class="sf-l">${by === 'theme' ? '테마' : '업종'}</th>${th}<th class="sf-sep">거래대금</th><th data-tip="정규장 칸 체결 매수 어림 합(억) — 서버 셈 · 넥스트 체결 · 거래대금 상위 밖 종목은 빠져 거래대금보다 작음">매수</th><th data-tip="정규장 칸 체결 매도 어림 합(억) — 서버 셈">매도</th><th>전날 대비</th><th>등락률</th></tr></thead>
      <tbody>${tr || `<tr><td class="sf-l st-err" colspan="${C.length + 7}">${m.phase === 'pre' ? `— 아직 칸이 없음(첫 칸은 ${SL[1] ? hm(SL[1]) : '—'} 사진 뒤)` : '— 이 날 찍힌 값 없음(서버가 그 시간에 값을 안 남김)'}</td></tr>`}</tbody></table></div>
    <div class="st-cap">거래대금 = 그 칸 동안 그 줄 종목들의 5분봉 종가 × 거래량 합 · 08:50~09:00 은 장이 없어 칸을 뺌 · 등락률 = 마지막 칸 시각에 그 줄 종목 평균(전날 정규장 종가 대비) · 전날 대비 = 같은 칸들의 합끼리</div>`;
}

export async function loadSector(day) {
  if (!box) return;
  lastDay = day;
  const my = ++seq; clearTimeout(timer); timer = null;
  let j = null;
  try { const r = await fetch(`${API}?by=${by}${day ? `&day=${encodeURIComponent(day)}` : ''}`, { cache: 'no-store' }); j = r.ok ? await r.json() : { _st: r.status }; }
  catch (e) { j = { _st: '연결 안 됨' }; }
  if (my !== seq || !box) return;
  await toneReady; if (my !== seq || !box) return;
  paint(j);
  const m = (j && j.meta) || {}, ms = Number(m.refreshMs);
  if (m.phase && m.phase !== 'closed' && ms > 0) timer = setTimeout(() => loadSector(day), ms);   // 다시 받는 간격은 서버가 정함
}

export function mountSector(el) {
  clearTimeout(timer); timer = null; seq++; box = el;
  if (!el) return;
  { const t = el.querySelector('.sf-h b'); if (t) t.textContent = '섹터수급 — 같은 업종 · 테마에 돈이 들어오나'; }   // 시각은 값을 받으면 서버 slots 로 붙임(틀 글의 시각을 안 믿음)
  const tabs = el.querySelector('.sf-by');
  if (tabs) {
    tabs.innerHTML = BY.map(([k, t]) => `<button type="button" class="kh-chip${k === by ? ' is-active' : ''}" data-by="${k}">${t}</button>`).join('');
    tabs.addEventListener('click', (e) => { const b = e.target.closest('[data-by]'); if (!b || b.dataset.by === by) return; by = b.dataset.by; tabs.querySelectorAll('[data-by]').forEach((x) => x.classList.toggle('is-active', x.dataset.by === by)); loadSector(lastDay); });
  }
}
