/* ==========================================================================
   고른 종목 패널 — 투자자 정보 · AI 분석 · 종목 뉴스 (2026-09-21 지시)

   재권님 말씀 —

       여기 모달에 있는걸 홀딩스의 메인화면에서 가져다 쓴다
       투자자 정보 · ai분석 · 종목뉴스는 해당 ui 높이의 각각 1/3 을 차지한다

   ── 한 벌로 두는 이유 ──

   같은 셋이 **두 자리**에 나온다.

       첫 화면      차트 오른쪽 세로 칸
       모달·종목화면  오른쪽 열 (전에는 「뉴스·공시」와 「개인·외국인·기관」이 있던 자리)

   마크업을 양쪽 HTML 에 두면 한쪽만 고쳐져 갈라진다. 그래서 **이 파일이
   마크업까지 만든다** — 붙일 자리만 건네받는다. `stock-view.js` 가
   stock.html 을 원본으로 삼는 것과 같은 생각이다.

   ── 셋이 1/3씩 ──

   높이는 CSS 가 `grid-template-rows: 1fr 1fr 1fr` 로 나눈다. 글이 길어도
   칸은 안 늘어나고 **그 칸 안에서 굴러간다** — 오늘만 세 번 겪은
   「칸이 늘면 차트가 끌려간다」 를 구조로 막는다.
   ========================================================================== */

import { mountInvestor } from './investor.js';
import { mountAiAnalysis } from './ai-analysis.js';
import { mountStockNews } from './stock-news.js';

const HTML = `
  <div class="kh-p3-s kh-iv-s">
    <div class="kh-p3-h"><b>투자자 정보</b>
      <span class="kh-chips kh-iv-tabs">
        <button class="kh-chip is-active" data-view="today">오늘</button>
        <button class="kh-chip" data-view="days">5일</button>
      </span>
      <span class="kh-bd kh-bd-on">한국투자증권</span></div>
    <div class="kh-p3-b kh-iv-box">불러오는 중</div>
  </div>

  <div class="kh-p3-s kh-ai-s">
    <div class="kh-p3-h"><b>AI 분석</b>
      <span class="kh-bd kh-bd-on kh-ai-when">—</span></div>
    <div class="kh-p3-b kh-ai-box">불러오는 중</div>
  </div>

  <div class="kh-p3-s">
    <div class="kh-p3-h"><b>종목 뉴스</b>
      <span class="kh-bd kh-bd-on">네이버</span></div>
    <div class="kh-p3-b kh-nw-box">불러오는 중</div>
  </div>`;

/**
 * 셋을 한 칸에 그린다.
 *   root : 이 안에 마크업을 만든다 (.kh-p3)
 * setCode(code) 로 종목을 바꾸고, destroy() 로 끝낸다.
 */
export function mountStockPanel(root, { code = null } = {}) {
  if (!root) return { setCode() {}, destroy() {} };

  root.classList.add('kh-p3');
  root.innerHTML = HTML;

  /* **id 를 쓰지 않는다.** 첫 화면과 모달이 동시에 떠 있으면 같은 id 가
     둘이 되어 엉뚱한 칸을 칠한다. 각자 제 root 안에서만 찾는다. */
  const q = (sel) => root.querySelector(sel);

  const investor = mountInvestor({ box: q('.kh-iv-box'), tabs: q('.kh-iv-tabs') });
  const ai = mountAiAnalysis({ box: q('.kh-ai-box'), when: q('.kh-ai-when') });
  const news = mountStockNews(q('.kh-nw-box'), { limit: 8 });

  if (code) { investor.setCode(code); ai.setCode(code); news.setCode(code); }

  return {
    setCode(next) {
      if (!next) return;
      investor.setCode(next);
      ai.setCode(next);
      news.setCode(next);
    },
    destroy() {
      investor.destroy();
      ai.destroy();
      if (news.destroy) news.destroy();
    },
  };
}
