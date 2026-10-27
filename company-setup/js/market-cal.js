// 시황분석 탭 「다가오는 일정 — 이번 주」 + 확률 표의 「다음 발표」 날짜 (2026-10-26 재권님 「가에다가 나를 추가하면」 → 시안 → 「응 만들어줘」).
// 값은 열 때 홀딩스 서버에서 받는다(「두 구역이 같은 값을 쓰면」 · 「서버가 알려준다」) — 따로 받는 도구 · 파일을 두지 않는다.
//   · 미국 지표 — /api/macro/releases 의 nextReleaseKst(한국 시각)
//   · FOMC · 미국 실적 — /api/macro/calendar 의 kst · kstDate(서버가 한국 시각으로 바꿔 줌 · 화면은 셈하지 않는다)
//   · 한국 실적 — /api/dart/ir 의 earnings=true(DART 「기업설명회(IR)개최」 공시) · 하루 한 줄로 묶는다 (2026-10-26 시안 → 「응 해줘」)
// 확률 표의 「다음 발표」 는 주 1회 셈한 파일 값이라 지난 날짜로 남을 수 있어 서버 일정으로 바꿔 쓴다(행의 data-rel = 서버 열쇠). 못 받으면 파일 값 그대로
const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const WEEK = 7;   // 오늘부터 며칠을 보이나 — 칸 이름 「이번 주」
const KDAY = '일월화수목금토';
const js = u => fetch(u, { cache: 'no-store' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
const kst = () => new Date(Date.now() + 9 * 3600e3);
const ymd = x => x.toISOString().slice(0, 10);
const label = s => { const x = new Date(s + 'T00:00:00Z'); return `${s.slice(5)}(${KDAY[x.getUTCDay()]})`; };
const NONE = '99';   // 시각 없는 줄은 그날 맨 뒤

(async () => {
  const [REL, CAL, IR] = await Promise.all([js('/api/macro/releases'), js('/api/macro/calendar'), js('/api/dart/ir')]);
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
  const miss = [!REL && '/api/macro/releases', !CAL && '/api/macro/calendar', !IR && '/api/dart/ir'].filter(Boolean);
  if (miss.length === 3) { box.innerHTML = '<span class="err">일정을 받지 못했습니다 — 서버 ' + miss.join(' · ') + '</span>'; return; }
  const from = ymd(kst()), to = ymd(new Date(kst().getTime() + (WEEK - 1) * 864e5));
  const inWeek = d => d && d >= from && d <= to;
  const rows = [];
  rel.forEach(r => { const t = r.nextReleaseKst; if (t && inWeek(t.slice(0, 10))) rows.push({ d: t.slice(0, 10), t: t.slice(11, 16), c: '미국', w: esc(r.name), s: '서버 발표 일정' }); });
  ((CAL && CAL.data) || []).forEach(e => {
    const d = e.kstDate || e.date; if (!inWeek(d)) return;
    const c = e.country === 'KR' ? '한국' : e.country === 'US' ? '미국' : esc(e.country);
    rows.push({ d, t: e.kst ? e.kst.slice(11, 16) + (e.kind === '실적' ? ' 전후' : '') : '—', c, w: esc(String(e.title).replace(new RegExp('^' + c + '\\s*'), '')), s: '서버 일정' });
  });
  const kr = {};
  ((IR && IR.data) || []).filter(e => e.earnings && inWeek(e.date)).forEach(e => { const a = (kr[e.date] = kr[e.date] || []); if (!a.some(x => x.code === e.code)) a.push(e); });
  Object.entries(kr).forEach(([d, a]) => {
    a.sort((x, y) => String(x.time || NONE).localeCompare(String(y.time || NONE)));
    rows.push({ d, t: '—', c: '한국', w: `실적 발표 ${a.length}곳 — ` + a.map(e => esc(e.name) + (e.time ? `(${esc(e.time)})` : '')).join(' · '), s: 'DART 기업설명회 공시' });
  });
  const key = x => x.d + (x.t === '—' ? NONE : x.t);
  rows.sort((a, b) => key(a).localeCompare(key(b)));   // 같은 날은 날짜를 그날 첫 줄에만 쓴다(2026-10-26 재권님 「같은 날이면 맨위에 하나만 써줘 헷갈려」)
  box.innerHTML = rows.length
    ? '<table><thead><tr><th>날</th><th>시각</th><th>나라</th><th>일정</th><th>어디서</th></tr></thead><tbody>'
      + rows.map((x, i) => `<tr${i && rows[i - 1].d === x.d ? '' : ' class="cal-day"'}><td>${i && rows[i - 1].d === x.d ? '' : label(x.d)}</td><td>${x.t}</td><td>${x.c}</td><td style="text-align:left;white-space:normal">${x.w}</td><td><small>${x.s}</small></td></tr>`).join('') + '</tbody></table>'
    : '<span class="err">이번 주(' + from.slice(5) + '~' + to.slice(5) + ')에 받은 일정이 없습니다</span>';
  document.getElementById('cap-cal').insertAdjacentHTML('beforeend', ` · ${from.slice(5)}~${to.slice(5)}` + (miss.length ? ` · 못 받음: ${miss.join(' · ')}` : ''));
})();
