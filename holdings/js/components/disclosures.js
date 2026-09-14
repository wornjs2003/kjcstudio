/* ==========================================================================
   공시 목록 그리기

   첫 화면과 종목 화면이 같은 모양을 쓴다. 한 줄은
     회사이름(종목일 때는 생략) · 보고서 제목 · 접수 시각
   이고, 누르면 DART 원문이 새 창으로 열린다.

   못 받았을 때와 받았는데 없을 때를 구분해 적는다.
   그래야 연결이 안 된 건지 공시가 없는 건지 알 수 있다 (CLAUDE.md 데이터 규칙).
   ========================================================================== */

import { fetchDisclosures } from '../data/dart.js';

/* 20260914 → 09.14 */
function shortDate(s) {
  if (!s || s.length !== 8) return s || '';
  return `${s.slice(4, 6)}.${s.slice(6, 8)}`;
}

/* 제목 앞에 붙는 [기재정정] 같은 꼬리표를 떼어 따로 보여준다 */
function splitTag(title) {
  const m = /^\[([^\]]{1,10})\]\s*(.*)$/.exec(title || '');
  return m ? { tag: m[1], rest: m[2] } : { tag: null, rest: title || '' };
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function rowHtml(d, showName) {
  const { tag, rest } = splitTag(d.title);
  return `<a class="kh-dc-i" href="${esc(d.url)}" target="_blank" rel="noopener">
    ${showName ? `<span class="kh-dc-n">${esc(d.name)}</span>` : ''}
    <span class="kh-dc-t">${tag ? `<i class="kh-dc-tag">${esc(tag)}</i>` : ''}${esc(rest)}</span>
    <span class="kh-dc-d kh-num">${esc(shortDate(d.date))}</span>
  </a>`;
}

/**
 * 공시 목록을 host 에 그린다.
 *   code    : 종목코드. 없으면 감시 대상 전체
 *   limit   : 몇 줄까지
 *   showName: 회사 이름을 함께 보일지 (전체 목록이면 true)
 * 돌려주는 객체의 reload() 를 부르면 다시 받아 그린다.
 */
export function mountDisclosures(host, { code = null, limit = 8, showName = true } = {}) {
  if (!host) return { reload() {} };

  async function reload() {
    host.innerHTML = `<div class="kh-dc-empty">불러오는 중</div>`;
    const rows = await fetchDisclosures(code, limit);

    if (rows === null) {
      host.innerHTML = `<div class="kh-dc-empty">
        불러오지 못했습니다
        <span class="kh-dc-empty-s">중계 서버가 꺼져 있거나 인증키가 없습니다</span>
      </div>`;
      return;
    }
    if (!rows.length) {
      host.innerHTML = `<div class="kh-dc-empty">
        ${code ? '이 종목의 공시가 아직 없습니다' : '오늘 올라온 공시가 아직 없습니다'}
        <span class="kh-dc-empty-s">평일 장중에 접수되는 대로 채워집니다</span>
      </div>`;
      return;
    }
    host.innerHTML = rows.map(d => rowHtml(d, showName)).join('');
  }

  reload();
  return { reload };
}
