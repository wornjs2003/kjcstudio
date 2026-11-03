/* ==========================================================================
   나라별 장 여는 · 닫는 시각 — 홈 큰 차트(5분봉 · 1분봉)에 세로선으로 긋는다 (2026-11-03)

   재권님 — 「특정 시간대에 코스피 매수나 매도가 갑자기 변동이 되는데 장에 영향이 있는걸 알아야 할거같아」 →
   「이걸 차트에 보여지도록」 → 시안 두 판 중 「안 1로 해줘」(차트 안 세로선 · 보드 카드 「큰 차트에 나라별 장 여는 · 닫는 시각」).

   **시각은 그 나라 현지 시각으로 적는다** — 한국 시각으로 바꾸는 것은 브라우저의 시간대 표(Intl · IANA)가 한다.
   그래서 서머타임(유럽 · 미국 · 호주)이 바뀌어도 이 표는 그대로다. 한국 시각을 여기 적으면 해마다 두 번 틀린다.
   나라별 휴장일은 안 본다 — 그 나라가 쉬는 날에도 선이 그어진다(아직 안 했다 · 휴장 달력 원천을 정하면 더한다).

   who  — 이름표 앞(나라) · what — 이름표 뒤(무엇). 같은 한국 시각 · 같은 what 은 「중국 · 홍콩 개장」 으로 합친다
   until — 있으면 그 사이를 옅게 칠한다(동시호가)
   ========================================================================== */

export const SESSION_EVENTS = [
  { zone: 'Australia/Sydney', at: '10:00', who: '호주', what: '개장' },
  { zone: 'Asia/Seoul', at: '09:00', who: '한국', what: '개장' },
  { zone: 'Asia/Tokyo', at: '09:00', who: '일본', what: '개장' },
  { zone: 'Asia/Taipei', at: '09:00', who: '대만', what: '개장' },
  { zone: 'Asia/Shanghai', at: '09:30', who: '중국', what: '개장' },
  { zone: 'Asia/Hong_Kong', at: '09:30', who: '홍콩', what: '개장' },
  { zone: 'Asia/Tokyo', at: '12:30', who: '일본', what: '오후장' },
  { zone: 'Asia/Shanghai', at: '13:00', who: '중국', what: '오후장' },
  { zone: 'Asia/Hong_Kong', at: '13:00', who: '홍콩', what: '오후장' },
  { zone: 'Asia/Seoul', at: '15:20', until: '15:30', who: '한국', what: '동시호가' },
  { zone: 'Asia/Seoul', at: '15:30', who: '한국', what: '마감' },
  { zone: 'Asia/Seoul', at: '16:00', who: '한국', what: '시간외' },
  { zone: 'Europe/London', at: '08:00', who: '유럽', what: '개장' },
  { zone: 'America/New_York', at: '04:00', who: '미국', what: '프리장' },
  { zone: 'America/New_York', at: '09:30', who: '미국', what: '개장' },
];

const _fmt = new Map();
function partsIn(zone, ms) {
  let f = _fmt.get(zone);
  if (!f) {
    f = new Intl.DateTimeFormat('en-US', {
      timeZone: zone, hourCycle: 'h23',
      year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    });
    _fmt.set(zone, f);
  }
  const o = {};
  f.formatToParts(new Date(ms)).forEach((p) => { o[p.type] = p.value; });
  return o;
}

/* 그 시간대의 벽시계를 UTC 자리에 둔 값(ms) — 차이가 곧 그 순간의 시차다 */
function wallMs(zone, ms) {
  const p = partsIn(zone, ms);
  return Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute);
}

/* zone 의 그 날 hh:mm 이 한국 벽시계로 몇 시인가 — 차트 시각 자리(한국 벽시계를 UTC 로 둔 초)로 낸다 */
function toKstWall(y, m, d, hhmm, zone) {
  const [hh, mm] = hhmm.split(':').map(Number);
  const want = Date.UTC(y, m - 1, d, hh, mm);
  let utc = want - (wallMs(zone, want) - want);
  utc = want - (wallMs(zone, utc) - utc);        // 서머타임 바뀌는 날을 위해 한 번 더
  return Math.floor(wallMs('Asia/Seoul', utc) / 1000);
}

/**
 * 그 날짜들의 세로선 목록 — 한국 시각 순.
 * @param {string[]} days  'YYYYMMDD'
 * @returns {{t:number, until:number|null, label:string}[]}  t · until 은 차트 시각 자리(초)
 */
export function sessionMarks(days) {
  const out = [];
  days.forEach((s) => {
    const y = +s.slice(0, 4), m = +s.slice(4, 6), d = +s.slice(6, 8);
    const at = new Map();                         // 같은 한국 시각끼리 모은다
    SESSION_EVENTS.forEach((e) => {
      const t = toKstWall(y, m, d, e.at, e.zone);
      const until = e.until ? toKstWall(y, m, d, e.until, e.zone) : null;
      if (!at.has(t)) at.set(t, { t, until: null, byWhat: new Map() });
      const g = at.get(t);
      if (until) g.until = until;
      if (!g.byWhat.has(e.what)) g.byWhat.set(e.what, []);
      g.byWhat.get(e.what).push(e.who);
    });
    at.forEach((g) => {
      const label = [...g.byWhat].map(([what, who]) => who.join(' · ') + ' ' + what).join(' / ');
      out.push({ t: g.t, until: g.until, label });
    });
  });
  return out.sort((a, b) => a.t - b.t);
}
