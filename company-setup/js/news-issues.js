// 뉴스 분석 맨 위 — 「오늘의 주요 이슈 정리」 · 「지금 세계 주요 이슈」 (2026-11-13 재권님 「응 만들어. 만들고 모아놓은 기사를 읽고 정리해서 맨위에 넣는거까지 해줘」 ·
// 시안 temp/시황분석-ni · 룰 CLAUDE.md 「뉴스 분석은 모으는 자리다」 · 상세 README 뉴스 분석 절 「이슈 뽑기」).
//   /company-setup/data/news-brief.json   세션이 쌓인 기사를 읽고 이슈별로 쓴 정리 글 + 근거 기사(제목만 읽음)
//   /api/news/hot                         서버가 묶어 줄 세운 이슈(언론사 수 → 나라 수 · 합친 점수 없음) · rising = 막 뜨는 이슈
//   /api/news/stored                      1차 출처 새 소식 — 받는 곳 목록에서 갈래가 「(가)」 인 곳의 기사
//   /holdings/data/news-topics.json       받는 곳 목록(feeds · 갈래)
// 못 받은 값은 「못 받음」 · 나라를 못 세면 「못 잼」 — 0 으로 메우지 않는다.

const $ = id => document.getElementById(id);
const get = async u => { try { const r = await fetch(u, { cache: 'no-store' }); return r.ok ? await r.json() : null; } catch (e) { return null; } };
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const md = s => (s ? `${s.slice(5, 10)} ${s.slice(11, 16)}` : '—');
// 근거 기사들이 뜬 때 — 첫 보도 ~ 마지막 보도(재권님 「주요기사들이 뜬 시간도 필요해」 11-13)
const span = arts => { const t = (arts || []).map(a => a.at).filter(Boolean).sort(); return t.length ? `<span class="tm">첫 보도 ${md(t[0])} · 마지막 ${md(t[t.length - 1])}</span>` : ''; };
const nf = x => (x == null || !isFinite(x) ? '—' : Number(x).toLocaleString('ko-KR'));

(async () => {
  const [brief, hot, fl, st] = await Promise.all([
    get('/company-setup/data/news-brief.json'), get('/api/news/hot'), get('/holdings/data/news-topics.json'),
    get('/api/news/stored?hours=72&limit=3000'),
  ]);

  // ── 오늘의 주요 이슈 정리 (세션이 쓴 글) ──
  if (brief && Array.isArray(brief.issues)) {
    $('ni-brief-meta').textContent = `${md(brief.writtenAt)} 정리 · ${brief.range || ''} · 기사 제목만 읽음 · 정리 글은 세션이 씀`;
    $('ni-brief').innerHTML = brief.issues.map((x, i) => `<div class="ni-b"><div class="h"><span class="k">${i + 1}</span><b>${esc(x.name)}</b>${span(x.articles)}</div>`
      + `<p>${esc(x.text)}</p><details><summary>근거 기사 ${x.articles.length}</summary>`
      + x.articles.map(a => `<div class="a"><a href="${esc(a.link)}" target="_blank" rel="noopener">${esc(a.title)}</a><small>${esc(a.source)} · ${md(a.at)}</small></div>`).join('')
      + `</details></div>`).join('');
  } else { $('ni-brief').textContent = '못 받음'; }

  // ── 받는 곳 ──
  const feeds = fl && Array.isArray(fl.feeds) ? fl.feeds : null;
  if (feeds) {
    const by = {};
    feeds.forEach(f => { const g = f['갈래'] || '갈래 없음'; (by[g] = by[g] || new Set()).add(f.label || f.id); });
    $('ni-src').innerHTML = Object.entries(by).map(([g, s]) => `<span><b>${esc(g)}</b>${[...s].map(esc).join(' · ')}</span>`).join('');
  } else $('ni-src').textContent = '못 받음';

  // ── 주요 이슈 · 막 뜨는 이슈 ──
  const H = hot && hot.ok && hot.data;
  if (H && Array.isArray(H.issues)) {
    const nat = i => (i.nations == null ? '<span class="mute">못 잼</span>' : nf(i.nations));
    $('ni-issues').innerHTML = H.issues.length
      ? `<tr><th></th><th>이슈</th><th class="w">갈래</th><th class="r">기사</th><th class="r">언론사</th><th class="r w">나라</th><th class="w">첫 · 마지막 보도</th><th class="w">확인</th></tr>`
        + H.issues.slice(0, 12).map((i, k) => `<tr><td class="n">${k + 1}</td><td class="t">${esc(i.name)}<small class="nw">첫 보도 ${md(i.first)}</small></td><td class="w"><span class="nd-st part">${esc(i.kind || '갈래 없음')}</span></td>`
          + `<td class="r">${nf(i.articles)}</td><td class="r">${nf(i.presses)}</td><td class="r w">${nat(i)}</td><td class="mute w">${md(i.first)} ~ ${md(i.last)}</td>`
          + `<td class="w"><span class="nd-st ${i.confirm === '1차 출처' ? 'ok' : 'part'}">${esc(i.confirm || '—')}</span></td></tr>`).join('')
      : '<tr><td class="mute">묶인 이슈 없음(기사 둘 이상 묶인 묶음이 없다)</td></tr>';
    const m = hot.meta || {};
    $('ni-issues-note').textContent = `서버 셈 · 창 ${m.windowH ?? '—'}시간 · 나라 수 ${m.nations || '—'}`;
    const rise = (H.rising || []).map(id => H.issues.find(i => i.id === id)).filter(Boolean);
    $('ni-rise').innerHTML = rise.length
      ? rise.map(i => `<div><b>${esc(i.name)}</b><span class="mute">${m.riseH ?? '—'}시간 ${nf(i.recent)}건 ← 앞 ${nf(i.before)}건 · 언론사 ${nf(i.presses)}</span></div>`).join('')
      : '<div class="mute">지금 막 뜨는 이슈 없음</div>';
  } else { $('ni-issues').innerHTML = '<tr><td>못 받음</td></tr>'; $('ni-rise').textContent = '못 받음'; }

  // ── 1차 출처 새 소식 ──
  const prim = feeds ? new Set(feeds.filter(f => String(f['갈래'] || '').startsWith('(가)')).map(f => f.label || f.id)) : null;
  const groups = st && st.ok && st.data;
  if (prim && groups) {
    const items = groups.flatMap(g => [g, ...(g.others || [])]).filter(x => prim.has(x.source)).sort((a, b) => (b.at || '').localeCompare(a.at || ''));
    $('ni-prim').innerHTML = prim.size === 0
      ? '<div class="mute">아직 안 받음 — 받는 곳 목록에 1차 출처가 아직 없다(연준 · 유럽중앙은행 · 일본은행을 서버에 더하는 중)</div>'
      : items.length ? items.slice(0, 10).map(x => `<div class="pr"><span class="nd-st ok">${esc(x.source)}</span><a href="${esc(x.link)}" target="_blank" rel="noopener">${esc(x.title)}</a><span class="mute">${md(x.at)}</span>`
          + (x.titleOrig ? `<details><summary>원문 보기</summary>${esc(x.titleOrig)}<div class="mute">번역은 세션이 함</div></details>` : '') + `</div>`).join('')
      : '<div class="mute">지난 72시간 받은 1차 출처 소식 없음</div>';
  } else $('ni-prim').textContent = '못 받음';
})();
