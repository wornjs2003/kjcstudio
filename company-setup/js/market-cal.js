// 시황분석 탭 「다가오는 일정 — 이번 주」 + 확률 표의 「다음 발표」 날짜 (2026-10-26 재권님 「가에다가 나를 추가하면」 → 시안 → 「응 만들어줘」).
// 값은 열 때 홀딩스 서버에서 받는다(「두 구역이 같은 값을 쓰면」 · 「서버가 알려준다」) — 따로 받는 도구 · 파일을 두지 않는다.
//   · 미국 지표 — /api/macro/releases 의 dates · nextReleaseKst(한국 시각)
//   · FOMC · 미국 실적 — holdings/data/market-calendar.json(주식 레인 · 결과 알림 events.py 와 같은 파일 · 읽기만). 시각은 result.et(미국 동부)를 한국 시각으로 바꾼다
//   · 한국 실적 발표일은 아직 없다 — DART 「기업설명회(IR)개최」 공시는 날짜가 본문에만 있고 서버가 본문을 안 읽는다(서버에 더할 일 · 주식 레인)
// 확률 표의 「다음 발표」 는 주 1회 셈한 파일 값이라 지난 날짜로 남을 수 있어 서버 일정으로 바꿔 쓴다(행의 data-rel = 서버 열쇠). 못 받으면 파일 값 그대로
const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const WEEK = 7;   // 오늘부터 며칠을 보이나 — 칸 이름 「이번 주」
const KDAY = '일월화수목금토';
const js = u => fetch(u, { cache: 'no-store' }).then(r => (r.ok ? r.json() : null)).catch(() => null);

// 미국 동부 시각 → 한국 시각. 서머타임(3월 둘째 일요일 ~ 11월 첫 일요일)이면 +13, 아니면 +14 시간
function etToKst(day, hm) {
  const [y, m, d] = day.split('-').map(Number), [h, mi] = hm.split(':').map(Number);
  const nth = (mon, k) => { const f = new Date(Date.UTC(y, mon - 1, 1)).getUTCDay(); return 1 + ((7 - f) % 7) + 7 * (k - 1); };
  const t = Date.UTC(y, m - 1, d, h, mi), dst = t >= Date.UTC(y, 2, nth(3, 2), 2) && t < Date.UTC(y, 10, nth(11, 1), 2);
  return new Date(t + (dst ? 13 : 14) * 3600e3);   // UTC 칸에 한국 벽시계 값이 든 Date
}
const kst = () => new Date(Date.now() + 9 * 3600e3);
const ymd = x => x.toISOString().slice(0, 10);
const label = s => { const x = new Date(s + 'T00:00:00Z'); return `${s.slice(5)}(${KDAY[x.getUTCDay()]})`; };

(async () => {
  const [REL, CAL] = await Promise.all([js('/api/macro/releases'), js('../holdings/data/market-calendar.json')]);
  const rel = (REL && REL.releases) || [];

  // 확률 표 — 그 표가 그려진 뒤에 바꾼다(market.js 가 따로 그린다)
  const fix = (n = 0) => {
    const rows = document.querySelectorAll('#odds tr[data-rel]');
    if (!rows.length) return n < 40 && setTimeout(() => fix(n + 1), 250);
    rows.forEach(tr => { const r = rel.find(x => x.key === tr.dataset.rel); if (r && r.nextRelease) { tr.lastElementChild.textContent = r.nextRelease.slice(5); tr.lastElementChild.title = '서버 발표 일정'; } });
  };
  if (rel.length) fix();

  const box = document.getElementById('cal');
  if (!box) return;
  if (!REL && !CAL) { box.innerHTML = '<span class="err">일정을 받지 못했습니다 — 서버 /api/macro/releases · holdings/data/market-calendar.json</span>'; return; }
  const from = ymd(kst()), to = ymd(new Date(kst().getTime() + (WEEK - 1) * 864e5));
  const rows = [];
  rel.forEach(r => {
    const t = r.nextReleaseKst; if (!t) return;
    if (t.slice(0, 10) >= from && t.slice(0, 10) <= to) rows.push({ d: t.slice(0, 10), t: t.slice(11, 16), c: '미국', w: r.name, s: '서버 발표 일정' });
  });
  ((CAL && CAL.events) || []).forEach(e => {
    const et = e.result && e.result.et, day = e.endDate || e.date;
    const k = et ? etToKst(day, et) : null, d = k ? ymd(k) : e.date;
    if (d < from || d > to) return;
    rows.push({ d, t: k ? k.toISOString().slice(11, 16) + (e.kind === '실적' ? ' 전후' : '') : '—', c: e.country === 'KR' ? '한국' : e.country === 'US' ? '미국' : esc(e.country), w: e.title, s: '일정 파일' });
  });
  rows.sort((a, b) => (a.d + a.t).localeCompare(b.d + b.t));
  box.innerHTML = rows.length
    ? '<table><thead><tr><th>날</th><th>시각</th><th>나라</th><th>일정</th><th>어디서</th></tr></thead><tbody>'
      + rows.map(x => `<tr><td>${label(x.d)}</td><td>${x.t}</td><td>${x.c}</td><td style="text-align:left">${esc(String(x.w).replace(new RegExp('^' + x.c + '\\s*'), ''))}</td><td><small>${x.s}</small></td></tr>`).join('') + '</tbody></table>'
    : '<span class="err">이번 주(' + from.slice(5) + '~' + to.slice(5) + ')에 받은 일정이 없습니다</span>';
  document.getElementById('cap-cal').insertAdjacentHTML('beforeend', ` · ${from.slice(5)}~${to.slice(5)} · 한국 실적 발표일은 아직 없음(DART 공시 본문을 서버가 안 읽음)`);
})();
