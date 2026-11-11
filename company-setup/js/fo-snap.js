// 시황분석 탭 「선물 · 풋」 칸 (2026-11-10 재권님 「선물이랑 풋을 … 시황분석에 넣어줘」 → 「실시간 거래에서 확인할수 있으면 돼」)
// 값은 서버 /api/kis/fo-snapshot(주식페이지_개발) 하나 — 다시 받는 때는 서버가 주는 meta.cacheTtl 을 따른다(화면에 주기 숫자를 두지 않는다).
// 종목 풋은 체결이 드물어(하루 한 자릿수~수십 계약) 흐름이 아니라 값 · 남은 계약(미결제)으로 읽는다. price 는 마지막 체결가라 그날 거래 0 이면 전날 값.
import { signClass } from '/assets/js/sign.js';

const CODES = ['005930', '000660'];   // 시황분석 탭이 보는 두 종목(미국→국내 표와 같은 둘)
const box = document.querySelector('#fo-snap [data-fo]');
const n0 = (v) => v == null ? '—' : Number(v).toLocaleString('ko-KR');
const pctOf = (price, chg) => price == null || chg == null || price === chg ? null : Math.round(chg / (price - chg) * 10000) / 100 || 0;
const sg = (v, t) => `<span class="${signClass(v)}">${t}</span>`;
const chgTxt = (price, chg) => { const p = pctOf(price, chg); return chg == null ? '—' : sg(p, `${chg > 0 ? '+' : ''}${n0(chg)} (${p > 0 ? '+' : ''}${p == null ? '—' : p.toFixed(2)}%)`); };
const ym = (s) => s ? `${s.slice(2, 4)}.${s.slice(4, 6)}물` : '';

function stock(code, s) {
  if (!s) return `<div class="fo-st"><b>${code}</b> 못 받음</div>`;
  if (s.error) return `<div class="fo-st"><b>${s.name || code}</b> <span class="fo-m">${s.error}</span></div>`;
  const f = s.futures || {};
  const near = (rows) => (rows || []).reduce((a, p) => a == null || Math.abs(p.strike - f.price) < Math.abs(a.strike - f.price) ? p : a, null);
  return `<div class="fo-st"><div class="fo-h"><b>${s.name}</b> <span class="fo-m">선물 ${ym(f.month)} · 옵션 ${ym(s.optionMonth || s.putMonth)} · ${s.at || ''} 값 · 굵은 줄 = 선물 값에 가장 가까운 행사가</span></div>
    <div class="fo-kv"><div><i>선물</i><b>${n0(f.price)}</b>${chgTxt(f.price, f.change)}</div><div><i>거래량</i><b>${n0(f.volume)}</b></div><div><i>미결제</i><b>${n0(f.openInterest)}</b></div></div>
    <div class="fo-opt">${optTable('콜', '오름에 거는 계약', s.calls, near(s.calls))}${optTable('풋', '내림에 거는 계약', s.puts, near(s.puts))}</div></div>`;
}

// 콜 · 풋을 따로 — 재권님 「풋옵션 콜옵션은 구분되어야해」(16:5x)
function optTable(kind, sub, rows, nr) {
  if (!rows || !rows.length) return `<div class="fo-op"><div class="fo-oh"><b>${kind}</b> <span class="fo-m">${sub} · 못 받음</span></div></div>`;
  return `<div class="fo-op"><div class="fo-oh"><b>${kind}</b> <span class="fo-m">${sub}</span></div><div class="fo-scroll"><table class="fo-tb"><tr><th>행사가</th><th>값</th><th>전날 대비</th><th>거래량</th><th>미결제</th></tr>
    ${rows.map((p) => `<tr${p === nr ? ' class="near"' : ''}><td>${n0(p.strike)}</td><td>${n0(p.price)}</td><td>${chgTxt(p.price, p.change)}</td><td>${n0(p.volume)}</td><td>${n0(p.openInterest)}</td></tr>`).join('')}</table></div></div>`;
}

// 코스피200 묶음 — 종목과 같은 꼴(선물 · 콜 표 · 풋 표) + 풋/콜 비율 · 재권님 「코스피200은 코스피로 나누고 여기도 적용해줘」(16:5x) → 코스피 종합에는 선물 · 옵션이 없어 「없으면 코스피200으로 하자」(17:1x · 개발 창)
// 서버가 kospi200.futures · calls · puts 를 아직 안 주면 그 칸은 「서버에 아직 없음」 — 합계 · 비율은 전처럼
function k200(k) {
  if (!k) return '<div class="fo-st">코스피200 못 받음</div>';
  const f = k.futures || null;
  const r = (v) => v == null ? '—' : v.toFixed(2);
  const near = (rows) => (rows || []).reduce((a, p) => a == null || Math.abs(p.strike - k.index) < Math.abs(a.strike - k.index) ? p : a, null);
  const rows = (x) => x && x.length ? x : null;
  const tbl = (kind, sub, x) => rows(x) ? optTable(kind, sub, x, near(x)) : `<div class="fo-op"><div class="fo-oh"><b>${kind}</b> <span class="fo-m">${sub} · 행사가 줄은 서버에 아직 없음(더하는 중)</span></div></div>`;
  return `<div class="fo-st"><div class="fo-h"><b>코스피200 지수</b> <span class="fo-m">선물 ${f ? ym(f.month) : '—'} · 옵션 ${ym(k.optionMonth || k.month)} · ${k.at || ''} 값 · 굵은 줄 = 지수에 가장 가까운 행사가</span></div>
    <div class="fo-kv"><div><i>지수</i><b>${n0(k.index)}</b></div><div><i>선물</i><b>${f ? n0(f.price) : '—'}</b>${f ? chgTxt(f.price, f.change) : '<span class="fo-m">서버에 아직 없음</span>'}</div><div><i>풋/콜 거래량 · 미결제</i><b>${r(k.putCallVolume)} · ${r(k.putCallOI)}</b><span class="fo-m">풋 ${n0(k.putVolume)} · 콜 ${n0(k.callVolume)}</span></div></div>
    <div class="fo-opt">${tbl('콜', '오름에 거는 계약', k.calls)}${tbl('풋', '내림에 거는 계약', k.puts)}</div>
    <div class="fo-m">풋/콜 비율은 시장 전체가 아니라 그 월물 행사가 ${n0(k.strikes && k.strikes[0])}~${n0(k.strikes && k.strikes[1])}(${k.strikeCount}칸) 합 · 1 보다 크면 풋(내림 대비)이 콜보다 많음${k.missing ? ` · 못 받은 칸 ${k.missing}` : ''}</div></div>`;
}

async function load() {
  let j = null;
  try { const r = await fetch('/api/kis/fo-snapshot?codes=' + CODES.join(','), { cache: 'no-cache' }); if (r.ok) j = await r.json(); }
  catch (e) { console.warn('[선물 · 풋] 못 받음', e); }
  if (!j || !j.ok) { box.textContent = '못 받음 — 서버에 선물 · 풋 주소가 아직 없거나 응답이 없음'; return; }
  const st = j.data.stocks || {};
  box.innerHTML = `<h3 class="fo-gh">종목</h3><div class="fo-grid">${CODES.map((c) => stock(c, st[c])).join('')}</div>
    <h3 class="fo-gh">코스피200</h3><div class="fo-grid one">${k200(j.data.kospi200)}</div>
    <div class="fo-m">출처 — 서버 /api/kis/fo-snapshot(KIS 주식선물 · 주식옵션 · 코스피200 옵션) · 값은 마지막 체결가(그날 거래가 없으면 전날 값)</div>`;
  const ttl = j.meta && j.meta.cacheTtl;
  if (ttl) setTimeout(load, ttl * 1000);   // 서버가 묵히는 동안은 같은 값 — 그 뒤 한 번 다시 받는다
}
load();
