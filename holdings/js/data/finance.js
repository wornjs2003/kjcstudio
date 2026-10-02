/* 재무 — 모달 「투자 지표」 칸 재무 카드가 쓰는 값 (2026-10-02 지시)
 *
 * 재권님 — 재무 카드 시안 v3 를 보시고 「방향이 맞아 개발해」.
 * 받는 곳은 서버 `/api/kis/finance` 하나다 (`kis_proxy.py` 의 `fetch_finance`).
 *
 * **여기서 하는 일은 셋뿐이다** — 그리는 일은 하지 않는다.
 *     받기         `fetchFinance(code)`                 서버가 분기 · 억원 · 99.99→null 을 이미 맞춰 준다
 *     PER 밴드      `perBand(rows, daily)`               일봉 종가 ÷ TTM EPS 의 최저 · 가운데 · 최고
 *     분기 말 종가  `quarterEndCloses(yms, daily, monthly)` 일봉이 없는 옛 분기는 월봉으로
 *
 * **값을 지어내지 않는다.** 빈 칸은 `null` 그대로 두고, 그리는 쪽이 「데이터 없음」 을 쓴다.
 * 수명(캐시)은 서버가 정한다 — 여기 박지 않는다(「캐시·주기·한도 값을 화면에 박지 않는다」).
 */

import { apiFetch } from './api.js';

/** 서버가 준 분기 재무. 못 받으면 `null` — 「없음」 을 빈 배열 `[]` 로 바꾸지 않는다. */
export async function fetchFinance(code) {
  try {
    const r = await apiFetch(`/api/kis/finance?code=${encodeURIComponent(code)}`, { cache: 'default' });
    if (!r || !r.ok) return null;
    const j = await r.json();
    if (!j || !j.ok || !Array.isArray(j.data)) return null;
    return { rows: j.data, meta: j.meta || {} };
  } catch {
    return null;
  }
}

const PREV_Q = { '06': '03', '09': '06', '12': '09' };

/** 연 누적 EPS → 분기 EPS. 1분기는 그대로, 아니면 같은 해 앞 분기를 뺀다. 못 구하면 `null`. */
export function quarterEps(rows) {
  const ytd = new Map(rows.map(r => [r.ym, r.epsYtd]));
  const out = new Map();
  for (const r of rows) {
    const v = r.epsYtd;
    if (v == null) { out.set(r.ym, null); continue; }
    const m = r.ym.slice(4);
    if (m === '03') { out.set(r.ym, v); continue; }
    const before = ytd.get(r.ym.slice(0, 4) + PREV_Q[m]);
    out.set(r.ym, before == null ? null : v - before);
  }
  return out;
}

/** 최근 4분기 EPS 합(TTM). 네 분기가 다 있어야 낸다. */
export function ttmEps(rows) {
  const q = quarterEps(rows);
  const yms = rows.map(r => r.ym).sort();
  const out = new Map();
  yms.forEach((ym, i) => {
    if (i < 3) return;
    const four = yms.slice(i - 3, i + 1).map(y => q.get(y));
    if (four.every(v => v != null)) out.set(ym, four.reduce((a, b) => a + b, 0));
  });
  return out;
}

/* 분기 말 날짜(YYYYMMDD) — 그날부터 그 분기 TTM 을 쓴다고 본다.
 * ⚠️ 실제 실적 발표는 분기 말보다 늦다. 밴드가 조금 앞당겨 보인다 — 범례에 적는다. */
const qEnd = ym => ym + ({ '03': '31', '06': '30', '09': '30', '12': '31' }[ym.slice(4)] || '31');

/** PER 밴드. 배수는 지어내지 않고 이 기간 PER(종가 ÷ TTM)의 최저 · 가운데 · 최고로 낸다.
 *  daily: [{ts:'YYYYMMDD', close}] · 반환: { multiples:[lo,mid,hi], points:[{ts, close, ttm}] } 또는 null */
export function perBand(rows, daily) {
  const ttm = ttmEps(rows);
  const ends = [...ttm.keys()].sort().map(ym => [qEnd(ym), ttm.get(ym)]);
  if (!ends.length || !Array.isArray(daily) || !daily.length) return null;
  const points = [];
  for (const c of daily) {
    let t = null;
    for (const [d, v] of ends) { if (d <= c.ts) t = v; else break; }
    if (t != null && t > 0 && c.close != null) points.push({ ts: c.ts, close: c.close, ttm: t });
  }
  if (!points.length) return null;
  const pers = points.map(p => p.close / p.ttm).sort((a, b) => a - b);
  const mid = pers[Math.floor(pers.length / 2)];
  const r2 = v => Math.round(v * 100) / 100;
  return { multiples: [r2(pers[0]), r2(mid), r2(pers[pers.length - 1])], points };
}

/** 분기마다 그 분기 마지막 거래일 종가. 일봉에 그 달이 있으면 일봉, 없으면 월봉. 둘 다 없으면 `null`. */
export function quarterEndCloses(yms, daily, monthly) {
  const lastIn = (list, ym) => {
    let hit = null;
    for (const c of list || []) if (String(c.ts).startsWith(ym)) hit = c;
    return hit;
  };
  return yms.map(ym => {
    const d = lastIn(daily, ym);
    if (d) return { ym, close: d.close, from: 'D' };
    const m = lastIn(monthly, ym);
    return m ? { ym, close: m.close, from: 'M' } : { ym, close: null, from: null };
  });
}
