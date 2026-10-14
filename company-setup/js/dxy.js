// 달러인덱스 — ICE(.DXY · 1973년 3월 = 100)를 이 서버 /api/market/indicator 에서 받는 한 곳 (2026-10-14 재권님 「그렇게 해」 · 창구 경유).
// 시황분석 탭(market.js) · 흐름도 미국 말풍선(flowmap.html) · 홈 매크로 줄(home-macro.js)이 함께 쓴다 — 1개월 셈을 세 곳에 두지 않는다.
// world-macro.json 의 FRED 교역가중(2006년 1월 = 100)은 기준이 달라 화면에는 안 쓴다(받기는 그대로). 못 받으면 null — 화면은 「—」
import { indicatorSeries } from './indicator.js';
export async function dxyIce() {
  const r = await indicatorSeries('dxy'); if (!r) return null;
  const s = r.s, last = s[s.length - 1], back = s.length > 21 ? s[s.length - 22] : null;   // 한 달 = 22봉 앞
  return { v: last[1], date: last[0], m1: back ? +((last[1] / back[1] - 1) * 100).toFixed(1) : null, src: 'ICE 달러인덱스 · 네이버', s };
}
