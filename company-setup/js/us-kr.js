// 미국→국내 날마다 표 (2026-11-10 · 머리 주석은 us-kr.html) — 값은 서버만 부른다. 기간 · 받아 두는 주기는 서버 meta 가 정한다(화면에 숫자를 안 둔다).
// 짝짓기: 국내 거래일 D 의 「전날 밤 미국장」 = 미국 거래일 중 D 보다 앞인 마지막 날(미국 date 는 현지 날짜라 한국 D 아침 전에 끝난 장이다)
import { signClass } from '/assets/js/sign.js';

const US = [['NASDAQ', '나스닥'], ['SPX', 'S&P500'], ['SOX', '필라델피아 반도체']];
const KR = [['005930', '삼성전자'], ['000660', 'SK하이닉스']];
const $ = (id) => document.getElementById(id);
const fmt = (v, dp = 0) => v == null ? '—' : Number(v).toLocaleString('ko-KR', { minimumFractionDigits: dp, maximumFractionDigits: dp });
const pct = (a, b) => (a == null || !b) ? null : (a / b - 1) * 100;
const pctTxt = (p) => p == null ? '—' : (p > 0 ? '+' : '') + p.toFixed(2) + '%';
const ppTxt = (p) => p == null ? '—' : (p > 0 ? '+' : '') + p.toFixed(2);
const ppWord = (p, by) => p > 0 ? by + '보다 강함' : p < 0 ? by + '보다 약함' : by + '과 같음';   // 칸 숫자는 %p 를 떼고 뜻을 글로(11-10 재권님 「필반보다 더 오른 정도로 해주고 더 인지 쉽도록」)
const day = (s) => `${s.slice(2, 4)}.${s.slice(4, 6)}.${s.slice(6, 8)}`;

async function json(u) {
  const r = await fetch(u);
  if (!r.ok) throw new Error(u + ' ' + r.status);
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || u);
  return j;
}

function prevMap(bars) {           // date → 전 거래일 종가
  const m = {};
  (bars || []).forEach((b, i) => { m[b.date] = i ? bars[i - 1].close : null; });
  return m;
}

// 「○○보다 더 오른 정도」 칸 — 숫자(등락률 차이) · 아래 한 줄 뜻 · 옅은 바탕 · 하나라도 없으면 못 받음
function relCell(rel, by) {
  if (rel == null) return '<td class="na">못 받음</td>';
  return `<td class="rel rel-${signClass(rel)}"><b class="${signClass(rel)}">${ppTxt(rel)}</b><i>${ppWord(rel, by)}</i></td>`;
}

// 장중 줄의 종가 칸 — 종가가 아니라 「마감 전」 · 아래에 지금 값을 흐리게
function liveCell(v, prev, dp = 0) {
  if (v == null) return '<td class="na">마감 전</td>';
  const p = pct(v, prev);
  return `<td class="na">마감 전<i>지금 ${fmt(v, dp)} ${pctTxt(p)}</i></td>`;
}

function cell(v, prev, dp = 0) {
  if (v == null) return '<td class="na">못 받음</td>';
  const p = pct(v, prev);
  return `<td>${fmt(v, dp)}<i class="${signClass(p)}">${pctTxt(p)}</i></td>`;
}

async function main() {
  let idx;
  try { idx = await json('/api/kis/index-daily?codes=KOSPI,' + US.map((u) => u[0]).join(',')); }
  catch (e) { $('uk-sub').textContent = '지수 값을 못 받음 — ' + e.message; console.warn('[미국→국내]', e); return; }
  const kospi = idx.data.KOSPI && idx.data.KOSPI.bars;
  if (!kospi) { $('uk-sub').textContent = '코스피 일봉을 못 받음'; return; }
  const first = kospi[0].date;
  // 오늘 줄이 장중인지 — 장 시각은 서버(/api/alerts/market-hours)가 준다(화면에 15:30 을 박지 않는다) · 못 받으면 오늘 줄을 장중으로 본다(종가로 둔갑하지 않게)
  let live = null, mh = null;
  try {
    mh = (await json('/api/alerts/market-hours')).data.today;
    const d = new Date(), hm = String(d.getHours()).padStart(2, '0') + String(d.getMinutes()).padStart(2, '0');
    live = (mh && (!mh.open ? null : hm < mh.reg[1] ? mh.day : null));
  } catch (e) {
    const d = new Date(); live = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
    console.warn('[미국→국내] 장 시각 못 받음 — 오늘 줄을 장중으로 둠', e);
  }
  // 종목은 정규장(KRX · 09:00~15:30) 일봉 — /api/kis/stock-daily(주식페이지_개발 f23078d). /api/kis/chart 일봉은 통합(종가 20:00 · 시가 프리장 첫 값)이라 쓰지 않는다
  // (11-10 재권님 「오늘 하이닉스는 11.49%오른적이 없는데」 → 「정규장 종가」)
  const stocks = {};
  try {
    const j = await json('/api/kis/stock-daily?codes=' + KR.map((k) => k[0]).join(','));
    for (const [c] of KR) stocks[c] = (j.data[c] && j.data[c].bars) || null;
  } catch (e) { console.warn('[미국→국내] 정규장 일봉 못 받음', e); }
  const usBars = Object.fromEntries(US.map(([k]) => [k, (idx.data[k] && idx.data[k].bars) || null]));
  const usPrev = Object.fromEntries(US.map(([k]) => [k, prevMap(usBars[k])]));
  const kPrev = prevMap(kospi);
  const sMap = Object.fromEntries(KR.map(([c]) => [c, Object.fromEntries((stocks[c] || []).map((b) => [b.date, b]))]));
  const sPrev = Object.fromEntries(KR.map(([c]) => [c, prevMap(stocks[c])]));

  const head1 = `<tr><th rowspan="2">날짜</th><th colspan="3" class="g">전날 밤 미국 등락률</th><th colspan="4" class="g">코스피</th>`
    + KR.map(([, n]) => `<th colspan="5" class="g">${n}</th>`).join('') + '</tr>';
  const head2 = '<tr>' + US.map(([, n], i) => `<th${i ? '' : ' class="g"'}>${n}</th>`).join('')
    + '<th class="g">시가</th><th>최고가</th><th>종가</th><th data-tip="그날 종가 등락률 − 전날 밤 S&P500 등락률">S&P보다<br>더 오른 정도</th>'
    + KR.map(() => '<th class="g">프리장 시작가</th><th>시가</th><th>최고가</th><th>종가</th><th data-tip="그날 종가 등락률 − 전날 밤 필라델피아 반도체 등락률">필반보다<br>더 오른 정도</th>').join('') + '</tr>';

  const rows = kospi.slice().reverse().map((k) => {
    const isLive = k.date === live;   // 오늘 장이 안 끝났다 — 종가 · 「더 오른 정도」 는 「마감 전」 으로(11-10 재권님 「오늘 종가는 아직 안나왔는데 넣은 이유는 뭐지?」)
    let tr = `<tr${isLive ? ' class="live"' : ''}><td class="d">${day(k.date)}${isLive ? '<i>장중 — 마감 전</i>' : ''}</td>`;
    const usP = {};
    US.forEach(([u], i) => {
      const bars = usBars[u];
      const b = bars ? [...bars].reverse().find((x) => x.date < k.date) : null;
      const p = b ? pct(b.close, usPrev[u][b.date]) : null;
      usP[u] = p;
      const g = i ? '' : ' g';
      tr += p == null ? `<td class="na${g}">못 받음</td>` : `<td class="us${g} ${signClass(p)}" data-tip="미국 ${day(b.date)} 장">${pctTxt(p)}</td>`;
    });
    tr += cell(k.open, kPrev[k.date], 2).replace('<td', '<td class="g"') + cell(k.high, kPrev[k.date], 2) + (isLive ? liveCell(k.close, kPrev[k.date], 2) : cell(k.close, kPrev[k.date], 2));
    // 코스피는 시장 전체끼리 — 전날 밤 S&P500 과 견준다(11-10 재권님 「가 로해줘」)
    tr += isLive ? '<td class="na">마감 전</td>' : relCell(usP.SPX != null ? pct(k.close, kPrev[k.date]) - usP.SPX : null, 'S&P');
    KR.forEach(([c]) => {
      const b = sMap[c][k.date], pv = sPrev[c][k.date];
      tr += '<td class="na g">못 받음</td>';          // 프리장(넥스트레이드 08:00) 시작가 — 서버 값이 오면 채운다(개발1 배분 · 11-10)
      tr += b ? cell(b.open, pv) + cell(b.high, pv) + (isLive ? liveCell(b.close, pv) : cell(b.close, pv)) : '<td class="na">못 받음</td>'.repeat(3);
      // 필라델피아 반도체 대비 — 그날 정규장 종가 등락률 − 전날 밤 필반 등락률(2026-11-10 재권님 「필라델파아 반도체지수대비 등락」) · 둘 중 하나라도 없으면 못 받음
      tr += isLive ? '<td class="na">마감 전</td>' : relCell((b && usP.SOX != null) ? pct(b.close, pv) - usP.SOX : null, '필반');
    });
    return tr + '</tr>';
  });
  $('uk-t').innerHTML = head1 + head2 + rows.join('');
  const now = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });
  $('uk-sub').textContent = `${day(first)} ~ ${day(kospi[kospi.length - 1].date)} · 국내 거래일 ${kospi.length}일 · 기간은 서버 값(${idx.meta.months}개월) · ${now} 에 받음`;
  $('uk-foot').innerHTML = '출처 — 지수: 서버 /api/kis/index-daily(KIS) · 종목: 서버 /api/kis/stock-daily(KIS 정규장 일봉 · 09:00~15:30 · 등락률은 전날 정규장 종가 대비) · 미국 날짜는 현지 날짜 · '
    + '프리장 시작가는 서버에 아직 없어 「못 받음」(받는 길은 개발1 이 재는 중 — 「아직」 이지 「영영」 이 아님) · 오늘 줄은 장이 끝나기 전이면 종가를 「마감 전」 으로 두고 지금 값만 흐리게 · 그 줄의 시가 · 최고가도 장중 값'
    + ' · 열어 둔 채여도 장이 끝나면 한 번 다시 받아 오늘 줄을 종가로 바꿈';
  // 장중에 열어 둔 화면 — 장 마감(서버가 준 reg 끝) 뒤 서버가 일봉을 다시 받을 때까지(서버 meta.cacheTtl) 기다렸다가 한 번만 다시 받는다
  // (11-10 재권님 「날마다 갱신되도록 해줘」 → 「응 해줘」) · 몇 초마다 묻는 주기가 아니다 — 시각도 기다림도 서버 값(「캐시·주기·한도 값을 화면에 박지 않는다」)
  if (live && mh && mh.reg && idx.meta && idx.meta.cacheTtl != null) {
    const c = mh.reg[1], at = new Date();
    at.setHours(+c.slice(0, 2), +c.slice(2, 4), 0, 0);
    const wait = Math.max(0, at - Date.now()) + idx.meta.cacheTtl * 1000;
    clearTimeout(main.again);
    main.again = setTimeout(main, wait);
  }
}
main();
