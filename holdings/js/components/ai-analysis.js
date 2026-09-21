/* ==========================================================================
   AI 분석 (2026-09-21 지시)

   **화면은 AI 를 부르지 않는다.** 저장소에 그럴 열쇠도 코드도 없다.
   세션이 글을 써서 `data/ai-analysis.json` 에 두고, 여기서는 읽어 그린다.
   데일리분석의 문안과 같은 방식이다.

   ── 무엇이 들어 있나 ──

       summary     값 요약 — 52주 어디쯤인가 · PER·PBR · 오늘 업종
       flow        수급 — 며칠간 누가 샀나 · 지금 호가가 어느 쪽인가
       news        뉴스·공시를 묶어 본 것
       consensus   **아직 없다.** 받아올 곳을 못 찾았다 — null 이면 빨간 표시를 낸다

   ── 관심종목 8개만 있다 ──

   글을 쓰는 데 종목마다 API 일곱 번이 든다. 순위표 200종목을 다 쓰면
   하루에도 몇 백 번이다. 그 밖의 종목을 고르면 「아직 없습니다」를 적는다.

   ── 글은 낡는다 ──

   값이 움직여도 글은 그대로다. 그래서 **언제 쓴 것인지**를 배지에 적는다.
   파일에는 `_잰값`(글을 쓸 때 실제로 본 숫자)도 들어 있는데, 화면은 쓰지
   않는다 — 나중에 「이 글이 얼마나 낡았나」를 기계로 재는 자리다.
   ========================================================================== */

import { apiFetch } from '../data/api.js';

/* 파일은 세션이 하루 한 번 고친다. 화면이 자주 볼 이유가 없다 */
const RELOAD_MS = 30 * 60 * 1000;

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/* 2026-09-21T12:00:00+09:00 → 09.21 12:00 */
function whenText(at) {
  const t = String(at || '');
  if (t.length < 16) return '';
  return `${t.slice(5, 7)}.${t.slice(8, 10)} ${t.slice(11, 16)}`;
}

const PARTS = [
  { key: 'summary', label: '값' },
  { key: 'flow', label: '수급' },
  { key: 'news', label: '뉴스' },
];

export function mountAiAnalysis(root) {
  if (!root) return { setCode() {}, destroy() {} };

  const box = root.querySelector('#kh-ai-box');
  const when = root.querySelector('#kh-ai-when');
  if (!box) return { setCode() {}, destroy() {} };

  let code = null;
  let doc = null;          // 파일 전체
  let timer = null;

  async function load() {
    try {
      /* 저장소 파일이라 /api 가 아니다. 서버가 그대로 내보낸다 */
      const r = await apiFetch('./data/ai-analysis.json', { cache: 'no-store' });
      if (!r || !r.ok) throw new Error(r && r.status);
      doc = await r.json();
    } catch {
      doc = null;
    }
    paint();
  }

  function paint() {
    if (when) when.textContent = doc && doc.at ? whenText(doc.at) : '—';

    if (!doc || !doc.codes) {
      box.innerHTML = '<span class="kh-mut">분석 파일을 불러오지 못했습니다</span>';
      return;
    }
    const d = code ? doc.codes[code] : null;
    if (!d) {
      box.innerHTML = '<span class="kh-mut">이 종목은 아직 없습니다 —'
        + ' 관심종목부터 쓰고 있습니다</span>';
      return;
    }

    const parts = PARTS.filter(p => d[p.key]).map(p => `
      <div class="kh-ai-p"><span class="kh-ai-l">${p.label}</span>
        <span>${esc(d[p.key])}</span></div>`).join('');

    /* consensus 가 null 이면 빨간 표시를 낸다 — 받아올 곳이 아직 없다
       (CLAUDE.md 「아직 안 정해진 자리는 빨간 바탕으로 남긴다」) */
    const cons = d.consensus
      ? `<div class="kh-ai-p"><span class="kh-ai-l">컨센서스</span>
           <span>${esc(d.consensus)}</span></div>`
      : `<div class="kh-todo"><b>컨센서스는 아직 연결하지 않았습니다</b>
           증권사 목표주가를 받아올 곳을 정하는 중입니다.</div>`;

    box.innerHTML = parts + cons;
  }

  timer = setInterval(() => { if (!document.hidden) load(); }, RELOAD_MS);
  load();

  return {
    setCode(next) {
      if (!next || next === code) return;
      code = next;
      paint();          // 파일은 이미 있다. 다시 받을 이유가 없다
    },
    destroy() { if (timer) clearInterval(timer); },
  };
}
