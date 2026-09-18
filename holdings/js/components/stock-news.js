/* ==========================================================================
   종목 뉴스 (2026-09-18 지시 — "이 종목 공시 -> 종목 뉴스 로 변경")

   전에는 이 자리가 「이 종목 공시」였다. 이름만 바꾸면 내용(OpenDART 공시)과
   어긋나므로 받아오는 곳도 뉴스로 바꿨다. **전체 공시는 오른쪽 칸에 그대로 있다.**

   ── 어디서 받나 ──

   네이버 종목별 뉴스다 (`/api/naver/news?code=...`). OpenDART 에는 뉴스가 없고,
   KIS 에도 종목별 뉴스 API 가 없다. 서버가 **묶음마다 첫 기사만** 골라 보내고
   같은 사건을 쓴 기사 수를 `more` 로 준다 — `server/naver.py` 의 news() 참고.

   ── 줄 모양은 공시와 같은 것을 쓴다 ──

   같은 패널 안에서 두 칸이 나란히 있던 자리라 모양이 다르면 눈에 걸린다.
   `.kh-dc-i` 계열 클래스를 그대로 쓴다 (`css/home.css`).
   ========================================================================== */

import { apiFetch } from '../data/api.js';

/* 202609181902 (YYYYMMDDHHMM) → 오늘 것이면 19:02, 아니면 09.18.
   칸 너비가 같도록 둘 다 다섯 글자다. */
function whenText(s) {
  const t = String(s || '');
  if (t.length < 12) return '';
  const ymd = t.slice(0, 8);
  const now = new Date();
  const today = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;
  return ymd === today ? `${t.slice(8, 10)}:${t.slice(10, 12)}`
                       : `${t.slice(4, 6)}.${t.slice(6, 8)}`;
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function rowHtml(n) {
  /* 같은 사건을 여러 곳이 썼으면 몇 개가 더 있는지 적는다. 하나뿐이면 안 적는다 */
  const more = n.more > 0 ? `<i class="kh-dc-tag">+${n.more}</i>` : '';
  const a = n.url ? `<a class="kh-dc-i" href="${esc(n.url)}" target="_blank" rel="noopener">`
                  : '<div class="kh-dc-i">';
  return `${a}
    <span class="kh-dc-n">${esc(n.office)}</span>
    <span class="kh-dc-t">${more}${esc(n.title)}</span>
    <span class="kh-dc-d kh-num">${esc(whenText(n.at))}</span>
  ${n.url ? '</a>' : '</div>'}`;
}

/**
 * 종목 뉴스를 host 에 그린다.
 *   limit : 몇 줄까지 (서버는 더 받아 두고 여기서 자른다)
 * setCode(code) 로 종목을 바꾸고, reload() 로 다시 받는다.
 */
export function mountStockNews(host, { limit = 6 } = {}) {
  if (!host) return { setCode() {}, reload() {} };

  let code = null;
  let seq = 0;              // 늦게 온 응답이 새 종목을 덮지 않게

  async function reload() {
    if (!code) return;
    const mine = ++seq;
    host.innerHTML = `<div class="kh-dc-empty">불러오는 중</div>`;
    let rows = null;
    try {
      const r = await apiFetch(`/api/naver/news?code=${code}`, { cache: 'no-store' });
      if (r && r.ok) {
        const j = await r.json();
        if (j && j.ok && Array.isArray(j.data)) rows = j.data;
      }
    } catch { /* 아래에서 못 받았다고 적는다 */ }
    if (mine !== seq) return;              // 그새 종목이 바뀌었다

    if (rows === null) {
      host.innerHTML = `<div class="kh-dc-empty">
        불러오지 못했습니다
        <span class="kh-dc-empty-s">중계 서버가 꺼져 있거나 네이버가 응답하지 않습니다</span>
      </div>`;
      return;
    }
    if (!rows.length) {
      host.innerHTML = `<div class="kh-dc-empty">
        이 종목의 뉴스가 아직 없습니다
        <span class="kh-dc-empty-s">올라오는 대로 채워집니다</span>
      </div>`;
      return;
    }
    host.innerHTML = rows.slice(0, limit).map(rowHtml).join('');
  }

  return {
    setCode(next) {
      if (!next || next === code) return;
      code = next;
      reload();
    },
    reload,
  };
}
